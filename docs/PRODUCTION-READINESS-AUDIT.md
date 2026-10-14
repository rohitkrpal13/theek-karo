# Production Readiness Audit (Phase 16)

Status: **Evidence refresh — 2026-10-14**

This document records verified repository checks and outstanding go-live
blockers. The detailed sections below began as a 2026-08-17 baseline; where
their status conflicts with this refresh, this evidence section is current.
No cloud deployment or external operational control is claimed as verified.
See [PRODUCTION-READINESS-PLAN.md](./PRODUCTION-READINESS-PLAN.md) for the
sequenced implementation plan and exit criteria.

Legend: `READY` · `NEEDS_IMPROVEMENT` · `BLOCKED` · `UNKNOWN`

---

## 0. Current verified evidence (2026-10-14)

Checks run against the working tree:

- Frontend: `npm run lint`, `npx tsc --noEmit`, and `npm test` passed (63 tests
  across 18 files); `npm run build` passed on Next.js 16.4.0 and Vitest 4.1.11.
- Backend: `uv run ruff format --check .`, `uv run ruff check .`, and
  `uv run mypy src` passed. `uv run pytest -q
  --ignore=tests/integration/test_backup_restore.py` passed (616 passed,
  1 skipped). This includes 10 PostgreSQL integration tests against an
  isolated PostGIS database.
- The backup/restore test was not run locally because it creates and drops
  temporary databases. The integration CI job includes this test, but its
  GitHub Actions result was not inspected.
- The Phase 3 test creates explicit test fixtures and only cleans rows matching
  its own identifiers.
- Migration `0022` widens Alembic's revision column before applying its
  >32-character revision ID; migration to head and the Phase 3 integration
  test passed on the isolated database.
- `npm audit --omit=dev --audit-level=moderate` reported zero production
  dependency advisories. Full `npm audit` still reports five HIGH advisories
  in the `eslint-config-next` -> `fast-glob` -> `micromatch` -> `braces`
  development lint toolchain; the available npm fix downgrades the Next ESLint
  config to 14.2.35, incompatible with the app's Next 16. No downgrade was
  applied.
- Frontend lint, TypeScript, 63 tests, and the Next.js 16.4.0 production build
  passed. Production preview `/hi/explore` returned HTTP 200 with CSP (without
  `unsafe-eval`), HSTS, and the configured security headers. Dev server and API
  `/healthz` and `/readyz` returned HTTP 200.
- Frontend `/api/v1/:path*` and `/api/public/v1/:path*` proxy to the configured
  API upstream.
- The logged-out public alert banner now uses a separate rate-limited
  `GET /api/v1/communication/public-alerts` endpoint. It returns only
  verified, published, unexpired alerts and excludes internal source/body
  fields; the existing full alert list remains staff-protected. Backend
  filtering and frontend retry/expiry behavior have focused tests.
- Institution suggestions query the first-party registered-institution
  directory, debounce requests, support keyboard selection, and search address
  words as well as institution names. Empty catalog results remain explicit;
  no unapproved external dataset is represented as real data.
- Request-size middleware now applies the configured global cap as an
  additional limit alongside the existing content-type limits; focused tests
  verify oversized declared and streamed requests return HTTP 413.
- `npm audit --omit=dev --audit-level=moderate` reported zero production
  dependency vulnerabilities in this refresh.
- The live institution catalog remains empty, and the UDISE+ reuse clearance
  recorded in `docs/PROVENANCE.md` is unresolved; official institution imports
  must remain blocked until approved source data is available.

---

## 1. Summary matrix

