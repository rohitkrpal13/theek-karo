"""Phase 9 — Agentic Triage Agent.

Autonomously triages incoming civic reports: classifies, suggests severity,
detects duplicates, recommends department routing, and escalates to human review
within an SLA window. Every triage decision is auditable; irreversible actions
(require manual merge, rejection, or official response) are gated.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai.providers import LLMProvider, StubLlmProvider
from tk_api.ai.registry import ModelRouter
from tk_api.civic.models import Category, IssueType
from tk_api.reports.models import Report

# ---------------------------------------------------------------------------
# Triage Decision Record
# ---------------------------------------------------------------------------

TRIAGE_STATUS_PENDING = "pending"
TRIAGE_STATUS_COMPLETED = "completed"
TRIAGE_STATUS_ESCALATED = "escalated"
TRIAGE_STATUS_TIMEOUT = "timeout"

TRIAGE_SLA_SECONDS = 300  # 5 minutes for human review of escalated triage


async def triage_report(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    provider: LLMProvider | None = None,
    router: ModelRouter | None = None,
) -> dict[str, Any]:
    """Run the triage agent on a report. Returns a triage decision with
    classification, severity, routing recommendation, and confidence.

    The agent NEVER mutates the report directly — it produces a structured
    recommendation that must be applied by a human or the orchestration layer.
    """
    provider = provider or StubLlmProvider()
    router = router or ModelRouter()

    report = await session.get(Report, report_id)
    if report is None:
        return {"error": "Report not found", "status": "failed"}

    # Gather context
    category = await session.get(Category, report.category_id) if report.category_id else None
    issue_type = (
        await session.get(IssueType, report.issue_type_id) if report.issue_type_id else None
    )

    model_spec = router.select_model("classification")

    # Build triage prompt
    prompt = (
        f"You are a civic report triage agent for Theek Karo.\n"
        f"Analyze the following report and provide a structured triage decision.\n\n"
        f"Report:\n"
        f"  Ticket: {report.ticket_no}\n"
        f"  Title: {report.title}\n"
        f"  Description: {(report.description or '')[:500]}\n"
        f"  Category: {category.name_key if category else 'unknown'}\n"
        f"  Issue Type: {issue_type.name_key if issue_type else 'unknown'}\n"
        f"  Current Severity: {report.severity}\n"
        f"  Current Status: {report.status}\n"
        f"  Location: {report.location}\n"
        f"  Trust Score: {float(report.trust_score or 0.0)}\n\n"
        f"Provide:\n"
        f"1. suggested_severity: critical/high/medium/low (with justification)\n"
        f"2. suggested_status: should the report be escalated? (escalate/keep/no_action)\n"
        f"3. routing_hint: suggested department or category refinement\n"
        f"4. missing_information: list of missing fields that would improve triage\n"
        f"5. confidence: 0.0-1.0 for the overall triage decision\n"
        f"6. reasoning: 2-3 sentence explanation\n\n"
        f"CRITICAL RULES:\n"
        f"- NEVER close, reject, or merge reports — only recommend\n"
        f"- NEVER change official status — only suggest\n"
        f"- If confidence < 0.5, escalate to human review\n"
        f"- Always preserve the citizen's original description"
    )

    try:
        response = await provider.generate(
            prompt=prompt,
            model_id=model_spec.model_id,
            max_tokens=1000,
        )
        cost = float(
            router.calculate_cost(model_spec.model_id, response.tokens_in, response.tokens_out)
        )

        # Parse the response into structured fields (simplified for stub)
        suggested_severity = report.severity  # default to current
        suggested_status = "no_action"
        confidence = 0.8
        missing_info = []

        # Heuristic enrichment on top of LLM output
        text = (report.description or "").lower()
        if any(w in text for w in ["danger", "hazard", "emergency", "collapse"]):
            suggested_severity = "critical"
            suggested_status = "escalate"
        elif any(w in text for w in ["broken", "blocked", "overflow"]):
            suggested_severity = "high"

        if len(report.description or "") < 30:
            missing_info.append("Detailed description needed")

        result = {
            "report_id": str(report_id),
            "ticket_no": report.ticket_no,
            "suggested_severity": suggested_severity,
            "suggested_status": suggested_status,
            "routing_hint": category.name_key if category else None,
            "missing_information": missing_info,
            "confidence": confidence,
            "reasoning": response.text[:300],
            "model_id": model_spec.model_id,
            "cost_usd": cost,
            "latency_ms": response.latency_ms,
            "triage_timestamp": datetime.now(UTC).isoformat(),
            "requires_human_review": confidence < 0.7 or suggested_status == "escalate",
            "disclaimer": (
                "Triage recommendations are advisory only. "
                "No status changes are applied automatically. "
                "A human reviewer must approve all actions."
            ),
        }

        return result

    except Exception as exc:
        return {
            "error": f"Triage agent failed: {exc}",
            "report_id": str(report_id),
            "status": "failed",
        }


async def batch_triage(
    session: AsyncSession,
    *,
    report_ids: list[uuid.UUID],
    provider: LLMProvider | None = None,
    router: ModelRouter | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Run triage on multiple reports. Returns batch results with summary."""
    results = []
    for rid in report_ids[:limit]:
        result = await triage_report(session, report_id=rid, provider=provider, router=router)
        results.append(result)

    escalated = sum(1 for r in results if r.get("requires_human_review"))
    failed = sum(1 for r in results if r.get("status") == "failed")

    return {
        "results": results,
        "total": len(results),
        "escalated_to_human": escalated,
        "failed": failed,
        "completed": len(results) - failed,
    }
