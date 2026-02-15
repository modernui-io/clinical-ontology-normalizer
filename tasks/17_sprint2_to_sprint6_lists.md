# Sprint 2-6 Execution Lists

Source
- `tasks/09_master_change_backlog_p0_p4.md`

## Sprint-2
- Task count: 17

1. P0-001-B | Owner: `CTO + Ops` | Due: `2026-03-13` | Fail closed in readiness when Neo4j is unavailable.
2. P0-002-B | Owner: `CTO + Ops` | Due: `2026-03-13` | Fail closed in readiness when Kafka is unavailable for required flows.
3. P0-003-B | Owner: `CTO + CISO` | Due: `2026-03-13` | Remove "mock_mode treated as connected" semantics from production posture checks.
4. P0-004-B | Owner: `Clinical AI + CTO` | Due: `2026-03-13` | Surface `dependency_state` in all clinical query responses.
5. P0-005-B | Owner: `Clinical AI` | Due: `2026-03-13` | Block graph build when ingestion has note-level extraction failures.
6. P0-006-B | Owner: `Clinical AI` | Due: `2026-03-13` | Propagate extraction status (`ok|partial|failed`) across import, KG build, and Q&A.
7. P0-007-B | Owner: `Clinical AI + CISO` | Due: `2026-03-13` | Enforce strict narrative grounding prior to KG writes.
8. P0-008-B | Owner: `Clinical AI + CTO` | Due: `2026-03-13` | Disable hardcoded ontology edge fallback in production pathways.
9. P0-009-B | Owner: `CISO` | Due: `2026-03-13` | Enforce authentication by default in non-dev environments.
10. P0-010-B | Owner: `CISO + Platform` | Due: `2026-03-13` | Remove insecure credential defaults from deployment templates.
11. P0-011-B | Owner: `CISO + Ops` | Due: `2026-03-13` | Require Redis authentication and restricted network exposure.
12. P0-012-B | Owner: `CISO + Platform` | Due: `2026-03-13` | Enforce encryption-at-rest for PHI stores.
13. P0-013-B | Owner: `CISO + Ops` | Due: `2026-03-13` | Enforce TLS for ingress and service links handling PHI.
14. P0-014-B | Owner: `CISO + Ops` | Due: `2026-03-13` | Add audit coverage for worker-based PHI operations.
15. P0-015-B | Owner: `CISO + Clinical AI` | Due: `2026-03-13` | Add audit tags for graph data access and query provenance.
16. P0-016-B | Owner: `CISO + Platform` | Due: `2026-03-13` | Enforce tenant/org boundary checks at query boundaries.
17. P0-017-B | Owner: `CISO + Clinical AI` | Due: `2026-03-13` | Add explicit policy gate for external model routes handling PHI.

## Sprint-3
- Task count: 39

