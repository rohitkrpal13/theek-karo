"""AI Orchestrator managing bounded agent workflows, RAG, tool routing, and audit logging."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai.models import AiConversation, AiMessage, AiRun
from tk_api.ai.prompts import (
    DEVELOPER_RULES,
    PROMPT_CIVIC_ASSISTANT_V1,
    PROMPT_DISCUSSION_SUMMARY_V1,
    PROMPT_DUPLICATE_DETECTION_V1,
    PROMPT_INSTITUTION_SUMMARY_V1,
    PROMPT_REPORT_CLASSIFIER_V1,
    PROMPT_TRANSLATION_V1,
    redact_pii_from_prompt,
)
from tk_api.ai.providers import LLMProvider, StubLlmProvider
from tk_api.ai.rag import RagRetriever
from tk_api.ai.registry import ModelRouter
from tk_api.ai.schemas import (
    AiUsageStatsRead,
    CitationItem,
    CivicChatRequest,
    CivicChatResponse,
    DuplicateAnalysisOutput,
    InstitutionSummaryOutput,
    RelatedEntityRef,
    ReportClassificationOutput,
    TranslationResponse,
)
from tk_api.ai.tools import ToolRegistry


class AgentOrchestrator:
    """Central orchestrator for evidence-grounded civic AI workflows."""

    def __init__(
        self,
        session: AsyncSession,
        provider: LLMProvider | None = None,
        router: ModelRouter | None = None,
        tools: ToolRegistry | None = None,
    ) -> None:
        self.session = session
        self.provider = provider or StubLlmProvider()
        self.router = router or ModelRouter()
        self.tools = tools or ToolRegistry()
        self.retriever = RagRetriever(session, self.provider)

    async def chat_civic_research(
        self,
        req: CivicChatRequest,
        user_id: uuid.UUID | None = None,
        access_level: str = "PUBLIC",
    ) -> CivicChatResponse:
        """Bounded conversational research assistant answering with RAG and tools."""
        # 1. Resolve or create conversation session
        now = datetime.now(UTC)
        conv_id = req.conversation_id or uuid.uuid4()
        conv = await self.session.get(AiConversation, conv_id)
        if not conv:
            conv = AiConversation(
                id=conv_id,
                user_id=user_id,
                session_id=req.session_id,
                title=req.message[:50],
                created_at=now,
                updated_at=now,
            )
            self.session.add(conv)

        # 2. Scrub PII from input
        clean_query = redact_pii_from_prompt(req.message)

        # 3. Retrieve relevant context via RAG
        retrieved_chunks = await self.retriever.retrieve(
            clean_query,
            access_level=access_level,
            language=req.language,
            institution_id=str(req.institution_id) if req.institution_id else None,
            top_k=3,
        )
        citations = self.retriever.build_citation_items(retrieved_chunks)

        # 4. Tool calls based on intent detection
        context_parts: list[str] = [c.snippet for c in citations]
        related_entities: list[RelatedEntityRef] = []

        query_lower = clean_query.lower()
        if req.institution_id or "school" in query_lower or "hospital" in query_lower:
            inst_results = await self.tools.execute(
                self.session,
                "search_institutions",
                {"query": "School" if "school" in query_lower else "Hospital", "limit": 3},
            )
            for inst in inst_results.get("institutions", []):
                related_entities.append(
                    RelatedEntityRef(
                        id=inst["id"],
                        kind="institution",
                        title=inst["name"],
                        subtitle=f"{inst.get('category')} · {inst.get('operational_status')}",
                    )
                )
                op_st = inst.get("operational_status")
                context_parts.append(f"Institution: {inst['name']} - Status: {op_st}")

        if "report" in query_lower or "issue" in query_lower:
            rep_results = await self.tools.execute(
                self.session,
                "search_reports",
                {"query": clean_query, "limit": 3},
            )
            for r in rep_results.get("reports", []):
                related_entities.append(
                    RelatedEntityRef(
                        id=r["id"],
                        kind="report",
                        title=r["title"],
                        subtitle=f"Ticket #{r.get('ticket_no')} · {r.get('status')}",
                    )
                )
                t_no = r.get("ticket_no")
                r_st = r.get("status")
                context_parts.append(f"Citizen Report #{t_no}: {r['title']} [Status: {r_st}]")

        context_str = (
            "\n---\n".join(context_parts)
            if context_parts
            else "No specific records matched in database."
        )

        # 5. Format prompt with injection-isolated tags
        # Build conversation history context
        conv_history_str = "No prior conversation."
        if req.conversation_id:
            try:
                hist_stmt = (
                    select(AiMessage)
                    .where(AiMessage.conversation_id == req.conversation_id)
                    .order_by(AiMessage.created_at.asc())
                    .limit(10)
                )
                hist_msgs = (await self.session.execute(hist_stmt)).scalars().all()
                if hist_msgs:
                    conv_history_str = "\n".join(
                        f"[{m.role}]: {m.content[:200]}" for m in hist_msgs
                    )
            except Exception:
                pass

        prompt = PROMPT_CIVIC_ASSISTANT_V1.format(
            developer_rules=DEVELOPER_RULES.strip(),
            current_timestamp=now.strftime("%Y-%m-%d %H:%M UTC"),
            language=req.language,
            context=context_str,
            conversation_history=conv_history_str,
            user_query=clean_query,
        )

        model_spec = self.router.select_model("chat_assistant", language=req.language)
        llm_resp = await self.provider.generate(
            prompt=prompt,
            model_id=model_spec.model_id,
            temperature=0.2,
        )

        cost_usd = self.router.calculate_cost(
            model_spec.model_id, llm_resp.tokens_in, llm_resp.tokens_out
        )

        # 6. Audit run
        run_record = AiRun(
            id=uuid.uuid4(),
            task_kind="chat_assistant",
            model_id=model_spec.model_id,
            provider=self.provider.provider_name,
            payload_in={"query": clean_query, "language": req.language},
            payload_out={"answer": llm_resp.text, "citations_count": len(citations)},
            confidence=Decimal("0.85"),
            latency_ms=llm_resp.latency_ms,
            tokens_in=llm_resp.tokens_in,
            tokens_out=llm_resp.tokens_out,
            cost_usd=cost_usd,
            prompt_version="civic_chat_v1",
            status="succeeded",
            created_at=now,
        )
        self.session.add(run_record)

        # 7. Persist messages in conversation history
        user_msg = AiMessage(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user",
            content=clean_query,
            created_at=now,
        )
        asst_msg = AiMessage(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="assistant",
            content=llm_resp.text,
            citations=[c.model_dump() for c in citations],
            tool_calls=[e.model_dump() for e in related_entities],
            created_at=now,
        )
        self.session.add_all([user_msg, asst_msg])
        await self.session.commit()

        return CivicChatResponse(
            conversation_id=conv_id,
            answer=llm_resp.text,
            evidence_points=[c.snippet for c in citations[:2]],
            citations=citations,
            data_freshness_note="Official benchmarks last retrieved in August 2026.",
            related_entities=related_entities,
            language=req.language,
            confidence_label="high" if citations else "moderate",
            model_info={"model": model_spec.model_id, "provider": self.provider.provider_name},
            created_at=now,
        )

    async def classify_report(
        self,
        title: str,
        description: str,
        fields: dict[str, Any] | None = None,
    ) -> ReportClassificationOutput:
        """Classify report intake data with suggest-only recommendations."""
        now = datetime.now(UTC)
        clean_title = redact_pii_from_prompt(title)
        clean_desc = redact_pii_from_prompt(description)

        prompt = PROMPT_REPORT_CLASSIFIER_V1.format(
            developer_rules=DEVELOPER_RULES.strip(),
            title=clean_title,
            description=clean_desc,
            fields_json=json.dumps(fields or {}),
        )

        model_spec = self.router.select_model("classification", preferred_tier="fast")
        output, llm_resp = await self.provider.generate_structured(
            prompt=prompt,
            schema_class=ReportClassificationOutput,
            model_id=model_spec.model_id,
        )

        cost_usd = self.router.calculate_cost(
            model_spec.model_id, llm_resp.tokens_in, llm_resp.tokens_out
        )

        run_record = AiRun(
            id=uuid.uuid4(),
            task_kind="report_classification",
            model_id=model_spec.model_id,
            provider=self.provider.provider_name,
            payload_in={"title": clean_title},
            payload_out=output.model_dump(),
            confidence=Decimal(str(round(output.confidence, 3))),
            latency_ms=llm_resp.latency_ms,
            tokens_in=llm_resp.tokens_in,
            tokens_out=llm_resp.tokens_out,
            cost_usd=cost_usd,
            prompt_version="report_classifier_v1",
            status="succeeded",
            created_at=now,
        )
        self.session.add(run_record)
        await self.session.commit()
        return output

    async def check_duplicates(
        self,
        target_title: str,
        target_description: str,
        candidate_title: str,
        candidate_description: str,
        candidate_status: str,
        candidate_ticket_no: str,
        distance_m: float = 0.0,
    ) -> DuplicateAnalysisOutput:
        """Analyze if two reports describe the same defect."""
        now = datetime.now(UTC)
        prompt = PROMPT_DUPLICATE_DETECTION_V1.format(
            developer_rules=DEVELOPER_RULES.strip(),
            target_title=redact_pii_from_prompt(target_title),
            target_description=redact_pii_from_prompt(target_description),
            candidate_title=redact_pii_from_prompt(candidate_title),
            candidate_description=redact_pii_from_prompt(candidate_description),
            candidate_status=candidate_status,
            candidate_ticket_no=candidate_ticket_no,
            distance_m=round(distance_m, 1),
        )

        model_spec = self.router.select_model("duplicate_detection", preferred_tier="fast")
        output, llm_resp = await self.provider.generate_structured(
            prompt=prompt,
            schema_class=DuplicateAnalysisOutput,
            model_id=model_spec.model_id,
        )

        cost_usd = self.router.calculate_cost(
            model_spec.model_id, llm_resp.tokens_in, llm_resp.tokens_out
        )

        run_record = AiRun(
            id=uuid.uuid4(),
            task_kind="duplicate_detection",
            model_id=model_spec.model_id,
            provider=self.provider.provider_name,
            payload_in={"target_title": target_title},
            payload_out=output.model_dump(),
            confidence=Decimal(str(round(output.similarity_score, 3))),
            latency_ms=llm_resp.latency_ms,
            tokens_in=llm_resp.tokens_in,
            tokens_out=llm_resp.tokens_out,
            cost_usd=cost_usd,
            prompt_version="duplicate_detection_v1",
            status="succeeded",
            created_at=now,
        )
        self.session.add(run_record)
        await self.session.commit()
        return output

    async def summarize_institution(
        self,
        institution_id: uuid.UUID,
    ) -> InstitutionSummaryOutput:
        """Synthesize digital twin situation summary using official data & reports."""
        now = datetime.now(UTC)
        inst_data = await self.tools.execute(
            self.session, "get_institution_details", {"institution_id": str(institution_id)}
        )
        rep_data = await self.tools.execute(
            self.session, "search_reports", {"institution_id": str(institution_id), "limit": 10}
        )
        disc_data = await self.tools.execute(
            self.session, "get_discrepancies", {"institution_id": str(institution_id)}
        )
        off_data = await self.tools.execute(
            self.session, "get_official_data", {"institution_id": str(institution_id)}
        )

        inst_name = inst_data.get("name", "Public Institution")
        reports = rep_data.get("reports", [])
        discrepancies = disc_data.get("discrepancies", [])

        # Format prompt
        prompt = PROMPT_INSTITUTION_SUMMARY_V1.format(
            developer_rules=DEVELOPER_RULES.strip(),
            institution_name=inst_name,
            institution_type=inst_data.get("category", "institution"),
            official_baseline_json=json.dumps(off_data.get("canonical_resources", {})),
            report_count=len(reports),
            reports_summary="\n".join(f"- {r['title']} ({r['status']})" for r in reports[:5])
            or "No reports.",
            discrepancies_json=json.dumps(discrepancies),
        )

        model_spec = self.router.select_model("summarization")
        llm_resp = await self.provider.generate(
            prompt=prompt,
            model_id=model_spec.model_id,
        )

        situation = (
            f"Current Situation for {inst_name}: {len(reports)} community reports filed. "
            f"Official data was registered with {len(discrepancies)} active discrepancy check(s)."
        )

        citations: list[CitationItem] = []
        if off_data.get("provenance"):
            p = off_data["provenance"]
            citations.append(
                CitationItem(
                    dataset_name=p.get("source_name", "Official Portal"),
                    dataset_version=p.get("dataset_version"),
                    publication_date=p.get("publication_date"),
                    url=p.get("source_url"),
                    snippet=f"Official baseline indicators for {inst_name}.",
                )
            )

        summary_output = InstitutionSummaryOutput(
            institution_id=str(institution_id),
            institution_name=inst_name,
            situation_summary=situation,
            total_reports_analyzed=len(reports),
            verified_reports_count=sum(1 for r in reports if r.get("status") == "verified"),
            dominant_categories=[inst_data.get("category", "general")],
            official_data_freshness="August 2026 Active Baseline",
            discrepancy_note=f"{len(discrepancies)} discrepancies flagged."
            if discrepancies
            else "No discrepancies detected.",
            citations=citations,
        )

        cost_usd = self.router.calculate_cost(
            model_spec.model_id, llm_resp.tokens_in, llm_resp.tokens_out
        )

        run_record = AiRun(
            id=uuid.uuid4(),
            task_kind="institution_summary",
            model_id=model_spec.model_id,
            provider=self.provider.provider_name,
            payload_in={"institution_id": str(institution_id)},
            payload_out=summary_output.model_dump(),
            confidence=Decimal("0.90"),
            latency_ms=llm_resp.latency_ms,
            tokens_in=llm_resp.tokens_in,
            tokens_out=llm_resp.tokens_out,
            cost_usd=cost_usd,
            prompt_version="institution_summary_v1",
            status="succeeded",
            created_at=now,
        )
        self.session.add(run_record)
        await self.session.commit()
        return summary_output

    async def translate_text(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "en",
    ) -> TranslationResponse:
        """Translate text preserving code identifiers and ticket numbers."""
        now = datetime.now(UTC)
        prompt = PROMPT_TRANSLATION_V1.format(
            source_language=source_language,
            target_language=target_language,
            text=text,
        )

        model_spec = self.router.select_model(
            "translation", language=target_language, preferred_tier="fast"
        )
        llm_resp = await self.provider.generate(
            prompt=prompt,
            model_id=model_spec.model_id,
        )

        cost_usd = self.router.calculate_cost(
            model_spec.model_id, llm_resp.tokens_in, llm_resp.tokens_out
        )

        run_record = AiRun(
            id=uuid.uuid4(),
            task_kind="translation",
            model_id=model_spec.model_id,
            provider=self.provider.provider_name,
            payload_in={"source_language": source_language, "target_language": target_language},
            payload_out={"translated_text": llm_resp.text},
            confidence=Decimal("0.95"),
            latency_ms=llm_resp.latency_ms,
            tokens_in=llm_resp.tokens_in,
            tokens_out=llm_resp.tokens_out,
            cost_usd=cost_usd,
            prompt_version="translation_v1",
            status="succeeded",
            created_at=now,
        )
        self.session.add(run_record)
        await self.session.commit()

        return TranslationResponse(
            translated_text=llm_resp.text,
            source_language=source_language,
            target_language=target_language,
            model_id=model_spec.model_id,
            confidence=0.95,
        )

    async def summarize_discussion(
        self,
        ticket_no: str,
        status: str,
        title: str,
        comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Neutral, advisory community-thread summary (Phase 13). Never orders
        bans — moderation stays human; the summary only flags for review."""
        now = datetime.now(UTC)
        redacted_comments = [redact_pii_from_prompt(str(c)) for c in comments]
        prompt = PROMPT_DISCUSSION_SUMMARY_V1.format(
            developer_rules=DEVELOPER_RULES,
            ticket_no=ticket_no,
            status=status,
            title=title,
            comments=json.dumps(redacted_comments, ensure_ascii=False)[:4000],
        )

        model_spec = self.router.select_model("translation", language="en", preferred_tier="fast")
        llm_resp = await self.provider.generate(
            prompt=prompt,
            model_id=model_spec.model_id,
        )

        cost_usd = self.router.calculate_cost(
            model_spec.model_id, llm_resp.tokens_in, llm_resp.tokens_out
        )
        try:
            output: dict[str, Any] = json.loads(llm_resp.text)
        except (json.JSONDecodeError, TypeError):
            output = {"summary": llm_resp.text[:500], "key_concerns": [], "consensus": None}

        run_record = AiRun(
            id=uuid.uuid4(),
            task_kind="discussion_summary",
            model_id=model_spec.model_id,
            provider=self.provider.provider_name,
            payload_in={"ticket_no": ticket_no},
            payload_out=output,
            confidence=Decimal("0.90"),
            latency_ms=llm_resp.latency_ms,
            tokens_in=llm_resp.tokens_in,
            tokens_out=llm_resp.tokens_out,
            cost_usd=cost_usd,
            prompt_version="discussion_summary_v1",
            status="succeeded",
            created_at=now,
        )
        self.session.add(run_record)
        await self.session.commit()
        return output

    async def get_usage_statistics(self) -> AiUsageStatsRead:
        """Aggregate token consumption, latency, and costs for platform monitoring."""
        stmt = select(
            func.count(AiRun.id).label("total_runs"),
            func.coalesce(func.sum(AiRun.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(AiRun.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.sum(AiRun.cost_usd), Decimal("0.0")).label("total_cost"),
            func.coalesce(func.avg(AiRun.latency_ms), 0.0).label("avg_latency"),
        )
        res = await self.session.execute(stmt)
        row = res.one()

        # Breakdown by model
        m_stmt = select(AiRun.model_id, func.count(AiRun.id)).group_by(AiRun.model_id)
        m_res = await self.session.execute(m_stmt)
        model_breakdown = {str(k): int(v) for k, v in m_res.all()}

        # Breakdown by provider
        p_stmt = select(AiRun.provider, func.count(AiRun.id)).group_by(AiRun.provider)
        p_res = await self.session.execute(p_stmt)
        provider_breakdown = {str(k): int(v) for k, v in p_res.all()}

        return AiUsageStatsRead(
            total_runs=int(row.total_runs),
            total_tokens_in=int(row.tokens_in),
            total_tokens_out=int(row.tokens_out),
            total_cost_usd=float(row.total_cost),
            model_breakdown=model_breakdown,
            provider_breakdown=provider_breakdown,
            average_latency_ms=float(row.avg_latency),
        )
