# Clinical AI Deployment Readiness Blueprint (Detailed)

## Purpose
- Convert the existing Clinical AI review into a resume-safe one-on-one execution plan that can be run role-by-role and resumed after interruption.
- Keep the scope tied to OpenEHR-first migration for Ramsey Health Australia and pilot-ready safety constraints.

## Baseline Context
- Start date: Friday, 2026-02-13
- Review window: 30 days (2026-02-13 to 2026-03-14)
- Canonical chain: ingestion → ontology normalizer → KG build → narrative extraction → UMLS/OMOP grounding → Q&A
- Canonical data model assumption: OpenEHR semantics are the output contract; Meditech input is adapter-based.
- Current repo phase: analysis-only, no code edits in this document pass.

## Continuation Protocol (must run on every session start)
1. Open `tasks/04_enterprise_readiness_multi_agent_playbook.md` and confirm
   - `current_stage: implementation_gating`
   - `next_stage: implementation_gating`
   - `completed_roles: [cto, ciso, cio, vp_product, operations, clinical_ai]`
2. Open `tasks/04_enterprise_readiness_multi_agent_playbook_run.md` and verify run date/status.
3. Open `exec-review/clinical-ai-review.md` and resume marker.
4. Open this file and continue with the first unchecked `CAI-*` item or resume at `Session checkpoint`.

## Current Execution Focus
- Active role: Clinical AI closure complete (non-editing pass)
- Active item: `ROL-01` complete in `tasks/08_autonomous_execution_board.md`
- Next action: await explicit implementation approval, then execute P0/P1 closure items in order.

## Resumption Checkpoint
```
checkpoint_id: clinical-ai-pass-v2
run_id: enterprise-readiness-openehr-pilot-v1
last_item: ROL-01
last_updated_utc: 2026-02-13T00:00:00Z
status: in_progress
next_role_hint: implementation_gating
open_questions:
  - Is implementation approved for P0/P1 closure execution now?
  - What is the accepted pilot launch date after P0/P1 hardening?
```

## One-at-a-Time Role Prompt Pack (Copy/Paste)

### Role: CTO
You are the CTO conducting a production feasibility and reliability audit for a restricted pilot.
Task: return only blockers in the current code and docs that affect launch safety.
Output format: `Finding ID`, `Severity P0/P1/P2/P3`, `Likelihood`, `Evidence` (file:path:line), `Clinical impact`, `Decision`, `Owner`, `Pilot impact (go / controlled go / hold)`. 
Scope limit: no speculative architecture changes.

### Role: CISO
You are the CISO and you must identify hard-security blockers to clinical deployment.
Task: produce a hard-stop list and a parallel hardening list mapped to code evidence.
Output format: `Finding ID`, `Asset`, `Threat`, `Likelihood`, `Evidence`, `Control gap`, `Owner`, `Pilot action`. Include at least one finding mapped to auth defaults, one to secrets lifecycle, one to PHI boundary.

### Role: CIO
You are the CIO confirming enterprise readiness and OpenEHR governance.
Task: identify operational and data-governance blockers that block onboarding and support.
Output format: `Finding ID`, `Severity`, `Evidence`, `Required policy decision`, `Escalation owner`, `Pilot viability`.

### Role: VP Product
You are the VP Product translating risk into safe user outcomes.
Task: produce a workflow matrix for `77%` accuracy with confidence bands by user action.
Output format: `Workflow`, `Acceptable range`, `Block condition`, `Escalation path`, `Trust signals`, `Owner`.

### Role: Clinical AI Lead
You are the Clinical AI lead reviewing inference reliability from ingestion to answer.
Task: identify where wrongness can appear with false confidence and propose explicit control per workflow.
Output format: `Finding ID`, `Pipeline stage`, `Failure mode`, `Confidence distortion`, `Clinical risk`, `Control`, `Owner`, `Exit condition`.

### Role: SRE / Ops
You are SRE leadership for pilot operations.
Task: validate reliability posture for readiness and rollback.
Output format: `Metric`, `Target`, `Evidence`, `Gap`, `Mitigation`, `Owner`, `SLA status`.

### Orchestration rule
- Process roles in this order: CTO, CISO, CIO, VP Product, Clinical AI, Ops.
- For each role answer only within role scope, then pause for cross-role dependency reconciliation.
- After all roles, run the TODO execution matrix below.

