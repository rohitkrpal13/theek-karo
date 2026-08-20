"""Resolution-side intelligence (Phase 20, spec §13, docs/INTELLIGENCE-METHODOLOGY.md).

Read-only aggregates over the case lifecycle: SLA response/resolution clocks,
aging buckets, reopen/followup counts, and a list of verified improvements
(positive-verification reports; not a promise that the underlying problem
never returns).
"""

from __future__ import annotations

import statistics
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases.models import CivicCase
from tk_api.intelligence.schemas import (
    AgingBucketItem,
    ImprovementItem,
    ImprovementResponse,
    ResolutionIntelligenceResponse,
)
from tk_api.reports.models import Report, ReportEvidence, ReportVerification
from tk_api.resolution.models import ResolutionFollowup

RESOLVED_STATUSES = ("resolved", "community_verified", "closed")
HOURS = 3600.0
_IMPROVEMENT_NOTE = (
    "Improvements are reports marked resolved, disclosed transparently. "
    "A resolved report is not a guarantee the problem will not recur."
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    hours = (end - start).total_seconds() / HOURS
    return round(max(hours, 0.0), 1)


def _p90(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sorted(values)[int(len(values) * 0.9) - 1], 1)


class ResolutionIntelligenceService:
    async def summarize(
        self, session: AsyncSession, *, geography_id: uuid.UUID | None = None
    ) -> ResolutionIntelligenceResponse:
        stmt = select(CivicCase)
        if geography_id:
            stmt = stmt.where(CivicCase.assigned_geography_id == geography_id)
        cases = (await session.execute(stmt)).scalars().all()

        response_hours: list[float] = []
        resolution_hours: list[float] = []
        within_sla = at_risk = breached = 0
        aging: dict[str, int] = {"0-7": 0, "8-14": 0, "15-30": 0, "31-90": 0, "90+": 0}
        open_count = 0
        for c in cases:
            first = c.sla_started_at or c.created_at
            if c.sla_status == "breached":
                breached += 1
            elif c.sla_status == "at_risk":
                at_risk += 1
            elif c.sla_status == "within_sla":
                within_sla += 1
            if c.resolution_verified_at or c.closed_at:
                rh = _hours_between(first, c.resolution_verified_at or c.closed_at)
                if rh is not None:
                    resolution_hours.append(rh)
                res_time = c.resolution_verified_at or c.closed_at
                age_days = (res_time - first).total_seconds() / 86400 if res_time and first else 0
                bucket = (
                    "0-7"
                    if age_days <= 7
                    else "8-14"
                    if age_days <= 14
                    else "15-30"
                    if age_days <= 30
                    else "31-90"
                    if age_days <= 90
                    else "90+"
                )
                aging[bucket] += 1
            else:
                open_count += 1
                age_days = (_utcnow() - first).total_seconds() / 86400 if first else 0
                bucket = (
                    "0-7"
                    if age_days <= 7
                    else "8-14"
                    if age_days <= 14
                    else "15-30"
                    if age_days <= 30
                    else "31-90"
                    if age_days <= 90
                    else "90+"
                )
                aging[bucket] += 1

        followups = 0
        reopen_count = 0
        if cases:
            case_ids = [c.id for c in cases]
            followups = len(
                (
                    await session.execute(
                        select(ResolutionFollowup).where(ResolutionFollowup.case_id.in_(case_ids))
                    )
                )
                .scalars()
                .all()
            )

        total = len(cases)
        return ResolutionIntelligenceResponse(
            total_cases=total,
            avg_response_hours=(
                round(statistics.mean(response_hours), 1) if response_hours else None
            ),
            median_response_hours=(
                round(statistics.median(response_hours), 1) if response_hours else None
            ),
            p90_response_hours=_p90(response_hours),
            avg_resolution_hours=(
                round(statistics.mean(resolution_hours), 1) if resolution_hours else None
            ),
            median_resolution_hours=(
                round(statistics.median(resolution_hours), 1) if resolution_hours else None
            ),
            p90_resolution_hours=_p90(resolution_hours),
            within_sla_count=within_sla,
            at_risk_count=at_risk,
            breached_count=breached,
            sla_compliance_pct=(
                round(within_sla / total * 100, 1) if total and within_sla else 0.0
            ),
            open_count=open_count,
            aging_buckets=[
                AgingBucketItem(
                    bucket_label=k,
                    count=v,
                    pct=round(v / total * 100, 1) if total else 0.0,
                )
                for k, v in sorted(
                    aging.items(), key=lambda kv: int(kv[0].split("-")[0].rstrip("+"))
                )
            ],
            reopen_count=reopen_count,
            followup_signals=followups,
            verified_resolution_count=sum(1 for c in cases if c.resolution_verified_at),
            community_confirmed_count=sum(1 for c in cases if c.community_confirmed_at),
            limitations=[
                "Response hours are not captured when SLA was never started.",
                "Reopen tracking counts case status history entries, not conversations.",
            ],
            generated_at=_utcnow(),
        )

    async def improvements(
        self, session: AsyncSession, *, geography_id: uuid.UUID | None = None, limit: int = 50
    ) -> ImprovementResponse:
        from tk_api.civic.models import Category

        stmt = (
            select(Report.id, Report.title, Report.category_id, Report.created_at, Report.status)
            .where(
                Report.visibility == "public",
                Report.deleted_at.is_(None),
                Report.status.in_(RESOLVED_STATUSES),
            )
            .order_by(Report.created_at.desc())
            .limit(max(limit * 8, 200))
        )
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        rows = (await session.execute(stmt)).all()
        if not rows:
            return ImprovementResponse(
                items=[], count=0, generated_at=_utcnow(), note=_IMPROVEMENT_NOTE
            )
        cat_ids = {r.category_id for r in rows if r.category_id}
        slug_map: dict[uuid.UUID, str] = {}
        if cat_ids:
            for c in (
                await session.execute(select(Category).where(Category.id.in_(cat_ids)))
            ).scalars():
                slug_map[c.id] = c.slug
        report_ids = [r.id for r in rows]
        ev_counts = {
            e.report_id: int(e.n)
            for e in (
                await session.execute(
                    select(ReportEvidence.report_id, func.count(ReportEvidence.id).label("n"))
                    .where(ReportEvidence.report_id.in_(report_ids))
                    .group_by(ReportEvidence.report_id)
                )
            ).all()
        }
        latest_ver: dict[uuid.UUID, datetime] = {}
        for report_id, v_at in (
            await session.execute(
                select(ReportVerification.report_id, func.max(ReportVerification.created_at))
                .where(ReportVerification.report_id.in_(report_ids))
                .group_by(ReportVerification.report_id)
            )
        ).all():
            latest_ver[report_id] = v_at
        items: list[ImprovementItem] = [
            ImprovementItem(
                report_id=r.id,
                title=str(r.title)[:160],
                category_slug=slug_map.get(r.category_id) if r.category_id else None,
                resolved_at=r.created_at,
                verified_at=latest_ver.get(r.id),
                evidence_count=ev_counts.get(r.id, 0),
                source="resolution",
            )
            for r in rows
        ][:limit]
        return ImprovementResponse(
            items=items, count=len(items), generated_at=_utcnow(), note=_IMPROVEMENT_NOTE
        )
