"""Phase 7 Authorization, RBAC, and IDOR test suite (PRD §14, SECURITY.md §3)."""

from __future__ import annotations

import uuid

import pytest

from tk_api.auth.authorization import ROLE_PERMISSIONS, AuthorizationError, AuthorizationService
from tk_api.users.models import Role, User


class MockReport:
    def __init__(self, reporter_id: uuid.UUID) -> None:
        self.id = uuid.uuid4()
        self.reporter_id = reporter_id


def make_user(roles: list[str], status: str = "active") -> User:
    u = User(
        id=uuid.uuid4(),
        email="test@example.com",
        display_name="Test User",
        status=status,
    )
    u.roles = [Role(id=uuid.uuid4(), code=r, name=r.capitalize()) for r in roles]
    return u


def test_all_standard_roles_have_defined_permissions() -> None:
    expected_roles = {
        "citizen",
        "volunteer",
        "verified_contributor",
        "moderator",
        "institution_representative",
        "department_representative",
        "analyst",
        "admin",
        "super_admin",
    }
    assert expected_roles.issubset(set(ROLE_PERMISSIONS.keys()))


def test_super_admin_has_all_permissions_wildcard() -> None:
    super_admin = make_user(["super_admin"])
    assert AuthorizationService.can(super_admin, "any.arbitrary.permission") is True
    assert AuthorizationService.can(super_admin, "system.manage") is True
    assert AuthorizationService.can(super_admin, "users.roles.manage") is True


def test_citizen_permissions_and_restrictions() -> None:
    citizen = make_user(["citizen"])
    assert AuthorizationService.can(citizen, "reports.create") is True
    assert AuthorizationService.can(citizen, "reports.read_public") is True
    assert AuthorizationService.can(citizen, "comments.create") is True

    # Citizens cannot moderate reports or manage system
    assert AuthorizationService.can(citizen, "reports.moderate") is False
    assert AuthorizationService.can(citizen, "system.manage") is False
    assert AuthorizationService.can(citizen, "users.roles.manage") is False


def test_moderator_permissions() -> None:
    moderator = make_user(["moderator"])
    assert AuthorizationService.can(moderator, "reports.moderate") is True
    assert AuthorizationService.can(moderator, "comments.moderate") is True
    assert AuthorizationService.can(moderator, "reports.read_private") is True
    assert AuthorizationService.can(moderator, "users.roles.manage") is False


def test_idor_report_ownership_checks() -> None:
    user_a = make_user(["citizen"])
    user_b = make_user(["citizen"])
    report_a = MockReport(reporter_id=user_a.id)

    # User A can update their own report
    assert AuthorizationService.can(user_a, "reports.update_own", resource=report_a) is True

    # User B CANNOT update User A's report (IDOR Protection)
    assert AuthorizationService.can(user_b, "reports.update_own", resource=report_a) is False

    # AuthorizationService.require raises AuthorizationError for User B
    with pytest.raises(AuthorizationError):
        AuthorizationService.require(user_b, "reports.update_own", resource=report_a)

    # Admin CAN update any report
    admin = make_user(["admin"])
    assert AuthorizationService.can(admin, "reports.update_own", resource=report_a) is True


def test_inactive_and_deleted_users_denied_all_permissions() -> None:
    pending_user = make_user(["citizen"], status="pending_verification")
    assert AuthorizationService.can(pending_user, "reports.create") is False

    suspended_user = make_user(["citizen"], status="suspended")
    assert AuthorizationService.can(suspended_user, "reports.create") is False
