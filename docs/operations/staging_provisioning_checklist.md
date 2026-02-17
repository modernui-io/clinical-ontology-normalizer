# Staging Provisioning Checklist

**Document ID**: OPS-STAGING-001
**Version**: 1.0
**Effective Date**: 2026-02-17
**Owner**: CTO + CIO + Ops Lead
**Classification**: Internal — Operational
**Linked Blockers**: P0-028 conditions 1-5, Execution Board staging blockers

## Purpose

Define the complete checklist for provisioning, configuring, and validating a staging environment that can clear the 5 remaining infrastructure-blocked conditions from the P0-028 signoff. Staging sign-off is required before broad rollout; pilot on localhost remains CONDITIONAL GO.

## Escalation Timeline

| Date | Action | Owner |
|------|--------|-------|
| 2026-03-02 | Staging infra escalation if not provisioned | CTO + CIO |
| 2026-03-09 | Executive sponsor escalation if no CTO/CIO resolution | Program Lead |
| 2026-03-16 | Signoff expiry — re-signoff required from all 6 roles | All role leads |
| 2026-03-17 | 30-day closure review | Program Lead |

---

## Phase 1: Infrastructure Provisioning

### 1.1 Compute and Networking

- [ ] Provision staging host(s) — minimum spec: 8 vCPU, 32 GB RAM, 200 GB SSD (encrypted volume)
- [ ] Assign staging DNS: `staging.con.internal` (or equivalent)
- [ ] Configure network security group / firewall rules:
  - [ ] Internal-only access (no public ingress)
  - [ ] Port 443 (HTTPS via nginx)
  - [ ] Port 5432 (PostgreSQL — internal only, `data-net` equivalent)
  - [ ] Port 6379 (Redis — internal only, `queue-net` equivalent)
  - [ ] Port 7474/7687 (Neo4j HTTP/Bolt — internal only)
  - [ ] Port 9092 (Kafka — internal only)
  - [ ] Port 2181 (Zookeeper — internal only)
- [ ] Verify full-disk encryption enabled on host OS (LUKS / dm-crypt / cloud encrypted volumes)
- [ ] Confirm host is in `ap-southeast-2` (Sydney) per P4-005 single-region decision

### 1.2 Docker / Container Runtime

- [ ] Install Docker Engine 24+ with Compose V2
- [ ] Verify `docker compose version` reports v2.x
- [ ] Pull required images:
  - [ ] `postgres:16-alpine`
  - [ ] `redis:7-alpine`
  - [ ] `neo4j:5`
  - [ ] `confluentinc/cp-zookeeper:7.5.0`
  - [ ] `confluentinc/cp-kafka:7.5.0`
  - [ ] `nginx:alpine`
- [ ] Build backend and frontend production images using `Dockerfile.prod`

### 1.3 TLS Certificates

- [ ] Generate or obtain TLS certificate for `staging.con.internal`
- [ ] Place cert + key in `nginx/ssl/` (referenced by `docker-compose.prod.yml`)
- [ ] Verify nginx config references correct cert paths
- [ ] Confirm TLS termination on port 443 (P0-013 requirement)

---

## Phase 2: Secrets and Configuration

### 2.1 Environment Variables (.env for staging)

Create a staging `.env` file with all required secrets. **No placeholder or default credentials** (P0-010 enforcement).

| Variable | Requirement | Notes |
|----------|-------------|-------|
| `POSTGRES_PASSWORD` | Required, strong (32+ chars) | Used by PG + backend + worker |
| `POSTGRES_USER` | Required | Default `postgres` acceptable |
| `POSTGRES_DB` | Required | `clinical_ontology` |
| `REDIS_PASSWORD` | Required, strong (32+ chars) | P0-011 enforced in prod compose |
| `NEO4J_USER` | Required | Default `neo4j` acceptable |
| `NEO4J_PASSWORD` | Required, strong (32+ chars) | |
| `API_KEY` | Required | Backend API auth key |
| `CON_API_KEYS` | Optional | Additional consumer keys |
| `ANTHROPIC_API_KEY` | Required if LLM enabled | For clinical agent Q&A |
| `LLM_PROVIDER` | `anthropic` | |
| `LLM_MODEL` | `claude-opus-4-5-20251101` | Or current approved model |
| `AUTH_ENABLED` | `true` | P0-009 — must be true in staging |
| `DEBUG` | `false` | |
| `USE_DB_VOCABULARY` | `true` | Production OMOP vocabulary |
| `NEXT_PUBLIC_API_URL` | `https://staging.con.internal/api` | Frontend → backend |

