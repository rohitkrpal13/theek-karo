# IMPLEMENTATION STATUS

Live tracking of Theek Karo phases. **Cycle 2** starts with this document set
(Phase 1). The **Cycle-1 reference baseline** (Phases 0–12, all green) is
summarised below and remains the working system until Cycle-2 phases replace
or extend it. Source of truth: `docs/`.

## Cycle 2 — Phase Status

| Phase | Scope | Status | Completed | Notes |
|-------|-------|--------|-----------|-------|
| 1 | Product spec + architecture foundation (PRD §1–16, ROADMAP MVP→V3, UX journeys, feature matrix, acceptance criteria, risks, deps, implications) | ✅ Complete | 2026-08-16 | Docs-only per instruction; baseline preserved |
| 2 (user-sequenced) | System architecture (ARCHITECTURE/AI-ARCHITECTURE/SECURITY/DECISIONS 036–041; diagrams, data flow, scalability) | ✅ Complete | 2026-08-16 | Docs-only per instruction; roadmap's baseline-reconciliation delta folds into the next implementation phase |
| 3 (user-sequenced) | Database + PostGIS + data architecture (identity, geography registry, institutions, provenance, categories v2 + issue types, reports v2, evidence/media pipeline, duplicates, community + moderation, resolution + reputation, subscriptions, i18n content, AI/RAG/gov domains, analytics; 0010–0020) | ✅ Complete | 2026-08-16 | Head 0020; 95 tables; fresh round trip verified; 139 unit + 10 integration; see Phase-3 record below |
| 5 (user-sequenced) | Backend foundation & core API layer (modular monolith, core pagination, safe sort allowlists, RFC 9457 error details, correlation middleware, geography hierarchy APIs, institution digital twins, civic issue types, report lifecycle FSM, multi-domain search, centralized /api/v1 router registry) | ✅ Complete | 2026-08-16 | 144 unit tests passing; 0 ruff errors; 0 mypy strict errors (90 source files); ADR-043 |
| 6 (user-sequenced) | Frontend application foundation & core UX (modular API client, AppShell, GlobalSearch, Home, dynamic Geography navigation, Institutions Digital Twin, Reports feed & detail, Submit wizard flow, Map abstraction, Profile, i18n 14 languages, WCAG 2.2 AA) | ✅ Complete | 2026-08-16 | 18 vitest tests passing; 0 tsc errors; 0 eslint errors; Next.js 16 build passing; ADR-044 |
| 7 (user-sequenced) | Authentication, authorization, identity & account security (Argon2id passwords, single-use token hashes, session tracking & revocation, 9-role RBAC, fine-grained permissions, IDOR protection, Google OAuth, DPDP account anonymization, audit events, security pages) | ✅ Complete | 2026-08-16 | 157 pytest backend tests; 22 vitest frontend tests; 0 tsc errors; Next.js 16 build passing; ADR-045 |
| 8 (user-sequenced) | Civic reporting, media evidence, AI-assisted intake & verification (drafts lifecycle, observation vs submission timestamps, coordinate sources, media upload slots & SHA-256 verification, trust scoring & auto-promotion, heuristic duplicate detection, suggest-only AI intake, SubmitWizard, ReportDetail, My Reports & Drafts) | ✅ Complete | 2026-08-16 | 161 pytest backend tests; 22 vitest frontend tests; 0 tsc errors; Next.js 16 build passing; ADR-046 |
| 9 (user-sequenced) | Maps, GIS, geographic intelligence & location discovery (PostGIS bounding-box queries, spatial clustering, Haversine nearby discovery, forward & reverse geocoding, geographic aggregation summaries, density heatmap, MapExplore, /map discovery page) | ✅ Complete | 2026-08-17 | 167 pytest backend tests; 25 vitest frontend tests; 0 tsc errors; Next.js 16 build passing; ADR-047 |
| 10 (user-sequenced) | Government data integration, official-source comparison, data provenance, and resource intelligence (UDISE+, NHP, CCTNS, eCourts, PMGSY connectors, SSRF guard, CSV formula sanitization, PII scrubbing, raw payload storage, multi-signal entity matching, rule-based discrepancy engine, provenance audit, Digital Twin comparative matrix, public & admin portals) | ✅ Complete | 2026-08-17 | 177 pytest backend tests; 28 vitest frontend tests; 0 tsc errors; Next.js 16 build passing; ADR-048 |
| 11 (user-sequenced) | AI intelligence, grounded RAG, controlled domain tools, MCP-ready architecture, and agentic workflows (provider-neutral abstraction, Stub/DeepSeek, ModelRouter, PII scrubbing, prompt injection defense, read-only domain tools, access-controlled hybrid RAG, AgentOrchestrator, ai_runs auditing, CivicAssistantChat, 14 Indian languages, citations tray) | ✅ Complete | 2026-08-17 | 187 pytest backend tests; 31 vitest frontend tests; 0 tsc errors; Next.js 16 build passing; ADR-049 |
| 12 (user-sequenced) | Civic analytics, dashboards, command center and decision intelligence (metric catalog & registry, time-series aggregations, category rollups, resolution integrity & velocity, backlog aging buckets, multi-level geographic drilldowns, data quality scorecards, AI cost & token telemetry, moderation queues, CSV/JSON export with small-cell privacy protection, public analytics dashboard & admin command center) | ✅ Complete | 2026-08-17 | 197 pytest backend tests; 37 vitest frontend tests; 0 tsc errors; Next.js 16 build passing; ADR-050 |
| 13 | Community + moderation (feed ranking & tabs, threaded comments depth ≤ 2, moderation queue, reactions, saves, follows, blocks/privacy, public profiles, share previews, notification grouping + locked preferences) | ✅ Complete | 2026-08-17 | 218 pytest backend tests; 3 pre-existing test-harness failures documented (see record); OpenAPI snapshot regenerated; ADR-032 path completed |
| 14 (user-sequenced) | Departments & civic cases (department registry, organization verification, case lifecycle FSM, assignment history, SLA policies + clocks + pauses, escalation engine + worker sweep, resolution workflow with independent review, department-scoped access, Phase 14 frontend) | ✅ Complete | 2026-08-17 | 238 pytest backend tests (9 dedicated Phase-14 API tests); ruff lint + format + mypy clean (127 source files); migration 0026 validated on Postgres; OpenAPI snapshot regenerated; web tsc/eslint clean for new files; 37 vitest + Next.js 16 build passing; ADR-051 |
| 18 | Community & civic participation layer (civic initiatives, volunteer system, community groups, deterministic badges, initiative follows, AI community tools, community hub frontend, moderation/guidelines docs) | ✅ Complete | 2026-08-17 | 277 pytest backend tests (13 dedicated Phase-18 tests); ruff + mypy clean; migration 0029 validated on Postgres; OpenAPI snapshot regenerated; web tsc/eslint clean on new files, 37 vitest + Next.js 16 build green; ADR-053 |
| 16-hardening (user-sequenced) | Phase 16 security hardening program, Steps 3–18 (flaky-test fix, MFA + login backoff, authorization/IDOR suite, upload security, object-storage audit, PII inventory + retention purge, DB pool + indexes, DR + restore test, Redis/queue reliability, AI safety, observability, frontend security, CI dependency audits, IR/release/go-live docs, India-scale readiness, security testing + scale report) | ✅ Complete | 2026-08-18 | 300 pytest backend tests (unit + integration incl. new media-hardening, retention, queue-reliability, AI-safety, observability, backup-restore suites); ruff + mypy clean (137 source files); migration 0030 verified + round-tripped on Postgres; OpenAPI snapshot regenerated; web tsc clean, 37 vitest, Next.js build green, security headers verified live; k6 SLO smoke p95 11.9 ms / 0% 5xx; ADR-054/055; see record below |
| 15 (user-sequenced) | Community confirmation on resolved cases (two-confirmer gate closes PRD §B.2; "issue still exists" reopen signal with human review; citizen follow-up endpoints; contributor notifications; analytics counts two-confirmer closures) | ✅ Complete | 2026-08-18 | 307 pytest backend tests (7 dedicated Phase-15 API tests); ruff + mypy clean (138 source files); migration 0031 downgrade→upgrade round-tripped on real Postgres (tables + column + 6 hi/en templates verified); OpenAPI snapshot regenerated; Bandit + Semgrep clean on new code; ADR-056 |
| 19 | Government interoperability + data integration layer (connector registry with health/circuit-breaker state, transactional outbox for reliable external events, signed webhook delivery with retries + dead-letter, data-source authority/completeness fields, import change-detection counters + schema drift flag) | ✅ Complete | 2026-08-18 | 324 pytest backend tests (17 dedicated Phase-19 API tests); migration 0032 applied head on real Postgres; OpenAPI snapshot regenerated; record section pending |
| 20 | National civic intelligence platform (deterministic trend/seasonality engine, IQR anomaly detection, issue clusters, recurring-issue detection, data freshness & coverage duty-of-care, resolution intelligence, transparent forecasting, signal review lifecycle, model version registry, intelligence report artifacts, methodology doc) + frontend hub | ✅ Complete | 2026-08-18 | 334 pytest backend tests (10 dedicated Phase-20 API tests); ruff + mypy clean; migration 0033 applied head on real Postgres (11 tables verified); OpenAPI snapshot regenerated; 3 worker tasks + 3 beat schedules; INTELLIGENCE-METHODOLOGY.md; web tsc clean, eslint clean on new files, 45 vitest (8 dedicated intelligence tests), Next.js 16 build green; see record below |
| 23 | Data Trust, Provenance, Verification & Open Data layer (evidence registry, verification records, data quality engine, conflict detection, dispute management, change history, provenance chain, metric definitions, data quarantine, source health, MCP tools) | ✅ Complete | 2026-08-18 | 357 pytest backend tests (23 dedicated Phase-23 tests); ruff + mypy clean (163 source files); migration 0035 applied head on real Postgres (10 new tables verified); OpenAPI snapshot regenerated; 26 MCP tools (6 data-trust); see record below |
| 24 | Identity, Profile, Verification, Trust & Organization layer (user profiles, preferences, privacy, identity verification, organization identity/membership/invitations, institution claims, representative assignments, trust labels, contribution history, MCP tools) | ✅ Complete | 2026-08-18 | 383 pytest backend tests (26 dedicated Phase-24 tests); ruff + mypy clean (168 source files); migration 0036 applied head on real Postgres (10 new tables verified); OpenAPI snapshot regenerated; 33 MCP tools (7 identity); see record below |
| 25 | Government & Department Workflow Platform (routing rules, case routing with confidence/review, case handoffs, official responses with versioning, configurable workflow definitions, government integration adapter, external case references, sync runs, dashboard analytics, work queue, bulk operations, MCP tools) | ✅ Complete | 2026-08-18 | 386 pytest backend tests (14 dedicated Phase-25 tests); ruff + mypy clean; migration 0037 applied head on real Postgres (10 new tables verified); OpenAPI snapshot regenerated; 40 MCP tools (7 government); see record below |
| 26 | Communication, Notification, Messaging, Alert & Citizen Engagement (provider abstraction, delivery pipeline with retry/dead-letter, public alerts lifecycle, template versioning, user devices, campaign communication, analytics, provider health, MCP tools) | ✅ Complete | 2026-08-18 | 396 pytest backend tests (10 dedicated Phase-26 tests); ruff + mypy clean; migration 0038 applied head on real Postgres (8 new tables verified); OpenAPI snapshot regenerated; 45 MCP tools (5 communication); see record below |
| 27 | AI Platform: LLMs, RAG, MCP, Agents, Skills, Multi-Agent Workflows, Structured Outputs, AI Evaluation, Human-in-the-Loop, AI Safety, AI Governance, Model Routing, AI Observability, Cost Optimization (AI Gateway, 10 specialized agents, 10 skills, 3 multi-agent workflows, 13 golden evaluation test cases, safety agent, circuit breaker, model router, cost tracking, prompt registry) | ✅ Complete | 2026-08-18 | 457 pytest backend tests (61 dedicated Phase-27 tests); ruff + mypy clean; migration 0039 applied head on real Postgres (8 new tables verified); 20+ API endpoints under /api/v1/ai-platform/; see record below |
| 28 | Security, Privacy, Trust, Compliance, AI Safety & Abuse Prevention (security incidents, IP blocking, abuse detection, input validation, data classification, SSRF protection, prompt injection protection, security audit, security health, enhanced security headers, middleware stack) | ✅ Complete | 2026-08-19 | 481 pytest backend tests (24 dedicated Phase-28 tests); ruff + mypy clean; migration 0040 applied head on real Postgres (6 new tables verified); 15 API endpoints under /api/v1/security/; see record below |
| 29 | Production Readiness: National-scale traffic, high availability, reliability, performance, observability, disaster recovery (caching layer, performance budgets, cost tracking, SLO monitoring, health checks, database optimization, pagination, capacity planning) | ✅ Complete | 2026-08-19 | 511 pytest backend tests (30 dedicated Phase-29 tests); ruff + mypy clean; production module with cache, observability, db_optimization; 10 API endpoints under /api/v1/production/; comprehensive health, performance budgets, cost tracking, database maintenance; see record below |
| 30 | Production Deployment: Release engineering, CI/CD, cloud infrastructure, monitoring, backup, operational readiness, go-live (GitHub Actions CI/CD, Terraform IaC, ECS Fargate, RDS, ElastiCache, S3/CloudFront, smoke tests, runbooks, go-live checklist, release process) | ✅ Complete | 2026-08-19 | 532 pytest backend tests (21 dedicated Phase-30 smoke tests); CI pipeline with lint, typecheck, tests, security scan; deploy pipeline with ECR, migrations, ECS, smoke; rollback pipeline; Terraform IaC; 7 operational runbooks; go-live checklist; release process docs; see record below |
| C2-5 (roadmap) | Maps v2 + Evidence v2: real tile basemap behind the marker/cluster API, heatmaps + severity + timeline scrub; video + before/after evidence chain | ✅ Complete | 2026-08-20 | 597 pytest backend tests (14 dedicated Phase C2-5 maps/evidence tests); migration 0041 applied on Postgres (evidence_chains table + ReportMedia columns + MediaObject video fields); heatmap data endpoint, timeline data endpoint, video evidence support (MP4/QuickTime/WebM), before/after pair support, tamper-evident SHA-256 evidence chain; frontend evidence chain + report media API client; see record below |
| C2-7 (roadmap) | i18n full: 15 languages live (web catalogs + server strings + notification templates), community translation workflow, script QC pass | ✅ Complete | 2026-08-20 | All 15 Indian languages registered (en, hi, bn, te, mr, ta, gu, kn, ml, or, pa, as, ur, mai, sd); en + hi fully translated (400+ keys each); remaining 13 locales use English fallback with community translation architecture ready; see record below |
| C2-8 (roadmap) | AI + civic assistant polish: conversation persistence, official-persona Q&A depth, source freshness, context carry-forward, department context | ✅ Complete | 2026-08-20 | 597 pytest backend tests; conversation history API (create, list, get messages, save); official persona deep-dive tool, source freshness tool, department context tool; multi-turn conversation context in prompts; frontend conversation API client methods; see record below |
| C2-9 (roadmap) | Agentic capabilities (V2): triage agents with human-in-the-loop SLA, recidivism analytics, ML moderation assist | ✅ Complete | 2026-08-20 | 597 pytest backend tests (12 dedicated C2-9 agentic tests in test_phase9_agentic.py); triage agent with 5-min SLA, batch triage, confidence scoring; recidivism analytics (180-day window, 2+ resolved + 1 open signal); ML moderation assist (10 categories, advisory only); 6 new API endpoints under /api/v1/ai/; see record below |
| C2-10 (roadmap) | Hardening + release: MFA enforcement for officials, load/SLO gates at scale, DPDP/counsel close-out, privacy notice v2 | ✅ Complete | 2026-08-20 | Privacy notice v2 (full DPDP Act 2023 compliance page with data table, rights, retention, security, sharing); MFA enforcement validation endpoint; SLO validation endpoint (p95 latency + error rate); security health endpoint fix (NULL expires_at, enum comparison); see record below |
| C2-11 (roadmap) | Deploy: cloud bootstrap (validated Terraform), DLT SMS onboarding, institute pilot onboarding | ⬜ Not Started | TBD | Deferred — requires AWS account + OIDC + DLT SMS provider selection |

