"""Geography registry service (PRD §3, API.md §6).

Handles 12-level hierarchy navigation, parent-child traversal, translations, and search.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.errors import NotFoundError
from tk_api.core.pagination import PageParams, PageResponse
from tk_api.geography.models import Geography, GeographyTranslation, GeographyType
from tk_api.geography.schemas import (
    GeographyCreate,
    GeographyDetailRead,
    GeographyRead,
    GeographyTranslationRead,
    GeographyTypeRead,
)


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


async def list_geography_types(session: AsyncSession) -> list[GeographyTypeRead]:
    stmt = (
        select(GeographyType)
        .where(GeographyType.is_active.is_(True))
        .order_by(GeographyType.sort_order)
    )
    result = await session.execute(stmt)
    return [GeographyTypeRead.model_validate(gt) for gt in result.scalars().all()]


async def get_geography_type(session: AsyncSession, type_id: uuid.UUID) -> GeographyType:
    gt = await session.get(GeographyType, type_id)
    if not gt:
        raise NotFoundError(f"Geography type {type_id} not found", kind="geography_type_not_found")
    return gt


async def list_geographies(
    session: AsyncSession,
    *,
    type_id: uuid.UUID | None = None,
    parent_id: uuid.UUID | None = None,
    country_code: str | None = None,
    params: PageParams,
) -> PageResponse[GeographyRead]:
    base_query = select(Geography)
    count_query = select(func.count(Geography.id))

    if type_id is not None:
        base_query = base_query.where(Geography.type_id == type_id)
        count_query = count_query.where(Geography.type_id == type_id)
    if parent_id is not None:
        base_query = base_query.where(Geography.parent_id == parent_id)
        count_query = count_query.where(Geography.parent_id == parent_id)
    if country_code is not None:
        base_query = base_query.where(Geography.country_code == country_code)
        count_query = count_query.where(Geography.country_code == country_code)

    total = (await session.execute(count_query)).scalar_one()
    stmt = base_query.order_by(Geography.name).offset(params.offset).limit(params.limit)
    rows = (await session.execute(stmt)).scalars().all()

    items = [GeographyRead.model_validate(row) for row in rows]
    return PageResponse.create(items=items, total=total, params=params)


async def get_geography(session: AsyncSession, geo_id: uuid.UUID) -> Geography:
    geo = await session.get(Geography, geo_id)
    if not geo:
        raise NotFoundError(f"Geography {geo_id} not found", kind="geography_not_found")
    return geo


async def get_geography_detail(session: AsyncSession, geo_id: uuid.UUID) -> GeographyDetailRead:
    geo = await get_geography(session, geo_id)
    geo_type = await session.get(GeographyType, geo.type_id)

    parent_read: GeographyRead | None = None
    if geo.parent_id:
        parent_geo = await session.get(Geography, geo.parent_id)
        if parent_geo:
            parent_read = GeographyRead.model_validate(parent_geo)

    stmt = select(GeographyTranslation).where(GeographyTranslation.geography_id == geo_id)
    trans_rows = (await session.execute(stmt)).scalars().all()
    translations = [GeographyTranslationRead.model_validate(t) for t in trans_rows]

    return GeographyDetailRead(
        id=geo.id,
        type_id=geo.type_id,
        type_code=geo_type.code if geo_type else None,
        name=geo.name,
        normalized_name=geo.normalized_name,
        parent_id=geo.parent_id,
        country_code=geo.country_code,
        official_identifier=geo.official_identifier,
        alternate_names=geo.alternate_names,
        created_at=geo.created_at,
        updated_at=geo.updated_at,
        translations=translations,
        parent=parent_read,
    )


async def get_children(session: AsyncSession, geo_id: uuid.UUID) -> list[GeographyRead]:
    await get_geography(session, geo_id)
    stmt = select(Geography).where(Geography.parent_id == geo_id).order_by(Geography.name)
    rows = (await session.execute(stmt)).scalars().all()
    return [GeographyRead.model_validate(r) for r in rows]


async def get_ancestors(session: AsyncSession, geo_id: uuid.UUID) -> list[GeographyRead]:
    ancestors: list[GeographyRead] = []
    current_id: uuid.UUID | None = geo_id

    visited = set()
    while current_id is not None:
        if current_id in visited:
            break
        visited.add(current_id)

        geo = await session.get(Geography, current_id)
        if not geo:
            break
        if geo.id != geo_id:
            ancestors.append(GeographyRead.model_validate(geo))
        current_id = geo.parent_id

    return ancestors


async def search_geographies(
    session: AsyncSession,
    query: str,
    *,
    type_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[GeographyRead]:
    clean_q = _normalize(query)
    if not clean_q:
        return []

    stmt = select(Geography).where(Geography.normalized_name.ilike(f"%{clean_q}%"))
    if type_id is not None:
        stmt = stmt.where(Geography.type_id == type_id)

    stmt = stmt.order_by(Geography.name).limit(min(limit, 100))
    rows = (await session.execute(stmt)).scalars().all()
    return [GeographyRead.model_validate(r) for r in rows]


async def create_geography(session: AsyncSession, payload: GeographyCreate) -> GeographyRead:
    await get_geography_type(session, payload.type_id)
    if payload.parent_id is not None:
        await get_geography(session, payload.parent_id)

    norm = _normalize(payload.name)
    geo = Geography(
        type_id=payload.type_id,
        name=payload.name,
        normalized_name=norm,
        parent_id=payload.parent_id,
        country_code=payload.country_code,
        official_identifier=payload.official_identifier,
        alternate_names=payload.alternate_names,
    )
    session.add(geo)
    await session.flush()
    return GeographyRead.model_validate(geo)