1. P0-001-C | Owner: `CTO + Ops` | Due: `2026-03-27` | Fail closed in readiness when Neo4j is unavailable.
2. P0-002-C | Owner: `CTO + Ops` | Due: `2026-03-27` | Fail closed in readiness when Kafka is unavailable for required flows.
3. P0-003-C | Owner: `CTO + CISO` | Due: `2026-03-27` | Remove "mock_mode treated as connected" semantics from production posture checks.
4. P0-004-C | Owner: `Clinical AI + CTO` | Due: `2026-03-27` | Surface `dependency_state` in all clinical query responses.
5. P0-005-C | Owner: `Clinical AI` | Due: `2026-03-27` | Block graph build when ingestion has note-level extraction failures.
6. P0-006-C | Owner: `Clinical AI` | Due: `2026-03-27` | Propagate extraction status (`ok|partial|failed`) across import, KG build, and Q&A.
7. P0-007-C | Owner: `Clinical AI + CISO` | Due: `2026-03-27` | Enforce strict narrative grounding prior to KG writes.
8. P0-008-C | Owner: `Clinical AI + CTO` | Due: `2026-03-27` | Disable hardcoded ontology edge fallback in production pathways.
9. P0-009-C | Owner: `CISO` | Due: `2026-03-27` | Enforce authentication by default in non-dev environments.
10. P0-010-C | Owner: `CISO + Platform` | Due: `2026-03-27` | Remove insecure credential defaults from deployment templates.
11. P0-011-C | Owner: `CISO + Ops` | Due: `2026-03-27` | Require Redis authentication and restricted network exposure.
12. P0-012-C | Owner: `CISO + Platform` | Due: `2026-03-27` | Enforce encryption-at-rest for PHI stores.
13. P0-013-C | Owner: `CISO + Ops` | Due: `2026-03-27` | Enforce TLS for ingress and service links handling PHI.
14. P0-014-C | Owner: `CISO + Ops` | Due: `2026-03-27` | Add audit coverage for worker-based PHI operations.
15. P0-015-C | Owner: `CISO + Clinical AI` | Due: `2026-03-27` | Add audit tags for graph data access and query provenance.
16. P0-016-C | Owner: `CISO + Platform` | Due: `2026-03-27` | Enforce tenant/org boundary checks at query boundaries.
17. P0-017-C | Owner: `CISO + Clinical AI` | Due: `2026-03-27` | Add explicit policy gate for external model routes handling PHI.
18. P0-018-B | Owner: `CIO + CTO` | Due: `2026-03-27` | Publish and approve canonical Meditech-to-OpenEHR mapping contract.
19. P0-018-C | Owner: `CIO + CTO` | Due: `2026-03-27` | Publish and approve canonical Meditech-to-OpenEHR mapping contract.
20. P0-019-B | Owner: `CIO + Ops` | Due: `2026-03-27` | Add OpenEHR reconciliation and rollback procedure before live onboarding.
21. P0-019-C | Owner: `CIO + Ops` | Due: `2026-03-27` | Add OpenEHR reconciliation and rollback procedure before live onboarding.
22. P0-020-B | Owner: `CTO + VP Product` | Due: `2026-03-27` | Define one canonical ingestion-to-Q&A route for pilot users.
23. P0-020-C | Owner: `CTO + VP Product` | Due: `2026-03-27` | Define one canonical ingestion-to-Q&A route for pilot users.
24. P0-021-B | Owner: `VP Product + Clinical AI` | Due: `2026-03-27` | Enforce confidence-to-action policy for high-risk workflows.
25. P0-021-C | Owner: `VP Product + Clinical AI` | Due: `2026-03-27` | Enforce confidence-to-action policy for high-risk workflows.
26. P0-022-B | Owner: `Clinical AI` | Due: `2026-03-27` | Require evidence-bound confidence and decline behavior on unsupported claims.
27. P0-022-C | Owner: `Clinical AI` | Due: `2026-03-27` | Require evidence-bound confidence and decline behavior on unsupported claims.
28. P0-023-B | Owner: `Clinical AI + Product` | Due: `2026-03-27` | Require source document IDs and provenance fields for every non-empty answer.
29. P0-023-C | Owner: `Clinical AI + Product` | Due: `2026-03-27` | Require source document IDs and provenance fields for every non-empty answer.
30. P0-024-B | Owner: `VP Product` | Due: `2026-03-27` | Add explicit "degraded" UX mode with action block and clinician escalation.
31. P0-024-C | Owner: `VP Product` | Due: `2026-03-27` | Add explicit "degraded" UX mode with action block and clinician escalation.
32. P0-025-B | Owner: `CIO + Ops` | Due: `2026-03-27` | Define and staff incident escalation matrix with response SLAs.
33. P0-025-C | Owner: `CIO + Ops` | Due: `2026-03-27` | Define and staff incident escalation matrix with response SLAs.
34. P0-026-B | Owner: `Ops` | Due: `2026-03-27` | Execute one backup restore drill for PostgreSQL and Neo4j.
35. P0-026-C | Owner: `Ops` | Due: `2026-03-27` | Execute one backup restore drill for PostgreSQL and Neo4j.
36. P0-027-B | Owner: `Ops + CTO` | Due: `2026-03-27` | Execute one failover/dependency outage simulation and record MTTR.
37. P0-027-C | Owner: `Ops + CTO` | Due: `2026-03-27` | Execute one failover/dependency outage simulation and record MTTR.
38. P0-028-B | Owner: `Program Lead` | Due: `2026-03-27` | Produce final pre-pilot signoff matrix (CTO/CISO/CIO/Clinical AI/Product/Ops).
39. P0-028-C | Owner: `Program Lead` | Due: `2026-03-27` | Produce final pre-pilot signoff matrix (CTO/CISO/CIO/Clinical AI/Product/Ops).

