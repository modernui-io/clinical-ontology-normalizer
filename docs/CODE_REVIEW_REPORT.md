# Full Codebase Review Report

**Date:** 2026-02-18
**Method:** 10-agent parallel swarm (feature-dev:code-reviewer + silent-failure-hunter)
**Scope:** ~841K LOC — backend (686K) + frontend (155K)
**Focus:** All 8 git-modified files, plus depth-first sampling of largest/most critical files

---

## Executive Summary

| Severity | Count | Action |
|----------|-------|--------|
| **CRITICAL** | 28 | Fix before next merge to main |
| **HIGH** | 49 | Fix before next release |
| **MEDIUM** | 62 | Address in next sprint |
| **LOW** | 47 | Tech debt backlog |
| **Total** | **186** | |

**The most urgent cluster:** The two modified API files (`clinical_agent.py`, `graph_rag.py`) expose all PHI-handling endpoints with **zero authentication**. Combined with Cypher injection vulnerabilities in both files, this is the highest-priority security work. Separately, the `040`/`041` shared concept node migration has a runtime-breaking bug that will crash on first execution.

---

## CRITICAL — Fix Immediately

### Security

**C-SEC-1 · `clinical_agent.py` and `graph_rag.py` — Zero auth on all endpoints**
`backend/app/api/clinical_agent.py` (all endpoints) · `backend/app/api/graph_rag.py` (all endpoints)
Every endpoint in both modified files — import, build-graph, query, graph read/delete, provenance, lineage, patient list, semantic search, patient-summary, answer, traverse — has no `Depends(get_current_user)` or `Depends(require_admin)`. These are the canonical pilot routes handling PHI. Compare with `patients.py`, `phenotypes.py`, `graph.py` which all use auth dependencies.
**Fix:** Add `current_user: CurrentUser = Depends(get_current_user)` to all endpoints in both files. The DELETE and load-sample-data endpoints require `Depends(require_admin)`.

**C-SEC-2 · Cypher injection via f-string interpolation**
`backend/app/api/graph_rag.py:806–810` · `backend/app/api/graph.py:1294–1296`
`vocabulary`, `domain`, and `target_domains` are user-supplied strings directly interpolated into Cypher queries via f-strings (e.g., `f"AND c.vocabulary_id = '{vocabulary}'"`, `f"'{d}'"` for domains). A crafted string like `' OR 1=1 //` escapes the literal and injects arbitrary Cypher.
**Fix:** Use Cypher `$` parameters throughout: `AND c.vocabulary_id = $vocabulary` with the value in the `parameters` dict. Constrain `target_domains` to an enum.

**C-SEC-3 · Auth tokens in localStorage — XSS exfiltration**
`frontend/src/hooks/auth/authStorage.ts:22–32`
Access and refresh tokens are stored in localStorage. Any XSS in the app grants full token access. Multiple pages (`pipelines/page.tsx:74`, `admin/data-sources/page.tsx:75`, `pipelines/openehr/page.tsx:55–67`) read tokens directly from `localStorage` rather than via the auth context.
**Fix:** Migrate to httpOnly cookies set by the backend. Remove all direct localStorage token reads from page components.

**C-SEC-4 · Core API client never attaches auth headers**
`frontend/src/lib/api.ts:267–356`
`fetchWithRetry` — the main API client used by the NLP page and all core calls (documents, patients, facts) — never injects an Authorization header. `authApi.ts` does inject Bearer tokens, but the majority of API calls bypass it.
**Fix:** Add an auth header interceptor to `fetchWithRetry`, or confirm the Next.js `/api` proxy layer adds the header (and document this).

**C-SEC-5 · TenantContext stub in `security.py` always authorizes**
`backend/app/core/security.py:220–231`
`TenantContext.get_tenant_context()` always returns `TenantContext(tenant_id=None)`, making `is_authorized_for()` always return `True`. The real implementation is in `core/tenant.py` but both are exported, creating a silent bypass if the wrong one is injected.
**Fix:** Remove the stub `TenantContext`/`get_tenant_context()` from `security.py`, or add a production guard that raises if called outside dev.

