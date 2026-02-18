# Clinical Ontology Normalizer

A comprehensive healthcare data platform for clinical NLP extraction, terminology normalization, knowledge graph construction, and clinical decision support. The system processes unstructured clinical text, maps entities to standard vocabularies (OMOP, SNOMED-CT, ICD-10, RxNorm, LOINC), and provides a rich set of clinical intelligence APIs.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)

---

## Current Readiness Snapshot

- **Posture:** CONDITIONAL GO (pilot)
- **Scope closed:** P0/P1/P2/P3 complete; all P0/P1/P2/P3 gates closed.
- **P4:** Decisions 20/20 complete; I/V 15/20 each with 5 ADR-deferred gates.
- **ROL-08:** PASS — 79 precision guardrail tests, lint clean, zero regressions.
- **ROL-09:** PASS — explicit go/no-go table with residual risks recorded.
- **Staging blockers remaining (5):** OpenEHR round-trip, Redis failover, Neo4j restore, cascade failover, 30-day review.

- **Readiness artifacts**
  - [Snapshot packet](docs/readiness_snapshot_2026-02-17.md)
  - [Execution board](tasks/08_autonomous_execution_board.md)
  - [Rollup backlog](tasks/09_master_change_backlog_p0_p4.md)
  - [Run log](tasks/04_enterprise_readiness_multi_agent_playbook_run.md)

- **Public proof surface:** `/proof`

## Overview

### What Does This System Do?

The Clinical Ontology Normalizer is an enterprise healthcare data platform that:

1. **Extracts Clinical Entities** - Processes clinical notes using NLP to identify diagnoses, medications, procedures, lab results, vital signs, allergies, and more
2. **Normalizes to Standard Vocabularies** - Maps extracted entities to OMOP concept IDs, SNOMED-CT, ICD-10-CM, CPT, RxNorm, LOINC, and other standard terminologies
3. **Builds Knowledge Graphs** - Constructs patient-centric knowledge graphs in Neo4j for relationship discovery and clinical reasoning
4. **Provides Clinical Decision Support** - Offers drug interaction checking, differential diagnosis, HCC gap analysis, and quality measure tracking
5. **Enables Interoperability** - Full FHIR R4 support with CDS Hooks, Bulk Data Export, SMART on FHIR, and terminology services

### Who Is It For?

- **Healthcare Organizations** - Hospitals, health systems, and clinics needing clinical NLP and terminology normalization
- **Health IT Developers** - Teams building clinical applications that require structured medical data
- **Clinical Researchers** - Researchers needing to extract and analyze clinical concepts from unstructured text
- **Health Information Management** - HIM professionals for coding assistance and documentation improvement
- **Population Health** - Teams tracking quality measures, care gaps, and risk stratification

### Problems It Solves

- Converting unstructured clinical notes into structured, queryable data
- Standardizing clinical terminology across disparate systems
- Identifying drug interactions and safety concerns in real-time
- Detecting HCC coding gaps and revenue optimization opportunities
- Tracking HEDIS/CQM quality measures and care gaps
- Enabling multi-hop clinical reasoning through knowledge graphs

---

## Key Features

### Clinical NLP Extraction

| Feature | Description |
|---------|-------------|
| Entity Extraction | Diagnoses, medications, procedures, lab results, vital signs, allergies, anatomical locations |
| Negation Detection | Identifies negated findings (e.g., "denies chest pain", "no fever") |
| Assertion Status | Present, absent, possible, conditional, hypothetical, historical |
| Section Detection | HPI, ROS, Assessment, Plan, Medications, Allergies, Physical Exam |
| Temporal Extraction | Dates, durations, frequencies from clinical text |
| Value Extraction | Lab values, vital sign measurements with units |

### Terminology & Normalization

- **OMOP CDM Mapping** - 5.36M+ concepts from OMOP vocabularies
- **SNOMED-CT** - Clinical terms and relationships
- **ICD-10-CM/PCS** - Diagnosis and procedure codes
- **CPT/HCPCS** - Procedure and service codes
- **RxNorm** - Medication normalization
- **LOINC** - Laboratory and observation codes
- **NDC** - National Drug Codes

### Knowledge Graph

