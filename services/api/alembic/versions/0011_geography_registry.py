"""Geography registry: configurable hierarchy (PRD §3, ARCHITECTURE §6).

Cycle-1 fixed-kind `gis_boundaries` remains the geometry implementation for
ingested boundaries; the registry becomes the general source of truth going
forward. Kinds are data (geography_types), relationships are rows
(geographies.parent_id) — no level names are hard-coded.

Revision ID: 0011_geography_registry
Revises: 0010_identity_expansion
Create Date: 2026-08-16

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_geography_registry"
down_revision: str | None = "0010_identity_expansion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GEO_TYPES = [
    ("country", None),
    ("state_ut", None),
    ("division", None),
    ("district", None),
    ("subdivision", None),
    ("block", None),
    ("panchayat", None),
    ("municipality", None),
    ("ward", None),
    ("village", None),
    ("locality", None),
    ("institution", None),
]


def upgrade() -> None:
    op.create_table(
        "geography_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("parent_type_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "supports_geometry", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.ForeignKeyConstraint(["parent_type_id"], ["geography_types.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "geographies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("country_code", sa.String(length=4), nullable=False),
        sa.Column("official_identifier", sa.Text(), nullable=True),
        sa.Column("alternate_names", postgresql.JSONB(), nullable=True),
        sa.Column("geom", Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("centroid", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_identifier", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_id", "normalized_name", "country_code"),
        sa.ForeignKeyConstraint(["parent_id"], ["geographies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["geography_types.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("id <> parent_id", name="ck_geographies_not_self_parent"),
    )
    op.create_index(op.f("ix_geographies_parent"), "geographies", ["parent_id"])
    op.create_index(op.f("ix_geographies_type_name"), "geographies", ["type_id", "name"])
    op.create_index(op.f("ix_geographies_normalized"), "geographies", ["normalized_name"])
    op.create_table(
        "geography_translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("geography_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("transliteration", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="community"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("geography_id", "locale"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
    )

    op.bulk_insert(
        sa.table(
            "geography_types",
            sa.column("id", sa.Uuid()),
            sa.column("code", sa.String()),
            sa.column("name_key", sa.Text()),
            sa.column("parent_type_id", sa.Uuid()),
            sa.column("sort_order", sa.Integer()),
            sa.column("supports_geometry", sa.Boolean()),
            sa.column("is_active", sa.Boolean()),
            sa.column("created_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "name_key": f"geography.type.{code}",
                "parent_type_id": None,
                "sort_order": i,
                "supports_geometry": True,
                "is_active": True,
                "created_at": datetime.now(UTC),
            }
            for i, (code, _parent) in enumerate(_GEO_TYPES)
        ],
    )


def downgrade() -> None:
    op.drop_table("geography_translations")
    op.drop_index(op.f("ix_geographies_normalized"), table_name="geographies")
    op.drop_index(op.f("ix_geographies_type_name"), table_name="geographies")
    op.drop_index(op.f("ix_geographies_parent"), table_name="geographies")
    op.drop_table("geographies")
    op.drop_table("geography_types")
