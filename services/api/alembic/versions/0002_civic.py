"""civic configuration tables: categories, campaigns

Revision ID: 0002_civic
Revises: 0001_auth
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_civic"
down_revision: str | None = "0001_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False),
        sa.Column("form_schema", postgresql.JSONB(), nullable=False),
        sa.Column("verification_policy", postgresql.JSONB(), nullable=False),
        sa.Column("attachment_rules", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("default_locale_keys", postgresql.JSONB(), nullable=False),
        sa.Column("form_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_categories_slug"), "categories", ["slug"], unique=True)
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title_key", sa.Text(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_campaigns_category_id"), "campaigns", ["category_id"])
    op.create_index(op.f("ix_campaigns_slug"), "campaigns", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_campaigns_slug"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_category_id"), table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_index(op.f("ix_categories_slug"), table_name="categories")
    op.drop_table("categories")