- **Neo4j Integration** - Graph database for clinical relationships
- **Multi-Hop Reasoning** - DR.KNOWS pattern for treatment path discovery
- **Patient Similarity** - Jaccard, cosine, and overlap similarity metrics
- **Evidence Aggregation** - Path scoring and confidence calculation
- **Concept Hierarchy** - Ancestor/descendant traversal

### Clinical Decision Support

| Module | Capabilities |
|--------|--------------|
| Drug Safety | Contraindications, interactions, pregnancy/lactation safety, dosing guidelines |
| Drug Interactions | Multi-drug interaction checking with severity levels |
| Differential Diagnosis | Ranked differential diagnoses from symptoms and findings |
| Clinical Calculators | 50+ validated calculators (MELD, CHA2DS2-VASc, Wells, etc.) |
| Lab Reference | Normal ranges, critical values, interpretation guidance |

### Revenue Cycle & Coding

- **ICD-10 Suggestions** - Code suggestions from clinical text with CER citations
- **CPT Suggestions** - Procedure code recommendations with bundling analysis
- **HCC Analysis** - Hierarchical Condition Category gap detection with RAF scores
- **Coding Assistant** - AI-powered coding query resolution

### Quality Measures

- **HEDIS Measures** - Healthcare Effectiveness Data tracking
- **CQM/eCQM** - Clinical Quality Measures with numerator/denominator logic
- **MIPS Measures** - Merit-based Incentive Payment System
- **Care Gap Detection** - Identify patients with missing care activities
- **Performance Trending** - Historical performance and benchmark comparison

### FHIR & Standards Compliance

| Standard | Implementation |
|----------|----------------|
| FHIR R4 | Full resource support, import/export |
| CDS Hooks 1.1 | patient-view, medication-prescribe, order-sign hooks |
| Bulk Data Export | $export operations per HL7 specification |
| SMART on FHIR | Authorization server with OAuth 2.0 flows |
| Terminology Services | $lookup, $validate-code, $expand, $translate, $subsumes |
| CDISC | SDTM/ADaM mappings for clinical trials |
| TEFCA | Trusted Exchange Framework support |

### Additional Capabilities

- **Semantic Search** - Vector-based similarity search across concepts
- **Patient Timeline** - Chronological clinical event visualization
- **Cohort Builder** - Define and analyze patient populations
- **Federated Learning** - Privacy-preserving model training
- **Synthetic Data** - Generate realistic synthetic patient data
- **Voice Integration** - Speech-to-text for clinical documentation
- **Streaming/SSE** - Real-time updates and Kafka integration

---

## Architecture

```
+-----------------------------------------------------------------------------------+
|                              Frontend (Next.js 16)                                 |
|  Dashboard | Patients | Knowledge Graph | Clinical Tools | Billing | Analytics   |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                              Backend (FastAPI)                                     |
|  +-------------+  +-------------+  +-------------+  +------------------+          |
|  |   NLP API   |  | Graph API   |  |  FHIR API   |  | CDS Hooks API    |          |
|  +-------------+  +-------------+  +-------------+  +------------------+          |
|  +-------------+  +-------------+  +-------------+  +------------------+          |
|  | Drug Safety |  | HCC Analysis|  | Quality Msr |  | Predictions API  |          |
|  +-------------+  +-------------+  +-------------+  +------------------+          |
+-----------------------------------------------------------------------------------+
         |                    |                    |                    |
         v                    v                    v                    v
+----------------+   +----------------+   +----------------+   +----------------+
|   PostgreSQL   |   |     Neo4j      |   |     Redis      |   |     Kafka      |
|   (OMOP CDM)   |   | Knowledge Graph|   |  Cache/Queue   |   |   Streaming    |
+----------------+   +----------------+   +----------------+   +----------------+
```

### Core Components

| Component | Role | Port |
|-----------|------|------|
| **PostgreSQL 16** | Primary database with OMOP vocabulary, clinical facts, audit logs | 15432 |
| **Neo4j 5** | Knowledge graph database with APOC plugin | 7474 (HTTP), 7687 (Bolt) |
| **Redis 7** | Caching, session storage, job queue | 16379 |
| **Kafka** | Real-time streaming for HL7v2/FHIR messages | 9092, 29092 |
| **Zookeeper** | Kafka coordination | 2181 |
| **Backend** | FastAPI application server | 8080 |
| **Worker** | RQ background job processor | - |
| **Frontend** | Next.js web application | 3000 |

