"""Government dataset entities with time-travel (PRD §25): versioned records
answer "what did the data say at that point in time?"."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GovDataset(Base):
    __tablename__ = "gov_datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT")
    )
    publisher: Mapped[str] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active")
    url: Mapped[str | None] = mapped_column(Text)
    # Phase 19: explicit adapter mapping — registry key from
    # ``govdata.connectors.CONNECTOR_REGISTRY`` (e.g. ``udise_plus_school``);
    # ``generic_gov`` for legacy rows. Reliable connector lookup instead of
    # deriving the code from the dataset name.
    connector_code: Mapped[str | None] = mapped_column(String(64), default="generic_gov")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GovImportJob(Base):
    __tablename__ = "gov_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gov_datasets.id", ondelete="RESTRICT"), index=True
    )
    run_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_total: Mapped[int | None] = mapped_column(Integer)
    rows_imported: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    # Phase 19 change-detection counters + schema-drift flag + rollback
    # bookkeeping (affected institution ids).
    rows_added: Mapped[int | None] = mapped_column(Integer)
    rows_removed: Mapped[int | None] = mapped_column(Integer)
    rows_modified: Mapped[int | None] = mapped_column(Integer)
    rows_unchanged: Mapped[int | None] = mapped_column(Integer)
    rows_rejected: Mapped[int | None] = mapped_column(Integer)
    schema_drift_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))


class GovRawPayload(Base):
    __tablename__ = "gov_raw_payloads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gov_datasets.id", ondelete="RESTRICT"), index=True
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gov_import_jobs.id", ondelete="SET NULL")
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(64), default="application/json")
    byte_size: Mapped[int | None] = mapped_column(Integer)
    raw_content: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    status: Mapped[str] = mapped_column(String(32), default="stored")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GovDatasetRecord(Base):
    __tablename__ = "gov_dataset_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gov_datasets.id", ondelete="RESTRICT")
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gov_import_jobs.id", ondelete="SET NULL")
    )
    external_key: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    validation_status: Mapped[str] = mapped_column(String(32), default="validated")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EntityMatchReview(Base):
    __tablename__ = "entity_match_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gov_datasets.id", ondelete="RESTRICT"), index=True
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gov_import_jobs.id", ondelete="SET NULL")
    )
    external_key: Mapped[str] = mapped_column(Text)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    candidate_institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), index=True
    )
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.5"))
    match_status: Mapped[str] = mapped_column(String(32), default="POSSIBLE_MATCH")
    match_signals: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    review_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "match_status IN ('MATCHED', 'POSSIBLE_MATCH', 'CONFLICT', 'UNMATCHED')",
            name="ck_entity_matches_status",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'confirmed', 'rejected', 'created_new')",
            name="ck_entity_matches_review",
        ),
    )


class InstitutionDiscrepancy(Base):
    __tablename__ = "institution_discrepancies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    resource_key: Mapped[str] = mapped_column(String(64))
    discrepancy_state: Mapped[str] = mapped_column(
        String(32), default="NO_DISCREPANCY_DETECTED", index=True
    )
    official_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    citizen_summary: Mapped[str | None] = mapped_column(Text)
    ai_finding: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.5"))
    rule_code: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="active")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "discrepancy_state IN ('NO_DISCREPANCY_DETECTED', 'POSSIBLE_DISCREPANCY', "
            "'CONFLICTING_DATA', 'OUTDATED_OFFICIAL_DATA', 'INSUFFICIENT_DATA', "
            "'UNDER_REVIEW', 'RESOLVED')",
            name="ck_discrepancies_state",
        ),
    )
