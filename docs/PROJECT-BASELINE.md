# PROJECT BASELINE

**Project:** Theek Karo
**Date:** 2026-08-14
**Author:** Principal AI Engineering Agent
**Status:** Phase 0 scaffold complete (2026-08-14) — see `IMPLEMENTATION-STATUS.md` for live status
**Verification:** Independently re-inspected on 2026-08-14 (repository scan, file glob, `git rev-parse`). Findings confirmed unchanged from baseline creation: one file (`docs/PROJECT-BASELINE.md`), one directory (`docs/`), no git repository, no application code. This document is a frozen snapshot of the pre-scaffold state; post-Phase-0 reality is tracked in `IMPLEMENTATION-STATUS.md`.

---

## 1. Repository Summary

| Item | Status |
|------|--------|
| Location | `/Users/rohitkumar/Documents/Projects/theek-karo` |
| Version control | None initialized (recommended: `git init` in Phase 0) |
| Application code | None |
| Existing folders | `docs/` (created as part of this baseline) |
| Existing packages | None |
| Existing dependencies | None |
| Existing tests | None |
| Existing CI/CD | None |
| Existing infrastructure | None |

This is a **greenfield project**. Every component listed below must be created.

---

## 2. Current Architecture

No architecture exists. The controller document specifies the target architecture:

- **Frontend:** Next.js + React + TypeScript, mobile-first responsive SPA/PWA
- **Backend:** Python + FastAPI + Pydantic (modular monolith with clean module boundaries)
- **Database:** PostgreSQL + PostGIS (geospatial queries, proximity, boundary maps)
- **Async:** Redis + Celery (or equivalent) for report ingestion, verification tasks, notifications
- **Storage:** S3-compatible object storage (photos, documents, evidence attachments)
- **AI:** DeepSeek-compatible AI gateway; RAG + vector search; tool calling; agentic workflows; MCP where genuinely useful
- **Infrastructure:** Docker; CI/CD; AWS or GCP
- **Observability:** OpenTelemetry; structured logging; metrics; tracing; alerting

---

## 3. Reusable Components

None exist locally. No internal code can be reused.

External, license-permissible components to consider later (not part of this phase):

| Component | Purpose |
|-----------|---------|
| Next.js / React / TS | Frontend framework |
| FastAPI / Pydantic | Backend API layer |
| PostgreSQL / PostGIS | RDBMS + geospatial |
| Redis / Celery | Workers + queues |
| MinIO / S3 SDK | Object storage (dev: MinIO; prod: AWS S3) |
| OpenTelemetry SDK | Tracing/metrics |
| pgvector | Vector search for RAG |
| OpenStreetMap Data / OGR | India region boundaries, GIS data sources |
| Geocoding | Indian addresses (e.g., Google Geocoding or OSM-based Nominatim) |

**Note on government data:** per the controller's Data Provenance principle, no government information (ward boundaries, school lists, hospital lists) may be hard-coded or fabricated. All such data must be ingested from documented sources with provenance metadata. This is a key architectural constraint.

---

## 4. Missing Components (all must be created)

### 4.1 Application
- Backend service (FastAPI) with modular boundaries:
  - `auth` — authentication/authorization
  - `users` — citizens, volunteers, officials, admins
  - `civic` — generic category/campaign manager (configurable, not hard-coded)
  - `reports` — report lifecycle (discover → understand → report → verify → collaborate → track → resolve → verify resolution → measure)
  - `gis` — geospatial engine (PostGIS)
  - `ai` — AI gateway (DeepSeek-compatible), RAG, provenance, confidence
  - `media` — attachment upload/storage
  - `notifications` — SMS/email/push/WhatsApp-style (India-first, e.g., Indian SMS providers)
  - `i18n` — Hindi, English, and regional Indian languages
- Frontend application (Next.js) — mobile-first civic UI
- Database migrations + seed infrastructure
- Redis/Celery workers

### 4.2 Cross-cutting
- Configuration/validation (Pydantic Settings)
- Structured logging + OpenTelemetry
- Error handling conventions
- Testing: unit, integration, contract, E2E (Playwright)
- Docker: `docker-compose.yml` for local dev (postgres+postgis, redis, minio, api, web, worker)
- CI/CD pipeline
- Security hardening (auth, rate limiting, media scanning, audit trail)

