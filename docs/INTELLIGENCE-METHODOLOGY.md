# Phase 20 — Civic Intelligence Methodology

This document is the faithful, non-privileged account of how the Phase 20
engines compute what they compute. It exists so that every number the platform
shows can be rederived by hand from the underlying tables, and so that "how was
this computed?" never requires reading code. Where the platform makes a claim
stronger than the data supports, that tension is flagged here rather than
hidden in a docstring.

Scope: the deterministic compute layer (`tk_api.intelligence.*`), the signal
review tables, forecast runs, and intelligence report artifacts. It does not
cover Phase 19 import/registry machinery or Phase 12 analytics.

---

## 1. Trends (`trends.py`)

**Inputs.** Public reports (`reports.visibility = 'public'`, `deleted_at`
NULL), optionally scoped by `boundary_id` (geography) and category slug.

**Method.** The counter for a metric over the current observation window is
compared with the counter over the *previous equal-length window*
(comparable periods). Windows: yesterday, last 7 / 30 / 90 days, last year,
or a custom range. Direction thresholds: `+10%` ⇒ increasing, `-10%` ⇒
decreasing, else stable; fewer than 3 observations ⇒ `insufficient_data`.

**Metrics.**

| metric | counter |
| --- | --- |
| `reports` | rows in `reports` |
| `resolved` | rows whose `status` is in `{resolved, community_verified, closed}` |

**Series.** Weekly (or daily/monthly) counts over the observation window,
bucketized by week start (Monday).

**Seasonality.** Monthly means over at least 2 years of history, returned as
proportions. Explicitly labeled: aggregated monthly pattern, not a causal
claim about seasonality.

**Saved.** `trend_snapshots` is append-only; each snapshot stores the metric,
period bounds, series, change, and `observed_at`. This gives historical
comparison without recomputation and without trusting report edits.

**Limitations (stated to consumers).**

- Counts are series of events, not risk. A large count of *open* items is
  different from a large count of *submitted* items.
- The comparison assumes comparable reporting propensity. A holiday or a
  media campaign changes propensity, and this is not controlled.
- No causation is inferred from a trend; the period comparison is
  descriptive.

---

## 2. Segmented time-series trends (`trends.py` same table)

When a trend request specifies `interval` granularity and a date range, the
engine also splits the series by `boundary_id` (segments) and, within each
segment, reports the top contributors by count. This is used to answer
"which geography is driving the national trend" without pretending the
geography *caused* it.

---

## 3. Snapshot integrity

Snapshots are written by the worker (`tk_worker.intelligence_snapshot`,
beat hourly) and by the summarize endpoints. They are never updated in
place; a new snapshot is always a new row. This makes the timeline
append-only and auditable (ADR-006 provenance discipline applied to internal
computation).

---

## 4. Anomalies (`anomalies.py`)

**Detectors.**

| metric | series | baseline | rule |
| --- | --- | --- | --- |
| `report_volume` | public reports per calendar week | trailing 8 weeks | point outside `[Q1 − 1.5·IQR, Q3 + 1.5·IQR]` of the baseline (Tukey fences) |
| `resolution_time` | hours from case creation to `resolution_verified_at` | trailing resolved cases | point outside same fences |
| `community_activity` | comments + verifications per week | trailing 8 weeks | point outside same fences |

Minimum baseline length is 8 points; below that the detector returns
`status = "insufficient_data"` instead of publishing a value. The anomaly
record stores `observed_value`, `expected_low`, `expected_high`,
`deviation_pct`, `method`, and a human-readable `explanation`.

**Semantics.** An anomaly is defined as *unusual relative to the recent
baseline*, not as *wrong*. Every stored event keeps its expected range, so a
reviewer can see the basis. `anomaly_events` is append-only; events carry
`status` (NEW / UNDER_REVIEW / CONFIRMED_SIGNAL / DISMISSED) managed through
the signal-review lifecycle when promoted to a signal.

---

## 5. Issue clusters (`clusters.py`)

**Inputs.** Public reports in the last `window_days = 30` (configurable,
default 30) that are not deleted.

**Grouping key.** `(geography or institution) + category + issue_type`.
Additionally, within the same (geography, institution, category) group,
titles whose normalized similarity ≥ `0.75` (Jaccard over tokens or
`difflib` ratio, whichever is higher) are folded into one cluster.

