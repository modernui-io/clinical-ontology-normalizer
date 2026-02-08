# Software Risk Assessment - FMEA

**Document ID:** VP-Quality-1-FMEA
**Version:** 1.0
**Last Updated:** 2026-02-08
**Classification:** CONFIDENTIAL - Internal Use Only
**Owner:** VP of Quality / Engineering Lead
**Approval Status:** DRAFT - Pending Review
**Methodology:** Failure Mode and Effects Analysis (FMEA) per IEC 14971:2019

---

## 1. Scope

This risk assessment covers the clinical trial patient matching pipeline, including:
- FHIR data import (`FHIRImportService`)
- NLP clinical text extraction (`ExtractionPipeline`)
- OMOP concept mapping (`MappingServiceInterface`)
- Clinical fact construction and knowledge graph building
- Trial eligibility screening (`TrialEligibilityService`)
- User interface presentation of results (`MatchExplanation` component)

---

## 2. Risk Scoring Methodology

### 2.1 Severity (S) - Impact if failure occurs

| Score | Level | Description |
|---|---|---|
| 1-2 | Negligible | Minor inconvenience; no clinical impact |
| 3-4 | Minor | Delays in workflow; no patient safety impact |
| 5-6 | Moderate | Incorrect screening result caught by clinician review; workflow disruption |
| 7-8 | Major | Eligible patient missed (false negative) or ineligible patient progresses further before caught; potential delay in access to therapy |
| 9-10 | Critical | Patient safety concern (e.g., contraindicated patient not flagged); regulatory compliance violation |

### 2.2 Occurrence (O) - Probability of failure occurring

| Score | Level | Description |
|---|---|---|
| 1-2 | Remote | Less than 1 in 10,000 operations |
| 3-4 | Low | 1 in 1,000 to 1 in 10,000 operations |
| 5-6 | Moderate | 1 in 100 to 1 in 1,000 operations |
| 7-8 | High | 1 in 10 to 1 in 100 operations |
| 9-10 | Very High | Greater than 1 in 10 operations |

### 2.3 Detection (D) - Ability to detect failure before impact

| Score | Level | Description |
|---|---|---|
| 1-2 | Almost Certain | Automated validation catches failure; user immediately sees error |
| 3-4 | High | Systematic review process likely to detect failure |
| 5-6 | Moderate | Failure detectable through careful review but may be missed |
| 7-8 | Low | Failure unlikely to be detected without targeted investigation |
| 9-10 | Very Low | Failure cannot be detected through normal operations |

### 2.4 Risk Priority Number (RPN)

**RPN = Severity x Occurrence x Detection**

| RPN Range | Risk Level | Action Required |
|---|---|---|
| 1-50 | Low | Monitor; no immediate action required |
| 51-100 | Medium | Implement mitigation when feasible |
| 101-200 | High | Mitigation required before production use |
| 201-1000 | Critical | Immediate action required; consider blocking release |

---

## 3. Failure Mode Analysis

### FM-01: NLP False Negative - Clinical Mention Not Extracted

| Attribute | Value |
|---|---|
| **Component** | ExtractionPipeline (pattern-based extraction) |
| **Failure Mode** | NLP pipeline fails to extract a clinically relevant mention from free-text clinical notes |
| **Potential Cause** | Unusual abbreviation, misspelling, non-standard terminology, complex sentence structure, section misclassification |
| **Potential Effect** | Patient's condition/medication/lab result not captured in ClinicalFact table; criterion evaluates as UNKNOWN instead of PASS; eligible patient missed |
| **Severity** | 7 |
| **Occurrence** | 6 |
| **Detection** | 6 |
| **RPN** | **252** |
| **Risk Level** | Critical |
| **Current Controls** | Data completeness scoring identifies missing domains; `UNKNOWN` status differentiated from `NOT_MET`; false-negative monitoring service |
| **Mitigation** | (1) Expand NLP extraction patterns and synonym dictionaries; (2) Implement LLM-enhanced extraction for low-confidence cases; (3) Require data completeness > 80% before auto-screening; (4) Monthly false-negative audit reviews |

### FM-02: NLP False Positive - Incorrect Mention Extracted