## Execution Rules for This TODO List
- Every item is done only when evidence + verification are present.
- A role can block the next stage by marking `Status: [~] blocked` with explicit owner and date.
- All P0 and P1 items must have acceptance evidence before pilot start.
- If any P0 item is unresolved, pilot decision cannot be `go`; final must be `hold` or `controlled go` only.

## Delivery Contract
- **Evidence Mapping:** each TODO has at least one code or doc anchor.
- **Owner confirmation:** acceptance requires role owner sign-off.
- **Operational impact:** risk if skipped is described in plain clinical terms.
- **Verification:** one reproducible check command or manual artifact proof.
- **Exit condition:** gating condition must be testable.

## Execution Checkboxes (Status-First Tracking)
- CAI-P0-01: [ ] in_progress
- CAI-P0-02: [ ] in_progress
- CAI-P0-03: [ ] in_progress
- CAI-P0-04: [ ] in_progress
- CAI-P0-05: [ ] in_progress
- CAI-P0-06: [ ] in_progress
- CAI-P0-07: [ ] in_progress
- CAI-P1-08: [ ] in_progress
- CAI-P1-09: [ ] in_progress
- CAI-P1-10: [ ] in_progress
- CAI-P1-11: [ ] in_progress
- CAI-P1-12: [ ] in_progress
- CAI-P1-13: [ ] in_progress
- CAI-P1-14: [ ] in_progress
- CAI-P1-15: [ ] in_progress
- CAI-P1-16: [ ] in_progress
- CAI-P1-17: [ ] in_progress
- CAI-P1-18: [ ] in_progress
- CAI-P1-19: [ ] in_progress
- CAI-P2-20: [ ] in_progress
- CAI-P2-21: [ ] in_progress

## Detailed Clinical AI TODOs by Week

### Week 1 (Feb 13–Feb 20): Safety Gate and Trust Boundaries

#### CAI-P0-01 — Block hidden degradation in bulk ingestion
Priority: P0
Owner: Clinical AI + CTO
Evidence: `backend/app/api/clinical_agent.py:796-803`, `backend/app/api/clinical_agent.py:840-857`
Requirement: If any note fails extraction, set `note_errors`, `pipeline_status="partial"`, `can_build_graph=false` unless explicit operator waiver is present.
Decision test: no successful graph build when one or more notes fail silently.
Verification: send two-note payload (one valid, one malformed) and assert response blocks graph path.
Risk if skipped: hidden missing allergy/problem data can pass as complete KG.
Exit condition: `/clinical-agent/import` can never return complete KG status for partial extraction.

#### CAI-P0-02 — Surface graph integrity metrics in query responses
Priority: P0
Owner: Clinical AI + CTO + CIO
Evidence: `backend/app/api/clinical_agent.py:659-846`, `backend/app/api/clinical_agent.py:2750-2760`
Requirement: Query response must include `evidence_quality`, `missing_notes`, `failed_notes_count`, `fallback_used`, and `data_coverage_pct` for all pathways.
Decision test: no query result path returns complete confidence without these fields.
Verification: query patient where one upstream note failed; verify fields are present and non-empty.
Risk if skipped: clinicians cannot assess completeness and may trust partial knowledge.
Exit condition: fields are present for both success and partial extraction paths.

#### CAI-P0-03 — Make mock dependency posture safe for readiness
Priority: P0
Owner: Operations + CTO + CISO
Evidence: `backend/app/services/graph_database_service.py:177-180`, `backend/app/services/kafka_service.py:394-406`, `backend/app/api/health.py:321-360`, `backend/app/api/health.py:453-472`
Requirement: `mock_mode` must map to degraded/read-only for readiness, never to healthy in production class check.
Decision test: any synthetic critical dependency in production context sets readiness false.
Verification: run readiness check in environment with mock path enabled and record non-ready response.
Risk if skipped: production can show healthy with synthetic execution paths.
Exit condition: `/health/ready` reflects degraded dependencies.

#### CAI-P0-04 — Make dependency state explicit in Q&A payload
Priority: P0
Owner: CTO + Clinical AI
Evidence: `backend/app/api/clinical_agent.py:1960-2004`, `backend/app/services/graph_augmented_rag.py:231-236`
Requirement: add `dependency_state` with KG/doc/context/LLM status and warning flag in query responses.
Decision test: low-source paths must visibly indicate degraded provenance.
Verification: execute query with KG unavailable and confirm explicit warning in response.
Risk if skipped: low-confidence output appears as normal recommendation.
Exit condition: UI and API always show dependency provenance in query object.

