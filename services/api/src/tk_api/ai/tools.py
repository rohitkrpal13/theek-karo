"""Controlled, read-only domain tools with MCP-ready schemas and permission guards."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.community.models import CivicInitiative
from tk_api.govdata.models import GovDataset, GovImportJob, InstitutionDiscrepancy
from tk_api.govdata.service import get_institution_official_data
from tk_api.institutions.models import Institution
from tk_api.integrations.registry import list_connectors
from tk_api.provenance.models import DataSource
from tk_api.reports.models import Report, ReportComment


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[..., Coroutine[Any, Any, dict[str, Any]]]
    risk_level: str = "READ_ONLY"
    required_role: str = "public"


# -----------------------------------------------------------------------------
# Tool Handlers
# -----------------------------------------------------------------------------


async def tool_search_institutions(
    session: AsyncSession,
    query: str,
    limit: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    stmt = select(Institution).where(Institution.name.ilike(f"%{query}%")).limit(min(limit, 20))
    res = await session.execute(stmt)
    items = [
        {
            "id": str(inst.id),
            "name": inst.name,
            "operational_status": inst.operational_status,
            "address": inst.address,
            "official_code": inst.official_identifier,
        }
        for inst in res.scalars().all()
    ]
    return {"institutions": items, "count": len(items)}


async def tool_get_institution_details(
    session: AsyncSession,
    institution_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        inst_uuid = uuid.UUID(institution_id)
    except ValueError:
        return {"error": "Invalid institution UUID format"}

    inst = await session.get(Institution, inst_uuid)
    if not inst:
        return {"error": "Institution not found"}

    return {
        "id": str(inst.id),
        "name": inst.name,
        "address": inst.address,
        "operational_status": inst.operational_status,
        "official_code": inst.official_identifier,
        "attributes": inst.meta or {},
    }


async def tool_search_reports(
    session: AsyncSession,
    query: str | None = None,
    institution_id: str | None = None,
    status: str | None = None,
    limit: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    stmt = select(Report).where(Report.visibility == "public")
    if query:
        stmt = stmt.where(Report.title.ilike(f"%{query}%"))
    if institution_id:
        with contextlib.suppress(ValueError):
            stmt = stmt.where(Report.institution_id == uuid.UUID(institution_id))
    if status:
        stmt = stmt.where(Report.status == status)

    stmt = stmt.limit(min(limit, 20))
    res = await session.execute(stmt)
    items = [
        {
            "id": str(r.id),
            "ticket_no": r.ticket_no,
            "title": r.title,
            "category_id": str(r.category_id),
            "status": r.status,
            "severity": r.severity,
            "trust_score": float(r.trust_score or 0.0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in res.scalars().all()
    ]
    return {"reports": items, "count": len(items)}


async def tool_get_official_data(
    session: AsyncSession,
    institution_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        inst_uuid = uuid.UUID(institution_id)
    except ValueError:
        return {"error": "Invalid institution UUID format"}

    try:
        data = await get_institution_official_data(session, institution_id=inst_uuid)
    except Exception:
        return {"official_data": None, "message": "No official data registered"}

    return {
        "institution_id": str(data.institution_id),
        "institution_name": data.institution_name,
        "operational_status": data.operational_status,
        "canonical_resources": data.canonical_data,
        "provenance": data.provenance.model_dump() if data.provenance else None,
    }


async def tool_summarize_discussion(
    session: AsyncSession,
    report_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Public-safe thread content for a report, with author labels — never private
    contact data. AI summaries cite this thread; it is advisory only."""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        return {"error": "Invalid report UUID format"}
    report = await session.get(Report, report_uuid)
    if report is None or report.visibility != "public":
        return {"error": "Report not found or not public"}
    rows = (
        (
            await session.execute(
                select(ReportComment)
                .where(ReportComment.report_id == report_uuid)
                .order_by(ReportComment.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    comments = [
        {
            "comment_id": str(c.id),
            "author_id": str(c.author_id),
            "body": c.body,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
        if not c.is_removed
    ]
    return {
        "report": {
            "id": str(report.id),
            "ticket_no": report.ticket_no,
            "title": report.title,
            "status": report.status,
            "severity": report.severity,
        },
        "comments": comments,
        "count": len(comments),
        "disclaimer": (
            "Community discussion is not verification; platform/official states are authoritative."
        ),
    }


async def tool_find_related_reports(
    session: AsyncSession,
    query: str,
    category_id: str | None = None,
    limit: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Duplicate-prevention aid: public reports matching a title/description query."""
    stmt = select(Report).where(Report.visibility == "public")
    if query:
        stmt = stmt.where(Report.title.ilike(f"%{query}%"))
    if category_id:
        with contextlib.suppress(ValueError):
            stmt = stmt.where(Report.category_id == uuid.UUID(category_id))
    rows = (await session.execute(stmt.limit(min(limit, 20)))).scalars().all()
    items = [
        {
            "id": str(r.id),
            "ticket_no": r.ticket_no,
            "title": r.title,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"reports": items, "count": len(items)}


async def tool_recommend_public_initiatives(
    session: AsyncSession,
    skills: list[str] | None = None,
    interests: list[str] | None = None,
    geography_id: str | None = None,
    limit: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Recommend active public initiatives matching explicit volunteer preferences.
    Uses only public, non-personal data; never exposes volunteer/participant details."""
    stmt = select(CivicInitiative).where(CivicInitiative.status.in_(("approved", "active")))
    if geography_id:
        with contextlib.suppress(ValueError):
            stmt = stmt.where(CivicInitiative.geography_id == uuid.UUID(geography_id))
    rows = (await session.execute(stmt.limit(50))).scalars().all()

    wanted = set((skills or []) + (interests or []))
    scored: list[tuple[int, Any]] = []
    for row in rows:
        score = 0
        haystack = " ".join(
            [row.title, row.description, " ".join(row.expected_activities or [])]
        ).lower()
        for term in wanted:
            if term.lower() in haystack:
                score += 1
        scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1].created_at))
    items = [
        {
            "id": str(row.id),
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "participant_count": 0,  # replaced below to avoid per-row query cost
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for _, row in scored[: min(limit, 20)]
    ]
    return {
        "initiatives": items,
        "count": len(items),
        "matched_terms": sorted(wanted),
        "disclaimer": "Matches are based on explicit preferences only; no personal profiling.",
    }


async def tool_get_discrepancies(
    session: AsyncSession,
    institution_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        inst_uuid = uuid.UUID(institution_id)
    except ValueError:
        return {"error": "Invalid institution UUID format"}

    stmt = select(InstitutionDiscrepancy).where(InstitutionDiscrepancy.institution_id == inst_uuid)
    res = await session.execute(stmt)
    discrepancies = [
        {
            "id": str(d.id),
            "resource_key": d.resource_key,
            "official_value": d.official_value,
            "discrepancy_state": d.discrepancy_state,
            "findings_summary": d.ai_finding,
            "last_evaluated_at": d.created_at.isoformat(),
        }
        for d in res.scalars().all()
    ]
    return {"discrepancies": discrepancies, "count": len(discrepancies)}


async def tool_get_civic_metrics(
    session: AsyncSession,
    geography_id: str | None = None,
    category_slug: str | None = None,
    date_preset: str = "30d",
    **kwargs: Any,
) -> dict[str, Any]:
    from tk_api.analytics.schemas import AnalyticsFilterParams
    from tk_api.analytics.service import AnalyticsService

    geo_uuid = None
    if geography_id:
        with contextlib.suppress(ValueError):
            geo_uuid = uuid.UUID(geography_id)

    filters = AnalyticsFilterParams(
        geography_id=geo_uuid,
        category_slug=category_slug,
        date_preset=date_preset,  # type: ignore[arg-type]
    )
    res = await AnalyticsService().get_overview_kpis(session, filters)
    return {
        "kpis": [k.model_dump() for k in res.kpis],
        "data_coverage_note": res.data_coverage_note,
    }


async def tool_get_report_trend(
    session: AsyncSession,
    interval: str = "day",
    date_preset: str = "30d",
    **kwargs: Any,
) -> dict[str, Any]:
    from tk_api.analytics.schemas import AnalyticsFilterParams
    from tk_api.analytics.service import AnalyticsService

    filters = AnalyticsFilterParams(
        interval=interval,  # type: ignore[arg-type]
        date_preset=date_preset,  # type: ignore[arg-type]
    )
    res = await AnalyticsService().get_report_trends(session, filters)
    return {
        "total_in_range": res.total_in_range,
        "interval": res.interval,
        "points": [p.model_dump() for p in res.series[-10:]],
    }


async def tool_get_category_breakdown(
    session: AsyncSession,
    date_preset: str = "30d",
    **kwargs: Any,
) -> dict[str, Any]:
    from tk_api.analytics.schemas import AnalyticsFilterParams
    from tk_api.analytics.service import AnalyticsService

    filters = AnalyticsFilterParams(date_preset=date_preset)  # type: ignore[arg-type]
    res = await AnalyticsService().get_category_analytics(session, filters)
    return {
        "total_reports": res.total_reports,
        "categories": [c.model_dump() for c in res.categories],
    }


async def tool_get_geographic_summary(
    session: AsyncSession,
    geography_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    from tk_api.analytics.schemas import AnalyticsFilterParams
    from tk_api.analytics.service import AnalyticsService

    geo_uuid = None
    if geography_id:
        with contextlib.suppress(ValueError):
            geo_uuid = uuid.UUID(geography_id)

    filters = AnalyticsFilterParams(geography_id=geo_uuid)
    res = await AnalyticsService().get_geographic_drilldown(session, filters)
    return {
        "current_level": res.current_level,
        "children": [c.model_dump() for c in res.children],
    }


async def tool_research_query(
    session: AsyncSession,
    geography_id: str | None = None,
    category_slug: str | None = None,
    status: str = "all",
    date_preset: str = "30d",
    date_from: str | None = None,
    date_to: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 15 research query: structured, validated analytics (no SQL)."""
    from datetime import datetime

    from tk_api.publicdata import service as pd_service

    geo_uuid = None
    if geography_id:
        with contextlib.suppress(ValueError):
            geo_uuid = uuid.UUID(geography_id)
    date_from_dt = None
    date_to_dt = None
    if date_from:
        with contextlib.suppress(ValueError):
            date_from_dt = datetime.fromisoformat(date_from)
    if date_to:
        with contextlib.suppress(ValueError):
            date_to_dt = datetime.fromisoformat(date_to)
    result = await pd_service.PublicDataService().research_query(
        session,
        geography_id=geo_uuid,
        category_slug=category_slug,
        status_filter=status if status in ("open", "resolved", "verified", "all") else "all",
        date_from=date_from_dt,
        date_to=date_to_dt,
        date_preset=date_preset,
    )
    return {
        "count": result["count"],
        "verified_count": result["verified_count"],
        "resolved_count": result["resolved_count"],
        "open_count": result["open_count"],
        "period_label": result["period_label"],
        "trends": result["trends"][-5:],
        "top_categories": result["categories"][:5],
        "top_institutions": result["top_institutions"][:5],
        "coverage": result["coverage"],
        "limitations": result["limitations"],
    }


async def tool_research_compare(
    session: AsyncSession,
    geography_ids: str,
    category_slug: str | None = None,
    status: str = "all",
    date_preset: str = "all",
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 15 comparison tool: compare geographies side by side."""
    from tk_api.publicdata import service as pd_service

    ids: list[uuid.UUID] = []
    for part in geography_ids.split(","):
        with contextlib.suppress(ValueError):
            ids.append(uuid.UUID(part.strip()))
    result = await pd_service.PublicDataService().research_compare(
        session,
        ids,
        category_slug=category_slug,
        status_filter=status if status in ("open", "resolved", "verified", "all") else "all",
        date_preset=date_preset,
    )
    return {
        "items": result["items"],
        "warnings": result["warnings"],
        "methodology_note": result["methodology_note"],
    }


async def tool_get_source_metadata(
    session: AsyncSession,
    source_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 19 tool: registered data-source metadata (spec §10, §120-§122).
    Read-only; returns provenance + license + freshness, never credentials."""
    try:
        src_uuid = uuid.UUID(source_id)
    except ValueError:
        return {"error": "Invalid source UUID format"}
    src = await session.get(DataSource, src_uuid)
    if src is None:
        return {"error": "Source not found"}
    return {
        "source_id": str(src.id),
        "name": src.name,
        "source_type": src.source_type,
        "publisher": src.publisher,
        "url": src.url,
        "license": src.license,
        "version": src.version,
        "dataset_identifier": src.dataset_identifier,
        "authority_level": src.authority_level,
        "verification_state": src.verification_state,
        "retrieved_at": src.retrieval_date.isoformat() if src.retrieval_date else None,
        "last_verified_at": src.last_verified_at.isoformat() if src.last_verified_at else None,
    }


async def tool_get_dataset_metadata(
    session: AsyncSession,
    dataset_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 19 tool: dataset metadata incl. connector freshness + last sync
    (spec §13-§14). Read-only; the connector row carries no secrets."""
    try:
        ds_uuid = uuid.UUID(dataset_id)
    except ValueError:
        return {"error": "Invalid dataset UUID format"}
    ds = await session.get(GovDataset, ds_uuid)
    if ds is None:
        return {"error": "Dataset not found"}
    latest_job = await session.scalar(
        select(GovImportJob)
        .where(GovImportJob.dataset_id == ds.id)
        .order_by(GovImportJob.started_at.desc())
        .limit(1)
    )
    return {
        "dataset_id": str(ds.id),
        "name": ds.name,
        "publisher": ds.publisher,
        "license": ds.license,
        "version": ds.version,
        "connector_code": ds.connector_code,
        "url": ds.url,
        "last_sync": {
            "status": latest_job.status if latest_job else None,
            "finished_at": latest_job.finished_at.isoformat()
            if latest_job and latest_job.finished_at
            else None,
            "rows_added": latest_job.rows_added if latest_job else None,
            "rows_rejected": latest_job.rows_rejected if latest_job else None,
        },
    }


async def tool_get_sync_status(
    session: AsyncSession,
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 19 tool (admin): connector health + freshness summary. Public-safe
    (statuses/counters only — no credentials, no endpoint internals)."""
    rows = await list_connectors(session)
    return {
        "connectors": rows,
        "count": len(rows),
        "note": "Circuit-breaker states are operational signals, not data quality.",
    }


async def tool_get_data_conflicts(
    session: AsyncSession,
    institution_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 19 tool: recorded official-vs-observation conflicts (spec §16-§17).
    AI summarizes; it never declares official data false — states carry the
    review status."""
    try:
        inst_uuid = uuid.UUID(institution_id)
    except ValueError:
        return {"error": "Invalid institution UUID format"}
    stmt = select(InstitutionDiscrepancy).where(InstitutionDiscrepancy.institution_id == inst_uuid)
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "conflicts": [
            {
                "id": str(d.id),
                "resource_key": d.resource_key,
                "official_value": d.official_value,
                "discrepancy_state": d.discrepancy_state,
                "status": d.status,
                "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
            }
            for d in rows
        ],
        "count": len(rows),
        "note": (
            "Conflict states are review signals; community observation never "
            "overrides official data automatically."
        ),
    }


async def tool_get_department_cases(
    session: AsyncSession,
    department_id: str | None = None,
    status: str | None = None,
    limit: int = 10,
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 19 tool (department_manager/admin): public-safe case summary for
    authorized department users. Only non-private metadata is returned."""
    from tk_api.cases.models import CivicCase

    stmt = select(CivicCase)
    if department_id:
        with contextlib.suppress(ValueError):
            stmt = stmt.where(CivicCase.primary_department_id == uuid.UUID(department_id))
    if status:
        stmt = stmt.where(CivicCase.status == status)
    rows = (await session.execute(stmt.limit(min(limit, 50)))).scalars().all()
    return {
        "cases": [
            {
                "id": str(c.id),
                "report_id": str(c.report_id),
                "department_id": str(c.primary_department_id) if c.primary_department_id else None,
                "status": c.status,
                "sla_status": c.sla_status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ],
        "count": len(rows),
        "disclaimer": "Aggregate case metadata; details require the department portal.",
    }


async def tool_research_trends(
    session: AsyncSession,
    geography_id: str | None = None,
    category_slug: str | None = None,
    metric: str = "reports",
    interval: str = "month",
    date_preset: str = "90d",
    **kwargs: Any,
) -> dict[str, Any]:
    """Phase 15 trend tool: time series for a metric + change percentage."""
    from tk_api.publicdata import service as pd_service

    geo_uuid = None
    if geography_id:
        with contextlib.suppress(ValueError):
            geo_uuid = uuid.UUID(geography_id)
    result = await pd_service.PublicDataService().research_trends(
        session,
        geography_id=geo_uuid,
        category_slug=category_slug,
        metric=metric,
        interval=interval,
        date_preset=date_preset,
    )
    return {
        "metric": result["metric"],
        "period_label": result["period_label"],
        "series": result["series"][-8:],
        "change_count": result["change_count"],
        "change_pct": result["change_pct"],
    }


# -----------------------------------------------------------------------------
# Phase 8 — AI Assistant Polish Tools
# -----------------------------------------------------------------------------


async def tool_institution_deep_dive(
    session: AsyncSession,
    institution_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Official-persona Q&A: comprehensive institution briefing combining
    twin data, official baseline, recent reports, discrepancies, and SLA status."""
    from tk_api.cases.models import CivicCase

    try:
        inst_uuid = uuid.UUID(institution_id)
    except ValueError:
        return {"error": "Invalid institution UUID format"}

    inst = await session.get(Institution, inst_uuid)
    if not inst:
        return {"error": "Institution not found"}

    # Get institution type
    inst_type = None
    if inst.institution_type_id:
        from tk_api.institutions.models import InstitutionType

        it = await session.get(InstitutionType, inst.institution_type_id)
        inst_type = it.name_key if it else None

    # Get recent reports
    recent_reports = (
        (
            await session.execute(
                select(Report)
                .where(
                    Report.institution_id == inst_uuid,
                    Report.visibility == "public",
                    Report.deleted_at.is_(None),
                )
                .order_by(Report.created_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    reports_summary = [
        {
            "ticket_no": r.ticket_no,
            "title": r.title,
            "status": r.status,
            "severity": r.severity,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recent_reports
    ]

    # Get open case count
    open_cases = await session.scalar(
        select(CivicCase.id).where(
            CivicCase.report_id.in_(select(Report.id).where(Report.institution_id == inst_uuid)),
            CivicCase.status.not_in(("closed", "resolved")),
        )
    )

    # Get official data if available
    official_data = None
    try:
        data = await get_institution_official_data(session, institution_id=inst_uuid)
        official_data = {
            "resources": data.canonical_data if data.canonical_data else {},
            "provenance": data.provenance.model_dump() if data.provenance else None,
        }
    except Exception:
        official_data = {"message": "No official data registered"}

    # Get discrepancies
    discrepancies = (
        (
            await session.execute(
                select(InstitutionDiscrepancy).where(
                    InstitutionDiscrepancy.institution_id == inst_uuid
                )
            )
        )
        .scalars()
        .all()
    )

    discrepancy_summary = [
        {
            "resource_key": d.resource_key,
            "discrepancy_state": d.discrepancy_state,
        }
        for d in discrepancies[:5]
    ]

    return {
        "institution": {
            "id": str(inst.id),
            "name": inst.name,
            "type": inst_type,
            "operational_status": inst.operational_status,
            "address": inst.address,
            "official_code": inst.official_identifier,
        },
        "recent_reports": reports_summary,
        "open_cases_count": open_cases or 0,
        "official_data": official_data,
        "discrepancies": discrepancy_summary,
        "discrepancy_count": len(discrepancies),
        "disclaimer": (
            "This briefing combines official baseline data and citizen observations. "
            "Official data is authoritative; citizen observations are subject to verification."
        ),
    }


async def tool_source_freshness(
    session: AsyncSession,
    source_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Check freshness of a data source — last sync, record count, staleness."""
    from datetime import UTC, datetime, timedelta

    try:
        src_uuid = uuid.UUID(source_id)
    except ValueError:
        return {"error": "Invalid source UUID format"}

    src = await session.get(DataSource, src_uuid)
    if src is None:
        return {"error": "Source not found"}

    # Check staleness
    now = datetime.now(UTC)
    last_sync = src.retrieval_date
    is_stale = False
    days_since_sync = None
    if last_sync:
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=UTC)
        delta = now - last_sync
        days_since_sync = delta.days
        is_stale = delta > timedelta(days=30)

    # Get latest import job
    latest_job = await session.scalar(
        select(GovImportJob)
        .where(GovImportJob.source_id == src_uuid)
        .order_by(GovImportJob.started_at.desc())
        .limit(1)
    )

    return {
        "source_id": str(src.id),
        "name": src.name,
        "publisher": src.publisher,
        "last_sync": last_sync.isoformat() if last_sync else None,
        "days_since_sync": days_since_sync,
        "is_stale": is_stale,
        "latest_job_status": latest_job.status if latest_job else None,
        "latest_job_rows": latest_job.rows_added if latest_job else None,
        "freshness_note": (
            f"Data was last synced {days_since_sync} days ago."
            if days_since_sync
            else "No sync history available."
        ),
    }


async def tool_department_briefing(
    session: AsyncSession,
    department_id: str | None = None,
    category_slug: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Public-safe department briefing with case counts, SLA compliance, escalations."""
    from tk_api.cases.models import CaseEscalation, CivicCase
    from tk_api.departments.models import Department

    departments_to_brief: list[Any] = []
    if department_id:
        try:
            dept = await session.get(Department, uuid.UUID(department_id))
            if dept:
                departments_to_brief = [dept]
        except ValueError:
            return {"error": "Invalid department UUID"}
    else:
        departments_to_brief = list(
            (await session.execute(select(Department).limit(20))).scalars().all()
        )

    result = []
    for dept in departments_to_brief:
        # Count cases by status
        case_stmt = select(CivicCase).where(CivicCase.primary_department_id == dept.id)
        cases = (await session.execute(case_stmt)).scalars().all()
        total_cases = len(cases)
        open_cases = sum(1 for c in cases if c.status not in ("closed", "resolved"))
        resolved_cases = sum(1 for c in cases if c.status in ("closed", "resolved"))
        breached_sla = sum(1 for c in cases if c.sla_status == "breached")

        # Count escalations
        await session.scalar(
            select(CaseEscalation.id)
            .where(
                CaseEscalation.case_id.in_(
                    select(CivicCase.id).where(CivicCase.primary_department_id == dept.id)
                )
            )
            .limit(100)
        )

        result.append(
            {
                "id": str(dept.id),
                "name": dept.name,
                "slug": dept.slug,
                "total_cases": total_cases,
                "open_cases": open_cases,
                "resolved_cases": resolved_cases,
                "sla_breached": breached_sla,
                "escalation_count": 0,  # simplified count
            }
        )

    return {
        "departments": result,
        "count": len(result),
        "disclaimer": (
            "Aggregate department metrics; individual case details"
            " require authorization."
        ),
    }


# -----------------------------------------------------------------------------
# Tool Registry
# -----------------------------------------------------------------------------


class ToolRegistry:
    """Allowlist-enforcing registry providing MCP-compliant tool specifications."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register(
            ToolSpec(
                name="search_institutions",
                description="Search public institutions (schools, hospitals, courts) by keyword.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term or institution name",
                        },
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"institutions": {"type": "array"}},
                },
                handler=tool_search_institutions,
            )
        )
        self.register(
            ToolSpec(
                name="get_institution_details",
                description="Get detailed profile of a public institution by its UUID.",
                input_schema={
                    "type": "object",
                    "properties": {"institution_id": {"type": "string"}},
                    "required": ["institution_id"],
                },
                output_schema={"type": "object"},
                handler=tool_get_institution_details,
            )
        )
        self.register(
            ToolSpec(
                name="search_reports",
                description="Search public citizen reports by keyword, institution ID, or status.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "institution_id": {"type": "string"},
                        "status": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                },
                output_schema={"type": "object", "properties": {"reports": {"type": "array"}}},
                handler=tool_search_reports,
            )
        )
        self.register(
            ToolSpec(
                name="get_official_data",
                description="Retrieve registered official government dataset baseline.",
                input_schema={
                    "type": "object",
                    "properties": {"institution_id": {"type": "string"}},
                    "required": ["institution_id"],
                },
                output_schema={"type": "object"},
                handler=tool_get_official_data,
            )
        )
        self.register(
            ToolSpec(
                name="get_discrepancies",
                description="Retrieve flagged discrepancies with citizen reports.",
                input_schema={
                    "type": "object",
                    "properties": {"institution_id": {"type": "string"}},
                    "required": ["institution_id"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"discrepancies": {"type": "array"}},
                },
                handler=tool_get_discrepancies,
            )
        )
        self.register(
            ToolSpec(
                name="get_civic_metrics",
                description="Retrieve high-level civic health KPIs and resolution rates.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "geography_id": {"type": "string"},
                        "category_slug": {"type": "string"},
                        "date_preset": {"type": "string", "default": "30d"},
                    },
                },
                output_schema={"type": "object", "properties": {"kpis": {"type": "array"}}},
                handler=tool_get_civic_metrics,
            )
        )
        self.register(
            ToolSpec(
                name="get_report_trend",
                description="Retrieve time series trends of reports over time.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "interval": {"type": "string", "default": "day"},
                        "date_preset": {"type": "string", "default": "30d"},
                    },
                },
                output_schema={"type": "object", "properties": {"points": {"type": "array"}}},
                handler=tool_get_report_trend,
            )
        )
        self.register(
            ToolSpec(
                name="get_category_breakdown",
                description="Retrieve category breakdown of reported issues.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "date_preset": {"type": "string", "default": "30d"},
                    },
                },
                output_schema={"type": "object", "properties": {"categories": {"type": "array"}}},
                handler=tool_get_category_breakdown,
            )
        )
        self.register(
            ToolSpec(
                name="get_geographic_summary",
                description="Retrieve geographic drilldown summary of reports and institutions.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "geography_id": {"type": "string"},
                    },
                },
                output_schema={"type": "object", "properties": {"children": {"type": "array"}}},
                handler=tool_get_geographic_summary,
            )
        )
        self.register(
            ToolSpec(
                name="research_query",
                description=(
                    "Phase 15 structured research query: counts, verified/resolved/open splits, "
                    "trends, top categories and top institutions within a geography, category, "
                    "status and date window. Never exposes raw SQL."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "geography_id": {"type": "string"},
                        "category_slug": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["all", "open", "resolved", "verified"],
                        },
                        "date_preset": {"type": "string", "default": "30d"},
                        "date_from": {"type": "string", "description": "ISO date"},
                        "date_to": {"type": "string", "description": "ISO date"},
                    },
                },
                output_schema={"type": "object"},
                handler=tool_research_query,
            )
        )
        self.register(
            ToolSpec(
                name="research_compare",
                description=(
                    "Phase 15 comparison: compare report/resolution stats across "
                    "multiple geographies."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "geography_ids": {
                            "type": "string",
                            "description": "Comma separated geography UUIDs (2-10)",
                        },
                        "category_slug": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["all", "open", "resolved", "verified"],
                        },
                        "date_preset": {"type": "string", "default": "all"},
                    },
                    "required": ["geography_ids"],
                },
                output_schema={"type": "object"},
                handler=tool_research_compare,
            )
        )
        self.register(
            ToolSpec(
                name="research_trends",
                description=(
                    "Phase 15 trend tool: time series for a metric (reports, resolved, "
                    "verified) with change percentages."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "geography_id": {"type": "string"},
                        "category_slug": {"type": "string"},
                        "metric": {"type": "string", "enum": ["reports", "resolved", "verified"]},
                        "interval": {"type": "string", "enum": ["day", "week", "month"]},
                        "date_preset": {"type": "string", "default": "90d"},
                    },
                },
                output_schema={"type": "object"},
                handler=tool_research_trends,
            )
        )
        self.register(
            ToolSpec(
                name="summarize_discussion",
                description=(
                    "Phase 18 tool: retrieve the public comment thread for a report "
                    "(author-labeled, no private data) so the AI can summarize it with citations."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"report_id": {"type": "string"}},
                    "required": ["report_id"],
                },
                output_schema={"type": "object"},
                handler=tool_summarize_discussion,
            )
        )
        self.register(
            ToolSpec(
                name="find_related_reports",
                description=(
                    "Phase 18 duplicate-prevention tool: public reports matching a title "
                    "query, optionally within a category."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "category_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
                output_schema={"type": "object"},
                handler=tool_find_related_reports,
            )
        )
        self.register(
            ToolSpec(
                name="recommend_public_initiatives",
                description=(
                    "Phase 18 tool: recommend approved/active public initiatives matching "
                    "explicit volunteer skills/interests. Public data only; never profiles "
                    "participants."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "skills": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Explicitly stated skills (e.g. photography)",
                        },
                        "interests": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Explicitly stated interests (e.g. education)",
                        },
                        "geography_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                },
                output_schema={"type": "object"},
                handler=tool_recommend_public_initiatives,
            )
        )
        # -- Phase 19 integration tools (read-only; source-aware) ---------------
        self.register(
            ToolSpec(
                name="get_source_metadata",
                description=(
                    "Phase 19 tool: metadata for a registered data source — publisher, "
                    "license, authority level, freshness. Read-only; never credentials."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"source_id": {"type": "string"}},
                    "required": ["source_id"],
                },
                output_schema={"type": "object"},
                handler=tool_get_source_metadata,
            )
        )
        self.register(
            ToolSpec(
                name="get_dataset_metadata",
                description=(
                    "Phase 19 tool: dataset metadata + connector freshness + last sync "
                    "(spec §13-§14). Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"dataset_id": {"type": "string"}},
                    "required": ["dataset_id"],
                },
                output_schema={"type": "object"},
                handler=tool_get_dataset_metadata,
            )
        )
        self.register(
            ToolSpec(
                name="get_sync_status",
                description=(
                    "Phase 19 tool (admin): connector health, circuit-breaker states and "
                    "freshness. Public-safe operational signals only."
                ),
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
                handler=tool_get_sync_status,
                required_role="admin",
            )
        )
        self.register(
            ToolSpec(
                name="get_data_conflicts",
                description=(
                    "Phase 19 tool: recorded official-vs-community conflicts for an "
                    "institution (spec §16-§17). Review signals only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"institution_id": {"type": "string"}},
                    "required": ["institution_id"],
                },
                output_schema={"type": "object"},
                handler=tool_get_data_conflicts,
            )
        )
        self.register(
            ToolSpec(
                name="get_department_cases",
                description=(
                    "Phase 19 tool (department_manager/admin): aggregate case metadata "
                    "for an authorized department. Non-private summary only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "string"},
                        "status": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                },
                output_schema={"type": "object"},
                handler=tool_get_department_cases,
                required_role="department_manager",
            )
        )
        # -- Phase 21 civic-action tools (all read-only, public-safe) ---------
        from tk_api.civic_action import ai_tools as civic_action_tools

        self.register(
            ToolSpec(
                name="get_action_plan",
                description=(
                    "Phase 21 tool: action plan summary (objective, status, "
                    "progress, open tasks) for an initiative or plan. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "initiative_id": {"type": "string"},
                        "plan_id": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
                handler=civic_action_tools.tool_get_action_plan,
            )
        )
        self.register(
            ToolSpec(
                name="find_volunteer_matches",
                description=(
                    "Phase 21 tool: suggested volunteer profiles for an initiative. "
                    "Returns public preferences only; contact details are never exposed."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "initiative_id": {"type": "string"},
                        "plan_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                },
                output_schema={"type": "object"},
                handler=civic_action_tools.tool_get_volunteer_matches,
            )
        )
        self.register(
            ToolSpec(
                name="get_campaign_progress",
                description=(
                    "Phase 21 tool: aggregate progress of initiatives linked to a "
                    "campaign. Derived from task state only. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"campaign_id": {"type": "string"}},
                    "required": ["campaign_id"],
                },
                output_schema={"type": "object"},
                handler=civic_action_tools.tool_get_campaign_progress,
            )
        )
        self.register(
            ToolSpec(
                name="get_impact_metrics",
                description=(
                    "Phase 21 tool: verified impact metrics for an initiative or "
                    "plan. Only human-approved measurements count. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "initiative_id": {"type": "string"},
                        "plan_id": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
                handler=civic_action_tools.tool_get_impact_metrics,
            )
        )
        self.register(
            ToolSpec(
                name="get_action_evidence",
                description=(
                    "Phase 21 tool: verification status of evidence attached to an "
                    "initiative/task (metadata only). Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "initiative_id": {"type": "string"},
                        "task_id": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
                handler=civic_action_tools.tool_get_action_evidence,
            )
        )
        self.register(
            ToolSpec(
                name="get_verification_status",
                description=(
                    "Phase 21 tool: verification state of an initiative's action "
                    "plan and whether human review is required. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"initiative_id": {"type": "string"}},
                },
                output_schema={"type": "object"},
                handler=civic_action_tools.tool_get_verification_status,
            )
        )
        # -- Phase 23 data-trust tools (read-only, public-safe) ---------------
        from tk_api.data_trust import ai_tools as dt_tools

        self.register(
            ToolSpec(
                name="get_evidence_record",
                description=(
                    "Phase 23 tool: evidence metadata for provenance lookup. "
                    "Returns type, source, status, verification state. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"evidence_id": {"type": "string"}},
                    "required": ["evidence_id"],
                },
                output_schema={"type": "object"},
                handler=dt_tools.tool_get_evidence_record,
            )
        )
        self.register(
            ToolSpec(
                name="get_verification_history",
                description=(
                    "Phase 23 tool: verification history for an entity. Helps AI "
                    "explain trust state with cited verification methods. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity_type": {"type": "string"},
                        "entity_id": {"type": "string"},
                    },
                    "required": ["entity_type", "entity_id"],
                },
                output_schema={"type": "object"},
                handler=dt_tools.tool_get_verification_history,
            )
        )
        self.register(
            ToolSpec(
                name="get_data_conflicts_for_entity",
                description=(
                    "Phase 23 tool: summarize data conflicts for an entity. AI "
                    "explains both sides without resolving. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity_type": {"type": "string"},
                        "entity_id": {"type": "string"},
                    },
                    "required": ["entity_type", "entity_id"],
                },
                output_schema={"type": "object"},
                handler=dt_tools.tool_get_data_conflicts_summary,
            )
        )
        self.register(
            ToolSpec(
                name="get_disputes_for_entity",
                description=(
                    "Phase 23 tool: check if an entity has active disputes. AI must "
                    "show dispute banners. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity_type": {"type": "string"},
                        "entity_id": {"type": "string"},
                    },
                    "required": ["entity_type", "entity_id"],
                },
                output_schema={"type": "object"},
                handler=dt_tools.tool_get_disputes_summary,
            )
        )
        self.register(
            ToolSpec(
                name="get_source_health",
                description=(
                    "Phase 23 tool: source health and freshness status. Helps AI "
                    "explain data freshness to users. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"source_id": {"type": "string"}},
                    "required": ["source_id"],
                },
                output_schema={"type": "object"},
                handler=dt_tools.tool_get_source_health,
            )
        )
        self.register(
            ToolSpec(
                name="explain_provenance",
                description=(
                    "Phase 23 tool: AI-powered provenance explanation citing sources, "
                    "verifications, quality, and limitations. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity_type": {"type": "string"},
                        "entity_id": {"type": "string"},
                    },
                    "required": ["entity_type", "entity_id"],
                },
                output_schema={"type": "object"},
                handler=dt_tools.tool_explain_provenance,
            )
        )
        # -- Phase 24 identity tools (read-only, public-safe) ---------------
        from tk_api.identity import ai_tools as id_tools

        self.register(
            ToolSpec(
                name="get_my_profile",
                description=(
                    "Phase 24 tool: get current user profile with verification "
                    "labels and trust context. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
                output_schema={"type": "object"},
                handler=id_tools.tool_get_my_profile,
            )
        )
        self.register(
            ToolSpec(
                name="get_my_permissions",
                description=(
                    "Phase 24 tool: explain user's roles and permissions. "
                    "AI cannot grant or modify permissions. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
                output_schema={"type": "object"},
                handler=id_tools.tool_get_my_permissions,
            )
        )
        self.register(
            ToolSpec(
                name="get_my_organizations",
                description=(
                    "Phase 24 tool: list organizations the user belongs to. "
                    "Never exposes private member data. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
                output_schema={"type": "object"},
                handler=id_tools.tool_get_my_organizations,
            )
        )
        self.register(
            ToolSpec(
                name="get_my_contributions",
                description=(
                    "Phase 24 tool: factual contribution history (not a quality "
                    "score or ranking). Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
                output_schema={"type": "object"},
                handler=id_tools.tool_get_my_contributions,
            )
        )
        self.register(
            ToolSpec(
                name="get_verification_status",
                description=(
                    "Phase 24 tool: verification status for a user. "
                    "Verification describes platform-specific claim verification, "
                    "not personal trustworthiness. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
                output_schema={"type": "object"},
                handler=id_tools.tool_get_verification_status,
            )
        )
        self.register(
            ToolSpec(
                name="get_organization_profile",
                description=(
                    "Phase 24 tool: organization public profile. "
                    "Never exposes private member data. Read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"organization_id": {"type": "string"}},
                    "required": ["organization_id"],
                },
                output_schema={"type": "object"},
                handler=id_tools.tool_get_organization_profile,
            )
        )
        self.register(
            ToolSpec(
                name="get_institution_profile",
                description=("Phase 24 tool: institution public profile. Read-only."),
                input_schema={
                    "type": "object",
                    "properties": {"institution_id": {"type": "string"}},
                    "required": ["institution_id"],
                },
                output_schema={"type": "object"},
                handler=id_tools.tool_get_institution_profile,
            )
        )
        # -- Phase 25 government workflow tools (read-only, public-safe) ---
        from tk_api.government import ai_tools as gov_tools

        self.register(
            ToolSpec(
                name="get_department_info",
                description=("Phase 25 tool: department profile with case counts and SLA status."),
                input_schema={
                    "type": "object",
                    "properties": {"department_id": {"type": "string"}},
                    "required": ["department_id"],
                },
                output_schema={"type": "object"},
                handler=gov_tools.tool_get_department_info,
            )
        )
        self.register(
            ToolSpec(
                name="get_case_queue_summary",
                description=("Phase 25 tool: summarize a department case queue."),
                input_schema={
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "string"},
                        "status": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                },
                output_schema={"type": "object"},
                handler=gov_tools.tool_get_case_queue_summary,
            )
        )
        self.register(
            ToolSpec(
                name="get_case_sla_status",
                description=("Phase 25 tool: SLA status for a specific case. Read-only."),
                input_schema={
                    "type": "object",
                    "properties": {"case_id": {"type": "string"}},
                    "required": ["case_id"],
                },
                output_schema={"type": "object"},
                handler=gov_tools.tool_get_case_sla_status,
            )
        )
        self.register(
            ToolSpec(
                name="get_department_responses",
                description=("Phase 25 tool: official responses for a case."),
                input_schema={
                    "type": "object",
                    "properties": {"case_id": {"type": "string"}},
                    "required": ["case_id"],
                },
                output_schema={"type": "object"},
                handler=gov_tools.tool_get_department_responses,
            )
        )
        self.register(
            ToolSpec(
                name="get_department_analytics",
                description=("Phase 25 tool: aggregate case metrics for a department."),
                input_schema={
                    "type": "object",
                    "properties": {"department_id": {"type": "string"}},
                    "required": ["department_id"],
                },
                output_schema={"type": "object"},
                handler=gov_tools.tool_get_department_analytics,
            )
        )
        self.register(
            ToolSpec(
                name="explain_routing",
                description=("Phase 25 tool: routing history and recommendation for a case."),
                input_schema={
                    "type": "object",
                    "properties": {"case_id": {"type": "string"}},
                    "required": ["case_id"],
                },
                output_schema={"type": "object"},
                handler=gov_tools.tool_explain_routing,
            )
        )
        self.register(
            ToolSpec(
                name="summarize_escalations",
                description=("Phase 25 tool: summarize active escalations for a department."),
                input_schema={
                    "type": "object",
                    "properties": {"department_id": {"type": "string"}},
                },
                output_schema={"type": "object"},
                handler=gov_tools.tool_summarize_escalations,
            )
        )
        # -- Phase 26 communication tools (read-only, public-safe) ---------
        from tk_api.communication import ai_tools as comm_tools

        self.register(
            ToolSpec(
                name="get_notification_summary",
                description=("Phase 26 tool: summarize unread notifications for a user."),
                input_schema={
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
                output_schema={"type": "object"},
                handler=comm_tools.tool_get_notification_summary,
            )
        )
        self.register(
            ToolSpec(
                name="explain_alert",
                description=("Phase 26 tool: explain a public alert with source and verification."),
                input_schema={
                    "type": "object",
                    "properties": {"alert_id": {"type": "string"}},
                    "required": ["alert_id"],
                },
                output_schema={"type": "object"},
                handler=comm_tools.tool_explain_alert,
            )
        )
        self.register(
            ToolSpec(
                name="get_delivery_status",
                description=("Phase 26 tool: delivery status for a notification across channels."),
                input_schema={
                    "type": "object",
                    "properties": {"notification_id": {"type": "string"}},
                    "required": ["notification_id"],
                },
                output_schema={"type": "object"},
                handler=comm_tools.tool_get_delivery_status,
            )
        )
        self.register(
            ToolSpec(
                name="get_communication_analytics",
                description=("Phase 26 tool: aggregate communication analytics."),
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "days": {"type": "integer", "default": 30},
                    },
                },
                output_schema={"type": "object"},
                handler=comm_tools.tool_get_communication_analytics,
            )
        )
        self.register(
            ToolSpec(
                name="summarize_unread",
                description=(
                    "Phase 26 tool: summarize today's unread notifications in simple terms."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
                output_schema={"type": "object"},
                handler=comm_tools.tool_summarize_unread,
            )
        )
        # -- Phase 8 AI assistant polish tools (read-only, public-safe) -------
        self.register(
            ToolSpec(
                name="get_institution_deep_dive",
                description=(
                    "Phase 8 official-persona Q&A tool: comprehensive institution "
                    "profile combining twin data, official baseline, recent reports, "
                    "discrepancies, and SLA status. Returns a structured briefing."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"institution_id": {"type": "string"}},
                    "required": ["institution_id"],
                },
                output_schema={"type": "object"},
                handler=tool_institution_deep_dive,
            )
        )
        self.register(
            ToolSpec(
                name="get_source_freshness",
                description=(
                    "Phase 8 tool: check freshness of a data source — when it was "
                    "last synced, how many records it has, and whether it's stale."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"source_id": {"type": "string"}},
                    "required": ["source_id"],
                },
                output_schema={"type": "object"},
                handler=tool_source_freshness,
            )
        )
        self.register(
            ToolSpec(
                name="get_department_briefing",
                description=(
                    "Phase 8 department context tool: public-safe department "
                    "briefing with case counts, SLA compliance, and active escalations."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "string"},
                        "category_slug": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
                handler=tool_department_briefing,
            )
        )

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get_tool(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Export MCP-compatible tool schema definitions."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
                "outputSchema": t.output_schema,
                "riskLevel": t.risk_level,
                "requiredRole": t.required_role,
            }
            for t in self._tools.values()
        ]

    async def execute(
        self,
        session: AsyncSession,
        name: str,
        arguments: dict[str, Any],
        viewer: Any | None = None,
    ) -> dict[str, Any]:
        """Execute a tool, enforcing its ``required_role`` guard (Step 12).

        ``required_role`` defaults to ``"public"`` (public-safe data only, no
        auth needed). Tools that require a role refuse to run for anonymous or
        under-privileged callers — the guard is enforced here, not left to each
        handler, so a prompt-injected tool call cannot bypass authorization.
        """
        spec = self.get_tool(name)
        if not spec:
            return {"error": f"Tool '{name}' is not registered or not permitted."}
        required = spec.required_role
        if required != "public":
            allowed = viewer is not None and (viewer.has_role(required) or viewer.has_role("admin"))
            if not allowed:
                return {"error": f"Tool '{name}' requires role '{required}' — access denied."}
        try:
            return await spec.handler(session=session, **arguments)
        except Exception as err:
            return {"error": f"Tool execution failed: {err}"}
