"""Integration: notifications + worker on live Postgres/Redis.

Requires compose (make up) with the worker container running. Proves:
queue rows on PG, worker dispatch (beat or direct), in-app history + receipts,
and a true Celery broker round-trip via ``send_task``.
"""

from __future__ import annotations

import asyncio
import os
import random
import uuid

import pytest

pytestmark = pytest.mark.integration

DB_URL = os.environ.get(
    "TK_TEST_DATABASE_URL", "postgresql+asyncpg://tk:tk_dev_password@127.0.0.1:5434/theek_karo"
)


def _postgres_reachable() -> bool:
    from sqlalchemy.ext.asyncio import create_async_engine

    from tk_api.core.db import ping_database

    async def check() -> bool:
        engine = create_async_engine(DB_URL)
        try:
            await ping_database(engine)
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _postgres_reachable(), reason="compose postgres not running (make up)"),
]


def _run_migrations() -> None:
    from alembic.config import Config

    from alembic import command

    old = os.environ.get("TK_DATABASE_URL")
    os.environ["TK_DATABASE_URL"] = DB_URL
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if old is None:
            os.environ.pop("TK_DATABASE_URL", None)
        else:
            os.environ["TK_DATABASE_URL"] = old


def _register(client, sender, phone: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "contact": phone,
            "display_name": "Notify Integration",
            "password": "s3cure-pass!",
            "consent": True,
            "terms_version": "2026-08-01",
        },
    )
    assert response.status_code == 201, response.text
    code = sender.sent[-1][1]
    tokens = client.post("/api/v1/auth/verify-otp", json={"contact": phone, "code": code})
    assert tokens.status_code == 200, tokens.text
    return tokens.json()


def _cleanup(category_slug: str) -> None:
    async def clean() -> None:
        from sqlalchemy import text

        from tk_api.core.db import create_engine, create_session_factory

        engine = create_engine(DB_URL)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                for statement in [
                    "DELETE FROM notification_receipts WHERE notification_id IN "
                    "(SELECT id FROM notifications)",
                    "DELETE FROM notifications",
                    "DELETE FROM notification_queue",
                    "DELETE FROM ai_reviews",
                    "DELETE FROM ai_citations",
                    "DELETE FROM ai_annotations",
                    "DELETE FROM ai_runs",
                    "DELETE FROM reports",
                    "DELETE FROM campaigns WHERE category_id IN "
                    "(SELECT id FROM categories WHERE slug = :slug)",
                    "DELETE FROM categories WHERE slug = :slug",
                ]:
                    await session.execute(text(statement), {"slug": category_slug})
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(clean())