#### CAI-P0-05 — Remove non-production hardcoded edges from normalizer
Priority: P0
Owner: Clinical AI + CTO
Evidence: `backend/app/api/clinical_agent.py:1459-1510`
Requirement: disable treatment hardcoded fallback except in explicit shadow mode.
Decision test: there is no production pathway that emits synthetic ontology edges without provenance.
Verification: grep for hardcoded edge fallback execution under production-like settings.
Risk if skipped: false positive treatment chains and false guideline hits.
Exit condition: hardcoded fallbacks are gated and logged with source-of-truth markers.

#### CAI-P0-06 — Validate narrative grounding before graph write
Priority: P0
Owner: Clinical AI + CISO
Evidence: `backend/app/services/narrative_extractor.py:411-441`, `backend/app/services/narrative_extractor.py:453-515`
Requirement: validate linked text fields and causal links strictly against extracted entities and provenance.
Decision test: ungrounded narrative triples are rejected before KG ingestion.
Verification: inject synthetic unsupported links and verify they are dropped with reason logging.
Risk if skipped: fabricated relationships can trigger unsafe recommendations.
Exit condition: no narrative KG link without matching entity ID and source evidence.

#### CAI-P0-07 — Propagate extraction status all the way to clients
Priority: P0
Owner: Clinical AI + CTO
Evidence: `backend/app/services/narrative_extractor.py:439-442`, `backend/app/services/narrative_extractor.py:495-500`
Requirement: output status must be `failed|partial|ok` and propagate into import, build, and query surfaces.
Decision test: parse failures are distinguishable from empty-extraction successes.
Verification: induce parser parse error; confirm status appears in all relevant endpoints.
Risk if skipped: teams act on false assumption that extraction is complete.
Exit condition: status is visible and consumed by downstream gating logic.

### Week 2 (Feb 21–Feb 28): Determinism, Evidence Quality, and UMLS/OMOP Reliability

#### CAI-P1-08 — Gate LLM answers with verifiable evidence
Priority: P1
Owner: Clinical AI + CTO + CISO
Evidence: `backend/app/api/clinical_agent.py:2621-2637`, `backend/app/api/clinical_agent.py:2711-2731`, `backend/app/api/clinical_agent.py:2750-2774`
Requirement: block high-confidence claims if KG/doc evidence is insufficient; require `answer_confidence="declined"` and follow-up guidance.
Decision test: no unsupported claim passes as full-confidence answer.
Verification: remove support evidence and run QA query with clinical statement; response must decline.
Risk if skipped: hallucinated CDS guidance may be presented as true.
Exit condition: answer confidence is evidence-bound.

#### CAI-P1-09 — Replace brittle confidence heuristics with evidence-weighted scoring
Priority: P1
Owner: Clinical AI
Evidence: `backend/app/api/clinical_agent.py:2632-2645`, `backend/app/services/hybrid_clinical_analyzer.py:628-697`
Requirement: define scoring tiers and store rationale: hard fact > structured evidence > keyword. Confidence should reflect evidence quality, not count alone.
Decision test: two scenarios with same count but different evidence type do not produce equal confidence by default.
Verification: run twin scenarios and compare confidence outputs and rationale.
Risk if skipped: overconfidence in weak text-only reasoning.
Exit condition: explainable, tiered confidence output exists.

#### CAI-P1-10 — Enforce strict provenance in narrative-to-KG linkage
Priority: P1
Owner: Clinical AI + CTO
Evidence: `backend/app/api/clinical_agent.py:986-1003`, `backend/app/api/clinical_agent.py:1083-1100`, `backend/app/services/narrative_extractor.py:453-515`
Requirement: merge step requires exact normalized IDs and denies substring-only causal merges.
Decision test: no near-match substring link can reach KG edges.
Verification: craft near-match entities and confirm no link created.
Risk if skipped: false causal graph edges that support incorrect clinical inferences.
Exit condition: provenance checks prevent weak links from persisting.

