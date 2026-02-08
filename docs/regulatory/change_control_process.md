# Change Control Process - Standard Operating Procedure

**Document ID:** VP-Quality-1-CCP
**Version:** 1.0
**Last Updated:** 2026-02-08
**Classification:** CONFIDENTIAL - Internal Use Only
**Owner:** VP of Quality / Engineering Lead
**Approval Status:** DRAFT - Pending Review
**Effective Date:** Upon approval

---

## 1. Purpose

This document establishes the change control process for the Clinical Ontology Normalizer Trial Matching Module. It ensures that all changes to the system are evaluated for clinical safety, regulatory, security, and data integrity impact before implementation, and that appropriate documentation, testing, and approval are completed.

This process supports:
- Maintenance of the CDS exemption under 21st Century Cures Act Section 520(o)(1)
- Compliance with ICH E6(R2) GCP requirements for computerized systems
- HIPAA Security Rule requirements for change management (45 CFR 164.312)
- Software quality best practices aligned with IEC 62304

---

## 2. Scope

This process applies to all changes to:
- Backend application code (`backend/`)
- Frontend application code (`frontend/`)
- Database schema and migrations
- Infrastructure configuration (`docker-compose*.yml`, `k8s/`, `nginx/`)
- NLP extraction patterns and dictionaries
- OMOP mapping tables and vocabularies
- Trial eligibility criteria configuration
- System configuration and environment variables
- Third-party library dependencies
- API contracts and schemas

---

## 3. Change Categories

### 3.1 Category Definitions

| Category | Description | Examples | Approval Level | Testing Requirements |
|---|---|---|---|---|
| **Critical** | Changes with potential clinical safety impact or that could alter the system's regulatory classification | Modifications to eligibility scoring logic; changes to safety hard-stop mechanism; removal or weakening of CDS Criterion 4 controls; changes to NLP assertion classification (negation detection) | VP Quality + CMO + Engineering Lead | Full regression + targeted safety tests + clinical validation |
| **Major** | Feature additions or significant modifications that change system behavior but do not directly impact clinical safety | New eligibility criterion types; new data import sources; new UI features for trial management; API endpoint additions; FHIR resource handler additions | Engineering Lead + Product Manager | Full regression + feature-specific tests + integration tests |
| **Minor** | Bug fixes, performance improvements, and minor enhancements that do not change clinical output | Performance optimization; logging improvements; UI styling fixes; error message improvements; dependency security patches | Engineering Lead (or delegate) | Targeted tests for affected component + smoke tests |
| **Cosmetic** | Changes with no functional impact | Documentation updates; code comments; internal refactoring with no behavior change; test additions | Engineering Lead (or delegate) | Verify no behavior change (existing tests pass) |

### 3.2 Category Determination Flowchart

```
Does the change affect eligibility screening output?
  |
  +-- YES --> Does it affect safety controls (hard stops, CDS flags, assertions)?
  |             |
  |             +-- YES --> CRITICAL
  |             |
  |             +-- NO  --> Does it change scoring, matching, or criterion evaluation logic?
  |                           |
  |                           +-- YES --> CRITICAL
  |                           +-- NO  --> MAJOR
  |
  +-- NO  --> Does it add new features or change user-facing behavior?
                |
                +-- YES --> MAJOR
                |
                +-- NO  --> Does it fix a bug or improve performance?
                              |
                              +-- YES --> MINOR
                              +-- NO  --> COSMETIC
```

---

## 4. Change Request Template

### 4.1 Change Request Form

Every change must be documented with the following information before implementation begins:

```
CHANGE REQUEST
==============

CR Number:          CR-YYYY-NNN (auto-assigned)
Date Submitted:     YYYY-MM-DD
Submitter:          [Name / Role]
Change Category:    [ ] Critical  [ ] Major  [ ] Minor  [ ] Cosmetic

Title:              [Brief descriptive title]

Description:
  [Detailed description of the proposed change, including what will be
   modified and why]

Justification:
  [Why is this change needed? Link to issue/ticket/requirement]

Affected Components:
  [ ] Backend - Eligibility Service
  [ ] Backend - NLP Pipeline
  [ ] Backend - FHIR Import
  [ ] Backend - OMOP Mapping
  [ ] Backend - Data Models/Schemas
  [ ] Backend - API Endpoints
  [ ] Backend - Job Queue/Workers
  [ ] Frontend - Trial Matching UI
  [ ] Frontend - Evidence Display
  [ ] Frontend - Dashboard/Analytics
  [ ] Database Schema
  [ ] Infrastructure/Deployment
  [ ] Configuration
  [ ] Dependencies
  [ ] Other: _______________

Impact Assessment: (see Section 5 checklist)

Rollback Plan:
  [How will this change be reverted if issues are discovered?]

Target Release:     [Version / Sprint / Date]
```

