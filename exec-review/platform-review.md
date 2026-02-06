# Platform & Infrastructure Assessment

**Prepared by:** VP of Platform/Infrastructure
**Date:** 2026-02-06
**Classification:** Executive Review -- Internal

---

## Executive Summary

This platform runs a polyglot data architecture (PostgreSQL + Neo4j + Redis + Kafka) behind a FastAPI backend with a Next.js frontend, all orchestrated via Docker Compose. The foundation is architecturally sound for a clinical data platform at the pilot/early-production stage. The health check infrastructure is well-designed, the circuit breaker pattern is implemented, and the codebase shows genuine platform engineering discipline (connection pooling, thread-safe singletons, request context propagation).

However, the system has critical gaps that must be closed before any enterprise or production deployment: there is no container orchestration beyond Compose, no automated backup/recovery, no centralized logging or metrics pipeline, and every stateful service runs as a single instance with no replication. The "graceful degradation to mock mode" pattern -- where Neo4j and Kafka silently fall back to fake data -- is appropriate for development but is a reliability hazard if it reaches production without explicit observability.

The path to 99.9% uptime is achievable in 2-3 quarters with focused investment. The path to 99.99% requires managed services or dedicated SRE headcount.

---

## 1. Service Topology Assessment

### Current Architecture (docker-compose.yml)

| Service | Image | Port Mapping | Healthcheck | Restart Policy | Depends On |
|---|---|---|---|---|---|
| postgres | postgres:16-alpine | 15432:5432 | pg_isready | unless-stopped | -- |
| redis | redis:7-alpine | 16379:6379 | redis-cli ping | unless-stopped | -- |
| neo4j | neo4j:5 | 7474/7687 | wget spider | unless-stopped | -- |
| zookeeper | confluentinc/cp-zookeeper:7.5.0 | 2181 | nc -z | unless-stopped | -- |
| kafka | confluentinc/cp-kafka:7.5.0 | 9092/29092 | broker-api-versions | unless-stopped | zookeeper (healthy) |
| backend | custom Dockerfile | 8080:8000 | curl /health | unless-stopped | -- (no explicit deps) |
| worker | custom Dockerfile | -- | none | unless-stopped | postgres (healthy), redis (healthy) |
| migrations | custom Dockerfile | -- | -- | -- (run-once profile) |
| frontend | custom Dockerfile | 3000:3000 | none | unless-stopped | backend |

### Findings

**What works well:**
- Every data store (PostgreSQL, Redis, Neo4j, Kafka) has a Docker healthcheck defined, which is better than most early-stage systems.
- The migration service uses Compose profiles (`migrate`) so it only runs on demand -- correct pattern.
- Restart policies are `unless-stopped` across the board.
- Non-default host ports (15432, 16379) prevent collision with local development services.

**Critical gaps:**

1. **Backend has no dependency ordering.** The backend container does not declare `depends_on` for postgres, redis, or neo4j. It relies on graceful fallback (mock mode) rather than startup ordering. In a cold-start scenario, the backend may begin serving requests before postgres is ready, causing the health endpoint to report "unhealthy" during the first 30-60 seconds.

2. **Worker has no healthcheck.** The RQ worker (`con-worker`) has no Docker healthcheck defined. If the worker process crashes but the container stays alive (zombie state), Docker will not restart it and job processing silently stops.

3. **Frontend has no healthcheck.** Same issue -- a Next.js container that fails to bind port 3000 will not be detected.

4. **Single instance of every service.** There is zero horizontal scaling. The PostgreSQL instance is the system-of-record for a healthcare platform with no replica, no failover, and no streaming replication.

5. **Volume driver is `local` for all data volumes.** No remote/network storage. A host failure loses all data.

6. **Neo4j password mismatch.** docker-compose.yml sets `NEO4J_AUTH: neo4j/password` on the Neo4j container but passes `NEO4J_PASSWORD: clinical123` to the backend. These do not match. The backend will fail to authenticate against Neo4j, triggering mock mode silently.

