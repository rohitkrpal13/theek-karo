"""Phase 21 civic action orchestration tests (spec §120-§121).

Covers the full coordinated-action lifecycle (initiative → plan → AI
suggestion gate → tasks → assignment → evidence → verification → impact),
RBAC/IDOR security on every surface, volunteer-privacy guarantees of the
MCP tools, and the failure scenarios (unapproved initiative, transition
guards, verification gates, duplicate/self dependencies).

Runs on the in-memory SQLite unit schema (Base.metadata.create_all);
the 0034 migration is exercised against Postgres via integration markers.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.civic.models import Campaign
from tk_api.community.models import VolunteerProfile
from tk_api.core.db import create_session_factory
from tk_api.media.models import MediaObject
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "ph21",
    "icon": "ph21",
    "form_schema": {
        "type": "object",
        "required": ["title", "description"],
        "properties": {
            "title": {"type": "string", "minLength": 10},
            "description": {"type": "string", "minLength": 25},
        },
        "additionalProperties": False,
    },
    "verification_policy": {"min_verifications": 2, "min_locale_diversity": 1},
    "attachment_rules": {"max_files": 4, "max_size_mb": 8},
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _phone() -> str:
    return f"9{random.randrange(10**9, 10**10)}"


def _grant_role(client: TestClient, user_id: str, code: str) -> None:  # type: ignore[no-untyped-def]
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _citizen(client: TestClient, sender) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, _phone())
    return tokens["user"]["id"], _auth(tokens["access_token"])


def _role_headers(client: TestClient, sender, role: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, _phone())
    _grant_role(client, tokens["user"]["id"], role)
    return _auth(tokens["access_token"])


def _setup_category(client: TestClient, sender) -> str:  # type: ignore[no-untyped-def]
    headers = _role_headers(client, sender, "admin")
    response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
    if response.status_code == 201:
        return response.json()["id"]
    if response.status_code == 409:
        for cat in client.get("/api/v1/civic/categories").json()["items"]:
            if cat["slug"] == CATEGORY["slug"]:
                return cat["id"]
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _initiative_payload(**overrides) -> dict:  # type: ignore[no-untyped-def]
    payload = {
        "title": "Road safety blackspot survey",
        "description": "Document dangerous junctions in the district with photos and observations",
        "goal": "Map every blackspot and report to the road authority",
        "duration_days": 45,
        "expected_activities": ["Identify junctions", "Take photos", "Submit observations"],
        "evidence_requirements": {"required": ["location", "image", "observation"]},
    }
    payload.update(overrides)
    return payload


def _create_approved_initiative(  # type: ignore[no-untyped-def]
    client: TestClient, sender, *, owner: dict[str, str]
) -> dict:
    category_id = _setup_category(client, sender)
    created = client.post(
        "/api/v1/community/initiatives",
        json=_initiative_payload(category_id=category_id),
        headers=owner,
    )
    assert created.status_code == 201, created.text
    initiative = created.json()
    submitted = client.post(
        f"/api/v1/community/initiatives/{initiative['id']}/submit",
        headers=owner,
    )
    assert submitted.status_code == 200, submitted.text
    moderator = _role_headers(client, sender, "moderator")
    approved = client.post(
        f"/api/v1/community/initiatives/{initiative['id']}/review",
        json={"decision": "approve", "note": "civic and evidence-based"},
        headers=moderator,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "active"
    return approved.json()


def _create_plan(client: TestClient, initiative_id: str, headers: dict[str, str]) -> dict:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/civic-actions/plans",
        json={
            "initiative_id": initiative_id,
            "objective": "Coordinate the blackspot survey from assessment to verified outcome.",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_media(client: TestClient, user_id: str, *, status: str = "ready") -> str:  # type: ignore[no-untyped-def]
    async def seed() -> str:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            media = MediaObject(
                bucket="tests",
                object_key=f"evidence/{uuid.uuid4().hex}.jpg",
                checksum_sha256="a" * 64,
                mime_type="image/jpeg",
                size_bytes=1234,
                scan_status="clean",
                status=status,
                uploaded_by=uuid.UUID(user_id),
            )
            session.add(media)
            await session.commit()
            return str(media.id)

    return asyncio.run(seed())


# ---------------------------------------------------------------------------
# Happy-path lifecycle (§120)
# ---------------------------------------------------------------------------


class TestCoordinatedActionLifecycle:
    def test_full_plan_to_impact_cycle(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        initiator_id, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        assert plan["status"] == "PROPOSED"
        assert plan["progress"]["overall"] == 0.0

        # duplicate plan rejected
        dup = client.post(
            "/api/v1/civic-actions/plans",
            json={
                "initiative_id": initiative["id"],
                "objective": "Another objective that is long enough.",
            },
            headers=initiator,
        )
        assert dup.status_code == 409

        # AI suggestion gate: stored, tasks NOT created yet
        suggested = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/ai-suggest",
            headers=initiator,
        )
        assert suggested.status_code == 200, suggested.text
        plan = suggested.json()
        assert plan["ai_generated"] is False
        assert plan["ai_suggestion"]["ai_generated"] is True
        assert plan["tasks"] == []

        # human approval materializes tasks
        decided = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/ai-decide",
            json={"decision": "approve"},
            headers=initiator,
        )
        assert decided.status_code == 200, decided.text
        plan = decided.json()
        assert plan["ai_generated"] is True
        assert plan["status"] == "OPEN"
        assert len(plan["tasks"]) >= 3

        # assign a task to a second citizen
        volunteer_id, _ = _citizen(
            client,
            sender,
        )
        task = plan["tasks"][0]
        assigned = client.post(
            f"/api/v1/civic-actions/tasks/{task['id']}/assign",
            json={"assignee_id": volunteer_id},
            headers=initiator,
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["status"] == "ASSIGNED"

        # task transition guards: direct COMPLETED rejected
        blocked = client.patch(
            f"/api/v1/civic-actions/tasks/{task['id']}",
            json={"status": "COMPLETED"},
            headers=initiator,
        )
        assert blocked.status_code == 409
        assert blocked.json()["type"].endswith("/requires_verification")

        # assignee can advance it (owner-created task remains editable by plan owner)
        advanced = client.patch(
            f"/api/v1/civic-actions/tasks/{task['id']}",
            json={"status": "IN_PROGRESS"},
            headers=initiator,
        )
        assert advanced.status_code == 200, advanced.text
        submitted = client.patch(
            f"/api/v1/civic-actions/tasks/{task['id']}",
            json={"status": "SUBMITTED"},
            headers=initiator,
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "SUBMITTED"

        # attach approved evidence → task moves to VERIFICATION_PENDING
        media_id = _seed_media(client, initiator_id)
        evidence = client.post(
            "/api/v1/civic-actions/evidence",
            json={
                "initiative_id": initiative["id"],
                "media_id": media_id,
                "task_id": task["id"],
                "kind": "before",
            },
            headers=initiator,
        )
        assert evidence.status_code == 201, evidence.text
        assert evidence.json()["verification_status"] == "unverified"

        # evidence review by moderator → approved
        moderator = _role_headers(client, sender, "moderator")
        reviewed = client.post(
            f"/api/v1/civic-actions/evidence/{evidence.json()['id']}/review",
            json={"decision": "approved", "note": "genuine photos"},
            headers=moderator,
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["verification_status"] == "approved"

        # human outcome review approves the task → COMPLETED
        outcome = client.post(
            "/api/v1/civic-actions/reviews",
            json={
                "entity_type": "task",
                "entity_id": task["id"],
                "decision": "approved",
                "evidence_ids": [evidence.json()["id"]],
            },
            headers=initiator,
        )
        assert outcome.status_code == 201, outcome.text
        moderation_proof = client.get(
            f"/api/v1/civic-actions/plans/{plan['id']}", headers=initiator
        )
        assert moderation_proof.status_code == 200

        # complete ALL tasks so the plan can enter verification
        for task_item in plan["tasks"][1:]:
            client.patch(
                f"/api/v1/civic-actions/tasks/{task_item['id']}",
                json={"status": "IN_PROGRESS"},
                headers=initiator,
            )
            client.patch(
                f"/api/v1/civic-actions/tasks/{task_item['id']}",
                json={"status": "SUBMITTED"},
                headers=initiator,
            )
            media2 = _seed_media(client, initiator_id)
            client.post(
                "/api/v1/civic-actions/evidence",
                json={
                    "initiative_id": initiative["id"],
                    "media_id": media2,
                    "task_id": task_item["id"],
                },
                headers=initiator,
            )
            client.post(
                "/api/v1/civic-actions/reviews",
                json={
                    "entity_type": "task",
                    "entity_id": task_item["id"],
                    "decision": "approved",
                },
                headers=initiator,
            )

        plan_view = client.get(
            f"/api/v1/civic-actions/plans/{plan['id']}", headers=initiator
        ).json()
        assert plan_view["progress"]["tasks_done"] == len(plan_view["tasks"])

        # verification gate: plan → VERIFICATION_PENDING → human VERIFIED
        pending = client.patch(
            f"/api/v1/civic-actions/plans/{plan['id']}",
            json={"status": "VERIFICATION_PENDING"},
            headers=initiator,
        )
        assert pending.status_code == 200, pending.text
        verified = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/verify",
            json={"decision": "approve"},
            headers=moderator,
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "VERIFIED"

        # impact: metric + measurement (evidence required) + human approval
        metric = client.post(
            "/api/v1/civic-actions/impact/metrics",
            json={
                "plan_id": plan["id"],
                "name": "Water points mapped",
                "baseline": 0.0,
                "unit": "points",
            },
            headers=initiator,
        )
        assert metric.status_code == 201, metric.text
        measurement = client.post(
            "/api/v1/civic-actions/impact/measurements",
            json={
                "metric_id": metric.json()["id"],
                "value": 12.0,
                "evidence_id": evidence.json()["id"],
            },
            headers=initiator,
        )
        assert measurement.status_code == 201, measurement.text
        assert measurement.json()["status"] == "pending"
        decided = client.post(
            f"/api/v1/civic-actions/impact/measurements/{measurement.json()['id']}/decide",
            json={"decision": "approved"},
            headers=moderator,
        )
        assert decided.status_code == 200, decided.text
        dashboard = client.get(
            f"/api/v1/civic-actions/impact/dashboard?initiative_id={initiative['id']}",
            headers=initiator,
        ).json()
        assert dashboard["summary"]["verified_metrics"] == 1
        assert dashboard["items"][0]["latest_value"] == 12.0

        # updates feed
        update = client.post(
            "/api/v1/civic-actions/updates",
            json={
                "initiative_id": initiative["id"],
                "description": "All junctions surveyed and verified.",
            },
            headers=initiator,
        )
        assert update.status_code == 201, update.text
        updates = client.get(
            f"/api/v1/civic-actions/initiatives/{initiative['id']}/updates",
            headers=initiator,
        ).json()
        assert updates["items"][0]["status_snapshot"]["overall"] == 1.0

    def test_task_dependencies_and_comments(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        client.post(f"/api/v1/civic-actions/plans/{plan['id']}/ai-suggest", headers=initiator)
        decided = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/ai-decide",
            json={"decision": "approve"},
            headers=initiator,
        ).json()
        tasks = decided["tasks"]

        created = client.post(
            "/api/v1/civic-actions/tasks",
            json={
                "plan_id": plan["id"],
                "title": "Uses previous result",
                "priority": "HIGH",
                "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            },
            headers=initiator,
        )
        assert created.status_code == 201, created.text

        dep = client.post(
            f"/api/v1/civic-actions/tasks/{tasks[0]['id']}/dependencies",
            json={"depends_on_task_id": created.json()["id"]},
            headers=initiator,
        )
        assert dep.status_code == 201, dep.text
        self_dep = client.post(
            f"/api/v1/civic-actions/tasks/{tasks[0]['id']}/dependencies",
            json={"depends_on_task_id": tasks[0]["id"]},
            headers=initiator,
        )
        assert self_dep.status_code == 422
        dup_dep = client.post(
            f"/api/v1/civic-actions/tasks/{tasks[0]['id']}/dependencies",
            json={"depends_on_task_id": created.json()["id"]},
            headers=initiator,
        )
        assert dup_dep.status_code == 409
        removed = client.delete(
            f"/api/v1/civic-actions/tasks/{tasks[0]['id']}/dependencies/{created.json()['id']}",
            headers=initiator,
        )
        assert removed.status_code == 200, removed.text

        comment = client.post(
            f"/api/v1/civic-actions/tasks/{tasks[0]['id']}/comments",
            json={"body": "Recheck the junction checklist."},
            headers=initiator,
        )
        assert comment.status_code == 201, comment.text
        comments = client.get(
            f"/api/v1/civic-actions/tasks/{tasks[0]['id']}/comments",
            headers=initiator,
        ).json()
        assert comments["items"][0]["body"] == "Recheck the junction checklist."

    def test_milestones(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        milestone = client.post(
            "/api/v1/civic-actions/milestones",
            json={"plan_id": plan["id"], "title": "Assessment phase", "order_idx": 1},
            headers=initiator,
        )
        assert milestone.status_code == 201, milestone.text
        updated = client.patch(
            f"/api/v1/civic-actions/milestones/{milestone.json()['id']}",
            json={"status": "completed"},
            headers=initiator,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["status"] == "completed"
        plan_view = client.get(
            f"/api/v1/civic-actions/plans/{plan['id']}", headers=initiator
        ).json()
        assert plan_view["milestones"][0]["status"] == "completed"

    def test_volunteer_teams_campaigns_events(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        initiator_id, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        _create_plan(client, initiative["id"], initiator)
        category_id = _setup_category(client, sender)

        # volunteer application → decision → withdraw
        volunteer_id, volunteer = _citizen(
            client,
            sender,
        )
        app = client.post(
            "/api/v1/civic-actions/volunteer-applications",
            json={"initiative_id": initiative["id"], "message": "I document roads daily."},
            headers=volunteer,
        )
        assert app.status_code == 201, app.text
        my = client.get("/api/v1/civic-actions/volunteer-applications/my", headers=volunteer).json()
        assert len(my["items"]) == 1
        decided = client.post(
            f"/api/v1/civic-actions/volunteer-applications/{app.json()['id']}/decide",
            json={"decision": "approved"},
            headers=initiator,
        )
        assert decided.status_code == 200, decided.text
        assert decided.json()["status"] == "approved"
        listing = client.get(
            f"/api/v1/civic-actions/initiatives/{initiative['id']}/applications",
            headers=initiator,
        ).json()
        assert listing["items"][0]["status"] == "approved"

        # teams
        team = client.post(
            "/api/v1/civic-actions/teams",
            json={"initiative_id": initiative["id"], "name": "Survey Crew A"},
            headers=initiator,
        )
        assert team.status_code == 201, team.text
        added = client.post(
            f"/api/v1/civic-actions/teams/{team.json()['id']}/members",
            json={"user_id": volunteer_id, "role": "field_volunteer"},
            headers=initiator,
        )
        assert added.status_code == 201, added.text
        teams = client.get(
            f"/api/v1/civic-actions/initiatives/{initiative['id']}/teams",
            headers=initiator,
        ).json()
        assert len(teams["items"][0]["members"]) == 2

        # campaigns
        async def _seed_campaign() -> str:
            from tk_api.civic_action.models import CampaignMember

            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                campaign = Campaign(
                    category_id=uuid.UUID(category_id),
                    slug=f"campaign_{uuid.uuid4().hex[:8]}",
                    title_key="campaign.test",
                    scope={"state": "BIHAR"},
                )
                session.add(campaign)
                await session.flush()
                session.add(
                    CampaignMember(
                        campaign_id=campaign.id,
                        user_id=uuid.UUID(initiator_id),
                        role="organizer",
                    )
                )
                await session.commit()
                return str(campaign.id)

        campaign_id = asyncio.run(_seed_campaign())
        linked = client.post(
            "/api/v1/civic-actions/campaign-links",
            json={"campaign_id": campaign_id, "initiative_id": initiative["id"]},
            headers=initiator,
        )
        assert linked.status_code == 201, linked.text
        stranger_join = client.post(
            f"/api/v1/civic-actions/campaigns/{campaign_id}/join",
            headers=volunteer,
        )
        assert stranger_join.status_code == 201  # any active citizen may join

        # events: draft → submit (organizer) → publish (moderator) → join
        event = client.post(
            "/api/v1/civic-actions/events",
            json={
                "initiative_id": initiative["id"],
                "title": "Junction walk-through",
                "location": {"label": "Ward 12 circle"},
                "starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "capacity": 10,
            },
            headers=initiator,
        )
        assert event.status_code == 201, event.text
        submitted = client.patch(
            f"/api/v1/civic-actions/events/{event.json()['id']}",
            json={"status": "submitted"},
            headers=initiator,
        )
        assert submitted.status_code == 200, submitted.text
        moderator = _role_headers(client, sender, "moderator")
        published = client.patch(
            f"/api/v1/civic-actions/events/{event.json()['id']}",
            json={"status": "published"},
            headers=moderator,
        )
        assert published.status_code == 200, published.text
        joined_event = client.post(
            f"/api/v1/civic-actions/events/{event.json()['id']}/join",
            headers=volunteer,
        )
        assert joined_event.status_code == 201, joined_event.text
        full = client.post(
            f"/api/v1/civic-actions/events/{event.json()['id']}/join",
            headers=initiator,
        )
        assert full.status_code == 201  # capacity 10, only one participant
        visible = client.get(
            f"/api/v1/civic-actions/events/{event.json()['id']}", headers=volunteer
        ).json()
        assert visible["status"] == "published"
        cancelled = client.post(
            f"/api/v1/civic-actions/events/{event.json()['id']}/cancel",
            headers=volunteer,
        )
        assert cancelled.status_code == 200, cancelled.text


# ---------------------------------------------------------------------------
# Security: IDOR, RBAC, privacy (§121)
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_idor_private_plan_hidden(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        initiator_id, initiator = _citizen(
            client,
            sender,
        )
        category_id = _setup_category(client, sender)
        created = client.post(
            "/api/v1/community/initiatives",
            json=_initiative_payload(category_id=category_id),
            headers=initiator,
        ).json()

        async def _seed_plan() -> str:
            from tk_api.civic_action.models import ActionPlan

            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                plan = ActionPlan(
                    initiative_id=uuid.UUID(created["id"]),
                    objective="Coordinate the survey from start to verified outcome.",
                    owner_id=uuid.UUID(initiator_id),
                    status="PROPOSED",
                    created_by=uuid.UUID(initiator_id),
                )
                session.add(plan)
                await session.commit()
                return str(plan.id)

        plan_id = asyncio.run(_seed_plan())
        _, outsider = _citizen(
            client,
            sender,
        )
        hidden = client.get(f"/api/v1/civic-actions/plans/{plan_id}", headers=outsider)
        assert hidden.status_code == 404  # draft initiative not public
        visible = client.get(f"/api/v1/civic-actions/plans/{plan_id}", headers=initiator)
        assert visible.status_code == 200

    def test_rbac_plan_tasks(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        _, outsider = _citizen(
            client,
            sender,
        )
        forbidden = client.patch(
            f"/api/v1/civic-actions/plans/{plan['id']}",
            json={"status": "OPEN"},
            headers=outsider,
        )
        assert forbidden.status_code == 403
        task = client.post(
            "/api/v1/civic-actions/tasks",
            json={"plan_id": plan["id"], "title": "Secret task"},
            headers=outsider,
        )
        assert task.status_code == 403
        suggest = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/ai-suggest",
            headers=outsider,
        )
        assert suggest.status_code == 403

    def test_evidence_media_ownership(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        initiator_id, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        _, other = _citizen(
            client,
            sender,
        )
        media_id = _seed_media(client, initiator_id)
        stolen = client.post(
            "/api/v1/civic-actions/evidence",
            json={
                "initiative_id": initiative["id"],
                "media_id": media_id,
            },
            headers=other,
        )
        assert stolen.status_code == 403
        assert stolen.json()["type"].endswith("/media_not_owned")

    def test_evidence_review_rbac(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        initiator_id, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        _, random_user = _citizen(
            client,
            sender,
        )
        media_id = _seed_media(client, initiator_id)
        evidence = client.post(
            "/api/v1/civic-actions/evidence",
            json={"initiative_id": initiative["id"], "media_id": media_id},
            headers=initiator,
        ).json()
        rejected = client.post(
            f"/api/v1/civic-actions/evidence/{evidence['id']}/review",
            json={"decision": "approved"},
            headers=random_user,
        )
        assert rejected.status_code == 403

    def test_volunteer_applications_rbac(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        _, applicant = _citizen(
            client,
            sender,
        )
        app = client.post(
            "/api/v1/civic-actions/volunteer-applications",
            json={"initiative_id": initiative["id"]},
            headers=applicant,
        )
        assert app.status_code == 201
        _, stranger = _citizen(
            client,
            sender,
        )
        forbidden = client.post(
            f"/api/v1/civic-actions/volunteer-applications/{app.json()['id']}/decide",
            json={"decision": "approved"},
            headers=stranger,
        )
        assert forbidden.status_code == 403
        listing = client.get(
            f"/api/v1/civic-actions/initiatives/{initiative['id']}/applications",
            headers=stranger,
        )
        assert listing.status_code == 403

    def test_event_edit_rbac(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        event = client.post(
            "/api/v1/civic-actions/events",
            json={
                "initiative_id": initiative["id"],
                "title": "Open meeting",
                "location": {"label": "Community hall"},
                "starts_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
            headers=initiator,
        ).json()
        _, outsider = _citizen(
            client,
            sender,
        )
        forbidden = client.patch(
            f"/api/v1/civic-actions/events/{event['id']}",
            json={"status": "published"},
            headers=outsider,
        )
        assert forbidden.status_code == 403
        # organizer may submit but not publish
        organizer_submit = client.patch(
            f"/api/v1/civic-actions/events/{event['id']}",
            json={"status": "submitted"},
            headers=initiator,
        )
        assert organizer_submit.status_code == 200
        organizer_publish = client.patch(
            f"/api/v1/civic-actions/events/{event['id']}",
            json={"status": "published"},
            headers=initiator,
        )
        assert organizer_publish.status_code == 403

    def test_measurement_rbac(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        initiator_id, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        metric = client.post(
            "/api/v1/civic-actions/impact/metrics",
            json={"plan_id": plan["id"], "name": "Trees planted", "baseline": 0.0},
            headers=initiator,
        ).json()
        media_id = _seed_media(client, initiator_id)
        evidence = client.post(
            "/api/v1/civic-actions/evidence",
            json={"initiative_id": initiative["id"], "media_id": media_id},
            headers=initiator,
        ).json()
        client.post(
            f"/api/v1/civic-actions/evidence/{evidence['id']}/review",
            json={"decision": "approved"},
            headers=_role_headers(client, sender, "moderator"),
        )
        measurement = client.post(
            "/api/v1/civic-actions/impact/measurements",
            json={"metric_id": metric["id"], "value": 5.0, "evidence_id": evidence["id"]},
            headers=initiator,
        ).json()
        _, outsider = _citizen(
            client,
            sender,
        )
        forbidden = client.post(
            f"/api/v1/civic-actions/impact/measurements/{measurement['id']}/decide",
            json={"decision": "approved"},
            headers=outsider,
        )
        assert forbidden.status_code == 403

    def test_ai_tool_volunteer_matches_never_leak_pii(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)

        async def _seed_profile() -> None:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                user = User(
                    email=f"vol_{uuid.uuid4().hex[:8]}@example.com",
                    display_name="Volunteer A",
                    status="active",
                )
                session.add(user)
                await session.flush()
                session.add(
                    VolunteerProfile(
                        user_id=user.id,
                        languages=["hi"],
                        skills=["photography", "mapping"],
                        areas=["patna"],
                        availability={"weekends": True},
                    )
                )
                await session.commit()

        asyncio.run(_seed_profile())
        from tk_api.ai.tools import ToolRegistry

        async def _run_tool() -> dict:
            factory = create_session_factory(client.app.state.engine)
            async with factory() as session:
                return await ToolRegistry().execute(
                    session,
                    "find_volunteer_matches",
                    {"initiative_id": initiative["id"]},
                )

        matches = asyncio.run(_run_tool())
        assert matches["matches"]
        row = matches["matches"][0]
        assert "email" not in row
        assert "phone" not in row
        assert "address" not in row
        assert row.get("skills") == ["photography", "mapping"]


# ---------------------------------------------------------------------------
# Failure scenarios (§121)
# ---------------------------------------------------------------------------


class TestFailureScenarios:
    def test_plan_requires_approved_initiative(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        category_id = _setup_category(client, sender)
        draft = client.post(
            "/api/v1/community/initiatives",
            json=_initiative_payload(category_id=category_id),
            headers=initiator,
        ).json()
        rejected = client.post(
            "/api/v1/civic-actions/plans",
            json={
                "initiative_id": draft["id"],
                "objective": "Coordinate the survey from start to verified outcome.",
            },
            headers=initiator,
        )
        assert rejected.status_code == 409
        assert rejected.json()["type"].endswith("/initiative_not_approved")

    def test_ai_decision_without_suggestion(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        rejected = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/ai-decide",
            json={"decision": "approve"},
            headers=initiator,
        )
        assert rejected.status_code == 409
        assert rejected.json()["type"].endswith("/no_ai_suggestion")

    def test_ai_rejection_wipes_suggestion(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        client.post(f"/api/v1/civic-actions/plans/{plan['id']}/ai-suggest", headers=initiator)
        rejected = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/ai-decide",
            json={"decision": "reject"},
            headers=initiator,
        )
        assert rejected.status_code == 200
        plan_view = client.get(
            f"/api/v1/civic-actions/plans/{plan['id']}", headers=initiator
        ).json()
        assert plan_view["ai_suggestion"] is None
        assert plan_view["ai_generated"] is False
        assert plan_view["tasks"] == []

    def test_verification_gate_blocks_incomplete_plan(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        client.post(f"/api/v1/civic-actions/plans/{plan['id']}/ai-suggest", headers=initiator)
        plan = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/ai-decide",
            json={"decision": "approve"},
            headers=initiator,
        ).json()
        blocked = client.patch(
            f"/api/v1/civic-actions/plans/{plan['id']}",
            json={"status": "VERIFICATION_PENDING"},
            headers=initiator,
        )
        assert blocked.status_code == 409
        assert blocked.json()["type"].endswith("/tasks_incomplete")

    def test_verify_wrong_state(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        verified = client.post(
            f"/api/v1/civic-actions/plans/{plan['id']}/verify",
            json={"decision": "approve"},
            headers=initiator,
        )
        assert verified.status_code == 409
        assert verified.json()["type"].endswith("/not_verification_pending")

    def test_task_delete_locked(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        task = client.post(
            "/api/v1/civic-actions/tasks",
            json={"plan_id": plan["id"], "title": "Locked task"},
            headers=initiator,
        ).json()
        client.patch(
            f"/api/v1/civic-actions/tasks/{task['id']}",
            json={"status": "IN_PROGRESS"},
            headers=initiator,
        )
        locked = client.delete(f"/api/v1/civic-actions/tasks/{task['id']}", headers=initiator)
        assert locked.status_code == 200  # not completed → deletable
        missing = client.delete(f"/api/v1/civic-actions/tasks/{task['id']}", headers=initiator)
        assert missing.status_code == 404

    def test_cross_plan_dependency_rejected(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        task_a = client.post(
            "/api/v1/civic-actions/tasks",
            json={"plan_id": plan["id"], "title": "Task A"},
            headers=initiator,
        ).json()
        other_plan = _create_plan(
            client, _create_approved_initiative(client, sender, owner=initiator)["id"], initiator
        )
        task_b = client.post(
            "/api/v1/civic-actions/tasks",
            json={"plan_id": other_plan["id"], "title": "Task B"},
            headers=initiator,
        ).json()
        rejected = client.post(
            f"/api/v1/civic-actions/tasks/{task_a['id']}/dependencies",
            json={"depends_on_task_id": task_b["id"]},
            headers=initiator,
        )
        assert rejected.status_code == 422
        assert rejected.json()["type"].endswith("/cross_plan_dependency")

    def test_measurement_requires_approved_evidence(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        initiator_id, initiator = _citizen(
            client,
            sender,
        )
        initiative = _create_approved_initiative(client, sender, owner=initiator)
        plan = _create_plan(client, initiative["id"], initiator)
        metric = client.post(
            "/api/v1/civic-actions/impact/metrics",
            json={"plan_id": plan["id"], "name": "Potholes filled", "baseline": 0.0},
            headers=initiator,
        ).json()
        media_id = _seed_media(client, initiator_id)
        evidence = client.post(
            "/api/v1/civic-actions/evidence",
            json={"initiative_id": initiative["id"], "media_id": media_id},
            headers=initiator,
        ).json()
        rejected = client.post(
            "/api/v1/civic-actions/impact/measurements",
            json={"metric_id": metric["id"], "value": 3.0, "evidence_id": evidence["id"]},
            headers=initiator,
        )
        assert rejected.status_code == 409
        assert rejected.json()["type"].endswith("/evidence_not_approved")
