# Service Level Agreements (SLAs)

**Document Version:** 1.0
**Effective Date:** 2026-02-08
**Last Reviewed:** 2026-02-08
**Owner:** Platform Engineering

## Overview

This document defines the Service Level Agreements (SLAs) for each critical service
in the Clinical Trial Patient Recruitment Platform. Each SLA specifies availability
targets, latency targets, error budgets, measurement methods, alerting thresholds,
and escalation procedures.

SLAs are measured using Service Level Indicators (SLIs) collected by the
`sli_collector` middleware and the `error_budget_service`.

### Definitions

- **SLA (Service Level Agreement):** The target level of service promised.
- **SLI (Service Level Indicator):** A quantitative measure of a service aspect
  (e.g., request latency, error rate).
- **SLO (Service Level Objective):** The target value for an SLI (e.g., p95 < 500ms).
- **Error Budget:** The maximum allowable amount of unreliability within an SLA period.
  Calculated as `1 - SLA_target`. For example, 99.9% availability allows 0.1% errors.

### Measurement Period

All SLAs are measured on a rolling 30-day calendar month. Error budgets reset at the
start of each calendar month (UTC).

---

## 1. API Gateway

### Service Description

The API Gateway serves as the primary entry point for all HTTP requests. It handles
routing, authentication, rate limiting, and middleware processing for all platform
endpoints.

### Availability Target

| Metric | Target |
|--------|--------|
| Uptime | 99.9% |
| Monthly allowed downtime | 43.2 minutes |

### Latency Targets

| Percentile | Target |
|------------|--------|
| p50 | < 100ms |
| p95 | < 500ms |
| p99 | < 2,000ms |

### Error Budget

- **Allowed error rate:** 0.1% of total requests per month
- **Calculation:** `total_errors / total_requests` must remain below `0.001`
- **Error definition:** Any response with HTTP status >= 500 (server errors)
- **Exclusions:** Client errors (4xx) are not counted against the error budget

### Measurement Method

- SLI middleware tracks every request passing through the API Gateway
- Latency measured from request receipt to response send (middleware timing)
- Availability calculated as: `1 - (5xx_responses / total_responses)`
- Metrics exposed at `GET /metrics/sli`

### Alerting Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| p95 latency > 500ms for 5 minutes | Warning | Notify on-call |
| p95 latency > 2s for 5 minutes | Critical | Page on-call |
| Error rate > 0.05% (50% budget consumed) | Warning | Notify on-call |
| Error rate > 0.08% (80% budget consumed) | Critical | Page on-call |
| Error budget exhausted | Critical | Freeze non-critical deployments |

### Escalation Procedures

1. **L1 (0-15 min):** On-call engineer investigates, checks health endpoints
2. **L2 (15-30 min):** Engineering lead notified, incident channel opened
3. **L3 (30-60 min):** VP Engineering notified, war room convened
4. **L4 (60+ min):** CTO notified, customer communication initiated

---

## 2. Trial Screening Service

### Service Description

The Trial Screening service evaluates patients against clinical trial eligibility
criteria. It supports single-patient screening and batch cohort screening for
patient recruitment.

### Availability Target

| Metric | Target |
|--------|--------|
| Uptime | 99.5% |
| Monthly allowed downtime | 3.6 hours |

### Latency Targets

| Operation | Percentile | Target |
|-----------|------------|--------|
| Single patient screen | p50 | < 1,000ms |
| Single patient screen | p95 | < 3,000ms |
| Single patient screen | p99 | < 5,000ms |
| Cohort screen (batch) | p50 | < 15,000ms |
| Cohort screen (batch) | p95 | < 30,000ms |
| Cohort screen (batch) | p99 | < 60,000ms |

### Error Budget

- **Allowed error rate:** 0.5% of total screening requests per month
- **Calculation:** `screening_errors / total_screening_requests` must remain below `0.005`
- **Error definition:** Screening requests that fail due to server errors, timeouts,
  or produce incorrect eligibility determinations
- **Exclusions:** Invalid input errors (malformed criteria), patient-not-found errors

### Measurement Method

- Per-endpoint SLI tracking on `/api/v1/trials/*/screen` and `/api/v1/cohorts/*/screen`
- Latency measured end-to-end including criteria evaluation and data retrieval
- Correctness sampled via periodic validation against known test cases
- Metrics aggregated in SLI collector with 5-minute rolling windows

