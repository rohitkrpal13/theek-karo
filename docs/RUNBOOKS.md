# INCIDENT RUNBOOKS (Phase 10, hardened Step 16)

## Incident response lifecycle

1. **Detect** — alert rules (`docs/SLOs.md`), `/readyz` probes, error budgets,
   DLQ growth (`tk:dlq`), dead-letter/backlog alerts.
2. **Triage** — classify by the severity ladder below; open a tracker with the
   time, symptom, and affected surface; copy the JSON access-log `request_id`s
   that correlate to the failure window.
3. **Respond** — follow the specific runbook below. Stabilize first (rollback,
   restart, failover) — investigate after the service is back.
4. **Communicate** — internal channel for S2+; for S1 (incl. any suspected
   breach) invoke the DPDP 72-hour notification clock immediately
   (`S1-Breach` below) and keep a timeline.
5. **Postmortem** — within 5 business days for S1/S2: timeline, root cause,
   what prevented detection, corrective actions; attach the incident to the
   release notes. Never punish the reporter — blameless review.

## Severity ladder

| Sev | Definition | Response |
|-----|-----------|----------|
| S1 | Full outage / data breach / legal exposure | On-call + senior engineer; 15-min response; page |
| S2 | Partial outage or degraded service (p95 or errors breached) | 30-min response; page from alert rules |
| S3 | Minor degradation, silent failures only in logs | Next-business-day fix |
| S4 | Cosmetic/UX incidents | Regular-cycle fix |

## S1-ApiDown
1. `docker compose ps`; check api health (S1 if `/healthz` doesn't answer).
2. `docker compose logs api --since 10m` — look for OOM/uvicorn crash traces.
3. Restart: `docker compose up -d --build api`.
4. If boot-looping: check `TK_DATABASE_URL`, migrations (`uv run alembic current` vs `head`).
5. Escalate: notify on-call; declare S2 resolved when `/readyz` + `/api/v1/version` respond.

## S1-DatabaseDown
1. `docker compose logs postgres` — disk full? `df -h` on the pgdata volume.
2. `pg_isready`; restart `docker compose restart postgres`.
3. If corrupted: restore from the last backup snapshot; record the window for the audit.
4. Notifications worker will retry automatically (backoff); API serves degraded `readyz` 503.

## S2-RedisDown
1. `redis-cli -p 6380 ping`.
2. Restart redis; the API falls back to memory rate-limiting/OTP stores automatically (documented).
3. Replaying outbound notification queue is triggered by the next beat after recovery.

## S2-MinioUnavailable
1. `mc alias` checks; `docker compose up -d minio`.
2. Uploads fail fast with clear 409/5xx; nothing is queued against a down object store.

## S2-QueueBacklog (TkWorkerQueueBacklog alert)
1. `docker compose exec postgres psql -U tk -d theek_karo -c "SELECT status, count(*) FROM notification_queue GROUP BY status;"`.
2. If queued > 500: worker stalled? `docker compose logs worker`; restart worker.
3. Provider-side failures mark rows `failed` after 3 attempts (bounded, no infinite loop).

## S2-AIProviderFailure
1. Gateway fallback chain handles provider outages (returns the next URL; last resort stub).
2. Check `ai_runs.status` for `failed`; re-run analysis: `POST /reports/{id}/analysis/refresh`.
3. If persistent, flip `TK_AI_GATEWAY_URLS` to the fallback provider via env + restart.

## S2-OtpDeliveryFailure
1. Console sandbox logs prove code generation; verify store reachable (Redis).
2. `verify-otp` errors are rate-limited; if mass failure, check rate-limit keys purge.
3. Phase 8 DLT SMS onboarding: provider outage → codes stay ephemeral; users retry.

## S1-Breach (DPDP §8(6) — 72-hour notification)
1. **Contain**: rotate `TK_JWT_SECRET` + minio creds; suspend affected accounts; snapshot evidence.
2. **Assess**: scope (users/contacts/AI logs/media) from audit_logs + retention tables.
3. **Notify** (draft): Data Protection Board + affected principals within 72h;
   fields: nature, timing, extent, mitigation, contact. Template lives in the
   incident folder (created on first use).
4. **Post-incident**: root-cause entry, checklist re-run, counsel review (COMPLIANCE-DPDP.md).

## S3-LatencyBreach (TkApiP95LatencySLO)
1. Dashboards: p95 by route group — identify hot group (usually reports/gis bulk reads).
2. Check `EXPLAIN ANALYZE` on the hot query; confirm index usage (reports category/status,
   GIST geography).
3. Mitigate: cursor pagination size down, add the planned index, or bound the
   duplicate-scan window; re-run `k6 run infra/k6/slo-smoke.js` to confirm the target.

## Runbook hygiene
- Every runbook ends with: timestamp, responder, timeline, follow-up ticket.
- Alert rules (infra/prometheus/rules.yml) reference these runbooks by section.
