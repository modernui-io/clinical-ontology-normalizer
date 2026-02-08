# Business Continuity Plan (COO-2)

## 1. Policy and Objectives

### Purpose
This Business Continuity Plan (BCP) ensures the clinical trial patient recruitment platform can maintain or rapidly resume critical operations following disruptive events. The plan covers tabletop exercise scenarios, recovery procedures, exercise scheduling, and ongoing program metrics.

### Scope
- All production systems supporting clinical trial patient screening and recruitment
- Integration points with external services (Metriport, FHIR endpoints, trial sponsor APIs)
- Data stores (PostgreSQL, Redis, Neo4j) containing PHI and clinical trial data
- Infrastructure components (compute, storage, networking, DNS)

### Objectives
- **Recovery Time Objective (RTO)**: Restore critical services within scenario-specific RTO targets (ranging from 1 hour to 48 hours depending on scenario severity)
- **Recovery Point Objective (RPO)**: Limit data loss to scenario-specific RPO targets (ranging from 0 hours to 24 hours)
- **Exercise Frequency**: Conduct at least one tabletop exercise per scenario per quarter
- **Action Item Closure**: Close 90% or more of exercise-identified action items within 30 days

## 2. Tabletop Exercise Scenarios

### SCENARIO_1: Database Corruption During Active Trial Screening
- **Severity**: CRITICAL
- **RTO**: 4 hours | **RPO**: 1 hour
- **Description**: PostgreSQL database corruption in clinical_facts and screening_results tables during peak screening. Active trial screening for concurrent trials is disrupted.
- **Affected Systems**: PostgreSQL, screening engine, clinical facts store, audit logging, patient matching
- **Key Recovery Steps**: Halt pipelines, assess corruption, restore from backup (PITR), validate integrity, resume operations
- **Roles**: Incident Commander, DBA, Platform Engineer, Clinical Operations Lead, Compliance Officer

### SCENARIO_2: Complete Datacenter Failover (DR Activation)
- **Severity**: CRITICAL
- **RTO**: 8 hours | **RPO**: 4 hours
- **Description**: Primary datacenter unavailable due to regional cloud outage. All production services must failover to DR site.
- **Affected Systems**: All production services, databases, caches, graph DB, storage, DNS
- **Key Recovery Steps**: Confirm outage, declare DR event, promote replicas, switch DNS, verify services, validate screening
- **Roles**: Incident Commander, DBA, Platform Engineer, QA Engineer, Clinical Operations Lead, CISO

### SCENARIO_3: PHI Breach Detected in Audit Logs
- **Severity**: CRITICAL
- **RTO**: 2 hours | **RPO**: 0 hours
- **Description**: Unauthorized PHI access detected via audit log analysis. Compromised API key used from unknown IP to access patient data across multiple trials.
- **Affected Systems**: Patient matching, audit logging, API gateway, auth service, demographics, screening results
- **Key Recovery Steps**: Revoke credentials, activate breach response, forensic analysis, rotate keys, prepare HIPAA notification, notify patients and HHS
- **Roles**: CISO, Privacy Officer, Security Engineer, Legal Counsel, Clinical Operations Lead, Compliance Officer

### SCENARIO_4: NLP Service Complete Failure During Batch Processing
- **Severity**: HIGH
- **RTO**: 2 hours | **RPO**: 0 hours
- **Description**: NLP extraction service fails during large batch processing. ML ensemble crashes from memory exhaustion, rule-based fallback also fails.
- **Affected Systems**: NLP service, ML ensemble, rule-based engine, vocabulary cache, batch queue, screening pipeline
- **Key Recovery Steps**: Identify root cause, restart with increased resources, rebuild vocab cache, requeue with smaller batches, validate quality, resume
- **Roles**: ML Engineer, Platform Engineer, Clinical NLP Specialist, Clinical Operations Lead

### SCENARIO_5: Ransomware Attack on File Storage
- **Severity**: CRITICAL
- **RTO**: 12 hours | **RPO**: 24 hours
- **Description**: Ransomware encrypts clinical document storage including PDFs, lab reports, and diagnostic images for active trials.
- **Affected Systems**: Document storage, ingestion service, document viewer, backup storage, service credentials
- **Key Recovery Steps**: Isolate storage, engage forensics, assess variant, restore from immutable backup, verify integrity, rotate credentials, resume operations
- **Roles**: CISO, Security Engineer, Platform Engineer, Legal Counsel, Clinical Operations Lead, Forensics Team

### SCENARIO_6: Third-Party API (Metriport) Extended Outage
- **Severity**: HIGH
- **RTO**: 1 hour | **RPO**: 0 hours
- **Description**: Metriport health data integration API experiences 48+ hour outage. Patient medical records cannot be fetched for screening.
- **Affected Systems**: Metriport integration, FHIR import, patient data sync, screening engine, enrollment workflow
- **Key Recovery Steps**: Confirm outage, activate cached data fallback, enable manual upload, notify coordinators, queue sync jobs, re-sync on restoration
- **Roles**: Platform Engineer, Clinical Operations Lead, Trial Coordinator

