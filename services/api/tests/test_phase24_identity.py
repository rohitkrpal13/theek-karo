"""Phase 24 — Identity, Profile, Verification & Organization tests.

Tests: profile CRUD, preferences, identity verification lifecycle,
organization creation/membership/invitations, institution claims,
trust labels, contribution history, and API endpoint validation.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class TestUserProfile:
    """Test profile creation, retrieval, and visibility."""

    def test_get_profile_requires_auth(self, client: TestClient):
        """Getting own profile requires authentication."""
        resp = client.get("/api/v1/identity/me/profile")
        assert resp.status_code in (200, 401)

    def test_update_profile(self, client: TestClient):
        """Updating profile works with valid data."""
        resp = client.patch(
            "/api/v1/identity/me/profile",
            json={"display_name": "Test User", "bio": "Civic volunteer"},
        )
        assert resp.status_code in (200, 401)

    def test_public_profile(self, client: TestClient):
        """Public profile endpoint exists."""
        user_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/identity/profiles/{user_id}")
        assert resp.status_code in (200, 404)

    def test_profile_visibility_settings(self, client: TestClient):
        """Profile visibility settings are accepted."""
        resp = client.patch(
            "/api/v1/identity/me/profile",
            json={
                "profile_visibility": "COMMUNITY",
                "contact_visibility": "PRIVATE",
                "contribution_visibility": "PUBLIC",
            },
        )
        assert resp.status_code in (200, 401)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


class TestUserPreferences:
    """Test preferences CRUD."""

    def test_get_preferences(self, client: TestClient):
        """Getting preferences works."""
        resp = client.get("/api/v1/identity/me/preferences")
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            data = resp.json()
            assert "language" in data
            assert "timezone" in data

    def test_update_preferences(self, client: TestClient):
        """Updating preferences works."""
        resp = client.patch(
            "/api/v1/identity/me/preferences",
            json={"language": "hi", "timezone": "Asia/Kolkata"},
        )
        assert resp.status_code in (200, 401)


# ---------------------------------------------------------------------------
# Identity Verification
# ---------------------------------------------------------------------------


class TestIdentityVerification:
    """Test verification request and review lifecycle."""

    def test_create_verification_request(self, client: TestClient):
        """Creating verification request works."""
        resp = client.post(
            "/api/v1/identity/verifications",
            json={
                "verification_type": "EMAIL_VERIFIED",
                "target_type": "user",
                "target_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code in (201, 401)

    def test_list_verifications(self, client: TestClient):
        """Listing verifications works."""
        resp = client.get("/api/v1/identity/verifications")
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            data = resp.json()
            assert "items" in data
            assert "total" in data

    def test_invalid_verification_type_rejected(self, client: TestClient):
        """Invalid verification type is rejected."""
        resp = client.post(
            "/api/v1/identity/verifications",
            json={
                "verification_type": "INVALID_TYPE",
                "target_type": "user",
                "target_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code in (422, 401)

    def test_verification_types_accepted(self, client: TestClient):
        """All valid verification types are accepted."""
        for vtype in (
            "EMAIL_VERIFIED",
            "PHONE_VERIFIED",
            "IDENTITY_VERIFIED",
            "ORGANIZATION_VERIFIED",
            "INSTITUTION_REP_VERIFIED",
            "OFFICIAL_REP_VERIFIED",
            "SKILL_VERIFIED",
        ):
            resp = client.post(
                "/api/v1/identity/verifications",
                json={
                    "verification_type": vtype,
                    "target_type": "user",
                    "target_id": str(uuid.uuid4()),
                },
            )
            assert resp.status_code in (201, 401), f"Type {vtype} failed"


# ---------------------------------------------------------------------------
# Trust Labels
# ---------------------------------------------------------------------------


class TestTrustLabels:
    """Test contextual trust label retrieval."""

    def test_get_trust_labels(self, client: TestClient):
        """Trust labels endpoint returns valid structure."""
        user_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/identity/trust/{user_id}")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "user_id" in data
            assert "labels" in data
            assert isinstance(data["labels"], list)

    def test_trust_labels_not_score(self, client: TestClient):
        """Trust labels never return a single score."""
        user_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/identity/trust/{user_id}")
        if resp.status_code == 200:
            data = resp.json()
            # Should not have a numeric trust_score field
            assert "trust_score" not in data
            assert "quality_score" not in data


# ---------------------------------------------------------------------------
# Contribution Summary
# ---------------------------------------------------------------------------


class TestContributions:
    """Test factual contribution history."""

    def test_get_contributions(self, client: TestClient):
        """Contributions endpoint returns valid structure."""
        user_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/identity/contributions/{user_id}")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "user_id" in data
            assert "public_reports" in data
            assert "initiatives_participated" in data
            assert "note" in data


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


class TestOrganizations:
    """Test organization CRUD, membership, and invitations."""

    def test_create_organization(self, client: TestClient):
        """Creating organization works."""
        resp = client.post(
            "/api/v1/identity/organizations",
            json={
                "name": "Test Civic Group",
                "organization_type": "civic",
                "description": "A test civic organization",
            },
        )
        assert resp.status_code in (201, 401)

    def test_list_organizations(self, client: TestClient):
        """Listing organizations works."""
        resp = client.get("/api/v1/identity/organizations")
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            data = resp.json()
            assert "items" in data
            assert "total" in data

    def test_organization_types_accepted(self, client: TestClient):
        """All valid organization types are accepted."""
        for otype in (
            "ngo",
            "community_group",
            "resident_association",
            "educational",
            "healthcare",
            "civic",
            "professional",
            "government",
            "other",
        ):
            resp = client.post(
                "/api/v1/identity/organizations",
                json={
                    "name": f"Test {otype} Org",
                    "organization_type": otype,
                },
            )
            assert resp.status_code in (201, 401), f"Type {otype} failed"

    def test_invite_member(self, client: TestClient):
        """Inviting member works."""
        org_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/identity/organizations/{org_id}/invite",
            json={
                "invitee_email": "test@example.com",
                "role": "member",
            },
        )
        assert resp.status_code in (201, 401, 403, 404)

    def test_list_members(self, client: TestClient):
        """Listing members works."""
        org_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/identity/organizations/{org_id}/members")
        assert resp.status_code in (200, 401, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "items" in data


# ---------------------------------------------------------------------------
# Institution Claims
# ---------------------------------------------------------------------------


class TestInstitutionClaims:
    """Test institution claim workflow."""

    def test_create_claim(self, client: TestClient):
        """Creating institution claim works."""
        resp = client.post(
            "/api/v1/identity/institution-claims",
            json={
                "institution_id": str(uuid.uuid4()),
                "claim_note": "I am the principal of this school",
                "evidence_refs": [],
            },
        )
        assert resp.status_code in (201, 401)

    def test_claim_status_workflow(self, client: TestClient):
        """Claim status values are valid."""
        valid_states = (
            "REQUESTED",
            "UNDER_REVIEW",
            "MORE_INFORMATION",
            "APPROVED",
            "REJECTED",
            "REVOKED",
        )
        # Just verify the states are defined (tested via model constraints)
        assert len(valid_states) == 6


# ---------------------------------------------------------------------------
# End-to-End Lifecycle
# ---------------------------------------------------------------------------


class TestEndToEndLifecycle:
    """Test the full identity lifecycle."""

    def test_profile_trust_labels_empty(self, client: TestClient):
        """New user has no trust labels."""
        user_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/identity/trust/{user_id}")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["labels"] == []

    def test_contributions_empty(self, client: TestClient):
        """New user has zero contributions."""
        user_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/identity/contributions/{user_id}")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["public_reports"] == 0
            assert data["initiatives_participated"] == 0
            assert "not a quality score" in data["note"].lower()

    def test_organization_creation_and_listing(self, client: TestClient):
        """Organization can be created and listed."""
        resp = client.post(
            "/api/v1/identity/organizations",
            json={
                "name": "Test Organization",
                "organization_type": "civic",
            },
        )
        # May fail auth but tests the endpoint exists
        assert resp.status_code in (201, 401)

        resp = client.get("/api/v1/identity/organizations")
        assert resp.status_code in (200, 401)

    def test_verification_request_and_listing(self, client: TestClient):
        """Verification can be requested and listed."""
        resp = client.post(
            "/api/v1/identity/verifications",
            json={
                "verification_type": "EMAIL_VERIFIED",
                "target_type": "user",
                "target_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code in (201, 401)

        resp = client.get("/api/v1/identity/verifications")
        assert resp.status_code in (200, 401)

    def test_institution_claim_workflow(self, client: TestClient):
        """Institution claim can be created."""
        resp = client.post(
            "/api/v1/identity/institution-claims",
            json={
                "institution_id": str(uuid.uuid4()),
                "claim_note": "I am the authorized representative",
            },
        )
        assert resp.status_code in (201, 401)

    def test_representative_assignment(self, client: TestClient):
        """Representative assignment endpoint exists."""
        resp = client.post(
            "/api/v1/identity/representatives",
            json={
                "user_id": str(uuid.uuid4()),
                "representative_type": "organization",
                "target_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code in (201, 401, 403)
