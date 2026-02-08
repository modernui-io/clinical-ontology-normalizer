# Operational Qualification (OQ) Protocol

**Document ID:** OQ-CON-001
**Version:** 1.0
**Effective Date:** 2026-02-08
**System:** Clinical Ontology Normalizer (CON) - Clinical Trial Patient Recruitment Platform

---

## 1. Purpose

This Operational Qualification (OQ) protocol verifies that the Clinical Ontology Normalizer system operates correctly under normal conditions across all critical functional areas. It confirms that the system performs as designed when used within its specified operating parameters.

## 2. Scope

This OQ covers functional verification of:

- User authentication and authorization
- Clinical document ingestion and NLP extraction
- OMOP concept mapping
- Clinical trial screening (inclusion/exclusion criteria evaluation)
- Patient knowledge graph construction and querying
- Audit trail integrity and compliance
- Data export (FHIR R4, OMOP CDM)
- Error handling and graceful degradation

## 3. References

| Document | ID |
|---|---|
| Installation Qualification Protocol | IQ-CON-001 |
| System Requirements Specification | SRS-CON-001 |
| Performance Qualification Protocol | PQ-CON-001 |
| User Requirements Specification | URS-CON-001 |

## 4. Prerequisites

- IQ-CON-001 completed and approved
- Test environment provisioned and stable
- Test data loaded (patients, documents, trials)
- Test user accounts created with appropriate roles

## 5. Responsibilities

| Role | Responsibility |
|---|---|
| QA Lead | Execute OQ test cases, document results |
| Clinical SME | Verify clinical logic correctness |
| Validation Lead | Review and approve OQ results |
| Development Lead | Provide technical support |

---

## 6. OQ Protocol Sections

### 6.1 User Authentication and Authorization

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-AUTH-001 | Login with valid credentials | 200 OK, JWT token returned |
| OQ-AUTH-002 | Login with invalid credentials | 401 Unauthorized |
| OQ-AUTH-003 | Access protected endpoint without token | 401 Unauthorized |
| OQ-AUTH-004 | Access protected endpoint with valid token | 200 OK, data returned |
| OQ-AUTH-005 | Access admin endpoint with non-admin role | 403 Forbidden |
| OQ-AUTH-006 | RBAC enforcement on patient data | Only permitted roles access PHI |

### 6.2 Clinical Document Ingestion

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-DOC-001 | Ingest plain text clinical note | Document created, ID returned |
| OQ-DOC-002 | FHIR DocumentReference import | Document parsed and stored |
| OQ-DOC-003 | NLP extraction on clinical note | Mentions extracted with offsets |
| OQ-DOC-004 | Assertion classification | PRESENT/ABSENT/POSSIBLE detected |
| OQ-DOC-005 | Temporality detection | CURRENT/HISTORICAL classified |
| OQ-DOC-006 | Duplicate document detection | Duplicate flagged or rejected |

### 6.3 OMOP Concept Mapping

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-MAP-001 | Map "diabetes mellitus" to OMOP | Correct concept_id returned |
| OQ-MAP-002 | Map "aspirin" to RxNorm/OMOP | Correct drug concept returned |
| OQ-MAP-003 | Map ambiguous term | Multiple candidates with scores |
| OQ-MAP-004 | Map unknown term | Unmapped result with 0 candidates |
| OQ-MAP-005 | Batch mapping (10 terms) | All mapped within timeout |

### 6.4 Trial Screening

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-SCR-001 | Screen patient meeting all inclusion criteria | Eligible, match_score > 0.8 |
| OQ-SCR-002 | Screen patient failing exclusion criterion | Ineligible, exclusion_triggered populated |
| OQ-SCR-003 | Screen patient with missing data | UNKNOWN criteria identified |
| OQ-SCR-004 | Screen with safety block (exclusion) | safety_blocked = True, score = 0.0 |
| OQ-SCR-005 | Bulk screening (100 patients x 1 trial) | All results returned, no errors |
| OQ-SCR-006 | CDS disclaimer present | requires_clinician_review = True |
| OQ-SCR-007 | Data completeness score | Completeness metrics calculated |

