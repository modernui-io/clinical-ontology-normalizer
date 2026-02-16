# Support Staffing Model and On-Call Rotation

**Document ID**: OPS-P1-026
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CIO + Operations
**Classification**: Internal — Operational

## Purpose

Formalize the support staffing model and on-call rotation for the pilot window, ensuring adequate coverage for incident response, user support, and operational monitoring.

## Staffing Model

### Pilot Phase (Months 1-3)

| Role | FTE Allocation | Coverage | Primary Responsibility |
|---|---|---|---|
| SRE/DevOps Lead | 1.0 | Business hours + on-call | Infrastructure, monitoring, incident response |
| DevOps Engineer | 1.0 | Business hours + on-call backup | Deployment, scaling, backup verification |
| Clinical Support | 0.5 | Business hours | Clinician queries, workflow issues, training |
| Data Engineer | 0.5 | Business hours | Data quality, pipeline monitoring, reconciliation |
| Security Analyst | 0.25 | Business hours + escalation | Audit review, access monitoring, incident triage |

### Scale Phase (Months 4-6)

Add:
- Additional SRE for 24/7 coverage
- Dedicated clinical support FTE
- Interoperability engineer for multi-site

## On-Call Rotation

### Schedule

| Rotation | Week A | Week B | Week C | Week D |
|---|---|---|---|---|
| Primary | SRE Lead | DevOps Eng | SRE Lead | DevOps Eng |
| Secondary | DevOps Eng | SRE Lead | DevOps Eng | SRE Lead |
| Clinical Escalation | Clinical AI Lead | Clinical AI Lead | Clinical AI Lead | Clinical AI Lead |
| Security Escalation | CISO | Security Analyst | CISO | Security Analyst |

### Coverage Hours

- **Business hours** (Mon-Fri 08:00-18:00 AEDT): Primary on-call + all support staff
- **After hours** (18:00-08:00 weekdays, weekends): Primary on-call via PagerDuty
- **Escalation**: Secondary on-call if primary doesn't respond within 15 minutes

### Handoff Procedure

1. Monday 09:00 AEDT: Outgoing reviews active incidents with incoming
2. Transfer any open items in incident tracker
3. Verify PagerDuty rotation updated
4. Confirm access to all monitoring dashboards
5. Brief on any known issues or upcoming changes

## Support Channels

| Channel | Purpose | Response SLA |
|---|---|---|
| PagerDuty | SEV-1/SEV-2 incidents | 15 min |
| Slack #incidents | Incident coordination | 15 min (business hours) |
| Slack #ops-alerts | Automated alerts | 30 min (business hours) |
| Slack #clinical-support | Clinician questions | 2 hours (business hours) |
| Email support@sulci.ai | Non-urgent requests | 8 hours (business hours) |

## Escalation Tiers

| Tier | Who | When |
|---|---|---|
| L1 | Primary on-call | All alerts, initial triage |
| L2 | Secondary on-call + domain specialist | Unresolved after 30 min, or domain expertise needed |
| L3 | CTO + relevant lead | Unresolved after 2 hours, or cross-domain issue |
| Executive | CIO | Any patient safety concern, external notification needed |

## Burnout Prevention

- Maximum consecutive on-call days: 7
- Minimum gap between on-call rotations: 14 days
- Comp time: 1 day off per weekend on-call shift
- Post-incident rest: If SEV-1 resolved after midnight, late start next day

## Approval

| Role | Name | Date | Signature |
|---|---|---|---|
| CIO | | | |
| Operations Lead | | | |
| HR (staffing approval) | | | |
