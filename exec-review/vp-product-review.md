# VP Product Review: Clinical Product Readiness for Pilot Go/No-Go

**Date:** 2026-02-13  
**Scope:** Ramsey Health / Australia pilot, Meditech-to-OpenEHR focus  
**Mode:** Analysis-only (no code changes in this pass)

## Executive Verdict
**Controlled go** for a narrow pilot only.

The product has strong clinical primitives, but current experience and control UX are not yet safe for broader clinical workflows. The dominant gap is not missing model capability, but missing explicit product-level risk controls: confidence-based UX behavior is inconsistent, and there is no enforced escalation policy across common paths that already require clinical override decisions.

## 77% Confidence Decision Matrix (Product Acceptance by Workflow)

| Workflow | Clinical Risk | Accept at ~77%? | Gate Required to Proceed | Why |
|---|---|---|---|---|
| Entity extraction preview / internal analysis | Medium | **Yes with banner** | Show extraction-level confidence with caveats before clinician uses results | Useful for support work and triage prep |
| Q&A / conversational answering | Very High | **No** (unless explicit guardrail) | Block downstream decisions when confidence `< 0.8`; force manual verification workflow | LLM answer can still be high confidence but unsupported by evidence |
| Medication / treatment suggestions | Very High | **No** | Require dual confirmation + evidence links + fallback refusal when confidence `< 0.85` | Incorrect outputs carry direct patient risk |
| KG build for clinical context continuity | High | **Conditional** | Reject/flag low-confidence entities, disallow silent drops | Missing concepts can silently remove contraindications/allergies |
| Screening summaries / documentation support | Medium | **Yes with disclaimer** | Mark as "review-draft" output and require clinician attestation | Human review still required before clinical action |
| OpenEHR canonical onboarding evidence | Critical | **No** | Require contract tests for Meditech source-to-OpenEHR schema mapping | Missing mapping is a deployment blocker for your environment |

## Finding Register

### VP-P1 — There is no active confidence-to-action policy in Q&A and KG workflows
**Severity:** P1  
**Likelihood:** High  
**Evidence:** `frontend/src/app/nlp/page.tsx` (`handleQAQuery`, `workbenchMode`, `ConfidenceBadge` usage) and backend `backend/app/api/clinical_agent.py:1918` (`hybrid_query`)  
**Clinical Impact:** The interface can present answers even when confidence is weak; no hard block exists in UI or API for low-confidence outputs.  
**Risk:** LLM outputs can be trusted too early, leading to wrong medication/recommendation interpretation.  
**Recommendation:** Add product-level policy:
- if confidence `< 0.6`: do not proceed, show hard block and require clinical sign-off
- if `0.6–0.79`: warning-only, no action mode
- if `>= 0.8`: advisory mode with clear provenance  
**Owner Role:** VP Product + Clinical Safety  
**Pilot Impact:** **hold** for unguarded medication/order workflows.

### VP-P2 — Q&A path currently degrades with a template answer at `0.5` confidence without explicit UX escalation
**Severity:** P1  
**Likelihood:** High  
**Evidence:** `backend/app/api/clinical_agent.py:2694-2708` sets fallback `confidence = 0.5` when LLM fails and returns generic fallback text.  
**Clinical Impact:** Fail-open behavior can be mistaken as valid low-risk output and reduce trust.  
**Risk:** Operational confusion and undocumented reliance on degraded answers.  
**Recommendation:** In product terms, route all fallback outputs to `status: degraded`, and block downstream use until clinician confirms manual review.  
**Owner Role:** VP Product + Engineering  
**Pilot Impact:** **controlled go** only if escalation required by UX.

### VP-P3 — Evidence strength is not surfaced consistently in KG build + Q&A path
**Severity:** P2  
**Likelihood:** High  
**Evidence:** `backend/app/api/clinical_agent.py:2044-2114` (query sources and citations) plus `frontend/src/app/nlp/page.tsx` display path where citations are optional.  
**Clinical Impact:** Clinicians may not be able to judge when an answer is traceable versus inferred.  
**Risk:** Overreliance on summary-grade output in high-risk decisions.  
**Recommendation:** Mark every returned QA with:
- source count,
- source quality grade,
- and a short provenance summary card before answer acceptance.
**Owner Role:** VP Product + UX + Clinical Informatics  
**Pilot Impact:** **can ship** if visibility and refusal rules are added.

