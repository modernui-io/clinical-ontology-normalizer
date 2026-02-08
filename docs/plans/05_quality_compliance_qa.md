# Deep Implementation Plan: Quality, Compliance, QA, COO, and FHIR Specialist

**Scope**: VP Quality/Regulatory, CLO/Compliance Officer, QA Engineer, COO, and FHIR Integration Specialist sections from `docs/HARDENING_PLAN.md`
**Research basis**: `docs/research/03_quality_compliance_research.md`

---

## Table of Contents

1. [VP Quality / Regulatory](#1-vp-quality--regulatory)
2. [CLO / Compliance Officer](#2-clo--compliance-officer)
3. [QA Engineer](#3-qa-engineer)
4. [COO](#4-coo)
5. [FHIR Integration Specialist](#5-fhir-integration-specialist)

---

## 1. VP Quality / Regulatory

### 1.1 Regulatory Determination Document

**Hardening item**: Establish CDS exemption rationale under Cures Act Section 520(o). All 4 criteria must be documented.

**Files to create**:
- `docs/regulatory/cds_exemption_determination.md` -- the regulatory determination file
- `docs/regulatory/README.md` -- index of all regulatory docs

**Implementation steps**:
1. Draft Section 520(o) criterion-by-criterion analysis specific to our platform:
   - Criterion 1: Confirm we do NOT acquire/process/analyze medical images or IVD signals. Our pipeline ingests FHIR Bundles via `backend/app/api/metriport_webhook.py` and clinical notes via `backend/app/api/documents/` -- text only.
   - Criterion 2: Document that we display/analyze/print medical information. The frontend at `frontend/src/app/` presents patient data, eligibility results, and knowledge graph visualizations.
   - Criterion 3: Document that the system is intended for HCP use only. Reference the existing demo login flow (commit `44b6074`) which authenticates users as providers.
   - Criterion 4: Document the explainability features. The `TrialEligibilityService.check_patient_eligibility()` at `backend/app/services/trial_eligibility_service.py:794-884` returns `PatientEligibility` with per-criterion `CriterionResult` objects including `evidence_fact_ids`, `confidence`, and `details` -- fulfilling the transparency requirement.
2. Document intended use statement that will appear in product UI and all marketing materials.
3. Map all current and planned features against the 4 criteria to identify any features that could jeopardize exemption status.
4. Create a risk register of features that must never be implemented (autonomous enrollment, direct-to-patient screening without HCP, time-critical alerting).

**Acceptance criteria**:
- Document addresses all 4 Cures Act Section 520(o) criteria with codebase-specific evidence
- Legal review sign-off (external counsel recommended)
- Document is version-controlled and linked from CLAUDE.md regulatory section

**Effort**: 3-5 days (includes legal review cycle)

**Dependencies**: None -- can start immediately

---

### 1.2 Intended Use Statement

**Hardening item**: "Clinical decision support for healthcare professionals" must be prominent in product and documentation.

**Files to modify**:
- `frontend/src/app/page.tsx` -- landing page
- `frontend/src/app/layout.tsx` -- root layout (add footer disclaimer)
- `frontend/src/app/(dashboard)/trials/page.tsx` -- trial matching UI (if exists)
- `backend/app/api/trials.py` -- API response headers/disclaimers
- `backend/app/services/trial_eligibility_service.py:656-667` -- add disclaimer field to `ScreeningResponse`
- `docs/regulatory/intended_use_statement.md` -- canonical intended use text

**Implementation steps**:
1. Draft the canonical intended use statement:
   ```
   This software is intended to provide clinical decision support for
   healthcare professionals. It does not replace clinical judgment.
   All patient-trial matches require independent clinician review
   before any enrollment action.
   ```
2. Add to `ScreeningResponse` schema in `backend/app/schemas/trial.py` a `disclaimer: str` field with the above text as a default.
3. Add to the `PatientEligibility` schema a `requires_clinician_review: bool = True` field.
4. Add footer component to `frontend/src/app/layout.tsx` with the disclaimer.
5. Add the disclaimer text prominently on all trial matching result pages.
6. Update the API docs description in `backend/app/main.py` to include the intended use statement.

**Acceptance criteria**:
- Intended use statement appears on every page where clinical data or trial matches are displayed
- API responses for screening include the disclaimer field
- `PatientEligibility.requires_clinician_review` is always `True` and cannot be set to `False`

**Effort**: 1 day

**Dependencies**: 1.1 (the statement wording should match the regulatory determination)

---

### 1.3 IQ/OQ/PQ Documentation

**Hardening item**: Installation, Operational, and Performance Qualification for clinical-grade software. GAMP 5 2nd Edition framework.

**Files to create**:
- `docs/regulatory/iq_oq_pq/README.md` -- overview and index
- `docs/regulatory/iq_oq_pq/installation_qualification.md` -- IQ document
- `docs/regulatory/iq_oq_pq/operational_qualification.md` -- OQ document
- `docs/regulatory/iq_oq_pq/performance_qualification.md` -- PQ document
- `backend/scripts/iq_check.py` -- automated IQ verification script
- `backend/scripts/oq_check.py` -- automated OQ verification script

**Implementation steps**:
1. **IQ (Installation Qualification)**: Write a script `iq_check.py` that verifies:
   - Python version >= 3.13 (matches `backend/pyproject.toml` requirement)
   - All required packages installed at pinned versions (parse `backend/uv.lock`)
   - PostgreSQL connection and version check
   - Redis connection and version check
   - Database schema matches expected state (compare `alembic heads` with deployed)
   - Environment variables for all required config in `backend/app/core/config.py`
   - Docker image versions match expected (parse `docker-compose.yml`)
2. **OQ (Operational Qualification)**: Write a script `oq_check.py` that runs:
   - Health check endpoint (`/health`) returns 200
   - Document ingestion endpoint accepts and processes a test document
   - FHIR import endpoint processes a sample Bundle
   - NLP extraction produces expected mentions from a known clinical note
   - OMOP mapping resolves known terms (e.g., "diabetes" -> concept 201826)
   - Trial screening returns expected results for a known patient-trial pair
   - Audit logging captures all operations from the above tests
3. **PQ (Performance Qualification)**: Document performance benchmarks:
   - Webhook response time < 500ms (per `backend/app/api/metriport_webhook.py` spec of 4-second Metriport requirement)
   - NLP processing time < 5s per document
   - Trial matching API response < 2s
   - Knowledge graph query < 1s
   - Record baseline measurements with `pytest-benchmark` or custom timing
4. Add `make iq-check` and `make oq-check` targets to `Makefile`.

**Acceptance criteria**:
- IQ script runs green on a fresh deployment and catches misconfigurations
- OQ script validates all critical path operations
- PQ document records baseline performance metrics
- All three documents follow GAMP 5 2nd Edition risk-based approach

**Effort**: 2-3 weeks

**Dependencies**: None for documentation; OQ script depends on existing test infrastructure

---

### 1.4 Change Control Process

**Hardening item**: Every code change affecting clinical output must have documented review and approval.

**Files to modify**:
- `.github/workflows/ci.yml` -- add clinical path change detection
- `.github/PULL_REQUEST_TEMPLATE.md` -- add clinical impact checklist (create if missing)

**Files to create**:
- `docs/regulatory/change_control_process.md` -- formal change control SOP
- `.github/workflows/clinical-review.yml` -- GitHub Actions workflow for clinical path changes
- `scripts/detect_clinical_path_changes.py` -- script to detect changes in clinical-critical code

**Implementation steps**:
1. Define the "clinical critical paths" in the codebase:
   - `backend/app/services/trial_eligibility_service.py` -- eligibility logic
   - `backend/app/services/fhir_import.py` -- FHIR data ingestion
   - `backend/app/services/mapping*.py` -- OMOP concept mapping
   - `backend/app/services/fact_builder*.py` -- clinical fact creation
   - `backend/app/services/nlp*.py` -- NLP extraction
   - `backend/app/services/rule_based_nlp*.py` -- rule-based NLP
   - `backend/app/models/clinical_fact.py` -- clinical fact model
   - `backend/app/models/trial.py` -- trial model
   - `backend/app/schemas/trial.py` -- trial schemas
2. Create `scripts/detect_clinical_path_changes.py` that uses `git diff` to detect changes in clinical paths and outputs a summary.
3. Create `.github/workflows/clinical-review.yml`:
   - Trigger on PRs that modify files in clinical critical paths
   - Require explicit approval from a designated "clinical reviewer" role
   - Block merge until clinical review is completed
   - Add label `clinical-impact` to PRs that touch clinical paths
4. Create PR template with clinical impact checklist:
   - Does this change affect NLP extraction accuracy?
   - Does this change affect OMOP mapping results?
   - Does this change affect trial eligibility logic?
   - Does this change affect patient safety labels/disclaimers?
   - Has the golden dataset regression suite been run?
5. Write the formal SOP document covering:
   - Change request initiation and categorization
   - Risk assessment for clinical changes
   - Review and approval workflow
   - Testing requirements per change category
   - Post-deployment verification

**Acceptance criteria**:
- PRs touching clinical paths are automatically flagged
- Clinical review is required for flagged PRs before merge
- Change control SOP is documented and accessible
- PR template includes clinical impact assessment checklist

**Effort**: 3-5 days

**Dependencies**: None

---

### 1.5 CAPA System

**Hardening item**: Corrective and Preventive Action workflow for NLP errors with clinical impact.

**Files to create**:
- `backend/app/models/capa.py` -- CAPA data model
- `backend/app/schemas/capa.py` -- CAPA Pydantic schemas
- `backend/app/api/capa.py` -- CAPA API endpoints
- `backend/app/services/capa_service.py` -- CAPA business logic
- `backend/tests/test_capa.py` -- CAPA tests
- `docs/regulatory/capa_sop.md` -- CAPA standard operating procedure

**Implementation steps**:
1. Create `backend/app/models/capa.py`:
   ```python
   class CAPAStatus(str, Enum):
       OPEN = "open"
       INVESTIGATION = "investigation"
       ROOT_CAUSE = "root_cause"
       CORRECTIVE_ACTION = "corrective_action"
       PREVENTIVE_ACTION = "preventive_action"
       VERIFICATION = "verification"
       CLOSED = "closed"

   class CAPASeverity(str, Enum):
       CRITICAL = "critical"   # Patient safety impact
       MAJOR = "major"         # Clinical accuracy impact
       MINOR = "minor"         # Cosmetic/usability

   class CAPARecord(Base):
       __tablename__ = "capa_records"
       title: str
       description: str
       severity: CAPASeverity
       status: CAPAStatus
       source: str  # e.g., "nlp_false_negative", "mapping_error", "eligibility_logic"
       affected_patient_ids: list[str]  # JSON array
       root_cause: str | None
       corrective_action: str | None
       preventive_action: str | None
       assigned_to: str | None
       opened_at: datetime
       closed_at: datetime | None
       verification_notes: str | None
   ```
2. Create CRUD API at `backend/app/api/capa.py` (following patterns in existing API files).
3. Create service at `backend/app/services/capa_service.py` with:
   - `open_capa()` -- triggered manually or by automated monitoring
   - `update_capa_status()` -- workflow transitions with validation
   - `link_to_audit_trail()` -- cross-reference with `AuditLog` entries
   - `generate_capa_report()` -- export for regulatory reporting
4. Wire into the audit system: when a clinician override occurs (rejects a match the system recommended, or approves one the system missed), auto-create a CAPA if the pattern exceeds a threshold (e.g., >5% override rate for a specific criterion).
5. Add API router to `backend/app/api/__init__.py`.
6. Write tests following the pattern in `backend/tests/test_mapping_service.py`.

**Acceptance criteria**:
- CAPA records can be created, updated through status workflow, and closed
- Each CAPA links to affected patient IDs and audit trail entries
- CAPA report can be exported for regulatory review
- Integration tests verify full CAPA lifecycle

**Effort**: 1-2 weeks

**Dependencies**: Audit logging system (already exists at `backend/app/models/audit.py` and `backend/app/services/audit_service.py`)

---

### 1.6 Traceability Matrix

**Hardening item**: Requirements to design to implementation to test for all clinical features.

**Files to create**:
- `docs/regulatory/traceability_matrix.md` -- the matrix document
- `scripts/generate_traceability_matrix.py` -- auto-generate matrix from code annotations

**Implementation steps**:
1. Define requirement IDs for all clinical features (REQ-NLP-001 through REQ-TRIAL-NNN).
2. Map each requirement to:
   - Design: relevant service file and function
   - Implementation: specific file:line references
   - Test: specific test file:test_name
3. Add `# REQ: REQ-NLP-001` comments to critical code paths for automated tracing.
4. Write `scripts/generate_traceability_matrix.py` to:
   - Parse `# REQ:` comments from all `backend/app/services/*.py` files
   - Parse test function names from `backend/tests/test_*.py` files
   - Generate a markdown table showing coverage gaps
5. Key traceability entries:
   | Requirement | Design | Implementation | Test |
   |---|---|---|---|
   | REQ-NLP-001: Entity extraction | `services/nlp_service.py` | `services/rule_based_nlp*.py` | `tests/test_nlp_rule_based.py` |
   | REQ-MAP-001: OMOP mapping | `services/mapping.py` | `services/mapping_db.py` | `tests/test_mapping_service.py` |
   | REQ-FACT-001: Fact building | `services/fact_builder*.py` | Same | `tests/test_fact_builder.py` |
   | REQ-TRIAL-001: Eligibility screening | `services/trial_eligibility_service.py` | Same:560-667 | (needs test) |
   | REQ-FHIR-001: Bundle import | `services/fhir_import.py` | Same:172-307 | (needs test) |

**Acceptance criteria**:
- Every clinical requirement has a traceable path from requirement to test
- Automated script identifies untested requirements
- Matrix is regenerated on every release

**Effort**: 1 week initial, ongoing maintenance

**Dependencies**: 1.4 (change control ensures matrix stays updated)

---

### 1.7 ISO 14971 Risk Assessment (FMEA/FTA)

**Hardening item**: FMEA for NLP extraction, mapping, eligibility logic failures. FTA for "wrong patient enrolled in trial."

**Files to create**:
- `docs/regulatory/risk_management/fmea.md` -- Failure Mode and Effects Analysis
- `docs/regulatory/risk_management/fta.md` -- Fault Tree Analysis
- `docs/regulatory/risk_management/risk_register.md` -- Risk register with mitigations

**Implementation steps**:
1. **FMEA for NLP Extraction Pipeline**:
   - Failure mode: Entity not detected (false negative) in `backend/app/services/rule_based_nlp*.py`
     - Effect: Eligible patient missed for trial
     - Severity: HIGH | Occurrence: MEDIUM | Detection: LOW (no monitoring)
     - RPN = S x O x D -- prioritize by RPN
     - Mitigation: Golden dataset regression testing, sensitivity monitoring
   - Failure mode: Wrong assertion detected (negation error)
     - Effect: Patient flagged as having condition they were denied
     - Mitigation: Assertion detection test suite (see QA section 3.3)
   - Failure mode: Wrong OMOP concept mapped in `backend/app/services/mapping_db.py`
     - Effect: Incorrect eligibility determination
     - Mitigation: OMOP regression suite (see QA section 3.2)
2. **FMEA for Trial Eligibility Logic**:
   - Failure mode: Age calculation error in `trial_eligibility_service.py:441-470`
     - The `_get_demographic_patient_ids` method calculates age from `birth_date` in KGNode properties using `(now - birth_date).days / 365.25` which is approximate
     - Mitigation: Use `dateutil.relativedelta` for exact age calculation
   - Failure mode: Exclusion criterion not evaluated in `trial_eligibility_service.py:617-636`
     - If `_criterion_patient_query` returns `None` for an exclusion, the patient is not excluded
     - Mitigation: Fail-safe -- unknown exclusion status should flag for manual review
3. **FTA for "Wrong Patient Enrolled in Trial"**:
   - Top event: Patient enrolled in contraindicated trial
   - Gate 1 (OR): Patient passes screening incorrectly OR clinician overrides incorrectly
   - Gate 1.1 (OR): NLP misses exclusion condition OR mapping error OR eligibility logic bug
   - Each leaf maps to specific code path with test coverage requirements
4. Map each identified risk to a mitigation that already exists or needs implementation.

**Acceptance criteria**:
- FMEA covers all pipeline stages with severity/occurrence/detection ratings
- FTA traces "wrong enrollment" to specific code-level failure modes
- Each HIGH-risk item has a documented mitigation plan
- Risk register is maintained as a living document

**Effort**: 1-2 weeks

**Dependencies**: Understanding of pipeline (this exploration phase satisfies it)

---

### 1.8 SaMD Contingency Plan

**Hardening item**: IEC 62304 Class B lifecycle + ISO 13485 QMS readiness, in case FDA reclassifies.

**Files to create**:
- `docs/regulatory/samd_contingency_plan.md`

**Implementation steps**:
1. Document the gap analysis between current state and IEC 62304 Class B requirements:
   - Software development plan: exists informally (CLAUDE.md, docs/IMPLEMENTATION_PLAN.md) but not formatted per IEC 62304
   - Requirements analysis: partially exists in schemas (Pydantic models in `backend/app/schemas/`)
   - Architecture design: exists in CLAUDE.md and `docs/ARCHITECTURE_RATIONALIZATION_PLAN.md`
   - Detailed design: exists as code documentation
   - Unit testing: exists (`backend/tests/`) but coverage unknown
   - Integration testing: exists (`backend/tests/test_integration.py`)
   - System testing: does not exist
   - Risk management: does not exist (created in 1.7)
   - Configuration management: exists via Git
   - Problem resolution: does not exist (CAPA in 1.5)
2. Estimate effort for each gap: 2-4 weeks per gap, 6-9 months total.
3. Identify which current artifacts could be adapted vs. created from scratch.
4. Budget estimate: $50K-$150K for external regulatory consulting + internal effort.

**Acceptance criteria**:
- Gap analysis document with clear remediation plan per IEC 62304 clause
- Timeline and budget estimate for SaMD pathway
- Decision framework for when to activate the contingency

**Effort**: 3-5 days for the document

**Dependencies**: 1.1 (regulatory determination informs whether contingency is likely)

---

## 2. CLO / Compliance Officer

### 2.1 BAA Framework

**Hardening item**: Business Associate Agreement templates for all data sharing relationships.

**Files to create**:
- `docs/compliance/baa_template.md` -- BAA template
- `docs/compliance/baa_registry.md` -- tracking document for executed BAAs
- `backend/app/models/data_agreement.py` -- data agreement tracking model
- `backend/app/api/compliance.py` -- compliance management API

**Implementation steps**:
1. Create BAA template covering:
   - Permitted uses and disclosures of PHI
   - Obligations of the Business Associate (us)
   - Obligations of the Covered Entity (customer)
   - Safeguards required (encryption, access controls, audit logging)
   - Breach notification procedures (aligned with 2025 HIPAA NPRM <24h requirement)
   - Term, termination, and data return/destruction obligations
2. Create `backend/app/models/data_agreement.py`:
   ```python
   class DataAgreement(Base):
       __tablename__ = "data_agreements"
       agreement_type: str  # "BAA", "DUA", "consent"
       counterparty: str
       effective_date: datetime
       expiration_date: datetime | None
       status: str  # "draft", "active", "expired", "terminated"
       document_path: str | None  # path to signed document
       phi_categories: list[str]  # JSON: what PHI is covered
       review_date: datetime | None
   ```
3. Create a simple API for tracking BAA status (CRUD at `backend/app/api/compliance.py`).
4. Identify all current data relationships that require BAAs:
   - Metriport (FHIR data exchange) -- see `backend/app/api/metriport_webhook.py`
   - Any cloud infrastructure providers (AWS, etc.)
   - Any analytics or monitoring services

**Acceptance criteria**:
- BAA template approved by legal counsel
- All current data relationships have BAA status tracked
- API endpoint can list all active/pending BAAs
- Alert mechanism for BAAs approaching expiration

**Effort**: 1 week (template + model), ongoing legal review

**Dependencies**: None

---

### 2.2 Consent Management System

**Hardening item**: Opt-in at GDPR/MHMDA level. Washington My Health My Data Act has no revenue threshold and private right of action.

**Files to create**:
- `backend/app/models/consent.py` -- consent record model
- `backend/app/schemas/consent.py` -- consent Pydantic schemas
- `backend/app/services/consent_service.py` -- consent management logic
- `backend/app/api/consent.py` -- consent API endpoints
- `backend/tests/test_consent_service.py` -- consent tests
- `frontend/src/app/(dashboard)/consent/page.tsx` -- consent management UI

**Implementation steps**:
1. Create `backend/app/models/consent.py`:
   ```python
   class ConsentPurpose(str, Enum):
       TREATMENT = "treatment"
       TRIAL_SCREENING = "trial_screening"
       DATA_SHARING = "data_sharing"
       RESEARCH = "research"
       ANALYTICS = "analytics"

   class ConsentStatus(str, Enum):
       GRANTED = "granted"
       DENIED = "denied"
       WITHDRAWN = "withdrawn"
       EXPIRED = "expired"

   class ConsentRecord(Base):
       __tablename__ = "consent_records"
       patient_id: str
       purpose: ConsentPurpose
       status: ConsentStatus
       consent_text: str  # exact text patient consented to
       granted_at: datetime | None
       withdrawn_at: datetime | None
       expires_at: datetime | None
       mechanism: str  # "electronic", "paper", "verbal"
       ip_address: str | None
       user_agent: str | None
       version: int  # consent form version number
   ```
2. Create `backend/app/services/consent_service.py`:
   - `check_consent(patient_id, purpose)` -- returns bool; called before any PHI access
   - `grant_consent(patient_id, purpose, ...)` -- create consent record
   - `withdraw_consent(patient_id, purpose)` -- mark withdrawn, trigger data handling
   - `get_consent_status(patient_id)` -- returns all consent records for a patient
3. Integrate consent checks into critical paths:
   - `backend/app/services/trial_eligibility_service.py` -- check `trial_screening` consent before screening
   - `backend/app/services/fhir_import.py` -- check `treatment` consent before import
   - `backend/app/api/metriport_webhook.py` -- log consent status at webhook ingestion
4. Wire consent service into the FHIR import pipeline: in `FHIRImportService.import_bundle()` at line 172, add a consent check before processing.
5. Build frontend consent management page where administrators can view/manage patient consent records.
6. Implement consent audit trail -- every consent grant/withdrawal creates an `AuditLog` entry via `backend/app/services/audit_service.py`.

**Acceptance criteria**:
- Consent records are immutable (withdrawal creates new record, doesn't modify old one)
- PHI access paths check consent status before proceeding
- Consent UI allows viewing/managing consent per patient
- All consent changes are audit-logged
- Default is "consent not granted" (GDPR/MHMDA opt-in model)

**Effort**: 2-3 weeks

**Dependencies**: Audit logging (exists), RBAC (exists at `backend/app/models/rbac.py`)

---

### 2.3 Data Use Agreements

**Hardening item**: Template frameworks for sharing de-identified data with pharma partners.

**Files to create**:
- `docs/compliance/dua_template_research.md` -- DUA template for research use
- `docs/compliance/dua_template_commercial.md` -- DUA template for commercial use
- `docs/compliance/dua_template_regulatory.md` -- DUA template for regulatory submissions

**Implementation steps**:
1. Create three DUA templates covering the most common pharma data sharing scenarios:
   - **Research DUA**: IRB-approved research use of de-identified data
   - **Commercial DUA**: Enrollment analytics, screen failure data for pharma sponsors
   - **Regulatory DUA**: Data submissions for FDA regulatory filings
2. Each template must specify:
   - Data elements included (which OMOP tables/fields)
   - De-identification method (Safe Harbor vs Expert Determination)
   - Permitted uses and re-identification prohibition
   - Data security requirements for the recipient
   - Term and termination provisions
   - Breach notification obligations
3. Extend the `DataAgreement` model from 2.1 with `agreement_type = "DUA"` and appropriate metadata fields.

**Acceptance criteria**:
- Three DUA templates covering research, commercial, and regulatory use cases
- Templates approved by legal counsel
- DUA tracking integrated into the compliance API from 2.1

**Effort**: 1 week (templates are primarily legal/business artifacts)

**Dependencies**: 2.1 (BAA framework provides the tracking infrastructure)

---

### 2.4 Right-to-Deletion

**Hardening item**: GDPR, CCPA, MHMDA all require this. Cascade through clinical facts, KG nodes. Flag (don't delete) audit logs.

**Files to create**:
- `backend/app/services/data_deletion_service.py` -- cascading deletion logic
- `backend/app/api/data_rights.py` -- data subject rights API
- `backend/tests/test_data_deletion.py` -- deletion tests

**Implementation steps**:
1. Create `backend/app/services/data_deletion_service.py`:
   ```python
   async def delete_patient_data(patient_id: str, session: AsyncSession, requested_by: str) -> dict:
       """Cascade-delete all patient data while preserving audit trail."""
       # 1. Delete KGEdges (foreign key to KGNode)
       # 2. Delete KGNodes
       # 3. Delete ClinicalFacts + FactEvidence
       # 4. Delete Documents (and associated Mentions, MentionConceptCandidates)
       # 5. Delete TrialEnrollments
       # 6. Delete ConsentRecords
       # 7. Flag (NOT delete) AuditLog entries: set a "data_deleted" flag
       # 8. Create a new AuditLog entry recording the deletion event
       # 9. Return summary of deleted records
   ```
2. The deletion must follow the data model relationships found in:
   - `backend/app/models/knowledge_graph.py` -- KGNode, KGEdge (patient_id field)
   - `backend/app/models/clinical_fact.py` -- ClinicalFact (patient_id field)
   - `backend/app/models/document.py` -- Document (patient_id field)
   - `backend/app/models/mention.py` -- Mention (linked via Document)
   - `backend/app/models/trial.py` -- TrialEnrollment (patient_id field)
3. Important: The existing `FHIRImportService.import_bundle()` at `backend/app/services/fhir_import.py:226-233` already does a "clear existing data" pattern -- model the deletion service similarly but with audit preservation.
4. For AuditLog entries referencing the deleted patient: set `details.data_deleted = True` and `details.deletion_request_id = <request_id>` but do NOT delete the audit records (required for compliance).
5. Create API endpoint at `backend/app/api/data_rights.py`:
   - `POST /api/v1/data-rights/deletion-request` -- initiate deletion
   - `GET /api/v1/data-rights/deletion-request/{id}` -- check status
   - `GET /api/v1/data-rights/patient/{id}/data-summary` -- show what data exists before deletion
6. Write tests that verify:
   - All patient data is removed after deletion
   - Audit log entries are flagged but not deleted
   - Deletion creates its own audit trail entry
   - Deletion is idempotent (running twice is safe)

**Acceptance criteria**:
- All patient data across all tables is cascade-deleted
- Audit log entries are preserved with deletion flags
- Deletion event itself is audit-logged
- API allows initiating and tracking deletion requests
- Test suite verifies complete deletion with no orphaned records

**Effort**: 1-2 weeks

**Dependencies**: Consent management (2.2), Audit logging (exists)

---

### 2.5 Audit Trail for 21 CFR Part 11

**Hardening item**: Secure, time-stamped, immutable. Previously recorded information must NOT be obscured by changes. No user (including admins) can modify audit trails.

**Files to modify**:
- `backend/app/models/audit.py` -- add immutability constraints
- `backend/app/services/audit_service.py` -- add tamper detection
- `backend/app/core/database.py` -- add DB-level protections

**Files to create**:
- `backend/app/services/audit_integrity_service.py` -- hash chain verification
- `backend/tests/test_audit_integrity.py` -- integrity tests

**Implementation steps**:
1. **Immutability at the database level**: Create a PostgreSQL trigger that prevents UPDATE and DELETE on the `audit_logs` table:
   ```sql
   CREATE OR REPLACE FUNCTION prevent_audit_modification()
   RETURNS TRIGGER AS $$
   BEGIN
       RAISE EXCEPTION 'Audit log records cannot be modified or deleted';
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER audit_log_immutable
   BEFORE UPDATE OR DELETE ON audit_logs
   FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
   ```
   Add this as an Alembic migration.
2. **Hash chain for tamper detection**: Add a `record_hash` column to `AuditLog` and a `previous_hash` column. Each new record includes `SHA-256(previous_hash + record_data)`. This creates a tamper-evident chain.
   - Modify `backend/app/services/audit_service.py` to compute and store the hash chain
   - Add `record_hash: Mapped[str]` and `previous_hash: Mapped[str | None]` to `AuditLog` model
3. **Integrity verification**: Create `backend/app/services/audit_integrity_service.py`:
   - `verify_chain(start_id, end_id)` -- verify hash chain integrity between two records
   - `detect_tampering()` -- full chain verification
   - `export_with_integrity_proof(date_range)` -- export audit logs with hash verification data
4. **Retention policy**: Add a `retention_expiry` field to `AuditLog`. Per 21 CFR Part 11, retention must equal or exceed the underlying record retention (6 years for HIPAA). Prevent deletion of records within retention period even via the data deletion service.
5. Update existing `AuditService.log_access()` and related methods to include the hash chain computation.

**Acceptance criteria**:
- Database trigger prevents any modification to audit_logs table
- Hash chain provides tamper-evident verification
- Integrity check API can verify chain validity
- 6-year retention is enforced at the application level
- No user (including database admins acting through the application) can modify audit records

**Effort**: 1-2 weeks

**Dependencies**: Existing audit model (`backend/app/models/audit.py`)

---

### 2.6 IRB Compliance Framework

**Hardening item**: When does trial matching require IRB review?

**Files to create**:
- `docs/compliance/irb_framework.md` -- IRB compliance guidance document

**Implementation steps**:
1. Document the decision tree for IRB review requirements:
   - Internal screening (patient data stays within covered entity): May proceed under HIPAA Preparatory to Research (45 CFR 164.512(i)(1)(ii))
   - External disclosure of PHI to sponsors: Requires IRB waiver of authorization
   - Patient contact/outreach: Requires IRB-approved recruitment materials
   - Data sharing with pharma: Requires DUA + potentially IRB review
2. Map the decision tree to specific platform features:
   - Auto-screening in `trial_eligibility_service.py:936-975` -- internal, may proceed under Preparatory to Research
   - Enrollment creation via `enroll_patient()` at line 981 -- may require consent
   - Data export via `backend/app/api/export/` -- requires DUA if external
3. Add IRB status tracking to the `Trial` model in `backend/app/models/trial.py`:
   - `irb_status: str | None` -- "pending", "approved", "exempt", "not_required"
   - `irb_number: str | None` -- IRB protocol number
   - `irb_approval_date: datetime | None`
   - `irb_expiry_date: datetime | None`

**Acceptance criteria**:
- Decision tree document covers all platform data flow scenarios
- Trial model includes IRB tracking fields
- Platform enforces IRB approval status before enabling patient contact features

**Effort**: 3-5 days

**Dependencies**: 2.1 (BAA framework), 2.2 (consent management)

---

### 2.7 State Privacy Law Compliance

**Hardening item**: Default to highest standard (GDPR/MHMDA-level opt-in).

**Files to create**:
- `docs/compliance/privacy_law_matrix.md` -- state-by-state requirements
- `backend/app/services/privacy_policy_service.py` -- jurisdiction-aware privacy logic

**Implementation steps**:
1. Create a compliance matrix documenting requirements for:
   - HIPAA (federal baseline)
   - GDPR (EU -- if applicable)
   - Washington MHMDA (strictest US state law, private right of action)
   - California CCPA/CPRA
   - Connecticut Data Privacy Act (health data amendments)
   - Nevada SB 370
2. Create `backend/app/services/privacy_policy_service.py`:
   - `get_applicable_laws(patient_state: str) -> list[str]` -- returns applicable privacy laws
   - `get_consent_requirements(patient_state: str) -> dict` -- returns required consent types
   - `check_compliance(patient_id: str) -> dict` -- returns compliance status per applicable law
3. Default to GDPR/MHMDA-level opt-in for all patients regardless of location.
4. The consent model from 2.2 already supports this -- this service adds jurisdiction awareness.

**Acceptance criteria**:
- Privacy law matrix covers all relevant jurisdictions
- Service can determine applicable laws based on patient location
- Default consent level is opt-in (highest standard)

**Effort**: 1 week

**Dependencies**: 2.2 (consent management)

---

## 3. QA Engineer

### 3.1 Golden Dataset Testing

**Hardening item**: Fixed input documents with clinician-validated expected outputs. 200+ annotated notes, 50+ trial criteria, 200+ patient profiles.

**Files to create**:
- `backend/tests/golden/` -- golden dataset directory
- `backend/tests/golden/clinical_notes/` -- annotated clinical notes (JSON fixtures)
- `backend/tests/golden/trial_criteria/` -- trial criteria with expected parse trees
- `backend/tests/golden/patient_profiles/` -- patient profiles with known eligibility
- `backend/tests/golden/README.md` -- golden dataset documentation
- `backend/tests/test_golden_dataset.py` -- golden dataset test runner
- `backend/tests/conftest_golden.py` -- golden dataset fixtures

**Implementation steps**:
1. **Create initial golden dataset structure**:
   ```
   backend/tests/golden/
     clinical_notes/
       note_001_diabetes_progress.json    # {text, expected_mentions, expected_facts}
       note_002_oncology_consult.json
       note_003_cardiology_discharge.json
       ...
     trial_criteria/
       criteria_001_ad_dupixent.json      # {criteria_json, expected_parse_tree}
       criteria_002_cscc_cemiplimab.json
       ...
     patient_profiles/
       patient_001_eligible_ad.json       # {patient_data, trial_id, expected_eligible}
       patient_002_ineligible_age.json
       patient_003_excluded_cancer.json
       ...
   ```
2. **Clinical note format** (each JSON file):
   ```json
   {
     "id": "note_001",
     "text": "Patient is a 55-year-old male with type 2 diabetes...",
     "note_type": "progress_note",
     "expected_mentions": [
       {"text": "type 2 diabetes", "domain": "Condition", "assertion": "present"},
       {"text": "metformin", "domain": "Drug", "assertion": "present"}
     ],
     "expected_facts": [
       {"concept_name": "Type 2 diabetes mellitus", "domain": "Condition", "omop_concept_id": 201826}
     ]
   }
   ```
3. **Create test runner** `backend/tests/test_golden_dataset.py`:
   - Parametrize tests over all golden dataset files using `pytest.mark.parametrize`
   - For clinical notes: run NLP extraction and compare mentions against expected
   - For trial criteria: parse criteria and compare against expected structure
   - For patient profiles: run eligibility check and compare against expected result
   - Report precision/recall/F1 per category
4. **Seed with initial data**: Start with the existing sample clinical text in `backend/tests/conftest.py:464-500` and the demo trial criteria in `backend/app/services/trial_eligibility_service.py:198-357`.
5. Add `make test-golden` target to Makefile.
6. Add golden dataset tests to CI pipeline in `.github/workflows/ci.yml`.

**Acceptance criteria**:
- Golden dataset directory with at least 20 clinical notes, 10 trial criteria, 20 patient profiles (initial seed; target 200/50/200)
- Test runner reports per-file pass/fail and aggregate precision/recall/F1
- Tests run in CI and block merges when golden dataset regressions occur
- README documents the annotation schema and contribution process

**Effort**: 2-3 weeks (framework + initial seed), ongoing expansion

**Dependencies**: None (can start immediately)

---

### 3.2 OMOP Mapping Regression Suite

**Hardening item**: 500+ curated term-to-concept mappings. Run on every vocabulary update and every PR that touches mapping code.

**Files to create**:
- `backend/tests/golden/omop_mappings/known_mappings.json` -- curated mapping corpus
- `backend/tests/test_omop_mapping_regression.py` -- regression test runner
- `backend/tests/golden/omop_mappings/README.md` -- mapping corpus documentation

**Implementation steps**:
1. **Create curated mapping corpus** `known_mappings.json`:
   ```json
   {
     "version": "1.0.0",
     "mappings": [
       {
         "input_text": "type 2 diabetes mellitus",
         "expected_concept_id": 201826,
         "expected_concept_name": "Type 2 diabetes mellitus",
         "expected_vocabulary": "SNOMED",
         "expected_domain": "Condition",
         "category": "conditions_common"
       },
       {
         "input_text": "hypertension",
         "expected_concept_id": 320128,
         "expected_concept_name": "Essential hypertension",
         "expected_vocabulary": "SNOMED",
         "expected_domain": "Condition",
         "category": "conditions_common"
       },
       {
         "input_text": "metformin",
         "expected_concept_id": 1503297,
         "expected_concept_name": "metformin",
         "expected_vocabulary": "RxNorm",
         "expected_domain": "Drug",
         "category": "drugs_common"
       }
       // ... 500+ entries
     ]
   }
   ```
2. **Create regression test runner** `backend/tests/test_omop_mapping_regression.py`:
   - Load the mapping corpus
   - For each entry, call `BaseMappingService.map_mention()` (or the concrete implementation from `backend/app/services/mapping_db.py`)
   - Assert the top result matches expected concept_id
   - Track and report: total mappings, matched, unmatched, changed (concept_id differs from expected)
   - Fail if matched rate drops below 95%
3. **Categorize mappings** by domain and difficulty:
   - Common conditions (diabetes, hypertension, COPD, etc.)
   - Common drugs (metformin, lisinopril, atorvastatin, etc.)
   - Common procedures (ECG, CT scan, colonoscopy, etc.)
   - Common measurements (HbA1c, blood glucose, creatinine, etc.)
   - Ambiguous terms (cold, discharge, lead, etc.)
   - Abbreviations (DM, HTN, SOB, etc.)
   - Misspellings (diabetis, hipertension, etc.)
4. **CI integration**: Add to `.github/workflows/ci.yml` as a separate job that runs when mapping files change:
   ```yaml
   omop-regression:
     name: OMOP Mapping Regression
     runs-on: ubuntu-latest
     if: contains(github.event.pull_request.changed_files, 'mapping')
     steps:
       - run: uv run pytest tests/test_omop_mapping_regression.py -v
   ```
5. Add `make test-omop-regression` target to Makefile.

**Acceptance criteria**:
- Corpus contains 100+ initial mappings (target 500+)
- Regression test runs on every PR that touches `backend/app/services/mapping*.py`
- Test report shows per-category match rates
- Mapping match rate >= 95% or build fails
- Corpus version is tracked and changes are PR-reviewed

**Effort**: 2 weeks (framework + initial 100 mappings), ongoing expansion

**Dependencies**: OMOP mapping service exists at `backend/app/services/mapping*.py`

---

### 3.3 Eligibility Logic Test Framework

**Hardening item**: Property-based tests: clearly eligible, clearly ineligible, boundary cases, missing data, conflicting data, complex boolean AND/OR/NOT.

**Files to create**:
- `backend/tests/test_eligibility_logic.py` -- eligibility logic tests
- `backend/tests/test_eligibility_property.py` -- property-based tests (hypothesis)
- `backend/tests/fixtures/eligibility/` -- eligibility test fixtures

**Implementation steps**:
1. **Unit tests for criterion evaluation** (`test_eligibility_logic.py`):
   - Test `_criterion_patient_query()` at `trial_eligibility_service.py:373-422` for each criterion type
   - Test `_get_demographic_patient_ids()` at line 424-470 for age boundary cases:
     - `age = 18 exactly` (min_age=18) should match
     - `age = 17.999` should not match
     - `age = 75 exactly` (max_age=75) should match
     - `age = 75.001` should not match
     - Missing birth_date should not match
   - Test `_evaluate_criterion()` at line 676-792 for:
     - High confidence match (confidence > 0.7) returns PASS
     - Medium confidence (0.3-0.7) returns POSSIBLE_MATCH
     - Low confidence (< 0.3) returns UNKNOWN
     - Exclusion criterion match returns FAIL
2. **Integration tests for full screening** (`test_eligibility_logic.py`):
   - Test `check_patient_eligibility()` at line 794-884 with:
     - Patient meeting all inclusion, no exclusion -> eligible=True, score=1.0
     - Patient missing one inclusion -> eligible=False
     - Patient meeting inclusion but triggering exclusion -> eligible=False, score=0.0
     - Patient with missing data -> eligible=False, missing_data populated
3. **Property-based tests** (`test_eligibility_property.py`):
   - Use `hypothesis` library to generate random patient profiles
   - Property: If a patient meets all inclusion criteria and no exclusion criteria, they must be eligible
   - Property: If any exclusion criterion is met, the patient must be ineligible regardless of inclusion
   - Property: Match score must be between 0.0 and 1.0
   - Property: `inclusion_met + missing_data` must equal `inclusion_total`
4. **Fixture data**: Create test fixtures for each demo trial in `trial_eligibility_service.py:198-357`:
   - Atopic Dermatitis trial: 5 clearly eligible, 5 clearly ineligible, 5 boundary
   - CSCC trial: similar
   - DME trial: similar, plus HbA1c value boundary testing
5. These tests require the async database session from `backend/tests/conftest.py:131-143`. Create ClinicalFact fixtures that represent each test patient's clinical data.

**Acceptance criteria**:
- All criterion types tested: demographic, condition, drug, measurement, procedure
- Boundary conditions tested for age and measurement values
- Missing data handling verified (returns UNKNOWN, not crash)
- Property-based tests run 100+ generated cases per property
- Full screening integration test covers all three demo trials
- Tests use the async_session fixture pattern from conftest.py

**Effort**: 2 weeks

**Dependencies**: None (existing test infrastructure supports this)

---

### 3.4 Load Testing

**Hardening item**: Performance under realistic concurrent user loads. 100 simultaneous webhook deliveries, 1000 concurrent API requests.

**Files to create**:
- `backend/tests/load/locustfile.py` -- Locust load test definitions
- `backend/tests/load/README.md` -- load testing documentation
- `backend/tests/load/scenarios/` -- load test scenario configurations

**Implementation steps**:
1. **Install Locust** in dev dependencies (`backend/pyproject.toml`).
2. **Create Locust test scenarios** in `backend/tests/load/locustfile.py`:
   - **Webhook burst**: Simulate 100 simultaneous Metriport webhook deliveries
     - Target: Response time < 500ms p95 (per Metriport 4-second spec)
     - Payload: FHIR Bundle with ~50 entries (realistic Metriport payload)
   - **API concurrent reads**: 1000 concurrent trial screening API requests
     - Target: Response time < 2s p95
   - **Mixed workload**: 70% reads (trial listing, patient data), 20% screening, 10% writes (enrollment)
     - Target: No errors under 500 concurrent users
   - **NLP throughput**: Queue 100 documents and measure processing time
     - Target: < 5s per document average
3. **Baseline measurement**: Run load tests against local Docker stack (`docker compose up`) and record baseline metrics.
4. **Bottleneck identification**: Instrument with timing decorators to identify which stage is slowest:
   - Webhook ingestion -> FHIR import -> NLP processing -> fact building -> screening
5. Add `make load-test` target to Makefile.

**Acceptance criteria**:
- Locust test scenarios cover webhook burst, concurrent reads, mixed workload
- Baseline metrics recorded and documented
- Performance regression threshold defined (e.g., p95 response time cannot increase >20%)
- Bottleneck analysis identifies the slowest pipeline stage

**Effort**: 1 week

**Dependencies**: Docker compose stack (exists)

---

### 3.5 End-to-End Pipeline Tests

**Hardening item**: Document ingestion through NLP through OMOP mapping through fact building through eligibility evaluation. Run on every deploy.

**Files to create**:
- `backend/tests/test_e2e_pipeline.py` -- end-to-end pipeline test
- `backend/tests/fixtures/e2e/` -- E2E test fixtures

**Implementation steps**:
1. **Create E2E test** `backend/tests/test_e2e_pipeline.py`:
   ```python
   @pytest.mark.asyncio
   async def test_full_pipeline_diabetes_patient(async_session):
       """Test full pipeline: FHIR Bundle -> NLP -> OMOP -> Facts -> KG -> Screening."""
       # 1. Create a FHIR Bundle fixture with a diabetes patient
       bundle = load_fixture("e2e/diabetes_patient_bundle.json")

       # 2. Import via FHIRImportService
       service = FHIRImportService()
       result = await service.import_bundle(async_session, bundle, "test-patient-001")
       assert result["success"] is True
       assert result["conditions"] > 0

       # 3. Verify ClinicalFacts were created
       facts = await async_session.execute(
           select(ClinicalFact).where(ClinicalFact.patient_id == "test-patient-001")
       )
       fact_list = facts.scalars().all()
       assert len(fact_list) > 0
       # Verify diabetes condition exists
       diabetes_facts = [f for f in fact_list if "diabetes" in f.concept_name.lower()]
       assert len(diabetes_facts) > 0

       # 4. Verify KG nodes were created
       nodes = await async_session.execute(
           select(KGNode).where(KGNode.patient_id == "test-patient-001")
       )
       assert len(nodes.scalars().all()) > 0

       # 5. Screen against EYLEA HD trial (requires diabetes + DME)
       trial_service = get_trial_service()
       # Find the EYLEA trial
       eylea_trial_id = ...
       eligibility = await trial_service.check_patient_eligibility(
           eylea_trial_id, "test-patient-001", session=async_session
       )
       assert eligibility is not None
       # Patient should match on diabetes but may not have DME
   ```
2. **Create FHIR Bundle fixtures** in `backend/tests/fixtures/e2e/`:
   - `diabetes_patient_bundle.json` -- patient with Type 2 DM, HTN, standard meds
   - `oncology_patient_bundle.json` -- patient with skin cancer
   - `ophthalmology_patient_bundle.json` -- patient with DME + diabetes
   - Model these after the Metriport Bundle format expected by `FHIRImportService.import_bundle()` at `backend/app/services/fhir_import.py:172-307`
3. **Create a separate CI job** for E2E tests that runs after unit tests pass.
4. Add `make test-e2e` target to Makefile.

**Acceptance criteria**:
- E2E test covers: FHIR import -> ClinicalFact creation -> KG creation -> eligibility screening
- At least 3 patient scenarios (diabetes, oncology, ophthalmology) matching the 3 demo trials
- Tests use the async database fixtures from conftest.py
- E2E tests run in CI on every PR (but can be skipped with a label for non-clinical PRs)

**Effort**: 1-2 weeks

**Dependencies**: 3.1 (golden dataset provides the fixture data), existing FHIR import service

---

### 3.6 Security Testing

**Hardening item**: OWASP Top 10 testing, PHI access audit verification, compliance testing for HIPAA technical safeguards.

**Files to create**:
- `backend/tests/security/test_owasp.py` -- OWASP Top 10 tests
- `backend/tests/security/test_phi_audit.py` -- PHI access audit tests
- `backend/tests/security/test_hipaa_safeguards.py` -- HIPAA technical safeguard tests

**Implementation steps**:
1. **OWASP Top 10 tests** (`test_owasp.py`):
   - **Injection**: Test that patient_id, document text, and search queries are properly sanitized. SQLAlchemy ORM (used throughout, e.g., `trial_eligibility_service.py`) provides parameterized queries, but verify no raw SQL.
   - **Broken Authentication**: Test that `AUTH_BYPASS_DEV` is not enabled when `environment=production` in `backend/app/core/config.py`
   - **Sensitive Data Exposure**: Test that API responses do not leak PHI in error messages. Verify that the webhook handler at `backend/app/api/metriport_webhook.py:342-346` does not include patient data in error responses.
   - **XXE**: Test that XML parsing in `FHIRImportService._extract_text_from_ccda()` at `backend/app/services/fhir_import.py:966-997` uses regex (not lxml/xml.etree) so XXE is not applicable.
   - **Broken Access Control**: Test that RBAC permissions from `backend/app/models/rbac.py` are enforced on all PHI endpoints.
   - **Security Misconfiguration**: Test that default credentials are rejected in production mode.
2. **PHI Access Audit tests** (`test_phi_audit.py`):
   - Verify that accessing patient data creates an `AuditLog` entry with `phi_accessed=True`
   - Verify that audit entries include user_id, timestamp, resource_type, resource_id
   - Verify that audit entries cannot be modified (test the immutability from 2.5)
   - Verify that bulk data access (e.g., screening all patients) creates appropriate audit entries
3. **HIPAA Technical Safeguard tests** (`test_hipaa_safeguards.py`):
   - Access controls: verify RBAC enforcement
   - Audit controls: verify audit logging
   - Integrity: verify hash chain (from 2.5)
   - Transmission security: verify TLS configuration in nginx
   - Authentication: verify password hashing, account lockout (in `backend/app/models/rbac.py:183-192`)

**Acceptance criteria**:
- OWASP Top 10 tests cover injection, auth, data exposure, access control, misconfiguration
- PHI audit tests verify every access path creates proper audit entries
- HIPAA technical safeguard tests verify all four categories
- All tests pass in CI

**Effort**: 2 weeks

**Dependencies**: RBAC (exists), Audit logging (exists), Immutability (2.5)

---

## 4. COO

### 4.1 SLA Definitions

**Hardening item**: Response time for webhook ingestion (<500ms), NLP processing (<5s per document), trial matching API (<2s), knowledge graph query (<1s).

**Files to create**:
- `docs/operations/sla_definitions.md` -- SLA specification document
- `backend/app/middleware/sla_monitoring.py` -- SLA monitoring middleware
- `backend/tests/test_sla_compliance.py` -- SLA compliance tests

**Implementation steps**:
1. **Define SLAs** in `docs/operations/sla_definitions.md`:
   | Endpoint/Operation | SLA (p95) | Critical? | Measurement Point |
   |---|---|---|---|
   | Metriport webhook response | < 500ms | Yes | `metriport_webhook.py:316` -> response |
   | NLP document processing | < 5s/doc | Yes | Queue -> fact creation |
   | Trial screening API | < 2s | Yes | `screen_patients()` total |
   | Patient eligibility check | < 2s | Yes | `check_patient_eligibility()` total |
   | KG query | < 1s | No | Graph query endpoints |
   | Health check | < 100ms | Yes | `/health` endpoint |
2. **Create SLA monitoring middleware** `backend/app/middleware/sla_monitoring.py`:
   - FastAPI middleware that records request duration for every endpoint
   - Tags requests with the SLA category (webhook, screening, query, etc.)
   - Logs violations when response time exceeds SLA threshold
   - Exposes metrics for monitoring (Prometheus-compatible if available)
3. **Create SLA compliance tests** `backend/tests/test_sla_compliance.py`:
   - Use `pytest-benchmark` or `time.perf_counter()` to measure response times
   - Test webhook endpoint with realistic payload against < 500ms target
   - Test screening endpoint against < 2s target (note: the service already logs timing at `trial_eligibility_service.py:648-654`)
4. Wire the middleware into `backend/app/main.py`.

**Acceptance criteria**:
- SLA document specifies target for every critical endpoint
- Middleware logs all SLA violations
- Compliance tests verify SLAs are met with empty and seeded databases
- SLA metrics are available for monitoring/alerting

**Effort**: 1 week

**Dependencies**: None

---

### 4.2 Cost Per Patient Processed

**Hardening item**: Infrastructure cost modeling. What does it cost to ingest, extract, map, match one patient?

**Files to create**:
- `docs/operations/cost_model.md` -- cost model document
- `backend/app/services/cost_tracking_service.py` -- resource usage tracking

**Implementation steps**:
1. **Document the cost model** per patient:
   - FHIR Bundle ingestion: compute time for `FHIRImportService.import_bundle()` (IO-bound, ~1-5s)
   - NLP extraction: compute time per document (CPU-bound, varies by document length)
   - OMOP mapping: compute time per mention (~10-50ms per term)
   - KG construction: database writes (IO-bound)
   - Trial screening: SQL queries (~100ms-2s per trial)
   - Storage: bytes per patient across all tables
2. **Create resource tracking** `backend/app/services/cost_tracking_service.py`:
   - Track wall-clock time for each pipeline stage
   - Track database row counts per patient
   - Track storage size estimates per patient
   - Store in a lightweight `pipeline_metrics` table or in-memory aggregation
3. **Compute infrastructure costs** at scale tiers:
   - 10K patients: estimated monthly compute + storage
   - 100K patients: estimated monthly compute + storage
   - 1M patients: estimated monthly compute + storage (identify bottlenecks)
4. The auto-screening path in `metriport_webhook.py:186-199` processes a full patient pipeline -- instrument this as the primary cost measurement point.

**Acceptance criteria**:
- Cost model document with per-patient cost breakdown by pipeline stage
- Resource tracking captures timing and storage per patient
- Scale projections for 10K/100K/1M patients with bottleneck identification

**Effort**: 3-5 days

**Dependencies**: None

---

### 4.3 Capacity Planning

**Hardening item**: Model for 10K, 100K, 1M patients. What's the infrastructure cost at each tier?

**Files to create**:
- `docs/operations/capacity_plan.md` -- capacity planning document

**Implementation steps**:
1. **Profile current resource usage**:
   - Database row counts per patient: ~5 ClinicalFacts + ~5 KGNodes + ~5 KGEdges + ~2 Documents + ~20 Mentions = ~37 rows per patient
   - Storage per patient: estimate ~10KB per patient (structured data)
   - NLP processing: ~5s per document, ~2 documents per patient = ~10s
   - Trial screening: ~500ms per patient per trial, 3 active trials = ~1.5s
2. **Scale projections**:
   | Patients | DB Rows | Storage | NLP Compute (initial) | Screening (per run) |
   |----------|---------|---------|----------------------|-------------------|
   | 10K | 370K | 100MB | 28 hours | 4 hours |
   | 100K | 3.7M | 1GB | 280 hours | 42 hours |
   | 1M | 37M | 10GB | 2,800 hours | 417 hours |
3. **Identify bottlenecks**:
   - NLP processing is CPU-bound and scales linearly -- needs queue-based horizontal scaling
   - Database can handle 37M rows but needs proper indexing (check existing indexes)
   - Trial screening is N*M (patients * trials) -- needs caching/batching
   - In-memory trial storage (`_trials dict` at `trial_eligibility_service.py:190`) doesn't scale -- need database-backed storage
4. **Recommend infrastructure**:
   - 10K: Single-server Docker Compose (current setup)
   - 100K: Managed PostgreSQL (RDS), Redis cluster, 2-4 worker processes
   - 1M: Kubernetes deployment, read replicas, dedicated NLP workers, connection pooling

**Acceptance criteria**:
- Capacity plan with projections at 3 scale tiers
- Bottleneck analysis with remediation recommendations
- Infrastructure cost estimates per tier
- Scale-limiting factors clearly identified

**Effort**: 3-5 days

**Dependencies**: 4.2 (cost per patient data feeds into this)

---

### 4.4 Incident Response Runbooks

**Hardening item**: Data pipeline stall, NLP degradation, FHIR webhook outage, database failover, auth system failure.

**Files to create**:
- `docs/operations/runbooks/pipeline_stall.md`
- `docs/operations/runbooks/nlp_degradation.md`
- `docs/operations/runbooks/webhook_outage.md`
- `docs/operations/runbooks/database_failover.md`
- `docs/operations/runbooks/auth_failure.md`
- `docs/operations/runbooks/README.md`

**Implementation steps**:
1. **Pipeline Stall Runbook**:
   - Detection: Redis queue depth increasing, no workers consuming jobs
   - Diagnosis: Check `backend/scripts/run_worker.sh` process, Redis connectivity, worker logs
   - Resolution: Restart workers, check for poison messages, verify Redis health
   - Recovery: Re-queue failed jobs, verify data consistency
2. **NLP Degradation Runbook**:
   - Detection: Unmapped term rate > 5%, extraction confidence scores dropping
   - Diagnosis: Check vocabulary service (`backend/app/services/vocabulary.py`), NLP model health
   - Resolution: Reload vocabulary, restart NLP service, rollback model if canary deployment
   - Recovery: Re-process affected documents, run golden dataset verification
3. **Webhook Outage Runbook**:
   - Detection: Metriport reports delivery failures, no webhook logs in `metriport_webhook.py`
   - Diagnosis: Check nginx, FastAPI process, signature verification configuration
   - Resolution: Restart services, verify `metriport_webhook_key` in settings
   - Recovery: Metriport retries automatically; verify no duplicate processing via `_check_dedup()` at line 282
4. **Database Failover Runbook**:
   - Detection: Connection errors from SQLAlchemy, health check failing
   - Diagnosis: Check PostgreSQL process, disk space, connection limits
   - Resolution: Failover to replica (if available), restart PostgreSQL
   - Recovery: Verify data consistency, run IQ check
5. **Auth Failure Runbook**:
   - Detection: 401/403 errors spiking, user login failures
   - Diagnosis: Check JWT secret, token expiration, `RefreshToken` table
   - Resolution: Rotate JWT secret if compromised, clear expired tokens
   - Recovery: Force re-authentication for all users

**Acceptance criteria**:
- Each runbook has: detection, diagnosis, resolution, recovery sections
- Runbooks reference specific code paths and configuration files
- Each runbook has an estimated MTTR (Mean Time to Resolve)
- Runbooks are reviewed by engineering team

**Effort**: 3-5 days

**Dependencies**: None

---

### 4.5 Disaster Recovery

**Hardening item**: RPO/RTO defined and tested. Backup encryption. Multi-region capability assessment.

**Files to create**:
- `docs/operations/disaster_recovery_plan.md`
- `backend/scripts/backup.sh` -- automated backup script
- `backend/scripts/restore.sh` -- restore verification script

**Implementation steps**:
1. **Define RPO/RTO**:
   - **RPO (Recovery Point Objective)**: 1 hour -- maximum acceptable data loss
   - **RTO (Recovery Time Objective)**: 4 hours -- maximum acceptable downtime
   - These align with healthcare SaaS industry standards
2. **Backup strategy**:
   - PostgreSQL: Continuous WAL archiving (for point-in-time recovery) + daily full backups
   - Redis: AOF persistence + RDB snapshots
   - Neo4j (if used): Graph database dump
   - Application configuration: Git-tracked (already version controlled)
   - Create `backend/scripts/backup.sh` that orchestrates all backup operations
3. **Backup encryption**:
   - All backups encrypted at rest using AES-256
   - Backup encryption keys stored separately from backup data
   - Key rotation schedule: every 90 days
4. **Restore testing**:
   - Create `backend/scripts/restore.sh` that:
     - Restores from the latest backup
     - Runs IQ check (from 1.3) to verify installation
     - Runs a subset of golden dataset tests (from 3.1) to verify data integrity
     - Reports success/failure
5. **Multi-region assessment**:
   - Current: Single-region Docker Compose deployment
   - Assessment: PostgreSQL supports streaming replication; Redis supports sentinel/cluster
   - Recommendation: Managed services (RDS Multi-AZ, ElastiCache) for production

**Acceptance criteria**:
- RPO (1h) and RTO (4h) defined and documented
- Backup script covers all data stores
- Restore script verifies data integrity post-restore
- DR plan is tested quarterly (documented in runbook)

**Effort**: 1 week

**Dependencies**: 1.3 (IQ check script used for restore verification)

---

## 5. FHIR Integration Specialist

### 5.1 FHIR R4 Resource Validation

**Hardening item**: Strict validation on Metriport webhook payloads. Reject malformed resources with detailed error logging (but never log PHI in errors).

**Files to create**:
- `backend/app/services/fhir_validator.py` -- FHIR resource validator
- `backend/tests/test_fhir_validator.py` -- validator tests
- `backend/tests/fixtures/fhir/` -- FHIR test fixtures (valid and invalid)

**Implementation steps**:
1. **Create FHIR validator** `backend/app/services/fhir_validator.py`:
   ```python
   class FHIRValidationResult:
       is_valid: bool
       errors: list[str]  # errors must NOT contain PHI
       warnings: list[str]
       resource_type: str | None
       resource_id: str | None  # safe to log: FHIR resource IDs are not PHI

   class FHIRValidator:
       def validate_bundle(self, bundle: dict) -> FHIRValidationResult:
           """Validate a FHIR R4 Bundle."""
           # Check resourceType == "Bundle"
           # Check bundle.type is valid (transaction, batch, etc.)
           # Validate each entry has a resource with resourceType
           # Validate required fields per resource type

       def validate_resource(self, resource: dict) -> FHIRValidationResult:
           """Validate a single FHIR R4 resource."""
           # Dispatch to type-specific validators

       def _validate_patient(self, resource: dict) -> list[str]:
           # Require: name, gender, birthDate
       def _validate_condition(self, resource: dict) -> list[str]:
           # Require: code, subject
       def _validate_observation(self, resource: dict) -> list[str]:
           # Require: code, subject, status
       def _validate_medication_request(self, resource: dict) -> list[str]:
           # Require: medicationCodeableConcept or medicationReference, subject
       # ... for each resource type in the handler_map at fhir_import.py:267-276
   ```
2. **Integrate into the import pipeline**: Modify `FHIRImportService.import_bundle()` at `backend/app/services/fhir_import.py:172`:
   - Validate the bundle before processing
   - Log validation errors (without PHI)
   - For invalid resources: quarantine (skip + log) rather than crash
   - This aligns with the existing `try/except` at line 298-303 but adds structured validation
3. **Integrate into webhook handler**: Call validation in `_process_consolidated_data()` at `backend/app/api/metriport_webhook.py:109` before import.
4. **PHI-safe error logging**: Ensure error messages only reference FHIR resource types and IDs, never patient names, MRNs, or clinical data. The existing `logger.warning()` at `fhir_import.py:300-303` already follows this pattern -- extend to validation errors.
5. **Test with malformed payloads**:
   - Bundle with missing Patient resource
   - Condition with missing code
   - Observation with invalid status
   - Bundle with non-UTF8 encoded data
   - Bundle with deeply nested structure (DoS prevention)

**Acceptance criteria**:
- Validator covers all 8 resource types in the handler_map
- Malformed resources are quarantined, not crashed on
- Error messages never contain PHI
- Validation results are logged and available for monitoring
- Test suite covers 20+ malformed payload variants

**Effort**: 1-2 weeks

**Dependencies**: None

---

### 5.2 Resource Mapping Completeness

**Hardening item**: Verify handling of Patient, Condition, Observation, MedicationRequest, DiagnosticReport, DocumentReference, Encounter, Procedure, AllergyIntolerance, Immunization.

**Files to modify**:
- `backend/app/services/fhir_import.py` -- add Encounter, Immunization handlers

**Files to create**:
- `backend/tests/test_fhir_import_completeness.py` -- resource coverage tests

**Implementation steps**:
1. **Audit current handler coverage** against the hardening requirement:
   | Resource Type | Handler Exists? | Location |
   |---|---|---|
   | Patient | Yes | `fhir_import.py:236-248` (inline in import_bundle) |
   | Condition | Yes | `fhir_import.py:518-588` (_import_condition) |
   | Observation | Yes | `fhir_import.py:747-838` (_import_observation) |
   | MedicationRequest | Yes | `fhir_import.py:590-659` (_import_medication) |
   | MedicationStatement | Yes | `fhir_import.py:309-370` (_import_medication_statement) |
   | DiagnosticReport | Yes | `fhir_import.py:1177-1345` (_import_diagnostic_report) |
   | DocumentReference | Yes | `fhir_import.py:1058-1175` (_import_document_reference) |
   | Procedure | Yes | `fhir_import.py:840-911` (_import_procedure) |
   | AllergyIntolerance | Yes | `fhir_import.py:661-745` (_import_allergy) |
   | **Encounter** | **NO** | Need to add |
   | **Immunization** | **NO** | Need to add |
2. **Add Encounter handler** `_import_encounter()`:
   - Extract: period (start/end), type, serviceType, reasonCode, location
   - Create ClinicalFact with domain=OBSERVATION
   - Create KGNode with node_type=VISIT (if NodeType exists) or OBSERVATION
   - Add to handler_map at line 267
3. **Add Immunization handler** `_import_immunization()`:
   - Extract: vaccineCode, occurrenceDateTime, status, manufacturer
   - Create ClinicalFact with domain=DRUG (immunizations map to Drug domain in OMOP)
   - Create KGNode with node_type=DRUG
   - Add to handler_map at line 267
4. **Create completeness tests** `backend/tests/test_fhir_import_completeness.py`:
   - For each of the 10 resource types, create a minimal valid FHIR resource
   - Import a bundle containing all 10 types
   - Verify that all resources are processed (none in `skipped_resource_types`)
   - Verify correct ClinicalFact domain for each resource type

**Acceptance criteria**:
- All 10 resource types from the hardening requirement are handled
- No resource types appear in `skipped_resource_types` for a complete bundle
- Each handler creates appropriate ClinicalFact and KGNode entries
- Tests verify all 10 resource types

**Effort**: 3-5 days

**Dependencies**: None

---

### 5.3 Bundle Processing

**Hardening item**: Proper handling of Transaction vs Batch bundles. Reference resolution within bundles.

**Files to modify**:
- `backend/app/services/fhir_import.py` -- add bundle type handling and reference resolution

**Files to create**:
- `backend/tests/test_fhir_bundle_processing.py` -- bundle processing tests

**Implementation steps**:
1. **Bundle type handling**: Currently `import_bundle()` at `fhir_import.py:172` only checks `resourceType == "Bundle"`. Add handling for `bundle.type`:
   - `transaction`: All entries succeed or all fail (wrap in a transaction -- already using `session.commit()` at line 305)
   - `batch`: Each entry processed independently (current behavior, continue on error per line 298-303)
   - `collection`: Read-only collection of resources (current behavior works)
   - `document`: Clinical document bundle (extract composition resource)
2. **Reference resolution**: FHIR Bundles use relative references (e.g., `"subject": {"reference": "Patient/abc123"}`). Currently the code extracts patient_id from the Patient resource. Add a reference map:
   ```python
   # Build reference map: fullUrl -> resource
   reference_map = {}
   for entry in entries:
       full_url = entry.get("fullUrl", "")
       resource = entry.get("resource", {})
       if full_url:
           reference_map[full_url] = resource
       # Also map by resourceType/id
       rid = resource.get("id", "")
       rtype = resource.get("resourceType", "")
       if rid and rtype:
           reference_map[f"{rtype}/{rid}"] = resource
   ```
   - Use reference_map to resolve `medicationReference` (when MedicationRequest references a Medication resource instead of using `medicationCodeableConcept`)
   - Use reference_map to resolve `DiagnosticReport.result` references to Observation resources
3. **Test bundle types**:
   - Transaction bundle: all succeed or all fail
   - Batch bundle: partial failures don't block other entries
   - Bundle with internal references: verify resolution

**Acceptance criteria**:
- Bundle type is respected (transaction = all-or-nothing)
- Internal references are resolved within the bundle
- Unresolvable references are logged as warnings, not errors
- Tests cover transaction, batch, and collection bundle types

**Effort**: 3-5 days

**Dependencies**: None

---

### 5.4 Error Handling and Graceful Degradation

**Hardening item**: When Metriport sends non-conformant bundles, quarantine and continue, don't crash.

**Files to modify**:
- `backend/app/services/fhir_import.py` -- enhance error handling
- `backend/app/api/metriport_webhook.py` -- add quarantine logic

**Files to create**:
- `backend/app/models/fhir_quarantine.py` -- quarantine model
- `backend/tests/test_fhir_quarantine.py` -- quarantine tests

**Implementation steps**:
1. **Create quarantine model** `backend/app/models/fhir_quarantine.py`:
   ```python
   class FHIRQuarantineRecord(Base):
       __tablename__ = "fhir_quarantine"
       source: str  # "metriport", "manual", etc.
       bundle_type: str | None
       resource_type: str | None
       resource_id: str | None  # FHIR resource ID (not PHI)
       error_type: str  # "validation", "processing", "reference"
       error_message: str  # PHI-free error description
       raw_payload_hash: str  # SHA-256 hash of the raw payload (for dedup)
       patient_id: str | None  # internal patient ID (for correlation)
       status: str  # "quarantined", "retried", "resolved", "discarded"
       retry_count: int = 0
       resolved_at: datetime | None
   ```
2. **Enhance `import_bundle()` error handling**: The existing `try/except` at `fhir_import.py:298-303` catches per-resource errors. Enhance to:
   - Create a `FHIRQuarantineRecord` for each failed resource
   - Continue processing remaining resources (already done)
   - Return quarantine count in the result summary
3. **Enhance webhook handler**: In `_process_consolidated_data()` at `metriport_webhook.py:109`:
   - Wrap the entire import in try/except
   - On total failure (e.g., bundle parse error), quarantine the entire payload
   - On partial failure, quarantine individual resources
4. **Quarantine review API**: Add endpoints to `backend/app/api/compliance.py`:
   - `GET /api/v1/fhir/quarantine` -- list quarantined items
   - `POST /api/v1/fhir/quarantine/{id}/retry` -- retry processing
   - `POST /api/v1/fhir/quarantine/{id}/discard` -- mark as discarded
5. **Test scenarios**:
   - Completely malformed JSON payload
   - Valid JSON but invalid FHIR structure
   - Bundle with mix of valid and invalid resources
   - Resource with missing required fields
   - Resource with unexpected field types

**Acceptance criteria**:
- Non-conformant resources are quarantined, not crashed on
- Valid resources in the same bundle are still processed
- Quarantine records are created with PHI-free error messages
- Quarantine items can be reviewed, retried, or discarded via API
- Webhook always returns 200 to Metriport (per spec) even on processing errors

**Effort**: 1 week

**Dependencies**: 5.1 (FHIR validator provides the validation logic)

---

### 5.5 Terminology Translation

**Hardening item**: ICD-10 to SNOMED to OMOP concept mapping must handle all common terminologies.

**Files to modify**:
- `backend/app/services/fhir_import.py` -- enhance terminology handling
- `backend/app/services/mapping_db.py` -- add cross-terminology resolution

**Files to create**:
- `backend/tests/test_terminology_translation.py` -- terminology tests

**Implementation steps**:
1. **Audit current terminology handling**: The `_get_code_from_codeable_concept()` at `fhir_import.py:136-155` extracts the first coding from a CodeableConcept. This is insufficient because:
   - A CodeableConcept may have multiple codings (ICD-10 + SNOMED for the same concept)
   - The first coding may not be the most specific
   - Some terminologies need translation before OMOP mapping
2. **Enhance CodeableConcept handling**:
   ```python
   def _get_best_coding(self, codeable_concept: dict) -> tuple[str, str, str]:
       """Extract the best coding from a CodeableConcept.

       Priority: SNOMED > LOINC > RxNorm > ICD-10 > other
       """
       codings = codeable_concept.get("coding", [])
       priority = {
           "http://snomed.info/sct": 1,
           "http://loinc.org": 2,
           "http://www.nlm.nih.gov/research/umls/rxnorm": 3,
           "http://hl7.org/fhir/sid/icd-10-cm": 4,
       }
       sorted_codings = sorted(codings, key=lambda c: priority.get(c.get("system", ""), 99))
       if sorted_codings:
           c = sorted_codings[0]
           return c.get("code"), c.get("display"), c.get("system")
       return None, codeable_concept.get("text"), None
   ```
3. **Cross-terminology mapping**: When the source coding is ICD-10 but the mapping service expects SNOMED, provide a translation layer:
   - Use the OMOP concept_relationship table (if loaded) to find ICD-10 -> SNOMED mappings
   - Alternatively, maintain a curated ICD-10 -> SNOMED mapping table for common codes
   - This integrates with the mapping service at `backend/app/services/mapping_db.py`
4. **Test with real-world variety**: Create test fixtures with CodeableConcepts containing:
   - Single SNOMED coding (simple case)
   - Single ICD-10 coding (requires translation)
   - Multiple codings (SNOMED + ICD-10 for same concept)
   - Coding with display text but no code (text-only mapping)
   - Coding with unknown terminology system

**Acceptance criteria**:
- CodeableConcept handler prioritizes most specific coding
- ICD-10 codes are translated to OMOP concepts
- Multi-coding resources use the highest-priority coding
- Tests cover 5+ terminology systems
- Unknown terminologies fall back to text-based mapping gracefully

**Effort**: 1 week

**Dependencies**: OMOP mapping service (exists)

---

### 5.6 Provenance Tracking

**Hardening item**: Every data element traces back to specific FHIR resource + element path.

**Files to modify**:
- `backend/app/models/clinical_fact.py` -- add provenance fields
- `backend/app/services/fhir_import.py` -- populate provenance during import

**Files to create**:
- `backend/tests/test_fhir_provenance.py` -- provenance tests

**Implementation steps**:
1. **Extend ClinicalFact model**: Check current model at `backend/app/models/clinical_fact.py`. Add provenance fields if not present:
   ```python
   # FHIR provenance tracking
   source_fhir_resource_type: Mapped[str | None]  # "Condition", "Observation", etc.
   source_fhir_resource_id: Mapped[str | None]     # FHIR resource ID
   source_fhir_element_path: Mapped[str | None]    # "code.coding[0]", "valueQuantity.value"
   source_system: Mapped[str | None]               # "metriport_hie", "manual", "nlp"
   ```
   Note: The existing code already stores `fhir_id` in KGNode.properties (e.g., `fhir_import.py:568`). This formalizes it as a first-class field on ClinicalFact.
2. **Populate provenance during FHIR import**: In each import handler, set the provenance fields:
   - `_import_condition()`: source_fhir_resource_type="Condition", source_fhir_element_path="code.coding[0]"
   - `_import_medication()`: source_fhir_resource_type="MedicationRequest", source_fhir_element_path="medicationCodeableConcept.coding[0]"
   - `_import_observation()`: source_fhir_resource_type="Observation", source_fhir_element_path="valueQuantity.value" (for the value)
   - etc. for all handlers
3. **Provenance query API**: Add an endpoint to retrieve the full provenance chain for a ClinicalFact:
   - `GET /api/v1/facts/{id}/provenance` -- returns source FHIR resource type, ID, element path, and timestamp
4. **Test provenance tracking**:
   - Import a FHIR Bundle
   - Query ClinicalFacts and verify all have populated provenance fields
   - Verify that the FHIR resource ID matches the original bundle entry
   - Verify the element path accurately describes where the data came from

**Acceptance criteria**:
- Every ClinicalFact created from FHIR import has provenance fields populated
- Provenance includes: resource type, resource ID, element path, source system
- API can retrieve provenance for any clinical fact
- Tests verify provenance completeness after bundle import

**Effort**: 3-5 days

**Dependencies**: None (existing model can be extended via Alembic migration)

---

## Implementation Priority Summary

| Phase | Items | Timeline | Key Deliverables |
|-------|-------|----------|-----------------|
| **Phase 1: Foundations** | 1.1, 1.2, 2.5, 3.1, 5.1, 5.4 | Weeks 1-4 | Regulatory determination, intended use, audit immutability, golden dataset framework, FHIR validation, error quarantine |
| **Phase 2: Clinical Safety** | 1.4, 1.5, 1.7, 3.3, 5.2, 5.6 | Weeks 4-8 | Change control, CAPA system, risk assessment, eligibility testing, resource completeness, provenance |
| **Phase 3: Compliance** | 2.1, 2.2, 2.4, 2.6, 3.2, 5.5 | Weeks 6-12 | BAA framework, consent management, right-to-deletion, IRB framework, OMOP regression, terminology |
| **Phase 4: Operations** | 4.1, 4.2, 4.3, 4.4, 4.5, 3.4, 3.5 | Weeks 8-14 | SLAs, cost model, capacity plan, runbooks, DR, load testing, E2E tests |
| **Phase 5: Hardening** | 1.3, 1.6, 1.8, 2.3, 2.7, 3.6, 5.3 | Weeks 12-20 | IQ/OQ/PQ, traceability, SaMD contingency, DUAs, privacy matrix, security testing, bundle processing |

**Total estimated effort**: 20-28 weeks with 2-3 engineers

---

*Generated from codebase analysis of `/Users/alexstinard/projects/brainstorm/jan-14-2026/` on 2026-02-08.*
*Cross-references: `docs/HARDENING_PLAN.md`, `docs/research/03_quality_compliance_research.md`*
