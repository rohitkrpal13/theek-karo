"""Application configuration via pydantic-settings.

All settings are read from environment variables with the ``TK_`` prefix or from a
``.env`` file in the working directory. Never commit real secrets.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Env = Literal["dev", "test", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TK_", env_file=".env", extra="ignore")

    env: Env = "dev"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://tk:tk_dev_password@127.0.0.1:5434/theek_karo"

    cors_origins: list[str] = ["http://localhost:3000"]

    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4318"

    redis_url: str = "redis://127.0.0.1:6380/0"

    # Auth (Phase 3)
    jwt_secret: str = "dev-secret-change-me"
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_days: int = 30
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 120
    password_min_length: int = 8
    terms_version: str = "2026-08-01"
    otp_channel: str = "console"  # console (dev/test) | twilio (production SMS)
    rate_limit_mode: str = "memory"

    # Delivery of auth-critical messages (OTP SMS + verification email).
    # ``console`` is the dev/test sandbox (logs instead of sending); production
    # fails closed at startup unless a real provider is configured. ``email_provider``
    # doubles for application notifications (shared below).
    app_base_url: str = "http://localhost:3000"  # base URL for verification links in emails
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True

    # MFA (TOTP) + per-account login backoff (Phase 16). ``mfa_enforce_privileged``
    # gates privileged-role authorization until MFA is enabled; it is mandatory
    # in prod/staging (validate_production_readiness).
    mfa_enforce_privileged: bool = False
    mfa_required_roles: list[str] = [
        "super_admin",
        "admin",
        "moderator",
        "department_manager",
        "reviewer",
        "official",
        "analyst",
        "department_representative",
        "institution_representative",
    ]
    mfa_challenge_ttl_seconds: int = 300
    mfa_max_attempts: int = 5
    mfa_backoff_seconds: int = 60
    login_max_failures: int = 5
    login_backoff_base_seconds: int = 60
    login_backoff_max_seconds: int = 3600
    login_failure_window_seconds: int = 300

    # Google OAuth (Phase 3). Real exchange requires both client id and secret.
    # ``oauth_mock_enabled`` permits the hermetic dev/test identity exchange
    # (used by unit/integration tests and local development); it is always
    # refused in prod/staging. ``oauth_redirect_uri_allowlist`` pins the set of
    # permitted redirect_uri values to prevent open-redirect/CSRF token theft.
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    oauth_mock_enabled: bool = True
    oauth_redirect_uri_allowlist: list[str] = [
        "http://localhost:3000",
        "http://localhost:3000/auth/callback",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3000/auth/callback",
    ]

    # Provider delivery-status callbacks (POST /notifications/receipts). The
    # sandbox keeps the endpoint open for console/SMTP providers; production
    # requires ``notification_callback_secret`` and rejects unsigned callbacks.
    notification_callback_secret: str | None = None

    # Media / object storage (Phase 5): memory (tests), local (dev API),
    # minio (compose + production-style presigned URLs).
    media_storage_mode: str = "local"
    media_local_dir: str = "media"
    media_stream_dir: str = "media-streams"
    media_minio_endpoint: str = "127.0.0.1:9000"
    media_minio_public_endpoint: str = "127.0.0.1:9000"
    media_minio_access_key: str = "tk_minio"
    media_minio_secret_key: str = "tk_minio_password"
    media_minio_bucket: str = "tk-media"
    media_minio_region: str = "us-east-1"
    media_minio_secure: bool = False

    # Connection pool (Step 9): pre_ping + recycle avoid stale connections
    # behind NAT/LB; size tuned for the Fargate API (5 → 10 + 20 overflow).
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800
    media_exports_bucket: str = "tk-exports"
    media_max_size_mb: int = 8
    media_allowed_mime: list[str] = ["image/jpeg", "image/png", "image/webp"]

    # AI gateway (Phase 6, ADR-017/030): OpenAI-compatible chat endpoint with a
    # fallback chain. Without an API key the provider falls back to the
    # deterministic StubGateway (dev/tests, eval harness).
    ai_gateway_urls: list[str] = ["https://api.deepseek.com/v1"]
    ai_api_key: str | None = None
    ai_model: str = "deepseek-chat"
    ai_embed_model: str = "embedding-model"
    ai_timeout_seconds: float = 30.0
    ai_auto_analysis: bool = False
    # Cost control (Step 12): hard daily cap on assistant chats per user/IP;
    # the per-minute rate limits bound bursts, this bounds daily spend.
    ai_daily_chat_limit: int = 300
    ai_dedup_similarity_threshold: float = 0.6
    ai_dedup_min_report_age_days: int = 90

    # Async + notifications (Phase 8): Celery on the compose Redis broker;
    # the API falls back to in-process jobs when the worker is not enabled.
    celery_broker_url: str = "redis://127.0.0.1:6380/1"
    celery_enabled: bool = False
    notification_channels: list[str] = ["in_app", "sms", "email"]
    quiet_hours_default: dict[str, str] = {"start": "21:00", "end": "07:00", "tz": "Asia/Kolkata"}
    sms_provider: str = "console"  # console sandbox; DLT-registered provider = open question
    email_provider: str = "console"
    notification_max_attempts: int = 3
    notification_backoff_seconds: int = 300

    # Phase 15 community confirmation (PRD §B.2): thresholds for the
    # two-confirmer gate and the "issue still exists" reopen signal. Signals
    # are review triggers — they never auto-close or auto-reopen a case.
    resolution_confirm_threshold: int = 2
    resolution_reopen_threshold: int = 3

    # Phase 19 integrations (ADR-057): connector circuit breaker + webhook
    # delivery. ``webhook_master_secret`` seeds per-subscription HMAC keys
    # (secret_key_id + master secret); it is a dev default only — production
    # must set TK_WEBHOOK_MASTER_SECRET and the readiness check enforces it.
    connector_failure_threshold: int = 3
    connector_cooldown_seconds: int = 300
    connector_freshness_grace_hours: int = 48
    webhook_master_secret: str = "dev-webhook-secret-change-me"
    webhook_max_attempts: int = 5
    webhook_base_delay_seconds: int = 30
    webhook_timeout_seconds: float = 10.0
    webhook_max_body_bytes: int = 1 * 1024 * 1024  # 1 MB
    integrations_default_sync_hours: int = 24

    # API configuration
    api_v1_prefix: str = "/api/v1"
    max_request_body_bytes: int = 10 * 1024 * 1024  # 10 MB

    @property
    def is_test(self) -> bool:
        return self.env == "test"

    @property
    def is_production(self) -> bool:
        return self.env in ("prod", "staging")

    def validate_production_readiness(self) -> None:
        """Fail fast if critical production secrets are insecure or using dev defaults."""
        if self.is_production:
            if (
                self.jwt_secret in ("dev-secret-change-me", "", "change-me")
                or len(self.jwt_secret) < 32
            ):
                raise ValueError(
                    "In production/staging, TK_JWT_SECRET must be at least 32 characters "
                    "and not default."
                )
            if "tk_dev_password" in self.database_url:
                raise ValueError(
                    "In production/staging, TK_DATABASE_URL must not contain default dev passwords."
                )
            if not self.mfa_enforce_privileged:
                raise ValueError(
                    "In production/staging, TK_MFA_ENFORCE_PRIVILEGED must be true "
                    "(privileged roles require TOTP)."
                )
            if self.webhook_master_secret in ("dev-webhook-secret-change-me", "", "change-me"):
                raise ValueError(
                    "In production/staging, TK_WEBHOOK_MASTER_SECRET must not be the dev default."
                )
            if self.otp_channel == "console":
                raise ValueError(
                    "In production/staging, TK_OTP_CHANNEL must not be 'console'; "
                    "configure TK_OTP_CHANNEL=twilio with TK_TWILIO_ACCOUNT_SID, "
                    "TK_TWILIO_AUTH_TOKEN and TK_TWILIO_FROM_NUMBER."
                )
            if self.email_provider == "console":
                raise ValueError(
                    "In production/staging, TK_EMAIL_PROVIDER must not be 'console'; "
                    "configure TK_EMAIL_PROVIDER=smtp with TK_SMTP_HOST, TK_SMTP_FROM "
                    "(and TK_SMTP_USER/TK_SMTP_PASSWORD for authenticated relays)."
                )
            if self.otp_channel == "twilio" and not (
                self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number
            ):
                raise ValueError(
                    "In production/staging, TK_OTP_CHANNEL=twilio requires "
                    "TK_TWILIO_ACCOUNT_SID, TK_TWILIO_AUTH_TOKEN and TK_TWILIO_FROM_NUMBER."
                )
            if self.email_provider == "smtp" and not (self.smtp_host and self.smtp_from):
                raise ValueError(
                    "In production/staging, TK_EMAIL_PROVIDER=smtp requires "
                    "TK_SMTP_HOST and TK_SMTP_FROM."
                )
            if self.google_oauth_client_id and not self.google_oauth_client_secret:
                raise ValueError(
                    "In production/staging, TK_GOOGLE_OAUTH_CLIENT_ID requires "
                    "TK_GOOGLE_OAUTH_CLIENT_SECRET."
                )
            if self.oauth_mock_enabled:
                raise ValueError(
                    "In production/staging, TK_OAUTH_MOCK_ENABLED must be false "
                    "(mock identity exchange is a dev/test-only capability)."
                )
            if not self.notification_callback_secret:
                raise ValueError(
                    "In production/staging, TK_NOTIFICATION_CALLBACK_SECRET must be set "
                    "to authenticate provider delivery-status callbacks."
                )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_readiness()
    return settings


def clear_settings_cache() -> None:
    """Clear the cached settings (used by tests)."""
    get_settings.cache_clear()
