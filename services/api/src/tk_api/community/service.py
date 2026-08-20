"""Phase 13 community service: feed, comments, reactions, follows, saves,
blocks, profiles, share previews, moderation (PRD §8, §15, §20, API.md §10).

Feed ranking is explicit and explainable — never a black box. Every item
carries a ``score_explanation`` with its components and human-readable
``reasons``. The formula (documented in ARCHITECTURE.md §Feed ranking):

    score = recency * 5 + relevance + follow + verification + engagement

* recency      — exponential decay, half-life ≈ 33h (exp(-hours/48))
* relevance    — you follow the report's category (+2) or institution (+1.5)
* follow       — you follow the report itself or its author (+1.5 each)
* verification — info_class weight (OFFICIAL_DATA=3 → +1.0 … UNVERIFIED=0)
* engagement   — capped confirmations+reactions (min(n,30)/30 * 1.5) so
                 engagement can never outweigh freshness: engagement ≠ truth.

Rules enforced here (Phase 13 spec): max comment depth 2 (a reply has no
replies); one reaction per user per report; blocked users' content is hidden
from the blocker everywhere; security notifications are never disabled;
no private contact fields are ever exposed on public profiles.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.analytics.models import AnalyticsEvent
from tk_api.community.models import (
    Bookmark,
    CategoryFollower,
    ContentReport,
    GeographyFollower,
    InstitutionFollower,
    Reaction,
    UserBlock,
    UserFollow,
)
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.core.pagination import decode_cursor, encode_cursor
from tk_api.institutions.models import Institution
from tk_api.media.models import MediaObject
from tk_api.notifications.events import (
    queue_follow,
    queue_mention,
    queue_moderation_notice,
    queue_reaction,
    queue_reply,
)
from tk_api.reports.models import (
    Report,
    ReportComment,
    ReportEvidence,
    ReportFollower,
    ReportVerification,
)
from tk_api.users.models import User

REACTION_KINDS = ("like", "helpful", "confirm", "celebrate", "flag")
INFO_CLASS_WEIGHTS = {
    "OFFICIAL_DATA": 3,
    "COMMUNITY_VERIFIED": 2,
    "AI_ANALYSIS": 1,
    "CITIZEN_REPORT": 0.5,
    "UNVERIFIED_INFORMATION": 0,
}
MAX_COMMENT_DEPTH = 2
FEED_CANDIDATE_DAYS = 90
FEED_CANDIDATE_LIMIT = 400
MODERATOR_ROLES = ("moderator", "admin", "super_admin")


class CommunityError(ApiError):
    pass


def _coerce_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; normalize to aware UTC for math."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_uuid(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise CommunityError(f"invalid {kind} id", 422, error_kind) from exc


async def _blocked_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = (
        (await session.execute(select(UserBlock.blocked_id).where(UserBlock.blocker_id == user_id)))
        .scalars()
        .all()
    )
    return set(rows)


async def _report_or_404(session: AsyncSession, report_id: uuid.UUID) -> Report:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise CommunityError("report not found", 404, "report_not_found")
    return report


def _has_moderator_role(user: Any) -> bool:
    return any(user.has_role(role) for role in MODERATOR_ROLES)


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


def _feed_score(
    report: Report,
    now: datetime,
    *,
    followed_categories: set[uuid.UUID],
    followed_institutions: set[uuid.UUID],
    followed_reports: set[uuid.UUID],
    followed_users: set[uuid.UUID],
    confirms: int,
    reactions: int,
) -> tuple[float, dict[str, float], list[str]]:
    hours = max(0.0, (now - _coerce_utc(report.created_at)).total_seconds() / 3600.0)
    recency = math.exp(-hours / 48.0)

    relevance = 0.0
    reasons: list[str] = []
    if report.category_id in followed_categories:
        relevance += 2.0
        reasons.append("you follow this category")
    if report.institution_id and report.institution_id in followed_institutions:
        relevance += 1.5
        reasons.append("you follow this institution")

    follow = 0.0
    if report.id in followed_reports:
        follow += 1.5
        reasons.append("you follow this report")
    if report.reporter_id in followed_users:
        follow += 1.5
        reasons.append("you follow this reporter")

    verification = INFO_CLASS_WEIGHTS.get(report.info_class, 0) / 3.0
    if verification >= 2 / 3:
        reasons.append("community verified")

    engagement = min(confirms + reactions, 30) / 30.0 * 1.5
    if confirms + reactions >= 5:
        reasons.append("active community discussion")

    if recency > 0.6:
        reasons.append("recent update")

    score = recency * 5.0 + relevance + follow + verification + engagement
    components = {
        "score": round(score, 3),
        "recency": round(recency * 5.0, 3),
        "relevance": round(relevance, 3),
        "follow": round(follow, 3),
        "verification": round(verification, 3),
        "engagement": round(engagement, 3),
    }
    return score, components, reasons[:4]


async def _aggregate_counts(
    session: AsyncSession, report_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    counts: dict[uuid.UUID, dict[str, int]] = {}
    for rid in report_ids:
        counts[rid] = {
            "reactions": 0,
            "confirms": 0,
            "refutes": 0,
            "comments": 0,
            "followers": 0,
            "saves": 0,
        }

    if not report_ids:
        return counts

    reaction_rows = (
        await session.execute(
            select(Reaction.report_id, func.count(Reaction.id))
            .where(Reaction.report_id.in_(report_ids))
            .group_by(Reaction.report_id)
        )
    ).all()
    for rid, n in reaction_rows:
        counts[rid]["reactions"] = n

    confirm_rows = (
        await session.execute(
            select(
                ReportVerification.report_id,
                ReportVerification.kind,
                func.count(ReportVerification.id),
            )
            .where(ReportVerification.report_id.in_(report_ids))
            .group_by(ReportVerification.report_id, ReportVerification.kind)
        )
    ).all()
    for rid, kind, n in confirm_rows:
        counts[rid]["confirms" if kind == "confirm" else "refutes"] = n

    comment_rows = (
        await session.execute(
            select(ReportComment.report_id, func.count(ReportComment.id))
            .where(ReportComment.report_id.in_(report_ids))
            .group_by(ReportComment.report_id)
        )
    ).all()
    for rid, n in comment_rows:
        counts[rid]["comments"] = n

    follower_rows = (
        await session.execute(
            select(ReportFollower.report_id, func.count(ReportFollower.user_id))
            .where(ReportFollower.report_id.in_(report_ids))
            .group_by(ReportFollower.report_id)
        )
    ).all()
    for rid, n in follower_rows:
        counts[rid]["followers"] = n

    save_rows = (
        await session.execute(
            select(Bookmark.report_id, func.count(Bookmark.id))
            .where(Bookmark.report_id.in_(report_ids))
            .group_by(Bookmark.report_id)
        )
    ).all()
    for rid, n in save_rows:
        counts[rid]["saves"] = n

    return counts


async def _media_thumbnails(
    session: AsyncSession,
    report_ids: list[uuid.UUID],
    *,
    storage: Any,
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Public, scan-clean image thumbnails only (private media never leaks)."""
    thumbs: dict[uuid.UUID, list[dict[str, Any]]] = {rid: [] for rid in report_ids}
    if not report_ids:
        return thumbs
    rows = (
        await session.execute(
            select(ReportEvidence.report_id, MediaObject)
            .join(MediaObject, MediaObject.id == ReportEvidence.media_object_id)
            .where(
                ReportEvidence.report_id.in_(report_ids),
                ReportEvidence.moderation_status == "approved",
                MediaObject.scan_status == "clean",
                MediaObject.status == "available",
                MediaObject.mime_type.startswith("image/"),
            )
            .order_by(ReportEvidence.uploaded_at.asc())
        )
    ).all()
    for report_id, media in rows:
        thumbs.setdefault(report_id, [])
        if len(thumbs[report_id]) >= 4:
            continue
        url = (
            storage.download_url(media.bucket, media.object_key, expires_seconds=3600)
            if storage
            else None
        )
        thumbs[report_id].append({"id": str(media.id), "mime_type": media.mime_type, "url": url})
    return thumbs


