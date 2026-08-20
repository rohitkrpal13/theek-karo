"""Per-account login backoff / lockout (SECURITY.md §4, Phase 16 hardening).

Unlike the IP-scoped token-bucket rate limits in ``core/rate_limit.py``, this
module tracks failures **per account identifier** (email/phone/username or the
MFA challenge subject) so credential-stuffing against one account escalates:
after ``login_max_failures`` consecutive failures the account is locked for an
exponential backoff (``login_backoff_base_seconds * 2**excess``, capped at
``login_backoff_max_seconds``). A successful login resets the counter.

Redis-backed in dev/prod with an in-memory fallback (same degradation story as
the rate limiter). Lock state is ephemeral on purpose: a crash clears it, which
is the safe direction for availability; the audit trail in ``security_events``
(LOGIN_FAILURE) is the durable record.
"""

from __future__ import annotations

import logging
import math
import time

import redis.asyncio as aioredis

logger = logging.getLogger("tk_api.login_throttle")

_FAIL_KEY = "login_fail"
_LOCK_KEY = "login_lock"


class LoginThrottle:
    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client
        self._memory: dict[str, tuple[int, float]] = {}  # key -> (failures, window_start_ts)
        self._memory_locks: dict[str, float] = {}  # key -> locked_until_ts

    # -- memory fallback -------------------------------------------------------
    def _memory_locked_seconds(self, key: str) -> int:
        until = self._memory_locks.get(key, 0.0)
        remaining = max(math.ceil(until - time.time()), 0)
        if remaining <= 0:
            self._memory_locks.pop(key, None)
            return 0
        return remaining

    def _memory_record_failure(
        self,
        key: str,
        *,
        max_failures: int,
        backoff_base: int,
        backoff_max: int,
        window_seconds: int,
    ) -> tuple[int, int]:
        now = time.time()
        failures, window_start = self._memory.get(key, (0, now))
        if now - window_start > window_seconds:
            failures, window_start = 0, now
        failures += 1
        self._memory[key] = (failures, window_start)
        if failures >= max_failures:
            lock_seconds = min(backoff_base * (2 ** (failures - max_failures)), backoff_max)
            self._memory_locks[key] = now + lock_seconds
            return failures, lock_seconds
        return failures, 0

    def _memory_reset(self, key: str) -> None:
        self._memory.pop(key, None)
        self._memory_locks.pop(key, None)

    # -- public API ------------------------------------------------------------
    async def locked_seconds(self, key: str) -> int:
        """Seconds until the lock expires (0 when not locked)."""
        if self._redis is None:
            return self._memory_locked_seconds(key)
        try:
            ttl = await self._redis.ttl(f"{_LOCK_KEY}:{key}")
            return max(int(ttl), 0)
        except Exception:
            logger.warning("Redis unavailable; using memory login throttle state")
            self._redis = None
            return self._memory_locked_seconds(key)

    async def record_failure(
        self,
        key: str,
        *,
        max_failures: int,
        backoff_base: int,
        backoff_max: int,
        window_seconds: int,
    ) -> tuple[int, int]:
        """Record a failed attempt. Returns ``(failures, lock_seconds)`` where
        ``lock_seconds > 0`` means the account was just locked."""
        if self._redis is None:
            return self._memory_record_failure(
                key,
                max_failures=max_failures,
                backoff_base=backoff_base,
                backoff_max=backoff_max,
                window_seconds=window_seconds,
            )
        try:
            pipe = self._redis.pipeline()
            pipe.incr(f"{_FAIL_KEY}:{key}")
            pipe.expire(f"{_FAIL_KEY}:{key}", window_seconds)
            await pipe.execute()
            failures = int(await self._redis.get(f"{_FAIL_KEY}:{key}") or 0)
            if failures >= max_failures:
                lock_seconds = min(backoff_base * (2 ** (failures - max_failures)), backoff_max)
                await self._redis.set(f"{_LOCK_KEY}:{key}", "1", ex=lock_seconds)
                return failures, lock_seconds
            return failures, 0
        except Exception:
            logger.warning("Redis unavailable; using memory login throttle state")
            self._redis = None
            return self._memory_record_failure(
                key,
                max_failures=max_failures,
                backoff_base=backoff_base,
                backoff_max=backoff_max,
                window_seconds=window_seconds,
            )

    async def reset(self, key: str) -> None:
        """Clear failure + lock state (call on successful login / MFA)."""
        if self._redis is None:
            self._memory_reset(key)
            return
        try:
            await self._redis.delete(f"{_FAIL_KEY}:{key}", f"{_LOCK_KEY}:{key}")
        except Exception:
            logger.warning("Redis unavailable; using memory login throttle state")
            self._redis = None
            self._memory_reset(key)
