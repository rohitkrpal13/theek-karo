"""Phase 30 — Social broadcasts: durable record of civic bot amplifications.

Revision ID: 0042
Revises: 0041
Create Date: 2026-10-21
"""

import sqlalchemy as sa

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_broadcasts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "requested_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("network", sa.String(16), nullable=False, server_default="x"),
        sa.Column("tone", sa.String(16), nullable=False, server_default="urgent"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("post_text", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("external_post_id", sa.String(64), nullable=True),
        sa.Column("published_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_social_broadcasts_report_status",
        "social_broadcasts",
        ["report_id", "status"],
    )
    op.create_index(
        "ix_social_broadcasts_status_created",
        "social_broadcasts",
        ["status", "created_at"],
    )
    op.create_index(
        "uq_social_broadcasts_report_idempotency",
        "social_broadcasts",
        ["report_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_social_broadcasts_active_report",
        "social_broadcasts",
        ["report_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'processing', 'published', 'outcome_unknown')"
        ),
        sqlite_where=sa.text("status IN ('queued', 'processing', 'published', 'outcome_unknown')"),
    )


def downgrade() -> None:
    op.drop_index("uq_social_broadcasts_active_report", table_name="social_broadcasts")
    op.drop_index("uq_social_broadcasts_report_idempotency", table_name="social_broadcasts")
    op.drop_index("ix_social_broadcasts_status_created", table_name="social_broadcasts")
    op.drop_index("ix_social_broadcasts_report_status", table_name="social_broadcasts")
    op.drop_table("social_broadcasts")
