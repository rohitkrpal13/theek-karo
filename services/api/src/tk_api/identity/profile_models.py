"""Phase 24 — Identity, Profile, Verification, Trust & Organization models.

Extends the existing auth/user/role foundation with:
- User profiles (public/private fields, visibility)
- User preferences (language, timezone, notifications)
- Privacy preferences (profile/contact/contribution visibility)
- Identity verification framework (types, evidence, expiration)
- Organization identity (membership, invitations, roles, verification)
- Institution claims (claim workflow with evidence and review)
- Representative assignments
- Identity provider links (extensible OAuth architecture)
- Account status history

Does NOT create: citizen scores, political profiling, reputation systems.
Trust is contextual and describes platform-specific verification state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# User Profile (spec §10-§13)
# ---------------------------------------------------------------------------

PROFILE_VISIBILITIES = ("PUBLIC", "COMMUNITY", "PRIVATE")


class UserProfile(Base):
    """Extended user profile with public/private fields and visibility control."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Public fields
    display_name: Mapped[str] = mapped_column(Text, default="")
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    civic_interests: Mapped[list[str]] = mapped_column(_jsonb(), default=list)
    # Visibility
    profile_visibility: Mapped[str] = mapped_column(String(16), default="PUBLIC")
    contact_visibility: Mapped[str] = mapped_column(String(16), default="PRIVATE")
    contribution_visibility: Mapped[str] = mapped_column(String(16), default="PUBLIC")
    location_visibility: Mapped[str] = mapped_column(String(16), default="PRIVATE")
    # Stats (denormalized for performance)
    public_report_count: Mapped[int] = mapped_column(Integer, default=0)
    public_initiative_count: Mapped[int] = mapped_column(Integer, default=0)
    public_evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    # Verification labels (contextual, not scores)
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    organization_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    official_representative: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "profile_visibility IN ('PUBLIC','COMMUNITY','PRIVATE')",
            name="ck_user_profiles_visibility",
        ),
        CheckConstraint(
            "contact_visibility IN ('PUBLIC','COMMUNITY','PRIVATE')",
            name="ck_user_profiles_contact_visibility",
        ),
        CheckConstraint(
            "contribution_visibility IN ('PUBLIC','COMMUNITY','PRIVATE')",
            name="ck_user_profiles_contribution_visibility",
        ),
    )


# ---------------------------------------------------------------------------
# User Preferences (spec §17-§18)
# ---------------------------------------------------------------------------


class UserPreferences(Base):
    """User preferences for language, timezone, notifications, accessibility."""

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(16), default="hi")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    notification_preferences: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    accessibility_settings: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    content_preferences: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    map_preferences: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    ai_processing_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


# ---------------------------------------------------------------------------
# Identity Verification (spec §19-§26)
# ---------------------------------------------------------------------------

VERIFICATION_TYPES = (
    "EMAIL_VERIFIED",
    "PHONE_VERIFIED",
    "IDENTITY_VERIFIED",
    "ORGANIZATION_VERIFIED",
    "INSTITUTION_REP_VERIFIED",
    "OFFICIAL_REP_VERIFIED",
    "SKILL_VERIFIED",
)

VERIFICATION_STATES = (
    "NOT_VERIFIED",
    "PENDING",
    "UNDER_REVIEW",
    "VERIFIED",
    "EXPIRED",
    "REJECTED",
    "SUSPENDED",
)


class IdentityVerification(Base):
    """Contextual verification record for users, organizations, institutions."""

    __tablename__ = "identity_verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    verification_type: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str] = mapped_column(String(32))  # user, organization, institution
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    status: Mapped[str] = mapped_column(String(24), default="NOT_VERIFIED")
    # Evidence
    evidence_refs: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    documentation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Review
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    review_method: Mapped[str | None] = mapped_column(String(64))
    review_note: Mapped[str | None] = mapped_column(Text)
    # Lifecycle
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    # Metadata
    meta: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "verification_type IN ('EMAIL_VERIFIED','PHONE_VERIFIED','IDENTITY_VERIFIED',"
            "'ORGANIZATION_VERIFIED','INSTITUTION_REP_VERIFIED','OFFICIAL_REP_VERIFIED',"
            "'SKILL_VERIFIED')",
            name="ck_identity_verifications_type",
        ),
        CheckConstraint(
            "status IN ('NOT_VERIFIED','PENDING','UNDER_REVIEW','VERIFIED',"
            "'EXPIRED','REJECTED','SUSPENDED')",
            name="ck_identity_verifications_status",
        ),
        CheckConstraint(
            "target_type IN ('user','organization','institution','department')",
            name="ck_identity_verifications_target",
        ),
        Index("ix_verification_user_type", "user_id", "verification_type"),
        Index("ix_verification_target", "target_type", "target_id"),
    )


