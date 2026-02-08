# Performance Qualification (PQ) Protocol

**Document ID:** PQ-CON-001
**Version:** 1.0
**Effective Date:** 2026-02-08
**System:** Clinical Ontology Normalizer (CON) - Clinical Trial Patient Recruitment Platform

---

## 1. Purpose

This Performance Qualification (PQ) protocol verifies that the Clinical Ontology Normalizer system performs acceptably under production-like conditions, including expected load levels, sustained operation, and failure recovery. It demonstrates that the system meets performance, reliability, and scalability requirements.

## 2. Scope

This PQ covers:

- Throughput testing (concurrent operations)
- Latency requirements (API response times)
- Data integrity under load
- Availability and failover
- Scalability testing (data volume)
- Backup and recovery verification
- Long-running stability (soak testing)

## 3. References

| Document | ID |
|---|---|
| Installation Qualification Protocol | IQ-CON-001 |
| Operational Qualification Protocol | OQ-CON-001 |
| System Requirements Specification | SRS-CON-001 |
| Infrastructure Capacity Plan | ICP-CON-001 |

## 4. Prerequisites

- IQ-CON-001 and OQ-CON-001 completed and approved
- Production-like environment provisioned (equivalent hardware specs)
- Representative data set loaded (10K patients, 50 trials, 100K documents)
- Monitoring and observability tools configured
- Load testing tools available (k6, locust, or equivalent)

## 5. Responsibilities

| Role | Responsibility |
|---|---|
| QA Lead | Execute PQ test cases, collect metrics |
| Performance Engineer | Design and run load tests |
| Infrastructure Engineer | Monitor system resources during tests |
| Validation Lead | Review and approve PQ results |

---

## 6. PQ Protocol Sections

### 6.1 Throughput Testing

Verify the system handles expected concurrent load.

| Check ID | Scenario | Target | Measurement |
|---|---|---|---|
| PQ-THR-001 | 100 concurrent screening requests | All complete within 30s | Requests/second, error rate |
| PQ-THR-002 | 50 FHIR imports per minute | All imported successfully | Throughput, failure rate |
| PQ-THR-003 | 200 concurrent API reads | p99 < 3s | Response time distribution |
| PQ-THR-004 | 50 concurrent document ingestions | All processed | Queue depth, processing time |
| PQ-THR-005 | 10 concurrent NLP extractions | All complete within timeout | Extraction throughput |

### 6.2 Latency Requirements

Verify API response times meet SLA targets.

| Check ID | Endpoint Category | p50 Target | p95 Target | p99 Target |
|---|---|---|---|---|
| PQ-LAT-001 | Health check endpoints | < 50ms | < 100ms | < 200ms |
| PQ-LAT-002 | Patient CRUD operations | < 200ms | < 500ms | < 1s |
| PQ-LAT-003 | Document ingestion | < 500ms | < 2s | < 5s |
| PQ-LAT-004 | Single patient screening | < 1s | < 5s | < 10s |
| PQ-LAT-005 | OMOP concept mapping | < 100ms | < 500ms | < 1s |
| PQ-LAT-006 | NLP extraction (per document) | < 2s | < 10s | < 30s |
| PQ-LAT-007 | Knowledge graph query | < 500ms | < 2s | < 5s |
| PQ-LAT-008 | Audit log query | < 200ms | < 1s | < 3s |
| PQ-LAT-009 | FHIR resource export | < 200ms | < 1s | < 2s |
| PQ-LAT-010 | Dashboard metrics | < 300ms | < 1s | < 2s |

### 6.3 Data Integrity Under Load

Verify data correctness is maintained during concurrent operations.

| Check ID | Scenario | Acceptance Criteria |
|---|---|---|
| PQ-INT-001 | Concurrent document ingestion | No duplicate documents created |
| PQ-INT-002 | Concurrent screening | No duplicate enrollment records |
| PQ-INT-003 | Concurrent fact creation | No orphaned or duplicate ClinicalFacts |
| PQ-INT-004 | Concurrent graph writes | No duplicate or missing edges |
| PQ-INT-005 | Concurrent audit writes | No missing audit entries, correct ordering |

### 6.4 Availability Targets

Verify system meets uptime and resilience requirements.

| Check ID | Scenario | Target |
|---|---|---|
| PQ-AVL-001 | Sustained uptime (24hr test) | 99.9% availability |
| PQ-AVL-002 | Database failover | Recovery within 30 seconds |
| PQ-AVL-003 | Redis failover | Recovery within 10 seconds |
| PQ-AVL-004 | Application restart | Ready within 60 seconds |
| PQ-AVL-005 | Graceful degradation (Neo4j down) | Core functions remain available |

