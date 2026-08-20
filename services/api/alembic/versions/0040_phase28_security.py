"""Phase 28 — Security, Privacy, Trust, Compliance models.

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

# revision identifiers
revision = "0040"
down_revision = "0039_phase27_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Security Incidents
    op.create_table(
        "security_incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="incidentseverity"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "category",
            sa.Enum(
                "credential_leak",
                "data_leak",
                "account_takeover",
                "malware_upload",
                "prompt_injection",
                "mcp_abuse",
                "government_integration_compromise",
                "provider_compromise",
                "privilege_escalation",
                "mass_spam",
                "data_exfiltration",
                "api_abuse",
                "other",
                name="incidentcategory",
            ),
            nullable=False,
            server_default="other",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "detected",
                "investigating",
                "contained",
                "eradicated",
                "recovered",
                "closed",
                name="incidentstatus",
            ),
            nullable=False,
            server_default="detected",
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("assigned_to", UUID(as_uuid=True), nullable=True),
        sa.Column("affected_components", JSON, nullable=True),
        sa.Column("impact_description", sa.Text, nullable=True),
        sa.Column("containment_actions", sa.Text, nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_security_incidents_severity", "security_incidents", ["severity"])
    op.create_index("ix_security_incidents_status", "security_incidents", ["status"])
    op.create_index("ix_security_incidents_detected_at", "security_incidents", ["detected_at"])

    # Abuse Scores
    op.create_table(
        "abuse_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.Text, nullable=True),
        sa.Column(
            "abuse_type",
            sa.Enum(
                "spam",
                "mass_case_creation",
                "duplicate_reports",
                "mass_comments",
                "mass_mentions",
                "message_abuse",
                "scraping",
                "credential_attack",
                "ai_abuse",
                "bot_behavior",
                name="abusetype",
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("evidence", JSON, nullable=True),
        sa.Column("action_taken", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_abuse_scores_user_type", "abuse_scores", ["user_id", "abuse_type"])
    op.create_index("ix_abuse_scores_ip_type", "abuse_scores", ["ip_address", "abuse_type"])

    # IP Blocks
    op.create_table(
        "ip_blocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ip_address", sa.Text, nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "brute_force",
                "scraping",
                "api_abuse",
                "malicious_requests",
                "manual",
                name="ipblockreason",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("blocked_by", UUID(as_uuid=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ip_blocks_active_ip", "ip_blocks", ["is_active", "ip_address"])
    op.create_index("ix_ip_blocks_ip", "ip_blocks", ["ip_address"])

    # Security Policies
    op.create_table(
        "security_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", JSON, nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_security_policies_code", "security_policies", ["code"], unique=True)

    # Security Audit Entries
    op.create_table(
        "security_audit_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("resource_type", sa.Text, nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("result", sa.Text, nullable=False, server_default="success"),
        sa.Column("risk_level", sa.Text, nullable=False, server_default="low"),
        sa.Column("ip_address", sa.Text, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("details", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_security_audit_actor", "security_audit_entries", ["actor_id"])
    op.create_index("ix_security_audit_action", "security_audit_entries", ["action"])
    op.create_index("ix_security_audit_risk", "security_audit_entries", ["risk_level"])
    op.create_index("ix_security_audit_created", "security_audit_entries", ["created_at"])

    # Data Retention Policies
    op.create_table(
        "data_retention_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.Text, nullable=False, unique=True),
        sa.Column("retention_days", sa.Integer, nullable=False),
        sa.Column("deletion_method", sa.Text, nullable=False, server_default="anonymize"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_data_retention_entity", "data_retention_policies", ["entity_type"], unique=True
    )


def downgrade() -> None:
    op.drop_table("data_retention_policies")
    op.drop_table("security_audit_entries")
    op.drop_table("security_policies")
    op.drop_table("ip_blocks")
    op.drop_table("abuse_scores")
    op.drop_table("security_incidents")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS ipblockreason")
    op.execute("DROP TYPE IF EXISTS abusetype")
    op.execute("DROP TYPE IF EXISTS incidentstatus")
    op.execute("DROP TYPE IF EXISTS incidentcategory")
    op.execute("DROP TYPE IF EXISTS incidentseverity")
