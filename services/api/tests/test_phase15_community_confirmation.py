"""Phase 15 tests (PRD §B.2): community confirmation on resolved cases.

Covers the citizen follow-up signals over independently-reviewed resolutions:
the two-confirmer gate (reporter + one more citizen -> community_confirmed_at),
the "issue still exists" reopen signal (threshold -> review queue -> human
approve reopens / dismiss keeps closed), one-signal-per-user dedup, the
no-auto-reopen/close guarantee, private-report visibility, and the analytics
count of two-confirmer closures.
"""

from __future__ import annotations

import asyncio
import random
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.cases.models import CivicCase
from tk_api.core.db import create_session_factory
from tk_api.notifications.models import Notification
from tk_api.resolution.models import ResolutionFollowup, ResolutionReopenSignal
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "ph15",
    "icon": "ph15",
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fresh_phone() -> str:
    return f"9{random.randrange(10**9, 10**10)}"


def _role_headers(client: TestClient, phone: str, role: str) -> dict[str, str]:
    tokens = _register_and_verify(client, client._recording_sender, phone)  # type: ignore[attr-defined]
    _grant_role(client, tokens["user"]["id"], role)
    return _auth(tokens["access_token"])


def _citizen(client: TestClient, phone: str) -> tuple[str, dict[str, str]]:
    tokens = _register_and_verify(client, client._recording_sender, phone)  # type: ignore[attr-defined]
    return tokens["user"]["id"], _auth(tokens["access_token"])


