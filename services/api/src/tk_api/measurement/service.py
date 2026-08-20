"""Measurement rollups, basic tier (API.md §10, DATABASE.md §3.10).

Phase 5 computes overview aggregates live from ``reports`` (volume, resolution
rate, median resolve hours). Campaign trends read immutable
``measurement_snapshots`` when available, otherwise materialize a live snapshot
on demand; the worker (Phase 8) takes over scheduled snapshotting.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic.models import Campaign, Category
from tk_api.core.errors import ApiError
from tk_api.measurement.models import MeasurementSnapshot
from tk_api.reports.models import Report

IST = "Asia/Kolkata"


class MeasurementError(ApiError):
    pass


def _already_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _median_resolve_hours(pairs: list[tuple[datetime, datetime]]) -> float | None:
    """Median of (resolved_at - created_at) in hours; None when no resolved rows."""
    if not pairs:
        return None
    hours = sorted(
        (_already_aware(resolved) - _already_aware(created)).total_seconds() / 3600
        for created, resolved in pairs
    )
    mid = len(hours) // 2
    if len(hours) % 2 == 1:
        return round(hours[mid], 1)
    return round((hours[mid - 1] + hours[mid]) / 2, 1)


def _rollup(total: int, resolved: int, median_hours: float | None) -> dict[str, Any]:
    return {
        "volume": total,
        "resolution_rate": round(resolved / total, 4) if total else 0.0,
        "median_resolve_hours": median_hours,
    }


async def _measure(session: AsyncSession, clause: Any) -> dict[str, Any]:
    rows = (
        await session.execute(select(Report.created_at, Report.resolved_at).where(clause))
    ).all()
    resolved = [(r.created_at, r.resolved_at) for r in rows if r.resolved_at is not None]
    return _rollup(len(rows), len(resolved), _median_resolve_hours(resolved))


async def overview(session: AsyncSession) -> dict[str, Any]:
    """Category + campaign aggregates (live-computed)."""
    category_rows: list[dict[str, Any]] = []
    for category in (await session.execute(select(Category))).scalars().all():
        category_rows.append(
            {
                "slug": category.slug,
                **(await _measure(session, Report.category_id == category.id)),
            }
        )
    campaign_rows: list[dict[str, Any]] = []
    for campaign in (await session.execute(select(Campaign))).scalars().all():
        campaign_rows.append(
            {
                "id": str(campaign.id),
                "slug": campaign.slug,
                **(await _measure(session, Report.campaign_id == campaign.id)),
            }
        )
    return {"categories": category_rows, "campaigns": campaign_rows}


async def campaign_trend(session: AsyncSession, campaign_id: uuid.UUID) -> dict[str, Any]:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise MeasurementError("campaign not found", 404, "campaign_not_found")
    all_snapshots = (await session.execute(select(MeasurementSnapshot))).scalars().all()
    snapshots = [
        s for s in all_snapshots if (s.dimension or {}).get("campaign_id") == str(campaign_id)
    ]
    if not snapshots:
        await write_snapshot(session, campaign)
        await session.commit()
        all_snapshots = (await session.execute(select(MeasurementSnapshot))).scalars().all()
        snapshots = [
            s for s in all_snapshots if (s.dimension or {}).get("campaign_id") == str(campaign_id)
        ]
    return {
        "campaign_id": str(campaign_id),
        "slug": campaign.slug,
        "snapshots": [{"metrics": s.metrics, "generated_at": s.generated_at} for s in snapshots],
    }


async def write_snapshot(session: AsyncSession, campaign: Campaign) -> MeasurementSnapshot:
    """Materialize one immutable measurement snapshot for a campaign."""
    snapshot = MeasurementSnapshot(
        dimension={"campaign_id": str(campaign.id)},
        metrics=await _measure(session, Report.campaign_id == campaign.id),
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def rollup_all(session: AsyncSession) -> int:
    """Worker task: snapshot every campaign (append-only history)."""
    campaigns = (await session.execute(select(Campaign))).scalars().all()
    written = 0
    for campaign in campaigns:
        await write_snapshot(session, campaign)
        written += 1
    await session.commit()
    return written
