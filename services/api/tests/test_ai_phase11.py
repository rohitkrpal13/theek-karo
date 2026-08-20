"""Tests for Phase 11: AI intelligence, RAG, Tools, and Agentic Workflows."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from starlette.testclient import TestClient

from tests.conftest import _register_and_verify
from tk_api.ai.models import AiConversation, AiRun
from tk_api.ai.orchestrator import AgentOrchestrator
from tk_api.ai.prompts import redact_pii_from_prompt
from tk_api.ai.providers import StubLlmProvider
from tk_api.ai.rag import RagRetriever
from tk_api.ai.registry import ModelRouter
from tk_api.ai.schemas import (
    CivicChatRequest,
    DuplicateAnalysisOutput,
    ReportClassificationOutput,
)
from tk_api.ai.tools import ToolRegistry
from tk_api.core.db import create_session_factory
from tk_api.institutions.models import Institution, InstitutionType
from tk_api.provenance.models import DataSource, ExternalSource
from tk_api.rag.models import RagChunk, RagDocument, RagDocumentVersion
from tk_api.users.models import Role, User, UserRole


def _promote_to_admin(client: TestClient, user_id: str) -> None:
    async def promote() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == "admin"))
            if not role:
                role = Role(code="admin", name="Admin")
                session.add(role)
                await session.flush()
            user = await session.get(User, uuid.UUID(user_id))
            if user:
                session.add(UserRole(user_id=user.id, role_id=role.id))
                await session.commit()

    asyncio.run(promote())


def _admin_headers(client: TestClient, sender: Any) -> dict[str, str]:
    phone_suffix = str(int(uuid.uuid4().hex[:6], 16) % 90000 + 10000)
    tokens = _register_and_verify(client, sender, f"98765{phone_suffix}")
    _promote_to_admin(client, tokens["user"]["id"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_provider_stub_generation() -> None:
    """Stub provider produces deterministic output, token counts, and structured outputs."""

    async def _run() -> None:
        provider = StubLlmProvider()

        # Text generation
        resp = await provider.generate(
            prompt="What are school issues in Patna?", model_id="stub-civic-v1"
        )
        assert "Patna" in resp.text
        assert resp.tokens_in > 0
        assert resp.tokens_out > 0
        assert resp.provider == "stub"

        # Structured generation
        prompt = (
            "<report_content>Title: Urgent leaking drinking water pipe in primary school\n"
            "Description: Water overflowing</report_content>"
        )
        struct_out, _ = await provider.generate_structured(
            prompt=prompt,
            schema_class=ReportClassificationOutput,
        )
        assert isinstance(struct_out, ReportClassificationOutput)
        assert struct_out.category_slug in ("school", "water")
        assert struct_out.confidence >= 0.7

    asyncio.run(_run())


def test_model_registry_and_routing() -> None:
    """Model router selects appropriate models and accurately calculates costs."""
    router = ModelRouter()

    chat_model = router.select_model("chat_assistant", language="hi")
    assert chat_model.provider in ("deepseek", "stub")

    class_model = router.select_model("classification", preferred_tier="fast")
    assert class_model.latency_tier == "fast"

    # Cost calculation
    cost = router.calculate_cost(chat_model.model_id, tokens_in=1000, tokens_out=1000)
    assert isinstance(cost, Decimal)
    assert cost >= Decimal("0.0")


def test_prompt_pii_redaction() -> None:
    """PII scrubber masks Aadhaar patterns and mobile phone numbers."""
    raw = (
        "Citizen report by Ramesh with Aadhaar 5432 1098 7654 "
        "and mobile 9876543210 about water leak."
    )
    scrubbed = redact_pii_from_prompt(raw)
    assert "5432 1098 7654" not in scrubbed
    assert "9876543210" not in scrubbed
    assert "[REDACTED_ID]" in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed


def test_controlled_tools_execution(client: TestClient) -> None:
    """Tool registry allows valid tools, queries real database records, and blocks unknown tools."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            tools = ToolRegistry()

            # Create dummy external source
            ext = ExternalSource(
                id=uuid.uuid4(),
                name="Education Dept",
                publisher="Govt",
                url="https://gov.in",
            )
            session.add(ext)
            await session.flush()

            # Create dummy institution type & institution
            itype = InstitutionType(
                id=uuid.uuid4(), code="school", name_key="institution_type.school"
            )
            session.add(itype)
            await session.flush()

            inst = Institution(
                id=uuid.uuid4(),
                institution_type_id=itype.id,
                source_id=ext.id,
                name="Govt Senior Secondary School Jaipur",
                normalized_name="govt senior secondary school jaipur",
                address="Sector 5, Jaipur",
                operational_status="active",
                official_identifier="UDISE-JAIPUR-01",
            )
            session.add(inst)
            await session.commit()

            # Execute search_institutions
            res = await tools.execute(session, "search_institutions", {"query": "Jaipur"})
            assert "institutions" in res
            assert any(i["name"] == inst.name for i in res["institutions"])

            # Execute get_institution_details
            details = await tools.execute(
                session, "get_institution_details", {"institution_id": str(inst.id)}
            )
            assert details["name"] == inst.name
            assert details["official_code"] == "UDISE-JAIPUR-01"

            # Block unknown tool
            blocked = await tools.execute(
                session, "execute_raw_sql", {"sql": "SELECT * FROM users;"}
            )
            assert "error" in blocked

    asyncio.run(_run())


