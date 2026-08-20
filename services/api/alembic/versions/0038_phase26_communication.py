"""Phase 26 — Communication & Notification tables.

Revision ID: 0038_phase26_comm
Revises: 0037_phase25_gov
Create Date: 2026-08-18

Tables created:
- communication_events
- delivery_records
- comm_templates
- public_alerts
- user_devices
- comm_campaigns
- comm_analytics
- digest_records
"""

from __future__ import annotations

import uuid as _uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0038_phase26_comm"
down_revision: str | None = "0037_phase25_gov"
branch_labels: str | None = None
depends_on: str | None = None


def _utcnow() -> sa.sql.elements.GenericFunction:
    return sa.func.now()


def upgrade() -> None:
    # communication_events
    op.create_table(
        "communication_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("resource_type", sa.String(32)),
        sa.Column("resource_id", UUID(as_uuid=True)),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("payload", JSONB(), server_default="{}"),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
    )
    op.create_index(
        "ix_comm_events_type_created", "communication_events", ["event_type", "created_at"]
    )

    # delivery_records
    op.create_table(
        "delivery_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "notification_id",
            UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="queued"),
        sa.Column("provider", sa.String(32)),
        sa.Column("provider_message_id", sa.Text()),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("max_attempts", sa.Integer(), server_default="3"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("cost_estimate", sa.Numeric(10, 4)),
        sa.Column("metadata", JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "status IN ('queued','processing','sent','delivered','failed','retrying','cancelled','dead_letter')",
            name="ck_delivery_records_status",
        ),
        sa.CheckConstraint(
            "channel IN ('in_app','email','sms','push','whatsapp')",
            name="ck_delivery_records_channel",
        ),
    )
    op.create_index("ix_delivery_records_channel_status", "delivery_records", ["channel", "status"])

    # comm_templates
    op.create_table(
        "comm_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("code", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("locale", sa.String(8), server_default="en"),
        sa.Column("subject", sa.Text()),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(16), server_default="draft"),
        sa.Column("variables", JSONB(), server_default="[]"),
        sa.Column("category", sa.String(32), server_default="system"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "status IN ('draft','published','archived')",
            name="ck_comm_templates_status",
        ),
        sa.UniqueConstraint("code", "channel", "locale", "version", name="uq_template_version"),
    )

    # public_alerts
    op.create_table(
        "public_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), server_default="info"),
        sa.Column("status", sa.String(16), server_default="draft"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column(
            "geography_id",
            UUID(as_uuid=True),
            sa.ForeignKey("geographies.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column("geojson", JSONB()),
        sa.Column("target_levels", JSONB(), server_default="[]"),
        sa.Column("verified", sa.Boolean(), server_default="false"),
        sa.Column(
            "verified_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "status IN ('draft','review','published','resolved','archived','rejected')",
            name="ck_public_alerts_status",
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','critical','emergency')",
            name="ck_public_alerts_severity",
        ),
    )

    # user_devices
    op.create_table(
        "user_devices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("push_token", sa.Text(), nullable=False),
        sa.Column("device_name", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "platform IN ('web','ios','android')",
            name="ck_user_devices_platform",
        ),
    )

    # comm_campaigns
    op.create_table(
        "comm_campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(32), server_default="community"),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("subject", sa.Text()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience_filter", JSONB(), server_default="{}"),
        sa.Column("estimated_recipients", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(16), server_default="draft"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("sent_count", sa.Integer(), server_default="0"),
        sa.Column("delivered_count", sa.Integer(), server_default="0"),
        sa.Column("failed_count", sa.Integer(), server_default="0"),
        sa.Column("cost_estimate", sa.Numeric(10, 4)),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "status IN ('draft','review','approved','scheduled','sending','paused','completed','cancelled')",
            name="ck_comm_campaigns_status",
        ),
    )

    # comm_analytics
    op.create_table(
        "comm_analytics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), server_default="system"),
        sa.Column("events_created", sa.Integer(), server_default="0"),
        sa.Column("notifications_sent", sa.Integer(), server_default="0"),
        sa.Column("delivered", sa.Integer(), server_default="0"),
        sa.Column("failed", sa.Integer(), server_default="0"),
        sa.Column("read_count", sa.Integer(), server_default="0"),
        sa.Column("suppressed", sa.Integer(), server_default="0"),
        sa.Column("cost", sa.Numeric(10, 4), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.UniqueConstraint("date", "channel", "category", name="uq_comm_analytics_daily"),
    )

    # digest_records
    op.create_table(
        "digest_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("digest_type", sa.String(16), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notification_count", sa.Integer(), server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("channel", sa.String(16), server_default="email"),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "digest_type IN ('daily','weekly')",
            name="ck_digest_records_type",
        ),
        sa.UniqueConstraint("user_id", "digest_type", "period_start", name="uq_digest_user_period"),
    )


def downgrade() -> None:
    op.drop_table("digest_records")
    op.drop_table("comm_analytics")
    op.drop_table("comm_campaigns")
    op.drop_table("user_devices")
    op.drop_table("public_alerts")
    op.drop_table("comm_templates")
    op.drop_table("delivery_records")
    op.drop_table("communication_events")