# ---------------------------------------------------------------------------
# Organization Identity (spec §27-§34)
# ---------------------------------------------------------------------------

ORGANIZATION_TYPES = (
    "ngo",
    "community_group",
    "resident_association",
    "educational",
    "healthcare",
    "civic",
    "professional",
    "government",
    "other",
)

ORGANIZATION_STATUSES = ("draft", "active", "suspended", "archived")

ORGANIZATION_MEMBER_ROLES = ("owner", "admin", "manager", "member", "viewer")

INVITATION_STATUSES = ("pending", "accepted", "declined", "expired", "revoked")


class Organization(Base):
    """First-class organization entity with profile, verification, and membership."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization_type: Mapped[str] = mapped_column(String(32), default="other")
    # Location
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL")
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Verification
    verification_status: Mapped[str] = mapped_column(String(24), default="NOT_VERIFIED")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Status
    status: Mapped[str] = mapped_column(String(16), default="draft")
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    # Metadata
    meta: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "organization_type IN ('ngo','community_group','resident_association',"
            "'educational','healthcare','civic','professional','government','other')",
            name="ck_organizations_type",
        ),
        CheckConstraint(
            "status IN ('draft','active','suspended','archived')",
            name="ck_organizations_status",
        ),
        CheckConstraint(
            "verification_status IN ('NOT_VERIFIED','PENDING','UNDER_REVIEW','VERIFIED',"
            "'EXPIRED','REJECTED','SUSPENDED')",
            name="ck_organizations_verification",
        ),
    )


class OrganizationMembership(Base):
    """User membership in an organization with role-based access."""

    __tablename__ = "organization_memberships"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), default="member")
    status: Mapped[str] = mapped_column(String(16), default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_memberships"),
        CheckConstraint(
            "role IN ('owner','admin','manager','member','viewer')",
            name="ck_org_memberships_role",
        ),
        CheckConstraint(
            "status IN ('active','suspended','removed')",
            name="ck_org_memberships_status",
        ),
    )


class OrganizationInvitation(Base):
    """Invitation to join an organization."""

    __tablename__ = "organization_invitations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    inviter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    invitee_email: Mapped[str] = mapped_column(Text)
    invitee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    role: Mapped[str] = mapped_column(String(16), default="member")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    token_hash: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','accepted','declined','expired','revoked')",
            name="ck_org_invitations_status",
        ),
    )


# ---------------------------------------------------------------------------
# Institution Claims (spec §35-§39)
# ---------------------------------------------------------------------------

CLAIM_STATES = ("REQUESTED", "UNDER_REVIEW", "MORE_INFORMATION", "APPROVED", "REJECTED", "REVOKED")


class InstitutionClaim(Base):
    """A user's claim to represent an institution."""

    __tablename__ = "institution_claims"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="REQUESTED")
    # Evidence
    evidence_refs: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    documentation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Review
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Lifecycle
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('REQUESTED','UNDER_REVIEW','MORE_INFORMATION','APPROVED',"
            "'REJECTED','REVOKED')",
            name="ck_institution_claims_status",
        ),
    )


# ---------------------------------------------------------------------------
# Representative Assignments (spec §33-§34)
# ---------------------------------------------------------------------------

REPRESENTATIVE_TYPES = ("organization", "institution", "department")


class RepresentativeAssignment(Base):
    """A designated representative for an organization, institution, or department."""

    __tablename__ = "representative_assignments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    representative_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    role: Mapped[str] = mapped_column(String(32), default="representative")
    status: Mapped[str] = mapped_column(String(16), default="active")
    # Verification
    verification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_verifications.id", ondelete="SET NULL")
    )
    # Lifecycle
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "representative_type IN ('organization','institution','department')",
            name="ck_representatives_type",
        ),
        CheckConstraint(
            "status IN ('active','suspended','revoked')",
            name="ck_representatives_status",
        ),
        Index("ix_rep_target", "representative_type", "target_id"),
    )


# ---------------------------------------------------------------------------
# Identity Provider Links (spec §8, §76 — extensible architecture)
# ---------------------------------------------------------------------------


class IdentityProviderLink(Base):
    """Extensible identity provider links beyond the existing OAuthAccount.
    Supports future providers (password, passkey, additional OAuth)."""

    __tablename__ = "identity_provider_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_subject: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())

    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_provider_subject"),)


# ---------------------------------------------------------------------------
# Account Status History (spec §61, §77 — append-only)
# ---------------------------------------------------------------------------


class AccountStatusHistory(Base):
    """Append-only account status change log for audit."""

    __tablename__ = "account_status_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
