# UX DESIGN — Theek Karo

**Version:** 2.0 (Cycle 2, Phase 1)
**Date:** 2026-08-16
**Status:** Approved — personas + user journeys per PRD §2; MVP scope per
ROADMAP M0. The Cycle-1 web (Next.js PWA, axe-clean, hi+en) is the UX
baseline to extend.

---

## 1. Design Principles

1. **Trust is visible**: every information block carries its tier badge
   (T1 Official · T2 Community Verified · T3 Citizen · T4 AI · T5 Unverified)
   and, where it matters, its source.
2. **Closed loop first**: the citizen's core expectation is "will it get
   fixed?" — status, next actor, and evidence always visible.
3. **One-handed mobile-first**: primary actions within the thumb zone;
   desktop merely relaxes.
4. **Configuration not special-casing**: new hierarchy levels, categories,
   and languages never require design changes.
5. **People before numbers**: reputation is aggregate-only; victims of
   harassment are protectable; moderation is visible and appealable.
6. **Accessibility is a feature**: WCAG 2.2 AA on all core flows; both
   scripts must render beautifully (Devanagari + Latin first).

## 2. User Journeys (MVP)

### J1 — Citizen: report → track → verify → close
1. Opens app (hi/en), sees nearby issues on the map.
2. Taps "Report" → wizard: category → schema-driven fields → photos →
   location pin → review (T3 label shown).
3. Receives ticket + SMS/sandbox confirm; follows the issue.
4. Watches transitions (each with actor + reason); verifies by confirm/refute
   once it's open to voting (self-report veto applies).
5. After resolution, sees before/after + official proof; can community-verify.
**Success:** one minute to submit; full transparency in the timeline.

### J2 — Volunteer: triage
1. Queue: unverified reports in my geography.
2. Confirms by visiting/evidence; requests "needs more information" when thin.
3. Gets reputation-visible-credit (aggregate only).
**Success:** quarantineable junk; real issues promoted fast.

### J3 — Institution Representative (school principal)
1. Claims the school twin via official link (OAuth + verification).
2. Views twin: official data (T1) + citizen-reported issues (T3) separately.
3. Assigned list → commits (visible) → resolves with photo proof (T1).
4. Rejects junk with reason (never silently).
**Success:** one dashboard = the school's public record.

### J4 — Moderator
1. Review queue (reports, comments, replies).
2. Acts (hide/flag/remove) with reason; user appeals; decision audited.
**Success:** abuse visible and bounded; zero un-reversible actions.

### J5 — Analyst (ward/block/district)
1. Picks geography → 7 metrics (open/resolved/rate/time/recurrence/severity/trend).
2. Drills into any number; exports; every number links to its provenance.
**Success:** evidence-backed answers for citizens and officials.

### J6 — Government/Department Representative
1. Assigned by SLA; official response with tier T1.
2. Bulk actions (batch-close batches of validated duplicates/archived rows).
**Success:** department-level KPIs from the same dashboard.

## 3. Information Architecture (MVP)

```
Home (map + nearby)          — public
  Explore (filters: geography, category, status, severity)
  Geography pages (state→district→block→ward: analytics + institutions)
  Institution twin profile   — public
  Report detail (timeline, evidence, tier blocks, verifications)
  Submit wizard             — citizen
  Auth (register/login/verify)   — all personas
  Notifications inbox       — logged-in
  Moderation queue          — moderator/admin
  Admin: hierarchy registry, categories, institutions, moderation config
Static: Privacy, Terms (counsel drafts), About
```

## 4. Trust Rendering Rules

- Level A (whole block): Tier badge + logos for T1/T2.
- Level B (element): small badge (T3 voice, T4 AI).
- Level C (footnote): provenance chip → source row, retrieval date, license.
- Never render T4 as if human; never hide T5.

## 5. Tier / Component Reference (MVP)

