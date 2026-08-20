"""Retention purge for time-limited PII (docs/PII-DATA-INVENTORY.md).

The platform keeps civic content (reports, evidence, comments) indefinitely as
public-interest data, but time-limited PII — tokens, sessions, verification
codes, security events — is purged after a documented retention window. This
module is the single enforcement point; the worker schedules it daily and the
unit tests exercise it against the app engine.

Deletion is a hard DELETE (these rows are auxiliary and never referenced by
civic content). Anonymized account tombstones (``users.status = 'deleted'``)
are *not* hard-deleted: reports/comments reference ``users.id`` with mixed
CASCADE/RESTRICT FKs, so the anonymized row is retained as a permanent tombstone
for referential integrity (PII already removed at deletion time).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# Retention windows (days) — keep in sync with docs/PII-DATA-INVENTORY.md.
REFRESH_TOKEN_RETENTION_DAYS = 90
SESSION_RETENTION_DAYS = 180
EMAIL_VERIFICATION_RETENTION_DAYS = 30
PASSWORD_RESET_RETENTION_DAYS = 30
SECURITY_EVENT_RETENTION_DAYS = 365
AI_CONVERSATION_RETENTION_DAYS = 90
PUBLIC_API_USAGE_RETENTION_DAYS = 365

# Audit logs are write-once (COMPLIANCE-DPDP.md §7) and are deliberately never
# purged by this job.


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def purge_expired_pii(
    session: AsyncSession, *, now: datetime | None = None
) -> dict[str, int]:
    """Delete PII-bearing rows past their retention window. Returns row counts."""
    now = now or _utcnow()
    counts: dict[str, int] = {}

    def _count(result: Any) -> int:
        return int(getattr(result, "rowcount", 0) or 0)

    from tk_api.auth.models import RefreshToken
    from tk_api.identity.models import (
        EmailVerification,
        PasswordResetToken,
        SecurityEvent,
    )
    from tk_api.identity.models import (
        Session as UserSession,
    )

    # Refresh tokens: expired or revoked for more than the retention window.
    cutoff = now - timedelta(days=REFRESH_TOKEN_RETENTION_DAYS)
    result = await session.execute(
        delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < cutoff,
                and_(
                    RefreshToken.revoked_at.is_not(None),
                    RefreshToken.revoked_at < cutoff,
                ),
            )
        )
    )
    counts["refresh_tokens"] = _count(result)

    # Sessions: revoked past retention, or stale (no activity) past retention.
    cutoff = now - timedelta(days=SESSION_RETENTION_DAYS)
    result = await session.execute(
        delete(UserSession).where(
            or_(
                and_(
                    UserSession.revoked_at.is_not(None),
                    UserSession.revoked_at < cutoff,
                ),
                and_(
                    UserSession.revoked_at.is_(None),
                    func.coalesce(UserSession.last_seen_at, UserSession.created_at) < cutoff,
                ),
            )
        )
    )
    counts["sessions"] = _count(result)

    # Email verification rows: past their expiry + retention.
    cutoff = now - timedelta(days=EMAIL_VERIFICATION_RETENTION_DAYS)
    result = await session.execute(
        delete(EmailVerification).where(EmailVerification.expires_at < cutoff)
    )
    counts["email_verifications"] = _count(result)

    # Password reset tokens: past their expiry + retention.
    cutoff = now - timedelta(days=PASSWORD_RESET_RETENTION_DAYS)
    result = await session.execute(
        delete(PasswordResetToken).where(PasswordResetToken.expires_at < cutoff)
    )
    counts["password_reset_tokens"] = _count(result)

    # Security events (login attempts, MFA events, account changes): kept long
    # enough for forensic review, purged after the window.
    cutoff = now - timedelta(days=SECURITY_EVENT_RETENTION_DAYS)
    result = await session.execute(delete(SecurityEvent).where(SecurityEvent.created_at < cutoff))
    counts["security_events"] = _count(result)

    # AI conversations (and their messages, cascaded): user prompts can contain
    # personal context; 90-day retention per COMPLIANCE-DPDP.md.
    from tk_api.ai.models import AiConversation, AiMessage

    cutoff = now - timedelta(days=AI_CONVERSATION_RETENTION_DAYS)
    stale = select(AiConversation.id).where(AiConversation.updated_at < cutoff)
    await session.execute(delete(AiMessage).where(AiMessage.conversation_id.in_(stale)))
    result = await session.execute(delete(AiConversation).where(AiConversation.updated_at < cutoff))
    counts["ai_conversations"] = _count(result)

    # Public API usage logs (key/endpoint/ip): usage accounting, 365 days.
    from tk_api.publicdata.models import PublicApiUsage

    cutoff = now - timedelta(days=PUBLIC_API_USAGE_RETENTION_DAYS)
    result = await session.execute(delete(PublicApiUsage).where(PublicApiUsage.created_at < cutoff))
    counts["public_api_usage"] = _count(result)

    await session.commit()
    return counts
