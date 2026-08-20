# Contributing to Theek Karo

Thank you for your interest in contributing to Theek Karo! This document provides guidelines and instructions for contributing to this project.

## 🌟 Welcome

Theek Karo (ठीक करो — Make It Right) is India-first, AI-native civic intelligence platform. We welcome contributions from developers, designers, translators, and civic tech enthusiasts.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style & Conventions](#code-style--conventions)
- [Testing Requirements](#testing-requirements)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)
- [Common Tasks](#common-tasks)
- [Getting Help](#getting-help)

## Code of Conduct

We are committed to providing a welcoming and inclusive experience for everyone. Please:

- Be respectful and constructive in all interactions
- Focus on what is best for the community and the civic mission
- Show empathy towards other contributors
- Use welcoming and inclusive language

## Getting Started

### Prerequisites

- **Docker** & Docker Compose (for local services)
- **Python 3.13+** with [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 20+** with npm (for frontend)
- **Git** for version control

### Setting Up Your Development Environment

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/theek-karo.git
   cd theek-karo
   git remote add upstream https://github.com/rohitkrpal13/theek-karo.git
   ```

2. **Start the development environment:**
   ```bash
   make up
   ```

3. **Verify everything is running:**
   ```bash
   curl http://localhost:8001/healthz   # → {"status":"ok"}
   curl http://localhost:8001/readyz    # → {"status":"ok","checks":{"database":"ok"}}
   ```

4. **Run database migrations:**
   ```bash
   make migrate
   ```

5. **Seed civic data (optional):**
   ```bash
   make seed-civic
   ```

### Frontend Setup (Optional)

If you're working on the frontend:

```bash
cd apps/web
npm install
npm run dev
```

The frontend runs on `http://localhost:3000`.

## Development Workflow

### 1. Sync with Upstream

Before starting any work, ensure your fork is up to date:

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

### 2. Create a Feature Branch

Always work on a feature branch, never directly on `main`:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

**Branch naming conventions:**
- `feature/` - New features (e.g., `feature/add-video-evidence`)
- `fix/` - Bug fixes (e.g., `fix/42-handle-null-location`)
- `docs/` - Documentation changes (e.g., `docs/update-api-examples`)
- `refactor/` - Code refactoring (e.g., `refactor/extract-auth-module`)
- `test/` - Adding or updating tests (e.g., `test/add-case-lifecycle-tests`)
- `chore/` - Maintenance tasks (e.g., `chore/update-dependencies`)

### 3. Make Your Changes

- Follow the [code style conventions](#code-style--conventions) below
- Write tests for new functionality
- Update documentation if needed

### 4. Run Quality Checks

Before committing, ensure all checks pass:

```bash
# Backend
make lint            # Ruff linting
make typecheck       # Mypy type checking
make test            # Unit tests

# Frontend (if applicable)
make web-lint        # ESLint + TypeScript checking
make web-build       # Build verification
```

### 5. Commit Your Changes

Follow our [commit message conventions](#commit-messages).

### 6. Push and Create a Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub against the `main` branch.

## Code Style & Conventions

### Python (Backend)

We use **strict** code quality tools:

- **Formatter:** [Ruff](https://docs.astral.sh/ruff/) (line length: 100)
- **Linter:** Ruff with rules: E, F, W, I, UP, B, SIM, RUF
- **Type Checker:** [mypy](https://mypy-lang.org/) in strict mode (Python 3.13)
- **Testing:** [pytest](https://docs.pytest.org/) with async support

**Key conventions:**

```python
# ✅ Good
from tk_api.users.service import UserService

async def get_user(user_id: int) -> User:
    """Get user by ID."""
    service = UserService(db)
    return await service.get_by_id(user_id)

# ❌ Bad - missing type hints
async def get_user(user_id):
    service = UserService(db)
    return await service.get_by_id(user_id)
```

- All functions must have type hints
- All public functions must have docstrings
- Use async/await for database operations
- Follow the existing module structure

### TypeScript (Frontend)

- **Formatter:** Prettier
- **Linter:** ESLint
- **Type Checker:** TypeScript (strict mode)
- **Framework:** Next.js 16 App Router + React 19

**Key conventions:**

```typescript
// ✅ Good
export async function ReportCard({ reportId }: { reportId: string }) {
  const report = await getReport(reportId);
  
  return (
    <div className="p-4 border rounded-lg">
      <h2>{report.title}</h2>
      <p>{report.description}</p>
    </div>
  );
}

// ❌ Bad - missing types
export async function ReportCard({ reportId }) {
  const report = await getReport(reportId);
  return <div>{report.title}</div>;
}
```

### General Principles

1. **Configuration over Code:** Don't hardcode values that should be configurable
2. **Provenance is Sacred:** Every data point must have a declared trust tier
3. **Append-Only History:** Never mutate history; append new records
4. **Fail Gracefully:** Handle errors with proper user feedback
5. **Security First:** Never trust user input; validate everything

## Testing Requirements

### Writing Tests

- **Location:** Tests go in `services/api/tests/`
- **Naming:** `test_<module>_<function>.py` or `test_phase<N>_<feature>.py`
- **Markers:** Use `@pytest.mark.integration` for tests requiring live database

**Example test:**

```python
import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_create_report(client: AsyncClient, auth_headers: dict):
    """Test creating a new civic report."""
    response = await client.post(
        "/api/v1/reports",
        json={
            "title": "Pothole on Main Street",
            "category_slug": "roads",
            "location": {"lat": 28.6139, "lng": 77.2090},
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Pothole on Main Street"
    assert data["status"] == "reported"
```

### Running Tests

```bash
# Unit tests (uses SQLite, fast)
make test

# Integration tests (requires running Docker services)
make test-integration

# Specific test file
cd services/api && uv run pytest tests/test_reports.py -v

# With coverage
cd services/api && uv run pytest --cov=tk_api --cov-report=html
```

### Test Coverage

We aim for high test coverage on critical paths:

- **API endpoints:** Must have integration tests
- **Business logic:** Must have unit tests
- **State machines:** Must test all valid transitions
- **Error handling:** Must test error cases

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(reports): add video evidence support` |
| `fix` | Bug fix | `fix(auth): handle expired refresh tokens` |
| `docs` | Documentation | `docs(api): update authentication examples` |
| `style` | Formatting (no code change) | `style: fix linting warnings` |
| `refactor` | Code restructuring | `refactor(cases): extract SLA evaluation` |
| `test` | Adding tests | `test(verification): add policy engine tests` |
| `chore` | Maintenance | `chore: update dependencies` |
| `perf` | Performance improvement | `perf(search): add database index` |

### Examples

```bash
# Simple feature
git commit -m "feat(media): add video upload support"

# With scope and body
git commit -m "feat(cases): implement SLA escalation

- Add EscalationRule model with weighted matching
- Implement manual and automatic escalation
- Add worker sweep for SLA evaluation

Closes #123"

# Breaking change
git commit -m "feat(api)!: change report status enum values

BREAKING CHANGE: Report status values now use snake_case
instead of camelCase. Migration script included."
```

### Tips

- Use imperative mood ("add feature" not "added feature")
- Keep first line under 72 characters
- Reference issues with `Closes #123` or `Fixes #123`
- Add `!` after type for breaking changes

## Pull Request Process

### Before Submitting

- [ ] Code compiles and runs without errors
- [ ] All existing tests pass (`make test`)
- [ ] New tests added for new functionality
- [ ] Linting passes (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow conventions

### PR Template

When creating a PR, include:

```markdown
## Description

Brief description of the changes.

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally

## Related Issues

Closes #123
```

### Review Process

1. **Automated Checks:** CI must pass (lint, typecheck, tests)
2. **Code Review:** At least one maintainer approval required
3. **Testing:** Reviewer may test locally for significant changes
4. **Merge:** Squash and merge for clean history

### After Merge

- Delete your feature branch
- Sync with upstream:
  ```bash
  git checkout main
  git pull upstream main
  git push origin main
  ```

## Project Structure

```
theek-karo/
├── apps/
│   └── web/                    # Next.js 16 frontend
│       ├── src/
│       │   ├── app/           # App Router pages
│       │   ├── components/    # React components
│       │   └── lib/           # Utilities and API client
│       └── public/            # Static assets
│
├── services/
│   └── api/                   # FastAPI backend
│       ├── src/tk_api/        # Application code
│       │   ├── identity/      # Authentication & authorization
│       │   ├── users/         # User profiles & reputation
│       │   ├── geography/     # Hierarchy registry
│       │   ├── institutions/  # Digital twins
│       │   ├── reports/       # Report lifecycle
│       │   ├── cases/         # Civic cases & SLA
│       │   ├── media/         # File uploads & evidence
│       │   ├── verification/  # Trust & verification
│       │   ├── resolution/    # Resolution workflow
│       │   ├── departments/   # Department registry
│       │   ├── analytics/     # Metrics & dashboards
│       │   ├── search/        # Search functionality
│       │   ├── ai/            # AI gateway & capabilities
│       │   ├── moderation/    # Content moderation
│       │   ├── notifications/ # Notification system
│       │   └── audit/         # Audit logging
│       ├── alembic/           # Database migrations
│       ├── tests/             # Test suite
│       └── scripts/           # Utility scripts
│
├── infra/                     # Infrastructure
│   ├── terraform/             # AWS infrastructure
│   ├── prometheus/            # Monitoring config
│   └── grafana/               # Dashboards
│
└── docs/                      # Documentation
    ├── PRD.md                 # Product Requirements
    ├── ARCHITECTURE.md        # System Architecture
    ├── SECURITY.md            # Security Model
    └── ...                    # 45+ documentation files
```

## Common Tasks

### Adding a New API Endpoint

1. Define the route in the appropriate module's `router.py`
2. Create Pydantic schemas in `schemas.py`
3. Implement business logic in `service.py`
4. Add database models if needed in `models.py`
5. Write tests in `tests/`
6. Update API documentation in `docs/API.md`

### Adding a Database Migration

1. Create a new migration file:
   ```bash
   cd services/api
   uv run alembic revision --autogenerate -m "description of change"
   ```

2. Review the generated migration in `alembic/versions/`

3. Test the migration:
   ```bash
   make migrate  # Apply
   make test     # Verify
   ```

### Adding a New Trust Tier Label

1. Update the `ProvenanceTier` enum in the schema
2. Add CHECK constraint in the migration
3. Update UI components to render the new tier
4. Add tests for the new tier
5. Document in `docs/SECURITY.md`

### Adding i18n Support

1. Add the language to the language registry
2. Create translation files in `src/tk_api/i18n/locales/`
3. Update notification templates
4. Test with the new locale
5. Document in `docs/I18N.md`

## Getting Help

### Resources

- **Documentation:** Check `docs/` directory for detailed guides
- **Architecture:** Read `docs/ARCHITECTURE.md` for system design
- **API Reference:** See `docs/API.md` for endpoint details
- **Security Model:** Review `docs/SECURITY.md` for trust boundaries

### Asking Questions

- **GitHub Issues:** Use for bugs, feature requests, and discussions
- **GitHub Discussions:** Use for questions and general discussion

### Reporting Bugs

When reporting bugs, please include:

1. **Environment:** OS, Python version, Node version
2. **Steps to reproduce:** Clear steps to reproduce the issue
3. **Expected behavior:** What you expected to happen
4. **Actual behavior:** What actually happened
5. **Screenshots:** If applicable
6. **Logs:** Relevant error messages

### Suggesting Features

When suggesting features:

1. **Problem statement:** What problem does this solve?
2. **Proposed solution:** How should it work?
3. **Alternatives considered:** Other approaches you've thought about
4. **Additional context:** Mockups, examples, related issues

## License

By contributing to Theek Karo, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Thank you for contributing to Theek Karo. Your efforts help make civic governance more transparent and accountable for all Indians. 🇮🇳

---

<p align="center">
  <a href="docs/PRD.md">PRD</a> ·
  <a href="docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="docs/API.md">API</a> ·
  <a href="docs/SECURITY.md">Security</a>
</p>
