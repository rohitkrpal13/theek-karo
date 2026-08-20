"""Pydantic v2 schemas for Phase 15 public data, research and transparency."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FreshnessLabel = Literal["fresh", "recently_updated", "may_be_outdated", "stale", "no_data"]


class DatasetListItem(BaseModel):
    slug: str
    name: str
    name_hi: str | None = None
    description: str | None = None
    category: str | None = None
    publisher: str | None = None
    source: str | None = None
    license: str | None = None
    update_frequency: str | None = None
    derived: bool = False
    version: str
    record_count: int | None = None
    last_updated_at: datetime | None = None
    freshness: FreshnessLabel = "no_data"
    status: str = "active"


class LineageStep(BaseModel):
    step_order: int
    step_name: str
    input_source: str | None = None
    description: str | None = None


class DatasetVersionItem(BaseModel):
    version: str
    released_at: datetime
    record_count: int | None = None
    checksum_sha256: str | None = None
    change_summary: str | None = None


class DatasetDetail(DatasetListItem):
    description_hi: str | None = None
    source_url: str | None = None
    license_url: str | None = None
    released_at: datetime | None = None
    retrieved_at: datetime | None = None
    processing_date: datetime | None = None
    derived: bool = False
    derived_from: dict[str, Any] | None = None
    coverage: dict[str, Any] | None = None
    formats: str | None = None
    checksum_sha256: str | None = None
    documentation_url: str | None = None
    methodology_slug: str | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[DatasetVersionItem] = Field(default_factory=list)
    lineage: list[LineageStep] = Field(default_factory=list)


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=300)
    name_hi: str | None = None
    description: str | None = None
    description_hi: str | None = None
    category: Literal[
        "civic_reports",
        "verified_reports",
        "cases",
        "resolutions",
        "institutions",
        "official_data",
        "geography",
    ] = "civic_reports"
    publisher: str | None = None
    source: str | None = None
    source_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    update_frequency: Literal["continuous", "daily", "weekly", "monthly", "quarterly", "adhoc"] = (
        "continuous"
    )
    released_at: datetime | None = None
    retrieved_at: datetime | None = None
    processing_date: datetime | None = None
    derived: bool = False
    derived_from: dict[str, Any] | None = None
    coverage: dict[str, Any] | None = None
    formats: str = "csv,json"
    version: str = "1.0.0"
    checksum_sha256: str | None = None
    record_count: int | None = Field(default=None, ge=0)
    documentation_url: str | None = None
    methodology_slug: str | None = None


class DatasetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    name_hi: str | None = None
    description: str | None = None
    description_hi: str | None = None
    publisher: str | None = None
    source: str | None = None
    source_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    update_frequency: (
        Literal["continuous", "daily", "weekly", "monthly", "quarterly", "adhoc"] | None
    ) = None
    released_at: datetime | None = None
    retrieved_at: datetime | None = None
    processing_date: datetime | None = None
    derived: bool | None = None
    derived_from: dict[str, Any] | None = None
    coverage: dict[str, Any] | None = None
    formats: str | None = None
    checksum_sha256: str | None = None
    record_count: int | None = Field(default=None, ge=0)
    documentation_url: str | None = None
    methodology_slug: str | None = None
    last_updated_at: datetime | None = None
    status: Literal["active", "inactive", "archived"] | None = None


class DatasetVersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    record_count: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = None
    change_summary: str | None = None


class LineageStepCreate(BaseModel):
    step_order: int = Field(ge=1)
    step_name: str = Field(min_length=2, max_length=128)
    input_source: str | None = None
    description: str | None = None


# -----------------------------------------------------------------------------
# Coverage, freshness, methodology
# -----------------------------------------------------------------------------


class CoverageLevel(BaseModel):
    level: str
    total: int
    with_institutions: int
    with_reports: int
    with_official_data: int
    institution_coverage_pct: float
    reporting_coverage_pct: float


class CoverageResponse(BaseModel):
    generated_at: datetime
    levels: list[CoverageLevel]
    overall_note: str


class FreshnessItem(BaseModel):
    scope: str
    label: FreshnessLabel
    last_activity_at: datetime | None = None
    detail: str


class MethodologySection(BaseModel):
    slug: str
    title: str
    body: str


class MetricDefinition(BaseModel):
    metric_id: str
    name: str
    formula: str
    explanation: str
    source: str


class MethodologyResponse(BaseModel):
    generated_at: datetime
    sections: list[MethodologySection]
    metrics: list[MetricDefinition]


# -----------------------------------------------------------------------------
# Research queries
# -----------------------------------------------------------------------------


class ResearchFilterParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    status: Literal["open", "resolved", "verified", "all"] | None = "all"
    date_from: datetime | None = None
    date_to: datetime | None = None
    date_preset: Literal["today", "7d", "30d", "90d", "year", "all"] | None = "30d"


class ResearchTrendPoint(BaseModel):
    timestamp: str
    total_count: int
    verified_count: int
    resolved_count: int


class ResearchQueryResult(BaseModel):
    count: int
    verified_count: int
    resolved_count: int
    open_count: int
    period_label: str
    trends: list[ResearchTrendPoint]
    categories: list[dict[str, Any]]
    top_institutions: list[dict[str, Any]]
    coverage: dict[str, Any]
    limitations: list[str]
    notices: list[str]
    generated_at: datetime


class GeographyCompareItem(BaseModel):
    geography_id: uuid.UUID
    name: str
    report_count: int
    verified_count: int
    resolved_count: int
    institution_count: int
    reports_per_1000_institutions: float | None
    last_report_at: datetime | None
    notes: list[str]


class CompareResponse(BaseModel):
    generated_at: datetime
    items: list[GeographyCompareItem]
    warnings: list[str]
    methodology_note: str


class TrendSeriesItem(BaseModel):
    timestamp: str
    value: int


class TrendsResponse(BaseModel):
    metric: str
    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    period_label: str
    series: list[TrendSeriesItem]
    change_count: int
    change_pct: float | None
    generated_at: datetime


# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------


class ExportRequest(BaseModel):
    kind: Literal["citizen_reports", "institutions", "resolutions", "statistics"]
    format: Literal["csv", "json"] = "csv"
    filters: dict[str, Any] = Field(default_factory=dict)


class ExportJobRead(BaseModel):
    id: uuid.UUID
    kind: str
    format: str
    filters: dict[str, Any]
    row_count: int | None = None
    status: str
    requested_at: datetime
    completed_at: datetime | None = None
    download_url: str | None = None
    expires_at: datetime | None = None
    error: str | None = None


class ExportJobCreate(ExportJobRead):
    pass


# -----------------------------------------------------------------------------
# Corrections
# -----------------------------------------------------------------------------


class CorrectionCreate(BaseModel):
    target_type: Literal["institution", "geography", "dataset", "report"]
    target_id: str = Field(min_length=1, max_length=120)
    target_name: str | None = None
    field: str | None = None
    current_value: str | None = None
    suggested_value: str | None = None
    reason: str = Field(min_length=5, max_length=2000)
    evidence: dict[str, Any] | None = None


class CorrectionRead(BaseModel):
    id: uuid.UUID
    target_type: str
    target_id: str
    target_name: str | None = None
    field: str | None = None
    current_value: str | None = None
    suggested_value: str | None = None
    reason: str | None = None
    status: str
    decision_note: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class CorrectionDecision(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


# -----------------------------------------------------------------------------
# Saved research queries
# -----------------------------------------------------------------------------


class SavedQueryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    filters: dict[str, Any] = Field(default_factory=dict)


class SavedQueryRead(BaseModel):
    id: uuid.UUID
    name: str
    filters: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# API keys + usage
# -----------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    quota_per_hour: int = Field(default=600, ge=60, le=10000)


class ApiKeyRead(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    status: str
    quota_per_hour: int
    created_at: datetime
    last_used_at: datetime | None = None


class ApiKeySecret(ApiKeyRead):
    key: str


class UsageBucket(BaseModel):
    endpoint: str
    requests: int
    errors: int
    latency_ms_p95: int
    api_key: str | None = None
    day: str | None = None


class UsageResponse(BaseModel):
    generated_at: datetime
    total_requests: int
    buckets: list[UsageBucket]


# -----------------------------------------------------------------------------
# Public API payloads
# -----------------------------------------------------------------------------


class PublicGeographyItem(BaseModel):
    id: uuid.UUID
    type_code: str
    name: str
    parent_id: uuid.UUID | None = None
    child_count: int = 0
    has_boundary: bool = False


class PublicCategoryItem(BaseModel):
    slug: str
    name_key: str
    icon: str
    report_count: int = 0
    is_active: bool = True


class PublicReportItem(BaseModel):
    id: uuid.UUID
    ticket_no: str
    title: str
    category_slug: str
    issue_type_slug: str | None = None
    status: str
    severity: str | None = None
    boundary_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    lat: float | None = None
    lon: float | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_verified_at: datetime | None = None


class PublicInstitutionItem(BaseModel):
    id: uuid.UUID
    name: str
    type_code: str
    geography_id: uuid.UUID | None = None
    official_identifier: str | None = None
    operational_status: str
    verification_state: str
    lat: float | None = None
    lon: float | None = None
    report_count: int = 0
    open_report_count: int = 0


class PublicResolutionItem(BaseModel):
    case_no: str
    report_ticket_no: str | None = None
    case_status: str
    department_name: str | None = None
    submitted_at: datetime | None = None
    resolution_date: datetime | None = None
    decision: str | None = None
    resolution_verified_at: datetime | None = None
    evidence_count: int = 0
    public_evidence: bool = False


class PublicDepartmentItem(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    type_name: str | None = None
    status: str
    member_count: int = 0
    case_assigned_count: int = 0


class PublicDepartmentProfile(BaseModel):
    department: PublicDepartmentItem
    metrics: dict[str, Any]
    methodology_note: str
    limitations: list[str]
    generated_at: datetime


class PublicStatistics(BaseModel):
    generated_at: datetime
    note: str
    data: dict[str, Any]


class PublicNatStats(BaseModel):
    generated_at: datetime
    note: str
    stats: dict[str, Any]
