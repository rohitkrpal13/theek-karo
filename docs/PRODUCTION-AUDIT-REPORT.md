# Production Audit Report

Theek Karo — audit & hardening pass covering the 101-point production-readiness spec.
Scope: `services/api` (FastAPI) and `apps/web` (Next.js), verified against live services.

## Inventory

| Area | Findings |
| --- | --- |
| Backend API | 242 endpoints audited; auth matrix, rate-limit tiers, error contract (RFC 9457), status enums |
| Frontend | Routes/components, i18n (en/hi), a11y (dialogs, focus), status enums diverged from API |
| Data & integrations | DB models/migrations, seed scripts, notifications callbacks, OAuth |
| Infra/CI | deployment envs (`dev/test/staging/prod`), readiness validation, docs |

## Fixes Landed

- **OAuth**: replaced fabricated mock token exchange with a real Google token exchange
  (`auth/service.py`); redirect-URI allowlist (400 `invalid_redirect_uri`), prod returns
  503 `oauth_not_configured` when client id is unset; `oauth_mock_enabled` is dev-only
  and rejected by prod readiness validation.
- **Notifications**: delivery receipts (`POST /receipts`) now require the
  `X-TK-Callback-Key` header (constant-time compare, `notification_callback_secret`).
  Open in sandbox; 403 `invalid_callback_signature` in prod.
- **Rate limits added**: reports list/detail/comments (120/min/IP), all GIS GETs
  (60/min/IP), media download (60/min/IP via shared dependency).
- **AI access control**: `access_level` derived from real role codes
  (`admin/super_admin` → ADMIN; `moderator/official/analyst` → MODERATOR).
- **Frontend**: report status union synced to API (17 statuses); theme color fix
  (`#c2410c` → brand `#157F4A`); wizard submit strings i18n'd; `FormattedDate` is
  locale-aware; privacy page has a real contact; root page now redirects to `/hi`;
  Modal/Drawer use a focus trap (keyboard a11y).
- **Demo seed**: `services/api/scripts/seed_demo_data.py` — 4 accounts
  (`admin/moderator/officer/citizen@theekkar.test`, `DevPassw0rd!2026`),
  `demo-development` department + manager membership; refuses prod env.

## Verification Gates

| Gate | Result |
| --- | --- |
| API pytest | **582 passed / 1 skipped** |
| ruff (`src/tk_api/`) | clean |
| mypy (`src/tk_api/`) | clean (208 files) |
| OpenAPI contract snapshot | regenerated, matches live schema |
| Web lint | 0 errors / 0 warnings |
| TypeScript `tsc --noEmit` | clean |
| Vitest | 45/45 passed |
| `next build` | OK |
| Playwright e2e | **28/28 passed** (incl. journeys 3+4; journey 4 x3 repeat = stable) |

## E2E Journey Matrix

| # | Journey | Coverage |
| --- | --- | --- |
| 1–2 | Core flows (citizen report → dashboard; public render) | wizard submit (422 regression), categories, statuses |
| 3 | Citizen reports → moderator verifies via UI | register/login, OTP, report post, verify panel, trust promotion |
| 4 | Authority: 2-verification trust gate → case → response → transitions → resolution proof | departments, case create, respond, transition chain, resolution submit |
| budget | Home load budgets on low-end device | performance |

## Known Residual Risks

- Two DB integration tests (`test_ai_db`, `test_civic_db`) are order-dependent against
  the shared compose Postgres; pass standalone — pre-existing, not introduced here.
- Git unavailable in this workspace (Xcode license) — changes are uncommitted.
- Prod deploy still requires real credentials (Twilio/SMTP/Google OAuth) and CI-workflow
  verification — environment-dependent, out of scope for this pass.

Status: **PASS** — all runnable gates green; deployment-specific items documented above.