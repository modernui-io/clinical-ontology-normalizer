# P4-015-I: Outcomes Feedback Loop Blueprint

**Task:** P4-015-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Governance plan complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-015-outcome-feedback.md`

## Summary

This document codifies the implementation blueprint for building clinical outcome feedback loops. Activation is gated on pilot day 90 for direct metrics and EHR outcome feed establishment for indirect metrics, as defined in P4-015-D. Direct metric collection (acceptance rate, override rate, time-to-action) uses existing P2-009 feedback pipeline.

## Current State Assessment

| Component | File | Lines | Maturity |
|-----------|------|-------|----------|
| Clinical Outcome Assessment Service | `backend/app/services/clinical_outcome_assessment_service.py` | 621 | Pilot-level (COA instruments) |
| Quality Measures | `backend/app/services/quality_measures.py` | 2,223 | Production |
| Quality Metrics | `backend/app/services/quality_metrics.py` | 573 | Production |
| Data Quality Service | `backend/app/services/data_quality_service.py` | 1,400 | Production |
| Clinician Feedback (P2-009) | Feedback capture + replay pipeline | — | Closed |
| Drift Detection (P2-010) | Terminology mapping drift alerts | — | Closed |

## Capture Points

### Recommendation Events
| Event Type | Capture Point | Data Captured |
|-----------|--------------|---------------|
| System recommendation issued | Clinical query response | recommendation_id, content, confidence, risk_tier, timestamp, patient_id, encounter_id |
| Provenance attached | Clinical query response | source_document_ids, kg_node_ids, evidence_count |
| Confidence policy gate result | `confidence_policy_service.py` | action_gate_result (allowed/blocked/warned), threshold applied, risk tier |

### Clinician Actions
| Action Type | Capture Point | Data Captured |
|------------|--------------|---------------|
| Recommendation accepted | P2-009 feedback pipeline | recommendation_id, clinician_id, action: accepted, timestamp |
| Recommendation modified | P2-009 feedback pipeline | recommendation_id, clinician_id, action: modified, modification_text, timestamp |
| Recommendation rejected | P2-009 feedback pipeline | recommendation_id, clinician_id, action: rejected, reason_code, timestamp |
| No action taken | Timeout detection (24h) | recommendation_id, action: no_response, timeout_duration |

### Outcome Linkage
| Linkage Type | Source | Join Key | Data Captured |
|-------------|--------|----------|---------------|
| Direct: Clinician action | P2-009 feedback | recommendation_id | acceptance/modification/rejection + timing |
| Semi-direct: Documentation completeness | Clinical facts vs chart audit | patient_id + encounter_id | fact coverage ratio |
| Indirect: Safety events | EHR ADT feed (future) | patient_id + 30-day window | adverse events, readmissions |
| Indirect: Lab outcomes | EHR lab feed (future) | patient_id + encounter_id | lab value trajectories |

## Data Pipeline Design

### Event -> Store -> Link -> Attribute -> Report

```
Stage 1: EVENT CAPTURE
  |-- Recommendation events (from clinical query API)
  |-- Clinician actions (from P2-009 feedback pipeline)
  +-- System metadata (confidence, provenance, risk tier)
         |
Stage 2: EVENT STORE
  |-- Recommendation Event Store (append-only)
  |     Fields: recommendation_id, patient_id, encounter_id, content,
  |             confidence, risk_tier, source_document_ids, timestamp
  |-- Action Event Store (append-only)
  |     Fields: recommendation_id, clinician_id, action_type,
  |             reason_code, modification_text, timestamp
  +-- Outcome Event Store (append-only, when EHR feed available)
        Fields: patient_id, outcome_type, outcome_value,
                outcome_date, source_system
         |
Stage 3: LINKAGE
  |-- Recommendation-Action Link (immediate, via recommendation_id)
  |-- Recommendation-Outcome Link (deferred, via patient_id + time window)
  +-- Cohort Assignment (system-informed vs control)
         |
Stage 4: ATTRIBUTION
  |-- Direct attribution (acceptance rate, override rate, time-to-action)
  |-- Semi-direct attribution (documentation completeness via chart audit)
  +-- Indirect attribution (safety events, readmissions — requires cohort matching)
         |
Stage 5: REPORTING
  |-- Quarterly outcome report
  |-- Clinical advisor review
  +-- Governance sign-off
