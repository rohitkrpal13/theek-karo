# Scale Test Report

**Date:** 2026-08-18
**Phase:** 16 Step 18 (security testing + scale test report)
**Tool:** k6 (`infra/k6/slo-smoke.js`, `docs/SLOs.md`)

## 1. Objective

Hold the documented SLOs under sustained load on the compose stack (real
Postgres + Redis + MinIO + API, same image as production):

- `http_req_duration` p(95) < 500 ms
- 5xx rate < 1%
- Functional checks pass ≥ 99%

## 2. Methodology

- Script: `infra/k6/slo-smoke.js` — 10 constant VUs for 30 s against
  `http://127.0.0.1:8001` (compose API on host port 8001, `TK_CELERY_ENABLED`
  compose default).
- Workload mix (per iteration, 6 requests): public categories list, reports
  list (`limit=20`), category detail, GIS tree, and a deliberately missing
  report (404 path — the only expected non-2xx; it exercises the error
  envelope under load).
- The 404 probe is excluded from the 5xx rate via `is5xx()`.

## 3. Results

| Metric | Value | SLO | Verdict |
|---|---|---|---|
| Requests | 7,164 (~235 req/s) | — | — |
| `http_req_duration` p(95) | **11.89 ms** | < 500 ms | ✅ |
| p(90) | 9.95 ms | — | — |
| max | 327.78 ms | — | — |
| 5xx rate | **0.00%** (0/1,194) | < 1% | ✅ |
| Functional checks | all passed | ≥ 99% | ✅ |
| `http_req_failed` | 16.66% (1,194/7,164) | — | = the intentional 404 probe (exactly 1 of 6 requests per iteration) |

## 4. Interpretation

- The API holds SLO latency with ~25× headroom on p95 under the smoke load.
  Median latency is 6.3 ms.
- Zero server errors; the only non-2xx responses are the scripted 404 probe.
- The rank-1 bottleneck at this scale is the API process + Postgres on the dev
  host, not the DB. Production Fargate (2 API tasks, RDS) is expected to
  sustain this comfortably; the real gate is at campaign scale (see §6).

## 5. Reproduce

```bash
make up                     # compose: postgres, redis, minio, api, worker
k6 run infra/k6/slo-smoke.js
```

The k6 thresholds fail the run (exit code non-zero) if any SLO is breached —
CI wiring for the load gate is the documented Phase 10 exit.

## 6. Known Limitations / Next Scale Steps

- **This is a smoke/scale test, not a full capacity test.** 10 VUs × 30 s on
  one dev host does not exercise: feed ranking at 100k reports, notification
  dispatch saturation, media scan worker throughput, or Postgres connection
  pool exhaustion under peak concurrency.
- Recommended before the first public campaign (Roadmap M3):
  1. Synthetic dataset (10k+ reports, 1k institutions) in staging.
  2. k6 soak (50 VUs, 15 min) against staging with the pool settings from
     Step 9 (10 + 20 overflow) and RDS metrics (CPU, connections, IOPS).
  3. Worker throughput test for media scan + notification dispatch.
  4. Feed endpoint p95 at cursor depth (page 50+) — verify the Step 9
     composite indexes hold.
- Full capacity planning (target RPS, concurrent users, storage growth) is
  tracked in the ROADMAP M3 gate.