### VP-P4 — The canonical extraction route is not enforced at product workflow level
**Severity:** P2  
**Likelihood:** High  
**Evidence:** `/frontend`: multiple build routes (`handleBuildKnowledgeGraph`, `handleBuildKnowledgeGraphFromHybrid`) and multiple backend routes in `backend/app/api/nlp.py` and `backend/app/api/clinical_agent.py`.  
**Clinical Impact:** Inconsistent outputs depending on which UI path a user picks.  
**Risk:** Workflow non-determinism, difficult incident triage, inconsistent pilot results.  
**Recommendation:** Publish and enforce one canonical path for pilot: text → structured extraction → canonical KG build → QA path. Hide or flag experimental alternatives.  
**Owner Role:** VP Product + Platform  
**Pilot Impact:** **hold** for scale; **conditional go** for narrow single-path usage.

### VP-P5 — Fixed hybrid-confidence values in KG build inflate perceived completeness
**Severity:** P2  
**Likelihood:** High  
**Evidence:** `frontend/src/app/nlp/page.tsx` assigns static `confidence` values (`0.9`, `0.85`) when converting hybrid context to KG entities; `backend/app/api/clinical_agent.py:1244` also skips entities below `0.5` in build.  
**Clinical Impact:** A KG node stream looks complete when some entries are synthetic-converted from uncertain structures.  
**Risk:** Overstated trust in graph for query and order-support workflows.  
**Recommendation:** Use source extraction confidence; keep original confidence and carry uncertainty labels per node/edge.  
**Owner Role:** VP Product + Clinical AI  
**Pilot Impact:** **controlled go** for confidence display and actionability until mapped.

### VP-P6 — OpenEHR and Meditech migration contract is absent from product onboarding path
**Severity:** P1  
**Likelihood:** High  
**Evidence:** `backend/app/connectors/` contains `fhir_connector.py`, `hl7v2_connector.py`, `ccda_connector.py`, `csv_connector.py` but no OpenEHR adapter; clinical docs for interoperability explicitly reference future Meditech migration context.  
**Clinical Impact:** Pilot onboarding variance and schema drift are uncontrolled.  
**Risk:** High onboarding downtime, wrong mapping of identifiers/encounters, and invalid clinical IDs.  
**Recommendation:** Deliver a signed OpenEHR contract before pilot acceptance with:
- source identifiers,
- encounter provenance,
- terminology lineage,
- validation fixtures from Meditech extracts.  
**Owner Role:** CIO + Platform + Clinical Informatics  
**Pilot Impact:** **hold** for broad onboarding; narrow internal pilot only with mocked data.

### VP-P7 — No explicit product guard for negative/insufficient OMOP/UMLS mapping
**Severity:** P2  
**Likelihood:** High  
**Evidence:** `backend/app/core/config.py` sets `enable_concept_mapping` and `use_ontology_edges` defaults that imply optional behavior (`enable_concept_mapping=False`, `use_ontology_edges=False` in defaults).  
**Clinical Impact:** Product can run with low ontology confidence without user-visible signaling.  
**Risk:** Clinical teams cannot distinguish normalized vs unmapped behavior in workflow.  
**Recommendation:** Add explicit session flags in UI:
- `normalized?`,
- `mapping_gap_reason`,
- `fallback_used` for each returned section.  
**Owner Role:** VP Product + Clinical AI  
**Pilot Impact:** **controlled go** with transparency requirements.

