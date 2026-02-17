# P4-014 Deferred Gate: Data Mesh Architecture

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** PREMATURE. Maintain monolith with domain boundaries in code. Revisit at 100K patients or 10+ engineers. (2026-02-16)
**ADR Path:** `docs/decisions/p4-014-data-mesh.md`

## Current Blocker

At <10K patients and <5 engineers, data mesh complexity vastly exceeds benefit. Operational overhead (N monitoring pipelines, N backup strategies, cross-service consistency) would consume more engineering capacity than the entire current team.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | CTO + Data |
| Risk Owner | CTO |
| Evidence Owner | Data |
| Escalation Owner | CTO |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. Team exceeds 10 engineers
2. Patient count exceeds 100K
3. Cross-domain query conflicts become measurable bottleneck

## Required Evidence to Start I/V

- Scale assessment showing 100K+ patients AND 10+ engineers
- Cross-domain query latency SLO violations documented
- Pilot domain (Analytics/Reporting) scoped

## Exit Criteria

- **P4-014-I (Implementation):** Pilot one domain as self-serve data product with contracts and SLOs
- **P4-014-V (Validation):** Measure data product consumer satisfaction and operational overhead vs monolithic baseline

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | CTO |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + CTO |

## Cross-Dependencies

- None (independent architecture decision)

## Evidence Directory

`docs/evidence/p4-014/`