- [ ] `.env` created with all required variables set
- [ ] No placeholder or default passwords present
- [ ] File permissions restricted (`chmod 600 .env`)
- [ ] `.env` NOT committed to git (verify `.gitignore`)

### 2.2 Configuration Validation

- [ ] Run backend startup validation (P1-020): confirm startup fails if any required credential missing
- [ ] Verify `AUTH_ENABLED=true` is enforced (P0-009): service refuses startup if auth disabled
- [ ] Verify `required_services` config includes `postgresql`, `redis` (P0-003)
- [ ] Verify mock_mode is NOT treated as healthy in staging (P0-003): `_is_production_like()` returns `True`

---

## Phase 3: Service Deployment

### 3.1 Launch Sequence

Deploy using production compose overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Startup order (enforced by `depends_on`):**
1. PostgreSQL → healthy
2. Redis → healthy
3. Zookeeper → healthy
4. Kafka → healthy (depends on Zookeeper)
5. Neo4j → healthy
6. Backend (2 replicas) → healthy
7. Worker (2 replicas) → healthy
8. Frontend (2 replicas) → healthy
9. Nginx → healthy

### 3.2 Post-Launch Health Verification

- [ ] `GET /health` returns 200 with all dependencies UP
- [ ] `GET /api/v1/health/ready` returns 200 (readiness probe)
- [ ] PostgreSQL: `pg_isready` passes, row counts visible
- [ ] Redis: `redis-cli ping` returns PONG (with auth)
- [ ] Neo4j: `http://neo4j:7474` responds (NOT mock_mode)
- [ ] Kafka: `kafka-broker-api-versions` returns broker info
- [ ] Zookeeper: `nc -z localhost 2181` succeeds
- [ ] Worker healthcheck: `check_worker_health()` returns healthy
- [ ] Frontend: `wget --spider http://localhost:3000/` returns 200
- [ ] Nginx: `https://staging.con.internal/health` returns 200

### 3.3 Database Initialization

- [ ] Run migrations: `docker compose run --rm --profile migrate migrations`
- [ ] Verify schema version matches HEAD alembic revision
- [ ] Load OMOP vocabulary if `USE_DB_VOCABULARY=true`
- [ ] Seed test data for drill scenarios (5 representative Meditech encounters)

---

## Phase 4: Staging Drill Execution (5 Conditions)

These are the 5 remaining conditions from P0-028 signoff. Each must produce evidence artifacts.

### 4.1 Condition 1: OpenEHR Round-Trip Staging Confirmation

**Owner**: CIO + Ops
**Acceptance**: 5/5 mixed-domain dry-runs PASS + 5/5 round-trip + rollback PASS on staging
**Reference**: Localhost evidence at `docs/evidence/p0-019/`

**Procedure:**
1. [ ] Run 5 dry-run scenarios via `POST /api/v1/openehr/dry-run`:
   - `mixed_all`, `labs_only`, `medications_heavy`, `procedures_vitals`, `allergies_conditions`
2. [ ] Verify all 5 return `success: true` with expected counts
3. [ ] Verify no rows persisted after dry-runs (savepoint rollback)
4. [ ] Run 5 real imports via `POST /api/v1/openehr/import`
5. [ ] Run reconciliation: `POST /api/v1/openehr/reconcile/{patient_id}` for each
6. [ ] Execute rollback: `POST /api/v1/openehr/rollback/{patient_id}` for each
7. [ ] Verify row counts return to pre-import baseline
8. [ ] Record evidence to `docs/evidence/staging/openehr-roundtrip-staging-evidence.json`

**Pass criteria (match localhost baseline):**
- 5/5 dry-runs PASS, 5/5 round-trips PASS, 5/5 rollbacks PASS
- Duration per scenario: < 5s (localhost was 0.066s for dry-run)
- Zero orphaned rows after rollback

### 4.2 Condition 2: Redis Containerized Failover Drill

**Owner**: Ops + CTO
**Acceptance**: MTTR < 60s, zero data loss, degraded banner visible
**Reference**: Redis was native on localhost — could not be Docker-paused

**Procedure:**
1. [ ] Record baseline: Redis PING, queue depth, worker health status
2. [ ] Induce outage: `docker pause <redis-container-id>`
3. [ ] Record detect time: when health probe reports Redis DOWN
4. [ ] Verify clinical queries blocked/degraded (readiness probe non-200)
5. [ ] Verify frontend degraded banner displayed
6. [ ] Recover: `docker unpause <redis-container-id>`
7. [ ] Record recovery time: when health returns Redis UP
8. [ ] Verify queue recovery: jobs resume, no duplicate processing
9. [ ] Verify data integrity: no job loss or corruption
10. [ ] Record evidence to `docs/evidence/staging/redis-failover-staging-evidence.md`