### Service Communication

- Frontend proxies `/api/*` to Backend `/api/v1/*`
- Backend connects to PostgreSQL via async SQLAlchemy
- Knowledge graph operations use Neo4j Bolt protocol
- Background jobs processed via Redis Queue (RQ)
- Real-time events streamed via Kafka or SSE

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.109+ | Web framework |
| SQLAlchemy | 2.0+ | ORM (async) |
| asyncpg | 0.29+ | PostgreSQL driver |
| neo4j | 5.15+ | Graph database driver |
| Pydantic | 2.5+ | Data validation |
| Redis | 5.0+ | Caching client |
| RQ | 1.16+ | Background jobs |
| Alembic | 1.13+ | Database migrations |
| sentence-transformers | 2.2+ | Semantic embeddings |
| scikit-learn | 1.3+ | ML utilities |
| pandas | 2.0+ | Data processing |
| httpx | 0.26+ | HTTP client |
| PyJWT | 2.8+ | JWT authentication |
| bcrypt | 4.0+ | Password hashing |
| cryptography | 41.0+ | Encryption |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 16.1 | React framework |
| React | 19.2 | UI library |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 4.x | Styling |
| Radix UI | Various | Accessible components |
| TanStack Query | 5.90+ | Data fetching |
| D3.js | 7.9 | Graph visualization |
| Recharts | 3.6 | Charts |
| Zod | 4.3+ | Schema validation |
| React Hook Form | 7.71+ | Form handling |
| Framer Motion | 12.26+ | Animations |

### Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| Docker | - | Containerization |
| Docker Compose | 3.8 | Orchestration |
| PostgreSQL | 16-alpine | Primary database |
| Neo4j | 5 | Graph database |
| Redis | 7-alpine | Cache/queue |
| Kafka | 7.5.0 | Event streaming |
| Zookeeper | 7.5.0 | Kafka coordination |

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** (required)
- **Node.js 18+** (for frontend development)
- **Python 3.11+** with **uv** (for backend development)

### Quick Start with Docker

The easiest way to get started is using the provided startup script:

```bash
# Clone the repository
git clone <repository-url>
cd jan-14-2026

# Start all services
./backend/scripts/start_all.sh

# Or for a clean start (removes existing data)
./backend/scripts/start_all.sh --clean
```

The script will:
1. Verify Docker is running
2. Start all services via Docker Compose
3. Wait for services to become healthy
4. Run database migrations
5. Create a demo user

### Manual Docker Compose

```bash
# Start all services
docker compose up -d

# Run database migrations
docker compose run --rm migrations

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

### Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Web application |
| Backend API | http://localhost:8080 | REST API |
| API Documentation | http://localhost:8080/api/v1/docs | Swagger UI |
| ReDoc | http://localhost:8080/api/v1/redoc | Alternative docs |
| Neo4j Browser | http://localhost:7474 | Graph database UI |
| PostgreSQL | localhost:15432 | Database (external port) |
| Redis | localhost:16379 | Cache (external port) |

### Demo Credentials

```
Email:    demo@example.com
Password: demo
```

### First Steps

1. **Health Check**: Verify the system is running
   ```bash
   curl http://localhost:8080/health
   ```

2. **List NLP Models**: See available extraction models
   ```bash
   curl http://localhost:8080/api/v1/nlp/models
   ```

3. **Extract Entities**: Process clinical text
   ```bash
   curl -X POST http://localhost:8080/api/v1/nlp/extract \
     -H "Content-Type: application/json" \
     -d '{"text": "Patient has type 2 diabetes and takes metformin 1000mg twice daily."}'
   ```

4. **Open the Dashboard**: Navigate to http://localhost:3000

---

## API Documentation

The API is organized into logical groups. Full interactive documentation is available at `/api/v1/docs`.

### Core Endpoints

#### NLP & Extraction
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/nlp/extract` | Extract entities from clinical text |
| POST | `/api/v1/nlp/extract/batch` | Batch extraction for multiple texts |
| POST | `/api/v1/nlp/normalize` | Normalize entities to standard codes |
| POST | `/api/v1/nlp/analyze` | Hybrid analysis (extraction + LLM reasoning) |
| POST | `/api/v1/nlp/build-graph` | Build knowledge graph from clinical text |
| GET | `/api/v1/nlp/models` | List available NLP models |

