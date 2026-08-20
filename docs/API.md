# API DESIGN

**Project:** Theek Karo
**Version:** 1.0
**Date:** 2026-08-14
**Status:** Approved (Phase 1) — endpoints land in Phases 2–9; health endpoints live since Phase 0

---

## 1. Conventions

- **Base path:** `/api/v1` (ADR-015). Ops endpoints (`/healthz`, `/readyz`) remain outside.
- **Transport:** HTTPS JSON. Request/response bodies validated by Pydantic v2 schemas.
- **JSON casing:** `snake_case` in payloads.
- **Datetimes:** ISO-8601 UTC (`2026-08-14T10:00:00Z`).
- **Coordinates:** `[longitude, latitude]` (GeoJSON order), WGS84.
- **Pagination:** cursor-based (`?cursor=...&limit=50`, max 100). `next_cursor` returned in
  responses; cursors are opaque.
- **Idempotency:** `Idempotency-Key` header (UUID) for create endpoints (report submission,
  media upload completion). Redis-backed; replay returns first result.
- **Validation errors:** RFC 9457 `application/problem+json` (ADR-014).
- **Rate limiting:** per-auth-identity + per-IP token bucket; `RateLimit-*` headers;
  burst allowances public endpoints (see SECURITY.md §5).
- **Auth:** `Authorization: Bearer <access_jwt>`; refresh via `POST /auth/refresh`.

## 2. Error Model (RFC 9457)

```json
{
  "type": "https://api.theekkar.in/errors/validation-error",
  "title": "Validation error",
  "status": 422,
  "detail": "3 field(s) failed validation",
  "instance": "/api/v1/reports",
  "errors": [
    {"field": "description", "reason": "must be at least 20 characters"}
  ]
}
```
Mapping: 400 malformed/domain, 401 unauthenticated, 403 forbidden, 404 not found,
409 conflict (state machine violation, duplicate), 422 validation, 429 throttled,
500/502/503 server-side (no internals leaked).

## 3. Auth & Users (implemented, Phase 3 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | public (rate-limited) | Phone/OTP or email+password; returns `verify_pending`, masked contact, `dev_otp_code` (console channel only) |
| POST | `/api/v1/auth/verify-otp` | public | Confirm phone/email OTP → first activation grants `citizen` role + tokens |
| POST | `/api/v1/auth/resend-otp` | public | New OTP honoring resend cooldown |
| POST | `/api/v1/auth/login` | public | Password → access + refresh JWT |
| POST | `/api/v1/auth/login-otp` | public | Issue login OTP to a registered active contact |
| POST | `/api/v1/auth/refresh` | refresh | Rotate refresh token; reuse detection revokes the whole family (ADR-008) |
| POST | `/api/v1/auth/logout` | any | Revoke refresh-token family |
| GET | `/api/v1/users/me` | bearer | Own profile + roles + masked contacts + consents |
| PATCH | `/api/v1/users/me` | bearer | Display name, locale (2-letter) |
| POST | `/api/v1/users/me/consents/revoke` | bearer | Revoke a consent purpose (`terms`/`data_processing`) |
| GET | `/api/v1/users/me/audit` | bearer | Own audit log (append-only, self-service transparency) |
| POST | `/api/v1/users/{user_id}/roles` | admin | Grant a role (`citizen`/`volunteer`/`official`/`admin`) |
| DELETE | `/api/v1/users/{user_id}/roles/{role}` | admin | Revoke a role (self-admin revocation blocked) |

Registration: phone (10-digit India numbers normalized to E.164 `+91…`) or email
(validated); password ≥ 8 chars (argon2id-hashed, never stored plaintext). Registering
with `consent: false` or an invalid `terms_version` is rejected. All auth endpoints are
rate-limited (per-IP and per-contact).

Login response:
```json
{"access_token": "...", "expires_in": 900, "token_type": "Bearer",
 "refresh_token": "...", "user": {"id": "uuid", "display_name": "...", "roles": ["citizen"]}}
```

Errors are RFC 9457 problem+json with semantic kinds, e.g.
`https://api.theekkar.in/errors/invalid_otp`,
`…/account_pending`, `…/token_reuse_detected`, `…/self_admin_revocation`, `…/consent_not_found`
(full catalog in the OpenAPI snapshot under `tests/contracts/`).