| Attribute | Value |
|---|---|
| **Component** | ExtractionPipeline (pattern-based extraction) |
| **Failure Mode** | NLP pipeline extracts a mention that is not actually present in the clinical text (e.g., negated condition extracted as present) |
| **Potential Cause** | Negation detection failure, section context misinterpretation, entity boundary error, template/boilerplate text misinterpreted |
| **Potential Effect** | Incorrect ClinicalFact created; patient incorrectly matches or fails an eligibility criterion; false positive or false exclusion |
| **Severity** | 6 |
| **Occurrence** | 5 |
| **Detection** | 4 |
| **RPN** | **120** |
| **Risk Level** | High |
| **Current Controls** | Assertion classification (present/absent/conditional/hypothetical); confidence scoring with thresholds; multi-stage validation in pipeline; clinician review (Criterion 4) |
| **Mitigation** | (1) Enhance negation detection with expanded trigger lists; (2) Add section-aware assertion rules; (3) Implement golden dataset validation testing; (4) Flag low-confidence extractions for human review |

### FM-03: OMOP Mapping Error - Incorrect Concept Assignment

| Attribute | Value |
|---|---|
| **Component** | MappingServiceInterface (exact/fuzzy/ML mapping) |
| **Failure Mode** | Clinical mention mapped to incorrect OMOP concept (e.g., "Type 1 DM" mapped to "Type 2 DM" concept) |
| **Potential Cause** | Fuzzy matching returns similar but clinically distinct concept; ambiguous mention text; vocabulary version mismatch |
| **Potential Effect** | Criterion evaluation uses wrong concept; patient may incorrectly match or fail a criterion |
| **Severity** | 6 |
| **Occurrence** | 4 |
| **Detection** | 5 |
| **RPN** | **120** |
| **Risk Level** | High |
| **Current Controls** | Mapping confidence scoring; concept candidate ranking; evidence summaries show mapped concept names for clinician verification |
| **Mitigation** | (1) Implement mapping quality monitoring service; (2) Add concept name display in all UI surfaces; (3) Enable clinician feedback on incorrect mappings; (4) Maintain curated synonym tables for high-priority therapeutic areas |

### FM-04: FHIR Import Data Loss - Resources Not Imported

| Attribute | Value |
|---|---|
| **Component** | FHIRImportService (import_bundle) |
| **Failure Mode** | FHIR resources within a Bundle are silently dropped during import (e.g., malformed CodeableConcept, missing display text) |
| **Potential Cause** | Resource has no `display` text in CodeableConcept; unsupported resource type (skipped without warning); exception in individual resource handler caught and logged but processing continues |
| **Potential Effect** | Incomplete patient clinical profile; criteria evaluate as UNKNOWN due to missing data; eligible patient missed |
| **Severity** | 7 |
| **Occurrence** | 5 |
| **Detection** | 4 |
| **RPN** | **140** |
| **Risk Level** | High |
| **Current Controls** | Import summary statistics returned (counts per resource type); `skipped_resource_types` list; data completeness scoring; per-resource exception logging |
| **Mitigation** | (1) Add import completeness validation (expected vs actual resource counts); (2) Alert on high skip rates; (3) Require minimum data completeness for auto-screening; (4) Log warnings for resources dropped due to missing display text |

### FM-05: Eligibility Logic Error - Incorrect Boolean Logic

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (screen_patients, check_patient_eligibility) |
| **Failure Mode** | Boolean logic in criterion evaluation produces incorrect result (e.g., OR applied where AND is required; exclusion criteria not properly subtracted) |
| **Potential Cause** | Criterion coding error (wrong `root_operator`); code bug in set intersection/union logic; edge case in empty criterion set handling |
| **Potential Effect** | Patients incorrectly classified as eligible or ineligible; systematic screening error affecting all patients for a trial |
| **Severity** | 8 |
| **Occurrence** | 3 |
| **Detection** | 3 |
| **RPN** | **72** |
| **Risk Level** | Medium |
| **Current Controls** | Per-criterion audit trail with pass/fail status; unit tests for Boolean logic; clinician review of evidence summaries |
| **Mitigation** | (1) Comprehensive unit test coverage for all Boolean combinations; (2) Integration tests with known patient-trial pairs; (3) Add criterion logic validation at trial creation time; (4) Peer review for criterion coding changes |

