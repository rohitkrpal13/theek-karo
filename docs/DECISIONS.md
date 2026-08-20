# ARCHITECTURE DECISION RECORDS (ADR)

**Project:** Theek Karo
**Status:** Active log. One entry per decision; statuses: Accepted / Proposed / Superseded.
Format: Context → Decision → Consequences.

---

## ADR-001 — uv as the Python package manager
- **Status:** Accepted (Phase 0)
- **Context:** Need reproducible, fast dependency management for a Python monorepo with a
  committed lockfile; developer machines vary (macOS/Linux).
- **Decision:** Use `uv` with `pyproject.toml` + committed `uv.lock`; dev deps in
  `[dependency-groups]`.
- **Consequences:** Fast cold installs; lockfile is source of truth; pin `uv` version in
  Dockerfile to match lockfile format. Trade-off: toolchain churn tracked against
  migration path.

## ADR-002 — Modular monolith, not microservices
- **Status:** Accepted (Phase 1)
- **Context:** Early-stage team; many bounded modules (auth, civic, reports, gis, ai,
  media, notifications); microservices would add ops burden before scale justifies it.
- **Decision:** One FastAPI deployable with strict service-layer boundaries; only
  `worker` (Celery) is separate. Extraction candidates measured by OTel before splitting.
- **Consequences:** Cheaper to develop; extraction cost deferred until real scale signals.

## ADR-003 — Civic categories/campaigns as configuration data
- **Status:** Accepted (Phase 1)
- **Context:** 14+ civic domains, new ones expected; code-per-category would multiply
  maintenance and block non-engineers from adding categories.
- **Decision:** Categories/campaigns are DB rows (`categories.form_schema` JSON Schema,
  `verification_policy` JSON); application is category-agnostic.
- **Consequences:** Adding a category = admin data change (≤ 1 day); schema must be
  versioned; UI renders forms dynamically.

## ADR-004 — PostgreSQL + PostGIS + pgvector as the single data platform
- **Status:** Accepted (Phase 1)
- **Context:** Geospatial queries + vector search both needed; a separate vector DB adds
  ops + consistency cost for MVP volumes.
- **Decision:** Use Postgres with PostGIS (geometry) and pgvector (embeddings); revisit
  only at >50M embedding rows with measured latency problems.
- **Consequences:** One system of record; GIST/vector indexes; simpler ops.

## ADR-005 — Redis + Celery for async work
- **Status:** Accepted (Phase 1)
- **Context:** Report analysis, media processing, notifications are slow and independent.
- **Decision:** Celery workers with Redis broker/result backend; idempotent tasks;
  at-least-once delivery with edge idempotency keys.
- **Consequences:** Proven stack; broker not a system of record; result retention bounded.

## ADR-006 — Provenance-first external data (never fabricate official info)
- **Status:** Accepted (Phase 1, product-level)
- **Context:** Government data is scarce, versioned, and legally sensitive; fabricated
  data would destroy trust and invite legal exposure.
- **Decision:** All external data carries `external_sources` + `provenance_records`;
  boundaries are ingested, never hand-drawn; "no data" is an honest state.
- **Consequences:** Schema-level enforcement (FK on `source_id`); ETL required for any
  dataset; some categories may launch without full official data.

## ADR-007 — Five-tier information classification
- **Status:** Accepted (Phase 1)
- **Context:** Content mixes citizen claims, community verification, official data, and
  AI output; trust requires an explicit, enforced taxonomy.
- **Decision:** `OFFICIAL_DATA | CITIZEN_REPORT | COMMUNITY_VERIFIED | AI_ANALYSIS |
  UNVERIFIED_INFORMATION`; enforced via CHECK constraints; AI restricted to T4.
- **Consequences:** UI can render truthfully; measurement distinguishes verified vs
  unverified; enforcement at DB level prevents mislabeling.

## ADR-008 — JWT access tokens + rotating refresh tokens (no opaque sessions)
- **Status:** Accepted (Phase 1)
- **Context:** Stateless APIs, multiple clients; OAuth server is heavyweight for MVP.
- **Decision:** Short-lived access JWT (15 min) + refresh tokens with family rotation and
  reuse-detection; TOTP MFA for officials/admins later.
- **Consequences:** Token revocation is bounded by refresh rotation; Redis blacklist for
  emergency revocation; custom implementation reviewed in Phase 3 (possible migration to
  OIDC if needs outgrow).

## ADR-009 — FastAPI + Pydantic v2
- **Status:** Accepted (Phase 0/1)
- **Context:** Python backend with strict validation and OpenAPI generation.
- **Decision:** FastAPI with Pydantic v2 models as the contract boundary.
- **Consequences:** Auto OpenAPI docs, typed validation; OpenAPI snapshots as contract tests.

## ADR-010 — Next.js (App Router) + React + TypeScript
- **Status:** Accepted (Phase 1, implementation Phase 7)
- **Context:** Need SSR for public report pages (SEO/accessibility), PWA capabilities,
  i18n, mobile-first.
- **Decision:** Next.js + React + TypeScript; static rendering for public routes where
  possible; client islands for maps/forms.
- **Consequences:** Rich ecosystem; build-time i18n via catalogs; CDN-friendly output.

## ADR-011 — docker-compose at repo root; host ports remapped for local dev
- **Status:** Accepted (Phase 0)
- **Context:** Other local projects occupy 5432/6379/8000 on the developer machine;
  port conflicts break dev experience.
- **Decision:** Compose file at root (`docker-compose.yml`); container ports standard,
  host ports remapped: api `8001`, postgres `5434`, redis `6380`, minio `9000/9001`.
- **Consequences:** No conflicts with other stacks; docs/README state the mapping;
  prod ports unaffected (no host binding in prod).

## ADR-012 — httpx2 as TestClient transport
- **Status:** Accepted (Phase 0)
- **Context:** starlette deprecated `httpx` as the TestClient transport in favor of
  `httpx2`.
- **Decision:** Dev dependency `httpx2`; tests use `fastapi.testclient.TestClient`.
- **Consequences:** No deprecation warnings; follows upstream direction.

## ADR-013 — Python ≥ 3.13, runtime image python:3.14-slim, uv pinned
- **Status:** Accepted (Phase 0)
- **Context:** Toolchain alignment between local dev (3.14.6) and containers.
- **Decision:** `requires-python >= 3.13`; runtime image `python:3.14-slim`; Dockerfile
  copies `uv` 0.11.24 pinned.
- **Consequences:** Reproducible builds; python minor bumps reviewed in CI.

## ADR-014 — RFC 9457 error model (application/problem+json)
- **Status:** Accepted (Phase 1)
- **Context:** Machine-usable, localizable error contracts across API.
- **Decision:** All non-2xx errors use RFC 9457 problem+json with `type`, `title`,
  `status`, `detail`, `instance`, optional `errors[]`.
- **Consequences:** Consistent client handling; error i18n via `title_key` later.

## ADR-015 — API versioning: `/api/v1`, additive-only minor changes
- **Status:** Accepted (Phase 1)
- **Context:** Long-lived mobile/web clients need stability.
- **Decision:** Base path `/api/v1`; breaking changes create `/api/v2` with ≥ 6-month
  migration window; additive changes allowed within v1.
- **Consequences:** Clean deprecation path; OpenAPI snapshot per version.

## ADR-016 — MCP only where genuinely useful
- **Status:** Accepted (Phase 1)
- **Context:** MCP is trending; adopting it wholesale would add coupling without need.
- **Decision:** MCP servers (e.g., boundary datasets, official-data lookups) are optional
  tool integrations introduced with the AI layer when they demonstrably reduce
  integration cost; core AI uses native tool calling.
- **Consequences:** No MCP in MVP path; revisit during Phase 6/12 spikes.

## ADR-017 — DeepSeek-compatible AI gateway with provider fallback
- **Status:** Accepted (Phase 1)
- **Context:** Need cost-effective chat + embeddings with no vendor lock-in.
- **Decision:** OpenAI-compatible client targeting a DeepSeek-compatible endpoint;
  fallback provider chain; degraded mode explicit; model/version recorded per run.
- **Consequences:** Provider swap is config-only; eval harness pins quality (≥ 95%
  citation precision) before scaling.

## ADR-018 — Human review for sensitive AI decisions
- **Status:** Accepted (Phase 1)
- **Context:** Duplicate merges, official-status claims, escalations are irreversible or
  reputation-bearing.
- **Decision:** AI marks candidates (`merged_by_ai`, review queue); only humans apply
  them; every decision audited.
- **Consequences:** Slightly slower merges; guarantees accountability; queue tooling in Phase 6.

