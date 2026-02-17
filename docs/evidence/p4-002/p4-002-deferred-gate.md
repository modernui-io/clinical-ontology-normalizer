# P4-002 Deferred Gate: TEFCA Strategy

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** DEFER (2026-02-16)
**ADR Path:** `docs/decisions/p4-002-tefca-strategy.md`

## Current Blocker

TEFCA is US-specific. Current pilot is AU (Ramsey Health). No US customer demand exists.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | Interop + CIO |
| Risk Owner | CIO |
| Evidence Owner | Interop |
| Escalation Owner | CIO |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. US customer LOI signed
2. Partner QHIN selected (Carequality preferred)
3. QHIN must support IHE PDQm and MHD
4. QHIN must have AU/APAC-aware privacy controls or explicit data residency boundary

## Required Evidence to Start I/V

- Signed US customer LOI; QHIN partner selection completed

## Exit Criteria

- **P4-002-I (Implementation):** TEFCA-compliant exchange endpoints and credential management built
- **P4-002-V (Validation):** End-to-end query/response test with TEFCA sandbox

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | CIO |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + CIO |

## Cross-Dependencies

- P4-003: ONC certification may be co-required if US market entry proceeds
- P4-005: Multi-region architecture needed if US data residency required

## Evidence Directory

`docs/evidence/p4-002/`
