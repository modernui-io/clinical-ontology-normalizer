# P4-005-D: Multi-Region Architecture Decision

**Decision ID:** P4-005-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** CTO + CISO
**Risk Owner:** CISO
**Evidence Owner:** CTO

## Context

The Ramsey Health Australia pilot has data residency requirements under the Privacy Act 1988 (Cth) and Australian Privacy Principles (APPs). Current deployment topology:

- **K8s manifests:** `k8s/` with overlays for dev, staging, prod (`k8s/overlays/`)
- **Database:** PostgreSQL StatefulSet (`k8s/postgres/statefulset.yaml`)
- **Redis:** Single-instance deployment (`k8s/redis/deployment.yaml`)
- **Ingress:** Single ingress controller (`k8s/ingress.yaml`)
- **Network policies:** Namespace-level isolation (`k8s/network-policies.yaml`)
- **No multi-region configuration** exists in current K8s manifests
- **Scalability audit:** PostgreSQL rated HIGH risk for horizontal scaling (CTO-1)

### Data Residency Constraints (AU)

1. PHI must remain within Australian jurisdiction (or approved jurisdictions with adequate protection)
2. Australian Privacy Principle 8 (APP 8): cross-border disclosure requires consent or adequate protections
3. Ramsey Health likely requires AU-only data residency for initial pilot

### Current Single-Region Risks

- Single point of failure for entire application stack
- No geographic redundancy for disaster recovery
- Latency from non-AU regions (if deployed outside AU)

## Decision

**Single-region AU deployment for pilot. Design for active-passive failover at scale.**

### Architecture Decision

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Pilot topology | Single-region (ap-southeast-2 Sydney) | Simplest, meets data residency, sufficient for pilot scale |
| DR strategy | Cross-AZ within ap-southeast-2 | Multi-AZ provides 99.99% availability without cross-border complexity |
| Data residency boundary | AU-only (Sydney + Melbourne AZs) | Meets APP 8 without cross-border consent requirements |
| Future multi-region | Active-passive to ap-southeast-4 (Melbourne) when demand justifies | Same jurisdiction, adds geo-redundancy without data residency issues |
| Latency budget | <200ms p95 for clinical queries from AU | Single-region easily meets this |

### Active-Passive Design (When Activated)

```
Primary: ap-southeast-2 (Sydney)
  ├── PostgreSQL primary (read-write)
  ├── Redis primary
  ├── Application pods (active)
  └── Neo4j (if non-mock)

Secondary: ap-southeast-4 (Melbourne)
  ├── PostgreSQL replica (read-only, async replication)
  ├── Redis replica
  ├── Application pods (standby, read-only traffic)
  └── Neo4j replica (if applicable)

DNS: Route 53 health-check failover
RTO target: <15 minutes
RPO target: <5 minutes (async replication lag)
```

### Why NOT Active-Active

1. PostgreSQL write conflict resolution adds complexity without proportional benefit at pilot scale
2. Active-active requires distributed transaction coordination (Citus or similar)
3. Clinical data consistency is paramount — eventual consistency is unacceptable for clinical facts
4. Cost doubles without clear demand signal

### Why NOT Multi-Country

1. AU data residency requirements are strict (APP 8)
2. No non-AU customer demand exists yet
3. Cross-border data transfer requires legal framework (Standard Contractual Clauses or equivalent)
4. Adds 6+ months of compliance work for zero pilot value

## Consequences

- Deploy exclusively in ap-southeast-2 for pilot
- K8s manifests remain single-cluster with multi-AZ node affinity
- Add cross-AZ PostgreSQL replica as P2/P3 operational hardening item
- Multi-region activation gated on: (a) second AU customer, OR (b) non-AU customer with data residency solution
- No infrastructure changes required for pilot launch

## Evidence Paths

- K8s deployment: `k8s/backend/deployment.yaml`, `k8s/postgres/statefulset.yaml`
- K8s overlays: `k8s/overlays/dev/`, `k8s/overlays/staging/`, `k8s/overlays/prod/`
- Network policies: `k8s/network-policies.yaml`
- Scalability audit: `docs/architecture/scalability_audit.md`
- SOC 2 compliance: `docs/compliance/soc2_gap_analysis.md`
- This decision: `docs/decisions/p4-005-multi-region.md`
