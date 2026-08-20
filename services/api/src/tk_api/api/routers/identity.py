"""Phase 24 — Identity API router.

Endpoints for user profiles, preferences, identity verification,
organization identity, institution claims, trust labels, and
contribution history.

Mounts under ``/api/v1/identity/``.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from tk_api.api.deps import CurrentUser, DbSession, OptionalUser, require_active
from tk_api.identity import service as identity_service

identity_router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@identity_router.get("/me/profile")
async def get_my_profile(
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Get the current user's full profile."""
    return await identity_service.get_or_create_profile(db, user.id)


@identity_router.patch("/me/profile")
async def update_my_profile(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Update the current user's profile."""
    return await identity_service.update_profile(db, user_id=user.id, data=body, actor_id=user.id)


@identity_router.get("/profiles/{user_id}")
async def get_public_profile(
    user_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Get a user's public profile. Respects visibility settings."""
    viewer_id = user.id if user else None
    return await identity_service.get_public_profile(db, user_id, viewer_id)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


@identity_router.get("/me/preferences")
async def get_my_preferences(
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Get the current user's preferences."""
    return await identity_service.get_preferences(db, user.id)


@identity_router.patch("/me/preferences")
async def update_my_preferences(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Update the current user's preferences."""
    return await identity_service.update_preferences(db, user_id=user.id, data=body)


# ---------------------------------------------------------------------------
# Identity Verification
# ---------------------------------------------------------------------------


@identity_router.post("/verifications", status_code=201)
async def create_verification(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Create an identity verification request."""
    return await identity_service.create_verification_request(db, user_id=user.id, data=body)


@identity_router.get("/verifications")
async def list_my_verifications(
    db: DbSession,
    user: CurrentUser,
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List the current user's verification records."""
    return await identity_service.list_verifications(
        db, user_id=user.id, status=status, limit=limit, offset=offset
    )


@identity_router.get("/verifications/{user_id}")
async def list_user_verifications(
    user_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List a user's public verification status."""
    return await identity_service.list_verifications(
        db, user_id=user_id, status=status, limit=limit, offset=offset
    )


_moderator_or_admin = Depends(require_active("admin", "moderator"))


@identity_router.patch("/verifications/{verification_id}/review")
async def review_verification(
    verification_id: uuid.UUID,
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _moderator_or_admin],
) -> dict[str, Any]:
    """Review and decide on a verification request (admin/moderator only)."""
    return await identity_service.review_verification(
        db, verification_id=verification_id, data=body, reviewer_id=user.id
    )


# ---------------------------------------------------------------------------
# Trust Labels
# ---------------------------------------------------------------------------


@identity_router.get("/trust/{user_id}")
async def get_trust_labels(
    user_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Get contextual trust labels for a user."""
    return await identity_service.get_trust_labels(db, user_id)


# ---------------------------------------------------------------------------
# Contribution Summary
# ---------------------------------------------------------------------------


@identity_router.get("/contributions/{user_id}")
async def get_contributions(
    user_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Get factual contribution history for a user."""
    return await identity_service.get_contribution_summary(db, user_id)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


@identity_router.post("/organizations", status_code=201)
async def create_organization(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Create a new organization."""
    return await identity_service.create_organization(db, owner_id=user.id, data=body)


@identity_router.get("/organizations")
async def list_organizations(
    db: DbSession,
    user: OptionalUser = None,
    organization_type: str | None = Query(None),
    geography_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List active organizations."""
    geo_id = _safe_uuid(geography_id)
    return await identity_service.list_organizations(
        db,
        org_type=organization_type,
        geography_id=geo_id,
        limit=limit,
        offset=offset,
    )


@identity_router.get("/organizations/{org_id}")
async def get_organization(
    org_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Get organization details."""
    return await identity_service.get_organization(db, org_id)


@identity_router.post("/organizations/{org_id}/invite", status_code=201)
async def invite_organization_member(
    org_id: uuid.UUID,
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Invite a user to an organization."""
    return await identity_service.invite_member(
        db, organization_id=org_id, inviter_id=user.id, data=body
    )


@identity_router.post("/organizations/invitations/{invitation_id}/accept")
async def accept_organization_invitation(
    invitation_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Accept an organization invitation."""
    return await identity_service.accept_invitation(
        db, invitation_id=invitation_id, user_id=user.id
    )


@identity_router.get("/organizations/{org_id}/members")
async def list_organization_members(
    org_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List organization members."""
    return await identity_service.list_organization_members(
        db, organization_id=org_id, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# Institution Claims
# ---------------------------------------------------------------------------


@identity_router.post("/institution-claims", status_code=201)
async def create_institution_claim(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Create an institution claim request."""
    return await identity_service.create_institution_claim(db, user_id=user.id, data=body)


@identity_router.patch("/institution-claims/{claim_id}/review")
async def review_institution_claim(
    claim_id: uuid.UUID,
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _moderator_or_admin],
) -> dict[str, Any]:
    """Review an institution claim (admin/moderator only)."""
    return await identity_service.review_institution_claim(
        db, claim_id=claim_id, data=body, reviewer_id=user.id
    )


# ---------------------------------------------------------------------------
# Representative Assignments
# ---------------------------------------------------------------------------


@identity_router.post("/representatives", status_code=201)
async def assign_representative(
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _moderator_or_admin],
) -> dict[str, Any]:
    """Assign a representative (admin/moderator only)."""
    return await identity_service.assign_representative(db, data=body, assigned_by=user.id)
