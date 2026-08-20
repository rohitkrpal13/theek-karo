# Security Testing Strategy (SAST / DAST / Red Team)

**Status:** Live (Step 18)
**Applies to:** CI pipeline, staging, pre-go-live pentest

## 1. SAST (static) — runs in CI on every push/PR

| Check | Tool | Scope | Gate |
|---|---|---|---|
| Python lint | ruff | all source | must pass |
| Type checking | mypy (strict) | `src` | must pass |
| SAST (Python patterns) | Bandit | `services/api/src` | 0 findings (High/Med/Low) |
| SAST (semantic rules) | Semgrep (`--config=auto`, ERROR+WARNING) | `services/api` (src + migrations + scripts) | 0 findings |
| Image + repo scan | Trivy (fs + image, HIGH/CRITICAL) | API image + repo | exit-code 1 on findings |
| Python dependencies | pip-audit | `pyproject.toml` | no known vulns |
| npm dependencies | npm audit | `apps/web` | HIGH+ fails |
| Authorization/IDOR | dedicated test suite | `tests/test_security_authorization.py` (reports, evidence, objects, thumbnails, cases/tenants) | must pass |
| Upload security | `tests/test_media.py::TestUploadHardening` (spoof MIME, polyglot, decompression bomb, size limits, rate limits) | media pipeline | must pass |
| AI safety | `tests/test_ai_safety.py` (tool authorization, daily chat cap) | AI layer | must pass |
| PII/retention | `tests/test_retention_purge.py` | retention job | must pass |

**Wired (2026-08-18):** Bandit + Semgrep run in the `security-scan` CI job on
every push/PR (`uvx bandit -q -r src` and `uvx semgrep scan --config=auto`),
failing the pipeline on any finding. The initial run surfaced and fixed 7
Bandit findings (hardcoded-looking credentials → named constant + `# nosec`;
`except Exception: pass` → narrow `ValueError` handling; f-string SQL → static
SQL/bound params; MD5 for entity keys → `usedforsecurity=False`; SSRF blocklist
literal + beat schedule path → justified `# nosec`) and 5 Semgrep findings
(dynamic `text()` SQL → SQLAlchemy Core `table()`/`select()`; constant-only
migration DDL/seed + ops CLI download URL → justified `# nosemgrep`). Remaining
pre-go-live item: staging ZAP active scan.

## 2. DAST (dynamic) — prep for staging

Recommended tool: **OWASP ZAP** (baseline + full scan) against a staging
deployment with a seeded dataset.

```bash
# Baseline (passive) — fast, catches header/misconfig issues
docker run --rm -t ghcr.io/zaproxy/zaproxy zap-baseline.py \
  -t https://staging.example.com -r zap-baseline.html

# Full active scan (slower; run off-peak, rate limits will 429 — whitelist the
# scanner IP in staging rate-limit config)
docker run --rm -t ghcr.io/zaproxy/zaproxy zap-full-scan.py \
  -t https://staging.example.com -r zap-full.html
```

DAST focus list (verified by existing suites, re-verify via ZAP):
- IDOR on `/reports/{id}`, `/cases/{id}`, media/evidence objects + thumbnails
- Auth: MFA gate, login backoff, token rotation/reuse detection
- Upload endpoints: MIME spoof, size limits, scan gate
- Comment/initiative/group abuse: rate limits, capacity, ownership
- Security headers: CSP, X-Frame-Options, nosniff, HSTS on web + API

## 3. Red Team prep (manual / supervised)

Scope boundaries (never in prod without written authorization):
- **Auth & session**: refresh-token reuse, MFA bypass attempts, password-reset
  token abuse, session fixation.
- **IDOR / privilege escalation**: cross-tenant case access, moderator
  escalation, group-role confusion (owner vs moderator), initiative ownership
  bypass.
- **Abuse**: report bombing (dedup + aggregation), reaction rings, mass
  duplicate comments, follow spam, volunteer data scraping.
- **AI red team** (Phase 18 §198): prompt injection against the assistant
  (system-rule override attempts), political-persuasion refusal, false
  accusation generation, doxxing attempts via tool calls, private-data
  extraction through `find_related_reports`/`summarize_discussion`, and
  fake-civic-campaign generation. Expected behavior: refuse or stay
  evidence-grounded; tool calls are role-guarded (Step 12).
- **Infra**: bucket policy review (private + versioned), presigned URL expiry,
  Redis auth, RDS security group, secret rotation.

Deliverable per engagement: findings report with severity, repro, and fix
owner; S1/S2 findings block go-live.

## 4. Test-data safety

- All red-team/DAST activity runs against **staging** with synthetic data
  (never real citizen data; see PII-DATA-INVENTORY.md §1).
- Scanner IPs are documented in the staging rate-limit allowlist; scans are
  scheduled outside quiet hours to avoid OTP/SMS provider abuse.
