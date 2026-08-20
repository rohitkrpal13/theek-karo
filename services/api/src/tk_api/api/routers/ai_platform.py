"""AI Platform API: agents, skills, evaluation, observability, governance (Phase 27)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from tk_api.ai.providers import StubLlmProvider
from tk_api.ai.registry import ModelRouter
from tk_api.ai_platform import agents as agent_module
from tk_api.ai_platform import evaluation as eval_module
from tk_api.ai_platform import observability as obs_module
from tk_api.ai_platform import skills as skill_module
from tk_api.ai_platform.gateway import AIGateway, AIGatewayRequest
from tk_api.ai_platform.models import (
    AiAgentRun,
    AiEvalResult,
)
from tk_api.api.deps import CurrentUser, DbSession
from tk_api.auth.authorization import require_permission
from tk_api.core.errors import ApiError

ai_platform_router = APIRouter(prefix="/api/v1/ai-platform", tags=["ai-platform"])

DepAiRead = Annotated[Any, Depends(require_permission("ai.use"))]
DepAiAdmin = Annotated[Any, Depends(require_permission("ai.admin"))]


def _parse_id(raw: str, *, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, "invalid_id") from exc


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------


@ai_platform_router.post("/gateway/chat", summary="AI Gateway chat endpoint")
async def gateway_chat(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepAiRead,
) -> dict[str, Any]:
    gateway = AIGateway(provider=StubLlmProvider(), router=ModelRouter())
    request = AIGatewayRequest(
        user_id=user.id,
        task=body.get("task", "chat_assistant"),
        input_data=body,
        language=body.get("language", "en"),
        risk_level=body.get("risk_level", "low"),
    )
    response = await gateway.process(session, request)
    return {
        "request_id": str(response.request_id),
        "status": response.status,
        "answer": response.text,
        "model_id": response.model_id,
        "provider": response.provider,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "cost_usd": response.cost_usd,
        "latency_ms": response.latency_ms,
        "error": response.error,
    }


@ai_platform_router.get("/gateway/health", summary="AI Gateway health")
async def gateway_health(
    _user: DepAiRead,
) -> dict[str, Any]:
    gateway = AIGateway(provider=StubLlmProvider(), router=ModelRouter())
    return gateway.get_health()


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@ai_platform_router.get("/agents", summary="List available AI agents")
async def list_agents(
    _user: DepAiRead,
) -> dict[str, Any]:
    agent_router = agent_module.build_default_agents()
    return {"agents": agent_router.list_agents(), "count": len(agent_router.list_agents())}


@ai_platform_router.post("/agents/execute", summary="Execute an AI agent")
async def execute_agent(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepAiRead,
) -> dict[str, Any]:
    agent_code = body.get("agent_code", "civic_assistant")
    agent_router = agent_module.build_default_agents()
    agent = agent_router._agents.get(agent_code)
    if not agent:
        raise ApiError(f"agent '{agent_code}' not found", 404, "agent_not_found")

    result = await agent.execute(
        session,
        input_data=body.get("input_data", {}),
        context=body.get("context"),
        user_id=user.id,
    )
    return {
        "agent": agent_code,
        "status": result.status,
        "output": result.output,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms,
        "requires_approval": result.requires_approval,
        "error": result.error,
    }


@ai_platform_router.get("/agents/{agent_code}", summary="Agent detail")
async def get_agent(
    agent_code: str,
    _user: DepAiRead,
) -> dict[str, Any]:
    agent_router = agent_module.build_default_agents()
    agent = agent_router._agents.get(agent_code)
    if not agent:
        raise ApiError(f"agent '{agent_code}' not found", 404, "agent_not_found")
    return {
        "code": agent.code,
        "name": agent.name,
        "description": agent.description,
        "risk_level": agent.risk_level,
        "allowed_tools": agent.allowed_tools,
        "max_execution_time_s": agent.max_execution_time_s,
        "max_tool_calls": agent.max_tool_calls,
        "max_tokens": agent.max_tokens,
        "cost_budget_usd": agent.cost_budget_usd,
    }


# ---------------------------------------------------------------------------
# Multi-Agent Workflows
# ---------------------------------------------------------------------------


@ai_platform_router.get("/workflows", summary="List multi-agent workflows")
async def list_workflows(
    _user: DepAiRead,
) -> dict[str, Any]:
    agent_router = agent_module.build_default_agents()
    orchestrator = skill_module.MultiAgentOrchestrator(agent_router)
    return {"workflows": orchestrator.list_workflows(), "count": len(orchestrator.list_workflows())}


@ai_platform_router.post("/workflows/execute", summary="Execute a multi-agent workflow")
async def execute_workflow(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepAiRead,
) -> dict[str, Any]:
    workflow_code = body.get("workflow_code")
    if not workflow_code:
        raise ApiError("workflow_code is required", 422, "missing_field")

    agent_router = agent_module.build_default_agents()
    orchestrator = skill_module.MultiAgentOrchestrator(agent_router)
    result = await orchestrator.execute_workflow(
        session,
        workflow_code=workflow_code,
        input_data=body.get("input_data", {}),
        user_id=user.id,
    )
    return result


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


@ai_platform_router.get("/skills", summary="List AI skills")
async def list_skills(
    _user: DepAiRead,
) -> dict[str, Any]:
    registry = skill_module.SkillRegistry()
    skills = registry.list_skills()
    return {
        "skills": [
            {
                "code": s.code,
                "name": s.name,
                "description": s.description,
                "tools": s.tools,
                "risk_level": s.risk_level,
                "status": s.status.value,
            }
            for s in skills
        ],
        "count": len(skills),
    }


@ai_platform_router.post("/skills/compose", summary="Compose multiple skills")
async def compose_skills(
    body: dict[str, Any],
    _user: DepAiRead,
) -> dict[str, Any]:
    skill_codes = body.get("skill_codes", [])
    registry = skill_module.SkillRegistry()
    result = registry.compose(skill_codes)
    return result


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@ai_platform_router.get("/evaluations", summary="List evaluation results")
async def list_evaluations(
    session: DbSession,
    _user: DepAiAdmin,
    eval_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    from sqlalchemy import select

    stmt = select(AiEvalResult).order_by(AiEvalResult.created_at.desc())
    if eval_type:
        stmt = stmt.where(AiEvalResult.eval_type == eval_type)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return {
        "items": [
            {
                "id": str(e.id),
                "eval_type": e.eval_type,
                "target_code": e.target_code,
                "test_case_id": e.test_case_id,
                "passed": e.passed,
                "score": e.score,
                "metrics": e.metrics,
                "run_at": e.run_at,
            }
            for e in rows
        ],
        "count": len(rows),
    }


@ai_platform_router.get("/evaluations/summary", summary="Evaluation summary")
async def evaluation_summary(
    session: DbSession,
    _user: DepAiAdmin,
    eval_type: Annotated[str | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, Any]:
    return await obs_module.get_evaluation_summary(session, eval_type=eval_type, days=days)


@ai_platform_router.get("/evaluations/test-cases", summary="List golden test cases")
async def list_test_cases(
    _user: DepAiAdmin,
    eval_type: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    framework = eval_module.EvaluationFramework()
    cases = framework.list_test_cases(eval_type=eval_type)
    return {
        "test_cases": [
            {
                "test_id": c.test_id,
                "eval_type": c.eval_type,
                "target_code": c.target_code,
                "tags": c.tags,
                "risk_level": c.risk_level,
            }
            for c in cases
        ],
        "count": len(cases),
    }


@ai_platform_router.post("/evaluations/run", summary="Run evaluation suite")
async def run_evaluation(
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepAiAdmin,
) -> dict[str, Any]:
    eval_type = body.get("eval_type")
    agent_router = agent_module.build_default_agents()
    framework = eval_module.EvaluationFramework()
    result = await framework.run_full_evaluation(session, agent_router, eval_type=eval_type)
    await session.commit()
    return result


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@ai_platform_router.get("/traces/{trace_id}", summary="Get AI trace")
async def get_trace(
    trace_id: str,
    session: DbSession,
    _user: DepAiAdmin,
) -> dict[str, Any]:
    return await obs_module.get_ai_trace(session, _parse_id(trace_id, kind="trace"))


@ai_platform_router.get("/costs", summary="AI cost summary")
async def cost_summary(
    session: DbSession,
    _user: DepAiAdmin,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    agent_code: Annotated[str | None, Query()] = None,
    model_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return await obs_module.get_ai_cost_summary(
        session, days=days, agent_code=agent_code, model_id=model_id
    )


@ai_platform_router.get("/health", summary="AI system health")
async def ai_health(
    session: DbSession,
    _user: DepAiRead,
) -> dict[str, Any]:
    return await obs_module.get_ai_health(session)


# ---------------------------------------------------------------------------
# Agent Runs
# ---------------------------------------------------------------------------


@ai_platform_router.get("/runs", summary="List AI agent runs")
async def list_runs(
    session: DbSession,
    _user: DepAiAdmin,
    agent_code: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    from sqlalchemy import select

    stmt = select(AiAgentRun).order_by(AiAgentRun.created_at.desc())
    if agent_code:
        stmt = stmt.where(AiAgentRun.agent_code == agent_code)
    if status:
        stmt = stmt.where(AiAgentRun.status == status)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "trace_id": str(r.trace_id),
                "agent_code": r.agent_code,
                "task": r.task,
                "status": r.status,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "cost_usd": r.cost_usd,
                "latency_ms": r.latency_ms,
                "requires_approval": r.requires_approval,
                "approval_status": r.approval_status,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@ai_platform_router.get("/runs/{run_id}", summary="Agent run detail")
async def get_run(
    run_id: str,
    session: DbSession,
    _user: DepAiAdmin,
) -> dict[str, Any]:

    parsed = _parse_id(run_id, kind="run")
    run = await session.get(AiAgentRun, parsed)
    if run is None:
        raise ApiError("run not found", 404, "run_not_found")
    return {
        "id": str(run.id),
        "trace_id": str(run.trace_id),
        "agent_code": run.agent_code,
        "task": run.task,
        "input_data": run.input_data,
        "output_data": run.output_data,
        "tools_called": run.tools_called,
        "model_calls": run.model_calls,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "cost_usd": run.cost_usd,
        "latency_ms": run.latency_ms,
        "status": run.status,
        "error": run.error,
        "risk_level": run.risk_level,
        "requires_approval": run.requires_approval,
        "approval_status": run.approval_status,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


@ai_platform_router.post("/runs/{run_id}/approve", summary="Approve an AI agent run")
async def approve_run(
    run_id: str,
    body: dict[str, Any],
    session: DbSession,
    user: CurrentUser,
    _perm: DepAiAdmin,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    parsed = _parse_id(run_id, kind="run")
    run = await session.get(AiAgentRun, parsed)
    if run is None:
        raise ApiError("run not found", 404, "run_not_found")
    if run.approval_status != "pending":
        raise ApiError("run is not pending approval", 409, "not_pending")

    decision = body.get("decision", "approved")
    run.approval_status = decision
    run.approved_by = user.id
    run.approved_at = datetime.now(UTC)
    await session.commit()
    return {"id": str(run.id), "approval_status": run.approval_status}
