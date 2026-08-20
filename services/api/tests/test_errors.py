"""RFC 9457 error model tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from tk_api.core.config import Settings
from tk_api.main import create_app


class DummyPayload(BaseModel):
    name: str = Field(min_length=3)


def _app_with_endpoint() -> FastAPI:
    app = create_app(
        settings=Settings(
            _env_file=None,
            env="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://tk:tk@127.0.0.1:59999/x",
        )
    )

    @app.post("/dummy")
    async def dummy(payload: DummyPayload) -> dict[str, str]:
        return {"name": payload.name}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    @app.get("/conflict")
    async def conflict() -> None:
        from starlette.exceptions import HTTPException

        raise HTTPException(status_code=409, detail="state transition not allowed")

    return app


def test_validation_error_shape() -> None:
    client = TestClient(_app_with_endpoint())
    response = client.post("/dummy", json={"name": "x"})
    assert response.status_code == 422
    body = response.json()
    assert body["type"].endswith("/validation-error")
    assert body["title"] == "Validation error"
    assert body["status"] == 422
    assert body["instance"] == "/dummy"
    assert any(e["field"] == "name" and "reason" in e for e in body["errors"])


def test_http_exception_maps_to_problem() -> None:
    client = TestClient(_app_with_endpoint())
    response = client.get("/conflict")
    assert response.status_code == 409
    body = response.json()
    assert body["type"].endswith("/conflict")
    assert body["detail"] == "state transition not allowed"


def test_404_maps_to_problem() -> None:
    client = TestClient(_app_with_endpoint())
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    body = response.json()
    assert body["type"].endswith("/not-found")
    assert body["instance"] == "/api/v1/nonexistent"


def test_unhandled_exception_does_not_leak() -> None:
    client = TestClient(_app_with_endpoint(), raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["title"] == "Internal server error"
    assert "secret detail" not in str(body)
    assert "Traceback" not in str(body)


def test_validation_error_uses_problem_content_type() -> None:
    client = TestClient(_app_with_endpoint())
    response = client.post("/dummy", json={})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
