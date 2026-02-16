# Sprint 1 Execution Board (Auto-Generated)

Window
- `2026-02-16` to `2026-02-27`

Source
- `tasks/12_ticket_seed_backlog_399.csv`

## Summary
- Total Sprint-1 tasks: 28
- P0 tasks: 28
- P1 tasks: 0

## Workstream Breakdown
- WS-01 Platform reliability: 4 tasks
- WS-02 Security compliance: 9 tasks
- WS-03 Clinical AI safety: 7 tasks
- WS-04 Product trust UX: 2 tasks
- WS-05 OpenEHR interoperability: 2 tasks
- WS-06 SRE operations: 3 tasks
- WS-08 Program governance: 1 tasks

## Task Table
| subtask_id | backlog_id | priority | workstream | owner | summary | due_date | status |
|---|---|---|---|---|---|---|---|
| P0-001-A | P0-001 | P0 | WS-01 Platform reliability | CTO + Ops | Fail closed in readiness when Neo4j is unavailable. | 2026-02-27 | done |
| P0-002-A | P0-002 | P0 | WS-01 Platform reliability | CTO + Ops | Fail closed in readiness when Kafka is unavailable for required flows. | 2026-02-27 | done |
| P0-003-A | P0-003 | P0 | WS-01 Platform reliability | CTO + CISO | Remove ""mock_mode treated as connected"" semantics from production posture checks. | 2026-02-27 | done |
| P0-004-A | P0-004 | P0 | WS-03 Clinical AI safety | Clinical AI + CTO | Surface `dependency_state` in all clinical query responses. | 2026-02-27 | done |
| P0-005-A | P0-005 | P0 | WS-03 Clinical AI safety | Clinical AI | Block graph build when ingestion has note-level extraction failures. | 2026-02-27 | done |
| P0-006-A | P0-006 | P0 | WS-03 Clinical AI safety | Clinical AI | Propagate extraction status (`ok|partial|failed`) across import, KG build, and Q&A. | 2026-02-27 | done |
| P0-007-A | P0-007 | P0 | WS-03 Clinical AI safety | Clinical AI + CISO | Enforce strict narrative grounding prior to KG writes. | 2026-02-27 | done |
| P0-008-A | P0-008 | P0 | WS-03 Clinical AI safety | Clinical AI + CTO | Disable hardcoded ontology edge fallback in production pathways. | 2026-02-27 | done |
| P0-009-A | P0-009 | P0 | WS-02 Security compliance | CISO | Enforce authentication by default in non-dev environments. | 2026-02-27 | done |
| P0-010-A | P0-010 | P0 | WS-02 Security compliance | CISO + Platform | Remove insecure credential defaults from deployment templates. | 2026-02-27 | done |
| P0-011-A | P0-011 | P0 | WS-02 Security compliance | CISO + Ops | Require Redis authentication and restricted network exposure. | 2026-02-27 | done |
| P0-012-A | P0-012 | P0 | WS-02 Security compliance | CISO + Platform | Enforce encryption-at-rest for PHI stores. | 2026-02-27 | done |
| P0-013-A | P0-013 | P0 | WS-02 Security compliance | CISO + Ops | Enforce TLS for ingress and service links handling PHI. | 2026-02-27 | done |
| P0-014-A | P0-014 | P0 | WS-02 Security compliance | CISO + Ops | Add audit coverage for worker-based PHI operations. | 2026-02-27 | done |
| P0-015-A | P0-015 | P0 | WS-02 Security compliance | CISO + Clinical AI | Add audit tags for graph data access and query provenance. | 2026-02-27 | done |
| P0-016-A | P0-016 | P0 | WS-02 Security compliance | CISO + Platform | Enforce tenant/org boundary checks at query boundaries. | 2026-02-27 | done |
| P0-017-A | P0-017 | P0 | WS-02 Security compliance | CISO + Clinical AI | Add explicit policy gate for external model routes handling PHI. | 2026-02-27 | done |
| P0-018-A | P0-018 | P0 | WS-05 OpenEHR interoperability | CIO + CTO | Publish and approve canonical Meditech-to-OpenEHR mapping contract. | 2026-02-27 | done |
| P0-019-A | P0-019 | P0 | WS-05 OpenEHR interoperability | CIO + Ops | Add OpenEHR reconciliation and rollback procedure before live onboarding. Rollback savepoint fix applied (session-poisoning bug). Evidence: docs/evidence/p0-019/. Re-run against staging to confirm PASS. | 2026-02-27 | in-progress |
| P0-020-A | P0-020 | P0 | WS-01 Platform reliability | CTO + VP Product | Define one canonical ingestion-to-Q&A route for pilot users. | 2026-02-27 | done |
| P0-021-A | P0-021 | P0 | WS-04 Product trust UX | VP Product + Clinical AI | Enforce confidence-to-action policy for high-risk workflows. | 2026-02-27 | done |
| P0-022-A | P0-022 | P0 | WS-03 Clinical AI safety | Clinical AI | Require evidence-bound confidence and decline behavior on unsupported claims. | 2026-02-27 | done |
| P0-023-A | P0-023 | P0 | WS-03 Clinical AI safety | Clinical AI + Product | Require source document IDs and provenance fields for every non-empty answer. | 2026-02-27 | done |
| P0-024-A | P0-024 | P0 | WS-04 Product trust UX | VP Product | Add explicit ""degraded"" UX mode with action block and clinician escalation. | 2026-02-27 | done |
| P0-025-A | P0-025 | P0 | WS-06 SRE operations | CIO + Ops | Define and staff incident escalation matrix with response SLAs. | 2026-02-27 | todo |
| P0-026-A | P0-026 | P0 | WS-06 SRE operations | Ops | Execute one backup restore drill for PostgreSQL and Neo4j. | 2026-02-27 | todo |
| P0-027-A | P0-027 | P0 | WS-06 SRE operations | Ops + CTO | Execute one failover/dependency outage simulation and record MTTR. | 2026-02-27 | todo |
| P0-028-A | P0-028 | P0 | WS-08 Program governance | Program Lead | Produce final pre-pilot signoff matrix (CTO/CISO/CIO/Clinical AI/Product/Ops). | 2026-02-27 | todo |
