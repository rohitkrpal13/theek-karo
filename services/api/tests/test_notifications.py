"""Notification tests (API.md §9): rendering, quiet hours, preferences,
enqueue-on-event hooks, worker dispatch with provider fakes + receipts."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.config import Settings
from tk_api.core.db import create_session_factory
from tk_api.notifications import queue as queue_mod
from tk_api.notifications.models import (
    Notification,
    NotificationPreference,
    NotificationQueue,
    NotificationReceipt,
)
from tk_api.notifications.providers import DeliveryResult
from tk_api.notifications.service import process_queue_row


def _grant(client: TestClient, user_id: str, code: str) -> None:  # type: ignore[no-untyped-def]
    from tk_api.users.models import Role, User, UserRole

    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _user(client: TestClient, sender, phone: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, phone)
    return tokens["user"]["id"], {"Authorization": f"Bearer {tokens['access_token']}"}


def _admin(client: TestClient, sender, phone: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    user_id, headers = _user(client, sender, phone)
    _grant(client, user_id, "admin")
    return user_id, headers


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        database_url="sqlite+aiosqlite://",
        log_level="WARNING",
        quiet_hours_default={"start": "21:00", "end": "07:00", "tz": "Asia/Kolkata"},
    )


class _RecordingProviders:
    """Fake provider objects (each exposes .send like the console sandbox)."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    class _Sms:
        def __init__(self, rec: _RecordingProviders) -> None:
            self._rec = rec

        def send(self, **kw):  # type: ignore[no-untyped-def]
            self._rec.sent.append((str(kw["to_contact"]), kw["body"]))
            return DeliveryResult(provider_message_id=str(kw["message_id"]))

    class _Email:
        def __init__(self, rec: _RecordingProviders) -> None:
            self._rec = rec

        def send(self, **kw):  # type: ignore[no-untyped-def]
            self._rec.sent.append((str(kw["to_contact"]), f"{kw['subject']}: {kw['body']}"))
            return DeliveryResult(provider_message_id=str(kw["message_id"]))


def _providers(recording: _RecordingProviders) -> dict[str, object]:
    return {
        "sms": _RecordingProviders._Sms(recording),
        "email": _RecordingProviders._Email(recording),
        "in_app": None,
    }


class TestRenderAndQuietHours:
    def test_render_interpolates_payload(self) -> None:
        body = "Your report {ticket_no} is now {status_label}"
        assert queue_mod.render(body, {"ticket_no": "TK-1", "status_label": "verified"}) == (
            "Your report TK-1 is now verified"
        )

    def test_quiet_hour_windows(self) -> None:
        default = {"start": "21:00", "end": "07:00", "tz": "Asia/Kolkata"}
        inside = datetime(2026, 8, 15, 17, 0, tzinfo=UTC)  # 22:30 IST
        outside = datetime(2026, 8, 15, 6, 30, tzinfo=UTC)  # 12:00 IST
        assert queue_mod.is_quiet_hour(inside, quiet_hours=None, default=default)
        assert not queue_mod.is_quiet_hour(outside, quiet_hours=None, default=default)
        # midnight wrap: 23:00 IST and 03:00 IST (same UTC day pair)
        assert queue_mod.is_quiet_hour(
            datetime(2026, 8, 15, 17, 30, tzinfo=UTC), quiet_hours=None, default=default
        )
        assert queue_mod.is_quiet_hour(
            datetime(2026, 8, 14, 21, 30, tzinfo=UTC), quiet_hours=None, default=default
        )

    def test_event_group_mapping(self) -> None:
        assert queue_mod.event_group_for("report.status_change") == "status_change"
        assert queue_mod.event_group_for("report.comment") == "collaboration"
        assert queue_mod.event_group_for("ai.review") == "ai"