#### Knowledge Graph
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/graph/health` | Neo4j connection status |
| GET | `/api/v1/graph/concepts/{id}/neighbors` | Get related concepts |
| GET | `/api/v1/graph/concepts/{id}/ancestors` | Get concept hierarchy |
| POST | `/api/v1/graph/concepts/path` | Find path between concepts |
| GET | `/api/v1/graph/patients/{id}/subgraph` | Get patient knowledge graph |
| GET | `/api/v1/graph/patients/{id}/similar` | Find similar patients |
| POST | `/api/v1/graph/reasoning/multi-hop` | Multi-hop reasoning queries |
| POST | `/api/v1/graph/reasoning/find-treatments` | Find treatment paths |
| POST | `/api/v1/graph/reasoning/check-contraindications` | Check drug contraindications |

#### Clinical Decision Support
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/drug-safety/check` | Drug safety check with patient context |
| POST | `/api/v1/differential-diagnosis/analyze` | Generate differential diagnoses |
| POST | `/api/v1/clinical-calculators/calculate` | Execute clinical calculators |
| GET | `/api/v1/lab-reference/ranges` | Get lab normal ranges |

#### Billing & Coding
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/icd10-suggestions/suggest` | ICD-10 code suggestions |
| POST | `/api/v1/cpt-suggestions/suggest` | CPT code suggestions |
| POST | `/api/v1/hcc-analysis/analyze` | HCC gap analysis |
| GET | `/api/v1/hcc-analysis/opportunities` | Get HCC opportunities |

#### Quality Measures
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/quality-measures` | List quality measures |
| GET | `/api/v1/quality-measures/{id}` | Get measure details |
| POST | `/api/v1/quality-measures/{id}/calculate` | Calculate performance |
| GET | `/api/v1/quality-measures/gaps` | Get care gaps |

#### FHIR
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/fhir/import` | Import patient from FHIR server |
| GET | `/api/v1/fhir/patients/{id}` | Fetch FHIR patient |
| POST | `/api/v1/fhir/$export` | Start bulk data export |
| GET | `/api/v1/fhir/$export/{job_id}` | Get export status |

#### CDS Hooks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cds-services` | Discovery endpoint |
| POST | `/api/v1/cds-services/{id}` | Invoke CDS Hook |

#### Terminology Services
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/fhir/CodeSystem/$lookup` | Concept lookup |
| POST | `/api/v1/fhir/CodeSystem/$validate-code` | Validate code |
| POST | `/api/v1/fhir/ValueSet/$expand` | Expand value set |
| POST | `/api/v1/fhir/ConceptMap/$translate` | Translate codes |

### Authentication

Most endpoints require API key authentication via the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/v1/patients
```

Public endpoints (health, metrics) do not require authentication.

### Rate Limiting

