"""Phase 26 — Communication & Notification API tests.

Tests cover:
- Public alerts (create, review, publish, resolve)
- Communication templates (create, publish)
- Delivery records
- User devices (register, list, revoke)
- Campaigns (create, approve, cancel)
- Communication analytics
- Provider health
- Authorization (IDOR protection)
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
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
            if role and user:
                existing = await session.scalar(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == role.id,
                    )
                )
                if not existing:
                    session.add(UserRole(user_id=user.id, role_id=role.id))
                    await session.commit()

    import asyncio

    asyncio.run(grant())


# ---------------------------------------------------------------------------
# Public Alerts
# ---------------------------------------------------------------------------


def test_alert_create_and_review(client: TestClient) -> None:
    headers = _role_headers(client, "9100000001", "admin")

    # Create
    resp = client.post(
        "/api/v1/communication/alerts",
        json={
            "title": "Road closure on NH-44 near Jaipur",
            "body": "Due to construction, NH-44 is closed between km 200-210.",
            "category": "infrastructure",
            "severity": "warning",
            "source": "NHAI Official Notice",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    alert_id = resp.json()["id"]

    # Review & publish
    resp = client.post(
        f"/api/v1/communication/alerts/{alert_id}/review",
        json={"decision": "published", "note": "Verified with NHAI"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    # List published
    resp = client.get("/api/v1/communication/alerts", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1

    # Resolve
    resp = client.post(
        f"/api/v1/communication/alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_alert_reject(client: TestClient) -> None:
    headers = _role_headers(client, "9100000002", "admin")

    resp = client.post(
        "/api/v1/communication/alerts",
        json={
            "title": "Suspicious alert",
            "body": "This is a test.",
            "category": "other",
            "severity": "info",
            "source": "Unknown",
        },
        headers=headers,
    )
    alert_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/communication/alerts/{alert_id}/review",
        json={"decision": "rejected", "note": "Unverified source"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_template_create_and_publish(client: TestClient) -> None:
    headers = _role_headers(client, "9100000003", "admin")

    # Create
    resp = client.post(
        "/api/v1/communication/templates",
        json={
            "code": "case_update_en",
            "name": "Case Update (English)",
            "channel": "email",
            "locale": "en",
            "subject": "Case {ticket_no} updated",
            "body_text": "Your case {ticket_no} has been updated to {status}.",
            "category": "case",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["id"]
    assert resp.json()["version"] == 1

    # Publish
    resp = client.post(
        f"/api/v1/communication/templates/{template_id}/publish",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    # List
    resp = client.get("/api/v1/communication/templates", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


# ---------------------------------------------------------------------------
# User Devices
# ---------------------------------------------------------------------------


def test_device_register_list_revoke(client: TestClient) -> None:
    headers = _role_headers(client, "9100000004", "citizen")

    # Register
    resp = client.post(
        "/api/v1/communication/devices",
        json={
            "platform": "web",
            "push_token": "test-push-token-abc123",
            "device_name": "Chrome on macOS",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    device_id = resp.json()["id"]

    # List
    resp = client.get("/api/v1/communication/devices", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1

    # Revoke
    resp = client.delete(
        f"/api/v1/communication/devices/{device_id}",
        headers=headers,
    )
    assert resp.status_code == 204


def test_device_revoke_idor(client: TestClient) -> None:
    headers_a = _role_headers(client, "9100000005", "citizen")
    headers_b = _role_headers(client, "9100000006", "citizen")

    # Register device for user A
    resp = client.post(
        "/api/v1/communication/devices",
        json={"platform": "web", "push_token": "token-a"},
        headers=headers_a,
    )
    device_id = resp.json()["id"]

    # User B tries to revoke — should fail
    resp = client.delete(
        f"/api/v1/communication/devices/{device_id}",
        headers=headers_b,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------


def test_campaign_create_approve_cancel(client: TestClient) -> None:
    headers = _role_headers(client, "9100000007", "admin")

    # Create
    resp = client.post(
        "/api/v1/communication/campaigns",
        json={
            "name": "Community Cleanup Drive",
            "description": "Join us for a community cleanup drive this weekend.",
            "category": "community",
            "channel": "in_app",
            "subject": "Cleanup Drive",
            "body": "Join the community cleanup drive this Saturday at 9 AM.",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    campaign_id = resp.json()["id"]

    # Approve
    resp = client.post(
        f"/api/v1/communication/campaigns/{campaign_id}/approve",
        json={"estimated_recipients": 500},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Cancel
    resp = client.post(
        f"/api/v1/communication/campaigns/{campaign_id}/cancel",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def test_analytics_endpoint(client: TestClient) -> None:
    headers = _role_headers(client, "9100000008", "admin")

    resp = client.get("/api/v1/communication/analytics", headers=headers)
    assert resp.status_code == 200
    assert "totals" in resp.json()
    assert "delivery_rate" in resp.json()


def test_provider_health(client: TestClient) -> None:
    headers = _role_headers(client, "9100000009", "admin")

    resp = client.get("/api/v1/communication/providers/health", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


# ---------------------------------------------------------------------------
# Delivery Records
# ---------------------------------------------------------------------------


def test_delivery_records_list(client: TestClient) -> None:
    headers = _role_headers(client, "9100000010", "admin")

    resp = client.get("/api/v1/communication/deliveries", headers=headers)
    assert resp.status_code == 200
    assert "items" in resp.json()


# ---------------------------------------------------------------------------
# Alert Detail
# ---------------------------------------------------------------------------


def test_alert_detail(client: TestClient) -> None:
    headers = _role_headers(client, "9100000011", "admin")

    resp = client.post(
        "/api/v1/communication/alerts",
        json={
            "title": "Water supply disruption",
            "body": "Scheduled maintenance on water supply.",
            "category": "utility",
            "severity": "info",
            "source": "Municipal Corporation",
        },
        headers=headers,
    )
    alert_id = resp.json()["id"]

    resp = client.get(f"/api/v1/communication/alerts/{alert_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Water supply disruption"
    assert resp.json()["source"] == "Municipal Corporation"
