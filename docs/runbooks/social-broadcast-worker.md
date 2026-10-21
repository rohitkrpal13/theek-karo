# RUNBOOK: Civic Social Broadcast Worker Pipeline

## 1. System Overview

The TheekKaro Civic Social Broadcast Pipeline autonomously amplifies high- and critical-severity civic hazards to social platforms (starting with official verified posts on 𝕏 / Twitter) tagging responsible municipal authorities and ward commissioners.

```
+-----------------------------------------------------------------------------------------+
|                                  THEEKKARO API                                          |
|                                                                                         |
| 1. POST /reports/{id}/social-broadcast                                                  |
|    - Gate checks: public visibility, non-draft, reporter/staff auth, severity in (high, crit)|
|    - Create durable SocialBroadcast record (status="queued", idempotency_key deduplication) |
|    - Audit event: report.social_broadcast_requested                                        |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                    REDIS BROKER                                         |
| Task: tk_worker.social_broadcast (Queue: tk_jobs)                                       |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                CELERY WORKER                                            |
|                                                                                         |
| 2. DurableTask Execution:                                                               |
|    - Atomically claim record: UPDATE ... WHERE status IN ('queued','retry_wait')        |
|      (guarantees no concurrent workers can execute the same broadcast simultaneously)   |
|    - Emergency kill-switch pre-claim check                                              |
|    - Pre-flight re-validation: fetch live Report (aborts if deleted, private, or draft) |
|    - Pre-publish kill-switch check immediately before adapter call                      |
|    - Call X Publisher Adapter (RFC 5849 OAuth 1.0a User Context HMAC-SHA1 signing)      |
|      OUTSIDE active database transaction                                                |
|    - Outcome transition:                                                                |
|      * Mode=simulated -> status="simulated", mock ID generated                          |
|      * Mode=live, Success (HTTP 201) -> status="published", external ID & URL stored   |
|      * Connect Timeout / Network Err (Pre-Connect) -> status="retry_wait", retryable    |
|      * Ambiguous In-Flight Timeout (Post-Connect) -> status="outcome_unknown", NO RETRY |
|      * Rate Limit (HTTP 429) / Upstream 5xx -> status="retry_wait", exponential backoff |
|      * Permanent Error / Exhausted -> status="failed", dead-lettered to tk:dlq          |
|    - Audit event: report.social_broadcast_{status}                                      |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Configuration & Secrets Reference

All worker and API processes read from environment variables prefixed with `TK_`.

| Variable Name | Default | Required in Prod | Description |
|---|---|---|---|
| `TK_SOCIAL_BROADCAST_MODE` | `simulated` | Yes (`live` when enabled) | Operational mode: `disabled`, `simulated`, or `live`. |
| `TK_SOCIAL_BROADCAST_MAX_ATTEMPTS` | `3` | No | Maximum retry attempts for transient provider failures. |
| `TK_SOCIAL_BROADCAST_RETRY_DELAY_SECONDS` | `30` | No | Initial exponential backoff delay in seconds. |
| `TK_CELERY_ENABLED` | `false` (dev/test) | Yes (`true` in prod) | Whether to enqueue to Celery broker or run in-process. |
| `TK_CELERY_BROKER_URL` | `redis://127.0.0.1:6379/0` | Yes | Redis broker connection URI. |
| `TK_TWITTER_API_KEY` | `""` | Yes (for live mode) | X API Consumer / App Key (OAuth 1.0a). |
| `TK_TWITTER_API_SECRET` | `""` | Yes (for live mode) | X API Consumer / App Secret. |
| `TK_TWITTER_ACCESS_TOKEN` | `""` | Yes (for live mode) | X Account Access Token (with User Context `write` permissions). |
| `TK_TWITTER_ACCESS_TOKEN_SECRET` | `""` | Yes (for live mode) | X Account Access Token Secret. |
| `TK_TWITTER_BEARER_TOKEN` | `""` | Optional | App-only token. Note: Cannot be used for `/2/tweets` (User Context required). |
| `TK_TWITTER_API_BASE_URL` | `https://api.x.com` | No | Base URL for Twitter API v2. |
| `TK_TWITTER_REQUEST_TIMEOUT_SECONDS` | `10.0` | No | HTTP request timeout for outbound X API requests. |

> [!CAUTION]
> Never commit OAuth secrets, tokens, or private keys to source control. In production, load credentials via AWS Secrets Manager injected directly into the worker container environment.

### Safe AWS Secrets Manager Verification Protocol (Zero-Exposure)

Do not use `aws secretsmanager get-secret-value` in verification scripts, shell sessions, or audit runbooks, as it prints unmasked `SecretString` data into local shell history, terminal output, and log files. Follow this safe metadata verification sequence:

1. **Verify Secret Existence & Metadata (Without retrieving secret values):**
   ```bash
   aws secretsmanager describe-secret \
     --secret-id "tk-prod-runtime" \
     --query '{Name:Name,ARN:ARN,LastChangedDate:LastChangedDate,KmsKeyId:KmsKeyId}' \
     --output table
   ```
   *Required Evidence:* The secret exists, is in active status, and is encrypted with the project KMS key.

