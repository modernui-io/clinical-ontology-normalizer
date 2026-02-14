# CTO Review: Enterprise Pilot Readiness (Pass 1)

**Date:** 2026-02-13  
**Scope:** Ramsey Health Australia pilot readiness, with Meditech-to-OpenEHR migration context  
**Mode:** Analysis-only (no code changes in this pass)  

## Executive Verdict
**Controlled go** for a restricted pilot only.  
Recommended decision: **proceed with strict guardrails**, no unrestricted production access, and no claims of "OpenEHR-native parity" until connector assumptions are verified.

## Key Decisions for the CTO Lens
- The platform is functionally advanced enough to run a pilot, but several architecture-level risk clusters are unresolved.
- The highest CTO blocker is not feature absence, but **observability-safe correctness under failure**.
- OpenEHR migration is currently an integration planning task, not yet an implemented technical contract.

## Finding Register

### CTO-1 — Neo4j Mock Mode Is Safety-Critical and Not Fail-Closed
Severity: P1  
Likelihood: High  
Evidence: `backend/app/services/graph_database_service.py`, `backend/app/services/graph_augmented_rag.py`, `exec-review/platform-review.md: The mock-mode trap section`  
Impact: Clinical reasoning can use synthetic graph context without explicit visibility to clinicians or workflows.  
Recommendation: enforce hard-fail behavior in non-dev environments when Neo4j dependency is down, or return empty results with `data_source="unavailable"` and explicit API-level warning.  
Pilot Impact: **hold** for any workflow where KG-derived recommendation is mandatory.

### CTO-2 — Mock Fallbacks Exist Across Multiple Infra Dependencies Without Hard Alerts
Severity: P1  
Likelihood: High  
Evidence: `backend/app/services/kafka_service.py`, `backend/app/services/graph_database_service.py`  
Impact: Kafka and Neo4j fallback can hide outages while continuing to serve responses, creating silent integrity failures.  
Recommendation: promote fallback state into a hard signal on `/ready` and `/health/ready`, and route to alerting.  
Pilot Impact: **controlled go** only with dependency readiness gates and on-call escalation.

### CTO-3 — OpenEHR Connector Is Not Present as a Canonical Inbound Contract
Severity: P1  
Likelihood: High  
Evidence: `backend/app/connectors/fhir_connector.py`, `backend/app/connectors/hl7v2_connector.py`, `backend/app/connectors/ccda_connector.py`, `backend/app/connectors/csv_connector.py`, absence of OpenEHR connector in `backend/app/connectors/`  
Impact: The current migration path to OpenEHR is implicit and may reintroduce data-shape drift during Meditech transitions.  
Recommendation: define and publish an OpenEHR canonical ingest adapter before pilot acceptance; treat Meditech handoff as data-contract proof point.  
Pilot Impact: **hold** until migration contract and reconciliation tests are demonstrated.

### CTO-4 — Ingestion and NLP Path Has Overlapping Pipelines Without One Canonical Route
Severity: P2  
Likelihood: High  
Evidence: `backend/app/api/nlp.py`, `backend/app/services/ensemble*`, `backend/app/services/clinical_ontology_mapper.py`, `tasks/02_agent_findings.md`, `tasks/03_wiring_audit.md`  
Impact: UI, API, and QA can follow different pathways leading to inconsistent provenance and partial KG materialization.  
Recommendation: pin one canonical path and enforce deprecation tags for alternates.  
Pilot Impact: **controlled go** with strict UI-level routing.

### CTO-5 — Credential Drift Between Services Threatens Reliable Runtime Startup
Severity: P1  
Likelihood: Medium  
Evidence: `docker-compose.yml`, `backend/app/core/config.py`  
Impact: Mismatched credentials cause local orchestration failures and can force accidental mock behavior.  
Recommendation: standardize credentials via environment contract and remove ambiguous defaults across compose/env templates.  
Pilot Impact: **controlled go** only while startup reproducibility is validated on a clean deployment.

