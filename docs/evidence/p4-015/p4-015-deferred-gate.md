# P4-015 Deferred Gate: Clinical Outcome Feedback Loops

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** Framework defined. Direct metrics at pilot launch; indirect metrics deferred to EHR outcome feed. (2026-02-16)
**ADR Path:** `docs/decisions/p4-015-outcome-feedback.md`

## Current Blocker

Insufficient outcome data volume during initial pilot. No EHR outcome data feed established for indirect metrics (readmission, safety events). Direct metrics (acceptance rate, override rate, time-to-action) begin at pilot launch via P2-009 feedback pipeline.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | Clinical AI + CIO |
| Risk Owner | CIO |
| Evidence Owner | Clinical AI |
| Escalation Owner | CIO |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. Pilot operational for 90+ days (minimum data volume for direct metrics report)
2. EHR outcome data feed established (ADT events, lab results, follow-up diagnosis codes)
3. Clinical advisor sign-off on outcome metric definitions
4. At least one clinical advisor per active specialty reviews attribution methodology

## Required Evidence to Start I/V

- First quarterly direct metrics report available
- EHR outcome data feed specification agreed with Ramsey Health

## Exit Criteria

- **P4-015-I (Implementation):** Outcome data capture pipeline with linkage to system recommendations built
- **P4-015-V (Validation):** First quarterly outcome report demonstrating measurable signal — positive, negative, or inconclusive

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | CIO |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + CIO |

## Cross-Dependencies

- P4-009 (guideline corpus informs which outcomes are measurable per specialty)

## Evidence Directory

`docs/evidence/p4-015/`
