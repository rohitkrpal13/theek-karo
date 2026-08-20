# PERFORMANCE — Theek Karo

**Version:** 1.0  
**Date:** 2026-08-19  

---

## 1. Performance Budget

### 1.1 API Response Times

| Endpoint Category | p50 | p95 | p99 |
|------------------|-----|-----|-----|
| Health/Status | 10ms | 50ms | 100ms |
| Read (single) | 50ms | 200ms | 500ms |
| Read (list) | 100ms | 300ms | 1000ms |
| Write (create) | 100ms | 500ms | 1000ms |
| Search | 100ms | 300ms | 1000ms |
| AI (chat) | 1s | 5s | 15s |

### 1.2 Database Query Times

| Query Type | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| Simple Read | 5ms | 20ms | 50ms |
| Indexed Lookup | 2ms | 10ms | 25ms |
| Complex Join | 20ms | 100ms | 300ms |
| Aggregation | 50ms | 200ms | 500ms |
| Full-text Search | 20ms | 100ms | 300ms |

---

## 2. Optimization Strategies

### 2.1 Database Optimization

1. **Indexing**: Ensure all foreign keys and frequently queried columns are indexed
2. **Connection Pooling**: 10-30 connections with pre-ping and recycle
3. **Query Optimization**: Avoid N+1, use eager loading, limit result sets
4. **Read Replicas**: Route read traffic to replicas for scale
5. **Partitioning**: Partition large tables (audit_logs, notifications) by time

### 2.2 Caching Strategy

| Data Type | TTL | Invalidation |
|-----------|-----|-------------|
| Public Institution | 1 hour | On update |
| Public Department | 1 hour | On update |
| Geography Hierarchy | 24 hours | On update |
| Analytics Summary | 5 minutes | On data change |
| Configuration | 1 hour | On deploy |
| User Profile | 5 minutes | On update |

### 2.3 API Optimization

1. **Pagination**: Cursor-based for large datasets
2. **Field Selection**: Return only needed fields
3. **Compression**: gzip/brotli for responses
4. **HTTP Caching**: ETags, Cache-Control headers
5. **Rate Limiting**: Prevent abuse, ensure fairness

### 2.4 Frontend Optimization

1. **Code Splitting**: Lazy load routes
2. **Image Optimization**: WebP, lazy loading, responsive images
3. **Bundle Size**: Tree shaking, minimize dependencies
4. **Caching**: Service worker for offline support
5. **CDN**: Static assets on CDN

---

## 3. Load Testing

### 3.1 Test Scenarios

| Scenario | Users | Duration | Target |
|----------|-------|----------|--------|
| Normal Load | 100 | 30 min | p95 < 500ms |
| Peak Load | 1000 | 15 min | p95 < 1s |
| Stress Test | 10000 | 5 min | Find breaking point |
| Soak Test | 100 | 24 hours | No memory leaks |

### 3.2 Key Metrics

- Requests per second
- Response time (p50, p95, p99)
- Error rate
- Database connection pool utilization
- Queue depth
- Memory usage
- CPU utilization

### 3.3 Load Testing Tools

- **k6**: API load testing
- **Locust**: Complex scenarios
- **pgbench**: Database benchmarking
- **wrk**: Simple HTTP load testing

---

## 4. Monitoring

### 4.1 Key Metrics to Track

| Metric | Warning | Critical |
|--------|---------|----------|
| API Error Rate | > 0.1% | > 1% |
| API p95 Latency | > 500ms | > 2s |
| DB Connection Pool | > 70% | > 90% |
| Queue Depth | > 1000 | > 5000 |
| Memory Usage | > 70% | > 90% |
| CPU Usage | > 70% | > 90% |
| Cache Hit Ratio | < 80% | < 50% |

### 4.2 Performance Dashboards

1. **API Performance**: Request rate, latency, errors
2. **Database Performance**: Query latency, connections, slow queries
3. **Cache Performance**: Hit ratio, memory, eviction rate
4. **Queue Performance**: Depth, processing time, failures
5. **Infrastructure**: CPU, memory, disk, network

---

## 5. Common Issues & Fixes

### 5.1 Slow API Responses

1. Check database query latency
2. Verify indexes are being used
3. Check for N+1 queries
4. Review connection pool utilization
5. Check cache hit ratio

### 5.2 High Database Load

1. Identify slow queries
2. Add missing indexes
3. Optimize query patterns
4. Add read replicas
5. Consider query result caching

### 5.3 Memory Leaks

1. Profile application memory
2. Check for growing caches
3. Review connection pool settings
4. Monitor worker memory usage
5. Check for large result sets in memory
