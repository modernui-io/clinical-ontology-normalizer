# P0/P1 Sprint Plan (Q1 2026)

Date anchors
- Plan baseline: `2026-02-13`
- Sprint window: `2026-02-16` to `2026-04-24`

Purpose
- Break the roadmap into executable two-week sprints focused on P0 then P1 closure.
- Tie each sprint to backlog IDs, owner lanes, and exit gates.

Cadence
- Sprint length: 2 weeks
- Demo/review: each sprint end Friday
- Gate review: each sprint end +1 business day

## Sprint 1 (2026-02-16 to 2026-02-27)

Theme
- P0 design lock and acceptance criteria freeze

Target backlog IDs
- `P0-001` `P0-002` `P0-003` `P0-004` `P0-005` `P0-006` `P0-007` `P0-008`
- `P0-009` `P0-010` `P0-011` `P0-012` `P0-013` `P0-014` `P0-015` `P0-016` `P0-017`
- `P0-018` `P0-019` `P0-020` `P0-021` `P0-022` `P0-023` `P0-024` `P0-025` `P0-026` `P0-027` `P0-028`

Commitments
- Acceptance tests documented per P0 item.
- Owner and due date set for every P0.
- Dependency map for P0 implementation sequence approved.

Exit gate
- Zero unresolved acceptance ambiguities for P0 scope.

### Sprint 1 Exit Gate Record (2026-02-21)
| Criterion | Result |
|-----------|--------|
| Planned IDs | P0-001..P0-028 (28 items) |
| Completed IDs | P0-001..P0-028 (28/28 — 100%) |
| Slipped IDs | None |
| Blockers | BLK-01..BLK-04 all CLOSED |
| Risk acceptance | 5 staging conditions documented in P0-028 signoff |
| Decision posture | `conditional_go` (pilot), `blocked_by_infrastructure` (staging), `hold` (broad rollout) |
| Test baseline | 43,005 passed, 0 failed |
| Evidence integrity | 143/143 paths verified |

**Note**: Sprint 1 completed ahead of schedule. All P0 items closed by 2026-02-19. P1 (35/35), P2 (30/30), P3 (25/25), and P4 plans also completed. Sprint 2-6 subtasks (191 total) are superseded by parent item closure. Remaining work is staging infrastructure provisioning.

## Sprint 2 (2026-03-02 to 2026-03-13) — SUPERSEDED

Theme
- P0 core implementation batch A (dependency safety + security defaults)

Target backlog IDs
- `P0-001` `P0-002` `P0-003` `P0-009` `P0-010` `P0-011` `P0-012` `P0-013`
- `P0-014` `P0-015` `P0-016` `P0-017`

Commitments
- Readiness and dependency fail-closed posture implemented.
- Auth/secrets/PHI boundary controls implemented for target scope.
- Security and ops acceptance checks executed for batch A.

Exit gate
- Batch A controls verified in pre-prod environment.

## Sprint 3 (2026-03-16 to 2026-03-27) — SUPERSEDED

Theme
- P0 core implementation batch B (clinical AI safety + product gating + ops drills)

Target backlog IDs
- `P0-004` `P0-005` `P0-006` `P0-007` `P0-008`
- `P0-018` `P0-019` `P0-020`
- `P0-021` `P0-022` `P0-023` `P0-024`
- `P0-025` `P0-026` `P0-027` `P0-028`

Commitments
- Evidence-bound response semantics and degraded workflow behavior implemented.
- OpenEHR contract and rollback/reconciliation package in place.
- Restore and outage simulation evidence captured.

Exit gate
- P0 closure review passed or signed bounded exceptions recorded.

## Sprint 4 (2026-03-30 to 2026-04-10) — SUPERSEDED

Theme
- P1 safety batch A (confidence model, provenance integrity, evidence fields)

Target backlog IDs
- `P1-001` `P1-002` `P1-003` `P1-004` `P1-005` `P1-006` `P1-007`
- `P1-008` `P1-009` `P1-010` `P1-011` `P1-012`

Commitments
- Confidence semantics and refusal policy implemented for critical workflows.
- Provenance and evidence requirements enforced in API payloads.
- OMOP fallback hardening and cache policy changes delivered.

Exit gate
- High-risk workflows pass confidence/evidence acceptance suite.

## Sprint 5 (2026-04-13 to 2026-04-24) — SUPERSEDED

Theme
- P1 safety batch B (operations governance, OpenEHR replay, compliance controls)

Target backlog IDs
- `P1-013` `P1-014` `P1-015` `P1-016` `P1-017` `P1-018` `P1-019`
- `P1-020` `P1-021` `P1-022` `P1-023` `P1-024` `P1-025` `P1-026`
- `P1-027` `P1-028` `P1-029` `P1-030` `P1-031` `P1-032` `P1-033` `P1-034` `P1-035`

Commitments
- Incident governance and support model are operational.
- OpenEHR replay and onboarding controls validated.
- Compliance/risk-acceptance/release gates active and auditable.

Exit gate
- P1 closure posture declared with evidence packet.

## Sprint 6 (2026-04-27 to 2026-05-08) — SUPERSEDED

Theme
- Transition sprint into P2 scale gate

Target backlog IDs
- `P2-001` `P2-002` `P2-003` `P2-004` `P2-005` `P2-006` `P2-007` `P2-008`

Commitments
- Scale-gate test harness starts with integration and provenance checks.
- Canary and reliability validation framework launched.

Exit gate
- P2 scale-gate execution is fully underway with measurable burn.

## Owner lanes (execution focus)

- CTO lane
- `P0-001` `P0-002` `P0-003` `P0-020` `P1-020` `P1-021` `P1-035`

- CISO lane
- `P0-009` `P0-010` `P0-011` `P0-012` `P0-013` `P0-014` `P0-015` `P0-016` `P0-017`
- `P1-027` `P1-028` `P1-029` `P1-034`

- Clinical AI lane
- `P0-004` `P0-005` `P0-006` `P0-007` `P0-008` `P0-022` `P0-023`
- `P1-001` to `P1-015`

- VP Product lane
- `P0-021` `P0-024`
- `P1-016` `P1-017` `P1-018` `P1-019`

- CIO/Interop lane
- `P0-018` `P0-019` `P0-025` `P0-028`
- `P1-030` `P1-031` `P1-032` `P1-033`

- Ops/SRE lane
- `P0-025` `P0-026` `P0-027`
- `P1-021` `P1-022` `P1-023` `P1-024` `P1-025` `P1-026`

## Reporting template per sprint

- Planned IDs
- Completed IDs
- Slipped IDs with cause
- Blockers and owner
- Risk acceptance decisions
- Decision posture (`hold` / `controlled_go_only` / `broader_pilot_candidate`)

## Source references

- `tasks/09_master_change_backlog_p0_p4.md`
- `tasks/10_execution_roadmap_2026.md`
- `tasks/08_autonomous_execution_board.md`