## Sprint-4
- Task count: 47

1. P1-001-A | Owner: `Clinical AI` | Due: `2026-04-10` | Replace heuristic confidence assembly with tiered evidence-weighted scoring.
2. P1-001-B | Owner: `Clinical AI` | Due: `2026-04-10` | Replace heuristic confidence assembly with tiered evidence-weighted scoring.
3. P1-002-A | Owner: `Clinical AI + Product` | Due: `2026-04-10` | Standardize confidence semantics across extraction, KG, reasoning, and final answer.
4. P1-002-B | Owner: `Clinical AI + Product` | Due: `2026-04-10` | Standardize confidence semantics across extraction, KG, reasoning, and final answer.
5. P1-003-A | Owner: `Product + Clinical AI` | Due: `2026-04-10` | Add confidence threshold policy object configurable by workflow type.
6. P1-003-B | Owner: `Product + Clinical AI` | Due: `2026-04-10` | Add confidence threshold policy object configurable by workflow type.
7. P1-004-A | Owner: `Product + Clinical AI` | Due: `2026-04-10` | Implement refusal mode for critical errors and low-confidence clinical paths.
8. P1-004-B | Owner: `Product + Clinical AI` | Due: `2026-04-10` | Implement refusal mode for critical errors and low-confidence clinical paths.
9. P1-005-A | Owner: `Clinical AI` | Due: `2026-04-10` | Add missing note and coverage metrics to all query payloads.
10. P1-005-B | Owner: `Clinical AI` | Due: `2026-04-10` | Add missing note and coverage metrics to all query payloads.
11. P1-006-A | Owner: `Clinical AI + Ops` | Due: `2026-04-10` | Attach data freshness and ingestion timestamp to Q&A responses.
12. P1-006-B | Owner: `Clinical AI + Ops` | Due: `2026-04-10` | Attach data freshness and ingestion timestamp to Q&A responses.
13. P1-007-A | Owner: `Clinical AI` | Due: `2026-04-10` | Add provenance integrity checks in KG merge stage for near-match entities.
14. P1-007-B | Owner: `Clinical AI` | Due: `2026-04-10` | Add provenance integrity checks in KG merge stage for near-match entities.
15. P1-008-A | Owner: `Clinical AI` | Due: `2026-04-10` | Harden OMOP fallback matching to reduce semantic false positives.
16. P1-008-B | Owner: `Clinical AI` | Due: `2026-04-10` | Harden OMOP fallback matching to reduce semantic false positives.
17. P1-009-A | Owner: `CTO + Clinical AI` | Due: `2026-04-10` | Add bounded cache and invalidation on OMOP version change.
18. P1-009-B | Owner: `CTO + Clinical AI` | Due: `2026-04-10` | Add bounded cache and invalidation on OMOP version change.
19. P1-010-A | Owner: `QA + Clinical AI` | Due: `2026-04-10` | Create UMLS/OMOP acceptance corpus with positive and negative concept pairs.
20. P1-010-B | Owner: `QA + Clinical AI` | Due: `2026-04-10` | Create UMLS/OMOP acceptance corpus with positive and negative concept pairs.
21. P1-011-A | Owner: `CTO + Clinical AI` | Due: `2026-04-10` | Add real-source document retrieval in GraphRAG path (remove placeholder behavior).
22. P1-011-B | Owner: `CTO + Clinical AI` | Due: `2026-04-10` | Add real-source document retrieval in GraphRAG path (remove placeholder behavior).
23. P1-012-A | Owner: `Clinical AI + Compliance` | Due: `2026-04-10` | Add guideline corpus versioning, expiration, and update policy.
24. P1-012-B | Owner: `Clinical AI + Compliance` | Due: `2026-04-10` | Add guideline corpus versioning, expiration, and update policy.
25. P1-013-A | Owner: `Clinical AI` | Due: `2026-04-10` | Expand drug safety coverage and explicitly label uncovered pairs.
26. P1-014-A | Owner: `Clinical AI` | Due: `2026-04-10` | Add clinical plausibility validation to calculator inputs.
27. P1-015-A | Owner: `Clinical AI + Product` | Due: `2026-04-10` | Label differential diagnosis scores as ranking until calibrated.
28. P1-016-A | Owner: `VP Product + CIO` | Due: `2026-04-10` | Add explicit pilot policy for 77% accuracy classes by workflow.
29. P1-017-A | Owner: `VP Product` | Due: `2026-04-10` | Lock pilot UI to single sanctioned extraction mode profile.
30. P1-018-A | Owner: `VP Product + Clinical AI` | Due: `2026-04-10` | Show model/provider route and risk tier in every answer header.
31. P1-019-A | Owner: `Clinical AI` | Due: `2026-04-10` | Add fallback_used and reason_code to every degraded response.
32. P1-020-A | Owner: `CTO + CISO` | Due: `2026-04-10` | Add production-safe startup validation for dependency credentials.
33. P1-021-A | Owner: `Ops + CTO` | Due: `2026-04-10` | Split critical/non-critical dependency classes in health/readiness policies.
34. P1-022-A | Owner: `Ops` | Due: `2026-04-10` | Add worker liveness checks based on process and queue health, not API ping.
35. P1-023-A | Owner: `Ops + CTO` | Due: `2026-04-10` | Add queue depth SLOs and intake throttling/backpressure policy.
36. P1-024-A | Owner: `Ops` | Due: `2026-04-10` | Add alert routing for degraded or mock dependency states.
37. P1-025-A | Owner: `Ops` | Due: `2026-04-10` | Add service restart policy consistency for production stack.
38. P1-026-A | Owner: `CIO + Ops` | Due: `2026-04-10` | Formalize support staffing model and on-call rotation for pilot window.
39. P1-027-A | Owner: `CIO + Compliance` | Due: `2026-04-10` | Add Australian residency and consent metadata capture at ingestion.
40. P1-028-A | Owner: `Compliance + Ops` | Due: `2026-04-10` | Add retention policy enforcement and archival controls for PHI paths.
41. P1-029-A | Owner: `Compliance + CISO` | Due: `2026-04-10` | Add purpose-of-use tagging in audit events where clinically relevant.
42. P1-030-A | Owner: `CIO + Interop` | Due: `2026-04-10` | Add external integration onboarding checklist (data contract, validation, rollback).
43. P1-031-A | Owner: `Interop + QA` | Due: `2026-04-10` | Add Meditech sample replay validation against OpenEHR contract.
44. P1-032-A | Owner: `CIO + Ops + Clinical AI` | Due: `2026-04-10` | Add production incident taxonomy and severity rubric for clinical AI failures.
45. P1-033-A | Owner: `Program + CISO` | Due: `2026-04-10` | Add risk-acceptance workflow with expiry dates for unresolved P1 items.
46. P1-034-A | Owner: `CISO + Legal` | Due: `2026-04-10` | Add legal/provider contract gate for any external LLM with PHI exposure potential.
47. P1-035-A | Owner: `CTO + Ops` | Due: `2026-04-10` | Add immutable release checklist tying deployment SHA to safety checks.

