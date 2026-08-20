"""Production delivery-channel gating (ADR: no dev codes or console channels in prod).

Covers:
- ``validate_production_readiness`` rejects console OTP / console email / missing
  Twilio or SMTP credentials in prod/staging.
- The auth service never returns plaintext OTPs or verification tokens outside
  dev/test; verification links are delivered via the configured email provider.
"""

from __future__ import annotations

import asyncio
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import tk_api.core.models  # noqa: F401 - register full schema
from tk_api.auth.otp import ConsoleOtpSender, TwilioSmsSender, build_otp_sender
from tk_api.core.config import Settings
from tk_api.core.db import Base
from tk_api.main import create_app
from tk_api.notifications.providers import (
    ConsoleEmailProvider,
    SmtpEmailProvider,
    build_providers,
)

LONG_SECRET = "very-long-production-grade-jwt-secret-string-12345"
LONG_WEBHOOK = "very-long-production-grade-webhook-secret-67890"


def _prod_settings(**overrides: object) -> Settings:
    base: dict[str, object] = dict(
        _env_file=None,
        env="prod",
        log_level="WARNING",
        database_url="sqlite+aiosqlite://",
        rate_limit_mode="memory",
        jwt_secret=LONG_SECRET,
        webhook_master_secret=LONG_WEBHOOK,
        mfa_enforce_privileged=True,
        otp_channel="twilio",
        twilio_account_sid="AC-test-sid",
        twilio_auth_token="test-auth-token",
        twilio_from_number="+15005550001",
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_from="no-reply@theek-karo.example",
        app_base_url="https://app.theek-karo.example",
        oauth_mock_enabled=False,
        notification_callback_secret="prod-callback-secret-0123456789",
    )
    base.update(overrides)
    return Settings(**base)


class TestProductionReadinessValidation:
    def test_prod_rejects_console_otp(self) -> None:
        settings = _prod_settings(otp_channel="console")
        with pytest.raises(ValueError, match="TK_OTP_CHANNEL must not be 'console'"):
            settings.validate_production_readiness()

    def test_prod_twilio_requires_credentials(self) -> None:
        settings = _prod_settings(twilio_auth_token=None)
        with pytest.raises(ValueError, match="TK_TWILIO_AUTH_TOKEN"):
            settings.validate_production_readiness()

    def test_prod_rejects_console_email(self) -> None:
        settings = _prod_settings(email_provider="console")
        with pytest.raises(ValueError, match="TK_EMAIL_PROVIDER must not be 'console'"):
            settings.validate_production_readiness()

    def test_prod_smtp_requires_host_and_from(self) -> None:
        settings = _prod_settings(smtp_host=None)
        with pytest.raises(ValueError, match="TK_SMTP_HOST"):
            settings.validate_production_readiness()

    def test_valid_prod_configuration_passes(self) -> None:
        settings = _prod_settings()
        assert settings.is_production
        settings.validate_production_readiness()


class TestChannelFactories:
    def test_build_otp_sender_console_raises_in_prod(self) -> None:
        settings = _prod_settings(otp_channel="console")
        with pytest.raises(ValueError, match="TK_OTP_CHANNEL"):
            build_otp_sender(settings)

    def test_build_otp_sender_twilio(self) -> None:
        settings = _prod_settings()
        sender = build_otp_sender(settings)
        assert isinstance(sender, TwilioSmsSender)

    def test_build_otp_sender_console_outside_prod(self) -> None:
        settings = Settings(_env_file=None, env="dev", otp_channel="console")
        assert isinstance(build_otp_sender(settings), ConsoleOtpSender)

    def test_build_providers_console_for_dev(self) -> None:
        settings = Settings(_env_file=None, env="dev", email_provider="console")
        assert isinstance(build_providers(settings)["email"], ConsoleEmailProvider)

    def test_build_providers_smtp(self) -> None:
        settings = Settings(
            _env_file=None,
            env="dev",
            email_provider="smtp",
            smtp_host="smtp.example.com",
            smtp_from="no-reply@example.com",
        )
        assert isinstance(build_providers(settings)["email"], SmtpEmailProvider)

    def test_build_providers_rejects_console_in_prod(self) -> None:
        settings = _prod_settings(email_provider="console")
        with pytest.raises(ValueError, match="TK_EMAIL_PROVIDER"):
            build_providers(settings)


class RecordingEmail:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, to_contact: str, subject: str, body: str, message_id: str):
        self.sent.append(
            {"to_contact": to_contact, "subject": subject, "body": body, "message_id": message_id}
        )