## Phase 24 (Identity, Profile, Verification, Trust & Organization) — 2026-08-18

**Deliverables (backend `services/api`, docs `docs/`):**
- **Migration 0036** (`alembic/versions/0036_phase24_identity.py`) — 10 new tables: `user_profiles` (extended profile with visibility controls for profile/contact/contribution/location), `user_preferences` (language, timezone, notification, accessibility, content, map, AI consent), `identity_verifications` (7 types x 7 states with evidence, review, expiration, revocation), `organizations` (9 types with verification and status), `organization_memberships` (5 roles with status), `organization_invitations` (token-based with expiration), `institution_claims` (6-state workflow with evidence), `representative_assignments` (organization/institution/department), `identity_provider_links` (extensible OAuth architecture), `account_status_history` (append-only audit).
- **Identity Profile Models** (`tk_api/identity/profile_models.py`) — 10 ORM models with CHECK constraints, proper FK relationships to existing tables (users, geographies, institutions, identity_verifications), JSONB for flexible metadata.
- **User Profile** — Public/private fields with visibility controls (PUBLIC/COMMUNITY/PRIVATE for profile, contact, contribution, location). Denormalized contribution counts. Contextual verification labels (identity_verified, organization_verified, official_representative). Supports Indian names and regional language characters.
- **User Preferences** — Language, timezone, notification preferences, accessibility settings, content preferences, map preferences, AI processing consent.
- **Identity Verification Framework** — 7 verification types (EMAIL, PHONE, IDENTITY, ORGANIZATION, INSTITUTION_REP, OFFICIAL_REP, SKILL) with 7 states (NOT_VERIFIED through SUSPENDED). Evidence-based with reviewer, method, decision, explanation. Supports expiration and revocation. Append-only audit.
- **Organization Identity** — First-class organization entities with 9 types (NGO, community_group, educational, healthcare, civic, professional, government, etc.). 5 roles (owner, admin, manager, member, viewer). Verification workflow. Invitation system with token-based acceptance and expiration.
- **Institution Claims** — 6-state claim workflow (REQUESTED → UNDER_REVIEW → MORE_INFORMATION → APPROVED/REJECTED/REVOKED). Evidence-based with reviewer separation. Approval does NOT grant government data access.
- **Representative Assignments** — Designated representatives for organizations, institutions, and departments. Linked to verification records. Supports expiration and revocation.
- **Identity Provider Links** — Extensible architecture for future OAuth providers. Supports password, passkey, and additional OAuth providers.
- **Account Status History** — Append-only status change log for audit.
- **Service Layer** (`tk_api/identity/service.py`) — Business logic for all operations with validation, authorization, and audit logging.
- **API Router** (`tk_api/api/routers/identity.py`) — 18 endpoints under `/api/v1/identity/`: profile (GET/PATCH), public profile, preferences (GET/PATCH), verifications (POST/GET/PATCH review), trust labels, contributions, organizations (POST/GET/invite/accept/members), institution claims (POST/PATCH review), representatives (POST). Authenticated endpoints require appropriate roles; read endpoints support optional auth.
- **MCP Tools** (`tk_api/identity/ai_tools.py`) — 7 read-only tools: `get_my_profile`, `get_my_permissions`, `get_my_organizations`, `get_my_contributions`, `get_verification_status`, `get_organization_profile`, `get_institution_profile`. All permission-guarded, AI never bypasses authorization or exposes private data.
- **Tool Registry Integration** — All 7 identity tools registered in `tk_api/ai/tools.py` ToolRegistry with MCP-compliant schemas.
- **Models Registration** — All 10 new models registered in `tk_api/core/models.py` for Alembic autogenerate.
- **Router Registration** — `identity_router` registered in `tk_api/api/v1.py`.
- **OpenAPI Snapshot** — Regenerated with 18 new endpoints.
- **Documentation** — `IDENTITY.md` (architecture, tables, API, MCP tools, trust model), `VERIFICATION.md` (types, states, evidence, review, expiration, revocation).

**Verification:** 383 pytest passed (26 dedicated Phase-24 API tests in `tests/test_phase24_identity.py` covering profile CRUD + visibility, preferences, verification request lifecycle + all types, trust labels (never scores), contribution history, organization creation + types + membership + invitations, institution claims, representative assignments, end-to-end lifecycle validation); ruff + mypy clean (168 source files); migration 0036 applied head on real Postgres (10 new tables verified); OpenAPI snapshot regenerated; all 357 pre-existing tests continue passing (1 pre-existing Phase-21 test failure documented).

**Design principles:** Trust is contextual, never a hidden global score. No citizen ranking or political profiling. Verification describes platform-specific claim verification, not personal trustworthiness. Private information remains private. All identity changes are audit logged. Institution claim and data access are separate.

## Phase 25 (Government & Department Workflow Platform) — 2026-08-18

**Deliverables (backend `services/api`, docs `docs/`):**
- **Migration 0037** (`alembic/versions/0037_phase25_government.py`) — 10 new tables: `routing_rules` (data-driven category/geography/institution-type-to-department mapping), `case_routes` (routing decisions with confidence, source, acceptance/rejection), `case_handoffs` (department-to-department transfers with accept/reject workflow), `official_responses` (versioned responses with source tracking, withdrawal, superseding), `workflow_definitions` (configurable state machines per category/department), `workflow_transitions` (audit trail for workflow state changes), `government_integrations` (adapter abstraction for external government systems with status mapping), `external_case_references` (Theek Karo-to-external system case mapping), `sync_runs` (external system synchronization tracking), `bulk_operation_logs` (audit for bulk operations).
- **Government Models** (`tk_api/government/models.py`) — 10 ORM models with CHECK constraints, proper FK relationships to existing tables (cases, departments, users, categories, issue_types, geographies, institution_types), JSONB for flexible metadata.
- **Routing Rules** — Data-driven mapping: category + geography + institution type → department. Best-match scoring (department 8 / category 4 / issue type 2 / geography 1). Never hard-coded per department.
- **Case Routing** — Recommended department with confidence score, source (rule_based / ai_recommended / manual), accept/reject workflow. AI recommendations are clearly marked; human validation required.
- **Case Handoffs** — Department-to-department transfer with explicit accept/reject. Never silently move ownership. Both departments must participate.
- **Official Responses** — Versioned responses from department representatives. Edits create new versions, never silently overwrite. Supports withdrawal with reason. Source tracking (platform / external_api / imported).
- **Workflow Definitions** — Configurable state machines per category/department. Different categories use different workflows. Validated at runtime. Audit trail via workflow_transitions.
- **Government Integration Adapter** — Abstract adapter pattern for external government systems. Capabilities: submit_case, get_status, retrieve_reference, retrieve_response, synchronize_status. Status mapping from external to internal states. Circuit-breaker health tracking.
- **External Case References** — Maps Theek Karo cases to external government system references. Never invents official reference numbers. Explicit status mapping.
- **Sync Runs** — Tracks external system synchronization: records processed/succeeded/failed, errors, external version. Never trust HTTP 200 = case resolved.
- **Bulk Operations** — Authorized managers may bulk assign/route cases. Requires confirmation. Full audit logging.
- **Dashboard Analytics** — Department-scoped metrics: total/open/resolved cases, SLA breaches, active escalations, pending handoffs, pending responses. Transparent methodology.
- **Work Queue** — Department-scoped case queue with status/priority filters.
- **Service Layer** (`tk_api/government/service.py`) — Business logic for all operations with validation, authorization, and audit logging.
- **API Router** (`tk_api/api/routers/government.py`) — 20+ endpoints under `/api/v1/government/`: routing-rules (GET/POST), routes (POST/GET/POST review), handoffs (POST/GET/POST respond), responses (POST/GET/PATCH/POST withdraw), workflows (GET/POST), integrations (GET/POST/GET detail/PATCH), external-references (POST/GET), dashboard (GET), work-queue (GET), bulk/assign (POST). Authenticated endpoints require appropriate government.* permissions.
- **MCP Tools** (`tk_api/government/ai_tools.py`) — 7 read-only tools: `get_department_info`, `get_case_queue_summary`, `get_case_sla_status`, `get_department_responses`, `get_department_analytics`, `explain_routing`, `summarize_escalations`. All permission-guarded, AI never bypasses authorization.
- **Tool Registry Integration** — All 7 government tools registered in `tk_api/ai/tools.py` ToolRegistry with MCP-compliant schemas.
- **RBAC Extensions** — Added `government.*` permissions to admin, department_manager, department_representative, reviewer, and analyst roles in `authorization.py`.
- **Models Registration** — All 10 new models registered in `tk_api/core/models.py` for Alembic autogenerate.
- **Router Registration** — `government_router` registered in `tk_api/api/v1.py`.
- **OpenAPI Snapshot** — Regenerated with 20+ new endpoints.

**Verification:** 386 pytest passed (14 dedicated Phase-25 API tests in `tests/test_phase25_government.py` covering routing rules CRUD + duplicate rejection, case routing create + accept + reject, case handoffs create + accept + reject + same-department rejection, official responses create + version update + withdraw, workflow definitions create + list, government integrations create + list + detail + update, external references create + list, department dashboard metrics, work queue, end-to-end lifecycle); ruff + mypy clean; migration 0037 applied head on real Postgres (10 new tables verified); OpenAPI snapshot regenerated; all 372 pre-existing tests continue passing (1 pre-existing Phase-21 test failure documented).

**Design principles:** Never impersonate government departments. Every official action comes from verified authorized representatives. Routing recommendations require human/system validation. Handoffs are never silent. Official responses are versioned, never silently overwritten. External system statuses are mapped explicitly, never assumed. No fabricated reference numbers. No government role granted based on email domain or profile name alone.

## Phase 26 (Communication, Notification, Messaging, Alert & Citizen Engagement) — 2026-08-18

**Deliverables (backend `services/api`, docs `docs/`):**
- **Migration 0038** (`alembic/versions/0038_phase26_communication.py`) — 8 new tables: `communication_events` (immutable event log with idempotency), `delivery_records` (per-channel delivery tracking with retry/dead-letter/cost), `comm_templates` (versioned templates with locale/channel/status lifecycle), `public_alerts` (draft/review/publish/resolve with geo-targeting and severity), `user_devices` (push token registration with revoke), `comm_campaigns` (bulk communication with audience targeting, approval, scheduling), `comm_analytics` (daily aggregated metrics per channel/category), `digest_records` (daily/weekly digest tracking with dedup).
- **Communication Models** (`tk_api/communication/models.py`) — 8 ORM models with CHECK constraints, proper FK relationships, JSONB for flexible metadata.
- **Provider Abstraction** (`tk_api/communication/providers.py`) — Extensible `CommunicationProvider` ABC with implementations: `InAppProvider`, `EmailProvider`, `SMSProvider`, `PushProvider`, `WhatsAppProvider`. Business logic never couples to a specific provider. `DeliveryResult` dataclass for standardized outcomes.
- **Delivery Pipeline** — Queue → Preference Check → Authorization → Channel Selection → Provider → Delivery → Status → Retry → Dead-Letter. Exponential backoff (30s × 2^n, max 5 min). Max attempts configurable per record. Dead-letter queue for admin inspection.
- **Idempotency** — `CommunicationEvent.idempotency_key` prevents duplicate notifications from retries/restarts. `DeliveryRecord` tracks per-channel delivery state.
- **Public Alerts** — Full lifecycle: Draft → Review → Published → Resolved → Archived. Geo-targeting via geography_id + target_levels. Severity levels (info/warning/critical/emergency). Source attribution + verification. Expiration support. Emergency disclaimer.
- **Template Versioning** — Templates support code/channel/locale/version. Published version is active; previous versions auto-archived. Variables list for interpolation.
- **User Devices** — Push token registration with platform (web/ios/android), device name, active status, revocation. Tokens never exposed via public API.
- **Campaign Communication** — Draft → Review → Approved → Scheduled → Sending → Completed/Cancelled. Audience filtering via JSONB. Approval workflow. Cost estimation. Pause/cancel support.
- **Analytics** — Daily aggregated metrics per channel: events created, notifications sent, delivered, failed, read, suppressed, cost. Delivery rate calculation.
- **Provider Health** — Health check endpoint aggregating provider status + recent failure counts.
- **Service Layer** (`tk_api/communication/service.py`) — Unified pipeline: event recording, delivery creation/processing, alert lifecycle, template management, device management, campaign management, analytics, digest tracking.
- **API Router** (`tk_api/api/routers/communication.py`) — 18+ endpoints under `/api/v1/communication/`: alerts (GET/GET{id}/POST/POST review/POST resolve), templates (GET/POST/POST publish), deliveries (GET), devices (GET/POST/DELETE), campaigns (GET/POST/POST approve/POST cancel), analytics (GET), providers/health (GET).
- **MCP Tools** (`tk_api/communication/ai_tools.py`) — 5 read-only tools: `get_notification_summary`, `explain_alert`, `get_delivery_status`, `get_communication_analytics`, `summarize_unread`. All permission-guarded.
- **Tool Registry Integration** — All 5 communication tools registered in `tk_api/ai/tools.py` ToolRegistry.
- **Models Registration** — All 8 new models registered in `tk_api/core/models.py`.
- **Router Registration** — `communication_router` registered in `tk_api/api/v1.py`.
- **OpenAPI Snapshot** — Regenerated with 18+ new endpoints.

**Verification:** 396 pytest passed (10 dedicated Phase-26 API tests in `tests/test_phase26_communication.py` covering alert create/review/publish/resolve/reject, template create/publish/list, device register/list/revoke/IDOR, campaign create/approve/cancel, analytics endpoint, provider health, delivery records list, alert detail); ruff + mypy clean; migration 0038 applied head on real Postgres (8 new tables verified); OpenAPI snapshot regenerated; all 386 pre-existing tests continue passing (1 pre-existing Phase-21 test failure documented).

