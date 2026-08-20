"""Deterministic trend engine (Phase 20, docs/INTELLIGENCE-METHODOLOGY.md).

Answers "what is happening, where, when, how often, increasing or decreasing"
using fixed, reproducible rules — never an LLM. Every result carries the
observation period, the comparison basis and explicit limitations. The engine
reports what changed and by how much; it never claims *why* a change happened
unless a separate, documented mechanism established that.

Comparison periods (comparable windows, not calendar quirks):

* previous week  — current rolling 7 days vs the 7 days before that
* previous month — current rolling 30 days vs the 30 days before that
* previous quarter — current rolling 90 days vs the 90 days before that
* previous year  — current rolling 365 days vs the 365 days before that
* custom         — explicit start/end for both periods

Direction thresholds are constant and documented:

* increasing  — change >= +10%
* decreasing  — change <= -10%
* stable      — otherwise (with ≥2 comparable buckets)
* insufficient_data — fewer than 2 buckets of history
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic.models import Category
from tk_api.geography.models import Geography
from tk_api.intelligence.models import TrendSnapshot
from tk_api.intelligence.schemas import (
    TrendAnalysisItem,
    TrendAnalysisResponse,
    TrendComparison,
)
from tk_api.reports.models import Report

logger = logging.getLogger("tk_api.intelligence")

INCREASE_THRESHOLD_PCT = 10.0
DECREASE_THRESHOLD_PCT = 10.0

MIN_COMPARISON_BUCKETS = 2
MIN_SEASONAL_YEARS = 2


def _utcnow() -> datetime:
    return datetime.now(UTC)


def comparable_periods(
    preset: str,
    *,
    timezone: str = "Asia/Kolkata",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_start: datetime | None = None,
    current_end: datetime | None = None,
) -> tuple[datetime | None, datetime | None, datetime | None, datetime | None, str] | None:
    """Return (current_start, current_end, prev_start, prev_end, label).

    ``preset`` is one of: today, yesterday, 7d, 30d, 90d, year, custom, all.
    For custom periods the caller supplies both start/end and the implicit
    previous period of equal length is used.
    Returns None when a comparison is not meaningful (e.g. "all").
    """
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("Asia/Kolkata")
    now_local = datetime.now(tz)
    now_utc = _utcnow()

    if preset == "all":
        return None

    if preset == "custom":
        if start_date is None or end_date is None:
            return None
        length = end_date - start_date
        if length <= timedelta(0):
            return None
        prev_end = start_date - timedelta(microseconds=1)
        prev_start = prev_end - length + timedelta(microseconds=1)
        return start_date, end_date, prev_start, prev_end, "Custom period"

    if preset == "today":
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        cur_start = start_local.astimezone(UTC)
        cur_end = now_utc
        prev_length = cur_end - (start_local - timedelta(days=1)).astimezone(UTC)
        prev_end = cur_start - timedelta(microseconds=1)
        prev_start = prev_end - prev_length + timedelta(microseconds=1)
        return cur_start, cur_end, prev_start, prev_end, "Today"

    durations: dict[str, timedelta] = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "year": timedelta(days=365),
    }
    if preset not in durations:
        return None
    length = durations[preset]
    cur_start = current_start or (now_utc - length)
    cur_end = current_end or now_utc
    prev_end = cur_start - timedelta(microseconds=1)
    prev_start = prev_end - length + timedelta(microseconds=1)
    labels = {
        "7d": "Previous 7 days",
        "30d": "Previous 30 days",
        "90d": "Previous 90 days",
        "year": "Previous 365 days",
    }
    return cur_start, cur_end, prev_start, prev_end, labels[preset]


def classify_change(change_pct: float | None, has_comparison: bool) -> str:
    if not has_comparison or change_pct is None:
        return "insufficient_data"
    if change_pct >= INCREASE_THRESHOLD_PCT:
        return "increasing"
    if change_pct <= -DECREASE_THRESHOLD_PCT:
        return "decreasing"
    return "stable"


class TrendEngine:
    """Deterministic trend + seasonality analytics over public reports."""

    async def report_series(
        self,
        session: AsyncSession,
        *,
        start: datetime | None,
        end: datetime | None,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        interval: str = "day",
        metric: str = "reports",
    ) -> list[dict[str, Any]]:
        """Count public reports per interval bucket within [start, end]."""
        stmt = select(Report).where(Report.visibility == "public", Report.deleted_at.is_(None))
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        if category_slug:
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == category_slug
            )
        if start:
            stmt = stmt.where(Report.created_at >= start)
        if end:
            stmt = stmt.where(Report.created_at <= end)
        rows = (await session.execute(stmt)).scalars().all()

        buckets: dict[str, int] = {}
        for r in rows:
            dt = (r.created_at or _utcnow()).astimezone(ZoneInfo("Asia/Kolkata"))
            if interval == "month":
                key = dt.strftime("%Y-%m")
            elif interval == "week":
                key = f"{dt.year}-W{dt.isocalendar().week:02d}"
            else:
                key = dt.strftime("%Y-%m-%d")
            buckets[key] = buckets.get(key, 0) + 1

        sortable = sorted(buckets.items(), key=lambda pair: pair[0])
        series = [{"timestamp": k, "value": v} for k, v in sortable]
        return series

    async def _count(
        self,
        session: AsyncSession,
        *,
        start: datetime | None,
        end: datetime | None,
        geography_id: uuid.UUID | None,
        category_slug: str | None,
        metric: str,
    ) -> int:
        if metric == "resolved":
            column = Report.status
            value = ("resolved", "community_verified", "closed")
            stmt = select(func.count(Report.id)).where(column.in_(value))
        else:
            stmt = select(func.count(Report.id))
        stmt = stmt.where(Report.visibility == "public", Report.deleted_at.is_(None))
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        if category_slug:
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == category_slug
            )
        if start:
            stmt = stmt.where(Report.created_at >= start)
        if end:
            stmt = stmt.where(Report.created_at <= end)
        return int((await session.scalar(stmt)) or 0)

    async def analyze(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        metric: str = "reports",
        preset: str = "30d",
        interval: str = "week",
        timezone: str = "Asia/Kolkata",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> TrendAnalysisItem:
        """Compare the current period against the comparable previous period."""
        resolved = comparable_periods(
            preset,
            timezone=timezone,
            start_date=start_date,
            end_date=end_date,
        )
        if resolved is None:
            return TrendAnalysisItem(
                metric=metric,
                geography_id=geography_id,
                category_slug=category_slug,
                interval=interval,
                comparison=TrendComparison(
                    period_label="All time",
                    count=await self._count(
                        session,
                        start=None,
                        end=None,
                        geography_id=geography_id,
                        category_slug=category_slug,
                        metric=metric,
                    ),
                    direction="insufficient_data",
                    coverage_note=("No comparison period: all-time counts have no denominator."),
                ),
                limitations=["A period comparison requires a bounded observation window."],
            )

        cur_start, cur_end, prev_start, prev_end, label = resolved
        current_count = await self._count(
            session,
            start=cur_start,
            end=cur_end,
            geography_id=geography_id,
            category_slug=category_slug,
            metric=metric,
        )
        previous_count = await self._count(
            session,
            start=prev_start,
            end=prev_end,
            geography_id=geography_id,
            category_slug=category_slug,
            metric=metric,
        )
        change_count = current_count - previous_count
        change_pct = round(change_count / previous_count * 100.0, 1) if previous_count > 0 else None
        direction = classify_change(change_pct, has_comparison=True)

        series = await self.report_series(
            session,
            start=prev_start,
            end=cur_end,
            geography_id=geography_id,
            category_slug=category_slug,
            interval=interval,
        )
        seasonality = await self.seasonal_pattern(
            session,
            geography_id=geography_id,
            category_slug=category_slug,
        )

        return TrendAnalysisItem(
            metric=metric,
            geography_id=geography_id,
            category_slug=category_slug,
            interval=interval,
            observation_period={
                "start": cur_start.isoformat() if cur_start else None,
                "end": cur_end.isoformat() if cur_end else None,
            },
            comparison=TrendComparison(
                period_label=label,
                start=cur_start,
                end=cur_end,
                count=current_count,
                change_count=change_count,
                change_pct=change_pct if change_pct is not None else None,
                direction=direction,  # type: ignore[arg-type]
                denominator=f"public {metric} in the previous {label.lower()}",
                coverage_note=(
                    "Counts use public reports only. No causation is inferred from this comparison."
                ),
            ),
            series=series,
            seasonality=seasonality,
            limitations=[
                "Reporting volume reflects community activity and awareness as well as issues.",
                "The cause of any change is not determined by this analysis.",
            ],
        )

    async def seasonal_pattern(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None,
        category_slug: str | None,
        min_years: int = MIN_SEASONAL_YEARS,
    ) -> list[dict[str, Any]]:
        """Group report counts by calendar month across years >= ``min_years``.

        Only reports the pattern as observed counts per month; it does not
        claim any cause (e.g. monsoon) unless separately established.
        """
        stmt = select(Report).where(
            Report.visibility == "public",
            Report.deleted_at.is_(None),
            Report.created_at.is_not(None),
        )
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        if category_slug:
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == category_slug
            )
        rows = (await session.execute(stmt)).scalars().all()
        by_month_year: dict[str, dict[str, int]] = {}
        years: set[str] = set()
        for r in rows:
            dt = (r.created_at or _utcnow()).astimezone(ZoneInfo("Asia/Kolkata"))
            month = dt.strftime("%m")
            year = dt.strftime("%Y")
            years.add(year)
            by_month_year.setdefault(month, {})[year] = by_month_year[month].get(year, 0) + 1
        if len(years) < min_years:
            return []
        out: list[dict[str, Any]] = []
        for month in sorted(by_month_year):
            counts_by_year = by_month_year[month]
            if len(counts_by_year) < min_years:
                continue
            values = [counts_by_year[y] for y in sorted(counts_by_year)]
            mean = sum(values) / len(values)
            out.append(
                {
                    "month": month,
                    "years": sorted(counts_by_year),
                    "counts": values,
                    "mean": round(mean, 1),
                    "note": "Observed monthly pattern; no causation claimed.",
                }
            )
        return out

    async def save_snapshot(
        self,
        session: AsyncSession,
        result: TrendAnalysisItem,
        *,
        geography_name: str | None = None,
    ) -> TrendSnapshot:
        """Persist an append-only trend snapshot for auditability."""
        snap = TrendSnapshot(
            metric=result.metric,
            geography_id=result.geography_id,
            category_slug=result.category_slug,
            period=result.observation_period,
            interval=result.interval,
            series=result.series,
            change_count=result.comparison.change_count,
            change_pct=result.comparison.change_pct,
            direction=result.comparison.direction,
            observed_at=_utcnow(),
        )
        session.add(snap)
        await session.flush()
        return snap

    async def summarize(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        metric: str = "reports",
        preset: str = "30d",
        timezone: str = "Asia/Kolkata",
    ) -> TrendAnalysisResponse:
        geo_name = None
        geo = await session.get(Geography, geography_id) if geography_id else None
        geo_name = geo.name if geo else None
        item = await self.analyze(
            session,
            geography_id=geography_id,
            category_slug=category_slug,
            metric=metric,
            preset=preset,
            timezone=timezone,
        )
        return TrendAnalysisResponse(
            items=[item],
            generated_at=_utcnow(),
            methodology_note=(
                "Deterministic period-over-period comparison on comparable windows. "
                "Geography: "
                + (geo_name or "National")
                + ". Direction thresholds: ±10%. No causation is inferred."
            ),
        )
