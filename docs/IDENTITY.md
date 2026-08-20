# IDENTITY

**Phase 24 — Unified Identity, Profile, Verification, Trust & Organization Layer**

## Overview

Phase 24 establishes a unified identity layer connecting users, profiles,
verification, organizations, institution claims, and contextual trust labels.

```
USER
 ↓
IDENTITY
 ↓
PROFILE
 ↓
VERIFICATION
 ↓
ROLES
 ↓
ORGANIZATIONS
 ↓
INSTITUTIONS
 ↓
PERMISSIONS
 ↓
TRUST
 ↓
CIVIC PARTICIPATION
```

## Core Principle

Trust is **contextual**. It describes platform-specific verification and
contribution context, not the value or worth of a person.

**NEVER create:**
- Citizen scores
- Political scores
- Citizen rankings
- Hidden reputation scores
- Political affiliation inference
- Religion/caste/ideology inference

## Architecture

### Separation of Concerns

| Concept | Purpose |
|---------|---------|
| **Authentication Identity** | Who are you? (password, OAuth, MFA) |
| **Public Profile** | What do you show publicly? |
| **Verification** | Has a specific claim been verified? |
| **Permissions** | What can you do? (RBAC + ABAC) |
| **Organization Membership** | Which organizations do you belong to? |

### Trust Model

Trust is described through **contextual labels**, never a single score:

| Label | Meaning |
|-------|---------|
| Identity Verified | This identity has been verified according to a defined process |
| Organization Verified | An organization this user belongs to has been verified |
| Official Representative Verified | Official representative status has been verified |
| Email Verified | Email address has been verified |
| Phone Verified | Phone number has been verified |
| Skill Verified | A specific skill claim has been verified |

## New Tables

| Table | Purpose |
|-------|---------|
| `user_profiles` | Extended profile with visibility controls |
| `user_preferences` | Language, timezone, notification settings |
| `identity_verifications` | Verification requests and decisions |
| `organizations` | First-class organization entities |
| `organization_memberships` | User membership in organizations |
| `organization_invitations` | Invitation workflow |
| `institution_claims` | Claim to represent an institution |
| `representative_assignments` | Designated representatives |
| `identity_provider_links` | Extensible OAuth architecture |
| `account_status_history` | Append-only status change log |

## API Endpoints

### Profile
- `GET /api/v1/identity/me/profile` — Get own profile (authenticated)
- `PATCH /api/v1/identity/me/profile` — Update own profile (authenticated)
- `GET /api/v1/identity/profiles/{user_id}` — Get public profile (public, respects visibility)

### Preferences
- `GET /api/v1/identity/me/preferences` — Get own preferences (authenticated)
- `PATCH /api/v1/identity/me/preferences` — Update own preferences (authenticated)

### Verification
- `POST /api/v1/identity/verifications` — Create verification request (authenticated)
- `GET /api/v1/identity/verifications` — List own verifications (authenticated)
- `GET /api/v1/identity/verifications/{user_id}` — List user verifications (public)
- `PATCH /api/v1/identity/verifications/{id}/review` — Review verification (admin/moderator)

### Trust
- `GET /api/v1/identity/trust/{user_id}` — Get trust labels (public)
- `GET /api/v1/identity/contributions/{user_id}` — Get contribution summary (public)

### Organizations
- `POST /api/v1/identity/organizations` — Create organization (authenticated)
- `GET /api/v1/identity/organizations` — List organizations (public)
- `GET /api/v1/identity/organizations/{id}` — Get organization (public)
- `POST /api/v1/identity/organizations/{id}/invite` — Invite member (org admin)
- `POST /api/v1/identity/organizations/invitations/{id}/accept` — Accept invitation
- `GET /api/v1/identity/organizations/{id}/members` — List members (public)

### Institution Claims
- `POST /api/v1/identity/institution-claims` — Create claim (authenticated)
- `PATCH /api/v1/identity/institution-claims/{id}/review` — Review claim (admin/moderator)

### Representatives
- `POST /api/v1/identity/representatives` — Assign representative (admin/moderator)

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_my_profile` | Get user profile with verification labels |
| `get_my_permissions` | Explain user's roles and permissions |
| `get_my_organizations` | List user's organization memberships |
| `get_my_contributions` | Factual contribution history (not a score) |
| `get_verification_status` | Verification status for a user |
| `get_organization_profile` | Organization public profile |
| `get_institution_profile` | Institution public profile |

All tools are READ_ONLY and permission-guarded.

## Verification States

```
NOT_VERIFIED → PENDING → UNDER_REVIEW → VERIFIED
                                    → REJECTED
                                    → MORE_INFORMATION
                                    → SUSPENDED
                                    → EXPIRED
```

## Organization Roles

| Role | Permissions |
|------|------------|
| Owner | Full control, cannot be removed |
| Admin | Manage members, invitations, settings |
| Manager | Manage initiatives, tasks |
| Member | Participate in initiatives |
| Viewer | Read-only access |

## Institution Claim Workflow

```
REQUESTED → UNDER_REVIEW → APPROVED
                       → MORE_INFORMATION
                       → REJECTED
                       → REVOKED
```

**Important:** Claim approval does NOT grant access to government internal
data. Institution claim and data access are separate.

## Privacy

- Profile visibility: PUBLIC, COMMUNITY, PRIVATE
- Contact visibility: controls who sees email/phone
- Contribution visibility: controls who sees activity
- Location visibility: controls who sees location
- Private information never exposed through MCP or AI
- Organization members not publicly exposed by default

## Security

- All endpoints auth-gated with appropriate roles
- Write operations require authentication
- Verification review requires admin/moderator role
- Organization invitations are token-based with expiration
- Account status changes are append-only audit logged
- No citizen ranking or political profiling
