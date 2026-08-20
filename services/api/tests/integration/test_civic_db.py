"""Integration: civic engine + PostGIS foundation against live Postgres.

Requires compose (make up). Runs alembic upgrade head so the schema is current,
then exercises the civic API on real Postgres and verifies PostGIS spatial
queries + GIST indexes (ROADMAP Phase 4 exit criteria).
"""

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


def _grant_admin(user_id: uuid.UUID) -> None:
    import asyncio as _asyncio

    from sqlalchemy import text

    from tk_api.core.db import create_engine, create_session_factory

    async def grant() -> None:
        engine = create_engine(DB_URL)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO user_roles (user_id, role_id, granted_at) "
                        "SELECT :user_id, id, now() FROM roles WHERE code = 'admin'"
                    ),
                    {"user_id": user_id},
                )
                await session.commit()
        finally:
            await engine.dispose()

    _asyncio.run(grant())


def test_civic_lifecycle_on_postgres() -> None:
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
    suffix = random.randint(1000, 9999)
    category_slug = f"school-{suffix}"
    campaign_slug = f"schools-of-jaipur-{suffix}"

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "contact": phone,
                "display_name": "Civic Admin",
                "password": "s3cure-pass!",
                "consent": True,
                "terms_version": "2026-08-01",
            },
        )
        assert response.status_code == 201
        code = sender.sent[-1][1]
        tokens = client.post(
            "/api/v1/auth/verify-otp", json={"contact": phone, "code": code}
        ).json()
        admin = {"Authorization": f"Bearer {tokens['access_token']}"}
        _grant_admin(uuid.UUID(tokens["user"]["id"]))

        category = client.post(
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
                "attachment_rules": {"max_files": 4, "max_size_mb": 8},
            },
            headers=admin,
        )
        assert category.status_code == 201, category.text
        category_id = category.json()["id"]

        campaign = client.post(
            "/api/v1/civic/campaigns",
            json={
                "category_id": category_id,
                "slug": campaign_slug,
                "title_key": "campaign.schools_jaipur_2026.title",
                "scope": {"state": "RJ", "district": "Jaipur"},
            },
            headers=admin,
        )
        assert campaign.status_code == 201, campaign.text
        assert campaign.json()["materialized_scope"] == {
            "boundary_id": None,
            "district": "Jaipur",
            "state": "RJ",
        }

        assert (
            client.patch(
                f"/api/v1/civic/campaigns/{campaign.json()['id']}",
                json={"status": "live"},
                headers=admin,
            ).status_code
            == 200
        )

        public_list = client.get("/api/v1/civic/campaigns?status=live")
        assert public_list.status_code == 200
        # id-desc ordering: the freshly created campaign is somewhere in the page
        assert campaign.json()["id"] in {item["id"] for item in public_list.json()["items"]}
        assert client.get(f"/api/v1/civic/categories/{category_slug}").status_code == 200


def test_postgis_spatial_queries_and_indexes() -> None:
    _run_migrations()
    import asyncio as _asyncio

    from sqlalchemy import text

    from tk_api.core.db import create_engine

    async def run() -> None:
        engine = create_engine(DB_URL)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("BEGIN"))
                version = (await conn.execute(text("SELECT postgis_version()"))).scalar_one()
                assert version.startswith("3.4"), version

                locales = (await conn.execute(text("SELECT count(*) FROM locales"))).scalar_one()
                assert locales == 10, locales

                user_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO users (id, display_name, status, created_at, updated_at) "
                        "VALUES (:id, 'spatial-tester', 'active', now(), now())"
                    ),
                    {"id": user_id},
                )
                category_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO categories (id, slug, icon, form_schema, verification_policy, "
                        "attachment_rules, default_locale_keys, created_at, updated_at) "
                        "VALUES (:id, 'spatial', 'pin', '{}', '{}', '{}', '{}', now(), now())"
                    ),
                    {"id": category_id},
                )
                for rid, lon, lat in ((uuid.uuid4(), 77.2, 28.6), (uuid.uuid4(), 77.5, 28.6)):
                    await conn.execute(
                        text(
                            "INSERT INTO reports (id, ticket_no, category_id, reporter_id, title, "
                            "description, location, location_accuracy_m, created_at, updated_at) "
                            "VALUES (:id, :ticket, :cat, :user, 'title', 'description', "
                            "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 10, now(), now())"
                        ),
                        {
                            "id": rid,
                            "ticket": f"TK-{rid}",
                            "cat": category_id,
                            "user": user_id,
                            "lon": lon,
                            "lat": lat,
                        },
                    )
                count = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM reports WHERE ST_DWithin("
                            "location::geography, "
                            "ST_SetSRID(ST_MakePoint(77.2, 28.6), 4326)::geography, 1000)"
                        )
                    )
                ).scalar_one()
                assert count == 1, count

                gist_indexes = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM pg_indexes WHERE tablename = 'reports' "
                            "AND indexdef ILIKE '%USING gist%'"
                        )
                    )
                ).scalar_one()
                assert gist_indexes == 1, gist_indexes
                await conn.rollback()
        finally:
            await engine.dispose()

    _asyncio.run(run())