### VP-P8 — Narrative extraction fallback and extraction method selection lacks decision UX
**Severity:** P2  
**Likelihood:** Medium  
**Evidence:** `frontend/src/app/nlp/page.tsx` supports `analysis_type`, `extract_narrative`, `useMLModels`, `selectedModelId`, but these are not surfaced as clinical risk controls in result cards.  
**Clinical Impact:** Different users can get different outputs with no product-level interpretation guidance.  
**Risk:** Trust drift between users and no reliable repeatability.  
**Recommendation:** Lock pilot mode to one extraction policy and expose model/risk mode in every result header.  
**Owner Role:** VP Product + QA + Clinical Ops  
**Pilot Impact:** **can ship** with restrictions in controlled workflow.

### VP-P9 — Inconsistent confidence semantics across pipeline stages
**Severity:** P2  
**Likelihood:** High  
**Evidence:** `backend/app/api/clinical_agent.py` uses heuristic confidence assembly from `relevant_entities`, `graph_paths_data`, `guideline_citations_data`, etc.; frontend maps to generic `ConfidenceBadge` (`frontend/src/app/nlp/page.tsx`).  
**Clinical Impact:** Same numeric score can mean different reliability levels across extraction, KG, and QA.  
**Risk:** Users make inaccurate confidence judgments and act too early.  
**Recommendation:** Standardize confidence schema:
- extraction confidence,
- propagation confidence,
- reasoning confidence,
- final action confidence.  
**Owner Role:** VP Product + Clinical AI + Engineering  
**Pilot Impact:** **controlled go** once displayed as a 3-stage score.

### VP-P10 — No product-level refusal option for critical errors while allowing continued workflow
**Severity:** P3  
**Likelihood:** Medium  
**Evidence:** `frontend/src/app/nlp/page.tsx` proceeds from extraction into KG build and Q&A with little error-mode distinction besides toasts.  
**Clinical Impact:** One bad upstream dependency still allows user progression.  
**Risk:** Quietly incorrect follow-on context when upstream path is degraded.  
**Recommendation:** Add explicit workflow states and dead-end blocks: "Extracted with issues" and "KG incomplete—cannot query".  
**Owner Role:** VP Product + Engineering  
**Pilot Impact:** **can ship** when states are enforced in UI and API.

## Product Go/No-Go Summary

- **Go:** narrow internal pilot with visible confidence bands and mandatory clinician review mode.
- **Controlled go only:** any environment where fallback outputs are displayed as draft and require explicit confirmation.
- **Hold:** external rollout for medication-related decisions until OpenEHR contract + confidence gate policy is deployed.

## Top 3 Blockers
1) Confidence-to-action policy missing for `hybrid_query` outputs (VP-P1, VP-P2)  
2) No enforced canonical ingestion path (VP-P4)  
3) OpenEHR contract gap for Meditech handoff (VP-P6)

## Top 3 Can-Ship-with-Guardrails Items
1) Static confidence assignment for KG build entities (VP-P5) can remain only if transparency labels are added.  
2) Q&A visibility improvements (VP-P3, VP-P9) can be shipped with strict display semantics.  
3) Optional extraction path locking (VP-P8) can be shipped as a pilot profile.

## 30/60/90-Day Product Hardening Plan

### 0–30 Days (Pilot Launch-Readiness)
- Implement confidence gates in all user-facing pathways.
- Freeze one canonical clinical pipeline and deprecate alternates.
- Add explicit degraded-state UI mode for fallbacks.

### 31–60 Days (Pilot Stability)
- Add session-level trust annotations (mapping confidence, fallback type).
- Add explicit escalation button flows and refusal confirmation.
- Add deterministic conversion fixtures for OpenEHR canonical mapping.

### 61–90 Days (Wider Rollout)
- Replace fixed hybrid conversion confidences with provenance-driven confidence.
- Expand QA to provide decision-ready provenance cards and confidence reason codes.
- Publish user-facing decision support SOPs and acceptance tests.

## Open Questions for Product Leadership
- Which user groups get write/decision privileges in pilot phase?
- Is Q&A allowed to propose treatment framing, or should it remain informational only initially?
- What is the mandatory minimum confidence threshold for Meditech-to-OpenEHR ingestion at launch?