2. **Verify ECS Task Execution Role IAM Policy:**
   ```bash
   aws iam get-role-policy \
     --role-name tk-prod-execution \
     --policy-name read-secrets \
     --query 'PolicyDocument' \
     --output json
   ```
   *Required Evidence:* `Statement[].Resource` includes the exact ARN of `aws_secretsmanager_secret.runtime` (and any dedicated social credentials secret ARN) with `secretsmanager:GetSecretValue` permission.

3. **Verify ECS Task Definition Secrets Mapping:**
   ```bash
   aws ecs describe-task-definition \
     --task-definition tk-worker-task \
     --query 'taskDefinition.containerDefinitions[0].secrets' \
     --output json
   ```
   *Required Evidence:* JSON array maps required environment variables to their respective secret ARNs and JSON keys (e.g., `arn:aws:secretsmanager:...:secret_string:<key>`).

4. **Verify Application Fails Closed on Missing Credentials:**
   * Automated tests (`test_live_publisher_requires_user_context_credentials` and `test_missing_credentials_fails_closed`) prove that when keys are absent or empty strings, `LiveXPublisher.publish()` immediately returns `ok=False, retryable=False, last_error="live_credentials_not_configured"`. Zero outbound HTTP requests are dispatched to `api.x.com`.

5. **Verify Zero Secret Logging:**
   * CloudWatch logs filter pattern confirms no token strings:
     ```bash
     aws logs filter-log-events \
       --log-group-name "/ecs/theek-karo-prod" \
       --filter-pattern '"oauth_token"' \
       --max-items 5
     ```
   * *Required Evidence:* 0 matches. Secrets and tokens are never included in structured JSON log entries.

---

## 3. Worker Operations & Background Tasks

### Local Execution (Development & Testing)

To run the Celery worker locally against a local Redis instance:

```bash
# In services/api directory:
uv run celery -A tk_api.worker.celery_app worker -l info -Q tk_jobs -c 2
```

To test the task synchronously in Python:

```python
from tk_api.worker.tasks import social_broadcast

# Run worker task for a given broadcast UUID
result = social_broadcast("123e4567-e89b-12d3-a456-426614174000")
print(result)
```

### Automatic Stuck Job Recovery Beat Loop

The Celery beat scheduler runs `tk_worker.recover_stuck_jobs` every 5 minutes (300 s). This maintenance loop:
1. Re-drives media files stranded in `pending_scan`.
2. Inspects `social_broadcasts` for records stranded in `processing` or `queued` past 10 minutes (due to OOM, host crash, or lost broker task), and `retry_wait` past 60 seconds.
3. If `social_broadcast_mode == "disabled"`: Skips execution completely (NO-OP).
4. For stranded `processing` records in `live` mode: Transitions the record to `outcome_unknown` rather than blind re-queueing to eliminate duplicate publication if the crash occurred post-transmission.
5. If attempts < max_attempts: Re-enqueues the record to `queued` and re-dispatches to Celery.
6. If attempts >= max_attempts: Marks the record `failed` with descriptive audit logging.
7. **Exclusion:** Records in `outcome_unknown` are strictly EXCLUDED from automated recovery and remain safely quarantined until operator reconciliation.

### Docker Compose / Production Deployment

The Celery worker runs from the exact same container image as the FastAPI backend (`Dockerfile.api`), with an overridden CMD:

```yaml
  worker:
    build:
      context: ./services/api
    command: ["uv", "run", "celery", "-A", "tk_api.worker.celery_app", "worker", "-l", "info", "-Q", "tk_jobs", "-c", "4"]
    environment:
      - TK_DATABASE_URL=postgresql+asyncpg://tk:tk@postgres:5432/theek_karo
      - TK_CELERY_ENABLED=true
      - TK_CELERY_BROKER_URL=redis://redis:6379/0
      - TK_SOCIAL_BROADCAST_MODE=simulated  # Change to live only after human approval
    depends_on:
      - postgres
      - redis
```

### Celery Beat Process Isolation & Worker Replica Sizing

In `infra/terraform/main.tf`:
- The production worker service runs with `desired_count = 1` and container command:
  `["celery", "-A", "tk_api.worker:celery_app", "worker", "-Q", "tk_jobs", "--beat", "--pool=solo", "-l", "info"]`
- **Safety at Current Replica Count (`desired_count = 1`):** Running `--beat` embedded in the single worker container is safe because exactly one Beat scheduler exists cluster-wide.
- **Critical Scaling Constraint (`desired_count > 1`):** If worker replicas are scaled up to handle higher task volume, running `--beat` on all worker containers will start multiple Beat scheduler instances. This would cause duplicate scheduled ticks for periodic tasks (`recover_stuck_jobs` and media scans).
- **Required Architecture for Multi-Replica Scaling:**
  1. Decouple Beat into a dedicated single-replica ECS task definition (`tk-beat-task`) and service (`tk-beat`, `desired_count = 1`).
  2. Strip the `--beat` flag from the `tk-worker-task` definition command, leaving it dedicated to processing task queues: `["celery", "-A", "tk_api.worker:celery_app", "worker", "-Q", "tk_jobs", "-c", "4"]`.

