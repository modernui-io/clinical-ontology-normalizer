# P4-011-D: Adaptive Personalization of Confidence Thresholds Decision

**Decision ID:** P4-011-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Product + Clinical AI
**Risk Owner:** Product
**Evidence Owner:** Clinical AI

## Context

Confidence policy service exists at `backend/app/services/confidence_policy_service.py` (103 lines):

- Risk-tier-based thresholds (e.g., 0.95 for critical actions)
- Strict mode (block) vs advisory mode (warn)
- Configurable via `CONFIDENCE_POLICY_STRICT` env var
- `check_action_gate()` returns `ActionGateResult` with allowed/blocked status

Additional policy infrastructure: `backend/app/services/workflow_confidence_policy.py` (workflow-specific policies).

**Current state:** Uniform thresholds per risk tier. No per-role or per-workflow customization. P0-021 enforces confidence-to-action policy for high-risk workflows.

## Decision

**Conduct ethics review before any role-adaptive thresholds. Define safety floor that cannot be lowered.**

### Ethics Review Requirements

1. **Core question:** Do role-adaptive thresholds create safety disparities between patient populations served by different clinician roles?
2. **Review body:** Clinical AI Lead + external ethics advisor + Compliance representative
3. **Analysis required:**
   - Demonstrate that no role profile produces worse patient safety outcomes than the uniform baseline
   - Show that threshold adaptation direction is always "more cautious" for higher-risk roles, not "more permissive"
   - Document rationale for any threshold difference >10% between roles

### Safety Floor Definition

| Risk Tier | Minimum Threshold (Floor) | Rationale |
|-----------|--------------------------|-----------|
| Critical (medication, allergy, contraindication) | 0.95 | No role may lower below this — patient safety absolute |
| High (diagnosis, treatment recommendation) | 0.85 | Clinician expertise does not reduce extraction error rate |
| Medium (lab interpretation, vitals trending) | 0.70 | Lower floor acceptable for informational outputs |
| Low (administrative, scheduling, summary) | 0.50 | Informational only, no clinical action gated |

**Rule:** The safety floor is immutable. Role-adaptive profiles may only raise thresholds above the floor, never lower them.

### Allowed Adaptation Dimensions

| Dimension | Direction | Example |
|-----------|-----------|---------|
| Role experience level | Raise threshold for junior, lower (to floor) for senior | Resident: 0.97, Attending: 0.95 (critical tier) |
| Workflow type | Workflow-specific overrides via `workflow_confidence_policy.py` | Emergency: use medium tier for speed; elective: use critical tier |
| Time pressure | Advisory mode in emergencies, strict mode in elective | Emergency: warn instead of block (never below floor) |

### Validation Requirement

Before any adaptive profile goes live:
- Simulation on historical data showing no role profile produces worse safety outcomes
- Minimum 100 simulated decisions per role profile
- Sign-off by Clinical AI Lead and ethics review body

## Consequences

- No adaptive thresholds during pilot (uniform policy enforced)
- Safety floor defined and documented (immutable)
- Ethics review gated on demand signal from clinical users
- `confidence_policy_service.py` architecture supports per-role profiles (minor extension needed)
- Cross-dependency: P4-007 (copilot experiments) inherits confidence floor

## Evidence Paths

- Confidence policy: `backend/app/services/confidence_policy_service.py`
- Workflow policy: `backend/app/services/workflow_confidence_policy.py`
- Pilot accuracy policy: `docs/operations/pilot_accuracy_policy.md`
- This decision: `docs/decisions/p4-011-adaptive-confidence.md`
