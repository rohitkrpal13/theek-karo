"""Unit and API tests for Phase 9 GIS, spatial viewport queries, and map intelligence."""

from __future__ import annotations

import asyncio
import uuid

from starlette.testclient import TestClient

from tk_api.civic.models import Category
from tk_api.core.db import create_session_factory
from tk_api.geography.models import Geography, GeographyType
from tk_api.institutions.models import Institution, InstitutionType
from tk_api.provenance.models import ExternalSource
from tk_api.reports.models import Report
from tk_api.users.models import User


def _seed_map_data(client: TestClient) -> dict[str, str]:
    """Seed sample external source, user, geography, institution, category, and reports."""

    async def seed() -> dict[str, str]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # 1. External Source & User
            src = ExternalSource(
                name="NIC Jaipur Portal",
                publisher="National Informatics Centre",
                url="https://jaipur.rajasthan.gov.in",
                license="Open Government Data",
            )
            user = User(
                email=f"reporter_{uuid.uuid4().hex[:6]}@example.com",
                display_name="Citizen Reporter",
                status="active",
            )
            session.add_all([src, user])
            await session.flush()

            # 2. Geography Type & Node
            gtype = GeographyType(
                code=f"district_{uuid.uuid4().hex[:6]}",
                name_key="geography.district",
                sort_order=2,
            )
            session.add(gtype)
            await session.flush()

            geo = Geography(
                type_id=gtype.id,
                country_code="IN",
                name="Jaipur District",
                normalized_name="jaipur district",
            )
            session.add(geo)
            await session.flush()

            # 3. Institution Type & Institution
            itype = InstitutionType(
                code=f"school_{uuid.uuid4().hex[:6]}",
                name_key="institution.school",
            )
            session.add(itype)
            await session.flush()

            inst = Institution(
                institution_type_id=itype.id,
                geography_id=geo.id,
                name="Govt Senior Secondary School Jaipur",
                normalized_name="govt senior secondary school jaipur",
                official_identifier=f"SCH-JPR-{uuid.uuid4().hex[:6]}",
                operational_status="active",
                source_id=src.id,
                meta={"location": {"type": "Point", "coordinates": [75.7873, 26.9124]}},
            )
            session.add(inst)
            await session.flush()

            # 4. Category
            cat_slug = f"education_{uuid.uuid4().hex[:6]}"
            cat = Category(
                slug=cat_slug,
                icon="school",
                form_schema={"type": "object", "properties": {}},
                verification_policy={},
                attachment_rules={},
                default_locale_keys={},
                form_schema_version=1,
                is_active=True,
            )
            session.add(cat)
            await session.flush()

            # 5. Reports
            rep1 = Report(
                ticket_no=f"TK-20260817-{uuid.uuid4().hex[:6]}",
                reporter_id=user.id,
                category_id=cat.id,
                institution_id=inst.id,
                title="Classroom roof leaking during monsoon",
                description="Water dripping in Class 4 room causing electrical danger.",
                severity="high",
                visibility="public",
                source="citizen",
                location={"type": "Point", "coordinates": [75.7875, 26.9125]},
                location_accuracy_m=12,
                status="submitted",
                info_class="CITIZEN_REPORT",
                trust_score=0.15,
                fields={},
            )
            rep2 = Report(
                ticket_no=f"TK-20260817-{uuid.uuid4().hex[:6]}",
                reporter_id=user.id,
                category_id=cat.id,
                institution_id=inst.id,
                title="Broken boundary wall near sports ground",
                description="Boundary wall collapsed allowing stray animals inside.",
                severity="medium",
                visibility="public",
                source="citizen",
                location={"type": "Point", "coordinates": [75.7880, 26.9130]},
                location_accuracy_m=15,
                status="verified",
                info_class="COMMUNITY_VERIFIED",
                trust_score=0.45,
                fields={},
            )
            session.add_all([rep1, rep2])
            await session.commit()

            return {
                "geo_id": str(geo.id),
                "inst_id": str(inst.id),
                "cat_slug": cat_slug,
                "rep1_id": str(rep1.id),
            }

    return asyncio.run(seed())


