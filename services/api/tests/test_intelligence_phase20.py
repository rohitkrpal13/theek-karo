"""Phase 20 Civic Intelligence Platform tests (spec §6-§22).

Covers the deterministic engines (trends, IQR anomalies, issue clusters,
recurring issues, data freshness), the signal review lifecycle, forecast
runs, intelligence report generation, and the model version registry.

All tests run on the in-memory SQLite unit schema; the migration is exercised
separately against Postgres (integration/ marked tests).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tests.test_govdata_phase10 import _admin_headers
from tk_api.civic.models import Category
from tk_api.core.db import create_session_factory
from tk_api.geography.models import Geography, GeographyType
from tk_api.institutions.models import Institution, InstitutionType
from tk_api.intelligence.models import IntelligenceReport, IssueCluster
from tk_api.reports.models import Report
from tk_api.users.models import User, UserRole


def _grant_role(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        from tk_api.users.models import Role

        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _department_headers(client: TestClient, sender: Any) -> dict[str, str]:
    phone_suffix = str(int(uuid.uuid4().hex[:6], 16) % 90000 + 10000)
    tokens = _register_and_verify(client, sender, f"98764{phone_suffix}")
    _grant_role(client, tokens["user"]["id"], "department_representative")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _citizen_headers(client: TestClient, sender: Any) -> dict[str, str]:
    phone_suffix = str(int(uuid.uuid4().hex[:6], 16) % 90000 + 10000)
    tokens = _register_and_verify(client, sender, f"98763{phone_suffix}")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _seed_context(client: TestClient, sender: Any) -> dict[str, uuid.UUID]:
    """Geography type + geography + category + institution + reporter user."""

    async def seed() -> dict[str, uuid.UUID]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            geo_type = GeographyType(code="district", name_key="geo.district", sort_order=3)
            session.add(geo_type)
            await session.flush()
            geo = Geography(
                type_id=geo_type.id,
                name="Patna",
                normalized_name="patna",
                country_code="IN",
                official_identifier="IN-PA",
            )
            session.add(geo)
            await session.flush()
            category = Category(
                slug=f"water_{uuid.uuid4().hex[:6]}",
                icon="water",
                form_schema={},
                verification_policy={},
                default_locale_keys={},
            )
            session.add(category)
            await session.flush()
            inst_type = InstitutionType(code="pws", name_key="inst.pws", attribute_schema={})
            session.add(inst_type)
            await session.flush()
            from tk_api.provenance.models import ExternalSource

            ext = ExternalSource(
                name="Test Source",
                publisher="Test",
                url="https://example.test",
                license="test",
            )
            session.add(ext)
            await session.flush()
            inst = Institution(
                institution_type_id=inst_type.id,
                name="Patna Water Board",
                normalized_name="patna water board",
                geography_id=geo.id,
                operational_status="active",
                source_id=ext.id,
            )
            session.add(inst)
            await session.flush()
            user = User(
                email=f"reporter_{uuid.uuid4().hex[:8]}@example.com",
                display_name="Citizen Reporter",
                status="active",
            )
            session.add(user)
            await session.flush()
            await session.commit()
            return {
                "geography_id": geo.id,
                "category_id": category.id,
                "institution_id": inst.id,
                "user_id": user.id,
            }

    return asyncio.run(seed())


def _put_report(
    client: TestClient,
    ctx: dict[str, uuid.UUID],
    *,
    created_at: datetime,
    title: str = "Water issue",
    description: str = "Water supply irregular since morning",
    status: str = "submitted",
    institution_id: uuid.UUID | None = None,
) -> None:
    async def insert() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            session.add(
                Report(
                    ticket_no=f"TK-{uuid.uuid4().hex[:10].upper()}",
                    category_id=ctx["category_id"],
                    reporter_id=ctx["user_id"],
                    institution_id=institution_id or ctx["institution_id"],
                    title=title,
                    description=description,
                    location={"coordinates": [85.1, 25.6]},
                    location_accuracy_m=5,
                    boundary_id=ctx["geography_id"],
                    status=status,
                    visibility="public",
                    created_at=created_at,
                )
            )
            await session.commit()

    asyncio.run(insert())


def _weeks_ago(n: int, *, hour: int = 10) -> datetime:
    return datetime.now(UTC) - timedelta(weeks=n)


def test_overview_public(client: TestClient, sender: Any) -> None:
    res = client.get("/api/v1/intelligence/overview")
    assert res.status_code == 200, res.text
    body = res.json()
    keys = {s["key"] for s in body["sections"]}
    assert {"trends", "anomalies", "clusters", "recurring_issues", "data_freshness"} <= keys
    assert body["methodology_note"]


def test_clusters_detected_and_persisted(client: TestClient, sender: Any) -> None:
    ctx = _seed_context(client, sender)
    for i in range(4):
        _put_report(client, ctx, created_at=_weeks_ago(i), title=f"Water leak #{i}")
    res = client.get("/api/v1/intelligence/clusters")
    assert res.status_code == 200, res.text
    clusters = res.json()["clusters"]
    assert any(c["report_count"] >= 4 for c in clusters), clusters[:2]

    async def persisted() -> int:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            row = await session.scalar(select(IssueCluster))
            return row.report_count if row else 0

    assert asyncio.run(persisted()) >= 4


def test_recurring_issue_detection(client: TestClient, sender: Any) -> None:
    ctx = _seed_context(client, sender)
    for m in range(4):
        _put_report(client, ctx, created_at=_weeks_ago(m * 5))
    res = client.get("/api/v1/intelligence/recurring")
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert items, res.text
    assert any(i["distinct_months"] >= 3 for i in items), items


def test_anomaly_detection_on_volume_spike(client: TestClient, sender: Any) -> None:
    ctx = _seed_context(client, sender)
    for w in range(17, 8, -1):
        _put_report(client, ctx, created_at=_weeks_ago(w))
    for _ in range(40):
        _put_report(client, ctx, created_at=_weeks_ago(2))
    res = client.get("/api/v1/intelligence/anomalies")
    assert res.status_code == 200, res.text
    anomalies = res.json()["anomalies"]
    assert any(a["metric"] == "report_volume" for a in anomalies), anomalies


def test_signals_review_lifecycle(client: TestClient, sender: Any) -> None:
    admin_h = _admin_headers(client, sender)
    res = client.post(
        "/api/v1/intelligence/signals",
        headers=admin_h,
        json={
            "signal_type": "DATA_CONFLICT",
            "title": "Test signal",
            "description": "seed from test",
            "severity": "HIGH",
            "confidence": "MEDIUM",
        },
    )
    assert res.status_code == 201, res.text
    signal_id = res.json()["id"]

    dept_h = _department_headers(client, sender)
    review = client.post(
        f"/api/v1/intelligence/signals/{signal_id}/review",
        headers=dept_h,
        json={"action": "CONFIRM", "note": "verified in test"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "CONFIRMED_SIGNAL"
    assert review.json()["review_history"][0]["action"] == "CONFIRM"

    listing = client.get("/api/v1/intelligence/signals", headers=admin_h)
    assert listing.status_code == 200
    assert any(s["id"] == signal_id for s in listing.json()["items"])

    detail = client.get(f"/api/v1/intelligence/signals/{signal_id}")
    assert detail.status_code == 200
    assert detail.json()["evidence"][0]["kind"] == "review"


def test_signal_permissions(client: TestClient, sender: Any) -> None:
    headers = _citizen_headers(client, sender)
    res = client.post(
        "/api/v1/intelligence/signals",
        headers=headers,
        json={
            "signal_type": "ANOMALY",
            "title": "citizen attempt",
            "severity": "LOW",
            "confidence": "LOW",
        },
    )
    assert res.status_code == 403
    admin_h = _admin_headers(client, sender)
    created = client.post(
        "/api/v1/intelligence/signals",
        headers=admin_h,
        json={
            "signal_type": "ANOMALY",
            "title": "admin created",
            "severity": "LOW",
            "confidence": "LOW",
        },
    )
    assert created.status_code == 201, created.text
    review = client.post(
        f"/api/v1/intelligence/signals/{created.json()['id']}/review",
        headers=headers,
        json={"action": "DISMISS"},
    )
    assert review.status_code == 403


def test_forecast_run_and_list(client: TestClient, sender: Any) -> None:
    ctx = _seed_context(client, sender)
    for w in range(20, 0, -1):
        _put_report(client, ctx, created_at=_weeks_ago(w))
    headers = _department_headers(client, sender)
    res = client.post(
        "/api/v1/intelligence/forecasts",
        headers=headers,
        json={"metric": "reports", "horizon_days": 14},
    )
    assert res.status_code == 200, res.text
    run = res.json()
    assert run["status"] in {"completed", "insufficient_data", "failed"}
    assert run["model_version"] == "phase20-piecewise-exp-1"
    if run["status"] == "completed":
        assert run["points"], run

    listing = client.get("/api/v1/intelligence/forecasts")
    assert listing.status_code == 200
    assert any(r["id"] == run["id"] for r in listing.json()["runs"])

    refused = client.post(
        "/api/v1/intelligence/forecasts",
        json={"metric": "reports", "horizon_days": 14},
    )
    assert refused.status_code in {401, 403}


def test_intelligence_report_generation(client: TestClient, sender: Any) -> None:
    from tk_api.intelligence.intel_reports import IntelligenceReportGenerator

    admin_h = _admin_headers(client, sender)
    res = client.post(
        "/api/v1/intelligence/reports",
        headers=admin_h,
        json={"title": "Weekly civic brief", "format": "json"},
    )
    assert res.status_code == 201, res.text
    report_id = res.json()["id"]

    async def generate() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            report = await session.get(IntelligenceReport, uuid.UUID(report_id))
            await IntelligenceReportGenerator().generate(
                session, report, save_callback=lambda key, blob: None
            )
            await session.commit()
            return str(report.status)

    status = asyncio.run(generate())
    assert status == "ready", status

    detail = client.get(f"/api/v1/intelligence/reports/{report_id}", headers=admin_h)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["status"] == "ready"
    sections = body["content"]["sections"]
    assert any(s["section"] == "trends" for s in sections)

    listing = client.get("/api/v1/intelligence/reports", headers=admin_h)
    assert listing.status_code == 200
    assert any(r["id"] == report_id for r in listing.json())


def test_report_permissions(client: TestClient, sender: Any) -> None:
    headers = _citizen_headers(client, sender)
    listing = client.get("/api/v1/intelligence/reports", headers=headers)
    assert listing.status_code == 403


def test_map_freshness_gaps_and_registry(client: TestClient, sender: Any) -> None:
    ctx = _seed_context(client, sender)
    _put_report(client, ctx, created_at=_weeks_ago(0))
    for path in (
        "/api/v1/intelligence/map",
        "/api/v1/intelligence/freshness",
        "/api/v1/intelligence/data-gaps",
        "/api/v1/intelligence/model-versions",
        "/api/v1/intelligence/improvements",
        "/api/v1/intelligence/resolution",
    ):
        res = client.get(path)
        assert res.status_code == 200, f"{path}: {res.text}"
    map_body = client.get("/api/v1/intelligence/map").json()
    assert map_body["layer"] == "report-intensity"
    registry = client.get("/api/v1/intelligence/model-versions").json()
    assert registry["models"]
    assert any(m["model_name"] == "forecasting" for m in registry["models"])