**C-SEC-6 · Auth bypass via client-visible environment variable**
`frontend/src/middleware.ts:62–64`
`NEXT_PUBLIC_AUTH_BYPASS === "true"` completely disables authentication. Since `NEXT_PUBLIC_*` vars are embedded in the client bundle, any visitor can see the bypass is enabled.
**Fix:** Use a server-only env var (no `NEXT_PUBLIC_` prefix), or remove the bypass entirely.

---

### Data Integrity

**C-DAT-1 · Migration 041 will fail at runtime — `updated_at` column does not exist**
`backend/alembic/versions/041_migrate_concept_nodes.py:77–78`
The migration INSERTs into `kg_nodes` with an `updated_at` column, but no migration has ever added `updated_at` to `kg_nodes`. The `Base` class provides only `id` and `created_at`; `SoftDeleteMixin` adds only `deleted_at`. This INSERT will raise `column "updated_at" of relation "kg_nodes" does not exist` on first execution.
**Fix:** Remove `updated_at` from the INSERT statement, or add a preceding step in migration 040 that adds the column.

**C-DAT-2 · Migration 041 downgrade is irreversible and destructive**
`backend/alembic/versions/041_migrate_concept_nodes.py:158–175`
The `downgrade()` function acknowledges (line 168) that edge repointing is not reversed. It then hard-DELETEs canonical shared nodes, which cascade-deletes any edges pointing to them — silently destroying cross-patient edge data. Edges that were repointed from per-patient IDs to canonical IDs are left orphaned.
**Fix:** Either (a) store original `source_node_id`/`target_node_id` before repointing and restore on downgrade, or (b) raise `NotImplementedError` in `downgrade()` and mark the migration explicitly as non-reversible.

**C-DAT-3 · Migration 040 downgrade will fail on non-nullable alter**
`backend/alembic/versions/040_shared_concept_nodes.py:65`
`downgrade()` executes `op.alter_column("kg_nodes", "patient_id", nullable=False)`. If any rows exist with `patient_id IS NULL` (shared concept nodes), this ALTER fails with a NOT NULL constraint violation.
**Fix:** Add `DELETE FROM kg_nodes WHERE patient_id IS NULL` (or a soft-delete) before the `alter_column` call.

**C-DAT-4 · ORM cascade on shared concept nodes destroys cross-patient edges**
`backend/app/models/knowledge_graph.py:68–79`
`KGNode` has `cascade="all, delete-orphan"` on both `outgoing_edges` and `incoming_edges`. For a shared concept node (`patient_id=NULL`), this cascade would hard-delete all connected edges across all patients, bypassing the soft-delete pattern.
**Fix:** Change cascade to `"save-update, merge"` and handle deletions explicitly via the soft-delete pattern.

---

### Clinical Safety

**C-CLIN-1 · Framingham CVD risk formula is wrong — sex-specific point tables are identical**
`backend/app/services/clinical_calculators.py:693–699, 733–734`
All cholesterol and smoking point branches evaluate to the same value regardless of sex (e.g., `tc_pts = 1 if female else 1`, `smoke_pts = 3 if female else 3`). The actual Framingham point table (2008 General CVD paper) has different values by sex. Women receive male cholesterol and smoking points, producing incorrect 10-year risk estimates.
**Fix:** Implement sex-specific point tables per the 2008 Framingham General CVD paper. Also note that `calculate_framingham` is not wired into the canonical service (`clinical_calculator_service.py:2373` has `"function": None`), so calling it via the service raises `ValueError`.

**C-CLIN-2 · Division by zero on zero-value inputs in calculators**
`backend/app/services/clinical_calculators.py:138–211` (BMI) · `:411–441` (eGFR) · `:3175` (QTc)
- BMI: `weight_kg / (height_m ** 2)` — no guard on `height_cm=0`
- eGFR CKD-EPI 2021: `scr_ratio = creatinine / kappa`; with `creatinine=0` and negative `alpha`, produces `ZeroDivisionError`/math domain error
- QTc Bazett: `rr_interval = 60 / heart_rate` — no guard on `heart_rate=0`
**Fix:** Validate inputs `> 0` at function entry for all three calculators.

