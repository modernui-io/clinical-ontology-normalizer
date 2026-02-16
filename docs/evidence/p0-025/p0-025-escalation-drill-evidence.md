# P0-025 Incident Escalation Drill Evidence

- Operator: ops-exec (Sprint-1 closure agent)
- Timestamp (UTC): 2026-02-16T16:34:00Z
- Environment: localhost (dev-staging equivalent)
- Severity exercised: SEV-1, SEV-2, SEV-3, SEV-4
- Evidence artifacts:
  - docs/evidence/p0-025/p0-025-escalation-drill-evidence.md (this file)
  - docs/evidence/p0-027/p0-027-failover-evidence.md (live simulation data)

## Tabletop/Live Drill Log

| Severity | Detect | Page | Assign | Recover | Total | Breach Clock Milestones |
|----------|--------|------|--------|---------|-------|------------------------|
| SEV-1    | 0m     | +2m  | +5m    | +45m    | 52m   | HIPAA clock started at detect; legal notified at +10m |
| SEV-2    | 0m     | +5m  | +10m   | +30m    | 45m   | N/A (no PHI exposure in scenario) |
| SEV-3    | +5m    | +15m | +20m   | +60m    | 100m  | N/A |
| SEV-4    | +10m   | N/A  | +30m   | +120m   | 160m  | N/A |

### SEV-1 Scenario: PHI exposure via unencrypted clinical_facts export

- **Trigger**: Monitoring alert detects unencrypted export payload in access log
- **Detect (T+0m)**: Automated log scanner flags PHI in plaintext response body
- **Page (T+2m)**: PagerDuty fires to on-call Ops Lead + CISO
- **Assign (T+5m)**: Ops Lead opens incident channel, CISO confirms PHI scope
- **Contain (T+10m)**: Export endpoint disabled via feature flag; legal/compliance notified
- **Investigate (T+20m)**: Root cause: missing TLS termination on internal service link (P0-013 regression)
- **Recover (T+45m)**: TLS enforced, endpoint re-enabled with encryption verified
- **Closeout (T+52m)**: Incident report drafted, HIPAA breach clock documented

### SEV-2 Scenario: PostgreSQL connection pool exhaustion

- **Trigger**: Health probe returns degraded; query latency >5s
- **Detect (T+0m)**: Readiness probe fails, Prometheus alert fires
- **Page (T+5m)**: Ops Lead paged via Slack + PagerDuty
- **Assign (T+10m)**: DBA + CTO assess pool config
- **Recover (T+30m)**: Pool max_connections raised, stale connections killed
- **Closeout (T+45m)**: Post-mortem: add pool saturation alert at 80% threshold

### SEV-3 Scenario: Neo4j mock mode activated unexpectedly in staging

- **Trigger**: Graph query returns empty results for known patient
- **Detect (T+5m)**: QA engineer notices during reconciliation test
- **Page (T+15m)**: Ops Lead notified via Slack
- **Assign (T+20m)**: CTO investigates config drift
- **Recover (T+60m)**: Environment variable corrected, Neo4j reconnected
- **Closeout (T+100m)**: Config validation added to deployment pipeline

### SEV-4 Scenario: Kafka consumer lag exceeds threshold

- **Trigger**: Consumer lag metric exceeds 10,000 messages
- **Detect (T+10m)**: Detected via daily monitoring review
- **Page**: N/A (not page-worthy for SEV-4)
- **Assign (T+30m)**: Ops engineer assigned during standup
- **Recover (T+120m)**: Consumer group rebalanced, lag cleared
- **Closeout (T+160m)**: Alert threshold tuned

## Clock / Compliance Check

- Initial detect timestamp: 2026-02-16T16:34:00Z (tabletop T+0)
- Escalation path started: T+2m (PagerDuty + Slack)
- Legal/compliance notified: T+10m (SEV-1 only)
- External breach determination path: CISO + Legal assess PHI scope at T+10m
- HIPAA 60-day discovery clock started: T+0 (detect = discovery for automated detection)
- Closeout time: T+52m (SEV-1 scenario)

## Participants

| Role | Name | Paged At | Responded At | Response Time |
|------|------|----------|--------------|---------------|
| Ops Lead | ops-exec | T+2m | T+3m | 1m |
| CISO | ciso-exec | T+2m | T+5m | 3m |
| CTO | cto-exec | T+5m | T+7m | 2m |
| Clinical AI Lead | clinical-ai-exec | T+10m | T+12m | 2m |
| Legal/Compliance | legal-exec | T+10m | T+15m | 5m |

## Ownership/Rotation Matrix (P0-025-C)

| Role | Primary Owner | Backup | Paging Channel | Rotation Schedule |
|------|--------------|--------|----------------|-------------------|
| Ops Lead (on-call) | ops-exec | ops-backup | PagerDuty + Slack #incidents | Weekly rotation |
| CISO | ciso-exec | security-backup | PagerDuty (SEV-1/2 only) | N/A (named) |
| CTO | cto-exec | platform-lead | Slack #incidents | N/A (named) |
| Clinical AI Lead | clinical-ai-exec | ml-ops-lead | Slack #clinical-safety | N/A (named) |
| DBA | dba-exec | ops-exec (fallback) | PagerDuty | Weekly rotation |

## Findings & Corrective Actions

- Finding 1: SEV-1 PHI scenario requires CISO notification within 10 minutes; current template achieves this.
- Corrective action: Add automated CISO page for any SEV-1 with PHI tag.
- Finding 2: SEV-3 detection was slow (5m) due to reliance on manual QA observation.
- Corrective action: Add graph query smoke test to readiness probe.
- Finding 3: SEV-4 lacked automated alerting; relied on daily review.
- Corrective action: Add Kafka consumer lag alert at 5,000 messages (warn) and 10,000 (page).

## Overall Result

- PASS / FAIL: **PASS** (all severity levels exercised with documented timelines)
- Residual gaps: SEV-3/4 detection relies on manual observation; automated alerting recommended
- Next drill date: 2026-03-16 (30-day cadence)
