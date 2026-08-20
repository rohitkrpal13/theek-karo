"""Pydantic v2 schemas for Phase 20 civic intelligence (docs/CIVIC-INTELLIGENCE.md)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IntelligenceFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    institution_id: uuid.UUID | None = None
    signal_type: str | None = None
    signal_status: str | None = None
    date_preset: str | None = "30d"
    start_date: datetime | None = None
    end_date: datetime | None = None
    timezone: str = "Asia/Kolkata"


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------


class TrendComparison(BaseModel):
    period_label: str
    start: datetime | None = None
    end: datetime | None = None
    count: int
    change_count: int | None = None
    change_pct: float | None = None
    direction: Literal["increasing", "decreasing", "stable", "insufficient_data"]
    denominator: str | None = None
    coverage_note: str | None = None


class TrendAnalysisItem(BaseModel):
    metric: str
    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    interval: str = "month"
    observation_period: dict[str, Any] | None = None
    comparison: TrendComparison
    series: list[dict[str, Any]] = Field(default_factory=list)
    seasonality: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TrendAnalysisResponse(BaseModel):
    items: list[TrendAnalysisItem]
    generated_at: datetime
    methodology_note: str


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


class AnomalyItem(BaseModel):
    metric: str
    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    observed_value: float
    expected_low: float | None = None
    expected_high: float | None = None
    deviation_pct: float | None = None
    method: str | None = None
    explanation: str | None = None
    status: str = "NEW"
    detected_at: datetime | None = None


class AnomalyResponse(BaseModel):
    anomalies: list[AnomalyItem]
    generated_at: datetime
    note: str


# ---------------------------------------------------------------------------
# Clusters
# ---------------------------------------------------------------------------


class ClusterItem(BaseModel):
    cluster_key: str
    label: str | None = None
    category_slug: str | None = None
    geography_id: uuid.UUID | None = None
    geography_name: str | None = None
    institution_id: uuid.UUID | None = None
    institution_name: str | None = None
    report_count: int
    evidence_count: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    report_ids: list[uuid.UUID] = Field(default_factory=list)
    status: str = "open"


class ClusterResponse(BaseModel):
    clusters: list[ClusterItem]
    observation_window_days: int
    generated_at: datetime
    note: str


# ---------------------------------------------------------------------------
# Recurring issues
# ---------------------------------------------------------------------------


class RecurringIssueItem(BaseModel):
    institution_id: uuid.UUID | None = None
    institution_name: str | None = None
    geography_id: uuid.UUID | None = None
    geography_name: str | None = None
    category_slug: str | None = None
    issue_type_slug: str | None = None
    distinct_months: int
    total_reports: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    open_reports: int


class RecurringIssueResponse(BaseModel):
    items: list[RecurringIssueItem]
    window_months: int
    min_distinct_months: int
    generated_at: datetime
    note: str


# ---------------------------------------------------------------------------
# Resource gaps
# ---------------------------------------------------------------------------


class ResourceGapItem(BaseModel):
    institution_id: uuid.UUID
    institution_name: str
    resource_key: str
    official_value: float | None = None
    community_value: float | None = None
    gap: float | None = None
    discrepancy_state: str
    last_evaluated_at: datetime | None = None
    source: str | None = None


class ResourceGapResponse(BaseModel):
    items: list[ResourceGapItem]
    generated_at: datetime
    methodology_note: str


class DataGapItem(BaseModel):
    scope: str
    total: int
    with_data: int
    without_data: int
    coverage_pct: float | None = None
    note: str


class DataGapResponse(BaseModel):
    items: list[DataGapItem]
    generated_at: datetime
    interpretation_note: str


class FreshnessItem(BaseModel):
    scope: str
    label: str
    last_updated_at: datetime | None = None
    expected_frequency: str | None = None
    detail: str | None = None


class DataFreshnessResponse(BaseModel):
    items: list[FreshnessItem]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Resolution intelligence
# ---------------------------------------------------------------------------


class AgingBucketItem(BaseModel):
    bucket_label: str
    count: int
    pct: float


class ResolutionIntelligenceResponse(BaseModel):
    total_cases: int
    avg_response_hours: float | None = None
    median_response_hours: float | None = None
    p90_response_hours: float | None = None
    avg_resolution_hours: float | None = None
    median_resolution_hours: float | None = None
    p90_resolution_hours: float | None = None
    within_sla_count: int
    at_risk_count: int
    breached_count: int
    sla_compliance_pct: float
    open_count: int
    aging_buckets: list[AgingBucketItem] = Field(default_factory=list)
    reopen_count: int
    followup_signals: int
    verified_resolution_count: int
    community_confirmed_count: int
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime


class ImprovementItem(BaseModel):
    case_no: str | None = None
    report_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    institution_name: str | None = None
    title: str | None = None
    category_slug: str | None = None
    resolved_at: datetime | None = None
    verified_at: datetime | None = None
    community_confirmed_at: datetime | None = None
    evidence_count: int = 0
    source: str = "resolution"


class ImprovementResponse(BaseModel):
    items: list[ImprovementItem]
    count: int
    generated_at: datetime
    note: str


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------


class ForecastPointItem(BaseModel):
    point: datetime
    low: float
    point_value: float
    high: float


class ForecastRunRead(BaseModel):
    id: uuid.UUID
    metric: str
    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    horizon_days: int
    model_version: str | None = None
    method: str | None = None
    training_start: datetime | None = None
    training_end: datetime | None = None
    status: str
    eval_metrics: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    points: list[ForecastPointItem] = Field(default_factory=list)


class ForecastRunRequest(BaseModel):
    metric: Literal["reports", "resolved", "reports_per_week"] = "reports"
    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    horizon_days: int = Field(default=30, ge=7, le=180)
    interval: Literal["week", "month"] = "week"


class ForecastListResponse(BaseModel):
    runs: list[ForecastRunRead]
    generated_at: datetime
    note: str


class ModelVersionItem(BaseModel):
    model_name: str
    version: str
    model_type: str
    training_data_ref: str | None = None
    feature_definition: dict[str, Any] | None = None
    evaluation_metrics: dict[str, Any] | None = None
    deployed_at: datetime | None = None
    status: str


class ModelRegistryResponse(BaseModel):
    models: list[ModelVersionItem]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Signals + review
# ---------------------------------------------------------------------------


class SignalRead(BaseModel):
    id: uuid.UUID
    signal_type: str
    title: str
    description: str | None = None
    category_slug: str | None = None
    geography_id: uuid.UUID | None = None
    geography_name: str | None = None
    institution_id: uuid.UUID | None = None
    institution_name: str | None = None
    severity: str
    confidence: str
    status: str
    visibility: str
    evidence_count: int
    source_count: int
    observation_period: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None
    explanation: dict[str, Any] | None = None
    detected_at: datetime | None = None
    created_at: datetime
    review_history: list[dict[str, Any]] = Field(default_factory=list)


class SignalListResponse(BaseModel):
    items: list[SignalRead]
    count: int
    generated_at: datetime
    note: str


class SignalDetailResponse(SignalRead):
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReviewActionRequest(BaseModel):
    action: Literal[
        "CONFIRM", "DISMISS", "REQUEST_MORE_DATA", "MONITOR", "ESCALATE", "MARK_RESOLVED"
    ]
    note: str | None = None


class ManualSignalCreate(BaseModel):
    signal_type: str
    title: str
    description: str | None = None
    category_slug: str | None = None
    geography_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    visibility: Literal["PUBLIC", "COMMUNITY", "DEPARTMENT", "ADMIN", "RESTRICTED"] = "PUBLIC"


# ---------------------------------------------------------------------------
# Dashboard + map
# ---------------------------------------------------------------------------


class DashboardSection(BaseModel):
    key: str
    title: str
    data: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class IntelligenceDashboardResponse(BaseModel):
    generated_at: datetime
    geography_name: str | None = None
    sections: list[DashboardSection]
    methodology_note: str


class MapLayerItem(BaseModel):
    layer: str
    geography_id: uuid.UUID | None = None
    geography_name: str | None = None
    geography_type: str | None = None
    value: float
    count: int
    denominator: str | None = None
    normalized: float | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    caveat: str | None = None


class IntelligenceMapResponse(BaseModel):
    layer: str
    explanation: str
    items: list[MapLayerItem]
    generated_at: datetime
    note: str


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class IntelligenceReportCreate(BaseModel):
    title: str
    scope: Literal["PUBLIC", "COMMUNITY", "DEPARTMENT", "ADMIN", "RESTRICTED"] = "PUBLIC"
    geography_id: uuid.UUID | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    format: Literal["json", "csv"] = "json"


class IntelligenceReportRead(BaseModel):
    id: uuid.UUID
    title: str
    scope: str
    geography_id: uuid.UUID | None = None
    filters: dict[str, Any] | None = None
    status: str
    format: str
    generated_at: datetime | None = None
    methodology: dict[str, Any] | None = None
    dataset_versions: dict[str, Any] | None = None
    model_versions: dict[str, Any] | None = None
    created_at: datetime


class IntelligenceReportDetail(IntelligenceReportRead):
    content: dict[str, Any] | None = None
    error: str | None = None
