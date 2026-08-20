"""Institutions domain: types, flexible attributes, translations (PRD §5).

Revision ID: 0012_institutions
Revises: 0011_geography_registry
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_institutions"
down_revision: str | None = "0011_geography_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institution_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("attribute_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "institutions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_type_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("official_identifier", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("geometry", Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("management_type", sa.String(length=32), nullable=True),
        sa.Column(
            "operational_status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column(
            "verification_state", sa.String(length=32), nullable=False, server_default="unverified"
        ),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_identifier", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("official_identifier"),
        sa.UniqueConstraint("institution_type_id", "normalized_name"),
        sa.CheckConstraint(
            "operational_status IN ('active', 'inactive', 'closed', 'under_construction')",
            name="ck_institutions_operational_status",
        ),
        sa.CheckConstraint(
            "verification_state IN ('unverified', 'pending', 'official_verified', "
            "'community_verified', 'rejected')",
            name="ck_institutions_verification_state",
        ),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["institution_type_id"], ["institution_types.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_institutions_type"), "institutions", ["institution_type_id"])
    op.create_index(op.f("ix_institutions_geography"), "institutions", ["geography_id"])
    op.create_index(op.f("ix_institutions_normalized"), "institutions", ["normalized_name"])
    op.create_index(op.f("ix_institutions_source"), "institutions", ["source_id"])
    op.create_table(
        "institution_attribute_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_type_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("value_type", sa.String(length=16), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_type_id", "code"),
        sa.ForeignKeyConstraint(
            ["institution_type_id"], ["institution_types.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "value_type IN ('string', 'integer', 'decimal', 'boolean', 'date', 'enum')",
            name="ck_attr_def_value_type",
        ),
    )
    op.create_table(
        "institution_attribute_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("string_value", sa.Text(), nullable=True),
        sa.Column("integer_value", sa.BigInteger(), nullable=True),
        sa.Column("decimal_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("date_value", sa.Date(), nullable=True),
        sa.Column("enum_value", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "definition_id"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["institution_attribute_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"]),
    )
    op.create_table(
        "institution_translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "locale"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    op.drop_table("institution_translations")
    op.drop_table("institution_attribute_values")
    op.drop_table("institution_attribute_definitions")
    op.drop_index(op.f("ix_institutions_source"), table_name="institutions")
    op.drop_index(op.f("ix_institutions_normalized"), table_name="institutions")
    op.drop_index(op.f("ix_institutions_geography"), table_name="institutions")
    op.drop_index(op.f("ix_institutions_type"), table_name="institutions")
    op.drop_table("institutions")
    op.drop_table("institution_types")
