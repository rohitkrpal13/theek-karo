"""Security, privacy, and abuse-prevention models (Phase 28).

Implements:
- SecurityIncident: Track and manage security incidents
- AbuseScore: Risk scoring for accounts and actions
- DataClassification: Data sensitivity classification labels
- SecurityAuditEntry: Enhanced security-focused audit entries
- IPBlock: IP-based blocking for abuse prevention
- SecurityPolicy: Configurable security policies
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Index, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tk_api.core.db import Base

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IncidentSeverity(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(enum.StrEnum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    ERADICATED = "eradicated"
    RECOVERED = "recovered"
    CLOSED = "closed"


class IncidentCategory(enum.StrEnum):
    CREDENTIAL_LEAK = "credential_leak"
    DATA_LEAK = "data_leak"
    ACCOUNT_TAKEOVER = "account_takeover"
    MALWARE_UPLOAD = "malware_upload"
    PROMPT_INJECTION = "prompt_injection"
    MCP_ABUSE = "mcp_abuse"
    GOVERNMENT_INTEGRATION_COMPROMISE = "government_integration_compromise"
    PROVIDER_COMPROMISE = "provider_compromise"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    MASS_SPAM = "mass_spam"
    DATA_EXFILTRATION = "data_exfiltration"
    API_ABUSE = "api_abuse"
    OTHER = "other"


class DataClassification(enum.StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    HIGHLY_RESTRICTED = "highly_restricted"


class AbuseType(enum.StrEnum):
    SPAM = "spam"
    MASS_CASE_CREATION = "mass_case_creation"
    DUPLICATE_REPORTS = "duplicate_reports"
    MASS_COMMENTS = "mass_comments"
    MASS_MENTIONS = "mass_mentions"
    MESSAGE_ABUSE = "message_abuse"
    SCRAPING = "scraping"
    CREDENTIAL_ATTACK = "credential_attack"
    AI_ABUSE = "ai_abuse"
    BOT_BEHAVIOR = "bot_behavior"


class IPBlockReason(enum.StrEnum):
    BRUTE_FORCE = "brute_force"
    SCRAPING = "scraping"
    API_ABUSE = "api_abuse"
    MALICIOUS_REQUESTS = "malicious_requests"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Security Incident
# ---------------------------------------------------------------------------


class SecurityIncident(Base):
    """Track security incidents through their lifecycle."""

    __tablename__ = "security_incidents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity), nullable=False, default=IncidentSeverity.MEDIUM
    )
    category: Mapped[IncidentCategory] = mapped_column(
        Enum(IncidentCategory), nullable=False, default=IncidentCategory.OTHER
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), nullable=False, default=IncidentStatus.DETECTED
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    affected_components: Mapped[list[str] | None] = mapped_column(JSON)
    impact_description: Mapped[str | None] = mapped_column(Text)
    containment_actions: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_security_incidents_severity", "severity"),
        Index("ix_security_incidents_status", "status"),
        Index("ix_security_incidents_detected_at", "detected_at"),
    )


# ---------------------------------------------------------------------------
# Abuse Score
# ---------------------------------------------------------------------------


class AbuseScore(Base):
    """Risk scoring for accounts and actions to detect abuse patterns."""

    __tablename__ = "abuse_scores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    ip_address: Mapped[str | None] = mapped_column(Text, index=True)
    abuse_type: Mapped[AbuseType] = mapped_column(Enum(AbuseType), nullable=False)
    score: Mapped[float] = mapped_column(default=0.0)  # 0.0 = no risk, 1.0 = max risk
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    action_taken: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_abuse_scores_user_type", "user_id", "abuse_type"),
        Index("ix_abuse_scores_ip_type", "ip_address", "abuse_type"),
    )


# ---------------------------------------------------------------------------
# IP Block
# ---------------------------------------------------------------------------


class IPBlock(Base):
    """IP-based blocking for abuse prevention."""

    __tablename__ = "ip_blocks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ip_address: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reason: Mapped[IPBlockReason] = mapped_column(Enum(IPBlockReason), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    blocked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    blocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (Index("ix_ip_blocks_active_ip", "is_active", "ip_address"),)


# ---------------------------------------------------------------------------
# Security Policy
# ---------------------------------------------------------------------------


class SecurityPolicy(Base):
    """Configurable security policies for the platform."""

    __tablename__ = "security_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Security Audit Entry (enhanced)
# ---------------------------------------------------------------------------


class SecurityAuditEntry(Base):
    """Security-focused audit entries for tracking sensitive operations."""

    __tablename__ = "security_audit_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    result: Mapped[str] = mapped_column(
        Text, nullable=False, default="success"
    )  # success|denied|error
    risk_level: Mapped[str] = mapped_column(
        Text, nullable=False, default="low"
    )  # low|medium|high|critical
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_security_audit_actor", "actor_id"),
        Index("ix_security_audit_action", "action"),
        Index("ix_security_audit_risk", "risk_level"),
        Index("ix_security_audit_created", "created_at"),
    )


# ---------------------------------------------------------------------------
# Data Retention Policy
# ---------------------------------------------------------------------------


class DataRetentionPolicy(Base):
    """Define data retention periods for different data categories."""

    __tablename__ = "data_retention_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    retention_days: Mapped[int] = mapped_column(nullable=False)
    deletion_method: Mapped[str] = mapped_column(
        Text, nullable=False, default="anonymize"
    )  # delete|anonymize|archive
    description: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
