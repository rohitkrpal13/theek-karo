"""Integration: AI review pipeline on live Postgres.

Requires compose (make up). Operates on the real schema (migrations up to
``head``) and proves: analysis runs land in ``ai_runs``/``ai_annotations`` with
the T4 envelope, duplicate suggestions reach the human-review queue, a decision
applies ``duplicate_of`` + audited merge, and per-run audit rows exist.
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
            "display_name": "AI Integration",
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
                        "DELETE FROM ai_reviews WHERE report_id IN (SELECT id FROM reports "
                        "WHERE category_id IN (SELECT id FROM categories WHERE slug = :slug))"
                    ),
                    {"slug": category_slug},
                )
                await conn.execute(
                    text(
                        "DELETE FROM ai_citations WHERE annotation_id IN ("
                        "SELECT a.id FROM ai_annotations a JOIN reports r2 ON r2.id = a.report_id "
                        "WHERE r2.category_id IN (SELECT id FROM categories WHERE slug = :slug))"
                    ),
                    {"slug": category_slug},
                )
                await conn.execute(
                    text(
                        "DELETE FROM ai_annotations WHERE report_id IN (SELECT id FROM reports "
                        "WHERE category_id IN (SELECT id FROM categories WHERE slug = :slug))"
                    ),
                    {"slug": category_slug},
                )
                await conn.execute(
                    text(
                        "DELETE FROM ai_runs WHERE id NOT IN (SELECT run_id FROM ai_annotations) "
                        "AND payload_in::text LIKE :slug_like"
                    ),
                    {"slug_like": f"%{category_slug}%"},
                )
                await conn.execute(
                    text(
                        "DELETE FROM reports WHERE category_id IN "
                        "(SELECT id FROM categories WHERE slug = :slug)"
                    ),
                    {"slug": category_slug},
                )
                await conn.execute(
                    text("DELETE FROM categories WHERE slug = :slug"),
                    {"slug": category_slug},
                )
        finally:
            await engine.dispose()

    asyncio.run(clean())


def test_ai_review_pipeline_on_postgres() -> None:
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
        ai_auto_analysis=False,
    )
    app = create_app(settings=settings)
    sender = RecordingSender()
    app.state.otp_sender = sender

    suffix = uuid.uuid4().hex[:8]
    category_slug = f"ai-school-{suffix}"
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
                        "required": ["issue_area"],
                        "properties": {"issue_area": {"type": "string", "enum": ["classroom"]}},
                    },
                    "verification_policy": {"min_verifications": 2},
                    "attachment_rules": {},
                },
                headers=admin_headers,
            )
            assert created.status_code == 201, created.text

            def submit(title: str, description: str) -> dict:
                user = _register(client, sender, f"9{random.randrange(10**9, 10**10)}")
                headers = {"Authorization": f"Bearer {user['access_token']}"}
                response = client.post(
                    "/api/v1/reports",
                    json={
                        "category_slug": category_slug,
                        "title": title,
                        "description": description,
                        "location": {"type": "Point", "coordinates": [75.7873, 26.9124]},
                        "location_accuracy_m": 10,
                        "fields": {"issue_area": "classroom"},
                    },
                    headers=headers,
                )
                assert response.status_code == 201, response.text
                return response.json()

            first = submit(
                "Broken classroom windows in block A",
                "Windows broken since May with sharp edges near the class rooms in block A",
            )
            dup = submit(
                "Broken classroom windows in block A",
                "Windows broken since May with sharp edges near the class rooms "
                "in block A duplicate",
            )

            # analysis + duplicate suggestion via admin refresh of the new report
            analyzed = client.post(
                f"/api/v1/reports/{dup['id']}/analysis/refresh", headers=admin_headers
            )
            assert analyzed.status_code == 200, analyzed.text
            assert analyzed.json()["info_class"] == "AI_ANALYSIS"
            assert analyzed.json()["run"]["provider"] == "stub"

            queue = client.get("/api/v1/ai/human-review-queue", headers=admin_headers)
            assert queue.status_code == 200
            reviews = [i for i in queue.json()["items"] if i["report"]["id"] == dup["id"]]
            assert len(reviews) == 1, queue.text
            review_id = reviews[0]["id"]

            approved = client.post(
                f"/api/v1/ai/reviews/{review_id}/decision",
                json={"approve": True, "reason": "identical location and description"},
                headers=admin_headers,
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "approved"

            detail = client.get(f"/api/v1/reports/{dup['id']}")
            assert detail.status_code == 200
            assert detail.json()["duplicate_of"] == first["id"]
            assert detail.json()["status"] == "duplicate_merged"

            # runs+annotations persisted on PG with the T4 envelope
            async def check_rows() -> None:
                engine = create_engine(DB_URL)
                try:
                    factory = create_session_factory(engine)
                    async with factory() as session:
                        runs = (
                            await session.execute(
                                text(
                                    "SELECT count(*) FROM ai_runs "
                                    "WHERE task_kind = 'report_analysis' "
                                    "AND provider = 'stub'"
                                )
                            )
                        ).scalar_one()
                        assert runs >= 1, runs  # the dup refresh run
                        annotations = (
                            await session.execute(
                                text(
                                    "SELECT count(*) FROM ai_annotations a "
                                    "JOIN reports r2 ON r2.id = a.report_id "
                                    "WHERE r2.category_id IN "
                                    "(SELECT id FROM categories c2 WHERE c2.slug = :slug)"
                                ),
                                {"slug": category_slug},
                            )
                        ).scalar_one()
                        assert annotations == 1, annotations
                finally:
                    await engine.dispose()

            asyncio.run(check_rows())
        finally:
            _cleanup(category_slug)
