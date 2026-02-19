# Codebase Review v2 — Four-Lens Analysis

**Date:** 2026-02-17
**Method:** 8-specialist agent parallel review (2 agents per lens)
**Scope:** ~468K LOC — backend (~345K) + frontend (~123K)
**Lenses:** Performance & Scalability, Architecture & Design Patterns, Observability & Monitoring, HIPAA/PHI Compliance

---

## Executive Summary

| Lens | CRITICAL | HIGH | MEDIUM | LOW | Total |
|------|----------|------|--------|-----|-------|
| Performance & Scalability | 7 | 10 | 13 | 4 | 34 |
| Architecture & Design Patterns | 6 | 8 | 10 | 3 | 27 |
| Observability & Monitoring | 6 | 8 | 8 | 5 | 27 |
| HIPAA/PHI Compliance | 7 | 11 | 9 | 5 | 32 |
| **Totals** | **26** | **37** | **40** | **17** | **120** |

**Top-priority cluster:** The HIPAA CRITICALs represent immediate legal and regulatory risk — unauthenticated export endpoints, disabled auth defaults, plaintext PHI storage, and XSS-accessible auth tokens. These must be remediated before any production deployment.

**Second-priority cluster:** Performance CRITICALs in the GraphRAG and semantic search paths will cause production outages under real patient load — unbounded in-memory loads, N+1 query storms, and 60fps allocation churn on the frontend graph canvas.

---

## Critical Findings (All 26, Deduplicated)

### HIPAA/PHI Compliance — CRITICALs

**H-C1.** SEVERITY: CRITICAL | FILE: backend/app/api/export.py:41-55
ISSUE: Export endpoint has zero auth or authorization — any network caller can export any patient's complete PHI.
DETAIL: Direct violation of HIPAA 45 CFR 164.312(a). No `get_current_user`, no `PermissionChecker`, no `verify_patient_access()`.
FIX: Add `Depends(get_current_user)` + `Depends(PermissionChecker("export","read"))` + `verify_patient_access()`.

**H-C2.** SEVERITY: CRITICAL | FILE: backend/app/core/security.py:51-55
ISSUE: Auth completely disabled when no API keys configured — default deployment is unauthenticated.
DETAIL: If no `API_KEYS` env var is set, all auth checks pass. Production deployments without explicit key configuration are fully open.
FIX: Default `auth_enabled=True`; require explicit `AUTH_ENABLED=false` + `environment=development` to disable.

**H-C3.** SEVERITY: CRITICAL | FILE: backend/app/core/security.py:228-231
ISSUE: `get_tenant_context()` always returns `TenantContext(tenant_id=None)` — universal access granted.
DETAIL: Any route using this dependency has zero patient-level access control. Tenant isolation is effectively non-existent.
FIX: Remove stub; ensure all routes use `tenant.py` implementation with real tenant resolution.

**H-C4.** SEVERITY: CRITICAL | FILE: backend/app/models/document.py:42-45
ISSUE: Clinical note text (PHI) stored as plaintext `Text` column — no column-level encryption.
DETAIL: Volume encryption provides one layer, but SQL injection or DB backup theft exposes all clinical notes in cleartext. No defense-in-depth.
FIX: Column-level encryption via `sqlalchemy-utils` `EncryptedType` or `pgcrypto`.

**H-C5.** SEVERITY: CRITICAL | FILE: frontend/src/hooks/auth/authStorage.ts:32
ISSUE: Auth tokens (access + refresh) stored in `localStorage` — XSS-accessible.
DETAIL: Direct HIPAA 164.312(d) person/entity authentication risk. Any XSS vulnerability exposes session tokens.
FIX: Migrate to httpOnly, Secure, SameSite=Strict cookies managed by backend. Frontend should never handle raw tokens.

**H-C6.** SEVERITY: CRITICAL | FILE: frontend/src/hooks/auth/authApi.ts:21
ISSUE: `has_auth` cookie set without `Secure` flag — transmitted over HTTP.
DETAIL: Cookie can be intercepted on non-HTTPS connections.
FIX: Add `Secure` flag; move cookie management to backend.

**H-C7.** SEVERITY: CRITICAL | FILE: frontend/src/hooks/auth/AuthContext.tsx (entire)
ISSUE: No session idle timeout or auto-logout — direct HIPAA 164.312(a)(2)(iii) violation.
DETAIL: Token expiry not tied to user activity. No idle/inactivity/session_timeout patterns anywhere in codebase.
FIX: Implement idle timeout tracker monitoring mouse/keyboard activity; warning dialog + forced logout after ~15min inactivity.

### Performance & Scalability — CRITICALs

**P-C1.** SEVERITY: CRITICAL | FILE: backend/app/services/graph_augmented_rag.py:477-538
ISSUE: N+1 query in BFS traversal — per-edge SELECT for target nodes.
DETAIL: `_bfs_traverse_async` issues up to 5,000 individual SELECTs per RAG call (5 start nodes x 10 edges x 3 hops). Sync variant at lines 617-678 has the same problem.
FIX: Batch `target_node_ids` with `IN` query per hop level; use `selectinload` on edge-to-target_node.

**P-C2.** SEVERITY: CRITICAL | FILE: backend/app/services/graph_augmented_rag.py:540-591
ISSUE: N+1 in temporal context — fetches 50 edges then per-edge SELECT.
DETAIL: Sync variant at lines 706-756 has the same pattern.
FIX: Pre-fetch all target nodes in one `IN` query before loop.

**P-C3.** SEVERITY: CRITICAL | FILE: backend/app/services/graph_augmented_rag.py:369-409
ISSUE: Unbounded query loads ALL patient nodes into memory for Python-side string matching.
DETAIL: Catastrophic for oncology/chronic disease patients with large graphs. Async variant at lines 411-451 has same issue.
FIX: Push label matching into SQL `WHERE` clause with `ilike()`; add `.limit(20)`.

