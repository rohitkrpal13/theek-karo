# DISASTER RECOVERY — Theek Karo

**Version:** 1.0  
**Date:** 2026-08-19  
**Status:** Framework — implement with actual infrastructure

---

## 1. Recovery Objectives

| Component | RPO (Recovery Point) | RTO (Recovery Time) |
|-----------|---------------------|---------------------|
| Database | 1 hour | 4 hours |
| Object Storage | 24 hours | 2 hours |
| Application | 0 (stateless) | 15 minutes |
| Redis | 1 hour | 1 hour |
| Configuration | 0 (in code) | 5 minutes |

---

## 2. Failure Scenarios & Response

### 2.1 Database Unavailable

**Impact**: Case creation, search, all reads/writes affected  
**Detection**: Health check failure, connection pool exhaustion  
**Response**:
1. Alert fires (readiness probe fails)
2. Check database server status
3. If server down: restore from latest backup
4. If connection issue: check pool settings, network
5. Verify recovery with health check

**Mitigation**: Read replicas for read traffic, connection pool limits

### 2.2 Redis Unavailable

**Impact**: Rate limiting falls back to memory, cache misses, session issues  
**Detection**: Redis health check failure  
**Response**:
1. API continues with memory-based rate limiting (documented degradation)
2. Restart Redis
3. Verify queue connectivity
4. Monitor for any queued message loss

**Mitigation**: Redis persistence (AOF), memory fallback in application

### 2.3 Object Storage Unavailable

**Impact**: Media upload/download affected  
**Detection**: Storage health check failure  
**Response**:
1. Media upload returns 503 with retry-after
2. Existing media served from CDN cache if available
3. Check storage service status
4. If prolonged: activate backup storage if configured

**Mitigation**: CDN caching, graceful upload failure

### 2.4 AI Provider Unavailable

**Impact**: AI features unavailable, core case workflow continues  
**Detection**: Circuit breaker opens, AI health check failure  
**Response**:
1. AI circuit breaker prevents cascade failures
2. Core platform continues operating
3. AI features show "temporarily unavailable"
4. Monitor provider status for recovery

**Mitigation**: Circuit breaker, fallback providers, graceful degradation

### 2.5 Notification Provider Unavailable

**Impact**: Push/email/SMS delayed  
**Detection**: Delivery failure rate spike  
**Response**:
1. Notifications queued for retry (at-least-once delivery)
2. In-app notifications continue working
3. Check provider status
4. If prolonged: switch to fallback provider if configured

**Mitigation**: Retry with backoff, dead letter queue, fallback providers

### 2.6 Government Integration Unavailable

**Impact**: Government workflow features affected  
**Detection**: Integration health check failure  
**Response**:
1. External sync paused
2. Local case workflow continues
3. Check external API status
4. Retry with backoff when available

**Mitigation**: Idempotent operations, queue-based retry, circuit breaker

---

## 3. Backup Strategy

### 3.1 Database Backups

| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| Full Backup | Daily | 30 days | Separate region |
| WAL Archiving | Continuous | 7 days | Separate region |
| Logical Dump | Weekly | 90 days | Cold storage |

### 3.2 Object Storage Backups

| Type | Frequency | Retention |
|------|-----------|-----------|
| Cross-Region Replication | Real-time | Same as primary |
| Snapshot | Daily | 30 days |

### 3.3 Configuration Backups

| Type | Method |
|------|--------|
| Application Config | Git repository |
| Infrastructure Config | IaC (Terraform) |
| Secrets | Secret manager (not in backups) |

---

## 4. Restore Testing

### 4.1 Monthly Restore Test

1. Restore database from backup to test environment
2. Verify data integrity
3. Run application against restored database
4. Document recovery time
5. Update RPO/RTO if actual differs from target

### 4.2 Quarterly DR Drill

1. Simulate complete regional failure
2. Activate backup infrastructure
3. Verify all services recover
4. Document lessons learned
5. Update runbook

---

## 5. Communication Plan

### 5.1 Incident Severity Levels

| Level | Description | Response Time | Communication |
|-------|-------------|---------------|---------------|
| P1 | Complete outage | 15 minutes | Status page + internal |
| P2 | Major feature down | 1 hour | Status page |
| P3 | Minor feature issue | 4 hours | Internal |
| P4 | Cosmetic/non-urgent | 24 hours | Ticket |

### 5.2 Status Page

Public status page showing:
- API Status
- Case Submission
- Maps
- AI Features
- Notifications
- Government Integrations

---

## 6. Runbooks

### 6.1 Database Recovery

```bash
# 1. Check database status
pg_isready -h <db_host> -p 5432

# 2. If down, check storage
df -h /var/lib/postgresql/data

# 3. Restore from backup
pg_restore -h <db_host> -d theek_karo /backups/latest.dump

# 4. Verify
psql -h <db_host> -d theek_karo -c "SELECT count(*) FROM cases"
```

### 6.2 Redis Recovery

```bash
# 1. Check Redis status
redis-cli -h <redis_host> ping

# 2. If down, check memory
redis-cli -h <redis_host> info memory

# 3. Restart Redis
systemctl restart redis

# 4. Verify queue integrity
redis-cli -h <redis_host> llen tk:jobs
```

### 6.3 Application Recovery

```bash
# 1. Check application health
curl -f http://localhost:8000/healthz

# 2. Check readiness
curl -f http://localhost:8000/readyz

# 3. If issues, check logs
docker logs theek-karo-api --tail 100

# 4. Restart if needed
docker restart theek-karo-api
```

---

## 7. Prevention

### 7.1 Regular Maintenance

- Weekly: Review slow queries, optimize indexes
- Monthly: Restore test, capacity review
- Quarterly: DR drill, security audit
- Annually: Full architecture review

### 7.2 Monitoring

- Automated health checks every 30 seconds
- Alert on error budget burn
- Monitor storage growth trends
- Track dependency health
