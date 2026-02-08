# CTO & VP Engineering Deep Implementation Plan

> Billion-dollar clinical trial matching SaaS hardening plan.
> Synthesized from codebase analysis of 177 service files, 95 API modules, 159 test files (4,261 test functions), 33 Alembic migrations, and 4 docker-compose configurations.
> Each item includes current state with file paths and line numbers, gap analysis, implementation steps, acceptance criteria, effort estimates, and cross-dependencies.

---

## Table of Contents

- [CTO Items](#cto-items)
  - [CTO-1: Architecture Scalability Audit](#cto-1-architecture-scalability-audit)
  - [CTO-2: Service Variant Consolidation](#cto-2-service-variant-consolidation)
  - [CTO-3: NLP Pipeline Regression Testing](#cto-3-nlp-pipeline-regression-testing)
  - [CTO-4: OMOP Mapping Quality](#cto-4-omop-mapping-quality)
  - [CTO-5: API Contract Stability](#cto-5-api-contract-stability)
  - [CTO-6: Observability Stack Design](#cto-6-observability-stack-design)
  - [CTO-7: Developer Experience Improvements](#cto-7-developer-experience-improvements)
- [VP Engineering Items](#vp-engineering-items)
  - [VPE-1: Test Coverage for Clinical Paths](#vpe-1-test-coverage-for-clinical-paths)
  - [VPE-2: CI/CD Maturity](#vpe-2-cicd-maturity)
  - [VPE-3: Database Migration Safety](#vpe-3-database-migration-safety)
  - [VPE-4: Service Reliability SLAs](#vpe-4-service-reliability-slas)
  - [VPE-5: Technical Debt Quantification](#vpe-5-technical-debt-quantification)
  - [VPE-6: Production Docker-Compose Hardening](#vpe-6-production-docker-compose-hardening)
- [Dependency Graph](#dependency-graph)
- [Sequencing and Timeline](#sequencing-and-timeline)

---

## CTO Items

### CTO-1: Architecture Scalability Audit

**Objective**: Determine what breaks first at 10x-100x data volume and document capacity limits for webhook ingestion, NLP processing, graph queries, and trial matching.

#### 1. Current State

**Database connection pool** (`backend/app/core/database.py`, lines 74-82):
```
engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```
Pool is configured at 20 base + 40 overflow = 60 max connections per process. The production docker-compose (`docker-compose.prod.yml`, line 37) configures PostgreSQL with `max_connections=200`. With 2 backend replicas (line 159) + 2 worker replicas (line 193), each with its own SQLAlchemy pool, that is 60 x 4 = 240 potential connections against 200 max. This will break under load.

**Job queue** (`backend/app/core/queue.py`, lines 144-152): RQ with Redis backend. Six named queues exist (document, nlp, mapping, graph, export, pipeline) but the worker command in `docker-compose.yml` (line 158) only listens on `document_processing` and `default` queues. The `nlp_processing`, `concept_mapping`, `graph_building`, `data_export`, and `pipeline_processing` queues have no consumer.

**Trial eligibility service** (`backend/app/services/trial_eligibility_service.py`, lines 50-52): Uses in-memory trial storage (`_TrialRecord` class). Trial data is lost on restart and cannot be shared across replicas. The comment on line 51 confirms: "In-memory trial storage (mirrors CohortService pattern)".

**Webhook ingestion**: The Metriport webhook handler at `backend/app/api/metriport_webhook.py` processes FHIR bundles synchronously. No backpressure mechanism exists. A burst of 100 concurrent webhook deliveries would saturate the backend.

**NLP processing**: The ensemble pipeline (`backend/app/services/nlp_ensemble.py`, 604 lines) runs extraction synchronously. The `EnsembleConfig` (lines 47-83) enables 5 extractors (rule-based, ML NER, ModernBERT, value extraction, relation extraction) that run sequentially. No parallelism or batching.

**Knowledge graph**: 23 KG-related service files exist under `backend/app/services/kg_*.py` and `backend/app/services/graph_*.py`. Neo4j connection pool is configured at 50 connections (`backend/app/core/config.py`, line 132). Graph builder operates in `graph_builder.py` (in-memory) and `graph_builder_db.py` (database-backed) with no fan-out.

**Kafka**: Configured in `docker-compose.yml` (lines 83-110) with Zookeeper dependency. `backend/app/services/kafka_service.py` exists but no consumer is wired in the application startup.

#### 2. Gap Analysis

| Bottleneck | Current Limit | 10x Target | Issue |
|---|---|---|---|
| DB connections | 60/replica x 4 replicas = 240 vs 200 max | Needs connection pooler (PgBouncer) | Connection exhaustion under load |
| Webhook ingestion | Synchronous, single-threaded per worker | 1000 webhooks/minute | No backpressure, no idempotency key |
| NLP throughput | ~5 documents/second (sequential extractors) | 50 docs/sec | Extractors run serially, no parallelism |
| Trial storage | In-memory, single process | Multi-replica persistent | Data loss on restart, no cross-replica sharing |
| Graph queries | Single Neo4j with 50-connection pool | Distributed reads | No read replicas, no query caching |
| Kafka | Configured but no consumer in backend | Event-driven pipeline | Kafka service exists but is unused |
| RQ queues | 4 of 6 queues have no consumer | All queues consumed | Worker only listens on 2 of 6 queues |

#### 3. Implementation Steps

**Step 1: Add PgBouncer connection pooler** (2 days)
- Add PgBouncer service to `docker-compose.yml` and `docker-compose.prod.yml`
- Route backend connections through PgBouncer in transaction mode
- Reduce per-process pool_size to 5, let PgBouncer manage the global pool
- File: `docker-compose.prod.yml` -- add pgbouncer service
- File: `backend/app/core/database.py` lines 74-82 -- reduce pool_size to 5, max_overflow to 10

**Step 2: Move trial storage to PostgreSQL** (3 days)
- Create Alembic migration for `trials`, `trial_criteria`, `trial_enrollments` tables
- File: `backend/alembic/versions/037_create_trial_persistence.py` (new)
- Refactor `backend/app/services/trial_eligibility_service.py` to use `AsyncSession`
- Remove `_TrialRecord` in-memory class (line 55)
- Add ORM model to `backend/app/models/trial.py`

**Step 3: Implement webhook backpressure** (2 days)
- File: `backend/app/api/metriport_webhook.py` -- enqueue webhook payloads to RQ instead of processing inline
- Add idempotency key checking (FHIR Bundle.id + hash)
- Add dead-letter queue for failed webhook processing
- File: `backend/app/core/queue.py` -- add `get_webhook_queue()` function

**Step 4: Parallelize NLP ensemble** (3 days)
- File: `backend/app/services/nlp_ensemble.py` -- refactor extraction to use `concurrent.futures.ThreadPoolExecutor`
- Run rule-based, ML NER, ModernBERT, and value extraction in parallel
- Keep relation extraction as sequential post-processing step (depends on other outputs)
- Add configurable `max_workers` to `EnsembleConfig` (after line 83)

**Step 5: Activate all RQ queue consumers** (1 day)
- File: `docker-compose.yml` line 158 -- expand worker queue list to include all 6 queues
- Alternatively, add dedicated worker services for high-volume queues (nlp, mapping)
- File: `docker-compose.prod.yml` -- add separate worker definitions per queue group

**Step 6: Document capacity limits** (1 day)
- Create `docs/CAPACITY_LIMITS.md` with load test results
- Define breaking points per service
- Establish capacity planning model for 10K/100K/1M patients

#### 4. Acceptance Criteria

- [ ] Connection pool exhaustion test: 100 concurrent API requests sustained for 60 seconds without connection errors
- [ ] Webhook burst test: 100 webhooks delivered in 10 seconds, all processed within 60 seconds, zero data loss
- [ ] NLP throughput: >20 documents/second with ensemble pipeline (4x improvement over baseline)
- [ ] Trial data survives backend restart and is consistent across 2 replicas
- [ ] All 6 RQ queues have active consumers
- [ ] Capacity limits document reviewed and signed off

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| PgBouncer pooler | 2 days |
| Trial storage migration | 3 days |
| Webhook backpressure | 2 days |
| NLP parallelization | 3 days |
| RQ queue activation | 1 day |
| Capacity documentation | 1 day |
| **Total** | **12 days** |

#### 6. Dependencies

- VPE-6 (Docker-compose hardening) -- PgBouncer changes overlap
- VPE-3 (Migration safety) -- trial table migration
- CTO-6 (Observability) -- capacity testing requires metrics collection
- VPE-4 (SLAs) -- capacity limits feed directly into SLA definitions

---

### CTO-2: Service Variant Consolidation

**Objective**: Map all 177 service files to Production/Pilot/Scaffold tiers, identify duplicates, and block Scaffold endpoints in production.

#### 1. Current State

The `backend/app/services/` directory contains 177 entries (files, `__init__.py`, `__pycache__`, and subdirectories). The following groups have clear duplication or variant proliferation:

**NLP Pipeline (10 files + 1 subpackage)**:

| File | LOC | Purpose | Proposed Tier |
|---|---|---|---|
| `nlp.py` | 119 | Interface + `BaseNLPService` abstract class | Production |
| `nlp_rule_based.py` | ~400 | Aho-Corasick rule-based extractor | Production |
| `nlp_clinical_ner.py` | ~500 | `ClinicalNERService(BaseNLPService)` -- transformer NER | Pilot |
| `nlp_modernbert_ner.py` | ~500 | `ModernBERTNERService(BaseNLPService)` -- 8K context | Pilot |
| `nlp_ensemble.py` | 604 | `EnsembleNLPService(BaseNLPService)` -- combines all | Pilot |
| `nlp_advanced.py` | ~700 | `AdvancedNLPService` -- another orchestrator | Pilot (duplicate?) |
| `nlp_claude_api.py` | ~500 | `LLMNLPService` -- LLM-based NLP via Claude API | Scaffold |
| `nlp_vocabulary.py` | ~300 | Vocabulary-backed NLP | Production |
| `nlp_coverage.py` | ~200 | Coverage analysis utility | Scaffold |
| `nlp_entity_service.py` | ~400 | Entity service wrapper | Production |
| `nlp_entity/` (subpackage) | 4,132 | Core, extractors, linkers, normalizers, ML models, date parser | Pilot |

**Concern**: `nlp_advanced.py` (`AdvancedNLPService`, line 437) and `nlp_ensemble.py` (`EnsembleNLPService`, line 99) are competing orchestrators. Both call into `nlp_rule_based.py` and `nlp_clinical_ner.py`. Unclear which is canonical.

**Vocabulary/Mapping (10 files)**:

| File | LOC | Purpose | Proposed Tier |
|---|---|---|---|
| `vocabulary.py` | ~500 | Core `VocabularyService` (file-based) | Production |
| `vocabulary_db.py` | ~400 | `DatabaseVocabularyService` | Production |
| `vocabulary_enhanced.py` | ~500 | `EnhancedVocabularyService(VocabularyService)` | Pilot |
| `vocabulary_mapping.py` | ~500 | `VocabularyMappingService` | Pilot |
| `vocabulary_version_service.py` | ~300 | Version tracking | Scaffold |
| `mapping.py` | 124+ | Interface `MappingServiceInterface` + `BaseMappingService` | Production |
| `mapping_db.py` | ~300 | `DatabaseMappingService(BaseMappingService)` | Production |
| `mapping_sql.py` | ~300 | `SQLMappingService(BaseMappingService)` | Pilot |
| `clinical_ontology_mapper.py` | 1,718 | Comprehensive mapper with fuzzy matching | Pilot |
| `concept_lookup.py` | ~300 | Simple concept lookup | Production |

**Concern**: Three mapping implementations (`mapping_db.py`, `mapping_sql.py`, `clinical_ontology_mapper.py`) with unclear routing of which is used when.

**Calculator Services (6 files)**:

| File | LOC | Purpose | Proposed Tier |
|---|---|---|---|
| `clinical_calculators.py` | 4,181 | `ClinicalCalculatorService` (mega-file) | Production |
| `clinical_calculator_service.py` | 3,034 | Another `ClinicalCalculatorService` (DUPLICATE NAME) | Pilot |
| `calculator_builder.py` | 1,355 | `CalculatorBuilderService` | Pilot |
| `calculator_definitions.py` | 12,713 | Definition data (largest service file in codebase) | Production |
| `calculator_kg_integration.py` | ~400 | KG integration | Scaffold |
| `calculator_reasoning_service.py` | ~400 | Reasoning service | Scaffold |

**CRITICAL**: Two files export classes with the identical name `ClinicalCalculatorService`. This is a namespace collision that causes unpredictable behavior depending on import order.

**Graph/KG Services (23 files)**:
- Core graph (7): `graph_builder.py`, `graph_builder_db.py`, `graph_database_service.py`, `graph_analytics_service.py`, `graph_augmented_rag.py`, `graph_embedding_service.py`, `graph_etl_service.py`
- KG infrastructure (16): `kg_api_key_service.py`, `kg_audit_service.py`, `kg_cache_service.py`, `kg_calculator_mapper.py`, `kg_config_service.py`, `kg_data_export_service.py`, `kg_grafana_dashboards.py`, `kg_kafka_streaming_service.py`, `kg_load_testing_service.py`, `kg_logging_service.py`, `kg_partitioning_service.py`, `kg_prometheus_metrics.py`, `kg_schema_migration_service.py`, `kg_tracing_service.py`, `kg_visualization_service.py`, `kg_webhook_service.py`

Many KG infrastructure services (load testing, Grafana dashboards, Kafka streaming) are Scaffold tier but are imported and registered at startup.

**Additional duplicates**:
- `semantic_search.py` and `semantic_search_service.py` -- both define `SemanticSearchService`
- `medication_reconciliation.py` (1,517 LOC) and `med_reconciliation_service.py` (86 LOC)
- `provenance_service.py`, `provenance_db_service.py`, `provenance_assembler.py` -- three provenance variants
- `export/omop_exporter.py` and `export/omop_exporter_db.py` -- two OMOP export variants

#### 2. Gap Analysis

- No maturity tier annotations on any service file
- No runtime gate preventing Scaffold endpoints from being called in production
- Two competing NLP orchestrators (`nlp_advanced.py` vs `nlp_ensemble.py`)
- Two classes named `ClinicalCalculatorService` in different files
- Two classes named `SemanticSearchService` in different files
- ~40% of service files are Pilot/Scaffold but loaded at startup, consuming memory and increasing startup time
- `main.py` pre-warm function (lines 119-342) attempts to load 25+ services at startup (though currently skipped at line 393)
- 82 routers registered in `main.py` (lines 640-720) with no conditional loading

#### 3. Implementation Steps

**Step 1: Annotate all service files with maturity tier** (2 days)
- Add module-level variable to every service file: `__maturity__ = "production"` or `"pilot"` or `"scaffold"`
- Create `backend/app/services/maturity.py` with `Maturity` enum and `@maturity_gate` decorator
- File: every `.py` file in `backend/app/services/` -- add `__maturity__` variable

**Step 2: Create maturity gate middleware** (1 day)
- File: `backend/app/api/middleware/maturity_gate.py` (new)
- Read `ENABLE_PILOT_ENDPOINTS` and `ENABLE_SCAFFOLD_ENDPOINTS` feature flags from config
- File: `backend/app/core/config.py` -- add `enable_pilot_endpoints: bool = True` and `enable_scaffold_endpoints: bool = False`
- Return 404 for scaffold endpoints when `environment == "production"` and flag is false

**Step 3: Consolidate NLP orchestrators** (3 days)
- Retire `nlp_advanced.py` -- merge any unique logic into `nlp_ensemble.py`
- File: `backend/app/services/nlp_ensemble.py` -- becomes the canonical orchestrator
- File: `backend/app/services/nlp_advanced.py` -- add deprecation warning, delegate to `nlp_ensemble.py`
- Update `backend/app/main.py` prewarm (line 213) to use `nlp_ensemble` instead of `nlp_advanced`

**Step 4: Resolve ClinicalCalculatorService collision** (1 day)
- Rename class in `clinical_calculator_service.py` to `DataDrivenCalculatorService`
- Update all imports (primarily `backend/app/api/calculators.py`)
- File: `backend/app/services/clinical_calculator_service.py` line 2330 -- rename class

**Step 5: Consolidate SemanticSearchService** (1 day)
- File: `backend/app/services/semantic_search.py` -- mark as deprecated, delegate to service
- File: `backend/app/services/semantic_search_service.py` -- becomes canonical
- Update `backend/app/api/semantic_search.py` imports

**Step 6: Lazy-load Scaffold services** (2 days)
- Wrap scaffold router includes in `main.py` (lines 640-720) in conditional blocks:
  ```
  if settings.enable_scaffold_endpoints:
      api_v1_router.include_router(tefca_router)
      api_v1_router.include_router(federated_router)
      ...
  ```
- This reduces startup time and attack surface in production

#### 4. Acceptance Criteria

- [ ] Every service file has `__maturity__` annotation
- [ ] `ENABLE_SCAFFOLD_ENDPOINTS=false` blocks all scaffold API routes (returns 404)
- [ ] Zero `ClinicalCalculatorService` namespace collisions
- [ ] Exactly one NLP orchestrator is canonical (ensemble)
- [ ] Startup time reduced by 30%+ when scaffold services are disabled
- [ ] Service maturity inventory exported to `docs/SERVICE_MATURITY_INVENTORY.md`

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Tier annotation (177 files) | 2 days |
| Maturity gate middleware | 1 day |
| NLP consolidation | 3 days |
| Calculator collision fix | 1 day |
| SemanticSearch consolidation | 1 day |
| Lazy loading scaffold routers | 2 days |
| **Total** | **10 days** |

#### 6. Dependencies

- CTO-5 (API contracts) -- maturity annotations feed into API lifecycle labeling
- VPE-5 (Tech debt quantification) -- this IS the tech debt inventory

---

### CTO-3: NLP Pipeline Regression Testing

**Objective**: Build measurable precision/recall metrics for the NLP ensemble and require regression suite execution on every PR that touches NLP code.

#### 1. Current State

**NLP test files** (11 files, ~370 test functions):
- `backend/tests/test_nlp_service.py` -- 24 tests, basic NLP service tests
- `backend/tests/test_nlp_rule_based.py` -- 21 tests, rule-based extractor
- `backend/tests/test_nlp_advanced.py` -- 47 tests, advanced NLP
- `backend/tests/test_ensemble_nlp.py` -- 30 tests, ensemble
- `backend/tests/test_clinical_ner.py` -- 47 tests, clinical NER
- `backend/tests/test_modernbert_ner.py` -- 21 tests, ModernBERT
- `backend/tests/test_assertion_classifier.py` -- 43 tests, assertion detection
- `backend/tests/test_section_parser.py` -- 32 tests, section parsing
- `backend/tests/test_value_extraction.py` -- 44 tests, value extraction
- `backend/tests/test_relation_extraction.py` -- 36 tests, relation extraction
- `backend/tests/test_enhanced_extraction.py` -- 23 tests, enhanced extraction

**Sample notes**: `backend/tests/sample_notes/` directory exists.

**Ensemble configuration** (`backend/app/services/nlp_ensemble.py`, lines 47-83):
- Rule-based confidence: 0.85, ML NER confidence: 0.80, ModernBERT confidence: 0.88
- Agreement boost: 0.10, Max confidence: 0.99
- Domain preferences: measurements -> value extraction, drugs -> rule_based, conditions -> ml_ner

**Assertion classifier** (`backend/app/services/assertion_classifier.py`): Probabilistic assertion classifier with `classify_assertion` and `ProbabilisticAssertionClassifier`. Tests exist (43 tests) but no golden dataset for measuring precision/recall.

**Missing**: No golden annotated dataset. No precision/recall/F1 metrics computation. No regression gate in CI. Tests are unit tests, not regression benchmarks.

#### 2. Gap Analysis

- No golden dataset of clinician-annotated notes with expected extraction outputs
- No precision/recall/F1 measurement framework
- No per-entity-type metrics (conditions vs medications vs lab values vs procedures)
- No CI gate that blocks merge on NLP regression
- No benchmark tracking over time
- Existing ~370 NLP tests validate code paths but do not measure extraction quality against ground truth

#### 3. Implementation Steps

**Step 1: Create golden dataset** (5 days -- requires clinical input)
- File: `backend/tests/golden_data/` (new directory)
- File: `backend/tests/golden_data/notes/` -- 50 annotated clinical notes minimum
- File: `backend/tests/golden_data/expected_mentions.json` -- expected extractions per note
- Format: `{note_id, mentions: [{text, start, end, entity_type, assertion, omop_concept_id}]}`
- Distribution: 10 discharge summaries, 10 H&P notes, 10 progress notes, 10 radiology reports, 10 pathology reports
- Assertion variety: negated, historical, family history, conditional, uncertain

**Step 2: Build regression measurement framework** (3 days)
- File: `backend/tests/nlp_regression/` (new package)
- File: `backend/tests/nlp_regression/metrics.py` -- compute TP/FP/FN per entity type
- File: `backend/tests/nlp_regression/runner.py` -- run pipeline on golden dataset, output metrics
- File: `backend/tests/nlp_regression/report.py` -- generate comparison report vs baseline
- Metrics: Precision, Recall, F1 per entity type (Condition, Drug, Measurement, Procedure)
- Additional: Assertion accuracy (negation, hypothetical, family history)

**Step 3: Establish baseline** (1 day)
- Run current ensemble on golden dataset
- Record baseline metrics in `backend/tests/nlp_regression/baseline.json`
- Expected baseline (industry benchmarks): Precision 85-92%, Recall 80-88%, F1 82-90%

**Step 4: Add CI regression gate** (1 day)
- File: `.github/workflows/ci.yml` -- add `nlp-regression` job
- Trigger condition: `paths: ['backend/app/services/nlp*.py', 'backend/app/services/assertion_classifier.py', 'backend/app/services/section_parser.py', 'backend/app/services/value_extraction.py', 'backend/app/services/relation_extraction.py']`
- Fail if F1 drops > 2% from baseline
- Upload metrics as CI artifact

**Step 5: Add assertion detection regression suite** (2 days)
- File: `backend/tests/nlp_regression/assertion_test_cases.json` -- 200+ annotated assertion cases
- Categories: negation, hypothetical, family history, conditional, uncertain
- Examples: "Patient denies chest pain" (ABSENT), "Mother had diabetes" (FAMILY), "Consider diabetes if A1c > 6.5" (CONDITIONAL)

#### 4. Acceptance Criteria

- [ ] Golden dataset: 50+ annotated notes with 500+ labeled mentions
- [ ] Regression framework reports per-entity-type precision/recall/F1
- [ ] Baseline metrics recorded and versioned in repository
- [ ] CI blocks merge if F1 drops > 2% on any entity type
- [ ] Assertion detection accuracy > 90% on golden dataset
- [ ] Metrics report generated and archived on every NLP-touching PR

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Golden dataset creation | 5 days (needs clinician) |
| Metrics framework | 3 days |
| Baseline establishment | 1 day |
| CI integration | 1 day |
| Assertion regression suite | 2 days |
| **Total** | **12 days** |

#### 6. Dependencies

- CTO-2 (Service consolidation) -- must know canonical NLP orchestrator before building regression
- External: Requires clinician time for golden dataset annotation

---

### CTO-4: OMOP Mapping Quality

**Objective**: Build a concept coverage dashboard, track unmapped mention rates, alert on vocabulary update breakages.

#### 1. Current State

**Mapping service hierarchy**:
- `backend/app/services/mapping.py` (lines 51-124): `MappingServiceInterface` ABC with `map_mention()` method; `BaseMappingService` concrete implementation
- `backend/app/services/mapping_db.py` (line 17): `DatabaseMappingService(BaseMappingService)` -- database lookups
- `backend/app/services/mapping_sql.py` (line 27): `SQLMappingService(BaseMappingService)` -- raw SQL approach
- `backend/app/services/clinical_ontology_mapper.py` (1,718 lines): Comprehensive mapper with fuzzy matching

**Mapping methods** (`mapping.py`, lines 15-20): `MappingMethod` enum with `EXACT`, `FUZZY`, `ML`.

**ConceptCandidate** (`mapping.py`, lines 24-48): Carries `omop_concept_id`, `concept_name`, `concept_code`, `vocabulary_id`, `domain_id`, `score`, `method`, `rank`.

**Vocabulary service** (`backend/app/services/vocabulary.py`): File-based vocabulary loaded at startup. `preload_vocabulary()` called in `main.py` line 385. Reports `concept_count` and `term_count` at startup.

**Vocabulary enhanced** (`backend/app/services/vocabulary_enhanced.py`, line 162): `EnhancedVocabularyService(VocabularyService)` adds fuzzy matching and stemming.

**Vocabulary versioning**: `backend/app/services/vocabulary_version_service.py` exists. Migration `023_add_vocabulary_versioning.py` adds tables. Currently Scaffold tier.

**Existing test coverage**:
- `backend/tests/test_mapping_service.py` -- 26 tests
- `backend/tests/test_mapping_accuracy.py` -- 26 tests (accuracy tests exist)
- `backend/tests/test_vocabulary_service.py` -- 28 tests
- `backend/tests/test_vocabulary_enhanced.py` -- 33 tests
- `backend/tests/test_vocabulary_db.py` -- 32 tests

#### 2. Gap Analysis

- No runtime dashboard for concept coverage rates
- No tracking of unmapped mention rate (mentions extracted by NLP but not mapped to any OMOP concept)
- `vocabulary_version_service.py` exists as Scaffold but is not wired for regression testing
- No alert mechanism when SNOMED/RxNorm/LOINC updates break existing mappings
- Three mapping implementations with no clear routing or fallback chain documented
- `mapping_accuracy` tests exist but results are not tracked over time
- No OMOP CDM data quality tooling (Achilles/DQD integration)

#### 3. Implementation Steps

**Step 1: Define canonical mapping chain** (1 day)
- File: `backend/app/services/mapping.py` -- document the official fallback order:
  1. Direct concept_id from NLP extraction (bypass mapping, from curated vocabulary)
  2. Exact match via `DatabaseMappingService`
  3. Fuzzy match via `clinical_ontology_mapper.py`
  4. Return unmapped with `concept_id=0`
- File: `backend/app/services/mapping_orchestrator.py` (new) -- single entry point that orchestrates the chain

**Step 2: Add mapping quality metrics collection** (2 days)
- File: `backend/app/services/mapping_quality_metrics.py` (new)
- Track per request: total mentions, mapped count, unmapped count, mapping method distribution, average confidence
- Persist to Redis counter or PostgreSQL metrics table
- Expose via existing metrics endpoint at `backend/app/api/metrics.py`

**Step 3: Build OMOP coverage dashboard API** (2 days)
- File: `backend/app/api/data_quality.py` -- add endpoint `GET /api/v1/quality/omop-coverage`
- Response: `{total_mentions, mapped, unmapped, unmapped_rate, coverage_by_domain, coverage_by_vocabulary, top_unmapped_terms}`
- Additional endpoint: `GET /api/v1/quality/unmapped-terms` -- paginated list of unmapped mention text with frequency

**Step 4: Vocabulary update regression testing** (3 days)
- File: `backend/tests/vocabulary_regression/` (new package)
- File: `backend/tests/vocabulary_regression/baseline_mappings.json` -- 500+ curated term-to-concept pairs
- Test: Load new vocabulary version, re-map all baseline terms, diff against previous
- Report: broken mappings, new mappings, confidence changes
- File: `.github/workflows/ci.yml` -- add vocabulary regression job triggered by changes to `fixtures/` or vocabulary files

**Step 5: Activate vocabulary versioning** (2 days)
- Promote `backend/app/services/vocabulary_version_service.py` from Scaffold to Pilot
- Wire into vocabulary loading in `backend/app/services/vocabulary.py`
- Track which SNOMED CT / RxNorm / LOINC / ICD-10 version is active
- Add API endpoint to query active vocabulary versions

#### 4. Acceptance Criteria

- [ ] Single canonical mapping chain with clear fallback order documented
- [ ] OMOP coverage metrics available via API: total mapped rate, per-domain rates, top unmapped terms
- [ ] 500+ curated baseline mappings for regression testing
- [ ] Vocabulary update regression test runs on every PR touching mapping/vocabulary code
- [ ] Active vocabulary version tracking (SNOMED version, RxNorm version, etc.)
- [ ] Alert when unmapped rate exceeds 20% threshold

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Canonical mapping chain | 1 day |
| Quality metrics collection | 2 days |
| Coverage dashboard API | 2 days |
| Vocabulary regression tests | 3 days |
| Vocabulary versioning activation | 2 days |
| **Total** | **10 days** |

#### 6. Dependencies

- CTO-2 (Service consolidation) -- must know which mapping service is canonical
- CTO-3 (NLP regression) -- unmapped rate depends on NLP extraction quality

---

### CTO-5: API Contract Stability

**Objective**: Version all APIs, enforce backward compatibility, establish deprecation policies, and ensure consistent naming across 726 endpoints.

#### 1. Current State

**API structure**: 95 entries in `backend/app/api/`, including:
- Flat module files (80+): `patients.py`, `coding.py`, `trials.py`, `graph.py`, etc.
- Sub-packages (4): `documents/`, `etl/`, `quality/`, `middleware/`
- `graphql/` (GraphQL schema package)
- `middleware/` (11 middleware files): `audit_middleware.py`, `auth_middleware.py`, `error_handler.py`, `kg_auth_middleware.py`, `kg_error_handler.py`, `kg_versioning.py`, `metrics.py`, `rate_limit.py`, `request_id.py`, `security_headers.py`

**Router registration** (`backend/app/main.py`, lines 590-723): Single `api_v1_router` with prefix `/api/v1`. All 82 routers mounted under v1. No v2 routes. No per-router version or maturity annotation.

**Legacy redirect** (`main.py`, lines 734-743): Redirects `/api/*` to `/api/v1/*` with 308 permanent redirect.

**OpenAPI spec**: Auto-generated at `/api/v1/openapi.json`. Tags defined in `main.py` (lines 497-570) cover 20 categories. Not all routers have tags assigned.

**Naming inconsistencies**:
- REST nouns: `patients.py`, `cohorts.py`, `documents/`
- Action verbs: `coding.py`, `streaming.py`, `reconciliation.py`
- Domain-qualified: `graph_rag.py`, `kg_benchmark.py`, `knowledge_graph_fhir.py`
- Duplicated domains: `auth.py` + `auth_sessions.py`, `quality/` package + `quality_measures.py` flat file

#### 2. Gap Analysis

- No API versioning strategy beyond v1 prefix
- No backward compatibility policy or contract testing
- No deprecation header mechanism (no `Sunset` header per RFC 8594)
- No consistent naming convention across endpoints
- No per-endpoint maturity annotation (Production/Pilot/Scaffold)
- No breaking change detection in CI
- OpenAPI spec is auto-generated, not a design-first contract

#### 3. Implementation Steps

**Step 1: Audit and normalize endpoint naming** (3 days)
- File: `docs/API_NAMING_CONVENTIONS.md` (new) -- define RESTful naming standard
- Audit all 95 API files for naming consistency
- Create mapping of current to normalized endpoint paths
- Add deprecated redirect routes for renamed endpoints
- Convention: `/{resource}` (noun, plural), standard HTTP verbs, no action verbs in URLs

**Step 2: Add per-router maturity tags** (1 day)
- File: each router file -- add `tags=["Production"]` or `tags=["Pilot"]` or `tags=["Scaffold"]` to router constructor
- File: `backend/app/main.py` lines 497-570 -- add maturity tags to OpenAPI tag metadata

**Step 3: Implement deprecation headers** (2 days)
- File: `backend/app/api/middleware/deprecation.py` (new)
- Add `Sunset` header (RFC 8594) and `Deprecation` header to responses from deprecated endpoints
- File: `backend/app/core/config.py` -- add `deprecated_endpoints: dict` mapping endpoint to sunset date
- Return `Warning: 299` header for deprecated endpoints

**Step 4: Add OpenAPI contract testing to CI** (2 days)
- File: `.github/workflows/ci.yml` -- add `api-contract` job
- Snapshot current `openapi.json` in repository: `backend/api-contracts/v1/openapi.json`
- On each PR, generate new OpenAPI spec and diff against snapshot
- Use `oasdiff` tool to detect breaking changes
- Breaking change = fail CI; non-breaking = info annotation

**Step 5: API lifecycle documentation** (1 day)
- File: `docs/API_LIFECYCLE.md` (new)
- Define stages: Alpha (Scaffold) -> Beta (Pilot) -> GA (Production) -> Deprecated -> Removed
- Define timeline: minimum 6 months from deprecation to removal

#### 4. Acceptance Criteria

- [ ] All endpoints follow consistent RESTful naming convention
- [ ] Every router has a maturity tag (Production/Pilot/Scaffold)
- [ ] Deprecated endpoints emit `Sunset` and `Deprecation` headers
- [ ] CI detects breaking API changes and blocks merge
- [ ] OpenAPI contract snapshot versioned in repository
- [ ] API lifecycle policy documented and reviewed

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Naming audit and normalization | 3 days |
| Per-router maturity tags | 1 day |
| Deprecation headers middleware | 2 days |
| Contract testing in CI | 2 days |
| Lifecycle documentation | 1 day |
| **Total** | **9 days** |

#### 6. Dependencies

- CTO-2 (Service consolidation) -- maturity tiers feed into API maturity tags
- VPE-2 (CI/CD maturity) -- contract testing requires CI pipeline

---

### CTO-6: Observability Stack Design

**Objective**: Implement distributed tracing across the full pipeline (webhook -> NLP -> OMOP mapping -> KG build -> trial match) with dashboards and alerting.

#### 1. Current State

**Existing observability infrastructure**:
- `backend/app/api/middleware/metrics.py` -- `MetricsMiddleware` collects request metrics (registered in `main.py` line 604)
- `backend/app/api/middleware/request_id.py` -- `RequestIdMiddleware` adds `X-Request-ID` header (line 597)
- `backend/app/api/middleware/audit_middleware.py` -- HIPAA audit logging (line 599)
- `backend/app/api/health.py` -- health check endpoints (`/health`, `/ready`)
- `backend/app/api/metrics.py` -- Prometheus-compatible metrics endpoint
- `backend/app/services/kg_prometheus_metrics.py` (516 LOC) -- KG-specific Prometheus metrics (Scaffold)
- `backend/app/services/kg_tracing_service.py` (191 LOC) -- KG tracing service (Scaffold)
- `backend/app/services/kg_logging_service.py` -- KG structured logging (Scaffold)
- `backend/app/services/kg_grafana_dashboards.py` -- Grafana dashboard definitions (Scaffold)

**Logging**: Python `logging` module throughout. Some structured logging with `extra={}` dict (e.g., `main.py` lines 359-367, `database.py` line 219). No standardized JSON logging format.

**Tracing gap**: `RequestIdMiddleware` generates trace IDs but these are NOT propagated through background jobs. When a webhook triggers NLP -> mapping -> graph build via RQ, the worker has no knowledge of the originating request ID.

#### 2. Gap Analysis

- No end-to-end distributed tracing (no OpenTelemetry)
- Request IDs not propagated through RQ background jobs
- No structured JSON logging format (required for log aggregation tools)
- KG observability services exist as Scaffold but are not wired to actual infrastructure
- No alerting rules defined anywhere
- No pipeline-stage latency tracking
- No SLI measurement infrastructure
- No Grafana/Prometheus stack configured in docker-compose

#### 3. Implementation Steps

**Step 1: Implement structured JSON logging** (2 days)
- File: `backend/app/core/logging_config.py` (new) -- configure `python-json-logger` or `structlog`
- Format: `{timestamp, level, logger, request_id, user_id, message, extra...}`
- File: `backend/app/main.py` -- configure logging in lifespan startup before line 384
- File: `backend/app/core/config.py` -- add `log_format: str = "json"` setting

**Step 2: Add OpenTelemetry instrumentation** (3 days)
- Add dependencies: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-exporter-otlp`
- File: `backend/app/core/telemetry.py` (new) -- initialize tracer provider and meter provider
- Auto-instrument: FastAPI, SQLAlchemy, Redis, httpx
- Custom spans for pipeline stages:
  - `backend/app/services/nlp_ensemble.py` -- add spans around ensemble extraction
  - `backend/app/services/mapping.py` -- add spans around mapping operations
  - `backend/app/services/fact_builder_db.py` -- add spans around fact persistence
  - `backend/app/services/graph_builder_db.py` -- add spans around graph construction
  - `backend/app/services/trial_eligibility_service.py` -- add spans around screening
- Span attributes: `document_id`, `patient_id`, `mention_count`, `mapping_method`, etc.

**Step 3: Propagate trace context through background jobs** (2 days)
- File: `backend/app/core/queue.py` -- serialize `request_id` and OpenTelemetry trace context into RQ job metadata
- Workers extract and restore trace context from job metadata before execution
- File: `backend/app/core/database.py` -- use `DatabaseRequestContext` (lines 33-55) consistently in all paths

**Step 4: Define SLIs and SLOs** (1 day)
- File: `docs/OBSERVABILITY_SLIs.md` (new)
- SLIs: request latency p50/p95/p99, error rate, NLP throughput, mapping success rate, trial match latency
- SLOs: API latency p99 < 2s, NLP processing < 5s/doc, mapping success rate > 80%, webhook processing < 30s

**Step 5: Create observability docker-compose and dashboards** (2 days)
- File: `docker-compose.observability.yml` (new) -- Jaeger/Tempo + Grafana + Prometheus
- File: `monitoring/grafana/dashboards/pipeline.json` -- pipeline dashboard (ingestion rate, NLP throughput, mapping success rate, graph build time, error rates)
- File: `monitoring/prometheus/alerts.yml` -- alert rules: error rate > 5%, p99 latency > 5s, queue depth > 100

**Step 6: Configure alerting rules** (1 day)
- Alerts: error rate > 5%, p99 latency > 5s, NLP throughput < 1 doc/sec, webhook queue depth > 100, DB connection pool exhaustion (>80% utilized)
- File: `monitoring/prometheus/alerts.yml` (new)
- Integration: Slack/PagerDuty webhook for P1/P2 alerts

#### 4. Acceptance Criteria

- [ ] All log output in JSON format with request_id correlation
- [ ] End-to-end trace visible from webhook receipt through NLP through mapping through graph build
- [ ] Grafana dashboards operational for all pipeline stages
- [ ] Alert fires within 5 minutes of SLO violation
- [ ] Background job traces linked to originating request trace
- [ ] SLI/SLO definitions documented and measured

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Structured JSON logging | 2 days |
| OpenTelemetry instrumentation | 3 days |
| Background job context propagation | 2 days |
| SLI/SLO definition | 1 day |
| Observability stack + dashboards | 2 days |
| Alerting rules | 1 day |
| **Total** | **11 days** |

#### 6. Dependencies

- VPE-4 (SLAs) -- SLIs/SLOs defined here feed into SLA definitions
- VPE-6 (Docker-compose hardening) -- Prometheus/Grafana services in compose
- CTO-1 (Scalability) -- capacity testing requires observability

---

### CTO-7: Developer Experience Improvements

**Objective**: Ensure a new engineer can onboard and ship in week 1 with dev/prod parity and fast feedback loops.

#### 1. Current State

**Makefile** (`Makefile`, 187 lines): Provides targets for `test`, `lint`, `typecheck`, `dev`, `docker-up`, `docker-down`, `docker-dev`, `docker-migrate`. Documentation via `make help`.

**Docker dev mode**: `docker-compose.dev.yml` exists (referenced by `make docker-dev`, Makefile line 172). Base `docker-compose.yml` mounts source code via volumes (lines 141-142: `./backend:/app`).

**Backend dev server**: `make dev-backend` runs `uv run uvicorn app.main:app --reload` (Makefile line 92).

**Startup**: Backend loads vocabulary at boot (`main.py` lines 384-389). Pre-warming skipped (line 393).

**Python version mismatch**: CI uses Python 3.11 (`.github/workflows/ci.yml` line 14: `PYTHON_VERSION: "3.11"`), CLAUDE.md says Python 3.13, Dockerfiles use 3.11.

**No `.env.example`**: Developers must reverse-engineer 30+ configuration variables from `backend/app/core/config.py`.

**No pre-commit hooks**: Linting/formatting issues caught only in CI (slow feedback loop).

**Docker stack overhead**: `docker-compose.yml` starts 7 services (PostgreSQL, Redis, Neo4j, Zookeeper, Kafka, Backend, Worker) even when only PostgreSQL + Redis are needed.

#### 2. Gap Analysis

- Python version inconsistency (3.11 vs 3.13)
- No `.env.example` file
- No pre-commit hooks
- No lightweight dev mode (PostgreSQL + Redis only)
- No data seeding for local development
- No developer onboarding guide beyond CLAUDE.md
- No `make shell` for interactive Python with app context
- Dockerfile base image has `--reload` flag (line 33) -- development artifact in build

#### 3. Implementation Steps

**Step 1: Create `.env.example`** (0.5 day)
- File: `.env.example` (new) -- document all 30+ environment variables from `backend/app/core/config.py`
- Include comments, mark required vs optional, include safe development defaults

**Step 2: Add pre-commit hooks** (0.5 day)
- File: `.pre-commit-config.yaml` (new)
- Hooks: ruff check, ruff format, mypy (backend), eslint (frontend)
- File: `Makefile` -- add `make install-hooks` target

**Step 3: Add lightweight dev mode** (1 day)
- File: `docker-compose.lite.yml` (new) -- only PostgreSQL + Redis (no Kafka, Neo4j, Zookeeper)
- File: `Makefile` -- add `make docker-lite` target
- Documentation: "Use lite mode for API development; full mode for graph/streaming features"

**Step 4: Add data seeding** (1 day)
- A seed script already exists (recent commit `44b6074`: "add demo login flow and comprehensive data seed script")
- Ensure seed is idempotent and referenceable via `make seed`
- File: `Makefile` -- add `make seed` target pointing to existing seed script

**Step 5: Fix Python version consistency** (0.5 day)
- File: `.github/workflows/ci.yml` line 14 -- verify and align with Dockerfiles
- File: `backend/Dockerfile` line 1 -- align base image
- File: `backend/Dockerfile.prod` line 7 -- align base image
- File: `CLAUDE.md` -- correct Python version statement

**Step 6: Add Makefile convenience targets** (0.5 day)
- `make shell` -- Python shell with app context loaded
- `make openapi` -- generate and save OpenAPI spec
- `make db-reset` -- drop and recreate dev database
- `make coverage` -- run tests with HTML coverage report

**Step 7: Developer onboarding guide** (1 day)
- File: `docs/DEVELOPER_ONBOARDING.md` (new)
- Contents: prerequisites, setup steps, architecture pointer to CLAUDE.md, common workflows, debugging tips
- "Day 1 checklist" with specific tasks to verify setup

#### 4. Acceptance Criteria

- [ ] New developer can go from clone to running tests in < 15 minutes
- [ ] `make docker-lite` starts minimal stack in < 30 seconds
- [ ] `make seed` populates development database with realistic sample data
- [ ] Pre-commit hooks catch linting/formatting issues before push
- [ ] Python version consistent across CI, Dockerfile, Dockerfile.prod, CLAUDE.md
- [ ] `.env.example` documents all configuration variables

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| .env.example | 0.5 day |
| Pre-commit hooks | 0.5 day |
| Lightweight dev mode | 1 day |
| Data seeding wiring | 1 day |
| Python version fix | 0.5 day |
| Makefile targets | 0.5 day |
| Onboarding guide | 1 day |
| **Total** | **5 days** |

#### 6. Dependencies

- No hard dependencies on other items
- Should be completed early to accelerate all other work

---

## VP Engineering Items

### VPE-1: Test Coverage for Clinical Paths

**Objective**: Achieve >90% test coverage on NLP extraction, OMOP mapping, trial matching, and FHIR import -- the four critical paths that directly affect patient outcomes and revenue.

#### 1. Current State

**Test inventory**: 159 test files in `backend/tests/` containing approximately 4,261 test functions. Total test code: ~60,713 lines.

**Coverage measurement**: CI runs pytest with `--cov=app --cov-report=xml` (`.github/workflows/ci.yml` lines 124-131). Coverage uploaded to Codecov (line 138). No coverage thresholds enforced -- CI does not fail on coverage drops.

**Critical path coverage gaps**:

| Critical Path | Service File (LOC) | Test File | Test Count | Status |
|---|---|---|---|---|
| Trial eligibility/matching | `trial_eligibility_service.py` (~800) | **NONE** | 0 | NO TESTS |
| Metriport webhooks | `metriport_service.py` (~400) | **NONE** | 0 | NO TESTS |
| FHIR import pipeline | `fhir_import.py` (1,345) | **NONE** | 0 | NO TESTS |
| NLP ensemble | `nlp_ensemble.py` (604) | `test_ensemble_nlp.py` | 30 | Exists |
| OMOP mapping | `mapping.py` + `mapping_db.py` | `test_mapping_service.py` | 26 | Exists |
| Document processing | `documents/` package | `test_api_documents.py` | 22 | Basic |
| Fact builder | `fact_builder_db.py` | `test_fact_builder_db.py` | 19 | Exists |
| Drug safety | `drug_safety.py` (885) | `test_drug_safety.py` | 43 | Good |

**The three most critical paths (trial matching, webhook ingestion, FHIR import) have ZERO tests.** These are the paths that directly affect whether patients get matched to trials.

**Strong coverage areas**: KG services (20+ test files, 500+ tests), clinical calculators (70 tests), drug interactions (40 tests), billing/coding stack (test_billing_optimizer 25, test_cpt_suggester 41, test_icd10_suggester 39, test_hcc_analyzer 39).

#### 2. Gap Analysis

- **CRITICAL**: Zero tests for trial eligibility service, Metriport webhooks, FHIR import
- No `--cov-fail-under` threshold in CI configuration
- No differentiation between unit tests and integration tests
- No end-to-end pipeline tests (document -> NLP -> mapping -> fact -> graph -> trial match)
- Coverage report not correlated to critical paths
- No test for webhook idempotency or pipeline error recovery

#### 3. Implementation Steps

**Step 1: Add trial eligibility tests** (3 days)
- File: `backend/tests/test_trial_eligibility_service.py` (new)
- Test cases:
  - Create trial with inclusion/exclusion criteria
  - Screen patient meeting all criteria (eligible)
  - Screen patient with exclusion criteria triggered (ineligible)
  - Screen patient with missing data (unknown/indeterminate)
  - Enrollment workflow (screen -> enroll -> complete/withdraw)
  - Edge cases: age boundary (exactly 18), date boundary, conflicting data
  - Dashboard analytics endpoints
  - Concurrent screening (thread safety of in-memory storage)
- Target: 40+ tests

**Step 2: Add Metriport webhook tests** (2 days)
- File: `backend/tests/test_metriport_webhook.py` (new)
- Test cases:
  - Valid FHIR bundle processing end-to-end
  - HMAC signature verification (pass and fail)
  - Idempotent re-delivery (same bundle ID twice = no duplicates)
  - Malformed/incomplete bundle rejection with correct HTTP status
  - Partial bundle processing (some resources fail, others succeed)
  - Rate limiting behavior under burst
- Target: 25+ tests

**Step 3: Add FHIR import tests** (2 days)
- File: `backend/tests/test_fhir_import_service.py` (new)
- Test cases:
  - Import Patient resource -> verify patient record created
  - Import Condition resource -> verify clinical fact created
  - Import Observation resource -> verify measurement fact
  - Import MedicationRequest -> verify medication fact
  - Import DocumentReference -> verify NLP pipeline triggered
  - Bundle with internal references (resolve Reference/Patient/123)
  - Graceful degradation on unknown/unsupported resource types
- Target: 30+ tests

**Step 4: Add end-to-end pipeline tests** (3 days)
- File: `backend/tests/test_pipeline_e2e.py` (new)
- Full pipeline test: Document ingestion -> NLP extraction -> OMOP mapping -> Fact building -> Graph construction -> Trial screening
- Use sample clinical note from `backend/tests/sample_notes/`
- Assert: correct mentions extracted, mapped to OMOP concepts, facts created, graph nodes/edges built, trial eligibility determined
- Target: 10 happy-path scenarios + 5 critical failure modes

**Step 5: Enforce coverage thresholds in CI** (0.5 day)
- File: `.github/workflows/ci.yml` line 125 -- add `--cov-fail-under=70` (start at 70%, ratchet up quarterly)
- Consider per-module thresholds for critical paths (90%+ target)

**Step 6: Separate unit and integration test markers** (0.5 day)
- File: `backend/tests/conftest.py` -- add `@pytest.mark.integration` and `@pytest.mark.unit` markers
- File: `backend/pyproject.toml` -- register custom markers
- CI: run unit tests on every PR; integration tests on merge to main

#### 4. Acceptance Criteria

- [ ] Trial eligibility service: 40+ tests, >90% line coverage
- [ ] Metriport webhook: 25+ tests, >85% line coverage
- [ ] FHIR import service: 30+ tests, >85% line coverage
- [ ] End-to-end pipeline: 15+ scenarios covering happy path and failures
- [ ] CI enforces minimum 70% overall coverage (ratchet to 80% in 3 months)
- [ ] Zero critical path services with 0% test coverage

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Trial eligibility tests | 3 days |
| Metriport webhook tests | 2 days |
| FHIR import tests | 2 days |
| E2E pipeline tests | 3 days |
| Coverage enforcement | 0.5 day |
| Test markers | 0.5 day |
| **Total** | **11 days** |

#### 6. Dependencies

- CTO-1 (Scalability) -- trial storage migration may change the service under test
- CTO-3 (NLP regression) -- NLP tests overlap with regression framework
- VPE-2 (CI/CD) -- coverage enforcement is a CI configuration change

---

### VPE-2: CI/CD Maturity

**Objective**: Add SAST (Bandit), dependency scanning (pip-audit, npm audit), container scanning, and secrets scanning to the pipeline. Close remaining security gaps.

#### 1. Current State

**CI workflows** (`.github/workflows/`):

| Workflow | Lines | Purpose | Status |
|---|---|---|---|
| `ci.yml` | 324 | Lint + test + build + security scan + dependency review | Active |
| `deploy.yml` | 326 | Build/push to GHCR + K8s deploy (staging/production) | Active |
| `kg-check.yml` | ~50 | Knowledge graph freshness check | Active |
| `release.yml` | ~100 | Release management | Active |

**What already exists in ci.yml**:
- `backend-lint`: Ruff check + format + mypy (lines 19-66)
- `backend-test`: pytest with coverage, Codecov upload (lines 68-151)
- `frontend-lint`: ESLint + TypeScript type check (lines 153-178)
- `frontend-test`: Jest with coverage (lines 180-211)
- `frontend-build`: Next.js production build (lines 214-237)
- `docker-build`: Build Docker images without push (lines 239-265)
- `security-scan`: Trivy **filesystem** scan, SARIF upload to GitHub Security (lines 268-291)
- `dependency-review`: GitHub dependency review on PRs, blocks GPL/AGPL + HIGH severity (lines 293-304)
- `ci-success`: Gate check requiring all jobs pass (lines 307-323)
- Concurrency control with cancel-in-progress (lines 9-11)

**deploy.yml features**: GHCR container registry, multi-platform builds (amd64 + arm64), K8s rollout with rollback, smoke tests (health check only), Slack notifications.

#### 2. Gap Analysis

| Category | Current State | Target |
|---|---|---|
| SAST | Trivy filesystem only | Trivy + Bandit (Python-specific SAST) |
| Python deps | dependency-review (PRs only) | pip-audit on every push |
| JS deps | None | npm audit on every push |
| Container images | Not scanned | Trivy image scan after Docker build |
| Secrets scanning | None | gitleaks or similar |
| DAST | None | OWASP ZAP baseline on staging deploys |
| Coverage gates | Report only (no threshold) | Fail on < 70% |
| Deploy smoke tests | Health check only (`curl /health`) | Health + API contract + critical path |

#### 3. Implementation Steps

**Step 1: Add Bandit SAST scanning** (0.5 day)
- File: `.github/workflows/ci.yml` -- add `backend-sast` job after `backend-lint`
- Run: `uv run bandit -r app/ -c pyproject.toml --severity-level medium -f sarif -o bandit-report.sarif`
- Upload SARIF to GitHub Security tab
- File: `backend/pyproject.toml` -- add `[tool.bandit]` configuration section

**Step 2: Add pip-audit and npm audit** (0.5 day)
- Backend: add step to `backend-test` job: `uv run pip-audit`
- Frontend: add step to `frontend-lint` job: `npm audit --audit-level=high`

**Step 3: Add container image scanning** (0.5 day)
- File: `.github/workflows/ci.yml` -- modify `docker-build` job to scan images after build:
  ```
  - name: Scan backend image with Trivy
    uses: aquasecurity/trivy-action@master
    with:
      image-ref: clinical-ontology-normalizer/backend:${{ github.sha }}
      format: sarif
      severity: CRITICAL,HIGH
  ```

**Step 4: Add secrets scanning** (0.5 day)
- File: `.github/workflows/ci.yml` -- add `secrets-scan` job:
  ```
  - uses: gitleaks/gitleaks-action@v2
  ```
- File: `.gitleaks.toml` (new) -- configure allowlist for test fixtures and sample data

**Step 5: Add DAST baseline scan on staging** (1 day)
- File: `.github/workflows/deploy.yml` -- add after staging smoke tests:
  ```
  - name: OWASP ZAP Baseline
    uses: zaproxy/action-baseline@v0.12.0
    with:
      target: https://staging-api.clinical-ontology.example.com
  ```
- File: `.zap/rules.tsv` (new) -- configure scan rules and severity thresholds

**Step 6: Enhance staging deploy smoke tests** (1 day)
- File: `.github/workflows/deploy.yml` -- replace simple `curl /health` with:
  - Health check: `/health` AND `/ready`
  - API contract: download OpenAPI spec and validate structure
  - Critical path: POST a test document, verify 200/201 response
  - Rollback automatically if any smoke test fails

#### 4. Acceptance Criteria

- [ ] Bandit SAST runs on every push, results in GitHub Security tab
- [ ] pip-audit checks Python dependencies for known CVEs
- [ ] npm audit checks frontend dependencies for known CVEs
- [ ] Container images scanned by Trivy after Docker build
- [ ] gitleaks secret scanning passes on repository
- [ ] DAST baseline scan runs on staging deployments
- [ ] Staging smoke tests include API contract and critical path verification

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Bandit SAST | 0.5 day |
| pip-audit + npm audit | 0.5 day |
| Container scanning | 0.5 day |
| Secrets scanning | 0.5 day |
| DAST baseline | 1 day |
| Enhanced smoke tests | 1 day |
| **Total** | **4 days** |

#### 6. Dependencies

- No hard dependencies
- VPE-6 (Docker hardening) -- container scanning validates hardened images

---

### VPE-3: Database Migration Safety

**Objective**: Establish zero-downtime migration strategy with rollback plans and schema drift prevention.

#### 1. Current State

**Alembic configuration**:
- `backend/alembic.ini` (5,008 bytes) -- configuration file
- `backend/alembic/env.py` (87 lines) -- async migration runner using `async_engine_from_config`, imports `Base` from `app.core.database` and all models via `from app.models import *`
- `backend/alembic/versions/` -- 33 migration files numbered 001-036 (with gaps at 007-010)

**Migration numbering collision**: Two migrations share number 016:
- `016_create_calculator_tables.py`
- `016_create_rbac_tables.py`
This is a branch collision in Alembic's revision chain that could cause unpredictable migration ordering.

**Migration execution**: docker-compose has a dedicated `migrations` service (`docker-compose.yml`, lines 176-189) running `uv run alembic upgrade head` with `profiles: [migrate]` (must be explicitly triggered).

**Database init bypass**: `backend/app/core/database.py` lines 228-234: `init_db()` calls `Base.metadata.create_all` when `settings.debug` is True. This bypasses Alembic and creates tables directly from ORM models, creating schema drift between Alembic state and actual database.

**Production deployment**: `deploy.yml` lines 138-140 runs migration job before deployment with 300s timeout. No pre-migration backup automation (line 209-212 has a rudimentary `pg_dump` but no S3 upload or verification).

**Soft delete**: `SoftDeleteMixin` in `database.py` (lines 143-194) adds `deleted_at`/`deleted_by` columns. Migration `029_add_soft_delete_and_composite_indexes.py` covers this. The hardening plan mentions a past `deleted_at` column incident as a symptom of schema drift.

#### 2. Gap Analysis

- Duplicate migration number 016 (calculator tables vs RBAC tables) -- potential branch collision
- `init_db()` with `create_all` in debug mode creates schema drift
- No rollback migration testing (`downgrade()` functions never exercised in CI)
- No migration linting (no check for destructive operations like DROP TABLE)
- No pre-deployment database backup automation with verification
- No schema diff check between ORM models and Alembic head
- No concurrent migration protection beyond Alembic default
- Production migration timeout (300s) with no retry or alerting on failure

#### 3. Implementation Steps

**Step 1: Fix migration 016 collision** (0.5 day)
- File: `backend/alembic/versions/016_create_rbac_tables.py` -- renumber to 016b or adjust `down_revision`
- Run `alembic heads` to verify single head after fix
- Run `alembic check` to validate revision graph integrity

**Step 2: Remove `create_all` from application startup** (0.5 day)
- File: `backend/app/main.py` lines 375-381 -- replace `init_db()` call with Alembic version check:
  ```
  # In production/staging: verify migration state instead of create_all
  if not settings.debug:
      # Log current alembic revision for observability
      pass
  ```
- File: `backend/app/core/database.py` lines 228-234 -- gate `init_db()` behind `TESTING` env var only
- For tests: use `conftest.py` with `create_all` for test database setup

**Step 3: Add migration linting to CI** (1 day)
- File: `backend/scripts/check_migration_safety.py` (new)
- Rules to enforce:
  - No `DROP TABLE` without explicit approval comment
  - No `ALTER COLUMN TYPE` without data migration step
  - All migrations must have `downgrade()` implementation (not just `pass`)
  - `CREATE INDEX` should use `CONCURRENTLY` for large tables
- File: `.github/workflows/ci.yml` -- add `migration-lint` step

**Step 4: Add migration rollback testing** (1 day)
- File: `.github/workflows/ci.yml` -- add to `backend-test` job (with PG service already available):
  ```
  - name: Test migration cycle
    run: |
      uv run alembic upgrade head
      uv run alembic downgrade base
      uv run alembic upgrade head
  ```
- Verifies: every migration can upgrade and downgrade cleanly

**Step 5: Add pre-deployment backup with verification** (1 day)
- File: `.github/workflows/deploy.yml` -- enhance backup step (around line 209):
  - Backup to S3/GCS with timestamp and deployment version tag
  - Verify backup integrity: `pg_restore --list backup.sql`
  - Set backup retention policy (30 days)
  - Abort deployment if backup fails

**Step 6: Add schema drift detection** (1 day)
- File: `backend/scripts/check_schema_drift.py` (new)
- Compare ORM model definitions against latest Alembic migration
- Detect: columns in models not in migrations, type mismatches, missing indexes
- File: `.github/workflows/ci.yml` -- add drift check step, fail if drift detected

#### 4. Acceptance Criteria

- [ ] `alembic heads` returns exactly one head (no branches)
- [ ] `create_all` never runs in non-test environments
- [ ] Every migration has a working `downgrade()` function (verified in CI)
- [ ] CI blocks migrations with destructive operations without approval
- [ ] Pre-deployment backup verified before every production migration
- [ ] Schema drift detection passes in CI
- [ ] Migration up/down/up cycle succeeds for all 33 migrations

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Fix 016 collision | 0.5 day |
| Remove create_all | 0.5 day |
| Migration linting | 1 day |
| Rollback testing | 1 day |
| Pre-deployment backup | 1 day |
| Schema drift detection | 1 day |
| **Total** | **5 days** |

#### 6. Dependencies

- CTO-1 (Scalability) -- trial table migration is first test case for new process
- VPE-2 (CI/CD) -- migration checks are CI pipeline additions

---

### VPE-4: Service Reliability SLAs

**Objective**: Define and measure 99.9%+ uptime for critical paths with incident response targets.

#### 1. Current State

**Health checks**:
- `main.py` lines 746-758: `/health` returns `{status: "healthy"}` -- liveness probe (no dependency checks)
- `main.py` lines 760-783: `/ready` returns vocabulary stats and prewarm status -- readiness probe
- `docker-compose.yml` backend healthcheck (lines 144-149): `curl -f http://localhost:8000/health` every 30s
- `Dockerfile.prod` healthcheck (line 63): Same curl-based check

**Rate limiting**: `RateLimitMiddleware` (main.py line 606). nginx rate limiting at 10r/s for API, 30r/s for general (nginx.conf lines 43-44).

**Circuit breaker**: `backend/app/services/circuit_breaker.py` exists with 40 tests. Retry handler at `retry_handler.py` with 40 tests. Both exist as reusable services but unclear which external calls use them.

**No SLA definitions exist anywhere.** No SLI measurement. No error budget tracking. No incident runbooks.

#### 2. Gap Analysis

- No formal SLA definitions for any service or endpoint group
- No SLI measurement infrastructure (requires CTO-6 observability first)
- No error budget tracking
- No incident response runbooks
- `/health` endpoint too simple -- does not verify database or Redis connectivity
- No synthetic monitoring (external health checks)
- Circuit breaker exists but unclear which services actually use it
- No chaos engineering or failure injection testing framework

#### 3. Implementation Steps

**Step 1: Define SLA tiers** (1 day)
- File: `docs/SERVICE_LEVEL_AGREEMENTS.md` (new)
- Tier 1 (99.9% -- 8.76h downtime/year): Webhook ingestion, trial matching API, FHIR resource API
- Tier 2 (99.5% -- 43.8h downtime/year): NLP processing, OMOP mapping, knowledge graph queries
- Tier 3 (99.0% -- 87.6h downtime/year): Reporting, exports, dashboard analytics, admin endpoints
- Per-tier targets: availability, latency (p50/p95/p99), error rate

**Step 2: Enhance health checks** (1 day)
- File: `backend/app/api/health.py` -- add deep health check endpoint:
  - PostgreSQL: execute `SELECT 1` with timeout
  - Redis: execute `PING` with timeout
  - Neo4j: execute `RETURN 1` (if configured, graceful degradation if not)
  - RQ: check queue lengths and stuck job count
- Add `GET /api/v1/health/deep` with per-dependency status
- Keep `/health` lightweight for K8s liveness probes (no external calls)

**Step 3: Implement SLI collection** (2 days)
- File: `backend/app/api/middleware/sli_collector.py` (new)
- Collect per request: latency, status code, endpoint path, SLA tier
- Aggregate: availability (non-5xx / total), latency percentiles, error rate
- Expose via Prometheus metrics endpoint with labels: `{tier, endpoint_group, method}`

**Step 4: Wire circuit breaker to external dependencies** (1 day)
- Apply circuit breaker pattern to: Neo4j queries, Metriport API calls, LLM API calls
- File: `backend/app/services/graph_database_service.py` -- wrap Neo4j operations
- File: `backend/app/services/metriport_service.py` -- wrap external API calls
- File: `backend/app/services/nlp_claude_api.py` -- wrap LLM API calls
- Circuit breaker config: 5 failures opens circuit, 30s recovery window, half-open after 15s

**Step 5: Create incident response runbooks** (2 days)
- File: `docs/runbooks/` (new directory)
- `docs/runbooks/webhook_pipeline_stall.md` -- symptoms, diagnosis, remediation
- `docs/runbooks/nlp_degradation.md` -- extraction quality drop detection and response
- `docs/runbooks/database_connection_exhaustion.md` -- pool saturation handling
- `docs/runbooks/trial_matching_latency.md` -- screening performance degradation
- `docs/runbooks/fhir_import_failure.md` -- webhook processing errors
- Each runbook: symptoms, impact assessment, investigation commands, resolution steps, escalation path, post-incident checklist

**Step 6: Add error budget tracking** (1 day)
- File: `backend/app/services/error_budget_service.py` (new)
- Calculate: remaining error budget per SLA tier per rolling 30-day window
- Alert thresholds: 50% consumed (warning), 75% consumed (critical), 100% consumed (freeze non-critical deploys)

#### 4. Acceptance Criteria

- [ ] SLA definitions documented for all three tiers with measurable targets
- [ ] Deep health check verifies PostgreSQL, Redis, and Neo4j connectivity
- [ ] SLIs measured and exposed via Prometheus-compatible metrics
- [ ] Circuit breakers active on all external dependency calls
- [ ] 5 incident response runbooks documented with codebase-specific commands
- [ ] Error budget tracked with alerting at consumption thresholds

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| SLA definitions | 1 day |
| Enhanced health checks | 1 day |
| SLI collection | 2 days |
| Circuit breaker wiring | 1 day |
| Incident runbooks | 2 days |
| Error budget tracking | 1 day |
| **Total** | **8 days** |

#### 6. Dependencies

- CTO-6 (Observability) -- SLI collection requires metrics/tracing infrastructure
- CTO-1 (Scalability) -- capacity limits inform SLA targets

---

### VPE-5: Technical Debt Quantification

**Objective**: Inventory all technical debt with risk scores, effort estimates, and a sprint-ready paydown plan.

#### 1. Current State

From codebase analysis, the following debt items have been identified:

**Category 1: Namespace Collisions and Duplicates**
1. Two classes named `ClinicalCalculatorService` in `clinical_calculators.py` (line 3967) and `clinical_calculator_service.py` (line 2330)
2. Two classes named `SemanticSearchService` in `semantic_search.py` (line 37) and `semantic_search_service.py` (line 328)
3. Two NLP orchestrators: `nlp_advanced.py` (`AdvancedNLPService`) and `nlp_ensemble.py` (`EnsembleNLPService`)
4. Two medication reconciliation services: `medication_reconciliation.py` (1,517 LOC) and `med_reconciliation_service.py` (86 LOC)

**Category 2: Schema and Data Integrity**
5. Duplicate Alembic migration number 016 (calculator tables vs RBAC tables)
6. `init_db()` with `create_all` bypasses Alembic in debug mode (`database.py` line 228-234)
7. Trial eligibility uses in-memory storage (`trial_eligibility_service.py` line 51) -- data loss on restart

**Category 3: Build and Infrastructure**
8. Scaffold services loaded at startup consuming memory (82 router includes, `main.py` lines 640-720)
9. Kafka deployed in docker-compose but no consumers wired in application
10. 4 of 6 RQ queues have no consumer (`queue.py` lines 144-152 vs worker command)
11. nginx CORS wildcard `*` in `nginx.conf` line 113
12. Python version inconsistency: CI 3.11, CLAUDE.md says 3.13
13. `Dockerfile` line 33 has `--reload` flag (development artifact)
14. `Dockerfile.prod` line 23 uses `requirements.txt` but project uses `uv`/`pyproject.toml`/`uv.lock`

**Category 4: Test and Quality Gaps**
15. Zero tests for 3 critical path services (trial eligibility, Metriport webhooks, FHIR import)
16. No coverage enforcement threshold in CI

**Total service files**: 177. Estimated tier distribution: ~50 Production, ~70 Pilot, ~57 Scaffold.

#### 2. Gap Analysis

- No formal debt tracking system or registry
- No cost estimation per debt item
- No risk scoring methodology
- No debt budget (% of sprint capacity allocated to paydown)
- Architecture rationalization plan exists in `docs/ARCHITECTURE_RATIONALIZATION_PLAN.md` but no tracking of remediation progress

#### 3. Implementation Steps

**Step 1: Create debt registry** (1 day)
- File: `docs/TECHNICAL_DEBT_REGISTRY.md` (new)
- Per item: ID, title, description, risk level (Critical/High/Medium/Low), effort estimate, files affected, proposed resolution, owner, target date
- Populate with all 16 items above plus any discovered during maturity annotation

**Step 2: Risk-score all debt items** (1 day)
- Score dimensions (1-5 each):
  - **Blast radius**: How many services/users affected if it causes a problem?
  - **Probability**: How likely to cause a problem in the next 90 days?
  - **Recovery time**: How long to fix if it triggers?
- Priority = Blast radius x Probability x Recovery time
- Rank all items by priority score

**Step 3: Create paydown plan** (1 day)
- File: `docs/TECHNICAL_DEBT_PAYDOWN.md` (new)
- Allocate 20% of sprint capacity to debt paydown
- Sprint 1 (Critical): Fix namespace collisions (#1, #2), fix migration 016 (#5), remove create_all (#6)
- Sprint 2 (High): NLP consolidation (#3), trial storage migration (#7), Dockerfile fixes (#13, #14)
- Sprint 3 (Medium): CORS fix (#11), Kafka wiring (#9), queue consumers (#10)
- Sprint 4+: Scaffold gating (#8), version consistency (#12), test gaps (#15, #16)

**Step 4: Add complexity metrics to CI** (0.5 day)
- File: `.github/workflows/ci.yml` -- add `radon` cyclomatic complexity check
- Track: files exceeding complexity threshold (CC > 15), trend over time
- File: `backend/pyproject.toml` -- add radon configuration

**Step 5: Establish debt budget policy** (0.5 day)
- File: `docs/ENGINEERING_POLICIES.md` (new or append)
- Policy: 20% of each sprint allocated to technical debt
- Policy: No new Scaffold services without CTO approval
- Policy: Every new service file must have `__maturity__` annotation
- Policy: PRs that increase total complexity must include offsetting debt paydown

#### 4. Acceptance Criteria

- [ ] All 16+ known debt items documented with risk scores and effort estimates
- [ ] Paydown plan for next 4 sprints with specific file changes listed
- [ ] Cyclomatic complexity measured and tracked in CI
- [ ] Debt budget policy documented and reviewed by engineering leadership
- [ ] Top 5 critical debt items have assigned owners and target dates

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| Debt registry | 1 day |
| Risk scoring | 1 day |
| Paydown plan | 1 day |
| Complexity metrics | 0.5 day |
| Budget policy | 0.5 day |
| **Total** | **4 days** |

#### 6. Dependencies

- CTO-2 (Service consolidation) -- maturity tier annotations feed into debt registry
- VPE-1 (Test coverage) -- coverage gaps are debt items

---

### VPE-6: Production Docker-Compose Hardening

**Objective**: Harden `docker-compose.prod.yml` to eliminate all dev defaults, exposed ports, volume mounts, and security gaps.

#### 1. Current State

**docker-compose.yml** (base, 221 lines) -- security issues:
- Hardcoded PostgreSQL credentials: `postgres/postgres` (lines 13-14)
- Hardcoded Neo4j credentials: `neo4j/password` (line 49)
- Database ports exposed to host: PostgreSQL 15432 (line 16), Redis 16379 (line 33), Neo4j 7474+7687 (lines 52-53), Kafka 9092+29092 (lines 100-101)
- Source code mounted as volume: `./backend:/app` (line 141)
- `AUTH_BYPASS_DEV: true` (line 126), `AUTH_ENABLED: false` (line 127), `DEBUG: true` (line 125)

**docker-compose.prod.yml** (267 lines -- overlay) -- good patterns:
- `${POSTGRES_PASSWORD:?required}` (line 27) -- enforces env var
- `AUTH_ENABLED: "true"` (line 168), `DEBUG: "false"` (line 167)
- `volumes: []` (lines 172, 202, 228) -- removes source mounts
- Resource limits for all services
- Logging with max-size/max-file
- 2 replicas for backend, worker, frontend
- nginx reverse proxy with SSL placeholder

**Remaining issues in docker-compose.prod.yml**:
- `AUTH_BYPASS_DEV` not explicitly overridden to `"false"` (inherited from base)
- No Docker network isolation (all services on default network)
- No read-only filesystem, no capability drops (`security_opt`, `cap_drop`)
- Database ports still exposed (inherited from base compose port mappings)
- No PgBouncer connection pooler
- `Dockerfile.prod` (line 23) uses `requirements.txt` but project uses `uv`

**Dockerfile** (base, 33 lines):
- Line 33: `CMD` includes `--reload` flag -- development flag in production-capable image
- Uses `python:3.11-slim` without digest pinning

**Dockerfile.prod** (70 lines):
- Multi-stage build (good), non-root user (good), HEALTHCHECK (good)
- Uses `requirements.txt` (line 23) instead of `uv sync` -- inconsistent with dev workflow
- No read-only filesystem directive

**nginx.conf** (167 lines):
- Line 113: `add_header 'Access-Control-Allow-Origin' '*' always;` -- wildcard CORS
- Lines 59-80: SSL/TLS configuration commented out
- No HSTS header, no Content-Security-Policy

#### 2. Gap Analysis

| Issue | Severity | Location |
|---|---|---|
| Wildcard CORS in nginx | Critical | `nginx/nginx.conf` line 113 |
| `--reload` in base Dockerfile | High | `backend/Dockerfile` line 33 |
| TLS commented out | Critical | `nginx/nginx.conf` lines 69-80 |
| No Docker network isolation | High | `docker-compose.prod.yml` -- missing |
| No capability drops | Medium | `docker-compose.prod.yml` -- missing |
| `requirements.txt` vs `uv` inconsistency | Medium | `backend/Dockerfile.prod` line 23 |
| No HSTS header | High | `nginx/nginx.conf` -- missing |
| AUTH_BYPASS_DEV not overridden | High | `docker-compose.prod.yml` -- missing |
| DB ports exposed in base | Medium | `docker-compose.yml` lines 16, 33, 52-53 |
| No image digest pinning | Medium | All Dockerfiles |

#### 3. Implementation Steps

**Step 1: Fix CORS wildcard in nginx** (0.5 day)
- File: `nginx/nginx.conf` line 113 -- replace `'*'` with `$cors_origin` variable using `map` block
- Add HSTS header: `add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;`

**Step 2: Enable TLS in nginx** (0.5 day)
- File: `nginx/nginx.conf` lines 59-80 -- uncomment HTTPS configuration
- Add HTTP-to-HTTPS redirect (uncomment lines 60-64)
- Document cert generation/renewal process in `docs/TLS_SETUP.md`

**Step 3: Add Docker network isolation** (1 day)
- File: `docker-compose.prod.yml` -- define isolated networks:
  ```
  networks:
    frontend-net: {}
    backend-net: {}
    data-net: {}
    queue-net: {}
  ```
- Assign services: nginx -> frontend-net, frontend -> frontend-net + backend-net, backend -> backend-net + data-net + queue-net, PostgreSQL/Neo4j -> data-net, Redis/Kafka -> queue-net

**Step 4: Add container hardening** (1 day)
- File: `docker-compose.prod.yml` -- add to all services:
  ```
  security_opt: [no-new-privileges:true]
  cap_drop: [ALL]
  read_only: true
  tmpfs: [/tmp]
  ```
- Add `cap_add: [NET_BIND_SERVICE]` only for nginx
- Verify application works with read-only root filesystem (add tmpfs for Python `__pycache__`)

**Step 5: Fix Dockerfile inconsistencies** (1 day)
- File: `backend/Dockerfile` line 33 -- remove `--reload` flag
- File: `backend/Dockerfile.prod` lines 22-24 -- replace `requirements.txt` with `uv`:
  ```
  COPY pyproject.toml uv.lock ./
  RUN pip install uv && uv sync --frozen --no-dev
  ```
- Pin base images to specific digests for reproducibility

**Step 6: Override all dev defaults** (0.5 day)
- File: `docker-compose.prod.yml` -- explicitly set:
  ```
  backend:
    environment:
      AUTH_BYPASS_DEV: "false"
  ```
- Override all database port mappings: `ports: []` for postgres, redis, neo4j, kafka
- Verify no dev credentials leak through base compose overlay

**Step 7: Add PgBouncer** (0.5 day)
- File: `docker-compose.prod.yml` -- add PgBouncer service in `data-net` + `backend-net`
- Configure: transaction pooling mode, 200 max client connections, 40 default pool size
- Route backend `DATABASE_URL` through PgBouncer instead of direct PostgreSQL

#### 4. Acceptance Criteria

- [ ] No wildcard CORS -- explicit origin allowlist in nginx
- [ ] TLS enabled with correct certificate configuration documented
- [ ] Network isolation: frontend cannot directly reach databases
- [ ] All containers run as non-root with dropped capabilities
- [ ] No `--reload` flag in any Dockerfile
- [ ] `AUTH_BYPASS_DEV=false` explicitly set in production compose
- [ ] Database ports not exposed to host in production
- [ ] PgBouncer connection pooling active
- [ ] Consistent `uv` usage across all Dockerfiles
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` validates cleanly

#### 5. Effort Estimate

| Step | Effort |
|---|---|
| CORS fix + HSTS | 0.5 day |
| TLS enablement | 0.5 day |
| Network isolation | 1 day |
| Container hardening | 1 day |
| Dockerfile fixes | 1 day |
| Dev defaults override | 0.5 day |
| PgBouncer | 0.5 day |
| **Total** | **5 days** |

#### 6. Dependencies

- CTO-1 (Scalability) -- PgBouncer addition overlaps
- VPE-2 (CI/CD) -- container scanning validates hardened images

---

## Dependency Graph

```
CTO-7 (Dev Experience) ---- no dependencies, do first
    |
    v
CTO-2 (Service Consolidation) ---> CTO-5 (API Contracts)
    |                                       |
    |                                       v
    |                              VPE-2 (CI/CD Maturity)
    |
    +---> CTO-3 (NLP Regression)
    |
    +---> VPE-5 (Tech Debt Quantification)
    |
    v
CTO-4 (OMOP Quality)

CTO-6 (Observability) ---> VPE-4 (SLAs)

CTO-1 (Scalability) depends on: CTO-6, VPE-3, VPE-6

VPE-1 (Test Coverage) -- mostly independent
VPE-3 (Migration Safety) -- mostly independent
VPE-6 (Docker Hardening) -- mostly independent
```

---

## Sequencing and Timeline

### Phase 1: Foundation (Weeks 1-2) -- 14 days effort

| Item | Effort | Rationale |
|---|---|---|
| CTO-7: Developer Experience | 5 days | Accelerates all subsequent work |
| VPE-6: Docker-Compose Hardening | 5 days | Security fundamentals, blocks production risk |
| VPE-3: Database Migration Safety | 5 days | Prevents schema drift, unblocks safe migrations |

### Phase 2: Quality and Testing (Weeks 3-5) -- 25 days effort

| Item | Effort | Rationale |
|---|---|---|
| VPE-1: Test Coverage (critical paths) | 11 days | Zero test coverage on 3 critical patient-facing services |
| CTO-2: Service Variant Consolidation | 10 days | Reduce codebase complexity before building more |
| VPE-2: CI/CD Maturity | 4 days | Security scanning gates |

### Phase 3: Pipeline and Data Quality (Weeks 6-8) -- 21 days effort

| Item | Effort | Rationale |
|---|---|---|
| CTO-3: NLP Regression Testing | 12 days | Requires clinical input for golden dataset |
| CTO-5: API Contract Stability | 9 days | Depends on maturity tiers from CTO-2 |

### Phase 4: Scale and Operations (Weeks 9-11) -- 29 days effort

| Item | Effort | Rationale |
|---|---|---|
| CTO-1: Architecture Scalability | 12 days | Informed by observability and testing |
| CTO-6: Observability Stack | 11 days | Enables SLA measurement |
| CTO-4: OMOP Mapping Quality | 10 days | Depends on canonical mapping chain from CTO-2 |

### Phase 5: Operationalize (Weeks 12-13) -- 12 days effort

| Item | Effort | Rationale |
|---|---|---|
| VPE-4: Service Reliability SLAs | 8 days | Requires observability infrastructure from CTO-6 |
| VPE-5: Tech Debt Quantification | 4 days | Final prioritization with full inventory |

### Total Effort Summary

| Role | Items | Total Effort |
|---|---|---|
| CTO | 7 items | 69 days |
| VP Engineering | 6 items | 37 days |
| **Combined** | **13 items** | **106 days** |

With 2 senior engineers dedicated full-time, the complete plan executes in approximately **13-14 weeks** (one quarter). Critical security items (VPE-6, VPE-2) and developer experience (CTO-7) are front-loaded. Revenue-critical items (trial matching tests, NLP quality) are in Phase 2-3. Operational maturity (SLAs, observability) follows in Phase 4-5.

**Key risk**: CTO-3 (NLP Regression) requires clinician time for golden dataset creation. Begin recruiting clinical annotators during Phase 1 to avoid blocking Phase 3.

---

*Plan generated from codebase analysis on 2026-02-08. All file paths are absolute from repository root at `/Users/alexstinard/projects/brainstorm/jan-14-2026/`.*
