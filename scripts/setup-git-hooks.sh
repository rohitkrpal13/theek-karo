#!/bin/bash
set -euo pipefail

# Theek Karo - Git Hooks Setup Script
# This script installs pre-commit hooks and other quality checks

echo "🔧 Setting up git hooks for Theek Karo..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Not a git repository. Run this from the project root.${NC}"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Python pre-commit
install_precommit() {
    echo "📦 Installing pre-commit..."
    if command_exists uv; then
        uv tool install pre-commit
    elif command_exists pip; then
        pip install pre-commit
    elif command_exists pipx; then
        pipx install pre-commit
    else
        echo -e "${RED}❌ Could not install pre-commit. Please install manually:${NC}"
        echo "   pip install pre-commit"
        echo "   or"
        echo "   brew install pre-commit"
        exit 1
    fi
    echo -e "${GREEN}✅ pre-commit installed${NC}"
}

# Function to install commitizen
install_commitizen() {
    echo "📦 Installing commitizen..."
    if command_exists uv; then
        uv tool install commitizen
    elif command_exists pip; then
        pip install commitizen
    elif command_exists pipx; then
        pipx install commitizen
    else
        echo -e "${YELLOW}⚠️  Could not install commitizen. Commit message validation may not work.${NC}"
        return
    fi
    echo -e "${GREEN}✅ commitizen installed${NC}"
}

# Function to setup pre-commit hooks
setup_precommit() {
    echo "🔗 Setting up pre-commit hooks..."
    pre-commit install
    pre-commit install --hook-type commit-msg
    echo -e "${GREEN}✅ pre-commit hooks installed${NC}"
}

# Function to create custom git hooks
create_custom_hooks() {
    echo "📝 Creating custom git hooks..."

    # Create hooks directory if it doesn't exist
    HOOKS_DIR=".git/hooks"
    mkdir -p "$HOOKS_DIR"

    # Pre-push hook
    cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
set -euo pipefail

# Theek Karo - Pre-push Hook
# Runs quality checks before pushing

echo "🔍 Running pre-push checks..."
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

ERRORS=0

# Check for large files
echo "📦 Checking for large files..."
LARGE_FILES=$(git diff --name-only HEAD @{upstream} 2>/dev/null | head -20)
if [ -n "$LARGE_FILES" ]; then
    for file in $LARGE_FILES; do
        if [ -f "$file" ]; then
            SIZE=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0)
            if [ "$SIZE" -gt 5242880 ]; then  # 5MB
                echo -e "${RED}❌ Large file detected: $file ($(( SIZE / 1024 / 1024 ))MB)${NC}"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
fi

# Check for secrets in staged files
echo "🔐 Checking for secrets..."
if git diff --cached --name-only | xargs grep -l -E '(password|secret|api_key|token|credential)\s*=\s*["\x27][^"\x27]{8,}' 2>/dev/null; then
    echo -e "${RED}❌ Potential secrets detected in staged files${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check for TODO/FIXME in critical files
echo "📋 Checking for TODOs in critical files..."
if git diff --name-only HEAD @{upstream} 2>/dev/null | grep -E '\.(py|ts|tsx)$' | xargs grep -l 'TODO\|FIXME\|HACK\|XXX' 2>/dev/null; then
    echo -e "${YELLOW}⚠️  TODO/FIXME comments found in changed files${NC}"
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Pre-push checks failed. Please fix the issues above.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Pre-push checks passed${NC}"
EOF
    chmod +x "$HOOKS_DIR/pre-push"

    # Post-checkout hook
    cat > "$HOOKS_DIR/post-checkout" << 'EOF'
#!/bin/bash
set -euo pipefail

# Theek Karo - Post-checkout Hook
# Runs after checkout/branch switch

BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")

echo "🔀 Switched to branch: $BRANCH"

# Check if we're on main/master and remind about protection
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    echo "⚠️  You're on the protected branch: $BRANCH"
    echo "   Consider creating a feature branch for your changes."
fi

# Auto-update dependencies if package files changed
if git diff --name-only HEAD@{1} 2>/dev/null | grep -qE '(package\.json|pyproject\.toml|uv\.lock)'; then
    echo "📦 Package files changed. Consider running:"
    echo "   npm install          # for frontend"
    echo "   uv sync              # for backend"
fi
EOF
    chmod +x "$HOOKS_DIR/post-checkout"

    # Post-merge hook
    cat > "$HOOKS_DIR/post-merge" << 'EOF'
#!/bin/bash
set -euo pipefail

# Theek Karo - Post-merge Hook
# Runs after git merge

echo "🔀 Merge completed successfully"

