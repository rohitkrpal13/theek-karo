"""Phase 24 — Identity service layer.

Implements: user profiles, preferences, privacy, identity verification,
organization identity, institution claims, trust labels, and contribution
history. All operations enforce authorization and audit every sensitive action.

Design principles:
- Trust is contextual, never a hidden global score
- No citizen ranking or political profiling
- Verification describes platform-specific claim verification
- Private information remains private
- Append-only audit for all identity changes
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.identity.profile_models import (
    AccountStatusHistory,
    IdentityVerification,
    InstitutionClaim,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    RepresentativeAssignment,
    UserPreferences,
    UserProfile,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def _require_uuid(value: str | None, field_name: str) -> uuid.UUID:
    result = _safe_uuid(value)
    if result is None:
        raise ApiError(f"{field_name} is required", 422, f"missing_{field_name}")
    return result


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------


async def get_or_create_profile(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Get or create a user profile."""
    profile = await session.get(UserProfile, user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.flush()
    return _profile_to_dict(profile)


async def update_profile(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Update user profile fields."""
    profile = await session.get(UserProfile, user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        session.add(profile)

    # Only allow updating specific fields
    allowed_fields = {
        "display_name",
        "bio",
        "profile_image_url",
        "civic_interests",
        "profile_visibility",
        "contact_visibility",
        "contribution_visibility",
        "location_visibility",
    }
    for field in allowed_fields:
        if field in data:
            setattr(profile, field, data[field])

    profile.updated_at = _utcnow()
    await session.flush()

    await audit(
        session,
        action="identity.profile_update",
        entity_type="user_profiles",
        entity_id=user_id,
        actor_id=actor_id or user_id,
    )

    return _profile_to_dict(profile)


async def get_public_profile(
    session: AsyncSession,
    user_id: uuid.UUID,
    viewer_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Get a public-safe profile. Respects visibility settings."""
    profile = await session.get(UserProfile, user_id)
    if profile is None:
        raise ApiError("profile not found", 404, "profile_not_found")

    # Check visibility
    is_own = viewer_id == user_id
    if not is_own and profile.profile_visibility == "PRIVATE":
        raise ApiError("profile is private", 404, "profile_not_found")

    result = _profile_to_dict(profile)

    # Strip private fields for non-owners
    if not is_own:
        result.pop("contact_visibility", None)
        result.pop("location_visibility", None)

    return result


def _profile_to_dict(p: UserProfile) -> dict[str, Any]:
    return {
        "user_id": str(p.user_id),
        "display_name": p.display_name,
        "bio": p.bio,
        "profile_image_url": p.profile_image_url,
        "civic_interests": p.civic_interests,
        "profile_visibility": p.profile_visibility,
        "contact_visibility": p.contact_visibility,
        "contribution_visibility": p.contribution_visibility,
        "location_visibility": p.location_visibility,
        "public_report_count": p.public_report_count,
        "public_initiative_count": p.public_initiative_count,
        "public_evidence_count": p.public_evidence_count,
        "identity_verified": p.identity_verified,
        "organization_verified": p.organization_verified,
        "official_representative": p.official_representative,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ---------------------------------------------------------------------------
# User Preferences
# ---------------------------------------------------------------------------


async def get_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Get user preferences."""
    prefs = await session.get(UserPreferences, user_id)
    if prefs is None:
        return {
            "user_id": str(user_id),
            "language": "hi",
            "timezone": "Asia/Kolkata",
            "notification_preferences": {},
            "accessibility_settings": {},
            "content_preferences": {},
            "map_preferences": {},
            "ai_processing_consent": True,
        }
    return _prefs_to_dict(prefs)


async def update_preferences(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Update user preferences."""
    prefs = await session.get(UserPreferences, user_id)
    if prefs is None:
        prefs = UserPreferences(user_id=user_id)
        session.add(prefs)

    allowed_fields = {
        "language",
        "timezone",
        "notification_preferences",
        "accessibility_settings",
        "content_preferences",
        "map_preferences",
        "ai_processing_consent",
    }
    for field in allowed_fields:
        if field in data:
            setattr(prefs, field, data[field])

    prefs.updated_at = _utcnow()
    await session.flush()
    return _prefs_to_dict(prefs)


def _prefs_to_dict(p: UserPreferences) -> dict[str, Any]:
    return {
        "user_id": str(p.user_id),
        "language": p.language,
        "timezone": p.timezone,
        "notification_preferences": p.notification_preferences,
        "accessibility_settings": p.accessibility_settings,
        "content_preferences": p.content_preferences,
        "map_preferences": p.map_preferences,
        "ai_processing_consent": p.ai_processing_consent,
    }


# ---------------------------------------------------------------------------
# Identity Verification
# ---------------------------------------------------------------------------

VALID_VERIFICATION_TYPES = {
    "EMAIL_VERIFIED",
    "PHONE_VERIFIED",
    "IDENTITY_VERIFIED",
    "ORGANIZATION_VERIFIED",
    "INSTITUTION_REP_VERIFIED",
    "OFFICIAL_REP_VERIFIED",
    "SKILL_VERIFIED",
}


async def create_verification_request(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
    request: Any = None,
) -> dict[str, Any]:
    """Create a new identity verification request."""
    vtype = data.get("verification_type", "")
    if vtype not in VALID_VERIFICATION_TYPES:
        raise ApiError("invalid verification_type", 422, "invalid_verification_type")

    target_type = data.get("target_type", "user")
    target_id = _require_uuid(data.get("target_id"), "target_id")

    verification = IdentityVerification(
        user_id=user_id,
        verification_type=vtype,
        target_type=target_type,
        target_id=target_id,
        status="PENDING",
        evidence_refs=data.get("evidence_refs", []),
        documentation_url=data.get("documentation_url"),
        meta=data.get("meta"),
    )
    session.add(verification)
    await session.flush()

    await audit(
        session,
        action="identity.verification_request",
        entity_type="identity_verifications",
        entity_id=verification.id,
        actor_id=user_id,
    )

    return _verification_to_dict(verification)


async def review_verification(
    session: AsyncSession,
    *,
    verification_id: uuid.UUID,
    data: dict[str, Any],
    reviewer_id: uuid.UUID,
    request: Any = None,
) -> dict[str, Any]:
    """Review and decide on a verification request."""
    verification = await session.get(IdentityVerification, verification_id)
    if verification is None:
        raise ApiError("verification not found", 404, "verification_not_found")

    decision = data.get("status", "")
    valid_decisions = {"VERIFIED", "REJECTED", "UNDER_REVIEW", "MORE_INFORMATION", "SUSPENDED"}
    if decision not in valid_decisions:
        raise ApiError("invalid decision", 422, "invalid_decision")

    verification.status = decision
    verification.reviewer_id = reviewer_id
    verification.review_method = data.get("review_method")
    verification.review_note = data.get("review_note")

    if decision == "VERIFIED":
        verification.verified_at = _utcnow()
        # Set expiration if provided
        expires_days = data.get("expires_days")
        if expires_days:
            verification.expires_at = _utcnow() + timedelta(days=int(expires_days))
        # Update profile verification labels
        await _update_profile_verification_status(
            session, verification.user_id, verification.verification_type, True
        )
    elif decision == "REJECTED":
        verification.revoke_reason = data.get("revoke_reason")
    elif decision == "SUSPENDED":
        verification.revoked_at = _utcnow()
        verification.revoke_reason = data.get("revoke_reason")
        await _update_profile_verification_status(
            session, verification.user_id, verification.verification_type, False
        )

    verification.updated_at = _utcnow()
    await session.flush()

    await audit(
        session,
        action="identity.verification_review",
        entity_type="identity_verifications",
        entity_id=verification.id,
        actor_id=reviewer_id,
        after={"status": decision},
    )

    return _verification_to_dict(verification)


async def list_verifications(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List verification records."""
    stmt = select(IdentityVerification)
    if user_id:
        stmt = stmt.where(IdentityVerification.user_id == user_id)
    if target_type:
        stmt = stmt.where(IdentityVerification.target_type == target_type)
    if target_id:
        stmt = stmt.where(IdentityVerification.target_id == target_id)
    if status:
        stmt = stmt.where(IdentityVerification.status == status)
    stmt = stmt.order_by(IdentityVerification.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    total = await session.scalar(select(func.count(IdentityVerification.id)))
    return {"items": [_verification_to_dict(v) for v in rows], "total": total or 0}


async def _update_profile_verification_status(
    session: AsyncSession,
    user_id: uuid.UUID,
    verification_type: str,
    verified: bool,
) -> None:
    """Update profile verification labels when verification status changes."""
    profile = await session.get(UserProfile, user_id)
    if profile is None:
        return
    if verification_type == "IDENTITY_VERIFIED":
        profile.identity_verified = verified
    elif verification_type == "ORGANIZATION_VERIFIED":
        profile.organization_verified = verified
    elif verification_type == "OFFICIAL_REP_VERIFIED":
        profile.official_representative = verified
    profile.updated_at = _utcnow()


def _verification_to_dict(v: IdentityVerification) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "user_id": str(v.user_id),
        "verification_type": v.verification_type,
        "target_type": v.target_type,
        "target_id": str(v.target_id),
        "status": v.status,
        "evidence_refs": v.evidence_refs,
        "reviewer_id": str(v.reviewer_id) if v.reviewer_id else None,
        "review_method": v.review_method,
        "review_note": v.review_note,
        "verified_at": v.verified_at.isoformat() if v.verified_at else None,
        "expires_at": v.expires_at.isoformat() if v.expires_at else None,
        "revoked_at": v.revoked_at.isoformat() if v.revoked_at else None,
        "revoke_reason": v.revoke_reason,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


# ---------------------------------------------------------------------------
# Organization Identity
# ---------------------------------------------------------------------------


async def create_organization(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    data: dict[str, Any],
    request: Any = None,
) -> dict[str, Any]:
    """Create a new organization."""
    name = data.get("name", "").strip()
    if len(name) < 3:
        raise ApiError("name must be at least 3 characters", 422, "invalid_name")

    slug = data.get("slug", "").strip().lower()
    if not slug:
        slug = name.lower().replace(" ", "-")[:64]

    # Check slug uniqueness
    existing = await session.scalar(select(Organization).where(Organization.slug == slug))
    if existing:
        raise ApiError("slug already exists", 409, "slug_conflict")

    org_type = data.get("organization_type", "other")
    valid_types = {
        "ngo",
        "community_group",
        "resident_association",
        "educational",
        "healthcare",
        "civic",
        "professional",
        "government",
        "other",
    }
    if org_type not in valid_types:
        raise ApiError("invalid organization_type", 422, "invalid_org_type")

    org = Organization(
        name=name,
        slug=slug,
        description=data.get("description"),
        organization_type=org_type,
        geography_id=_safe_uuid(data.get("geography_id")),
        address=data.get("address"),
        website=data.get("website"),
        owner_id=owner_id,
        status="active",
    )
    session.add(org)
    await session.flush()

    # Auto-add owner as member
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=owner_id,
        role="owner",
        status="active",
        invited_by=owner_id,
    )
    session.add(membership)
    await session.flush()

    await audit(
        session,
        action="identity.organization_create",
        entity_type="organizations",
        entity_id=org.id,
        actor_id=owner_id,
    )

    return _org_to_dict(org)


async def get_organization(
    session: AsyncSession,
    org_id: uuid.UUID,
) -> dict[str, Any]:
    """Get organization details."""
    org = await session.get(Organization, org_id)
    if org is None:
        raise ApiError("organization not found", 404, "org_not_found")
    return _org_to_dict(org)


async def list_organizations(
    session: AsyncSession,
    *,
    org_type: str | None = None,
    status: str | None = None,
    geography_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List organizations."""
    stmt = select(Organization).where(Organization.status == "active")
    if org_type:
        stmt = stmt.where(Organization.organization_type == org_type)
    if status:
        stmt = stmt.where(Organization.status == status)
    if geography_id:
        stmt = stmt.where(Organization.geography_id == geography_id)
    stmt = stmt.order_by(Organization.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    total = await session.scalar(select(func.count(Organization.id)))
    return {"items": [_org_to_dict(o) for o in rows], "total": total or 0}


async def invite_member(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    inviter_id: uuid.UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Invite a user to an organization."""
    # Check inviter is admin/owner
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == inviter_id,
            OrganizationMembership.status == "active",
        )
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise ApiError("not authorized to invite", 403, "forbidden")

    email = data.get("invitee_email", "").strip()
    if not email:
        raise ApiError("email is required", 422, "missing_email")

    # Check for existing pending invitation
    existing = await session.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.invitee_email == email,
            OrganizationInvitation.status == "pending",
        )
    )
    if existing:
        raise ApiError("invitation already pending", 409, "invitation_exists")

    role = data.get("role", "member")
    valid_roles = {"admin", "manager", "member", "viewer"}
    if role not in valid_roles:
        raise ApiError("invalid role", 422, "invalid_role")

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    invitation = OrganizationInvitation(
        organization_id=organization_id,
        inviter_id=inviter_id,
        invitee_email=email,
        role=role,
        status="pending",
        token_hash=token_hash,
        expires_at=_utcnow() + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    await audit(
        session,
        action="identity.org_invitation_create",
        entity_type="organization_invitations",
        entity_id=invitation.id,
        actor_id=inviter_id,
    )

    return {
        "id": str(invitation.id),
        "organization_id": str(organization_id),
        "invitee_email": email,
        "role": role,
        "status": "pending",
        "expires_at": invitation.expires_at.isoformat(),
        "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
    }


async def accept_invitation(
    session: AsyncSession,
    *,
    invitation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Accept an organization invitation."""
    invitation = await session.get(OrganizationInvitation, invitation_id)
    if invitation is None:
        raise ApiError("invitation not found", 404, "invitation_not_found")

    if invitation.status != "pending":
        raise ApiError("invitation is not pending", 409, "invitation_not_pending")

    if invitation.expires_at and invitation.expires_at < _utcnow():
        invitation.status = "expired"
        await session.flush()
        raise ApiError("invitation has expired", 410, "invitation_expired")

    # Accept
    invitation.status = "accepted"
    invitation.accepted_at = _utcnow()
    invitation.invitee_user_id = user_id

    # Create membership
    membership = OrganizationMembership(
        organization_id=invitation.organization_id,
        user_id=user_id,
        role=invitation.role,
        status="active",
        invited_by=invitation.inviter_id,
    )
    session.add(membership)
    await session.flush()

    await audit(
        session,
        action="identity.org_invitation_accept",
        entity_type="organization_invitations",
        entity_id=invitation.id,
        actor_id=user_id,
    )

    return {
        "id": str(invitation.id),
        "status": "accepted",
        "organization_id": str(invitation.organization_id),
        "role": invitation.role,
    }


async def list_organization_members(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List organization members."""
    stmt = (
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
        )
        .order_by(OrganizationMembership.joined_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    total = await session.scalar(
        select(func.count(OrganizationMembership.id)).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
        )
    )
    return {
        "items": [
            {
                "id": str(m.id),
                "user_id": str(m.user_id),
                "role": m.role,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            for m in rows
        ],
        "total": total or 0,
    }


def _org_to_dict(o: Organization) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "name": o.name,
        "slug": o.slug,
        "description": o.description,
        "organization_type": o.organization_type,
        "geography_id": str(o.geography_id) if o.geography_id else None,
        "address": o.address,
        "website": o.website,
        "verification_status": o.verification_status,
        "verified_at": o.verified_at.isoformat() if o.verified_at else None,
        "status": o.status,
        "owner_id": str(o.owner_id),
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


# ---------------------------------------------------------------------------
# Institution Claims
# ---------------------------------------------------------------------------


async def create_institution_claim(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Create an institution claim request."""
    institution_id = _require_uuid(data.get("institution_id"), "institution_id")

    # Check for existing active claim
    existing = await session.scalar(
        select(InstitutionClaim).where(
            InstitutionClaim.user_id == user_id,
            InstitutionClaim.institution_id == institution_id,
            InstitutionClaim.status.in_(("REQUESTED", "UNDER_REVIEW", "MORE_INFORMATION")),
        )
    )
    if existing:
        raise ApiError("claim already pending", 409, "claim_exists")

    claim = InstitutionClaim(
        user_id=user_id,
        institution_id=institution_id,
        status="REQUESTED",
        evidence_refs=data.get("evidence_refs", []),
        documentation_url=data.get("documentation_url"),
        claim_note=data.get("claim_note"),
    )
    session.add(claim)
    await session.flush()

    await audit(
        session,
        action="identity.institution_claim_create",
        entity_type="institution_claims",
        entity_id=claim.id,
        actor_id=user_id,
    )

    return _claim_to_dict(claim)


async def review_institution_claim(
    session: AsyncSession,
    *,
    claim_id: uuid.UUID,
    data: dict[str, Any],
    reviewer_id: uuid.UUID,
) -> dict[str, Any]:
    """Review an institution claim."""
    claim = await session.get(InstitutionClaim, claim_id)
    if claim is None:
        raise ApiError("claim not found", 404, "claim_not_found")

    decision = data.get("status", "")
    valid_decisions = {"UNDER_REVIEW", "MORE_INFORMATION", "APPROVED", "REJECTED", "REVOKED"}
    if decision not in valid_decisions:
        raise ApiError("invalid decision", 422, "invalid_decision")

    claim.status = decision
    claim.reviewer_id = reviewer_id
    claim.review_note = data.get("review_note")
    claim.decided_at = _utcnow()

    if decision == "APPROVED":
        claim.approved_at = _utcnow()
        # Grant institution representative role (NOT full admin access)
        # This is separate from data access permissions
    elif decision in ("REJECTED", "REVOKED"):
        claim.revoked_at = _utcnow()
        claim.revoke_reason = data.get("revoke_reason")

    claim.updated_at = _utcnow()
    await session.flush()

    await audit(
        session,
        action="identity.institution_claim_review",
        entity_type="institution_claims",
        entity_id=claim.id,
        actor_id=reviewer_id,
        after={"status": decision},
    )

    return _claim_to_dict(claim)


def _claim_to_dict(c: InstitutionClaim) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "user_id": str(c.user_id),
        "institution_id": str(c.institution_id),
        "status": c.status,
        "evidence_refs": c.evidence_refs,
        "documentation_url": c.documentation_url,
        "claim_note": c.claim_note,
        "reviewer_id": str(c.reviewer_id) if c.reviewer_id else None,
        "review_note": c.review_note,
        "decided_at": c.decided_at.isoformat() if c.decided_at else None,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        "revoke_reason": c.revoke_reason,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ---------------------------------------------------------------------------
# Representative Assignments
# ---------------------------------------------------------------------------


async def assign_representative(
    session: AsyncSession,
    *,
    data: dict[str, Any],
    assigned_by: uuid.UUID,
) -> dict[str, Any]:
    """Assign a representative to an organization, institution, or department."""
    user_id = _require_uuid(data.get("user_id"), "user_id")
    rep_type = data.get("representative_type", "")
    valid_types = {"organization", "institution", "department"}
    if rep_type not in valid_types:
        raise ApiError("invalid representative_type", 422, "invalid_rep_type")

    target_id = _require_uuid(data.get("target_id"), "target_id")
    verification_id = _safe_uuid(data.get("verification_id"))

    assignment = RepresentativeAssignment(
        user_id=user_id,
        representative_type=rep_type,
        target_id=target_id,
        role=data.get("role", "representative"),
        status="active",
        verification_id=verification_id,
        assigned_by=assigned_by,
    )
    session.add(assignment)
    await session.flush()

    await audit(
        session,
        action="identity.representative_assign",
        entity_type="representative_assignments",
        entity_id=assignment.id,
        actor_id=assigned_by,
    )

    return {
        "id": str(assignment.id),
        "user_id": str(user_id),
        "representative_type": rep_type,
        "target_id": str(target_id),
        "role": assignment.role,
        "status": "active",
        "assigned_at": assignment.assigned_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Trust Labels (contextual, not scores)
# ---------------------------------------------------------------------------


async def get_trust_labels(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Get contextual trust labels for a user. Never a single score."""
    profile = await session.get(UserProfile, user_id)
    if profile is None:
        return {"user_id": str(user_id), "labels": []}

    labels = []
    if profile.identity_verified:
        labels.append(
            {
                "type": "IDENTITY_VERIFIED",
                "label": "Identity Verified",
                "description": "This identity has been verified according to a defined process.",
            }
        )
    if profile.organization_verified:
        labels.append(
            {
                "type": "ORGANIZATION_VERIFIED",
                "label": "Organization Verified",
                "description": "An organization this user belongs to has been verified.",
            }
        )
    if profile.official_representative:
        labels.append(
            {
                "type": "OFFICIAL_REP_VERIFIED",
                "label": "Official Representative Verified",
                "description": "This user's official representative status has been verified.",
            }
        )

    # Check active verifications for additional labels
    active_verifs = await session.scalars(
        select(IdentityVerification).where(
            IdentityVerification.user_id == user_id,
            IdentityVerification.status == "VERIFIED",
        )
    )
    for v in active_verifs.all():
        if v.expires_at and v.expires_at < _utcnow():
            continue  # Skip expired
        label_map = {
            "EMAIL_VERIFIED": ("Email Verified", "Email address has been verified."),
            "PHONE_VERIFIED": ("Phone Verified", "Phone number has been verified."),
            "SKILL_VERIFIED": ("Skill Verified", "A specific skill claim has been verified."),
        }
        if v.verification_type in label_map:
            name, desc = label_map[v.verification_type]
            labels.append(
                {
                    "type": v.verification_type,
                    "label": name,
                    "description": desc,
                }
            )

    return {
        "user_id": str(user_id),
        "labels": labels,
    }


# ---------------------------------------------------------------------------
# Contribution History (factual, not scored)
# ---------------------------------------------------------------------------


async def get_contribution_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Get factual contribution history. Never converted to a quality score."""
    from tk_api.community.models import InitiativeMember
    from tk_api.reports.models import Report

    # Count public reports
    report_count = (
        await session.scalar(
            select(func.count(Report.id)).where(
                Report.reporter_id == user_id,
                Report.visibility == "public",
                Report.deleted_at.is_(None),
            )
        )
        or 0
    )

    # Count initiatives participated in
    initiative_count = (
        await session.scalar(
            select(func.count(InitiativeMember.id)).where(
                InitiativeMember.user_id == user_id,
                InitiativeMember.status == "active",
            )
        )
        or 0
    )

    return {
        "user_id": str(user_id),
        "public_reports": report_count,
        "initiatives_participated": initiative_count,
        "note": "Factual activity record. Not a quality score or ranking.",
    }


# ---------------------------------------------------------------------------
# Account Status History
# ---------------------------------------------------------------------------


async def record_status_change(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    old_status: str | None,
    new_status: str,
    reason: str | None = None,
    changed_by: uuid.UUID | None = None,
) -> None:
    """Record an account status change (append-only)."""
    record = AccountStatusHistory(
        user_id=user_id,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        changed_by=changed_by,
    )
    session.add(record)
    await session.flush()
