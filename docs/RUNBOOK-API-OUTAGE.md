# RUNBOOK: API Outage

**Severity:** P1 (Critical)  
**Response Time:** 15 minutes  
**Last Updated:** 2026-08-19

---

## 1. Detection

### Symptoms
- Health check (`/healthz`) returns non-200
- Readiness check (`/readyz`) fails
- Users report "site is down"
- Monitoring dashboard shows error spike
- ALB target health shows unhealthy

### Automated Alerts
- `API Error Rate > 1% for 5 minutes`
- `API p95 Latency > 5s for 5 minutes`
- `Health check failures > 3 consecutive`

---

## 2. Immediate Response (First 15 minutes)

### Step 1: Confirm the Outage
```bash
# Check health endpoint
curl -sf https://api.theekkar.in/healthz

# Check readiness
curl -sf https://api.theekkar.in/readyz

# Check from multiple locations
curl -sf https://api.theekkar.in/api/v1/version
```

### Step 2: Check ECS Service Status
```bash
aws ecs describe-services \
  --cluster tk-prod \
  --services tk-api \
  --query 'services[0].{status:status,desired:desiredCount,running:runningCount,health:healthCheckGracePeriodSeconds}'
```

### Step 3: Check Recent Deployments
```bash
aws ecs describe-services \
  --cluster tk-prod \
  --services tk-api \
  --query 'services[0].deployments[*].{status:status,taskDefinition:taskDefinition,rolloutState:rolloutState}'
```

### Step 4: Check Application Logs
```bash
aws logs tail /ecs/tk-prod --since 15m --format short
```

### Step 5: Check Database
```bash
aws rds describe-db-instances \
  --db-instance-identifier tk-prod-pg \
  --query 'DBInstances[0].{status:DBInstanceStatus,cpu:ProcessorFeatures,storage:AllocatedStorage}'
```

---

## 3. Decision Tree

### If Recent Deployment Caused Issue
→ **ROLLBACK** (see `/docs/RUNBOOK-ROLLBACK.md`)

### If Database Issue
→ **DATABASE OUTAGE** (see `/docs/RUNBOOK-DATABASE.md`)

### If Redis Issue
→ **REDIS DEGRADED** (proceed with memory fallback)

### If Application Bug (No Recent Deploy)
→ **HOTFIX** (create fix, test, deploy)

### If External Provider Issue
→ **DEGRADE GRACEFULLY** (disable affected feature, notify users)

---

## 4. Rollback Procedure

```bash
# Via GitHub Actions
# Go to: Actions → Rollback → Run workflow
# Select: environment=prod, service=api

# Or via CLI
PREV_REVISION=$(( $(aws ecs describe-task-definition \
  --task-definition tk-api-task \
  --query 'taskDefinition.revision' --output text) - 1 ))

aws ecs update-service \
  --cluster tk-prod \
  --service tk-api \
  --task-definition tk-api-task:$PREV_REVISION \
  --force-new-deployment

aws ecs wait services-stable \
  --cluster tk-prod \
  --services tk-api
```

---

## 5. Communication

### Internal
- Post in #incident Slack channel
- Update status page

### External (if user-facing)
- Status page: "Investigating API issues"
- After resolution: "API restored"

---

## 6. Post-Incident

- [ ] Create incident report
- [ ] Identify root cause
- [ ] Add monitoring if gap found
- [ ] Update runbook if process changed
- [ ] Schedule postmortem