async def _report_card(
    session: AsyncSession,
    report: Report,
    *,
    counts: dict[str, int],
    viewer: Any,
    my_reaction: str | None = None,
    saved: bool = False,
    followed: bool = False,
    score_info: dict[str, Any] | None = None,
    storage: Any = None,
) -> dict[str, Any]:
    reporter = await session.scalar(select(User).where(User.id == report.reporter_id))
    category = None
    if report.category_id:
        from tk_api.civic.models import Category

        category = await session.get(Category, report.category_id)
    institution = None
    if report.institution_id:
        institution = await session.get(Institution, report.institution_id)

    return {
        "id": str(report.id),
        "ticket_no": report.ticket_no,
        "title": report.title,
        "description": report.description,
        "status": report.status,
        "severity": report.severity,
        "info_class": report.info_class,
        "trust_score": float(report.trust_score or 0),
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        "boundary_id": str(report.boundary_id) if report.boundary_id else None,
        "address_hint": report.address_hint,
        "location_accuracy_m": float(report.location_accuracy_m or 0),
        "reporter": {
            "id": str(report.reporter_id),
            "username": reporter.username if reporter else None,
            "display_name": reporter.display_name if reporter else None,
        },
        "category": {
            "slug": category.slug,
            "name": (category.default_locale_keys or {}).get("en") or category.slug.title(),
        }
        if category
        else None,
        "institution": {"id": str(institution.id), "name": institution.name}
        if institution
        else None,
        "stats": counts,
        "my_reaction": my_reaction,
        "saved": saved,
        "followed": followed,
        "verification": {
            "confirms": counts["confirms"],
            "refutes": counts["refutes"],
            "verified": counts["confirms"] > counts["refutes"],
        },
        "score_explanation": score_info,
    }


def _apply_chrono_cursor(stmt: Any, cursor: str) -> Any:
    """Filter after a "{created_at_iso}|{id}" cursor (latest/geography tabs)."""
    try:
        created_raw, report_raw = decode_cursor(cursor).split("|")
        created_at = datetime.fromisoformat(created_raw)
        report_id = uuid.UUID(report_raw)
    except (ValueError, TypeError):
        raise CommunityError("invalid feed cursor", 422, "invalid_cursor") from None
    return stmt.where(
        (Report.created_at < created_at)
        | ((Report.created_at == created_at) & (Report.id < report_id))
    )


