# Technical Debt Registry

**Last Updated**: 2026-02-08
**Scan Method**: Manual code review + automated scanner (`backend/app/services/tech_debt_scanner.py`)
**Scope**: Full codebase (backend 345K LOC, frontend 123K LOC)

---

## Summary

| Metric | Value |
|--------|-------|
| Total debt items | 28 |
| Critical | 2 |
| High | 7 |
| Medium | 11 |
| Low | 8 |
| Estimated total effort | ~98 days |

---

## Registry

### TD-001: Calculator Definitions God File (12,713 lines)

| Field | Value |
|-------|-------|
| **ID** | TD-001 |
| **Category** | architecture |
| **Severity** | high |
| **Affected files** | `backend/app/services/calculator_definitions.py` (12,713 lines) |
| **Description** | Single file contains all clinical calculator definitions in a monolithic data structure. At 12,713 lines it is the largest file in the codebase by a factor of 3x over the next largest. Difficult to review, test, and maintain. Adding a new calculator requires modifying a single massive file. |
| **Risk if not addressed** | Merge conflicts when multiple developers add calculators, difficulty reasoning about individual calculator logic, IDE performance degradation |
| **Estimated effort** | 5 days |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Q2 2026 |

---

### TD-002: Duplicate Migration Sequence Number (016)

| Field | Value |
|-------|-------|
| **ID** | TD-002 |
| **Category** | operations |
| **Severity** | critical |
| **Affected files** | `backend/alembic/versions/016_create_calculator_tables.py`, `backend/alembic/versions/016_create_rbac_tables.py` |
| **Description** | Two migration files share the same sequence number `016`. This creates an ambiguous migration order -- the RBAC and calculator table migrations could execute in either order depending on filesystem sort. Alembic uses its own revision chain but the filename conflict suggests the migrations were added outside the normal workflow. |
| **Risk if not addressed** | Fresh database provisioning may fail or produce schema differences depending on execution order; confusing migration history for developers |
| **Estimated effort** | 0.5 days |
| **Business impact** | Clinical safety (inconsistent database state), compliance (audit trail gaps) |
| **Recommended timeline** | Immediate |

---

### TD-003: Migration Sequence Gap (007-010 missing)

| Field | Value |
|-------|-------|
| **ID** | TD-003 |
| **Category** | operations |
| **Severity** | medium |
| **Affected files** | `backend/alembic/versions/` |
| **Description** | Migration numbering jumps from `006_add_job_id_columns.py` to `011_advanced_kg_properties.py`. The gap (007-010) suggests migrations were created and then deleted, or developed on branches that were abandoned. While Alembic uses its own revision chain and not file numbering, the gap creates confusion about the migration history and may indicate lost schema changes. |
| **Risk if not addressed** | Developer confusion about schema evolution history, potential for re-introducing conflicting migrations in the gap range |
| **Estimated effort** | 0.5 days |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Q2 2026 |

---

### TD-004: PostgreSQL Version Mismatch Between Dev and Prod

| Field | Value |
|-------|-------|
| **ID** | TD-004 |
| **Category** | operations |
| **Severity** | high |
| **Affected files** | `docker-compose.yml` (postgres:16-alpine), `docker-compose.prod.yml` (postgres:15) |
| **Description** | Development uses PostgreSQL 16 while production is pinned to PostgreSQL 15. This creates a risk of using PG16-specific features in development that silently fail or behave differently in production. |
| **Risk if not addressed** | SQL syntax/feature incompatibility between environments, potential data corruption from version-specific behavior differences |
| **Estimated effort** | 1 day |
| **Business impact** | Clinical safety (production behavior divergence), performance |
| **Recommended timeline** | Immediate |

---

### TD-005: Redis Password Missing in Production Docker Compose

