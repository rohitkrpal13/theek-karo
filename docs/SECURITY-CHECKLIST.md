# SECURITY CHECKLIST — Phase 10 hardening pass

Status: ✅ implemented · 🔶 partial (deferred item tracked) · ⬜ not applicable.
Reviewed against `docs/SECURITY.md` (threat model §1, authn §2, authz §3, API
§4, data §5, audit §6, secrets §7, infra §8, AI §9, IR §10, compliance §11).

## Authentication & session (§2)
- ✅ Phone/email OTP with rate limits, lockout on max attempts, resend cooldown
- ✅ Argon2id password hashing; no plaintext secrets in transit (`TK_JWT_*` dev keys documented)
- ✅ JWT access (15 min) + rotating refresh with family reuse detection (ADR-008)
- 🔶 MFA/TOTP for officials/admins — deferred (Phase 10 note; not required for MVP pilot)

## Authorization (§3)
- ✅ RBAC: citizen/volunteer/official/admin enforced per endpoint; admin-only config writes
- ✅ Report transitions role-gated; AI merge decisions admin-gated (ADR-018)
- ✅ Self-admin revocation blocked; role changes audited

## API hardening (§4)
- ✅ RFC 9457 problem+json everywhere; no stack traces to clients
- ✅ Rate limiting (auth strict, writes moderate, receipts bounded) with 429 + Retry-After
- ✅ **NEW (Phase 10):** security headers middleware — nosniff, X-Frame DENY,
  Referrer-Policy, Permissions-Policy on every response
- ✅ Timeouts on AI gateway + storage clients; worker task time limits
- 🔶 HSTS — deferred to the CDN/ALB layer in prod (Phase 11)

## Data protection (§5)
- ✅ Private-by-default media; owner/admin-only reads; presigned URLs 15-min expiry
- ✅ Scan gate never serves failed media; PII-insulated AI payloads (ADR-019)
- ✅ Retention documented (DATABASE.md §7); DPDP memo in `COMPLIANCE-DPDP.md`
- 🔶 Encryption at rest is cloud-provider default (RDS volumes) — Phase 11

## Audit (§6)
- ✅ Append-only audit_logs for auth/config/media/review/notification-privacy actions
- ✅ Report timelines append-only (per-report audit)
- 🔶 Admin console for audit browsing — deferred to the admin UI workstream

## Secrets (§7)
- ✅ `.env.example` documents required vars; `.env` git-ignored; dev-only defaults never prod-safe
- ✅ JWT secret, MinIO creds, Gem: no secrets committed; compose uses env interpolation
- 🔶 Vault/secret-manager wiring — Phase 11

## Infrastructure (§8)
- ✅ Compose healthchecks + depends_on gating; worker healthcheck via `celery inspect ping`
- ✅ Non-root runtime user in the API image; only dev host ports exposed
- ✅ **NEW (Phase 10):** observability stack (Prometheus/Grafana) isolates probing from user traffic; metrics are read-only
- 🔶 WAF/CDN, network segmentation, TLS termination — Phase 11

## AI security (§9)
- ✅ T4 envelope mandatory; schema CHECK prevents self-declared verified status
- ✅ Human review gate on merges, PII-insulated prompts, provider no-training contract documented
- ✅ Eval harness pins floors (category accuracy) — metrics recorded

## Incident response (§10)
- ✅ Runbooks drafted (docs/RUNBOOKS.md) — severity ladder + 7 scenarios
- ✅ DPDP 72-hour breach notification draft inside the runbook + memo
- 🔶 24×7 on-call roster + Alertmanager channel — Phase 11

## Compliance (§11)
- ✅ DPDP memo (docs/COMPLIANCE-DPDP.md): consent records, purpose bounds,
  retention, rights flows, breach process — awaiting counsel review (tracked)

## Phase 10 gate
The checklist above is the Phase 10 security pass. Blockers: none.
Deferred items are explicitly tracked in IMPLEMENTATION-STATUS Phase 10
limitations and reopen with the listed phases.
## Phase 11 additions

- ✅ Deploy secrets flow through AWS Secrets Manager + ECS `secrets` (no env
  plaintext); GitHub uses OIDC (no static cloud keys).
- ✅ HSTS + TLS: ALB terminates TLS13-1-2 with ACM certs; the web serves
  HSTS once CloudFront/ALB headers are wired (in the Terraform/ALB headers
  configuration).
- ✅ Container image + repo source scanned by Trivy in CI (HIGH/CRITICAL).
- ✅ Database: RDS encrypted at rest, deletion-protected in prod, 7-day
  backups + final snapshot policy (staging skips).
- ✅ Rollback drill: `.github/workflows/rollback.yml` + RUNBOOKS#rollback.
- 🔶 Route53 real domain + ACM validation + WAF rules: wired in the repo
  config; live DNS/registration is org action at first apply.

---

## Phase 16 hardening audit (Steps 3–18) — 2026-08-18

Consolidated result of the Phase 16 hardening program. All items implemented
and verified by automated tests unless marked otherwise.

### Step 3 — Flaky tests
- ✅ Community harness + notifications quiet-hours determinism fixed; full
  suite deterministic (289 unit tests green).

