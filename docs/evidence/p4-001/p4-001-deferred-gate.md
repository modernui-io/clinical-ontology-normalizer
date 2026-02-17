# P4-001 Deferred Gate: Federated Learning

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** DEFER (2026-02-16)
**ADR Path:** `docs/decisions/p4-001-federated-learning.md`

## Current Blocker

Single-site production stability not yet achieved. Pilot not yet launched; 90-day stability period has not started.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | VP ML + CTO |
| Risk Owner | CTO |
| Evidence Owner | VP ML |
| Escalation Owner | CTO |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. Single-site stability gate: 90 consecutive days with zero SEV-1 and <3 SEV-2
2. Formal differential privacy budget analysis reviewed by external privacy counsel
3. Legal determination on whether federated model outputs constitute SaMD (cross-ref P4-013)
4. At least 2 committed partner organizations with signed data sharing agreements
5. Infrastructure readiness: mTLS, model versioning registry (P4-006), audit trail

## Required Evidence to Start I/V

- All 5 gate criteria met simultaneously; CTO + VP ML joint memo recommending activation

## Exit Criteria

- **P4-001-I (Implementation):** Privacy-preserving training pipeline built with DP guarantees
- **P4-001-V (Validation):** Model quality parity demonstrated between federated and centralized on test corpus

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | CTO |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + CTO |

## Cross-Dependencies

- P4-006: Model versioning registry required for infrastructure readiness
- P4-013: SaMD legal determination required before activation

## Evidence Directory

`docs/evidence/p4-001/`
