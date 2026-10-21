# TheekKaro Civic Social Amplification: Final Production Go-Live Security & Reliability Audit

**Audit Date:** 2026-10-21
**Auditor Roles:** Principal Software Architect, Senior Python/FastAPI Engineer, OAuth Security Specialist, Celery/Redis Reliability Engineer, Application Security Auditor
**Target Capability:** Civic Social Amplification (𝕏 / Twitter Web Intents, Instagram 9:16 Story Cards, WhatsApp Mobilization, Municipal Authority Tagging, and Autonomous Civic Bot Worker Pipeline)
**Report Artifact Location:** `docs/production-readiness/social-amplification-audit.md`
**Runbook Location:** `docs/runbooks/social-broadcast-worker.md`
**Final Production Readiness Decision:** **`READY_WITH_CONDITIONS`**

---

## 1. Executive Summary & Verification Matrix

This audit constitutes the final independent security, reliability, and mathematical correctness review of TheekKaro Civic Social Amplification prior to enabling autonomous public social broadcasts.

| Dimension / Requirement | Previous Reported State | Final Verified State | Evidence & Verification Outcome |
|---|---|---|---|
| **Final Decision** | `READY` (claimed) | **`READY_WITH_CONDITIONS`** | Live external X publishing gated on human authorization & verified credentials. |
| **Audit A: OAuth 1.0a Correctness** | Syntactic header presence only | **RFC 5849 Errata ID 2550 Verified** | Exact HMAC-SHA1 signature bytes match official IETF test vector (`r6/TJjbCOr97/+UU0NsvSne7s5g=`). URI normalized, query params extracted & canonicalized. App-only bearer tokens rejected. |
| **Audit B: Timeout & Duplicate Safety** | Blind retry on `TimeoutException` | **`outcome_unknown` Quarantine State** | Distinguishes `ConnectTimeout` (retryable) from in-flight `ReadTimeout` / `WriteTimeout` (non-retryable `outcome_unknown`). Zero blind duplicate posts. Operator reconciliation procedure implemented. |
| **Audit C: Emergency Kill-Switch** | Startup config check only | **Multi-Stage Autorun Guard** | `TK_SOCIAL_BROADCAST_MODE=disabled` checked at API creation, worker claim, pre-publish invocation, and periodic beat sweeps. |
| **Audit D: Database & Task Reliability** | Application-level `if not existing` | **Atomic DB Claim & Partial Unique Indexes** | `uq_social_broadcasts_active_report` includes `('queued', 'processing', 'published', 'outcome_unknown')`. Atomic `UPDATE ... WHERE status IN ('queued', 'retry_wait')`. DLQ durability on Celery `DurableTask`. |
| **Audit E: Authorization & Privacy** | Optional unauthenticated GET | **Strict BOLA/IDOR Protection** | `POST` and `GET` require `ReporterUser` and check `is_reporter or is_staff` (`403 broadcast_unauthorized`). Draft and private reports strictly blocked. PII sanitized. |
| **Audit F: Operational Runbooks** | Generic deployment notes | **Comprehensive Failure Runbook** | Detailed step-by-step operator reconciliation runbook, DLQ replay procedures, and kill-switch instructions in `docs/runbooks/social-broadcast-worker.md`. |
| **Backend Test Suite** | 625 Passed (reported) | **641 Passed, 1 Skipped, 11 Deselected** | 642 selected non-integration tests pass cleanly in 140s. |
| **Targeted Amplification & Queue Tests** | 25 Passed | **41 Passed, 0 Failed** | 33 passed in `test_social_amplify.py` + 8 passed in `test_queue_reliability.py` (including stranded task recovery from PostgreSQL and attempts exhaustion). |
| **Frontend Test Suite** | 72 Passed | **72 Passed across 19 files** | Modal polling, status transitions, accessibility announcements (`aria-live="polite"`), and official/unverified authority badge rendering. |
| **Static Analysis** | Reported Clean | **100% Clean** | Ruff: Clean, Ruff Format: Clean (329 files), Mypy: Clean (217 files), ESLint: Clean, TSC: Clean. |

---

## 2. Audit A: Independent OAuth 1.0a Verification

