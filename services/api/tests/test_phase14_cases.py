"""Phase 14 tests (API.md §11-§13, PRD §38-§44): department registry,
jurisdiction scoped membership, civic case lifecycle, SLA clocks, escalation
and the resolution review workflow."""

from __future__ import annotations

import asyncio
import random
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.cases.escalation import escalate_on_breach
from tk_api.cases.models import CaseEscalation, CivicCase, EscalationRule, SlaInstance, SlaPolicy
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "ph13",
    "icon": "ph13",
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


def _role_headers(client: TestClient, phone: str, role: str) -> dict[str, str]:
    tokens = _register_and_verify(client, client._recording_sender, phone)  # type: ignore[attr-defined]
    _grant_role(client, tokens["user"]["id"], role)
    return _auth(tokens["access_token"])


def _grant_role(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _fresh_phone() -> str:
    return f"9{random.randrange(10**9, 10**10)}"


def _setup(client: TestClient, sender) -> str:
    headers = _role_headers(client, _fresh_phone(), "admin")
    response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _submit(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {
        "category_slug": "ph13",
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


def _create_department(client: TestClient, name: str) -> dict:
    admin = _role_headers(client, _fresh_phone(), "admin")
    response = client.post(
        "/api/v1/departments/types",
        json={"code": f"dept-{uuid.uuid4().hex[:8]}", "name_key": "dept"},
        headers=admin,
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
        headers=admin,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_member(
    client: TestClient, department_id: str, user_id: str, role_in_department: str
) -> dict:
    admin = _role_headers(client, _fresh_phone(), "admin")
    response = client.post(
        f"/api/v1/departments/{department_id}/members",
        json={"user_id": user_id, "role_in_department": role_in_department},
        headers=admin,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_case(
    client: TestClient,
    manager_headers: dict[str, str],
    report_id: str,
    department_id: str,
    severity: str = "medium",
) -> dict:
    response = client.post(
        "/api/v1/cases",
        json={"report_id": report_id, "department_id": department_id, "severity": severity},
        headers=manager_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_sla_policy(client: TestClient) -> None:
    async def seed() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            existing = await session.scalar(
                select(SlaPolicy).where(SlaPolicy.code == "default-24h")
            )
            if existing is None:
                session.add(
                    SlaPolicy(
                        code="default-24h",
                        name="Default 24h",
                        resolution_hours=24,
                        at_risk_pct=0.8,
                    )
                )
            existing_rule = await session.scalar(
                select(EscalationRule).where(EscalationRule.code == "sla-breach-l1")
            )
            if existing_rule is None:
                session.add(
                    EscalationRule(
                        code="sla-breach-l1",
                        threshold_type="sla_breached",
                        level=1,
                        target_role="department_manager",
                        message="SLA breach",
                    )
                )
            await session.commit()

    asyncio.run(seed())


def _transition_case(
    client: TestClient,
    case_id: str,
    headers: dict[str, str],
    to_status: str,
    reason: str | None = None,
) -> None:
    response = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={"to_status": to_status, "reason": reason},
        headers=headers,
    )
    assert response.status_code == 200, response.text


class TestDepartmentRegistry:
    def test_admin_creates_type_department_member(self, client: TestClient, sender) -> None:
        admin = _role_headers(client, _fresh_phone(), "admin")
        response = client.post(
            "/api/v1/departments/types",
            json={"code": f"edu-{uuid.uuid4().hex[:8]}", "name_key": "education"},
            headers=admin,
        )
        assert response.status_code == 201, response.text
        type_id = response.json()["id"]

        response = client.post(
            "/api/v1/departments",
            json={
                "slug": f"edu-{uuid.uuid4().hex[:6]}",
                "name": "Education Department",
                "department_type_id": type_id,
                "description": "School infrastructure",
            },
            headers=admin,
        )
        assert response.status_code == 201, response.text
        department = response.json()
        assert department["slug"]

        user, _ = _citizen(client, _fresh_phone())
        response = client.post(
            f"/api/v1/departments/{department['id']}/members",
            json={"user_id": user, "role_in_department": "manager"},
            headers=admin,
        )
        assert response.status_code == 201, response.text
        member = response.json()
        assert member["user_id"] == user

    def test_citizen_cannot_manage_registry(self, client: TestClient, sender) -> None:
        _, headers = _citizen(client, _fresh_phone())
        response = client.post(
            "/api/v1/departments/types",
            json={"code": "x", "name_key": "x"},
            headers=headers,
        )
        assert response.status_code == 403


class TestOrganizationVerification:
    def test_request_and_review_creates_membership(self, client: TestClient, sender) -> None:
        department = _create_department(client, "Water Board")
        _, headers = _citizen(client, _fresh_phone())
        response = client.post(
            "/api/v1/departments/verifications",
            json={
                "organization_name": "Jaipur Nagar Nigam",
                "department_id": department["id"],
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        verification = response.json()

        admin = _role_headers(client, _fresh_phone(), "admin")
        response = client.post(
            f"/api/v1/departments/verifications/{verification['id']}/review",
            json={"state": "verified", "scope_note": "ward 21 zone"},
            headers=admin,
        )
        assert response.status_code == 200, response.text

        response = client.get("/api/v1/departments/me", headers=headers)
        assert response.status_code == 200, response.text
        assert any(m["department_id"] == department["id"] for m in response.json())


class TestCaseLifecycle:
    def test_full_lifecycle_to_resolution_and_reopen(self, client: TestClient, sender) -> None:
        _setup(client, sender)
        manager = _role_headers(client, _fresh_phone(), "department_manager")
        representative = _role_headers(client, _fresh_phone(), "department_representative")
        reviewer = _role_headers(client, _fresh_phone(), "reviewer")
        _, citizen = _citizen(client, _fresh_phone())

        department = _create_department(client, "Electricity Board")
        _add_member(client, department["id"], _user_id(client, manager), "manager")
        _add_member(client, department["id"], _user_id(client, representative), "member")

        report = _submit(client, citizen)
        _report_to_verified(client, report["id"])

        case = _create_case(client, manager, report["id"], department["id"], severity="high")
        case_id = case["id"]
        assert case["status"] == "submitted"

        _transition_case(client, case_id, manager, "under_review")
        _transition_case(client, case_id, manager, "verified")

        response = client.post(
            f"/api/v1/cases/{case_id}/assign",
            json={
                "department_id": department["id"],
                "assignee_user_id": _user_id(client, representative),
            },
            headers=manager,
        )
        assert response.status_code == 200, response.text
        check = client.get(f"/api/v1/cases/{case_id}", headers=manager)
        assert check.status_code == 200, check.text
        assert check.json()["status"] == "assigned"

        _transition_case(client, case_id, representative, "acknowledged")
        response = client.post(
            f"/api/v1/cases/{case_id}/respond",
            json={"kind": "acknowledgement", "body": "Team notified, engineer assigned."},
            headers=representative,
        )
        assert response.status_code == 200, response.text
        _transition_case(client, case_id, representative, "action_planned")

        response = client.post(
            f"/api/v1/cases/{case_id}/actions",
            json={"title": "Replace transformer", "target_date": "2026-09-01T10:00:00Z"},
            headers=representative,
        )
        assert response.status_code == 201, response.text
        action_id = response.json()["id"]
        response = client.patch(
            f"/api/v1/cases/{case_id}/actions/{action_id}",
            json={"status": "in_progress", "notes": "Parts ordered"},
            headers=representative,
        )
        assert response.status_code == 200, response.text

        _transition_case(client, case_id, representative, "in_progress")
        response = client.post(
            "/api/v1/resolutions",
            json={
                "case_id": case_id,
                "explanation": "Transformer replaced on site",
                "reference_numbers": {"job": "J-8831"},
                "evidence": [{"kind": "after", "notes": "New transformer installed"}],
            },
            headers=representative,
        )
        assert response.status_code == 201, response.text
        resolution_id = response.json()["id"]

        response = client.post(
            f"/api/v1/resolutions/{resolution_id}/review",
            json={"decision": "verified", "reason": "Site photos match report"},
            headers=reviewer,
        )
        assert response.status_code == 200, response.text
        assert response.json()["submission_status"] == "verified"

        response = client.get(f"/api/v1/cases/{case_id}", headers=citizen)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "resolved"

        response = client.post(
            f"/api/v1/cases/{case_id}/reopen-requests",
            json={"reason": "Streetlight still flickering", "evidence": "video note"},
            headers=citizen,
        )
        assert response.status_code == 201, response.text
        reopen_id = response.json()["id"]

        response = client.post(
            f"/api/v1/cases/{case_id}/reopen-requests/{reopen_id}/review",
            json={"decision": "approved", "note": "Engineer to revisit"},
            headers=manager,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"
        reopened = client.get(f"/api/v1/cases/{case_id}", headers=manager)
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["status"] == "reopened"

    def test_resolution_rejected_then_fixed(self, client: TestClient, sender) -> None:
        _setup(client, sender)
        manager = _role_headers(client, _fresh_phone(), "department_manager")
        representative = _role_headers(client, _fresh_phone(), "department_representative")
        reviewer = _role_headers(client, _fresh_phone(), "reviewer")
        _, citizen = _citizen(client, _fresh_phone())

        department = _create_department(client, "Public Works")
        _add_member(client, department["id"], _user_id(client, representative), "member")

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
                "explanation": "Cleaned the drain",
                "evidence": [{"kind": "after", "notes": "photo"}],
            },
            headers=representative,
        )
        assert response.status_code == 201, response.text
        resolution_id = response.json()["id"]

        response = client.post(
            f"/api/v1/resolutions/{resolution_id}/review",
            json={"decision": "more_evidence_required", "reason": "Blurry photo"},
            headers=reviewer,
        )
        assert response.status_code == 200, response.text
        assert response.json()["submission_status"] == "more_evidence_required"

        response = client.post(
            f"/api/v1/resolutions/{resolution_id}/evidence",
            json={"items": [{"kind": "after", "notes": "clear photo"}]},
            headers=representative,
        )
        assert response.status_code == 201, response.text

        response = client.post(
            "/api/v1/resolutions",
            json={
                "case_id": case_id,
                "explanation": "Replaced mesh cover",
                "evidence": [{"kind": "after", "notes": "clear photo"}],
            },
            headers=representative,
        )
        assert response.status_code == 201, response.text
        response = client.post(
            f"/api/v1/resolutions/{response.json()['id']}/review",
            json={"decision": "verified"},
            headers=reviewer,
        )
        assert response.status_code == 200, response.text


class TestCaseScoping:
    def test_department_members_only_see_own_cases(self, client: TestClient, sender) -> None:
        _setup(client, sender)
        manager_a = _role_headers(client, _fresh_phone(), "department_manager")
        manager_b = _role_headers(client, _fresh_phone(), "department_manager")
        _, citizen = _citizen(client, _fresh_phone())

        dept_a = _create_department(client, "Dept A")
        dept_b = _create_department(client, "Dept B")
        _add_member(client, dept_a["id"], _user_id(client, manager_a), "manager")
        _add_member(client, dept_b["id"], _user_id(client, manager_b), "manager")

        report = _submit(client, citizen)
        _report_to_verified(client, report["id"])
        case = _create_case(client, manager_a, report["id"], dept_a["id"])

        response = client.get(f"/api/v1/cases/{case['id']}", headers=manager_b)
        assert response.status_code == 403

        response = client.get("/api/v1/cases", headers=manager_a)
        assert response.status_code == 200, response.text
        assert any(c["id"] == case["id"] for c in response.json()["items"])

        response = client.get("/api/v1/cases", headers=manager_b)
        assert response.status_code == 200, response.text
        assert all(c["id"] != case["id"] for c in response.json()["items"])

    def test_citizen_lists_only_own_cases_and_public_timeline(
        self, client: TestClient, sender
    ) -> None:
        _setup(client, sender)
        manager = _role_headers(client, _fresh_phone(), "department_manager")
        representative = _role_headers(client, _fresh_phone(), "department_representative")
        _, other = _citizen(client, _fresh_phone())
        _, citizen = _citizen(client, _fresh_phone())

        department = _create_department(client, "Forest Dept")
        _add_member(client, department["id"], _user_id(client, representative), "member")

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
        client.post(
            f"/api/v1/cases/{case_id}/respond",
            json={"kind": "public_response", "body": "Inspector scheduled"},
            headers=representative,
        )
        client.post(
            f"/api/v1/cases/{case_id}/respond",
            json={
                "kind": "internal_note",
                "visibility": "internal",
                "body": "Corrupt official suspected",
            },
            headers=representative,
        )

        response = client.get("/api/v1/cases", headers=citizen)
        assert response.status_code == 200, response.text
        assert any(c["id"] == case_id for c in response.json()["items"])

        response = client.get("/api/v1/cases", headers=other)
        assert response.status_code == 200, response.text
        assert all(c["id"] != case_id for c in response.json()["items"])

        response = client.get(f"/api/v1/cases/{case_id}/timeline", headers=citizen)
        assert response.status_code == 200, response.text
        body = response.text
        assert "Inspector scheduled" in body
        assert "Corrupt official suspected" not in body

        response = client.get(f"/api/v1/cases/{case_id}", headers=other)
        assert response.status_code == 403


class TestSlaAndEscalation:
    def test_sla_pause_resume_and_escalation_engine(self, client: TestClient, sender) -> None:
        _setup(client, sender)
        manager = _role_headers(client, _fresh_phone(), "department_manager")
        representative = _role_headers(client, _fresh_phone(), "department_representative")
        _, citizen = _citizen(client, _fresh_phone())

        department = _create_department(client, "Crime Branch")
        _add_member(client, department["id"], _user_id(client, representative), "member")

        _seed_sla_policy(client)
        admin = _role_headers(client, _fresh_phone(), "admin")

        report = _submit(client, citizen)
        _report_to_verified(client, report["id"])
        case = _create_case(client, manager, report["id"], department["id"])
        case_id = case["id"]

        response = client.get(f"/api/v1/cases/{case_id}/sla", headers=manager)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "within_sla"

        response = client.post(
            f"/api/v1/cases/{case_id}/sla/pause",
            json={"reason": "awaiting floor plan from architect"},
            headers=admin,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "paused"

        response = client.post(f"/api/v1/cases/{case_id}/sla/resume", json={}, headers=admin)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "within_sla"

        async def verify_engine() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                instance = await session.scalar(
                    select(SlaInstance).where(SlaInstance.case_id == uuid.UUID(case_id))
                )
                assert instance is not None
                instance.started_at = instance.started_at.replace(year=2020)
                instance.target_resolution_at = instance.target_resolution_at.replace(year=2020)
                await session.commit()

                case_row = (
                    await session.execute(
                        select(CivicCase).where(CivicCase.id == uuid.UUID(case_id))
                    )
                ).scalar_one()
                await escalate_on_breach(session, case_row)
                await session.commit()
                escalations = list(
                    (
                        await session.execute(
                            select(CaseEscalation).where(
                                CaseEscalation.case_id == uuid.UUID(case_id)
                            )
                        )
                    ).scalars()
                )
                assert len(escalations) == 1
                assert escalations[0].level == 1

                case_row = (
                    await session.execute(
                        select(CivicCase).where(CivicCase.id == uuid.UUID(case_id))
                    )
                ).scalar_one()
                await escalate_on_breach(session, case_row)
                await session.commit()
                escalations = list(
                    (
                        await session.execute(
                            select(CaseEscalation).where(
                                CaseEscalation.case_id == uuid.UUID(case_id)
                            )
                        )
                    ).scalars()
                )
                assert len(escalations) == 1

        asyncio.run(verify_engine())

    def test_manual_escalation_requires_member(self, client: TestClient, sender) -> None:
        _setup(client, sender)
        manager = _role_headers(client, _fresh_phone(), "department_manager")
        outsider = _role_headers(client, _fresh_phone(), "department_manager")
        _, citizen = _citizen(client, _fresh_phone())

        department = _create_department(client, "Dept X")
        _add_member(client, department["id"], _user_id(client, manager), "manager")

        report = _submit(client, citizen)
        _report_to_verified(client, report["id"])
        case = _create_case(client, manager, report["id"], department["id"])

        response = client.post(
            f"/api/v1/cases/{case['id']}/escalate",
            json={"level": 2, "reason": "no response"},
            headers=outsider,
        )
        assert response.status_code == 403


def _citizen(client: TestClient, phone: str) -> tuple[str, dict[str, str]]:
    tokens = _register_and_verify(client, client._recording_sender, phone)  # type: ignore[attr-defined]
    return tokens["user"]["id"], _auth(tokens["access_token"])


def _user_id(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]
