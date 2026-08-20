# DATA TRUST

**Phase 23 — Unified Data Trust, Provenance, Verification & Open Data Layer**

## Overview

Every important piece of information on Theek Karo answers:

- **WHO** provided it?
- **WHEN** was it provided?
- **WHERE** did it come from?
- **WHAT** evidence supports it?
- **HAS** it been verified?
- **WHO** verified it?
- **WHEN** was it verified?
- **HAS** the information changed?
- **WHAT** is the source?
- **WHAT** are the limitations?

## Architecture

```
DATA SOURCE
    ↓
INGESTION LAYER
    ↓
NORMALIZATION
    ↓
VALIDATION ENGINE
    ↓
PROVENANCE LAYER
    ↓
┌──────────┬──────────┐
│          │          │
↓          ↓          │
DATA QUALITY  VERIFICATION  │
│          │          │
└──────────┴──────────┘
    ↓
TRUSTED DATA
    ↓
┌──────────┬──────────┐
│          │          │
↓          ↓          │
ANALYTICS  PUBLIC DATA
│
↓
AI/RAG/MCP
```

## Core Tables

| Table | Purpose |
|-------|---------|
| `evidence_registry` | Central evidence tracking with type, source, uploader, integrity hash |
| `verification_records` | Append-only verification with method, decision, AI provenance |
| `data_quality_results` | Multi-dimensional quality scoring (7 dimensions) |
| `data_conflicts` | Source A vs source B conflict detection and resolution |
| `dispute_records` | Formal disputes with public banner support |
| `data_change_history` | Append-only change log with tamper-evident chain |
| `data_publication_snapshots` | Immutable quality metrics at publication time |
| `metric_definitions` | Centralized metric catalog with versioning |
| `data_quarantine_records` | Invalid imports held for review |
| `source_health_snapshots` | Periodic source health tracking |

## API Endpoints

All endpoints are under `/api/v1/data-trust/`.

### Evidence Registry
- `POST /evidence` — Register evidence (authenticated)
- `GET /evidence` — List evidence (public, with filters)
- `GET /evidence/{id}` — Get evidence details (public)

### Verification
- `POST /verifications` — Create verification record (authenticated)
- `GET /verifications` — List verifications (public, with filters)

### Data Quality
- `POST /quality` — Record quality check (admin/analyst/moderator)
- `GET /quality/{entity_type}/{entity_id}` — Get quality summary (public)

### Conflicts
- `POST /conflicts` — Detect conflict (admin/analyst/moderator)
- `GET /conflicts` — List conflicts (public)
- `PATCH /conflicts/{id}/resolve` — Resolve conflict (admin/analyst/moderator)

### Disputes
- `POST /disputes` — File dispute (authenticated)
- `GET /disputes` — List disputes (public)
- `PATCH /disputes/{id}/review` — Review dispute (admin/analyst/moderator)

### Provenance
- `GET /provenance/{entity_type}/{entity_id}` — Complete provenance chain (public)

### Change History
- `GET /history/{entity_type}/{entity_id}` — Change history (public)

### Dashboard
- `GET /dashboard` — Data quality dashboard (admin/analyst)

### Metrics
- `POST /metrics` — Create/update metric definition (admin/analyst)
- `GET /metrics` — List metric definitions (public)

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_evidence_record` | Evidence metadata for provenance lookup |
| `get_verification_history` | Verification history for an entity |
| `get_data_conflicts_for_entity` | Summarize conflicts for an entity |
| `get_disputes_for_entity` | Check active disputes |
| `get_source_health` | Source health and freshness status |
| `explain_provenance` | AI-powered provenance explanation |

All tools are READ_ONLY and permission-guarded.

## Design Principles

1. **Multi-dimensional quality**: No single trust score. Track authority, freshness, completeness, consistency, coverage, and provenance independently.

2. **Never silently resolve**: Conflicts show both values. Disputes create banners. Data is never overwritten without explicit review.

3. **Append-only audit**: Verification records, change history, and dispute records are append-only. Historical records are never destroyed.

4. **AI is advisory**: AI may assist with data quality analysis and provenance explanation but never makes verification decisions alone.

5. **Evidence hashing detects integrity, not truthfulness**: SHA-256 hashes detect if files have been changed, not whether the underlying content is truthful.

6. **Disputed data shows banners**: If a public record is disputed, it shows "Information is currently under review." It is never presented as fully verified.

7. **Original language preserved**: Evidence preserves original text and translation separately. Translations never replace originals.

## Worker Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `data_quality_sweep` | Daily 03:00 IST | Run quality checks across all active datasets |
| `source_health_snapshots` | Every 4 hours | Capture source health counters |
| `quarantine_review_check` | Daily 09:00 IST | Check quarantine backlog and notify stewards |