#### CAI-P1-11 — Replace document-placeholder RAG path with source-backed retrieval
Priority: P1
Owner: CTO + Clinical AI + Product
Evidence: `backend/app/services/graph_augmented_rag.py:231-236`
Requirement: remove placeholder branch, return deterministic document evidence identifiers where docs are present.
Decision test: every non-empty QA answer includes one or more `document_source_id` references.
Verification: query with supporting docs and assert response has IDs and lineage.
Risk if skipped: evidence-less QA looks authoritative but cannot be audited.
Exit condition: source IDs are mandatory in answer metadata.

#### CAI-P1-12 — Harden OMOP fallback string matching
Priority: P1
Owner: Clinical AI
Evidence: `backend/app/services/omop_hierarchy_service.py:481-513`
Requirement: raise threshold and constrain word-overlap matching to reduce false positives.
Decision test: known non-equivalents do not match under fallback mode.
Verification: execute curated negative corpus and observe precision lift.
Risk if skipped: wrong guideline mapping due to semantic drift.
Exit condition: false-positive count within approved tolerance on pilot set.

#### CAI-P1-13 — Add bounded cache policy and version invalidation for OMOP
Priority: P1
Owner: CTO + Clinical AI
Evidence: `backend/app/services/omop_hierarchy_service.py:72-75`, `backend/app/services/omop_hierarchy_service.py:233-283`, `backend/app/services/omop_hierarchy_service.py:515-520`
Requirement: limit `_concept_cache` and `_ancestor_cache` with TTL/LRU and clear on vocabulary version change.
Decision test: no unbounded memory growth in sustained batch runs.
Verification: run long synthetic batch and capture cache metrics.
Risk if skipped: memory pressure and stale ontology semantics.
Exit condition: bounded cache and explicit invalidation behavior are documented and tested.

### Week 3 (Feb 29–Mar 7): OpenEHR Path Control and Canonical Product Route

#### CAI-P1-14 — Publish Meditech-to-OpenEHR contract
Priority: P1
Owner: CIO + CTO + Platform
Evidence: `backend/app/connectors/fhir_connector.py`, `backend/app/connectors/hl7v2_connector.py`, `backend/app/connectors/ccda_connector.py`, `backend/app/connectors/csv_connector.py`
Requirement: produce contract with field mapping, identifiers, code-system translation, exception strategy, and versioning.
Decision test: every Meditech sample maps deterministically with lineage metadata.
Verification: map one production-like Meditech sample end-to-end.
Risk if skipped: silent data drift and audit failures after migration.
Exit condition: contract signed by platform + clinical governance.

#### CAI-P1-15 — Define one canonical ingestion route (delete drift)
Priority: P1
Owner: CTO + Product
Evidence: `backend/app/api/nlp.py:720-836`, `backend/app/api/clinical_agent.py:659-845`
Requirement: identify one canonical import route for pilot and mark legacy routes deprecated with warning response codes.
Decision test: runbook and UI references one route only.
Verification: run static review and query logs for route usage.
Risk if skipped: duplicate paths create inconsistent patient graphs.
Exit condition: canonical route in code comments, docs, and UI.

#### CAI-P1-16 — Add UMLS/OMOP acceptance corpus and precision checks
Priority: P1
Owner: Clinical AI + QA
Evidence: `backend/app/services/clinical_ontology_mapper.py:3-20`, `backend/app/services/omop_hierarchy_service.py:60-100`
Requirement: 50 mapped concepts and 20 negative pairs plus precision guardrails in tests.
Decision test: regression shows no precision drop beyond agreed threshold.
Verification: run test suite with threshold gates in CI.
Risk if skipped: model confidence with weak clinical mappings persists.
Exit condition: precision/recall thresholds are enforced with failing thresholds.

#### CAI-P1-17 — Build OpenEHR reconciliation and rollback runbook
Priority: P1
Owner: Operations + CIO + CTO
Evidence: `docs/operations/disaster_recovery_plan.md`, connector docs under `backend/app/connectors/`
Requirement: define drift checks, reconciliation cadence, and rollback switch within pilot launch package.
Decision test: dry-run reconciliation and rollback drill passes before day0.
Verification: execute one reconciliation drill on sample payload.
Risk if skipped: unrecoverable sync divergence after first real load.
Exit condition: dry-run and rollback evidence attached to the runbook.

### Week 4 (Mar 8–Mar 14): Clinical UX and Governed Expansion

