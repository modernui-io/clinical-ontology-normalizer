# Risk Acceptance Workflow with Expiry Dates

**Document ID**: GOV-P1-033
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Program Lead + CISO
**Classification**: Internal — Governance

## Purpose

Define the formal process for documenting, approving, and tracking risk acceptances for unresolved P1 items. Each acceptance has a mandatory expiry date, preventing risks from being permanently deferred.

## When Risk Acceptance Is Required

A risk acceptance is required when:
1. A P1 backlog item cannot be resolved before its target milestone
2. A known vulnerability or gap is accepted for a bounded period
3. A workaround is in place but the root fix is deferred
4. A compliance requirement has a temporary exception

## Risk Acceptance Process

### Step 1: Risk Owner Documents the Risk

| Field | Description |
|---|---|
| Risk ID | Format: RA-YYYY-NNN |
| Related Backlog Item | P0/P1/P2 ID |
| Risk Description | What could go wrong and under what conditions |
| Impact Assessment | Patient safety / Data integrity / Security / Operational |
| Likelihood | High / Medium / Low |
| Current Mitigation | What controls are in place today |
| Residual Risk Level | Critical / High / Medium / Low |

### Step 2: Propose Acceptance Terms

| Field | Description |
|---|---|
| Acceptance Duration | Maximum 90 days for P1, 180 days for P2 |
| Expiry Date | Specific calendar date |
| Conditions | Any conditions that must remain true |
| Monitoring Plan | How the risk is monitored during acceptance |
| Trigger for Revocation | What would force immediate remediation |

### Step 3: Approval Chain

| Residual Risk | Required Approvers |
|---|---|
| Critical | CTO + CISO + CIO (all three) |
| High | CTO + CISO or CIO |
| Medium | CTO or CISO |
| Low | Risk Owner's direct manager |

### Step 4: Record in Register

Risk acceptance is recorded in the risk register with all fields above, plus:
- Approval date and approver names
- Review schedule (monthly for Critical/High, quarterly for Medium/Low)
- Closure criteria

## Risk Register Template

| Risk ID | Backlog ID | Description | Residual Level | Expiry | Approvers | Status |
|---|---|---|---|---|---|---|
| RA-2026-001 | P1-016 | Accuracy policy not yet clinician-validated | Medium | 2026-05-15 | CTO, VP Product | Active |
| RA-2026-002 | P1-034 | LLM provider contract pending legal review | High | 2026-04-15 | CTO, CISO, CIO | Active |

## Expiry Enforcement

### 30 Days Before Expiry
- Automated notification to risk owner and approvers
- Risk owner must submit update: Resolved / Extend / Escalate

### On Expiry Date
- If not resolved: Risk automatically escalates to next severity level
- Extension request requires re-approval with justification
- Maximum one extension per risk (then must be resolved or escalated to board)

### Post-Expiry
- Unresolved expired risks block the next release
- Reported in monthly executive risk summary (P2-030)

## Tracking

- Risk register maintained in `docs/governance/risk_register.md`
- Monthly review in program status meeting
- Quarterly audit by CISO
- Annual purge of resolved/expired acceptances

## Governance

- This workflow cannot be bypassed
- "Verbal acceptance" is not valid — must be documented
- Backdated acceptances are prohibited
- All changes to an acceptance require re-approval
