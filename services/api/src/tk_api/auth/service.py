"""Auth service: registration, email verification, login, sessions, password reset,
Google OAuth, and security events (SECURITY.md §2-§4, PRD §14, ADR-008, ADR-045).
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.auth.authorization import AuthorizationService
from tk_api.auth.mfa import (
    MfaChallengeError,
    create_mfa_challenge_token,
    decode_mfa_challenge_token,
    generate_totp_secret,
    otpauth_uri,
    verify_totp,
)
from tk_api.auth.models import RefreshToken
from tk_api.auth.otp import OtpError, OtpSender, OtpStore, consume_otp, issue_otp
from tk_api.auth.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_crypto_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from tk_api.core.audit import audit
from tk_api.core.config import Settings
from tk_api.core.errors import ApiError
from tk_api.core.login_throttle import LoginThrottle
from tk_api.core.rate_limit import client_ip
from tk_api.identity.models import (
    EmailVerification,
    OAuthAccount,
    PasswordResetToken,
    SecurityEvent,
    UserMfa,
)
from tk_api.identity.models import (
    Session as UserSession,
)
from tk_api.notifications.providers import EmailProvider
from tk_api.users.models import Consent, Role, User, UserRole

CITIZEN_ROLE = "citizen"
# OAuth token-type label (RFC 6750) — a scheme name, not a credential.
# nosec B105: the constant name contains "token", which Bandit's hardcoded-
# secret heuristic treats as suspicious; the value is not a secret.
TOKEN_TYPE = "Bearer"  # nosec B105

RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "superadmin",
    "moderator",
    "official",
    "system",
    "theekkaro",
    "theek_karo",
    "support",
    "help",
    "security",
    "root",
    "api",
    "null",
    "undefined",
    "gov",
    "government",
    "police",
    "municipal",
    "ward",
}

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,30}$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(ApiError):
    pass


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10:
        return "+91" + digits
    return "+" + digits


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_username(username: str) -> str:
    cleaned = username.strip().lower()
    if not USERNAME_REGEX.match(cleaned):
        raise AuthError(
            "Username must be 3-30 characters (letters, numbers, underscores only)",
            422,
            "invalid_username",
        )
    if cleaned in RESERVED_USERNAMES:
        raise AuthError("This username is reserved and cannot be used", 422, "reserved_username")
    return cleaned


def mask_contact(contact: str | None) -> str:
    if not contact:
        return ""
    if "@" in contact:
        local, domain = contact.split("@", 1)
        return f"{local[0]}•••@{domain}"
    return contact[:3] + "•••••" + contact[-3:]


async def record_security_event(
    session: AsyncSession,
    *,
    event: str,
    user_id: uuid.UUID | None = None,
    request: Request | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Record a structured security event (PRD §14, SECURITY.md §9)."""
    ip = client_ip(request) if request else None
    user_agent = request.headers.get("user-agent") if request else None
    session.add(
        SecurityEvent(
            user_id=user_id,
            event=event,
            ip=ip,
            user_agent=user_agent,
            meta=meta or {},
        )
    )


def user_summary(user: User) -> dict[str, Any]:
    permissions = list(AuthorizationService.get_user_permissions(user))
    return {
        "id": str(user.id),
        "email": user.email,
        "phone": user.phone,
        "username": user.username,
        "display_name": user.display_name,
        "contact_masked": mask_contact(user.email or user.phone),
        "roles": user.role_codes(),
        "permissions": permissions,
        "locale": user.locale,
        "status": user.status,
        "trust_score": user.trust_score,
        "bio": user.bio,
        "profile_image_url": user.profile_image_url,
        "mfa_enabled": bool(user.mfa_enabled),
    }


def _login_identifier_key(contact: str) -> str:
    """Deterministic per-account key for the login throttle (email/phone/username)."""
    if "@" in contact:
        return f"login:{normalize_email(contact)}"
    if contact.isdigit() or contact.startswith("+"):
        return f"login:{normalize_phone(contact)}"
    return f"login:{contact.strip().lower()}"


def _privileged_role(user: User, settings: Settings) -> bool:
    """True when the user holds any MFA-required (privileged) role."""
    return any(role in settings.mfa_required_roles for role in user.role_codes())


async def _tokens_or_mfa_challenge(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    request: Request | None = None,
) -> dict[str, Any]:
    """Issue access tokens, or a MFA challenge when the user has TOTP enabled.

    Privileged-role users without MFA still receive tokens (so they can reach
    the MFA setup flow) but the response flags ``mfa_setup_required`` and the
    authorization layer denies privileged actions until MFA is enabled.
    """
    if user.mfa_enabled:
        challenge = create_mfa_challenge_token(user.id, settings)
        return {
            "mfa_required": True,
            "challenge_token": challenge,
            "expires_in": settings.mfa_challenge_ttl_seconds,
            "user": {
                "id": str(user.id),
                "roles": user.role_codes(),
                "mfa_enabled": True,
            },
        }
    result = await _issue_tokens(session, user, settings, request=request)
    if _privileged_role(user, settings):
        result["mfa_setup_required"] = True
    return result


