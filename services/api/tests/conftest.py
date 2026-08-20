"""Shared test fixtures.

Unit tests run against an in-memory SQLite database (fast, no external services);
``integration``-marked tests require compose postgres (ADR-026). Auth tests read OTP
codes from a recording sender attached to ``app.state.otp_sender``.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from tk_api.core.config import Settings
from tk_api.core.db import Base
from tk_api.main import create_app
from tk_api.users.models import Role

TEST_DATABASE_URL = "postgresql+asyncpg://tk:tk@127.0.0.1:59999/theek_karo"

ROLE_CODES = [
    "citizen",
    "volunteer",
    "verified_contributor",
    "moderator",
    "institution_representative",
    "department_representative",
    "department_manager",
    "reviewer",
    "analyst",
    "admin",
    "super_admin",
    "official",
]


def _register(client: TestClient, sender: RecordingSender, contact: str, **extra) -> dict:
    payload = {
        "contact": contact,
        "display_name": "Amit Sharma",
        "password": "s3cure-pass!",
        "consent": True,
        "terms_version": "2026-08-01",
        **extra,
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _verify(client: TestClient, sender: RecordingSender, contact: str) -> dict:
    code = last_otp(sender, contact)
    response = client.post("/api/v1/auth/verify-otp", json={"contact": contact, "code": code})
    assert response.status_code == 200, response.text
    return response.json()


def _register_and_verify(client: TestClient, sender: RecordingSender, contact: str) -> dict:
    _register(client, sender, contact)
    return _verify(client, sender, contact)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        log_level="WARNING",
        database_url="sqlite+aiosqlite://",
        rate_limit_mode="memory",
        otp_channel="console",
        jwt_secret="test-secret-not-for-prod",
    )


class RecordingSender:
    """Captures sent OTP codes; mimics ConsoleOtpSender API."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, contact: str, code: str, *, purpose: str) -> None:
        self.sent.append((contact, code, purpose))


def _build_app(settings: Settings):
    import tk_api.core.models  # noqa: F401 - register the full schema (incl. Phase-3 domains)

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            for code in ROLE_CODES:
                session.add(Role(code=code, name=code.capitalize()))
            await session.commit()

    asyncio.run(init_schema())
    app = create_app(settings=settings, engine=engine)
    return app, engine


@pytest.fixture
def app_with_db(settings: Settings):
    app, engine = _build_app(settings)
    yield app
    asyncio.run(engine.dispose())


@pytest.fixture
def client(app_with_db) -> TestClient:  # type: ignore[no-untyped-def]
    sender = RecordingSender()
    app_with_db.state.otp_sender = sender
    with TestClient(app_with_db) as test_client:
        test_client._recording_sender = sender  # type: ignore[attr-defined]
        yield test_client


@pytest.fixture
def sender(client) -> RecordingSender:  # type: ignore[no-untyped-def]
    return client._recording_sender  # type: ignore[attr-defined]


def last_otp(sender: RecordingSender, contact: str) -> str:
    if contact.isdigit() or contact.startswith("+"):
        digits = "".join(ch for ch in contact if ch.isdigit())
        normalized = "+91" + digits if len(digits) == 10 else "+" + digits
    else:
        normalized = contact.strip().lower()
    for c, code, _purpose in reversed(sender.sent):
        if c == normalized:
            return code
    raise AssertionError(f"no OTP sent for {contact}")
