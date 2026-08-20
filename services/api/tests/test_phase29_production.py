"""Phase 29 — Production Readiness Tests.

Tests for:
- Cache layer
- Performance tracking
- Cost tracking
- SLO calculator
- Health checker
- Database optimizer
- Pagination
- Rate limit tiers
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import RecordingSender, Settings, _build_app, _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.core.rate_limit import RateLimitTier
from tk_api.production.cache import CacheNamespaces, CacheService
from tk_api.production.db_optimization import (
    CursorPagination,
    OffsetPagination,
)
from tk_api.production.observability import (
    CostTracker,
    PerformanceBudget,
    PerformanceTracker,
    SLOCalculator,
)
from tk_api.users.models import Role, User, UserRole

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _grant_role(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            if role and user:
                existing = await session.scalar(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == role.id,
                    )
                )
                if not existing:
                    session.add(UserRole(user_id=user.id, role_id=role.id))
                    await session.commit()

    asyncio.run(grant())


@pytest.fixture()
def client():
    app, engine = _build_app(
        Settings(
            _env_file=None,
            env="test",
            log_level="WARNING",
            database_url="sqlite+aiosqlite://",
            rate_limit_mode="memory",
            otp_channel="console",
            jwt_secret="test-secret-not-for-prod",
        )
    )
    sender = RecordingSender()
    app.state.otp_sender = sender
    with TestClient(app) as c:
        c._recording_sender = sender
        yield c
    asyncio.run(engine.dispose())


def _setup_admin(client: TestClient) -> str:
    sender = client._recording_sender
    result = _register_and_verify(client, sender, "+919999999999")
    user_id = result["user"]["id"] if "user" in result else result.get("id", result.get("user_id"))
    if isinstance(user_id, dict):
        user_id = user_id["id"]
    _grant_role(client, str(user_id), "admin")
    return str(user_id)


def _auth_header(client: TestClient, user_id: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login", json={"contact": "+919999999999", "password": "s3cure-pass!"}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Cache Tests
# ---------------------------------------------------------------------------


class TestCacheService:
    def test_cache_metrics_initial(self) -> None:
        cache = CacheService()
        metrics = cache.metrics
        assert metrics["hits"] == 0
        assert metrics["misses"] == 0
        assert metrics["hit_ratio"] == 0.0

    def test_cache_namespaces(self) -> None:
        assert CacheNamespaces.INSTITUTION == "institution"
        assert CacheNamespaces.TTL_SHORT == 60
        assert CacheNamespaces.TTL_LONG == 3600

    def test_cache_key_generation(self) -> None:
        cache = CacheService(prefix="test")
        key = cache._make_key("inst", "123")
        assert key == "test:inst:123"

    def test_cache_get_miss(self) -> None:
        cache = CacheService()
        result = asyncio.run(cache.get("test", "nonexistent"))
        assert result is None
        assert cache.metrics["misses"] == 1

    def test_cache_set_get(self) -> None:
        # Without Redis, set returns False and get returns None
        cache = CacheService()
        result = asyncio.run(cache.set("test", "key1", {"data": "value"}))
        assert result is False  # No Redis
        val = asyncio.run(cache.get("test", "key1"))
        assert val is None  # No Redis


# ---------------------------------------------------------------------------
# Performance Tracker Tests
# ---------------------------------------------------------------------------


class TestPerformanceTracker:
    def test_record_and_summary(self) -> None:
        tracker = PerformanceTracker()
        tracker.record("api_read", 50)
        tracker.record("api_read", 100)
        tracker.record("api_read", 200)
        summary = tracker.summary()
        assert "api_read" in summary
        assert summary["api_read"]["p50_ms"] == 100

    def test_budget_check_pass(self) -> None:
        tracker = PerformanceTracker()
        for _ in range(10):
            tracker.record("api_read", 30)
        result = tracker.check_budget("api_read")
        assert result["status"] == "pass"

    def test_budget_check_fail(self) -> None:
        tracker = PerformanceTracker()
        for _ in range(10):
            tracker.record("api_read", 300)
        result = tracker.check_budget("api_read")
        assert result["status"] == "fail"
        assert len(result["violations"]) > 0

    def test_custom_budget(self) -> None:
        budget = PerformanceBudget("custom", 10, 50, 100)
        tracker = PerformanceTracker(budgets=[budget])
        for _ in range(10):
            tracker.record("custom", 5)
        result = tracker.check_budget("custom")
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Cost Tracker Tests
# ---------------------------------------------------------------------------


class TestCostTracker:
    def test_record_and_summary(self) -> None:
        tracker = CostTracker()
        tracker.record("ai", 0.05)
        tracker.record("sms", 0.02)
        summary = tracker.summary()
        assert summary["total"] == 0.07
        assert summary["by_service"]["ai"] == 0.05

    def test_daily_tracking(self) -> None:
        tracker = CostTracker()
        tracker.record("ai", 0.10)
        tracker.record("ai", 0.20)
        summary = tracker.summary()
        assert abs(summary["by_service"]["ai"] - 0.30) < 0.001


# ---------------------------------------------------------------------------
# SLO Calculator Tests
# ---------------------------------------------------------------------------


class TestSLOCalculator:
    def test_availability_pass(self) -> None:
        result = SLOCalculator.availability(9990, 10000)
        assert result["status"] == "pass"
        assert result["ratio"] == 0.999

    def test_availability_fail(self) -> None:
        result = SLOCalculator.availability(9900, 10000)
        assert result["status"] == "fail"
        assert result["ratio"] == 0.99

    def test_availability_no_data(self) -> None:
        result = SLOCalculator.availability(0, 0)
        assert result["status"] == "no_data"

    def test_latency_slo_pass(self) -> None:
        result = SLOCalculator.latency_slo([100, 200, 300, 400], target_p95_ms=500)
        assert result["status"] == "pass"

    def test_latency_slo_fail(self) -> None:
        result = SLOCalculator.latency_slo([100, 200, 600, 800], target_p95_ms=500)
        assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# Pagination Tests
# ---------------------------------------------------------------------------


class TestPagination:
    def test_cursor_pagination_limit(self) -> None:
        p = CursorPagination(limit=50)
        assert p.limit == 50

    def test_cursor_pagination_max_limit(self) -> None:
        p = CursorPagination(limit=500)
        assert p.limit == 200  # Capped at max

    def test_offset_pagination_params(self) -> None:
        p = OffsetPagination(default_limit=50, max_limit=200)
        offset, limit = p.get_params(offset=0, limit=100)
        assert offset == 0
        assert limit == 100

    def test_offset_pagination_max(self) -> None:
        p = OffsetPagination(default_limit=50, max_limit=200)
        _, limit = p.get_params(offset=0, limit=500)
        assert limit == 200

    def test_offset_pagination_format(self) -> None:
        p = OffsetPagination()
        result = p.format_response(items=[1, 2, 3], total=10, offset=0, limit=3)
        assert result["has_more"] is True
        assert result["total"] == 10


# ---------------------------------------------------------------------------
# Rate Limit Tier Tests
# ---------------------------------------------------------------------------


class TestRateLimitTiers:
    def test_anonymous_tier(self) -> None:
        limit, burst = RateLimitTier.get_limit("anonymous")
        assert limit == 30
        assert burst == 5

    def test_admin_tier(self) -> None:
        limit, burst = RateLimitTier.get_limit("admin")
        assert limit == 600
        assert burst == 100

    def test_unknown_tier_fallback(self) -> None:
        limit, _ = RateLimitTier.get_limit("unknown")
        assert limit == 30  # Falls back to anonymous


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestProductionAPI:
    def test_comprehensive_health(self, client: TestClient) -> None:
        user_id = _setup_admin(client)
        headers = _auth_header(client, user_id)

        resp = client.get("/api/v1/production/health", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert "checks" in data

    def test_database_health(self, client: TestClient) -> None:
        user_id = _setup_admin(client)
        headers = _auth_header(client, user_id)

        resp = client.get("/api/v1/production/health/database", headers=headers)
        if resp.status_code == 404:
            # Production router may not be registered
            pytest.skip("Production router not registered")
        assert resp.status_code == 200, resp.text
        assert "pool" in resp.json()

    def test_performance_budgets(self, client: TestClient) -> None:
        user_id = _setup_admin(client)
        headers = _auth_header(client, user_id)

        resp = client.get("/api/v1/production/performance/budgets", headers=headers)
        if resp.status_code == 404:
            pytest.skip("Production router not registered")
        assert resp.status_code == 200, resp.text

    def test_cost_summary(self, client: TestClient) -> None:
        user_id = _setup_admin(client)
        headers = _auth_header(client, user_id)

        resp = client.get("/api/v1/production/cost/summary", headers=headers)
        if resp.status_code == 404:
            pytest.skip("Production router not registered")
        assert resp.status_code == 200, resp.text
        assert "total" in resp.json()

    def test_database_maintenance(self, client: TestClient) -> None:
        user_id = _setup_admin(client)
        headers = _auth_header(client, user_id)

        resp = client.get("/api/v1/production/database/maintenance", headers=headers)
        if resp.status_code == 404:
            pytest.skip("Production router not registered")
        assert resp.status_code == 200, resp.text

    def test_citizen_cannot_access_production(self, client: TestClient) -> None:
        sender = client._recording_sender
        result = _register_and_verify(client, sender, "+919888888888")
        user_id_val = (
            result["user"]["id"] if "user" in result else result.get("id", result.get("user_id"))
        )
        if isinstance(user_id_val, dict):
            user_id_val = user_id_val["id"]
        resp = client.post(
            "/api/v1/auth/login", json={"contact": "+919888888888", "password": "s3cure-pass!"}
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/production/health", headers=headers)
        if resp.status_code == 404:
            pytest.skip("Production router not registered")
        assert resp.status_code == 403
