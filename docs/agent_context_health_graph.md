# Agent Context Bundle
Generated: 2026-02-01

## Task

<fill in>

## Constraints

<fill in>

## AGENTS.md
```markdown
# Agents Documentation

## Project: Clinical Ontology Normalizer

### Workflow

This project uses the Ralph Loop iterative development methodology:

1. Each iteration picks ONE unchecked task from IMPLEMENTATION_PLAN.md
2. Implement the task fully with tests
3. Run quality gates: `make test`, `make lint`, `make typecheck`
4. Update IMPLEMENTATION_PLAN.md to check off completed task
5. Commit with message: "task: <short name>"
6. Exit (loop continues until all tasks complete)

### Allowed Commands

```bash
# Development
make dev          # Start development servers
make test         # Run all tests
make lint         # Run linters
make typecheck    # Run type checkers

# Backend
cd backend && pytest                    # Run Python tests
cd backend && ruff check .              # Lint Python
cd backend && mypy .                    # Type check Python

# Frontend (when exists)
cd frontend && npm test                 # Run JS tests
cd frontend && npm run lint             # Lint TypeScript
cd frontend && npm run typecheck        # Type check

# Database
cd backend && alembic upgrade head      # Run migrations
cd backend && python -m app.seed        # Seed data
```

### Directory Structure

```
/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── api/            # FastAPI routes
│   │   └── workers/        # RQ job workers
│   ├── tests/              # pytest tests
│   ├── alembic/            # Database migrations
│   └── pyproject.toml
├── frontend/               # Next.js TypeScript frontend
├── infra/                  # Docker, deployment configs
├── specs/                  # Technical specifications
├── fixtures/               # Synthetic test data
├── IMPLEMENTATION_PLAN.md  # Task checklist
└── Makefile               # Build commands
```

### Data Model Overview

- **Document**: Raw clinical note text with metadata
- **StructuredResource**: FHIR bundle or CSV payload
- **Mention**: Extracted text span with offsets, assertion, temporality, experiencer
- **MentionConceptCandidate**: Candidate OMOP mappings with confidence scores
- **ClinicalFact**: Canonical normalized fact with full metadata
- **FactEvidence**: Links facts to source evidence
- **KGNode/KGEdge**: Knowledge graph projection

### Quality Gates

Before every commit:
1. All tests pass: `make test`
2. Linting passes: `make lint`
3. Type checking passes: `make typecheck`

### Important Rules

- NO real PHI - only synthetic data in fixtures
- Negated findings MUST be preserved (assertion=absent)
- One task per iteration
- Tests must pass before marking task complete

### Agent Context (Read First)

Core flow:
- Document ingestion -> Mentions -> Mapping -> ClinicalFact -> Knowledge Graph

Primary entry points:
- `backend/app/main.py`: FastAPI app + router registration
- `backend/app/api/__init__.py`: router index
- `backend/app/services/`: business logic
- `backend/app/models/` + `backend/app/schemas/`: data contracts

Repo maps:
- `CODEBASE_MAP.md`: human-readable map
- `codebase_kg.json`: machine-readable KG
- `scripts/generate_codebase_kg.py`: regenerate KG
 - `AGENT_PROMPT_TEMPLATE.md`: scoped task template
```

