# Installation Qualification (IQ) Protocol

**Document ID:** IQ-CON-001
**Version:** 1.0
**Effective Date:** 2026-02-08
**System:** Clinical Ontology Normalizer (CON) - Clinical Trial Patient Recruitment Platform

---

## 1. Purpose

This Installation Qualification (IQ) protocol verifies that the Clinical Ontology Normalizer system has been installed correctly per design specifications. It confirms that all hardware, software, infrastructure components, and configurations are properly deployed and meet the documented requirements.

## 2. Scope

This IQ covers the following components:

- Backend services (FastAPI / Python)
- Frontend application (Next.js / TypeScript)
- Database systems (PostgreSQL, Redis, Neo4j)
- Infrastructure configuration (Docker, Kubernetes)
- Security baseline (TLS, Authentication, RBAC)
- Network connectivity (inter-service communication)

## 3. References

| Document | ID |
|---|---|
| System Requirements Specification | SRS-CON-001 |
| Architecture Design Document | ADD-CON-001 |
| Operational Qualification Protocol | OQ-CON-001 |
| Performance Qualification Protocol | PQ-CON-001 |
| CLAUDE.md (System Architecture) | N/A |

## 4. Responsibilities

| Role | Responsibility |
|---|---|
| QA Lead | Execute IQ test cases, document results |
| IT Operations | Provide infrastructure access, verify deployments |
| Validation Lead | Review and approve IQ results |
| Development Lead | Provide technical support during qualification |
| Quality Assurance Manager | Final sign-off |

---

## 5. IQ Protocol Sections

### 5.1 Hardware / Infrastructure Requirements Verification

Verify that all required infrastructure components are provisioned and accessible.

| Check ID | Component | Requirement | Expected Result |
|---|---|---|---|
| IQ-HW-001 | PostgreSQL Server | Version 14+ accessible on configured host:port | Connection successful, version >= 14 |
| IQ-HW-002 | Redis Server | Version 7+ accessible on configured host:port | PING returns PONG, version >= 7 |
| IQ-HW-003 | Neo4j Server | Version 5+ accessible (optional) | Connection successful or graceful degradation |
| IQ-HW-004 | Application Server | CPU >= 4 cores, RAM >= 8GB | Resource check passes |
| IQ-HW-005 | Disk Storage | >= 50GB available for data and logs | df -h shows sufficient space |
| IQ-HW-006 | Network Interfaces | All required ports open (8000, 5432, 6379, 7687) | Port connectivity verified |

### 5.2 Software Version Verification

Verify that all software dependencies match the specified versions.

| Check ID | Component | Required Version | Verification Method |
|---|---|---|---|
| IQ-SW-001 | Python | 3.13.x | `python --version` |
| IQ-SW-002 | Node.js | 20.x or 22.x LTS | `node --version` |
| IQ-SW-003 | FastAPI | Latest stable | `pip show fastapi` |
| IQ-SW-004 | SQLAlchemy | 2.x (async) | `pip show sqlalchemy` |
| IQ-SW-005 | Pydantic | 2.x | `pip show pydantic` |
| IQ-SW-006 | Next.js | 14.x or 15.x | `npm list next` |
| IQ-SW-007 | TypeScript | 5.x | `npm list typescript` |
| IQ-SW-008 | Docker Engine | 24+ | `docker --version` |
| IQ-SW-009 | Docker Compose | 2.x | `docker compose version` |

### 5.3 Configuration Verification

Verify that all environment variables and feature flags are correctly set.

| Check ID | Configuration | Requirement | Verification |
|---|---|---|---|
| IQ-CF-001 | DATABASE_URL | Valid PostgreSQL connection string | Parse and test connection |
| IQ-CF-002 | REDIS_URL | Valid Redis connection string | Parse and test connection |
| IQ-CF-003 | API_V1_PREFIX | Set to `/api/v1` | Config check |
| IQ-CF-004 | CORS_ORIGINS | Configured for deployment environment | Non-empty in production |
| IQ-CF-005 | SECRET_KEY | Set and >= 32 characters | Length check |
| IQ-CF-006 | ENVIRONMENT | Set to correct environment name | Value matches deployment |
| IQ-CF-007 | DEBUG | False in production/staging | Boolean check |
| IQ-CF-008 | LOG_LEVEL | Set appropriately (INFO for prod) | Config check |