Wizard (schema-driven, required-fields enforced), Timeline stepper (12
states), Evidence gallery (scan gate visible), Twin dashboard (provenance
ledger), Map + filters, Feed snippets, Analytics cards (7 metrics),
Notification preferences (quiet hours), Moderation queue.

## 6. Accessibility (WCAG 2.2 AA — carries from Cycle 1)

Skip links, visible focus, contrast tokens, reduced-motion, aria steppers,
axecore in CI, per-language script QA (Devanagari first, then Urdu/RTL when
it lands). Map interactions always have non-map equivalents (list view).

## 7. Performance Budgets (MVP)

p95 API < 500 ms (SLO); web LCP < 4.5 s on a throttled low-end device; JS
transfer < 400 KB for the shell; map-lite/offline shell retained until V1
tiles. Verified with the existing k6 + Playwright budget specs.

## 8. RTL & Scripts (futures)

Urdu (RTL) lands in the V1 set: layout mirroring is design-system-level,
not per-page; catalog strings already direction-aware.

## 9. Implemented Phase 6 Core Frontend Interfaces

- **AppShell & Global Header**: Top desktop navigation + mobile bottom navigation thumb zone (`/[locale]/...`), real-time debounced `GlobalSearch` combobox with domain filter tabs, 14-language selector, and theme toggle (Dark/Light).
- **Home (`Landing.tsx`)**: Dynamic category navigation, real-time civic impact counters, live recent reports list, and interactive map preview.
- **Explore (`/explore`)**: Dynamic multi-level geography hierarchy drilldown without hardcoded levels, category/status/severity filter bar, and dual Map/List layout.
- **Institutions Directory & Digital Twin (`/institutions`, `/institutions/[id]`)**: Institution cards with operational status, verification badge, official ID; Digital Twin view with dynamic infrastructure & staffing attributes, linked reports, issues tabs (Open, In Progress, Resolved), and provenance chips.
- **Reports Feed & Detail (`/reports`, `/reports/[id]`)**: Filtered reports feed; Detail page with ticket number, severity badge, dynamic category schema fields, lifecycle status stepper, GPS location map, community verification vote controls, and discussion thread.
- **Report Submission Wizard (`/submit`)**: 6 accessible steps: Category selection → Location/GPS coordinates → Optional institution association → Issue type & schema attributes → Evidence staging → Idempotent review & submission.
- **User Profile (`/profile`)**: Privacy-preserving citizen dashboard with submission history, reputation score, and auth management.

## 10. Implemented Phase 14 Case & Department Interfaces

- **Departments Directory (`/[locale]/departments`)**: public registry — department cards (type, status badge, jurisdiction scope), search, and "my departments" section; verified members see their memberships and role; citizens can file an organization verification request inline (borrows no membership until approved).
- **Cases List (`/[locale]/cases`)**: role-aware list — citizens see their own case numbers and statuses; department members see department-scoped cases with filters (status, department, search); case rows carry `TK-…` numbers, status badges, SLA health, and department.
- **Case Detail (`/[locale]/cases/[id]`)**: public timeline (status changes + public responses; internal notes shown only to staff), case status stepper, SLA panel (deadline, pause/resume for admins), action items, escalation level 1–5 history, resolution submit (staff) / review (reviewer) with evidence list, and citizen reopen request flow.
- **Department Admin (`/[locale]/admin` → "Departments & Cases" tab)**: department type management, registry create/edit/archive, member add/role/promote, and the verification queue (approve → auto-membership, suspend, revoke) with inline state badges.

### Case status tone mapping (consistent across surfaces)

- Grey: `reopened`, `closed` — terminal/inert states.
- Blue: `under_review`, `verified`, `assigned`, `acknowledged` — in progress, no friction.
- Amber: `action_planned`, `action_in_progress`, `waiting_for_information`, `resolution_rejected`, `out_for_comment` — attention needed.
- Red: `unassigned`, `rejected` — needs staff action.
- Green: `partially_resolved`, `resolved` — outcomes.