---

## 4. Failure Modes & Incident Triage

### Triage Checklist

1. **Check Queue Depth & Worker Health**:
   ```bash
   # Inspect pending jobs in Redis queue
   docker compose exec redis redis-cli LLEN tk_jobs

   # Inspect dead-letter list
   docker compose exec redis redis-cli LLEN tk:dlq
   docker compose exec redis redis-cli LRANGE tk:dlq 0 10
   ```

2. **Check Broadcast Table State**:
   ```bash
   docker compose exec postgres psql -U tk -d theek_karo -c "
     SELECT id, report_id, status, attempts, last_error, created_at, updated_at
     FROM social_broadcasts
     ORDER BY created_at DESC
     LIMIT 20;
   "
   ```

3. **Check Worker Logs**:
   ```bash
   docker compose logs worker --since 15m | grep social_broadcast
   ```

---

## 5. Specific Operational Scenarios

### Scenario A: X API Rate Limit Hit (HTTP 429)
- **Symptom**: Worker logs `x api rate limit exceeded`, broadcast state transitions to `retry_wait`.
- **Behavior**: Task retries with exponential backoff up to `max_attempts` (default 3).
- **Remediation**: If civic hazard frequency spikes, Twitter API v2 Basic tier caps monthly posts. Verify current usage against Twitter Developer Portal.

### Scenario B: Ambiguous Network Timeout (`outcome_unknown`)
- **Symptom**: Worker logs `x api request timed out post-transmission (ambiguous outcome - do not retry)`. The broadcast row transitions to `outcome_unknown`.
- **Safety Guarantee**: The broadcast is NOT retried automatically by Celery or beat sweeps. The report is locked against duplicate broadcasts via the database partial index `uq_social_broadcasts_active_report`.
- **Operator Reconciliation Procedure**:
  1. Inspect the official X account profile (@TheekKaro) or query X timeline via API.
  2. Search for the hazard ticket number (e.g. `#BLR-2026-0042`) in recent tweets.
  3. **Case 1: Post was successfully published on X:**
     Obtain the tweet ID (e.g. `1848293049201948201`) and run the reconciliation script:
     ```python
     import asyncio, uuid
     from tk_api.core.config import get_settings
     from tk_api.core.db import create_session_factory, get_engine
     from tk_api.reports.broadcast_service import reconcile_broadcast_outcome

     async def reconcile_published(broadcast_id_str, tweet_id):
         settings = get_settings()
         engine = get_engine(settings)
         factory = create_session_factory(engine)
         async with factory() as session:
             b = await reconcile_broadcast_outcome(
                 session,
                 broadcast_id=uuid.UUID(broadcast_id_str),
                 outcome="published",
                 external_post_id=tweet_id,
                 resolution_note="Manually confirmed tweet exists on timeline",
             )
             print(f"Reconciled {b.id} as published: {b.published_url}")

     asyncio.run(reconcile_published("<BROADCAST_UUID>", "<TWEET_ID>"))
     ```
  4. **Case 2: Post was NOT published on X:**
     Reconcile as failed to clear the active report lock:
     ```python
     async def reconcile_failed(broadcast_id_str):
         settings = get_settings()
         engine = get_engine(settings)
         factory = create_session_factory(engine)
         async with factory() as session:
             b = await reconcile_broadcast_outcome(
                 session,
                 broadcast_id=uuid.UUID(broadcast_id_str),
                 outcome="failed",
                 resolution_note="Confirmed no post was created on X after timeout",
             )
             print(f"Reconciled {b.id} as failed.")

     asyncio.run(reconcile_failed("<BROADCAST_UUID>"))
     ```

### Scenario C: Pre-Flight Re-Validation Rejection
- **Symptom**: Broadcast marked `failed` with error `Report visibility was changed from public; broadcast aborted` or `Report is in draft status`.
- **Behavior**: Safe intentional abort. The civic bot strictly avoids publicizing unverified, private, or draft data.

### Scenario D: Dead-Letter Queue (DLQ) Recovery Procedure
- **Symptom**: Items appear in `tk:dlq` in Redis.
- **Payload Schema**: Dead-letter entries contain `{"task_id": "...", "task_name": "tk_worker.social_broadcast", "args": ["<broadcast_uuid>"], "kwargs": {}, "error": "..."}`.
- **Replay Command**: After resolving upstream credentials or network issues, re-dispatch the job:
  ```python
  from tk_api.worker import celery_app
  celery_app.send_task("tk_worker.social_broadcast", args=["<broadcast_uuid>"])
  ```

---

## 6. Emergency Rollback & Kill-Switch

### Architecture of Configuration Propagation

In TheekKaro, `TK_SOCIAL_BROADCAST_MODE` is read from container environment variables by `tk_api.core.config.Settings` (defaulting to `"simulated"`). In AWS ECS Fargate (`infra/terraform/main.tf`), container environment variables are baked directly into the **ECS Task Definition** (`containerDefinitions[0].environment`). They are **NOT** stored in Secrets Manager.

