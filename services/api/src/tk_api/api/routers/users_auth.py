"""Auth and user management routers (API.md §3, SECURITY.md §2/§3/§4, PRD §14)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.api.deps import get_current_user, get_db, require_roles
from tk_api.api.schemas import (
    ChangePasswordRequest,
    ConsentRevokeRequest,
    ForgotPasswordRequest,
    LoginOtpRequest,
    LoginPasswordRequest,
    LogoutRequest,
    MfaCodeRequest,
    MfaVerifyRequest,
    OAuthCallbackRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    ResendEmailVerificationRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    RoleChangeRequest,
    VerifyEmailRequest,
    VerifyOtpRequest,
)
from tk_api.auth import service as auth_service
from tk_api.auth.authorization import ROLE_PERMISSIONS
from tk_api.auth.otp import OtpSender, OtpStore, issue_otp
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.users import service as users_service
from tk_api.users.models import Role, User

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])

admin_only = require_roles("admin", "super_admin")

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(admin_only)]


def _otp_store(request: Request) -> OtpStore:
    return cast(OtpStore, request.app.state.otp_store)


def _otp_sender(request: Request) -> OtpSender:
    return cast(OtpSender, request.app.state.otp_sender)


# -----------------------------------------------------------------------------
# Auth Endpoints
# -----------------------------------------------------------------------------


@auth_router.post("/register", status_code=201, summary="Register a citizen account")
async def register(
    body: RegisterRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"register:{client_ip(request)}", limit=10, window_seconds=60
    )
    await rate_limit(
        request, bucket="auth", key=f"register:{body.contact}", limit=5, window_seconds=300
    )
    otp_store = getattr(request.app.state, "otp_store", None)
    otp_sender = getattr(request.app.state, "otp_sender", None)
    return await auth_service.register(
        session,
        request.app.state.settings,
        otp_store,
        otp_sender,
        email_sender=getattr(request.app.state, "email_provider", None),
        contact=body.contact,
        display_name=body.display_name,
        password=body.password,
        username=body.username,
        consent=body.consent,
        terms_version=body.terms_version,
        locale=body.locale,
        location_pref=body.location_pref,
        request=request,
    )


@auth_router.post("/verify-email", summary="Verify email address via token")
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="auth",
        key=f"verify-email:{client_ip(request)}",
        limit=20,
        window_seconds=300,
    )
    return await auth_service.verify_email(
        session,
        request.app.state.settings,
        token=body.token,
        request=request,
    )


@auth_router.post("/resend-verification", summary="Resend email verification token")
async def resend_verification(
    body: ResendEmailVerificationRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="auth",
        key=f"resend-email:{body.email}",
        limit=3,
        window_seconds=300,
    )
    return await auth_service.resend_email_verification(
        session,
        request.app.state.settings,
        email_sender=getattr(request.app.state, "email_provider", None),
        email=body.email,
        request=request,
    )


@auth_router.post("/verify-otp", summary="Verify OTP and receive tokens")
async def verify_otp(
    body: VerifyOtpRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"otp:{body.contact}", limit=10, window_seconds=300
    )
    return await auth_service.verify_otp_and_activate(
        session,
        request.app.state.settings,
        _otp_store(request),
        contact=body.contact,
        code=body.code,
        request=request,
    )


@auth_router.post("/resend-otp", summary="Resend verification OTP")
async def resend_otp(
    body: ResendOtpRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    settings = request.app.state.settings
    await rate_limit(
        request,
        bucket="auth",
        key=f"resend:{body.contact}",
        limit=1,
        window_seconds=max(settings.otp_resend_cooldown_seconds, 1),
    )
    is_phone = body.contact.isdigit() or body.contact.startswith("+")
    normalized = (
        auth_service.normalize_phone(body.contact)
        if is_phone
        else auth_service.normalize_email(body.contact)
    )
    await issue_otp(
        _otp_store(request), _otp_sender(request), settings, normalized, purpose="resend"
    )
    return {"status": "verify_pending", "contact_masked": auth_service.mask_contact(normalized)}


@auth_router.post("/login", summary="Login with email/username/phone and password")
async def login(
    body: LoginPasswordRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"login:{client_ip(request)}", limit=15, window_seconds=60
    )
    await rate_limit(
        request, bucket="auth", key=f"login:{body.contact}", limit=10, window_seconds=300
    )
    return await auth_service.login_password(
        session,
        request.app.state.settings,
        contact=body.contact,
        password=body.password,
        request=request,
    )


# -----------------------------------------------------------------------------
# MFA (TOTP) Endpoints
# -----------------------------------------------------------------------------


@auth_router.get("/mfa/status", summary="MFA status for the current user")
async def mfa_status(
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await auth_service.mfa_status(session, user=user, settings=request.app.state.settings)


@auth_router.post("/mfa/setup", summary="Start TOTP setup (returns secret once)")
async def mfa_setup(
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"mfa-setup:{user.id}", limit=5, window_seconds=300
    )
    return await auth_service.setup_mfa(session, user=user, request=request)


@auth_router.post("/mfa/enable", summary="Enable TOTP after verifying a code")
async def mfa_enable(
    body: MfaCodeRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await auth_service.enable_mfa(session, user=user, code=body.code, request=request)


@auth_router.post("/mfa/disable", summary="Disable TOTP (requires a valid code)")
async def mfa_disable(
    body: MfaCodeRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await auth_service.disable_mfa(session, user=user, code=body.code, request=request)


@auth_router.post("/mfa/verify", summary="Exchange MFA challenge + TOTP code for tokens")
async def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"mfa-verify:{client_ip(request)}", limit=20, window_seconds=60
    )
    return await auth_service.verify_mfa_challenge(
        session,
        request.app.state.settings,
        challenge_token=body.challenge_token,
        code=body.code,
        request=request,
    )


@auth_router.post("/login-otp", summary="Request login OTP")
async def login_otp(
    body: LoginOtpRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"login-otp:{body.contact}", limit=5, window_seconds=300
    )
    return await auth_service.send_login_otp(
        session,
        request.app.state.settings,
        _otp_store(request),
        _otp_sender(request),
        contact=body.contact,
        request=request,
    )


@auth_router.post("/forgot-password", summary="Request password reset link")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"forgot-pw:{client_ip(request)}", limit=5, window_seconds=300
    )
    return await auth_service.forgot_password(
        session,
        request.app.state.settings,
        email=body.email,
        request=request,
    )


@auth_router.post("/reset-password", summary="Execute password reset with token")
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"reset-pw:{client_ip(request)}", limit=5, window_seconds=300
    )
    return await auth_service.reset_password(
        session,
        request.app.state.settings,
        token=body.token,
        new_password=body.new_password,
        request=request,
    )


@auth_router.post("/change-password", summary="Change password for current authenticated user")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"change-pw:{user.id}", limit=5, window_seconds=300
    )
    return await auth_service.change_password(
        session,
        request.app.state.settings,
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
        revoke_other_sessions=body.revoke_other_sessions,
        request=request,
    )


@auth_router.post("/refresh", summary="Rotate refresh token, issue new pair")
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"refresh:{client_ip(request)}", limit=20, window_seconds=60
    )
    return await auth_service.refresh(
        session,
        request.app.state.settings,
        refresh_token=body.refresh_token,
        request=request,
    )


@auth_router.post("/logout", summary="Logout: revoke current refresh-token family and session")
async def logout(
    body: LogoutRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    await auth_service.logout(
        session, refresh_token=body.refresh_token, actor=user, request=request
    )
    return {"status": "logged_out"}


@auth_router.post("/logout-all", summary="Logout from all devices / sessions")
async def logout_all(
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    await auth_service.logout_all(session, actor=user, request=request)
    return {"status": "logged_out_all"}


@auth_router.get("/me", summary="Authenticated user session overview")
async def auth_me(
    user: CurrentUser,
) -> dict[str, Any]:
    return auth_service.user_summary(user)


@auth_router.get("/sessions", summary="List active sessions for current user")
async def list_user_sessions(
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    items = await auth_service.list_sessions(session, user=user)
    return {"items": items}


@auth_router.delete("/sessions/{session_id}", summary="Revoke a specific active session")
async def revoke_user_session(
    session_id: str,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    try:
        sess_uuid = uuid.UUID(session_id)
    except ValueError as exc:
        raise ApiError("invalid session id", 422, "invalid_session_id") from exc
    await auth_service.revoke_session(session, session_id=sess_uuid, user=user, request=request)
    return {"status": "session_revoked"}


@auth_router.get("/oauth/google/url", summary="Get Google OAuth authorization URL")
async def get_google_auth_url(
    redirect_uri: str,
    state: str | None = None,
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, str]:
    return auth_service.google_auth_url(
        request.app.state.settings, redirect_uri=redirect_uri, state=state
    )


@auth_router.post("/oauth/google/callback", summary="Exchange Google OAuth code for tokens")
async def google_oauth_callback(
    body: OAuthCallbackRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="auth", key=f"oauth:{client_ip(request)}", limit=10, window_seconds=60
    )
    return await auth_service.google_callback(
        session,
        request.app.state.settings,
        code=body.code,
        state=body.state,
        redirect_uri=body.redirect_uri,
        request=request,
    )


# -----------------------------------------------------------------------------
# User Profile Endpoints
# -----------------------------------------------------------------------------


@users_router.get("/me", summary="Own profile")
async def me(
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await users_service.get_profile(session, user)


@users_router.patch("/me", summary="Update own profile")
async def patch_me(
    body: ProfileUpdateRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await users_service.update_profile(
        session,
        user,
        display_name=body.display_name,
        username=body.username,
        bio=body.bio,
        profile_image_url=body.profile_image_url,
        location_pref=body.location_pref,
        locale=body.locale,
        request=request,
    )


@users_router.delete("/me", summary="Delete/anonymize own account per DPDP privacy guidelines")
async def delete_me(
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await auth_service.delete_account(session, user=user, request=request)


@users_router.post("/me/consents/revoke", summary="Revoke a consent purpose")
async def revoke_consent(
    body: ConsentRevokeRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    return await users_service.revoke_consent(session, user, purpose=body.purpose, request=request)


@users_router.get("/me/audit", summary="Own audit trail")
async def own_audit(
    user: CurrentUser,
    session: DbSession,
    limit: int = 50,
) -> dict[str, Any]:
    return {"items": await users_service.own_audit_log(session, user, limit=limit)}


def _parse_user_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError("invalid user id", 422, "invalid_user_id") from exc


@users_router.get(
    "/roles",
    summary="List available roles and permissions (admin)",
    dependencies=[Depends(admin_only)],
)
async def list_roles_and_permissions(
    session: DbSession,
) -> dict[str, Any]:
    roles = (await session.execute(select(Role).order_by(Role.code))).scalars().all()
    return {
        "roles": [
            {
                "id": str(r.id),
                "code": r.code,
                "name": r.name,
                "permissions": list(ROLE_PERMISSIONS.get(r.code, set())),
            }
            for r in roles
        ]
    }


@users_router.post(
    "/{user_id}/roles", summary="Grant role (admin)", dependencies=[Depends(admin_only)]
)
async def grant_role(
    user_id: str,
    body: RoleChangeRequest,
    request: Request,
    actor: AdminUser,
    session: DbSession,
) -> dict[str, Any]:
    return await users_service.grant_role(
        session,
        target_user_id=_parse_user_id(user_id),
        role_code=body.role,
        actor=actor,
        request=request,
    )


@users_router.delete(
    "/{user_id}/roles/{role}", summary="Revoke role (admin)", dependencies=[Depends(admin_only)]
)
async def revoke_role(
    user_id: str,
    role: str,
    request: Request,
    actor: AdminUser,
    session: DbSession,
) -> dict[str, Any]:
    return await users_service.revoke_role(
        session,
        target_user_id=_parse_user_id(user_id),
        role_code=role,
        actor=actor,
        request=request,
    )
