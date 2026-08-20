"""Phase 5 — Evidence v2: video support, before/after pairs, evidence chain.

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Evidence v2: video columns on media_objects
    op.add_column("media_objects", sa.Column("duration_seconds", sa.BigInteger(), nullable=True))
    op.add_column("media_objects", sa.Column("fps", sa.Integer(), nullable=True))
    op.add_column("media_objects", sa.Column("codec", sa.String(32), nullable=True))

    # Before/after pair support on report_media
    op.add_column("report_media", sa.Column("pair_group", sa.String(64), nullable=True))
    op.add_column("report_media", sa.Column("pair_role", sa.String(16), nullable=True))
    op.add_column(
        "report_media",
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Evidence chain table
    op.create_table(
        "evidence_chains",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            index=True,
        ),
        sa.Column("chain_hash", sa.Text(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Indexes for pair lookups
    op.create_index(
        "ix_report_media_pair",
        "report_media",
        ["report_id", "pair_group"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_report_media_pair", table_name="report_media")
    op.drop_table("evidence_chains")
    op.drop_column("report_media", "captured_at")
    op.drop_column("report_media", "pair_role")
    op.drop_column("report_media", "pair_group")
    op.drop_column("media_objects", "codec")
    op.drop_column("media_objects", "fps")
    op.drop_column("media_objects", "duration_seconds")
