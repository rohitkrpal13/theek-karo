"""AI orchestration: analysis, duplicate suggestion, and intake assistance (PRD §14)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.ai import duplicates
from tk_api.ai import gateway as gateway_mod
from tk_api.ai.analysis import analyze_report
from tk_api.civic.models import Category, IssueType
from tk_api.reports.models import Report


async def process_report(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    gateway: gateway_mod.AiGateway,
    threshold: float,
    min_report_age_days: int,
    request: Request | None = None,
    actor_id: uuid.UUID | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    result = await analyze_report(
        session,
        report_id=report_id,
        gateway=gateway,
        request=request,
        actor_id=actor_id,
        refresh=refresh,
    )
    report = await session.get(Report, report_id)
    if report is None:
        return result
    annotation_id = uuid.UUID(result["annotation_id"])
    matches = await duplicates.find_duplicates(
        session,
        report,
        threshold=threshold,
        min_report_age_days=min_report_age_days,
    )
    queued = await duplicates.queue_for_review(
        session, report=report, annotation_id=annotation_id, matches=matches
    )
    if queued:
        await session.commit()
    return result


async def suggest_intake(
    session: AsyncSession,
    *,
    description: str,
    title: str | None = None,
    category_slug: str | None = None,
    location: dict[str, Any] | None = None,
    gateway: gateway_mod.AiGateway | None = None,
) -> dict[str, Any]:
    """Provide real-time AI suggestions for report title, category, issue type, and severity.

    Never mutates submissions or displays subjective accusations (PRD §14, §62, §63).
    """
    text = f"{title or ''} {description}".lower()

    # Heuristic & keyword classification
    cat_slug = category_slug
    if not cat_slug:
        if any(w in text for w in ["pothole", "road", "street", "traffic", "footpath"]):
            cat_slug = "roads"
        elif any(w in text for w in ["water", "pipe", "leak", "tap", "drinking", "drainage"]):
            cat_slug = "water"
        elif any(w in text for w in ["garbage", "trash", "waste", "clean", "sewage", "dump"]):
            cat_slug = "sanitation"
        elif any(w in text for w in ["school", "teacher", "classroom", "student", "college"]):
            cat_slug = "education"
        elif any(w in text for w in ["hospital", "doctor", "clinic", "medicine", "nurse"]):
            cat_slug = "healthcare"
        elif any(w in text for w in ["light", "electricity", "wire", "pole", "power"]):
            cat_slug = "electricity"

    # Category entity lookup
    matched_cat = None
    if cat_slug:
        matched_cat = await session.scalar(select(Category).where(Category.slug == cat_slug))

    # Issue type suggestion
    issue_type_code = None
    if matched_cat:
        issue_types = list(
            (
                await session.execute(
                    select(IssueType)
                    .where(IssueType.category_id == matched_cat.id, IssueType.is_active.is_(True))
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        for it in issue_types:
            if it.slug.lower() in text or it.name.lower() in text:
                issue_type_code = it.slug
                break
        if not issue_type_code and issue_types:
            issue_type_code = issue_types[0].slug

    # Severity suggestion
    severity = "medium"
    critical_words = ["danger", "hazard", "accident", "emergency", "fire", "shock", "collapse"]
    if any(w in text for w in critical_words):
        severity = "critical"
    elif any(w in text for w in ["broken", "overflow", "blocked", "heavy", "urgent", "major"]):
        severity = "high"
    elif any(w in text for w in ["minor", "small", "cleaning", "maintenance"]):
        severity = "low"

    # Title suggestion
    clean_words = [w for w in re.split(r"\s+", description.strip()) if len(w) > 2]
    first_phrase = " ".join(clean_words[:6]).capitalize()
    suggested_title = title or (f"{first_phrase} issue" if first_phrase else "Civic issue report")

    # Missing information checklist
    missing_info = []
    if len(description.strip()) < 30:
        missing_info.append("Detailed description of observed issue")
    if not location or not location.get("coordinates"):
        missing_info.append("Specific geographic location or landmark")

    return {
        "category_suggestion": matched_cat.slug if matched_cat else cat_slug,
        "issue_type_suggestion": issue_type_code,
        "title_suggestion": suggested_title,
        "severity_suggestion": severity,
        "missing_information": missing_info,
        "confidence": 0.88 if matched_cat else 0.72,
        "model_id": "gemini-2.5-flash",
    }
