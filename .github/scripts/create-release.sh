#!/bin/bash
set -euo pipefail

# Theek Karo Release Helper
# Usage: ./create-release.sh <version> [--deploy staging|prod]

VERSION=""
DEPLOY_ENV=""
SKIP_DEPLOY=false

usage() {
    echo "Usage: $0 <version> [options]"
    echo ""
    echo "Options:"
    echo "  --deploy <env>    Deploy after release (staging or prod)"
    echo "  --skip-deploy     Skip deployment"
    echo "  --prerelease      Mark as pre-release"
    echo "  --dry-run         Show what would happen without executing"
    echo "  -h, --help        Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 1.0.0                          # Create release v1.0.0"
    echo "  $0 1.0.0 --deploy staging         # Create and deploy to staging"
    echo "  $0 1.1.0-beta.1 --prerelease      # Create pre-release"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --deploy)
                DEPLOY_ENV="$2"
                shift 2
                ;;
            --skip-deploy)
                SKIP_DEPLOY=true
                shift
                ;;
            --prerelease)
                IS_PRERELEASE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                if [[ -z "$VERSION" ]]; then
                    VERSION="$1"
                else
                    echo "❌ Unknown option: $1"
                    usage
                    exit 1
                fi
                shift
                ;;
        esac
    done
}

validate_version() {
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "❌ Invalid version format: $VERSION"
        echo "Expected format: X.Y.Z or X.Y.Z-prerelease"
        exit 1
    fi

    # Check if tag already exists
    if git rev-parse "v$VERSION" >/dev/null 2>&1; then
        echo "❌ Tag v$VERSION already exists"
        exit 1
    fi
}

validate_changelog() {
    if ! grep -q "## \[${VERSION}\]" CHANGELOG.md; then
        echo "⚠️  Warning: No changelog entry found for v${VERSION}"
        echo "   Please add a changelog entry before releasing."
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

check_uncommitted() {
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "❌ Uncommitted changes found. Please commit or stash them first."
        exit 1
    fi
}

create_release() {
    echo "🚀 Creating release v${VERSION}..."
    echo ""

    # Create annotated tag
    echo "📌 Creating tag v${VERSION}..."
    if [[ "${DRY_RUN:-false}" != "true" ]]; then
        git tag -a "v${VERSION}" -m "Release v${VERSION}"
    fi
    echo "   ✅ Tag created"

    # Push tag
    echo "📤 Pushing tag..."
    if [[ "${DRY_RUN:-false}" != "true" ]]; then
        git push origin "v${VERSION}"
    fi
    echo "   ✅ Tag pushed"

    echo ""
    echo "✅ Release v${VERSION} initiated!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. GitHub Actions will create the release"
    echo "   2. Docker images will be built and pushed"
    if [[ "$SKIP_DEPLOY" == "false" && -n "$DEPLOY_ENV" ]]; then
        echo "   3. Deployment to ${DEPLOY_ENV} will begin"
    else
        echo "   3. Deploy manually if needed"
    fi
    echo ""
    echo "🔗 Release URL: https://github.com/rohitkrpal13/theek-karo/releases/tag/v${VERSION}"
}

main() {
    parse_args "$@"

    if [[ -z "$VERSION" ]]; then
        echo "❌ Version is required"
        usage
        exit 1
    fi

    echo "🎯 Release v${VERSION}"
    echo ""

    check_uncommitted
    validate_version
    validate_changelog

    echo ""
    echo "📋 Release Summary:"
    echo "   Version: ${VERSION}"
    echo "   Deploy: ${DEPLOY_ENV:-none}"
    echo "   Skip Deploy: ${SKIP_DEPLOY}"
    echo "   Pre-release: ${IS_PRERELEASE:-false}"
    echo ""

    read -p "Continue with release? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Release cancelled"
        exit 1
    fi

    create_release
}

main "$@"
