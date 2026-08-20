"""Redis-backed caching layer (Phase 29).

Provides:
- TTL-based caching with namespace isolation
- Stampede protection via request coalescing
- Invalidation patterns (key, pattern, namespace)
- Cache-aside pattern helpers
- Metrics for hit/miss tracking
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import redis.asyncio as aioredis

logger = logging.getLogger("tk_api.cache")

T = TypeVar("T")


@dataclass
class CacheMetrics:
    """Track cache performance metrics."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    sets: int = 0
    invalidations: int = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheService:
    """Redis-backed cache with stampede protection and namespace isolation.

    Namespace isolation: keys are prefixed with namespace to prevent collisions.
    Stampede protection: concurrent requests for the same key coalesce into a
    single Redis fetch using asyncio locks.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        default_ttl: int = 300,  # 5 minutes
        prefix: str = "tk:cache",
    ):
        self._redis = redis_client
        self._default_ttl = default_ttl
        self._prefix = prefix
        self._locks: dict[str, asyncio.Lock] = {}
        self._metrics = CacheMetrics()

    @property
    def metrics(self) -> dict[str, Any]:
        return {
            "hits": self._metrics.hits,
            "misses": self._metrics.misses,
            "errors": self._metrics.errors,
            "sets": self._metrics.sets,
            "invalidations": self._metrics.invalidations,
            "hit_ratio": round(self._metrics.hit_ratio, 4),
        }

    def _make_key(self, namespace: str, key: str) -> str:
        """Create a fully qualified cache key."""
        return f"{self._prefix}:{namespace}:{key}"

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for stampede protection."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get(
        self,
        namespace: str,
        key: str,
    ) -> Any | None:
        """Get a value from cache."""
        if self._redis is None:
            self._metrics.misses += 1
            return None

        full_key = self._make_key(namespace, key)
        try:
            raw = await self._redis.get(full_key)
            if raw is not None:
                self._metrics.hits += 1
                return json.loads(raw)
            self._metrics.misses += 1
            return None
        except Exception:
            self._metrics.errors += 1
            logger.debug("Cache get error for %s", full_key)
            return None

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in cache with optional TTL."""
        if self._redis is None:
            return False

        full_key = self._make_key(namespace, key)
        try:
            serialized = json.dumps(value, default=str)
            ttl_seconds = ttl or self._default_ttl
            await self._redis.set(full_key, serialized, ex=ttl_seconds)
            self._metrics.sets += 1
            return True
        except Exception:
            self._metrics.errors += 1
            logger.debug("Cache set error for %s", full_key)
            return False

    async def get_or_set(
        self,
        namespace: str,
        key: str,
        factory: Callable[..., Any],
        ttl: int | None = None,
        **factory_kwargs: Any,
    ) -> Any:
        """Cache-aside pattern: get from cache, or compute and cache.

        Uses stampede protection: concurrent requests for the same key
        coalesce into a single factory call.
        """
        # Try cache first
        cached = await self.get(namespace, key)
        if cached is not None:
            return cached

        # Stampede protection: lock per key
        lock = self._get_lock(key)
        async with lock:
            # Double-check after acquiring lock
            cached = await self.get(namespace, key)
            if cached is not None:
                return cached

            # Compute value
            if asyncio.iscoroutinefunction(factory):
                value = await factory(**factory_kwargs)
            else:
                value = factory(**factory_kwargs)

            # Cache the result
            await self.set(namespace, key, value, ttl=ttl)
            return value

    async def invalidate(
        self,
        namespace: str,
        key: str,
    ) -> bool:
        """Invalidate a specific cache key."""
        if self._redis is None:
            return False

        full_key = self._make_key(namespace, key)
        try:
            result = await self._redis.delete(full_key)
            self._metrics.invalidations += 1
            return result > 0
        except Exception:
            self._metrics.errors += 1
            return False

    async def invalidate_namespace(
        self,
        namespace: str,
    ) -> int:
        """Invalidate all keys in a namespace (uses SCAN for safety)."""
        if self._redis is None:
            return 0

        pattern = f"{self._prefix}:{namespace}:*"
        count = 0
        try:
            async for key in self._redis.scan_iter(match=pattern, count=100):
                await self._redis.delete(key)
                count += 1
                self._metrics.invalidations += 1
        except Exception:
            self._metrics.errors += 1
            logger.debug("Cache namespace invalidation error for %s", namespace)
        return count

    async def invalidate_pattern(
        self,
        pattern: str,
    ) -> int:
        """Invalidate keys matching a glob pattern."""
        if self._redis is None:
            return 0

        full_pattern = f"{self._prefix}:{pattern}"
        count = 0
        try:
            async for key in self._redis.scan_iter(match=full_pattern, count=100):
                await self._redis.delete(key)
                count += 1
                self._metrics.invalidations += 1
        except Exception:
            self._metrics.errors += 1
        return count

    async def exists(
        self,
        namespace: str,
        key: str,
    ) -> bool:
        """Check if a key exists in cache."""
        if self._redis is None:
            return False

        full_key = self._make_key(namespace, key)
        try:
            return bool(await self._redis.exists(full_key))
        except Exception:
            return False

    async def ttl(
        self,
        namespace: str,
        key: str,
    ) -> int:
        """Get remaining TTL for a key (-1 = no expiry, -2 = not found)."""
        if self._redis is None:
            return -2

        full_key = self._make_key(namespace, key)
        try:
            return int(await self._redis.ttl(full_key))
        except Exception:
            return -2


# ---------------------------------------------------------------------------
# Pre-defined cache namespaces with appropriate TTLs
# ---------------------------------------------------------------------------


class CacheNamespaces:
    """Standard cache namespaces for the application."""

    INSTITUTION = "institution"
    DEPARTMENT = "department"
    GEOGRAPHY = "geography"
    ANALYTICS = "analytics"
    REPORT = "report"
    CASE = "case"
    USER_PROFILE = "user_profile"
    PUBLIC_DATASET = "public_dataset"
    CONFIG = "config"
    SEARCH = "search"
    MAP = "map"
    SECURITY = "security"

    # TTLs in seconds
    TTL_SHORT = 60  # 1 minute
    TTL_MEDIUM = 300  # 5 minutes
    TTL_LONG = 3600  # 1 hour
    TTL_VERY_LONG = 86400  # 24 hours


# ---------------------------------------------------------------------------
# Cache decorator for service methods
# ---------------------------------------------------------------------------


def cached(
    namespace: str,
    key_template: str,
    ttl: int = CacheNamespaces.TTL_MEDIUM,
) -> Callable[..., Any]:
    """Decorator to cache service method results.

    Usage:
        @cached("institution", "details:{institution_id}", ttl=3600)
        async def get_institution(session, institution_id):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract cache service from kwargs or args
            cache = kwargs.get("cache")
            if cache is None:
                for arg in args:
                    if isinstance(arg, CacheService):
                        cache = arg
                        break
            if cache is None:
                return await func(*args, **kwargs)

            # The cache factory only accepts keyword arguments — callers that
            # pass positional args bypass the cache (cannot be keyed anyway).
            if args:
                return await func(*args, **kwargs)

            # Build cache key from template
            try:
                key = key_template.format(**kwargs)
            except (KeyError, IndexError):
                return await func(*args, **kwargs)

            return await cache.get_or_set(namespace, key, func, ttl=ttl, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
