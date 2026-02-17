# P4-005 Deferred Gate: Multi-Region Architecture

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** Single-region AU (ap-southeast-2) for pilot; active-passive to Melbourne when demand justifies (2026-02-16)
**ADR Path:** `docs/decisions/p4-005-multi-region.md`

## Current Blocker

Single-region sufficient for pilot scale. No second AU customer or non-AU customer. Multi-AZ within Sydney provides 99.99% availability.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | CTO + CISO |
| Risk Owner | CISO |
| Evidence Owner | CTO |
| Escalation Owner | CISO |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. Second AU customer signed (geo-redundancy justification)
2. Non-AU customer with data residency solution
3. Regulatory requirement for geographic redundancy

## Required Evidence to Start I/V

- Second customer LOI or non-AU data residency framework approved; cross-AZ PostgreSQL replica operational (P2/P3 prerequisite)

## Exit Criteria

- **P4-005-I (Implementation):** Multi-region deployment topology with cross-region replication and DNS failover
- **P4-005-V (Validation):** Region failover drill with RTO/RPO measurement and data residency compliance check

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | CISO |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + CISO |

## Cross-Dependencies

- P4-002: TEFCA strategy requires multi-region if US data residency needed
- P4-004: Graph platform migration topology depends on region count

## Evidence Directory

`docs/evidence/p4-005/`
