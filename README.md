# Theek Karo

India-first, AI-native civic intelligence platform: discover, understand, report, verify,
collaborate, track, resolve, and measure improvement of civic issues.

See `docs/` for source-of-truth documents (PRD, architecture, API, security, roadmap, status).

## Repository layout

```
apps/web/       Next.js frontend (Phase 7)
services/api/   FastAPI backend
services/worker/ Celery workers (Phase 8)
packages/       shared types/schemas (later)
infra/          infrastructure (Docker, terraform)
docs/           source-of-truth documentation
```

## Local development

Requirements: Docker, uv (or pip).

```sh
make up        # build and start postgres, redis, minio, api
curl http://localhost:8001/healthz   # -> {"status":"ok"}
curl http://localhost:8001/readyz    # -> {"status":"ok","checks":{"database":"ok"}}
make test      # api unit tests
make test-integration  # api tests against compose postgres (needs: make up)
make migrate   # alembic upgrade head
make lint      # ruff lint
make typecheck # mypy
make down      # stop services
```

Host ports (remapped from defaults to avoid conflicts with other local projects):

| Service | Host port | Container port |
|---------|-----------|----------------|
| API | 8001 | 8000 |
| Postgres/PostGIS | 5434 | 5432 |
| Redis | 6380 | 6379 |
| MinIO API | 9000 | 9000 |
| MinIO console | 9001 | 9001 |

For Python tooling without Docker: `cd services/api && uv sync && uv run pytest`.