### FM-06: Exclusion Criterion Missed - Contraindicated Patient Not Blocked

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (_evaluate_criterion with is_exclusion=True) |
| **Failure Mode** | Patient has a documented contraindication (exclusion criterion match) but the system fails to detect it |
| **Potential Cause** | Condition coded with different terminology than exclusion criterion codes; NLP extraction missed the mention; condition documented only in narrative text not yet processed; ILIKE pattern too narrow |
| **Potential Effect** | Contraindicated patient appears as eligible candidate; if clinician review also misses it, patient could be enrolled in a trial with a contraindication |
| **Severity** | 9 |
| **Occurrence** | 4 |
| **Detection** | 5 |
| **RPN** | **180** |
| **Risk Level** | High |
| **Current Controls** | Safety hard-stop mechanism (CMO-5) for high-confidence matches (>0.7); safety block logging to patient_safety logger and audit trail; mandatory clinician review; PI final determination required |
| **Mitigation** | (1) Expand exclusion criterion code sets to include all synonyms and related codes; (2) Implement secondary exclusion check using broader concept hierarchies; (3) Flag patients with incomplete data who bypass exclusion screening; (4) Require explicit exclusion attestation from PI at enrollment |

### FM-07: Safety Hard-Stop Bypass - Safety Block Not Enforced

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (check_patient_eligibility, auto_screen_patient) |
| **Failure Mode** | The safety_blocked flag is set but the patient is still presented as eligible or auto-enrolled |
| **Potential Cause** | Code regression removes or bypasses safety block check; race condition in auto-screening; database inconsistency |
| **Potential Effect** | Contraindicated patient progresses through enrollment pipeline despite safety block |
| **Severity** | 10 |
| **Occurrence** | 2 |
| **Detection** | 2 |
| **RPN** | **40** |
| **Risk Level** | Low |
| **Current Controls** | Belt-and-suspenders implementation: safety_blocked forces score=0.0 AND eligible=False independently of exclusion_triggered logic (lines 1309-1323); auto_screen_patient explicitly checks safety_blocked before enrollment (lines 1526-1533); safety block logged to dedicated logger; audit trail |
| **Mitigation** | (1) Regression test suite specifically for safety block enforcement; (2) Code review checklist item for any changes to eligibility evaluation; (3) Integration test: verified contraindicated patient never appears as eligible |

### FM-08: Demographic Criterion Error - Age Calculation Wrong

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (_get_demographic_patient_ids) |
| **Failure Mode** | Patient age calculated incorrectly from birth date, causing incorrect demographic criterion evaluation |
| **Potential Cause** | Birth date parsing error; timezone handling bug; leap year calculation error; birth_date stored in unexpected format |
| **Potential Effect** | Patient incorrectly included or excluded based on age criterion |
| **Severity** | 5 |
| **Occurrence** | 3 |
| **Detection** | 3 |
| **RPN** | **45** |
| **Risk Level** | Low |
| **Current Controls** | Age calculated as `(now - birth_date).days / 365.25`; demographic evidence summary shows calculated age and DOB for clinician verification; try/except handles parse errors |
| **Mitigation** | (1) Use `dateutil.relativedelta` for precise age calculation; (2) Unit tests with edge cases (leap year, January birthdays); (3) Display age prominently in UI for easy verification |

### FM-09: Measurement Value Comparison Error

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (_criterion_patient_query, _evaluate_criterion) |
| **Failure Mode** | Lab value comparison against criterion range produces incorrect result (e.g., HbA1c > 12% exclusion not triggered) |
| **Potential Cause** | String-to-float cast failure (`cast(ClinicalFact.value, SAFloat)`); value stored with unit text; different units between criterion and stored value; NULL value |
| **Potential Effect** | Patient with out-of-range lab value not excluded; or patient with normal lab value excluded |
| **Severity** | 7 |
| **Occurrence** | 5 |
| **Detection** | 5 |
| **RPN** | **175** |
| **Risk Level** | High |
| **Current Controls** | Evidence summary shows actual lab value, unit, and date for clinician verification; confidence scoring reduces weight for uncertain matches |
| **Mitigation** | (1) Validate numeric parsability of ClinicalFact.value before comparison; (2) Implement unit normalization/conversion; (3) Flag value comparison failures as UNKNOWN rather than silent pass; (4) Add explicit unit checking against criterion expected units |

### FM-10: Stale Data - Clinical Data Outdated at Screening Time

