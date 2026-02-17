# P4-014-I: Data Mesh Pilot Design

**Task:** P4-014-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Governance plan complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-014-data-mesh.md`

## Summary

This document codifies the pilot design for transitioning from monolithic data architecture to domain-oriented data mesh. Activation is gated on 100K patients OR 10+ engineers AND measurable cross-domain bottleneck, as defined in P4-014-D. Current architecture (monolithic PostgreSQL with domain boundaries in code) is sufficient for pilot and first year of production.

## Current State Assessment

| Component | File | Lines | Maturity |
|-----------|------|-------|----------|
| Data Quality Service | `backend/app/services/data_quality_service.py` | 1,400 | Production |
| Data Pipeline Plan | `docs/PLAN-data-pipeline.md` | — | Scaffold |
| Scalability Audit | `docs/architecture/scalability_audit.md` | — | Assessment complete |
| Data Lineage (P2-022) | End-to-end lineage fields | — | Closed |
| Integration Checklist (P1-030) | Per-integration validation | — | Closed |

## Domain and Data Product Boundary Definitions

### Domain Taxonomy

| Domain | Scope | Primary Data | Ownership |
|--------|-------|-------------|-----------|
| **Clinical** | Patient data, encounters, clinical facts, mentions, concepts | `clinical_facts`, `mentions`, `mention_concept_candidates`, `documents` | Clinical AI team |
| **Interop** | External data exchange, FHIR, OpenEHR, Meditech | `fhir_resources`, `openehr_compositions`, `integration_logs` | Interop team |
| **Analytics** | Reporting, quality measures, outcome metrics, dashboards | `quality_measures`, `quality_metrics`, `reports`, `audit_events` | Data/Analytics team |
| **Admin** | Users, tenants, RBAC, configuration, API keys | `users`, `tenants`, `roles`, `permissions`, `config` | Platform team |

### Domain Interaction Map

```
Clinical <-> Interop (document exchange, FHIR/OpenEHR transforms)
Clinical -> Analytics (clinical facts feed quality measures)
Admin -> Clinical (tenant/user context for all queries)
Admin -> Interop (tenant/integration configuration)
Analytics <- Interop (integration health metrics)
```

## Data Product Contracts Per Domain

### Clinical Domain Data Product

| Contract Field | Value |
|---------------|-------|
| **Product name** | Clinical Facts Stream |
| **Owner** | Clinical AI Lead |
| **Schema** | `clinical_facts` table (patient_id, fact_type, concept_id, confidence, provenance, created_at) |
| **SLO: Freshness** | <5 minutes from ingestion to fact availability |
| **SLO: Completeness** | >95% of extracted mentions mapped to OMOP concepts |
| **SLO: Accuracy** | Extraction precision >85% (P4-010 threshold) |
| **SLO: Availability** | >99.5% read availability |
| **Access pattern** | Read via clinical query API; write via ingestion pipeline only |
| **Change notification** | Schema changes announced 30 days in advance via changelog |
| **Quality gate** | `data_quality_service.py` validates on write |

### Interop Domain Data Product

| Contract Field | Value |
|---------------|-------|
| **Product name** | Integration Exchange Log |
| **Owner** | Interop Lead |
| **Schema** | `integration_logs` (source_system, direction, format, status, timestamp) |
| **SLO: Freshness** | Real-time (event-driven) |
| **SLO: Completeness** | 100% of exchange events logged |
| **SLO: Availability** | >99.0% (non-critical for clinical decisions) |
| **Access pattern** | Read via analytics queries; write via integration pipeline |
| **Change notification** | Breaking changes require 14-day notice |

### Analytics Domain Data Product

| Contract Field | Value |
|---------------|-------|
| **Product name** | Quality Measures Report |
| **Owner** | Data/Analytics Lead |
| **Schema** | `quality_measures` (measure_id, period, numerator, denominator, rate, confidence_interval) |
| **SLO: Freshness** | <1 hour from source data change |
| **SLO: Completeness** | All active measures computed per period |
| **SLO: Availability** | >99.0% |
| **Access pattern** | Read via reports API and dashboard; write via quality pipeline |
| **Quality gate** | Measure computation validated against `quality_measures.py` (2,223 lines) |

### Admin Domain Data Product

| Contract Field | Value |
|---------------|-------|
| **Product name** | Tenant Configuration |
| **Owner** | Platform Lead |
| **Schema** | `tenants` (tenant_id, name, config, limits, created_at) |
| **SLO: Freshness** | <1 second (transactional) |
| **SLO: Availability** | >99.9% (critical for all queries) |
| **Access pattern** | Read via middleware on every request; write via admin API |

## Governance Model

### Federated Computational Governance

| Governance Layer | Responsibility | Enforcement |
|-----------------|---------------|-------------|
| **Global policies** | Data retention (7 years HIPAA), encryption at rest, audit logging | Automated via infrastructure policies |
| **Domain policies** | Schema management, SLO definition, access control | Domain owner responsibility |
| **Quality gates** | Data validation, completeness checks, freshness monitoring | `data_quality_service.py` (centralized engine, domain-specific rules) |
| **Interoperability standards** | FHIR, OpenEHR, OMOP vocabularies | Centralized standards body |

### Governance Cadence
- **Weekly:** Domain owners report SLO adherence
- **Monthly:** Cross-domain governance review (schema changes, new contracts)
- **Quarterly:** Full governance audit (compliance, quality, retention)

## Analytics Domain Pilot Design (Recommended First Domain)

### Why Analytics First
1. **Least safety-critical:** Reporting data does not affect clinical decisions directly
2. **Most self-contained:** Analytics reads from Clinical and Interop but has minimal write-back
3. **Clear consumer base:** Operations and executive reporting teams
4. **Measurable benefit:** Self-serve reporting reduces engineering support tickets

### Pilot Architecture

```
Clinical Domain (PostgreSQL) --ETL--> Analytics Domain (Read Replica or Dedicated DB)
                                        |-- Quality Measures Pipeline
                                        |-- Reporting Dashboard
                                        +-- Self-Serve Query Interface
