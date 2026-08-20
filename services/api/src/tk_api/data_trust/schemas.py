"""Pydantic schemas for the Phase 23 Data Trust API layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Evidence Registry
# ---------------------------------------------------------------------------


class EvidenceRecordCreate(BaseModel):
    evidence_type: str
    title: str | None = None
    description: str | None = None
    source_type: str = "CITIZEN"
    source_id: str | None = None
    media_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    location: dict[str, Any] | None = None
    language: str | None = None
    original_text: str | None = None


class EvidenceRecordRead(BaseModel):
    id: str
    evidence_type: str
    title: str | None = None
    description: str | None = None
    source_type: str
    source_id: str | None = None
    uploader_id: str | None = None
    media_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    checksum_sha256: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    status: str
    verification_status: str
    verification_count: int
    language: str | None = None
    created_at: str | None = None


class EvidenceRecordList(BaseModel):
    items: list[EvidenceRecordRead]
    total: int = 0


# ---------------------------------------------------------------------------
# Verification Records
# ---------------------------------------------------------------------------


class VerificationRecordCreate(BaseModel):
    entity_type: str
    entity_id: str
    decision: str
    method: str
    evidence_refs: list[str] = Field(default_factory=list)
    explanation: str | None = None
    confidence: float | None = None
    ai_model: str | None = None
    ai_model_version: str | None = None
    ai_reasoning: str | None = None


class VerificationRecordRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    reviewer_id: str | None = None
    reviewer_type: str
    decision: str
    method: str
    evidence_refs: list[Any]
    explanation: str | None = None
    confidence: float | None = None
    ai_model: str | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------


class DataQualityCheck(BaseModel):
    entity_type: str
    entity_id: str
    source_id: str | None = None
    dataset_id: str | None = None
    dimension: str
    score: float = Field(ge=0.0, le=1.0)
    status: str
    details: dict[str, Any] | None = None
    missing_fields: list[str] | None = None
    invalid_fields: list[str] | None = None
    overall_status: str = "UNVERIFIED"
    ai_assisted: bool = False
    ai_confidence: float | None = None
    ai_reasoning: str | None = None


class DataQualityRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    dimension: str
    score: float
    status: str
    overall_status: str
    details: dict[str, Any] | None = None
    created_at: str | None = None


class DataQualitySummary(BaseModel):
    entity_type: str
    entity_id: str
    overall_status: str
    dimensions: list[DataQualityRead]


# ---------------------------------------------------------------------------
# Data Conflicts
# ---------------------------------------------------------------------------


class DataConflictCreate(BaseModel):
    entity_type: str
    entity_id: str
    field_name: str
    source_a_id: str | None = None
    source_a_value: Any
    source_a_timestamp: str | None = None
    source_b_id: str | None = None
    source_b_value: Any
    source_b_timestamp: str | None = None
    severity: str = "MEDIUM"


class DataConflictResolve(BaseModel):
    status: str
    resolved_value: Any = None
    resolution_note: str | None = None


class DataConflictRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    field_name: str
    source_a_value: Any
    source_b_value: Any
    source_a_timestamp: str | None = None
    source_b_timestamp: str | None = None
    status: str
    resolved_value: Any = None
    resolution_note: str | None = None
    severity: str
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------


class DisputeCreate(BaseModel):
    dispute_target_type: str
    dispute_target_id: str
    reason: str
    explanation: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class DisputeReview(BaseModel):
    status: str
    decision: str | None = None


class DisputeRead(BaseModel):
    id: str
    dispute_target_type: str
    dispute_target_id: str
    filed_by: str
    reason: str
    explanation: str | None = None
    status: str
    decision: str | None = None
    public_banner: bool
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Data Change History
# ---------------------------------------------------------------------------


class DataChangeHistoryRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    field_name: str
    old_value: Any = None
    new_value: Any = None
    change_source: str
    changed_by: str | None = None
    reason: str | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Metric Definitions
# ---------------------------------------------------------------------------


class MetricDefinitionCreate(BaseModel):
    metric_id: str
    name: str
    name_hi: str | None = None
    description: str
    formula: str
    definition: str | None = None
    source: str | None = None
    category: str | None = None
    version: str = "1.0"
    visibility: str = "PUBLIC"
    required_role: str | None = None
    coverage: str | None = None
    limitations: str | None = None
    period: str | None = None


class MetricDefinitionRead(BaseModel):
    id: str
    metric_id: str
    name: str
    name_hi: str | None = None
    description: str
    formula: str
    definition: str | None = None
    source: str | None = None
    category: str | None = None
    version: str
    visibility: str
    coverage: str | None = None
    limitations: str | None = None
    status: str
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Data Quality Dashboard
# ---------------------------------------------------------------------------


class DataQualityDashboard(BaseModel):
    total_sources: int
    active_sources: int
    failed_sources: int
    stale_sources: int
    total_datasets: int
    total_conflicts: int
    open_conflicts: int
    total_disputes: int
    open_disputes: int
    total_evidence: int
    verified_evidence: int
    total_verifications: int
    quarantined_records: int
    freshness_summary: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class ProvenanceChain(BaseModel):
    entity_type: str
    entity_id: str
    source: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    verifications: list[dict[str, Any]] = Field(default_factory=list)
    change_history: list[dict[str, Any]] = Field(default_factory=list)
    quality: dict[str, Any] | None = None
    disputes: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Correction Requests
# ---------------------------------------------------------------------------


class CorrectionRequestCreate(BaseModel):
    target_type: str
    target_id: str
    target_name: str | None = None
    field: str | None = None
    current_value: str | None = None
    suggested_value: str | None = None
    reason: str
    evidence: dict[str, Any] | None = None


class CorrectionRequestRead(BaseModel):
    id: str
    user_id: str
    target_type: str
    target_id: str
    target_name: str | None = None
    field: str | None = None
    current_value: str | None = None
    suggested_value: str | None = None
    reason: str | None = None
    status: str
    decision_note: str | None = None
    created_at: str | None = None


class CorrectionReview(BaseModel):
    status: str  # approved, rejected
    decision_note: str | None = None
