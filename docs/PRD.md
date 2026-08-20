# PRODUCT REQUIREMENTS DOCUMENT — Theek Karo

**Version:** 2.0 (Cycle 2, Phase 1)
**Date:** 2026-08-16
**Status:** Approved (Cycle 2 Phase 1) — supersedes the Cycle-1 PRD; the Cycle-1
implementation (Phases 0–12, see IMPLEMENTATION-STATUS history) is the
**reference baseline** and remains the working system until phases of this
cycle replace/extend it.

---

## 1. Product Vision

**What it is.** Theek Karo ("ठीक करो" — make it right) is an India-first,
AI-native civic platform where every civic issue has a public, verifiable
life: citizens report, communities verify, institutions respond, and the
record is permanent and provenance-labelled.

**Who it serves.** Citizens, volunteers, verified contributors, moderators,
institution representatives (schools, hospitals, ward offices), government
departments, analysts, and administrators — across every level from locality
to nation.

**The problem.** Civic complaints today are fragmented, unverifiable, and
opaque: offline registers, WhatsApp groups, helplines that don't close the
loop, portals that bury answers. Nobody can tell what is true, who is fixing
what, or whether anything improved.

**Why it differs from a complaint portal.**

| Complaint portal | Theek Karo |
|------------------|-----------|
| One-way complaint intake | Two-sided: institutions respond with commitments and evidence |
| Anonymity by default, trust undefined | Every data point carries a declared provenance + confidence tier |
| Static categories | Categories are configurable data, evolving with the country |
| Closed after "resolved" | Permanent, auditable, community-verifiable lifecycle |
| Per-department silos | One graph: issue → institution → geography → analytics |

**How AI improves it.** AI handles the mundane forever-load: classifying and
routing every incoming report, detecting duplicates before humans see them,
translating across 15 Indian languages, extracting facts from images (OCR),
suggesting severity, and drafting responses — always labelled AI, always
human-reviewable where irreversible, always citation-grounded. It converts a
firehose into a decision-ready queue.

**How it scales nationally.** Geography is **configuration, not code**: a
12-level hierarchy (locality → institution → ward → panchayat → block →
subdivision → district → division → state → country) lives in a registry, so
onboarding any state is data work, not development. Institutions onboard as
**digital twins** with their own profile, history, and evidence ledger.
Analytics aggregate upward through the same hierarchy, so "what is happening
in my ward" and "what is happening nationally" are the same query at
different levels. i18n, DLT SMS/email, and a data-ingestion pipeline make each
additional state a repeatable playbook.

## 2. User Personas

| Persona | As a … | They want to … | Guards |
|---------|--------|----------------|--------|
| **Citizen** | any person | report + track + verify issues near them | minimal friction, private by default |
| **Volunteer** | registered contributor | triage, gather evidence, help neighbours | cannot fabricate status |
| **Verified Contributor** | identity-and-consistency-vetted citizen | higher-weight verification votes, evidence review | reputation at stake |
| **Moderator** | community steward | curate posts/comments, moderate feeds | powers audited, appealable |
| **Institution Representative** | principal/medical officer/ward staff | own the institution twin, post commitments + resolutions | must be officially linked to the institution |
| **Government/Department Representative** | department official | assignment, SLAs, official responses | admin-gated, audited, T1 official provenance |
| **Analyst** | researcher/official/public | dashboards, exports, trend queries | aggregate-first, no PII leaks |
| **Administrator** | platform operator | manage categories, hierarchy, institutions, moderation queue | RBAC top of stack |
| **Super Administrator** | platform owner | full system governance, impersonation-safe privileges | break-glass, audited |

## 3. Geographic Hierarchy (configurable)

A hierarchy **registry** (data, not code; no India-specific logic in code):

`Country → State/UT → Division → District → Subdivision → Block/Prakhanda → Panchayat → Municipality → Ward → Village → Locality → Institution`

- Any level may be skipped per region (a ward may sit under a municipality;
  a village under a block — links are declared per row, with parent-kind rules
  in the registry).
- Every node carries: kind, name (+localized names), geometry, parent,
  provenance (source + version), validity window.
- Reports, institutions, analytics, and notifications resolve through the
  hierarchy; **no business logic hard-codes a level name or depth**.
- Localization maps level labels per language ("District", "ज़िला", "जिला").

## 4. Civic Categories (configurable)

Seeded domains (data-driven, extensible per state):

Education · Healthcare · Police · Courts · Roads · Water · Sanitation ·
Public transport · Government offices · Public facilities · Other civic services

