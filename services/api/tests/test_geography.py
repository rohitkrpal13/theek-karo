"""Tests for Geography hierarchy, search, and navigation endpoints."""

from __future__ import annotations

import asyncio
import uuid

from starlette.testclient import TestClient

from tk_api.core.db import create_session_factory
from tk_api.geography.models import Geography, GeographyTranslation, GeographyType


def _seed_geography(client: TestClient) -> dict[str, uuid.UUID]:
    async def seed() -> dict[str, uuid.UUID]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            country_type = GeographyType(code="country", name_key="geo.country", sort_order=1)
            state_type = GeographyType(code="state", name_key="geo.state", sort_order=2)
            district_type = GeographyType(code="district", name_key="geo.district", sort_order=3)
            session.add_all([country_type, state_type, district_type])
            await session.flush()

            india = Geography(
                type_id=country_type.id,
                name="India",
                normalized_name="india",
                country_code="IND",
                official_identifier="IN",
            )
            session.add(india)
            await session.flush()

            bihar = Geography(
                type_id=state_type.id,
                name="Bihar",
                normalized_name="bihar",
                parent_id=india.id,
                country_code="IND",
                official_identifier="IN-BR",
            )
            session.add(bihar)
            await session.flush()

            patna = Geography(
                type_id=district_type.id,
                name="Patna",
                normalized_name="patna",
                parent_id=bihar.id,
                country_code="IND",
                official_identifier="IN-BR-PAT",
            )
            session.add(patna)
            await session.flush()

            trans = GeographyTranslation(
                geography_id=bihar.id,
                locale="hi",
                name="बिहार",
                transliteration="Bihar",
            )
            session.add(trans)
            await session.commit()

            return {
                "country_type": country_type.id,
                "state_type": state_type.id,
                "district_type": district_type.id,
                "india": india.id,
                "bihar": bihar.id,
                "patna": patna.id,
            }

    return asyncio.run(seed())


def test_geography_types_list(client: TestClient) -> None:
    _seed_geography(client)
    res = client.get("/api/v1/geography/types")
    assert res.status_code == 200
    types = res.json()
    assert len(types) >= 3
    codes = [t["code"] for t in types]
    assert "country" in codes
    assert "state" in codes
    assert "district" in codes


def test_geography_list_and_filter(client: TestClient) -> None:
    ids = _seed_geography(client)
    res = client.get(f"/api/v1/geography?type_id={ids['state_type']}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(g["name"] == "Bihar" for g in data["items"])


def test_geography_detail_and_translations(client: TestClient) -> None:
    ids = _seed_geography(client)
    res = client.get(f"/api/v1/geography/{ids['bihar']}")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Bihar"
    assert data["parent"]["name"] == "India"
    assert len(data["translations"]) == 1
    assert data["translations"][0]["name"] == "बिहार"


def test_geography_children_and_ancestors(client: TestClient) -> None:
    ids = _seed_geography(client)
    # Children of Bihar -> Patna
    res_children = client.get(f"/api/v1/geography/{ids['bihar']}/children")
    assert res_children.status_code == 200
    children = res_children.json()
    assert any(c["name"] == "Patna" for c in children)

    # Ancestors of Patna -> Bihar, India
    res_ancestors = client.get(f"/api/v1/geography/{ids['patna']}/ancestors")
    assert res_ancestors.status_code == 200
    ancestors = res_ancestors.json()
    ancestor_names = [a["name"] for a in ancestors]
    assert "Bihar" in ancestor_names
    assert "India" in ancestor_names


def test_geography_search(client: TestClient) -> None:
    _seed_geography(client)
    res = client.get("/api/v1/geography/search?q=pat")
    assert res.status_code == 200
    items = res.json()
    assert any(g["name"] == "Patna" for g in items)
