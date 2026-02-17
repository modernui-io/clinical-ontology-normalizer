# P4-013 Deferred Gate: SaMD Pathway

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** Current features do NOT meet SaMD definition. Threshold triggers defined for monitoring. (2026-02-16)
**ADR Path:** `docs/decisions/p4-013-samd-pathway.md`

## Current Blocker

Current feature set does not meet SaMD definition under TGA (AU) or FDA (US) guidance. System is positioned as clinical decision SUPPORT with clinician-in-the-loop requirement.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | Compliance + Legal |
| Risk Owner | Legal |
| Evidence Owner | Compliance |
| Escalation Owner | Legal |

## Activation Trigger Conditions

If ANY of the following become true, activation review required:

1. System makes autonomous treatment recommendations without clinician review
2. Drug interaction checker operates as standalone safety system
3. Marketing materials claim diagnostic capability
4. Clinical calculators remove "verify with clinician" warnings
5. Confidence thresholds removed or lowered below safety floor (P4-011)
6. System marketed as replacement for (not supplement to) clinician judgment

## Required Evidence to Start I/V

- SaMD threshold trigger confirmed
- Legal determination of classification pathway (TGA/FDA/MDR)

## Exit Criteria

- **P4-013-I (Implementation):** Quality management system and design history file built
- **P4-013-V (Validation):** Pre-submission meeting or regulatory sandbox feedback on classification and pathway

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | Legal |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + Legal |

## Cross-Dependencies

- P4-007 (copilot) may trigger SaMD review
- P4-010 (causal inference) may trigger SaMD review
- P4-001 (federated learning) cross-references SaMD determination

## Evidence Directory

`docs/evidence/p4-013/`
