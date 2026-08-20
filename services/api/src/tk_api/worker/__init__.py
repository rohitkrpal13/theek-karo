"""Celery application (ADR-005): Redis broker, JSON serialization.

The worker runs in its own compose container (same image as the API) and owns
the durable jobs: notification dispatch, media scan + thumbnails, AI analysis,
measurement rollups. The API enqueues via ``send_task`` when
``TK_CELERY_ENABLED=true`` and falls back to in-process jobs otherwise (tests,
single-process dev).

Queue reliability (Step 11):

- ``task_acks_late`` + ``task_reject_on_worker_lost`` give at-least-once
  delivery — a worker that dies mid-task leaves the message unacked and it is
  redelivered.
- Durable tasks inherit :class:`DurableTask`: transient exceptions are retried
  with exponential backoff + jitter (max 3 attempts); business failures return
  status strings instead of raising, so they are never blindly retried.
- When retries are exhausted, ``on_failure`` writes the dead task into the
  Redis dead-letter list ``tk:dlq`` (inspected with ``LRANGE tk:dlq 0 -1``)
  and logs at ERROR. No worker consumes ``tk:dlq`` — it is a dead letter by
  design, reviewed by ops.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, ClassVar

from celery import Celery, Task  # type: ignore[import-untyped]

import tk_api.core.models  # noqa: F401 - register every table so deferred ORM FKs resolve in-worker
from tk_api.core.config import Settings, get_settings
from tk_api.core.logging import configure_logging
from tk_api.core.rate_limit import try_redis

_settings = get_settings()
# Structured JSON logs on stdout in the worker too (Step 13), so CloudWatch/
# compose logs are single-line JSON from both processes.
configure_logging(_settings.log_level)
_broker = os.environ.get("TK_CELERY_BROKER_URL", _settings.celery_broker_url)
_result_backend = f"{_broker.rsplit('/', 1)[0]}/2"

DLQ_LIST = "tk:dlq"
DLQ_MAX_RECORDS = 1000  # cap so a broken task cannot grow Redis unboundedly

_logger = logging.getLogger("tk_api.worker")


class DurableTask(Task):  # type: ignore[misc]  # celery ships no type stubs
    """Base task: transient retries with backoff, dead-letter on exhaustion.

    Tasks that hit a permanent business failure must *return* a status rather
    than raise, so ``autoretry_for`` only ever re-runs transient infrastructure
    errors (DB/Redis/provider outages).
    """

    autoretry_for: ClassVar[tuple[type[BaseException], ...]] = (Exception,)
    retry_backoff: ClassVar[bool] = True
    retry_backoff_max: ClassVar[int] = 300
    retry_jitter: ClassVar[bool] = True
    max_retries: ClassVar[int] = 3
    reject_on_worker_lost: ClassVar[bool] = True
    acks_late: ClassVar[bool] = True

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # type: ignore[no-untyped-def]
        record = dead_letter_record(
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            exc=exc,
        )
        _logger.error(
            "task %s (%s) failed after retries; dead-lettered",
            self.name,
            task_id,
            exc_info=exc,
        )
        _push_dead_letter(record)


def dead_letter_record(
    *, task_id: str, task_name: str, args: Any, kwargs: Any, exc: BaseException
) -> dict[str, Any]:
    """Structured dead-letter record (Step 11)."""
    return {
        "task_id": str(task_id),
        "task_name": task_name,
        "args": [str(a) for a in (args or ())],
        "kwargs": {k: str(v) for k, v in (kwargs or {}).items()},
        "error": str(exc)[:1000],
    }


def _push_dead_letter(record: dict[str, Any]) -> None:
    """Best-effort append to the Redis DLQ list (never raises into Celery)."""
    try:
        client = None
        loop = None
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = loop.run_until_complete(try_redis(get_settings()))
            if client is not None:
                loop.run_until_complete(client.lpush(DLQ_LIST, json.dumps(record)))
                loop.run_until_complete(client.ltrim(DLQ_LIST, 0, DLQ_MAX_RECORDS - 1))
        finally:
            if client is not None and loop is not None:
                loop.run_until_complete(client.aclose())
            if loop is not None:
                loop.close()
    except Exception:
        _logger.exception("could not write dead-letter record to Redis")


celery_app = Celery(
    "tk_worker",
    broker=_broker,
    backend=_result_backend,
    include=["tk_api.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_default_queue="tk_jobs",
    task_time_limit=180,
    task_soft_time_limit=150,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    broker_connection_retry_on_startup=True,
    # beat runs as uid 10001 with a read-only /app — schedule file goes to
    # /tmp (nosec B108: container has a dedicated writable tmpfs; /app is ro)
    beat_schedule_filename="/tmp/celerybeat-schedule",  # nosec B108
    beat_schedule={
        "dispatch-notifications": {
            "task": "tk_worker.dispatch_due_notifications",
            "schedule": 60.0,
        },
        "measurement-rollup-daily": {
            "task": "tk_worker.measurement_rollup_all",
            "schedule": 3600.0,
        },
        "evaluate-sla-due": {
            "task": "tk_worker.evaluate_sla_due",
            "schedule": 60.0,
        },
        "purge-expired-pii": {
            "task": "tk_worker.purge_expired_pii",
            "schedule": 86400.0,  # daily: PII retention enforcement
        },
        "recover-stuck-jobs": {
            "task": "tk_worker.recover_stuck_jobs",
            "schedule": 300.0,  # every 5 min: re-drive stuck pending_scan media
        },
        # Phase 19 integrations: deliver outbox events to signed webhook
        # subscriptions (retries + dead-letter per subscription).
        "dispatch-webhooks": {
            "task": "tk_worker.dispatch_webhooks",
            "schedule": 60.0,
        },
        # Phase 20 civic intelligence: hourly signal work (trends + anomalies),
        # daily cluster/recurrence scan.
        "intelligence-snapshot": {
            "task": "tk_worker.intelligence_snapshot",
            "schedule": 3600.0,
        },
        "intelligence-clusters": {
            "task": "tk_worker.intelligence_clusters",
            "schedule": 86400.0,
        },
        # Phase 23 data trust: quality sweep (daily), source health (every 4h),
        # quarantine review (daily).
        "data-quality-sweep": {
            "task": "tk_worker.data_quality_sweep",
            "schedule": 86400.0,
        },
        "source-health-snapshots": {
            "task": "tk_worker.source_health_snapshots",
            "schedule": 14400.0,
        },
        "quarantine-review-check": {
            "task": "tk_worker.quarantine_review_check",
            "schedule": 86400.0,
        },
    },
)


def settings() -> Settings:
    return get_settings()
