"""Tests for Institutions Digital Twin CRUD, types, and search endpoints."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from starlette.testclient import TestClient

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.institutions.models import (
    InstitutionAttributeDefinition,
    InstitutionType,
)
from tk_api.provenance.models import ExternalSource
from tk_api.users.models import Role, User, UserRole


def _grant(client: TestClient, user_id: str, code: str) -> None:
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            if user and role:
                session.add(UserRole(user_id=user.id, role_id=role.id))
                await session.commit()

    asyncio.run(grant())


def _user(client: TestClient, sender, phone: str) -> tuple[str, dict[str, str]]:
    tokens = _register_and_verify(client, sender, phone)
    return tokens["user"]["id"], {"Authorization": f"Bearer {tokens['access_token']}"}


def _seed_institution_type_and_source(client: TestClient) -> dict[str, uuid.UUID]:
    async def seed() -> dict[str, uuid.UUID]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            source = ExternalSource(
                name="UDISE+ Directory",
                publisher="Ministry of Education",
                url="https://udiseplus.gov.in",
            )
            session.add(source)
            await session.flush()

            school_type = InstitutionType(
                code=f"school_{uuid.uuid4().hex[:6]}",
                name_key="inst.school",
                attribute_schema={"type": "object"},
            )
            session.add(school_type)
            await session.flush()

            attr_def = InstitutionAttributeDefinition(
                institution_type_id=school_type.id,
                code="total_students",
                value_type="integer",
            )
            session.add(attr_def)
            await session.commit()

            return {
                "source_id": source.id,
                "school_type_id": school_type.id,
                "attr_def_id": attr_def.id,
            }

    return asyncio.run(seed())


def test_institution_types_list(client: TestClient) -> None:
    ids = _seed_institution_type_and_source(client)
    res = client.get("/api/v1/institutions/types")
    assert res.status_code == 200
    types = res.json()
    assert len(types) >= 1
    assert any(t["id"] == str(ids["school_type_id"]) for t in types)


def test_institution_crud(client: TestClient, sender) -> None:
    ids = _seed_institution_type_and_source(client)
    user_id, citizen_headers = _user(client, sender, "9876543201")
    _grant(client, user_id, "official")

    # 1. Create institution
    payload = {
        "institution_type_id": str(ids["school_type_id"]),
        "name": "Government High School Phulwari",
        "official_identifier": f"SCH-{uuid.uuid4().hex[:6]}",
        "address": "Phulwari Sharif, Patna, Bihar",
        "contact_phone": "+916122554433",
        "source_id": str(ids["source_id"]),
    }
    create_res = client.post("/api/v1/institutions", json=payload, headers=citizen_headers)
    assert create_res.status_code == 201
    inst_data = create_res.json()
    inst_id = inst_data["id"]
    assert inst_data["name"] == payload["name"]

    # 2. Get detail
    detail_res = client.get(f"/api/v1/institutions/{inst_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["name"] == payload["name"]
    assert detail_data["type"] is not None

    # 3. Update
    patch_res = client.patch(
        f"/api/v1/institutions/{inst_id}",
        json={"operational_status": "active", "website": "https://school.bihar.gov.in"},
        headers=citizen_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["website"] == "https://school.bihar.gov.in"

    # 4. List with query filter
    list_res = client.get("/api/v1/institutions?q=Phulwari")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1
