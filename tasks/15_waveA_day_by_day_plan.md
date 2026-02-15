# Wave A Day-by-Day Plan (P0 Design Lock)

Window
- `2026-02-16` to `2026-02-27`

Objective
- Achieve P0 design/acceptance lock for all `P0-001..P0-028`.

## Day Plan

### Day 1 (`2026-02-16`)
- Kickoff and owner assignment confirmation.
- Confirm P0 scope freeze and acceptance format.
- Start with `P0-001..P0-003` design review.

Deliverables
- Owner roster and contacts.
- Draft acceptance criteria for dependency fail-closed posture.

### Day 2 (`2026-02-17`)
- Security control design for `P0-009..P0-017`.
- Define config baseline and policy expectations.

Deliverables
- Security acceptance matrix.
- Draft config compliance checklist.

### Day 3 (`2026-02-18`)
- Clinical AI safety design for `P0-004..P0-008`, `P0-022`, `P0-023`.
- Define response contract fields and decline behavior requirements.

Deliverables
- Clinical AI acceptance matrix.
- API response schema change list (design-level).

### Day 4 (`2026-02-19`)
- Product safety gating design for `P0-021`, `P0-024`.
- UX refusal/degraded behavior policy review.

Deliverables
- Confidence-to-action decision table.
- UI state matrix (`ok/degraded/blocked`).

### Day 5 (`2026-02-20`)
- OpenEHR migration design for `P0-018`, `P0-019`.
- Reconciliation and rollback controls draft.

Deliverables
- OpenEHR mapping and lineage draft.
- Rollback and reconciliation checklist draft.

### Day 6 (`2026-02-23`)
- Operations readiness design for `P0-025`, `P0-026`, `P0-027`.
- Incident and drill plans aligned to acceptance tests.

Deliverables
- Incident ownership draft with response windows.
- Restore/failure drill test plan.

### Day 7 (`2026-02-24`)
- Program signoff workflow for `P0-028`.
- Consolidate all P0 acceptance criteria into one packet.

Deliverables
- P0 acceptance packet v1.
- Risk acceptance template for exceptions.

### Day 8 (`2026-02-25`)
- Cross-role dependency review.
- Resolve conflicting assumptions and missing approvals.

Deliverables
- Dependency decision log.
- Updated blockers with owners/dates.

### Day 9 (`2026-02-26`)
- Final readiness walkthrough of all P0 design artifacts.
- Pre-implementation gate simulation.

Deliverables
- P0 gate simulation notes.
- Remediation list for unresolved items.

### Day 10 (`2026-02-27`)
- Milestone M1 decision review.
- Publish go/no-go for transition into P0 implementation.

Deliverables
- M1 outcome record.
- Sprint 2 implementation kickoff packet.

## Daily standup template
- Yesterday completed
- Today planned
- Blockers
- Risk changes
- Needed decisions

## End-of-Wave-A gate checklist
- All P0 items have acceptance criteria.
- All P0 items have owner and due date.
- All cross-role dependencies have named decision owner.
- All unresolved risks are explicitly tracked with mitigation.

## Source references
- `tasks/10_execution_roadmap_2026.md`
- `tasks/11_p0_p1_sprint_plan_2026_q1.md`
- `tasks/12_ticket_seed_backlog_399.csv`
- `tasks/14_risk_dependency_register.md`

