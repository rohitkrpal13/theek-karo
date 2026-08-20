"""Phase 16 auth hardening tests (SECURITY.md §2/§4): TOTP MFA flow (setup /
enable / challenge / disable), privileged-role MFA enforcement, and per-account
login backoff / lockout."""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import RecordingSender, _build_app, _register_and_verify
from tk_api.auth.mfa import totp_code
from tk_api.core.config import Settings
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole

# RFC 6238 Appendix B vector key (base32 of ASCII "12345678901234567890")
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _grant_role(client: TestClient, user_id: str, code: str) -> None:  # type: ignore[no-untyped-def]
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


@contextmanager
def _mfa_app(enforce_privileged: bool = False, **overrides) -> TestClient:  # type: ignore[no-untyped-def]
    """Yield an isolated app (own in-memory DB) with custom auth settings.

    Entering the TestClient context runs the lifespan (engine/limiter/throttle
    wiring); the engine is disposed on exit.
    """
    settings = Settings(
        _env_file=None,
        env="test",
        log_level="WARNING",
        database_url="sqlite+aiosqlite://",
        rate_limit_mode="memory",
        otp_channel="console",
        jwt_secret="test-secret-not-for-prod",
        mfa_enforce_privileged=enforce_privileged,
        **overrides,
    )
    app, engine = _build_app(settings)
    sender = RecordingSender()
    app.state.otp_sender = sender
    try:
        with TestClient(app) as client:
            client._recording_sender = sender  # type: ignore[attr-defined]
            yield client
    finally:
        asyncio.run(engine.dispose())


def _fresh_phone() -> str:
    return str(random.randrange(10**9, 10**10))  # 10-digit number


def _register(client: TestClient, sender: RecordingSender) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, _fresh_phone())
    return tokens["user"]["id"], _auth(tokens["access_token"])


class TestTotpUnit:
    def test_rfc6238_vectors(self) -> None:
        from datetime import UTC, datetime

        from tk_api.auth.mfa import totp_code

        vectors = [
            (59, "287082"),
            (1111111109, "081804"),
            (1111111111, "050471"),
            (1234567890, "005924"),
            (2000000000, "279037"),
            (20000000000, "353130"),
        ]
        for t, expected in vectors:
            assert totp_code(RFC_SECRET, at=datetime.fromtimestamp(t, tz=UTC)) == expected

    def test_verify_window_and_rejection(self) -> None:
        from datetime import UTC, datetime

        from tk_api.auth.mfa import verify_totp

        at = datetime.fromtimestamp(59, tz=UTC)
        assert verify_totp(RFC_SECRET, "287082", at=at)
        assert not verify_totp(RFC_SECRET, "000000", at=at)
        assert not verify_totp(RFC_SECRET, "28708", at=at)  # wrong length
        assert not verify_totp(RFC_SECRET, "28708a", at=at)  # non-digit

    def test_secret_generation(self) -> None:
        from tk_api.auth.mfa import generate_totp_secret

        secret = generate_totp_secret()
        assert len(secret) == 32
        assert secret != generate_totp_secret()
        # generated secrets round-trip through the code generator
        assert len(totp_code(secret)) == 6


