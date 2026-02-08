# Security Hardening Research: Clinical Data Normalization Pipeline

> Research Date: 2026-02-08
> Scope: Healthcare SaaS security hardening across CISO, Data Engineering, DevSecOps, and Pen Testing perspectives
> Stack: FastAPI (Python 3.13) + Next.js App Router + PostgreSQL + Redis + Neo4j + Docker Compose + nginx

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [CISO / Security Architect Perspective](#2-ciso--security-architect-perspective)
3. [Data Engineer Perspective](#3-data-engineer-perspective)
4. [DevSecOps Perspective](#4-devsecops-perspective)
5. [Pen Testing Perspective](#5-pen-testing-perspective)
6. [Current State Assessment](#6-current-state-assessment)
7. [Prioritized Action Items](#7-prioritized-action-items)

---

## 1. Executive Summary

Healthcare data pipelines are high-value targets. In 2024-2025, healthcare experienced more reported cyberthreats than any other sector, with 275M+ records exposed. Medical records are worth approximately 10x more than credit card data on dark markets. The attack surface for a clinical data normalization pipeline that ingests FHIR data, runs NLP extraction, maps to OMOP, and serves a knowledge graph is substantial.

This report synthesizes security hardening patterns across four perspectives, mapped to our specific stack (Metriport webhooks -> FHIR import -> NLP extraction -> OMOP mapping -> knowledge graph -> trial matching). Each section includes specific, actionable items with priority ratings.

### Key Regulatory Context

The 2025 HIPAA Security Rule NPRM (published Federal Register Jan 6, 2025) proposes the first major update since 2013:
- Elimination of "addressable" vs "required" distinction -- all safeguards become mandatory
- Encryption of ePHI at rest and in transit required (limited exceptions)
- Business associate verification every 12 months with written certification
- 24-hour security incident reporting requirement
- Expected finalization in 2026

---

## 2. CISO / Security Architect Perspective

### 2.1 Compliance Frameworks Mapping

| Framework | Relevance | Key Controls for Our Pipeline |
|-----------|-----------|-------------------------------|
| HIPAA Security Rule (2026 update) | Mandatory | Encryption at rest/in transit, access controls, audit logging, incident response within 24h |
| SOC 2 Type II | Expected by enterprise customers | Trust Services Criteria: Security, Availability, Processing Integrity, Confidentiality, Privacy |
| HITRUST CSF r2 | Required by 80%+ of hospitals/health systems | 200-800 controls depending on scope; prescriptive tasks; 2-year certification cycle |
| FedRAMP | If selling to federal health agencies | NIST 800-53 controls; authorization boundary documentation |

**Recommendation**: Start with SOC 2 Type II (faster, less expensive), then pursue HITRUST CSF r2 for healthcare market access. Over 80% of hospitals require HITRUST from vendors.

### 2.2 Attack Surface Analysis for Our Data Flow

```
Metriport Webhooks --> FHIR Import --> NLP Extraction --> OMOP Mapping --> KG Build --> Trial Match UI
     |                    |                |                  |               |              |
  Webhook HMAC     Schema validation   Injection via      Mapping logic    Graph query    XSS via
  verification     SSRF prevention     clinical text      integrity        injection      patient data
  TLS only         Input sanitization  PHI in memory      Audit trail      Access control Display encoding
```

#### Critical Control Points

1. **Metriport Webhook Ingress**
   - HMAC signature verification on every webhook payload (constant-time comparison)
   - Timestamp window validation (reject payloads older than 5 minutes)
   - IP allowlisting for Metriport's known egress IPs
   - TLS 1.2+ only; pin Metriport's certificate if possible
   - Rate limiting at ingress (nginx + application level)
   - Webhook secret rotation schedule (quarterly minimum)

2. **FHIR Data Import**
   - Validate every FHIR resource against profiles (US Core, FHIR R4)
   - SSRF prevention: block private IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x, fd00::/8)
   - Schema enforcement before any processing
   - Reject resources that fail structural validation (cardinality, required fields, value domains)
   - Digital signature verification on FHIR Bundles when available

3. **Authentication and Authorization**
   - Migrate from cookie-based auth to OAuth 2.0 / OIDC with JWT access tokens
   - Implement SMART on FHIR authorization for any external app integrations
   - Role-Based Access Control (RBAC) at minimum; consider Attribute-Based (ABAC) for fine-grained PHI access
   - Enforce principle of least privilege on all API endpoints
   - Session management: HttpOnly, Secure, SameSite=Strict cookies; 30-minute idle timeout; session ID regeneration on privilege change

4. **API Security**
   - OAuth 2.0 with scoped access tokens per SMART on FHIR
   - Rate limiting per-user and per-IP (differentiate by endpoint sensitivity)
   - Request size limits (especially for document/FHIR bundle upload endpoints)
   - API versioning with deprecation lifecycle
   - Comprehensive audit logging on all PHI access (who, what, when, from where)

### 2.3 SMART on FHIR Security Requirements

For CDS Hooks and external app integrations:
- Each CDS service must have its own OAuth client ID
- CDS services should have the same access privileges as the current practitioner (not elevated)
- Access tokens must be scoped (e.g., read Patient, read Condition -- not blanket FHIR resource access)
- Authorization codes must be exchanged over TLS only
- Generate unpredictable `state` parameter per user session to prevent replay attacks

### 2.4 Encryption Requirements

| Data State | Current | Required |
|------------|---------|----------|
| In transit (external) | TLS configuration exists but commented out in nginx | TLS 1.2+ mandatory; HSTS enabled; strong cipher suites only |
| In transit (internal) | Plaintext between services | mTLS between all service containers; encrypted Redis connections |
| At rest (PostgreSQL) | No column-level encryption | Transparent Data Encryption (TDE) or column-level encryption for PHI fields |
| At rest (Redis) | No encryption | Redis 7+ TLS; encrypt cached PHI |
| At rest (Neo4j) | No encryption | Neo4j Enterprise TDE; encrypted backups |
| At rest (volumes) | Docker volumes unencrypted | LUKS or dm-crypt on host volume mounts |

### 2.5 Audit and Monitoring

- Implement immutable audit logs for all PHI access (read/write/delete)
- Log structure: timestamp, user_id, resource_type, resource_id, action, source_ip, user_agent
- Ship logs to SIEM (Splunk, Elastic, or cloud-native) with tamper-evident storage
- Alert on: bulk PHI access, after-hours access, access from unusual IPs, failed auth attempts > threshold
- Retain audit logs for minimum 6 years (HIPAA requirement)
- Data lineage tracking: every clinical fact should be traceable back to source document

---

## 3. Data Engineer Perspective

### 3.1 Pipeline Security Architecture

The clinical data normalization pipeline (FHIR -> NLP -> OMOP -> KG) has PHI flowing through every stage. Each stage needs specific hardening.

#### Stage 1: FHIR Ingestion

**Schema Enforcement**
- Validate every incoming FHIR resource against FHIR R4 schema + US Core profiles
- Use HAPI FHIR validator or fhir.resources Python library for structural validation
- Reject malformed resources with detailed error logging (but never log PHI in error messages)
- Enforce cardinality constraints, required fields, and value domain checks
- Validate CodeableConcept bindings against known terminology servers

**Data Quality Gates**
- Implement a quarantine queue for resources that fail validation
- Automated outlier detection for vital signs, lab results, medication dosages
- Flag blood pressure readings outside 40/20 - 300/200, heart rates outside 20-300 BPM, etc.
- Provenance tracking: record source system, timestamp, transport metadata for every resource

#### Stage 2: NLP Extraction

**PHI Handling During Processing**
- Process clinical text in memory-isolated workers (separate container/process)
- Never write raw clinical text to log files
- Implement PHI detection scanning (regex + ML-based) before any external API calls
- If using LLMs for extraction: sanitize/de-identify clinical text before sending to external LLM providers
- Enforce memory limits on NLP workers to prevent PHI from persisting in swap

**Input Sanitization**
- Clinical text can contain malicious content (embedded scripts, SQL fragments)
- Strip HTML/JavaScript from all text fields before NLP processing
- Validate character encoding (reject non-UTF-8 or mixed encoding)
- Implement maximum text length limits per field type

#### Stage 3: OMOP Mapping

**Mapping Integrity**
- Version-control all mapping tables and concept dictionaries
- Implement checksums on mapping table updates
- Audit trail for every mapping decision (source concept -> target OMOP concept_id + confidence + method)
- Separate mapping validation stage that compares outputs against known-good reference sets
- Prevent unauthorized modification of mapping rules

**Data Lineage**
- Every ClinicalFact must carry full provenance chain: source_document -> mention -> mapping_candidates -> selected_mapping -> fact
- Implement data lineage graph (can leverage Neo4j for this)
- Support "explain this fact" queries that trace back to source text with offsets

#### Stage 4: Knowledge Graph Construction

**Graph Security**
- Access control on graph queries (role-based: clinician sees patient data, researcher sees de-identified)
- Query complexity limits to prevent resource exhaustion (max depth, max expansion, timeout)
- Input validation on Cypher queries -- never interpolate user input into Cypher strings
- Parameterized queries only for Neo4j
- Rate limit graph traversal queries

### 3.2 PHI Detection and Masking

Implement a three-layer PHI detection strategy:

1. **Rule-based detection** (fast, high precision): Regex patterns for SSN, MRN, phone numbers, email addresses, dates of birth, ZIP codes
2. **NER-based detection** (medium speed, high recall): Use clinical NER models (e.g., John Snow Labs Spark NLP for Healthcare, or Presidio) to detect patient names, provider names, locations, organizations
3. **Contextual detection** (slower, catches edge cases): ML classifier trained on clinical text to identify PHI in context (e.g., "Dr. Smith" vs "Smith fracture")

**Masking Strategies by Use Case**
| Use Case | Strategy |
|----------|----------|
| Analytics/research | Safe Harbor de-identification (remove 18 HIPAA identifiers) |
| Development/testing | Synthetic data generation (no real PHI in non-prod) |
| Audit/compliance | Tokenization (reversible with proper authorization) |
| Display in UI | Minimum necessary: show only PHI required for the user's role |

### 3.3 Data Validation Framework

Implement validation at system boundaries:

```
Input Validation (Pydantic v2 schemas)
  -> FHIR Profile Validation (structural + terminological)
    -> Business Rule Validation (clinical plausibility checks)
      -> Cross-Reference Validation (consistency across resources in a bundle)
        -> Output Validation (verify transformed data matches expected schema)
```

Specific validations for clinical trial matching:
- Patient age calculation must use exact birth date, not approximation
- Diagnosis codes must be validated against ICD-10 and SNOMED CT hierarchies
- Lab results must include units and reference ranges for eligibility comparison
- Medication lists must be normalized to RxNorm for interaction checking

---

## 4. DevSecOps Perspective

### 4.1 Container Security

#### Docker Image Hardening

**Current Issues Observed (from docker-compose.yml analysis)**
- Hardcoded credentials: `POSTGRES_PASSWORD: postgres`, `NEO4J_AUTH: neo4j/password`
- Neo4j password mismatch: docker-compose sets `neo4j/password` but backend env uses `clinical123`
- All service ports exposed to host (PostgreSQL 15432, Redis 16379, Neo4j 7474/7687, Kafka 9092/29092)
- Source code mounted as volume in backend container (`./backend:/app`)
- `AUTH_BYPASS_DEV: true` and `AUTH_ENABLED: false` as defaults
- Default API key: `dev-api-key-change-in-production`

**Required Hardening**
1. Use multi-stage Docker builds with minimal base images (distroless or Alpine)
2. Run containers as non-root user (add `USER nonroot` in Dockerfiles)
3. Set read-only root filesystem where possible (`read_only: true`)
4. Drop all Linux capabilities and add back only what is needed (`cap_drop: ALL`, `cap_add: [NET_BIND_SERVICE]`)
5. Use Docker Content Trust for image signing
6. Pin image digests (not just tags) for reproducible builds
7. Scan images with Trivy or Grype in CI before push to registry

#### Network Segmentation

Implement Docker network isolation:

```yaml
networks:
  frontend-net:     # frontend <-> nginx only
  backend-net:      # nginx <-> backend
  data-net:         # backend <-> postgres, redis, neo4j (NEVER exposed to frontend)
  queue-net:        # backend <-> kafka, worker
```

**Rules**
- Frontend container must NEVER have direct access to database containers
- Database ports must NOT be exposed to host in production
- Inter-service communication uses internal Docker DNS only
- External access only through nginx reverse proxy

### 4.2 Dependency Scanning

#### Python (Backend)

| Tool | Purpose | Integration Point |
|------|---------|-------------------|
| Bandit | SAST - finds common Python security issues (hardcoded passwords, SQL injection, unsafe deserialization) | CI pipeline, pre-commit hook |
| Safety / pip-audit | Known vulnerability scanning against PyPI advisories and safety-db | CI pipeline, weekly scheduled scan |
| Semgrep | Advanced SAST with healthcare-specific rules | CI pipeline |
| Trivy | Container + dependency scanning | CI pipeline, registry scanning |

**Python-Specific Checks**
- Audit all `subprocess` calls, `os.system`, unsafe deserialization usage
- Check for SSRF patterns in `httpx`, `aiohttp`, `requests` usage
- Validate all SQLAlchemy queries use parameterized binding (no f-string interpolation)
- Scan for hardcoded secrets (API keys, passwords, tokens)

#### TypeScript/JavaScript (Frontend)

| Tool | Purpose | Integration Point |
|------|---------|-------------------|
| npm audit / yarn audit | Known vulnerability scanning | CI pipeline, pre-commit |
| ESLint security plugin | Static analysis for XSS, injection | CI pipeline |
| Snyk | Dependency + SAST scanning | CI pipeline, PR checks |
| Socket.dev | Supply chain attack detection | CI pipeline |

### 4.3 Secret Management

**Current State**: Environment variables in docker-compose.yml with hardcoded defaults.

**Target State**: External secret management with rotation.

**Recommended Path** (staged):

1. **Immediate**: Remove all hardcoded credentials from docker-compose.yml; use `.env` file (git-ignored) with a `.env.example` template
2. **Short-term**: Docker Secrets for Docker Swarm deployments; SOPS or age for encrypting env files at rest
3. **Medium-term**: HashiCorp Vault or AWS Secrets Manager
   - Dynamic database credentials (Vault generates short-lived PostgreSQL credentials)
   - Automatic rotation for API keys, webhook secrets, JWT signing keys
   - Audit trail for all secret access
4. **Production requirement**: No secret should have a lifetime > 90 days without rotation

**Secrets Inventory for This Stack**
| Secret | Current Location | Risk |
|--------|-----------------|------|
| PostgreSQL password | docker-compose.yml hardcoded | CRITICAL |
| Neo4j password | docker-compose.yml hardcoded (mismatched) | CRITICAL |
| Redis password | None configured | HIGH |
| API key | docker-compose.yml with insecure default | CRITICAL |
| JWT secret key | Not set (None) | CRITICAL when auth enabled |
| Metriport API key | Environment variable | MEDIUM (correctly externalized) |
| Metriport webhook signing key | Environment variable | MEDIUM |
| Anthropic API key | Environment variable | MEDIUM |
| ETL encryption key | Not set (None) | HIGH - new key per restart loses data |
| UMLS API key | Environment variable | MEDIUM |

### 4.4 CI/CD Security Pipeline

```
Code Commit
  -> Pre-commit hooks: ruff (lint), bandit (SAST), detect-secrets
  -> PR Check: Trivy (container scan), pip-audit (dependency), npm audit, Semgrep (SAST)
  -> Build: Multi-stage Docker build, image signing
  -> Pre-deploy: DAST scan (OWASP ZAP) against staging
  -> Deploy: Immutable infrastructure, no SSH access to production
  -> Post-deploy: Runtime security monitoring (Falco), dependency update bot (Dependabot/Renovate)
```

### 4.5 Infrastructure Hardening

#### nginx Hardening (Current Gaps)

Current nginx.conf observations:
- HTTPS/TLS configuration commented out
- CORS set to `Access-Control-Allow-Origin: *` (allows any origin)
- Missing: Content-Security-Policy header
- Missing: Strict-Transport-Security (HSTS) header
- Missing: Permissions-Policy header
- X-XSS-Protection is deprecated (CSP replaces it)
- No ModSecurity WAF integration
- No request body size limits
- WebSocket endpoint has no authentication or origin validation

**Required nginx Hardening**
1. Enable TLS 1.2+ with modern cipher suites; disable TLS 1.0/1.1
2. Enable HSTS with `max-age=31536000; includeSubDomains; preload`
3. Add Content-Security-Policy with strict nonce-based policy
4. Replace `Access-Control-Allow-Origin: *` with explicit origin allowlist matching `cors_origins` config
5. Add `client_max_body_size` limits (e.g., 10MB for document upload, 1MB for API)
6. Add ModSecurity with OWASP Core Rule Set (CRS)
7. Add request body inspection and filtering
8. Rate limit login/auth endpoints more aggressively (5 req/min)

#### Database Hardening

**PostgreSQL**
- Enable SSL connections (`ssl = on` in postgresql.conf)
- Use scram-sha-256 authentication (not md5)
- Create dedicated database users per service with minimum required privileges
- Enable `pgaudit` extension for query auditing
- Set `log_connections = on`, `log_disconnections = on`
- Configure row-level security (RLS) for multi-tenant PHI isolation
- Regular backup encryption with separate key management

**Redis**
- Enable Redis AUTH with strong password (`requirepass`)
- Enable TLS (Redis 7+ supports native TLS)
- Disable dangerous commands: `FLUSHDB`, `FLUSHALL`, `DEBUG`, `CONFIG` in production
- Set `maxmemory-policy` to prevent unbounded growth
- Bind to internal network interface only

**Neo4j**
- Enable authentication (already configured but with weak password)
- Configure SSL/TLS for bolt connections
- Use fine-grained access control (Neo4j Enterprise)
- Disable remote procedure calls that allow file system access
- Set query timeout limits to prevent resource exhaustion
- Disable browser access (port 7474) in production

---

## 5. Pen Testing Perspective

### 5.1 OWASP API Security Top 10 Applied to Our Stack

| # | OWASP API Risk | How It Applies to Our System | Specific Attack Scenario |
|---|----------------|------------------------------|--------------------------|
| API1 | Broken Object Level Authorization (BOLA) | Patient data endpoints: `/api/v1/patients/{id}`, FHIR resources | Attacker enumerates patient IDs to access other patients' clinical data |
| API2 | Broken Authentication | Cookie-based auth with `AUTH_BYPASS_DEV=true` default | Auth bypass reaching production; session fixation on cookie auth |
| API3 | Broken Object Property Level Authorization | FHIR resource updates may expose/modify fields beyond user's scope | Attacker modifies `Patient.identifier` or `Observation.value` via partial update |
| API4 | Unrestricted Resource Consumption | Document upload, FHIR bundle import, NLP processing, graph queries | Upload massive FHIR bundle to exhaust memory; trigger recursive graph traversal |
| API5 | Broken Function Level Authorization | Admin endpoints, ETL configuration, mapping table management | Regular user accessing admin mapping configuration endpoints |
| API6 | Unrestricted Access to Sensitive Business Flows | Trial matching, screening pipeline, patient enrollment | Automated enumeration of trial eligibility criteria to identify patient cohorts |
| API7 | Server Side Request Forgery (SSRF) | FHIR server fetch, webhook configuration, document URL import | Configure webhook URL pointing to internal metadata service (169.254.169.254) |
| API8 | Security Misconfiguration | Default credentials, debug mode, permissive CORS, exposed ports | `AUTH_BYPASS_DEV=true` in production; `DEBUG=true` exposing stack traces |
| API9 | Improper Inventory Management | 726 endpoints, maturity tiers (Production/Pilot/Scaffold) | Scaffold endpoints accessible in production without proper auth |
| API10 | Unsafe Consumption of APIs | Metriport webhook data, external FHIR servers, LLM API responses | Malicious FHIR server returns crafted payload that exploits NLP pipeline |

### 5.2 SQL Injection Through Clinical Text

**Attack Vector**: Clinical notes contain free-text that flows through NLP extraction, concept mapping, and storage. If any stage interpolates this text into SQL queries, injection is possible.

**Specific Scenarios**
1. Patient name containing SQL: `Robert'); DROP TABLE patients;--` stored in FHIR Patient resource
2. Clinical note text with embedded SQL fragments passing through NLP and being stored
3. Search queries on clinical text fields using LIKE with unescaped user input
4. Concept mapping tables where source terms are used in dynamic queries

**Mitigations**
- SQLAlchemy ORM with parameterized queries (already in use -- verify no raw SQL string formatting)
- Pydantic v2 input validation on all API endpoints
- Grep entire codebase for `f"SELECT`, `f"INSERT`, `f"UPDATE`, `f"DELETE`, `.format(` in SQL context
- Implement prepared statements for any raw SQL queries
- Database user permissions: application user should not have DDL privileges

### 5.3 XSS Through Patient Data in UI

**Attack Vector**: Patient names, clinical notes, diagnostic reports, and other clinical data displayed in the Next.js frontend could contain malicious scripts.

**Specific Scenarios**
1. Patient name field containing script tags that execute on render
2. Clinical note containing embedded HTML/JavaScript rendered in knowledge graph display
3. FHIR Narrative (`resource.text.div`) containing XSS payloads -- FHIR narratives are XHTML by spec
4. Diagnostic report text with event handlers in image tags

**Mitigations**
1. React/Next.js auto-escapes JSX expressions by default -- but React's raw HTML insertion bypasses this
2. Grep codebase for all raw HTML rendering patterns -- every usage needs manual review
3. Sanitize FHIR Narrative content with DOMPurify before rendering
4. Implement Content-Security-Policy header with strict nonce-based script policy
5. Never use `Function()` constructor or direct DOM innerHTML assignment with clinical data
6. TypeScript strict mode + ESLint security rules to catch unsafe patterns

### 5.4 WebSocket Security

**Attack Vector**: WebSocket endpoints (`/api/ws`) may lack the same auth and validation as REST endpoints.

**Specific Scenarios**
1. Cross-Site WebSocket Hijacking (CSWSH): attacker's page connects to ws endpoint using victim's cookies
2. Message injection: malicious data in WebSocket messages that gets processed/stored without validation
3. Denial of service: flooding WebSocket with messages to exhaust server resources
4. Unauthorized subscription to real-time patient data updates

**Mitigations**
- Validate Origin header on WebSocket handshake (reject unknown origins)
- Require authentication token in WebSocket connection (not just cookies)
- Validate and sanitize every WebSocket message using JSON schema
- Implement per-connection message rate limiting (e.g., 10 msg/sec)
- Set maximum message size (64KB)
- Use `wss://` only (no unencrypted WebSocket)
- Authorization check per message/subscription, not just at connection time

### 5.5 Metriport Webhook Attack Surface

**Attack Scenarios**
1. Webhook replay: attacker captures and replays a valid webhook payload
2. Webhook forgery: attacker sends crafted FHIR bundles without valid HMAC
3. Timing attack on HMAC verification: non-constant-time comparison leaks secret bytes
4. Webhook flood: attacker triggers massive webhook deliveries to overwhelm processing

**Mitigations**
- HMAC verification with constant-time comparison (`hmac.compare_digest`)
- Timestamp validation: reject webhooks with timestamp > 5 minutes old
- Idempotency: track webhook delivery IDs and reject duplicates
- Rate limiting on webhook endpoint (separate from general API rate limit)
- IP allowlisting for Metriport's egress IPs
- Queue incoming webhooks for async processing (prevent synchronous overload)

### 5.6 Clinical NLP Pipeline Adversarial Attacks

**Attack Vector**: Adversarial inputs in clinical text can manipulate NLP model outputs.

Research shows:
- Minor changes to clinical text (preserving meaning) can force NLP systems to make erroneous decisions
- Targeted manipulation of just 1.1% of model weights can inject incorrect biomedical facts
- Prompt injection attacks on medical LLMs can alter diagnosis, medication, and treatment recommendations

**Mitigations**
1. Ensemble approach: use multiple NLP models and compare outputs (already in architecture)
2. Confidence thresholds: flag low-confidence extractions for human review
3. Input validation: detect anomalous character patterns that may indicate adversarial manipulation
4. Output validation: cross-reference NLP outputs against known clinical ontologies
5. Monitoring: alert on sudden shifts in extraction pattern distributions
6. For LLM-based extraction: implement output guardrails that validate against medical ontologies

---

## 6. Current State Assessment

Based on analysis of `docker-compose.yml`, `nginx.conf`, `backend/app/core/config.py`, and `backend/app/core/auth.py`:

### Strengths (Already Implemented)
- Pydantic v2 settings with validation (VP-Security-3)
- Insecure default detection in config (rejects known bad passwords)
- Production environment validation (requires JWT_SECRET_KEY, API_KEY)
- CORS origin validation (requires absolute URLs, no wildcards in config)
- SSRF prevention framework (allowed_fhir_servers config, private IP blocking)
- Metriport webhook signing key support
- Auth bypass clearly flagged as dev-only
- Health check endpoints on all services
- Rate limiting zones configured in nginx

### Critical Gaps
| Gap | Severity | Location |
|-----|----------|----------|
| Hardcoded PostgreSQL credentials in docker-compose | CRITICAL | `docker-compose.yml:14` |
| Hardcoded Neo4j credentials in docker-compose | CRITICAL | `docker-compose.yml:48` |
| Neo4j password mismatch (docker vs backend env) | HIGH | `docker-compose.yml:48` vs `:123` |
| Redis has no authentication | HIGH | `docker-compose.yml:29` |
| TLS/HTTPS disabled (commented out) | CRITICAL | `nginx.conf:69-80` |
| CORS `Access-Control-Allow-Origin: *` in nginx | CRITICAL | `nginx.conf:113` |
| No Content-Security-Policy header | HIGH | `nginx.conf:82-86` |
| No HSTS header | HIGH | `nginx.conf` |
| All database ports exposed to host | HIGH | `docker-compose.yml` |
| Source code volume-mounted in production compose | HIGH | `docker-compose.yml:143` |
| `AUTH_BYPASS_DEV=true` as default | CRITICAL | `docker-compose.yml:126` |
| `AUTH_ENABLED=false` as default | HIGH | `docker-compose.yml:127` |
| `DEBUG=true` as default | HIGH | `docker-compose.yml:125` |
| No WAF (ModSecurity) on nginx | MEDIUM | `nginx.conf` |
| No request body size limits | MEDIUM | `nginx.conf` |
| Kafka listeners on plaintext | MEDIUM | `docker-compose.yml:93` |
| No container user restrictions (running as root) | HIGH | `docker-compose.yml` |
| No Docker network segmentation | HIGH | `docker-compose.yml` |
| WebSocket endpoint has no origin validation | HIGH | `nginx.conf:119-127` |
| No SAST/DAST in CI pipeline | HIGH | Not configured |
| No dependency scanning automation | HIGH | Not configured |
| ETL encryption key not set (regenerated per restart) | HIGH | `config.py:163` |

---

## 7. Prioritized Action Items

### P0 -- Must Fix Before Any Production/Pilot Deployment

| # | Action | Perspective | Effort |
|---|--------|-------------|--------|
| 1 | Remove all hardcoded credentials from docker-compose; use .env with .env.example template | DevSecOps | 2h |
| 2 | Enable TLS/HTTPS in nginx; enforce TLS 1.2+ with modern ciphers | CISO | 4h |
| 3 | Add HSTS, CSP, Permissions-Policy headers to nginx | DevSecOps | 2h |
| 4 | Replace `Access-Control-Allow-Origin: *` with explicit origin allowlist | CISO | 1h |
| 5 | Set `AUTH_ENABLED=true`, `AUTH_BYPASS_DEV=false`, `DEBUG=false` as production defaults | CISO | 1h |
| 6 | Enable Redis AUTH with strong password | DevSecOps | 1h |
| 7 | Fix Neo4j password mismatch between docker-compose and backend config | DevSecOps | 30m |
| 8 | Remove host port exposure for databases in production compose | DevSecOps | 1h |
| 9 | Implement Docker network segmentation (frontend/backend/data/queue networks) | DevSecOps | 4h |
| 10 | Add Metriport webhook HMAC verification with constant-time comparison | PenTest | 4h |
| 11 | Enable PostgreSQL SSL and switch to scram-sha-256 auth | DevSecOps | 2h |

### P1 -- Required Within 30 Days of Production

| # | Action | Perspective | Effort |
|---|--------|-------------|--------|
| 12 | Implement comprehensive audit logging for all PHI access | CISO | 2-3 days |
| 13 | Add Bandit + pip-audit + npm audit to CI pipeline | DevSecOps | 1 day |
| 14 | Add Trivy container scanning to CI pipeline | DevSecOps | 4h |
| 15 | Implement FHIR resource validation against US Core profiles | DataEng | 2-3 days |
| 16 | Run containers as non-root users | DevSecOps | 1 day |
| 17 | Add request body size limits to nginx (10MB upload, 1MB API) | DevSecOps | 1h |
| 18 | Sanitize FHIR Narrative content before UI rendering (DOMPurify) | PenTest | 1 day |
| 19 | Audit codebase for raw HTML rendering patterns and raw SQL interpolation | PenTest | 1 day |
| 20 | Implement session management hardening (idle timeout, regeneration, secure cookie flags) | PenTest | 1 day |
| 21 | Add WebSocket origin validation and per-message auth | PenTest | 1 day |
| 22 | Set ETL encryption key as required config for production | CISO | 1h |
| 23 | Implement data lineage tracking for clinical facts | DataEng | 3-5 days |

### P2 -- Required Within 90 Days

| # | Action | Perspective | Effort |
|---|--------|-------------|--------|
| 24 | Deploy ModSecurity WAF with OWASP Core Rule Set | DevSecOps | 2-3 days |
| 25 | Implement PHI detection scanning (rule-based + NER) in NLP pipeline | DataEng | 1-2 weeks |
| 26 | Migrate to external secret management (Vault or cloud-native) | DevSecOps | 1-2 weeks |
| 27 | Implement mTLS between internal services | DevSecOps | 1 week |
| 28 | Add DAST scanning (OWASP ZAP) to CI/CD for staging deployments | DevSecOps | 3-5 days |
| 29 | Implement RBAC with fine-grained permissions on all 726 endpoints | CISO | 2-3 weeks |
| 30 | Add NLP output validation against clinical ontologies | DataEng | 1 week |
| 31 | Implement API maturity labeling (block Scaffold endpoints in production) | CISO | 1 week |
| 32 | Enable pgaudit for PostgreSQL query auditing | CISO | 2 days |
| 33 | Implement column-level encryption for PHI fields in PostgreSQL | DataEng | 1-2 weeks |
| 34 | Set up Kafka TLS and SASL authentication | DevSecOps | 2-3 days |
| 35 | Create separate docker-compose.prod.yml with all hardening applied | DevSecOps | 2-3 days |

### P3 -- Required for SOC 2 / HITRUST Readiness

| # | Action | Perspective | Effort |
|---|--------|-------------|--------|
| 36 | SOC 2 Type II readiness assessment and gap analysis | CISO | 2-4 weeks |
| 37 | Implement formal incident response plan and runbook | CISO | 1-2 weeks |
| 38 | Deploy runtime security monitoring (Falco or equivalent) | DevSecOps | 1 week |
| 39 | Implement automated secret rotation (quarterly minimum) | DevSecOps | 1-2 weeks |
| 40 | Third-party penetration test by healthcare-specialized firm | PenTest | Contracted |
| 41 | Implement de-identification pipeline for research/analytics data | DataEng | 2-4 weeks |
| 42 | Create BAA (Business Associate Agreement) template | CISO | Legal review |
| 43 | Deploy SIEM with healthcare-specific alert rules | CISO | 2-4 weeks |
| 44 | Begin HITRUST CSF r2 assessment process | CISO | 6-12 months |
| 45 | Implement synthetic data generation for non-production environments | DataEng | 2-3 weeks |

---

## Sources

### HIPAA and Compliance
- [2026 HIPAA Rule Updates - Chess Health Solutions](https://www.chesshealthsolutions.com/2025/11/06/2026-hipaa-rule-updates-what-healthcare-providers-administrators-and-compliance-officers-need-to-know/)
- [HIPAA Security Rule NPRM Fact Sheet - HHS.gov](https://www.hhs.gov/hipaa/for-professionals/security/hipaa-security-rule-nprm/factsheet/index.html)
- [HIPAA Security Rule Federal Register](https://www.federalregister.gov/documents/2025/01/06/2024-30983/hipaa-security-rule-to-strengthen-the-cybersecurity-of-electronic-protected-health-information)
- [2026 HIPAA Changes - HIPAA Vault](https://www.hipaavault.com/resources/2026-hipaa-changes/)
- [HITRUST vs SOC 2 - Cloudticity](https://blog.cloudticity.com/hitrust-vs-soc2-compliance-for-healthcare-data-comparison)
- [HITRUST vs SOC 2 - Bright Defense](https://www.brightdefense.com/resources/hitrust-vs-soc-2/)

### FHIR and API Security
- [FHIR Security Best Practices - Kodjin](https://kodjin.com/blog/fhir-security-best-practices/)
- [FHIR Security - HL7 v6.0.0](https://build.fhir.org/security.html)
- [FHIR and APIs: Building Secure Healthcare Systems - Censinet](https://censinet.com/perspectives/fhir-apis-building-secure-healthcare-systems)
- [HIPAA-Compliant FHIR API Security - SCIMUS](https://thescimus.com/blog/how-to-build-a-hipaa-compliant-fhir-api-security-best-practices/)
- [SMART on FHIR Introduction - Smile CDR](https://smilecdr.com/docs/smart/smart_on_fhir_introduction.html)
- [SMART on FHIR: CDS Hooks and Coverage - IntuitionLabs](https://intuitionlabs.ai/articles/smart-on-fhir-cds-hooks-coverage-guide)

### Data Pipeline Security
- [Securing PII and PHI in ETL Pipelines - STX Next](https://www.stxnext.com/blog/safeguarding-personal-data)
- [Common Techniques to Detect PHI and PII - AWS](https://aws.amazon.com/blogs/industries/common-techniques-to-detect-phi-and-pii-data-using-aws-services/)
- [Healthcare Data De-Identification Strategies - Evoke Technologies](https://www.evoketechnologies.com/blog/solutions-healthcare-data-de-identification/)
- [FHIR Data Validation - HL7](https://build.fhir.org/validation)
- [FHIR Schema Validator - HAPI FHIR](https://hapifhir.io/hapi-fhir/docs/validation/schema_validator.html)

### Healthcare Breach Statistics
- [Healthcare Data Breaches 2025: 275M Records Exposed - DeepStrike](https://deepstrike.io/blog/healthcare-data-breaches-2025-statistics)
- [Healthcare Data Breach Statistics 2025 - Patient-Protect](https://www.patient-protect.com/post/healthcare-data-breach-statistics-2025-why-medical-records-are-worth-10-more-than-credit-cards)
- [Healthcare Data Breach Statistics 2026 - Bright Defense](https://www.brightdefense.com/resources/healthcare-data-breach-statistics/)
- [Healthcare Cyberthreats 2024 - AHA](https://www.aha.org/news/headline/2025-05-12-report-health-care-had-most-reported-cyberthreats-2024)

### Clinical AI Security
- [Zero Trust AI for Hospitals - John Snow Labs](https://www.johnsnowlabs.com/zero-trust-ai-why-hospitals-must-treat-llm-output-like-sensitive-infrastructure/)
- [Adversarial Attacks on Medical ML - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7657648/)
- [Adversarial Attacks on LLMs in Medicine - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11468488/)
- [Medical LLMs Susceptible to Targeted Misinformation - Nature](https://www.nature.com/articles/s41746-024-01282-7)

### DevSecOps and Container Security
- [FastAPI Security Guide - Escape.tech](https://escape.tech/blog/how-to-secure-fastapi-api/)
- [Bandit SAST for Python - GitHub](https://github.com/PyCQA/bandit)
- [DevSecOps Tools 2026 - Wiz](https://www.wiz.io/academy/application-security/devsecops-tools)
- [Container Security Best Practices - ActiveState](https://www.activestate.com/blog/container-security-best-practices-for-modern-devsecops-teams/)
- [Docker Secret Management - GitGuardian](https://blog.gitguardian.com/how-to-handle-secrets-in-docker/)
- [HashiCorp Vault - GitHub](https://github.com/hashicorp/vault)

### Web Application Security
- [OWASP API Security Top 10](https://owasp.org/API-Security/)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [WebSocket Security - OWASP](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html)
- [Next.js Content Security Policy - Vercel](https://nextjs.org/docs/app/guides/content-security-policy)
- [Next.js Security Checklist - Arcjet](https://blog.arcjet.com/next-js-security-checklist/)
- [nginx Security Hardening Guide - Linux Audit](https://linux-audit.com/web/nginx-security-configuration-hardening-guide/)
- [PostgreSQL Security Guide - Percona](https://www.percona.com/blog/postgresql-database-security-what-you-need-to-know/)
- [Neo4j Security Checklist](https://neo4j.com/docs/operations-manual/current/security/checklist/)

### Metriport
- [Metriport Quickstart](https://docs.metriport.com/medical-api/getting-started/quickstart)
- [Webhook Security Best Practices - Kusari](https://www.kusari.dev/learning-center/webhook-security)
