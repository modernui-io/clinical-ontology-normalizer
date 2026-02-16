# P0-027 Failover Simulation Evidence

- Operator: ___
- Timestamp (UTC): ___
- Environment: staging

## MTTR Table

| Simulation    | Outage Start | Detect | Recovery Start | Full Recovery | MTTR    | Pass Criteria | Notes |
|---------------|--------------|--------|----------------|---------------|---------|---------------|-------|
| PostgreSQL    |              |        |                |               |         |               |       |
| Redis/Kafka   |              |        |                |               |         |               |       |
| Neo4j         |              |        |                |               |         |               |       |
| External LLM  |              |        |                |               |         |               |       |
| Cascade (all) |              |        |                |               |         |               |       |

## Degraded Mode / Safety Checks

- Frontend degraded banner observed: YES / NO
  - Screenshot path:
- Clinical path blocked when unsafe: YES / NO
  - Endpoint tested:
  - Expected behavior:
  - Actual behavior:
- No-data-loss validated: YES / NO
  - Pre-outage row count:
  - Post-recovery row count:
- Data consistency post-recovery: YES / NO
  - Validation method:

## Pass/Fail Summary

| Check                          | Result |
|-------------------------------|--------|
| All MTTR within SLA targets   |        |
| Degraded banner displayed      |        |
| Clinical safety fallback works |        |
| No data loss                   |        |
| Data consistency               |        |

- Overall PASS/FAIL:
- Issues encountered:
- Corrective actions:
- Reference: docs/operations/failover_simulation.md
