# Incident Escalation Matrix with Response SLAs

**Document ID**: OPS-P0-025
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CIO + Operations
**Classification**: Internal — Operational

## Purpose

Define named owners, escalation paths, and response time SLAs for all incident types relevant to the clinical AI platform.

## Severity Classification

| Severity | Description | Response SLA | Resolution Target | Example |
|---|---|---|---|---|
| SEV-1 (Critical) | Patient safety impact, PHI breach, complete service outage | 15 min acknowledge, 30 min bridge call | 4 hours | Wrong drug interaction result, PHI exposed, all APIs down |
| SEV-2 (High) | Major feature degraded, data accuracy concern, partial outage | 30 min acknowledge, 1 hour investigation | 8 hours | NLP extraction failing, KG build errors, OpenEHR import broken |
| SEV-3 (Medium) | Non-critical feature issue, performance degradation | 2 hours acknowledge | 24 hours | Dashboard slow, export timeout, non-critical API errors |
| SEV-4 (Low) | Minor issue, cosmetic, no clinical impact | 8 hours acknowledge | 72 hours | UI rendering issue, log formatting, non-blocking warning |

## Escalation Roles

| Role | Primary | Backup | Contact Method |
|---|---|---|---|
| Incident Commander | CTO | VP Engineering | PagerDuty + Slack #incidents |
| Clinical Safety Lead | Chief Medical Officer | Clinical AI Lead | PagerDuty + Phone |
| Security Lead | CISO | Security Engineer | PagerDuty + Slack #security |
| Operations Lead | SRE Lead | DevOps Engineer | PagerDuty + Slack #ops |
| Data Integrity Lead | Data Engineering Lead | CTO | PagerDuty + Slack #data |
| Compliance Lead | Compliance Officer | CIO | PagerDuty + Email |
| Communications Lead | VP Product | CIO | Slack #comms |

## Escalation Paths by Incident Type

### Clinical Safety Incidents (SEV-1)

```
Detection → Operations Lead (5 min) → Incident Commander (10 min)
         → Clinical Safety Lead (10 min, parallel)
         → CISO (15 min if PHI involved)
         → CIO (30 min if external notification required)
```

**Actions**:
1. Immediately disable affected clinical pathway
2. Open bridge call with Clinical Safety Lead
3. Assess patient impact scope
4. Notify compliance if PHI breach suspected
5. Document in incident tracker within 1 hour

### Data Integrity Incidents (SEV-1/SEV-2)

```
Detection → Data Integrity Lead (15 min) → CTO (30 min)
         → Clinical Safety Lead (30 min if clinical data affected)
```

**Actions**:
1. Quarantine affected data pipeline
2. Run reconciliation on affected date range
3. Assess downstream impact (KG, clinical agent, exports)
4. Initiate rollback if data corruption confirmed

### Security Incidents

```
Detection → Security Lead (15 min) → Incident Commander (15 min)
         → Compliance Lead (30 min if PHI/regulatory)
         → Legal (1 hour if breach confirmed)
```

**Actions**:
1. Follow `docs/security/incident_runbooks/runbook_phi_breach.md`
2. Preserve forensic evidence
3. Contain blast radius
4. Begin HIPAA breach assessment within 1 hour

### Service Outage

```
Detection → Operations Lead (15 min) → CTO (30 min)
         → Communications Lead (1 hour if user-facing)
```

**Actions**:
1. Follow `docs/security/incident_runbooks/runbook_service_outage.md`
2. Check dependency health (`/health/ready`)
3. Initiate failover if primary services unrecoverable
4. Status page update within 30 minutes

### Interoperability Incidents (OpenEHR/FHIR)

```
Detection → Data Integrity Lead (30 min) → CTO (1 hour)
         → Site liaison (2 hours if partner-facing)
```

**Actions**:
1. Disable affected connector
2. Review contract violation details
3. Run replay validation against affected batch
4. Follow `docs/operations/openehr_reconciliation_rollback.md`

## On-Call Rotation

| Week | Primary On-Call | Secondary On-Call | Hours |
|---|---|---|---|
| Week 1 | SRE Lead | DevOps Eng #1 | 24/7 |
| Week 2 | DevOps Eng #1 | SRE Lead | 24/7 |
| Pilot period | CTO (backup) | — | Business hours + escalation |

**On-call handoff**: Monday 09:00 AEDT. Handoff includes active incident review and open item transfer.

## Communication Templates

### SEV-1 Initial Notification
```
INCIDENT: [Brief description]
SEVERITY: SEV-1
DETECTED: [Timestamp]
IMPACT: [Scope — users, patients, data]
STATUS: Investigating / Mitigating / Resolved
BRIDGE: [Call link]
IC: [Name]
NEXT UPDATE: [Time]
```

### Status Update (every 30 min for SEV-1)
```
UPDATE #[N]: [Description of progress]
STATUS: [Current status]
ETA: [Estimated resolution]
NEXT UPDATE: [Time]
```

