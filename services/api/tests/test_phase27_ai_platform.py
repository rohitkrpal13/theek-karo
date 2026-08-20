"""Phase 27 — AI Platform tests.

Tests for: Gateway, Agents, Skills, Workflows, Evaluation, Observability.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.ai_platform.agents import (
    SafetyAgent,
    build_default_agents,
)
from tk_api.ai_platform.evaluation import GOLDEN_DATASET, EvaluationFramework
from tk_api.ai_platform.gateway import (
    AICircuitBreaker,
    AIGatewayRequest,
    AIGatewayResponse,
)
from tk_api.ai_platform.skills import (
    WORKFLOW_DEFINITIONS,
    MultiAgentOrchestrator,
    SkillRegistry,
)
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _role_headers(client: TestClient, phone: str, role: str) -> dict[str, str]:
    tokens = _register_and_verify(client, client._recording_sender, phone)
    _grant_role(client, tokens["user"]["id"], role)
    return _auth(tokens["access_token"])


def _grant_role(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            if role and user:
                existing = await session.scalar(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == role.id,
                    )
                )
                if not existing:
                    session.add(UserRole(user_id=user.id, role_id=role.id))
                    await session.commit()

    import asyncio

    asyncio.run(grant())


# ---------------------------------------------------------------------------
# Unit Tests: AI Gateway
# ---------------------------------------------------------------------------


class TestAIGateway:
    def test_circuit_breaker_basic(self):
        cb = AICircuitBreaker(failure_threshold=3, recovery_timeout_s=60)
        assert not cb.is_open("provider_a")
        cb.record_success("provider_a")
        assert not cb.is_open("provider_a")

    def test_circuit_breaker_opens(self):
        cb = AICircuitBreaker(failure_threshold=2, recovery_timeout_s=60)
        cb.record_failure("provider_a")
        assert not cb.is_open("provider_a")
        cb.record_failure("provider_a")
        assert cb.is_open("provider_a")

    def test_circuit_breaker_recovery(self):
        cb = AICircuitBreaker(failure_threshold=2, recovery_timeout_s=60)
        cb.record_failure("provider_a")
        cb.record_failure("provider_a")
        assert cb.is_open("provider_a")
        cb.record_success("provider_a")
        assert not cb.is_open("provider_a")

    def test_circuit_breaker_get_status(self):
        cb = AICircuitBreaker(failure_threshold=5, recovery_timeout_s=60)
        status = cb.get_status()
        assert "failure_counts" in status
        assert "open_until" in status

    def test_gateway_request_defaults(self):
        req = AIGatewayRequest()
        assert req.task == "chat"
        assert req.risk_level == "low"
        assert req.max_tokens == 4000
        assert req.temperature == 0.2

    def test_gateway_response_defaults(self):
        resp = AIGatewayResponse(request_id=uuid.uuid4(), status="success")
        assert resp.status == "success"
        assert resp.tokens_in == 0
        assert resp.cost_usd == 0.0


# ---------------------------------------------------------------------------
# Unit Tests: Agent Router
# ---------------------------------------------------------------------------


class TestAgentRouter:
    def test_build_default_agents(self):
        router = build_default_agents()
        assert len(router._agents) >= 10

    def test_agent_codes(self):
        router = build_default_agents()
        codes = set(router._agents.keys())
        assert "civic_assistant" in codes
        assert "case_analysis" in codes
        assert "routing" in codes
        assert "translation" in codes
        assert "analytics" in codes
        assert "evidence" in codes
        assert "data_quality" in codes
        assert "geospatial" in codes
        assert "policy_research" in codes
        assert "safety" in codes

    def test_intent_routing(self):
        router = build_default_agents()
        agent = router.route("CASE_QUERY")
        assert agent is not None
        assert agent.code == "case_analysis"

    def test_keyword_routing_case(self):
        router = build_default_agents()
        agent = router.route_by_keywords("Why is this case unresolved?")
        assert agent.code == "case_analysis"

    def test_keyword_routing_department(self):
        router = build_default_agents()
        agent = router.route_by_keywords("Which department handles water supply?")
        assert agent.code == "routing"

    def test_keyword_routing_translation(self):
        router = build_default_agents()
        agent = router.route_by_keywords("Translate this to Hindi")
        assert agent.code == "translation"

    def test_keyword_routing_analytics(self):
        router = build_default_agents()
        agent = router.route_by_keywords("Show me trends in Patna")
        assert agent.code == "analytics"

    def test_keyword_routing_geospatial(self):
        router = build_default_agents()
        agent = router.route_by_keywords("Map of nearby issues")
        assert agent.code == "geospatial"

    def test_keyword_routing_policy(self):
        router = build_default_agents()
        agent = router.route_by_keywords("What is the government scheme?")
        assert agent.code == "policy_research"

    def test_keyword_routing_default(self):
        router = build_default_agents()
        agent = router.route_by_keywords("Hello world")
        assert agent.code == "civic_assistant"

    def test_list_agents(self):
        router = build_default_agents()
        agents = router.list_agents()
        assert len(agents) >= 10
        assert all("code" in a for a in agents)
        assert all("name" in a for a in agents)
        assert all("risk_level" in a for a in agents)

    def test_intent_categories_defined(self):
        from tk_api.ai_platform.agents import INTENT_CATEGORIES

        assert len(INTENT_CATEGORIES) >= 12
        assert "CASE_QUERY" in INTENT_CATEGORIES
        assert "TRANSLATION" in INTENT_CATEGORIES


# ---------------------------------------------------------------------------
# Unit Tests: Skills
# ---------------------------------------------------------------------------


class TestSkills:
    def test_skill_registry(self):
        registry = SkillRegistry()
        skills = registry.list_skills()
        assert len(skills) >= 10

    def test_skill_get(self):
        registry = SkillRegistry()
        skill = registry.get("case_summary")
        assert skill is not None
        assert skill.code == "case_summary"

    def test_skill_get_nonexistent(self):
        registry = SkillRegistry()
        skill = registry.get("nonexistent")
        assert skill is None

    def test_skill_compose(self):
        registry = SkillRegistry()
        result = registry.compose(["case_summary", "evidence_analysis"])
        assert "case_summary" in result["skills"]
        assert "evidence_analysis" in result["skills"]
        assert result["risk_level"] == "medium"

    def test_skill_compose_empty(self):
        registry = SkillRegistry()
        result = registry.compose([])
        assert result["skills"] == []
        assert result["risk_level"] == "low"

    def test_workflow_definitions(self):
        assert len(WORKFLOW_DEFINITIONS) >= 3
        codes = [wf.code for wf in WORKFLOW_DEFINITIONS]
        assert "case_deep_analysis" in codes
        assert "district_overview" in codes
        assert "resolution_assessment" in codes


# ---------------------------------------------------------------------------
# Unit Tests: Safety Agent (deterministic, no LLM needed)
# ---------------------------------------------------------------------------


class TestSafetyAgent:
    def test_detects_prohibited(self):
        agent = SafetyAgent()
        mock_session = AsyncMock()
        result = asyncio.run(
            agent.execute(
                mock_session,
                input_data={"output": "Case closed and permission granted", "agent_code": "test"},
            )
        )
        assert result.status == "completed"
        assert result.output["passed"] is False
        assert len(result.output["issues"]) > 0

    def test_passes_clean(self):
        agent = SafetyAgent()
        mock_session = AsyncMock()
        result = asyncio.run(
            agent.execute(
                mock_session,
                input_data={
                    "output": "Analysis of school infrastructure in district",
                    "agent_code": "test",
                },
            )
        )
        assert result.status == "completed"
        assert result.output["passed"] is True

    def test_detects_sensitive(self):
        agent = SafetyAgent()
        mock_session = AsyncMock()
        result = asyncio.run(
            agent.execute(
                mock_session,
                input_data={
                    "output": "Based on political affiliation, we rank citizens",
                    "agent_code": "test",
                },
            )
        )
        assert result.status == "completed"
        assert result.output["passed"] is False

    def test_no_false_positive_on_normal_text(self):
        agent = SafetyAgent()
        mock_session = AsyncMock()
        result = asyncio.run(
            agent.execute(
                mock_session,
                input_data={
                    "output": "The school needs repair. Government department of "
                    "education should review.",
                    "agent_code": "test",
                },
            )
        )
        assert result.status == "completed"
        assert result.output["passed"] is True

    def test_detects_bypass(self):
        agent = SafetyAgent()
        mock_session = AsyncMock()
        result = asyncio.run(
            agent.execute(
                mock_session,
                input_data={"output": "User bypassed security", "agent_code": "test"},
            )
        )
        assert result.output["passed"] is False


# ---------------------------------------------------------------------------
# Unit Tests: Evaluation Framework
# ---------------------------------------------------------------------------


class TestEvaluation:
    def test_golden_dataset(self):
        assert len(GOLDEN_DATASET) >= 13

    def test_framework_list(self):
        fw = EvaluationFramework()
        cases = fw.list_test_cases()
        assert len(cases) >= 13

    def test_framework_filter_by_type(self):
        fw = EvaluationFramework()
        safety_cases = fw.list_test_cases(eval_type="safety")
        assert len(safety_cases) >= 3
        assert all(c.eval_type == "safety" for c in safety_cases)

    def test_framework_filter_by_tag(self):
        fw = EvaluationFramework()
        red_team_cases = fw.list_test_cases(tags=["red_team"])
        assert len(red_team_cases) >= 3

    def test_framework_filter_by_agent(self):
        fw = EvaluationFramework()
        cases = fw.list_test_cases(target_code="safety")
        assert len(cases) >= 3
        assert all(c.target_code == "safety" for c in cases)

    def test_framework_filter_combined(self):
        fw = EvaluationFramework()
        cases = fw.list_test_cases(eval_type="agent", tags=["routing"])
        assert len(cases) >= 3
        assert all(c.eval_type == "agent" for c in cases)

    def test_framework_multilingual_cases(self):
        fw = EvaluationFramework()
        cases = fw.list_test_cases(tags=["multilingual"])
        assert len(cases) >= 1


# ---------------------------------------------------------------------------
# Unit Tests: Multi-Agent Orchestration
# ---------------------------------------------------------------------------


class TestMultiAgentOrchestration:
    def test_workflow_list(self):
        router = build_default_agents()
        orchestrator = MultiAgentOrchestrator(router)
        wfs = orchestrator.list_workflows()
        assert len(wfs) >= 3
        codes = [wf["code"] for wf in wfs]
        assert "case_deep_analysis" in codes
        assert "resolution_assessment" in codes

    def test_workflow_steps(self):
        router = build_default_agents()
        orchestrator = MultiAgentOrchestrator(router)
        wf = orchestrator.get_workflow("case_deep_analysis")
        assert wf is not None
        assert len(wf.steps) >= 3

    def test_workflow_not_found(self):
        router = build_default_agents()
        orchestrator = MultiAgentOrchestrator(router)
        wf = orchestrator.get_workflow("nonexistent")
        assert wf is None

    def test_workflow_risk_levels(self):
        router = build_default_agents()
        orchestrator = MultiAgentOrchestrator(router)
        wfs = orchestrator.list_workflows()
        for wf in wfs:
            assert "risk_level" in wf
            assert wf["risk_level"] in ("low", "medium", "high", "critical")


# ---------------------------------------------------------------------------
# API Tests: AI Platform Endpoints
# ---------------------------------------------------------------------------


class TestAIPlatformAPI:
    def test_gateway_chat(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000001", "admin")
        resp = client.post(
            "/api/v1/ai-platform/gateway/chat",
            json={"query": "What issues are near me?"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "success"
        assert "answer" in data

    def test_gateway_health(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000002", "admin")
        resp = client.get(
            "/api/v1/ai-platform/gateway/health",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "healthy"

    def test_list_agents(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000003", "admin")
        resp = client.get(
            "/api/v1/ai-platform/agents",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 10

    def test_execute_agent(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000004", "admin")
        resp = client.post(
            "/api/v1/ai-platform/agents/execute",
            json={
                "agent_code": "civic_assistant",
                "input_data": {"query": "What is Theek Karo?"},
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"

    def test_execute_nonexistent_agent(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000005", "admin")
        resp = client.post(
            "/api/v1/ai-platform/agents/execute",
            json={"agent_code": "nonexistent_agent", "input_data": {}},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_get_agent_detail(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000006", "admin")
        resp = client.get(
            "/api/v1/ai-platform/agents/civic_assistant",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["code"] == "civic_assistant"
        assert "name" in data
        assert "risk_level" in data

    def test_get_nonexistent_agent(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000007", "admin")
        resp = client.get(
            "/api/v1/ai-platform/agents/nonexistent",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_list_skills(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000008", "admin")
        resp = client.get(
            "/api/v1/ai-platform/skills",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 10

    def test_compose_skills(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000009", "admin")
        resp = client.post(
            "/api/v1/ai-platform/skills/compose",
            json={"skill_codes": ["case_summary", "translation"]},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "case_summary" in data["skills"]

    def test_list_workflows(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000010", "admin")
        resp = client.get(
            "/api/v1/ai-platform/workflows",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 3

    def test_execute_workflow(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000011", "admin")
        resp = client.post(
            "/api/v1/ai-platform/workflows/execute",
            json={
                "workflow_code": "case_deep_analysis",
                "input_data": {"case_data": {"id": "test"}, "query": "Analyze"},
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"

    def test_execute_nonexistent_workflow(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000012", "admin")
        resp = client.post(
            "/api/v1/ai-platform/workflows/execute",
            json={"workflow_code": "nonexistent", "input_data": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_workflow_missing_code(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000013", "admin")
        resp = client.post(
            "/api/v1/ai-platform/workflows/execute",
            json={"input_data": {}},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_ai_health(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000014", "admin")
        resp = client.get(
            "/api/v1/ai-platform/health",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "status" in data
        assert "recent_runs_1h" in data

    def test_cost_summary(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000015", "admin")
        resp = client.get(
            "/api/v1/ai-platform/costs?days=7",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "totals" in data

    def test_list_agent_runs(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000016", "admin")
        resp = client.get(
            "/api/v1/ai-platform/runs",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "items" in data
        assert "count" in data

    def test_unauthorized_access(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai-platform/agents")
        assert resp.status_code in (401, 403)

    def test_evaluate_run(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000017", "admin")
        resp = client.post(
            "/api/v1/ai-platform/evaluations/run",
            json={"eval_type": "safety"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total" in data
        assert "passed" in data
        assert data["total"] >= 3

    def test_list_evaluations(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000018", "admin")
        resp = client.get(
            "/api/v1/ai-platform/evaluations",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    def test_list_test_cases(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000019", "admin")
        resp = client.get(
            "/api/v1/ai-platform/evaluations/test-cases",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 13

    def test_evaluation_summary(self, client: TestClient) -> None:
        headers = _role_headers(client, "9700000020", "admin")
        resp = client.get(
            "/api/v1/ai-platform/evaluations/summary?days=30",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
