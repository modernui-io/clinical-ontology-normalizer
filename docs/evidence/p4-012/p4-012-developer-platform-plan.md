# P4-012-I: External Developer Platform Plan

**Task:** P4-012-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Governance plan complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-012-developer-platform.md`

## Summary

This document codifies the implementation plan for building an external developer platform for partner integrations. Activation is gated on first external partner LOI + sandbox provisioning capability, as defined in P4-012-D. No external API access is available during pilot.

## Current State Assessment

| Component | File | Lines | Maturity |
|-----------|------|-------|----------|
| RBAC Service | `backend/app/security/rbac_service.py` | 1,013 | Production (P0-016 enforced) |
| Tenant Service | `backend/app/core/tenant.py` | 260 | Production (P0-016 enforced) |
| Audit Middleware | `backend/app/middleware/audit_middleware.py` | 630 | Production (P0-014/015 enforced) |
| OpenAPI Spec Tests | `backend/tests/test_openapi_spec.py` | 141 | Pilot-level |
| API Endpoints | FastAPI auto-generated | 726 | Mixed maturity |

## API Key Model Design

### Key Lifecycle

```
Create -> Distribute -> Active -> Rotate -> Revoke -> Archived
```

### Key Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_key_id` | UUID | Yes | Unique key identifier |
| `tenant_id` | UUID | Yes | Owning tenant (scoped isolation) |
| `key_hash` | string(64) | Yes | SHA-256 hash of key (plaintext never stored) |
| `key_prefix` | string(8) | Yes | First 8 chars for identification (e.g., `con_live_`) |
| `name` | string | Yes | Human-readable label (e.g., "Production - Partner A") |
| `scopes` | array[string] | Yes | Permitted API categories (e.g., ["clinical:read", "documents:write"]) |
| `rate_limit_profile` | enum | Yes | Rate limit tier: starter, standard, enterprise |
| `created_at` | datetime | Yes | Creation timestamp (UTC) |
| `expires_at` | datetime | No | Optional expiry (default: 1 year, max: 2 years) |
| `last_used_at` | datetime | No | Last successful API call timestamp |
| `revoked_at` | datetime | No | Revocation timestamp (null if active) |
| `revoked_by` | string | No | Identity of revoker |
| `revocation_reason` | string | No | Reason for revocation |

### Rate Limit Profiles

| Profile | Requests/min | Requests/day | Burst | Concurrent |
|---------|-------------|-------------|-------|-----------|
| Starter | 60 | 10,000 | 10 | 5 |
| Standard | 300 | 100,000 | 50 | 20 |
| Enterprise | 1,000 | 1,000,000 | 200 | 100 |

### Key Security Requirements
1. Plaintext key shown once at creation — never stored or retrievable
2. All key storage uses SHA-256 hash only
3. Key rotation generates new key + 24-hour grace period for old key
4. Revoked keys return `401 Unauthorized` immediately (no grace period)
5. All key lifecycle events logged to audit trail with tenant context

## Sandbox Controls

### K8s Namespace Isolation
- Each partner sandbox runs in dedicated Kubernetes namespace
- Network policies restrict cross-namespace communication
- Resource quotas per namespace (CPU: 2 cores, memory: 4GB, storage: 10GB)
- Sandbox namespaces use separate PostgreSQL schema (not separate database)

### Data Seeding
- Standardized synthetic patient dataset (100 patients, 10 encounters each)
- No PHI in sandbox environments — all data is synthetic
- Dataset versioned and reproducible from seed file
- Partner can request domain-specific synthetic data (e.g., cardiology, oncology)

### Reset Policy
- Partner can reset sandbox to clean state via API call
- Reset preserves API key and configuration but clears all data
- Maximum 10 resets per day (prevents abuse)
- Reset logged to audit trail

