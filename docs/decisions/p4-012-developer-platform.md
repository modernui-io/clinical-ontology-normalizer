# P4-012-D: External Developer Platform Decision

**Decision ID:** P4-012-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** CTO + Product
**Risk Owner:** CTO
**Evidence Owner:** Product

## Context

The system exposes 726 API endpoints via FastAPI with auto-generated OpenAPI spec:

- OpenAPI spec tested at `backend/tests/test_openapi_spec.py` (141 lines) — validates tags, examples, descriptions
- API test results documented at `docs/api_test_results.md`
- RBAC enforcement: `backend/app/security/rbac_service.py`, tenant isolation: `backend/app/core/tenant.py`
- Rate limiting exists via security headers (P0-009 through P0-017)

**Current state:** Internal API only. No developer portal, no sandboxed API keys, no external usage dashboards.

## Decision

**Defer external developer platform until core product stabilizes. Define API surface and isolation model now.**

### API Surface Decision

| API Category | External Exposure | Rationale |
|-------------|------------------|-----------|
| Clinical Query (`/api/v1/clinical/query`) | Yes (future) | Core value proposition for partners |
| Document Ingestion (`/api/v1/documents/`) | Yes (future) | Data exchange integration point |
| FHIR endpoints (`/api/v1/fhir/`) | Yes (future) | Standards-based interoperability |
| OpenEHR endpoints (`/api/v1/openehr/`) | Yes (future) | Primary exchange format |
| Admin/Config (`/api/v1/admin/`) | No | Internal operations only |
| Health/Readiness (`/api/v1/health/`) | Limited | Status only, no PHI |

### Tenant Isolation Model

1. **API key scoping:** Each partner gets tenant-specific API key with namespace isolation
2. **Rate limiting:** Per-tenant rate limits (not shared pool)
3. **Data isolation:** Tenant boundary enforced at query level (P0-016 already implemented)
4. **Audit:** All partner API calls logged with tenant context (P0-014/015 already implemented)

### Partner Onboarding Requirements

1. Signed data sharing agreement (or BAA for PHI access)
2. Sandboxed environment provisioned (separate from production)
3. API key issued with tenant ID and rate limit profile
4. Integration test suite provided (minimum 10 happy-path + 5 error-path tests)
5. Time-to-first-integration target: <5 business days

### Platform Components (When Activated)

| Component | Build vs. Buy | Effort | Priority |
|-----------|--------------|--------|----------|
| Developer portal (docs) | Buy (Redocly or Stoplight) | Low | First |
| API key management | Build (extend existing auth) | Medium | First |
| Usage dashboard | Build (extend existing metrics) | Medium | Second |
| Sandbox provisioning | Build (K8s namespace per tenant) | High | Second |
| SDK generation | Auto-generate from OpenAPI | Low | Third |

## Consequences

- No external developer platform during pilot
- API surface defined and categorized for future exposure
- Tenant isolation already enforced (P0-016)
- External platform activation gated on: (a) first external partner LOI, (b) sandbox provisioning capability
- Cross-dependency: P4-002 (TEFCA) and P4-003 (ONC) may require specific API compliance for external access

## Evidence Paths

- OpenAPI spec tests: `backend/tests/test_openapi_spec.py`
- RBAC: `backend/app/security/rbac_service.py`
- Tenant isolation: `backend/app/core/tenant.py`
- Audit middleware: `backend/app/middleware/audit_middleware.py`
- API docs: `docs/api_test_results.md`
- This decision: `docs/decisions/p4-012-developer-platform.md`