def test_notifications_on_postgres_and_worker_round_trip() -> None:
    _run_migrations()
    from fastapi.testclient import TestClient

    from tests.conftest import RecordingSender
    from tk_api.core.config import Settings
    from tk_api.main import create_app

    settings = Settings(
        _env_file=None,
        env="test",
        log_level="WARNING",
        database_url=DB_URL,
        rate_limit_mode="memory",
        jwt_secret="test-secret-not-for-prod",
        celery_enabled=False,
    )
    app = create_app(settings=settings)
    sender = RecordingSender()
    app.state.otp_sender = sender

    suffix = uuid.uuid4().hex[:8]
    category_slug = f"notify-school-{suffix}"
    with TestClient(app) as client:
        try:
            admin = _register(client, sender, f"9{random.randrange(10**9, 10**10)}")
            admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
            reporter = _register(client, sender, f"9{random.randrange(10**9, 10**10)}")
            reporter_headers = {"Authorization": f"Bearer {reporter['access_token']}"}

            create_role_sql = (
                "INSERT INTO user_roles (user_id, role_id, granted_at) "
                "SELECT :user_id, id, now() FROM roles WHERE code = 'admin'"
            )
            from sqlalchemy import text

            from tk_api.core.db import create_engine, create_session_factory

            async def grant() -> None:
                engine = create_engine(DB_URL)
                try:
                    factory = create_session_factory(engine)
                    async with factory() as session:
                        await session.execute(
                            text(create_role_sql), {"user_id": admin["user"]["id"]}
                        )
                        await session.commit()
                finally:
                    await engine.dispose()

            asyncio.run(grant())

            created = client.post(
                "/api/v1/civic/categories",
                json={
                    "slug": category_slug,
                    "icon": "school",
                    "form_schema": {"type": "object", "required": [], "properties": {}},
                    "verification_policy": {"min_verifications": 2},
                    "attachment_rules": {},
                },
                headers=admin_headers,
            )
            assert created.status_code == 201, created.text

            submitted = client.post(
                "/api/v1/reports",
                json={
                    "category_slug": category_slug,
                    "title": "Broken classroom windows on ground floor",
                    "description": "Windows on the ground floor remain broken since May "
                    "with sharp edges",
                    "location": {"type": "Point", "coordinates": [75.7873, 26.9124]},
                    "location_accuracy_m": 10,
                    "fields": {},
                },
                headers=reporter_headers,
            )
            assert submitted.status_code == 201, submitted.text
            report_id = submitted.json()["id"]

            # volunteer role so the state machine walk is legal for the admin? admin suffices
            transition = client.post(
                f"/api/v1/reports/{report_id}/transition",
                json={"to_status": "under_verification"},
                headers=admin_headers,
            )
            assert transition.status_code == 200, transition.text

            # queue rows exist on PG for the reporter
            queue_count = asyncio.run(
                _count_rows(
                    "SELECT count(*) FROM notification_queue WHERE user_id = :uid",
                    {"uid": reporter["user"]["id"]},
                )
            )
            assert queue_count >= 1, queue_count

            # in-app + sandbox dispatch via the worker service path
            from tk_api.core.config import Settings as WorkerSettings
            from tk_api.notifications import service as notifications_service
            from tk_api.notifications.providers import build_providers

            async def dispatch() -> int:
                engine = create_engine(DB_URL)
                try:
                    factory = create_session_factory(engine)
                    async with factory() as session:
                        worker_settings = WorkerSettings(
                            _env_file=None,
                            env="test",
                            database_url=DB_URL,
                            quiet_hours_default={
                                "start": "00:00",
                                "end": "00:00",
                                "tz": "UTC",
                            },
                        )
                        providers = build_providers(worker_settings)
                        providers["in_app"] = None
                        return await notifications_service.dispatch_due(
                            session, settings=worker_settings, providers=providers
                        )
                finally:
                    await engine.dispose()

            # drain queue rows until this report's notifications exist (the
            # compose worker may also be dispatching concurrently)
            reporter_id_uuid = uuid.UUID(reporter["user"]["id"])
            for _ in range(5):
                asyncio.run(dispatch())
                found = asyncio.run(
                    _count_rows(
                        "SELECT count(*) FROM notifications "
                        "WHERE event = 'report.status_change' AND user_id = :uid",
                        {"uid": reporter_id_uuid},
                    )
                )
                if found:
                    break

            # Deterministic sms/email receipts regardless of time of day: the
            # compose worker may have already delivered these rows (receipts
            # exist) or deferred them inside its quiet-hours window
            # (21:00-07:00 IST default, next_attempt_at pushed +12h). Force-
            # deliver any still-queued rows with quiet hours disabled so the
            # receipt assertion below never depends on the wall clock.
            async def deliver_deferred() -> None:
                from sqlalchemy import select

                from tk_api.core.config import Settings as WorkerSettings
                from tk_api.notifications import service as notifications_service
                from tk_api.notifications.models import NotificationQueue
                from tk_api.notifications.providers import build_providers

                engine = create_engine(DB_URL)
                try:
                    factory = create_session_factory(engine)
                    async with factory() as session:
                        rows = (
                            (
                                await session.execute(
                                    select(NotificationQueue).where(
                                        NotificationQueue.user_id == reporter_id_uuid,
                                        NotificationQueue.channel.in_(["sms", "email"]),
                                        NotificationQueue.status == "queued",
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                        worker_settings = WorkerSettings(
                            _env_file=None,
                            env="test",
                            database_url=DB_URL,
                            quiet_hours_default={
                                "start": "00:00",
                                "end": "00:00",
                                "tz": "UTC",
                            },
                        )
                        providers = build_providers(worker_settings)
                        providers["in_app"] = None
                        for row in rows:
                            await notifications_service.process_queue_row(
                                session,
                                row=row,
                                settings=worker_settings,
                                providers=providers,
                            )
                        await session.commit()
                finally:
                    await engine.dispose()

            asyncio.run(deliver_deferred())

            # history visible through the API
            async def dump_rows() -> list:
                from sqlalchemy import text

                from tk_api.core.db import create_engine

                engine = create_engine(DB_URL)
                try:
                    async with engine.connect() as conn:
                        rows = (
                            await conn.execute(
                                text(
                                    "SELECT user_id, event, channel FROM notifications "
                                    "ORDER BY created_at"
                                )
                            )
                        ).all()
                        return [dict(r._mapping) for r in rows]
                finally:
                    await engine.dispose()

            probe = asyncio.run(dump_rows())
            history = client.get("/api/v1/notifications", headers=reporter_headers)
            assert history.status_code == 200, history.text
            if not history.json()["items"]:
                raise AssertionError(f"no history; notifications rows={probe}")

            receipts = asyncio.run(_count_rows("SELECT count(*) FROM notification_receipts", {}))
            assert receipts >= 1  # sms/email sandbox deliveries

            # true broker round-trip: the compose worker executes tk_worker.ping
            from tk_api.worker import celery_app

            result = celery_app.send_task("tk_worker.ping")
            pong = result.get(timeout=20)
            assert "pong" in pong, pong
        finally:
            _cleanup(category_slug)


async def _count_rows(sql: str, params: dict) -> int:
    from sqlalchemy import text

    from tk_api.core.db import create_engine, create_session_factory

    engine = create_engine(DB_URL)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            rows = await session.execute(text(sql), params)
            return int(rows.scalar_one())
    finally:
        await engine.dispose()
