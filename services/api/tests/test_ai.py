"""AI layer tests (API.md §6): T4 envelope analysis + refresh versioning,
citations grounded in provenanced sources, duplicate review queue + audited
decisions (ADR-018)."""

from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.provenance.models import ExternalSource
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "school",
    "icon": "school",
    "form_schema": {
        "type": "object",
        "required": ["issue_area"],
        "properties": {"issue_area": {"type": "string", "enum": ["classroom"]}},
    },
    "verification_policy": {"min_verifications": 2},
    "attachment_rules": {},
}

LOCATION = {"type": "Point", "coordinates": [75.7873, 26.9124]}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _grant(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _admin(client: TestClient, sender) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, f"9876545{_next_phone()}")
    _grant(client, tokens["user"]["id"], "admin")
    return _auth(tokens["access_token"])


def _citizen(client: TestClient, sender, phone: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, phone)
    return tokens["user"]["id"], _auth(tokens["access_token"])


def _volunteer(client: TestClient, sender) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, f"9876545{_next_phone()}")
    _grant(client, tokens["user"]["id"], "volunteer")
    return _auth(tokens["access_token"])


def _setup(client: TestClient, sender) -> None:  # type: ignore[no-untyped-def]
    assert (
        client.post(
            "/api/v1/civic/categories", json=CATEGORY, headers=_admin(client, sender)
        ).status_code
        == 201
    )


