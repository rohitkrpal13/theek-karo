"""Data quality duty-of-care engines (Phase 20, spec §16, docs/INTELLIGENCE-METHODOLOGY.md).

DataFreshnessEngine.scan            → who is stale / not being refreshed (sources,
                                      connectors, verification due).
DataFreshnessEngine.gap_analysis    → which institution types lack official-data
                                      coverage (resource-gap discovery duty of care).

These are observational checks. They never mutate source systems; they produce
snapshot summaries consumed by the worker (intelligence jobs) and the API
(endpoints).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.govdata.models import GovDataset, GovImportJob
from tk_api.institutions.models import Institution
from tk_api.integrations.models import IntegrationConnector
from tk_api.intelligence.schemas import (
    DataFreshnessResponse,
    DataGapItem,
    DataGapResponse,
    FreshnessItem,
)
from tk_api.provenance.models import DataSource

STALE_VERIFICATION_DAYS = 90
STALE_FETCH_FACTOR = 2.0  # frequency * 2 without refresh => stale
MIN_REFRESH_DAYS = 30  # active source without a successful import in this window


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _age_days(ts: datetime | None) -> float | None:
    if not ts:
        return None
    return max(0.0, (_utcnow() - ts).total_seconds() / 86400)


class DataFreshnessEngine:
    """Read-only freshness and coverage scans over registered data sources."""

    async def scan(self, session: AsyncSession) -> DataFreshnessResponse:
        items: list[FreshnessItem] = []

        sources = (
            (await session.execute(select(DataSource).where(DataSource.status != "inactive")))
            .scalars()
            .all()
        )
        for s in sources:
            if s.update_frequency_hours:
                expected_days = s.update_frequency_hours / 24
                last = s.retrieval_date or s.publication_date
                age = _age_days(last)
                stale = age is not None and age > expected_days * STALE_FETCH_FACTOR
                items.append(
                    FreshnessItem(
                        scope="data_source",
                        label=f"Source '{s.name}'",
                        last_updated_at=last,
                        expected_frequency=f"every {s.update_frequency_hours}h",
                        detail=(
                            f"{'STALE' if stale else 'fresh'}: last retrieval {age:.0f}d ago"
                            if age is not None
                            else "never retrieved"
                        ),
                    )
                )

        datasets = (await session.execute(select(GovDataset))).scalars().all()
        for d in datasets:
            job = await session.scalar(
                select(GovImportJob)
                .where(GovImportJob.dataset_id == d.id)
                .order_by(GovImportJob.started_at.desc())
                .limit(1)
            )
            last = job.finished_at if job else None
            age = _age_days(last)
            stale = age is not None and age > MIN_REFRESH_DAYS
            items.append(
                FreshnessItem(
                    scope="official_dataset",
                    label=f"Dataset '{d.name}'",
                    last_updated_at=last,
                    expected_frequency="monthly check",
                    detail=(
                        f"{'STALE' if stale else 'recent'}: last import {age:.0f}d ago"
                        if age is not None
                        else "never imported"
                    ),
                )
            )

        connectors = (
            (
                await session.execute(
                    select(IntegrationConnector).where(IntegrationConnector.status == "UNKNOWN")
                )
            )
            .scalars()
            .all()
        )
        for c in connectors:
            age = _age_days(c.last_success_at)
            overdue = (
                age is not None
                and c.sync_frequency_hours
                and age > (c.sync_frequency_hours * STALE_FETCH_FACTOR / 24)
            )
            items.append(
                FreshnessItem(
                    scope="connector",
                    label=f"Connector '{c.name}'",
                    last_updated_at=c.last_success_at or c.last_sync_at,
                    expected_frequency=(
                        f"every {c.sync_frequency_hours}h" if c.sync_frequency_hours else None
                    ),
                    detail=(
                        f"{'STALE' if overdue else 'ok'} ({age:.0f}d since last success)"
                        if age is not None
                        else "never synced"
                    ),
                )
            )

        stale_verifications = [
            s.name
            for s in sources
            if (age := _age_days(s.last_verified_at)) is None or age > STALE_VERIFICATION_DAYS
        ]
        if stale_verifications:
            items.append(
                FreshnessItem(
                    scope="verification",
                    label=f"{len(stale_verifications)} source(s) due re-verification",
                    detail=", ".join(stale_verifications[:8]),
                )
            )
        return DataFreshnessResponse(items=items, generated_at=_utcnow())

    async def gap_analysis(self, session: AsyncSession) -> DataGapResponse:
        rows = (
            await session.execute(
                select(
                    Institution.institution_type_id,
                    func.count(Institution.id).label("total"),
                ).group_by(Institution.institution_type_id)
            )
        ).all()
        from tk_api.institutions.models import InstitutionType

        type_names: dict[uuid.UUID, str] = {}
        if rows:
            ids = [r.institution_type_id for r in rows if r.institution_type_id]
            if ids:
                for t in (
                    await session.execute(
                        select(InstitutionType).where(InstitutionType.id.in_(ids))
                    )
                ).scalars():
                    type_names[t.id] = t.code

        from tk_api.govdata.models import InstitutionDiscrepancy

        with_data: dict[uuid.UUID, int] = {}
        if rows:
            type_ids = [r.institution_type_id for r in rows if r.institution_type_id]
            grouped: dict[Any, int] = {}
            if type_ids:
                joined = (
                    await session.execute(
                        select(
                            Institution.institution_type_id,
                            func.count(InstitutionDiscrepancy.id),
                        )
                        .join(
                            InstitutionDiscrepancy,
                            InstitutionDiscrepancy.institution_id == Institution.id,
                        )
                        .where(Institution.institution_type_id.in_(type_ids))
                        .group_by(Institution.institution_type_id)
                    )
                ).all()
                for tid, cnt in joined:
                    grouped[tid] = int(cnt)
                with_data = grouped

        items: list[DataGapItem] = []
        for tid, total in rows:
            if not tid:
                continue
            count_with = with_data.get(tid, 0)
            items.append(
                DataGapItem(
                    scope="institution_type",
                    total=total,
                    with_data=count_with,
                    without_data=total - count_with,
                    coverage_pct=round(count_with / total * 100, 1) if total else None,
                    note=(
                        f"{type_names.get(tid, tid)}: {count_with}/{total} institutions "
                        "have official-data matches (discrepancy rows)."
                    ),
                )
            )
        items.sort(key=lambda i: i.coverage_pct or 0)
        return DataGapResponse(
            items=items,
            generated_at=_utcnow(),
            interpretation_note=(
                "Coverage counts institutions that carry an official-data comparison "
                "(InstitutionDiscrepancy row). Low coverage means the institution type "
                "lacks official data imports — candidates for new source pings, not "
                "evidence of failure."
            ),
        )
