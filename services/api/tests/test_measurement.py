"""Measurement tests (API.md §10): live overview aggregates + campaign trend snapshots."""

from __future__ import annotations

import asyncio
import random
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "school",
    "icon": "school",
    "form_schema": {
        "type": "object",
        "required": ["title"],
        "properties": {"title": {"type": "string", "minLength": 10}},
    },
    "verification_policy": {"min_verifications": 2},
    "attachment_rules": {},
}

LOCATION = {"type": "Point", "coordinates": [75.7873, 26.9124]}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user_headers(client: TestClient, sender) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, f"9{random.randrange(10**9, 10**10)}")
    return _auth(tokens["access_token"])


def _grant(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _admin_headers(client: TestClient, sender) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, f"9{random.randrange(10**9, 10**10)}")
    _grant(client, tokens["user"]["id"], "admin")
    return _auth(tokens["access_token"])


def _setup_category_and_campaign(client: TestClient, sender) -> tuple[str, dict]:  # type: ignore[no-untyped-def]
    admin = _admin_headers(client, sender)
    created = client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin)
    assert created.status_code == 201, created.text
    category_id = created.json()["id"]
    campaign = client.post(
        "/api/v1/civic/campaigns",
        json={
            "category_id": category_id,
            "slug": f"meas-{uuid.uuid4().hex[:8]}",
            "title_key": "campaign.meas.title",
            "scope": {"state": "RJ"},
        },
        headers=admin,
    )
    assert campaign.status_code == 201, campaign.text
    return category_id, campaign.json()


def _submit(
    client: TestClient, headers: dict[str, str], category_slug: str, campaign_id: str | None
) -> dict:  # type: ignore[no-untyped-def]
    payload = {
        "category_slug": category_slug,
        "title": "Broken classroom windows on the ground floor",
        "description": "Windows on the ground floor remain broken since May with sharp edges",
        "location": LOCATION,
        "location_accuracy_m": 12,
        "fields": {"title": "Broken classroom windows"},
    }
    if campaign_id:
        payload["campaign_id"] = campaign_id
    response = client.post("/api/v1/reports", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _walk_to_resolved(client: TestClient, sender, report_id: str) -> None:  # type: ignore[no-untyped-def]
    volunteer_tokens = _register_and_verify(client, sender, f"9{random.randrange(10**9, 10**10)}")
    _grant(client, volunteer_tokens["user"]["id"], "volunteer")
    volunteer = _auth(volunteer_tokens["access_token"])
    official_tokens = _register_and_verify(client, sender, f"9{random.randrange(10**9, 10**10)}")
    _grant(client, official_tokens["user"]["id"], "official")
    official = _auth(official_tokens["access_token"])

    for to, headers in (
        ("under_verification", volunteer),
        ("verified", volunteer),
        ("assigned", official),
        ("in_progress", official),
        ("resolved", official),
    ):
        response = client.post(
            f"/api/v1/reports/{report_id}/transition",
            json={"to_status": to},
            headers=headers,
        )
        assert response.status_code == 200, response.text


class TestOverview:
    def test_overview_aggregates(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _category_id, campaign = _setup_category_and_campaign(client, sender)
        headers = _user_headers(client, sender)
        _submit(client, headers, "school", campaign["id"])
        _submit(client, headers, "school", campaign["id"])
        resolved_report = _submit(client, headers, "school", campaign["id"])
        _walk_to_resolved(client, sender, resolved_report["id"])

        overview = client.get("/api/v1/measurement/overview")
        assert overview.status_code == 200
        body = overview.json()
        category = next(c for c in body["categories"] if c["slug"] == "school")
        assert category["volume"] == 3  # type: ignore[index]
        assert category["resolution_rate"] == round(1 / 3, 4)
        assert category["median_resolve_hours"] == 0.0  # type: ignore[index]

        campaigns = [c for c in body["campaigns"] if c["id"] == campaign["id"]]
        assert len(campaigns) == 1
        assert campaigns[0]["volume"] == 3  # type: ignore[index]

    def test_campaign_trend_materializes_snapshot(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, campaign = _setup_category_and_campaign(client, sender)
        headers = _user_headers(client, sender)
        _submit(client, headers, "school", campaign["id"])

        trend = client.get(f"/api/v1/measurement/campaign/{campaign['id']}")
        assert trend.status_code == 200
        body = trend.json()
        assert body["campaign_id"] == campaign["id"]
        assert len(body["snapshots"]) == 1
        assert body["snapshots"][0]["metrics"]["volume"] == 1

        # second call returns the same immutable snapshot set
        again = client.get(f"/api/v1/measurement/campaign/{campaign['id']}")
        assert again.status_code == 200
        assert len(again.json()["snapshots"]) == 1

    def test_campaign_missing_404(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"/api/v1/measurement/campaign/{uuid.uuid4()}").status_code == 404