## Sprint-5
- Task count: 58

1. P1-001-C | Owner: `Clinical AI` | Due: `2026-04-24` | Replace heuristic confidence assembly with tiered evidence-weighted scoring.
2. P1-002-C | Owner: `Clinical AI + Product` | Due: `2026-04-24` | Standardize confidence semantics across extraction, KG, reasoning, and final answer.
3. P1-003-C | Owner: `Product + Clinical AI` | Due: `2026-04-24` | Add confidence threshold policy object configurable by workflow type.
4. P1-004-C | Owner: `Product + Clinical AI` | Due: `2026-04-24` | Implement refusal mode for critical errors and low-confidence clinical paths.
5. P1-005-C | Owner: `Clinical AI` | Due: `2026-04-24` | Add missing note and coverage metrics to all query payloads.
6. P1-006-C | Owner: `Clinical AI + Ops` | Due: `2026-04-24` | Attach data freshness and ingestion timestamp to Q&A responses.
7. P1-007-C | Owner: `Clinical AI` | Due: `2026-04-24` | Add provenance integrity checks in KG merge stage for near-match entities.
8. P1-008-C | Owner: `Clinical AI` | Due: `2026-04-24` | Harden OMOP fallback matching to reduce semantic false positives.
9. P1-009-C | Owner: `CTO + Clinical AI` | Due: `2026-04-24` | Add bounded cache and invalidation on OMOP version change.
10. P1-010-C | Owner: `QA + Clinical AI` | Due: `2026-04-24` | Create UMLS/OMOP acceptance corpus with positive and negative concept pairs.
11. P1-011-C | Owner: `CTO + Clinical AI` | Due: `2026-04-24` | Add real-source document retrieval in GraphRAG path (remove placeholder behavior).
12. P1-012-C | Owner: `Clinical AI + Compliance` | Due: `2026-04-24` | Add guideline corpus versioning, expiration, and update policy.
13. P1-013-B | Owner: `Clinical AI` | Due: `2026-04-24` | Expand drug safety coverage and explicitly label uncovered pairs.
14. P1-013-C | Owner: `Clinical AI` | Due: `2026-04-24` | Expand drug safety coverage and explicitly label uncovered pairs.
15. P1-014-B | Owner: `Clinical AI` | Due: `2026-04-24` | Add clinical plausibility validation to calculator inputs.
16. P1-014-C | Owner: `Clinical AI` | Due: `2026-04-24` | Add clinical plausibility validation to calculator inputs.
17. P1-015-B | Owner: `Clinical AI + Product` | Due: `2026-04-24` | Label differential diagnosis scores as ranking until calibrated.
18. P1-015-C | Owner: `Clinical AI + Product` | Due: `2026-04-24` | Label differential diagnosis scores as ranking until calibrated.
19. P1-016-B | Owner: `VP Product + CIO` | Due: `2026-04-24` | Add explicit pilot policy for 77% accuracy classes by workflow.
20. P1-016-C | Owner: `VP Product + CIO` | Due: `2026-04-24` | Add explicit pilot policy for 77% accuracy classes by workflow.
21. P1-017-B | Owner: `VP Product` | Due: `2026-04-24` | Lock pilot UI to single sanctioned extraction mode profile.
22. P1-017-C | Owner: `VP Product` | Due: `2026-04-24` | Lock pilot UI to single sanctioned extraction mode profile.
23. P1-018-B | Owner: `VP Product + Clinical AI` | Due: `2026-04-24` | Show model/provider route and risk tier in every answer header.
24. P1-018-C | Owner: `VP Product + Clinical AI` | Due: `2026-04-24` | Show model/provider route and risk tier in every answer header.
25. P1-019-B | Owner: `Clinical AI` | Due: `2026-04-24` | Add fallback_used and reason_code to every degraded response.
26. P1-019-C | Owner: `Clinical AI` | Due: `2026-04-24` | Add fallback_used and reason_code to every degraded response.
27. P1-020-B | Owner: `CTO + CISO` | Due: `2026-04-24` | Add production-safe startup validation for dependency credentials.
28. P1-020-C | Owner: `CTO + CISO` | Due: `2026-04-24` | Add production-safe startup validation for dependency credentials.
29. P1-021-B | Owner: `Ops + CTO` | Due: `2026-04-24` | Split critical/non-critical dependency classes in health/readiness policies.
30. P1-021-C | Owner: `Ops + CTO` | Due: `2026-04-24` | Split critical/non-critical dependency classes in health/readiness policies.
31. P1-022-B | Owner: `Ops` | Due: `2026-04-24` | Add worker liveness checks based on process and queue health, not API ping.
32. P1-022-C | Owner: `Ops` | Due: `2026-04-24` | Add worker liveness checks based on process and queue health, not API ping.
33. P1-023-B | Owner: `Ops + CTO` | Due: `2026-04-24` | Add queue depth SLOs and intake throttling/backpressure policy.
34. P1-023-C | Owner: `Ops + CTO` | Due: `2026-04-24` | Add queue depth SLOs and intake throttling/backpressure policy.
35. P1-024-B | Owner: `Ops` | Due: `2026-04-24` | Add alert routing for degraded or mock dependency states.
36. P1-024-C | Owner: `Ops` | Due: `2026-04-24` | Add alert routing for degraded or mock dependency states.
37. P1-025-B | Owner: `Ops` | Due: `2026-04-24` | Add service restart policy consistency for production stack.
38. P1-025-C | Owner: `Ops` | Due: `2026-04-24` | Add service restart policy consistency for production stack.
39. P1-026-B | Owner: `CIO + Ops` | Due: `2026-04-24` | Formalize support staffing model and on-call rotation for pilot window.
40. P1-026-C | Owner: `CIO + Ops` | Due: `2026-04-24` | Formalize support staffing model and on-call rotation for pilot window.
41. P1-027-B | Owner: `CIO + Compliance` | Due: `2026-04-24` | Add Australian residency and consent metadata capture at ingestion.
42. P1-027-C | Owner: `CIO + Compliance` | Due: `2026-04-24` | Add Australian residency and consent metadata capture at ingestion.
43. P1-028-B | Owner: `Compliance + Ops` | Due: `2026-04-24` | Add retention policy enforcement and archival controls for PHI paths.
44. P1-028-C | Owner: `Compliance + Ops` | Due: `2026-04-24` | Add retention policy enforcement and archival controls for PHI paths.
45. P1-029-B | Owner: `Compliance + CISO` | Due: `2026-04-24` | Add purpose-of-use tagging in audit events where clinically relevant.
46. P1-029-C | Owner: `Compliance + CISO` | Due: `2026-04-24` | Add purpose-of-use tagging in audit events where clinically relevant.
47. P1-030-B | Owner: `CIO + Interop` | Due: `2026-04-24` | Add external integration onboarding checklist (data contract, validation, rollback).
48. P1-030-C | Owner: `CIO + Interop` | Due: `2026-04-24` | Add external integration onboarding checklist (data contract, validation, rollback).
49. P1-031-B | Owner: `Interop + QA` | Due: `2026-04-24` | Add Meditech sample replay validation against OpenEHR contract.
50. P1-031-C | Owner: `Interop + QA` | Due: `2026-04-24` | Add Meditech sample replay validation against OpenEHR contract.
51. P1-032-B | Owner: `CIO + Ops + Clinical AI` | Due: `2026-04-24` | Add production incident taxonomy and severity rubric for clinical AI failures.
52. P1-032-C | Owner: `CIO + Ops + Clinical AI` | Due: `2026-04-24` | Add production incident taxonomy and severity rubric for clinical AI failures.
53. P1-033-B | Owner: `Program + CISO` | Due: `2026-04-24` | Add risk-acceptance workflow with expiry dates for unresolved P1 items.
54. P1-033-C | Owner: `Program + CISO` | Due: `2026-04-24` | Add risk-acceptance workflow with expiry dates for unresolved P1 items.
55. P1-034-B | Owner: `CISO + Legal` | Due: `2026-04-24` | Add legal/provider contract gate for any external LLM with PHI exposure potential.
56. P1-034-C | Owner: `CISO + Legal` | Due: `2026-04-24` | Add legal/provider contract gate for any external LLM with PHI exposure potential.
57. P1-035-B | Owner: `CTO + Ops` | Due: `2026-04-24` | Add immutable release checklist tying deployment SHA to safety checks.
58. P1-035-C | Owner: `CTO + Ops` | Due: `2026-04-24` | Add immutable release checklist tying deployment SHA to safety checks.

