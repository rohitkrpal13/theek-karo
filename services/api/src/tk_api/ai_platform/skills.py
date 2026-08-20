"""AI Skills and Multi-Agent Orchestration (Phase 27).

Skills: Reusable AI capabilities composed of tools + prompts + models.
Multi-agent orchestration: Workflow graphs with sequential, parallel,
conditional, and human-approval steps.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai_platform.agents import AgentResult, AgentRouter

# ---------------------------------------------------------------------------
# Skill Definitions
# ---------------------------------------------------------------------------


class SkillStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


@dataclass
class SkillDefinition:
    """Defines a reusable AI skill."""

    code: str
    name: str
    description: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)
    risk_level: str = "low"
    model_requirements: dict[str, Any] = field(default_factory=dict)
    prompt_code: str | None = None
    status: SkillStatus = SkillStatus.ACTIVE


# Built-in skill definitions
SKILL_DEFINITIONS: list[SkillDefinition] = [
    SkillDefinition(
        code="case_summary",
        name="Case Summary Skill",
        description="Summarize a civic case with key facts, evidence, and status",
        tools=["get_department_cases", "get_verification_history"],
        risk_level="low",
    ),
    SkillDefinition(
        code="department_routing",
        name="Department Routing Skill",
        description="Recommend which department should handle a case",
        tools=["get_department_cases", "search_institutions"],
        risk_level="medium",
    ),
    SkillDefinition(
        code="evidence_analysis",
        name="Evidence Analysis Skill",
        description="Analyze evidence for relevance, completeness, contradictions",
        tools=["get_evidence_record", "get_verification_history"],
        risk_level="medium",
    ),
    SkillDefinition(
        code="data_quality_check",
        name="Data Quality Check Skill",
        description="Check data quality across sources and datasets",
        tools=["get_source_health", "get_data_conflicts_for_entity"],
        risk_level="low",
    ),
    SkillDefinition(
        code="translation",
        name="Translation Skill",
        description="Translate civic content across Indian languages",
        tools=[],
        risk_level="low",
    ),
    SkillDefinition(
        code="map_analysis",
        name="Map Analysis Skill",
        description="Analyze geographic patterns in civic data",
        tools=["get_geographic_summary"],
        risk_level="low",
    ),
    SkillDefinition(
        code="policy_research",
        name="Policy Research Skill",
        description="Research government policies and compare with reported conditions",
        tools=["get_official_data", "get_source_metadata"],
        risk_level="medium",
    ),
    SkillDefinition(
        code="impact_analysis",
        name="Impact Analysis Skill",
        description="Analyze impact of civic actions and resolutions",
        tools=["get_civic_metrics", "get_department_cases"],
        risk_level="low",
    ),
    SkillDefinition(
        code="report_drafting",
        name="Report Drafting Skill",
        description="Draft civic reports with AI assistance",
        tools=["search_institutions", "search_reports"],
        risk_level="medium",
    ),
    SkillDefinition(
        code="communication_draft",
        name="Communication Draft Skill",
        description="Draft civic communications and announcements",
        tools=[],
        risk_level="medium",
    ),
]


class SkillRegistry:
    """Registry of available AI skills."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        for skill in SKILL_DEFINITIONS:
            self._skills[skill.code] = skill

    def get(self, code: str) -> SkillDefinition | None:
        return self._skills.get(code)

    def list_skills(self, status: SkillStatus | None = None) -> list[SkillDefinition]:
        if status:
            return [s for s in self._skills.values() if s.status == status]
        return list(self._skills.values())

    def compose(self, skill_codes: list[str]) -> dict[str, Any]:
        """Compose multiple skills into a combined capability."""
        combined_tools: list[str] = []
        combined_permissions: list[str] = []
        max_risk = "low"
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}

        for code in skill_codes:
            skill = self._skills.get(code)
            if skill:
                combined_tools.extend(skill.tools)
                combined_permissions.extend(skill.required_permissions)
                if risk_order.get(skill.risk_level, 0) > risk_order.get(max_risk, 0):
                    max_risk = skill.risk_level

        return {
            "skills": skill_codes,
            "tools": list(set(combined_tools)),
            "permissions": list(set(combined_permissions)),
            "risk_level": max_risk,
        }


# ---------------------------------------------------------------------------
# Multi-Agent Orchestration
# ---------------------------------------------------------------------------


