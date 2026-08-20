"""Phase 19 tests: integration hub (connector registry + circuit breaker,
idempotent change-detected imports, schema-drift protection, signed webhooks +
outbox, rollback, lineage)."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from tests.conftest import _register_and_verify
from tests.test_govdata_phase10 import _admin_headers, _seed_govdata_fixtures
from tk_api.core.db import create_session_factory
from tk_api.govdata.models import GovDataset, GovDatasetRecord
from tk_api.integrations.diff import record_checksum
from tk_api.integrations.drift import compute_fingerprint
from tk_api.integrations.models import (
    IntegrationConnector,
    OutboxEvent,
    WebhookDelivery,
    WebhookSubscription,
)
from tk_api.integrations.webhooks import (
    derive_signing_key,
    dispatch_due_webhooks,
    emit_outbox_event,
    sign_payload,
    verify_signature,
)


def _seed_connector(client: TestClient, code: str = "generic_gov") -> str:
    async def seed() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            row = IntegrationConnector(
                code=code,
                name="Generic Government Dataset Connector",
                provider="Theek Karo",
                category="general",
                auth_type="none",
                status="UNKNOWN",
                config={},
            )
            session.add(row)
            await session.flush()
            await session.commit()
            return str(row.id)

    return asyncio.run(seed())


def _seed_webhook_subscription(client: TestClient, *, events: list[str]) -> dict[str, str]:
    async def seed() -> dict[str, str]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            sub = WebhookSubscription(
                name="Test Webhook",
                url="https://example.in/hooks/tk",
                events=events,
                secret_key_id="test-key-id-123",
                status="active",
            )
            session.add(sub)
            await session.flush()
            await session.commit()
            return {"id": str(sub.id), "secret_key_id": sub.secret_key_id}

    return asyncio.run(seed())


def _emit_outbox(client: TestClient, event: str) -> str:
    async def emit() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            row = await emit_outbox_event(
                session,
                event=event,
                aggregate_type="report",
                aggregate_id=uuid.uuid4(),
                payload={"report_id": str(uuid.uuid4()), "title": "test"},
            )
            await session.commit()
            return str(row.id)

    return asyncio.run(emit())


# -----------------------------------------------------------------------------
# 1. Change detection & drift (pure functions)
# -----------------------------------------------------------------------------


def test_record_checksum_deterministic() -> None:
    a = record_checksum({"b": 2, "a": 1, "c": [1, 2]})
    b = record_checksum({"a": 1, "c": [1, 2], "b": 2})
    assert a == b
    assert record_checksum({"a": 1}) != record_checksum({"a": 2})


def test_compute_fingerprint_ignores_order() -> None:
    fp1 = compute_fingerprint([{"name": "A", "students": 10}])
    fp2 = compute_fingerprint([{"students": 10, "name": "A"}])
    assert fp1 == fp2
    fp3 = compute_fingerprint([{"name": "A", "students": 10, "new_field": 1}])
    assert fp1 != fp3


def test_sign_and_verify_hmac_with_replay_protection() -> None:
    payload = b'{"event": "report.created"}'
    ts = 1_700_000_000
    sig = sign_payload("master-secret", "key-id", payload, ts)
    assert sig.startswith(f"t={ts},v1=")
    assert verify_signature("master-secret", "key-id", payload, sig, now=ts)
    # Replay: old timestamp outside the skew window must be rejected
    assert not verify_signature("master-secret", "key-id", payload, sig, now=ts + 3600)
    # Tampered payload must fail
    assert not verify_signature(
        "master-secret", "key-id", b'{"event": "report.deleted"}', sig, now=ts
    )
    # Wrong key id must fail (derived key)
    assert not verify_signature("master-secret", "other-key", payload, sig, now=ts)
    assert derive_signing_key("master", "a") != derive_signing_key("master", "b")


def test_webhook_url_validation() -> None:
    from tk_api.integrations.webhooks import WebhookError, validate_webhook_url

    assert validate_webhook_url("https://example.in/hook") == "https://example.in/hook"
    with pytest.raises(WebhookError):
        validate_webhook_url("http://example.in/hook")  # no plain http
    with pytest.raises(WebhookError):
        validate_webhook_url("https://127.0.0.1/hook")  # loopback


# -----------------------------------------------------------------------------
# 2. Connector registry + circuit breaker (API)
# -----------------------------------------------------------------------------


def test_connector_health_endpoint(client: TestClient, sender: Any) -> None:
    _seed_connector(client, "udise_plus_school")
    headers = _admin_headers(client, sender)
    resp = client.get("/api/v1/govdata/connectors/health", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["code"] == "udise_plus_school" for r in rows)
    row = next(r for r in rows if r["code"] == "udise_plus_school")
    assert row["status"] in {"UNKNOWN", "HEALTHY", "DEGRADED", "CIRCUIT_OPEN", "RECOVERING"}
    assert row["freshness"] in {"FRESH", "RECENT", "STALE", "UNKNOWN", "UNAVAILABLE"}
    # public-safe: never any secret material
    assert "secret" not in json.dumps(row).lower()


def test_circuit_breaker_blocks_sync(client: TestClient, sender: Any) -> None:
    """A connector that fails repeatedly moves DEGRADED and blocks new syncs."""
    data = _seed_govdata_fixtures(client)
    dataset_id = data["dataset_id"]
    _seed_connector(client, "generic_gov")
    headers = _admin_headers(client, sender)

    # Fail the schema the threshold number of times (invalid payloads)
    for _ in range(3):
        resp = client.post(
            "/api/v1/govdata/imports",
            json={"dataset_id": dataset_id, "raw_payload": {"records": []}},
            headers=headers,
        )
        assert resp.status_code == 202
        assert resp.json()["status"] in ("failed", "partial")

    # Now the connector must be DEGRADED (>= threshold failures) and block sync
    health = client.get("/api/v1/govdata/connectors/health", headers=headers).json()
    row = next(r for r in health if r["code"] == "generic_gov")
    assert row["status"] == "DEGRADED"

    resp = client.post(
        "/api/v1/govdata/imports",
        json={"dataset_id": dataset_id, "raw_payload": {"records": [{"name": "x"}]}},
        headers=headers,
    )
    body = resp.json()
    assert body["status"] == "failed"
    assert "circuit" in (body["error"] or "").lower()


# -----------------------------------------------------------------------------
# 3. Idempotent import + change detection (API)
# -----------------------------------------------------------------------------


def _import_payload(dataset_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"dataset_id": dataset_id, "raw_payload": {"records": records}}


def test_import_is_idempotent_and_detects_changes(client: TestClient, sender: Any) -> None:
    data = _seed_govdata_fixtures(client)
    dataset_id = data["dataset_id"]
    _seed_connector(client, "generic_gov")
    headers = _admin_headers(client, sender)

    records = [
        {
            "name": "Govt Senior Secondary School Jaipur",
            "udise_code": "SCH-JPR-101",
            "total_students": 520,
            "sanctioned_teachers": 18,
        },
        {
            "name": "Govt Primary School Johari",
            "udise_code": "SCH-JPR-202",
            "total_students": 140,
        },
    ]

    # First import: 2 added
    resp = client.post(
        "/api/v1/govdata/imports", json=_import_payload(dataset_id, records), headers=headers
    )
    body = resp.json()
    assert body["status"] == "completed", body
    assert body["rows_added"] == 2
    assert body["rows_imported"] == 2

    # Re-import identical payload: idempotent — 0 added, 2 unchanged
    resp = client.post(
        "/api/v1/govdata/imports", json=_import_payload(dataset_id, records), headers=headers
    )
    body = resp.json()
    assert body["status"] == "completed"
    assert body["rows_added"] == 0
    assert body["rows_unchanged"] == 2

    # Change one record + drop the other: 1 modified + 1 removed
    changed = [dict(records[0], total_students=600)]
    resp = client.post(
        "/api/v1/govdata/imports", json=_import_payload(dataset_id, changed), headers=headers
    )
    body = resp.json()
    assert body["status"] == "completed"
    assert body["rows_modified"] == 1
    assert body["rows_removed"] == 1

    # Time-travel preserved: the old version row is closed, not deleted
    async def check() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(GovDatasetRecord).where(
                            GovDatasetRecord.dataset_id == uuid.UUID(dataset_id),
                            GovDatasetRecord.external_key == "SCH-JPR-101",
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 2  # v1 closed + v2 open
            assert sum(1 for r in rows if r.valid_to is not None) == 1
            assert sum(1 for r in rows if r.valid_to is None) == 1

    asyncio.run(check())


def test_import_preview_writes_nothing(client: TestClient, sender: Any) -> None:
    data = _seed_govdata_fixtures(client)
    dataset_id = data["dataset_id"]
    _seed_connector(client, "generic_gov")
    headers = _admin_headers(client, sender)

    records = [{"name": "New School Only In Preview", "udise_code": "SCH-X1"}]
    resp = client.post(
        "/api/v1/govdata/imports",
        json={**_import_payload(dataset_id, records), "preview_only": True},
        headers=headers,
    )
    body = resp.json()
    assert body["status"] == "preview_completed"
    assert body["rows_added"] == 1

    # Nothing was actually written
    async def check() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            count = await session.scalar(
                select(GovDatasetRecord.id).where(
                    GovDatasetRecord.dataset_id == uuid.UUID(dataset_id),
                    GovDatasetRecord.external_key == "SCH-X1",
                )
            )
            assert count is None

    asyncio.run(check())


def test_import_rollback(client: TestClient, sender: Any) -> None:
    data = _seed_govdata_fixtures(client)
    dataset_id = data["dataset_id"]
    _seed_connector(client, "generic_gov")
    headers = _admin_headers(client, sender)

    records = [{"name": "Govt Senior Secondary School Jaipur", "udise_code": "SCH-JPR-101"}]
    resp = client.post(
        "/api/v1/govdata/imports", json=_import_payload(dataset_id, records), headers=headers
    )
    job_id = resp.json()["id"]

    roll = client.post(f"/api/v1/govdata/imports/{job_id}/rollback", headers=headers)
    assert roll.status_code == 200
    body = roll.json()
    assert body["status"] == "rolled_back"
    assert body["records_removed"] >= 1


def test_schema_drift_blocks_then_force_overrides(client: TestClient, sender: Any) -> None:
    data = _seed_govdata_fixtures(client)
    dataset_id = data["dataset_id"]
    _seed_connector(client, "generic_gov")
    headers = _admin_headers(client, sender)

    first = [{"name": "School A", "udise_code": "A1", "students": 100}]
    resp = client.post(
        "/api/v1/govdata/imports", json=_import_payload(dataset_id, first), headers=headers
    )
    assert resp.json()["status"] == "completed"

    # Schema changed (new key) → drift blocks the import
    drifted = [{"name": "School A", "udise_code": "A1", "students": 100, "toilets": 4}]
    resp = client.post(
        "/api/v1/govdata/imports", json=_import_payload(dataset_id, drifted), headers=headers
    )
    body = resp.json()
    assert body["status"] == "failed"
    assert body["schema_drift_flagged"] is True

    # Operator forces it → import proceeds and fingerprint updates
    resp = client.post(
        "/api/v1/govdata/imports",
        json={**_import_payload(dataset_id, drifted), "force": True},
        headers=headers,
    )
    body = resp.json()
    assert body["status"] == "completed"
    assert body["schema_drift_flagged"] is False


# -----------------------------------------------------------------------------
# 4. Webhooks + outbox (API + service)
# -----------------------------------------------------------------------------


def test_webhook_subscription_admin_crud(client: TestClient, sender: Any) -> None:
    _seed_connector(client)
    headers = _admin_headers(client, sender)

    resp = client.post(
        "/api/v1/integrations/webhooks",
        json={
            "name": "Partner Notifications",
            "url": "https://partner.example.in/hooks/tk",
            "events": ["report.created", "resolution.verified"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    sub = resp.json()
    assert sub["status"] == "active"
    assert set(sub["events"]) == {"report.created", "resolution.verified"}
    # The secret_key_id is an identifier — the raw key is never returned
    assert sub["secret_key_id"]

    # invalid event rejected
    resp = client.post(
        "/api/v1/integrations/webhooks",
        json={
            "name": "Bad",
            "url": "https://partner.example.in/hooks/bad",
            "events": ["report.not_an_event"],
        },
        headers=headers,
    )
    assert resp.status_code == 422

    # plain-http URL rejected (SSRF-safe)
    resp = client.post(
        "/api/v1/integrations/webhooks",
        json={
            "name": "Insecure",
            "url": "http://partner.example.in/hooks/x",
            "events": ["report.created"],
        },
        headers=headers,
    )
    assert resp.status_code == 422

    # list + delete
    subs = client.get("/api/v1/integrations/webhooks", headers=headers).json()
    assert any(s["id"] == sub["id"] for s in subs)
    assert (
        client.delete(f"/api/v1/integrations/webhooks/{sub['id']}", headers=headers).status_code
        == 204
    )


def test_webhook_crud_requires_admin(client: TestClient, sender: Any) -> None:
    phone_suffix = str(int(uuid.uuid4().hex[:6], 16) % 90000 + 10000)
    tokens = _register_and_verify(client, sender, f"98765{phone_suffix}")
    citizen_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.get("/api/v1/integrations/webhooks", headers=citizen_headers)
    assert resp.status_code == 403


def test_outbox_dispatch_to_webhook(client: TestClient, sender: Any) -> None:
    """Outbox event is delivered to a matching subscription; deliveries log."""
    _seed_webhook_subscription(client, events=["report.created"])

    event_id = _emit_outbox(client, "report.created")

    async def run_dispatch() -> dict[str, int]:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            return await dispatch_due_webhooks(session)

    counts = asyncio.run(run_dispatch())

    async def check() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            event = await session.get(OutboxEvent, uuid.UUID(event_id))
            assert event is not None
            # Delivery to a https://example.in URL fails (network) → FAILED, retry scheduled
            delivery = await session.scalar(select(WebhookDelivery).limit(1))
            assert delivery is not None
            assert delivery.status in ("SUCCESS", "FAILED", "DEAD")
            assert delivery.attempts >= 1

    asyncio.run(check())
    assert counts["events_processed"] >= 1


def test_report_submit_emits_outbox_event(client: TestClient, sender: Any) -> None:
    """Creating a report writes an outbox row in the same transaction."""
    from tk_api.civic.models import Category

    async def seed_category() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            cat = Category(
                slug=f"roads_{uuid.uuid4().hex[:6]}",
                icon="road",
                form_schema={"type": "object", "properties": {}},
                verification_policy={},
                attachment_rules={},
                default_locale_keys={},
                form_schema_version=1,
                is_active=True,
            )
            session.add(cat)
            await session.flush()
            await session.commit()
            return str(cat.id)

    category_id = asyncio.run(seed_category())
    phone_suffix = str(int(uuid.uuid4().hex[:6], 16) % 90000 + 10000)
    tokens = _register_and_verify(client, sender, f"98765{phone_suffix}")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Find the category slug by id via the seeded Category table
    async def find_slug() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            row = await session.get(Category, uuid.UUID(category_id))
            return row.slug if row else ""

    slug = asyncio.run(find_slug())
    resp = client.post(
        "/api/v1/reports",
        json={
            "category_slug": slug,
            "title": "Pothole on main road",
            "description": "Deep pothole near the bus stop, dangerous at night.",
            "location": {"type": "Point", "coordinates": [77.2, 28.6]},
            "location_accuracy_m": 10,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    async def check_outbox() -> bool:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            row = await session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.event == "report.created",
                    OutboxEvent.aggregate_type == "report",
                )
            )
            return row is not None

    assert asyncio.run(check_outbox())


# -----------------------------------------------------------------------------
# 5. Lineage + catalog
# -----------------------------------------------------------------------------


def test_institution_lineage(client: TestClient, sender: Any) -> None:
    data = _seed_govdata_fixtures(client)
    inst_id = data["inst_id"]
    _seed_connector(client, "generic_gov")
    headers = _admin_headers(client, sender)

    # Import so records exist
    client.post(
        "/api/v1/govdata/imports",
        json=_import_payload(
            data["dataset_id"],
            [{"name": "Govt Senior Secondary School Jaipur", "udise_code": "SCH-JPR-101"}],
        ),
        headers=headers,
    )

    resp = client.get(f"/api/v1/govdata/lineage/institution/{inst_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    levels = [c["level"] for c in body["chain"]]
    assert "canonical_institution" in levels
    assert "source" in levels
    assert "dataset" in levels
    assert "report" in levels


def test_public_catalog_endpoint(client: TestClient) -> None:
    data = _seed_govdata_fixtures(client)
    _seed_connector(client, "generic_gov")
    resp = client.get("/api/v1/govdata/catalog")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["dataset_id"] == data["dataset_id"] for r in rows)
    row = next(r for r in rows if r["dataset_id"] == data["dataset_id"])
    assert row["publisher"] == "Ministry of Education"
    assert row["freshness"] in {"FRESH", "RECENT", "STALE", "UNKNOWN", "UNAVAILABLE"}


def test_sync_connector_endpoint(client: TestClient, sender: Any) -> None:
    data = _seed_govdata_fixtures(client)

    # Point the dataset at an explicitly registered connector
    async def set_code() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            ds = await session.get(GovDataset, uuid.UUID(data["dataset_id"]))
            if ds:
                ds.connector_code = "generic_gov"
                await session.commit()

    asyncio.run(set_code())
    _seed_connector(client, "generic_gov")
    headers = _admin_headers(client, sender)

    resp = client.post("/api/v1/integrations/connectors/generic_gov/sync", headers=headers)
    assert resp.status_code == 202
    body = resp.json()
    assert body["connector_code"] == "generic_gov"
    assert len(body["queued_jobs"]) >= 1
    assert all(j["status"] == "queued" for j in body["queued_jobs"])
