"""Phase 9 — ML Moderation Assist.

AI-assisted content moderation for reports and community comments.
Provides moderation recommendations (flag, hide, escalate) with
confidence scores. All moderation actions require human approval.

Every moderation recommendation is auditable and appealable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai.providers import LLMProvider, StubLlmProvider
from tk_api.ai.registry import ModelRouter, ModelSpec
from tk_api.reports.models import Report, ReportComment


# ---------------------------------------------------------------------------
# Moderation Categories
# ---------------------------------------------------------------------------

MOD_CATEGORIES = {
    "spam": "Commercial or irrelevant content",
    "harassment": "Targeted attacks or bullying",
    "misinformation": "Factual inaccuracies or false claims",
    "hate_speech": "Discriminatory or hateful content",
    "personal_info": "Exposes personal information (doxxing)",
    "off_topic": "Not related to civic issues",
    "duplicate": "Duplicate of existing content",
    "low_quality": "Insufficient detail or unclear",
    "political": "Political campaigning or partisan content",
    "safe": "No moderation issues detected",
}


# ---------------------------------------------------------------------------
# Content Moderation
# ---------------------------------------------------------------------------

async def moderate_content(
    session: AsyncSession,
    *,
    content: str,
    content_type: str = "comment",  # comment | report
    content_id: uuid.UUID | None = None,
    provider: LLMProvider | None = None,
    router: ModelRouter | None = None,
) -> dict[str, Any]:
    """AI-assisted content moderation. Returns a recommendation with
    category, confidence, and suggested action.

    This is advisory only — no moderation action is taken automatically.
    """
    provider = provider or StubLlmProvider()
    router = router or ModelRouter()

    model_spec = router.select_model("classification")

    prompt = (
        f"You are a content moderation assistant for Theek Karo, "
        f"a civic issue reporting platform.\n\n"
        f"Analyze the following {content_type} content for moderation issues.\n"
        f"Content:\n\"\"\"\n{content[:1000]}\n\"\"\"\n\n"
        f"Check for these categories:\n"
        f"- spam: Commercial or irrelevant content\n"
        f"- harassment: Targeted attacks or bullying\n"
        f"- misinformation: Factual inaccuracies or false claims\n"
        f"- hate_speech: Discriminatory or hateful content\n"
        f"- personal_info: Exposes personal information (doxxing)\n"
        f"- off_topic: Not related to civic issues\n"
        f"- low_quality: Insufficient detail or unclear\n"
        f"- political: Political campaigning or partisan content\n"
        f"- safe: No issues detected\n\n"
        f"Provide:\n"
        f"1. category: the primary moderation category\n"
        f"2. confidence: 0.0-1.0\n"
        f"3. action: flag/hide/escalate/allow\n"
        f"4. reasoning: brief explanation\n\n"
        f"CRITICAL RULES:\n"
        f"- NEVER auto-remove content — only recommend\n"
        f"- Civic criticism of government services is NOT harassment\n"
        f"- Reporting about political figures on civic issues is NOT political campaigning\n"
        f"- When in doubt, allow (err on side of free expression)"
    )

    try:
        response = await provider.generate(
            prompt=prompt,
            model_id=model_spec.model_id,
            max_tokens=500,
        )

        # Parse response (simplified for stub)
        category = "safe"
        confidence = 0.9
        action = "allow"

        # Heuristic checks
        content_lower = content.lower()
        if any(w in content_lower for w in ["buy now", "click here", "free money", "lottery"]):
            category = "spam"
            confidence = 0.85
            action = "flag"
        elif any(w in content_lower for w in ["idiot", "stupid", "shut up"]):
            category = "harassment"
            confidence = 0.7
            action = "flag"
        elif any(w in content_lower for w in ["phone:", "address:", "aadhaar"]):
            category = "personal_info"
            confidence = 0.8
            action = "flag"

        return {
            "content_type": content_type,
            "content_id": str(content_id) if content_id else None,
            "category": category,
            "category_label": MOD_CATEGORIES.get(category, category),
            "confidence": confidence,
            "suggested_action": action,
            "reasoning": response.text[:200],
            "model_id": model_spec.model_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "disclaimer": (
                "Moderation recommendations are advisory only. "
                "All moderation decisions require human approval. "
                "Content is not automatically removed or hidden."
            ),
        }

    except Exception as exc:
        return {
            "error": f"Moderation analysis failed: {exc}",
            "category": "unknown",
            "suggested_action": "allow",
            "confidence": 0.0,
        }


async def moderate_report_comments(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    provider: LLMProvider | None = None,
    router: ModelRouter | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Moderate all comments on a report. Returns per-comment recommendations."""
    stmt = (
        select(ReportComment)
        .where(
            ReportComment.report_id == report_id,
            ReportComment.is_removed.is_(False),
        )
        .order_by(ReportComment.created_at.desc())
        .limit(limit)
    )
    comments = (await session.execute(stmt)).scalars().all()

    results = []
    flagged_count = 0
    for comment in comments:
        result = await moderate_content(
            session,
            content=comment.body,
            content_type="comment",
            content_id=comment.id,
            provider=provider,
            router=router,
        )
        results.append(result)
        if result.get("suggested_action") in ("flag", "hide"):
            flagged_count += 1

    return {
        "report_id": str(report_id),
        "total_comments": len(comments),
        "flagged_count": flagged_count,
        "results": results,
        "note": (
            f"{flagged_count} comments flagged for human review. "
            "No comments have been removed or hidden."
        ),
    }