---

## 5. Impact Assessment Checklist

Every change request must complete this checklist. Any "YES" answer in the Clinical Safety or Regulatory sections automatically elevates the change to at minimum MAJOR category, and may require CRITICAL classification.

### 5.1 Clinical Safety Impact

| # | Question | Yes/No | If Yes, Details |
|---|---|---|---|
| CS-1 | Does this change modify how patients are screened for eligibility? | | |
| CS-2 | Does this change affect the safety hard-stop mechanism (safety_blocked, CMO-5)? | | |
| CS-3 | Does this change modify NLP assertion classification (negation, temporality, experiencer)? | | |
| CS-4 | Does this change affect confidence scoring or threshold values? | | |
| CS-5 | Does this change modify exclusion criterion evaluation logic? | | |
| CS-6 | Does this change affect the CDS disclaimer text or requires_clinician_review flag? | | |
| CS-7 | Could this change cause a previously blocked patient to appear as eligible? | | |
| CS-8 | Could this change cause a previously eligible patient to be missed? | | |
| CS-9 | Does this change affect auto-screening behavior? | | |
| CS-10 | Does this change modify the match score calculation? | | |

**If ANY CS question is answered YES: Change category is CRITICAL. CMO review required.**

### 5.2 Regulatory Impact

| # | Question | Yes/No | If Yes, Details |
|---|---|---|---|
| RG-1 | Does this change alter the intended use of the system? | | |
| RG-2 | Does this change add medical image or signal processing capabilities? | | |
| RG-3 | Does this change enable autonomous clinical decisions without clinician review? | | |
| RG-4 | Does this change modify the system's CDS Criterion 4 transparency features? | | |
| RG-5 | Does this change affect patient-facing functionality? | | |
| RG-6 | Does this change affect the system's interaction with FDA-regulated data (e.g., 21 CFR Part 11)? | | |
| RG-7 | Could this change affect the CDS exemption status? | | |

**If RG-1, RG-2, RG-3, or RG-7 is YES: STOP. Consult Regulatory Affairs before proceeding. The change may require a regulatory re-determination.**

### 5.3 Security Impact

| # | Question | Yes/No | If Yes, Details |
|---|---|---|---|
| SC-1 | Does this change modify authentication or authorization logic? | | |
| SC-2 | Does this change affect PHI data handling, storage, or transmission? | | |
| SC-3 | Does this change add new external service integrations or API endpoints? | | |
| SC-4 | Does this change modify data encryption or access controls? | | |
| SC-5 | Does this change introduce new third-party dependencies? | | |
| SC-6 | Does this change affect audit logging or trail integrity? | | |

**If ANY SC question is answered YES: Security review required before approval.**

### 5.4 Data Integrity Impact

| # | Question | Yes/No | If Yes, Details |
|---|---|---|---|
| DI-1 | Does this change modify database schema or migrations? | | |
| DI-2 | Does this change affect ClinicalFact creation, modification, or deletion? | | |
| DI-3 | Does this change modify FHIR import data transformation logic? | | |
| DI-4 | Does this change affect data lineage tracking? | | |
| DI-5 | Does this change modify pipeline version stamping? | | |
| DI-6 | Could this change cause data loss or corruption? | | |
| DI-7 | Does this change affect data backup or recovery? | | |

**If DI-6 is YES: Change category is at minimum MAJOR. Data migration plan required.**

---

## 6. Approval Workflow

### 6.1 Approval Matrix

| Change Category | Approver(s) | Approval Method |
|---|---|---|
| **Critical** | VP Quality AND Chief Medical Officer AND Engineering Lead | Formal sign-off (documented in CR) |
| **Major** | Engineering Lead AND Product Manager | Pull request approval + CR sign-off |
| **Minor** | Engineering Lead (or designated delegate) | Pull request approval |
| **Cosmetic** | Any senior engineer | Pull request approval |

### 6.2 Approval Process