**P-C4.** SEVERITY: CRITICAL | FILE: backend/app/services/semantic_search.py:83-123
ISSUE: Loads ALL `ClinicalFacts` with embeddings into Python memory for in-memory cosine similarity.
DETAIL: Potentially hundreds of MB per call. No patient_id filter, no limit.
FIX: Use `pgvector <=>` operator or at minimum add `.limit(1000)` + `patient_id` filter.

**P-C5.** SEVERITY: CRITICAL | FILE: frontend/src/components/KnowledgeGraph/GraphCanvas.tsx:168-171
ISSUE: Array spread on every D3 simulation tick (~60fps) — allocates 78,000 objects/sec for 500-node graph.
DETAIL: `simulationNodesRef.current = [...nodeData]` creates new array each tick when D3 mutates in-place.
FIX: Direct assignment without spread — D3 mutates the array in-place.

**P-C6.** SEVERITY: CRITICAL | FILE: frontend/src/components/KnowledgeGraph/GraphCanvas.tsx:74-956
ISSUE: Monolithic 900-line useEffect with 16 dependencies — rebuilds entire D3 simulation on ANY change.
DETAIL: Selected node, label visibility, search filter, hull toggles all trigger full simulation rebuild causing visible stutter.
FIX: Split into (1) simulation-setup effect for nodes/edges/layout; (2) visual-update effect for selection/labels/hulls via refs.

**P-C7.** SEVERITY: CRITICAL | FILE: frontend/src/app/nlp/page.tsx:1679-1702
ISSUE: Sequential waterfall in hybrid analyzer — `nlpOntologyMap` blocks `nlpHybridAnalyze` despite independence.
DETAIL: Adds 200-800ms latency per analysis run.
FIX: `Promise.all([nlpOntologyMap(...), nlpHybridAnalyze(...)])`.

### Architecture & Design Patterns — CRITICALs

**A-C1.** SEVERITY: CRITICAL | FILE: backend/app/api/clinical_agent.py (3,575 LOC)
ISSUE: God file — API layer contains ~2,500 lines of business logic, NLP orchestration, graph construction, OMOP resolution.
DETAIL: Direct raw DELETE/INSERT/SELECT SQL in API handlers. Untestable without full DB + web framework stack.
FIX: Extract `_build_patient_knowledge_graph` into `KGBuildService`; `_create_narrative_nodes` into `NarrativeGraphService`; `compute_evidence_weighted_confidence` into `ConfidenceService`; `_query_omop_relationships` into OMOP service. API file should only parse, call, respond.

**A-C2.** SEVERITY: CRITICAL | FILE: backend/app/api/clinical_agent.py:862,:1117
ISSUE: Direct service instantiation in API handlers — no dependency injection.
DETAIL: `RuleBasedNLPService()`, `DatabaseGraphBuilderService()`, `GraphAugmentedRAGService(db)` created inline. Same pattern in nlp.py:852, patients.py:256,375, documents_core.py:323.
FIX: FastAPI `Depends()` factories in `core/dependencies.py` for all services.

**A-C3.** SEVERITY: CRITICAL | FILE: backend/app/api/graph_rag.py (1,295 LOC)
ISSUE: API layer contains raw SQLAlchemy queries in every endpoint — zero service delegation.
DETAIL: Clinical Q&A logic (lines 362-530+) implements keyword parsing, filtering, answer generation, confidence scoring all inside route handlers.
FIX: Create `GraphRAGQueryService`; endpoints delegate entirely.

**A-C4.** SEVERITY: CRITICAL | FILE: frontend/src/lib/api.ts (4,187 LOC)
ISSUE: Monolithic API client — type definitions, methods, and infrastructure for 15+ domains in one file.
DETAIL: Every import pulls 4,187 lines into the bundle.
FIX: Split into domain modules under `lib/api/` with barrel index; types into `@/types/`; shared infra in `api/client.ts`.

**A-C5.** SEVERITY: CRITICAL | FILE: frontend/src/lib/api.ts + frontend/src/hooks/auth/authApi.ts
ISSUE: `fetchWithRetry` NEVER attaches Authorization headers — all 100+ API functions make unauthenticated requests.
DETAIL: Auth module manages tokens independently via separate `apiFetch` helper. Two parallel HTTP stacks with no integration.
FIX: Inject token retrieval into `fetchWithRetry` or create axios/ky instance with interceptor.

**A-C6.** SEVERITY: CRITICAL | FILE: frontend/src/app/nlp/page.tsx (3,165 LOC)
ISSUE: God page — 6+ direct API calls, 15+ useState, inline transforms, entity rendering, tab management, visualization, markdown all in one component.
DETAIL: `useNLP.ts` hook is explicitly empty ("placeholder").
FIX: Extract data fetching into `hooks/api/useNLP.ts`; split into `EntityViewer`, `ExtractionForm`, `ResultsPanel`.

### Observability & Monitoring — CRITICALs

**O-C1.** SEVERITY: CRITICAL | FILE: backend/app/jobs/document_processing.py:121
ISSUE: Background jobs have no request_id/correlation_id — all log lines have `request_id=null`.
DETAIL: Cannot trace failures across document processing pipeline. `RequestIdContext` exists but is unused.
FIX: Wrap entire `process_document` body in `with RequestIdContext(f"job-doc-{document_id}"):`.

**O-C2.** SEVERITY: CRITICAL | FILE: backend/app/services/ (81 logger.error() calls)
ISSUE: 73% of `logger.error()` calls omit stack traces — 58 of 81 contain only message string.
DETAIL: Notable offenders: graph_database_service.py:317, graph_embedding_service.py (6), nlp_claude_api.py (4), notification_service.py (2), policy_kg_builder.py (3).
FIX: Replace `logger.error(f"...{e}")` with `logger.exception(f"...{e}")` in all exception handlers.

