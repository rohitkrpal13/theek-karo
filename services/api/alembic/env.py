"""Alembic async environment for Theek Karo API.

Database URL is sourced from tk_api.core.config.Settings so migrations and the
application always agree on the target.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from tk_api.core import models  # noqa: F401  (register all ORM models with metadata)
from tk_api.core.config import get_settings
from tk_api.core.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

database_url = get_settings().database_url


def run_migrations_offline() -> None:
    import sqlalchemy as _sa  # noqa: WPS433
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        version_table_column_type=_sa.String(length=128),
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    import sqlalchemy as _sa  # noqa: WPS433
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, version_table_column_type=_sa.String(length=128))
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