### 6.5 Scalability Testing

Verify system handles expected data volumes.

| Check ID | Scenario | Target |
|---|---|---|
| PQ-SCL-001 | 10,000 patients in database | CRUD operations within latency SLA |
| PQ-SCL-002 | 50 active trials | Screening performance within SLA |
| PQ-SCL-003 | 100,000 documents | Search and retrieval within SLA |
| PQ-SCL-004 | 1,000,000 clinical facts | Graph queries within SLA |
| PQ-SCL-005 | 500,000 audit log entries | Audit queries within SLA |

### 6.6 Backup and Recovery Verification

Verify data protection and recovery capabilities.

| Check ID | Scenario | Target |
|---|---|---|
| PQ-BKP-001 | Database backup execution | Completes within 30 minutes |
| PQ-BKP-002 | Recovery Point Objective (RPO) | < 1 hour data loss |
| PQ-BKP-003 | Recovery Time Objective (RTO) | < 4 hours to full service |
| PQ-BKP-004 | Backup data integrity | Restored data matches original |
| PQ-BKP-005 | Point-in-time recovery | Recover to specific timestamp |

### 6.7 Long-Running Stability (Soak Test)

Verify system stability under sustained load.

| Check ID | Scenario | Duration | Acceptance Criteria |
|---|---|---|---|
| PQ-SOK-001 | Sustained normal load | 24 hours | No memory leaks (RSS stable within 10%) |
| PQ-SOK-002 | Sustained normal load | 24 hours | No connection pool exhaustion |
| PQ-SOK-003 | Sustained normal load | 24 hours | No increasing error rate |
| PQ-SOK-004 | Sustained normal load | 24 hours | No latency degradation (p95 stable) |
| PQ-SOK-005 | Sustained normal load | 24 hours | Log files do not exceed disk capacity |

---

## 7. PQ Test Cases

### Throughput Tests

#### PQ-TC-001: Concurrent Screening Load
- **Objective:** Verify 100 concurrent screening requests complete successfully
- **Procedure:** Use load testing tool to submit 100 simultaneous screening requests
- **Pass Criteria:** All requests complete, error rate < 1%, p95 < 10s
- **Measurements:** Requests/sec, error count, latency distribution
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-002: FHIR Import Throughput
- **Objective:** Verify 50 FHIR imports per minute sustained
- **Procedure:** Submit FHIR resources at 50/min for 10 minutes
- **Pass Criteria:** All imports successful, no queue backlog > 100
- **Measurements:** Import rate, queue depth, error count
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-003: Concurrent API Read Load
- **Objective:** Verify 200 concurrent read requests
- **Procedure:** Simulate 200 concurrent GET requests across endpoints
- **Pass Criteria:** p99 < 3s, error rate < 0.1%
- **Status:** [ ] PASS  [ ] FAIL

### Latency Tests

#### PQ-TC-004: Health Check Latency
- **Objective:** Verify health endpoint responds within SLA
- **Procedure:** 1000 sequential health check requests
- **Pass Criteria:** p50 < 50ms, p95 < 100ms
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-005: Patient CRUD Latency
- **Objective:** Verify patient operations meet latency SLA
- **Procedure:** 500 CRUD operations (mixed create/read/update)
- **Pass Criteria:** p95 < 500ms
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-006: Screening Latency
- **Objective:** Verify single patient screening latency
- **Procedure:** 100 individual screening operations
- **Pass Criteria:** p95 < 5s
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-007: NLP Extraction Latency
- **Objective:** Verify NLP extraction time per document
- **Procedure:** Process 50 clinical notes of varying length
- **Pass Criteria:** p95 < 10s per document
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-008: Knowledge Graph Query Latency
- **Objective:** Verify graph query response time
- **Procedure:** 200 graph traversal queries (2-hop)
- **Pass Criteria:** p95 < 2s
- **Status:** [ ] PASS  [ ] FAIL

### Data Integrity Tests

#### PQ-TC-009: Concurrent Write Integrity
- **Objective:** Verify no data corruption under concurrent writes
- **Procedure:** 50 concurrent document ingestions, verify all records
- **Pass Criteria:** All documents present, no duplicates, correct content
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-010: Screening Result Consistency
- **Objective:** Verify screening results are deterministic
- **Procedure:** Screen same patient 10 times, compare results
- **Pass Criteria:** All 10 results identical
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-011: Audit Log Completeness Under Load
- **Objective:** Verify no audit entries lost under load
- **Procedure:** Generate 1000 API requests, count audit entries
- **Pass Criteria:** Audit count matches request count
- **Status:** [ ] PASS  [ ] FAIL