# Check if package files were updated
if git diff-tree -r --name-only HEAD@{1} HEAD 2>/dev/null | grep -qE '(package\.json|pyproject\.toml|uv\.lock)'; then
    echo "📦 Package files were updated during merge."
    echo "   Please run: npm install && cd services/api && uv sync"
fi

# Check if migrations were added
if git diff-tree -r --name-only HEAD@{1} HEAD 2>/dev/null | grep -q 'alembic/versions/'; then
    echo "🗄️  Database migrations were added."
    echo "   Please run: make migrate"
fi
EOF
    chmod +x "$HOOKS_DIR/post-merge"

    # Commit-msg hook for additional validation
    cat > "$HOOKS_DIR/commit-msg" << 'EOF'
#!/bin/bash
set -euo pipefail

# Theek Karo - Commit Message Hook
# Validates commit message format

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

# Conventional Commits pattern
PATTERN="^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\([a-z0-9_-]+\))?: .{1,72}"

if ! echo "$COMMIT_MSG" | head -1 | grep -qE "$PATTERN"; then
    echo "❌ Invalid commit message format!"
    echo ""
    echo "Expected format: <type>(<scope>): <description>"
    echo ""
    echo "Types:"
    echo "  feat:     New feature"
    echo "  fix:      Bug fix"
    echo "  docs:     Documentation"
    echo "  style:    Formatting"
    echo "  refactor: Code restructuring"
    echo "  test:     Adding tests"
    echo "  chore:    Maintenance"
    echo "  perf:     Performance"
    echo "  ci:       CI/CD"
    echo "  build:    Build system"
    echo "  revert:   Revert commit"
    echo ""
    echo "Examples:"
    echo "  feat(reports): add video evidence support"
    echo "  fix(auth): handle expired refresh tokens"
    echo "  docs(api): update authentication examples"
    echo ""
    echo "Your message: $COMMIT_MSG"
    exit 1
fi

# Check description length
DESCRIPTION=$(echo "$COMMIT_MSG" | head -1 | sed -E 's/^[^:]+: //')
if [ ${#DESCRIPTION} -gt 72 ]; then
    echo "⚠️  Description is too long (${#DESCRIPTION} chars, max 72)"
    echo "   Consider shortening: $DESCRIPTION"
fi
EOF
    chmod +x "$HOOKS_DIR/commit-msg"

    echo -e "${GREEN}✅ Custom git hooks installed${NC}"
}

# Function to create gitlint config
create_gitlint_config() {
    echo "📝 Creating gitlint configuration..."

    cat > .gitlint << 'EOF'
[general]
# Allow merge commits
allow-title-warnings=false
allow-body-warnings=false

[title-max-length]
line-length=72

[title-must-not-contain-word]
words=WIP,draft

[body]
# Require body for certain types
regex=^(feat|fix|perf)(\(.+\))?: .+

[contributors]
# Check for Co-authored-by
ignore=bot$

[typed]
# Require type prefixes
types=feat,fix,docs,style,refactor,test,chore,perf,ci,build,revert
EOF

    echo -e "${GREEN}✅ gitlint configuration created${NC}"
}

# Main installation
echo ""
echo "🚀 Starting git hooks setup..."
echo ""

# Check if pre-commit is installed
if ! command_exists pre-commit; then
    install_precommit
else
    echo -e "${GREEN}✅ pre-commit is already installed${NC}"
fi

# Check if commitizen is installed
if ! command_exists cz; then
    install_commitizen
else
    echo -e "${GREEN}✅ commitizen is already installed${NC}"
fi

# Setup pre-commit hooks
setup_precommit

# Create custom git hooks
create_custom_hooks

# Create gitlint config
create_gitlint_config

echo ""
echo "✨ Setup complete!"
echo ""
echo "📋 What was installed:"
echo "   • pre-commit hooks (trailing whitespace, YAML, JSON, etc.)"
echo "   • Ruff linting (Python)"
echo "   • ESLint (TypeScript)"
echo "   • Commit message validation (conventional commits)"
echo "   • Security scanning (Bandit)"
echo "   • Dockerfile linting (Hadolint)"
echo "   • Terraform formatting"
echo "   • Custom git hooks (pre-push, post-checkout, post-merge)"
echo ""
echo "🚀 Quick start:"
echo "   • Make changes to your code"
echo "   • Stage with: git add ."
echo "   • Commit with: git commit -m 'feat(scope): description'"
echo "   • Hooks will run automatically!"
echo ""
echo "💡 To run hooks manually:"
echo "   pre-commit run --all-files"
echo ""
echo "📚 Documentation:"
echo "   • https://pre-commit.com"
echo "   • https://www.conventionalcommits.org/"
