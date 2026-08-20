"""Phase 18 community & civic participation layer (ADR-053).

New tables: civic_initiatives, initiative_members, initiative_observations,
initiative_followers, volunteer_profiles, volunteer_opportunities,
volunteer_signups, community_groups, group_members, badges, user_badges.

Design notes:
- Initiative lifecycle: draft → submitted → review → approved → active →
  completed → archived (plus rejected); platform moderators review public
  initiatives; the initiator owns the draft.
- Volunteer profiles are opt-in and store only explicit user preferences
  (languages, interests, categories, areas, skills, availability) — no phone,
  address, or exact location. Opportunities are the only joinable surface.
- Groups: owner/moderator/member; platform safety rules always override group
  rules; status requested → approved → active (or suspended/archived).
- Badges: deterministic criteria (JSON) evaluated by the badge engine; never
  AI-only awards.
- initiative_followers reuses the follow pattern (like report/institution/
  geography/category follows).

Revision ID: 0029_phase18_community_layer
Revises: 0028_phase16_mfa_login_backoff
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_phase18_community_layer"
down_revision: str | None = "0028_phase16_mfa_login_backoff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BADGE_SEEDS = [
    {
        "code": "verified_contributor",
        "name": "Verified Contributor",
        "name_hi": "सत्यापित योगदानकर्ता",
        "description": "Earned 5 platform-verified contributions (reports or resolutions).",
        "criteria": {"metric": "verified_contributions", "min": 5},
    },
    {
        "code": "evidence_contributor",
        "name": "Evidence Contributor",
        "name_hi": "साक्ष्य योगदानकर्ता",
        "description": "Added 10 accepted pieces of evidence.",
        "criteria": {"metric": "accepted_evidence", "min": 10},
    },
    {
        "code": "community_researcher",
        "name": "Community Researcher",
        "name_hi": "सामुदायिक शोधकर्ता",
        "description": "Added 20 accepted data corrections.",
        "criteria": {"metric": "accepted_corrections", "min": 20},
    },
    {
        "code": "community_contributor",
        "name": "Community Contributor",
        "name_hi": "सामुदायिक योगदानकर्ता",
        "description": "Wrote 20 constructive comments or replies on public reports.",
        "criteria": {"metric": "comments_written", "min": 20},
    },
    {
        "code": "volunteer",
        "name": "Volunteer",
        "name_hi": "स्वयंसेवक",
        "description": "Completed 3 volunteer activities.",
        "criteria": {"metric": "volunteer_completions", "min": 3},
    },
    {
        "code": "initiative_organizer",
        "name": "Initiative Organizer",
        "name_hi": "पहल आयोजक",
        "description": "Led 2 completed community initiatives.",
        "criteria": {"metric": "initiatives_completed_organized", "min": 2},
    },
    {
        "code": "helpful_contributor",
        "name": "Helpful Contributor",
        "name_hi": "सहायक योगदानकर्ता",
        "description": "Received 20 helpful reactions on contributions.",
        "criteria": {"metric": "helpful_reactions", "min": 20},
    },
]


def upgrade() -> None:
    # -- civic initiatives ------------------------------------------------------
    op.create_table(
        "civic_initiatives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("initiator_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("expected_activities", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("participation_rules", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "evidence_requirements", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_civic_initiatives_slug"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["initiator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'review', 'approved', 'active', "
            "'completed', 'archived', 'rejected')",
            name="ck_civic_initiatives_status",
        ),
    )
    op.create_index(op.f("ix_civic_initiatives_status"), "civic_initiatives", ["status"])
    op.create_index(op.f("ix_civic_initiatives_initiator"), "civic_initiatives", ["initiator_id"])
    op.create_index(op.f("ix_civic_initiatives_geography"), "civic_initiatives", ["geography_id"])

    op.create_table(
        "initiative_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("initiative_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role", sa.String(length=16), nullable=False, server_default=sa.text("'participant'")
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["initiative_id"], ["civic_initiatives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("initiative_id", "user_id", name="uq_initiative_members"),
        sa.CheckConstraint(
            "role IN ('initiator', 'organizer', 'participant')", name="ck_initiative_members_role"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'completed')", name="ck_initiative_members_status"
        ),
    )
    op.create_index(
        op.f("ix_initiative_members_initiative"), "initiative_members", ["initiative_id"]
    )
    op.create_index(op.f("ix_initiative_members_user"), "initiative_members", ["user_id"])

    op.create_table(
        "initiative_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("initiative_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'observation'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("media_object_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["initiative_id"], ["civic_initiatives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_object_id"], ["media_objects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "kind IN ('observation', 'photo', 'document', 'location_confirmation', 'correction')",
            name="ck_initiative_observations_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_initiative_observations_status",
        ),
    )
    op.create_index(
        op.f("ix_initiative_observations_initiative"),
        "initiative_observations",
        ["initiative_id"],
    )

    op.create_table(
        "initiative_followers",
        sa.Column("initiative_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("initiative_id", "user_id", name="pk_initiative_followers"),
        sa.ForeignKeyConstraint(["initiative_id"], ["civic_initiatives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )

    # -- volunteer system --------------------------------------------------------
    op.create_table(
        "volunteer_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("interests", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("areas", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("availability", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "volunteer_opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("initiative_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location_label", sa.Text(), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("participants_needed", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["initiative_id"], ["civic_initiatives.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('open', 'closed', 'completed')", name="ck_volunteer_opportunities_status"
        ),
    )
    op.create_index(
        op.f("ix_volunteer_opportunities_status"), "volunteer_opportunities", ["status"]
    )
    op.create_index(
        op.f("ix_volunteer_opportunities_initiative"),
        "volunteer_opportunities",
        ["initiative_id"],
    )

    op.create_table(
        "volunteer_signups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default=sa.text("'joined'")
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["volunteer_opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("opportunity_id", "user_id", name="uq_volunteer_signups"),
        sa.CheckConstraint(
            "status IN ('joined', 'withdrawn', 'completed')", name="ck_volunteer_signups_status"
        ),
    )
    op.create_index(
        op.f("ix_volunteer_signups_opportunity"), "volunteer_signups", ["opportunity_id"]
    )
    op.create_index(op.f("ix_volunteer_signups_user"), "volunteer_signups", ["user_id"])

    # -- community groups ---------------------------------------------------------
    op.create_table(
        "community_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'requested'"),
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_community_groups_slug"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'active', 'suspended', 'archived')",
            name="ck_community_groups_status",
        ),
    )
    op.create_index(op.f("ix_community_groups_status"), "community_groups", ["status"])
    op.create_index(op.f("ix_community_groups_owner"), "community_groups", ["owner_id"])

    op.create_table(
        "group_members",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default=sa.text("'member'")),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("group_id", "user_id", name="pk_group_members"),
        sa.ForeignKeyConstraint(["group_id"], ["community_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "role IN ('owner', 'moderator', 'member')", name="ck_group_members_role"
        ),
        sa.CheckConstraint("status IN ('active', 'banned')", name="ck_group_members_status"),
    )
    op.create_index(op.f("ix_group_members_user"), "group_members", ["user_id"])

    # -- badges --------------------------------------------------------------------
    op.create_table(
        "badges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_hi", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_badges_code"),
    )

    op.create_table(
        "user_badges",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("badge_id", sa.Uuid(), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "badge_id", name="pk_user_badges"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["badge_id"], ["badges.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_user_badges_badge"), "user_badges", ["badge_id"])

    # -- seeds -----------------------------------------------------------------------
    import json
    import uuid
    from datetime import UTC, datetime

    conn = op.get_bind()
    now = datetime.now(UTC)
    existing = {row[0] for row in conn.execute(sa.text("SELECT code FROM badges")).fetchall()}
    for seed in _BADGE_SEEDS:
        if seed["code"] in existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO badges (id, code, name, name_hi, description, criteria, created_at) "
                "VALUES (:id, :code, :name, :name_hi, :description, CAST(:criteria AS json), :now)"
            ),
            {
                "id": uuid.uuid4(),
                "code": seed["code"],
                "name": seed["name"],
                "name_hi": seed.get("name_hi"),
                "description": seed.get("description"),
                "criteria": json.dumps(seed["criteria"]),
                "now": now,
            },
        )


def downgrade() -> None:
    op.drop_table("user_badges")
    op.drop_table("badges")
    op.drop_table("group_members")
    op.drop_table("community_groups")
    op.drop_table("volunteer_signups")
    op.drop_table("volunteer_opportunities")
    op.drop_table("volunteer_profiles")
    op.drop_table("initiative_followers")
    op.drop_table("initiative_observations")
    op.drop_table("initiative_members")
    op.drop_table("civic_initiatives")