| Area | Status | Primary evidence |
|------|--------|------------------|
| Architecture | READY | `docs/ARCHITECTURE.md`; monolith + worker, modular routers |
| Security (application) | NEEDS_IMPROVEMENT | Headers configured; CSP, live TLS, and MFA rollout still require environment verification (§8) |
| Authentication | NEEDS_IMPROVEMENT | Argon2id/JWT, TOTP MFA, per-account backoff implemented; live privileged-role enforcement not verified (§9) |
| Authorization | NEEDS_IMPROVEMENT | RBAC and focused IDOR tests exist; complete tenant-isolation matrix remains unverified (§10) |
| Database | NEEDS_IMPROVEMENT | PostGIS/PG16 and 41 migrations tested to head; production backup/restore and index plan audit remain unverified (§13) |
| API | NEEDS_IMPROVEMENT | Problem+JSON, rate limits, request IDs, public alerts, and configured request-size limits; reverse-proxy body limits and version-policy enforcement need verification (§3, ADR-015) |
| Frontend | NEEDS_IMPROVEMENT | Production headers and both API proxies configured; five HIGH dev-toolchain advisories remain (§18) |
| Infrastructure | READY (unapplied) | Terraform for AWS ECS/RDS/ElastiCache/S3/CF — `terraform validate` only gate (§19) |
| CI/CD | READY (partial) | Gates + migration round-trip + trivy; approval/canary absent (§19) |
| Observability | READY (partial) | JSON logs, request-id, `/metrics`, `/healthz`, `/readyz`, Prom+Grafana, OTel opt-in (§15) |
| AI | NEEDS_IMPROVEMENT | Fallback gateway exists; no tool-use authorization audit, no cost controls (§11) |
| Storage / media | NEEDS_IMPROVEMENT | Magic-byte scan, presigned URLs; ClamAV slot is dev-only (§12) |
| Networking/CDN | NEEDS_IMPROVEMENT | CloudFront for media; no CDN for web; DNS/HSTS unknown |
| Caching | READY (Redis) | Redis-backed rate limit/cache; memory fallback (§14) |
| Queues / workers | NEEDS_IMPROVEMENT | Celery time limits; no per-task retry/backoff/DLQ (§14) |
| Notifications | NEEDS_IMPROVEMENT | Console sandbox providers; DLT provider open question (§12) |
| GIS | READY | PostGIS + boundary ingest + viewport APIs + tests |
| Analytics | READY | Analytics service + metrics registry + public endpoints |
| Open Data (Phase 15) | NEEDS_IMPROVEMENT | Public API implemented; docs (PUBLIC-API/OPEN-DATA/DATA-*) missing |
| Disaster Recovery | BLOCKED | Proposed RPO/RTO and runbook exist; production restore drill and infrastructure evidence are missing (§20) |
| Privacy / DPDP | NEEDS_IMPROVEMENT | PII inventory missing; anonymization exists; retention undefined (§12) |
| Compliance | NEEDS_IMPROVEMENT | `docs/COMPLIANCE-DPDP.md` exists; DPDP readiness unverified externally |
| Performance | NEEDS_IMPROVEMENT | k6 SLO smoke only (10 VU/30s); no load/spike scale evidence (§15) |
| Cost | UNKNOWN | No cost tracking instrumentation (§19) |
| India scale | NEEDS_IMPROVEMENT | en+hi, IST timezone, Indian number/date formats; 13-language target unverified (§17) |

---

## 2. Architecture

Status: **READY**

- Modular monolith (`tk_api` modules: auth, ai, analytics, cases, civic, community,
  departments, geography, gis, govdata, institutions, media, notifications,
  provenance, publicdata, rag, reports, resolution, search, users) behind
  `/api/v1` + `/api/public/v1` routers (`services/api/src/tk_api/api/v1.py`,
  `services/api/src/tk_api/main.py`).
- Single async API process + Celery worker, Postgres/PostGIS + Redis + MinIO/S3.
  Matches the target production architecture (§4 of the brief) without
  premature microservices/Kubernetes (ADR-034, `infra/terraform/main.tf`).
- Evidence: `make lint`, `make typecheck` (133 files), `make format-check`
  green; app factory constructs in-process fallbacks for storage/gateway/limiter
  when infra is absent (`main.py` lifespan).

## 3. API

Status: **NEEDS_IMPROVEMENT**

Ready: RFC 9457 problem+json errors (`core/errors.py`), request correlation
headers `X-Request-Id`/`X-Correlation-Id` (`api/middleware.py`), 43
`rate_limit(...)` call sites, OpenAPI snapshot contract test
(`tests/test_openapi_snapshot.py`), version endpoint `/api/v1/version`.

The web proxy now includes both `/api/v1/:path*` and `/api/public/v1/:path*`
rewrites in `apps/web/next.config.ts`.

Gaps:
- Request-size middleware enforces declared and streamed body sizes against
  configured and content-type limits; reverse-proxy limits still require
  verification.
- ADR-015 defines additive-only `/api/v1` changes and a minimum six-month
  migration window for breaking `/api/v2` changes; implementation still needs
  explicit deprecation/compatibility enforcement and versioned contract checks.
- The public banner uses a dedicated, rate-limited endpoint with a minimal
  response restricted to verified, published, unexpired alerts. The full alert
  listing and write/review operations remain protected.