7. **Kafka replication factor is 1.** Single-broker Kafka with `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1`. Any Kafka restart loses uncommitted consumer offsets.

---

## 2. Database Architecture Assessment

### PostgreSQL (Primary OLTP Store)

**Role:** System of record for documents, clinical facts, mentions, knowledge graph nodes/edges, audit logs, RBAC, OMOP CDM tables, vocabulary, calculators, pipelines, SMART apps, and policies. 36 Alembic migrations spanning the full schema.

**Engine:** `asyncpg` via SQLAlchemy async, with connection pool metrics exposed in the health endpoint.

**Assessment:**
- Schema is well-structured with progressive migrations. The migration chain from `001_create_document_tables` through `036_add_narrative_node_edge_types` shows disciplined evolution.
- Connection pool health is monitored (pool size, checked in/out, overflow) -- a strong signal of platform maturity.
- Request context propagation (`DatabaseRequestContext` via `contextvars`) enables per-request tracing through database operations.
- **Risk:** No evidence of read replicas, connection limits, or statement timeouts configured. The default `asyncpg` pool under load will exhaust connections before the health check detects it.
- **Risk:** No database backup automation exists in the Compose file or any discovered cron/script.

### Neo4j (Knowledge Graph)

**Role:** OMOP concept hierarchy, clinical ontology relationships, patient similarity graphs, semantic path traversal. Used by guideline RAG, calculator-KG integration, and OMOP hierarchy service.

**Engine:** `neo4j-driver` with connection pooling (max 50 connections, 30s timeout, 60s acquisition timeout).

**Assessment:**
- The `GraphDatabaseService` is well-architected with health checks, transaction management, read/write separation, and query metrics (count, avg latency).
- Mock mode fallback is comprehensive but dangerous: when Neo4j is unavailable, the service returns hardcoded clinical data (Type 2 diabetes, Metformin, etc.). In production, a clinical system returning mock medical data without clear signaling is a patient safety issue.
- The APOC plugin is loaded (`NEO4J_PLUGINS: '["apoc"]'`) -- required for advanced graph operations.
- **Risk:** Single Neo4j instance with no clustering. Neo4j Enterprise (or Aura) is required for causal clustering and HA.
- **Risk:** The credential mismatch noted above means Neo4j is likely running in mock mode in all current deployments.

### Redis (Cache + Job Queue)

**Role:** Three distinct workloads:
1. **RQ job queue** -- document processing and pipeline execution jobs
2. **Terminology cache** -- in-memory TTL cache for ICD-10, CPT, drug safety lookups
3. **KG query cache** -- multi-tier L1 (in-memory LRU) + L2 (Redis-backed) cache for graph queries
4. **Async operations** -- async Redis client for FastAPI endpoint caching

**Assessment:**
- Redis runs with AOF persistence (`--appendonly yes`) -- correct for job queue durability.
- Both sync and async Redis clients are available (`get_redis()` / `get_async_redis()`), properly initialized with thread-safe singletons.
- The `AsyncRedisCache` helper provides a clean namespaced caching API with TTL support.
- **Risk:** A single Redis instance serves both the job queue and cache workloads. A cache stampede (e.g., mass terminology cache expiry) could impact job processing latency.
- **Risk:** No Redis `maxmemory` policy configured. Under memory pressure, Redis will OOM-kill rather than evict cache entries.
- **Risk:** No Redis Sentinel or Cluster mode. Redis failure halts all background job processing.

### Polyglot Assessment

The three-database architecture (PostgreSQL + Neo4j + Redis) is architecturally justified:
- PostgreSQL for transactional OLTP and the OMOP CDM -- correct.
- Neo4j for hierarchical ontology traversal and graph analytics -- correct; relational databases are inefficient for multi-hop relationship queries.
- Redis for caching and job queue -- correct; in-memory speed for hot paths.

