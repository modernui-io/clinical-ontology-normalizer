"""Dashboard API endpoints for role-based views."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.schemas.dashboard import (
    ActionItem,
    AdminDashboardResponse,
    BillerDashboardResponse,
    DashboardMetadata,
    EntityDistribution,
    ErrorSummary,
    HCCOpportunitySummary,
    ProcessingMetricsSummary,
    ProviderDashboardResponse,
    QualityDashboardResponse,
    ServiceHealthSummary,
    SystemStatsSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


# ==============================================================================
# Helper Functions
# ==============================================================================


def _create_metadata(patient_id: str | None = None) -> DashboardMetadata:
    """Create dashboard metadata."""
    return DashboardMetadata(
        generated_at=datetime.now(timezone.utc),
        patient_id=patient_id,
        time_window="24h",
    )


def _safe_get_stats(service: Any, service_name: str) -> dict[str, Any]:
    """Safely get stats from a service."""
    try:
        if hasattr(service, "get_stats"):
            return service.get_stats()
        return {}
    except Exception as e:
        logger.warning(f"Failed to get stats from {service_name}: {e}")
        return {"error": str(e)}


# ==============================================================================
# Provider Dashboard
# ==============================================================================


@router.get(
    "/provider",
    response_model=ProviderDashboardResponse,
    summary="Get provider/clinician dashboard",
    description="Aggregates clinical decision support data for providers.",
)
async def get_provider_dashboard(
    patient_id: str | None = Query(None, description="Patient ID for patient-specific view"),
) -> ProviderDashboardResponse:
    """Get clinical decision support dashboard for providers.

    Aggregates data from:
    - DifferentialDiagnosisService
    - ClinicalCalculatorService
    - DrugInteractionService
    - DrugSafetyService
    - LabReferenceService
    """
    from app.services.differential_diagnosis import get_differential_diagnosis_service
    from app.services.clinical_calculators import get_clinical_calculator_service
    from app.services.drug_interactions import get_drug_interaction_service
    from app.services.drug_safety import get_drug_safety_service
    from app.services.lab_reference import get_lab_reference_service

    # Get services
    diff_dx_service = get_differential_diagnosis_service()
    calc_service = get_clinical_calculator_service()
    drug_interaction_service = get_drug_interaction_service()
    drug_safety_service = get_drug_safety_service()
    lab_service = get_lab_reference_service()

    # Build action items based on service capabilities
    action_items = []

    # Get service statistics for summary
    stats = {
        "differential_diagnosis": _safe_get_stats(diff_dx_service, "differential_diagnosis"),
        "clinical_calculators": _safe_get_stats(calc_service, "clinical_calculators"),
        "drug_interactions": _safe_get_stats(drug_interaction_service, "drug_interactions"),
        "drug_safety": _safe_get_stats(drug_safety_service, "drug_safety"),
        "lab_reference": _safe_get_stats(lab_service, "lab_reference"),
    }

    # Add summary counts
    stats["summary"] = {
        "available_calculators": stats["clinical_calculators"].get("total_calculators", 0),
        "drug_interactions_tracked": stats["drug_interactions"].get("total_interactions", 0),
        "drug_safety_profiles": stats["drug_safety"].get("total_drug_profiles", 0),
        "lab_references": stats["lab_reference"].get("total_lab_definitions", 0),
    }

    return ProviderDashboardResponse(
        metadata=_create_metadata(patient_id),
        clinical_summary=None,  # Would be populated with patient data
        differential_diagnoses=[],  # Would be populated with patient symptoms
        risk_scores=[],  # Would be populated with patient data
        drug_alerts=[],  # Would be populated with patient medications
        abnormal_labs=[],  # Would be populated with patient labs
        stats=stats,
        action_items=action_items,
    )


# ==============================================================================
# Biller Dashboard
# ==============================================================================


@router.get(
    "/biller",
    response_model=BillerDashboardResponse,
    summary="Get biller/coder dashboard",
    description="Aggregates revenue and coding opportunity data.",
)
async def get_biller_dashboard(
    patient_id: str | None = Query(None, description="Patient ID for patient-specific view"),
    clinical_text: str | None = Query(None, description="Clinical text to analyze for opportunities"),
) -> BillerDashboardResponse:
    """Get revenue/coding opportunities dashboard for billers.

    Aggregates data from:
    - ICD10SuggesterService
    - CPTSuggesterService
    - BillingOptimizationService
    - HCCAnalyzerService
    - CodingQueryGeneratorService
    """
    from app.services.icd10_suggester import get_icd10_suggester_service
    from app.services.cpt_suggester import get_cpt_suggester_service
    from app.services.billing_optimizer import get_billing_optimization_service
    from app.services.hcc_analyzer import get_hcc_analyzer_service
    from app.services.coding_query_generator import get_coding_query_generator_service

    # Get services
    icd10_service = get_icd10_suggester_service()
    cpt_service = get_cpt_suggester_service()
    billing_service = get_billing_optimization_service()
    hcc_service = get_hcc_analyzer_service()
    cdi_service = get_coding_query_generator_service()

    # Initialize response components
    hcc_opportunities = []
    action_items = []

    # If clinical text provided, analyze for opportunities
    if clinical_text:
        # Analyze for HCC opportunities
        hcc_result = hcc_service.analyze_patient(clinical_text)
        for opp in hcc_result.opportunities[:10]:  # Top 10
            hcc_opportunities.append(
                HCCOpportunitySummary(
                    hcc_code=opp.hcc_code,
                    description=opp.hcc_description,
                    gap_type=opp.gap_type.value,
                    confidence=opp.capture_confidence.value,
                    estimated_revenue=opp.estimated_revenue,
                    recommended_icd10=opp.recommended_icd10,
                )
            )

        # Add action items from HCC analysis
        for action in hcc_result.priority_actions[:5]:
            action_items.append(
                ActionItem(
                    priority="high" if "[HIGH PRIORITY]" in action else "medium",
                    title="HCC Opportunity",
                    description=action,
                    category="hcc",
                    patient_id=patient_id,
                )
            )

    # Get service stats
    hcc_stats = _safe_get_stats(hcc_service, "hcc_analyzer")
    billing_stats = _safe_get_stats(billing_service, "billing_optimizer")
    icd10_stats = _safe_get_stats(icd10_service, "icd10_suggester")
    cpt_stats = _safe_get_stats(cpt_service, "cpt_suggester")

    # Calculate revenue summary from service stats
    revenue_summary = {
        "total_potential_revenue": sum(o.estimated_revenue for o in hcc_opportunities),
        "high_confidence_opportunities": len([o for o in hcc_opportunities if o.confidence == "high"]),
        "hcc_definitions_available": hcc_stats.get("total_hcc_definitions", 0),
        "icd10_mappings": hcc_stats.get("total_icd10_mappings", 0),
        "billing_rules_tracked": billing_stats.get("cci_bundles_tracked", 0),
        "icd10_codes_loaded": icd10_stats.get("total_codes", 0),
        "cpt_codes_loaded": cpt_stats.get("total_codes", 0),
    }

    return BillerDashboardResponse(
        metadata=_create_metadata(patient_id),
        icd10_suggestions=[],  # Would be populated with clinical text analysis
        cpt_suggestions=[],  # Would be populated with procedure analysis
        billing_findings=[],  # Would be populated with encounter analysis
        hcc_opportunities=hcc_opportunities,
        cdi_queries=[],  # Would be populated with documentation analysis
        revenue_summary=revenue_summary,
        action_items=action_items,
    )


# ==============================================================================
# Quality Dashboard
# ==============================================================================


@router.get(
    "/quality",
    response_model=QualityDashboardResponse,
    summary="Get quality metrics dashboard",
    description="Aggregates NLP processing quality and accuracy metrics.",
)
async def get_quality_dashboard(
    patient_id: str | None = Query(None, description="Patient ID for patient-specific view"),
) -> QualityDashboardResponse:
    """Get quality metrics dashboard.

    Aggregates data from:
    - QualityMetricsService
    - ReportGeneratorService
    """
    from app.services.quality_metrics import get_quality_metrics_service, TimeWindow

    # Get services
    quality_service = get_quality_metrics_service()

    # Get aggregated metrics
    try:
        aggregated = quality_service.get_aggregated_metrics(TimeWindow.DAY)

        # Build processing metrics summary
        processing_metrics = ProcessingMetricsSummary(
            documents_processed=aggregated.document_count,
            avg_processing_time_ms=aggregated.avg_total_time_ms,
            total_extractions=aggregated.total_mentions,
            avg_confidence=aggregated.avg_confidence,
            error_rate=aggregated.error_rate,
        )

        # Build entity distribution
        entity_dist = aggregated.by_entity_type
        entity_distribution = EntityDistribution(
            conditions=entity_dist.get("condition", 0),
            drugs=entity_dist.get("drug", 0),
            measurements=entity_dist.get("measurement", 0),
            procedures=entity_dist.get("procedure", 0),
            observations=entity_dist.get("observation", 0),
        )

        # Build error summary
        top_errors = [
            ErrorSummary(
                error_type=err,
                count=count,
                percentage=(count / aggregated.error_count * 100) if aggregated.error_count > 0 else 0,
            )
            for err, count in sorted(aggregated.error_types.items(), key=lambda x: -x[1])[:5]
        ]

        # Get trend data
        processing_trend = quality_service.get_processing_trend("processing_time", points=24)

        # Build action items based on metrics
        action_items = []
        if aggregated.error_rate > 0.1:  # More than 10% error rate
            action_items.append(
                ActionItem(
                    priority="high",
                    title="High Error Rate Detected",
                    description=f"Error rate of {aggregated.error_rate:.1%} exceeds 10% threshold",
                    category="quality",
                )
            )
        if aggregated.avg_confidence < 0.7:
            action_items.append(
                ActionItem(
                    priority="medium",
                    title="Low Confidence Scores",
                    description=f"Average confidence of {aggregated.avg_confidence:.1%} is below 70% target",
                    category="quality",
                )
            )

        confidence_distribution = aggregated.confidence_distribution

    except Exception as e:
        logger.warning(f"Failed to get quality metrics: {e}")
        # Return defaults if metrics unavailable
        processing_metrics = ProcessingMetricsSummary(
            documents_processed=0,
            avg_processing_time_ms=0.0,
            total_extractions=0,
            avg_confidence=0.0,
            error_rate=0.0,
        )
        entity_distribution = EntityDistribution()
        top_errors = []
        processing_trend = []
        action_items = []
        confidence_distribution = {}

    return QualityDashboardResponse(
        metadata=_create_metadata(patient_id),
        processing_metrics=processing_metrics,
        accuracy_by_entity=[],  # Would need validation data
        entity_distribution=entity_distribution,
        confidence_distribution=confidence_distribution,
        top_errors=top_errors,
        processing_trend=processing_trend,
        action_items=action_items,
    )


# ==============================================================================
# Admin Dashboard
# ==============================================================================


@router.get(
    "/admin",
    response_model=AdminDashboardResponse,
    summary="Get admin dashboard",
    description="Full system overview with all role summaries.",
)
async def get_admin_dashboard(
    patient_id: str | None = Query(None, description="Patient ID for patient-specific view"),
) -> AdminDashboardResponse:
    """Get full system overview dashboard for administrators.

    Includes:
    - All service health status
    - System-wide statistics
    - Summaries from all other dashboards
    """
    # Service health checks
    services_to_check = [
        ("differential_diagnosis", "app.services.differential_diagnosis", "get_differential_diagnosis_service"),
        ("clinical_calculator", "app.services.clinical_calculators", "get_clinical_calculator_service"),
        ("drug_interaction", "app.services.drug_interactions", "get_drug_interaction_service"),
        ("drug_safety", "app.services.drug_safety", "get_drug_safety_service"),
        ("lab_reference", "app.services.lab_reference", "get_lab_reference_service"),
        ("icd10_suggester", "app.services.icd10_suggester", "get_icd10_suggester_service"),
        ("cpt_suggester", "app.services.cpt_suggester", "get_cpt_suggester_service"),
        ("billing_optimizer", "app.services.billing_optimizer", "get_billing_optimization_service"),
        ("hcc_analyzer", "app.services.hcc_analyzer", "get_hcc_analyzer_service"),
        ("coding_query_generator", "app.services.coding_query_generator", "get_coding_query_generator_service"),
        ("quality_metrics", "app.services.quality_metrics", "get_quality_metrics_service"),
    ]

    service_health = []
    for name, module_path, func_name in services_to_check:
        try:
            import importlib
            module = importlib.import_module(module_path)
            getter = getattr(module, func_name)
            service = getter()
            stats = _safe_get_stats(service, name)
            service_health.append(
                ServiceHealthSummary(
                    service_name=name,
                    status="healthy",
                    stats=stats,
                )
            )
        except Exception as e:
            logger.error(f"Service {name} health check failed: {e}")
            service_health.append(
                ServiceHealthSummary(
                    service_name=name,
                    status="unhealthy",
                    stats={"error": str(e)},
                )
            )

    # Get summaries from other dashboards
    # Note: Must pass named arguments to avoid Query() defaults being used
    provider_resp = await get_provider_dashboard(patient_id=patient_id)
    biller_resp = await get_biller_dashboard(patient_id=patient_id, clinical_text=None)
    quality_resp = await get_quality_dashboard(patient_id=patient_id)

    # Build system stats
    system_stats = SystemStatsSummary(
        total_patients=0,  # Would query from database
        total_documents=0,  # Would query from database
        total_extractions=quality_resp.processing_metrics.total_extractions,
        documents_today=quality_resp.processing_metrics.documents_processed,
        documents_this_week=0,  # Would query from database
    )

    # Aggregate all action items
    all_action_items = (
        provider_resp.action_items + biller_resp.action_items + quality_resp.action_items
    )

    return AdminDashboardResponse(
        metadata=_create_metadata(patient_id),
        system_stats=system_stats,
        service_health=service_health,
        provider_summary=provider_resp.stats,
        biller_summary=biller_resp.revenue_summary,
        quality_summary={
            "documents_processed": quality_resp.processing_metrics.documents_processed,
            "avg_processing_time_ms": quality_resp.processing_metrics.avg_processing_time_ms,
            "error_rate": quality_resp.processing_metrics.error_rate,
            "total_extractions": quality_resp.processing_metrics.total_extractions,
        },
        all_action_items=all_action_items,
    )
