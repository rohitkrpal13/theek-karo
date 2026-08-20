# CAPACITY PLAN — Theek Karo

**Version:** 1.0  
**Date:** 2026-08-19  
**Status:** Planning targets — not current infrastructure claims

---

## 1. Planning Targets

| Metric | Planning Target | Timeframe |
|--------|----------------|-----------|
| Registered Users | 10,000,000 | 3 years |
| Monthly Active Users | 2,000,000 | 3 years |
| Daily Active Users | 500,000 | 3 years |
| Total Cases (lifetime) | 100,000,000 | 5 years |
| Monthly New Cases | 500,000 | 3 years |
| Peak Concurrent Users | 100,000 | Campaign events |
| Notifications/Day | 10,000,000 | Peak campaigns |
| Media Storage | 10 TB | 3 years |
| RAG Documents | 1,000,000 | 3 years |
| AI Requests/Day | 500,000 | 3 years |

---

## 2. Capacity Model

### 2.1 Traffic Estimates

| Metric | Normal Day | Peak Day | Spike |
|--------|-----------|----------|-------|
| API Requests/sec | 500 | 2,000 | 10,000 |
| Case Creation/sec | 10 | 50 | 200 |
| Search Queries/sec | 100 | 500 | 2,000 |
| Notification Sends/sec | 50 | 500 | 2,000 |
| AI Requests/sec | 10 | 100 | 500 |

### 2.2 Storage Estimates

| Type | Growth Rate | 1-Year | 3-Year |
|------|------------|--------|--------|
| Database (cases) | 1 GB/day | 365 GB | 1 TB |
| Media (images) | 10 GB/day | 3.6 TB | 10 TB |
| Media (videos) | 50 GB/day | 18 TB | 50 TB |
| Documents | 1 GB/day | 365 GB | 1 TB |
| RAG Index | 500 MB/day | 180 GB | 500 GB |
| Audit Logs | 500 MB/day | 180 GB | 500 GB |

### 2.3 Compute Estimates

| Component | Min Instances | Recommended | Peak Scale |
|-----------|--------------|-------------|------------|
| API Server | 2 | 4-8 | 16 |
| Worker | 1 | 2-4 | 8 |
| Database | 1 (vertical) | Primary + 1 Replica | Primary + 3 Replicas |
| Redis | 1 | 1 (6 GB) | 1 Cluster |
| Object Storage | 1 | Managed (S3/MinIO) | Multi-region |
| Search | PostgreSQL FTS | OpenSearch (3 nodes) | 5 nodes |

---

## 3. SLO/SLI/SLA Definitions

### 3.1 Service Level Indicators (SLIs)

| SLI | Measurement |
|-----|-------------|
| API Availability | Non-5xx responses / Total responses |
| API Latency | Request duration (seconds) |
| Case Creation Success | Successful creates / Total attempts |
| Notification Delivery | Delivered / Sent |
| AI Response Success | Successful responses / Total attempts |

### 3.2 Service Level Objectives (SLOs)

| SLO | Target | Window |
|-----|--------|--------|
| API Availability | 99.9% | 30-day rolling |
| API p95 Latency | < 500ms | 30-day rolling |
| Case Creation p95 | < 1s | 30-day rolling |
| Notification Delivery | > 99% | 30-day rolling |
| AI Response Availability | 99% | 30-day rolling |

### 3.3 Error Budgets

| SLO | Target | Error Budget/Month |
|-----|--------|-------------------|
| 99.9% Availability | 99.9% | 43.8 minutes downtime |
| 99.95% Availability | 99.95% | 21.9 minutes downtime |

---

## 4. Performance Budgets

| Operation | p50 Target | p95 Target | p99 Target |
|-----------|-----------|-----------|-----------|
| API Read | 50ms | 200ms | 500ms |
| API Write | 100ms | 500ms | 1000ms |
| Case Create | 200ms | 500ms | 1000ms |
| Search | 100ms | 300ms | 1000ms |
| Map Query | 100ms | 500ms | 1500ms |
| AI Chat | 1s | 5s | 15s |
| Notification | 500ms | 2s | 5s |

---

## 5. Scaling Strategy

### 5.1 Horizontal Scaling

- **API Servers**: Stateless, scale behind load balancer
- **Workers**: Scale by queue depth (Celery autoscale)
- **Read Replicas**: Add replicas for read-heavy workloads

### 5.2 Vertical Scaling

- **Database**: Scale up CPU/RAM before sharding
- **Redis**: Scale memory before clustering
- **Object Storage**: Managed service scales automatically

### 5.3 Auto-scaling Rules

| Metric | Scale Up | Scale Down |
|--------|----------|------------|
| CPU > 70% | +1 instance | -1 if < 30% for 10min |
| Queue Depth > 1000 | +1 worker | -1 if < 100 for 10min |
| Memory > 80% | +1 instance | -1 if < 40% for 10min |
| p95 Latency > 1s | +2 instances | -1 if < 200ms for 10min |

---

## 6. Cost Estimates

### 6.1 Monthly Cost Projections

| Component | Low Traffic | Normal | Peak |
|-----------|------------|--------|------|
| Compute (API) | $200 | $800 | $2,000 |
| Compute (Workers) | $100 | $400 | $1,000 |
| Database | $200 | $500 | $1,500 |
| Redis | $50 | $150 | $400 |
| Object Storage | $50 | $500 | $1,000 |
| CDN | $20 | $200 | $500 |
| AI (LLM) | $100 | $1,000 | $5,000 |
| SMS/Email | $50 | $500 | $2,000 |
| **Total** | **$770** | **$4,050** | **$13,400** |

---

## 7. Peak Traffic Design

### 7.1 Traffic Spike Scenarios

1. **National Campaign**: 10x normal traffic for 24-48 hours
2. **Major Incident**: 50x normal traffic for 2-6 hours
3. **Viral Case**: 100x normal traffic for 1-2 hours
4. **Election Period**: 3x normal traffic for 2-4 weeks

### 7.2 Graceful Degradation

| Component | Degrades To |
|-----------|-------------|
| AI Unavailable | Normal case workflow continues |
| Search Unavailable | Basic database search |
| Push Notifications | In-app notifications only |
| Maps Unavailable | List view |
| Analytics Unavailable | Operational data |

---

## 8. Monitoring & Alerting

### 8.1 Key Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| API Error Rate | > 1% for 5min | High |
| API p95 Latency | > 2s for 5min | High |
| Database Connections | > 80% pool | High |
| Queue Depth | > 5000 for 10min | Medium |
| Worker Failure | > 5 failures/hour | High |
| Storage > 80% | Capacity warning | Medium |
| AI Cost Spike | > 300% normal | Medium |

### 8.2 Dashboards

1. **API Overview**: Request rate, latency, errors
2. **Database**: Connections, query latency, replication lag
3. **Workers**: Queue depth, processing time, failures
4. **Cache**: Hit ratio, memory usage
5. **Cost**: Daily spend by service
6. **SLO**: Error budget burn rate