| Attribute | Value |
|---|---|
| **Component** | FHIRImportService, TrialEligibilityService |
| **Failure Mode** | Patient's clinical status has changed since data was imported, but screening uses outdated data |
| **Potential Cause** | Data imported weeks/months before screening; EHR not re-queried; condition resolved but ClinicalFact still shows PRESENT |
| **Potential Effect** | Patient screened against outdated clinical profile; may be incorrectly included or excluded |
| **Severity** | 6 |
| **Occurrence** | 6 |
| **Detection** | 7 |
| **RPN** | **252** |
| **Risk Level** | Critical |
| **Current Controls** | Evidence summaries show dates of source data; data completeness scoring; clinician review expected to verify current status |
| **Mitigation** | (1) Display data freshness indicators (last import date) prominently in UI; (2) Implement re-import triggers before screening; (3) Add maximum data age threshold with warning; (4) Require CRC to verify current status as part of enrollment checklist |

### FM-11: Text Matching Too Broad - ILIKE Pattern False Match

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (_criterion_patient_query, _evaluate_criterion) |
| **Failure Mode** | `concept_name.ilike(f"%{term}%")` matches unrelated clinical concepts (e.g., "malignant" in "malignant hypertension" matches cancer exclusion criterion for "malignant neoplasm") |
| **Potential Cause** | Substring matching inherent in ILIKE with wildcards; short or ambiguous display terms; generic medical terms appearing in multiple clinical contexts |
| **Potential Effect** | False exclusion (benign condition triggers cancer exclusion) or false inclusion (unrelated condition matches target indication) |
| **Severity** | 6 |
| **Occurrence** | 6 |
| **Detection** | 5 |
| **RPN** | **180** |
| **Risk Level** | High |
| **Current Controls** | Confidence scoring; per-criterion evidence shows matched concept names; clinician review |
| **Mitigation** | (1) Use OMOP concept IDs for matching instead of/in addition to text matching; (2) Implement concept hierarchy-aware matching; (3) Add negative term exclusions to criterion definitions; (4) Require minimum term length for ILIKE matching; (5) Validate criterion text terms against known false-match patterns |

### FM-12: Auto-Screening Race Condition

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (auto_screen_patient) |
| **Failure Mode** | FHIR import triggers auto-screening before all resources are committed to the database |
| **Potential Cause** | auto_screen_patient called before session.commit() completes; concurrent import and screening operations |
| **Potential Effect** | Screening runs against incomplete patient data; results reflect partial import |
| **Severity** | 5 |
| **Occurrence** | 3 |
| **Detection** | 6 |
| **RPN** | **90** |
| **Risk Level** | Medium |
| **Current Controls** | import_bundle commits before returning; auto_screen_patient called after commit |
| **Mitigation** | (1) Ensure auto-screening is always called after successful commit; (2) Add data completeness minimum threshold before auto-screening activates; (3) Implement idempotent re-screening capability |

### FM-13: Database Connection Failure During Screening

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (all database-querying methods) |
| **Failure Mode** | Database connection lost during eligibility screening, causing partial or failed evaluation |
| **Potential Cause** | Database server failure; connection pool exhaustion; network interruption; query timeout |
| **Potential Effect** | Screening returns error; partial results returned; user receives incomplete information |
| **Severity** | 4 |
| **Occurrence** | 3 |
| **Detection** | 2 |
| **RPN** | **24** |
| **Risk Level** | Low |
| **Current Controls** | FastAPI error handling; async session management; connection pool configuration |
| **Mitigation** | (1) Implement retry logic with exponential backoff; (2) Return clear error messages distinguishing infrastructure failure from clinical result; (3) Never return partial results without clear indication of incompleteness |

### FM-14: Criterion Configuration Error - Wrong Codes in Trial Definition

| Attribute | Value |
|---|---|
| **Component** | Trial CRUD (TrialEligibilityService.create_trial, update_trial) |
| **Failure Mode** | Trial eligibility criteria configured with incorrect codes, wrong value ranges, or missing criteria |
| **Potential Cause** | Human error in criterion coding; copy-paste from wrong protocol; ICD-10 version mismatch; incomplete translation from protocol narrative to structured criteria |
| **Potential Effect** | All screening for the affected trial produces incorrect results; systematic false positives or false negatives |
| **Severity** | 8 |
| **Occurrence** | 5 |
| **Detection** | 6 |
| **RPN** | **240** |
| **Risk Level** | Critical |
| **Current Controls** | None specific to criterion validation at entry time |
| **Mitigation** | (1) Implement criterion validation at trial creation (verify codes exist in vocabulary); (2) Require dual-person review for trial criterion configuration; (3) Run validation screening against known test patients before activating trial; (4) Maintain criterion change audit trail; (5) Implement protocol-to-criteria reconciliation checklist |

