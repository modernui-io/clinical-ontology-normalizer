# P4-010-I: Causal Reasoning Implementation Constraints

**Task:** P4-010-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Implementation constraints complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-010-causal-inference.md`

## Summary

This document defines the implementation constraints for advanced causal inference modules. Activation is gated on 5 trust metric thresholds being met simultaneously. Until then, all clinical outputs are labeled as correlation/ranking (not causal) per P1-015. The `causal_reasoning_service.py` and `hybrid_clinical_analyzer.py` services are maintained but causal inference is not activated in clinical paths.

## 5 Trust Metric Thresholds

All five thresholds must be met **simultaneously** over the specified measurement windows before causal inference activation.

### Threshold 1: Extraction Precision >85%

| Parameter | Value |
|-----------|-------|
| **Metric** | Precision on P1-010 UMLS/OMOP acceptance corpus |
| **Threshold** | >85% (30-day rolling average) |
| **Measurement** | Automated daily evaluation against acceptance corpus |
| **Current state** | Not yet measured at production scale (corpus exists per P1-010) |
| **Service reference** | `backend/app/services/narrative_extractor.py` + P1-010 corpus |
| **Computation** | True positives / (True positives + False positives) on entity extraction |

**Rationale:** Causal chains built on imprecise extractions propagate errors. >85% ensures foundation is reliable.

### Threshold 2: Confidence Calibration Error <10%

| Parameter | Value |
|-----------|-------|
| **Metric** | Brier score comparing stated confidence to observed correctness |
| **Threshold** | <10% calibration error (30-day rolling average) |
| **Measurement** | Computed from P3-005 calibration infrastructure |
| **Current state** | P3-005 calibration plots exist; not yet measured at scale |
| **Service reference** | `backend/app/services/confidence_policy_service.py`, P3-005 |
| **Computation** | Mean squared error between predicted probability and actual outcome |

**Rationale:** Causal claims with miscalibrated confidence create false certainty. <10% ensures confidence is meaningful.

### Threshold 3: False Positive Rate <5% at High Confidence

| Parameter | Value |
|-----------|-------|
| **Metric** | False positive rate for outputs with confidence >0.9 |
| **Threshold** | <5% (30-day rolling average) |
| **Measurement** | Clinician-validated sample of high-confidence outputs |
| **Current state** | Not yet measured at scale |
| **Service reference** | `backend/app/services/hybrid_clinical_analyzer.py` |
| **Computation** | False positives / (False positives + True negatives) at confidence >0.9 |

**Rationale:** High-confidence causal claims that are wrong are more dangerous than low-confidence ones. <5% FPR at >0.9 confidence is the safety floor.

### Threshold 4: KG Completeness >70%

| Parameter | Value |
|-----------|-------|
| **Metric** | Per-patient knowledge graph completeness score |
| **Threshold** | >70% average across active patients (30-day rolling) |
| **Measurement** | P2-006 completeness scoring model |
| **Current state** | P2-006 scoring model exists; not yet measured at scale |
| **Service reference** | KG completeness service (P2-006) |
| **Computation** | (Present expected nodes + edges) / (Total expected nodes + edges) per patient |

**Rationale:** Causal reasoning on incomplete graphs produces spurious conclusions. >70% ensures sufficient evidence basis.

### Threshold 5: Zero SEV-1 AI Incidents for 90 Days

| Parameter | Value |
|-----------|-------|
| **Metric** | SEV-1 AI-related incident count |
| **Threshold** | 0 incidents in 90 consecutive days |
| **Measurement** | Incident tracking system (P1-032 taxonomy) |
| **Current state** | Pilot not yet launched |
| **Service reference** | `docs/operations/incident_taxonomy.md` |
| **Computation** | Count of SEV-1 incidents classified as AI-related in rolling 90-day window |

**Rationale:** Causal inference is the highest-risk AI feature. Zero SEV-1 for 90 days demonstrates system stability.

### Threshold Status Dashboard
```
CAUSAL INFERENCE ACTIVATION STATUS

Threshold 1 (Extraction Precision >85%):    [NOT MEASURED]  ____%
Threshold 2 (Calibration Error <10%):        [NOT MEASURED]  ____%
Threshold 3 (FPR <5% at high confidence):    [NOT MEASURED]  ____%
Threshold 4 (KG Completeness >70%):          [NOT MEASURED]  ____%
Threshold 5 (Zero SEV-1 for 90 days):        [NOT MEASURED]  ____days

