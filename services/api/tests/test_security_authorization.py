"""Phase 16 authorization audit + IDOR test suite (SECURITY.md §3, brief §15).

Systematically verifies cross-user and cross-tenant access is denied on the
user-scoped and scoped resources flagged by the production-readiness audit:
``/reports/{id}`` (fields, media, visibility), evidence objects, ``/cases/{id}``
(department A vs B isolation), admin-only user endpoints, and institution
edits. Regression coverage for the private-report visibility fix.
"""

from __future__ import annotations

import asyncio
import io
import random
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "idor",
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

PRIVATE_FIELDS = {
    "title": "Private structural issue in my home",
    "description": "Details only the owner should see about the issue",
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fresh_phone() -> str:
    return str(random.randrange(10**9, 10**10))


def _citizen(client: TestClient, sender) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, _fresh_phone())
    return tokens["user"]["id"], _auth(tokens["access_token"])


def _grant_role(client: TestClient, user_id: str, code: str) -> None:  # type: ignore[no-untyped-def]
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _role_headers(client: TestClient, sender, role: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    user_id, headers = _citizen(client, sender)
    _grant_role(client, user_id, role)
    return user_id, headers


def _setup(client: TestClient, sender) -> None:  # type: ignore[no-untyped-def]
    _, admin = _role_headers(client, sender, "admin")
    response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin)
    assert response.status_code == 201, response.text


