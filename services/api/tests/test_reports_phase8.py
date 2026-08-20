"""Phase 8 civic reporting, drafts, media evidence, AI intake tests (PRD §7-§14)."""

from __future__ import annotations

import asyncio
import io
import uuid

from PIL import Image
from sqlalchemy import select
from starlette.testclient import TestClient

from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, UserRole


def _jpeg_bytes(size: tuple[int, int] = (16, 16)) -> bytes:
    """A real, decodable JPEG (the Phase 6 scan gate rejects truncated files)."""
    stream = io.BytesIO()
    Image.new("RGB", size, "blue").save(stream, format="JPEG")
    return stream.getvalue()


CATEGORY = {
    "slug": "sanitation",
    "icon": "trash",
    "form_schema": {
        "type": "object",
        "properties": {"waste_type": {"type": "string"}},
        "required": [],
    },
    "verification_policy": {"min_verifications": 2},
    "attachment_rules": {},
}

LOCATION = {"type": "Point", "coordinates": [75.7873, 26.9124]}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, sender, phone: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    contact = f"user_{phone}@example.com"
    res = client.post(
        "/api/v1/auth/register",
        json={
            "contact": contact,
            "display_name": f"User {phone[-4:]}",
            "password": "Password123!",
            "consent": True,
        },
    )
    assert res.status_code == 201, res.text
    token = res.json()["dev_verification_token"]
    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"token": token},
    )
    assert verified.status_code == 200, verified.text
    user_id = verified.json()["user"]["id"]
    return user_id, _auth(verified.json()["access_token"])


def _admin_headers(client: TestClient, sender) -> dict[str, str]:  # type: ignore[no-untyped-def]
    uid, headers = _register(client, sender, "9876543200")

    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == "admin"))
            if role:
                session.add(UserRole(user_id=uuid.UUID(uid), role_id=role.id))
                await session.commit()

    asyncio.run(grant())
    return headers


def _setup_category(client: TestClient, sender) -> None:  # type: ignore[no-untyped-def]
    admin = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin)


class TestPhase8Drafts:
    def test_draft_crud_and_submit(self, client: TestClient, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _uid, headers = _register(client, sender, "9876543201")

        # 1. Create draft
        draft_res = client.post(
            "/api/v1/reports/drafts",
            json={
                "category_slug": "sanitation",
                "title": "Overflowing garbage bin",
                "description": "Garbage has not been collected for 5 days",
                "location": LOCATION,
                "location_accuracy_m": 10.0,
                "coordinate_source": "DEVICE_LOCATION",
                "severity": "high",
            },
            headers=headers,
        )
        assert draft_res.status_code == 201
        draft = draft_res.json()
        assert draft["status"] == "draft"
        assert draft["title"] == "Overflowing garbage bin"
        assert draft["coordinate_source"] == "DEVICE_LOCATION"

        # 2. List drafts
        list_res = client.get("/api/v1/reports/drafts", headers=headers)
        assert list_res.status_code == 200
        items = list_res.json()["items"]
        assert any(d["id"] == draft["id"] for d in items)

        # 3. Update draft
        update_res = client.patch(
            f"/api/v1/reports/drafts/{draft['id']}",
            json={"title": "Updated overflowing garbage bin title"},
            headers=headers,
        )
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "Updated overflowing garbage bin title"

        # 4. Another user cannot update or delete this draft (IDOR protection)
        _, other_headers = _register(client, sender, "9876543202")
        blocked_patch = client.patch(
            f"/api/v1/reports/drafts/{draft['id']}",
            json={"title": "Hacked Title"},
            headers=other_headers,
        )
        assert blocked_patch.status_code == 403

        blocked_delete = client.delete(
            f"/api/v1/reports/drafts/{draft['id']}",
            headers=other_headers,
        )
        assert blocked_delete.status_code == 403

        # 5. Submit draft
        submit_res = client.post(
            f"/api/v1/reports/drafts/{draft['id']}/submit",
            json={},
            headers=headers,
        )
        assert submit_res.status_code == 200
        submitted = submit_res.json()
        assert submitted["status"] == "submitted"

        # 6. Cannot edit submitted draft as draft
        resubmit = client.post(
            f"/api/v1/reports/drafts/{draft['id']}/submit",
            json={},
            headers=headers,
        )
        assert resubmit.status_code == 409


class TestPhase8MediaEvidence:
    def test_media_upload_and_attachment(self, client: TestClient, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _uid, headers = _register(client, sender, "9876543203")

        # 1. Create a report
        rep_res = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "sanitation",
                "title": "Broken street drainage pipe",
                "description": "Drainage water is overflowing onto the main street road",
                "location": LOCATION,
                "location_accuracy_m": 15.0,
                "coordinate_source": "MAP_SELECTED",
                "severity": "medium",
            },
            headers=headers,
        )
        assert rep_res.status_code == 201
        report = rep_res.json()

        jpeg_bytes = _jpeg_bytes()

        # 2. Request upload slot with matching size
        slot_res = client.post(
            f"/api/v1/reports/{report['id']}/media/upload-url",
            json={"mime_type": "image/jpeg", "size_bytes": len(jpeg_bytes), "kind": "image"},
            headers=headers,
        )
        assert slot_res.status_code == 200
        slot = slot_res.json()
        media_id = slot["media_id"]

        # Simulate upload bytes into dev storage
        storage = client.app.state.storage
        storage.save_bytes(
            client.app.state.settings.media_minio_bucket,
            slot["object_key"],
            jpeg_bytes,
        )

        # 3. Complete media evidence upload
        complete_res = client.post(
            f"/api/v1/reports/{report['id']}/media/complete",
            json={"media_id": media_id},
            headers=headers,
        )
        assert complete_res.status_code == 200
        ev = complete_res.json()
        assert ev["report_id"] == report["id"]
        assert ev["kind"] == "image"

        # 4. List media evidence
        list_ev = client.get(f"/api/v1/reports/{report['id']}/media")
        assert list_ev.status_code == 200
        assert len(list_ev.json()["items"]) >= 1

        # 5. Delete media evidence
        del_res = client.delete(
            f"/api/v1/reports/{report['id']}/media/{ev['id']}",
            headers=headers,
        )
        assert del_res.status_code == 204


