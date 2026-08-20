"""AI Observability (Phase 27).

Traces, cost tracking, health monitoring, circuit breaker, and AI quality dashboard.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai_platform.models import (
    AiAgentRun,
    AiCostRecord,
    AiEvalResult,
    AiTraceSpan,
)


async def get_ai_trace(session: AsyncSession, trace_id: uuid.UUID) -> dict[str, Any]:
    """Get full trace for an AI execution."""
    spans = (
        (
            await session.execute(
                select(AiTraceSpan)
                .where(AiTraceSpan.trace_id == trace_id)
                .order_by(AiTraceSpan.started_at.asc())
            )
        )
        .scalars()
        .all()
    )

    runs = (
        (
            await session.execute(
                select(AiAgentRun)
                .where(AiAgentRun.trace_id == trace_id)
                .order_by(AiAgentRun.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    return {
        "trace_id": str(trace_id),
        "spans": [
            {
                "id": str(s.id),
                "type": s.span_type,
                "name": s.name,
                "status": s.status,
                "latency_ms": s.latency_ms,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
            for s in spans
        ],
        "agent_runs": [
            {
                "id": str(r.id),
                "agent": r.agent_code,
                "status": r.status,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "cost_usd": r.cost_usd,
                "latency_ms": r.latency_ms,
            }
            for r in runs
        ],
    }


async def get_ai_cost_summary(
    session: AsyncSession,
    *,
    days: int = 30,
    agent_code: str | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate AI cost metrics over a period."""
    since = datetime.now(UTC) - timedelta(days=min(days, 365))

    stmt = select(AiCostRecord).where(AiCostRecord.date >= since)
    if agent_code:
        stmt = stmt.where(AiCostRecord.agent_code == agent_code)
    if model_id:
        stmt = stmt.where(AiCostRecord.model_id == model_id)

    rows = (await session.execute(stmt)).scalars().all()

    totals = {
        "request_count": sum(r.request_count for r in rows),
        "tokens_in": sum(r.tokens_in for r in rows),
        "tokens_out": sum(r.tokens_out for r in rows),
        "cost_usd": sum(r.cost_usd for r in rows),
    }

    by_model: dict[str, dict[str, Any]] = {}
    for r in rows:
        entry = by_model.setdefault(r.model_id, {"requests": 0, "cost_usd": 0, "tokens": 0})
        entry["requests"] += r.request_count
        entry["cost_usd"] += r.cost_usd
        entry["tokens"] += r.tokens_in + r.tokens_out

    by_agent: dict[str, dict[str, Any]] = {}
    for r in rows:
        entry = by_agent.setdefault(r.agent_code, {"requests": 0, "cost_usd": 0})
        entry["requests"] += r.request_count
        entry["cost_usd"] += r.cost_usd

    return {
        "period_days": days,
        "totals": totals,
        "by_model": by_model,
        "by_agent": by_agent,
    }


async def get_ai_health(
    session: AsyncSession,
    providers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """AI system health status."""
    now = datetime.now(UTC)
    last_hour = now - timedelta(hours=1)

    # Recent runs
    recent_runs = (
        await session.scalar(
            select(func.count(AiAgentRun.id)).where(AiAgentRun.created_at >= last_hour)
        )
        or 0
    )

    recent_failures = (
        await session.scalar(
            select(func.count(AiAgentRun.id)).where(
                AiAgentRun.created_at >= last_hour,
                AiAgentRun.status == "failed",
            )
        )
        or 0
    )

    # Provider health
    provider_health = {}
    if providers:
        for name, provider in providers.items():
            provider_health[name] = (
                provider.check_health()
                if hasattr(provider, "check_health")
                else {"status": "unknown"}
            )

    return {
        "status": "healthy" if recent_failures == 0 else "degraded",
        "recent_runs_1h": recent_runs,
        "recent_failures_1h": recent_failures,
        "failure_rate": round(recent_failures / recent_runs, 4) if recent_runs > 0 else 0,
        "providers": provider_health,
        "checked_at": now.isoformat(),
    }


async def get_evaluation_summary(
    session: AsyncSession,
    *,
    eval_type: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """Aggregate evaluation results."""
    since = datetime.now(UTC) - timedelta(days=min(days, 365))
    stmt = select(AiEvalResult).where(AiEvalResult.created_at >= since)
    if eval_type:
        stmt = stmt.where(AiEvalResult.eval_type == eval_type)

    rows = (await session.execute(stmt)).scalars().all()

    total = len(rows)
    passed = sum(1 for r in rows if r.passed)

    by_type: dict[str, dict[str, int]] = {}
    for r in rows:
        entry = by_type.setdefault(r.eval_type, {"total": 0, "passed": 0})
        entry["total"] += 1
        if r.passed:
            entry["passed"] += 1

    return {
        "period_days": days,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total > 0 else 0,
        "by_type": by_type,
    }


async def record_cost(
    session: AsyncSession,
    *,
    agent_code: str,
    model_id: str,
    provider: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
) -> AiCostRecord:
    """Record a cost entry for daily aggregation."""
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    existing = await session.scalar(
        select(AiCostRecord).where(
            AiCostRecord.date == day_start,
            AiCostRecord.agent_code == agent_code,
            AiCostRecord.model_id == model_id,
            AiCostRecord.provider == provider,
        )
    )

    if existing:
        existing.request_count += 1
        existing.tokens_in += tokens_in
        existing.tokens_out += tokens_out
        existing.cost_usd += cost_usd
        # Running average latency
        existing.avg_latency_ms = (
            existing.avg_latency_ms * (existing.request_count - 1) + latency_ms
        ) / existing.request_count
        return existing

    row = AiCostRecord(
        date=day_start,
        agent_code=agent_code,
        model_id=model_id,
        provider=provider,
        request_count=1,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        avg_latency_ms=float(latency_ms),
    )
    session.add(row)
    return row
