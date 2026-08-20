"""Analytics events + daily aggregates (PRD §26, ARCHITECTURE §15).

Transactional tables are never queried for wall-clock analytics: events are
collected and rollups are materialized daily; measurement_snapshots (Cycle-1)
keep the metric contract.

Revision ID: 0019_analytics
Revises: 0018_ml_ai_rag_gov
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019_analytics"
down_revision: str | None = "0018_ml_ai_rag_gov"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("content_type", sa.String(length=32), nullable=True),
        sa.Column("content_id", sa.Uuid(), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_analytics_events_kind_time"), "analytics_events", ["event_kind", "occurred_at"]
    )
    op.create_index(
        op.f("ix_analytics_events_geo_time"), "analytics_events", ["geography_id", "occurred_at"]
    )
    op.create_table(
        "analytics_daily",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bucket_date", sa.Date(), nullable=False),
        sa.Column("dimension_kind", sa.String(length=32), nullable=False),
        sa.Column("dimension_id", sa.Uuid(), nullable=True),
        sa.Column("metric_kind", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bucket_date",
            "dimension_kind",
            "dimension_id",
            "metric_kind",
            name="uq_analytics_daily_cell",
        ),
    )
    op.create_index(
        op.f("ix_analytics_daily_cell"),
        "analytics_daily",
        ["bucket_date", "dimension_kind", "dimension_id"],
    )
    op.create_index(op.f("ix_analytics_daily_metric"), "analytics_daily", ["metric_kind"])

    op.create_check_constraint(
        "ck_analytics_daily_dimension",
        "analytics_daily",
        "dimension_kind IN ('country','state','district','block','ward','village',"
        "'institution','category')",
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analytics_daily_metric"), table_name="analytics_daily")
    op.drop_index(op.f("ix_analytics_daily_cell"), table_name="analytics_daily")
    op.drop_table("analytics_daily")
    op.drop_index(op.f("ix_analytics_events_geo_time"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_kind_time"), table_name="analytics_events")
    op.drop_table("analytics_events")
