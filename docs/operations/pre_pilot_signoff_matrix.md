# Pre-Pilot Signoff Matrix

**Document ID**: OPS-P0-028
**Version**: 2.0
**Effective Date**: 2026-02-16
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

| Gate | Evidence Artifact | Backing P0 | Status |
|---|---|---|---|
| Authentication enforced in production | `backend/app/core/config.py` — service refuses startup if `AUTH_ENABLED=false` outside dev; `backend/tests/test_auth_enforcement.py` | P0-009 | PASS |
| Credential defaults removed from deploy templates | `docker-compose.yml`, `.env.example` — no hardcoded/placeholder credentials in deploy path | P0-010 | PASS |
| Redis authentication and network isolation | `docker-compose.yml` `requirepass` config, `backend/app/core/queue.py` auth params | P0-011 | PASS |
| PHI encryption at rest | PostgreSQL/Neo4j storage encryption documented in deployment manifests | P0-012 | PASS |
| TLS for all clinical data transport | `nginx/nginx.conf` TLS termination, plaintext disabled in production | P0-013 | PASS |
| Audit coverage for worker PHI operations | `backend/app/middleware/audit_middleware.py`, worker audit events in `backend/app/workers/` | P0-014 | PASS |
| Audit tags for graph data access | `backend/app/services/graph_database_service.py` user/tenant/patient context in events | P0-015 | PASS |
| Tenant boundary enforcement at query boundaries | `backend/app/core/tenant.py`, `backend/app/security/rbac_service.py` cross-tenant blocks | P0-016 | PASS |
| External model PHI policy gate | Model/agent service config blocks unapproved providers | P0-017 | PASS |
| Drug safety coverage meets threshold | `backend/app/services/drug_safety.py` coverage report + unknown-pair warning | P1-013 | PASS |
| Confidence policy active for all workflows | `backend/app/services/confidence_policy_service.py`, `backend/app/schemas/confidence_policy.py` | P0-021, P1-003 | PASS |
| Degraded mode blocks unsafe actions | `frontend/src/components/DegradedBanner.tsx`, dependency simulation test | P0-024 | PASS |

### Clinical AI Safety Gates

| Gate | Evidence Artifact | Backing P0 | Status |
|---|---|---|---|
| Dependency state surfaced in clinical responses | `backend/app/api/clinical_agent.py` KG/doc/LLM availability flags | P0-004 | PASS |
| Graph build blocked on extraction failures | Partial extraction cannot produce "complete" pipeline status | P0-005 | PASS |
| Extraction status propagated across pipeline | `narrative_extractor.py` → `clinical_agent.py` ok/partial/failed status | P0-006 | PASS |
| Narrative grounding enforced before KG writes | Ungrounded links rejected with reason code | P0-007 | PASS |
| Hardcoded ontology fallback disabled | Synthetic edges only in explicit shadow/test mode | P0-008 | PASS |
| Evidence-bound confidence with decline behavior | Insufficient evidence returns decline + escalation path | P0-022 | PASS |
| Source provenance required for non-empty answers | No evidence-less answer accepted in pilot mode | P0-023 | PASS |
| Canonical ingestion-to-Q&A route defined | Non-canonical routes marked non-pilot/deprecated | P0-020 | PASS |

### Quality Gates

| Gate | Evidence Artifact | Backing P0/P1 | Status |
|---|---|---|---|
| Backend test suite passing | `make test` — test suite with coverage (run at commit `4e78c69`) | — | PASS |
| Frontend build clean | `npm run build` + `npm run lint` — verified clean at commit `960ab4c` | — | PASS |
| OpenEHR replay validation passing | `backend/tests/test_meditech_replay_validation.py`, canonical contract | P0-018 | PASS |
| OMOP mapping acceptance corpus passing | `backend/tests/test_omop_acceptance.py` CI threshold gate | P1-010 | PASS |
| NLP extraction precision/recall baseline recorded | Ranking scores labeled (not calibrated probability); benchmark captured | P1-015 | PASS |

### Operational Gates

| Gate | Evidence Artifact | Backing P0 | Status |
|---|---|---|---|
| Escalation matrix published | `docs/operations/incident_escalation_matrix.md` v2.0 with HIPAA clock | P0-025 | PASS (doc published) |
| Escalation drill executed | Tabletop exercise with paging + response-clock evidence | P0-025-A/B | **BLOCKED — needs live drill** |
| Backup restore drill completed | `docs/operations/backup_restore_drill.md` procedure ready | P0-026 | **BLOCKED — needs infrastructure execution** |
| Failover simulation completed | `docs/operations/failover_simulation.md` procedure ready | P0-027 | **BLOCKED — needs infrastructure execution** |
| On-call rotation staffed | Rotation calendar in escalation matrix | P0-025 | **BLOCKED — needs named staff** |
| Monitoring dashboards active | Dashboard configuration | — | **BLOCKED — needs deployment** |

### Interoperability Gates

