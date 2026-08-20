"""FastAPI router for Phase 20 Civic Intelligence (spec §6-§22).

Everything here is a read-only observation of stored data (or an append-only
review/queue action). No endpoint mutates reports or cases. Forecasts and
intelligence reports run in the worker with an inline fallback for tests and
single-process deploys (same pattern as the reports router).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from tk_api.api.deps import CurrentUser, DbSession, OptionalUser, require_active
from tk_api.core.db import create_session_factory
from tk_api.core.errors import ApiError
from tk_api.geography.models import Geography
from tk_api.intelligence.anomalies import AnomalyEngine
from tk_api.intelligence.clusters import ClusterEngine, RecurringIssueEngine
from tk_api.intelligence.forecasting import ForecastExecutor
from tk_api.intelligence.freshness import DataFreshnessEngine
from tk_api.intelligence.models import (
    ForecastResult,
    ForecastRun,
    IntelligenceReport,
    ModelVersion,
)
from tk_api.intelligence.resolve_intel import ResolutionIntelligenceService
from tk_api.intelligence.schemas import (
    AnomalyResponse,
    ClusterResponse,
    DashboardSection,
    DataFreshnessResponse,
    DataGapResponse,
    ForecastListResponse,
    ForecastPointItem,
    ForecastRunRead,
    ForecastRunRequest,
    ImprovementResponse,
    IntelligenceDashboardResponse,
    IntelligenceMapResponse,
    IntelligenceReportCreate,
    IntelligenceReportDetail,
    IntelligenceReportRead,
    ManualSignalCreate,
    MapLayerItem,
    ModelRegistryResponse,
    ModelVersionItem,
    RecurringIssueResponse,
    ResolutionIntelligenceResponse,
    ReviewActionRequest,
    SignalDetailResponse,
    SignalListResponse,
    SignalRead,
    TrendAnalysisResponse,
)
from tk_api.intelligence.signals import SignalService
from tk_api.intelligence.trends import TrendEngine
from tk_api.reports.models import Report

intelligence_router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

_signals = SignalService()
_resolution = ResolutionIntelligenceService()
_admin_required = require_active("admin")
_department_required = require_active("admin", "department_representative", "department_manager")
logger = logging.getLogger("tk_api.intelligence")


@intelligence_router.get("/overview", response_model=IntelligenceDashboardResponse)
async def intelligence_overview(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    date_preset: str = "30d",
    timezone: str = "Asia/Kolkata",
) -> IntelligenceDashboardResponse:
    trend = await TrendEngine().summarize(
        session, geography_id=geography_id, preset=date_preset, timezone=timezone
    )
    anomalies = await AnomalyEngine().summarize(session, geography_id=geography_id)
    clusters = await ClusterEngine().summarize(session, geography_id=geography_id)
    recurring = await RecurringIssueEngine().summarize(session, geography_id=geography_id)
    freshness = await DataFreshnessEngine().scan(session)
    geo = await session.get(Geography, geography_id) if geography_id else None
    # /overview refreshes persisted clusters (idempotent upsert) - commit once
    # so the read-side write is durable.
    await session.commit()
    return IntelligenceDashboardResponse(
        generated_at=trend.generated_at,
        geography_name=geo.name if geo else None,
        sections=[
            DashboardSection(
                key="trends",
                title="Trend comparison",
                data={
                    "direction": trend.items[0].comparison.direction if trend.items else None,
                    "change_pct": trend.items[0].comparison.change_pct if trend.items else None,
                    "series": trend.items[0].series if trend.items else [],
                    "methodology": trend.methodology_note,
                },
                limitations=["Comparable-window ratio; no causation."],
            ),
            DashboardSection(
                key="anomalies",
                title="Detected anomalies",
                data={
                    "anomalies": [a.model_dump(mode="json") for a in anomalies.anomalies],
                    "note": anomalies.note,
                },
                limitations=["Deviation triggers require human review."],
            ),
            DashboardSection(
                key="clusters",
                title="Issue clusters",
                data={
                    "clusters": [c.model_dump(mode="json") for c in clusters.clusters],
                    "note": clusters.note,
                },
                limitations=["Clusters never merge or delete reports."],
            ),
            DashboardSection(
                key="recurring_issues",
                title="Recurring issues",
                data={"items": [i.model_dump(mode="json") for i in recurring.items]},
                limitations=["Distinct-month recurrence is a review trigger."],
            ),
            DashboardSection(
                key="data_freshness",
                title="Data freshness",
                data={"items": [i.model_dump(mode="json") for i in freshness.items]},
                limitations=["Last-import based; sources may publish elsewhere."],
            ),
        ],
        methodology_note=(
            "Deterministic engines over stored data (trends/seasonality, IQR anomalies, "
            "geo+category clusters, distinct-month recurrence, staleness checks). "
            "Everything is inspectable and reason-free; no ML model is invoked."
        ),
    )


@intelligence_router.get("/signals", response_model=SignalListResponse)
async def list_signals(
    session: DbSession,
    user: OptionalUser = None,
    signal_type: str | None = None,
    signal_status: str | None = None,
    geography_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SignalListResponse:
    return await _signals.list(
        session,
        signal_type=signal_type,
        status=signal_status,
        geography_id=geography_id,
        limit=min(limit, 100),
        offset=offset,
        user=user,
    )


@intelligence_router.get("/signals/{signal_id}", response_model=SignalDetailResponse)
async def get_signal(session: DbSession, signal_id: uuid.UUID) -> SignalDetailResponse:
    return await _signals.get(session, signal_id)


@intelligence_router.post(
    "/signals",
    response_model=SignalRead,
    status_code=201,
    dependencies=[Depends(_admin_required)],
)
async def create_signal(
    session: DbSession,
    user: CurrentUser,
    payload: ManualSignalCreate,
) -> SignalRead:
    signal = await _signals.create_manual(session, user, payload)
    await session.commit()
    return signal


@intelligence_router.post(
    "/signals/{signal_id}/review",
    response_model=SignalRead,
    dependencies=[Depends(_department_required)],
)
async def review_signal(
    session: DbSession,
    user: CurrentUser,
    signal_id: uuid.UUID,
    payload: ReviewActionRequest,
) -> SignalRead:
    signal = await _signals.review(session, user, signal_id, payload)
    await session.commit()
    return signal


@intelligence_router.get("/trends", response_model=TrendAnalysisResponse)
async def get_trends(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    category_slug: str | None = None,
    date_preset: str = "30d",
    timezone: str = "Asia/Kolkata",
) -> TrendAnalysisResponse:
    return await TrendEngine().summarize(
        session,
        geography_id=geography_id,
        category_slug=category_slug,
        preset=date_preset,
        timezone=timezone,
    )


@intelligence_router.get("/anomalies", response_model=AnomalyResponse)
async def get_anomalies(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
) -> AnomalyResponse:
    return await AnomalyEngine().summarize(session, geography_id=geography_id)


@intelligence_router.get("/clusters", response_model=ClusterResponse)
async def get_clusters(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    category_slug: str | None = None,
) -> ClusterResponse:
    response = await ClusterEngine().summarize(
        session, geography_id=geography_id, category_slug=category_slug
    )
    # summarize() refreshes the persisted cluster table (idempotent upsert);
    # the worker also runs it daily. Commit keeps the read-side refresh durable.
    await session.commit()
    return response


@intelligence_router.get("/recurring", response_model=RecurringIssueResponse)
async def get_recurring(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
) -> RecurringIssueResponse:
    return await RecurringIssueEngine().summarize(session, geography_id=geography_id)


@intelligence_router.get("/resolution", response_model=ResolutionIntelligenceResponse)
async def get_resolution_intelligence(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
) -> ResolutionIntelligenceResponse:
    return await _resolution.summarize(session, geography_id=geography_id)


@intelligence_router.get("/improvements", response_model=ImprovementResponse)
async def get_improvements(
    session: DbSession,
    geography_id: uuid.UUID | None = None,
    limit: int = 50,
) -> ImprovementResponse:
    return await _resolution.improvements(session, geography_id=geography_id, limit=limit)


@intelligence_router.get("/freshness", response_model=DataFreshnessResponse)
async def get_data_freshness(session: DbSession) -> DataFreshnessResponse:
    return await DataFreshnessEngine().scan(session)


@intelligence_router.get("/data-gaps", response_model=DataGapResponse)
async def get_data_gaps(session: DbSession) -> DataGapResponse:
    return await DataFreshnessEngine().gap_analysis(session)


@intelligence_router.get("/map", response_model=IntelligenceMapResponse)
async def get_intelligence_map(
    session: DbSession,
    layer: str = "report-intensity",
    geography_type: str | None = None,
    days: int = 90,
) -> IntelligenceMapResponse:
    from tk_api.geography.models import GeographyType

    since = datetime.now(UTC) - timedelta(days=min(days, 365))
    geo_stmt = select(Geography, GeographyType.code).join(
        GeographyType, Geography.type_id == GeographyType.id
    )
    if geography_type:
        geo_stmt = geo_stmt.where(GeographyType.code == geography_type)
    geo_rows = (await session.execute(geo_stmt)).all()
    counts: dict[uuid.UUID, int] = {}
    rows = (
        await session.execute(
            select(Report.boundary_id, func.count(Report.id))
            .where(
                Report.visibility == "public",
                Report.deleted_at.is_(None),
                Report.created_at >= since,
                Report.boundary_id.isnot(None),
            )
            .group_by(Report.boundary_id)
        )
    ).all()
    for gid, n in rows:
        counts[gid] = int(n)
    total = sum(counts.values()) or 1
    items = []
    for geo, type_code in geo_rows:
        n = counts.get(geo.id, 0)
        if n == 0:
            continue
        items.append(
            MapLayerItem(
                layer=layer,
                geography_id=geo.id,
                geography_name=geo.name,
                geography_type=type_code,
                value=float(n),
                count=n,
                denominator=f"public reports in last {days}d",
                normalized=round(n / total * 100, 2),
                detail={"window_days": days},
                caveat="Raw counts, not rates; small areas will look active.",
            )
        )
    items.sort(key=lambda x: x.value, reverse=True)
    return IntelligenceMapResponse(
        layer=layer,
        explanation="Per-area public report intensity.",
        items=items,
        generated_at=datetime.now(UTC),
        note="Read-only aggregation; no weighting by population applied.",
    )


def _points(points: Sequence[ForecastResult]) -> list[ForecastPointItem]:
    return [
        ForecastPointItem(
            point=p.point,
            low=p.low,
            point_value=p.point_value,
            high=p.high,
        )
        for p in points
    ]


@intelligence_router.get("/forecasts", response_model=ForecastListResponse)
async def list_forecasts(
    session: DbSession,
    limit: int = 10,
) -> ForecastListResponse:
    runs = (
        (
            await session.execute(
                select(ForecastRun).order_by(ForecastRun.created_at.desc()).limit(min(limit, 50))
            )
        )
        .scalars()
        .all()
    )
    out: list[ForecastRunRead] = []
    for run in runs:
        points = (
            (
                await session.execute(
                    select(ForecastResult)
                    .where(ForecastResult.run_id == run.id)
                    .order_by(ForecastResult.point.asc())
                )
            )
            .scalars()
            .all()
        )
        out.append(
            ForecastRunRead(
                id=run.id,
                metric=run.metric,
                geography_id=run.geography_id,
                category_slug=run.category_slug,
                horizon_days=run.horizon_days,
                model_version=run.model_version,
                method=run.method,
                training_start=run.training_start,
                training_end=run.training_end,
                status=run.status,
                eval_metrics=run.eval_metrics,
                error=run.error,
                created_at=run.created_at,
                points=_points(points),
            )
        )
    return ForecastListResponse(
        runs=out,
        generated_at=datetime.now(UTC),
        note=(
            "Forecasts continue observed levels; they are planning ranges, not causal predictions."
        ),
    )


@intelligence_router.post(
    "/forecasts", response_model=ForecastRunRead, dependencies=[Depends(_department_required)]
)
async def run_forecast(
    session: DbSession,
    user: CurrentUser,
    payload: ForecastRunRequest,
) -> ForecastRunRead:
    run = ForecastRun(
        metric=payload.metric,
        geography_id=payload.geography_id,
        category_slug=payload.category_slug,
        horizon_days=payload.horizon_days,
        status="queued",
    )
    session.add(run)
    await session.flush()
    await ForecastExecutor().execute(session, run)
    await session.commit()
    points = (
        (
            await session.execute(
                select(ForecastResult)
                .where(ForecastResult.run_id == run.id)
                .order_by(ForecastResult.point.asc())
            )
        )
        .scalars()
        .all()
    )
    return ForecastRunRead(
        id=run.id,
        metric=run.metric,
        geography_id=run.geography_id,
        category_slug=run.category_slug,
        horizon_days=run.horizon_days,
        model_version=run.model_version,
        method=run.method,
        training_start=run.training_start,
        training_end=run.training_end,
        status=run.status,
        eval_metrics=run.eval_metrics,
        error=run.error,
        created_at=run.created_at,
        points=_points(points),
    )


@intelligence_router.get("/model-versions", response_model=ModelRegistryResponse)
async def list_model_versions(session: DbSession) -> ModelRegistryResponse:
    rows = (await session.execute(select(ModelVersion))).scalars().all()
    items = [
        ModelVersionItem(
            model_name=m.model_name,
            version=m.version,
            model_type=m.model_type,
            training_data_ref=m.training_data_ref,
            feature_definition=m.feature_definition,
            evaluation_metrics=m.evaluation_metrics,
            deployed_at=m.deployed_at,
            status=m.status,
        )
        for m in rows
    ]
    if not items:
        items = [
            ModelVersionItem(
                model_name="trend",
                version="phase20-rules-v1",
                model_type="deterministic",
                training_data_ref="public reports",
                feature_definition={"periods": ["7d", "30d", "90d", "year"]},
                evaluation_metrics=None,
                deployed_at=None,
                status="active",
            ),
            ModelVersionItem(
                model_name="anomaly-detection",
                version="phase20-iqr-v1",
                model_type="statistical",
                training_data_ref="public reports, cases, community activity",
                feature_definition={"method": "Tukey IQR x1.5", "min_baseline_points": 8},
                evaluation_metrics=None,
                deployed_at=None,
                status="active",
            ),
            ModelVersionItem(
                model_name="clustering",
                version="phase20-rules-v1",
                model_type="deterministic",
                training_data_ref="public reports",
                feature_definition={
                    "window_days": 30,
                    "min_reports": 3,
                    "similarity_threshold": 0.75,
                },
                evaluation_metrics=None,
                deployed_at=None,
                status="active",
            ),
            ModelVersionItem(
                model_name="forecasting",
                version="phase20-piecewise-exp-1",
                model_type="statistical",
                training_data_ref="public reports / status history",
                feature_definition={"method": "EMA + clamped drift", "min_history_weeks": 8},
                evaluation_metrics=None,
                deployed_at=None,
                status="active",
            ),
        ]
    return ModelRegistryResponse(models=items, generated_at=datetime.now(UTC))


def _report_read(r: IntelligenceReport) -> IntelligenceReportRead:
    return IntelligenceReportRead(
        id=r.id,
        title=r.title,
        scope=r.scope,
        geography_id=r.geography_id,
        filters=r.filters,
        status=r.status,
        format=r.format,
        generated_at=r.generated_at,
        methodology=r.methodology,
        dataset_versions=r.dataset_versions,
        model_versions=r.model_versions,
        created_at=r.created_at,
    )


@intelligence_router.get(
    "/reports",
    response_model=list[IntelligenceReportRead],
    dependencies=[Depends(_department_required)],
)
async def list_intelligence_reports(
    session: DbSession,
    limit: int = 50,
) -> list[IntelligenceReportRead]:
    rows = (
        (
            await session.execute(
                select(IntelligenceReport)
                .order_by(IntelligenceReport.created_at.desc())
                .limit(min(limit, 100))
            )
        )
        .scalars()
        .all()
    )
    return [_report_read(r) for r in rows]


@intelligence_router.post(
    "/reports",
    response_model=IntelligenceReportRead,
    status_code=201,
    dependencies=[Depends(_department_required)],
)
async def create_intelligence_report(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    payload: IntelligenceReportCreate,
) -> IntelligenceReportRead:
    report = IntelligenceReport(
        title=payload.title,
        scope=payload.scope,
        geography_id=payload.geography_id,
        filters=payload.filters,
        format=payload.format,
        status="pending",
        created_by=user.id,
    )
    session.add(report)
    await session.flush()
    await _schedule_intelligence_report(request, report.id)
    await session.commit()
    return _report_read(report)


async def _schedule_intelligence_report(request: Request, report_id: uuid.UUID) -> None:
    settings = request.app.state.settings
    if settings.celery_enabled:
        try:
            from tk_api.worker import celery_app as worker_app

            worker_app.send_task("tk_worker.generate_intelligence_report", args=[str(report_id)])
            return
        except Exception:
            pass

    from tk_api.intelligence.intel_reports import IntelligenceReportGenerator
    from tk_api.intelligence.models import IntelligenceReport
    from tk_api.media.storage import build_storage

    engine = request.app.state.engine
    storage = build_storage(settings)

    async def job() -> None:
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                report = await session.get(IntelligenceReport, report_id)
                if report is None:
                    return
                await IntelligenceReportGenerator().generate(
                    session,
                    report,
                    save_callback=lambda key, blob: storage.save_bytes("tk-exports", key, blob),
                )
                await session.commit()
        except Exception:
            logger.exception(
                "inline intelligence report generation failed",
                extra={"report_id": str(report_id)},
            )

    task = asyncio.create_task(job())
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


@intelligence_router.get(
    "/reports/{report_id}",
    response_model=IntelligenceReportDetail,
    dependencies=[Depends(_department_required)],
)
async def get_intelligence_report(
    session: DbSession,
    request: Request,
    report_id: uuid.UUID,
) -> IntelligenceReportDetail:
    report = await session.get(IntelligenceReport, report_id)
    if report is None:
        raise ApiError("intelligence report not found", 404, "report_not_found")
    detail = IntelligenceReportDetail(**vars(_report_read(report)))
    detail.content = report.content
    detail.error = report.error
    if detail.status == "ready" and report.file_key:
        try:
            from tk_api.media.storage import build_storage

            storage = build_storage(request.app.state.settings)
            detail.content = detail.content or {}
            detail.content["download_url"] = storage.download_url("tk-exports", report.file_key)
        except Exception:
            pass
    return detail
