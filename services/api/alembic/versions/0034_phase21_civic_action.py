"""Phase 21 civic action orchestration.

Adds the coordinated-action model on top of Phase 18 initiatives and
Phase 20 intelligence: action plans (with AI-assisted suggestion + human
approval gate), tasks with milestones and dependencies, volunteer
applications and assignments, civic teams with role permissions, action
evidence with verification, human outcome reviews, impact metrics +
measurements, civic events, and campaign links (initiatives + members).

Design principles (docs/CIVIC-ACTION.md):

* AI assists humans — plans, volunteer matches and impact claims are always
  labeled AI GENERATED/AI ASSISTED and require human approval or review.
* Progress is computed from task/milestone state, never entered manually.
* Impact is only "verified" when evidence + human review exist.
* Volunteer privacy: only opt-in preferences are stored; matches never
  expose contact details or exact locations.
* No autonomous high-impact action: tasks, assignments and government-facing
  requests always require an explicit human step.

New tables: ``action_plans``, ``action_tasks``, ``action_milestones``,
``action_dependencies``, ``task_comments``, ``action_updates``,
``civic_teams``, ``civic_team_members``, ``volunteer_applications``,
``action_evidence``, ``action_reviews``, ``impact_metrics``,
``impact_measurements``, ``civic_events``, ``event_participants``,
``campaign_initiatives``, ``campaign_members``.

Plus notification template seeds (hi/en) for the new event types.

Pure additive; downgrade drops the tables/columns and the templates.

Revision ID: 0034_phase21_civic_action
Revises: 0033_phase20_civic_intelligence
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0034_phase21_civic_action"
down_revision: str | None = "0033_phase20_civic_intelligence"

_TEMPLATES = [
    # (event, channel, locale, subject_key, body_text)
    (
        "civic_action.task_assigned",
        "in_app",
        "hi",
        "नया कार्य सौंपा गया",
        "{title} कार्य आपको सौंपा गया है।",
    ),
    (
        "civic_action.task_assigned",
        "in_app",
        "en",
        "Task assigned",
        "You have been assigned task: {title}.",
    ),
    (
        "civic_action.task_deadline",
        "in_app",
        "hi",
        "कार्य की समय सीमा",
        "कार्य {title} की समय सीमा {due} है।",
    ),
    (
        "civic_action.task_deadline",
        "in_app",
        "en",
        "Task deadline",
        "Task {title} is due {due}.",
    ),
    (
        "civic_action.task_comment",
        "in_app",
        "hi",
        "नई टिप्पणी",
        "{actor} ने कार्य {title} पर टिप्पणी की।",
    ),
    (
        "civic_action.task_comment",
        "in_app",
        "en",
        "New comment",
        "{actor} commented on task {title}.",
    ),
    (
        "civic_action.volunteer_applied",
        "in_app",
        "hi",
        "स्वयंसेवक आवेदन",
        "{actor} ने आपकी पहल पर आवेदन किया।",
    ),
    (
        "civic_action.volunteer_applied",
        "in_app",
        "en",
        "Volunteer application",
        "{actor} applied to your initiative.",
    ),
    (
        "civic_action.volunteer_decision",
        "in_app",
        "hi",
        "आवेदन पर निर्णय",
        "आपका स्वयंसेवक आवेदन {status} हुआ।",
    ),
    (
        "civic_action.volunteer_decision",
        "in_app",
        "en",
        "Application decision",
        "Your volunteer application was {status}.",
    ),
    (
        "civic_action.evidence_reviewed",
        "in_app",
        "hi",
        "साक्ष्य समीक्षा",
        "आपके साक्ष्य की समीक्षा हुई: {status}।",
    ),
    (
        "civic_action.evidence_reviewed",
        "in_app",
        "en",
        "Evidence reviewed",
        "Your evidence was reviewed: {status}.",
    ),
    (
        "civic_action.outcome_verified",
        "in_app",
        "hi",
        "परिणाम सत्यापित",
        "पहल का परिणाम सत्यापित हुआ।",
    ),
    (
        "civic_action.outcome_verified",
        "in_app",
        "en",
        "Outcome verified",
        "The initiative outcome was verified.",
    ),
    (
        "civic_action.event_published",
        "in_app",
        "hi",
        "आयोजन प्रकाशित",
        "आयोजन {title} प्रकाशित हुआ।",
    ),
    (
        "civic_action.event_published",
        "in_app",
        "en",
        "Event published",
        "Event {title} was published.",
    ),
]


def upgrade() -> None:
    op.create_table(
        "action_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id",
            sa.Uuid(),
            sa.ForeignKey("civic_initiatives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="PROPOSED"),
        sa.Column(
            "risk_notes",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "ai_suggestion",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "ai_approved_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ai_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
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
            "status IN ('PROPOSED','OPEN','ACTIVE','BLOCKED','COMPLETED',"
            "'VERIFICATION_PENDING','VERIFIED','CANCELLED')",
            name="ck_action_plans_status",
        ),
    )
    op.create_index("ix_action_plans_initiative_id", "action_plans", ["initiative_id"], unique=True)

    op.create_table(
        "action_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("action_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "assignee_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("priority", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(32), nullable=False, server_default="TODO"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "location",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column(
            "checklist",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('TODO','ASSIGNED','IN_PROGRESS','BLOCKED','SUBMITTED',"
            "'VERIFICATION_PENDING','COMPLETED','CANCELLED')",
            name="ck_action_tasks_status",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')", name="ck_action_tasks_priority"
        ),
    )
    op.create_index("ix_action_tasks_plan_id", "action_tasks", ["plan_id"])
    op.create_index("ix_action_tasks_assignee_id", "action_tasks", ["assignee_id"])
    op.create_index("ix_action_tasks_status", "action_tasks", ["status"])
    op.create_index("ix_action_tasks_due_at", "action_tasks", ["due_at"])
    op.create_index("ix_action_tasks_institution_id", "action_tasks", ["institution_id"])

    op.create_table(
        "action_milestones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("action_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_idx", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','cancelled')",
            name="ck_action_milestones_status",
        ),
    )
    op.create_index("ix_action_milestones_plan_id", "action_milestones", ["plan_id"])

    op.create_table(
        "action_dependencies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("action_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_task_id",
            sa.Uuid(),
            sa.ForeignKey("action_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_action_dependencies"),
        sa.CheckConstraint("task_id != depends_on_task_id", name="ck_action_dependencies_distinct"),
    )
    op.create_index("ix_action_dependencies_task_id", "action_dependencies", ["task_id"])
    op.create_index(
        "ix_action_dependencies_depends_on_task_id", "action_dependencies", ["depends_on_task_id"]
    )

    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("action_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id"])

    op.create_table(
        "action_updates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id",
            sa.Uuid(),
            sa.ForeignKey("civic_initiatives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status_snapshot",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_action_updates_initiative_id", "action_updates", ["initiative_id"])

    op.create_table(
        "civic_teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id",
            sa.Uuid(),
            sa.ForeignKey("civic_initiatives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_civic_teams_initiative_id", "civic_teams", ["initiative_id"])

    op.create_table(
        "civic_team_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "team_id",
            sa.Uuid(),
            sa.ForeignKey("civic_teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("role", sa.String(24), nullable=False, server_default="field_volunteer"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("team_id", "user_id", name="uq_civic_team_members"),
        sa.CheckConstraint(
            "role IN ('coordinator','field_volunteer','evidence_reviewer','data_reviewer')",
            name="ck_civic_team_members_role",
        ),
    )
    op.create_index("ix_civic_team_members_team_id", "civic_team_members", ["team_id"])

    op.create_table(
        "volunteer_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id",
            sa.Uuid(),
            sa.ForeignKey("civic_initiatives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("action_tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "applicant_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "decided_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','withdrawn')",
            name="ck_volunteer_applications_status",
        ),
    )
    op.create_index(
        "ix_volunteer_applications_initiative_id", "volunteer_applications", ["initiative_id"]
    )
    op.create_index("ix_volunteer_applications_task_id", "volunteer_applications", ["task_id"])
    op.create_index(
        "ix_volunteer_applications_applicant_id", "volunteer_applications", ["applicant_id"]
    )

    op.create_table(
        "action_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id",
            sa.Uuid(),
            sa.ForeignKey("civic_initiatives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("action_plans.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("action_tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "uploader_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "media_id",
            sa.Uuid(),
            sa.ForeignKey("media_objects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(24), nullable=False, server_default="general"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "checklist_snapshot",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "location",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("sha256", sa.String(64), nullable=False, server_default=sa.text("''")),
        sa.Column("mime_type", sa.String(64), nullable=False, server_default=sa.text("''")),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "verification_status", sa.String(16), nullable=False, server_default="unverified"
        ),
        sa.Column(
            "reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "kind IN ('general','before','after','document','field_note')",
            name="ck_action_evidence_kind",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified','pending','approved','rejected')",
            name="ck_action_evidence_verification_status",
        ),
    )
    op.create_index("ix_action_evidence_initiative_id", "action_evidence", ["initiative_id"])
    op.create_index("ix_action_evidence_task_id", "action_evidence", ["task_id"])
    op.create_index("ix_action_evidence_media_id", "action_evidence", ["media_id"])
    op.create_index(
        "ix_action_evidence_initiative_task", "action_evidence", ["initiative_id", "task_id"]
    )

    op.create_table(
        "action_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "evidence_ids",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "decision IN ('pending','approved','rejected')", name="ck_action_reviews_decision"
        ),
        sa.CheckConstraint("entity_type IN ('initiative','task')", name="ck_action_reviews_entity"),
    )
    op.create_index("ix_action_reviews_entity_id", "action_reviews", ["entity_id"])

    op.create_table(
        "impact_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("action_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("baseline", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("target", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
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
    op.create_index("ix_impact_metrics_plan_id", "impact_metrics", ["plan_id"])

    op.create_table(
        "impact_measurements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "metric_id",
            sa.Uuid(),
            sa.ForeignKey("impact_metrics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("methodology_note", sa.Text(), nullable=True),
        sa.Column(
            "evidence_id",
            sa.Uuid(),
            sa.ForeignKey("action_evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_impact_measurements_status"
        ),
    )
    op.create_index("ix_impact_measurements_metric_id", "impact_measurements", ["metric_id"])

    op.create_table(
        "civic_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id",
            sa.Uuid(),
            sa.ForeignKey("civic_initiatives.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "location",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "organizer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column(
            "requirements",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("safety_info", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
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
            "status IN ('draft','submitted','published','cancelled','completed')",
            name="ck_civic_events_status",
        ),
    )
    op.create_index("ix_civic_events_initiative_id", "civic_events", ["initiative_id"])

    op.create_table(
        "event_participants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Uuid(),
            sa.ForeignKey("civic_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="joined"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_participants"),
        sa.CheckConstraint(
            "status IN ('joined','attended','cancelled')", name="ck_event_participants_status"
        ),
    )
    op.create_index("ix_event_participants_event_id", "event_participants", ["event_id"])

    op.create_table(
        "campaign_initiatives",
        sa.Column(
            "campaign_id",
            sa.Uuid(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "initiative_id",
            sa.Uuid(),
            sa.ForeignKey("civic_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "campaign_members",
        sa.Column(
            "campaign_id",
            sa.Uuid(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("role IN ('member','organizer')", name="ck_campaign_members_role"),
    )

    # -- notification template seeds (hi/en) ----------------------------------
    templates = sa.table(
        "notification_templates",
        sa.column("id", sa.Uuid()),
        sa.column("event", sa.String()),
        sa.column("channel", sa.String()),
        sa.column("locale", sa.String()),
        sa.column("subject_key", sa.Text()),
        sa.column("body_text", sa.Text()),
        sa.column("created_at", sa.DateTime()),
    )
    for event, channel, locale, subject, body in _TEMPLATES:
        op.execute(
            templates.insert().from_select(
                ["id", "event", "channel", "locale", "subject_key", "body_text", "created_at"],
                sa.select(
                    sa.func.gen_random_uuid(),
                    sa.literal(event),
                    sa.literal(channel),
                    sa.literal(locale),
                    sa.literal(subject),
                    sa.literal(body),
                    sa.func.now(),
                ).where(
                    ~sa.exists(
                        sa.select(sa.literal(1)).where(
                            templates.c.event == event,
                            templates.c.channel == channel,
                            templates.c.locale == locale,
                        )
                    )
                ),
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM notification_templates WHERE event LIKE 'civic_action.%'"))
    op.drop_table("campaign_members")
    op.drop_table("campaign_initiatives")
    op.drop_table("event_participants")
    op.drop_table("civic_events")
    op.drop_table("impact_measurements")
    op.drop_table("impact_metrics")
    op.drop_table("action_reviews")
    op.drop_table("action_evidence")
    op.drop_table("volunteer_applications")
    op.drop_table("civic_team_members")
    op.drop_table("civic_teams")
    op.drop_table("action_updates")
    op.drop_table("task_comments")
    op.drop_table("action_dependencies")
    op.drop_table("action_milestones")
    op.drop_table("action_tasks")
    op.drop_table("action_plans")