### FM-15: UI Misrepresentation - Evidence Display Incorrect

| Attribute | Value |
|---|---|
| **Component** | MatchExplanation component (frontend) |
| **Failure Mode** | Frontend displays incorrect status, confidence, or evidence for a criterion evaluation |
| **Potential Cause** | API response parsing error; field mapping mismatch between backend schema and frontend interface; rendering bug in status color coding |
| **Potential Effect** | Clinician reviews incorrect evidence; may make wrong eligibility determination based on displayed information |
| **Severity** | 7 |
| **Occurrence** | 3 |
| **Detection** | 3 |
| **RPN** | **63** |
| **Risk Level** | Medium |
| **Current Controls** | TypeScript type checking; Pydantic schema validation on backend; color-coded status indicators with defined mappings |
| **Mitigation** | (1) End-to-end integration tests verifying API response matches UI display; (2) Playwright visual regression tests for MatchExplanation component; (3) Add "raw JSON" view for power users to inspect unformatted API response |

### FM-16: False-Negative Monitoring Failure

| Attribute | Value |
|---|---|
| **Component** | fn_monitoring_service (record_screening_result) |
| **Failure Mode** | False-negative monitoring service fails to record screening results, preventing detection of systematic false negatives |
| **Potential Cause** | Exception in FN monitoring (designed to not break screening pipeline via try/except); service initialization failure; storage exhaustion |
| **Potential Effect** | Systematic false negatives go undetected; no quality signal for screening accuracy degradation |
| **Severity** | 6 |
| **Occurrence** | 3 |
| **Detection** | 6 |
| **RPN** | **108** |
| **Risk Level** | High |
| **Current Controls** | Warning logged when FN monitoring fails (line 1356); screening result is never affected by FN monitoring failure |
| **Mitigation** | (1) Monitor FN service health independently; (2) Alert on FN recording failure rate > threshold; (3) Periodic manual FN audits independent of automated monitoring |

### FM-17: Confidence Threshold Miscalibration

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (_evaluate_criterion) |
| **Failure Mode** | Confidence threshold for safety blocks (>0.7) is too high (missing real contraindications) or too low (false safety blocks) |
| **Potential Cause** | Threshold not validated against clinical data; confidence scoring distribution shift; different data sources produce different confidence distributions |
| **Potential Effect** | If too high: contraindicated patients not blocked. If too low: excessive false safety blocks reducing screening efficiency |
| **Severity** | 8 |
| **Occurrence** | 4 |
| **Detection** | 6 |
| **RPN** | **192** |
| **Risk Level** | High |
| **Current Controls** | Fixed threshold at 0.7; POSSIBLE_MATCH status for 0.3-0.7 range; clinician review for all results |
| **Mitigation** | (1) Validate threshold against historical screening data; (2) Implement configurable threshold with audit trail; (3) Monitor safety block rate per trial for anomaly detection; (4) Periodic threshold calibration review with clinical team |

### FM-18: Data Lineage Gap - ClinicalFact Not Traceable to Source

| Attribute | Value |
|---|---|
| **Component** | FHIRImportService (_record_fhir_lineage), lineage_service |
| **Failure Mode** | ClinicalFact created but lineage record not created, making the fact untraceable to its source FHIR resource |
| **Potential Cause** | Exception in record_lineage (caught and logged but not re-raised); lineage table write failure; missing source resource ID |
| **Potential Effect** | Cannot trace screening evidence back to source data; reduced auditability; compromised Criterion 4 compliance (clinician cannot verify source) |
| **Severity** | 5 |
| **Occurrence** | 3 |
| **Detection** | 5 |
| **RPN** | **75** |
| **Risk Level** | Medium |
| **Current Controls** | Warning logged on lineage failure; lineage failure never blocks import pipeline; evidence_fact_ids in criterion results provide alternate traceability |
| **Mitigation** | (1) Monitor lineage recording success rate; (2) Implement lineage completeness check in data quality dashboard; (3) Add lineage gap alerts |

### FM-19: Concurrent Trial Modification During Screening

