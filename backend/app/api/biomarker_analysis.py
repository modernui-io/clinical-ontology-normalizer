"""Biomarker Analysis & Real-World Evidence API endpoints (VP-DS-9).

Provides biomarker CRUD, association analysis, patient biomarker recording,
panel management, RWE study design, propensity score matching, RWE-RCT
comparability assessment, patient stratification, enrichment analysis,
and aggregate metrics.

Endpoints:
    GET    /biomarker-analysis/biomarkers                             - List biomarkers
    POST   /biomarker-analysis/biomarkers                             - Create biomarker
    GET    /biomarker-analysis/biomarkers/{id}                        - Get biomarker
    DELETE /biomarker-analysis/biomarkers/{id}                        - Delete biomarker
    PUT    /biomarker-analysis/biomarkers/{id}/status                 - Update status
    GET    /biomarker-analysis/associations                           - List associations
    POST   /biomarker-analysis/associations                           - Create association
    GET    /biomarker-analysis/associations/by-biomarker/{id}         - By biomarker
    GET    /biomarker-analysis/associations/by-condition              - By condition
    GET    /biomarker-analysis/patient-values                         - List patient values
    POST   /biomarker-analysis/patient-values                         - Record value
    GET    /biomarker-analysis/patient-values/{patient_id}            - Patient values
    GET    /biomarker-analysis/patient-values/biomarker/{id}          - Values by biomarker
    GET    /biomarker-analysis/panels                                 - List panels
    POST   /biomarker-analysis/panels                                 - Create panel
    GET    /biomarker-analysis/panels/{id}                            - Get panel
    GET    /biomarker-analysis/panels/{id}/score/{patient_id}         - Score patient
    GET    /biomarker-analysis/rwe-studies                             - List RWE studies
    POST   /biomarker-analysis/rwe-studies                             - Create RWE study
    GET    /biomarker-analysis/rwe-studies/{id}                        - Get RWE study
    DELETE /biomarker-analysis/rwe-studies/{id}                        - Delete RWE study
    POST   /biomarker-analysis/rwe-studies/{id}/complete               - Complete study
    POST   /biomarker-analysis/rwe-studies/{id}/propensity-score       - Run PS matching
    GET    /biomarker-analysis/comparabilities                         - List comparabilities
    POST   /biomarker-analysis/comparabilities                         - Create comparability
    GET    /biomarker-analysis/comparabilities/{id}                    - Get comparability
    GET    /biomarker-analysis/comparabilities/by-study/{id}           - By study
    GET    /biomarker-analysis/stratification/{biomarker_id}           - Stratify patients
    GET    /biomarker-analysis/enrichment/{biomarker_id}               - Enrichment analysis
    GET    /biomarker-analysis/metrics/biomarkers                      - Biomarker metrics
    GET    /biomarker-analysis/metrics/rwe                             - RWE metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.biomarker_analysis import (
    AssociationCreateRequest,
    Biomarker,
    BiomarkerAssociation,
    BiomarkerCreateRequest,
    BiomarkerListResponse,
    BiomarkerMetrics,
    BiomarkerPanel,
    BiomarkerRole,
    BiomarkerStatus,
    BiomarkerStratificationResult,
    BiomarkerType,
    ComparabilityCreateRequest,
    EnrichmentResult,
    EvidenceLevel,
    MatchingMethod,
    PanelCreateRequest,
    PatientBiomarkerRequest,
    PatientBiomarkerValue,
    PropensityScoreResult,
    RWEComparability,
    RWEMetrics,
    RWEStudy,
    RWEStudyCreateRequest,
    RWEStudyListResponse,
    RWEStudyType,
)
from app.services.biomarker_analysis_service import get_biomarker_analysis_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/biomarker-analysis",
    tags=["Biomarker Analysis"],
)


# ---------------------------------------------------------------------------
# Biomarker CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/biomarkers",
    response_model=BiomarkerListResponse,
    summary="List all biomarkers",
    description="Retrieve all biomarkers with optional type/role/status filters.",
)
async def list_biomarkers(
    biomarker_type: Optional[BiomarkerType] = Query(None),
    role: Optional[BiomarkerRole] = Query(None),
    status: Optional[BiomarkerStatus] = Query(None),
) -> BiomarkerListResponse:
    """List all biomarkers."""
    svc = get_biomarker_analysis_service()
    items = svc.list_biomarkers(biomarker_type=biomarker_type, role=role, status=status)
    return BiomarkerListResponse(items=items, total=len(items))


@router.post(
    "/biomarkers",
    response_model=Biomarker,
    status_code=201,
    summary="Create a biomarker",
    description="Register a new biomarker in the discovery pipeline.",
)
async def create_biomarker(req: BiomarkerCreateRequest) -> Biomarker:
    """Create a new biomarker."""
    svc = get_biomarker_analysis_service()
    return svc.create_biomarker(req)


@router.get(
    "/biomarkers/{biomarker_id}",
    response_model=Biomarker,
    summary="Get a biomarker",
    description="Retrieve a single biomarker by its ID.",
)
async def get_biomarker(biomarker_id: str) -> Biomarker:
    """Get a single biomarker."""
    svc = get_biomarker_analysis_service()
    bm = svc.get_biomarker(biomarker_id)
    if bm is None:
        raise HTTPException(status_code=404, detail=f"Biomarker {biomarker_id} not found")
    return bm


@router.delete(
    "/biomarkers/{biomarker_id}",
    status_code=204,
    summary="Delete a biomarker",
    description="Remove a biomarker from the system.",
)
async def delete_biomarker(biomarker_id: str) -> None:
    """Delete a biomarker."""
    svc = get_biomarker_analysis_service()
    if not svc.delete_biomarker(biomarker_id):
        raise HTTPException(status_code=404, detail=f"Biomarker {biomarker_id} not found")


@router.put(
    "/biomarkers/{biomarker_id}/status",
    response_model=Biomarker,
    summary="Update biomarker status",
    description="Advance a biomarker through its lifecycle (DISCOVERED -> VALIDATED -> QUALIFIED -> APPROVED or REJECTED).",
)
async def update_biomarker_status(
    biomarker_id: str,
    new_status: BiomarkerStatus = Query(...),
) -> Biomarker:
    """Update biomarker lifecycle status."""
    svc = get_biomarker_analysis_service()
    result = svc.update_biomarker_status(biomarker_id, new_status)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition biomarker {biomarker_id} to {new_status.value}",
        )
    return result


# ---------------------------------------------------------------------------
# Association analysis
# ---------------------------------------------------------------------------


@router.get(
    "/associations",
    response_model=list[BiomarkerAssociation],
    summary="List all associations",
    description="Retrieve all biomarker-condition associations.",
)
async def list_associations() -> list[BiomarkerAssociation]:
    """List all associations."""
    svc = get_biomarker_analysis_service()
    return svc.list_associations()


@router.post(
    "/associations",
    response_model=BiomarkerAssociation,
    status_code=201,
    summary="Create an association",
    description="Register a new biomarker-condition association.",
)
async def create_association(req: AssociationCreateRequest) -> BiomarkerAssociation:
    """Create a new association."""
    svc = get_biomarker_analysis_service()
    assoc = svc.create_association(req)
    if assoc is None:
        raise HTTPException(status_code=404, detail=f"Biomarker {req.biomarker_id} not found")
    return assoc


@router.get(
    "/associations/by-biomarker/{biomarker_id}",
    response_model=list[BiomarkerAssociation],
    summary="Get associations by biomarker",
    description="Get all associations for a specific biomarker.",
)
async def get_associations_by_biomarker(biomarker_id: str) -> list[BiomarkerAssociation]:
    """Get associations by biomarker."""
    svc = get_biomarker_analysis_service()
    return svc.get_associations_by_biomarker(biomarker_id)


@router.get(
    "/associations/by-condition",
    response_model=list[BiomarkerAssociation],
    summary="Get associations by condition",
    description="Get all associations for a specific condition.",
)
async def get_associations_by_condition(
    condition: str = Query(..., description="Clinical condition to search for"),
) -> list[BiomarkerAssociation]:
    """Get associations by condition."""
    svc = get_biomarker_analysis_service()
    return svc.get_associations_by_condition(condition)


# ---------------------------------------------------------------------------
# Patient biomarker values
# ---------------------------------------------------------------------------


@router.get(
    "/patient-values",
    response_model=list[PatientBiomarkerValue],
    summary="List all patient biomarker values",
    description="Retrieve all recorded patient biomarker measurements.",
)
async def list_patient_values() -> list[PatientBiomarkerValue]:
    """List all patient biomarker values."""
    svc = get_biomarker_analysis_service()
    return svc.list_patient_values()


@router.post(
    "/patient-values",
    response_model=PatientBiomarkerValue,
    status_code=201,
    summary="Record a patient biomarker value",
    description="Record a biomarker measurement for a patient. Automatically detects abnormality.",
)
async def record_patient_biomarker(req: PatientBiomarkerRequest) -> PatientBiomarkerValue:
    """Record a patient biomarker value."""
    svc = get_biomarker_analysis_service()
    result = svc.record_patient_biomarker(req)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Biomarker {req.biomarker_id} not found")
    return result


@router.get(
    "/patient-values/{patient_id}",
    response_model=list[PatientBiomarkerValue],
    summary="Get patient biomarker values",
    description="Retrieve all biomarker values for a specific patient.",
)
async def get_patient_biomarkers(patient_id: str) -> list[PatientBiomarkerValue]:
    """Get all biomarker values for a patient."""
    svc = get_biomarker_analysis_service()
    return svc.get_patient_biomarkers(patient_id)


@router.get(
    "/patient-values/biomarker/{biomarker_id}",
    response_model=list[PatientBiomarkerValue],
    summary="Get values by biomarker",
    description="Retrieve all patient values for a specific biomarker.",
)
async def get_biomarker_patient_values(biomarker_id: str) -> list[PatientBiomarkerValue]:
    """Get all patient values for a biomarker."""
    svc = get_biomarker_analysis_service()
    return svc.get_biomarker_patient_values(biomarker_id)


# ---------------------------------------------------------------------------
# Panel management
# ---------------------------------------------------------------------------


@router.get(
    "/panels",
    response_model=list[BiomarkerPanel],
    summary="List all biomarker panels",
    description="Retrieve all biomarker panels.",
)
async def list_panels() -> list[BiomarkerPanel]:
    """List all panels."""
    svc = get_biomarker_analysis_service()
    return svc.list_panels()


@router.post(
    "/panels",
    response_model=BiomarkerPanel,
    status_code=201,
    summary="Create a biomarker panel",
    description="Create a new biomarker panel with composite performance calculation.",
)
async def create_panel(req: PanelCreateRequest) -> BiomarkerPanel:
    """Create a new panel."""
    svc = get_biomarker_analysis_service()
    return svc.create_panel(req)


@router.get(
    "/panels/{panel_id}",
    response_model=BiomarkerPanel,
    summary="Get a panel",
    description="Retrieve a specific biomarker panel.",
)
async def get_panel(panel_id: str) -> BiomarkerPanel:
    """Get a panel."""
    svc = get_biomarker_analysis_service()
    panel = svc.get_panel(panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail=f"Panel {panel_id} not found")
    return panel


@router.get(
    "/panels/{panel_id}/score/{patient_id}",
    summary="Score patient against panel",
    description="Evaluate a patient against a biomarker panel, returning individual and composite scores.",
)
async def score_patient_panel(panel_id: str, patient_id: str) -> dict:
    """Score a patient against a biomarker panel."""
    svc = get_biomarker_analysis_service()
    result = svc.score_patient_panel(panel_id, patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Panel {panel_id} not found")
    return result


# ---------------------------------------------------------------------------
# RWE Study CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/rwe-studies",
    response_model=RWEStudyListResponse,
    summary="List all RWE studies",
    description="Retrieve all real-world evidence studies with optional filters.",
)
async def list_rwe_studies(
    study_type: Optional[RWEStudyType] = Query(None),
    status: Optional[str] = Query(None),
) -> RWEStudyListResponse:
    """List all RWE studies."""
    svc = get_biomarker_analysis_service()
    items = svc.list_rwe_studies(study_type=study_type, status=status)
    return RWEStudyListResponse(items=items, total=len(items))


@router.post(
    "/rwe-studies",
    response_model=RWEStudy,
    status_code=201,
    summary="Create an RWE study",
    description="Design and register a new real-world evidence study.",
)
async def create_rwe_study(req: RWEStudyCreateRequest) -> RWEStudy:
    """Create a new RWE study."""
    svc = get_biomarker_analysis_service()
    return svc.create_rwe_study(req)


@router.get(
    "/rwe-studies/{study_id}",
    response_model=RWEStudy,
    summary="Get an RWE study",
    description="Retrieve a specific RWE study by its ID.",
)
async def get_rwe_study(study_id: str) -> RWEStudy:
    """Get an RWE study."""
    svc = get_biomarker_analysis_service()
    study = svc.get_rwe_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"RWE study {study_id} not found")
    return study


@router.delete(
    "/rwe-studies/{study_id}",
    status_code=204,
    summary="Delete an RWE study",
    description="Remove an RWE study from the system.",
)
async def delete_rwe_study(study_id: str) -> None:
    """Delete an RWE study."""
    svc = get_biomarker_analysis_service()
    if not svc.delete_rwe_study(study_id):
        raise HTTPException(status_code=404, detail=f"RWE study {study_id} not found")


@router.post(
    "/rwe-studies/{study_id}/complete",
    response_model=RWEStudy,
    summary="Complete an RWE study",
    description="Complete an RWE study with results, effect size, and bias assessment.",
)
async def complete_rwe_study(
    study_id: str,
    results_summary: str = Query(...),
    treatment_effect: float = Query(...),
    ci_lower: float = Query(...),
    ci_upper: float = Query(...),
    p_value: float = Query(...),
    bias_assessment: str = Query(""),
) -> RWEStudy:
    """Complete an RWE study with results."""
    svc = get_biomarker_analysis_service()
    result = svc.complete_rwe_study(
        study_id=study_id,
        results_summary=results_summary,
        treatment_effect=treatment_effect,
        confidence_interval=(ci_lower, ci_upper),
        p_value=p_value,
        bias_assessment=bias_assessment,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"RWE study {study_id} not found")
    return result


@router.post(
    "/rwe-studies/{study_id}/propensity-score",
    response_model=PropensityScoreResult,
    summary="Run propensity score matching",
    description="Simulate propensity score matching for an RWE study.",
)
async def run_propensity_score(study_id: str) -> PropensityScoreResult:
    """Run propensity score matching."""
    svc = get_biomarker_analysis_service()
    result = svc.run_propensity_score_matching(study_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"RWE study {study_id} not found")
    return result


# ---------------------------------------------------------------------------
# RWE-RCT Comparability
# ---------------------------------------------------------------------------


@router.get(
    "/comparabilities",
    response_model=list[RWEComparability],
    summary="List all comparabilities",
    description="Retrieve all RWE-RCT comparability assessments.",
)
async def list_comparabilities() -> list[RWEComparability]:
    """List all comparabilities."""
    svc = get_biomarker_analysis_service()
    return svc.list_comparabilities()


@router.post(
    "/comparabilities",
    response_model=RWEComparability,
    status_code=201,
    summary="Create a comparability assessment",
    description="Create a new RWE-RCT comparability assessment.",
)
async def create_comparability(req: ComparabilityCreateRequest) -> RWEComparability:
    """Create a comparability assessment."""
    svc = get_biomarker_analysis_service()
    result = svc.create_comparability(req)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"RWE study {req.rwe_study_id} not found",
        )
    return result


@router.get(
    "/comparabilities/{cmp_id}",
    response_model=RWEComparability,
    summary="Get a comparability assessment",
    description="Retrieve a specific comparability assessment.",
)
async def get_comparability(cmp_id: str) -> RWEComparability:
    """Get a comparability assessment."""
    svc = get_biomarker_analysis_service()
    result = svc.get_comparability(cmp_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Comparability {cmp_id} not found")
    return result


@router.get(
    "/comparabilities/by-study/{rwe_study_id}",
    response_model=list[RWEComparability],
    summary="Get comparabilities by study",
    description="Retrieve all comparability assessments for a given RWE study.",
)
async def get_comparabilities_by_study(rwe_study_id: str) -> list[RWEComparability]:
    """Get comparabilities by RWE study."""
    svc = get_biomarker_analysis_service()
    return svc.get_comparabilities_by_study(rwe_study_id)


# ---------------------------------------------------------------------------
# Stratification & Enrichment
# ---------------------------------------------------------------------------


@router.get(
    "/stratification/{biomarker_id}",
    response_model=BiomarkerStratificationResult,
    summary="Stratify patients by biomarker",
    description="Group patients above/below a threshold for a specific biomarker.",
)
async def stratify_patients(
    biomarker_id: str,
    threshold: Optional[float] = Query(None, description="Custom threshold; defaults to normal range high"),
) -> BiomarkerStratificationResult:
    """Stratify patients by biomarker value."""
    svc = get_biomarker_analysis_service()
    result = svc.stratify_patients(biomarker_id, threshold=threshold)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Biomarker {biomarker_id} not found")
    return result


@router.get(
    "/enrichment/{biomarker_id}",
    response_model=EnrichmentResult,
    summary="Run enrichment analysis",
    description="Determine if a biomarker predicts trial success using available association data.",
)
async def enrichment_analysis(biomarker_id: str) -> EnrichmentResult:
    """Run enrichment analysis for a biomarker."""
    svc = get_biomarker_analysis_service()
    result = svc.enrichment_analysis(biomarker_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Biomarker {biomarker_id} not found")
    return result


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics/biomarkers",
    response_model=BiomarkerMetrics,
    summary="Biomarker aggregate metrics",
    description="Discovery funnel, validation rates, and performance statistics.",
)
async def biomarker_metrics() -> BiomarkerMetrics:
    """Get biomarker aggregate metrics."""
    svc = get_biomarker_analysis_service()
    return svc.get_biomarker_metrics()


@router.get(
    "/metrics/rwe",
    response_model=RWEMetrics,
    summary="RWE aggregate metrics",
    description="Study completion rates, effect sizes, and comparability scores.",
)
async def rwe_metrics() -> RWEMetrics:
    """Get RWE aggregate metrics."""
    svc = get_biomarker_analysis_service()
    return svc.get_rwe_metrics()
