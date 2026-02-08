# Implementation Plan: CMO, CSO, CDO, and Director of Clinical Informatics

> Deep implementation plan for clinical safety, scientific rigor, data governance, and terminology fidelity.
> Each item traces to a specific hardening plan entry, with current-state code references, gap analysis, implementation steps, acceptance criteria, effort estimates, and inter-item dependencies.

---

## Table of Contents

1. [CMO Items](#1-cmo--chief-medical-officer)
   - 1.1 "Clinician Review Required" Labeling
   - 1.2 Assertion/Negation Validation
   - 1.3 Temporal Reasoning Validation
   - 1.4 Clinical Validation Study Design
   - 1.5 Patient Safety Guardrails
   - 1.6 False Negative Monitoring
   - 1.7 Clinician Feedback Loop
2. [CSO Items](#2-cso--chief-scientific-officer)
   - 2.1 Reproducibility (Version Pinning)
   - 2.2 Publication-Ready Data Exports
   - 2.3 Cohort Identification Accuracy
   - 2.4 Trial Eligibility Criteria Fidelity
   - 2.5 Longitudinal Patient Tracking
3. [Director of Clinical Informatics Items](#3-director-of-clinical-informatics)
   - 3.1 Terminology Governance Workflow
   - 3.2 FHIR R4 Conformance Testing
   - 3.3 Value Set Management
   - 3.4 OMOP ETL Validation
   - 3.5 Vocabulary Update Regression Testing
4. [CDO Items](#4-cdo--chief-data-officer)
   - 4.1 Data Lineage Tracking
   - 4.2 Data Quality Dashboard
   - 4.3 Data Completeness Scoring Per Patient
5. [Dependency Graph](#5-dependency-graph)
6. [Priority Sequencing](#6-priority-sequencing)

---

## 1. CMO / Chief Medical Officer

### 1.1 "Clinician Review Required" Labeling

**Hardening Plan Reference:** CMO item 1 -- "All match outputs must prominently state this. Required for CDS exemption under Cures Act Criterion 4. No autonomous enrollment."

#### Current State

The screening API returns `ScreeningResponse` and `PatientEligibility` objects from:

- **API layer:** `backend/app/api/trials.py` (lines 186-205) -- `screen_patients()` endpoint and (lines 208-229) -- `check_patient_eligibility()` endpoint return raw eligibility results with no CDS labeling.
- **Schema:** `backend/app/schemas/trial.py` (lines 167-181) -- `PatientEligibility` has `eligible: bool`, `match_score: float`, `criteria_details`, but no field for review status or CDS disclaimer.
- **Schema:** `backend/app/schemas/trial.py` (lines 200-218) -- `ScreeningResponse` has no `review_disclaimer` or `requires_clinician_review` field.
- **Service:** `backend/app/services/trial_eligibility_service.py` (lines 656-667) -- `screen_patients()` returns the `ScreeningResponse` directly with no labeling metadata.
- **Service:** `backend/app/services/trial_eligibility_service.py` (lines 936-975) -- `auto_screen_patient()` auto-enrolls patients with score > 0.5 as CANDIDATE without any clinician review gate.
- **Frontend:** `frontend/src/app/trials/[id]/page.tsx` -- Trial detail page displays screening results with no review-required banner.

**No** instance of `clinician_review`, `review_required`, or CDS disclaimer text exists anywhere in the codebase.

#### Gap Analysis

- **Critical regulatory gap:** Cures Act Criterion 4 requires that CDS provide "sufficient information for the HCP to NOT rely primarily on the software." Without labeling, the system could be classified as SaMD.
- All API responses lack review-required metadata.
- Auto-screening in `auto_screen_patient()` (line 962) creates enrollments without any review gate.
- Frontend has no visual indicator that results require clinician review.
- No audit trail of whether a clinician has actually reviewed a match.

#### Implementation Steps

1. **Add schema fields** in `backend/app/schemas/trial.py`:
   - Add `requires_clinician_review: bool = True` to `PatientEligibility` (always `True`).
   - Add `review_status: str = "PENDING_REVIEW"` to `PatientEligibility` (values: `PENDING_REVIEW`, `CLINICIAN_APPROVED`, `CLINICIAN_REJECTED`).
   - Add `cds_disclaimer: str` to `ScreeningResponse` with static text: `"This information is intended as clinical decision support for healthcare professionals. All match results require independent clinician review before any clinical action. This system does not autonomously determine patient eligibility."`
   - Add `review_disclaimer: str` to `PatientEligibility`.

2. **Update service layer** in `backend/app/services/trial_eligibility_service.py`:
   - In `check_patient_eligibility()` (line 872), populate `requires_clinician_review=True` and `review_status="PENDING_REVIEW"` in the returned `PatientEligibility`.
   - In `_build_real_candidates()` (line 918), populate the same fields.
   - In `screen_patients()` (line 656), add `cds_disclaimer` to the `ScreeningResponse`.
   - In `auto_screen_patient()` (line 962), change enrollment status from `CANDIDATE` to a new `PENDING_REVIEW` status, or gate the enrollment on a configuration flag `AUTO_ENROLL_ENABLED` defaulting to `False`.

3. **Add review endpoint** in `backend/app/api/trials.py`:
   - `POST /api/v1/trials/{trial_id}/review/{patient_id}` -- accepts `{action: "approve"|"reject", reviewer_id: str, notes: str}`.
   - Updates enrollment `review_status`, captures reviewer identity, timestamp.
   - Only after `CLINICIAN_APPROVED` can status move to `ENROLLED`.

4. **Add audit model** -- create `ClinicalReviewAudit` table with: `id`, `trial_id`, `patient_id`, `reviewer_id`, `action`, `timestamp`, `notes`, `match_score_at_review`, `criteria_snapshot`.

5. **Frontend updates** in `frontend/src/app/trials/[id]/page.tsx`:
   - Add yellow banner at top of screening results: "All screening results require independent clinician review before clinical action."
   - Add per-patient "Approve" / "Reject" buttons that call the review endpoint.
   - Show review status badge on each patient row.

#### Acceptance Criteria

- [ ] Every API response from `/trials/{id}/screen` and `/trials/{id}/check/{patient_id}` includes `requires_clinician_review: true` and the CDS disclaimer text.
- [ ] No patient can be moved to `ENROLLED` status without a `CLINICIAN_APPROVED` review record.
- [ ] The `ClinicalReviewAudit` table captures reviewer identity, timestamp, and criteria snapshot for every review action.
- [ ] Frontend displays the review-required banner on all screening result views.
- [ ] `auto_screen_patient()` does not create `CANDIDATE` enrollments without a review gate.

#### Effort Estimate

- Backend schema + service: 1 day
- Review endpoint + audit model: 1 day
- Frontend banner + review UI: 1 day
- Tests: 0.5 days
- **Total: 3.5 days**

#### Dependencies

- None (foundational; other items depend on this)

---

### 1.2 Assertion/Negation Validation

**Hardening Plan Reference:** CMO item 2 -- "Patient denies chest pain vs Patient reports chest pain must be correctly distinguished."

#### Current State

The assertion detection system is sophisticated and already implemented:

- **Probabilistic Assertion Classifier:** `backend/app/services/assertion_classifier.py` (lines 1-495) -- A full `ProbabilisticAssertionClassifier` with:
  - 32 `ABSENT_TRIGGERS` (lines 97-132) with calibrated confidence scores (0.85-0.98)
  - 17 `UNCERTAIN_TRIGGERS` (lines 134-169) with confidence scores (0.30-0.75)
  - 16 `HYPOTHETICAL_TRIGGERS` (lines 171-188) with confidence scores (0.20-0.35)
  - 13 `PRESENT_TRIGGERS` (lines 190-213) with confidence scores (0.85-0.98)
  - 9 `PSEUDO_NEGATION_TRIGGERS` (lines 217-227) -- "no change", "gram negative", etc.
  - Scope-aware matching (FORWARD, BACKWARD, BIDIRECTIONAL) at lines 32-37
  - Scope termination patterns (lines 230-245) -- "but", "however", etc.
  - Token distance limiting (`max_scope_tokens`) for precision

- **Rule-Based NLP Integration:** `backend/app/services/nlp_rule_based.py` (lines 349-354) calls `classify_assertion()` for every extracted mention, populating `assertion_confidence` and `assertion_trigger` fields.

- **Assertion Enum:** `backend/app/schemas/base.py` (lines 8-17) -- `Assertion` enum has `PRESENT`, `ABSENT`, `POSSIBLE`, `CONDITIONAL`, `HYPOTHETICAL`, `FAMILY_HISTORY`, `HISTORICAL`.

- **Trial Eligibility Filtering:** `backend/app/services/trial_eligibility_service.py` (lines 410-412) -- Eligibility screening filters on `ClinicalFact.assertion == Assertion.PRESENT`, correctly excluding negated findings from positive matches.

#### Gap Analysis

- **No dedicated test suite:** There are no test files specifically for assertion detection edge cases (e.g., "no evidence of pneumonia" vs "pneumonia"). The existing tests in `backend/tests/` do not include an assertion-specific regression suite.
- **No clinical validation:** No ground-truth annotated dataset for assertion detection accuracy measurement.
- **No confidence threshold enforcement:** The trial eligibility service at line 774 uses confidence > 0.7 for PASS and > 0.3 for POSSIBLE_MATCH, but these thresholds are not configurable or validated against clinical outcomes.
- **Missing edge cases in triggers:** The classifier does not handle double negation ("not without"), litotes ("not insignificant"), or section-aware assertion adjustment (negation in "Allergies" section means something different from "Review of Systems").
- **No assertion audit logging:** When assertion determines eligibility, there is no record of which trigger matched, at what confidence, for regulatory traceability.

#### Implementation Steps

1. **Create assertion test suite** at `backend/tests/test_assertion_validation.py`:
   - Minimum 100 test cases organized by category:
     - Simple negation: "no chest pain", "denies nausea" (20 cases)
     - Hypothetical: "if patient develops fever" (10 cases)
     - Family history: "mother had breast cancer" (10 cases)
     - Double negation: "not without concern" (10 cases)
     - Pseudo-negation: "no change in diabetes" (10 cases)
     - Scope termination: "no chest pain, but has diabetes" (10 cases)
     - Context-dependent: "ROS: denies headache. Assessment: migraine" (15 cases)
     - Medication context: "taking no medications" vs "taking metformin, no side effects" (15 cases)

2. **Add section-aware assertion adjustment** in `backend/app/services/assertion_classifier.py`:
   - If mention is in "Family History" section and no explicit assertion trigger found, default to `FAMILY_HISTORY` assertion instead of `PRESENT`.
   - If mention is in "Allergies" section, weight negation triggers differently.

3. **Add assertion audit to CriterionResult** in `backend/app/schemas/trial.py`:
   - Add `assertion_trigger: str | None` and `assertion_confidence: float | None` to `CriterionResult`.
   - Populate these in `_evaluate_criterion()` at `backend/app/services/trial_eligibility_service.py` line 676.

4. **Make confidence thresholds configurable** in `backend/app/core/config.py`:
   - Add `ASSERTION_PASS_THRESHOLD: float = 0.7` and `ASSERTION_POSSIBLE_THRESHOLD: float = 0.3`.
   - Reference these in `_evaluate_criterion()` instead of hardcoded values.

5. **Build golden assertion dataset** at `backend/fixtures/assertion_golden_dataset.json`:
   - 200+ annotated clinical text snippets with ground-truth assertion labels.
   - Two annotators per snippet, adjudicated disagreements.

#### Acceptance Criteria

- [ ] Assertion test suite passes with >= 95% accuracy on golden dataset.
- [ ] "Patient denies chest pain" correctly classified as `ABSENT` with confidence >= 0.95.
- [ ] "Patient reports chest pain" correctly classified as `PRESENT` with confidence >= 0.85.
- [ ] "Cannot rule out pneumonia" correctly classified as `POSSIBLE` with confidence 0.40-0.50.
- [ ] "No change in diabetes" correctly classified as `PRESENT` (pseudo-negation) with confidence >= 0.85.
- [ ] "No chest pain, but has diabetes" -- "chest pain" is `ABSENT`, "diabetes" is `PRESENT`.
- [ ] All criterion evaluations include assertion trigger and confidence in audit trail.

#### Effort Estimate

- Test suite creation: 2 days
- Section-aware adjustment: 1 day
- Audit fields + configurable thresholds: 0.5 days
- Golden dataset (initial): 3 days (requires clinical SME)
- **Total: 6.5 days** (2 days engineering, 4.5 days with clinical annotation)

#### Dependencies

- Golden dataset creation requires clinical SME (external dependency)
- Feeds into: 1.5 Patient Safety Guardrails, 1.6 False Negative Monitoring

---

### 1.3 Temporal Reasoning Validation

**Hardening Plan Reference:** CMO item 3 -- "Diagnosed 6 months ago vs diagnosed 6 years ago changes everything."

#### Current State

A temporal extraction system exists:

- **Temporal Extractor:** `backend/app/services/temporal_extractor.py` (lines 1-487) -- A `TemporalExtractor` class with:
  - 11 temporal patterns (lines 67-148): ISO dates, US dates, month+year, relative expressions ("3 days ago", "last week")
  - `TemporalExpression` dataclass (lines 26-36) with `date`, `date_precision`, `expression_type`, `confidence`
  - `EntityTemporalBinding` (lines 39-48) linking entities to temporal expressions
  - `bind_entities_to_temporals()` (lines 358-425) proximity-based binding with max 100 character distance
  - `_determine_relationship()` (lines 427-453) keyword-based relationship detection ("diagnosed", "started", "stopped")

- **ClinicalFact model:** `backend/app/models/clinical_fact.py` (lines 74-80) has `start_date` column.

- **FHIR Import:** `backend/app/services/fhir_import.py` parses `onsetDateTime` (line 544), `authoredOn` (line 609), `effectiveDateTime` (line 767) from FHIR resources.

- **Trial Eligibility Service:** `backend/app/services/trial_eligibility_service.py` -- the eligibility service does **NOT** use temporal information at all. Lines 405-422 query ClinicalFacts by domain, assertion, and concept name, but there is no temporal filtering.

#### Gap Analysis

- **Critical gap:** Trial eligibility criteria often include temporal constraints ("diagnosed within last 6 months", "no prior chemotherapy in last 12 months") but the screening engine ignores all temporal data.
- The temporal extractor exists but is NOT integrated into the trial eligibility evaluation pipeline.
- No temporal criteria type in the inclusion/exclusion criteria JSON schema -- only `demographic`, `condition`, `drug`, `measurement`, `procedure`, `observation` are supported (lines 389-395 of `trial_eligibility_service.py`).
- Approximate relative date parsing: "3 months ago" uses 30 * n days (line 249 of `temporal_extractor.py`) which is imprecise for eligibility cutoffs.
- No test suite for temporal extraction accuracy.

#### Implementation Steps

1. **Add temporal criterion type** to `backend/app/services/trial_eligibility_service.py`:
   - Add `"temporal_condition"` to `domain_map` and `_criterion_patient_query()`.
   - Support criteria format: `{"criterion_type": "temporal_condition", "name": "Recent diagnosis", "codes": [...], "temporal_constraint": {"within_days": 180, "reference": "diagnosis_date"}}`.
   - Query `ClinicalFact.start_date` to check temporal constraints.

2. **Integrate temporal filtering into criterion evaluation** at `_evaluate_criterion()`:
   - When `criterion.get("temporal_constraint")` exists, add SQL filter: `ClinicalFact.start_date >= (now - within_days)`.
   - Support operators: `within_days`, `at_least_days_ago`, `before_date`, `after_date`.

3. **Create temporal test suite** at `backend/tests/test_temporal_validation.py`:
   - Test cases for: absolute dates, relative dates, month precision, year precision, edge cases (leap year, "6 months ago" boundary).
   - Integration tests: patient diagnosed 5 months ago passes "within 6 months" criterion; patient diagnosed 7 months ago fails.

4. **Improve relative date precision** in `backend/app/services/temporal_extractor.py`:
   - Replace `timedelta(days=n * 30)` for months with `dateutil.relativedelta` for calendar-accurate month arithmetic.
   - Add warning when date precision is "approximate" and temporal constraint is tight (e.g., within_days < 90).

5. **Add temporal confidence to eligibility results** in `CriterionResult`:
   - Add `temporal_data_available: bool` and `temporal_precision: str` fields.
   - When temporal data is missing, set status to `UNKNOWN` with details explaining missing temporal information.

#### Acceptance Criteria

- [ ] Trial criteria can specify temporal constraints (within_days, at_least_days_ago).
- [ ] Patient diagnosed 5 months ago matches "diagnosed within 6 months" criterion.
- [ ] Patient diagnosed 7 months ago does NOT match "diagnosed within 6 months" criterion.
- [ ] Missing temporal data results in `UNKNOWN` status, not `PASS`.
- [ ] Relative date parsing handles month boundaries correctly (not just days*30).
- [ ] Temporal extraction test suite passes with >= 90% accuracy on date parsing.

#### Effort Estimate

- Temporal criterion type + SQL integration: 2 days
- Temporal extractor improvements: 1 day
- Test suite: 1.5 days
- Update demo trial criteria with temporal constraints: 0.5 days
- **Total: 5 days**

#### Dependencies

- Benefits from 1.2 (assertion validation) -- temporal + assertion together determine eligibility
- Required by 2.4 (trial eligibility criteria fidelity)

---

### 1.4 Clinical Validation Study Design

**Hardening Plan Reference:** CMO item 4 -- "Plan retrospective chart review (n=500+), prospective concordance study."

#### Current State

- No validation study infrastructure exists in the codebase.
- No golden dataset of annotated clinical notes.
- No mechanism to record ground-truth eligibility alongside system predictions.
- The `ScreeningResponse` schema (`backend/app/schemas/trial.py` lines 200-218) returns aggregate counts but has no ground-truth comparison fields.
- No endpoint for recording manual chart review results alongside automated screening.

#### Gap Analysis

- No infrastructure for importing ground-truth annotations.
- No database table for storing validation study results.
- No API for comparing system output against clinician gold standard.
- No metrics calculation engine (sensitivity, specificity, PPV, NPV, F1).
- No stratified analysis by demographic group, therapeutic area, or criterion type.

#### Implementation Steps

1. **Create validation study models** in `backend/app/models/validation.py`:
   - `ValidationStudy`: id, name, study_type (retrospective/prospective), start_date, end_date, status, therapeutic_area, n_patients.
   - `ValidationCase`: id, study_id, patient_id, trial_id, ground_truth_eligible (bool), system_eligible (bool), system_match_score, reviewer_id, review_timestamp, notes, demographics (age, sex, race).
   - `ValidationMetrics`: id, study_id, computed_at, sensitivity, specificity, ppv, npv, f1, auc_roc, n_cases, subgroup_label.

2. **Create validation API** in `backend/app/api/validation.py`:
   - `POST /api/v1/validation/studies` -- create a validation study.
   - `POST /api/v1/validation/studies/{id}/cases` -- import ground-truth cases.
   - `POST /api/v1/validation/studies/{id}/run` -- run system screening against study cases and compute metrics.
   - `GET /api/v1/validation/studies/{id}/metrics` -- return computed metrics.
   - `GET /api/v1/validation/studies/{id}/confusion-matrix` -- return TP/FP/TN/FN breakdown.

3. **Create metrics computation service** in `backend/app/services/validation_service.py`:
   - Compute sensitivity, specificity, PPV, NPV, F1, AUC-ROC.
   - Compute per-subgroup metrics (by age bracket, sex, therapeutic area).
   - Generate confusion matrix with example cases for each cell.

4. **Create golden dataset import** -- CLI tool to import annotated cases from CSV with columns: patient_id, trial_id, ground_truth_eligible, reviewer_name.

5. **Design Study 1 protocol document** (non-code):
   - Retrospective chart review, n=500, oncology focus.
   - Two independent reviewers per chart, Cohen's kappa target > 0.75.
   - Stratified by cancer type, stage, demographics.

#### Acceptance Criteria

- [ ] Validation study can be created, cases imported, and metrics computed via API.
- [ ] Metrics endpoint returns sensitivity, specificity, PPV, NPV, F1 with 95% confidence intervals.
- [ ] Subgroup analysis available by age, sex, race, therapeutic area.
- [ ] Confusion matrix includes example patient IDs for each cell (TP, FP, TN, FN).
- [ ] Study 1 protocol document reviewed and approved by clinical team.

#### Effort Estimate

- Models + schemas: 1 day
- API endpoints: 2 days
- Metrics computation engine: 2 days
- CLI import tool: 0.5 days
- Study protocol document: 1 day (clinical team)
- **Total: 6.5 days** (5.5 engineering + 1 day clinical)

#### Dependencies

- Requires: 1.1 (review labeling), 1.2 (assertion validation), 1.3 (temporal validation)
- Feeds into: CSO 2.3 (cohort identification accuracy), CSO 2.4 (trial eligibility fidelity)

---

### 1.5 Patient Safety Guardrails

**Hardening Plan Reference:** CMO item 5 -- "Trial matching must never recommend a contraindicated trial. Build exclusion criteria enforcement with hard stops."

#### Current State

- **Exclusion logic exists:** `backend/app/services/trial_eligibility_service.py` lines 617-637 implement exclusion criteria subtraction -- patients matching exclusion criteria are removed from eligible set.
- **Score zeroing:** Lines 864-866 -- any exclusion triggered drops match score to zero.
- **Confidence thresholds:** Lines 774-782 -- only facts with confidence > 0.7 result in PASS/FAIL status; lower confidence results in POSSIBLE_MATCH or UNKNOWN.

**However:**
- **Auto-enrollment bypass:** Lines 958-968 -- `auto_screen_patient()` enrolls patients as CANDIDATE if `eligible=True` and `score > 0.5` with NO hard stop on exclusion verification.
- **Missing data treated as passing:** When exclusion criteria have no matching clinical facts, the patient is NOT excluded (line 630 -- `matching = set()` means no exclusion triggered). This is correct for set logic but clinically dangerous: missing data about contraindications should NOT mean "no contraindication."
- **No severity classification:** All exclusion criteria are treated equally. "Active cancer" and "mild seasonal allergies" have the same enforcement level.

#### Gap Analysis

- Missing data for safety-critical exclusion criteria should flag `UNKNOWN_SAFETY_RISK`, not silently pass.
- No distinction between hard exclusion (life-threatening contraindication) and soft exclusion (relative contraindication).
- No "safety hold" mechanism to prevent enrollment when critical data is missing.
- Auto-screening creates enrollments without safety verification.

#### Implementation Steps

1. **Add safety classification to exclusion criteria** schema:
   - Add `severity: "hard" | "soft"` field to exclusion criterion JSON.
   - Hard exclusions: absolute contraindications (e.g., active cancer for immunotherapy trial). Missing data = SAFETY_HOLD.
   - Soft exclusions: relative contraindications. Missing data = REVIEW_REQUIRED.

2. **Implement missing data safety logic** in `_evaluate_criterion()`:
   - When `is_exclusion=True` and `status="UNKNOWN"` (no facts found), check criterion severity.
   - If `severity="hard"`, return status `SAFETY_HOLD` instead of `UNKNOWN`.
   - Add `safety_hold: bool` field to `PatientEligibility`.

3. **Add `PatientEligibility.safety_flags: list[str]`** to schema:
   - Populated with human-readable safety concerns.
   - Examples: "Missing data for hard exclusion: Active cancer", "Low-confidence match for drug interaction".

4. **Gate auto-enrollment on safety** in `auto_screen_patient()`:
   - If any `safety_hold=True`, do NOT create enrollment. Log the safety hold.
   - If any hard exclusion has `UNKNOWN` status, do NOT create enrollment.

5. **Add safety dashboard endpoint** at `GET /api/v1/trials/{id}/safety`:
   - Return count of patients on safety hold, breakdown by criterion.
   - Return patients with missing critical data.

#### Acceptance Criteria

- [ ] Hard exclusion criteria with missing data result in `SAFETY_HOLD`, preventing enrollment.
- [ ] `auto_screen_patient()` never enrolls a patient with any safety hold.
- [ ] Safety flags are visible in API response and frontend.
- [ ] Soft exclusion criteria with missing data result in `REVIEW_REQUIRED` but do not prevent enrollment.
- [ ] Safety dashboard shows per-criterion safety hold counts.

#### Effort Estimate

- Schema changes + severity classification: 0.5 days
- Safety logic in eligibility evaluation: 1.5 days
- Auto-enrollment gating: 0.5 days
- Safety dashboard endpoint: 0.5 days
- Tests: 1 day
- **Total: 4 days**

#### Dependencies

- Requires: 1.1 (review labeling)
- Feeds into: 1.6 (false negative monitoring)

---

### 1.6 False Negative Monitoring

**Hardening Plan Reference:** CMO item 6 -- "False negatives (missing eligible patients) are MORE harmful than false positives. Target sensitivity >90%."

#### Current State

- **No false negative tracking.** The system returns eligible patients but has no mechanism to detect patients it missed.
- **No sensitivity measurement.** There is no ground-truth comparison infrastructure.
- **No miss rate reporting.** The `ScreeningResponse` at `backend/app/schemas/trial.py` line 200 reports `eligible_count` and `ineligible_count` but has no `unknown_count` or `data_insufficient_count`.
- **UNKNOWN status exists** in `CriterionResult` (line 150) but is not aggregated or reported.

#### Gap Analysis

- No mechanism to capture "clinician identified eligible patient that system missed" events.
- No API endpoint for reporting false negatives.
- No dashboard tracking miss rates over time.
- UNKNOWN criteria are mixed into `ineligible_count` -- patients with insufficient data are treated identically to patients who clearly fail criteria.

#### Implementation Steps

1. **Separate UNKNOWN from INELIGIBLE** in `ScreeningResponse`:
   - Add `data_insufficient_count: int` to `ScreeningResponse` -- count of patients where any inclusion criterion is UNKNOWN.
   - Add `needs_manual_review_count: int` -- patients with POSSIBLE_MATCH on any criterion.
   - Modify `screen_patients()` in `trial_eligibility_service.py` to compute these counts.

2. **Create false negative reporting endpoint**:
   - `POST /api/v1/trials/{trial_id}/false-negatives` -- body: `{patient_id, reporter_id, notes, ground_truth_eligible: true}`.
   - Stores the report and triggers re-evaluation to identify what the system missed.

3. **Create false negative analysis service** in `backend/app/services/fn_monitoring_service.py`:
   - When a false negative is reported, re-run eligibility evaluation with detailed logging.
   - Identify which criterion(s) the system got wrong.
   - Track root cause categories: missing NLP extraction, wrong assertion, wrong temporal, missing FHIR data, unmapped concept.

4. **Add monitoring dashboard endpoint** at `GET /api/v1/monitoring/false-negatives`:
   - Total false negatives reported, by trial, by criterion type.
   - Root cause breakdown.
   - Trend over time (weekly/monthly).
   - Estimated sensitivity based on reported FN rate.

5. **Add miss rate to TrialDashboard** in `backend/app/schemas/trial.py`:
   - Add `false_negatives_reported: int`, `estimated_sensitivity: float | None`.

#### Acceptance Criteria

- [ ] Clinicians can report false negatives via API.
- [ ] False negative reports trigger root cause analysis identifying the failing component.
- [ ] `ScreeningResponse` separates unknown/insufficient-data patients from truly ineligible.
- [ ] Dashboard shows false negative trend and estimated sensitivity.
- [ ] Sensitivity target of >90% is trackable and alertable.

#### Effort Estimate

- Schema changes + count separation: 0.5 days
- FN reporting endpoint: 1 day
- FN analysis service: 2 days
- Monitoring dashboard: 1 day
- Tests: 0.5 days
- **Total: 5 days**

#### Dependencies

- Requires: 1.4 (validation study design -- provides ground truth infrastructure)
- Feeds into: 1.7 (clinician feedback loop)

---

### 1.7 Clinician Feedback Loop

**Hardening Plan Reference:** CMO item 7 -- "When a clinician overrides a match, capture that as training signal."

#### Current State

- **Enrollment management exists:** `backend/app/services/trial_eligibility_service.py` lines 981-1016 -- `enroll_patient()` and lines 1018-1045 -- `update_enrollment()`.
- **Enrollment status tracking:** `backend/app/models/trial.py` has `EnrollmentStatus` enum with CANDIDATE, SCREENED, ELIGIBLE, ENROLLED, ACTIVE, COMPLETED, WITHDRAWN, SCREEN_FAILED.
- **No override tracking:** When enrollment status changes (e.g., CANDIDATE to SCREEN_FAILED), there is no record of WHY the clinician overrode the system recommendation.
- **No feedback capture:** Override reasons are not stored in a structured format that could be used for system improvement.

#### Gap Analysis

- No `ClinicalOverride` model or table to capture clinician disagreements.
- No structured taxonomy for override reasons.
- No aggregate reporting on override rates.
- No mechanism to feed overrides back into NLP or eligibility rule improvement.

#### Implementation Steps

1. **Create override model** in `backend/app/models/clinical_override.py`:
   - `ClinicalOverride`: id, trial_id, patient_id, override_type (APPROVED_DESPITE_INELIGIBLE, REJECTED_DESPITE_ELIGIBLE), original_eligible (bool), original_score (float), clinician_id, override_reason_category (enum: INCORRECT_NLP, MISSING_DATA, TEMPORAL_ERROR, CRITERIA_INTERPRETATION, CLINICAL_JUDGMENT, OTHER), override_reason_text, criteria_affected (list[str]), timestamp.

2. **Create override API** in `backend/app/api/trials.py`:
   - `POST /api/v1/trials/{trial_id}/override/{patient_id}` -- captures structured override data.
   - Automatically logs to audit trail.

3. **Create override analytics endpoint**:
   - `GET /api/v1/monitoring/overrides` -- aggregate override rates by trial, criterion, reason category.
   - Override rate = overrides / total screenings. Track weekly.
   - Alert when override rate exceeds threshold (e.g., > 20% for any trial).

4. **Create feedback analysis service** in `backend/app/services/feedback_service.py`:
   - Analyze override patterns: which criteria are most frequently overridden?
   - Which assertion triggers produce the most false positives/negatives?
   - Generate improvement recommendations (e.g., "85% of overrides for Trial X are due to temporal criterion misinterpretation").

5. **Export override data for model retraining**:
   - CLI command to export overrides as training data: `{clinical_text, system_assertion, clinician_assertion, correct_label}`.
   - Can be used to fine-tune assertion classifier confidence thresholds.

#### Acceptance Criteria

- [ ] Clinician overrides are captured with structured reason categories.
- [ ] Override rate is computed and visible per trial and per criterion.
- [ ] Aggregate override analytics identify systematic failure patterns.
- [ ] Override data can be exported as training data for model improvement.
- [ ] Alert fires when override rate exceeds 20% for any active trial.

#### Effort Estimate

- Override model + schema: 0.5 days
- Override API endpoint: 1 day
- Analytics endpoint + service: 1.5 days
- Export functionality: 0.5 days
- Tests: 0.5 days
- **Total: 4 days**

#### Dependencies

- Requires: 1.1 (review labeling -- provides review infrastructure)
- Feeds into: VP Data Science model governance

---

## 2. CSO / Chief Scientific Officer

### 2.1 Reproducibility (Version Pinning)

**Hardening Plan Reference:** CSO item 1 -- "Same input document must produce identical extraction + mapping results across pipeline versions."

#### Current State

- **Provenance service exists:** `backend/app/services/provenance_service.py` (lines 1-80+) tracks `ExtractionMethod`, `model_name`, `model_version`, `extraction_date`, `raw_confidence`, `calibrated_confidence`. This is a good foundation but is NOT integrated into the extraction pipeline output.

- **NLP ensemble config:** `backend/app/services/nlp_ensemble.py` (lines 47-80) defines `EnsembleConfig` with extractors enabled/disabled and confidence thresholds, but NO version tracking for the config itself.

- **Vocabulary versioning exists:** `backend/app/services/vocabulary_version_service.py` tracks vocabulary versions with `vocabulary_version`, `version_date`, `status` fields. The `Concept` model has `vocabulary_version` and `version_date` columns.

- **No pipeline version tracking:** There is no mechanism to record which NLP model version, vocabulary version, and mapping algorithm version produced a given ClinicalFact.

- **ClinicalFact model:** `backend/app/models/clinical_fact.py` -- lacks `pipeline_version`, `nlp_model_version`, `vocabulary_version`, or `mapping_version` columns.

#### Gap Analysis

- ClinicalFacts have no record of which pipeline version produced them.
- No way to reproduce results from a previous pipeline version.
- No version pinning for NLP models (rule-based patterns, ML models, LLM prompts).
- Vocabulary version is tracked in the Concept table but not in ClinicalFact records.
- Mapping service has no version identifier.
- No mechanism to re-process documents through a specific pipeline version.

#### Implementation Steps

1. **Add version metadata to ClinicalFact** in `backend/app/models/clinical_fact.py`:
   - Add columns: `pipeline_version: str`, `nlp_model_version: str | None`, `vocabulary_version: str | None`, `mapping_version: str | None`, `extraction_method: str | None`.

2. **Create pipeline version registry** in `backend/app/services/pipeline_version_service.py`:
   - Singleton service that tracks current versions: `{"pipeline": "1.2.0", "nlp_rule_based": "1.0.0", "nlp_ensemble": "1.0.0", "vocabulary_snomed": "2025-09", "vocabulary_rxnorm": "2025-08", "mapping": "1.0.0"}`.
   - Load from config file or environment variables.
   - Stamp every ClinicalFact with the current pipeline version at creation time.

3. **Integrate provenance into fact creation** in `backend/app/services/fact_builder_db.py`:
   - When creating ClinicalFact, populate `pipeline_version` and `extraction_method` from the provenance service.
   - When importing FHIR data, set `extraction_method = "fhir_import"`.

4. **Add version to ScreeningResponse** in `backend/app/schemas/trial.py`:
   - Add `pipeline_version: str` to `ScreeningResponse` so research consumers know which version produced results.

5. **Create version-pinned re-processing endpoint**:
   - `POST /api/v1/documents/{id}/reprocess?pipeline_version=X` -- re-runs extraction with version X.
   - Stores results separately, does NOT overwrite current facts.

#### Acceptance Criteria

- [ ] Every ClinicalFact records pipeline_version, nlp_model_version, vocabulary_version.
- [ ] Pipeline version is visible in screening API responses.
- [ ] Re-processing a document with the same pipeline version produces identical ClinicalFacts.
- [ ] Version registry is queryable via API (`GET /api/v1/pipeline/version`).
- [ ] Switching vocabulary version does not silently change existing fact mappings.

#### Effort Estimate

- Model migration + columns: 0.5 days
- Pipeline version service: 1 day
- Fact builder integration: 1 day
- Re-processing endpoint: 1 day
- Tests: 0.5 days
- **Total: 4 days**

#### Dependencies

- Requires: Dir CI 3.5 (vocabulary update regression testing -- provides vocabulary version tracking)
- Feeds into: 2.2 (publication-ready exports), 1.4 (validation study -- version must be recorded)

---

### 2.2 Publication-Ready Data Exports

**Hardening Plan Reference:** CSO item 2 -- "OMOP CDM format, FHIR bulk export, cohort definition export."

#### Current State

- **FHIR exporter exists:** `backend/app/services/fhir_exporter.py` (lines 1-100+) exports ClinicalFacts to FHIR R4 resources (Condition, MedicationStatement, Observation, Procedure, DiagnosticReport). Has proper FHIR resource structure and CodeableConcept generation.

- **FHIR API exists:** `backend/app/api/fhir.py` provides FHIR export endpoints.

- **ClinicalFact model** stores data in a semi-OMOP format (domain, omop_concept_id, assertion, temporality) but is NOT a full OMOP CDM.

- **No OMOP CDM export:** There is no service to export data in the full OMOP CDM format (PERSON, CONDITION_OCCURRENCE, DRUG_EXPOSURE, MEASUREMENT, PROCEDURE_OCCURRENCE, OBSERVATION tables).

- **No FHIR bulk export:** The FHIR exporter produces individual resources. There is no FHIR $export (bulk data) endpoint per the SMART Backend Services specification.

- **No cohort export:** The cohort service does not export cohort definitions in ATLAS/OHDSI JSON format.

#### Gap Analysis

- No OMOP CDM table-level export (CSV or Parquet files per OMOP table).
- No FHIR Bulk Data ($export) endpoint compliant with HL7 Bulk Data Access specification.
- No cohort definition export in OHDSI ATLAS JSON format.
- No data dictionary or metadata export alongside data.
- No export audit logging (who exported what, when).

#### Implementation Steps

1. **Create OMOP CDM export service** in `backend/app/services/omop_export_service.py`:
   - Map ClinicalFacts to OMOP CDM v5.4 tables: PERSON, CONDITION_OCCURRENCE, DRUG_EXPOSURE, MEASUREMENT, PROCEDURE_OCCURRENCE, OBSERVATION, NOTE_NLP.
   - Export as CSV files (one per table) with OMOP CDM column headers.
   - Include data dictionary metadata file.

2. **Create FHIR Bulk Export endpoint** in `backend/app/api/fhir.py`:
   - `POST /api/v1/fhir/$export` -- initiate bulk export.
   - `GET /api/v1/fhir/$export/{job_id}` -- poll for completion.
   - Export as NDJSON (newline-delimited JSON) per FHIR Bulk Data spec.
   - Support `_type` parameter for resource type filtering.

3. **Create cohort export** in existing cohort API:
   - `GET /api/v1/cohorts/{id}/export/ohdsi` -- export cohort definition in ATLAS JSON format.
   - `GET /api/v1/cohorts/{id}/export/patients` -- export patient list with demographics.

4. **Add export audit logging**:
   - Log every export: who initiated, what was exported, when, how many records, destination.
   - Store in `ExportAuditLog` table.

5. **Add pipeline version to all exports** (links to 2.1):
   - Every export includes metadata header with pipeline version, vocabulary versions, export timestamp.

#### Acceptance Criteria

- [ ] OMOP CDM export produces valid CSV files that can be loaded into an OHDSI CDM database.
- [ ] FHIR Bulk Export produces valid NDJSON files per the Bulk Data Access specification.
- [ ] Cohort definitions export in ATLAS-compatible JSON format.
- [ ] All exports include pipeline version metadata.
- [ ] Export audit log captures who, what, when for every export.
- [ ] Exported OMOP data passes Achilles DQD (Data Quality Dashboard) basic checks.

#### Effort Estimate

- OMOP CDM export service: 3 days
- FHIR Bulk Export endpoint: 2 days
- Cohort export: 1 day
- Audit logging: 0.5 days
- Tests: 1.5 days
- **Total: 8 days**

#### Dependencies

- Requires: 2.1 (version pinning -- version metadata in exports)
- Feeds into: Clinical validation studies, pharma data sharing

---

### 2.3 Cohort Identification Accuracy

**Hardening Plan Reference:** CSO item 3 -- "Patient knowledge graphs must enable precise phenotyping. Validate against manual chart review."

#### Current State

- **KG-based patient representation exists:** `backend/app/models/knowledge_graph.py` -- KGNode and KGEdge models. `backend/app/services/graph_builder.py` and `graph_builder_db.py` build patient knowledge graphs.
- **ClinicalFact-based screening:** The trial eligibility service queries ClinicalFacts (not the KG) for patient screening.
- **No phenotype definitions:** No standardized phenotype definition format (like PheKB or OHDSI phenotype definitions).
- **No chart review comparison infrastructure.**

#### Gap Analysis

- No standardized phenotype library or phenotype definition service.
- No mechanism to compare KG-derived cohorts against manual chart review.
- No per-phenotype accuracy metrics.
- Eligibility screening uses string matching (`concept_name.ilike`) rather than OMOP concept hierarchy traversal.

#### Implementation Steps

1. **Create phenotype definition service** in `backend/app/services/phenotype_service.py`:
   - Support OHDSI-style phenotype definitions: concept sets + logic.
   - Use OMOP concept hierarchy (IS-A relationships via `backend/app/services/omop_hierarchy_service.py`) for concept set expansion.

2. **Replace string matching with concept set matching** in `_criterion_patient_query()`:
   - Instead of `ClinicalFact.concept_name.ilike(f"%{term}%")` (line 406), use `ClinicalFact.omop_concept_id.in_(expanded_concept_set)`.
   - This eliminates false matches from substring matching (e.g., "dermatitis" matching "contact dermatitis").

3. **Add phenotype validation endpoint**:
   - `POST /api/v1/phenotypes/{id}/validate` -- compare phenotype-derived cohort against ground truth.
   - Return precision, recall, F1 per phenotype.

4. **Build initial phenotype library** for demo therapeutic areas (atopic dermatitis, CSCC, DME) with validated concept sets.

#### Acceptance Criteria

- [ ] Phenotype definitions use OMOP concept sets with hierarchy expansion.
- [ ] Eligibility screening uses concept_id matching instead of string matching.
- [ ] Per-phenotype accuracy metrics available via API.
- [ ] Initial library of 3+ validated phenotype definitions.

#### Effort Estimate

- Phenotype service: 2 days
- Concept set matching migration: 2 days
- Validation endpoint: 1 day
- Initial phenotype library: 1 day
- **Total: 6 days**

#### Dependencies

- Requires: Dir CI 3.3 (value set management -- concept sets)
- Feeds into: 2.4 (trial eligibility fidelity)

---

### 2.4 Trial Eligibility Criteria Fidelity

**Hardening Plan Reference:** CSO item 4 -- "Structured criteria must faithfully represent protocol I/E. Target >89% parsing accuracy."

#### Current State

- **Criteria format:** `backend/app/schemas/trial.py` lines 17-34 -- `TrialCreate` uses freeform `dict` for `inclusion_criteria` and `exclusion_criteria`. No schema validation.
- **Demo criteria:** `backend/app/services/trial_eligibility_service.py` lines 198-357 -- three hardcoded demo trials with manually structured criteria.
- **No criteria parsing:** No service to parse natural-language trial criteria into structured format.
- **No criteria validation:** No mechanism to verify that structured criteria faithfully represent the protocol I/E text.

#### Gap Analysis

- `inclusion_criteria: dict | None` has no Pydantic model validation -- any arbitrary JSON accepted.
- No natural-language criteria parser (contrast with TrialGPT's 87.3% accuracy).
- No criteria fidelity scoring.
- No mapping from ClinicalTrials.gov criteria text to structured logic.

#### Implementation Steps

1. **Define strict criteria schema** in `backend/app/schemas/trial.py`:
   - Create `EligibilityCriterion` Pydantic model with validated fields: `criterion_type`, `name`, `codes`, `code_system`, `temporal_constraint`, `value_range`, `severity`, `negated`.
   - Create `CriteriaSet` model: `criteria: list[EligibilityCriterion]`, `root_operator: AND | OR`.
   - Replace `inclusion_criteria: dict | None` with `inclusion_criteria: CriteriaSet | None`.

2. **Create criteria parser service** in `backend/app/services/criteria_parser_service.py`:
   - Parse natural-language I/E criteria from ClinicalTrials.gov format.
   - Use LLM-assisted parsing with structured output validation.
   - Return structured criteria with parsing confidence per criterion.

3. **Create criteria fidelity validation endpoint**:
   - `POST /api/v1/trials/{id}/validate-criteria` -- compare structured criteria against source protocol text.
   - Return per-criterion fidelity score and flagged discrepancies.

4. **Add criteria versioning**:
   - Track changes to criteria over time.
   - When criteria change, re-run screening and flag patients whose eligibility changed.

#### Acceptance Criteria

- [ ] Eligibility criteria are validated by strict Pydantic schema.
- [ ] Criteria parser achieves >89% accuracy on ClinicalTrials.gov format.
- [ ] Criteria changes are versioned with before/after comparison.
- [ ] Each criterion links to source protocol text for auditability.

#### Effort Estimate

- Strict schema: 1 day
- Criteria parser service: 3 days
- Fidelity validation: 1 day
- Versioning: 1 day
- **Total: 6 days**

#### Dependencies

- Requires: 1.3 (temporal reasoning -- temporal criteria support), 2.3 (concept sets)

---

### 2.5 Longitudinal Patient Tracking

**Hardening Plan Reference:** CSO item 5 -- "Disease trajectory must be reconstructable from knowledge graph."

#### Current State

- **Knowledge graph model:** `backend/app/models/knowledge_graph.py` -- KGNode and KGEdge with temporal properties.
- **Temporal extractor:** `backend/app/services/temporal_extractor.py` extracts dates from clinical text.
- **ClinicalFact has `start_date`:** The model at `backend/app/models/clinical_fact.py` has `start_date` column.
- **Temporal query service exists:** `backend/app/services/temporal_query_service.py` -- provides temporal queries against the KG.

#### Gap Analysis

- No `end_date` tracking for conditions (when did the condition resolve?).
- No treatment sequence reconstruction (first-line, second-line therapy ordering).
- No disease progression timeline visualization endpoint.
- Temporal ordering relies on `start_date` only; many facts lack dates.
- No longitudinal data completeness scoring.

#### Implementation Steps

1. **Add `end_date` to ClinicalFact** model and populate from FHIR `abatementDateTime` and `effectivePeriod.end`.

2. **Create patient timeline endpoint** at `GET /api/v1/patients/{id}/timeline`:
   - Return chronologically ordered clinical events grouped by domain.
   - Include date confidence and precision.
   - Support filtering by domain (conditions only, medications only).

3. **Create treatment sequence reconstruction** service:
   - Order medications by start_date.
   - Identify first-line, second-line, etc. within therapeutic categories.
   - Detect concurrent therapies.

4. **Add longitudinal completeness score** per patient:
   - Score based on: has demographics, has conditions with dates, has medications with dates, has labs with dates.
   - Flag patients with insufficient longitudinal data for research use.

#### Acceptance Criteria

- [ ] Patient timeline API returns chronologically ordered events with dates.
- [ ] Treatment sequence shows first-line/second-line ordering.
- [ ] Longitudinal completeness score available per patient.
- [ ] Facts with and without temporal data are clearly distinguished.

#### Effort Estimate

- end_date column + FHIR integration: 1 day
- Timeline endpoint: 1.5 days
- Treatment sequence service: 2 days
- Completeness scoring: 1 day
- **Total: 5.5 days**

#### Dependencies

- Requires: 1.3 (temporal reasoning)
- Feeds into: 2.3 (cohort identification -- temporal phenotyping)

---

## 3. Director of Clinical Informatics

### 3.1 Terminology Governance Workflow

**Hardening Plan Reference:** Dir CI item 1 -- "Who approves new OMOP concept mappings? Establish a terminology committee or review queue."

#### Current State

- **Mapping services exist:** `backend/app/services/mapping.py`, `mapping_db.py`, `mapping_sql.py` -- provide OMOP concept mapping with exact, fuzzy, and ML methods.
- **Vocabulary service:** `backend/app/services/vocabulary.py` and `vocabulary_db.py` -- load and query OMOP concepts.
- **No approval workflow:** Any mapping created by the NLP pipeline is immediately used without human review.
- **No mapping review queue:** No endpoint to list pending/unreviewed mappings.
- **No mapping audit:** No record of who approved a mapping or when.

#### Gap Analysis

- No concept mapping review/approval workflow.
- No role-based access for terminology review (who can approve mappings).
- No queue of unmapped or low-confidence mappings for review.
- No mapping feedback mechanism (clinician corrects wrong mapping).
- No terminology committee governance structure.

#### Implementation Steps

1. **Create mapping review model** in `backend/app/models/mapping_review.py`:
   - `MappingReview`: id, mention_text, suggested_concept_id, suggested_concept_name, mapping_confidence, mapping_method, review_status (PENDING, APPROVED, REJECTED, REMAPPED), reviewer_id, reviewed_at, approved_concept_id, notes.

2. **Create mapping review queue API** in `backend/app/api/terminology_governance.py`:
   - `GET /api/v1/terminology/review-queue` -- list pending mapping reviews, filterable by confidence threshold.
   - `POST /api/v1/terminology/review/{id}/approve` -- approve a mapping.
   - `POST /api/v1/terminology/review/{id}/reject` -- reject with reason.
   - `POST /api/v1/terminology/review/{id}/remap` -- suggest alternate concept.

3. **Route low-confidence mappings to review queue**:
   - In `backend/app/services/mapping_db.py`, when best match confidence < 0.8, create a `MappingReview` record.
   - Continue using the suggested mapping but mark ClinicalFact as `review_pending=True`.

4. **Create governance dashboard**:
   - Total pending reviews, average review time, rejection rate.
   - Top unmapped terms.
   - Reviewer activity metrics.

5. **Document terminology governance SOP** (non-code):
   - Review cadence (daily/weekly).
   - Reviewer qualifications.
   - Escalation path for ambiguous mappings.

#### Acceptance Criteria

- [ ] Low-confidence mappings (<0.8) are automatically queued for review.
- [ ] Reviewers can approve, reject, or remap via API.
- [ ] Approved mappings update the ClinicalFact and clear `review_pending`.
- [ ] Governance dashboard shows queue depth, review latency, rejection rates.
- [ ] All review actions are audit-logged with reviewer identity and timestamp.

#### Effort Estimate

- Model + migration: 0.5 days
- API endpoints: 1.5 days
- Queue routing logic: 1 day
- Dashboard: 0.5 days
- SOP document: 0.5 days
- **Total: 4 days**

#### Dependencies

- Feeds into: Dir CI 3.5 (vocabulary regression testing), CSO 2.1 (reproducibility)

---

### 3.2 FHIR R4 Conformance Testing

**Hardening Plan Reference:** Dir CI item 2 -- "Validate against US Core profiles."

#### Current State

- **FHIR import handles:** Patient, Condition, MedicationRequest, MedicationStatement, AllergyIntolerance, Observation, Procedure, DocumentReference, DiagnosticReport -- at `backend/app/services/fhir_import.py` lines 266-276.
- **FHIR export handles:** Condition, MedicationStatement, Observation, Procedure, DiagnosticReport -- at `backend/app/services/fhir_exporter.py`.
- **FHIR terminology service:** `backend/app/services/fhir_terminology.py` implements $lookup, $validate-code, $expand, $translate, $subsumes, $closure.
- **Existing conformance tests:** `backend/tests/test_fhir_conformance.py` and `backend/tests/test_fhir_terminology_conformance.py` exist but test only terminology operations with mocked services, not actual FHIR resource conformance.
- **No US Core profile validation:** Imported and exported resources are not validated against US Core FHIR R4 profiles.
- **No FHIR resource validation library:** No `fhir.resources` or similar validation library is used.

#### Gap Analysis

- No validation that imported FHIR resources conform to US Core profiles.
- No validation that exported FHIR resources conform to US Core profiles.
- Missing FHIR resource types: Encounter, Immunization (mentioned in hardening plan).
- No conformance statement / CapabilityStatement endpoint.
- FHIR import uses lenient parsing -- malformed resources are silently skipped (lines 300-303 of `fhir_import.py`).
- No structured error reporting for non-conformant resources.

#### Implementation Steps

1. **Add FHIR resource validation** using `fhirpath` or `fhir.resources` library:
   - Validate imported bundles against US Core 6.1.0 profiles.
   - Validate exported resources before returning.
   - Log validation errors with resource ID and violation details.

2. **Create conformance test suite** at `backend/tests/test_fhir_us_core_conformance.py`:
   - Test each resource type against US Core profile requirements.
   - Test required elements, required bindings, cardinality.
   - Test with real-world FHIR samples (use Synthea-generated data).

3. **Add CapabilityStatement endpoint** at `GET /api/v1/fhir/metadata`:
   - Return FHIR CapabilityStatement listing supported resource types, operations, and profiles.

4. **Add Encounter and Immunization import handlers** to `fhir_import.py`:
   - `_import_encounter()` -- create visit/encounter facts.
   - `_import_immunization()` -- create immunization facts.

5. **Create FHIR validation report endpoint**:
   - `POST /api/v1/fhir/validate` -- accept a FHIR resource or bundle and return validation results.
   - Report conformance level (valid, warnings, errors) with specific profile violations.

#### Acceptance Criteria

- [ ] All imported FHIR resources are validated against US Core 6.1.0 profiles.
- [ ] All exported FHIR resources pass US Core profile validation.
- [ ] Non-conformant resources are quarantined with structured error reports (no silent skipping).
- [ ] CapabilityStatement endpoint returns valid FHIR metadata.
- [ ] Encounter and Immunization resource types are handled.
- [ ] Conformance test suite covers all 10 US Core resource types with >= 50 test cases.

#### Effort Estimate

- FHIR validation integration: 2 days
- US Core conformance test suite: 2 days
- CapabilityStatement endpoint: 0.5 days
- Encounter + Immunization handlers: 1 day
- Validation report endpoint: 0.5 days
- **Total: 6 days**

#### Dependencies

- Feeds into: CSO 2.2 (publication-ready exports must be FHIR-conformant)

---

### 3.3 Value Set Management

**Hardening Plan Reference:** Dir CI item 3 -- "Curated, versioned value sets. Track which SNOMED/ICD-10/LOINC/RxNorm versions are in use."

#### Current State

- **Vocabulary versioning:** `backend/app/services/vocabulary_version_service.py` tracks vocabulary versions per concept.
- **FHIR terminology service:** `backend/app/services/fhir_terminology.py` supports $expand for ValueSets.
- **Code system mapping:** `backend/app/services/fhir_terminology.py` lines 40-80 maps code system URIs.
- **No curated value set library:** No pre-built value sets for common clinical use cases (e.g., "Type 2 Diabetes" value set, "Hypertension medications" value set).
- **No value set versioning:** The $expand endpoint does not support version-specific expansion.

#### Gap Analysis

- No value set management API (create, version, publish, retire).
- No value set storage model (only ad-hoc concept lists in trial criteria).
- No version tracking per value set (which SNOMED version was used to build it).
- No value set binding to eligibility criteria (criteria reference display text, not value sets).
- Trial eligibility criteria use `codes` with raw display text rather than value set references.

#### Implementation Steps

1. **Create value set model** in `backend/app/models/value_set.py`:
   - `ValueSet`: id, name, description, oid, version, status (draft/active/retired), vocabulary_id, vocabulary_version, created_by, created_at, published_at.
   - `ValueSetMember`: id, value_set_id, concept_id, concept_code, concept_name, code_system, include_descendants (bool).

2. **Create value set management API** in `backend/app/api/valuesets.py` (extend existing if present):
   - `POST /api/v1/valuesets` -- create a value set.
   - `PUT /api/v1/valuesets/{id}` -- update (creates new version).
   - `POST /api/v1/valuesets/{id}/expand` -- expand value set with descendant concepts.
   - `GET /api/v1/valuesets/{id}/members` -- list current members.
   - `POST /api/v1/valuesets/{id}/publish` -- publish a draft value set.

3. **Create initial value sets** for demo therapeutic areas:
   - "Atopic Dermatitis" condition value set (ICD-10 + SNOMED).
   - "Anti-IL4/IL13 Biologics" medication value set (RxNorm).
   - "HbA1c" measurement value set (LOINC).

4. **Link value sets to trial criteria**:
   - Modify criteria schema to accept `value_set_id` instead of raw `codes` list.
   - Modify `_criterion_patient_query()` to expand value sets into concept_id IN queries.

5. **Track vocabulary source versions** in value set metadata:
   - Record which SNOMED CT version, RxNorm version, etc. was used to build each value set.

#### Acceptance Criteria

- [ ] Value sets can be created, versioned, expanded, and published via API.
- [ ] Value set expansion includes descendant concepts from OMOP hierarchy.
- [ ] Trial criteria can reference value sets instead of raw code lists.
- [ ] Each value set records the vocabulary version used to build it.
- [ ] At least 3 curated value sets exist for demo therapeutic areas.

#### Effort Estimate

- Model + migration: 1 day
- API endpoints: 2 days
- Value set expansion with hierarchy: 1 day
- Initial value set creation: 1 day
- Criteria integration: 1 day
- **Total: 6 days**

#### Dependencies

- Requires: OMOP hierarchy service (`backend/app/services/omop_hierarchy_service.py`)
- Feeds into: 2.3 (cohort identification), 3.5 (vocabulary regression testing)

---

### 3.4 OMOP ETL Validation

**Hardening Plan Reference:** Dir CI item 4 -- "Systematic comparison of source FHIR data vs OMOP CDM output."

#### Current State

- **FHIR-to-OMOP transformation:** `backend/app/services/fhir_import.py` transforms FHIR resources directly into ClinicalFacts (semi-OMOP). This is effectively an ETL pipeline.
- **Data quality API exists:** `backend/app/api/data_quality.py` (lines 1-60) provides completeness and consistency endpoints using `data_completeness_service`, `data_consistency_service`, and `data_quality_service`.
- **No ETL validation:** There is no comparison between source FHIR data and resulting ClinicalFacts to verify no semantic loss.

#### Gap Analysis

- No round-trip validation (FHIR -> ClinicalFact -> FHIR export, then compare).
- No ETL error rate tracking (how many FHIR resources fail to produce ClinicalFacts).
- No semantic drift detection (are we losing clinical meaning in the transformation?).
- No OHDSI DQD (Data Quality Dashboard) integration.
- No ETL mapping documentation.

#### Implementation Steps

1. **Create ETL validation service** in `backend/app/services/etl_validation_service.py`:
   - Round-trip test: import FHIR bundle, export ClinicalFacts as FHIR, compare.
   - Compare: resource count, concept coverage, value preservation (lab values match).
   - Score: ETL fidelity percentage.

2. **Create ETL validation endpoint**:
   - `POST /api/v1/etl/validate` -- accept a FHIR bundle, run import, compare with source.
   - Return per-resource comparison with match/mismatch details.

3. **Track ETL metrics** per import:
   - Total resources in bundle, resources processed, resources skipped, resources with errors.
   - Store in `ETLImportLog` table for trend analysis.

4. **Add OHDSI DQD integration** (long-term):
   - Export OMOP CDM tables and run Achilles + DQD checks.
   - Return DQD results via API.

5. **Create ETL mapping documentation** (non-code):
   - Document every FHIR element to OMOP CDM column mapping.
   - Document semantic decisions (e.g., AllergyIntolerance maps to Observation domain).

#### Acceptance Criteria

- [ ] Round-trip validation (FHIR -> ClinicalFact -> FHIR) preserves >= 95% of clinical semantics.
- [ ] ETL import logs capture per-resource success/failure with reasons.
- [ ] ETL fidelity score available via API.
- [ ] Mapping documentation covers all supported FHIR resource types.
- [ ] ETL error rate is tracked over time.

#### Effort Estimate

- ETL validation service: 2 days
- ETL logging: 0.5 days
- Validation endpoint: 0.5 days
- Documentation: 1 day
- Tests: 1 day
- **Total: 5 days**

#### Dependencies

- Requires: 3.2 (FHIR conformance -- validated FHIR resources)
- Feeds into: CSO 2.2 (publication-ready exports)

---

### 3.5 Vocabulary Update Regression Testing

**Hardening Plan Reference:** Dir CI item 5 -- "SNOMED CT, RxNorm, LOINC release quarterly. Each update can break existing mappings."

#### Current State

- **Vocabulary version service:** `backend/app/services/vocabulary_version_service.py` (lines 1-160+) handles version imports with `import_version_update()`, tracking added/updated/deprecated concepts.
- **Concept status tracking:** The `Concept` model has `status` (active/deprecated/retired), `status_changed_at`, `previous_concept_id`, and `vocabulary_version` fields.
- **Version history:** `get_version_history()` follows `previous_concept_id` chains.
- **No regression test suite:** No automated comparison of pre-update vs post-update mapping results.
- **No impact analysis:** When a concept is deprecated, there is no automatic analysis of which ClinicalFacts or eligibility criteria reference it.

#### Gap Analysis

- No automated regression test that runs before and after a vocabulary update to compare results.
- No "snapshot baseline" mechanism to capture current mappings before update.
- No deprecated concept impact analysis (which patients, trials, facts are affected).
- No alert when a vocabulary update deprecates concepts used in active trial criteria.
- No migration tooling to map deprecated concepts to successors.

#### Implementation Steps

1. **Create vocabulary regression test service** in `backend/app/services/vocab_regression_service.py`:
   - `snapshot_baseline()` -- capture current state of all active mappings (500+ curated term -> concept pairs).
   - `apply_update_and_compare()` -- load new vocabulary version, re-map terms, diff against baseline.
   - `generate_impact_report()` -- for each changed mapping, list affected ClinicalFacts, trials, value sets.

2. **Create regression test fixtures** at `backend/fixtures/vocab_regression_baseline.json`:
   - 500+ curated term-to-concept mappings covering conditions, drugs, measurements, procedures.
   - Each entry: `{"term": "diabetes mellitus", "expected_concept_id": 201826, "expected_domain": "Condition", "vocabulary": "SNOMED"}`.

3. **Create vocabulary update API**:
   - `POST /api/v1/vocabulary/update/preview` -- show what would change without applying.
   - `POST /api/v1/vocabulary/update/apply` -- apply update after review.
   - `GET /api/v1/vocabulary/update/impact` -- deprecated concepts + affected resources.

4. **Create concept migration tooling**:
   - When a concept is deprecated, find successor concepts via `previous_concept_id` chain and OMOP concept relationships.
   - `POST /api/v1/vocabulary/migrate/{deprecated_concept_id}` -- migrate all references to successor.

5. **Add vocabulary version alerts**:
   - When running screening and a criterion references a deprecated concept, log warning and include in `CriterionResult.details`.

#### Acceptance Criteria

- [ ] Baseline of 500+ curated mappings exists and is tested in CI.
- [ ] Vocabulary update preview shows all changes before applying.
- [ ] Deprecated concept impact analysis identifies affected ClinicalFacts and trials.
- [ ] Migration tooling can remap deprecated concepts to successors.
- [ ] Alert fires when active trial criteria reference deprecated concepts.
- [ ] All regression tests pass after vocabulary update with no unintended mapping changes.

#### Effort Estimate

- Regression test service: 2 days
- Baseline fixtures: 1 day (with clinical input)
- Update preview/apply API: 1 day
- Migration tooling: 1 day
- Alert integration: 0.5 days
- **Total: 5.5 days**

#### Dependencies

- Requires: 3.3 (value set management -- value sets must also be regression-tested)
- Feeds into: CSO 2.1 (reproducibility), Dir CI 3.1 (terminology governance)

---

## 4. CDO / Chief Data Officer

### 4.1 Data Lineage Tracking

**Hardening Plan Reference:** CDO item 1 -- "Every clinical fact must trace back to: source FHIR resource -> extraction method -> mention with offsets -> mapping confidence -> selected OMOP concept."

#### Current State

- **Provenance service exists:** `backend/app/services/provenance_service.py` (lines 1-80+) defines `SourceDocument`, `ExtractionInfo`, `ExtractionMethod` enum (MANUAL, NLP_RULE, NLP_ML, NLP_LLM, FHIR_IMPORT, etc.) and confidence levels. This is a comprehensive data model but appears to be an in-memory service, NOT persisted to the database.

- **FactEvidence model exists:** `backend/app/models/clinical_fact.py` defines `FactEvidence` with `evidence_type`, `source_id`, `source_table`, `weight`, linking facts to their sources.

- **ClinicalFact has confidence:** The model tracks confidence scores.

- **FHIR import tracks source:** `fhir_import.py` stores `fhir_id` in KGNode properties.

- **No end-to-end lineage visualization:** There is no API that returns the complete provenance chain for a fact.

#### Gap Analysis

- Provenance service is in-memory, not persisted to database.
- No single API endpoint that returns the full lineage chain: FHIR resource -> Document -> Mention -> MappingCandidate -> ClinicalFact.
- Extraction method is not recorded on ClinicalFact (as noted in 2.1).
- Mention-to-fact linkage exists via FactEvidence but is not consistently populated.
- No lineage visualization in the frontend.

#### Implementation Steps

1. **Persist provenance to database** -- ensure `FactEvidence` records are created for every ClinicalFact:
   - FHIR import: create FactEvidence with `evidence_type=STRUCTURED_DATA`, `source_table="fhir_resource"`.
   - NLP extraction: create FactEvidence with `evidence_type=NLP_MENTION`, `source_table="mentions"`.

2. **Create lineage API endpoint** at `GET /api/v1/facts/{fact_id}/lineage`:
   - Return: source document (with text snippet at offsets), extraction method, mention details, mapping candidates considered, selected concept, confidence at each stage.

3. **Create patient-level lineage endpoint** at `GET /api/v1/patients/{id}/lineage`:
   - Return all ClinicalFacts with their complete lineage chains.
   - Filterable by domain, date range, confidence threshold.

4. **Add `extraction_method` to ClinicalFact** model (same as 2.1 step).

5. **Create lineage completeness metric**: percentage of ClinicalFacts that have complete lineage (source document + mention + mapping).

#### Acceptance Criteria

- [ ] Every ClinicalFact has at least one FactEvidence record linking it to its source.
- [ ] Lineage API returns complete chain: source -> extraction -> mention -> mapping -> fact.
- [ ] Lineage completeness metric is >= 95% for all facts.
- [ ] FHIR-imported facts link back to FHIR resource ID.
- [ ] NLP-extracted facts link back to document ID, section, and character offsets.

#### Effort Estimate

- FactEvidence consistency enforcement: 1.5 days
- Lineage API endpoints: 1.5 days
- extraction_method column (shared with 2.1): 0 additional days
- Completeness metric: 0.5 days
- Tests: 0.5 days
- **Total: 4 days**

#### Dependencies

- Requires: CSO 2.1 (version pinning -- extraction_method column)
- Feeds into: 4.2 (data quality dashboard)

---

### 4.2 Data Quality Dashboard

**Hardening Plan Reference:** CDO item 2 -- "Completeness, consistency, accuracy, timeliness metrics."

#### Current State

- **Data quality API exists:** `backend/app/api/data_quality.py` (lines 1-60) with endpoints:
  - `GET /data-quality/completeness` -- overall completeness report per OMOP table.
  - `GET /data-quality/completeness/{table}` -- table-specific completeness.
  - `GET /data-quality/completeness/trends` -- historical trends.
  - `GET /data-quality/consistency` -- consistency validation.
  - `POST /data-quality/consistency/run` -- trigger consistency checks.

- **Services exist:** `data_completeness_service`, `data_consistency_service`, `data_quality_service` are imported.

- **Quality reports API:** `backend/app/api/quality/quality_reports.py` also exists.

#### Gap Analysis

- The existing data quality endpoints focus on OMOP table-level completeness. Missing:
  - Per-patient data quality scoring (how complete is each patient's record?).
  - Timeliness metrics (how fresh is the data? when was it last updated?).
  - Accuracy metrics (what percentage of facts have been validated?).
  - NLP-specific quality metrics (unmapped term rate, low-confidence extraction rate).
  - Comparison to industry benchmarks.
- No unified dashboard that combines completeness, consistency, timeliness, and accuracy.

#### Implementation Steps

1. **Create unified data quality dashboard endpoint** at `GET /api/v1/data-quality/dashboard`:
   - Aggregate: completeness score (0-100), consistency score, timeliness score, accuracy score.
   - Breakdown by data source (FHIR import, NLP extraction, manual entry).
   - Trend over last 30/90 days.

2. **Add NLP-specific quality metrics**:
   - Unmapped term rate: percentage of extracted mentions without OMOP mapping.
   - Low-confidence rate: percentage of ClinicalFacts with confidence < 0.7.
   - Assertion distribution: breakdown of PRESENT/ABSENT/POSSIBLE/UNKNOWN.

3. **Add timeliness metrics**:
   - Data freshness: average age of most recent ClinicalFact per patient.
   - Processing latency: time from document ingestion to ClinicalFact creation.
   - Stale data alert: patients with no new data in > 90 days.

4. **Create quality scorecard per data domain** (Conditions, Drugs, Labs, Procedures):
   - Completeness: % of patients with at least one fact in this domain.
   - Mapping coverage: % of facts with valid OMOP concept_id (not 0).
   - Confidence distribution histogram.

5. **Frontend dashboard** -- quality summary cards with trend sparklines.

#### Acceptance Criteria

- [ ] Unified dashboard endpoint returns completeness, consistency, timeliness, accuracy scores.
- [ ] NLP quality metrics (unmapped rate, low-confidence rate) are tracked and alertable.
- [ ] Timeliness metrics show data freshness per patient.
- [ ] Per-domain quality scorecards available.
- [ ] Alerts fire when any quality metric falls below threshold.

#### Effort Estimate

- Dashboard aggregation endpoint: 1 day
- NLP quality metrics: 1 day
- Timeliness metrics: 0.5 days
- Domain scorecards: 0.5 days
- Frontend dashboard: 1 day
- **Total: 4 days**

#### Dependencies

- Requires: 4.1 (data lineage -- lineage completeness feeds quality score)
- Feeds into: VP Product dashboards

---

### 4.3 Data Completeness Scoring Per Patient

**Hardening Plan Reference:** CDO item 6 -- "For trial matching, know whether you have enough data to make a confident determination. Flag UNKNOWN vs NOT MET."

#### Current State

- **PatientEligibility schema:** `backend/app/schemas/trial.py` (lines 167-181) has `missing_data: list[str]` field that lists criteria with insufficient data.
- **CriterionResult status values:** `PASS`, `FAIL`, `UNKNOWN`, `POSSIBLE_MATCH` (line 151) -- `UNKNOWN` indicates insufficient data.
- **Trial eligibility service:** `_evaluate_criterion()` at `backend/app/services/trial_eligibility_service.py` (lines 760-768) returns `UNKNOWN` when no matching ClinicalFacts found.
- **No per-patient completeness score:** There is no pre-computed score of how complete a patient's record is for trial matching.

#### Gap Analysis

- `UNKNOWN` is treated as "data missing" but is reported as part of `missing_data` list without scoring.
- No overall patient data completeness score (0-100%) covering demographics, conditions, labs, medications.
- No distinction between "no data available" and "data checked, condition not present" (UNKNOWN vs NOT MET).
- No data sufficiency assessment before screening (can we even evaluate this patient?).
- ScreeningResponse lumps data-insufficient patients into `ineligible_count`.

#### Implementation Steps

1. **Create patient completeness scoring service** in `backend/app/services/patient_completeness_service.py`:
   - Compute per-patient completeness score based on required data domains:
     - Demographics (age, sex): weight 20%
     - Conditions: weight 25%
     - Medications: weight 20%
     - Labs/Measurements: weight 20%
     - Procedures: weight 15%
   - Score = weighted sum of (has_data_in_domain ? 1 : 0).

2. **Add completeness endpoint** at `GET /api/v1/patients/{id}/completeness`:
   - Return overall score and per-domain breakdown.
   - List specific missing data categories.
   - Flag whether patient has sufficient data for trial matching.

3. **Add trial-specific data sufficiency** in `check_patient_eligibility()`:
   - Before evaluating criteria, compute which criteria CAN be evaluated given available data.
   - Add `data_sufficiency_score: float` to `PatientEligibility` -- percentage of criteria that can be evaluated.
   - Add `data_sufficiency_warning: str | None` if score < 0.7.

4. **Distinguish UNKNOWN from NOT_MET** in CriterionResult:
   - `UNKNOWN`: No data available to evaluate (we cannot determine).
   - `NOT_MET`: Data exists but criterion is not satisfied.
   - Modify `_evaluate_criterion()` to use `NOT_MET` when facts exist in the domain but don't match the criterion.

5. **Add batch completeness scoring** at `GET /api/v1/patients/completeness?min_score=0.7`:
   - Return all patients with completeness score above threshold.
   - Useful for identifying patients with sufficient data for trial matching.

#### Acceptance Criteria

- [ ] Patient completeness score (0-100%) available via API per patient.
- [ ] Per-domain completeness breakdown (demographics, conditions, medications, labs, procedures).
- [ ] Trial-specific data sufficiency score in PatientEligibility response.
- [ ] `NOT_MET` distinguished from `UNKNOWN` in CriterionResult.
- [ ] ScreeningResponse includes `data_insufficient_count` separate from `ineligible_count`.
- [ ] Patients with completeness score < 50% are flagged with data sufficiency warning.

#### Effort Estimate

- Completeness scoring service: 1.5 days
- Patient completeness endpoint: 0.5 days
- Trial-specific sufficiency: 1 day
- NOT_MET vs UNKNOWN distinction: 0.5 days
- ScreeningResponse updates: 0.5 days
- Tests: 1 day
- **Total: 5 days**

#### Dependencies

- Feeds into: 1.5 (patient safety guardrails -- missing data triggers safety hold)
- Feeds into: 1.6 (false negative monitoring -- data insufficiency as root cause)

---

## 5. Dependency Graph

```
CMO 1.1 (Review Labeling) ───────────────────────┐
    |                                             |
    v                                             v
CMO 1.5 (Safety Guardrails) <──────────── CDO 4.3 (Patient Completeness)
    |
    v
CMO 1.2 (Assertion Validation) ────> CMO 1.3 (Temporal Validation)
    |                                       |
    v                                       v
CMO 1.4 (Validation Study) <───── CSO 2.4 (Criteria Fidelity) <── CSO 2.3 (Cohort Accuracy)
    |                                                                      |
    v                                                                      |
CMO 1.6 (FN Monitoring) ────> CMO 1.7 (Feedback Loop)          Dir CI 3.3 (Value Sets)
                                                                      |
CSO 2.1 (Reproducibility) ────> CSO 2.2 (Data Exports)         Dir CI 3.5 (Vocab Regression)
    |                                                                      |
    v                                                               Dir CI 3.1 (Term Governance)
CDO 4.1 (Data Lineage) ────> CDO 4.2 (Quality Dashboard)
                                                              Dir CI 3.2 (FHIR Conformance)
CSO 2.5 (Longitudinal) <──── CMO 1.3 (Temporal)                    |
                                                              Dir CI 3.4 (ETL Validation)
```

---

## 6. Priority Sequencing

### Phase 1: Safety Foundation (Weeks 1-3)
| Item | Effort | Priority | Rationale |
|------|--------|----------|-----------|
| 1.1 CDS Review Labeling | 3.5d | P0 | Regulatory (Cures Act Criterion 4) |
| 1.5 Patient Safety Guardrails | 4d | P0 | Patient safety (hard exclusion enforcement) |
| 4.3 Patient Completeness | 5d | P0 | UNKNOWN vs NOT_MET distinction critical for safety |

### Phase 2: Clinical Accuracy (Weeks 3-6)
| Item | Effort | Priority | Rationale |
|------|--------|----------|-----------|
| 1.2 Assertion Validation | 6.5d | P1 | Clinical accuracy foundation |
| 1.3 Temporal Validation | 5d | P1 | Eligibility accuracy |
| 3.3 Value Set Management | 6d | P1 | Concept set matching replaces string matching |

### Phase 3: Scientific Rigor (Weeks 6-10)
| Item | Effort | Priority | Rationale |
|------|--------|----------|-----------|
| 2.1 Reproducibility | 4d | P1 | Required for all downstream research work |
| 4.1 Data Lineage | 4d | P1 | Provenance for regulatory compliance |
| 3.1 Terminology Governance | 4d | P2 | Mapping quality governance |
| 3.5 Vocabulary Regression | 5.5d | P2 | Mapping stability |

### Phase 4: Validation and Monitoring (Weeks 10-16)
| Item | Effort | Priority | Rationale |
|------|--------|----------|-----------|
| 1.4 Validation Study Design | 6.5d | P2 | Scientific credibility |
| 1.6 FN Monitoring | 5d | P2 | Ongoing quality tracking |
| 1.7 Feedback Loop | 4d | P2 | Continuous improvement |
| 2.3 Cohort Accuracy | 6d | P2 | Research utility |

### Phase 5: Standards and Export (Weeks 16-22)
| Item | Effort | Priority | Rationale |
|------|--------|----------|-----------|
| 3.2 FHIR Conformance | 6d | P2 | Interoperability |
| 3.4 ETL Validation | 5d | P2 | Data transformation quality |
| 2.2 Publication-Ready Exports | 8d | P3 | Partner/research enablement |
| 2.4 Criteria Fidelity | 6d | P3 | Research accuracy |
| 2.5 Longitudinal Tracking | 5.5d | P3 | Research utility |
| 4.2 Quality Dashboard | 4d | P3 | Operational visibility |

### Total Effort Summary

| Role | Items | Total Effort |
|------|-------|-------------|
| CMO | 7 items | 33 days |
| CSO | 5 items | 29.5 days |
| Dir Clinical Informatics | 5 items | 26.5 days |
| CDO | 3 items | 13 days |
| **Total** | **20 items** | **102 days** |

At 1 engineer, this is approximately 5 months of work. With 2 engineers working in parallel on non-dependent items, this reduces to approximately 3 months.

---

*Generated from codebase analysis of `/Users/alexstinard/projects/brainstorm/jan-14-2026` against hardening plan items for CMO, CSO, CDO, and Director of Clinical Informatics roles. February 2026.*
