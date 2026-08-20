"""Institutions service (PRD §5, API.md §7).

Handles Institution Digital Twin CRUD, types, attributes, search, and visibility.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.errors import ConflictError, NotFoundError, ValidationError
from tk_api.core.pagination import PageParams, PageResponse
from tk_api.institutions.models import (
    Institution,
    InstitutionAttributeDefinition,
    InstitutionAttributeValue,
    InstitutionTranslation,
    InstitutionType,
)
from tk_api.institutions.schemas import (
    InstitutionAttributeValueRead,
    InstitutionCreate,
    InstitutionDetailRead,
    InstitutionRead,
    InstitutionTranslationRead,
    InstitutionTypeRead,
    InstitutionUpdate,
)


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


async def list_institution_types(session: AsyncSession) -> list[InstitutionTypeRead]:
    stmt = (
        select(InstitutionType)
        .where(InstitutionType.is_active.is_(True))
        .order_by(InstitutionType.code)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [InstitutionTypeRead.model_validate(r) for r in rows]


async def get_institution_type(session: AsyncSession, type_id: uuid.UUID) -> InstitutionType:
    it = await session.get(InstitutionType, type_id)
    if not it:
        raise NotFoundError(
            f"Institution type {type_id} not found", kind="institution_type_not_found"
        )
    return it


async def list_institutions(
    session: AsyncSession,
    *,
    type_id: uuid.UUID | None = None,
    geography_id: uuid.UUID | None = None,
    operational_status: str | None = None,
    verification_state: str | None = None,
    q: str | None = None,
    params: PageParams,
) -> PageResponse[InstitutionRead]:
    base_query = select(Institution).where(Institution.deleted_at.is_(None))
    count_query = select(func.count(Institution.id)).where(Institution.deleted_at.is_(None))

    if type_id is not None:
        base_query = base_query.where(Institution.institution_type_id == type_id)
        count_query = count_query.where(Institution.institution_type_id == type_id)
    if geography_id is not None:
        base_query = base_query.where(Institution.geography_id == geography_id)
        count_query = count_query.where(Institution.geography_id == geography_id)
    if operational_status is not None:
        base_query = base_query.where(Institution.operational_status == operational_status)
        count_query = count_query.where(Institution.operational_status == operational_status)
    if verification_state is not None:
        base_query = base_query.where(Institution.verification_state == verification_state)
        count_query = count_query.where(Institution.verification_state == verification_state)
    if q is not None and q.strip():
        norm = _normalize(q)
        base_query = base_query.where(Institution.normalized_name.ilike(f"%{norm}%"))
        count_query = count_query.where(Institution.normalized_name.ilike(f"%{norm}%"))

    total = (await session.execute(count_query)).scalar_one()
    stmt = base_query.order_by(Institution.name).offset(params.offset).limit(params.limit)
    rows = (await session.execute(stmt)).scalars().all()

    items = [InstitutionRead.model_validate(r) for r in rows]
    return PageResponse.create(items=items, total=total, params=params)


async def get_institution(session: AsyncSession, inst_id: uuid.UUID) -> Institution:
    inst = await session.get(Institution, inst_id)
    if not inst or inst.deleted_at is not None:
        raise NotFoundError(f"Institution {inst_id} not found", kind="institution_not_found")
    return inst


async def get_institution_detail(
    session: AsyncSession, inst_id: uuid.UUID
) -> InstitutionDetailRead:
    inst = await get_institution(session, inst_id)
    inst_type = await session.get(InstitutionType, inst.institution_type_id)

    # Fetch attributes
    stmt_attr = (
        select(InstitutionAttributeValue, InstitutionAttributeDefinition.code)
        .join(
            InstitutionAttributeDefinition,
            InstitutionAttributeValue.definition_id == InstitutionAttributeDefinition.id,
        )
        .where(InstitutionAttributeValue.institution_id == inst_id)
    )
    attr_results = (await session.execute(stmt_attr)).all()
    attributes: list[InstitutionAttributeValueRead] = []
    for val_row, def_code in attr_results:
        attr_item = InstitutionAttributeValueRead(
            id=val_row.id,
            definition_id=val_row.definition_id,
            code=def_code,
            string_value=val_row.string_value,
            integer_value=val_row.integer_value,
            decimal_value=float(val_row.decimal_value)
            if val_row.decimal_value is not None
            else None,
            boolean_value=val_row.boolean_value,
            date_value=val_row.date_value.isoformat() if val_row.date_value else None,
            enum_value=val_row.enum_value,
            source_id=val_row.source_id,
        )
        attributes.append(attr_item)

    # Fetch translations
    stmt_trans = select(InstitutionTranslation).where(
        InstitutionTranslation.institution_id == inst_id
    )
    trans_rows = (await session.execute(stmt_trans)).scalars().all()
    translations = [InstitutionTranslationRead.model_validate(t) for t in trans_rows]

    return InstitutionDetailRead(
        id=inst.id,
        institution_type_id=inst.institution_type_id,
        name=inst.name,
        normalized_name=inst.normalized_name,
        official_identifier=inst.official_identifier,
        address=inst.address,
        geography_id=inst.geography_id,
        contact_phone=inst.contact_phone,
        contact_email=inst.contact_email,
        website=inst.website,
        management_type=inst.management_type,
        operational_status=inst.operational_status,
        verification_state=inst.verification_state,
        created_at=inst.created_at,
        updated_at=inst.updated_at,
        type=InstitutionTypeRead.model_validate(inst_type) if inst_type else None,
        attributes=attributes,
        translations=translations,
    )


async def create_institution(
    session: AsyncSession,
    payload: InstitutionCreate,
) -> InstitutionRead:
    await get_institution_type(session, payload.institution_type_id)

    if payload.official_identifier:
        existing = await session.scalar(
            select(Institution).where(
                Institution.official_identifier == payload.official_identifier
            )
        )
        if existing:
            raise ConflictError(
                f"Institution with identifier '{payload.official_identifier}' already exists",
                kind="institution_identifier_conflict",
            )

    source_id = payload.source_id
    if source_id is None:
        # Fallback to default external source if exists
        from tk_api.provenance.models import ExternalSource

        default_source = await session.scalar(select(ExternalSource).limit(1))
        if default_source:
            source_id = default_source.id
        else:
            raise ValidationError("source_id is required for institution creation")

    norm = _normalize(payload.name)
    inst = Institution(
        institution_type_id=payload.institution_type_id,
        name=payload.name,
        normalized_name=norm,
        official_identifier=payload.official_identifier,
        address=payload.address,
        geography_id=payload.geography_id,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        website=payload.website,
        management_type=payload.management_type,
        source_id=source_id,
        source_identifier=payload.source_identifier,
        meta=payload.meta,
    )
    session.add(inst)
    await session.flush()
    return InstitutionRead.model_validate(inst)


async def update_institution(
    session: AsyncSession,
    inst_id: uuid.UUID,
    payload: InstitutionUpdate,
) -> InstitutionRead:
    inst = await get_institution(session, inst_id)

    if payload.name is not None:
        inst.name = payload.name
        inst.normalized_name = _normalize(payload.name)
    if payload.address is not None:
        inst.address = payload.address
    if payload.contact_phone is not None:
        inst.contact_phone = payload.contact_phone
    if payload.contact_email is not None:
        inst.contact_email = payload.contact_email
    if payload.website is not None:
        inst.website = payload.website
    if payload.management_type is not None:
        inst.management_type = payload.management_type
    if payload.operational_status is not None:
        inst.operational_status = payload.operational_status
    if payload.verification_state is not None:
        inst.verification_state = payload.verification_state
    if payload.meta is not None:
        inst.meta = payload.meta

    await session.flush()
    return InstitutionRead.model_validate(inst)