class TestPreferences:
    def test_defaults_and_update(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, headers = _user(client, sender, "9876546201")
        prefs = client.get("/api/v1/notifications/preferences", headers=headers)
        assert prefs.status_code == 200, prefs.text
        body = prefs.json()
        assert body["channels"]["sms"]["status_change"]["enabled"] is True

        patched = client.patch(
            "/api/v1/notifications/preferences",
            json={"status_change": {"sms": False}},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["channels"]["sms"]["status_change"]["enabled"] is False

        quiet = client.patch(
            "/api/v1/notifications/preferences",
            json={
                "collaboration": {
                    "sms": {"enabled": True, "quiet_hours": {"start": "22:00", "end": "06:00"}}
                }
            },
            headers=headers,
        )
        assert quiet.status_code == 200
        sms = quiet.json()["channels"]["sms"]["collaboration"]
        assert sms["quiet_hours"]["start"] == "22:00"

        bad = client.patch(
            "/api/v1/notifications/preferences",
            json={"bogus_group": {"sms": False}},
            headers=headers,
        )
        assert bad.status_code == 422

    def test_preferences_require_auth(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get("/api/v1/notifications/preferences").status_code == 401


class TestHooksAndDispatch:
    def test_status_and_verification_events_enqueue(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        admin_headers = _admin(client, sender, "9876546202")[1]
        reporter_id, reporter = _user(client, sender, "9876546203")
        category = client.post(
            "/api/v1/civic/categories",
            json={
                "slug": "school",
                "icon": "school",
                "form_schema": {"type": "object", "required": [], "properties": {}},
                "verification_policy": {"min_verifications": 2},
                "attachment_rules": {},
            },
            headers=admin_headers,
        )
        assert category.status_code == 201, category.text

        submitted = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "school",
                "title": "Broken classroom windows on ground floor",
                "description": "Windows on the ground floor remain broken since May "
                "with sharp edges",
                "location": {"type": "Point", "coordinates": [75.7873, 26.9124]},
                "location_accuracy_m": 12,
                "fields": {},
            },
            headers=reporter,
        )
        assert submitted.status_code == 201, submitted.text
        report_id = submitted.json()["id"]

        verifier = _user(client, sender, "9876546204")[1]
        vote = client.post(
            f"/api/v1/reports/{report_id}/verifications",
            json={"kind": "confirm"},
            headers=verifier,
        )
        assert vote.status_code == 201, vote.text
        # verification auto-promoted submitted → under_verification; admins may
        # take it to verified (an allowed edge)
        changed = client.post(
            f"/api/v1/reports/{report_id}/transition",
            json={"to_status": "verified"},
            headers=admin_headers,
        )
        assert changed.status_code == 200, changed.text

        async def collect() -> tuple[list[str], list[dict]]:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                rows = (
                    (
                        await session.execute(
                            select(NotificationQueue)
                            .where(NotificationQueue.user_id == uuid.UUID(reporter_id))
                            .order_by(NotificationQueue.created_at.asc())
                        )
                    )
                    .scalars()
                    .all()
                )
                return [r.event for r in rows], [r.payload for r in rows]

        events, payloads = asyncio.run(collect())
        assert "report.verification" in events
        assert "report.status_change" in events
        assert any("ticket_no" in p for p in payloads)

    def test_dispatch_writes_inapp_and_receipts(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        user_id, headers = _user(client, sender, "9876546205")
        settings = Settings(
            _env_file=None,
            env="test",
            database_url="sqlite+aiosqlite://",
            log_level="WARNING",
            quiet_hours_default={"start": "00:00", "end": "00:00", "tz": "UTC"},
        )
        recording = _RecordingProviders()

        async def seed_and_dispatch() -> tuple[int, int]:
            from tk_api.notifications import service as ns

            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                await ns.enqueue(
                    session,
                    user_id=uuid.UUID(user_id),
                    event="report.status_change",
                    locale="en",
                    payload={"ticket_no": "TK-TEST-1", "status": "verified"},
                    channels=["in_app", "sms", "email"],
                )
                await session.commit()
                rows = (await session.execute(select(NotificationQueue))).scalars().all()
                for row in rows:
                    await process_queue_row(
                        session, row=row, settings=settings, providers=_providers(recording)
                    )
                await session.commit()
                notifications = (await session.execute(select(Notification))).scalars().all()
                return len(notifications), len(recording.sent)

        inapp, delivered = asyncio.run(seed_and_dispatch())
        assert inapp == 3  # history rows for in_app + sms + email
        assert delivered == 2  # sms + email via sandbox fakes

        history = client.get("/api/v1/notifications", headers=headers)
        assert history.status_code == 200
        assert any(n["event"] == "report.status_change" for n in history.json()["items"])

        async def count_receipts() -> int:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                return len((await session.execute(select(NotificationReceipt))).scalars().all())

        assert asyncio.run(count_receipts()) == 2

    def test_dispatch_respects_quiet_hours(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        user_id, _ = _user(client, sender, "9876546206")
        settings = _settings()
        recording = _RecordingProviders()

        async def run() -> None:
            from tk_api.notifications import service as ns

            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                session.add(
                    NotificationPreference(
                        user_id=uuid.UUID(user_id),
                        channel="sms",
                        event_group="status_change",
                        enabled=True,
                        quiet_hours={"start": "00:00", "end": "23:59", "tz": "Asia/Kolkata"},
                    )
                )
                await ns.enqueue(
                    session,
                    user_id=uuid.UUID(user_id),
                    event="report.status_change",
                    locale="en",
                    payload={"ticket_no": "T1"},
                    channels=["sms"],
                )
                await session.commit()
                rows = (await session.execute(select(NotificationQueue))).scalars().all()
                for row in rows:
                    await process_queue_row(
                        session, row=row, settings=settings, providers=_providers(recording)
                    )
                await session.commit()
                row = (await session.execute(select(NotificationQueue))).scalars().first()
                assert row is not None and row.attempts >= 1  # deferred, not delivered
                assert row.next_attempt_at is not None

        asyncio.run(run())
        assert recording.sent == []

    def test_deferred_row_deliverable_when_quiet_hours_disabled(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        """A row the worker deferred (quiet hours, future ``next_attempt_at``)
        must still deliver when dispatched with quiet hours disabled. This is
        the guarantee the PG integration test relies on to stay deterministic
        regardless of time of day (compose worker vs test dispatch race)."""
        user_id, _ = _user(client, sender, "9876546208")
        recording = _RecordingProviders()

        async def run() -> None:
            from tk_api.notifications import service as ns

            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                await ns.enqueue(
                    session,
                    user_id=uuid.UUID(user_id),
                    event="report.status_change",
                    locale="en",
                    payload={"ticket_no": "T3"},
                    channels=["sms"],
                )
                await session.commit()
                row = (await session.execute(select(NotificationQueue))).scalars().one()
                # simulate the worker's quiet-hours deferral
                row.attempts += 1
                row.next_attempt_at = datetime.now(UTC) + timedelta(hours=12)
                await session.commit()

                disabled = Settings(
                    _env_file=None,
                    env="test",
                    database_url="sqlite+aiosqlite://",
                    log_level="WARNING",
                    quiet_hours_default={"start": "00:00", "end": "00:00", "tz": "UTC"},
                )
                await process_queue_row(
                    session, row=row, settings=disabled, providers=_providers(recording)
                )
                await session.commit()
                row = (await session.execute(select(NotificationQueue))).scalars().one()
                assert row.status == "done"
                assert row.delivered_at is not None

        asyncio.run(run())
        assert len(recording.sent) == 1

    def test_receipts_endpoint(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        user_id, _ = _user(client, sender, "9876546207")

        async def seed() -> str:
            from tk_api.notifications import service as ns

            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                await ns.enqueue(
                    session,
                    user_id=uuid.UUID(user_id),
                    event="report.comment",
                    locale="en",
                    payload={"ticket_no": "T2"},
                    channels=["in_app"],
                )
                await session.commit()
                rows = (await session.execute(select(NotificationQueue))).scalars().all()
                recording = _RecordingProviders()
                for row in rows:
                    await process_queue_row(
                        session, row=row, settings=_settings(), providers=_providers(recording)
                    )
                await session.commit()
                n = (await session.execute(select(Notification))).scalars().first()
                assert n is not None
                return str(n.id)

        notification_id = asyncio.run(seed())
        receipt = client.post(
            "/api/v1/notifications/receipts",
            json={"notification_id": notification_id, "channel": "sms", "status": "delivered"},
        )
        assert receipt.status_code == 200
        assert receipt.json()["status"] == "delivered"
        bad = client.post(
            "/api/v1/notifications/receipts",
            json={"channel": "sms", "status": "delivered"},
        )
        assert bad.status_code == 422