```
1. Submitter creates Change Request (CR) with impact assessment
                    |
2. Category auto-determined from impact assessment answers
                    |
3. CR routed to appropriate approver(s) based on category
                    |
4. Approver(s) review:
   - Change description and justification
   - Impact assessment responses
   - Rollback plan
   - Test plan
                    |
5. Approver decision:
   +-- APPROVED  --> Proceed to implementation
   +-- APPROVED WITH CONDITIONS --> Implement with specified constraints
   +-- RETURNED --> Revise and resubmit
   +-- REJECTED --> Change not implemented (document rationale)
                    |
6. Implementation (see Section 7)
                    |
7. Testing (see Section 8)
                    |
8. Release approval (see Section 9)
                    |
9. Post-deployment verification (see Section 10)
```

### 6.3 Emergency Changes

For production-critical issues requiring immediate resolution:

1. Engineering Lead (or on-call engineer) may implement the fix immediately
2. CR must be created retrospectively within 24 hours
3. Full impact assessment completed within 48 hours
4. If the emergency change is determined to be CRITICAL category, CMO and VP Quality review within 72 hours
5. Emergency changes that affect clinical safety controls require follow-up validation testing within one week

---

## 7. Implementation Requirements

### 7.1 Code Change Requirements

| Category | Requirements |
|---|---|
| **Critical** | Feature branch; code review by 2 senior engineers; paired programming recommended; no self-merge |
| **Major** | Feature branch; code review by 1 senior engineer; no self-merge |
| **Minor** | Feature branch; code review by 1 engineer |
| **Cosmetic** | Feature branch; standard review process |

### 7.2 Documentation Requirements

| Category | Requirements |
|---|---|
| **Critical** | Update CLAUDE.md if architecture changes; update regulatory docs if scope changes; update FMEA if new failure modes identified; update intended use statement if applicable; detailed commit messages; release notes |
| **Major** | Update relevant design docs; release notes; API changelog if endpoints change |
| **Minor** | Commit messages; bug fix notes |
| **Cosmetic** | Commit messages |

### 7.3 CDS Criterion 4 Preservation Checklist (Critical Changes Only)

For any CRITICAL change, verify the following before approval:

- [ ] `requires_clinician_review` field still hardcoded to `True` in `backend/app/schemas/trial.py`
- [ ] `CDS_DISCLAIMER` constant still present and unchanged in `backend/app/schemas/trial.py`
- [ ] All `PatientEligibility` responses still include `review_disclaimer`
- [ ] All `ScreeningResponse` objects still include `cds_disclaimer`
- [ ] Safety block logic (`safety_blocked`) still forces `score = 0.0` and `eligible = False`
- [ ] Safety block cannot be overridden via API or configuration
- [ ] Per-criterion `evidence_summary` and `confidence_explanation` fields still populated
- [ ] Frontend `MatchExplanation` component still renders evidence details
- [ ] No new autonomous enrollment pathway introduced

---

## 8. Testing Requirements

### 8.1 Testing Matrix

| Category | Unit Tests | Integration Tests | Regression Suite | Clinical Validation | Performance Tests |
|---|---|---|---|---|---|
| **Critical** | Required (new + existing) | Required | Full suite | Required (known patient-trial pairs) | If performance-relevant |
| **Major** | Required (new + existing) | Required | Full suite | Recommended | If performance-relevant |
| **Minor** | Required (affected component) | Recommended | Smoke tests | Not required | Not required |
| **Cosmetic** | Existing must pass | Not required | Existing must pass | Not required | Not required |

### 8.2 Clinical Validation Test Cases (Critical Changes)

For CRITICAL changes affecting eligibility screening:

1. **Known Eligible Patient**: Verify patient with all inclusion criteria met and no exclusion triggers is correctly identified as eligible (match_score > 0.5, eligible = True)
2. **Known Ineligible Patient (Exclusion)**: Verify patient with documented contraindication triggers safety block (safety_blocked = True, score = 0.0, eligible = False)
3. **Known Ineligible Patient (Missing Inclusion)**: Verify patient missing required inclusion criteria is not flagged as eligible
4. **Incomplete Data Patient**: Verify patient with missing clinical domains shows appropriate UNKNOWN status and data completeness < 1.0
5. **Edge Case: Negated Condition**: Verify a negated condition (e.g., "no evidence of cancer") does not trigger an exclusion criterion
6. **Edge Case: Historical Condition**: Verify a resolved historical condition is handled appropriately based on trial requirements
7. **Safety Block Enforcement**: Verify safety-blocked patient cannot be auto-enrolled and appears with safety block indicators in UI

