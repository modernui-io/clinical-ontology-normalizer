# Infrastructure Hardening Guide (VPE-6)

Production Docker Compose refinement and infrastructure hardening recommendations
for the Clinical Trial Patient Recruitment Platform.

## Current State Assessment

The `docker-compose.prod.yml` file defines 9 services: PostgreSQL, Redis, Neo4j,
Zookeeper, Kafka, Backend API, RQ Worker, Frontend, and Nginx reverse proxy.

### Strengths (already implemented)

- **Resource limits**: All services have CPU and memory limits via `deploy.resources`.
- **Security hardening**: `no-new-privileges`, `cap_drop: ALL`, and `read_only` filesystem
  are applied to most services.
- **Health checks**: All services define health check probes with intervals and retries.
- **Logging**: JSON-file driver with `max-size` and `max-file` rotation on all services.
- **Environment secrets**: Sensitive values use `${VAR:?required}` syntax to prevent
  deployment with missing credentials.
- **PostgreSQL tuning**: Production-grade settings for shared_buffers, WAL, and
  connection pooling.

### Areas for Improvement

| Area | Current | Recommended |
|------|---------|-------------|
| Restart policies | Missing on most services | Add `restart: unless-stopped` to all |
| Image pinning | `neo4j:5`, `nginx:alpine` lack patch version | Pin to `neo4j:5.x.y`, `nginx:1.27-alpine` |
| Network segmentation | Single default network | Separate frontend, backend, data networks |
| Secret management | Environment variables | Docker Secrets or external vault |
| TLS termination | Nginx config file mount | Automated cert management (certbot sidecar) |
| Backup automation | Not configured | pg_dump cron + volume snapshots |
| Worker health check | Checks HTTP (wrong for worker) | Check RQ process or queue depth |

## Per-Service Recommendations

### PostgreSQL

- **Restart policy**: Add `restart: unless-stopped`.
- **Backups**: Add a sidecar container running `pg_dump` on a cron schedule.
  Store backups in an encrypted S3 bucket with 30-day retention.
- **Connection pooling**: Consider PgBouncer in front of PostgreSQL to manage
  connection exhaustion under load.
- **Monitoring**: Expose `pg_stat_statements` and scrape with Prometheus postgres_exporter.

### Redis

- **Restart policy**: Add `restart: unless-stopped`.
- **Persistence**: Currently using AOF (`appendonly yes`). Consider RDB snapshots
  as a secondary backup mechanism.
- **Memory**: Monitor memory usage relative to the 768MB maxmemory limit.
  Alert when utilization exceeds 80%.

### Neo4j

- **Image pinning**: Pin to a specific patch version (e.g., `neo4j:5.26.0`).
- **Restart policy**: Add `restart: unless-stopped`.
- **Backup**: Configure `neo4j-admin database dump` via cron for graph backups.
- **read_only**: Add `read_only: true` with appropriate tmpfs mounts.

### Kafka + Zookeeper

- **Image pinning**: Both services lack explicit image tags. Pin to specific
  Confluent Platform versions.
- **Restart policy**: Add `restart: unless-stopped`.
- **Replication**: Current config has `replication_factor: 1`. For production,
  deploy 3 Kafka brokers with replication factor 3.
- **Migration**: Consider migrating from Zookeeper to KRaft mode for Kafka 3.x+.

### Backend API

- **Restart policy**: Add `restart: unless-stopped`.
- **Graceful shutdown**: Configure `stop_grace_period: 30s` to allow in-flight
  requests to complete.
- **Scaling**: Current config uses `replicas: 2`. Consider horizontal pod
  autoscaling based on CPU/request metrics.

### RQ Worker

- **Health check**: The current health check (`curl http://localhost:8000/health`)
  is incorrect for a worker process. Replace with a check that verifies the
  RQ worker process is alive and the queue is accessible.
- **Restart policy**: Add `restart: unless-stopped`.

### Frontend

- **Restart policy**: Add `restart: unless-stopped`.
- **Caching**: Add cache headers for static assets (Next.js handles this
  internally but verify nginx config passes them through).

### Nginx

- **Image pinning**: Pin to `nginx:1.27-alpine` (specific patch version).
- **TLS**: Automate certificate renewal with certbot or use ACME protocol.
- **Rate limiting**: Configure `limit_req_zone` for API endpoints.
- **Security headers**: Verify HSTS, CSP, X-Frame-Options are set.

## Resource Limit Recommendations

Based on expected workload for a clinical trial platform handling 500-1000
concurrent users:

