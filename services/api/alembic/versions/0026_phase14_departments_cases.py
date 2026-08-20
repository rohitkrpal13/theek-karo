"""Phase 14 government & department response platform: departments,
jurisdictions, civic cases, SLA, escalation and the resolution workflow.

New tables: department_types, departments, department_categories,
jurisdiction_scopes, organization_verifications, department_users, cases,
case_status_history, case_assignments, case_actions, case_responses,
case_reopen_requests, sla_policies, sla_instances, sla_pauses,
escalation_rules, case_escalations, resolution_reviews.

Extended: resolution_submissions (case_id, explanation, resolution_date,
reference_numbers, status CHECK), resolution_evidence (version_no,
document_kind, before_after, captured_at, checksum, visibility).

Seeds: role codes (department_manager, reviewer), 19 new permission codes +
role-permission mapping, generic escalation rules, case/SLA notification
templates (en/hi).

Revision ID: 0026_phase14_departments_cases
Revises: 0025_phase13_community
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_phase14_departments_cases"
down_revision: str | None = "0025_phase13_community"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CASE_STATUSES = (
    "submitted",
    "under_review",
    "needs_information",
    "verified",
    "assigned",
    "acknowledged",
    "action_planned",
    "in_progress",
    "waiting_for_information",
    "resolution_submitted",
    "resolution_under_review",
    "resolution_rejected",
    "partially_resolved",
    "resolved",
    "closed",
    "reopened",
    "rejected",
    "duplicate",
)

_DEPARTMENT_TYPES = [
    ("government_department", "department.type.government_department"),
    ("municipal_corporation", "department.type.municipal_corporation"),
    ("police", "department.type.police"),
    ("education", "department.type.education"),
    ("health", "department.type.health"),
    ("public_works", "department.type.public_works"),
    ("water_sanitation", "department.type.water_sanitation"),
    ("transport", "department.type.transport"),
    ("electricity", "department.type.electricity"),
    ("rural_development", "department.type.rural_development"),
]

# 19 new permission codes
_PERMISSIONS = [
    "departments.read",
    "departments.manage",
    "departments.jurisdiction.manage",
    "departments.members.manage",
    "departments.verify_org",
    "cases.create",
    "cases.read",
    "cases.read_internal",
    "cases.manage",
    "cases.assign",
    "cases.acknowledge",
    "cases.respond",
    "cases.actions.manage",
    "cases.reopen.request",
    "cases.escalate",
    "sla.read",
    "sla.manage",
    "escalation.manage",
    "analytics.department",
]

# role -> added permissions (existing roles only get additions; new roles get full sets)
_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "citizen": ["departments.read"],
    "volunteer": ["departments.read", "cases.read"],
    "verified_contributor": ["departments.read", "cases.read"],
    "moderator": [
        "departments.read",
        "cases.create",
        "cases.read",
        "cases.read_internal",
        "cases.reopen.request",
        "sla.read",
    ],
    "institution_representative": [
        "departments.read",
        "cases.create",
        "cases.read",
        "cases.respond",
        "sla.read",
    ],
    "department_representative": [
        "departments.read",
        "cases.create",
        "cases.read",
        "cases.read_internal",
        "cases.acknowledge",
        "cases.respond",
        "cases.actions.manage",
        "cases.reopen.request",
        "cases.escalate",
        "sla.read",
    ],
    "department_manager": [
        "departments.read",
        "departments.members.manage",
        "cases.create",
        "cases.read",
        "cases.read_internal",
        "cases.assign",
        "cases.acknowledge",
        "cases.respond",
        "cases.actions.manage",
        "cases.reopen.request",
        "cases.escalate",
        "sla.read",
        "analytics.department",
        "reports.read_public",
        "reports.read_private",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "reports.reopen",
        "institutions.read",
        "institutions.update",
        "institutions.twin.update",
        "comments.create",
        "resolution.submit",
        "analytics.read",
        "analytics.advanced",
        "government_data.read",
        "government_data.import",
        "ai.use",
    ],
    "reviewer": [
        "departments.read",
        "cases.read",
        "cases.read_internal",
        "cases.reopen.request",
        "resolution.review",
        "resolution.verify",
        "sla.read",
        "analytics.read",
        "analytics.department",
        "ai.use",
        "reports.read_public",
        "reports.read_private",
        "institutions.read",
        "government_data.read",
    ],
    "analyst": [
        "departments.read",
        "sla.read",
        "analytics.department",
    ],
    "admin": [
        "departments.read",
        "departments.manage",
        "departments.jurisdiction.manage",
        "departments.members.manage",
        "departments.verify_org",
        "cases.create",
        "cases.read",
        "cases.read_internal",
        "cases.manage",
        "cases.assign",
        "cases.acknowledge",
        "cases.respond",
        "cases.actions.manage",
        "cases.reopen.request",
        "cases.escalate",
        "sla.read",
        "sla.manage",
        "escalation.manage",
        "analytics.department",
        "resolution.review",
        "resolution.verify",
    ],
}

_TEMPLATES = [
    ("case.assigned", "in_app", "en", "Your report {ticket_no} was assigned to {department_name}"),
    ("case.assigned", "in_app", "hi", "आपकी रिपोर्ट {ticket_no} {department_name} को सौंपी गई"),
    ("case.assigned", "sms", "en", "TK: {ticket_no} assigned to {department_name}"),
    ("case.assigned", "sms", "hi", "TK: {ticket_no} {department_name} को सौंपी गई"),
    ("case.assigned", "email", "en", "Your report {ticket_no} was assigned to {department_name}"),
    ("case.assigned", "email", "hi", "आपकी रिपोर्ट {ticket_no} {department_name} को सौंपी गई"),
    ("case.status_change", "in_app", "en", "Your report {ticket_no} is now {status_label}"),
    ("case.status_change", "in_app", "hi", "आपकी रिपोर्ट {ticket_no} अब {status_label} है"),
    ("case.status_change", "sms", "en", "TK: {ticket_no} is now {status_label}"),
    ("case.status_change", "sms", "hi", "TK: {ticket_no} अब {status_label} है"),
    ("case.status_change", "email", "en", "Status update on {ticket_no}: {status_label}"),
    ("case.status_change", "email", "hi", "{ticket_no} पर स्थिति अद्यतन: {status_label}"),
    ("case.response", "in_app", "en", "A department response was posted on {ticket_no}"),
    ("case.response", "in_app", "hi", "{ticket_no} पर विभाग की प्रतिक्रिया पोस्ट की गई"),
    ("case.response", "sms", "en", "TK: department responded on {ticket_no}"),
    ("case.response", "sms", "hi", "TK: {ticket_no} पर विभाग ने प्रतिक्रिया दी"),
    ("case.response", "email", "en", "Department response on {ticket_no}"),
    ("case.response", "email", "hi", "{ticket_no} पर विभाग की प्रतिक्रिया"),
    (
        "case.resolution_submitted",
        "in_app",
        "en",
        "Resolution evidence was submitted for {ticket_no}",
    ),
    ("case.resolution_submitted", "in_app", "hi", "{ticket_no} के लिए समाधान साक्ष्य प्रस्तुत किया गया"),
    ("case.resolution_submitted", "sms", "en", "TK: resolution submitted for {ticket_no}"),
    ("case.resolution_submitted", "sms", "hi", "TK: {ticket_no} के लिए समाधान प्रस्तुत"),
    ("case.resolution_submitted", "email", "en", "Resolution submitted for {ticket_no}"),
    ("case.resolution_submitted", "email", "hi", "{ticket_no} के लिए समाधान प्रस्तुत"),
    (
        "case.resolution_reviewed",
        "in_app",
        "en",
        "Resolution review for {ticket_no}: {outcome_label}",
    ),
    ("case.resolution_reviewed", "in_app", "hi", "{ticket_no} की समाधान समीक्षा: {outcome_label}"),
    (
        "case.resolution_reviewed",
        "sms",
        "en",
        "TK: resolution review {outcome_label} for {ticket_no}",
    ),
    ("case.resolution_reviewed", "sms", "hi", "TK: {ticket_no} की समाधान समीक्षा {outcome_label}"),
    (
        "case.resolution_reviewed",
        "email",
        "en",
        "Resolution review for {ticket_no}: {outcome_label}",
    ),
    ("case.resolution_reviewed", "email", "hi", "{ticket_no} की समाधान समीक्षा: {outcome_label}"),
    ("case.reopened", "in_app", "en", "Your report {ticket_no} was reopened"),
    ("case.reopened", "in_app", "hi", "आपकी रिपोर्ट {ticket_no} फिर खोली गई"),
    ("case.reopened", "sms", "en", "TK: {ticket_no} was reopened"),
    ("case.reopened", "sms", "hi", "TK: {ticket_no} फिर खोली गई"),
    ("case.reopened", "email", "en", "Your report {ticket_no} was reopened"),
    ("case.reopened", "email", "hi", "आपकी रिपोर्ट {ticket_no} फिर खोली गई"),
    ("case.escalated", "in_app", "en", "Case {case_no} was escalated to level {level}"),
    ("case.escalated", "in_app", "hi", "केस {case_no} स्तर {level} पर भेजा गया"),
    ("case.escalated", "sms", "en", "TK: case {case_no} escalated to level {level}"),
    ("case.escalated", "sms", "hi", "TK: केस {case_no} स्तर {level} पर"),
    ("case.escalated", "email", "en", "Case {case_no} escalated to level {level}"),
    ("case.escalated", "email", "hi", "केस {case_no} स्तर {level} पर भेजा गया"),
    ("sla.at_risk", "in_app", "en", "Case {case_no} is approaching its SLA deadline"),
    ("sla.at_risk", "in_app", "hi", "केस {case_no} की SLA समय सीमा निकट है"),
    ("sla.at_risk", "sms", "en", "TK: case {case_no} SLA at risk"),
    ("sla.at_risk", "sms", "hi", "TK: केस {case_no} SLA जोखिम में"),
    ("sla.at_risk", "email", "en", "SLA at risk for case {case_no}"),
    ("sla.at_risk", "email", "hi", "केस {case_no} की SLA जोखिम में"),
    ("sla.breached", "in_app", "en", "Case {case_no} exceeded its SLA deadline"),
    ("sla.breached", "in_app", "hi", "केस {case_no} की SLA समय सीमा समाप्त"),
    ("sla.breached", "sms", "en", "TK: case {case_no} SLA breached"),
    ("sla.breached", "sms", "hi", "TK: केस {case_no} SLA उल्लंघन"),
    ("sla.breached", "email", "en", "SLA breached for case {case_no}"),
    ("sla.breached", "email", "hi", "केस {case_no} की SLA उल्लंघन"),
    ("case.reopen_requested", "in_app", "en", "A reopen request was filed for {ticket_no}"),
    ("case.reopen_requested", "in_app", "hi", "{ticket_no} के लिए पुनर्खोल अनुरोध दायर किया गया"),
]

_ESCALATION_RULES = [
    ("sla-at-risk-l1", "sla_at_risk", 1, "department_manager"),
    ("sla-breached-l2", "sla_breached", 2, "reviewer"),
    ("sla-breached-l3", "sla_breached", 3, "admin"),
]


def upgrade() -> None:
    # -- department registry -----------------------------------------------------
    op.create_table(
        "department_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_department_types_code"),
    )

    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "department_type_id",
            sa.Uuid(),
            sa.ForeignKey("department_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_department_id",
            sa.Uuid(),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "jurisdiction_geography_id",
            sa.Uuid(),
            sa.ForeignKey("geographies.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("official_contact", sa.Text(), nullable=True),
        sa.Column("official_email", sa.Text(), nullable=True),
        sa.Column("official_phone", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_departments_slug"),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'suspended')", name="ck_departments_status"
        ),
    )
    op.create_index(op.f("ix_departments_type"), "departments", ["department_type_id"])
    op.create_index(op.f("ix_departments_parent"), "departments", ["parent_department_id"])
    op.create_index(
        op.f("ix_departments_jurisdiction"), "departments", ["jurisdiction_geography_id"]
    )

    op.create_table(
        "department_categories",
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("department_id", "category_id", name="pk_department_categories"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "jurisdiction_scopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("institution_type_id", sa.Uuid(), nullable=True),
        sa.Column(
            "scope_kind",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'full'"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["institution_type_id"], ["institution_types.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "scope_kind IN ('full', 'geography', 'institution')",
            name="ck_jurisdiction_scopes_kind",
        ),
    )
    op.create_index(op.f("ix_jurisdiction_scopes_dept"), "jurisdiction_scopes", ["department_id"])

    # -- organization verification + department members --------------------------
    op.create_table(
        "organization_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_name", sa.Text(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column(
            "verification_state",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("submitted_email", sa.Text(), nullable=True),
        sa.Column("submitted_reason", sa.Text(), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "verification_state IN ('pending', 'verified', 'suspended', 'revoked')",
            name="ck_organization_verifications_state",
        ),
    )
    op.create_index(
        op.f("ix_organization_verifications_user"), "organization_verifications", ["user_id"]
    )

    op.create_table(
        "department_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role_in_department",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'member'"),
        ),
        sa.Column("scope_geography_id", sa.Uuid(), nullable=True),
        sa.Column("verification_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["verification_id"], ["organization_verifications.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("user_id", "department_id", name="uq_department_users_membership"),
        sa.CheckConstraint(
            "role_in_department IN ('member', 'manager', 'reviewer')",
            name="ck_department_users_role",
        ),
    )
    op.create_index(op.f("ix_department_users_department"), "department_users", ["department_id"])

    # -- civic cases ------------------------------------------------------------
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("issue_type_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("response_hours", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("resolution_hours", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "at_risk_pct",
            sa.Numeric(precision=5, scale=4),
            nullable=False,
            server_default=sa.text("'0.8000'"),
        ),
        sa.Column(
            "evidence_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_sla_policies_code"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issue_type_id"], ["issue_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_sla_policies_severity",
        ),
    )

    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_no", sa.Text(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'submitted'"),
        ),
        sa.Column("primary_department_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_geography_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column(
            "priority", sa.String(length=16), nullable=False, server_default=sa.text("'medium'")
        ),
        sa.Column("sla_policy_id", sa.Uuid(), nullable=True),
        sa.Column("sla_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sla_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'not_started'"),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_no", name="uq_cases_case_no"),
        sa.UniqueConstraint("report_id", name="uq_cases_report_id"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sla_policy_id"], ["sla_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('submitted', 'under_review', 'needs_information', 'verified', "
            "'assigned', 'acknowledged', 'action_planned', 'in_progress', "
            "'waiting_for_information', 'resolution_submitted', 'resolution_under_review', "
            "'resolution_rejected', 'partially_resolved', 'resolved', 'closed', 'reopened', "
            "'rejected', 'duplicate')",
            name="ck_cases_status",
        ),
        sa.CheckConstraint(
            "sla_status IN ('not_started', 'within_sla', 'at_risk', 'breached', "
            "'paused', 'exempt')",
            name="ck_cases_sla_status",
        ),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_cases_severity",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')", name="ck_cases_priority"
        ),
    )
    op.create_index(op.f("ix_cases_report"), "cases", ["report_id"])
    op.create_index(
        op.f("ix_cases_department_status"), "cases", ["primary_department_id", "status"]
    )
    op.create_index(op.f("ix_cases_sla_status"), "cases", ["sla_status"])

    op.create_table(
        "case_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_case_status_history_case"), "case_status_history", ["case_id"])

    op.create_table(
        "case_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("queue", sa.Text(), nullable=True),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("previous_department_id", sa.Uuid(), nullable=True),
        sa.Column("previous_geography_id", sa.Uuid(), nullable=True),
        sa.Column("previous_queue", sa.Text(), nullable=True),
        sa.Column("previous_assignee_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["previous_department_id"], ["departments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["previous_assignee_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_case_assignments_case"), "case_assignments", ["case_id"])
    op.create_index(
        op.f("ix_case_assignments_current"), "case_assignments", ["case_id", "is_current"]
    )

    op.create_table(
        "case_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("responsible_team", sa.Text(), nullable=True),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'planned'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled', 'blocked')",
            name="ck_case_actions_status",
        ),
    )
    op.create_index(op.f("ix_case_actions_case"), "case_actions", ["case_id"])

    op.create_table(
        "case_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "visibility", sa.String(length=16), nullable=False, server_default=sa.text("'public'")
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "kind IN ('acknowledgement', 'public_response', 'internal_note', 'progress_update')",
            name="ck_case_responses_kind",
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'internal')", name="ck_case_responses_visibility"
        ),
    )
    op.create_index(op.f("ix_case_responses_case"), "case_responses", ["case_id"])

    op.create_table(
        "case_reopen_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_case_reopen_requests_status"
        ),
    )
    op.create_index(op.f("ix_case_reopen_requests_case"), "case_reopen_requests", ["case_id"])

    # -- SLA --------------------------------------------------------------------
    op.create_table(
        "sla_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_resolution_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_seconds", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default=sa.text("'not_started'")
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("breached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_sla_instances_case"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["sla_policies.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('not_started', 'within_sla', 'at_risk', 'breached', 'paused', 'exempt')",
            name="ck_sla_instances_status",
        ),
    )

    op.create_table(
        "sla_pauses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sla_instance_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("paused_by", sa.Uuid(), nullable=True),
        sa.Column("expected_resume_condition", sa.Text(), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sla_instance_id"], ["sla_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paused_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_sla_pauses_instance"), "sla_pauses", ["sla_instance_id"])

    # -- escalation -------------------------------------------------------------
    op.create_table(
        "escalation_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("threshold_type", sa.String(length=16), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column(
            "target_role",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_escalation_rules_code"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "threshold_type IN ('sla_at_risk', 'sla_breached', 'manual')",
            name="ck_escalation_rules_threshold",
        ),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_escalation_rules_severity",
        ),
    )

    op.create_table(
        "case_escalations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("previous_level", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("escalated_by", sa.Uuid(), nullable=True),
        sa.Column("escalated_by_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["escalated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('active', 'resolved', 'dismissed')", name="ck_case_escalations_status"
        ),
        sa.UniqueConstraint("case_id", "level", "status", name="uq_case_escalations_level"),
    )
    op.create_index(op.f("ix_case_escalations_case"), "case_escalations", ["case_id"])

    # -- resolution extensions + reviews ----------------------------------------
    op.add_column(
        "resolution_submissions",
        sa.Column("case_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_resolution_submissions_case",
        "resolution_submissions",
        "cases",
        ["case_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_resolution_submissions_case"), "resolution_submissions", ["case_id"])
    op.add_column(
        "resolution_submissions",
        sa.Column("explanation", sa.Text(), nullable=True),
    )
    op.add_column(
        "resolution_submissions",
        sa.Column("resolution_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "resolution_submissions",
        sa.Column("reference_numbers", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.drop_constraint("ck_resolution_submissions_status", "resolution_submissions", type_="check")
    op.create_check_constraint(
        "ck_resolution_submissions_status",
        "resolution_submissions",
        (
            "status IN ('submitted', 'under_review', 'approved', 'verified', 'rejected', "
            "'more_evidence_required', 'partially_verified', 'disputed')"
        ),
    )

    op.add_column(
        "resolution_evidence",
        sa.Column("version_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("resolution_evidence", sa.Column("document_kind", sa.Text(), nullable=True))
    op.add_column(
        "resolution_evidence", sa.Column("before_after", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "resolution_evidence", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("resolution_evidence", sa.Column("checksum", sa.Text(), nullable=True))
    op.add_column(
        "resolution_evidence",
        sa.Column(
            "visibility", sa.String(length=16), nullable=False, server_default=sa.text("'public'")
        ),
    )
    op.create_check_constraint(
        "ck_resolution_evidence_before_after",
        "resolution_evidence",
        "before_after IS NULL OR before_after IN ('before', 'after', 'neutral')",
    )
    op.create_check_constraint(
        "ck_resolution_evidence_visibility",
        "resolution_evidence",
        "visibility IN ('public', 'internal')",
    )

    op.create_table(
        "resolution_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resolution_submission_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ai_assessment", sa.JSON(), nullable=True),
        sa.Column("conflict_of_interest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["resolution_submission_id"], ["resolution_submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "decision IN ('verified', 'more_evidence_required', 'rejected', 'partially_verified')",
            name="ck_resolution_reviews_decision",
        ),
    )
    op.create_index(
        op.f("ix_resolution_reviews_submission"), "resolution_reviews", ["resolution_submission_id"]
    )

    # -- seeds -------------------------------------------------------------------
    import uuid
    from datetime import UTC, datetime

    conn = op.get_bind()
    now = datetime.now(UTC)

    # department types
    existing_types = {
        row[0] for row in conn.execute(sa.text("SELECT code FROM department_types")).fetchall()
    }
    for code, name_key in _DEPARTMENT_TYPES:
        if code not in existing_types:
            conn.execute(
                sa.text(
                    "INSERT INTO department_types (id, code, name_key, is_active, created_at) "
                    "VALUES (:id, :code, :name_key, TRUE, :created_at)"
                ),
                {"id": uuid.uuid4(), "code": code, "name_key": name_key, "created_at": now},
            )

    # roles
    existing_roles = {
        row[0]: row[1] for row in conn.execute(sa.text("SELECT code, id FROM roles")).fetchall()
    }
    for code in ("department_manager", "reviewer"):
        if code not in existing_roles:
            role_id = uuid.uuid4()
            conn.execute(
                sa.text("INSERT INTO roles (id, code, name) VALUES (:id, :code, :name)"),
                {"id": role_id, "code": code, "name": code.replace("_", " ").title()},
            )
            existing_roles[code] = role_id

    # permissions + role mapping
    existing_permissions = {
        row[0]: row[1]
        for row in conn.execute(sa.text("SELECT code, id FROM permissions")).fetchall()
    }
    for code in _PERMISSIONS:
        if code not in existing_permissions:
            perm_id = uuid.uuid4()
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, description, created_at) "
                    "VALUES (:id, :code, :desc, :created_at)"
                ),
                {"id": perm_id, "code": code, "desc": code, "created_at": now},
            )
            existing_permissions[code] = perm_id

    existing_rp = {
        (row[0], row[1])
        for row in conn.execute(
            sa.text("SELECT role_id, permission_id FROM role_permissions")
        ).fetchall()
    }
    for role_code, perm_codes in _ROLE_PERMISSIONS.items():
        role_id = existing_roles.get(role_code)
        if not role_id:
            continue
        for perm_code in perm_codes:
            perm_id = existing_permissions.get(perm_code)
            if not perm_id:
                continue
            if (role_id, perm_id) not in existing_rp:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id, granted_at) "
                        "VALUES (:role_id, :permission_id, :granted_at)"
                    ),
                    {"role_id": role_id, "permission_id": perm_id, "granted_at": now},
                )
                existing_rp.add((role_id, perm_id))

    # escalation rules
    existing_rules = {
        row[0] for row in conn.execute(sa.text("SELECT code FROM escalation_rules")).fetchall()
    }
    for code, threshold, level, target_role in _ESCALATION_RULES:
        if code not in existing_rules:
            conn.execute(
                sa.text(
                    "INSERT INTO escalation_rules "
                    "(id, code, threshold_type, level, target_role, message, is_active, "
                    "priority_order, created_at, updated_at) "
                    "VALUES (:id, :code, :threshold_type, :level, :target_role, NULL, TRUE, "
                    ":priority_order, :created_at, :updated_at)"
                ),
                {
                    "id": uuid.uuid4(),
                    "code": code,
                    "threshold_type": threshold,
                    "level": level,
                    "target_role": target_role,
                    "priority_order": level * 10,
                    "created_at": now,
                    "updated_at": now,
                },
            )

    # notification templates
    existing_templates = {
        (row[0], row[1], row[2])
        for row in conn.execute(
            sa.text("SELECT event, channel, locale FROM notification_templates")
        ).fetchall()
    }
    for event, channel, locale, body in _TEMPLATES:
        if (event, channel, locale) not in existing_templates:
            conn.execute(
                sa.text(
                    "INSERT INTO notification_templates "
                    "(id, event, channel, locale, subject_key, body_text, created_at) "
                    "VALUES (:id, :event, :channel, :locale, :subject_key, :body_text, :created_at)"
                ),
                {
                    "id": uuid.uuid4(),
                    "event": event,
                    "channel": channel,
                    "locale": locale,
                    "subject_key": f"notify.{event}",
                    "body_text": body,
                    "created_at": now,
                },
            )


def downgrade() -> None:
    op.drop_table("resolution_reviews")
    op.drop_constraint("ck_resolution_evidence_visibility", "resolution_evidence", type_="check")
    op.drop_constraint("ck_resolution_evidence_before_after", "resolution_evidence", type_="check")
    op.drop_column("resolution_evidence", "visibility")
    op.drop_column("resolution_evidence", "checksum")
    op.drop_column("resolution_evidence", "captured_at")
    op.drop_column("resolution_evidence", "before_after")
    op.drop_column("resolution_evidence", "document_kind")
    op.drop_column("resolution_evidence", "version_no")
    op.drop_constraint("ck_resolution_submissions_status", "resolution_submissions", type_="check")
    op.create_check_constraint(
        "ck_resolution_submissions_status",
        "resolution_submissions",
        "status IN ('submitted', 'under_review', 'approved', 'rejected', 'disputed')",
    )
    op.drop_column("resolution_submissions", "reference_numbers")
    op.drop_column("resolution_submissions", "resolution_date")
    op.drop_column("resolution_submissions", "explanation")
    op.drop_index(op.f("ix_resolution_submissions_case"), table_name="resolution_submissions")
    op.drop_constraint(
        "fk_resolution_submissions_case", "resolution_submissions", type_="foreignkey"
    )
    op.drop_column("resolution_submissions", "case_id")
    op.drop_table("case_escalations")
    op.drop_table("escalation_rules")
    op.drop_table("sla_pauses")
    op.drop_table("sla_instances")
    op.drop_table("case_reopen_requests")
    op.drop_table("case_responses")
    op.drop_table("case_actions")
    op.drop_table("case_assignments")
    op.drop_table("case_status_history")
    op.drop_table("cases")
    op.drop_table("sla_policies")
    op.drop_table("department_users")
    op.drop_table("organization_verifications")
    op.drop_table("jurisdiction_scopes")
    op.drop_table("department_categories")
    op.drop_table("departments")
    op.drop_table("department_types")