## HIPAA Breach Notification Clock (P0-025-B)

This section documents the regulatory response-clock obligations triggered when a breach of unsecured PHI is discovered or reasonably should have been discovered. All timelines below are **calendar days** from the **Discovery Date**.

### Discovery Date Definition

The **Discovery Date** is the first day on which the breach is known to any member of the workforce, or would have been known through the exercise of reasonable diligence. An incident is "discovered" when it is first identified by:
- Automated monitoring or alerting (e.g., anomalous PHI access in audit logs)
- A workforce member, contractor, or business associate reporting suspicious activity
- A routine access review, audit, or security assessment

> The discovery date is **not** the date a formal investigation concludes. It is the date the potential breach was first noticed.

### Notification Timelines

| Obligation | Deadline | Recipient | Owner | Notes |
|---|---|---|---|---|
| Internal breach assessment | Discovery + 0–5 days | Security Lead + Compliance Lead | CISO | Determine if incident is a reportable breach under HIPAA 45 CFR 164.402 |
| Individual notification | Discovery + 60 days (max) | Each affected individual | Compliance Lead | Written notice by first-class mail; email only if individual has agreed to electronic notice |
| HHS/OCR notification (< 500 individuals) | Calendar year end (60 days after year of discovery) | HHS Office for Civil Rights | Compliance Lead | Submitted via HHS Breach Portal; may be batched annually |
| HHS/OCR notification (>= 500 individuals) | Discovery + 60 days (max) | HHS Office for Civil Rights | Compliance Lead | Submitted via HHS Breach Portal; must be concurrent with individual notification |
| Media notification (>= 500 in a single state/jurisdiction) | Discovery + 60 days (max) | Prominent media outlet(s) in affected state(s) | Communications Lead + Compliance Lead | Press release or equivalent; required by 45 CFR 164.406 |
| State Attorney General notification | Varies by state | State AG office | Compliance Lead + Legal | Some states (e.g., CA, TX, NY) have stricter/shorter timelines; check applicable state law |
| Business Associate notification to Covered Entity | Discovery + 60 days (max) | Covered Entity (if Sulci is the BA) | CISO + Compliance Lead | Must identify each individual whose PHI was involved |

### Response Clock Evidence Path

For every breach-like event, the following evidence chain must be captured and preserved:

```
Detection Event
  └─ Timestamp (UTC)
  └─ Detection method (alert name, audit log ID, reporter name)
  └─ Affected system(s)

Assessment Phase
  └─ Start timestamp
  └─ Assessor (name, role)
  └─ Breach determination: YES / NO / INCONCLUSIVE
  └─ Number of individuals affected (or estimate)
  └─ Types of PHI involved (demographics, clinical, financial)
  └─ Was PHI encrypted? (Y/N — if yes, breach exception may apply per 45 CFR 164.402(2))

Notification Phase (if breach confirmed)
  └─ Individual notification: date sent, method, count
  └─ HHS notification: date submitted, portal confirmation ID
  └─ Media notification: date issued, outlet(s), state(s)
  └─ State AG notification: date sent, state(s)
  └─ Business Associate notification: date sent, entity name
```

### Breach Exception (Encryption Safe Harbor)

Under 45 CFR 164.402(2), if PHI was encrypted using a method consistent with NIST SP 800-111 guidance and the decryption key was not compromised in the same incident, the event is **not** a reportable breach. Document encryption status as part of every assessment.

### Internal Escalation Timeline (Detect-to-Notify)

This is the internal clock from detection to external notification readiness. Target: complete internal assessment within 14 calendar days to allow sufficient time for notification within the 60-day window.

```
Day 0        Detection event logged
Day 0        Security Lead paged (per SEV-1 SLA: 15 min acknowledge)
Day 0–1      Initial containment + evidence preservation
Day 1–3      Forensic analysis: scope, affected individuals, PHI types
Day 3–7      Breach determination (YES/NO) by CISO + Compliance Lead
Day 7–14     If breach confirmed: draft notification letters, HHS submission
Day 14–30    Individual notifications mailed; HHS portal submission
Day 30–60    Media notification (if >= 500); state AG notification
Day 60       HARD DEADLINE — all required notifications must be complete
```

### Drill Requirements (P0-025-B)

To close P0-025-B, execute a tabletop exercise that walks through the full response clock:

- [ ] Simulate a PHI breach event (e.g., unauthorized access to patient records)
- [ ] Page the on-call roster and record response times
- [ ] Walk through breach assessment checklist
- [ ] Draft a mock HHS notification submission
- [ ] Draft mock individual notification letters
- [ ] Record the full detect → page → assess → notify timeline
- [ ] Verify response times meet internal SLA targets
- [ ] Store evidence in `docs/evidence/p0-025/`

## Post-Incident

- SEV-1/SEV-2: Postmortem within 48 hours (see `docs/operations/incident_postmortem_template.md`)
- SEV-3: Summary note in incident tracker within 1 week
- All: Action items tracked to closure in backlog
