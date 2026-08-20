#!/bin/bash
set -euo pipefail

# Theek Karo - Post-Checkout Hook
# This script runs after git checkout or branch switch

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}🔀 Branch switched${NC}"
echo ""

# Get current branch
BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")

# Get previous branch
PREV_BRANCH=$(git rev-parse --abbrev-ref HEAD@{1} 2>/dev/null || echo "unknown")

echo -e "📍 Current branch: ${GREEN}$BRANCH${NC}"
if [ "$PREV_BRANCH" != "unknown" ]; then
    echo -e "📍 Previous branch: ${YELLOW}$PREV_BRANCH${NC}"
fi
echo ""

# Check if we're on a protected branch
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" || "$BRANCH" == "develop" ]]; then
    echo -e "${YELLOW}⚠️  You're on a protected branch: $BRANCH${NC}"
    echo "   Consider creating a feature branch for your changes:"
    echo "   git checkout -b feature/your-feature-name"
    echo ""
fi

# Check if package files changed
if git diff --name-only HEAD@{1} 2>/dev/null | grep -qE '(package\.json|pyproject\.toml|uv\.lock)'; then
    echo -e "${YELLOW}📦 Package files changed since last branch${NC}"
    echo "   Consider updating dependencies:"
    echo "   • Frontend: npm install"
    echo "   • Backend: cd services/api && uv sync"
    echo ""
fi

# Check if migration files were added
if git diff-tree -r --name-only HEAD@{1} HEAD 2>/dev/null | grep -q 'alembic/versions/'; then
    echo -e "${YELLOW}🗄️  Database migrations detected${NC}"
    echo "   Consider running migrations:"
    echo "   make migrate"
    echo ""
fi

# Check if Docker files changed
if git diff-tree -r --name-only HEAD@{1} HEAD 2>/dev/null | grep -qE '(Dockerfile|docker-compose)'; then
    echo -e "${YELLOW}🐳 Docker configuration changed${NC}"
    echo "   Consider rebuilding containers:"
    echo "   make up --build"
    echo ""
fi

# Check if CI files changed
if git diff-tree -r --name-only HEAD@{1} HEAD 2>/dev/null | grep -q '.github/workflows/'; then
    echo -e "${YELLOW}⚙️  CI/CD configuration changed${NC}"
    echo "   Consider checking GitHub Actions:"
    echo "   https://github.com/rohitkrpal13/theek-karo/actions"
    echo ""
fi

# Show helpful commands
echo -e "${BLUE}💡 Quick commands:${NC}"
echo "   make test          # Run tests"
echo "   make lint          # Lint code"
echo "   make typecheck     # Type check"
echo "   make up            # Start services"
echo "   make down          # Stop services"
echo ""
