# Architecture Rationalization Plan (No Deletions)

Date: 2026-02-06
Scope: Clinical Ontology Normalizer (`backend/`, `frontend/`)
Mode: Non-destructive. Freeze/deprecate/quarantine first. Hard deletes are optional and deferred.

## 1. Executive Summary

The platform has a strong clinical core, but it is diluted by a very large API/service surface with mixed maturity.

Measured baseline from this analysis:
- OpenAPI surface: `625` paths, `694` operations.
- API routers mounted via `main.py`: `78`.
- Backend app code: `252,344` Python LOC.
- Backend tests: `62,787` Python LOC.
- Frontend app code: `121,210` TS/JS LOC.
- Frontend tests: `5,679` TS/JS LOC.

The main engineering risk is not missing functionality. It is silent degradation and low-observability fallback behavior in critical response paths.

## 2. Evidence Snapshot

### 2.1 Concentration risk (large critical functions)

From `backend/app/api/clinical_agent.py`:
- `hybrid_query`: `871` lines, `14` `try` blocks, `14` broad `except` handlers.
- `_build_patient_knowledge_graph`: `644` lines.

From `backend/app/main.py`:
- `prewarm_all_services`: `224` lines, `27` broad `except` handlers.

### 2.2 Silent-failure patterns

Global pattern scan (`backend/app/**/*.py`) found:
- `except Exception` categorized as:
  - `277` log-and-fallback blocks,
  - `26` explicit `pass`,
  - `6` `return {}` fallbacks,
  - `5` `return None` fallbacks.

High-impact examples:
- `backend/app/api/clinical_agent.py:2317` uses `except Exception: pass` in policy retrieval block.
- `backend/app/api/clinical_agent.py:2368` uses `except Exception: pass` while recording guideline provenance.
- `backend/app/services/guideline_rag_service.py:135` marks `_loaded = True` when fixture is missing.

### 2.3 Duplication clusters

NLP cluster (`backend/app/services/`):
- Multiple variants coexist (`nlp_rule_based.py`, `nlp_clinical_ner.py`, `nlp_modernbert_ner.py`, `nlp_ensemble.py`, `nlp_advanced.py`) plus package-based `nlp_entity/*` core and a compatibility wrapper `nlp_entity_service.py`.

Calculator cluster:
- Large overlapping surfaces across `clinical_calculators.py`, `clinical_calculator_service.py`, `calculator_builder.py`, `calculator_definitions.py`, and integration layers.

Graph cluster:
- Overlapping responsibilities across `graph_builder.py`, `graph_builder_db.py`, `graph_database_service.py`, `graph_analytics_service.py`, `graph_augmented_rag.py`, and many `kg_*` services.

### 2.4 Type design friction

- Duplicate `Temporality` enum definitions in:
  - `backend/app/schemas/base.py`
  - `backend/app/schemas/knowledge_graph.py`
- KG model stores `temporality` as raw string:
  - `backend/app/models/knowledge_graph.py` (`String(20)`), not enum-constrained.
- Heavy use of unstructured dictionaries in key contracts:
  - `properties: dict` in KG schemas,
  - calculator and orchestration services use broad `dict[str, Any]` payloads.

### 2.5 API maturity distribution (signal-based)

Signals used:
- Runtime frontend references (`frontend/src`, excluding changelog docs page),
- Backend test path references (`backend/tests`),
- Stub/mock marker density in imported services,
- Broad exception density.

A conservative tiering pass produced:
- `3` clear core-stable prefixes (`/documents`, `/patients`, `/search`)
- `25` active but risk-bearing prefixes (core-or-pilot-with-risk)
- `8` pilot/backend-only prefixes
- `46` scaffold-or-dormant prefixes

This does not mean scaffold features are useless. It means they should be explicitly marked as such and isolated from production critical paths.

## 3. Keep / Consolidate / Freeze (No Deletes)

## 3.1 Keep as canonical production backbone

Keep these paths as the primary runtime spine:
- Document ingestion + patient graph flow:
  - `/documents`, `/patients`, `/clinical-agent`, `/search`, `/nlp`
- Coding support path currently surfaced in UI:
  - `/ai-coding`, `/icd10-suggestions`, `/cpt-suggestions`, `/hcc-analysis`
- Baseline interoperability utility set:
  - `/fhir`, `/valuesets`, `/smart-server` (with maturity flags)

Canonical implementation targets:
- NLP canonical path: `nlp_entity` package + deterministic extraction path used by `api/nlp.py`.
- Calculator canonical path: `calculator_definitions.py` + `calculator_reasoning_service.py`.
- Graph canonical path: `graph_builder_db.py` + `graph_database_service.py` + explicit Graph RAG adapter.

## 3.2 Consolidate (merge behavior, keep compatibility adapters)

- NLP:
  - Keep one deterministic production path and one experimental ML path.
  - Convert other variants into strategy plugins behind a single interface.
- Calculators:
  - Keep data-driven definitions as source of truth.
  - Convert `clinical_calculators.py`/`clinical_calculator_service.py` to compatibility facades over one engine.
- Graph:
  - Separate responsibilities into three bounded modules:
    - Graph storage/query,
    - Graph analytics,
    - Graph RAG enrichment.

## 3.3 Freeze + quarantine first (no deletion)

Freeze as `experimental`/`integration-preview` until production backing systems exist:
- `federated`, `tefca`, `x12`, large parts of `llm_finetuning`, synthetic/federation mock-heavy paths.

