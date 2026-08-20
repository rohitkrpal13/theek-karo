from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from tests.conftest import _register_and_verify
from tk_api.civic.models import Category
from tk_api.core.db import create_session_factory
from tk_api.geography.models import Geography, GeographyType
from tk_api.govdata.connectors import (
    ConnectorSecurityError,
    UDISEPlusSchoolConnector,
    sanitize_csv_cell,
    scrub_pii,
    validate_source_url,
)
from tk_api.govdata.matching import calculate_name_similarity
from tk_api.govdata.models import GovDataset
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


def _seed_govdata_fixtures(client: TestClient) -> dict[str, str]:
    """Seed test external source, institution, data source, dataset, category, and reports."""

    async def seed() -> dict[str, str]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # 1. Admin User
            admin_user = User(
                email=f"reporter_{uuid.uuid4().hex[:6]}@example.com",
                display_name="Citizen Reporter",
                status="active",
            )
            session.add(admin_user)
            await session.flush()

            # 2. External & Data Sources
            ext_src = ExternalSource(
                name="UDISE+ Education Portal",
                publisher="Ministry of Education",
                url="https://udiseplus.gov.in",
                license="Open Government Data (OGD)",
                version="2026-07",
            )
            data_src = DataSource(
                name="UDISE+ School Infrastructure",
                source_type="official_dataset",
                publisher="Ministry of Education",
                url="https://udiseplus.gov.in/datasets",
                license="OGD-India",
                version="2026-07",
                confidence_base=0.9,
                verification_state="official",
            )
            session.add_all([ext_src, data_src])
            await session.flush()

            # 3. Gov Dataset
            dataset = GovDataset(
                name="udise_plus_school",
                data_source_id=data_src.id,
                publisher="Ministry of Education",
                license="OGD",
                version="2026-07",
                status="active",
                url="https://udiseplus.gov.in/datasets/schools_2026.json",
            )
            session.add(dataset)
            await session.flush()

            # 4. Geography & Institution
            gtype = GeographyType(
                code=f"district_{uuid.uuid4().hex[:6]}", name_key="geography.district", sort_order=2
            )
            itype = InstitutionType(
                code=f"school_{uuid.uuid4().hex[:6]}", name_key="institution.school"
            )
            session.add_all([gtype, itype])
            await session.flush()

            geo = Geography(
                type_id=gtype.id,
                country_code="IN",
                name="Jaipur Rural",
                normalized_name="jaipur rural",
            )
            session.add(geo)
            await session.flush()

            inst = Institution(
                institution_type_id=itype.id,
                geography_id=geo.id,
                name="Govt Senior Secondary School Jaipur",
                normalized_name="govt senior secondary school jaipur",
                official_identifier="SCH-JPR-101",
                operational_status="active",
                source_id=ext_src.id,
                source_identifier="UDISE-0812001",
                meta={
                    "canonical_data": {
                        "sanctioned_teachers": 14,
                        "working_teachers": 12,
                        "vacancies": 2,
                        "toilets_total": 6,
                        "drinking_water_available": True,
                        "electricity_available": True,
                    }
                },
            )
            session.add(inst)
            await session.flush()

            # 5. Category & Reports
            cat = Category(
                slug=f"education_{uuid.uuid4().hex[:6]}",
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

            rep1 = Report(
                ticket_no=f"TK-{uuid.uuid4().hex[:6]}",
                reporter_id=admin_user.id,
                category_id=cat.id,
                institution_id=inst.id,
                title="Teacher shortage in Class 9 and 10",
                description=(
                    "Only 4 working teachers present. Mathematics teacher absent for months."
                ),
                severity="high",
                visibility="public",
                source="citizen",
                location={"type": "Point", "coordinates": [75.78, 26.91]},
                location_accuracy_m=10,
                status="submitted",
                info_class="CITIZEN_REPORT",
                trust_score=0.2,
                fields={},
            )
            rep2 = Report(
                ticket_no=f"TK-{uuid.uuid4().hex[:6]}",
                reporter_id=admin_user.id,
                category_id=cat.id,
                institution_id=inst.id,
                title="Staff shortage affecting science laboratory",
                description="No lab assistant or physics teacher available.",
                severity="high",
                visibility="public",
                source="citizen",
                location={"type": "Point", "coordinates": [75.78, 26.91]},
                location_accuracy_m=10,
                status="verified",
                info_class="COMMUNITY_VERIFIED",
                trust_score=0.45,
                fields={},
            )
            session.add_all([rep1, rep2])
            await session.commit()

            return {
                "admin_id": str(admin_user.id),
                "inst_id": str(inst.id),
                "dataset_id": str(dataset.id),
                "data_source_id": str(data_src.id),
            }

    return asyncio.run(seed())


# -----------------------------------------------------------------------------
# 1. Security & Connector Tests
# -----------------------------------------------------------------------------


def test_ssrf_url_validation() -> None:
    """Test SSRF guard blocks private IPs, metadata endpoints, and non-HTTP schemes."""
    # Valid official domain
    assert (
        validate_source_url("https://data.gov.in/resource/schools.json")
        == "https://data.gov.in/resource/schools.json"
    )

    with pytest.raises(ConnectorSecurityError):
        validate_source_url("http://127.0.0.1:8000/data.json")

    with pytest.raises(ConnectorSecurityError):
        validate_source_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ConnectorSecurityError):
        validate_source_url("http://192.168.1.50/data.csv")


