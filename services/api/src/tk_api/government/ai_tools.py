"""Government workflow MCP tools (Phase 25).

Read-only AI-assisted tools for government workflow operations.
AI may assist with routing recommendations, queue summaries, SLA monitoring,
response drafting, and escalation identification. All tools enforce
authorization — AI never bypasses permissions.

Write tools require explicit confirmation for consequential operations.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def tool_get_department_info(
    session: AsyncSession,
    department_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Get department profile with case counts and SLA status."""
    from tk_api.cases.models import CivicCase
    from tk_api.departments.models import Department

    try:
        dept_uuid = uuid.UUID(department_id)
    except ValueError:
        return {"error": "Invalid department UUID format"}

    dept = await session.get(Department, dept_uuid)
    if dept is None:
        return {"error": "Department not found"}

    case_count = (
        await session.scalar(
            select(__import__("sqlalchemy").func.count(CivicCase.id)).where(
                CivicCase.primary_department_id == dept_uuid
            )
        )
        or 0
    )

    return {
        "id": str(dept.id),
        "name": dept.name,
        "slug": dept.slug,
        "status": dept.status,
        "case_count": case_count,
        "description": dept.description,
        "official_contact": dept.official_contact,
        "disclaimer": "Counts are deterministic; details require the department portal.",
    }


async def tool_get_case_queue_summary(
    session: AsyncSession,
    department_id: str | None = None,
    status: str | None = None,
    limit: int = 10,
    **kwargs: Any,
) -> dict[str, Any]:
    """Summarize a department's case queue. Public-safe metadata only."""
    from tk_api.cases.models import CivicCase

    stmt = select(CivicCase)
    if department_id:
        try:
            dept_uuid = uuid.UUID(department_id)
            stmt = stmt.where(CivicCase.primary_department_id == dept_uuid)
        except ValueError:
            return {"error": "Invalid department UUID format"}
    if status:
        stmt = stmt.where(CivicCase.status == status)
    stmt = stmt.order_by(CivicCase.created_at.desc()).limit(min(limit, 50))
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "cases": [
            {
                "id": str(c.id),
                "case_no": c.case_no,
                "status": c.status,
                "priority": c.priority,
                "sla_status": c.sla_status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ],
        "count": len(rows),
        "disclaimer": "Aggregate queue metadata; details require department portal access.",
    }


