# P4-004-D: Managed Graph Platform Migration Decision

**Decision ID:** P4-004-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** CTO + Ops
**Risk Owner:** CTO
**Evidence Owner:** Ops

## Context

The knowledge graph is currently backed by Neo4j Community Edition, running in mock mode for pilot (non-critical dependency per P0-001). Evidence from codebase:

- **Graph service:** `backend/app/services/graph_database_service.py` — connection management, Cypher execution, mock fallback
- **Connection config:** Single-instance bolt:// URI, max pool size 50, no clustering
- **Scalability audit (CTO-1):** Neo4j rated MEDIUM risk at `docs/architecture/scalability_audit.md`
  - Current: ~200 traversals/s (depth <=3), ~20% utilization
  - At 1M patients: ~80M nodes, ~200M edges
  - Community Edition: single-instance only, no clustering
- **Mock mode behavior:** Graph data reconstructable from `clinical_facts` in PostgreSQL
- **P0-001:** Neo4j unavailability now fails-closed in production readiness probe
- **P0-026-B:** Neo4j restore drill deferred (mock_mode)

### Current Neo4j Role in Architecture

Neo4j serves as a **projection layer** — all authoritative data lives in PostgreSQL. The KG is built from clinical facts and can be reconstructed. This architectural choice significantly reduces the HA requirements for the graph store.

## Decision

**Maintain Neo4j Community Edition for pilot; evaluate managed alternatives at 50K patient threshold.**

### Platform Comparison

| Platform | HA/Clustering | Managed Option | Cost (50K patients) | Migration Effort | Cypher Compatible |
|----------|--------------|----------------|---------------------|-----------------|-------------------|
| Neo4j Community | No clustering | No | $0 (self-hosted) | N/A (current) | Yes |
| Neo4j Enterprise | Causal clustering | Self-managed | ~$36K/year license | Low (same driver) | Yes |
| Neo4j Aura | Fully managed HA | Yes (DBaaS) | ~$800-2,000/month | Low (same driver) | Yes |
| Amazon Neptune | Multi-AZ HA | Yes (AWS managed) | ~$700-1,500/month | High (Gremlin/openCypher) | Partial (openCypher) |
| Azure Cosmos DB (Gremlin) | Global distribution | Yes (Azure managed) | ~$500-1,200/month | High (Gremlin API) | No |

### Recommended Migration Path

1. **Pilot (now-90 days):** Neo4j Community in mock/optional mode. Graph is reconstruction-safe from PostgreSQL.
2. **Post-pilot stability (90-180 days):** If graph query volume justifies, migrate to Neo4j Aura Professional for managed HA with zero Cypher migration cost.
3. **Scale threshold (50K+ patients):** Re-evaluate Neptune if AWS is primary cloud AND Cypher compatibility improves, or stay on Aura.

### Why NOT Migrate Now

1. Graph is non-critical (projection layer, reconstructable)
2. Current utilization is 20% — no capacity pressure
3. Mock mode is acceptable for pilot (P0-001 ensures fail-closed behavior)
4. Migration effort diverts from P0/P1 closure and staging provisioning

### Why Neo4j Aura Over Neptune (When Ready)

1. Zero Cypher migration — all existing queries work unchanged
2. `graph_database_service.py` driver (`neo4j-driver`) is compatible
3. Managed backup, monitoring, and scaling
4. Lower operational burden than self-hosted Enterprise

## Consequences

- No graph platform migration during pilot
- Neo4j Community remains in deployment stack with mock fallback
- Aura migration planned for post-pilot if graph query demand materializes
- Neptune evaluation deferred unless AWS mandate from infrastructure team
- `graph_database_service.py` connection config should be parameterized for easy Aura cutover (URI + auth change only)

## Evidence Paths

- Graph service: `backend/app/services/graph_database_service.py`
- Scalability audit: `docs/architecture/scalability_audit.md` (Neo4j section)
- Mock mode behavior: `ConnectionStatus.MOCK_MODE` in graph service
- P0-001 fail-closed: `backend/app/api/health.py` `check_neo4j()`
- K8s topology: `k8s/` (no Neo4j StatefulSet — only PG and Redis)
- This decision: `docs/decisions/p4-004-graph-platform.md`