def _user_id(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _grant_role(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _setup(client: TestClient, admin: dict[str, str] | None = None) -> dict[str, str]:
    headers = admin or _role_headers(client, _fresh_phone(), "admin")
    response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
    assert response.status_code == 201, response.text
    return headers


def _submit(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {
        "category_slug": "ph15",
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


def _report_to_verified(client: TestClient, report_id: str) -> None:
    volunteer = _role_headers(client, _fresh_phone(), "volunteer")
    response = client.post(
        f"/api/v1/reports/{report_id}/transition",
        json={"to_status": "under_verification"},
        headers=volunteer,
    )
    assert response.status_code == 200, response.text
    response = client.post(
        f"/api/v1/reports/{report_id}/transition",
        json={"to_status": "verified"},
        headers=volunteer,
    )
    assert response.status_code == 200, response.text


def _create_department(client: TestClient, name: str, admin: dict[str, str] | None = None) -> dict:
    headers = admin or _role_headers(client, _fresh_phone(), "admin")
    response = client.post(
        "/api/v1/departments/types",
        json={"code": f"dept-{uuid.uuid4().hex[:8]}", "name_key": "dept"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    type_id = response.json()["id"]
    response = client.post(
        "/api/v1/departments",
        json={
            "slug": f"dept-{uuid.uuid4().hex[:10]}",
            "name": name,
            "department_type_id": type_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_member(
    client: TestClient,
    department_id: str,
    user_id: str,
    admin: dict[str, str] | None = None,
) -> dict:
    headers = admin or _role_headers(client, _fresh_phone(), "admin")
    response = client.post(
        f"/api/v1/departments/{department_id}/members",
        json={"user_id": user_id, "role_in_department": "member"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_case(
    client: TestClient, manager_headers: dict[str, str], report_id: str, department_id: str
) -> dict:
    response = client.post(
        "/api/v1/cases",
        json={"report_id": report_id, "department_id": department_id},
        headers=manager_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _transition_case(
    client: TestClient, case_id: str, headers: dict[str, str], to_status: str
) -> None:
    response = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={"to_status": to_status},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def _resolve_case(client: TestClient) -> tuple[dict, str, dict[str, str]]:
    """Walk a case to 'resolved' via the department + independent review."""
    admin = _setup(client)
    manager = _role_headers(client, _fresh_phone(), "department_manager")
    representative = _role_headers(client, _fresh_phone(), "department_representative")
    reviewer = _role_headers(client, _fresh_phone(), "reviewer")
    reporter_id, citizen = _citizen(client, _fresh_phone())

    department = _create_department(client, "Education Board", admin=admin)
    _add_member(client, department["id"], _user_id(client, representative), admin=admin)

    report = _submit(client, citizen)
    _report_to_verified(client, report["id"])
    case = _create_case(client, manager, report["id"], department["id"])
    case_id = case["id"]
    _transition_case(client, case_id, manager, "under_review")
    _transition_case(client, case_id, manager, "verified")
    response = client.post(
        f"/api/v1/cases/{case_id}/assign",
        json={"department_id": department["id"]},
        headers=manager,
    )
    assert response.status_code == 200, response.text
    _transition_case(client, case_id, representative, "acknowledged")
    _transition_case(client, case_id, representative, "in_progress")

    response = client.post(
        "/api/v1/resolutions",
        json={
            "case_id": case_id,
            "explanation": "Windows replaced on site",
            "reference_numbers": {"job": "J-5511"},
            "evidence": [{"kind": "after", "notes": "New windows installed"}],
        },
        headers=representative,
    )
    assert response.status_code == 201, response.text
    response = client.post(
        f"/api/v1/resolutions/{response.json()['id']}/review",
        json={"decision": "verified", "reason": "Site photos match report"},
        headers=reviewer,
    )
    assert response.status_code == 200, response.text

    check = client.get(f"/api/v1/cases/{case_id}", headers=manager)
    assert check.status_code == 200, check.text
    assert check.json()["status"] == "resolved"
    return case, reporter_id, citizen


def _db_rows(client: TestClient, model, **where) -> list:
    async def fetch() -> list:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            stmt = select(model)
            for col, value in where.items():
                stmt = stmt.where(getattr(model, col) == value)
            return list((await session.execute(stmt)).scalars().all())

    return asyncio.run(fetch())


def _notifications(client: TestClient, user_id: str, event: str) -> int:
    rows = _db_rows(client, Notification, user_id=uuid.UUID(user_id), event=event)
    return len(rows)


class TestResolutionFollowup:
    def test_followup_requires_resolved_case(self, client: TestClient, sender) -> None:
        admin = _setup(client)
        manager = _role_headers(client, _fresh_phone(), "department_manager")
        _, citizen = _citizen(client, _fresh_phone())
        department = _create_department(client, "Water Board", admin=admin)
        report = _submit(client, citizen)
        _report_to_verified(client, report["id"])
        _create_case(client, manager, report["id"], department["id"])

        response = client.post(
            f"/api/v1/reports/{report['id']}/resolution-followups",
            json={"signal": "observed_improvement"},
            headers=citizen,
        )
        assert response.status_code == 409, response.text
        assert "case_not_resolved" in response.json()["type"]

    def test_two_confirmer_gate_marks_confirmed_and_notifies(
        self, client: TestClient, sender
    ) -> None:
        case, reporter_id, citizen = _resolve_case(client)
        report_id = case["report_id"]
        _, citizen_b = _citizen(client, _fresh_phone())

        # Reporter confirms first: below threshold (2), stays pending.
        response = client.post(
            f"/api/v1/reports/{report_id}/resolution-followups",
            json={"signal": "observed_improvement", "observation": "new windows installed"},
            headers=citizen,
        )
        assert response.status_code == 201, response.text

        # Second citizen confirms: gate fires.
        response = client.post(
            f"/api/v1/reports/{report_id}/resolution-followups",
            json={"signal": "observed_improvement"},
            headers=citizen_b,
        )
        assert response.status_code == 201, response.text

        followups = _db_rows(client, ResolutionFollowup, case_id=uuid.UUID(case["id"]))
        assert len(followups) == 2
        assert all(f.status == "confirmed" for f in followups)

        case_row = _db_rows(client, CivicCase, id=uuid.UUID(case["id"]))[0]
        assert case_row.community_confirmed_at is not None
        # The gate is a review trigger: no auto-close.
        assert case_row.status == "resolved"

        # Reporter was notified the community confirmed their case.
        assert _notifications(client, reporter_id, "resolution.followup_confirmed") == 1

        summary = client.get(f"/api/v1/reports/{report_id}/resolution-followups")
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["observed_improvement_count"] == 2
        assert body["community_confirmed_at"] is not None

    def test_dedup_same_user_second_signal_conflict(self, client: TestClient, sender) -> None:
        case, _, citizen = _resolve_case(client)
        report_id = case["report_id"]

        response = client.post(
            f"/api/v1/reports/{report_id}/resolution-followups",
            json={"signal": "issue_still_exists"},
            headers=citizen,
        )
        assert response.status_code == 201, response.text

        response = client.post(
            f"/api/v1/reports/{report_id}/resolution-followups",
            json={"signal": "observed_improvement"},
            headers=citizen,
        )
        assert response.status_code == 409, response.text
        assert "conflict" in response.json()["type"]

    def test_reopen_signal_threshold_then_approve_reopens(self, client: TestClient, sender) -> None:
        case, reporter_id, _citizen_a = _resolve_case(client)
        report_id = case["report_id"]
        reviewer = _role_headers(client, _fresh_phone(), "reviewer")

        users = [
            _citizen_a,
            _citizen(client, _fresh_phone())[1],
            _citizen(client, _fresh_phone())[1],
        ]
        # three distinct citizens report the issue persists
        for idx, headers in enumerate(users):
            response = client.post(
                f"/api/v1/reports/{report_id}/resolution-followups",
                json={"signal": "issue_still_exists", "observation": f"still broken {idx}"},
                headers=headers,
            )
            assert response.status_code == 201, response.text

        followups = _db_rows(client, ResolutionFollowup, case_id=uuid.UUID(case["id"]))
        assert len(followups) == 3
        assert all(f.status == "escalated" for f in followups)
        signals = _db_rows(client, ResolutionReopenSignal, case_id=uuid.UUID(case["id"]))
        assert len(signals) == 1
        assert signals[0].status == "pending"
        assert signals[0].signal_count == 3

        queue = client.get("/api/v1/resolutions/reopen-signals", headers=reviewer)
        assert queue.status_code == 200, queue.text
        assert queue.json()["count"] == 1
        signal_id = queue.json()["items"][0]["id"]

        response = client.post(
            f"/api/v1/resolutions/reopen-signals/{signal_id}/review",
            json={"decision": "approved", "note": "engineer to revisit"},
            headers=reviewer,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"
        assert response.json()["case_status"] == "reopened"

        case_row = _db_rows(client, CivicCase, id=uuid.UUID(case["id"]))[0]
        assert case_row.status == "reopened"
        assert _notifications(client, reporter_id, "resolution.reopen_approved") == 1

    def test_reopen_signal_dismissed_keeps_case_resolved(self, client: TestClient, sender) -> None:
        case, _, citizen_a = _resolve_case(client)
        report_id = case["report_id"]
        reviewer = _role_headers(client, _fresh_phone(), "reviewer")

        citizens = [
            citizen_a,
            _citizen(client, _fresh_phone())[1],
            _citizen(client, _fresh_phone())[1],
        ]
        for headers in citizens:
            response = client.post(
                f"/api/v1/reports/{report_id}/resolution-followups",
                json={"signal": "issue_still_exists"},
                headers=headers,
            )
            assert response.status_code == 201, response.text

        signal = _db_rows(client, ResolutionReopenSignal, case_id=uuid.UUID(case["id"]))[0]
        response = client.post(
            f"/api/v1/resolutions/reopen-signals/{signal.id}/review",
            json={"decision": "dismissed", "note": "re-inspection confirmed fix"},
            headers=reviewer,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "dismissed"

        case_row = _db_rows(client, CivicCase, id=uuid.UUID(case["id"]))[0]
        assert case_row.status == "resolved"

    def test_private_report_followups_hidden(self, client: TestClient, sender) -> None:
        case, _, citizen = _resolve_case(client)
        report_id = case["report_id"]
        _, other = _citizen(client, _fresh_phone())

        async def make_private() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                from tk_api.reports.models import Report

                report = await session.get(Report, uuid.UUID(report_id))
                report.visibility = "private"
                await session.commit()

        asyncio.run(make_private())

        response = client.post(
            f"/api/v1/reports/{report_id}/resolution-followups",
            json={"signal": "observed_improvement"},
            headers=other,
        )
        assert response.status_code == 404, response.text
        response = client.get(f"/api/v1/reports/{report_id}/resolution-followups", headers=other)
        assert response.status_code == 404, response.text

        # The reporter still can.
        response = client.post(
            f"/api/v1/reports/{report_id}/resolution-followups",
            json={"signal": "observed_improvement"},
            headers=citizen,
        )
        assert response.status_code == 201, response.text

    def test_analytics_counts_two_confirmer_closures(self, client: TestClient, sender) -> None:
        case, _, citizen = _resolve_case(client)
        report_id = case["report_id"]
        _, citizen_b = _citizen(client, _fresh_phone())

        for headers in (citizen, citizen_b):
            response = client.post(
                f"/api/v1/reports/{report_id}/resolution-followups",
                json={"signal": "observed_improvement"},
                headers=headers,
            )
            assert response.status_code == 201, response.text

        response = client.get("/api/v1/analytics/resolution")
        assert response.status_code == 200, response.text
        assert response.json()["community_confirmed_count"] >= 1
