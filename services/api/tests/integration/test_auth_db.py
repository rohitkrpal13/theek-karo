"""Integration test: full auth lifecycle against real Postgres.

Requires compose (make up) + migrations applied. The test runs alembic upgrade head
itself so the schema is always current.
"""

import os
import random

import pytest

pytestmark = pytest.mark.integration

DB_URL = os.environ.get(
    "TK_TEST_DATABASE_URL", "postgresql+asyncpg://tk:tk_dev_password@127.0.0.1:5434/theek_karo"
)


def _postgres_reachable() -> bool:
    import asyncio

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
    import os as _os

    from alembic.config import Config

    from alembic import command

    old = _os.environ.get("TK_DATABASE_URL")
    _os.environ["TK_DATABASE_URL"] = DB_URL
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if old is None:
            _os.environ.pop("TK_DATABASE_URL", None)
        else:
            _os.environ["TK_DATABASE_URL"] = old


def test_full_auth_lifecycle_on_postgres() -> None:
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
    )
    app = create_app(settings=settings)
    sender = RecordingSender()
    app.state.otp_sender = sender
    phone = f"9{random.randint(100000000, 999999999)}"

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "contact": phone,
                "display_name": "Integration",
                "password": "s3cure-pass!",
                "consent": True,
                "terms_version": "2026-08-01",
            },
        )
        assert response.status_code == 201
        code = sender.sent[-1][1]
        response = client.post("/api/v1/auth/verify-otp", json={"contact": phone, "code": code})
        assert response.status_code == 200
        tokens = response.json()
        assert tokens["user"]["roles"] == ["citizen"]

        auth = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = client.get("/api/v1/users/me", headers=auth)
        assert response.status_code == 200
        assert response.json()["status"] == "active"

        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 200
        second = response.json()["refresh_token"]

        response = client.post("/api/v1/auth/logout", json={"refresh_token": second}, headers=auth)
        assert response.status_code == 200

        response = client.post("/api/v1/auth/refresh", json={"refresh_token": second})
        assert response.status_code == 401

        response = client.post(
            "/api/v1/auth/login", json={"contact": phone, "password": "s3cure-pass!"}
        )
        assert response.status_code == 200