## 4. Repository / source control

Status: **BLOCKED** (for production)

- The repository has **zero commits** (`git log` fails: "current branch 'main'
  does not have any commits yet"); the entire tree is untracked
  (`git status` shows `??` for everything).
- Consequence: no history for release diffs, no tag pinning, no rollback
  baseline, no secret-history audit possible via git (see §8).
- `.gitignore` correctly excludes `.env*`, `.venv`, `node_modules`, caches.
- Action required before go-live: initial commit, `main` protection, signed
  commits, tag/release process (see `docs/RELEASE-PROCESS.md` once written).

## 5. Environment separation

Status: **NEEDS_IMPROVEMENT**

Ready: `TK_ENV` ∈ {dev, test, staging, prod}; `Settings` fail-fast
`validate_production_readiness()` blocking default JWT/dev DB password in
prod/staging (`core/config.py`); `.env.example` documents infra defaults;
docker-compose is dev-only with distinct ports.

Gaps:
- Staging/prod differ mainly by Terraform input; no documented per-environment
  matrix (databases, storage, keys, monitoring, queues) beyond `main.tf`.
- CI deploy uses `staging|prod` via environment names; secrets per environment
  are GitHub secrets (unverified whether GB secrets are rotated).

## 6. Configuration management

Status: **READY**

- All env-specific configuration read from `TK_*` env vars via
  pydantic-settings (`core/config.py`); no hard-coded passwords/keys beyond
  dev defaults that fail fast in prod.

## 7. Secret audit

Status: **READY** (high-level scan)

Scan `rg -i "sk-...|api_key=...|secret=...|password=..."` across the tree
(excluding venv/node_modules/snapshots): **no leaked third-party secrets
found**. Only dev defaults with explicit prod guards
(`tk_dev_password`, `tk_minio_password`, `dev-secret-change-me`,
`dev-grafana-password`).

Caveats:
- Full history scan impossible (no commits, §4). Fresh commit must be scanned.
- Terraform task definitions now source the database URL, JWT, AI, and media
  secrets from Secrets Manager, including the worker media key. Terraform has
  not been applied; verify secret access in a real plan/deployment, and protect
  Terraform state because secret values are represented in Terraform inputs
  and secret-version resources.

## 8. Application security headers

Status: **NEEDS_IMPROVEMENT**

`api/security.py` sets: `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy`. The Next.js server additionally sets CSP, HSTS,
`Cross-Origin-Opener-Policy`, and `Cross-Origin-Resource-Policy`; the production
build was smoke-tested locally with those headers. Development CSP allows
`unsafe-eval` for Next.js dev tooling; production CSP does not.

Gaps: the production CSP still permits `unsafe-inline`; HSTS must be verified
at the real TLS termination point, including subdomain and preload readiness.
Headers have not been validated through the deployed CDN/ALB.

## 9. Authentication & sessions

Status: **NEEDS_IMPROVEMENT**

Ready: Argon2id password hashing (`auth/security.py`), sha256 digests for
tokens, HS256 short-lived access JWT (900 s) + 30-day refresh, OTP (max 5
attempts, 600 s TTL, 120 s resend cooldown), rate limits on 14 auth routes
(`users_auth.py`), OAuth sign-in (Google — verify current provider config in
staging/prod), refresh-token rotation + revocation endpoints.

TOTP MFA and per-account login backoff are implemented and covered by tests.
Production/staging configuration fails closed unless
`TK_MFA_ENFORCE_PRIVILEGED=true`; that setting and required role enrollment
still need verification in the real environment.

Gaps (brief §9–13, §68):
- Password reset + OTP enumeration hardening not fully verified.
- Session/device management (list) not verified.

## 10. Authorization & IDOR

Status: **NEEDS_IMPROVEMENT**

Ready: RBAC roles + permission keys; `require_active(...)` dependency gates;
ownership checks on user-scoped routes (e.g. export jobs, saved queries,
corrections); department scope checks in `cases`/`departments` modules;
`core/audit.py` audit trail.

Focused IDOR and tenant-isolation tests cover reports, evidence objects, cases,
users, and institutions in `tests/test_security_authorization.py`; they passed
in the non-integration suite. Remaining gap: broaden the role/resource matrix
and verify authorization against production-like seeded tenants.

## 11. AI / RAG / MCP tools

Status: **NEEDS_IMPROVEMENT**

Ready: provider fallback chain (big-model → small → deterministic StubGateway,
`ai/gateway.py`), tool registry with per-tool schemas + risk levels
(`ai/tools.py`), RAG with "unable to retrieve supporting information" behavior
(verify `rag.py`), tool execution catches errors into structured
`{"error": ...}` (no invented output), per-tool permission annotations.

Gaps (brief §46–§54, §115):
- Tool authorization: verify each tool call enforces the caller's role/scope
  end-to-end (currently `registry.execute` has no session-level user context —
  verify orchestrator passes it).
- No AI cost per feature/model/provider/user tracking.
- No explicit indirect prompt-injection quarantine for imported documents
  (RAG chunks) independent of user content.
- No red-team test suite (§115).

## 12. Storage, media, uploads, notifications

Status: **NEEDS_IMPROVEMENT**

Ready: upload flow = idempotent presigned URL request → PUT → complete →
scan gate ("magic-byte verification, dimension caps", `media/scan.py`) +
thumbnail + strip-metadata save; MIME allowlist + size cap (8 MB) +
`media_allowed_mime`; MinIO/S3 + CloudFront OAI in TF; presigned URLs for
downloads; console sandbox SMS/email with DLT open question.

Gaps: ClamAV/malware scanning is a *dev slot* — no antivirus in production
path; no video processing (only image thumbnail); no resumable/multipart
upload beyond presigned PUT; no retention/lifecycle policy on MinIO/S3 buckets;
no notification delivery SLAs enforcement beyond queue length.

## 13. Database

Status: **NEEDS_IMPROVEMENT**

Ready: Postgres 16 + PostGIS + pgvector (native), 27 migrations with
upgrade/downgrade round-trip in CI (`fresh-db-migrations` job),
checksum-critical TZ correctness, `create_engine` pooling defaults, no
superuser app role in TF (`tk_app` least-privilege), RDS encryption at rest +
deletion protection (prod), SSL via RDS.

Gaps: no EXPLAIN/index-usage audit for hot paths (reports feed, GIS viewport,
notifications, analytics rollups); no connection-pool tuning evidence;
no partitioning plan; PITR configured implicitly (retention 7) — must become
an explicit, documented policy.

## 14. Caching, queues, workers, resilience

Status: **NEEDS_IMPROVEMENT**

Ready: Redis-backed token bucket with in-memory fallback
(`core/rate_limit.py` — degradation documented); idempotency store on Redis
(`core/idempotency.py`); analytics cache; Celery with JSON serialization,
time limits (150/180 s), beat schedule (notifications 60 s, rollups 1 h,
SLA 60 s), connection retry on startup; report/case state machine transitions.

Gaps: no per-task retry/backoff/max-retries, no dead-letter queue/table, no
task idempotency keys on notify/export paths, no Redis failover story beyond
memory fallback, no backlog alerting metrics wiring beyond queue gauge (verify
`rules.yml`), notification dispatch flaky test (quiet-hours — §16).

## 15. Observability

Status: **READY (partial)** → `READY` after verification

Ready: structured JSON logs with request_id via contextvar
(`core/logging.py`, `api/middleware.py`), `/metrics` Prometheus
(`core/metrics.py` request histogram/counters, route-group labels), liveness
`/healthz` + readiness `/readyz` (DB check only, fail → 503 without dependency
death spiral), OTel export opt-in (`TK_OTEL_ENABLED`, `core/otel.py`), SLOs
doc (`docs/SLOs.md`) with Prom alert rules + Grafana dashboard (provisioned),
k6 smoke with SLO thresholds.

Gaps: no traces propagation beyond request_id (OTel off by default), no
error-tracking integration (Sentry etc.), no alert routing documented past
`rules.yml`, no ops/status dashboard for the frontend.

## 16. Reliability / testing

Status: **NEEDS_IMPROVEMENT**

- Backend lint, formatting, type checks, and non-integration tests passed on
  2026-10-14 (604 passed, 1 skipped). Ten PostgreSQL integration tests passed
  against an isolated database; the backup/restore test was not run locally
  because it creates and drops two temporary databases.
- Migration-to-head and the Phase 3 registry/report/provenance integration
  test passed after fixing long Alembic revision storage and making fixtures
  independent of pre-seeded shared data.
- JWT test keys now meet the SHA-256 HMAC minimum length. The only test-suite
  warning is Starlette's deprecation notice for its httpx-backed TestClient.
- No load/spike/chaos evidence beyond k6 SLO smoke (10 VU/30 s).
- No end-to-end civic lifecycle test (brief §157) and no complete
  authorization lifecycle test (brief §158).

## 17. India-scale readiness

Status: **NEEDS_IMPROVEMENT**

Ready: en/hi localization + i18n infra (`docs/I18N.md`, `apps/web/src/lib/i18n*`),
Asia/Kolkata default (`quiet_hours_default`, celery timezone), Indian number
formatting (analytics), IST date handling in `resolve_date_bounds`, PWA
(manifest + `sw.js` + `PwaRegistration`), boundary ingest (India ADM-1 with
versioned labels).

Gaps: only en+hi shipped (target 13 languages unverified), no regional
language QA harness, low-bandwidth (image compression/lazy loading) not
verified, offline report draft not implemented (PWA shell only).

## 18. Frontend

Status: **NEEDS_IMPROVEMENT**

Ready: `reactStrictMode`, `output: standalone`, proxy rewrites for `/api/v1`
and `/api/public/v1`, PWA assets, CSP/HSTS and related security headers in
`next.config.ts`, Vitest 4.1.11 (63 tests passing), and a successful Next.js
16.4.0 production build. Local dev and production preview routes both returned
HTTP 200; the prod CSP excludes `unsafe-eval`.

Gaps: full `npm audit` still reports five HIGH issues in transitive
development-only lint dependencies. Production dependencies currently audit
clean; CI gates that production dependency audit. No e2e execution evidence
beyond Playwright scaffolding (`web-e2e`).

## 19. Infrastructure, CI/CD, cost

Status: **READY (unapplied)** for infra; **NEEDS_IMPROVEMENT** for CI/CD/cost

Ready: Terraform (ECS Fargate api/worker/web, ALB with TLS1.2/1.3, RDS 16
encrypted + deletion protection, ElastiCache, S3 + CloudFront OAI, Secrets
Manager, OIDC GitHub → AWS), CI gates (ruff/mypy/pytest, integration on real
PostGIS, migration upgrade↔downgrade round-trip, Trivy FS + image scan,
web lint/tsc/build), deploy workflow with ECS rolling
(`force-new-deployment`, `services-stable` wait), rollback workflow
(previous task-def revision), smoke step after deploy.

Gaps:
- Terraform never applied (`terraform validate` is the only gate; no plan/apply
  evidence in CI; no AWS account/OIDC provider bootstrap).
- No review/approval gate between migration and production deploy (single job
  chain), no canary, no DB-compat rollback analysis, no staging smoke for web.
- No cost instrumentation (CloudWatch billing, AI cost per feature) anywhere.
- No autoscaling policies (fixed desired_count).

## 20. Disaster recovery, backup, compliance

Status: **BLOCKED**

- `docs/DISASTER-RECOVERY.md` defines proposed RPO/RTO targets and a restore
  procedure; these remain a framework, not measured service objectives.
- `tests/integration/test_backup_restore.py` exercises a synthetic logical
  dump/restore and runs in the integration CI job, but was not executed in this
  local session. No AWS RDS snapshot/PITR restore has been demonstrated.
- RDS retention=7 is configured; restore has not been exercised against the
  production infrastructure. No incident response/on-call process or status
  page has been verified.
- Privacy: account deletion + anonymization exists (`DELETE /users/me`,
  `auth/service.py` §7); DPDP doc exists; but PII inventory, retention
  schedule, and deletion of media/evidence workflows are undefined.

---

## 21. Top gaps to close in Phase 16 (ranked)

1. Source control: initial commit + branch protection (unblocks everything).
2. DR: approve and run CI restore test; exercise AWS RDS recovery and verify
   the proposed RPO/RTO in `DISASTER-RECOVERY.md`.
3. Security: verify privileged MFA enforcement, TLS/HSTS at the deployed edge,
   CSP policy, and Terraform secret/state handling in a staging deployment.
4. Observability: enable OTel traces, alert routing, ops dashboard.
5. Reliability: task retries/backoff + DLQ, idempotency on queue-dispatch,
   fix flaky community/notification tests.
6. Scale evidence: load/spike/chaos test plan with real numbers.
7. India scale: regional language QA + low-bandwidth + offline draft.
8. Docs from Phase 15 backlog (PUBLIC-API/OPEN-DATA/DATA-METHODOLOGY/
   DATA-GOVERNANCE) plus all Phase 16 required docs.

Category status at the end of Phase 16 will be re-reported with evidence
(`GO / NO-GO / CONDITIONAL GO` in the final report).