**C-CLIN-3 · CHA2DS2-VASc accepts `age=0` default — silently under-scores stroke risk**
`backend/app/services/clinical_calculators.py:218–219`
`age: int = 0` as default means a patient whose age was not captured gets age points suppressed, potentially producing a score of 0 for a patient with actual AFib risk factors.
**Fix:** Make `age` required (no default), or raise `ValueError` if age is 0 or clinically implausible for an AFib patient.

---

### Runtime Crashes

**C-RUN-1 · `AssertionStatus.UNCERTAIN` does not exist — crashes NLP endpoint**
`backend/app/api/nlp.py:668`
The `AssertionStatus` enum has no `UNCERTAIN` member. When the ML ensemble path is taken, this line raises `AttributeError`, crashing the entire extraction request.
**Fix:** Change `AssertionStatus.UNCERTAIN` to `AssertionStatus.POSSIBLE`.

**C-RUN-2 · PhenotypeEngine singleton caches stale SQLAlchemy session**
`backend/app/services/phenotype_engine.py:833–848`
`get_phenotype_engine()` stores the first-ever instance with its original `session` globally. Subsequent calls with a different/fresh session silently use the original (closed/expired) session, causing `DetachedInstanceError` on all subsequent phenotype queries.
**Fix:** Remove the singleton pattern, or accept `session` per-call rather than at construction time.

**C-RUN-3 · Phenotype engine silently returns zero matches for all patients after migration**
`backend/app/services/phenotype_engine.py:556–559`
`_evaluate_criterion` queries `KGNode.patient_id == patient_id`, but shared concept nodes (created by the 040/041 migration) have `patient_id=NULL`. After migration, this condition will never match shared concept nodes, making all phenotype evaluations (HFrEF, T2DM, CKD 3+) return `ABSENT` or `INSUFFICIENT_DATA` for every patient.
**Fix:** Route the join through `KGEdge.patient_id == patient_id` to reach shared concept nodes via their edges, mirroring the pattern in `graph_builder_db.py:get_nodes_for_patient()`.

**C-RUN-4 · `ContextVar` mutable default leaks degradation state across requests**
`backend/app/core/degradation_context.py:22–23`
`ContextVar(default=[])` uses a shared mutable list as the default. The guard at lines 51–53 (`if not components`) fails when the list has been mutated by a previous request — a new request can append to the polluted shared default list rather than getting a fresh one.
**Fix:** Use `default=None` and lazily create lists on first access. Or ensure `DegradationContext.reset()` is called at the start of every request via middleware.

---

### XSS

**C-XSS-1 · FHIR export embeds unsanitized entity text in HTML**
`frontend/src/app/nlp/page.tsx:1379`
`div: \`<div>${entity.text}</div>\`` inserts unsanitized, user-extracted entity text into a FHIR Bundle's `text.div` field. A clinical note containing an XSS payload creates a stored XSS vector when the bundle is re-imported into any system that renders `text.div`.
**Fix:** HTML-escape `entity.text` before embedding, or use a safe serializer.

---

### Test Coverage

**C-TEST-1 · All 5 actively modified backend service files have zero test coverage**
`narrative_extractor.py`, `graph_augmented_rag.py`, `ontology_graph_integration.py`, `graph_rag.py` (API), `document_processing.py` (job) — all modified in the current working tree and all lack a corresponding test file.
**Fix:** Create test files for each before merging. Minimum coverage: happy path, failure injection, edge cases (empty input, missing dependencies).

**C-TEST-2 · Old graph builder tests contradict new shared concept tests**
`backend/tests/test_graph_builder.py:381` · `backend/tests/test_graph_builder_db.py:364` vs `backend/tests/test_shared_concept_kg.py:387`
Old tests assert `assertion`, `is_negated`, `is_uncertain` are in `node.properties`. The new untracked test explicitly asserts they are NOT in `node.properties` but ARE in `edge.properties`. These will produce contradictory pass/fail signals.
**Fix:** Update `test_graph_builder.py` and `test_graph_builder_db.py` to reflect the new model.

---

## HIGH — Fix Before Next Release

### Security & Auth

**H-SEC-1 · `X-Forwarded-For` trusted without proxy validation — rate limit bypass**
`backend/app/api/middleware/rate_limit.py:410–413`
Any client can spoof the header to rotate fake IPs and bypass per-IP rate limits.
**Fix:** Validate against a `TRUSTED_PROXIES` config; fall back to `request.client.host` when not from a trusted proxy.

