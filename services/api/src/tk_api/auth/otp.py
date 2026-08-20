"""OTP issuance: secure code generation, ephemeral storage, and delivery.

- OTPs live only in the store (Redis in prod/dev-with-redis, in-memory fallback)
  with TTL and attempt limits (SECURITY.md §2). OTP state is ephemeral by design
  (ADR-005: Redis is never a system of record; OTPs are by-nature ephemeral).
- Delivery is via an OtpSender; ``ConsoleOtpSender`` is the dev channel
  (``TK_OTP_CHANNEL=console``). SMS/email providers land in Phase 8
  (ROADMAP open question: Indian DLT-registered provider).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

import redis.asyncio as aioredis

from tk_api.auth.security import generate_otp, hash_otp, verify_otp
from tk_api.core.config import Settings
from tk_api.core.logging import log_extra

logger = logging.getLogger("tk_api.otp")


@dataclass
class OtpRecord:
    salt: str
    hash: str
    attempts: int = 0
    used: bool = False
    created_at: float = field(default_factory=time.time)


class OtpStore(Protocol):
    async def save(self, contact: str, record: OtpRecord, ttl_seconds: int) -> None: ...

    async def get(self, contact: str) -> OtpRecord | None: ...

    async def delete(self, contact: str) -> None: ...


class MemoryOtpStore:
    def __init__(self) -> None:
        self._records: dict[str, tuple[OtpRecord, float]] = {}

    async def save(self, contact: str, record: OtpRecord, ttl_seconds: int) -> None:
        self._records[contact] = (record, time.time() + ttl_seconds)

    async def get(self, contact: str) -> OtpRecord | None:
        entry = self._records.get(contact)
        if entry is None:
            return None
        record, expires_at = entry
        if time.time() > expires_at:
            del self._records[contact]
            return None
        return record

    async def delete(self, contact: str) -> None:
        self._records.pop(contact, None)


class RedisOtpStore:
    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    def _key(self, contact: str) -> str:
        return f"tk:otp:{contact}"

    async def save(self, contact: str, record: OtpRecord, ttl_seconds: int) -> None:
        await self._client.hset(
            self._key(contact),
            mapping={
                "salt": record.salt,
                "hash": record.hash,
                "attempts": record.attempts,
                "used": int(record.used),
                "created_at": record.created_at,
            },
        )
        await self._client.expire(self._key(contact), ttl_seconds)

    async def get(self, contact: str) -> OtpRecord | None:
        data = await self._client.hgetall(self._key(contact))
        if not data:
            return None
        salt = _as_bytes(data[b"salt"])
        digest = _as_bytes(data[b"hash"])
        attempts = _as_bytes(data[b"attempts"])
        used = _as_bytes(data[b"used"])
        created_at = _as_bytes(data[b"created_at"])
        return OtpRecord(
            salt=salt.decode(),
            hash=digest.decode(),
            attempts=int(attempts),
            used=bool(int(used)),
            created_at=float(created_at),
        )

    async def delete(self, contact: str) -> None:
        await self._client.delete(self._key(contact))


def _as_bytes(value: bytes | str) -> bytes:
    return value if isinstance(value, bytes) else value.encode()


class OtpSender(Protocol):
    async def send(self, contact: str, code: str, *, purpose: str) -> None: ...


class ConsoleOtpSender:
    """Dev channel: logs the code. Never enabled outside dev/test."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, contact: str, code: str, *, purpose: str) -> None:
        self.sent.append((contact, code, purpose))
        logger.info("OTP generated", **log_extra(contact=contact, purpose=purpose, otp_code=code))


class TwilioSmsSender:
    """Production SMS channel: Twilio Messages API via standard-library HTTP."""

    MESSAGES_URL = (
        "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    )

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    async def send(self, contact: str, code: str, *, purpose: str) -> None:
        await asyncio.to_thread(self._send_sync, contact, code, purpose)

    def _send_sync(self, contact: str, code: str, purpose: str) -> None:
        body = urllib.parse.urlencode(
            {"To": contact, "From": self.from_number, "Body": f"Your Theek Karo OTP is {code}"}
        ).encode()
        request = urllib.request.Request(
            self.MESSAGES_URL.format(account_sid=self.account_sid),
            data=body,
            method="POST",
        )
        credentials = base64.b64encode(
            f"{self.account_sid}:{self.auth_token}".encode()
        ).decode()
        request.add_header("Authorization", f"Basic {credentials}")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in (200, 201):
                raise OSError(f"Twilio SMS delivery failed: HTTP {response.status}")


def build_otp_sender(settings: Settings) -> OtpSender:
    """Construct the OTP delivery channel from settings (fail closed in prod)."""
    if settings.otp_channel == "twilio":
        if not (
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_from_number
        ):
            raise ValueError(
                "TK_OTP_CHANNEL=twilio requires TK_TWILIO_ACCOUNT_SID, TK_TWILIO_AUTH_TOKEN "
                "and TK_TWILIO_FROM_NUMBER."
            )
        return TwilioSmsSender(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_from_number,
        )
    if settings.is_production:
        raise ValueError(
            "In production/staging, TK_OTP_CHANNEL must not be 'console' (see config validation)."
        )
    return ConsoleOtpSender()


def mask_contact(contact: str) -> str:
    if "@" in contact:
        local, domain = contact.split("@", 1)
        return f"{local[0]}•••@{domain}"
    return contact[:3] + "•••••" + contact[-3:]


async def issue_otp(
    store: OtpStore,
    sender: OtpSender,
    settings: Settings,
    contact: str,
    *,
    purpose: str,
) -> str:
    """Generate, store (hashed), and send an OTP. Returns the plaintext code (tests/dev)."""
    code = generate_otp()
    salt, digest = hash_otp(code)
    await store.save(contact, OtpRecord(salt=salt, hash=digest), settings.otp_ttl_seconds)
    await sender.send(contact, code, purpose=purpose)
    return code


class OtpError(Exception):
    def __init__(self, message: str, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


async def consume_otp(store: OtpStore, settings: Settings, contact: str, code: str) -> None:
    """Validate and consume an OTP. Raises OtpError on any failure."""
    record = await store.get(contact)
    if record is None:
        raise OtpError("otp expired or not found", "invalid_otp")
    if record.used:
        raise OtpError("otp already used", "invalid_otp")
    if record.attempts >= settings.otp_max_attempts:
        await store.delete(contact)
        raise OtpError("too many attempts", "otp_attempts_exceeded")
    record.attempts += 1
    await store.save(contact, record, settings.otp_ttl_seconds)
    if not verify_otp(code, record.salt, record.hash):
        raise OtpError("invalid code", "invalid_otp")
    record.used = True
    record.attempts += 1
    await store.save(contact, record, settings.otp_ttl_seconds)


def build_store(settings: Settings, redis_client: aioredis.Redis | None) -> OtpStore:
    if redis_client is None:
        return MemoryOtpStore()
    return RedisOtpStore(redis_client)
