"""Auth flow tests (SECURITY.md §2, ADR-008): registration, OTP, login, refresh rotation."""

import jwt as pyjwt

from tests.conftest import _register, _register_and_verify, _verify, last_otp


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRegistration:
    def test_register_returns_verify_pending(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        body = _register(client, sender, "9876543210")
        assert body["status"] == "verify_pending"
        assert body["contact_masked"].endswith("210")
        assert body["dev_otp_code"]
        assert len(body["dev_otp_code"]) == 6

    def test_register_requires_consent(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        response = client.post(
            "/api/v1/auth/register",
            json={
                "contact": "9876543211",
                "display_name": "A",
                "consent": False,
                "terms_version": "2026-08-01",
            },
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/consent_required")

    def test_register_duplicate_contact_conflict(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register(client, sender, "9876543212")
        response = client.post(
            "/api/v1/auth/register",
            json={
                "contact": "9876543212",
                "display_name": "B",
                "consent": True,
                "terms_version": "2026-08-01",
            },
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/already_registered")

    def test_phone_normalized_to_e164(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register(client, sender, "9876543213")
        assert sender.sent[-1][0] == "+919876543213"

    def test_weak_password_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        response = client.post(
            "/api/v1/auth/register",
            json={
                "contact": "9876543214",
                "display_name": "A",
                "password": "short",
                "consent": True,
                "terms_version": "2026-08-01",
            },
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/validation-error")


class TestOtpVerification:
    def test_verify_activates_and_returns_tokens(self, client, sender, settings) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543220")
        payload = pyjwt.decode(tokens["access_token"], settings.jwt_secret, algorithms=["HS256"])
        assert payload["roles"] == ["citizen"]
        assert tokens["token_type"] == "Bearer"
        assert tokens["expires_in"] == settings.jwt_access_ttl_seconds

    def test_wrong_code_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register(client, sender, "9876543221")
        response = client.post(
            "/api/v1/auth/verify-otp", json={"contact": "9876543221", "code": "000000"}
        )
        assert response.status_code == 401
        assert response.json()["type"].endswith("/invalid_otp")

    def test_otp_not_reusable(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register_and_verify(client, sender, "9876543222")
        code = last_otp(sender, "+919876543222")
        response = client.post(
            "/api/v1/auth/verify-otp", json={"contact": "9876543222", "code": code}
        )
        assert response.status_code == 401

    def test_max_attempts_locks_otp(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register(client, sender, "9876543223")
        for _ in range(5):
            client.post("/api/v1/auth/verify-otp", json={"contact": "9876543223", "code": "000000"})
        response = client.post(
            "/api/v1/auth/verify-otp", json={"contact": "9876543223", "code": "000000"}
        )
        assert response.status_code == 401
        assert response.json()["type"].endswith("/otp_attempts_exceeded")

    def test_resend_otp_new_code(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register(client, sender, "9876543224")
        first = last_otp(sender, "+919876543224")
        response = client.post("/api/v1/auth/resend-otp", json={"contact": "9876543224"})
        assert response.status_code == 200
        second = last_otp(sender, "+919876543224")
        assert first != second


class TestLogin:
    def test_login_password_success(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register_and_verify(client, sender, "9876543230")
        response = client.post(
            "/api/v1/auth/login", json={"contact": "9876543230", "password": "s3cure-pass!"}
        )
        assert response.status_code == 200
        assert response.json()["refresh_token"]

    def test_login_wrong_password_generic_error(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register_and_verify(client, sender, "9876543231")
        for password in ("wrong-pass", "wrong-pass2"):
            response = client.post(
                "/api/v1/auth/login", json={"contact": "9876543231", "password": password}
            )
            assert response.status_code == 401
        response = client.post(
            "/api/v1/auth/login", json={"contact": "9999999999", "password": "whatever1"}
        )
        assert response.status_code == 401
        assert response.json()["type"].endswith("/invalid_credentials")

    def test_login_otp_flow(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register_and_verify(client, sender, "9876543232")
        response = client.post("/api/v1/auth/login-otp", json={"contact": "9876543232"})
        assert response.status_code == 200
        tokens = _verify(client, sender, "9876543232")
        assert tokens["access_token"]

    def test_login_otp_unknown_contact(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        response = client.post("/api/v1/auth/login-otp", json={"contact": "9999999998"})
        assert response.status_code == 404

    def test_pending_account_cannot_login(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _register(client, sender, "9876543233")
        response = client.post(
            "/api/v1/auth/login", json={"contact": "9876543233", "password": "s3cure-pass!"}
        )
        assert response.status_code == 403
        assert response.json()["type"].endswith("/account_pending")


class TestRefreshRotation:
    def test_refresh_rotates_token(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543240")
        old_refresh = tokens["refresh_token"]
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert response.status_code == 200
        new_tokens = response.json()
        assert new_tokens["refresh_token"] != old_refresh
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert response.status_code == 401

    def test_reuse_detection_revokes_family(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543241")
        first = tokens["refresh_token"]
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
        second = response.json()["refresh_token"]
        client.post("/api/v1/auth/refresh", json={"refresh_token": first})  # reuse!
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": second})
        assert response.status_code == 401
        assert response.json()["type"].endswith("/token_reuse_detected")

    def test_garbage_refresh_token(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage" * 8})
        assert response.status_code == 401

    def test_logout_revokes_family(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876543242")
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers=_auth(tokens["access_token"]),
        )
        assert response.status_code == 200
        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 401


class TestAccessTokenGuard:
    def test_expired_token_rejected(self, client, settings) -> None:  # type: ignore[no-untyped-def]
        expired = pyjwt.encode(
            {"sub": "x", "roles": [], "exp": 0}, settings.jwt_secret, algorithm="HS256"
        )
        response = client.get("/api/v1/users/me", headers=_auth(expired))
        assert response.status_code == 401
        assert response.json()["type"].endswith("/token_expired")

    def test_missing_token(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401

    def test_garbage_token(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/api/v1/users/me", headers=_auth("not.a.token"))
        assert response.status_code == 401