ALL THRESHOLDS MET: [ ] NO  [ ] YES -> Activation eligible
```

## 3-Phase Activation Plan

### Phase 1: Assumption Declaration

**Objective:** Every causal claim explicitly declares its assumptions

| Requirement | Implementation | Enforcement |
|-------------|---------------|-------------|
| Confounder declaration | Each `CausalLink` must populate `confounders_considered` field | Schema validation at write time |
| Temporal ordering evidence | Each `CausalLink` must have `TemporalOrder` enum value with supporting timestamps | Schema validation at write time |
| Intervention assignment | Declare whether relationship is from observational data, RCT, or expert knowledge | Required field on `CausalLink` |
| User-facing labeling | All outputs include explicit label distinguishing causal hypothesis from correlation | UI rendering rule |

**Label Taxonomy:**
| Label | Meaning | Display Style |
|-------|---------|---------------|
| "Correlation observed" | Statistical association, no causal claim | Standard text |
| "Temporal association" | Time-ordered relationship, no causal mechanism claimed | Standard text + time icon |
| "Causal hypothesis (not validated)" | Proposed causal mechanism with declared assumptions | Yellow warning badge |
| "Causal relationship (validated)" | Clinician-reviewed and confirmed causal mechanism | Green verified badge |

**Duration:** Phase 1 runs for minimum 30 days before Phase 2 activation.

### Phase 2: Uncertainty Propagation

**Objective:** No single-point causal estimates in clinical outputs

| Requirement | Implementation |
|-------------|---------------|
| Confidence intervals on causal chains | Propagate uncertainty through `CausalChain` dataclass using Monte Carlo or analytical bounds |
| No point predictions | All causal outputs show range (e.g., "65-80% likely causal" not "72% causal") |
| Sensitivity analysis | For each causal claim, compute how conclusion changes if each assumption is violated |
| Display confidence bands | UI shows uncertainty range, not single number |

**Propagation Method:**
```
For CausalChain with links [L1, L2, ..., Ln]:
  - Each link has confidence interval [lower, upper]
  - Chain confidence: product of link confidences (pessimistic bound)
  - Display: "Based on {n} linked observations, {lower}% to {upper}% confidence in causal pathway"
  - If chain confidence lower bound < 50%: auto-label as "weak causal hypothesis"
```

**Duration:** Phase 2 runs for minimum 60 days before Phase 3 activation.

### Phase 3: Blinded Clinical Evaluation

**Objective:** Demonstrate causal outputs do not produce worse safety outcomes

See Validation artifact (`p4-010-evidence-2026-02-17.md`) for full blinded evaluation protocol.

**Duration:** Evaluation takes 4-6 weeks. Results must show non-inferiority before production activation.

## Explicit Labeling Requirements

### Labeling Rules (Active Now — P1-015 Compliance)
1. **All differential diagnosis scores are labeled as "ranking" not "probability"** (P1-015 closed)
2. **No output may use the word "causes" without declared assumptions** (enforced at rendering)
3. **"Associated with" is the default relationship language** (until Phase 1 declares otherwise)
4. **Hybrid analyzer outputs include "AI-assisted correlation analysis" disclaimer** (active)

### Labeling Rules (Post-Activation — Phase 1+)
5. **Causal hypotheses carry explicit "not validated" badge** until clinician review
6. **Validated causal relationships carry "clinician-verified" badge** with verifier identity
7. **Causal chain confidence shows range, not point estimate** (Phase 2)
8. **Sensitivity analysis summary available on hover/click** (Phase 2)

### Prohibited Labels (Never Allowed)
- "Proven cause" (clinical evidence standard not achievable by system alone)
- "Definite causation" (same reason)
- Any numeric causal probability without uncertainty range (Phase 2 requirement)
- Causal claims without assumption declarations (Phase 1 requirement)

## Current Service Assessment

### `causal_reasoning_service.py` (569 lines)
| Component | Present? | Production Ready? | Notes |
|-----------|----------|------------------|-------|
| `CausalRelationType` enum | Yes | Yes | Direct, indirect, mediating, confounding |
| `TemporalOrder` enum | Yes | Yes | Before, after, concurrent, unknown |
| `CausalLink` dataclass | Yes | Scaffold | Needs confounders_considered field |
| `CausalChain` dataclass | Yes | Scaffold | Needs confidence interval propagation |
| Assumption declaration | No | N/A | To be built in Phase 1 |
| Uncertainty propagation | No | N/A | To be built in Phase 2 |

### `hybrid_clinical_analyzer.py` (1,049 lines)
| Component | Present? | Production Ready? | Notes |
|-----------|----------|------------------|-------|
| Hybrid deterministic+LLM architecture | Yes | Pilot-level | 100% token coverage, ~1ms deterministic |
| Grounded reasoning | Yes | Pilot-level | Reduced hallucination risk |
| Ontology mapping | Yes | Production | Fully deterministic |
| LLM clinical reasoning | Yes | Pilot-level | With grounding constraints |
| Causal claim labeling | No | N/A | Currently all outputs labeled as correlation |

## Activation Criteria Checklist

- [ ] Threshold 1: Extraction precision >85% (30-day rolling)
- [ ] Threshold 2: Calibration error <10% (30-day rolling)
- [ ] Threshold 3: FPR <5% at confidence >0.9 (30-day rolling)
- [ ] Threshold 4: KG completeness >70% (30-day rolling)
- [ ] Threshold 5: Zero SEV-1 for 90 consecutive days
- [ ] All 5 thresholds met simultaneously for >7 consecutive days
- [ ] Phase 1 (Assumption Declaration) implemented and tested
- [ ] Phase 2 (Uncertainty Propagation) implemented and tested
- [ ] Phase 3 (Blinded Evaluation) completed with non-inferiority result
- [ ] Clinical AI Lead and CTO joint approval for production activation

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P1-010 (Acceptance corpus) | Required for Threshold 1 measurement | Closed |
| P1-015 (Ranking labels) | Current labeling baseline | Closed |
| P2-006 (KG completeness) | Required for Threshold 4 measurement | Closed |
| P3-005 (Calibration plots) | Required for Threshold 2 measurement | Closed |
| P4-009 (Guideline corpus) | Richer guidelines improve causal reasoning quality | Monitoring |
| P4-013 (SaMD) | Causal features may trigger higher regulatory classification | Monitoring |
