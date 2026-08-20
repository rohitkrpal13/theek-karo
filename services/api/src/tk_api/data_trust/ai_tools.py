"""Phase 23 — Data Trust AI/MCP tools.

All tools are READ_ONLY and permission-guarded. AI may assist with data
quality analysis, provenance lookup, and conflict explanation — but never
makes verification decisions or modifies production data.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.data_trust import service as trust_service
from tk_api.data_trust.models import (
    DataConflict,
    DisputeRecord,
    EvidenceRecord,
    VerificationRecord,
)
from tk_api.provenance.models import DataSource


async def tool_get_evidence_record(
    session: AsyncSession,
    evidence_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get evidence metadata for provenance lookup."""
    try:
        eid = uuid.UUID(evidence_id)
    except ValueError:
        return {"error": "Invalid evidence UUID format"}
    evidence = await session.get(EvidenceRecord, eid)
    if evidence is None:
        return {"error": "Evidence not found"}
    return {
        "id": str(evidence.id),
        "evidence_type": evidence.evidence_type,
        "source_type": evidence.source_type,
        "status": evidence.status,
        "verification_status": evidence.verification_status,
        "verification_count": evidence.verification_count,
        "checksum_sha256": evidence.checksum_sha256,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
    }


async def tool_get_verification_history(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get verification history for an entity."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        return {"error": "Invalid entity UUID format"}
    stmt = (
        select(VerificationRecord)
        .where(
            VerificationRecord.entity_type == entity_type,
            VerificationRecord.entity_id == eid,
        )
        .order_by(VerificationRecord.created_at.desc())
        .limit(10)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "verifications": [
            {
                "decision": v.decision,
                "method": v.method,
                "reviewer_type": v.reviewer_type,
                "explanation": v.explanation,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in rows
        ],
        "count": len(rows),
        "note": "Verification records are append-only.",
    }


async def tool_get_data_conflicts_summary(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Summarize data conflicts for an entity."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        return {"error": "Invalid entity UUID format"}
    stmt = (
        select(DataConflict)
        .where(
            DataConflict.entity_type == entity_type,
            DataConflict.entity_id == eid,
        )
        .order_by(DataConflict.created_at.desc())
        .limit(10)
    )
    rows = (await session.execute(stmt)).scalars().all()
    note = (
        "Conflict states are review signals; community observation "
        "never overrides official data automatically."
    )
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "conflicts": [
            {
                "field_name": c.field_name,
                "source_a_value": c.source_a_value,
                "source_b_value": c.source_b_value,
                "status": c.status,
                "severity": c.severity,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ],
        "count": len(rows),
        "note": note,
    }


async def tool_get_disputes_summary(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Check if an entity has active disputes."""
    stmt = (
        select(DisputeRecord)
        .where(
            DisputeRecord.dispute_target_type == entity_type,
            DisputeRecord.dispute_target_id == entity_id,
        )
        .order_by(DisputeRecord.created_at.desc())
        .limit(5)
    )
    rows = (await session.execute(stmt)).scalars().all()
    active = [d for d in rows if d.status in ("OPEN", "UNDER_REVIEW")]
    banner_text = "Information is currently under review." if active else None
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "active_disputes": len(active),
        "total_disputes": len(rows),
        "has_active_banner": len(active) > 0,
        "banner_text": banner_text,
    }


async def tool_get_source_health(
    session: AsyncSession,
    source_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Get source health status."""
    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        return {"error": "Invalid source UUID format"}
    src = await session.get(DataSource, sid)
    if src is None:
        return {"error": "Source not found"}
    return {
        "source_id": str(src.id),
        "name": src.name,
        "status": src.status,
        "authority_level": src.authority_level,
        "verification_state": src.verification_state,
        "last_verified_at": (src.last_verified_at.isoformat() if src.last_verified_at else None),
        "update_frequency_hours": src.update_frequency_hours,
        "license": src.license,
        "note": "Source health reflects operational status, not data truthfulness.",
    }


async def tool_explain_provenance(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    """AI-powered provenance explanation."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        return {"error": "Invalid entity UUID format"}

    provenance = await trust_service.get_provenance(session, entity_type=entity_type, entity_id=eid)
    evidence_count = len(provenance.get("evidence", []))
    verification_count = len(provenance.get("verifications", []))
    quality = provenance.get("quality", {})
    limitations = provenance.get("limitations", [])

    explanation_parts: list[str] = []
    if evidence_count:
        explanation_parts.append(f"{evidence_count} evidence item(s) registered.")
    if verification_count:
        last_verif = provenance["verifications"][0] if provenance["verifications"] else None
        if last_verif:
            explanation_parts.append(
                f"Last verification: {last_verif['decision']} via {last_verif['method']}."
            )
    if quality.get("overall_status"):
        explanation_parts.append(f"Quality status: {quality['overall_status']}.")
    if limitations:
        explanation_parts.append("Limitations: " + "; ".join(limitations))

    summary = " ".join(explanation_parts) if explanation_parts else "No provenance data available."
    disclaimer = "This explanation is AI-generated and advisory. Source data is authoritative."
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "summary": summary,
        "provenance": provenance,
        "disclaimer": disclaimer,
    }
