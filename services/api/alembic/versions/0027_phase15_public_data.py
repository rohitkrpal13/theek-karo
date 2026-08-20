"""Phase 15 public data, transparency and research layer (ADR-052).

New tables: public_datasets, public_dataset_versions, public_dataset_lineage,
data_correction_requests, public_api_keys, public_api_usage, data_export_jobs,
saved_research_queries.

Seeds: the curated public-data catalog (civic_reports, verified_reports, cases,
resolutions, institutions, official_data, geography datasets), dataset versions
and lineage steps for the derived datasets.

Revision ID: 0027_phase15_public_data
Revises: 0026_phase14_departments_cases
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_phase15_public_data"
down_revision: str | None = "0026_phase14_departments_cases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATASET_SEEDS = [
    {
        "slug": "citizen-reports",
        "category": "civic_reports",
        "name": "Citizen Reports",
        "name_hi": "नागरिक शिकायतें",
        "description": "Public citizen reports of civic issues submitted through the platform.",
        "description_hi": "प्लेटफ़ॉर्म के माध्यम से दर्ज नागरिक शिकायतें।",
        "publisher": "Theek Karo",
        "source": "Platform citizen reports",
        "derived": False,
        "update_frequency": "hourly",
        "formats": "csv,json",
        "version": "2026.08",
        "methodology_slug": "public-reporting",
        "coverage": {
            "scope": "All report locations & categories",
            "excludes": "Personal details, exact locations, private media",
        },
    },
    {
        "slug": "verified-reports",
        "category": "verified_reports",
        "name": "Verified Reports",
        "name_hi": "सत्यापित शिकायतें",
        "description": "Citizen reports verified by the platform team or officials.",
        "description_hi": "प्लेटफ़ॉर्म टीम या अधिकारियों द्वारा सत्यापित नागरिक शिकायतें।",
        "publisher": "Theek Karo",
        "source": "Platform verification workflow",
        "derived": True,
        "derived_from": {"dataset": "citizen-reports"},
        "update_frequency": "hourly",
        "formats": "csv,json",
        "version": "2026.08",
        "methodology_slug": "public-reporting",
        "coverage": {
            "scope": "Reports with status verified or higher",
            "excludes": "Unverified reports",
        },
    },
    {
        "slug": "civic-cases",
        "category": "cases",
        "name": "Civic Cases",
        "name_hi": "नागरिक मामले",
        "description": "Public civic cases with acknowledged, in-progress and resolved statuses.",
        "description_hi": "स्वीकृत, प्रगति-पर और हल किए गए नागरिक मामले।",
        "publisher": "Theek Karo",
        "source": "Platform case workflow",
        "derived": True,
        "derived_from": {"dataset": "verified-reports"},
        "update_frequency": "daily",
        "formats": "csv,json",
        "version": "2026.08",
        "methodology_slug": "public-reporting",
        "coverage": {
            "scope": "Public case outcomes",
            "excludes": "Internal notes, responses by private officials",
        },
    },
    {
        "slug": "resolutions",
        "category": "resolutions",
        "name": "Resolutions & Evidence",
        "name_hi": "समाधान और साक्ष्य",
        "description": "Public resolution submissions with evidence summaries.",
        "description_hi": "साक्ष्य सहित सार्वजनिक समाधान प्रस्तुतियाँ।",
        "publisher": "Theek Karo",
        "source": "Platform resolution workflow",
        "derived": True,
        "derived_from": {"dataset": "civic-cases"},
        "update_frequency": "daily",
        "formats": "csv,json",
        "version": "2026.08",
        "methodology_slug": "public-reporting",
        "coverage": {
            "scope": "Resolutions with public visibility",
            "excludes": "Private evidence media",
        },
    },
    {
        "slug": "institutions",
        "category": "institutions",
        "name": "Public Institutions",
        "name_hi": "सार्वजनिक संस्थान",
        "description": "Public institutions (schools, hospitals, courts) covered by the platform.",
        "description_hi": "प्लेटफ़ॉर्म द्वारा कवर किए गए सार्वजनिक संस्थान।",
        "publisher": "Theek Karo",
        "source": "Registered institution directory",
        "derived": False,
        "update_frequency": "weekly",
        "formats": "csv,json",
        "version": "2026.08",
        "methodology_slug": "public-reporting",
        "coverage": {
            "scope": "Directory of registered institutions",
            "excludes": "Contact details of individuals",
        },
    },
    {
        "slug": "official-data",
        "category": "official_data",
        "name": "Official Government Data",
        "name_hi": "सरकारी डेटा",
        "description": "Curated imported datasets from official government sources.",
        "description_hi": "आधिकारिक सरकारी स्रोतों से आयातित डेटासेट।",
        "publisher": "Government sources",
        "source": "Curated import pipeline (govdata)",
        "derived": False,
        "update_frequency": "monthly",
        "formats": "csv,json",
        "version": "2026.08",
        "methodology_slug": "official-data",
        "coverage": {
            "scope": "Published official datasets",
            "excludes": "Unpublished or restricted data",
        },
    },
    {
        "slug": "geography",
        "category": "geography",
        "name": "Geography & Boundaries",
        "name_hi": "भौगोलिक क्षेत्र",
        "description": "Geographic hierarchy and boundary coverage used by the platform.",
        "description_hi": "प्लेटफ़ॉर्म द्वारा उपयोग किए जाने वाले भौगोलिक पदानुक्रम और सीमाएँ।",
        "publisher": "Theek Karo",
        "source": "Registered geography hierarchy",
        "derived": False,
        "update_frequency": "monthly",
        "formats": "csv,json",
        "version": "2026.08",
        "methodology_slug": "public-reporting",
        "coverage": {"scope": "Geography codes & boundaries", "excludes": "Sensitive geometry"},
    },
]


def upgrade() -> None:
    op.create_table(
        "public_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_hi", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("description_hi", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("update_frequency", sa.String(length=32), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("derived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("derived_from", sa.JSON(), nullable=True),
        sa.Column("coverage", sa.JSON(), nullable=True),
        sa.Column("formats", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("documentation_url", sa.Text(), nullable=True),
        sa.Column("methodology_slug", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'archived')", name="ck_public_datasets_status"
        ),
        sa.CheckConstraint(
            "category IN ('civic_reports', 'verified_reports', 'cases', 'resolutions', "
            "'institutions', 'official_data', 'geography')",
            name="ck_public_datasets_category",
        ),
    )

    op.create_table(
        "public_dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dataset_id"], ["public_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("dataset_id", "version", name="uq_public_dataset_versions"),
    )
    op.create_index(
        op.f("ix_public_dataset_versions_dataset_id"),
        "public_dataset_versions",
        ["dataset_id"],
    )

    op.create_table(
        "public_dataset_lineage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("input_source", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dataset_id"], ["public_datasets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dataset_id", "step_order", name="uq_public_dataset_lineage"),
    )
    op.create_index(
        op.f("ix_public_dataset_lineage_dataset_id"),
        "public_dataset_lineage",
        ["dataset_id"],
    )

    op.create_table(
        "data_correction_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("target_name", sa.Text(), nullable=True),
        sa.Column("field", sa.Text(), nullable=True),
        sa.Column("current_value", sa.Text(), nullable=True),
        sa.Column("suggested_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "target_type IN ('institution', 'geography', 'dataset', 'report')",
            name="ck_corrections_target_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_corrections_status"
        ),
    )
    op.create_index(
        op.f("ix_data_correction_requests_user_id"),
        "data_correction_requests",
        ["user_id"],
    )

    op.create_table(
        "public_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(length=8), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("quota_per_hour", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_public_api_keys_status"),
    )
    op.create_index(op.f("ix_public_api_keys_user_id"), "public_api_keys", ["user_id"])

    op.create_table(
        "public_api_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint", sa.String(length=160), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_id"], ["public_api_keys.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_public_api_usage_key_id"), "public_api_usage", ["key_id"])

    op.create_table(
        "data_export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("format", sa.String(length=8), nullable=False, server_default="csv"),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("file_key", sa.Text(), nullable=True),
        sa.Column("file_url_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dataset_id"], ["public_datasets.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "kind IN ('citizen_reports', 'institutions', 'resolutions', 'statistics')",
            name="ck_export_jobs_kind",
        ),
        sa.CheckConstraint("format IN ('csv', 'json')", name="ck_export_jobs_format"),
        sa.CheckConstraint(
            "status IN ('queued', 'generating', 'ready', 'failed', 'expired')",
            name="ck_export_jobs_status",
        ),
    )
    op.create_index(op.f("ix_data_export_jobs_user_id"), "data_export_jobs", ["user_id"])

    op.create_table(
        "saved_research_queries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_saved_research_queries_user_id"),
        "saved_research_queries",
        ["user_id"],
    )

    # -- seeds -------------------------------------------------------------------
    import json
    import uuid
    from datetime import UTC, datetime

    conn = op.get_bind()
    now = datetime.now(UTC)

    existing = {
        row[0] for row in conn.execute(sa.text("SELECT slug FROM public_datasets")).fetchall()
    }
    for seed in _DATASET_SEEDS:
        if seed["slug"] in existing:
            continue
        dataset_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO public_datasets (id, slug, name, name_hi, description, "
                "description_hi, category, publisher, source, derived, derived_from, "
                "update_frequency, formats, version, methodology_slug, coverage, status, "
                "last_updated_at, created_at, updated_at) "
                "VALUES (:id, :slug, :name, :name_hi, :description, :description_hi, "
                ":category, :publisher, :source, :derived, CAST(:derived_from AS json), "
                ":update_frequency, :formats, :version, :methodology_slug, "
                "CAST(:coverage AS json), "
                "'active', :now, :now, :now)"
            ),
            {
                "id": dataset_id,
                "slug": seed["slug"],
                "name": seed["name"],
                "name_hi": seed.get("name_hi"),
                "description": seed.get("description"),
                "description_hi": seed.get("description_hi"),
                "category": seed["category"],
                "publisher": seed["publisher"],
                "source": seed["source"],
                "derived": seed["derived"],
                "derived_from": json.dumps(seed.get("derived_from") or {}),
                "update_frequency": seed["update_frequency"],
                "formats": seed["formats"],
                "version": seed["version"],
                "methodology_slug": seed["methodology_slug"],
                "coverage": json.dumps(seed.get("coverage") or {}),
                "now": now,
            },
        )
        conn.execute(
            sa.text(
                "INSERT INTO public_dataset_versions (id, dataset_id, version, released_at, "
                "created_at) VALUES (:id, :dataset_id, :version, :released_at, :created_at)"
            ),
            {
                "id": uuid.uuid4(),
                "dataset_id": dataset_id,
                "version": seed["version"],
                "released_at": now,
                "created_at": now,
            },
        )
        lineage = [
            ("collect", "Public submission intake (reports, verification, cases)"),
            ("normalize", "Normalize statuses, visibility and timestamps"),
            ("generalize", "Generalize coordinates to ~0.01 deg"),
            ("exclude", "Drop private/PII fields per public allowlist"),
        ]
        if seed["derived"]:
            lineage.insert(0, ("source", "Read from underlying dataset(s) only"))
        for step_order, (step_name, description) in enumerate(lineage, start=1):
            conn.execute(
                sa.text(
                    "INSERT INTO public_dataset_lineage (id, dataset_id, step_order, "
                    "step_name, description, created_at) "
                    "VALUES (:id, :dataset_id, :step_order, :step_name, :description, :created_at)"
                ),
                {
                    "id": uuid.uuid4(),
                    "dataset_id": dataset_id,
                    "step_order": step_order,
                    "step_name": step_name,
                    "description": description,
                    "created_at": now,
                },
            )

    # role permissions for public-data management
    existing_roles = {
        row[0]: row[1] for row in conn.execute(sa.text("SELECT code, id FROM roles")).fetchall()
    }
    existing_permissions = {
        row[0]: row[1]
        for row in conn.execute(sa.text("SELECT code, id FROM permissions")).fetchall()
    }
    existing_rp = {
        (row[0], row[1])
        for row in conn.execute(
            sa.text("SELECT role_id, permission_id FROM role_permissions")
        ).fetchall()
    }
    for code in ("public_data.read", "public_data.manage", "public_data.export"):
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
    role_permissions = {
        "admin": ["public_data.read", "public_data.manage", "public_data.export"],
        "analyst": ["public_data.read", "public_data.export"],
        "department_manager": ["public_data.read"],
    }
    for role_code, perm_codes in role_permissions.items():
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
    op.drop_table("saved_research_queries")
    op.drop_table("data_export_jobs")
    op.drop_table("public_api_usage")
    op.drop_table("public_api_keys")
    op.drop_table("data_correction_requests")
    op.drop_table("public_dataset_lineage")
    op.drop_table("public_dataset_versions")
    op.drop_table("public_datasets")
