"""Notification endpoints (API.md §9)."""

from __future__ import annotations

import hmac
import uuid
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from tk_api.api.deps import CurrentUser, DbSession
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.notifications import service as notifications_service

notifications_router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class DeliveryReceiptIn(BaseModel):
    """Delivery-status callback from a notification provider.

    Sandbox providers (console/SMTP) call this directly in dev; production
    requires the shared callback secret (see ``record_receipt``).
    """

    notification_id: str = Field(min_length=1, max_length=64)
    channel: str = Field(min_length=1, max_length=32)
    status: str = Field(min_length=1, max_length=32)
    provider_message_id: str | None = Field(default=None, max_length=256)
    error: str | None = Field(default=None, max_length=1024)


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


@notifications_router.get("/preferences", summary="Notification preferences")
async def get_preferences(user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await notifications_service.get_preferences(session, user.id)


@notifications_router.patch("/preferences", summary="Update preferences (channel x event groups)")
async def update_preferences(
    body: dict[str, Any],
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="notify", key=f"write:{client_ip(request)}", limit=30, window_seconds=60
    )
    return await notifications_service.update_preferences(
        session, user_id=user.id, changes=body, actor=user, request=request
    )


@notifications_router.get("", summary="Own notification history (in-app)")
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    return await notifications_service.list_notifications(session, user.id, limit=limit)


@notifications_router.get("/unread-count", summary="Unread notification count (bell badge)")
async def unread_notifications(user: CurrentUser, session: DbSession) -> dict[str, int]:
    return await notifications_service.unread_count(session, user.id)


@notifications_router.post("/mark-read", summary="Mark notifications as read")
async def mark_notifications_read(
    body: dict[str, Any],
    user: CurrentUser,
    session: DbSession,
) -> dict[str, int]:
    """Body: {"notification_ids": [...]}, {"group_key": "..."}, or {"all": true}."""
    notification_ids = body.get("notification_ids")
    group_key = body.get("group_key")
    all_read = body.get("all")
    if isinstance(all_read, str):
        all_read = all_read.lower() == "true"
    parsed_ids: list[uuid.UUID] = []
    if notification_ids is not None:
        if not isinstance(notification_ids, list) or not notification_ids:
            raise ApiError("notification_ids must be a non-empty list", 422, "invalid_payload")
        try:
            parsed_ids = [uuid.UUID(str(raw)) for raw in notification_ids]
        except ValueError as exc:
            raise ApiError("invalid notification id", 422, "invalid_notification_id") from exc
    return await notifications_service.mark_read(
        session,
        user.id,
        notification_ids=parsed_ids,
        group_key=group_key if isinstance(group_key, str) else None,
        all_read=all_read is True,
    )


@notifications_router.post("/receipts", summary="Delivery status callback (sandbox providers)")
async def record_receipt(
    body: DeliveryReceiptIn,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="notify", key=f"receipt:{client_ip(request)}", limit=120, window_seconds=60
    )
    # Production providers must authenticate callbacks with the shared secret;
    # in sandbox environments (console/SMTP) the endpoint stays open so local
    # development and tests can exercise the full delivery loop.
    settings = request.app.state.settings
    if settings.is_production:
        expected = settings.notification_callback_secret or ""
        provided = request.headers.get("X-TK-Callback-Key", "")
        if not expected or not hmac.compare_digest(provided, expected):
            raise ApiError(
                "unsigned delivery callbacks are not accepted", 403, "invalid_callback_signature"
            )
    return await notifications_service.record_receipt(
        session,
        notification_id=_parse_id(
            body.notification_id, kind="notification", error_kind="invalid_notification_id"
        ),
        channel=body.channel,
        status=body.status,
        provider_message_id=body.provider_message_id,
        error=body.error,
    )
