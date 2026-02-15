# Pilot Readiness TODO List (Ramsey Health / Australia / OpenEHR)

## Priority Legend
- P0: must stop
- P1: must complete before external pilot
- P2: must complete before scale
- P3: can defer to post-pilot optimization

## Phase 0 – Mandatory Pre-Launch (Complete First)

1. [ ] P1 Enforce authentication by default in all non-dev environments (`auth_enabled`), and reject startup if unauthenticated in production (`backend/app/core/config.py`).
2. [ ] P1 Remove insecure defaults and hardcoded credentials from compose/env templates (`docker-compose.yml`, `.env.example`, `backend/app/core/config.py`).
3. [ ] P1 Require Redis authentication and network isolation (`docker-compose.yml`, `backend/app/core/queue.py`).
4. [ ] P1 Define OpenEHR canonical ingest contract for Meditech-to-OpenEHR conversion (including source system, identifiers, code system mapping, encounter metadata).
5. [ ] P1 Set mock/fallback paths to explicit pilot-blocking behavior for core clinical paths (`backend/app/services/graph_database_service.py`, `backend/app/services/kafka_service.py`).
6. [ ] P1 Add Australian residency/consent metadata capture in ingestion and governance paths (`backend/app/models/clinical_fact.py`, `backend/app/services/fhir_import.py`).
7. [ ] P1 Create pilot runbook with one canonical pipeline: `Document -> Mentions -> Facts -> KG -> QA` and document command order (`tasks/03_wiring_audit.md`).

## Phase 1 – Controlled Pilot Readiness (Within 1 Week)

8. [ ] P1 Declare one canonical extraction + KG route in UI/backend and deprecate alternate entrypoints (`frontend/src/app/nlp/page.tsx`, `backend/app/api/nlp.py`).
9. [ ] P1 Implement explicit confidence gates in UI workflows for 77% output bands (`frontend/src/app/clinical/page.tsx`, `backend/app/services/hybrid_clinical_analyzer.py`).
10. [ ] P2 Add tenant/organizational scope checks at data query boundaries (`backend/app/core/tenant.py`, `backend/app/security/rbac_service.py`).
11. [ ] P2 Add audit events for worker-based clinical data operations (`backend/app/core/queue.py`, `backend/app/workers/*`).
12. [ ] P2 Update health checks to mark dependency or mock degradation as actionable warnings and incident pages (`backend/app/api/health.py`).

## Phase 2 – Stabilization (Days 8-30)

13. [ ] P1 Add service-result reliability model for core clinical-agent paths (ok/degraded/unavailable signals) (`backend/app/api/clinical_agent.py`, `backend/app/services/clinical_intelligence_agent.py`).
14. [ ] P2 Add OpenEHR migration test suite with Meditech fixture replay and evidence comparison (`backend/tests/`).
15. [ ] P2 Add contract tests for KG provenance and evidence requirements in QA (`backend/tests/test_kg_orchestration_api.py`, `backend/app/api/clinical_agent.py`).
16. [ ] P1 Document escalation matrix and runbook (clinical, platform, security, data governance owners).
17. [ ] P2 Add operational ownership and alerting plan for dependency failures (SRE runbook + contact tree).

## Phase 3 – Pre-Scale (Days 31-90)

18. [ ] P2 Add backup strategy and recovery drill for PostgreSQL and Neo4j (`docker-compose*.yml`, `k8s/` runbooks).
19. [ ] P2 Implement multi-worker separation by pipeline class (NLP vs mapping vs KG vs export) and queue backpressure.
20. [ ] P3 Split monolithic API client/API modules to improve incident triage and frontend deployability if scale is planned.
21. [ ] P2 Add FHIR interoperability checks for OpenEHR-derived profiles and Meditech compatibility scenarios.

## Ownership Mapping

- CTO: items 4, 7, 8, 13, 18, 19  
- CISO: items 1, 2, 3, 5, 11, 12, 16  
- CIO: items 6, 10, 14, 15, 16, 17, 18, 20  
- VP Product/Clinical AI: items 9, 10, 14, 15, 20  
- Operations: items 12, 17, 18, 19

## Weekly Exit Criteria

- Week 1: Items 1-12 complete or actively blocked with signed risk acceptance.  
- Week 4: P1 items complete, reliable mock handling, and documented escalation in operation.  
- Week 12: All P2/P3 items planned with clear owners and owners' progress gates.
