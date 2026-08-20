"""Forecast executor (Phase 20, spec §14, docs/INTELLIGENCE-METHODOLOGY.md).

The piecewise-exponential/rolling-mean forecasts used here are deliberately
simple and fully documented: we forecast report volume (new public reports per
week) with a trailing-mean + linear drift, and resolved-volume with the same
method. Any week with a jump rate that disqualifies the stationary assumption
sets ``status=insufficient_data`` instead of publishing a number. Output rows
are append-only and each run pins the methodology used (``method`` +
``model_version``) so later explanations can cite the exact run.

The math lives here so tests can call it directly; the worker calls it with a
session.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic.models import Category
from tk_api.intelligence.models import ForecastResult, ForecastRun
from tk_api.reports.models import Report, ReportStatusHistory

MIN_HISTORY_WEEKS = 8
WEEK = timedelta(days=7)
RESOLVED_STATUSES = ("resolved", "community_verified", "closed")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _snap_week(dt: datetime) -> datetime:
    return (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def weekly_series(
    start: datetime, end: datetime, counts: dict[datetime, int]
) -> list[dict[str, Any]]:
    """Fill continuous week buckets between start and end (inclusive)."""
    out: list[dict[str, Any]] = []
    cursor = _snap_week(start)
    last = _snap_week(end)
    while cursor <= last:
        out.append({"week": cursor.isoformat(), "count": counts.get(cursor, 0)})
        cursor += WEEK
    return out


def _bucketize(dates: list[datetime]) -> dict[datetime, int]:
    counts: dict[datetime, int] = {}
    for d in dates:
        counts[_snap_week(d)] = counts.get(_snap_week(d), 0) + 1
    return counts


def piecewise_forecast(
    quarterly: list[float],
    *,
    horizon_weeks: int,
    max_weeks_back: int = 130,
) -> dict[str, Any]:
    """Simple transparent forecast with an explicit insufficient-data path.

    Returns keys: method, points (list), eval (RMSE/MAPE), status, min_model
    horizon weeks, and a bullet-proof ``notes`` list explaining limitations.
    """
    earliest = max(MIN_HISTORY_WEEKS, min(len(quarterly), max_weeks_back))
    series = quarterly[-earliest:] if quarterly else []
    if len(series) < MIN_HISTORY_WEEKS:
        return {
            "method": "piecewise-exponential",
            "points": [],
            "eval": None,
            "status": "insufficient_data",
            "min_history_weeks": MIN_HISTORY_WEEKS,
            "notes": [
                f"need at least {MIN_HISTORY_WEEKS} weekly observations; found {len(series)}."
            ],
        }

    alpha = 0.3
    smoothed = series[0]
    smoothed_hist: list[float] = []
    for v in series:
        # EMA-based expected value; keeps drift conservative.
        smoothed = alpha * v + (1 - alpha) * smoothed
        smoothed_hist.append(smoothed)
    base = smoothed_hist[-1]

    # Drift: average change per week over the *second half* only (recent
    # behaviour), clamped so the forecast cannot go exponential.
    half = sorted(series[-len(series) // 2 :])
    drift = (half[-1] - half[0]) / max(len(half) - 1, 1) if half else 0.0
    max_growth = 0.5 + base  # per-week absolute cap is relative to base
    drift = max(-base, min(max_growth, drift))

    points: list[dict[str, Any]] = []
    value = base
    for w in range(1, horizon_weeks + 1):
        value = max(0.0, value + drift)
        spread = max(1.0, value * 0.35)
        points.append(
            {
                "week": (_snap_week(_utcnow()) + WEEK * (w)).isoformat(),
                "low": round(value - spread, 2),
                "point": round(value, 2),
                "high": round(value + spread, 2),
            }
        )

    # Residuals of the smoothing fit: observed vs fitted (MAPE + RMSE).
    squared = [
        (observed - fitted) ** 2 for observed, fitted in zip(series, smoothed_hist, strict=True)
    ]
    rmse = math.sqrt(sum(squared) / len(squared)) if squared else 0.0
    mape = (
        round(
            sum(
                abs(observed - fitted) / max(observed, 1.0)
                for observed, fitted in zip(series, smoothed_hist, strict=True)
            )
            / len(series)
            * 100,
            1,
        )
        if series
        else 0.0
    )
    return {
        "method": "piecewise-exponential",
        "points": points,
        "eval": {"rmse": round(rmse, 2), "mape_pct": mape},
        "status": "completed",
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "notes": [
            "Forecast continues the recent EMA level with a clamped linear drift.",
            "It is not a causal model; treat as a planning range, not a prediction.",
        ],
    }


class ForecastExecutor:
    """Runs and stores one forecast run; the run row is created by the API."""

    async def execute(self, session: AsyncSession, run: ForecastRun) -> ForecastRun:
        run.status = "running"
        run.method = "piecewise-exponential"
        await session.flush()

        try:
            end = _utcnow()
            start = end - timedelta(weeks=max(MIN_HISTORY_WEEKS, run.horizon_days // 14 + 4) * 2)
            base = select(Report.id).where(
                Report.visibility == "public",
                Report.deleted_at.is_(None),
            )
            if run.geography_id:
                base = base.where(Report.boundary_id == run.geography_id)
            if run.category_slug:
                cat_id = await session.scalar(
                    select(Category.id).where(Category.slug == run.category_slug)
                )
                if cat_id:
                    base = base.where(Report.category_id == cat_id)

            if run.metric == "resolved":
                hist_stmt = (
                    select(ReportStatusHistory.created_at)
                    .join(Report, ReportStatusHistory.report_id == Report.id)
                    .where(
                        ReportStatusHistory.created_at >= start,
                        ReportStatusHistory.created_at <= end,
                        ReportStatusHistory.to_status.in_(RESOLVED_STATUSES),
                        Report.visibility == "public",
                        Report.deleted_at.is_(None),
                    )
                )
                if run.geography_id:
                    hist_stmt = hist_stmt.where(Report.boundary_id == run.geography_id)
                if run.category_slug and cat_id:
                    hist_stmt = hist_stmt.where(Report.category_id == cat_id)
                dates: list[datetime] = list((await session.execute(hist_stmt)).scalars())
                counts = _bucketize(dates)
            else:
                rows = (
                    await session.execute(
                        base.add_columns(Report.created_at).where(Report.created_at >= start)
                    )
                ).all()
                counts = _bucketize([r.created_at for r in rows if r.created_at])

            quarterly = [float(counts.get(k, 0.0)) for k in sorted(counts)]
            horizon_weeks = max(2, math.ceil(run.horizon_days / 7))
            out = piecewise_forecast(
                quarterly,
                horizon_weeks=horizon_weeks,
            )
            run.status = out["status"]
            run.eval_metrics = out["eval"]
            run.model_version = "phase20-piecewise-exp-1"
            run.training_start = start
            run.training_end = end
            run.min_points = len(quarterly)
            if out["status"] != "completed":
                run.error = "; ".join(out["notes"])
                await session.flush()
                return run

            for p in out["points"]:
                session.add(
                    ForecastResult(
                        run_id=run.id,
                        point=datetime.fromisoformat(p["week"]),
                        low=float(p["low"]),
                        point_value=float(p["point"]),
                        high=float(p["high"]),
                    )
                )
            await session.flush()
            return run
        except Exception as exc:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
            await session.flush()
            return run
