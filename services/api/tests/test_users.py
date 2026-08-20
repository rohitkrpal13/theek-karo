"""Profile, consent, audit, and RBAC tests (SECURITY.md §3/§6, API.md §3)."""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole


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


class TestProfile:
    def test_me_returns_profile(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543310")
        response = client.get("/api/v1/users/me", headers=_auth(tokens["access_token"]))
        assert response.status_code == 200
        body = response.json()
        assert body["display_name"] == "Amit Sharma"
        assert body["phone_masked"] == "+91•••••310"
        assert body["phone_verified"] is True
        assert body["roles"] == ["citizen"]
        assert body["status"] == "active"
        purposes = {c["purpose"] for c in body["consents"]}
        assert purposes == {"terms", "data_processing"}

    def test_patch_profile_audited(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543311")
        response = client.patch(
            "/api/v1/users/me",
            json={"display_name": "Amit Kumar", "locale": "hi"},
            headers=_auth(tokens["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Amit Kumar"
        audit = client.get("/api/v1/users/me/audit", headers=_auth(tokens["access_token"])).json()[
            "items"
        ]
        assert any(item["action"] == "user.profile_update" for item in audit)

    def test_invalid_locale_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543312")
        response = client.patch(
            "/api/v1/users/me", json={"locale": "en-US"}, headers=_auth(tokens["access_token"])
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_locale")


class TestConsent:
    def test_revoke_consent(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543320")
        response = client.post(
            "/api/v1/users/me/consents/revoke",
            json={"purpose": "terms"},
            headers=_auth(tokens["access_token"]),
        )
        assert response.status_code == 200
        consents = {c["purpose"]: c for c in response.json()["consents"]}
        assert consents["terms"]["revoked_at"] is not None

    def test_revoke_unknown_purpose(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543321")
        response = client.post(
            "/api/v1/users/me/consents/revoke",
            json={"purpose": "marketing"},
            headers=_auth(tokens["access_token"]),
        )
        assert response.status_code == 404


class TestAuditTrail:
    def test_sensitive_actions_recorded(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543330")
        client.post(
            "/api/v1/auth/login", json={"contact": "9876543330", "password": "s3cure-pass!"}
        )
        items = client.get("/api/v1/users/me/audit", headers=_auth(tokens["access_token"])).json()[
            "items"
        ]
        actions = {item["action"] for item in items}
        assert {"user.register", "otp.verify", "auth.login"} <= actions
        for item in items:
            assert item["entity_type"] == "user"
            assert item["entity_id"] == tokens["user"]["id"]


class TestRbac:
    def test_citizen_cannot_grant_roles(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        citizen = _register_and_verify(client, sender, "9876543350")
        target = _register_and_verify(client, sender, "9876543351")
        response = client.post(
            f"/api/v1/users/{target['user']['id']}/roles",
            json={"role": "volunteer"},
            headers=_auth(citizen["access_token"]),
        )
        assert response.status_code == 403
        assert response.json()["type"].endswith("/forbidden")

    def test_admin_grants_and_revokes_role(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        admin = _register_and_verify(client, sender, "9876543352")
        _promote_to_admin(client, admin["user"]["id"])
        target = _register_and_verify(client, sender, "9876543353")

        response = client.post(
            f"/api/v1/users/{target['user']['id']}/roles",
            json={"role": "volunteer"},
            headers=_auth(admin["access_token"]),
        )
        assert response.status_code == 200
        assert "volunteer" in response.json()["roles"]

        response = client.delete(
            f"/api/v1/users/{target['user']['id']}/roles/volunteer",
            headers=_auth(admin["access_token"]),
        )
        assert response.status_code == 200
        assert "volunteer" not in response.json()["roles"]

        audit = client.get("/api/v1/users/me/audit", headers=_auth(admin["access_token"])).json()[
            "items"
        ]
        actions = {item["action"] for item in audit}
        assert "user.role_grant" in actions and "user.role_revoke" in actions

    def test_admin_cannot_revoke_own_admin_role(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543354")
        _promote_to_admin(client, tokens["user"]["id"])
        response = client.delete(
            f"/api/v1/users/{tokens['user']['id']}/roles/admin",
            headers=_auth(tokens["access_token"]),
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/self_admin_revocation")

    def test_invalid_role_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        admin = _register_and_verify(client, sender, "9876543355")
        _promote_to_admin(client, admin["user"]["id"])
        target = _register_and_verify(client, sender, "9876543356")
        response = client.post(
            f"/api/v1/users/{target['user']['id']}/roles",
            json={"role": "superuser"},
            headers=_auth(admin["access_token"]),
        )
        assert response.status_code == 422
