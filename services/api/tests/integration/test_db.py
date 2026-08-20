"""Integration test against a real Postgres (compose).

Skipped unless TK_TEST_DATABASE_URL is set or default local dev postgres is reachable.
Run with: make up  (then)  uv run pytest -m integration
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from tk_api.core.config import Settings
from tk_api.core.db import ping_database
from tk_api.main import create_app

pytestmark = pytest.mark.integration

DEFAULT_URL = os.environ.get(
    "TK_TEST_DATABASE_URL", "postgresql+asyncpg://tk:tk_dev_password@127.0.0.1:5434/theek_karo"
)


def _database_reachable(url: str) -> bool:
    import asyncio

    async def check() -> bool:
        engine = create_async_engine(url)
        try:
            await ping_database(engine)
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _database_reachable(DEFAULT_URL), reason="compose postgres not running (make up)"
    ),
]


def test_readyz_with_real_database() -> None:
    settings = Settings(_env_file=None, env="test", log_level="WARNING", database_url=DEFAULT_URL)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}