**O-C3.** SEVERITY: CRITICAL | FILE: backend/app/services/observability_service.py (entire)
ISSUE: Distributed tracing is in-memory only — spans stored in a capped Python list. No OTLP/Jaeger export.
DETAIL: On restart: all trace data lost. Multi-worker: traces silently fragmented. W3C TraceContext code exists but is never called from middleware.
FIX: Add OTLP exporter; wire `traceparent` header parsing into `RequestIdMiddleware`.

**O-C4.** SEVERITY: CRITICAL | FILE: frontend/package.json (entire)
ISSUE: No browser error tracking SDK — zero monitoring dependencies (no Sentry, Datadog, LogRocket).
DETAIL: All frontend errors only go to `console.error`, invisible in production.
FIX: Install `@sentry/nextjs` with source maps upload.

**O-C5.** SEVERITY: CRITICAL | FILE: frontend/src/components/ErrorBoundary.tsx:90-106
ISSUE: `handleReportError` is a mock — `console.log` + browser `alert()`. Errors never reach any monitoring service.
FIX: Replace with `Sentry.captureException()` or equivalent.

**O-C6.** SEVERITY: CRITICAL | FILE: frontend/src/components/Providers.tsx:40-42
ISSUE: Production `ErrorBoundary.onError` gated by `NODE_ENV === "development"` — zero information sent anywhere when component tree crashes in production.
FIX: Remove development guard; always forward errors to monitoring service.

---

## Per-Lens Findings

### Performance & Scalability

#### HIGH

**P-H1.** FILE: backend/app/services/graph_builder_db.py:775-796
ISSUE: N+1 in `get_negated_nodes` — loops over `negated_node_ids` calling `get_node_by_id()` each.
FIX: Single `IN` query for all negated_node_ids.

**P-H2.** FILE: backend/app/services/graph_augmented_rag.py:369-409
ISSUE: Python-side `[:20]` slice but DB materializes full result set.
FIX: Add `.limit(100)` to SQL query.

**P-H3.** FILE: backend/app/services/graph_augmented_rag.py:547-554
ISSUE: Temporal edge query missing LIMIT — DB sorts entire set before Python `[:50]` slice.
FIX: Add `.limit(50)` to SQL.

**P-H4.** FILE: backend/app/services/semantic_search.py:282-328
ISSUE: Unbounded query for embedding backfill loads all facts without embeddings.
FIX: Use `yield_per(batch_size)` or paginated offset/limit.

**P-H5.** FILE: backend/app/api/batch.py:291-292
ISSUE: `_batch_jobs` and `_batch_results` module-level dicts never evict — memory leak proportional to job history.
FIX: TTL-based eviction or Redis-backed storage.

**P-H6.** FILE: frontend/src/components/graph/CanvasRenderer.tsx:192-198
ISSUE: O(N*E) linear scan — `nodes.find(n => n.id === edge.source)` called per-edge per-frame.
DETAIL: 1M comparisons/frame at 60fps for 500-node graph.
FIX: Build `Map<string, CanvasNode>` once before render loop.

**P-H7.** FILE: frontend/src/app/ (62 routes)
ISSUE: Only 1 global `loading.tsx` — no per-route loading skeletons for heavy pages.
FIX: Add `loading.tsx` to 5-10 heaviest routes (`/nlp`, `/investors`, `/billing`, etc.).

**P-H8.** FILE: frontend/src/app/ (all pages)
ISSUE: Only 1 route uses `next/dynamic` — 62 routes eagerly load all dependencies including KnowledgeGraph, D3, framer-motion.
FIX: `dynamic()` with `ssr: false` for KnowledgeGraph, D3 components, framer-motion sections.

**P-H9.** FILE: frontend/src/components/KnowledgeGraph/GraphCanvas.tsx:416-434
ISSUE: O(N*M) `nodeData.find()` inside D3 `.attr()` callbacks for edge color/marker.
FIX: Build `nodeMap = new Map(nodeData.map(n => [n.id, n]))` before join.

**P-H10.** FILE: frontend/src/hooks/use-websocket.ts:308-317
ISSUE: `subscribeToJob` calls during reconnect silently dropped; subscriptions not re-sent after reconnect.
FIX: Queue subscriptions in ref during disconnect; flush in `onopen`.

#### MEDIUM

**P-M1.** FILE: backend/app/services/graph_builder_db.py:204-248
ISSUE: Per-edge dedup SELECT before INSERT — hundreds of round trips during `build_graph_for_patient`.
FIX: Cache edge keys in `_prime_caches` or use `INSERT ON CONFLICT DO NOTHING`.

**P-M2.** FILE: backend/app/services/graph_builder_db.py:129-202
ISSUE: Shared concept nodes always SELECT even when cache primed.
FIX: `INSERT ON CONFLICT DO NOTHING RETURNING id`.

**P-M3.** FILE: backend/app/services/graph_builder_db.py:337-387
ISSUE: Two unbounded queries in `get_nodes_for_patient`.
FIX: Add `.distinct()` and safety `.limit(10000)`.

**P-M4.** FILE: backend/app/services/retry_handler.py:255
ISSUE: Synchronous `time.sleep()` in retry handler — blocks event loop if called from async context.
FIX: Provide `execute_async()` variant using `asyncio.sleep()`.

**P-M5.** FILE: backend/app/services/graph_augmented_rag.py:477-538
ISSUE: BFS has no visited-node tracking — allows cycle re-visitation, exponential query multiplication.
FIX: Add `visited: set[str]` parameter.

**P-M6.** FILE: frontend/src/app/nlp/page.tsx:309-394
ISSUE: `HighlightedText` and 5+ other components lack `React.memo` — re-render on every of 20+ parent state changes.
FIX: Wrap in `React.memo`.

