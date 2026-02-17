# P4-004 Deferred Gate: Graph Platform Migration

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** Maintain Neo4j Community for pilot; evaluate at 50K patient threshold (2026-02-16)
**ADR Path:** `docs/decisions/p4-004-graph-platform.md`

## Current Blocker

Graph is non-critical projection layer (reconstructable from PostgreSQL). Current utilization 20%. No capacity pressure. Mock mode acceptable for pilot.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | CTO + Ops |
| Risk Owner | CTO |
| Evidence Owner | Ops |
| Escalation Owner | CTO |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. Patient count reaches 50K threshold
2. Graph query volume justifies managed HA
3. AWS mandate from infrastructure team (for Neptune consideration)

## Required Evidence to Start I/V

- 50K patient threshold reached OR graph query SLO violations observed; cost-benefit analysis of Aura vs Community at current scale

## Exit Criteria

- **P4-004-I (Implementation):** Migration plan with data export/import pipeline and zero-downtime cutover strategy
- **P4-004-V (Validation):** Load test on target platform matching production query patterns and throughput

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | CTO |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + CTO |

## Cross-Dependencies

- P4-006: Model versioning registry may share infrastructure considerations
- P4-005: Multi-region architecture impacts graph replication topology

## Evidence Directory

`docs/evidence/p4-004/`
