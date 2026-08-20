"""Tests for Phase 12: Civic Analytics, Dashboards, Command Center, and Decision Intelligence."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from tests.conftest import _register_and_verify
from tk_api.ai.models import AiRun
from tk_api.analytics.catalog import GLOBAL_METRIC_REGISTRY
from tk_api.analytics.schemas import AnalyticsFilterParams, ExportRequest
from tk_api.analytics.service import AnalyticsService
from tk_api.civic.models import Category, IssueType
from tk_api.core.db import create_session_factory
from tk_api.geography.models import Geography, GeographyType
from tk_api.institutions.models import Institution, InstitutionType
from tk_api.provenance.models import DataSource, ExternalSource
from tk_api.reports.models import Report
from tk_api.users.models import Role, User, UserRole


def _promote_to_admin(client: TestClient, user_id: str) -> None:
    async def promote() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == "admin"))
            if not role:
                role = Role(code="admin", name="Admin")
                session.add(role)
                await session.flush()
            user = await session.get(User, uuid.UUID(user_id))
            if user:
                session.add(UserRole(user_id=user.id, role_id=role.id))
                await session.commit()

    asyncio.run(promote())


def _admin_headers(client: TestClient, sender: Any) -> dict[str, str]:
    phone_suffix = str(int(uuid.uuid4().hex[:6], 16) % 90000 + 10000)
    tokens = _register_and_verify(client, sender, f"98765{phone_suffix}")
    _promote_to_admin(client, tokens["user"]["id"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_test_user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        status="active",
    )
    session.add(user)
    await session.flush()
    return user


def test_metric_catalog_registration() -> None:
    """Metric registry contains core metrics with formulas, dimensions, and permissions."""
    metric = GLOBAL_METRIC_REGISTRY.get_metric("resolution_rate")
    assert metric is not None
    assert metric.unit == "percentage"
    assert "reports" in metric.formula or "resolved" in metric.formula

    public_metrics = GLOBAL_METRIC_REGISTRY.list_metrics(role="public")
    assert any(m.metric_id == "report_count" for m in public_metrics)
    assert not any(m.metric_id == "ai_cost_usd" for m in public_metrics)

    admin_metrics = GLOBAL_METRIC_REGISTRY.list_metrics(role="admin")
    assert any(m.metric_id == "ai_cost_usd" for m in admin_metrics)


def test_analytics_overview_kpis(client: TestClient) -> None:
    """Overview service computes live verified reports, resolution rates, and KPI cards."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            user = await _create_test_user(session)
            cat = Category(
                id=uuid.uuid4(),
                slug="roads",
                icon="road",
                form_schema={},
                verification_policy={},
                default_locale_keys={"en": "Roads"},
            )
            session.add(cat)
            await session.flush()

            now = datetime.now(UTC)
            r1 = Report(
                id=uuid.uuid4(),
                ticket_no="TK-A1",
                title="Pothole 1",
                description="Pothole description 1",
                reporter_id=user.id,
                location={"type": "Point", "coordinates": [77.2, 28.6]},
                location_accuracy_m=Decimal("10.0"),
                category_id=cat.id,
                status="resolved",
                created_at=now - timedelta(days=2),
                resolved_at=now - timedelta(days=1),
                visibility="public",
            )
            r2 = Report(
                id=uuid.uuid4(),
                ticket_no="TK-A2",
                title="Pothole 2",
                description="Pothole description 2",
                reporter_id=user.id,
                location={"type": "Point", "coordinates": [77.2, 28.6]},
                location_accuracy_m=Decimal("10.0"),
                category_id=cat.id,
                status="submitted",
                created_at=now - timedelta(days=1),
                visibility="public",
            )
            session.add_all([r1, r2])
            await session.commit()

            service = AnalyticsService()
            res = await service.get_overview_kpis(session, AnalyticsFilterParams(date_preset="30d"))

            assert len(res.kpis) >= 5
            kpi_map = {k.metric_id: k.value for k in res.kpis}
            assert kpi_map["report_count"] >= 2.0
            assert kpi_map["resolved_report_count"] >= 1.0

    asyncio.run(_run())