class WorkflowStepType(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    HUMAN_APPROVAL = "human_approval"
    RETRY = "retry"
    FALLBACK = "fallback"
    TERMINATION = "termination"


@dataclass
class WorkflowStep:
    """A single step in a multi-agent workflow."""

    step_id: str
    step_type: WorkflowStepType
    agent_code: str | None = None
    skill_code: str | None = None
    input_mapping: dict[str, str] = field(default_factory=dict)
    condition: str | None = None  # for conditional steps
    approval_required: bool = False
    max_retries: int = 0
    timeout_s: int = 30
    fallback_step_id: str | None = None


@dataclass
class WorkflowDefinition:
    """Defines a multi-agent workflow graph."""

    code: str
    name: str
    description: str
    steps: list[WorkflowStep]
    risk_level: str = "low"
    max_execution_time_s: int = 120


@dataclass
class WorkflowState:
    """Runtime state of a workflow execution."""

    workflow_code: str
    trace_id: uuid.UUID
    current_step_index: int = 0
    step_results: dict[str, AgentResult] = field(default_factory=dict)
    status: str = "created"  # created|running|waiting_approval|completed|failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


# Pre-defined workflows
WORKFLOW_DEFINITIONS: list[WorkflowDefinition] = [
    WorkflowDefinition(
        code="case_deep_analysis",
        name="Deep Case Analysis",
        description="Multi-agent case analysis: research → data → evidence → synthesis",
        steps=[
            WorkflowStep(
                step_id="research",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="case_analysis",
                input_mapping={"case_data": "case_data", "query": "query"},
            ),
            WorkflowStep(
                step_id="evidence_check",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="evidence",
                input_mapping={"evidence_data": "case_data"},
            ),
            WorkflowStep(
                step_id="data_quality",
                step_type=WorkflowStepType.PARALLEL,
                agent_code="data_quality",
                input_mapping={"data_summary": "case_data"},
            ),
            WorkflowStep(
                step_id="synthesis",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="civic_assistant",
                input_mapping={"query": "synthesis_query"},
            ),
        ],
        risk_level="low",
    ),
    WorkflowDefinition(
        code="district_overview",
        name="District Overview Analysis",
        description="Comprehensive district analysis with multiple agents",
        steps=[
            WorkflowStep(
                step_id="analytics",
                step_type=WorkflowStepType.PARALLEL,
                agent_code="analytics",
                input_mapping={"query": "query", "data": "analytics_data"},
            ),
            WorkflowStep(
                step_id="geospatial",
                step_type=WorkflowStepType.PARALLEL,
                agent_code="geospatial",
                input_mapping={"query": "query", "geographic_data": "geo_data"},
            ),
            WorkflowStep(
                step_id="data_quality",
                step_type=WorkflowStepType.PARALLEL,
                agent_code="data_quality",
                input_mapping={"data_summary": "data_summary"},
            ),
            WorkflowStep(
                step_id="synthesis",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="civic_assistant",
                input_mapping={"query": "synthesis_query"},
            ),
        ],
        risk_level="low",
    ),
    WorkflowDefinition(
        code="resolution_assessment",
        name="Resolution Assessment",
        description="Assess case resolution with evidence and policy comparison",
        steps=[
            WorkflowStep(
                step_id="case_analysis",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="case_analysis",
                input_mapping={"case_data": "case_data"},
            ),
            WorkflowStep(
                step_id="evidence_analysis",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="evidence",
                input_mapping={"evidence_data": "resolution_evidence"},
            ),
            WorkflowStep(
                step_id="policy_check",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="policy_research",
                input_mapping={"query": "policy_query"},
            ),
            WorkflowStep(
                step_id="safety_validation",
                step_type=WorkflowStepType.SEQUENTIAL,
                agent_code="safety",
                input_mapping={"output": "draft_output", "agent_code": "resolution_assessment"},
                approval_required=True,
            ),
        ],
        risk_level="high",
    ),
]


class MultiAgentOrchestrator:
    """Orchestrates multi-agent workflows with state management."""

    def __init__(self, agent_router: AgentRouter):
        self.agent_router = agent_router
        self._workflows: dict[str, WorkflowDefinition] = {}
        for wf in WORKFLOW_DEFINITIONS:
            self._workflows[wf.code] = wf

    def get_workflow(self, code: str) -> WorkflowDefinition | None:
        return self._workflows.get(code)

    def list_workflows(self) -> list[dict[str, Any]]:
        return [
            {
                "code": wf.code,
                "name": wf.name,
                "description": wf.description,
                "steps": len(wf.steps),
                "risk_level": wf.risk_level,
            }
            for wf in self._workflows.values()
        ]

    async def execute_workflow(
        self,
        session: AsyncSession,
        workflow_code: str,
        input_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Execute a multi-agent workflow."""
        workflow = self._workflows.get(workflow_code)
        if not workflow:
            return {"status": "error", "error": f"Workflow '{workflow_code}' not found"}

        trace_id = uuid.uuid4()
        state = WorkflowState(
            workflow_code=workflow_code,
            trace_id=trace_id,
            status="running",
            started_at=datetime.now(UTC),
        )

        context: dict[str, Any] = dict(input_data)

        for step in workflow.steps:
            if not step.agent_code:
                continue
            agent = self.agent_router._agents.get(step.agent_code)
            if not agent:
                state.step_results[step.step_id] = AgentResult(
                    status="failed", error=f"Agent '{step.agent_code}' not found"
                )
                continue

            # Map input from context
            step_input = {}
            for param_name, context_key in step.input_mapping.items():
                step_input[param_name] = context.get(context_key, context.get(param_name))

            # Check approval requirement
            if step.approval_required:
                state.status = "waiting_approval"
                return {
                    "status": "waiting_approval",
                    "trace_id": str(trace_id),
                    "workflow": workflow_code,
                    "pending_step": step.step_id,
                    "agent": step.agent_code,
                    "intermediate_results": {k: v.output for k, v in state.step_results.items()},
                }

            # Execute agent
            try:
                result = await agent.execute(
                    session,
                    step_input,
                    user_id=user_id,
                )
                state.step_results[step.step_id] = result

                # Update context with results
                if result.output:
                    context[f"{step.step_id}_result"] = result.output
                    context["synthesis_query"] = (
                        f"Based on the following analysis results, provide a comprehensive "
                        f"synthesis:\n{str(result.output)[:1000]}"
                    )
            except Exception as exc:
                state.step_results[step.step_id] = AgentResult(status="failed", error=str(exc))

        state.status = "completed"
        state.completed_at = datetime.now(UTC)

        # Aggregate results
        total_cost = sum(r.cost_usd for r in state.step_results.values())
        total_tokens_in = sum(r.tokens_in for r in state.step_results.values())
        total_tokens_out = sum(r.tokens_out for r in state.step_results.values())

        return {
            "status": "completed",
            "trace_id": str(trace_id),
            "workflow": workflow_code,
            "results": {
                k: {"status": v.status, "output": v.output, "error": v.error}
                for k, v in state.step_results.items()
            },
            "total_cost_usd": total_cost,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
        }
