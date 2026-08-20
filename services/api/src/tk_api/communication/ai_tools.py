"""Communication MCP tools (Phase 26).

Read-only AI-assisted tools for communication operations.
AI may assist with notification summaries, alert explanations, and preference
management. All tools enforce authorization — AI never bypasses permissions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def tool_get_notification_summary(
    session: AsyncSession,
    user_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Summarize unread notifications for a user. Public-safe metadata only."""
    from tk_api.notifications.models import Notification

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": "Invalid user UUID format"}

    total = (
        await session.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == uid,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )

    # Count by event group
    rows = (
        await session.execute(
            select(Notification.event, func.count(Notification.id))
            .where(
                Notification.user_id == uid,
                Notification.read_at.is_(None),
            )
            .group_by(Notification.event)
        )
    ).all()

    by_event = {row[0]: row[1] for row in rows}

    return {
        "user_id": user_id,
        "unread_count": total,
        "by_event": by_event,
        "disclaimer": "Summary is advisory; detailed notification data requires direct access.",
    }


async def tool_explain_alert(
    session: AsyncSession,
    alert_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Explain a public alert with source, verification, and limitations."""
    from tk_api.communication.models import PublicAlert

    try:
        aid = uuid.UUID(alert_id)
    except ValueError:
        return {"error": "Invalid alert UUID format"}

    alert = await session.get(PublicAlert, aid)
    if alert is None:
        return {"error": "Alert not found"}

    return {
        "id": str(alert.id),
        "title": alert.title,
        "category": alert.category,
        "severity": alert.severity,
        "status": alert.status,
        "source": alert.source,
        "verified": alert.verified,
        "published_at": alert.published_at.isoformat() if alert.published_at else None,
        "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "disclaimer": (
            "Alert information is sourced from: "
            + alert.source
            + ". Always verify with official sources for emergency decisions."
        ),
    }


async def tool_get_delivery_status(
    session: AsyncSession,
    notification_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Get delivery status for a notification across all channels."""
    from tk_api.communication.models import DeliveryRecord

    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        return {"error": "Invalid notification UUID format"}

    rows = (
        (await session.execute(select(DeliveryRecord).where(DeliveryRecord.notification_id == nid)))
        .scalars()
        .all()
    )

    return {
        "notification_id": notification_id,
        "deliveries": [
            {
                "channel": d.channel,
                "status": d.status,
                "provider": d.provider,
                "attempts": d.attempts,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
                "error": d.error,
            }
            for d in rows
        ],
        "count": len(rows),
    }


async def tool_get_communication_analytics(
    session: AsyncSession,
    channel: str | None = None,
    days: int = 30,
    **kwargs: Any,
) -> dict[str, Any]:
    """Aggregate communication analytics for the specified period."""
    from tk_api.communication.models import CommAnalytics

    since = datetime.now(UTC) - timedelta(days=min(days, 365))
    stmt = select(CommAnalytics).where(CommAnalytics.date >= since)
    if channel:
        stmt = stmt.where(CommAnalytics.channel == channel)
    rows = (await session.execute(stmt)).scalars().all()

    totals = {
        "notifications_sent": sum(r.notifications_sent for r in rows),
        "delivered": sum(r.delivered for r in rows),
        "failed": sum(r.failed for r in rows),
        "read_count": sum(r.read_count for r in rows),
        "suppressed": sum(r.suppressed for r in rows),
    }
    delivery_rate = (
        totals["delivered"] / totals["notifications_sent"]
        if totals["notifications_sent"] > 0
        else 0
    )

    return {
        "period_days": days,
        "totals": totals,
        "delivery_rate": round(delivery_rate, 4),
        "methodology": {
            "definition": "Aggregated communication metrics over the specified period.",
            "limitations": "Cost estimates are approximate.",
        },
    }


async def tool_summarize_unread(
    session: AsyncSession,
    user_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Summarize today's unread notifications for a user in simple terms."""
    from tk_api.notifications.models import Notification

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": "Invalid user UUID format"}

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        (
            await session.execute(
                select(Notification)
                .where(
                    Notification.user_id == uid,
                    Notification.read_at.is_(None),
                    Notification.created_at >= today_start,
                )
                .order_by(Notification.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )

    events: dict[str, int] = {}
    for n in rows:
        events[n.event] = events.get(n.event, 0) + 1

    return {
        "user_id": user_id,
        "today_unread": len(rows),
        "by_event": events,
        "summary": (
            f"You have {len(rows)} new notifications today."
            if rows
            else "No new notifications today."
        ),
        "disclaimer": "AI summary is advisory. Check the notification center for details.",
    }
