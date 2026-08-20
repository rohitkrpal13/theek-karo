# RUNBOOK: Database Outage

**Severity:** P1 (Critical)  
**Response Time:** 15 minutes  
**RTO:** 4 hours  
**RPO:** 1 hour

---

## 1. Detection

- Health check fails with "Database dependency unavailable"
- Connection pool exhaustion in logs
- High database CPU/connections in CloudWatch

## 2. Immediate Response

### Check RDS Status
```bash
aws rds describe-db-instances \
  --db-instance-identifier tk-prod-pg \
  --query 'DBInstances[0].{status:DBInstanceStatus,cpu:ProcessorFeatures}'
```

### Check CloudWatch Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=tk-prod-pg \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

### Check Connection Count
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBInstanceIdentifier,Value=tk-prod-pg \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Maximum
```

## 3. Recovery

### If RDS is Down (AZ Failure)
- Multi-AZ should auto-failover (RTO ~minutes)
- If not, contact AWS support
- If prolonged: restore from latest backup

### If Connection Limit Reached
```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Terminate idle connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '10 minutes';
```

### If Storage Full
```sql
-- Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;

-- Vacuum if bloated
VACUUM ANALYZE;
```

## 4. Restore from Backup

```bash
# List available backups
aws rds describe-db-snapshots \
  --db-instance-identifier tk-prod-pg \
  --query 'DBSnapshots[*].{id:DBSnapshotIdentifier,time:SnapshotCreateTime,status:Status}'

# Restore to new instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier tk-prod-restore \
  --db-snapshot-identifier <snapshot-id>

# Wait for restore
aws rds wait db-instance-available --db-instance-identifier tk-prod-restore

# Update TK_DATABASE_URL to new endpoint
# Update DNS or connection string
```

## 5. Post-Incident
- Document timeline
- Check if data loss occurred (compare RPO)
- Review connection pool settings
- Consider read replicas for scale
