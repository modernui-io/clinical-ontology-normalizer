# Operations Review: SRE Readiness for Pilot Launch

**Date:** 2026-02-13  
**Scope:** Ramsey Health / Australia pilot, Meditech-to-OpenEHR focus  
**Mode:** Analysis-only (no code changes in this pass)

## Executive Verdict
**Controlled pilot-ready only** with explicit operational controls enabled.

The platform has promising observability and DR planning assets, but critical production resilience controls are incomplete for controlled clinical reliability.

## Current SLO Posture (Defined vs. Enforced)

| Domain | Target (recommended) | Evidence in code/docs | Enforcement status |
|---|---|---|---|
| Ingestion-to-KG freshness | P95 < 10 min for batch upload, P95 < 2 min for single-document | No explicit enforced end-to-end SLA in API; workflow exists in clinical endpoints | **Not enforced** |
| QA response latency | P95 < 2.5s for in-cache context, < 8s for cross-module path | `backend/app/api/clinical_agent.py` has no request budgeting | **Not enforced** |
| API error rate | P95 < 1% windowed, P99 < 3% | SLI middleware available but no alert thresholds in repo | **Not enforced** |
| Graph availability (knowledge graph routes) | >= 99.9% for pilot window | `backend/app/services/graph_database_service.py` can return mock mode as `mock_mode` and `health_check` reports `connected`-ish status | **Partially visible, not actionable** |
| Ingestion pipeline health | 100% critical ingestion queue uptime required for pilot | `backend/app/core/queue.py` provides multiple queues, but no enforced circuit-breaker behavior in docs or runbook | **Not enforced** |
## Findings Register

### OPS-1 — Readiness checks are dependency-agnostic and hide partial outage
**Severity:** P1  
**Likelihood:** High  
**Evidence:** `backend/app/api/health.py` readiness endpoint checks only `check_database` and sets `services_ready=1`.  
**Impact:** Kubernetes will mark pods ready during Neo4j/Kafka downtime even if critical product features are offline.  
**Recommendation:** Expand readiness contract for clinical pilot to include graph + queue readiness and explicit degraded-state labels.  
**Owner:** Operations + Platform  
**Pilot Impact:** **controlled go** with admission restrictions.

### OPS-2 — Mock-mode dependencies can appear green in health outputs
**Severity:** P1  
**Likelihood:** High  
**Evidence:** `backend/app/services/graph_database_service.py` and `backend/app/services/kafka_service.py` report mock-like states as operational in health results (`get_health` marks mock mode connected in both cases).  
**Impact:** Operators may not detect that production safety-critical dependencies are effectively offline.  
**Recommendation:** Split readiness into `up`, `degraded`, `mock`, `down` and alert on mock states.  
**Owner:** Engineering + SRE  
**Pilot Impact:** **hold** for risk-sensitive workflows until mock visibility is elevated.

### OPS-3 — Restart policy is not uniformly applied in `docker-compose.prod.yml`
**Severity:** P2  
**Likelihood:** High  
**Evidence:** only `nginx` has `restart: unless-stopped`; backend/redis/kafka/neo4j/workers lack restart policy.  
**Impact:** Service crashes may remain down until manual intervention, increasing recovery time and support burden.  
**Recommendation:** Add `restart: unless-stopped` across all services with explicit restart reason policy.  
**Owner:** Platform / SRE  
**Pilot Impact:** **controlled go**; avoid unattended outages.

### OPS-4 — Kafka cluster topology not HA for pilot production assumptions
**Severity:** P1  
**Likelihood:** High  
**Evidence:** `docker-compose.prod.yml` defines one Kafka broker, `KAFKA_BROKER_ID: 1`, `replication_factor: 1`, plus zookeeper single node.  
**Impact:** Broker or disk failure can halt streaming paths and event-driven pipelines.  
**Recommendation:** For pilot, run 3-broker baseline or document that Kafka path is optional/degraded at pilot scope.  
**Owner:** Platform / Architecture  
**Pilot Impact:** **hold** for strict uptime expectation.

### OPS-5 — Worker health check does not validate worker liveness
**Severity:** P2  
**Likelihood:** High  
**Evidence:** `docker-compose.prod.yml` sets worker health check to `curl http://localhost:8000/health` on worker container.  
**Impact:** Worker process-level failures can be masked, leaving queue buildup and silent task backlog.  
**Recommendation:** Replace with worker process check and queue-depth check in worker health endpoint.  
**Owner:** SRE + Platform  
**Pilot Impact:** **controlled go** but with strict manual monitoring.