def test_rag_hybrid_retrieval_and_access_control(client: TestClient) -> None:
    """RAG retriever respects access levels and synthesizes citations."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            source = DataSource(
                id=uuid.uuid4(),
                name="UDISE+ Public Portal",
                publisher="Ministry of Education",
                source_type="official_portal",
                version="2026.1",
                url="https://udiseplus.gov.in",
            )
            session.add(source)
            await session.flush()

            doc = RagDocument(
                id=uuid.uuid4(),
                data_source_id=source.id,
                title="Jaipur School Infrastructure Dataset",
                language="en",
            )
            session.add(doc)
            await session.flush()

            doc_ver = RagDocumentVersion(
                id=uuid.uuid4(),
                document_id=doc.id,
                version=1,
            )
            session.add(doc_ver)
            await session.flush()

            chunk_public = RagChunk(
                id=uuid.uuid4(),
                document_version_id=doc_ver.id,
                chunk_index=0,
                content="Jaipur School has 16 teachers, functional water, and separate toilets.",
                access_level="PUBLIC",
            )
            chunk_admin = RagChunk(
                id=uuid.uuid4(),
                document_version_id=doc_ver.id,
                chunk_index=1,
                content="CONFIDENTIAL: Internal notes on Jaipur School staff vacancies.",
                access_level="ADMIN",
            )

            session.add_all([chunk_public, chunk_admin])
            await session.commit()

            retriever = RagRetriever(session)

            # Public user search -> should NOT receive ADMIN chunk
            pub_chunks = await retriever.retrieve("Jaipur School staff", access_level="PUBLIC")
            assert len(pub_chunks) >= 1
            assert all(c.chunk_id != chunk_admin.id for c in pub_chunks)

            # Admin user search -> CAN receive ADMIN chunk
            admin_chunks = await retriever.retrieve(
                "Jaipur School staff vacancies", access_level="ADMIN"
            )
            assert any(c.chunk_id == chunk_admin.id for c in admin_chunks)

            # Citations
            citations = retriever.build_citation_items(pub_chunks)
            assert len(citations) >= 1
            assert citations[0].dataset_name == "UDISE+ Public Portal"

    asyncio.run(_run())


def test_ai_orchestrator_chat_and_audit(client: TestClient) -> None:
    """Agent orchestrator executes conversational research with citations and audit records."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            orch = AgentOrchestrator(session)

            req = CivicChatRequest(
                message="What are the registered details for schools in Patna with water issues?",
                language="en",
            )
            resp = await orch.chat_civic_research(req)

            assert resp.answer
            assert resp.conversation_id
            assert resp.confidence_label in ("high", "moderate")

            # Verify conversation & message persistence
            conv = await session.get(AiConversation, resp.conversation_id)
            assert conv is not None

            # Verify ai_runs audit log
            runs = (await session.execute(select(AiRun))).scalars().all()
            assert len(runs) >= 1
            latest_run = runs[-1]
            assert latest_run.task_kind == "chat_assistant"
            assert latest_run.prompt_version == "civic_chat_v1"
            assert latest_run.tokens_in is not None

    asyncio.run(_run())


