# P4-014-D: Data Mesh Architecture Decision

**Decision ID:** P4-014-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** CTO + Data
**Risk Owner:** CTO
**Evidence Owner:** Data

## Context

Current data architecture:

- **Monolithic PostgreSQL** as primary data store (all domains in single database)
- **Data pipeline plan** exists at `docs/PLAN-data-pipeline.md` (scaffold) with: frontend components (Data Sources, Pipelines Builder, Job Monitor, Quality Dashboard), backend orchestrator, multi-source connectors (FHIR, HIE/Direct, C-CDA, HL7v2)
- **Data quality service:** `backend/app/services/data_quality_service.py` (1,400 lines, production maturity)
- **Data lineage:** P2-022 closed (structured lineage fields end-to-end)
- **Scalability audit (CTO-1):** PostgreSQL rated HIGH risk at 1M patients (~100M rows in clinical_facts)

**Data mesh principles:** Domain-oriented ownership, data-as-a-product, self-serve data infrastructure, federated computational governance.

## Decision

**Data mesh is premature. Maintain monolithic data architecture with domain boundaries in code.**

### Quantified Complexity Cost vs. Benefit

| Factor | Monolithic (Current) | Data Mesh | Delta |
|--------|---------------------|-----------|-------|
| Operational overhead | 1 database, 1 backup, 1 monitoring | N databases (per domain), N backups, N monitors | +300-500% ops burden |
| Cross-domain queries | Single JOIN | Cross-service API calls or materialized views | +200-500ms latency |
| Team size required | 2-3 engineers | 1 per domain (minimum 5-7) | +150% headcount |
| Data consistency | ACID (single DB) | Eventually consistent (distributed) | Reduced safety guarantee |
| Time to implement | N/A (current) | 6-12 months | High opportunity cost |

### Current Scale Assessment

- Patient count: <10K (pilot)
- clinical_facts: ~594 rows (current), ~100 rows per patient at scale
- Data domains identified: Clinical, Interop, Analytics, Admin
- Team size: <5 engineers

**Verdict:** At <10K patients and <5 engineers, data mesh complexity vastly exceeds benefit. The operational overhead alone (N monitoring pipelines, N backup strategies, cross-service consistency) would consume more engineering capacity than the entire current team.

### What to Do Instead

1. **Domain boundaries in code:** Use schema prefixes or namespace conventions in PostgreSQL
2. **Data contracts:** Define per-domain API contracts (already started via P1-030 integration checklist)
3. **Quality SLOs:** Per-domain data quality targets via existing `data_quality_service.py`
4. **Revisit trigger:** When team exceeds 10 engineers AND patient count exceeds 100K AND cross-domain query conflicts become measurable bottleneck

### If Activated (Pilot One Domain)

Recommended pilot domain: **Analytics/Reporting** (least safety-critical, most self-contained)
- Separate reporting database (read replica or ETL target)
- Self-serve query interface for operations team
- SLO: <1 hour data freshness, >99.5% query availability
- Success metric: Operations team can answer reporting questions without engineering support

## Consequences

- No data mesh during pilot or first year of production
- PostgreSQL remains single source of truth for all domains
- Domain boundaries enforced at code/schema level, not infrastructure level
- Data quality service applies uniformly across all domains
- Re-evaluation at 100K patients or 10+ engineer team size

## Evidence Paths

- Data pipeline plan: `docs/PLAN-data-pipeline.md`
- Data quality service: `backend/app/services/data_quality_service.py`
- Scalability audit: `docs/architecture/scalability_audit.md`
- Data lineage: P2-022 (closed)
- Integration checklist: P1-030 (closed)
- This decision: `docs/decisions/p4-014-data-mesh.md`
