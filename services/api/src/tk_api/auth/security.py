"""Password hashing (argon2id), secure token hashing, and JWT utilities.

- Passwords: argon2id via argon2-cffi (SECURITY.md §2, PRD §14).
- Tokens: Email verification, password reset, and refresh tokens stored as sha256 digests.
- JWTs: HS256 short-lived access tokens with explicit algorithm enforcement and payload validation.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from tk_api.core.config import Settings

_argon2 = PasswordHasher()
_OTP_ALPHABET = "0123456789"


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _argon2.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _argon2.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def generate_otp() -> str:
    return "".join(secrets.choice(_OTP_ALPHABET) for _ in range(6))


def hash_otp(code: str) -> tuple[str, str]:
    """Return (salt_hex, hash_hex) — hash = sha256(salt || code)."""
    salt = secrets.token_hex(16)
    return salt, hashlib.sha256((salt + code).encode()).hexdigest()


def verify_otp(code: str, salt: str, expected_hash: str) -> bool:
    actual = hashlib.sha256((salt + code).encode()).hexdigest()
    return hmac.compare_digest(actual, expected_hash)


def hash_token(raw_token: str) -> str:
    """Compute sha256 hex digest of a raw token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def new_crypto_token(length_bytes: int = 32) -> tuple[str, str]:
    """Generate a single-use cryptographically secure token and its sha256 hash.

    Returns (raw_plaintext_token, sha256_hash).
    """
    raw = secrets.token_urlsafe(length_bytes)
    return raw, hash_token(raw)


def create_access_token(
    user_id: uuid.UUID,
    roles: list[str],
    settings: Settings,
    *,
    permissions: list[str] | None = None,
    username: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "roles": roles,
        "permissions": permissions or [],
        "username": username,
        "jti": secrets.token_hex(16),
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_access_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        options={"require": ["sub", "exp"]},
    )


def new_refresh_token() -> tuple[str, str]:
    """Return (plaintext_token, sha256_hash). Plaintext is returned once to the client."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def refresh_expiry(settings: Settings) -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
