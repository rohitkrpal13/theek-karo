"""Security API router (Phase 28).

Endpoints for:
- Security incident management
- IP blocking/unblocking
- Abuse score monitoring
- Security audit logs
- Input validation
- Data classification
- Security health checks
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select

from tk_api.api.deps import CurrentUser, DbSession
from tk_api.auth.authorization import require_permission
from tk_api.core.audit import audit
from tk_api.security.models import (
    AbuseScore,
    IPBlock,
    SecurityAuditEntry,
    SecurityIncident,
)
from tk_api.security.schemas import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
    IPBlockCreate,
    IPBlockResponse,
    SecurityAuditEntryResponse,
    SecuritySummaryResponse,
)
from tk_api.security.service import (
    DataClassificationService,
    InputSanitizer,
    IPBlockService,
    SecurityAuditService,
    SecurityIncidentService,
)

router = APIRouter(prefix="/api/v1/security", tags=["security"])

DepSecManage = Annotated[Any, Depends(require_permission("security.manage"))]
DepSecRead = Annotated[Any, Depends(require_permission("security.read"))]
DepAiUse = Annotated[Any, Depends(require_permission("ai.use"))]


# ---------------------------------------------------------------------------
# Security Incidents
# ---------------------------------------------------------------------------


@router.post("/incidents", response_model=IncidentResponse)
async def create_incident(
    data: IncidentCreate,
    user: CurrentUser,
    _perm: DepSecManage,
    db: DbSession,
) -> SecurityIncident:
    """Create a new security incident."""
    incident = await SecurityIncidentService.create_incident(
        db,
        title=data.title,
        description=data.description,
        severity=data.severity,
        category=data.category,
        affected_components=data.affected_components,
        impact_description=data.impact_description,
    )
    await audit(
        db,
        action="security.incident.create",
        entity_type="SecurityIncident",
        entity_id=incident.id,
        actor_id=user.id,
        after={"title": data.title, "severity": data.severity},
    )
    await db.commit()
    return incident


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[SecurityIncident]:
    """List security incidents with optional filters."""
    stmt = select(SecurityIncident)
    if status:
        stmt = stmt.where(SecurityIncident.status == status)
    if severity:
        stmt = stmt.where(SecurityIncident.severity == severity)
    stmt = stmt.order_by(SecurityIncident.detected_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> SecurityIncident:
    """Get a specific security incident."""
    incident = await db.get(SecurityIncident, incident_id)
    if not incident:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: uuid.UUID,
    data: IncidentUpdate,
    user: CurrentUser,
    _perm: DepSecManage,
    db: DbSession,
) -> SecurityIncident:
    """Update a security incident."""
    incident = await SecurityIncidentService.update_status(
        db,
        incident_id=incident_id,
        status=data.status or "investigating",
        assigned_to=data.assigned_to,
        containment_actions=data.containment_actions,
        resolution=data.resolution,
    )
    if not incident:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Incident not found")
    await audit(
        db,
        action="security.incident.update",
        entity_type="SecurityIncident",
        entity_id=incident_id,
        actor_id=user.id,
        after=data.model_dump(exclude_none=True),
    )
    await db.commit()
    return incident


# ---------------------------------------------------------------------------
# IP Blocking
# ---------------------------------------------------------------------------


@router.post("/ip-blocks", response_model=IPBlockResponse)
async def block_ip(
    data: IPBlockCreate,
    user: CurrentUser,
    _perm: DepSecManage,
    db: DbSession,
) -> IPBlock:
    """Block an IP address."""
    from tk_api.security.models import IPBlockReason

    block = await IPBlockService.block_ip(
        db,
        ip=data.ip_address,
        reason=IPBlockReason(data.reason),
        description=data.description,
        blocked_by=user.id,
        duration_hours=data.duration_hours,
    )
    await audit(
        db,
        action="security.ip.block",
        entity_type="IPBlock",
        entity_id=block.id,
        actor_id=user.id,
        after={"ip": data.ip_address, "reason": data.reason},
    )
    await db.commit()
    return block


@router.delete("/ip-blocks/{ip_address}")
async def unblock_ip(
    ip_address: str,
    user: CurrentUser,
    _perm: DepSecManage,
    db: DbSession,
) -> dict[str, Any]:
    """Unblock an IP address."""
    removed = await IPBlockService.unblock_ip(db, ip_address)
    await audit(
        db,
        action="security.ip.unblock",
        entity_type="IPBlock",
        actor_id=user.id,
        after={"ip": ip_address, "removed": removed},
    )
    await db.commit()
    return {"ip_address": ip_address, "unblocked": removed}


@router.get("/ip-blocks", response_model=list[IPBlockResponse])
async def list_ip_blocks(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
) -> list[IPBlock]:
    """List IP blocks."""
    stmt = select(IPBlock)
    if active_only:
        stmt = stmt.where(IPBlock.is_active == True)  # noqa: E712
    stmt = stmt.order_by(IPBlock.blocked_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Abuse Scores
# ---------------------------------------------------------------------------


@router.get("/abuse-scores", response_model=list[dict[str, Any]])
async def list_abuse_scores(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    ip_address: Annotated[str | None, Query()] = None,
    min_score: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """List abuse scores with optional filters."""
    stmt = select(AbuseScore)
    if user_id:
        stmt = stmt.where(AbuseScore.user_id == user_id)
    if ip_address:
        stmt = stmt.where(AbuseScore.ip_address == ip_address)
    if min_score > 0:
        stmt = stmt.where(AbuseScore.score >= min_score)
    stmt = stmt.order_by(AbuseScore.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    scores = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id) if s.user_id else None,
            "ip_address": s.ip_address,
            "abuse_type": s.abuse_type.value if hasattr(s.abuse_type, "value") else s.abuse_type,
            "score": s.score,
            "action_taken": s.action_taken,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in scores
    ]


# ---------------------------------------------------------------------------
# Security Audit
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=list[SecurityAuditEntryResponse])
async def list_security_audit(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
    action: str | None = Query(None),
    risk_level: str | None = Query(None),
    result: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[SecurityAuditEntry]:
    """List security audit entries."""
    stmt = select(SecurityAuditEntry)
    if action:
        stmt = stmt.where(SecurityAuditEntry.action == action)
    if risk_level:
        stmt = stmt.where(SecurityAuditEntry.risk_level == risk_level)
    if result:
        stmt = stmt.where(SecurityAuditEntry.result == result)
    stmt = stmt.order_by(SecurityAuditEntry.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/audit/summary", response_model=SecuritySummaryResponse)
async def get_security_summary(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
    hours: int = Query(24, ge=1, le=720),
) -> dict[str, Any]:
    """Get a summary of security events."""
    return await SecurityAuditService.get_security_summary(db, hours=hours)


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------


@router.post("/validate-input")
async def validate_input(
    text: str,
    user: CurrentUser,
    _perm: DepAiUse,
    db: DbSession,
) -> dict[str, Any]:
    """Validate user input for potential security issues."""
    findings = []
    findings.extend(InputSanitizer.detect_injection(text))
    findings.extend(InputSanitizer.detect_sql_injection(text))
    findings.extend(InputSanitizer.detect_path_traversal(text))

    return {
        "is_safe": len(findings) == 0,
        "findings": findings,
        "recommendation": "proceed" if len(findings) == 0 else "review",
    }


# ---------------------------------------------------------------------------
# Data Classification
# ---------------------------------------------------------------------------


@router.get("/classification/{entity_type}")
async def get_classification(
    entity_type: str,
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> dict[str, Any]:
    """Get data classification for an entity type."""
    classification = DataClassificationService.get_classification(entity_type)
    return {
        "entity_type": entity_type,
        "classification": classification.value,
    }


# ---------------------------------------------------------------------------
# Security Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def security_health(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> dict[str, Any]:
    """Get security health status."""
    from datetime import UTC, datetime, timedelta

    # Count active blocks — include permanent blocks (expires_at IS NULL)
    block_stmt = select(func.count(IPBlock.id)).where(
        and_(
            IPBlock.is_active == True,  # noqa: E712
            or_(
                IPBlock.expires_at.is_(None),
                IPBlock.expires_at > func.now(),
            ),
        )
    )
    active_blocks = (await db.execute(block_stmt)).scalar() or 0

    # Count recent denials
    since = datetime.now(UTC) - timedelta(hours=24)
    deny_stmt = select(func.count(SecurityAuditEntry.id)).where(
        and_(
            SecurityAuditEntry.created_at >= since,
            SecurityAuditEntry.result == "denied",
        )
    )
    recent_denials = (await db.execute(deny_stmt)).scalar() or 0

    # Count active incidents
    from tk_api.security.models import IncidentStatus

    incident_stmt = select(func.count(SecurityIncident.id)).where(
        SecurityIncident.status.in_([
            IncidentStatus.DETECTED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.CONTAINED,
        ])
    )
    active_incidents = (await db.execute(incident_stmt)).scalar() or 0

    # MFA enforcement status
    from tk_api.auth.authorization import (
        _MFA_ENFORCEMENT_ENABLED,
        _MFA_REQUIRED_ROLES,
    )

    return {
        "status": "healthy" if active_incidents == 0 else "degraded",
        "checks": {
            "ip_blocking": "enabled",
            "abuse_detection": "enabled",
            "input_validation": "enabled",
            "security_headers": "enabled",
            "mfa_enforcement": "enabled" if _MFA_ENFORCEMENT_ENABLED else "disabled",
        },
        "active_blocks": active_blocks,
        "recent_deny_count": recent_denials,
        "active_incidents": active_incidents,
        "mfa_required_roles": sorted(_MFA_REQUIRED_ROLES),
    }


# ---------------------------------------------------------------------------
# Phase 10 — Hardening: MFA Enforcement & SLO Validation
# ---------------------------------------------------------------------------


@router.get("/mfa-status")
async def get_mfa_status(
    user: CurrentUser,
    _perm: DepSecRead,
) -> dict[str, Any]:
    """Check MFA enforcement status across privileged roles."""
    from tk_api.auth.authorization import _MFA_ENFORCEMENT_ENABLED, _MFA_REQUIRED_ROLES

    return {
        "mfa_enforcement_enabled": _MFA_ENFORCEMENT_ENABLED,
        "required_roles": sorted(_MFA_REQUIRED_ROLES),
        "note": (
            "MFA is enforced at the authorization layer. "
            "Officials and admins must complete TOTP setup."
        ),
    }


@router.get("/slo-status")
async def get_slo_status(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> dict[str, Any]:
    """SLO validation: check p95 latency and error rates against thresholds."""
    from datetime import UTC, datetime, timedelta

    # SLO targets (from SECURITY.md / SCALE-TEST-REPORT.md)
    SLO_TARGETS = {
        "p95_latency_ms": 500,
        "error_rate_pct": 1.0,
        "availability_pct": 99.9,
    }

    # Check recent API usage stats
    since = datetime.now(UTC) - timedelta(hours=1)
    from tk_api.ai.models import AiRun

    recent_runs = (
        await db.execute(
            select(AiRun).where(AiRun.created_at >= since)
        )
    ).scalars().all()

    if recent_runs:
        latencies = [r.latency_ms for r in recent_runs if r.latency_ms]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 2 else avg_latency
        error_count = sum(1 for r in recent_runs if r.status == "failed")
        error_rate = (error_count / len(recent_runs)) * 100 if recent_runs else 0
    else:
        p95_latency = 0
        error_rate = 0

    return {
        "slo_targets": SLO_TARGETS,
        "current": {
            "p95_latency_ms": round(p95_latency, 1),
            "error_rate_pct": round(error_rate, 2),
            "recent_requests": len(recent_runs),
        },
        "status": {
            "p95_latency": "met" if p95_latency <= SLO_TARGETS["p95_latency_ms"] else "breached",
            "error_rate": "met" if error_rate <= SLO_TARGETS["error_rate_pct"] else "breached",
        },
        "overall": (
            "healthy"
            if p95_latency <= SLO_TARGETS["p95_latency_ms"]
            and error_rate <= SLO_TARGETS["error_rate_pct"]
            else "degraded"
        ),
        "note": (
            "SLOs measured against the last hour of API traffic. "
            "k6 smoke tests validate under load."
        ),
    }


# Export router
security_router = router
