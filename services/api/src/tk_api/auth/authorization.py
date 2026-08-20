"""Fine-grained RBAC & resource-level authorization service (SECURITY.md §3, PRD §14).

Enforces:
1. User -> Roles -> Permissions mapping.
2. Resource-level access policies (e.g., report ownership, institution scoping).
3. Centralized `AuthorizationService.can()` and `.require()` checks.
4. FastAPI dependency helpers (`require_permission`, `require_any_permission`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tk_api.api.deps import CurrentUser
from tk_api.core.errors import ApiError
from tk_api.users.models import User

# ---------------------------------------------------------------------------
# MFA gate (Phase 16): privileged roles must have TOTP enabled before they can
# exercise non-bootstrap permissions. Configured at app startup from Settings
# (``mfa_enforce_privileged`` + ``mfa_required_roles``); enforced in
# prod/staging. The bootstrap allowlist keeps a privileged user able to reach
# their own profile/audit + the MFA setup endpoints while MFA is pending.
# ---------------------------------------------------------------------------
_MFA_ENFORCEMENT_ENABLED = False
_MFA_REQUIRED_ROLES: frozenset[str] = frozenset()
_MFA_BOOTSTRAP_PERMISSIONS = frozenset(
    {
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
    }
)


def configure_mfa_enforcement(enabled: bool, required_roles: set[str]) -> None:
    """Set the module-level MFA gate configuration (called from create_app)."""
    global _MFA_ENFORCEMENT_ENABLED, _MFA_REQUIRED_ROLES
    _MFA_ENFORCEMENT_ENABLED = enabled
    _MFA_REQUIRED_ROLES = frozenset(required_roles)


def mfa_gate_denies(user: User, permission: str) -> bool:
    """True when a privileged-role user without MFA tries a non-bootstrap action."""
    if not _MFA_ENFORCEMENT_ENABLED:
        return False
    if getattr(user, "mfa_enabled", False):
        return False
    if not any(role in _MFA_REQUIRED_ROLES for role in user.role_codes()):
        return False
    return permission not in _MFA_BOOTSTRAP_PERMISSIONS


def mfa_gate_denies_any(user: User) -> bool:
    """True when a privileged-role user has no MFA enabled (role-gated endpoints)."""
    if not _MFA_ENFORCEMENT_ENABLED:
        return False
    if getattr(user, "mfa_enabled", False):
        return False
    return any(role in _MFA_REQUIRED_ROLES for role in user.role_codes())


def _raise_mfa_required() -> None:
    raise AuthorizationError(
        detail="multi-factor authentication is required for this action",
        code="mfa_required",
    )


# Standard Role-to-Permission mapping registry
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "citizen": {
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
        "reports.create",
        "reports.read_public",
        "reports.update_own",
        "reports.delete_own",
        "reports.verify",
        "institutions.read",
        "comments.create",
        "resolution.verify",
        "government_data.read",
        "analytics.read",
        "ai.use",
        "departments.read",
        "cases.read",
        "cases.reopen.request",
        "sla.read",
    },
    "volunteer": {
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
        "reports.create",
        "reports.read_public",
        "reports.update_own",
        "reports.delete_own",
        "reports.verify",
        "reports.transition",
        "institutions.read",
        "comments.create",
        "resolution.verify",
        "government_data.read",
        "analytics.read",
        "ai.use",
        "departments.read",
        "cases.read",
    },
    "verified_contributor": {
        "identity.read_self",
        "identity.update_self",
        "identity.delete_self",
        "audit.read_self",
        "reports.create",
        "reports.read_public",
        "reports.update_own",
        "reports.delete_own",
        "reports.verify",
        "reports.transition",
        "institutions.read",
        "comments.create",
        "resolution.verify",
        "government_data.read",
        "analytics.read",
        "analytics.export",
        "ai.use",
        "departments.read",
        "cases.read",
    },
    "moderator": {
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "reports.read_private",
        "reports.moderate",
        "reports.verify",
        "reports.transition",
        "institutions.read",
        "comments.create",
        "comments.moderate",
        "analytics.read",
        "ai.use",
        "departments.read",
        "cases.create",
        "cases.read",
        "cases.read_internal",
        "cases.reopen.request",
        "sla.read",
        "security.read",
    },
    "institution_representative": {
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "institutions.read",
        "institutions.update",
        "institutions.twin.update",
        "comments.create",
        "resolution.submit",
        "analytics.read",
        "ai.use",
        "departments.read",
        "cases.create",
        "cases.read",
        "cases.respond",
        "sla.read",
    },
    "department_representative": {
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "reports.read_private",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "reports.reopen",
        "institutions.read",
        "institutions.update",
        "institutions.twin.update",
        "comments.create",
        "resolution.submit",
        "analytics.read",
        "analytics.advanced",
        "government_data.read",
        "government_data.import",
        "ai.use",
        "departments.read",
        "cases.create",
        "cases.read",
        "cases.read_internal",
        "cases.acknowledge",
        "cases.respond",
        "cases.actions.manage",
        "cases.reopen.request",
        "cases.escalate",
        "sla.read",
        "government.read",
        "government.route",
        "government.respond",
    },
    "department_manager": {
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "reports.read_private",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "reports.reopen",
        "institutions.read",
        "institutions.update",
        "institutions.twin.update",
        "comments.create",
        "resolution.submit",
        "analytics.read",
        "analytics.advanced",
        "government_data.read",
        "government_data.import",
        "ai.use",
        "departments.read",
        "departments.members.manage",
        "cases.create",
        "cases.read",
        "cases.read_internal",
        "cases.assign",
        "cases.acknowledge",
        "cases.respond",
        "cases.actions.manage",
        "cases.reopen.request",
        "cases.escalate",
        "sla.read",
        "analytics.department",
        "government.read",
        "government.route",
        "government.handoff",
        "government.respond",
        "government.analytics",
    },
    "reviewer": {
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "reports.read_private",
        "institutions.read",
        "government_data.read",
        "analytics.read",
        "ai.use",
        "departments.read",
        "cases.read",
        "cases.read_internal",
        "cases.reopen.request",
        "resolution.review",
        "resolution.verify",
        "sla.read",
        "analytics.department",
        "government.read",
        "government.analytics",
    },
    "analyst": {
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "reports.read_public",
        "institutions.read",
        "government_data.read",
        "government_data.import",
        "analytics.read",
        "analytics.advanced",
        "analytics.export",
        "ai.use",
        "departments.read",
        "sla.read",
        "analytics.department",
    },
    "admin": {
        "identity.read_self",
        "identity.update_self",
        "audit.read_self",
        "audit.read_all",
        "users.read",
        "users.manage",
        "users.roles.manage",
        "reports.create",
        "reports.read_public",
        "reports.read_private",
        "reports.update_own",
        "reports.delete_own",
        "reports.moderate",
        "reports.verify",
        "reports.assign",
        "reports.transition",
        "reports.resolve",
        "reports.reopen",
        "institutions.read",
        "institutions.create",
        "institutions.update",
        "institutions.twin.update",
        "institutions.verify",
        "comments.create",
        "comments.moderate",
        "resolution.submit",
        "resolution.review",
        "resolution.verify",
        "government_data.read",
        "government_data.import",
        "government_data.manage",
        "analytics.read",
        "analytics.advanced",
        "analytics.export",
        "ai.use",
        "ai.admin",
        "administration.configure",
        "administration.institutions",
        "system.manage",
        "departments.manage",
        "departments.jurisdiction.manage",
        "departments.members.manage",
        "departments.verify_org",
        "cases.create",
        "cases.manage",
        "cases.assign",
        "cases.escalate",
        "cases.respond",
        "sla.manage",
        "escalation.manage",
        "analytics.department",
        "government.read",
        "government.manage",
        "government.route",
        "government.handoff",
        "government.respond",
        "government.integration",
        "government.analytics",
        "security.read",
        "security.manage",
    },
    "super_admin": {
        "*"  # Super admin possesses all permissions wildcard
    },
}


class AuthorizationError(ApiError):
    def __init__(self, detail: str = "insufficient permissions", code: str = "forbidden") -> None:
        super().__init__(detail, 403, code)


class AuthorizationService:
    @staticmethod
    def get_user_permissions(user: User) -> set[str]:
        """Collect the aggregate set of permissions granted by all of the user's active roles."""
        perms: set[str] = set()
        for role_code in user.role_codes():
            role_perms = ROLE_PERMISSIONS.get(role_code, set())
            if "*" in role_perms:
                return {"*"}
            perms.update(role_perms)
        return perms

    @classmethod
    def can(cls, user: User, permission: str, resource: Any = None) -> bool:
        """Check if a user has a specific permission, optionally evaluating resource ownership."""
        if not user.is_active or user.is_deleted:
            return False

        # MFA gate takes precedence over everything, including super_admin.
        if mfa_gate_denies(user, permission):
            return False

        # Super admin override
        if user.has_role("super_admin"):
            return True

        user_perms = cls.get_user_permissions(user)
        if "*" not in user_perms and permission not in user_perms:
            return False

        # Resource-level authorization policies
        if resource is not None:
            return cls._check_resource_policy(user, permission, resource)

        return True

    @classmethod
    def require(cls, user: User, permission: str, resource: Any = None) -> None:
        """Assert that a user has permission; raises AuthorizationError (403) if denied."""
        if mfa_gate_denies(user, permission):
            _raise_mfa_required()
        if not cls.can(user, permission, resource):
            raise AuthorizationError(
                detail=f"permission denied: requires '{permission}'",
                code="insufficient_permissions",
            )

    @classmethod
    def _check_resource_policy(cls, user: User, permission: str, resource: Any) -> bool:
        """Evaluate resource ownership and scoping rules."""
        # Admin override for all resources
        if user.has_role("admin") or user.has_role("super_admin"):
            return True

        # Report ownership check (User A cannot edit/delete User B's report)
        if permission in ("reports.update_own", "reports.delete_own"):
            reporter_id = getattr(resource, "reporter_id", None)
            if reporter_id is not None:
                # Handle UUID comparison whether UUID object or string
                return str(reporter_id) == str(user.id)

        # Institution representative scoped twin update
        if permission == "institutions.twin.update" and user.has_role("institution_representative"):
            # Future claim / association check; representative can manage assigned twin
            return True

        # User profile self-modification check
        if permission in ("identity.update_self", "identity.delete_self"):
            target_id = getattr(resource, "id", None)
            if target_id is not None:
                return str(target_id) == str(user.id)

        return True


def require_permission(permission: str) -> Callable[..., Any]:
    """FastAPI dependency for verifying a specific permission on the authenticated user."""

    async def dependency(user: CurrentUser) -> User:
        AuthorizationService.require(user, permission)
        return user

    return dependency


def require_any_permission(*permissions: str) -> Callable[..., Any]:
    """FastAPI dependency for verifying that the user has at least one of the listed permissions."""

    async def dependency(user: CurrentUser) -> User:
        if any(mfa_gate_denies(user, p) for p in permissions):
            _raise_mfa_required()
        if not any(AuthorizationService.can(user, p) for p in permissions):
            raise AuthorizationError(
                detail=f"permission denied: requires one of {permissions}",
                code="insufficient_permissions",
            )
        return user

    return dependency