| Gate | Evidence Artifact | Backing P0 | Status |
|---|---|---|---|
| Meditech-to-OpenEHR canonical contract validated | `backend/app/connectors/` contract + lineage integration | P0-018 | PASS |
| OpenEHR dry-run reconciliation completed | `scripts/p0_019_evidence_capture.py` + `docs/evidence/p0-019/` | P0-019-A | **BLOCKED — needs live backend** |
| OpenEHR rollback drill completed | Evidence script includes rollback + residual verification | P0-019-B | **BLOCKED — needs live backend** |
| FHIR conformance baseline recorded | FHIR import/export services implemented | — | PASS (baseline) |

## Gate Summary

| Category | Total Gates | PASS | BLOCKED |
|---|---|---|---|
| Safety | 12 | 12 | 0 |
| Clinical AI Safety | 8 | 8 | 0 |
| Quality | 5 | 5 | 0 |
| Operational | 6 | 1 | 5 |
| Interoperability | 4 | 2 | 2 |
| **Total** | **35** | **28** | **7** |

## Unresolved Risks

| Risk ID | Description | Severity | Owner | Mitigation | Accepted By | Expiry |
|---|---|---|---|---|---|---|
| R-006 | OpenEHR reconciliation not yet validated against live data | High | CIO + Ops | Evidence script ready (`scripts/p0_019_evidence_capture.py`); execute against staging | | 2026-02-27 |
| R-007 | Backup restore and failover drills not yet executed | High | Ops | Procedures fully documented; execute against staging infrastructure | | 2026-02-27 |
| R-008 | Escalation drill not yet executed with real paging | Medium | CIO + Ops | Escalation matrix published with HIPAA clock; tabletop exercise needed | | 2026-02-27 |
| R-009 | On-call rotation requires named staff assignment | Medium | Ops | Rotation template in escalation matrix; assign real names | | 2026-02-27 |

## Conditional Approvals

If any signoff is conditional, document the conditions here:

| Role | Condition | Resolution Deadline |
|---|---|---|
| Operations Lead | Complete backup restore drill (P0-026) and failover simulation (P0-027) | 2026-02-27 |
| CIO | Execute OpenEHR reconciliation against live staging data (P0-019-A/B) | 2026-02-27 |
| CIO | Execute escalation drill with paging roster (P0-025-A/B) | 2026-02-27 |

## Rollback Decision Criteria (P0-028-B)

Explicit triggers for rolling back during pilot. Any single trigger is sufficient for a rollback decision.

### Automatic Rollback Triggers (no human approval needed)

| Trigger | Threshold | Detection Method |
|---|---|---|
| Patient safety event | Any confirmed wrong clinical result acted upon | Incident report + clinical safety review |
| PHI breach confirmed | Any confirmed unauthorized PHI disclosure | Security incident assessment |
| Data corruption | Reconciliation `match: false` on >1 patient | `POST /api/v1/openehr/reconcile/{patient_id}` |
| Complete service outage | >30 min unrecoverable outage during clinical hours | Health check + PagerDuty |

### Conditional Rollback Triggers (Incident Commander decides)

| Trigger | Threshold | Escalation Path |
|---|---|---|
| Partial outage | >2 hours for critical clinical pathway | Operations Lead → Incident Commander |
| NLP accuracy degradation | Confidence scores drop >20% from baseline | Clinical AI Lead → CTO |
| Repeated data integrity failures | >3 reconciliation mismatches in 24 hours | Data Integrity Lead → CTO |
| User safety complaints | >2 clinician-reported safety concerns in 7 days | VP Product → Clinical Safety Lead |

### Rollback Authority

| Decision Level | Who Can Call It | Notification Required |
|---|---|---|
| Emergency rollback (automatic triggers) | Any Incident Commander, CISO, Clinical Safety Lead | Notify CTO + CIO within 15 min |
| Conditional rollback | Incident Commander with CTO approval | Notify all signoff stakeholders within 1 hour |
| Planned rollback (e.g., end of pilot phase) | Program Lead with majority stakeholder agreement | 24-hour advance notice |

### Rollback Execution Steps

1. Disable new patient onboarding (`openehr_import_enabled: false`)
2. Quarantine affected data pipeline
3. Execute batch rollback via `POST /api/v1/openehr/rollback` for affected patients
4. Verify rollback via reconciliation endpoint (expect "No facts found")
5. Notify affected clinical users via escalation matrix communication templates
6. Preserve all evidence for post-incident review
7. Do not re-enable until root cause identified and fix verified via dry-run

## Final Determination

| Decision | Date | Notes |
|---|---|---|
| [ ] GO — Pilot approved | | All 35 gates PASS, all risks resolved |
| [ ] CONDITIONAL GO — Approved with conditions above | | 28/35 gates PASS, 7 operational gates require live execution |
| [ ] NO-GO — Blockers must be resolved | | |

**Program Lead Signature**: _________________ **Date**: _________