### Alerting Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| Single screen p95 > 3s for 10 min | Warning | Notify on-call |
| Single screen p95 > 5s for 5 min | Critical | Page on-call |
| Cohort screen p95 > 30s for 10 min | Warning | Notify on-call |
| Error rate > 0.25% (50% budget) | Warning | Notify on-call |
| Error rate > 0.40% (80% budget) | Critical | Page on-call |
| Error budget exhausted | Critical | Freeze deployments to screening path |

### Escalation Procedures

1. **L1 (0-15 min):** On-call engineer checks database query plans, NLP pipeline health
2. **L2 (15-30 min):** Clinical engineering lead reviews screening logic
3. **L3 (30-60 min):** Engineering and clinical team joint investigation
4. **L4 (60+ min):** Leadership notified, fallback to manual screening initiated

---

## 3. FHIR Import Service

### Service Description

The FHIR Import service processes incoming FHIR R4 bundles, webhooks from external
EHR systems (including Metriport), and transforms clinical data into the platform's
internal representation.

### Availability Target

| Metric | Target |
|--------|--------|
| Uptime | 99.5% |
| Monthly allowed downtime | 3.6 hours |

### Latency Targets

| Operation | Percentile | Target |
|-----------|------------|--------|
| Webhook response (acknowledgment) | p50 | < 50ms |
| Webhook response (acknowledgment) | p95 | < 200ms |
| Webhook response (acknowledgment) | p99 | < 500ms |
| Bundle processing (small, <50 resources) | p50 | < 3,000ms |
| Bundle processing (small, <50 resources) | p95 | < 10,000ms |
| Bundle processing (large, 50-500 resources) | p95 | < 30,000ms |

### Error Budget

- **Allowed error rate:** 0.5% of total import operations per month
- **Calculation:** `import_errors / total_imports` must remain below `0.005`
- **Error definition:** Failed FHIR bundle processing, webhook timeouts, data
  transformation errors
- **Exclusions:** Invalid FHIR bundles (validation errors), duplicate resource imports

### Measurement Method

- Webhook response time measured at the HTTP layer (time to send 200/202 acknowledgment)
- Bundle processing time measured from receipt to completion of all resource persistence
- Import success rate tracked per source system
- Metrics collected via SLI middleware on `/api/v1/fhir/*` and `/api/v1/metriport/*`

### Alerting Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| Webhook p95 > 200ms for 5 min | Warning | Notify on-call |
| Webhook p95 > 500ms for 5 min | Critical | Page on-call |
| Bundle processing p95 > 10s for 10 min | Warning | Notify on-call |
| Import error rate > 0.25% (50% budget) | Warning | Notify on-call |
| Import error rate > 0.40% (80% budget) | Critical | Page on-call |
| Error budget exhausted | Critical | Pause non-critical imports |

### Escalation Procedures

1. **L1 (0-15 min):** On-call checks FHIR validation logs, database connection health
2. **L2 (15-30 min):** Integration engineer reviews webhook payloads and EHR connectivity
3. **L3 (30-60 min):** Cross-team investigation with EHR vendor support
4. **L4 (60+ min):** Leadership notified, manual data import procedures activated

---

## 4. NLP Pipeline

### Service Description

The NLP Pipeline processes clinical documents to extract medical entities, map them
to standard terminologies (OMOP, SNOMED-CT, ICD-10), and build clinical facts for
the knowledge graph.

### Availability Target

| Metric | Target |
|--------|--------|
| Uptime | 99.0% |
| Monthly allowed downtime | 7.2 hours |

### Latency Targets

| Operation | Percentile | Target |
|-----------|------------|--------|
| Document extraction (single) | p50 | < 2,000ms |
| Document extraction (single) | p95 | < 5,000ms |
| Document extraction (single) | p99 | < 10,000ms |
| Terminology mapping | p50 | < 500ms |
| Terminology mapping | p95 | < 2,000ms |

### Error Budget

- **Allowed error rate:** 1.0% of total NLP processing requests per month
- **Calculation:** `nlp_errors / total_nlp_requests` must remain below `0.01`
- **Error definition:** Failed document processing, extraction timeouts, mapping failures
- **Exclusions:** Empty documents, unsupported document formats

### Measurement Method

- Per-document processing time tracked from submission to completion
- Extraction quality measured via periodic F1 score evaluation against gold standard
- Terminology mapping accuracy sampled weekly
- Metrics collected on `/api/v1/documents/*/process`, `/api/v1/nlp/*`

