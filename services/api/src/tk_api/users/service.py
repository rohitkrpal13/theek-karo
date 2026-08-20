"""User profile, roles, and consent operations (RBAC per SECURITY.md §3, PRD §14)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.auth.authorization import AuthorizationService
from tk_api.core.audit import AuditLog, audit
from tk_api.core.errors import ApiError
from tk_api.users.models import Consent, Role, User, UserRole

VALID_ROLES = {
    "citizen",
    "volunteer",
    "verified_contributor",
    "moderator",
    "institution_representative",
    "department_representative",
    "analyst",
    "admin",
    "super_admin",
    "official",  # Legacy compatibility alias
}


class UserError(ApiError):
    pass


def _summary(user: User, consents: list[Consent]) -> dict[str, Any]:
    permissions = list(AuthorizationService.get_user_permissions(user))
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "phone_masked": _mask(user.phone),
        "email_masked": _mask(user.email),
        "phone_verified": user.phone_verified_at is not None,
        "email_verified": user.email_verified_at is not None,
        "bio": user.bio,
        "profile_image_url": user.profile_image_url,
        "location_pref": user.location_pref,
        "locale": user.locale,
        "roles": user.role_codes(),
        "permissions": permissions,
        "status": user.status,
        "trust_score": user.trust_score,
        "consents": [
            {
                "purpose": c.purpose,
                "terms_version": c.terms_version,
                "granted_at": c.granted_at,
                "revoked_at": c.revoked_at,
            }
            for c in consents
        ],
        "created_at": user.created_at,
    }


def _mask(value: str | None) -> str | None:
    if value is None:
        return None
    if "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[0]}•••@{domain}"
    return value[:3] + "•••••" + value[-3:]


async def get_profile(session: AsyncSession, user: User) -> dict[str, Any]:
    consents = list(
        (await session.execute(select(Consent).where(Consent.user_id == user.id))).scalars()
    )
    return _summary(user, consents)


async def update_profile(
    session: AsyncSession,
    user: User,
    *,
    display_name: str | None = None,
    username: str | None = None,
    bio: str | None = None,
    profile_image_url: str | None = None,
    location_pref: str | None = None,
    locale: str | None = None,
    request: Request,
) -> dict[str, Any]:
    before = {
        "display_name": user.display_name,
        "username": user.username,
        "bio": user.bio,
        "profile_image_url": user.profile_image_url,
        "location_pref": user.location_pref,
        "locale": user.locale,
    }
    if display_name is not None:
        if not display_name.strip():
            raise UserError("display_name cannot be empty", 422, "invalid_display_name")
        user.display_name = display_name.strip()

    if username is not None:
        from tk_api.auth.service import normalize_username

        clean_username = normalize_username(username)
        if clean_username != user.username:
            existing = await session.scalar(select(User).where(User.username == clean_username))
            if existing is not None and existing.id != user.id:
                raise UserError("username is already taken", 409, "username_taken")
            user.username = clean_username

    if bio is not None:
        user.bio = bio.strip() if bio else None

    if profile_image_url is not None:
        user.profile_image_url = profile_image_url.strip() if profile_image_url else None

    if location_pref is not None:
        user.location_pref = location_pref.strip() if location_pref else None

    if locale is not None:
        if len(locale) != 2 or not locale.isalpha():
            raise UserError("locale must be a 2-letter code", 422, "invalid_locale")
        user.locale = locale.lower()

    user.updated_at = datetime.now(UTC)
    await audit(
        session,
        action="user.profile_update",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        before=before,
        after={
            "display_name": user.display_name,
            "username": user.username,
            "bio": user.bio,
            "profile_image_url": user.profile_image_url,
            "location_pref": user.location_pref,
            "locale": user.locale,
        },
        request=request,
    )
    await session.commit()
    return await get_profile(session, user)


async def grant_role(
    session: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    role_code: str,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    if role_code not in VALID_ROLES:
        raise UserError(f"invalid role: {role_code}", 422, "invalid_role")
    target = await session.get(User, target_user_id)
    if target is None:
        raise UserError("user not found", 404, "user_not_found")
    role = await session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise UserError(f"role not seeded: {role_code}", 500, "role_missing")
    if not target.has_role(role_code):
        session.add(UserRole(user_id=target.id, role_id=role.id, granted_by=actor.id))
    await session.refresh(target, ["roles"])
    await audit(
        session,
        action="user.role_grant",
        entity_type="user",
        entity_id=target.id,
        actor_id=actor.id,
        before={"roles": [r for r in target.role_codes() if r != role_code]},
        after={"roles": target.role_codes()},
        request=request,
    )
    await session.commit()
    return {"roles": target.role_codes()}


async def revoke_role(
    session: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    role_code: str,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    if role_code not in VALID_ROLES:
        raise UserError(f"invalid role: {role_code}", 422, "invalid_role")
    target = await session.get(User, target_user_id)
    if target is None:
        raise UserError("user not found", 404, "user_not_found")
    if actor.id == target.id and role_code in ("admin", "super_admin"):
        raise UserError("cannot revoke own admin role", 409, "self_admin_revocation")
    from sqlalchemy import delete

    await session.execute(
        delete(UserRole).where(
            UserRole.user_id == target.id,
            UserRole.role_id.in_(select(Role.id).where(Role.code == role_code)),
        )
    )
    await session.refresh(target, ["roles"])
    await audit(
        session,
        action="user.role_revoke",
        entity_type="user",
        entity_id=target.id,
        actor_id=actor.id,
        before={"roles": [*target.role_codes(), role_code]},
        after={"roles": target.role_codes()},
        request=request,
    )
    await session.commit()
    return {"roles": target.role_codes()}


async def revoke_consent(
    session: AsyncSession, user: User, *, purpose: str, request: Request
) -> dict[str, Any]:
    consent = await session.scalar(
        select(Consent).where(
            Consent.user_id == user.id,
            Consent.purpose == purpose,
            Consent.revoked_at.is_(None),
        )
    )
    if consent is None:
        raise UserError("no active consent for purpose", 404, "consent_not_found")
    consent.revoked_at = datetime.now(UTC)
    await audit(
        session,
        action="consent.revoke",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        after={"purpose": purpose, "revoked_at": consent.revoked_at},
        request=request,
    )
    await session.commit()
    return await get_profile(session, user)


async def own_audit_log(
    session: AsyncSession, user: User, *, limit: int = 50
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    rows = (
        await session.execute(
            select(AuditLog)
            .where(AuditLog.actor_id == user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": str(row.entity_id) if row.entity_id else None,
            "created_at": row.created_at,
            "ip": row.ip,
        }
        for row in rows
    ]
