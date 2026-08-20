"""Human review queue for sensitive AI decisions (ADR-018)

Revision ID: 0007_ai_reviews
Revises: 0006_ai_ops
Create Date: 2026-08-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_ai_reviews"
down_revision: str | None = "0006_ai_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),  # duplicate_merge | ...
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("annotation_id", sa.Uuid(), nullable=True),
        sa.Column("suggested_report_id", sa.Uuid(), nullable=True),
        sa.Column("similarity", sa.Numeric(4, 3), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_ai_reviews_status"
        ),
        sa.ForeignKeyConstraint(["annotation_id"], ["ai_annotations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["suggested_report_id"], ["reports.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_ai_reviews_status_created"), "ai_reviews", ["status", "created_at"])
    op.create_index(op.f("ix_ai_reviews_report_id"), "ai_reviews", ["report_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_reviews_report_id"), table_name="ai_reviews")
    op.drop_index(op.f("ix_ai_reviews_status_created"), table_name="ai_reviews")
    op.drop_table("ai_reviews")
