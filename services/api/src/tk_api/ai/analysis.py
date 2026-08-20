"""Report analysis pipeline (AI-ARCHITECTURE.md §4.1, API.md §6).

One submission → one ``ai_runs`` row (PII-insulated payload per ADR-019) → one
``ai_annotations`` row carrying the T4 envelope (content + confidence + model),
plus citations grounded in provenanced sources (ADR-006). Refreshes are
versioned: previous annotations are preserved and the latest is served.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.ai.gateway import AiGateway
from tk_api.ai.models import AiAnnotation, AiCitation, AiRun
from tk_api.ai.rag import citation_payload, retrieve
from tk_api.civic.models import Category
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.reports.models import Report


class AiError(ApiError):
    pass


def _prompt_for(report: Report, category: Category) -> str:
    # ADR-019: never send phone/email/address; the payload_* columns stay insulated.
    fields = report.fields or {}
    return (
        "REPORT\n"
        f"category: {category.slug}\n"
        f"title: {report.title}\n"
        f"description: {report.description}\n"
        f"fields: {fields}\n"
        "Suggest the most specific matching category from the platform list, "
        "summarise the issue, extract entities, and list cross-references."
    )


def _redact(text: str) -> str:
    import re

    return re.sub(r"[+\d][\d\s-]{9,}", "<REDACTED>", text)


async def _loading_required(session: AsyncSession, report: Report) -> Category:
    category = await session.get(Category, report.category_id)
    if category is None:
        raise AiError("category not found", 404, "category_not_found")
    return category


async def analyze_report(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    gateway: AiGateway,
    request: Request | None = None,
    actor_id: uuid.UUID | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise AiError("report not found", 404, "report_not_found")
    if not refresh and await session.scalar(
        select(AiAnnotation.id).where(AiAnnotation.report_id == report.id).limit(1)
    ):
        return await annotation_out(session, report.id)

    category = await _loading_required(session, report)
    prompt = _prompt_for(report, category)
    started = perf_counter()
    result = await gateway.analyze(prompt=prompt)
    latency = int((perf_counter() - started) * 1000)

    confidence = min(1.0, max(0.0, result.confidence))
    run = AiRun(
        task_kind="report_analysis",
        model_id=result.model_id,
        provider=result.provider,
        payload_in={
            "category": category.slug,
            "title": _redact(report.title),
            "description": _redact(report.description[:2000]),
        },
        payload_out=result.content,
        confidence=Decimal(str(round(confidence, 3))),
        latency_ms=latency,
        status="succeeded",
    )
    session.add(run)
    await session.flush()

    annotation = AiAnnotation(
        report_id=report.id,
        run_id=run.id,
        content=result.content,
        info_class="AI_ANALYSIS",
        confidence=Decimal(str(round(confidence, 3))),
        model_id=result.model_id,
    )
    session.add(annotation)
    await session.flush()

    sources = await retrieve(session, f"{report.title} {report.description}")
    for source in sources:
        payload = citation_payload(source)
        session.add(
            AiCitation(
                annotation_id=annotation.id,
                text=payload["text"],
                source_id=source.id,
                url=payload["url"],
                snippet=payload["snippet"],
            )
        )

    if refresh:
        await audit(
            session,
            action="ai.analysis_refresh",
            entity_type="ai_annotation",
            entity_id=annotation.id,
            actor_id=actor_id,
            after={
                "report_id": str(report.id),
                "run_id": str(run.id),
                "confidence": float(confidence),
                "provider": run.provider,
            },
            request=request,
        )
    await session.commit()
    return await annotation_out(session, report.id)


def _annotation_payload(
    annotation: AiAnnotation, run: AiRun, citations: list[AiCitation]
) -> dict[str, Any]:
    return {
        "annotation_id": str(annotation.id),
        "report_id": str(annotation.report_id),
        "info_class": annotation.info_class,
        "confidence": float(annotation.confidence),
        "model_id": annotation.model_id,
        "created_at": annotation.created_at,
        "content": annotation.content,
        "run": {
            "id": str(run.id),
            "task_kind": run.task_kind,
            "provider": run.provider,
            "status": run.status,
            "latency_ms": run.latency_ms,
        },
        "citations": [
            {
                "id": str(c.id),
                "text": c.text,
                "source_id": str(c.source_id),
                "url": c.url,
                "snippet": c.snippet,
            }
            for c in citations
        ],
    }


async def annotation_out(session: AsyncSession, report_id: uuid.UUID) -> dict[str, Any]:
    annotation = (
        await session.execute(
            select(AiAnnotation)
            .where(AiAnnotation.report_id == report_id)
            .order_by(AiAnnotation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if annotation is None:
        raise AiError("no analysis yet for this report", 404, "analysis_missing")
    run = await session.get(AiRun, annotation.run_id)
    if run is None:
        raise AiError("analysis run missing", 409, "run_missing")
    citations = list(
        (await session.execute(select(AiCitation).where(AiCitation.annotation_id == annotation.id)))
        .scalars()
        .all()
    )
    return _annotation_payload(annotation, run, citations)


async def citations_for_annotation(
    session: AsyncSession, annotation_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = (
        (await session.execute(select(AiCitation).where(AiCitation.annotation_id == annotation_id)))
        .scalars()
        .all()
    )
    if not rows:
        raise AiError("no citations for this annotation", 404, "citations_missing")
    return [
        {
            "id": str(c.id),
            "annotation_id": str(c.annotation_id) if c.annotation_id else None,
            "text": c.text,
            "source_id": str(c.source_id),
            "url": c.url,
            "snippet": c.snippet,
        }
        for c in rows
    ]