### 8.3 Test Environment Requirements

| Category | Environment |
|---|---|
| **Critical** | Full staging environment with production-equivalent data volume |
| **Major** | Staging environment |
| **Minor** | Development/CI environment |
| **Cosmetic** | CI environment |

---

## 9. Release Procedures

### 9.1 Pre-Release Checklist

- [ ] All CR approvals obtained and documented
- [ ] All required tests passed
- [ ] No unresolved CRITICAL or HIGH-severity defects
- [ ] Release notes prepared
- [ ] Rollback procedure verified
- [ ] Database migration tested (if applicable)
- [ ] CDS Criterion 4 preservation checklist completed (if CRITICAL change)
- [ ] Deployment runbook reviewed

### 9.2 Release Approval

| Category | Release Approval |
|---|---|
| **Critical** | VP Quality + Engineering Lead explicit sign-off |
| **Major** | Engineering Lead explicit sign-off |
| **Minor** | Standard CI/CD pipeline approval |
| **Cosmetic** | Standard CI/CD pipeline approval |

### 9.3 Deployment

1. Deploy to staging environment
2. Run smoke tests in staging
3. Verify clinical validation test cases (CRITICAL changes)
4. Deploy to production (with rollback capability)
5. Monitor production logs for 1 hour post-deployment
6. Verify key health metrics (API response times, error rates, screening accuracy indicators)

---

## 10. Rollback Procedures

### 10.1 Rollback Triggers

A rollback should be initiated when:
- Screening results show unexpected behavior in production
- Safety block mechanism is not functioning correctly
- CDS disclaimer or clinician review flags are missing from responses
- Data integrity issues detected (facts not traceable, lineage gaps)
- Error rate exceeds baseline by > 2x
- User reports of incorrect eligibility determinations

### 10.2 Rollback Process

| Step | Action | Owner | Max Time |
|---|---|---|---|
| 1 | Detect issue (monitoring alert or user report) | On-call Engineer | - |
| 2 | Assess severity and confirm rollback decision | Engineering Lead | 15 minutes |
| 3 | Execute rollback to previous known-good version | On-call Engineer | 30 minutes |
| 4 | Verify rollback successful (smoke tests, key metrics) | On-call Engineer | 15 minutes |
| 5 | Notify stakeholders (VP Quality, CMO if clinical impact) | Engineering Lead | 1 hour |
| 6 | Create incident report | On-call Engineer | 24 hours |
| 7 | Root cause analysis | Engineering team | 1 week |
| 8 | Corrective action plan | Engineering Lead + VP Quality | 2 weeks |

### 10.3 Database Migration Rollback

If the change includes database migrations:
- All migrations must have corresponding rollback (down) migrations
- Rollback migrations must be tested before the release
- Data backup must be taken before migration execution
- Migration rollback must be included in deployment runbook

### 10.4 Rollback for CRITICAL Changes

For CRITICAL changes, the rollback plan must include:
- Verification that safety block mechanism is restored
- Verification that CDS Criterion 4 controls are intact
- Re-screening of any patients screened during the period with the faulty change
- Notification to clinical research sites if screening results may have been affected
- Incident documented in quality management system

---

## 11. Records and Retention

### 11.1 Records to Maintain

| Record | Retention Period | Storage |
|---|---|---|
| Change Requests (all categories) | 5 years or product lifecycle + 2 years, whichever is longer | Quality management system |
| Impact Assessments | Same as CR | Attached to CR |
| Approval Records | Same as CR | Attached to CR |
| Test Results | Same as CR | CI/CD system + attached to CR |
| Release Notes | Product lifecycle + 2 years | Version control system |
| Rollback Incident Reports | Product lifecycle + 2 years | Quality management system |
| CDS Criterion 4 Verification Records | Product lifecycle + 5 years | Quality management system |

### 11.2 Audit Trail

All changes to the system must be traceable through:
1. Version control system (Git) commit history
2. Change Request records in quality management system
3. CI/CD pipeline execution logs
4. Deployment records

---

## 12. Periodic Review

This change control process shall be reviewed:
- **Annually** as part of the quality management system review
- **Upon any regulatory determination change** (e.g., if CDS exemption status changes)
- **After any CRITICAL change rollback** to assess process adequacy
- **Upon request** from VP Quality, CMO, or Regulatory Affairs

---

## Document Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| VP of Quality | | | |
| Engineering Lead | | | |
| Chief Medical Officer | | | |
| Product Manager | | | |