### 6.5 Patient Knowledge Graph

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-KG-001 | Create patient node | Node created with properties |
| OQ-KG-002 | Create condition edge | Edge links patient to condition |
| OQ-KG-003 | Query patient subgraph | All connected nodes returned |
| OQ-KG-004 | Graph traversal (2 hops) | Related concepts discovered |
| OQ-KG-005 | Graph analytics (centrality) | Metrics calculated correctly |

### 6.6 Audit Trail

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-AUD-001 | API request generates audit entry | Audit log record created |
| OQ-AUD-002 | PHI access logged | Patient data access recorded |
| OQ-AUD-003 | Screening override logged | Override action with reason stored |
| OQ-AUD-004 | Audit log tamper detection | Integrity check passes |
| OQ-AUD-005 | Audit log query by date range | Filtered results returned |
| OQ-AUD-006 | Audit log query by user | User-specific entries returned |

### 6.7 Data Export

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-EXP-001 | Export patient as FHIR Patient resource | Valid FHIR R4 JSON |
| OQ-EXP-002 | Export conditions as FHIR Conditions | Valid FHIR R4 bundle |
| OQ-EXP-003 | Export to OMOP CDM format | CDM-compliant output |
| OQ-EXP-004 | Bulk export (NDJSON) | All records in NDJSON format |

### 6.8 Error Handling

| Check ID | Scenario | Expected Result |
|---|---|---|
| OQ-ERR-001 | Invalid request body | 422 with field-level errors |
| OQ-ERR-002 | Resource not found | 404 with descriptive message |
| OQ-ERR-003 | Database connection failure | 503 Service Unavailable, graceful message |
| OQ-ERR-004 | Rate limit exceeded | 429 Too Many Requests |
| OQ-ERR-005 | Internal server error | 500 with request ID for tracing |

---

## 7. OQ Test Cases

### Authentication & Authorization

#### OQ-TC-001: Successful Login
- **Objective:** Verify user authentication with valid credentials
- **Precondition:** Test user exists in system
- **Procedure:** POST /api/v1/auth/login with valid username/password
- **Expected:** 200 OK, response contains access_token
- **Acceptance:** Token is valid JWT with correct claims
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-002: Failed Login
- **Objective:** Verify rejection of invalid credentials
- **Procedure:** POST /api/v1/auth/login with wrong password
- **Expected:** 401 Unauthorized
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-003: Token-Protected Endpoint Access
- **Objective:** Verify authenticated access to protected endpoints
- **Procedure:** GET /api/v1/patients with valid Bearer token
- **Expected:** 200 OK with patient list
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-004: Unauthorized Endpoint Access
- **Objective:** Verify unauthenticated requests are rejected
- **Procedure:** GET /api/v1/patients without Authorization header
- **Expected:** 401 Unauthorized
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-005: Role-Based Access Control
- **Objective:** Verify RBAC enforcement
- **Procedure:** Access admin endpoint with non-admin user token
- **Expected:** 403 Forbidden
- **Status:** [ ] PASS  [ ] FAIL

### Document Ingestion & NLP

#### OQ-TC-006: Ingest Clinical Note
- **Objective:** Verify document ingestion pipeline
- **Procedure:** POST /api/v1/documents with clinical note text
- **Expected:** 201 Created, document_id returned
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-007: NLP Mention Extraction
- **Objective:** Verify NLP extracts clinical mentions
- **Procedure:** Submit note "Patient has type 2 diabetes mellitus"
- **Expected:** Mention extracted: "type 2 diabetes mellitus" with offsets
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-008: Assertion Detection
- **Objective:** Verify assertion classification (present/absent)
- **Procedure:** Submit note "Patient denies chest pain"
- **Expected:** "chest pain" classified as ABSENT
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-009: FHIR Document Import
- **Objective:** Verify FHIR DocumentReference import
- **Procedure:** POST /api/v1/fhir/DocumentReference with valid FHIR resource
- **Expected:** Document created from FHIR resource
- **Status:** [ ] PASS  [ ] FAIL

