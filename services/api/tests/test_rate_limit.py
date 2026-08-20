"""Rate limiting tests (SECURITY.md §4): 429 problem+json with Retry-After."""


class TestRateLimits:
    def test_login_rate_limit_per_ip(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        # Per-account backoff (Phase 16) locks a single account after 5
        # failures, so exercise the per-IP limit with distinct identifiers.
        response = None
        for i in range(15):
            response = client.post(
                "/api/v1/auth/login",
                json={"contact": f"98765{i:05d}", "password": "wrong-pass"},
            )
            assert response.status_code == 401
        response = client.post(
            "/api/v1/auth/login", json={"contact": "98765123456", "password": "wrong-pass"}
        )
        assert response.status_code == 429
        body = response.json()
        assert body["title"] == "Rate limit exceeded"
        assert response.headers["Retry-After"]

    def test_otp_resend_cooldown(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        from tests.conftest import _register

        _register(client, sender, "9876543411")
        response = client.post("/api/v1/auth/resend-otp", json={"contact": "9876543411"})
        assert response.status_code == 200
        response = client.post("/api/v1/auth/resend-otp", json={"contact": "9876543411"})
        assert response.status_code == 429
        assert response.json()["type"].endswith("/rate-limit-exceeded")
