"""Settings behavior tests."""

import pytest

from tk_api.core.config import Settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.env == "dev"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.otel_enabled is False


def test_env_prefix_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TK_ENV", "prod")
    monkeypatch.setenv("TK_DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    monkeypatch.setenv("TK_CORS_ORIGINS", '["https://app.theekkar.in"]')
    settings = Settings(_env_file=None)
    assert settings.env == "prod"
    assert settings.database_url == "postgresql+asyncpg://u:p@db:5432/x"
    assert settings.cors_origins == ["https://app.theekkar.in"]


def test_invalid_env_rejected() -> None:
    import os

    from pydantic import ValidationError

    os.environ["TK_ENV"] = "nope"
    try:
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
    finally:
        del os.environ["TK_ENV"]


def test_custom_prefix_not_leaked(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "sekret")
    settings = Settings(_env_file=None)
    assert getattr(settings, "POSTGRES_PASSWORD", None) is None