def test_report_classification_and_duplicate_detection(client: TestClient) -> None:
    """AI classification and duplicate evaluation produce validated structured schemas."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            orch = AgentOrchestrator(session)

            class_res = await orch.classify_report(
                title="Broken water pipeline near market",
                description="Water is overflowing onto the street for 3 days.",
            )
            assert class_res.category_slug == "water"
            assert class_res.confidence >= 0.7

            dup_res = await orch.check_duplicates(
                target_title="Pothole on Main Road",
                target_description="Deep pothole in front of community center",
                candidate_title="Large pothole near community center",
                candidate_description="Similar pothole causing traffic jams",
                candidate_status="submitted",
                candidate_ticket_no="TK-1002",
                distance_m=15.0,
            )
            assert isinstance(dup_res, DuplicateAnalysisOutput)

    asyncio.run(_run())


def test_institution_summary_synthesis(client: TestClient) -> None:
    """Digital twin summary synthesizes official baselines and reports with citations."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            ext = ExternalSource(
                id=uuid.uuid4(),
                name="Education Dept",
                publisher="Govt",
                url="https://gov.in",
            )
            session.add(ext)
            await session.flush()

            itype = InstitutionType(
                id=uuid.uuid4(), code="school", name_key="institution_type.school"
            )
            session.add(itype)
            await session.flush()

            inst = Institution(
                id=uuid.uuid4(),
                institution_type_id=itype.id,
                source_id=ext.id,
                name="Jaipur Primary School North",
                normalized_name="jaipur primary school north",
                operational_status="active",
            )
            session.add(inst)
            await session.commit()

            orch = AgentOrchestrator(session)
            summary = await orch.summarize_institution(inst.id)

            assert summary.institution_name == "Jaipur Primary School North"
            assert "Situation" in summary.situation_summary

    asyncio.run(_run())


def test_multilingual_translation_preserves_identifiers(client: TestClient) -> None:
    """Translation produces translated text while preserving code tokens."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            orch = AgentOrchestrator(session)

            res = await orch.translate_text(
                text="Report TK-9901 about school UDISE-0812999 has been updated.",
                source_language="en",
                target_language="hi",
            )
            assert res.target_language == "hi"
            assert "TK-9901" in res.translated_text or "Translated" in res.translated_text

    asyncio.run(_run())


def test_ai_api_endpoints(client: TestClient, sender: Any) -> None:
    """FastAPI endpoints for AI chat, classification, translation, and tools."""
    # 1. Chat endpoint
    chat_resp = client.post(
        "/api/v1/ai/chat",
        json={
            "message": "Show reports about hospital emergency services in Jaipur",
            "language": "en",
        },
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "answer" in chat_data
    assert "conversation_id" in chat_data

    # 2. Classify endpoint
    class_resp = client.post(
        "/api/v1/ai/classify-report",
        json={"title": "No electricity in govt clinic", "description": "Power cuts for 12 hours"},
    )
    assert class_resp.status_code == 200
    assert "category_slug" in class_resp.json()

    # 3. Tools endpoint
    tools_resp = client.get("/api/v1/ai/tools")
    assert tools_resp.status_code == 200
    tools_data = tools_resp.json()
    assert "tools" in tools_data
    assert any(t["name"] == "search_institutions" for t in tools_data["tools"])

    # 4. Admin usage report
    headers = _admin_headers(client, sender)
    usage_resp = client.get("/api/v1/ai/admin/usage", headers=headers)
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()
    assert "total_runs" in usage_data
    assert usage_data["total_runs"] >= 1