API responses include rate limit headers:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when window resets

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI route handlers (80+ routers)
│   │   │   ├── nlp.py              # NLP extraction endpoints
│   │   │   ├── graph.py            # Knowledge graph endpoints
│   │   │   ├── fhir.py             # FHIR import/export
│   │   │   ├── cds_hooks.py        # CDS Hooks implementation
│   │   │   ├── drug_safety.py      # Drug safety checking
│   │   │   ├── hcc_analysis.py     # HCC gap analysis
│   │   │   ├── predictions.py      # Predictive analytics
│   │   │   ├── quality_measures.py # Quality measure tracking
│   │   │   └── ...                 # 70+ additional routers
│   │   ├── core/                   # Core configuration
│   │   │   ├── config.py           # Settings management
│   │   │   ├── database.py         # Database connections
│   │   │   ├── redis.py            # Redis client
│   │   │   └── queue.py            # Job queue setup
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic schemas
│   │   ├── services/               # Business logic (100+ services)
│   │   │   ├── nlp_entity_service.py
│   │   │   ├── graph_database_service.py
│   │   │   ├── drug_safety.py
│   │   │   ├── hcc_analyzer.py
│   │   │   ├── quality_measures.py
│   │   │   └── ...
│   │   └── main.py                 # FastAPI application entry
│   ├── alembic/                    # Database migrations
│   ├── scripts/                    # Utility scripts
│   │   ├── start_all.sh            # Full stack startup
│   │   └── ...
│   ├── tests/                      # Test suite
│   ├── Dockerfile                  # Backend container
│   └── pyproject.toml              # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router pages
│   │   │   ├── dashboard/          # Main dashboard
│   │   │   ├── patients/           # Patient management
│   │   │   │   └── [patientId]/
│   │   │   │       ├── graph/      # Knowledge graph viewer
│   │   │   │       ├── timeline/   # Patient timeline
│   │   │   │       └── facts/      # Clinical facts
│   │   │   ├── clinical/           # Clinical tools
│   │   │   │   ├── safety/         # Drug safety
│   │   │   │   ├── differential/   # Differential diagnosis
│   │   │   │   ├── icd10/          # ICD-10 coding
│   │   │   │   ├── cpt/            # CPT coding
│   │   │   │   └── hcc/            # HCC analysis
│   │   │   ├── billing/            # Revenue cycle
│   │   │   ├── quality/            # Quality measures
│   │   │   ├── analytics/          # Analytics dashboards
│   │   │   ├── etl/                # ETL pipelines
│   │   │   ├── cohorts/            # Cohort builder
│   │   │   ├── admin/              # Administration
│   │   │   └── ...
│   │   ├── components/             # React components
│   │   └── lib/                    # Utilities, API client
│   ├── Dockerfile                  # Frontend container
│   └── package.json                # Node dependencies
│
├── docker-compose.yml              # Container orchestration
├── .env.example                    # Environment template
└── README.md                       # This file
```

---

## Configuration

### Environment Variables

Key environment variables (create `.env` from `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/clinical_ontology

# Redis
REDIS_URL=redis://redis:6379

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=clinical123

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Authentication
AUTH_ENABLED=false                    # Enable for production
API_KEY=dev-api-key-change-in-production
JWT_SECRET_KEY=your-secret-key

# LLM Configuration (for AI features)
ANTHROPIC_API_KEY=your-anthropic-key
LLM_PROVIDER=anthropic
LLM_MODEL=claude-opus-4-5-20251101

# Feature Flags
ENABLE_CONCEPT_MAPPING=false
USE_ONTOLOGY_EDGES=true
ENABLE_TEMPORAL_EXTRACTION=true

# CORS (production)
CORS_ORIGINS=https://your-domain.com
```

### Security Configuration

For production deployments:

1. Set `AUTH_ENABLED=true`
2. Generate a secure `JWT_SECRET_KEY`
3. Set unique `API_KEY` values
4. Configure `CORS_ORIGINS` for your domain
5. Use secure `NEO4J_PASSWORD`
6. Enable TLS/SSL for all connections

---

## Development

### Local Backend Development

```bash
cd backend

# Install dependencies with uv
uv sync

# Set up environment
cp ../.env.example ../.env

# Start dependent services
docker compose up -d postgres redis neo4j

# Run migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --port 8000
```

### Local Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server (proxies to backend)
npm run dev
```

### Code Quality

```bash
# Backend linting
cd backend
uv run ruff check .
uv run mypy app

# Frontend linting
cd frontend
npm run lint
npm run typecheck
```

---

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/test_nlp_rule_based.py -v

# Run tests matching pattern
uv run pytest -k "test_extract" -v
```

### Frontend Tests

```bash
cd frontend

# Run unit tests
npm test

# Run with coverage
npm run test:coverage

# Run E2E tests (Playwright)
npm run test:e2e

# Run E2E with UI
npm run test:e2e:ui
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest` and `npm test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Coding Standards

- Python: Follow PEP 8, use type hints, run ruff and mypy
- TypeScript: Use strict mode, prefer functional components
- Commits: Use conventional commit messages
- Documentation: Update README and API docs for new features

---

## License

Proprietary - See LICENSE file for details.

---

## Support

For questions or issues:
- Open an issue on GitHub
- Email: support@example.com
- API Documentation: http://localhost:8080/api/v1/docs