class TestMfaFlow:
    def test_setup_enable_challenge_verify_disable(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, headers = _register(client, sender)

        status = client.get("/api/v1/auth/mfa/status", headers=headers)
        assert status.status_code == 200
        assert status.json() == {
            "enabled": False,
            "required_by_role": False,
            "setup_required": False,
        }

        setup = client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]
        assert len(secret) == 32
        assert "otpauth://totp/" in setup.json()["otpauth_uri"]

        # wrong code cannot enable
        bad = client.post("/api/v1/auth/mfa/enable", json={"code": "000000"}, headers=headers)
        assert bad.status_code == 401
        assert bad.json()["type"].endswith("/invalid_mfa_code")

        code = totp_code(secret)
        enabled = client.post("/api/v1/auth/mfa/enable", json={"code": code}, headers=headers)
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["mfa_enabled"] is True

        status = client.get("/api/v1/auth/mfa/status", headers=headers)
        assert status.json()["enabled"] is True

        # password login now demands the challenge instead of tokens
        login = client.post(
            "/api/v1/auth/login",
            json={"contact": _registered_contact(client, headers), "password": "s3cure-pass!"},
        )
        assert login.status_code == 200, login.text
        body = login.json()
        assert body["mfa_required"] is True
        assert body["challenge_token"]
        assert "access_token" not in body

        # wrong challenge code rejected
        bad_verify = client.post(
            "/api/v1/auth/mfa/verify",
            json={"challenge_token": body["challenge_token"], "code": "000000"},
        )
        assert bad_verify.status_code == 401
        assert bad_verify.json()["type"].endswith("/invalid_mfa_code")

        # correct code exchanges for tokens
        verified = client.post(
            "/api/v1/auth/mfa/verify",
            json={"challenge_token": body["challenge_token"], "code": totp_code(secret)},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers=_auth(verified.json()["access_token"]))
        assert me.status_code == 200
        assert me.json()["mfa_enabled"] is True

        # disable requires the current code and turns the challenge off
        disabled = client.post(
            "/api/v1/auth/mfa/disable", json={"code": totp_code(secret)}, headers=headers
        )
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["mfa_enabled"] is False
        login = client.post(
            "/api/v1/auth/login",
            json={"contact": _registered_contact(client, headers), "password": "s3cure-pass!"},
        )
        assert login.json().get("mfa_required") is not True
        assert login.json()["access_token"]

    def test_setup_rotates_secret_and_requires_reenable(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, headers = _register(client, sender)
        first = client.post("/api/v1/auth/mfa/setup", headers=headers).json()["secret"]
        second = client.post("/api/v1/auth/mfa/setup", headers=headers).json()["secret"]
        assert first != second
        # old secret no longer works
        bad = client.post(
            "/api/v1/auth/mfa/enable", json={"code": totp_code(first)}, headers=headers
        )
        assert bad.status_code == 401


def _registered_contact(client: TestClient, headers: dict[str, str]) -> str:  # type: ignore[no-untyped-def]
    me = client.get("/api/v1/auth/me", headers=headers).json()
    return me["phone"] or me["email"]


class TestMfaPrivilegedEnforcement:
    def test_privileged_role_blocked_until_mfa(self) -> None:
        with _mfa_app(enforce_privileged=True) as client:
            sender = client._recording_sender  # type: ignore[attr-defined]
            user_id, headers = _register(client, sender)
            _grant_role(client, user_id, "admin")

            # bootstrap endpoints still reachable
            assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
            assert client.get("/api/v1/users/me", headers=headers).status_code == 200

            # role-gated endpoint blocked with mfa_required
            blocked = client.get("/api/v1/users/roles", headers=headers)
            assert blocked.status_code == 403, blocked.text
            assert blocked.json()["type"].endswith("/mfa_required")

            # permission-gated endpoint blocked too (departments.manage)
            blocked2 = client.post(
                "/api/v1/departments/types",
                json={"code": "mfa-gate-test", "name_key": "mfa.gate.test"},
                headers=headers,
            )
            assert blocked2.status_code == 403
            assert blocked2.json()["type"].endswith("/mfa_required")

            # set up + enable MFA
            secret = client.post("/api/v1/auth/mfa/setup", headers=headers).json()["secret"]
            enabled = client.post(
                "/api/v1/auth/mfa/enable", json={"code": totp_code(secret)}, headers=headers
            )
            assert enabled.status_code == 200, enabled.text

            assert client.get("/api/v1/users/roles", headers=headers).status_code == 200
            created = client.post(
                "/api/v1/departments/types",
                json={"code": "mfa-gate-test", "name_key": "mfa.gate.test"},
                headers=headers,
            )
            assert created.status_code == 201, created.text

    def test_super_admin_also_gated(self) -> None:
        with _mfa_app(enforce_privileged=True) as client:
            sender = client._recording_sender  # type: ignore[attr-defined]
            user_id, headers = _register(client, sender)
            _grant_role(client, user_id, "super_admin")
            blocked = client.get("/api/v1/users/roles", headers=headers)
            assert blocked.status_code == 403
            assert blocked.json()["type"].endswith("/mfa_required")

    def test_gate_off_by_default(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        # default settings (enforce off) keep the dev/test behavior
        user_id, headers = _register(client, sender)
        _grant_role(client, user_id, "admin")
        assert client.get("/api/v1/users/roles", headers=headers).status_code == 200


class TestLoginBackoff:
    def test_account_locks_after_consecutive_failures_and_resets_on_success(self) -> None:
        with _mfa_app(
            login_max_failures=3,
            login_backoff_base_seconds=60,
        ) as client:
            sender = client._recording_sender  # type: ignore[attr-defined]
            phone = _fresh_phone()
            _register_and_verify(client, sender, phone)
            contact = "+91" + phone

            def attempt() -> int:
                return client.post(
                    "/api/v1/auth/login",
                    json={"contact": contact, "password": "wrong-password"},
                ).status_code

            # two failures, then a success resets the counter
            assert attempt() == 401
            assert attempt() == 401
            ok = client.post(
                "/api/v1/auth/login",
                json={"contact": contact, "password": "s3cure-pass!"},
            )
            assert ok.status_code == 200, ok.text

            # three consecutive failures lock the account
            assert attempt() == 401
            assert attempt() == 401
            assert attempt() == 401
            locked = client.post(
                "/api/v1/auth/login",
                json={"contact": contact, "password": "s3cure-pass!"},
            )
            assert locked.status_code == 429, locked.text
            assert locked.json()["type"].endswith("/account_locked")

            # still locked even with the correct password
            again = client.post(
                "/api/v1/auth/login",
                json={"contact": contact, "password": "s3cure-pass!"},
            )
            assert again.status_code == 429

            # throttle reset path (what happens on successful login elsewhere)
            from tk_api.auth.service import _login_identifier_key

            asyncio.run(client.app.state.login_throttle.reset(_login_identifier_key(contact)))
            ok = client.post(
                "/api/v1/auth/login",
                json={"contact": contact, "password": "s3cure-pass!"},
            )
            assert ok.status_code == 200, ok.text

    def test_lock_expires_after_backoff(self) -> None:
        with _mfa_app(
            login_max_failures=2,
            login_backoff_base_seconds=1,
            login_backoff_max_seconds=1,
        ) as client:
            sender = client._recording_sender  # type: ignore[attr-defined]
            phone = _fresh_phone()
            _register_and_verify(client, sender, phone)
            contact = "+91" + phone

            for _ in range(2):
                assert (
                    client.post(
                        "/api/v1/auth/login",
                        json={"contact": contact, "password": "wrong"},
                    ).status_code
                    == 401
                )
            assert (
                client.post(
                    "/api/v1/auth/login",
                    json={"contact": contact, "password": "wrong"},
                ).status_code
                == 429
            )
            time.sleep(1.3)
            ok = client.post(
                "/api/v1/auth/login",
                json={"contact": contact, "password": "s3cure-pass!"},
            )
            assert ok.status_code == 200, ok.text

    def test_unknown_account_probing_also_backs_off(self) -> None:
        with _mfa_app(login_max_failures=2) as client:
            contact = "+919999999999"  # not registered
            for _ in range(2):
                assert (
                    client.post(
                        "/api/v1/auth/login",
                        json={"contact": contact, "password": "nope"},
                    ).status_code
                    == 401
                )
            assert (
                client.post(
                    "/api/v1/auth/login",
                    json={"contact": contact, "password": "nope"},
                ).status_code
                == 429
            )