### Mathematical Correctness & RFC 5849 Ground Truth
Twitter/X API v2 `POST /2/tweets` requires User Context authorization. The implementation was audited for RFC 5849 compliance across all required sub-specifications:

1. **HTTP Method Normalization (§3.4.1.1):** Uppercase `POST`.
2. **Base String URI Normalization (§3.4.1.2):**
   - Scheme and authority converted to lowercase (`http://` or `https://`, lowercase host).
   - Default ports (`:80` for HTTP, `:443` for HTTPS) stripped.
   - Query parameters and fragments excluded from the Base String URI and redirected into the parameter collector.
3. **Parameter Canonicalization (§3.4.1.3):**
   - OAuth parameters, query string parameters, and extra body parameters collected into a single collection.
   - All keys and values percent-encoded using RFC 5849 §3.6 rules (`ALPHA / DIGIT / "-" / "." / "_" / "~"` unreserved).
   - Parameters sorted canonically: first by encoded key ascending, then by encoded value ascending.
   - Parameters joined with `=` and delimited by `&`.
4. **Signature Base String Construction (§3.4.1.1):**
   - `HTTP_METHOD + "&" + percent_encode(normalized_uri) + "&" + percent_encode(param_string)`.
5. **Signing Key Derivation (§3.4.2):**
   - `percent_encode(consumer_secret) + "&" + percent_encode(token_secret)`.
6. **HMAC-SHA1 & Base64 Encoding:**
   - Raw SHA1 HMAC computed over the Base String using the Signing Key, and standard Base64-encoded.

### Verification Against IETF RFC 5849 Errata ID 2550
In the original IETF RFC 5849 specification (sections 3.1 & 3.4.1.1), the published example erroneously listed `bYT5CMsGcbgUdFHObYMEfcx6bsw%3D` as the signature for a `POST` request (which was mistakenly computed using `GET`). IETF Errata ID 2550 (verified by Peter Saint-Andre) establishes the authoritative `POST` signature vector:

- **Method:** `POST`
- **Request URL:** `http://example.com/request?b5=%3D%253D&a3=a&c%40=&a2=r%20b`
- **Consumer Key:** `9djdj82h48djs9d2`
- **Consumer Secret:** `j49sk3j29djd`
- **Token:** `kkk9d7dh3k39sjv7`
- **Token Secret:** `dh893hdasih9`
- **Timestamp:** `137131201`
- **Nonce:** `7d8f3e4a`
- **Extra Entity Body Parameters:** `c2` and `a3=2+q`
- **Expected HMAC-SHA1 Signature:** `r6/TJjbCOr97/+UU0NsvSne7s5g=` (`r6%2FTJjbCOr97%2F%2BUU0NsvSne7s5g%3D`)

**Verification Result:** Test `test_rfc5849_errata2550_official_test_vector` executed in pytest directly invokes `LiveXPublisher._build_oauth1_header` and asserts exact byte-for-byte matching with `r6/TJjbCOr97/+UU0NsvSne7s5g=`. Passed.

### Account Context & Bearer Token Guard
Twitter API v2 `/2/tweets` rejects Application-Only Bearer Tokens with HTTP 403 Forbidden.
- **Guard Implemented:** `LiveXPublisher._build_headers()` explicitly checks if only `twitter_bearer_token` is present without the 4 OAuth 1.0a User Context credentials. It logs an error and returns an empty header mapping, preventing spurious 403 network calls and categorizing the broadcast as `not_configured`.
- **Secret Redaction:** Consumer secrets and token secrets are strictly held in private adapter attributes and never logged, exposed in error payloads, or returned in API responses.

---

## 3. Audit B: Ambiguous Timeout & Duplicate-Publication Safety

### The Ambiguous Timeout Failure Mode
In high-concurrency cloud networks, the following failure sequence can occur:
1. Celery worker claims broadcast and issues `POST https://api.x.com/2/tweets`.
2. Twitter receives the request, publishes the tweet publicly to the timeline, and prepares HTTP 201 Created.
3. A network disruption or intermediate proxy drop causes a client socket timeout (`httpx.ReadTimeout` or `httpx.WriteTimeout`) before the client reads the response.
4. The worker receives an exception without the external tweet ID.
5. **Historical Vulnerability:** The previous code treated all `httpx.TimeoutException` instances as `retryable=True`. On automatic Celery or beat retry, the worker re-transmitted the text, creating duplicate identical public tweets.

