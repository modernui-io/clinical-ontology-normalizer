# Wiring Audit 03: NLP Workbench → Hybrid → KG → QA

Date: 2026-02-02
Scope: UI entrypoints + backend pipeline actually used today.

---

## 1) Canonical Extraction Entrypoint(s)

**UI entry:** `frontend/src/app/nlp/page.tsx`

**Primary API calls from the Workbench**
- Extraction: `POST /api/nlp/extract` (backend: `backend/app/api/nlp.py` → `ClinicalNLPEntityService`)
- Hybrid analysis: `POST /api/nlp/analyze` (backend: `backend/app/api/nlp.py` → `HybridClinicalAnalyzer`)
- Full coverage mode: `POST /api/nlp/ontology/map` (backend: `backend/app/api/nlp.py` → `ClinicalOntologyMapper`)
- Build KG: `POST /api/nlp/build-graph` (backend: `backend/app/api/nlp.py` → `OntologyGraphIntegration`)
- QA: `POST /api/clinical-agent/query/{patient_id}` (backend: `backend/app/api/clinical_agent.py`)

**Canonical path (MVP):**
1. `POST /nlp/extract` → entity extraction + coverage + gap report
2. (optional) `POST /nlp/analyze` → hybrid reasoning grounded in extraction
3. `POST /nlp/build-graph` → persists Document + KG for QA evidence
4. `POST /clinical-agent/query/{patient_id}` → QA over KG + documents

---

## 2) Coverage Metric + Current Gaps

**Coverage definition (MVP):** extracted token coverage = `extraction_covered_tokens / total_tokens`.

**Current coverage tooling:**
- `/nlp/extract` can return `coverage` + `coverage_gap` (token-level gap report).
- `/nlp/ontology/map` returns full token classification + unknown tokens when requested.

**Observed gap types (from gap report):**
- **Ontology-only tokens**: clinical tokens classified by ontology but missed by extraction.
- **Extraction-only tokens**: tokens extracted as entities but not classified as ontology entities.

---

## 3) Wiring: What’s Connected vs Orphaned

**Connected / Used by UI today**
- `frontend/src/app/nlp/page.tsx` → `/nlp/extract`, `/nlp/analyze`, `/nlp/ontology/map`, `/nlp/build-graph`, `/clinical-agent/query/{patient_id}`
- `backend/app/services/ontology_graph_integration.py` is the KG path used by the Workbench.

**Orphaned / Parallel Paths**
- `/documents/preview/extract` (rule-based preview pipeline) — not used by Workbench.
- `/clinical-agent/build-graph` — entities-only graph builder; not used by Workbench and drops negated/low-confidence entities.
- Multiple extraction paths overlap (rule-based extractor, ML models, ensemble, ontology mapper) without a single orchestration layer.

---

## 4) Prioritized Fix List (max 8)

1) **Declare one canonical pipeline** for the Workbench and document it (avoid UI falling into alternate paths).
2) **Deprecate or re-route `/clinical-agent/build-graph`** to call `OntologyGraphIntegration` when raw text is available.
3) **Unify coverage + gap reporting** into Workbench defaults (done in `/nlp/extract`; make it the standard view).
4) **Ensure QA evidence is always available** by persisting Documents when building KG (already handled in `/nlp/build-graph`).
5) **Add a single “one-click” flow** in the UI: Extract → Build KG → QA tab with shared patient_id.
6) **Make model selection explicit** in UI (ensure `model_id` is passed and reflected in results).
7) **Reduce duplicate extraction endpoints** or clearly label them as legacy (e.g., `/documents/preview/extract`).
8) **Standardize provenance metadata** (note_id, encounter_id) across extraction → KG → QA for traceability.