**Minimum size.** A cluster is emitted only when it has ≥ `3` reports
(`MIN_CLUSTER_REPORTS`).

**Cluster fields.** `cluster_key`, `label`, `category_slug`, scopes
(geography / institution), `report_ids` (all members), `report_count`,
`evidence_count` (members with `trust_score ≥ 0.3`), `first_seen`,
`last_seen`, `status = "open"`.

**Persistence.** `issue_clusters` is an upsert keyed by `cluster_key`;
membership is overwritten with the current computation. This is a summary
table, deliberately separated from the reports themselves.

**Important limit (stated to consumers):** clustering groups *related*
reports; it **never deletes or merges** reports. Duplicate decisions remain
a human action on the existing duplicate/moderation machinery. The engine
also never claims two reports are the same event — it reports that they are
*similar* and that the group warrants review.

---

## 6. Recurring issues (`clusters.py`, `RecurringIssueEngine`)

**Definition.** An issue *recurs* when the same `(geography or institution)
+ category + issue_type` appears in ≥ `3` distinct calendar months within the
last `6` months (no duplicate-of reports are counted).

**Output.** `distinct_months`, `total_reports`, `open_reports`,
`first_seen`, `last_seen`.

**Interpretation (locked in the response):** recurrence is a *review
trigger*, not proof of an unresolved problem. "Water issue reported in
May, June, July" does not by itself mean the water issue was never fixed —
it means the institution should be asked.

---

## 7. Data freshness and coverage duty-of-care (`freshness.py`)

**Freshness scan** (`DataFreshnessEngine.scan`):

- For each `data_sources` row (status ≠ inactive): compare `retrieval_date`
  (or `publication_date`) to `update_frequency_hours × 2` — older ⇒ STALE.
- For each `govdatasets` row: age of the latest successful
  `govimportjobs`; older than 30 days ⇒ STALE.
- For each `integration_connectors` in status `UNKNOWN`: age of
  `last_success_at` vs. configured frequency — older than 2× ⇒ STALE;
  never synced ⇒ flagged.
- Sources whose `last_verified_at` is missing or older than 90 days are
  listed as due re-verification.

**Coverage gaps** (`DataFreshnessEngine.gap_analysis`): per institution
type, count of institutions *with* an official-data comparison
(`institution_discrepancies` row) vs. total. Low coverage is *not* evidence
of failure — it is a candidate list for new source pings.

---

## 8. Resolution intelligence (`resolve_intel.py`)

Read-only aggregates over `cases`:

- Response / resolution clocks (avg, median, p90 in hours) from
  `sla_started_at`/`created_at` to `resolution_verified_at`/`closed_at`.
- SLA bucket counts (`within_sla`, `at_risk`, `breached`), compliance %.
- Aging buckets: 0–7, 8–14, 15–30, 31–90, 90+ days (closed cases age from
  start to close; open cases age from start to now).
- `reopen_count` (from case status history), `followup_signals`,
  `verified_resolution_count`, `community_confirmed_count`.

**Improvements** are reports currently in a resolved status (resolution
occurred at some point; `created_at` is the available timestamp anchor).
The response explains that a resolved report is not a guarantee the problem
will not recur.

---

## 9. Forecasting (`forecasting.py`)

**Model.** Weekly counts of the chosen metric
(`reports` / `resolved` / `reports_per_week`) trained on the trailing
history (≥ 8 weeks, capped at 130), smoothed with EMA (α = 0.3), and
extended with a linear drift clamped to `[−base, base + 0.5]`. Forecast
points carry `low` / `point / high` at ±35% spread. Evaluation metrics
(RMSE, MAPE%) are stored on the run.

**Insufficient-data path.** Fewer than 8 weekly observations ⇒
`status = "insufficient_data"` and *no points are published*. A forecast
that cannot be justified is not shown.

**Statuses.** `queued → running → completed | insufficient_data | failed`
(failure persists `error` on the run row). Each run pins `method`,
`model_version`, training window, and min point count, so an explanation in
the future can cite the exact run.

**Honest limits (in the response).** The model continues observed levels
with a clamped drift; it is a *planning range*, not a causal prediction.

---

## 10. Signals and review (`signals.py`, Phase 20 spec §6–§8)

**Creation.** Signals are created by the hourly/daily worker jobs
(converted from snapshots/anomaly events — implemented as manual/planned
promotion in 0033 wave-2; see below) or manually by administrators
(`POST /api/v1/intelligence/signals`).