| Field | Value |
|-------|-------|
| **ID** | TD-005 |
| **Category** | security |
| **Severity** | critical |
| **Affected files** | `docker-compose.prod.yml` |
| **Description** | The production Redis configuration does not set `--requirepass` in the command and does not reference `REDIS_PASSWORD` anywhere. The base `docker-compose.yml` properly requires `REDIS_PASSWORD` for the Redis `--requirepass` flag, but the production override does not propagate this. Any service or container on the queue network can access Redis without authentication. |
| **Risk if not addressed** | Unauthorized access to Redis cache containing clinical session data, potential data exfiltration or cache poisoning |
| **Estimated effort** | 0.5 days |
| **Business impact** | Clinical safety, compliance (HIPAA), security |
| **Recommended timeline** | Immediate |

---

### TD-006: NLP Service Proliferation (10 Files)

| Field | Value |
|-------|-------|
| **ID** | TD-006 |
| **Category** | architecture |
| **Severity** | high |
| **Affected files** | `backend/app/services/nlp.py`, `nlp_advanced.py`, `nlp_claude_api.py`, `nlp_clinical_ner.py`, `nlp_coverage.py`, `nlp_ensemble.py`, `nlp_entity_service.py`, `nlp_modernbert_ner.py`, `nlp_rule_based.py`, `nlp_vocabulary.py` + `nlp_entity/` subpackage (7 files) |
| **Description** | NLP functionality is spread across 10 top-level service files plus a 7-file subpackage. This indicates organic growth without a clear architectural boundary. Multiple files implement overlapping entity extraction logic (rule-based, ML, transformer, ensemble). The CLAUDE.md notes this as a known issue under "Phase 2: Canonicalize NLP/calculator/graph service variants". |
| **Risk if not addressed** | Inconsistent NLP results depending on which service is called, difficulty maintaining extraction quality across variants, duplicated bug fixes |
| **Estimated effort** | 10 days |
| **Business impact** | Clinical safety (inconsistent entity extraction), developer velocity |
| **Recommended timeline** | Q2 2026 |

---

### TD-007: Mock Implementations in Production Services

| Field | Value |
|-------|-------|
| **ID** | TD-007 |
| **Category** | code_quality |
| **Severity** | high |
| **Affected files** | `backend/app/services/cohort_service.py` (lines 1157-1340), `backend/app/services/streaming_etl_service.py` (lines 738-767), `backend/app/services/job_queue_service.py` (lines 173-248) |
| **Description** | Multiple production service files contain mock/fake implementations that generate random data instead of querying real data sources. The cohort service returns random patient counts and mock demographic breakdowns. The streaming ETL service returns mock processing results. The job queue service initializes with fabricated mock workers and jobs. These are labeled as mock implementations in their docstrings. |
| **Risk if not addressed** | Users may receive fabricated clinical data presented as real results, clinical decisions based on random numbers, compliance violations for data integrity |
| **Estimated effort** | 8 days |
| **Business impact** | Clinical safety (fake data presented as real), compliance |
| **Recommended timeline** | Q1 2026 (overdue) |

---

### TD-008: Circuit Breaker Mock (Empty Implementation)

| Field | Value |
|-------|-------|
| **ID** | TD-008 |
| **Category** | architecture |
| **Severity** | medium |
| **Affected files** | `backend/app/services/circuit_breaker_mock.py` |
| **Description** | The circuit breaker pattern is implemented as a completely empty mock class (just `pass`). Any code importing CircuitBreaker gets a no-op that provides no fault tolerance. This suggests the circuit breaker pattern was planned but never implemented. |
| **Risk if not addressed** | Cascading failures when downstream services are unavailable, no fault isolation between service boundaries |
| **Estimated effort** | 3 days |
| **Business impact** | Performance, clinical safety (system availability) |
| **Recommended timeline** | Q2 2026 |

---

### TD-009: Silent Exception Swallowing (50+ Locations)