> [!WARNING]
> Running `aws ecs update-service --service tk-api --force-new-deployment` merely restarts tasks using the *currently active task definition revision*. It will **NOT** change `TK_SOCIAL_BROADCAST_MODE`. To change the operating mode in ECS, an operator must register a new task definition revision containing the updated environment variable and update the service to that new revision.

### Verified 7-Step Emergency Disablement Sequence for AWS ECS

#### Step 1: Export Active Task Definitions
Download the active task definition JSON for both `tk-api` and `tk-worker`:
```bash
aws ecs describe-task-definition \
  --task-definition tk-api-task \
  --query 'taskDefinition' \
  --output json > /tmp/tk-api-task.json

aws ecs describe-task-definition \
  --task-definition tk-worker-task \
  --query 'taskDefinition' \
  --output json > /tmp/tk-worker-task.json
```
*Required Evidence:* JSON files exist and contain valid `containerDefinitions`.

#### Step 2: Update Publishing Mode to `disabled` and Strip Read-Only Metadata
Use `jq` to strip system-assigned metadata fields (`taskDefinitionArn`, `revision`, `status`, `requiresAttributes`, `compatibilities`, `registeredAt`, `registeredBy`) and set `TK_SOCIAL_BROADCAST_MODE="disabled"` in the container environment array:
```bash
jq 'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
   | .containerDefinitions[0].environment = [
       (.containerDefinitions[0].environment[] | select(.name != "TK_SOCIAL_BROADCAST_MODE")),
       {"name": "TK_SOCIAL_BROADCAST_MODE", "value": "disabled"}
     ]' /tmp/tk-api-task.json > /tmp/tk-api-task-disabled.json

jq 'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
   | .containerDefinitions[0].environment = [
       (.containerDefinitions[0].environment[] | select(.name != "TK_SOCIAL_BROADCAST_MODE")),
       {"name": "TK_SOCIAL_BROADCAST_MODE", "value": "disabled"}
     ]' /tmp/tk-worker-task.json > /tmp/tk-worker-task-disabled.json
```
*Required Evidence:* Inspect files with `jq '.containerDefinitions[0].environment[] | select(.name=="TK_SOCIAL_BROADCAST_MODE")'` to verify `value == "disabled"`.

#### Step 3: Register New Task Definition Revisions
```bash
NEW_API_TASK_ARN=$(aws ecs register-task-definition \
  --cli-input-json file:///tmp/tk-api-task-disabled.json \
  --query 'taskDefinition.taskDefinitionArn' --output text)

NEW_WORKER_TASK_ARN=$(aws ecs register-task-definition \
  --cli-input-json file:///tmp/tk-worker-task-disabled.json \
  --query 'taskDefinition.taskDefinitionArn' --output text)

echo "Registered API Task: $NEW_API_TASK_ARN"
echo "Registered Worker Task: $NEW_WORKER_TASK_ARN"
```
*Required Evidence:* Non-empty ARN strings ending in the incremented revision number (e.g., `:2`).

#### Step 4: Deploy the Updated Configuration to Services
```bash
CLUSTER="tk-prod"

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "tk-api" \
  --task-definition "$NEW_API_TASK_ARN" \
  --force-new-deployment

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "tk-worker" \
  --task-definition "$NEW_WORKER_TASK_ARN" \
  --force-new-deployment
```
*Required Evidence:* AWS ECS returns service description with `desiredCount` matching running count and status `ACTIVE`.

#### Step 5: Wait for Service Stability & Verify Running Tasks
```bash
aws ecs wait services-stable --cluster "$CLUSTER" --services tk-api tk-worker
```
*Required Evidence:* Wait command completes with exit code 0. `aws ecs describe-services --cluster "$CLUSTER" --services tk-api tk-worker --query 'services[*].deployments'` shows only 1 deployment per service with status `PRIMARY` pointing to the new task definition ARN.

#### Step 6: Confirm API Rejection, Worker Halt, and Recovery Inactivity
1. **API Behavior:** Send a test broadcast request:
   ```bash
   curl -s -X POST "https://api.theekkaro.in/api/v1/reports/<REPORT_ID>/social-broadcast" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"network": "x", "tone": "urgent"}' | jq .
   ```
   *Required Evidence:* HTTP 200/201 with `status: "disabled"` and `last_error: "Civic bot social broadcasting is currently disabled by administrator configuration."`. No task is enqueued to Redis.
2. **Worker Behavior:** Check CloudWatch worker logs:
   ```bash
   aws logs filter-log-events \
     --log-group-name "/ecs/theek-karo-prod" \
     --filter-pattern '"report.social_broadcast_disabled"' \
     --start-time $(date -v-15M +%s000)
   ```
   *Required Evidence:* Log event shows `status="disabled"` without invoking provider.
3. **Recovery Inactivity:** The periodic recovery sweep `tk_worker.recover_stuck_jobs` executes every 300s, checks `settings.social_broadcast_mode == "disabled"`, and immediately returns `[]` without re-dispatching any stranded tasks.

