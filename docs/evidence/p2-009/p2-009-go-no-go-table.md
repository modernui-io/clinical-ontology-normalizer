# P2-009 Go/No-Go Decision Table

## Metadata

| Field | Value |
|-------|-------|
| Document | Go/No-Go Decision Table |
| ROL ID | ROL-09 |
| Assessment Date | 2026-02-17 |
| Period Under Review | 2026-02-01 through 2026-02-17 |
| Overall Decision | **CONDITIONAL GO** (pilot) / **HOLD** (broad rollout) |
| Next Reassessment | 2026-03-17 |

---

## Decision Table

### Dimension 1: Safety

| Field | Detail |
|-------|--------|
| **Criteria** | All clinical safety controls enforced: confidence-to-action gating, decline behavior on unsupported claims, evidence-bound provenance, extraction status propagation, narrative grounding, ontology edge control |
| **Evidence Status** | P0-004 through P0-008, P0-021 through P0-023 — all PASS. Confidence policy enforced per risk tier. 77% accuracy class gated with explicit decline. Precision guardrail corpus: 79 tests, zero false-positive tolerance. |
| **Evidence Freshness** | 2026-02-16 (signoff) / 2026-02-17 (guardrail extension) |
| **Decision Owner** | Clinical AI Lead (clinical-ai-exec) |
| **Result** | **GO** |
| **Residual Risks** | 77% accuracy class remains gated — acceptable for supervised pilot. Precision corpus covers medication, condition, procedure, measurement domains with per-domain thresholds. |
| **Next Action** | Monitor precision drift via `test_umls_omop_precision_guardrails.py` in CI. Reassess accuracy class gates at 30-day review (2026-03-17). |

---

### Dimension 2: Uptime / Resilience

| Field | Detail |
|-------|--------|
| **Criteria** | Dependency health fail-closed in production; backup restore drill executed with RTO < 60s; failover drill executed with MTTR < 60s; worker liveness checks operational; restart policies consistent |
| **Evidence Status** | P0-001/002/003 fail-closed (PASS). P0-026 PG restore RTO: 30.42s (PASS). P0-027 PG failover MTTR: 15.2s (PASS). P1-021/022/025 health class split, worker liveness, restart policy (PASS). Neo4j restore, Redis failover, cascade simulation deferred to staging. |
| **Evidence Freshness** | 2026-02-16 (drill execution) |
| **Decision Owner** | Ops Lead (ops-exec) |
| **Result** | **CONDITIONAL GO** |
| **Residual Risks** | Redis failover untested on Docker. Neo4j running in mock_mode (non-critical dependency). Cascade simulation not yet executed. All deferred to staging provisioning. |
| **Next Action** | Execute Redis containerized failover, Neo4j restore, and cascade simulation when staging provisioned. Escalate if staging not ready by 2026-03-02. |

---

### Dimension 3: Data Quality

| Field | Detail |
|-------|--------|
| **Criteria** | OMOP mapping precision meets domain thresholds; extraction status propagated; KG completeness scoring active; data lineage end-to-end; drift detection thresholds defined |
| **Evidence Status** | P2-008 precision guardrails: 79 tests, 11 classes. Domain thresholds: medication 0.90, condition 0.80, procedure 0.75, measurement 0.80. P0-006 extraction status propagation (PASS). P2-006 KG completeness scoring (PASS). P2-010 drift detection (PASS). P2-022 data lineage (PASS). |
| **Evidence Freshness** | 2026-02-17 (guardrail corpus extension) |
| **Decision Owner** | CTO (cto-exec) |
| **Result** | **GO** |
| **Residual Risks** | Drift detection thresholds defined but not yet triggered in production (expected — no production traffic). Precision corpus covers known ambiguity classes; unknown classes may emerge in production. |
| **Next Action** | Monitor drift alerts in first 30 days of pilot. Expand precision corpus if new ambiguity classes discovered. |

---

### Dimension 4: Clinical Governance

| Field | Detail |
|-------|--------|
| **Criteria** | Pilot accuracy policy approved; confidence calibration reporting active; clinician feedback capture pipeline operational; uncertainty taxonomy published; answer explanation templates deployed |
| **Evidence Status** | P1-016 pilot accuracy policy (PASS). P3-005 calibration plots (PASS). P2-009 feedback capture (PASS). P2-007 uncertainty taxonomy (PASS). P3-004 explanation templates (PASS). P1-032 incident taxonomy for clinical AI (PASS). P1-033 risk acceptance workflow (PASS). |
| **Evidence Freshness** | 2026-02-16 (all items closed) |
| **Decision Owner** | Clinical AI Lead (clinical-ai-exec) + CIO (cio-exec) |
| **Result** | **GO** |
| **Residual Risks** | Calibration data will only be meaningful after sufficient pilot volume. Feedback pipeline requires clinical reviewers to be assigned. |
| **Next Action** | Assign clinical reviewers for weekly feedback review. Generate first calibration report after 2 weeks of pilot data. |