**Pass criteria:**
- MTTR < 60s (target)
- Degraded banner displayed during outage
- Clinical paths blocked while Redis unavailable
- Zero job loss post-recovery
- Queue depth returns to pre-outage level

### 4.3 Condition 3: Neo4j Restore Drill

**Owner**: Ops
**Acceptance**: Backup + restore completes with node/edge count match, RTO < 120s
**Reference**: Deferred from P0-026 (was running mock_mode on localhost)

**Procedure:**
1. [ ] Seed Neo4j with test KG data: import patients → build KG → record node/edge counts
2. [ ] Record baseline counts:
   - Node count: `MATCH (n) RETURN count(n)`
   - Edge count: `MATCH ()-[r]->() RETURN count(r)`
3. [ ] Execute backup: `neo4j-admin database dump neo4j --to-path=/backups/`
4. [ ] Drop and recreate database (simulate data loss)
5. [ ] Execute restore: `neo4j-admin database load neo4j --from-path=/backups/ --overwrite-destination`
6. [ ] Verify post-restore counts match baseline (exact match required)
7. [ ] Verify Neo4j healthcheck passes: `http://neo4j:7474` responds
8. [ ] Verify backend reconnects to Neo4j and graph queries return expected results
9. [ ] Record evidence to `docs/evidence/staging/neo4j-restore-staging-evidence.md`

**Pass criteria:**
- RTO < 120s (target, non-critical dependency)
- Node count exact match pre/post
- Edge count exact match pre/post
- Backend graph queries functional after restore
- Health probe reports Neo4j UP

### 4.4 Condition 4: Cascade Failover Simulation

**Owner**: Ops + CTO
**Acceptance**: MTTR < 300s for full cascade, zero data loss, all safety controls activate
**Reference**: Deferred from P0-027 (required all deps containerized)

**Procedure:**
1. [ ] Record baseline health: all deps UP, row counts, queue depths
2. [ ] **Stage 1 — Single dependency (PostgreSQL):**
   - [ ] `docker pause <postgres-container>`
   - [ ] Verify readiness probe fails within 10s
   - [ ] Verify clinical queries return error/degraded (not stale data)
   - [ ] Verify degraded banner renders
   - [ ] `docker unpause <postgres-container>`
   - [ ] Verify recovery within 60s
   - [ ] Verify data integrity (row counts match)
3. [ ] **Stage 2 — Dual dependency (PostgreSQL + Redis):**
   - [ ] `docker pause <postgres-container> <redis-container>`
   - [ ] Verify full service outage (backend cannot serve any clinical requests)
   - [ ] Verify worker health fails
   - [ ] `docker unpause <postgres-container> <redis-container>`
   - [ ] Verify recovery: backend healthy, workers resume, queue backlog cleared
   - [ ] Verify data integrity
4. [ ] **Stage 3 — Triple dependency (PostgreSQL + Redis + Neo4j):**
   - [ ] `docker pause <postgres-container> <redis-container> <neo4j-container>`
   - [ ] Verify total system outage
   - [ ] `docker unpause` all three
   - [ ] Verify cascaded recovery in correct order
   - [ ] Verify data integrity across all stores
5. [ ] **Stage 4 — Full cascade (all deps + Kafka):**
   - [ ] `docker pause <postgres> <redis> <neo4j> <kafka> <zookeeper>`
   - [ ] Record total outage state
   - [ ] `docker unpause` all containers
   - [ ] Verify full recovery: health green, queue processing resumes, graph queries work
   - [ ] Verify zero data loss across all stores
6. [ ] Record evidence to `docs/evidence/staging/cascade-failover-staging-evidence.md`

**Pass criteria per stage:**

| Stage | MTTR Target | Data Loss | Safety Controls |
|-------|-------------|-----------|-----------------|
| Single (PG) | < 60s | Zero | Readiness fails, banner shows |
| Dual (PG+Redis) | < 120s | Zero | Full outage, workers fail |
| Triple (PG+Redis+Neo4j) | < 180s | Zero | Total clinical block |
| Full cascade | < 300s | Zero | Total outage, cascaded recovery |

### 4.5 Condition 5: 30-Day Signoff Review Preparation