def test_analytics_report_trends(client: TestClient) -> None:
    """Report trends aggregate time-series points across days."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            user = await _create_test_user(session)
            cat = Category(
                id=uuid.uuid4(),
                slug="water",
                icon="droplet",
                form_schema={},
                verification_policy={},
                default_locale_keys={"en": "Water"},
            )
            session.add(cat)
            await session.flush()

            now = datetime.now(UTC)
            r = Report(
                id=uuid.uuid4(),
                ticket_no="TK-W1",
                title="Water leakage",
                description="Broken pipeline leaking fresh water",
                reporter_id=user.id,
                location={"type": "Point", "coordinates": [77.2, 28.6]},
                location_accuracy_m=Decimal("10.0"),
                category_id=cat.id,
                status="verified",
                severity="critical",
                created_at=now,
                visibility="public",
            )
            session.add(r)
            await session.commit()

            service = AnalyticsService()
            trends = await service.get_report_trends(
                session, AnalyticsFilterParams(interval="day", date_preset="30d")
            )

            assert len(trends.series) >= 1
            assert trends.total_in_range >= 1
            assert any(p.critical_count >= 1 for p in trends.series)

    asyncio.run(_run())


def test_analytics_category_breakdown(client: TestClient) -> None:
    """Category analytics breaks down reports by category and top issue types."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            user = await _create_test_user(session)
            cat = Category(
                id=uuid.uuid4(),
                slug="education",
                icon="book",
                form_schema={},
                verification_policy={},
                default_locale_keys={"en": "Education"},
            )
            session.add(cat)
            await session.flush()

            itype = IssueType(
                id=uuid.uuid4(),
                category_id=cat.id,
                slug="school_toilets",
                name="School Toilets",
            )
            session.add(itype)
            await session.flush()

            r = Report(
                id=uuid.uuid4(),
                ticket_no="TK-E1",
                title="Broken school toilet",
                description="Needs sanitization and plumber repair",
                reporter_id=user.id,
                location={"type": "Point", "coordinates": [77.2, 28.6]},
                location_accuracy_m=Decimal("10.0"),
                category_id=cat.id,
                issue_type_id=itype.id,
                status="submitted",
                visibility="public",
            )
            session.add(r)
            await session.commit()

            service = AnalyticsService()
            cat_res = await service.get_category_analytics(
                session, AnalyticsFilterParams(date_preset="30d")
            )

            assert len(cat_res.categories) >= 1
            ed_cat = next((c for c in cat_res.categories if c.category_slug == "education"), None)
            assert ed_cat is not None
            assert ed_cat.report_count >= 1
            assert any(it.slug == "school_toilets" for it in ed_cat.top_issue_types)

    asyncio.run(_run())


def test_analytics_resolution_and_aging(client: TestClient) -> None:
    """Resolution and backlog analytics compute durations, rates, and aging buckets."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            user = await _create_test_user(session)
            cat = Category(
                id=uuid.uuid4(),
                slug="sanitation",
                icon="trash",
                form_schema={},
                verification_policy={},
                default_locale_keys={"en": "Sanitation"},
            )
            session.add(cat)
            await session.flush()

            now = datetime.now(UTC)
            r_res = Report(
                id=uuid.uuid4(),
                ticket_no="TK-S1",
                title="Cleaned garbage pile",
                description="Garbage removal verified on site",
                reporter_id=user.id,
                location={"type": "Point", "coordinates": [77.2, 28.6]},
                location_accuracy_m=Decimal("10.0"),
                category_id=cat.id,
                status="resolved",
                created_at=now - timedelta(hours=48),
                resolved_at=now,
                visibility="public",
            )
            r_old_open = Report(
                id=uuid.uuid4(),
                ticket_no="TK-S2",
                title="Overflowing drain",
                description="Drain uncleaned for two weeks",
                reporter_id=user.id,
                location={"type": "Point", "coordinates": [77.2, 28.6]},
                location_accuracy_m=Decimal("10.0"),
                category_id=cat.id,
                status="submitted",
                created_at=now - timedelta(days=15),
                visibility="public",
            )
            session.add_all([r_res, r_old_open])
            await session.commit()

            service = AnalyticsService()
            res_data = await service.get_resolution_analytics(
                session, AnalyticsFilterParams(date_preset="30d")
            )
            assert res_data.total_resolved >= 1
            assert res_data.median_resolution_hours is not None
            assert res_data.median_resolution_hours >= 40.0

            backlog_data = await service.get_verification_and_backlog(
                session, AnalyticsFilterParams(date_preset="30d")
            )
            assert len(backlog_data.aging_buckets) == 4
            b_8_30 = next(
                (b for b in backlog_data.aging_buckets if b.bucket_label == "8-30 days"), None
            )
            assert b_8_30 is not None
            assert b_8_30.count >= 1

    asyncio.run(_run())


def test_analytics_geographic_drilldown(client: TestClient) -> None:
    """Geographic analytics aggregates metrics across child hierarchy nodes."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            gtype = GeographyType(id=uuid.uuid4(), code="state", name_key="geo.state")
            session.add(gtype)
            await session.flush()

            geo = Geography(
                id=uuid.uuid4(),
                type_id=gtype.id,
                name="Rajasthan",
                normalized_name="rajasthan",
                country_code="IN",
            )
            session.add(geo)
            await session.commit()

            service = AnalyticsService()
            geo_res = await service.get_geographic_drilldown(session, AnalyticsFilterParams())
            assert len(geo_res.children) >= 1
            assert any(c.name == "Rajasthan" for c in geo_res.children)

    asyncio.run(_run())