---

### Dimension 5: Compliance

| Field | Detail |
|-------|--------|
| **Criteria** | Authentication enforced in non-dev; encryption-at-rest for PHI stores; TLS for ingress; audit coverage for worker operations; tenant boundary checks; retention policy active; purpose-of-use tagging; threat model cadence defined |
| **Evidence Status** | P0-009 through P0-017 all PASS (auth, secrets, encryption, TLS, audit, tenant boundaries). P1-027 AU residency/consent (PASS). P1-028 retention policy (PASS). P1-029 purpose-of-use tagging (PASS). P1-034 LLM provider contract gate (PASS). P2-026 threat model cadence (PASS). P2-024 RBAC test suite (PASS). P2-025 sensitive defaults policy (PASS). |
| **Evidence Freshness** | 2026-02-16 (security controls) |
| **Decision Owner** | CISO (ciso-exec) |
| **Result** | **CONDITIONAL GO** |
| **Residual Risks** | Neo4j encryption-at-rest deferred (mock_mode). Kafka HA not yet established. Encryption verified on PG only. |
| **Next Action** | Verify Neo4j encryption when staging provisioned. Execute Kafka HA strategy per P2-014 decision. Quarterly threat model update per P2-026 cadence. |

---

### Dimension 6: Infrastructure Readiness

| Field | Detail |
|-------|--------|
| **Criteria** | Staging environment provisioned; all dependencies containerized for drill execution; OpenEHR round-trip confirmed on staging; backup automation operational; SLO dashboard active |
| **Evidence Status** | P2-016 backup automation (PASS — localhost). P2-017 SLO dashboard (PASS). P2-014 Kafka HA strategy (PASS — decision only). P2-015 Redis separation (PASS — design). Staging provisioning: NOT COMPLETE. 5 staging conditions from P0-028 signoff remain blocked_by_infrastructure. |
| **Evidence Freshness** | 2026-02-16 (signoff conditions documented) |
| **Decision Owner** | CTO (cto-exec) + CIO (cio-exec) |
| **Result** | **HOLD** (for staging/broad rollout) |
| **Residual Risks** | No staging environment exists. Cannot execute Redis failover, Neo4j restore, cascade simulation, or OpenEHR staging round-trip. Broad rollout cannot proceed without staging evidence. |
| **Next Action** | Provision staging infrastructure. Escalation trigger: 2026-03-02 (CTO + CIO decision required). Execute all 5 staging drills once provisioned. |

---

## Decision Summary

| Dimension | Result | Decision Owner | Conditions |
|-----------|--------|----------------|------------|
| Safety | **GO** | Clinical AI Lead | Monitor precision drift |
| Uptime / Resilience | **CONDITIONAL GO** | Ops Lead | 3 staging drills required |
| Data Quality | **GO** | CTO | Monitor drift alerts |
| Clinical Governance | **GO** | Clinical AI Lead + CIO | Assign clinical reviewers |
| Compliance | **CONDITIONAL GO** | CISO | Neo4j/Kafka encryption verification |
| Infra Readiness | **HOLD** | CTO + CIO | Staging provisioning required |

### Aggregate Decision

| Scope | Decision | Basis |
|-------|----------|-------|
| Pilot (localhost) | **CONDITIONAL GO** | 4/6 GO, 2/6 CONDITIONAL GO, 0/6 HOLD for pilot scope |
| Staging | **BLOCKED** | Infra Readiness = HOLD; 5 staging conditions unmet |
| Broad Rollout | **HOLD** | Cannot proceed until staging evidence captured |

### Escalation Timeline

| Date | Action | Owner |
|------|--------|-------|
| 2026-03-02 | Staging infra escalation if not provisioned | CTO + CIO |
| 2026-03-09 | Executive sponsor escalation if no CTO/CIO resolution | Program Lead |
| 2026-03-16 | Signoff expiry — re-signoff required | All 6 role leads |
| 2026-03-17 | 30-day closure review | Program Lead |

---

*Generated: 2026-02-17T00:00:00Z | Operator: autonomous-agent | Next reassessment: 2026-03-17*