### Availability Tests

#### PQ-TC-012: Application Restart Recovery
- **Objective:** Verify application recovers from restart
- **Procedure:** Restart application process, measure time to ready
- **Pass Criteria:** /ready returns 200 within 60 seconds
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-013: Graceful Degradation (Neo4j Down)
- **Objective:** Verify core functions work without Neo4j
- **Procedure:** Stop Neo4j, verify document ingestion and screening still work
- **Pass Criteria:** Core endpoints return 200, graph endpoints return 503
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-014: Redis Reconnection
- **Objective:** Verify Redis reconnection after brief outage
- **Procedure:** Restart Redis, verify application reconnects
- **Pass Criteria:** Application recovers within 10 seconds
- **Status:** [ ] PASS  [ ] FAIL

### Scalability Tests

#### PQ-TC-015: Large Patient Database
- **Objective:** Verify performance with 10K patients
- **Procedure:** Load 10K patients, run patient search/list queries
- **Pass Criteria:** Search p95 < 1s, list p95 < 2s
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-016: Many Active Trials
- **Objective:** Verify performance with 50 active trials
- **Procedure:** Create 50 trials, run bulk screening
- **Pass Criteria:** Bulk screening completes within 5 minutes
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-017: Large Audit Log
- **Objective:** Verify audit query performance with 500K entries
- **Procedure:** Generate 500K audit entries, query with filters
- **Pass Criteria:** Filtered query p95 < 3s
- **Status:** [ ] PASS  [ ] FAIL

### Backup/Recovery Tests

#### PQ-TC-018: Backup Execution
- **Objective:** Verify database backup completes successfully
- **Procedure:** Trigger full database backup
- **Pass Criteria:** Backup completes, file is valid
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-019: Restore from Backup
- **Objective:** Verify database restore from backup
- **Procedure:** Restore from backup to clean database, verify data
- **Pass Criteria:** All records present, data integrity verified
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-020: Recovery Time
- **Objective:** Verify RTO < 4 hours
- **Procedure:** Simulate full system failure, perform recovery
- **Pass Criteria:** System operational within 4 hours
- **Status:** [ ] PASS  [ ] FAIL

### Soak Tests

#### PQ-TC-021: 24-Hour Stability
- **Objective:** Verify system stability over 24 hours
- **Procedure:** Run normal load for 24 hours, monitor metrics
- **Pass Criteria:** No memory leaks, stable latency, no crashes
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-022: Memory Stability
- **Objective:** Verify no memory leaks during sustained operation
- **Procedure:** Monitor RSS memory over 24 hours
- **Pass Criteria:** RSS variation < 10% from baseline
- **Status:** [ ] PASS  [ ] FAIL

#### PQ-TC-023: Connection Pool Stability
- **Objective:** Verify connection pools do not exhaust
- **Procedure:** Monitor active connections over 24 hours
- **Pass Criteria:** Active connections stay within pool limits
- **Status:** [ ] PASS  [ ] FAIL

---

## 8. Performance Baselines

Record baseline measurements during PQ execution for future regression comparison.

| Metric | Baseline Value | Date Measured | Measured By |
|---|---|---|---|
| Health check p50 | ___ms | __________ | ____________ |
| Health check p95 | ___ms | __________ | ____________ |
| Patient CRUD p95 | ___ms | __________ | ____________ |
| Screening p95 | ___ms | __________ | ____________ |
| NLP extraction p95 | ___ms | __________ | ____________ |
| Max concurrent users | _____ | __________ | ____________ |
| Peak memory (RSS) | ___MB | __________ | ____________ |
| Startup time | ___ms | __________ | ____________ |

---

## 9. Sign-Off

| Role | Name | Signature | Date |
|---|---|---|---|
| QA Lead | _________________ | _________________ | __________ |
| Performance Engineer | _________________ | _________________ | __________ |
| Infrastructure Engineer | _________________ | _________________ | __________ |
| Validation Lead | _________________ | _________________ | __________ |
| Quality Assurance Manager | _________________ | _________________ | __________ |

---

## 10. Deviation Log

| Deviation # | PQ Test | Description | Impact | Resolution | Resolved By | Date |
|---|---|---|---|---|---|---|
| | | | | | | |
