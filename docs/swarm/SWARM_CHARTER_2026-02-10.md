# Swarm Charter (2026-02-10)

## Mission
Build durable, line-by-line understanding of the codebase and preserve it in-repo so future sessions can resume without chat history.

## Scope
- Backend startup/config/middleware/auth foundations.
- API surface and maturity/auth exposure.
- Service/schema/model patterns across modules.
- Document->fact->graph pipelines and orchestration paths.
- Frontend API/query integration layers.
- Test quality and regression risk concentration.

## Baseline Snapshot
- Captured: 2026-02-10 04:47:29 UTC (2026-02-09 23:47:29 EST)
- Branch: `master`
- HEAD: `84b47d7`
- Remote: `https://github.com/astinard/clinical-ontology-normalizer.git`
- Tracked files: `1772`
- Total tracked LOC: `4,201,735`
- Endpoints inventoried: `3,113`

## Workstreams (Subagent-style)
- W1 Platform: app init, settings, infra dependencies, auth primitives.
- W2 API Surface: endpoint catalog, maturity tiers, auth flags, route wiring.
- W3 Service Taxonomy: in-memory vs DB-backed vs external connector service classes.
- W4 Pipeline Trace: ingestion/extraction/mapping/fact-builder/graph-builder execution flow.
- W5 Frontend Integration: API client boundaries, query caching, domain route coupling.
- W6 Test Signal: test breadth/depth by domain and high-risk untested seams.
- W7 Rewrite Strategy: targeted refactor map vs rewrite criteria by subsystem.

## Deliverables
- `SWARM_LOC_BASELINE_2026-02-10.md`
- `SWARM_AUTH_SEMANTICS_2026-02-10.md`
- `SWARM_SERVICE_TAXONOMY_2026-02-10.md`
- `SWARM_PIPELINE_TRACE_2026-02-10.md`
- `SWARM_PHARMA_MODULE_QUALITY_MATRIX_2026-02-10.md`
- `SWARM_UNAUTH_MODULES_DEEPDIVE_2026-02-10.md`
- `SWARM_PIPELINE_IDEMPOTENCY_ANALYSIS_2026-02-10.md`
- `SWARM_BILLION_DOLLAR_ORG_REVIEW_2026-02-10.md`
- `SWARM_FINDINGS.md`
- `SWARM_MEMORY.md`
- `SWARM_PROGRESS_LOG.md`
- `SWARM_STATE_2026-02-10.json`

## Success Criteria
- Every major code slice has file-level ownership and behavior notes.
- Top risk paths are identified with concrete file references.
- Rewrite-vs-refactor decisions are supported by measured hotspots.
- Resume protocol is explicit and deterministic.