async def list_feed(
    session: AsyncSession,
    *,
    viewer: Any,
    tab: str,
    boundary_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = 25,
    storage: Any = None,
) -> dict[str, Any]:
    """Public feed with tabs; ranked tabs are scored and explained in Python
    (portable across Postgres + SQLite), latest is SQL-ordered."""
    now = _utcnow()
    blocked = await _blocked_ids(session, viewer.id)
    base: list[Any] = [
        Report.visibility == "public",
        Report.deleted_at.is_(None),
    ]
    if blocked:
        base.append(Report.reporter_id.notin_(blocked))

    if tab == "geography":
        if boundary_id is None:
            raise CommunityError(
                "boundary_id is required for the geography tab", 422, "boundary_required"
            )
        stmt = (
            select(Report)
            .where(*base, Report.boundary_id == boundary_id)
            .order_by(Report.created_at.desc())
        )
        if cursor:
            stmt = _apply_chrono_cursor(stmt, cursor)
        reports = list((await session.execute(stmt.limit(limit + 1))).scalars().all())
        has_more = len(reports) > limit
        reports = reports[:limit]
        score_info = None
    elif tab == "latest":
        stmt = select(Report).where(*base).order_by(Report.created_at.desc())
        if cursor:
            stmt = _apply_chrono_cursor(stmt, cursor)
        reports = list((await session.execute(stmt.limit(limit + 1))).scalars().all())
        has_more = len(reports) > limit
        reports = reports[:limit]
        score_info = None
    else:
        cutoff = now - timedelta(days=FEED_CANDIDATE_DAYS)
        stmt = (
            select(Report)
            .where(*base, Report.created_at >= cutoff)
            .order_by(Report.created_at.desc())
            .limit(FEED_CANDIDATE_LIMIT)
        )
        candidates = list((await session.execute(stmt)).scalars().all())
        if not candidates:
            reports, score_info, has_more = [], None, False
        else:
            report_ids = [r.id for r in candidates]
            counts = await _aggregate_counts(session, report_ids)
            followed_categories = set(
                (
                    await session.execute(
                        select(CategoryFollower.category_id).where(
                            CategoryFollower.user_id == viewer.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            followed_institutions = set(
                (
                    await session.execute(
                        select(InstitutionFollower.institution_id).where(
                            InstitutionFollower.user_id == viewer.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            followed_reports = set(
                (
                    await session.execute(
                        select(ReportFollower.report_id).where(ReportFollower.user_id == viewer.id)
                    )
                )
                .scalars()
                .all()
            )
            followed_users = set(
                (
                    await session.execute(
                        select(UserFollow.following_id).where(UserFollow.follower_id == viewer.id)
                    )
                )
                .scalars()
                .all()
            )

            ranked: list[tuple[float, Report, dict[str, Any]]] = []
            for report in candidates:
                if tab == "following":
                    in_following = (
                        report.id in followed_reports
                        or report.reporter_id in followed_users
                        or (
                            report.institution_id and report.institution_id in followed_institutions
                        )
                        or (report.category_id and report.category_id in followed_categories)
                    )
                    if not in_following:
                        continue
                score, components, reasons = _feed_score(
                    report,
                    now,
                    followed_categories=followed_categories,
                    followed_institutions=followed_institutions,
                    followed_reports=followed_reports,
                    followed_users=followed_users,
                    confirms=counts[report.id]["confirms"],
                    reactions=counts[report.id]["reactions"],
                )
                if tab == "trending":
                    score = min(counts[report.id]["confirms"] + counts[report.id]["reactions"], 50)
                    components = {"score": score}
                ranked.append(
                    (
                        score,
                        report,
                        {
                            "components": components,
                            "reasons": reasons,
                        },
                    )
                )

            ranked.sort(key=lambda item: (-item[0], item[1].created_at))
            # cursor: "{score}|{id}"
            offset_score, offset_id = None, None
            if cursor:
                try:
                    raw_score, raw_id = decode_cursor(cursor).split("|")
                    offset_score, offset_id = float(raw_score), uuid.UUID(raw_id)
                except (ValueError, TypeError):
                    raise CommunityError("invalid feed cursor", 422, "invalid_cursor") from None
            filtered: list[tuple[float, Report, dict[str, Any]]] = []
            for score, report, info in ranked:
                if offset_score is not None:
                    if score < offset_score:
                        continue
                    if score == offset_score and str(report.id) <= str(offset_id):
                        continue
                filtered.append((score, report, info))
            has_more = len(filtered) > limit
            page = filtered[:limit]
            reports = [r for _, r, _ in page]
            score_map = {r.id: {"score": s, **info} for s, r, info in page}
            score_info = score_map

    # viewer state + thumbnails for the page
    my_reactions = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(Reaction.report_id, Reaction.kind).where(
                    Reaction.report_id.in_([r.id for r in reports]),
                    Reaction.user_id == viewer.id,
                )
            )
        ).all()
    }
    saved_ids = set(
        (
            await session.execute(
                select(Bookmark.report_id).where(
                    Bookmark.report_id.in_([r.id for r in reports]),
                    Bookmark.user_id == viewer.id,
                )
            )
        )
        .scalars()
        .all()
    )
    followed_ids = set(
        (
            await session.execute(
                select(ReportFollower.report_id).where(
                    ReportFollower.report_id.in_([r.id for r in reports]),
                    ReportFollower.user_id == viewer.id,
                )
            )
        )
        .scalars()
        .all()
    )
    page_counts = await _aggregate_counts(session, [r.id for r in reports])
    thumbs = await _media_thumbnails(session, [r.id for r in reports], storage=storage)

    items: list[dict[str, Any]] = []
    for report in reports:
        card = await _report_card(
            session,
            report,
            counts=page_counts[report.id],
            viewer=viewer,
            my_reaction=my_reactions.get(report.id),
            saved=report.id in saved_ids,
            followed=report.id in followed_ids,
            score_info=score_info.get(report.id) if score_info else None,
            storage=storage,
        )
        card["media"] = thumbs.get(report.id, [])
        items.append(card)

    next_cursor: str | None = None
    if has_more and reports:
        last = reports[-1]
        if score_info is not None:
            next_cursor = encode_cursor(f"{score_info[last.id]['score']}|{last.id}")
        else:
            next_cursor = encode_cursor(f"{last.created_at.isoformat()}|{last.id}")

    session.add(
        AnalyticsEvent(
            event_kind="feed.viewed",
            actor_id=viewer.id,
            content_type="feed",
            payload={"tab": tab},
        )
    )
    await session.commit()
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


# ---------------------------------------------------------------------------
# Comments (threaded, depth ≤ 2, moderation-aware)
# ---------------------------------------------------------------------------


async def list_comment_threads(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    viewer_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Top-level comments with their single level of replies. Removed comments
    are shown masked ("[removed]") for transparency; blocked authors are hidden."""
    await _report_or_404(session, report_id)
    blocked = await _blocked_ids(session, viewer_id)
    rows = (
        await session.execute(
            select(ReportComment, User)
            .join(User, User.id == ReportComment.author_id)
            .where(ReportComment.report_id == report_id)
            .order_by(ReportComment.created_at.asc())
            .limit(max(1, min(limit, 300)) * 2)
        )
    ).all()

    def _entry(c: ReportComment, u: User) -> dict[str, Any]:
        if c.is_removed:
            return {
                "id": str(c.id),
                "report_id": str(c.report_id),
                "author": None,
                "body": "[removed]",
                "removed": True,
                "parent_id": str(c.parent_id) if c.parent_id else None,
                "created_at": c.created_at.isoformat(),
                "edited_at": c.edited_at.isoformat() if c.edited_at else None,
            }
        return {
            "id": str(c.id),
            "report_id": str(c.report_id),
            "author": {
                "id": str(c.author_id),
                "username": u.username,
                "display_name": u.display_name or "Citizen",
            },
            "body": c.body,
            "removed": False,
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "created_at": c.created_at.isoformat(),
            "edited_at": c.edited_at.isoformat() if c.edited_at else None,
        }

    top: list[dict[str, Any]] = []
    replies_by_parent: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for comment, user in rows:
        if comment.author_id in blocked:
            continue
        entry = _entry(comment, user)
        if comment.parent_id is None:
            entry["replies"] = []
            top.append(entry)
        else:
            replies_by_parent.setdefault(comment.parent_id, []).append(entry)
    for item in top:
        item["replies"] = replies_by_parent.get(uuid.UUID(item["id"]), [])
    return top


async def add_reply(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    parent_id: uuid.UUID,
    body: str,
    author: User,
    mentionee_ids: list[uuid.UUID] | None = None,
) -> dict[str, Any]:
    """Reply to a top-level comment (depth ≤ 2). Queues reply + mention events."""
    report = await _report_or_404(session, report_id)
    parent = await session.get(ReportComment, parent_id)
    if parent is None or parent.report_id != report.id:
        raise CommunityError("parent comment not found on this report", 404, "comment_not_found")
    if parent.parent_id is not None:
        raise CommunityError(
            f"comments are limited to {MAX_COMMENT_DEPTH} levels", 422, "max_comment_depth"
        )
    if not body.strip():
        raise CommunityError("comment body cannot be empty", 422, "empty_comment")

    row = ReportComment(
        report_id=report.id,
        author_id=author.id,
        parent_id=parent.id,
        body=body.strip(),
    )
    session.add(row)
    await queue_reply(session, report=report, parent=parent, actor_id=author.id)
    if mentionee_ids:
        await queue_mention(session, report=report, mentionee_ids=mentionee_ids, actor_id=author.id)
    session.add(
        AnalyticsEvent(
            event_kind="comment.created",
            actor_id=author.id,
            content_type="comment",
            content_id=row.id,
            geography_id=None,
            payload={"report_id": str(report.id), "depth": 2},
        )
    )
    await session.commit()
    return {
        "id": str(row.id),
        "report_id": str(row.report_id),
        "parent_id": str(row.parent_id),
        "body": row.body,
        "created_at": row.created_at.isoformat(),
    }


async def edit_comment(
    session: AsyncSession,
    comment_id: uuid.UUID,
    *,
    body: str,
    user: User,
    request: Request,
) -> dict[str, Any]:
    comment = await session.get(ReportComment, comment_id)
    if comment is None:
        raise CommunityError("comment not found", 404, "comment_not_found")
    if comment.author_id != user.id and not _has_moderator_role(user):
        raise CommunityError("only the author may edit a comment", 403, "forbidden")
    if not body.strip():
        raise CommunityError("comment body cannot be empty", 422, "empty_comment")
    comment.body = body.strip()
    comment.edited_at = _utcnow()
    comment.updated_at = _utcnow()
    await audit(
        session,
        action="community.comment_edit",
        entity_type="report_comment",
        entity_id=comment.id,
        actor_id=user.id,
        after={"body": body.strip()},
        request=request,
    )
    await session.commit()
    return {"id": str(comment.id), "body": comment.body, "edited_at": comment.edited_at.isoformat()}


async def remove_comment(
    session: AsyncSession,
    comment_id: uuid.UUID,
    *,
    user: User,
    reason: str | None = None,
    request: Request,
) -> dict[str, Any]:
    """Author or moderator removes a comment (soft-delete, audited)."""
    comment = await session.get(ReportComment, comment_id)
    if comment is None:
        raise CommunityError("comment not found", 404, "comment_not_found")
    if comment.author_id != user.id and not _has_moderator_role(user):
        raise CommunityError(
            "only the author or a moderator may remove a comment", 403, "forbidden"
        )
    if comment.is_removed:
        raise CommunityError("comment already removed", 409, "already_removed")

    is_moderation = comment.author_id != user.id
    comment.is_removed = True
    comment.removed_by = user.id
    comment.removal_reason = reason
    comment.updated_at = _utcnow()
    if is_moderation:
        await queue_moderation_notice(
            session,
            user_id=comment.author_id,
            event="community.moderation.comment_removed",
            payload={"comment_id": str(comment.id)},
            actor_id=user.id,
        )
    await audit(
        session,
        action="community.comment_remove",
        entity_type="report_comment",
        entity_id=comment.id,
        actor_id=user.id,
        after={"reason": reason, "moderation": is_moderation},
        request=request,
    )
    await session.commit()
    return {"id": str(comment.id), "removed": True}


async def restore_comment(
    session: AsyncSession,
    comment_id: uuid.UUID,
    *,
    user: User,
    request: Request,
) -> dict[str, Any]:
    if not _has_moderator_role(user):
        raise CommunityError("only moderators may restore comments", 403, "forbidden")
    comment = await session.get(ReportComment, comment_id)
    if comment is None:
        raise CommunityError("comment not found", 404, "comment_not_found")
    if not comment.is_removed:
        raise CommunityError("comment is not removed", 409, "not_removed")
    comment.is_removed = False
    comment.removed_by = None
    comment.removal_reason = None
    comment.updated_at = _utcnow()
    await audit(
        session,
        action="community.comment_restore",
        entity_type="report_comment",
        entity_id=comment.id,
        actor_id=user.id,
        after={},
        request=request,
    )
    await session.commit()
    return {"id": str(comment.id), "removed": False}


async def report_content(
    session: AsyncSession,
    *,
    content_type: str,
    content_id: uuid.UUID,
    reason: str,
    details: str | None,
    user: User,
    request: Request,
) -> dict[str, Any]:
    existing = await session.scalar(
        select(ContentReport).where(
            ContentReport.content_type == content_type,
            ContentReport.content_id == content_id,
            ContentReport.reporter_id == user.id,
        )
    )
    if existing is not None:
        raise CommunityError("you have already reported this content", 409, "already_reported")
    row = ContentReport(
        reporter_id=user.id,
        content_type=content_type,
        content_id=content_id,
        reason=reason,
        details=details,
        status="open",
    )
    session.add(row)
    await audit(
        session,
        action="community.content_report",
        entity_type=content_type,
        entity_id=content_id,
        actor_id=user.id,
        after={"reason": reason},
        request=request,
    )
    await session.commit()
    return {"id": str(row.id), "status": "open"}


# ---------------------------------------------------------------------------
# Reactions (one per user per report; toggleable)
# ---------------------------------------------------------------------------


async def set_reaction(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    comment_id: uuid.UUID | None,
    kind: str,
    user: User,
    request: Request,
) -> dict[str, Any]:
    if kind not in REACTION_KINDS:
        raise CommunityError(
            f"reaction kind must be one of {REACTION_KINDS}", 422, "invalid_reaction"
        )
    if comment_id is None:
        report = await _report_or_404(session, report_id)
        await session.execute(
            delete(Reaction).where(Reaction.user_id == user.id, Reaction.report_id == report.id)
        )
        row = Reaction(user_id=user.id, kind=kind, report_id=report.id)
        session.add(row)
        await queue_reaction(session, report=report, actor_id=user.id, kind=kind)
        session.add(
            AnalyticsEvent(
                event_kind="reaction.created",
                actor_id=user.id,
                content_type="report",
                content_id=report.id,
                payload={"kind": kind},
            )
        )
    else:
        comment = await session.get(ReportComment, comment_id)
        if comment is None:
            raise CommunityError("comment not found", 404, "comment_not_found")
        await session.execute(
            delete(Reaction).where(
                Reaction.user_id == user.id,
                Reaction.comment_id == comment.id,
                Reaction.kind == kind,
            )
        )
        row = Reaction(user_id=user.id, kind=kind, comment_id=comment.id)
        session.add(row)
    await audit(
        session,
        action="community.reaction",
        entity_type="report_comment" if comment_id else "report",
        entity_id=comment_id or report_id,
        actor_id=user.id,
        after={"kind": kind},
        request=request,
    )
    await session.commit()
    counts = await _aggregate_counts(session, [report_id])
    return {"reaction": kind, "counts": counts[report_id]}


async def remove_reaction(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    comment_id: uuid.UUID | None,
    user: User,
) -> dict[str, Any]:
    if comment_id is None:
        await session.execute(
            delete(Reaction).where(Reaction.user_id == user.id, Reaction.report_id == report_id)
        )
    else:
        await session.execute(
            delete(Reaction).where(Reaction.user_id == user.id, Reaction.comment_id == comment_id)
        )
    await session.commit()
    return {"reaction": None}


# ---------------------------------------------------------------------------
# Saves (bookmarks)
# ---------------------------------------------------------------------------


async def save_report(session: AsyncSession, report_id: uuid.UUID, *, user: User) -> dict[str, Any]:
    await _report_or_404(session, report_id)
    existing = await session.scalar(
        select(Bookmark).where(Bookmark.report_id == report_id, Bookmark.user_id == user.id)
    )
    if existing is None:
        session.add(Bookmark(report_id=report_id, user_id=user.id))
        session.add(
            AnalyticsEvent(
                event_kind="save.created",
                actor_id=user.id,
                content_type="report",
                content_id=report_id,
            )
        )
        await session.commit()
    return {"status": "saved"}


async def unsave_report(
    session: AsyncSession, report_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    await session.execute(
        delete(Bookmark).where(Bookmark.report_id == report_id, Bookmark.user_id == user.id)
    )
    await session.commit()
    return {"status": "unsaved"}


async def list_saved(
    session: AsyncSession,
    *,
    user: User,
    cursor: str | None = None,
    limit: int = 25,
    storage: Any = None,
) -> dict[str, Any]:
    stmt = (
        select(Bookmark, Report)
        .join(Report, Report.id == Bookmark.report_id)
        .where(Bookmark.user_id == user.id, Report.deleted_at.is_(None))
        .order_by(Bookmark.created_at.desc())
    )
    if cursor:
        try:
            created_at_raw, report_id_raw = decode_cursor(cursor).split("|")
            stmt = stmt.where(
                (Bookmark.created_at < datetime.fromisoformat(created_at_raw))
                | (
                    (Bookmark.created_at == datetime.fromisoformat(created_at_raw))
                    & (
                        Bookmark.report_id
                        < _parse_uuid(report_id_raw, kind="report", error_kind="invalid_report_id")
                    )
                )
            )
        except (ValueError, TypeError):
            raise CommunityError("invalid saved-cursor", 422, "invalid_cursor") from None
    rows = list((await session.execute(stmt.limit(limit + 1))).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    report_ids = [r.id for _, r in rows]
    counts = await _aggregate_counts(session, report_ids)
    thumbs = await _media_thumbnails(session, report_ids, storage=storage)
    items = []
    for _bookmark, report in rows:
        card = await _report_card(
            session, report, counts=counts[report.id], viewer=user, saved=True, storage=storage
        )
        card["media"] = thumbs.get(report.id, [])
        items.append(card)
    next_cursor = None
    if has_more and rows:
        bookmark, report = rows[-1]
        next_cursor = encode_cursor(f"{bookmark.created_at.isoformat()}|{report.id}")
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


# ---------------------------------------------------------------------------
# Follows (reports, institutions, geographies, categories, users)
# ---------------------------------------------------------------------------


async def follow_category(
    session: AsyncSession, category_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    from tk_api.civic.models import Category

    category = await session.get(Category, category_id)
    if category is None:
        raise CommunityError("category not found", 404, "category_not_found")
    existing = await session.scalar(
        select(CategoryFollower).where(
            CategoryFollower.category_id == category_id, CategoryFollower.user_id == user.id
        )
    )
    if existing is None:
        session.add(CategoryFollower(category_id=category_id, user_id=user.id))
        await session.commit()
    return {"status": "following", "category_id": str(category_id)}


async def unfollow_category(
    session: AsyncSession, category_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    await session.execute(
        delete(CategoryFollower).where(
            CategoryFollower.category_id == category_id, CategoryFollower.user_id == user.id
        )
    )
    await session.commit()
    return {"status": "not_following", "category_id": str(category_id)}


async def follow_user(session: AsyncSession, target_id: uuid.UUID, *, user: User) -> dict[str, Any]:
    if target_id == user.id:
        raise CommunityError("you cannot follow yourself", 422, "cannot_follow_self")
    target = await session.get(User, target_id)
    if target is None or target.status != "active":
        raise CommunityError("user not found", 404, "user_not_found")
    blocked = await _blocked_ids(session, user.id)
    if target_id in blocked:
        raise CommunityError("cannot follow a blocked user", 409, "blocked")
    existing = await session.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == user.id, UserFollow.following_id == target_id
        )
    )
    if existing is None:
        session.add(UserFollow(follower_id=user.id, following_id=target_id))
        await queue_follow(session, following_id=target_id, actor_id=user.id)
        session.add(
            AnalyticsEvent(
                event_kind="follow.created",
                actor_id=user.id,
                content_type="user",
                content_id=target_id,
            )
        )
        await session.commit()
    return {"status": "following", "user_id": str(target_id)}


async def unfollow_user(
    session: AsyncSession, target_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    await session.execute(
        delete(UserFollow).where(
            UserFollow.follower_id == user.id, UserFollow.following_id == target_id
        )
    )
    await session.commit()
    return {"status": "not_following", "user_id": str(target_id)}


async def follow_institution(
    session: AsyncSession, institution_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    institution = await session.get(Institution, institution_id)
    if institution is None:
        raise CommunityError("institution not found", 404, "institution_not_found")
    existing = await session.scalar(
        select(InstitutionFollower).where(
            InstitutionFollower.institution_id == institution_id,
            InstitutionFollower.user_id == user.id,
        )
    )
    if existing is None:
        session.add(InstitutionFollower(institution_id=institution_id, user_id=user.id))
        await session.commit()
    return {"status": "following", "institution_id": str(institution_id)}


async def unfollow_institution(
    session: AsyncSession, institution_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    await session.execute(
        delete(InstitutionFollower).where(
            InstitutionFollower.institution_id == institution_id,
            InstitutionFollower.user_id == user.id,
        )
    )
    await session.commit()
    return {"status": "not_following", "institution_id": str(institution_id)}


async def follow_geography(
    session: AsyncSession, geography_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    from tk_api.geography.models import Geography

    geography = await session.get(Geography, geography_id)
    if geography is None:
        raise CommunityError("geography not found", 404, "geography_not_found")
    existing = await session.scalar(
        select(GeographyFollower).where(
            GeographyFollower.geography_id == geography_id, GeographyFollower.user_id == user.id
        )
    )
    if existing is None:
        session.add(GeographyFollower(geography_id=geography_id, user_id=user.id))
        await session.commit()
    return {"status": "following", "geography_id": str(geography_id)}


async def unfollow_geography(
    session: AsyncSession, geography_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    await session.execute(
        delete(GeographyFollower).where(
            GeographyFollower.geography_id == geography_id,
            GeographyFollower.user_id == user.id,
        )
    )
    await session.commit()
    return {"status": "not_following", "geography_id": str(geography_id)}


async def follows_summary(session: AsyncSession, user: User) -> dict[str, int]:
    counts: dict[str, int] = {}
    reports = await session.scalar(
        select(func.count(ReportFollower.report_id)).where(ReportFollower.user_id == user.id)
    )
    institutions = await session.scalar(
        select(func.count(InstitutionFollower.institution_id)).where(
            InstitutionFollower.user_id == user.id
        )
    )
    geographies = await session.scalar(
        select(func.count(GeographyFollower.geography_id)).where(
            GeographyFollower.user_id == user.id
        )
    )
    categories = await session.scalar(
        select(func.count(CategoryFollower.category_id)).where(CategoryFollower.user_id == user.id)
    )
    users = await session.scalar(
        select(func.count(UserFollow.following_id)).where(UserFollow.follower_id == user.id)
    )
    counts = {
        "reports": reports or 0,
        "institutions": institutions or 0,
        "geographies": geographies or 0,
        "categories": categories or 0,
        "users": users or 0,
    }
    return counts


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


async def block_user(
    session: AsyncSession, target_id: uuid.UUID, *, user: User, request: Request
) -> dict[str, Any]:
    if target_id == user.id:
        raise CommunityError("you cannot block yourself", 422, "cannot_block_self")
    target = await session.get(User, target_id)
    if target is None:
        raise CommunityError("user not found", 404, "user_not_found")
    existing = await session.scalar(
        select(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_id)
    )
    if existing is None:
        session.add(UserBlock(blocker_id=user.id, blocked_id=target_id))
        await session.execute(
            delete(UserFollow).where(
                ((UserFollow.follower_id == user.id) & (UserFollow.following_id == target_id))
                | ((UserFollow.follower_id == target_id) & (UserFollow.following_id == user.id))
            )
        )
        session.add(
            AnalyticsEvent(
                event_kind="block.created",
                actor_id=user.id,
                content_type="user",
                content_id=target_id,
            )
        )
        await audit(
            session,
            action="community.user_block",
            entity_type="user",
            entity_id=target_id,
            actor_id=user.id,
            after={},
            request=request,
        )
        await session.commit()
    return {"status": "blocked"}


async def unblock_user(
    session: AsyncSession, target_id: uuid.UUID, *, user: User, request: Request
) -> dict[str, Any]:
    await session.execute(
        delete(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_id)
    )
    await audit(
        session,
        action="community.user_unblock",
        entity_type="user",
        entity_id=target_id,
        actor_id=user.id,
        after={},
        request=request,
    )
    await session.commit()
    return {"status": "unblocked"}


# ---------------------------------------------------------------------------
# Public profiles + share previews
# ---------------------------------------------------------------------------


async def public_profile(session: AsyncSession, username: str, *, viewer: User) -> dict[str, Any]:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None or user.status != "active":
        raise CommunityError("user not found", 404, "user_not_found")
    blocked = await _blocked_ids(session, viewer.id)
    if user.id in blocked:
        raise CommunityError("user not found", 404, "user_not_found")

    reports_count = (
        await session.scalar(
            select(func.count(Report.id)).where(
                Report.reporter_id == user.id,
                Report.deleted_at.is_(None),
                Report.visibility == "public",
            )
        )
    ) or 0
    confirm_rows = (
        await session.execute(
            select(ReportVerification.kind, func.count(ReportVerification.id))
            .join(Report, Report.id == ReportVerification.report_id)
            .where(Report.reporter_id == user.id)
            .group_by(ReportVerification.kind)
        )
    ).all()
    confirms = sum(n for kind, n in confirm_rows if kind == "confirm")
    refutes = sum(n for kind, n in confirm_rows if kind == "refute")
    followers = (
        await session.scalar(
            select(func.count(UserFollow.follower_id)).where(UserFollow.following_id == user.id)
        )
    ) or 0
    following = (
        await session.scalar(
            select(func.count(UserFollow.following_id)).where(UserFollow.follower_id == user.id)
        )
    ) or 0
    is_following = (
        await session.scalar(
            select(UserFollow).where(
                UserFollow.follower_id == viewer.id, UserFollow.following_id == user.id
            )
        )
    ) is not None
    is_blocked = (
        await session.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == viewer.id, UserBlock.blocked_id == user.id
            )
        )
    ) is not None

    return {
        "username": user.username,
        "display_name": user.display_name or "Citizen",
        "bio": user.bio,
        "profile_image_url": user.profile_image_url,
        "member_since": user.created_at.isoformat(),
        "locale": user.locale,
        "stats": {
            "reports": reports_count,
            "confirms_received": confirms,
            "refutes_received": refutes,
            "followers": followers,
            "following": following,
        },
        "my_state": {"is_following": is_following, "is_blocked": is_blocked},
    }


async def share_preview(
    session: AsyncSession, report_id: uuid.UUID, *, storage: Any = None
) -> dict[str, Any]:
    """Public share/OG data — never includes contact info or private locations."""
    report = await _report_or_404(session, report_id)
    if report.visibility != "public":
        raise CommunityError("report not found", 404, "report_not_found")
    reporter = await session.scalar(select(User).where(User.id == report.reporter_id))
    thumbs = await _media_thumbnails(session, [report.id], storage=storage)
    return {
        "title": report.title,
        "description": (report.description or "")[:300],
        "ticket_no": report.ticket_no,
        "status": report.status,
        "severity": report.severity,
        "info_class": report.info_class,
        "created_at": report.created_at.isoformat(),
        "boundary_id": str(report.boundary_id) if report.boundary_id else None,
        "address_hint": report.address_hint,
        "reporter_name": reporter.display_name if reporter else None,
        "thumbnail": thumbs.get(report.id, [{}])[0].get("url") if thumbs.get(report.id) else None,
    }


# ---------------------------------------------------------------------------
# Moderation queue (moderators)
# ---------------------------------------------------------------------------


async def list_moderation_queue(
    session: AsyncSession,
    *,
    user: User,
    status: str = "open",
    limit: int = 50,
) -> dict[str, Any]:
    if not _has_moderator_role(user):
        raise CommunityError("moderator role required", 403, "forbidden")
    rows = (
        (
            await session.execute(
                select(ContentReport)
                .where(ContentReport.status == status)
                .order_by(ContentReport.created_at.asc())
                .limit(max(1, min(limit, 200)))
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "content_type": r.content_type,
                "content_id": str(r.content_id),
                "reason": r.reason,
                "details": r.details,
                "status": r.status,
                "reporter_id": str(r.reporter_id),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "status": status,
    }


async def resolve_moderation_item(
    session: AsyncSession,
    item_id: uuid.UUID,
    *,
    action: str,
    user: User,
    reason: str | None = None,
    request: Request,
) -> dict[str, Any]:
    if not _has_moderator_role(user):
        raise CommunityError("moderator role required", 403, "forbidden")
    from tk_api.community.models import ModerationAction, ModerationDecision

    item = await session.get(ContentReport, item_id)
    if item is None:
        raise CommunityError("content report not found", 404, "content_report_not_found")
    if item.status != "open":
        raise CommunityError("content report already resolved", 409, "already_resolved")

    if action == "dismiss":
        item.status = "dismissed"
        session.add(
            ModerationAction(
                content_type=item.content_type,
                content_id=item.content_id,
                action="restore",
                reason=reason or "dismissed by moderator",
                moderator_id=user.id,
            )
        )
    elif action == "remove":
        item.status = "actioned"
        mod_action = ModerationAction(
            content_type=item.content_type,
            content_id=item.content_id,
            action="remove",
            reason=reason,
            moderator_id=user.id,
        )
        session.add(mod_action)
        await session.flush()
        session.add(
            ModerationDecision(
                moderation_action_id=mod_action.id,
                decision="upheld",
                decided_by=user.id,
            )
        )
        if item.content_type == "comment":
            comment = await session.get(ReportComment, item.content_id)
            if comment is not None and not comment.is_removed:
                comment.is_removed = True
                comment.removed_by = user.id
                comment.removal_reason = reason or "removed after community report"
                comment.updated_at = _utcnow()
                await queue_moderation_notice(
                    session,
                    user_id=comment.author_id,
                    event="community.moderation.comment_removed",
                    payload={"comment_id": str(comment.id)},
                    actor_id=user.id,
                )
    else:
        raise CommunityError("action must be 'dismiss' or 'remove'", 422, "invalid_action")

    await audit(
        session,
        action="community.moderation_resolve",
        entity_type="content_report",
        entity_id=item.id,
        actor_id=user.id,
        after={"action": action, "reason": reason},
        request=request,
    )
    await session.commit()
    return {"id": str(item.id), "status": item.status}
