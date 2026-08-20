"""Report lifecycle tests (API.md §5, DATABASE.md §5): submission validation,
idempotency, state machine (409 on violations), verification trust scoring +
policy-driven promotion, collaboration, timeline."""

from __future__ import annotations

import asyncio
import random
import re
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
        "additionalProperties": False,
    },
    "verification_policy": {"min_verifications": 2, "min_locale_diversity": 1},
    "attachment_rules": {"max_files": 4, "max_size_mb": 8},
}

LOCATION = {"type": "Point", "coordinates": [75.7873, 26.9124]}

VALID_FIELDS = {
    "title": "Broken classroom windows",
    "description": "Ground floor windows broken since May",
}
VALID_FIELDS2 = {
    "title": "Leaking roof in corridor",
    "description": "Water seeps through the roof when it rains",
}
VALID_FIELDS3 = {
    "title": "Broken water tap outside",
    "description": "Tap pours continuously since last week",
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _grant_role(client: TestClient, user_id: str, code: str) -> None:
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
    _grant_role(client, tokens["user"]["id"], "admin")
    return _auth(tokens["access_token"])


def _citizen_headers(client: TestClient, sender, phone: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, phone)
    return tokens["user"]["id"], _auth(tokens["access_token"])


def _role_headers(client: TestClient, sender, phone: str, role: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, phone)
    _grant_role(client, tokens["user"]["id"], role)
    return _auth(tokens["access_token"])


def _setup_category(client: TestClient, sender) -> str:  # type: ignore[no-untyped-def]
    headers = _admin_headers(client, sender)
    response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_campaign(client: TestClient, sender, category_id: str, status: str = "live") -> dict:  # type: ignore[no-untyped-def]
    headers = _admin_headers(client, sender)
    response = client.post(
        "/api/v1/civic/campaigns",
        json={
            "category_id": category_id,
            "slug": f"schools-of-jaipur-{uuid.uuid4().hex[:8]}",
            "title_key": "campaign.schools_jaipur.title",
            "scope": {"state": "RJ"},
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    if status != "planned":
        patched = client.patch(
            f"/api/v1/civic/campaigns/{campaign['id']}",
            json={"status": status},
            headers=headers,
        )
        assert patched.status_code == 200, patched.text
        campaign = patched.json()
    return campaign


def _submit(client: TestClient, headers: dict[str, str], **overrides) -> dict:  # type: ignore[no-untyped-def]
    payload = {
        "category_slug": "school",
        "title": "Broken classroom windows on ground floor",
        "description": "Windows on the ground floor remain broken since May with sharp edges",
        "location": LOCATION,
        "location_accuracy_m": 12,
        "fields": VALID_FIELDS,
        **overrides,
    }
    response = client.post("/api/v1/reports", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


class TestSubmission:
    def test_requires_auth(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.post(
            "/api/v1/reports",
            json={"category_slug": "school", "title": "X" * 10, "description": "Y" * 50},
        )
        assert response.status_code == 401

    def test_unknown_category(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, headers = _citizen_headers(client, sender, "9876543101")
        response = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "nope",
                "title": "Broken classroom windows on the ground floor",
                "description": "Windows on the ground floor remain broken since May"
                " with sharp edges",
                "location": LOCATION,
                "location_accuracy_m": 12,
                "fields": VALID_FIELDS,
            },
            headers=headers,
        )
        assert response.status_code == 404
        assert response.json()["type"].endswith("/category_not_found")

    def test_field_validation_against_form_schema(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, headers = _citizen_headers(client, sender, "9876543102")
        response = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "school",
                "title": "Broken classroom windows on ground floor",
                "description": "Windows on the ground floor remain broken since May",
                "location": LOCATION,
                "location_accuracy_m": 12,
                "fields": {"title": 42},  # wrong type + missing description
            },
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/field_validation_failed")

    def test_closed_campaign_rejects(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        category_id = _setup_category(client, sender)
        campaign = _create_campaign(client, sender, category_id, status="closed")
        _, headers = _citizen_headers(client, sender, "9876543103")
        response = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "school",
                "campaign_id": campaign["id"],
                "title": "Broken classroom windows on ground floor",
                "description": "Windows on the ground floor remain broken since May",
                "location": LOCATION,
                "location_accuracy_m": 12,
                "fields": VALID_FIELDS,
            },
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/campaign_closed")

    def test_campaign_category_mismatch(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        category_id = _setup_category(client, sender)
        campaign = _create_campaign(client, sender, category_id)
        _, headers = _citizen_headers(client, sender, "9876543104")
        response = (
            client.post(
                "/api/v1/reports",
                json={
                    "category_slug": "school",
                    "campaign_id": campaign["id"],
                    "title": "Broken classroom windows on ground floor",
                    "description": "Windows on the ground floor remain broken since May",
                    "location": LOCATION,
                    "location_accuracy_m": 12,
                    "fields": VALID_FIELDS,
                },
                headers=headers,
            )
            if False
            else None
        )
        # campaign belongs to category id, so mismatch needs another category
        other = {
            "slug": "road",
            "icon": "road",
            "form_schema": {"type": "object", "properties": {}},
            "verification_policy": {"min_verifications": 2},
            "attachment_rules": {},
        }
        admin = _admin_headers(client, sender)
        assert client.post("/api/v1/civic/categories", json=other, headers=admin).status_code == 201
        # now submit against the school campaign with the road category
        response = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "road",
                "campaign_id": campaign["id"],
                "title": "Broken classroom windows on ground floor",
                "description": "Windows on the ground floor remain broken since May",
                "location": LOCATION,
                "location_accuracy_m": 12,
                "fields": {},
            },
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/campaign_category_mismatch")

    def test_happy_path_with_ticket_and_location(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        user_id, headers = _citizen_headers(client, sender, "9876543105")
        report = _submit(client, headers)
        assert report["status"] == "submitted"
        assert report["info_class"] == "CITIZEN_REPORT"
        assert report["trust_score"] == 0.0
        assert report["reporter_id"] == user_id
        assert re.fullmatch(r"TK-\d{8}-[0-9A-F]{6}", report["ticket_no"])
        assert report["location"] == LOCATION
        assert report["fields"] == VALID_FIELDS
        assert report["campaign_id"] is None

        detail = client.get(f"/api/v1/reports/{report['id']}")
        assert detail.status_code == 200
        assert detail.json()["ticket_no"] == report["ticket_no"]
        assert detail.json()["verifications"] == []

    def test_idempotent_submission_replays(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, headers = _citizen_headers(client, sender, "9876543106")
        payload = {
            "category_slug": "school",
            "title": "Broken classroom windows on ground floor",
            "description": "Windows on the ground floor remain broken since May",
            "location": LOCATION,
            "location_accuracy_m": 12,
            "fields": VALID_FIELDS,
        }
        key = str(uuid.uuid4())
        first = client.post(
            "/api/v1/reports", json=payload, headers={**headers, "Idempotency-Key": key}
        )
        assert first.status_code == 201
        replay = client.post(
            "/api/v1/reports", json=payload, headers={**headers, "Idempotency-Key": key}
        )
        assert replay.status_code == 200
        assert replay.json()["id"] == first.json()["id"]
        # a second key creates a distinct report
        other = client.post(
            "/api/v1/reports",
            json=payload,
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert other.status_code == 201
        assert other.json()["id"] != first.json()["id"]

    def test_invalid_idempotency_key(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, headers = _citizen_headers(client, sender, "9876543107")
        response = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "school",
                "title": "Broken classroom windows on ground floor",
                "description": "Windows on the ground floor remain broken since May",
                "location": LOCATION,
                "location_accuracy_m": 12,
                "fields": VALID_FIELDS,
            },
            headers={**headers, "Idempotency-Key": "not-a-uuid"},
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_idempotency_key")


class TestListing:
    def test_filters_and_cursor(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, headers = _citizen_headers(client, sender, "9876543108")
        first = _submit(
            client,
            headers,
            title="First broken window report",
            description="First description of broken windows" + "x" * 10,
        )
        _submit(
            client,
            headers,
            title="Second broken window report",
            description="Second description of broken windows" + "x" * 10,
        )
        listing = client.get("/api/v1/reports?category_slug=school&status=submitted&limit=1")
        assert listing.status_code == 200
        items = listing.json()["items"]
        assert len(items) == 1
        assert listing.json()["next_cursor"] is not None
        page2 = client.get(
            f"/api/v1/reports?category_slug=school&limit=1&cursor={listing.json()['next_cursor']}"
        )
        assert page2.status_code == 200
        ids = {items[0]["id"], *(i["id"] for i in page2.json()["items"])}
        assert first["id"] in ids

        assert client.get("/api/v1/reports?status=bogus").json()["type"].endswith("/invalid_status")
        assert client.get("/api/v1/reports?cursor=nope").json()["type"].endswith("/invalid_cursor")
        assert client.get("/api/v1/reports?category_slug=ghost").status_code == 404

    def test_missing_report_404(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"/api/v1/reports/{uuid.uuid4()}").status_code == 404


class TestFieldsUpdate:
    def test_reporter_can_edit_while_submitted(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _user_id, headers = _citizen_headers(client, sender, "9876543109")
        report = _submit(client, headers)
        response = client.patch(
            f"/api/v1/reports/{report['id']}/fields",
            json={"fields": VALID_FIELDS2},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["fields"] == VALID_FIELDS2

        stranger = _citizen_headers(client, sender, "9876543110")[1]
        blocked = client.patch(
            f"/api/v1/reports/{report['id']}/fields",
            json={"title": "Hijacked title"},
            headers=stranger,
        )
        assert blocked.status_code == 403

    def test_fields_locked_after_submitted_stage(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, headers = _citizen_headers(client, sender, "9876543111")
        report = _submit(client, headers)
        volunteer = _role_headers(client, sender, "9876543112", "volunteer")
        assert (
            client.post(
                f"/api/v1/reports/{report['id']}/transition",
                json={"to_status": "under_verification"},
                headers=volunteer,
            ).status_code
            == 200
        )
        blocked = client.patch(
            f"/api/v1/reports/{report['id']}/fields",
            json={"title": "Late edit"},
            headers=headers,
        )
        assert blocked.status_code == 409
        assert blocked.json()["type"].endswith("/fields_locked")


class TestStateMachine:
    def _walk(self, client, sender) -> dict:  # type: ignore[no-untyped-def]
        def trans(headers: dict[str, str], to: str, *, reason: str | None = None) -> dict:  # type: ignore[no-untyped-def]
            response = client.post(
                f"/api/v1/reports/{report['id']}/transition",
                json={"to_status": to, "reason": reason},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            return response.json()

        citizen = _citizen_headers(client, sender, "9876543113")[1]
        volunteer = _role_headers(client, sender, "9876543114", "volunteer")
        official = _role_headers(client, sender, "9876543115", "official")
        admin = _role_headers(client, sender, "9876543116", "admin")

        report = _submit(client, citizen)
        # citizen may not promote
        assert (
            client.post(
                f"/api/v1/reports/{report['id']}/transition",
                json={"to_status": "under_verification"},
                headers=citizen,
            ).status_code
            == 403
        )
        assert trans(volunteer, "under_verification")["status"] == "under_verification"
        assert trans(volunteer, "verified")["status"] == "verified"
        assert trans(official, "assigned")["status"] == "assigned"
        assert trans(official, "in_progress")["status"] == "in_progress"
        resolved = trans(official, "resolved")
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None
        reopened = trans(volunteer, "reopened", reason="reported as false")
        assert reopened["status"] == "reopened"
        assert reopened["resolved_at"] is None
        assert trans(official, "resolved")["status"] == "resolved"
        assert trans(volunteer, "resolution_verified")["status"] == "resolution_verified"
        assert trans(admin, "closed")["status"] == "closed"
        return report

    def test_full_walk_and_timeline(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        report = self._walk(client, sender)
        timeline = client.get(f"/api/v1/reports/{report['id']}/timeline")
        assert timeline.status_code == 200
        statuses = [t["to_status"] for t in timeline.json()["items"]]
        assert statuses == [
            "closed",
            "resolution_verified",
            "resolved",
            "reopened",
            "resolved",
            "in_progress",
            "assigned",
            "verified",
            "under_verification",
            "submitted",
        ]
        history = client.get(f"/api/v1/reports/{report['id']}/timeline").json()["items"]
        assert history[-1]["from_status"] is None  # initial submission
        assert history[-1]["to_status"] == "submitted"

    def test_illegal_transitions_409(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, citizen = _citizen_headers(client, sender, "9876543117")
        report = _submit(client, citizen)
        official = _role_headers(client, sender, "9876543118", "official")
        # submitted -> closed is not an edge
        response = client.post(
            f"/api/v1/reports/{report['id']}/transition",
            json={"to_status": "closed"},
            headers=official,
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/invalid_status_transition")
        # unknown status
        assert (
            client.post(
                f"/api/v1/reports/{report['id']}/transition",
                json={"to_status": "bogus"},
                headers=official,
            ).status_code
            == 422
        )
        # rejection requires a reason
        response = client.post(
            f"/api/v1/reports/{report['id']}/transition",
            json={"to_status": "rejected"},
            headers=official,
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/reason_required")


class TestVerifications:
    def test_trust_scoring_and_auto_promotion(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _reporter_id, reporter_headers = _citizen_headers(client, sender, "9876543119")
        report = _submit(client, reporter_headers)

        # reporter cannot verify own report
        assert (
            client.post(
                f"/api/v1/reports/{report['id']}/verifications",
                json={"kind": "confirm"},
                headers=reporter_headers,
            ).status_code
            == 403
        )
        # self-verification is blocked by "id" equality check
        v1 = _citizen_headers(client, sender, "9876543120")[1]
        first = client.post(
            f"/api/v1/reports/{report['id']}/verifications",
            json={"kind": "confirm", "evidence": "seen it myself"},
            headers=v1,
        )
        assert first.status_code == 201, first.text
        assert first.json()["trust_score"] == 0.15
        # first verification auto-promotes to under_verification (policy min evidence 1)
        assert first.json()["status"] == "under_verification"

        v2 = _citizen_headers(client, sender, "9876543121")[1]
        second = client.post(
            f"/api/v1/reports/{report['id']}/verifications",
            json={"kind": "confirm"},
            headers=v2,
        )
        assert second.status_code == 201
        assert second.json()["trust_score"] == 0.3
        # min_verifications=2 → verified
        assert second.json()["status"] == "verified"

        # duplicates rejected
        dup = client.post(
            f"/api/v1/reports/{report['id']}/verifications",
            json={"kind": "confirm"},
            headers=v2,
        )
        assert dup.status_code == 409
        assert dup.json()["type"].endswith("/duplicate_verification")

    def test_refute_lowers_trust(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, reporter = _citizen_headers(client, sender, "9876543122")
        report = _submit(client, reporter)
        v1 = _citizen_headers(client, sender, "9876543123")[1]
        refute = client.post(
            f"/api/v1/reports/{report['id']}/verifications",
            json={"kind": "refute", "evidence": "checked, no such damage"},
            headers=v1,
        )
        assert refute.status_code == 201
        assert refute.json()["trust_score"] == 0.0  # floor at 0
        assert refute.json()["status"] == "under_verification"


class TestCollaboration:
    def test_comments_and_follow(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, reporter = _citizen_headers(client, sender, "9876543124")
        report = _submit(client, reporter)
        other = _citizen_headers(client, sender, "9876543125")[1]

        comment = client.post(
            f"/api/v1/reports/{report['id']}/comments",
            json={"body": "Also visible from the hallway"},
            headers=other,
        )
        assert comment.status_code == 201
        reply = client.post(
            f"/api/v1/reports/{report['id']}/comments",
            json={"body": "Agreed", "parent_id": comment.json()["id"]},
            headers=other,
        )
        assert reply.status_code == 201
        listing = client.get(f"/api/v1/reports/{report['id']}/comments")
        assert [c["body"] for c in listing.json()] == ["Also visible from the hallway", "Agreed"]

        # parent from another report is rejected
        _, reporter2 = _citizen_headers(client, sender, "9876543126")
        report2 = _submit(client, reporter2)
        bogus = client.post(
            f"/api/v1/reports/{report2['id']}/comments",
            json={"body": "reply", "parent_id": comment.json()["id"]},
            headers=other,
        )
        assert bogus.status_code == 404

        follow = client.post(
            f"/api/v1/reports/{report['id']}/follow",
            json={"notify_level": "status_only"},
            headers=other,
        )
        assert follow.status_code == 201
        assert follow.json()["notify_level"] == "status_only"
        updated = client.post(f"/api/v1/reports/{report['id']}/follow", json={}, headers=other)
        assert updated.status_code == 201
        assert updated.json()["notify_level"] == "all"
        assert (
            client.delete(f"/api/v1/reports/{report['id']}/follow", headers=other).status_code
            == 204
        )
        assert (
            client.delete(f"/api/v1/reports/{report['id']}/follow", headers=other).status_code
            == 404
        )
