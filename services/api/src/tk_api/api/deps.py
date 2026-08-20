"""FastAPI dependencies: DB session, current user, RBAC."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Any

import jwt as pyjwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.auth.security import decode_access_token
from tk_api.core.db import create_session_factory
from tk_api.core.errors import ApiError
from tk_api.users.models import User


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = create_session_factory(request.app.state.engine)
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


class AuthError(ApiError):
    pass


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("missing bearer token", 401, "unauthenticated")
    return token.strip()


async def get_current_user(
    request: Request,
    session: DbSession,
) -> User:
    settings = request.app.state.settings
    try:
        payload = decode_access_token(_bearer_token(request), settings)
    except pyjwt.ExpiredSignatureError as exc:
        raise AuthError("token expired", 401, "token_expired") from exc
    except pyjwt.InvalidTokenError as exc:
        raise AuthError("invalid token", 401, "unauthenticated") from exc
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthError("invalid token", 401, "unauthenticated") from exc
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AuthError("user not found", 401, "unauthenticated")
    if user.status not in ("active", "pending_verification"):
        raise AuthError("account suspended", 403, "account_suspended")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(request: Request, session: DbSession) -> User | None:
    """Current user when a bearer token is sent, None for anonymous callers.

    A present-but-invalid token is still rejected (no silent fallback).
    """
    if not request.headers.get("authorization"):
        return None
    return await get_current_user(request, session)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: str) -> Callable[..., Any]:
    async def dependency(user: CurrentUser) -> User:
        # imported lazily to avoid a cycle (authorization.py imports CurrentUser)
        from tk_api.auth.authorization import mfa_gate_denies_any

        if not any(user.has_role(role) for role in roles):
            raise AuthError("insufficient permissions", 403, "forbidden")
        # privileged-role users must have MFA enabled before using role-gated
        # endpoints (Phase 16 enforcement; off unless configured)
        if mfa_gate_denies_any(user):
            raise AuthError(
                "multi-factor authentication is required for this action", 403, "mfa_required"
            )
        return user

    return dependency


def require_active(*roles: str) -> Callable[..., Any]:
    async def dependency(user: CurrentUser) -> User:
        from tk_api.auth.authorization import mfa_gate_denies_any

        if user.status != "active":
            raise AuthError("account not verified", 403, "account_pending")
        if roles and not any(user.has_role(role) for role in roles):
            raise AuthError("insufficient permissions", 403, "forbidden")
        if mfa_gate_denies_any(user):
            raise AuthError(
                "multi-factor authentication is required for this action", 403, "mfa_required"
            )
        return user

    return dependency
