"""Phase 21 AI-assisted planning and volunteer matching (MCP tools + drafts).

Safety rules (docs/AI-SAFETY.md §Phase 21):

* Every tool is READ_ONLY and returns public-safe data only. Volunteer
  matches expose profile preferences (skills/languages/areas) — never phone,
  email, address, or exact location.
* AI planning output is always labeled AI GENERATED, stored as a suggestion,
  and only materializes after a human approval gate.
* No political targeting, no harassment tooling, no fake-signature/impact
  generation. Progress numbers always come from stored state.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic_action.models import (
    ActionEvidence,
    ActionMilestone,
    ActionPlan,
    ActionTask,
)
from tk_api.community.models import CivicInitiative, VolunteerProfile


def _coerce_uuid(value: Any, field: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# MCP tool handlers (registered in ai/tools.py)
# ---------------------------------------------------------------------------


async def tool_get_action_plan(
    session: AsyncSession,
    initiative_id: str | None = None,
    plan_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Public summary of an action plan: objective, status, progress, and
    open tasks. Read-only; returns public-safe data only."""
    plan = None
    if plan_id and _coerce_uuid(plan_id, "plan_id"):
        plan = await session.get(ActionPlan, _coerce_uuid(plan_id, "plan_id"))
    if plan is None and initiative_id and _coerce_uuid(initiative_id, "initiative_id"):
        plan = await session.scalar(
            select(ActionPlan).where(
                ActionPlan.initiative_id == _coerce_uuid(initiative_id, "initiative_id")
            )
        )
    if plan is None:
        return {"plan": None}
    tasks = (
        (await session.execute(select(ActionTask).where(ActionTask.plan_id == plan.id)))
        .scalars()
        .all()
    )
    milestones = (
        (await session.execute(select(ActionMilestone).where(ActionMilestone.plan_id == plan.id)))
        .scalars()
        .all()
    )
    return {
        "plan": {
            "id": str(plan.id),
            "initiative_id": str(plan.initiative_id),
            "objective": plan.objective,
            "status": plan.status,
            "ai_generated": plan.ai_generated,
            "open_tasks": [
                {"id": str(t.id), "title": t.title, "status": t.status, "priority": t.priority}
                for t in tasks
                if t.status in ("TODO", "ASSIGNED", "IN_PROGRESS", "BLOCKED")
            ],
            "progress": {
                "tasks_total": len(tasks),
                "tasks_done": sum(1 for t in tasks if t.status == "COMPLETED"),
                "milestones_total": len(milestones),
                "milestones_done": sum(1 for m in milestones if m.status == "completed"),
            },
        }
    }


