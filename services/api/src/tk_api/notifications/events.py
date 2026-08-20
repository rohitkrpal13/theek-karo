"""Cross-module event hooks that enqueue notifications (API.md §9).

Every call runs inside the action's own transaction (same session, like
``audit``), so a notification is only ever queued when the action commits.
In-app rows are written immediately; SMS/email flow through the worker queue +
preferences + quiet hours.

Phase 13: locale-aware rendering (per-recipient ``locale``), groupable
community events (``group_key`` collapses into "12 new comments"), and
mention/reply/reaction/follow hooks.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.notifications import service as notifications_service
from tk_api.notifications.queue import group_key_for
from tk_api.reports.models import Report, ReportComment, ReportFollower
from tk_api.users.models import User

CHANNELS_ALL = ["in_app", "sms", "email"]


def _followers_of(session: AsyncSession, report_id: uuid.UUID) -> Any:
    return select(ReportFollower.user_id).where(ReportFollower.report_id == report_id)


async def _recipient_locales(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = (await session.execute(select(User.id, User.locale).where(User.id.in_(user_ids)))).all()
    return {row.id: row.locale or "hi" for row in rows}


async def _actor_display_name(session: AsyncSession, actor_id: uuid.UUID) -> str:
    name = await session.scalar(select(User.display_name).where(User.id == actor_id))
    return str(name or "Someone")


async def enqueue_report_event(
    session: AsyncSession,
    *,
    report: Report,
    event: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID,
    channels: list[str] = CHANNELS_ALL,
) -> None:
    """Queue for the reporter + followers (event payload carries ticket_no)."""
    follower_ids = (await session.execute(_followers_of(session, report.id))).scalars().all()
    targets = {report.reporter_id, *follower_ids} - {actor_id}
    locales = await _recipient_locales(session, list(targets))
    group_key = group_key_for(event, payload)
    for user_id in targets:
        await notifications_service.enqueue(
            session,
            user_id=user_id,
            event=event,
            locale=locales.get(user_id, "hi"),
            payload=payload,
            channels=channels,
            group_key=group_key,
        )


async def enqueue_for_users(
    session: AsyncSession,
    *,
    user_ids: list[uuid.UUID],
    event: str,
    payload: dict[str, Any],
    channels: list[str] = CHANNELS_ALL,
) -> None:
    locales = await _recipient_locales(session, user_ids)
    for user_id in user_ids:
        await notifications_service.enqueue(
            session,
            user_id=user_id,
            event=event,
            locale=locales.get(user_id, "hi"),
            payload=payload,
            channels=channels,
        )


async def _enqueue_with_group(
    session: AsyncSession,
    *,
    user_ids: list[uuid.UUID],
    event: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID,
    channels: list[str] = CHANNELS_ALL,
) -> None:
    locales = await _recipient_locales(session, user_ids)
    group_key = group_key_for(event, payload)
    for user_id in user_ids:
        await notifications_service.enqueue(
            session,
            user_id=user_id,
            event=event,
            locale=locales.get(user_id, "hi"),
            payload=payload,
            channels=channels,
            group_key=group_key,
        )
    await session.flush()


async def queue_status_change(
    session: AsyncSession, *, report: Report, actor_id: uuid.UUID, to_status: str
) -> None:
    await enqueue_report_event(
        session,
        report=report,
        event="report.status_change",
        payload={"ticket_no": report.ticket_no, "status": to_status},
        actor_id=actor_id,
    )


async def queue_verification(session: AsyncSession, *, report: Report, actor_id: uuid.UUID) -> None:
    await enqueue_report_event(
        session,
        report=report,
        event="report.verification",
        payload={"ticket_no": report.ticket_no},
        actor_id=actor_id,
    )


async def queue_comment(session: AsyncSession, *, report: Report, actor_id: uuid.UUID) -> None:
    """Notify reporter + followers of a new comment (grouped per report)."""
    await enqueue_report_event(
        session,
        report=report,
        event="report.comment",
        payload={
            "ticket_no": report.ticket_no,
            "report_id": str(report.id),
            "actor_name": await _actor_display_name(session, actor_id),
        },
        actor_id=actor_id,
    )


async def queue_reply(
    session: AsyncSession,
    *,
    report: Report,
    parent: ReportComment,
    actor_id: uuid.UUID,
) -> None:
    """Notify the parent comment's author about a reply."""
    if parent.author_id == actor_id:
        return
    await _enqueue_with_group(
        session,
        user_ids=[parent.author_id],
        event="community.reply",
        payload={
            "ticket_no": report.ticket_no,
            "report_id": str(report.id),
            "actor_name": await _actor_display_name(session, actor_id),
        },
        actor_id=actor_id,
    )


async def queue_mention(
    session: AsyncSession,
    *,
    report: Report,
    mentionee_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
) -> None:
    targets = [uid for uid in set(mentionee_ids) if uid != actor_id]
    if not targets:
        return
    await _enqueue_with_group(
        session,
        user_ids=targets,
        event="community.mention",
        payload={
            "ticket_no": report.ticket_no,
            "report_id": str(report.id),
            "actor_name": await _actor_display_name(session, actor_id),
        },
        actor_id=actor_id,
    )


async def queue_reaction(
    session: AsyncSession, *, report: Report, actor_id: uuid.UUID, kind: str
) -> None:
    """Notify the reporter + followers about a reaction (grouped per report)."""
    follower_ids = (await session.execute(_followers_of(session, report.id))).scalars().all()
    targets = {report.reporter_id, *follower_ids} - {actor_id}
    if not targets:
        return
    await _enqueue_with_group(
        session,
        user_ids=list(targets),
        event="community.reaction",
        payload={
            "ticket_no": report.ticket_no,
            "report_id": str(report.id),
            "actor_name": await _actor_display_name(session, actor_id),
            "kind": kind,
        },
        actor_id=actor_id,
    )


async def queue_follow(
    session: AsyncSession, *, following_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    if following_id == actor_id:
        return
    await _enqueue_with_group(
        session,
        user_ids=[following_id],
        event="community.follow",
        payload={
            "actor_id": str(actor_id),
            "actor_name": await _actor_display_name(session, actor_id),
        },
        actor_id=actor_id,
    )


async def queue_moderation_notice(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    event: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID,
) -> None:
    """Notify a content author when a moderator action is taken (event
    ``community.moderation.*``; never silenced, always in_app + sms + email)."""
    if user_id == actor_id:
        return
    locale = await session.scalar(select(User.locale).where(User.id == user_id))
    await notifications_service.enqueue(
        session,
        user_id=user_id,
        event=event,
        locale=str(locale or "hi"),
        payload=payload,
        channels=CHANNELS_ALL,
    )
    await session.flush()


async def queue_ai_review_admin(
    session: AsyncSession, *, report: Report, actor_id: uuid.UUID
) -> None:
    from tk_api.users.models import Role, UserRole

    admin_ids = (
        (
            await session.execute(
                select(User.id)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.code == "admin", User.status == "active")
            )
        )
        .scalars()
        .all()
    )
    if admin_ids:
        await enqueue_for_users(
            session,
            user_ids=[uid for uid in admin_ids if uid != actor_id],
            event="ai.review",
            payload={"ticket_no": report.ticket_no},
        )
