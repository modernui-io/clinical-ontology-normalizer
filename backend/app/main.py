"""FastAPI application for Clinical Ontology Normalizer."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import (
    AuditMiddleware,
    ErrorHandlerMiddleware,
    MetricsMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    agent_router,
    agent_chat_router,
    ai_audit_router,
    ai_coding_router,
    assistant_router,
    audit_router,
    auth_router,
    auth_sessions_router,
    calculators_router,
    clinical_calculators_router,
    data_driven_calculators_router,
    cdisc_router,
    cds_hooks_router,
    coding_router,
    cohorts_router,
    dashboard_router,
    documents_router,
    etl_router,
    export_router,
    federated_router,
    fhir_router,
    graph_router,
    graph_reasoning_router,
    graph_rag_router,
    health_router,
    jobs_router,
    job_queue_router,
    llm_router,
    llm_finetuning_router,
    metrics_router,
    nlp_router,
    notes_router,
    notifications_router,
    patients_router,
    predictions_router,
    quality_router,
    quality_measures_router,
    reconciliation_router,
    risk_router,
    search_router,
    semantic_search_router,
    smart_router,
    smart_server_router,
    sse_router,
    tefca_router,
    terminology_router,
    timeline_router,
    users_router,
    valuesets_router,
    clinical_valuesets_router,
    visualizations_router,
    vocabulary_mapping_router,
    websocket_router,
    streaming_router,
    synthetic_router,
    knowledge_graph_fhir_router,
    kg_benchmark_router,
    kg_health_router,
    kg_orchestration_router,
    drug_safety_router,
    differential_diagnosis_router,
    icd10_suggestions_router,
    cpt_suggestions_router,
    hcc_analysis_router,
    voice_router,
    coding_assistant_router,
    lab_reference_router,
    alert_rules_router,
    risk_thresholds_router,
    prediction_audit_router,
    pipeline_scheduling_router,
    data_completeness_router,
    data_consistency_router,
    model_registry_router,
    clinical_agent_router,
    guidelines_router,
    policy_router,
    vocabulary_router,
    data_sources_router,
    phenotypes_router,
    pipeline_version_router,
    pipelines_router,
    feedback_router,
    trials_router,
    bulk_screening_router,
    mapping_quality_router,
    model_evaluation_router,
    metriport_api_router,
    metriport_webhook_router,
    lineage_router,
    incidents_router,
    screening_results_router,
    sites_router,
    backup_status_router,
    roi_dashboard_router,
    terminology_governance_router,
    cohort_phenotypes_router,
    consent_router,
    data_quality_dqd_router,
    screen_failure_analytics_router,
    diversity_analytics_router,
    criteria_fidelity_router,
    etl_validation_router,
    fhir_validation_router,
    validation_study_router,
    experiments_router,
    gold_standard_router,
    observability_router,
    secret_rotation_router,
    data_governance_router,
    drift_detection_router,
    fairness_audit_router,
    quality_management_router,
    iac_management_router,
    infrastructure_router,
    soc2_compliance_router,
    rfp_management_router,
    scalability_audit_router,
    hitrust_compliance_router,
    data_classification_router,
    traceability_router,
)
from app.api.error_handlers import register_all_exception_handlers
from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.sli_collector import SLICollectorMiddleware, sli_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.logging_config import setup_logging
from app.core.queue import clear_queues
from app.core.redis import close_redis
from app.services.smart_fhir import close_smart_client
from app.services.vocabulary import get_vocabulary_service, preload_vocabulary

# CTO-6: Configure structured logging before any logger is used.
# In production this emits JSON; in debug mode it emits colored text.
setup_logging()

logger = logging.getLogger(__name__)


def prewarm_all_services() -> dict[str, Any]:
    """Pre-warm all singleton services at startup.

    This ensures no customer ever hits a cold service.
    All data is loaded into memory before accepting requests.

    Returns:
        Dictionary with service names and their stats.
    """
    start_time = time.perf_counter()
    services_loaded = {}

    # Clinical Decision Support Services
    try:
        from app.services.differential_diagnosis import get_differential_diagnosis_service
        svc = get_differential_diagnosis_service()
        services_loaded["differential_diagnosis"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm differential_diagnosis: {e}")

    try:
        from app.services.clinical_calculators import get_clinical_calculator_service
        svc = get_clinical_calculator_service()
        services_loaded["clinical_calculators"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm clinical_calculators: {e}")

    try:
        from app.services.calculator_builder import get_calculator_builder_service
        svc = get_calculator_builder_service()
        services_loaded["calculator_builder"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm calculator_builder: {e}")

    try:
        from app.services.lab_reference import get_lab_reference_service
        svc = get_lab_reference_service()
        services_loaded["lab_reference"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm lab_reference: {e}")

    # Drug Safety Services
    try:
        from app.services.drug_interactions import get_drug_interaction_service
        svc = get_drug_interaction_service()
        services_loaded["drug_interactions"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm drug_interactions: {e}")

    try:
        from app.services.drug_safety import get_drug_safety_service
        svc = get_drug_safety_service()
        services_loaded["drug_safety"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm drug_safety: {e}")

    # Billing & Coding Services
    try:
        from app.services.icd10_suggester import get_icd10_suggester_service
        svc = get_icd10_suggester_service()
        services_loaded["icd10_suggester"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm icd10_suggester: {e}")

    try:
        from app.services.cpt_suggester import get_cpt_suggester_service
        svc = get_cpt_suggester_service()
        services_loaded["cpt_suggester"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm cpt_suggester: {e}")

    try:
        from app.services.hcc_analyzer import get_hcc_analyzer_service
        svc = get_hcc_analyzer_service()
        services_loaded["hcc_analyzer"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm hcc_analyzer: {e}")

    try:
        from app.services.billing_optimizer import get_billing_optimization_service
        svc = get_billing_optimization_service()
        services_loaded["billing_optimizer"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm billing_optimizer: {e}")

    try:
        from app.services.coding_query_generator import get_coding_query_generator_service
        svc = get_coding_query_generator_service()
        services_loaded["coding_query_generator"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm coding_query_generator: {e}")

    # NLP Services
    try:
        from app.services.nlp_advanced import get_advanced_nlp_service
        svc = get_advanced_nlp_service()
        services_loaded["nlp_advanced"] = "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm nlp_advanced: {e}")

    try:
        from app.services.vocabulary_enhanced import get_enhanced_vocabulary_service
        svc = get_enhanced_vocabulary_service()
        services_loaded["vocabulary_enhanced"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm vocabulary_enhanced: {e}")

    try:
        from app.services.value_extraction import get_value_extraction_service
        svc = get_value_extraction_service()
        services_loaded["value_extraction"] = "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm value_extraction: {e}")

    try:
        from app.services.nlp_entity_service import get_nlp_entity_service
        svc = get_nlp_entity_service()
        services_loaded["nlp_entity_service"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm nlp_entity_service: {e}")

    # Audit Service (HIPAA compliance)
    try:
        from app.services.audit_service import get_audit_service
        svc = get_audit_service()
        services_loaded["audit_service"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm audit_service: {e}")

    # Quality Measure Service (HEDIS/CQM)
    try:
        from app.services.quality_measures import get_quality_measure_service
        svc = get_quality_measure_service()
        services_loaded["quality_measures"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm quality_measures: {e}")

    # Patient Timeline Service
    try:
        from app.services.patient_timeline import get_patient_timeline_service
        svc = get_patient_timeline_service()
        services_loaded["patient_timeline"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm patient_timeline: {e}")

    # Value Set Service (Terminology Management)
    try:
        from app.services.value_set_service import get_value_set_service
        svc = get_value_set_service()
        services_loaded["value_set_service"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm value_set_service: {e}")

    # CDS Hooks Service
    try:
        from app.services.cds_hooks_service import get_cds_hooks_service
        svc = get_cds_hooks_service()
        services_loaded["cds_hooks"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm cds_hooks: {e}")

    # Bulk Export Service
    try:
        from app.services.bulk_export_service import get_bulk_export_service
        svc = get_bulk_export_service()
        services_loaded["bulk_export"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm bulk_export: {e}")

    # Graph Database Service (Neo4j Knowledge Graph)
    try:
        from app.services.graph_database_service import get_graph_database_service
        svc = get_graph_database_service()
        services_loaded["graph_database"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm graph_database: {e}")

    # Graph Analytics Service
    try:
        from app.services.graph_analytics_service import get_graph_analytics_service
        svc = get_graph_analytics_service()
        services_loaded["graph_analytics"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm graph_analytics: {e}")

    # ML Model Service (Predictive Analytics)
    try:
        from app.services.ml_model_service import get_ml_model_service
        svc = get_ml_model_service()
        services_loaded["ml_model_service"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm ml_model_service: {e}")

    # Risk Prediction Service
    try:
        from app.services.risk_prediction_service import get_risk_prediction_service
        svc = get_risk_prediction_service()
        services_loaded["risk_prediction"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm risk_prediction: {e}")

    # Federated Learning Service
    try:
        from app.services.federated_learning_service import get_federated_learning_service
        svc = get_federated_learning_service()
        services_loaded["federated_learning"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm federated_learning: {e}")

    # Synthetic Data Service
    try:
        from app.services.synthetic_data_service import get_synthetic_data_service
        svc = get_synthetic_data_service()
        services_loaded["synthetic_data"] = svc.get_stats() if hasattr(svc, 'get_stats') else "loaded"
    except Exception as e:
        logger.warning(f"Failed to prewarm synthetic_data: {e}")

    total_time_ms = (time.perf_counter() - start_time) * 1000

    return {
        "services_loaded": len(services_loaded),
        "total_prewarm_time_ms": round(total_time_ms, 2),
        "services": services_loaded,
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize database, preload vocabulary, prewarm ALL services
    - Shutdown: Close database and Redis connections, clear queues

    Pre-warming ensures no customer ever hits a cold service.
    """
    startup_start = time.perf_counter()
    startup_timestamp = datetime.now(timezone.utc)

    # Log startup initiation with environment info
    logger.info(
        "Application startup initiated",
        extra={
            "event": "startup_begin",
            "timestamp": startup_timestamp.isoformat(),
            "debug_mode": settings.debug,
            "api_version": "v1",
            "api_prefix": settings.api_v1_prefix,
        }
    )

    # Set app start time for health check uptime tracking
    from app.api.health import set_app_start_time
    set_app_start_time(time.time())

    # Startup - Initialize database (development only)
    # VPE-3: In production/staging, schema is managed exclusively by Alembic.
    # init_db() calls create_all() which bypasses migration tracking.
    # The guard inside init_db() will also refuse to run in production/staging.
    if settings.debug and settings.environment.lower() not in ("production", "staging"):
        logger.info("Initializing database via create_all (debug mode, non-production)")
        try:
            await init_db()
            logger.info("Database tables initialized via create_all")
        except Exception as e:
            logger.warning(f"Database init (create_all) skipped — tables may already exist: {e}")
    else:
        logger.info(
            "Skipping create_all — schema managed by Alembic migrations "
            "(environment=%s, debug=%s)",
            settings.environment,
            settings.debug,
        )

    # Preload vocabulary service (singleton) for fast NLP extraction
    logger.info("Preloading vocabulary service...")
    vocab_stats = preload_vocabulary()
    logger.info(
        f"Vocabulary preloaded: {vocab_stats['concept_count']} concepts, "
        f"{vocab_stats['term_count']} terms in {vocab_stats['load_time_ms']}ms"
    )

    # Skip pre-warming at startup - services initialize lazily on first request
    # This avoids startup hangs when dependent services are unavailable
    prewarm_stats = {"services_loaded": 0, "total_prewarm_time_ms": 0, "services": {}}
    logger.info("Skipping service pre-warming (lazy initialization enabled)")

    total_startup_ms = (time.perf_counter() - startup_start) * 1000

    # Store prewarm stats for health endpoint
    app.state.prewarm_stats = prewarm_stats
    app.state.startup_time_ms = total_startup_ms
    app.state.startup_timestamp = startup_timestamp

    # Log startup completion with full details
    logger.info(
        "Application startup complete - ready to accept requests",
        extra={
            "event": "startup_complete",
            "startup_time_ms": round(total_startup_ms, 2),
            "services_loaded": prewarm_stats["services_loaded"],
            "vocabulary_concepts": vocab_stats["concept_count"],
            "vocabulary_terms": vocab_stats["term_count"],
            "api_endpoints": f"{settings.api_v1_prefix}/*",
            "docs_url": "/api/v1/docs",
        }
    )

    yield

    # Shutdown
    shutdown_start = time.perf_counter()
    logger.info(
        "Application shutdown initiated",
        extra={
            "event": "shutdown_begin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Clean up resources
    logger.info("Clearing job queues...")
    clear_queues()

    # VP-Lifecycle-2: Close SMART client HTTP connection
    logger.info("Closing SMART client...")
    await close_smart_client()

    logger.info("Closing Redis connections...")
    close_redis()

    logger.info("Closing database connections...")
    await close_db()

    shutdown_time_ms = (time.perf_counter() - shutdown_start) * 1000
    logger.info(
        "Application shutdown complete",
        extra={
            "event": "shutdown_complete",
            "shutdown_time_ms": round(shutdown_time_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


app = FastAPI(
    title="Clinical Ontology Normalizer",
    description="""
## Clinical Ontology Normalizer API

A comprehensive healthcare data platform for clinical data normalization,
terminology mapping, and knowledge graph construction.

### Features

- **Clinical NLP**: Extract medical entities from clinical text
- **Terminology Mapping**: Map to OMOP, SNOMED-CT, ICD-10, CPT, RxNorm
- **Drug Safety**: Check drug interactions and contraindications
- **Billing Optimization**: ICD-10 and CPT code suggestions with HCC analysis
- **Knowledge Graphs**: Neo4j-powered clinical concept relationships
- **Real-time Streaming**: Kafka-based HL7v2/FHIR message processing
- **FHIR R4 Support**: Full FHIR resource management and CDS Hooks

### Authentication

Most endpoints require API key authentication via the `X-API-Key` header.
Public endpoints (health checks, metrics) do not require authentication.

### Rate Limiting

API requests are rate-limited. Check response headers for limits:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when the window resets

### Environments

| Environment | Base URL |
|-------------|----------|
| Development | http://localhost:8000/api/v1 |
| Staging | https://staging.example.com/api/v1 |
| Production | https://api.example.com/api/v1 |
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    openapi_tags=[
        {
            "name": "Health",
            "description": "Health check and observability endpoints for monitoring system status.",
        },
        {
            "name": "Metrics",
            "description": "Prometheus-compatible metrics for monitoring and alerting.",
        },
        {
            "name": "Patients",
            "description": "Patient management and demographic operations.",
        },
        {
            "name": "Documents",
            "description": "Clinical document ingestion and NLP processing.",
        },
        {
            "name": "Coding",
            "description": "Medical coding assistance for ICD-10, CPT, and HCPCS.",
        },
        {
            "name": "Search",
            "description": "Full-text and semantic search across clinical data.",
        },
        {
            "name": "FHIR",
            "description": "FHIR R4 resource management and operations.",
        },
        {
            "name": "Terminology",
            "description": "Clinical terminology lookup and mapping services.",
        },
        {
            "name": "Graph",
            "description": "Knowledge graph queries and relationship exploration.",
        },
        {
            "name": "Predictions",
            "description": "ML-powered clinical predictions and risk scores.",
        },
        {
            "name": "Quality",
            "description": "Clinical quality measures (HEDIS, CQM) calculation.",
        },
        {
            "name": "Audit",
            "description": "HIPAA-compliant audit logging and compliance reporting.",
        },
        {
            "name": "Drug Safety",
            "description": "Drug safety checking: contraindications, interactions, pregnancy/lactation safety, and dosing guidelines.",
        },
        {
            "name": "ICD-10 Suggestions",
            "description": "ICD-10-CM code suggestions from clinical text with CER citations and coding guidance.",
        },
        {
            "name": "HCC Analysis",
            "description": "Hierarchical Condition Category gap analysis with RAF score calculation and revenue impact.",
        },
        {
            "name": "CPT Suggestions",
            "description": "CPT code suggestions for procedures and E/M services with bundling analysis.",
        },
        {
            "name": "Differential Diagnosis",
            "description": "Clinical decision support for ranked differential diagnoses based on symptoms and findings.",
        },
        {
            "name": "FHIR Terminology",
            "description": "FHIR R4 Terminology Services: $lookup, $validate-code, $expand, $translate, $subsumes, $closure.",
        },
    ],
    servers=[
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://staging.example.com", "description": "Staging server"},
        {"url": "https://api.example.com", "description": "Production server"},
    ],
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://example.com/license",
    },
)

# ============================================================================
# API Versioning - Create versioned router
# ============================================================================

api_v1_router = APIRouter(prefix=settings.api_v1_prefix)

# Register exception handlers for standardized error responses
register_all_exception_handlers(app)

# Configure middleware (order matters - first added = last executed)
# 1. Request ID middleware - adds X-Request-ID header for request tracing
app.add_middleware(RequestIdMiddleware)

# 2. Request logging middleware - structured access log for every request (CTO-6)
from app.api.middleware.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# 3. Audit middleware - HIPAA-compliant request logging (logs all PHI access)
app.add_middleware(AuditMiddleware)

# 4. Metrics middleware - collects request metrics for Prometheus
app.add_middleware(MetricsMiddleware)

# 4b. SLI collector middleware - VPE-4: per-endpoint SLI metrics for SLA monitoring
app.add_middleware(SLICollectorMiddleware)

# 5. Rate limit middleware - enforces rate limits per endpoint
app.add_middleware(RateLimitMiddleware)

# 6. Error handler middleware - catches exceptions and returns standardized responses
app.add_middleware(ErrorHandlerMiddleware)

# 7. Security headers middleware - adds OWASP security headers (VP-Security)
app.add_middleware(SecurityHeadersMiddleware)

# 8. API Maturity Gate middleware - labels tiers and blocks scaffold in production (CTO-2)
from app.api.middleware.maturity_gate import MaturityGateMiddleware
app.add_middleware(MaturityGateMiddleware)

# 9. CORS middleware - handles cross-origin requests
# VP-Security-3: CORS origins loaded from environment (settings.cors_origins)
_cors_origins = settings.cors_origins_list
if not _cors_origins and settings.is_production:
    logger.warning(
        "No CORS origins configured for production! "
        "Set CORS_ORIGINS environment variable."
    )
elif _cors_origins:
    logger.info(f"CORS allowed origins: {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Explicit methods
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "Accept"],  # Explicit headers
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-API-Maturity",
    ],  # Allow frontend to read these headers
)

# Include routers under versioned API router
api_v1_router.include_router(agent_router)
api_v1_router.include_router(agent_chat_router)
api_v1_router.include_router(ai_audit_router)
api_v1_router.include_router(ai_coding_router)
api_v1_router.include_router(assistant_router)
api_v1_router.include_router(auth_sessions_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(clinical_calculators_router)
api_v1_router.include_router(data_driven_calculators_router)  # Must be before calculators_router
api_v1_router.include_router(calculators_router)
api_v1_router.include_router(cdisc_router)
api_v1_router.include_router(cds_hooks_router)
api_v1_router.include_router(coding_router)
api_v1_router.include_router(cohorts_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(etl_router)
api_v1_router.include_router(export_router)
api_v1_router.include_router(federated_router)
api_v1_router.include_router(fhir_router)
api_v1_router.include_router(fhir_validation_router)
api_v1_router.include_router(graph_router)
api_v1_router.include_router(graph_reasoning_router)
api_v1_router.include_router(graph_rag_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(job_queue_router)
api_v1_router.include_router(llm_router)
api_v1_router.include_router(llm_finetuning_router)
api_v1_router.include_router(nlp_router)
api_v1_router.include_router(notes_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(patients_router)
api_v1_router.include_router(predictions_router)
api_v1_router.include_router(quality_router)
api_v1_router.include_router(quality_measures_router)
api_v1_router.include_router(reconciliation_router)
api_v1_router.include_router(risk_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(semantic_search_router)
api_v1_router.include_router(smart_router)
api_v1_router.include_router(smart_server_router)
api_v1_router.include_router(sse_router)
api_v1_router.include_router(tefca_router)
api_v1_router.include_router(terminology_router)
api_v1_router.include_router(timeline_router)
api_v1_router.include_router(valuesets_router)
api_v1_router.include_router(clinical_valuesets_router)
api_v1_router.include_router(visualizations_router)
api_v1_router.include_router(vocabulary_mapping_router)
api_v1_router.include_router(websocket_router)
api_v1_router.include_router(streaming_router)
api_v1_router.include_router(synthetic_router)
api_v1_router.include_router(knowledge_graph_fhir_router)
api_v1_router.include_router(kg_benchmark_router)
api_v1_router.include_router(kg_health_router)
api_v1_router.include_router(kg_orchestration_router)
api_v1_router.include_router(drug_safety_router)
api_v1_router.include_router(differential_diagnosis_router)
api_v1_router.include_router(icd10_suggestions_router)
api_v1_router.include_router(cpt_suggestions_router)
api_v1_router.include_router(hcc_analysis_router)
api_v1_router.include_router(voice_router)
api_v1_router.include_router(coding_assistant_router)
api_v1_router.include_router(lab_reference_router)
api_v1_router.include_router(alert_rules_router)
api_v1_router.include_router(risk_thresholds_router)
api_v1_router.include_router(prediction_audit_router)
api_v1_router.include_router(pipeline_scheduling_router)
api_v1_router.include_router(data_completeness_router)
api_v1_router.include_router(data_consistency_router)
api_v1_router.include_router(mapping_quality_router)
api_v1_router.include_router(model_evaluation_router)
api_v1_router.include_router(model_registry_router)
api_v1_router.include_router(clinical_agent_router)
api_v1_router.include_router(guidelines_router)
api_v1_router.include_router(policy_router)
api_v1_router.include_router(vocabulary_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(data_sources_router)
api_v1_router.include_router(phenotypes_router)
api_v1_router.include_router(pipeline_version_router)
api_v1_router.include_router(pipelines_router)
api_v1_router.include_router(feedback_router)
api_v1_router.include_router(bulk_screening_router)
api_v1_router.include_router(trials_router)
api_v1_router.include_router(metriport_api_router)
api_v1_router.include_router(metriport_webhook_router)
api_v1_router.include_router(lineage_router)
api_v1_router.include_router(incidents_router)
api_v1_router.include_router(screening_results_router)
api_v1_router.include_router(sites_router)
api_v1_router.include_router(backup_status_router)
api_v1_router.include_router(roi_dashboard_router)
api_v1_router.include_router(terminology_governance_router)
api_v1_router.include_router(cohort_phenotypes_router)
api_v1_router.include_router(data_quality_dqd_router)
api_v1_router.include_router(etl_validation_router)
api_v1_router.include_router(consent_router)
api_v1_router.include_router(screen_failure_analytics_router)
api_v1_router.include_router(diversity_analytics_router)
api_v1_router.include_router(criteria_fidelity_router)
api_v1_router.include_router(validation_study_router)
api_v1_router.include_router(gold_standard_router)
api_v1_router.include_router(observability_router)
api_v1_router.include_router(secret_rotation_router)
api_v1_router.include_router(experiments_router)
api_v1_router.include_router(data_governance_router)
api_v1_router.include_router(drift_detection_router)
api_v1_router.include_router(fairness_audit_router)
api_v1_router.include_router(quality_management_router)
api_v1_router.include_router(iac_management_router)
api_v1_router.include_router(infrastructure_router)
api_v1_router.include_router(soc2_compliance_router)
api_v1_router.include_router(rfp_management_router)
api_v1_router.include_router(scalability_audit_router)
api_v1_router.include_router(hitrust_compliance_router)
api_v1_router.include_router(data_classification_router)
api_v1_router.include_router(traceability_router)

# Mount versioned API router
app.include_router(api_v1_router)

# Include observability routers (health and metrics have their own /api/v1 prefixes)
app.include_router(health_router)
app.include_router(metrics_router)
# VPE-4: SLI metrics endpoints (/metrics/sli, /metrics/sli/summary)
app.include_router(sli_router)


# ============================================================================
# Legacy Route Redirects (for backward compatibility)
# ============================================================================

@app.get("/api/{path:path}", include_in_schema=False)
async def redirect_legacy_api(path: str) -> RedirectResponse:
    """Redirect legacy /api/* routes to /api/v1/*.

    This provides backward compatibility for clients using the old API paths.
    """
    return RedirectResponse(
        url=f"{settings.api_v1_prefix}/{path}",
        status_code=308,  # Permanent redirect that preserves method
    )


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint (liveness probe).

    Returns service status and basic info for monitoring.
    Use /ready for readiness checks.
    """
    return {
        "status": "healthy",
        "service": "clinical-ontology-normalizer",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict[str, Any]:
    """Readiness check endpoint.

    Confirms all services are pre-warmed and ready to handle requests.
    Use this for Kubernetes readiness probes.
    """
    vocab = get_vocabulary_service()
    vocab_stats = vocab.get_stats()

    prewarm_stats = getattr(app.state, 'prewarm_stats', {})
    startup_time = getattr(app.state, 'startup_time_ms', 0)

    return {
        "status": "ready",
        "service": "clinical-ontology-normalizer",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "startup_time_ms": startup_time,
        "vocabulary": vocab_stats,
        "prewarmed_services": prewarm_stats.get("services_loaded", 0),
        "prewarm_time_ms": prewarm_stats.get("total_prewarm_time_ms", 0),
    }


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root endpoint with API info."""
    return {
        "service": "Clinical Ontology Normalizer API",
        "version": "1.0.0",
        "api_version": "v1",
        "api_prefix": settings.api_v1_prefix,
        "docs": "/api/v1/docs",
        "redoc": "/api/v1/redoc",
        "openapi": "/api/v1/openapi.json",
        "health": "/api/v1/health",
        "metrics": "/api/v1/metrics",
        "ready": "/api/v1/health/ready",
    }


@app.get("/openapi.json", include_in_schema=False)
async def openapi_redirect() -> RedirectResponse:
    """Redirect root /openapi.json to versioned endpoint."""
    return RedirectResponse(url="/api/v1/openapi.json", status_code=308)


@app.get("/.well-known/smart-configuration", tags=["SMART on FHIR"])
async def smart_configuration(request: Request) -> dict[str, Any]:
    """SMART on FHIR well-known configuration endpoint.

    Returns the SMART App Launch configuration for this FHIR server.
    This endpoint is used by SMART apps to discover authorization endpoints.

    See: https://hl7.org/fhir/smart-app-launch/conformance.html
    """
    # Build base URL from request
    base_url = str(request.base_url).rstrip("/")

    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/api/v1/smart-server/authorize",
        "token_endpoint": f"{base_url}/api/v1/smart-server/token",
        "capabilities": [
            "launch-ehr",
            "launch-standalone",
            "client-public",
            "client-confidential-symmetric",
            "context-ehr-patient",
            "context-ehr-encounter",
            "permission-v2",
        ],
        "scopes_supported": [
            "openid",
            "fhirUser",
            "launch",
            "launch/patient",
            "launch/encounter",
            "offline_access",
            "patient/*.read",
            "patient/*.write",
            "patient/Patient.read",
            "patient/Observation.read",
            "patient/Condition.read",
            "patient/MedicationRequest.read",
            "patient/AllergyIntolerance.read",
            "patient/Procedure.read",
            "patient/Encounter.read",
            "user/*.read",
            "user/*.write",
            "system/*.read",
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": [
            "authorization_code",
            "client_credentials",
            "refresh_token",
        ],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
            "private_key_jwt",
        ],
    }
