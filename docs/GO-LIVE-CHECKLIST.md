# GO-LIVE CHECKLIST — Theek Karo

**Version:** 1.0  
**Date:** 2026-08-19  
**Status:** Pre-launch readiness assessment

---

## Pre-Launch Criteria

### Infrastructure ✅
- [ ] AWS account provisioned with appropriate limits
- [ ] VPC, subnets, security groups configured
- [ ] ECS Fargate cluster operational
- [ ] RDS Postgres 16 with PostGIS provisioned
- [ ] ElastiCache Redis provisioned
- [ ] S3 buckets created (media, exports)
- [ ] CloudFront distribution configured
- [ ] ALB with HTTPS configured
- [ ] ACM certificates issued
- [ ] Route53 DNS configured

### CI/CD ✅
- [ ] GitHub Actions CI pipeline passing
- [ ] Security scans passing (Trivy, Bandit, Semgrep, pip-audit)
- [ ] Deploy pipeline tested on staging
- [ ] Rollback pipeline tested
- [ ] ECR repositories created
- [ ] Container images built and pushed

### Database ✅
- [ ] Migrations up to date (0040)
- [ ] Fresh database migration tested
- [ ] Rollback migration tested
- [ ] Backup configured (daily + PITR)
- [ ] Multi-AZ enabled for prod
- [ ] Connection pool tuned

### Security ✅
- [ ] No hardcoded secrets in codebase
- [ ] Secrets Manager configured
- [ ] JWT secret >= 32 characters
- [ ] MFA enforced for privileged roles
- [ ] CORS configured for production domains
- [ ] Rate limiting active
- [ ] Security headers present
- [ ] Input validation active
- [ ] SSRF protection active

### Application ✅
- [ ] Health endpoints working (`/healthz`, `/readyz`)
- [ ] Comprehensive health check working
- [ ] Auth flow working (signup, login, logout)
- [ ] Case creation working
- [ ] Case viewing working
- [ ] Search working
- [ ] Maps working
- [ ] Notifications working
- [ ] AI assistant working (with rate limits)
- [ ] Admin dashboard working
- [ ] Government workflow working

### Monitoring ✅
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards configured
- [ ] Alert rules configured
- [ ] Log aggregation working
- [ ] Error tracking working

### Documentation ✅
- [ ] API documentation (OpenAPI) up to date
- [ ] Runbooks created
- [ ] On-call process defined
- [ ] Incident response process defined

---

## Launch Day Checklist

### Pre-Launch (T-2 hours)
- [ ] Final staging smoke tests pass
- [ ] Production backup taken
- [ ] Rollback plan confirmed
- [ ] On-call team notified
- [ ] Status page updated: "Maintenance in progress"

### Launch (T-0)
- [ ] DNS cutover (if applicable)
- [ ] SSL certificate verified
- [ ] Health checks passing
- [ ] Smoke tests against production
- [ ] Status page updated: "Operational"

### Post-Launch (T+1 hour)
- [ ] Monitor error rates
- [ ] Monitor latency
- [ ] Monitor database connections
- [ ] Monitor queue depth
- [ ] Check user registrations
- [ ] Check case creation

### Post-Launch (T+24 hours)
- [ ] Review overnight metrics
- [ ] Check for any incidents
- [ ] Review cost data
- [ ] User feedback review

---

## Rollback Criteria

**Immediate Rollback If:**
- Error rate > 5% for 5 minutes
- p95 latency > 10s for 5 minutes
- Database unreachable
- Authentication broken
- Cross-tenant data exposure
- Security vulnerability exploited

**Rollback Procedure:**
```bash
# Via GitHub Actions: Rollback → prod → all
# Or via CLI:
aws ecs update-service \
  --cluster tk-prod \
  --service tk-api \
  --task-definition tk-api-task:<previous-revision> \
  --force-new-deployment
```

---

## Communication Template

### Launch Announcement
```
Theek Karo is now live!

We're launching in [region/district] as part of our staged rollout.

Report civic issues at: https://theekkar.in
```

### Incident Template
```
We're experiencing [issue description].

Impact: [affected features]
Status: Investigating
ETA: [estimated resolution]

Updates: https://status.theekkar.in
```

### Resolution Template
```
The issue has been resolved.

Summary: [what happened]
Root cause: [cause]
Prevention: [what we're doing to prevent recurrence]

We apologize for the inconvenience.
```
