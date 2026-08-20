"""Communication service (Phase 26).

Unified communication pipeline: Event → Preference Check → Authorization →
Channel Selection → Queue → Provider → Delivery → Status → Retry → Analytics.

Extends the existing notification infrastructure with delivery tracking,
idempotency, retry with backoff, dead-letter, public alerts, templates,
campaigns, and analytics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.communication.models import (
    CommAnalytics,
    CommCampaign,
    CommTemplate,
    CommunicationEvent,
    DeliveryRecord,
    DigestRecord,
    PublicAlert,
    UserDevice,
)
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError, NotFoundError
from tk_api.notifications.models import (
    Notification,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Delivery States
# ---------------------------------------------------------------------------
DELIVERY_QUEUED = "queued"
DELIVERY_PROCESSING = "processing"
DELIVERY_SENT = "sent"
DELIVERY_DELIVERED = "delivered"
DELIVERY_FAILED = "failed"
DELIVERY_RETRYING = "retrying"
DELIVERY_CANCELLED = "cancelled"
DELIVERY_DEAD_LETTER = "dead_letter"


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------
PRIORITY_LOW = "low"
PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"
PRIORITY_CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Event Processing
# ---------------------------------------------------------------------------


async def record_event(
    session: AsyncSession,
    *,
    event_type: str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> CommunicationEvent:
    """Record an immutable communication event. Idempotent via idempotency_key."""
    if idempotency_key:
        existing = await session.scalar(
            select(CommunicationEvent).where(CommunicationEvent.idempotency_key == idempotency_key)
        )
        if existing:
            return existing  # idempotent — return existing event

    row = CommunicationEvent(
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        payload=payload or {},
        idempotency_key=idempotency_key,
    )
    session.add(row)
    return row


# ---------------------------------------------------------------------------
# Delivery Pipeline
# ---------------------------------------------------------------------------


async def create_delivery(
    session: AsyncSession,
    *,
    notification_id: uuid.UUID,
    channel: str,
    priority: str = PRIORITY_NORMAL,
    provider: str | None = None,
    max_attempts: int = 3,
) -> DeliveryRecord:
    """Create a delivery record for tracking. In-app deliveries are marked
    delivered immediately.
    """
    row = DeliveryRecord(
        notification_id=notification_id,
        channel=channel,
        status=DELIVERY_QUEUED if channel != "in_app" else DELIVERY_DELIVERED,
        provider=provider or channel,
        max_attempts=max_attempts,
        delivered_at=_utcnow() if channel == "in_app" else None,
    )
    session.add(row)
    return row


async def process_delivery(
    session: AsyncSession,
    record: DeliveryRecord,
    *,
    providers: dict[str, Any],
    settings: Any | None = None,
) -> DeliveryRecord:
    """Process a single delivery through the provider. Handles retry logic."""
    if record.status in (DELIVERY_DELIVERED, DELIVERY_CANCELLED, DELIVERY_DEAD_LETTER):
        return record

    provider = providers.get(record.channel)
    if provider is None:
        record.status = DELIVERY_FAILED
        record.error = f"no provider for channel {record.channel}"
        record.attempts += 1
        record.last_attempt_at = _utcnow()
        record.failed_at = _utcnow()
        return record

    # Fetch the notification for content
    notification = await session.get(Notification, record.notification_id)
    if notification is None:
        record.status = DELIVERY_FAILED
        record.error = "notification not found"
        record.failed_at = _utcnow()
        return record

    record.status = DELIVERY_PROCESSING
    record.last_attempt_at = _utcnow()
    record.attempts += 1

    try:
        result = provider.send(
            to=str(notification.user_id),
            subject=notification.subject,
            body=notification.body,
            metadata=notification.payload,
        )
        if result.ok:
            record.status = DELIVERY_DELIVERED
            record.delivered_at = _utcnow()
            record.provider_message_id = result.provider_message_id
            record.cost_estimate = result.cost
        else:
            record.status = DELIVERY_FAILED
            record.error = result.error
            record.failed_at = _utcnow()
    except Exception as exc:
        record.status = DELIVERY_FAILED
        record.error = str(exc)[:500]
        record.failed_at = _utcnow()

    # Retry logic
    if record.status == DELIVERY_FAILED and record.attempts < record.max_attempts:
        record.status = DELIVERY_RETRYING
        backoff = min(300, 30 * (2 ** (record.attempts - 1)))  # exponential, max 5 min
        record.next_attempt_at = _utcnow() + timedelta(seconds=backoff)
        record.failed_at = None  # reset since we'll retry
    elif record.status == DELIVERY_FAILED and record.attempts >= record.max_attempts:
        record.status = DELIVERY_DEAD_LETTER
        record.failed_at = _utcnow()

    return record


async def dispatch_due_deliveries(
    session: AsyncSession,
    *,
    providers: dict[str, Any],
    settings: Any | None = None,
    batch_size: int = 100,
) -> int:
    """Worker poll: dispatch all due delivery records."""
    now = _utcnow()
    rows = (
        (
            await session.execute(
                select(DeliveryRecord)
                .where(
                    DeliveryRecord.status.in_([DELIVERY_QUEUED, DELIVERY_RETRYING]),
                    (DeliveryRecord.next_attempt_at.is_(None))
                    | (DeliveryRecord.next_attempt_at <= now),
                )
                .order_by(DeliveryRecord.created_at.asc())
                .limit(batch_size)
            )
        )
        .scalars()
        .all()
    )

    processed = 0
    for row in rows:
        await process_delivery(session, row, providers=providers, settings=settings)
        processed += 1
        if processed % 25 == 0:
            await session.flush()

    if processed:
        await session.flush()
    return processed


# ---------------------------------------------------------------------------
# Public Alerts
# ---------------------------------------------------------------------------


async def create_alert(
    session: AsyncSession,
    *,
    title: str,
    body: str,
    category: str,
    severity: str = "info",
    source: str,
    source_url: str | None = None,
    geography_id: uuid.UUID | None = None,
    target_levels: list[str] | None = None,
    actor_id: uuid.UUID,
    expires_at: datetime | None = None,
) -> PublicAlert:
    row = PublicAlert(
        title=title,
        body=body,
        category=category,
        severity=severity,
        source=source,
        source_url=source_url,
        geography_id=geography_id,
        target_levels=target_levels or [],
        created_by=actor_id,
        expires_at=expires_at,
    )
    session.add(row)
    await audit(
        session,
        action="alert.create",
        entity_type="public_alert",
        entity_id=row.id,
        actor_id=actor_id,
        after={"title": title, "severity": severity},
    )
    return row


async def review_alert(
    session: AsyncSession,
    alert: PublicAlert,
    *,
    decision: str,  # published | rejected
    actor_id: uuid.UUID,
    note: str | None = None,
) -> PublicAlert:
    if alert.status not in ("draft", "review"):
        raise ApiError("alert cannot be reviewed in current state", 409, "invalid_state")
    alert.reviewed_by = actor_id
    alert.reviewed_at = _utcnow()
    alert.review_note = note
    if decision == "published":
        alert.status = "published"
        alert.published_at = _utcnow()
    elif decision == "rejected":
        alert.status = "rejected"
    else:
        raise ApiError("decision must be 'published' or 'rejected'", 422, "invalid_decision")
    await audit(
        session,
        action="alert.review",
        entity_type="public_alert",
        entity_id=alert.id,
        actor_id=actor_id,
        after={"decision": decision},
    )
    return alert


async def resolve_alert(
    session: AsyncSession,
    alert: PublicAlert,
    *,
    actor_id: uuid.UUID,
) -> PublicAlert:
    if alert.status != "published":
        raise ApiError("only published alerts can be resolved", 409, "invalid_state")
    alert.status = "resolved"
    alert.resolved_at = _utcnow()
    await audit(
        session,
        action="alert.resolve",
        entity_type="public_alert",
        entity_id=alert.id,
        actor_id=actor_id,
    )
    return alert


async def list_alerts(
    session: AsyncSession,
    *,
    status: str | None = None,
    geography_id: uuid.UUID | None = None,
    include_expired: bool = False,
    limit: int = 50,
) -> list[PublicAlert]:
    now = _utcnow()
    stmt = select(PublicAlert).order_by(PublicAlert.created_at.desc())
    if status:
        stmt = stmt.where(PublicAlert.status == status)
    else:
        stmt = stmt.where(PublicAlert.status.in_(["published", "resolved"]))
    if geography_id:
        stmt = stmt.where(PublicAlert.geography_id == geography_id)
    if not include_expired:
        stmt = stmt.where((PublicAlert.expires_at.is_(None)) | (PublicAlert.expires_at > now))
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def get_alert(session: AsyncSession, alert_id: uuid.UUID) -> PublicAlert:
    alert = await session.get(PublicAlert, alert_id)
    if alert is None:
        raise NotFoundError("alert not found", kind="alert_not_found")
    return alert


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


async def create_template(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    channel: str,
    locale: str = "en",
    subject: str | None = None,
    body_text: str = "",
    body_html: str | None = None,
    variables: list[str] | None = None,
    category: str = "system",
    created_by: uuid.UUID | None = None,
) -> CommTemplate:
    max_ver = await session.scalar(
        select(func.max(CommTemplate.version)).where(
            CommTemplate.code == code,
            CommTemplate.channel == channel,
            CommTemplate.locale == locale,
        )
    )
    next_ver = (max_ver or 0) + 1
    row = CommTemplate(
        code=code,
        name=name,
        channel=channel,
        locale=locale,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        version=next_ver,
        variables=variables or [],
        category=category,
        created_by=created_by,
    )
    session.add(row)
    return row


async def publish_template(
    session: AsyncSession,
    template: CommTemplate,
    *,
    actor_id: uuid.UUID,
) -> CommTemplate:
    if template.status == "published":
        raise ApiError("template already published", 409, "already_published")
    # Archive previous published version
    prev = await session.scalar(
        select(CommTemplate).where(
            CommTemplate.code == template.code,
            CommTemplate.channel == template.channel,
            CommTemplate.locale == template.locale,
            CommTemplate.status == "published",
        )
    )
    if prev:
        prev.status = "archived"
        prev.archived_at = _utcnow()
    template.status = "published"
    template.published_at = _utcnow()
    await audit(
        session,
        action="template.publish",
        entity_type="comm_template",
        entity_id=template.id,
        actor_id=actor_id,
        after={"code": template.code, "version": template.version},
    )
    return template


async def list_templates(
    session: AsyncSession,
    *,
    code: str | None = None,
    channel: str | None = None,
    locale: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[CommTemplate]:
    stmt = select(CommTemplate).order_by(CommTemplate.created_at.desc())
    if code:
        stmt = stmt.where(CommTemplate.code == code)
    if channel:
        stmt = stmt.where(CommTemplate.channel == channel)
    if locale:
        stmt = stmt.where(CommTemplate.locale == locale)
    if status:
        stmt = stmt.where(CommTemplate.status == status)
    return list((await session.execute(stmt.limit(limit))).scalars().all())


# ---------------------------------------------------------------------------
# User Devices
# ---------------------------------------------------------------------------


async def register_device(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    platform: str,
    push_token: str,
    device_name: str | None = None,
) -> UserDevice:
    # Check for existing device with same token
    existing = await session.scalar(
        select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.push_token == push_token,
        )
    )
    if existing:
        existing.is_active = True
        existing.last_active_at = _utcnow()
        existing.device_name = device_name or existing.device_name
        return existing

    row = UserDevice(
        user_id=user_id,
        platform=platform,
        push_token=push_token,
        device_name=device_name,
    )
    session.add(row)
    return row


async def revoke_device(
    session: AsyncSession,
    device: UserDevice,
    *,
    actor_id: uuid.UUID,
) -> UserDevice:
    device.is_active = False
    device.revoked_at = _utcnow()
    await audit(
        session,
        action="device.revoke",
        entity_type="user_device",
        entity_id=device.id,
        actor_id=actor_id,
    )
    return device


async def list_user_devices(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_inactive: bool = False,
) -> list[UserDevice]:
    stmt = select(UserDevice).where(UserDevice.user_id == user_id)
    if not include_inactive:
        stmt = stmt.where(UserDevice.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------


async def create_campaign(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    category: str = "community",
    channel: str,
    subject: str | None = None,
    body: str,
    audience_filter: dict[str, Any] | None = None,
    actor_id: uuid.UUID,
) -> CommCampaign:
    row = CommCampaign(
        name=name,
        description=description,
        category=category,
        channel=channel,
        subject=subject,
        body=body,
        audience_filter=audience_filter or {},
        created_by=actor_id,
    )
    session.add(row)
    await audit(
        session,
        action="campaign.create",
        entity_type="comm_campaign",
        entity_id=row.id,
        actor_id=actor_id,
        after={"name": name, "channel": channel},
    )
    return row


async def approve_campaign(
    session: AsyncSession,
    campaign: CommCampaign,
    *,
    actor_id: uuid.UUID,
    estimated_recipients: int = 0,
) -> CommCampaign:
    if campaign.status not in ("draft", "review"):
        raise ApiError("campaign cannot be approved in current state", 409, "invalid_state")
    campaign.status = "approved"
    campaign.approved_by = actor_id
    campaign.approved_at = _utcnow()
    campaign.estimated_recipients = estimated_recipients
    await audit(
        session,
        action="campaign.approve",
        entity_type="comm_campaign",
        entity_id=campaign.id,
        actor_id=actor_id,
    )
    return campaign


async def cancel_campaign(
    session: AsyncSession,
    campaign: CommCampaign,
    *,
    actor_id: uuid.UUID,
) -> CommCampaign:
    if campaign.status in ("completed", "cancelled"):
        raise ApiError("campaign already finished", 409, "invalid_state")
    campaign.status = "cancelled"
    campaign.cancelled_at = _utcnow()
    await audit(
        session,
        action="campaign.cancel",
        entity_type="comm_campaign",
        entity_id=campaign.id,
        actor_id=actor_id,
    )
    return campaign


async def list_campaigns(
    session: AsyncSession,
    *,
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[CommCampaign]:
    stmt = select(CommCampaign).order_by(CommCampaign.created_at.desc())
    if status:
        stmt = stmt.where(CommCampaign.status == status)
    if category:
        stmt = stmt.where(CommCampaign.category == category)
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def get_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> CommCampaign:
    campaign = await session.get(CommCampaign, campaign_id)
    if campaign is None:
        raise NotFoundError("campaign not found", kind="campaign_not_found")
    return campaign


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


async def get_communication_analytics(
    session: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    now = _utcnow()
    from_date = date_from or (now - timedelta(days=30))
    to_date = date_to or now

    stmt = select(CommAnalytics).where(
        CommAnalytics.date >= from_date,
        CommAnalytics.date <= to_date,
    )
    if channel:
        stmt = stmt.where(CommAnalytics.channel == channel)

    rows = (await session.execute(stmt.order_by(CommAnalytics.date.asc()))).scalars().all()

    totals = {
        "events_created": sum(r.events_created for r in rows),
        "notifications_sent": sum(r.notifications_sent for r in rows),
        "delivered": sum(r.delivered for r in rows),
        "failed": sum(r.failed for r in rows),
        "read_count": sum(r.read_count for r in rows),
        "suppressed": sum(r.suppressed for r in rows),
        "cost": float(sum(r.cost for r in rows)),
    }

    by_channel: dict[str, dict[str, int]] = {}
    for r in rows:
        ch = by_channel.setdefault(r.channel, {"sent": 0, "delivered": 0, "failed": 0})
        ch["sent"] += r.notifications_sent
        ch["delivered"] += r.delivered
        ch["failed"] += r.failed

    delivery_rate = (
        totals["delivered"] / totals["notifications_sent"]
        if totals["notifications_sent"] > 0
        else 0
    )

    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "totals": totals,
        "by_channel": by_channel,
        "delivery_rate": round(delivery_rate, 4),
        "methodology": {
            "definition": "Aggregated communication metrics over the specified period.",
            "period": f"{from_date.date()} to {to_date.date()}",
            "limitations": "Cost estimates are approximate. Delivery rate excludes in-app.",
        },
    }


async def get_provider_health(
    session: AsyncSession,
    providers: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for name, provider in providers.items():
        health = provider.check_health()
        # Get recent failure count
        recent_failures = (
            await session.scalar(
                select(func.count(DeliveryRecord.id)).where(
                    DeliveryRecord.channel == name,
                    DeliveryRecord.status == DELIVERY_FAILED,
                    DeliveryRecord.last_attempt_at >= _utcnow() - timedelta(hours=24),
                )
            )
            or 0
        )
        health["recent_failures_24h"] = recent_failures
        results.append(health)
    return results


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------


async def create_digest_record(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    digest_type: str,
    period_start: datetime,
    period_end: datetime,
    notification_count: int,
    channel: str = "email",
) -> DigestRecord:
    # Check for existing digest in this period
    existing = await session.scalar(
        select(DigestRecord).where(
            DigestRecord.user_id == user_id,
            DigestRecord.digest_type == digest_type,
            DigestRecord.period_start == period_start,
        )
    )
    if existing:
        existing.notification_count = notification_count
        return existing

    row = DigestRecord(
        user_id=user_id,
        digest_type=digest_type,
        period_start=period_start,
        period_end=period_end,
        notification_count=notification_count,
        channel=channel,
    )
    session.add(row)
    return row