**The cost is operational complexity.** Three databases means three backup strategies, three monitoring configurations, three failure domains, and three upgrade cycles. This is manageable for a team with dedicated platform/SRE resources but burdensome for a small team.

---

## 3. Failure Mode Analysis

| Component | Failure Scenario | Current Behavior | Impact | Detection Time |
|---|---|---|---|---|
| PostgreSQL | Container crash | Docker restarts (unless-stopped); backend returns 503 on health check | **Total outage** -- all reads/writes fail, document processing stops | ~40s (healthcheck interval + start_period) |
| PostgreSQL | Disk full | Writes fail with pg error; health check may still pass (SELECT 1 succeeds) | **Silent data loss** -- new documents, facts, audit records rejected | **Undetected** until write failure propagates |
| PostgreSQL | Connection pool exhaustion | Health check detects "pool exhausted"; backend returns degraded | **Request failures** -- API returns 500s for any DB-dependent endpoint | ~30s (health check reports pool_status: critical) |
| Redis | Container crash | Docker restarts; RQ worker loses in-flight jobs; cache goes cold | **Job loss** -- in-flight document processing jobs lost; cold cache causes latency spike | ~10s (healthcheck interval) |
| Redis | OOM | Redis process killed; container restarts; all queued jobs and cache lost | **Job queue wipe** -- all pending jobs lost; system-wide latency spike | ~10s (healthcheck) |
| Neo4j | Container crash | GraphDatabaseService falls back to mock mode silently | **Silent degradation** -- graph queries return hardcoded data; clinical decisions based on fake data | ~30s (healthcheck), but **mock mode is not alarmed** |
| Neo4j | Slow queries | No query timeout configured; long-running Cypher queries block connection pool | **Connection starvation** -- other graph queries queue behind slow query | **Undetected** -- no query timeout or slow query log |
| Kafka | Broker crash | KafkaService falls to mock mode; mock message loop generates fake streaming data | **Silent degradation** -- streaming pipeline appears functional but processes no real data | ~30s (healthcheck), but mock mode is reported as "connected" |
| Kafka | Zookeeper crash | Kafka loses metadata; producer/consumer fail; KafkaService falls to mock | **Complete streaming outage** masked by mock mode | **Undetected** unless Kafka healthcheck catches it first |
| Backend | Process crash | Docker restarts; ~40s start_period before healthy | **API outage** for ~40-60 seconds during restart | Immediate (frontend gets connection refused) |
| Worker | Process crash inside alive container | No healthcheck to detect | **Silent job processing failure** -- jobs queue in Redis but never execute | **Undetected** -- no healthcheck or dead letter monitoring |
| Frontend | Build failure / runtime crash | No healthcheck to detect; Docker restart may loop | **UI outage** -- users see blank page or error | **Undetected** by infrastructure |

### The "Mock Mode" Problem

The most significant failure mode is what I call the **mock mode trap**. Both `GraphDatabaseService` and `KafkaService` silently fall back to generating fake data when their backing stores are unavailable. The health endpoints report these as "up" (with a `mock_mode: true` detail), but:

1. The overall health status reports "degraded" rather than "unhealthy" for Neo4j and Kafka failures (they are classified as `NON_CRITICAL_SERVICES`).
2. There is no external alerting on mock mode activation.
3. The Kafka mock mode reports `connected: True` in `get_health()` when mock mode is active -- this is misleading.
4. Clinical queries against the knowledge graph can silently return hardcoded diabetes/metformin data instead of real patient data.

**Recommendation:** In any environment beyond development, mock mode should either (a) fail closed (return errors), or (b) set a prominent flag that triggers an immediate PagerDuty/alert.

---

## 4. Scaling Strategy

### What Breaks First Under Load

**Tier 1 (breaks at ~100 concurrent users):**
1. **PostgreSQL connection pool.** Default asyncpg pool size + overflow will exhaust under sustained API load. The health check monitors pool status but there is no backpressure mechanism -- requests queue until timeout.
2. **Single RQ worker.** One worker process handles all document processing and pipeline jobs sequentially. At ~100 concurrent document uploads, the queue depth grows unbounded.

