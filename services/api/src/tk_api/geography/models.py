"""Geography registry entities (PRD §3).

Models with geometry (`Geography`) are unregistered from the unit-test schema
(ADR-027 discipline): they are only exercised on Postgres by integration
tests. Type + translation entities are plain and registered.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GeographyType(Base):
    __tablename__ = "geography_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name_key: Mapped[str] = mapped_column(Text)
    parent_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geography_types.id", ondelete="RESTRICT")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    supports_geometry: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GeographyTranslation(Base):
    __tablename__ = "geography_translations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    geography_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("geographies.id", ondelete="CASCADE")
    )
    locale: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(Text)
    transliteration: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="community")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Geography(Base):
    """PG-only: the geometry columns exist in DDL but are deliberately not
    mapped (raw SQL + PostGIS in the integration tests); NOT registered in the
    unit-test schema (ADR-027 discipline)."""

    __tablename__ = "geographies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("geography_types.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="RESTRICT")
    )
    country_code: Mapped[str] = mapped_column(String(4))
    official_identifier: Mapped[str | None] = mapped_column(Text)
    alternate_names: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("external_sources.id"))
    source_identifier: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (CheckConstraint("id <> parent_id", name="ck_geographies_not_self_parent"),)
