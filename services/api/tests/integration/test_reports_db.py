"""Integration: report lifecycle + spatial round-trip on live Postgres.

Requires compose (make up). Proves the ORM LocationPoint path stores real
PostGIS geometry on PG (WKB binding via the TypeDecorator) and that proximity
queries in meters work through ``ST_DWithin`` with a ``::geography`` cast
(ADR-027: geometry 4326 distances are in degrees).
"""

from __future__ import annotations

import asyncio
import os
import random
import uuid

import pytest
from sqlalchemy import text

from tk_api.core.db import create_engine, create_session_factory

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


def _grant_role(user_id: uuid.UUID, code: str) -> None:
    async def grant() -> None:
        engine = create_engine(DB_URL)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO user_roles (user_id, role_id, granted_at) "
                        "SELECT :user_id, id, now() FROM roles WHERE code = :code"
                    ),
                    {"user_id": user_id, "code": code},
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(grant())


def _register(client, sender, phone: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "contact": phone,
            "display_name": "Integration User",
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
        engine = create_engine(DB_URL)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "DELETE FROM report_media WHERE report_id IN "
                        "(SELECT id FROM reports WHERE category_id IN "
                        "(SELECT id FROM categories WHERE slug = :slug))"
                    ),
                    {"slug": category_slug},
                )
                await conn.execute(
                    text(
                        "DELETE FROM reports WHERE category_id IN "
                        "(SELECT id FROM categories WHERE slug = :slug)"
                    ),
                    {"slug": category_slug},
                )
                await conn.execute(
                    text(
                        "DELETE FROM campaigns WHERE category_id IN "
                        "(SELECT id FROM categories WHERE slug = :slug)"
                    ),
                    {"slug": category_slug},
                )
                await conn.execute(
                    text("DELETE FROM categories WHERE slug = :slug"), {"slug": category_slug}
                )
        finally:
            await engine.dispose()

    asyncio.run(clean())


def test_report_lifecycle_and_spatial_round_trip() -> None:
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

    suffix = uuid.uuid4().hex[:8]
    category_slug = f"integration-school-{suffix}"
    with TestClient(app) as client:
        try:
            admin = _register(client, sender, f"9{random.randrange(10**9, 10**10)}")
            _grant_role(uuid.UUID(admin["user"]["id"]), "admin")
            admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

            created = client.post(
                "/api/v1/civic/categories",
                json={
                    "slug": category_slug,
                    "icon": "school",
                    "form_schema": {
                        "type": "object",
                        "required": ["title"],
                        "properties": {"title": {"type": "string", "minLength": 10}},
                    },
                    "verification_policy": {"min_verifications": 2},
                    "attachment_rules": {},
                },
                headers=admin_headers,
            )
            assert created.status_code == 201, created.text

            reporter = _register(client, sender, f"9{random.randrange(10**9, 10**10)}")
            reporter_headers = {"Authorization": f"Bearer {reporter['access_token']}"}
            lon, lat = 75.7873, 26.9124  # Jaipur
            submitted = client.post(
                "/api/v1/reports",
                json={
                    "category_slug": category_slug,
                    "title": "Broken classroom windows on the ground floor",
                    "description": "Windows on the ground floor remain broken since May"
                    " with sharp edges",
                    "location": {"type": "Point", "coordinates": [lon, lat]},
                    "location_accuracy_m": 12,
                    "fields": {"title": "Broken classroom windows"},
                },
                headers=reporter_headers,
            )
            assert submitted.status_code == 201, submitted.text
            report_id = submitted.json()["id"]

            verifier = _register(client, sender, f"9{random.randrange(10**9, 10**10)}")
            verifier_headers = {"Authorization": f"Bearer {verifier['access_token']}"}
            vote = client.post(
                f"/api/v1/reports/{report_id}/verifications",
                json={"kind": "confirm", "evidence": "seen during a school visit"},
                headers=verifier_headers,
            )
            assert vote.status_code == 201, vote.text

            # spatial round-trip: the ORM stored a real PostGIS point; ST_DWithin in
            # meters (geography cast) matches near points and rejects far ones
            async def proximity_check() -> None:
                engine = create_engine(DB_URL)
                try:
                    async with engine.connect() as conn:
                        near = await conn.execute(
                            text(
                                "SELECT ST_DWithin(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
                                "::geography, "
                                "location::geography, 1000) FROM reports WHERE id = :rid"
                            ),
                            {"lon": lon + 0.001, "lat": lat, "rid": report_id},
                        )
                        assert near.scalar_one() is True
                        far = await conn.execute(
                            text(
                                "SELECT ST_DWithin(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
                                "::geography, "
                                "location::geography, 1000) FROM reports WHERE id = :rid"
                            ),
                            {"lon": lon + 1.0, "lat": lat, "rid": report_id},
                        )
                        assert far.scalar_one() is False
                finally:
                    await engine.dispose()

            asyncio.run(proximity_check())

            detail = client.get(f"/api/v1/reports/{report_id}")
            assert detail.status_code == 200
            body = detail.json()
            assert body["location"] == {"type": "Point", "coordinates": [lon, lat]}
            assert body["status"] == "under_verification"
        finally:
            _cleanup(category_slug)