## ADR-019 — PII-minimized AI logging
- **Status:** Accepted (Phase 1)
- **Context:** DPDP + retention obligations; LLM providers may process payloads.
- **Decision:** `ai_runs.payload_in` stores actor ids and redacted free text, not raw PII;
  90-day retention unless flagged; provider contract must prohibit training.
- **Consequences:** Investigation-grade logs require care; redaction pipeline in Phase 6.

## ADR-020 — OpenTelemetry as the observability standard
- **Status:** Accepted (Phase 1)
- **Context:** Need metrics, traces, logs on one pipeline; vendor portability.
- **Decision:** OTel SDK in API + workers; JSON structured logs with correlation ids;
  Prometheus-compatible export; Grafana dashboards (Phase 10).
- **Consequences:** Dashboards portable across AWS/GCP; SLO alerting in Phase 10.

## ADR-021 — i18n mechanism (decided in Phase 7)
- **Status:** Accepted (Phase 7)
- **Context:** Need type-safe, SSR-friendly bilingual catalogs (en/hi) on a
  Next.js 16 app with the community-translation store (`translations` table)
  feeding in later (I18N.md §6).
- **Decision:** Hand-rolled, dependency-free i18n: `en`/`hi` dictionaries in
  `apps/web/src/lib/i18n.ts` with format-string interpolation, a
  locale-context `useT()` on the client and a plain `t()` for server
  components, locale routing via the Next 16 `proxy.ts` (`/` → `/en`,
  `/hi|/en/…` preserved). `next-intl` was trialled and skipped for its Next 16
  churn; the API `translations` table remains the community-review store.
- **Consequences:** Zero dependency, full type-checking of keys; adding locales
  is dictionary work; community translations replace web catalogs behind the
  same `t()` keys when the i18n backend endpoint ships.

## ADR-022 — Alembic migrations with fresh-db CI verification
- **Status:** Accepted (Phase 1)
- **Context:** Schema changes must be reproducible and safe.
- **Decision:** Alembic; migrations run in CI against fresh PostGIS; downgrade tested;
  seed data via idempotent data migrations.
- **Consequences:** Safe schema evolution; CI catches order/state drift.

## ADR-023 — stdlib JSON logging (no structlog dependency)
- **Status:** Accepted (Phase 2)
- **Context:** Need structured single-line JSON logs with correlation ids without adding
  a logging framework.
- **Decision:** stdlib `logging` with a custom `JsonFormatter` + `ExtraFieldFilter`;
  extras passed via `log_extra(**fields)`; uvicorn loggers redirected; request id carried
  by a contextvar (usable later by Celery tasks).
- **Consequences:** Zero extra runtime deps; formatting conventions enforced by ruff/mypy;
  migration path to structlog open if field control needs grow.

## ADR-024 — OpenAPI snapshot as the contract test
- **Status:** Accepted (Phase 2)
- **Context:** API.md is the design contract; drift between docs and code must be caught.
- **Decision:** Commit `tests/contracts/openapi.snapshot.json`; a test fails on drift;
  `scripts/update_openapi_snapshot.py` regenerates after intentional changes.
- **Consequences:** Contract drift is a CI-visible failure; regeneration is explicit.

## ADR-025 — Readiness semantics: liveness without deps, readiness with DB check
- **Status:** Accepted (Phase 2)
- **Context:** Orchestrators need to distinguish "process alive" from "can serve traffic".
- **Decision:** `/healthz` stays dependency-free (200 always when process runs);
  `/readyz` executes `SELECT 1` via SQLAlchemy async engine and returns 503 problem+json
  when the database is unreachable.
- **Consequences:** K8s/compose routing can pull the api from load when DB is down;
  monitoring distinguishes liveness from dependency health.

## ADR-026 — SQLite in-memory unit tests, Postgres for integration
- **Status:** Accepted (Phase 3)
- **Context:** Unit tests must run fast, offline, and repeatable while still exercising
  real SQLAlchemy ORM code. Phase 2's harness could only ping Postgres, so auth flows
  (the first persistence-heavy feature) needed a day-one test database.
- **Decision:** Unit tests build the app against `sqlite+aiosqlite://` (StaticPool,
  in-memory, schema created via `Base.metadata.create_all` + role seed). Tests that need
  real Postgres behavior (UUID binding, timezone handling, migrations) live in
  `tests/integration/` under the `integration` pytest marker; `make test-integration`
  requires `make up` and runs Alembic `upgrade head` itself.
- **Consequences:** Fast, hermetic suites; drift between SQLite and Postgres is caught
  by the small integration suite + live verification each phase. SQLite quirks that
  surfaced (naive datetimes, string UUID binds, JSON serializer) were fixed in shared
  code, which also hardened the Postgres path.

## ADR-027 — GeoAlchemy2 for spatial types; GIST indexes auto-managed (Phase 4)
- **Status:** Accepted (Phase 4)
- **Context:** PostGIS geometry columns (`reports.location`, `gis_boundaries.geom`,
  `gis_places.geom`) enter the schema in Phase 4. GeoAlchemy2 auto-creates a GIST index
  (`idx_*`) for every `Geometry` column, so hand-written `GIST` indexes in migrations
  would be duplicates. Unit tests run on SQLite (ADR-026), which has no spatial types.
- **Decision:** Declare spatial columns via GeoAlchemy2 `Geometry(geometry_type, 4326)`;
  never write explicit GIST indexes in migrations (GeoAlchemy2 owns them); migration
  downgrades drop only the tables, letting the auto-indexes fall away. Spatial-FK tables
  such as `campaign_scopes` keep `boundary_id` as a plain UUID column with no ORM FK so
  the SQLite unit-test schema stays non-spatial; the FK is enforced at migration level
  (`0005_reports_media`). Spatial behaviour is exercised only by integration tests on
  Postgres (e.g. `ST_DWithin` with `::geography` cast — geometry(4326) distances are in
  degrees, not meters).
- **Consequences:** Clean schema (`IS (gist) (location)` appears exactly once, verified
  by test); unit tests stay fast and equivalent; anything space-dependent must be
  integration-tested on the compose PostGIS before a release.

## ADR-028 — Dialect-swapped spatial column type for testable ORM geometry (Phase 5)
- **Status:** Accepted (Phase 5)
- **Context:** `reports.location` must be real PostGIS geometry on Postgres while
  unit tests run on SQLite (ADR-026), which has no spatial types. Wrapping
  GeoAlchemy2's `Geometry` in a plain `TypeDecorator` for a SQLite fallback does
  not work as-is: the decorator's processors replace GeoAlchemy2's, so a
  `WKBElement` reaches the driver and fails; and GeoAlchemy2 wraps itself in
  user-defined types that do not nest cleanly.
- **Decision:** A custom `LocationPoint` TypeDecorator whose
  `load_dialect_impl` returns `Geometry(POINT, 4326)` on Postgres and `String`
  on SQLite, with its own processors both ways: GeoJSON dict → hex EWKB string
  (Postgis accepts EWKB hex as column input; SRID header included) / JSON string
  (SQLite), and reads back hex/EWKB/WKBElement → GeoJSON dict. No reliance on
  GeoAlchemy2's bind/result processors. Service code always uses GeoJSON
  Point dicts.
- **Consequences:** The full report engine is unit-tested on SQLite with real
  GeoJSON round-trips; Postgres geometry + GIST indexing + `ST_DWithin`
  (metres via `::geography`) verified by integration tests and live checks.
  Spatial behaviour remains integration-only (ADR-027). Hex-EWKB string binding
  is Postgres-specific and stayed isolated in the type.

## ADR-029 — Presigned URLs signed with the client-facing endpoint (Phase 5)
- **Status:** Accepted (Phase 5)
- **Context:** MinIO/S3 presigned URLs are SigV4-signed and the canonical
  request includes the `Host` header. Rewriting a URL's host after signing
  (e.g. internal `minio:9000` → public `127.0.0.1:9000`) invalidates the
  signature (`SignatureDoesNotMatch`). The API container cannot reach the
  public endpoint, so the presigning client must not perform network lookups.
- **Decision:** The storage adapter keeps two MinIO clients: an internal one
  (`TK_MEDIA_MINIO_ENDPOINT`) for object operations/bucket setup, and a signer
  client bound to the public endpoint (`TK_MEDIA_MINIO_PUBLIC_ENDPOINT`,
  reachable by browsers/hosts) used only to mint presigned PUT/GET URLs, with
  the region pinned to `us-east-1` so the SDK never issues a network
  GetBucketLocation against the public endpoint. Installations must point the
  public endpoint at the address clients will actually use.
- **Consequences:** Presigned flows work from browsers and local tools across
  compose and cloud (S3/VPC endpoint = internal, public DNS = signer);
  misconfiguration surfaces as client-side signature errors rather than
  server failures.

