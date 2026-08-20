.PHONY: lint format format-check typecheck test up down ps logs migrate seed-civic eval-ai update-contracts web-dev web-lint web-test-build web-e2e

lint:
	cd services/api && uv run ruff check .

format:
	cd services/api && uv run ruff format .

format-check:
	cd services/api && uv run ruff format --check .

typecheck:
	cd services/api && uv run mypy src

test:
	cd services/api && uv run pytest

test-integration:
	cd services/api && uv run pytest -m integration

migrate:
	cd services/api && uv run alembic upgrade head

seed-civic:
	cd services/api && uv run python scripts/seed_civic.py

eval-ai:
	cd services/api && uv run python scripts/eval_ai.py

ingest-adm1:
	cd services/api && uv run python scripts/ingest_boundaries.py --download-adm1 --kind state --version-label IND-ADM1-2026.05

load-test:
	k6 run infra/k6/slo-smoke.js

web-dev:
	cd apps/web && npm run dev

web-lint:
	cd apps/web && npm run lint && npx tsc --noEmit

web-build:
	cd apps/web && npm run build

web-e2e:
	cd apps/web && npx playwright test

update-contracts:
	cd services/api && uv run python scripts/update_openapi_snapshot.py

up:
	docker compose up -d --build

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f
