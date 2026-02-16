# Failover and Dependency Outage Simulation

**Document ID**: OPS-P0-027
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Operations + CTO
**Classification**: Internal — Operational

## Purpose

Define the procedure for simulating dependency outages, measuring Mean Time To Recovery (MTTR), and verifying graceful degradation behavior. Execute at least once before pilot go-live.

## Dependencies Under Test

| Dependency | Failure Mode | Expected Behavior | Health Endpoint |
|---|---|---|---|
| PostgreSQL | Connection refused | API returns 503, readiness non-ready | `/health/ready` |
| Redis | Connection timeout | Queue operations fail, workers pause | `/health/ready` |
| Neo4j | Unavailable | KG queries degraded, clinical agent returns partial | `/health/ready` |
| Kafka | Broker down | Async jobs queue locally, backpressure active | `/health/ready` |
| External LLM | API timeout | Fallback to rule-based, degraded flag set | `/health/dependencies` |

## Simulation Procedures

### Simulation 1: PostgreSQL Outage

**Setup**:
```bash
# Block PostgreSQL port (staging only)
sudo iptables -A INPUT -p tcp --dport 5432 -j DROP
```

**Verify**:
1. `/health/ready` returns non-ready within 30 seconds
2. API endpoints return 503 Service Unavailable
3. Frontend shows degraded mode banner
4. No data corruption after recovery

**Recovery**:
```bash
sudo iptables -D INPUT -p tcp --dport 5432 -j DROP
```

**Record**: Time from outage to detection, time from recovery to healthy.

### Simulation 2: Redis Outage

**Setup**:
```bash
# Stop Redis
docker stop sulci-redis
```

**Verify**:
1. Job queue operations fail gracefully (no silent drops)
2. Backpressure policy activates
3. Health check reflects Redis unavailable
4. After restart, queued jobs resume

**Recovery**:
```bash
docker start sulci-redis
```

### Simulation 3: Neo4j Unavailable

**Setup**:
```bash
docker stop sulci-neo4j
```

**Verify**:
1. Clinical agent returns degraded responses with `fallback_used: true`
2. KG-dependent queries return partial results with coverage warning
3. Document ingestion continues (KG build queued)
4. Health check shows KG as unavailable

**Recovery**:
```bash
docker start sulci-neo4j
```

### Simulation 4: External LLM Timeout

**Setup**:
```bash
# Set LLM provider to unreachable endpoint
export LLM_BASE_URL=https://10.255.255.1/timeout
# Restart clinical agent service
```

**Verify**:
1. Clinical agent falls back to rule-based extraction
2. Responses include `model_route: "rule_based_fallback"`
3. Confidence scores reflect reduced capability
4. No PHI sent to unreachable endpoint

### Simulation 5: Full Cascade (PostgreSQL + Redis)

**Setup**: Bring down both PostgreSQL and Redis simultaneously.

**Verify**:
1. Service enters full degraded mode
2. No data loss during outage window
3. Recovery is automatic upon dependency restoration
4. Data consistency verified post-recovery

## MTTR Recording Template

| Simulation | Outage Start | Detection Time | Recovery Start | Full Recovery | MTTR | Status |
|---|---|---|---|---|---|---|
| PostgreSQL | | | | | | |
| Redis | | | | | | |
| Neo4j | | | | | | |
| External LLM | | | | | | |
| Full Cascade | | | | | | |

## Acceptance Criteria

- [ ] All simulations executed
- [ ] MTTR < 15 minutes for all single-dependency failures
- [ ] MTTR < 30 minutes for cascade failures
- [ ] No data loss or corruption in any scenario
- [ ] Health endpoints correctly reflect degraded state
- [ ] Frontend degraded banner appears within 30 seconds
- [ ] Recovery is automatic (no manual intervention required)

## Evidence Record

| Field | Value |
|---|---|
| Drill Date | |
| Operator | |
| Environment | staging / DR |
| All Simulations Passed | YES / NO |
| Max MTTR Observed | |
| Issues Found | |
| Corrective Actions | |
| Approved By | |

## Schedule

- Pre-pilot: Full simulation suite
- Monthly during pilot: Rotate through one simulation per week
- Quarterly post-pilot: Full suite with cascade
