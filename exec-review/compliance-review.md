# VP Compliance Review: Regulatory & Security Assessment

**Prepared for:** Audit Committee / Executive Leadership
**Author:** VP of Compliance
**Date:** 2026-02-06
**Classification:** Confidential -- Internal Use Only
**Platform:** Clinical Ontology Normalizer (CON)
**Repository Snapshot:** commit 2c2f8be (master)

---

## Executive Summary

The Clinical Ontology Normalizer (CON) platform demonstrates meaningful investment in compliance infrastructure -- JWT-based authentication, role-based access control, HIPAA-oriented audit logging, security headers middleware, rate limiting, and SSRF protections are all present. This is notably ahead of where most clinical platforms stand at the pilot stage.

However, the platform is **not yet enterprise-deployment-ready** from a compliance standpoint. Authentication is disabled by default, tenant isolation is incomplete, encryption at rest is not enforced, and the audit trail has coverage gaps that would be flagged in a HIPAA audit or SOC 2 Type II examination. The TEFCA module is entirely simulated. Several critical controls that enterprise customers, OCR investigators, and payer auditors expect are either absent or not wired into production code paths.

**Overall Compliance Readiness: PILOT -- with significant remediation required before PHI enters production.**

The good news: the architectural bones are sound, and the team has clearly been thinking about security from the start (evidenced by VP-Security tagged commits). What follows is a detailed gap analysis and prioritized remediation roadmap.

---

## 1. HIPAA Compliance Posture

### 1.1 Administrative Safeguards (45 CFR 164.308)

| Requirement | Status | Evidence | Gap |
|---|---|---|---|
| Security Officer designation | Not implemented | No configuration for security officer role | Need designated security officer role in RBAC |
| Workforce access management | Partial | RBAC with admin/provider/biller/viewer roles (`rbac_service.py`) | No access review workflow, no time-based access expiry |
| Security awareness training | Not applicable | Platform concern, not application | Organization-level control |
| Incident response procedures | Not implemented | No incident tracking or breach notification module | Critical gap for OCR compliance |
| Contingency planning | Not implemented | No backup verification or disaster recovery endpoints | Operational gap |

### 1.2 Technical Safeguards (45 CFR 164.312)

| Requirement | Status | Evidence | Gap |
|---|---|---|---|
| Unique user identification | Implemented | JWT tokens with user_id (`auth_middleware.py:163`) | Auth disabled by default (`config.py:102`) |
| Emergency access procedure | Not implemented | No break-glass mechanism | Required for clinical use |
| Automatic logoff | Partial | 30-min access token expiry (`config.py:117`) | No session invalidation on inactivity |
| Encryption at rest | NOT IMPLEMENTED | Database stores PHI in plaintext PostgreSQL | **Critical finding** |
| Encryption in transit | Partial | HSTS headers present in production (`security_headers.py:54-57`) | No TLS enforcement at infrastructure level; docker-compose exposes plain HTTP |
| Audit controls | Implemented | `audit_service.py` with PHI detection, HIPAA export format | Coverage gaps (see Section 4) |
| Integrity controls | Partial | SHA-256 checksums on audit exports (`audit_service.py:754`) | No integrity verification on stored PHI |
| PHI access logging | Implemented | Auto-detection via path/resource/content patterns (`audit_service.py:56-84`) | Pattern-based detection may miss novel PHI vectors |

### 1.3 PHI Handling Assessment

**Where PHI lives in this system:**
- PostgreSQL: Clinical documents, patient records, clinical facts, mentions, FHIR resources
- Neo4j: Knowledge graph nodes containing patient clinical data
- Redis: Potentially cached query results containing PHI
- Kafka: Stream messages may contain clinical data
- Filesystem: Export files (NDJSON, audit exports)
- Application logs: Audit entries may contain PHI metadata