#### Step 7: Persistence Guarantee
Because the configuration is registered in the active ECS task definition revision (`$NEW_API_TASK_ARN` and `$NEW_WORKER_TASK_ARN`), any task restarts, crash loops, or auto-scaling events will strictly spawn containers with `TK_SOCIAL_BROADCAST_MODE=disabled`. The kill-switch cannot be accidentally reverted by a container restart.

---

### Database Rollback Consequences (Alembic Migration 0042)

If an operator considers running `alembic downgrade 0041`:
- **What it does:** Drops the table `social_broadcasts` and all associated partial indexes (`uq_social_broadcasts_active_report`, `uq_social_broadcasts_report_idempotency`).
- **Consequences:**
  1. **All historical civic amplification records and audit trail are irreversibly erased.**
  2. Citizens and officials lose visibility into which hazards were previously broadcast to social networks.
  3. Core civic reports in the `reports` table and evidence in `report_evidence` remain intact (no cascade damage to parent entities).
  4. Any running API or worker container that executes code expecting `social_broadcasts` will immediately fail with `relation "social_broadcasts" does not exist` (HTTP 500 errors).
- **Mandatory Policy:** **NEVER downgrade migration 0042 as an emergency response to an operational incident.** To halt social broadcasting immediately and safely, use the verified kill-switch (`TK_SOCIAL_BROADCAST_MODE=disabled`). Migration downgrade is reserved solely for complete feature deprecation after database backup.

---

## 7. Municipal Authority Verification & Governance Lifecycle

To prevent misattribution, spoofing, or unintended tagging of civilian or inactive accounts, all civic municipal handles follow an evidence-backed verification lifecycle:

### Governance Tracking Metadata

For every municipal directory entry, the platform tracks:
1. **City & Department**: Administrative jurisdiction (e.g., Bengaluru - BBMP Health & Solid Waste Management).
2. **Platform & Handle**: Platform (`x`, `instagram`) and canonical handle string (e.g., `@BBMPCOMM`).
3. **Official Verification Source**: Authoritative source URL (must be an official `.gov.in` portal, municipal press release, or state gazette). Third-party directories, search results, or personal attestations are strictly disqualified.
4. **Verification Status**:
   - `verified_official`: Authority identity verified against official government documentation by authorized TheekKaro security personnel.
   - `unverified`: Sourced from public heuristics or unconfirmed submissions; visibly flagged in UI with amber badge.
5. **Reviewer & Review Timestamp**: Identity of TheekKaro operator performing verification and ISO-8601 timestamp.
6. **Last Verification Date & Expiry Policy**: Verifications expire after 90 days (`next_review_due`). Expired entries automatically revert to `unverified` status until renewed.

### Safe Fallback Policy

If no verified municipal handle is available for a report's jurisdiction:
- The system defaults tagging to the national urban affairs handle (`@MoHUA_India`, marked `unverified`) and the TheekKaro platform verification ledger (`@TheekKaro`, marked `verified_official`).
- Autonomous bot publishing never tags unverified civilian handles.

---

## 8. Measurable Operational Signals & Prometheus Alerting

The following operational metrics and alert thresholds monitor pipeline reliability:

| Signal / Metric | Prometheus / Log Indicator | Warning Threshold | Critical / Pager Threshold | Action |
|---|---|---|---|---|
| **Queue Depth** | `redis_queue_length{queue="tk_jobs"}` | `> 50` for 5m | `> 200` for 2m | Scale worker replicas; check Redis CPU/memory |
| **Oldest Pending Job** | `theekkaro_broadcast_oldest_queued_age_seconds` | `> 300s` | `> 900s` | Check worker concurrency; investigate worker stalls |
| **Processing Duration** | `theekkaro_social_broadcast_duration_seconds{quantile="0.95"}` | `> 5.0s` | `> 10.0s` | Upstream X API latency or DNS resolution delay |
| **Publication Failure Rate** | Rate of `theekkaro_social_broadcast_total{status="failed"}` | `> 5%` over 10m | `> 15%` over 5m | Check error logs for auth failures or format errors |
| **Rate Limit Hits** | `theekkaro_social_broadcast_rate_limits_total` | `> 0` / hour | `> 10` / hour | X API tier limit approached; throttle publication |
| **Ambiguous Timeouts** | `theekkaro_social_broadcast_outcome_unknown_total` | `> 0` (Immediate) | `> 3` in 1h | Trigger Incident Playbook: Ambiguous Timeout Reconcile |
| **Stuck-Task Recovery** | `theekkaro_stuck_broadcasts_recovered_total` | `> 5` in 1h | `> 20` in 1h | Beat scheduler recovering stalled workers |
| **Dead-Letter Queue** | `redis_queue_length{queue="tk:dlq"}` | `> 0` | `> 10` | Inspect DLQ payload; re-drive after bugfix |
| **Worker / Broker Health** | `celery_workers_online` / `redis_up` | `< 2` workers | `0` workers or Redis down | P1 Alert: Restart Celery/Redis services |
| **Kill-Switch State** | `theekkaro_social_broadcast_mode` | Mode == `disabled` | N/A | Notify oncall that civic bot publishing is inactive |

