# Ticket Seed Backlog (399 Subtasks) - Usage Guide

Files
- Seed CSV: `tasks/12_ticket_seed_backlog_399.csv`
- Source backlog: `tasks/09_master_change_backlog_p0_p4.md`

What this is
- A ticket-ready decomposition of the 133-item master backlog into 399 subtasks:
- `PLAN`, `BUILD`, and `VERIFY` for each backlog ID.

Row count
- 400 CSV lines total (1 header + 399 subtasks).

Columns
- `subtask_id`: unique subtask identifier (example: `P0-001-A`)
- `backlog_id`: parent backlog ID (example: `P0-001`)
- `phase`: `PLAN`, `BUILD`, or `VERIFY`
- `priority`: `P0` to `P4`
- `workstream`: mapped execution lane
- `owner`: owner from source backlog
- `summary`: source item summary
- `sprint`: planned sprint/wave bucket
- `due_date`: target completion date
- `status`: default `todo`

Sprint mapping logic
- `P0 PLAN`: Sprint-1 (`2026-02-27`)
- `P0 BUILD`: Sprint-2 or Sprint-3 by item grouping
- `P0 VERIFY`: Sprint-3 (`2026-03-27`)
- `P1 PLAN`: Sprint-4 (`2026-04-10`)
- `P1 BUILD`: Sprint-4 or Sprint-5
- `P1 VERIFY`: Sprint-5 (`2026-04-24`)
- `P2`: Sprint-6 / Wave-D
- `P3`: Wave-E
- `P4`: Wave-F

Recommended import process
1. Import CSV into Jira/Linear as tasks.
2. Use `backlog_id` as parent-link key.
3. Group by `priority`, then `workstream`, then `sprint`.
4. Add labels: `roadmap-2026`, `pilot-readiness`, and priority labels.
5. Assign each row to named person (not only role) during sprint planning.

Required custom fields (recommended)
- `priority_class` (`P0`..`P4`)
- `workstream` (`WS-01`..`WS-08`)
- `gate_phase` (`PLAN`/`BUILD`/`VERIFY`)
- `pilot_gate_critical` (`true` for P0 and selected P1)

Weekly reporting minimum
- Planned vs completed vs slipped by sprint
- P0 burn-down
- P1 burn-down
- Blocker aging (days open)
- Decision posture (`hold`, `controlled_go_only`, `broader_pilot_candidate`)

Data quality note
- This seed is generated from role-reviewed backlog artifacts and is intended as a starting point.
- During sprint planning, replace role owners with named individuals and team capacity limits.

