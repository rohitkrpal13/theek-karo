"""Government workflow API: routing, handoffs, official responses, workflow,
integrations, analytics (Phase 25).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from tk_api.api.deps import CurrentUser, DbSession
from tk_api.auth.authorization import require_permission
from tk_api.cases.models import CivicCase
from tk_api.core.errors import ApiError, NotFoundError
from tk_api.government import service as gov_service
from tk_api.government.models import (
    CaseHandoff,
    CaseRoute,
    OfficialResponse,
)
from tk_api.government.schemas import (
    CaseBulkAssign,
    CaseHandoffCreate,
    CaseHandoffResponse,
    CaseRouteAccept,
    CaseRouteCreate,
    ExternalReferenceCreate,
    GovernmentIntegrationCreate,
    GovernmentIntegrationUpdate,
    OfficialResponseCreate,
    OfficialResponseUpdate,
    OfficialResponseWithdraw,
    RoutingRuleCreate,
    WorkflowDefinitionCreate,
)

government_router = APIRouter(prefix="/api/v1/government", tags=["government"])

DepGovRead = Annotated[Any, Depends(require_permission("government.read"))]
DepGovManage = Annotated[Any, Depends(require_permission("government.manage"))]
DepGovRoute = Annotated[Any, Depends(require_permission("government.route"))]
DepGovHandoff = Annotated[Any, Depends(require_permission("government.handoff"))]
DepGovRespond = Annotated[Any, Depends(require_permission("government.respond"))]
DepGovIntegration = Annotated[Any, Depends(require_permission("government.integration"))]
DepGovAnalytics = Annotated[Any, Depends(require_permission("government.analytics"))]


def _parse_id(raw: str, *, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, "invalid_id") from exc


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


@government_router.get("/routing-rules", summary="List routing rules")
async def list_routing_rules(
    session: DbSession,
    _user: DepGovRead,
    category_id: Annotated[uuid.UUID | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    include_inactive: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    rows = await gov_service.list_routing_rules(
        session,
        category_id=category_id,
        department_id=department_id,
        include_inactive=include_inactive,
        limit=limit,
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "code": r.code,
                "name": r.name,
                "category_id": str(r.category_id) if r.category_id else None,
                "geography_id": str(r.geography_id) if r.geography_id else None,
                "target_department_id": str(r.target_department_id),
                "secondary_department_ids": [str(d) for d in (r.secondary_department_ids or [])],
                "priority_order": r.priority_order,
                "is_active": r.is_active,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@government_router.post("/routing-rules", status_code=201, summary="Create a routing rule")
async def create_routing_rule(
    body: RoutingRuleCreate,
    session: DbSession,
    _user: DepGovManage,
) -> dict[str, Any]:
    row = await gov_service.create_routing_rule(
        session,
        code=body.code,
        name=body.name,
        description=body.description,
        category_id=body.category_id,
        issue_type_id=body.issue_type_id,
        geography_id=body.geography_id,
        institution_type_id=body.institution_type_id,
        target_department_id=body.target_department_id,
        secondary_department_ids=body.secondary_department_ids,
        priority_order=body.priority_order,
    )
    await session.commit()
    return {"id": str(row.id), "code": row.code}


# ---------------------------------------------------------------------------
# Case Routing
# ---------------------------------------------------------------------------


@government_router.post(
    "/routes", status_code=201, summary="Create a routing recommendation for a case"
)
async def create_case_route(
    body: CaseRouteCreate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovRoute,
) -> dict[str, Any]:
    row = await gov_service.create_case_route(
        session,
        case_id=body.case_id,
        recommended_department_id=body.recommended_department_id,
        confidence=body.confidence,
        reason=body.reason,
        routing_source=body.routing_source,
        actor_id=user.id,
    )
    await session.commit()
    return {
        "id": str(row.id),
        "case_id": str(row.case_id),
        "recommended_department_id": str(row.recommended_department_id),
        "confidence": float(row.confidence),
        "routing_source": row.routing_source,
    }


@government_router.get("/cases/{case_id}/routes", summary="List routing decisions for a case")
async def list_case_routes(
    case_id: str,
    session: DbSession,
    _user: DepGovRead,
) -> dict[str, Any]:
    parsed = _parse_id(case_id, kind="case")
    rows = await gov_service.list_case_routes(session, parsed)
    return {
        "items": [
            {
                "id": str(r.id),
                "recommended_department_id": str(r.recommended_department_id),
                "confidence": float(r.confidence),
                "reason": r.reason,
                "routing_source": r.routing_source,
                "accepted": r.accepted,
                "accepted_at": r.accepted_at,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@government_router.post(
    "/routes/{route_id}/review", summary="Accept or reject a routing recommendation"
)
async def review_route(
    route_id: str,
    body: CaseRouteAccept,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovRoute,
) -> dict[str, Any]:
    parsed = _parse_id(route_id, kind="route")
    route = await session.get(CaseRoute, parsed)
    if route is None:
        raise NotFoundError("route not found", kind="route_not_found")
    row = await gov_service.accept_case_route(
        session,
        route,
        accepted=body.accepted,
        actor_id=user.id,
        rejection_reason=body.rejection_reason,
    )
    await session.commit()
    return {"id": str(row.id), "accepted": row.accepted}


# ---------------------------------------------------------------------------
# Case Handoffs
# ---------------------------------------------------------------------------


@government_router.post(
    "/handoffs", status_code=201, summary="Initiate a case handoff to another department"
)
async def create_handoff(
    body: CaseHandoffCreate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovHandoff,
) -> dict[str, Any]:
    row = await gov_service.create_handoff(
        session,
        case_id=body.case_id,
        to_department_id=body.to_department_id,
        reason=body.reason,
        actor_id=user.id,
    )
    await session.commit()
    return {
        "id": str(row.id),
        "case_id": str(row.case_id),
        "from_department_id": str(row.from_department_id),
        "to_department_id": str(row.to_department_id),
        "status": row.status,
    }


@government_router.post(
    "/handoffs/{handoff_id}/respond",
    summary="Accept or reject a handoff request",
)
async def respond_to_handoff(
    handoff_id: str,
    body: CaseHandoffResponse,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovHandoff,
) -> dict[str, Any]:
    parsed = _parse_id(handoff_id, kind="handoff")
    handoff = await session.get(CaseHandoff, parsed)
    if handoff is None:
        raise NotFoundError("handoff not found", kind="handoff_not_found")
    row = await gov_service.respond_to_handoff(
        session,
        handoff,
        accepted=body.accepted,
        actor_id=user.id,
        rejection_reason=body.rejection_reason,
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@government_router.get("/cases/{case_id}/handoffs", summary="List handoffs for a case")
async def list_handoffs(
    case_id: str,
    session: DbSession,
    _user: DepGovRead,
) -> dict[str, Any]:
    parsed = _parse_id(case_id, kind="case")
    rows = await gov_service.list_handoffs(session, parsed)
    return {
        "items": [
            {
                "id": str(h.id),
                "from_department_id": str(h.from_department_id),
                "to_department_id": str(h.to_department_id),
                "reason": h.reason,
                "status": h.status,
                "created_at": h.created_at,
            }
            for h in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Official Responses (versioned)
# ---------------------------------------------------------------------------


@government_router.post("/responses", status_code=201, summary="Submit an official response")
async def create_official_response(
    body: OfficialResponseCreate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovRespond,
) -> dict[str, Any]:
    case = await session.get(CivicCase, body.case_id)
    if case is None:
        raise NotFoundError("case not found", kind="case_not_found")
    department_id = case.primary_department_id
    if department_id is None:
        raise ApiError("case has no assigned department", 409, "no_department")
    row = await gov_service.create_official_response(
        session,
        case_id=body.case_id,
        department_id=department_id,
        author_id=user.id,
        summary=body.summary,
        action_taken=body.action_taken,
        current_status=body.current_status,
        next_step=body.next_step,
        estimated_completion=body.estimated_completion,
        external_reference_id=body.external_reference_id,
    )
    await session.commit()
    return {
        "id": str(row.id),
        "case_id": str(row.case_id),
        "version": row.version,
        "summary": row.summary,
    }


@government_router.get("/cases/{case_id}/responses", summary="List official responses for a case")
async def list_official_responses(
    case_id: str,
    session: DbSession,
    _user: DepGovRead,
    include_withdrawn: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    parsed = _parse_id(case_id, kind="case")
    rows = await gov_service.list_official_responses(
        session, parsed, include_withdrawn=include_withdrawn
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "version": r.version,
                "department_id": str(r.department_id),
                "author_id": str(r.author_id),
                "summary": r.summary,
                "action_taken": r.action_taken,
                "current_status": r.current_status,
                "next_step": r.next_step,
                "estimated_completion": r.estimated_completion,
                "external_reference_id": r.external_reference_id,
                "source": r.source,
                "is_current": r.is_current,
                "withdrawn": r.withdrawn,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@government_router.patch(
    "/responses/{response_id}",
    summary="Update an official response (creates new version)",
)
async def update_official_response(
    response_id: str,
    body: OfficialResponseUpdate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovRespond,
) -> dict[str, Any]:
    parsed = _parse_id(response_id, kind="response")
    response = await session.get(OfficialResponse, parsed)
    if response is None:
        raise NotFoundError("response not found", kind="response_not_found")
    row = await gov_service.update_official_response(
        session,
        response,
        author_id=user.id,
        summary=body.summary,
        action_taken=body.action_taken,
        current_status=body.current_status,
        next_step=body.next_step,
        estimated_completion=body.estimated_completion,
        change_reason=body.change_reason,
    )
    await session.commit()
    return {"id": str(row.id), "version": row.version}


@government_router.post(
    "/responses/{response_id}/withdraw",
    summary="Withdraw an official response",
)
async def withdraw_official_response(
    response_id: str,
    body: OfficialResponseWithdraw,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovRespond,
) -> dict[str, Any]:
    parsed = _parse_id(response_id, kind="response")
    response = await session.get(OfficialResponse, parsed)
    if response is None:
        raise NotFoundError("response not found", kind="response_not_found")
    row = await gov_service.withdraw_official_response(
        session, response, actor_id=user.id, reason=body.reason
    )
    await session.commit()
    return {"id": str(row.id), "withdrawn": row.withdrawn}


# ---------------------------------------------------------------------------
# Workflow Definitions
# ---------------------------------------------------------------------------


@government_router.get("/workflows", summary="List workflow definitions")
async def list_workflows(
    session: DbSession,
    _user: DepGovRead,
    category_id: Annotated[uuid.UUID | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, Any]:
    rows = await gov_service.list_workflow_definitions(
        session, category_id=category_id, department_id=department_id
    )
    return {
        "items": [
            {
                "id": str(w.id),
                "code": w.code,
                "name": w.name,
                "category_id": str(w.category_id) if w.category_id else None,
                "department_id": str(w.department_id) if w.department_id else None,
                "states": w.states,
                "is_default": w.is_default,
            }
            for w in rows
        ],
        "count": len(rows),
    }


@government_router.post("/workflows", status_code=201, summary="Create a workflow definition")
async def create_workflow(
    body: WorkflowDefinitionCreate,
    session: DbSession,
    _user: DepGovManage,
) -> dict[str, Any]:
    row = await gov_service.create_workflow_definition(
        session,
        code=body.code,
        name=body.name,
        description=body.description,
        category_id=body.category_id,
        department_id=body.department_id,
        states=body.states,
        transitions=body.transitions,
        required_roles=body.required_roles,
        is_default=body.is_default,
    )
    await session.commit()
    return {"id": str(row.id), "code": row.code}


# ---------------------------------------------------------------------------
# Government Integrations
# ---------------------------------------------------------------------------


@government_router.get("/integrations", summary="List government integrations")
async def list_integrations(
    session: DbSession,
    _user: DepGovRead,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    rows = await gov_service.list_government_integrations(
        session, department_id=department_id, status=status
    )
    return {
        "items": [
            {
                "id": str(g.id),
                "code": g.code,
                "name": g.name,
                "provider_type": g.provider_type,
                "department_id": str(g.department_id) if g.department_id else None,
                "status": g.status,
                "capabilities": g.capabilities,
                "last_sync_at": g.last_sync_at,
                "consecutive_failures": g.consecutive_failures,
            }
            for g in rows
        ],
        "count": len(rows),
    }


@government_router.post(
    "/integrations", status_code=201, summary="Register a government integration"
)
async def create_integration(
    body: GovernmentIntegrationCreate,
    session: DbSession,
    _user: DepGovIntegration,
) -> dict[str, Any]:
    row = await gov_service.create_government_integration(
        session,
        code=body.code,
        name=body.name,
        provider_type=body.provider_type,
        endpoint_url=body.endpoint_url,
        department_id=body.department_id,
        auth_type=body.auth_type,
        capabilities=body.capabilities,
        status_mapping=body.status_mapping,
    )
    await session.commit()
    return {"id": str(row.id), "code": row.code}


@government_router.get("/integrations/{integration_id}", summary="Integration detail")
async def get_integration(
    integration_id: str,
    session: DbSession,
    _user: DepGovRead,
) -> dict[str, Any]:
    parsed = _parse_id(integration_id, kind="integration")
    row = await gov_service.get_government_integration(session, parsed)
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "provider_type": row.provider_type,
        "endpoint_url": row.endpoint_url,
        "department_id": str(row.department_id) if row.department_id else None,
        "status": row.status,
        "auth_type": row.auth_type,
        "capabilities": row.capabilities,
        "status_mapping": row.status_mapping,
        "last_sync_at": row.last_sync_at,
        "last_sync_status": row.last_sync_status,
        "last_error": row.last_error,
        "consecutive_failures": row.consecutive_failures,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@government_router.patch(
    "/integrations/{integration_id}", summary="Update a government integration"
)
async def update_integration(
    integration_id: str,
    body: GovernmentIntegrationUpdate,
    session: DbSession,
    _user: DepGovIntegration,
) -> dict[str, Any]:
    parsed = _parse_id(integration_id, kind="integration")
    row = await gov_service.get_government_integration(session, parsed)
    updated = await gov_service.update_government_integration(
        session,
        row,
        name=body.name,
        endpoint_url=body.endpoint_url,
        status=body.status,
        capabilities=body.capabilities,
        status_mapping=body.status_mapping,
    )
    await session.commit()
    return {"id": str(updated.id), "status": updated.status}


# ---------------------------------------------------------------------------
# External Case References
# ---------------------------------------------------------------------------


@government_router.post(
    "/external-references", status_code=201, summary="Link a case to an external reference"
)
async def create_external_reference(
    body: ExternalReferenceCreate,
    session: DbSession,
    _user: DepGovIntegration,
) -> dict[str, Any]:
    row = await gov_service.create_external_reference(
        session,
        case_id=body.case_id,
        integration_id=body.integration_id,
        external_reference_id=body.external_reference_id,
        external_status=body.external_status,
    )
    await session.commit()
    return {
        "id": str(row.id),
        "external_reference_id": row.external_reference_id,
        "submission_status": row.submission_status,
    }


@government_router.get(
    "/cases/{case_id}/external-references",
    summary="List external references for a case",
)
async def list_external_references(
    case_id: str,
    session: DbSession,
    _user: DepGovRead,
) -> dict[str, Any]:
    parsed = _parse_id(case_id, kind="case")
    rows = await gov_service.list_external_references(session, parsed)
    return {
        "items": [
            {
                "id": str(r.id),
                "integration_id": str(r.integration_id),
                "external_reference_id": r.external_reference_id,
                "external_status": r.external_status,
                "mapped_status": r.mapped_status,
                "submission_status": r.submission_status,
                "last_synced_at": r.last_synced_at,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Dashboard & Analytics
# ---------------------------------------------------------------------------


@government_router.get("/dashboard/{department_id}", summary="Department dashboard metrics")
async def get_department_dashboard(
    department_id: str,
    session: DbSession,
    _user: DepGovAnalytics,
) -> dict[str, Any]:
    parsed = _parse_id(department_id, kind="department")
    return await gov_service.get_department_dashboard(session, parsed)


@government_router.get("/work-queue/{department_id}", summary="Department work queue")
async def get_work_queue(
    department_id: str,
    session: DbSession,
    _user: DepGovRead,
    status: Annotated[str | None, Query()] = None,
    priority: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    parsed = _parse_id(department_id, kind="department")
    items = await gov_service.get_work_queue(
        session, parsed, status=status, priority=priority, limit=limit, offset=offset
    )
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------


@government_router.post("/bulk/assign", summary="Bulk assign cases to a department")
async def bulk_assign(
    body: CaseBulkAssign,
    session: DbSession,
    user: CurrentUser,
    _perm: DepGovManage,
) -> dict[str, Any]:
    result = await gov_service.bulk_assign_cases(
        session,
        case_ids=body.case_ids,
        department_id=body.department_id,
        actor_id=user.id,
        reason=body.reason,
    )
    await session.commit()
    return result
