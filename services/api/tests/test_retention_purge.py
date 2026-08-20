"""PII retention purge tests (Step 8, docs/PII-DATA-INVENTORY.md).

Seeds auxiliary PII rows with old and recent timestamps and asserts the daily
purge deletes only what is past its retention window. Runs against the app's
engine (SQLite in unit tests, Postgres in integration runs)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tk_api.ai.models import AiConversation, AiMessage
from tk_api.auth.models import RefreshToken
from tk_api.core.db import create_session_factory
from tk_api.core.retention import (
    SESSION_RETENTION_DAYS,
    purge_expired_pii,
)
from tk_api.identity.models import (
    EmailVerification,
    PasswordResetToken,
    SecurityEvent,
)
from tk_api.identity.models import (
    Session as UserSession,
)
from tk_api.publicdata.models import PublicApiUsage
from tk_api.users.models import User

_MODELS = {
    "refresh_tokens": RefreshToken,
    "sessions": UserSession,
    "email_verifications": EmailVerification,
    "password_reset_tokens": PasswordResetToken,
    "security_events": SecurityEvent,
    "ai_conversations": AiConversation,
    "public_api_usage": PublicApiUsage,
}


@pytest.fixture
def _retention_rows(client):  # type: ignore[no-untyped-def]
    """Seed one old (purgable) and one recent (kept) row per table."""
    import asyncio

    old = datetime.now(UTC) - timedelta(days=400)
    stale_session = datetime.now(UTC) - timedelta(days=SESSION_RETENTION_DAYS + 30)

    async def seed() -> dict[str, tuple[uuid.UUID, uuid.UUID]]:
        factory = create_session_factory(client.app.state.engine)
        ids: dict[str, tuple[uuid.UUID, uuid.UUID]] = {}
        async with factory() as session:
            old_user = User(phone="9876000001", display_name="Old", status="active")
            recent_user = User(phone="9876000002", display_name="Recent", status="active")
            session.add_all([old_user, recent_user])
            await session.flush()

            pairs = {
                "refresh_tokens": (
                    RefreshToken(
                        user_id=old_user.id,
                        token_hash=uuid.uuid4().hex,
                        family_id=uuid.uuid4(),
                        expires_at=old,
                    ),
                    RefreshToken(
                        user_id=recent_user.id,
                        token_hash=uuid.uuid4().hex,
                        family_id=uuid.uuid4(),
                        expires_at=datetime.now(UTC) + timedelta(days=30),
                    ),
                ),
                "sessions": (
                    UserSession(
                        user_id=old_user.id,
                        client_id="old",
                        last_seen_at=stale_session,
                    ),
                    UserSession(
                        user_id=recent_user.id,
                        client_id="recent",
                        last_seen_at=datetime.now(UTC),
                    ),
                ),
                "email_verifications": (
                    EmailVerification(
                        user_id=old_user.id,
                        email="old@example.com",
                        code_hash="x",
                        expires_at=old,
                    ),
                    EmailVerification(
                        user_id=recent_user.id,
                        email="recent@example.com",
                        code_hash="y",
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                    ),
                ),
                "password_reset_tokens": (
                    PasswordResetToken(
                        user_id=old_user.id,
                        token_hash="a",
                        expires_at=old,
                    ),
                    PasswordResetToken(
                        user_id=recent_user.id,
                        token_hash="b",
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                    ),
                ),
                "security_events": (
                    SecurityEvent(user_id=old_user.id, event="LOGIN", ip="1.1.1.1", created_at=old),
                    SecurityEvent(
                        user_id=recent_user.id,
                        event="LOGIN",
                        ip="2.2.2.2",
                        created_at=datetime.now(UTC),
                    ),
                ),
                "ai_conversations": (
                    AiConversation(user_id=old_user.id, title="old", updated_at=old),
                    AiConversation(
                        user_id=recent_user.id,
                        title="recent",
                        updated_at=datetime.now(UTC),
                    ),
                ),
                "public_api_usage": (
                    PublicApiUsage(
                        endpoint="/public",
                        method="GET",
                        status_code=200,
                        latency_ms=5,
                        created_at=old,
                    ),
                    PublicApiUsage(
                        endpoint="/public",
                        method="GET",
                        status_code=200,
                        latency_ms=5,
                        created_at=datetime.now(UTC),
                    ),
                ),
            }
            for key, (old_row, recent_row) in pairs.items():
                session.add_all([old_row, recent_row])
                await session.flush()
                ids[key] = (old_row.id, recent_row.id)
            # one message inside the old conversation (must cascade away)
            session.add(
                AiMessage(
                    conversation_id=ids["ai_conversations"][0],
                    role="user",
                    content="private context",
                )
            )
            await session.commit()
        return ids

    return asyncio.run(seed())


def _run_purge(client):  # type: ignore[no-untyped-def]
    import asyncio

    async def run() -> dict[str, int]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            return await purge_expired_pii(session)

    return asyncio.run(run())


def _count(client, model, *ids):  # type: ignore[no-untyped-def]
    import asyncio

    from sqlalchemy import select

    async def count() -> int:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            result = await session.execute(select(model).where(model.id.in_(list(ids))))
            return len(result.scalars().all())

    return asyncio.run(count())


class TestRetentionPurge:
    def test_old_rows_purged_recent_rows_kept(self, client, _retention_rows) -> None:  # type: ignore[no-untyped-def]
        ids = _retention_rows
        counts = _run_purge(client)

        for key in ids:
            old_id, recent_id = ids[key]
            remaining = _count(client, _MODELS[key], old_id, recent_id)
            # the old row was purged, the recent row survives
            assert remaining == 1, f"{key}: expected only the recent row to remain"

        assert counts["refresh_tokens"] >= 1
        assert counts["sessions"] >= 1
        assert counts["email_verifications"] >= 1
        assert counts["password_reset_tokens"] >= 1
        assert counts["security_events"] >= 1
        assert counts["ai_conversations"] >= 1
        assert counts["public_api_usage"] >= 1

    def test_expired_refresh_token_within_window_kept(self, client, _retention_rows) -> None:  # type: ignore[no-untyped-def]
        """A token expired 30 days ago is past expiry but inside retention."""
        import asyncio

        from sqlalchemy import select

        old = datetime.now(UTC) - timedelta(days=30)
        token_id: uuid.UUID

        async def seed() -> uuid.UUID:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                user = User(phone="9876000003", display_name="Mid", status="active")
                session.add(user)
                await session.flush()
                token = RefreshToken(
                    user_id=user.id,
                    token_hash=uuid.uuid4().hex,
                    family_id=uuid.uuid4(),
                    expires_at=old,
                )
                session.add(token)
                await session.commit()
                return token.id

        token_id = asyncio.run(seed())
        _run_purge(client)

        async def remaining() -> int:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                result = await session.execute(
                    select(RefreshToken).where(RefreshToken.id == token_id)
                )
                return len(result.scalars().all())

        assert asyncio.run(remaining()) == 1