## Usage Telemetry Schema

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | UUID | Partner tenant identifier |
| `api_key_id` | UUID | Key used for this request |
| `endpoint` | string | API endpoint path |
| `method` | string | HTTP method |
| `status_code` | int | Response status code |
| `latency_ms` | int | Request-to-response time |
| `request_size_bytes` | int | Request body size |
| `response_size_bytes` | int | Response body size |
| `timestamp` | datetime | Request timestamp (UTC) |
| `error_code` | string | Error code if status >= 400 |

### Aggregation Views
- Per-tenant: request counts, error rates, p50/p95/p99 latency (hourly, daily, monthly)
- Per-key: usage volume, last active, scope utilization
- Per-endpoint: popularity, error rates, latency distribution
- Alerts: rate limit approaching (80%), error rate spike (>5%), key unused (>30 days)

## Partner Onboarding Workflow

### Onboarding Stages

```
LOI Signed -> BAA Executed -> Sandbox Provisioned -> API Key Issued -> Integration Tests -> Go-Live Review -> Production Access
```

### Stage Details

| Stage | Owner | Duration | Exit Criteria |
|-------|-------|----------|--------------|
| 1. LOI Signed | BD + Legal | 1-2 weeks | Signed LOI with scope of integration |
| 2. BAA Executed | Legal + Compliance | 1-2 weeks | Signed BAA if PHI access required |
| 3. Sandbox Provisioned | Platform | 1 day | K8s namespace + synthetic data seeded |
| 4. API Key Issued | Platform | 1 hour | Key generated with appropriate scopes |
| 5. Integration Tests | Partner + Platform | 2-3 days | 10 happy-path + 5 error-path tests passing |
| 6. Go-Live Review | CTO + Clinical AI | 1 day | Security review, data flow review, SLO agreement |
| 7. Production Access | Platform | 1 hour | Production key issued, monitoring enabled |

**Target: <5 business days from sandbox provisioning to integration tests passing.**

## Developer Portal Architecture

### Evaluation Criteria for Portal Platform

| Criterion | Weight | Redocly | Stoplight | Custom Build |
|-----------|--------|---------|-----------|-------------|
| OpenAPI integration | 25% | Excellent | Excellent | Medium |
| Hosted/managed option | 20% | Yes | Yes | No |
| Custom branding | 15% | Yes | Yes | Full control |
| Interactive API explorer | 20% | Yes | Yes | Build required |
| Cost (annual) | 10% | $5-15K | $10-25K | Engineering time |
| Time to deploy | 10% | 1-2 weeks | 1-2 weeks | 4-8 weeks |

**Recommendation:** Redocly for initial deployment (lower cost, faster). Migrate to Stoplight if multi-version documentation required.

### Portal Content Structure
1. **Getting Started:** Authentication, first API call, sandbox setup
2. **API Reference:** Auto-generated from OpenAPI spec (726 endpoints, filtered to external-facing)
3. **Guides:** Integration patterns, error handling, rate limits, best practices
4. **SDKs:** Auto-generated from OpenAPI (Python, TypeScript, Java)
5. **Status:** Real-time API health (limited view of `/health` endpoint)
6. **Support:** Contact form, SLA documentation, changelog

## Activation Gate Checklist

- [ ] First external partner LOI signed
- [ ] BAA template approved by Legal + Compliance
- [ ] Sandbox provisioning automated (K8s namespace + data seeding)
- [ ] API key management service deployed and tested
- [ ] Rate limiting enforcement verified per tier
- [ ] Usage telemetry pipeline operational
- [ ] Developer portal deployed with OpenAPI integration
- [ ] Integration test suite template available for partners
- [ ] Go-live review process documented and staffed

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P0-016 (Tenant boundaries) | Foundation for API key tenant scoping | Closed |
| P0-014/015 (Audit coverage) | Audit trail for key lifecycle and API usage | Closed |
| P4-002 (TEFCA) | May require specific API compliance | Deferred (ADR) |
| P4-003 (ONC) | May require API certification | Deferred (ADR) |
| P4-013 (SaMD) | API for clinical data may have regulatory implications | Deferred (ADR) |