## ADR-030 — Duplicate matching: trigram-free Python scorer now, pgvector as the scale-up (Phase 6)
- **Status:** Accepted (Phase 6)
- **Context:** ADR-004/ADR-017 planned pgvector cosine similarity for duplicate
  matching, but the dev PostGIS image ships no `vector` extension (verified in
  compose) and adopting a community PostGIS+pgvector image is a supply-chain
  risk. The human-review guarantee (ADR-018) must hold regardless of the scorer.
- **Decision:** Phase 6 matches duplicates with a cross-dialect Jaccard
  word-bigram scorer in Python over a bounded recent-window scan — identical
  results on SQLite unit tests and Postgres — feeding the `ai_reviews` queue
  (migration `0007_ai_reviews`). `report_embeddings` (pgvector) stays in
  DATABASE.md as the documented scale-up; its migration ships when the
  deployment platform provides the extension (RDS/Aurora ship pgvector
  natively). The gateway likewise falls back to the deterministic `stub`
  provider without an API key, and the eval harness (`make eval-ai`) pins a
  category-accuracy floor of 0.5 for whichever provider runs.
- **Consequences:** Review queue + eval work identically on every environment;
  switching to embeddings later only replaces the scorer behind the same queue
  contract; compose stays on the official image.

## ADR-031 — Celery worker owns durable jobs; console providers as sandbox (Phase 8)
- **Status:** Accepted (Phase 8)
- **Context:** ADR-005 promised Celery on Redis for async work (media scan,
  AI analysis, notification dispatch, measurement rollups); the API had been
  running those inline. Phase 8 needs the queue staffed and providers
  pluggable without a DLT-registered SMS vendor in reach.
- **Decision:** A `worker` compose service (same image) runs
  `celery -A tk_api.worker:celery_app worker --beat` (solo pool for dev; the
  beat schedule file lives in `/tmp` because the runtime user's `/app` is
  read-only). Tasks open their own sessions on the shared Postgres and are
  re-entrant (status gates make at-least-once safe). The worker entry imports
  the full model registry so deferred ORM FKs resolve in-process. Media
  complete → `pending_scan` + task; AI auto-analysis and hourly rollups are
  celery tasks; the in-process fallbacks remain for tests and
  single-process dev (`TK_CELERY_ENABLED=false`). Provider side: SMS/email are
  structured-log console sandboxes behind a `send()` protocol — the India DLT
  provider and transactional email drop in without touching the queue flow.
- **Consequences:** Long-running work leaves the API process; deliveries are
  inspectable in worker logs (sandbox); retries/attempts live in
  `notification_queue`; a failing provider degrades to visible `failed` rows
  instead of silent loss.

## Superseded / Rejected

- **Rejected:** Separate vector database (overkill at MVP, ADR-004 alternative).
- **Rejected:** Keycloak/OIDC for MVP (ops weight; ADR-008 alternative; revisit if SSO
  becomes a product requirement).
- **Superseded:** `httpx` TestClient transport (→ ADR-012).
- **Superseded:** Baseline provisional phase list (→ `ROADMAP.md`).## ADR-032 — Boundary ingestion ETL + reverse geocode on PostGIS (Phase 9)
- **Status:** Accepted (Phase 9)
- **Context:** Phase 9 needs real India boundaries that satisfy ADR-006
  (ingested, never hand-drawn, full provenance) plus reverse geocoding, and an
  honest path when official data is not yet available.
- **Decision:** A CLI ETL (`scripts/ingest_boundaries.py`) loads a licensed
  GeoJSON FeatureCollection (default source: geoBoundaries India ADM1, CC-BY,
  served via `media.githubusercontent` — the repo stores data on Git LFS) into
  `gis_boundaries`, creating/git-cloning the `external_sources` +
  `gis_boundary_versions` provenance pair; idempotency is the version label
  (re-ingest swaps the version's rows). Kind-ordered reverse geocoding
  (fine→coarse via `array_position` + `ST_Covers`) powers
  `/gis/reverse-geocode` and automatic `boundary_id` assignment on report
  submission; proximity uses the geography cast for metres. The GIS module
  never registers ORM models at import (constants live in a model-free
  module), so the SQLite unit schema stays geometry-free (ADR-026/027).
- **Consequences:** One auditable command to load new boundary levels/wards
  (`--parent-kind` links children by name); tests use clearly-labeled
  synthetic fixtures; the live DB holds real states with CC-BY attribution
  surfaced in every boundary detail response.

## Superseded / Rejected
## ADR-033 — Prometheus + Grafana for SLOs; security headers; load test as the SLO gate (Phase 10)
- **Status:** Accepted (Phase 10)
- **Context:** Phase 10 needs observable SLOs (p95 latency, error rate,
  availability), alert rules, a load-tested performance gate, and a
  compliance/security pass — without standing up a full observability
  platform prematurely (ADR-020 OTel wires tracing/metrics export; no collector
  yet).
- **Decision:** The API exposes Prometheus text metrics at `/metrics`
  (`prometheus-client`): request histogram/counters by a bounded route-group
  label set (cardinality discipline), plus a per-scrape notification queue
  gauge. Compose adds `prometheus` (host 9091) + `grafana` (host 3031) with
  repo-provided provisioning (datasource, `tk-api-slo` dashboard, rules file);
  SLOs and runbooks live in the repo (docs/SLOs.md, docs/RUNBOOKS.md). The
  performance gate is a k6 script (`infra/k6/slo-smoke.js`) whose thresholds
  mirror the SLOs (p95 < 500 ms, 5xx < 1%). Hardening: a security-headers
  middleware (nosniff/X-Frame/Referrer/Permissions) + the SECURITY-CHECKLIST,
  DPDP memo, and runbooks. OTel remains for tracing + rich verbosity needs;
  Grafana consumes Prometheus directly.
- **Consequences:** Zero-dependency-`grafana`-cluster ops; the dashboard and
  alert rules are reviewable infra-as-code; HSTS/TLS/WAF/Alertmanager
  channels are explicitly deferred to Phase 11; port remaps (9091/3031)
  documented in ARCHITECTURE + compose.

## Superseded / Rejected
## ADR-034 — Production deploy shape: AWS ECS Fargate via OIDC + Terraform (Phase 11)
- **Status:** Accepted (Phase 11)
- **Context:** Need a repeatable, auditable production path (ADR-004/005/032
  presaged PostGIS+Redis+S3; Phase 10 validated SLO/p95 baseline). This repo
  has no AWS tenant credentials; infra must be reviewable and validate-able
  locally and apply-able from the pipeline.
- **Decision:** GitHub Actions with OIDC (no long-lived keys) drives build +
  push to ECR, runs `alembic upgrade head` against the target DB **before**
  cutting services, then updates ECS services with pinned revisions; a
  rollback workflow restores the previous task-def revision. Terraform
  (infra/terraform, `terraform validate` passes) expresses the whole stack —
  VPC/ALB/TLS (ACM), ECS Fargate (api/worker/web), RDS Postgres 16
  (+PostGIS +pgvector native), ElastiCache Redis, S3 media via an IAM user +
  CloudFront OAI, Secrets Manager for runtime secrets. `--pool=solo` worker
  on Fargate; CloudWatch logs 14 days.
- **Consequences:** First `terraform apply` + ACM validation + Route53 wiring
  remain human bootstrap steps from the pipeline account; costs are
  Fargate-tiered; every deploy is revision-pinned and rollback-symmetric;
  staging and prod share the exact same code path (only variables differ),
  which the workflow enforces.

## Superseded / Rejected
## ADR-035 — Hierarchical + places ingestion, honest no-data for unavailable sets (Phase 12)
- **Status:** Accepted (Phase 12)
- **Context:** Phase 9 loaded states only. Districts (geoBoundaries ADM2)
  carry **no parent references** in their properties; wards have no licensed
  open source for the pilot geography; the schools pilot needs point
  "directory" data with provenance.
- **Decision:** Parent linking is **centroid containment** (`ST_Covers` on the
  child centroid against the parent kind) — one UPDATE after batch insert,
  robust to datasets without parent attributes. The ETL gained a places path
  (`--places`) writing **point** records into `gis_places` (replace-per-source
  idempotency; the table deliberately carries no version column). Missing
  datasets are recorded honestly in `docs/PROVENANCE.md` with a licensing
  assessment and next actions (UDISE+ schools, municipal wards) rather than
  fabricated or hand-drawn substitutes (ADR-006).
- **Consequences:** 735 districts live, 100% linked to states; reverse
  geocoding resolves to district depth for the platform; the dev schools
  fixture exercises the places pipeline with explicit "NOT official data"
  labeling; ward-level data stays out until a licensed source clears.

## Superseded / Rejected
## ADR-036 — Modular monolith with 23 module boundaries (Cycle 2)
- **Status:** Accepted (Cycle 2, Phase 2 — System Architecture)
- **Context:** The product scope grew to 23 bounded modules (identity, users,
  geography, institutions, categories, reports, media, comments, community,
  moderation, verification, resolution, notifications, analytics, search,
  maps, government-data, rag, ai, agents, integrations, administration,
  audit). Microservices remain an ops burden without measured scale signals.
- **Decision:** One FastAPI deployable; modules exchange through service
  functions (no cross-module SQL in the API layer); only the Celery worker is
  separate. Extract candidates are chosen by OTel dependency heat and the S4
  triggers in ARCHITECTURE §19 — measurement first, never by taste.
- **Consequences:** Cheaper evolution; extraction deferred until ~1M users or
  measured saturation; module tests keep boundaries honest.

## ADR-037 — Model-agnostic AI: gateway → router → capabilities
- **Status:** Accepted (Cycle 2, Phase 2)
- **Context:** Business logic must not couple to DeepSeek (or any provider);
  providers churn and the product already lists 14 AI capabilities.
- **Decision:** The AI surface is capability contracts only (AI-ARCHITECTURE
  §1–§4). A data-defined **model router** maps task→providers/models with
  cost/latency budgets and eval floors; the DeepSeek-compatible gateway is
  one provider behind the chain; the stub remains for dev/tests/eval.
- **Consequences:** Provider swaps are config changes; eval floors gate
  promotions; cost analytics feed router policy; no name leakage into
  business logic.

## ADR-038 — Vector strategy: pgvector now, dedicated at >10M rows
- **Status:** Accepted (Cycle 2, Phase 2)
- **Context:** RAG + NL search need embeddings storage; Cycle 1 deferred
  pgvector until the platform had it (compose image / RDS parity).
- **Decision:** Use pgvector on the same Postgres (RDS ships it natively;
  compose gets the extension by migration). Metrics (embedding-row counts,
  p95) trigger a dedicated vector instance + indexing service at >10M rows;
  partition report embeddings by time.
- **Consequences:** One system of record early; a clean split path when
  measured — never a rewrite of the RAG contracts.

## ADR-039 — RAG answers only from provenance-gated corpora
- **Status:** Accepted (Cycle 2, Phase 2)
- **Context:** Assistant/civic Q&A must never fabricate (ADR-019 series);
  government comparisons must only use authoritative data.
- **Decision:** RAG retrieval scoped to the corpora registry (licensed
  datasets + platform-verified corpus); every answer carries citations or
  declines; no-citation ⇒ no-claim is a product rule enforced by eval.
- **Consequences:** Answer quality is bounded by dataset licensing;
  "no data is an honest state" extends from boundaries to every corpus
  (PROVENANCE.md).

## ADR-040 — Agents: capability units + human-in-the-loop gates; MCP optional
- **Status:** Accepted (Cycle 2, Phase 2)
- **Context:** V2 adds agentic assist; ADR-016 kept MCP optional from Cycle 1.
- **Decision:** Agents are registry-defined compositions of capability +
  tool units with step/cost budgets and full `ai_runs`-style audit. Any
  irreversible action (merge, strike, official post, delete, official
  response) stops at a human gate with a rationale + evidence links. MCP
  surfaces are read-only platform servers where they demonstrably cut
  integration cost; write-capable MCP is phase-gated behind the same RBAC +
  audit as the API.
- **Consequences:** Safe autonomy with accountability; MCP stays a niche
  adapter; agents remain observable and budgeted.

## ADR-041 — Search tiering: Postgres first, dedicated engine at scale
- **Status:** Accepted (Cycle 2, Phase 2)
- **Context:** Search spans reports, twin profiles, and the feed; a dedicated
  engine adds an SRE surface before 1M rows justify it.
- **Decision:** Ship search on Postgres (pg_trgm + pgvector hybrid) behind a
  service interface; introduce a dedicated indexer+search engine only when
  measured ≥1M rows or search-p95 > 300 ms; NL search re-ranks through the AI
  router (V1).
- **Consequences:** One interface, two backends; the swap is an adapter
  change behind the same contract (ARCHITECTURE §7, §19).

## Superseded / Rejected (history)
- Cycle-1 ADRs 001–035 remain active and are the provenance for the baseline;
  this phase's decisions extend, not replace, them (ADR-016 refined by
  ADR-040; ADR-008 extended for OAuth/MFA in SECURITY §2).