## 4. Civic Engine (implemented, Phase 4 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/civic/categories` | public | Active categories incl. `form_schema` + verification policy; `?include_inactive=true` is admin-only (403 otherwise) |
| GET | `/api/v1/civic/categories/{slug}` | public | Single category; admins see inactive ones too |
| GET | `/api/v1/civic/campaigns` | public | Campaigns by `?status=&boundary_id=&cursor=&limit=` (default 50, max 100); status filter: `planned|live|paused|closed` |
| GET | `/api/v1/civic/campaigns/{id}` | public | Campaign detail incl. `materialized_scope` |
| POST | `/api/v1/civic/categories` | admin | Create category (data-driven); 201 |
| PATCH | `/api/v1/civic/categories/{id}` | admin | Update category (versioned — see below) |
| POST | `/api/v1/civic/campaigns` | admin | Create campaign (status `planned`); 201 |
| PATCH | `/api/v1/civic/campaigns/{id}` | admin | Transition status / rescope; closed campaigns are immutable |

Category payload (subset):
```json
{"slug": "school", "icon": "school",
 "form_schema": {"type": "object", "required": ["class_rooms"], "properties": {"class_rooms": {"type": "integer"}}},
 "verification_policy": {"min_verifications": 2, "min_locale_diversity": 1},
 "attachment_rules": {"max_files": 4, "max_size_mb": 8, "mime": ["image/jpeg", "image/png", "image/webp"]}}
```

Rules:

- `slug` matches `^[a-z0-9_-]+$`; categories are keyed by slug, campaigns by UUID id.
- `form_schema` must be a JSON Schema of `type: object`; it and `verification_policy` are
  validated on write. `default_locale_keys` defaults to `{label_key: "category.<slug>", …}`.
- Category edits are versioned: changing `form_schema` or `verification_policy` bumps
  `form_schema_version` (reports reference the version they were submitted against — Phase 5).
- Campaign status machine: `planned → live|closed`, `live → paused|closed`,
  `paused → live|closed`, `closed` is terminal (reopen → 409 `/campaign_closed`);
  illegal transitions → 409 `/invalid_status_transition`.
- `scope` (`{boundary_id?, district?, state?}`) is materialized into
  `campaign_scopes` rows so `?boundary_id=` filtering works without JSONB queries.
- Slugs unique (409 `/slug_conflict`); missing entities → 404 (`/category_not_found`,
  `/campaign_not_found`); malformed ids → 422 (`/invalid_category_id`,
  `/invalid_campaign_id`, `/invalid_boundary_id`); empty PATCH bodies → 422
  `/empty_update`; write endpoints are rate-limited (civic bucket, 30/60s per IP).
- Seeded by default (`make seed-civic`, idempotent): 14 initial categories — `school`,
  `hospital`, `road`, `water`, `sanitation`, `public_transport`, `police_station`, `court`,
  `public_facility`, `panchayat`, `municipal_service`, `government_office`, `bridge`,
  `other` — with generic shared form schema / verification policy (per-category
  refinement arrives with Phase 5/12 data work).

## 5. Reports & Civic Intake (implemented, Phase 8 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/reports` | any | Create one-shot (idempotent via `Idempotency-Key`) |
| GET | `/api/v1/reports/{id}` | public | Detail incl. verifications, timeline, evidence, duplicate links |
| GET | `/api/v1/reports` | public | List: `?category_slug=&campaign_id=&institution_id=&issue_type_id=&status=&severity=&visibility=&boundary_id=&cursor=&limit=` |
| PATCH | `/api/v1/reports/{id}/fields` | reporter/admin | Edit non-location fields while `draft`/`submitted`/`needs_information` |
| POST | `/api/v1/reports/drafts` | authenticated | Create draft observation |
| GET | `/api/v1/reports/drafts` | authenticated | List current user's active drafts |
| PATCH | `/api/v1/reports/drafts/{id}` | reporter/admin | Update draft fields & location |
| DELETE | `/api/v1/reports/drafts/{id}` | reporter/admin | Delete draft |
| POST | `/api/v1/reports/drafts/{id}/submit` | reporter/admin | Convert draft into submitted public report |
| POST | `/api/v1/reports/{id}/media/upload-url` | reporter/admin | Reserve pre-signed upload slot for evidence |
| POST | `/api/v1/reports/{id}/media/complete` | reporter/admin | Verify upload and link to `report_evidence` |
| GET | `/api/v1/reports/{id}/media` | public | List evidence attachments |
| DELETE | `/api/v1/reports/{id}/media/{ev_id}` | reporter/admin | Remove evidence attachment |
| POST | `/api/v1/reports/ai/suggest` | any | Suggest-only AI intake (category, issue type, title, severity, hazard warnings) |
| GET | `/api/v1/reports/{id}/duplicates` | public | Spatial Haversine duplicate candidates |
| POST | `/api/v1/reports/{id}/duplicates/link` | citizen+ | Link duplicate candidate (`possible`/`confirmed`/`rejected`) |
| GET | `/api/v1/reports/{id}/verifications` | public | List community corroboration & refutation votes |
| POST | `/api/v1/reports/{id}/verifications` | citizen+ | Submit verification vote (`confirm`/`refute`/`needs_information`) |
| POST | `/api/v1/reports/{id}/comments` | any | Threaded collaboration comment (`parent_id`) |
| GET | `/api/v1/reports/{id}/comments` | public | Comment thread list |
| POST | `/api/v1/reports/{id}/follow` | any | Follow notification updates (`all`/`status_only`/`none`) |
| DELETE | `/api/v1/reports/{id}/follow` | any | Unfollow |
| POST | `/api/v1/reports/{id}/transition` | per-state | Status transition: `{to_status, reason}` |
| GET | `/api/v1/reports/{id}/timeline` | public | Append-only status history |

