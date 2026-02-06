# Capability Inventory (No-Delete Baseline)

Generated: 2026-02-06

Scope: repository-grounded capability inventory for understanding what exists now without deleting modules.

Method:
- Static scan of `backend/app/api`, `backend/app/services`, `backend/tests`
- Signal extraction for `mock|simulated|placeholder|not implemented`
- Manual domain curation for maturity and external dependency mapping

## Snapshot

| Metric | Value |
|---|---|
| Backend Python lines | 344,709 |
| Frontend TS/TSX lines | 123,180 |
| API router files | 111 |
| Routers mounted in `main.py` | 81 |
| Endpoint decorators (`@router.*`) | 726 |
| Service files (`backend/app/services`) | 187 |
| Model files (`backend/app/models`) | 19 |
| Alembic migrations | 34 |
| Backend test files | 156 |
| Backend test functions | 4,261 |

## Maturity Rubric

| Label | Definition |
|---|---|
| `production` | Core logic implemented and test-covered; no mock/simulated path in primary happy path. |
| `pilot` | Real implementation exists but mixed with fallbacks/mock mode, partial integration, or reliability caveats. |
| `scaffold` | Contract-first module exists (routes/models/workflows), but behavior is mostly simulated/placeholder until external systems are connected. |

## Capability Matrix