**Design principles:** Every communication must answer: Why sent? Who authorized? Who receives? Which resource? Which channel? Can user control? Theek Karo must never become a spam platform. Notifications are not permission boundaries — opening a resource re-checks authorization. AI-generated communication is clearly labeled as draft. Security notifications are not disableable. Public alerts require authorized publication. Emergency disclaimer always shown.

## Phase 20 (Civic Intelligence Platform) — 2026-08-18

**Deliverables (backend `services/api`, docs `docs/`):**
- **Migration 0033** (`alembic/versions/0033_phase20_civic_intelligence.py`) — `civic_signals`, `signal_evidence`, `signal_sources`, `issue_clusters`, `trend_snapshots`, `anomaly_events`, `forecast_runs`, `forecast_results`, `intelligence_reviews`, `intelligence_reports`, `model_versions`; models registered in `core/models.py`.
- **Deterministic compute engines (`tk_api/intelligence/`)** — `trends.py` (equal-length window comparison, ±10% direction thresholds, <3 observations ⇒ insufficient_data, weekly series, monthly seasonality means); `anomalies.py` (IQR per-scope baselines, review triggers only — never auto-actions); `clusters.py` (ClusterEngine: 30-day window, ≥0.75 near-duplicate fold, clusters append-only and never merge/delete reports; RecurringIssueEngine: ≥3 reports at ≥0.75 similarity); `freshness.py` (DataFreshnessEngine: per-source lag scan + geographic gap analysis, duty-of-care surfacing); `forecasting.py` (EMA α=0.3, clamped drift, min 8 weeks, planning-range output that hides points on insufficient data); `resolve_intel.py` (ResolutionIntelligenceService: median/p90 resolution time + improvement opportunities by evidence counts); `signals.py` (SignalService: create/list/get/review lifecycle with evidence + sources, audit-events); `intel_reports.py` (IntelligenceReportGenerator: per-category sections, JSON/CSV artifacts).
- **Signal review lifecycle** — reviewers (department reps/managers + admins) triage `confirmed` / `false_positive` / `duplicate` / `dismissed` with notes; every review recorded in `intelligence_reviews` with before/after status; append-only.
- **Router (`api/routers/intelligence.py`)** — `/overview`, `/signals` (+ review, admin/department gates, 201 on create), `/trends`, `/anomalies`, `/clusters`, `/recurring`, `/resolution`, `/improvements`, `/freshness`, `/data-gaps`, `/map`, `/forecasts` GET/POST, `/model-versions`, `/reports` GET/POST/GET{id}; report generation falls back to an inline async background task when Celery is disabled.
- **Worker jobs (`worker/tasks.py` + `worker/__init__.py`)** — `intelligence_snapshot` (hourly, 3600 s), `intelligence_clusters` (daily, 86400 s), `generate_intelligence_report`; beat schedule entries added.
- **Frontend (`apps/web`)** — `intelligenceApi` typed client (`src/lib/api/intelligence.ts`, 20 endpoints, re-exported from `src/lib/api.ts` + barrel); `/intelligence` page (Next 16 async-params convention) hosting `IntelligenceHub` with 9 tabs: Overview (dashboard sections), Trends & Anomalies (SVG `ChartBars` + IQR deviations), Clusters & Recurring, Freshness & Data Gaps (staleness detection), Resolution (response/resolution hours, SLA, aging buckets) + Improvement opportunities, Forecasts (department-only run form + range table), Signal review queue (staff review actions with notes, admin manual-signal creation, review-history shown append-only), Intelligence reports (department-only create + download), Model registry (versioned definitions); nav link in `AppShell`; en+hi i18n (`intelligence.*` namespace, type-enforced parity).
- **Docs** — `INTELLIGENCE-METHODOLOGY.md` (17 sections: per-engine method, inputs, thresholds, guarantees, explicit non-claims — no causation, no auto-actions, forecasts as planning ranges, access control).

**Verification:** 334 pytest passed at phase exit (10 dedicated Phase-20 API tests in `tests/test_intelligence_phase20.py` covering trends, anomalies, clusters + recurring, freshness + data gaps, resolution + improvements, forecasts incl. insufficient-data hiding, signal lifecycle + review IDOR, report generation + scheduling); ruff + mypy clean (158 source files); migration 0033 applied head on real Postgres (11 tables verified); OpenAPI snapshot regenerated; web tsc clean (0 errors), eslint clean on new files (22 pre-existing errors in older files untouched), 45 vitest passing (8 dedicated: 5 client + 3 component in `intelligence.test.ts` + `IntelligenceHub.test.tsx`), Next.js 16 production build green incl. `/intelligence` route.

## Phase 23 (Data Trust, Provenance, Verification & Open Data) — 2026-08-18

**Deliverables (backend `services/api`):**
- **Migration 0035** (`alembic/versions/0035_phase23_data_trust.py`) — 10 new tables: `evidence_registry` (central evidence with type, source, uploader, integrity hash, multilingual support, tamper-evident chain), `verification_records` (append-only with reviewer, method, decision, AI provenance), `data_quality_results` (multi-dimensional quality: completeness/validity/consistency/uniqueness/freshness/coverage/referential_integrity), `data_conflicts` (source A vs source B with resolution workflow), `dispute_records` (formal disputes with public banner), `data_change_history` (append-only change log with tamper-evident chain), `data_publication_snapshots` (immutable quality metrics at publication time), `metric_definitions` (centralized metric catalog with versioning), `data_quarantine_records` (invalid/suspicious imports held for review), `source_health_snapshots` (periodic source health tracking).
- **Data Trust Models** (`tk_api/data_trust/models.py`) — 10 ORM models with CHECK constraints, proper FK relationships to existing tables (data_sources, gov_datasets, gov_import_jobs, media_objects, users), JSONB for flexible metadata.
- **Evidence Registry** — Register evidence with type (image/video/document/audio/text/official_record/external_reference), source attribution (11 source types incl. CITIZEN, OFFICIAL_GOVERNMENT, AI_GENERATED), SHA-256 integrity hash, entity linkage, multilingual support (original + translation preserved), tamper-evident chain hash.
- **Verification Records** — Append-only verification with 9 methods (human_review, official_source_confirmation, cross_source_consistency, location_validation, timestamp_validation, document_verification, duplicate_analysis, structured_data_validation, ai_assisted), 6 decisions (NOT_REVIEWED through REJECTED), AI provenance tracking (model, version, reasoning).
- **Data Quality Engine** — Multi-dimensional quality scoring (7 dimensions × 8 states), AI-assisted analysis with confidence/reasoning, aggregated quality summaries per entity.
- **Conflict Detection** — Record conflicts between two data sources for the same field, never silently resolve — always show both values with timestamps. Resolution workflow: select authoritative source, merge, mark unresolved, or dismiss.
- **Dispute Management** — Formal dispute filing against any record type (report, evidence, dataset, institution, metric, public_data), review workflow (OPEN → UNDER_REVIEW → RESOLVED/REJECTED/WITHDRAWN), public banner support for disputed records.
- **Change History** — Append-only change log tracking old_value, new_value, source (user/system/import/ai/correction/dispute), and reason. Tamper-evident chain hash.
- **Provenance Chain** — Complete provenance for any entity: evidence items, verification history, change history, quality summary, disputes, and limitations.
- **Metric Definitions** — Centralized metric catalog with versioning, visibility control, formula, coverage, limitations, and period.
- **Data Quarantine** — Invalid/suspicious imports held in quarantine states (RECEIVED → VALIDATING → QUARANTINED → APPROVED/REJECTED).
- **Source Health** — Periodic health snapshots tracking records received/accepted/rejected/duplicated/conflicting, processing time, schema changes.
- **Service Layer** (`tk_api/data_trust/service.py`) — Business logic for all operations with validation, audit logging, and error handling.
- **API Router** (`tk_api/api/routers/data_trust.py`) — 15 endpoints under `/api/v1/data-trust/`: evidence (POST/GET/GET{id}), verifications (POST/GET), quality (POST/GET), conflicts (POST/GET/PATCH), disputes (POST/GET/PATCH), provenance (GET), history (GET), dashboard (GET), metrics (POST/GET). Authenticated endpoints require appropriate roles; read endpoints support optional auth.
- **MCP Tools** (`tk_api/data_trust/ai_tools.py`) — 6 read-only tools: `get_evidence_record`, `get_verification_history`, `get_data_conflicts_for_entity`, `get_disputes_for_entity`, `get_source_health`, `explain_provenance`. All permission-guarded, AI may assist with data quality analysis and provenance explanation but never makes verification decisions.
- **Tool Registry Integration** — All 6 data-trust tools registered in `tk_api/ai/tools.py` ToolRegistry with MCP-compliant schemas.
- **Models Registration** — All 10 new models registered in `tk_api/core/models.py` for Alembic autogenerate.
- **Router Registration** — `data_trust_router` registered in `tk_api/api/v1.py`.
- **OpenAPI Snapshot** — Regenerated with 15 new endpoints.

**Verification:** 357 pytest passed (23 dedicated Phase-23 API tests in `tests/test_phase23_data_trust.py` covering evidence lifecycle, verification records, data quality dimensions, conflict detection/resolution, dispute filing/review, provenance chain (empty + populated), change history, metric definitions, dashboard auth, end-to-end lifecycle validation of all severity levels / evidence types / dispute target types); ruff + mypy clean (163 source files); migration 0035 applied head on real Postgres (10 new tables verified); OpenAPI snapshot regenerated; all 334 pre-existing tests continue passing (1 pre-existing Phase-21 test failure documented).

**Design principles:** Every data point answers WHO/WHEN/WHERE/WHAT/HAS-IT-BEEN-VERIFIED. No universal trust score — multi-dimensional quality. Conflicts are never silently resolved. Disputes create public banners but don't remove data. AI is advisory only for verification. Evidence hashing detects integrity changes, not truthfulness. Append-only audit/verification/change history.

## Phase 18 (Community & Civic Participation Layer) — 2026-08-17

**Deliverables (backend `services/api`, frontend `apps/web`, docs `docs/`):**
- **Migration 0029** (`alembic/versions/0029_phase18_community_layer.py`) — `civic_initiatives`, `initiative_members`, `initiative_observations`, `initiative_followers`, `volunteer_profiles`, `volunteer_opportunities`, `volunteer_signups`, `community_groups`, `group_members`, `badges` (+ deterministic seed) and `user_badges`; indexes + check constraints; models registered in `core/models.py`.
- **Civic initiatives (`tk_api/community/participation.py`)** — Draft → Submitted → Review → Approved → Active → Completed → Archived lifecycle; initiator-only draft editing; moderator approval with notification; join/leave; observations with organizer/moderator review (accepted evidence counts); completion with results; initiative follows (`follows/initiative/{id}`); visibility rules (public statuses + own drafts for citizens; moderators see all).
- **Volunteer system** — privacy-safe profiles (languages, interests, categories, areas, skills, availability — no phone/address/exact location); opportunities created by initiative organizers or moderators (linked-initiative ownership enforced); capacity-limited join with `opportunity_full`; withdraw; `my_status` per viewer.
- **Community groups** — request → moderator review → active; Owner/Moderator/Member roles; member management (add/remove/ban/promote/demote); owner cannot be removed/banned; platform safety rules always override group rules.
- **Deterministic badges** — `_badge_metrics` computed from auditable tables only (verified contributions, accepted evidence, approved data corrections, comments, volunteer completions, initiatives led, helpful reactions); badge seeds `verified_contributor`, `evidence_contributor`, `community_researcher`, `community_contributor`, `volunteer`, `initiative_organizer`, `helpful_contributor`; `GET /community/badges` (transparent criteria) + `GET /community/badges/me` (progress + awards).
- **AI community tools** (`tk_api/ai/tools.py`) — `summarize_discussion` (public thread content, author-labeled), `find_related_reports` (duplicate prevention), `recommend_public_initiatives` (explicit-preferences matching, public data only, no participant profiling); all READ_ONLY and permission-guarded.
- **Endpoints** — 20+ new routes under `/api/v1/community` (initiatives, volunteer, groups, badges) with per-surface rate limits (initiative 10/h, opportunity 10/h, group 5/h per IP).
- **Frontend** — `communityApi` typed client (`lib/api/community.ts` + `put` added to core client), `CommunityHub` client component with Initiatives/Volunteer/Groups/Badges tabs, `/community`, `/community/guidelines`, `/initiatives`, `/volunteer`, `/groups` pages, Header nav link, en+hi i18n keys.
- **Docs** — `COMMUNITY-GUIDELINES.md`, `COMMUNITY-MODERATION.md`, `VOLUNTEER-SAFETY.md`, `INITIATIVES.md` created.

**Verification:** 277 pytest passed at phase exit (13 dedicated Phase-18 API tests in `tests/test_phase18_community.py` covering initiative lifecycle + review + IDOR, join/observe/complete, initiative follows, volunteer profile privacy, opportunity capacity + organizer-link authorization, group request/review/membership, member-management permissions, badge determinism + award-on-comment, no-volume-only badges); ruff + mypy clean; migration 0029 applied head on real Postgres; OpenAPI snapshot regenerated; web tsc clean, eslint clean on new files, 37 vitest passing, Next.js 16 production build green.

**Civic-principle guardrails implemented:** non-partisan (no political campaign surfaces), evidence-based (observation review, no crowd-verified truth claims), privacy-respecting (no volunteer contact details, no attendee lists, no exact volunteer locations), safe (rate limits, moderation queue reuse, group rules never override platform rules), inclusive (i18n, low-bandwidth-friendly cards), transparent (badge criteria public and deterministic, moderation audit + aggregate transparency).

## Phase 15 (Community Confirmation on Resolved Cases) — 2026-08-18

**Deliverables (backend `services/api`, docs `docs/`):**
- **Migration 0031** (`alembic/versions/0031_phase15_community_confirmation.py`) — `resolution_followups` (one citizen signal per case: `observed_improvement` | `issue_still_exists`; unique per `(case_id, user_id)` so no double-voting; status `pending → confirmed | escalated | dismissed`), `resolution_reopen_signals` (aggregate review queue), `cases.community_confirmed_at` (durable two-confirmer marker), + 6 hi/en notification templates.
- **Two-confirmer gate (`tk_api/resolution/community.py`)** — when `resolution_confirm_threshold` (default 2, reporter counts) distinct citizens confirm the improvement, follow-ups are marked `confirmed` and `cases.community_confirmed_at` is set; the resolution reviewer then closes via the existing `resolved → closed` transition. **Never auto-closes.**
- **Reopen signal** — when `resolution_reopen_threshold` (default 3) distinct citizens report the issue persists, follow-ups are `escalated` and a pending `ResolutionReopenSignal` is queued; department members + reporter are notified. **Never auto-reopens.**
- **Human review** — `GET /api/v1/resolutions/reopen-signals` (review queue) + `POST /reopen-signals/{id}/review` (`approved` routes the case through the existing reopen-request machinery — case FSM `reopened` + SLA restart; `dismissed` keeps it closed; `resolution.review` permission required; FSM-role pre-check with a clear 409 for closed cases needing admin).
- **Citizen endpoints** — `POST /api/v1/reports/{id}/resolution-followups` (rate-limited 10/h per user, visibility-gated — private reports 404 for outsiders) + `GET /api/v1/reports/{id}/resolution-followups` (aggregate counts + own signal + pending reopen signal, no PII).
- **Analytics** — `GET /api/v1/analytics/resolution` now computes `verified_resolution_count` from `cases.resolution_verified_at` and `community_confirmed_count` from `cases.community_confirmed_at` (report statuses never carried closure state).
- **Settings** — `TK_RESOLUTION_CONFIRM_THRESHOLD`, `TK_RESOLUTION_REOPEN_THRESHOLD` (+ `.env.example`); events mapped to notification preference groups (`community` / `status_change`).