| Attribute | Value |
|---|---|
| **Component** | TrialEligibilityService (in-memory trial storage) |
| **Failure Mode** | Trial eligibility criteria modified while a screening operation is in progress, causing inconsistent results |
| **Potential Cause** | Concurrent API calls: one modifying trial criteria, another screening patients; no locking mechanism on trial records |
| **Potential Effect** | Screening uses partially updated criteria; some patients screened against old criteria, others against new |
| **Severity** | 5 |
| **Occurrence** | 3 |
| **Detection** | 7 |
| **RPN** | **105** |
| **Risk Level** | High |
| **Current Controls** | In-memory storage with Python GIL provides some serialization; screen_patients reads criteria once at start |
| **Mitigation** | (1) Snapshot trial criteria at screening start; (2) Record criteria version used in screening results; (3) Implement optimistic locking for trial updates; (4) Require trial status change to PAUSED before criteria modification |

### FM-20: Pipeline Version Mismatch

| Attribute | Value |
|---|---|
| **Component** | All services (pipeline_version stamping) |
| **Failure Mode** | ClinicalFacts created by different pipeline versions produce inconsistent results when screened together |
| **Potential Cause** | System upgraded between patient data imports; facts from old pipeline version have different confidence distributions or extraction patterns |
| **Potential Effect** | Screening accuracy varies based on when patient data was imported; inconsistent behavior across patient population |
| **Severity** | 4 |
| **Occurrence** | 4 |
| **Detection** | 6 |
| **RPN** | **96** |
| **Risk Level** | Medium |
| **Current Controls** | pipeline_version stamped on all ClinicalFact records; version tracked in data lineage |
| **Mitigation** | (1) Flag screening results where facts span multiple pipeline versions; (2) Implement re-processing capability for facts created by older pipeline versions; (3) Maintain backward compatibility testing for pipeline version upgrades |

---

## 4. Risk Summary Matrix

| FM# | Failure Mode | S | O | D | RPN | Risk Level |
|---|---|---|---|---|---|---|
| FM-01 | NLP False Negative | 7 | 6 | 6 | **252** | Critical |
| FM-10 | Stale Data | 6 | 6 | 7 | **252** | Critical |
| FM-14 | Criterion Configuration Error | 8 | 5 | 6 | **240** | Critical |
| FM-17 | Confidence Threshold Miscalibration | 8 | 4 | 6 | **192** | Critical |
| FM-06 | Exclusion Criterion Missed | 9 | 4 | 5 | **180** | High |
| FM-11 | ILIKE Pattern False Match | 6 | 6 | 5 | **180** | High |
| FM-09 | Measurement Value Comparison Error | 7 | 5 | 5 | **175** | High |
| FM-04 | FHIR Import Data Loss | 7 | 5 | 4 | **140** | High |
| FM-02 | NLP False Positive | 6 | 5 | 4 | **120** | High |
| FM-03 | OMOP Mapping Error | 6 | 4 | 5 | **120** | High |
| FM-16 | FN Monitoring Failure | 6 | 3 | 6 | **108** | High |
| FM-19 | Concurrent Trial Modification | 5 | 3 | 7 | **105** | High |
| FM-20 | Pipeline Version Mismatch | 4 | 4 | 6 | **96** | Medium |
| FM-12 | Auto-Screening Race Condition | 5 | 3 | 6 | **90** | Medium |
| FM-18 | Data Lineage Gap | 5 | 3 | 5 | **75** | Medium |
| FM-05 | Eligibility Logic Error | 8 | 3 | 3 | **72** | Medium |
| FM-15 | UI Misrepresentation | 7 | 3 | 3 | **63** | Medium |
| FM-08 | Demographic Age Calculation Error | 5 | 3 | 3 | **45** | Low |
| FM-07 | Safety Hard-Stop Bypass | 10 | 2 | 2 | **40** | Low |
| FM-13 | Database Connection Failure | 4 | 3 | 2 | **24** | Low |

---

## 5. High-Priority Mitigation Plan

The following failure modes have RPN >= 140 and require active mitigation:

### 5.1 FM-01: NLP False Negative (RPN 252)

| Action | Owner | Target Date | Status |
|---|---|---|---|
| Expand NLP extraction synonym dictionaries for top 20 therapeutic areas | NLP Engineer | Q2 2026 | Not Started |
| Implement LLM fallback for low-confidence extractions | NLP Engineer | Q3 2026 | Not Started |
| Establish minimum data completeness threshold (80%) for auto-screening | Engineering Lead | Q1 2026 | Not Started |
| Implement monthly false-negative audit (manual chart review of 50 screened-out patients) | Clinical Operations | Ongoing | Not Started |
| Build golden dataset for NLP extraction validation (100+ annotated notes) | NLP Engineer | Q1 2026 | In Progress |