**Tier 2 (breaks at ~500 concurrent users):**
3. **Backend single instance.** One FastAPI process (even with uvicorn workers) will CPU-saturate on NLP extraction workloads. No horizontal scaling path exists in Compose.
4. **Redis single instance.** Mixed job queue + cache workload starts contending. Cache evictions cause terminology lookups to hit PostgreSQL directly, amplifying database load.

**Tier 3 (breaks at ~1000+ concurrent users):**
5. **Neo4j single instance.** Graph traversal queries are CPU-intensive. Multi-hop Cypher queries with no timeout can block the entire connection pool.
6. **Kafka single broker.** Single partition leadership means zero parallelism for consumers.

### Scaling Path

| Stage | Target | Actions |
|---|---|---|
| **Stage 1** (Immediate) | Handle 100 concurrent users reliably | Add PostgreSQL connection limits and statement timeouts; scale RQ workers to 3-5; add `maxmemory-policy allkeys-lru` to Redis |
| **Stage 2** (Next quarter) | Handle 500 concurrent users | Move to Kubernetes or ECS; run 3+ backend replicas behind load balancer; add PostgreSQL read replica; separate Redis instances for cache vs. job queue |
| **Stage 3** (6 months) | Handle 1000+ concurrent users | Neo4j causal cluster (3 nodes); Kafka multi-broker cluster; managed database services (RDS, ElastiCache, Neo4j Aura); CDN for frontend |

---

## 5. Observability Gaps

### What Exists (Strong Foundation)

| Capability | Implementation | Quality |
|---|---|---|
| Health endpoints | `/health`, `/health/live`, `/health/ready`, `/health/deep` | Production-grade. Parallel checks, proper HTTP status codes (503 for unhealthy), K8s probe compatibility |
| Connection pool monitoring | Pool size, checked in/out, overflow reported in health | Good -- detects pool exhaustion |
| Circuit breakers | `CircuitBreakerRegistry` with per-service breakers (Neo4j, Redis, embedding, external APIs) | Good -- state transitions are logged, metrics tracked |
| Request metrics middleware | `MetricsMiddleware` tracks request count, duration, active requests, error counts by endpoint | Good foundation |
| Prometheus metrics | `kg_prometheus_metrics.py` implements counter/gauge/histogram/summary types | Custom implementation -- not actual prometheus_client library |
| Distributed tracing | `kg_tracing_service.py` implements OpenTelemetry-compatible span model | Custom implementation -- not actual OpenTelemetry SDK |
| System metrics | Deep health check reports memory, disk, CPU, load average via psutil | Good for debugging |
| KG query metrics | GraphDatabaseService tracks total queries and average latency | Basic but useful |
| Cache statistics | Terminology cache reports hit/miss rates; KG cache has multi-tier stats | Good for cache tuning |

### What Is Missing (Critical Gaps)

1. **No centralized log aggregation.** All logging goes to stdout/stderr. No ELK, Datadog, or CloudWatch integration. When the system has an incident, engineers must `docker logs` into individual containers. This does not scale past 3 containers.

2. **No real Prometheus scraping.** The `kg_prometheus_metrics.py` is a custom implementation that reimplements Prometheus metric types in pure Python. It does not use the `prometheus_client` library and does not expose a `/metrics` endpoint in Prometheus exposition format. No Prometheus server is in the Compose stack. No Grafana dashboards consume this data.

3. **No real distributed tracing.** The `kg_tracing_service.py` implements an OpenTelemetry-compatible span model but does not integrate with the actual OpenTelemetry SDK, Jaeger, or Zipkin. Traces are stored in-memory only.

4. **No alerting pipeline.** There is no integration with PagerDuty, OpsGenie, or even email for critical failures. The circuit breaker state changes are logged but not alarmed.