**Review.** `POST /api/v1/intelligence/signals/{id}/review` (admin or
department). Actions map to status:

| action | new status |
| --- | --- |
| CONFIRM | CONFIRMED_SIGNAL |
| DISMISS | DISMISSED |
| REQUEST_MORE_DATA | UNDER_REVIEW |
| MONITOR | MONITORING |
| ESCALATE | CONFIRMED_SIGNAL (note carries escalation context) |
| MARK_RESOLVED | RESOLVED |

Every review appends an `intelligence_reviews` row (append-only) **and** an
audit-log entry (`Action: signals.review`). Evidence rows of kind `review`
record the decision with the reviewer id. Nothing in review mutates the
underlying reports or cases.

**Naming.** Severity (`LOW/MEDIUM/HIGH/CRITICAL`), confidence
(`LOW/MEDIUM/HIGH`), and visibility (`PUBLIC/COMMUNITY/DEPARTMENT/ADMIN/
RESTRICTED`) are stored on the signal; the visibility gate applies at
read time (see §16).

---

## 11. Model version registry (spec §12)

The `model_versions` table carries the versioning record for every
algorithmic component that produces a stored artifact. Phase 20 seeds the
entry points in the API (`/model-versions`) when the table is empty;
persisted rows always win over the seed list. Each entry pins training-data
reference and feature definitions (thresholds, windows) so "what went into
this number" is one query away.

---

## 12. Intelligence reports (`intel_reports.py`, spec §12)

`POST /api/v1/intelligence/reports` (admin/department) creates a
`pending` row. The worker (`tk_worker.generate_intelligence_report`) runs
the trend + anomaly + cluster + recurring + freshness + gap engines against
the report's scope, composes the six sections, serializes as JSON or CSV,
stores the artifact on the exports bucket, and flips the row to
`ready` (or `failed` + `error`, persisted).

Every artifact embeds `methodology` and `dataset_versions` so the "how was
this computed" answer ships inside the file itself.

---

## 13. Dashboard sections and map layers (spec §9, §11)

`GET /api/v1/intelligence/overview` composes: trend comparison, anomalies,
clusters, recurring issues, data freshness. Sections carry `limitations`
strings next to the numbers — the UI is expected to render them
(unformatted) as part of the section card.

`GET /api/v1/intelligence/map` aggregates public report counts per
geography (window `days`, default 90). It returns raw counts plus `count /
national total` normalized share, with an explicit caveat that raw counts
are not rates and small areas will look active. No population weighting is
applied (defensible, stated).

---

## 14. Export formats (spec §12)

- `json`: full payload with all sections + methodology.
- `csv`: one flattened row per entity per section (single table layout,
  `section` column + entity fields), suitable for spreadsheet pivots.

Stored at `tk-exports/intelligence/<report_id>.<format>`; the detail
endpoint returns a short-lived presigned URL.

---

## 15. Lifecycle / duty-of-care

- Worker job `intelligence_snapshot` (beat hourly): trends summary +
  snapshot persist + anomaly detect + persist events.
- Worker job `intelligence_clusters` (beat daily): cluster compute + save +
  recurrence detect.
- Both jobs are idempotent and safe under at-least-once delivery (append-only
  writes / keyed upserts).

---

## 16. Access control

- Read endpoints (`/trends`, `/anomalies`, `/clusters`, `/recurring`,
  `/overview`, `/map`, `/freshness`, `/data-gaps`, `/forecasts`,
  `/model-versions`, `/signals`, `/signals/{id}`) are public; signals are
  filtered to `PUBLIC/COMMUNITY/DEPARTMENT/ADMIN` for non-admins at read
  time.
- Create/review endpoints (`/signals`, `/signals/{id}/review`,
  `/forecasts`, `/reports`, `/reports/{id}`) require `admin` or
  `department` roles via the standard `require_active` gates.

---

## 17. What the platform does NOT claim

- No claim that any cluster member is "the same problem" — only similarity
  within a documented group followed by human review.
- No claim that a forecast is predictive — it is a planning range with
  explicit error terms.
- No claim that a resolved report cannot recur — improvements disclose
  recurrence explicitly.
- No claim about causation from trends, seasonality, or recurrence.
- Anomaly events are triggers for review, never accusations.