def test_csv_formula_sanitization_and_pii() -> None:
    """Test CSV formula escape and Aadhaar/ID redaction."""
    assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("Normal Text") == "Normal Text"

    raw_text = "Principal Aadhaar: 1234 5678 9012, verified."
    assert scrub_pii(raw_text) == "Principal Aadhaar: [REDACTED_ID], verified."


def test_connector_normalization() -> None:
    """Test UDISE+ school connector normalizes canonical attributes."""
    connector = UDISEPlusSchoolConnector()
    sample = {
        "school_name": "Govt Higher Secondary School Jaipur",
        "udise_code": "0812001",
        "total_students": 450,
        "sanctioned_teachers": 16,
        "working_teachers": 14,
        "vacancies": 2,
        "toilets_total": 8,
        "drinking_water": True,
    }
    assert connector.validate_schema(sample)
    norm = connector.normalize_record(sample)
    assert norm["name"] == "Govt Higher Secondary School Jaipur"
    assert norm["official_identifier"] == "0812001"
    assert norm["canonical_data"]["sanctioned_teachers"] == 16
    assert norm["canonical_data"]["total_students"] == 450


def test_name_similarity_metric() -> None:
    """Test token similarity calculation."""
    sim1 = calculate_name_similarity(
        "Govt Senior Secondary School Jaipur", "Government Senior Secondary School Jaipur"
    )
    assert sim1 >= 0.70

    sim2 = calculate_name_similarity("District Civil Hospital", "Police Station Kotwali")
    assert sim2 == 0.0


# -----------------------------------------------------------------------------
# 2. API & Discrepancy Tests
# -----------------------------------------------------------------------------


def test_get_official_data_endpoint(client: TestClient) -> None:
    """Test GET /api/v1/institutions/{id}/official-data returns canonical fields and provenance."""
    data = _seed_govdata_fixtures(client)
    inst_id = data["inst_id"]

    resp = client.get(f"/api/v1/institutions/{inst_id}/official-data")
    assert resp.status_code == 200
    body = resp.json()
    assert body["institution_id"] == inst_id
    assert body["official_identifier"] == "SCH-JPR-101"
    assert body["canonical_data"]["sanctioned_teachers"] == 14
    assert body["provenance"]["publisher"] == "Ministry of Education"
    assert "Published" in body["freshness_label"] or "active" in body["freshness_label"]


def test_get_discrepancies_endpoint(client: TestClient) -> None:
    """Test GET /api/v1/institutions/{id}/discrepancies detects staffing discrepancy."""
    data = _seed_govdata_fixtures(client)
    inst_id = data["inst_id"]

    resp = client.get(f"/api/v1/institutions/{inst_id}/discrepancies")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1

    staff_disc = next(d for d in items if d["resource_key"] == "staffing")
    assert staff_disc["discrepancy_state"] == "POSSIBLE_DISCREPANCY"
    assert (
        "discrepancy" in staff_disc["ai_finding"].lower()
        or "reports" in staff_disc["ai_finding"].lower()
    )


def test_get_comparison_endpoint(client: TestClient) -> None:
    """Test GET /api/v1/institutions/{id}/comparison returns resource matrix."""
    data = _seed_govdata_fixtures(client)
    inst_id = data["inst_id"]

    resp = client.get(f"/api/v1/institutions/{inst_id}/comparison")
    assert resp.status_code == 200
    body = resp.json()
    assert body["institution_id"] == inst_id
    assert len(body["comparison_matrix"]) >= 3
    assert body["overall_discrepancy_state"] == "POSSIBLE_DISCREPANCY"

    teacher_row = next(
        r for r in body["comparison_matrix"] if r["resource_key"] == "sanctioned_teachers"
    )
    assert teacher_row["official_value"] == 14
    assert teacher_row["discrepancy_state"] == "POSSIBLE_DISCREPANCY"


def test_data_sources_registry(client: TestClient) -> None:
    """Test listing and retrieving official data sources."""
    data = _seed_govdata_fixtures(client)
    src_id = data["data_source_id"]

    # List sources
    resp = client.get("/api/v1/govdata/sources")
    assert resp.status_code == 200
    items = resp.json()
    assert any(s["id"] == src_id for s in items)

    # Get single source
    resp_detail = client.get(f"/api/v1/govdata/sources/{src_id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["publisher"] == "Ministry of Education"


def test_import_job_execution(client: TestClient, sender: Any) -> None:
    """Test trigger import job matching against existing institution."""
    data = _seed_govdata_fixtures(client)
    dataset_id = data["dataset_id"]

    headers = _admin_headers(client, sender)
    payload = {
        "dataset_id": dataset_id,
        "dry_run": False,
        "raw_payload": {
            "records": [
                {
                    "school_name": "Govt Senior Secondary School Jaipur",
                    "udise_code": "SCH-JPR-101",
                    "total_students": 520,
                    "sanctioned_teachers": 18,
                    "working_teachers": 16,
                }
            ]
        },
    }

    resp = client.post("/api/v1/govdata/imports", json=payload, headers=headers)
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "completed"
    assert body["rows_imported"] == 1


def test_data_quality_report(client: TestClient, sender: Any) -> None:
    """Test GET /api/v1/govdata/data-quality returns platform quality statistics."""
    _seed_govdata_fixtures(client)
    headers = _admin_headers(client, sender)
    resp = client.get("/api/v1/govdata/data-quality", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_datasets"] >= 1
    assert body["total_institutions"] >= 1
