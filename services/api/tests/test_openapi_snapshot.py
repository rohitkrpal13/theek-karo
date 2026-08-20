"""OpenAPI contract snapshot test.

The snapshot (tests/contracts/openapi.snapshot.json) is the machine-checkable API
contract. Regenerate after intentional contract changes:
    uv run python scripts/update_openapi_snapshot.py
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tk_api.core.config import Settings
from tk_api.main import create_app

SNAPSHOT_PATH = Path(__file__).parent / "contracts" / "openapi.snapshot.json"


def _live_openapi() -> dict:
    app = create_app(
        settings=Settings(
            _env_file=None,
            env="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://tk:tk@127.0.0.1:59999/x",
        )
    )
    client = TestClient(app)
    return client.get("/openapi.json").json()


def test_openapi_matches_snapshot() -> None:
    assert SNAPSHOT_PATH.exists(), (
        "snapshot missing; run: uv run python scripts/update_openapi_snapshot.py"
    )
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    live = _live_openapi()
    assert live == snapshot, (
        "OpenAPI contract drifted from snapshot. If intentional, regenerate: "
        "uv run python scripts/update_openapi_snapshot.py"
    )


def test_health_endpoints_present_in_contract() -> None:
    live = _live_openapi()
    paths = live["paths"]
    assert "/healthz" in paths
    assert "/readyz" in paths
    assert "/api/v1/version" in paths