### Step 4 — Auth hardening
- ✅ MFA (TOTP, RFC 6238-verified) for privileged roles with challenge TTL,
  attempt caps and backoff; enforced at the authorization dependency layer
  (`auth/authorization.py`), not just the login endpoint.
- ✅ Per-account login backoff/lockout (exponential, windowed).

### Step 5 — Authorization audit + IDOR suite
- ✅ `tests/test_security_authorization.py`: report field/evidence ownership,
  private-report 404-by-id, evidence object + thumbnail visibility gates,
  department/tenant case isolation.

### Step 6 — Input validation + upload security
- ✅ Media scan gate strengthened: full WebP/PNG signatures, decodability
  check (blocks HTML polyglots), pixel/dimension caps (decompression bombs).
- ✅ Per-user upload request/complete rate limits; JSON parse guards (422);
  Content-Length pre-checks on dev PUT; nosniff + server-generated
  Content-Disposition on every media response; no client filenames stored.
- ✅ Evidence download route (`/media/{id}/download`) now exists and is
  visibility-gated (previously 404).

### Step 7 — Object storage audit
- ✅ Production S3 bugs fixed: `secure` + `region` now configurable and set in
  terraform (presigned URLs were signed for localhost/us-east-1);
  `TK_MEDIA_MINIO_PUBLIC_ENDPOINT` set; CloudFront forwards query strings;
  IAM media key scope reduced (no ListBucket).
- ✅ Private-report evidence thumbnails no longer world-readable.

### Step 8 — PII inventory + retention + deletion
- ✅ `docs/PII-DATA-INVENTORY.md` (authoritative inventory + retention table).
- ✅ Daily purge job (`tk_worker.purge_expired_pii`): tokens 90 d, sessions
  180 d, verification codes 30 d, security events + API usage 365 d, AI
  conversations 90 d. Account deletion anonymizes immediately; tombstones are
  permanent (FK integrity).

### Step 9 — Database hardening
- ✅ Configurable pool (10 + 20 overflow, 1800 s recycle, pre_ping) wired into
  API + worker.
- ✅ 7 hot-path indexes added (feed composite, boundary+created, category,
  reporter, evidence media lookup, reactions, notifications inbox); migration
  0030 verified on Postgres.

### Step 10 — Backup + DR
- ✅ Prod RDS multi-AZ; media bucket versioning + 30 d lifecycle; Redis daily
  snapshot; `docs/DISASTER-RECOVERY.md` (RPO/RTO + runbook).
- ✅ Real restore test: `tests/integration/test_backup_restore.py` (pg_dump →
  psql round-trip).

### Step 11 — Redis + queue reliability
- ✅ Celery: acks_late + reject_on_worker_lost (at-least-once), retry backoff +
  jitter on durable tasks, Redis dead-letter list `tk:dlq`.
- ✅ `recover_stuck_jobs` beat sweep re-drives stuck `pending_scan` media.

### Step 12 — AI safety
- ✅ Tool authorization enforced at the registry (`required_role`), verified
  all shipped tools are public/READ_ONLY; daily per-user chat cap (300/d)
  added on top of per-minute rate limits.
- ✅ Verified: provider fallback chain, PII redaction, injection-boundary
  system rules.

### Step 13 — Observability
- ✅ `/live` + `/livez` added (liveness/readiness aliases complete); worker
  logs are now structured JSON with request correlation.

### Step 14 — Frontend security
- ✅ Web security headers (CSP, X-Frame DENY, nosniff, Referrer-Policy,
  Permissions-Policy, HSTS) verified on the production server.
- ✅ `npm audit` 0 vulnerabilities; `pip-audit` 0 vulnerabilities.

### Step 15 — CI/CD
- ✅ pip-audit + npm audit wired into CI; existing deploy (migrations-first,
  pinned image, stable-wait, smoke) + rollback workflows validated.
- ✅ **Bandit + Semgrep SAST** added to the `security-scan` CI job (both fail on
  any finding); initial run fixed 7 Bandit + 5 Semgrep findings (details in
  `SECURITY-TESTING.md` §1).

### Step 16 — IR + release + go-live
- ✅ Incident-response lifecycle added to `RUNBOOKS.md`; `docs/RELEASES.md`;
  `docs/GO-LIVE-CHECKLIST.md`.

### Step 17 — India-scale readiness
- ✅ Hindi-first default locale aligned (web `DEFAULT_LOCALE = "hi"`, matches
  API default); 15 locales declared; UTC storage + Asia/Kolkata quiet hours;
  low-bandwidth via server thumbnails + cursor pagination.

### Step 18 — Security testing + scale
- ✅ `docs/SECURITY-TESTING.md` (SAST in CI, ZAP DAST prep, red-team + AI red
  team playbook); `docs/SCALE-TEST-REPORT.md` (k6: p95 11.9 ms, 0% 5xx at
  ~235 req/s on compose).
- ✅ Bandit + Semgrep SAST now in CI (2026-08-18), both clean.
- 🔶 Staging ZAP active scan remains a pre-go-live task.
