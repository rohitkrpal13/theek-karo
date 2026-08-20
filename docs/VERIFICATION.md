# VERIFICATION

**Phase 24 — Identity Verification Framework**

## Overview

Verification is **context-specific**. A verified account does NOT mean
"This person is always truthful." It means "This identity or organizational
claim has been verified according to a defined process."

## Verification Types

| Type | Scope | Evidence Required |
|------|-------|-------------------|
| `EMAIL_VERIFIED` | User | Email confirmation |
| `PHONE_VERIFIED` | User | Phone confirmation |
| `IDENTITY_VERIFIED` | User | Government ID or equivalent |
| `ORGANIZATION_VERIFIED` | Organization | Registration documents |
| `INSTITUTION_REP_VERIFIED` | User→Institution | Authorization letter |
| `OFFICIAL_REP_VERIFIED` | User→Department | Government appointment |
| `SKILL_VERIFIED` | User | Certification or demonstration |

## Verification States

| State | Meaning |
|-------|---------|
| `NOT_VERIFIED` | No verification attempted |
| `PENDING` | Request submitted, awaiting review |
| `UNDER_REVIEW` | Being reviewed by authorized reviewer |
| `VERIFIED` | Successfully verified |
| `EXPIRED` | Verification period has expired |
| `REJECTED` | Verification request denied |
| `SUSPENDED` | Previously verified, now suspended |

## Verification Evidence

Each verification record references:
- **Evidence references** — IDs of supporting documents/media
- **Documentation URL** — External documentation link
- **Review method** — How the review was conducted
- **Reviewer** — Who made the decision
- **Decision** — The verification outcome
- **Expiration** — When verification expires (if applicable)

## Verification Review

### Reviewer Requirements
- Must be admin or moderator
- Cannot approve their own verification (separation of duties)
- Must provide decision and optional explanation

### Review Actions
1. **Approve** — Mark as verified, optionally set expiration
2. **Reject** — Deny with reason
3. **Request More Information** — Ask for additional evidence
4. **Suspend** — Temporarily revoke verification
5. **Escalate** — Send to higher authority

## Verification Expiration

Some verification types may expire:
- `IDENTITY_VERIFIED` — Typically 1-2 years
- `ORGANIZATION_VERIFIED` — Annual renewal
- `OFFICIAL_REP_VERIFIED` — Per appointment period

When verification expires:
- Status changes to `EXPIRED`
- Profile labels are updated
- User is notified before expiration

## Verification Revocation

Authorized reviewers can revoke verification:
- Requires reason
- Requires reviewer identity
- Audit logged
- Profile labels updated

## Document Verification

Where identity documents are supported:
- Secure storage (never public)
- Restricted access (reviewer only)
- Retention policy (delete after verification)
- Audit logs (who accessed, when)

**Sensitive verification documents must never be public.**

## Verification and Trust Labels

Verification directly updates profile trust labels:
- `IDENTITY_VERIFIED` → `identity_verified: true`
- `ORGANIZATION_VERIFIED` → `organization_verified: true`
- `OFFICIAL_REP_VERIFIED` → `official_representative: true`

Labels are contextual and explain what was verified.