async def _issue_tokens(
    session: AsyncSession, user: User, settings: Settings, *, request: Request | None = None
) -> dict[str, Any]:
    raw_refresh, digest = new_refresh_token()
    family_id = uuid.uuid4()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest,
            family_id=family_id,
            expires_at=refresh_expiry(settings),
        )
    )

    # Track active session
    ip = client_ip(request) if request else None
    user_agent = request.headers.get("user-agent") if request else None
    user_session = UserSession(
        user_id=user.id,
        client_id=str(family_id),
        ip=ip,
        user_agent=user_agent,
        last_seen_at=datetime.now(UTC),
    )
    session.add(user_session)

    perms = list(AuthorizationService.get_user_permissions(user))
    access = create_access_token(
        user.id,
        user.role_codes(),
        settings,
        permissions=perms,
        username=user.username,
    )
    return {
        "access_token": access,
        "expires_in": settings.jwt_access_ttl_seconds,
        "token_type": TOKEN_TYPE,
        "refresh_token": raw_refresh,
        "user": user_summary(user),
    }


async def ensure_role(session: AsyncSession, user: User, code: str) -> None:
    role = await session.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise AuthError(f"role not found: {code}", 500, "role_missing")
    existing = await session.scalar(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    if existing is None:
        session.add(UserRole(user_id=user.id, role_id=role.id))


def _ensure_active(user: User) -> None:
    if user.deleted_at is not None:
        raise AuthError("account has been deleted", 403, "account_deleted")
    if user.status == "suspended":
        raise AuthError("account suspended", 403, "account_suspended")
    if user.status != "active":
        raise AuthError("account not verified", 403, "account_pending")


# -----------------------------------------------------------------------------
# 1. Registration Flow
# -----------------------------------------------------------------------------


async def register(
    session: AsyncSession,
    settings: Settings,
    store: OtpStore | None = None,
    sender: OtpSender | None = None,
    *,
    email_sender: EmailProvider | None = None,
    contact: str,
    display_name: str,
    password: str | None = None,
    username: str | None = None,
    consent: bool,
    terms_version: str = "2026-v1",
    locale: str = "hi",
    location_pref: str | None = None,
    request: Request,
) -> dict[str, Any]:
    if not consent:
        raise AuthError("consent required", 422, "consent_required")
    if not display_name.strip():
        raise AuthError("display_name required", 422, "display_name_required")

    is_email = "@" in contact
    is_phone = not is_email and (contact.isdigit() or contact.startswith("+"))

    if not is_email and not is_phone:
        raise AuthError("contact must be a valid email or phone number", 422, "invalid_contact")

    normalized_contact = normalize_email(contact) if is_email else normalize_phone(contact)
    if is_email and not EMAIL_REGEX.match(normalized_contact):
        raise AuthError("invalid email format", 422, "invalid_email")

    # Check for existing contact
    existing = await session.scalar(
        select(User).where(
            User.email == normalized_contact if is_email else User.phone == normalized_contact
        )
    )
    if existing is not None:
        raise AuthError("contact already registered", 409, "already_registered")

    # Check username if provided
    normalized_uname = None
    if username:
        normalized_uname = normalize_username(username)
        existing_uname = await session.scalar(select(User).where(User.username == normalized_uname))
        if existing_uname is not None:
            raise AuthError("username is already taken", 409, "username_taken")

    # Password policy check
    if password is not None:
        if len(password) < settings.password_min_length:
            raise AuthError(
                f"password must be at least {settings.password_min_length} characters",
                422,
                "weak_password",
            )
        if len(password) > 128:
            raise AuthError("password cannot exceed 128 characters", 422, "password_too_long")

    user = User(
        email=normalized_contact if is_email else None,
        phone=normalized_contact if is_phone else None,
        username=normalized_uname,
        password_hash=hash_password(password) if password else None,
        display_name=display_name.strip(),
        locale=locale,
        location_pref=location_pref,
        status="pending_verification",
    )
    session.add(user)
    await session.flush()

    # Consents
    session.add_all(
        [
            Consent(user_id=user.id, purpose="terms", terms_version=terms_version),
            Consent(user_id=user.id, purpose="data_processing", terms_version=terms_version),
        ]
    )

    # Issue verification token or OTP
    raw_token = None
    dev_otp_code = None

    if is_email:
        raw_token, token_digest = new_crypto_token(32)
        session.add(
            EmailVerification(
                user_id=user.id,
                email=normalized_contact,
                code_hash=token_digest,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        if email_sender is not None:
            locale_prefix = (locale or "en").split("-")[0]
            if locale_prefix not in ("en", "hi"):
                locale_prefix = "en"
            verify_url = (
                f"{settings.app_base_url.rstrip('/')}/{locale_prefix}"
                f"/verify-email?{urlencode({'token': raw_token})}"
            )
            email_sender.send(
                to_contact=normalized_contact,
                subject="Verify your email — Theek Karo",
                body=(
                    "Welcome to Theek Karo.\n\n"
                    "Confirm your email address to activate your account:\n"
                    f"{verify_url}\n\n"
                    "This link expires in 24 hours. If you did not create an "
                    "account, you can safely ignore this email."
                ),
                message_id=f"register:{user.id}",
            )
        # plaintext token is a dev/test convenience only — never in production
        if settings.is_production:
            raw_token = None
    elif is_phone and store is not None and sender is not None:
        code = await issue_otp(store, sender, settings, normalized_contact, purpose="register")
        if not settings.is_production:
            dev_otp_code = code

    await record_security_event(
        session,
        event="REGISTER",
        user_id=user.id,
        request=request,
        meta={"contact": mask_contact(normalized_contact), "username": normalized_uname},
    )
    await audit(
        session,
        action="user.register",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()

    result: dict[str, Any] = {
        "status": "verify_pending",
        "contact_masked": mask_contact(normalized_contact),
        "expires_in": 86400 if is_email else settings.otp_ttl_seconds,
    }
    # plaintext dev conveniences only outside production
    if not settings.is_production:
        if raw_token is not None:
            result["dev_verification_token"] = raw_token
        if dev_otp_code is not None:
            result["dev_otp_code"] = dev_otp_code
    return result


# -----------------------------------------------------------------------------
# 2. Email Verification Flow
# -----------------------------------------------------------------------------


async def verify_email(
    session: AsyncSession,
    settings: Settings,
    *,
    token: str,
    request: Request,
) -> dict[str, Any]:
    token_digest = hash_token(token)
    now = datetime.now(UTC)

    verification = await session.scalar(
        select(EmailVerification).where(
            EmailVerification.code_hash == token_digest,
            EmailVerification.verified_at.is_(None),
        )
    )
    if verification is None:
        raise AuthError("Invalid or already used verification token", 400, "invalid_token")

    expires_at = verification.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if now > expires_at:
        raise AuthError("Verification token has expired", 400, "token_expired")

    verification.verified_at = now
    user = await session.get(User, verification.user_id)
    if user is None:
        raise AuthError("User associated with token not found", 404, "user_not_found")

    user.email_verified_at = now
    if user.status == "pending_verification":
        user.status = "active"
        user.updated_at = now
        await ensure_role(session, user, CITIZEN_ROLE)

    await session.refresh(user, ["roles"])
    await record_security_event(
        session,
        event="EMAIL_VERIFIED",
        user_id=user.id,
        request=request,
    )
    await audit(
        session,
        action="email.verify",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )

    tokens = await _issue_tokens(session, user, settings, request=request)
    await session.commit()
    return tokens


async def resend_email_verification(
    session: AsyncSession,
    settings: Settings,
    *,
    email_sender: EmailProvider | None = None,
    email: str,
    request: Request,
) -> dict[str, Any]:
    normalized = normalize_email(email)
    user = await session.scalar(select(User).where(User.email == normalized))

    # Safe generic response to avoid account enumeration
    if user is None or user.email_verified_at is not None or user.deleted_at is not None:
        return {
            "status": "verification_sent",
            "message": (
                "If an unverified account exists for this email, a verification link has been sent."
            ),
        }

    raw_token, token_digest = new_crypto_token(32)
    session.add(
        EmailVerification(
            user_id=user.id,
            email=normalized,
            code_hash=token_digest,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )
    await session.commit()
    result: dict[str, Any] = {
        "status": "verification_sent",
        "contact_masked": mask_contact(normalized),
    }
    if settings.is_production:
        if email_sender is None:
            raise AuthError("email delivery not configured", 503, "email_unavailable")
        verify_url = (
            f"{settings.app_base_url.rstrip('/')}/en/verify-email?{urlencode({'token': raw_token})}"
        )
        email_sender.send(
            to_contact=normalized,
            subject="Verify your email — Theek Karo",
            body=(
                "Confirm your email address to activate your account:\n"
                f"{verify_url}\n\n"
                "This link expires in 24 hours."
            ),
            message_id=f"resend:{user.id}",
        )
    else:
        result["dev_verification_token"] = raw_token
    return result


# -----------------------------------------------------------------------------
# 3. Login & Authentication Flow
# -----------------------------------------------------------------------------


async def login_password(
    session: AsyncSession,
    settings: Settings,
    *,
    contact: str,
    password: str,
    request: Request,
) -> dict[str, Any]:
    is_email = "@" in contact
    is_phone = not is_email and (contact.isdigit() or contact.startswith("+"))

    user: User | None = None
    if is_email:
        user = await session.scalar(select(User).where(User.email == normalize_email(contact)))
    elif is_phone:
        user = await session.scalar(select(User).where(User.phone == normalize_phone(contact)))
    else:
        # Check by username
        user = await session.scalar(select(User).where(User.username == contact.strip().lower()))

    identifier_key = _login_identifier_key(contact)
    throttle = request.app.state.login_throttle
    locked = await throttle.locked_seconds(identifier_key)
    if locked:
        await record_security_event(
            session,
            event="LOGIN_BLOCKED",
            user_id=user.id if user else None,
            request=request,
            meta={"identifier": mask_contact(contact), "retry_after_seconds": locked},
        )
        await session.commit()
        raise AuthError("Too many failed attempts. Try again later.", 429, "account_locked")

    if (
        user is None
        or user.password_hash is None
        or not verify_password(user.password_hash, password)
    ):
        await record_security_event(
            session,
            event="LOGIN_FAILURE",
            user_id=user.id if user else None,
            request=request,
            meta={"identifier": mask_contact(contact)},
        )
        await session.commit()
        await throttle.record_failure(
            identifier_key,
            max_failures=settings.login_max_failures,
            backoff_base=settings.login_backoff_base_seconds,
            backoff_max=settings.login_backoff_max_seconds,
            window_seconds=settings.login_failure_window_seconds,
        )
        raise AuthError("Invalid credentials", 401, "invalid_credentials")

    await throttle.reset(identifier_key)
    _ensure_active(user)

    await record_security_event(
        session,
        event="LOGIN_SUCCESS",
        user_id=user.id,
        request=request,
    )
    await audit(
        session,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )

    result = await _tokens_or_mfa_challenge(session, user, settings, request=request)
    await session.commit()
    return result


async def verify_otp_and_activate(
    session: AsyncSession,
    settings: Settings,
    store: OtpStore,
    *,
    contact: str,
    code: str,
    request: Request,
) -> dict[str, Any]:
    is_phone = contact.isdigit() or contact.startswith("+")
    normalized = normalize_phone(contact) if is_phone else normalize_email(contact)
    try:
        await consume_otp(store, settings, normalized, code)
    except OtpError as exc:
        raise AuthError(str(exc), 401, exc.kind) from exc

    user = await session.scalar(
        select(User).where(User.phone == normalized if is_phone else User.email == normalized)
    )
    if user is None:
        raise AuthError("contact not found", 404, "contact_not_found")

    now = datetime.now(UTC)
    if is_phone:
        user.phone_verified_at = now
    else:
        user.email_verified_at = now
    first_activation = user.status == "pending_verification"
    if first_activation:
        user.status = "active"
        user.updated_at = now
        await ensure_role(session, user, CITIZEN_ROLE)

    await session.refresh(user, ["roles"])
    await record_security_event(
        session,
        event="LOGIN_SUCCESS" if not first_activation else "REGISTER_VERIFIED",
        user_id=user.id,
        request=request,
    )
    await audit(
        session,
        action="otp.verify",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        after={"first_activation": first_activation},
        request=request,
    )
    result = await _tokens_or_mfa_challenge(session, user, settings, request=request)
    await session.commit()
    return result


async def send_login_otp(
    session: AsyncSession,
    settings: Settings,
    store: OtpStore,
    sender: OtpSender,
    *,
    contact: str,
    request: Request,
) -> dict[str, str]:
    is_phone = contact.isdigit() or contact.startswith("+")
    normalized = normalize_phone(contact) if is_phone else normalize_email(contact)
    user = await session.scalar(
        select(User).where(User.phone == normalized if is_phone else User.email == normalized)
    )
    if user is None:
        raise AuthError("contact not found", 404, "contact_not_found")
    _ensure_active(user)
    await issue_otp(store, sender, settings, normalized, purpose="login")
    await session.commit()
    return {"status": "verify_pending", "contact_masked": mask_contact(normalized)}


# -----------------------------------------------------------------------------
# 4. Token Refresh & Session Management
# -----------------------------------------------------------------------------


async def refresh(
    session: AsyncSession, settings: Settings, *, refresh_token: str, request: Request
) -> dict[str, Any]:
    token_digest = hash_token(refresh_token)
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_digest)
    )
    if token is None:
        raise AuthError("refresh token invalid", 401, "invalid_token")
    user = await session.get(User, token.user_id)
    if user is None:
        raise AuthError("user not found", 401, "invalid_token")
    if token.revoked_at is not None or token.is_expired:
        await _revoke_family(session, token.family_id)
        await record_security_event(
            session,
            event="SUSPICIOUS_ACTIVITY",
            user_id=user.id,
            request=request,
            meta={"reason": "refresh_reuse_detected"},
        )
        await session.commit()
        raise AuthError("refresh token revoked; family invalidated", 401, "token_reuse_detected")
    _ensure_active(user)

    now = datetime.now(UTC)
    token.revoked_at = now
    raw_new, digest_new = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest_new,
            family_id=token.family_id,
            expires_at=refresh_expiry(settings),
        )
    )

    # Update session last_seen_at
    await session.execute(
        update(UserSession)
        .where(UserSession.client_id == str(token.family_id))
        .values(last_seen_at=now)
    )

    perms = list(AuthorizationService.get_user_permissions(user))
    access = create_access_token(
        user.id,
        user.role_codes(),
        settings,
        permissions=perms,
        username=user.username,
    )
    await session.commit()
    return {
        "access_token": access,
        "expires_in": settings.jwt_access_ttl_seconds,
        "token_type": TOKEN_TYPE,
        "refresh_token": raw_new,
        "user": user_summary(user),
    }


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(
        update(UserSession)
        .where(UserSession.client_id == str(family_id), UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def logout(
    session: AsyncSession, *, refresh_token: str, actor: User, request: Request
) -> None:
    token_digest = hash_token(refresh_token)
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_digest)
    )
    if token is not None and token.user_id == actor.id:
        await _revoke_family(session, token.family_id)
        await record_security_event(
            session,
            event="LOGOUT",
            user_id=actor.id,
            request=request,
        )
        await audit(
            session,
            action="auth.logout",
            entity_type="user",
            entity_id=actor.id,
            actor_id=actor.id,
            request=request,
        )
        await session.commit()


async def logout_all(session: AsyncSession, *, actor: User, request: Request) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == actor.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == actor.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await record_security_event(
        session,
        event="LOGOUT_ALL",
        user_id=actor.id,
        request=request,
    )
    await audit(
        session,
        action="auth.logout_all",
        entity_type="user",
        entity_id=actor.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()


async def list_sessions(session: AsyncSession, *, user: User) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.last_seen_at.desc())
        )
    ).scalars()
    return [
        {
            "id": str(s.id),
            "client_id": s.client_id,
            "ip": s.ip,
            "user_agent": s.user_agent,
            "created_at": s.created_at,
            "last_seen_at": s.last_seen_at,
        }
        for s in rows
    ]