class TestPhase8AiIntake:
    def test_ai_suggest_intake(self, client: TestClient, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _uid, headers = _register(client, sender, "9876543204")

        suggest_res = client.post(
            "/api/v1/reports/ai/suggest",
            json={
                "description": "Dangerous open pothole on the main road causing accidents",
                "location": LOCATION,
            },
            headers=headers,
        )
        assert suggest_res.status_code == 200
        res = suggest_res.json()
        assert res["category_suggestion"] == "roads"
        assert res["severity_suggestion"] == "critical"
        title_lower = res["title_suggestion"].lower()
        assert "pothole" in title_lower or "road" in title_lower


class TestPhase8DuplicatesAndVerifications:
    def test_duplicates_and_verifications_list(self, client: TestClient, sender) -> None:  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _u1, h1 = _register(client, sender, "9876543205")
        _u2, h2 = _register(client, sender, "9876543206")

        # Report 1
        r1 = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "sanitation",
                "title": "Garbage dump near public school",
                "description": "A huge pile of garbage has formed near the public school gate",
                "location": LOCATION,
                "location_accuracy_m": 10.0,
            },
            headers=h1,
        ).json()

        # Report 2 (nearby)
        r2 = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "sanitation",
                "title": "Waste accumulated outside school",
                "description": "Waste has been dumped outside the school gate",
                "location": {"type": "Point", "coordinates": [75.7875, 26.9125]},
                "location_accuracy_m": 12.0,
            },
            headers=h2,
        ).json()

        # Check duplicate candidates
        dups = client.get(f"/api/v1/reports/{r1['id']}/duplicates")
        assert dups.status_code == 200
        dup_items = dups.json()["items"]
        assert any(d["candidate_report_id"] == r2["id"] for d in dup_items)

        # Verification by user 2
        v_res = client.post(
            f"/api/v1/reports/{r1['id']}/verifications",
            json={"kind": "confirm", "notes": "Verified in person on Monday morning"},
            headers=h2,
        )
        assert v_res.status_code == 201

        # Check verifications list
        v_list = client.get(f"/api/v1/reports/{r1['id']}/verifications")
        assert v_list.status_code == 200
        assert v_list.json()["confirmations_count"] == 1
        assert len(v_list.json()["items"]) == 1