Each category: slug, icon, i18n labels, JSON-Schema form fields, verification
policy, attachment rules, routing hints (recommended departments), severity
ladder, display rules. Categories can be regional (state-specific) and
versioned (reports bind to the form version they were filed against).

## 5. Institution Digital Twin

Every institution (school, hospital, ward office, police station…) has a
**profile = one ledger with typed provenance per data point**:

| Data class | Provenance | Example |
|------------|-----------|---------|
| Official data | OFFICIAL (T1) | UDISE+ enrollment, department headcount |
| Government datasets | OFFICIAL (T1) | public directory rows |
| Citizen reports | CITIZEN (T5) | "roof leaks in block A" |
| Verified evidence | COMMUNITY_VERIFIED (T2) | 3 confirms + photos |
| Community activity | COMMUNITY (T3) | comments, follows, subscriptions |
| Historical information | provenance chain | past resolutions, trend data |
| AI insights | AI (T4) | anomaly flags, predictive maintenance hints |

The twin is the institution's public record: **nothing is merged without its
provenance label**, aggregate scores clearly carry their ingredients, and any
single data point can be traced to its source row + retrieval date + license.
Adverse official data is never deleted — only superseded with a new version.

## 6. Reporting Lifecycle

**Happy path:**

`Reported → Submitted → Under Verification → Verified → Assigned →
In Progress → Resolution Submitted → Resolution Review → Resolved →
Community Verified → Closed`

**Negative + administrative states:** `Rejected · Duplicate · Invalid ·
Needs More Information · Reopened · Archived`

Rules: every transition is actor-labelled, append-only in history, and 409
guarded (state machine in code + CHECK constraints). `Duplicate` is a status
wrapping a link to the canonical report (AI *suggests*; humans *apply*).
`Archived` is retention-driven, never lossy (audit persists).

## 7. Evidence

- **Kinds:** images, videos, documents, before/after evidence (paired
  timestamps), structured timestamps, location (accuracy declared), resolution
  proof (official or community).
- **Chain:** every piece of evidence scans first (virus/magic-bytes), then
  associates to a report/verification/resolution with owner + provenance tier;
  metadata is immutable; download is licensed/audited.
- **Trust input:** evidence from verified contributors and official actors
  weights the verification policy; before/after pairs feed resolution review.

## 8. Community

Feed · Posts · Comments · Replies · Reactions · Follows · Subscriptions ·
Notifications · Reputation · Moderation.

- Feed = hierarchy-scoped stream of reports/posts; submissions and institutions
  are followable; subscriptions gate notification channels with quiet hours.
- Reputation: verified-vote weight, helpful-signals; **visible reputation is
  aggregate-only**, never a leaderboard of individual votes for victims of
  abuse. Moderation has a review queue, appeals, and full audit.

## 9. Maps

Markers · Clusters · Heatmaps · Filters · Geographic navigation ·
Institution profiles · Issue visualization · Severity visualization · Timeline.

- Tile-free map-lite baseline (projected SVG) upgraded to real basemaps in V1.
- Geometry-first: markers from report points, institution footprint from the
  twin geometry, clusters by zoom, heatmaps of open issues, severity by
  intensity. Timeline scrubbing on the map is supported by the append-only
  history.

## 10. Analytics

Levels: citizen · institution · ward · panchayat · block · district · state ·
national.

Metrics: open issues · resolved issues · resolution rate · average resolution
time · recurring problems · severity distribution · geographic trends.

- Same query over the hierarchy registry → any level; snapshots append-only;
  drill-down preserves provenance and never exposes PII.

## 11. Multilingual Support

Launch set (15, architecture supports more): English, Hindi, Bengali, Telugu,
Marathi, Tamil, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese, Urdu,
Maithili — plus Bodo/Dogri/Konkani/Sanskrit/Manipuri/Sindhi later.

- Architecture: language registry (code, script, directionality, plural
  rules); web catalogs + server strings + notification templates all resolve
  through the registry with a fallback chain; community translation workflow
  with review status; 10 locales already seeded from Cycle 1 (en, hi, ta, te,
  bn, mr, gu, kn, ml, pa) — Phase 2 of this cycle adds the remaining five.

## 12. AI Use Cases

Classification · duplicate detection · image analysis · OCR · severity
suggestions · department routing · translation · moderation · RAG ·
government-information comparison · resolution-verification assistance ·
analytics · natural-language search · civic assistant.

Rules: all AI output is T4-labelled; every model call is logged
(PII-insulated); irreversible actions (merges, moderation strikes) require
human decision; RAG cites only provenanced sources; a civic assistant
answers only from the platform's verified corpus + provenanced datasets.