| Field | Value |
|-------|-------|
| **ID** | TD-009 |
| **Category** | code_quality |
| **Severity** | high |
| **Affected files** | `backend/app/services/calculator_kg_integration.py`, `backend/app/services/kg_logging_service.py`, `backend/app/services/nlp_clinical_ner.py`, `backend/app/services/batch_processor.py`, `backend/app/services/drug_interactions.py`, `backend/app/services/coding_assistant_service.py`, `backend/app/services/impact_analysis_service.py`, and 20+ more files |
| **Description** | Over 50 locations in the codebase use `except Exception:` followed by `pass` or no logging. These silently swallow errors making debugging extremely difficult. In a clinical system, silently dropped exceptions can hide data corruption or processing failures. |
| **Risk if not addressed** | Hidden data processing failures, clinical facts computed from incomplete data, impossible-to-debug production issues |
| **Estimated effort** | 5 days |
| **Business impact** | Clinical safety (silent failures), developer velocity |
| **Recommended timeline** | Q1 2026 (overdue) |

---

### TD-010: Disabled Fuzzy Matching in Concept Lookup

| Field | Value |
|-------|-------|
| **ID** | TD-010 |
| **Category** | code_quality |
| **Severity** | medium |
| **Affected files** | `backend/app/services/concept_lookup.py` (line 90) |
| **Description** | Fuzzy concept matching is disabled with a TODO comment: "Enable pg_trgm extension in PostgreSQL to re-enable fuzzy matching". The commented-out code prevents the concept lookup service from finding approximate matches, reducing mapping coverage for clinical terms with minor spelling variations. |
| **Risk if not addressed** | Reduced concept mapping coverage, clinical entities with minor spelling variations go unmapped, lower overall NLP recall |
| **Estimated effort** | 2 days |
| **Business impact** | Clinical safety (missed mappings), performance |
| **Recommended timeline** | Q2 2026 |

---

### TD-011: Missing Calculator Input Validation

| Field | Value |
|-------|-------|
| **ID** | TD-011 |
| **Category** | code_quality |
| **Severity** | medium |
| **Affected files** | `backend/app/services/kg_calculator_mapper.py` (line 258) |
| **Description** | The calculator-to-KG mapper has a TODO for implementing required parameter detection: `missing = []  # TODO: Implement based on calculator requirements`. This means calculators can be executed with incomplete inputs without any warning, potentially producing incorrect clinical risk scores. |
| **Risk if not addressed** | Clinical calculators run with missing inputs producing incorrect risk scores, no feedback to users about incomplete data |
| **Estimated effort** | 3 days |
| **Business impact** | Clinical safety (incorrect risk calculations) |
| **Recommended timeline** | Q1 2026 (overdue) |

---

### TD-012: Worker Container Missing Health Check

| Field | Value |
|-------|-------|
| **ID** | TD-012 |
| **Category** | operations |
| **Severity** | medium |
| **Affected files** | `docker-compose.yml` (worker service, lines 167-193) |
| **Description** | The RQ worker container has no healthcheck defined. If the worker process crashes or deadlocks, Docker will not detect the failure and will not restart the container despite `restart: unless-stopped`. Other services (postgres, redis, neo4j, kafka, backend) all have proper healthchecks. |
| **Risk if not addressed** | Background document processing silently stops, clinical data pipeline stalls without alerting |
| **Estimated effort** | 0.5 days |
| **Business impact** | Performance, clinical safety (processing delays) |
| **Recommended timeline** | Q1 2026 |

---

### TD-013: Frontend Container Missing Health Check

| Field | Value |
|-------|-------|
| **ID** | TD-013 |
| **Category** | operations |
| **Severity** | low |
| **Affected files** | `docker-compose.yml` (frontend service, lines 212-228) |
| **Description** | The frontend container has no healthcheck. If the Next.js process crashes, Docker cannot detect the failure for orchestration. |
| **Risk if not addressed** | Frontend becomes unavailable without automated detection/restart |
| **Estimated effort** | 0.5 days |
| **Business impact** | Performance |
| **Recommended timeline** | Q2 2026 |

