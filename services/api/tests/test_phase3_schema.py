"""Phase 3 data-layer unit tests (SQLite): new-domain relationships,
constraints, and policies across the full registered schema."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.identity.models import Permission, RolePermission
from tk_api.institutions.models import InstitutionAttributeDefinition, InstitutionType
from tk_api.localization.models import ContentTranslation
from tk_api.resolution.models import ReputationEvent, ReputationPolicy, Subscription
from tk_api.users.models import Role


async def _query(client, sql: str) -> list:  # type: ignore[no-untyped-def]
    factory = create_session_factory(client.app.state.engine)
    async with factory() as session:
        rows = await session.execute(text(sql))
        return [row[0] for row in rows]


class TestIdentityPermissions:
    def test_permission_unique_and_role_link(self, client) -> None:  # type: ignore[no-untyped-def]
        async def exercise() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                session.add(Permission(code="reports.create", description="create reports"))
                await session.commit()
                with pytest.raises(IntegrityError):
                    session.add(Permission(code="reports.create", description="duplicate"))
                    await session.commit()
                    await session.rollback()

        asyncio.run(exercise())

        codes = asyncio.run(_query(client, "SELECT code FROM permissions ORDER BY code"))
        assert codes == ["reports.create"]

        async def link() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                role = (
                    await session.execute(select(Role).where(Role.code == "admin"))
                ).scalar_one()
                permission = (
                    await session.execute(
                        select(Permission).where(Permission.code == "reports.create")
                    )
                ).scalar_one()
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))
                await session.commit()
                with pytest.raises(IntegrityError):
                    session.add(RolePermission(role_id=role.id, permission_id=permission.id))
                    await session.commit()

        asyncio.run(link())


class TestInstitutionsAttributes:
    def test_attribute_definition_value_types(self, client) -> None:  # type: ignore[no-untyped-def]
        async def exercise() -> dict[str, str]:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                school = InstitutionType(
                    code="school_unit", name_key="institution.type.school", is_active=True
                )
                session.add(school)
                await session.flush()
                session.add(
                    InstitutionAttributeDefinition(
                        institution_type_id=school.id,
                        code="student_count",
                        value_type="integer",
                        required=True,
                        unit="students",
                    )
                )
                await session.commit()
                return {"type_id": str(school.id)}

        result = asyncio.run(exercise())
        assert uuid.UUID(result["type_id"])


class TestTranslations:
    def test_content_translation_insert_and_read(self, client) -> None:  # type: ignore[no-untyped-def]
        content_id = uuid.uuid4()

        async def exercise() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                session.add(
                    ContentTranslation(
                        content_type="report",
                        content_id=content_id,
                        locale="hi",
                        original_language="en",
                        title="एक रिपोर्ट",
                        body="विवरण",
                        translation_source="ai",
                        status="pending",
                    )
                )
                await session.commit()

        asyncio.run(exercise())
        rows = asyncio.run(_orm_locales(client, content_id))
        assert rows == ["hi"]


class TestReputation:
    def test_policies_and_event_append(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876547001")

        async def exercise() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                session.add(ReputationPolicy(event_kind="valid_report", delta=10))
                session.add(ReputationPolicy(event_kind="abuse", delta=-20))
                await session.commit()

        asyncio.run(exercise())
        policies = asyncio.run(
            _query(client, "SELECT event_kind FROM reputation_policies ORDER BY event_kind")
        )
        assert "valid_report" in policies and "abuse" in policies

        async def record() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                policy = (
                    await session.execute(
                        select(ReputationPolicy).where(
                            ReputationPolicy.event_kind == "valid_report"
                        )
                    )
                ).scalar_one()
                session.add(
                    ReputationEvent(
                        user_id=uuid.UUID(tokens["user"]["id"]),
                        event_kind=policy.event_kind,
                        delta=policy.delta,
                    )
                )
                await session.commit()

        asyncio.run(record())


class TestSubscriptions:
    def test_valid_subscription_saves(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        tokens = _register_and_verify(client, sender, "9876547002")

        async def exercise() -> uuid.UUID:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                sub = Subscription(
                    user_id=uuid.UUID(tokens["user"]["id"]),
                    subscriber_kind="category",
                    category_id=uuid.uuid4(),
                )
                session.add(sub)
                await session.commit()
                return sub.id

        assert asyncio.run(exercise())  # positive path; the single-target CHECK
        # is enforced on Postgres (verified by the Phase-3 integration suite)


async def _orm_locales(client, content_id: uuid.UUID) -> list[str]:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    factory = create_session_factory(client.app.state.engine)
    async with factory() as session:
        rows = await session.execute(
            select(ContentTranslation.locale).where(ContentTranslation.content_id == content_id)
        )
        return [row[0] for row in rows]
