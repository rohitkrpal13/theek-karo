# PRODUCTION DEPLOYMENT — Theek Karo

**Version:** 1.0  
**Date:** 2026-08-19

---

## Architecture

```
                    INTERNET
                       │
                    DNS (Route53)
                       │
                    CDN (CloudFront)
                       │
                LOAD BALANCER (ALB)
                       │
          ┌────────────┼────────────┐
          │            │            │
       FRONTEND      API 1        API N
       (ECS)        (ECS)        (ECS)
                       │
                 MODULAR MONOLITH
                       │
       ┌───────────────┼────────────────┐
       │               │                │
     REDIS          QUEUES           STORAGE
   (ElastiCache)   (Redis)          (S3)
       │               │                │
       │             WORKERS            │
       │             (ECS)              │
       │               │                │
       │       ┌───────┼───────┐        │
       │       │       │       │        │
       │      AI     MEDIA  NOTIFY      │
       │       │       │       │        │
       └───────┴───────┴───────┴────────┘
                       │
                  POSTGRESQL
                  (RDS)
```

---

## Deployment Flow

### 1. Code Changes
```bash
# Developer creates feature branch
git checkout -b feat/my-feature

# Make changes
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feat/my-feature
```

### 2. CI Pipeline (Automatic)
- Lint (Ruff)
- Type check (Mypy)
- Unit tests
- Integration tests
- Security scan (Trivy, Bandit, Semgrep)
- Frontend lint, type check, build

### 3. Merge to Main
- PR approved and merged
- Deploy pipeline triggers automatically

### 4. Deploy Pipeline (Automatic)
1. Build Docker images (API, Web)
2. Push to ECR with git SHA tag
3. Run database migrations
4. Update ECS task definitions
5. Deploy to ECS (rolling update)
6. Wait for service stability
7. Run smoke tests

### 5. Manual Approval (Staging → Production)
- Review staging metrics
- Verify staging smoke tests
- Approve production deployment

---

## Manual Deployment

### Deploy Specific Image
```bash
# Set environment
export ENV=prod
export ECR_REGISTRY=<account>.dkr.ecr.ap-south-1.amazonaws.com
export GIT_SHA=<commit-sha>

# Build and push
docker build -t $ECR_REGISTRY/tk-api:$GIT_SHA services/api
docker push $ECR_REGISTRY/tk-api:$GIT_SHA

# Update ECS
aws ecs update-service \
  --cluster tk-$ENV \
  --service tk-api \
  --force-new-deployment
```

### Run Migrations
```bash
# Set database URL from Secrets Manager
export TK_DATABASE_URL=$(aws secretsmanager get-secret-value \
  --secret-id tk-prod-runtime \
  --query 'SecretString.db_url' --output text)

# Run migrations
cd services/api
alembic upgrade head
```

---

## Environment Configuration

### Production Environment Variables
```bash
TK_ENV=prod
TK_LOG_LEVEL=INFO
TK_DATABASE_URL=<from Secrets Manager>
TK_JWT_SECRET=<from Secrets Manager>
TK_CORS_ORIGINS=["https://theekkar.in","https://www.theekkar.in"]
TK_MFA_ENFORCE_PRIVILEGED=true
TK_CELERY_ENABLED=true
TK_CELERY_BROKER_URL=redis://<elasticache>:6379/1
TK_MEDIA_STORAGE_MODE=minio
TK_MEDIA_MINIO_ENDPOINT=s3.ap-south-1.amazonaws.com
TK_MEDIA_MINIO_BUCKET=tk-media-prod
TK_AI_API_KEY=<from Secrets Manager>
TK_WEBHOOK_MASTER_SECRET=<from Secrets Manager>
```

---

## Rollback

### Automatic Rollback (GitHub Actions)
1. Go to Actions → Rollback
2. Select environment: prod
3. Select service: api (or all)
4. Run workflow

### Manual Rollback
```bash
# Get previous task definition
PREV_REV=$(aws ecs describe-task-definition \
  --task-definition tk-api-task \
  --query 'taskDefinition.revision' --output text)
PREV_REV=$((PREV_REV - 1))

# Rollback
aws ecs update-service \
  --cluster tk-prod \
  --service tk-api \
  --task-definition tk-api-task:$PREV_REV \
  --force-new-deployment

# Wait for stability
aws ecs wait services-stable \
  --cluster tk-prod \
  --services tk-api
```

---

## Monitoring

### Key Metrics
- API error rate
- API latency (p50, p95, p99)
- Database connections
- Queue depth
- Worker utilization
- Cache hit ratio
- AI cost

### Dashboards
- Grafana: API Overview, Database, Workers, Queues, AI
- CloudWatch: ECS, RDS, ElastiCache, S3

### Alerts
- API error rate > 1%
- API p95 > 2s
- Database connections > 80%
- Queue depth > 5000
- Worker failures > 5/hour