### Implemented Zero-Duplicate Reconciliation Architecture

```
                                  Outbound Request to X
                                            |
                         +------------------+------------------+
                         |                                     |
                Pre-Connection Failure                 In-Flight / Post-Connect
             (ConnectTimeout, ConnectError)           (ReadTimeout, WriteTimeout)
                         |                                     |
               Request NEVER reached X               Outcome is AMBIGUOUS
                         |                                     |
                   retryable=True                       retryable=False
               outcome_unknown=False                 outcome_unknown=True
                         |                                     |
                  Status: retry_wait                  Status: outcome_unknown
                         |                                     |
                  Celery Backoff Retry                AUTOMATIC RETRIES HALTED
                                                      Exempt from Celery retry
                                                      Exempt from Beat recovery sweep
                                                      Report blocked from re-broadcasting
                                                               |
                                                               v
                                                    Operator Reconciliation Runbook
                                                    (Verify X Account -> Reconcile)
```

1. **Exception Differentiation in `LiveXPublisher.publish()`:**
   - `httpx.ConnectTimeout` and `httpx.ConnectError`: Connection was never established; request never left the host. Safe to retry (`ok=False, retryable=True, outcome_unknown=False`).
   - `httpx.ReadTimeout`, `httpx.WriteTimeout`, and generic `httpx.TimeoutException`: Request was transmitted over TCP; outcome cannot be confirmed. `ok=False, retryable=False, outcome_unknown=True`.
2. **State Transition to `outcome_unknown`:**
   - In `execute_broadcast()`, when `result.outcome_unknown` is True, `broadcast.status` transitions to `"outcome_unknown"`.
   - Celery retry is NOT scheduled.
   - Beat recovery sweep `recover_stuck_broadcasts` deliberately ignores `outcome_unknown` records.
3. **Database-Level Active Record Lock:**
   - `SocialBroadcast` partial unique index `uq_social_broadcasts_active_report` includes `'outcome_unknown'`:
     `WHERE status IN ('queued', 'processing', 'published', 'outcome_unknown')`.
   - A report with an uncertain broadcast cannot have another broadcast created by any user until the outcome is resolved.
4. **Worker Crash Recovery During `live` Execution:**
   - If a worker process crashes (OOM, SIGKILL) while executing a `live` broadcast in `processing` status, `recover_stuck_broadcasts()` transitions the record to `outcome_unknown` rather than blind re-queuing, preventing duplicate posting upon container restart.
5. **Operator Reconciliation Procedure:**
   - Added `reconcile_broadcast_outcome(session, broadcast_id=..., outcome="published"|"failed", external_post_id=..., resolution_note=...)`.
   - If `published`, requires `external_post_id` confirmed from X timeline, sets `status="published"`, `published_url=https://x.com/TheekKaro/status/{id}`, and records audit log.
   - If `failed`, sets `status="failed"`.

---

## 4. Audit C: Emergency Kill-Switch Behavior & Boundaries

### Configuration
Controlled cluster-wide by `TK_SOCIAL_BROADCAST_MODE=disabled`.

### Multi-Stage Autorun Interception
The kill-switch is enforced dynamically at four independent checkpoints without requiring database schema alterations:
1. **API Submission Guard:** In `create_broadcast_request()`, if `social_broadcast_mode == "disabled"`, the broadcast record is created with `status = "disabled"` and `last_error = "Civic bot social broadcasting is currently disabled by administrator configuration."`. No task is enqueued to Celery.
2. **Worker Pre-Claim Check:** In `execute_broadcast()`, before claiming the row or touching report entities, `settings.social_broadcast_mode` is evaluated. If disabled, the record transitions to `disabled`, logs `report.social_broadcast_disabled`, and returns immediately.
3. **Pre-Publish In-Flight Check:** Immediately before `pub.publish()` is called, `settings.social_broadcast_mode` is re-checked. If disabled, publication is aborted, status is set to `disabled`, and the external provider is never contacted.
4. **Periodic Recovery Sweep Guard:** In `recover_stuck_broadcasts()`, if `social_broadcast_mode == "disabled"`, the function returns `[]` immediately and re-enqueues zero tasks.
5. **Disabled Provider Implementation:** `DisabledXPublisher` unconditionally returns `ok=False, retryable=False, outcome_unknown=False`.