### CTO-6 — Single-Path Async Scaling for Ingestion and Pipelines Is Not Yet Load-Robust
Severity: P2  
Likelihood: Medium  
Evidence: `docker-compose.yml` (worker services and queue bindings), `backend/app/core/queue.py`, `backend/app/services/multi_agent_orchestrator.py`, `backend/app/services/nlp_ensemble.py`  
Impact: concurrency spikes can starve pipelines; queue backpressure is under-defined.  
Recommendation: scale worker classes by pipeline class (NLP, mapping, graph build, export) and add queue-depth SLOs.  
Pilot Impact: **controlled go** with explicit volume caps per day and queue monitoring.

### CTO-7 — Exception Handling in Core Clinical Agent Path Remains Non-Deterministic
Severity: P1  
Likelihood: Medium  
Evidence: `backend/app/api/clinical_agent.py`, `backend/app/services/clinical_intelligence_agent.py`, `backend/app/services/multi_agent_orchestrator.py`  
Impact: Swallowed exceptions degrade into plausible but incomplete outputs.  
Recommendation: typed service-result semantics with explicit degradations and "unreliable output" flags.  
Pilot Impact: **hold** for workflows used as direct clinical decision support.

### CTO-8 — Test Coverage Has Gaps for Live-Data Paths in KG and OMOP Reasoning
Severity: P2  
Likelihood: Medium  
Evidence: `backend/tests/test_graph` coverage pattern in `backend/tests/test_kg_orchestration_api.py`, `backend/tests/test_hybrid_clinical_analyzer.py`, `exec-review/quality-review.md`  
Impact: Integration regressions could pass unit tests but fail in end-to-end clinical runs.  
Recommendation: add contract tests with a real Neo4j + PostgreSQL stack for OMOP hierarchy, KG materialization, and KG-backed QA.  
Pilot Impact: **controlled go** with explicit acceptance criteria, not broad claims.

### CTO-9 — OpenEHR Migration Requires Terminology Consistency Governance
Severity: P2  
Likelihood: High  
Evidence: `backend/app/services/vocabulary_db.py`, `backend/app/services/clinical_ontology_mapper.py`, `backend/app/services/omop_hierarchy_service.py`  
Impact: Meditech-to-OpenEHR migration can silently fork coding systems if identifier and terminology lineage is not pinned.  
Recommendation: require source system, code system, and transformation lineage for every normalized fact before pilot load.  
Pilot Impact: **controlled go** with governance checks.

### CTO-10 — Deployment Topology Is Not Hardened for HA Expectations
Severity: P2  
Likelihood: Medium  
Evidence: `docker-compose.yml`, `docker-compose.prod.yml`, `k8s/` deployment manifests  
Impact: single-instance backend/db/neo4j/redis/Kafka profiles are insufficient for pilot resilience in a health-system environment.  
Recommendation: declare a minimum redundancy baseline for pilot host (read replicas, worker redundancy, Redis replication or managed broker).  
Pilot Impact: **controlled go** with explicit no-SLA expectation for HA.

## Top 4 Must-Fix Before Broad Pilot Expansion
1) Fail-safe when core KG or LLM dependencies are unavailable.  
2) Create one canonical ingestion-to-KG-to-QA execution route and retire ambiguous alternates.  
3) Validate OpenEHR migration contract with Meditech export samples before real data onboarding.  
4) Replace silent exception behavior with explicit reliability states in `clinical_agent.py`.

## CTO Go/No-Go Checklist
Go only if all of the following are true:
- OpenEHR intake contract is explicit and tested on realistic Meditech export files.
- No synthetic data is used in core clinical workflows unless explicitly labeled and blocked from clinical use.
- Critical failure modes are surfaced as degradations and are visible in `/health` and ops dashboards.
- Core QA path has deterministic provenance from extraction to KG to answer.

Recommendation for leadership:
Start with **restricted pilot** (single service line, curated patient set, supervised workflows), then expand once the above pass.
