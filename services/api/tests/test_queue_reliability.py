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
            social_broadcast,
        )

        for task in (
            dispatch_due_notifications,
            process_media,
            recover_stuck_jobs,
            social_broadcast,
        ):
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


class TestSocialBroadcastRecovery:
    def test_lost_redis_task_recovered_from_postgres_without_duplicates(self, client) -> None:  # type: ignore[no-untyped-def]
        import asyncio
        from decimal import Decimal
        from unittest.mock import patch

        from tk_api.civic.models import Category
        from tk_api.reports.broadcast_service import recover_stuck_broadcasts
        from tk_api.reports.models import Report, SocialBroadcast

        async def scenario() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                user = User(
                    phone=f"98{uuid.uuid4().hex[:8]}",
                    display_name="RecovUser",
                    status="active",
                )
                session.add(user)
                cat = Category(
                    slug=f"cat_{uuid.uuid4().hex[:6]}",
                    icon="alert",
                    form_schema={"type": "object"},
                    verification_policy={"policy": "threshold"},
                    default_locale_keys={"name": "Drainage"},
                )
                session.add(cat)
                await session.flush()

                report = Report(
                    ticket_no=f"TK-REC-{uuid.uuid4().hex[:4]}",
                    title="Collapsed Manhole",
                    description="Deep hazard on pedestrian walkway.",
                    category_id=cat.id,
                    severity="high",
                    status="submitted",
                    visibility="public",
                    reporter_id=user.id,
                    location={"type": "Point", "coordinates": [77.5946, 12.9716]},
                    location_accuracy_m=Decimal("5.0"),
                )
                session.add(report)
                await session.flush()

                # Seed an orphaned queued broadcast older than 10 mins (lost broker task simulation)
                ten_mins_ago = datetime.now(UTC) - timedelta(minutes=15)
                b = SocialBroadcast(
                    report_id=report.id,
                    requested_by=user.id,
                    network="x",
                    tone="urgent",
                    status="queued",
                    post_text="Urgent hazard",
                    attempts=0,
                    max_attempts=3,
                    created_at=ten_mins_ago,
                    updated_at=ten_mins_ago,
                )
                session.add(b)
                await session.commit()
                await session.refresh(b)
                b_id = b.id

                # Run recovery sweep with mock Celery app
                with patch("tk_api.worker.celery_app.send_task") as mock_send:
                    recovered = await recover_stuck_broadcasts(
                        session,
                        settings=client.app.state.settings.model_copy(
                            update={"celery_enabled": True}
                        ),
                        max_age_seconds=600,
                    )
                    assert b_id in recovered
                    mock_send.assert_called_once_with(
                        "tk_worker.social_broadcast", args=[str(b_id)]
                    )

                # Verify single updated row in PostgreSQL (no duplicate records)
                reloaded = await session.get(SocialBroadcast, b_id)
                assert reloaded is not None
                assert reloaded.status == "queued"
                assert "Recovered from stranded state" in str(reloaded.last_error)

        asyncio.run(scenario())

    def test_recovery_exhaustion_marks_failed(self, client) -> None:  # type: ignore[no-untyped-def]
        import asyncio
        from decimal import Decimal

        from tk_api.civic.models import Category
        from tk_api.reports.broadcast_service import recover_stuck_broadcasts
        from tk_api.reports.models import Report, SocialBroadcast

        async def scenario() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                user = User(
                    phone=f"98{uuid.uuid4().hex[:8]}",
                    display_name="ExhaustUser",
                    status="active",
                )
                session.add(user)
                cat = Category(
                    slug=f"cat_{uuid.uuid4().hex[:6]}",
                    icon="alert",
                    form_schema={"type": "object"},
                    verification_policy={"policy": "threshold"},
                    default_locale_keys={"name": "Roads"},
                )
                session.add(cat)
                await session.flush()

                report = Report(
                    ticket_no=f"TK-EXH-{uuid.uuid4().hex[:4]}",
                    title="Exhausted Task Hazard",
                    description="Deep hazard test.",
                    category_id=cat.id,
                    severity="critical",
                    status="submitted",
                    visibility="public",
                    reporter_id=user.id,
                    location={"type": "Point", "coordinates": [77.5946, 12.9716]},
                    location_accuracy_m=Decimal("5.0"),
                )
                session.add(report)
                await session.flush()

                ten_mins_ago = datetime.now(UTC) - timedelta(minutes=15)
                b = SocialBroadcast(
                    report_id=report.id,
                    requested_by=user.id,
                    network="x",
                    tone="urgent",
                    status="queued",
                    post_text="Urgent hazard",
                    attempts=3,
                    max_attempts=3,
                    created_at=ten_mins_ago,
                    updated_at=ten_mins_ago,
                )
                session.add(b)
                await session.commit()
                await session.refresh(b)
                b_id = b.id

                recovered = await recover_stuck_broadcasts(
                    session,
                    settings=client.app.state.settings,
                    max_age_seconds=600,
                )
                assert b_id in recovered

                reloaded = await session.get(SocialBroadcast, b_id)
                assert reloaded is not None
                assert reloaded.status == "failed"
                assert "reached maximum attempts" in str(reloaded.last_error)

        asyncio.run(scenario())