def test_analytics_institution_summary(client: TestClient) -> None:
    """Institution analytics calculates individual institutional workload and resolution rate."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            ext = ExternalSource(
                id=uuid.uuid4(),
                name="Health Dept",
                publisher="Govt",
                url="https://health.gov.in",
            )
            session.add(ext)
            await session.flush()

            itype = InstitutionType(id=uuid.uuid4(), code="hospital", name_key="inst.hospital")
            session.add(itype)
            await session.flush()

            inst = Institution(
                id=uuid.uuid4(),
                institution_type_id=itype.id,
                source_id=ext.id,
                name="Jaipur District Hospital",
                normalized_name="jaipur district hospital",
                operational_status="active",
            )
            session.add(inst)
            await session.commit()

            service = AnalyticsService()
            inst_data = await service.get_institution_analytics(session, inst.id)
            assert inst_data is not None
            assert inst_data.name == "Jaipur District Hospital"
            assert inst_data.resolution_rate >= 0.0

    asyncio.run(_run())


def test_data_quality_and_ai_ops_scorecards(client: TestClient) -> None:
    """Admin scorecards calculate source freshness and AI token/cost telemetry."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # Seed data source
            src = DataSource(
                id=uuid.uuid4(),
                name="PMGSY Roads Dataset",
                source_type="official_portal",
                verification_state="verified",
            )
            session.add(src)

            # Seed AI run
            run = AiRun(
                id=uuid.uuid4(),
                task_kind="chat_assistant",
                model_id="deepseek-chat",
                provider="deepseek",
                payload_in={},
                payload_out={},
                tokens_in=120,
                tokens_out=60,
                cost_usd=Decimal("0.000500"),
                latency_ms=250,
                status="succeeded",
            )
            session.add(run)
            await session.commit()

            service = AnalyticsService()
            dq = await service.get_data_quality_analytics(session)
            assert dq.total_sources >= 1
            assert dq.healthy_sources_count >= 1

            ai_ops = await service.get_ai_operations_analytics(session)
            assert ai_ops.total_requests >= 1
            assert ai_ops.total_tokens >= 180
            assert ai_ops.estimated_cost_usd >= 0.0005

    asyncio.run(_run())


def test_analytics_export_engine(client: TestClient, sender: Any) -> None:
    """Export engine streams CSV and JSON with formatted headers."""

    async def _run() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            service = AnalyticsService()

            # CSV export
            csv_exp = await service.export_analytics(
                session, ExportRequest(domain="reports", format="csv")
            )
            assert "text/csv" in csv_exp.content_type
            assert "ticket_no" in csv_exp.data

            # JSON export
            json_exp = await service.export_analytics(
                session, ExportRequest(domain="reports", format="json")
            )
            assert "application/json" in json_exp.content_type
            assert "records" in json_exp.data

    asyncio.run(_run())


def test_analytics_api_endpoints_and_rbac(client: TestClient, sender: Any) -> None:
    """FastAPI analytics endpoints respond correctly with public access and admin guards."""
    # 1. Public catalog
    cat_resp = client.get("/api/v1/analytics/catalog")
    assert cat_resp.status_code == 200
    assert "metrics" in cat_resp.json()

    # 2. Public overview
    ov_resp = client.get("/api/v1/analytics/overview")
    assert ov_resp.status_code == 200
    assert "kpis" in ov_resp.json()

    # 3. Public trends
    tr_resp = client.get("/api/v1/analytics/trends")
    assert tr_resp.status_code == 200
    assert "series" in tr_resp.json()

    # 4. Admin endpoints guard (anonymous callers receive 401/403)
    ai_ops_unauth = client.get("/api/v1/analytics/ai-ops")
    assert ai_ops_unauth.status_code in (401, 403)

    # 5. Admin endpoints with admin token
    headers = _admin_headers(client, sender)
    ai_ops_admin = client.get("/api/v1/analytics/ai-ops", headers=headers)
    assert ai_ops_admin.status_code == 200
    assert "total_requests" in ai_ops_admin.json()

    dq_admin = client.get("/api/v1/analytics/data-quality", headers=headers)
    assert dq_admin.status_code == 200
    assert "total_sources" in dq_admin.json()
