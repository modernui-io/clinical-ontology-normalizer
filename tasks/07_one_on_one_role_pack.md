# One-on-One Role Pack (Rapid Answers)

Purpose
- Give fast, defensible answers during leadership one-on-ones.
- Keep responses aligned with current repository evidence and the OpenEHR pilot posture.
- Default answer length: three sentences.

Current baseline posture
- Pilot decision: controlled go only for a narrow supervised scope.
- Broad rollout: hold until P0/P1 blockers are closed.
- Canonical migration target: OpenEHR with Meditech input adapters.

## CTO Questions (Architecture, Production Feasibility)
| Likely question | Three-sentence answer template | Evidence anchors |
|---|---|---|
| Can this go to production now? | We can run a restricted pilot, but not broad production yet. The core blockers are fail-closed dependency behavior, canonical OpenEHR contractization, and deterministic pipeline routing. We should treat this as controlled go only until those are closed. | `exec-review/cto-review.md`, `tasks/06_clinical_ai_todo_list.md` |
| What is our architecture risk right now? | The highest risk is silent degradation when graph or queue dependencies are in fallback/mocked behavior. That creates correctness risk rather than obvious downtime. We need readiness and query responses to surface degraded state explicitly. | `backend/app/services/graph_database_service.py`, `backend/app/services/kafka_service.py`, `backend/app/api/health.py` |
| Is OpenEHR ready in code? | Not as a canonical implemented adapter yet. We have connector coverage for FHIR/HL7v2/CCDA/CSV, but OpenEHR contract and reconciliation checks remain gating work. That is a rollout blocker for full migration confidence. | `backend/app/connectors/`, `exec-review/cio-review.md` |
| What must be true before scale? | One canonical ingestion route, hard fail-safe behavior, and end-to-end provenance visibility are mandatory. We also need confidence logic to be evidence-bound across KG and Q&A. Without those, scaling multiplies silent failure risk. | `tasks/06_clinical_ai_todo_list.md`, `exec-review/vp-product-review.md` |
| Are we over-relying on fallback logic? | Yes in ways that are acceptable for development but risky for clinical production semantics. Fallback needs explicit degraded mode and pilot-level gating, not implicit continuity. We should prioritize that before broad onboarding. | `exec-review/operations-review.md`, `exec-review/ciso-review.md` |

## CISO Questions (Security, PHI, Compliance)
| Likely question | Three-sentence answer template | Evidence anchors |
|---|---|---|
| Is security posture sufficient for external pilot access? | Not yet for external unrestricted use. Primary gaps are auth defaults, secret hygiene, and incomplete audit coverage across worker and graph paths. We should keep access restricted until these controls are enforced. | `exec-review/ciso-review.md`, `backend/app/core/config.py`, `docker-compose.yml` |
| Is auth enforced by default? | Current defaults are not strict enough for production clinical posture. We need mandatory auth behavior in non-dev environments and fail-start if misconfigured. That is a hard-stop control gap. | `backend/app/core/config.py`, `tasks/05_pilot_todo_list.md` |
| Are secrets and credentials handled safely? | There are still insecure default patterns in compose and environment templates. That creates deployment drift and audit risk if not overridden consistently. We need explicit runtime secrets policy before expansion. | `docker-compose.yml`, `.env.example`, `exec-review/compliance-review.md` |
| Can mock mode create compliance blind spots? | Yes, because synthetic fallback can appear operational without clear compliance signaling. That can blur PHI processing state and incident visibility. Mock/degraded states need explicit alerting and policy treatment. | `backend/app/api/health.py`, `backend/app/services/kafka_service.py`, `backend/app/services/graph_database_service.py` |
| Are we audit-ready? | We have good middleware foundations, but coverage is incomplete for some background and graph pathways. That means access reconstruction could be partial in incident review. We should close those gaps before external clinical exposure. | `backend/app/middleware/audit_middleware.py`, `exec-review/compliance-review.md` |

## CIO Questions (Governance, Onboarding, Operating Model)
| Likely question | Three-sentence answer template | Evidence anchors |
|---|---|---|
| Can this be onboarded cleanly at health-system level? | For a narrow internal pilot, yes with strict governance controls. For broad onboarding, OpenEHR contractization and reconciliation runbooks are still missing as enforceable artifacts. We should hold expansion until those are complete. | `exec-review/cio-review.md`, `tasks/06_clinical_ai_todo_list.md` |
| What is the biggest governance gap? | There is no fully operationalized OpenEHR migration and rollback framework tied to daily operations yet. That exposes onboarding drift risk during Meditech transition. We need signed mapping, lineage, and rollback ownership. | `tasks/06_clinical_ai_todo_list.md`, `exec-review/interop-review.md` |
| Is support ownership clear? | Partially. We have role reviews and runbooks, but escalation and enforcement still need closure at pilot operations level. Named owners with response windows should be finalized before day 0. | `exec-review/operations-review.md`, `tasks/05_pilot_todo_list.md` |
| What do we do with 77% accuracy classes? | We accept that only in low-to-moderate risk informational workflows. High-risk clinical decisions require higher confidence and explicit escalation-to-human policy. Product controls must enforce this rather than rely on user judgment alone. | `exec-review/vp-product-review.md` |
| What is the rollout recommendation? | Start with single-tenant, single-service-line, supervised workflows. Treat initial deployment as controlled pilot with explicit data governance gates. Expand only after P0/P1 closure evidence. | `exec-review/cio-review.md`, `tasks/04_enterprise_readiness_multi_agent_playbook_run.md` |

