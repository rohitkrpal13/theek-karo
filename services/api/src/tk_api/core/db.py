"""Database session management (SQLAlchemy 2.0 async + asyncpg).

ORM models live next to their modules (users/, auth/, ...) and are aggregated in
``tk_api.core.models`` so migrations see the full metadata (see alembic/env.py).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(
    database_url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_recycle: int = 1800,
) -> AsyncEngine:
    """Async engine with a health-checked, recycled pool (Step 9).

    ``pool_pre_ping`` revalidates connections before checkout and
    ``pool_recycle`` drops connections older than the Postgres/network idle
    lifetime so requests never hit a stale connection behind NAT/LB.
    """
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping_database(engine: AsyncEngine) -> None:
    """Execute ``SELECT 1``; raises on connection failure."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def get_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
