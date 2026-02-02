# Agent Prompt Pack 02 (Model-Aware Orchestration)

Purpose: audit + unify the NLP Workbench pipeline with explicit attention to model selection and coverage.

---

## Coordinator Prompt

Task
You are coordinating a model-aware audit of the NLP Workbench → Hybrid Analyzer → KG → QA pipeline.
Primary goal: ensure the selected model is actually used, and coverage metrics are visible and persisted.

Context
- Use repo maps and specs.
- Focus on the actual UI route used by NLP Workbench.
- Target pipeline: Document → Mention → Mapping → ClinicalFact → KG → QA.

Requirements
- Identify where model selection is ignored or overridden.
- Identify coverage-capable paths and how to surface coverage in UI.
- Deliver a prioritized fix list (max 8 items).

---

## Agent 1: Model Selection Wiring

Task
Verify if model selection (model_id) is honored end-to-end.

Scope
- UI request payloads
- /nlp/extract handler
- Ensemble vs rule-based vs ModernBERT/ClinicalBERT

Output
- Exact locations where model_id is ignored or hard-coded.
- Recommended changes to honor model selection.

---

## Agent 2: Coverage & Extraction Pipeline

Task
Identify which pipeline provides full token coverage and how to expose it in the Workbench.

Scope
- clinical_ontology_mapper
- hybrid_clinical_analyzer
- coverage stats propagation

Output
- How to show coverage_pct + unknown tokens in UI.
- Which endpoint should drive the extraction tab to meet the MVP.

---

## Agent 3: KG Build Path + Evidence

Task
Trace KG build path from UI and confirm document persistence and evidence.

Scope
- /clinical-agent/build-graph
- /nlp/build-graph
- document persistence + provenance

Output
- Gaps preventing QA evidence.
- Recommendation to unify KG build path.

---

## Agent 4: QA / Hybrid Reasoner Wiring

Task
Verify QA endpoints and their dependency on KG + documents.

Scope
- /clinical-agent/query
- Graph RAG + guideline/policy RAG

Output
- Missing inputs from Workbench pipeline.
- Changes needed for grounded QA.

---

## Agent 5: Redundancy + “Awesome Parts”

Task
Identify redundant pipelines and standout components to incorporate.

Scope
- extraction_pipeline, nlp_advanced, value_extraction, relation_extraction
- ensemble vs ontology mapper vs entity service

Output
- Keep / merge / deprecate list
- Top 5 components to integrate now