---

### TD-014: Mapping Service Proliferation (3 Variants)

| Field | Value |
|-------|-------|
| **ID** | TD-014 |
| **Category** | architecture |
| **Severity** | medium |
| **Affected files** | `backend/app/services/mapping.py`, `backend/app/services/mapping_db.py`, `backend/app/services/mapping_sql.py` |
| **Description** | Three separate mapping service files implement concept mapping with overlapping responsibilities. `mapping.py` uses in-memory lookups, `mapping_db.py` uses database queries, and `mapping_sql.py` provides raw SQL-based mapping. The relationship between these is unclear and callers must decide which to use. |
| **Risk if not addressed** | Inconsistent mapping results depending on which service is used, duplicated maintenance effort |
| **Estimated effort** | 4 days |
| **Business impact** | Clinical safety (mapping inconsistency), developer velocity |
| **Recommended timeline** | Q2 2026 |

---

### TD-015: Graph Builder Service Duplication

| Field | Value |
|-------|-------|
| **ID** | TD-015 |
| **Category** | architecture |
| **Severity** | medium |
| **Affected files** | `backend/app/services/graph_builder.py`, `backend/app/services/graph_builder_db.py` |
| **Description** | Two graph builder service files exist: one builds knowledge graphs in memory, the other persists to the database. The split is reasonable for separation of concerns but creates duplicated logic for node/edge construction. |
| **Risk if not addressed** | Divergent graph construction logic between in-memory and persisted paths |
| **Estimated effort** | 3 days |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Q3 2026 |

---

### TD-016: Fact Builder Service Duplication

| Field | Value |
|-------|-------|
| **ID** | TD-016 |
| **Category** | architecture |
| **Severity** | medium |
| **Affected files** | `backend/app/services/fact_builder.py`, `backend/app/services/fact_builder_db.py` |
| **Description** | Same pattern as TD-015: two fact builder implementations with overlapping logic for constructing clinical facts from mentions. |
| **Risk if not addressed** | Inconsistent clinical fact construction between code paths |
| **Estimated effort** | 3 days |
| **Business impact** | Clinical safety (fact inconsistency), developer velocity |
| **Recommended timeline** | Q3 2026 |

---

### TD-017: Guideline Generation Script Proliferation (11 Scripts)

| Field | Value |
|-------|-------|
| **ID** | TD-017 |
| **Category** | code_quality |
| **Severity** | low |
| **Affected files** | `backend/scripts/generate_guidelines.py`, `generate_guidelines_batch2.py` through `generate_guidelines_batch12.py`, `generate_guidelines_bulk.py` |
| **Description** | Eleven separate guideline generation scripts exist in the scripts directory. These appear to be incremental batch scripts created over time rather than parameterized versions of a single script. |
| **Risk if not addressed** | Script maintenance burden, confusion about which script to run, duplicated script logic |
| **Estimated effort** | 2 days |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Q3 2026 |

---

### TD-018: Test Files in Scripts Directory

| Field | Value |
|-------|-------|
| **ID** | TD-018 |
| **Category** | testing |
| **Severity** | low |
| **Affected files** | `backend/scripts/test_hybrid_analyzer.py`, `backend/scripts/test_ontology_kg_integration.py`, `backend/scripts/test_pipeline_e2e.py` |
| **Description** | Three test files are located in the `scripts/` directory rather than the `tests/` directory. These are not discoverable by pytest's standard test collection and likely are not run in CI. |
| **Risk if not addressed** | Tests are never run in CI, regressions go undetected |
| **Estimated effort** | 0.5 days |
| **Business impact** | Developer velocity, clinical safety (untested code paths) |
| **Recommended timeline** | Q1 2026 |

---

### TD-019: ETL Orchestrator Excessive Exception Handling (1,829 lines)

