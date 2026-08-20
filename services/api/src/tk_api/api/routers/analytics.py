"""FastAPI router for Phase 12 Analytics, Dashboards, and Decision Intelligence."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from tk_api.analytics.catalog import GLOBAL_METRIC_REGISTRY
from tk_api.analytics.schemas import (
    AiOpsAnalyticsResponse,
    AnalyticsFilterParams,
    CategoryAnalyticsResponse,
    DataQualityScorecardResponse,
    ExportRequest,
    ExportResponse,
    GeographicAnalyticsResponse,
    InstitutionAnalyticsResponse,
    ModerationAnalyticsResponse,
    OverviewAnalyticsResponse,
    ReportTrendsResponse,
    ResolutionAnalyticsResponse,
    VerificationAndBacklogResponse,
)
from tk_api.analytics.service import AnalyticsService
from tk_api.api.deps import CurrentUser, DbSession, OptionalUser, require_active
from tk_api.core.errors import ApiError

analytics_router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
_service = AnalyticsService()


class AnalyticsError(ApiError):
    pass


@analytics_router.get("/catalog")
async def get_metric_catalog(
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Retrieve cataloged metric definitions, formulas, and dimension specs."""
    role = "admin" if user and user.has_role("admin") else "public"
    metrics = GLOBAL_METRIC_REGISTRY.list_metrics(role=role)
    return {"metrics": [m.to_dict() for m in metrics], "count": len(metrics)}


@analytics_router.get("/overview", response_model=OverviewAnalyticsResponse)
async def get_overview(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    category_slug: str | None = None,
    date_preset: str | None = "30d",
    timezone: str = "Asia/Kolkata",
) -> OverviewAnalyticsResponse:
    """Retrieve public high-level KPI cards and civic health summary."""
    filters = AnalyticsFilterParams(
        geography_id=geography_id,
        category_slug=category_slug,
        date_preset=date_preset,  # type: ignore[arg-type]
        timezone=timezone,
    )
    return await _service.get_overview_kpis(session, filters)


@analytics_router.get("/trends", response_model=ReportTrendsResponse)
async def get_trends(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    category_slug: str | None = None,
    date_preset: str | None = "30d",
    interval: str = "day",
    timezone: str = "Asia/Kolkata",
) -> ReportTrendsResponse:
    """Retrieve time-series trends (Total, Verified, Resolved, Critical)."""
    filters = AnalyticsFilterParams(
        geography_id=geography_id,
        category_slug=category_slug,
        date_preset=date_preset,  # type: ignore[arg-type]
        interval=interval,  # type: ignore[arg-type]
        timezone=timezone,
    )
    return await _service.get_report_trends(session, filters)


@analytics_router.get("/categories", response_model=CategoryAnalyticsResponse)
async def get_categories(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    date_preset: str | None = "30d",
    timezone: str = "Asia/Kolkata",
) -> CategoryAnalyticsResponse:
    """Retrieve category breakdown and nested issue-type distributions."""
    filters = AnalyticsFilterParams(
        geography_id=geography_id,
        date_preset=date_preset,  # type: ignore[arg-type]
        timezone=timezone,
    )
    return await _service.get_category_analytics(session, filters)


@analytics_router.get("/resolution", response_model=ResolutionAnalyticsResponse)
async def get_resolution(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    category_slug: str | None = None,
    date_preset: str | None = "30d",
    timezone: str = "Asia/Kolkata",
) -> ResolutionAnalyticsResponse:
    """Retrieve resolution metrics, median duration, and verified resolution rates."""
    filters = AnalyticsFilterParams(
        geography_id=geography_id,
        category_slug=category_slug,
        date_preset=date_preset,  # type: ignore[arg-type]
        timezone=timezone,
    )
    return await _service.get_resolution_analytics(session, filters)


@analytics_router.get("/verification", response_model=VerificationAndBacklogResponse)
async def get_verification(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    category_slug: str | None = None,
    date_preset: str | None = "30d",
    timezone: str = "Asia/Kolkata",
) -> VerificationAndBacklogResponse:
    """Retrieve verification pipeline status breakdown and open aging buckets."""
    filters = AnalyticsFilterParams(
        geography_id=geography_id,
        category_slug=category_slug,
        date_preset=date_preset,  # type: ignore[arg-type]
        timezone=timezone,
    )
    return await _service.get_verification_and_backlog(session, filters)


@analytics_router.get("/geography", response_model=GeographicAnalyticsResponse)
async def get_geography_drilldown(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
) -> GeographicAnalyticsResponse:
    """Retrieve child geography breakdown with institution counts and data coverage."""
    filters = AnalyticsFilterParams(geography_id=geography_id)
    return await _service.get_geographic_drilldown(session, filters)


@analytics_router.get("/institutions/{institution_id}", response_model=InstitutionAnalyticsResponse)
async def get_institution_analytics(
    institution_id: uuid.UUID,
    session: DbSession,
) -> InstitutionAnalyticsResponse:
    """Retrieve institution-specific analytics, issue volume, and resolution rate."""
    res = await _service.get_institution_analytics(session, institution_id)
    if not res:
        raise AnalyticsError("Institution not found", 404, "institution_not_found")
    return res


@analytics_router.get(
    "/data-quality",
    response_model=DataQualityScorecardResponse,
    dependencies=[Depends(require_active("admin", "analyst"))],
)
async def get_data_quality(
    session: DbSession,
) -> DataQualityScorecardResponse:
    """Admin/Analyst: Retrieve government data source health and coverage scorecard."""
    return await _service.get_data_quality_analytics(session)


@analytics_router.get(
    "/ai-ops",
    response_model=AiOpsAnalyticsResponse,
    dependencies=[Depends(require_active("admin"))],
)
async def get_ai_operations(
    session: DbSession,
) -> AiOpsAnalyticsResponse:
    """Admin: Retrieve AI model distribution, token volume, USD costs, and feedback."""
    return await _service.get_ai_operations_analytics(session)


@analytics_router.get(
    "/moderation",
    response_model=ModerationAnalyticsResponse,
    dependencies=[Depends(require_active("moderator", "admin"))],
)
async def get_moderation_analytics(
    session: DbSession,
) -> ModerationAnalyticsResponse:
    """Moderator/Admin: Retrieve pending queue size, aging, and high priority count."""
    filters = AnalyticsFilterParams()
    return await _service.get_moderation_analytics(session, filters)


@analytics_router.post("/export", response_model=ExportResponse)
async def export_analytics_data(
    req: ExportRequest,
    session: DbSession,
    user: CurrentUser,
) -> ExportResponse:
    """Export analytics records in CSV or JSON format with small-cell privacy masking."""
    return await _service.export_analytics(session, req)