**Owner**: Program Lead + all 6 role leads
**Acceptance**: Updated signoff matrix with staging evidence, new expiry date
**Scheduled**: 2026-03-16 (or when staging drills 1-4 complete, whichever comes first)

**Procedure:**
1. [ ] Collect evidence from drills 4.1-4.4
2. [ ] Update `docs/evidence/p0-028/p0-028-signoff-template.md`:
   - [ ] Replace "CONDITIONAL GO" conditions with staging PASS evidence
   - [ ] Update residual risks (remove staging blockers, add any new findings)
   - [ ] Set new expiry date (30 days from re-signoff)
3. [ ] Re-collect signatures from all 6 roles:
   - [ ] CTO: Confirm fail-closed behavior on staging
   - [ ] CISO: Confirm encryption-at-rest on staging volumes + Neo4j verified
   - [ ] CIO: Confirm OpenEHR round-trip on staging
   - [ ] Clinical AI Lead: Confirm clinical safety controls active on staging
   - [ ] Product VP: Confirm degraded UX and confidence gating on staging
   - [ ] Ops Lead: Confirm all drills pass on staging with MTTR/RTO within targets
4. [ ] Update execution board posture: `blocked_by_infrastructure` → staging result
5. [ ] Update go/no-go table (Dimension 6: Infra Readiness) from HOLD → result
6. [ ] Record evidence to `docs/evidence/staging/signoff-review-staging-evidence.md`

---

## Phase 5: Post-Staging Validation

### 5.1 Smoke Test Suite

Run after all drills complete to confirm system is stable:

- [ ] Full health endpoint green: `GET /health` all deps UP
- [ ] OpenEHR import + export round-trip (1 patient, all 5 domains)
- [ ] Clinical agent query with confidence policy enforcement
- [ ] Degraded banner toggle (pause/unpause one dep, verify banner)
- [ ] Audit log captures all clinical operations
- [ ] Worker processes queued job within 30s
- [ ] Frontend renders all pilot routes without console errors

### 5.2 Evidence File Checklist

All staging drill evidence must be captured before signoff update:

| Evidence File | Source Drill | Status |
|--------------|-------------|--------|
| `docs/evidence/staging/openehr-roundtrip-staging-evidence.json` | Condition 1 | [ ] |
| `docs/evidence/staging/redis-failover-staging-evidence.md` | Condition 2 | [ ] |
| `docs/evidence/staging/neo4j-restore-staging-evidence.md` | Condition 3 | [ ] |
| `docs/evidence/staging/cascade-failover-staging-evidence.md` | Condition 4 | [ ] |
| `docs/evidence/staging/signoff-review-staging-evidence.md` | Condition 5 | [ ] |

### 5.3 Board Updates After Completion

- [ ] `tasks/08_autonomous_execution_board.md`: Update staging blockers table (blocked → PASS/FAIL)
- [ ] `tasks/09_master_change_backlog_p0_p4.md`: Add staging evidence references
- [ ] `tasks/04_enterprise_readiness_multi_agent_playbook_run.md`: Append staging closure log entry
- [ ] `docs/evidence/p2-009/p2-009-go-no-go-table.md`: Update Dimension 6 from HOLD → result

---

## Resource Requirements Summary

| Resource | Minimum Spec | Notes |
|----------|-------------|-------|
| Compute | 8 vCPU, 32 GB RAM | Hosts all containers including 2x backend + 2x worker replicas |
| Storage | 200 GB SSD (encrypted) | PG data, Neo4j data, Kafka logs, Redis AOF |
| Network | Internal only, TLS ingress | No public-facing endpoints |
| Region | ap-southeast-2 (Sydney) | Per P4-005 single-region decision |
| Docker | Engine 24+, Compose V2 | Production overlay: `docker-compose.prod.yml` |
| TLS | Valid cert for staging domain | Self-signed acceptable for staging |
| Secrets | 4 strong passwords + API key | PG, Redis, Neo4j, API key (no defaults) |
| Test data | 5 Meditech encounters + KG seed | For drill scenarios |

## Estimated Drill Duration

| Drill | Estimated Duration | Dependencies |
|-------|-------------------|-------------|
| OpenEHR round-trip | 30 minutes | PG + backend running |
| Redis failover | 15 minutes | Redis containerized |
| Neo4j restore | 30 minutes | Neo4j with seeded data |
| Cascade simulation | 45 minutes | All deps containerized |
| Signoff review | 60 minutes | All drills complete |
| **Total** | **~3 hours** | Sequential execution |

---

*Generated: 2026-02-17 | Reference: P0-028 signoff conditions, P2-009 go/no-go table, execution board staging blockers*
