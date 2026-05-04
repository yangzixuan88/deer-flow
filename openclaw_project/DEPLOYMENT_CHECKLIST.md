(No response from agent)# OpenClaw Deployment Checklist
## Phase 18: 部署上线

---

## Pre-Deployment Verification

### 1. Code Quality Gates ✓

- [ ] All tests passing (`npm test`)
- [ ] TypeScript compilation clean (`npx tsc --noEmit`)
- [ ] ESLint checks passing (`npx eslint src/`)
- [ ] Security scan completed (`npm audit`)
- [ ] Docker image builds successfully

### 2. Environment Configuration

- [ ] Redis password set in secrets
- [ ] Grafana admin password set in secrets
- [ ] N8N webhook URL configured
- [ ] Cloudflare tunnel token configured
- [ ] SMTP credentials for alerts configured
- [ ] Slack webhook URL for notifications configured

### 3. Infrastructure Readiness

- [ ] Docker and Docker Compose installed on server
- [ ] Ports available: 6379, 8080, 8081, 9411, 50005
- [ ] Sufficient disk space (>10GB)
- [ ] Network connectivity to GitHub Container Registry

---

## Staging Deployment

### 4. Deploy to Staging

```bash
# Pull latest images
docker compose -f src/infrastructure/docker-compose.yml pull

# Deploy
docker compose -f src/infrastructure/docker-compose.yml up -d

# Verify health
curl http://localhost:8081/health
curl http://localhost:8081/ready
```

### 5. Post-Staging Verification

- [ ] Health endpoint returns 200
- [ ] Ready endpoint returns 200
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards loading
- [ ] Redis connection working
- [ ] Dapr sidecar running
- [ ] n8n workflow engine accessible

### 6. E2E Testing

- [ ] Playwright tests passing
- [ ] Critical user flows verified
- [ ] Performance within acceptable range

---

## Production Deployment

### 7. Pre-Production Checklist

- [ ] Staging deployment verified
- [ ] E2E tests passing on staging
- [ ] Rollback plan documented
- [ ] On-call team notified
- [ ] Maintenance window scheduled (if needed)

### 8. Production Deployment

```bash
# Pull production image
docker pull ghcr.io/<owner>/openclaw:main

# Deploy
docker compose -f src/infrastructure/docker-compose.yml up -d

# Verify
curl http://localhost:8081/health
```

### 9. Post-Production Verification

- [ ] All health checks passing
- [ ] No increase in error rates
- [ ] Latency within SLO
- [ ] Memory usage stable
- [ ] Task queue processing normally

---

## Monitoring & Alerts

### 10. Alert Verification

- [ ] Alertmanager receiving alerts
- [ ] Slack notifications working
- [ ] Email notifications working
- [ ] On-call pager integrated (PagerDuty optional)

### 11. Dashboards

- [ ] Grafana OpenClaw Overview accessible
- [ ] Prometheus metrics available
- [ ] Custom dashboards created

---

## Rollback Procedure

If issues detected:

```bash
# Rollback to previous version
docker pull ghcr.io/<owner>/openclaw:<previous-tag>
docker compose -f src/infrastructure/docker-compose.yml up -d

# Or use docker-compose rollback
docker compose -f src/infrastructure/docker-compose.yml rollback
```

---

## Contacts

- **On-Call**: oncall@openclaw.example.com
- **Infrastructure Team**: infra-team@openclaw.example.com
- **OpenClaw Team**: openclaw-team@openclaw.example.com

---

## Version History

| Date | Version | Changes | Deployed By |
|------|---------|---------|-------------|
| 2026-04-14 | 2.0.0 | Initial production deployment | |
