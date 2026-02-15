# Roadmap KPI Operating Scorecard

Date anchor
- Baseline: `2026-02-13`

Purpose
- Define objective metrics for roadmap execution and gate decisions.
- Standardize weekly and monthly reporting across roles.

## KPI Set

### Delivery KPIs

| KPI ID | Metric | Formula | Target |
|---|---|---|---|
| D-01 | P0 completion rate | completed P0 / total P0 | 100% before external pilot |
| D-02 | P1 completion rate | completed P1 / total P1 | >=95% before broad pilot |
| D-03 | Sprint predictability | completed sprint IDs / planned sprint IDs | >=85% |
| D-04 | Slip rate | slipped IDs / planned IDs | <=15% |
| D-05 | Blocker aging | avg days open for blockers | <=7 days |

### Safety and Quality KPIs

| KPI ID | Metric | Formula | Target |
|---|---|---|---|
| S-01 | Evidence-backed answer rate | answers with source IDs / non-empty answers | 100% in pilot mode |
| S-02 | Degraded-state visibility | degraded responses with reason_code / degraded responses | 100% |
| S-03 | Unsafe low-confidence action rate | unsafe low-confidence actions / low-confidence events | 0 |
| S-04 | Extraction status integrity | flows with propagated status / total flows | 100% |
| S-05 | OMOP mapping precision (negative set) | true negatives / negative test set | threshold set by QA signoff |

### Security and Compliance KPIs

| KPI ID | Metric | Formula | Target |
|---|---|---|---|
| C-01 | Auth enforcement coverage | prod-class services with auth enforced / prod-class services | 100% |
| C-02 | Secret hygiene compliance | deployment configs without insecure defaults / total configs | 100% |
| C-03 | Audit coverage completeness | PHI pathways with audit events / PHI pathways | 100% |
| C-04 | Tenant boundary enforcement | tenant-scoped queries passing tests / tenant-scoped tests | 100% |
| C-05 | PHI transport encryption compliance | encrypted PHI flows / total PHI flows | 100% |

### Operations KPIs

| KPI ID | Metric | Formula | Target |
|---|---|---|---|
| O-01 | Readiness integrity | correct readiness outcomes / readiness scenarios | 100% |
| O-02 | Incident response SLA adherence | incidents within SLA / total incidents | >=95% |
| O-03 | Restore drill success | successful restore drills / planned restore drills | 100% |
| O-04 | Dependency outage detection time | avg minutes to detection | <=5 min |
| O-05 | Queue backpressure activation correctness | correct activations / required activations | 100% |

## Gate Thresholds

- Gate G0 (P0 Exit)
- `D-01` = 100%
- `S-03` = 0
- `C-01` = 100%
- `O-01` = 100%

- Gate G1 (P1 Exit)
- `D-02` >= 95%
- `S-01` = 100%
- `S-02` = 100%
- `C-03` = 100%
- `O-02` >= 95%

- Gate G2 (Scale Gate)
- P2 completion materially on track
- SLO dashboards and canaries active
- DR and failover evidence current

## Reporting Cadence

- Daily
- Update delivery KPIs `D-01..D-05`

- Weekly
- Update safety/security/operations KPIs
- Publish posture recommendation

- Monthly
- Publish executive scorecard and trend analysis

## Posture Mapping

- `hold`
- Any P0 unresolved or any critical KPI below threshold.

- `controlled_go_only`
- P0 substantially closed, bounded exceptions signed, KPIs stable.

- `broader_pilot_candidate`
- P0 complete, P1 threshold met, and governance signoff complete.

## Source references

- `tasks/09_master_change_backlog_p0_p4.md`
- `tasks/10_execution_roadmap_2026.md`
- `tasks/11_p0_p1_sprint_plan_2026_q1.md`
- `tasks/12_ticket_seed_backlog_399.csv`

