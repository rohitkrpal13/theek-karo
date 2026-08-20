"""Idempotent create endpoints (API.md §1).

``Idempotency-Key`` (UUID) headers make POST /reports and POST /media/uploads
replay-safe: a repeated request with the same key returns the first response
instead of creating a second entity. Backing stores mirror the OTP pattern
(ADR-005): Redis in live environments, in-memory for tests.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import redis.asyncio as aioredis

from tk_api.core.config import Settings

IDEMPOTENCY_TTL_SECONDS = 24 * 3600


@dataclass
class IdempotencyRecord:
    status_code: int
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> IdempotencyRecord | None: ...

    async def put(self, key: str, record: IdempotencyRecord, ttl_seconds: int) -> None: ...


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[str, tuple[IdempotencyRecord, float]] = {}

    async def get(self, key: str) -> IdempotencyRecord | None:
        entry = self._records.get(key)
        if entry is None:
            return None
        record, expires_at = entry
        if time.time() > expires_at:
            del self._records[key]
            return None
        return record

    async def put(self, key: str, record: IdempotencyRecord, ttl_seconds: int) -> None:
        self._records[key] = (record, time.time() + ttl_seconds)


class RedisIdempotencyStore:
    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    def _key(self, key: str) -> str:
        return f"tk:idem:{key}"

    async def get(self, key: str) -> IdempotencyRecord | None:
        raw = await self._client.get(self._key(key))
        if not raw:
            return None
        data = json.loads(raw)
        return IdempotencyRecord(
            status_code=int(data["status_code"]),
            payload=data["payload"],
            created_at=float(data["created_at"]),
        )

    async def put(self, key: str, record: IdempotencyRecord, ttl_seconds: int) -> None:
        raw = json.dumps(
            {
                "status_code": record.status_code,
                "payload": record.payload,
                "created_at": record.created_at,
            }
        )
        await self._client.set(self._key(key), raw, ex=ttl_seconds)


def build_idempotency_store(
    settings: Settings, redis_client: aioredis.Redis | None
) -> IdempotencyStore:
    """Redis-backed store when Redis is reachable, in-memory otherwise (ADR-005)."""
    if redis_client is not None:
        return RedisIdempotencyStore(redis_client)
    return MemoryIdempotencyStore()