Create request:
```json
{"category_slug": "school", "campaign_id": null, "title": "Broken classroom windows",
 "description": "Windows on ground floor are broken since May; sharp edges at child height.",
 "location": {"type": "Point", "coordinates": [75.7873, 26.9124]},
 "location_accuracy_m": 12, "fields": {"issue_area": "classroom"}, "media_ids": ["uuid"]}
```

Rules:

- `fields` is validated against the category's `form_schema` (JSON Schema via
  `jsonschema`); violations → 422 `/field_validation_failed`. `title`/`description`
  live on the report row; `fields` carries only category-specific data.
- Location is a GeoJSON `Point [lon, lat]` (WGS84); stores as PostGIS
  `POINT(4326)` (ADR-028). Campaigns must be open (`planned`/`live`/`paused`) —
  closed → 409 `/campaign_closed`; campaign/category mismatch → 422.
- `ticket_no` format `TK-YYYYMMDD-XXXXXX`, unique.
- Create is idempotent: same `Idempotency-Key` (UUID) replays the first response
  (200) without creating a second report; malformed keys → 422
  `/invalid_idempotency_key`.
- Verification: one vote per verifier (409 `/duplicate_verification`); the
  reporter cannot verify their own report (403 `/self_verification`); voting is
  open on `submitted`/`under_verification`/`resolved` (else 409
  `/verification_closed`). Trust score: +0.15 per confirm, −0.20 per refute
  (floor 0, cap 1). Auto promotion: first vote → `under_verification`; confirms ≥
  `verification_policy.min_verifications` (distinct verifiers) → `verified`.
- Transition map (actors per DATABASE.md §5): `draft→submitted` (citizen),
  `submitted→under_verification|verified` (volunteer), `→rejected` (volunteer,
  reason required), `under_verification→verified|rejected`, `verified→assigned`
  (official), `assigned→in_progress` (official), `in_progress→resolved` (official),
  `resolved→reopened|resolution_verified` (volunteer, reason for reopened),
  `reopened→assigned|in_progress|resolved` (official),
  `resolution_verified→closed` (admin), `*→duplicate_merged` (admin). Unknown
  target → 422 `/invalid_status`; illegal edge → 409
  `/invalid_status_transition`.

Create response (201): report with `ticket_no`, `status: "submitted"`,
`info_class: "CITIZEN_REPORT"`, `trust_score: 0`. With `TK_AI_AUTO_ANALYSIS=true`
the AI analysis is scheduled in a background task (worker replaces this in
Phase 8); the analysis becomes available via §6.

## 6. AI Analysis (implemented, Phase 6 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/reports/{id}/analysis` | public | Latest T4 annotation: summary, entities, suggested category, confidence, run meta, citations |
| POST | `/api/v1/reports/{id}/analysis/refresh` | reporter/admin | Re-run (versioned — old annotations preserved; audited `ai.analysis_refresh`) |
| GET | `/api/v1/ai/citations/{annotation_id}` | public | Citation detail w/ source provenance |
| GET | `/api/v1/ai/human-review-queue` | volunteer+ | Pending sensitive decisions (dup merge) |
| POST | `/api/v1/ai/reviews/{review_id}/decision` | volunteer+ | Approve (admin-only) / reject with reason (audited) |

Rules:

- Every AI response is wrapped with the T4 envelope (AI-ARCHITECTURE.md §7).
- The gateway is OpenAI-compatible against a DeepSeek-compatible endpoint with a
  fallback provider chain (ADR-017); without an API key the deterministic
  `stub` provider is used (dev/tests/eval). Every call is logged in `ai_runs`
  with provider/model/confidence/latency and a PII-insulated payload (ADR-019).