| Capability | Key Modules | Maturity | Evidence | Dependency to make fully real |
|---|---|---|---|---|
| Document ingestion + processing jobs | `backend/app/api/documents/*`, `backend/app/services/extraction_pipeline.py`, `backend/app/services/batch_processor.py` | `production` | Broad API + service coverage and dedicated tests (`test_api_documents.py`, `test_documents.py`, `test_jobs.py`) | None beyond current Postgres/Redis deployment |
| Rule-based NLP extraction (deterministic) | `backend/app/services/nlp_rule_based.py`, `assertion_classifier.py`, `section_parser.py`, `value_extraction.py`, `relation_extraction.py` | `production` | Strong dedicated tests (`test_nlp_rule_based.py`, `test_assertion_classifier.py`, `test_section_parser.py`, `test_value_extraction.py`, `test_relation_extraction.py`) | None |
| Transformer/ensemble NLP path | `backend/app/services/nlp_clinical_ner.py`, `nlp_modernbert_ner.py`, `nlp_ensemble.py`, `nlp_advanced.py` | `pilot` | Implemented and tested, but model/runtime readiness varies by local model assets and infra | Stable model serving/runtime, GPU where needed, model artifact lifecycle |
| Terminology + OMOP mapping | `backend/app/services/vocabulary*.py`, `mapping*.py`, `api/vocabulary_mapping.py` | `production` | Multiple services and tests (`test_mapping_service.py`, `test_mapping_accuracy.py`, `test_vocabulary*.py`) | Full OMOP vocab load and DB tuning in target env |
| Clinical fact construction | `backend/app/services/fact_builder.py`, `fact_builder_db.py` | `production` | Dedicated tests (`test_fact_builder.py`, `test_fact_builder_db.py`, `test_fact_builder_service.py`) | None |
| Knowledge graph build/materialization | `backend/app/services/graph_builder.py`, `graph_builder_db.py`, `api/clinical_agent.py` | `pilot` | Core works and tested, but some paths degrade gracefully and can hide partial failures | Enforced degradation flags, strict error policy, Neo4j SLOs |
| Graph query layer | `backend/app/api/graph.py`, `services/graph_database_service.py`, `services/graph_analytics_service.py` | `pilot` | Explicit mock-mode fallback in graph DB service/API | Highly available Neo4j cluster and fail-closed policy for critical endpoints |
| GraphRAG + multi-hop reasoning | `backend/app/api/graph_rag.py`, `services/graph_augmented_rag.py` | `pilot` | Placeholder comments and mock-mode response paths present | Production semantic retrieval backend + strict fallback signaling |
| Clinical agent orchestration | `backend/app/api/clinical_agent.py`, `services/multi_agent_orchestrator.py`, `services/clinical_intelligence_agent.py` | `pilot` | Rich capability surface, but reliability risks from broad exception handling in critical flows | Error budget + observable degraded mode + function decomposition |
| Guideline retrieval/RAG | `backend/app/api/guidelines.py`, `services/guideline_rag_service.py` | `pilot` | Implemented and used; quality sensitive to corpus availability and hierarchy connectivity | Managed guideline corpus updates + Neo4j hierarchy availability |
| Drug safety + interactions | `backend/app/api/drug_safety.py`, `services/drug_safety.py`, `services/drug_interactions.py` | `production` | Strong service and API tests (`test_drug_safety.py`, `test_drug_interactions.py`) | Ongoing dataset updates |
| Differential diagnosis | `backend/app/api/differential_diagnosis.py`, `services/differential_diagnosis.py` | `production` | Dedicated tests and active endpoint surface (`test_differential_diagnosis.py`) | Continuous medical knowledge refresh |
| Clinical calculators | `backend/app/api/calculators.py`, `services/clinical_calculators.py`, `services/calculator_builder.py` | `production` | Dedicated test coverage (`test_calculators.py`, `test_clinical_calculators.py`) | Governance for formula changes and references |
| OMOP concept hierarchy | `services/omop_hierarchy_service.py` | `pilot` | Real Cypher queries against Neo4j IS_A/SUBSUMES relationships; in-memory caching; falls back to string/substring matching when Neo4j unavailable. Used by guideline RAG and calculator-KG integration for semantic condition matching | Neo4j loaded with full OMOP vocabulary (5.65M concepts); stable graph DB connectivity SLOs |
| Clinical narrative extraction | `services/narrative_extractor.py` | `pilot` | LLM-based extraction of admission reason, hospital course, and discharge plan; grounded in pre-extracted entities to prevent hallucination; supports Ollama (prefers medical models like BioMistral/MedGemma) and Claude API; structured dataclasses with temporal event ordering | Reliable LLM service (Ollama with GPU or Claude API key); model artifact availability |
| Calculator-KG integration | `services/calculator_kg_integration.py`, `services/kg_calculator_mapper.py` | `pilot` | Neo4j-dependent behavior; warnings/fallback when graph unavailable; uses OMOP hierarchy for semantic criteria matching | Consistent Neo4j + typed mapping contracts + OMOP hierarchy service availability |
| Billing optimization stack | `services/icd10_suggester.py`, `cpt_suggester.py`, `hcc_analyzer.py`, `billing_optimizer.py`, `coding_query_generator.py` | `production` | Broad tests (`test_icd10_suggester.py`, `test_cpt_suggester.py`, `test_hcc_analyzer.py`, `test_billing_optimizer.py`) | Updated coding datasets/rules over time |
| AI auto-coding endpoint set | `api/ai_coding.py`, `services/ai_coding_service.py` | `pilot` | Fully wired API but TF-IDF heuristic approach and limited dedicated tests | Higher-fidelity coding engine + dedicated API/service tests |
| Coding assistant chat | `api/coding_assistant.py`, `services/coding_assistant_service.py` | `pilot` | Explicit mock fallback when LLM processing fails | Reliable LLM provider + fallback transparency to caller |
| FHIR import/export + terminology | `api/fhir.py`, `api/terminology.py`, `services/fhir_import.py`, `fhir_exporter.py`, `fhir_terminology.py` | `pilot` | Strong implementation surface; some bulk export paths include mock generation services | Real FHIR server integration testing + conformance suite in CI |
| SMART on FHIR | `api/smart.py`, `api/smart_server.py`, `services/smart_fhir.py`, `services/smart_auth_server.py` | `pilot` | Full endpoint surface exists; production value depends on external EHR trust/config | Real EHR registration, OAuth client onboarding, launch validation |
| CDS Hooks | `api/cds_hooks.py`, `services/cds_hooks_service.py` | `pilot` | Implemented service, but hook-specific gaps and mock prefetch noted | Real EHR hook traffic + production hook logic per hook type |
| TEFCA exchange | `api/tefca.py`, `services/tefca_service.py` | `scaffold` | Mock QHIN initialization and simulated document exchange paths | Real QHIN connectivity, trust framework onboarding, production endpoints |
| Federated learning | `api/federated.py`, `services/federated_learning_service.py` | `scaffold` | Simulated rounds/mock organization data in service | Multi-party infra, secure aggregation, org onboarding |
| Streaming/Kafka ingestion | `api/streaming.py`, `services/kafka_service.py`, `streaming_etl_service.py`, `kg_kafka_streaming_service.py` | `pilot` | Service supports real Kafka but explicitly runs mock mode when unavailable | Stable Kafka cluster + schema governance + replay/backpressure operations |
| Bulk data export | `services/bulk_export_service.py`, FHIR bulk endpoints in `api/fhir.py` | `scaffold` | Mock FHIR resource generation paths in export service | Real source-of-truth resource extraction pipeline |
| Data quality + cohorts + quality measures | `api/data_quality.py`, `api/cohorts.py`, `api/quality_measures.py`, related services | `pilot` | Real APIs exist; some mock implementations in cohort and quality paths | Replace simulated analytics paths with DB-backed computations |
| Model registry + ML model services | `api/model_registry.py`, `services/model_registry_service.py`, `services/ml_model_service.py` | `scaffold` | Mock model creation/performance metrics in ML model service | Real model artifact store, training registry, deployment hooks |
| LLM fine-tuning pipeline | `api/llm_finetuning.py`, `services/llm_finetuning_service.py` | `scaffold` | Simulated dataset statistics/training flow | Real training infra, experiment tracking, GPU jobs |
| Voice transcription | `api/voice.py`, `services/voice_transcription_service.py` | `scaffold` | Simulated transcription behavior in service | Real ASR backend (Whisper or equivalent), media pipeline |
| X12 claims/EDI | `api/x12.py`, `services/x12_service.py`, `services/x12_mapper.py` | `pilot` | Parser/mapping exists but integration depth is partial | Clearinghouse connectivity, transaction validation loops |
| CDISC/SDTM tooling | `api/cdisc.py`, `services/cdisc_terminology_service.py`, `sdtm_*` services | `pilot` | Strong terminology surface; some SDTM areas still placeholder-level operations | Study-grade validation workflow + external CT updates |
| Auth, RBAC, audit, security middleware | `api/auth.py`, `api/users.py`, `services/rbac_service.py`, `services/audit_service.py`, middleware stack | `pilot` | Security stack exists and tested; environment setup determines completeness | Hardened identity provider integration + tenant ops playbooks |
| Notifications + webhooks | `api/notifications.py`, `services/notification_service.py`, `services/kg_webhook_service.py` | `pilot` | Functional framework present; production behavior depends on channel integrations | Real SMTP/SMS/webhook infra and delivery observability |

## Keep-vs-Delete Guidance

This inventory is explicitly non-destructive.

Recommended handling:
- Keep `production` modules as current operating core.
- Keep `pilot` modules as active hardening targets.
- Keep `scaffold` modules as integration contracts and future adapters.
- Do not delete scaffold code until there is a replacement contract and migration plan.

## Suggested Operational Tagging Convention

For future clarity, tag each module header or doc with:
- `Maturity: production|pilot|scaffold`
- `External dependencies: <list>`
- `Fallback behavior: <none|degraded|mock>`
- `Owner: <team/person>`

This file is the baseline for that transition.
