# Risk and Dependency Register

Date anchor
- Baseline: `2026-02-13`

Purpose
- Track cross-stream risks and dependencies that affect roadmap dates and gate decisions.

Status legend
- `open`
- `mitigating`
- `closed`
- `accepted`

## Risks

| Risk ID | Description | Impact | Likelihood | Owner | Status | Target date | Mitigation |
|---|---|---|---|---|---|---|---|
| R-001 | Mock/fallback behavior remains non-fail-closed in production posture | High | High | CTO + Ops + CISO | open | 2026-03-13 | Close `P0-001..P0-003` and verify with outage simulation |
| R-002 | OpenEHR mapping ambiguity delays migration readiness | High | High | CIO + CTO | open | 2026-03-27 | Close `P0-018`, `P0-019`, `P1-031` with signed contract and replay evidence |
| R-003 | Confidence model remains inconsistent across modules | High | Medium | Clinical AI + Product | open | 2026-04-10 | Close `P1-001..P1-004`, `P1-016..P1-019` |
| R-004 | Auth/secrets controls incomplete in production templates | High | High | CISO | open | 2026-03-13 | Close `P0-009..P0-013` and run config compliance checks |
| R-005 | Audit gaps for worker and graph access persist | High | Medium | CISO + Ops | open | 2026-03-27 | Close `P0-014`, `P0-015`, `P1-029` |
| R-006 | Incident ownership unclear during pilot escalation | Medium | Medium | CIO + Ops | open | 2026-03-27 | Close `P0-025`, `P1-026`, `P1-032` |
| R-007 | Restore/failover drill failure reveals hidden infra weakness | High | Medium | Ops + CTO | open | 2026-03-27 | Execute `P0-026`, `P0-027` and remediate findings |
| R-008 | Team bandwidth causes P0/P1 slip | Medium | High | Program Lead | open | 2026-04-24 | Weekly capacity rebalance and scope freeze policy |
| R-009 | External provider/legal approvals lag for PHI-capable model routes | Medium | Medium | CISO + Legal | open | 2026-04-24 | Close `P0-017`, `P1-034` |
| R-010 | Interop replay fixtures not representative of real Meditech variability | Medium | Medium | Interop + QA | open | 2026-04-24 | Expand fixture coverage and close `P1-031` quality gate |

## Dependencies

| Dependency ID | Depends on | Blocks | Owner | Status | Needed by |
|---|---|---|---|---|---|
| D-001 | Finalized P0 acceptance criteria | P0 implementation start | Program Lead | open | 2026-02-27 |
| D-002 | Security policy decisions for auth/secrets | P0 security controls | CISO | open | 2026-03-13 |
| D-003 | OpenEHR contract signoff | Migration replay and rollback runbook | CIO + CTO | open | 2026-03-27 |
| D-004 | Unified confidence schema | Product gating and refusal policy | Clinical AI + Product | open | 2026-04-10 |
| D-005 | Alerting/paging ownership map | Ops incident SLA enforcement | Ops + CIO | open | 2026-04-24 |
| D-006 | QA test harness updates | P1/P2 evidence completion | QA Lead | open | 2026-04-24 |
| D-007 | Provider routing policy + legal approvals | External LLM PHI path controls | CISO + Legal | open | 2026-04-24 |
| D-008 | Capacity plan across streams | Sprint predictability targets | Program Lead | open | 2026-02-27 |

## Weekly update template

- Open risks by severity
- Newly mitigated risks
- Dependencies at risk of slip
- Net impact on milestone dates
- Required executive decisions

## Source references

- `tasks/10_execution_roadmap_2026.md`
- `tasks/11_p0_p1_sprint_plan_2026_q1.md`
- `tasks/12_ticket_seed_backlog_399.csv`
- `tasks/13_roadmap_kpi_operating_scorecard.md`