#### CAI-P1-18 — Enforce trust UX and unsafe-action gating
Priority: P1
Owner: VP Product + Clinical AI + Frontend
Evidence: `frontend/src/app/nlp/page.tsx`, `frontend/src/app/clinical/page.tsx`
Requirement: confidence band and unsafe-action disablement for low-confidence outputs; clear alternative action path.
Decision test: no clinical recommendation can be acted on directly when dependency confidence is low.
Verification: run UI manual test with low-confidence query/answer scenario.
Risk if skipped: unsafe autonomous action path remains available to clinician.
Exit condition: action gating is enforced by policy + UI warnings.

#### CAI-P1-19 — Implement structured feedback loop for model corrections
Priority: P1
Owner: Product + Clinical AI
Evidence: `backend/app/api/clinical_agent.py`
Requirement: capture feedback events with context (`query`, `expected`, `actual`, `clinician_decision`).
Decision test: feedback can be replayed for audit and model tuning.
Verification: create one accept/disagree event and verify persistence format.
Risk if skipped: no safety learning path and no governance evidence.
Exit condition: review board has weekly feedback reports.

#### CAI-P2-20 — Add confidence-bound safety tests
Priority: P2
Owner: CTO + QA
Evidence: `backend/tests/`
Requirement: tests must block unsafe suggestions when confidence below threshold classes.
Decision test: low-confidence classification never emits risky action guidance.
Verification: add/execute threshold assertions in CI.
Risk if skipped: regression can reintroduce unsafe low-confidence outputs.
Exit condition: CI gate fails if unsafe low-confidence behavior appears.

#### CAI-P2-21 — Re-run clinical AI review and produce monthly closure
Priority: P2
Owner: Clinical AI + CIO + CISO + CTO
Evidence: `exec-review/clinical-ai-review.md`, `tasks/04_enterprise_readiness_multi_agent_playbook.md`, `tasks/04_enterprise_readiness_multi_agent_playbook_run.md`
Requirement: updated clinical-ai review with explicit signoff status and month-end decision posture.
Decision test: review reflects all changes and includes explicit pass/blocker matrix.
Verification: final doc has date stamp, findings, and go/no-go by severity.
Risk if skipped: leadership loses continuity and decision auditability.
Exit condition: clinical-ai review fully updated and linked in playbook.

## Cross-Role Accountability Matrix
- CTO: CAI-P0-03, CAI-P0-04, CAI-P0-05, CAI-P1-09, CAI-P1-11, CAI-P1-13, CAI-P1-15, CAI-P1-17, CAI-P2-20, CAI-P2-21
- CISO: CAI-P0-03, CAI-P0-06, CAI-P1-08, CAI-P2-21
- CIO: CAI-P1-14, CAI-P1-15, CAI-P1-17, CAI-P2-21
- VP Product: CAI-P1-18, CAI-P1-19
- Clinical AI: CAI-P0-01, CAI-P0-02, CAI-P0-06, CAI-P0-07, CAI-P1-09, CAI-P1-10, CAI-P1-11, CAI-P1-12, CAI-P1-16, CAI-P1-18, CAI-P1-19, CAI-P2-21
- Operations/SRE: CAI-P0-03, CAI-P1-17, CAI-P2-21
- QA/Validation: CAI-P1-16, CAI-P2-20

## Decision Log Template (copy for each session)
```
Session ID:
Date:
Roles run (in order):
P0 status:
P1 status:
Blockers introduced:
Blocker owner + mitigation due date:
Pilot decision posture for next week:
```

## Monthly Exit Criteria (all must be true before March 14)
1. No dependency marked healthy when critical services are mocked in production-class posture.
2. Every extraction or parsing error has explicit user-visible effect in query and KG state.
3. Q&A and CDS outputs always include evidence linkage and confidence rationale.
4. Only one ingestion route is canonical for pilot onboarding.
5. UMLS/OMOP regression corpus with precision guardrails is green in CI.
6. One reconciliation + rollback drill is executed and documented.

## Session Notes (append-only)
- 2026-02-13: Session start: commencing Clinical AI pass using role order in this document (CTO first), with initial focus on P0 safety gate items CAI-P0-01 through CAI-P0-07.
- 2026-02-13: Clinical AI detailed TODO list reworked into role-ordered, resume-safe structure with explicit per-item validation criteria.