**P-M7.** FILE: frontend/src/components/KnowledgeGraph/GraphCanvas.tsx:119-134
ISSUE: O(N^2) node type grouping during setup — `filter()` inside `map()`.
FIX: Pre-group with `Map.groupBy` before map.

**P-M8.** FILE: frontend/src/app/nlp/page.tsx:1552
ISSUE: 2200-line monolithic NLP page with 20 `useState` hooks — any state change reconciles entire tree.
FIX: Split into sub-components with isolated state.

**P-M9.** FILE: frontend/src/app/investors/page.tsx:56-75
ISSUE: `AnimatedCounter` `setInterval` at 60fps with potential overlap on rapid unmount/remount.
FIX: Use `requestAnimationFrame` instead.

**P-M10.** FILE: frontend/src/app/investors/page.tsx:636-644
ISSUE: Raw scroll listener fires on every pixel — 60+ re-renders/sec.
FIX: Throttle to 10-15fps or use `requestAnimationFrame` + `IntersectionObserver`.

**P-M11.** FILE: frontend/src/lib/api.ts (entire)
ISSUE: No request deduplication — identical concurrent calls create duplicate network requests.
FIX: In-flight request cache keyed by URL+method+body.

**P-M12.** FILE: frontend/src/components/ (all)
ISSUE: Zero `React.memo` usage across entire components directory.
FIX: Add memo to leaf components in frequently-updating parents.

**P-M13.** FILE: frontend/src/app/investors/page.tsx:128-151
ISSUE: `TiltCard` recalculates transform on every mousemove via `setState`.
FIX: Use ref + CSS custom properties.

#### LOW

**P-L1.** FILE: backend/app/core/database.py:96-104
ISSUE: `pool_size=20`/`max_overflow=40` adequate now but fragile given N+1 patterns.
FIX: Make configurable via env; add pool exhaustion metrics.

**P-L2.** FILE: backend/app/core/queue.py:52-78
ISSUE: No backpressure on job queue — no max depth check.
FIX: Check queue depth before enqueue; return 429 when full.

**P-L3.** FILE: frontend/src/components/KnowledgeGraph/GraphCanvas.tsx:517-523
ISSUE: Stagger delay proportional to node count — 500 nodes = 15s until last node appears.
FIX: Cap at `Math.min(i * 30, 2000)`.

**P-L4.** FILE: frontend/src/app/investors/page.tsx:128-151
ISSUE: `TiltCard` recalculates transform on every mousemove.
FIX: Use ref + CSS custom properties.

---

### Architecture & Design Patterns

#### HIGH

**A-H1.** FILE: backend/app/main.py (1,380 LOC, 313 routers)
ISSUE: Monolithic router registration — 313 router imports in flat list, all loaded at import time.
FIX: Group into domain sub-applications; lazy registration for scaffold-maturity routers.

**A-H2.** FILE: backend/app/api/clinical_agent.py:1511-1516
ISSUE: Destructive DELETE-then-rebuild in API layer — loses entire patient graph if rebuild fails mid-way.
FIX: Move to service layer with upsert/merge strategy or savepoint rollback.

**A-H3.** FILE: backend/app/services/ (278 files, 421 cross-imports)
ISSUE: 421 service-to-service cross-imports creating tight coupling.
DETAIL: Top offenders: clinical_intelligence_agent.py (11 imports), medication_reconciliation.py (6), coding_assistant_service.py (6).
FIX: Introduce Protocol interfaces; inject via constructors.

**A-H4.** FILE: backend/app/api/patients.py:88,232,359,445 + nlp.py:808,1899,1994
ISSUE: Sync `Session(get_sync_engine())` in async API endpoints — blocks event loop.
DETAIL: Also found in search.py (3), phenotypes.py (4), export.py (1).
FIX: Migrate to `AsyncSession` via `get_db()` dependency; use `run_in_executor()` if sync needed.

**A-H5.** FILE: frontend/src/app/ (25 page files)
ISSUE: 25 pages import directly from `@/lib/api` bypassing React Query hook layer — no caching, deduplication, background refetch.
FIX: Complete hook layer for all domains; migrate all 25 pages to hooks.

**A-H6.** FILE: frontend/src/hooks/api/useSearch.ts (10 LOC) + useNLP.ts (11 LOC)
ISSUE: Empty hook modules — 40% of API surface has no React Query integration.
FIX: Implement hooks for NLP (~8), Search (~6), Cohorts (~12), Notes (~8), Synthetic (~8), AI Coding (~6), Job Queue (~10).

**A-H7.** FILE: frontend/src/components/KnowledgeGraph/useGraphState.ts (586 LOC)
ISSUE: God hook — 30+ state pieces, mixing UI state, data fetching, DOM manipulation, graph computation. Returns 60+ values.
DETAIL: Raw `fetch()` call at line 457 bypasses API client.
FIX: Decompose into `useGraphFilters`, `useGraphLayout`, `useGraphSelection`, `useGraphExport`, `useNodeProvenance`.

**A-H8.** FILE: frontend/src/app/cohorts/builder/page.tsx (1,537) + search/semantic/page.tsx (1,453) + ai-coding/page.tsx (1,124) + synthetic/page.tsx (806) + notes/editor/page.tsx (659)
ISSUE: Multiple god pages with mixed concerns.
FIX: Extract hooks + sub-components per domain.

#### MEDIUM

**A-M1.** FILE: backend/app/api/diagnostics.py:92,114,136,162,238
ISSUE: Config accessed via `os.getenv()` — parallel config channel bypassing Settings validation.
DETAIL: Also in maturity_gate.py, nlp.py, kafka_service.py.
FIX: All config through settings singleton; no `os.getenv()` outside `core/config.py`.

