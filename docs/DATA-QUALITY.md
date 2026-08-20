# DATA QUALITY

**Phase 23 — Data Quality Engine**

## Overview

The data quality engine tracks multiple quality dimensions independently for
every dataset, record, or entity. It never replaces human judgment — it
provides signals for review.

## Quality Dimensions

| Dimension | What it checks |
|-----------|----------------|
| **Completeness** | Are required fields present and non-null? |
| **Validity** | Do values match expected types and ranges? |
| **Consistency** | Do values agree across related records? |
| **Uniqueness** | Are there duplicate records? |
| **Freshness** | How recently was the data updated? |
| **Coverage** | What geography, time period, or institutions are covered? |
| **Referential Integrity** | Do foreign keys resolve to valid records? |

## Quality States

| State | Meaning |
|-------|---------|
| `VALID` | All checks pass for this dimension |
| `PARTIALLY_VALID` | Some checks pass, some fail |
| `INVALID` | Critical checks fail |
| `INCOMPLETE` | Required fields are missing |
| `STALE` | Data is older than expected update frequency |
| `CONFLICTING` | Values disagree with other sources |
| `DUPLICATE` | Similar records detected |
| `UNVERIFIED` | Quality check not yet performed |

## Quality Score

Each dimension produces a score from 0.0 to 1.0:

- **0.95-1.0**: VALID
- **0.70-0.94**: PARTIALLY_VALID
- **Below 0.70**: INVALID or INCOMPLETE

## Overall Quality

The overall quality status is derived from dimension scores:

- If any dimension is INVALID or CONFLICTING → overall is CONFLICTING
- If any dimension is INCOMPLETE → overall is INCOMPLETE
- If any dimension is STALE → overall is STALE
- If all dimensions are VALID → overall is VALID
- Otherwise → PARTIALLY_VALID or UNVERIFIED

## Automated Checks

The `data_quality_sweep` worker task runs daily and checks:

1. **Completeness**: Percentage of non-null required fields
2. **Freshness**: Age of latest import job vs expected update frequency

## Manual Checks

Admins and analysts can record quality checks via `POST /api/v1/data-trust/quality`.

## Dashboard

The data quality dashboard (`GET /api/v1/data-trust/dashboard`) shows:
- Source counts (active, failed, stale)
- Dataset counts
- Conflict counts (total, open)
- Dispute counts (total, open)
- Evidence counts (total, verified)
- Verification counts
- Quarantined records

## Quality for AI

Before AI uses data, it should check:
- Source authority
- Data freshness
- Completeness
- Conflicts

AI should inform users when data is STALE, CONFLICTING, INCOMPLETE, or UNVERIFIED.