## CODEBASE_MAP.md
```markdown
# Codebase Map - Clinical Ontology Normalizer

Last updated: 2026-01-29

This document is a high-signal map of the repo for humans and agents. It focuses on entry points, data flow, and where responsibilities live.

## 0) Quick Orientation

Top-level anchors:

- `README.md`: high-level overview and setup.
- `DEVELOPMENT.md`: local dev workflow and common tasks.
- `backend/`: FastAPI backend (core logic).
- `frontend/`: Next.js frontend (App Router).
- `specs/`: design docs for NLP, KG, mapping, ingestion, etc.
- `fixtures/` + `backend/fixtures/`: synthetic vocab and test data.
- `k8s/`, `infra/`, `docker-compose*.yml`: deployment and infra.

## 1) Architecture in 60 Seconds

- Frontend (Next.js) talks to Backend (FastAPI) over REST.
- Backend runs NLP extraction, terminology mapping, fact building, and knowledge graph construction.
- Primary data store is PostgreSQL; Redis is used for queues; Neo4j is optional for graph persistence/analysis.
- Optional FHIR stack: `fhir-mcp/` + docker-compose.fhir.yml.

## 2) Key Entrypoints (Start Here)

Backend:

- `backend/app/main.py`: FastAPI app, router registration, middleware, startup lifecycle.
- `backend/app/api/__init__.py`: all API routers exported here.
- `backend/app/core/config.py`: env/config (auth, db, redis, neo4j, llm).
- `backend/app/core/database.py`: DB initialization/teardown.
- `backend/app/core/queue.py`: job queue setup.

Frontend:

- `frontend/src/app/layout.tsx`: App Router root layout.
- `frontend/src/app/page.tsx`: landing page.
- `frontend/src/hooks/api/`: client-side API hooks.
- `frontend/src/components/`: shared UI + KG components.

## 3) Core Data Model (Conceptual)

Canonical entities used across services (see `backend/app/models/` and `backend/app/schemas/`):

- Document -> raw clinical note
- Mention -> extracted span w/ offsets + assertion/temporality/experiencer
- MentionConceptCandidate -> candidate OMOP mappings
- ClinicalFact -> normalized fact
- FactEvidence -> links facts to source
- KGNode/KGEdge -> knowledge graph projection

## 4) Primary Data Flow

1. Ingest document via `backend/app/api/documents/*`.
2. NLP extraction (rule-based + advanced + ensemble) in `backend/app/services/`.
3. Mapping to OMOP via `backend/app/services/mapping*.py`.
4. ClinicalFact creation via `backend/app/services/fact_builder*.py`.
5. Graph construction via `backend/app/services/graph_builder*.py`.
6. Export to OMOP/FHIR or analytics endpoints.

## 5) Backend Structure (What Lives Where)

API routers:

- `backend/app/api/`: each file maps to a route group.
- `backend/app/api/documents/`: documents endpoints split into submodules.
- `backend/app/api/etl/`: ETL endpoints.
- `backend/app/api/graphql/`: KG GraphQL.
- `backend/app/api/middleware/`: request ID, audit, error handling, rate limits.

Services (business logic):

- `backend/app/services/`:
  - NLP: `nlp_rule_based.py`, `nlp_advanced.py`, `nlp_entity_service.py`, `relation_extraction.py`, `value_extraction.py`
  - Mapping: `mapping.py`, `mapping_sql.py`, `vocabulary*.py`
  - Facts/Graph: `fact_builder*.py`, `graph_builder*.py`, `graph_database_service.py`
  - FHIR/OMOP: `fhir_import.py`, `fhir_exporter.py`, `export/omop_exporter*.py`
  - Billing/Coding: `icd10_suggester.py`, `cpt_suggester.py`, `hcc_analyzer.py`, `billing_optimizer.py`
  - Quality/Analytics: `quality_measures.py`, `semantic_search.py`, `graph_analytics_service.py`

Models/Schemas:

- `backend/app/models/`: SQLAlchemy ORM models.
- `backend/app/schemas/`: Pydantic request/response models.

Jobs/ETL:

- `backend/app/jobs/`: background workers.
- `backend/app/etl/`: ETL pipelines for OMOP domains.
- `backend/app/connectors/`: FHIR, CSV, HL7v2, database, CCDA connectors.

## 6) Frontend Structure (What Lives Where)

- `frontend/src/app/`: App Router pages; routes mirror backend domains.
- `frontend/src/components/KnowledgeGraph/`: KG canvas + graph UI.
- `frontend/src/components/provenance/`: evidence display.
- `frontend/src/hooks/api/`: API query hooks.
- `frontend/__tests__/` and `frontend/playwright/`: unit + e2e tests.

## 7) Infra & Ops

- `docker-compose*.yml`: local stacks, optional FHIR stack.
- `k8s/`: deployments, services, monitoring, overlays.
- `infra/`: deployment configs.
- `nginx/`: reverse proxy config.

## 8) Tests & Fixtures

- `backend/tests/`: extensive service + API tests.
- `backend/tests/sample_notes/`: synthetic note fixtures.
- `fixtures/` + `backend/fixtures/`: vocabulary + synthetic datasets.

## 9) Navigation Tips for Agents

Common lookups:

- Find route handler: `backend/app/api/<domain>.py` (registered in `backend/app/main.py`).
- Find business logic: `backend/app/services/<domain>_service.py` or `<domain>.py`.
- Find model/schema: `backend/app/models/` and `backend/app/schemas/`.
- Find tests: `backend/tests/test_<domain>.py` or `frontend/__tests__/`.

Useful ripgrep patterns:

- `rg "router =" backend/app/api`
- `rg "get_.*_service" backend/app/services`
- `rg "class .*\(Base" backend/app/models`
- `rg "@router" backend/app/api`

## 10) Related Reference Docs

- `backend/SYSTEM_INVENTORY.md`: detailed services inventory and gaps.
- `specs/knowledge_graph.md`: KG design.
- `specs/nlp.md`: NLP pipeline.
- `specs/mapping.md`: mapping strategy.
- `specs/ingestion.md`: data ingestion.

## 11) Keeping the KG Up to Date

- Generator script: `scripts/generate_codebase_kg.py`
- Output: `codebase_kg.json`

Suggested usage:

```bash
python3 scripts/generate_codebase_kg.py
```

## 12) Indexing Hygiene

- `/.cursorindexingignore`: excludes large fixtures and generated artifacts from indexing.

## 13) Agent Skills (Repo-Local)

- `skills/new-endpoint/SKILL.md`: add a FastAPI endpoint
- `skills/new-service-tests/SKILL.md`: add a service + tests
- `skills/docs-update/SKILL.md`: update docs after changes

## 14) KG Export & Skills Install

- `scripts/export_codebase_kg_neo4j.py`: export KG to Neo4j CSV (`kg_export/nodes.csv`, `kg_export/edges.csv`)
- `scripts/install_repo_skills.py`: install repo skills into `$CODEX_HOME/skills`
- `scripts/prepare_agent_context.py`: generate an agent context bundle (map + KG slice)
- `AGENT_PROMPT_TEMPLATE.md`: prompt template for scoped tasks

Make targets:
- `make kg`: regenerate `codebase_kg.json`
- `make kg-export`: export KG to `kg_export/`
- `make kg-check`: verify KG is up to date (useful in CI)
- `make agent-bundle`: generate `agent_context_bundle.md`
- `make agent-bundle-filtered`: generate `agent_context_health_graph.md`
- `make agent-bundles`: generate common domain bundles in `agent_bundles/`

---

If you want a deeper, machine-friendly graph, see `codebase_kg.json`.
```

## KG Slice (JSON)
```json
{
  "nodes": [
    {
      "id": "frontend",
      "type": "dir",
      "label": "frontend",
      "path": "frontend"
    },
    {
      "id": "backend/app/api",
      "type": "dir",
      "label": "backend/app/api",
      "path": "backend/app/api"
    },
    {
      "id": "backend/app/services",
      "type": "dir",
      "label": "backend/app/services",
      "path": "backend/app/services"
    },
    {
      "id": "backend/app/models",
      "type": "dir",
      "label": "backend/app/models",
      "path": "backend/app/models"
    },
    {
      "id": "backend/app/api/cohorts.py",
      "type": "file",
      "label": "cohorts.py",
      "path": "backend/app/api/cohorts.py"
    },
    {
      "id": "backend/app/services/cohort_service.py",
      "type": "service",
      "label": "cohort_service.py",
      "path": "backend/app/services/cohort_service.py"
    },
    {
      "id": "endpoint:GET /{cohort_id}/demographics (backend/app/api/cohorts.py)",
      "type": "endpoint",
      "label": "GET /{cohort_id}/demographics",
      "path": "backend/app/api/cohorts.py",
      "meta": {
        "method": "GET",
        "path": "/{cohort_id}/demographics",
        "function": "get_cohort_demographics",
        "response_model": "DemographicBreakdown",
        "summary": "Get demographics breakdown",
        "description": "Get demographic statistics for patients in the cohort."
      }
    },
    {
      "id": "backend/app/api/kg_orchestration.py",
      "type": "file",
      "label": "kg_orchestration.py",
      "path": "backend/app/api/kg_orchestration.py"
    },
    {
      "id": "backend/app/services/causal_reasoning_service.py",
      "type": "service",
      "label": "causal_reasoning_service.py",
      "path": "backend/app/services/causal_reasoning_service.py"
    },
    {
      "id": "backend/app/services/drknows_benchmark_service.py",
      "type": "service",
      "label": "drknows_benchmark_service.py",
      "path": "backend/app/services/drknows_benchmark_service.py"
    },
    {
      "id": "backend/app/services/graph_analytics_service.py",
      "type": "service",
      "label": "graph_analytics_service.py",
      "path": "backend/app/services/graph_analytics_service.py"
    },
    {
      "id": "backend/app/services/graph_database_service.py",
      "type": "service",
      "label": "graph_database_service.py",
      "path": "backend/app/services/graph_database_service.py"
    },
    {
      "id": "backend/app/services/graph_embedding_service.py",
      "type": "service",
      "label": "graph_embedding_service.py",
      "path": "backend/app/services/graph_embedding_service.py"
    },
    {
      "id": "backend/app/services/kg_partitioning_service.py",
      "type": "service",
      "label": "kg_partitioning_service.py",
      "path": "backend/app/services/kg_partitioning_service.py"
    },
    {
      "id": "backend/app/services/kg_visualization_service.py",
      "type": "service",
      "label": "kg_visualization_service.py",
      "path": "backend/app/services/kg_visualization_service.py"
    },
    {
      "id": "backend/app/services/medagentbench_service.py",
      "type": "service",
      "label": "medagentbench_service.py",
      "path": "backend/app/services/medagentbench_service.py"
    },
    {
      "id": "backend/app/services/multi_agent_orchestrator.py",
      "type": "service",
      "label": "multi_agent_orchestrator.py",
      "path": "backend/app/services/multi_agent_orchestrator.py"
    },
    {
      "id": "backend/app/services/provenance_service.py",
      "type": "service",
      "label": "provenance_service.py",
      "path": "backend/app/services/provenance_service.py"
    },
    {
      "id": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "GET /status",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "GET",
        "path": "/status",
        "function": "get_orchestration_status",
        "response_model": "OrchestrationStatusResponse"
      }
    },
    {
      "id": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "POST /query",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "POST",
        "path": "/query",
        "function": "execute_unified_query"
      }
    },
    {
      "id": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "POST /clinical-question",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "POST",
        "path": "/clinical-question",
        "function": "answer_clinical_question"
      }
    },
    {
      "id": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "POST /reasoning-path",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "POST",
        "path": "/reasoning-path",
        "function": "find_reasoning_paths"
      }
    },
    {
      "id": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "GET /patient/{patient_id}/graph",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "GET",
        "path": "/patient/{patient_id}/graph",
        "function": "get_patient_knowledge_graph"
      }
    },
    {
      "id": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "GET /patient/{patient_id}/timeline",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "GET",
        "path": "/patient/{patient_id}/timeline",
        "function": "get_patient_timeline"
      }
    },
    {
      "id": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "POST /export",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "POST",
        "path": "/export",
        "function": "export_knowledge_graph"
      }
    },
    {
      "id": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "POST /mdt-session",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "POST",
        "path": "/mdt-session",
        "function": "start_mdt_session"
      }
    },
    {
      "id": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "GET /semantic-groups",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "GET",
        "path": "/semantic-groups",
        "function": "list_semantic_groups"
      }
    },
    {
      "id": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "type": "endpoint",
      "label": "GET /relationship-types",
      "path": "backend/app/api/kg_orchestration.py",
      "meta": {
        "method": "GET",
        "path": "/relationship-types",
        "function": "list_relationship_types"
      }
    },
    {
      "id": "backend/app/services/terminology_cache.py",
      "type": "service",
      "label": "terminology_cache.py",
      "path": "backend/app/services/terminology_cache.py"
    },
    {
      "id": "backend/app/api/health.py",
      "type": "file",
      "label": "health.py",
      "path": "backend/app/api/health.py"
    },
    {
      "id": "backend/app/services/kafka_service.py",
      "type": "service",
      "label": "kafka_service.py",
      "path": "backend/app/services/kafka_service.py"
    },
    {
      "id": "endpoint:GET  (backend/app/api/health.py)",
      "type": "endpoint",
      "label": "GET ",
      "path": "backend/app/api/health.py",
      "meta": {
        "method": "GET",
        "path": "",
        "function": "health_check",
        "response_model": "HealthResponse",
        "summary": "Comprehensive health check",
        "description": "Performs health checks on all system dependencies and returns overall status."
      }
    },
    {
      "id": "endpoint:GET /live (backend/app/api/health.py)",
      "type": "endpoint",
      "label": "GET /live",
      "path": "backend/app/api/health.py",
      "meta": {
        "method": "GET",
        "path": "/live",
        "function": "liveness_probe",
        "response_model": "LivenessResponse",
        "summary": "Liveness probe",
        "description": "Simple liveness check for container orchestration. Always returns 200 if the process is running."
      }
    },
    {
      "id": "endpoint:GET /ready (backend/app/api/health.py)",
      "type": "endpoint",
      "label": "GET /ready",
      "path": "backend/app/api/health.py",
      "meta": {
        "method": "GET",
        "path": "/ready",
        "function": "readiness_probe",
        "response_model": "ReadinessResponse",
        "summary": "Readiness probe",
        "description": "Checks if the system is ready to handle requests. Returns 200 if ready, 503 if not."
      }
    },
    {
      "id": "endpoint:GET /deep (backend/app/api/health.py)",
      "type": "endpoint",
      "label": "GET /deep",
      "path": "backend/app/api/health.py",
      "meta": {
        "method": "GET",
        "path": "/deep",
        "function": "deep_health_check",
        "response_model": "DeepHealthResponse",
        "summary": "Deep health check with system metrics",
        "description": "Comprehensive health check including system resource metrics. Use for debugging and monitoring."
      }
    },
    {
      "id": "endpoint:GET /cache (backend/app/api/health.py)",
      "type": "endpoint",
      "label": "GET /cache",
      "path": "backend/app/api/health.py",
      "meta": {
        "method": "GET",
        "path": "/cache",
        "function": "get_cache_stats",
        "summary": "Get terminology cache statistics",
        "description": "Returns hit/miss rates and sizes for all terminology caches."
      }
    },
    {
      "id": "endpoint:POST /cache/clear (backend/app/api/health.py)",
      "type": "endpoint",
      "label": "POST /cache/clear",
      "path": "backend/app/api/health.py",
      "meta": {
        "method": "POST",
        "path": "/cache/clear",
        "function": "clear_caches",
        "summary": "Clear all terminology caches",
        "description": "Invalidates all cached terminology results."
      }
    },
    {
      "id": "backend/app/api/phenotypes.py",
      "type": "file",
      "label": "phenotypes.py",
      "path": "backend/app/api/phenotypes.py"
    },
    {
      "id": "endpoint:POST /{patient_id}/evaluate/{phenotype_id} (backend/app/api/phenotypes.py)",
      "type": "endpoint",
      "label": "POST /{patient_id}/evaluate/{phenotype_id}",
      "path": "backend/app/api/phenotypes.py",
      "meta": {
        "method": "POST",
        "path": "/{patient_id}/evaluate/{phenotype_id}",
        "function": "evaluate_phenotype",
        "response_model": "PhenotypeEvaluationResponse",
        "summary": "Evaluate phenotype for patient",
        "description": "Evaluate a specific phenotype for a patient using their knowledge graph."
      }
    },
    {
      "id": "backend/app/api/graph.py",
      "type": "file",
      "label": "graph.py",
      "path": "backend/app/api/graph.py"
    },
    {
      "id": "backend/app/services/graph_etl_service.py",
      "type": "service",
      "label": "graph_etl_service.py",
      "path": "backend/app/services/graph_etl_service.py"
    },
    {
      "id": "backend/app/services/kg_cache_service.py",
      "type": "service",
      "label": "kg_cache_service.py",
      "path": "backend/app/services/kg_cache_service.py"
    },
    {
      "id": "endpoint:GET /health (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /health",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/health",
        "function": "health_check",
        "response_model": "HealthResponse",
        "summary": "Check Neo4j connection health",
        "description": "Returns the status of the Neo4j database connection."
      }
    },
    {
      "id": "endpoint:GET /cache/stats (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /cache/stats",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/cache/stats",
        "function": "get_cache_stats",
        "summary": "Get cache statistics",
        "description": "Returns statistics about the query cache including hit rate and memory usage."
      }
    },
    {
      "id": "endpoint:DELETE /cache/clear (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "DELETE /cache/clear",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "DELETE",
        "path": "/cache/clear",
        "function": "clear_cache",
        "summary": "Clear the query cache",
        "description": "Clears all cached query results. Use sparingly."
      }
    },
    {
      "id": "endpoint:GET /concepts/{concept_id}/neighbors (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /concepts/{concept_id}/neighbors",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/concepts/{concept_id}/neighbors",
        "function": "get_concept_neighbors",
        "response_model": "NeighborsListResponse",
        "summary": "Get related concepts",
        "description": "Returns concepts related to the specified concept."
      }
    },
    {
      "id": "endpoint:GET /concepts/{concept_id}/ancestors (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /concepts/{concept_id}/ancestors",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/concepts/{concept_id}/ancestors",
        "function": "get_concept_ancestors",
        "response_model": "AncestorsListResponse",
        "summary": "Get concept hierarchy",
        "description": "Returns ancestors of a concept in the ontology hierarchy."
      }
    },
    {
      "id": "endpoint:POST /concepts/path (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "POST /concepts/path",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "POST",
        "path": "/concepts/path",
        "function": "find_concept_path",
        "response_model": "PathResponse",
        "summary": "Find path between concepts",
        "description": "Finds the shortest path between two concepts in the knowledge graph."
      }
    },
    {
      "id": "endpoint:GET /patients/{patient_id}/similar (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /patients/{patient_id}/similar",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/patients/{patient_id}/similar",
        "function": "find_similar_patients",
        "response_model": "SimilarPatientsResponse",
        "summary": "Find similar patients",
        "description": "Finds patients similar to the specified patient based on clinical features."
      }
    },
    {
      "id": "endpoint:GET /patients/{patient_id}/subgraph (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /patients/{patient_id}/subgraph",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/patients/{patient_id}/subgraph",
        "function": "get_patient_subgraph",
        "response_model": "PatientSubgraphResponse",
        "summary": "Get patient knowledge graph",
        "description": "Extracts the knowledge subgraph for a patient including conditions, drugs, and procedures."
      }
    },
    {
      "id": "endpoint:POST /query (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "POST /query",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "POST",
        "path": "/query",
        "function": "execute_cypher_query",
        "response_model": "CypherQueryResponse",
        "summary": "Execute Cypher query (admin only)",
        "description": "Executes a raw Cypher query. Restricted to admin users."
      }
    },
    {
      "id": "endpoint:GET /stats (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /stats",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/stats",
        "function": "get_graph_stats",
        "response_model": "GraphStatsResponse",
        "summary": "Get graph statistics",
        "description": "Returns statistics about the knowledge graph."
      }
    },
    {
      "id": "endpoint:POST /etl/load-sample (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "POST /etl/load-sample",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "POST",
        "path": "/etl/load-sample",
        "function": "load_sample_data",
        "summary": "Load sample graph data",
        "description": "Loads sample OMOP concepts into the graph for demonstration."
      }
    },
    {
      "id": "endpoint:GET /concepts/search (backend/app/api/graph.py)",
      "type": "endpoint",
      "label": "GET /concepts/search",
      "path": "backend/app/api/graph.py",
      "meta": {
        "method": "GET",
        "path": "/concepts/search",
        "function": "search_concepts",
        "summary": "Search concepts",
        "description": "Search for concepts by name in the knowledge graph."
      }
    },
    {
      "id": "backend/app/services/policy_service.py",
      "type": "service",
      "label": "policy_service.py",
      "path": "backend/app/services/policy_service.py"
    },
    {
      "id": "backend/app/services/llm_service.py",
      "type": "service",
      "label": "llm_service.py",
      "path": "backend/app/services/llm_service.py"
    },
    {
      "id": "backend/app/api/kg_health.py",
      "type": "file",
      "label": "kg_health.py",
      "path": "backend/app/api/kg_health.py"
    },
    {
      "id": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "service",
      "label": "kg_kafka_streaming_service.py",
      "path": "backend/app/services/kg_kafka_streaming_service.py"
    },
    {
      "id": "endpoint:GET / (backend/app/api/kg_health.py)",
      "type": "endpoint",
      "label": "GET /",
      "path": "backend/app/api/kg_health.py",
      "meta": {
        "method": "GET",
        "path": "/",
        "function": "get_overall_health"
      }
    },
    {
      "id": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "type": "endpoint",
      "label": "GET /component/{component_name}",
      "path": "backend/app/api/kg_health.py",
      "meta": {
        "method": "GET",
        "path": "/component/{component_name}",
        "function": "get_component_health"
      }
    },
    {
      "id": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "type": "endpoint",
      "label": "GET /dependencies",
      "path": "backend/app/api/kg_health.py",
      "meta": {
        "method": "GET",
        "path": "/dependencies",
        "function": "get_dependencies_health"
      }
    },
    {
      "id": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "type": "endpoint",
      "label": "GET /liveness",
      "path": "backend/app/api/kg_health.py",
      "meta": {
        "method": "GET",
        "path": "/liveness",
        "function": "liveness_probe"
      }
    },
    {
      "id": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "type": "endpoint",
      "label": "GET /readiness",
      "path": "backend/app/api/kg_health.py",
      "meta": {
        "method": "GET",
        "path": "/readiness",
        "function": "readiness_probe"
      }
    },
    {
      "id": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "type": "endpoint",
      "label": "GET /metrics",
      "path": "backend/app/api/kg_health.py",
      "meta": {
        "method": "GET",
        "path": "/metrics",
        "function": "get_health_metrics"
      }
    },
    {
      "id": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "type": "endpoint",
      "label": "GET /alerts",
      "path": "backend/app/api/kg_health.py",
      "meta": {
        "method": "GET",
        "path": "/alerts",
        "function": "get_health_alerts"
      }
    },
    {
      "id": "backend/app/api/clinical_agent.py",
      "type": "file",
      "label": "clinical_agent.py",
      "path": "backend/app/api/clinical_agent.py"
    },
    {
      "id": "backend/app/services/guideline_rag_service.py",
      "type": "service",
      "label": "guideline_rag_service.py",
      "path": "backend/app/services/guideline_rag_service.py"
    },
    {
      "id": "backend/app/services/nlp_rule_based.py",
      "type": "service",
      "label": "nlp_rule_based.py",
      "path": "backend/app/services/nlp_rule_based.py"
    },
    {
      "id": "backend/app/services/provenance_db_service.py",
      "type": "service",
      "label": "provenance_db_service.py",
      "path": "backend/app/services/provenance_db_service.py"
    },
    {
      "id": "endpoint:POST /import (backend/app/api/clinical_agent.py)",
      "type": "endpoint",
      "label": "POST /import",
      "path": "backend/app/api/clinical_agent.py",
      "meta": {
        "method": "POST",
        "path": "/import",
        "function": "bulk_import_documents",
        "response_model": "BulkImportResponse",
        "summary": "Bulk import clinical documents",
        "description": "Import multiple clinical notes, extract entities via NLP, and optionally build knowledge graph."
      }
    },
    {
      "id": "endpoint:POST /build-graph (backend/app/api/clinical_agent.py)",
      "type": "endpoint",
      "label": "POST /build-graph",
      "path": "backend/app/api/clinical_agent.py",
      "meta": {
        "method": "POST",
        "path": "/build-graph",
        "function": "build_graph_from_entities",
        "response_model": "BuildGraphResponse",
        "summary": "Build knowledge graph from pre-extracted entities",
        "description": "Build a patient knowledge graph using entities already extracted by the frontend NLP."
      }
    },
    {
      "id": "endpoint:GET /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "type": "endpoint",
      "label": "GET /graph/{patient_id}",
      "path": "backend/app/api/clinical_agent.py",
      "meta": {
        "method": "GET",
        "path": "/graph/{patient_id}",
        "function": "get_patient_graph",
        "response_model": "PatientGraphResponse",
        "summary": "Get patient knowledge graph",
        "description": "Retrieve the complete knowledge graph for a patient."
      }
    },
    {
      "id": "endpoint:POST /query/{patient_id} (backend/app/api/clinical_agent.py)",
      "type": "endpoint",
      "label": "POST /query/{patient_id}",
      "path": "backend/app/api/clinical_agent.py",
      "meta": {
        "method": "POST",
        "path": "/query/{patient_id}",
        "function": "hybrid_query",
        "response_model": "HybridQueryResponse",
        "summary": "Query patient data with hybrid reasoning",
        "description": "Ask natural language questions combining EHR data and knowledge graph."
      }
    },
    {
      "id": "endpoint:DELETE /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "type": "endpoint",
      "label": "DELETE /graph/{patient_id}",
      "path": "backend/app/api/clinical_agent.py",
      "meta": {
        "method": "DELETE",
        "path": "/graph/{patient_id}",
        "function": "delete_patient_graph",
        "summary": "Delete patient knowledge graph",
        "description": "Remove all knowledge graph data for a patient."
      }
    },
    {
      "id": "endpoint:GET /patients (backend/app/api/clinical_agent.py)",
      "type": "endpoint",
      "label": "GET /patients",
      "path": "backend/app/api/clinical_agent.py",
      "meta": {
        "method": "GET",
        "path": "/patients",
        "function": "list_patients_with_graphs",
        "summary": "List patients with knowledge graphs",
        "description": "Get list of patients that have knowledge graphs."
      }
    },
    {
      "id": "backend/app/api/visualizations.py",
      "type": "file",
      "label": "visualizations.py",
      "path": "backend/app/api/visualizations.py"
    },
    {
      "id": "endpoint:GET /geospatial (backend/app/api/visualizations.py)",
      "type": "endpoint",
      "label": "GET /geospatial",
      "path": "backend/app/api/visualizations.py",
      "meta": {
        "method": "GET",
        "path": "/geospatial",
        "function": "get_geospatial_data",
        "response_model": "GeospatialResponse",
        "summary": "Get regional health data",
        "description": "Aggregate health metrics by geographic region for choropleth mapping."
      }
    },
    {
      "id": "backend/app/api/nlp.py",
      "type": "file",
      "label": "nlp.py",
      "path": "backend/app/api/nlp.py"
    },
    {
      "id": "backend/app/services/clinical_ontology_mapper.py",
      "type": "service",
      "label": "clinical_ontology_mapper.py",
      "path": "backend/app/services/clinical_ontology_mapper.py"
    },
    {
      "id": "backend/app/services/graph_builder_db.py",
      "type": "service",
      "label": "graph_builder_db.py",
      "path": "backend/app/services/graph_builder_db.py"
    },
    {
      "id": "backend/app/services/nlp_entity_service.py",
      "type": "service",
      "label": "nlp_entity_service.py",
      "path": "backend/app/services/nlp_entity_service.py"
    },
    {
      "id": "backend/app/services/ontology_graph_integration.py",
      "type": "service",
      "label": "ontology_graph_integration.py",
      "path": "backend/app/services/ontology_graph_integration.py"
    },
    {
      "id": "endpoint:POST /extract (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "POST /extract",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "POST",
        "path": "/extract",
        "function": "extract_entities",
        "response_model": "ExtractResponse",
        "summary": "Extract entities from clinical text",
        "description": "Extract clinical entities from text using NLP."
      }
    },
    {
      "id": "endpoint:POST /extract/batch (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "POST /extract/batch",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "POST",
        "path": "/extract/batch",
        "function": "batch_extract_entities",
        "response_model": "BatchExtractResponse",
        "summary": "Batch extract entities from multiple texts",
        "description": "Process multiple clinical texts for entity extraction."
      }
    },
    {
      "id": "endpoint:GET /models (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "GET /models",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "GET",
        "path": "/models",
        "function": "list_models",
        "response_model": "ModelsResponse",
        "summary": "List available NLP models",
        "description": "Get list of available NLP models for entity extraction."
      }
    },
    {
      "id": "endpoint:POST /normalize (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "POST /normalize",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "POST",
        "path": "/normalize",
        "function": "normalize_entities",
        "response_model": "NormalizeResponse",
        "summary": "Normalize entities to standard codes",
        "description": "Normalize extracted entities to standard vocabulary codes."
      }
    },
    {
      "id": "endpoint:GET /samples (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "GET /samples",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "GET",
        "path": "/samples",
        "function": "get_sample_notes",
        "summary": "Get sample clinical notes",
        "description": "Get sample clinical notes for testing the NLP extraction."
      }
    },
    {
      "id": "endpoint:POST /ontology/map (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "POST /ontology/map",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "POST",
        "path": "/ontology/map",
        "function": "ontology_map",
        "response_model": "OntologyMapResponse",
        "summary": "Map clinical text using ontology mapper",
        "description": "Fast deterministic extraction using clinical ontologies."
      }
    },
    {
      "id": "endpoint:POST /analyze (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "POST /analyze",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "POST",
        "path": "/analyze",
        "function": "hybrid_analyze",
        "response_model": "HybridAnalyzeResponse",
        "summary": "Hybrid clinical analysis",
        "description": "Combines deterministic extraction with optional LLM reasoning."
      }
    },
    {
      "id": "endpoint:GET /stats (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "GET /stats",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "GET",
        "path": "/stats",
        "function": "get_service_stats",
        "summary": "Get NLP service statistics",
        "description": "Get statistics about the NLP entity extraction service."
      }
    },
    {
      "id": "endpoint:POST /build-graph (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "POST /build-graph",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "POST",
        "path": "/build-graph",
        "function": "build_knowledge_graph",
        "response_model": "BuildGraphResponse",
        "summary": "Build knowledge graph from clinical text",
        "description": "Process clinical text through NLP extraction and build a knowledge graph."
      }
    },
    {
      "id": "endpoint:POST /batch-build-graph (backend/app/api/nlp.py)",
      "type": "endpoint",
      "label": "POST /batch-build-graph",
      "path": "backend/app/api/nlp.py",
      "meta": {
        "method": "POST",
        "path": "/batch-build-graph",
        "function": "batch_build_knowledge_graph",
        "summary": "Build knowledge graph from multiple notes",
        "description": "Process multiple clinical notes and build a combined knowledge graph for a patient."
      }
    },
    {
      "id": "backend/app/api/patients.py",
      "type": "file",
      "label": "patients.py",
      "path": "backend/app/api/patients.py"
    },
    {
      "id": "endpoint:GET /{patient_id}/graph (backend/app/api/patients.py)",
      "type": "endpoint",
      "label": "GET /{patient_id}/graph",
      "path": "backend/app/api/patients.py",
      "meta": {
        "method": "GET",
        "path": "/{patient_id}/graph",
        "function": "get_patient_graph",
        "response_model": "PatientGraph",
        "summary": "Get patient knowledge graph",
        "description": "Retrieve the complete knowledge graph for a patient, including all nodes and edges."
      }
    },
    {
      "id": "endpoint:POST /{patient_id}/graph/build (backend/app/api/patients.py)",
      "type": "endpoint",
      "label": "POST /{patient_id}/graph/build",
      "path": "backend/app/api/patients.py",
      "meta": {
        "method": "POST",
        "path": "/{patient_id}/graph/build",
        "function": "build_patient_graph",
        "response_model": "PatientGraph",
        "status_code": "status.HTTP_201_CREATED",
        "summary": "Build patient knowledge graph",
        "description": "Build or rebuild the knowledge graph for a patient from their clinical facts."
      }
    },
    {
      "id": "endpoint:GET /{patient_id}/facts (backend/app/api/patients.py)",
      "type": "endpoint",
      "label": "GET /{patient_id}/facts",
      "path": "backend/app/api/patients.py",
      "meta": {
        "method": "GET",
        "path": "/{patient_id}/facts",
        "function": "get_patient_facts",
        "response_model": null,
        "summary": "Get patient clinical facts",
        "description": "Retrieve all clinical facts for a patient, with optional filtering."
      }
    },
    {
      "id": "backend/app/api/drug_safety.py",
      "type": "file",
      "label": "drug_safety.py",
      "path": "backend/app/api/drug_safety.py"
    },
    {
      "id": "endpoint:POST /check (backend/app/api/drug_safety.py)",
      "type": "endpoint",
      "label": "POST /check",
      "path": "backend/app/api/drug_safety.py",
      "meta": {
        "method": "POST",
        "path": "/check",
        "function": "check_drug_safety",
        "response_model": "SafetyCheckResponse",
        "summary": "Check drug safety",
        "description": "Check drug safety given patient context including conditions, medications, and demographics."
      }
    },
    {
      "id": "backend/app/api/graph_rag.py",
      "type": "file",
      "label": "graph_rag.py",
      "path": "backend/app/api/graph_rag.py"
    },
    {
      "id": "endpoint:GET /search/{patient_id} (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "GET /search/{patient_id}",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "GET",
        "path": "/search/{patient_id}",
        "function": "search_graph",
        "response_model": "GraphSearchResult"
      }
    },
    {
      "id": "endpoint:GET /patient-summary/{patient_id} (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "GET /patient-summary/{patient_id}",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "GET",
        "path": "/patient-summary/{patient_id}",
        "function": "get_patient_summary",
        "response_model": "PatientSummary"
      }
    },
    {
      "id": "endpoint:POST /answer (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "POST /answer",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "POST",
        "path": "/answer",
        "function": "answer_clinical_question",
        "response_model": "ClinicalAnswer"
      }
    },
    {
      "id": "endpoint:GET /traverse/{patient_id}/{node_id} (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "GET /traverse/{patient_id}/{node_id}",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "GET",
        "path": "/traverse/{patient_id}/{node_id}",
        "function": "traverse_from_node",
        "response_model": "dict"
      }
    },
    {
      "id": "endpoint:GET /concepts/{patient_id} (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "GET /concepts/{patient_id}",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "GET",
        "path": "/concepts/{patient_id}",
        "function": "get_unique_concepts",
        "response_model": "dict"
      }
    },
    {
      "id": "endpoint:GET /ontology/search (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "GET /ontology/search",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "GET",
        "path": "/ontology/search",
        "function": "search_ontology_concepts",
        "response_model": "dict"
      }
    },
    {
      "id": "endpoint:GET /ontology/expand/{concept_id} (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "GET /ontology/expand/{concept_id}",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "GET",
        "path": "/ontology/expand/{concept_id}",
        "function": "expand_concept",
        "response_model": "dict"
      }
    },
    {
      "id": "endpoint:POST /ontology-enhanced-answer (backend/app/api/graph_rag.py)",
      "type": "endpoint",
      "label": "POST /ontology-enhanced-answer",
      "path": "backend/app/api/graph_rag.py",
      "meta": {
        "method": "POST",
        "path": "/ontology-enhanced-answer",
        "function": "answer_with_ontology",
        "response_model": "OntologyEnrichedAnswer"
      }
    },
    {
      "id": "backend/app/api/kg_benchmark.py",
      "type": "file",
      "label": "kg_benchmark.py",
      "path": "backend/app/api/kg_benchmark.py"
    },
    {
      "id": "endpoint:GET /health (backend/app/api/kg_benchmark.py)",
      "type": "endpoint",
      "label": "GET /health",
      "path": "backend/app/api/kg_benchmark.py",
      "meta": {
        "method": "GET",
        "path": "/health",
        "function": "benchmark_health"
      }
    },
    {
      "id": "backend/app/api/data_sources.py",
      "type": "file",
      "label": "data_sources.py",
      "path": "backend/app/api/data_sources.py"
    },
    {
      "id": "endpoint:GET /{source_id}/health (backend/app/api/data_sources.py)",
      "type": "endpoint",
      "label": "GET /{source_id}/health",
      "path": "backend/app/api/data_sources.py",
      "meta": {
        "method": "GET",
        "path": "/{source_id}/health",
        "function": "check_health",
        "response_model": "ConnectionTestResult"
      }
    },
    {
      "id": "backend/app/api/search.py",
      "type": "file",
      "label": "search.py",
      "path": "backend/app/api/search.py"
    },
    {
      "id": "backend/app/services/embedding_service.py",
      "type": "service",
      "label": "embedding_service.py",
      "path": "backend/app/services/embedding_service.py"
    },
    {
      "id": "backend/app/services/hybrid_search.py",
      "type": "service",
      "label": "hybrid_search.py",
      "path": "backend/app/services/hybrid_search.py"
    },
    {
      "id": "backend/app/services/vocabulary.py",
      "type": "service",
      "label": "vocabulary.py",
      "path": "backend/app/services/vocabulary.py"
    },
    {
      "id": "endpoint:POST /semantic/nodes (backend/app/api/search.py)",
      "type": "endpoint",
      "label": "POST /semantic/nodes",
      "path": "backend/app/api/search.py",
      "meta": {
        "method": "POST",
        "path": "/semantic/nodes",
        "function": "search_kg_nodes",
        "response_model": "SemanticSearchResponse",
        "summary": "Semantic search knowledge graph nodes",
        "description": "Search knowledge graph nodes using natural language."
      }
    },
    {
      "id": "backend/app/api/streaming.py",
      "type": "file",
      "label": "streaming.py",
      "path": "backend/app/api/streaming.py"
    },
    {
      "id": "endpoint:GET /health (backend/app/api/streaming.py)",
      "type": "endpoint",
      "label": "GET /health",
      "path": "backend/app/api/streaming.py",
      "meta": {
        "method": "GET",
        "path": "/health",
        "function": "get_streaming_health",
        "response_model": "HealthResponse"
      }
    },
    {
      "id": "backend/app/api/knowledge_graph_fhir.py",
      "type": "file",
      "label": "knowledge_graph_fhir.py",
      "path": "backend/app/api/knowledge_graph_fhir.py"
    },
    {
      "id": "endpoint:POST /provenance (backend/app/api/knowledge_graph_fhir.py)",
      "type": "endpoint",
      "label": "POST /provenance",
      "path": "backend/app/api/knowledge_graph_fhir.py",
      "meta": {
        "method": "POST",
        "path": "/provenance",
        "function": "export_reasoning_as_provenance",
        "response_model": null
      }
    },
    {
      "id": "endpoint:POST /evidence (backend/app/api/knowledge_graph_fhir.py)",
      "type": "endpoint",
      "label": "POST /evidence",
      "path": "backend/app/api/knowledge_graph_fhir.py",
      "meta": {
        "method": "POST",
        "path": "/evidence",
        "function": "export_causal_as_evidence",
        "response_model": null
      }
    },
    {
      "id": "endpoint:POST /library (backend/app/api/knowledge_graph_fhir.py)",
      "type": "endpoint",
      "label": "POST /library",
      "path": "backend/app/api/knowledge_graph_fhir.py",
      "meta": {
        "method": "POST",
        "path": "/library",
        "function": "export_concepts_as_library",
        "response_model": null
      }
    },
    {
      "id": "endpoint:POST /bundle (backend/app/api/knowledge_graph_fhir.py)",
      "type": "endpoint",
      "label": "POST /bundle",
      "path": "backend/app/api/knowledge_graph_fhir.py",
      "meta": {
        "method": "POST",
        "path": "/bundle",
        "function": "export_graph_as_bundle",
        "response_model": null
      }
    },
    {
      "id": "endpoint:POST /temporal-snapshot (backend/app/api/knowledge_graph_fhir.py)",
      "type": "endpoint",
      "label": "POST /temporal-snapshot",
      "path": "backend/app/api/knowledge_graph_fhir.py",
      "meta": {
        "method": "POST",
        "path": "/temporal-snapshot",
        "function": "export_temporal_snapshot",
        "response_model": null
      }
    },
    {
      "id": "endpoint:GET /stats (backend/app/api/knowledge_graph_fhir.py)",
      "type": "endpoint",
      "label": "GET /stats",
      "path": "backend/app/api/knowledge_graph_fhir.py",
      "meta": {
        "method": "GET",
        "path": "/stats",
        "function": "get_export_stats",
        "response_model": null
      }
    },
    {
      "id": "backend/app/services/vocabulary_version_service.py",
      "type": "service",
      "label": "vocabulary_version_service.py",
      "path": "backend/app/services/vocabulary_version_service.py"
    },
    {
      "id": "backend/app/services/fhir_import.py",
      "type": "service",
      "label": "fhir_import.py",
      "path": "backend/app/services/fhir_import.py"
    },
    {
      "id": "backend/app/models/clinical_fact.py",
      "type": "model",
      "label": "clinical_fact.py",
      "path": "backend/app/models/clinical_fact.py"
    },
    {
      "id": "backend/app/models/knowledge_graph.py",
      "type": "model",
      "label": "knowledge_graph.py",
      "path": "backend/app/models/knowledge_graph.py"
    },
    {
      "id": "backend/app/services/phenotype_engine.py",
      "type": "service",
      "label": "phenotype_engine.py",
      "path": "backend/app/services/phenotype_engine.py"
    },
    {
      "id": "backend/app/services/impact_analysis_service.py",
      "type": "service",
      "label": "impact_analysis_service.py",
      "path": "backend/app/services/impact_analysis_service.py"
    },
    {
      "id": "backend/app/services/graph_augmented_rag.py",
      "type": "service",
      "label": "graph_augmented_rag.py",
      "path": "backend/app/services/graph_augmented_rag.py"
    },
    {
      "id": "backend/app/services/temporal_query_service.py",
      "type": "service",
      "label": "temporal_query_service.py",
      "path": "backend/app/services/temporal_query_service.py"
    },
    {
      "id": "backend/app/services/semantic_search.py",
      "type": "service",
      "label": "semantic_search.py",
      "path": "backend/app/services/semantic_search.py"
    },
    {
      "id": "frontend/src/components/KnowledgeGraph",
      "type": "dir",
      "label": "frontend/src/components/KnowledgeGraph",
      "path": "frontend/src/components/KnowledgeGraph"
    }
  ],
  "edges": [
    {
      "from": "backend/app/api",
      "to": "backend/app/api/cohorts.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/cohort_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/cohorts.py",
      "to": "backend/app/services/cohort_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/cohorts.py",
      "to": "endpoint:GET /{cohort_id}/demographics (backend/app/api/cohorts.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /{cohort_id}/demographics (backend/app/api/cohorts.py)",
      "to": "backend/app/services/cohort_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/kg_orchestration.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_database_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/provenance_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /status (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /clinical-question (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /reasoning-path (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/graph (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patient/{patient_id}/timeline (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /export (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /mdt-session (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /semantic-groups (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_orchestration.py",
      "to": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /relationship-types (backend/app/api/kg_orchestration.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/terminology_cache.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/health.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_database_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/kafka_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "backend/app/services/kafka_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/terminology_cache.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "backend/app/services/terminology_cache.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "endpoint:GET  (backend/app/api/health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET  (backend/app/api/health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET  (backend/app/api/health.py)",
      "to": "backend/app/services/kafka_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET  (backend/app/api/health.py)",
      "to": "backend/app/services/terminology_cache.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "endpoint:GET /live (backend/app/api/health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /live (backend/app/api/health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /live (backend/app/api/health.py)",
      "to": "backend/app/services/kafka_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /live (backend/app/api/health.py)",
      "to": "backend/app/services/terminology_cache.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "endpoint:GET /ready (backend/app/api/health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /ready (backend/app/api/health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /ready (backend/app/api/health.py)",
      "to": "backend/app/services/kafka_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /ready (backend/app/api/health.py)",
      "to": "backend/app/services/terminology_cache.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "endpoint:GET /deep (backend/app/api/health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /deep (backend/app/api/health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /deep (backend/app/api/health.py)",
      "to": "backend/app/services/kafka_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /deep (backend/app/api/health.py)",
      "to": "backend/app/services/terminology_cache.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "endpoint:GET /cache (backend/app/api/health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /cache (backend/app/api/health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /cache (backend/app/api/health.py)",
      "to": "backend/app/services/kafka_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /cache (backend/app/api/health.py)",
      "to": "backend/app/services/terminology_cache.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/health.py",
      "to": "endpoint:POST /cache/clear (backend/app/api/health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /cache/clear (backend/app/api/health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /cache/clear (backend/app/api/health.py)",
      "to": "backend/app/services/kafka_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /cache/clear (backend/app/api/health.py)",
      "to": "backend/app/services/terminology_cache.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/phenotypes.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/phenotypes.py",
      "to": "endpoint:POST /{patient_id}/evaluate/{phenotype_id} (backend/app/api/phenotypes.py)",
      "type": "defines"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/graph.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_database_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /health (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /health (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /health (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /health (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /health (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /cache/stats (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /cache/stats (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /cache/stats (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /cache/stats (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /cache/stats (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:DELETE /cache/clear (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:DELETE /cache/clear (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:DELETE /cache/clear (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:DELETE /cache/clear (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:DELETE /cache/clear (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /concepts/{concept_id}/neighbors (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/neighbors (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/neighbors (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/neighbors (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/neighbors (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /concepts/{concept_id}/ancestors (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/ancestors (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/ancestors (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/ancestors (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/{concept_id}/ancestors (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:POST /concepts/path (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /concepts/path (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /concepts/path (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /concepts/path (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /concepts/path (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /patients/{patient_id}/similar (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/similar (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/similar (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/similar (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/similar (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /patients/{patient_id}/subgraph (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/subgraph (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/subgraph (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/subgraph (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients/{patient_id}/subgraph (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:POST /query (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /stats (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /stats (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /stats (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /stats (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /stats (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:POST /etl/load-sample (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /etl/load-sample (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /etl/load-sample (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /etl/load-sample (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /etl/load-sample (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/graph.py",
      "to": "endpoint:GET /concepts/search (backend/app/api/graph.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /concepts/search (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/search (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/search (backend/app/api/graph.py)",
      "to": "backend/app/services/graph_etl_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /concepts/search (backend/app/api/graph.py)",
      "to": "backend/app/services/kg_cache_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/terminology_cache.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/policy_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/llm_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/kg_health.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_database_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/provenance_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "endpoint:GET / (backend/app/api/kg_health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET / (backend/app/api/kg_health.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /component/{component_name} (backend/app/api/kg_health.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /dependencies (backend/app/api/kg_health.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /liveness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /readiness (backend/app/api/kg_health.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /metrics (backend/app/api/kg_health.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/kg_health.py",
      "to": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/causal_reasoning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/drknows_benchmark_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_analytics_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_database_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/graph_embedding_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_kafka_streaming_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_partitioning_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/kg_visualization_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/medagentbench_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/multi_agent_orchestrator.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /alerts (backend/app/api/kg_health.py)",
      "to": "backend/app/services/provenance_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/clinical_agent.py",
      "type": "contains"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/llm_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "backend/app/services/llm_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/policy_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "backend/app/services/policy_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "endpoint:POST /import (backend/app/api/clinical_agent.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /import (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /import (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/llm_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /import (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /import (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/policy_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /import (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "endpoint:POST /build-graph (backend/app/api/clinical_agent.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /build-graph (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /build-graph (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/llm_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /build-graph (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /build-graph (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/policy_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /build-graph (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "endpoint:GET /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/llm_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/policy_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "endpoint:POST /query/{patient_id} (backend/app/api/clinical_agent.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:POST /query/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/llm_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/policy_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:POST /query/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "endpoint:DELETE /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:DELETE /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:DELETE /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/llm_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:DELETE /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "uses"
    },
    {
      "from": "endpoint:DELETE /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/policy_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:DELETE /graph/{patient_id} (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/api/clinical_agent.py",
      "to": "endpoint:GET /patients (backend/app/api/clinical_agent.py)",
      "type": "defines"
    },
    {
      "from": "endpoint:GET /patients (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/guideline_rag_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/llm_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/nlp_rule_based.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/policy_service.py",
      "type": "uses"
    },
    {
      "from": "endpoint:GET /patients (backend/app/api/clinical_agent.py)",
      "to": "backend/app/services/provenance_db_service.py",
      "type": "uses"
    },
    {
      "from": "backend/app/services",
      "to": "backend/app/services/llm_service.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/visualizations.py",
      "type": "contains"
    },
    {
      "from": "backend/app/api/visualizations.py",
      "to": "endpoint:GET /geospatial (backend/app/api/visualizations.py)",
      "type": "defines"
    },
    {
      "from": "backend/app/api",
      "to": "backend/app/api/nlp.py",
      "type": "contains"
    }
  ]
}
```
