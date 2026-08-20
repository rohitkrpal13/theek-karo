# RELEASE PROCESS — Theek Karo

**Version:** 1.0  
**Date:** 2026-08-19

---

## Versioning

### Semantic Versioning
```
MAJOR.MINOR.PATCH

MAJOR: Breaking changes, major features
MINOR: New features, backwards compatible
PATCH: Bug fixes, security patches
```

### Examples
- `1.0.0` — Initial production release
- `1.1.0` — New feature (e.g., government workflow)
- `1.1.1` — Bug fix
- `1.2.0` — New feature (e.g., AI assistant)
- `2.0.0` — Breaking API change

---

## Release Types

### Hotfix (Emergency)
**Trigger:** Critical bug, security vulnerability, outage  
**Process:**
1. Create branch `hotfix/fix-description`
2. Fix the issue
3. Add tests
4. PR with expedited review
5. Merge to main
6. Auto-deploy to staging
7. Smoke test
8. Manual approval for production
9. Verify in production

**Timeline:** Same day

### Patch
**Trigger:** Bug fix, minor improvement  
**Process:**
1. Create branch `fix/fix-description`
2. Fix the issue
3. Add tests
4. PR with review
5. Merge to main
6. Auto-deploy to staging
7. Verify in staging
8. Schedule production deploy

**Timeline:** Next release cycle

### Minor
**Trigger:** New feature, enhancement  
**Process:**
1. Create branch `feat/feature-name`
2. Implement feature
3. Add tests
4. Update documentation
5. PR with review
6. Merge to main
7. Auto-deploy to staging
8. Verify in staging
9. Schedule production deploy

**Timeline:** Next release cycle

### Major
**Trigger:** Breaking change, major refactor  
**Process:**
1. Create branch `feat/major-feature`
2. Implement changes
3. Migration plan
4. Backwards compatibility layer (if possible)
5. PR with thorough review
6. Merge to main
7. Auto-deploy to staging
8. Extended testing in staging
9. Plan production deploy with rollback

**Timeline:** Planned release

---

## Release Checklist

### Pre-Release
- [ ] All CI checks passing
- [ ] Security scans passing
- [ ] Staging tests passing
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Migration tested (upgrade + downgrade)

### Release
- [ ] Create release branch (if needed)
- [ ] Tag release (`v1.0.0`)
- [ ] Build Docker images
- [ ] Push to ECR
- [ ] Run migrations
- [ ] Deploy to production
- [ ] Verify health checks
- [ ] Run smoke tests
- [ ] Monitor for 1 hour

### Post-Release
- [ ] Update CHANGELOG.md
- [ ] Create GitHub release
- [ ] Notify team
- [ ] Monitor metrics
- [ ] Review error rates

---

## Changelog Format

```markdown
# Changelog

## [1.0.0] - 2026-08-19

### Added
- Initial production release
- Citizen report submission
- Case management workflow
- AI-powered analysis
- Government workflow integration
- Public transparency dashboard

### Security
- MFA enforced for privileged roles
- Rate limiting active
- Input validation active

### Known Limitations
- AI features use stub provider (production requires API key)
- Government integrations are abstract (no live connections)
```

---

## Feature Flags

### Launch Flags
```python
# Feature flags for controlled rollout
FEATURE_FLAGS = {
    "ai_assistant": True,      # AI chat functionality
    "government_workflow": True, # Government case routing
    "advanced_analytics": True,  # Advanced analytics
    "campaigns": True,          # Campaign communication
    "voice_reports": False,     # Voice report submission
}
```

### Rollback Flags
```python
# Emergency disable flags
EMERGENCY_FLAGS = {
    "disable_ai_writes": False,  # Disable AI write operations
    "disable_bulk_send": False,  # Disable bulk communication
    "disable_external_sync": False,  # Disable external integrations
}
```

---

## Hotfix Process

### 1. Identify Issue
```bash
# Check production logs
aws logs tail /ecs/tk-prod --since 1h --filter-pattern "ERROR"

# Check metrics
# Grafana → API → Error Rate
```

### 2. Create Hotfix Branch
```bash
git checkout main
git pull
git checkout -b hotfix/fix-description
```

### 3. Fix and Test
```bash
# Make fix
# Add regression test
make test
make lint
make typecheck
```

### 4. Deploy
```bash
# Create PR (expedited review)
# Merge to main
# Auto-deploy to staging
# Verify
# Manual approve production
```

### 5. Verify
```bash
# Check production
curl -sf https://api.theekkar.in/healthz

# Monitor for 30 minutes
# Check error rates
# Check user reports
```

---

## Communication

### Release Notes (Internal)
```
Release v1.1.0 deployed to production.

Changes:
- Added government workflow routing
- Improved search performance
- Fixed case status display bug

Rollback: Available via GitHub Actions
```

### Release Notes (External)
```
Theek Karo v1.1.0

New Features:
- Government departments can now respond to cases directly
- Search is faster for large result sets

Improvements:
- Better mobile experience
- Improved accessibility

Bug Fixes:
- Fixed case status not updating
- Fixed notification delays
```