## ADR-042 — Phase-3 data layer: full Cycle-2 domains, pgvector-deferred
- **Status:** Accepted (Cycle 2, Phase 3)
- **Context:** Phase 3 must materialise the product's 36-section data model
  (identity → analytics) on the existing Postgres while keeping the Cycle-1
  baseline green and the unit-test schema SQLite-safe (ADR-026/027).
- **Decision:** 11 new migrations (0010—0020) added all domains additively:
  identity expansion (permissions/role_permissions/oauth/sessions/
  verification/reset/security-events), geography registry (types/geography/
  translations; geometry via PostGIS; **level names are data**), institutions
  (types + typed attribute system + translations; no hundreds of nullable
  columns), provenance domain (sources/versions/records/imports with
  time-travel), categories v2 + issue types, reports v2 (nullable
  institution/issue-type FKs, severity/visibility CHECKs), evidence + media
  processing pipeline (UPLOADED→REJECTED states), report duplicates
  (AI-suggest only), community + moderation (reactions/posts/followers/
  bookmarks/content-reports/actions/decisions/appeals), resolution +
  reputation (balanced policies, events) + subscriptions (single-target
  CHECK) + push devices, content translations, AI outputs/feedback/
  evaluations, RAG documents/versions/chunks, government datasets with
  versioned records, and analytics events/daily cells. Versioned-key
  uniqueness (source_records, gov_dataset_records) makes "what did the data
  say at time T" answerable — fixed by migration 0020. **pgvector is
  deferred**: `rag_chunks.embedding` + HNSW land when the instance can host
  the `vector` extension (RDS native; compose image constraint from ADR-030);
  `embedding_status` already gates the embedder worker.
- **Consequences:** The schema is the registry for the entire product; no
  India-specific hierarchy in code; AI can only suggest duplicates (human
  applies); fresh-DB round trip and live-dev upgrade both verified; the
  geometry-bearing ORM tables stay unregistered in the SQLite unit schema
  (raw SQL in PG integration tests).

## ADR-043 — Modular Monolith Core API Layer and API v1 Registry
- **Status:** Accepted (Cycle 2, Phase 5)
- **Context:** Phase 5 establishes the backend foundation for Theek Karo's Cycle-2 expansion. The API layer requires a modular structure (`tk_api/<domain>/`), generic pagination and safe SQL sort allowlists, RFC 9457 Problem Details error responses with correlation tracing, dynamic geographic hierarchy traversal (no hardcoded levels), digital twin CRUD for public institutions, extensible issue types, and a centralized versioned API routing mount (`/api/v1`).
- **Decision:**
  1. Built modular domain packages (`geography`, `institutions`, `civic`, `reports`, `search`, `core`).
  2. Implemented generic `PageParams`, `CursorParams`, `PageResponse[T]`, and base64 cursor helpers.
  3. Implemented safe column sort helper `apply_sort()` with explicit allowlists to prevent SQL injection.
  4. Standardized error handling on RFC 9457 `ProblemDetails` injecting `request_id` and `X-Correlation-ID`.
  5. Implemented dynamic Geography hierarchy endpoints (`/types`, `/{id}/children`, `/{id}/ancestors`, `/search`).
  6. Implemented Institution Digital Twin CRUD and attribute value filtering.
  7. Expanded Report state machine and added issue type and institution linkage.
  8. Created Unified Search abstraction (`tk_api/search/`) across reports, institutions, geography, and categories.
  9. Centralized all domain routers under `/api/v1` in `tk_api/api/v1.py` and provided dual ops probes (`/health`, `/healthz`, `/ready`, `/readyz`).
- **Consequences:** Clean domain separation with zero hardcoded administrative hierarchy; future API versions (`/api/v2`) can be mounted alongside `/api/v1`; 100% test suite compatibility maintained (144 unit tests passing).