async def tool_get_volunteer_matches(
    session: AsyncSession,
    initiative_id: str | None = None,
    plan_id: str | None = None,
    limit: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Suggested volunteer profiles for an initiative/plan. Returns only
    public preferences (skills, languages, areas, availability). Never
    contact details or exact locations."""
    initiative_id_uuid = _coerce_uuid(initiative_id, "initiative_id")
    plan = None
    if plan_id and _coerce_uuid(plan_id, "plan_id"):
        plan = await session.get(ActionPlan, _coerce_uuid(plan_id, "plan_id"))
    if plan is not None:
        initiative_id_uuid = plan.initiative_id
    initiative = None
    if initiative_id_uuid:
        initiative = await session.get(CivicInitiative, initiative_id_uuid)
    profiles = (
        (await session.execute(select(VolunteerProfile).limit(min(limit, 50)))).scalars().all()
    )
    # Deterministic heuristic: prefer profiles sharing initiative categories.
    target_categories = (
        {str(initiative.category_id)} if initiative and initiative.category_id else set()
    )
    matches: list[dict[str, Any]] = []
    for profile in profiles:
        score = 0
        if target_categories and profile.categories:
            score = len(set(profile.categories) & target_categories)
        if initiative and initiative.geography_id and profile.areas:
            score += 2
        matches.append(
            {
                "user_id": str(profile.user_id),
                "languages": profile.languages,
                "interests": profile.interests,
                "skills": profile.skills,
                "areas": profile.areas,
                "availability": bool(profile.availability),
                "match_score": score,
            }
        )
    matches.sort(key=lambda m: m["match_score"], reverse=True)
    return {"matches": matches[: min(limit, 50)]}


async def tool_get_campaign_progress(
    session: AsyncSession, campaign_id: str | None = None, **kwargs: Any
) -> dict[str, Any]:
    """Aggregate progress of initiatives linked to a campaign. Read-only.
    Progress is derived from task/milestone state, never entered manually."""
    from tk_api.civic_action.models import CampaignInitiativeLink

    campaign_uuid = _coerce_uuid(campaign_id, "campaign_id")
    if campaign_uuid is None:
        return {"campaign": None}
    links = (
        (
            await session.execute(
                select(CampaignInitiativeLink).where(
                    CampaignInitiativeLink.campaign_id == campaign_uuid
                )
            )
        )
        .scalars()
        .all()
    )
    initiatives = []
    for link in links:
        initiative = await session.get(CivicInitiative, link.initiative_id)
        if initiative is None:
            continue
        plan = await session.scalar(
            select(ActionPlan).where(ActionPlan.initiative_id == link.initiative_id)
        )
        plan_status = plan.status if plan else None
        tasks = (
            (await session.execute(select(ActionTask).where(ActionTask.plan_id == plan.id)))
            .scalars()
            .all()
            if plan
            else []
        )
        initiatives.append(
            {
                "initiative_id": str(link.initiative_id),
                "title": initiative.title,
                "status": initiative.status,
                "action_plan_status": plan_status,
                "tasks_total": len(tasks),
                "tasks_done": sum(1 for t in tasks if t.status == "COMPLETED"),
            }
        )
    return {"campaign_id": str(campaign_uuid), "initiatives": initiatives}


async def tool_get_impact_metrics(
    session: AsyncSession,
    initiative_id: str | None = None,
    plan_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Verified impact metrics for an initiative/plan. Only approved
    measurements are reported as impact; pending ones are labeled pending."""
    from tk_api.civic_action.models import ImpactMeasurement, ImpactMetric

    plan_uuid = _coerce_uuid(plan_id, "plan_id")
    if plan_uuid is None and initiative_id and _coerce_uuid(initiative_id, "initiative_id"):
        plan = await session.scalar(
            select(ActionPlan).where(
                ActionPlan.initiative_id == _coerce_uuid(initiative_id, "initiative_id")
            )
        )
        plan_uuid = plan.id if plan else None
    if plan_uuid is None:
        return {"metrics": []}
    metrics = (
        (await session.execute(select(ImpactMetric).where(ImpactMetric.plan_id == plan_uuid)))
        .scalars()
        .all()
    )
    result = []
    for metric in metrics:
        measurements = (
            (
                await session.execute(
                    select(ImpactMeasurement).where(ImpactMeasurement.metric_id == metric.id)
                )
            )
            .scalars()
            .all()
        )
        approved = [m for m in measurements if m.status == "approved"]
        result.append(
            {
                "metric_id": str(metric.id),
                "name": metric.name,
                "unit": metric.unit,
                "baseline": metric.baseline,
                "target": metric.target,
                "latest_verified_value": approved[-1].value if approved else None,
                "status": "verified" if approved else "pending",
            }
        )
    return {"metrics": result}


async def tool_get_action_evidence(
    session: AsyncSession,
    initiative_id: str | None = None,
    task_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Verification status of attached evidence for an initiative/task.
    Returns metadata only (kind, status, sha256 of uploaded media)."""
    stmt = select(ActionEvidence)
    if task_id and _coerce_uuid(task_id, "task_id"):
        stmt = stmt.where(ActionEvidence.task_id == _coerce_uuid(task_id, "task_id"))
    elif initiative_id and _coerce_uuid(initiative_id, "initiative_id"):
        stmt = stmt.where(
            ActionEvidence.initiative_id == _coerce_uuid(initiative_id, "initiative_id")
        )
    rows = (await session.execute(stmt.limit(50))).scalars().all()
    return {
        "evidence": [
            {
                "id": str(e.id),
                "task_id": str(e.task_id) if e.task_id else None,
                "kind": e.kind,
                "verification_status": e.verification_status,
                "sha256": e.sha256,
                "mime_type": e.mime_type,
                "size_bytes": e.size_bytes,
            }
            for e in rows
        ]
    }


async def tool_get_verification_status(
    session: AsyncSession, initiative_id: str | None = None, **kwargs: Any
) -> dict[str, Any]:
    """Current verification state of an initiative's action plan."""
    initiative_uuid = _coerce_uuid(initiative_id, "initiative_id")
    if initiative_uuid is None:
        return {"plan": None}
    plan = await session.scalar(
        select(ActionPlan).where(ActionPlan.initiative_id == initiative_uuid)
    )
    if plan is None:
        return {"plan": None}
    return {
        "plan": {
            "id": str(plan.id),
            "initiative_id": str(plan.initiative_id),
            "status": plan.status,
            "ai_generated": plan.ai_generated,
            "ai_approved": plan.ai_approved_by is not None,
            "requires_human_review": plan.status in ("VERIFICATION_PENDING", "PROPOSED", "BLOCKED"),
        }
    }


# ---------------------------------------------------------------------------
# AI plan drafting (suggestion + approval gate)
# ---------------------------------------------------------------------------


async def generate_ai_plan_draft(session: AsyncSession, initiative_id: uuid.UUID) -> dict[str, Any]:
    """Rule-based AI GENERATED draft suggestion for an initiative: breaks the
    stated goal into proposed tasks/milestones with estimates. The output is
    stored separately and only applied after explicit human approval."""
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ValueError("initiative not found")
    goal = initiative.goal or initiative.description or ""
    title = initiative.title or "initiative"
    task_proposals: list[dict[str, Any]] = []
    # Deterministic decomposition of the goal text into suggested steps.
    keywords = ["survey", "surveying", "assessment", "assess", "inspect", "inspection", "audit"]
    for i, keyword in enumerate(
        [
            "survey the current state",
            "identify stakeholders",
            "plan the intervention",
            "execute the intervention",
            "document evidence",
            "report outcomes",
        ]
    ):
        task_proposals.append(
            {
                "title": keyword,
                "description": (
                    f"AI-suggested step for {title}: {keyword}. Review and edit before approval."
                ),
                "priority": "MEDIUM" if i not in (0, 2) else "HIGH",
                "order": i,
            }
        )
    checklist_draft = []
    for kw in keywords:
        if kw in goal.lower():
            checklist_draft.append(
                {"item": f"verify {kw} results are uploaded as evidence", "done": False}
            )
    return {
        "ai_generated": True,
        "disclaimer": (
            "AI GENERATED draft — for review only. Requires human approval "
            "before any task is created."
        ),
        "initiative_id": str(initiative_id),
        "objective_draft": (
            f"Coordinate {title} from assessment to verified outcome with evidence at every stage."
        ),
        "milestones_draft": [
            {"title": "Assessment", "description": "Baseline assessment and stakeholder mapping."},
            {"title": "Execution", "description": "Carry out the initiative's planned activities."},
            {
                "title": "Verification",
                "description": "Collect evidence, review outcomes, record impact.",
            },
        ],
        "tasks_draft": task_proposals,
        "checklist_draft": checklist_draft,
    }


async def plan_from_suggestion(
    session: AsyncSession, suggestion: dict[str, Any]
) -> list[dict[str, Any]]:
    """Materialize an APPROVED suggestion into task rows (called only after
    the human approval gate: ``decide_ai_plan_suggestion(decision="approve")``)."""
    tasks: list[dict[str, Any]] = []
    for i, item in enumerate(suggestion.get("tasks_draft") or []):
        tasks.append(
            {
                "title": str(item.get("title") or "task").strip(),
                "description": item.get("description"),
                "priority": item.get("priority") or "MEDIUM",
                "order": int(item.get("order") or i),
                "checklist": suggestion.get("checklist_draft") or [],
            }
        )
    return tasks