**Critical Finding: No encryption at rest.** The `docker-compose.yml` shows PostgreSQL (`postgres:16-alpine`) and Neo4j (`neo4j:5`) running with default configurations. Neither database has encryption at rest configured. The PostgreSQL password is `postgres` (line 14), and Neo4j uses `neo4j/password` (line 49). Redis runs without authentication (`redis:7-alpine`, line 30). This configuration would fail any compliance audit immediately.

**Critical Finding: Redis has no authentication.** Redis is exposed on port 16379 with no password protection (`docker-compose.yml:32`). Any process on the network can read cached data, which may include PHI-adjacent query results.

---

## 2. Authentication & Authorization Assessment

### 2.1 Authentication Architecture

The platform implements a dual authentication model:

1. **API Key Authentication** (`security.py`): Simple key-based auth for service-to-service and development use
2. **JWT Authentication** (`auth_middleware.py`): Full user-based auth with access/refresh token rotation

**Strengths:**
- Token rotation on refresh (refresh tokens are revoked and reissued)
- Logout-all-devices capability (`auth.py:262-278`)
- Password change revokes all tokens
- Bcrypt password hashing (`rbac.py:143`)
- Insecure default detection (`config.py:22-28`) -- rejects known-bad values like "password" and "changeme"
- Production environment validation requires credentials (`config.py:194-204`)

**Findings:**

| Finding | Severity | Location | Detail |
|---|---|---|---|
| Auth disabled by default | HIGH | `config.py:102` | `auth_enabled: bool = False` -- must be opt-out, not opt-in for production |
| Dev auth bypass exists | HIGH | `auth_middleware.py:116-135` | `auth_bypass_dev` returns full admin permissions with static user ID |
| No MFA/2FA | HIGH | System-wide | No multi-factor authentication. Required for HIPAA administrative access |
| HS256 JWT algorithm | MEDIUM | `config.py:116` | Symmetric key algorithm; RS256 with asymmetric keys is preferred for production |
| No account lockout | MEDIUM | `auth.py:155-157` | Failed logins are logged but no lockout after N failures |
| No password complexity enforcement | MEDIUM | `auth.py:88` | Only `min_length=8` -- no complexity requirements (uppercase, number, special char) |
| API key logged in audit | LOW | `audit_middleware.py:152-154` | Partial API key logged (`api:{api_key[:8]}...`) -- acceptable but note for PCI |
| Docker-compose API key | HIGH | `docker-compose.yml:127` | `API_KEY: ${API_KEY:-dev-api-key-change-in-production}` -- fallback default is insecure |

### 2.2 Authorization (RBAC) Assessment

The RBAC implementation in `rbac_service.py` is well-structured:

- 4 system roles: admin, provider, biller, viewer
- 33 granular permissions across 10 resource types
- Resource:action pattern (e.g., `documents:read`, `patients:write`)
- Permission caching with TTL (1 hour, 10K user max) -- VP-Memory-1

**Gaps:**
- **No row-level security.** RBAC controls endpoint access but does not enforce which *specific* patients or documents a user can access. A provider with `patients:read` can read ALL patients.
- **No data classification.** Permissions don't distinguish between PHI and non-PHI data access within the same resource type.
- **Tenant isolation is incomplete.** `tenant.py` and `security.py:188-231` define `TenantContext` but `get_tenant_context()` always returns unrestricted access (`tenant_id=None`) in the current implementation.
- **No separation of duties enforcement.** An admin can simultaneously be a provider with full data access -- no conflict-of-interest controls.

---

## 3. Infrastructure Security Assessment

### 3.1 Docker Compose / Deployment Security

Reviewing `docker-compose.yml` against CIS Docker Benchmark and HIPAA infrastructure requirements:

