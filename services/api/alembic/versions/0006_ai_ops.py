"""AI, notifications, and measurement tables

Revision ID: 0006_ai_ops
Revises: 0005_reports_media
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_ai_ops"
down_revision: str | None = "0005_reports_media"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_kind", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("payload_in", postgresql.JSONB(), nullable=False),
        sa.Column("payload_out", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_runs_task_kind"), "ai_runs", ["task_kind"])

    op.create_table(
        "ai_annotations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("info_class", sa.String(length=32), nullable=False, server_default="AI_ANALYSIS"),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="RESTRICT"),
        # the DB itself prevents AI from self-declaring verified status
        sa.CheckConstraint("info_class = 'AI_ANALYSIS'", name="ck_ai_annotations_info_class"),
    )
    op.create_index(op.f("ix_ai_annotations_report_id"), "ai_annotations", ["report_id"])

    op.create_table(
        "ai_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("annotation_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["annotation_id"], ["ai_annotations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_ai_citations_annotation_id"), "ai_citations", ["annotation_id"])

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("subject_key", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event", "channel", "locale"),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
    )

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("event_group", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quiet_hours", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "channel", "event_group"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "notification_queue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_notification_queue_status_due"),
        "notification_queue",
        ["status", "next_attempt_at"],
    )
    op.create_index(op.f("ix_notification_queue_user_id"), "notification_queue", ["user_id"])

    op.create_table(
        "measurement_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dimension", postgresql.JSONB(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_measurement_snapshots_generated_at"), "measurement_snapshots", ["generated_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_measurement_snapshots_generated_at"), table_name="measurement_snapshots")
    op.drop_table("measurement_snapshots")
    op.drop_index(op.f("ix_notification_queue_user_id"), table_name="notification_queue")
    op.drop_index(op.f("ix_notification_queue_status_due"), table_name="notification_queue")
    op.drop_table("notification_queue")
    op.drop_table("notification_preferences")
    op.drop_table("notification_templates")
    op.drop_index(op.f("ix_ai_citations_annotation_id"), table_name="ai_citations")
    op.drop_table("ai_citations")
    op.drop_index(op.f("ix_ai_annotations_report_id"), table_name="ai_annotations")
    op.drop_table("ai_annotations")
    op.drop_index(op.f("ix_ai_runs_task_kind"), table_name="ai_runs")
    op.drop_table("ai_runs")
