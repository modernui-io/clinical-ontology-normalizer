# Pre-Pilot Signoff Matrix

**Document ID**: OPS-P0-028
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Program Lead
**Classification**: Internal — Executive

## Purpose

Formal signoff artifact for pilot readiness. All named stakeholders must review and sign before the platform enters live clinical use. This document captures both approval and any accepted residual risks.

## Signoff Table

| Role | Name | Area of Responsibility | Status | Date | Signature |
|---|---|---|---|---|---|
| CTO | | Architecture, code quality, performance, scalability | PENDING | | |
| CISO | | Security posture, PHI protection, access controls, audit | PENDING | | |
| CIO | | Operations readiness, staffing, vendor contracts, compliance | PENDING | | |
| Clinical AI Lead | | NLP accuracy, confidence policy, clinical safety | PENDING | | |
| VP Product | | UX safety, degraded mode, pilot scope, user training | PENDING | | |
| Operations Lead | | Infrastructure, monitoring, on-call, DR readiness | PENDING | | |
| Compliance Officer | | Regulatory alignment, consent, data residency | PENDING | | |
| QA Lead | | Test coverage, regression suite, acceptance criteria | PENDING | | |

## Readiness Gates

Each gate must be marked PASS before signoff is valid.

### Safety Gates

| Gate | Evidence | Status |
|---|---|---|
| Authentication enforced in production | Config test + deployment verification | |
| PHI encryption at rest | PostgreSQL/Neo4j encryption documentation | |
| TLS for all clinical data transport | nginx config + cert verification | |
| Drug safety coverage meets threshold | Drug safety coverage report | |
| Confidence policy active for all workflows | Policy config + test evidence | |
| Degraded mode blocks unsafe actions | Frontend test + dependency simulation | |

### Quality Gates

| Gate | Evidence | Status |
|---|---|---|
| Backend test suite passing (>95%) | CI report | |
| Frontend build clean | CI report | |
| OpenEHR replay validation passing | `test_meditech_replay_validation.py` results | |
| OMOP mapping acceptance corpus passing | `test_omop_acceptance.py` results | |
| NLP extraction precision/recall baseline recorded | Benchmark report | |

### Operational Gates

| Gate | Evidence | Status |
|---|---|---|
| Backup restore drill completed | `backup_restore_drill.md` evidence record | |
| Failover simulation completed | `failover_simulation.md` evidence record | |
| Escalation matrix published | `incident_escalation_matrix.md` | |
| On-call rotation staffed | Rotation calendar | |
| Monitoring dashboards active | Dashboard screenshots | |

### Interoperability Gates

| Gate | Evidence | Status |
|---|---|---|
| OpenEHR contract validated | Contract signature verification | |
| Meditech reconciliation completed | `openehr_reconciliation_rollback.md` evidence | |
| FHIR conformance baseline recorded | Conformance report | |

## Unresolved Risks

| Risk ID | Description | Severity | Owner | Mitigation | Accepted By | Expiry |
|---|---|---|---|---|---|---|
| | | | | | | |

## Conditional Approvals

If any signoff is conditional, document the conditions here:

| Role | Condition | Resolution Deadline |
|---|---|---|
| | | |

## Final Determination

| Decision | Date | Notes |
|---|---|---|
| [ ] GO — Pilot approved | | |
| [ ] CONDITIONAL GO — Approved with conditions above | | |
| [ ] NO-GO — Blockers must be resolved | | |

**Program Lead Signature**: _________________ **Date**: _________