- Citations only ever reference rows in `external_sources` (ADR-006 — with no
  ingested sources the honest response is an empty citation list).
- Duplicates are only *suggested*: similarity ≥ `TK_AI_DEDUP_SIMILARITY_THRESHOLD`
  creates a pending `ai_reviews` row and flags the report `merged_by_ai`
  (ADR-018). Approving a merge (admin) sets `duplicate_of` and transitions to
  `duplicate_merged` (audited `ai.review.approve`); rejecting clears the flag
  (`ai.review.reject`).
- Eval harness (`make eval-ai`, `scripts/eval_ai.py`) runs the golden set against
  the provider and records metrics in `eval/metrics.json`; category accuracy must
  stay above 0.5 and duplicate similarity above the dissimilar baseline.

## 7. Media (implemented, Phase 5 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/media/uploads` | any | Request upload → `{media_id, upload_method, presigned_url?}` (idempotent) |
| PUT | `/api/v1/media/uploads/{id}/object` | any | Dev-mode direct upload (memory/local storage only) |
| POST | `/api/v1/media/uploads/{id}/complete` | any | Post-upload verify size/checksum, run scan gate, thumbnails |
| GET | `/api/v1/media/{id}` | owner | Metadata + presigned download URL (audited) |
| GET | `/api/v1/media/{id}/thumbnail` | public | Low-res JPEG preview for public reports |
| GET | `/api/v1/media/object/{bucket}/{key}` | — | Dev-mode read route (memory/local storage only) |

Upload flow: 1) client POSTs `/uploads` (returns a presigned PUT URL when backing
storage is MinIO/S3, else the dev API route), 2) client PUTs the bytes directly to
storage, 3) client POSTs `/uploads/{id}/complete` → the API verifies declared size
(409 `/size_mismatch`, `/upload_missing`), optional SHA-256 checksum (409
`/checksum_mismatch`), runs the scan gate (magic bytes + size — the ClamAV slot;
Phase 8 swaps in the real scanner, the gate contract stays), records dimensions,
generates a 640px JPEG thumbnail, and flips status `uploading` → `available` or
`failed`.

Rules:

- `mime_type` limited to `image/jpeg|png|webp` (422 `/unsupported_mime`); size
  bounded by `TK_MEDIA_MAX_SIZE_MB` (8, 422 `/invalid_size`).
- Upload request is idempotent via `Idempotency-Key` (200 on replay).
- Complete is replay-safe: a second `complete` returns the stored final state.
- Media whose scan result is not `clean` is `failed` and can never be served
  (GET → 409 `/media_failed`); junk content → 422 `/scan_failed`.
- `GET /media/{id}` is owner/admin-only (403 otherwise) and records
  `media.upload_request|complete|failed` in the audit trail (SECURITY.md §6);
  presigned URLs expire in 15 minutes.
- Production uses presigned URLs signed against the public S3 endpoint
  (SigV4-correct); dev uses API-backed routes for memory/local storage modes.

## 8. GIS & Geographic Intelligence (implemented, Phase 9 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/gis/map/institutions` | public | Viewport bounding box filter: `?min_lon=&min_lat=&max_lon=&max_lat=&type_id=&operational_status=&limit=` |
| GET | `/api/v1/gis/map/reports` | public | Viewport bounding box filter: `?min_lon=&min_lat=&max_lon=&max_lat=&category_slug=&status=&severity=&limit=` |
| GET | `/api/v1/gis/map/nearby` | public | Nearby discovery: `?lat=&lng=&radius_m=&domain=&category_slug=&limit=` (returns institutions + reports) |
| GET | `/api/v1/gis/map/summary` | public | Geographic hierarchy summary: `?geography_id=&boundary_id=` (counts, open/resolved, severity breakdown, coverage pct) |
| GET | `/api/v1/gis/geocode/forward` | public | Forward geocode: `?q=&limit=` (resolves coordinates, administrative geographies, institutions) |
| GET | `/api/v1/gis/reverse-geocode` | public | `?lat=&lng=` → address hint + boundary ids (finest first; not a legal record) |
| GET | `/api/v1/gis/boundaries` | public | Boundary tree by `?kind=&parent_id=&lat=&lng=` (point filter = polygons covering it) |
| GET | `/api/v1/gis/boundaries/{id}` | public | Geometry (GeoJSON) + provenance (`source_id`, source name/publisher/url/license, version label) |
| GET | `/api/v1/gis/proximity` | public | Reports near point: `?lat=&lng=&radius_m=` (1..100000, metres via geography cast) |

Rules:

