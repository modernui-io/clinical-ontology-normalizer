# Clinical Validation Study Protocol

## CMO-1.4: Screening Accuracy Validation

**Document ID:** VS-PROTO-001
**Version:** 1.0
**Status:** DRAFT
**Effective Date:** TBD

---

## 1. Study Objectives

### 1.1 Primary Objective

Measure the accuracy of the automated clinical trial patient screening system
by comparing its eligibility determinations against gold-standard physician
review. The primary endpoints are sensitivity and specificity of the system's
screening decisions.

### 1.2 Secondary Objectives

- Quantify positive predictive value (PPV) and negative predictive value (NPV)
- Measure inter-rater agreement (Cohen's Kappa) between the system and
  clinical reviewers
- Identify systematic screening errors (false negative patterns)
- Assess performance across different trial therapeutic areas (oncology,
  dermatology, ophthalmology)

---

## 2. Study Design

### 2.1 Design Type

Retrospective chart review with blinded comparison.

### 2.2 Overview

1. Select a random sample of patient records that have been screened by the
   automated system for a given clinical trial.
2. Board-certified physicians independently review the same patient records
   against the same eligibility criteria, blinded to the system's results.
3. Compare the system's ELIGIBLE/INELIGIBLE determination against the
   physician's determination (gold standard).
4. Compute validation metrics from the resulting confusion matrix.

### 2.3 Blinding

- Clinical reviewers are blinded to the system's screening result.
- Reviewers receive the patient record and the trial's eligibility criteria
  only.
- Unblinding occurs after all reviews are complete and locked.

---

## 3. Sample Selection Criteria

### 3.1 Inclusion Criteria (for study samples)

- Patient records that have been processed through the automated screening
  pipeline.
- Records with sufficient clinical data to evaluate eligibility criteria
  (data completeness score >= 0.7).
- Patients screened within the most recent 12-month period.

### 3.2 Exclusion Criteria (for study samples)

- Records with known data quality issues (flagged by data quality dashboard).
- Duplicate patient records.
- Records where the screening pipeline encountered system errors.

### 3.3 Sampling Strategy

- Stratified random sampling to ensure representation across:
  - Eligible and ineligible patients (proportional to actual screening rates)
  - All therapeutic areas under study
  - Different data completeness levels
- Over-sample from borderline cases (match score 0.4-0.7) to stress-test
  the system at decision boundaries.

---

## 4. Gold Standard Definition

### 4.1 Reviewer Qualifications

- Board-certified physician (MD or DO) with active medical license.
- Minimum 3 years of clinical experience in the relevant therapeutic area.
- Completed training on the trial's specific eligibility criteria.
- No conflicts of interest with the trial sponsor or screening system vendor.

### 4.2 Review Process

1. Reviewer receives de-identified patient record and trial eligibility
   criteria.
2. Reviewer evaluates each inclusion and exclusion criterion independently.
3. Reviewer records overall determination: ELIGIBLE or INELIGIBLE.
4. Reviewer documents rationale for any borderline decisions.
5. For cases where two reviewers disagree, a third senior reviewer
   adjudicates.

### 4.3 Inter-Reviewer Reliability

- A subset of 20% of cases will be independently reviewed by two physicians.
- Cohen's Kappa between reviewers must exceed 0.80 to validate the gold
  standard itself.
- If inter-reviewer Kappa < 0.80, review training is repeated and
  discordant criteria are clarified.

---

## 5. Sample Size Calculation

### 5.1 Power Analysis

Based on the primary endpoint (sensitivity), with the following assumptions:

- Expected sensitivity: 95% (H1)
- Null hypothesis sensitivity: 85% (H0)
- Type I error (alpha): 0.05 (two-sided)
- Type II error (beta): 0.20 (power = 80%)
- Prevalence of eligible patients: 30% (estimated from screening data)

Using the formula for comparing a proportion to a reference value:

    n_positive = (Z_alpha/2 + Z_beta)^2 * p0 * (1 - p0) / (p1 - p0)^2

    n_positive = (1.96 + 0.84)^2 * 0.85 * 0.15 / (0.95 - 0.85)^2
    n_positive = 7.84 * 0.1275 / 0.01
    n_positive = 100 (actual positives needed)

With a 30% prevalence of eligible patients:

    Total sample size = 100 / 0.30 = 334 patients (minimum)

### 5.2 Recommended Sample Size

- **Minimum:** 334 patients per trial type
- **Recommended:** 400 patients per trial type (to account for incomplete data)
- **Total across 3 therapeutic areas:** 1,200 patients

---

## 6. Data Collection Procedures

### 6.1 Data Elements Collected

For each case in the study:

| Field | Description |
|---|---|
| Patient ID (de-identified) | Unique study identifier |
| Trial ID | Clinical trial being validated |
| System Result | ELIGIBLE or INELIGIBLE |
| Gold Standard Result | ELIGIBLE or INELIGIBLE |
| Reviewer ID | Identifier of the reviewing physician |
| Review Date | Date of physician review |
| Reviewer Notes | Free-text rationale for borderline cases |
| Data Completeness Score | System's data completeness assessment |
| Match Score | System's confidence score |
| Criteria Details | Per-criterion system evaluation |

### 6.2 Data Management

- All study data stored in the validation study management system.
- Case data is append-only (no modifications after review submission).
- Study data is separate from production screening data.
- Audit trail maintained for all study operations.

---

## 7. Statistical Analysis Plan

### 7.1 Primary Analyses

| Metric | Formula | Purpose |
|---|---|---|
| Sensitivity | TP / (TP + FN) | Detect truly eligible patients |
| Specificity | TN / (TN + FP) | Correctly exclude ineligible patients |
| PPV | TP / (TP + FP) | Reliability of positive screening |
| NPV | TN / (TN + FN) | Reliability of negative screening |
| Accuracy | (TP + TN) / Total | Overall correctness |
| F1 Score | 2*(PPV*Sens) / (PPV+Sens) | Harmonic mean of PPV and sensitivity |
| Cohen's Kappa | (p_o - p_e) / (1 - p_e) | Agreement beyond chance |

### 7.2 Confidence Intervals

- 95% Wilson score confidence intervals for sensitivity, specificity,
  PPV, and NPV.
- Wilson intervals are preferred over normal approximation for proportions
  near 0 or 1 and for small samples.

### 7.3 Subgroup Analyses

- By therapeutic area (dermatology, oncology, ophthalmology)
- By data completeness level (high >= 0.9, medium 0.7-0.9, low < 0.7)
- By criterion type (demographic, condition, measurement, medication)
- By system confidence score quartile

### 7.4 False Negative Analysis

- Detailed review of all false negative cases (system says INELIGIBLE,
  gold standard says ELIGIBLE).
- Root cause categorization: data gap, criterion interpretation, NLP error,
  mapping error.
- Comparison with CMO-6 false negative monitoring flags.

---

## 8. Success Criteria

### 8.1 Primary Success Criteria

| Metric | Target | Rationale |
|---|---|---|
| Sensitivity | >= 95% | Minimize missed eligible patients |
| Specificity | >= 85% | Acceptable false positive rate for screening |

### 8.2 Secondary Success Criteria

| Metric | Target | Rationale |
|---|---|---|
| PPV | >= 70% | Acceptable positive screening reliability |
| NPV | >= 95% | High confidence in negative screening |
| Cohen's Kappa | >= 0.75 | Substantial agreement with clinicians |
| F1 Score | >= 0.85 | Balanced precision and recall |

### 8.3 Interpretation

- **Sensitivity >= 95%:** The system catches at least 95% of truly eligible
  patients. This is the most critical metric for a screening system because
  missing eligible patients (false negatives) means patients lose access
  to potentially beneficial treatments.
- **Specificity >= 85%:** Up to 15% of ineligible patients may be flagged
  as potentially eligible. This is acceptable because all system results
  require clinician review before enrollment.

---

## 9. Limitations and Potential Biases

### 9.1 Known Limitations

- **Retrospective design:** Cannot capture real-time clinical context or
  patient preferences.
- **Data availability bias:** System performance depends on available
  structured data; patients with sparse records may be systematically
  misclassified.
- **Gold standard subjectivity:** Even board-certified physicians may
  disagree on borderline cases.
- **Temporal bias:** Eligibility criteria interpretation may change over
  time; retrospective review may apply updated understanding.

### 9.2 Mitigation Strategies

- Use multiple reviewers with adjudication for disagreements.
- Stratify analysis by data completeness to quantify data availability
  impact.
- Measure inter-reviewer reliability (Kappa) to validate the gold standard.
- Document all protocol deviations and include in final report.

### 9.3 Generalizability

- Results are specific to the trial types and patient populations included
  in the study.
- Performance may differ for trials with complex multi-step criteria,
  novel biomarkers, or rare conditions not well represented in training data.
- External validation with independent datasets is recommended before
  expanding to new therapeutic areas.

---

## 10. Reporting

### 10.1 Study Report Contents

- Executive summary with key metrics and target achievement
- Detailed confusion matrix and metrics with confidence intervals
- Subgroup analyses
- False negative case review findings
- Recommendations for system improvement
- Protocol deviations and their impact

### 10.2 Report Timeline

- Interim analysis: After 50% of target sample size is achieved
- Final report: Within 30 days of study completion
- Follow-up report: After system improvements based on findings

---

## Appendix A: Definitions

| Term | Definition |
|---|---|
| True Positive (TP) | System says ELIGIBLE, gold standard agrees |
| True Negative (TN) | System says INELIGIBLE, gold standard agrees |
| False Positive (FP) | System says ELIGIBLE, gold standard says INELIGIBLE |
| False Negative (FN) | System says INELIGIBLE, gold standard says ELIGIBLE |
| Sensitivity | TP / (TP + FN) -- also called recall or true positive rate |
| Specificity | TN / (TN + FP) -- also called true negative rate |
| PPV | TP / (TP + FP) -- also called precision |
| NPV | TN / (TN + FN) |
| Cohen's Kappa | Measure of agreement corrected for chance |

## Appendix B: Regulatory References

- FDA Guidance: Clinical Decision Support Software (2022)
- 21 CFR Part 11: Electronic Records; Electronic Signatures
- ICH E6(R2): Good Clinical Practice
- ISO 14155: Clinical Investigation of Medical Devices