```

### Pilot Success Criteria
- Operations team can answer 80% of reporting questions without engineering support
- Data freshness <1 hour for all analytics queries
- Query availability >99.5% during business hours
- No impact on clinical domain performance (latency p95 unchanged)

### Pilot Timeline
| Phase | Duration | Activities |
|-------|----------|-----------|
| Design | 2 weeks | Schema design, ETL pipeline design, SLO definition |
| Build | 4 weeks | Read replica setup, ETL implementation, dashboard |
| Validate | 2 weeks | SLO verification, user acceptance testing |
| Operate | 4 weeks | Supervised operation, SLO monitoring, feedback |

## Self-Serve Data Infrastructure Requirements

| Requirement | Description | Priority |
|------------|-------------|----------|
| Query interface | SQL-compatible interface for analytics domain | High |
| Data catalog | Searchable catalog of available data products | Medium |
| Access control | Per-domain, per-user query permissions | High |
| Monitoring | SLO dashboards per domain | High |
| Alerting | SLO breach alerts to domain owners | Medium |
| Documentation | Per-product schema docs and usage examples | Medium |

## Activation Gate Checklist

- [ ] Patient count exceeds 100K
- [ ] Engineering team exceeds 10 members
- [ ] Measurable cross-domain query bottleneck documented
- [ ] Analytics domain pilot design approved by CTO
- [ ] ETL pipeline architecture reviewed
- [ ] Budget approved for additional infrastructure ($500-2K/mo estimated)
- [ ] Domain owners assigned and governance cadence established

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P2-022 (Data lineage) | Lineage fields support cross-domain traceability | Closed |
| P1-030 (Integration onboarding) | Onboarding checklist informs domain contracts | Closed |
| P2-010 (Drift detection) | Drift alerts apply per-domain | Closed |
| P4-012 (Developer platform) | External API may need domain-aware routing | Deferred (ADR) |