## VP Product Questions (Workflow Safety, Trust UX)
| Likely question | Three-sentence answer template | Evidence anchors |
|---|---|---|
| Is product behavior safe at current confidence levels? | It is acceptable only with explicit confidence-to-action gating. Right now, some fallback and low-evidence flows can still feel actionable to users. We need forced escalation patterns in high-risk workflows before broad launch. | `exec-review/vp-product-review.md`, `frontend/src/app/nlp/page.tsx` |
| Where does user trust break first? | Trust breaks when confidence values are shown without evidence quality context. Users can over-trust numerics that came from weaker paths. We should display dependency state, evidence grade, and refusal conditions together. | `backend/app/api/clinical_agent.py`, `exec-review/vp-product-review.md` |
| Is one canonical user path defined? | Not fully enforced yet. Multiple alternate routes still exist for similar outcomes, which can yield inconsistency. Pilot should lock one canonical path and mark alternates as non-pilot/experimental. | `backend/app/api/nlp.py`, `frontend/src/app/nlp/page.tsx` |
| Can we ship with 77% in pilot? | Yes for draft, informational, and reviewed workflows with explicit warning. No for autonomous high-risk clinical action flows. The product must encode that policy in UI and API behavior. | `exec-review/vp-product-review.md`, `tasks/06_clinical_ai_todo_list.md` |
| What is the fastest product hardening step? | Add confidence band policy tied to available actions and mandatory escalation for low-confidence answers. That immediately reduces unsafe use while keeping pilot velocity. Then enforce one canonical ingestion-to-QA workflow. | `tasks/05_pilot_todo_list.md`, `tasks/06_clinical_ai_todo_list.md` |

## Clinical AI Lead Questions (Inference Reliability)
| Likely question | Three-sentence answer template | Evidence anchors |
|---|---|---|
| Where can wrong answers look confident? | In hybrid Q&A when evidence is sparse but answer synthesis still proceeds. Heuristic confidence can overstate reliability without strong provenance checks. We need evidence-bound confidence and decline behavior when support is weak. | `backend/app/api/clinical_agent.py`, `exec-review/clinical-ai-review.md` |
| What is the top patient-safety risk? | Silent graph incompleteness and ungrounded narrative links are the top safety risks. A missing note or fabricated relation can distort downstream recommendations. Extraction status and grounding validation must be first-class gating signals. | `backend/app/api/clinical_agent.py`, `backend/app/services/narrative_extractor.py` |
| Is OMOP/UMLS reliability acceptable? | The architecture is strong, but fallback matching and cache strategy need hardening for production confidence. We need bounded caching, vocabulary invalidation behavior, and precision guardrails for non-equivalent matches. That is required before scale. | `backend/app/services/omop_hierarchy_service.py`, `tasks/06_clinical_ai_todo_list.md` |
| Can we trust current narrative extraction output? | It is useful but not yet fully safe for unattended use. Prompt-level grounding exists, but post-parse strict validation is still incomplete. We should treat narrative output as controlled until strict grounding checks are enforced. | `backend/app/services/narrative_extractor.py`, `exec-review/clinical-ai-review.md` |
| What is the right launch scope? | Launch as clinician-supervised decision support, not autonomous recommendation execution. Require provenance visibility and explicit degraded-state handling in every answer. Expand scope only after P0/P1 closure evidence. | `tasks/06_clinical_ai_todo_list.md` |

## SRE/Ops Questions (SLA, Failover, DR, Readiness)
| Likely question | Three-sentence answer template | Evidence anchors |
|---|---|---|
| What is downtime posture today? | Current posture supports a controlled pilot, not enterprise-grade SLA claims. Core gaps are dependency-aware readiness, alerting rigor, and single-node failure domains. We should communicate controlled-go reliability limits explicitly. | `exec-review/operations-review.md`, `docker-compose.prod.yml` |
| Are readiness checks launch-safe? | Not fully, because some degraded/mock states can still appear healthy enough for continuation. We need readiness to fail closed for critical dependency classes in production posture. That is a gate before broader use. | `backend/app/api/health.py`, `backend/app/services/graph_database_service.py` |
| Is failover/DR complete? | Documentation exists, but operationally enforced drills and version-bound evidence need completion. Until that is done, recovery confidence is policy-level rather than proven. Pilot should run with explicit rollback guardrails. | `docs/operations/disaster_recovery_plan.md`, `exec-review/operations-review.md` |
| Can we support incidents at pilot scale? | Yes with constrained scope and manual monitoring discipline. For wider rollout, we need stronger alert routing, queue pressure controls, and dependency-state paging. Otherwise MTTR and silent failures become the core risk. | `backend/app/middleware/sli_collector.py`, `backend/app/core/queue.py` |
| What is day-0 operational requirement? | Confirm dependency states are real, not mocked, across health and readiness endpoints. Run ingestion-to-QA smoke tests with traceable provenance before opening user access. Lock escalation contacts and response windows pre-launch. | `tasks/05_pilot_todo_list.md`, `exec-review/operations-review.md` |

## Do-Not-Say List (Meeting Risk Controls)
- Do not claim "production-ready" without the qualifier "restricted controlled pilot."
- Do not claim "OpenEHR-native" until canonical adapter contract and reconciliation tests are complete.
- Do not treat fallback/mocked dependency paths as acceptable for high-risk clinical workflows.
- Do not present confidence numbers without evidence quality and escalation context.