| Field | Value |
|-------|-------|
| **ID** | TD-019 |
| **Category** | code_quality |
| **Severity** | medium |
| **Affected files** | `backend/app/services/etl_orchestrator.py` (1,829 lines, 17 `except Exception` blocks) |
| **Description** | The ETL orchestrator contains 17 broad exception handlers across its 1,829 lines. Many of these catch `Exception` generically and log the error but continue processing, which can lead to partial ETL runs where some phases succeed and others silently fail. The file also exceeds reasonable size for a single service module. |
| **Risk if not addressed** | Partial ETL pipeline execution producing incomplete datasets, difficulty diagnosing pipeline failures |
| **Estimated effort** | 4 days |
| **Business impact** | Clinical safety (incomplete data processing), developer velocity |
| **Recommended timeline** | Q2 2026 |

---

### TD-020: Frontend ESLint Suppressions

| Field | Value |
|-------|-------|
| **ID** | TD-020 |
| **Category** | code_quality |
| **Severity** | low |
| **Affected files** | `frontend/src/components/KnowledgeGraph/GraphCanvas.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/policies/page.tsx`, `frontend/src/app/clinical/stats/page.tsx`, `frontend/src/app/clinical/intelligence/page.tsx` |
| **Description** | Five eslint-disable comments suppress React hooks exhaustive-deps warnings. These typically indicate stale closures or missing effect dependencies that can cause subtle UI bugs. |
| **Risk if not addressed** | Stale data in React components, subtle rendering bugs, effects not re-running when dependencies change |
| **Estimated effort** | 2 days |
| **Business impact** | Developer velocity, performance |
| **Recommended timeline** | Q3 2026 |

---

### TD-021: Frontend TypeScript `any` Usage (33 Occurrences)

| Field | Value |
|-------|-------|
| **ID** | TD-021 |
| **Category** | code_quality |
| **Severity** | low |
| **Affected files** | 14 files across `frontend/src/`, notably `frontend/src/app/clinical/calculators/[calculatorId]/page.tsx` (10 occurrences), `frontend/src/hooks/use-permissions.tsx` (6 occurrences) |
| **Description** | 33 uses of the `any` type across 14 frontend files bypass TypeScript's type checking. The calculator page has the highest density with 10 `any` usages. |
| **Risk if not addressed** | Type errors caught at runtime instead of compile time, reduced IDE support for refactoring |
| **Estimated effort** | 2 days |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Q3 2026 |

---

### TD-022: Clinical Agent API File Size (3,039 lines)

| Field | Value |
|-------|-------|
| **ID** | TD-022 |
| **Category** | architecture |
| **Severity** | medium |
| **Affected files** | `backend/app/api/clinical_agent.py` (3,039 lines) |
| **Description** | The clinical agent API file is the largest API route file at 3,039 lines. It combines graph query building, LLM interaction, response formatting, and hardcoded treatment mappings in a single route handler module. The file contains a conditional branch for hardcoded vs OMOP-based treatment mappings (lines 1461-1465) that should be handled at the service layer. |
| **Risk if not addressed** | Difficult to test individual capabilities, merge conflicts, tight coupling between query building and response formatting |
| **Estimated effort** | 5 days |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Q2 2026 |

---

### TD-023: Calculator Service Proliferation (6 Files)

| Field | Value |
|-------|-------|
| **ID** | TD-023 |
| **Category** | architecture |
| **Severity** | medium |
| **Affected files** | `backend/app/services/calculator_builder.py`, `calculator_definitions.py`, `calculator_kg_integration.py`, `calculator_reasoning_service.py`, `clinical_calculator_service.py`, `clinical_calculators.py` |
| **Description** | Six calculator-related service files with overlapping responsibilities. The relationship between `clinical_calculators.py` (4,181 lines) and `clinical_calculator_service.py` (3,034 lines) is unclear -- both appear to implement calculator execution. The CLAUDE.md notes this as a known issue under "Phase 2: Canonicalize NLP/calculator/graph service variants". |
| **Risk if not addressed** | Inconsistent calculator results depending on entry point, duplicated validation logic |
| **Estimated effort** | 6 days |
| **Business impact** | Clinical safety (calculator inconsistency), developer velocity |
| **Recommended timeline** | Q2 2026 |

