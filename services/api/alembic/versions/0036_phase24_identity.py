"""Phase 24 — Identity, Profile, Verification, Trust & Organization layer.

Establishes the unified identity layer connecting users, profiles,
verification, organizations, institution claims, and trust labels.

New tables: ``user_profiles``, ``user_preferences``,
``identity_verifications``, ``organizations``, ``organization_memberships``,
``organization_invitations``, ``institution_claims``,
``representative_assignments``, ``identity_provider_links``,
``account_status_history``.

Pure additive; downgrade drops all tables.

Revision ID: 0036_phase24_identity
Revises: 0035_phase23_data_trust
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0036_phase24_identity"
down_revision: str | None = "0035_phase23_data_trust"


def upgrade() -> None:
    # -- User Profile (spec §10-§13) -----------------------------------------
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("display_name", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("profile_image_url", sa.Text(), nullable=True),
        sa.Column(
            "civic_interests",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("profile_visibility", sa.String(16), nullable=False, server_default="PUBLIC"),
        sa.Column("contact_visibility", sa.String(16), nullable=False, server_default="PRIVATE"),
        sa.Column(
            "contribution_visibility", sa.String(16), nullable=False, server_default="PUBLIC"
        ),
        sa.Column("location_visibility", sa.String(16), nullable=False, server_default="PRIVATE"),
        sa.Column("public_report_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "public_initiative_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "public_evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "identity_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "organization_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "official_representative", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "profile_visibility IN ('PUBLIC','COMMUNITY','PRIVATE')",
            name="ck_user_profiles_visibility",
        ),
        sa.CheckConstraint(
            "contact_visibility IN ('PUBLIC','COMMUNITY','PRIVATE')",
            name="ck_user_profiles_contact_visibility",
        ),
        sa.CheckConstraint(
            "contribution_visibility IN ('PUBLIC','COMMUNITY','PRIVATE')",
            name="ck_user_profiles_contribution_visibility",
        ),
    )

    # -- User Preferences (spec §17-§18) -------------------------------------
    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("language", sa.String(16), nullable=False, server_default="hi"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column(
            "notification_preferences",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "accessibility_settings",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "content_preferences",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "map_preferences",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "ai_processing_consent", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # -- Identity Verification (spec §19-§26) ---------------------------------
    op.create_table(
        "identity_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("verification_type", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="NOT_VERIFIED"),
        sa.Column(
            "evidence_refs",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("documentation_url", sa.Text(), nullable=True),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("review_method", sa.String(64), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column(
            "meta",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "verification_type IN ('EMAIL_VERIFIED','PHONE_VERIFIED','IDENTITY_VERIFIED',"
            "'ORGANIZATION_VERIFIED','INSTITUTION_REP_VERIFIED','OFFICIAL_REP_VERIFIED',"
            "'SKILL_VERIFIED')",
            name="ck_identity_verifications_type",
        ),
        sa.CheckConstraint(
            "status IN ('NOT_VERIFIED','PENDING','UNDER_REVIEW','VERIFIED',"
            "'EXPIRED','REJECTED','SUSPENDED')",
            name="ck_identity_verifications_status",
        ),
        sa.CheckConstraint(
            "target_type IN ('user','organization','institution','department')",
            name="ck_identity_verifications_target",
        ),
    )
    op.create_index(
        "ix_verification_user_type", "identity_verifications", ["user_id", "verification_type"]
    )
    op.create_index(
        "ix_verification_target", "identity_verifications", ["target_type", "target_id"]
    )

    # -- Organizations (spec §27-§34) -----------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("organization_type", sa.String(32), nullable=False, server_default="other"),
        sa.Column(
            "geography_id",
            sa.Uuid(),
            sa.ForeignKey("geographies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column(
            "verification_status", sa.String(24), nullable=False, server_default="NOT_VERIFIED"
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verified_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "meta",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "organization_type IN ('ngo','community_group','resident_association',"
            "'educational','healthcare','civic','professional','government','other')",
            name="ck_organizations_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','suspended','archived')",
            name="ck_organizations_status",
        ),
        sa.CheckConstraint(
            "verification_status IN ('NOT_VERIFIED','PENDING','UNDER_REVIEW','VERIFIED',"
            "'EXPIRED','REJECTED','SUSPENDED')",
            name="ck_organizations_verification",
        ),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # -- Organization Memberships ---------------------------------------------
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "invited_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_memberships"),
        sa.CheckConstraint(
            "role IN ('owner','admin','manager','member','viewer')",
            name="ck_org_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('active','suspended','removed')",
            name="ck_org_memberships_status",
        ),
    )
    op.create_index("ix_org_memberships_org", "organization_memberships", ["organization_id"])
    op.create_index("ix_org_memberships_user", "organization_memberships", ["user_id"])

    # -- Organization Invitations ---------------------------------------------
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inviter_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("invitee_email", sa.Text(), nullable=False),
        sa.Column(
            "invitee_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','declined','expired','revoked')",
            name="ck_org_invitations_status",
        ),
    )
    op.create_index("ix_org_invitations_org", "organization_invitations", ["organization_id"])

    # -- Institution Claims (spec §35-§39) ------------------------------------
    op.create_table(
        "institution_claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "institution_id",
            sa.Uuid(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="REQUESTED"),
        sa.Column(
            "evidence_refs",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("documentation_url", sa.Text(), nullable=True),
        sa.Column("claim_note", sa.Text(), nullable=True),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED','UNDER_REVIEW','MORE_INFORMATION','APPROVED',"
            "'REJECTED','REVOKED')",
            name="ck_institution_claims_status",
        ),
    )
    op.create_index("ix_institution_claims_user", "institution_claims", ["user_id"])
    op.create_index("ix_institution_claims_institution", "institution_claims", ["institution_id"])

    # -- Representative Assignments (spec §33-§34) ----------------------------
    op.create_table(
        "representative_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("representative_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="representative"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "verification_id",
            sa.Uuid(),
            sa.ForeignKey("identity_verifications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "representative_type IN ('organization','institution','department')",
            name="ck_representatives_type",
        ),
        sa.CheckConstraint(
            "status IN ('active','suspended','revoked')",
            name="ck_representatives_status",
        ),
    )
    op.create_index("ix_representatives_user", "representative_assignments", ["user_id"])
    op.create_index(
        "ix_rep_target", "representative_assignments", ["representative_type", "target_id"]
    )

    # -- Identity Provider Links (spec §8, §76) -------------------------------
    op.create_table(
        "identity_provider_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "meta",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_provider_subject"),
    )
    op.create_index("ix_provider_links_user", "identity_provider_links", ["user_id"])

    # -- Account Status History (spec §61, §77) -------------------------------
    op.create_table(
        "account_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("old_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "changed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_account_status_user", "account_status_history", ["user_id"])


def downgrade() -> None:
    op.drop_table("account_status_history")
    op.drop_table("identity_provider_links")
    op.drop_table("representative_assignments")
    op.drop_table("institution_claims")
    op.drop_table("organization_invitations")
    op.drop_table("organization_memberships")
    op.drop_table("organizations")
    op.drop_table("identity_verifications")
    op.drop_table("user_preferences")
    op.drop_table("user_profiles")
