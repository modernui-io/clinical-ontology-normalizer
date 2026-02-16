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

## Post-Incident

- SEV-1/SEV-2: Postmortem within 48 hours (see `docs/operations/incident_postmortem_template.md`)
- SEV-3: Summary note in incident tracker within 1 week
- All: Action items tracked to closure in backlog