### OMOP Mapping

#### OQ-TC-010: Single Term Mapping
- **Objective:** Verify OMOP concept mapping for known term
- **Procedure:** Map "type 2 diabetes mellitus" to OMOP
- **Expected:** Returns concept_id with high confidence score
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-011: Medication Mapping
- **Objective:** Verify medication mapping to RxNorm/OMOP
- **Procedure:** Map "metformin 500mg"
- **Expected:** Correct drug concept with ingredient/form
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-012: Unmappable Term Handling
- **Objective:** Verify graceful handling of unmappable terms
- **Procedure:** Map "xyzabc123" (gibberish)
- **Expected:** Empty candidates, no error
- **Status:** [ ] PASS  [ ] FAIL

### Trial Screening

#### OQ-TC-013: Eligible Patient Screening
- **Objective:** Verify eligible patient is correctly identified
- **Procedure:** Screen patient with data matching all inclusion criteria
- **Expected:** eligible=True, match_score > 0.8
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-014: Ineligible Patient Screening
- **Objective:** Verify ineligible patient is correctly excluded
- **Procedure:** Screen patient with exclusion criterion match
- **Expected:** eligible=False, exclusion_triggered populated
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-015: Missing Data Screening
- **Objective:** Verify UNKNOWN status for missing data
- **Procedure:** Screen patient with incomplete records
- **Expected:** Missing criteria identified, data_completeness provided
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-016: Safety Block Enforcement
- **Objective:** Verify safety block prevents enrollment
- **Procedure:** Screen patient matching high-confidence exclusion
- **Expected:** safety_blocked=True, match_score=0.0
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-017: CDS Disclaimer Compliance
- **Objective:** Verify CDS disclaimer is always present
- **Procedure:** Check any screening response
- **Expected:** requires_clinician_review=True, cds_disclaimer present
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-018: Bulk Screening
- **Objective:** Verify bulk screening returns complete results
- **Procedure:** Screen 50 patients against 3 trials
- **Expected:** All 150 pairs evaluated, summary statistics correct
- **Status:** [ ] PASS  [ ] FAIL

### Knowledge Graph

#### OQ-TC-019: Node Creation
- **Objective:** Verify KG node creation
- **Procedure:** Create patient node via graph API
- **Expected:** Node created with correct properties
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-020: Edge Creation
- **Objective:** Verify KG edge creation
- **Procedure:** Create HAS_CONDITION edge between patient and condition
- **Expected:** Edge created with relationship type
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-021: Subgraph Query
- **Objective:** Verify subgraph retrieval
- **Procedure:** Query all nodes connected to a patient
- **Expected:** Complete subgraph returned
- **Status:** [ ] PASS  [ ] FAIL

### Audit Trail

#### OQ-TC-022: Request Audit Logging
- **Objective:** Verify API requests generate audit entries
- **Procedure:** Make API call, check audit log
- **Expected:** Audit entry with timestamp, user, endpoint, method
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-023: PHI Access Logging
- **Objective:** Verify PHI access is logged
- **Procedure:** Access patient record, check audit log
- **Expected:** PHI access event logged with patient_id
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-024: Audit Log Query
- **Objective:** Verify audit log is queryable
- **Procedure:** GET /api/v1/audit with date range filter
- **Expected:** Filtered audit entries returned
- **Status:** [ ] PASS  [ ] FAIL

### Data Export

