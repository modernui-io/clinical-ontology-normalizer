# Data Pipeline Feature - Implementation Plan

## Overview

Build a comprehensive data ingestion pipeline system with both backend services and frontend UI that integrates with the existing clinical ontology platform. This enables importing patient data from Health Information Exchanges (HIEs), FHIR servers, and aggregator services, then transforming it through the ontology normalization pipeline.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Data Sources │  │  Pipelines   │  │  Job Monitor │  │   Quality    │    │
│  │  Management  │  │   Builder    │  │  Dashboard   │  │  Dashboard   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      Pipeline Orchestrator                            │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │  │
│  │  │Schedule │  │  Queue  │  │ Execute │  │ Monitor │  │  Alert  │   │  │
│  │  │ Manager │  │ Manager │  │ Workers │  │ Service │  │ Service │   │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐  │
│  │              Data Source Connectors                                   │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────────┐ │  │
│  │  │  FHIR  │  │  HIE   │  │ C-CDA  │  │ HL7v2  │  │  Aggregators   │ │  │
│  │  │ Server │  │ Direct │  │ Import │  │ Feed   │  │ (Particle,etc) │ │  │
│  │  └────────┘  └────────┘  └────────┘  └────────┘  └────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐  │
│  │              Transformation Pipeline                                  │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │  │
│  │  │ Ingest  │→ │Validate │→ │Transform│→ │  NLP    │→ │  Load   │   │  │
│  │  │  Stage  │  │  Stage  │  │  Stage  │  │ Enrich  │  │  Stage  │   │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐  │
│  │              Storage & Ontology                                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │  │
│  │  │  OMOP   │  │ Clinical │  │Knowledge │  │     Provenance       │ │  │
│  │  │   CDM   │  │  Facts   │  │  Graph   │  │      Records         │ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Phase 1: Data Source Management (Steps 1-6)

#### Step 1: Data Source Model
Create database model for storing configured data sources.

**File**: `backend/app/models/data_source.py`
```python
class DataSource(Base):
    id: UUID
    name: str
    source_type: Enum[FHIR_SERVER, HIE, AGGREGATOR, FILE_UPLOAD, HL7_FEED]
    connection_config: JSON  # encrypted credentials, URLs, auth tokens
    is_active: bool
    last_connected_at: datetime
    health_status: Enum[HEALTHY, DEGRADED, OFFLINE, UNKNOWN]
    created_at: datetime
    updated_at: datetime
```

**File**: `backend/app/models/pipeline.py`
```python
class Pipeline(Base):
    id: UUID
    name: str
    description: str
    source_id: FK -> DataSource
    schedule_cron: str  # cron expression for recurring
    is_active: bool
    transformation_config: JSON  # mapping rules, filters
    last_run_at: datetime
    next_run_at: datetime

class PipelineRun(Base):
    id: UUID
    pipeline_id: FK -> Pipeline
    status: Enum[PENDING, RUNNING, COMPLETED, FAILED, CANCELLED]
    started_at: datetime
    completed_at: datetime
    records_processed: int
    records_failed: int
    error_message: str
    statistics: JSON
```

#### Step 2: Alembic Migration
**File**: `backend/alembic/versions/025_create_pipeline_tables.py`
- Create `data_sources` table
- Create `pipelines` table
- Create `pipeline_runs` table
- Add indexes for status queries

#### Step 3: Data Source Service
**File**: `backend/app/services/data_source_service.py`
- CRUD operations for data sources
- Connection testing/validation
- Health check polling
- Credential encryption/decryption

#### Step 4: Data Source API
**File**: `backend/app/api/data_sources.py`
```
POST   /api/v1/data-sources           - Create data source
GET    /api/v1/data-sources           - List data sources
GET    /api/v1/data-sources/{id}      - Get data source details
PUT    /api/v1/data-sources/{id}      - Update data source
DELETE /api/v1/data-sources/{id}      - Delete data source
POST   /api/v1/data-sources/{id}/test - Test connection
GET    /api/v1/data-sources/{id}/health - Check health status
```

