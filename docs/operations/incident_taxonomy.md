# Production Incident Taxonomy and Severity Rubric

**Document ID**: OPS-P1-032
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CIO + Operations + Clinical AI
**Classification**: Internal — Operational

## Purpose

Define a structured taxonomy of incident types specific to the clinical AI platform, with severity classification rubrics tied to response SLAs.

## Incident Categories

### Category 1: Clinical Safety (CS)

Incidents affecting clinical decision accuracy or patient safety.

| ID | Incident Type | Severity | Response SLA | Example |
|---|---|---|---|---|
| CS-01 | Incorrect drug interaction result | SEV-1 | 15 min | System misses known contraindication |
| CS-02 | Wrong clinical fact domain assignment | SEV-2 | 30 min | Condition mapped as measurement |
| CS-03 | NLP extraction producing false positives at scale | SEV-2 | 30 min | Negated conditions extracted as present |
| CS-04 | Confidence scores miscalibrated | SEV-2 | 1 hour | Low-quality results shown as high confidence |
| CS-05 | Clinical agent returning ungrounded assertions | SEV-1 | 15 min | Statements without source document evidence |
| CS-06 | Calculator producing out-of-range results | SEV-2 | 30 min | CHA2DS2-VASc returning impossible score |

### Category 2: Data Integrity (DI)

Incidents affecting data correctness, completeness, or lineage.

| ID | Incident Type | Severity | Response SLA | Example |
|---|---|---|---|---|
| DI-01 | Data loss during import | SEV-1 | 15 min | Entries silently dropped without lineage |
| DI-02 | Duplicate clinical facts created | SEV-2 | 30 min | Same entry imported twice |
| DI-03 | Lineage chain broken or incomplete | SEV-3 | 2 hours | Missing transformation steps |
| DI-04 | Code system mapping corruption | SEV-2 | 30 min | SNOMED codes mapped to wrong concepts |
| DI-05 | KG inconsistency (orphaned nodes) | SEV-3 | 2 hours | Nodes without patient edges |
| DI-06 | Cross-patient data contamination | SEV-1 | 15 min | Patient A data visible to Patient B |

### Category 3: Security and Privacy (SP)

Incidents affecting PHI protection, access controls, or audit integrity.

| ID | Incident Type | Severity | Response SLA | Example |
|---|---|---|---|---|
| SP-01 | PHI exposure in logs | SEV-1 | 15 min | Patient names in application logs |
| SP-02 | Unauthorized data access | SEV-1 | 15 min | User accessing another tenant's data |
| SP-03 | Authentication bypass | SEV-1 | 15 min | Endpoint accessible without auth |
| SP-04 | Audit log gap | SEV-2 | 30 min | PHI access not recorded |
| SP-05 | Mock mode in production | SEV-1 | 15 min | Dependency mock active in prod |
| SP-06 | Credential exposure | SEV-1 | 15 min | API key in public repository |

### Category 4: Service Availability (SA)

Incidents affecting platform uptime and responsiveness.

| ID | Incident Type | Severity | Response SLA | Example |
|---|---|---|---|---|
| SA-01 | Complete service outage | SEV-1 | 15 min | All API endpoints returning 5xx |
| SA-02 | Critical dependency down | SEV-2 | 30 min | PostgreSQL or Redis unavailable |
| SA-03 | Performance degradation | SEV-3 | 2 hours | P95 latency >10x baseline |
| SA-04 | Worker queue backup | SEV-3 | 2 hours | Queue depth exceeding SLO |
| SA-05 | Partial feature outage | SEV-3 | 2 hours | Single endpoint failing |

### Category 5: Interoperability (IO)

Incidents affecting external data exchange.

| ID | Incident Type | Severity | Response SLA | Example |
|---|---|---|---|---|
| IO-01 | Contract violation on import | SEV-2 | 30 min | Composition fails contract validation |
| IO-02 | Export producing invalid format | SEV-2 | 30 min | FHIR/OpenEHR export fails profile validation |
| IO-03 | Connector authentication failure | SEV-3 | 2 hours | Source system rejecting credentials |
| IO-04 | Data format change without notice | SEV-2 | 30 min | Source sending unexpected schema |

## Severity Rubric

### SEV-1 Criteria (any one of)
- Patient safety could be compromised
- PHI exposed to unauthorized parties
- Complete service unavailable to all users
- Cross-patient data contamination
- Regulatory notification may be required

### SEV-2 Criteria (any one of)
- Clinical data accuracy affected for a subset of records
- Major feature degraded for >10% of users
- Data integrity issue requiring investigation
- Security control partially bypassed

### SEV-3 Criteria (any one of)
- Non-critical feature affected
- Performance impact within tolerance
- Issue has workaround
- No clinical or security impact

### SEV-4 Criteria
- Cosmetic or minor functional issue
- No user impact
- Fix can wait for next release

## Response SLA Summary

| Severity | Acknowledge | Investigation Start | Resolution Target | Postmortem |
|---|---|---|---|---|
| SEV-1 | 15 min | 30 min | 4 hours | Within 48 hours |
| SEV-2 | 30 min | 1 hour | 8 hours | Within 1 week |
| SEV-3 | 2 hours | 4 hours | 24 hours | Optional |
| SEV-4 | 8 hours | Next sprint | 72 hours | Not required |
