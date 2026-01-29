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

---

If you want a deeper, machine-friendly graph, see `codebase_kg.json`.