#### OQ-TC-025: FHIR Patient Export
- **Objective:** Verify FHIR Patient resource export
- **Procedure:** GET /api/v1/fhir/Patient/{id}
- **Expected:** Valid FHIR R4 Patient JSON
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-026: FHIR Condition Export
- **Objective:** Verify FHIR Condition resource export
- **Procedure:** GET /api/v1/fhir/Condition?patient={id}
- **Expected:** Valid FHIR R4 Bundle with Conditions
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-027: OMOP CDM Export
- **Objective:** Verify OMOP CDM format export
- **Procedure:** Export patient data in OMOP CDM format
- **Expected:** CDM-compliant tables with correct mappings
- **Status:** [ ] PASS  [ ] FAIL

### Error Handling

#### OQ-TC-028: Validation Error Response
- **Objective:** Verify 422 on invalid input
- **Procedure:** POST with invalid JSON body
- **Expected:** 422 with structured error details
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-029: Not Found Response
- **Objective:** Verify 404 on missing resource
- **Procedure:** GET /api/v1/patients/nonexistent-id
- **Expected:** 404 with descriptive message
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-030: Rate Limit Response
- **Objective:** Verify 429 on rate limit exceeded
- **Procedure:** Send requests exceeding rate limit
- **Expected:** 429 with retry-after information
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-031: Internal Error Response
- **Objective:** Verify 500 response includes request ID
- **Procedure:** Trigger internal error condition
- **Expected:** 500 with X-Request-ID for tracing
- **Status:** [ ] PASS  [ ] FAIL

#### OQ-TC-032: Service Unavailable Response
- **Objective:** Verify 503 on dependent service failure
- **Procedure:** Simulate database unavailability
- **Expected:** 503 Service Unavailable, graceful message
- **Status:** [ ] PASS  [ ] FAIL

---

## 8. Requirements Traceability Matrix

| Requirement ID | Requirement Description | OQ Test Case(s) |
|---|---|---|
| REQ-AUTH-001 | Users must authenticate before accessing protected resources | OQ-TC-001, OQ-TC-002, OQ-TC-003, OQ-TC-004 |
| REQ-AUTH-002 | Role-based access control must be enforced | OQ-TC-005 |
| REQ-DOC-001 | System must ingest clinical documents | OQ-TC-006 |
| REQ-NLP-001 | System must extract clinical mentions from text | OQ-TC-007, OQ-TC-008 |
| REQ-FHIR-001 | System must import FHIR resources | OQ-TC-009 |
| REQ-MAP-001 | System must map mentions to OMOP concepts | OQ-TC-010, OQ-TC-011 |
| REQ-MAP-002 | System must handle unmappable terms gracefully | OQ-TC-012 |
| REQ-SCR-001 | System must screen patients against trial criteria | OQ-TC-013, OQ-TC-014 |
| REQ-SCR-002 | System must identify missing data | OQ-TC-015 |
| REQ-SCR-003 | System must enforce safety blocks | OQ-TC-016 |
| REQ-SCR-004 | System must include CDS disclaimers | OQ-TC-017 |
| REQ-SCR-005 | System must support bulk screening | OQ-TC-018 |
| REQ-KG-001 | System must build patient knowledge graphs | OQ-TC-019, OQ-TC-020, OQ-TC-021 |
| REQ-AUD-001 | All actions must be audit-logged | OQ-TC-022, OQ-TC-023, OQ-TC-024 |
| REQ-EXP-001 | System must export data in FHIR R4 format | OQ-TC-025, OQ-TC-026 |
| REQ-EXP-002 | System must export data in OMOP CDM format | OQ-TC-027 |
| REQ-ERR-001 | System must return structured error responses | OQ-TC-028 through OQ-TC-032 |

---

## 9. Sign-Off

| Role | Name | Signature | Date |
|---|---|---|---|
| QA Lead | _________________ | _________________ | __________ |
| Clinical SME | _________________ | _________________ | __________ |
| Validation Lead | _________________ | _________________ | __________ |
| Quality Assurance Manager | _________________ | _________________ | __________ |

---

## 10. Deviation Log

| Deviation # | OQ Test | Description | Impact | Resolution | Resolved By | Date |
|---|---|---|---|---|---|---|
| | | | | | | |
