"""AI Agent architecture (Phase 27).

Base agent, agent router, and specialized agents for civic intelligence.
Every agent has: name, purpose, allowed_tools, risk_level, model_policy, timeout, budget.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai.providers import LLMProvider, StubLlmProvider
from tk_api.ai.registry import ModelRouter, ModelSpec

# ---------------------------------------------------------------------------
# Agent States
# ---------------------------------------------------------------------------
AGENT_CREATED = "created"
AGENT_RUNNING = "running"
AGENT_WAITING_TOOL = "waiting_for_tool"
AGENT_WAITING_APPROVAL = "waiting_for_approval"
AGENT_COMPLETED = "completed"
AGENT_FAILED = "failed"
AGENT_CANCELLED = "cancelled"


@dataclass
class AgentResult:
    """Standardized agent output."""

    status: str
    output: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    model_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None
    requires_approval: bool = False
    risk_level: str = "low"


class BaseAgent(ABC):
    """Base class for all AI agents."""

    code: str = "base"
    name: str = "Base Agent"
    description: str = ""
    risk_level: str = "low"
    allowed_tools: ClassVar[list[str]] = []
    allowed_data: list[str] = field(default_factory=list)
    max_execution_time_s: int = 30
    max_tool_calls: int = 10
    max_tokens: int = 4000
    cost_budget_usd: float = 1.0

    def __init__(
        self,
        provider: LLMProvider | None = None,
        router: ModelRouter | None = None,
    ):
        self.provider = provider or StubLlmProvider()
        self.router = router or ModelRouter()

    @abstractmethod
    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """Execute the agent with given input and context."""

    def _select_model(self, task: str, language: str = "en") -> ModelSpec:
        return self.router.select_model(task, language=language)


# ---------------------------------------------------------------------------
# Agent Router
# ---------------------------------------------------------------------------


class AgentRouter:
    """Routes user requests to the best agent based on intent classification."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._intent_map: dict[str, str] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.code] = agent

    def register_intent(self, intent: str, agent_code: str) -> None:
        self._intent_map[intent] = agent_code

    def route(self, intent: str) -> BaseAgent | None:
        agent_code = self._intent_map.get(intent)
        if agent_code:
            return self._agents.get(agent_code)
        return None

    def route_by_keywords(self, query: str) -> BaseAgent:
        """Simple keyword-based routing as fallback."""
        q = query.lower()
        if any(w in q for w in ("case", "report", "ticket", "complaint")):
            return self._agents.get("case_analysis", self._get_default())
        if any(w in q for w in ("department", "route", "assign", "which department")):
            return self._agents.get("routing", self._get_default())
        if any(w in q for w in ("evidence", "photo", "image", "document")):
            return self._agents.get("evidence", self._get_default())
        if any(w in q for w in ("translate", "hindi", "language")):
            return self._agents.get("translation", self._get_default())
        if any(w in q for w in ("analytics", "trend", "statistics", "data")):
            return self._agents.get("analytics", self._get_default())
        if any(w in q for w in ("map", "location", "geographic", "nearby")):
            return self._agents.get("geospatial", self._get_default())
        if any(w in q for w in ("policy", "scheme", "government", "regulation")):
            return self._agents.get("policy_research", self._get_default())
        return self._get_default()

    def _get_default(self) -> BaseAgent:
        found = self._agents.get("civic_assistant")
        if found is None:
            found = next(iter(self._agents.values()), None)
        if found is None:
            raise ValueError("No agents registered")
        return found

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "code": a.code,
                "name": a.name,
                "description": a.description,
                "risk_level": a.risk_level,
                "allowed_tools": a.allowed_tools,
            }
            for a in self._agents.values()
        ]


# ---------------------------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------------------------

INTENT_CATEGORIES = [
    "CASE_QUERY",
    "CASE_ANALYSIS",
    "DEPARTMENT_QUERY",
    "INSTITUTION_QUERY",
    "MAP_QUERY",
    "DATA_QUERY",
    "REPORT_ASSISTANCE",
    "DOCUMENT_ANALYSIS",
    "TRANSLATION",
    "COMMUNICATION",
    "ANALYTICS",
    "VERIFICATION_HELP",
    "GENERAL_CIVIC_ASSISTANCE",
]


# ---------------------------------------------------------------------------
# Specialized Agents
# ---------------------------------------------------------------------------


