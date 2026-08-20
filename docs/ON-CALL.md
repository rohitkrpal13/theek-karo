# ON-CALL — Theek Karo

**Version:** 1.0  
**Date:** 2026-08-19

---

## On-Call Schedule

### Rotation
- **Primary:** 1 week rotation
- **Secondary:** 1 week rotation (backup)
- **Escalation:** Engineering lead

### Contact
- **Primary:** [Phone number]
- **Secondary:** [Phone number]
- **Slack:** #oncall-theek-karo
- **PagerDuty:** [If configured]

---

## Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| P1 | Complete outage | 15 minutes | Immediate |
| P2 | Major feature down | 1 hour | Within 2 hours |
| P3 | Minor feature issue | 4 hours | Within 8 hours |
| P4 | Cosmetic/non-urgent | 24 hours | Next business day |

---

## Incident Response Process

### 1. Detection (Automated)
- Monitoring alerts fire
- Health checks fail
- User reports received

### 2. Acknowledgment (5 minutes)
- Acknowledge alert
- Post in #incidents channel
- Begin investigation

### 3. Investigation (15 minutes)
- Check dashboards
- Review logs
- Identify scope
- Determine severity

### 4. Containment (30 minutes)
- If deployment issue: rollback
- If provider issue: degrade gracefully
- If security issue: isolate

### 5. Resolution (varies)
- Apply fix
- Verify resolution
- Monitor stability

### 6. Communication
- Update status page
- Notify affected users
- Internal postmortem

### 7. Postmortem (within 48 hours)
- Document timeline
- Identify root cause
- Create action items
- Update runbooks

---

## Common Scenarios

### API Down
1. Check ECS service status
2. Check recent deployments
3. If deployment issue: rollback
4. If application issue: check logs
5. If database issue: see DB runbook

### Database Down
1. Check RDS status
2. Check CloudWatch metrics
3. If AZ failure: wait for Multi-AZ failover
4. If storage full: cleanup or resize
5. If connection limit: tune pool

### Redis Down
1. Check ElastiCache status
2. API continues with memory fallback
3. Queue processing paused
4. Restart Redis if needed

### AI Provider Down
1. Check provider status page
2. Circuit breaker activates
3. Core features continue
4. AI features show "unavailable"

### High Error Rate
1. Check which endpoints
2. Check recent changes
3. Check database queries
4. Check external providers
5. Rollback if needed

---

## Escalation Path

```
On-Call Engineer
    ↓ (if unresolved in 30 min)
Engineering Lead
    ↓ (if unresolved in 2 hours)
CTO/VP Engineering
    ↓ (if security/data breach)
Legal/Compliance
```

---

## Post-Incident Review

### Template
```markdown
# Incident Report: [Title]

**Date:** YYYY-MM-DD
**Duration:** X hours Y minutes
**Severity:** P1/P2/P3/P4
**Impact:** [Description]

## Timeline
- HH:MM - Alert fired
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix applied
- HH:MM - Verified resolved

## Root Cause
[Description]

## Impact
- Users affected: X
- Duration: X hours
- Features affected: [list]

## Resolution
[What was done]

## Prevention
- [ ] Action item 1
- [ ] Action item 2

## Lessons Learned
[What we learned]
```

---

## Monitoring Checklist

### Daily
- [ ] Check error rates
- [ ] Check latency
- [ ] Check database metrics
- [ ] Check queue depth

### Weekly
- [ ] Review incident reports
- [ ] Review cost metrics
- [ ] Review security alerts
- [ ] Update on-call schedule

### Monthly
- [ ] Postmortem review
- [ ] Runbook updates
- [ ] Capacity planning
- [ ] Security audit
