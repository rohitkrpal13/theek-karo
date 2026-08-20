"""Phase 24 — Identity AI/MCP tools.

All tools are READ_ONLY and permission-guarded. AI may help users understand
their account settings, verification status, memberships, and permissions —
but never bypasses authentication or exposes private data.

AI must NOT:
- Reveal private information (phone, email, exact location)
- Grant permissions or bypass authorization
- Make verification decisions
- Expose other users' private data
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.identity import service as identity_service
from tk_api.identity.profile_models import Organization, OrganizationMembership
from tk_api.institutions.models import Institution
from tk_api.users.models import User


async def tool_get_my_profile(
    session: AsyncSession,
    user_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get the current user's profile with verification labels."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": "Invalid user UUID format"}
    profile = await identity_service.get_or_create_profile(session, uid)
    labels = await identity_service.get_trust_labels(session, uid)
    return {
        "profile": profile,
        "trust_labels": labels.get("labels", []),
        "disclaimer": "Trust labels describe platform verification state, not personal worth.",
    }


async def tool_get_my_permissions(
    session: AsyncSession,
    user_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Explain the user's roles and permissions."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": "Invalid user UUID format"}
    user = await session.get(User, uid)
    if user is None:
        return {"error": "User not found"}
    return {
        "user_id": str(uid),
        "roles": user.role_codes(),
        "status": user.status,
        "mfa_enabled": user.mfa_enabled,
        "note": "AI can explain permissions but cannot grant or modify them.",
    }


async def tool_get_my_organizations(
    session: AsyncSession,
    user_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """List organizations the user is a member of."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": "Invalid user UUID format"}

    stmt = (
        select(OrganizationMembership, Organization)
        .join(Organization, OrganizationMembership.organization_id == Organization.id)
        .where(
            OrganizationMembership.user_id == uid,
            OrganizationMembership.status == "active",
        )
    )
    rows = (await session.execute(stmt)).all()
    return {
        "organizations": [
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "role": mem.role,
                "verification_status": org.verification_status,
            }
            for mem, org in rows
        ],
        "count": len(rows),
        "note": (
            "Organization members are not publicly exposed unless the "
            "organization chooses to show them."
        ),
    }


async def tool_get_my_contributions(
    session: AsyncSession,
    user_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get factual contribution history (not a quality score)."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": "Invalid user UUID format"}
    summary = await identity_service.get_contribution_summary(session, uid)
    return {
        **summary,
        "disclaimer": "This is a factual activity record, not a quality score or ranking.",
    }


async def tool_get_verification_status(
    session: AsyncSession,
    user_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get the verification status for a user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": "Invalid user UUID format"}
    labels = await identity_service.get_trust_labels(session, uid)
    verifs = await identity_service.list_verifications(session, user_id=uid, limit=20)
    return {
        "user_id": str(uid),
        "labels": labels.get("labels", []),
        "verifications": verifs.get("items", []),
        "note": (
            "Verification describes platform-specific claim verification, "
            "not personal trustworthiness."
        ),
    }


async def tool_get_organization_profile(
    session: AsyncSession,
    organization_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get organization public profile."""
    try:
        oid = uuid.UUID(organization_id)
    except ValueError:
        return {"error": "Invalid organization UUID format"}
    org = await session.get(Organization, oid)
    if org is None:
        return {"error": "Organization not found"}
    return {
        "id": str(org.id),
        "name": org.name,
        "description": org.description,
        "organization_type": org.organization_type,
        "verification_status": org.verification_status,
        "status": org.status,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


async def tool_get_institution_profile(
    session: AsyncSession,
    institution_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get institution public profile."""
    try:
        iid = uuid.UUID(institution_id)
    except ValueError:
        return {"error": "Invalid institution UUID format"}
    inst = await session.get(Institution, iid)
    if inst is None:
        return {"error": "Institution not found"}
    return {
        "id": str(inst.id),
        "name": inst.name,
        "address": inst.address,
        "operational_status": inst.operational_status,
        "official_identifier": inst.official_identifier,
    }
