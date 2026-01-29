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