### 5.4 Database Schema Verification

Verify that all database migrations have been applied and tables exist.

| Check ID | Check | Expected Result |
|---|---|---|
| IQ-DB-001 | Migration status | All migrations applied (alembic current == head) |
| IQ-DB-002 | Table count | >= 20 core tables present |
| IQ-DB-003 | Patient table | Exists with required columns |
| IQ-DB-004 | Document table | Exists with required columns |
| IQ-DB-005 | Mention table | Exists with required columns |
| IQ-DB-006 | ClinicalFact table | Exists with required columns |
| IQ-DB-007 | Trial table | Exists with required columns |
| IQ-DB-008 | Enrollment table | Exists with required columns |
| IQ-DB-009 | AuditLog table | Exists with required columns |
| IQ-DB-010 | Index verification | All defined indexes exist |

### 5.5 Network Connectivity Verification

Verify inter-service communication paths are functional.

| Check ID | Source | Destination | Protocol | Expected |
|---|---|---|---|---|
| IQ-NET-001 | Backend | PostgreSQL | TCP/5432 | Connection established |
| IQ-NET-002 | Backend | Redis | TCP/6379 | PING/PONG successful |
| IQ-NET-003 | Backend | Neo4j | TCP/7687 | Connection or graceful skip |
| IQ-NET-004 | Frontend | Backend | HTTP/8000 | 200 OK on /health |
| IQ-NET-005 | Load Balancer | Backend | HTTP/8000 | Health check passes |

### 5.6 Security Baseline Verification

Verify security controls are in place.

| Check ID | Control | Requirement | Verification |
|---|---|---|---|
| IQ-SEC-001 | TLS Configuration | TLS 1.2+ enforced | Certificate and protocol check |
| IQ-SEC-002 | Authentication | API key or JWT required on protected endpoints | 401 on missing auth |
| IQ-SEC-003 | RBAC | Role-based access control enforced | Permission denied on unauthorized |
| IQ-SEC-004 | Security Headers | OWASP headers present | Response header inspection |
| IQ-SEC-005 | Rate Limiting | Configured and enforced | 429 on excessive requests |
| IQ-SEC-006 | CORS | Properly restricted | No wildcard in production |
| IQ-SEC-007 | Audit Logging | Middleware active | Audit entries created on requests |

---

## 6. IQ Test Cases

