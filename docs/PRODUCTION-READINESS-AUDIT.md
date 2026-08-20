# Production Readiness Audit (Phase 16)

Status: **Initial audit — 2026-08-17**

This document is the Phase 16 baseline audit of the Theek Karo platform. Every
statement is backed by repository evidence (file paths + observed behavior).
Nothing in this document claims readiness without verification.

Legend: `READY` · `NEEDS_IMPROVEMENT` · `BLOCKED` · `UNKNOWN`

---

## 0. Evidence basis

Audit performed against the working tree (no git history — see §4) with:

- Backend: `services/api/src/tk_api` — 133 files type-checked clean (`mypy --strict`),
  204 files ruff-clean (`ruff check .` + `ruff format --check .`).
- Tests: `237 passed / 4 failed` on `pytest -q` (failures: 3 pre-existing
  `tests/test_community.py` harness issues + 1 time-of-day-flaky
  `test_notifications_db` quiet-hours mismatch — see §16).
- CI: `.github/workflows/{ci,deploy,rollback}.yml`; infra: `infra/terraform/main.tf`,
  `infra/prometheus/{prometheus,rules}.yml`, `infra/grafana/`, `infra/k6/slo-smoke.js`.
- Compose stack: postgres (postgis 16), redis 7, minio, api, worker (+ prometheus,
  grafana) with healthchecks.
- Frontend: `apps/web` (Next.js 16, standalone output, proxy to API, PWA manifest
  + service worker present).

---

## 1. Summary matrix

| Area | Status | Primary evidence |
|------|--------|------------------|
| Architecture | READY | `docs/ARCHITECTURE.md`; monolith + worker, modular routers |
| Security (application) | NEEDS_IMPROVEMENT | Headers/CSP/MFA gaps (§8) |
| Authentication | NEEDS_IMPROVEMENT | Argon2id + JWT strong; no MFA, no lockout (§9) |
| Authorization | NEEDS_IMPROVEMENT | RBAC + permissions + ownership checks exist; IDOR suite not yet run (§10) |
| Database | NEEDS_IMPROVEMENT | PostGIS/PG16, migrations round-trip in CI; index plan audit missing (§13) |
| API | NEEDS_IMPROVEMENT | Problem+JSON, rate limits, request IDs; public API v1 not proxied by web (§3) |
| Frontend | NEEDS_IMPROVEMENT | PWA present; CSP/HSTS headers absent at app layer (§18) |
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
| Disaster Recovery | BLOCKED | No RPO/RTO, no backup restore test, no DR docs (§16) |
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

Gaps:
- `/api/public/v1` is not proxied by the Next.js rewrite table
  (`apps/web/next.config.ts` only rewrites `/api/v1/:path*`) — the Phase 15
  public API is unreachable from the web app in dev/self-host.
- No global request-body size middleware beyond per-route validation
  (`max_request_body_bytes` setting exists, enforcement not verified).
- No API versioning policy doc beyond `api_v1_prefix`.

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
- `infra/terraform/main.tf` renders `TK_DATABASE_URL` with
  `var.db_password` into the ECS task environment (plaintext in task
  definition) — move to Secrets Manager like JWT/AI keys (§8 of brief).
- Worker task definition omits `TK_MEDIA_MINIO_SECRET_KEY` entirely —
  worker-side media jobs would lack credentials (needs verification or
  completion of the secret mapping).

## 8. Application security headers

Status: **NEEDS_IMPROVEMENT**

`api/security.py` sets: `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy`. Gaps: no `Content-Security-Policy`, no `HSTS`
(intentionally deferred to CDN/ALB per comment — must be implemented in
TERRAFORM/ALB listener and verified, not promised), no `Cross-Origin-*
` resource policy. CSP must not break the Next.js app (brief §78).

## 9. Authentication & sessions

Status: **NEEDS_IMPROVEMENT**

Ready: Argon2id password hashing (`auth/security.py`), sha256 digests for
tokens, HS256 short-lived access JWT (900 s) + 30-day refresh, OTP (max 5
attempts, 600 s TTL, 120 s resend cooldown), rate limits on 14 auth routes
(`users_auth.py`), OAuth sign-in (Google — verify current provider config in
staging/prod), refresh-token rotation + revocation endpoints.

Gaps (brief §9–13, §68):
- **No MFA** for admin/department-manager/mod reviewer roles.
- **No account lockout/backoff** — only IP rate limits; no per-account
  throttling (brute-force/credential-stuffing exposure).
- Password reset + OTP enumeration hardening not explicitly tested.
- Session/device management (list) not verified.

## 10. Authorization & IDOR

Status: **NEEDS_IMPROVEMENT**

Ready: RBAC roles + permission keys; `require_active(...)` dependency gates;
ownership checks on user-scoped routes (e.g. export jobs, saved queries,
corrections); department scope checks in `cases`/`departments` modules;
`core/audit.py` audit trail.

Gaps: no automated IDOR test suite (brief §15: `/reports/{id}`,
`/cases/{id}`, `/users/{id}`, `/institutions/{id}`, `/documents/{id}`);
tenant-isolation matrix (department A ≠ B, district A ≠ B) not systematically
tested. Phase 16 must add these tests (Step 26 `tests/test_security_authorization.py`).

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

- `pytest`: 237 passed / 4 failed. Failures:
  - 3× `tests/test_community.py` — pre-existing harness defects around
    follow/notification grouping (double `_setup`, worker-dispatch mocks);
    known since before this phase, no product regression.
  - 1× `tests/integration/test_notifications_db.py` — quiet-hours window
    (21:00–07:00 IST): sms/email rows deferred, receipts asserted
    unconditionally → flaky by time-of-day, not a code regression.
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

Ready: `reactStrictMode`, `output: standalone`, proxy rewrite for `/api/v1`,
PWA assets, tested (vitest 37 passed previously — re-verify on Phase 16 gate),
build green.

Gaps: no CSP/security headers on the web server, no `headers()` config in
`next.config.ts`, no dependency audit step for the frontend, `/api/public/v1`
rewrite missing (§3), no e2e harness evidence beyond Playwright scaffolding
(`web-e2e`).

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

- RDS retention=7 (implicit daily + PITR window) — but RPO/RTO not defined,
  restore never exercised, no backup restore test in CI or docs.
- No DR document, no runbook beyond `docs/RUNBOOKS.md` promise, no incident
  response process, no status page, no backup/restore automation.
- Privacy: account deletion + anonymization exists (`DELETE /users/me`,
  `auth/service.py` §7); DPDP doc exists; but PII inventory, retention
  schedule, and deletion of media/evidence workflows are undefined.

---

## 21. Top gaps to close in Phase 16 (ranked)

1. Source control: initial commit + branch protection (unblocks everything).
2. DR: RPO/RTO definitions, automated backup + restore test, `DISASTER-RECOVERY.md`.
3. Security: MFA for privileged roles, account backoff, CSP+HSTS, IDOR suite,
   worker MinIO secret fix, move DB URL to Secrets Manager in TF.
4. Observability: enable OTel traces, alert routing, ops dashboard.
5. Reliability: task retries/backoff + DLQ, idempotency on queue-dispatch,
   fix flaky community/notification tests.
6. Scale evidence: load/spike/chaos test plan with real numbers.
7. India scale: regional language QA + low-bandwidth + offline draft.
8. Docs from Phase 15 backlog (PUBLIC-API/OPEN-DATA/DATA-METHODOLOGY/
   DATA-GOVERNANCE) plus all Phase 16 required docs.

Category status at the end of Phase 16 will be re-reported with evidence
(`GO / NO-GO / CONDITIONAL GO` in the final report).