## ADR-044 — Frontend Application Architecture, Modular API Client, and Accessible UX Foundation
- **Status:** Accepted (Cycle 2, Phase 6)
- **Context:** Phase 6 establishes the production-grade frontend architecture for Theek Karo, connecting the Phase 4 design system and Phase 5 backend API layer into an accessible, responsive, mobile-first web application.
- **Decision:**
  1. **Stack & Routing**: Standardized on Next.js 16 (App Router), React 19, TypeScript, TailwindCSS v4 with PostCSS, and localized route prefixing (`/[locale]/...`).
  2. **Modular API Client**: Structured `apps/web/src/lib/api/` with domain clients (`geography`, `institutions`, `civic`, `reports`, `search`) providing typed request execution, RFC 9457 Problem Details error decoding, and query string parameter safety.
  3. **Global Search**: Built accessible combobox search experience (`GlobalSearch.tsx`) with domain filter tabs (`All`, `Reports`, `Institutions`, `Places`, `Categories`), debounced query dispatch, and keyboard navigation.
  4. **Dynamic Geographic Exploration**: Implemented zero-hardcoding hierarchy drilldown and breadcrumbs using `/api/v1/geography` endpoints with dual Map/List layout.
  5. **Institutions Digital Twin**: Implemented directory listing (`/institutions`) and digital twin detail page (`/institutions/[id]`) showing operational status, dynamic EAV infrastructure/staffing attributes, linked reports, and provenance.
  6. **Report Creation Wizard**: Multi-step submission flow (`/submit`) with category selection, GPS geolocation, optional institution association, dynamic schema fields validation, evidence upload staging, and idempotent review/submission.
  7. **Multilingual Architecture**: Supported 14 Indian languages via typed key-value catalogs with fallback resolution.
  8. **Accessibility & Quality**: WCAG 2.2 AA compliance, semantic HTML, screen reader labels, keyboard focus rings, light/dark theme switching, and automated Vitest component testing.
- **Consequences:** Scalable and maintainable frontend codebase; 100% TypeScript compilation and Vitest pass rate; clean separation between UI components and API communication.