### SCENARIO_7: Key Personnel Unavailability (Bus Factor)
- **Severity**: MEDIUM
- **RTO**: 24 hours | **RPO**: 0 hours
- **Description**: Sole DBA and lead ML engineer simultaneously unavailable. Critical maintenance overdue and NLP model requires urgent hotfix.
- **Affected Systems**: Database administration, NLP model management, on-call rotation, knowledge transfer documentation
- **Key Recovery Steps**: Activate cross-trained backup, access runbooks, execute maintenance per documented procedures, deploy hotfix via CI/CD, validate accuracy
- **Roles**: Engineering Manager, Backup DBA, Backup ML Engineer, QA Engineer

### SCENARIO_8: Regulatory Audit with 48-Hour Data Production Requirement
- **Severity**: HIGH
- **RTO**: 48 hours | **RPO**: 0 hours
- **Description**: FDA issues 48-hour data production request covering screening decisions, eligibility mappings, audit trails, and algorithm validation for past 6 months.
- **Affected Systems**: Audit logging, data export, screening records, algorithm validation reports, document management
- **Key Recovery Steps**: Acknowledge request, generate audit exports, compile eligibility documentation, generate validation report, legal review, submit package
- **Roles**: Compliance Officer, Platform Engineer, Clinical Operations Lead, ML Engineer, Legal Counsel, CTO

## 3. Exercise Schedule and Frequency

### Target Frequency
- Each scenario must be exercised at least once per quarter (every 90 days)
- CRITICAL severity scenarios should be exercised monthly when possible
- Exercises should rotate through different participant groups

### Exercise Types
1. **Tabletop Discussion**: Walk through scenario and recovery steps verbally (1-2 hours)
2. **Partial Simulation**: Execute some recovery steps in staging environment (2-4 hours)
3. **Full Drill**: Execute complete recovery in DR environment (4-8 hours)

### Annual Exercise Calendar
| Quarter | Primary Scenarios | Exercise Type |
|---------|------------------|---------------|
| Q1 | SCENARIO_1, SCENARIO_3 | Full Drill, Tabletop |
| Q2 | SCENARIO_2, SCENARIO_5 | Full Drill, Tabletop |
| Q3 | SCENARIO_4, SCENARIO_6 | Partial Simulation |
| Q4 | SCENARIO_7, SCENARIO_8 | Tabletop |

### Exercise Process
1. **Schedule**: Plan exercise at least 2 weeks in advance
2. **Prepare**: Distribute scenario materials to participants
3. **Conduct**: Walk through or execute recovery steps
4. **Evaluate**: Assess actual RTO/RPO against targets
5. **Document**: Record findings and action items
6. **Follow Up**: Track action item closure

## 4. Roles and Responsibilities

### BC Program Owner
- **Role**: Chief Operating Officer (COO)
- **Responsibilities**: Overall BC program accountability, budget approval, annual review

### BC Program Manager
- **Role**: VP of Engineering
- **Responsibilities**: Exercise scheduling, metrics reporting, action item tracking

### Incident Commander
- **Responsibilities**: Leads incident response, makes go/no-go decisions, coordinates teams

### Recovery Team Leads
| Role | BC Responsibility |
|------|------------------|
| DBA | Database recovery, backup validation |
| Platform Engineer | Infrastructure failover, service restoration |
| Security Engineer | Breach response, credential management |
| ML Engineer | NLP/ML service recovery, model deployment |
| Clinical Operations Lead | Stakeholder communication, workflow fallbacks |
| Privacy Officer | HIPAA breach response, notification compliance |
| Compliance Officer | Regulatory response, audit coordination |
| Legal Counsel | Legal review, regulatory communication |
| QA Engineer | Validation testing, quality verification |

### Backup Personnel
Each critical role must have at least one identified backup:
- Primary DBA -> Backup DBA (cross-trained platform engineer)
- Lead ML Engineer -> Backup ML Engineer (senior data scientist)
- Incident Commander -> Deputy IC (engineering manager)

## 5. Program Metrics

### Key Performance Indicators
| Metric | Target | Measurement |
|--------|--------|-------------|
| Exercise frequency | Quarterly per scenario | Days since last exercise |
| RTO compliance | 100% of exercises meet RTO | Actual vs. expected RTO |
| RPO compliance | 100% of exercises meet RPO | Actual vs. expected RPO |
| Action item closure | 90% within 30 days | Open vs. closed items |
| Readiness score | >= 80/100 | Weighted composite score |

### Readiness Score Components
- Exercise frequency coverage: 30%
- RTO compliance rate: 25%
- RPO compliance rate: 25%
- Action item closure rate: 20%

## 6. API Reference

All endpoints are available under `/api/v1/operations/bc/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /scenarios | List all tabletop scenarios |
| GET | /scenarios/{id} | Get scenario detail |
| POST | /exercises | Schedule an exercise |
| GET | /exercises | List exercises |
| GET | /exercises/{id} | Get exercise detail |
| PUT | /exercises/{id} | Update exercise (record results) |
| GET | /metrics | Get BC program metrics |
| POST | /validate-procedures | Validate recovery procedures |

## 7. Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-08 | COO-2 Implementation | Initial release |

This document should be reviewed quarterly and updated whenever scenarios, recovery procedures, or organizational roles change.