## 13. Trust (declared provenance, five tiers)

| Tier | Label | Meaning |
|------|-------|---------|
| T1 | **Official** | published by a government/institution account or imported from a licensed official dataset |
| T2 | **Community Verified** | report + evidence satisfying the category verification policy |
| T3 | **Citizen Reported** | a citizen submission with identity, unverified |
| T4 | **AI Generated** | AI summary/insight — never self-promotes to any other tier |
| T5 | **Unverified** | anonymous/remnant data with no identity or evidence |

Enforced at schema level (CHECK constraints); UI always renders the tier.

## 14. Security

Authentication (OTP + password, console dev channel; DLT SMS in V1) ·
Authorization (RBAC per §2 with permission keys per module) · OAuth (account
linking for official persona verification in V1) · Password reset (V1) ·
MFA readiness (TOTP scaffolding designed; enabled for officials/admins at
launch hardening) · Privacy (consent registry, private-by-default,
anonymisation flows per DPDP) · Audit logs (append-only) · Rate limiting ·
Secure uploads (presigned, scanned, size-bounded). Baseline hardening from
Cycle 1 (security headers, secrets manager, runbooks) carries forward.

## 15. MVP (P0–P3)

**MVP = one pilot geography, three categories fully closed-loop.**

### P0 (must be in MVP)
1. Accounts + OTP login + citizen persona
2. Hierarchy registry for state → district → block → ward + locality
3. Three categories live (school, road, water) with versioned forms
4. Report lifecycle: Reported → … → Closed with negative states
5. Evidence upload (photo/doc) with scan gate
6. Institution digital twin (school) with official + citizen data separated
7. Comments + follow + notifications (in-app + SMS/email sandbox)
8. Moderation of comments/reports (basic queue)
9. Maps: markers, clusters, filters, ward/block navigation
10. Analytics at institution/ward/district level (7 metrics)
11. i18n: English + Hindi first; architecture ready for 15
12. Trust tiers rendered everywhere; audit trail on every mutation

### P1 (V1)
Verified-contributor program, video evidence, resolution proof workflow,
heatmaps + severity viz, national-level analytics, 15 languages, official
persona + OAuth, department routing + SLAs, civic assistant MVP, analytics
exports, avatars/reputation, native mobile/PWA offline mode.

### P2 (V2)
Other categories + regional category catalogs, OCR + image analysis +
before/after auto-frames, predictive/recurring-problem analytics, agentic
assistant (multistep tasks), community translation workflow, advanced
moderation (ML-assisted), institution self-service tools.

### P3 (V3)
National scale: all 28 states onboarding toolkit, multi-department workflow
engines, policy analytics, decision-support furniture for state/national
levels, federation (interoperability with other platforms), complete
agentic governance layer.

## 16. Future Roadmap (V1–V3)

- **MVP (V0)** — pilot geography closed loop (§15 P0)
- **V1** — platform for one state (P1): verified community, official
  personas, full i18n, dashboards everywhere
- **V2** — multi-state with agentic assist (P2): autonomous triage has a
  human-in-the-loop SLA, recidivism analytics, ML moderation
- **V3** — national engine (P3): state onboarding playbook, federation,
  policy analytics, agent-capable public assistant

## 17. Phase 14 Addendum — Departments, Civic Cases & Resolution Workflow (implemented 2026-08-17)

