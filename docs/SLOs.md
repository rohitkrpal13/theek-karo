# SLOs (Phase 10)

Service-level objectives for the Theek Karo API (dev: measured against the
compose stack; production: identical thresholds on the deployed fleet).

## Definitions

- **Latency**: request duration from ingress to response, observed via
  `tk_api_request_duration_seconds` (bucketed histogram).
- **Error rate**: share of 5xx responses over the window
  (`tk_api_requests_total{status_class="5xx"}`).
- **Window**: 5-minute rolling (30-day cumulative error budget for prod).

## Targets

| SLO | Target | Error budget (30d) | Alert |
|-----|--------|--------------------|-------|
| API p95 latency (all routes) | < 500 ms | 5% of requests ≤ 500 ms violated | `TkApiP95LatencySLO` (page, 5m) |
| API 5xx error rate | < 1% | 1% of 30-day requests | `TkApiErrorRateHigh` (warning at 5%, 10m) |
| API availability (scrape up) | > 99.9% | 43 min/month | `TkApiTargetDown` (critical, 2m) |
| Notification queue length | ≤ 500 queued | drains weekly | `TkWorkerQueueBacklog` (warning, 15m) |

## Instruments

- `/metrics` (Prometheus text) on the API: request histogram/counters by
  route-group, `readyz` DB failures, queue-backlog gauge (per-scrape).
- Grafana dashboard `tk-api-slo` (provisioned, compose port 3001) with the
  p95/error/rate/queue panels; Prometheus rule file `infra/prometheus/rules.yml`.
- Load test: `k6 run infra/k6/slo-smoke.js` — 10 VUs for 30 s against the live
  compose API; thresholds replicate the p95/error SLOs.

## Enforcement

- The k6 thresholds fail the Phase 10 load-test gate; alert rules are
  provisioned in the compose stack and fire into the incident channel wired in
  production (Phase 11 wires Alertmanager/notifications).
- Dashboard + rules live in the repo (infra-as-code); drift between dashboard
  and rules is a review point, not an "at runtime" surprise.