- Viewport queries validate bbox coordinates (-180..180, -90..90, min ≤ max, area ≤ 25 deg²; 422 `/invalid_bbox`).
- Data is **ingested, never hand-drawn** (ADR-006): every boundary carries `source_id` + `version_id` FKs; detail surfaces the full provenance trail.
- Proximity distances are metres (geography cast); reports are excluded when soft-deleted.
- Forward geocoding is multi-entity (coordinates, administrative hierarchy nodes, public institution twins).
- Neutral civic labeling ("Reported issues", "Reported issue density", "Verified resolutions") avoiding misleading bias.

## 9. Notifications (implemented, Phase 8 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/notifications/preferences` | any | Channel × event-group preferences (defaults all enabled) |
| PATCH | `/api/v1/notifications/preferences` | any | Update prefs + per-channel quiet hours: `{"status_change": {"sms": false}}` or `{"collaboration": {"sms": {"enabled": true, "quiet_hours": {...}}}}` |
| GET | `/api/v1/notifications` | any | Own notification history (marks page read, returns `unread`) |
| POST | `/api/v1/notifications/receipts` | provider | Delivery status callback: `{notification_id, channel, status, provider_message_id?, error?}` |

Rules:

- Events (report status change, verification, comment, AI review) enqueue one
  row per channel **inside the action's transaction** — no event is notified
  unless the action commits. SMS/email deliver through the worker queue;
  in-app rows also write history immediately.
- Preference key is `event_group` (`status_change`, `collaboration`, `ai`) ×
  channel (`in_app`, `sms`, `email`); unknown keys → 422.
- Quiet hours (default 21:00–07:00 IST, per-user overrides) defer non-urgent
  SMS/email; in-app delivery is never delayed. Deferred rows re-queue ~12h.
- Templates are per event × channel × locale (hi/en), `{field}` payload
  interpolation; status change messages include a localized status label.
- Providers: console sandbox ships dev/test deliveries to the structured log
  (inspect via `docker compose logs worker`); the DLT-registered India SMS
  provider + transactional email

## 10. Geography Registry (implemented, Phase 5 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/geography/types` | public | List supported geographic hierarchy types (country, state, district, block, etc.) |
| GET | `/api/v1/geography` | public | Browse geographies by `?type_id=&parent_id=&country_code=&page=&limit=` |
| GET | `/api/v1/geography/{id}` | public | Geography detail with parent hierarchy and localized translations |
| GET | `/api/v1/geography/{id}/children` | public | Direct child geographies of a given node |
| GET | `/api/v1/geography/{id}/ancestors` | public | Ancestor chain up to root country level |
| GET | `/api/v1/geography/search` | public | Search geographies: `?q=&type_id=&limit=` |

## 11. Institutions Digital Twin (implemented, Phase 5 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/institutions/types` | public | List institution types (school, hospital, ward office, police station) |
| GET | `/api/v1/institutions` | public | Browse and filter institutions by `?type_id=&geography_id=&operational_status=&verification_state=&q=&page=&limit=` |
| GET | `/api/v1/institutions/{id}` | public | Institution digital twin detail with dynamic attribute values and translations |
| POST | `/api/v1/institutions` | official/admin | Create a new institution record (audited `institution.create`) |
| PATCH | `/api/v1/institutions/{id}` | official/admin | Update an institution record (audited `institution.update`) |

## 12. Unified Search (implemented, Phase 5 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/search` | public | Unified search across domains: `?q=&domain=all|reports|institutions|geography|categories&limit=` |

## 13. Government Data & Official-Source Comparison (Phase 10 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/institutions/{id}/official-data` | public | Structured canonical official metrics, operational status, and source provenance |
| GET | `/api/v1/institutions/{id}/discrepancies` | public | Objective rule-based discrepancy analysis across staffing, sanitation, water, and electricity |
| GET | `/api/v1/institutions/{id}/comparison` | public | Side-by-side comparative matrix (Official baseline vs Citizen observations vs AI note) |
| GET | `/api/v1/govdata/sources` | public | Approved government source registry with publication and retrieval freshness |
| GET | `/api/v1/govdata/sources/{id}` | public | Specific data source details |
| POST | `/api/v1/govdata/sources` | `admin`, `analyst` | Register new official data source in registry |
| POST | `/api/v1/govdata/imports` | `admin`, `analyst` | Trigger connector ingestion and entity matching job (dry-run or commit) |
| GET | `/api/v1/govdata/entity-matches` | `admin`, `analyst` | Staging review queue for low-confidence or conflicting record matches |
| POST | `/api/v1/govdata/entity-matches/{id}/review` | `admin`, `analyst` | Submit administrative review decision (`confirm`, `reject`, `reassign`, `create_new`) |
| GET | `/api/v1/govdata/data-quality` | `admin`, `analyst` | Platform data quality scorecard with coverage percentages |

