# Alert Routing for Degraded and Mock Dependency States

**Document ID**: OPS-P1-024
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Operations
**Classification**: Internal — Operational

## Purpose

Define alert routing rules triggered when the platform detects degraded, mock, or unavailable dependency states. Ensures no silent degradation in production.

## Alert Sources

Alerts are generated from the health check system (`/health/ready`) which monitors:

| Dependency | Check Method | Poll Interval |
|---|---|---|
| PostgreSQL | Connection pool health | 30s |
| Redis | PING command | 30s |
| Neo4j | Driver session verify | 60s |
| Kafka | Broker metadata fetch | 60s |
| External LLM | Lightweight inference check | 120s |

## Alert Rules

### Rule 1: Dependency Unavailable (SEV-2)

**Trigger**: Any critical dependency (PostgreSQL, Redis) reports unavailable for >60 seconds.

**Route**: PagerDuty → Primary On-Call → Slack #incidents

**Actions**:
1. Page primary on-call immediately
2. Post to #incidents with dependency name and check output
3. If not acknowledged in 15 minutes, escalate to CTO

### Rule 2: KG Dependency Degraded (SEV-3)

**Trigger**: Neo4j unavailable for >2 minutes or Kafka unavailable for >5 minutes.

**Route**: Slack #ops-alerts → Operations Lead

**Actions**:
1. Alert in #ops-alerts with degraded dependency details
2. Verify clinical agent returns `fallback_used: true`
3. Monitor for recovery within 15 minutes

### Rule 3: Mock Mode Detected in Non-Dev (SEV-1)

**Trigger**: Any dependency health check returns `mock_mode: true` when environment is `staging` or `production`.

**Route**: PagerDuty → CTO + CISO immediately

**Actions**:
1. CRITICAL: Mock mode in production is a safety violation
2. Page CTO and CISO simultaneously
3. Block all clinical endpoints until resolved
4. Incident report required

### Rule 4: LLM Provider Unreachable (SEV-3)

**Trigger**: External LLM health check fails for >2 consecutive checks.

**Route**: Slack #ops-alerts → Clinical AI Lead

**Actions**:
1. Verify rule-based fallback is active
2. Monitor extraction quality for degradation
3. Escalate to SEV-2 if fallback quality drops below threshold

### Rule 5: Sustained Degradation (SEV-2 escalation)

**Trigger**: Any SEV-3 alert unresolved for >30 minutes.

**Route**: Escalate from Slack to PagerDuty

**Actions**:
1. Automatic escalation to PagerDuty
2. Page Operations Lead
3. Begin root cause investigation

## Alert Deduplication

- Same dependency, same state: Suppress duplicate for 5 minutes
- Recovery after alert: Send recovery notification to same channel
- Flapping detection: If dependency toggles >3 times in 10 minutes, raise SEV-2 "flapping" alert

## Integration Points

### Backend Implementation

Alert state changes are detected by the existing health check polling in `backend/app/api/health.py`. The alert routing integrates with:

- `backend/app/services/alert_rules_service.py` — Rule evaluation engine
- `backend/app/services/notification_service.py` — Delivery (PagerDuty, Slack, email)
- `backend/app/services/observability_service.py` — Metric recording

### Configuration

```python
DEPENDENCY_ALERT_RULES = {
    "postgresql_unavailable": {
        "severity": "SEV-2",
        "threshold_seconds": 60,
        "route": ["pagerduty", "slack:#incidents"],
    },
    "redis_unavailable": {
        "severity": "SEV-2",
        "threshold_seconds": 60,
        "route": ["pagerduty", "slack:#incidents"],
    },
    "neo4j_degraded": {
        "severity": "SEV-3",
        "threshold_seconds": 120,
        "route": ["slack:#ops-alerts"],
    },
    "mock_mode_production": {
        "severity": "SEV-1",
        "threshold_seconds": 0,
        "route": ["pagerduty", "slack:#incidents", "slack:#security"],
    },
    "llm_unreachable": {
        "severity": "SEV-3",
        "threshold_seconds": 240,
        "route": ["slack:#ops-alerts"],
    },
}
```

## Testing

- Alert routing tested during failover simulation (P0-027)
- Mock mode detection tested in staging environment
- PagerDuty integration verified via test escalation