class CivicAssistantAgent(BaseAgent):
    """General-purpose civic assistant for user queries."""

    code = "civic_assistant"
    name = "Civic Assistant"
    description = "Answers general civic questions, helps users navigate the platform"
    risk_level = "low"
    allowed_tools: ClassVar[list[str]] = [
        "search_institutions",
        "search_reports",
        "get_institution_details",
        "get_civic_metrics",
        "get_geographic_summary",
    ]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        query = input_data.get("query", "")
        model_spec = self._select_model("chat_assistant", input_data.get("language", "en"))

        context_str = "\n".join(context[:5]) if context else "No additional context."
        prompt = (
            f"You are a helpful civic assistant for the Theek Karo platform.\n"
            f"Context:\n{context_str}\n\n"
            f"User query: {query}\n\n"
            f"Provide a helpful, factual response. Cite sources where available."
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=self.max_tokens,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={"answer": response.text, "sources": []},
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class CaseAnalysisAgent(BaseAgent):
    """Analyzes civic cases: timeline, evidence, status, recommendations."""

    code = "case_analysis"
    name = "Case Analysis Agent"
    description = "Analyzes case details, evidence, timeline, and provides assessment"
    risk_level = "medium"
    allowed_tools: ClassVar[list[str]] = [
        "get_department_cases",
        "search_reports",
        "get_source_metadata",
        "get_data_conflicts_for_entity",
        "get_verification_history",
    ]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        case_data = input_data.get("case_data", {})
        query = input_data.get("query", "Analyze this case")
        model_spec = self._select_model("summarization")

        prompt = (
            f"Analyze the following civic case and provide:\n"
            f"1. Summary\n2. Key Facts\n3. Evidence Assessment\n"
            f"4. Missing Information\n5. Status Assessment\n6. Recommended Next Step\n\n"
            f"Case Data:\n{str(case_data)[:2000]}\n\n"
            f"Query: {query}"
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=self.max_tokens,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={
                    "analysis": response.text,
                    "case_id": case_data.get("id"),
                    "case_no": case_data.get("case_no"),
                },
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class RoutingAgent(BaseAgent):
    """Recommends department routing for cases."""

    code = "routing"
    name = "Routing Agent"
    description = "Recommends which department should handle a case"
    risk_level = "medium"
    allowed_tools: ClassVar[list[str]] = ["get_department_cases", "search_institutions"]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        case_info = input_data.get("case_data", {})
        model_spec = self._select_model("classification")

        prompt = (
            f"Based on the following case information, recommend the most appropriate "
            f"department. Provide: department name, service type, jurisdiction, reason, "
            f"and confidence level (high/medium/low).\n\n"
            f"Case: {str(case_info)[:1500]}"
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=1000,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={"routing_recommendation": response.text},
                requires_approval=True,
                risk_level="medium",
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class TranslationAgent(BaseAgent):
    """Translates content preserving proper nouns, case numbers, official terms."""

    code = "translation"
    name = "Translation Agent"
    description = "Translates civic content across Indian languages"
    risk_level = "low"
    allowed_tools: ClassVar[list[str]] = []

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        text = input_data.get("text", "")
        target = input_data.get("target_language", "en")
        source = input_data.get("source_language", "auto")
        model_spec = self._select_model("translation", target)

        prompt = (
            f"Translate the following text from {source} to {target}.\n"
            f"Preserve: case numbers (TK-...), institution names, department names, "
            f"proper nouns, and official terminology.\n\n"
            f"Text: {text}"
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=2000,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={
                    "translated_text": response.text,
                    "source_language": source,
                    "target_language": target,
                },
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class AnalyticsAgent(BaseAgent):
    """Performs analytics: trends, comparisons, aggregations."""

    code = "analytics"
    name = "Analytics Agent"
    description = "Analyzes civic data for trends, comparisons, and insights"
    risk_level = "low"
    allowed_tools: ClassVar[list[str]] = [
        "get_civic_metrics",
        "get_report_trend",
        "get_category_breakdown",
        "get_geographic_summary",
    ]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        query = input_data.get("query", "Analyze civic data")
        data_context = input_data.get("data", {})
        model_spec = self._select_model("summarization")

        prompt = (
            f"Analyze the following civic data and provide insights:\n"
            f"Query: {query}\n"
            f"Data: {str(data_context)[:2000]}\n\n"
            f"Provide: trends, key findings, comparisons, and recommendations."
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=self.max_tokens,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={"analysis": response.text, "data_sources": list(data_context.keys())},
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class EvidenceAgent(BaseAgent):
    """Analyzes evidence: summary, classification, contradictions."""

    code = "evidence"
    name = "Evidence Agent"
    description = "Analyzes evidence items for relevance, completeness, and contradictions"
    risk_level = "medium"
    allowed_tools: ClassVar[list[str]] = ["get_evidence_record", "get_verification_history"]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        evidence_data = input_data.get("evidence_data", {})
        model_spec = self._select_model("summarization")

        prompt = (
            f"Analyze the following evidence and provide:\n"
            f"1. Summary\n2. Relevance assessment\n3. Completeness\n"
            f"4. Any contradictions or concerns\n5. Verification recommendations\n\n"
            f"Evidence: {str(evidence_data)[:2000]}"
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=self.max_tokens,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={"evidence_analysis": response.text},
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class DataQualityAgent(BaseAgent):
    """Detects data quality issues: missing values, duplicates, staleness."""

    code = "data_quality"
    name = "Data Quality Agent"
    description = "Monitors data quality across the platform"
    risk_level = "low"
    allowed_tools: ClassVar[list[str]] = [
        "get_source_health",
        "get_data_conflicts_for_entity",
        "get_disputes_for_entity",
    ]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        data_summary = input_data.get("data_summary", {})
        model_spec = self._select_model("classification")

        prompt = (
            f"Analyze the following data quality metrics and identify issues:\n"
            f"{str(data_summary)[:2000]}\n\n"
            f"Provide: quality assessment, issues found, severity, recommendations."
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=2000,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={"quality_assessment": response.text},
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class GeospatialAgent(BaseAgent):
    """Geospatial analysis: hotspots, clusters, patterns."""

    code = "geospatial"
    name = "Geospatial Intelligence Agent"
    description = "Analyzes geographic patterns in civic data"
    risk_level = "low"
    allowed_tools: ClassVar[list[str]] = ["get_geographic_summary"]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        geo_data = input_data.get("geographic_data", {})
        query = input_data.get("query", "Analyze geographic patterns")
        model_spec = self._select_model("summarization")

        prompt = (
            f"Analyze geographic patterns in civic data:\n"
            f"Query: {query}\n"
            f"Data: {str(geo_data)[:2000]}\n\n"
            f"Provide: hotspot analysis, clustering, patterns, recommendations."
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=self.max_tokens,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={"geospatial_analysis": response.text},
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class PolicyResearchAgent(BaseAgent):
    """Researches government policies and schemes using RAG."""

    code = "policy_research"
    name = "Policy Research Agent"
    description = "Researches government policies, schemes, and regulations"
    risk_level = "medium"
    allowed_tools: ClassVar[list[str]] = ["get_official_data", "get_source_metadata"]

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        query = input_data.get("query", "Research policy")
        rag_context = "\n".join(context[:5]) if context else "No retrieved documents."
        model_spec = self._select_model("chat_assistant")

        prompt = (
            f"Research the following policy question using the provided context:\n"
            f"Query: {query}\n"
            f"Sources:\n{rag_context}\n\n"
            f"Provide: relevant policy information, comparison with reported conditions, "
            f"gaps identified. Always cite sources. Do not provide legal advice."
        )

        try:
            response = await self.provider.generate(
                prompt=prompt,
                model_id=model_spec.model_id,
                max_tokens=self.max_tokens,
            )
            cost = float(
                self.router.calculate_cost(
                    model_spec.model_id, response.tokens_in, response.tokens_out
                )
            )
            return AgentResult(
                status=AGENT_COMPLETED,
                output={
                    "policy_analysis": response.text,
                    "disclaimer": "Information only, not legal advice.",
                },
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=cost,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            return AgentResult(status=AGENT_FAILED, error=str(exc))


class SafetyAgent(BaseAgent):
    """Validates AI outputs for safety, bias, and policy compliance."""

    code = "safety"
    name = "Safety Agent"
    description = "Validates AI outputs for safety, bias, and policy compliance"
    risk_level = "critical"
    allowed_tools: ClassVar[list[str]] = []

    async def execute(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        context: list[str] | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentResult:
        output_to_validate = input_data.get("output", "")
        agent_code = input_data.get("agent_code", "unknown")

        # Safety checks (deterministic + LLM)
        safety_issues = []

        # Check for prohibited content patterns
        prohibited = [
            "government lied",
            "official response published",
            "case closed",
            "permission granted",
            "bypass",
        ]
        output_lower = str(output_to_validate).lower()
        for pattern in prohibited:
            if pattern in output_lower:
                safety_issues.append(f"Prohibited pattern detected: '{pattern}'")

        # Check for sensitive attribute usage
        sensitive = ["religion", "caste", "political affiliation", "voting"]
        for attr in sensitive:
            if attr in output_lower:
                safety_issues.append(f"Sensitive attribute reference detected: '{attr}'")

        passed = len(safety_issues) == 0

        return AgentResult(
            status=AGENT_COMPLETED,
            output={
                "passed": passed,
                "issues": safety_issues,
                "agent_validated": agent_code,
                "validation_timestamp": datetime.now(UTC).isoformat(),
            },
            risk_level="critical",
        )


# ---------------------------------------------------------------------------
# Build default agent registry
# ---------------------------------------------------------------------------


def build_default_agents(
    provider: LLMProvider | None = None,
    router: ModelRouter | None = None,
) -> AgentRouter:
    """Build the default set of agents and route intents."""
    agent_router = AgentRouter()

    agents = [
        CivicAssistantAgent(provider, router),
        CaseAnalysisAgent(provider, router),
        RoutingAgent(provider, router),
        TranslationAgent(provider, router),
        AnalyticsAgent(provider, router),
        EvidenceAgent(provider, router),
        DataQualityAgent(provider, router),
        GeospatialAgent(provider, router),
        PolicyResearchAgent(provider, router),
        SafetyAgent(provider, router),
    ]

    for agent in agents:
        agent_router.register(agent)

    # Intent mappings
    agent_router.register_intent("CASE_QUERY", "case_analysis")
    agent_router.register_intent("CASE_ANALYSIS", "case_analysis")
    agent_router.register_intent("DEPARTMENT_QUERY", "routing")
    agent_router.register_intent("TRANSLATION", "translation")
    agent_router.register_intent("ANALYTICS", "analytics")
    agent_router.register_intent("MAP_QUERY", "geospatial")
    agent_router.register_intent("DATA_QUERY", "analytics")
    agent_router.register_intent("GENERAL_CIVIC_ASSISTANCE", "civic_assistant")

    return agent_router
