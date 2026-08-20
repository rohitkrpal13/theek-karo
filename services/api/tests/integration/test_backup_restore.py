"""DR restore test (Step 10, docs/DISASTER-RECOVERY.md).

Proves the backup strategy end-to-end against real Postgres (compose): create a
throwaway database, build the schema, seed a row, ``pg_dump`` it, restore into a
second throwaway database, and assert the data survived. Uses the postgres
server binaries — either a local ``pg_dump``/``psql`` on PATH or the compose
``postgres`` container via ``docker compose exec``.

Marked ``integration`` and skipped when compose postgres is not reachable.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tk_api.core.db import Base, create_session_factory, ping_database

pytestmark = pytest.mark.integration

ADMIN_URL = os.environ.get(
    "TK_TEST_DATABASE_URL",
    "postgresql+asyncpg://tk:tk_dev_password@127.0.0.1:5434/postgres",
)
REPO_ROOT = Path(__file__).resolve().parents[4]  # services/api/tests/integration → repo root


def _database_reachable(url: str) -> bool:
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
        not _database_reachable(ADMIN_URL), reason="compose postgres not running (make up)"
    ),
]


def _pg_tool(tool: str) -> list[str] | None:
    """Resolve how to run a postgres CLI tool: local binary or compose exec."""
    local = shutil.which(tool)
    if local is not None:
        return [local]
    compose_file = REPO_ROOT / "docker-compose.yml"
    if compose_file.exists() and shutil.which("docker") is not None:
        return ["docker", "compose", "-f", str(compose_file), "exec", "-T", "postgres", tool]
    return None


def _run_sql(tool: str, args: list[str], *, stdin: bytes | None = None) -> str:
    cmd = _pg_tool(tool)
    assert cmd is not None, f"{tool} not available (install postgres client or run compose)"
    env = {**os.environ, "PGPASSWORD": "tk_dev_password"}
    if cmd[0] == "docker":
        args = ["-U", "tk", *args]
    else:
        args = ["-h", "127.0.0.1", "-p", "5434", "-U", "tk", *args]
    result = subprocess.run(
        [*cmd, *args],
        input=stdin,
        capture_output=True,
        env=env,
        cwd=REPO_ROOT,
        timeout=120,
    )
    if result.returncode != 0:
        raise AssertionError(f"{tool} failed: {result.stderr.decode(errors='replace')[:1000]}")
    return result.stdout.decode(errors="replace")


def _admin_engine():
    return create_async_engine(ADMIN_URL, pool_pre_ping=True)


async def _ddl(engine, sql: str) -> None:
    # CREATE/DROP DATABASE cannot run inside a transaction block → autocommit
    conn = await engine.connect()
    try:
        autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await autocommit.execute(text(sql))
    finally:
        await conn.close()


async def _verify_restore(dst_url: str, user_id: str, event_id: str) -> None:
    """Assert the restored rows exist with the original values."""
    verify_engine = create_async_engine(dst_url)
    try:
        factory = create_session_factory(verify_engine)
        async with factory() as session:
            user = (
                await session.execute(
                    text("SELECT display_name, status FROM users WHERE id = :id"),
                    {"id": user_id},
                )
            ).one()
            assert user.display_name == "Restore Fixture"
            assert user.status == "active"
            event = (
                await session.execute(
                    text("SELECT event FROM security_events WHERE id = :id"),
                    {"id": event_id},
                )
            ).one()
            assert event.event == "LOGIN"
    finally:
        await verify_engine.dispose()


def test_backup_restore_round_trip() -> None:
    src_name = f"tk_restore_src_{uuid.uuid4().hex[:10]}"
    dst_name = f"tk_restore_dst_{uuid.uuid4().hex[:10]}"

    async def run() -> None:
        admin = _admin_engine()
        src_url = ADMIN_URL.rsplit("/", 1)[0] + f"/{src_name}"
        dst_url = ADMIN_URL.rsplit("/", 1)[0] + f"/{dst_name}"
        try:
            await _ddl(admin, f'CREATE DATABASE "{src_name}"')
            await _ddl(admin, f'CREATE DATABASE "{dst_name}"')

            # 1. Build schema + seed data in the source database
            src_engine = create_async_engine(src_url)
            try:
                async with src_engine.begin() as conn:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                    await conn.run_sync(Base.metadata.create_all)
            finally:
                await src_engine.dispose()

            user_id = uuid.uuid4()
            event_id = uuid.uuid4()
            seed_engine = create_async_engine(src_url)
            try:
                factory = create_session_factory(seed_engine)
                async with factory() as session:
                    from tk_api.identity.models import SecurityEvent
                    from tk_api.users.models import User

                    session.add(
                        User(
                            id=user_id,
                            display_name="Restore Fixture",
                            status="active",
                            phone=f"98{uuid.uuid4().hex[:8]}",
                        )
                    )
                    await session.flush()
                    session.add(
                        SecurityEvent(id=event_id, user_id=user_id, event="LOGIN", ip="10.0.0.1")
                    )
                    await session.commit()
            finally:
                await seed_engine.dispose()

            # 2. Dump the source database
            dump = _run_sql("pg_dump", ["-d", src_name])
            assert "CREATE TABLE" in dump, "dump is missing schema"
            assert "Restore Fixture" in dump, "dump is missing seeded data"

            # 3. Restore into the destination database
            _run_sql("psql", ["-d", dst_name], stdin=dump.encode())

            # 4. Verify the data survived the round trip
            await _verify_restore(dst_url, str(user_id), str(event_id))
        finally:
            await _ddl(admin, f'DROP DATABASE IF EXISTS "{src_name}" WITH (FORCE)')
            await _ddl(admin, f'DROP DATABASE IF EXISTS "{dst_name}" WITH (FORCE)')
            await admin.dispose()

    asyncio.run(run())