Freeze policy:
- Keep endpoints available only behind feature flags and explicit readiness labels.
- Add deprecation headers and docs for old/duplicate routes.
- Stop adding new functionality to frozen routes until promotion criteria pass.

## 4. What To Add (Robustness and Operability)

Additions are the highest ROI because they reduce hidden clinical risk without deleting anything.

### 4.1 Degradation contract (mandatory)

Every critical response should include machine-readable reliability metadata:
- `degraded: bool`
- `degraded_components: list[str]`
- `fallback_used: bool`
- `warnings: list[str]`
- `trace_id: str`

Behavior:
- If graph/guideline/policy/orchestrator/calculator stages fail, response remains usable but explicitly marked degraded.

### 4.2 Error budget and SLOs

Define service-level objectives for core clinical query path:
- Availability SLO for `/clinical-agent/query/*`
- Degradation rate SLO (`% responses with degraded=true`)
- Provenance completeness SLO (`% responses with full expected provenance`)

### 4.3 Structured telemetry and traceability

- Adopt OpenTelemetry semantic logging/tracing conventions.
- Emit per-stage span events for `KG_RETRIEVAL`, `GRAPH_RAG`, `RAG_SEARCH`, `ORCHESTRATOR`, `CALCULATOR`, `LLM`.
- Add counters for each fallback path currently hidden in broad exceptions.

### 4.4 Typed contracts for high-variance payloads

- Replace core `dict[str, Any]` payloads with explicit typed contracts in:
  - KG node/edge properties,
  - calculator integration inputs/results,
  - orchestrator summary payloads.

### 4.5 Explicit API lifecycle controls

- Mark deprecated endpoints in OpenAPI.
- Add HTTP `Deprecation` + `Sunset` headers for frozen routes.
- Publish a route maturity matrix (`core`, `pilot`, `experimental`).

## 5. Standards Alignment (Research-backed)

This direction aligns with current regulatory and standards trajectory:
- CMS Interoperability/Prior Auth Final Rule requires FHIR API capabilities and standards alignment by `January 1, 2027`.
- ONC HTI-1 final rule pushes health IT certification baseline updates (USCDI v3 timeline and algorithm transparency obligations).
- Core interoperability standards are converging on:
  - US Core (`8.0.0` published 2026-02-02),
  - SMART App Launch (`2.2.0`),
  - FHIR Bulk Data Access (`2.0.0`),
  - CDS Hooks (`2.0.1`).

Implication:
- Do not delete integration scaffolding.
- Keep it, but make maturity explicit and operationally safe.

## 6. 4-Phase Execution Plan

### Phase 1: Safety envelope (2 weeks)

Goals:
- Eliminate silent failures on critical query path.

Actions:
- Replace `except Exception: pass` in critical API paths with typed error handling + degradation metadata.
- Add stage-level health and fallback counters.
- Add regression tests proving degraded responses are explicit.

Exit criteria:
- No silent pass in `/clinical-agent`, `/nlp`, `/graph`, `/documents` critical flow.
- New response schema includes degradation metadata.

### Phase 2: Canonicalization (3-4 weeks)

Goals:
- One canonical engine per domain, adapters for legacy entry points.

Actions:
- NLP: harden one deterministic path + one experimental path.
- Calculators: unify execution engine and route all wrappers through it.
- Graph: enforce 3-module boundary (storage, analytics, RAG).

Exit criteria:
- Duplicate services converted to adapters or flagged experimental.
- Contract tests ensure old endpoints still work through adapters.

### Phase 3: Maturity labeling + lifecycle controls (1-2 weeks)

Goals:
- Make route maturity explicit to developers and consumers.

Actions:
- Tag routes as `core`, `pilot`, `experimental` in docs/OpenAPI extensions.
- Add `Deprecation` and optional `Sunset` headers for frozen/legacy routes.
- Add “readiness gates” document for promoting experimental routes.

Exit criteria:
- All routes have a maturity label.
- Frozen routes are discoverable and intentionally separated.

### Phase 4: Type hardening + policy compliance support (3 weeks)

Goals:
- Reduce schema drift and runtime ambiguity.

Actions:
- Unify `Temporality` enum across schemas/models.
- Replace critical `dict[str, Any]` hotspots with typed payload models.
- Add validation for guideline/policy payload structures.

Exit criteria:
- Single temporality representation end-to-end.
- Typed contracts cover KG edge/node properties and calculator I/O.

## 7. Immediate Cut/Add Decisions (Actionable)

Cut now (meaning: stop expanding these, freeze as preview):
- `/federated`, `/tefca`, `/x12`, `/llm/finetune`.

Consolidate now:
- NLP variants into one production + one experimental strategy.
- Calculator services into one engine with compatibility wrappers.
- Graph service sprawl into storage/analytics/RAG boundary.

Add now:
- Degradation contract in core responses.
- Fallback telemetry counters and dashboards.
- API maturity labels and deprecation headers.

## 8. Decision Rule For Future Work

Before adding any new endpoint/service, require:
1. Declared maturity (`core/pilot/experimental`).
2. Owner and promotion criteria.
3. Failure-mode behavior (degrade vs fail-fast).
4. Observability contract (metrics/logs/traces).
5. Typed request/response contract.

If any item is missing, route remains `experimental` by default.

## 9. Why This Is The Right Tradeoff

This plan preserves optionality and prior investment:
- No deletes required.
- Existing integrations remain available as scaffolding.
- Production clinical path becomes safer, more observable, and easier to evolve.

It aligns with current interoperability and governance direction while reducing operational risk immediately.
