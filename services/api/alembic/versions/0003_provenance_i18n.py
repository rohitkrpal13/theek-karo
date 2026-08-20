"""provenance and i18n tables (external_sources, provenance_records, locales, translations)

Revision ID: 0003_provenance_i18n
Revises: 0002_civic
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_provenance_i18n"
down_revision: str | None = "0002_civic"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# I18N.md: launch locales hi/en first; follow-ons in priority order.
_INITIAL_LOCALES = ["en", "hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa"]


def upgrade() -> None:
    op.create_table(
        "external_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "retrieval_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Text(), nullable=True),
        sa.Column("geo_applicability", postgresql.JSONB(), nullable=False),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("confidence_base", sa.Numeric(4, 3), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "provenance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_meta", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_provenance_records_entity"), "provenance_records", ["entity_type", "entity_id"]
    )
    op.create_table(
        "locales",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.bulk_insert(
        sa.table("locales", sa.column("code", sa.String())), [{"code": c} for c in _INITIAL_LOCALES]
    )
    op.create_table(
        "translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("locale", "key"),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "review_status IN ('draft', 'reviewed')", name="ck_translations_review_status"
        ),
    )
    op.create_index(
        op.f("ix_translations_locale_key"), "translations", ["locale", "key"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_translations_locale_key"), table_name="translations")
    op.drop_table("translations")
    op.drop_table("locales")
    op.drop_index(op.f("ix_provenance_records_entity"), table_name="provenance_records")
    op.drop_table("provenance_records")
    op.drop_table("external_sources")