#### Step 5: Frontend - Data Sources Page
**File**: `frontend/src/app/admin/data-sources/page.tsx`
- List configured data sources with status indicators
- Add/Edit data source modal with connection wizard
- Test connection button with live feedback
- Health status badges (green/yellow/red)
- Source type icons (FHIR, HIE, etc.)

#### Step 6: Frontend - Data Source Configuration Wizard
**File**: `frontend/src/app/admin/data-sources/new/page.tsx`
- Step 1: Select source type (FHIR Server, HIE, Aggregator, File Upload)
- Step 2: Configure connection (URL, auth method, credentials)
- Step 3: Test connection and verify access
- Step 4: Configure default settings (batch size, retry policy)
- Step 5: Review and save

---

### Phase 2: Pipeline Builder (Steps 7-12)

#### Step 7: Pipeline Service
**File**: `backend/app/services/pipeline_service.py`
- Pipeline CRUD operations
- Schedule management (cron parsing, next run calculation)
- Pipeline execution trigger
- Run history management

#### Step 8: Pipeline Scheduler
**File**: `backend/app/services/pipeline_scheduler.py`
- Background scheduler using APScheduler or similar
- Cron expression evaluation
- Job queue integration (RQ)
- Missed job handling
- Concurrent execution limits

#### Step 9: Pipeline API
**File**: `backend/app/api/pipelines.py`
```
POST   /api/v1/pipelines              - Create pipeline
GET    /api/v1/pipelines              - List pipelines
GET    /api/v1/pipelines/{id}         - Get pipeline details
PUT    /api/v1/pipelines/{id}         - Update pipeline
DELETE /api/v1/pipelines/{id}         - Delete pipeline
POST   /api/v1/pipelines/{id}/run     - Trigger manual run
POST   /api/v1/pipelines/{id}/pause   - Pause scheduled runs
POST   /api/v1/pipelines/{id}/resume  - Resume scheduled runs
GET    /api/v1/pipelines/{id}/runs    - Get run history
GET    /api/v1/pipelines/{id}/runs/{run_id} - Get run details
```

#### Step 10: Frontend - Pipelines List Page
**File**: `frontend/src/app/pipelines/page.tsx`
- Pipeline cards with status, last run, next run
- Quick actions: Run Now, Pause, Edit, Delete
- Filter by status, source type
- Search by name

#### Step 11: Frontend - Pipeline Builder
**File**: `frontend/src/app/pipelines/new/page.tsx`
- Step 1: Name and description
- Step 2: Select data source
- Step 3: Configure schedule (manual, hourly, daily, weekly, custom cron)
- Step 4: Configure transformations:
  - Patient matching strategy
  - Code mapping preferences
  - NLP enrichment options
  - Data quality thresholds
- Step 5: Review and create

#### Step 12: Frontend - Pipeline Detail Page
**File**: `frontend/src/app/pipelines/[id]/page.tsx`
- Pipeline configuration summary
- Run history table with pagination
- Statistics charts (records over time, success rate)
- Recent errors list
- Manual run button

---

### Phase 3: Pipeline Execution Engine (Steps 13-18)

#### Step 13: Pipeline Executor
**File**: `backend/app/services/pipeline_executor.py`
- Orchestrates full pipeline execution
- Stage management (ingest → validate → transform → enrich → load)
- Progress tracking and event emission
- Error handling with configurable retry
- Partial failure handling (continue on error vs fail fast)

#### Step 14: Ingestion Stage
**File**: `backend/app/services/pipeline_stages/ingest.py`
- Connects to data source using appropriate connector
- Streams data in batches (memory efficient)
- Handles pagination for FHIR/API sources
- File parsing for uploads (FHIR Bundle JSON, C-CDA XML)
- Raw data staging