## 14. AI Intelligence, RAG, Tools & Assistant (Phase 11 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/ai/chat` | public | Grounded multi-turn civic research assistant with citations and referenced entities |
| POST | `/api/v1/ai/classify-report` | public | Automatic report category/issue-type classification and missing info detection |
| POST | `/api/v1/ai/duplicate-check` | public | Semantic and spatial duplicate report analysis with confidence score |
| GET | `/api/v1/ai/institutions/{id}/summary` | public | Digital twin factual situation summary with citations and official freshness |
| POST | `/api/v1/ai/translate` | public | Multilingual civic translation preserving codes, URLs, and ticket numbers |
| GET | `/api/v1/ai/tools` | public | Allowlisted MCP-compliant tool specifications exporter |
| POST | `/api/v1/ai/feedback` | public | User feedback rating (+1/-1) and comments on AI-generated outputs |
| GET | `/api/v1/ai/admin/usage` | `admin` | AI token consumption, USD cost breakdown, latency, and task distribution |

Rules:

- The LLM never accesses the database directly; it accesses data via allowlisted domain tools (`tk_api.ai.tools`).
- Prompt injection defense isolates user queries and retrieved context in separate XML blocks (`<user_input>`, `<retrieved_context>`).
- Automatic PII scrubbing masks 12-digit Indian national ID / Aadhaar patterns and phone numbers before model dispatch.
- Every factual RAG answer includes citations with source dataset, version, publication date, and verbatim chunk snippet.

## 15. Civic Analytics, Dashboards & Decision Intelligence (Phase 12 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/analytics/overview` | public | High-level KPI cards with verified rates, denominators, and cataloged definitions |
| GET | `/api/v1/analytics/trends` | public | Time-series report volume trends (Total, Verified, Resolved, Critical) by day/week/month |
| GET | `/api/v1/analytics/categories` | public | Civic domain distribution and nested top 5 issue types with percentage share |
| GET | `/api/v1/analytics/resolution` | public | Resolution rate, verified community fixes, reopened counts, and median/P90 durations |
| GET | `/api/v1/analytics/verification` | public | Verification velocity and open backlog aging distribution (`0-7d`, `8-30d`, `31-90d`, `90+d`) |
| GET | `/api/v1/analytics/geography` | public | Multi-level geographic drilldown aggregating child administrative boundaries |
| GET | `/api/v1/analytics/institutions/{id}` | public | Institution-specific workload profile, resolution velocity, and discrepancy count |
| GET | `/api/v1/analytics/data-quality` | `admin`, `analyst` | Government data source health scorecard and entity reconciliation status |
| GET | `/api/v1/analytics/ai-ops` | `admin` | AI token consumption, USD cost breakdown, latency percentiles, and feedback positivity |
| GET | `/api/v1/analytics/moderation` | `moderator`, `admin` | Moderation triage queue size, high-priority counts, and queue aging distribution |
| POST | `/api/v1/analytics/export` | authenticated | Export analytics records in CSV or JSON with small-cell privacy protection |
| GET | `/api/v1/analytics/catalog` | public | Authoritative metric registry definitions, formulas, and dimensional axes |

Rules:

- Backend owns metric definitions (`tk_api.analytics.catalog.GLOBAL_METRIC_REGISTRY`). Frontend components must not invent independent formulas.
- Metrics strictly distinguish: Observed Data, Reported Data, Verified Data, Official Data, AI-Derived Data, and Calculated Metrics.
- Small-cell privacy protection suppresses granular cells with &lt; 5 records in sensitive dimensions to prevent individual de-anonymization.
- Bulk exports are audited with actor ID, timestamp, and filter boundaries.
- Pre-retrieval access control enforces data authorization (`PUBLIC`, `AUTHENTICATED`, `MODERATOR`, `ADMIN`).
- All AI operations are audited in `ai_runs` with token usage, USD cost calculations, model ID, latency, and prompt versions.

## 16. Departments, Civic Cases, SLA & Resolution (Phase 14 — live)

