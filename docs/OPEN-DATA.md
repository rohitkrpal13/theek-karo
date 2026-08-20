# OPEN DATA

**Phase 23 — Open Data Portal, Licensing, Privacy, and API**

## Overview

The Open Data Portal allows public users to discover appropriate
non-sensitive datasets with full metadata, licensing, and methodology.

## Categories

| Category | Description |
|----------|-------------|
| `civic_reports` | Raw citizen-submitted reports |
| `verified_reports` | Reports that have been verified |
| `cases` | Department cases |
| `resolutions` | Resolved cases with evidence |
| `institutions` | Institution digital twins |
| `official_data` | Government-sourced datasets |
| `geography` | Geographic boundaries |

## Dataset Metadata

Every public dataset includes:
- **Name** and description
- **Publisher** and source
- **License** and license URL
- **Version** number
- **Record count**
- **Last updated** timestamp
- **Update frequency** (daily, weekly, monthly)
- **Freshness** label (fresh, recently_updated, may_be_outdated, stale)
- **Schema** description
- **Coverage** (geography, time period)
- **Methodology** explanation

## Licensing

Before publishing a dataset publicly:
1. Check source license
2. Check usage rights
3. Check privacy requirements
4. Check redistribution restrictions
5. Store license metadata
6. Show attribution requirements

## Privacy Filter

Before publishing, the system checks for:
- **PII**: Phone numbers, emails, names, addresses
- **Sensitive personal information**: Health, financial, legal data
- **Precise private locations**: Exact home addresses
- **Confidential records**: Internal government notes
- **Restricted information**: Classified or embargoed data

### Anonymization

Where appropriate:
- Remove direct identifiers
- Aggregate data
- Reduce geographic precision (to ~1 km)
- Suppress small groups (< 5 records)

### Small-Cell Protection

If an aggregation could identify individuals:
- Suppress or aggregate the data
- Especially for: health, education, legal, safety, vulnerable populations

## Downloads

Supported formats:
- **CSV** — Tabular data
- **JSON** — Structured data
- **GeoJSON** — Geographic data (where applicable)

Large datasets are generated asynchronously via export jobs.

## API

### Endpoints

```
GET /api/v1/public-data/datasets
GET /api/v1/public-data/datasets/{slug}
GET /api/v1/public-data/datasets/{slug}/records
POST /api/v1/public-data/datasets (admin)
PATCH /api/v1/public-data/datasets/{slug} (admin)
POST /api/v1/public-data/datasets/{slug}/versions (admin)
POST /api/v1/public-data/datasets/{slug}/export
GET /api/v1/public-data/methodology
GET /api/v1/public-data/coverage
GET /api/v1/public-data/freshness
```

### Rate Limiting

Public API endpoints apply rate limits:
- Read endpoints: 100 requests per minute
- Export endpoints: 5 requests per hour
- Write endpoints: require authentication

### API Keys

For programmatic access:
- Register an API key via the platform
- Keys are stored as SHA-256 hashes
- Support rotation, expiration, and revocation
- Usage is audited per key

### Pagination

All list endpoints support:
- `limit` (1-100, default 20)
- `offset` (default 0)

### Versioning

Public APIs are versioned: `/api/v1/...`
Breaking changes require a new version.
Deprecation notices are provided 6 months before removal.

## Attribution

Public datasets must show:
- Publisher name
- Source URL
- License
- Version
- Last updated date

Users should be able to cite a dataset:
```
Dataset Name
Version X.Y
Publisher: ...
Date: YYYY-MM-DD
URL: /open-data/datasets/{slug}
License: ...
```

## Methodology

Every public dashboard shows:
- Source attribution
- Date of data
- Methodology explanation
- Coverage scope
- Known limitations