class RecordingSms:
    """Mirrors ConsoleOtpSender but never logs the code."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, contact: str, code: str, *, purpose: str) -> None:
        self.sent.append((contact, code, purpose))


class TestNoDevCodesInProduction:
    @pytest.fixture
    def prod_client(self):
        from tk_api.users.models import Role

        settings = _prod_settings()
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )

        async def init_schema() -> None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                for code in ("citizen", "admin", "moderator"):
                    session.add(Role(code=code, name=code.capitalize()))
                await session.commit()

        asyncio.run(init_schema())
        app = create_app(settings=settings, engine=engine)
        app.state.otp_sender = RecordingSms()
        app.state.email_provider = RecordingEmail()
        with TestClient(app) as test_client:
            test_client._recording_email = app.state.email_provider  # type: ignore[attr-defined]
            yield (test_client, app.state.email_provider, app.state.otp_sender)
        asyncio.run(engine.dispose())

    def test_phone_register_never_returns_otp(self, prod_client) -> None:  # type: ignore[no-untyped-def]
        client, _email, sms = prod_client
        response = client.post(
            "/api/v1/auth/register",
            json={
                "contact": "+919876000001",
                "display_name": "Prod User",
                "consent": True,
                "terms_version": "2026-08-01",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "verify_pending"
        assert "dev_otp_code" not in body
        # OTP was still issued through the delivery channel (Twilio-equivalent)
        assert sms.sent and sms.sent[-1][0] == "+919876000001"

    def test_email_register_emails_token_and_never_returns_it(  # type: ignore[no-untyped-def]
        self, prod_client
    ) -> None:
        client, email, _sms = prod_client
        response = client.post(
            "/api/v1/auth/register",
            json={
                "contact": "prod@example.com",
                "display_name": "Prod Email",
                "consent": True,
                "terms_version": "2026-08-01",
                "locale": "en",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "verify_pending"
        assert "dev_verification_token" not in body

        message = email.sent[-1]
        assert message["to_contact"] == "prod@example.com"
        assert "Verify your email" in message["subject"]
        match = re.search(r"verify-email\?token=([\w-]+)", message["body"])
        assert match, "verification link must be emailed in production"

        # The emailed link is a real, consumable token on the verify endpoint
        verify = client.post(
            "/api/v1/auth/verify-email",
            json={"token": match.group(1)},
        )
        assert verify.status_code == 200
        assert verify.json()["access_token"]


class TestOAuthAndCallbackHardening:
    """Production gating for Google OAuth and provider delivery callbacks."""

    @pytest.fixture
    def prod_client(self):  # type: ignore[no-untyped-def]
        from tk_api.users.models import Role

        settings = _prod_settings()
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )

        async def init_schema() -> None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                session.add_all([Role(code=c, name=c.capitalize()) for c in ("citizen",)])
                await session.commit()

        asyncio.run(init_schema())
        app = create_app(settings=settings, engine=engine)
        app.state.otp_sender = RecordingSms()
        app.state.email_provider = RecordingEmail()
        with TestClient(app) as test_client:
            yield test_client
        asyncio.run(engine.dispose())

    def test_prod_oauth_url_rejected_when_unconfigured(self, prod_client) -> None:  # type: ignore[no-untyped-def]
        resp = prod_client.get(
            "/api/v1/auth/oauth/google/url?redirect_uri=https://app.theek-karo.example/auth/callback"
        )
        assert resp.status_code == 503
        assert resp.json()["type"].endswith("/oauth_not_configured")

    def test_prod_oauth_callback_rejected_when_unconfigured(self, prod_client) -> None:  # type: ignore[no-untyped-def]
        resp = prod_client.post(
            "/api/v1/auth/oauth/google/callback",
            json={
                "code": "any-code",
                "state": "s",
                "redirect_uri": "https://app.theek-karo.example/auth/callback",
            },
        )
        assert resp.status_code == 503
        assert resp.json()["type"].endswith("/oauth_not_configured")

    def test_prod_receipts_reject_unsigned_callbacks(self, prod_client) -> None:  # type: ignore[no-untyped-def]
        payload = {
            "notification_id": "00000000-0000-0000-0000-000000000001",
            "channel": "sms",
            "status": "delivered",
        }
        no_key = prod_client.post("/api/v1/notifications/receipts", json=payload)
        assert no_key.status_code == 403
        assert no_key.json()["type"].endswith("/invalid_callback_signature")

        wrong_key = prod_client.post(
            "/api/v1/notifications/receipts", json=payload, headers={"X-TK-Callback-Key": "nope"}
        )
        assert wrong_key.status_code == 403

    def test_prod_receipts_accept_valid_key(self, prod_client) -> None:  # type: ignore[no-untyped-def]
        payload = {
            "notification_id": "00000000-0000-0000-0000-000000000001",
            "channel": "sms",
            "status": "delivered",
        }
        resp = prod_client.post(
            "/api/v1/notifications/receipts",
            json=payload,
            headers={"X-TK-Callback-Key": "prod-callback-secret-0123456789"},
        )
        # A well-signed callback for a nonexistent notification must not 403;
        # it is ignored cleanly (delivery records only exist for real ids).
        assert resp.status_code in (200, 404, 422)
        assert "invalid_callback_signature" not in resp.json().get("type", "")


class TestOAuthAllowlist:
    def test_allowlist_accepts_configured_origins(self) -> None:
        from tk_api.auth.service import _oauth_allowed_redirect_uri, google_auth_url

        settings = Settings(_env_file=None, env="dev")
        assert _oauth_allowed_redirect_uri(settings, "http://localhost:3000/auth/callback")
        assert _oauth_allowed_redirect_uri(settings, "http://127.0.0.1:3000")
        result = google_auth_url(settings, redirect_uri="http://localhost:3000/auth/callback")
        assert "accounts.google.com" in result["url"]
        assert result["url"].startswith("https://accounts.google.com/o/oauth2/v2/auth")

    def test_allowlist_rejects_unknown_mock_redirect(self) -> None:
        from tk_api.auth.service import _oauth_allowed_redirect_uri, google_auth_url

        settings = Settings(_env_file=None, env="dev")
        assert not _oauth_allowed_redirect_uri(settings, "https://evil.example/cb")
        try:
            google_auth_url(settings, redirect_uri="https://evil.example/cb")
        except Exception as exc:
            assert getattr(exc, "status", None) == 400
            assert getattr(exc, "kind", None) == "invalid_redirect_uri"
        else:  # pragma: no cover
            raise AssertionError("google_auth_url accepted an untrusted redirect_uri")
