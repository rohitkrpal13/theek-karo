"""Dev/test demo accounts for E2E journeys and local smoke testing.

Usage: uv run python scripts/seed_demo_data.py

Creates (idempotently) the accounts used by the Playwright journeys and by
local development:

    admin@theekkar.test     admin
    moderator@theekkar.test moderator
    officer@theekkar.test   official + department_representative
    citizen@theekkar.test   citizen

All share the password ``DevPassw0rd!2026`` (dev-only) and are instantly
active with phone+email verified. The script **refuses to run** when the
environment is prod/staging — demo credentials must never exist there.

Journeys these unlock (e2e/core-flows.spec.ts):
  Journey 3 (moderator):   review report → verify
  Journey 4 (authority):   view assigned case → respond → mark resolved
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

import tk_api.core.models  # noqa: F401  # register the full schema (FK resolution)
from tk_api.auth.security import hash_password
from tk_api.core.config import Settings, get_settings
from tk_api.core.db import create_engine, create_session_factory
from tk_api.departments.models import Department, DepartmentUser, DepartmentType
from tk_api.users.models import Role, User, UserRole

DEMO_ACCOUNTS = [
    {"email": "admin@theekkar.test", "display_name": "Demo Admin", "roles": ["admin"]},
    {
        "email": "moderator@theekkar.test",
        "display_name": "Demo Moderator",
        "roles": ["moderator"],
    },
    {
        "email": "officer@theekkar.test",
        "display_name": "Demo Officer",
        "roles": ["official", "department_representative", "department_manager"],
    },
    {"email": "citizen@theekkar.test", "display_name": "Demo Citizen", "roles": ["citizen"]},
]

DEMO_PASSWORD = "DevPassw0rd!2026"


async def seed(settings: Settings) -> None:
    if settings.is_production:
        raise RuntimeError(
            "seed_demo_data refuses to run in prod/staging (demo credentials "
            "must never exist outside dev/test environments)."
        )
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        role_by_code = {
            code: role
            for code, role in ((r.code, r) for r in (await session.scalars(select(Role))).all())
        }
        missing = [c for acc in DEMO_ACCOUNTS for c in acc["roles"] if c not in role_by_code]
        if missing:
            raise RuntimeError(
                f"missing role codes in database: {sorted(set(missing))} — run alembic upgrade head"
            )
        now = datetime.now(UTC)
        created = 0
        for account in DEMO_ACCOUNTS:
            user = await session.scalar(select(User).where(User.email == account["email"]))
            if user is None:
                user = User(
                    email=account["email"],
                    display_name=account["display_name"],
                    password_hash=hash_password(DEMO_PASSWORD),
                    phone_verified_at=now,
                    email_verified_at=now,
                    status="active",
                )
                session.add(user)
                await session.flush()
                created += 1
            for code in account["roles"]:
                exists = await session.scalar(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == role_by_code[code].id,
                    )
                )
                if exists is None:
                    session.add(
                        UserRole(user_id=user.id, role_id=role_by_code[code].id, granted_at=now)
                    )
        await session.commit()

        # Demo department + officer membership so the officer can own cases
        # (case scope requires an explicit department membership).
        dept = await session.scalar(select(Department).where(Department.slug == "demo-development"))
        if dept is None:
            dept_type = await session.scalar(
                select(DepartmentType).limit(1)
            )
            if dept_type is None:
                raise RuntimeError(
                    "no department types seeded — run alembic upgrade head and seed_civic first"
                )
            dept = Department(
                slug="demo-development",
                name="Demo Development Department",
                department_type_id=dept_type.id,
                description="Auto-created by seed_demo_data for development journeys",
            )
            session.add(dept)
            await session.flush()
        officer = await session.scalar(select(User).where(User.email == "officer@theekkar.test"))
        membership = await session.scalar(
            select(DepartmentUser).where(
                DepartmentUser.user_id == officer.id,
                DepartmentUser.department_id == dept.id,
            )
        )
        if membership is None:
            session.add(
                DepartmentUser(
                    user_id=officer.id,
                    department_id=dept.id,
                    role_in_department="manager",
                    is_active=True,
                )
            )
        await session.commit()
        print(
            f"seed_demo_data: {created} accounts created; demo password: {DEMO_PASSWORD} "
            f"(dev-only, never enabled in prod/staging)"
        )
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dev/test demo accounts")
    parser.add_argument("--database-url", default=None, help="Override TK_DATABASE_URL")
    args = parser.parse_args()
    settings = get_settings()
    if args.database_url:
        settings = Settings(_env_file=None, database_url=args.database_url)
        settings.validate_production_readiness()
    asyncio.run(seed(settings))


if __name__ == "__main__":
    main()