### Inherent Physical Boundaries of Interruptibility
> [!IMPORTANT]
> Once an outbound HTTP request has been written to the TCP socket and acknowledged by Twitter's upstream gateway, toggling `TK_SOCIAL_BROADCAST_MODE=disabled` cannot recall the tweet or prevent Twitter from committing it. The kill-switch prevents all queued, claimed, retry, recovery, and pending requests from executing.

---

## 5. Audit D: Database & Task Reliability

- **Atomic Status Claims:** Claiming a broadcast row uses an atomic single-statement SQL update:
  `UPDATE social_broadcasts SET status='processing', attempts=attempts+1, updated_at=NOW() WHERE id=:id AND status IN ('queued', 'retry_wait')`.
  If multiple workers dequeue duplicate Celery messages, exactly one worker receives `rowcount == 1`. Subsequent workers receive `rowcount == 0` and safely exit.
- **Idempotency Guarantee:**
  - Client-supplied `idempotency_key` is backed by partial unique index `uq_social_broadcasts_report_idempotency` (`report_id, idempotency_key WHERE idempotency_key IS NOT NULL`).
  - Concurrent requests with identical idempotency keys roll back on `IntegrityError` and return the existing broadcast.
- **Celery & Redis Durability:**
  - `DurableTask` sets `acks_late=True` and `reject_on_worker_lost=True`.
  - Redis DLQ list `tk:dlq` captures failed task metadata (capped at 1000 items) without storing sensitive citizen PII or credentials.
  - Redis persistence must have Append-Only File (`appendonly yes`) enabled in production to survive container restarts.

---

## 6. Audit E: Authorization, Privacy & Rate Limiting

- **BOLA / IDOR Verification:**
  - `POST /api/v1/reports/{report_id}/social-broadcast`: Enforces authenticated user; restricts access to report creator (`report.reporter_id == user.id`) or authorized civic staff (`admin`, `super_admin`, `moderator`, `authority`, `platform_admin`).
  - `GET /api/v1/reports/{report_id}/social-broadcast`: Enforces authenticated user; blocks unrelated citizens with HTTP 403 `broadcast_unauthorized`.
- **Privacy Gating:**
  - Private reports (`visibility != "public"`) reject amplification with HTTP 403 `private_report_amplification_forbidden`.
  - Draft reports (`status == "draft"`) reject amplification with HTTP 400 `draft_cannot_be_amplified`.
  - Low/medium severity hazards reject bot escalation with HTTP 422 `ineligible_severity_for_broadcast`.
  - PII masking: Social post text includes only hazard category, municipal authority handles, approximate landmark hint, and public ticket URL. Citizen names, phone numbers, and private addresses are strictly excluded.
- **Rate Limiting:**
  - Broadcast submission: 5 requests / min per user.
  - Status polling: 60 requests / min per user.

---

## 7. Audit F: Test Commands & Actual Verified Results

All checks were executed in the repository without mocks for internal services:

| Command | Working Directory | Exit Code | Result Summary | Evidence Status |
|---|---|---|---|---|
| `uv run pytest tests/test_social_amplify.py -v` | `services/api` | **0** | **33 passed** in 4.11s. Covers Errata 2550 vector, URI normalization, timeout differentiation, outcome_unknown quarantine, duplicate reconciliation rejection, pre-flight re-validation, kill-switch, concurrency, BOLA, and authority governance. | Verified by automated tests |
| `uv run pytest tests/test_queue_reliability.py -v` | `services/api` | **0** | **8 passed** in 0.71s. Covers stuck media recovery, celery durability config, DLQ record shape, dlq key constant, stranded task recovery from PostgreSQL without duplicate records, and max attempts exhaustion. | Verified by automated tests |
| `uv run pytest tests/test_openapi_snapshot.py -v` | `services/api` | **0** | **2 passed** in 0.89s. Verifies OpenAPI contract conformity. | Verified by automated tests |
| `uv run pytest -m "not integration"` | `services/api` | **0** | **641 passed, 1 skipped, 11 deselected** in 140.03s. Complete non-integration backend test suite. | Verified by automated tests |
| `npm test` | `apps/web` | **0** | **72 passed across 19 files** in 1.87s. Complete frontend component and hook test suite. | Verified by automated tests |
| `make lint format-check typecheck web-lint` | Workspace root | **0** | **100% clean**. Ruff: passed, Ruff Format: 281 backend files formatted, Mypy: passed (217 files), ESLint: passed, TypeScript: passed. | Verified by automated tests |

