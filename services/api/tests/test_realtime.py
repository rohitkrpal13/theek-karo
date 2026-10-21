"""Realtime super-power: live activity + bulk + SSE handshake."""

from fastapi.testclient import TestClient


def _citizen_headers(client: TestClient, sender) -> dict[str, str]:
    import random

    phone = f"9{random.randint(100000000, 999999999)}"
    # register
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "contact": phone,
            "display_name": "Test Citizen",
            "password": "s3cure-pass!",
            "consent": True,
            "terms_version": "2026-08-01",
        },
    )
    assert resp.status_code == 201, resp.text
    # verify via recording sender
    from tests.conftest import last_otp

    code = last_otp(sender, phone)
    resp = client.post("/api/v1/auth/verify-otp", json={"contact": phone, "code": code})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(client: TestClient, sender) -> dict[str, str]:
    import asyncio
    import random

    phone = f"9{random.randint(100000000, 999999999)}"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "contact": phone,
            "display_name": "Admin User",
            "password": "s3cure-pass!",
            "consent": True,
            "terms_version": "2026-08-01",
        },
    )
    assert resp.status_code == 201, resp.text
    from tests.conftest import last_otp

    code = last_otp(sender, phone)
    resp = client.post("/api/v1/auth/verify-otp", json={"contact": phone, "code": code})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    user_id = data["user"]["id"]
    # grant admin via DB
    from sqlalchemy import select

    async def grant():
        from tk_api.core.db import create_session_factory

        # reuse engine from app
        engine = client.app.state.engine  # type: ignore[attr-defined]
        factory = create_session_factory(engine)
        async with factory() as session:
            import uuid

            from tk_api.users.models import Role, UserRole

            role = await session.scalar(select(Role).where(Role.code == "admin"))
            assert role is not None
            session.add(UserRole(user_id=uuid.UUID(user_id), role_id=role.id))
            await session.commit()

    asyncio.run(grant())
    # re-login to get fresh token with role
    resp = client.post("/api/v1/auth/login", json={"contact": phone, "password": "s3cure-pass!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _ensure_category(client: TestClient, sender) -> str:
    # try list first
    resp = client.get("/api/v1/civic/categories")
    if resp.status_code == 200 and resp.json():
        items = resp.json()
        if isinstance(items, list) and items:
            return items[0]["id"]
        if isinstance(items, dict) and items.get("items"):
            return items["items"][0]["id"]
    # create via admin (reuse ph18 shape)
    admin_h = _admin_headers(client, sender)
    slug = f"rt-{__import__('uuid').uuid4().hex[:6]}"
    resp = client.post(
        "/api/v1/civic/categories",
        json={
            "slug": slug,
            "icon": "rt",
            "form_schema": {
                "type": "object",
                "required": ["title", "description"],
                "properties": {
                    "title": {"type": "string", "minLength": 10},
                    "description": {"type": "string", "minLength": 25},
                },
                "additionalProperties": False,
            },
            "verification_policy": {"min_verifications": 2, "min_locale_diversity": 1},
            "attachment_rules": {"max_files": 4, "max_size_mb": 8},
        },
        headers=admin_h,
    )
    if resp.status_code == 201:
        return resp.json()["id"]
    if resp.status_code == 409:
        # fetch existing
        for cat in client.get("/api/v1/civic/categories").json().get("items", []):
            if cat["slug"] == slug:
                return cat["id"]
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def test_live_activity_empty(client: TestClient):
    resp = client.get("/api/v1/live/activity?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "has_more" in body
    assert "next_cursor" in body
    assert isinstance(body["items"], list)


def test_live_activity_limit_validation(client: TestClient):
    resp = client.get("/api/v1/live/activity?limit=100")
    assert resp.status_code == 422


def test_bulk_validation(client: TestClient, sender):
    headers = _citizen_headers(client, sender)
    # empty
    resp = client.post("/api/v1/reports/bulk", json={"items": []}, headers=headers)
    assert resp.status_code == 422
    # over limit
    resp = client.post(
        "/api/v1/reports/bulk", json={"items": [{"title": "a"}] * 26}, headers=headers
    )
    assert resp.status_code == 422
    # title too short
    resp = client.post("/api/v1/reports/bulk", json={"items": [{"title": "ab"}]}, headers=headers)
    assert resp.status_code == 422


def test_bulk_create_success(client: TestClient, sender):
    headers = _citizen_headers(client, sender)
    cat_id = _ensure_category(client, sender)
    resp = client.post(
        "/api/v1/reports/bulk",
        json={
            "items": [
                {"title": "Bulk report 1 valid title", "description": "desc", "category_id": cat_id}
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    assert len(body["created"]) == 1
    assert "ticket_no" in body["created"][0]


def test_stream_reports_smoke(client: TestClient):
    resp = client.get("/api/v1/reports/stream?limit=2")
    assert resp.status_code == 200
    assert "x-ndjson" in resp.headers.get("content-type", "")
    text = resp.text.strip()
    if text:
        lines = text.split("\n")
        assert len(lines) >= 1


def test_live_stats(client: TestClient):
    resp = client.get("/api/v1/live/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "reports_24h" in data
    assert "open_reports" in data
    assert "resolved_24h" in data
    assert "velocity_rate" in data
    assert "generated_at" in data


def test_event_bus_and_broadcast(client: TestClient):
    import asyncio

    from tk_api.core.events import InMemoryEventBus, broadcast_live_event, get_event_bus

    app = client.app  # type: ignore[attr-defined]
    bus = get_event_bus(app)
    assert isinstance(bus, InMemoryEventBus)

    async def scenario():
        q = await bus.register()
        try:
            await broadcast_live_event(app, "test.event", {"hello": "world"})
            item = await asyncio.wait_for(q.get(), timeout=2.0)
            assert item["event"] == "test.event"
            assert item["data"]["hello"] == "world"
        finally:
            await bus.unregister(q)

    asyncio.run(scenario())
