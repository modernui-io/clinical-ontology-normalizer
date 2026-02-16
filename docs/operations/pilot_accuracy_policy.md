# Pilot Accuracy Policy — Workflow-Specific Thresholds

**Document ID**: GOV-P1-016
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: VP Product + CIO
**Classification**: Internal — Governance

## Purpose

Define explicit accuracy class policies for the 77% baseline accuracy tier observed in NLP extraction benchmarks. Each clinical workflow has distinct risk profiles requiring tailored action policies.

## Accuracy Baseline

Current system-wide NLP extraction accuracy: **77%** (F1 score across entity types).

This represents aggregate performance. Per-entity performance varies:

| Entity Type | Precision | Recall | F1 |
|---|---|---|---|
| Conditions (ICD-mapped) | 82% | 79% | 80% |
| Medications (RxNorm) | 85% | 81% | 83% |
| Lab Values (LOINC) | 79% | 74% | 76% |
| Procedures (CPT/SNOMED) | 74% | 68% | 71% |
| Allergies | 71% | 65% | 68% |
| Vitals | 88% | 85% | 86% |

## Workflow Risk Tiers

### Tier 1 — Clinical Decision Support (High Risk)

**Affected workflows**: Drug interaction checks, clinical agent Q&A, guideline alerts

**Policy**:
- Minimum confidence threshold: **0.85**
- Below threshold: Mandatory "unverified" label + clinician review flag
- Action block: No automated clinical action on unverified items
- Decline behavior: Return "insufficient evidence" with escalation path
- Required: Source document ID for every assertion

### Tier 2 — Chart Summarization (Medium Risk)

**Affected workflows**: Patient summary, problem list generation, KG visualization

**Policy**:
- Minimum confidence threshold: **0.70**
- Below threshold: Display with "low confidence" badge
- Missing coverage: Show explicit "not assessed" for uncovered domains
- Required: Coverage percentage in summary header

### Tier 3 — Billing/Coding Support (Medium Risk)

**Affected workflows**: Code suggestion, HCC capture, charge reconciliation

**Policy**:
- Minimum confidence threshold: **0.80**
- Below threshold: Suggest but do not auto-submit
- All suggestions marked as "requires coder review"
- Required: Supporting evidence span from source document

### Tier 4 — Research/Analytics (Lower Risk)

**Affected workflows**: Cohort identification, trend analysis, quality metrics

**Policy**:
- Minimum confidence threshold: **0.60**
- Aggregate metrics include error bounds
- Individual records flagged below threshold
- Required: Methodology note in export metadata

## Calibration Requirements

1. **Pre-pilot**: Accuracy measured on gold-standard corpus (min 200 annotated notes)
2. **Weekly during pilot**: Sample 20 extractions for manual review
3. **Monthly**: Full benchmark re-run, update this matrix if thresholds shift >5%
4. **Trigger**: If any entity type drops below 60% F1, disable that entity in affected Tier 1 workflows

## Governance

- This policy requires CIO + VP Product joint approval for changes
- Threshold changes require Clinical AI Lead sign-off
- Exception requests documented in risk-acceptance register (see P1-033)
- Policy version tracked alongside model/pipeline version
