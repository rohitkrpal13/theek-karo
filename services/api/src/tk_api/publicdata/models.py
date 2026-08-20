"""Phase 15 public data, open data, research and transparency entities.

The public-data layer exposes carefully scoped, provenance-tagged views over the
platform's own (public) data plus the curated catalog of imported government
datasets. Key invariants (ADR-052):

- public datasets are *descriptions* of data (catalog rows) plus version +
  lineage provenance — never raw records copied into this layer;
- exports apply public-safe field allowlists and generalized coordinates — no
  PII, no exact personal locations, no private media;
- correction requests never mutate official datasets — they are reviewable
  suggestions recorded in ``data_correction_requests``;
- API keys store only a sha256 of the secret (the plaintext is shown once at
  creation); usage rows are aggregate-only in every response.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base

_CORRECTION_TARGETS = ("institution", "geography", "dataset", "report")


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PublicDataset(Base):
    __tablename__ = "public_datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    name_hi: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    description_hi: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    license_url: Mapped[str | None] = mapped_column(Text)
    update_frequency: Mapped[str | None] = mapped_column(String(32))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    derived: Mapped[bool] = mapped_column(Boolean, default=False)
    derived_from: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    coverage: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    formats: Mapped[str | None] = mapped_column(String(64), default="csv,json")
    version: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str | None] = mapped_column(Text)
    record_count: Mapped[int | None] = mapped_column(Integer)
    documentation_url: Mapped[str | None] = mapped_column(Text)
    methodology_slug: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')", name="ck_public_datasets_status"
        ),
        CheckConstraint(
            "category IN ('civic_reports', 'verified_reports', 'cases', 'resolutions', "
            "'institutions', 'official_data', 'geography')",
            name="ck_public_datasets_category",
        ),
    )


class PublicDatasetVersion(Base):
    __tablename__ = "public_dataset_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public_datasets.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(Text)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    record_count: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str | None] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(Text)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_public_dataset_versions"),)


class PublicDatasetLineage(Base):
    __tablename__ = "public_dataset_lineage"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public_datasets.id", ondelete="CASCADE"), index=True
    )
    step_order: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String(128))
    input_source: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("dataset_id", "step_order", name="uq_public_dataset_lineage"),
    )


class DataCorrectionRequest(Base):
    __tablename__ = "data_correction_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(Text)
    target_name: Mapped[str | None] = mapped_column(Text)
    field: Mapped[str | None] = mapped_column(Text)
    current_value: Mapped[str | None] = mapped_column(Text)
    suggested_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    status: Mapped[str] = mapped_column(String(16), default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "target_type IN ('institution', 'geography', 'dataset', 'report')",
            name="ck_corrections_target_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_corrections_status"
        ),
    )


class PublicApiKey(Base):
    __tablename__ = "public_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    key_prefix: Mapped[str] = mapped_column(String(8))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    quota_per_hour: Mapped[int] = mapped_column(Integer, default=600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked')", name="ck_public_api_keys_status"),
    )


class PublicApiUsage(Base):
    __tablename__ = "public_api_usage"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("public_api_keys.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    endpoint: Mapped[str] = mapped_column(String(160))
    method: Mapped[str] = mapped_column(String(8))
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DataExportJob(Base):
    __tablename__ = "data_export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("public_datasets.id", ondelete="SET NULL")
    )
    format: Mapped[str] = mapped_column(String(8), default="csv")
    filters: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    row_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    file_key: Mapped[str | None] = mapped_column(Text)
    file_url_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('citizen_reports', 'institutions', 'resolutions', 'statistics')",
            name="ck_export_jobs_kind",
        ),
        CheckConstraint("format IN ('csv', 'json')", name="ck_export_jobs_format"),
        CheckConstraint(
            "status IN ('queued', 'generating', 'ready', 'failed', 'expired')",
            name="ck_export_jobs_status",
        ),
    )


class SavedResearchQuery(Base):
    __tablename__ = "saved_research_queries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
