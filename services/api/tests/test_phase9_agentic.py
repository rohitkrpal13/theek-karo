"""Phase 9 — Agentic capabilities tests.

Tests: triage agent, recidivism detection, content moderation.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 1. Triage Agent
# ---------------------------------------------------------------------------


def test_triage_import():
    """Triage module imports cleanly."""
    from tk_api.ai.triage import triage_report, batch_triage, TRIAGE_SLA_SECONDS

    assert TRIAGE_SLA_SECONDS == 300


def test_triage_report_constants():
    """Triage constants are reasonable."""
    from tk_api.ai.triage import (
        TRIAGE_STATUS_PENDING,
        TRIAGE_STATUS_COMPLETED,
        TRIAGE_STATUS_ESCALATED,
        TRIAGE_SLA_SECONDS,
    )

    assert TRIAGE_STATUS_PENDING == "pending"
    assert TRIAGE_STATUS_COMPLETED == "completed"
    assert TRIAGE_STATUS_ESCALATED == "escalated"
    assert TRIAGE_SLA_SECONDS == 300


# ---------------------------------------------------------------------------
# 2. Recidivism Analytics
# ---------------------------------------------------------------------------


def test_recidivism_import():
    """Recidivism module imports cleanly."""
    from tk_api.ai.recidivism import (
        detect_recidivism,
        get_recidivism_summary,
        RECIDIVISM_WINDOW_DAYS,
        RECIDIVISM_MIN_REPEATS,
    )

    assert RECIDIVISM_WINDOW_DAYS == 180
    assert RECIDIVISM_MIN_REPEATS == 2


def test_recidivism_constants():
    """Recidivism detection parameters are reasonable."""
    from tk_api.ai.recidivism import RECIDIVISM_RADIUS_M

    assert RECIDIVISM_RADIUS_M == 200


# ---------------------------------------------------------------------------
# 3. Moderation Assist
# ---------------------------------------------------------------------------


def test_moderation_import():
    """Moderation module imports cleanly."""
    from tk_api.ai.moderation import (
        moderate_content,
        moderate_report_comments,
        MOD_CATEGORIES,
    )

    assert "spam" in MOD_CATEGORIES
    assert "harassment" in MOD_CATEGORIES
    assert "safe" in MOD_CATEGORIES
    assert len(MOD_CATEGORIES) >= 8


def test_moderation_categories_comprehensive():
    """All expected moderation categories exist."""
    from tk_api.ai.moderation import MOD_CATEGORIES

    expected = {"spam", "harassment", "misinformation", "hate_speech",
                "personal_info", "off_topic", "low_quality", "political", "safe", "duplicate"}
    assert expected == set(MOD_CATEGORIES.keys())


# ---------------------------------------------------------------------------
# 4. API Endpoint Registration
# ---------------------------------------------------------------------------


def test_ai_router_has_triage_endpoint():
    """The AI router includes the triage endpoint."""
    from tk_api.api.routers.ai import ai_router

    paths = {r.path for r in ai_router.routes}
    assert any("triage" in p for p in paths)


def test_ai_router_has_recidivism_endpoint():
    """The AI router includes the recidivism endpoint."""
    from tk_api.api.routers.ai import ai_router

    paths = {r.path for r in ai_router.routes}
    assert any("recidivism" in p for p in paths)


def test_ai_router_has_moderate_endpoint():
    """The AI router includes the moderation endpoint."""
    from tk_api.api.routers.ai import ai_router

    paths = {r.path for r in ai_router.routes}
    assert any("moderate" in p for p in paths)


# ---------------------------------------------------------------------------
# 5. Agent Platform Integration
# ---------------------------------------------------------------------------


def test_agent_registry_has_all_agents():
    """The default agent registry includes all expected agents."""
    from tk_api.ai_platform.agents import build_default_agents

    router = build_default_agents()
    agents = router.list_agents()
    codes = {a["code"] for a in agents}

    expected = {
        "civic_assistant", "case_analysis", "routing", "translation",
        "analytics", "evidence", "data_quality", "geospatial",
        "policy_research", "safety",
    }
    assert expected.issubset(codes)


def test_agent_safety_check():
    """Safety agent catches prohibited patterns."""
    from tk_api.ai_platform.agents import SafetyAgent
    import asyncio

    agent = SafetyAgent()

    async def run():
        result = await agent.execute(
            session=None,  # type: ignore
            input_data={
                "output": "The government lied about the case. Case closed.",
                "agent_code": "test",
            },
        )
        return result

    result = asyncio.run(run())
    assert result.output["passed"] is False
    assert len(result.output["issues"]) >= 2


def test_agent_safety_passes_clean_content():
    """Safety agent passes clean content."""
    from tk_api.ai_platform.agents import SafetyAgent
    import asyncio

    agent = SafetyAgent()

    async def run():
        result = await agent.execute(
            session=None,  # type: ignore
            input_data={
                "output": "Based on the analysis, 3 reports were filed about road conditions.",
                "agent_code": "analytics",
            },
        )
        return result

    result = asyncio.run(run())
    assert result.output["passed"] is True
    assert len(result.output["issues"]) == 0
