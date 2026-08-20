# GitHub Actions CI/CD Setup — Theek Karo

**Date:** 2026-08-20
**Status:** Ready for configuration

---

## Overview

Theek Karo uses GitHub Actions for CI/CD with three workflows:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push to main, PRs | Lint, test, security scan |
| `deploy.yml` | Push to main, manual | Build, migrate, deploy to AWS |
| `rollback.yml` | Manual | Emergency rollback |

---

## Prerequisites

1. **AWS Account** with programmatic access
2. **GitHub Repository** with Actions enabled
3. **Terraform** deployed infrastructure (see `CLOUD-DEPLOYMENT-GUIDE.md`)

---

## Step 1: Create GitHub Environments

### Create `staging` environment:

1. Go to **Settings → Environments → New environment**
2. Name: `staging`
3. Configure:
   - ✅ Required reviewers: (add yourself)
   - ✅ Wait timer: 0 minutes
   - ✅ Deployment branches: `main` only

### Create `prod` environment:

1. Go to **Settings → Environments → New environment**
2. Name: `prod`
3. Configure:
   - ✅ Required reviewers: (add yourself + team lead)
   - ✅ Wait timer: 5 minutes
   - ✅ Deployment branches: `main` only

---

## Step 2: Configure GitHub Secrets

Go to **Settings → Secrets and variables → Actions → Secrets** and add:

### Required Secrets

| Secret | Description | How to get |
|--------|-------------|------------|
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN for OIDC | `terraform output github_deploy_role_arn` |
| `TARGET_DATABASE_URL` | PostgreSQL connection string | See format below |
| `SMOKE_URL` | Deployed app URL for smoke tests | `https://api.staging.theekkar.in` |

### Database URL Format

```
postgresql+asyncpg://tk_app:<password>@<rds-endpoint>:5432/theek_karo
```

Example:
```
postgresql+asyncpg://tk_app:MyStr0ngP@ss!@tk-staging-pg.xxxx.ap-south-1.rds.amazonaws.com:5432/theek_karo
```

### How to get the values

```bash
# Get AWS Deploy Role ARN
cd infra/terraform
terraform output github_deploy_role_arn

# Get RDS endpoint
terraform output db_endpoint

# Get DB password (from Secrets Manager)
aws secretsmanager get-secret-value --secret-id tk-staging-runtime --query 'SecretString' --output text | jq -r '.db_url'
```

---

## Step 3: Configure GitHub Variables

Go to **Settings → Secrets and variables → Actions → Variables** and add:

| Variable | Value | Description |
|----------|-------|-------------|
| `AWS_REGION` | `ap-south-1` | AWS region |
| `ECR_REGISTRY` | `<account-id>.dkr.ecr.ap-south-1.amazonaws.com` | ECR registry URL |

### How to get ECR Registry

```bash
aws sts get-caller-identity --query Account --output text
# Output: 123456789012

# ECR Registry is:
# 123456789012.dkr.ecr.ap-south-1.amazonaws.com
```

---

## Step 4: Verify Workflows

### Test CI workflow:

```bash
# Create a test branch and push
git checkout -b test/ci-check
git commit --allow-empty -m "test: verify CI workflow"
git push origin test/ci-check

# Create a PR to main
# The CI workflow should run automatically
```

### Test Deploy workflow:

```bash
# Trigger manually via GitHub UI:
# Actions → Deploy → Run workflow → staging
```

---

## Workflow Details

### CI Pipeline (`ci.yml`)

```
┌─────────────┐
│  API Gates  │ ← ruff, mypy, pytest
└──────┬──────┘
       │
┌──────▼──────┐   ┌─────────────┐
│ Integration │   │  Web Gates  │ ← npm audit, lint, tsc, vitest
└──────┬──────┘   └──────┬──────┘
       │                 │
┌──────▼──────┐   ┌──────▼──────┐
│  Fresh DB   │   │  Web E2E   │ ← Playwright
│  Migration  │   └─────────────┘
└─────────────┘
       
┌─────────────┐   ┌─────────────┐
│  Security   │   │  Secrets    │
│   Scan      │   │    Scan     │
└─────────────┘   └─────────────┘
```

### Deploy Pipeline (`deploy.yml`)

```
┌──────────────┐
│ Build & Push │ ← Docker images to ECR
└──────┬───────┘
       │
┌──────▼───────┐
│  Migrations  │ ← Alembic upgrade head
└──────┬───────┘
       │
┌──────▼───────┐
│    Deploy    │ ← Update ECS services
└──────┬───────┘
       │
┌──────▼───────┐
│    Smoke     │ ← Verify deployment
└──────────────┘
```

### Rollback Pipeline (`rollback.yml`)

```
┌──────────────┐
│   Rollback   │ ← Restore previous task-def
└──────┬───────┘
       │
┌──────▼───────┐
│    Smoke     │ ← Verify rollback
└──────────────┘
```

---

## Monitoring Deployments

### View workflow runs:

```bash
# Via GitHub CLI
gh run list --workflow=ci.yml
gh run list --workflow=deploy.yml

# View specific run
gh run view <run-id>
```

### View deployment status:

```bash
# Check ECS service status
aws ecs describe-services --cluster tk-staging --services tk-api tk-web tk-worker

# View recent deployments
aws ecs describe-services --cluster tk-staging --services tk-api --query 'services[0].deployments'
```

---

## Troubleshooting

### CI fails with "uv: command not found"

The `astral-sh/setup-uv@v5` action should install uv. If it fails:

```yaml
# Add to ci.yml steps:
- name: Install uv
  run: pip install uv
```

### Deploy fails with "OIDC token invalid"

1. Verify the OIDC provider exists in AWS
2. Check the trust policy on the deploy role
3. Ensure the GitHub repo name matches the trust policy

### Deploy fails with "ECR login failed"

1. Verify `ECR_REGISTRY` variable is set correctly
2. Check the deploy role has ECR permissions
3. Ensure ECR repositories exist

### Smoke tests fail

1. Check ECS service is stable: `aws ecs describe-services`
2. Check task logs: `aws logs tail /ecs/tk-staging --follow`
3. Verify ALB target groups are healthy

---

## Security Best Practices

1. ✅ **OIDC** — No long-lived AWS credentials in GitHub
2. ✅ **Environment protection** — Required reviewers for prod
3. ✅ **Secret scanning** — CI checks for hardcoded secrets
4. ✅ **Dependency scanning** — npm audit + pip-audit
5. ✅ **SAST** — Bandit + Semgrep for Python
6. ✅ **Container scanning** — Trivy for Docker images
7. ✅ **Branch protection** — Require PR reviews for main

---

## Next Steps

1. ✅ Configure GitHub secrets (Step 2)
2. ✅ Configure GitHub variables (Step 3)
3. ✅ Test CI workflow (Step 4)
4. ✅ Test deploy workflow (Step 4)
5. ✅ Set up branch protection rules
6. ✅ Configure Slack notifications (optional)