### 4.3 Source-of-truth documentation
- `/docs/PRD.md` — product requirements
- `/docs/ARCHITECTURE.md` — system architecture
- `/docs/DATABASE.md` — schema and data model
- `/docs/API.md` — API contracts
- `/docs/AI-ARCHITECTURE.md` — AI gateway, RAG, provenance, confidence
- `/docs/SECURITY.md` — security model
- `/docs/UX.md` — UX principles
- `/docs/I18N.md` — language/localization strategy
- `/docs/ROADMAP.md` — phased roadmap
- `/docs/DECISIONS.md` — architectural decision records (ADRs)
- `/docs/IMPLEMENTATION-STATUS.md` — live status of each phase

Only `PROJECT-BASELINE.md` exists so far; the remaining docs must be created during Phase 1.

---

## 5. Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | Scope creep — building all 14 civic categories at once | High | Configurable category/campaign engine; generic data model; add categories as data, not code |
| 2 | Fabricated government data | High | Data Provenance model; provenance fields on every external dataset; no hard-coded government info |
| 3 | AI hallucinations presented as fact | High | Explicit provenance + confidence + source tagging; human review for sensitive decisions; 5-tier information classification |
| 4 | Non-English users excluded | Medium | i18n from day one (Hindi first), RTL not required for Hindi; community translation workflow |
| 5 | Geospatial complexity (boundaries, pin accuracy) | Medium | PostGIS; bounded system for report location accuracy; human verification for sensitive geolocation |
| 6 | Abuse of report system (spam, fake reports) | Medium | Verification workflow; rate limiting; trust scoring; community verification |
| 7 | Low-internet users (India context) | Medium | Mobile-first, lightweight pages, lazy-loaded media, offline-tolerant UX where feasible |
| 8 | Secrets/keys leakage | High | Env-based config, secret manager, no keys in repo, CI secret scanning |
| 9 | Monorepo complexity | Low | Modest monorepo: `apps/` (web) + `services/` (api, worker) + `packages/` (shared) |

---

## 6. Recommended Implementation Sequence

The controller mandates phased development ("Theek Karo" lifecycle). Recommended order:

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| Phase 0 | Repository scaffold: git init, `.gitignore`, directory layout, lint/format/typecheck config, `docker-compose.yml` | Repo builds; services boot locally; lint/format pass |
| Phase 1 | Core docs: PRD, ARCHITECTURE, DATABASE, API, AI-ARCHITECTURE, SECURITY, UX, I18N, ROADMAP, DECISIONS, IMPLEMENTATION-STATUS | All source-of-truth docs present and consistent |
| Phase 2 | API skeleton: FastAPI app, health endpoints, config, structured logging, OpenTelemetry, error model, test harness | API boots; health + sample tests pass |
| Phase 3 | Auth + Users: registration, login, roles (citizen/volunteer/official/admin), JWT/session, RBAC, audit trail | Auth flows tested |
| Phase 4 | Civic engine: configurable categories/campaigns; PostGIS data model; migrations | Categories/campaigns are data-driven |
| Phase 5 | Report lifecycle core: create, verify, collaborate, track, resolve; media upload (S3/MinIO) | CRUD + state machine tests |
| Phase 6 | AI layer: DeepSeek-compatible gateway, provenance model, confidence scoring, RAG/vector search, tool calling, human-review workflow | AI endpoints tested; all outputs tagged with source/confidence/timestamp |
| Phase 7 | Web app: Next.js mobile-first UI for full lifecycle; accessibility; i18n (Hindi first) | UX flows usable on mobile |
| Phase 8 | Async + notifications: Celery workers, Redis, SMS/email/push integrations (India providers) | Notifications tested |
| Phase 9 | GIS features: boundaries, proximity search, maps for reports | Map features tested |
| Phase 10 | Observability, security hardening, load testing | Dashboards + alerts live |
| Phase 11 | CI/CD + production deployment (AWS/GCP), staging | Pipelines green |
| Phase 12 | Geo-political data ingestion with provenance (India region boundaries) | Datasets documented + ingested via ETL |

Each phase ends with: tests green, lint/typecheck green, docs + IMPLEMENTATION-STATUS updated, and a completion report.

---

## 7. Decision: Repo Layout (default pending approval in phase implementations)

```
theek-karo/
├── docs/                    # source of truth (this file lives here)
├── apps/
│   └── web/                 # Next.js frontend
├── services/
│   ├── api/                 # FastAPI backend
│   └── worker/              # Celery workers
├── packages/
│   └── shared/              # shared types/schemas (optional later)
├── infra/
│   ├── docker/              # docker-compose, Dockerfiles
│   └── terraform/           # cloud infra (later phase)
└── .github/workflows/       # CI/CD
```

---

## 8. Immediate Next Step

Initialize Phase 0 (repository scaffold) **only after the controller/user issues the next instruction**. No application code was written during this baseline task, per the current task constraints.