---

## 8. Audit G: Deployment & Infrastructure Topology

The deployment architecture across staging and production was audited against real configuration files (`docker-compose.yml`, `infra/terraform/main.tf`, `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`):

### 1. Celery Worker & Beat Process Isolation
- **Queue Flag:** Celery worker process is explicitly pinned to queue `-Q tk_jobs` in application defaults, `docker-compose.yml`, and `infra/terraform/main.tf`.
- **Beat Scheduler:** Runs periodic recovery sweep `tk_worker.recover_stuck_jobs` every 300 seconds.
- **Beat Concurrency & Worker Scaling:**
  - In `infra/terraform/main.tf`, the worker service runs with `desired_count = 1` and container command:
    `["celery", "-A", "tk_api.worker:celery_app", "worker", "-Q", "tk_jobs", "--beat", "--pool=solo", "-l", "info"]`.
  - **Safety at Current Count:** Safe at `desired_count = 1` because exactly one Beat scheduler exists.
  - **Multi-Replica Scaling Constraint:** If worker replicas are increased beyond 1, Beat **MUST** be decoupled into a dedicated single-replica ECS task definition and service (`tk-beat`, `desired_count = 1`), and the worker task definition command must drop `--beat` to prevent duplicate periodic interval triggers.

### 2. Redis Persistence & Broker Durability Architecture
- **Local / Staging Docker Compose:** `docker-compose.yml` configured with `command: ["redis-server", "--appendonly", "yes"]` and dedicated named volume `redisdata:/data`.
- **AWS ElastiCache Redis 7 Reality:** AWS ElastiCache Redis 7 (`default.redis7`) does **not** support AOF persistence. In `infra/terraform/main.tf`, Redis is provisioned as a single-node `aws_elasticache_cluster` (`cache.t4g.micro`, 1 node) with daily RDB snapshots (`snapshot_retention_limit = 1`). It lacks Multi-AZ and automatic failover. Redis is strictly a transient job broker.
- **PostgreSQL-Anchored Durability Guarantee:** Business durability does not rely on Redis. All broadcast requests are durably committed to PostgreSQL `social_broadcasts` before Celery dispatch. If the ElastiCache node restarts and in-memory queue tasks are lost, the periodic Celery Beat recovery sweep (`recover_stuck_jobs` every 300s) inspects PostgreSQL directly and re-dispatches stranded `queued` and `retry_wait` tasks without creating duplicate broadcasts.

### 3. Emergency Kill-Switch Propagation Mechanics in ECS
- **Configuration Source:** In `infra/terraform/main.tf`, `TK_SOCIAL_BROADCAST_MODE` is defined as a container environment variable inside the ECS Task Definition (`containerDefinitions[0].environment`), **not** in Secrets Manager.
- **Propagation Reality:** Calling `aws ecs update-service --service tk-api --force-new-deployment` merely restarts tasks using the *currently active task definition revision*. It does **not** alter environment variables.
- **Operator Requirement:** To set `TK_SOCIAL_BROADCAST_MODE=disabled` in ECS, an operator must register a new task definition revision containing the updated environment array and update the service to that revision.

### 4. Database Migration Order & Rollback Consequences
- **Deployment Pipeline Order:** In `.github/workflows/deploy.yml`, `migrations` (`alembic upgrade head`) runs as a mandatory dependency before `deploy` (`needs: migrations`), guaranteeing backward-compatible database schema availability before new API and worker containers receive traffic.
- **Production RDS Status:** Migration `0042_social_broadcasts.py` is present in the working tree and tested in CI, but has **not** yet been applied to production RDS.
- **Rollback Consequences:** Running `alembic downgrade 0041` drops `social_broadcasts` and all its partial indexes, permanently destroying civic amplification history. Operational incident response must **never** downgrade migration 0042; instead, operators must set `TK_SOCIAL_BROADCAST_MODE=disabled`.