**A-M2.** FILE: backend/app/services/calculator_definitions.py (12,716 LOC)
ISSUE: Largest file in codebase — single file with 12,700+ lines of calculator definitions.
FIX: Split into domain-specific calculator modules under `calculators/` package.

**A-M3.** FILE: backend/app/services/ontology_graph_integration.py:109-117
ISSUE: Direct concrete instantiation of `DatabaseGraphBuilderService` in constructor.
FIX: Accept `GraphBuilderServiceInterface` (Protocol) in constructor.

**A-M4.** FILE: backend/app/services/ (overall)
ISSUE: Three DI patterns coexist: singleton `get_*()`, direct `new`, inline.
FIX: Standardize on singleton `get_*()` for stateless, `Depends()` for request-scoped.

**A-M5.** FILE: frontend/src/lib/api.ts + authApi.ts
ISSUE: Duplicate type definitions between API client and auth module.
FIX: Create `@/types/` directory with domain-specific type files.

**A-M6.** FILE: frontend/src/hooks/use-api.ts + use-auth.tsx
ISSUE: Deprecated re-export shims add import path confusion.
FIX: ESLint `no-restricted-imports` to ban deprecated paths; plan removal.

**A-M7.** FILE: frontend/src/hooks/auth/AuthContext.tsx:304-318
ISSUE: `useRequireAuth` uses `window.location.href` (full reload) instead of Next.js router.
FIX: Use `useRouter().push()`.

**A-M8.** FILE: frontend/src/middleware.ts:62-64
ISSUE: `NEXT_PUBLIC_AUTH_BYPASS` exposed in client-side JS bundle. (Also HIPAA finding H-H11.)
FIX: Remove `NEXT_PUBLIC_` prefix; add production guard.

**A-M9.** FILE: frontend/src/components/KnowledgeGraph/useGraphState.ts:457
ISSUE: Raw `fetch()` call bypasses API client — no retry, no error handling, no base URL config.
FIX: Create `getNodeProvenance()` in `api.ts` + `useNodeProvenance` React Query hook.

**A-M10.** FILE: frontend/src/lib/api.ts + query-client.ts
ISSUE: Double retry: `fetchWithRetry` retries 3x AND React Query retries 3x. Failing request gets up to 12 total attempts.
FIX: Remove retries from `fetchWithRetry` (set to 0); let React Query own retry.

#### LOW

**A-L1.** FILE: backend/app/main.py:356-595
ISSUE: 240-line `prewarm_all_services()` defined but never called (commented out).
FIX: Move to `core/prewarm.py` behind config flag or remove.

**A-L2.** FILE: backend/app/api/clinical_agent.py:66-78
ISSUE: Custom `_PilotRoute` for headers duplicates `MaturityGateMiddleware`.
FIX: Consolidate into middleware.

**A-L3.** FILE: frontend/src/hooks/auth/AuthContext.tsx:304-318
ISSUE: `useRequireAuth` uses `window.location.href` — full reload navigation.
FIX: Use Next.js `useRouter().push()`.

---

### Observability & Monitoring

#### HIGH

**O-H1.** FILE: backend/app/middleware/tracing_middleware.py:226
ISSUE: Sampling misses errors — 90% of non-expensive requests untraced, no "always trace on error" logic.
DETAIL: A 500 error has only 10% chance of being traced.
FIX: Always trace on `status_code >= 500` or `duration > threshold` regardless of sampling.

**O-H2.** FILE: backend/app/api/metrics.py, middleware/metrics.py
ISSUE: Hand-rolled Prometheus format — no `prometheus_client` library. No multiprocess-safe collectors.
FIX: Migrate to standard `prometheus_client` with `MultiProcessCollector`.

**O-H3.** FILE: backend/app/services/ (458 f-string logs vs 695 %-format logs)
ISSUE: Inconsistent structured logging — f-string interpolated values buried in message string, not machine-parseable.
FIX: Standardize on `extra={}` pattern: `logger.info("msg", extra={"count": n, "patient_id": pid})`.

**O-H4.** FILE: backend/app/jobs/document_processing.py:323-326
ISSUE: Graph build failure silently degrades — caught, logged as WARNING, document marked COMPLETED.
DETAIL: No metric emitted, no degradation flag.
FIX: Emit metric for `graph_build_failures`; use `logger.error()` with `exc_info`; add `graph_build_status` field.

**O-H5.** FILE: frontend/src/app/error.tsx:18-22
ISSUE: Root `error.tsx` only logs in development — production sends nothing. "Send to error tracking service" is a TODO comment.
FIX: Add `Sentry.captureException()`; remove TODO.

**O-H6.** FILE: frontend/src/app/ (all routes)
ISSUE: Only one root `error.tsx` — no per-route boundaries. Any unhandled error crashes entire page.
FIX: Add `error.tsx` to `patients/[patientId]/`, `nlp/`, `analytics/`, `clinical/`, `assistant/`, `documents/[documentId]/`.

**O-H7.** FILE: frontend/src/app/global-error.tsx (MISSING)
ISSUE: No `global-error.tsx` — root layout errors crash to browser default with no reporting.
FIX: Create `global-error.tsx` with minimal HTML + error reporting.

**O-H8.** FILE: frontend/src/ (entire)
ISSUE: No Web Vitals instrumentation — LCP, FID/INP, CLS unmeasured.
FIX: Add `web-vitals` package + `reportWebVitals` in `instrumentation.ts`.

#### MEDIUM

**O-M1.** FILE: backend/app/api/health.py:209-297
ISSUE: DB health check doesn't reliably detect pool exhaustion.
FIX: Pre-flight pool capacity check before acquiring session.

**O-M2.** FILE: backend/app/core/degradation_context.py:6-8
ISSUE: Telemetry counters declared as comments only — `record_stage_failure()` logs warning but increments nothing.
FIX: Implement actual counter metrics; wire `record_stage_failure` to increment.

