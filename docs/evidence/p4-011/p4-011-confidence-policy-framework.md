# P4-011-I: Adaptive Confidence Policy Framework

**Task:** P4-011-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Governance plan complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-011-adaptive-confidence.md`

## Summary

This document codifies the implementation plan for role-adaptive confidence threshold personalization. Activation is gated on ethics review completion + 100-case simulation per role profile, as defined in P4-011-D. No adaptive thresholds are active during pilot; the uniform policy (P0-021) remains enforced.

## Current State Assessment

| Component | File | Lines | Maturity |
|-----------|------|-------|----------|
| Confidence Policy Service | `backend/app/services/confidence_policy_service.py` | 103 | Production (P0-021 enforced) |
| Workflow Confidence Policy | `backend/app/services/workflow_confidence_policy.py` | 254 | Pilot-level (workflow-specific) |
| Pilot Accuracy Policy | `docs/operations/pilot_accuracy_policy.md` | — | Approved (P1-016) |

## Role Profile Schema

### Profile Definition

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role_profile_id` | UUID | Yes | Unique identifier for this profile |
| `role_type` | enum | Yes | Attending, Resident, NP, PA, Pharmacist, Nurse |
| `risk_tier_overrides` | JSON | No | Per-tier threshold overrides (must be >= safety floor) |
| `safety_floor_enforced` | boolean | Yes | Always `true` — immutable field, cannot be set to `false` |
| `workflow_policies` | array[UUID] | No | Associated workflow policy IDs from `workflow_confidence_policy.py` |
| `created_at` | datetime | Yes | Profile creation timestamp (UTC) |
| `created_by` | string | Yes | Identity of profile creator |
| `ethics_review_id` | UUID | Yes | Reference to ethics review that approved this profile |
| `simulation_evidence_id` | UUID | Yes | Reference to simulation run that validated this profile |

### Safety Floor Enforcement

The safety floor from P4-011-D is immutable and embedded in the profile validation layer:

| Risk Tier | Minimum Threshold (Floor) | Override Direction |
|-----------|--------------------------|-------------------|
| Critical (medication, allergy, contraindication) | 0.95 | May only raise, never lower |
| High (diagnosis, treatment recommendation) | 0.85 | May only raise, never lower |
| Medium (lab interpretation, vitals trending) | 0.70 | May only raise, never lower |
| Low (administrative, scheduling, summary) | 0.50 | May only raise, never lower |

**Enforcement rule:** Profile validation rejects any override that sets a threshold below the floor. This check is performed at profile creation time and at every policy evaluation. No runtime bypass mechanism exists.

## Workflow Confidence Policy Extension Points

Reference: `backend/app/services/workflow_confidence_policy.py` (254 lines)

### Current Capabilities
- Workflow-type-specific policy definitions
- Action-gate evaluation per workflow context
- Configurable strict/advisory mode per workflow

### Required Extensions for Adaptive Profiles
1. **Profile binding:** Associate a role profile with a workflow policy via `workflow_policies` array
2. **Merged evaluation:** When evaluating confidence gate, merge role profile overrides with workflow policy — take the HIGHER (more conservative) threshold
3. **Emergency override:** In emergency workflow context, allow advisory mode (warn instead of block) but NEVER below safety floor
4. **Audit trail:** Log which profile and workflow policy contributed to each gate evaluation

## Experiment Safety Constraints

### Pre-Activation Requirements
1. Ethics review body formed (Clinical AI Lead + external ethics advisor + Compliance representative)
2. 100-case simulation completed per proposed role profile
3. Non-inferiority demonstrated against uniform baseline (no profile produces worse safety outcomes)
4. Clinical AI Lead and ethics body sign-off on file

### During Active Experimentation
1. Real-time monitoring of gate outcomes per role profile
2. Automatic rollback to uniform policy if any profile exceeds adverse event threshold
3. Weekly review of per-profile metrics by ethics body during first 90 days
4. Monthly review thereafter

### Prohibited Actions
1. No profile may set `safety_floor_enforced = false`
2. No profile may lower any tier below its floor (validation enforced, not just policy)
3. No emergency override may bypass the safety floor (only changes mode from strict to advisory)
4. No profile may be activated without simulation evidence

## Disparity Risk Assessment Methodology

### Assessment Dimensions
1. **Role-outcome disparity:** Compare patient safety event rates across patients served by different role profiles
2. **Population-outcome disparity:** Check whether role-adaptive thresholds correlate with patient demographic outcomes
3. **Threshold-action disparity:** Measure whether lower thresholds for certain roles lead to more false positives or missed signals

### Assessment Process
1. Define comparison cohorts (role A vs role B patients)
2. Run simulation on historical data (minimum 100 decisions per cohort)
3. Compute safety outcome delta with 95% confidence intervals
4. Flag any delta where lower CI bound < -5% (worse than baseline)
5. Ethics body reviews flagged disparities before profile activation

### Reporting
- Disparity assessment report produced per proposed role profile
- Report includes sample size, outcome rates, confidence intervals, and ethics body verdict
- Report archived as evidence artifact linked to `simulation_evidence_id`

## Activation Gate Checklist

- [ ] Ethics review body formed (Clinical AI Lead + external advisor + Compliance)
- [ ] 100-case simulation completed per role profile
- [ ] Non-inferiority demonstrated for all profiles vs. uniform baseline
- [ ] Disparity risk assessment completed with no unresolved flags
- [ ] Clinical AI Lead sign-off
- [ ] Ethics body sign-off
- [ ] Profile validation layer deployed and tested (rejects below-floor overrides)
- [ ] Audit trail for profile-aware gate evaluations implemented

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P0-021 (Confidence-to-action policy) | Foundation that adaptive profiles extend | Closed |
| P4-007 (Copilot experiments) | Inherits confidence floor from this framework | Deferred (ADR) |
| P1-016 (Pilot accuracy policy) | Baseline accuracy matrix that profiles must match or exceed | Closed |
| P4-010 (Causal inference) | Must not lower confidence floor for causal outputs | Deferred (ADR) |