Satisfies and operationalizes the P0/P1 institutional-engagement criteria
("institution rep commits and resolves with proof", "second citizen
confirms"; §2 personas, §6 lifecycle):

- **Department registry** — `department_types`/`departments`/
  `department_categories` + per-category `jurisdiction_scopes` (full /
  geography / institution). Public directory; organization verification
  (`pending → verified | suspended | revoked`) grants verified
  membership (`member` | `manager` | `reviewer`).
- **Civic case lifecycle** — cases open from reports with a public
  `TK-YY-xxxxxxxxxxxx` case number; append-only status history + assignment
  chain; action items (to-do) and responses (public vs internal note);
  citizen agency = reopen requests (never direct status mutation).
- **SLA + escalation** — data-driven `SlaPolicy` (weighted match, default
  fallback), pause/resume with accumulated pauses, 60-second worker sweep
  (`evaluate_sla_due`), idempotent escalation capped at level 5.
- **Resolution workflow** — evidence submissions (photo / before_after /
  document), independent review (`verified | more_evidence_required |
  rejected | partially_verified`) with self-review forbidden; resolution
  verified → case resolved with `resolution_verified_at`.
- **Access** — department-scoped case visibility; citizens see only their
  own cases; every mutation audited in status history.

### Phase 14 acceptance status (PRD §B mapping)

| MVP acceptance criterion | Status |
|--------------------------|--------|
| B.1 institution rep commits and resolves with proof | ✅ implemented: action items + evidence-backed resolution + review gate; E2E covered by `tests/test_phase14_cases.py` lifecycle test |
| B.2 second citizen confirms (community confirm) | ✅ implemented (Phase 15): reporter + one more citizen post `observed_improvement` follow-up signals → two-confirmer gate sets `cases.community_confirmed_at`; resolution reviewer closes via the existing `resolved → closed` transition. "Issue still exists" signals aggregate into a human-reviewed reopen signal (never auto-reopens). See IMPLEMENTATION-STATUS Phase 15 |
| B.6 409 guards on the lifecycle; audit rows on every mutation | ✅ status history is append-only and written on every transition |
| B.7 load/SLO at pilot scale | Deferred to hardening phase (10) |

---

## Appendices

### A. Feature Matrix (extract)

| Feature | MVP (P0) | V1 | V2 | V3 |
|---------|:--:|:--:|:--:|:--:|
| OTP login + citizen | ✅ | | | |
| Hierarchy registry | ✅ | | | |
| Categories as data (3) | ✅ | +regional | +more | all |
| Full lifecycle + negatives | ✅ | | | |
| Evidence (photo/doc) | ✅ | +video | +OCR auto | |
| Institution twin | ✅ | +departments | +self-service | +federation |
| Community feed/comments/follow | ✅ | +reactions/reputation | +ML mod | |
| Maps (markers/clusters/filters) | ✅ | +heat/severity | +timeline scrub | |
| Analytics | ward→district | +state | +national | +policy |
| i18n | hi, en | 15 | community workflow | |
| Civic assistant | — | MVP | agentic | national agent |
| Digital-twin AI insights | — | flags | predictive | policy-grade |

### B. Acceptance Criteria (MVP gate)

1. A citizen in the pilot geography reports via web in Hindi or English with
   photo evidence; a volunteer verifies; the institution rep commits and
   resolves with proof; a second citizen confirms; status reads Closed with
   the full timeline public.
2. Every screen displays a trust tier for every piece of information.
3. Duplicate detection suggests; only a human marks Duplicate; the link is
   visible forever.
4. Analytics at ward/block/district compute the 7 metrics and preserve
   provenance.
5. Zero serious/critical accessibility violations on core flows; both
   languages render fully.
6. Migration round-trip verified on a fresh database; 409 guards on the
   lifecycle; audit rows on every mutation.
7. Load test holds p95 < 500 ms and < 1% 5xx on the pilot routes.

### C. Major Risks

| Risk | Mitigation |
|------|-----------|
| Official-data licensing (UDISE+ etc.) | License assessment before import; honest "no data" fallback (ADR-006) |
| Institutional engagement in pilot | Co-design onboarding; twin value from day one; local champions |
| Abuse/false reports at scale | Verified-contributor program, moderation queue, reputation |
| AI errors on irreversible actions | Human-review gates; eval floors; T4 labelling |
| Language/script rendering gaps | Script-aware fonts, QC screenshots per language |
| National scaling data quality | Registry as data; ingestion playbook; provenance required |

### D. Dependencies

- DLT-registered SMS provider (V1 onboarding gate; console sandbox until then)
- Official data licensing (schools/enrollment) for twin completeness
- Counsel review of privacy/terms + DPDP memo (close-out tracked)
- Cloud account bootstrap for the validated Terraform (ECS/RDS/ElastiCache)
- Civic-assistant eval corpus (golden sets per category)

### E. Architectural Implications

1. **Hierarchy as registry** — new tables/kinds must remain configuration;
   analytics/reporting resolve through it (no hard-coded India logic).
2. **Digital twin** — one provenance-typed ledger; replaces naive
   "institution as category" modelling.
3. **Lifecycle v2** — new states (Resolution Submitted/Review, Community
   Verified, Archived) extend the Cycle-1 machine; ALL state-machine rules
   stay data/registry-driven.
4. **i18n** — language registry deeper than dictionaries (plural rules,
   scripts, server strings, notifications); 5 new locales + community review
   workflow.
5. **AI/agentic** — gateway + eval harness already exist from Cycle 1;
   V2 agents compose the same units (classify → route → draft → cite).
6. **Maps** — replace map-lite with a real tile layer behind the same
   marker/cluster API in V1.
7. **Security** — RBAC keys, OAuth identity linking, MFA scaffolding and
   password reset are additive to the Cycle-1 auth core.