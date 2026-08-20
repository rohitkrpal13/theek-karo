"""Integration hub admin router (Phase 19): webhook subscriptions + sync.

Webhook management is admin-only (``government_data.manage``); sync triggers
run through the existing govdata import pipeline with background support.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select

from tk_api.api.deps import DbSession, require_roles
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.govdata import service as gov_service
from tk_api.govdata.models import GovDataset
from tk_api.integrations import webhooks
from tk_api.integrations.models import WebhookSubscription
from tk_api.integrations.schemas import (
    WebhookDeliveryRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
)
from tk_api.integrations.webhooks import WebhookError, create_subscription

integrations_router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
AdminOnly = Annotated[Any, Depends(require_roles("admin"))]


@integrations_router.get(
    "/webhooks",
    response_model=list[WebhookSubscriptionRead],
    summary="List webhook subscriptions (Admin)",
)
async def list_webhooks(
    session: DbSession,
    user: AdminOnly,
) -> list[WebhookSubscriptionRead]:
    """List outgoing webhook subscriptions (secret_key_id shown, never the key)."""
    subs = await webhooks.list_subscriptions(session)
    return [WebhookSubscriptionRead.model_validate(s) for s in subs]


@integrations_router.post(
    "/webhooks",
    response_model=WebhookSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a webhook subscription (Admin)",
)
async def create_webhook(
    payload: WebhookSubscriptionCreate,
    session: DbSession,
    request: Request,
    user: AdminOnly,
) -> WebhookSubscriptionRead:
    """Register an outgoing webhook target. URL must be https and SSRF-safe;
    the HMAC signing key is derived from a server master secret — the raw key
    is never stored or returned."""
    try:
        sub = await create_subscription(
            session,
            name=payload.name,
            url=payload.url,
            events=payload.events,
            created_by=user.id,
        )
    except WebhookError as exc:
        raise ApiError(str(exc), 422, "webhook_invalid") from exc
    await audit(
        session,
        action="integrations.webhook_create",
        entity_type="webhook_subscription",
        entity_id=sub.id,
        actor_id=user.id,
        after={"name": payload.name, "url": payload.url, "events": payload.events},
        request=request,
    )
    await session.commit()
    await session.refresh(sub)
    return WebhookSubscriptionRead.model_validate(sub)


@integrations_router.delete(
    "/webhooks/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook subscription (Admin)",
)
async def delete_webhook(
    subscription_id: uuid.UUID,
    session: DbSession,
    request: Request,
    user: AdminOnly,
) -> None:
    """Remove a subscription (deliveries are cascade-deleted)."""
    sub = await session.get(WebhookSubscription, subscription_id)
    if sub is None:
        raise ApiError("webhook subscription not found", 404, "webhook_not_found")
    await session.delete(sub)
    await audit(
        session,
        action="integrations.webhook_delete",
        entity_type="webhook_subscription",
        entity_id=subscription_id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()


@integrations_router.get(
    "/webhooks/deliveries",
    response_model=list[WebhookDeliveryRead],
    summary="Webhook delivery log (Admin)",
)
async def webhook_deliveries(
    session: DbSession,
    subscription_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    user: AdminOnly = None,
) -> list[WebhookDeliveryRead]:
    """Recent delivery attempts with status, HTTP code, retry/error info."""
    rows = await webhooks.get_delivery_log(session, limit=limit, subscription_id=subscription_id)
    return [WebhookDeliveryRead.model_validate(r) for r in rows]


@integrations_router.post(
    "/connectors/{code}/sync",
    response_model=dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a connector sync (Admin)",
)
async def sync_connector(
    code: str,
    session: DbSession,
    request: Request,
    user: AdminOnly,
) -> dict[str, Any]:
    """Queue a sync for every active dataset mapped to this connector (spec §32:
    large imports run through the background worker). DEMO note: no live
    government API is called — connectors here are adapters over the admin-
    supplied payloads / seeded sandbox data (see docs/INTEGRATIONS.md)."""
    datasets = (
        (
            await session.execute(
                select(GovDataset).where(
                    GovDataset.connector_code == code,
                    GovDataset.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    if not datasets:
        raise ApiError(f"no active dataset uses connector '{code}'", 404, "dataset_not_found")

    queued: list[dict[str, Any]] = []
    for ds in datasets:
        job = await gov_service.trigger_import_job(
            session,
            dataset_id=ds.id,
            raw_payload=None,
            background=True,
            request=request,
        )
        queued.append(
            {
                "job_id": str(job.id),
                "dataset_id": str(ds.id),
                "dataset_name": ds.name,
                "status": job.status,
            }
        )
    await audit(
        session,
        action="integrations.connector_sync",
        entity_type="integration_connector",
        entity_id=None,
        actor_id=user.id,
        after={"connector_code": code, "jobs": queued},
        request=request,
    )
    return {
        "connector_code": code,
        "queued_jobs": queued,
        "note": (
            "Sandbox/demo sync: no live government API is invoked; imports "
            "consume admin-supplied payloads via the generic connector."
        ),
    }
