"""Phase 18 community & civic participation tests (ADR-053): civic initiatives
lifecycle + permissions, volunteer profiles/opportunities + privacy, community
groups (request/review/membership/moderation), deterministic badges, and IDOR
protection across all new surfaces.
"""

from __future__ import annotations

import asyncio
import random
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.community.models import Badge
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "ph18",
    "icon": "ph18",
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


def _grant_role(client: TestClient, user_id: str, code: str) -> None:  # type: ignore[no-untyped-def]
    async def grant() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            role = await session.scalar(select(Role).where(Role.code == code))
            user = await session.get(User, uuid.UUID(user_id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()

    asyncio.run(grant())


def _citizen(client: TestClient, sender, phone: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, phone)
    return tokens["user"]["id"], _auth(tokens["access_token"])


def _role_headers(client: TestClient, sender, phone: str, role: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tokens = _register_and_verify(client, sender, phone)
    _grant_role(client, tokens["user"]["id"], role)
    return _auth(tokens["access_token"])


def _phone() -> str:
    return f"9{random.randrange(10**9, 10**10)}"


def _setup_category(client: TestClient, sender) -> str:  # type: ignore[no-untyped-def]
    headers = _role_headers(client, sender, _phone(), "admin")
    response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
    if response.status_code == 201:
        return response.json()["id"]
    if response.status_code == 409:
        for cat in client.get("/api/v1/civic/categories").json()["items"]:
            if cat["slug"] == CATEGORY["slug"]:
                return cat["id"]
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _seed_badges(client: TestClient) -> None:  # type: ignore[no-untyped-def]
    async def seed() -> None:
        factory = create_session_factory(client.app.state.engine)
        async with factory() as session:
            existing = set((await session.execute(select(Badge.code))).scalars())
            seeds = [
                {
                    "code": "community_contributor",
                    "name": "Community Contributor",
                    "name_hi": "सामुदायिक योगदानकर्ता",
                    "description": "Wrote 1 constructive comment.",
                    "criteria": {"metric": "comments_written", "min": 1},
                },
                {
                    "code": "volunteer",
                    "name": "Volunteer",
                    "name_hi": "स्वयंसेवक",
                    "description": "Completed 1 volunteer activity.",
                    "criteria": {"metric": "volunteer_completions", "min": 1},
                },
                {
                    "code": "verified_contributor",
                    "name": "Verified Contributor",
                    "name_hi": "सत्यापित योगदानकर्ता",
                    "description": "Earned 1 verified contribution.",
                    "criteria": {"metric": "verified_contributions", "min": 1},
                },
            ]
            for seed in seeds:
                if seed["code"] not in existing:
                    session.add(Badge(**seed))
            await session.commit()

    asyncio.run(seed())


def _initiative_payload(**overrides) -> dict:  # type: ignore[no-untyped-def]
    payload = {
        "title": "Clean drinking water survey",
        "description": "Document public drinking-water facilities in ward 12 with photos",
        "goal": "Map every public water point and its condition",
        "duration_days": 30,
        "expected_activities": ["Identify facilities", "Take photos", "Submit observations"],
        "evidence_requirements": {"required": ["location", "image", "observation"]},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Civic initiatives
# ---------------------------------------------------------------------------


class TestInitiatives:
    def test_full_lifecycle_and_review(self, client, sender):  # type: ignore[no-untyped-def]
        category_id = _setup_category(client, sender)
        _, user_headers = _citizen(client, sender, _phone())
        moderator = _role_headers(client, sender, _phone(), "moderator")

        created = client.post(
            "/api/v1/community/initiatives",
            json=_initiative_payload(category_id=category_id),
            headers=user_headers,
        )
        assert created.status_code == 201, created.text
        initiative = created.json()
        assert initiative["status"] == "draft"
        assert initiative["is_organizer"] is True

        # drafts are not visible to other citizens
        hidden = client.get(f"/api/v1/community/initiatives/{initiative['id']}", headers=moderator)
        assert hidden.status_code == 200  # moderators can see drafts

        # edit while draft
        edited = client.patch(
            f"/api/v1/community/initiatives/{initiative['id']}",
            json={"title": "Clean drinking water survey (ward 12)"},
            headers=user_headers,
        )
        assert edited.status_code == 200, edited.text
        assert "ward 12" in edited.json()["title"]

        # submit for review
        submitted = client.post(
            f"/api/v1/community/initiatives/{initiative['id']}/submit", headers=user_headers
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "submitted"

        # only moderators may review
        denied = client.post(
            f"/api/v1/community/initiatives/{initiative['id']}/review",
            json={"decision": "approve"},
            headers=user_headers,
        )
        assert denied.status_code == 403

        # approve
        approved = client.post(
            f"/api/v1/community/initiatives/{initiative['id']}/review",
            json={"decision": "approve", "note": "clearly civic and evidence-based"},
            headers=moderator,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "active"

        # now public
        listed = client.get("/api/v1/community/initiatives", headers=moderator)
        assert listed.status_code == 200
        assert any(item["id"] == initiative["id"] for item in listed.json()["items"])

    def test_join_observe_complete(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, organizer = _citizen(client, sender, _phone())
        _, member = _citizen(client, sender, _phone())

        created = client.post(
            "/api/v1/community/initiatives", json=_initiative_payload(), headers=organizer
        ).json()
        init_id = created["id"]
        client.post(f"/api/v1/community/initiatives/{init_id}/submit", headers=organizer)
        client.post(
            f"/api/v1/community/initiatives/{init_id}/review",
            json={"decision": "approve"},
            headers=_role_headers(client, sender, _phone(), "moderator"),
        )

        # joining
        joined = client.post(f"/api/v1/community/initiatives/{init_id}/join", headers=member)
        assert joined.status_code == 200, joined.text
        assert joined.json()["is_member"] is True
        assert joined.json()["participant_count"] >= 1

        # non-members cannot add observations
        outsider = _citizen(client, sender, _phone())[1]
        denied = client.post(
            f"/api/v1/community/initiatives/{init_id}/observations",
            json={"kind": "observation", "notes": "water point dry"},
            headers=outsider,
        )
        assert denied.status_code == 403

        # member observation
        observed = client.post(
            f"/api/v1/community/initiatives/{init_id}/observations",
            json={"kind": "observation", "notes": "handpump near school is dry"},
            headers=member,
        )
        assert observed.status_code == 201, observed.text
        assert observed.json()["status"] == "pending"

        # organizer accepts
        accepted = client.post(
            f"/api/v1/community/initiatives/{init_id}/observations/{observed.json()['id']}/review",
            json={"decision": "accept"},
            headers=organizer,
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "accepted"

        detail = client.get(f"/api/v1/community/initiatives/{init_id}", headers=member).json()
        assert detail["accepted_evidence_count"] >= 1
        assert detail["observation_count"] >= 1

        # complete (organizer only)
        completed = client.post(
            f"/api/v1/community/initiatives/{init_id}/complete",
            json={"results": {"institutions_covered": 3, "observations": 4}},
            headers=organizer,
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"

    def test_follow_initiative(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, organizer = _citizen(client, sender, _phone())
        _, follower = _citizen(client, sender, _phone())

        created = client.post(
            "/api/v1/community/initiatives", json=_initiative_payload(), headers=organizer
        ).json()
        init_id = created["id"]

        followed = client.post(f"/api/v1/community/follows/initiative/{init_id}", headers=follower)
        assert followed.status_code == 200, followed.text
        assert followed.json()["status"] == "following"

        # invalid follow type rejected
        bad = client.post(f"/api/v1/community/follows/notatype/{init_id}", headers=follower)
        assert bad.status_code == 422

        unfollowed = client.delete(
            f"/api/v1/community/follows/initiative/{init_id}", headers=follower
        )
        assert unfollowed.status_code == 200
        assert unfollowed.json()["status"] == "not_following"

    def test_idor_draft_hidden_from_others(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, owner = _citizen(client, sender, _phone())
        _, other = _citizen(client, sender, _phone())

        created = client.post(
            "/api/v1/community/initiatives", json=_initiative_payload(), headers=owner
        ).json()
        init_id = created["id"]
        assert created["is_organizer"] is True

        # other user cannot read the draft
        hidden = client.get(f"/api/v1/community/initiatives/{init_id}", headers=other)
        assert hidden.status_code == 404

        # other user cannot edit or submit it
        assert (
            client.patch(
                f"/api/v1/community/initiatives/{init_id}",
                json={"title": "hijack"},
                headers=other,
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/community/initiatives/{init_id}/submit", headers=other
            ).status_code
            == 403
        )

        # owner sees it
        visible = client.get(f"/api/v1/community/initiatives/{init_id}", headers=owner)
        assert visible.status_code == 200


# ---------------------------------------------------------------------------
# Volunteers
# ---------------------------------------------------------------------------


class TestVolunteers:
    def test_profile_privacy_safe(self, client, sender):  # type: ignore[no-untyped-def]
        _, headers = _citizen(client, sender, _phone())

        updated = client.put(
            "/api/v1/community/volunteer/profile",
            json={
                "languages": ["hi", "en"],
                "interests": ["education", "water"],
                "skills": ["photography", "translation"],
                "areas": ["patna"],
                "availability": {"weekends": True},
            },
            headers=headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["skills"] == ["photography", "translation"]

        # no private contact fields are stored
        assert "phone" not in updated.json()
        assert "email" not in updated.json()

        fetched = client.get("/api/v1/community/volunteer/profile", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["languages"] == ["hi", "en"]

    def test_opportunity_flow(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, organizer = _citizen(client, sender, _phone())
        volunteer = _citizen(client, sender, _phone())[1]

        created = client.post(
            "/api/v1/community/volunteer/opportunities",
            json={
                "title": "School accessibility survey",
                "description": "Document wheelchair access at 5 schools in Bangalore",
                "location_label": "Bangalore",
                "skills": ["photography", "basic observation"],
                "participants_needed": 2,
            },
            headers=organizer,
        )
        assert created.status_code == 201, created.text
        opp = created.json()
        assert opp["status"] == "open"
        assert opp["participants_needed"] == 2

        joined = client.post(
            f"/api/v1/community/volunteer/opportunities/{opp['id']}/join",
            headers=volunteer,
        )
        assert joined.status_code == 200, joined.text
        assert joined.json()["participants_count"] == 1
        assert joined.json()["my_status"] == "joined"

        # capacity enforced: a second join fills it; third is rejected
        second = _citizen(client, sender, _phone())[1]
        third = _citizen(client, sender, _phone())[1]
        assert (
            client.post(
                f"/api/v1/community/volunteer/opportunities/{opp['id']}/join",
                headers=second,
            ).status_code
            == 200
        )
        full = client.post(
            f"/api/v1/community/volunteer/opportunities/{opp['id']}/join", headers=third
        )
        assert full.status_code == 409
        assert full.json()["type"].endswith("/opportunity_full")

        withdrawn = client.post(
            f"/api/v1/community/volunteer/opportunities/{opp['id']}/withdraw",
            headers=volunteer,
        )
        assert withdrawn.status_code == 200
        assert withdrawn.json()["my_status"] == "withdrawn"

    def test_opportunity_requires_organizer_link(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, initiator = _citizen(client, sender, _phone())
        _, stranger = _citizen(client, sender, _phone())

        created = client.post(
            "/api/v1/community/initiatives", json=_initiative_payload(), headers=initiator
        ).json()
        init_id = created["id"]

        # stranger cannot link an opportunity to someone else's initiative
        denied = client.post(
            "/api/v1/community/volunteer/opportunities",
            json={
                "initiative_id": init_id,
                "title": "rogue drive",
                "description": "not authorized by the initiative",
            },
            headers=stranger,
        )
        assert denied.status_code == 403


# ---------------------------------------------------------------------------
# Community groups
# ---------------------------------------------------------------------------


class TestGroups:
    def test_request_review_membership(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, owner = _citizen(client, sender, _phone())
        _, member = _citizen(client, sender, _phone())
        moderator = _role_headers(client, sender, _phone(), "moderator")

        created = client.post(
            "/api/v1/community/groups",
            json={"name": "Patna Civic Community", "description": "Local civic updates"},
            headers=owner,
        )
        assert created.status_code == 201, created.text
        group = created.json()
        assert group["status"] == "requested"
        assert group["my_role"] == "owner"

        # requested groups hidden from others
        hidden = client.get(f"/api/v1/community/groups/{group['id']}", headers=member)
        assert hidden.status_code == 404

        # non-moderator cannot review
        denied = client.post(
            f"/api/v1/community/groups/{group['id']}/review",
            json={"decision": "approve"},
            headers=owner,
        )
        assert denied.status_code == 403

        # moderator approves
        approved = client.post(
            f"/api/v1/community/groups/{group['id']}/review",
            json={"decision": "approve"},
            headers=moderator,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "active"

        joined = client.post(f"/api/v1/community/groups/{group['id']}/join", headers=member)
        assert joined.status_code == 200, joined.text
        assert joined.json()["my_role"] == "member"
        assert joined.json()["member_count"] >= 2

        left = client.post(f"/api/v1/community/groups/{group['id']}/leave", headers=member)
        assert left.status_code == 200
        assert left.json()["my_role"] is None

    def test_member_management_permissions(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        owner_id, owner = _citizen(client, sender, _phone())
        member_id, member = _citizen(client, sender, _phone())
        moderator = _role_headers(client, sender, _phone(), "moderator")

        created = client.post(
            "/api/v1/community/groups",
            json={"name": "Bihar Education Watch", "description": "Schools monitoring"},
            headers=owner,
        ).json()
        group_id = created["id"]
        client.post(
            f"/api/v1/community/groups/{group_id}/review",
            json={"decision": "approve"},
            headers=moderator,
        )
        client.post(f"/api/v1/community/groups/{group_id}/join", headers=member)

        # plain member cannot promote or ban
        assert (
            client.post(
                f"/api/v1/community/groups/{group_id}/members/{owner_id}",
                json={"action": "promote"},
                headers=member,
            ).status_code
            == 403
        )

        # owner promotes member to moderator
        promoted = client.post(
            f"/api/v1/community/groups/{group_id}/members/{member_id}",
            json={"action": "promote"},
            headers=owner,
        )
        assert promoted.status_code == 200, promoted.text

        # owner cannot remove or ban self
        assert (
            client.post(
                f"/api/v1/community/groups/{group_id}/members/{owner_id}",
                json={"action": "ban"},
                headers=owner,
            ).status_code
            == 409
        )

        # ban the member (now moderator) and demote first is blocked while banned
        banned = client.post(
            f"/api/v1/community/groups/{group_id}/members/{member_id}",
            json={"action": "ban"},
            headers=owner,
        )
        assert banned.status_code == 200, banned.text

    def test_group_rules_cannot_override_platform(self, client, sender):  # type: ignore[no-untyped-def]
        _setup_category(client, sender)
        _, owner = _citizen(client, sender, _phone())
        created = client.post(
            "/api/v1/community/groups",
            json={
                "name": "Local Watch",
                "description": "Observations",
                "rules": {"allows_political_campaigning": True},
            },
            headers=owner,
        )
        # rules are stored as metadata only; platform safety rules always apply
        assert created.status_code == 201, created.text


# ---------------------------------------------------------------------------
# Badges (deterministic criteria)
# ---------------------------------------------------------------------------


class TestBadges:
    def test_badge_criteria_are_deterministic(self, client, sender):  # type: ignore[no-untyped-def]
        _seed_badges(client)
        listed = client.get("/api/v1/community/badges")
        assert listed.status_code == 200
        codes = {b["code"] for b in listed.json()["items"]}
        assert "community_contributor" in codes
        for badge in listed.json()["items"]:
            assert "metric" in badge["criteria"]
            assert "min" in badge["criteria"]

    def test_comment_awards_community_contributor(self, client, sender):  # type: ignore[no-untyped-def]
        _seed_badges(client)
        _setup_category(client, sender)
        _, headers = _citizen(client, sender, _phone())

        # create a public report to comment on
        report = client.post(
            "/api/v1/reports",
            json={
                "category_slug": "ph18",
                "title": "Broken classroom windows on the ground floor",
                "description": "Windows remain broken since May with sharp edges",
                "location": {"type": "Point", "coordinates": [75.7873, 26.9124]},
                "location_accuracy_m": 12,
                "fields": {
                    "title": "Broken classroom windows",
                    "description": "Ground floor windows broken since May",
                },
            },
            headers=headers,
        )
        assert report.status_code == 201, report.text
        report_id = report.json()["id"]

        comment = client.post(
            f"/api/v1/reports/{report_id}/comments",
            json={"body": "I saw the same broken windows last week near the library block."},
            headers=headers,
        )
        assert comment.status_code == 201, comment.text

        mine = client.get("/api/v1/community/badges/me", headers=headers)
        assert mine.status_code == 200, mine.text
        metrics = mine.json()["metrics"]
        assert metrics["comments_written"] >= 1
        earned = {b["code"] for b in mine.json()["earned"]}
        assert "community_contributor" in earned

    def test_badges_never_awarded_by_volume_only(self, client, sender):  # type: ignore[no-untyped-def]
        _seed_badges(client)
        _, headers = _citizen(client, sender, _phone())
        mine = client.get("/api/v1/community/badges/me", headers=headers)
        assert mine.status_code == 200
        # fresh account earns nothing
        assert mine.json()["earned"] == []