**O-M3.** FILE: backend/app/services/observability_service.py:557-603
ISSUE: Alert engine evaluates rules but has zero delivery — no PagerDuty, Slack, email, SNS.
FIX: Wire `AlertEngine.evaluate()` to `NotificationService.send()` on FIRING transition.

**O-M4.** FILE: backend/app/middleware/tracing_middleware.py:186
ISSUE: TraceStore is module-level singleton — multi-worker: each worker has isolated store.
FIX: Store traces in Redis with TTL for multi-worker.

**O-M5.** FILE: backend/app/ (no slow query logging)
ISSUE: No SQLAlchemy event listener for slow queries — a 30-second query generates no log.
FIX: Add `after_cursor_execute` event listener logging queries > 1000ms with `request_id`.

**O-M6.** FILE: frontend/src/middleware.ts
ISSUE: No request ID generation or trace header propagation.
FIX: Add `X-Request-ID: crypto.randomUUID()` to requests; propagate to API client.

**O-M7.** FILE: frontend/src/ (70+ console.error calls, 40+ files)
ISSUE: Ad-hoc unstructured `console.error` — inconsistent prefixes, no structured metadata.
FIX: Centralize in `frontend/src/lib/logger.ts`.

**O-M8.** FILE: frontend/src/hooks/api/*.ts (17 files)
ISSUE: API hooks don't surface errors consistently — no global onError toast.
FIX: Add global query error handler showing toast via sonner (already installed).

#### LOW

**O-L1.** FILE: backend/app/api/middleware/sli_collector.py
ISSUE: SLI metrics and MetricsMiddleware track overlapping data independently.
FIX: Consolidate into single pipeline.

**O-L2.** FILE: backend/app/core/worker_health.py:102
ISSUE: Worker health result not emitted as metric — can't alert on stuck workers.
FIX: Expose as Prometheus gauge.

**O-L3.** FILE: backend/app/services/kg_tracing_service.py
ISSUE: Duplicate tracing implementation alongside `observability_service.py`.
FIX: Merge into `observability_service`.

**O-L4.** FILE: backend/app/api/middleware/request_logging.py:83-86
ISSUE: 500 errors log only `status_code`, not exception type/message.
FIX: Add `error_type` and `error_message` to extra dict.

**O-L5.** FILE: frontend/src/components/ErrorBoundary.tsx:72-75
ISSUE: `componentDidCatch` logs only in development — no-op in production without `onError` prop.
FIX: Always log in `componentDidCatch`; gate verbose details (not occurrence) on dev mode.

---

### HIPAA/PHI Compliance

#### HIGH

**H-H1.** FILE: backend/app/services/agent_chat_service.py:133
ISSUE: LLM tool inputs (potentially containing clinical queries/patient IDs) logged at INFO level.
DETAIL: `PHIRedactionFilter` only catches SSN/MRN patterns.
FIX: Reduce to DEBUG; apply `sanitize_for_logging()` before logging.

**H-H2.** FILE: backend/app/services/ (30+ files)
ISSUE: Patient IDs logged at INFO level extensively — creates detailed access pattern correlation.
FIX: Reduce `patient_id` logging to DEBUG; use one-way hash or truncated ID at INFO level.

**H-H3.** FILE: backend/app/api/middleware/audit_middleware.py:508-510
ISSUE: Audit logging failure silently swallowed — request proceeds without audit record.
DETAIL: Could mean hours of PHI access go unrecorded.
FIX: Fail request (503) when audit logging fails in production; implement fallback (Redis queue, local file).

**H-H4.** FILE: backend/app/api/middleware/auth_middleware.py:116-135
ISSUE: Auth bypass mode grants full admin — no validator preventing `auth_bypass_dev=True` in production.
FIX: Add config validator raising `ValueError` if `auth_bypass_dev=True` and `environment != "development"`.

**H-H5.** FILE: backend/app/models/document.py:33-37, clinical_fact.py:34-38
ISSUE: `patient_id` stored as plain `String(255)` — DB compromise enables full re-identification.
FIX: Pseudonymized patient identifier with secure lookup table; ensure TLS on DB connection (`sslmode=require`).

**H-H6.** FILE: frontend/src/hooks/auth/authStorage.ts:55
ISSUE: User profile (id, email, name, roles, permissions) stored in localStorage — persists after browser close.
FIX: Use `sessionStorage` or in-memory React state only; re-hydrate from backend on load.

**H-H7.** FILE: frontend/src/app/smart/callback/page.tsx:88-96
ISSUE: SMART tokens + `patient_id` + `encounter_id` stored in sessionStorage — XSS-accessible PHI identifiers.
FIX: Store SMART tokens server-side via API call; clear immediately after consumption.

**H-H8.** FILE: frontend/src/app/notes/page.tsx:216
ISSUE: Full generated clinical notes (PHI) stored in sessionStorage to pass between pages.
FIX: Pass via server-side temporary store with short-lived ID or React context.

**H-H9.** FILE: frontend/src/app/nlp/page.tsx:1753-1754
ISSUE: Patient IDs and clinical entity data logged to browser console in production.
FIX: Remove all `console.log` with patient IDs or clinical data; gate on `NODE_ENV=development`.

**H-H10.** FILE: frontend/src/app/patients/[patientId]/*
ISSUE: Patient IDs in URL paths — exposed in browser history, bookmarks, referrer headers, analytics.
FIX: Ensure only UUIDs (never MRNs) in URL segments; add `Referrer-Policy: no-referrer`.

**H-H11.** FILE: frontend/src/middleware.ts:62-64
ISSUE: `NEXT_PUBLIC_AUTH_BYPASS` in client-side bundle — if set in production, all auth bypassed.
FIX: Remove `NEXT_PUBLIC_` prefix; add production guard that ignores variable.

#### MEDIUM

**H-M1.** FILE: backend/app/core/logging_config.py:31-39
ISSUE: PHI redaction filter covers only SSN/MRN/account — misses 15 other HIPAA identifiers.
FIX: Expand to cover all 18 HIPAA identifiers; consider Microsoft Presidio.

**H-M2.** FILE: backend/app/core/tenant.py:115-121
ISSUE: Access denial response leaks `patient_id` being accessed — enables enumeration attacks.
FIX: Return generic "Access denied" without `patient_id` in response body.

**H-M3.** FILE: backend/app/core/config.py:54
ISSUE: Default DB URL has no TLS config — no production validator requiring `sslmode=require`.
FIX: Add `model_validator` checking `sslmode=require` in production.

**H-M4.** FILE: backend/app/api/documents/ (multiple)
ISSUE: Document API endpoints lack RBAC guards.
FIX: Add `get_current_user` + `PermissionChecker` to all document endpoints.

**H-M5.** FILE: backend/app/services/nlp_entity/nlp_entity_linkers.py:588-704
ISSUE: Clinical text fragments logged at DEBUG level — PHI if DEBUG enabled in non-dev.
FIX: Validate DEBUG logging never enabled in production; apply `sanitize_for_logging()` even to DEBUG.

**H-M6.** FILE: frontend/src/lib/api.ts (fetchWithRetry)
ISSUE: No `Cache-Control: no-store` on PHI-containing API requests — browsers may cache clinical data to disk.
FIX: Add `Cache-Control: no-store, no-cache, must-revalidate` headers to all clinical data requests.

**H-M7.** FILE: frontend/src/hooks/auth/AuthContext.tsx:159-173
ISSUE: `logout()` clears storage but not browser history — back button can redisplay PHI pages after logout.
FIX: `history.replaceState` on logout; `Cache-Control: no-store` on PHI responses.

**H-M8.** FILE: frontend/src/app/patients/[patientId]/summary/page.tsx:245
ISSUE: PHI copied to clipboard with no audit logging.
FIX: Log clipboard copy events to backend audit trail; show warning dialog; clear clipboard after timeout.

**H-M9.** FILE: frontend/src/hooks/auth/authApi.ts:47-48
ISSUE: Hardcoded demo credentials (`admin@example.com` / `Admin123!` with `permissions:["*"]`) in client-side code.
FIX: Gate behind build-time flag (not `NEXT_PUBLIC_`) stripped from production builds.

#### LOW

**H-L1.** FILE: backend/app/core/privacy.py:8-11
ISSUE: Privacy module self-describes as "basic implementation for demonstration."
FIX: Integrate Microsoft Presidio or equivalent for production-grade PHI detection.

**H-L2.** FILE: backend/app/core/security.py:75-82
ISSUE: OpenAPI docs (`/docs`, `/redoc`, `/openapi.json`) publicly accessible in production.
FIX: Set `docs_url=None`, `redoc_url=None` in production.

**H-L3.** FILE: backend/app/models/audit.py:219-229
ISSUE: Tamper-evident hash chain fields are nullable — `record_hash` and `previous_hash` not enforced.
FIX: Enforce hash chain; make `record_hash` NOT NULL.

**H-L4.** FILE: backend/app/models/audit.py:86-246
ISSUE: Audit log immutability trigger mentioned in docstring but not implemented.
FIX: Add migration creating immutability trigger; startup check verifying trigger exists.

**H-L5.** FILE: frontend/src (global)
ISSUE: No print protection — no `@media print` CSS to redact PHI.
FIX: Add `@media print` styles redacting PHI sections or displaying "Contains PHI" watermark.

---

## Cross-Cutting Patterns

### 1. God Files / Components (Architecture + Performance)
The codebase has a systemic pattern of oversized, monolithic files that concentrate too many responsibilities. This appears across both frontend and backend, in both architecture and performance findings:
- `clinical_agent.py` (3,575 LOC) — API + business logic + SQL
- `graph_rag.py` (1,295 LOC) — API + query logic + answer generation
- `api.ts` (4,187 LOC) — types + methods + infra for 15 domains
- `nlp/page.tsx` (3,165 LOC) — 6 API calls + 15 state hooks + rendering
- `calculator_definitions.py` (12,716 LOC) — single file for all calculators
- `useGraphState.ts` (586 LOC) — 30+ state pieces, 60+ return values

**Impact:** Untestable logic, bundle bloat, unnecessary re-renders, and impossible code review.

### 2. Missing Auth / Auth Bypass in Production (HIPAA + Architecture)
Authentication and authorization have multiple independent failure modes:
- `fetchWithRetry` never attaches auth headers (A-C5)
- Auth disabled by default when no API keys configured (H-C2)
- `get_tenant_context()` always returns null tenant (H-C3)
- Export endpoint has zero auth (H-C1)
- Auth bypass dev mode lacks production guard (H-H4)
- `NEXT_PUBLIC_AUTH_BYPASS` in client bundle (H-H11)

**Impact:** A system handling PHI has multiple paths to unauthenticated access.

### 3. No Production Error Visibility (Observability + HIPAA)
Both frontend and backend suppress errors in production:
- No browser error tracking SDK (O-C4)
- ErrorBoundary reports only in development (O-C6)
- `error.tsx` only logs in development (O-H5)
- 73% of backend `logger.error()` calls omit stack traces (O-C2)
- Audit logging failure silently swallowed (H-H3)
- Graph build failure marked COMPLETED (O-H4)

**Impact:** Production incidents go undetected; PHI access events may go unrecorded.

### 4. N+1 Query Patterns (Performance)
Multiple backend services exhibit the same pattern of issuing per-item SELECTs in loops:
- BFS traversal: per-edge SELECT (P-C1)
- Temporal context: per-edge SELECT (P-C2)
- Negated nodes: per-ID SELECT (P-H1)
- Edge deduplication: per-edge SELECT (P-M1)

**Impact:** Single API call can generate thousands of DB queries; pool exhaustion under moderate load.

### 5. Unbounded In-Memory Data Loading (Performance + HIPAA)
Multiple services load entire datasets into Python/JS memory:
- All patient nodes for string matching (P-C3)
- All ClinicalFacts with embeddings for cosine similarity (P-C4)
- All facts without embeddings for backfill (P-H4)
- Array spread on every D3 tick (P-C5)

**Impact:** Memory exhaustion under real patient load; potential information leakage via error messages.

### 6. PHI Leakage Through Logging (HIPAA + Observability)
Patient identifiers and clinical data appear in logs across both tiers:
- Patient IDs logged at INFO in 30+ backend files (H-H2)
- PHI redaction covers only 3 of 18 HIPAA identifiers (H-M1)
- Patient IDs and graph data logged to browser console (H-H9)
- Clinical text at DEBUG level in NLP linkers (H-M5)
- LLM tool inputs at INFO (H-H1)

**Impact:** Log aggregation systems become unauthorized PHI repositories.

### 7. Frontend State Management Gaps (Architecture + Performance)
The frontend lacks a consistent data fetching layer:
- 25 pages bypass React Query hooks (A-H5)
- 40% of API surface has empty hook modules (A-H6)
- Raw `fetch()` calls bypass API client (A-M9)
- Double retry between `fetchWithRetry` and React Query (A-M10)
- Zero `React.memo` across components directory (P-M12)

**Impact:** Inconsistent caching, duplicate requests, unnecessary re-renders.

---

## Prioritized Fix Sequence

### Phase 1: HIPAA Critical — Legal Risk (1-2 weeks)
Regulatory violations that could trigger enforcement action.

1. **Add auth to export endpoint** (H-C1) — single most exploitable PHI exposure
2. **Fix auth defaults** (H-C2) — prevent unauthenticated production deployments
3. **Fix tenant context stub** (H-C3) — enable patient-level access control
4. **Add production guard for auth bypass** (H-H4) — prevent dev mode in production
5. **Remove NEXT_PUBLIC_AUTH_BYPASS** (H-H11) — eliminate client-side auth bypass
6. **Implement session idle timeout** (H-C7) — HIPAA 164.312(a)(2)(iii) requirement
7. **Migrate auth tokens to httpOnly cookies** (H-C5, H-C6) — XSS protection for tokens
8. **Remove hardcoded demo credentials from bundle** (H-M9)
9. **Add Cache-Control: no-store to PHI requests** (H-M6)

### Phase 2: Auth Integration — Systemic Fix (1-2 weeks)
Fix the auth architecture so it actually works end-to-end.

10. **Integrate auth headers into fetchWithRetry** (A-C5) — all 100+ API functions currently unauthenticated
11. **Add RBAC to document endpoints** (H-M4)
12. **Make audit logging failure block requests** (H-H3) — ensure PHI access always logged
13. **Expand PHI redaction filter** (H-M1) — cover all 18 HIPAA identifiers

### Phase 3: Observability Foundation (1-2 weeks)
Cannot fix what you cannot see.

14. **Install Sentry on frontend** (O-C4, O-C5, O-C6) — single change captures all frontend errors
15. **Fix ErrorBoundary to report in production** (O-C6) — remove development guard
16. **Add correlation IDs to background jobs** (O-C1)
17. **Fix logger.error() calls to include stack traces** (O-C2) — 58 call sites
18. **Add OTLP exporter to observability service** (O-C3)
19. **Always trace on 500 errors** (O-H1)

### Phase 4: Performance Critical — Production Stability (2-3 weeks)
These will cause outages under real patient load.

20. **Batch BFS traversal queries** (P-C1, P-C2) — eliminate 5,000 queries per RAG call
21. **Push node matching into SQL** (P-C3) — eliminate unbounded memory load
22. **Use pgvector for semantic search** (P-C4) — eliminate in-memory cosine similarity
23. **Fix D3 tick allocation** (P-C5) — eliminate 78K objects/sec
24. **Split GraphCanvas useEffect** (P-C6) — eliminate simulation rebuilds
25. **Parallelize NLP waterfall** (P-C7) — eliminate 200-800ms per analysis

### Phase 5: Architecture — Maintainability (3-4 weeks)
Reduce complexity to make future fixes sustainable.

26. **Extract business logic from clinical_agent.py** (A-C1) — god file decomposition
27. **Extract service layer for graph_rag.py** (A-C3)
28. **Split api.ts into domain modules** (A-C4) — reduce bundle size
29. **Split nlp/page.tsx** (A-C6) — implement useNLP hook, extract sub-components
30. **Standardize DI pattern** (A-C2, A-M4) — FastAPI Depends() for all services

### Phase 6: Remaining HIGH/MEDIUM — Hardening (ongoing)
Work through remaining findings by severity within each lens.

31. Fix N+1 patterns in graph_builder_db.py (P-H1, P-M1)
32. Add per-route loading.tsx and error.tsx (P-H7, O-H6)
33. Implement lazy loading with next/dynamic (P-H8)
34. Build CanvasRenderer node map (P-H6)
35. Reduce patient_id logging verbosity (H-H2)
36. Add slow query logging (O-M5)
37. Implement Web Vitals instrumentation (O-H8)
38. Column-level encryption for PHI (H-C4) — requires migration planning
39. Complete React Query hook layer (A-H5, A-H6)
40. Fix WebSocket reconnection subscription loss (P-H10)

---

*Report generated 2026-02-17 by 8-specialist agent review. 120 findings across 4 lenses.*
