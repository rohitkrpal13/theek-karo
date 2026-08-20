"""Phase 13 community endpoints: comments, reactions, saves, follows, blocks,
profiles, share previews, moderation queue (API.md §10, PRD §8, §15)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from tk_api.api.deps import CurrentUser, DbSession, require_active
from tk_api.community import participation
from tk_api.community import service as community_service
from tk_api.community.schemas import (
    CommentEditBody,
    CommentRemoveBody,
    ContentReportCreate,
    ModerationResolveBody,
    ReactionCreate,
)
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.reports import service as reports_service
from tk_api.reports.models import ReportComment

community_router = APIRouter(prefix="/api/v1/community", tags=["community"])

ActiveUser = Annotated[Any, Depends(require_active())]

FOLLOW_TYPES = ("report", "institution", "geography", "category", "user", "initiative")


def _parse_id(raw: str, *, kind: str, error_kind: str) -> Any:
    try:
        import uuid

        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


async def _storage(request: Request) -> Any:
    return getattr(request.app.state, "storage", None)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@community_router.get(
    "/reports/{report_id}/comments", summary="Threaded comments (replies ≤ depth 2)"
)
async def list_threaded_comments(
    report_id: str,
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=100, ge=1, le=300),
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    items = await community_service.list_comment_threads(
        session, parsed, viewer_id=user.id, limit=limit
    )
    return {"items": items}


@community_router.post(
    "/reports/{report_id}/comments/{comment_id}/replies",
    status_code=201,
    summary="Reply to a comment (one level deep)",
)
async def add_reply(
    report_id: str,
    comment_id: str,
    body: CommentEditBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="community", key=f"reply:{client_ip(request)}", limit=20, window_seconds=60
    )
    parsed_report = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    parsed_comment = _parse_id(comment_id, kind="comment", error_kind="invalid_comment_id")
    return await community_service.add_reply(
        session,
        report_id=parsed_report,
        parent_id=parsed_comment,
        body=body.body,
        author=user,
    )


@community_router.patch("/comments/{comment_id}", summary="Edit own comment (audited)")
async def edit_comment(
    comment_id: str,
    body: CommentEditBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(comment_id, kind="comment", error_kind="invalid_comment_id")
    return await community_service.edit_comment(
        session, parsed, body=body.body, user=user, request=request
    )


@community_router.post(
    "/comments/{comment_id}/remove", summary="Remove comment (author or moderator)"
)
async def remove_comment(
    comment_id: str,
    body: CommentRemoveBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(comment_id, kind="comment", error_kind="invalid_comment_id")
    return await community_service.remove_comment(
        session, parsed, user=user, reason=body.reason, request=request
    )


@community_router.post(
    "/comments/{comment_id}/restore", summary="Restore removed comment (moderator)"
)
async def restore_comment(
    comment_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(comment_id, kind="comment", error_kind="invalid_comment_id")
    return await community_service.restore_comment(session, parsed, user=user, request=request)


@community_router.post("/content-reports", status_code=201, summary="Report content for moderation")
async def report_content(
    body: ContentReportCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="community",
        key=f"report-content:{client_ip(request)}",
        limit=10,
        window_seconds=60,
    )
    return await community_service.report_content(
        session,
        content_type=body.content_type,
        content_id=_parse_id(body.content_id, kind="content", error_kind="invalid_content_id"),
        reason=body.reason,
        details=body.details,
        user=user,
        request=request,
    )


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------


@community_router.put(
    "/reports/{report_id}/reaction", summary="React to a report (one reaction per user per report)"
)
async def set_report_reaction(
    report_id: str,
    body: ReactionCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="community",
        key=f"reaction:{client_ip(request)}",
        limit=30,
        window_seconds=60,
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await community_service.set_reaction(
        session, report_id=parsed, comment_id=None, kind=body.kind, user=user, request=request
    )


@community_router.delete(
    "/reports/{report_id}/reaction", status_code=200, summary="Remove my reaction from a report"
)
async def remove_report_reaction(
    report_id: str,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await community_service.remove_reaction(
        session, report_id=parsed, comment_id=None, user=user
    )


@community_router.put("/comments/{comment_id}/reaction", summary="React to a comment")
async def set_comment_reaction(
    comment_id: str,
    body: ReactionCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="community",
        key=f"reaction:{client_ip(request)}",
        limit=30,
        window_seconds=60,
    )
    parsed = _parse_id(comment_id, kind="comment", error_kind="invalid_comment_id")
    comment = await session.get(ReportComment, parsed)
    if comment is None:
        raise ApiError("comment not found", 404, "comment_not_found")
    return await community_service.set_reaction(
        session,
        report_id=comment.report_id,
        comment_id=parsed,
        kind=body.kind,
        user=user,
        request=request,
    )


# ---------------------------------------------------------------------------
# Saves
# ---------------------------------------------------------------------------


@community_router.post("/reports/{report_id}/save", summary="Save a report")
async def save_report(
    report_id: str,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await community_service.save_report(session, parsed, user=user)


@community_router.delete("/reports/{report_id}/save", summary="Unsave a report")
async def unsave_report(
    report_id: str,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await community_service.unsave_report(session, parsed, user=user)


@community_router.get("/saved", summary="My saved reports")
async def list_saved(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=50),
) -> dict[str, Any]:
    return await community_service.list_saved(
        session, user=user, cursor=cursor, limit=limit, storage=await _storage(request)
    )


# ---------------------------------------------------------------------------
# Follows
# ---------------------------------------------------------------------------


@community_router.post("/follows/{follow_type}/{target_id}", summary="Follow an entity")
async def follow_entity(
    follow_type: str,
    target_id: str,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    if follow_type not in FOLLOW_TYPES:
        raise ApiError(f"follow_type must be one of {FOLLOW_TYPES}", 422, "invalid_follow_type")
    parsed = _parse_id(target_id, kind=follow_type, error_kind="invalid_target_id")
    if follow_type == "report":
        return await reports_service.follow_report(session, parsed, notify_level="all", user=user)
    if follow_type == "initiative":
        return await participation.follow_initiative(session, parsed, user=user)
    handlers = {
        "institution": community_service.follow_institution,
        "geography": community_service.follow_geography,
        "category": community_service.follow_category,
        "user": community_service.follow_user,
    }
    return await handlers[follow_type](session, parsed, user=user)


@community_router.delete("/follows/{follow_type}/{target_id}", summary="Unfollow an entity")
async def unfollow_entity(
    follow_type: str,
    target_id: str,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    if follow_type not in FOLLOW_TYPES:
        raise ApiError(f"follow_type must be one of {FOLLOW_TYPES}", 422, "invalid_follow_type")
    parsed = _parse_id(target_id, kind=follow_type, error_kind="invalid_target_id")
    if follow_type == "report":
        await reports_service.unfollow_report(session, parsed, user=user)
        return {"status": "not_following", "report_id": str(parsed)}
    if follow_type == "initiative":
        return await participation.unfollow_initiative(session, parsed, user=user)
    handlers = {
        "institution": community_service.unfollow_institution,
        "geography": community_service.unfollow_geography,
        "category": community_service.unfollow_category,
        "user": community_service.unfollow_user,
    }
    return await handlers[follow_type](session, parsed, user=user)


@community_router.get("/follows/summary", summary="My follow counts per entity type")
async def follows_summary(user: CurrentUser, session: DbSession) -> dict[str, int]:
    return await community_service.follows_summary(session, user)


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


@community_router.post("/users/{target_id}/block", summary="Block a user (mutual follow removal)")
async def block_user(
    target_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(target_id, kind="user", error_kind="invalid_user_id")
    return await community_service.block_user(session, parsed, user=user, request=request)


@community_router.delete("/users/{target_id}/block", summary="Unblock a user")
async def unblock_user(
    target_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(target_id, kind="user", error_kind="invalid_user_id")
    return await community_service.unblock_user(session, parsed, user=user, request=request)


# ---------------------------------------------------------------------------
# Profiles + share previews
# ---------------------------------------------------------------------------


@community_router.get("/users/{username}", summary="Public profile (no private contact fields)")
async def public_profile(
    username: str,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await community_service.public_profile(session, username, viewer=user)


@community_router.get("/share/reports/{report_id}", summary="Public share/OG preview")
async def share_preview(
    report_id: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await community_service.share_preview(session, parsed, storage=await _storage(request))


@community_router.post(
    "/reports/{report_id}/ai/discussion-summary",
    summary="AI advisory thread summary (reporter or moderator; no autonomous moderation)",
)
async def discussion_summary(
    report_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    from tk_api.ai.orchestrator import AgentOrchestrator
    from tk_api.reports.models import Report

    await rate_limit(
        request, bucket="ai", key=f"discussion:{client_ip(request)}", limit=10, window_seconds=60
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    report = await session.get(Report, parsed)
    if report is None or report.deleted_at is not None:
        raise ApiError("report not found", 404, "report_not_found")
    if report.reporter_id != user.id and not any(
        user.has_role(r) for r in ("moderator", "admin", "super_admin")
    ):
        raise ApiError("only the reporter or a moderator may request a summary", 403, "forbidden")
    thread = await community_service.list_comment_threads(
        session, parsed, viewer_id=user.id, limit=200
    )
    comments = [
        {
            "author": item["author"]["display_name"] if item["author"] else "removed",
            "body": item["body"],
            "replies": [r["body"] for r in item.get("replies", [])],
        }
        for item in thread
        if not item["removed"]
    ]
    orch = AgentOrchestrator(session)
    return await orch.summarize_discussion(
        ticket_no=report.ticket_no,
        status=report.status,
        title=report.title,
        comments=comments,
    )


# ---------------------------------------------------------------------------
# Moderation queue (moderators)
# ---------------------------------------------------------------------------


@community_router.get("/moderation/queue", summary="Open content reports (moderators)")
async def moderation_queue(
    user: CurrentUser,
    session: DbSession,
    status: str = Query(default="open"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return await community_service.list_moderation_queue(
        session, user=user, status=status, limit=limit
    )


@community_router.post(
    "/moderation/queue/{item_id}", summary="Dismiss or action a content report (moderators)"
)
async def resolve_moderation(
    item_id: str,
    body: ModerationResolveBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(item_id, kind="content_report", error_kind="invalid_content_report_id")
    return await community_service.resolve_moderation_item(
        session,
        parsed,
        action=body.action,
        reason=body.reason,
        user=user,
        request=request,
    )


# ---------------------------------------------------------------------------
# Civic initiatives (Phase 18)
# ---------------------------------------------------------------------------


@community_router.post(
    "/initiatives", status_code=201, summary="Propose a civic initiative (draft)"
)
async def create_initiative(
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="community_initiative",
        key=client_ip(request),
        limit=10,
        window_seconds=3600,
    )
    return await participation.create_initiative(session, actor=user, data=body, request=request)


@community_router.get("/initiatives", summary="List civic initiatives")
async def list_initiatives(
    session: DbSession,
    user: CurrentUser,
    status: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    geography_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await participation.list_initiatives(
        session,
        viewer=user,
        status=status,
        category_id=_parse_id(category_id, kind="category", error_kind="invalid_category_id")
        if category_id
        else None,
        geography_id=_parse_id(geography_id, kind="geography", error_kind="invalid_geography_id")
        if geography_id
        else None,
        limit=limit,
        offset=offset,
    )


@community_router.get("/initiatives/{initiative_id}", summary="Get a civic initiative")
async def get_initiative(
    initiative_id: str,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.get_initiative(session, parsed, viewer=user)


@community_router.patch(
    "/initiatives/{initiative_id}", summary="Edit an initiative draft (initiator only)"
)
async def update_initiative(
    initiative_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.update_initiative(
        session, initiative_id=parsed, actor=user, changes=body, request=request
    )


@community_router.post(
    "/initiatives/{initiative_id}/submit", summary="Submit an initiative for review"
)
async def submit_initiative(
    initiative_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.submit_initiative(
        session, initiative_id=parsed, actor=user, request=request
    )


@community_router.post(
    "/initiatives/{initiative_id}/review", summary="Approve or reject an initiative (moderators)"
)
async def review_initiative(
    initiative_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.review_initiative(
        session,
        initiative_id=parsed,
        reviewer=user,
        decision=str(body.get("decision") or ""),
        note=body.get("note"),
        request=request,
    )


@community_router.post("/initiatives/{initiative_id}/join", summary="Join an active initiative")
async def join_initiative(
    initiative_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.join_initiative(
        session, initiative_id=parsed, actor=user, request=request
    )


@community_router.post("/initiatives/{initiative_id}/leave", summary="Leave an initiative")
async def leave_initiative(
    initiative_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.leave_initiative(
        session, initiative_id=parsed, actor=user, request=request
    )


@community_router.get(
    "/initiatives/{initiative_id}/observations", summary="List initiative observations"
)
async def list_observations(
    initiative_id: str,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.list_observations(session, initiative_id=parsed, viewer=user)


@community_router.post(
    "/initiatives/{initiative_id}/observations",
    status_code=201,
    summary="Add an observation / evidence to an initiative (members)",
)
async def add_observation(
    initiative_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    media_id = (
        _parse_id(body["media_object_id"], kind="media", error_kind="invalid_media_object_id")
        if body.get("media_object_id")
        else None
    )
    return await participation.add_observation(
        session,
        initiative_id=parsed,
        actor=user,
        kind=str(body.get("kind") or "observation"),
        notes=body.get("notes"),
        media_object_id=media_id,
        request=request,
    )


@community_router.post(
    "/initiatives/{initiative_id}/observations/{observation_id}/review",
    summary="Accept or reject an observation (organizers/moderators)",
)
async def review_observation(
    initiative_id: str,
    observation_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    init_parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    obs_parsed = _parse_id(observation_id, kind="observation", error_kind="invalid_observation_id")
    return await participation.review_observation(
        session,
        initiative_id=init_parsed,
        observation_id=obs_parsed,
        reviewer=user,
        decision=str(body.get("decision") or ""),
        request=request,
    )


@community_router.post(
    "/initiatives/{initiative_id}/complete", summary="Complete an initiative (organizers)"
)
async def complete_initiative(
    initiative_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative", error_kind="invalid_initiative_id")
    return await participation.complete_initiative(
        session,
        initiative_id=parsed,
        actor=user,
        results=body.get("results"),
        request=request,
    )


# ---------------------------------------------------------------------------
# Volunteers (Phase 18)
# ---------------------------------------------------------------------------


@community_router.get("/volunteer/profile", summary="My volunteer profile (privacy-safe)")
async def my_volunteer_profile(user: ActiveUser, session: DbSession) -> dict[str, Any]:
    return await participation.get_volunteer_profile(session, user)


@community_router.put("/volunteer/profile", summary="Update my volunteer profile")
async def update_volunteer_profile(
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await participation.update_volunteer_profile(
        session, user=user, changes=body, request=request
    )


@community_router.get("/volunteer/opportunities", summary="List volunteer opportunities")
async def list_opportunities(
    session: DbSession,
    user: CurrentUser,
    status: str | None = Query(default=None),
    geography_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await participation.list_opportunities(
        session,
        viewer=user,
        status=status,
        geography_id=_parse_id(geography_id, kind="geography", error_kind="invalid_geography_id")
        if geography_id
        else None,
        limit=limit,
        offset=offset,
    )


@community_router.post(
    "/volunteer/opportunities", status_code=201, summary="Create a volunteer opportunity"
)
async def create_opportunity(
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="community_opportunity",
        key=client_ip(request),
        limit=10,
        window_seconds=3600,
    )
    return await participation.create_opportunity(session, actor=user, data=body, request=request)


@community_router.get(
    "/volunteer/opportunities/{opportunity_id}", summary="Get a volunteer opportunity"
)
async def get_opportunity(
    opportunity_id: str,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    parsed = _parse_id(opportunity_id, kind="opportunity", error_kind="invalid_opportunity_id")
    return await participation.get_opportunity(session, parsed, viewer=user)


@community_router.post(
    "/volunteer/opportunities/{opportunity_id}/join", summary="Join a volunteer opportunity"
)
async def join_opportunity(
    opportunity_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(opportunity_id, kind="opportunity", error_kind="invalid_opportunity_id")
    return await participation.join_opportunity(
        session, opportunity_id=parsed, actor=user, request=request
    )


@community_router.post(
    "/volunteer/opportunities/{opportunity_id}/withdraw",
    summary="Withdraw from a volunteer opportunity",
)
async def withdraw_opportunity(
    opportunity_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(opportunity_id, kind="opportunity", error_kind="invalid_opportunity_id")
    return await participation.withdraw_opportunity(
        session, opportunity_id=parsed, actor=user, request=request
    )


# ---------------------------------------------------------------------------
# Community groups (Phase 18)
# ---------------------------------------------------------------------------


@community_router.post("/groups", status_code=201, summary="Request a community group")
async def create_group(
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="community_group", key=client_ip(request), limit=5, window_seconds=3600
    )
    return await participation.create_group(session, actor=user, data=body, request=request)


@community_router.get("/groups", summary="List community groups")
async def list_groups(
    session: DbSession,
    user: CurrentUser,
    status: str | None = Query(default=None),
    geography_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await participation.list_groups(
        session,
        viewer=user,
        status=status,
        geography_id=_parse_id(geography_id, kind="geography", error_kind="invalid_geography_id")
        if geography_id
        else None,
        limit=limit,
        offset=offset,
    )


@community_router.get("/groups/{group_id}", summary="Get a community group")
async def get_group(
    group_id: str,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    parsed = _parse_id(group_id, kind="group", error_kind="invalid_group_id")
    return await participation.get_group(session, parsed, viewer=user)


@community_router.patch("/groups/{group_id}", summary="Edit a group (owner/moderators)")
async def update_group(
    group_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(group_id, kind="group", error_kind="invalid_group_id")
    return await participation.update_group(
        session, group_id=parsed, actor=user, changes=body, request=request
    )


@community_router.post(
    "/groups/{group_id}/review", summary="Approve or reject a group (moderators)"
)
async def review_group(
    group_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(group_id, kind="group", error_kind="invalid_group_id")
    return await participation.review_group(
        session,
        group_id=parsed,
        reviewer=user,
        decision=str(body.get("decision") or ""),
        note=body.get("note"),
        request=request,
    )


@community_router.post("/groups/{group_id}/join", summary="Join a community group")
async def join_group(
    group_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(group_id, kind="group", error_kind="invalid_group_id")
    return await participation.join_group(session, group_id=parsed, actor=user, request=request)


@community_router.post("/groups/{group_id}/leave", summary="Leave a community group")
async def leave_group(
    group_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(group_id, kind="group", error_kind="invalid_group_id")
    return await participation.leave_group(session, group_id=parsed, actor=user, request=request)


@community_router.post(
    "/groups/{group_id}/members/{target_user_id}",
    summary="Manage a group member (add/remove/ban/promote/demote)",
)
async def manage_group_member(
    group_id: str,
    target_user_id: str,
    body: dict[str, Any],
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    group_parsed = _parse_id(group_id, kind="group", error_kind="invalid_group_id")
    target_parsed = _parse_id(target_user_id, kind="user", error_kind="invalid_user_id")
    return await participation.manage_group_member(
        session,
        group_id=group_parsed,
        target_user_id=target_parsed,
        actor=user,
        action=str(body.get("action") or ""),
        request=request,
    )


# ---------------------------------------------------------------------------
# Badges (Phase 18)
# ---------------------------------------------------------------------------


@community_router.get("/badges", summary="List all badges with transparent criteria")
async def list_badges(session: DbSession) -> dict[str, Any]:
    return await participation.list_badges(session)


@community_router.get("/badges/me", summary="My badges and progress (deterministic criteria)")
async def my_badges(user: ActiveUser, session: DbSession) -> dict[str, Any]:
    return await participation.my_badges(session, user)
