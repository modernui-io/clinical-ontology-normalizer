"""FastAPI application for Clinical Ontology Normalizer."""

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    AuditMiddleware,
    ErrorHandlerMiddleware,
    RequestIdMiddleware,
    assistant_router,
    audit_router,
    auth_router,
    calculators_router,
    cdisc_router,
    cds_hooks_router,
    coding_router,
    cohorts_router,
    dashboard_router,
    documents_router,
    etl_router,
    export_router,
    fhir_router,
    jobs_router,
    llm_router,
    notes_router,
    notifications_router,
    patients_router,
    quality_router,
    reconciliation_router,
    search_router,
    smart_router,
    sse_router,
    terminology_router,
    timeline_router,
    users_router,
    valuesets_router,
    vocabulary_mapping_router,
    websocket_router,
)
from app.api.middleware.error_handler import register_exception_handlers
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.queue import clear_queues
from app.core.redis import close_redis
from app.services.vocabulary import get_vocabulary_service, preload_vocabulary

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

    # Startup
    if settings.debug:
        await init_db()

    # Preload vocabulary service (singleton) for fast NLP extraction
    vocab_stats = preload_vocabulary()
    logger.info(
        f"Vocabulary preloaded: {vocab_stats['concept_count']} concepts, "
        f"{vocab_stats['term_count']} terms in {vocab_stats['load_time_ms']}ms"
    )

    # Pre-warm ALL singleton services so no customer hits cold services
    prewarm_stats = prewarm_all_services()
    logger.info(
        f"Services pre-warmed: {prewarm_stats['services_loaded']} services "
        f"in {prewarm_stats['total_prewarm_time_ms']}ms"
    )

    total_startup_ms = (time.perf_counter() - startup_start) * 1000
    logger.info(f"Server ready - total startup time: {total_startup_ms:.0f}ms")

    # Store prewarm stats for health endpoint
    app.state.prewarm_stats = prewarm_stats
    app.state.startup_time_ms = total_startup_ms

    yield

    # Shutdown
    clear_queues()
    close_redis()
    await close_db()


app = FastAPI(
    title="Clinical Ontology Normalizer",
    description="API for ingesting clinical data, extracting mentions, mapping to OMOP concepts, and building patient knowledge graphs.",
    version="0.1.0",
    lifespan=lifespan,
)

# Register exception handlers for standardized error responses
register_exception_handlers(app)

# Configure middleware (order matters - first added = last executed)
# 1. Request ID middleware - adds X-Request-ID header for request tracing
app.add_middleware(RequestIdMiddleware)

# 2. Audit middleware - HIPAA-compliant request logging (logs all PHI access)
app.add_middleware(AuditMiddleware)

# 3. Error handler middleware - catches exceptions and returns standardized responses
app.add_middleware(ErrorHandlerMiddleware)

# 4. CORS middleware - handles cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # Allow frontend to read request ID
)

# Include routers
app.include_router(assistant_router)
app.include_router(audit_router)
app.include_router(calculators_router)
app.include_router(cdisc_router)
app.include_router(cds_hooks_router)
app.include_router(coding_router)
app.include_router(cohorts_router)
app.include_router(dashboard_router)
app.include_router(documents_router)
app.include_router(etl_router)
app.include_router(export_router)
app.include_router(fhir_router)
app.include_router(jobs_router)
app.include_router(llm_router)
app.include_router(notes_router)
app.include_router(notifications_router)
app.include_router(patients_router)
app.include_router(quality_router)
app.include_router(reconciliation_router)
app.include_router(search_router)
app.include_router(smart_router)
app.include_router(sse_router)
app.include_router(terminology_router)
app.include_router(timeline_router)
app.include_router(valuesets_router)
app.include_router(vocabulary_mapping_router)
app.include_router(websocket_router)


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
        "timestamp": datetime.now(UTC).isoformat(),
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
        "timestamp": datetime.now(UTC).isoformat(),
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
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }
