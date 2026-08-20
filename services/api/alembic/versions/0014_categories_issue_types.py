"""Categories v2 (translations + hierarchy) and configurable issue types (PRD §4, §8).

Revision ID: 0014_categories_issue_types
Revises: 0013_provenance_domain
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_categories_issue_types"
down_revision: str | None = "0013_provenance_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ISSUE_TYPES = [
    ("school", "toilet", "Toilet / sanitation"),
    ("school", "drinking_water", "Drinking water"),
    ("school", "classroom", "Classroom condition"),
    ("school", "electricity", "Electricity"),
    ("school", "teacher_availability", "Teacher availability"),
    ("school", "furniture", "Furniture"),
    ("school", "boundary_wall", "Boundary wall"),
    ("school", "cleanliness", "Cleanliness"),
    ("school", "safety", "Safety"),
    ("hospital", "bed_availability", "Bed availability"),
    ("hospital", "staff", "Staff"),
    ("hospital", "medicine", "Medicine"),
    ("hospital", "equipment", "Equipment"),
    ("hospital", "cleanliness", "Cleanliness"),
    ("hospital", "water", "Water"),
    ("hospital", "electricity", "Electricity"),
    ("road", "pothole", "Pothole"),
    ("road", "drainage", "Drainage"),
    ("road", "street_light", "Street light"),
    ("road", "surface_damage", "Surface damage"),
    ("road", "signage", "Signage"),
]


def upgrade() -> None:
    op.create_table(
        "category_translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "locale"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
    )
    op.create_table(
        "category_relationships",
        sa.Column("parent_category_id", sa.Uuid(), nullable=False),
        sa.Column("child_category_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("parent_category_id", "child_category_id"),
        sa.CheckConstraint(
            "parent_category_id <> child_category_id", name="ck_category_rels_not_self"
        ),
        sa.ForeignKeyConstraint(["child_category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_category_id"], ["categories.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "issue_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("form_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "slug"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_issue_types_category"), "issue_types", ["category_id"])

    values = ", ".join(f"('{cat}', '{slug}', '{name}')" for cat, slug, name in _ISSUE_TYPES)
    op.execute(
        # Seed migration: every interpolated value comes from the module-level
        # _ISSUE_TYPES constant tuple — no user input exists in migrations.
        sa.text(  # nosemgrep
            f"""
            INSERT INTO issue_types (id, category_id, slug, name, description,
                                     form_schema, is_active, created_at, updated_at)
            SELECT gen_random_uuid(), c.id, t.slug, t.name, t.name,
                   '{{}}'::jsonb, true, now(), now()
            FROM (VALUES {values}) AS t(cat_slug, slug, name)
            JOIN categories c ON c.slug = t.cat_slug
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_issue_types_category"), table_name="issue_types")
    op.drop_table("issue_types")
    op.drop_table("category_relationships")
    op.drop_table("category_translations")
