# P4-003 Deferred Gate: ONC Certification

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** CONDITIONAL DEFER (2026-02-16)
**ADR Path:** `docs/decisions/p4-003-onc-certification.md`

## Current Blocker

ONC certification is US-specific and not required for AU pilot. System positioned as clinical ontology normalization platform, not EHR module.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | Compliance + Interop |
| Risk Owner | Compliance |
| Evidence Owner | Interop |
| Escalation Owner | Compliance |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. Product marketed as certified EHR module
2. Product performs functions requiring information blocking exceptions
3. US customer contractually requires ONC certification

## Required Evidence to Start I/V

- US market entry decision with ONC requirement confirmed; formal ONC-ACB engagement initiated

## Exit Criteria

- **P4-003-I (Implementation):** Gap analysis and remediation against ONC criteria (API conditions, USCDI data classes)
- **P4-003-V (Validation):** Pre-submission conformance testing against ONC test harness

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | Compliance |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + Compliance |

## Cross-Dependencies

- P4-002: TEFCA strategy likely co-activated with ONC certification for US market entry

## Evidence Directory

`docs/evidence/p4-003/`
