"""Civic engine tests: categories/campaigns as configuration data (API.md §4, ADR-003)."""

import asyncio
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
        "required": ["title", "description"],
        "properties": {
            "title": {"type": "string", "minLength": 10},
            "description": {"type": "string", "minLength": 25},
        },
    },
    "verification_policy": {"min_verifications": 2, "min_locale_diversity": 1},
    "attachment_rules": {
        "max_files": 4,
        "max_size_mb": 8,
        "mime": ["image/jpeg", "image/png", "image/webp"],
    },
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(client: TestClient, user_id: str) -> None:
    async def promote() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == "admin"))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(promote())


def _admin_headers(client: TestClient, sender) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, "9876543390")
    _promote_to_admin(client, tokens["user"]["id"])
    return _auth(tokens["access_token"])


class TestCategories:
    def test_empty_list_is_empty(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/api/v1/civic/categories")
        assert response.status_code == 200
        assert response.json() == {"items": [], "next_cursor": None}

    def test_admin_can_create_and_list(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["slug"] == "school"
        assert body["form_schema_version"] == 1
        assert body["default_locale_keys"] == {
            "label_key": "category.school",
            "description_key": "category.school.description",
        }

        listing = client.get("/api/v1/civic/categories")
        assert listing.status_code == 200
        assert [c["slug"] for c in listing.json()["items"]] == ["school"]

        detail = client.get("/api/v1/civic/categories/school")
        assert detail.status_code == 200
        assert detail.json()["verification_policy"] == CATEGORY["verification_policy"]

    def test_create_requires_admin(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.post("/api/v1/civic/categories", json=CATEGORY)
        assert response.status_code == 401

    def test_citizen_cannot_create(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543391")
        response = client.post(
            "/api/v1/civic/categories", json=CATEGORY, headers=_auth(tokens["access_token"])
        )
        assert response.status_code == 403
        assert response.json()["type"].endswith("/forbidden")

    def test_duplicate_slug_conflict(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        created = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
        assert created.status_code == 201
        response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
        assert response.status_code == 409
        assert response.json()["type"].endswith("/slug_conflict")

    def test_invalid_payloads_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        bad_slug = {**CATEGORY, "slug": "Bad Slug!"}
        bad_slug_response = client.post("/api/v1/civic/categories", json=bad_slug, headers=headers)
        assert bad_slug_response.status_code == 422
        bad_schema = {**CATEGORY, "form_schema": {"type": "array"}}
        response = client.post("/api/v1/civic/categories", json=bad_schema, headers=headers)
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_form_schema")
        bad_policy = {**CATEGORY, "verification_policy": {"min_verifications": -1}}
        assert (
            client.post("/api/v1/civic/categories", json=bad_policy, headers=headers).status_code
            == 422
        )
        bad_rules = {**CATEGORY, "attachment_rules": {"mime": "image/jpeg"}}
        assert (
            client.post("/api/v1/civic/categories", json=bad_rules, headers=headers).status_code
            == 422
        )

    def test_update_bumps_schema_version_and_audits(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        created = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers).json()
        response = client.patch(
            f"/api/v1/civic/categories/{created['id']}",
            json={
                "form_schema": {
                    **CATEGORY["form_schema"],
                    "properties": {"extra": {"type": "string"}},
                },
                "is_active": False,
            },
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["form_schema_version"] == 2
        assert response.json()["is_active"] is False

        assert client.get("/api/v1/civic/categories").json()["items"] == []
        assert client.get("/api/v1/civic/categories/school").status_code == 404
        admin_view = client.get("/api/v1/civic/categories/school", headers=headers)
        assert admin_view.status_code == 200
        assert admin_view.json()["is_active"] is False

        assert client.get("/api/v1/civic/categories?include_inactive=true").status_code == 403
        assert (
            client.get(
                "/api/v1/civic/categories?include_inactive=true", headers=headers
            ).status_code
            == 200
        )

    def test_update_unknown_category_404(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        response = client.patch(
            f"/api/v1/civic/categories/{uuid.uuid4()}", json={"icon": "x"}, headers=headers
        )
        assert response.status_code == 404
        assert response.json()["type"].endswith("/category_not_found")

    def test_empty_update_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        created = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers).json()
        response = client.patch(
            f"/api/v1/civic/categories/{created['id']}", json={}, headers=headers
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/empty_update")

    def test_create_audited(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
        audit = client.get("/api/v1/users/me/audit", headers=headers).json()["items"]
        assert any(
            item["action"] == "category.create" and item["entity_type"] == "category"
            for item in audit
        )


class TestCampaigns:
    def _create_category(self, client, sender, headers) -> str:  # type: ignore[no-untyped-def]
        return client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers).json()["id"]

    def test_create_get_list_and_transitions(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        category_id = self._create_category(client, sender, headers)
        payload = {
            "category_id": category_id,
            "slug": "schools-of-jaipur-2026",
            "title_key": "campaign.schools_jaipur_2026.title",
            "scope": {"state": "RJ", "district": "Jaipur"},
        }
        response = client.post("/api/v1/civic/campaigns", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        campaign = response.json()
        assert campaign["status"] == "planned"
        assert campaign["materialized_scope"] == {
            "boundary_id": None,
            "district": "Jaipur",
            "state": "RJ",
        }

        detail = client.get(f"/api/v1/civic/campaigns/{campaign['id']}")
        assert detail.status_code == 200
        assert detail.json()["slug"] == "schools-of-jaipur-2026"

        listing = client.get("/api/v1/civic/campaigns")
        assert listing.status_code == 200
        assert [c["id"] for c in listing.json()["items"]] == [campaign["id"]]

        def patch(status: str) -> int:
            return client.patch(
                f"/api/v1/civic/campaigns/{campaign['id']}",
                json={"status": status},
                headers=headers,
            ).status_code

        assert patch("live") == 200
        assert patch("paused") == 200
        assert patch("live") == 200
        assert patch("closed") == 200
        assert patch("live") == 409
        assert client.get(f"/api/v1/civic/campaigns/{campaign['id']}").json()["status"] == "closed"

    def test_create_requires_existing_category(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        response = client.post(
            "/api/v1/civic/campaigns",
            json={
                "category_id": str(uuid.uuid4()),
                "slug": "orphan",
                "title_key": "t",
                "scope": {},
            },
            headers=headers,
        )
        assert response.status_code == 404
        assert response.json()["type"].endswith("/category_not_found")

    def test_closed_campaigns_are_immutable(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        category_id = self._create_category(client, sender, headers)
        campaign = client.post(
            "/api/v1/civic/campaigns",
            json={
                "category_id": category_id,
                "slug": "immutable",
                "title_key": "t",
                "scope": {},
            },
            headers=headers,
        ).json()
        assert (
            client.patch(
                f"/api/v1/civic/campaigns/{campaign['id']}",
                json={"status": "closed"},
                headers=headers,
            ).status_code
            == 200
        )
        response = client.patch(
            f"/api/v1/civic/campaigns/{campaign['id']}",
            json={"scope": {"state": "UP"}},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/campaign_closed")

    def test_invalid_status_filter_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _admin_headers(client, sender)
        response = client.get("/api/v1/civic/campaigns?status=bogus")
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_status")

    def test_list_by_boundary_and_cursor_pagination(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        category_id = self._create_category(client, sender, headers)
        boundary = uuid.uuid4()
        for index, scope in enumerate([{"boundary_id": str(boundary)}, {"state": "UP"}]):
            client.post(
                "/api/v1/civic/campaigns",
                json={
                    "category_id": category_id,
                    "slug": f"campaign-{index}",
                    "title_key": f"title-{index}",
                    "scope": scope,
                },
                headers=headers,
            )
        only_boundary = client.get(f"/api/v1/civic/campaigns?boundary_id={boundary}").json()
        assert [c["slug"] for c in only_boundary["items"]] == ["campaign-0"]

        page_one = client.get("/api/v1/civic/campaigns?limit=1").json()
        assert len(page_one["items"]) == 1
        assert page_one["next_cursor"] is not None
        page_two = client.get(
            f"/api/v1/civic/campaigns?limit=1&cursor={page_one['next_cursor']}"
        ).json()
        assert len(page_two["items"]) == 1
        assert page_two["next_cursor"] is None
        seen = {page_one["items"][0]["id"], page_two["items"][0]["id"]}
        assert len(seen) == 2

    def test_campaign_audited_and_invalid_cursor(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        headers = _admin_headers(client, sender)
        category_id = self._create_category(client, sender, headers)
        response = client.get("/api/v1/civic/campaigns?cursor=not-a-uuid")
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_cursor")

        response = client.post(
            "/api/v1/civic/campaigns",
            json={
                "category_id": category_id,
                "slug": "audited-campaign",
                "title_key": "t",
                "scope": {},
            },
            headers=headers,
        )
        assert response.status_code == 201
        audit = client.get("/api/v1/users/me/audit", headers=headers).json()["items"]
        assert any(item["action"] == "campaign.create" for item in audit)
