from fastapi.testclient import TestClient


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-Id"]


def test_readyz_ok(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from tk_api.api.routers import health as health_module

    async def fake_ping(engine) -> None:  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(health_module, "ping_database", fake_ping)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_readyz_ok_with_test_db(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_version(client: TestClient) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["service"] == "tk-api"
