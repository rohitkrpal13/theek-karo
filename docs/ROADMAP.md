# ROADMAP — Cycle 2 (new product scope)

**Project:** Theek Karo
**Version:** 2.0 (Cycle 2, Phase 1)
**Date:** 2026-08-16
**Status:** Approved (Phase 1) — supersedes the Cycle-1 roadmap. The Cycle-1
implementation (Phases 0–12, all green) is the **reference baseline**; this
roadmap sequences the new product scope (digital twins, 12-level hierarchy,
15-language i18n, community, maps, analytics, agentic AI) on top of it.

---

## 1. Principles

- Ship small, verifiable increments; nothing starts until the previous exits
  green (tests, lint, typecheck, docs, completion report).
- Product truth lives in `docs/PRD.md` (§2–§16) — this file sequences it.
- **Configuration over code**: hierarchy, categories, institutions, language
  tables, and state-machine rules are data. Anything hard-coded to a region
  is a defect.
- Provenance is non-negotiable: any data point without a declared tier or
  source is a bug (ADR-006 spirit applies to the whole product).

## 2. Product Roadmap

### MVP (V0) — pilot geography, closed loop
**Scope (PRD §15 P0):** OTP accounts; hierarchy registry (state→ward+locality);
3 categories (school, road, water); full lifecycle incl. negative states;
evidence (photo/doc) w/ scan gate; **institution digital twins (school)**;
comments/follow/notifications; basic moderation; markers/clusters/filter
maps; ward..district analytics; hi+en; trust tiers everywhere.
**Exit:** PRD Appendix B acceptance criteria green on the pilot geography.

### V1 — one state
Verified contributors; video evidence; resolution-proof workflow; heatmap +
severity maps; state-level analytics; 15 languages; official personas +
OAuth; department routing + SLAs; civic assistant MVP; offline-first PWA.

### V2 — multi-state, agentic assist
Regional category catalogs; OCR + image analysis + before/after auto-frames;
recidivism/predictive analytics; **agentic assistant** (multistep tasks with
human-in-the-loop SLA); ML-assisted moderation; community translation
workflow; institution self-service.

### V3 — national engine
All-28-states onboarding playbook; multi-department workflow engines;
policy-grade analytics; federation with other platforms; complete agentic
governance layer (audited, gamble-zero on irreversible actions).

## 3. Engineering Sequence (Cycle 2 phases)

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **1** | Product spec + architecture foundation (this set: PRD/ROADMAP/UX/STATUS; feature matrix, journeys, acceptance criteria, risks, deps, implications) | Docs cross-checked; no code |
| **2** | Baseline reconciliation + platform deltas: hierarchy registry (12-level, no hard-codes), 5 new locales (or, as, ur, mai + script QC), OAuth/password-reset/MFA scaffolding, RBAC permission keys | Registry data-driven; fresh-DB round trip incl. new kinds; auth deltas tested |
| **3** | Lifecycle v2 + digital twins: new states (Resolution Submitted/Review, Community Verified, Archived) + registry-driven rules; school twin ledger w/ provenance-typed fields; institution personas | Twin CRUD + provenance typing; lifecycle extensions tested incl. 409s |
| **4** | Community + moderation: feed, posts/replies/reactions, reputation (aggregate-only), moderation queue + appeals, subscriptions | Moderation actions audited + appealable; reputation privacy-guarded |
| **5** | Maps v2 + evidence v2: real tile basemap behind the marker/cluster API, heatmaps + severity + timeline scrub; video + before/after evidence chain | Map features behind one API; evidence chain with scan + tiers |
| **6** | Analytics platform: 7 metrics × all hierarchy levels (snapshot pipeline), exports, drill-down preserving provenance | Level-agnostic query; PII-safe exports |
| **7** | i18n full: 15 languages live (web catalogs + server strings + notification templates), community translation workflow, script QC pass | All 15 render; fallback chain tested |
| **8** | AI + civic assistant: assistant MVP on the existing gateway/eval; official-persona Q&A; department routing + SLA framework | Assistant answers cite-only provenanced sources; eval floors held |
| **9** | Agentic capabilities (V2): triage agents with human-in-the-loop SLA, recidivism analytics, ML moderation assist | Agent decisions auditable; none irreversible without human |
| **10** | Hardening + release: MFA enforcement for officials, load/SLO gates at scale, DPDP/counsel close-out, privacy notice v2 | Checklist closed; SLOs hold under k6 |
| **11** | Deploy: cloud bootstrap (validated Terraform), DLT SMS onboarding, institute pilot onboarding | Pilot geography live; first campaign data |

**Completed out of original sequence (tracked in IMPLEMENTATION-STATUS.md):**
Phase 4 (community + moderation) shipped as **Phase 13**; the department
registry + SLA framework originally stubbed in Phase 8 shipped as **Phase 14**
(departments, civic cases, SLA clocks, escalation engine, resolution workflow,
frontend routes `/cases`, `/departments`, `/admin` departments tab); the
community-confirmation slot left open by Phase 14 shipped as **Phase 15**
(PRD §B.2 two-confirmer gate: citizen follow-up signals, reopen-signal review
queue, analytics) — all exit-criteria gates of §4 met. **Phase 5** (maps v2
+ evidence v2) completed 2026-08-20 — heatmap/timeline endpoints, video evidence,
evidence chain. **Phase 7** (i18n full) completed 2026-08-20 — 15 languages
registered, en+hi fully translated. **Phase 8** (AI assistant polish) completed
2026-08-20 — conversation persistence, deep-dive tools, source freshness,
multi-turn context. **Phase 9** (agentic capabilities) completed 2026-08-20 —
triage agent, recidivism analytics, ML moderation. **Phase 10** (hardening)
completed 2026-08-20 — DPDP privacy notice, MFA/SLO validation endpoints.
Remaining queue: **Phase 11** (cloud deploy) — requires AWS account + DLT SMS
provider. Suggested next phase: **Phase 11 — cloud deploy** (Terraform bootstrap,
DNS, SSL, staging deployment, load testing).

## 4. Definition of Done (every phase)

1. All planned scope implemented (no TODOs as features).
2. Tests for new behaviour + regression suite green.
3. Lint/format/typecheck green for touched services.
4. Security review per `docs/SECURITY-CHECKLIST.md`.
5. Docs updated: relevant source-of-truth + IMPLEMENTATION-STATUS.md.
6. Known limitations + next recommendation in the completion report.

## 5. Milestones

| Milestone | Product | Phases |
|-----------|---------|--------|
| M0 "Loop" | MVP pilot closed loop | 2–6 (subset per P0) |
| M1 "State" | One-state platform | 7–8 |
| M2 "Multi" | V2 agentic assist | 9 |
| M3 "National" | V3 engine | 10–11 + data |

## 6. Open Questions (tracked, not blocking)

- DLT SMS provider + pricing (V1 gate; console sandbox until then)
- Official-data licensing for twins (UDISE+; assessed in PROVENANCE.md)
- Agentic assistant hosting + eval corpus per category (Phase 9 spike)
- Community translation incentive model (Phase 7 design)