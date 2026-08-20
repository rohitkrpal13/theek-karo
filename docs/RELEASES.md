# Release Process

**Status:** Live (Step 16)
**Mechanics:** GitHub Actions (`.github/workflows/`) + ECS Fargate (terraform)

## 1. Versioning & branches

- `main` is the trunk; every merge to `main` runs CI (`ci.yml`) and, when
  `services/api/**` or `apps/web/**` changed, the deploy pipeline.
- Deploys are **immutable images** tagged `:latest` + `:<sha>`; ECS tasks are
  updated to the exact `<sha>` tag (no floating tags in task definitions).
- No semver ceremony required for internal deploys; keep `services/api/src/tk_api/__init__.py`
  `__version__` bumped for externally visible releases (public API consumers).

## 2. CI gates (must pass before deploy)

1. `api-gates`: ruff (lint + format), mypy (strict), unit + contract tests
   (OpenAPI snapshot diff fails the build).
2. `integration`: compose Postgres/Redis/MinIO round-trip (`-m integration`).
3. `fresh-db-migrations`: `alembic upgrade head → downgrade base → upgrade head`.
4. `security-scan`: Trivy (image + repo fs, HIGH/CRITICAL) + `pip-audit`.
5. `web-gates`: `npm audit` (HIGH+), eslint, `tsc --noEmit`, production build.

## 3. Deploy order (`deploy.yml`)

1. **Build & push** — API and WEB images to ECR (`:<sha>` + `:latest`).
2. **Migrations** — `alembic upgrade head` against the target DB **before**
   any new task rolls (backward-compatible migrations are mandatory; a
   forward-only migration that breaks the old task blocks the release).
3. **Deploy** — ECS `update-service` with the pinned image, per service in
   parallel (`api`, `worker`, `web`); wait for `services-stable`.
4. **Smoke** — hit `/readyz` and a public endpoint on the deployed URL.

### Pre-deploy DB snapshot (rollback safety)

Before deploying a migration to **prod**, take a manual RDS snapshot:

```bash
aws rds create-db-snapshot \
  --db-instance-identifier tk-prod-pg \
  --db-snapshot-identifier pre-deploy-$(date +%Y%m%d-%H%M)
```

## 4. Rollback (`rollback.yml`)

- Manual trigger (workflow_dispatch): choose environment, service (or `all`),
  and optionally a specific ECS task-def revision (defaults to the previous
  revision).
- **Data** is not rolled back: migrations are forward-only. If a migration
  must be reverted, restore from the pre-deploy RDS snapshot (see
  `DISASTER-RECOVERY.md`) — never hand-edit `alembic_version`.
- After rollback, re-run smoke + fix forward (a corrected release is preferred
  over staying on the old revision).

## 5. Post-release verification

- `/readyz` 200 with `checks.database: ok`.
- Access logs (JSON, `request_id`) visible in CloudWatch for the new revision.
- One end-to-end civic flow (report → comment → notification) against the
  deployed environment.
- If AI auto-analysis is enabled, confirm `ai_runs` rows are being written.

## 6. Deploy windows

- Staging: any time.
- Prod: prefer off-peak (post-midnight IST); no prod deploy during a known
  incident without the on-call's sign-off (see `RUNBOOKS.md`).
