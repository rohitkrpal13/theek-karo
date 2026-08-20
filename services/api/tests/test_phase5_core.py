"""Tests for Phase 5 core architecture: health, error RFC 9457, correlation headers,
pagination, filtering, config validation, issue types, and expanded FSM transitions.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from starlette.testclient import TestClient

from tk_api.civic.models import Category
from tk_api.core.config import Settings
from tk_api.core.db import create_session_factory
from tk_api.core.pagination import PageParams, PageResponse, decode_cursor, encode_cursor
from tk_api.reports.models import Report
from tk_api.reports.state import transition_report
from tk_api.users.models import Role, User, UserRole


def test_health_and_readiness_endpoints(client: TestClient) -> None:
    # Liveness
    res_h = client.get("/health")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "ok"

    res_hz = client.get("/healthz")
    assert res_hz.status_code == 200
    assert res_hz.json()["status"] == "ok"

    # Readiness
    res_r = client.get("/ready")
    assert res_r.status_code == 200
    assert res_r.json()["checks"]["database"] == "ok"

    res_rz = client.get("/readyz")
    assert res_rz.status_code == 200
    assert res_rz.json()["checks"]["database"] == "ok"


def test_correlation_headers_and_error_details(client: TestClient) -> None:
    # 1. Custom incoming correlation ID
    custom_cid = "test-corr-" + uuid.uuid4().hex
    res = client.get("/api/v1/civic/categories", headers={"X-Correlation-Id": custom_cid})
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-Id") == custom_cid
    assert res.headers.get("X-Request-Id") == custom_cid

    # 2. RFC 9457 Problem details on error with request_id
    err_res = client.get("/api/v1/geography/00000000-0000-0000-0000-000000000000")
    assert err_res.status_code == 404
    assert err_res.headers.get("content-type") == "application/problem+json"
    body = err_res.json()
    assert body["status"] == 404
    assert "request_id" in body
    assert body["title"] == "Not found"


def test_pagination_and_cursor_encoding() -> None:
    params = PageParams(page=2, limit=10)
    assert params.offset == 10
    resp = PageResponse.create(items=[1, 2, 3], total=25, params=params)
    assert resp.pages == 3
    assert resp.total == 25

    # Cursor encoding roundtrip
    raw = "2026-08-16T10:00:00Z"
    enc = encode_cursor(raw)
    dec = decode_cursor(enc)
    assert dec == raw


def test_production_config_validation() -> None:
    # In dev, dev secrets are permitted
    dev_settings = Settings(env="dev", jwt_secret="dev-secret-change-me")
    assert not dev_settings.is_production
    dev_settings.validate_production_readiness()

    # In prod, dev secrets fail fast
    with pytest.raises(
        ValueError, match="In production/staging, TK_JWT_SECRET must be at least 32 characters"
    ):
        prod_bad = Settings(env="prod", jwt_secret="dev-secret-change-me")
        prod_bad.validate_production_readiness()

    # In prod with insecure short secret
    with pytest.raises(
        ValueError, match="In production/staging, TK_JWT_SECRET must be at least 32 characters"
    ):
        prod_short = Settings(env="prod", jwt_secret="short-key")
        prod_short.validate_production_readiness()

    # In prod, privileged-role MFA enforcement is mandatory
    with pytest.raises(
        ValueError, match="In production/staging, TK_MFA_ENFORCE_PRIVILEGED must be true"
    ):
        no_mfa = Settings(
            env="prod",
            jwt_secret="very-long-production-grade-jwt-secret-string-12345",
            database_url="postgresql+asyncpg://tk:real_prod_pw@db.internal:5432/tk",
            webhook_master_secret="very-long-production-grade-webhook-secret-67890",
        )
        no_mfa.validate_production_readiness()

    # Valid prod settings pass
    valid_prod = Settings(
        env="prod",
        oauth_mock_enabled=False,
        notification_callback_secret="very-long-production-grade-callback-secret-12345",
        mfa_enforce_privileged=True,
        jwt_secret="very-long-production-grade-jwt-secret-string-12345",
        database_url="postgresql+asyncpg://tk:real_prod_pw@db.internal:5432/tk",
        webhook_master_secret="very-long-production-grade-webhook-secret-67890",
        otp_channel="twilio",
        twilio_account_sid="AC-test",
        twilio_auth_token="test",
        twilio_from_number="+15005550001",
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_from="no-reply@example.com",
    )
    assert valid_prod.is_production
    valid_prod.validate_production_readiness()


def test_issue_types_api(client: TestClient) -> None:
    async def seed_category() -> uuid.UUID:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            cat = Category(
                slug="health_p5",
                icon="hospital",
                form_schema={"type": "object"},
                verification_policy={"policy": "threshold"},
                default_locale_keys={"name": "Health"},
            )
            session.add(cat)
            await session.commit()

    asyncio.run(seed_category())

    res = client.get("/api/v1/civic/issue-types?category_slug=health_p5")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_expanded_report_fsm_transitions(client: TestClient) -> None:
    async def run_fsm_flow() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            from sqlalchemy import select

            citizen_role = await session.scalar(select(Role).where(Role.code == "citizen"))
            volunteer_role = await session.scalar(select(Role).where(Role.code == "volunteer"))
            official_role = await session.scalar(select(Role).where(Role.code == "official"))

            citizen_user = User(display_name="Citizen", trust_score=0)
            volunteer_user = User(display_name="Volunteer", trust_score=0)
            official_user = User(display_name="Official", trust_score=0)
            session.add_all([citizen_user, volunteer_user, official_user])
            await session.flush()

            if citizen_role:
                session.add(UserRole(user_id=citizen_user.id, role_id=citizen_role.id))
            if volunteer_role:
                session.add(UserRole(user_id=volunteer_user.id, role_id=volunteer_role.id))
            if official_role:
                session.add(UserRole(user_id=official_user.id, role_id=official_role.id))

            cat = Category(
                slug=f"roads_{uuid.uuid4().hex[:4]}",
                icon="road",
                form_schema={"type": "object"},
                verification_policy={"policy": "threshold"},
                default_locale_keys={"name": "Roads"},
            )
            session.add(cat)
            await session.flush()

            # Create report in submitted state
            report = Report(
                ticket_no=f"TK-FSM-{uuid.uuid4().hex[:4]}",
                category_id=cat.id,
                reporter_id=citizen_user.id,
                title="Pothole on Main Street",
                description="Large pothole causing vehicle damage",
                location={"type": "Point", "coordinates": [85.123, 25.456]},
                location_accuracy_m=10,
                status="submitted",
                visibility="public",
            )
            session.add(report)
            await session.commit()

            # Refresh objects with relationships
            from sqlalchemy.orm import selectinload

            volunteer_u = (
                await session.execute(
                    select(User)
                    .where(User.id == volunteer_user.id)
                    .options(selectinload(User.roles))
                )
            ).scalar_one()
            official_u = (
                await session.execute(
                    select(User)
                    .where(User.id == official_user.id)
                    .options(selectinload(User.roles))
                )
            ).scalar_one()

            # 1. submitted -> under_verification (by volunteer)
            await transition_report(
                session, report, to_status="under_verification", reason=None, actor=volunteer_u
            )
            assert report.status == "under_verification"

            # 2. under_verification -> verified (by volunteer)
            await transition_report(
                session, report, to_status="verified", reason=None, actor=volunteer_u
            )
            assert report.status == "verified"

            # 3. verified -> assigned (by official)
            await transition_report(
                session, report, to_status="assigned", reason=None, actor=official_u
            )
            assert report.status == "assigned"

            # 4. assigned -> in_progress (by official)
            await transition_report(
                session, report, to_status="in_progress", reason=None, actor=official_u
            )
            assert report.status == "in_progress"

            # 5. in_progress -> resolution_submitted (by official)
            await transition_report(
                session, report, to_status="resolution_submitted", reason=None, actor=official_u
            )
            assert report.status == "resolution_submitted"

            # 6. resolution_submitted -> resolution_review (by volunteer)
            await transition_report(
                session, report, to_status="resolution_review", reason=None, actor=volunteer_u
            )
            assert report.status == "resolution_review"

            # 7. resolution_review -> resolved (by official)
            await transition_report(
                session, report, to_status="resolved", reason=None, actor=official_u
            )
            assert report.status == "resolved"

            # 8. resolved -> community_verified (by volunteer)
            await transition_report(
                session, report, to_status="community_verified", reason=None, actor=volunteer_u
            )
            assert report.status == "community_verified"

    asyncio.run(run_fsm_flow())