### 5.2 FM-10: Stale Data (RPN 252)

| Action | Owner | Target Date | Status |
|---|---|---|---|
| Display data freshness indicators (last import timestamp) in screening results UI | Frontend Engineer | Q1 2026 | Not Started |
| Implement maximum data age warning (> 90 days since last import) | Engineering Lead | Q1 2026 | Not Started |
| Add FHIR re-import trigger in screening workflow | Backend Engineer | Q2 2026 | Not Started |
| Include "data verified as of" attestation in enrollment checklist | Clinical Operations | Q1 2026 | Not Started |

### 5.3 FM-14: Criterion Configuration Error (RPN 240)

| Action | Owner | Target Date | Status |
|---|---|---|---|
| Implement code validation at trial creation (verify ICD-10/SNOMED codes exist) | Backend Engineer | Q1 2026 | Not Started |
| Require dual-person review (four-eyes principle) for trial criterion configuration | Clinical Operations | Q1 2026 | Not Started |
| Build test patient set for criterion validation before trial activation | Engineering Lead | Q2 2026 | Not Started |
| Add protocol-to-criteria reconciliation checklist template | Clinical Operations | Q1 2026 | Not Started |

### 5.4 FM-17: Confidence Threshold Miscalibration (RPN 192)

| Action | Owner | Target Date | Status |
|---|---|---|---|
| Validate 0.7 safety block threshold against historical screening data | Data Science | Q2 2026 | Not Started |
| Implement safety block rate monitoring dashboard per trial | Engineering Lead | Q2 2026 | Not Started |
| Schedule quarterly threshold calibration review with clinical advisory board | VP Quality | Quarterly | Not Started |

### 5.5 FM-06: Exclusion Criterion Missed (RPN 180)

| Action | Owner | Target Date | Status |
|---|---|---|---|
| Expand exclusion criterion code sets with concept hierarchy descendants | Backend Engineer | Q2 2026 | Not Started |
| Implement secondary exclusion check using broader matching | Backend Engineer | Q2 2026 | Not Started |
| Require explicit exclusion attestation from PI at enrollment | Clinical Operations | Q1 2026 | Not Started |
| Add data gap flagging for patients bypassing exclusion screening | Engineering Lead | Q2 2026 | Not Started |

### 5.6 FM-11: ILIKE Pattern False Match (RPN 180)

| Action | Owner | Target Date | Status |
|---|---|---|---|
| Migrate from text-based ILIKE matching to OMOP concept ID matching | Backend Engineer | Q2 2026 | Not Started |
| Implement concept hierarchy-aware matching | Backend Engineer | Q3 2026 | Not Started |
| Add known false-match pattern exclusion list | NLP Engineer | Q1 2026 | Not Started |

---

## 6. Residual Risk Assessment

After implementation of all planned mitigations, the residual risk profile is expected to be:

| FM# | Failure Mode | Original RPN | Mitigated RPN (Est.) | Residual Risk Level |
|---|---|---|---|---|
| FM-01 | NLP False Negative | 252 | ~100 | Medium |
| FM-10 | Stale Data | 252 | ~80 | Medium |
| FM-14 | Criterion Configuration Error | 240 | ~60 | Medium |
| FM-17 | Confidence Threshold Miscalibration | 192 | ~80 | Medium |
| FM-06 | Exclusion Criterion Missed | 180 | ~90 | Medium |
| FM-11 | ILIKE Pattern False Match | 180 | ~50 | Low |

**Overall Residual Risk Assessment**: ACCEPTABLE

The residual risk is acceptable because:
1. The mandatory clinician review (Criterion 4) provides a human safety barrier for all screening output
2. The PI must make the final eligibility determination independently
3. Clinical trial enrollment also requires informed consent, IRB oversight, and protocol-specific safety assessments
4. The system is one screening aid within a multi-layered clinical trial enrollment process

---

## 7. Review and Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| VP of Quality | | | |
| Engineering Lead | | | |
| Chief Medical Officer | | | |
| Clinical Operations Lead | | | |

**Next Review Date:** Q3 2026 or upon significant system change, whichever is earlier.