5. **No request rate monitoring at the infrastructure level.** The MetricsMiddleware collects data but there is no dashboard, no anomaly detection, and no rate-based alerting.

6. **No database query logging or slow query detection.** PostgreSQL `log_min_duration_statement` is not configured. Neo4j has no query timeout. Slow queries degrade the system silently.

7. **No job queue depth monitoring.** RQ queue depth, processing latency, and failure rates are not tracked. A growing queue is a leading indicator of system stress.

8. **No disk space or volume monitoring.** Docker volumes grow unbounded. PostgreSQL WAL files, Neo4j transaction logs, and Kafka data directories can fill disks with no warning.

---

## 6. Disaster Recovery Readiness

### Current State: **Not Production-Ready**

| DR Capability | Status | Assessment |
|---|---|---|
| Database backups | **None** | No pg_dump, no WAL archiving, no point-in-time recovery. A PostgreSQL corruption event loses all data. |
| Neo4j backups | **None** | No `neo4j-admin dump` scheduled. Graph data is unrecoverable after a volume loss. |
| Redis persistence | **Partial** | AOF enabled, but no RDB snapshots. No backup export to external storage. |
| Kafka data retention | **Partial** | 7-day retention on most topics, 30-day on DLQ. But single-broker with replication factor 1 -- a disk failure loses all unconsumed messages. |
| Volume backup | **None** | All Docker volumes use the `local` driver. No snapshots, no replication, no off-host backup. |
| Configuration backup | **Partial** | Config is in code (git). But runtime state (database contents, graph data, credentials) is not in git. |
| RTO (Recovery Time Objective) | **Undefined** | No documented recovery procedure. Estimated RTO from scratch: 4-8 hours (rebuild containers, re-run migrations, reload OMOP vocabulary, rebuild graph). |
| RPO (Recovery Point Objective) | **Undefined** | No backup = RPO is "everything since the last manual export." For a healthcare platform, this is unacceptable. |
| Runbook | **None** | No documented incident response, failover, or recovery procedures. |

### Minimum DR Requirements for Healthcare

1. **Daily automated PostgreSQL backups** with 30-day retention, stored in a separate storage system (S3, GCS, or equivalent).
2. **Point-in-time recovery** capability via WAL archiving for PostgreSQL.
3. **Daily Neo4j dumps** to external storage.
4. **Redis RDB snapshots** in addition to AOF, exported to external storage.
5. **Documented and tested recovery runbook** with target RTO < 1 hour and RPO < 1 hour.

---

## 7. Configuration Management Assessment

### config.py Strengths

The `Settings` class in `config.py` demonstrates strong configuration discipline:
- **Pydantic-settings** with `.env` file support -- proper separation of config from code.
- **Insecure default detection:** Known-bad passwords (`_INSECURE_DEFAULTS`) are rejected by the field validator.
- **Production validation:** The `model_validator` enforces that `JWT_SECRET_KEY` and `API_KEY` are present when `environment=production`.
- **CORS origin validation:** Origins are validated as absolute URLs, rejecting wildcards or relative paths.
- **Credential masking:** Connection strings are masked in health check responses and logs.
- **Feature flags:** Ontology features (concept mapping, ontology edges, temporal extraction) can be toggled without deployment.

### config.py Risks

1. **Auth is disabled by default** (`auth_enabled: bool = False`). This means every development and staging deployment runs unauthenticated unless explicitly overridden. A deployment to a staging environment that forgets to set `AUTH_ENABLED=true` exposes the full API.
2. **Neo4j password is optional** (`neo4j_password: str | None = None`). The validator only warns, it does not fail. This means the application happily starts with no Neo4j credentials and silently runs in mock mode.
3. **ETL encryption key is ephemeral** (`etl_encryption_key: str | None = None`). The comment says "each restart generates new key" if not set. This means encrypted data source credentials become unreadable after a restart.
4. **Docker Compose hardcodes credentials** in plaintext (`POSTGRES_PASSWORD: postgres`, `NEO4J_AUTH: neo4j/password`, `API_KEY: dev-api-key-change-in-production`). These should use Compose secrets or an external secrets manager.

