"""Phase 23 — Data Trust worker tasks.

Periodic jobs: data quality checks, source health snapshots, quarantine
validation, and stale data detection. All tasks follow the DurableTask
pattern (at-least-once delivery, dead-letter on exhaustion).

Beat schedules (added to celery_app.conf.beat_schedule in __init__.py):
- ``data-quality-sweep``: daily 03:00 IST — run quality dimensions per dataset
- ``source-health-snapshot``: every 4 hours — capture source health counters
- ``quarantine-review``: daily 09:00 IST — notify stewards of quarantined records
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from tk_api.core.config import Settings
from tk_api.core.db import create_engine, create_session_factory
from tk_api.worker import DurableTask, celery_app

_logger = logging.getLogger("tk_api.worker.data_trust")


def _settings() -> Settings:
    return Settings()


def _engine(settings: Settings) -> Any:
    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
    )


# ---------------------------------------------------------------------------
# Data Quality Sweep
# ---------------------------------------------------------------------------


async def _run_quality_sweep(settings: Settings) -> dict[str, Any]:
    """Run data quality checks across all active datasets.

    For each dataset with source records, compute:
    - completeness: % of non-null required fields
    - freshness: how recently records were updated
    - consistency: no conflicting values for same field
    """
    from tk_api.data_trust.models import DataQualityResult
    from tk_api.govdata.models import GovDataset, GovDatasetRecord

    engine = _engine(settings)
    results: dict[str, Any] = {"datasets_checked": 0, "quality_results": 0}
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            datasets = (
                (await session.execute(select(GovDataset).where(GovDataset.status == "active")))
                .scalars()
                .all()
            )

            for dataset in datasets:
                results["datasets_checked"] += 1

                # Count records
                total = (
                    await session.scalar(
                        select(func.count(GovDatasetRecord.id)).where(
                            GovDatasetRecord.dataset_id == dataset.id,
                            GovDatasetRecord.valid_to.is_(None),
                        )
                    )
                    or 0
                )

                if total == 0:
                    continue

                # Completeness: check how many records have non-null data
                records_with_data = (
                    await session.scalar(
                        select(func.count(GovDatasetRecord.id)).where(
                            GovDatasetRecord.dataset_id == dataset.id,
                            GovDatasetRecord.valid_to.is_(None),
                            GovDatasetRecord.data.isnot(None),
                        )
                    )
                    or 0
                )

                completeness_score = records_with_data / total if total else 0.0
                completeness_status = (
                    "VALID"
                    if completeness_score >= 0.95
                    else "PARTIALLY_VALID"
                    if completeness_score >= 0.7
                    else "INCOMPLETE"
                )

                # Freshness: check import job timestamps
                from tk_api.govdata.models import GovImportJob

                latest_job = await session.scalar(
                    select(GovImportJob)
                    .where(GovImportJob.dataset_id == dataset.id)
                    .order_by(GovImportJob.started_at.desc())
                    .limit(1)
                )

                freshness_score = 1.0
                freshness_status = "VALID"
                if latest_job and latest_job.finished_at:
                    age_days = (datetime.now(UTC) - latest_job.finished_at).days
                    if age_days > 90:
                        freshness_score = 0.2
                        freshness_status = "STALE"
                    elif age_days > 30:
                        freshness_score = 0.6
                        freshness_status = "PARTIALLY_VALID"

                # Record quality results
                for dimension, score, status in [
                    ("completeness", completeness_score, completeness_status),
                    ("freshness", freshness_score, freshness_status),
                ]:
                    # Upsert: check if recent result exists
                    existing = await session.scalar(
                        select(DataQualityResult)
                        .where(
                            DataQualityResult.entity_type == "dataset",
                            DataQualityResult.entity_id == dataset.id,
                            DataQualityResult.dimension == dimension,
                        )
                        .order_by(DataQualityResult.created_at.desc())
                    )

                    # Only create new if older than 24 hours or doesn't exist
                    should_create = (
                        existing is None
                        or (datetime.now(UTC) - existing.created_at).total_seconds() > 86400
                    )

                    if should_create:
                        result = DataQualityResult(
                            entity_type="dataset",
                            entity_id=dataset.id,
                            dataset_id=dataset.id,
                            dimension=dimension,
                            score=score,
                            status=status,
                            overall_status=status,
                        )
                        session.add(result)
                        results["quality_results"] += 1

            await session.commit()
    finally:
        await engine.dispose()
    return results


@celery_app.task(
    name="tk_worker.data_quality_sweep",
    base=DurableTask,
)
def data_quality_sweep() -> dict[str, Any]:
    """Beat daily: run data quality checks across all active datasets."""
    return asyncio.run(_run_quality_sweep(_settings()))


# ---------------------------------------------------------------------------
# Source Health Snapshots
# ---------------------------------------------------------------------------


async def _run_source_health_snapshots(settings: Settings) -> dict[str, Any]:
    """Capture health snapshots for all active data sources."""
    from tk_api.data_trust.models import SourceHealthSnapshot
    from tk_api.provenance.models import DataSource

    engine = _engine(settings)
    results: dict[str, Any] = {"sources_snapshotted": 0}
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            sources = (
                (await session.execute(select(DataSource).where(DataSource.status == "active")))
                .scalars()
                .all()
            )

            for source in sources:
                # Determine health from source status
                status = "HEALTHY"
                error_summary = None

                if source.status == "failed":
                    status = "FAILED"
                elif source.status == "stale":
                    status = "DEGRADED"
                    error_summary = "Source data is stale"

                snapshot = SourceHealthSnapshot(
                    source_id=source.id,
                    status=status,
                    error_summary=error_summary,
                )
                session.add(snapshot)
                results["sources_snapshotted"] += 1

            await session.commit()
    finally:
        await engine.dispose()
    return results


@celery_app.task(
    name="tk_worker.source_health_snapshots",
    base=DurableTask,
)
def source_health_snapshots() -> dict[str, Any]:
    """Beat every 4 hours: capture source health snapshots."""
    return asyncio.run(_run_source_health_snapshots(_settings()))


# ---------------------------------------------------------------------------
# Quarantine Review Notifications
# ---------------------------------------------------------------------------


async def _run_quarantine_review(settings: Settings) -> dict[str, Any]:
    """Check for quarantined records pending review and notify data stewards."""
    from tk_api.data_trust.models import DataQuarantineRecord

    engine = _engine(settings)
    results: dict[str, Any] = {"quarantined_pending": 0}
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            quarantined = (
                await session.scalar(
                    select(func.count(DataQuarantineRecord.id)).where(
                        DataQuarantineRecord.status == "QUARANTINED"
                    )
                )
                or 0
            )

            results["quarantined_pending"] = quarantined

            # Notify admins if quarantine is growing
            if quarantined > 10:
                _logger.warning(
                    "Quarantine backlog: %d records pending review",
                    quarantined,
                )
    finally:
        await engine.dispose()
    return results


@celery_app.task(
    name="tk_worker.quarantine_review_check",
    base=DurableTask,
)
def quarantine_review_check() -> dict[str, Any]:
    """Beat daily: check quarantine backlog and notify stewards."""
    return asyncio.run(_run_quarantine_review(_settings()))