## ADR-045: Production Identity, Authentication, Fine-Grained RBAC & Account Security (Phase 7)
- **Status:** Accepted
- **Context:** The platform requires production-grade user identity, authentication, session management, multi-role RBAC with 9 standard roles, resource-level ownership enforcement (IDOR protection), password reset/change lifecycle, Google OAuth integration, active session revocation, DPDP-compliant account anonymization, and structured security event audit logging.
- **Decision:**
  1. **Authentication Architecture**:
     - Passwords hashed using Argon2id (`argon2-cffi`) with min 8 chars policy.
     - Single-use verification and password reset tokens stored as SHA-256 digests (`email_verifications`, `password_reset_tokens`) with strict TTL and one-time invalidation.
     - Safe generic responses on `forgot-password` and `resend-verification` to prevent account enumeration.
     - Active multi-device session tracking in `sessions` table, with per-session revocation and `logout-all` invalidation.
  2. **Fine-Grained Authorization & RBAC**:
     - 9 standard roles seeded: `citizen`, `volunteer`, `verified_contributor`, `moderator`, `institution_representative`, `department_representative`, `analyst`, `admin`, `super_admin`.
     - Centralized `AuthorizationService.can(user, permission, resource)` and `.require()`.
     - Resource-level IDOR enforcement (e.g. User A cannot edit or delete User B's report; institution representative scoped actions; self-profile modification).
     - Super Admin wildcard (`*`) permission override.
     - FastAPI dependencies `require_permission(code)` and `require_any_permission(*codes)`.
  3. **Account Lifecycle & Privacy**:
     - Google Sign-In OAuth flow (`GET /auth/oauth/google/url`, `POST /auth/oauth/google/callback`) with verified-email account linking.
     - DPDP Act compliant account deletion (`DELETE /users/me`) anonymizing PII (`Anonymous Citizen`, stripped email/phone/username/passwords) while preserving public civic contributions for auditability.
     - Comprehensive security event logging into `security_events` table (`REGISTER`, `EMAIL_VERIFIED`, `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`, `PASSWORD_CHANGED`, `SESSION_REVOKED`, `LOGOUT`, `LOGOUT_ALL`, `OAUTH_LOGIN`, `OAUTH_LINKED`, `ACCOUNT_DELETED`).
  4. **Frontend Security Experience**:
     - Upgraded `AuthProvider` and `useAuth()` hook with `roles`, `permissions`, `hasRole()`, and `hasPermission()`.
     - Built dedicated `/verify-email`, `/forgot-password`, `/reset-password`, `/auth/callback`, and `/profile/security` pages.
- **Consequences:** End-to-end security posture verified across 157 pytest backend tests and 22 vitest frontend tests; full prevention of IDOR and token replay attacks; DPDP compliance.

## ADR-046: Civic Reporting Lifecycle, Media Evidence Pipeline, AI-Assisted Intake, and Community Verification (Phase 8)
- **Status:** Accepted (Cycle 2, Phase 8)
- **Context:** Civic observation reporting is the primary data intake channel of Theek Karo. A civic report is a structured observation record (Who, What, Where, When, Category, Issue Type, Observation Date, Evidence, Severity, Verification State, History) rather than a simple text complaint. Requirements include: Draft saving & recovery, one-shot submission, pre-signed upload slots & checksum verification for media evidence, clear separation of community verification from policy moderation, suggest-only non-intrusive AI intake, heuristic spatial duplicate detection, and rich frontend reporting experiences.
- **Decision:**
  1. **Data Model & Migrations**:
     - Alembic migration `0022_phase8_reporting_enhancements.py` adding `observed_at` (nullable datetime for observation date separate from submission timestamp) and `coordinate_source` (enum check constraint: `USER_SELECTED`, `DEVICE_LOCATION`, `INSTITUTION_LOCATION`, `MAP_SELECTED`, `IMPORTED`) to `reports` table.
  2. **Draft & Report Lifecycle**:
     - Complete draft CRUD (`POST /reports/drafts`, `GET /reports/drafts`, `PATCH /reports/drafts/{id}`, `DELETE /reports/drafts/{id}`, `POST /reports/drafts/{id}/submit`) with IDOR ownership protection.
     - Immutable observation records upon submission; status transitions recorded append-only in `report_status_history`.
     - Fields update restricted to editable statuses (`draft`, `submitted`, `needs_information`), locking modifications upon assignment/verification (`fields_locked`).
  3. **Media Evidence Pipeline**:
     - Pre-signed upload authorization (`POST /reports/{id}/media/upload-url`) enforcing mime type and declared size limits.
     - Completion verification (`POST /reports/{id}/media/complete`) validating actual byte length and computing SHA-256 checksums.
     - Multi-evidence attachment, listing, and deletion with ownership checks.
  4. **Community Verification & Trust Scoring**:
     - `POST /reports/{id}/verifications` and `GET /reports/{id}/verifications`.
     - Separate verification (credibility) from moderation (policy compliance).
     - Self-verification prohibited (403 `own_report_verification_forbidden`).
     - Confirmation increases trust score (+0.15); refutation decreases trust score (-0.20).
     - Auto-promotion from `submitted` to `under_verification` and upon reaching trust threshold (≥ 0.30) to `verified`.
  5. **AI-Assisted Intake & Heuristics**:
     - Suggest-only real-time suggestions (`POST /reports/ai/suggest`) providing category, issue type, title, and severity recommendations without mutating user inputs.
     - Spatial Haversine duplicate detection (`GET /reports/{id}/duplicates`) and duplicate linking (`POST /reports/{id}/duplicates/link`).
  6. **Frontend Experience**:
     - Upgraded `SubmitWizard.tsx` with dynamic category loading, GPS auto-detect, institution linkage, structured custom fields, observation date picker, AI auto-suggest helper, evidence media staging, local auto-save & recovery, and submission receipt.
     - Enhanced `ReportDetail.tsx` with evidence gallery, verification modal, trust progress indicator, duplicate candidate cards, timeline progression stepper, follow toggle, and threaded comments.
     - Tabbed "My Reports" & "Drafts" in `apps/web/src/app/[locale]/profile/page.tsx`.
- **Consequences:** 100% backend test pass rate across 161 tests; 100% frontend test pass rate across 22 tests; Next.js production build succeeds with 0 errors; clean structured civic data ready for analytics, AI, and resolution verification in subsequent phases.

## ADR-047: Geographic Intelligence, PostGIS Viewport Discovery, Map Provider Abstraction, and Spatial Clustering (Phase 9)
- **Status:** Accepted (Cycle 2, Phase 9)
- **Context:** The map in Theek Karo is a core discovery and civic-intelligence interface rather than a passive visual gadget. Citizens and analysts must explore India across all administrative hierarchy tiers (Country → State → District → Block → Panchayat/Municipality → Ward → Institution → Reports). Requirements: Multi-provider map abstraction (Leaflet/MapLibre/SVG decoupled), backend-driven PostGIS spatial calculations and viewport bounding box queries, dynamic spatial marker clustering, density heatmap layer without browser-side bloat, synchronized map and accessible list views, multi-entity forward and reverse geocoding, geographic aggregation summaries with honest data coverage percentages, and strict location privacy (never leaking private user/reporter personal coordinates).
- **Decision:**
  1. **Map Provider Abstraction & Spatial Intelligence**:
     - Decoupled GIS logic and map visualization from specific map vendors.
     - Viewport bounding-box queries (`GET /api/v1/gis/map/institutions`, `GET /api/v1/gis/map/reports`) with strict coordinate validation (-180..180, -90..90, max area 25 deg²).
     - Proximity search (`GET /api/v1/gis/map/nearby`) supporting Haversine/PostGIS radius querying across institutions and public reports.
  2. **Forward Geocoding & Multi-Entity Search**:
     - `GET /api/v1/gis/geocode/forward` resolving numeric coordinate pairs (`lat, lng`), administrative geography entities (`Jaipur District`), and public institutions (`Govt High School`).
     - Reverse geocoding (`GET /api/v1/gis/reverse-geocode`) mapping coordinates to containing administrative boundaries.
  3. **Aggregated Hierarchy Summaries & Data Coverage**:
     - `GET /api/v1/gis/map/summary` returning total institutions, total reports, open/in-progress count, verified/resolved count, severity breakdown, and data coverage percentage.
     - Neutral civic labeling ("Reported issues", "Reported issue density", "Verified resolutions") avoiding misleading bias.
  4. **Frontend Map & Exploration Interface**:
     - `MapExplore.tsx` featuring zoom/pan SVG projection, dynamic marker clustering, density heatmap radial overlay, keyboard navigation, accessible marker symbols (▲ critical/high, ◆ medium, ● low, 🏛 institution), and synchronized side-by-side (desktop) / bottom drawer (mobile) list view.
     - Upgraded `/map` page with live geocoding search, geographic hierarchy breadcrumbs (`India / State / District / ...`), layer toggles (Institutions, Reports, Heatmap), category/status filters, GPS "Find Near Me" geolocation, and URL search parameter state synchronization (`lat`, `lng`, `zoom`, `category`, `status`, `geography_id`).
- **Consequences:** All 167 backend tests passing; all 25 frontend tests passing; Next.js production build succeeds with 0 errors; full PostGIS and geographic intelligence layer operational for upcoming Phase 10 (Digital Twins & Public Institution Directory).

## ADR-048: Government Data Integration, Official-Source Comparison, Data Provenance, and Resource Intelligence (Phase 10)
- **Status:** Accepted (Cycle 2, Phase 10)
- **Context:** Citizens, authorities, and researchers need to understand what information is officially published about public institutions (schools, hospitals, police stations, courts, public works) and how that compares with what citizens observe on the ground. Core trust principles: Never present a citizen report as an official fact; never present an AI inference as an official fact; never present an outdated government dataset as current reality; and every data point must have end-to-end provenance. Discrepancies must be objective and non-accusatory. Connectors must enforce SSRF guards, CSV formula sanitization, and PII scrubbing.
- **Decision:**
  1. **Source Registry & Connector Abstraction**:
     - `GovernmentDataConnector` base interface (`validate_schema`, `normalize_record`, `extract_external_key`) with built-in adapters for UDISE+ (Schools), NHP (Hospitals), CCTNS (Police Stations), eCourts (Judicial), PMGSY (Public Works/Roads), and Generic JSON/CSV datasets.
     - Strict SSRF protection (`validate_source_url`) blocking loopback, link-local, cloud metadata (`169.254.169.254`), and private IPv4/IPv6 address spaces.
     - CSV formula injection sanitization (`sanitize_csv_cell`) escaping leading `=`, `+`, `-`, `@`, `\t`, `\r`.
     - PII masking (`scrub_pii`) protecting 12-digit Indian national ID / Aadhaar patterns before publishing canonical attributes.
  2. **Raw Data Ingestion, Staging & Time-Travel Versioning**:
     - Immutable raw payload storage (`gov_raw_payloads`) with deterministic SHA-256 digests.
     - Append-only dataset records (`gov_dataset_records`) supporting historical time-travel analysis ("What did the data say at that point in time?").
  3. **Multi-Signal Entity Matching & Admin Review Queue**:
     - Multi-factor entity matching algorithm (`match_institution_candidate`) combining exact official identifier matching (0.95), geographic boundary containment (0.90), and token-based name similarity (0.70+).
     - Categorization into `MATCHED`, `POSSIBLE_MATCH`, `CONFLICT`, and `UNMATCHED`.
     - Staging queue (`entity_match_reviews`) and admin review API (`/api/v1/govdata/entity-matches/{id}/review`) supporting `confirm`, `reject`, `reassign`, and `create_new`.
  4. **Rule-Based Discrepancy Engine**:
     - Objective comparison evaluating staffing (sanctioned vs working vs citizen reports), sanitation/toilets, drinking water availability, and power supply.
     - Nuanced discrepancy states (`NO_DISCREPANCY_DETECTED`, `POSSIBLE_DISCREPANCY`, `CONFLICTING_DATA`, `OUTDATED_OFFICIAL_DATA`, `INSUFFICIENT_DATA`, `UNDER_REVIEW`, `RESOLVED`).
     - Strictly enforced neutral civic terminology ("Possible discrepancy", "Recent citizen observations differ from published official figures", "Official dataset last published over 12 months ago") avoiding inflammatory or accusatory claims.
  5. **Data Provenance & Freshness**:
     - `ProvenanceDetail` tracking source organization, retrieval timestamp, dataset version, license, transformation version, and source link for every public attribute.
     - Dynamic freshness labeling ("Published 30 days ago", "Official benchmark active").
     - RAG document and text chunk preparation (`prepare_rag_document_chunks`) in `rag_documents` and `rag_chunks` for downstream vector search.
  6. **Frontend Comparative Digital Twin & Admin Workspace**:
     - `OfficialDataCard`: Visual representation of structured canonical indicators with source badges.
     - `DiscrepancyCard`: Side-by-side comparative resource matrix (Official vs Citizen vs AI) with community verification triggers.
     - `ProvenancePanel`: Source audit modal showing license, SHA-256 checksum, and portal link.
     - Upgraded `/institutions/[id]` Digital Twin with "Official vs Citizen Comparison" tab.
     - Upgraded public `/government-data` portal and created `/admin/government-data` administration workspace.
- **Consequences:** 100% backend test pass rate across 177 tests; 100% frontend test pass rate across 28 tests; Next.js production build succeeds with 0 errors; establishes a reliable, non-accusatory civic intelligence layer comparing official public data with community observations.

## ADR-049: AI Intelligence Layer, Grounded Hybrid RAG, Controlled Domain Tools, and Agentic Workflows (Phase 11)
- **Status:** Accepted (Cycle 2, Phase 11)
- **Context:** Transforming Theek Karo into an evidence-grounded civic intelligence system requires AI capabilities that assist users in discovering civic information, summarizing reports, detecting duplicates, classifying intake, translating across 14 Indian languages, and comparing official baselines with citizen reports. The system must adhere strictly to core safety principles: The LLM must NOT directly access the database or receive unrestricted credentials; the LLM must use controlled tools; the application must remain model/provider-neutral; AI inference must never be presented as official fact; every factual RAG response must carry citations; prompt injection defenses must isolate untrusted user inputs; and AI actions must remain bounded and read-only without autonomous mutation of authority records.
- **Decision:**
  1. **Provider Abstraction & Task-Aware Model Router**:
     - `LLMProvider` protocol decoupled from specific vendors, with built-in `StubLlmProvider` (deterministic, hermetic for dev/tests/CI) and `OpenAiCompatibleProvider` (targeting OpenAI, DeepSeek, Groq, local Ollama).
     - Centralized `ModelRouter` matching tasks (`chat_assistant`, `classification`, `duplicate_detection`, `institution_summary`, `translation`) with latency/cost requirements and token pricing estimations.
  2. **Prompt Safety & Injection Defenses**:
     - Centralized prompt registry in `tk_api.ai.prompts` with strict system boundary separation: `DEVELOPER_RULES`, `<retrieved_context>`, `<user_input>`, and `<report_content>`.
     - Automatic PII scrubbing (`redact_pii_from_prompt`) masking 12-digit Indian national ID / Aadhaar patterns and mobile phone numbers before prompts reach external models.
     - Mandatory "insufficient evidence" fallback policy preventing hallucinated government statistics.
  3. **Controlled Domain Tools & MCP-Ready Export**:
     - Allowlisted, read-only tools: `search_institutions`, `get_institution_details`, `search_reports`, `get_official_data`, and `get_discrepancies`.
     - `ToolRegistry` enforcing strict parameter validation, database session safety, and exporting standard Model Context Protocol (MCP) JSON schemas.
  4. **Access-Controlled Hybrid RAG Retriever**:
     - Hybrid retriever (`RagRetriever`) combining keyword frequency overlap, vector similarity, language filtering, and metadata scoping.
     - Pre-retrieval authorization levels (`PUBLIC`, `AUTHENTICATED`, `MODERATOR`, `ADMIN`) ensuring sensitive administrative data is never retrieved into public assistant contexts.
     - Verifiable citation items with dataset names, versions, publication timestamps, and snippet excerpts.
  5. **Agent Orchestrator & Audit Trails**:
     - `AgentOrchestrator` managing multi-turn conversations (`ai_conversations`, `ai_messages`) and bounded workflows (Civic Research, Report Classification, Duplicate Check, Institution Summary, Multilingual Translation).
     - Full operational audit logging in `ai_runs` with model IDs, prompt versions, input/output tokens, execution latency, and estimated USD costs.
  6. **Frontend Civic Assistant Experience**:
     - `CivicAssistantChat.tsx`: Interactive, responsive research assistant supporting 14 Indian languages, suggested query chips, interactive citation trays, source provenance modals, referenced entity cards, and feedback triggers (thumbs-up / thumbs-down).
     - Upgraded `/assistant` page with live research capabilities.
     - Typed frontend API client (`apps/web/src/lib/api/ai.ts`).
- **Consequences:** 100% backend test pass rate across 187 tests; 100% frontend test pass rate across 31 tests; Next.js production build succeeds with 0 errors; establishes a transparent, auditable, evidence-grounded AI intelligence layer.

## ADR-050: Metric Catalog, Analytics Aggregation Engine, and Decision Intelligence Layer (Phase 12)
- **Status:** Accepted (Cycle 2, Phase 12)
- **Context:** Transforming the platform into a production-grade decision intelligence system requires measurable, explorable analytics spanning all administrative hierarchies (National → State → District → Sub-division → Block → Panchayat/Municipality → Ward → Village/Locality → Institution → Report). The analytics layer must strictly distinguish Observed Data, Reported Data, Verified Data, Official Data, AI-Derived Data, and Calculated Metrics; avoid confusing claims ("2,000 infrastructure failures" vs "2,000 reports submitted, 1,420 verified"); eliminate ad-hoc metric calculations on the frontend; distinguish true ground resolutions from simple status changes; use robust statistical metrics (median and P90 rather than misleading averages); enforce small-cell privacy protection (< 5 count suppression for sensitive cuts); and guard against speculative political or corruption scoring.
- **Decision:**
  1. **Centralized Metric Catalog & Registry (`tk_api.analytics.catalog`)**:
     - Authoritative definitions for core platform metrics (`report_count`, `verified_report_count`, `open_report_count`, `resolved_report_count`, `verified_resolution_count`, `resolution_rate`, `verification_rate`, `median_resolution_hours`, `median_verification_hours`, `institution_coverage_pct`, `official_data_coverage_pct`, `discrepancy_rate`, `backlog_aging_buckets`, `ai_cost_usd`, `ai_token_volume`, `ai_feedback_positivity_pct`).
     - Explicit definitions, mathematical formulas, dimensional axes, data source provenance, refresh frequencies, and RBAC authorization tiers.
     - Public catalog discovery endpoint (`GET /api/v1/analytics/catalog`) providing transparency into platform methodology.
  2. **Analytics Query Engine & Time-Series Aggregations (`tk_api.analytics.service`)**:
     - High-performance, read-optimized SQL aggregation service supporting date range presets (`today`, `yesterday`, `7d`, `30d`, `90d`, `year`, `all`) with `Asia/Kolkata` timezone awareness.
     - Time-series trend generation (`get_report_trends`) grouping counts by day/week/month across Total, Verified, Resolved, and Critical volume.
     - Category rollups with nested issue-type breakdowns and percentage distributions.
     - Resolution analytics evaluating true resolution rates, community-verified fixes, reopened cases, and median/P90 resolution durations in hours.
     - Verification velocity & open backlog aging intervals (`0-7d`, `8-30d`, `31-90d`, `90+d`).
     - Multi-level geographic drilldowns aggregating child administrative boundaries.
     - Institution workload profiles and discrepancy counts.
     - Government data quality scorecard tracking source health, staleness, and pending entity matches.
     - AI operations telemetry summarizing token volume, estimated USD costs, latency percentiles, and model/task distributions.
     - Moderation queue size and queue aging distribution.
  3. **Data Export Engine & Small-Cell Privacy Protection**:
     - Streaming CSV and JSON export endpoint (`POST /api/v1/analytics/export`) with dynamic column generation and actor auditing.
     - Automatic small-cell suppression (< 5 thresholding) on sensitive dimensions to prevent individual de-anonymization.
  4. **AI Analytics Tools Integration**:
     - 4 read-only analytics tools added to Phase 11 Assistant (`tool_get_civic_metrics`, `tool_get_report_trend`, `tool_get_category_breakdown`, `tool_get_geographic_summary`).
  5. **Frontend Analytics Dashboards & Command Center**:
     - `KpiCard`: Accessible metric card with definition tooltip, formula, source tag, and trend indicator.
     - `TrendChart`: Accessible SVG time-series chart with series toggling and screen-reader data table.
     - `CategoryBreakdownChart`: Category distribution bars with expandable nested issue-type breakdown.
     - `AgingBucketChart`: Backlog aging distribution bars.
     - `ResolutionMatrix`: Resolution rate, median and P90 resolution hours, and verified resolution breakdown.
     - `DataQualityScorecard`: Source health, freshness badges, import telemetry, and discrepancy stats.
     - `AiOpsDashboard`: Token consumption, estimated USD costs, latency metrics, and user feedback positivity.
     - `ModerationBacklogView`: Verification backlog, queue age distribution, and high priority queue indicators.
     - `AnalyticsFilterBar`: Responsive filter bar for date presets, interval, and CSV/JSON exports.
     - Upgraded `/analytics` (Public Civic Analytics Dashboard) and `/admin` (Command Center).
- **Consequences:** 100% backend test pass rate across 197 tests; 100% frontend test pass rate across 37 tests; Next.js production build succeeds with 0 errors; establishes a transparent, methodologically rigorous, and privacy-preserving civic analytics layer.

## ADR-051: Department Registry, Civic Case Lifecycle, SLA Engine, Escalation and Resolution Workflow (Phase 14)
- **Status:** Accepted (Cycle 2, Phase 14)
- **Context:** MVP acceptance requires an institution representative to "commit and resolve with proof" (PRD §B.1), which demands a first-class department model — not the institution-twin overload — plus a case lifecycle with SLAs, escalation, and an independently reviewed resolution workflow. The platform must stay configurable (no India-specific hard-coding, PRD §E), remain privacy-safe for citizens, and keep every mutation auditable.
- **Decision:**
  1. **Department registry as its own module** (`tk_api/departments`) — `DepartmentType` → `Department` (with `DepartmentCategory` + per-category `JurisdictionScope`: full / geography / institution), `OrganizationVerification` (approval auto-creates `DepartmentUser` membership so verification and onboarding are one step), `DepartmentUser` roles `member | manager | reviewer`. Departments are deliberately decoupled from the institution digital twin (twin = data ledger about one institution; department = an accountable service entity with staff and case ownership).
  2. **Civic cases as a dedicated module** (`tk_api/cases`) with table name `cases` (deliberately not `civic_cases` — code uses `CivicCase`, a common ORM naming convention; tables named after the domain concept read naturally in SQL; consistency with `reports`/`posts`).
  3. **One role-gated FSM** (`cases/state.py`, 18 statuses, 40+ edges) — the single authority for transitions; API routes never branch on status literals; every edge validates permission + role + department scope; citizens never mutate a case directly — their agency is `CaseReopenRequest` (request → staff approve/reject with reason).
  4. **Data-driven SLA** — `SlaPolicy` rows matched by weighted score (department 8 / category 4 / issue type 2 / severity 1, default fallback); no department-specific SLA policies hard-coded, per PRD §E.1. Pause/resume accumulates `paused_seconds`; worker sweep (`evaluate_sla_due`, 60 s beat) is the only async entry; escalation engine is idempotent per `(case_id, level, status)` and capped at `EscalationRule.max_level`.
  5. **Independent resolution review** (`tk_api/resolution`) — submissions with evidence; reviewer must differ from submitter; decisions map to CHECK-bound statuses; verified closure records `resolution_verified_at` and exempts the SLA. Community confirmation (PRD §B.2) remains a future slot (`partially_verified` path) rather than blocking Phase 14.
  6. **Jurisdiction-scoped reads** — `_user_can_access_case`: department roles need membership of the case's primary department; staff roles bypass; reporter always reads; citizen lists are filtered to own reports; internal notes never appear on public timelines.
  7. **Timezone-robust clock math** — SQLite returns naive UTC datetimes while Postgres returns aware; `cases/sla.py` normalizes via `_as_aware()` before subtracting (fixes elapsed-time math under both engines without coupling to the DB driver).
- **Consequences:** 238 backend tests pass (9 dedicated Phase-14 API tests), ruff + mypy clean (127 source files), migration 0026 verified on real Postgres; frontend adds `/cases`, `/cases/[id]`, `/departments`, admin departments tab with tsc/eslint-clean new files, 37 vitest tests, and a green Next.js production build. The pre-existing 0022 revision id (33 chars) requires widening `alembic_version.version_num` to varchar(64) on older dev databases only. Remaining: community confirmation gate (PRD §B.2) as a follow-up phase.

## ADR-053: Community & Civic Participation Layer — Initiatives, Volunteers, Groups, Deterministic Badges (Phase 18)
- **Status:** Accepted (Cycle 2, Phase 18)
- **Context:** Phase 18 adds a civic participation layer (REPORT → DISCOVER → DISCUSS → VERIFY → COLLABORATE → VOLUNTEER → FOLLOW → ACT → RESOLVE → MEASURE) while the platform must remain non-partisan, evidence-based, privacy-respecting, safe, inclusive and transparent. Existing Phase 13 community surfaces (feed, comments, reactions, saves, follows, blocks, moderation) must be reused, not duplicated.
- **Decision:**
  1. **New module `tk_api/community/participation.py`** for initiatives, volunteers, groups and badges, reusing the existing `community` router prefix and moderation queue; no duplicate feed/notification/comment systems.
  2. **Initiatives** use a reviewed lifecycle Draft → Submitted → Review → Approved → Active → Completed → Archived; draft editing is initiator-only; moderator approval gates public visibility; observations are reviewed by organizers/moderators before counting as accepted evidence (community contribution, never platform verification).
  3. **Volunteer safety by construction** — profiles store only explicit preferences (languages, interests, categories, areas, skills, availability); no phone, address or exact location columns exist; the only joinable surface is an opportunity with capacity; no public attendee lists; `my_status` is viewer-scoped.
  4. **Groups** are request → moderator-review → active; roles Owner/Moderator/Member; platform safety rules always override group rules; owner cannot be removed or banned.
  5. **Badges are deterministic** — `_badge_metrics` reads auditable tables only (reports, evidence, approved data-correction requests, comments, volunteer completions, initiatives led, helpful reactions); no AI-only awards; criteria are public via `GET /community/badges`; no competitive leaderboards.
  6. **Anti-abuse** — per-surface rate limits (initiative 10/h, opportunity 10/h, group 5/h per IP), capacity enforcement, IDOR guards (drafts hidden, ownership checks, organizer-only links), and existing moderation/reporting reuse.
  7. **AI community tools** are read-only and permission-guarded (`summarize_discussion`, `find_related_reports`, `recommend_public_initiatives`); matching uses explicit preferences only and never profiles participants.
- **Consequences:** 277 backend tests pass (13 dedicated Phase-18 tests), ruff + mypy clean, migration 0029 verified on real Postgres, OpenAPI snapshot regenerated; frontend adds `/community`, `/community/guidelines`, `/initiatives`, `/volunteer`, `/groups` with tsc/eslint-clean new files, 37 vitest tests, and a green Next.js production build. Deferred to a later phase: community events, direct messaging, community tasks/micro-contributions, and knowledge-base contributions (all designed but not built).

## ADR-054: PII Retention Enforcement (daily purge job) + permanent anonymized tombstones

- **Context:** DPDP requires data minimization and erasure. Civic content is
  retained as public interest, but time-limited PII (tokens, sessions,
  verification codes, security events, AI conversations, public API usage) had
  no automated deletion; account deletion only anonymized the user row.
- **Decision:** (1) `tk_api/core/retention.py` owns the retention windows
  (90 d refresh tokens, 180 d sessions, 30 d email verifications + password
  reset tokens, 365 d security events + public API usage, 90 d AI
  conversations); the worker runs `tk_worker.purge_expired_pii` daily (beat).
  (2) Deleted accounts become **permanent anonymized tombstones** — the row is
  kept with PII nulled because reports/comments reference `users.id` with mixed
  CASCADE/RESTRICT FKs; hard deletion would destroy civic content or be
  blocked. (3) Audit logs and consents are never purged (write-once / DPDP §6
  evidence).
- **Consequences:** `docs/PII-DATA-INVENTORY.md` is the authoritative inventory
  + retention table (keep in sync with the constants). Purge is idempotent,
  reports per-table counts, unit-tested (`tests/test_retention_purge.py`).
  Known gap: audit-log redaction tooling remains manual until a DPO is appointed.

## ADR-055: DR posture — multi-AZ prod DB, S3 versioning, Redis snapshots, PITR restore

- **Context:** production needed explicit RPO/RTO and a verified restore path;
  the media bucket had no versioning, prod RDS was single-AZ, and no restore
  test existed.
- **Decision:** prod RDS runs multi-AZ (`multi_az = environment == "prod"`,
  automatic failover, RTO ≈ 2 min for AZ loss); backups 7 d with PITR
  (RPO ≤ 5 min); media bucket gets versioning + 30 d noncurrent lifecycle;
  Redis keeps one daily snapshot (non-authoritative cache/broker). A real
  restore test (`tests/integration/test_backup_restore.py`) round-trips
  pg_dump → psql against compose Postgres. Full strategy + runbook:
  `docs/DISASTER-RECOVERY.md`.
- **Consequences:** RTO ≤ 1 h for logical restores, ≤ 30 min for media.
  Open items: cross-region replication deferred; dev-volume backup automation
  manual.

## ADR-056: Community confirmation on resolved cases — two-confirmer gate + reopen signals (Phase 15)

- **Status:** Accepted (Cycle 2, Phase 15)
- **Context:** PRD §B.2 requires "a second citizen confirms" before the MVP
  lifecycle reads Closed; the reviewer-approval gate from Phase 14 was an
  explicit stand-in (ADR-051). The reopen path must also surface community
  evidence that a "resolved" issue persists, without letting crowds drive
  case state.
- **Decision:**
  1. **Signals are review triggers, never auto-actions.** A `resolution_followup`
     (one per `(case, user)` — a DB unique constraint, so no double voting) is
     recorded for `observed_improvement` or `issue_still_exists`; posting one
     never transitions the case. `cases.community_confirmed_at` is the only
     durable side effect of the confirm gate; reopening always flows through the
     existing `CaseReopenRequest` machinery and the case FSM.
  2. **Two-confirmer gate** — `TK_RESOLUTION_CONFIRM_THRESHOLD` (default 2)
     distinct citizens confirming the improvement marks the confirmations
     `confirmed` and sets `community_confirmed_at`; the resolution reviewer
     then closes via the existing `resolved → closed` edge. The gate is
     deterministic (count of distinct users, reporter included) — no AI.
  3. **Reopen signal** — `TK_RESOLUTION_REOPEN_THRESHOLD` (default 3) distinct
     "issue still exists" signals create a pending `ResolutionReopenSignal`
     (aggregate count + earliest contributor); department members and the
     reporter are notified. A reviewer (`resolution.review`) approves → the
     case reopens through `request_reopen` + `review_reopen_request` (FSM +
     SLA restart); dismisses → stays closed. FSM-role pre-check returns a clear
     409 when a closed case needs an admin.
  4. **Endpoints under the report resource** — `POST/GET
     /reports/{id}/resolution-followups`; the GET returns aggregate counts and
     the caller's own signal only (no PII), gated by the report visibility rule
     (private reports 404 for outsiders). Reopen-signal review queue lives at
     `/resolutions/reopen-signals`.
  5. **Analytics truth moves to the case** — `verified_resolution_count` and
     `community_confirmed_count` in `/analytics/resolution` now read
     `cases.resolution_verified_at` / `cases.community_confirmed_at` (report
     statuses never carried closure state).
- **Consequences:** 307 backend tests pass (7 dedicated Phase-15 tests covering
  the gate, dedup 409, non-resolved 409, approve-reopens / dismiss-keeps-closed,
  private-report IDOR, analytics); ruff + mypy clean (138 source files);
  migration 0031 round-tripped on real Postgres; OpenAPI snapshot regenerated.
  Deferred: surfaced confirmation UI in the web app, and a "resolution
  follow-up signal" prompt surfaced to department dashboards (analytics can
  already read both counts).