---

## 8. Resilience Patterns Assessment

### Circuit Breaker (Strong)

The `CircuitBreakerRegistry` is well-implemented:
- Three-state model (closed/open/half-open) with configurable thresholds.
- Per-service breakers: Neo4j (3 failures, 30s recovery), Redis (5 failures, 15s recovery), embedding (3 failures, 60s recovery), external APIs (5 failures, 45s recovery).
- Thread-safe with reentrant locks.
- Both sync and async decorators available.
- Metrics tracking (failure rate, rejection rate, consecutive failures/successes).

**Gap:** Circuit breakers exist but I found no evidence of them being wired into the core service singletons (`GraphDatabaseService`, `KafkaService`). The Neo4j circuit breaker is defined but the `execute_query` method does not use it.

### Graceful Degradation (Mixed)

- Redis ping failure is handled gracefully in health checks.
- Neo4j and Kafka mock mode provides availability but at the cost of correctness -- a dangerous tradeoff in healthcare.
- No bulkhead pattern -- a slow Neo4j query can consume all connections and impact unrelated PostgreSQL-only endpoints.

---

## 9. Infrastructure Roadmap to 99.9% Uptime

99.9% uptime = 8.76 hours of downtime per year. Current architecture cannot achieve this due to single points of failure in every data layer.

### Phase 1: Foundation (Weeks 1-4) -- Target 99.5%

1. Fix the Neo4j credential mismatch (immediate).
2. Add healthchecks to worker and frontend containers.
3. Add `depends_on` with `service_healthy` conditions for the backend container.
4. Configure PostgreSQL statement timeout (30s) and connection limits.
5. Configure Redis `maxmemory` and `maxmemory-policy allkeys-lru`.
6. Add daily PostgreSQL backup script (pg_dump to mounted volume).
7. Add daily Neo4j backup (neo4j-admin dump).
8. Replace mock mode with fail-closed behavior in non-development environments.

### Phase 2: Observability (Weeks 5-8) -- Target 99.7%

1. Add Prometheus (`prometheus_client` library) + Grafana to docker-compose.yml.
2. Integrate the existing MetricsMiddleware with real Prometheus counters.
3. Add Loki or ELK for centralized log aggregation.
4. Configure PostgreSQL `log_min_duration_statement: 1000` for slow query detection.
5. Add RQ queue depth monitoring and alerting.
6. Wire circuit breakers into GraphDatabaseService and KafkaService.
7. Create a basic on-call runbook for each failure scenario.

### Phase 3: Redundancy (Weeks 9-16) -- Target 99.9%

1. Migrate to Kubernetes (EKS/GKE) or ECS with proper orchestration.
2. PostgreSQL: Add streaming replication with a hot standby (or migrate to RDS).
3. Redis: Separate instances for cache and job queue; add Sentinel or migrate to ElastiCache.
4. Backend: Run 3+ replicas behind a load balancer with rolling deployments.
5. Worker: Scale to 3-5 RQ workers across multiple containers.
6. Add external backup storage (S3) with automated backup verification.
7. Implement blue-green or canary deployment strategy.

### Phase 4: Enterprise (Quarters 3-4) -- Target 99.95%+

1. Neo4j causal cluster (3 nodes) or migrate to Neo4j Aura.
2. Kafka multi-broker cluster (3 brokers) with proper replication.
3. Cross-region backup replication.
4. Automated failover testing (chaos engineering).
5. Full OpenTelemetry integration with distributed tracing.
6. SOC 2 / HITRUST operational evidence collection from monitoring.

---

## 10. Top 5 Infrastructure Priorities for Next Quarter

### Priority 1: Automated Database Backups + Recovery Runbook
**Effort:** 1-2 weeks | **Risk Reduction:** Critical

