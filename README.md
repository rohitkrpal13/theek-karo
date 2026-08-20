# 🇮🇳 Theek Karo (ठीक करो — Make It Right)

**India-first, AI-native civic intelligence platform.**

Discover, understand, report, verify, collaborate, track, resolve, and measure improvement of civic issues — with full provenance, community verification, and institutional accountability.

[![CI](https://github.com/rohitkrpal13/theek-karo/actions/workflows/ci.yml/badge.svg)](https://github.com/rohitkrpal13/theek-karo/actions/workflows/ci.yml)
[![Deploy](https://github.com/rohitkrpal13/theek-karo/actions/workflows/deploy.yml/badge.svg)](https://github.com/rohitkrpal13/theek-karo/actions/workflows/deploy.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Why Theek Karo?

Civic complaints in India are fragmented, unverifiable, and opaque. Nobody can tell what is true, who is fixing what, or whether anything improved. Theek Karo changes that:

| Complaint Portal | Theek Karo |
|---|---|
| One-way complaint intake | Two-sided: institutions respond with commitments and evidence |
| Anonymity by default, trust undefined | Every data point carries a declared provenance + confidence tier |
| Static categories | Categories are configurable data, evolving with the country |
| Closed after "resolved" | Permanent, auditable, community-verifiable lifecycle |
| Per-department silos | One graph: issue → institution → geography → analytics |

**AI handles the mundane forever-load**: classifying, routing, detecting duplicates, translating across 15 Indian languages, extracting facts from images, suggesting severity, and drafting responses — always labelled AI, always human-reviewable.

## Key Features

- 🏛️ **Institution Digital Twins** — Provenance-typed ledger per institution with official + citizen data separated
- 📍 **Full Report Lifecycle** — 18 statuses from Reported → Closed with negative states and 409 guards
- ✅ **Community Verification** — Trust tiers (T1-T5) enforced at schema level
- 🗺️ **Maps & Analytics** — Markers, clusters, heatmaps; 7 metrics across 12 geographic levels
- 🌐 **15 Languages** — Hindi, English, Bengali, Telugu, Marathi, Tamil, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese, Urdu, Maithili + more
- 🤖 **AI Gateway** — Classification, deduplication, OCR, severity suggestion, RAG — all T4-labelled
- 🏢 **Departments & SLAs** — Data-driven SLA policies with automated escalation
- 🔒 **Security First** — RBAC, JWT auth, audit logs, append-only history, DPDP compliance

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CDN / WAF / TLS                     │
├──────────────────────┬──────────────────────────────────┤
│   Next.js 16 PWA     │      FastAPI Modular Monolith    │
│   (React 19 + TS)    │      (23 domain modules)         │
│   Port 3000          │      Port 8001                   │
├──────────────────────┴──────────────────────────────────┤
│                    Celery Worker + Beat                  │
├─────────────────────────────────────────────────────────┤
│  PostgreSQL 16    │  Redis 7    │  MinIO/S3              │
│  + PostGIS        │             │  (Object Storage)      │
│  + pgvector       │             │                        │
├─────────────────────────────────────────────────────────┤
│  AI Gateway → Model Router → Capabilities               │
├─────────────────────────────────────────────────────────┤
│  OpenTelemetry → Prometheus → Grafana                    │
└─────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy (async), Alembic |
| **Database** | PostgreSQL 16 + PostGIS + pgvector |
| **Cache / Queue** | Redis 7, Celery 5 |
| **Object Storage** | MinIO (dev) / S3 (prod) |
| **AI** | Gateway + model router, RAG, pgvector embeddings |
| **Observability** | OpenTelemetry, Prometheus, Grafana |
| **Infra** | Docker Compose (dev), Terraform (prod), GitHub Actions CI/CD |

## Repository Layout

```
apps/web/           Next.js frontend (PWA)
services/api/       FastAPI backend (modular monolith, 23 modules)
services/worker/    Celery workers (AI jobs, media, notifications)
packages/           Shared types/schemas (later)
infra/              Terraform, monitoring, load tests
docs/               Source-of-truth documentation
  ├── PRD.md              Product Requirements Document
  ├── ARCHITECTURE.md     System Architecture
  ├── SECURITY.md         Security Model
  ├── API.md              API Documentation
  ├── ROADMAP.md          Development Roadmap
  ├── DATABASE.md         Database Schema
  ├── I18N.md             Internationalization Guide
  └── ...                 (45+ documentation files)
```

## Local Development

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Node.js](https://nodejs.org/) 20+ (for frontend)

### Quick Start

```bash
# Clone the repo
git clone https://github.com/rohitkrpal13/theek-karo.git
cd theek-karo

# Start all services (Postgres, Redis, MinIO, API, Worker, Prometheus, Grafana)
make up

# Verify it's running
curl http://localhost:8001/healthz   # → {"status":"ok"}
curl http://localhost:8001/readyz    # → {"status":"ok","checks":{"database":"ok"}}
```

### Available Commands

```bash
# Services
make up              # Build and start all services
make down            # Stop all services
make ps              # Show running containers
make logs            # Tail service logs

# Database
make migrate         # Run Alembic migrations
make seed-civic      # Seed civic categories and hierarchy

# Testing
make test            # Run API unit tests
make test-integration # Run integration tests (requires: make up)
make load-test       # Run k6 SLO smoke tests

# Code Quality
make lint            # Ruff lint
make format          # Ruff format
make format-check    # Check formatting (CI)
make typecheck       # Mypy strict type checking

# Frontend
make web-dev         # Start Next.js dev server
make web-lint        # Lint + typecheck frontend
make web-build       # Build frontend
make web-e2e         # Run Playwright E2E tests

# AI
make eval-ai         # Run AI evaluation suite
make ingest-adm1     # Ingest administrative boundary data

# Contracts
make update-contracts # Update OpenAPI snapshot
```

### Host Ports

| Service | Host Port | Container Port |
|---------|-----------|----------------|
| API | 8001 | 8000 |
| PostgreSQL/PostGIS | 5434 | 5432 |
| Redis | 6380 | 6379 |
| MinIO API | 9000 | 9000 |
| MinIO Console | 9001 | 9001 |
| Prometheus | 9091 | 9090 |
| Grafana | 3031 | 3000 |

### Without Docker

```bash
cd services/api
uv sync
uv run pytest        # Run tests against SQLite
```

## API Overview

The API serves everything under `/api/v1/`. Key resource groups:

| Endpoint | Description |
|----------|-------------|
| `POST /auth/otp/request`, `POST /auth/otp/verify` | OTP authentication |
| `POST /auth/register`, `POST /auth/login` | Account creation & password login |
| `GET /reports`, `POST /reports` | Report listing & creation |
| `GET /reports/{id}/timeline` | Append-only lifecycle history |
| `POST /reports/{id}/evidence` | Evidence upload (presigned) |
| `GET /institutions/{id}/twin` | Institution digital twin profile |
| `GET /geography/{kind}` | Hierarchy navigation |
| `GET /analytics/dashboard` | Metrics (7 KPIs × hierarchy levels) |
| `GET /search/reports` | Trigram + vector hybrid search |
| `POST /cases` | Civic case creation |
| `GET /departments` | Department directory |

Full API documentation: [`docs/API.md`](docs/API.md)

## Trust Model

Every piece of data on the platform carries a declared **provenance tier**:

| Tier | Label | Meaning |
|------|-------|---------|
| T1 | **Official** | Published by a government/institution account |
| T2 | **Community Verified** | Report + evidence satisfying verification policy |
| T3 | **Citizen Reported** | Citizen submission with identity, unverified |
| T4 | **AI Generated** | AI summary/insight — never self-promotes |
| T5 | **Unverified** | Anonymous data with no identity or evidence |

Trust tiers are enforced at the database level (CHECK constraints) and rendered in the UI for every data point.

## Deployment

### Cloud (AWS via Terraform)

```bash
cd infra/terraform
terraform init -var-file=staging.tfvars
terraform plan
terraform apply
```

Infrastructure includes ECS Fargate, RDS PostgreSQL, ElastiCache Redis, S3, CloudFront CDN, and monitoring.

Full deployment guide: [`docs/CLOUD-DEPLOYMENT-GUIDE.md`](docs/CLOUD-DEPLOYMENT-GUIDE.md)

### GitHub Actions CI/CD

- **CI** (`.github/workflows/ci.yml`): Lint, typecheck, test on every PR
- **Deploy** (`.github/workflows/deploy.yml`): Build & deploy to staging/prod on merge

## Documentation

The [`docs/`](docs/) directory contains 45+ source-of-truth documents:

| Document | Description |
|----------|-------------|
| [`PRD.md`](docs/PRD.md) | Product Requirements Document |
| [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System Architecture (v2.0) |
| [`SECURITY.md`](docs/SECURITY.md) | Security Model & Trust Boundaries |
| [`API.md`](docs/API.md) | API Documentation |
| [`ROADMAP.md`](docs/ROADMAP.md) | Development Roadmap (V0–V3) |
| [`DATABASE.md`](docs/DATABASE.md) | Database Schema & Design |
| [`I18N.md`](docs/I18N.md) | Internationalization Guide |
| [`AI-ARCHITECTURE.md`](docs/AI-ARCHITECTURE.md) | AI Gateway & Capabilities |
| [`VERIFICATION.md`](docs/VERIFICATION.md) | Community Verification System |
| [`COMPLIANCE-DPDP.md`](docs/COMPLIANCE-DPDP.md) | DPDP Act Compliance |
| [`SLOs.md`](docs/SLOs.md) | Service Level Objectives |
| [`ON-CALL.md`](docs/ON-CALL.md) | On-Call Runbooks |

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 0–12** | Cycle 1 baseline: auth, reports, AI, community, analytics, frontend | ✅ Complete |
| **Phase 13–14** | Departments, civic cases, SLA & resolution workflow | ✅ Complete |
| **Phase 15** | Community confirmation of resolutions | ✅ Complete |
| **Phase 16** | Search enhancement & performance | ✅ Complete |
| **Phase 17** | Data quality & retention | ✅ Complete |
| **Phase 18** | Reporting & analytics Phase 8 | ✅ Complete |
| **Cycle 2 Phase 1** | PRD v2.0 & enhanced features | ✅ Complete |
| **Cycle 2 Phase 2** | Architecture & security model v2.0 | ✅ Complete |
| **V1** | Verified community, 15 languages, official personas | 🔄 In Progress |
| **V2** | Multi-state, agentic assist, ML moderation | 📋 Planned |
| **V3** | National scale, federation, policy analytics | 📋 Planned |

Full roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following existing conventions
4. Run checks: `make lint && make typecheck && make test`
5. Commit with a descriptive message
6. Push and create a Pull Request

### Code Quality

- **Linting**: Ruff (Python), ESLint (TypeScript)
- **Type Checking**: mypy strict (Python), TypeScript strict (frontend)
- **Testing**: pytest (670+ tests), Playwright (E2E)
- **Formatting**: Ruff format (Python), Prettier (TypeScript)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">Built with ❤️ for India's civic future</p>
<p align="center">
  <a href="docs/PRD.md">PRD</a> ·
  <a href="docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="docs/API.md">API</a> ·
  <a href="docs/SECURITY.md">Security</a> ·
  <a href="docs/ROADMAP.md">Roadmap</a>
</p>
