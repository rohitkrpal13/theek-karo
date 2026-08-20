"""Tests for Unified Search API across reports, institutions, geography, and categories."""

from __future__ import annotations

import asyncio
import uuid

from starlette.testclient import TestClient

from tk_api.core.db import create_session_factory
from tk_api.geography.models import Geography, GeographyType
from tk_api.institutions.models import Institution, InstitutionType
from tk_api.provenance.models import ExternalSource


def _seed_search_data(client: TestClient) -> None:
    async def seed() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # Geography
            gtype = GeographyType(code=f"city_{uuid.uuid4().hex[:4]}", name_key="geo.city")
            session.add(gtype)
            await session.flush()
            geo = Geography(
                type_id=gtype.id, name="Varanasi", normalized_name="varanasi", country_code="IND"
            )
            session.add(geo)

            # Institution
            source = ExternalSource(
                name="Public Dir",
                publisher="Government Directory",
                url="https://directory.gov.in",
            )
            session.add(source)
            await session.flush()
            itype = InstitutionType(code=f"hosp_{uuid.uuid4().hex[:4]}", name_key="inst.hospital")
            session.add(itype)
            await session.flush()
            inst = Institution(
                institution_type_id=itype.id,
                name="Varanasi District Hospital",
                normalized_name="varanasi district hospital",
                source_id=source.id,
                address="Chowk, Varanasi",
            )
            session.add(inst)
            await session.commit()

    asyncio.run(seed())


def test_unified_search_all(client: TestClient) -> None:
    _seed_search_data(client)
    res = client.get("/api/v1/search?q=Varanasi")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    domains = [item["domain"] for item in data["items"]]
    assert "geography" in domains
    assert "institutions" in domains


def test_unified_search_filtered_domain(client: TestClient) -> None:
    _seed_search_data(client)
    res = client.get("/api/v1/search?q=Varanasi&domain=geography")
    assert res.status_code == 200
    data = res.json()
    assert all(item["domain"] == "geography" for item in data["items"])