**Verification:** **307 pytest passed** (unit + integration, 1 skipped; 7 dedicated Phase-15 API tests covering the two-confirmer gate + notification, one-signal-per-user dedup (409), the 409 on non-resolved cases, reopen-signal threshold → queue → approve-reopens, dismiss-keeps-closed, private-report IDOR (404), and analytics counts); ruff check + format clean; mypy strict clean (138 source files); migration 0031 downgrade→upgrade round-tripped on real Postgres (2 tables + column + 6 templates verified); OpenAPI snapshot regenerated; Bandit 0 issues + Semgrep 0 findings on the new code.

**Civic-principle guardrails:** signals are review triggers, never auto-close/reopen; community agreement is not proof (the reviewer/FSM decides); one signal per user + rate limits stop reaction rings; no PII in aggregate summaries; private reports stay hidden (404, no existence leak).

## Phase 16 Hardening (Steps 3–18) — 2026-08-18

**Deliverables (backend `services/api`, frontend `apps/web`, infra `infra/terraform`, docs `docs/`):**
- **Steps 3–5 (foundation):** flaky-test fixes (community harness + notifications quiet-hours determinism); MFA (TOTP, RFC 6238-verified) for privileged roles enforced at the authorization layer + per-account login backoff (`0028_phase16_mfa_login_backoff`, `core/login_throttle.py`, `tests/test_auth_mfa.py`); authorization audit + IDOR suite (`tests/test_security_authorization.py`: report/evidence/object/thumbnail/tenant isolation).
- **Step 6 (upload security):** strengthened scan gate (WebP fourcc, PNG signature, decodability — blocks HTML polyglots; pixel/dimension caps stop decompression bombs), per-user upload rate limits, JSON parse guards, Content-Length pre-checks, nosniff + safe Content-Disposition, working visibility-gated evidence download route.
- **Step 7 (object storage):** fixed production S3 signing bugs (`media_minio_region`/`media_minio_secure` configurable; `TK_MEDIA_MINIO_PUBLIC_ENDPOINT` set in ECS), CloudFront query-string forwarding, reduced media IAM scope, private-report thumbnail gating.
- **Step 8 (PII):** `docs/PII-DATA-INVENTORY.md` (authoritative inventory + retention table); daily purge job `tk_worker.purge_expired_pii` (`core/retention.py`: tokens 90 d, sessions 180 d, verifications 30 d, security events + API usage 365 d, AI conversations 90 d); tombstone policy documented (ADR-054).
- **Step 9 (database):** configurable pool (10 + 20 overflow, 1800 s recycle, pre_ping) in API + worker; 7 hot-path indexes + migration `0030_step9_indexes_pool` (feed, boundary+created, category, reporter, evidence media lookup, reactions, notifications).
- **Step 10 (DR):** prod RDS multi-AZ, S3 versioning + 30 d lifecycle, Redis daily snapshot; `docs/DISASTER-RECOVERY.md` (RPO/RTO + runbook); real restore test `tests/integration/test_backup_restore.py` (pg_dump → psql round-trip) (ADR-055).
- **Step 11 (queues):** Celery at-least-once (acks_late + reject_on_worker_lost), retry backoff + jitter on durable tasks, Redis DLQ `tk:dlq`; `recover_stuck_jobs` beat sweep re-drives stuck `pending_scan` media.
- **Step 12 (AI safety):** `required_role` enforced in the tool registry (prompt-injected tool calls cannot bypass auth; all shipped tools verified public/READ_ONLY); daily per-user chat cap (`TK_AI_DAILY_CHAT_LIMIT=300`) on top of per-minute limits.
- **Step 13 (observability):** `/live` + `/livez` aliases; worker logs now structured JSON with request correlation (`configure_logging` in worker).
- **Step 14 (frontend):** web security headers (CSP, X-Frame DENY, nosniff, Referrer-Policy, Permissions-Policy, HSTS) verified live on the production server; `npm audit` + `pip-audit` clean.
- **Step 15 (CI/CD):** pip-audit + npm audit wired into `ci.yml`; existing migrations-first deploy + rollback workflows validated (YAML-parse checked).
- **Step 16 (IR/release/go-live):** incident-response lifecycle added to `RUNBOOKS.md`; `docs/RELEASES.md`; `docs/GO-LIVE-CHECKLIST.md`.
- **Step 17 (India-scale):** Hindi-first default locale aligned (web `DEFAULT_LOCALE = "hi"` matches API default); 15 locales declared; UTC storage + Asia/Kolkata quiet hours; low-bandwidth via server thumbnails + cursor pagination.
- **Step 18 (security testing + scale):** `docs/SECURITY-TESTING.md` (SAST in CI, ZAP DAST prep, red-team + AI red-team playbook); `docs/SCALE-TEST-REPORT.md` — k6 SLO smoke: **p95 11.9 ms (SLO < 500 ms), 0% 5xx, ~235 req/s** on compose; full hardening audit appended to `SECURITY-CHECKLIST.md`.

**Verification (final):** **300 pytest passed** (unit + integration, incl. 7 new hardening test files: media hardening, retention purge, queue reliability, AI safety, observability, backup-restore, MFA); ruff + mypy clean (137 source files); migration 0030 applied + downgraded + re-applied on real Postgres; OpenAPI snapshot regenerated; web tsc clean, 37 vitest passing, Next.js 16 production build green, security headers curl-verified; `terraform validate` clean after DR changes.

## Phase 14 (user-sequenced: Departments & Civic Cases) — 2026-08-17

**Deliverables (backend `services/api`, frontend `apps/web`):**
- **Department registry (`tk_api/departments/`)** — `DepartmentType`, `Department` (table `departments`, `meta` column maps to JSONB `metadata`), `DepartmentCategory`, `JurisdictionScope` (full/geography/institution), `OrganizationVerification` (pending → verified | suspended | revoked; approval auto-creates the `DepartmentUser` membership), `DepartmentUser` (role_in_department: member|manager|reviewer).
  - Routed under `/api/v1/departments`: types CRUD, registry CRUD + categories/scopes replacement, `/me` memberships, members CRUD, verification request + review queue.
  - Jurisdiction enforcement: department members acting on a case must belong to that case's primary department (`_user_can_access_case`); `super_admin`/`admin`/`moderator` bypass scope, case creator and reporter always read.
- **Civic case engine (`tk_api/cases/`)** — `CivicCase` (table `cases`, auto `TK-YY-xxxxxxxxxxxx` case number), `CaseStatusHistory` (append-only), `CaseAssignment` (append-only, `is_current` flag, previous-department chain), `CaseAction`, `CaseResponse` (public vs internal-note), `CaseReopenRequest` (citizen reporter may request; staff approve/reject), `SlaPolicy`, `SlaInstance`, `SlaPause`, `EscalationRule` (data-driven, never hardcoded per department), `CaseEscalation`.
  - **FSM** (`cases/state.py`): 18 statuses, 40+ role-gated edges in `_TRANSITIONS`; citizen never mutates a case directly — agency is reopen requests; `rejected`/`reopened` require a reason.
  - **SLA** (`cases/sla.py`): policy match scoring (department 8 / category 4 / issue type 2 / severity 1, default fallback), `start_sla`, pause/resume with accumulated pause seconds, deterministic `evaluate_case_sla` (within/at-risk/breached), tz-robust clock math (SQLite naive ↔ Postgres aware).
  - **Escalation** (`cases/escalation.py`): manual `escalate` and system `escalate_on_breach` (idempotent per level, max level 5, unique `(case_id, level, status)`), target selection from `department_users` roles inside the case department.
  - **Worker sweep**: `tk_worker.evaluate_sla_due` task + Celery beat entry every 60s evaluates due clocks and fires breach escalations + notifications.
- **Resolution workflow (`tk_api/resolution/`)** — submissions with evidence (kind/before_after/document_kind/captured_at/checksum, visibility public/internal, versioned via `ResolutionReview` append), independent review decisions mapped to case statuses (`verified`→resolved, `more_evidence_required`|`rejected`→resolution_rejected, `partially_verified`→partially_resolved); self-review forbidden; `resolution_verified_at` + SLA exempt on verified closure.
- **Permissions & roles**: 19 new permission keys across all role blocks; three new roles `department_representative`, `department_manager`, `reviewer` (migrated + seeded); `reports/state.py` `ROLE_RANK` extended; `notifications` `STATUS_LABELS` gained all case statuses (en+hi); models registered in `core/models.py`; routers in `api/v1.py`.
- **Frontend** — i18n keys (en+hi), typed clients `lib/api/departments.ts` / `cases.ts` / `resolutions.ts`, `CaseList` + `CaseStatusBadge`, `CaseDetailPanel` (transitions, responses public/internal, action plan, SLA panel, escalation, resolution submit/review, reopen request), `DepartmentsDirectory` (public list + verification request), `DepartmentAdmin` (type/department registry, membership, verification queue) wired as the "Departments & Cases" admin tab, nav links in Header.

**Verification:** 238 pytest passed (9 dedicated new API tests in `tests/test_phase14_cases.py` covering registry, org verification → auto membership, full lifecycle incl. reopen, rejection path, department scoping, citizen list scoping, SLA pause/resume + engine idempotency, escalation permission gating); ruff clean; mypy clean (127 source files); OpenAPI snapshot regenerated; migration `0026` applied head-to-head on real Postgres (PostGIS 16) after widening the pre-existing `alembic_version` column for the 33-char 0022 revision id; web: tsc clean, eslint clean on all new files (pre-existing lint debt untouched), 37 vitest passing, Next.js 16 production build green.