---

### TD-024: Backend Source Volume Mount in Development

| Field | Value |
|-------|-------|
| **ID** | TD-024 |
| **Category** | security |
| **Severity** | low |
| **Affected files** | `docker-compose.yml` (line 153: `./backend:/app`) |
| **Description** | The base docker-compose.yml mounts the entire `./backend` directory into the container as `/app`. This includes `.env` files, scripts, tests, and configuration that should not be accessible in the container. The production override correctly sets `volumes: []` but the base configuration exposes more than necessary. |
| **Risk if not addressed** | Accidental exposure of secrets or configuration files if base compose is used without production override |
| **Estimated effort** | 0.5 days |
| **Business impact** | Security |
| **Recommended timeline** | Q2 2026 |

---

### TD-025: Large API Route Files (7 files > 1,000 lines)

| Field | Value |
|-------|-------|
| **ID** | TD-025 |
| **Category** | architecture |
| **Severity** | low |
| **Affected files** | `backend/app/api/clinical_agent.py` (3,039), `nlp.py` (1,976), `graph.py` (1,947), `reconciliation.py` (1,428), `notes.py` (1,345), `coding.py` (1,343), `calculators.py` (1,328) |
| **Description** | Seven API route files exceed 1,000 lines each. Route files should primarily handle HTTP concerns (request parsing, response formatting, auth) and delegate to services. Large route files indicate business logic leaking into the API layer. |
| **Risk if not addressed** | Tight coupling between HTTP handling and business logic, difficulty testing business rules in isolation |
| **Estimated effort** | 8 days |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Q3 2026 |

---

### TD-026: Large Service Files (20+ files > 1,000 lines)

| Field | Value |
|-------|-------|
| **ID** | TD-026 |
| **Category** | architecture |
| **Severity** | medium |
| **Affected files** | `backend/app/services/calculator_definitions.py` (12,713), `clinical_calculators.py` (4,181), `clinical_calculator_service.py` (3,034), `cpt_suggester.py` (2,329), `note_generator.py` (2,324), `quality_measures.py` (2,223), `etl_orchestrator.py` (1,829), plus 13 more files between 1,000-1,800 lines |
| **Description** | Over 20 service files exceed 1,000 lines. The services layer contains approximately 153K total lines of code across 183 files, averaging ~837 lines per file. This indicates many services are doing too much and should be decomposed. |
| **Risk if not addressed** | Cognitive overload for developers, increased time to understand and modify services, higher defect rates in large files |
| **Estimated effort** | 15 days (incremental) |
| **Business impact** | Developer velocity |
| **Recommended timeline** | Ongoing (Q2-Q4 2026) |

---

### TD-027: Kafka Single-Broker Configuration in Production

| Field | Value |
|-------|-------|
| **ID** | TD-027 |
| **Category** | operations |
| **Severity** | high |
| **Affected files** | `docker-compose.prod.yml` (lines 128-144) |
| **Description** | Production Kafka is configured with `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1` and `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1`, indicating a single-broker setup with no replication. If the Kafka broker fails, all streaming ETL data in transit is lost. The offset topic having replication factor 1 means consumer group offsets are also not replicated. |
| **Risk if not addressed** | Data loss during broker failures, inability to resume streaming processing after Kafka restart |
| **Estimated effort** | 3 days |
| **Business impact** | Clinical safety (data loss), performance |
| **Recommended timeline** | Q1 2026 |

---

### TD-028: Frontend NLP Page Size (2,866 lines)

