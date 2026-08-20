"""Phase 10 ops tests: /metrics exposition, SLO label discipline, security headers."""

from __future__ import annotations

from tk_api.core.metrics import route_group

_EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "deny",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(self)",
}


class TestRouteGroups:
    def test_label_cardinality_is_bounded(self) -> None:
        assert route_group("/healthz") == "ops"
        assert route_group("/readyz") == "ops"
        assert route_group("/metrics") == "ops"
        assert route_group("/api/v1/reports/abc/timeline") == "reports"
        assert route_group("/api/v1/civic/categories") == "civic"
        assert route_group("/api/v1/auth/register") == "auth"
        assert route_group("/api/v1/gis/proximity") == "gis"
        assert route_group("/api/v1/media/uploads/x/complete") == "media"
        assert route_group("/api/v1/ai/human-review-queue") == "ai"
        assert route_group("/api/v1/notifications/preferences") == "notifications"
        assert route_group("/api/v1/measurement/overview") == "measurement"
        assert route_group("/api/v1/users/me") == "users"
        assert route_group("/something/else") == "other"


class TestMetricsEndpoint:
    def test_exposition_after_traffic(self, client) -> None:  # type: ignore[no-untyped-def]
        # generate traffic
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/v1/civic/categories").status_code == 200
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        body = response.text
        assert "tk_api_requests_total" in body
        assert "tk_api_request_duration_seconds_bucket" in body
        assert 'route_group="ops"' in body
        assert 'route_group="civic"' in body


class TestSecurityHeaders:
    def test_baseline_headers_present(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/api/v1/version")
        for name, value in _EXPECTED_HEADERS.items():
            assert response.headers.get(name).lower() == value, name