No backups exist for any data store. This is the highest-severity gap for a healthcare platform. A single disk corruption event, accidental migration error, or ransomware attack loses all clinical data irrecoverably.

- Daily pg_dump with 30-day retention to external storage.
- Daily Neo4j dump to external storage.
- Redis RDB snapshot to external storage.
- Documented and tested recovery procedure with target RTO < 1 hour.

### Priority 2: Fix Mock Mode Behavior for Production Environments
**Effort:** 1 week | **Risk Reduction:** High (patient safety)

The silent degradation to mock data is a clinical safety hazard. When Neo4j is unavailable, the knowledge graph API returns hardcoded clinical data (specific medications, conditions, and treatment relationships) that is not based on any real patient record.

- Environment-gated mock mode: only allow in `development` environment.
- Fail-closed in `staging` and `production`: return HTTP 503, not fake data.
- Alert on mock mode activation in any environment.
- Fix the Neo4j credential mismatch in docker-compose.yml.

### Priority 3: Centralized Logging + Alerting Pipeline
**Effort:** 2-3 weeks | **Risk Reduction:** High (incident response)

Without centralized logging, incident diagnosis requires SSH/docker-exec into individual containers. This is unacceptable for a multi-service system.

- Add Loki + Grafana (or ELK) to the infrastructure stack.
- Configure structured JSON logging in the backend.
- Create alerts for: health check failures, circuit breaker state changes, queue depth thresholds, disk space warnings, error rate spikes.
- Integrate with PagerDuty or OpsGenie for on-call escalation.

### Priority 4: Container Healthchecks + Dependency Ordering
**Effort:** 1 week | **Risk Reduction:** Medium

The worker and frontend containers have no healthchecks. The backend does not wait for its dependencies. These are simple fixes that improve cold-start reliability and reduce the "am I actually running?" uncertainty.

- Add healthchecks to worker (RQ process check) and frontend (HTTP check).
- Add `depends_on` with `service_healthy` for backend on postgres, redis.
- Add Neo4j healthcheck wait to backend startup.

### Priority 5: PostgreSQL + Redis Hardening
**Effort:** 1-2 weeks | **Risk Reduction:** Medium

Both PostgreSQL and Redis run with default configurations that will cause failures under load.

- PostgreSQL: Set `max_connections`, `statement_timeout`, `idle_in_transaction_session_timeout`. Configure connection pooling via PgBouncer if needed.
- Redis: Set `maxmemory`, `maxmemory-policy allkeys-lru`, configure `maxclients`. Add RDB snapshots alongside AOF.
- Separate Redis instances for cache and job queue workloads.

---

## Appendix: Service Dependency Graph

```
                    [Frontend :3000]
                         |
                    [Backend :8080]
                    /    |    \     \
            [PostgreSQL] [Redis] [Neo4j] [Kafka]
               :15432     :16379  :7687    :9092
                                            |
                                       [Zookeeper]
                                          :2181

            [Worker] ---> [Redis] ---> [PostgreSQL]
                                  \--> [Neo4j]
                                  \--> [Kafka]
```

---

## Appendix: Risk Heat Map

| Risk | Likelihood | Impact | Priority |
|---|---|---|---|
| Data loss (no backups) | Medium | **Critical** | **P0** |
| Mock data in production (Neo4j fallback) | High (credential mismatch makes this likely) | **Critical** (clinical safety) | **P0** |
| Silent worker failure | Medium | High (jobs stop processing) | P1 |
| PostgreSQL connection exhaustion | Medium (under load) | High (API outage) | P1 |
| Redis OOM | Low-Medium | High (job queue wipe) | P1 |
| Incident diagnosis delay (no centralized logs) | High | Medium (MTTR increase) | P1 |
| Neo4j slow query blocking | Low | Medium | P2 |
| Kafka data loss (replication=1) | Low | Medium | P2 |
| Disk space exhaustion | Low | High | P2 |
| Credential leak (hardcoded in Compose) | Low (internal access) | High | P2 |
