# P4-012 Deferred Gate: Developer Platform

**Gate Status:** BLOCKED BY ADR
**ADR Decision:** DEFER. API surface categorized. Activation gated on first external partner LOI. (2026-02-16)
**ADR Path:** `docs/decisions/p4-012-developer-platform.md`

## Current Blocker

No external partner demand. Core product not yet stabilized. Internal API only — no developer portal, no sandboxed API keys, no external usage dashboards.

## Ownership

| Role | Owner |
|------|-------|
| Decision Owner | CTO + Product |
| Risk Owner | CTO |
| Evidence Owner | Product |
| Escalation Owner | CTO |

## Activation Trigger Conditions

All of the following must be satisfied before I/V can begin:

1. First external partner LOI signed
2. Sandbox provisioning capability operational
3. Core product stability demonstrated (all P0/P1 closed, staging confirmed)

## Required Evidence to Start I/V

- Signed partner LOI
- Sandbox K8s namespace provisioning tested
- API surface review completed

## Exit Criteria

- **P4-012-I (Implementation):** Developer portal with sandboxed API keys, usage dashboards, and documentation built
- **P4-012-V (Validation):** One external partner onboarded end-to-end with time-to-first-integration measured

## Review Schedule

| Checkpoint | Date | Owner |
|-----------|------|-------|
| Next scheduled review | 2026-05-17 | CTO |
| Escalation if no progress | 2026-08-17 | CTO |
| Annual re-evaluation | 2027-02-17 | CTO + CTO |

## Cross-Dependencies

- P4-002 (TEFCA) may require specific API compliance
- P4-003 (ONC) may require specific API compliance

## Evidence Directory

`docs/evidence/p4-012/`
