"""Phase 23 — Data Trust, Provenance, Verification & Open Data entities.

Establishes the unified trust layer across the Theek Karo ecosystem.
Every important piece of information answers: WHO provided it, WHEN,
WHERE, WHAT evidence supports it, HAS it been verified, WHO verified it,
WHEN was it verified, WHAT is the source, and WHAT are the limitations.

Tables: ``evidence_registry``, ``verification_records``, ``data_quality_results``,
``data_conflicts``, ``dispute_records``, ``data_change_history``,
``data_publication_snapshots``, ``metric_definitions``,
``data_quarantine_records``, ``source_health_snapshots``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Evidence Registry (spec §14)
# ---------------------------------------------------------------------------

EVIDENCE_TYPES = (
    "image",
    "video",
    "document",
    "audio",
    "text",
    "official_record",
    "external_reference",
)
EVIDENCE_STATES = (
    "SUBMITTED",
    "PROCESSING",
    "UNDER_REVIEW",
    "VERIFIED",
    "PARTIALLY_VERIFIED",
    "REJECTED",
    "EXPIRED",
    "SUPERSEDED",
)


class EvidenceRecord(Base):
    """Central evidence registry — every uploaded/harvested piece of evidence
    is registered here with full metadata, integrity hash, and provenance."""

    __tablename__ = "evidence_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    evidence_type: Mapped[str] = mapped_column(String(32))  # image, video, etc.
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32))  # CITIZEN, OFFICIAL, etc.
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), index=True
    )
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Link to the media pipeline (existing media_objects table)
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_objects.id", ondelete="SET NULL"), index=True
    )
    # Link to relevant domain entity
    entity_type: Mapped[str | None] = mapped_column(String(64))  # report, case, initiative, etc.
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    # Integrity
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    # Location if available
    location: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    # Lifecycle
    status: Mapped[str] = mapped_column(String(24), default="SUBMITTED")
    # Verification summary
    verification_status: Mapped[str] = mapped_column(String(24), default="NOT_REVIEWED")
    verification_count: Mapped[int] = mapped_column(Integer, default=0)
    # Multilingual support: preserve original + translation
    language: Mapped[str | None] = mapped_column(String(16))
    original_text: Mapped[str | None] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text)
    translation_language: Mapped[str | None] = mapped_column(String(16))
    # Hash chain for tamper evidence
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    chain_hash: Mapped[str | None] = mapped_column(String(64))
    # Metadata
    meta: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('image','video','document','audio','text',"
            "'official_record','external_reference')",
            name="ck_evidence_registry_type",
        ),
        CheckConstraint(
            "status IN ('SUBMITTED','PROCESSING','UNDER_REVIEW','VERIFIED',"
            "'PARTIALLY_VERIFIED','REJECTED','EXPIRED','SUPERSEDED')",
            name="ck_evidence_registry_status",
        ),
        CheckConstraint(
            "verification_status IN ('NOT_REVIEWED','REVIEWED','VERIFIED',"
            "'PARTIALLY_VERIFIED','DISPUTED','REJECTED')",
            name="ck_evidence_registry_verification",
        ),
        CheckConstraint(
            "source_type IN ('CITIZEN','COMMUNITY','ORGANIZATION','INSTITUTION',"
            "'OFFICIAL_GOVERNMENT','PUBLIC_DATASET','OPEN_DATA','PARTNER',"
            "'INTERNAL','AI_GENERATED','DERIVED_ANALYTICS')",
            name="ck_evidence_registry_source_type",
        ),
    )


# ---------------------------------------------------------------------------
# Verification Records (spec §17-§18)
# ---------------------------------------------------------------------------

VERIFICATION_METHODS = (
    "human_review",
    "official_source_confirmation",
    "cross_source_consistency",
    "location_validation",
    "timestamp_validation",
    "document_verification",
    "duplicate_analysis",
    "structured_data_validation",
    "ai_assisted",
)

VERIFICATION_DECISIONS = (
    "NOT_REVIEWED",
    "REVIEWED",
    "VERIFIED",
    "PARTIALLY_VERIFIED",
    "DISPUTED",
    "REJECTED",
)


class VerificationRecord(Base):
    """Append-only verification record. Every verification action is recorded
    with reviewer, timestamp, method, evidence, decision, and explanation."""

    __tablename__ = "verification_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # What is being verified
    entity_type: Mapped[str] = mapped_column(String(64))  # evidence, report, dataset, etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    # Who verified
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewer_type: Mapped[str] = mapped_column(String(32), default="human")  # human, ai_assisted
    # What decision
    decision: Mapped[str] = mapped_column(String(24))
    # How
    method: Mapped[str] = mapped_column(String(64))
    # Evidence supporting the verification
    evidence_refs: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)  # ids of evidence used
    # Explanation
    explanation: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)  # 0.0-1.0 for AI-assisted
    # AI provenance (when AI assisted)
    ai_model: Mapped[str | None] = mapped_column(String(64))
    ai_model_version: Mapped[str | None] = mapped_column(String(32))
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    # Chain
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    chain_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('NOT_REVIEWED','REVIEWED','VERIFIED','PARTIALLY_VERIFIED',"
            "'DISPUTED','REJECTED')",
            name="ck_verification_records_decision",
        ),
        CheckConstraint(
            "method IN ('human_review','official_source_confirmation',"
            "'cross_source_consistency','location_validation','timestamp_validation',"
            "'document_verification','duplicate_analysis','structured_data_validation',"
            "'ai_assisted')",
            name="ck_verification_records_method",
        ),
        CheckConstraint(
            "reviewer_type IN ('human', 'ai_assisted')",
            name="ck_verification_records_reviewer_type",
        ),
        Index("ix_verification_entity", "entity_type", "entity_id"),
    )


# ---------------------------------------------------------------------------
# Data Quality Results (spec §26-§28)
# ---------------------------------------------------------------------------

QUALITY_STATES = (
    "VALID",
    "PARTIALLY_VALID",
    "INVALID",
    "INCOMPLETE",
    "STALE",
    "CONFLICTING",
    "DUPLICATE",
    "UNVERIFIED",
)

QUALITY_DIMENSIONS = (
    "completeness",
    "validity",
    "consistency",
    "uniqueness",
    "freshness",
    "coverage",
    "referential_integrity",
)


class DataQualityResult(Base):
    """Data quality check result for a specific entity or dataset record.
    Tracks multiple quality dimensions independently."""

    __tablename__ = "data_quality_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64))  # dataset, dataset_record, evidence, etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), index=True
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gov_datasets.id", ondelete="SET NULL"), index=True
    )
    # Quality dimensions
    dimension: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)  # 0.0-1.0
    status: Mapped[str] = mapped_column(String(24))
    details: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    missing_fields: Mapped[list[Any] | None] = mapped_column(_jsonb(), nullable=True)
    invalid_fields: Mapped[list[Any] | None] = mapped_column(_jsonb(), nullable=True)
    # Overall composite
    overall_status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")
    # AI-assisted analysis
    ai_assisted: Mapped[bool] = mapped_column(default=False)
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "dimension IN ('completeness','validity','consistency','uniqueness',"
            "'freshness','coverage','referential_integrity')",
            name="ck_data_quality_dimension",
        ),
        CheckConstraint(
            "status IN ('VALID','PARTIALLY_VALID','INVALID','INCOMPLETE',"
            "'STALE','CONFLICTING','DUPLICATE','UNVERIFIED')",
            name="ck_data_quality_status",
        ),
        CheckConstraint(
            "overall_status IN ('VALID','PARTIALLY_VALID','INVALID','INCOMPLETE',"
            "'STALE','CONFLICTING','DUPLICATE','UNVERIFIED')",
            name="ck_data_quality_overall",
        ),
    )


# ---------------------------------------------------------------------------
# Data Conflicts (spec §29-§30)
# ---------------------------------------------------------------------------

CONFLICT_STATES = (
    "DETECTED",
    "UNDER_REVIEW",
    "RESOLVED_SELECT_SOURCE",
    "RESOLVED_MERGED",
    "RESOLVED_UNRESOLVED",
    "DISMISSED",
)


class DataConflict(Base):
    """Tracks conflicts between data sources for the same entity.
    Never silently resolves — always shows both values."""

    __tablename__ = "data_conflicts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    field_name: Mapped[str] = mapped_column(String(128))
    # Source A
    source_a_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    source_a_value: Mapped[Any] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    source_a_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Source B
    source_b_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    source_b_value: Mapped[Any] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    source_b_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Resolution
    status: Mapped[str] = mapped_column(String(32), default="DETECTED")
    resolved_value: Mapped[Any | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    # Metadata
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    meta: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('DETECTED','UNDER_REVIEW','RESOLVED_SELECT_SOURCE',"
            "'RESOLVED_MERGED','RESOLVED_UNRESOLVED','DISMISSED')",
            name="ck_data_conflicts_status",
        ),
        CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_data_conflicts_severity",
        ),
    )


# ---------------------------------------------------------------------------
# Dispute Records (spec §67-§69)
# ---------------------------------------------------------------------------

DISPUTE_STATES = ("OPEN", "UNDER_REVIEW", "RESOLVED", "REJECTED", "WITHDRAWN")


class DisputeRecord(Base):
    """A formal dispute against a report, evidence, dataset, institution
    information, or public metric. A dispute does NOT automatically remove data."""

    __tablename__ = "dispute_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dispute_target_type: Mapped[str] = mapped_column(String(32))  # report, evidence, dataset, etc.
    dispute_target_id: Mapped[str] = mapped_column(Text)
    filed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    # Review
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decision: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Banner: show "Information currently under review" on public records
    public_banner: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','UNDER_REVIEW','RESOLVED','REJECTED','WITHDRAWN')",
            name="ck_dispute_records_status",
        ),
        CheckConstraint(
            "dispute_target_type IN ('report','evidence','dataset','institution',"
            "'metric','public_data')",
            name="ck_dispute_records_target",
        ),
    )


# ---------------------------------------------------------------------------
# Data Change History (spec §56)
# ---------------------------------------------------------------------------


class DataChangeHistory(Base):
    """Tracks important data changes with old/new values, source, and reason.
    Append-only — historical records are never destroyed."""

    __tablename__ = "data_change_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    field_name: Mapped[str] = mapped_column(String(128))
    old_value: Mapped[Any | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    new_value: Mapped[Any | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    change_source: Mapped[str] = mapped_column(String(32))  # user, system, import, ai
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reason: Mapped[str | None] = mapped_column(Text)
    # Tamper-evident chain
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    chain_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "change_source IN ('user','system','import','ai','correction','dispute')",
            name="ck_change_history_source",
        ),
        Index("ix_change_history_entity", "entity_type", "entity_id"),
    )


# ---------------------------------------------------------------------------
# Data Publication Snapshots (spec §10, §83-§84)
# ---------------------------------------------------------------------------


class DataPublicationSnapshot(Base):
    """Immutable snapshot of dataset quality metrics at publication time.
    Enables reproducible analytics and historical comparison."""

    __tablename__ = "data_publication_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gov_datasets.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    # Quality dimensions at snapshot time
    completeness_pct: Mapped[float | None] = mapped_column(Float)
    freshness_pct: Mapped[float | None] = mapped_column(Float)
    consistency_pct: Mapped[float | None] = mapped_column(Float)
    coverage_pct: Mapped[float | None] = mapped_column(Float)
    verification_pct: Mapped[float | None] = mapped_column(Float)
    conflict_count: Mapped[int | None] = mapped_column(Integer)
    duplicate_count: Mapped[int | None] = mapped_column(Integer)
    record_count: Mapped[int | None] = mapped_column(Integer)
    # Methodology
    methodology: Mapped[str | None] = mapped_column(Text)
    # Snapshot reference (for object storage)
    snapshot_key: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_pub_snapshots_dataset", "dataset_id", "created_at"),)


# ---------------------------------------------------------------------------
# Metric Definitions (spec §61-§62)
# ---------------------------------------------------------------------------


class MetricDefinition(Base):
    """Centralized metric catalog with versioning. Ensures dashboards
    never use ambiguous metric names."""

    __tablename__ = "metric_definitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    metric_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    name_hi: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    formula: Mapped[str] = mapped_column(Text)
    definition: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(16), default="1.0")
    # When a formula changes, historical reports retain the old version
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # Access
    visibility: Mapped[str] = mapped_column(String(16), default="PUBLIC")
    required_role: Mapped[str | None] = mapped_column(String(32))
    # Coverage & limitations
    coverage: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived', 'deprecated')",
            name="ck_metric_definitions_status",
        ),
        CheckConstraint(
            "visibility IN ('PUBLIC', 'COMMUNITY', 'DEPARTMENT', 'ADMIN', 'RESTRICTED')",
            name="ck_metric_definitions_visibility",
        ),
    )


# ---------------------------------------------------------------------------
# Data Quarantine (spec §88)
# ---------------------------------------------------------------------------

QUARANTINE_STATES = ("RECEIVED", "VALIDATING", "QUARANTINED", "APPROVED", "REJECTED")


class DataQuarantineRecord(Base):
    """Invalid or suspicious imports go into quarantine.
    Never published until reviewed and approved."""

    __tablename__ = "data_quarantine_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gov_datasets.id", ondelete="SET NULL"), index=True
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gov_import_jobs.id", ondelete="SET NULL")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    external_key: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    rejection_reasons: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    status: Mapped[str] = mapped_column(String(16), default="RECEIVED")
    # Review
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('RECEIVED','VALIDATING','QUARANTINED','APPROVED','REJECTED')",
            name="ck_quarantine_status",
        ),
    )


# ---------------------------------------------------------------------------
# Source Health Snapshots (spec §34, §85)
# ---------------------------------------------------------------------------


class SourceHealthSnapshot(Base):
    """Periodic health snapshot for data sources — tracks sync status,
    record counts, and error rates over time."""

    __tablename__ = "source_health_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))  # HEALTHY, DEGRADED, FAILED
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    records_accepted: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    records_duplicated: Mapped[int] = mapped_column(Integer, default=0)
    records_conflicting: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)
    schema_changed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('HEALTHY', 'DEGRADED', 'FAILED')",
            name="ck_source_health_status",
        ),
        Index("ix_source_health_source_time", "source_id", "created_at"),
    )