| Service | CPU Limit | Memory Limit | Rationale |
|---------|-----------|--------------|-----------|
| PostgreSQL | 4 cores | 8 GB | Primary data store, complex queries |
| Redis | 1 core | 2 GB | Cache + job queue, memory-bound |
| Neo4j | 2 cores | 4 GB | Graph queries, heap-intensive |
| Kafka | 2 cores | 4 GB | Message throughput, log retention |
| Zookeeper | 0.5 cores | 512 MB | Lightweight coordination |
| Backend | 4 cores | 4 GB | API processing, NLP workloads |
| Worker | 2 cores | 2 GB | Background job processing |
| Frontend | 1 core | 512 MB | Static serving, SSR |
| Nginx | 1 core | 256 MB | Reverse proxy, TLS |

## Logging Strategy

### Current

All services use `json-file` driver with rotation. This is adequate for
single-host deployments.

### Recommended

1. **Centralized logging**: Deploy an ELK stack (Elasticsearch, Logstash, Kibana)
   or use a managed service (Datadog, CloudWatch).
2. **Log format**: Ensure all services emit structured JSON logs with fields:
   - `timestamp`, `level`, `service`, `request_id`, `message`
3. **Retention**: 30 days hot storage, 90 days warm, 1 year cold (compliance).
4. **Alerting**: Configure alerts for ERROR-level logs, especially on critical
   paths (authentication, data ingestion, screening).

## Backup Schedule

| Data Store | Method | Frequency | Retention | Location |
|-----------|--------|-----------|-----------|----------|
| PostgreSQL | pg_dump (full) | Daily 02:00 UTC | 30 days | Encrypted S3 |
| PostgreSQL | WAL archiving | Continuous | 7 days | Local + S3 |
| Neo4j | neo4j-admin dump | Daily 03:00 UTC | 14 days | Encrypted S3 |
| Redis | RDB snapshot | Every 6 hours | 7 days | Local volume |
| Kafka | Topic backup | Weekly | 30 days | S3 |

### Restore Testing

- Monthly automated restore test to a staging environment.
- Quarterly disaster recovery drill with documented RTO/RPO verification.

## Monitoring Integration Points

| Service | Metrics Endpoint | Exporter |
|---------|-----------------|----------|
| PostgreSQL | N/A | postgres_exporter on :9187 |
| Redis | `INFO` command | redis_exporter on :9121 |
| Neo4j | `:2004/metrics` | Built-in Prometheus endpoint |
| Kafka | JMX | kafka_exporter on :9308 |
| Backend | `/api/v1/metrics` | Built-in Prometheus endpoint |
| Nginx | stub_status | nginx_exporter on :9113 |

### Key Metrics to Monitor

- **Latency**: P50, P95, P99 response times per endpoint
- **Error rate**: 5xx responses as percentage of total
- **Saturation**: CPU, memory, connection pool utilization
- **Queue depth**: RQ pending jobs, Kafka consumer lag

## Network Segmentation Plan

### Proposed Networks

```
frontend-net:    nginx <-> frontend
backend-net:     nginx <-> backend, frontend <-> backend
data-net:        backend <-> postgres, redis, neo4j, kafka
messaging-net:   kafka <-> zookeeper, backend <-> kafka, worker <-> kafka
```

### Implementation

```yaml
networks:
  frontend-net:
    driver: bridge
  backend-net:
    driver: bridge
  data-net:
    driver: bridge
    internal: true  # No external access
  messaging-net:
    driver: bridge
    internal: true
```

Each service should only be attached to the networks it needs, following
the principle of least privilege.

## Secret Management Recommendations

### Current State

Secrets are passed via environment variables with `${VAR:?required}` syntax.
This is acceptable for development but has limitations in production:

- Secrets visible in `docker inspect` output
- Secrets stored in shell history if set inline
- No rotation without container restart

### Recommended Approach

1. **Short-term**: Use Docker Secrets with `docker secret create` for all
   sensitive values (passwords, API keys, certificates).
2. **Medium-term**: Integrate HashiCorp Vault or AWS Secrets Manager for
   dynamic secret generation and automatic rotation.
3. **Long-term**: Implement mutual TLS (mTLS) between services to eliminate
   password-based authentication where possible.

### Secrets Inventory

| Secret | Services | Rotation Period |
|--------|----------|-----------------|
| POSTGRES_PASSWORD | postgres, backend, worker | 90 days |
| NEO4J_PASSWORD | neo4j, backend, worker | 90 days |
| API_KEY | backend | 30 days |
| TLS certificates | nginx | Auto via ACME |
| JWT signing key | backend | 180 days |