### 16.1 Department registry

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/departments/types` | public | Department type list (categorization taxonomy) |
| POST | `/api/v1/departments/types` | `admin`, `super_admin` | Create department type |
| PATCH | `/api/v1/departments/types/{type_id}` | `admin`, `super_admin` | Rename / edit type |
| DELETE | `/api/v1/departments/types/{type_id}` | `admin`, `super_admin` | Archive type |
| GET | `/api/v1/departments` | public | Public department directory (bare list, no envelope) |
| POST | `/api/v1/departments` | `super_admin` | Create department (returns `{id, slug}` only; jurisdiction scopes replace via `PUT`) |
| GET | `/api/v1/departments/{department_id}` | public | Department detail (includes `status`) |
| PATCH | `/api/v1/departments/{department_id}` | `admin`, `super_admin` | Update department (name, status, categories, scopes) |
| DELETE | `/api/v1/departments/{department_id}` | `super_admin` | Archive department |
| GET | `/api/v1/departments/me` | authenticated | Current user's memberships: list of `{department_id, department_name, role_in_department, …}` |
| POST | `/api/v1/departments/me` | authenticated citizen | Request organization verification (borrows no membership until approved) |
| POST | `/api/v1/departments/verifications` | `admin`, `super_admin` | Create (pre-approve) verification for a department |
| GET | `/api/v1/departments/verifications` | `admin`, `super_admin` | Verification queue (pending first) |
| PATCH | `/api/v1/departments/verifications/{id}` | `admin`, `super_admin` | Approve (`state=verified`) / suspend / revoke; approval auto-creates `DepartmentUser` membership |
| POST | `/api/v1/departments/{id}/members` | `admin`, `super_admin` | Add member with role (`member`\|`manager`\|`reviewer`) |
| GET | `/api/v1/departments/{id}/members` | authenticated (member) | List members |
| PATCH | `/api/v1/departments/{id}/members/{user_id}` | `admin`, `super_admin` | Change role / deactivate |
| DELETE | `/api/v1/departments/{id}/members/{user_id}` | `admin`, `super_admin` | Remove member (manager cannot demote self as sole manager) |

### 16.2 Civic cases (lifecycle, SLA, escalation)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/cases` | authenticated | List cases: internal roles see department-scoped cases (+ filters `status`, `primary_department_id`, `q`, pagination); citizens see own reports only |
| POST | `/api/v1/cases` | authenticated | Open case from a report (auto `TK-YY-xxxxxxxxxxxx` case number, both backfill + on-open) |
| GET | `/api/v1/cases/{case_id}` | authenticated (owner / dept member / staff) | Case detail + assignment history + status history |
| POST | `/api/v1/cases/{case_id}/assign` | manager / `admin` | Assign department (append-only history, `is_current` flag) |
| POST | `/api/v1/cases/{case_id}/assignments/{assignment_id}/complete` | manager / `admin` | Complete the current assignment; target goes Out for Comment / Closed, source stays Last Actioned |
| GET | `/api/v1/cases/{case_id}/timeline` | authenticated | Activity timeline: `{case_no, status, items[]}` with `type: "status_change"\|"response"` entries |
| POST | `/api/v1/cases/{case_id}/actions` | staff on case | Add action item (to-do) |
| PATCH | `/api/v1/cases/{case_id}/actions/{action_id}` | staff on case | Update action item (title, status `pending\|completed\|cancelled`) |
| GET | `/api/v1/cases/{case_id}/actions` | staff on case | List action items |
| POST | `/api/v1/cases/{case_id}/responses` | staff on case | Add response (public or internal note) |
| GET | `/api/v1/cases/{case_id}/responses` | member | List responses |
| POST | `/api/v1/cases/{case_id}/sla/pause` | `sla.manage` (admin) | Pause the SLA clock (accumulates pause seconds; resumption resumes) |
| POST | `/api/v1/cases/{case_id}/sla/resume` | `sla.manage` (admin) | Resume the SLA clock |
| GET | `/api/v1/cases/{case_id}/sla` | member | SLA detail (policy matched, deadline, pause history, status) |
| POST | `/api/v1/cases/{case_id}/escalate` | manager on case / `admin` | Manual escalation (level up, reason required); forbidden for non-members |
| GET | `/api/v1/cases/{case_id}/escalations` | member | Escalation history |

Rules:

- Non-internal roles can never mutate a case directly (citizen agency = `/reopen` below); all transitions are role-gated edges of the case FSM in `tk_api/cases/state.py`.
- Internal roles see only cases whose primary department they belong to (`super_admin`/`admin`/`moderator` bypass; reporter always reads).
- SLA policies score matches (department 8 / category 4 / issue type 2 / severity 1, default fallback) and are data-driven (`SlaPolicy`), never hard-coded; worker sweep (`evaluate_sla_due`, 60s beat) escalates breached clocks at max level 5, idempotent per `(case_id, level, status)`.