**H-SEC-2 · API keys cached forever — rotation requires restart**
`backend/app/core/security.py:39–59`
`@lru_cache` with no TTL means rotated API keys require a full application restart. Operationally unacceptable for a healthcare system.
**Fix:** Add a TTL-based cache or a SIGHUP-triggered invalidation mechanism.

**H-SEC-3 · Legacy `require_api_key()` is a no-op**
`backend/app/core/auth.py:47–58`
Any endpoint using `Depends(require_api_key)` from the deprecated module gets zero authentication enforcement.
**Fix:** Raise `NotImplementedError` redirecting to the canonical module, or delegate to `security.py:verify_api_key`.

**H-SEC-4 · PHI query params on POST endpoints**
`backend/app/api/graph_rag.py:362–367, 965–969`
`patient_id` and `question` on POST endpoints are query parameters — logged in server access logs and browser history.
**Fix:** Move to a request body model.

**H-SEC-5 · Exception details leaked to API clients**
`backend/app/api/graph_rag.py:852–858, 956–962` · `backend/app/api/clinical_agent.py:1156–1158, 3064`
Raw `str(e)` returned in error responses could expose DB connection strings, stack traces, or API keys.
**Fix:** Return a generic error message; log the full exception server-side.

**H-SEC-6 · Unauthenticated cache-clear and sample-data endpoints**
`backend/app/api/graph.py:583–595, 1106–1141`
Cache clearing is a DoS vector; loading sample data mutates the Neo4j graph. No auth on either.
**Fix:** Add `current_user: CurrentUser = Depends(require_admin)`.

**H-SEC-7 · Missing auth guards on PHI-handling frontend pages**
`frontend/src/app/exchange/page.tsx` · `frontend/src/app/cohorts/builder/page.tsx` · `frontend/src/app/quality/page.tsx` · `frontend/src/app/search/semantic/page.tsx` · `frontend/src/app/llm/finetuning/page.tsx`
None use `useRequireAuth()`. The exchange page handles patient search (PHI) with no auth guard.
**Fix:** Add `useRequireAuth()` to all non-public clinical pages.

### Data / Graph

**H-DAT-1 · JSON vs JSONB mismatch in ORM — JSONB operators will fail**
`backend/app/models/knowledge_graph.py:56–59, 169`
`KGNode.properties` and `KGEdge.properties` declare `JSON` in SQLAlchemy while the actual DB columns (from migration 004) are `JSONB`. GIN indexes and JSONB operators (`@>`, `?`) cannot be used via the ORM.
**Fix:** Change to `JSONB` from `sqlalchemy.dialects.postgresql`.

**H-DAT-2 · Migration chain branch (016/016b) appears unintentional**
`backend/alembic/versions/016_create_rbac_tables.py` · `backend/alembic/versions/016_create_calculator_tables.py`
Both have `down_revision = "015"`, creating a branch. Calculator migration 016 becomes a dead-end relative to the RBAC branch that 017 depends on.
**Fix:** Verify and linearize the chain; make 016b depend on 016 or vice versa.

**H-DAT-3 · SOFA cardiovascular dead code overwrites actual scoring**
`backend/app/services/clinical_calculators.py:1848–1953`
A complex but ineffective first attempt at cardiovascular scoring (lines 1927–1940) is immediately overwritten by a simplified block (lines 1943–1952). The dead code is confusing and a maintenance hazard.
**Fix:** Delete lines 1927–1940.

**H-DAT-4 · APACHE II temperature scoring missing a bin — scores 0 when should be 1**
`backend/app/services/clinical_calculators.py:1556–1571`
Temperature range 38.0–38.4°C is not handled; it falls through to the `>=36` bin (0 points) instead of the correct 1 point per the APACHE II APS table.
**Fix:** Add `elif temperature >= 38: temp_pts = 1` for the 38.0–38.4 range.

**H-DAT-5 · HEDIS Breast Cancer Screening incorrectly excludes cancer history**
`backend/app/services/quality_measures.py:519–522`
C50 (breast cancer history) is in `exclusion_diagnoses`, but HEDIS-BCS excludes bilateral mastectomy only — not cancer history. Eligible patients are incorrectly excluded.
**Fix:** Remove C50 from `exclusion_diagnoses`; keep only bilateral mastectomy codes.

