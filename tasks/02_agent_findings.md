# Agent Findings 02 (Model-Aware Orchestration)

Date: 2026-02-02
Scope: NLP Workbench → Hybrid Analyzer → KG → QA pipeline with explicit model selection behavior.

---

## Agent 1 — Model Selection Wiring

Findings
- UI only sends `use_ml_models` flag; no `model_id` is passed. `frontend/src/app/nlp/page.tsx`
- `/nlp/extract` ignores `model_id` when `use_ml_models=true`; it always uses `EnsembleNLPService` and hard-codes `model_id="ensemble_nlp"`. `backend/app/api/nlp.py`
- `nlp_entity_core` supports ML model registration + `model_id` selection, but no ML models are registered at startup. `backend/app/services/nlp_entity/nlp_entity_core.py`, `backend/app/main.py`
- `/nlp/models` returns only `rule_based` unless ML models are registered. `backend/app/api/nlp.py`

Implication
- Changing model selection in UI has no effect today. “New model” selection doesn’t reach the backend.

Recommendations
- Add a model selector in the Workbench that sends `model_id` to `/nlp/extract`.
- Modify `/nlp/extract` to honor `model_id` (or explicitly label it “Ensemble only”).
- Register ML models in the NLP entity service if you want model_id to work.

---

## Agent 2 — Coverage & Extraction Pipeline

Findings
- Full token coverage exists in `ClinicalOntologyMapper` with `coverage_pct` and `unknown_tokens`. `backend/app/services/clinical_ontology_mapper.py`
- `/nlp/ontology/map` returns coverage stats but not unknown spans (only entities). `backend/app/api/nlp.py`
- `/nlp/analyze` uses the ontology mapper and exposes `coverage_pct` in `structured_context`. `backend/app/services/hybrid_clinical_analyzer.py`
- Extraction tab uses `/nlp/extract`, which is entity-only by design.

Implication
- MVP “near-complete word coverage” can only be met by surfacing ontology mapper output and/or unknown spans.

Recommendations
- Add “Full Coverage” extraction mode in UI backed by `/nlp/ontology/map`.
- Extend `/nlp/ontology/map` response to include unknown token spans or token classifications for gap visualization.

---

## Agent 3 — KG Build Path + Evidence

Findings
- UI KG build uses `/clinical-agent/build-graph`, which accepts pre-extracted entities and discards:
  - low-confidence entities (<0.5)
  - negated entities
  - document persistence (no Document rows created)
- `/nlp/build-graph` uses `OntologyGraphIntegration` which uses the ontology mapper and persists KG nodes/edges, and returns coverage stats. `backend/app/api/nlp.py`, `backend/app/services/ontology_graph_integration.py`
- QA evidence in `/clinical-agent/query` depends on stored Documents; if KG is built from entities only, documents are empty.

Implication
- KG built from entity-only path is lower fidelity and lacks evidence provenance for QA.

Recommendations
- Route UI KG build to `/nlp/build-graph` or extend `/clinical-agent/build-graph` to accept raw text and call `OntologyGraphIntegration`.
- Persist the note text when building KG so QA can cite evidence.
- Do not drop negated entities; mark with assertion.

---

## Agent 4 — QA / Hybrid Reasoner Wiring

Findings
- `/clinical-agent/query/{patient_id}` uses KG nodes and optional documents to build context; it falls back to KG-only if docs missing. `backend/app/api/clinical_agent.py`
- Graph‑Augmented RAG is robust and supports temporal context and policy/guideline evidence. `backend/app/services/graph_augmented_rag.py`
- QA quality is limited when KG built from entity-only path without note persistence.

Recommendations
- Ensure KG build path persists Documents to enable evidence excerpts.
- Route QA context through ontology‑based KG for broader coverage.

---

## Agent 5 — Redundancy + “Awesome Parts”

Keep / Integrate Now
- ClinicalOntologyMapper (token coverage) `backend/app/services/clinical_ontology_mapper.py`
- OntologyGraphIntegration (coverage → KG) `backend/app/services/ontology_graph_integration.py`
- HybridClinicalAnalyzer (grounded LLM) `backend/app/services/hybrid_clinical_analyzer.py`
- GraphAugmentedRAG (multi-hop + temporal) `backend/app/services/graph_augmented_rag.py`
- EnsembleNLPService (multi-model extraction) `backend/app/services/nlp_ensemble.py`

Redundancies / Parallel Pipelines
- `/documents/preview/extract` (rule‑based only) vs `/nlp/extract` vs `/nlp/ontology/map`
- `/clinical-agent/build-graph` (entities-only) vs `/nlp/build-graph` (ontology mapper)
- NLP entity service vs rule-based service vs advanced service and extraction pipeline

Recommendation
- Declare one canonical extraction pipeline for the Workbench and deprecate the others.