### 16.3 Resolution workflow

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/resolutions/{case_id}/submit` | staff on case | Submit resolution with evidence items (kind `photo\|before_after\|document`, document_kind, captured_at, checksum, visibility public/internal) → `resolution_under_review` |
| POST | `/api/v1/resolutions/{case_id}/review` | reviewer on case | Independent review: `verified` → case `resolved`; `more_evidence_required` \| `rejected` → `resolution_rejected`; `partially_verified` → `partially_resolved`; returns `{id, decision, submission_status}`; self-review forbidden |
| GET | `/api/v1/resolutions/{case_id}` | member | Current submission + review trail |
| POST | `/api/v1/cases/{case_id}/evidence` | staff on case | Append evidence to a rejected/more-evidence submission, then resubmit |
| POST | `/api/v1/cases/{case_id}/reopen` | reporter / staff | Reopen request: reporter asks, staff approve (`reopened`, reason required) or reject with reason |

### 16.4 Community confirmation on resolved cases (Phase 15 — live)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/reports/{id}/resolution-followups` | authenticated | Post one citizen signal on a verified resolution: `{signal: observed_improvement|issue_still_exists, observation?}`. One signal per (case, user) — repeat → 409 `/conflict`; case not resolved/closed → 409 `/case_not_resolved`; rate-limited 10/h per user; private reports → 404 |
| GET | `/api/v1/reports/{id}/resolution-followups` | public (visibility-gated) | Aggregate summary: `observed_improvement_count`, `issue_still_exists_count`, `distinct_contributors`, `community_confirmed_at`, caller's `my_followup`, `pending_reopen_signal` — no PII |
| GET | `/api/v1/resolutions/reopen-signals` | `resolution.review` | Review queue of aggregate "issue still exists" signals (`?status=pending|approved|dismissed`) |
| POST | `/api/v1/resolutions/reopen-signals/{id}/review` | `resolution.review` | `{decision: approved|dismissed, note?}` — approve reopens the case via the reopen-request machinery (FSM + SLA restart); dismiss keeps it closed; closed cases need an admin (409 `/reopen_not_permitted`) |

Rules:

- **Signals are review triggers, never auto-actions**: posting never transitions
the case. The two-confirmer gate (`TK_RESOLUTION_CONFIRM_THRESHOLD`, default 2)
sets `cases.community_confirmed_at` and marks confirmations `confirmed`; the
resolution reviewer then closes via `resolved → closed`. The reopen signal
(`TK_RESOLUTION_REOPEN_THRESHOLD`, default 3) marks follow-ups `escalated` and
queues a pending signal for human review; only an approved review reopens.
- Community agreement is not proof: counts are displayed as community signals,
never as platform verification; the reviewer/FSM owns closure decisions.

## 17. Ops & Probes (implemented, live)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` / `/health` | Liveness — process up, no dependency checks |
| GET | `/readyz` / `/ready` | Readiness — checks database connectivity; 503 problem+json when unreachable |
| GET | `/api/v1/version` | `{"service": "tk-api", "version": "0.11.0"}` |

## 18. Versioning & Backward Compatibility

- Breaking changes: new major (`/api/v2`) mounted in centralized registry `tk_api/api/v1.py` with documented migration window ≥ 6 months.
- Additive changes (new fields, new endpoints) are non-breaking; Pydantic models use forward-compatible defaults.
- Deprecation headers (`Deprecation: true; date=...`) on sunset endpoints.

## 19. Testing Contract

- Contract tests for all endpoints in `services/api/tests/contracts/openapi.snapshot.json`.
- Every endpoint documented here has: happy path, validation-error, auth-missing cases tested in CI.
- OpenAPI (FastAPI auto) is the source of truth; this doc is the design contract.

## 20. Frontend Client Integration (Phase 6–11)

The frontend application (`apps/web`) interfaces with the backend via modular TypeScript API clients in `apps/web/src/lib/api/`:
- `geographyApi`: Geographic hierarchy listing, drilldown, ancestors, and search.
- `institutionsApi`: Institutions directory, type lookup, digital twin details, and CRUD.
- `civicApi`: Civic categories, issue types, and focus campaigns.
- `reportsApi`: Report submission wizard, feed listing, timeline inspection, community verification, and comments.
- `gisApi`: Spatial viewport queries, proximity discovery, geocoding, and map summaries.
- `govdataApi`: Official data indicators, discrepancy items, comparative matrix, source registry, and admin match reviews.
- `aiApi`: Civic research assistant chat, classification, duplicate check, digital twin summary, translation, feedback, and usage statistics.
- `searchApi`: Multi-domain unified search.

All clients share standard token authorization headers, RFC 9457 error decoding via `ApiError`, abort signal handling for asynchronous component cancellation, and safe query string construction.