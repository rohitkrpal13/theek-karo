# Third-Party Licenses

This document lists the licenses of third-party components used in Theek Karo.

## Python Dependencies (Backend)

| Package | License | Link |
|---------|---------|------|
| FastAPI | MIT | https://github.com/tiangolo/fastapi |
| SQLAlchemy | MIT | https://github.com/sqlalchemy/sqlalchemy |
| Pydantic | MIT | https://github.com/pydantic/pydantic |
| Alembic | MIT | https://github.com/sqlalchemy/alembic |
| Celery | BSD-3-Clause | https://github.com/celery/celery |
| Redis (Python) | MIT | https://github.com/redis/redis-py |
| httpx | BSD-3-Clause | https://github.com/encode/httpx |
| Pillow | MIT-CMU | https://github.com/python-pillow/Pillow |
| Python-JOSE | MIT | https://github.com/mpdavis/python-jose |
| Argon2-CFFI | MIT/Apache-2.0 | https://github.com/hynek/argon2-cffi |
| GeoAlchemy2 | MIT | https://github.com/geoalchemy/geoalchemy2 |
| MinIO | Apache-2.0 | https://github.com/minio/minio-py |
| OpenTelemetry | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python |
| Uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn |
| PyJWT | MIT | https://github.com/jpadilla/pyjwt |
| JSONSchema | MIT | https://github.com/python-jsonschema/jsonschema |

## JavaScript Dependencies (Frontend)

| Package | License | Link |
|---------|---------|------|
| Next.js | MIT | https://github.com/vercel/next.js |
| React | MIT | https://github.com/facebook/react |
| TypeScript | Apache-2.0 | https://github.com/microsoft/TypeScript |
| Tailwind CSS | MIT | https://github.com/tailwindlabs/tailwindcss |
| Vitest | MIT | https://github.com/vitest-dev/vitest |
| Playwright | Apache-2.0 | https://github.com/microsoft/playwright |

## Infrastructure

| Component | License | Link |
|-----------|---------|------|
| PostgreSQL | PostgreSQL License | https://www.postgresql.org/about/licence/ |
| PostGIS | GPL-2.0 | https://postgis.net/license/ |
| Redis | BSD-3-Clause | https://redis.io/license |
| MinIO | AGPL-3.0 | https://min.io/license |
| Docker | Apache-2.0 | https://www.docker.com/legal/ |
| Terraform | MPL-2.0 | https://github.com/hashicorp/terraform |
| Grafana | AGPL-3.0 | https://github.com/grafana/grafana |
| Prometheus | Apache-2.0 | https://github.com/prometheus/prometheus |

## Fonts and Icons

| Component | License | Link |
|-----------|---------|------|
| Inter Font | SIL Open Font License | https://github.com/rsms/inter |
| Material Icons | Apache-2.0 | https://github.com/google/material-design-icons |

## Development Tools

| Tool | License | Link |
|------|---------|------|
| Ruff | MIT | https://github.com/astral-sh/ruff |
| Mypy | MIT | https://github.com/python/mypy |
| ESLint | MIT | https://github.com/eslint/eslint |
| Prettier | MIT | https://github.com/prettier/prettier |

## AI and Machine Learning

| Component | License | Notes |
|-----------|---------|-------|
| OpenTelemetry | Apache-2.0 | Used for AI observability |
| pgvector | PostgreSQL License | Vector embeddings storage |

## License Compatibility

All dependencies are compatible with the MIT License used by Theek Karo.

### Notes

- **PostGIS** uses GPL-2.0, but since it's a database extension (not linked into our application code), it doesn't affect our MIT license.
- **MinIO** uses AGPL-3.0 for the server, but the Python client library uses Apache-2.0, which is compatible.
- **Grafana** uses AGPL-3.0, but we only use it for monitoring (not modified or distributed).
- **Redis** uses BSD-3-Clause, which is permissive and compatible.

## Adding New Dependencies

Before adding a new dependency:

1. Check the license is compatible with MIT
2. Add it to this file
3. Run `make lint` to verify no license issues
4. Ensure no AGPL/GPL dependencies are linked into our application code

## Resources

- [Choose a License](https://choosealicense.com/)
- [SPDX License List](https://spdx.org/licenses/)
- [FOSSA](https://fossa.com/) (license scanning)

---

*Last updated: August 2026*