### IQ-TC-001: PostgreSQL Connectivity
- **Objective:** Verify PostgreSQL database is accessible
- **Procedure:** Execute connection test using configured DATABASE_URL
- **Expected:** Connection successful, version >= 14
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-002: Redis Connectivity
- **Objective:** Verify Redis server is accessible
- **Procedure:** Execute PING command on configured REDIS_URL
- **Expected:** Returns PONG
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-003: Neo4j Connectivity (Optional)
- **Objective:** Verify Neo4j graph database is accessible or properly skipped
- **Procedure:** Attempt connection to Neo4j; verify graceful degradation if unavailable
- **Expected:** Connection successful OR skip with logged warning
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-004: Python Version
- **Objective:** Verify Python runtime version
- **Procedure:** Execute `python --version`
- **Expected:** Python 3.13.x
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-005: Node.js Version
- **Objective:** Verify Node.js runtime version
- **Procedure:** Execute `node --version`
- **Expected:** v20.x or v22.x
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-006: FastAPI Installation
- **Objective:** Verify FastAPI framework is installed at correct version
- **Procedure:** `pip show fastapi`
- **Expected:** Version present and importable
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-007: Database Migration Status
- **Objective:** Verify all Alembic migrations applied
- **Procedure:** `alembic current` and compare to `alembic heads`
- **Expected:** Current revision matches head
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-008: Core Table Existence
- **Objective:** Verify minimum table count in database
- **Procedure:** Query information_schema.tables
- **Expected:** >= 20 tables present
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-009: Environment Configuration
- **Objective:** Verify environment variables are set
- **Procedure:** Check all required env vars are non-empty
- **Expected:** All required variables present
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-010: API Prefix Configuration
- **Objective:** Verify API prefix is correctly configured
- **Procedure:** Check settings.api_v1_prefix
- **Expected:** `/api/v1`
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-011: Secret Key Strength
- **Objective:** Verify secret key meets minimum length
- **Procedure:** Check len(SECRET_KEY) >= 32
- **Expected:** Length >= 32 characters
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-012: Debug Mode Disabled (Production)
- **Objective:** Verify debug mode is off in production
- **Procedure:** Check settings.debug is False when ENVIRONMENT=production
- **Expected:** debug == False
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-013: CORS Configuration
- **Objective:** Verify CORS origins are properly restricted
- **Procedure:** Check settings.cors_origins_list
- **Expected:** Non-empty, no wildcard in production
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-014: Security Headers Middleware
- **Objective:** Verify security headers middleware is active
- **Procedure:** Send request, inspect response headers
- **Expected:** X-Content-Type-Options, X-Frame-Options present
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-015: Rate Limiting Active
- **Objective:** Verify rate limiting middleware is configured
- **Procedure:** Confirm RateLimitMiddleware in middleware stack
- **Expected:** Middleware registered
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-016: Audit Logging Active
- **Objective:** Verify audit middleware is registered
- **Procedure:** Confirm AuditMiddleware in middleware stack
- **Expected:** Middleware registered
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-017: Health Endpoint Accessible
- **Objective:** Verify /health endpoint responds
- **Procedure:** GET /health
- **Expected:** 200 OK with status "healthy"
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-018: Readiness Endpoint Accessible
- **Objective:** Verify /ready endpoint responds
- **Procedure:** GET /ready
- **Expected:** 200 OK with status "ready"
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-019: OpenAPI Documentation Available
- **Objective:** Verify API documentation is served
- **Procedure:** GET /api/v1/docs
- **Expected:** 200 OK, Swagger UI HTML
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-020: Docker Container Health
- **Objective:** Verify all Docker containers are running
- **Procedure:** `docker compose ps`
- **Expected:** All containers in "Up" state
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-021: Vocabulary Service Loaded
- **Objective:** Verify vocabulary data is preloaded
- **Procedure:** Check /ready endpoint vocabulary stats
- **Expected:** concept_count > 0, term_count > 0
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

### IQ-TC-022: Log Configuration
- **Objective:** Verify structured logging is configured
- **Procedure:** Check log output format matches expected pattern
- **Expected:** Structured JSON in production, colored text in debug
- **Status:** [ ] PASS  [ ] FAIL  [ ] N/A

---

## 7. Sign-Off

| Role | Name | Signature | Date |
|---|---|---|---|
| QA Lead | _________________ | _________________ | __________ |
| IT Operations | _________________ | _________________ | __________ |
| Validation Lead | _________________ | _________________ | __________ |
| Quality Assurance Manager | _________________ | _________________ | __________ |

---

## 8. Deviation Log

| Deviation # | IQ Check | Description | Impact | Resolution | Resolved By | Date |
|---|---|---|---|---|---|---|
| | | | | | | |

---

## 9. Appendices

### Appendix A: Environment Checklist
- [ ] All IQ test cases executed
- [ ] All deviations documented and resolved
- [ ] Sign-off obtained from all required roles
- [ ] IQ report archived in document management system

### Appendix B: Tools Used
- `pytest` - Automated IQ check execution
- `alembic` - Database migration verification
- `docker compose` - Container orchestration verification
- `curl` / `httpie` - HTTP endpoint verification
