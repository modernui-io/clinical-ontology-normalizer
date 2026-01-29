# Clinical Ontology Normalizer - Implementation Plan

## Overview
A system to ingest clinical data, extract mentions, map to OMOP concepts, build a patient knowledge graph, and expose via web UI.

## Progress Tracking
Each task should be completed in one iteration with tests passing before checking off.

---

## Phase 1: Repo Scaffolding & CI Gates

- [x] 1.1 Create backend Python package structure with pyproject.toml
- [x] 1.2 Set up backend linting (ruff) and formatting (black)
- [x] 1.3 Create pytest infrastructure with initial placeholder test
- [x] 1.4 Create Makefile with test, lint, typecheck targets
- [x] 1.5 Create AGENTS.md with workflow documentation
- [x] 1.6 Create 10 synthetic clinical note fixtures with expected outputs

## Phase 2: Data Models & Database

- [x] 2.1 Define Pydantic models for core entities (Document, Mention, ClinicalFact, etc.)
- [x] 2.2 Set up SQLAlchemy with async support and base model
- [x] 2.3 Create Document and StructuredResource tables with migrations
- [x] 2.4 Create Mention and MentionConceptCandidate tables with migrations
- [x] 2.5 Create ClinicalFact and FactEvidence tables with migrations
- [x] 2.6 Create KGNode and KGEdge tables with migrations
- [x] 2.7 Create seed script for local vocabulary fixture (OMOP concept subset)

## Phase 3: Ingestion API

- [x] 3.1 Set up FastAPI app with health endpoint
- [x] 3.2 Create document upload endpoint (POST /documents)
- [x] 3.3 Add Redis connection and RQ job queue setup
- [x] 3.4 Create job enqueue logic on document upload
- [x] 3.5 Add job status endpoint (GET /jobs/{job_id})
- [x] 3.6 Add document retrieval endpoint (GET /documents/{doc_id})

## Phase 4: NLP Pipeline (Mention Extraction)

- [x] 4.1 Create NLP service interface with extract_mentions method
- [x] 4.2 Implement rule-based mention extractor (regex for common patterns)
- [x] 4.3 Implement negation detection (NegEx-style rules)
- [x] 4.4 Implement temporality detection (past/current/future)
- [x] 4.5 Implement experiencer detection (patient/family/other)
- [x] 4.6 Create job worker that processes documents and creates Mentions
- [x] 4.7 Add tests with synthetic notes validating assertion/temporality/experiencer

## Phase 5: OMOP Mapping Service

- [x] 5.1 Create mapping service interface
- [x] 5.2 Load local vocabulary fixture into database
- [x] 5.3 Implement exact-match concept lookup
- [x] 5.4 Implement fuzzy/similarity-based concept lookup
- [x] 5.5 Create MentionConceptCandidate records with scores
- [x] 5.6 Add tests validating mapping accuracy on fixtures

## Phase 6: ClinicalFact Construction

- [x] 6.1 Create fact builder service interface
- [x] 6.2 Implement unstructured-to-fact conversion (from Mentions)
- [x] 6.3 Implement structured-to-fact conversion (from FHIR/CSV)
- [x] 6.4 Create FactEvidence links with provenance
- [x] 6.5 Handle negated findings correctly (assertion=absent)
- [x] 6.6 Add tests validating fact construction with evidence links

## Phase 7: Knowledge Graph Materialization

- [x] 7.1 Create graph builder service interface
- [x] 7.2 Implement patient node creation
- [x] 7.3 Implement fact-to-node projection (conditions, drugs, etc.)
- [x] 7.4 Implement edge creation (patient-has-condition, etc.)
- [x] 7.5 Add graph query API endpoint (GET /patients/{id}/graph)
- [x] 7.6 Add tests validating graph structure

## Phase 8: Web UI (Next.js)

- [x] 8.1 Initialize Next.js project with TypeScript
- [x] 8.2 Set up Tailwind CSS and component library
- [x] 8.3 Create document upload page
- [x] 8.4 Create job status/progress page
- [x] 8.5 Create document viewer with mention highlights
- [x] 8.6 Create clinical facts list view
- [x] 8.7 Create knowledge graph visualization (simple node/edge view)
- [x] 8.8 Add frontend linting and typecheck to Makefile

## Phase 9: OMOP Export

- [x] 9.1 Create export service interface
- [x] 9.2 Implement NOTE table export (document metadata)
- [x] 9.3 Implement NOTE_NLP export (mentions with assertion info)
- [x] 9.4 Create export endpoint (GET /export/omop)
- [x] 9.5 Add tests validating export format

## Phase 10: Hardening

- [x] 10.1 Add basic authentication middleware
- [x] 10.2 Add tenant/patient isolation
- [x] 10.3 Add audit logging for data access
- [x] 10.4 Add privacy safeguards (no real PHI checks)
- [x] 10.5 Final integration test across full pipeline

## Phase 11: Advanced NLP Enhancements

- [x] 11.1 Implement BioClinical ModernBERT NER Service
- [x] 11.2 Implement Neo4j Drug Interaction Enhancement

## Phase 12: Advanced ML Enhancements

- [ ] 12.1 Implement Computable Phenotype Engine
- [ ] 12.2 Implement Active Learning Feedback Service
- [x] 12.3 Implement Prediction Calibration Service

---

## Completion Criteria
All checkboxes must be checked, all tests must pass (`make test`), and all linting must pass (`make lint`) before outputting the completion promise.