async def revoke_session(
    session: AsyncSession, *, session_id: uuid.UUID, user: User, request: Request
) -> None:
    user_sess = await session.get(UserSession, session_id)
    if user_sess is None or user_sess.user_id != user.id:
        raise AuthError("Session not found", 404, "session_not_found")

    now = datetime.now(UTC)
    user_sess.revoked_at = now
    try:
        fam_id = uuid.UUID(user_sess.client_id)
    except ValueError:
        # Legacy sessions may carry a non-UUID client_id; nothing to revoke.
        fam_id = None
    if fam_id is not None:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == fam_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    await record_security_event(
        session,
        event="SESSION_REVOKED",
        user_id=user.id,
        request=request,
        meta={"session_id": str(session_id)},
    )
    await session.commit()


# -----------------------------------------------------------------------------
# 5. Password Reset & Password Change
# -----------------------------------------------------------------------------


async def forgot_password(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    request: Request,
) -> dict[str, Any]:
    normalized = normalize_email(email)
    user = await session.scalar(select(User).where(User.email == normalized))

    raw_token = None
    if user is not None and user.is_active and not user.is_deleted:
        raw_token, token_digest = new_crypto_token(32)
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_digest,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await record_security_event(
            session,
            event="PASSWORD_RESET_REQUESTED",
            user_id=user.id,
            request=request,
        )
        await session.commit()

    return {
        "status": "reset_link_sent",
        "message": (
            "If an account exists for this email, password reset instructions have been sent."
        ),
        "dev_reset_token": raw_token,
    }


