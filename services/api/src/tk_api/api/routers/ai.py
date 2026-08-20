"""AI endpoints (API.md §6, §13): Conversational Civic Assistant, Classification,
Duplicate Checking, Digital Twin Summaries, Translation, Tool Registry, Citations, and Usage.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from tk_api.ai import duplicates as ai_duplicates
from tk_api.ai.analysis import citations_for_annotation
from tk_api.ai.models import AiFeedback
from tk_api.ai.orchestrator import AgentOrchestrator
from tk_api.ai.schemas import (
    AiFeedbackCreate,
    AiUsageStatsRead,
    CivicChatRequest,
    CivicChatResponse,
    DuplicateAnalysisOutput,
    InstitutionSummaryOutput,
    ReportClassificationOutput,
    TranslationRequest,
    TranslationResponse,
)
from tk_api.ai.tools import ToolRegistry
from tk_api.api.deps import DbSession, OptionalUser, require_active
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit

ai_router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

ReviewerUser = Annotated[Any, Depends(require_active("volunteer", "official", "admin"))]
AdminUser = Annotated[Any, Depends(require_active("admin", "analyst"))]


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


# -----------------------------------------------------------------------------
# 1. Conversational Civic Research Assistant
# -----------------------------------------------------------------------------


@ai_router.post("/chat", response_model=CivicChatResponse, summary="Civic research assistant chat")
async def chat_assistant(
    body: CivicChatRequest,
    request: Request,
    session: DbSession,
    user: OptionalUser = None,
) -> CivicChatResponse:
    await rate_limit(
        request, bucket="ai_chat", key=f"chat:{client_ip(request)}", limit=30, window_seconds=60
    )
    # daily spend cap (Step 12): per authenticated user, else per IP
    identity = str(user.id) if user else client_ip(request)
    await rate_limit(
        request,
        bucket="ai_chat_daily",
        key=f"chat_daily:{identity}",
        limit=request.app.state.settings.ai_daily_chat_limit,
        window_seconds=86400,
    )
    orch = AgentOrchestrator(session)
    user_id = user.id if user else None
    access_level = "AUTHENTICATED" if user else "PUBLIC"
    if user:
        codes = set(user.role_codes())
        if codes & {"admin", "super_admin"}:
            access_level = "ADMIN"
        elif codes & {"moderator", "official", "analyst"}:
            access_level = "MODERATOR"

    return await orch.chat_civic_research(body, user_id=user_id, access_level=access_level)


@ai_router.post(
    "/research",
    summary="Structured civic research query (Phase 15): validated analytics aggregation",
    description=(
        "Runs a structured, validated research query against platform data: filtered "
        "counts, resolution/verification splits, time series trends, top categories and "
        "top institutions. No raw SQL or unrestricted aggregation is exposed; results "
        "carry data-coverage interpretation and methodology notes."
    ),
)
async def ai_research_endpoint(
    body: dict[str, Any],
    request: Request,
    session: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="ai_research",
        key=f"research:{client_ip(request)}",
        limit=60,
        window_seconds=60,
    )
    from tk_api.ai.tools import ToolRegistry

    registry = ToolRegistry()
    spec = registry.get_tool("research_query")
    if spec is None:
        raise ApiError("research tool unavailable", 503, "AI_INTERNAL_ERROR")
    return await registry.execute(session, "research_query", body)


# -----------------------------------------------------------------------------
# 2. Report Classification & Duplicate Detection
# -----------------------------------------------------------------------------


@ai_router.post(
    "/classify-report",
    response_model=ReportClassificationOutput,
    summary="Suggest category, issue type, and missing info for report intake",
)
async def classify_report(
    body: dict[str, Any],
    request: Request,
    session: DbSession,
) -> ReportClassificationOutput:
    await rate_limit(
        request,
        bucket="ai_classify",
        key=f"classify:{client_ip(request)}",
        limit=60,
        window_seconds=60,
    )
    title = body.get("title", "")
    description = body.get("description", "")
    fields = body.get("fields")
    orch = AgentOrchestrator(session)
    return await orch.classify_report(title, description, fields)


@ai_router.post(
    "/duplicate-check",
    response_model=DuplicateAnalysisOutput,
    summary="Analyze textual and geographic similarity between report candidates",
)
async def check_duplicates(
    body: dict[str, Any],
    request: Request,
    session: DbSession,
) -> DuplicateAnalysisOutput:
    await rate_limit(
        request, bucket="ai_dup", key=f"dup:{client_ip(request)}", limit=60, window_seconds=60
    )
    orch = AgentOrchestrator(session)
    return await orch.check_duplicates(
        target_title=body.get("target_title", ""),
        target_description=body.get("target_description", ""),
        candidate_title=body.get("candidate_title", ""),
        candidate_description=body.get("candidate_description", ""),
        candidate_status=body.get("candidate_status", "submitted"),
        candidate_ticket_no=body.get("candidate_ticket_no", "TK-0000"),
        distance_m=float(body.get("distance_m", 0.0)),
    )


# -----------------------------------------------------------------------------
# 3. Institution Digital Twin Summary
# -----------------------------------------------------------------------------


@ai_router.get(
    "/institutions/{institution_id}/summary",
    response_model=InstitutionSummaryOutput,
    summary="Generate evidence-grounded situation summary for an institution",
)
async def institution_summary(
    institution_id: str,
    request: Request,
    session: DbSession,
) -> InstitutionSummaryOutput:
    await rate_limit(
        request,
        bucket="ai_inst_sum",
        key=f"inst_sum:{client_ip(request)}",
        limit=40,
        window_seconds=60,
    )
    inst_uuid = _parse_id(institution_id, kind="institution", error_kind="invalid_institution_id")
    orch = AgentOrchestrator(session)
    return await orch.summarize_institution(inst_uuid)


# -----------------------------------------------------------------------------
# 4. Multilingual Translation
# -----------------------------------------------------------------------------


@ai_router.post(
    "/translate",
    response_model=TranslationResponse,
    summary="Translate text across 14 Indian languages preserving identifiers",
)
async def translate(
    body: TranslationRequest,
    request: Request,
    session: DbSession,
) -> TranslationResponse:
    await rate_limit(
        request, bucket="ai_trans", key=f"trans:{client_ip(request)}", limit=60, window_seconds=60
    )
    orch = AgentOrchestrator(session)
    return await orch.translate_text(
        text=body.text,
        source_language=body.source_language,
        target_language=body.target_language,
    )


# -----------------------------------------------------------------------------
# 5. Tool Registry / MCP Schema Manifest
# -----------------------------------------------------------------------------


@ai_router.get(
    "/tools",
    summary="List MCP-compatible schema definitions for read-only civic tools",
)
async def list_ai_tools() -> dict[str, Any]:
    registry = ToolRegistry()
    return {"tools": registry.list_tools()}


# -----------------------------------------------------------------------------
# 6. Citations, Feedback & Human Review Queue
# -----------------------------------------------------------------------------


@ai_router.get("/citations/{annotation_id}", summary="Citation detail w/ source provenance")
async def get_citations(annotation_id: str, session: DbSession) -> list[dict[str, Any]]:
    parsed = _parse_id(annotation_id, kind="annotation", error_kind="invalid_annotation_id")
    return await citations_for_annotation(session, parsed)


@ai_router.post("/feedback", summary="Submit user feedback on AI responses")
async def submit_feedback(
    body: AiFeedbackCreate,
    session: DbSession,
    user: Annotated[Any, Depends(require_active())],
) -> dict[str, Any]:
    feedback = AiFeedback(
        id=uuid.uuid4(),
        ai_output_id=body.ai_output_id or uuid.uuid4(),
        user_id=user.id,
        rating=body.rating,
        comment=f"[{body.feedback_type}] {body.comment or ''}".strip(),
    )
    session.add(feedback)
    await session.commit()
    return {"status": "success", "feedback_id": str(feedback.id)}


@ai_router.get("/human-review-queue", summary="Pending AI-reviewed decisions")
async def review_queue(
    session: DbSession,
    user: ReviewerUser,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    return {"items": await ai_duplicates.review_queue(session, limit=limit), "next_cursor": None}


@ai_router.post("/reviews/{review_id}/decision", summary="Approve/reject an AI decision (audited)")
async def decide_review(
    review_id: str,
    body: dict[str, Any],
    request: Request,
    user: ReviewerUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai", key=f"review:{client_ip(request)}", limit=20, window_seconds=60
    )
    approve = body.get("approve")
    if not isinstance(approve, bool):
        raise ApiError("approve (bool) is required", 422, "invalid_payload")
    reason = body.get("reason")
    parsed = _parse_id(review_id, kind="review", error_kind="invalid_review_id")
    return await ai_duplicates.decide_review(
        session,
        review_id=parsed,
        approve=approve,
        reason=reason if isinstance(reason, str) and reason else None,
        reviewer=user,
        request=request,
    )


# -----------------------------------------------------------------------------
# 7. Conversation History (Phase 8)
# -----------------------------------------------------------------------------


@ai_router.get("/conversations", summary="List user's recent conversations")
async def list_conversations(
    session: DbSession,
    user: Annotated[Any, Depends(require_active())],
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    from tk_api.ai.models import AiConversation
    from sqlalchemy import select

    stmt = (
        select(AiConversation)
        .where(AiConversation.user_id == user.id)
        .order_by(AiConversation.updated_at.desc())
        .limit(limit)
    )
    convos = (await session.execute(stmt)).scalars().all()
    return {
        "conversations": [
            {
                "id": str(c.id),
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in convos
        ],
        "count": len(convos),
    }


@ai_router.get("/conversations/{conversation_id}/messages", summary="Get conversation message history")
async def get_conversation_messages(
    conversation_id: str,
    session: DbSession,
    user: Annotated[Any, Depends(require_active())],
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    from tk_api.ai.models import AiMessage
    from sqlalchemy import select

    conv_uuid = _parse_id(conversation_id, kind="conversation", error_kind="invalid_conversation_id")
    stmt = (
        select(AiMessage)
        .where(AiMessage.conversation_id == conv_uuid)
        .order_by(AiMessage.created_at.asc())
        .limit(limit)
    )
    messages = (await session.execute(stmt)).scalars().all()
    return {
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "count": len(messages),
    }


@ai_router.post(
    "/conversations",
    status_code=201,
    summary="Create a new conversation",
)
async def create_conversation(
    body: dict[str, Any],
    session: DbSession,
    user: Annotated[Any, Depends(require_active())],
) -> dict[str, Any]:
    """Create a new conversation container for multi-turn chat."""
    from tk_api.ai.models import AiConversation
    from datetime import UTC, datetime

    title = body.get("title", "New Conversation")
    conversation = AiConversation(
        user_id=user.id,
        session_id=body.get("session_id"),
        title=title,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(conversation)
    await session.flush()
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
    }


@ai_router.post(
    "/conversations/{conversation_id}/messages",
    status_code=201,
    summary="Save a message to a conversation",
)
async def save_conversation_message(
    conversation_id: str,
    body: dict[str, Any],
    session: DbSession,
    user: Annotated[Any, Depends(require_active())],
) -> dict[str, Any]:
    """Save a message (user or assistant) to a conversation for history."""
    from tk_api.ai.models import AiConversation, AiMessage
    from datetime import UTC, datetime

    conv_uuid = _parse_id(conversation_id, kind="conversation", error_kind="invalid_conversation_id")
    conv = await session.get(AiConversation, conv_uuid)
    if conv is None or (conv.user_id and str(conv.user_id) != str(user.id)):
        raise ApiError("conversation not found", 404, "conversation_not_found")

    role = body.get("role", "user")
    content = body.get("content", "")
    if not content:
        raise ApiError("content is required", 422, "invalid_payload")

    message = AiMessage(
        conversation_id=conv_uuid,
        role=role,
        content=content,
        created_at=datetime.now(UTC),
    )
    session.add(message)

    # Update conversation timestamp
    conv.updated_at = datetime.now(UTC)
    await session.flush()

    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


# -----------------------------------------------------------------------------
# 8. Phase 9 — Agentic Triage, Recidivism & Moderation
# -----------------------------------------------------------------------------


@ai_router.post(
    "/triage/{report_id}",
    summary="Run triage agent on a report (advisory — no status changes)",
)
async def triage_report(
    report_id: str,
    request: Request,
    session: DbSession,
    user: Annotated[Any, Depends(require_active("moderator", "official", "admin"))],
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai_triage", key=f"triage:{client_ip(request)}", limit=30, window_seconds=60
    )
    from tk_api.ai.triage import triage_report as do_triage

    rid = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await do_triage(session, report_id=rid)


@ai_router.post(
    "/triage/batch",
    summary="Batch triage multiple reports",
)
async def batch_triage_reports(
    body: dict[str, Any],
    request: Request,
    session: DbSession,
    user: Annotated[Any, Depends(require_active("moderator", "admin"))],
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai_triage", key=f"triage_batch:{client_ip(request)}", limit=10, window_seconds=60
    )
    from tk_api.ai.triage import batch_triage

    report_ids_raw = body.get("report_ids", [])
    report_ids = [_parse_id(r, kind="report", error_kind="invalid_report_id") for r in report_ids_raw[:10]]
    return await batch_triage(session, report_ids=report_ids)


@ai_router.get(
    "/recidivism",
    summary="Detect recurring civic issues (recidivism analytics)",
)
async def get_recidivism(
    request: Request,
    session: DbSession,
    geography_id: Annotated[uuid.UUID | None, Query()] = None,
    category_slug: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai_recidivism", key=f"recidivism:{client_ip(request)}", limit=30, window_seconds=60
    )
    from tk_api.ai.recidivism import detect_recidivism

    return await detect_recidivism(
        session,
        geography_id=geography_id,
        category_slug=category_slug,
        limit=limit,
    )


@ai_router.get(
    "/recidivism/summary",
    summary="Recidivism analytics summary",
)
async def get_recidivism_summary(
    request: Request,
    session: DbSession,
    geography_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai_recidivism", key=f"recidivism_sum:{client_ip(request)}", limit=30, window_seconds=60
    )
    from tk_api.ai.recidivism import get_recidivism_summary as do_summary

    return await do_summary(session, geography_id=geography_id)


@ai_router.post(
    "/moderate",
    summary="AI-assisted content moderation (advisory — no auto-removal)",
)
async def moderate_content_endpoint(
    body: dict[str, Any],
    request: Request,
    session: DbSession,
    user: Annotated[Any, Depends(require_active("moderator", "admin"))],
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai_moderate", key=f"moderate:{client_ip(request)}", limit=60, window_seconds=60
    )
    from tk_api.ai.moderation import moderate_content

    content = body.get("content", "")
    content_type = body.get("content_type", "comment")
    content_id_str = body.get("content_id")
    content_id = None
    if content_id_str:
        content_id = _parse_id(content_id_str, kind="content", error_kind="invalid_content_id")
    return await moderate_content(
        session,
        content=content,
        content_type=content_type,
        content_id=content_id,
    )


@ai_router.get(
    "/moderate/report/{report_id}",
    summary="Moderate all comments on a report",
)
async def moderate_report_comments_endpoint(
    report_id: str,
    request: Request,
    session: DbSession,
    user: Annotated[Any, Depends(require_active("moderator", "admin"))],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai_moderate", key=f"mod_report:{client_ip(request)}", limit=20, window_seconds=60
    )
    from tk_api.ai.moderation import moderate_report_comments

    rid = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await moderate_report_comments(session, report_id=rid, limit=limit)


# -----------------------------------------------------------------------------
# 9. Admin Cost & Token Usage Analytics
# -----------------------------------------------------------------------------


@ai_router.get(
    "/admin/usage",
    response_model=AiUsageStatsRead,
    summary="Platform-wide AI token consumption, latency, and cost report",
)
async def get_usage_report(
    session: DbSession,
    admin: AdminUser,
) -> AiUsageStatsRead:
    orch = AgentOrchestrator(session)
    return await orch.get_usage_statistics()