---

## 9. Incident Response Playbooks

### Incident 1: Duplicate-Post Risk
- **Trigger**: Multiple reports or users report identical tweets for the same civic ticket.
- **Immediate Action**:
  1. Immediately execute emergency kill-switch: `TK_SOCIAL_BROADCAST_MODE=disabled`.
  2. Inspect database for constraint violations:
     ```sql
     SELECT report_id, COUNT(*) FROM social_broadcasts
     WHERE status IN ('queued', 'processing', 'published', 'outcome_unknown')
     GROUP BY report_id HAVING COUNT(*) > 1;
     ```
  3. Validate database migration: Verify partial unique index `uq_social_broadcasts_active_report` exists.
  4. If tweets were published duplicated, record external post IDs and delete surplus tweets via X developer console.

### Incident 2: Upstream Provider Outage (X API 5xx / Cloud Outage)
- **Trigger**: Worker logs show repeated `ConnectTimeout`, `HTTP 502 Bad Gateway`, or `HTTP 503 Service Unavailable`.
- **Behavior**: Celery retries with exponential backoff up to 3 attempts, then parks in `failed`.
- **Operator Steps**:
  1. Check official status: https://api.twitterstat.us
  2. If outage exceeds 30 minutes, switch `TK_SOCIAL_BROADCAST_MODE=simulated` to prevent consumer-facing submission failures while buffering alerts internally.
  3. Once upstream service restores, query failed broadcasts during the outage window:
     ```sql
     SELECT id, report_id, last_error FROM social_broadcasts
     WHERE status = 'failed' AND created_at >= NOW() - INTERVAL '2 hours';
     ```
  4. Re-drive eligible high/critical broadcasts via Celery `send_task`.

### Incident 3: Broker or Queue Failure (Redis Connectivity / Persistence Crash)
- **Trigger**: API returns `503 Service Unavailable` on enqueue, Celery logs connection refused to Redis.
- **Immediate Action**:
  1. Check Redis container/cluster health:
     ```bash
     # Local Docker Compose:
     docker compose ps redis
     docker compose exec redis redis-cli info persistence

     # AWS ElastiCache (via bastion or SSM):
     aws elasticache describe-cache-clusters --cache-cluster-id tk-prod-redis
     ```
  2. **AWS ElastiCache Redis Architecture**: Note that AWS ElastiCache on Redis 7 does NOT support AOF (Append-Only File) persistence. ElastiCache is treated as a transient task broker with daily RDB snapshots (`snapshot_retention_limit = 1`).
  3. **Authoritative PostgreSQL Durability Guarantee**: If an ElastiCache node reboots or fails over and in-memory queue tasks are lost, acknowledged Celery jobs are NOT lost to the business. The authoritative state is durably held in PostgreSQL `social_broadcasts`. The periodic Celery Beat recovery sweep (`recover_stuck_jobs` every 300s) inspects PostgreSQL directly and re-dispatches stranded `queued` and `retry_wait` tasks.
  4. **High-Availability Recommendation**: For production environments requiring sub-minute broker failover, upgrade from single-node `aws_elasticache_cluster` to `aws_elasticache_replication_group` with Multi-AZ and automatic failover enabled.

### Incident 4: Credential Revocation / Invalidation (HTTP 401 / 403)
- **Trigger**: Worker fails with `HTTP 401 Unauthorized` or `HTTP 403 Forbidden` (`client-not-enrolled` / `oauth-token-revoked`).
- **Immediate Action**:
  1. Set `TK_SOCIAL_BROADCAST_MODE=disabled`.
  2. Check X Developer Portal to verify app write permissions and regenerated token status.
  3. Rotate credentials in AWS Secrets Manager:
     - `TK_TWITTER_API_KEY`
     - `TK_TWITTER_API_SECRET`
     - `TK_TWITTER_ACCESS_TOKEN`
     - `TK_TWITTER_ACCESS_TOKEN_SECRET`
  4. Trigger rolling restart of Celery worker tasks to inject updated secrets.
  5. Test single broadcast in staging before re-enabling `live` mode.

