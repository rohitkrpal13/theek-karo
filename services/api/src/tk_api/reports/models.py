"""Report lifecycle entities (DATABASE.md §3.3, §5).

The location column is the dialect-swapped :class:`~tk_api.core.geo.LocationPoint`
(ADR-027): PostGIS POINT(4326) on Postgres, GeoJSON string on SQLite. FKs to
``gis_boundaries`` exist only in migrations (unit-test SQLite schema is
non-spatial, mirroring ``campaign_scopes``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base
from tk_api.core.geo import LocationPoint

TIERS = (
    "OFFICIAL_DATA",
    "CITIZEN_REPORT",
    "COMMUNITY_VERIFIED",
    "AI_ANALYSIS",
    "UNVERIFIED_INFORMATION",
)


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_no: Mapped[str] = mapped_column(Text, unique=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="RESTRICT"), index=True
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="RESTRICT"), index=True
    )
    issue_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("issue_types.id", ondelete="RESTRICT"), index=True
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    __table_args__ = (
        # Feed hot paths (Step 9): public feeds sort by recency; geography tab
        # filters by boundary first. Cursor pagination keys off created_at.
        Index("ix_reports_feed", "visibility", "deleted_at", "created_at"),
        Index("ix_reports_boundary_created", "boundary_id", "created_at"),
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[dict[str, Any]] = mapped_column(LocationPoint())
    location_accuracy_m: Mapped[Decimal] = mapped_column(Numeric)
    address_hint: Mapped[str | None] = mapped_column(Text)
    boundary_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    severity: Mapped[str | None] = mapped_column(String(16))  # low, medium, high, critical
    visibility: Mapped[str] = mapped_column(
        String(16), default="public"
    )  # public, private, unlisted
    source: Mapped[str | None] = mapped_column(String(32))
    coordinate_source: Mapped[str | None] = mapped_column(String(32))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str | None] = mapped_column(Text)
    info_class: Mapped[str] = mapped_column(String(32), default="CITIZEN_REPORT")
    trust_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0"))
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="RESTRICT"), index=True
    )
    merged_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    fields: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportEvidence(Base):
    __tablename__ = "report_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # image, video, document, url, structured
    media_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_objects.id", ondelete="SET NULL"), index=True
    )
    url: Mapped[str | None] = mapped_column(Text)
    structured: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    moderation_status: Mapped[str] = mapped_column(String(16), default="pending")
    verification_status: Mapped[str] = mapped_column(String(16), default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReportDuplicate(Base):
    __tablename__ = "report_duplicates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    candidate_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    confidence: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(16), default="possible"
    )  # possible, confirmed, rejected
    suggested_by: Mapped[str] = mapped_column(String(16), default="ai")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReportString(Base):
    __tablename__ = "report_strings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    info_class: Mapped[str] = mapped_column(String(32), default="COMMUNITY_VERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("report_id", "locale"),)


class ReportStatusHistory(Base):
    __tablename__ = "report_status_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReportVerification(Base):
    __tablename__ = "report_verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    verifier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(16))  # confirm | refute
    evidence: Mapped[str | None] = mapped_column(Text)
    location_independent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReportCollaboration(Base):
    __tablename__ = "report_collaborations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReportFollower(Base):
    __tablename__ = "report_followers"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    notify_level: Mapped[str] = mapped_column(String(32), default="all")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReportComment(Base):
    """Comment on a report; replies are one level deep (parent_id), Phase 13."""

    __tablename__ = "report_comments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("report_comments.id", ondelete="RESTRICT"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    is_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    removal_reason: Mapped[str | None] = mapped_column(Text)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
