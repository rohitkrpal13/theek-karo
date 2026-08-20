"""TOTP (RFC 6238) multi-factor authentication + challenge tokens (SECURITY.md §2).

Implementation is standard-library only (hmac/sha1 dynamic truncation, 30 s
step, 6 digits) so no third-party dependency is required. The secret is stored
base32-encoded in ``user_mfa.secret`` and never returned again after setup —
``setup_mfa`` generates a fresh secret each time it is called.

Login flow: password/OTP/OAuth success with MFA enabled returns a short-lived
``mfa_challenge_token`` (a purpose-tagged JWT) instead of access tokens; the
client exchanges it for tokens via ``POST /auth/mfa/verify`` with a valid TOTP
code. Privileged roles (see ``Settings.mfa_required_roles``) are additionally
gated at the authorization layer (``auth/authorization.py``) until MFA is
enabled, enforced in production/staging.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import jwt

from tk_api.core.config import Settings

TOTP_DIGITS = 6
TOTP_PERIOD_SECONDS = 30
TOTP_ALGORITHM = "SHA1"
_ISSUER = "Theek Karo"


def _b32decode(secret: str) -> bytes:
    """Decode base32 secret, tolerating missing padding and lowercase."""
    cleaned = secret.upper().strip().replace(" ", "")
    padded = cleaned + "=" * ((8 - len(cleaned) % 8) % 8)
    return base64.b32decode(padded)


def _hotp(secret: bytes, counter: int, digits: int = TOTP_DIGITS) -> str:
    """RFC 4226 HOTP with dynamic truncation (SHA-1)."""
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | (digest[offset + 1] << 16)
        | (digest[offset + 2] << 8)
        | digest[offset + 3]
    )
    return str(binary % (10**digits)).zfill(digits)


def generate_totp_secret() -> str:
    """Return a fresh 32-char base32 secret (160 bits of entropy)."""
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def totp_code(secret: str, at: datetime | None = None) -> str:
    """Compute the current 6-digit TOTP code (RFC 6238, SHA-1, 30 s step)."""
    now = at or datetime.now(UTC)
    counter = int(now.timestamp()) // TOTP_PERIOD_SECONDS
    return _hotp(_b32decode(secret), counter)


def verify_totp(secret: str, code: str, *, at: datetime | None = None, window: int = 1) -> bool:
    """Verify a TOTP code against the secret, allowing ``window`` steps of
    clock drift in each direction (default ±1 step = ±30 s)."""
    code = code.strip()
    if not code.isdigit() or len(code) != TOTP_DIGITS:
        return False
    now = at or datetime.now(UTC)
    counter = int(now.timestamp()) // TOTP_PERIOD_SECONDS
    decoded = _b32decode(secret)
    for offset in range(-window, window + 1):
        if hmac.compare_digest(_hotp(decoded, counter + offset), code):
            return True
    return False


def otpauth_uri(secret: str, account: str) -> str:
    """Provisioning URI for authenticator apps (otpauth://totp/...)."""
    label = quote(f"{_ISSUER}:{account}", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}"
        f"&issuer={quote(_ISSUER, safe='')}&algorithm={TOTP_ALGORITHM}"
        f"&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


# ---------------------------------------------------------------------------
# Challenge tokens (short-lived, purpose-tagged JWTs)
# ---------------------------------------------------------------------------


def create_mfa_challenge_token(user_id: uuid.UUID, settings: Settings) -> str:
    """Issue a single-purpose challenge token valid for ``mfa_challenge_ttl_seconds``.

    The token is not single-use by itself — the throttle on ``/auth/mfa/verify``
    bounds brute-force attempts; the access-token exchange happens exactly once
    and the short TTL bounds reuse.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "purpose": "mfa_challenge",
        "jti": secrets.token_hex(16),
        "iat": now,
        "exp": now + timedelta(seconds=settings.mfa_challenge_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


class MfaChallengeError(Exception):
    pass


def decode_mfa_challenge_token(token: str, settings: Settings) -> uuid.UUID:
    """Validate the challenge token and return the user id.

    Raises ``MfaChallengeError`` for expired, malformed, or wrong-purpose tokens.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "purpose"]},
        )
    except jwt.PyJWTError as exc:
        raise MfaChallengeError("invalid or expired MFA challenge") from exc
    if payload.get("purpose") != "mfa_challenge":
        raise MfaChallengeError("invalid MFA challenge purpose")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise MfaChallengeError("invalid MFA challenge subject") from exc
