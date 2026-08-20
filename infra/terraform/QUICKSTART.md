# Quick Start — Deploy Theek Karo to AWS

## 5-Minute Deployment (Staging)

### 1. Configure AWS

```bash
aws configure
# Enter: Access Key, Secret Key, Region (ap-south-1), Format (json)
```

### 2. Generate Secrets

```bash
export DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c 24)
export JWT_SECRET=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)
echo "Save these: DB_PASSWORD=$DB_PASSWORD JWT_SECRET=$JWT_SECRET"
```

### 3. Deploy

```bash
./infra/terraform/deploy.sh staging
```

### 4. Configure DNS

Point `staging.theekkar.in` and `api.staging.theekkar.in` to the ALB DNS name.

### 5. Verify

```bash
curl https://api.staging.theekkar.in/healthz
# Should return: {"status": "ok"}
```

---

## What Gets Created

| Resource | Description |
|----------|-------------|
| VPC | 2 public + 2 private subnets |
| ECS Cluster | Fargate (api, worker, web) |
| RDS | Postgres 16 + PostGIS |
| Redis | ElastiCache for caching |
| S3 | Media storage |
| CloudFront | CDN for media |
| ALB | Load balancer with HTTPS |
| ACM | SSL certificates |
| Secrets Manager | Database, JWT, AI keys |

---

## Cost

- **Staging:** ~$100-150/month
- **Production:** ~$300-450/month

---

## Rollback

```bash
# Quick rollback to previous version
aws ecs update-service --cluster tk-staging --service tk-api --force-new-deployment
```

---

## Next Steps

1. Read `docs/CLOUD-DEPLOYMENT-GUIDE.md` for detailed instructions
2. Set up GitHub Actions for CI/CD
3. Configure monitoring with Prometheus/Grafana
4. Run load tests with k6
