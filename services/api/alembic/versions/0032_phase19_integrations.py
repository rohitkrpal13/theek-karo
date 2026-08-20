"""Phase 19 government interoperability + data integration layer.

Adds the integration hub: a connector registry with health/circuit-breaker
state, an outbox for reliable external events, signed webhook delivery with
retries, plus the fields the ingestion pipeline needs for change detection
(diff counts on import jobs) and source registry completeness
(authority level, terms, documentation URL, update frequency, status).

* ``integration_connectors`` — one row per connector adapter (code = registry
  key). Status drives the circuit breaker: HEALTHY → DEGRADED (repeated
  failures) → CIRCUIT_OPEN (fail-fast until cooldown) → RECOVERING.
  No secrets are stored — ``config`` holds only non-secret settings and the
  ``auth_type`` label; credentials live in environment/secret-manager only.
* ``outbox_events`` — transactional outbox (one row per event written inside
  the action's DB transaction) so external delivery can never be lost or
  double-created; the worker dispatches due rows.
* ``webhook_subscriptions`` + ``webhook_deliveries`` — outgoing webhook
  targets and per-delivery log. The signing key is *derived* from a server
  master secret + the subscription's random ``secret_key_id`` (HMAC); the
  raw secret is never stored. Deliveries retry with backoff and dead-letter.
* ``data_sources`` gains authority_level / documentation_url / terms /
  update_frequency_hours / last_verified_at / status.
* ``gov_import_jobs`` gains the change-detection counters and the schema
  drift flag (``rows_added/removed/modified/unchanged/rejected``,
  ``schema_drift_flagged``) and the sync states queued/partial/cancelled.

Pure additive; downgrade drops the tables/columns and the seed.

Revision ID: 0032_phase19_integrations
Revises: 0031_phase15_community_confirmation
Create Date: 2026-08-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032_phase19_integrations"
down_revision: str | None = "0031_phase15_community_confirmation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# connector code -> (name, provider, category, auth_type, endpoint, version)
_CONNECTOR_SEED = [
    (
        "udise_plus_school",
        "UDISE+ School Data",
        "MoE / UDISE+",
        "education",
        "api_key",
        "https://udiseplus.gov.in",
        "1.0",
    ),
    (
        "nhp_hospital",
        "NHP Hospital Facilities",
        "National Health Portal",
        "healthcare",
        "public",
        "https://nhp.gov.in",
        "1.0",
    ),
    (
        "cctns_police",
        "CCTNS Police Stations",
        "NCRB / CCTNS",
        "police",
        "public",
        "https://www.cctns.gov.in",
        "1.0",
    ),
    (
        "ecourts",
        "eCourts District Courts",
        "eCourts Mission Mode Project",
        "courts",
        "public",
        "https://ecourts.gov.in",
        "1.0",
    ),
    (
        "pmgsy_roads",
        "PMGSY Road Infrastructure",
        "PMGSY / MoRD",
        "roads",
        "public",
        "https://pmgsy.nic.in",
        "1.0",
    ),
    (
        "generic_gov",
        "Generic Government Dataset Connector",
        "Theek Karo",
        "general",
        "none",
        "",
        "1.0",
    ),
]


def upgrade() -> None:
    op.create_table(
        "integration_connectors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("auth_type", sa.String(length=32), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column("version", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="UNKNOWN",
        ),
        sa.Column("sync_frequency_hours", sa.Integer(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_imported", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rate_limit_remaining", sa.Integer(), nullable=True),
        sa.Column("retry_after_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_fingerprint", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_integration_connectors_code"),
        sa.CheckConstraint(
            "status IN ('UNKNOWN', 'HEALTHY', 'DEGRADED', 'CIRCUIT_OPEN', 'RECOVERING')",
            name="ck_integration_connectors_status",
        ),
        sa.CheckConstraint(
            "auth_type IN ('none', 'public', 'api_key', 'oauth2', 'jwt', 'service_account')",
            name="ck_integration_connectors_auth_type",
        ),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'DELIVERING', 'DELIVERED', 'FAILED', 'DEAD')",
            name="ck_outbox_events_status",
        ),
    )
    op.create_index(
        op.f("ix_outbox_events_due"),
        "outbox_events",
        ["status", "next_attempt_at"],
    )

    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("secret_key_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'disabled')", name="ck_webhook_subscriptions_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_webhook_subscriptions_status"), "webhook_subscriptions", ["status"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("outbox_event_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SUCCESS', 'FAILED', 'DEAD')",
            name="ck_webhook_deliveries_status",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["webhook_subscriptions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["outbox_event_id"], ["outbox_events.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_webhook_deliveries_due"),
        "webhook_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        op.f("ix_webhook_deliveries_event"),
        "webhook_deliveries",
        ["outbox_event_id"],
    )

    # -- data_sources registry completeness -----------------------------------
    op.add_column("data_sources", sa.Column("authority_level", sa.String(length=32), nullable=True))
    op.add_column("data_sources", sa.Column("documentation_url", sa.Text(), nullable=True))
    op.add_column("data_sources", sa.Column("terms", sa.Text(), nullable=True))
    op.add_column("data_sources", sa.Column("update_frequency_hours", sa.Integer(), nullable=True))
    op.add_column(
        "data_sources", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "data_sources",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    )

    # -- gov_datasets: explicit connector mapping (registry key from
    # -- connectors.py, e.g. udise_plus_school). Defaults to generic_gov so
    # -- legacy rows keep importing through the generic adapter.
    op.add_column(
        "gov_datasets",
        sa.Column(
            "connector_code", sa.String(length=64), nullable=True, server_default="generic_gov"
        ),
    )

    # -- gov_import_jobs change-detection counters ----------------------------
    op.add_column("gov_import_jobs", sa.Column("rows_added", sa.Integer(), nullable=True))
    op.add_column("gov_import_jobs", sa.Column("rows_removed", sa.Integer(), nullable=True))
    op.add_column("gov_import_jobs", sa.Column("rows_modified", sa.Integer(), nullable=True))
    op.add_column("gov_import_jobs", sa.Column("rows_unchanged", sa.Integer(), nullable=True))
    op.add_column("gov_import_jobs", sa.Column("rows_rejected", sa.Integer(), nullable=True))
    op.add_column(
        "gov_import_jobs",
        sa.Column("schema_drift_flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "gov_import_jobs",
        sa.Column("meta", sa.JSON(), nullable=True),
    )

    # -- seed the known connector adapters (registry keys from connectors.py) --
    # Explicit SQL: the JSON ``config`` value is passed as text and cast in
    # SQL, so the asyncpg driver never sees a raw Python dict.
    for code, name, provider, category, auth_type, endpoint, version in _CONNECTOR_SEED:
        op.execute(
            sa.text(
                """
                INSERT INTO integration_connectors
                    (id, code, name, provider, category, auth_type, endpoint,
                     version, status, config, created_at, updated_at)
                SELECT gen_random_uuid(), :code, :name, :provider, :category,
                       :auth_type, :endpoint, :version, 'UNKNOWN', '{}'::jsonb,
                       now(), now()
                WHERE NOT EXISTS (
                    SELECT 1 FROM integration_connectors WHERE code = :code
                )
                """
            ).bindparams(
                code=code,
                name=name,
                provider=provider,
                category=category,
                auth_type=auth_type,
                endpoint=endpoint,
                version=version,
            )
        )


def downgrade() -> None:
    op.drop_column("gov_import_jobs", "meta")
    op.drop_column("gov_datasets", "connector_code")
    op.drop_column("gov_import_jobs", "schema_drift_flagged")
    op.drop_column("gov_import_jobs", "rows_rejected")
    op.drop_column("gov_import_jobs", "rows_unchanged")
    op.drop_column("gov_import_jobs", "rows_modified")
    op.drop_column("gov_import_jobs", "rows_removed")
    op.drop_column("gov_import_jobs", "rows_added")
    op.drop_column("data_sources", "status")
    op.drop_column("data_sources", "last_verified_at")
    op.drop_column("data_sources", "update_frequency_hours")
    op.drop_column("data_sources", "terms")
    op.drop_column("data_sources", "documentation_url")
    op.drop_column("data_sources", "authority_level")
    op.drop_index(op.f("ix_webhook_deliveries_event"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_due"), table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index(op.f("ix_webhook_subscriptions_status"), table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
    op.drop_index(op.f("ix_outbox_events_due"), table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("integration_connectors")