### OPS-6 — No production-grade queue backpressure policy in the runbook
**Severity:** P2  
**Likelihood:** Medium  
**Evidence:** `backend/app/core/queue.py` supports queue names but there is no runbook-backed backpressure/circuit-breaker policy in repo docs.  
**Impact:** Ingestion spikes can saturate Redis/RQ and lose SLA for batch imports.  
**Recommendation:** Add queue depth thresholds and throttle policy:
- pause external intake at queue limit,
- switch to manual ingestion mode,
- escalate to ops immediately.  
**Owner:** SRE + CTO  
**Pilot Impact:** **controlled go**.

### OPS-7 — SLI exists but no external alerting wiring visible in operations runbook
**Severity:** P2  
**Likelihood:** Medium  
**Evidence:** `backend/app/api/middleware/sli_collector.py` exposes `/metrics/sli` and `/metrics/sli/summary`, plus `/api/v1/metrics`. No alert routing policies in `docs/operations/*.md`.  
**Impact:** You can measure but not escalate automatically; incidents stay manual.  
**Recommendation:** Add alert rules, thresholds, and paging mappings for critical endpoints:
- `hybrid_query` error spikes,
- `build-graph` queue delay,
- readiness degradation to mock/degraded.
**Owner:** Operations + SRE  
**Pilot Impact:** **controlled go** with manual watch required.

### OPS-8 — DR/BCP planning exists but runbook execution is not linked to code-version checks
**Severity:** P2  
**Likelihood:** Medium  
**Evidence:** `docs/operations/disaster_recovery_plan.md`, `docs/operations/business_continuity_plan.md` include strong scenarios, but no code-based checklist binding in runbook artifacts.  
**Impact:** Teams may pass docs review while drift exists in deployment state.  
**Recommendation:** Require signed pre-flight checklist tied to commit IDs for:
- backup restore test,
- DR drill logs,
- failover verification.
**Owner:** Ops + CIO Office  
**Pilot Impact:** **controlled go** only with monthly tabletop + one technical drill.

### OPS-9 — Security hardening recommendations remain unimplemented in compose defaults
**Severity:** P3  
**Likelihood:** Medium  
**Evidence:** `docs/operations/infrastructure_hardening.md` explicitly lists security/segmentation gaps and secret management as recommendations.  
**Impact:** Pilot still exposed to credential drift and secret leakage risk.  
**Recommendation:** Move to Docker/K8s secret model before external clinical onboarding.  
**Owner:** CISO + SRE  
**Pilot Impact:** **hold** for external production onboarding.

## Minimal Viable Operational Runbook

### Day 0 — Before Pilot Start
1. Validate `/api/v1/health` and `/api/v1/health/ready` return consistent states with dependency matrix.
2. Verify Kafka/Neo4j are not in mock mode during pilot window (`mock_mode=false`).
3. Run one ingestion-to-QA smoke path using synthetic pilot patient.
4. Confirm queue depth and worker count are stable before start.

### Day 7 — First Production Week
1. Review `/metrics/sli/summary` and `/api/v1/metrics` for p95 and error rates.
2. Confirm no manual fallback mode was triggered unexpectedly (especially `/clinical-agent/query/{patient_id}`).
3. Validate runbook escalation channel:
- Slack #incidents ack within 15 min,
- on-call response tree tested.

### Day 30 — Pilot Hardening
1. Introduce restart coverage + alerting rules for all core services.
2. Complete Kafka resilience review and queue depth gating.
3. Validate DR scenario 1 (`DB` and 2 (`worker restart` / `queue recovery`) in `docs/operations/disaster_recovery_plan.md`.

## Pilot Readiness Checklist

- [ ] Readiness checks include DB + KG + queue + model dependencies
- [ ] Service-dependency mock states are visible in dashboards and alarms
- [ ] Worker liveness uses process/queue checks, not API-only checks
- [ ] At least one manual/fake-fail drill completed and signed
- [ ] Alerting thresholds defined and staffed (P1 within 15m, P2 within 30m)
- [ ] OpenEHR/Meditech migration path has rollback decision and ownership

## 30/60/90-Day Operations Roadmap

### 0–30 Days
- Harden readiness/dependency gates and remove mock masking.
- Add restart policies in `docker-compose.prod.yml`.
- Implement basic alert pages and routing.

### 31–60 Days
- Add queue backpressure policy and worker-level health.
- Add SLO dashboards and paging integration for high-signal signals.
- Document and test one failover drill for one high-risk scenario.

### 61–90 Days
- Move to multi-broker Kafka or equivalent managed equivalent.
- Add synthetic canary tests for the top clinical paths.
- Tie DR plans to versioned release artifacts.

## Open Questions for SRE Leadership
- Is the pilot allowed to operate with known Kafka single-node limits, or is HA mandatory from day 1?
- What is the max acceptable ingestion lag before manual intake freeze?
- Which metrics must page directly to human responders versus chat-only alerts?