| Finding | Severity | Line(s) | Detail |
|---|---|---|---|
| Hardcoded database credentials | CRITICAL | 13-14 | `POSTGRES_USER: postgres`, `POSTGRES_PASSWORD: postgres` |
| Hardcoded Neo4j credentials | CRITICAL | 49 | `NEO4J_AUTH: neo4j/password` |
| Mismatched Neo4j passwords | HIGH | 49, 124 | Compose uses `neo4j/password` but backend env uses `NEO4J_PASSWORD: clinical123` |
| Redis no authentication | HIGH | 30-31 | No `--requirepass` flag on Redis |
| Ports exposed to host | MEDIUM | Multiple | PostgreSQL (15432), Redis (16379), Neo4j (7474/7687), Kafka (9092/29092), Zookeeper (2181) all bound to 0.0.0.0 |
| No network segmentation | MEDIUM | N/A | All services on default Docker network; no internal-only networks defined |
| Source code mounted in container | HIGH | 141-142 | `./backend:/app` volume mount -- exposes source code inside container |
| No resource limits | MEDIUM | N/A | No CPU/memory limits on any service |
| Kafka plaintext listeners | MEDIUM | 93 | `PLAINTEXT://kafka:9092` -- no TLS between services |
| No health check on frontend | LOW | 196-200 | Frontend container has no healthcheck |

### 3.2 Security Headers

The `security_headers.py` middleware is well-implemented:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- HSTS: 1 year with includeSubDomains and preload (production only)
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: restricts geolocation, microphone, camera, payment
- Content-Security-Policy: default-src 'none' (production only)
- Cache-Control: no-store, no-cache, must-revalidate

**Assessment:** This is solid work. The production-only gates on HSTS and CSP are appropriate.

### 3.3 SSRF Protection

FHIR URL validation in `fhir.py:47-138` provides:
- Private IP blocking (RFC 1918, link-local, loopback, multicast)
- Internal hostname pattern blocking (localhost, .local, .internal, kubernetes, metadata)
- Configurable allowlist via `ALLOWED_FHIR_SERVERS` setting
- Localhost allowed only when `allow_localhost_fhir=True` (development)

**Assessment:** Good SSRF protection for the FHIR endpoint. However, this protection is not applied globally -- other endpoints that accept URLs (webhooks, data source connectors) should be audited for similar protection.

### 3.4 Rate Limiting

`rate_limit.py` implements token-bucket rate limiting with:
- Per-endpoint configurable limits
- Expensive operation throttling (MDT sessions: 10/min, benchmarks: 5/min)
- Standard rate limit headers (X-RateLimit-Limit, Remaining, Reset)
- 429 responses with Retry-After

**Gap:** Rate limiting is in-memory only. In a multi-instance deployment, each instance maintains independent counters. Must move to Redis-backed rate limiting for production.

---

## 4. Audit Trail Completeness

### 4.1 What Is Logged

The `audit_middleware.py` automatically captures:
- Every HTTP request (excluding health/docs/static paths)
- User ID, IP address, user agent
- Request method, path, response status
- Duration, request ID for correlation
- PHI access auto-detection

The `audit_service.py` provides:
- Structured logging for read, create, update, delete, export, search actions
- PHI pattern detection (SSN, MRN, phone, email, DOB, patient name, address, insurance ID)
- HIPAA-format export with all required fields
- SHA-256 integrity checksums on exports
- 10K record export cap (VP-Validation-1)

### 4.2 Audit Gaps

| Gap | Severity | Detail |
|---|---|---|
| Not all endpoints call audit service | HIGH | Audit middleware logs HTTP metadata, but service-level PHI access (e.g., internal service calls, background workers, Kafka consumers) is not logged |
| Worker processes unaudited | HIGH | RQ worker (`docker-compose.yml:152-173`) processes documents but has no audit middleware |
| Neo4j queries unaudited | HIGH | Knowledge graph queries go directly to Neo4j; no audit trail for graph traversals that return PHI |
| Bearer token user ID not resolved | MEDIUM | `audit_middleware.py:168-170` logs `bearer_auth` instead of actual user ID for JWT-authenticated requests |
| Audit logs stored in same database as PHI | MEDIUM | Audit logs in PostgreSQL alongside PHI data -- should be segregated for tamper resistance |
| No audit log tamper detection | MEDIUM | Beyond export checksums, no mechanism to detect if audit records are modified in-place |
| Failed authentication not logged via audit service | MEDIUM | Login failures logged to application logger but not to formal audit trail |
| Kafka message consumption unaudited | MEDIUM | Streaming ETL service processes clinical data without audit entries |
| No audit retention policy | LOW | No automated purge or archival of audit logs |

