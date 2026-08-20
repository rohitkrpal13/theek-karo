"""Civic engine router: configurable categories and campaigns (API.md §4, ADR-003)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.api.deps import get_db, get_optional_user, require_roles
from tk_api.civic import service as civic_service
from tk_api.civic.schemas import CampaignCreate, CampaignUpdate, CategoryCreate, CategoryUpdate
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.users.models import User

civic_router = APIRouter(prefix="/api/v1/civic", tags=["civic"])

admin_only = require_roles("admin")

DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[User, Depends(admin_only)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


@civic_router.get("/categories", summary="List categories (active by default)")
async def list_categories(
    session: DbSession,
    include_inactive: bool = False,
    viewer: OptionalUser = None,
) -> dict[str, Any]:
    if include_inactive and (viewer is None or not viewer.has_role("admin")):
        raise ApiError("include_inactive requires admin", 403, "forbidden")
    return await civic_service.list_categories(session, include_inactive=include_inactive)


@civic_router.get("/categories/{slug}", summary="Category detail + verification policy")
async def get_category(
    slug: str,
    session: DbSession,
    viewer: OptionalUser = None,
) -> dict[str, Any]:
    include_inactive = viewer is not None and viewer.has_role("admin")
    return await civic_service.get_category(session, slug, include_inactive=include_inactive)


@civic_router.get("/campaigns", summary="List campaigns by status / boundary")
async def list_campaigns(
    session: DbSession,
    status: str | None = None,
    boundary_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    boundary_uuid = (
        _parse_id(boundary_id, kind="boundary", error_kind="invalid_boundary_id")
        if boundary_id is not None
        else None
    )
    return await civic_service.list_campaigns(
        session, status=status, boundary_id=boundary_uuid, cursor=cursor, limit=limit
    )


@civic_router.get("/campaigns/{campaign_id}", summary="Campaign detail")
async def get_campaign(
    campaign_id: str,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(campaign_id, kind="campaign", error_kind="invalid_campaign_id")
    return await civic_service.get_campaign(session, parsed)


@civic_router.post("/categories", status_code=201, summary="Create category (admin)")
async def create_category(
    body: CategoryCreate,
    request: Request,
    actor: AdminUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="civic", key=f"write:{client_ip(request)}", limit=30, window_seconds=60
    )
    return await civic_service.create_category(
        session,
        slug=body.slug,
        icon=body.icon,
        form_schema=body.form_schema,
        verification_policy=body.verification_policy,
        attachment_rules=body.attachment_rules,
        default_locale_keys=body.default_locale_keys,
        actor_id=actor.id,
        request=request,
    )


@civic_router.patch("/categories/{category_id}", summary="Update category (admin, versioned)")
async def update_category(
    category_id: str,
    body: CategoryUpdate,
    request: Request,
    actor: AdminUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="civic", key=f"write:{client_ip(request)}", limit=30, window_seconds=60
    )
    parsed = _parse_id(category_id, kind="category", error_kind="invalid_category_id")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise ApiError("no fields to update", 422, "empty_update")
    return await civic_service.update_category(
        session, parsed, changes=changes, actor_id=actor.id, request=request
    )


@civic_router.post("/campaigns", status_code=201, summary="Create campaign (admin)")
async def create_campaign(
    body: CampaignCreate,
    request: Request,
    actor: AdminUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="civic", key=f"write:{client_ip(request)}", limit=30, window_seconds=60
    )
    return await civic_service.create_campaign(
        session,
        category_id=body.category_id,
        slug=body.slug,
        title_key=body.title_key,
        scope=body.scope,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        actor_id=actor.id,
        request=request,
    )


@civic_router.patch(
    "/campaigns/{campaign_id}", summary="Update campaign (admin: pause/close/rescope)"
)
async def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    request: Request,
    actor: AdminUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="civic", key=f"write:{client_ip(request)}", limit=30, window_seconds=60
    )
    parsed = _parse_id(campaign_id, kind="campaign", error_kind="invalid_campaign_id")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise ApiError("no fields to update", 422, "empty_update")
    return await civic_service.update_campaign(
        session, parsed, changes=changes, actor_id=actor.id, request=request
    )


@civic_router.get(
    "/categories/{id_or_slug}/detail", summary="Category detail with issue types & translations"
)
async def get_category_detail(
    id_or_slug: str,
    session: DbSession,
) -> dict[str, Any]:
    return await civic_service.get_category_detail(session, id_or_slug)


@civic_router.get("/issue-types", summary="List issue types (active)")
async def list_issue_types(
    session: DbSession,
    category_id: Annotated[uuid.UUID | None, Query(description="Filter by category ID")] = None,
    category_slug: Annotated[str | None, Query(description="Filter by category slug")] = None,
) -> list[dict[str, Any]]:
    return await civic_service.list_issue_types(
        session, category_id=category_id, category_slug=category_slug
    )


@civic_router.get("/issue-types/{issue_type_id}", summary="Get issue type by ID")
async def get_issue_type(
    issue_type_id: uuid.UUID,
    session: DbSession,
) -> dict[str, Any]:
    return await civic_service.get_issue_type(session, issue_type_id)


@civic_router.post("/issue-types", status_code=201, summary="Create issue type (admin)")
async def create_issue_type(
    body: dict[str, Any],
    request: Request,
    actor: AdminUser,
    session: DbSession,
) -> dict[str, Any]:
    category_id = _parse_id(
        str(body.get("category_id")), kind="category", error_kind="invalid_category_id"
    )
    slug = str(body.get("slug", ""))
    name = str(body.get("name", ""))
    description = body.get("description")
    form_schema = body.get("form_schema")
    return await civic_service.create_issue_type(
        session,
        category_id=category_id,
        slug=slug,
        name=name,
        description=description,
        form_schema=form_schema,
        actor_id=actor.id,
        request=request,
    )
