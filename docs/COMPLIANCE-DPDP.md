# DPDP ACT COMPLIANCE MEMO (Phase 10)

Status: **draft for counsel review** (input to the Phase 10 compliance pass, not legal advice).
Scope: India DPDP Act, 2023 obligations touched by this platform and how the
current implementation addresses each.

## 1. Consent & purpose limitation

- Consent records in `consents` (purpose, terms_version, granted_at, revoked_at);
  the `data_processing` purpose is a distinct consent seat; revocation flow exists
  (`POST /users/me/consents/revoke`), audited.
- Purposes are bounded: civic reporting, verification, notifications, analytics;
  no cross-purpose reuse; AI payloads carry PII-redacted text (ADR-019).
- Counsel review points: consent lifecycle wording, retention of consent evidence,
  and the privacy-notice copy (web `Terms` page is placeholder — Phase 11 content).

## 2. Lawful processing under 5(1) of the Act (general rule)

- Probable: consent (see §1) for citizen accounts; legitimate-use notices for
  de-identified measurement aggregates.
- Explicit consents for sensitive personal data (location triangulation,
  health-related fields in hospital reports) need prominent + separate consent —
  flagged as an implementation gap for the pilot categories (school/road avoid
  sensitive fields by schema design).

## 3. Notice obligations

- Privacy notice is a placeholder in the web app; a full notice must precede
  the first production campaign (Phase 11 content work).

## 4. Rights (6(1)-(6)(8))

- Right to access: user self-service profile/audit endpoints.
- Right to erasure: user deletion flow exists at DB level (deleted_at + 90-day
  grace + anonymisation path documented in DATABASE.md §7 retention).
- Right to grievance redress: needed — a grievance channel is a Phase 11 open item.

## 5. Data protection obligations (8(5)-(8(6)) in the Act)

- Security safeguards: audit trails, access control, rate limits, scan gate,
  presigned media URLs, non-root runtime — summarised in SECURITY-CHECKLIST.md.
- Data Protection Officer designation: org decision; documented as an open item.

## 6. Restriction of disclosure (16) and breach notification (8(6))

- Internal records: audit_logs cover disclosure-bearing actions (admin reads,
  review decisions); a breach runbook (RUNBOOKS.md#breach) drafts the 72-hour
  Data Protection Board notification with the required fields.

## 7. Retention (DPDP + IT rules alignment)

- DATABASE.md §7 tables: users 90-day grace → anonymised; reports indefinite
  with PII masking on demand; AI logs 90 days; media per campaign policy;
  audit indefinite (write-once).

## 8. Children

- Platform does not target children under 18; registration requires the
  citizen-consent self-certification. Official confirmation of age/guardian
  flows is a Phase 12 policy decision, not an MVP blocker.

## Counsel review (Phase 11 close-out)

- Web privacy notice + terms drafted (`apps/web/src/app/[locale]/privacy`,
  `terms`) and linked in the footer — status: **draft**, counsel
  approved-review pending on the human side.
- Review owner: platform counsel (assigned in Phase 11). This memo plus
  SECURITY-CHECKLIST.md and the privacy-notice draft are the review inputs;
  the ROADMAP M3 gate requires counsel sign-off before the first public campaign.