### 4.3 HIPAA Audit Trail Requirements (45 CFR 164.312(b))

HIPAA requires logging of: who accessed what PHI, when, from where, and why.

- **Who:** Partially met. JWT-authenticated users are identified; API key users get truncated key.
- **What:** Met for HTTP-layer access. Not met for service-layer, worker, and graph database access.
- **When:** Met. Timestamps with timezone (UTC).
- **Where:** Met. IP address with proxy-aware extraction.
- **Why:** NOT MET. No purpose-of-use field captured in audit logs. TEFCA endpoints capture purpose, but general PHI access does not.

---

## 5. Regulatory Readiness Assessment

### 5.1 FDA Considerations

If any clinical decision support features are classified as SaMD (Software as a Medical Device):

| Requirement | Status | Gap |
|---|---|---|
| Quality Management System (QMS) | Not implemented | No 21 CFR Part 820 controls |
| Design controls | Not implemented | No design history file (DHF) |
| Risk management (ISO 14971) | Not implemented | No formal risk analysis |
| Software lifecycle (IEC 62304) | Partial | Git history exists but no formal SDLC documentation |
| Clinical validation | Not implemented | No clinical accuracy benchmarks with validated datasets |
| Intended use documentation | Not implemented | No labeling or intended use statements |

**Assessment:** The differential diagnosis, clinical calculators, drug interaction checking, and guideline-based recommendation features likely fall under FDA guidance for Clinical Decision Support (CDS). The platform needs a regulatory strategy document defining which features require 510(k) clearance vs. qualify for CDS exemptions under the 21st Century Cures Act.

### 5.2 ONC Certification (Health IT)

For ONC Health IT Certification under the ONC Cures Act Final Rule:

| Criterion | Status | Gap |
|---|---|---|
| FHIR R4 API (g)(10) | Pilot | FHIR endpoints exist but not validated against ONC conformance suite |
| SMART on FHIR | Pilot | Endpoints exist but depend on external EHR trust configuration |
| CDS Hooks | Pilot | Service exists but hook logic incomplete per CDS Hooks spec |
| Bulk Data Export | Scaffold | Mock generation paths in export service |
| US Core profiles | Not validated | FHIR resources not validated against US Core FHIR profiles |
| TEFCA readiness | Scaffold | `tefca_service.py` is simulated (mock QHINs, simulated document exchange) |

### 5.3 CMS Interoperability Rules

| Rule | Status | Gap |
|---|---|---|
| Patient Access API (CMS-9115-F) | Pilot | FHIR Patient endpoints exist but not conformance-tested |
| Provider Directory API | Not implemented | No provider directory endpoints |
| Payer-to-payer data exchange | Not implemented | Would require FHIR payer resource support |
| Prior authorization API | Not implemented | No prior auth workflow |

### 5.4 State Privacy Laws

The platform does not implement state-specific privacy controls:
- No CCPA/CPRA consumer rights workflows (California)
- No state-specific consent management (e.g., 42 CFR Part 2 for substance abuse)
- No minor consent handling variations by state
- No special protections for sensitive categories (HIV, mental health, genetic data)

---

## 6. Security Vulnerability Surface

### 6.1 Penetration Test Risk Areas

Based on code review, the following areas would likely be flagged in a penetration test:

