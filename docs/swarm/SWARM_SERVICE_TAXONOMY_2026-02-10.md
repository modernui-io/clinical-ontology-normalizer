# Service Taxonomy Audit (2026-02-10)

## Purpose
Classify service-layer implementation patterns to identify consolidation and refactor leverage.

## Sources
- Service tree: `backend/app/services`
- Raw artifacts:
  - `docs/swarm/data/service_taxonomy_2026-02-10.json`
  - `docs/swarm/data/service_taxonomy_2026-02-10.tsv`

## Method
Static classification of each service file (`343` total) using import and code markers:
- `db_backed`: SQLAlchemy/session/query markers.
- `external_integration`: external connector/import markers (`httpx`, `openai`, `redis`, connectors, etc.).
- `db_plus_external`: both patterns in same file.
- `in_memory_or_fixture`: explicit in-memory state or fixture/file-loading markers.
- `logic_or_orchestration`: neither DB nor external/in-memory markers dominant.

## Topline Results
- Service files: `343`
- Service LOC: `303,578`

By file count:
- `db_backed`: `166`
- `in_memory_or_fixture`: `123`
- `logic_or_orchestration`: `33`
- `db_plus_external`: `12`
- `external_integration`: `9`

By top-100 largest service files:
- `db_backed`: `69`
- `in_memory_or_fixture`: `23`
- `logic_or_orchestration`: `4`
- `db_plus_external`: `3`
- `external_integration`: `1`

Interpretation:
- The largest service modules skew heavily DB-backed, not connector-heavy.
- In-memory/fixture patterns are still substantial and likely a major standardization target.

## Largest Service Files (Top 20)
| LOC | Classification | File |
|---:|---|---|
| 12713 | logic_or_orchestration | `backend/app/services/calculator_definitions.py` |
| 4181 | db_backed | `backend/app/services/clinical_calculators.py` |
| 3034 | logic_or_orchestration | `backend/app/services/clinical_calculator_service.py` |
| 2329 | db_backed | `backend/app/services/cpt_suggester.py` |
| 2324 | db_backed | `backend/app/services/note_generator.py` |
| 2223 | in_memory_or_fixture | `backend/app/services/quality_measures.py` |
| 2178 | db_backed | `backend/app/services/value_set_service.py` |
| 1875 | in_memory_or_fixture | `backend/app/services/nlp_entity/nlp_entity_extractors.py` |
| 1863 | db_backed | `backend/app/services/trial_eligibility_service.py` |
| 1829 | db_plus_external | `backend/app/services/etl_orchestrator.py` |
| 1754 | in_memory_or_fixture | `backend/app/services/fhir_terminology.py` |
| 1718 | db_backed | `backend/app/services/clinical_ontology_mapper.py` |
| 1686 | db_plus_external | `backend/app/services/fhir_import.py` |
| 1646 | external_integration | `backend/app/services/notification_service.py` |
| 1638 | db_backed | `backend/app/services/x12_service.py` |
| 1620 | db_backed | `backend/app/services/iac_service.py` |
| 1607 | in_memory_or_fixture | `backend/app/services/synthetic_data_service.py` |
| 1604 | in_memory_or_fixture | `backend/app/services/ai_coding_service.py` |
| 1602 | db_backed | `backend/app/services/federated_learning_service.py` |
| 1581 | db_backed | `backend/app/services/contract_lifecycle_service.py` |

## Structural Signals
- Files with `get_*service` factory pattern: `246/343`
- Files with `reset_*service` pattern: `191/343`
- Files with explicit `threading.Lock` pattern: `200/343`

Interpretation:
- Service lifecycle/singleton patterns are widespread and mostly manual.
- This is a candidate for framework-level standardization (factory/registry abstraction).

## Refactor Targets (High Leverage)
1. Standardize DB service base patterns (session lifecycle, pagination, error mapping).
2. Consolidate repeated singleton factory boilerplate (`get_*service`, lock, reset).
3. Isolate fixture/in-memory seeded service families behind clear adapter interfaces.
4. Split very large service files (>1.5k LOC) by bounded behavior slices.

## Caveats
- Classification is static and heuristic; treat as triage, not ground truth.
- Some files are mixed-mode and may shift class after deeper line-by-line review.
