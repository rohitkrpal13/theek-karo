"""Snapshot generator for the OpenAPI contract (see test_openapi_snapshot.py)."""

import json
import sys
from pathlib import Path

from tk_api.core.config import Settings
from tk_api.main import create_app

SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "contracts" / "openapi.snapshot.json"
)


def main() -> None:
    app = create_app(
        settings=Settings(
            _env_file=None,
            env="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://tk:tk@127.0.0.1:59999/x",
        )
    )
    schema = app.openapi()
    SNAPSHOT_PATH.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote {SNAPSHOT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
