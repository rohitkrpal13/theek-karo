"""Phase 7 Authentication, Session, and Account Security test suite (PRD §14, SECURITY.md §2-§4)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_email_registration_and_verification_flow(client: TestClient) -> None:
    # 1. Register with email
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "contact": "citizen.sharma@example.com",
            "display_name": "Citizen Sharma",
            "username": "sharma_citizen",
            "password": "SecurePassword123!",
            "consent": True,
            "terms_version": "2026-v1",
            "locale": "hi",
        },
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["status"] == "verify_pending"
    raw_token = reg_data["dev_verification_token"]
    assert raw_token is not None

    # 2. Cannot login before verification
    login_res = client.post(
        "/api/v1/auth/login",
        json={"contact": "citizen.sharma@example.com", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 403
    assert login_res.json()["type"].endswith("/account_pending")

    # 3. Verify email with single-use token
    verify_res = client.post(
        "/api/v1/auth/verify-email",
        json={"token": raw_token},
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert "access_token" in verify_data
    assert verify_data["user"]["status"] == "active"
    assert "citizen" in verify_data["user"]["roles"]

    # 4. Token cannot be reused (single-use enforcement)
    reuse_res = client.post(
        "/api/v1/auth/verify-email",
        json={"token": raw_token},
    )
    assert reuse_res.status_code == 400
    assert reuse_res.json()["type"].endswith("/invalid_token")

    # 5. Successful login after verification with email
    login_ok = client.post(
        "/api/v1/auth/login",
        json={"contact": "citizen.sharma@example.com", "password": "SecurePassword123!"},
    )
    assert login_ok.status_code == 200
    assert login_ok.json()["user"]["username"] == "sharma_citizen"

    # 6. Successful login with username
    login_uname = client.post(
        "/api/v1/auth/login",
        json={"contact": "sharma_citizen", "password": "SecurePassword123!"},
    )
    assert login_uname.status_code == 200
    assert login_uname.json()["user"]["email"] == "citizen.sharma@example.com"


def test_username_validation_and_reserved_names(client: TestClient) -> None:
    # Invalid characters
    res_inv = client.post(
        "/api/v1/auth/register",
        json={
            "contact": "bad.username@example.com",
            "display_name": "Bad User",
            "username": "bad-user!@",
            "password": "SecurePassword123!",
            "consent": True,
        },
    )
    assert res_inv.status_code == 422
    assert res_inv.json()["type"].endswith("/invalid_username")

    # Reserved name
    res_res = client.post(
        "/api/v1/auth/register",
        json={
            "contact": "fake.admin@example.com",
            "display_name": "Fake Admin",
            "username": "admin",
            "password": "SecurePassword123!",
            "consent": True,
        },
    )
    assert res_res.status_code == 422
    assert res_res.json()["type"].endswith("/reserved_username")


def test_password_policy_and_generic_forgot_password(client: TestClient) -> None:
    # Weak password rejected
    weak_res = client.post(
        "/api/v1/auth/register",
        json={
            "contact": "weak.pw@example.com",
            "display_name": "Weak User",
            "password": "123",
            "consent": True,
        },
    )
    assert weak_res.status_code == 422
    assert weak_res.json()["type"].endswith("/validation-error")

    # Forgot password returns safe generic response for non-existent user
    forgot_nonexist = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert forgot_nonexist.status_code == 200
    assert forgot_nonexist.json()["status"] == "reset_link_sent"
    assert forgot_nonexist.json().get("dev_reset_token") is None


def test_password_reset_and_session_invalidation(client: TestClient) -> None:
    # Register and verify
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "contact": "reset.user@example.com",
            "display_name": "Reset User",
            "password": "OldPassword123!",
            "consent": True,
        },
    )
    raw_vtoken = reg.json()["dev_verification_token"]
    v_res = client.post("/api/v1/auth/verify-email", json={"token": raw_vtoken})
    old_refresh_token = v_res.json()["refresh_token"]

    # Request password reset
    forgot_res = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset.user@example.com"},
    )
    assert forgot_res.status_code == 200
    raw_reset_token = forgot_res.json()["dev_reset_token"]
    assert raw_reset_token is not None

    # Execute password reset
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_reset_token, "new_password": "NewSecurePassword999!"},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "password_reset_success"

    # Old refresh token is revoked
    ref_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert ref_res.status_code == 401

    # Old password fails login
    old_login = client.post(
        "/api/v1/auth/login",
        json={"contact": "reset.user@example.com", "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # New password succeeds
    new_login = client.post(
        "/api/v1/auth/login",
        json={"contact": "reset.user@example.com", "password": "NewSecurePassword999!"},
    )
    assert new_login.status_code == 200


def test_session_management_and_logout_all(client: TestClient) -> None:
    # Register and verify
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "contact": "session.user@example.com",
            "display_name": "Session User",
            "password": "Password12345!",
            "consent": True,
        },
    )
    raw_vtoken = reg.json()["dev_verification_token"]
    v_res = client.post("/api/v1/auth/verify-email", json={"token": raw_vtoken})
    token1 = v_res.json()["access_token"]

    # Login a second time to create another session
    l_res = client.post(
        "/api/v1/auth/login",
        json={"contact": "session.user@example.com", "password": "Password12345!"},
    )
    ref2 = l_res.json()["refresh_token"]

    # List active sessions
    sess_res = client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert sess_res.status_code == 200
    sessions = sess_res.json()["items"]
    assert len(sessions) >= 2

    # Logout-all
    logout_all_res = client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert logout_all_res.status_code == 200

    # Refresh with token 2 now fails
    ref_fail = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ref2},
    )
    assert ref_fail.status_code == 401


def test_google_oauth_callback_flow(client: TestClient) -> None:
    # 1. Get OAuth Auth URL
    url_res = client.get(
        "/api/v1/auth/oauth/google/url?redirect_uri=http://localhost:3000/auth/callback"
    )
    assert url_res.status_code == 200
    assert "accounts.google.com" in url_res.json()["url"]
    state = url_res.json()["state"]

    # 2. Complete callback (creates new user and links Google OAuth)
    cb_res = client.post(
        "/api/v1/auth/oauth/google/callback",
        json={
            "code": "test-google-auth-code-12345",
            "state": state,
            "redirect_uri": "http://localhost:3000/auth/callback",
        },
    )
    assert cb_res.status_code == 200
    cb_data = cb_res.json()
    assert "access_token" in cb_data
    assert cb_data["user"]["status"] == "active"
    assert "citizen" in cb_data["user"]["roles"]


def test_account_anonymization_and_deletion(client: TestClient) -> None:
    # Register and verify
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "contact": "delete.me@example.com",
            "display_name": "Delete Me",
            "username": "delete_me_now",
            "password": "Password12345!",
            "consent": True,
        },
    )
    raw_vtoken = reg.json()["dev_verification_token"]
    v_res = client.post("/api/v1/auth/verify-email", json={"token": raw_vtoken})
    token = v_res.json()["access_token"]

    # Delete account
    del_res = client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "account_deleted_success"

    # Subsequent authenticated requests rejected
    me_res = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 401
