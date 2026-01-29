# Clinical Ontology Normalizer

A clinical NLP pipeline that extracts medical entities from clinical notes, maps them to OMOP standard concepts, and builds patient knowledge graphs for downstream analytics and interoperability.

## Features

- **Clinical NLP Pipeline**: Rule-based extraction of conditions, medications, measurements, procedures, and observations from clinical text
- **OMOP Concept Mapping**: Maps extracted entities to standardized OMOP concept IDs using a vocabulary database (5.36M+ concepts)
- **Negation Detection**: Identifies negated findings (e.g., "denies chest pain", "no fever")
- **Assertion Extraction**: Captures assertion status (present, absent, possible, conditional, hypothetical)
- **Temporality Detection**: Identifies temporal context (current, historical, future)
- **Knowledge Graph Construction**: Builds patient-centric knowledge graphs from clinical facts
- **FHIR Integration**: Import patient data from FHIR R4 servers
- **OMOP CDM Export**: Export clinical facts to OMOP Common Data Model format
- **Interactive Visualization**: D3.js force-directed graph visualization with filtering and highlighting

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│    Document Upload │ Patient Browser │ Knowledge Graph Viewer    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │  NLP    │──│ Mapping  │──│  Facts   │──│ Graph Builder   │  │
│  │ Service │  │ Service  │  │ Builder  │  │    Service      │  │
│  └─────────┘  └──────────┘  └──────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PostgreSQL                                 │
│    Documents │ Clinical Facts │ Knowledge Graph │ OMOP Vocab     │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI with async support
- SQLAlchemy 2.0 (async)
- PostgreSQL with pg_trgm extension
- Redis + RQ for job processing
- Alembic for database migrations

**Frontend:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- D3.js for graph visualization
- shadcn/ui components

**Infrastructure:**
- Docker Compose for local development
- HAPI FHIR server for FHIR integration
- FHIR MCP server for AI-assisted FHIR operations

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.11+ with uv (for backend development)

### Using Docker Compose

```bash
# Start all services (backend, frontend, postgres, redis)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

The services will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Local Development

**Backend:**
```bash
cd backend

# Install dependencies with uv
uv sync

# Set up environment variables
cp ../.env.example ../.env

# Run database migrations
uv run alembic upgrade head

# Seed OMOP vocabulary
uv run python -m scripts.seed_vocab

# Start the API server
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### FHIR Integration (Optional)

```bash
# Clone the FHIR MCP server (required for docker-compose.fhir.yml)
git clone https://github.com/jgsuess/fhir-mcp.git

# Start FHIR server stack
docker-compose -f docker-compose.fhir.yml up -d

# HAPI FHIR will be available at http://localhost:8090/fhir
# FHIR MCP server will be available at http://localhost:8001
```

## API Endpoints

### Documents
- `POST /documents` - Upload a clinical document for processing
- `GET /documents/{id}` - Get document details

### Jobs
- `GET /jobs/{id}` - Check processing job status

### Patients
- `GET /patients/{id}/facts` - Get clinical facts for a patient
- `GET /patients/{id}/graph` - Get knowledge graph for a patient
- `POST /patients/{id}/graph/build` - Build/rebuild patient graph

### FHIR
- `POST /fhir/import` - Import patient from FHIR server
- `GET /fhir/patients/{id}` - Preview FHIR patient data
- `GET /fhir/patients/{id}/summary` - Get summary of FHIR resources

### Export
- `GET /export/{patient_id}/omop` - Export patient to OMOP CDM format

### Search
- `GET /search/concepts` - Search OMOP concepts by text
- `GET /search/patients` - Search patients with clinical facts

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes
│   │   ├── core/           # Config, database, queue setup
│   │   ├── jobs/           # Background job processors
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic services
│   ├── alembic/            # Database migrations
│   ├── scripts/            # Utility scripts
│   └── tests/              # Test suite
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js app router pages
│   │   ├── components/     # React components
│   │   └── lib/            # API client, utilities
│   └── public/             # Static assets
├── fhir-mcp/               # FHIR MCP server for AI integration
├── fixtures/               # Sample data and vocabulary files
├── specs/                  # Design documents and specs
└── docker-compose.yml      # Docker orchestration
```

## Services Overview

### NLP Service (`nlp_rule_based.py`)
Rule-based clinical NLP that extracts:
- **Conditions**: Diagnoses, symptoms, findings
- **Drugs**: Medications with dosage patterns
- **Measurements**: Lab values, vital signs with units
- **Procedures**: Surgical and diagnostic procedures
- **Observations**: Other clinical observations

### Mapping Service (`mapping_sql.py`)
Maps extracted mentions to OMOP concepts using:
- Exact match on concept names and synonyms
- Prefix/contains matching for partial terms
- Multi-word term decomposition

### Fact Builder (`fact_builder_db.py`)
Creates ClinicalFact records with:
- OMOP concept ID
- Assertion status (present/absent/possible)
- Temporality (current/historical/future)
- Confidence scores
- Evidence tracking

### Graph Builder (`graph_builder_db.py`)
Constructs knowledge graphs with:
- Patient nodes as central hub
- Clinical fact nodes by type
- Relationship edges (has_condition, takes_drug, etc.)
- Property preservation from facts

## Sample Clinical Note

```
ED NOTE

Chief Complaint: Chest pain

History of Present Illness:
45-year-old male presents with substernal chest pain x2 hours.
Denies shortness of breath, nausea, or diaphoresis.

Past Medical History:
- Hypertension
- Type 2 Diabetes Mellitus
- No prior cardiac history

Medications:
- Metformin 1000mg BID
- Lisinopril 20mg daily
- Aspirin 81mg daily

Physical Exam:
BP 142/88, HR 78, RR 16, SpO2 98% RA
Heart: Regular rate and rhythm, no murmurs
Lungs: Clear to auscultation bilaterally

Assessment:
Chest pain, likely musculoskeletal. Rule out ACS.

Plan:
- Serial troponins
- EKG
- Observation
```

## Testing

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/test_nlp_rule_based.py -v
```

## Working With Agents

Use the prompt template and context bundler to keep tasks scoped and high-signal.

- Prompt template: `AGENT_PROMPT_TEMPLATE.md`
- Context bundle generator: `scripts/prepare_agent_context.py`

Example:

```bash
make agent-bundle
```

Filtered bundle:

```bash
python3 scripts/prepare_agent_context.py --query health --query graph --out agent_context_health_graph.md
```

Common domain bundles:

```bash
make agent-bundles
```

## Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/clinical_dev
SYNC_DATABASE_URL=postgresql://user:pass@localhost:5432/clinical_dev

# Redis
REDIS_URL=redis://localhost:6379

# API
DEBUG=true
SECRET_KEY=your-secret-key

# FHIR (optional)
FHIR_BASE_URL=http://localhost:8090/fhir
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
