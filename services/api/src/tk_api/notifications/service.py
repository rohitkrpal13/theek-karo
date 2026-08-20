"""Notification service: enqueue, dispatch, preferences, receipts (API.md §9).

The API enqueues rows into ``notification_queue``; the Celery worker dispatches
them through the channel providers, respects preferences + quiet hours, and
records in-app history + delivery receipts. Providers are the console sandbox
in dev/tests (DLT SMS + email plug in later).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.core.audit import audit
from tk_api.core.config import Settings
from tk_api.core.errors import ApiError
from tk_api.notifications.models import (
    Notification,
    NotificationPreference,
    NotificationQueue,
    NotificationReceipt,
    NotificationTemplate,
)
from tk_api.notifications.queue import render_with_status_label, should_dispatch


class NotificationError(ApiError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# enqueue (API side)
# ---------------------------------------------------------------------------


async def enqueue(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    event: str,
    locale: str,
    payload: dict[str, Any],
    channels: list[str],
    actor_id: uuid.UUID | None = None,
    group_key: str | None = None,
    request: Request | None = None,
) -> int:
    """Queue one delivery per enabled channel. In-app rows are also written
    immediately (history is source-of-truth for the UI)."""
    queued = 0
    for channel in channels:
        row = NotificationQueue(
            user_id=user_id,
            event=event,
            channel=channel,
            locale=locale,
            payload=payload,
            group_key=group_key,
        )
        session.add(row)
        queued += 1

        if channel == "in_app":
            template = await session.scalar(
                select(NotificationTemplate).where(
                    NotificationTemplate.event == event,
                    NotificationTemplate.channel == "in_app",
                    NotificationTemplate.locale == locale,
                )
            )
            body = (
                render_with_status_label(template.body_text, payload, locale=locale)
                if template
                else ""
            )
            notification = Notification(
                user_id=user_id,
                event=event,
                channel="in_app",
                subject=template.subject_key if template else event,
                body=body,
                payload=payload,
                group_key=group_key,
            )
            session.add(notification)
            row.status = "done"
            row.delivered_at = _utcnow()

    await session.flush()
    if request is not None:
        await audit(
            session,
            action="notification.enqueue",
            entity_type="notification_queue",
            actor_id=actor_id,
            after={"event": event, "channels": channels},
            request=request,
        )
    return queued


# ---------------------------------------------------------------------------
# worker side
# ---------------------------------------------------------------------------


async def process_queue_row(
    session: AsyncSession,
    *,
    row: NotificationQueue,
    settings: Settings,
    providers: dict[str, Any],
) -> None:
    """Dispatch one queued row: quiet-hours + preference gate → provider or
    in-app history → receipt. Exceptions mark the row failed (re-queued later)."""
    if row.status == "done":
        return

    if not await should_dispatch(
        session,
        user_id=row.user_id,
        channel=row.channel,
        event=row.event,
        quiet_hours_default=settings.quiet_hours_default,
    ):
        # quiet hours / disabled: defer to after the window (next day)
        row.attempts += 1
        row.next_attempt_at = _utcnow() + timedelta(hours=12)
        return

    template = await session.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.event == row.event,
            NotificationTemplate.channel == row.channel,
            NotificationTemplate.locale == row.locale,
        )
    )
    body = (
        render_with_status_label(template.body_text, row.payload, locale=row.locale)
        if template
        else ""
    )

    # every channel writes history (the UI surfaces in-app; sms/email rows are
    # the delivery audit trail each receipt points at)
    notification = Notification(
        user_id=row.user_id,
        event=row.event,
        channel=row.channel,
        subject=template.subject_key if template else row.event,
        body=body,
        payload=row.payload,
        group_key=row.group_key,
    )
    session.add(notification)
    await session.flush()

    if row.channel == "in_app":
        row.status = "done"
        row.delivered_at = _utcnow()
        return
    provider = providers.get(row.channel)
    if provider is None:
        row.status = "failed"
        row.error = f"no provider for channel {row.channel}"
        row.attempts += 1
        return
    if row.channel == "sms":
        delivery = provider.send(to_contact=str(row.user_id), body=body, message_id=str(row.id))
    else:
        delivery = provider.send(
            to_contact=str(row.user_id),
            subject=template.subject_key if template else row.event,
            body=body,
            message_id=str(row.id),
        )
    if delivery.ok:
        session.add(
            NotificationReceipt(
                notification_id=notification.id,
                channel=row.channel,
                provider_message_id=delivery.provider_message_id,
                status="delivered",
                delivered_at=_utcnow(),
            )
        )
        row.status = "done"
        row.delivered_at = _utcnow()
    else:
        row.attempts += 1
        row.error = delivery.error
        row.next_attempt_at = _utcnow() + timedelta(seconds=settings.notification_backoff_seconds)
        if row.attempts >= settings.notification_max_attempts:
            row.status = "failed"


async def dispatch_due(
    session: AsyncSession, *, settings: Settings, providers: dict[str, Any]
) -> int:
    """Worker poll: dispatch all due queued rows (one batch)."""
    rows = (
        (
            await session.execute(
                select(NotificationQueue)
                .where(
                    NotificationQueue.status == "queued",
                    NotificationQueue.next_attempt_at.is_(None)
                    | (NotificationQueue.next_attempt_at <= _utcnow()),
                )
                .order_by(NotificationQueue.created_at.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    for idx, row in enumerate(rows):
        try:
            await process_queue_row(session, row=row, settings=settings, providers=providers)
        except Exception as exc:
            row.status = "failed"
            row.error = str(exc)[:500]
        if idx % 25 == 0:
            await session.flush()
    await session.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# preferences + history (API side)
# ---------------------------------------------------------------------------

EVENT_GROUPS = ("status_change", "collaboration", "ai", "community", "system", "security")
CHANNELS = ("in_app", "sms", "email")
LOCKED_GROUPS = ("security",)


async def get_preferences(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    rows = (
        (
            await session.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    by_channel: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_channel.setdefault(row.channel, {})[row.event_group] = {
            "enabled": row.enabled,
            "locked": row.locked,
            "quiet_hours": row.quiet_hours,
        }
    # fill defaults for what's missing
    for channel in CHANNELS:
        entry = by_channel.setdefault(channel, {})
        for group in EVENT_GROUPS:
            entry.setdefault(
                group, {"enabled": True, "locked": group in LOCKED_GROUPS, "quiet_hours": None}
            )
    return {"channels": by_channel}


async def update_preferences(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    changes: dict[str, Any],
    actor: Any,
    request: Request,
) -> dict[str, Any]:
    """PATCH body: {"status_change": {"sms": false}} or {"sms": {"quiet_hours": {...}}}."""
    applied: list[dict[str, Any]] = []
    for group, group_changes in changes.items():
        if group not in EVENT_GROUPS:
            raise NotificationError(f"unknown event group: {group}", 422, "invalid_payload")
        if not isinstance(group_changes, dict):
            raise NotificationError(
                "event group must map to channel settings", 422, "invalid_payload"
            )
        for channel, value in group_changes.items():
            if channel not in CHANNELS:
                raise NotificationError(f"unknown channel: {channel}", 422, "invalid_payload")
            if not isinstance(value, dict):
                value = {"enabled": bool(value)}
            pref = await session.scalar(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.channel == channel,
                    NotificationPreference.event_group == group,
                )
            )
            if pref is None:
                pref = NotificationPreference(
                    user_id=user_id,
                    channel=channel,
                    event_group=group,
                    enabled=True,
                    locked=group in LOCKED_GROUPS,
                )
                session.add(pref)
            if "enabled" in value:
                if pref.locked:
                    raise NotificationError(
                        f"event group '{group}' cannot be disabled",
                        409,
                        "locked_preference",
                    )
                pref.enabled = bool(value["enabled"])
            if "quiet_hours" in value:
                pref.quiet_hours = value["quiet_hours"]
            applied.append({"channel": channel, "event_group": group, "pref": value})
    await audit(
        session,
        action="notification.preferences_update",
        entity_type="notification_preference",
        actor_id=actor.id,
        after={"changes": changes},
        request=request,
    )
    await session.commit()
    return await get_preferences(session, user_id)


async def list_notifications(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int
) -> dict[str, Any]:
    """Grouped in-app history: unread rows sharing a group_key collapse into
    one entry ("12 new comments"), each carrying a ``count``; read rows and
    ungrouped events stay individual. Nothing is auto-marked read here — the
    client calls ``mark_read`` when the user opens a group."""
    rows = (
        (
            await session.execute(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .limit(max(1, min(limit, 100)) * 3)
            )
        )
        .scalars()
        .all()
    )
    unread_total = (
        (
            await session.execute(
                select(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
                .with_only_columns(Notification.id)
            )
        )
        .scalars()
        .all()
    )

    items: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    for n in rows:
        entry = {
            "id": str(n.id),
            "event": n.event,
            "channel": n.channel,
            "subject": n.subject,
            "body": n.body,
            "payload": n.payload,
            "read": n.read_at is not None,
            "created_at": n.created_at,
            "count": 1,
        }
        if not entry["read"] and n.group_key:
            if n.group_key in groups:
                group = groups[n.group_key]
                group["count"] += 1
                continue
            groups[n.group_key] = entry
            entry["group_key"] = n.group_key
        items.append(entry)
    return {"items": items, "unread": len(unread_total)}


async def mark_read(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    notification_ids: list[uuid.UUID] | None = None,
    group_key: str | None = None,
    all_read: bool = False,
) -> dict[str, int]:
    """Mark specific notifications, a whole group, or everything read. Only
    rows owned by the user can be affected (no cross-user IDOR)."""
    stmt = update(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if notification_ids:
        stmt = stmt.where(Notification.id.in_(notification_ids))
    elif group_key:
        stmt = stmt.where(Notification.group_key == group_key)
    elif not all_read:
        return {"marked": 0}
    result = await session.execute(stmt.values(read_at=_utcnow()))
    await session.commit()
    rowcount = getattr(result, "rowcount", 0)
    return {"marked": int(rowcount or 0)}


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    total = (
        (
            await session.execute(
                select(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
                .with_only_columns(Notification.id)
            )
        )
        .scalars()
        .all()
    )
    return {"unread": len(total)}


async def record_receipt(
    session: AsyncSession,
    *,
    notification_id: uuid.UUID,
    channel: str,
    status: str,
    provider_message_id: str | None,
    error: str | None,
) -> dict[str, Any]:
    receipt = NotificationReceipt(
        notification_id=notification_id,
        channel=channel,
        status=status,
        provider_message_id=provider_message_id,
        error=error,
        delivered_at=_utcnow() if status == "delivered" else None,
    )
    session.add(receipt)
    await session.commit()
    return {"id": str(receipt.id), "status": receipt.status}
