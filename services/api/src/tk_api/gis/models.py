"""GIS entities (DATABASE.md §3.5, ADR-006).

These ORM models are intentionally **not** registered in ``tk_api.core.models``:
geometries exist only on Postgres (ADR-026/027), so the SQLite unit-test schema
must not create them. Migrations own the DDL; the ETL inserts geometry via raw
``ST_GeomFromGeoJSON`` and everything spatial is exercised by integration
tests on the compose PostGIS.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

try:
    from geoalchemy2 import Geometry
except ImportError:  # pragma: no cover
    Geometry = None  # type: ignore[assignment, misc]

from tk_api.core.db import Base


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GisBoundaryVersion(Base):
    __tablename__ = "gis_boundary_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(64), unique=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="RESTRICT")
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GisBoundary(Base):
    __tablename__ = "gis_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    boundary_kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(Text)
    name_local: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gis_boundaries.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="RESTRICT")
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gis_boundary_versions.id", ondelete="RESTRICT")
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GisPlace(Base):
    __tablename__ = "gis_places"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    name_local: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    kind: Mapped[str] = mapped_column(String(32))
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326))
    boundary_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gis_boundaries.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
