# CISO Review: Enterprise Pilot Readiness (Pass 1)

**Date:** 2026-02-13  
**Scope:** Security and privacy readiness for Ramsey Health pilot and Meditech-to-OpenEHR migration context  
**Mode:** Analysis-only (no code changes in this pass)

## Executive Verdict
**Controlled go with immediate conditional controls**, not production open.

This codebase has the right security primitives in place, but key launch-critical controls are currently incomplete for health-system scale.

## Finding Register

### CISO-1 — Auth Is Disabled by Default in Core Config
Severity: P0  
Likelihood: High  
Evidence: `backend/app/core/config.py: auth_enabled`  
Impact: Default unauthenticated access model is incompatible with PHI-handling and enterprise controls.  
Recommendation: enforce environment-gated authentication defaults at runtime and reject unauthenticated startup in non-dev environments.  
Pilot Impact: **hold** for external customer access until enforced.

### CISO-2 — Default Hardcoded Credentials and Placeholder Secrets in Infrastructure Manifests
Severity: P1  
Likelihood: High  
Evidence: `docker-compose.yml`, `docker-compose.fhir.yml`, `fhir-mcp/docker-compose.yml`, `.env.example`, `backend/app/core/config.py`  
Impact: Hardcoded defaults enable accidental insecure deployments and reduce audit defensibility.  
Recommendation: require explicit secrets in runtime envs and block startup with placeholder defaults.  
Pilot Impact: **hold** until sanitized deployment manifests are enforced.

### CISO-3 — Redis Has No Access Controls and May Carry PHI-Adjacent Cached Payloads
Severity: P1  
Likelihood: High  
Evidence: `docker-compose.yml` (`redis` service command), `backend/app/core/redis_client.py`  
Impact: Queue/cache tampering or leakage risk; queue/job spoofing potential if network access is granted.  
Recommendation: enforce Redis auth and network scoping, and classify what values may be cached.  
Pilot Impact: **hold** for any environment beyond local dev.

### CISO-4 — Database/Graph Credentials and Mismatches Can Cause Unauthorized Fallbacks
Severity: P1  
Likelihood: Medium  
Evidence: `docker-compose.yml`, `backend/app/services/graph_database_service.py`, `backend/app/services/kafka_service.py`  
Impact: dependency mismatches can trigger mock/fallback modes instead of hard failures, concealing unauthorized or degraded data states.  
Recommendation: fail closed on critical store unavailability and require explicit mock mode approvals.  
Pilot Impact: **controlled go** only with signed exception handling in incident policy.

### CISO-5 — Encryption at Rest and Strict TLS In-Transit Not Fully Enforced
Severity: P1  
Likelihood: High  
Evidence: `docker-compose.yml`, `docker-compose.prod.yml`, `nginx/nginx.conf`, `docs/plans/03_ciso_devsecops.md`  
Impact: PHI-at-rest/in-transit controls are likely insufficient for enterprise compliance review.  
Recommendation: enforce storage-level encryption posture for PostgreSQL/Neo4j/Redis and terminate TLS across exposed and internal service links.  
Pilot Impact: **hold** unless approved risk exception is explicit and signed.

### CISO-6 — Broad Mock-Mode Surfaces Lack Security Alerting
Severity: P2  
Likelihood: High  
Evidence: `backend/app/services/graph_database_service.py`, `backend/app/services/kafka_service.py`, `backend/app/api/health.py`  
Impact: security/compliance staff cannot distinguish live clinical context from synthetic fallback behavior.  
Recommendation: surface mock-mode state as a high-visibility audit event and include it in log pipelines and readiness checks.  
Pilot Impact: **controlled go** with strict monitoring.

### CISO-7 — Audit Coverage Has Gaps for Worker and Graph Access Paths
Severity: P2  
Likelihood: Medium  
Evidence: `backend/app/middleware/audit_middleware.py`, `backend/app/workers`, `backend/app/services/graph_database_service.py`  
Impact: PHI access in background paths may be invisible to audit trail and breach review processes.  
Recommendation: add worker-side audit event emission and graph-access audit tags (`query`, `read`, `patient_id`).  
Pilot Impact: **controlled go**; high priority before independent audit readiness.

### CISO-8 — RBAC Is Endpoint-Centric Without Strong Tenant-Level Constraints
Severity: P2  
Likelihood: Medium  
Evidence: `backend/app/security/rbac_service.py`, `backend/app/core/tenant.py`  
Impact: enterprise multi-tenant separation is incomplete for a health-system deployment.  
Recommendation: enforce tenant/organization scope at query boundaries and authorization checks.  
Pilot Impact: **controlled go** only in a single-tenant internal pilot.

### CISO-9 — External Model and Connector Trust Boundaries Are Under-Specified
Severity: P1  
Likelihood: Medium  
Evidence: `backend/app/services/agents/*`, `backend/app/services/nlp_*`, `backend/app/core/config.py`  
Impact: PHI may transit to external AI services or unstable connectors without explicit policy gating and DPA/BAA assumptions.  
Recommendation: confirm provider/legal contracts and define approved model/provider routing for PHI-bound paths.  
Pilot Impact: **hold** for any unapproved external LLM inference path.

### CISO-10 — Missing Australian Data-Residence and Consent Mapping Controls
Severity: P2  
Likelihood: Medium  
Evidence: `docs/agent_context_health_graph.md`, `backend/app/models/clinical_fact.py`, pipeline and connector services  
Impact: Australia/NDI/APS obligations can fail if residency and consent flags are not captured in data contracts.  
Recommendation: add explicit consent metadata and jurisdictional retention policy at ingestion and export boundaries.  
Pilot Impact: **controlled go** with clinical governance sign-off.

## OpenEHR-Specific Security Observations
- No dedicated OpenEHR adapter is currently visible in the connector layer; this increases transformation and re-identification risk during migration unless proven mapping is validated.
- Any Meditech export conversion to OpenEHR should include explicit lineage fields for patient identifiers, encounter, composer, source system, terminology system, and transformation timestamp.

## Controls-to-Finding Mapping (high-level)
- HIPAA technical safeguards: `ct` for access control and audit controls (`backend/app/core/config.py`, `backend/app/middleware/audit_middleware.py`) need stricter gating.
- Integrity and transmission security: `backend/app/services/graph_database_service.py`, `backend/app/services/kafka_service.py`, `nginx/nginx.conf`, infrastructure manifests.
- Australian Privacy Act / APS expectations: currently not operationalized in code; governance additions needed in ingestion and consent model.

## CISO Go/No-Go Checklist
Go only if all are true:
- auth is mandatory and cannot be disabled outside local development;
- all secret and password sources are explicit at runtime;
- no PHI handling path runs unaudited or in synthetic fallback mode without explicit flagging;
- mock-mode is treated as incident-worthy in health checks and alerts;
- OpenEHR conversion contract includes legal and consent controls.

Decision for leadership:
Current status supports a **restricted internal pilot only**, with no external production access until P0/P1 controls are materially reduced.
