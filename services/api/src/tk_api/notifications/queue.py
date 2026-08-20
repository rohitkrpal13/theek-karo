"""Template rendering + quiet-hours gate (API.md §9).

Templates live in ``notification_templates`` (hi/en); payload values are
interpolated as ``{field}``. Quiet hours (IST by default) suppress non-urgent
SMS/email sends — the worker re-queues them for after the window instead of
delivering late at night; in-app notifications are never delayed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from datetime import time as dtime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.notifications.models import NotificationPreference

STATUS_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "draft": "draft",
        "submitted": "submitted",
        "under_verification": "under verification",
        "verified": "verified",
        "assigned": "assigned",
        "in_progress": "in progress",
        "resolved": "resolved",
        "resolution_verified": "resolution verified",
        "closed": "closed",
        "rejected": "rejected",
        "reopened": "reopened",
        "duplicate_merged": "merged as duplicate",
        "under_review": "under review",
        "needs_information": "needs more information",
        "acknowledged": "acknowledged",
        "action_planned": "action planned",
        "waiting_for_information": "waiting for information",
        "resolution_submitted": "resolution submitted",
        "resolution_under_review": "resolution under review",
        "resolution_rejected": "resolution returned",
        "partially_resolved": "partially resolved",
        "duplicate": "duplicate",
    },
    "hi": {
        "draft": "ड्राफ्ट",
        "submitted": "प्रस्तुत",
        "under_verification": "सत्यापन में",
        "verified": "सत्यापित",
        "assigned": "सौंपा गया",
        "in_progress": "प्रगति में",
        "resolved": "समाधान हुआ",
        "resolution_verified": "समाधान सत्यापित",
        "closed": "बंद",
        "rejected": "अस्वीकृत",
        "reopened": "फिर खोला गया",
        "duplicate_merged": "डुप्लिकेट में विलय",
        "under_review": "समीक्षा में",
        "needs_information": "अधिक जानकारी चाहिए",
        "acknowledged": "स्वीकृत",
        "action_planned": "कार्य योजना बनी",
        "waiting_for_information": "जानकारी की प्रतीक्षा",
        "resolution_submitted": "समाधान प्रस्तुत",
        "resolution_under_review": "समाधान समीक्षा में",
        "resolution_rejected": "समाधान वापस किया गया",
        "partially_resolved": "आंशिक रूप से हल",
        "duplicate": "डुप्लिकेट",
    },
}


def render(template_body: str, payload: dict[str, Any], *, locale: str = "en") -> str:
    out = template_body
    for key, value in payload.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def render_with_status_label(template_body: str, payload: dict[str, Any], *, locale: str) -> str:
    """Inject the localized status label for status_change templates."""
    labels = STATUS_LABELS.get(locale, STATUS_LABELS["en"])
    if "status" in payload and "status_label" not in payload:
        payload = {
            **payload,
            "status_label": labels.get(str(payload["status"]), str(payload["status"])),
        }
    return render(template_body, payload, locale=locale)


def _parse_time(value: str) -> dtime:
    hour, minute = (int(part) for part in value.split(":"))
    return dtime(hour=hour, minute=minute)


def is_quiet_hour(
    now: datetime,
    *,
    quiet_hours: dict[str, Any] | None,
    default: dict[str, Any],
) -> bool:
    """True when ``now`` (UTC) falls inside the quiet window, wrapping midnight."""
    spec = quiet_hours or default
    tz = ZoneInfo(str(spec.get("tz", "Asia/Kolkata")))
    local = now.astimezone(tz).time()
    start = _parse_time(str(spec.get("start", "21:00")))
    end = _parse_time(str(spec.get("end", "07:00")))
    if start <= end:
        return start <= local < end
    return local >= start or local < end


def event_group_for(event: str) -> str:
    """Map an event to its preference group (API.md §9).

    Community events are groupable ("12 new comments"); security and system
    events are always delivered (their preference rows are locked).
    """
    if event.startswith("community."):
        return "community"
    if event.startswith("security."):
        return "security"
    if event.startswith("system."):
        return "system"
    mapping = {
        "report.status_change": "status_change",
        "report.comment": "collaboration",
        "report.verification": "collaboration",
        "ai.review": "ai",
        # Phase 15: community confirmation signals are community events;
        # reopening a case after follow-up is a case status change.
        "resolution.followup_confirmed": "community",
        "resolution.reopen_signal": "community",
        "resolution.reopen_approved": "status_change",
    }
    return mapping.get(event, "status_change")


def group_key_for(event: str, payload: dict[str, Any]) -> str | None:
    """Collapse key for grouped delivery (e.g. one entry per report's comments)."""
    if event in ("report.comment", "community.reply", "community.mention"):
        report_id = payload.get("report_id")
        return f"comment:{report_id}" if report_id else None
    if event == "community.reaction":
        report_id = payload.get("report_id")
        return f"reaction:{report_id}" if report_id else None
    if event == "community.follow":
        actor_id = payload.get("actor_id")
        return f"follow:{actor_id}" if actor_id else None
    return None


async def should_dispatch(
    session: AsyncSession,
    *,
    user_id: Any,
    channel: str,
    event: str,
    quiet_hours_default: dict[str, Any],
) -> bool:
    """Respect the preference toggle; SMS/email also respect quiet hours."""
    pref = await session.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.channel == channel,
            NotificationPreference.event_group == event_group_for(event),
        )
    )
    enabled = pref.enabled if pref is not None else True
    if not enabled:
        return False
    if channel == "in_app":
        return True
    return not is_quiet_hour(
        datetime.now(UTC),
        quiet_hours=pref.quiet_hours if pref else None,
        default=quiet_hours_default,
    )
