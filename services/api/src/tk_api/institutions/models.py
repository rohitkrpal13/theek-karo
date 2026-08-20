"""Institutions domain (PRD §5): types, flexible attributes, translations.
Geometry-bearing `Institution` is unmapped-by-geometry (PostGIS via raw SQL in
integration tests) and unregistered from the unit schema (ADR-027).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class InstitutionType(Base):
    __tablename__ = "institution_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name_key: Mapped[str] = mapped_column(Text)
    attribute_schema: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class InstitutionAttributeDefinition(Base):
    __tablename__ = "institution_attribute_definitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institution_types.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(64))
    value_type: Mapped[str] = mapped_column(String(16))
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    unit: Mapped[str | None] = mapped_column(String(16))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class InstitutionAttributeValue(Base):
    __tablename__ = "institution_attribute_values"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE")
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institution_attribute_definitions.id", ondelete="RESTRICT")
    )
    string_value: Mapped[str | None] = mapped_column(Text)
    integer_value: Mapped[int | None] = mapped_column(BigInteger)
    decimal_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    date_value: Mapped[date | None] = mapped_column(Date)
    enum_value: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("external_sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class InstitutionTranslation(Base):
    __tablename__ = "institution_translations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE")
    )
    locale: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Institution(Base):
    """PG-only (geometry in DDL); unmapped geometry columns (raw SQL in tests)."""

    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institution_types.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text, index=True)
    official_identifier: Mapped[str | None] = mapped_column(Text, unique=True)
    address: Mapped[str | None] = mapped_column(Text)
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="RESTRICT"), index=True
    )
    contact_phone: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    management_type: Mapped[str | None] = mapped_column(String(32))
    operational_status: Mapped[str] = mapped_column(String(32), default="active")
    verification_state: Mapped[str] = mapped_column(String(32), default="unverified")
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="RESTRICT"), index=True
    )
    source_identifier: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "operational_status IN ('active', 'inactive', 'closed', 'under_construction')",
            name="ck_institutions_operational_status",
        ),
    )