| Area | Risk | Evidence |
|---|---|---|
| Default credentials in deployment | CRITICAL | `postgres/postgres`, `neo4j/password`, `dev-api-key-change-in-production` |
| Auth bypass mechanism | HIGH | `auth_bypass_dev` with `debug=True` gives full admin access |
| Unauthenticated endpoints | HIGH | With `AUTH_ENABLED=false` (default), all 726 endpoints are open |
| No input sanitization audit | MEDIUM | Clinical text ingestion paths need SQL injection / XSS review |
| CORS wide open in development | MEDIUM | `localhost:3000,3001,3002` -- acceptable for dev but must be locked down |
| Email in login failure logs | LOW | `auth.py:157` logs attempted email address -- information leakage |
| No CSP in development mode | LOW | Content-Security-Policy only set in production |
| Export file path traversal | MEDIUM | `download_export_file` accepts filename parameter -- needs path traversal validation |

### 6.2 Dependency Supply Chain

No evidence of:
- Dependency vulnerability scanning (Dependabot, Snyk, etc.)
- SBOM (Software Bill of Materials) generation
- Container image scanning
- Signed container images

---

## 7. Data Governance

### 7.1 PHI Data Flow

```
[External Sources]
     |
     v
[FHIR Import / Document Upload / Kafka Streams]
     |
     v
[NLP Pipeline] --> [Clinical Facts] --> [Knowledge Graph (Neo4j)]
     |                    |                      |
     v                    v                      v
[PostgreSQL]        [PostgreSQL]            [Neo4j]
     |                    |                      |
     v                    v                      v
[FHIR Export]    [Billing/Coding]     [GraphRAG / Agent Queries]
     |                    |                      |
     v                    v                      v
[External Systems]  [Claims/EDI]         [API Responses]
```

### 7.2 Data Governance Gaps

| Gap | Severity | Detail |
|---|---|---|
| No data classification policy | HIGH | PHI, PII, and non-sensitive data are not tagged or classified in the data model |
| No data retention policy | HIGH | No automated purge of expired patient data or documents |
| No right to deletion | HIGH | No patient data deletion workflow (required for some state laws) |
| No data minimization | MEDIUM | Full clinical text stored; no redaction of unnecessary PHI |
| No data lineage tracking | MEDIUM | Once data enters the system, transformation history is not tracked |
| No consent management (internal) | MEDIUM | TEFCA module has consent but no internal consent enforcement for data processing |
| No data loss prevention | MEDIUM | No DLP controls on export or API response content |
| Cross-service PHI leakage | MEDIUM | LLM features send clinical text to external APIs (Anthropic, OpenAI) without PHI scrubbing |
| No BAA documentation | HIGH | Sending PHI to LLM providers requires Business Associate Agreements |

### 7.3 Third-Party PHI Exposure

**Critical concern:** The platform sends clinical text to external LLM providers (Anthropic Claude, OpenAI GPT) for narrative extraction, clinical agent queries, and coding assistance. This constitutes PHI disclosure to a third party under HIPAA.

- `config.py:121-125`: OpenAI and Anthropic API keys configured
- `narrative_extractor.py`: Sends clinical text to LLM for narrative extraction
- Clinical agent endpoints: Forward patient data to LLM for reasoning

**Requirements before production:**
1. Executed BAA with each LLM provider
2. PHI de-identification pipeline before LLM transmission (or use HIPAA-eligible LLM endpoints)
3. Logging of all PHI transmitted to third parties
4. Data processing agreements per GDPR if serving EU patients

---

## 8. Compliance Roadmap

### Phase 1: Pre-Production Blockers (0-3 months)

These must be resolved before any real PHI enters the system:

| # | Item | Priority | Effort |
|---|---|---|---|
| 1 | Enable authentication by default; remove dev bypass from production builds | P0 | 1 week |
| 2 | Implement encryption at rest (PostgreSQL TDE or application-level encryption) | P0 | 2-3 weeks |
| 3 | Secure all infrastructure credentials (vault integration, no hardcoded defaults) | P0 | 1-2 weeks |
| 4 | Redis authentication and TLS | P0 | 1 week |
| 5 | Neo4j authentication with strong credentials and TLS | P0 | 1 week |
| 6 | Network segmentation in Docker/Kubernetes (internal-only service networks) | P0 | 1 week |
| 7 | Execute BAAs with LLM providers or implement PHI de-identification before LLM calls | P0 | 2-4 weeks |
| 8 | Complete audit trail coverage (workers, Neo4j, Kafka consumers) | P0 | 2-3 weeks |
| 9 | Account lockout after failed login attempts | P1 | 1 week |
| 10 | MFA implementation for admin and provider roles | P1 | 2-3 weeks |