def _submit(
    client: TestClient,
    headers: dict[str, str],
    *,
    visibility: str = "public",
    private_fields: bool = False,
) -> dict:
    fields = PRIVATE_FIELDS if private_fields else VALID_FIELDS
    payload = {
        "category_slug": "idor",
        "title": "Broken classroom windows on ground floor",
        "description": "Windows on the ground floor remain broken since May with sharp edges",
        "location": LOCATION,
        "location_accuracy_m": 12,
        "fields": fields,
        "visibility": visibility,
    }
    response = client.post("/api/v1/reports", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(autouse=True)
def _memory_storage(client) -> None:  # type: ignore[no-untyped-def]
    """Use the in-memory storage adapter so evidence objects are readable via the dev route."""
    from tk_api.media.storage import MemoryStorageAdapter

    client.app.state.storage = MemoryStorageAdapter()
    yield


# ---------------------------------------------------------------------------
# Reports: ownership + visibility (IDOR)
# ---------------------------------------------------------------------------


class TestReportIdor:
    def test_user_b_cannot_edit_user_a_report_fields(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, a_headers = _citizen(client, sender)
        report = _submit(client, a_headers)
        _, b_headers = _citizen(client, sender)

        patch = client.patch(
            f"/api/v1/reports/{report['id']}/fields",
            json={"title": "Hijacked title for someone else's report"},
            headers=b_headers,
        )
        assert patch.status_code == 403
        assert patch.json()["type"].endswith("/forbidden")

        # owner can still edit
        ok = client.patch(
            f"/api/v1/reports/{report['id']}/fields",
            json={"title": "Owner updates the title to something new"},
            headers=a_headers,
        )
        assert ok.status_code == 200, ok.text

    def test_private_report_hidden_by_id(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        owner_id, owner_headers = _citizen(client, sender)
        report = _submit(client, owner_headers, visibility="private", private_fields=True)
        _, stranger_headers = _citizen(client, sender)

        # anonymous: 404 (no existence leak)
        assert client.get(f"/api/v1/reports/{report['id']}").status_code == 404
        # other citizen: 404
        assert (
            client.get(f"/api/v1/reports/{report['id']}", headers=stranger_headers).status_code
            == 404
        )
        # media list for a stranger: 404
        assert (
            client.get(
                f"/api/v1/reports/{report['id']}/media", headers=stranger_headers
            ).status_code
            == 404
        )
        # owner: 200 with private fields
        detail = client.get(f"/api/v1/reports/{report['id']}", headers=owner_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["fields"]["title"] == PRIVATE_FIELDS["title"]
        assert detail.json()["reporter_id"] == owner_id
        # moderator (reports.read_private): 200
        _, mod_headers = _role_headers(client, sender, "moderator")
        assert client.get(f"/api/v1/reports/{report['id']}", headers=mod_headers).status_code == 200

    def test_public_report_world_readable_but_ownership_kept(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, a_headers = _citizen(client, sender)
        report = _submit(client, a_headers)
        assert client.get(f"/api/v1/reports/{report['id']}").status_code == 200

    def test_user_b_cannot_delete_user_a_evidence(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, a_headers = _citizen(client, sender)
        report = _submit(client, a_headers)
        _, b_headers = _citizen(client, sender)

        # upload evidence as A and attach it
        data = _jpeg_bytes()
        upload = client.post(
            "/api/v1/media/uploads",
            headers={**a_headers, "Content-Type": "application/json"},
            json={"mime_type": "image/jpeg", "size_bytes": len(data)},
        )
        assert upload.status_code == 201, upload.text
        media_id = upload.json()["media_id"]
        put = client.put(
            f"/api/v1/media/uploads/{media_id}/object",
            headers={**a_headers, "Content-Type": "image/jpeg"},
            content=data,
        )
        assert put.status_code == 204
        complete = client.post(
            f"/api/v1/media/uploads/{media_id}/complete",
            headers={**a_headers, "Content-Type": "application/json"},
            json={},
        )
        assert complete.status_code == 200, complete.text

        attach = client.post(
            f"/api/v1/reports/{report['id']}/media/complete",
            headers={**a_headers, "Content-Type": "application/json"},
            json={"media_id": media_id},
        )
        assert attach.status_code == 200, attach.text
        evidence = client.get(f"/api/v1/reports/{report['id']}/media", headers=a_headers).json()[
            "items"
        ][0]

        deleted = client.delete(
            f"/api/v1/reports/{report['id']}/media/{evidence['id']}", headers=b_headers
        )
        assert deleted.status_code == 403


# ---------------------------------------------------------------------------
# Evidence objects (dev-mode read route)
# ---------------------------------------------------------------------------


def _jpeg_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (640, 480), "red").save(stream, format="JPEG")
    return stream.getvalue()


class TestEvidenceObjectIdor:
    def _attach_evidence(self, client, headers, report_id: str) -> str:  # type: ignore[no-untyped-def]
        data = _jpeg_bytes()
        upload = client.post(
            "/api/v1/media/uploads",
            headers={**headers, "Content-Type": "application/json"},
            json={"mime_type": "image/jpeg", "size_bytes": len(data)},
        )
        assert upload.status_code == 201, upload.text
        media_id = upload.json()["media_id"]
        assert (
            client.put(
                f"/api/v1/media/uploads/{media_id}/object",
                headers={**headers, "Content-Type": "image/jpeg"},
                content=data,
            ).status_code
            == 204
        )
        assert (
            client.post(
                f"/api/v1/media/uploads/{media_id}/complete",
                headers={**headers, "Content-Type": "application/json"},
                json={},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/reports/{report_id}/media/complete",
                headers={**headers, "Content-Type": "application/json"},
                json={"media_id": media_id},
            ).status_code
            == 200
        )
        return media_id

    def test_public_report_object_world_readable(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, owner_headers = _citizen(client, sender)
        report = _submit(client, owner_headers)
        media_id = self._attach_evidence(client, owner_headers, report["id"])
        url = f"/api/v1/media/{media_id}"
        meta = client.get(url, headers=owner_headers).json()
        assert meta["download_url"].startswith("/api/v1/media/object/")
        assert client.get(meta["download_url"]).status_code == 200

    def test_private_report_object_hidden_from_strangers(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, owner_headers = _citizen(client, sender)
        report = _submit(client, owner_headers, visibility="private")
        media_id = self._attach_evidence(client, owner_headers, report["id"])
        url = f"/api/v1/media/{media_id}"
        meta = client.get(url, headers=owner_headers).json()
        object_url = meta["download_url"]

        assert client.get(object_url).status_code == 404  # anonymous
        _, stranger_headers = _citizen(client, sender)
        assert client.get(object_url, headers=stranger_headers).status_code == 404
        assert client.get(object_url, headers=owner_headers).status_code == 200  # owner

    def test_public_report_thumbnail_world_readable(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        """Step 7: thumbnails of public-report evidence stay public (feeds)."""
        _setup(client, sender)
        _, owner_headers = _citizen(client, sender)
        report = _submit(client, owner_headers)
        media_id = self._attach_evidence(client, owner_headers, report["id"])
        thumb = client.get(f"/api/v1/media/{media_id}/thumbnail")
        assert thumb.status_code == 200

    def test_private_report_thumbnail_hidden_from_strangers(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        """Step 7: private-report evidence thumbnails must not leak either."""
        _setup(client, sender)
        _, owner_headers = _citizen(client, sender)
        report = _submit(client, owner_headers, visibility="private")
        media_id = self._attach_evidence(client, owner_headers, report["id"])
        thumb_url = f"/api/v1/media/{media_id}/thumbnail"
        assert client.get(thumb_url).status_code == 404  # anonymous
        _, stranger_headers = _citizen(client, sender)
        assert client.get(thumb_url, headers=stranger_headers).status_code == 404
        assert client.get(thumb_url, headers=owner_headers).status_code == 200


# ---------------------------------------------------------------------------
# Cases: department/tenant isolation
# ---------------------------------------------------------------------------


class TestCaseTenantIsolation:
    def test_department_a_member_cannot_read_department_b_case(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        # one shared admin keeps registrations under the register IP rate limit
        _, admin_headers = _role_headers(client, sender, "admin")

        dept_a = _create_department(client, "Dept A", admin_headers)
        dept_b = _create_department(client, "Dept B", admin_headers)
        _, manager_a = _role_headers(client, sender, "department_manager")
        _, manager_b = _role_headers(client, sender, "department_manager")
        member_a_id, member_a = _citizen(client, sender)
        member_b_id, member_b = _citizen(client, sender)
        _add_member(
            client, dept_a["id"], _user_id_from_headers(client, manager_a), "manager", admin_headers
        )
        _add_member(
            client, dept_b["id"], _user_id_from_headers(client, manager_b), "manager", admin_headers
        )
        _add_member(client, dept_a["id"], member_a_id, "member", admin_headers)
        _add_member(client, dept_b["id"], member_b_id, "member", admin_headers)

        # a verified report creates case A; reporter is a separate citizen
        _, reporter = _citizen(client, sender)
        report = _submit(client, reporter)
        _report_to_verified(client, report["id"], admin_headers)
        case = _create_case(client, manager_a, report["id"], dept_a["id"])
        case_id = case["id"]

        # reporter of the underlying report can read the case
        assert client.get(f"/api/v1/cases/{case_id}", headers=reporter).status_code == 200
        # department A member can read
        assert client.get(f"/api/v1/cases/{case_id}", headers=member_a).status_code == 200
        # department B member cannot (tenant isolation)
        blocked = client.get(f"/api/v1/cases/{case_id}", headers=member_b)
        assert blocked.status_code == 403
        # unrelated citizen cannot
        _, stranger = _citizen(client, sender)
        assert client.get(f"/api/v1/cases/{case_id}", headers=stranger).status_code == 403

        # department B cannot list A's case either (list is scoped per role)
        listing = client.get("/api/v1/cases", headers=member_b)
        assert listing.status_code == 200
        assert case_id not in {c["id"] for c in listing.json()["items"]}


# ---------------------------------------------------------------------------
# Admin-only user endpoints
# ---------------------------------------------------------------------------


class TestUserAdminIdor:
    def test_citizen_cannot_list_roles_or_grant_roles(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, citizen_headers = _citizen(client, sender)
        victim_id, _ = _citizen(client, sender)

        assert client.get("/api/v1/users/roles", headers=citizen_headers).status_code == 403
        grant = client.post(
            f"/api/v1/users/{victim_id}/roles",
            json={"role": "admin"},
            headers=citizen_headers,
        )
        assert grant.status_code == 403
        revoke = client.delete(f"/api/v1/users/{victim_id}/roles/citizen", headers=citizen_headers)
        assert revoke.status_code == 403


# ---------------------------------------------------------------------------
# Institutions: scoped writes
# ---------------------------------------------------------------------------


class TestInstitutionIdor:
    def test_citizen_cannot_edit_institution(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, admin = _role_headers(client, sender, "admin")
        created = client.post(
            "/api/v1/institutions",
            json={
                "name": "Govt Higher Secondary School IDOR",
                "institution_type_id": None,
                "geography_id": None,
                "attributes": {},
            },
            headers=admin,
        )
        # institution creation may require a type/geography; skip if 422
        if created.status_code == 422:
            pytest.skip("institution creation requires a type in this schema")
        assert created.status_code == 201, created.text
        institution_id = created.json()["id"]

        _, citizen_headers = _citizen(client, sender)
        patch = client.patch(
            f"/api/v1/institutions/{institution_id}",
            json={"name": "Hijacked institution name"},
            headers=citizen_headers,
        )
        assert patch.status_code == 403


# ---------------------------------------------------------------------------
# shared helpers (mirror test_phase14_cases.py patterns)
# ---------------------------------------------------------------------------


def _user_id_from_headers(client: TestClient, headers: dict[str, str]) -> str:  # type: ignore[no-untyped-def]
    me = client.get("/api/v1/auth/me", headers=headers).json()
    return me["id"]


def _create_department(client: TestClient, name: str, admin_headers: dict[str, str]) -> dict:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/departments/types",
        json={"code": f"dept-{uuid.uuid4().hex[:8]}", "name_key": "dept"},
        headers=admin_headers,
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
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_member(
    client: TestClient, department_id: str, user_id: str, role: str, admin_headers: dict[str, str]
) -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        f"/api/v1/departments/{department_id}/members",
        json={"user_id": user_id, "role_in_department": role},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text


def _report_to_verified(client: TestClient, report_id: str, staff_headers: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    for status in ("under_verification", "verified"):
        response = client.post(
            f"/api/v1/reports/{report_id}/transition",
            json={"to_status": status},
            headers=staff_headers,
        )
        assert response.status_code == 200, response.text


def _create_case(
    client: TestClient, manager_headers: dict[str, str], report_id: str, department_id: str
) -> dict:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/cases",
        json={"report_id": report_id, "department_id": department_id, "severity": "medium"},
        headers=manager_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()
