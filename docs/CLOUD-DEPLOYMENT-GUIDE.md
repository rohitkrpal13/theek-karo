# Cloud Deployment Guide — Theek Karo

**Date:** 2026-08-20
**Status:** Ready for deployment

---

## Overview

This guide walks through deploying Theek Karo to AWS using the existing
Terraform infrastructure. The deployment creates:

- **ECS Fargate** cluster (api, worker, web services)
- **RDS Postgres 16** with PostGIS
- **ElastiCache Redis** for caching and job queues
- **S3 + CloudFront** for media storage and CDN
- **ALB** with HTTPS (ACM certificates)
- **GitHub Actions** CI/CD with OIDC

---

## Prerequisites

| Requirement | Install/Setup |
|-------------|---------------|
| AWS Account | [Sign up](https://aws.amazon.com) |
| AWS CLI | `brew install awscli` or `pip install awscli` |
| Docker | [Install Docker Desktop](https://docker.com) |
| Terraform | `brew install terraform` |
| Python 3.11+ | For running migrations |
| Git | Already installed |

---

## Step 1: Configure AWS Credentials

```bash
# Configure AWS CLI with your credentials
aws configure

# You'll be prompted for:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (ap-south-1)
# - Default output format (json)

# Verify configuration
aws sts get-caller-identity
```

---

## Step 2: Set Environment Variables

```bash
# Generate strong passwords
export DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c 24)
export JWT_SECRET=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)

# Save these values - you'll need them later
echo "DB_PASSWORD=$DB_PASSWORD"
echo "JWT_SECRET=$JWT_SECRET"
```

---

## Step 3: Run Deployment

### Option A: Automated Script (Recommended)

```bash
# Deploy to staging
./infra/terraform/deploy.sh staging

# Deploy to production (after testing staging)
./infra/terraform/deploy.sh prod
```

### Option B: Manual Terraform

```bash
cd infra/terraform

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan -var-file="staging.tfvars" -out=tfplan

# Review the plan and apply
terraform apply tfplan

# Get outputs
terraform output
```

---

## Step 4: Configure DNS

### If using Route53:

```bash
# Get the nameservers from ACM certificate validation
aws acm describe-certificate --certificate-arn <ARN> --query 'Certificate.DomainValidationOptions'

# Create hosted zone (if not exists)
aws route53 create-hosted-zone --name theekkar.in --caller-reference $(date +%s)

# Update nameservers at your registrar to point to Route53
```

### If using external DNS:

Create CNAME records pointing to the ALB DNS name:

```
api.staging.theekkar.in  →  <ALB-DNS>
staging.theekkar.in      →  <ALB-DNS>
api.theekkar.in          →  <ALB-DNS>
theekkar.in              →  <ALB-DNS>
```

---

## Step 5: Verify Deployment

```bash
# Check API health
curl https://api.staging.theekkar.in/healthz

# Check web app
curl -I https://staging.theekkar.in

# View logs
aws logs tail /ecs/tk-staging --follow

# Check ECS services
aws ecs describe-services --cluster tk-staging --services tk-api tk-web tk-worker
```

---

## Step 6: Set Up GitHub Actions (Optional)

### Create GitHub Secrets:

1. Go to your GitHub repo → Settings → Secrets and variables → Actions
2. Add these secrets:
   - `AWS_DEPLOY_ROLE_ARN` — from Terraform output `github_deploy_role_arn`
   - `TARGET_DATABASE_URL` — full PostgreSQL connection string

### Create GitHub Variables:

1. Go to Settings → Secrets and variables → Actions → Variables
2. Add:
   - `AWS_REGION` — `ap-south-1`
   - `ECR_REGISTRY` — `<account-id>.dkr.ecr.ap-south-1.amazonaws.com`

### Trigger Deployment:

Push to `main` branch or manually trigger the Deploy workflow.

---

## Architecture Diagram

```
Internet
    │
    ▼
┌─────────┐
│   ALB   │ ← HTTPS (ACM)
└────┬────┘
     │
     ├── /api/* → ┌─────────┐
     │            │ tk-api  │ ← ECS Fargate
     │            └────┬────┘
     │                 │
     │            ┌────▼────┐     ┌─────────┐
     │            │Postgres │     │  Redis   │
     │            │(RDS)    │     │(ElastiC) │
     │            └─────────┘     └─────────┘
     │
     └── /*    → ┌─────────┐
                 │ tk-web  │ ← ECS Fargate
                 └─────────┘

┌─────────┐
│   S3    │ ← Media storage
└────┬────┘
     │
┌────▼────┐
│CloudFront│ ← CDN
└─────────┘
```

---

## Cost Estimates (Staging)

| Service | Monthly Cost (approx) |
|---------|----------------------|
| ECS Fargate (3 tasks) | $50-75 |
| RDS Postgres (db.t4g.micro) | $15-20 |
| ElastiCache Redis (cache.t4g.micro) | $15-20 |
| S3 + CloudFront | $5-10 |
| ALB | $15-20 |
| Secrets Manager | $1 |
| CloudWatch Logs | $5-10 |
| **Total** | **$100-150/month** |

## Cost Estimates (Production)

| Service | Monthly Cost (approx) |
|---------|----------------------|
| ECS Fargate (6 tasks, multi-AZ) | $150-200 |
| RDS Postgres (db.t4g.small, Multi-AZ) | $50-70 |
| ElastiCache Redis (cache.t4g.small) | $30-40 |
| S3 + CloudFront | $20-50 |
| ALB | $20-30 |
| Secrets Manager | $1 |
| CloudWatch Logs | $20-30 |
| **Total** | **$300-450/month** |

---

## Rollback Procedure

If something goes wrong:

```bash
# Option 1: Rollback ECS to previous task definition
aws ecs update-service \
  --cluster tk-staging \
  --service tk-api \
  --task-definition tk-api-task:<previous-revision>

# Option 2: Rollback Terraform
cd infra/terraform
terraform plan -var-file="staging.tfvars"
terraform apply -var-file="staging.tfvars"

# Option 3: Emergency rollback via GitHub Actions
# Go to Actions → Rollback → Run workflow
```

---

## Monitoring

### Check Service Health:

```bash
# ECS service status
aws ecs describe-services --cluster tk-staging --services tk-api

# Recent logs
aws logs tail /ecs/tk-staging --since 1h --follow

# Database connections
aws rds describe-db-instances --db-instance-identifier tk-staging-pg
```

### Grafana Dashboard:

```bash
# Port-forward to Grafana
kubectl port-forward svc/grafana 3001:3000

# Open: http://localhost:3001
# Default credentials: admin/admin
```

---

## Troubleshooting

### API returns 502 Bad Gateway

```bash
# Check ECS service events
aws ecs describe-services --cluster tk-staging --services tk-api --query 'services[0].events'

# Check task health
aws ecs list-tasks --cluster tk-staging --service-name tk-api
aws ecs describe-tasks --cluster tk-staging --tasks <task-arn>
```

### Database connection refused

```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier tk-staging-pg

# Check security groups
aws ec2 describe-security-groups --group-ids <sg-id>
```

### SSL certificate not issued

```bash
# Check ACM certificate status
aws acm list-certificates --query 'CertificateSummaryList[*].[CertificateArn,DomainName,Status]'

# Request validation
aws acm request-certificate-certificate-validation \
  --certificate-arn <arn> \
  --domain-validation-options <options>
```

---

## Next Steps

1. ✅ Run `./infra/terraform/deploy.sh staging`
2. ✅ Configure DNS for staging.theekkar.in
3. ✅ Verify API and web app are working
4. ✅ Set up GitHub Actions for CI/CD
5. ✅ Run load tests against staging
6. ✅ Deploy to production after validation
7. ✅ Configure monitoring and alerting
8. ✅ Set up on-call rotation
