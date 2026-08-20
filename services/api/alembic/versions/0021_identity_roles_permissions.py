"""Identity expansion: seed complete roles, permissions, role-permission mappings,
and add user profile columns (PRD §14, SECURITY.md §2-§4).

Revision ID: 0021_identity_roles_permissions
Revises: 0020_fix_versioning_uniques
Create Date: 2026-08-16

"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0021_identity_roles_permissions"
down_revision: str | None = "0020_fix_versioning_uniques"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 9 Standard Roles
_ROLES = [
    ("citizen", "Citizen"),
    ("volunteer", "Civic Volunteer"),
    ("verified_contributor", "Verified Contributor"),
    ("moderator", "Community Moderator"),
    ("institution_representative", "Institution Representative"),
    ("department_representative", "Department Representative"),
    ("analyst", "Civic Data Analyst"),
    ("admin", "System Administrator"),
    ("super_admin", "Super Administrator"),
]

# Comprehensive Fine-Grained Permissions
_PERMISSIONS = [
    # Identity & Profile
    ("identity.read_self", "Read own profile and active sessions"),
    ("identity.update_self", "Update own profile settings and preferences"),
    ("identity.delete_self", "Request own account anonymization/deletion"),
    ("audit.read_self", "Read own audit trail"),
    ("users.read", "Read public/administrative user records"),
    ("users.manage", "Manage user account status"),
    ("users.roles.manage", "Grant and revoke user roles"),
    ("permission.manage", "Configure role permissions"),
    # Reports & Issues
    ("reports.create", "Create civic reports"),
    ("reports.read_public", "Read public civic reports"),
    ("reports.read_private", "Read non-public or sensitive reports"),
    ("reports.update_own", "Update own submitted reports"),
    ("reports.delete_own", "Delete/withdraw own submitted reports"),
    ("reports.verify", "Vote verify/refute on reports"),
    ("reports.moderate", "Quarantine, hide, or moderate reports"),
    ("reports.assign", "Assign reports to institutions or departments"),
    ("reports.transition", "Transition report lifecycle status"),
    ("reports.resolve", "Submit or verify report resolution"),
    ("reports.reopen", "Reopen unresolved or recurring reports"),
    # Public Institutions & Digital Twins
    ("institutions.read", "Read public institutions"),
    ("institutions.create", "Create new institution records"),
    ("institutions.update", "Update public institution metadata"),
    ("institutions.twin.update", "Update institution digital twin operational state"),
    ("institutions.verify", "Verify institutional claims and data"),
    # Comments & Community
    ("comments.create", "Post comments on public reports"),
    ("comments.moderate", "Moderate or remove abusive comments"),
    # Resolution & Proof
    ("resolution.submit", "Submit resolution proof with evidence"),
    ("resolution.review", "Review and approve/reject resolution proof"),
    ("resolution.verify", "Community verify resolution"),
    # Government Data & Datasets
    ("government_data.read", "Read government dataset catalog"),
    ("government_data.import", "Import public government datasets"),
    ("government_data.manage", "Manage government data pipelines"),
    # Analytics
    ("analytics.read", "Read public and regional civic analytics"),
    ("analytics.advanced", "Access advanced breakdown and forecasting analytics"),
    ("analytics.export", "Export raw analytics datasets"),
    # AI & Automated Tools
    ("ai.use", "Use AI assistant and civic analysis tools"),
    ("ai.admin", "Configure AI models, prompts, and evaluation rules"),
    # System & Governance
    ("system.manage", "Full system administration and health management"),
    ("administration.configure", "Configure civic categories, schemas, and geography"),
    ("administration.institutions", "Manage institution directory and verifications"),
    ("audit.read_all", "Read system-wide security and operational audit logs"),
]

# Role to Permissions Mapping matrix
_ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "citizen": [
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
        "reports.create",
        "reports.read_public",
        "reports.update_own",
        "reports.delete_own",
        "reports.verify",
        "institutions.read",
        "comments.create",
        "resolution.verify",
        "government_data.read",
        "analytics.read",
        "ai.use",
    ],
    "volunteer": [
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
        "reports.create",
        "reports.read_public",
        "reports.update_own",
        "reports.delete_own",
        "reports.verify",
        "reports.transition",
        "institutions.read",
        "comments.create",
        "resolution.verify",
        "government_data.read",
        "analytics.read",
        "ai.use",
    ],
    "verified_contributor": [
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
        "reports.create",
        "reports.read_public",
        "reports.update_own",
        "reports.delete_own",
        "reports.verify",
        "reports.transition",
        "institutions.read",
        "comments.create",
        "resolution.verify",
        "government_data.read",
        "analytics.read",
        "analytics.export",
        "ai.use",
    ],
    "moderator": [
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "reports.read_private",
        "reports.moderate",
        "reports.verify",
        "reports.transition",
        "institutions.read",
        "comments.create",
        "comments.moderate",
        "analytics.read",
        "ai.use",
    ],
    "institution_representative": [
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "institutions.read",
        "institutions.update",
        "institutions.twin.update",
        "comments.create",
        "resolution.submit",
        "analytics.read",
        "ai.use",
    ],
    "department_representative": [
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
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
    "analyst": [
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "institutions.read",
        "government_data.read",
        "government_data.import",
        "analytics.read",
        "analytics.advanced",
        "analytics.export",
        "ai.use",
    ],
    "admin": [
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "audit.read_all",
        "users.read",
        "users.manage",
        "users.roles.manage",
        "reports.create",
        "reports.read_public",
        "reports.read_private",
        "reports.update_own",
        "reports.delete_own",
        "reports.moderate",
        "reports.verify",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "reports.reopen",
        "institutions.read",
        "institutions.create",
        "institutions.update",
        "institutions.twin.update",
        "institutions.verify",
        "comments.create",
        "comments.moderate",
        "resolution.submit",
        "resolution.review",
        "resolution.verify",
        "government_data.read",
        "government_data.import",
        "government_data.manage",
        "analytics.read",
        "analytics.advanced",
        "analytics.export",
        "ai.use",
        "ai.admin",
        "administration.configure",
        "administration.institutions",
        "system.manage",
    ],
    "super_admin": [
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
        "audit.read_all",
        "users.read",
        "users.manage",
        "users.roles.manage",
        "permission.manage",
        "reports.create",
        "reports.read_public",
        "reports.read_private",
        "reports.update_own",
        "reports.delete_own",
        "reports.moderate",
        "reports.verify",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "reports.reopen",
        "institutions.read",
        "institutions.create",
        "institutions.update",
        "institutions.twin.update",
        "institutions.verify",
        "comments.create",
        "comments.moderate",
        "resolution.submit",
        "resolution.review",
        "resolution.verify",
        "government_data.read",
        "government_data.import",
        "government_data.manage",
        "analytics.read",
        "analytics.advanced",
        "analytics.export",
        "ai.use",
        "ai.admin",
        "administration.configure",
        "administration.institutions",
        "system.manage",
    ],
}


def upgrade() -> None:
    # 1. Add user profile expansion columns
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("bio", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("profile_image_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("location_pref", sa.Text(), nullable=True))
        batch_op.create_unique_constraint("uq_users_username", ["username"])
        batch_op.create_index("ix_users_username", ["username"])

    # 2. Seed all 9 roles safely (insert ignore or lookup)
    conn = op.get_bind()
    existing_roles = {
        row[0]: row[1] for row in conn.execute(sa.text("SELECT code, id FROM roles")).fetchall()
    }
    now = datetime.now(UTC)

    for code, name in _ROLES:
        if code not in existing_roles:
            role_id = uuid.uuid4()
            conn.execute(
                sa.text("INSERT INTO roles (id, code, name) VALUES (:id, :code, :name)"),
                {"id": role_id, "code": code, "name": name},
            )
            existing_roles[code] = role_id

    # 3. Seed all permissions
    existing_permissions = {
        row[0]: row[1]
        for row in conn.execute(sa.text("SELECT code, id FROM permissions")).fetchall()
    }

    for code, desc in _PERMISSIONS:
        if code not in existing_permissions:
            perm_id = uuid.uuid4()
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, description, created_at) "
                    "VALUES (:id, :code, :desc, :created_at)"
                ),
                {"id": perm_id, "code": code, "desc": desc, "created_at": now},
            )
            existing_permissions[code] = perm_id

    # 4. Map roles to permissions in role_permissions
    existing_rp = {
        (row[0], row[1])
        for row in conn.execute(
            sa.text("SELECT role_id, permission_id FROM role_permissions")
        ).fetchall()
    }

    for role_code, perm_codes in _ROLE_PERMISSION_MAP.items():
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


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_username")
        batch_op.drop_constraint("uq_users_username", type_="unique")
        batch_op.drop_column("location_pref")
        batch_op.drop_column("profile_image_url")
        batch_op.drop_column("bio")
        batch_op.drop_column("username")
