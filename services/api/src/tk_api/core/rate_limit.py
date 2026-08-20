"""Token-bucket rate limiting (SECURITY.md §4).

Redis-backed in dev/prod with an in-memory fallback so the API remains usable when
Redis is down (documented degradation, not silent). Limits are per-bucket keys
(e.g. ``otp:{phone}``, ``auth:{ip}``). Exceeding a limit raises RateLimitError
which maps to a 429 problem+json with Retry-After (RFC 9457, API.md §2).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, ClassVar

import redis.asyncio as aioredis
from fastapi import Request
from fastapi.responses import JSONResponse

from tk_api.core.config import Settings
from tk_api.core.errors import _problem


async def try_redis(settings: Settings) -> aioredis.Redis | None:
    """Connect to Redis when configured; degrade to memory mode otherwise."""
    if settings.rate_limit_mode == "memory":
        return None
    try:
        client = aioredis.from_url(settings.redis_url)
        await client.ping()
        return client
    except Exception:
        import logging

        logging.getLogger("tk_api.rate_limit").warning(
            "Redis unavailable; falling back to memory rate limiting"
        )
        return None


class RateLimitError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after = retry_after


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


class RateLimiter:
    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client
        self._memory: dict[str, list[float]] = {}

    def _memory_hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        hits = [t for t in self._memory.get(key, []) if now - t < window_seconds]
        hits.append(now)
        self._memory[key] = hits
        if len(hits) > limit:
            retry_after = int(window_seconds - (now - hits[0])) + 1
            return RateLimitResult(False, max(limit - len(hits), 0), max(retry_after, 1))
        return RateLimitResult(True, limit - len(hits), 0)

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        if self._redis is None:
            return self._memory_hit(key, limit, window_seconds)
        try:
            pipe = self._redis.pipeline()
            pipe.set(key, 0, ex=window_seconds, nx=True)
            pipe.incr(key)
            pipe.ttl(key)
            await pipe.execute()
            current = int(await self._redis.get(key) or 0)
            ttl = int(await self._redis.ttl(key) or 0)
            if current > limit:
                return RateLimitResult(False, max(limit - current, 0), max(ttl, 1))
            return RateLimitResult(True, max(limit - current, 0), 0)
        except Exception:
            return self._memory_hit(key, limit, window_seconds)


async def rate_limit(
    request: Request,
    *,
    bucket: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    limiter: RateLimiter = request.app.state.limiter
    result = await limiter.hit(f"{bucket}:{key}", limit, window_seconds)
    request.state.rate_limit_remaining = result.remaining
    if not result.allowed:
        raise RateLimitError(result.retry_after)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Tier-based rate limits (Phase 29)
# ---------------------------------------------------------------------------


class RateLimitTier:
    """Tier-based rate limit configuration for different user types."""

    # (requests_per_minute, burst_per_second)
    TIERS: ClassVar[dict[str, tuple[int, int]]] = {
        "anonymous": (30, 5),
        "authenticated": (60, 10),
        "verified": (120, 20),
        "organization": (300, 50),
        "government": (300, 50),
        "admin": (600, 100),
    }

    @classmethod
    def get_limit(cls, tier: str) -> tuple[int, int]:
        """Get rate limit for a user tier. Returns (requests_per_minute, burst)."""
        return cls.TIERS.get(tier, cls.TIERS["anonymous"])

    @classmethod
    def get_user_tier(cls, user: Any) -> str:
        """Determine user tier from roles."""
        if user is None:
            return "anonymous"
        if hasattr(user, "has_role"):
            if user.has_role("super_admin") or user.has_role("admin"):
                return "admin"
            if user.has_role("department_manager") or user.has_role("government"):
                return "government"
            if hasattr(user, "organization_id") and user.organization_id:
                return "organization"
            if hasattr(user, "verified_contributor") or user.has_role("verified_contributor"):
                return "verified"
        return "authenticated"


def register_rate_limit_handler(app) -> None:  # type: ignore[no-untyped-def]
    async def handler(request: Request, exc: RateLimitError) -> JSONResponse:
        response = _problem(429, instance=str(request.url.path))
        response.headers["Retry-After"] = str(exc.retry_after)
        return response

    app.add_exception_handler(RateLimitError, handler)


# Re-export for mypy strict callers.
__all__ = [
    "RateLimitError",
    "RateLimitResult",
    "RateLimiter",
    "client_ip",
    "rate_limit",
    "register_rate_limit_handler",
    "try_redis",
]
