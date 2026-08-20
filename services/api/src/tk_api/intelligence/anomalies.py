"""Deterministic anomaly detection engine (Phase 20, docs/ANOMALY-DETECTION.md).

An anomaly means "something unusual was detected" — never "someone did
something wrong". The engine builds a baseline from a trailing window of
historical buckets and flags values that fall outside a documented expected
range. The method is fixed and reproducible (IQR over a trailing window, with
a minimum number of baseline points); the output always carries the expected
range and the deviation.

Metrics supported:

* ``report_volume``   — public report counts per bucket (day/week) vs trailing baseline
* ``resolution_time`` — resolution durations (hours) vs trailing baseline
* ``community_activity`` — comments+verifications per bucket vs trailing baseline
* ``report_institution_density`` — reports per institution count in the period
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic.models import Category
from tk_api.intelligence.models import AnomalyEvent
from tk_api.intelligence.schemas import AnomalyItem, AnomalyResponse
from tk_api.reports.models import Report, ReportComment, ReportVerification

MIN_BASELINE_POINTS = 8
IQR_MULTIPLIER = 1.5


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iqr_bounds(values: list[float]) -> tuple[float, float, float, float]:
    """Return (low, high, median, iqr) for a value list.

    Robust: uses Q1/Q3 (Tukey hinges) instead of mean/std so a few extreme
    historic points do not widen the baseline indefinitely.
    """
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    ordered = sorted(values)
    n = len(ordered)

    def q(p: float) -> float:
        idx = (n - 1) * p
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)

    q1, q3 = q(0.25), q(0.75)
    iqr = q3 - q1
    low = max(0.0, q1 - IQR_MULTIPLIER * iqr)
    high = q3 + IQR_MULTIPLIER * iqr
    return low, high, median(ordered), iqr


class AnomalyEngine:
    """Detect unusual patterns with documented expected ranges."""

    async def detect_report_volume(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        bucket: str = "week",
        baseline_buckets: int = 8,
    ) -> AnomalyItem | None:
        """Flag the most recent bucket as an anomaly vs the trailing baseline."""
        buckets = await self._volume_buckets(
            session,
            geography_id=geography_id,
            category_slug=category_slug,
            bucket=bucket,
            count=baseline_buckets + 1,
        )
        if len(buckets) < MIN_BASELINE_POINTS + 1:
            return None  # insufficient baseline; anomaly detection needs history
        baseline = [b["value"] for b in buckets[:-1]]
        current = buckets[-1]["value"]
        low, high, _med, _iqr = _iqr_bounds(baseline)
        if current <= high and current >= low:
            return None
        deviation_pct = round((current - _med) / _med * 100.0, 1) if _med > 0 else None
        return AnomalyItem(
            metric="report_volume",
            geography_id=geography_id,
            category_slug=category_slug,
            observed_value=float(current),
            expected_low=round(low, 2),
            expected_high=round(high, 2),
            deviation_pct=deviation_pct,
            method=f"iqr_trailing_{baseline_buckets}_{bucket}",
            explanation=(
                f"Observed {int(current)} reports in the latest {bucket} against an "
                f"expected range of {round(low)}-{round(high)} from the trailing "
                f"{baseline_buckets} {bucket}s. Possible explanations include a genuine "
                "increase, a reporting campaign, duplicates, an ingestion issue or an "
                "external event. This is a review trigger, not an accusation."
            ),
            status="NEW",
            detected_at=_utcnow(),
        )

    async def _volume_buckets(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None,
        category_slug: str | None,
        bucket: str,
        count: int,
    ) -> list[dict[str, Any]]:
        stmt = select(Report).where(Report.visibility == "public", Report.deleted_at.is_(None))
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        if category_slug:
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == category_slug
            )
        rows = (await session.execute(stmt)).scalars().all()
        from zoneinfo import ZoneInfo

        buckets: dict[str, int] = {}
        for r in rows:
            dt = (r.created_at or _utcnow()).astimezone(ZoneInfo("Asia/Kolkata"))
            if bucket == "day":
                key = dt.strftime("%Y-%m-%d")
            elif bucket == "month":
                key = dt.strftime("%Y-%m")
            else:
                key = f"{dt.year}-W{dt.isocalendar().week:02d}"
            buckets[key] = buckets.get(key, 0) + 1
        out = [{"timestamp": k, "value": v} for k, v in sorted(buckets.items())]
        return out[-count:]

    async def detect_resolution_time(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
    ) -> AnomalyItem | None:
        """Flag when the median resolution duration strayed outside the baseline."""
        from tk_api.cases.models import CivicCase

        case_stmt = select(CivicCase)
        rows = (await session.execute(case_stmt)).scalars().all()
        durations: list[list[float]] = []
        for case in rows:
            if case.resolution_verified_at and case.created_at:
                d = (case.resolution_verified_at - case.created_at).total_seconds() / 3600.0
                if d >= 0:
                    durations.append([d])
        if not durations:
            return None
        flat = [d[0] for d in durations]
        if len(flat) < MIN_BASELINE_POINTS:
            return None
        recent = flat[-1]
        low, high, _med, _iqr = _iqr_bounds(flat[:-1])
        if recent <= high and recent >= low:
            return None
        return AnomalyItem(
            metric="resolution_time",
            geography_id=geography_id,
            category_slug=category_slug,
            observed_value=round(recent, 1),
            expected_low=round(low, 1),
            expected_high=round(high, 1),
            method="iqr_trailing_resolution_hours",
            explanation=(
                "The latest verified resolution duration fell outside the trailing "
                "historical range. This is an operational observation, not a judgement "
                "on any department's conduct."
            ),
            status="NEW",
            detected_at=_utcnow(),
        )

    async def detect_community_activity(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        bucket: str = "week",
        baseline_buckets: int = 8,
    ) -> AnomalyItem | None:
        """Flag unusual community activity (comments + verifications) volume."""
        now = _utcnow()
        start = now - timedelta(days=baseline_buckets * 30)
        comments = (
            (
                await session.execute(
                    select(ReportComment.created_at).where(
                        ReportComment.created_at >= start, ReportComment.is_removed.is_(False)
                    )
                )
            )
            .scalars()
            .all()
        )
        verifications = (
            (
                await session.execute(
                    select(ReportVerification.created_at).where(
                        ReportVerification.created_at >= start
                    )
                )
            )
            .scalars()
            .all()
        )
        from zoneinfo import ZoneInfo

        def key(dt: datetime) -> str:
            local = dt.astimezone(ZoneInfo("Asia/Kolkata"))
            if bucket == "day":
                return local.strftime("%Y-%m-%d")
            return f"{local.year}-W{local.isocalendar().week:02d}"

        counts: dict[str, int] = {}
        for dt in comments:
            counts[key(dt)] = counts.get(key(dt), 0) + 1
        for dt in verifications:
            counts[key(dt)] = counts.get(key(dt), 0) + 1
        buckets_list: list[dict[str, Any]] = [
            {"timestamp": k, "value": v} for k, v in sorted(counts.items())
        ][-(baseline_buckets + 1) :]
        if len(buckets_list) < MIN_BASELINE_POINTS + 1:
            return None
        baseline = [float(b["value"]) for b in buckets_list[:-1]]
        current = float(buckets_list[-1]["value"])
        low, high, _med, _iqr = _iqr_bounds(baseline)
        if current <= high and current >= low:
            return None
        return AnomalyItem(
            metric="community_activity",
            geography_id=geography_id,
            observed_value=float(current),
            expected_low=round(low, 2),
            expected_high=round(high, 2),
            method="iqr_trailing_community_activity",
            explanation=(
                "Community activity (comments + verifications) was outside the trailing "
                "expected range. Possible explanations include genuine engagement, a "
                "coordinated drive or automated activity; moderation remains human."
            ),
            status="NEW",
            detected_at=_utcnow(),
        )

    async def detect_all(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
    ) -> list[AnomalyItem]:
        """Run the available detectors; anomalies are suggestions for review."""
        out: list[AnomalyItem] = []
        volume = await self.detect_report_volume(
            session, geography_id=geography_id, category_slug=category_slug
        )
        if volume:
            out.append(volume)
        resolution = await self.detect_resolution_time(
            session, geography_id=geography_id, category_slug=category_slug
        )
        if resolution:
            out.append(resolution)
        activity = await self.detect_community_activity(session, geography_id=geography_id)
        if activity:
            out.append(activity)
        return out

    async def persist(self, session: AsyncSession, items: list[AnomalyItem]) -> list[AnomalyEvent]:
        """Append-only persistence of detected anomalies."""
        persisted: list[AnomalyEvent] = []
        for item in items:
            event = AnomalyEvent(
                metric=item.metric,
                geography_id=item.geography_id,
                category_slug=item.category_slug,
                observed_value=item.observed_value,
                expected_low=item.expected_low,
                expected_high=item.expected_high,
                deviation_pct=item.deviation_pct,
                method=item.method,
                explanation=item.explanation,
                status="NEW",
                detected_at=item.detected_at or _utcnow(),
            )
            session.add(event)
            persisted.append(event)
        if persisted:
            await session.flush()
        return persisted

    async def list_events(
        self,
        session: AsyncSession,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AnomalyItem]:
        stmt = select(AnomalyEvent).order_by(AnomalyEvent.detected_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(AnomalyEvent.status == status)
        rows = (await session.execute(stmt)).scalars().all()
        return [
            AnomalyItem(
                metric=e.metric,
                geography_id=e.geography_id,
                category_slug=e.category_slug,
                observed_value=e.observed_value,
                expected_low=e.expected_low,
                expected_high=e.expected_high,
                deviation_pct=e.deviation_pct,
                method=e.method,
                explanation=e.explanation,
                status=e.status,
                detected_at=e.detected_at,
            )
            for e in rows
        ]

    async def summarize(
        self, session: AsyncSession, *, geography_id: uuid.UUID | None = None
    ) -> AnomalyResponse:
        items = await self.detect_all(session, geography_id=geography_id)
        if not items:
            items = await self.list_events(session, limit=20)
        return AnomalyResponse(
            anomalies=items or [],
            generated_at=_utcnow(),
            note=(
                "An anomaly is 'something unusual was detected' — never an accusation. "
                "It is a trigger for human review with an expected range and method "
                "shown for every item."
            ),
        )