def _submit(client: TestClient, headers: dict[str, str], title: str, description: str) -> dict:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/reports",
        json={
            "category_slug": "school",
            "title": title,
            "description": description,
            "location": LOCATION,
            "location_accuracy_m": 10,
            "fields": {"issue_area": "classroom"},
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_source(client: TestClient, report_title: str) -> str:
    async def add() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            source = ExternalSource(
                name=f"Jaipur School Directory {report_title}",
                publisher="Education Dept",
                url="https://edu.example.in/jaipur",
                geo_applicability={"states": ["RJ"]},
            )
            session.add(source)
            await session.commit()
            return str(source.id)

    return asyncio.run(add())


class TestReportAnalysis:
    def test_analysis_envelope_and_persistence(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, headers = _citizen(client, sender, "9876545201")
        report = _submit(
            client,
            headers,
            "Broken classroom windows",
            "Windows broken since May with sharp edges near class rooms",
        )

        # none before a run
        assert client.get(f"/api/v1/reports/{report['id']}/analysis").status_code == 404

        refreshed = client.post(f"/api/v1/reports/{report['id']}/analysis/refresh", headers=headers)
        assert refreshed.status_code == 200, refreshed.text
        body = refreshed.json()
        assert body["info_class"] == "AI_ANALYSIS"
        assert body["model_id"].startswith("deepseek")
        assert 0.0 <= body["confidence"] <= 1.0
        assert isinstance(body["content"]["summary"], str)
        assert body["content"]["suggested_category"] == "school"
        assert body["run"]["provider"] in ("stub",)
        assert body["citations"] == []

        # served via GET
        fetched = client.get(f"/api/v1/reports/{report['id']}/analysis")
        assert fetched.status_code == 200
        assert fetched.json()["annotation_id"] == body["annotation_id"]

        # refresh versioning: new annotation, old preserved
        refreshed2 = client.post(
            f"/api/v1/reports/{report['id']}/analysis/refresh", headers=headers
        )
        assert refreshed2.status_code == 200
        assert refreshed2.json()["annotation_id"] != body["annotation_id"]

    def test_analysis_owner_only(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, headers = _citizen(client, sender, "9876545202")
        report = _submit(
            client,
            headers,
            "Broken classroom windows",
            "Windows broken since May with sharp edges near class rooms",
        )
        stranger = _citizen(client, sender, "9876545203")[1]
        blocked = client.post(f"/api/v1/reports/{report['id']}/analysis/refresh", headers=stranger)
        assert blocked.status_code == 403
        assert blocked.json()["type"].endswith("/forbidden")

    def test_citations_grounded_in_sources(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, headers = _citizen(client, sender, "9876545204")
        report = _submit(
            client,
            headers,
            "Broken classroom windows",
            "Windows broken since May with sharp edges near class rooms",
        )
        source_id = _seed_source(client, "Broken classroom windows")
        refreshed = client.post(f"/api/v1/reports/{report['id']}/analysis/refresh", headers=headers)
        citations = refreshed.json()["citations"]
        assert len(citations) == 1
        assert citations[0]["source_id"] == source_id
        cit = client.get(f"/api/v1/ai/citations/{refreshed.json()['annotation_id']}")
        assert cit.status_code == 200
        assert cit.json()[0]["url"] == "https://edu.example.in/jaipur"


class TestReviewQueue:
    def _duplicate_report(self, client: TestClient, sender, title: str, description: str) -> dict:  # type: ignore[no-untyped-def]
        _, headers = _citizen(client, sender, f"9876545{_next_phone()}")
        return _submit(client, headers, title, description)

    def _analyze(self, client: TestClient, headers: dict[str, str], report_id: str) -> dict:  # type: ignore[no-untyped-def]
        response = client.post(f"/api/v1/reports/{report_id}/analysis/refresh", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def test_queue_and_approve_merge(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        first = self._duplicate_report(
            client,
            sender,
            "Broken classroom windows in block A",
            "Windows broken since May with sharp edges near the class rooms in block A",
        )
        dup = self._duplicate_report(
            client,
            sender,
            "Broken classroom windows in block A",
            "Windows broken since May with sharp edges near the class rooms "
            "in block A - duplicate submission",
        )

        admin = _admin(client, sender)
        volunteer = _volunteer(client, sender)
        self._analyze(client, admin, dup["id"])

        # volunteer can view the queue
        queue = client.get("/api/v1/ai/human-review-queue", headers=volunteer)
        assert queue.status_code == 200
        items = [i for i in queue.json()["items"] if i["report"]["id"] == dup["id"]]
        assert len(items) == 1
        review_id = items[0]["id"]

        # approve requires admin; volunteer gets 403
        denied = client.post(
            f"/api/v1/ai/reviews/{review_id}/decision",
            json={"approve": True},
            headers=volunteer,
        )
        assert denied.status_code == 403

        approved = client.post(
            f"/api/v1/ai/reviews/{review_id}/decision",
            json={"approve": True, "reason": "identical description"},
            headers=admin,
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        # merged report now points at the original
        detail = client.get(f"/api/v1/reports/{dup['id']}")
        assert detail.json()["duplicate_of"] == first["id"]
        assert detail.json()["merged_by_ai"] is True

        # second decision rejected
        again = client.post(
            f"/api/v1/ai/reviews/{review_id}/decision",
            json={"approve": False},
            headers=admin,
        )
        assert again.status_code == 409
        assert again.json()["type"].endswith("/review_decided")

    def test_queue_and_reject(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        self._duplicate_report(
            client,
            sender,
            "Broken classroom windows in block A",
            "Windows broken since May with sharp edges near the class rooms in block A",
        )
        dup = self._duplicate_report(
            client,
            sender,
            "Broken classroom windows in block A",
            "Windows broken since May with sharp edges near the class rooms "
            "in block A - duplicate submission",
        )

        admin = _admin(client, sender)
        self._analyze(client, admin, dup["id"])
        queue = client.get("/api/v1/ai/human-review-queue", headers=admin)
        review = next(i for i in queue.json()["items"] if i["report"]["id"] == dup["id"])
        rejected = client.post(
            f"/api/v1/ai/reviews/{review['id']}/decision",
            json={"approve": False, "reason": "actually two incidents"},
            headers=admin,
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        detail = client.get(f"/api/v1/reports/{dup['id']}")
        assert detail.json()["merged_by_ai"] is False

        # queue is empty again for dup kind
        queue2 = client.get("/api/v1/ai/human-review-queue", headers=admin)
        assert not [i for i in queue2.json()["items"] if i["report"]["id"] == dup["id"]]


_phone = [400]


def _next_phone() -> int:
    _phone[0] += 1
    return _phone[0]
