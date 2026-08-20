"""Civic engine service: categories and campaigns as configuration data.

The application is category-agnostic (ADR-003); every write is an admin action,
audited, and versioned. Campaigns carry an explicit status machine
(planned → live ⇄ paused → closed; closed is terminal).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.civic.models import (
    Campaign,
    CampaignScope,
    Category,
    CategoryTranslation,
    IssueType,
)
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError, ConflictError, NotFoundError

CAMPAIGN_STATUSES = ("planned", "live", "paused", "closed")
_TERMINAL = "closed"
# source of truth for transitions; missing edges are rejected with 409
_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"live", "closed"},
    "live": {"paused", "closed"},
    "paused": {"live", "closed"},
    "closed": set(),
}


class CivicError(ApiError):
    pass


def _now_updated(entity: Any) -> None:
    entity.updated_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def _validate_slug(slug: str) -> None:
    if not slug or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in slug):
        raise CivicError(
            "slug must be lowercase letters, digits, underscores, or hyphens", 422, "invalid_slug"
        )


def _validate_form_schema(form_schema: Any) -> None:
    if not isinstance(form_schema, dict) or form_schema.get("type") != "object":
        raise CivicError(
            "form_schema must be a JSON Schema object of type 'object'", 422, "invalid_form_schema"
        )


def _validate_policy(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise CivicError(
            "verification_policy must be an object", 422, "invalid_verification_policy"
        )
    count = policy.get("min_verifications")
    if count is not None and (not isinstance(count, int) or count < 0):
        raise CivicError(
            "verification_policy.min_verifications must be a non-negative integer",
            422,
            "invalid_verification_policy",
        )


def _validate_attachments(rules: Any) -> None:
    if not isinstance(rules, dict):
        raise CivicError("attachment_rules must be an object", 422, "invalid_attachment_rules")
    max_files = rules.get("max_files")
    if max_files is not None and (not isinstance(max_files, int) or max_files < 0):
        raise CivicError(
            "attachment_rules.max_files must be a non-negative integer",
            422,
            "invalid_attachment_rules",
        )
    max_size = rules.get("max_size_mb")
    if max_size is not None and (not isinstance(max_size, (int, float)) or max_size <= 0):
        raise CivicError(
            "attachment_rules.max_size_mb must be a positive number",
            422,
            "invalid_attachment_rules",
        )
    mime = rules.get("mime")
    if mime is not None and (
        not isinstance(mime, list) or not all(isinstance(m, str) for m in mime)
    ):
        raise CivicError(
            "attachment_rules.mime must be a list of strings",
            422,
            "invalid_attachment_rules",
        )


def _validate_scope(scope: Any) -> dict[str, Any]:
    if not isinstance(scope, dict):
        raise CivicError("scope must be an object", 422, "invalid_scope")
    boundary = scope.get("boundary_id")
    if boundary is not None:
        try:
            uuid.UUID(str(boundary))
        except ValueError as exc:
            raise CivicError("scope.boundary_id must be a UUID", 422, "invalid_scope") from exc
    return scope


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------


def _category_out(category: Category) -> dict[str, Any]:
    return {
        "id": str(category.id),
        "slug": category.slug,
        "icon": category.icon,
        "form_schema": category.form_schema,
        "verification_policy": category.verification_policy,
        "attachment_rules": category.attachment_rules,
        "default_locale_keys": category.default_locale_keys,
        "form_schema_version": category.form_schema_version,
        "is_active": category.is_active,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


def _scope_out(scope: CampaignScope | None) -> dict[str, Any] | None:
    if scope is None:
        return None
    return {
        "boundary_id": str(scope.boundary_id) if scope.boundary_id else None,
        "district": scope.district,
        "state": scope.state,
    }


def _campaign_out(campaign: Campaign, scope: CampaignScope | None = None) -> dict[str, Any]:
    return {
        "id": str(campaign.id),
        "category_id": str(campaign.category_id),
        "slug": campaign.slug,
        "title_key": campaign.title_key,
        "scope": campaign.scope,
        "materialized_scope": _scope_out(scope),
        "starts_at": campaign.starts_at,
        "ends_at": campaign.ends_at,
        "status": campaign.status,
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
    }


# ---------------------------------------------------------------------------
# categories
# ---------------------------------------------------------------------------


async def list_categories(
    session: AsyncSession, *, include_inactive: bool = False
) -> dict[str, Any]:
    query = select(Category).order_by(Category.id.asc())
    if not include_inactive:
        query = query.where(Category.is_active.is_(True))
    rows = (await session.execute(query)).scalars().all()
    return {"items": [_category_out(c) for c in rows], "next_cursor": None}


async def get_category(
    session: AsyncSession, slug: str, *, include_inactive: bool = False
) -> dict[str, Any]:
    category = await session.scalar(select(Category).where(Category.slug == slug))
    if category is None or (not category.is_active and not include_inactive):
        raise CivicError("category not found", 404, "category_not_found")
    return _category_out(category)


async def create_category(
    session: AsyncSession,
    *,
    slug: str,
    icon: str,
    form_schema: dict[str, Any],
    verification_policy: dict[str, Any],
    attachment_rules: dict[str, Any],
    default_locale_keys: dict[str, Any] | None,
    actor_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    _validate_slug(slug)
    _validate_form_schema(form_schema)
    _validate_policy(verification_policy)
    _validate_attachments(attachment_rules)
    if await session.scalar(select(Category.id).where(Category.slug == slug)) is not None:
        raise CivicError(f"category '{slug}' already exists", 409, "slug_conflict")
    keys = default_locale_keys or {
        "label_key": f"category.{slug}",
        "description_key": f"category.{slug}.description",
    }
    if not isinstance(keys, dict) or not keys.get("label_key"):
        raise CivicError("default_locale_keys must include a label_key", 422, "invalid_locale_keys")
    category = Category(
        slug=slug,
        icon=icon,
        form_schema=form_schema,
        verification_policy=verification_policy,
        attachment_rules=attachment_rules,
        default_locale_keys=keys,
    )
    session.add(category)
    await session.flush()
    await audit(
        session,
        action="category.create",
        entity_type="category",
        entity_id=category.id,
        actor_id=actor_id,
        after={"slug": slug, "icon": icon, "form_schema_version": category.form_schema_version},
        request=request,
    )
    await session.commit()
    return _category_out(category)


async def update_category(
    session: AsyncSession,
    category_id: uuid.UUID,
    *,
    changes: dict[str, Any],
    actor_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    category = await session.get(Category, category_id)
    if category is None:
        raise CivicError("category not found", 404, "category_not_found")
    before = _category_out(category)

    if (slug := changes.get("slug")) is not None:
        _validate_slug(slug)
        if slug != category.slug:
            if await session.scalar(select(Category.id).where(Category.slug == slug)) is not None:
                raise CivicError(f"category '{slug}' already exists", 409, "slug_conflict")
            category.slug = slug
    if (icon := changes.get("icon")) is not None:
        category.icon = icon
    if (form_schema := changes.get("form_schema")) is not None:
        _validate_form_schema(form_schema)
        if form_schema != category.form_schema:
            category.form_schema = form_schema
            category.form_schema_version += 1
    if (policy := changes.get("verification_policy")) is not None:
        _validate_policy(policy)
        if policy != category.verification_policy:
            category.verification_policy = policy
            category.form_schema_version += 1
    if (rules := changes.get("attachment_rules")) is not None:
        _validate_attachments(rules)
        category.attachment_rules = rules
    if (keys := changes.get("default_locale_keys")) is not None:
        if not isinstance(keys, dict) or not keys.get("label_key"):
            raise CivicError(
                "default_locale_keys must include a label_key", 422, "invalid_locale_keys"
            )
        category.default_locale_keys = keys
    if (is_active := changes.get("is_active")) is not None:
        category.is_active = is_active
    _now_updated(category)
    await audit(
        session,
        action="category.update",
        entity_type="category",
        entity_id=category.id,
        actor_id=actor_id,
        before=before,
        after=_category_out(category),
        request=request,
    )
    await session.commit()
    return _category_out(category)


# ---------------------------------------------------------------------------
# campaigns
# ---------------------------------------------------------------------------


def _parse_cursor(cursor: str | None) -> uuid.UUID | None:
    if cursor is None:
        return None
    try:
        return uuid.UUID(cursor)
    except ValueError as exc:
        raise CivicError("invalid cursor", 422, "invalid_cursor") from exc


async def list_campaigns(
    session: AsyncSession,
    *,
    status: str | None,
    boundary_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    if status is not None and status not in CAMPAIGN_STATUSES:
        raise CivicError(f"invalid status: {status}", 422, "invalid_status")
    query = select(Campaign)
    if status is not None:
        query = query.where(Campaign.status == status)
    if boundary_id is not None:
        query = query.join(CampaignScope, CampaignScope.campaign_id == Campaign.id).where(
            CampaignScope.boundary_id == boundary_id
        )
    last_id = _parse_cursor(cursor)
    if last_id is not None:
        query = query.where(Campaign.id < last_id)
    query = query.order_by(Campaign.id.desc()).limit(limit + 1)
    rows = (await session.execute(query)).scalars().all()
    has_more = len(rows) > limit
    page = rows[:limit]
    return {
        "items": [_campaign_out(c) for c in page],
        "next_cursor": str(page[-1].id) if has_more else None,
    }


async def get_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> dict[str, Any]:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise CivicError("campaign not found", 404, "campaign_not_found")
    scope = await session.scalar(
        select(CampaignScope).where(CampaignScope.campaign_id == campaign.id)
    )
    return _campaign_out(campaign, scope)


async def _replace_scope(session: AsyncSession, campaign: Campaign, scope: dict[str, Any]) -> None:
    row = await session.scalar(
        select(CampaignScope).where(CampaignScope.campaign_id == campaign.id)
    )
    boundary_id = scope.get("boundary_id")
    boundary_uuid = uuid.UUID(str(boundary_id)) if boundary_id is not None else None
    district = scope.get("district")
    state = scope.get("state")
    if boundary_uuid is None and not district and not state:
        if row is not None:
            await session.delete(row)
        return
    if row is None:
        session.add(
            CampaignScope(
                campaign_id=campaign.id,
                boundary_id=boundary_uuid,
                district=district,
                state=state,
            )
        )
    else:
        row.boundary_id = boundary_uuid
        row.district = district
        row.state = state


async def create_campaign(
    session: AsyncSession,
    *,
    category_id: uuid.UUID,
    slug: str,
    title_key: str,
    scope: dict[str, Any],
    starts_at: datetime | None,
    ends_at: datetime | None,
    actor_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    _validate_slug(slug)
    normalized_scope = _validate_scope(scope)
    if await session.get(Category, category_id) is None:
        raise CivicError("category not found", 404, "category_not_found")
    if await session.scalar(select(Campaign.id).where(Campaign.slug == slug)) is not None:
        raise CivicError(f"campaign '{slug}' already exists", 409, "slug_conflict")
    campaign = Campaign(
        category_id=category_id,
        slug=slug,
        title_key=title_key,
        scope=normalized_scope,
        starts_at=starts_at,
        ends_at=ends_at,
        status="planned",
    )
    session.add(campaign)
    await session.flush()
    await _replace_scope(session, campaign, normalized_scope)
    await audit(
        session,
        action="campaign.create",
        entity_type="campaign",
        entity_id=campaign.id,
        actor_id=actor_id,
        after={"slug": slug, "category_id": str(category_id), "status": "planned"},
        request=request,
    )
    await session.commit()
    scope_row = await session.scalar(
        select(CampaignScope).where(CampaignScope.campaign_id == campaign.id)
    )
    return _campaign_out(campaign, scope_row)


async def update_campaign(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    changes: dict[str, Any],
    actor_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise CivicError("campaign not found", 404, "campaign_not_found")
    before = _campaign_out(campaign)

    is_rescope = changes.get("scope") is not None
    if campaign.status == _TERMINAL and (is_rescope or changes.get("status") is not None):
        raise CivicError("closed campaigns are immutable", 409, "campaign_closed")

    if (status := changes.get("status")) is not None:
        if status not in _TRANSITIONS[campaign.status]:
            raise CivicError(
                f"cannot transition campaign from '{campaign.status}' to '{status}'",
                409,
                "invalid_status_transition",
            )
        campaign.status = status
    if is_rescope:
        normalized_scope = _validate_scope(changes["scope"])
        campaign.scope = normalized_scope
        await _replace_scope(session, campaign, normalized_scope)
    if (slug := changes.get("slug")) is not None:
        _validate_slug(slug)
        if slug != campaign.slug:
            if await session.scalar(select(Campaign.id).where(Campaign.slug == slug)) is not None:
                raise CivicError(f"campaign '{slug}' already exists", 409, "slug_conflict")
            campaign.slug = slug
    if (title_key := changes.get("title_key")) is not None:
        campaign.title_key = title_key
    if (starts_at := changes.get("starts_at")) is not None:
        campaign.starts_at = starts_at
    if (ends_at := changes.get("ends_at")) is not None:
        campaign.ends_at = ends_at
    _now_updated(campaign)
    await audit(
        session,
        action="campaign.update",
        entity_type="campaign",
        entity_id=campaign.id,
        actor_id=actor_id,
        before=before,
        after=_campaign_out(campaign),
        request=request,
    )
    await session.commit()
    scope_row = await session.scalar(
        select(CampaignScope).where(CampaignScope.campaign_id == campaign.id)
    )
    return _campaign_out(campaign, scope_row)


# ---------------------------------------------------------------------------
# Issue Types & Category Tree (Phase 5 / Cycle 2)
# ---------------------------------------------------------------------------


async def list_issue_types(
    session: AsyncSession,
    *,
    category_id: uuid.UUID | None = None,
    category_slug: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(IssueType).where(IssueType.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(IssueType.category_id == category_id)
    elif category_slug is not None:
        cat = await session.scalar(select(Category).where(Category.slug == category_slug))
        if cat:
            stmt = stmt.where(IssueType.category_id == cat.id)
        else:
            return []
    stmt = stmt.order_by(IssueType.slug)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "category_id": r.category_id,
            "slug": r.slug,
            "name": r.name,
            "description": r.description,
            "form_schema": r.form_schema,
            "is_active": r.is_active,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


async def get_issue_type(session: AsyncSession, issue_type_id: uuid.UUID) -> dict[str, Any]:
    it = await session.get(IssueType, issue_type_id)
    if not it or not it.is_active:
        raise NotFoundError(f"Issue type {issue_type_id} not found", kind="issue_type_not_found")
    return {
        "id": it.id,
        "category_id": it.category_id,
        "slug": it.slug,
        "name": it.name,
        "description": it.description,
        "form_schema": it.form_schema,
        "is_active": it.is_active,
        "created_at": it.created_at,
        "updated_at": it.updated_at,
    }


async def create_issue_type(
    session: AsyncSession,
    *,
    category_id: uuid.UUID,
    slug: str,
    name: str,
    description: str | None = None,
    form_schema: dict[str, Any] | None = None,
    actor_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    cat = await session.get(Category, category_id)
    if not cat:
        raise NotFoundError(f"Category {category_id} not found", kind="category_not_found")
    _validate_slug(slug)
    existing = await session.scalar(
        select(IssueType).where(IssueType.category_id == category_id, IssueType.slug == slug)
    )
    if existing:
        raise ConflictError(
            f"Issue type '{slug}' already exists in category", kind="issue_type_conflict"
        )

    it = IssueType(
        category_id=category_id,
        slug=slug,
        name=name,
        description=description,
        form_schema=form_schema or {},
        is_active=True,
    )
    session.add(it)
    await session.flush()
    await audit(
        session,
        action="issue_type.create",
        entity_type="issue_type",
        entity_id=it.id,
        actor_id=actor_id,
        after={"category_id": str(category_id), "slug": slug, "name": name},
        request=request,
    )
    await session.commit()
    return await get_issue_type(session, it.id)


async def get_category_detail(session: AsyncSession, id_or_slug: str) -> dict[str, Any]:
    cat: Category | None = None
    try:
        val_uuid = uuid.UUID(id_or_slug)
        cat = await session.get(Category, val_uuid)
    except ValueError:
        cat = await session.scalar(select(Category).where(Category.slug == id_or_slug))

    if not cat or not cat.is_active:
        raise NotFoundError(f"Category '{id_or_slug}' not found", kind="category_not_found")

    # Fetch issue types
    stmt_it = select(IssueType).where(
        IssueType.category_id == cat.id, IssueType.is_active.is_(True)
    )
    issue_types = (await session.execute(stmt_it)).scalars().all()

    # Fetch translations
    stmt_tr = select(CategoryTranslation).where(CategoryTranslation.category_id == cat.id)
    translations = (await session.execute(stmt_tr)).scalars().all()

    return {
        "id": cat.id,
        "slug": cat.slug,
        "icon": cat.icon,
        "form_schema": cat.form_schema,
        "verification_policy": cat.verification_policy,
        "attachment_rules": cat.attachment_rules,
        "default_locale_keys": cat.default_locale_keys,
        "form_schema_version": cat.form_schema_version,
        "is_active": cat.is_active,
        "created_at": cat.created_at,
        "updated_at": cat.updated_at,
        "issue_types": [
            {
                "id": it.id,
                "category_id": it.category_id,
                "slug": it.slug,
                "name": it.name,
                "description": it.description,
                "form_schema": it.form_schema,
                "is_active": it.is_active,
                "created_at": it.created_at,
                "updated_at": it.updated_at,
            }
            for it in issue_types
        ],
        "translations": [
            {
                "id": tr.id,
                "category_id": tr.category_id,
                "locale": tr.locale,
                "name": tr.name,
                "description": tr.description,
                "created_at": tr.created_at,
            }
            for tr in translations
        ],
    }