```

## Attribution Model

### Direct Attribution
| Metric | Definition | Measurement | Confidence Level |
|--------|-----------|-------------|-----------------|
| Acceptance rate | % of recommendations accepted by clinician | accepted / (accepted + modified + rejected) | High |
| Override rate | % of recommendations modified or rejected | (modified + rejected) / total | High |
| Time-to-action | Median time from recommendation to clinician action | median(action_timestamp - recommendation_timestamp) | High |
| Response rate | % of recommendations that receive any clinician action | (accepted + modified + rejected) / total | High |

### Indirect Attribution
| Metric | Definition | Measurement | Confidence Level |
|--------|-----------|-------------|-----------------|
| 30-day safety events | Adverse events within 30 days of system-informed decision | Count per 1000 system-informed encounters | Low (confounders) |
| 30-day readmission rate | All-cause readmission within 30 days | Readmissions per 100 discharges | Low (confounders) |
| Documentation completeness | Clinical facts captured vs chart review baseline | Fact count ratio | Medium |

### Inconclusive Attribution
- Applied when sample size <100 encounters
- Applied when confounding variables cannot be adjusted (acuity, comorbidity)
- Reported as "inconclusive" with confidence intervals and sample size
- Never reported as "no effect" — only "insufficient evidence"

## Outcome Metric Definitions with Measurement Windows

| Metric ID | Metric Name | Window | Data Source | Attribution | Available |
|-----------|------------|--------|------------|-------------|-----------|
| OM-001 | Recommendation acceptance rate | Per encounter | P2-009 feedback | Direct | Pilot launch |
| OM-002 | Recommendation override rate | Per encounter | P2-009 feedback | Direct | Pilot launch |
| OM-003 | Time-to-clinical-action | Per encounter | P2-009 feedback | Direct | Pilot launch |
| OM-004 | Clinician response rate | Per encounter | P2-009 feedback + timeout | Direct | Pilot launch |
| OM-005 | Documentation completeness | Per patient | Chart audit | Semi-direct | Pilot day 30 |
| OM-006 | 30-day safety events | 30-day lookback | EHR ADT feed | Indirect | Post-EHR feed |
| OM-007 | 30-day readmission rate | 30-day lookback | EHR ADT feed | Indirect | Post-EHR feed |
| OM-008 | Lab value trajectory | Per encounter + 7/14/30 day | EHR lab feed | Indirect | Post-EHR feed |

## First Quarterly Report Template

### Report Structure

```
QUARTERLY OUTCOME REPORT - Q[N] [Year]
Report period: [start_date] to [end_date]
Generated: [report_date]
Reviewed by: [Clinical AI Lead, CIO, Clinical Governance]

1. EXECUTIVE SUMMARY
   - Total recommendations issued: [N]
   - Total clinician actions captured: [N]
   - Overall acceptance rate: [X]% (95% CI: [L%, U%])
   - Key findings: [2-3 bullet points]

2. DIRECT METRICS
   2.1 Acceptance Rate
       - Overall: [X]% (n=[N], 95% CI: [L%, U%])
       - By risk tier: Critical [X]%, High [X]%, Medium [X]%, Low [X]%
       - By specialty: [breakdown]
       - Trend: [vs previous quarter if available]
   2.2 Override Rate
       - Overall: [X]% (n=[N], 95% CI: [L%, U%])
       - Top override reasons: [ranked list]
   2.3 Time-to-Action
       - Median: [X] minutes (IQR: [Q1, Q3])
       - By urgency: [breakdown]
   2.4 Response Rate
       - Overall: [X]% (n=[N])
       - No-response rate: [X]% (timeout at 24h)

3. SEMI-DIRECT METRICS
   3.1 Documentation Completeness
       - System-informed encounters: [X]% fact coverage
       - Baseline (chart review): [X]% fact coverage
       - Delta: [+/-X]% (95% CI: [L%, U%])

4. INDIRECT METRICS (if EHR feed available)
   4.1 Safety Events - [available / not yet available]
   4.2 Readmission Rate - [available / not yet available]

5. LIMITATIONS AND CAVEATS
   - Sample size: [adequate / insufficient for metric X]
   - Confounders: [list of uncontrolled variables]
   - Attribution confidence: [direct: high, indirect: low/N/A]

6. RECOMMENDATIONS
   - [action items for next quarter]

7. SIGN-OFF
   - Clinical AI Lead: [name, date, verdict]
   - CIO: [name, date, verdict]
   - Clinical Governance: [name, date, verdict]
```

## Clinical Advisor Review Cadence

| Review Type | Frequency | Participants | Deliverable |
|------------|-----------|-------------|-------------|
| Attribution methodology review | Before first measurement | Clinical advisor(s) + Clinical AI Lead | Signed methodology approval |
| Quarterly outcome review | Every 90 days | Clinical advisor(s) + Clinical AI Lead + CIO | Quarterly outcome report sign-off |
| Bias/confounding audit | Every 180 days | Clinical advisor(s) + external reviewer | Bias audit report |
| Metric definition update | As needed | Clinical advisor(s) + Clinical AI Lead | Updated metric definitions |

## Activation Gate Checklist

- [ ] Pilot day 90 reached (for direct metrics: OM-001 through OM-004)
- [ ] P2-009 feedback pipeline producing data at volume (>50 actions/week)
- [ ] Quarterly report template approved by Clinical Governance
- [ ] Clinical advisor assigned and methodology approved
- [ ] EHR outcome data feed established (for indirect metrics: OM-006 through OM-008)
- [ ] Cohort matching methodology approved (for indirect attribution)
- [ ] First quarterly report generated and reviewed

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P2-009 (Clinician feedback capture) | Foundation for action event capture | Closed |
| P2-010 (Drift detection) | Detects shifts in recommendation patterns | Closed |
| P4-009 (Guideline corpus) | Informs which outcomes are measurable per specialty | Deferred (ADR) |
| P4-010 (Causal inference) | Advanced attribution methods require stable trust metrics | Deferred (ADR) |
| P4-011 (Adaptive confidence) | Threshold changes affect recommendation rates | Deferred (ADR) |