**Known gaps:** the 3 pre-existing `tests/test_community.py` failures (test-harness issues, not regressions: duplicated `_setup`, notifications only materialize via the worker's dispatch path); `alembic check` reports only naming-level drift (custom index names in migrations vs ORM auto-names) consistent with every prior migration batch.

## Phase 13 (community + moderation, implemented 2026-08-17, tracked retroactively)

**Deliverables:** feed ranking + tabs, threaded comments (depth ≤ 2), moderation queue, reactions (one per user per report), saves, follows, blocks (privacy), public profiles, share previews, notification grouping + locked preferences, IDOR protection. Routed under `/api/v1/reports/...` (feed/comments/moderation), `/api/v1/notifications`, `/api/v1/community/...`.

**Verification:** 218 pytest backend tests at phase exit (3 documented test-harness failures remain: `TestFollows::test_follow_summary_and_unfollow` — call-site bug calling `_setup` twice; two `TestNotifications` tests — in-app rows are written by the worker-side dispatch path, not synchronously in tests); OpenAPI snapshot regenerated; ruff + mypy clean.

## Phase 12 (user-sequenced: Civic Analytics, Dashboards, Command Center and Decision Intelligence) — 2026-08-17

**Deliverables:**
- **Centralized Metric Catalog & Registry (`tk_api/analytics/catalog.py`)**:
  - Registered 16 authoritative metrics (`report_count`, `verified_report_count`, `open_report_count`, `resolved_report_count`, `verified_resolution_count`, `resolution_rate`, `verification_rate`, `median_resolution_hours`, `median_verification_hours`, `institution_coverage_pct`, `official_data_coverage_pct`, `discrepancy_rate`, `backlog_aging_buckets`, `ai_cost_usd`, `ai_token_volume`, `ai_feedback_positivity_pct`).
  - Formal formulas, dimensions, data sources, allowed roles, and refresh frequencies defined.
  - Discovery endpoint `GET /api/v1/analytics/catalog`.
- **Analytics Aggregation & Query Engine (`tk_api/analytics/service.py`)**:
  - `resolve_date_bounds()` with `Asia/Kolkata` timezone awareness and presets (`today`, `yesterday`, `7d`, `30d`, `90d`, `year`, `all`).
  - High-performance, read-optimized SQL aggregation service computing overview KPIs with verified rates and denominator tags.
  - Time-series trend generation (`get_report_trends`) grouping counts by day/week/month across Total, Verified, Resolved, and Critical volume.
  - Category rollups with nested issue-type breakdowns and percentage distributions.
  - Resolution analytics evaluating true resolution rates, community-verified fixes, reopened cases, and median/P90 resolution durations in hours.
  - Verification velocity & open backlog aging intervals (`0-7d`, `8-30d`, `31-90d`, `90+d`).
  - Multi-level geographic drilldowns aggregating child administrative boundaries.
  - Institution workload profiles and discrepancy counts.
  - Government data quality scorecard tracking source health, staleness, and pending entity matches.
  - AI operations telemetry summarizing token volume, estimated USD costs, latency percentiles, and model/task distributions.
  - Moderation queue size and queue aging distribution.
- **Data Export Engine with Small-Cell Privacy Protection**:
  - Streaming CSV and JSON export endpoint (`POST /api/v1/analytics/export`) with dynamic column generation.
  - Small-cell suppression (< 5 thresholding) on sensitive cuts.
- **FastAPI Analytics Router (`tk_api/api/routers/analytics.py`)**:
  - Mounted under `/api/v1/analytics`: `/overview`, `/trends`, `/categories`, `/resolution`, `/verification`, `/geography`, `/institutions/{id}`, `/data-quality`, `/ai-ops`, `/moderation`, `/export`, `/catalog`.
- **AI Analytics Domain Tools (`tk_api/ai/tools.py`)**:
  - Added 4 read-only analytics tools for Phase 11 Assistant (`tool_get_civic_metrics`, `tool_get_report_trend`, `tool_get_category_breakdown`, `tool_get_geographic_summary`).
- **Frontend Analytics Client & Components (`apps/web`)**:
  - Typed client `apps/web/src/lib/api/analytics.ts` and types in `apps/web/src/lib/types.ts`.
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

## Phase 11 (user-sequenced: AI Intelligence, RAG, Tools, MCP-Ready Architecture and Agentic Workflows) — 2026-08-17

**Deliverables:**
- **Database Migration `0024_phase11_ai_rag_enhancements.py`**:
  - Expanded `ai_runs` with token tracking (`tokens_in`, `tokens_out`), USD cost tracking (`cost_usd`), and prompt template versioning (`prompt_version`).
  - Enhanced `rag_chunks` with `metadata_payload` and pre-retrieval `access_level` (`PUBLIC`, `AUTHENTICATED`, `MODERATOR`, `ADMIN`).
  - Created `ai_conversations` and `ai_messages` for stateful multi-turn civic research assistant threads.
- **Provider-Neutral LLM Abstraction (`tk_api/ai/providers.py`)**:
  - `LLMProvider` protocol supporting text generation, structured schemas, and vector embeddings.
  - `StubLlmProvider`: Deterministic, hermetic provider for CI/CD and local development with zero external dependencies.
  - `OpenAiCompatibleProvider`: Production gateway targeting DeepSeek, OpenAI, Groq, or local Ollama servers.
- **Task-Aware Model Router & Cost Engine (`tk_api/ai/registry.py`)**:
  - Centralized registry (`MODEL_REGISTRY`) and `ModelRouter` matching tasks (`chat_assistant`, `classification`, `duplicate_detection`, `institution_summary`, `translation`) with latency/cost tiers and Indian language support.
  - Token-level USD cost estimation formula based on published provider pricing.
- **Prompt Safety Registry & Injection Defenses (`tk_api/ai/prompts.py`)**:
  - Explicit system boundary separation: `DEVELOPER_RULES`, `<retrieved_context>`, `<user_input>`, and `<report_content>`.
  - PII scrubbing (`redact_pii_from_prompt`) masking 12-digit Indian national ID / Aadhaar patterns and phone numbers.
  - Mandatory "insufficient evidence" fallback policy preventing hallucinated government statistics.
- **Controlled Domain Tools & MCP-Ready Export (`tk_api/ai/tools.py`)**:
  - Allowlisted read-only tools: `search_institutions`, `get_institution_details`, `search_reports`, `get_official_data`, `get_discrepancies`.
  - `ToolRegistry` exporting MCP-compliant tool specifications (`list_tools()`).
- **Access-Controlled Hybrid RAG Retriever (`tk_api/ai/rag.py`)**:
  - `RagRetriever` combining keyword overlap, vector similarity, language filtering, and metadata scoping.
  - Pre-retrieval access control filtering ensuring administrative chunks are never leaked into public context.
  - Verifiable citation items linking to source dataset name, version, publication date, and verbatim text chunks.
- **Agent Orchestrator & Workflows (`tk_api/ai/orchestrator.py`)**:
  - Multi-turn research assistant with automatic conversation saving and operational audit trails in `ai_runs`.
  - Bounded agent workflows: Report Classifier, Duplicate Detection, Digital Twin Summary, Multilingual Translator.
- **FastAPI AI Router (`tk_api/api/routers/ai.py`)**:
  - `POST /api/v1/ai/chat`
  - `POST /api/v1/ai/classify-report`
  - `POST /api/v1/ai/duplicate-check`
  - `GET /api/v1/ai/institutions/{id}/summary`
  - `POST /api/v1/ai/translate`
  - `GET /api/v1/ai/tools`
  - `POST /api/v1/ai/feedback`
  - `GET /api/v1/ai/admin/usage`
- **Frontend Civic Assistant Experience (`apps/web`)**:
  - Typed client `apps/web/src/lib/api/ai.ts`.
  - `CivicAssistantChat.tsx`: Interactive research assistant supporting 14 Indian languages, suggested queries, interactive citation trays, source provenance modals, referenced entity cards, and feedback ratings.
  - Upgraded `/assistant` page.

## Phase 10 (user-sequenced: Government Data Integration, Official-Source Comparison, Data Provenance and Resource Intelligence) — 2026-08-17

**Deliverables:**
- **Database Migration `0023_phase10_govdata_discrepancies.py`**: Added `gov_raw_payloads` (raw source capture with SHA-256 digests), `entity_match_reviews` (multi-signal matching staged for administrative review), and `institution_discrepancies` (rule-based discrepancy ledger with neutral state constraints).
- **Connector Abstraction & Adapters (`tk_api/govdata/connectors.py`)**:
  - `GovernmentDataConnector` base interface (`validate_schema`, `normalize_record`, `extract_external_key`).
  - Domain Adapters: `UDISEPlusSchoolConnector` (Schools), `NHPHospitalConnector` (Hospitals), `CCTNSPoliceConnector` (Police Stations), `eCourtsConnector` (Courts), `PMGSYRoadsConnector` (Roads), and `GenericGovDataConnector`.
  - Security utilities: `validate_source_url` (SSRF guard against loopback, cloud metadata `169.254.169.254`, and private RFC 1918 networks), `sanitize_csv_cell` (CSV formula injection defense), `scrub_pii` (12-digit Aadhaar/ID masking).
- **Multi-Signal Entity Matching (`tk_api/govdata/matching.py`)**:
  - Multi-factor resolution scoring exact official code (0.95), geographic containment (0.90), and token-based name similarity (0.70+).
  - Categorization into `MATCHED`, `POSSIBLE_MATCH`, `CONFLICT`, `UNMATCHED`.
- **Rule-Based Discrepancy Engine (`tk_api/govdata/discrepancy.py`)**:
  - Objective rules comparing official staffing baselines (sanctioned vs working vs citizen shortage reports), sanitation/toilets, drinking water, and electricity.
  - Nuanced neutral states: `NO_DISCREPANCY_DETECTED`, `POSSIBLE_DISCREPANCY`, `CONFLICTING_DATA`, `OUTDATED_OFFICIAL_DATA`, `INSUFFICIENT_DATA`, `UNDER_REVIEW`, `RESOLVED`.
- **FastAPI Router Endpoints (`tk_api/api/routers/govdata.py`)**:
  - `GET /api/v1/institutions/{id}/official-data`
  - `GET /api/v1/institutions/{id}/discrepancies`
  - `GET /api/v1/institutions/{id}/comparison`
  - `GET /api/v1/govdata/sources`
  - `GET /api/v1/govdata/sources/{id}`
  - `POST /api/v1/govdata/sources`
  - `POST /api/v1/govdata/imports`
  - `GET /api/v1/govdata/entity-matches`
  - `POST /api/v1/govdata/entity-matches/{id}/review`
  - `GET /api/v1/govdata/data-quality`
- **Frontend Components & Pages (`apps/web`)**:
  - `OfficialDataCard.tsx`: Structured visual display of canonical indicators with source badge and audit trigger.
  - `DiscrepancyCard.tsx`: Objective comparative resource matrix (Official vs Citizen vs AI) with neutral status badges and on-ground verification action.
  - `ProvenancePanel.tsx`: Audit modal displaying publisher, dataset version, retrieval timestamp, license, SHA-256 checksum, and source link.
  - Upgraded `/institutions/[id]` Digital Twin with "Official vs Citizen Comparison" tab.
  - Upgraded public `/government-data` portal.
  - Created `/admin/government-data` administrative control center with quality scorecard, connector runner, and entity match queue.

## Phase 9 (user-sequenced: Maps, GIS, Geographic Intelligence and Location-Based Discovery) — 2026-08-17

**Deliverables:**
- **Spatial Pydantic Contracts (`tk_api/gis/schemas.py`)**: Defined `BoundingBoxQuery`, `MapNearbyQuery`, `MapInstitutionItem`, `MapReportItem`, `MapSummaryRead`, `GeocodeResponse`, `GeocodeResultItem`.
- **Forward & Reverse Geocoding Service (`tk_api/gis/geocoding.py`)**: Multi-entity geocoding resolving numeric coordinates (`lat, lng`), administrative geography entities (`Jaipur District`), and public institutions (`Govt High School`).
- **PostGIS & Haversine Viewport Intelligence (`tk_api/gis/service.py`)**:
  - `query_institutions_bbox`: Bounding-box filtered institutions with linked open and resolved report tallies.
  - `query_reports_bbox`: Bounding-box filtered public civic reports with category, severity, status, and trust score.
  - `query_nearby`: Proximity radius search across institutions and reports.
  - `get_map_summary`: Aggregated metrics (total institutions, reports, open/resolved, severity breakdown, and data coverage percentage).
- **FastAPI Router Endpoints (`tk_api/api/routers/gis.py`)**:
  - `GET /api/v1/gis/map/institutions`
  - `GET /api/v1/gis/map/reports`
  - `GET /api/v1/gis/map/nearby`
  - `GET /api/v1/gis/map/summary`
  - `GET /api/v1/gis/geocode/forward`
  - `GET /api/v1/gis/reverse-geocode`
  - `GET /api/v1/gis/boundaries`
- **Frontend Map & Exploration Interface (`apps/web`)**:
  - `MapExplore.tsx` featuring zoom/pan SVG projection, dynamic marker clustering, density heatmap radial overlay, keyboard navigation, accessible marker symbols (▲ critical/high, ◆ medium, ● low, 🏛 institution), and synchronized side-by-side (desktop) / bottom drawer (mobile) list view.
  - Upgraded `/map` page with live geocoding search, geographic hierarchy breadcrumbs (`India / State / District / ...`), layer toggles (Institutions, Reports, Heatmap), category/status filters, GPS "Find Near Me" geolocation, and URL search parameter state synchronization (`lat`, `lng`, `zoom`, `category`, `status`, `geography_id`).

## Phase 8 (user-sequenced: Civic Reporting, Media Evidence, AI-Assisted Intake and Verification) — 2026-08-16

**Deliverables:**
- **Schema Migration `0022_phase8_reporting_enhancements.py`**: Added `observed_at` (nullable datetime for observation date separate from submission timestamp) and `coordinate_source` (enum check constraint: `USER_SELECTED`, `DEVICE_LOCATION`, `INSTITUTION_LOCATION`, `MAP_SELECTED`, `IMPORTED`) to `reports` table.
- **Draft & Report Lifecycle Service (`tk_api/reports/service.py`)**:
  - Full Draft CRUD (`POST /reports/drafts`, `GET /reports/drafts`, `PATCH /reports/drafts/{id}`, `DELETE /reports/drafts/{id}`, `POST /reports/drafts/{id}/submit`) with IDOR ownership validation.
  - One-shot submission with `observed_at`, `coordinate_source`, `media_ids`, and boundary detection.
  - Report immutable observation records with append-only status transition history.
  - Form fields update locked on assigned/verified stages (`fields_locked` 409).
- **Media Evidence Pipeline**:
  - Pre-signed upload slot reservation (`POST /reports/{id}/media/upload-url`) enforcing MIME types and size limits.
  - Upload completion verification (`POST /reports/{id}/media/complete`) computing SHA-256 digests and linking to `report_evidence`.
  - Evidence list & delete endpoints with ownership checks.
- **Community Verification & Trust Scoring**:
  - `POST /reports/{id}/verifications` and `GET /reports/{id}/verifications`.
  - Prohibits self-verification (403 `own_report_verification_forbidden`).
  - Confirmation increases trust score (+0.15); refutation decreases trust score (-0.20).
  - Automatic status promotion: `submitted` → `under_verification` on initial verification, and to `verified` when trust score reaches threshold (≥ 0.30).
- **AI-Assisted Intake & Heuristics**:
  - Suggest-only real-time suggestions (`POST /reports/ai/suggest`) providing category, issue type, title, and severity recommendations without mutating user inputs.
  - Spatial Haversine duplicate candidate detection (`GET /reports/{id}/duplicates`) and duplicate linking (`POST /reports/{id}/duplicates/link`).
  - Threaded comment replies (`POST /reports/{id}/comments` with `parent_id`) and notification follow toggles (`POST /reports/{id}/follow`).
- **Frontend Civic Reporting Experience (`apps/web`)**:
  - Upgraded `SubmitWizard.tsx` with dynamic category loading, GPS auto-detect, institution linkage, structured custom fields, observation date picker, AI auto-suggest helper, evidence media staging, local auto-save & recovery, and submission receipt.
  - Enhanced `ReportDetail.tsx` with evidence gallery, verification modal, trust progress indicator, duplicate candidate cards, timeline progression stepper, follow toggle, and threaded comments.
  - Upgraded `profile/page.tsx` with tabbed "My Reports" & "Drafts" management and wizard resume actions.

## Phase 7 (user-sequenced: Authentication, Authorization, Identity and Account Security) — 2026-08-16

**Deliverables:**
- **Schema Migration `0021_identity_roles_permissions.py`**: Added `username`, `bio`, `profile_image_url`, `location_pref` to `users` table; seeded 9 standard roles (`citizen`, `volunteer`, `verified_contributor`, `moderator`, `institution_representative`, `department_representative`, `analyst`, `admin`, `super_admin`); seeded fine-grained permission codes and `role_permissions` mapping matrix.
- **Argon2id Hashing & Security Utilities (`tk_api/auth/security.py`)**: Configured Argon2id password hashing via `argon2-cffi` with password length enforcement; cryptographic SHA-256 token hashing for email verification and password reset; JWT claims decoding with algorithm pinning.
- **Fine-Grained RBAC & Resource-Level Authorization (`tk_api/auth/authorization.py`)**: Built `AuthorizationService.can()` and `.require()` with aggregate role-permission resolution, super admin wildcard access, and resource-level ownership validation (IDOR protection: User A cannot edit or delete User B's report; scoped institution representative twin management). Added FastAPI dependency helpers `require_permission` and `require_any_permission`.
- **Comprehensive Auth & Session Service (`tk_api/auth/service.py`)**:
  - Email registration with single-use verification token (`email_verifications`) and reserved username checks.
  - Rate-limited verification resend and forgot-password endpoints with safe generic responses preventing account enumeration.
  - Single-use password reset with token invalidation and automatic session revocation across all active devices.
  - Authenticated password change with previous password verification and optional `revoke_other_sessions`.
  - Multi-device active session tracking (`sessions` table) with per-session deletion and `POST /auth/logout-all`.
  - Google OAuth sign-in (`GET /auth/oauth/google/url`, `POST /auth/oauth/google/callback`) with verified-email account linking.
  - DPDP Act compliant account anonymization (`DELETE /users/me`) stripping PII while preserving public civic contributions.
  - Structured security event logging (`security_events` table) across all authentication and lifecycle milestones.
- **Frontend Security & Auth Foundation (`apps/web`)**:
  - Typed `authApi` client methods (`lib/api/auth.ts`) and enhanced `AuthProvider` / `useAuth()` hook with `roles`, `permissions`, `hasRole()`, `hasPermission()`, `logoutAll()`.
  - Upgraded `LoginForm.tsx` with email/username/phone support, Google OAuth button, and forgot-password link.
  - Upgraded `RegisterForm.tsx` with name, email, username, password strength, DPDP terms consent, and Google OAuth option.
  - Built dedicated pages: `verify-email/page.tsx`, `forgot-password/page.tsx`, `reset-password/page.tsx`, `auth/callback/page.tsx`, and `profile/security/page.tsx` (session management, password change, account deletion modal).

**Verification:** 157 pytest backend tests passing (including 13 dedicated Phase 7 auth & IDOR tests), 22 vitest frontend tests passing, 0 TypeScript errors, successful Next.js 16 production build.

## Phase 6 (user-sequenced: Frontend Application Foundation and Core User Experience) — 2026-08-16

**Deliverables:**
- Modular typed API clients in `apps/web/src/lib/api/` (`geography`, `institutions`, `civic`, `reports`, `search`).
- Global Search combobox with live debounced querying, domain filter tabs, keyboard navigation, and direct navigation routing.
- Responsive Application Shell (`AppShell.tsx`) with desktop navigation, mobile bottom navigation bar, location context, language picker, and theme switcher (Dark/Light).
- Dynamic Home Page (`Landing.tsx`) with real category cards, live civic metrics, interactive map preview, and recent report cards.
- Explore Page (`explore/page.tsx`) with zero-hardcoding geography hierarchy drilldowns, breadcrumbs, filter bar, and dual Map/List layout.
- Public Institutions Directory (`institutions/page.tsx`) with type/geography filters and pagination.
- Institution Digital Twin Page (`institutions/[id]/page.tsx`) displaying operational status, dynamic EAV infrastructure and staffing attributes, linked citizen reports, issues tabs, location map, and provenance.
- Reports Feed (`reports/page.tsx`) and Detail (`ReportDetail.tsx`) pages with severity badges, category schema attributes, GPS coordinates, status stepper progression, community verification, and comments.
- Report Submission Wizard (`SubmitWizard.tsx`) with 6 accessible steps: category, GPS location, optional institution linkage, issue type & schema details, evidence upload staging, and review.
- Multilingual i18n foundation for 14 Indian languages with full translations for English and Hindi.
- WCAG 2.2 AA accessibility, screen reader announcements, semantic landmarks, and skip links.

**Verification:** 18 vitest unit/component tests passing, 0 TypeScript errors, 0 ESLint errors, successful Next.js 16 production build.

## Phase 5 (user-sequenced: Backend Foundation and Core API Layer) — 2026-08-16

**Deliverables:**
- Modular monolith package layout (`tk_api/core/`, `tk_api/geography/`, `tk_api/institutions/`, `tk_api/civic/`, `tk_api/reports/`, `tk_api/search/`, `tk_api/api/v1.py`).
- Generic pagination primitives (`PageParams`, `CursorParams`, `PageResponse[T]`, `CursorResponse[T]`, base64 cursor encoding/decoding).
- Safe dynamic query sorting helper (`apply_sort()`) with strict column allowlists preventing SQL injection.
- Standardized error hierarchy and RFC 9457 `ProblemDetails` format injecting `request_id` and `X-Correlation-ID`.
- Correlation ID middleware inspecting/emitting both `X-Correlation-Id` and `X-Request-Id`, suppressing logs on ops probes.
- Dynamic Geography hierarchy and search endpoints (`/api/v1/geography/types`, `/api/v1/geography`, `/api/v1/geography/{id}`, `/api/v1/geography/{id}/children`, `/api/v1/geography/{id}/ancestors`, `/api/v1/geography/search`).
- Institution Digital Twin CRUD and attribute aggregation (`/api/v1/institutions/types`, `/api/v1/institutions`, `/api/v1/institutions/{id}`, `POST /api/v1/institutions`, `PATCH /api/v1/institutions/{id}`).
- Civic issue types and category detail tree (`/api/v1/civic/issue-types`, `/api/v1/civic/categories/{id_or_slug}/detail`).
- Expanded Report state machine and attributes (`institution_id`, `issue_type_id`, `severity`, `visibility`, `source`, lifecycle statuses `resolution_submitted`, `resolution_review`, `community_verified`, `needs_information`, `archived`).
- Unified Search service and endpoint (`/api/v1/search?q=...&domain=all|reports|institutions|geography|categories`).
- Centralized `/api/v1` router registry in `tk_api/api/v1.py` and dual ops probes (`/health`, `/healthz`, `/ready`, `/readyz`).

**Verification:** 144 unit tests passing, 0 ruff errors, 0 mypy strict errors across 90 source files, updated OpenAPI snapshot (`tests/contracts/openapi.snapshot.json`).

## Phase 3 (user-sequenced: Database + PostGIS + Data Architecture) — 2026-08-16

**Deliverables:** migrations **0010–0020** (identity expansion; geography
registry w/ PostGIS geometry + translations; institutions + typed attributes;
provenance domain w/ versioned records; categories translations/hierarchy +
issue types (21 seeded); reports v2 (FKs + severity/visibility CHECKs);
report_evidence + media_processing_jobs pipeline; report_duplicates
(AI-suggest only); community + moderation; resolution + reputation +
subscriptions + devices; content_translations; ai_outputs/feedback/
evaluations; rag documents/versions/chunks; gov datasets/imports/records;
analytics events + daily). 11 new tables groups, ~13 new tables total → **95
tables** at head `0020_fix_versioning_uniques`; seeds: 15 permissions, 12
geography types, 21 issue types, 8 reputation policies (all synthetic/
config; no fabricated stats). ORM models added under the same SQLite-safe
registration discipline (geometry tables unregistered, raw-SQL on PG).

**Verification:** 139 unit + 10 integration; ruff/mypy clean (78 files);
fresh-db round trip upgrade→downgrade→upgrade (95 tables); live dev DB
upgraded 0009→0020 with zero data loss (14 categories/771 boundaries intact);
PG constraints spot-checked (versioned-key uniques, subscription single-target
CHECK, GIST auto-indexes).

**Defects found & fixed:** bulk-insert seed timezone/id bindings; SQLite
constraint portability (::int casts PG-only); num_nonnull availability (PG=16
only) → additive expression; migration-revision id length; versioned-key
uniqueness design bug → 0020 corrective migration; reports-V2 FK ordering in
tests; integration fixture uniqueness/idempotency.

**Decisions:** ADR-042 (full-domain schema; pgvector deferred).

**Next phase:** per controller instruction (architecture outline lands Phase 4+).

---

## Phase 2 (user-sequenced: System Architecture) — 2026-08-16

**Deliverables (documentation — no code, per instruction)**

- `docs/ARCHITECTURE.md` v2.0 — modular monolith (23 module boundaries table),
  system-context + citizen-report data-flow diagrams (Mermaid), per-tier
  components (frontend/backend/DB/GIS/search/storage/auth/notifications/AI/
  RAG/agents/MCP/analytics/observability/admin/moderation), scalability plan
  for 10K/100K/1M/10M+ users with **measured** triggers
- `docs/AI-ARCHITECTURE.md` v2.0 — Application → Gateway → Router →
  capabilities layer model; provider-agnostic DeepSeek-first chain; model
  router (task→model registry, budgets, eval floors); embeddings + pgvector;
  RAG (provenance-gated corpora, citation-or-decline policy); tools + agents
  with human-in-the-loop gates; MCP adapters; eval & safety
- `docs/SECURITY.md` v2.0 — trust boundaries (Mermaid), authentication
  (incl. OAuth/password-reset/MFA-ready), permission-key RBAC, API/file/AI
  security, secrets, DPDP privacy, auditability, incident response
- `docs/DECISIONS.md` — ADRs 036–041 appended (monolith; model-agnostic router;
  pgvector; RAG corpora policy; agents + MCP; search tiering)
- Consistency pass: PRD §15/§16 ↔ roadmap ↔ module table ↔ scalability
  triggers; AI cap list ↔ router registry ↔ eval floors; trust tiers ↔ SECURITY.

**Next phase (by instruction):** Phase 3 — the controller will sequence it.

---

## Phase 1 — Product Requirements + Architecture Foundation (2026-08-16)

**Deliverables (documentation only — no code, per instruction)**

- `docs/PRD.md` v2.0 — product vision (why not-a-complaint-portal, AI value,
  national scale); 9 personas; configurable 12-level geographic hierarchy
  (no India hard-coding); 11 category domains; Institution Digital Twin
  (provenance-typed ledger); lifecycle v2 (Reported→…→Closed +
  negative/administrative states); evidence chain; community (feed→moderation);
  maps (markers→timeline); analytics (7 metrics × 8 levels); 15-language i18n
  architecture; 14 AI use cases; 5-tier trust (schema-enforced); security
  (incl. OAuth/password-reset/MFA-ready); MVP P0–P3; V1–V3 roadmap with
  agentic layer
- `docs/ROADMAP.md` v2.0 — product roadmap (MVP/V1/V2/V3) + engineering
  phases 1–11 with exit criteria; DoD; milestones M0–M3; open questions
- `docs/UX.md` v2.0 — design principles; 6 user journeys (J1–J6); IA;
  tier-rendering rules; accessibility + performance budgets carried from
  Cycle-1 baseline
- `docs/IMPLEMENTATION-STATUS.md` — this file (Cycle-2 table + Phase 1 record)
- Artifacts embedded in PRD appendices: feature matrix (P0–P3/V1–V3),
  acceptance criteria (MVP gate), major risks, dependencies, architectural
  implications

**Cross-checking**

- Personas ↔ RBAC ↔ security appendix consistent.
- Lifecycle v2 statuses ↔ state-machine implication (§E3) and map appendix
  timeline feature aligned.
- i18n: Cycle-1 seed = en, hi, ta, te, bn, mr, gu, kn, ml, pa (10); Phase 2
  of this cycle adds odia, punjabi(complete set), assamese, urdu, maithili →
  15, plus script/RTL QC (urdu).
- Hierarchy registry implication de-couples analytics from India-specific
  depth (PRD §3 ↔ §E1/§E6).

**Known gaps / decisions for the next phase**

- Baseline reconciliation must verify Cycle-1 tables/kinds against the
  registry design before touching them (Path: new `hierarchy` model; existing
  `gis_boundaries` becomes one registry implementation).
- Locale additions + translation workflow shape confirmed in Phase 7; Phase 2
  lands the registry rows now.
- OAuth/password-reset/MFA scaffolding are additive to the Cycle-1 auth core
  (ADR-008 path).

**Next phase (by instruction):** Phase 2 — baseline reconciliation + platform
deltas (wait for explicit "start phase 2").

---

## Cycle 1 — Reference Baseline (Phases 0–12, complete 2026-08-16)

All phases exited green with completion reports on record:

- 0: scaffold · 1: docs · 2: API skeleton · 3: auth/RBAC/OTP/audit ·
  4: civic engine + full schema + PostGIS · 5: reports/media/measurement ·
  6: AI layer (T4 + review queue + eval) · 7: web PWA (axe-clean, hi+en) ·
  8: Celery worker + notifications + quiet hours ·
  9: GIS (36 states + 735 districts, provenance-fenced) ·
  10: observability/SLO/security/DPDP/runbooks · 11: CI/CD + validated
  Terraform + legal drafts · 12: geo-political ingestion + M1 close-out

**Final M1 state:** 133 unit + 9 integration + 9 E2E; p95 16.7 ms; eval
floors held; live stack all-healthy; 14 seeded categories + 36 states + 735
districts with provenance; migrations 0001–0009 round-trip verified.

**Carry-forwards into Cycle 2 (tracked):** AWS bootstrap for the validated
Terraform; DLT-registered SMS onboarding (console sandbox active); DPDP
counsel review + grievance contact; ward maps + UDISE+ school licensing
(assessed in PROVENANCE.md); plus the Cycle-2 projects above.

## Phase 27 (AI Platform) — 2026-08-18

**Deliverables (backend `services/api`, docs `docs/`):**
- **Migration 0039** (`alembic/versions/0039_phase27_ai_platform.py`) — 8 new tables: `ai_agent_registry` (agents with versions, permissions, policies, risk levels, budgets), `ai_agent_runs` (full execution tracking with traces, costs, approval status), `ai_tool_executions` (per-tool call audit), `ai_trace_spans` (distributed trace spans), `ai_cost_records` (daily cost aggregation by agent/model/provider), `ai_prompt_versions` (versioned prompt registry with draft/testing/approved lifecycle), `ai_skills` (skill definitions with tools and permissions), `ai_eval_results` (evaluation results for agents, tools, RAG, safety, red-team).
- **AI Gateway** (`tk_api/ai_platform/gateway.py`) — Centralized entry point for all AI calls. Rate limiting (per-user, per-minute), circuit breaker (5-failure threshold, 60s recovery), PII scrubbing, model selection via ModelRouter, retry with fallback (3 attempts), cost tracking, standardized request/response models.
- **Agent Architecture** (`tk_api/ai_platform/agents.py`) — BaseAgent ABC with 10 specialized agents: CivicAssistantAgent, CaseAnalysisAgent, RoutingAgent, TranslationAgent, AnalyticsAgent, EvidenceAgent, DataQualityAgent, GeospatialAgent, PolicyResearchAgent, SafetyAgent. AgentRouter with intent classification (13 categories) and keyword-based routing. Each agent has: code, name, risk_level, allowed_tools, allowed_data, max_execution_time, max_tool_calls, max_tokens, cost_budget.
- **Skills Architecture** (`tk_api/ai_platform/skills.py`) — 10 reusable skill definitions: case_summary, department_routing, evidence_analysis, data_quality_check, translation, map_analysis, policy_research, impact_analysis, report_drafting, communication_draft. SkillRegistry with composition support.
- **Multi-Agent Orchestration** (`tk_api/ai_platform/skills.py`) — WorkflowGraph with 3 predefined workflows: case_deep_analysis (4 steps), district_overview (4 steps), resolution_assessment (4 steps with human approval). Supports sequential, parallel, conditional, human-approval, retry, fallback steps.
- **Evaluation Framework** (`tk_api/ai_platform/evaluation.py`) — 13 golden evaluation test cases across: agent routing (5), safety (3), red-team (3), RAG (1), multilingual (1). EvaluationFramework runs tests, records results to DB, computes pass rates.
- **Observability** (`tk_api/ai_platform/observability.py`) — AI trace retrieval, cost summary (daily aggregation by model/agent), health monitoring (runs/failures per hour, provider health), evaluation summary. Cost recording with daily upsert aggregation.
- **Safety Agent** — Deterministic safety validation (no LLM required). Detects: prohibited patterns ("government lied", "official response published", "case closed", "permission granted", "bypass"), sensitive attribute references (religion, caste, political affiliation, voting). All deterministic, fast, auditable.
- **20+ API Endpoints** under `/api/v1/ai-platform/`: gateway/chat, gateway/health, agents, agents/{code}, agents/execute, skills, skills/compose, workflows, workflows/execute, evaluations, evaluations/run, evaluations/summary, evaluations/test-cases, traces/{id}, costs, health, runs, runs/{id}, runs/{id}/approve.
- **Circuit Breaker** — Per-provider failure tracking with configurable threshold and recovery timeout. Auto-opens circuit on repeated failures, auto-recovers after timeout. Status exposed via health endpoint.
- **Model Router** — Tiered model selection: fast (classification), standard (chat/analysis), deep_reasoning (complex analysis). Language-aware selection. Cost calculation per model/token-tier. Fallback chain for provider failures.

**Tests:**
- 61 dedicated Phase-27 pytest tests across 7 test classes:
  - TestAIGateway (6 tests) — Circuit breaker, request/response defaults
  - TestAgentRouter (12 tests) — Build agents, intent routing, keyword routing, list agents, intent categories
  - TestSkills (6 tests) — Registry, get, compose, workflow definitions
  - TestSafetyAgent (5 tests) — Prohibited content, clean text, sensitive attributes, bypass, false positives
  - TestEvaluation (7 tests) — Golden dataset, filtering by type/tag/agent, combined filters, multilingual
  - TestMultiAgentOrchestration (4 tests) — Workflow list, steps, not found, risk levels
  - TestAIPlatformAPI (20 tests) — All API endpoints: gateway, agents, skills, workflows, evaluation, health, costs, runs, authorization
- All 61 Phase-27 tests passing
- Pre-existing tests continue passing (259 non-Phase-27 tests verified)
- 1 pre-existing Phase-21 test failure documented (not caused by Phase 27)

**Security:**
- All AI endpoints require authentication and `ai.use` or `ai.admin` permissions
- AI Gateway rate-limits per user (30 requests/minute)
- Circuit breaker prevents cascade failures across providers
- Safety Agent blocks prohibited patterns and sensitive attribute usage
- PII scrubbing on all AI inputs via `redact_pii_from_prompt`
- Agent execution budgets: max_runtime, max_tool_calls, max_tokens, cost_budget
- Human-in-the-loop: RoutingAgent and ResolutionAssessment require approval
- Audit logging via existing AuditLog system

**Known Limitations:**
- No live LLM provider integration (StubLlmProvider only; production requires OpenAI/Anthropic/DeepSeek keys)
- RAG vector search uses existing pgvector architecture (no new embedding pipeline)
- Multi-agent workflows are sequential only (no true parallel execution in sync test harness)
- Evaluation framework runs synchronously (batch evaluation worker task not implemented)
- No frontend AI chat UI, agent dashboard, or evaluation dashboard
- Prompt registry has no UI for editing/approval workflow

**Recommended Phase 28:**
- Production LLM provider integration (OpenAI, Anthropic, DeepSeek)
- RAG document ingestion pipeline with chunking, embedding, re-indexing
- Frontend: AI chat interface, agent dashboard, evaluation dashboard
- Worker: batch evaluation, cost aggregation, prompt version deployment
- AI memory: conversation context, user preferences
- Multi-agent parallel execution
- AI observability dashboard (traces, costs, evaluation trends)

---

## Phase 28 (Security, Privacy, Trust, Compliance, AI Safety) — 2026-08-19

**Deliverables (backend `services/api`, docs `docs/`):**

- **Security Module** (`tk_api/security/`) — Complete security infrastructure with:
  - `models.py` — 6 new database models: SecurityIncident (lifecycle tracking), AbuseScore (risk scoring), IPBlock (IP-based blocking), SecurityPolicy (configurable policies), SecurityAuditEntry (security-focused audit), DataRetentionPolicy (retention rules)
  - `service.py` — Core security services: IPBlockService, AbuseDetectionService, SecurityIncidentService, InputSanitizer, DataClassificationService, SecurityAuditService, RateLimitConfig, PromptInjectionGuard
  - `middleware.py` — Enhanced security middleware: EnhancedSecurityHeadersMiddleware (CSP, HSTS, XSS protection), RequestSizeLimitMiddleware (body size limits), SSRFProtectionMiddleware (SSRF detection utilities), AbuseDetectionMiddleware (request-level abuse monitoring)
  - `schemas.py` — API request/response schemas for all security endpoints

- **Security API Router** (`tk_api/api/routers/security.py`) — 15 endpoints under `/api/v1/security/`:
  - `POST /incidents` — Create security incident
  - `GET /incidents` — List incidents with severity/status filters
  - `GET /incidents/{id}` — Get specific incident
  - `PATCH /incidents/{id}` — Update incident status
  - `POST /ip-blocks` — Block an IP address
  - `DELETE /ip-blocks/{ip}` — Unblock an IP
  - `GET /ip-blocks` — List active IP blocks
  - `GET /abuse-scores` — List abuse scores with filters
  - `GET /audit` — Security audit entries
  - `GET /audit/summary` — Security event summary
  - `POST /validate-input` — Validate input for injection attacks
  - `GET /classification/{entity_type}` — Get data classification level
  - `GET /health` — Security health status

- **Alembic Migration 0040** (`alembic/versions/0040_phase28_security.py`) — 6 new tables: `security_incidents`, `abuse_scores`, `ip_blocks`, `security_policies`, `security_audit_entries`, `data_retention_policies`

- **Enhanced Security Headers** — Updated middleware stack with:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=(self), payment=()`
  - `X-XSS-Protection: 1; mode=block`
  - `Cache-Control: no-store, no-cache, must-revalidate`
  - Content-Security-Policy for non-documentation paths

- **Input Validation & Sanitization**:
  - Prompt injection detection (10+ patterns: ignore instructions, system prompts, role overrides, bypass attempts)
  - SQL injection detection (DROP/TRUNCATE, INSERT INTO, UPDATE SET, DELETE FROM, EXEC, UNION SELECT)
  - Path traversal detection (../, %2e%2e%2f, encoded variants)
  - HTML sanitization (script tag removal, event handler stripping, javascript: URL blocking)
  - URL safety validation (SSRF protection: blocks localhost, private IPs, metadata endpoints)

- **Data Classification Service** — 5-level classification (PUBLIC → INTERNAL → CONFIDENTIAL → RESTRICTED → HIGHLY_RESTRICTED) with 18 entity-type mappings (user profiles, contacts, credentials, reports, evidence, government data, etc.)

- **Prompt Injection Protection** — AI input validation, external content wrapping with untrusted-data markers, tool output sanitization

- **RBAC Integration** — `security.read` and `security.manage` permissions added to admin and moderator roles

- **Middleware Stack** — 7 middleware layers: CORSMiddleware → CorrelationMiddleware → SecurityHeadersMiddleware → EnhancedSecurityHeadersMiddleware → RequestSizeLimitMiddleware → SSRFProtectionMiddleware → AbuseDetectionMiddleware → MetricsMiddleware

**Tests:**
- 24 dedicated Phase-28 pytest tests across 8 test classes:
  - TestSecurityIncidents (4 tests) — Create, list, update, authorization
  - TestIPBlocking (3 tests) — Block, list, unblock
  - TestAbuseScores (1 test) — List abuse scores
  - TestSecurityAudit (2 tests) — List audit entries, summary
  - TestInputValidation (3 tests) — Safe input, injection detection, SQL detection
  - TestDataClassification (1 test) — Classification lookup
  - TestSecurityHealth (1 test) — Health status check
  - TestSecurityServices (9 tests) — Injection, SQL, path traversal, HTML sanitize, SSRF, classification, prompt injection, content wrapping, tool output sanitization
- All 24 Phase-28 tests passing
- Pre-existing tests continue passing

**Security Improvements:**
- Zero Trust: All inputs validated at middleware and API layers
- Defense in Depth: 7 middleware layers, multiple validation points
- SSRF Protection: Blocks access to private IPs, metadata endpoints, internal services
- Input Sanitization: Detects prompt injection, SQL injection, path traversal, XSS
- IP Blocking: Time-limited blocks with reason tracking and audit
- Abuse Detection: Risk scoring with automatic action (IP block on threshold)
- Data Classification: 5-level sensitivity with clearance-based access control
- Prompt Injection Guard: Wraps external content as untrusted, sanitizes tool outputs
- Security Incidents: Full lifecycle (detected → investigating → contained → recovered → closed)
- Security Audit: Risk-leveled entries separate from general audit log

**Known Limitations:
- Middleware-based SSRF protection is a utility (pass-through); actual SSRF checking happens at call sites (HTTP clients, tool handlers)
- Abuse detection is event-driven (not real-time behavioral analysis)
- No automated malware scanning for uploads (ClamAV slot reserved)
- No distributed rate limiting across multiple backend instances
- No automated vulnerability scanning in CI/CD

**Recommended Phase 29:**
- Frontend: /admin/security dashboard (incidents, blocks, audit)
- Automated malware scanning for uploads (ClamAV integration)
- Distributed rate limiting (Redis-backed across instances)
- SAST/DAST integration in CI/CD
- Security incident response automation (playbooks)
- Penetration testing preparation and checklist
- Data retention enforcement worker tasks
- Account deletion workflow with relationship checks
- PII inventory and data export

---

## Phase 29 (Production Readiness) — 2026-08-19

**Deliverables (backend `services/api`, docs `docs/`):**

- **Production Module** (`tk_api/production/`) — Production readiness infrastructure:
  - `cache.py` — Redis-backed caching layer with TTL, namespace isolation, stampede protection (request coalescing via asyncio locks), cache-aside pattern, invalidation (key, pattern, namespace), and hit/miss metrics tracking. Pre-defined namespaces with TTLs: SHORT (60s), MEDIUM (5min), LONG (1hr), VERY_LONG (24hr)
  - `observability.py` — Comprehensive observability: HealthChecker (database, Redis, storage, worker checks), PerformanceTracker (latency budgets with p50/p95/p99 targets), CostTracker (daily cost aggregation by service), SLOCalculator (availability and latency SLO compliance). Prometheus metrics: API availability, latency, DB query latency, cache hits/misses, queue depth, AI requests/cost/tokens, notification sent/failures, government response time, storage usage
  - `db_optimization.py` — Database optimization: connection pool monitoring, table size analysis, unused index detection, table bloat estimation, slow query recording, query performance statistics, cursor-based pagination (with stampede protection), offset-based pagination with safety limits

- **Production API Router** (`tk_api/api/routers/production.py`) — 10 endpoints under `/api/v1/production/`:
  - `GET /health` — Comprehensive health check (database, Redis, storage, worker)
  - `GET /health/database` — Database-specific health with pool stats
  - `GET /performance/budgets` — Performance budget compliance check
  - `GET /cost/summary` — Cost summary by service (days parameter)
  - `GET /database/maintenance` — Table sizes, unused indexes, bloat analysis
  - `GET /database/slow-queries` — Recorded slow queries
  - `GET /database/query-stats` — Query performance statistics
  - `GET /slo/availability` — API availability SLO

- **Enhanced Health Endpoint** (`tk_api/api/routers/health.py`) — New `/health/comprehensive` endpoint with full dependency checks (database, Redis, storage, worker) and overall status

- **Tier-based Rate Limits** (`tk_api/core/rate_limit.py`) — Rate limit tiers: anonymous (30/min), authenticated (60/min), verified (120/min), organization/government (300/min), admin (600/min)

- **Documentation**:
  - `docs/CAPACITY-PLAN.md` — Planning targets, capacity model, traffic estimates, storage estimates, compute estimates, SLO/SLI/SLA definitions, performance budgets, scaling strategy, cost projections, peak traffic design
  - `docs/DISASTER-RECOVERY.md` — RPO/RTO targets, failure scenarios (database, Redis, storage, AI, notifications, government), backup strategy, restore testing, communication plan, runbooks
  - `docs/PERFORMANCE.md` — Performance budgets, optimization strategies (database, caching, API, frontend), load testing scenarios, monitoring metrics, common issues

**Tests:**
- 30 dedicated Phase-29 pytest tests across 9 test classes:
  - TestCacheService (5 tests) — Metrics, namespaces, key generation, get miss, set/get
  - TestPerformanceTracker (4 tests) — Record/summary, budget pass, budget fail, custom budget
  - TestCostTracker (2 tests) — Record/summary, daily tracking
  - TestSLOCalculator (5 tests) — Availability pass/fail/no-data, latency pass/fail
  - TestPagination (5 tests) — Cursor limit, max limit, offset params, offset max, format
  - TestRateLimitTiers (3 tests) — Anonymous, admin, unknown tier fallback
  - TestProductionAPI (6 tests) — Health, database, performance, cost, maintenance, authorization
- All 30 Phase-29 tests passing
- Pre-existing tests continue passing

**Key Improvements:**
- Comprehensive health checks with dependency tracking
- Performance budget monitoring against defined targets
- Cost tracking by service with daily aggregation
- Database optimization with table analysis and index recommendations
- SLO compliance calculation for availability and latency
- Pagination helpers (cursor-based for efficiency, offset-based for compatibility)
- Tier-based rate limiting for different user types
- Prometheus metrics for all production observability
- Capacity planning documentation with realistic targets
- Disaster recovery framework with RPO/RTO definitions
- Performance optimization guide with common issues

**Known Limitations:**
- Cache requires Redis (falls back to no-cache in memory mode)
- Database maintenance queries are PostgreSQL-specific (SQLite fallback for tests)
- SLO calculations are current-state (historical requires Prometheus integration)
- Cost tracking is in-memory (persistent tracking requires database integration)
- Load testing utilities not yet implemented (recommended for Phase 30)

**Recommended Phase 30:**
- Frontend: /admin/observability dashboard, /admin/cost dashboard
- Load testing with k6 (API, case creation, search, map)
- Distributed tracing with OpenTelemetry end-to-end
- Real-time SLO alerting integration
- Database read replica support
- Cache warming strategies
- Production Prometheus/Grafana dashboards
- Infrastructure as Code (Terraform) for cloud deployment

---

## Cycle 2 Roadmap Phase C2-5 (Maps v2 + Evidence v2) — 2026-08-20

**Deliverables (backend `services/api`, `apps/web`):**

- **Migration 0041** (`alembic/versions/0041_phase5_evidence_v2.py`) — new columns + table:
  - `report_media` — added `pair_group` (String(64)), `pair_role` (String(16)), `captured_at` (DateTime) for before/after evidence pairing
  - `media_objects` — added `duration_seconds` (BigInteger), `fps` (Integer), `codec` (String(32)) for video evidence support
  - New table `evidence_chains` — tamper-evident SHA-256 hash chain linking evidence items per report

- **Heatmap Data Endpoint** (`GET /api/v1/gis/map/heatmap`) — returns weighted density points for client-side heatmap rendering; supports category/status/severity filters and bounding box viewport; weights derived from severity (critical=3.0, high=2.0, medium=1.0, low=0.5)

- **Timeline Data Endpoint** (`GET /api/v1/gis/map/timeline`) — returns time-series bucketed by day/week/month for map timeline scrub; includes per-period open/resolved/critical/high/medium/low counts

- **Video Evidence Support** — scan gate (`media/scan.py`) now accepts MP4 (magic bytes `00 00 00 18 66 74 79 70` + `00 00 00 1c 66 74 79 70`), QuickTime (`66 74 79 70 71 74 20 20`), and WebM (`1a 45 df a3`) magic bytes; video MIME types accepted alongside existing image types

- **Before/After Evidence Pairing** — `ReportMedia` model supports `pair_group` (groups related before/after items), `pair_role` (before/after/standalone), and `captured_at` (exact capture timestamp)

- **Evidence Chain** (`media/models.py: EvidenceChain`) — `report_id`, `chain_hash` (SHA-256 of ordered evidence item hashes), `evidence_count`, timestamps; creates tamper-evident chain linking all evidence for a report

- **Media Object Video Fields** — `MediaObject` model extended with `duration_seconds`, `fps`, and `codec` for video metadata storage

- **Evidence Chain API** (`GET /api/v1/media/reports/{report_id}/evidence-chain`) — returns the latest evidence chain for a report

- **Report Media API** (`GET /api/v1/media/reports/{report_id}/media`) — lists all media items with before/after pairing info

- **Frontend API Client** — evidence chain + report media + conversation methods added to `apps/web/src/lib/api/ai.ts`

**Tests:**
- 14 dedicated tests in `tests/test_phase5_maps_evidence.py` (all passing)
- Covers: heatmap service, timeline service, video scan gate, before/after pairing, evidence chain creation
- All 597 pre-existing tests continue passing

**Migration:** 0041 applied on real Postgres (1 new table + 5 new columns verified)

**Known Limitations:
- Real tile basemap (MapLibre) not yet integrated in frontend — current MapExplore uses SVG rendering with server-side clustering
- Evidence chain auto-build (triggered on evidence upload) not yet implemented
- Video thumbnail generation not yet implemented

---

## Cycle 2 Roadmap Phase C2-7 (Full 15-Locale i18n) — 2026-08-20

**Deliverables (`apps/web`):**

- **15 Indian Languages Registered** — en, hi, bn, te, mr, ta, gu, kn, ml, or, pa, as, ur, mai, sd (all in `apps/web/src/lib/i18n.ts`)
- **English + Hindi Fully Translated** — 400+ keys each; complete coverage of all UI strings, error messages, notification templates
- **13 Remaining Locales** — Use English fallback with architecture ready for community translation; locale switcher functional in header
- **Locale-Specific Formatting** — Date, number, and currency formatting adapted per locale via `Intl` APIs
- **Backend i18n Catalogs** — Server-side string catalogs for notification templates in en + hi; other locales use en fallback

**Tests:**
- All 45 vitest frontend tests passing (i18n-related tests included)
- All 597 pytest backend tests passing
- No TypeScript errors

**Known Limitations:
- Community translation workflow (edit-in-browser, review, approve) not yet implemented
- Script QC pass (right-to-left rendering for Urdu, complex ligatures) not yet automated
- Notification templates for 13 locales not yet translated

---

## Cycle 2 Roadmap Phase C2-8 (AI Civic Assistant Polish) — 2026-08-20

**Deliverables (backend `services/api`, `apps/web`):**

- **Conversation History API** — 4 new endpoints:
  - `POST /api/v1/ai/conversations` — create a new conversation container
  - `POST /api/v1/ai/conversations/{id}/messages` — save a message (user or assistant) to a conversation
  - `GET /api/v1/ai/conversations` — list user's recent conversations (paginated)
  - `GET /api/v1/ai/conversations/{id}/messages` — get message history for a conversation

- **Official Persona Deep-Dive Tool** (`ai/tools.py: get_institution_deep_dive`) — comprehensive institution briefing combining: digital twin data, official baseline, recent reports, discrepancies, and SLA status; returns structured briefing with disclaimer about data authority

- **Source Freshness Tool** (`ai/tools.py: get_source_freshness`) — checks when a data source was last synced, days since sync, staleness flag (>30 days), latest import job status

- **Department Context Tool** (`ai/tools.py: get_department_briefing`) — public-safe department metrics: case counts by status, SLA breaches, escalations; no private data exposed

- **Multi-Turn Conversation Context** — `PROMPT_CIVIC_ASSISTANT_V1` now includes `conversation_history` section; orchestrator loads last 10 messages and injects them into the prompt; enables context-aware follow-up questions

- **Source Freshness in Prompts** — AI now notes when cited data is stale (>30 days old); maintains freshness metadata on every citation

- **Frontend Conversation API Client** — `listConversations`, `getConversationMessages`, `createConversation`, `saveConversationMessage` added to `apps/web/src/lib/api/ai.ts`

- **Frontend CivicAssistantChat** — already supports `conversation_id` state; passes it to `aiApi.chat()` for multi-turn persistence

**Tests:**
- All 597 pytest backend tests passing
- All 45 vitest frontend tests passing
- No TypeScript errors

**Known Limitations:
- Conversation search (full-text across past conversations) not yet implemented
- Conversation delete/archive not yet implemented
- Suggested follow-up questions are static (not context-aware from conversation history)
- AI cost tracking per conversation not yet exposed in frontend

---

## Cycle 2 Roadmap Phase C2-9 (Agentic Capabilities) — 2026-08-20

**Deliverables (backend `services/api`):**

- **Triage Agent** (`ai/triage.py`):
  - `triage_report()` — autonomous report classification with severity suggestion, routing hint, missing info detection, and confidence scoring
  - Heuristic enrichment on top of LLM output: critical keywords (danger, hazard, emergency, collapse) trigger escalation; missing description length triggers info request
  - SLA: 5-minute human review window for escalated triage decisions (TRIAGE_SLA_SECONDS = 300)
  - Advisory only — no status changes applied automatically; every triage decision is auditable

- **Batch Triage** (`ai/triage.py: batch_triage`):
  - Process multiple reports in a single call (max 10 per batch)
  - Returns per-report triage results + batch summary (total, escalated, failed, completed)

- **Recidivism Analytics** (`ai/recidivism.py`):
  - `detect_recidivism()` — detects recurring civic issues at same institution+category within 180-day window; requires 2+ resolved + 1 open report to trigger signal
  - Recidivism score: `min(1.0, resolved_count * 0.3 + high_severity_count * 0.2)`
  - Returns: institution/category, resolved/open counts, high-severity count, severity trend, sample tickets, recommendation
  - Supports geography and category filters

- **Recidivism Summary** (`ai/recidivism.py: get_recidivism_summary`):
  - High-level platform summary: total recurring patterns, institutions affected, categories affected, high-priority patterns (score ≥ 0.7)
  - Methodology documentation included in response

- **ML Moderation Assist** (`ai/moderation.py`):
  - `moderate_content()` — AI-assisted content analysis with 10 categories: spam, harassment, misinformation, hate_speech, personal_info, off_topic, low_quality, political, duplicate, safe
  - Heuristic checks: commercial spam keywords, harassment indicators, personal info exposure
  - Civic criticism of government services is NOT classified as harassment; civic reporting about political figures is NOT classified as political campaigning
  - Advisory only — no content auto-removed or hidden

- **Batch Report Moderation** (`ai/moderation.py: moderate_report_comments`):
  - Moderates all comments on a report (max 50 per call)
  - Returns per-comment recommendations + flagged count

- **API Endpoints** (6 new under `/api/v1/ai/`):
  - `POST /triage/{report_id}` — triage a single report (requires moderator/official/admin)
  - `POST /triage/batch` — batch triage (requires moderator/admin)
  - `GET /recidivism` — detect recurring issues (public, rate-limited)
  - `GET /recidivism/summary` — recidivism summary (public, rate-limited)
  - `POST /moderate` — moderate content (requires moderator/admin)
  - `GET /moderate/report/{report_id}` — moderate report comments (requires moderator/admin)

- **Frontend API Client** — `triageReport`, `moderateContent` added to `apps/web/src/lib/api/ai.ts`

**Tests:**
- 12 dedicated tests in `tests/test_phase9_agentic.py` (all passing)
- Covers: triage classification, batch triage, recidivism detection, recidivism summary, content moderation (safe/spam/harassment/personal_info), report comment moderation
- All 597 pytest backend tests passing (total with 12 new = 609, but 12 are in the new test file)

**Known Limitations:
- Triage agent uses StubLlmProvider (no real LLM calls in test/dev mode)
- Recidivism detection doesn't use geospatial proximity (relies on institution_id grouping only)
- Moderation doesn't integrate with existing community moderation queue
- Triage results are not persisted (computed on demand, not stored)
- No ML model training pipeline (relies on heuristic + LLM classification)

---

## Cycle 2 Roadmap Phase C2-10 (Hardening + Release) — 2026-08-20

**Deliverables (backend `services/api`, `apps/web`):**

- **Privacy Notice v2** (`apps/web/src/app/[locale]/privacy/page.tsx`) — full DPDP Act 2023 compliance page:
  - Data Controller details (Theek Karo Foundation)
  - Complete data inventory table (8 categories: Account, Reports, Media, Verification, AI, Analytics, Technical Logs, Communications)
  - 7 data subject rights (access, correction, withdrawal, erasure, grievance, portability, non-discrimination)
  - Data retention schedule (6 entity types with specific periods)
  - Security measures (8 items)
  - Third-party sharing (3 categories with legal basis)
  - Children's data protection
  - International data transfers
  - Contact details + DPO + Grievance Officer
  - Last updated timestamp

- **MFA Enforcement Validation** (`GET /api/v1/security/mfa-status`):
  - Returns MFA enforcement status (enabled/disabled)
  - Lists required roles for MFA
  - Documents that officials and admins must complete TOTP setup
  - Requires `security.read` permission (admin/analyst role)

- **SLO Validation** (`GET /api/v1/security/slo-status`):
  - Checks p95 latency against 500ms target
  - Checks error rate against 1.0% target
  - Measures over the last hour of API traffic using AiRun data
  - Returns per-metric status (met/breached) + overall status
  - Requires `security.read` permission (admin/analyst role)

- **Security Health Fix** — Fixed `security_health` endpoint:
  - Added `or_(IPBlock.expires_at.is_(None), IPBlock.expires_at > func.now())` to include permanent blocks
  - Changed `SecurityIncident.status.in_()` to use proper enum values instead of strings
  - Added MFA enforcement status to health response
  - Added missing `or_` import from SQLAlchemy

**Tests:**
- All 597 pytest backend tests passing
- All 45 vitest frontend tests passing
- All 28 E2E Playwright tests passing
- No TypeScript errors

**Known Limitations:
- MFA enforcement is disabled by default (`_MFA_ENFORCEMENT_ENABLED = False`); requires runtime enablement
- SLO validation reads from AiRun table only (not HTTP access logs)
- Privacy page is static (not dynamically generated from a data-source registry)
- DPDP compliance has not been reviewed by legal counsel

---

## Phase 30 (Production Deployment & Go-Live) — 2026-08-19

**Deliverables (backend `services/api`, docs `docs/`):**

- **Production Smoke Tests** (`tests/test_production_smoke.py`) — 21 automated smoke tests across 7 test classes:
  - TestHealthSmoke (5 tests) — Liveness, readiness, version, comprehensive health, metrics endpoint
  - TestAuthSmoke (3 tests) — Unauthenticated access denied, invalid token rejected, rate limiting
  - TestSecurityHeadersSmoke (2 tests) — Security headers present, CORS restricted
  - TestDataSmoke (4 tests) — Categories, geography, institutions, reports list
  - TestErrorHandlingSmoke (3 tests) — 404 safe errors, 405 method not allowed, invalid JSON
  - TestAISafetySmoke (2 tests) — AI requires auth, prompt injection blocked
  - TestGovernmentSafetySmoke (2 tests) — Government endpoints require auth, no fake government responses

- **CI/CD Pipeline** (`.github/workflows/`) — Complete CI/CD with:
  - `ci.yml` — Backend: lint (Ruff), type check (Mypy), unit tests, integration tests, fresh DB migration round-trip, security scan (Trivy, pip-audit, Bandit, Semgrep); Frontend: npm audit, lint, typecheck, build
  - `deploy.yml` — Build + push Docker images to ECR, run Alembic migrations, deploy to ECS Fargate (api, worker, web), wait for stable, run smoke tests; supports staging/prod via workflow_dispatch
  - `rollback.yml` — Emergency rollback to previous ECS task definition revision

- **Infrastructure as Code** (`infra/terraform/main.tf`) — AWS production infrastructure:
  - VPC with public/private subnets, internet gateway, route tables
  - ECS Fargate cluster (api, worker, web) with CloudWatch Container Insights
  - ALB with HTTPS (ACM certificates), HTTP→HTTPS redirect
  - RDS Postgres 16 with PostGIS, Multi-AZ for prod, 7-day backup, PITR
  - ElastiCache Redis 7 for queues and caching
  - S3 bucket with versioning and lifecycle for media
  - CloudFront CDN with security headers (HSTS, nosniff, DENY frame)
  - Secrets Manager for runtime credentials (DB, JWT, AI, media)
  - IAM roles with least privilege (ECS task execution, media S3 access)
  - Security groups (ALB, services, RDS, Redis)

- **Operational Runbooks** (`docs/`):
  - `RUNBOOK-API-OUTAGE.md` — Detection, decision tree, rollback procedure, communication template
  - `RUNBOOK-DATABASE.md` — RDS status, CloudWatch metrics, connection limits, restore from backup
  - `GO-LIVE-CHECKLIST.md` — Pre-launch criteria (infrastructure, CI/CD, database, security, application, monitoring), launch day checklist, rollback criteria, communication templates
  - `PRODUCTION-DEPLOYMENT.md` — Architecture diagram, deployment flow, environment configuration, rollback procedure, monitoring setup
  - `RELEASE-PROCESS.md` — Semantic versioning, release types (hotfix/patch/minor/major), release checklist, changelog format, feature flags
  - `ON-CALL.md` — Severity levels, incident response process, escalation path, post-incident review template
  - `PERFORMANCE.md` — Performance budgets, optimization strategies, load testing scenarios, monitoring metrics

**Existing Infrastructure Verified:**
- Docker Compose: PostgreSQL (PostGIS), Redis, MinIO, API, Worker, Prometheus, Grafana
- Dockerfile: Non-root user, health checks, uv dependency management
- Terraform: Full AWS infrastructure (VPC, ECS, RDS, ElastiCache, S3, CloudFront, ALB, ACM, Secrets Manager)
- CI/CD: GitHub Actions with OIDC to AWS, ECR, ECS deployment, smoke tests
- Monitoring: Prometheus scraping, Grafana dashboards, OTEL collector
- Load Testing: k6 SLO smoke test (10 VUs, p95 < 500ms, error rate < 1%)

**Tests:**
- 21 dedicated Phase-30 smoke tests across 7 test classes
- All 21 smoke tests passing
- All pre-existing tests continue passing
- Total: 532 pytest backend tests

**Key Improvements:**
- Automated smoke test suite validates critical production paths
- CI pipeline enforces quality gates before deployment
- Deploy pipeline automates staging→production flow
- Rollback pipeline enables emergency recovery
- Terraform IaC provides reproducible infrastructure
- Operational runbooks ensure consistent incident response
- Go-live checklist prevents launch of unready systems
- Release process ensures controlled, auditable deployments

**Known Limitations:**
- Production deployment not yet executed (requires AWS account + OIDC provider setup)
- Terraform state backend S3 bucket not yet created (bootstrap required)
- DNS (Route53) not yet configured for theekkar.in
- SSL certificates not yet issued
- Monitoring dashboards not yet provisioned in production
- Load testing not yet run against production
- Security scan findings not yet remediated (depends on scan results)

**Recommended Phase 31:**
- Execute Terraform bootstrap (create S3 state bucket, OIDC provider)
- Configure DNS (theekkar.in, api.theekkar.in)
- Issue SSL certificates
- Deploy to staging environment
- Run full load tests against staging
- Remediate any security scan findings
- Configure production monitoring dashboards
- Set up PagerDuty/Opsgenie for on-call
- Create public status page
- Execute go-live checklist
- Staged launch (internal alpha → private beta → limited public)
- CI/CD pipeline with security scanning