| Field | Value |
|-------|-------|
| **ID** | TD-028 |
| **Category** | code_quality |
| **Severity** | low |
| **Affected files** | `frontend/src/app/nlp/page.tsx` (2,866 lines) |
| **Description** | The NLP page component is 2,866 lines, making it the largest frontend component. This single-file component likely combines state management, data fetching, rendering logic, and UI sub-components. React best practices recommend splitting into smaller, focused components. |
| **Risk if not addressed** | Difficult to maintain, slow rendering due to unnecessary re-renders, hard to test individual UI behaviors |
| **Estimated effort** | 3 days |
| **Business impact** | Developer velocity, performance |
| **Recommended timeline** | Q3 2026 |

---

## Debt by Timeline

### Immediate (Critical/Overdue)

| ID | Title | Severity | Effort |
|----|-------|----------|--------|
| TD-002 | Duplicate Migration Sequence Number | critical | 0.5d |
| TD-004 | PostgreSQL Version Mismatch | high | 1d |
| TD-005 | Redis Password Missing in Prod | critical | 0.5d |

### Q1 2026 (Overdue)

| ID | Title | Severity | Effort |
|----|-------|----------|--------|
| TD-007 | Mock Implementations in Production Services | high | 8d |
| TD-009 | Silent Exception Swallowing | high | 5d |
| TD-011 | Missing Calculator Input Validation | medium | 3d |
| TD-012 | Worker Container Missing Health Check | medium | 0.5d |
| TD-018 | Test Files in Scripts Directory | low | 0.5d |
| TD-027 | Kafka Single-Broker in Prod | high | 3d |

### Q2 2026

| ID | Title | Severity | Effort |
|----|-------|----------|--------|
| TD-001 | Calculator Definitions God File | high | 5d |
| TD-003 | Migration Sequence Gap | medium | 0.5d |
| TD-006 | NLP Service Proliferation | high | 10d |
| TD-008 | Circuit Breaker Mock | medium | 3d |
| TD-010 | Disabled Fuzzy Matching | medium | 2d |
| TD-014 | Mapping Service Proliferation | medium | 4d |
| TD-019 | ETL Orchestrator Size | medium | 4d |
| TD-022 | Clinical Agent API Size | medium | 5d |
| TD-023 | Calculator Service Proliferation | medium | 6d |
| TD-024 | Backend Volume Mount | low | 0.5d |

### Q3 2026

| ID | Title | Severity | Effort |
|----|-------|----------|--------|
| TD-015 | Graph Builder Duplication | medium | 3d |
| TD-016 | Fact Builder Duplication | medium | 3d |
| TD-017 | Guideline Script Proliferation | low | 2d |
| TD-020 | Frontend ESLint Suppressions | low | 2d |
| TD-021 | Frontend TypeScript `any` Usage | low | 2d |
| TD-025 | Large API Route Files | low | 8d |
| TD-026 | Large Service Files | medium | 15d |
| TD-028 | Frontend NLP Page Size | low | 3d |

---

## Automated Scanning

Run the automated debt scanner to track metrics over time:

```bash
# Full markdown report
cd backend && python -m scripts.tech_debt_report

# Summary for terminal
cd backend && python -m scripts.tech_debt_report --format summary

# JSON for CI integration
cd backend && python -m scripts.tech_debt_report --format json --output debt_report.json

# CI gate: fail if debt score exceeds threshold
cd backend && python -m scripts.tech_debt_report --fail-above 500
```

The automated scanner detects:
- TODO/FIXME/HACK/XXX/NOQA marker comments
- Functions exceeding 50 lines
- Files exceeding 500 lines
- Bare `except:` clauses
- Silent `except Exception:` with only `pass`
- Magic number literals
- Potentially unused imports

---

## Changelog

| Date | Change |
|------|--------|
| 2026-02-08 | Initial registry created with 28 items from manual review and automated scan |
