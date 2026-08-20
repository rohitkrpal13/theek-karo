"""Queue reliability tests (Step 11).

Covers: (1) the stuck-media recovery sweep re-drives media whose worker scan
never completed, (2) Celery's at-least-once + retry configuration, and (3) the
dead-letter record shape written to the Redis DLQ list.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, datetime, timedelta

from PIL import Image

from tk_api.core.db import create_session_factory
from tk_api.media.models import MediaObject
from tk_api.media.service import (
    STUCK_SCAN_THRESHOLD_MINUTES,
    recover_stuck_media,
)
from tk_api.media.storage import MemoryStorageAdapter
from tk_api.users.models import User
from tk_api.worker import DLQ_LIST, dead_letter_record


def _jpeg_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (32, 32), "green").save(stream, format="JPEG")
    return stream.getvalue()


def _seed_pending_media(client, storage: MemoryStorageAdapter, *, age_minutes: int):  # type: ignore[no-untyped-def]
    """Insert a pending_scan MediaObject (optionally old) + its bytes."""
    import asyncio

    data = _jpeg_bytes()
    media_id: uuid.UUID

    async def insert() -> tuple[uuid.UUID, str]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            user = User(phone=f"98{uuid.uuid4().hex[:8]}", display_name="Q", status="active")
            session.add(user)
            await session.flush()
            key = f"media/2026/08/{uuid.uuid4().hex}"
            media = MediaObject(
                bucket=client.app.state.settings.media_minio_bucket,
                object_key=key,
                checksum_sha256="",
                mime_type="image/jpeg",
                size_bytes=len(data),
                scan_status="pending",
                status="pending_scan",
                uploaded_by=user.id,
            )
            if age_minutes:
                media.updated_at = datetime.now(UTC) - timedelta(minutes=age_minutes)
            session.add(media)
            await session.commit()
            return media.id, key

    media_id, key = asyncio.run(insert())
    storage.save_bytes(client.app.state.settings.media_minio_bucket, key, data)
    return media_id


def _recover(client, storage: MemoryStorageAdapter) -> list[uuid.UUID]:  # type: ignore[no-untyped-def]
    async def run() -> list[uuid.UUID]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            return await recover_stuck_media(
                session,
                settings=client.app.state.settings,
                storage=storage,
            )

    return asyncio.run(run())


def _status(client, media_id: uuid.UUID) -> str:  # type: ignore[no-untyped-def]
    import asyncio

    async def read() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            media = await session.get(MediaObject, media_id)
            return media.status if media else "missing"

    return asyncio.run(read())


class TestStuckMediaRecovery:
    def test_old_pending_scan_recovered_recent_untouched(self, client) -> None:  # type: ignore[no-untyped-def]
        storage = MemoryStorageAdapter()
        client.app.state.storage = storage
        old_id = _seed_pending_media(client, storage, age_minutes=STUCK_SCAN_THRESHOLD_MINUTES + 5)
        recent_id = _seed_pending_media(client, storage, age_minutes=1)

        recovered = _recover(client, storage)

        assert old_id in recovered
        assert recent_id not in recovered
        assert _status(client, old_id) == "available"
        assert _status(client, recent_id) == "pending_scan"

    def test_recovery_is_idempotent(self, client) -> None:  # type: ignore[no-untyped-def]
        storage = MemoryStorageAdapter()
        client.app.state.storage = storage
        old_id = _seed_pending_media(client, storage, age_minutes=STUCK_SCAN_THRESHOLD_MINUTES + 5)

        _recover(client, storage)
        second = _recover(client, storage)

        assert old_id not in second  # nothing left stuck
        assert _status(client, old_id) == "available"


class TestCeleryDurabilityConfig:
    def test_at_least_once_and_retry_settings(self) -> None:  # type: ignore[no-untyped-def]
        from tk_api.worker import celery_app

        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.task_reject_on_worker_lost is True
        assert celery_app.conf.task_default_retry_delay == 30

    def test_durable_tasks_inherit_base(self) -> None:  # type: ignore[no-untyped-def]
        from tk_api.worker import DurableTask
        from tk_api.worker.tasks import (
            dispatch_due_notifications,
            process_media,
            recover_stuck_jobs,
        )

        for task in (dispatch_due_notifications, process_media, recover_stuck_jobs):
            assert task.max_retries == DurableTask.max_retries
            assert task.acks_late is True


class TestDeadLetterRecord:
    def test_record_shape(self) -> None:  # type: ignore[no-untyped-def]
        record = dead_letter_record(
            task_id="t1",
            task_name="tk_worker.process_media",
            args=("abc-123",),
            kwargs={"force": True},
            exc=TimeoutError("provider timeout"),
        )
        assert record["task_id"] == "t1"
        assert record["task_name"] == "tk_worker.process_media"
        assert record["args"] == ["abc-123"]
        assert record["kwargs"] == {"force": "True"}
        assert "provider timeout" in record["error"]

    def test_dlq_key_constant(self) -> None:  # type: ignore[no-untyped-def]
        assert DLQ_LIST == "tk:dlq"