### Graph / RAG

**H-GRAPH-1 · N+1 query in negated node lookup**
`backend/app/services/graph_builder_db.py:762–783`
For each negated edge, `get_node_by_id` is called individually.
**Fix:** Batch-fetch with a single `WHERE KGNode.id IN (...)` query.

**H-GRAPH-2 · `edges_created` counter undercounts when shared concept node already exists**
`backend/app/services/graph_builder_db.py:522–525`
`edges_created` is only incremented when a node is newly created. When the shared concept node already exists (e.g., second patient's build), edges are created but not counted.
**Fix:** Increment `edges_created` independently of `node_exists`.

**H-GRAPH-3 · BFS traversal in RAG has no cycle detection**
`backend/app/services/graph_augmented_rag.py:477–537` (async) and `:617–678` (sync)
Cycles in the graph (e.g., Drug→Condition→Drug via treat/treated-by) cause redundant paths and unnecessary DB load up to `max_hops`.
**Fix:** Pass a `visited: set[str]` through the recursion.

**H-GRAPH-4 · `temporality` type mismatch causes `PatientGraph` serialization failures**
`backend/app/schemas/knowledge_graph.py:178` vs `backend/app/models/knowledge_graph.py:226`
Pydantic schema uses the `Temporality` enum; ORM model uses `Mapped[str | None]`. Passing a raw DB string into `PatientGraph` (which expects the enum) raises a Pydantic validation error at runtime.
**Fix:** Use `Enum(Temporality, ...)` in the ORM column, or convert at the serialization boundary.

### Frontend

**H-FE-1 · No error boundaries on any large page**
All 11 reviewed large pages lack React error boundaries. A runtime error crashes the entire page to a white screen.
**Fix:** Add `error.tsx` files for each route per Next.js App Router conventions.

**H-FE-2 · WebSocket reconnect causes infinite re-render loop**
`frontend/src/hooks/use-websocket.ts:308, 331–340`
`reconnectAttempts` is in both `connect`'s closure and its dependency array. The `onclose` handler increments it via `setState`, which recreates `connect`, which triggers the `useEffect`, which disconnects and reconnects infinitely. Additionally, the stale closure means `reconnectAttempts < maxReconnectAttempts` always reads the initial value.
**Fix:** Use a ref for `reconnectAttempts` and remove it from the dependency array.

**H-FE-3 · Silent mock/simulation fallbacks indistinguishable from real data**
`frontend/src/app/pipelines/openehr/page.tsx:1785–1793` · `frontend/src/app/exchange/page.tsx:561–571` · `frontend/src/app/federated/page.tsx:700–706`
API failures silently fall back to `simulateImport()` or static mock data with no user notification. In a clinical tool, fake data could be mistaken for real patient data.
**Fix:** Show a visible "Demo Mode" banner when simulation is active. Consider a global indicator.

**H-FE-4 · `asyncio.gather` without `return_exceptions=True` kills all parallel queries**
`backend/app/services/async_query_executor.py:479`
A single transient query failure in a parallel batch raises and cancels all other tasks.
**Fix:** Add `return_exceptions=True` and handle individual exception results, or document as intentional fail-fast and ensure all callers handle it.

---

## MEDIUM — Address in Next Sprint

### Backend

**M-BE-1 · Security headers not applied to error responses**
`backend/app/main.py:858–917`
`SecurityHeadersMiddleware` runs after `ErrorHandlerMiddleware`, so error responses are sent without security headers.
**Fix:** Move `SecurityHeadersMiddleware` to execute after `ErrorHandlerMiddleware` in the response path.

**M-BE-2 · Idempotency store is in-memory only**
`backend/app/middleware/idempotency_middleware.py:45–66`
In multi-process or multi-node deployments, idempotency keys are not shared — duplicate requests on different instances both execute.
**Fix:** Use a Redis-backed idempotency store for production.

**M-BE-3 · FAMILY_HISTORY and HISTORICAL assertion mapping inverts clinical meaning**
`backend/app/api/nlp.py:804–805`
`FAMILY_HISTORY` → `Assertion.PRESENT` (without experiencer=FAMILY) means a family member's condition appears as the patient's active condition. `HISTORICAL` → `Assertion.ABSENT` means a past condition is recorded as never having occurred.
**Fix:** Map `FAMILY_HISTORY` to `Assertion.PRESENT` with `experiencer=Experiencer.FAMILY`; map `HISTORICAL` to `Assertion.PRESENT` with `temporality=Temporality.PAST`.

**M-BE-4 · Negation scope offset wrong after context truncation**
`backend/app/services/nlp_entity/nlp_entity_normalizers.py:376`
`match.start()` is relative to the truncated string but `context_start` still refers to the original window start. The formula produces offsets that are too low when context has been trimmed.
**Fix:** Update `context_start` after each truncation step.

**M-BE-5 · `duplicate key "insulin"` in treatment map**
`backend/app/api/clinical_agent.py:1803, 1880`
`"insulin"` appears twice in the treatment map dict. Python silently keeps the last value, losing "type 1 diabetes" from the first entry.
**Fix:** Merge both entries.

**M-BE-6 · `list_patients_with_graphs` may include shared concept nodes (`patient_id=NULL`)**
`backend/app/api/clinical_agent.py:3369–3396`
The query groups by `KGNode.patient_id` without filtering `WHERE patient_id IS NOT NULL`.
**Fix:** Add `.where(KGNode.patient_id.isnot(None))`.

**M-BE-7 · `require_api_key()` parameter uses deprecated `regex=` syntax**
`backend/app/api/clinical_agent.py:2244`
FastAPI/Pydantic v2 uses `pattern=` not `regex=`. This may silently skip validation.
**Fix:** Change to `pattern=` or use `Literal["none", "summary", "full"]`.

**M-BE-8 · Narrative extractor singleton has no thread safety**
`backend/app/services/narrative_extractor.py:639–648`
Unlike other singletons in the codebase, `get_narrative_extractor()` has no lock around the `global` assignment.
**Fix:** Add a `threading.Lock()`, matching the pattern in `get_nlp_entity_service`.

**M-BE-9 · Double-commit pattern in NLP ingestion**
`backend/app/api/nlp.py:1904–1912`
`ingest_note()` commits internally, then `build_knowledge_graph` commits again. Transaction ownership is unclear.
**Fix:** Remove the internal commit from `ingest_note()` and let callers manage the transaction.

**M-BE-10 · Deprecated CPT code 99201 still in quality measures numerator**
`backend/app/services/quality_measures.py:912`
CPT 99201 was eliminated in 2021.
**Fix:** Remove from numerator procedure codes.

**M-BE-11 · ORM `Enum` vs `String` mismatch on `temporality`, `temporal_order`, `assertion`**
Multiple models use `String(20)` for enum-typed fields, meaning any string can be stored in the DB regardless of schema-layer validation.
**Fix:** Use `Enum(EnumClass, ...)` column types or add CHECK constraints.

**M-BE-12 · `_get_omop_concept_id` always returns None — shared node dedup is disabled**
`backend/app/services/ontology_graph_integration.py:270–278`
The placeholder always returns `None`, so all concept nodes are created as patient-specific rather than shared. The shared concept node infrastructure from 040/041 is inert until this is implemented.
**Fix:** Implement the OMOP vocabulary lookup or add a clearly visible TODO banner in the code.

**M-BE-13 · Worker processes do not integrate with `DegradationContext`**
`backend/app/jobs/document_processing.py` (all stages)
`DegradationContext` uses `ContextVar` which is async-request-scoped. Worker processes never benefit from it. Graph build failures (line 323) and cache invalidation failures (line 349) are logged but not tracked in any structured degradation store.
**Fix:** Add a worker-scoped degradation tracker (e.g., write to the job audit log with structured degradation fields).

**M-BE-14 · `PatientGraph.model_post_init` uses `object.__setattr__` anti-pattern**
`backend/app/schemas/knowledge_graph.py:234–237`
Bypasses Pydantic v2 validation. Use `@computed_field` instead.

### Frontend

**M-FE-1 · Inconsistent data-fetching — raw `fetch()` vs React Query**
`openehr/page.tsx`, `llm/finetuning/page.tsx`, `quality/page.tsx`, `settings/page.tsx`, `search/semantic/page.tsx` use raw `fetch()` with manual state. Pages using raw fetch lack retry, cache invalidation, and request deduplication.
**Fix:** Standardize on React Query. Create shared hooks in `frontend/src/hooks/api/`.

**M-FE-2 · D3 KG visualization: entire simulation recreated on any state change**
`frontend/src/components/KnowledgeGraph/GraphCanvas.tsx:74–956`
880-line `useEffect` with 16 dependencies and a suppressed exhaustive-deps lint rule. Any state change triggers full D3 simulation restart. Array spreading in canvas tick handler (`[...nodeData]`) allocates ~600K arrays/sec at 60 fps with 10K nodes.
**Fix:** Break into smaller hooks; use refs for frequently-changing values; remove spread in tick handler.

**M-FE-3 · WebSocket default uses `ws://` (not `wss://`)**
`frontend/src/hooks/use-websocket.ts:144–147`
Hardcoded `ws://` with port 8000 fails in TLS production deployments.
**Fix:** Use `wss://` when `window.location.protocol === 'https:'`.

**M-FE-4 · Missing form validation on JSON textarea and numeric inputs**
`openehr/page.tsx:1748` · `llm/finetuning/page.tsx:663–676` · `federated/page.tsx:530–539`
`JSON.parse()` without schema validation, `parseInt()` without NaN checks, and submit handlers with no validation.

**M-FE-5 · `alert()` used for user feedback in PHI-handling exchange page**
`frontend/src/app/exchange/page.tsx:604, 609, 616`
Replace with toast notifications (`sonner` already used in `settings/page.tsx`).

---

## LOW — Tech Debt Backlog

*(Selected items — full list in agent reports)*

- **Middleware CORS redirect handles GET only** despite 308 status (method-preserving): `backend/app/main.py:1247–1256`
- **API-key-only auth bypasses RBAC entirely** — any valid API key gets admin-equivalent access: `backend/app/core/permissions.py:242–253`
- **No `updated_at` index on `kg_edges.fact_id`** — full-table scans for edge-by-fact queries: `backend/app/models/knowledge_graph.py:164–168`
- **`Mention` model lacks `SoftDeleteMixin`** — mentions are hard-deleted, inconsistent with PHI compliance pattern on other models
- **Embedding columns use `ARRAY(Float)`** — consider `pgvector` for production-scale semantic search
- **Deprecated CKD-EPI race-coefficient formula still callable** in `calculator_definitions.py:7633`
- **`parseInt(e.normalized_codes[0].code)` produces NaN** for alphanumeric ICD-10 codes: `frontend/src/app/nlp/page.tsx:1775`
- **`useNLP.ts` is an empty placeholder** — NLP page makes direct `api.ts` calls with no React Query caching
- **`investors/page.tsx` (3,251 LOC)** — 20+ component functions in one file; pure static marketing, no data fetching
- **~55% of backend tests assert only status code 200** with no response body validation
- **Only 2.2% frontend page coverage** (4 of 180 pages) and 10% component coverage (7 of 69)
- **MD5 used for KG cache key generation**: `backend/app/api/graph.py:1275` — use SHA-256

---

## Cross-Cutting Patterns

### Pattern 1: The "Pilot" API files lack the safety practices of "Production" API files
The two modified pilot files (`clinical_agent.py`, `graph_rag.py`) are missing auth, rate limiting, parameterized queries, and error sanitization that the production files (`patients.py`, `graph.py`, `phenotypes.py`) all implement. The pattern is consistent enough to suggest these files were developed in a separate context without the production conventions.

### Pattern 2: Shared concept node refactor is incomplete
The 040/041 migrations and `graph_builder_db.py` changes introduce shared concept nodes, but three related subsystems have not been updated: (a) `phenotype_engine.py` still queries by `patient_id` and will miss shared nodes, (b) `ontology_graph_integration.py._get_omop_concept_id` always returns `None` so no shared nodes are actually created by the NLP path, and (c) old graph builder tests contradict the new edge-based assertion model.

### Pattern 3: `except Exception: pass` concentrated in scaffold-tier services
The broad grep found ~30 `except: pass` blocks. The majority are in scaffold-tier services (IAC, webhooks, config), not production/pilot paths. The most concerning non-scaffold instances are `calculator_kg_integration.py:157`, `terminology_cache.py:387`, and four consecutive silent swallows in `coding_assistant_service.py:402–426`.

### Pattern 4: @lru_cache on security-critical functions
`get_api_keys()`, `get_tenant_patient_mapping()`, and similar security functions use `@lru_cache` with no TTL. Credential rotation requires a full restart — operationally unacceptable for a HIPAA-adjacent system.

### Pattern 5: Frontend pages built before auth/error infrastructure matured
Pages appear to have been built before `useRequireAuth()` and error boundaries became standard. The `settings/page.tsx` and `cohorts/builder/page.tsx` are reference implementations that demonstrate the correct pattern; all other large pages should be brought up to the same standard.

---

## Recommended Fix Sequence

### This week (Critical)
1. Add auth to all `clinical_agent.py` and `graph_rag.py` endpoints
2. Fix Cypher injection in `graph_rag.py` and `graph.py`
3. Fix `updated_at` bug in migration 041 before anyone runs it
4. Fix `AssertionStatus.UNCERTAIN` (one-line fix, crashes NLP)
5. Fix `PhenotypeEngine` singleton stale session
6. Fix `PhenotypeEngine._evaluate_criterion` to join via edges for shared nodes
7. Fix Framingham sex-specific point tables
8. Add zero/negative input guards to BMI, eGFR, QTc calculators
9. Migrate auth tokens from localStorage to httpOnly cookies (or confirm proxy handles)
10. Fix `ContextVar` mutable default in `degradation_context.py`

### Before next release (High)
- Auth guards on all PHI-handling frontend pages
- Error boundaries via `error.tsx` per route
- Fix WebSocket reconnect infinite loop
- Fix `temporality` type mismatch (Pydantic enum vs ORM string)
- Fix `edges_created` counter bug in graph builder
- Fix N+1 queries in negated node lookup and RAG BFS traversal
- Fix APACHE II temperature scoring bin gap
- Fix HEDIS BCS exclusion (remove C50)
- Sanitize exception messages in API responses
- Write tests for all 5 zero-coverage modified files

### Next sprint (Medium)
- Standardize data fetching on React Query
- Fix FAMILY_HISTORY/HISTORICAL assertion mapping
- Fix negation scope offset after context truncation
- Implement `_get_omop_concept_id` or remove shared-node infra stubs
- Integrate worker processes with structured degradation tracking
- Fix `wss://` for WebSocket in TLS environments

---

## Agent Coverage Map

| Agent | Domain | Files Reviewed | Critical | High | Medium | Low |
|-------|--------|----------------|----------|------|--------|-----|
| 1 | Core Infrastructure | core/**, middleware/**, main.py, jobs/** | 3 | 5 | 7 | 6 |
| 2 | Data Layer | models/**, migrations, key schemas | 3 | 4 | 7 | 5 |
| 3 | API Layer | Top 15 endpoints by LOC | 3 | 7 | 7 | 7 |
| 4 | NLP Pipeline | narrative_extractor, nlp_entity/**, mapping*, nlp.py | 2 | 3 | 5 | 5 |
| 5 | KG/Graph | graph_builder_db, fact_builder_db, models/kg, schemas/kg, graph.py | 2 | 5 | 6 | 4 |
| 6 | Clinical Services | calculators, cpt_suggester, quality_measures, value_set | 3 | 7 | 8 | 6 |
| 7 | Frontend Core | api.ts, hooks/**, KG components, nlp/page.tsx | 3 | 4 | 7 | 5 |
| 8 | Frontend Pages | Top 11 pages by LOC | 0 | 4 | 5 | 4 |
| 9 | Test Coverage | 20 largest backend tests, all 20 frontend tests | 6 | 5 | 5 | 2 |
| 10 | Silent Failures | All 8 modified files + core safety envelope | 3 | 5 | 5 | 3 |
| **Total** | | | **28** | **49** | **62** | **47** |

*Note: Issues flagged by multiple agents (e.g., PhenotypeEngine by agents 4 and 10; migration 041 by agents 2 and 5) are deduplicated in the body of this report.*