### Phase 2: Enterprise Readiness (3-6 months)

| # | Item | Priority | Effort |
|---|---|---|---|
| 11 | Row-level security / patient-level access control enforcement | P1 | 3-4 weeks |
| 12 | Tenant isolation completion (wire TenantContext into all data access) | P1 | 2-3 weeks |
| 13 | Data retention policy implementation with automated purge | P1 | 2 weeks |
| 14 | Audit log segregation (separate database or append-only store) | P1 | 2 weeks |
| 15 | Purpose-of-use capture in audit trail | P1 | 1 week |
| 16 | Redis-backed distributed rate limiting | P2 | 1 week |
| 17 | Dependency vulnerability scanning in CI/CD | P2 | 1 week |
| 18 | Container image scanning and signing | P2 | 1-2 weeks |
| 19 | Incident response module (breach notification workflow) | P2 | 2-3 weeks |
| 20 | SOC 2 Type II evidence collection automation | P2 | 4-6 weeks |

### Phase 3: Regulatory Certification (6-12 months)

| # | Item | Priority | Effort |
|---|---|---|---|
| 21 | FDA regulatory strategy document (CDS exemption analysis) | P1 | 4-6 weeks |
| 22 | FHIR conformance testing against ONC certification criteria | P2 | 4-8 weeks |
| 23 | HITRUST CSF assessment readiness | P2 | 8-12 weeks |
| 24 | State privacy law compliance framework (CCPA, 42 CFR Part 2) | P2 | 4-6 weeks |
| 25 | Formal risk assessment (ISO 14971 / NIST CSF) | P2 | 4-6 weeks |
| 26 | TEFCA QHIN onboarding (replace scaffold with real integration) | P3 | 12+ weeks |

---

## 9. Top 5 Compliance Priorities for Next Quarter

### Priority 1: Enforce Authentication and Eliminate Dev Bypasses
**Risk:** Any deployment with `AUTH_ENABLED=false` (the current default) exposes all 726 API endpoints -- including full PHI access -- without authentication. The `auth_bypass_dev` flag grants unrestricted admin access with a static user ID.
**Action:** Flip default to `auth_enabled=True`. Remove `auth_bypass_dev` from production builds entirely. Add startup validation that blocks launch without JWT_SECRET_KEY in non-development environments.
**Timeline:** 2 weeks.

### Priority 2: Implement Encryption at Rest and Secure Infrastructure Credentials
**Risk:** PHI stored in plaintext PostgreSQL and Neo4j with default/hardcoded credentials would result in immediate audit failure and potential breach notification obligations if any database is compromised.
**Action:** Enable PostgreSQL TDE or implement application-level field encryption for PHI columns. Integrate a secrets manager (HashiCorp Vault, AWS Secrets Manager, or equivalent). Remove all hardcoded credentials from docker-compose.yml and configuration files. Add Redis authentication.
**Timeline:** 4 weeks.

### Priority 3: Establish BAAs and PHI Safeguards for LLM Provider Integration
**Risk:** Sending unredacted clinical text to Anthropic and OpenAI APIs without executed Business Associate Agreements constitutes an unauthorized PHI disclosure under HIPAA. This is a reportable breach waiting to happen.
**Action:** Execute BAAs with all LLM providers. Implement a PHI de-identification layer before any external API call. If HIPAA-eligible API tiers are available, migrate to those. Log all PHI transmitted to third parties.
**Timeline:** 4 weeks (BAA negotiation may extend).

