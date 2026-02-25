# Clinical Ontology Normalizer

A system to ingest clinical data, extract mentions, map to OMOP concepts, build a patient knowledge graph, and expose via web UI.

## Quick Orientation

- **Backend**: `backend/` - FastAPI (Python), ~345K LOC, 187 service files, 726 endpoints
- **Frontend**: `frontend/` - Next.js App Router (TypeScript), ~123K LOC
- **Database**: PostgreSQL (primary), Redis (job queue), Neo4j (optional graph persistence)
- **Infra**: `docker-compose*.yml`, `k8s/`, `nginx/`

## Architecture (60 seconds)

Frontend (Next.js) -> Backend (FastAPI) -> PostgreSQL + Redis + Neo4j (optional)

Core data flow:
1. Ingest document via `backend/app/api/documents/`
2. NLP extraction (rule-based + ML ensemble) in `backend/app/services/`
3. Map to OMOP via `backend/app/services/mapping*.py`
4. Build ClinicalFacts via `backend/app/services/fact_builder*.py`
5. Construct knowledge graph via `backend/app/services/graph_builder*.py`
6. Export to OMOP/FHIR or query via API

## Key Entry Points

Backend:
- `backend/app/main.py` - FastAPI app, router registration, startup
- `backend/app/api/__init__.py` - all API routers
- `backend/app/core/config.py` - env/config
- `backend/app/core/database.py` - DB init/teardown
- `backend/app/core/queue.py` - job queue setup

Frontend:
- `frontend/src/app/layout.tsx` - root layout
- `frontend/src/app/page.tsx` - landing page
- `frontend/src/hooks/api/` - API hooks
- `frontend/src/components/` - shared UI + KG components

## Core Data Model

- Document -> raw clinical note
- Mention -> extracted span w/ offsets + assertion/temporality/experiencer
- MentionConceptCandidate -> candidate OMOP mappings
- ClinicalFact -> normalized fact with provenance
- KGNode/KGEdge -> knowledge graph projection

Models: `backend/app/models/` | Schemas: `backend/app/schemas/`

## Where to Find Things

| What | Where |
|---|---|
| Route handler | `backend/app/api/<domain>.py` |
| Business logic | `backend/app/services/<domain>.py` |
| ORM model | `backend/app/models/` |
| Pydantic schema | `backend/app/schemas/` |
| Tests | `backend/tests/test_<domain>.py` |
| Frontend pages | `frontend/src/app/` |
| Frontend tests | `frontend/__tests__/` |
| Design specs | `specs/` |
| Planning docs | `docs/` |

## Maturity Tiers

- **Production**: Document ingestion, rule-based NLP, OMOP mapping, fact builder, drug safety, billing/coding stack, clinical calculators
- **Pilot**: ML NLP (transformer/ensemble), KG build, graph query, GraphRAG, clinical agent, guideline RAG, FHIR import/export, SMART on FHIR, CDS Hooks
- **Scaffold**: TEFCA, federated learning, bulk export, model registry, LLM fine-tuning, voice transcription

## Current Focus

Architecture rationalization (non-destructive):
- Phase 1: Safety envelope - eliminate silent failures on critical paths
- Phase 2: Canonicalize NLP/calculator/graph service variants
- Phase 3: API maturity labeling and lifecycle controls
- Phase 4: Type hardening for key contracts

See `docs/ARCHITECTURE_RATIONALIZATION_PLAN.md` for full plan.

## Dev Commands

```bash
make test          # run backend tests
make lint          # ruff check
make typecheck     # mypy
npm run build      # frontend build (from frontend/)
npm run lint       # frontend lint (from frontend/)
docker compose up  # full local stack
```

## Code Conventions

- Backend: Python 3.13, FastAPI, SQLAlchemy async, Pydantic v2, ruff for linting
- Frontend: TypeScript, Next.js App Router, Tailwind CSS, shadcn/ui
- Tests: pytest (backend), Jest + Playwright (frontend)
- All phases completed through Phase 12 (see `docs/IMPLEMENTATION_PLAN.md`)

## Context Loading Guide

Auto-generated indexes live in `memory/`. Regenerate with: `python3 backend/scripts/generate_context_index.py`

**Tier 1 — Codebase map** (load `service_registry.md` first, drill into others as needed):
- `memory/service_registry.md` (~350 lines) — top 20 hottest files + route index (5K+ endpoints grouped by file)
- `memory/service_index.md` (~460 lines) — one line per service file with docstring, key functions, deps
- `memory/model_index.md` (~150 lines) — ORM models with table names and columns

**Tier 2 — Domain deep-dives** (load when working in that area):
- `memory/domain_rag.md` — RAG pipeline, benchmark conditions C1-C5, QA experiments
- `memory/domain_calculators.md` — calculator definitions, execution, reasoning, KG integration
- `memory/domain_kg.md` — knowledge graph construction, caching, traversal

## Important Notes

- Do NOT read `codebase_kg.json` (730KB) or `docs/agent_context_health_graph.md` (120KB) into context - they will fill the entire context window
- Prefer targeted file reads over broad exploration
- The `docs/` folder contains planning/architecture documents - only read what's needed for the current task
