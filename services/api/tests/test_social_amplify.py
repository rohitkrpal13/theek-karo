"""Tests for civic social media amplification (X & Instagram) integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from tests.test_reports import CATEGORY, VALID_FIELDS, _admin_headers, _citizen_headers
from tk_api.core.config import Settings
from tk_api.reports.publisher import (
    DisabledXPublisher,
    LiveXPublisher,
    SimulatedXPublisher,
)
from tk_api.reports.social import (
    build_social_post_package,
    calculate_x_char_weight,
    resolve_city_directory,
    select_relevant_authorities,
)


def test_resolve_city_from_address_hint():
    # Bengaluru detection
    blr_dir = resolve_city_directory(
        address_hint="12th Main, Koramangala 4th Block, Bengaluru, Karnataka",
        location_coords=[77.6245, 12.9352],
    )
    assert blr_dir is not None
    assert blr_dir.city_name == "Bengaluru"
    assert blr_dir.municipal_authority.x_handle == "@BBMPCOMM"
    assert blr_dir.municipal_authority.ig_handle == "@bbmp.bangalore"
    assert blr_dir.municipal_authority.verification_status == "unverified"

    # Mumbai detection
    mum_dir = resolve_city_directory(
        address_hint="Near Bandra Station West, Mumbai",
        location_coords=None,
    )
    assert mum_dir is not None
    assert mum_dir.city_name == "Mumbai"
    assert mum_dir.municipal_authority.x_handle == "@mybmc"

    # Delhi detection
    delhi_dir = resolve_city_directory(
        address_hint="Sector 14, Dwarka, New Delhi",
        location_coords=None,
    )
    assert delhi_dir is not None
    assert delhi_dir.city_name == "Delhi"
    assert delhi_dir.municipal_authority.x_handle == "@MCD_Delhi"


def test_gps_bounding_box_prioritized_over_text():
    # If coords are in Bengaluru, GPS sensor ground truth takes precedence over text
    resolved = resolve_city_directory(
        address_hint="Visiting Mumbai next week, road broken here",
        location_coords=[77.6245, 12.9352],  # Bengaluru GPS
    )
    assert resolved is not None
    assert resolved.city_name == "Bengaluru"


def test_twitter_weighted_char_count():
    # URL counts as 23 characters regardless of length
    url = "https://theekkaro.in/reports/123e4567-e89b-12d3-a456-426614174000"
    assert calculate_x_char_weight(url) == 23

    # Emoji counts: single codepoint emoji is 2; emoji with variation selector is 4
    assert calculate_x_char_weight("🚨") == 2
    assert calculate_x_char_weight("⚠️") == 4

    # Mixed text
    mixed = f"🚨 Hazard: {url}"
    # 2 (emoji) + 1 (space) + 8 ("Hazard: ") + 23 (url) = 34
    assert calculate_x_char_weight(mixed) == 34


def test_category_authority_selection():
    blr_dir = resolve_city_directory(
        address_hint="Indiranagar, Bangalore",
        location_coords=[77.64, 12.97],
    )
    # Road defect should include Traffic Police
    road_authorities = select_relevant_authorities(blr_dir, "roads")
    handles = [a.x_handle for a in road_authorities]
    assert "@BBMPCOMM" in handles
    assert "@blrcitytraffic" in handles

    # Water logging / sewage should include BWSSB
    water_authorities = select_relevant_authorities(blr_dir, "water_sanitation")
    w_handles = [a.x_handle for a in water_authorities]
    assert "@BBMPCOMM" in w_handles
    assert "@BWSSB_Chairman" in w_handles


def test_build_social_post_package_constraints():
    pkg = build_social_post_package(
        report_id="123e4567-e89b-12d3-a456-426614174000",
        ticket_no="TK-2026-BLR-04821",
        title="Massive crater pothole causing vehicle damage and water accumulation",
        description=(
            "A 3-foot deep pothole has appeared right after the rain near 80 Feet Road. "
            "Two two-wheelers have already skidded."
        ),
        category_slug="roads_transport",
        severity="critical",
        address_hint="80 Feet Road, Koramangala 4th Block, Bengaluru",
        location_coords=[77.6245, 12.9352],
        tone="urgent",
    )

    # 1. Check X (Twitter) constraints
    x_post = pkg["x_post"]
    assert x_post["char_count"] <= 280
    assert x_post["fits_single_tweet"] is True
    assert "https://x.com/intent/tweet?text=" in x_post["intent_url"]
    assert "TK-2026-BLR-04821" in x_post["text"]
    assert "@BBMPCOMM" in x_post["text"]

    # 2. Check Instagram Post
    ig_post = pkg["instagram_post"]
    assert "⚠️ CIVIC OBSERVATION — ACTION REQUIRED" in ig_post["caption"]
    assert "@bbmp.bangalore" in ig_post["caption"]
    assert "TK-2026-BLR-04821" in ig_post["caption"]
    assert any("Bengaluru" in tag for tag in ig_post["hashtags"])

    # 3. Check Story Card Data
    story_card = pkg["story_card"]
    assert story_card["ticket_no"] == "TK-2026-BLR-04821"
    assert story_card["city"] == "Bengaluru"
    assert story_card["primary_authority_handle"] == "@BBMPCOMM"

    # 4. Check Authority verification status
    auths = pkg["authorities"]
    assert auths[0]["verification_status"] == "unverified"


def test_api_social_post_endpoint(client: TestClient, sender):
    # Setup category
    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)

    # Register citizen
    _, citizen_hdr = _citizen_headers(client, sender, "9876543210")

    # 1. Create a public report
    payload = {
        "category_slug": "school",
        "title": "Severe road depression near Indiranagar Metro",
        "description": (
            "The asphalt has sunk dangerously near Pillar 120. Needs immediate resurfacing."
        ),
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 10.0,
        "address_hint": "CMH Road, Indiranagar, Bengaluru, Karnataka",
        "severity": "high",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = rep["id"]

    # 2. Call social-post endpoint
    social_res = client.get(
        f"/api/v1/reports/{report_id}/social-post?tone=urgent",
        headers=citizen_hdr,
    )
    assert social_res.status_code == 200
    social_data = social_res.json()

    assert social_data["ticket_no"] == rep["ticket_no"]
    assert social_data["tone"] == "urgent"
    assert social_data["x_post"]["fits_single_tweet"] is True
    assert "@BBMPCOMM" in social_data["x_post"]["handles"]
    assert len(social_data["instagram_post"]["hashtags"]) >= 3
    assert social_data["story_card"]["city"] == "Bengaluru"
    assert social_data["authorities"][0]["verification_status"] == "unverified"

    # 3. Call social-broadcast endpoint (creator with high severity)
    broadcast_res = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x"},
        headers=citizen_hdr,
    )
    assert broadcast_res.status_code == 200
    b_data = broadcast_res.json()
    assert b_data["status"] == "simulated"
    assert b_data["published_url"] is None
    assert b_data["ticket_no"] == rep["ticket_no"]


def test_api_private_report_amplification_forbidden(client: TestClient, sender):
    # Setup category
    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)

    # Register citizen
    _, citizen_hdr = _citizen_headers(client, sender, "9876543211")

    # Create a private report
    payload = {
        "category_slug": "school",
        "title": "Private safety concern inside school premises",
        "description": "Confidential observation not for public amplification.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 10.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "high",
        "visibility": "private",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = rep["id"]

    # Attempting to get social post payload for private report MUST return 403 Forbidden
    res = client.get(
        f"/api/v1/reports/{report_id}/social-post?tone=urgent",
        headers=citizen_hdr,
    )
    assert res.status_code == 403
    assert "private_report_amplification_forbidden" in res.json()["type"]

    # Attempting to broadcast private report MUST return 403 Forbidden
    b_res = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x"},
        headers=citizen_hdr,
    )
    assert b_res.status_code == 403
    assert "private_report_amplification_forbidden" in b_res.json()["type"]


def test_api_draft_report_amplification_forbidden(client: TestClient, sender):
    # Setup category
    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)

    # Register citizen
    _, citizen_hdr = _citizen_headers(client, sender, "9876543212")

    # Create draft report
    draft_payload = {
        "category_slug": "school",
        "title": "Incomplete unsubmitted draft report",
        "description": "Draft report still being edited by user.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "fields": VALID_FIELDS,
    }
    draft_res = client.post("/api/v1/reports/drafts", json=draft_payload, headers=citizen_hdr)
    assert draft_res.status_code == 201
    draft_id = draft_res.json()["id"]

    # Amplifying unsubmitted draft MUST return 400 Bad Request
    res = client.get(
        f"/api/v1/reports/{draft_id}/social-post?tone=urgent",
        headers=citizen_hdr,
    )
    assert res.status_code == 400
    assert "draft_cannot_be_amplified" in res.json()["type"]


def test_api_broadcast_authorization_and_severity(client: TestClient, sender):
    # Setup category
    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)

    # Register citizen 1 (reporter) and citizen 2 (unrelated user)
    _, citizen1_hdr = _citizen_headers(client, sender, "9876543213")
    _, citizen2_hdr = _citizen_headers(client, sender, "9876543214")

    # Create a medium severity report
    payload = {
        "category_slug": "school",
        "title": "Minor cosmetic tile cracking in garden walkway",
        "description": "Tiles have minor hairline cracks, not an acute pedestrian hazard.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 10.0,
        "address_hint": "CMH Road, Indiranagar, Bengaluru, Karnataka",
        "severity": "medium",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen1_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = rep["id"]

    # 1. Unrelated citizen attempting broadcast must receive 403 Forbidden
    unauth_res = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x"},
        headers=citizen2_hdr,
    )
    assert unauth_res.status_code == 403
    assert "broadcast_unauthorized" in unauth_res.json()["type"]

    # 2. Reporter attempting broadcast on medium severity must receive 422 Unprocessable Entity
    ineligible_res = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x"},
        headers=citizen1_hdr,
    )
    assert ineligible_res.status_code == 422
    assert "ineligible_severity_for_broadcast" in ineligible_res.json()["type"]


def test_broadcast_idempotency_and_status_polling(client: TestClient, sender):
    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543220")

    payload = {
        "category_slug": "school",
        "title": "Severe road cavity collapsed on ring road",
        "description": "Bus route completely impassable. High risk of fatal accident.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Ring Road, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = rep["id"]

    # Before broadcasting, status endpoint returns 404
    status_res = client.get(
        f"/api/v1/reports/{report_id}/social-broadcast",
        headers=citizen_hdr,
    )
    assert status_res.status_code == 404

    # First broadcast with idempotency key
    idem_key = "test-idem-key-001"
    b_res1 = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x", "tone": "urgent", "idempotency_key": idem_key},
        headers=citizen_hdr,
    )
    assert b_res1.status_code == 200
    b1 = b_res1.json()
    assert b1["id"] is not None
    assert b1["status"] == "simulated"
    assert b1["ticket_no"] == rep["ticket_no"]

    # Replay request with same idempotency key must return the exact same broadcast record
    b_res2 = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x", "tone": "urgent", "idempotency_key": idem_key},
        headers=citizen_hdr,
    )
    assert b_res2.status_code == 200
    b2 = b_res2.json()
    assert b2["id"] == b1["id"]

    # Status endpoint now returns 200 with the active broadcast
    status_res2 = client.get(
        f"/api/v1/reports/{report_id}/social-broadcast",
        headers=citizen_hdr,
    )
    assert status_res2.status_code == 200
    b_status = status_res2.json()
    assert b_status["id"] == b1["id"]
    assert b_status["status"] == "simulated"


def test_staff_role_can_broadcast(client: TestClient, sender):
    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543221")

    payload = {
        "category_slug": "school",
        "title": "Flooded electrical transformer substation",
        "description": "Sparks flying near residential compound during storm.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = rep["id"]

    # Admin user can broadcast even though not the reporter
    admin_b_res = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x", "tone": "urgent"},
        headers=admin_hdr,
    )
    assert admin_b_res.status_code == 200
    assert admin_b_res.json()["status"] == "simulated"


@pytest.mark.asyncio
async def test_disabled_publisher():
    pub = DisabledXPublisher()
    res = await pub.publish("Test message", report_id="123")
    assert res.ok is False
    assert res.retryable is False
    assert "disabled" in res.error.lower()


@pytest.mark.asyncio
async def test_simulated_publisher():
    pub = SimulatedXPublisher()
    res = await pub.publish("Test message", report_id="123")
    assert res.ok is True
    assert res.published_url is None
    assert res.external_post_id.startswith("sim-")


@pytest.mark.asyncio
async def test_live_publisher_success():
    settings = Settings(
        social_broadcast_mode="live",
        twitter_api_key="mock_key",
        twitter_api_secret="mock_secret",
        twitter_access_token="mock_token",
        twitter_access_token_secret="mock_token_secret",
    )
    pub = LiveXPublisher(settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"data": {"id": "1840001112223334445", "text": "Hello world"}}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    pub._client = mock_client

    res = await pub.publish("Hello world", report_id="123")
    assert res.ok is True
    assert res.external_post_id == "1840001112223334445"
    assert "1840001112223334445" in res.published_url


@pytest.mark.asyncio
async def test_live_publisher_rate_limit():
    settings = Settings(
        social_broadcast_mode="live",
        twitter_api_key="mock_key",
        twitter_api_secret="mock_secret",
        twitter_access_token="mock_token",
        twitter_access_token_secret="mock_token_secret",
    )
    pub = LiveXPublisher(settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Rate limit exceeded"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    pub._client = mock_client

    res = await pub.publish("Hello world", report_id="123")
    assert res.ok is False
    assert res.retryable is True
    assert "rate limit" in res.error.lower()


@pytest.mark.asyncio
async def test_live_publisher_unauthorized():
    settings = Settings(
        social_broadcast_mode="live",
        twitter_api_key="mock_key",
        twitter_api_secret="mock_secret",
        twitter_access_token="mock_token",
        twitter_access_token_secret="mock_token_secret",
    )
    pub = LiveXPublisher(settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    pub._client = mock_client

    res = await pub.publish("Hello world", report_id="123")
    assert res.ok is False
    assert res.retryable is False
    assert "401" in res.error or "unauthorized" in res.error.lower()


@pytest.mark.asyncio
async def test_live_publisher_timeout():
    import httpx

    settings = Settings(
        social_broadcast_mode="live",
        twitter_api_key="mock_key",
        twitter_api_secret="mock_secret",
        twitter_access_token="mock_token",
        twitter_access_token_secret="mock_token_secret",
    )
    pub = LiveXPublisher(settings)

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
    pub._client = mock_client

    res = await pub.publish("Hello world", report_id="123")
    assert res.ok is False
    assert res.retryable is False
    assert res.outcome_unknown is True
    assert "timed out" in res.error.lower()


def test_execute_broadcast_revalidation(client: TestClient, sender):
    import asyncio
    import uuid

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import execute_broadcast
    from tk_api.reports.models import Report, SocialBroadcast

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543225")

    payload = {
        "category_slug": "school",
        "title": "Substation danger in residential area",
        "description": "Hazardous live wires exposed.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = uuid.UUID(rep["id"])

    async def run_scenario():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # Create a queued broadcast directly
            broadcast = SocialBroadcast(
                report_id=report_id,
                requested_by=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                status="queued",
                post_text="Test civic post",
                max_attempts=3,
            )
            session.add(broadcast)
            await session.commit()
            await session.refresh(broadcast)
            b_id = broadcast.id

            # Mutate report to private before worker executes
            report = await session.get(Report, report_id)
            assert report is not None
            report.visibility = "private"
            await session.commit()

            # Worker or execute_broadcast runs
            executed = await execute_broadcast(
                session, broadcast_id=b_id, settings=client.app.state.settings
            )
            assert executed.status == "failed"
            assert "visibility was changed" in str(executed.last_error)

    asyncio.run(run_scenario())


def test_worker_social_broadcast_task(client: TestClient, sender):
    from tk_api.worker import DurableTask
    from tk_api.worker.tasks import social_broadcast

    assert social_broadcast.name == "tk_worker.social_broadcast"
    assert social_broadcast.max_retries == DurableTask.max_retries
    assert social_broadcast.acks_late is True
    assert social_broadcast.reject_on_worker_lost is True


def test_oauth1_authorization_header():
    settings = Settings(
        social_broadcast_mode="live",
        twitter_api_key="consumer_key_123",
        twitter_api_secret="consumer_secret_456",
        twitter_access_token="access_token_789",
        twitter_access_token_secret="token_secret_abc",
    )
    pub = LiveXPublisher(settings)
    headers = pub._build_headers("https://api.x.com/2/tweets")
    auth = headers.get("Authorization", "")
    assert auth.startswith("OAuth ")
    assert 'oauth_consumer_key="consumer_key_123"' in auth
    assert 'oauth_signature_method="HMAC-SHA1"' in auth
    assert 'oauth_token="access_token_789"' in auth
    assert 'oauth_version="1.0"' in auth
    assert "oauth_nonce=" in auth
    assert "oauth_timestamp=" in auth
    assert "oauth_signature=" in auth


def test_unauthorized_user_cannot_read_broadcast_status(client: TestClient, sender):
    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen1_hdr = _citizen_headers(client, sender, "9876543291")
    _, citizen2_hdr = _citizen_headers(client, sender, "9876543292")

    payload = {
        "category_slug": "school",
        "title": "Severe road cavity near school",
        "description": "Hazardous crater near entrance.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "high",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen1_hdr)
    assert create_res.status_code == 201
    report_id = create_res.json()["id"]

    # Citizen 1 triggers broadcast
    b_res = client.post(
        f"/api/v1/reports/{report_id}/social-broadcast",
        json={"network": "x", "tone": "urgent"},
        headers=citizen1_hdr,
    )
    assert b_res.status_code == 200

    # Citizen 2 (unrelated citizen) attempts to inspect broadcast status -> 403 Forbidden
    unauth_res = client.get(
        f"/api/v1/reports/{report_id}/social-broadcast",
        headers=citizen2_hdr,
    )
    assert unauth_res.status_code == 403
    assert "broadcast_unauthorized" in unauth_res.json()["type"]

    # Admin user can inspect status -> 200 OK
    auth_admin_res = client.get(
        f"/api/v1/reports/{report_id}/social-broadcast",
        headers=admin_hdr,
    )
    assert auth_admin_res.status_code == 200

    # Report creator can inspect status -> 200 OK
    creator_res = client.get(
        f"/api/v1/reports/{report_id}/social-broadcast",
        headers=citizen1_hdr,
    )
    assert creator_res.status_code == 200


def test_execute_broadcast_atomic_concurrency(client: TestClient, sender):
    import asyncio
    import uuid

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import execute_broadcast
    from tk_api.reports.models import SocialBroadcast

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543293")

    payload = {
        "category_slug": "school",
        "title": "Severe wire hazard",
        "description": "High voltage wire exposed on sidewalk.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = uuid.UUID(rep["id"])

    async def run_scenario():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # Seed broadcast record in "processing" state
            b = SocialBroadcast(
                report_id=report_id,
                requested_by=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                status="processing",
                post_text="Concurrent test post",
                attempts=1,
                max_attempts=3,
            )
            session.add(b)
            await session.commit()
            await session.refresh(b)
            b_id = b.id

            mock_pub = AsyncMock()
            executed = await execute_broadcast(
                session,
                broadcast_id=b_id,
                settings=client.app.state.settings,
                publisher=mock_pub,
            )
            # Row was already processing, so execute_broadcast should skip publish
            assert executed.status == "processing"
            mock_pub.publish.assert_not_called()

    asyncio.run(run_scenario())


def test_recover_stuck_broadcasts_sweep(client: TestClient, sender):
    import asyncio
    import uuid
    from datetime import UTC, datetime, timedelta

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import recover_stuck_broadcasts
    from tk_api.reports.models import SocialBroadcast

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543294")

    payload = {
        "category_slug": "school",
        "title": "Open drain danger",
        "description": "Deep open manhole without cover.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "high",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = uuid.UUID(rep["id"])

    async def run_recovery():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # 1. Stuck in processing for 15 minutes, attempt 1 -> should recover to queued
            stuck_b = SocialBroadcast(
                report_id=report_id,
                requested_by=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                status="processing",
                post_text="Drain hazard",
                attempts=1,
                max_attempts=3,
                updated_at=datetime.now(UTC) - timedelta(minutes=15),
            )
            session.add(stuck_b)
            await session.commit()
            await session.refresh(stuck_b)
            stuck_id = stuck_b.id

            recovered = await recover_stuck_broadcasts(
                session, settings=client.app.state.settings, max_age_seconds=600
            )
            assert stuck_id in recovered

            reloaded = await session.get(SocialBroadcast, stuck_id)
            assert reloaded is not None
            assert reloaded.status == "queued"
            assert "timeout" in str(reloaded.last_error).lower()

            # 2. Stuck broadcast that exhausted attempts -> should transition to failed
            reloaded.status = "processing"
            reloaded.attempts = 3
            reloaded.max_attempts = 3
            reloaded.updated_at = datetime.now(UTC) - timedelta(minutes=15)
            await session.commit()

            recovered2 = await recover_stuck_broadcasts(
                session, settings=client.app.state.settings, max_age_seconds=600
            )
            assert stuck_id in recovered2

            reloaded2 = await session.get(SocialBroadcast, stuck_id)
            assert reloaded2 is not None
            assert reloaded2.status == "failed"
            assert "maximum attempts" in str(reloaded2.last_error)

    asyncio.run(run_recovery())


def test_rfc5849_errata2550_official_test_vector():
    """Validates RFC 5849 Errata ID 2550 official test vector with exact HMAC-SHA1 signature.

    RFC 5849 sections 3.1 & 3.4.1.1 originally had a known erratum where the signature was
    computed with GET instead of POST. Errata ID 2550 (verified by Peter Saint-Andre) establishes
    the true POST test vector with signature: r6/TJjbCOr97/+UU0NsvSne7s5g=
    """
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-key",
        twitter_api_key="9djdj82h48djs9d2",
        twitter_api_secret="j49sk3j29djd",
        twitter_access_token="kkk9d7dh3k39sjv7",
        twitter_access_token_secret="dh893hdasih9",
    )
    pub = LiveXPublisher(settings)

    header = pub._build_oauth1_header(
        method="POST",
        url="http://example.com/request?b5=%3D%253D&a3=a&c%40=&a2=r%20b",
        nonce="7d8f3e4a",
        timestamp="137131201",
        extra_params=[("c2", ""), ("a3", "2 q")],
        include_version=False,
    )

    assert 'oauth_signature="r6%2FTJjbCOr97%2F%2BUU0NsvSne7s5g%3D"' in header
    assert 'oauth_consumer_key="9djdj82h48djs9d2"' in header
    assert 'oauth_nonce="7d8f3e4a"' in header
    assert 'oauth_timestamp="137131201"' in header
    assert 'oauth_signature_method="HMAC-SHA1"' in header
    assert 'oauth_token="kkk9d7dh3k39sjv7"' in header


def test_rfc5849_uri_normalization_and_query_handling():
    """Validates that URI normalization strips default ports and lowercases scheme and authority."""
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-key",
        twitter_api_key="key1",
        twitter_api_secret="secret1",
        twitter_access_token="token1",
        twitter_access_token_secret="secret2",
    )
    pub = LiveXPublisher(settings)

    # Upper-case scheme, upper-case host, default port 80
    header1 = pub._build_oauth1_header(
        method="POST",
        url="HTTP://EXAMPLE.COM:80/request?param=value",
        nonce="testnonce",
        timestamp="123456789",
    )
    # Lower-case scheme, lower-case host, no port
    header2 = pub._build_oauth1_header(
        method="POST",
        url="http://example.com/request?param=value",
        nonce="testnonce",
        timestamp="123456789",
    )
    assert header1 == header2


def test_bearer_token_cannot_substitute_user_context():
    """Validates that app-only bearer token is rejected for /2/tweets User Context endpoint."""
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-key",
        twitter_bearer_token="app_only_bearer_token_123",
    )
    pub = LiveXPublisher(settings)
    headers = pub._build_headers("https://api.x.com/2/tweets")
    assert headers == {}


@pytest.mark.asyncio
async def test_publisher_distinguishes_connect_timeout_vs_ambiguous_read_timeout():
    """Validates that connect timeouts are safe to retry while read timeouts are ambiguous."""
    import httpx

    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-key",
        twitter_api_key="k",
        twitter_api_secret="s",
        twitter_access_token="t",
        twitter_access_token_secret="ts",
    )

    # 1. ConnectTimeout -> safe to retry, outcome is NOT unknown
    mock_client_connect = AsyncMock()
    mock_client_connect.post.side_effect = httpx.ConnectTimeout("Connect timed out")
    pub1 = LiveXPublisher(settings, client=mock_client_connect)
    res1 = await pub1.publish("text", report_id="rep-1")
    assert res1.ok is False
    assert res1.retryable is True
    assert res1.outcome_unknown is False

    # 2. ReadTimeout -> post-transmission, outcome is AMBIGUOUS, MUST NOT retry
    mock_client_read = AsyncMock()
    mock_client_read.post.side_effect = httpx.ReadTimeout("Read timed out")
    pub2 = LiveXPublisher(settings, client=mock_client_read)
    res2 = await pub2.publish("text", report_id="rep-1")
    assert res2.ok is False
    assert res2.retryable is False
    assert res2.outcome_unknown is True


def test_ambiguous_timeout_sets_outcome_unknown_and_stops_retries(client: TestClient, sender):
    """Validates that ambiguous timeout persists 'outcome_unknown' and halts retries."""
    import asyncio
    import uuid

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import (
        create_broadcast_request,
        execute_broadcast,
    )
    from tk_api.reports.publisher import PublishResult

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543295")

    payload = {
        "category_slug": "school",
        "title": "Gas leak hazard near school",
        "description": "Strong odor of LPG near school kitchen.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()

    queued_settings = client.app.state.settings.model_copy(update={"celery_enabled": True})

    async def run_scenario():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # 1. Create broadcast request
            b = await create_broadcast_request(
                session,
                report=rep,
                requester_id=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                settings=queued_settings,
            )
            assert b.status == "queued"
            b_id = b.id

            # 2. Mock publisher returning outcome_unknown=True
            mock_pub = AsyncMock()
            mock_pub.publish.return_value = PublishResult(
                ok=False,
                retryable=False,
                outcome_unknown=True,
                error="X API request timed out after transmission; outcome is ambiguous.",
            )

            executed = await execute_broadcast(
                session,
                broadcast_id=b_id,
                settings=queued_settings,
                publisher=mock_pub,
            )
            assert executed.status == "outcome_unknown"
            assert executed.attempts == 1

            # 3. Subsequent request returns existing outcome_unknown record
            subsequent = await create_broadcast_request(
                session,
                report=rep,
                requester_id=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                settings=queued_settings,
            )
            assert subsequent.id == b_id
            assert subsequent.status == "outcome_unknown"

    asyncio.run(run_scenario())


def test_reconcile_broadcast_outcome_procedure(client: TestClient, sender):
    """Validates the operator reconciliation procedure for 'outcome_unknown' broadcasts."""
    import asyncio
    import uuid

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import reconcile_broadcast_outcome
    from tk_api.reports.models import SocialBroadcast

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543296")

    payload = {
        "category_slug": "school",
        "title": "Collapsing structure",
        "description": "Boundary wall tilted dangerously.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = uuid.UUID(rep["id"])

    async def run_scenario():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # Seed broadcast in outcome_unknown
            b = SocialBroadcast(
                report_id=report_id,
                requested_by=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                status="outcome_unknown",
                post_text="Urgent hazard",
                attempts=1,
                max_attempts=3,
                last_error="Ambiguous timeout",
            )
            session.add(b)
            await session.commit()
            await session.refresh(b)
            b_id = b.id

            from tk_api.core.errors import ApiError

            # 1. Reconciling with outcome='published' but missing external_post_id
            # must fail with 422
            with pytest.raises(ApiError) as exc_missing:
                await reconcile_broadcast_outcome(
                    session,
                    broadcast_id=b_id,
                    outcome="published",
                    external_post_id=None,
                )
            assert exc_missing.value.status == 422
            assert exc_missing.value.kind == "missing_external_post_id"

            # 2. Reconcile as published with verified tweet ID
            reconciled = await reconcile_broadcast_outcome(
                session,
                broadcast_id=b_id,
                outcome="published",
                external_post_id="20261021998877",
                resolution_note="Verified tweet published on X account @TheekKaro",
            )
            assert reconciled.status == "published"
            assert reconciled.external_post_id == "20261021998877"
            assert reconciled.published_url == "https://x.com/TheekKaro/status/20261021998877"
            assert reconciled.published_at is not None

            # 3. Duplicate reconciliation on now-published broadcast must fail closed with 400
            with pytest.raises(ApiError) as exc_dup:
                await reconcile_broadcast_outcome(
                    session,
                    broadcast_id=b_id,
                    outcome="failed",
                    resolution_note="Duplicate attempt",
                )
            assert exc_dup.value.status == 400
            assert exc_dup.value.kind == "invalid_broadcast_status_for_reconciliation"

    asyncio.run(run_scenario())


def test_preflight_revalidation_aborts_on_visibility_change(client: TestClient, sender):
    """Validates that execute_broadcast aborts if report visibility changes before execution."""
    import asyncio
    import uuid

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import create_broadcast_request, execute_broadcast
    from tk_api.reports.models import Report

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543299")

    payload = {
        "category_slug": "school",
        "title": "Hazardous Live Wire",
        "description": "Exposed cable near school gate.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = uuid.UUID(rep["id"])
    reporter_id = uuid.UUID(rep["reporter_id"])

    queued_settings = client.app.state.settings.model_copy(update={"celery_enabled": True})

    async def run_scenario():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # 1. Create broadcast request while report is public
            broadcast = await create_broadcast_request(
                session,
                report=rep,
                requester_id=reporter_id,
                network="x",
                tone="urgent",
                settings=queued_settings,
            )
            assert broadcast.status == "queued"

            # 2. Modify report visibility to private
            db_report = await session.get(Report, report_id)
            assert db_report is not None
            db_report.visibility = "private"
            await session.commit()

            # 3. Execute broadcast: must abort during pre-flight re-validation
            mock_pub = AsyncMock()
            executed = await execute_broadcast(
                session,
                broadcast_id=broadcast.id,
                settings=client.app.state.settings,
                publisher=mock_pub,
            )
            assert executed.status == "failed"
            assert "visibility was changed from public" in str(executed.last_error).lower()
            mock_pub.publish.assert_not_called()

    asyncio.run(run_scenario())


def test_emergency_kill_switch_behavior(client: TestClient, sender):
    """Validates that TK_SOCIAL_BROADCAST_MODE=disabled halts API, queued, and sweep actions."""
    import asyncio
    import uuid

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import (
        create_broadcast_request,
        execute_broadcast,
        recover_stuck_broadcasts,
    )
    from tk_api.reports.models import SocialBroadcast

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543297")

    payload = {
        "category_slug": "school",
        "title": "Severe chemical spill",
        "description": "Hazardous drums leaking.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = uuid.UUID(rep["id"])

    disabled_settings = client.app.state.settings.model_copy(
        update={"social_broadcast_mode": "disabled"}
    )

    async def run_scenario():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            # 1. API submission with disabled mode
            b = await create_broadcast_request(
                session,
                report=rep,
                requester_id=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                settings=disabled_settings,
            )
            assert b.status == "disabled"
            assert "disabled" in str(b.last_error).lower()

            # 2. Previously queued task arriving at worker when mode was turned off
            queued_b = SocialBroadcast(
                report_id=report_id,
                requested_by=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                status="queued",
                post_text="Chemical spill hazard",
                attempts=0,
                max_attempts=3,
            )
            session.add(queued_b)
            await session.commit()
            await session.refresh(queued_b)

            mock_pub = AsyncMock()
            executed = await execute_broadcast(
                session,
                broadcast_id=queued_b.id,
                settings=disabled_settings,
                publisher=mock_pub,
            )
            assert executed.status == "disabled"
            mock_pub.publish.assert_not_called()

            # 3. Sweep recovery is completely suppressed
            swept = await recover_stuck_broadcasts(session, settings=disabled_settings)
            assert swept == []

    asyncio.run(run_scenario())


def test_stranded_live_processing_transitions_to_outcome_unknown(client: TestClient, sender):
    """Validates that a live broadcast stranded in processing transitions to outcome_unknown."""
    import asyncio
    import uuid
    from datetime import UTC, datetime, timedelta

    from tk_api.core.db import create_session_factory
    from tk_api.reports.broadcast_service import recover_stuck_broadcasts
    from tk_api.reports.models import SocialBroadcast

    admin_hdr = _admin_headers(client, sender)
    client.post("/api/v1/civic/categories", json=CATEGORY, headers=admin_hdr)
    _, citizen_hdr = _citizen_headers(client, sender, "9876543298")

    payload = {
        "category_slug": "school",
        "title": "Dangerous sinkhole",
        "description": "Massive cavity opened overnight.",
        "location": {"type": "Point", "coordinates": [77.64, 12.97]},
        "location_accuracy_m": 5.0,
        "address_hint": "Indiranagar, Bengaluru",
        "severity": "critical",
        "visibility": "public",
        "fields": VALID_FIELDS,
    }
    create_res = client.post("/api/v1/reports", json=payload, headers=citizen_hdr)
    assert create_res.status_code == 201
    rep = create_res.json()
    report_id = uuid.UUID(rep["id"])

    live_settings = client.app.state.settings.model_copy(update={"social_broadcast_mode": "live"})

    async def run_scenario():
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            stuck_b = SocialBroadcast(
                report_id=report_id,
                requested_by=uuid.UUID(rep["reporter_id"]),
                network="x",
                tone="urgent",
                status="processing",
                post_text="Sinkhole alert",
                attempts=1,
                max_attempts=3,
                updated_at=datetime.now(UTC) - timedelta(minutes=15),
            )
            session.add(stuck_b)
            await session.commit()
            await session.refresh(stuck_b)
            b_id = stuck_b.id

            recovered = await recover_stuck_broadcasts(
                session, settings=live_settings, max_age_seconds=600
            )
            assert b_id in recovered

            reloaded = await session.get(SocialBroadcast, b_id)
            assert reloaded is not None
            # In live mode, stranded processing MUST NOT be re-queued blindly
            assert reloaded.status == "outcome_unknown"
            assert "ambiguous" in str(reloaded.last_error).lower()

    asyncio.run(run_scenario())


def test_authority_verification_metadata_and_fallbacks():
    """Validates authority verification governance metadata and fallbacks."""
    # 1. Known city directory authority
    pkg = build_social_post_package(
        report_id="11111111-2222-3333-4444-555555555555",
        ticket_no="TK-BLR-001",
        title="Major Pothole on 100ft Road",
        description="Hazardous crater near junction.",
        category_slug="roads",
        severity="high",
        address_hint="Indiranagar, Bengaluru",
        location_coords=[77.64, 12.97],
    )
    assert len(pkg["authorities"]) >= 1
    primary_auth = pkg["authorities"][0]
    assert primary_auth["name"] == "BBMP (Bruhat Bengaluru Mahanagara Palike)"
    assert primary_auth["x_handle"] == "@BBMPCOMM"
    assert primary_auth["verification_status"] == "unverified"
    assert "official_verification_source" in primary_auth
    assert "verified_by" in primary_auth
    assert "last_verified_at" in primary_auth
    assert "next_review_due" in primary_auth

    # 2. Unknown location directory fallback to national / platform handles
    fallback_pkg = build_social_post_package(
        report_id="22222222-3333-4444-5555-666666666666",
        ticket_no="TK-RUR-002",
        title="Broken Culvert on Rural Route",
        description="Water overflowing across road.",
        category_slug="water",
        severity="medium",
        address_hint="Unmapped Village, Sector 99",
        location_coords=None,
    )
    assert len(fallback_pkg["authorities"]) == 2
    mohua = next(
        a
        for a in fallback_pkg["authorities"]
        if "Ministry" in a["name"] or "@MoHUA" in (a["x_handle"] or "")
    )
    platform = next(a for a in fallback_pkg["authorities"] if "Theek Karo" in a["name"])
    assert mohua["verification_status"] == "unverified"
    assert platform["verification_status"] == "verified_official"
    assert platform["official_verification_source"] == "https://theekkaro.in/about"
    assert platform["verified_by"] == "theekkaro-security"