#### Step 15: Validation Stage
**File**: `backend/app/services/pipeline_stages/validate.py`
- FHIR resource validation
- Required field checks
- Code system validation (is this a valid SNOMED code?)
- Data type validation
- Duplicate detection
- Outputs validation report

#### Step 16: Transformation Stage
**File**: `backend/app/services/pipeline_stages/transform.py`
- FHIR → OMOP CDM mapping
- Code normalization (map to standard OMOP concepts)
- Unit standardization
- Date/time normalization
- Patient matching/linking
- Leverages existing ETL services

#### Step 17: NLP Enrichment Stage
**File**: `backend/app/services/pipeline_stages/enrich.py`
- Process clinical notes through NLP pipeline
- Extract mentions with assertion/temporality
- Map to OMOP concepts
- Create clinical facts
- Build knowledge graph nodes/edges

#### Step 18: Load Stage
**File**: `backend/app/services/pipeline_stages/load.py`
- Atomic batch inserts to OMOP tables
- Clinical fact creation with provenance
- Knowledge graph updates
- Rollback on failure
- Statistics collection

---

### Phase 4: Monitoring & Quality (Steps 19-24)

#### Step 19: Pipeline Monitor Service
**File**: `backend/app/services/pipeline_monitor.py`
- Real-time progress tracking
- WebSocket event broadcasting
- Metrics collection (throughput, latency, error rates)
- Alert triggering on failures

#### Step 20: Pipeline Events WebSocket
**File**: `backend/app/api/pipeline_ws.py`
- WebSocket endpoint for live pipeline updates
- Events: stage_started, stage_completed, record_processed, error, completed
- Room-based subscriptions (subscribe to specific pipeline run)

#### Step 21: Frontend - Pipeline Monitor Dashboard
**File**: `frontend/src/app/pipelines/monitor/page.tsx`
- Real-time view of running pipelines
- Progress bars for each stage
- Live record counter
- Error stream
- Cancel button

#### Step 22: Data Quality Dashboard
**File**: `frontend/src/app/pipelines/quality/page.tsx`
- Data completeness metrics by domain
- Code mapping success rates
- Validation error summaries
- Trend charts over time
- Drill-down to specific issues

#### Step 23: Pipeline Alerts
**File**: `backend/app/services/pipeline_alerts.py`
- Configurable alert rules (failure, degraded performance, data quality)
- Notification channels (email, webhook, in-app)
- Alert history and acknowledgment

#### Step 24: Frontend - Sidebar & Navigation
**File**: `frontend/src/components/Sidebar.tsx`
- Add "Data Pipeline" section with:
  - Data Sources
  - Pipelines
  - Pipeline Monitor
  - Data Quality

---

## Key Files Summary

### Backend - New Files
| File | Purpose |
|------|---------|
| `models/data_source.py` | Data source and pipeline models |
| `models/pipeline.py` | Pipeline and run models |
| `alembic/versions/025_*.py` | Database migration |
| `services/data_source_service.py` | Data source management |
| `services/pipeline_service.py` | Pipeline CRUD and scheduling |
| `services/pipeline_scheduler.py` | Background job scheduler |
| `services/pipeline_executor.py` | Pipeline execution orchestration |
| `services/pipeline_stages/*.py` | Individual stage implementations |
| `services/pipeline_monitor.py` | Progress tracking and metrics |
| `services/pipeline_alerts.py` | Alert management |
| `api/data_sources.py` | Data source REST endpoints |
| `api/pipelines.py` | Pipeline REST endpoints |
| `api/pipeline_ws.py` | WebSocket for live updates |

### Backend - Modified Files
| File | Changes |
|------|---------|
| `main.py` | Mount new routers |
| `api/__init__.py` | Export new routers |
| `models/__init__.py` | Export new models |

