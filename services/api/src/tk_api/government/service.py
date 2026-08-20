"""Government workflow service (Phase 25).

Business logic for routing, handoffs, official responses, workflow state
tracking, government integrations, and analytics. All operations are
audited and enforce authorization.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases.models import CivicCase
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError, ConflictError, NotFoundError
from tk_api.departments import service as departments_service
from tk_api.government.models import (
    BulkOperationLog,
    CaseHandoff,
    CaseRoute,
    ExternalCaseReference,
    GovernmentIntegration,
    OfficialResponse,
    RoutingRule,
    SyncRun,
    WorkflowDefinition,
    WorkflowTransition,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


async def create_routing_rule(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    description: str | None = None,
    category_id: uuid.UUID | None = None,
    issue_type_id: uuid.UUID | None = None,
    geography_id: uuid.UUID | None = None,
    institution_type_id: uuid.UUID | None = None,
    target_department_id: uuid.UUID,
    secondary_department_ids: list[uuid.UUID] | None = None,
    priority_order: int = 100,
) -> RoutingRule:
    existing = await session.scalar(select(RoutingRule).where(RoutingRule.code == code))
    if existing is not None:
        raise ConflictError(f"routing rule with code '{code}' already exists")
    dept = await departments_service.get_department(session, target_department_id)
    row = RoutingRule(
        code=code,
        name=name,
        description=description,
        category_id=category_id,
        issue_type_id=issue_type_id,
        geography_id=geography_id,
        institution_type_id=institution_type_id,
        target_department_id=dept.id,
        secondary_department_ids=secondary_department_ids or [],
        priority_order=priority_order,
    )
    session.add(row)
    return row


async def list_routing_rules(
    session: AsyncSession,
    *,
    category_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    limit: int = 100,
) -> list[RoutingRule]:
    stmt = select(RoutingRule).order_by(
        RoutingRule.priority_order.asc(), RoutingRule.created_at.asc()
    )
    if not include_inactive:
        stmt = stmt.where(RoutingRule.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(RoutingRule.category_id == category_id)
    if department_id is not None:
        stmt = stmt.where(RoutingRule.target_department_id == department_id)
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def match_routing_rule(
    session: AsyncSession,
    *,
    category_id: uuid.UUID | None,
    issue_type_id: uuid.UUID | None,
    geography_id: uuid.UUID | None,
    institution_type_id: uuid.UUID | None,
) -> RoutingRule | None:
    """Best-match routing rule using specificity scoring (same as SLA)."""
    rows = await list_routing_rules(session, include_inactive=False, limit=200)
    best: RoutingRule | None = None
    best_score = -1

    for rule in rows:
        score = 0
        if rule.target_department_id is not None:
            score += 8
        if rule.category_id is not None:
            score += 4
        if rule.issue_type_id is not None:
            score += 2
        if rule.geography_id is not None:
            score += 1
        if rule.institution_type_id is not None:
            score += 1

        # Must match all specified non-null fields
        if rule.category_id is not None and category_id != rule.category_id:
            continue
        if rule.issue_type_id is not None and issue_type_id != rule.issue_type_id:
            continue
        if rule.geography_id is not None and geography_id != rule.geography_id:
            continue
        if rule.institution_type_id is not None and institution_type_id != rule.institution_type_id:
            continue

        if score > best_score:
            best_score = score
            best = rule

    return best


# ---------------------------------------------------------------------------
# Case Routing
# ---------------------------------------------------------------------------


async def create_case_route(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    recommended_department_id: uuid.UUID,
    confidence: float = 0.0,
    reason: str | None = None,
    routing_source: str = "rule_based",
    actor_id: uuid.UUID | None = None,
) -> CaseRoute:
    case = await session.get(CivicCase, case_id)
    if case is None:
        raise NotFoundError("case not found", kind="case_not_found")
    dept = await departments_service.get_department(session, recommended_department_id)
    row = CaseRoute(
        case_id=case.id,
        recommended_department_id=dept.id,
        confidence=confidence,
        reason=reason,
        routing_source=routing_source,
    )
    session.add(row)
    await audit(
        session,
        action="case.route.create",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor_id,
        after={
            "department_id": str(dept.id),
            "confidence": confidence,
            "source": routing_source,
        },
    )
    return row


async def accept_case_route(
    session: AsyncSession,
    route: CaseRoute,
    *,
    accepted: bool,
    actor_id: uuid.UUID,
    rejection_reason: str | None = None,
) -> CaseRoute:
    if route.accepted:
        raise ApiError("route already accepted", 409, "route_already_accepted")
    route.accepted = accepted
    route.accepted_by = actor_id
    route.accepted_at = _utcnow()
    if not accepted:
        route.rejection_reason = rejection_reason
    await audit(
        session,
        action="case.route.review",
        entity_type="case_route",
        entity_id=route.id,
        actor_id=actor_id,
        after={"accepted": accepted},
    )
    return route


async def list_case_routes(
    session: AsyncSession,
    case_id: uuid.UUID,
) -> list[CaseRoute]:
    return list(
        (
            await session.execute(
                select(CaseRoute)
                .where(CaseRoute.case_id == case_id)
                .order_by(CaseRoute.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Case Handoffs
# ---------------------------------------------------------------------------


async def create_handoff(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    to_department_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID,
) -> CaseHandoff:
    case = await session.get(CivicCase, case_id)
    if case is None:
        raise NotFoundError("case not found", kind="case_not_found")
    if case.primary_department_id is None:
        raise ApiError("case has no current department", 409, "no_department")
    if case.primary_department_id == to_department_id:
        raise ApiError("cannot handoff to same department", 409, "same_department")
    to_dept = await departments_service.get_department(session, to_department_id)
    row = CaseHandoff(
        case_id=case.id,
        from_department_id=case.primary_department_id,
        to_department_id=to_dept.id,
        reason=reason,
        initiated_by=actor_id,
    )
    session.add(row)
    await audit(
        session,
        action="case.handoff.create",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor_id,
        after={
            "from_department_id": str(case.primary_department_id),
            "to_department_id": str(to_dept.id),
            "reason": reason,
        },
    )
    return row


async def respond_to_handoff(
    session: AsyncSession,
    handoff: CaseHandoff,
    *,
    accepted: bool,
    actor_id: uuid.UUID,
    rejection_reason: str | None = None,
) -> CaseHandoff:
    if handoff.status != "pending":
        raise ApiError("handoff not pending", 409, "handoff_not_pending")
    if accepted:
        handoff.status = "accepted"
        handoff.accepted_by = actor_id
        handoff.accepted_at = _utcnow()
        # Move the case to the new department
        case = await session.get(CivicCase, handoff.case_id)
        if case is not None:
            case.primary_department_id = handoff.to_department_id
    else:
        handoff.status = "rejected"
        handoff.rejection_reason = rejection_reason
    await audit(
        session,
        action="case.handoff.respond",
        entity_type="case_handoff",
        entity_id=handoff.id,
        actor_id=actor_id,
        after={"accepted": accepted},
    )
    return handoff


async def list_handoffs(
    session: AsyncSession,
    case_id: uuid.UUID,
) -> list[CaseHandoff]:
    return list(
        (
            await session.execute(
                select(CaseHandoff)
                .where(CaseHandoff.case_id == case_id)
                .order_by(CaseHandoff.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Official Responses (versioned)
# ---------------------------------------------------------------------------


async def create_official_response(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    department_id: uuid.UUID,
    author_id: uuid.UUID,
    summary: str,
    action_taken: str | None = None,
    current_status: str | None = None,
    next_step: str | None = None,
    estimated_completion: datetime | None = None,
    external_reference_id: str | None = None,
    source: str = "platform",
) -> OfficialResponse:
    case = await session.get(CivicCase, case_id)
    if case is None:
        raise NotFoundError("case not found", kind="case_not_found")
    # Get next version number
    max_version = await session.scalar(
        select(func.max(OfficialResponse.version)).where(OfficialResponse.case_id == case_id)
    )
    next_version = (max_version or 0) + 1

    row = OfficialResponse(
        case_id=case.id,
        department_id=department_id,
        author_id=author_id,
        version=next_version,
        summary=summary,
        action_taken=action_taken,
        current_status=current_status,
        next_step=next_step,
        estimated_completion=estimated_completion,
        external_reference_id=external_reference_id,
        source=source,
    )
    session.add(row)
    await audit(
        session,
        action="official_response.create",
        entity_type="official_response",
        entity_id=case.id,
        actor_id=author_id,
        after={"version": next_version, "department_id": str(department_id)},
    )
    return row


async def update_official_response(
    session: AsyncSession,
    response: OfficialResponse,
    *,
    author_id: uuid.UUID,
    summary: str | None = None,
    action_taken: str | None = None,
    current_status: str | None = None,
    next_step: str | None = None,
    estimated_completion: datetime | None = None,
    change_reason: str | None = None,
) -> OfficialResponse:
    """Create a new version (supersede the old one)."""
    if response.withdrawn:
        raise ApiError("cannot update withdrawn response", 409, "response_withdrawn")
    # Supersede old version
    response.is_current = False
    response.superseded_at = _utcnow()
    response.superseded_reason = change_reason

    # Get next version number
    max_version = await session.scalar(
        select(func.max(OfficialResponse.version)).where(
            OfficialResponse.case_id == response.case_id
        )
    )
    next_version = (max_version or 0) + 1

    new_row = OfficialResponse(
        case_id=response.case_id,
        department_id=response.department_id,
        author_id=author_id,
        version=next_version,
        summary=summary or response.summary,
        action_taken=action_taken or response.action_taken,
        current_status=current_status or response.current_status,
        next_step=next_step or response.next_step,
        estimated_completion=estimated_completion or response.estimated_completion,
        external_reference_id=response.external_reference_id,
        source=response.source,
        is_current=True,
    )
    response.superseded_by = None  # Will be set after flush
    session.add(new_row)
    await session.flush()
    response.superseded_by = new_row.id

    await audit(
        session,
        action="official_response.update",
        entity_type="official_response",
        entity_id=response.case_id,
        actor_id=author_id,
        after={"old_version": response.version, "new_version": next_version},
    )
    return new_row


async def withdraw_official_response(
    session: AsyncSession,
    response: OfficialResponse,
    *,
    actor_id: uuid.UUID,
    reason: str,
) -> OfficialResponse:
    if response.withdrawn:
        raise ApiError("response already withdrawn", 409, "already_withdrawn")
    response.withdrawn = True
    response.withdrawn_by = actor_id
    response.withdrawn_at = _utcnow()
    response.withdrawn_reason = reason
    await audit(
        session,
        action="official_response.withdraw",
        entity_type="official_response",
        entity_id=response.case_id,
        actor_id=actor_id,
        after={"version": response.version, "reason": reason},
    )
    return response


async def list_official_responses(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    include_withdrawn: bool = False,
) -> list[OfficialResponse]:
    stmt = (
        select(OfficialResponse)
        .where(OfficialResponse.case_id == case_id)
        .order_by(OfficialResponse.version.desc())
    )
    if not include_withdrawn:
        stmt = stmt.where(OfficialResponse.withdrawn.is_(False))
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Workflow Definitions
# ---------------------------------------------------------------------------


async def create_workflow_definition(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    description: str | None = None,
    category_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    states: list[str] | None = None,
    transitions: dict[str, Any] | None = None,
    required_roles: dict[str, Any] | None = None,
    is_default: bool = False,
) -> WorkflowDefinition:
    existing = await session.scalar(
        select(WorkflowDefinition).where(WorkflowDefinition.code == code)
    )
    if existing is not None:
        raise ConflictError(f"workflow with code '{code}' already exists")
    row = WorkflowDefinition(
        code=code,
        name=name,
        description=description,
        category_id=category_id,
        department_id=department_id,
        states=states or [],
        transitions=transitions or {},
        required_roles=required_roles or {},
        is_default=is_default,
    )
    session.add(row)
    return row


async def list_workflow_definitions(
    session: AsyncSession,
    *,
    category_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[WorkflowDefinition]:
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(WorkflowDefinition.category_id == category_id)
    if department_id is not None:
        stmt = stmt.where(WorkflowDefinition.department_id == department_id)
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def record_workflow_transition(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    workflow_id: uuid.UUID | None,
    from_state: str,
    to_state: str,
    actor_id: uuid.UUID | None = None,
    reason: str | None = None,
    evidence_required: bool = False,
) -> WorkflowTransition:
    row = WorkflowTransition(
        case_id=case_id,
        workflow_id=workflow_id,
        from_state=from_state,
        to_state=to_state,
        actor_id=actor_id,
        reason=reason,
        evidence_required=evidence_required,
    )
    session.add(row)
    return row


# ---------------------------------------------------------------------------
# Government Integrations
# ---------------------------------------------------------------------------


async def create_government_integration(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    provider_type: str,
    endpoint_url: str | None = None,
    department_id: uuid.UUID | None = None,
    auth_type: str = "none",
    capabilities: list[str] | None = None,
    status_mapping: dict[str, Any] | None = None,
) -> GovernmentIntegration:
    existing = await session.scalar(
        select(GovernmentIntegration).where(GovernmentIntegration.code == code)
    )
    if existing is not None:
        raise ConflictError(f"integration with code '{code}' already exists")
    row = GovernmentIntegration(
        code=code,
        name=name,
        provider_type=provider_type,
        endpoint_url=endpoint_url,
        department_id=department_id,
        auth_type=auth_type,
        capabilities=capabilities or [],
        status_mapping=status_mapping or {},
    )
    session.add(row)
    return row


async def list_government_integrations(
    session: AsyncSession,
    *,
    department_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[GovernmentIntegration]:
    stmt = select(GovernmentIntegration).order_by(GovernmentIntegration.created_at.desc())
    if department_id is not None:
        stmt = stmt.where(GovernmentIntegration.department_id == department_id)
    if status is not None:
        stmt = stmt.where(GovernmentIntegration.status == status)
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def get_government_integration(
    session: AsyncSession, integration_id: uuid.UUID
) -> GovernmentIntegration:
    row = await session.get(GovernmentIntegration, integration_id)
    if row is None:
        raise NotFoundError("integration not found", kind="integration_not_found")
    return row


async def update_government_integration(
    session: AsyncSession,
    integration: GovernmentIntegration,
    *,
    name: str | None = None,
    endpoint_url: str | None = None,
    status: str | None = None,
    capabilities: list[str] | None = None,
    status_mapping: dict[str, Any] | None = None,
) -> GovernmentIntegration:
    if name is not None:
        integration.name = name
    if endpoint_url is not None:
        integration.endpoint_url = endpoint_url
    if status is not None:
        integration.status = status
    if capabilities is not None:
        integration.capabilities = capabilities
    if status_mapping is not None:
        integration.status_mapping = status_mapping
    integration.updated_at = _utcnow()
    return integration


# ---------------------------------------------------------------------------
# External Case References
# ---------------------------------------------------------------------------


async def create_external_reference(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    integration_id: uuid.UUID,
    external_reference_id: str,
    external_status: str | None = None,
) -> ExternalCaseReference:
    case = await session.get(CivicCase, case_id)
    if case is None:
        raise NotFoundError("case not found", kind="case_not_found")
    integration = await get_government_integration(session, integration_id)
    # Map external status to internal status
    mapped = (
        integration.status_mapping.get(external_status, external_status)
        if external_status
        else None
    )
    row = ExternalCaseReference(
        case_id=case.id,
        integration_id=integration.id,
        external_reference_id=external_reference_id,
        external_status=external_status,
        mapped_status=mapped,
        submission_status="submitted",
    )
    session.add(row)
    await audit(
        session,
        action="external_ref.create",
        entity_type="case",
        entity_id=case.id,
        actor_id=None,
        after={
            "integration_id": str(integration.id),
            "external_ref": external_reference_id,
        },
    )
    return row


async def list_external_references(
    session: AsyncSession, case_id: uuid.UUID
) -> list[ExternalCaseReference]:
    return list(
        (
            await session.execute(
                select(ExternalCaseReference)
                .where(ExternalCaseReference.case_id == case_id)
                .order_by(ExternalCaseReference.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Sync Runs
# ---------------------------------------------------------------------------


async def create_sync_run(
    session: AsyncSession,
    *,
    integration_id: uuid.UUID,
    direction: str,
) -> SyncRun:
    row = SyncRun(integration_id=integration_id, direction=direction)
    session.add(row)
    return row


async def complete_sync_run(
    session: AsyncSession,
    run: SyncRun,
    *,
    status: str = "completed",
    records_processed: int = 0,
    records_succeeded: int = 0,
    records_failed: int = 0,
    errors: list[str] | None = None,
    external_version: str | None = None,
) -> SyncRun:
    run.status = status
    run.records_processed = records_processed
    run.records_succeeded = records_succeeded
    run.records_failed = records_failed
    run.errors = errors or []
    run.external_version = external_version
    run.completed_at = _utcnow()
    return run


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------


async def bulk_assign_cases(
    session: AsyncSession,
    *,
    case_ids: list[uuid.UUID],
    department_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str | None = None,
) -> dict[str, Any]:
    from tk_api.cases import service as cases_service

    dept = await departments_service.get_department(session, department_id)
    assigned = 0
    errors: list[str] = []
    for cid in case_ids:
        try:
            case = await cases_service.get_case(session, cid)
            await cases_service.assign(
                session,
                case,
                department_id=dept.id,
                reason=reason,
                actor=type("Actor", (), {"id": actor_id, "roles": []})(),
            )
            assigned += 1
        except Exception as e:
            errors.append(f"{cid}: {e}")

    log = BulkOperationLog(
        operation="bulk_assign",
        actor_id=actor_id,
        case_count=assigned,
        filters={"department_id": str(department_id), "case_ids": [str(c) for c in case_ids]},
        result_summary={"assigned": assigned, "errors": errors},
    )
    session.add(log)
    return {"assigned": assigned, "errors": errors}


# ---------------------------------------------------------------------------
# Government Analytics
# ---------------------------------------------------------------------------


async def get_department_dashboard(
    session: AsyncSession,
    department_id: uuid.UUID,
) -> dict[str, Any]:
    """Aggregate case metrics for a department dashboard."""

    stmt = (
        select(
            CivicCase.status,
            func.count(CivicCase.id).label("count"),
        )
        .where(CivicCase.primary_department_id == department_id)
        .group_by(CivicCase.status)
    )
    rows = (await session.execute(stmt)).all()
    status_counts = {str(row[0]): int(row[1]) for row in rows}

    total = sum(status_counts.values())
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
    open_count = sum(status_counts.get(s, 0) for s in open_statuses)
    resolved_count = status_counts.get("resolved", 0) + status_counts.get("closed", 0)

    # SLA breach count
    from tk_api.cases.models import SlaInstance

    breached_count = (
        await session.scalar(
            select(func.count(SlaInstance.id)).where(
                SlaInstance.status == "breached",
                SlaInstance.case_id.in_(
                    select(CivicCase.id).where(CivicCase.primary_department_id == department_id)
                ),
            )
        )
        or 0
    )

    # Escalation count
    from tk_api.cases.models import CaseEscalation

    escalation_count = (
        await session.scalar(
            select(func.count(CaseEscalation.id)).where(
                CaseEscalation.status == "active",
                CaseEscalation.case_id.in_(
                    select(CivicCase.id).where(CivicCase.primary_department_id == department_id)
                ),
            )
        )
        or 0
    )

    # Pending handoffs
    from tk_api.government.models import CaseHandoff

    pending_handoffs = (
        await session.scalar(
            select(func.count(CaseHandoff.id)).where(
                CaseHandoff.to_department_id == department_id,
                CaseHandoff.status == "pending",
            )
        )
        or 0
    )

    # Pending official responses
    from tk_api.government.models import OfficialResponse

    pending_responses = (
        await session.scalar(
            select(func.count(OfficialResponse.id)).where(
                OfficialResponse.department_id == department_id,
                OfficialResponse.is_current.is_(True),
                OfficialResponse.withdrawn.is_(False),
            )
        )
        or 0
    )

    return {
        "department_id": str(department_id),
        "total_cases": total,
        "open_cases": open_count,
        "resolved_cases": resolved_count,
        "breached_sla": breached_count,
        "active_escalations": escalation_count,
        "pending_handoffs": pending_handoffs,
        "pending_responses": pending_responses,
        "status_breakdown": status_counts,
        "methodology": {
            "definition": "Aggregate counts for cases assigned to this department.",
            "period": "All time (current snapshot).",
            "limitations": "Does not include historical data for reassigned cases.",
        },
    }


async def get_work_queue(
    session: AsyncSession,
    department_id: uuid.UUID,
    *,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Department-scoped work queue."""
    stmt = (
        select(CivicCase)
        .where(CivicCase.primary_department_id == department_id)
        .order_by(CivicCase.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(CivicCase.status == status)
    if priority is not None:
        stmt = stmt.where(CivicCase.priority == priority)
    cases = list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return [
        {
            "id": str(c.id),
            "case_no": c.case_no,
            "status": c.status,
            "priority": c.priority,
            "sla_status": c.sla_status,
            "sla_due_at": c.sla_due_at,
            "created_at": c.created_at,
        }
        for c in cases
    ]
