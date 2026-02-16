# P4-010-D: Advanced Causal Inference Modules Decision

**Decision ID:** P4-010-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Clinical AI
**Risk Owner:** Clinical AI
**Evidence Owner:** CTO

## Context

Causal reasoning capabilities exist:

- `backend/app/services/causal_reasoning_service.py` (569 lines) — `CausalRelationType` enum, `TemporalOrder` enum, `CausalLink` and `CausalChain` dataclasses for modeling causal relationships in clinical data
- `backend/app/services/hybrid_clinical_analyzer.py` (1,049 lines) — hybrid deterministic+LLM architecture combining ontology mapping (100% token coverage, ~1ms) with LLM clinical reasoning. Grounded reasoning with reduced hallucination risk

**Current state:** Correlation-based reasoning with explicit labeling (P1-015: differential diagnosis scores labeled as ranking). No formal causal inference framework (do-calculus, instrumental variables, counterfactual reasoning).

## Decision

**Defer formal causal inference until core trust metrics stabilize. Define trust metric stability thresholds now.**

### Trust Metric Stability Thresholds (Gate Criteria)

| Metric | Threshold | Measurement Window | Current State |
|--------|-----------|-------------------|---------------|
| Extraction precision | >85% on P1-010 corpus | 30-day rolling average | Not yet measured at scale |
| Confidence calibration error | <10% (Brier score) | 30-day rolling average | P3-005 calibration plots exist |
| False positive rate (high-confidence) | <5% for confidence >0.9 | 30-day rolling average | Not yet measured at scale |
| KG completeness score | >70% per patient average | 30-day rolling average | P2-006 scoring model exists |
| Zero SEV-1 AI incidents | 90 consecutive days | Rolling window | Pilot not yet launched |

All five thresholds must be met simultaneously before causal inference activation.

### Causal Inference Activation Plan (When Gated)

1. **Phase 1:** Explicit assumption declaration
   - Every causal claim must declare: confounders considered, temporal ordering evidence, intervention assignment mechanism
   - User-facing label: "Causal hypothesis (not validated)" vs "Correlation observed"

2. **Phase 2:** Uncertainty propagation
   - Propagate confidence intervals through causal chains
   - No single-point causal estimates in clinical outputs
   - Display confidence bands, not point predictions

3. **Phase 3:** Blinded clinical evaluation
   - Compare causal vs. correlation-only outputs on safety-critical cases
   - Minimum 50 cases evaluated by 3 independent clinicians
   - Pass criterion: causal outputs must not produce worse safety outcomes

### Why NOT Activate Now

1. Core trust metrics (extraction precision, calibration) not yet measured at production scale
2. Causal claims carry higher liability risk than correlation observations
3. No regulatory clarity on causal AI outputs in clinical decision support (cross-ref P4-013)
4. Hybrid analyzer already provides grounded reasoning without formal causal claims

## Consequences

- Causal reasoning service maintained but not activated in pilot clinical paths
- All clinical outputs labeled as correlation/ranking (not causal) per P1-015
- Hybrid analyzer continues as primary reasoning engine
- Activation requires all 5 trust metric thresholds met simultaneously
- Cross-dependency: P4-013 (SaMD) may classify causal inference features as higher-risk medical device

## Evidence Paths

- Causal reasoning: `backend/app/services/causal_reasoning_service.py`
- Hybrid analyzer: `backend/app/services/hybrid_clinical_analyzer.py`
- Confidence calibration: P3-005 (closed)
- KG completeness: P2-006 (closed)
- This decision: `docs/decisions/p4-010-causal-inference.md`