## Sprint-6
- Task count: 30

1. P2-001-A | Owner: `QA + CTO` | Due: `2026-05-08` | Add integration tests with real Neo4j + PostgreSQL for KG/QA pathways.
2. P2-002-A | Owner: `QA + Clinical AI` | Due: `2026-05-08` | Add contract tests for answer provenance completeness.
3. P2-003-A | Owner: `Ops + QA` | Due: `2026-05-08` | Add synthetic canary tests for top 5 clinical workflows.
4. P2-004-A | Owner: `Clinical AI` | Due: `2026-05-08` | Add benchmark harness for NLP extraction precision/recall by entity type.
5. P2-005-A | Owner: `Clinical AI + QA` | Due: `2026-05-08` | Add regression tests for negation/experiencer edge cases.
6. P2-006-A | Owner: `Clinical AI + Product` | Due: `2026-05-08` | Add KG completeness scoring model and expose in API/UI.
7. P2-007-A | Owner: `Clinical AI` | Due: `2026-05-08` | Add uncertainty taxonomy and reason codes for all decline/degraded outputs.
8. P2-008-A | Owner: `Product` | Due: `2026-05-08` | Add chart-level "what system knows vs does not know" summary panel.
9. P2-009-A | Owner: `Product + Clinical AI` | Due: `2026-05-08` | Add clinician feedback capture and replay pipeline.
10. P2-010-A | Owner: `Clinical AI + Data` | Due: `2026-05-08` | Add drift detection for terminology mapping distributions over time.
11. P2-011-A | Owner: `Clinical AI + Product` | Due: `2026-05-08` | Add concept mapping disagreement dashboard (rule vs ML vs ensemble).
12. P2-012-A | Owner: `CTO + Ops` | Due: `2026-05-08` | Add queue partitioning by workload class (ingest/mapping/KG/export).
13. P2-013-A | Owner: `Ops + CTO` | Due: `2026-05-08` | Add horizontal scaling plan for worker pools with load tests.
14. P2-014-A | Owner: `CTO + Ops` | Due: `2026-05-08` | Add Kafka HA strategy decision (managed service vs multi-broker self-hosted).
15. P2-015-A | Owner: `Ops` | Due: `2026-05-08` | Add Redis separation for cache vs job queue in production design.
16. P2-016-A | Owner: `Ops` | Due: `2026-05-08` | Add scheduled backup automation and restore verification jobs.
17. P2-017-A | Owner: `Ops + Platform` | Due: `2026-05-08` | Add SLO dashboard with p95/p99 latency and error rates by endpoint.
18. P2-018-A | Owner: `Ops` | Due: `2026-05-08` | Add alert fatigue controls and tuned severity thresholds.
19. P2-019-A | Owner: `CTO + Clinical AI` | Due: `2026-05-08` | Add API budget/timeout policies for hybrid query path.
20. P2-020-A | Owner: `Platform` | Due: `2026-05-08` | Add idempotency and retry safety for ingestion endpoints.
21. P2-021-A | Owner: `Clinical AI + Ops` | Due: `2026-05-08` | Add deterministic reprocessing mode for failed notes.
22. P2-022-A | Owner: `Data + Clinical AI` | Due: `2026-05-08` | Add structured data lineage fields end-to-end (source system to answer).
23. P2-023-A | Owner: `CIO + Interop` | Due: `2026-05-08` | Add tenant onboarding automation and preflight validation checks.
24. P2-024-A | Owner: `Security + QA` | Due: `2026-05-08` | Add endpoint-level RBAC test suite for least privilege.
25. P2-025-A | Owner: `CISO + QA` | Due: `2026-05-08` | Add policy tests to ensure no sensitive defaults in production configs.
26. P2-026-A | Owner: `CISO` | Due: `2026-05-08` | Add threat model update cadence tied to release cycles.
27. P2-027-A | Owner: `Interop + QA` | Due: `2026-05-08` | Add OpenEHR profile validation suite for generated payloads.
28. P2-028-A | Owner: `Interop` | Due: `2026-05-08` | Add interoperability conformance suite (FHIR search/profile/capability statement).
29. P2-029-A | Owner: `CIO + Ops` | Due: `2026-05-08` | Add business continuity tabletop cadence with action item closure tracking.
30. P2-030-A | Owner: `Program Lead` | Due: `2026-05-08` | Add monthly executive risk summary with blocker trends.

