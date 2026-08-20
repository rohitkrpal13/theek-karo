"""Idempotent civic seed: the PRD's planned initial categories (PRD §7).

Usage: uv run python scripts/seed_civic.py [--database-url URL]

Inserts categories that are missing (matched by slug) and refreshes the managed
seed config (form schemas/version) for known slugs when the seed spec advances —
e.g. Phase 5 gave ``school``/``road`` real field schemas. Safe to run repeatedly
(dev + staging).
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from tk_api.civic.models import Category
from tk_api.core.config import Settings
from tk_api.core.db import create_engine, create_session_factory

# PRD §7: planned initial categories (all onboarded as data, in priority order).
INITIAL_CATEGORIES: list[dict[str, Any]] = [
    {"slug": "school", "icon": "school", "label_key": "category.school"},
    {"slug": "hospital", "icon": "hospital", "label_key": "category.hospital"},
    {"slug": "road", "icon": "road", "label_key": "category.road"},
    {"slug": "water", "icon": "water", "label_key": "category.water"},
    {"slug": "sanitation", "icon": "sanitation", "label_key": "category.sanitation"},
    {"slug": "public_transport", "icon": "bus", "label_key": "category.public_transport"},
    {"slug": "police_station", "icon": "shield", "label_key": "category.police_station"},
    {"slug": "court", "icon": "gavel", "label_key": "category.court"},
    {"slug": "public_facility", "icon": "park", "label_key": "category.public_facility"},
    {"slug": "panchayat", "icon": "building", "label_key": "category.panchayat"},
    {"slug": "municipal_service", "icon": "building", "label_key": "category.municipal_service"},
    {"slug": "government_office", "icon": "landmark", "label_key": "category.government_office"},
    {"slug": "bridge", "icon": "bridge", "label_key": "category.bridge"},
    {"slug": "other", "icon": "flag", "label_key": "category.other"},
]

FORM_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}

# Per-category schemas for the M1 pilot categories (Phase 5 pre-step). The API
# contract keeps ``title``/``description`` on the report row (API.md §5);
# ``fields`` carries only category-specific data, so schemas list those only.
PER_CATEGORY_FORM_SCHEMAS: dict[str, dict[str, Any]] = {
    "school": {
        "type": "object",
        "required": ["issue_area"],
        "properties": {
            "issue_area": {
                "type": "string",
                "enum": [
                    "classroom",
                    "washroom",
                    "water",
                    "electricity",
                    "playground",
                    "furniture",
                    "staff",
                    "other",
                ],
            },
            "class_rooms_affected": {"type": "integer", "minimum": 1, "maximum": 100},
            "children_affected": {"type": "integer", "minimum": 1, "maximum": 5000},
        },
        "additionalProperties": False,
    },
    "road": {
        "type": "object",
        "required": ["issue_type"],
        "properties": {
            "issue_type": {
                "type": "string",
                "enum": [
                    "pothole",
                    "damaged_stretch",
                    "missing_signage",
                    "streetlight",
                    "waterlogging",
                    "trees_obstructing",
                    "other",
                ],
            },
            "lanes_affected": {"type": "integer", "minimum": 1, "maximum": 8},
            "estimated_length_m": {"type": "integer", "minimum": 1, "maximum": 10000},
        },
        "additionalProperties": False,
    },
}

VERIFICATION_POLICY: dict[str, Any] = {"min_verifications": 2, "min_locale_diversity": 1}

ATTACHMENT_RULES: dict[str, Any] = {
    "max_files": 4,
    "max_size_mb": 8,
    "mime": ["image/jpeg", "image/png", "image/webp"],
}


async def seed(database_url: str) -> tuple[int, int]:
    engine = create_engine(database_url)
    created = 0
    updated = 0
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            for spec in INITIAL_CATEGORIES:
                category = await session.scalar(
                    select(Category).where(Category.slug == spec["slug"])
                )
                schema = PER_CATEGORY_FORM_SCHEMAS.get(spec["slug"], FORM_SCHEMA)
                now = datetime.now(UTC)
                if category is None:
                    session.add(
                        Category(
                            slug=spec["slug"],
                            icon=spec["icon"],
                            form_schema=schema,
                            verification_policy=VERIFICATION_POLICY,
                            attachment_rules=ATTACHMENT_RULES,
                            default_locale_keys={
                                "label_key": spec["label_key"],
                                "description_key": f"{spec['label_key']}.description",
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    created += 1
                    continue
                # Refresh managed seed config (school/road gained real field
                # schemas during Phase 5); version bumps only when it changed.
                if category.form_schema != schema:
                    category.form_schema = schema
                    category.form_schema_version += 1
                    category.updated_at = now
                    updated += 1
            await session.commit()
        return created, updated
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy async URL (default: TK_DATABASE_URL env / Settings)",
    )
    args = parser.parse_args()
    url = args.database_url or Settings().database_url
    created, updated = asyncio.run(seed(url))
    print(f"Seed complete: {created} created, {updated} refreshed (idempotent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