### Priority 4: Complete Audit Trail Coverage
**Risk:** Background workers, Neo4j graph queries, Kafka stream processors, and service-to-service calls currently operate without audit logging. This creates blind spots that would be flagged in any HIPAA audit.
**Action:** Instrument RQ workers with audit logging. Add audit hooks to Neo4j query service. Capture purpose-of-use in all audit entries. Segregate audit logs from PHI database. Implement tamper-evident audit storage.
**Timeline:** 4 weeks.

### Priority 5: Implement Multi-Factor Authentication and Account Security Controls
**Risk:** Single-factor authentication (password only) for admin and clinical users does not meet HIPAA best practices or enterprise customer expectations. No account lockout means brute-force attacks are feasible.
**Action:** Implement TOTP-based MFA for admin and provider roles. Add account lockout after 5 failed attempts with progressive backoff. Enforce password complexity requirements (12+ characters, mixed case, numbers, special characters). Add password history to prevent reuse.
**Timeline:** 6 weeks.

---

## 10. Compliance Strengths (Credit Where Due)

The development team has built a stronger compliance foundation than is typical at this stage. Items worth recognizing:

1. **Security-aware development culture.** VP-Security tagged commits show security was considered during development, not bolted on after.
2. **RBAC architecture is production-grade.** The permission model with resource:action granularity, bounded caching, and system role protection is well-designed.
3. **Audit service design is HIPAA-aware.** PHI pattern detection, HIPAA-format export, purpose-of-use support in TEFCA -- these show domain knowledge.
4. **SSRF protection on FHIR endpoints.** Private IP blocking, hostname validation, and configurable allowlists demonstrate security engineering.
5. **Security headers middleware is comprehensive.** OWASP-aligned headers with appropriate production/development gates.
6. **Insecure default detection in configuration.** The `_INSECURE_DEFAULTS` set and validation logic in `config.py` is a smart defensive measure.
7. **Token rotation on refresh.** Refresh token revocation with rotation is a solid security practice.

---

## Appendix A: Files Reviewed

| File | Purpose |
|---|---|
| `CAPABILITY_INVENTORY.md` | System capability baseline |
| `docker-compose.yml` | Infrastructure deployment configuration |
| `backend/app/core/config.py` | Application configuration and secrets handling |
| `backend/app/core/security.py` | API key authentication and tenant context |
| `backend/app/core/tenant.py` | Multi-tenant patient isolation |
| `backend/app/api/auth.py` | Authentication API endpoints |
| `backend/app/api/fhir.py` | FHIR data exchange endpoints |
| `backend/app/api/tefca.py` | TEFCA health information exchange |
| `backend/app/services/rbac_service.py` | Role-based access control |
| `backend/app/services/audit_service.py` | HIPAA audit trail logging |
| `backend/app/api/middleware/auth_middleware.py` | JWT authentication middleware |
| `backend/app/api/middleware/security_headers.py` | Security response headers |
| `backend/app/api/middleware/audit_middleware.py` | Automatic request audit logging |
| `backend/app/api/middleware/rate_limit.py` | API rate limiting |
| `backend/app/models/rbac.py` | User and role data models |

## Appendix B: Regulatory Reference Framework

- HIPAA Security Rule: 45 CFR Part 164, Subpart C
- HIPAA Privacy Rule: 45 CFR Part 164, Subpart E
- HITECH Act: Breach notification requirements
- 21 CFR Part 820: FDA Quality System Regulation
- IEC 62304: Medical device software lifecycle
- ISO 14971: Application of risk management to medical devices
- ONC Cures Act Final Rule: 85 FR 25642
- NIST Cybersecurity Framework v2.0
- CIS Docker Benchmark v1.6
- OWASP API Security Top 10 (2023)
- SOC 2 Type II: Trust Service Criteria (AICPA)
- HITRUST CSF v11

---

*This assessment is based on static code review and configuration analysis. A full compliance audit would include dynamic testing, penetration testing, architecture review sessions, and organizational policy review. Findings in this document should be validated with the engineering team and prioritized through the organization's risk management process.*