### Alerting Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| p95 latency > 5s for 15 min | Warning | Notify on-call |
| p95 latency > 10s for 10 min | Critical | Page on-call |
| Error rate > 0.5% (50% budget) | Warning | Notify on-call |
| Error rate > 0.8% (80% budget) | Critical | Page on-call |
| Error budget exhausted | Critical | Queue new documents, investigate |

### Escalation Procedures

1. **L1 (0-15 min):** On-call checks NLP service health, model loading status
2. **L2 (15-30 min):** NLP engineering lead reviews extraction pipeline
3. **L3 (30-60 min):** ML engineering team investigates model performance
4. **L4 (60+ min):** Leadership notified, fallback to rule-based extraction

---

## 5. Database (PostgreSQL)

### Service Description

PostgreSQL is the primary data store for all patient records, clinical documents,
trial definitions, screening results, FHIR resources, and audit logs.

### Availability Target

| Metric | Target |
|--------|--------|
| Uptime | 99.99% |
| Monthly allowed downtime | 4.3 minutes |

### Latency Targets

| Operation | Percentile | Target |
|-----------|------------|--------|
| Simple queries (SELECT by PK) | p50 | < 10ms |
| Simple queries (SELECT by PK) | p95 | < 100ms |
| Simple queries (SELECT by PK) | p99 | < 250ms |
| Complex queries (JOINs, aggregations) | p50 | < 50ms |
| Complex queries (JOINs, aggregations) | p95 | < 500ms |
| Write operations (INSERT/UPDATE) | p50 | < 20ms |
| Write operations (INSERT/UPDATE) | p95 | < 200ms |

### Error Budget

- **Allowed error rate:** 0.01% of total database operations per month
- **Calculation:** `db_errors / total_db_operations` must remain below `0.0001`
- **Error definition:** Connection failures, query timeouts, deadlocks, constraint
  violations from application bugs
- **Exclusions:** Expected constraint violations (duplicate key from idempotent ops)

### Measurement Method

- Connection pool health monitored via health check endpoint
- Query latency tracked via SQLAlchemy event hooks
- Connection pool saturation monitored (checked_out vs pool_size)
- Replication lag monitored (if applicable)
- Metrics available at `GET /api/v1/health/detailed`

### Alerting Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| Query p95 > 100ms for 5 min | Warning | Notify on-call |
| Query p95 > 500ms for 5 min | Critical | Page on-call |
| Connection pool > 80% utilized | Warning | Notify on-call |
| Connection pool exhausted | Critical | Page on-call |
| Replication lag > 10s | Warning | Notify on-call |
| Database unreachable | Critical | Page on-call immediately |
| Error budget > 50% consumed | Warning | Review recent deployments |
| Error budget exhausted | Critical | Freeze all deployments |

### Escalation Procedures

1. **L1 (0-5 min):** On-call engineer checks connection pool, slow query log
2. **L2 (5-15 min):** DBA or platform engineer investigates, considers failover
3. **L3 (15-30 min):** Engineering leadership notified, failover initiated if needed
4. **L4 (30+ min):** CTO and compliance officer notified (PHI data at risk)

---

## Error Budget Policy

### Budget Consumption Levels

| Level | Threshold | Actions |
|-------|-----------|---------|
| Green | < 50% consumed | Normal operations, deployments proceed |
| Yellow | 50-80% consumed | Increased monitoring, deploy with caution |
| Orange | 80-100% consumed | Only critical fixes deployed, incident review required |
| Red | Budget exhausted | Freeze all non-critical changes, mandatory post-mortem |

### Budget Reset

Error budgets reset at 00:00 UTC on the first day of each calendar month.

### Budget Tracking

The `error_budget_service` tracks budget consumption in real-time and exposes
current status at `GET /metrics/sli/summary`. The service calculates:

- **Budget remaining:** `1 - (current_error_rate / allowed_error_rate)`
- **Burn rate:** Rate at which the budget is being consumed relative to the SLA period
- **Time to exhaustion:** Projected time until budget is fully consumed at current burn rate

### Post-Mortem Requirements

When an error budget is exhausted:

1. Incident post-mortem must be completed within 3 business days
2. Root cause analysis with contributing factors identified
3. Action items assigned with owners and due dates
4. Preventive measures documented and tracked to completion
5. SLA targets reviewed for appropriateness

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-08 | Platform Engineering | Initial SLA definitions |