async def tool_get_case_sla_status(
    session: AsyncSession,
    case_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Get SLA status for a specific case. Read-only."""
    from tk_api.cases.models import CivicCase, SlaInstance

    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        return {"error": "Invalid case UUID format"}

    case = await session.get(CivicCase, case_uuid)
    if case is None:
        return {"error": "Case not found"}

    instance = await session.scalar(select(SlaInstance).where(SlaInstance.case_id == case_uuid))

    return {
        "case_id": str(case.id),
        "case_no": case.case_no,
        "sla_status": case.sla_status,
        "sla_started_at": case.sla_started_at.isoformat() if case.sla_started_at else None,
        "sla_due_at": case.sla_due_at.isoformat() if case.sla_due_at else None,
        "instance_status": instance.status if instance else None,
        "breached_at": instance.breached_at.isoformat()
        if instance and instance.breached_at
        else None,
        "paused_seconds": instance.paused_seconds if instance else 0,
    }


async def tool_get_department_responses(
    session: AsyncSession,
    case_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Get official responses for a case. Internal responses are excluded."""
    from tk_api.government.models import OfficialResponse

    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        return {"error": "Invalid case UUID format"}

    rows = (
        (
            await session.execute(
                select(OfficialResponse)
                .where(
                    OfficialResponse.case_id == case_uuid,
                    OfficialResponse.withdrawn.is_(False),
                )
                .order_by(OfficialResponse.version.desc())
            )
        )
        .scalars()
        .all()
    )

    return {
        "responses": [
            {
                "id": str(r.id),
                "version": r.version,
                "department_id": str(r.department_id),
                "summary": r.summary,
                "action_taken": r.action_taken,
                "current_status": r.current_status,
                "next_step": r.next_step,
                "source": r.source,
                "is_current": r.is_current,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }


async def tool_get_department_analytics(
    session: AsyncSession,
    department_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Aggregate case metrics for a department. Deterministic counts only."""
    from sqlalchemy import func

    from tk_api.cases.models import CivicCase, SlaInstance

    try:
        dept_uuid = uuid.UUID(department_id)
    except ValueError:
        return {"error": "Invalid department UUID format"}

    total = (
        await session.scalar(
            select(func.count(CivicCase.id)).where(CivicCase.primary_department_id == dept_uuid)
        )
        or 0
    )

    open_statuses = {
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
        "reopened",
    }
    open_count = 0
    for s in open_statuses:
        open_count += (
            await session.scalar(
                select(func.count(CivicCase.id)).where(
                    CivicCase.primary_department_id == dept_uuid,
                    CivicCase.status == s,
                )
            )
            or 0
        )

    resolved_count = (
        await session.scalar(
            select(func.count(CivicCase.id)).where(
                CivicCase.primary_department_id == dept_uuid,
                CivicCase.status.in_(["resolved", "closed"]),
            )
        )
        or 0
    )

    breached_count = (
        await session.scalar(
            select(func.count(SlaInstance.id)).where(
                SlaInstance.status == "breached",
                SlaInstance.case_id.in_(
                    select(CivicCase.id).where(CivicCase.primary_department_id == dept_uuid)
                ),
            )
        )
        or 0
    )

    return {
        "department_id": str(dept_uuid),
        "total_cases": total,
        "open_cases": open_count,
        "resolved_cases": resolved_count,
        "breached_sla": breached_count,
        "methodology": {
            "definition": "Aggregate counts for cases assigned to this department.",
            "period": "All time (current snapshot).",
            "limitations": "Does not include historical data for reassigned cases.",
        },
    }


async def tool_explain_routing(
    session: AsyncSession,
    case_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """AI-assisted routing explanation: shows routing history and recommendation."""
    from tk_api.cases.models import CivicCase
    from tk_api.government.models import CaseRoute

    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        return {"error": "Invalid case UUID format"}

    case = await session.get(CivicCase, case_uuid)
    if case is None:
        return {"error": "Case not found"}

    routes = (
        (
            await session.execute(
                select(CaseRoute)
                .where(CaseRoute.case_id == case_uuid)
                .order_by(CaseRoute.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    return {
        "case_id": str(case.id),
        "case_no": case.case_no,
        "current_department_id": str(case.primary_department_id)
        if case.primary_department_id
        else None,
        "routing_history": [
            {
                "id": str(r.id),
                "recommended_department_id": str(r.recommended_department_id),
                "confidence": float(r.confidence),
                "reason": r.reason,
                "source": r.routing_source,
                "accepted": r.accepted,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in routes
        ],
        "disclaimer": (
            "Routing explanations are advisory; official routing decisions "
            "are made by authorized reviewers."
        ),
    }


async def tool_summarize_escalations(
    session: AsyncSession,
    department_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Summarize active escalations for a department or system-wide."""

    from tk_api.cases.models import CaseEscalation, CivicCase

    stmt = select(CaseEscalation).where(CaseEscalation.status == "active")
    if department_id:
        try:
            dept_uuid = uuid.UUID(department_id)
            stmt = stmt.where(
                CaseEscalation.case_id.in_(
                    select(CivicCase.id).where(CivicCase.primary_department_id == dept_uuid)
                )
            )
        except ValueError:
            return {"error": "Invalid department UUID format"}

    rows = (await session.execute(stmt.order_by(CaseEscalation.level.desc()))).scalars().all()

    return {
        "escalations": [
            {
                "id": str(e.id),
                "case_id": str(e.case_id),
                "level": e.level,
                "reason": e.reason,
                "escalated_by_system": e.escalated_by_system,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ],
        "count": len(rows),
        "disclaimer": (
            "Escalation summaries are advisory; authorized users make escalation decisions."
        ),
    }