---

## 9. Evidence-Based Production Launch Prerequisites Checklist

The following matrix distinguishes verified repository code implementations from pending external administrative and infrastructure actions:

| # | Prerequisite Item | Category | Responsible Role | Status | Action Required / Verification Evidence |
|---|---|---|---|---|---|
| **1** | **X Developer Account Approval & Write Access** | External Admin | Production Release Manager | `BLOCKED_EXTERNAL` | Submit project justification in X Developer Portal for Basic/Elevated v2 write access for `@TheekKaro`. Required for live publishing. |
| **2** | **OAuth 1.0a User-Context Credentials Provisioning** | External Admin / Inf | DevSecOps Lead | `PENDING_EXTERNAL` | Generate Consumer Key/Secret and authenticated User Access Token/Secret with `write` scope. Store in AWS Secrets Manager (`prod/theekkaro/social-credentials`). |
| **3** | **Production Database Migration (Alembic 0042)** | DB Infrastructure | Database Reliability Eng | `NOT_APPLIED_PROD` | Migration `0042_social_broadcasts.py` tested for idempotency in CI. Uncommitted on `develop`; not applied in production RDS. Must be applied via deploy pipeline. |
| **4** | **Redis Durability & Broker Architecture** | Cloud Infrastructure | Cloud Infrastructure Eng | `VERIFIED_CODE_READY` | Local `docker-compose.yml` configured with AOF & volume. AWS ElastiCache operates as transient broker; durability anchored in PostgreSQL + Beat recovery sweep. |
| **5** | **Celery Worker & Beat Deployment Topology** | Cloud Infrastructure | Cloud Infrastructure Eng | `VERIFIED_CODE_READY` | Pinned to `-Q tk_jobs`. Safe at replica count 1; multi-replica requires separate `tk-beat` ECS service. Validated in Terraform. |
| **6** | **Municipal Authority Verification Governance** | Operations / Civic | Civic Operations Lead | `VERIFIED_CODE_READY` | Sourced verification metadata fields (`official_verification_source`, `verified_by`, `last_verified_at`, `next_review_due`) and unverified badge indicators implemented and tested. Initial 8 city directories configured. |
| **7** | **Prometheus Alert Rules & Alertmanager Delivery** | DevSecOps / SRE | DevSecOps / On-Call SRE | `VERIFIED_LOCAL_ONLY` | Rules defined in `infra/prometheus/rules.yml`. Production Alertmanager dispatch to Slack/PagerDuty is not yet verified in production cloud environment. |
| **8** | **Emergency Kill-Switch Runbook** | DevSecOps / SRE | Production Release Manager | `VERIFIED_CODE_READY` | Verified 7-step task definition revision sequence documented in `docs/runbooks/social-broadcast-worker.md`. |

---

## 10. Production Readiness Decision & Operational Posture

### Final Decisions:
1. **Simulated Mode Deployment:** **`GO_FOR_SIMULATED_DEPLOYMENT`** (or `READY_WITH_CONDITIONS`)
   - The codebase, database migration `0042`, queue recovery architecture, BOLA/IDOR security controls, and citizen UI are thoroughly verified by automated tests and ready for staging drill and simulated-mode production rollout.
   - Default operating mode is strictly `TK_SOCIAL_BROADCAST_MODE=simulated`.
2. **Autonomous Live X Publishing:** **`NO-GO`**
   - Strictly prohibited until X Developer write permissions are granted, OAuth 1.0a credentials are provisioned in AWS Secrets Manager, and production alert delivery is verified.

### Safe Simulated-Mode Release Checklist:
1. Merge migration `0042_social_broadcasts.py` and social broadcast code to release branch.
2. Confirm `.github/workflows/deploy.yml` applies Alembic migration `0042` before ECS deployment.
3. Confirm ECS task definitions define `TK_SOCIAL_BROADCAST_MODE = "simulated"`.
4. Deploy to staging environment and execute 10-step Staging Simulated-Mode Drill.
5. Verify zero network egress to `api.x.com` via staging VPC Flow Logs and Route 53 Resolver query logs.
6. Execute non-destructive Alertmanager drill to confirm notification receipt.
7. Deploy to production in simulated mode; verify Prometheus metrics and audit logs.
