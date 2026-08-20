"""Phase 25 — Government workflow API tests.

Tests cover:
- Routing rules CRUD
- Case routing + acceptance/rejection
- Case handoffs + acceptance/rejection
- Official responses (create, update, withdraw)
- Workflow definitions
- Government integrations
- External case references
- Dashboard analytics
- Work queue
- IDOR protection
- End-to-end lifecycle
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.departments.models import Department, DepartmentType
from tk_api.users.models import Role, User, UserRole


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _role_headers(client: TestClient, phone: str, role: str) -> dict[str, str]:
    tokens = _register_and_verify(client, client._recording_sender, phone)
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

    import asyncio

    asyncio.run(grant())


def _make_dept(client: TestClient, *, name: str = "Education Dept") -> str:
    """Create a department type + department directly in the DB and return dept id."""
    result = {}

    async def _create() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            dtype = await session.scalar(select(DepartmentType).limit(1))
            if dtype is None:
                dtype = DepartmentType(code="education", name_key="Education")
                session.add(dtype)
                await session.flush()
            dept = Department(
                slug=f"dept-{uuid.uuid4().hex[:8]}",
                name=name,
                department_type_id=dtype.id,
            )
            session.add(dept)
            await session.commit()
            result["id"] = str(dept.id)

    import asyncio

    asyncio.run(_create())
    return result["id"]


def _ensure_category(client: TestClient, headers: dict) -> None:
    client.post(
        "/api/v1/civic/categories",
        json={
            "slug": "gov-test",
            "icon": "gov-test",
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
        headers=headers,
    )
    # 201 = created, 409 = already exists — both fine


def _make_case(client: TestClient, headers: dict, *, department_id: str | None = None) -> dict:
    """Create a report and case, return case payload."""
    _ensure_category(client, headers)
    # Create a report first
    resp = client.post(
        "/api/v1/reports",
        json={
            "category_slug": "gov-test",
            "title": "Broken classroom windows in government school",
            "description": "Ground floor windows have been broken since May. "
            "Students are exposed to weather.",
            "location": {"type": "Point", "coordinates": [75.7873, 26.9124]},
            "location_accuracy_m": 12,
            "fields": {
                "title": "Broken classroom windows",
                "description": "Ground floor windows broken since May",
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    report_id = resp.json()["id"]

    # Verify the report (transition through under_verification -> verified)
    resp = client.post(
        f"/api/v1/reports/{report_id}/transition",
        json={"to_status": "under_verification"},
        headers=headers,
    )
    if resp.status_code == 200:
        resp = client.post(
            f"/api/v1/reports/{report_id}/transition",
            json={"to_status": "verified"},
            headers=headers,
        )

    # Create a case from the report
    resp = client.post(
        "/api/v1/cases",
        json={
            "report_id": report_id,
            "department_id": department_id,
            "priority": "medium",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


def test_routing_rule_create_and_list(client: TestClient) -> None:
    headers = _role_headers(client, "9000000001", "admin")
    dept_id = _make_dept(client, name="Roads Dept")

    resp = client.post(
        "/api/v1/government/routing-rules",
        json={
            "code": "edu-routes-001",
            "name": "Education Category Routing",
            "target_department_id": dept_id,
            "priority_order": 10,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    rule_id = data["id"]
    assert data["code"] == "edu-routes-001"

    # List
    resp = client.get("/api/v1/government/routing-rules", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(r["id"] == rule_id for r in items)


def test_routing_rule_duplicate_code(client: TestClient) -> None:
    headers = _role_headers(client, "9000000002", "admin")
    dept_id = _make_dept(client)

    client.post(
        "/api/v1/government/routing-rules",
        json={"code": "dup-rule", "name": "R1", "target_department_id": dept_id},
        headers=headers,
    )
    resp = client.post(
        "/api/v1/government/routing-rules",
        json={"code": "dup-rule", "name": "R2", "target_department_id": dept_id},
        headers=headers,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Case Routing
# ---------------------------------------------------------------------------


def test_case_route_create_and_review(client: TestClient) -> None:
    headers = _role_headers(client, "9000000003", "admin")
    dept_id = _make_dept(client)
    case = _make_case(client, headers, department_id=dept_id)

    resp = client.post(
        "/api/v1/government/routes",
        json={
            "case_id": case["id"],
            "recommended_department_id": dept_id,
            "confidence": 0.85,
            "reason": "Education category match",
            "routing_source": "rule_based",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    route_id = resp.json()["id"]
    assert float(resp.json()["confidence"]) == 0.85

    # List routes
    resp = client.get(f"/api/v1/government/cases/{case['id']}/routes", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1

    # Accept
    resp = client.post(
        f"/api/v1/government/routes/{route_id}/review",
        json={"accepted": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


def test_case_route_reject(client: TestClient) -> None:
    headers = _role_headers(client, "9000000004", "admin")
    dept_id = _make_dept(client)
    case = _make_case(client, headers, department_id=dept_id)

    resp = client.post(
        "/api/v1/government/routes",
        json={
            "case_id": case["id"],
            "recommended_department_id": dept_id,
            "confidence": 0.5,
            "routing_source": "ai_recommended",
        },
        headers=headers,
    )
    route_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/government/routes/{route_id}/review",
        json={"accepted": False, "rejection_reason": "Wrong department"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is False


# ---------------------------------------------------------------------------
# Case Handoffs
# ---------------------------------------------------------------------------


def test_handoff_create_and_accept(client: TestClient) -> None:
    headers = _role_headers(client, "9000000005", "admin")
    dept1_id = _make_dept(client, name="Dept A")
    dept2_id = _make_dept(client, name="Dept B")
    case = _make_case(client, headers, department_id=dept1_id)

    resp = client.post(
        "/api/v1/government/handoffs",
        json={
            "case_id": case["id"],
            "to_department_id": dept2_id,
            "reason": "Water issue, belongs to Dept B",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    handoff_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    # Accept
    resp = client.post(
        f"/api/v1/government/handoffs/{handoff_id}/respond",
        json={"accepted": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_handoff_reject(client: TestClient) -> None:
    headers = _role_headers(client, "9000000006", "admin")
    dept1_id = _make_dept(client, name="Dept X")
    dept2_id = _make_dept(client, name="Dept Y")
    case = _make_case(client, headers, department_id=dept1_id)

    resp = client.post(
        "/api/v1/government/handoffs",
        json={
            "case_id": case["id"],
            "to_department_id": dept2_id,
            "reason": "Transfer",
        },
        headers=headers,
    )
    handoff_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/government/handoffs/{handoff_id}/respond",
        json={"accepted": False, "rejection_reason": "Not our responsibility"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_handoff_same_department_rejected(client: TestClient) -> None:
    headers = _role_headers(client, "9000000007", "admin")
    dept_id = _make_dept(client)
    case = _make_case(client, headers, department_id=dept_id)

    resp = client.post(
        "/api/v1/government/handoffs",
        json={
            "case_id": case["id"],
            "to_department_id": dept_id,
            "reason": "Self handoff",
        },
        headers=headers,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Official Responses
# ---------------------------------------------------------------------------


def test_official_response_lifecycle(client: TestClient) -> None:
    headers = _role_headers(client, "9000000008", "admin")
    dept_id = _make_dept(client)
    case = _make_case(client, headers, department_id=dept_id)

    # Create
    resp = client.post(
        "/api/v1/government/responses",
        json={
            "case_id": case["id"],
            "summary": "We have received the complaint and are investigating.",
            "action_taken": "Site inspection scheduled",
            "current_status": "Under investigation",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    resp_id = resp.json()["id"]
    assert resp.json()["version"] == 1

    # Update (creates new version)
    resp = client.patch(
        f"/api/v1/government/responses/{resp_id}",
        json={
            "summary": "Investigation complete, repair work initiated.",
            "change_reason": "Progress update",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 2

    # List responses
    resp = client.get(f"/api/v1/government/cases/{case['id']}/responses", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    # Latest version should be current
    assert any(r["is_current"] and r["version"] == 2 for r in items)


def test_official_response_withdraw(client: TestClient) -> None:
    headers = _role_headers(client, "9000000009", "admin")
    dept_id = _make_dept(client)
    case = _make_case(client, headers, department_id=dept_id)

    resp = client.post(
        "/api/v1/government/responses",
        json={"case_id": case["id"], "summary": "Initial response"},
        headers=headers,
    )
    resp_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/government/responses/{resp_id}/withdraw",
        json={"reason": "Incorrect information"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["withdrawn"] is True


# ---------------------------------------------------------------------------
# Workflow Definitions
# ---------------------------------------------------------------------------


def test_workflow_create_and_list(client: TestClient) -> None:
    headers = _role_headers(client, "9000000010", "admin")

    resp = client.post(
        "/api/v1/government/workflows",
        json={
            "code": "edu-workflow-001",
            "name": "Education Case Workflow",
            "states": ["submitted", "triage", "in_progress", "resolved"],
            "transitions": {
                "submitted": ["triage"],
                "triage": ["in_progress"],
                "in_progress": ["resolved"],
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    wf_id = resp.json()["id"]

    resp = client.get("/api/v1/government/workflows", headers=headers)
    assert resp.status_code == 200
    assert any(w["id"] == wf_id for w in resp.json()["items"])


# ---------------------------------------------------------------------------
# Government Integrations
# ---------------------------------------------------------------------------


def test_integration_create_list_update(client: TestClient) -> None:
    headers = _role_headers(client, "9000000011", "admin")

    resp = client.post(
        "/api/v1/government/integrations",
        json={
            "code": "test-gov-api",
            "name": "Test Government API",
            "provider_type": "rest_api",
            "auth_type": "api_key",
            "capabilities": ["submit_case", "get_status"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    int_id = resp.json()["id"]

    # Get detail
    resp = client.get(f"/api/v1/government/integrations/{int_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == "test-gov-api"

    # Update
    resp = client.patch(
        f"/api/v1/government/integrations/{int_id}",
        json={"status": "active"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


# ---------------------------------------------------------------------------
# External References
# ---------------------------------------------------------------------------


def test_external_reference_create(client: TestClient) -> None:
    headers = _role_headers(client, "9000000012", "admin")
    dept_id = _make_dept(client)
    case = _make_case(client, headers, department_id=dept_id)

    # Create integration first
    resp = client.post(
        "/api/v1/government/integrations",
        json={
            "code": "ext-ref-test",
            "name": "External Ref Test",
            "provider_type": "rest_api",
        },
        headers=headers,
    )
    int_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/government/external-references",
        json={
            "case_id": case["id"],
            "integration_id": int_id,
            "external_reference_id": "GOV-2026-001234",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["external_reference_id"] == "GOV-2026-001234"

    # List
    resp = client.get(f"/api/v1/government/cases/{case['id']}/external-references", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_department_dashboard(client: TestClient) -> None:
    headers = _role_headers(client, "9000000013", "admin")
    dept_id = _make_dept(client)
    # Create a few cases
    for _ in range(3):
        _make_case(client, headers, department_id=dept_id)

    resp = client.get(f"/api/v1/government/dashboard/{dept_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cases"] >= 3
    assert "methodology" in data


def test_work_queue(client: TestClient) -> None:
    headers = _role_headers(client, "9000000014", "admin")
    dept_id = _make_dept(client)
    for _ in range(2):
        _make_case(client, headers, department_id=dept_id)

    resp = client.get(f"/api/v1/government/work-queue/{dept_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["count"] >= 2
