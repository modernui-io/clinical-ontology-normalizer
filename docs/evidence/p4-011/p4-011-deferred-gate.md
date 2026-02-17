# P4-011 Deferred Gate: Adaptive Confidence Thresholds

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** CONDITIONAL DEFER — Ethics review required before activation. Immutable safety floor defined per risk tier. (2026-02-16)
**ADR Path:** `docs/decisions/p4-011-adaptive-confidence.md`

## Current Blocker

Ethics review has not been conducted. No clinical user demand signal exists for role-adaptive thresholds. Uniform thresholds are enforced during pilot.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | Product + Clinical AI |
| Risk Owner | Product |
| Evidence Owner | Clinical AI |
| Escalation Owner | Product |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. Clinical user demand signal for role-specific threshold customization
2. Ethics review body convened (Clinical AI Lead + external ethics advisor + Compliance)
3. Ethics review demonstrates no role profile produces worse patient safety outcomes
4. Simulation on historical data with minimum 100 decisions per role profile
5. Clinical AI Lead and ethics review body sign-off

**Safety Floor (immutable):** Critical: 0.95, High: 0.85, Medium: 0.70, Low: 0.50

## Required Evidence to Start I/V

- Ethics review completed with positive determination
- Safety floor codified
- Simulation dataset available

## Exit Criteria

- **P4-011-I (Implementation):** Configurable threshold profiles per role with minimum safety floor that cannot be lowered
- **P4-011-V (Validation):** Simulation showing no role profile produces worse safety outcomes than baseline

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | Product |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + Product |

## Cross-Dependencies

- P4-007 (copilot experiments inherits confidence floor)

## Evidence Directory

`docs/evidence/p4-011/`
