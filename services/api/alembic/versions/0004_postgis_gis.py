"""PostGIS foundation and GIS boundary tables

Revision ID: 0004_postgis_gis
Revises: 0003_provenance_i18n
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_postgis_gis"
down_revision: str | None = "0003_provenance_i18n"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "gis_boundary_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "gis_boundaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("boundary_kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_local", postgresql.JSONB(), nullable=True),
        sa.Column(
            "geom",
            Geometry(geometry_type="MULTIPOLYGON", srid=4326),
            nullable=False,
        ),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["gis_boundaries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["gis_boundary_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "boundary_kind IN ('ward', 'panchayat', 'block', 'district', 'state', 'constituency')",
            name="ck_gis_boundaries_kind",
        ),
    )
    op.create_index(op.f("ix_gis_boundaries_parent_id"), "gis_boundaries", ["parent_id"])
    op.create_index(
        op.f("ix_gis_boundaries_kind_name"), "gis_boundaries", ["boundary_kind", "name"]
    )
    op.create_table(
        "gis_places",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_local", postgresql.JSONB(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("boundary_id", sa.Uuid(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["boundary_id"], ["gis_boundaries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["external_sources.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_gis_places_boundary_id"), "gis_places", ["boundary_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_gis_places_boundary_id"), table_name="gis_places")
    op.drop_table("gis_places")
    op.drop_index(op.f("ix_gis_boundaries_kind_name"), table_name="gis_boundaries")
    op.drop_index(op.f("ix_gis_boundaries_parent_id"), table_name="gis_boundaries")
    op.drop_table("gis_boundaries")
    op.drop_table("gis_boundary_versions")
