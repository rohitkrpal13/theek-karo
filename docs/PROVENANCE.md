# DATA PROVENANCE REGISTER (ADR-006/032)

Every external dataset in Theek Karo is documented here: source, license,
retrieval date, applicable scope, and honest status (ingested / candidate /
unavailable). Boundaries are ingested, never hand-drawn.

## Ingested (live DB)

| Dataset | Kind | Source | License | Version label | Rows | Retrieval |
|---------|------|--------|---------|---------------|------|-----------|
| India states/UTs | state | geoBoundaries gbOpen IND ADM1 (simplified) | CC-BY-4.0 | `IND-ADM1-2026.05` | 36 | 2026-08-16 (media.githubusercontent; LFS-aware) |
| India districts | district | geoBoundaries gbOpen IND ADM2 (simplified) | CC-BY-4.0 | `IND-ADM2-2026.05` | 735 (100% parent-linked to states by centroid containment) | 2026-08-16 |

Provenance chain: `external_sources` (name/publisher/url/license) →
`gis_boundary_versions` (label) → `gis_boundaries` (source_id + version_id on
every row); the API boundary detail surfaces the full chain.

## Dev fixture (clearly labeled, never presented as official)

| Dataset | Kind | Source | License | Rows | Note |
|---------|------|--------|---------|------|------|
| Synthetic schools (Jaipur/Udaipur points) | place | theek-karo dev fixture | test-only | 3 | exercises the `gis_places` ETL + boundary linking; NOT real directory data |
| Synthetic state+district polygons | boundary | theek-karo tests | test-only | (integration-only) | used by `tests/integration/test_gis_db.py` |

## Candidate sources (assessed, not yet ingested)

| Dataset | Source | License status | Blocker | Next action |
|---------|--------|----------------|---------|-------------|
| **Schools directory (pilot category)** | UDISE+ (Ministry of Education) via data.gov.in; geoBoundaries has no IND schools layer | Distribution unclear — UDISE+ terms require explicit reuse permission | Licensing clearance + API/structure mapping | Obtain clearance + export; ingest via `--places` ETL (ready) |
| Holiday/festival calendars, ward-level open maps | State portals | varies | Not required for M1 pilot | Reassess with campaign needs |

## Honest no-data statuses (ADR-006)

- **Wards (Jaipur MC / others)**: no licensed open-ward dataset identified for
  the pilot geography yet — ward boundaries stay OUT of the system until a
  licensed source is cleared (municipal partnership is the recommended path).
- **School enrollment / staffing micro-data**: only aggregated via UDISE+ —
  never pulled per-school until license + purpose alignment is documented.
- **Anything not ingested is shown as “no data”** in the product — never
  fabricated (report boundary assignment, reverse geocode, and map layers all
  degrade gracefully to empty).

## Refresh policy

- Version labels encode the source snapshot (`YYYY.MM`); re-running the ETL
  replaces that version's rows (idempotent), keeping full history rows in
  `external_sources` + `gis_boundary_versions`.
- Anyone can re-derive the register rows from `gis_boundary_versions` +
  `external_sources` — this document is the human-readable mirror.
