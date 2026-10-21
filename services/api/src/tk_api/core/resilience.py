"""Modern resilience primitives: timeout, retry, circuit breaker, bulkhead.

Used across AI gateway, govdata connectors, storage and notifications to keep
the platform fast and isolated (ADR-057, Step 12). Pure asyncio, zero new deps.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Simple count-based breaker: open after N failures, half-open after cooldown."""

    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    half_open_probes: int = 1

    _failures: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _probe_success: int = field(default=0, init=False)

    def can_execute(self) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if self._opened_at and (time.monotonic() - self._opened_at) >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._probe_success = 0
                return True
            return False
        # HALF_OPEN
        return True

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._probe_success += 1
            if self._probe_success >= self.half_open_probes:
                self._state = CircuitState.CLOSED
                self._failures = 0
                self._opened_at = None
        else:
            self._failures = 0

    def record_failure(self) -> None:
        self._failures += 1
        if self._state == CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    @property
    def state(self) -> CircuitState:
        # auto-transition from open to half-open when cooldown elapsed
        if (
            self._state == CircuitState.OPEN
            and self._opened_at
            and (time.monotonic() - self._opened_at) >= self.cooldown_seconds
        ):
            self._state = CircuitState.HALF_OPEN
            self._probe_success = 0
        return self._state


async def with_timeout(coro: Awaitable[T], seconds: float) -> T:
    """Run coro with a hard timeout (asyncio.wait_for)."""
    return await asyncio.wait_for(coro, timeout=seconds)


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Exponential backoff retry for idempotent async operations."""
    last: BaseException | None = None
    for i in range(attempts):
        try:
            return await fn()
        except retry_on as exc:
            last = exc
            if i == attempts - 1:
                raise
            delay = min(base_delay * (2**i), max_delay)
            # jitter 0-20%
            jitter = delay * 0.1 * (2 * (time.monotonic() % 1) - 1)
            await asyncio.sleep(max(0, delay + jitter))
    assert last is not None
    raise last


# Global registry for per-connector breakers (govdata, AI)
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(
    key: str,
    *,
    failure_threshold: int = 3,
    cooldown_seconds: float = 300.0,
) -> CircuitBreaker:
    if key not in _breakers:
        _breakers[key] = CircuitBreaker(
            failure_threshold=failure_threshold, cooldown_seconds=cooldown_seconds
        )
    return _breakers[key]


def breaker_state_all() -> dict[str, str]:
    return {k: v.state.value for k, v in _breakers.items()}