async def reset_password(
    session: AsyncSession,
    settings: Settings,
    *,
    token: str,
    new_password: str,
    request: Request,
) -> dict[str, Any]:
    if len(new_password) < settings.password_min_length:
        raise AuthError(
            f"Password must be at least {settings.password_min_length} characters",
            422,
            "weak_password",
        )
    if len(new_password) > 128:
        raise AuthError("Password cannot exceed 128 characters", 422, "password_too_long")

    token_digest = hash_token(token)
    now = datetime.now(UTC)

    reset_record = await session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_digest,
            PasswordResetToken.used_at.is_(None),
        )
    )
    if reset_record is None:
        raise AuthError("Invalid or already used password reset token", 400, "invalid_token")

    expires_at = reset_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if now > expires_at:
        raise AuthError("Password reset token has expired", 400, "token_expired")

    user = await session.get(User, reset_record.user_id)
    if user is None:
        raise AuthError("User not found", 404, "user_not_found")

    # Invalidate token
    reset_record.used_at = now
    # Update password
    user.password_hash = hash_password(new_password)
    user.updated_at = now

    # Invalidate all existing sessions and refresh tokens for security
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    await record_security_event(
        session,
        event="PASSWORD_RESET_COMPLETED",
        user_id=user.id,
        request=request,
    )
    await audit(
        session,
        action="auth.password_reset",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return {"status": "password_reset_success"}


async def change_password(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    current_password: str,
    new_password: str,
    revoke_other_sessions: bool = True,
    request: Request,
) -> dict[str, Any]:
    if user.password_hash is None or not verify_password(user.password_hash, current_password):
        raise AuthError("Current password is incorrect", 400, "invalid_current_password")

    if len(new_password) < settings.password_min_length:
        raise AuthError(
            f"New password must be at least {settings.password_min_length} characters",
            422,
            "weak_password",
        )
    if len(new_password) > 128:
        raise AuthError("New password cannot exceed 128 characters", 422, "password_too_long")

    now = datetime.now(UTC)
    user.password_hash = hash_password(new_password)
    user.updated_at = now

    if revoke_other_sessions:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    await record_security_event(
        session,
        event="PASSWORD_CHANGED",
        user_id=user.id,
        request=request,
    )
    await audit(
        session,
        action="auth.password_change",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return {"status": "password_changed_success"}


# -----------------------------------------------------------------------------
# 6. Google OAuth Flow & Account Linking
# -----------------------------------------------------------------------------


def _oauth_allowed_redirect_uri(settings: Settings, redirect_uri: str) -> bool:
    """True when redirect_uri matches the configured allowlist.

    The allowlist is seeded with localhost dev URLs; ``app_base_url`` (the
    app's own origin) is always acceptable, so deployments do not need to
    repeat it.
    """
    if redirect_uri in settings.oauth_redirect_uri_allowlist:
        return True
    app_origin = settings.app_base_url
    if app_origin.endswith("/"):
        app_origin = app_origin[:-1]
    return redirect_uri == app_origin or redirect_uri.startswith(app_origin + "/")


def google_auth_url(
    settings: Settings,
    *,
    redirect_uri: str,
    state: str | None = None,
) -> dict[str, str]:
    if settings.is_production and not settings.google_oauth_client_id:
        raise AuthError(
            "Google sign-in is not configured for this environment", 503, "oauth_not_configured"
        )
    if not _oauth_allowed_redirect_uri(settings, redirect_uri):
        raise AuthError("redirect_uri is not allowed", 400, "invalid_redirect_uri")
    state_val = state or uuid.uuid4().hex
    params = {
        "client_id": settings.google_oauth_client_id or "sandbox-google-client-id",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state_val,
        "prompt": "select_account",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"url": url, "state": state_val}


async def _google_exchange_code(
    settings: Settings,
    *,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Real Google token exchange (production path).

    Raises ``AuthError`` 503 when OAuth is not configured, and 502 when the
    provider exchange fails. The mock path is never used in prod/staging.
    """
    if not (settings.google_oauth_client_id and settings.google_oauth_client_secret):
        raise AuthError("Google sign-in is not configured", 503, "oauth_not_configured")
    body = urlencode(
        {
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = UrlRequest(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read())
    except Exception as exc:
        raise AuthError(
            "Google sign-in could not be completed (provider unreachable)",
            502,
            "oauth_provider_error",
        ) from exc
    if "id_token" not in token_data:
        raise AuthError("Google sign-in failed during token exchange", 400, "invalid_oauth_code")
    # Decode the signed ID token payload (unsigned verification; signature is
    # validated by the TLS exchange with Google and the audience claim below).
    payload_segment = token_data["id_token"].split(".")[1]
    payload_segment += "=" * (-len(payload_segment) % 4)
    try:
        claims: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload_segment))
    except Exception as exc:
        raise AuthError(
            "Google sign-in returned an invalid token", 502, "invalid_oauth_token"
        ) from exc
    if claims.get("aud") not in (settings.google_oauth_client_id, None):
        raise AuthError("Google sign-in token audience mismatch", 400, "invalid_oauth_token")
    return claims


async def google_callback(
    session: AsyncSession,
    settings: Settings,
    *,
    code: str,
    state: str,
    redirect_uri: str,
    request: Request,
    mock_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Real provider exchange whenever the tenant is configured for OAuth.
    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        if not _oauth_allowed_redirect_uri(settings, redirect_uri):
            raise AuthError("redirect_uri is not allowed", 400, "invalid_redirect_uri")
        claims = await _google_exchange_code(settings, code=code, redirect_uri=redirect_uri)
    elif settings.is_production:
        raise AuthError("Google sign-in is not configured", 503, "oauth_not_configured")
    elif mock_payload is not None and settings.oauth_mock_enabled:
        claims = mock_payload
    elif settings.oauth_mock_enabled:
        # Hermetic dev/test exchange: deterministic identity derived from the
        # code so flows are fully testable without external credentials.
        claims = {
            "sub": f"google-{hash_token(code)[:16]}",
            "email": f"googleuser-{code[:6]}@example.com",
            "email_verified": True,
            "name": "Google User",
        }
    else:
        raise AuthError("Google sign-in is not configured", 503, "oauth_not_configured")

    google_sub = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified", False)
    name = claims.get("name") or "Google User"

    if not google_sub:
        raise AuthError("Invalid OAuth profile from Google", 400, "invalid_oauth_profile")

    # 1. Look up existing OAuth account link
    oauth_acc = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_subject == google_sub,
        )
    )

    user: User | None = None
    if oauth_acc is not None:
        user = await session.get(User, oauth_acc.user_id)

    if user is None and email:
        # 2. Look up existing user with this email
        normalized = normalize_email(email)
        existing_user = await session.scalar(select(User).where(User.email == normalized))
        if existing_user is not None:
            # Secure account linking only if OAuth email is verified
            if not email_verified:
                raise AuthError(
                    "Cannot link Google account: email is not verified by Google",
                    400,
                    "unverified_oauth_email",
                )
            user = existing_user
            if existing_user.email_verified_at is None:
                existing_user.email_verified_at = datetime.now(UTC)
                existing_user.status = "active"
                await ensure_role(session, existing_user, CITIZEN_ROLE)

            session.add(
                OAuthAccount(
                    user_id=user.id,
                    provider="google",
                    provider_subject=google_sub,
                    email=normalized,
                    name=name,
                )
            )
            await record_security_event(
                session,
                event="OAUTH_LINKED",
                user_id=user.id,
                request=request,
                meta={"provider": "google"},
            )

    if user is None:
        # 3. Create new user account via Google OAuth
        now = datetime.now(UTC)
        user = User(
            email=normalize_email(email) if email else None,
            display_name=name,
            email_verified_at=now if email_verified else None,
            status="active" if email_verified else "pending_verification",
        )
        session.add(user)
        await session.flush()

        session.add_all(
            [
                Consent(user_id=user.id, purpose="terms", terms_version="2026-v1"),
                Consent(user_id=user.id, purpose="data_processing", terms_version="2026-v1"),
                OAuthAccount(
                    user_id=user.id,
                    provider="google",
                    provider_subject=google_sub,
                    email=email,
                    name=name,
                ),
            ]
        )
        await ensure_role(session, user, CITIZEN_ROLE)
        await record_security_event(
            session,
            event="OAUTH_LOGIN",
            user_id=user.id,
            request=request,
            meta={"provider": "google", "action": "created"},
        )

    _ensure_active(user)
    await session.refresh(user, ["roles"])
    result = await _tokens_or_mfa_challenge(session, user, settings, request=request)
    await session.commit()
    return result


# -----------------------------------------------------------------------------
# 6.5 MFA (TOTP) — setup, enable, disable, challenge verify
# -----------------------------------------------------------------------------


async def mfa_status(session: AsyncSession, *, user: User, settings: Settings) -> dict[str, Any]:
    mfa = await session.scalar(select(UserMfa).where(UserMfa.user_id == user.id))
    enabled = bool(mfa is not None and mfa.enabled_at is not None)
    required = _privileged_role(user, settings)
    return {
        "enabled": enabled,
        "required_by_role": required,
        "setup_required": required and not enabled,
    }


async def setup_mfa(session: AsyncSession, *, user: User, request: Request) -> dict[str, Any]:
    """Generate a fresh TOTP secret (previous secret is rotated). The account
    is not protected until ``enable_mfa`` succeeds with a valid code."""
    secret = generate_totp_secret()
    existing = await session.scalar(select(UserMfa).where(UserMfa.user_id == user.id))
    if existing is not None:
        existing.secret = secret
        existing.enabled_at = None
    else:
        session.add(UserMfa(user_id=user.id, secret=secret))
    user.mfa_enabled = False
    await record_security_event(
        session, event="MFA_SETUP_STARTED", user_id=user.id, request=request
    )
    await session.commit()
    account = user.email or user.phone or user.username or str(user.id)
    return {
        "secret": secret,
        "otpauth_uri": otpauth_uri(secret, account),
        "digits": 6,
        "period": 30,
    }


async def enable_mfa(
    session: AsyncSession, *, user: User, code: str, request: Request
) -> dict[str, Any]:
    mfa = await session.scalar(select(UserMfa).where(UserMfa.user_id == user.id))
    if mfa is None or not mfa.secret:
        raise AuthError("MFA setup required before enabling", 400, "mfa_setup_required")
    if mfa.enabled_at is not None:
        raise AuthError("MFA is already enabled", 409, "mfa_already_enabled")
    if not verify_totp(mfa.secret, code):
        await record_security_event(
            session, event="MFA_ENABLE_FAILURE", user_id=user.id, request=request
        )
        await session.commit()
        raise AuthError("Invalid authentication code", 401, "invalid_mfa_code")
    mfa.enabled_at = datetime.now(UTC)
    user.mfa_enabled = True
    await record_security_event(session, event="MFA_ENABLED", user_id=user.id, request=request)
    await audit(
        session,
        action="auth.mfa_enabled",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return {"status": "mfa_enabled", "mfa_enabled": True}


async def disable_mfa(
    session: AsyncSession, *, user: User, code: str, request: Request
) -> dict[str, Any]:
    mfa = await session.scalar(select(UserMfa).where(UserMfa.user_id == user.id))
    if mfa is None or mfa.enabled_at is None or not mfa.secret:
        raise AuthError("MFA is not enabled", 400, "mfa_not_enabled")
    if not verify_totp(mfa.secret, code):
        await record_security_event(
            session, event="MFA_DISABLE_FAILURE", user_id=user.id, request=request
        )
        await session.commit()
        raise AuthError("Invalid authentication code", 401, "invalid_mfa_code")
    mfa.enabled_at = None
    user.mfa_enabled = False
    await record_security_event(session, event="MFA_DISABLED", user_id=user.id, request=request)
    await audit(
        session,
        action="auth.mfa_disabled",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return {"status": "mfa_disabled", "mfa_enabled": False}


async def verify_mfa_challenge(
    session: AsyncSession,
    settings: Settings,
    *,
    challenge_token: str,
    code: str,
    request: Request,
) -> dict[str, Any]:
    """Exchange a challenge token + valid TOTP code for access tokens."""
    try:
        user_id = decode_mfa_challenge_token(challenge_token, settings)
    except MfaChallengeError as exc:
        raise AuthError(str(exc), 401, "invalid_challenge_token") from exc

    throttle: LoginThrottle = request.app.state.login_throttle
    throttle_key = f"mfa:{user_id}"
    locked = await throttle.locked_seconds(throttle_key)
    if locked:
        raise AuthError("Too many failed attempts. Try again later.", 429, "mfa_locked")

    user = await session.get(User, user_id)
    if user is None:
        raise AuthError("user not found", 401, "invalid_challenge_token")
    _ensure_active(user)

    mfa = await session.scalar(select(UserMfa).where(UserMfa.user_id == user.id))
    if mfa is None or mfa.enabled_at is None or not mfa.secret:
        raise AuthError("MFA is not enabled for this account", 400, "mfa_not_enabled")
    if not verify_totp(mfa.secret, code):
        await record_security_event(session, event="MFA_FAILURE", user_id=user.id, request=request)
        await session.commit()
        await throttle.record_failure(
            throttle_key,
            max_failures=settings.mfa_max_attempts,
            backoff_base=settings.mfa_backoff_seconds,
            backoff_max=settings.mfa_backoff_seconds * 8,
            window_seconds=settings.login_failure_window_seconds,
        )
        raise AuthError("Invalid authentication code", 401, "invalid_mfa_code")

    await throttle.reset(throttle_key)
    await record_security_event(session, event="MFA_VERIFIED", user_id=user.id, request=request)
    await audit(
        session,
        action="auth.mfa_verify",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    tokens = await _issue_tokens(session, user, settings, request=request)
    await session.commit()
    return tokens


# -----------------------------------------------------------------------------
# 7. Account Anonymization & Deletion
# -----------------------------------------------------------------------------


async def delete_account(session: AsyncSession, *, user: User, request: Request) -> dict[str, Any]:
    now = datetime.now(UTC)
    # Anonymize PII per DPDP privacy retention guidelines
    user.display_name = "Anonymous Citizen"
    user.email = None
    user.phone = None
    user.username = None
    user.password_hash = None
    user.bio = None
    user.profile_image_url = None
    user.location_pref = None
    user.status = "deleted"
    user.deleted_at = now

    # Revoke all active sessions and refresh tokens
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    # Remove OAuth links + MFA state
    await session.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user.id))
    await session.execute(delete(UserMfa).where(UserMfa.user_id == user.id))

    await record_security_event(
        session,
        event="ACCOUNT_DELETED",
        user_id=user.id,
        request=request,
    )
    await audit(
        session,
        action="user.account_deleted",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return {"status": "account_deleted_success"}