### Frontend - New Files
| File | Purpose |
|------|---------|
| `app/admin/data-sources/page.tsx` | Data sources list |
| `app/admin/data-sources/new/page.tsx` | Add data source wizard |
| `app/admin/data-sources/[id]/page.tsx` | Edit data source |
| `app/pipelines/page.tsx` | Pipelines list |
| `app/pipelines/new/page.tsx` | Pipeline builder |
| `app/pipelines/[id]/page.tsx` | Pipeline detail |
| `app/pipelines/monitor/page.tsx` | Live monitoring dashboard |
| `app/pipelines/quality/page.tsx` | Data quality dashboard |
| `components/pipeline/*.tsx` | Reusable pipeline components |

### Frontend - Modified Files
| File | Changes |
|------|---------|
| `components/Sidebar.tsx` | Add Data Pipeline nav section |

---

## Data Flow Example

### FHIR Server Import Flow
```
1. User creates Data Source (FHIR Server at https://hapi.example.com)
2. User creates Pipeline linked to that source
3. Pipeline scheduled to run daily at 2 AM

4. Scheduler triggers pipeline run:
   a. INGEST: Connect to FHIR server, fetch Patient/$everything
   b. VALIDATE: Check FHIR resources, flag invalid records
   c. TRANSFORM: Map to OMOP CDM using vocabulary service
   d. ENRICH: Process clinical notes through NLP
   e. LOAD: Insert into database with provenance

5. Results:
   - Person records in OMOP person table
   - Conditions in condition_occurrence
   - Medications in drug_exposure
   - Clinical facts with KG nodes/edges
   - Full provenance trail
```

### HIE/Aggregator Import Flow
```
1. User creates Data Source (Particle Health API)
2. User creates Pipeline with patient list

3. Pipeline executes:
   a. INGEST: Query aggregator for each patient
   b. VALIDATE: Normalize C-CDA documents
   c. TRANSFORM: Parse structured sections, map codes
   d. ENRICH: Extract from narrative sections via NLP
   e. LOAD: Merge with existing patient data

4. Patient matching:
   - MRN matching
   - Demographic matching (name, DOB, SSN last 4)
   - Probabilistic matching with confidence scores
```

---

## Technical Decisions

### Scheduler
- Use APScheduler with Redis job store for persistence
- Integrates with existing RQ workers
- Supports cron expressions and interval schedules

### Streaming
- AsyncIterator pattern for memory-efficient processing
- Configurable batch sizes (default 100 records)
- Backpressure handling

### Error Handling
- Configurable retry policy per pipeline
- Dead letter queue for failed records
- Partial success tracking (90% success = completed with warnings)

### Security
- Credentials encrypted at rest using Fernet
- API keys stored in secrets manager pattern
- Audit logging for all pipeline operations

### Monitoring
- Prometheus metrics endpoint
- WebSocket for real-time UI updates
- Structured logging for debugging

---

## Verification Checklist

### Phase 1 Complete When:
- [ ] Can create FHIR server data source via UI
- [ ] Can test connection and see success/failure
- [ ] Data sources persist and show in list
- [ ] Health status updates automatically

### Phase 2 Complete When:
- [ ] Can create pipeline linked to data source
- [ ] Can set schedule (manual, cron)
- [ ] Can trigger manual run
- [ ] Run appears in history

### Phase 3 Complete When:
- [ ] Pipeline executes all stages
- [ ] Data appears in OMOP tables
- [ ] Clinical facts created with provenance
- [ ] Knowledge graph updated

### Phase 4 Complete When:
- [ ] Can monitor running pipeline in real-time
- [ ] Quality metrics calculated and displayed
- [ ] Alerts fire on failure
- [ ] Full E2E flow works

---

## Dependencies

- Existing connector framework (FHIR, C-CDA, HL7)
- Existing ETL services
- Existing NLP pipeline
- Existing vocabulary service
- Redis (for scheduler persistence)
- WebSocket support (already in place)
