# Alert Fatigue Controls and Tuned Severity Thresholds

**Document ID**: OPS-P2-018
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Operations
**Classification**: Internal — Operational

## Purpose

Prevent alert fatigue by tuning severity thresholds, implementing deduplication, and establishing alert hygiene practices.

## Alert Hygiene Principles

1. **Every alert must be actionable** — If an alert doesn't require human action, it's a metric, not an alert
2. **Every alert must have a runbook** — No alert without documented response steps
3. **Every alert must have an owner** — Unowned alerts are deleted
4. **False positive rate <10%** — Alerts exceeding this are tuned or disabled

## Severity Threshold Tuning

### Latency Alerts

| Metric | SEV-3 Threshold | SEV-2 Threshold | SEV-1 Threshold | Window |
|---|---|---|---|---|
| API P95 latency | >2s for 5 min | >5s for 5 min | >10s for 2 min | 5 min |
| API P99 latency | >5s for 5 min | >10s for 5 min | >30s for 2 min | 5 min |
| NLP extraction | >10s for 10 min | >30s for 5 min | >60s for 2 min | 5 min |
| Database query | >1s for 10 min | >5s for 5 min | >10s for 2 min | 5 min |

### Error Rate Alerts

| Metric | SEV-3 | SEV-2 | SEV-1 | Window |
|---|---|---|---|---|
| 5xx error rate | >1% for 10 min | >5% for 5 min | >20% for 2 min | rolling |
| 4xx error rate | >10% for 30 min | >25% for 10 min | — | rolling |
| Worker failure rate | >5% for 15 min | >15% for 5 min | >50% for 2 min | rolling |

### Resource Alerts

| Metric | Warning | Critical | Window |
|---|---|---|---|
| CPU usage | >70% for 15 min | >90% for 5 min | sustained |
| Memory usage | >80% for 10 min | >95% for 5 min | sustained |
| Disk usage | >75% | >90% | point-in-time |
| Queue depth | >1000 msgs for 10 min | >5000 msgs for 5 min | sustained |
| Connection pool | >80% utilized | >95% utilized | sustained |

## Deduplication Rules

| Rule | Configuration |
|---|---|
| Same alert, same host | Suppress duplicate for 5 minutes |
| Same alert, different hosts | Group into single notification after 3 occurrences |
| Flapping detection | If state toggles >3 times in 10 min, suppress and raise "flapping" alert |
| Recovery notification | Send once when alert resolves, suppress if resolves in <1 minute |
| Maintenance window | Suppress all non-SEV-1 during scheduled maintenance |

## Alert Routing by Time

| Time Period | SEV-1 | SEV-2 | SEV-3 |
|---|---|---|---|
| Business hours | PagerDuty + Slack | PagerDuty + Slack | Slack only |
| After hours | PagerDuty | Slack (no page) | Suppressed |
| Weekends | PagerDuty | Slack (no page) | Suppressed |
| Maintenance window | PagerDuty | Suppressed | Suppressed |

## Alert Review Cadence

| Frequency | Activity |
|---|---|
| Weekly | Review alert volume, false positive rate, snooze any noisy alerts |
| Monthly | Tune thresholds based on baseline drift, retire stale alerts |
| Quarterly | Full alert audit — delete unused, update runbooks, review routing |

## Metrics to Track

| Metric | Target |
|---|---|
| Alerts per on-call shift | <10 (excluding informational) |
| False positive rate | <10% |
| Mean time to acknowledge | <5 min for SEV-1, <15 min for SEV-2 |
| Alerts without runbook | 0 |
| Unactionable alerts | 0 |