### Incident 5: Emergency Disablement Execution
Follow the authoritative 7-step sequence documented in [Section 6: Emergency Rollback & Kill-Switch](#verified-7-step-emergency-disablement-sequence-for-aws-ecs).

---

## 10. Production Launch Prerequisites Checklist

| # | Item | Category | Status | Blocking? | Verification Evidence / Action Required |
|---|---|---|---|---|---|
| 1 | **X Developer Account Approval & Write Access** | External Admin | `BLOCKED_EXTERNAL` | **YES** | Requires human application and approval in X Developer Portal for v2 `/2/tweets` write access. |
| 2 | **OAuth 1.0a User-Context Credentials** | External Admin / Inf | `PENDING_EXTERNAL` | **YES** | Generation of Access Token with write permission from authenticated @TheekKaro account and storage in AWS Secrets Manager. |
| 3 | **Production Database Migration (Alembic 0042)** | DB Infrastructure | `VERIFIED_CODE_READY` | **YES** | Migration script `0042_social_broadcasts.py` tested and verified in CI; must be applied in production deployment pipeline. |
| 4 | **Redis Durability & Broker Architecture** | Cloud Infrastructure | `VERIFIED_CONFIGURED`| **YES** | Local `docker-compose.yml` configured with AOF (`--appendonly yes`) & volume. AWS ElastiCache operates as transient broker; durability guaranteed by PostgreSQL ledger + Celery Beat recovery sweep. |
| 5 | **Celery Worker & Beat ECS Services** | Cloud Infrastructure | `VERIFIED_CONFIGURED`| **YES** | Worker and beat command lines, queue flags (`-Q tk_jobs`), health checks, and restart policies configured and verified in Terraform. |
| 6 | **Municipal Authority Verification Onboarding** | Operations / Civic | `IN_PROGRESS` | **NO (Soft)** | Initial 8 metropolitan directories configured with official fallback. Direct municipality MoU verifications can expand progressively. |
| 7 | **Monitoring, Alerting & Incident Ownership** | DevSecOps / SRE | `VERIFIED_READY` | **NO (Soft)** | Prometheus metrics, log alerts, runbook playbooks, and incident escalation paths documented. |

---

## 11. Staging Simulated-Mode Verification Drill

This drill verifies the end-to-end simulated amplification pipeline in an isolated staging environment without contacting real social networks.

### 10-Step Staging Verification Runbook

1. **Step 1: Create a Public High-Severity Test Report:**
   ```bash
   REPORT_RES=$(curl -s -X POST "https://staging-api.theekkaro.in/api/v1/reports" \
     -H "Authorization: Bearer $STAGING_CITIZEN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "STAGING TEST: Severe Road Cave-In",
       "description": "Drill test hazard for simulated social amplification verification.",
       "category_id": "'"$STAGING_ROADS_CAT_ID"'",
       "severity": "high",
       "visibility": "public",
       "location": {"type": "Point", "coordinates": [77.6245, 12.9352]},
       "location_accuracy_m": 5.0,
       "address_hint": "Koramangala 4th Block, Bengaluru"
     }')
   REPORT_ID=$(echo "$REPORT_RES" | jq -r '.id')
   echo "Created Staging Report: $REPORT_ID"
   ```
   *Pass Criteria:* HTTP 201 Created with valid report UUID, `visibility="public"`, `severity="high"`.

2. **Step 2: Verify Citizen UI Intent & Story Graphic Generation:**
   * Open staging web application: `https://staging.theekkaro.in/en/reports/$REPORT_ID`.
   * Click **Amplify Hazard** modal.
   * Verify X Web Intent URL: `https://x.com/intent/tweet?text=...` encodes official authority handles (`@BBMPCOMM`) and `#TheekKaro`.
   * Verify Story Graphic canvas renders 9:16 layout with hazard title, location, and QR code.

3. **Step 3: Trigger Server-Side Broadcast Request:**
   ```bash
   BROADCAST_RES=$(curl -s -X POST "https://staging-api.theekkaro.in/api/v1/reports/$REPORT_ID/social-broadcast" \
     -H "Authorization: Bearer $STAGING_CITIZEN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"network": "x", "tone": "urgent"}')
   BROADCAST_ID=$(echo "$BROADCAST_RES" | jq -r '.id')
   echo "Created Broadcast ID: $BROADCAST_ID"
   ```
   *Pass Criteria:* HTTP 201 Created with `status="queued"` and non-null `id`.

4. **Step 4: Verify Durable PostgreSQL Record:**
   ```sql
   SELECT id, report_id, network, status, attempts, published_url, external_post_id
   FROM social_broadcasts WHERE id = '<BROADCAST_ID>';
   ```
   *Pass Criteria:* Exactly 1 record in `queued` status, `published_url IS NULL`, `external_post_id IS NULL`.

5. **Step 5: Verify Celery Worker Processing on `tk_jobs`:**
   * Inspect worker logs:
     ```bash
     aws logs filter-log-events \
       --log-group-name "/ecs/theek-karo-staging" \
       --filter-pattern "\"social_broadcast claimed\"" \
       --start-time $(date -v-5M +%s000)
     ```
   *Pass Criteria:* Log event confirms worker claimed `<BROADCAST_ID>` from queue `tk_jobs`.

6. **Step 6: Confirm Transition to `simulated` Status:**
   ```bash
   curl -s "https://staging-api.theekkaro.in/api/v1/reports/$REPORT_ID/social-broadcast" \
     -H "Authorization: Bearer $STAGING_CITIZEN_TOKEN" | jq .
   ```
   *Pass Criteria:* HTTP 200 with `status="simulated"`, non-empty `simulated_at` timestamp.

7. **Step 7: Confirm Zero Real Posts & No Fabricated Publishing URL:**
   * In PostgreSQL:
     ```sql
     SELECT status, external_post_id, published_url FROM social_broadcasts WHERE id = '<BROADCAST_ID>';
     ```
   *Pass Criteria:* `status == 'simulated'`. `published_url` is `NULL` (or explicitly prefixed with internal simulated marker, never pointing to live `x.com/TheekKaro/status/...`).

8. **Step 8: Confirm UI Displays Simulated Status Badge:**
   * In web browser, check modal: badge displays **Simulated (Testing Mode)** in blue/slate. No live tweet link is rendered.

9. **Step 9: Verify Emergency Kill-Switch in Staging:**
   * Update staging task definition to `TK_SOCIAL_BROADCAST_MODE=disabled`.
   * Submit another broadcast request:
     ```bash
     curl -s -X POST "https://staging-api.theekkaro.in/api/v1/reports/$REPORT_ID/social-broadcast" \
       -H "Authorization: Bearer $STAGING_CITIZEN_TOKEN" \
       -H "Content-Type: application/json" \
       -d '{"network": "x", "tone": "urgent"}' | jq .
     ```
   *Pass Criteria:* Immediate response `status: "disabled"`, `last_error: "Civic bot social broadcasting is currently disabled by administrator configuration."`.

10. **Step 10: Verify Audit Records & Metrics:**
    * In database:
      ```sql
      SELECT action, details FROM audit_logs
      WHERE entity_id = '<REPORT_ID>' AND action LIKE 'report.social_broadcast_%'
      ORDER BY created_at ASC;
      ```
    *Pass Criteria:* Audit entries `report.social_broadcast_requested` and `report.social_broadcast_simulated` exist with matching correlation IDs.

### Network-Level Proof of Zero Egress (Network Isolation Verification)

> [!CRITICAL]
> An absence of application error logs is **NOT** sufficient proof of zero network egress. In simulated mode, absolute proof that zero packets reached `api.x.com` must be established at the network layer:

1. **VPC Flow Logs Verification:**
   Query AWS CloudWatch Insights on staging VPC Flow Logs for worker task ENIs:
   ```
   fields @timestamp, srcAddr, dstAddr, dstPort, packets, bytes
   | filter dstPort = 443
   | filter srcAddr like "10.1."
   | stats count() by dstAddr
   ```
   *Pass Criteria:* Destination IP addresses belong exclusively to AWS internal VPC endpoints, S3 regional endpoints, and RDS endpoints. Zero packets routed to public Twitter/X CIDR blocks (`104.244.42.0/21`, `199.16.156.0/22`, etc.).

2. **DNS Query Logging Verification (Route 53 Resolver):**
   ```bash
   aws route53resolver list-firewall-configs
   aws logs filter-log-events \
     --log-group-name "/aws/route53/staging-resolver-queries" \
     --filter-pattern '"api.x.com" "api.twitter.com"' \
     --start-time $(date -v-30M +%s000)
   ```
   *Pass Criteria:* Exactly 0 query log events recorded for `api.x.com` during the drill window.

---

## 12. Non-Destructive Alert-Delivery Drill

This drill proves that Prometheus alert rules are parsed and Alertmanager delivers alerts to operational notification channels (Slack / PagerDuty) without triggering public posts or perturbing production systems.

### Step 1: Syntactic Rule Validation
Run `promtool` on the alert rules file:
```bash
promtool check rules infra/prometheus/rules.yml
```
*Pass Criteria:* Output reports `Checking infra/prometheus/rules.yml: SUCCESS - 2 rules found`.

### Step 2: Non-Destructive Alertmanager Synthetic Alert Injection
Send a synthetic test alert payload directly to the staging Alertmanager API:
```bash
curl -X POST "http://alertmanager:9093/api/v2/alerts" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "labels": {
        "alertname": "TkSocialBroadcastOutcomeUnknown",
        "service": "tk-worker",
        "severity": "page",
        "environment": "staging-drill"
      },
      "annotations": {
        "summary": "DRILL ONLY: Simulated ambiguous timeout test",
        "runbook": "docs/runbooks/social-broadcast-worker.md#scenario-b-ambiguous-network-timeout-outcome_unknown"
      },
      "startsAt": "'"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'",
      "endsAt": "'"$(date -u -v+10M +"%Y-%m-%dT%H:%M:%SZ")"'"
    }
  ]'
```
*Pass Criteria:* HTTP 200 OK from Alertmanager.

### Step 3: Verify Receiver Delivery
* **Slack Channel (`#alerts-civic-bot-staging`):** Verify incoming message appears with title `[PAGE] TkSocialBroadcastOutcomeUnknown` and runbook link.
* **PagerDuty Staging Service:** Verify test incident triggers and pages the designated drill responder.

### Step 4: Resolve Alert
Send an expiration payload with `endsAt` set to current timestamp:
```bash
curl -X POST "http://alertmanager:9093/api/v2/alerts" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "labels": {
        "alertname": "TkSocialBroadcastOutcomeUnknown",
        "service": "tk-worker",
        "severity": "page",
        "environment": "staging-drill"
      },
      "startsAt": "'"$(date -u -v-10M +"%Y-%m-%dT%H:%M:%SZ")"'",
      "endsAt": "'"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'"
    }
  ]'
```
*Pass Criteria:* Slack alert resolves with green indicator; PagerDuty incident automatically resolves. Zero civic records or public posts are created.