def test_map_institutions_bbox(client: TestClient) -> None:
    """Test viewport bounding-box query for institutions."""
    _seed_map_data(client)
    resp = client.get(
        "/api/v1/gis/map/institutions",
        params={
            "min_lon": 75.0,
            "min_lat": 26.0,
            "max_lon": 76.0,
            "max_lat": 27.0,
        },
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert any(it["name"] == "Govt Senior Secondary School Jaipur" for it in items)
    match = next(it for it in items if it["name"] == "Govt Senior Secondary School Jaipur")
    assert match["location"]["coordinates"] == [75.7873, 26.9124]


def test_map_reports_bbox(client: TestClient) -> None:
    """Test viewport bounding-box query for reports."""
    data = _seed_map_data(client)
    resp = client.get(
        "/api/v1/gis/map/reports",
        params={
            "min_lon": 75.7,
            "min_lat": 26.8,
            "max_lon": 75.9,
            "max_lat": 27.0,
            "category_slug": data["cat_slug"],
        },
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2
    titles = [it["title"] for it in items]
    assert "Classroom roof leaking during monsoon" in titles


def test_map_bbox_validation(client: TestClient) -> None:
    """Test validation errors for invalid or overly large bounding boxes."""
    # min_lon > max_lon
    resp1 = client.get(
        "/api/v1/gis/map/institutions",
        params={"min_lon": 77.0, "min_lat": 26.0, "max_lon": 75.0, "max_lat": 27.0},
    )
    assert resp1.status_code == 422

    # Area > 25.0 deg^2 (e.g. 10 deg x 10 deg)
    resp2 = client.get(
        "/api/v1/gis/map/reports",
        params={"min_lon": 60.0, "min_lat": 10.0, "max_lon": 80.0, "max_lat": 30.0},
    )
    assert resp2.status_code == 422


def test_map_nearby_radius(client: TestClient) -> None:
    """Test nearby radius search around coordinate."""
    _seed_map_data(client)
    resp = client.get(
        "/api/v1/gis/map/nearby",
        params={
            "lat": 26.9124,
            "lng": 75.7873,
            "radius_m": 5000,
            "domain": "all",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["center"]["lat"] == 26.9124
    assert len(body["institutions"]) >= 1
    assert len(body["reports"]) >= 1


def test_map_summary(client: TestClient) -> None:
    """Test map summary metrics aggregation."""
    data = _seed_map_data(client)
    resp = client.get(
        "/api/v1/gis/map/summary",
        params={"geography_id": data["geo_id"]},
    )
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["geography_name"] == "Jaipur District"
    assert summary["institution_count"] >= 1
    assert summary["report_count"] >= 2
    assert summary["severity_breakdown"]["high"] >= 1
    assert summary["data_coverage_pct"] >= 50.0


def test_forward_geocode(client: TestClient) -> None:
    """Test forward geocoding with coordinates, place name, and institution."""
    _seed_map_data(client)

    # 1. Coordinates query
    resp_coord = client.get("/api/v1/gis/geocode/forward", params={"q": "26.9124, 75.7873"})
    assert resp_coord.status_code == 200
    results1 = resp_coord.json()["results"]
    assert len(results1) >= 1
    assert results1[0]["kind"] == "coordinate"

    # 2. Geography text search
    resp_geo = client.get("/api/v1/gis/geocode/forward", params={"q": "Jaipur"})
    assert resp_geo.status_code == 200
    results2 = resp_geo.json()["results"]
    assert any(r["label"] == "Jaipur District" for r in results2)

    # 3. Institution search
    resp_inst = client.get("/api/v1/gis/geocode/forward", params={"q": "Senior Secondary School"})
    assert resp_inst.status_code == 200
    results3 = resp_inst.json()["results"]
    assert any("Govt Senior Secondary School" in r["label"] for r in results3)
