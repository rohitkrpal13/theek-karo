"""Communication models (Phase 26).

Extends existing notification infrastructure with:
- Delivery records (per-channel delivery tracking with retry/dead-letter)
- Communication events (standardized event model)
- Template versioning & localization
- Public alerts with geo-targeting
- User devices & push tokens
- Campaign communication
- Digest scheduling
- Communication analytics
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


# ---------------------------------------------------------------------------
# Communication Events (standardized event model)
# ---------------------------------------------------------------------------


class CommunicationEvent(Base):
    """Immutable event log for communication system. Every event that triggers
    a notification or alert is recorded here for audit and analytics.
    """

    __tablename__ = "communication_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    payload: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(Text, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_comm_events_type_created", "event_type", "created_at"),)


# ---------------------------------------------------------------------------
# Delivery Records (per-channel tracking)
# ---------------------------------------------------------------------------


class DeliveryRecord(Base):
    """Tracks each delivery attempt per channel per notification.
    Supports retry, dead-letter, and delivery receipts.
    """

    __tablename__ = "delivery_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    provider: Mapped[str | None] = mapped_column(String(32))
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(10, 4))
    extra_data: Mapped[dict[str, Any]] = mapped_column("extra_data", _jsonb(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            (
                "status IN ('queued','processing','sent','delivered','failed','retrying',"
                " 'cancelled','dead_letter')"
            ),
            name="ck_delivery_records_status",
        ),
        CheckConstraint(
            "channel IN ('in_app','email','sms','push','whatsapp')",
            name="ck_delivery_records_channel",
        ),
        Index("ix_delivery_records_channel_status", "channel", "status"),
    )


# ---------------------------------------------------------------------------
# Template Versioning
# ---------------------------------------------------------------------------


class CommTemplate(Base):
    """Versioned communication template. Supports multiple locales,
    channel variants, and a lifecycle (draft → published → archived).
    """

    __tablename__ = "comm_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(16))
    locale: Mapped[str] = mapped_column(String(8), default="en")
    subject: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    variables: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    category: Mapped[str] = mapped_column(String(32), default="system")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("code", "channel", "locale", "version", name="uq_template_version"),
        CheckConstraint(
            "status IN ('draft','published','archived')",
            name="ck_comm_templates_status",
        ),
    )


# ---------------------------------------------------------------------------
# Public Alerts
# ---------------------------------------------------------------------------


class PublicAlert(Base):
    """Public alert with geo-targeting, lifecycle, and verification status.
    Requires authorized publication. Draft → Review → Published → Resolved → Archived.
    """

    __tablename__ = "public_alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16), default="info")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    source: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL"), index=True
    )
    geojson: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    target_levels: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','review','published','resolved','archived','rejected')",
            name="ck_public_alerts_status",
        ),
        CheckConstraint(
            "severity IN ('info','warning','critical','emergency')",
            name="ck_public_alerts_severity",
        ),
    )


# ---------------------------------------------------------------------------
# User Devices & Push Tokens
# ---------------------------------------------------------------------------


class UserDevice(Base):
    """Registered device for push notifications. Tokens are never exposed via API."""

    __tablename__ = "user_devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(16))
    push_token: Mapped[str] = mapped_column(Text)
    device_name: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "platform IN ('web','ios','android')",
            name="ck_user_devices_platform",
        ),
    )


# ---------------------------------------------------------------------------
# Campaign Communication
# ---------------------------------------------------------------------------


class CommCampaign(Base):
    """Bulk communication campaign with audience targeting, scheduling, and delivery tracking.
    Requires authorization and approval workflow.
    """

    __tablename__ = "comm_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), default="community")
    channel: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    audience_filter: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    estimated_recipients: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(10, 4))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            (
                "status IN ('draft','review','approved','scheduled','sending','paused',"
                " 'completed','cancelled')"
            ),
            name="ck_comm_campaigns_status",
        ),
    )


# ---------------------------------------------------------------------------
# Communication Analytics
# ---------------------------------------------------------------------------


class CommAnalytics(Base):
    """Daily aggregated communication analytics per channel/category."""

    __tablename__ = "comm_analytics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(32), default="system")
    events_created: Mapped[int] = mapped_column(Integer, default=0)
    notifications_sent: Mapped[int] = mapped_column(Integer, default=0)
    delivered: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    suppressed: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("date", "channel", "category", name="uq_comm_analytics_daily"),
    )


# ---------------------------------------------------------------------------
# Digest Records
# ---------------------------------------------------------------------------


class DigestRecord(Base):
    """Tracks generated digests to prevent duplicates and support delivery."""

    __tablename__ = "digest_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    digest_type: Mapped[str] = mapped_column(String(16))  # daily | weekly
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notification_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(16), default="email")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "digest_type IN ('daily','weekly')",
            name="ck_digest_records_type",
        ),
        UniqueConstraint("user_id", "digest_type", "period_start", name="uq_digest_user_period"),
    )
