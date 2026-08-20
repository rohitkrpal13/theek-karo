"""Integration hub entities (Phase 19): connector registry, transactional
outbox, and signed outgoing webhooks.

Invariants (ADR-057):

- ``IntegrationConnector`` rows hold **no secrets** — ``config`` is non-secret
  settings only; ``auth_type`` is a label (api_key/oauth2/...); credentials
  live in environment / the platform secret manager. Status drives a circuit
  breaker (UNKNOWN → HEALTHY | DEGRADED | CIRCUIT_OPEN | RECOVERING).
- ``OutboxEvent`` rows are written inside the same DB transaction as the
  action that caused them (report.created, dataset.updated, ...) so external
  delivery cannot diverge from committed state. The worker dispatches due
  rows to matching subscriptions.
- ``WebhookSubscription`` stores a random ``secret_key_id`` only — the HMAC
  key is derived from a server master secret + this id, so the raw secret is
  never persisted. Deliveries retry with backoff and dead-letter.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class IntegrationConnector(Base):
    __tablename__ = "integration_connectors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    auth_type: Mapped[str] = mapped_column(String(32))
    endpoint: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    sync_frequency_hours: Mapped[int | None] = mapped_column(Integer)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    records_imported: Mapped[int] = mapped_column(BigInteger, default=0)
    records_rejected: Mapped[int] = mapped_column(BigInteger, default=0)
    rate_limit_remaining: Mapped[int | None] = mapped_column(Integer)
    retry_after_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schema_fingerprint: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('UNKNOWN', 'HEALTHY', 'DEGRADED', 'CIRCUIT_OPEN', 'RECOVERING')",
            name="ck_integration_connectors_status",
        ),
        CheckConstraint(
            "auth_type IN ('none', 'public', 'api_key', 'oauth2', 'jwt', 'service_account')",
            name="ck_integration_connectors_auth_type",
        ),
    )


class OutboxEvent(Base):
    """Transactional outbox: one row per external event, written in-transaction."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event: Mapped[str] = mapped_column(String(64))
    aggregate_type: Mapped[str] = mapped_column(String(64))
    aggregate_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    payload: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_outbox_events_due", "status", "next_attempt_at"),
        CheckConstraint(
            "status IN ('PENDING', 'DELIVERING', 'DELIVERED', 'FAILED', 'DEAD')",
            name="ck_outbox_events_status",
        ),
    )


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    events: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    secret_key_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_webhook_subscriptions_status", "status"),
        CheckConstraint(
            "status IN ('active', 'paused', 'disabled')", name="ck_webhook_subscriptions_status"
        ),
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE")
    )
    outbox_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    http_status: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_webhook_deliveries_due", "status", "next_attempt_at"),
        Index("ix_webhook_deliveries_event", "outbox_event_id"),
        CheckConstraint(
            "status IN ('PENDING', 'SUCCESS', 'FAILED', 'DEAD')",
            name="ck_webhook_deliveries_status",
        ),
        UniqueConstraint(
            "subscription_id", "outbox_event_id", name="uq_webhook_deliveries_event_once"
        ),
    )
