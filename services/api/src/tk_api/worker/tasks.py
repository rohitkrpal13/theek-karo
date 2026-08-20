"""Worker tasks (ADR-005): durable jobs the API enqueues or beat schedules.

Each task opens its own DB session on a fresh engine (worker === same image,
same TK_ env) inside a single ``asyncio.run``; tasks are written to be safe
under at-least-once delivery (rows carry status + attempts).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from tk_api.core.config import Settings
from tk_api.core.db import create_engine, create_session_factory
from tk_api.worker import DurableTask, celery_app


def _settings() -> Settings:
    return Settings()


def _engine(settings: Settings) -> Any:
    """Engine honoring the pool settings (Step 9)."""
    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
    )


async def _dispatch_due(settings: Settings) -> int:
    from tk_api.notifications import service as notifications_service
    from tk_api.notifications.providers import build_providers

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            providers = build_providers(settings)
            providers["in_app"] = None
            return await notifications_service.dispatch_due(
                session, settings=settings, providers=providers
            )
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.dispatch_due_notifications", base=DurableTask)
def dispatch_due_notifications() -> dict[str, int]:
    """Poll the notification queue (beat every 60 s + after enqueues)."""
    dispatched = asyncio.run(_dispatch_due(_settings()))
    return {"dispatched": dispatched}


async def _process_media(settings: Settings, media_id: uuid.UUID) -> str:
    from tk_api.media import service as media_service
    from tk_api.media.storage import build_storage

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            return await media_service.process_media_task(
                session,
                media_id=media_id,
                settings=settings,
                storage=build_storage(settings),
            )
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.process_media", base=DurableTask)
def process_media(media_id: str) -> dict[str, Any]:
    """Scan + thumbnail + finalize a uploaded media object (off the API)."""
    status = asyncio.run(_process_media(_settings(), uuid.UUID(media_id)))
    return {"media_id": media_id, "status": status}


async def _analyze_report(settings: Settings, report_id: uuid.UUID) -> str:
    from tk_api.ai import service as ai_service
    from tk_api.ai.gateway import build_gateway

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            result = await ai_service.process_report(
                session,
                report_id=report_id,
                gateway=build_gateway(settings),
                threshold=settings.ai_dedup_similarity_threshold,
                min_report_age_days=settings.ai_dedup_min_report_age_days,
            )
            annotation_id = str(result.get("annotation_id") or "")
            return annotation_id
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.analyze_report", base=DurableTask)
def analyze_report(report_id: str) -> dict[str, Any]:
    """AI analysis + duplicate suggestion (PII-insulated payloads, ADR-019)."""
    annotation_id = asyncio.run(_analyze_report(_settings(), uuid.UUID(report_id)))
    return {"annotation_id": annotation_id}


async def _rollup_all(settings: Settings) -> int:
    from tk_api.measurement import service as measurement_service

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            return await measurement_service.rollup_all(session)
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.measurement_rollup_all", base=DurableTask)
def measurement_rollup_all() -> dict[str, int]:
    """Materialize fresh measurement snapshots for every campaign (beat hourly)."""
    written = asyncio.run(_rollup_all(_settings()))
    return {"snapshots_written": written}


async def _sla_sweep(settings: Settings) -> dict[str, int]:
    """Evaluate every active case SLA clock and escalate breaches (Phase 14)."""
    from sqlalchemy import select

    from tk_api.cases import escalation as escalation_engine
    from tk_api.cases import sla as sla_engine
    from tk_api.cases.models import CivicCase

    engine = _engine(settings)
    breached = 0
    evaluated = 0
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            cases = (
                (
                    await session.execute(
                        select(CivicCase).where(
                            CivicCase.sla_status.in_(
                                ("within_sla", "at_risk", "not_started", "paused")
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
            for case in cases:
                _, status = await sla_engine.evaluate_case_sla(session, case)
                evaluated += 1
                if status == "breached":
                    updated = await escalation_engine.escalate_on_breach(session, case)
                    if updated is not None:
                        breached += 1
            await session.commit()
    finally:
        await engine.dispose()
    return {"evaluated": evaluated, "escalations": breached}


@celery_app.task(name="tk_worker.evaluate_sla_due", base=DurableTask)
def evaluate_sla_due() -> dict[str, int]:
    """Beat loop (every 60 s): evaluate case SLA clocks, trigger escalations."""
    return asyncio.run(_sla_sweep(_settings()))


async def _generate_export(settings: Settings, job_id: uuid.UUID) -> dict[str, Any]:
    from tk_api.media.storage import build_storage
    from tk_api.publicdata import service as publicdata_service
    from tk_api.publicdata.models import DataExportJob

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            job = await session.get(DataExportJob, job_id)
            if job is None:
                return {"job_id": job_id, "status": "not_found"}
            result = await publicdata_service.PublicDataService().run_export(
                session,
                job,
                settings=settings,
                storage=build_storage(settings),
            )
            await session.commit()
            return {"job_id": job_id, "status": result["status"]}
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.generate_export", base=DurableTask)
def generate_export(job_id: str) -> dict[str, Any]:
    """Generate an async public-data export file (off the API, ADR-052)."""
    return asyncio.run(_generate_export(_settings(), uuid.UUID(job_id)))


async def _purge_pii(settings: Settings) -> dict[str, int]:
    """Enforce PII retention windows (Step 8, docs/PII-DATA-INVENTORY.md)."""
    from tk_api.core.retention import purge_expired_pii

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            return await purge_expired_pii(session)
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.purge_expired_pii", base=DurableTask)
def purge_expired_pii() -> dict[str, Any]:
    """Daily beat: delete tokens/sessions/security events past retention."""
    counts = asyncio.run(_purge_pii(_settings()))
    return {"purged": counts}


async def _recover_stuck_media(settings: Settings) -> dict[str, int]:
    """Re-drive media stuck in ``pending_scan`` (worker lost/crashed)."""
    from tk_api.media import service as media_service
    from tk_api.media.storage import build_storage

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            replayed = await media_service.recover_stuck_media(
                session,
                settings=settings,
                storage=build_storage(settings),
            )
        result: dict[str, Any] = {
            "recovered": len(replayed),
            "media_ids": [str(m) for m in replayed],
        }
        return result
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.recover_stuck_jobs", base=DurableTask)
def recover_stuck_jobs() -> dict[str, Any]:
    """Beat loop (every 5 min): re-drive stuck media scans (Step 11)."""
    return asyncio.run(_recover_stuck_media(_settings()))


async def _govdata_import(settings: Settings, job_id: uuid.UUID) -> dict[str, Any]:
    """Run a queued govdata import off the HTTP request (Phase 19, spec §32)."""
    from tk_api.govdata import service as govdata_service
    from tk_api.govdata.models import GovImportJob

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            job = await session.get(GovImportJob, job_id)
            if job is None:
                return {"job_id": str(job_id), "status": "not_found"}
            result = await govdata_service.run_import(
                session,
                dataset_id=job.dataset_id,
                job_id=job.id,
                raw_payload={},
            )
            await session.commit()
            return {
                "job_id": str(job.id),
                "status": result.status,
                "rows_added": result.rows_added,
                "rows_rejected": result.rows_rejected,
            }
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.govdata_import", base=DurableTask)
def govdata_import(job_id: str) -> dict[str, Any]:
    """Execute a queued dataset import in the worker (large imports never run
    inside the HTTP request; idempotent via external keys + diff)."""
    return asyncio.run(_govdata_import(_settings(), uuid.UUID(job_id)))


async def _dispatch_webhooks(settings: Settings) -> dict[str, int]:
    from tk_api.integrations import webhooks as webhooks_module

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            return await webhooks_module.dispatch_due_webhooks(session, settings=settings)
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.dispatch_webhooks", base=DurableTask)
def dispatch_webhooks() -> dict[str, int]:
    """Beat loop: deliver due outbox events to signed webhook subscriptions
    (Phase 19 outbox pattern; retries + dead-letter per subscription)."""
    return asyncio.run(_dispatch_webhooks(_settings()))


@celery_app.task(name="tk_worker.ping")
def ping() -> dict[str, str]:
    """Compose health probe target."""
    import time

    return {"pong": str(int(time.time()))}


async def _intelligence_snapshot(settings: Settings) -> dict[str, Any]:
    """Phase 20 signal work: trends + anomalies + snapshots (beat hourly)."""
    from tk_api.intelligence.anomalies import AnomalyEngine
    from tk_api.intelligence.trends import TrendEngine

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            trend = TrendEngine()
            result = await trend.summarize(session, preset="30d")
            await trend.save_snapshot(session, result.items[0])
            anomalies = await AnomalyEngine().detect_all(session)
            events = await AnomalyEngine().persist(session, anomalies)
            await session.commit()
            return {
                "trend_direction": result.items[0].comparison.direction,
                "anomaly_events_saved": len(events),
            }
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.intelligence_snapshot", base=DurableTask)
def intelligence_snapshot() -> dict[str, Any]:
    """Beat hourly: computation forming the intelligence baseline."""
    return asyncio.run(_intelligence_snapshot(_settings()))


async def _intelligence_clusters(settings: Settings) -> dict[str, Any]:
    """Phase 20 issue clusters + recurrence detection (beat daily)."""
    from tk_api.intelligence.clusters import ClusterEngine, RecurringIssueEngine

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            clusters = await ClusterEngine().compute_clusters(session)
            saved = await ClusterEngine().save_clusters(session, clusters)
            recurring = await RecurringIssueEngine().detect(session)
            await session.commit()
            return {
                "clusters_saved": len(saved),
                "recurring_patterns": len(recurring),
            }
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.intelligence_clusters", base=DurableTask)
def intelligence_clusters() -> dict[str, Any]:
    """Beat daily: cluster + recurrence scan (summary views, nothing merges)."""
    return asyncio.run(_intelligence_clusters(_settings()))


async def _generate_intelligence_report(settings: Settings, report_id: uuid.UUID) -> dict[str, Any]:
    """Generate one pending intelligence report off the HTTP request."""
    from tk_api.intelligence.intel_reports import IntelligenceReportGenerator
    from tk_api.intelligence.models import IntelligenceReport
    from tk_api.media.storage import build_storage

    engine = _engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            report = await session.get(IntelligenceReport, report_id)
            if report is None:
                return {"report_id": str(report_id), "status": "not_found"}
            storage = build_storage(settings)

            def save_callback(key: str, blob: bytes) -> None:
                storage.save_bytes("tk-exports", key, blob)

            await IntelligenceReportGenerator().generate(
                session, report, save_callback=save_callback
            )
            await session.commit()
            return {
                "report_id": str(report.id),
                "status": report.status,
                "error": report.error,
            }
    finally:
        await engine.dispose()


@celery_app.task(name="tk_worker.generate_intelligence_report", base=DurableTask)
def generate_intelligence_report(report_id: str) -> dict[str, Any]:
    """Render an intelligence report (JSON/CSV) into the exports bucket."""
    return asyncio.run(_generate_intelligence_report(_settings(), uuid.UUID(report_id)))
