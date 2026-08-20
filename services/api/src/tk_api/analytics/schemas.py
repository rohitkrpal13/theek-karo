"""Pydantic v2 schemas for Phase 12 Analytics, Dashboards, and Decision Intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsFilterParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    geography_id: uuid.UUID | None = None
    category_slug: str | None = None
    issue_type_slug: str | None = None
    status: str | None = None
    severity: str | None = None
    institution_id: uuid.UUID | None = None
    institution_type_id: uuid.UUID | None = None
    date_preset: Literal["today", "yesterday", "7d", "30d", "90d", "year", "all"] | None = "30d"
    start_date: datetime | None = None
    end_date: datetime | None = None
    interval: Literal["day", "week", "month"] = "day"
    timezone: str = "Asia/Kolkata"


# -----------------------------------------------------------------------------
# KPI Models
# -----------------------------------------------------------------------------


class KpiItem(BaseModel):
    metric_id: str
    name: str
    value: float
    unit: str
    period_label: str
    definition: str
    source: str
    denominator_label: str | None = None
    change_pct: float | None = None
    trend_direction: Literal["up", "down", "flat"] | None = None


class OverviewAnalyticsResponse(BaseModel):
    kpis: list[KpiItem]
    generated_at: datetime
    data_coverage_note: str


# -----------------------------------------------------------------------------
# Trend & Time Series Models
# -----------------------------------------------------------------------------


class TimeSeriesPoint(BaseModel):
    timestamp: str
    total_count: int
    verified_count: int
    resolved_count: int
    critical_count: int


class ReportTrendsResponse(BaseModel):
    series: list[TimeSeriesPoint]
    total_in_range: int
    interval: str


# -----------------------------------------------------------------------------
# Category & Issue Analytics Models
# -----------------------------------------------------------------------------


class IssueTypeBreakdown(BaseModel):
    slug: str
    name: str
    count: int
    pct: float


class CategoryAnalyticsItem(BaseModel):
    category_slug: str
    category_name: str
    report_count: int
    verified_count: int
    resolved_count: int
    open_count: int
    pct_of_total: float
    top_issue_types: list[IssueTypeBreakdown] = Field(default_factory=list)


class CategoryAnalyticsResponse(BaseModel):
    categories: list[CategoryAnalyticsItem]
    total_reports: int


# -----------------------------------------------------------------------------
# Aging & Backlog Models
# -----------------------------------------------------------------------------


class AgingBucket(BaseModel):
    bucket_label: str
    count: int
    pct: float


class VerificationAndBacklogResponse(BaseModel):
    total_submitted: int
    under_verification_count: int
    verified_count: int
    needs_info_count: int
    rejected_count: int
    duplicate_count: int
    verification_rate: float
    median_verification_hours: float | None
    aging_buckets: list[AgingBucket]


class ResolutionAnalyticsResponse(BaseModel):
    total_resolved: int
    resolution_rate: float
    verified_resolution_count: int
    community_confirmed_count: int
    closed_count: int
    reopened_count: int
    median_resolution_hours: float | None
    p90_resolution_hours: float | None
    resolution_by_category: dict[str, float] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Geographic & Institution Models
# -----------------------------------------------------------------------------


class GeographicDrilldownItem(BaseModel):
    geography_id: str
    name: str
    type_name: str
    hierarchy_path: str | None = None
    report_count: int
    verified_count: int
    open_count: int
    resolved_count: int
    resolution_rate: float
    institution_count: int
    coverage_pct: float


class GeographicAnalyticsResponse(BaseModel):
    current_level: str
    current_geography_name: str | None = None
    children: list[GeographicDrilldownItem]


class InstitutionAnalyticsResponse(BaseModel):
    institution_id: str
    name: str
    type_name: str
    operational_status: str
    report_count: int
    verified_count: int
    open_count: int
    resolved_count: int
    resolution_rate: float
    top_category: str | None = None
    last_reported_at: str | None = None
    official_data_updated_at: str | None = None
    discrepancies_flagged_count: int = 0


# -----------------------------------------------------------------------------
# Administrative & Operations Models
# -----------------------------------------------------------------------------


class DataQualityScorecardResponse(BaseModel):
    total_sources: int
    healthy_sources_count: int
    stale_sources_count: int
    failed_sources_count: int
    total_records_ingested: int
    pending_entity_matches_count: int
    institutions_with_official_data_pct: float
    sources_breakdown: list[dict[str, Any]] = Field(default_factory=list)


class AiOpsAnalyticsResponse(BaseModel):
    total_requests: int
    total_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: int
    p95_latency_ms: int
    feedback_positivity_pct: float
    task_breakdown: dict[str, int] = Field(default_factory=dict)
    model_breakdown: dict[str, int] = Field(default_factory=dict)


class ModerationAnalyticsResponse(BaseModel):
    pending_verification_count: int
    flagged_content_count: int
    duplicate_candidates_count: int
    high_priority_count: int
    median_queue_age_hours: float | None
    aging_buckets: list[AgingBucket] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Export Models
# -----------------------------------------------------------------------------


class ExportRequest(BaseModel):
    domain: Literal["reports", "institutions", "kpis", "discrepancies", "overview"] = "reports"
    format: Literal["csv", "json"] = "csv"
    filters: dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    filename: str
    content_type: str
    data: str
    record_count: int
    generated_at: datetime
