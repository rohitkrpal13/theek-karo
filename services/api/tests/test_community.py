"""Phase 13 community tests (API.md §10, PRD §8, §15): feed ranking + tabs,
threaded comments (depth <= 2), moderation, reactions (one per user per report),
saves, follows, blocks (privacy), public profiles, share previews, moderation
queue, notification grouping + locked preferences, and IDOR protection."""

from __future__ import annotations

import asyncio
import random
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import _register_and_verify
from tk_api.core.db import create_session_factory
from tk_api.users.models import Role, User, UserRole

CATEGORY = {
    "slug": "ph13",
    "icon": "ph13",
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

LOCATION = {"type": "Point", "coordinates": [75.7873, 26.9124]}

VALID_FIELDS = {
    "title": "Broken classroom windows",
    "description": "Ground floor windows broken since May",
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


def _setup(client: TestClient, sender) -> str:  # type: ignore[no-untyped-def]
    headers = _role_headers(client, sender, f"9{random.randrange(10**9, 10**10)}", "admin")
    response = client.post("/api/v1/civic/categories", json=CATEGORY, headers=headers)
    if response.status_code == 201:
        return response.json()["id"]
    if response.status_code == 409:
        categories = client.get("/api/v1/civic/categories")
        for cat in categories.json()["items"]:
            if cat["slug"] == CATEGORY["slug"]:
                return cat["id"]
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _submit(
    client: TestClient, headers: dict[str, str], title: str | None = None, **overrides
) -> dict:  # type: ignore[no-untyped-def]
    payload = {
        "category_slug": "ph13",
        "title": title or "Broken classroom windows on ground floor",
        "description": "Windows on the ground floor remain broken since May with sharp edges",
        "location": LOCATION,
        "location_accuracy_m": 12,
        "fields": VALID_FIELDS,
        **overrides,
    }
    response = client.post("/api/v1/reports", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _set_username(client: TestClient, headers: dict[str, str], username: str) -> None:  # type: ignore[no-untyped-def]
    response = client.patch("/api/v1/users/me", json={"username": username}, headers=headers)
    assert response.status_code == 200, response.text


def _comment(client: TestClient, report_id: str, headers: dict[str, str], body: str) -> dict:  # type: ignore[no-untyped-def]
    response = client.post(
        f"/api/v1/reports/{report_id}/comments", json={"body": body}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestFeed:
    def test_requires_auth(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get("/api/v1/feed").status_code == 401

    def test_invalid_tab(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, headers = _citizen(client, sender, "9876543001")
        response = client.get("/api/v1/feed?tab=bogus", headers=headers)
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_feed_tab")

    def test_for_you_ranked_with_explanation(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, reporter_headers = _citizen(client, sender, "9876543002")
        report = _submit(client, reporter_headers)
        _, viewer_headers = _citizen(client, sender, "9876543003")

        response = client.get("/api/v1/feed?tab=for_you", headers=viewer_headers)
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(item["id"] == report["id"] for item in items)
        card = next(item for item in items if item["id"] == report["id"])
        explanation = card["score_explanation"]
        assert set(explanation["components"]) >= {
            "score",
            "recency",
            "relevance",
            "follow",
            "verification",
            "engagement",
        }
        assert isinstance(explanation["reasons"], list)
        assert card["stats"]["comments"] == 0
        assert card["my_reaction"] is None
        assert "email" not in card["reporter"]
        assert "phone" not in card["reporter"]

    def test_latest_tab_and_cursor_pagination(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h1 = _citizen(client, sender, "9876543004")
        _, h2 = _citizen(client, sender, "9876543005")
        for i in range(3):
            _submit(client, h1, title=f"First issue number {i} on the ground floor")
            _submit(client, h2, title=f"Second issue number {i} on the ground floor")

        first = client.get("/api/v1/feed?tab=latest&limit=2", headers=h1)
        assert first.status_code == 200
        body = first.json()
        assert len(body["items"]) == 2
        assert body["next_cursor"] is not None
        assert body["has_more"] is True
        second = client.get(
            f"/api/v1/feed?tab=latest&limit=2&cursor={body['next_cursor']}", headers=h1
        )
        assert second.status_code == 200
        ids1 = {item["id"] for item in body["items"]}
        ids2 = {item["id"] for item in second.json()["items"]}
        assert not ids1 & ids2
        assert len(second.json()["items"]) == 2

    def test_private_reports_excluded(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, reporter_headers = _citizen(client, sender, "9876543006")
        _submit(client, reporter_headers, visibility="private")
        _, viewer_headers = _citizen(client, sender, "9876543007")
        response = client.get("/api/v1/feed", headers=viewer_headers)
        assert response.json()["items"] == []

    def test_geography_tab_requires_boundary(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, headers = _citizen(client, sender, "9876543008")
        response = client.get("/api/v1/feed?tab=geography", headers=headers)
        assert response.status_code == 422

    def test_following_tab_contains_followed_authors(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        author_id, author_headers = _citizen(client, sender, "9876543009")
        report = _submit(client, author_headers)
        _, viewer_headers = _citizen(client, sender, "9876543010")

        followed = client.post(
            f"/api/v1/community/follows/user/{author_id}", headers=viewer_headers
        )
        assert followed.status_code == 200
        response = client.get("/api/v1/feed?tab=following", headers=viewer_headers)
        body = response.json()
        assert report["id"] in {item["id"] for item in body["items"]}
        card = next(item for item in body["items"] if item["id"] == report["id"])
        assert "you follow this reporter" in card["score_explanation"]["reasons"]


class TestComments:
    def test_threaded_comments_and_depth_limit(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, reporter_headers = _citizen(client, sender, "9876543011")
        report = _submit(client, reporter_headers)
        _, user_headers = _citizen(client, sender, "9876543012")

        top = _comment(client, report["id"], user_headers, "A top-level comment here")
        reply = client.post(
            f"/api/v1/community/reports/{report['id']}/comments/{top['id']}/replies",
            json={"body": "A reply is allowed and should be fine"},
            headers=reporter_headers,
        )
        assert reply.status_code == 201, reply.text

        nested = client.post(
            f"/api/v1/community/reports/{report['id']}/comments/{reply.json()['id']}/replies",
            json={"body": "A reply to a reply must be rejected"},
            headers=user_headers,
        )
        assert nested.status_code == 422
        assert nested.json()["type"].endswith("/max_comment_depth")

        thread = client.get(
            f"/api/v1/community/reports/{report['id']}/comments", headers=user_headers
        )
        assert thread.status_code == 200
        items = thread.json()["items"]
        assert items[0]["id"] == top["id"]
        assert len(items[0]["replies"]) == 1

    def test_edit_own_comment_but_not_others(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h1 = _citizen(client, sender, "9876543013")
        report = _submit(client, h1)
        _, h2 = _citizen(client, sender, "9876543014")
        created = _comment(client, report["id"], h1, "This comment belongs to user one")

        edited = client.patch(
            f"/api/v1/community/comments/{created['id']}",
            json={"body": "Edited version of the comment text"},
            headers=h1,
        )
        assert edited.status_code == 200
        assert edited.json()["edited_at"] is not None

        forbidden = client.patch(
            f"/api/v1/community/comments/{created['id']}",
            json={"body": "Unauthorized edit attempt"},
            headers=h2,
        )
        assert forbidden.status_code == 403

    def test_remove_by_author_restore_by_moderator(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, author_headers = _citizen(client, sender, "9876543015")
        report = _submit(client, author_headers)
        created = _comment(client, report["id"], author_headers, "A comment to remove")
        _, h2 = _citizen(client, sender, "9876543016")

        removed = client.post(
            f"/api/v1/community/comments/{created['id']}/remove",
            json={"reason": "I changed my mind"},
            headers=author_headers,
        )
        assert removed.status_code == 200

        thread = client.get(f"/api/v1/community/reports/{report['id']}/comments", headers=h2).json()
        assert thread["items"][0]["removed"] is True
        assert thread["items"][0]["body"] == "[removed]"

        citizen_restore = client.post(
            f"/api/v1/community/comments/{created['id']}/restore", headers=author_headers
        )
        assert citizen_restore.status_code == 403

        mod_headers = _role_headers(client, sender, "9876543017", "moderator")
        restored = client.post(
            f"/api/v1/community/comments/{created['id']}/restore", headers=mod_headers
        )
        assert restored.status_code == 200
        assert restored.json()["removed"] is False

    def test_moderator_removal_of_others_comment(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h1 = _citizen(client, sender, "9876543018")
        report = _submit(client, h1)
        created = _comment(client, report["id"], h1, "Crossing the line with abusive words")
        mod_headers = _role_headers(client, sender, "9876543019", "moderator")
        response = client.post(
            f"/api/v1/community/comments/{created['id']}/remove",
            json={"reason": "abusive language"},
            headers=mod_headers,
        )
        assert response.status_code == 200

    def test_content_report_and_duplicate_protection(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h1 = _citizen(client, sender, "9876543020")
        report = _submit(client, h1)
        _, h2 = _citizen(client, sender, "9876543021")
        reported = client.post(
            "/api/v1/community/content-reports",
            json={
                "content_type": "report",
                "content_id": report["id"],
                "reason": "spam",
                "details": "Looks like duplicate spam",
            },
            headers=h2,
        )
        assert reported.status_code == 201, reported.text

        again = client.post(
            "/api/v1/community/content-reports",
            json={
                "content_type": "report",
                "content_id": report["id"],
                "reason": "spam",
                "details": "Second attempt",
            },
            headers=h2,
        )
        assert again.status_code == 409
        assert again.json()["type"].endswith("/already_reported")


class TestReactions:
    def test_one_reaction_per_user_per_report(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, reporter_headers = _citizen(client, sender, "9876543022")
        report = _submit(client, reporter_headers)
        _, h2 = _citizen(client, sender, "9876543023")

        first = client.put(
            f"/api/v1/community/reports/{report['id']}/reaction",
            json={"kind": "like"},
            headers=h2,
        )
        assert first.status_code == 200
        assert first.json()["counts"]["reactions"] == 1

        second = client.put(
            f"/api/v1/community/reports/{report['id']}/reaction",
            json={"kind": "celebrate"},
            headers=h2,
        )
        assert second.status_code == 200
        assert second.json()["reaction"] == "celebrate"
        assert second.json()["counts"]["reactions"] == 1

        feed = client.get("/api/v1/feed", headers=h2).json()
        card = next(item for item in feed["items"] if item["id"] == report["id"])
        assert card["my_reaction"] == "celebrate"

        removed = client.delete(f"/api/v1/community/reports/{report['id']}/reaction", headers=h2)
        assert removed.status_code == 200
        assert removed.json()["reaction"] is None

    def test_invalid_reaction_kind(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h1 = _citizen(client, sender, "9876543024")
        report = _submit(client, h1)
        response = client.put(
            f"/api/v1/community/reports/{report['id']}/reaction",
            json={"kind": "rage"},
            headers=h1,
        )
        assert response.status_code == 422


class TestSaves:
    def test_save_unsave_and_list(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h1 = _citizen(client, sender, "9876543025")
        report = _submit(client, h1)
        _, h2 = _citizen(client, sender, "9876543026")

        saved = client.post(f"/api/v1/community/reports/{report['id']}/save", headers=h2)
        assert saved.status_code == 200
        assert saved.json()["status"] == "saved"

        listing = client.get("/api/v1/community/saved", headers=h2)
        assert listing.status_code == 200
        assert listing.json()["items"][0]["saved"] is True
        assert listing.json()["items"][0]["id"] == report["id"]

        unsaved = client.delete(f"/api/v1/community/reports/{report['id']}/save", headers=h2)
        assert unsaved.status_code == 200
        listing = client.get("/api/v1/community/saved", headers=h2)
        assert listing.json()["items"] == []


class TestFollows:
    def test_follow_summary_and_unfollow(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        category_id = _setup(client, sender)
        user_a_id, _ = _citizen(client, sender, "9876543027")
        _, h_b = _citizen(client, sender, "9876543028")

        assert (
            client.post(f"/api/v1/community/follows/user/{user_a_id}", headers=h_b).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/community/follows/category/{category_id}", headers=h_b
            ).status_code
            == 200
        )
        summary = client.get("/api/v1/community/follows/summary", headers=h_b)
        assert summary.status_code == 200
        assert summary.json()["users"] == 1
        assert summary.json()["categories"] == 1

        assert (
            client.delete(f"/api/v1/community/follows/user/{user_a_id}", headers=h_b).status_code
            == 200
        )
        summary = client.get("/api/v1/community/follows/summary", headers=h_b)
        assert summary.json()["users"] == 0

    def test_cannot_follow_self(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        user_id, headers = _citizen(client, sender, "9876543029")
        response = client.post(f"/api/v1/community/follows/user/{user_id}", headers=headers)
        assert response.status_code == 422
        assert response.json()["type"].endswith("/cannot_follow_self")


class TestBlocks:
    def test_block_hides_content_and_removes_follow(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        blocked_id, blocked_headers = _citizen(client, sender, "9876543030")
        _set_username(client, blocked_headers, "blocked_author_name")
        report = _submit(client, blocked_headers)
        _, viewer_headers = _citizen(client, sender, "9876543031")

        client.post(f"/api/v1/community/follows/user/{blocked_id}", headers=viewer_headers)
        blocked = client.post(f"/api/v1/community/users/{blocked_id}/block", headers=viewer_headers)
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "blocked"

        summary = client.get("/api/v1/community/follows/summary", headers=viewer_headers)
        assert summary.json()["users"] == 0

        feed = client.get("/api/v1/feed", headers=viewer_headers).json()
        assert report["id"] not in {item["id"] for item in feed["items"]}

        profile = client.get("/api/v1/community/users/blocked_author_name", headers=viewer_headers)
        assert profile.status_code == 404

        unblocked = client.delete(
            f"/api/v1/community/users/{blocked_id}/block", headers=viewer_headers
        )
        assert unblocked.status_code == 200
        feed = client.get("/api/v1/feed", headers=viewer_headers).json()
        assert report["id"] in {item["id"] for item in feed["items"]}

    def test_cannot_block_self(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        user_id, headers = _citizen(client, sender, "9876543032")
        response = client.post(f"/api/v1/community/users/{user_id}/block", headers=headers)
        assert response.status_code == 422
        assert response.json()["type"].endswith("/cannot_block_self")


class TestProfilesAndShare:
    def test_public_profile_has_no_private_fields(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h_a = _citizen(client, sender, "9876543033")
        _set_username(client, h_a, "public_user_name")
        profile = client.patch(
            "/api/v1/users/me",
            json={"bio": "I care about my neighbourhood schools"},
            headers=h_a,
        )
        assert profile.status_code == 200
        report = _submit(client, h_a)

        _, h_b = _citizen(client, sender, "9876543034")
        response = client.get("/api/v1/community/users/public_user_name", headers=h_b)
        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "public_user_name"
        assert body["stats"]["reports"] == 1
        for private_field in ("email", "phone", "location_pref", "password"):
            assert private_field not in body

        preview = client.get(f"/api/v1/community/share/reports/{report['id']}", headers=h_b)
        assert preview.status_code == 200
        assert preview.json()["ticket_no"].startswith("TK-")
        for private_field in ("email", "phone", "reporter_id"):
            assert private_field not in preview.json()

    def test_unknown_user_404(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, headers = _citizen(client, sender, "9876543035")
        response = client.get("/api/v1/community/users/nobody_here_123", headers=headers)
        assert response.status_code == 404
        assert response.json()["type"].endswith("/user_not_found")


class TestModerationQueue:
    def test_citizen_forbidden_moderator_can_resolve(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, h_author = _citizen(client, sender, "9876543036")
        report = _submit(client, h_author)
        created = _comment(client, report["id"], h_author, "Reported comment text here")
        _, h_reporter = _citizen(client, sender, "9876543037")
        client.post(
            "/api/v1/community/content-reports",
            json={
                "content_type": "comment",
                "content_id": created["id"],
                "reason": "harassment",
            },
            headers=h_reporter,
        )

        forbidden = client.get("/api/v1/community/moderation/queue", headers=h_author)
        assert forbidden.status_code == 403

        mod_headers = _role_headers(client, sender, "9876543038", "moderator")
        queue = client.get("/api/v1/community/moderation/queue", headers=mod_headers)
        assert queue.status_code == 200
        assert len(queue.json()["items"]) == 1
        item_id = queue.json()["items"][0]["id"]

        resolved = client.post(
            f"/api/v1/community/moderation/queue/{item_id}",
            json={"action": "remove", "reason": "harassment confirmed"},
            headers=mod_headers,
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "actioned"

        thread = client.get(
            f"/api/v1/community/reports/{report['id']}/comments", headers=h_reporter
        ).json()
        assert thread["items"][0]["removed"] is True

        queue = client.get("/api/v1/community/moderation/queue", headers=mod_headers)
        assert queue.json()["items"] == []


class TestNotifications:
    def test_mark_read_all_and_unread_count(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, reporter_headers = _citizen(client, sender, "9876543039")
        report = _submit(client, reporter_headers)
        _, h_commenter = _citizen(client, sender, "9876543040")
        _comment(client, report["id"], h_commenter, "A notification generating comment")

        count_1 = client.get("/api/v1/notifications/unread-count", headers=reporter_headers)
        assert count_1.status_code == 200
        assert count_1.json()["unread"] >= 1

        marked = client.post(
            "/api/v1/notifications/mark-read", json={"all": True}, headers=reporter_headers
        )
        assert marked.status_code == 200
        assert marked.json()["marked"] >= 1

        count_2 = client.get("/api/v1/notifications/unread-count", headers=reporter_headers)
        assert count_2.json()["unread"] == 0

    def test_grouped_listing_and_group_mark_read(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _setup(client, sender)
        _, reporter_headers = _citizen(client, sender, "9876543041")
        report = _submit(client, reporter_headers)
        _, c1 = _citizen(client, sender, "9876543042")
        _, c2 = _citizen(client, sender, "9876543043")
        for headers in (c1, c2):
            _comment(client, report["id"], headers, "Another comment on this report")

        history = client.get("/api/v1/notifications", headers=reporter_headers)
        assert history.status_code == 200
        grouped = [
            item for item in history.json()["items"] if not item["read"] and item.get("group_key")
        ]
        assert grouped, "expected a grouped unread entry"
        assert grouped[0]["count"] >= 2
        assert history.json()["unread"] >= 2

        marked = client.post(
            "/api/v1/notifications/mark-read",
            json={"group_key": grouped[0]["group_key"]},
            headers=reporter_headers,
        )
        assert marked.status_code == 200
        remaining = client.get("/api/v1/notifications", headers=reporter_headers)
        assert remaining.json()["unread"] == 0

    def test_security_preferences_locked(self, client, sender) -> None:  # type: ignore[no-untyped-def]
        _, headers = _citizen(client, sender, "9876543044")
        response = client.patch(
            "/api/v1/notifications/preferences",
            json={"security": {"sms": {"enabled": False}}},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/locked_preference")
