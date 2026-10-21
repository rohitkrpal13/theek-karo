# Theek Karo — Production Readiness Plan

**Status:** In progress
**Last reviewed:** 2026-10-14

This plan turns the repository's readiness audit into sequential, testable
work. "Production ready" means both that the code passes its gates and that
the real deployment, data rights, security controls, and operating procedures
have been verified. Repository changes alone cannot complete the external
launch gates.

## Execution order

### 0. Establish a trustworthy baseline — Complete

- Keep the current development application available and confirm web/API
  health.
- Preserve pre-existing worktree changes; do not discard unrelated files.
- Use the audit and go-live checklist as the record of verified evidence.

### 1. Stabilize the core citizen journeys — In progress

Verify each journey end-to-end in the browser and API, with success, empty,
loading, error, retry, and authorization states:

- Register, verify contact, log in/out, refresh session, and privileged MFA.
- Find institutions by name/address and opt in to nearby search; never invent
  records when approved source data is absent.
- Create a report, attach permitted media, view its case/status, and retry
  recoverable failures without duplicate submission.
- Search, map, notifications, public alerts, and localized navigation.
- Verify staff/admin/government pages reject unauthorized users.

**Exit criteria:** focused automated tests and browser smoke checks for each
journey; no known uncaught errors or success-shaped failure fallbacks.

### 2. Close repository security and API gaps — Next

- Request-size enforcement now honors the configured global cap in addition to
  content-type caps and rejects oversized `Content-Length` and streamed
  requests; production reverse-proxy limits remain to be verified.
- Review authentication, authorization, tenant boundaries, public endpoints,
  SSRF, CORS, rate limits, and production security headers.
- ADR-015 defines the additive-only `/api/v1` policy and a migration window for
  breaking changes; add deprecation/compatibility enforcement and verify
  versioned OpenAPI contracts.
- Resolve dependency advisories without downgrading framework compatibility.

**Exit criteria:** focused regression tests, backend lint/type checks, frontend
lint/type/tests, and a reviewed dependency audit.

### 3. Make data and integrations launch-safe

- Obtain written permission and provenance for any imported institution data;
  import only approved, verifiable datasets.
- Configure production identity, email/SMS, notification delivery receipts,
  AI provider/cost controls, and media scanning/storage.
- Validate empty-catalog behavior, deduplication, data correction, and deletion
  workflows; do not represent demo or unverified content as official.

**External gate:** data-owner/reuse approval and production provider credentials.

### 4. Prove reliability and recovery

- Test fresh migrations, rollback strategy, backup/restore, and recovery time
  against a disposable environment.
- Verify queue retries, idempotency, dead-letter handling, worker health, and
  alerting.
- Run load/spike tests and inspect database query plans, pool sizing, latency,
  and resource limits.

**External gate:** production-like managed database/cache/storage and an
approved recovery window. Tests that drop databases require explicit approval
of the target environment before execution.

### 5. Deploy and operate safely

- Apply and review Terraform plans for isolated staging and production.
- Verify DNS, TLS termination, HSTS, CDN/WAF, CORS, secrets access, backups,
  dashboards, log retention, paging, and rollback in the real cloud accounts.
- Exercise CI deployment approvals, canary/health gates, rollback, and
  incident communications.

**External gate:** authorized cloud access, domain/certificate control, and
named operators/on-call owners.

### 6. Final go-live decision

- Re-run the complete CI suite and security scans on the release commit.
- Complete every applicable item in [GO-LIVE-CHECKLIST.md](./GO-LIVE-CHECKLIST.md)
  with evidence; unknowns stay open rather than being marked ready.
- Publish a release, run a production smoke test, monitor the agreed SLOs, and
  have a tested rollback owner and procedure.

## Current evidence and known blockers

- The local web app and API health endpoint respond successfully; backend and
  frontend targeted checks are passing for recent changes.
- The institution catalog is currently empty. Official institution imports
  remain blocked until source-data rights and provenance are approved.
- Cloud deployment, production TLS/edge, production database restore, provider
  delivery, and operations/on-call evidence have not been verified here.
- The latest readiness audit records five HIGH advisories in the frontend
  development lint toolchain; production dependencies had no advisories in
  that audit. Recheck before release.
- The backup/restore integration test was intentionally not run locally
  without approval for its temporary database create/drop operations.

See [PRODUCTION-READINESS-AUDIT.md](./PRODUCTION-READINESS-AUDIT.md) for
evidence and [GO-LIVE-CHECKLIST.md](./GO-LIVE-CHECKLIST.md) for deployment
sign-off.
