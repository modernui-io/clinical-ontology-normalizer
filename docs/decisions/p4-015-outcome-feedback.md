# P4-015-D: Clinical Outcome Feedback Loops Decision

**Decision ID:** P4-015-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Clinical AI + CIO
**Risk Owner:** CIO
**Evidence Owner:** Clinical AI

## Context

Outcome and quality measurement infrastructure is substantial:

- `backend/app/services/clinical_outcome_assessment_service.py` (621 lines) — COA management: instruments (PROs, ClinROs, ObsROs, PerfOs), assessment workflows, compliance reporting
- `backend/app/services/data_quality_service.py` (1,400 lines) — comprehensive data quality metrics
- `backend/app/services/quality_measures.py` (2,223 lines) — quality measurement calculations
- `backend/app/services/quality_metrics.py` (573 lines) — quality metric definitions
- Clinician feedback capture: P2-009 (closed) — feedback pipeline exists
- Drift detection: P2-010 (closed) — terminology mapping drift alerts active

**Missing:** No linkage between system recommendations and real-world patient outcomes. System tracks what it recommended but not whether the recommendation led to better/worse patient outcomes.

## Decision

**Define outcome measurement framework. Defer data collection to post-pilot when outcome data becomes available.**

### Outcome Metrics Definition

| Metric | Measurement | Window | Attribution Method |
|--------|------------|--------|-------------------|
| Recommendation acceptance rate | % of system suggestions accepted by clinician | Per encounter | Direct (system log) |
| Time to clinical action | Time from system suggestion to clinician action | Per encounter | Direct (timestamp delta) |
| Clinician override rate | % of system suggestions overridden/corrected | Per encounter | Direct (feedback loop) |
| Patient safety events | Adverse events within 30 days of system-informed decision | 30-day lookback | Indirect (requires outcome data linkage) |
| Readmission rate | 30-day all-cause readmission for patients with system-informed care | 30-day lookback | Indirect (requires outcome data) |
| Documentation completeness | % of clinical facts captured vs. chart review baseline | Per patient | Semi-direct (chart audit) |

### Data Collection Pipeline (When Activated)

```
System Recommendation
  ├── Captured: recommendation_id, content, confidence, timestamp
  ├── Clinician Action: accepted/modified/rejected + reason code
  ├── Patient Outcome: linked via encounter_id + patient_id
  └── Outcome Report: quarterly aggregate with attribution analysis
```

### Attribution Methodology

1. **Direct attribution:** Metrics where system action directly maps to outcome (acceptance rate, override rate, time-to-action)
2. **Indirect attribution:** Metrics requiring external outcome data (readmission, safety events) — requires:
   - EHR outcome data feed (ADT events, lab results, diagnosis codes at follow-up)
   - Time-windowed cohort matching (system-informed vs. control)
   - Confounding variable adjustment (patient acuity, comorbidity burden)
3. **Inconclusive attribution:** If sample size <100 or confounders not adjustable, report as "inconclusive" (not "no effect")

### First Quarterly Report Target

- **Content:** Acceptance rate, override rate, time-to-action (direct metrics only)
- **Timeline:** 90 days post-pilot launch
- **Audience:** Clinical AI Lead, CIO, Clinical Governance
- **Format:** Structured report with confidence intervals and sample sizes
- **Quality gate:** Signal must be "positive, negative, or inconclusive" — never "not measured"

### Clinical Advisor Requirements

- At least one clinical advisor per active specialty reviews attribution methodology
- Advisor signs off on outcome metric definitions before measurement begins
- Quarterly review of attribution analysis for bias or confounding

## Consequences

- No outcome measurement during initial pilot (insufficient data volume)
- Direct metrics (acceptance, override, time-to-action) begin collection at pilot launch using existing P2-009 feedback pipeline
- Indirect metrics deferred until EHR outcome data feed is established
- First quarterly report at pilot day 90
- Cross-dependency: P4-009 (guideline corpus) informs which outcomes are measurable per specialty

## Evidence Paths

- Outcome assessment: `backend/app/services/clinical_outcome_assessment_service.py`
- Data quality: `backend/app/services/data_quality_service.py`
- Quality measures: `backend/app/services/quality_measures.py`
- Feedback capture: P2-009 (closed)
- Drift detection: P2-010 (closed)
- This decision: `docs/decisions/p4-015-outcome-feedback.md`
