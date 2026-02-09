"""Investigator Performance Management API endpoints (CMO-11).

Exposes investigator tracking, certification management, performance
scorecards, inspection records, training compliance, and workload
capacity planning for multi-site clinical trial operations.

Endpoints:
    GET   /investigator-management/investigators                  - List investigators
    POST  /investigator-management/investigators                  - Create investigator
    GET   /investigator-management/investigators/{id}             - Get investigator
    PUT   /investigator-management/investigators/{id}             - Update investigator
    DELETE /investigator-management/investigators/{id}            - Delete investigator
    GET   /investigator-management/certifications/{inv_id}        - List certifications
    POST  /investigator-management/certifications                 - Add certification
    GET   /investigator-management/certifications/expiry-report   - Certification expiry report
    GET   /investigator-management/scorecards/{inv_id}            - List scorecards
    GET   /investigator-management/scorecards/detail/{sc_id}      - Get scorecard detail
    POST  /investigator-management/scorecards                     - Create scorecard
    GET   /investigator-management/scorecards/compare/{inv_id}    - Compare scorecards
    GET   /investigator-management/rankings                       - Performance rankings
    GET   /investigator-management/inspections                    - List inspections
    GET   /investigator-management/inspections/{id}               - Get inspection
    POST  /investigator-management/inspections                    - Create inspection
    GET   /investigator-management/training/{inv_id}              - List training records
    POST  /investigator-management/training                       - Create training record
    GET   /investigator-management/training/gap-analysis/{inv_id} - Training gap analysis
    GET   /investigator-management/workload/{inv_id}              - Get workload
    GET   /investigator-management/workload-report                - Full workload report
    GET   /investigator-management/match                          - Find available investigators
    GET   /investigator-management/metrics                        - Aggregate metrics
    GET   /investigator-management/stats                          - Service health stats
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.permissions import Permission, PermissionChecker
from app.schemas.investigator_management import (
    CertificationExpiryReport,
    CertificationType,
    InspectionCreateRequest,
    InspectionRecord,
    Investigator,
    InvestigatorCertification,
    InvestigatorCreateRequest,
    InvestigatorListResponse,
    InvestigatorMatchResult,
    InvestigatorMetrics,
    InvestigatorScorecard,
    InvestigatorWorkload,
    PerformanceRankingResponse,
    ScorecardCreateRequest,
    ScorecardListResponse,
    TrainingCreateRequest,
    TrainingGapAnalysis,
    TrainingRecord,
    TrainingStatus,
    WorkloadReport,
)
from app.services.investigator_management_service import get_investigator_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/investigator-management",
    tags=["Investigator Management"],
)


# ---------------------------------------------------------------------------
# Permission dependency
# ---------------------------------------------------------------------------

_perm_checker = PermissionChecker([Permission.READ_ANALYTICS])


async def _require_perm(request: Request) -> None:
    return await _perm_checker(request)


# ---------------------------------------------------------------------------
# Investigator CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/investigators",
    response_model=InvestigatorListResponse,
    summary="List investigators",
    description="List all investigators with optional filters for role, site, and performance rating.",
)
async def list_investigators(
    role: Optional[str] = Query(None, description="Filter by investigator role"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    rating: Optional[str] = Query(None, description="Filter by performance rating"),
    _perm: None = Depends(_require_perm),
) -> InvestigatorListResponse:
    """Return a filtered list of investigators."""
    svc = get_investigator_management_service()
    return svc.list_investigators(role=role, site_id=site_id, rating=rating)


@router.post(
    "/investigators",
    response_model=Investigator,
    summary="Create investigator",
    description="Create a new investigator record.",
    status_code=201,
)
async def create_investigator(
    req: InvestigatorCreateRequest,
    _perm: None = Depends(_require_perm),
) -> Investigator:
    """Create a new investigator."""
    svc = get_investigator_management_service()
    return svc.create_investigator(req)


@router.get(
    "/investigators/{investigator_id}",
    response_model=Investigator,
    summary="Get investigator",
    description="Get a single investigator by ID.",
)
async def get_investigator(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> Investigator:
    """Return an investigator by ID."""
    svc = get_investigator_management_service()
    inv = svc.get_investigator(investigator_id)
    if inv is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return inv


@router.put(
    "/investigators/{investigator_id}",
    response_model=Investigator,
    summary="Update investigator",
    description="Update an existing investigator record.",
)
async def update_investigator(
    investigator_id: str,
    updates: dict,
    _perm: None = Depends(_require_perm),
) -> Investigator:
    """Update investigator fields."""
    svc = get_investigator_management_service()
    inv = svc.update_investigator(investigator_id, updates)
    if inv is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return inv


@router.delete(
    "/investigators/{investigator_id}",
    summary="Delete investigator",
    description="Delete an investigator record.",
)
async def delete_investigator(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> dict:
    """Delete an investigator."""
    svc = get_investigator_management_service()
    deleted = svc.delete_investigator(investigator_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return {"deleted": True, "investigator_id": investigator_id}


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------


@router.get(
    "/certifications/expiry-report",
    response_model=CertificationExpiryReport,
    summary="Certification expiry report",
    description="Generate a report of certifications expiring within a specified timeframe.",
)
async def get_certification_expiry_report(
    days_ahead: int = Query(90, ge=1, le=365, description="Days ahead to check for expiring certifications"),
    _perm: None = Depends(_require_perm),
) -> CertificationExpiryReport:
    """Return certification expiry report."""
    svc = get_investigator_management_service()
    return svc.get_certification_expiry_report(days_ahead)


@router.get(
    "/certifications/{investigator_id}",
    response_model=list[InvestigatorCertification],
    summary="List certifications",
    description="List all certifications for an investigator.",
)
async def list_certifications(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> list[InvestigatorCertification]:
    """Return certifications for an investigator."""
    svc = get_investigator_management_service()
    if svc.get_investigator(investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return svc.get_certifications(investigator_id)


@router.post(
    "/certifications",
    response_model=InvestigatorCertification,
    summary="Add certification",
    description="Add a new certification record for an investigator.",
    status_code=201,
)
async def add_certification(
    investigator_id: str = Query(..., description="Investigator ID"),
    certification_type: CertificationType = Query(..., description="Certification type"),
    issued_date: str = Query(..., description="ISO date when issued"),
    expiry_date: Optional[str] = Query(None, description="ISO date of expiry"),
    issuing_authority: str = Query("Unknown", description="Issuing authority"),
    certificate_number: Optional[str] = Query(None, description="Certificate number"),
    _perm: None = Depends(_require_perm),
) -> InvestigatorCertification:
    """Add a new certification."""
    svc = get_investigator_management_service()
    if svc.get_investigator(investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")

    cert = InvestigatorCertification(
        id=f"cert-{uuid.uuid4().hex[:8]}",
        investigator_id=investigator_id,
        certification_type=certification_type,
        issued_date=issued_date,
        expiry_date=expiry_date,
        status=TrainingStatus.COMPLETED,
        issuing_authority=issuing_authority,
        certificate_number=certificate_number,
    )
    return svc.add_certification(cert)


# ---------------------------------------------------------------------------
# Scorecards
# ---------------------------------------------------------------------------


@router.get(
    "/scorecards/detail/{scorecard_id}",
    response_model=InvestigatorScorecard,
    summary="Get scorecard detail",
    description="Get a specific scorecard by ID.",
)
async def get_scorecard_detail(
    scorecard_id: str,
    _perm: None = Depends(_require_perm),
) -> InvestigatorScorecard:
    """Return a scorecard by ID."""
    svc = get_investigator_management_service()
    sc = svc.get_scorecard(scorecard_id)
    if sc is None:
        raise HTTPException(status_code=404, detail=f"Scorecard {scorecard_id} not found")
    return sc


@router.get(
    "/scorecards/compare/{investigator_id}",
    response_model=list[InvestigatorScorecard],
    summary="Compare scorecards",
    description="Get historical scorecards for an investigator for comparison.",
)
async def compare_scorecards(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> list[InvestigatorScorecard]:
    """Return scorecards sorted by period for historical comparison."""
    svc = get_investigator_management_service()
    if svc.get_investigator(investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return svc.compare_scorecards(investigator_id)


@router.get(
    "/scorecards/{investigator_id}",
    response_model=ScorecardListResponse,
    summary="List scorecards",
    description="List all scorecards for an investigator.",
)
async def list_scorecards(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> ScorecardListResponse:
    """Return scorecards for an investigator."""
    svc = get_investigator_management_service()
    if svc.get_investigator(investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return svc.get_scorecards(investigator_id)


@router.post(
    "/scorecards",
    response_model=InvestigatorScorecard,
    summary="Create scorecard",
    description="Create a new performance scorecard.",
    status_code=201,
)
async def create_scorecard(
    req: ScorecardCreateRequest,
    _perm: None = Depends(_require_perm),
) -> InvestigatorScorecard:
    """Create a new scorecard."""
    svc = get_investigator_management_service()
    if svc.get_investigator(req.investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {req.investigator_id} not found")
    return svc.create_scorecard(req)


# ---------------------------------------------------------------------------
# Performance rankings
# ---------------------------------------------------------------------------


@router.get(
    "/rankings",
    response_model=PerformanceRankingResponse,
    summary="Performance rankings",
    description="Rank investigators by performance score.",
)
async def get_rankings(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    _perm: None = Depends(_require_perm),
) -> PerformanceRankingResponse:
    """Return ranked investigators."""
    svc = get_investigator_management_service()
    return svc.get_performance_rankings(limit=limit)


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------


@router.get(
    "/inspections",
    response_model=list[InspectionRecord],
    summary="List inspections",
    description="List all inspection records, optionally filtered by investigator.",
)
async def list_inspections(
    investigator_id: Optional[str] = Query(None, description="Filter by investigator ID"),
    _perm: None = Depends(_require_perm),
) -> list[InspectionRecord]:
    """Return inspection records."""
    svc = get_investigator_management_service()
    return svc.get_inspections(investigator_id)


@router.get(
    "/inspections/{inspection_id}",
    response_model=InspectionRecord,
    summary="Get inspection",
    description="Get a single inspection record by ID.",
)
async def get_inspection(
    inspection_id: str,
    _perm: None = Depends(_require_perm),
) -> InspectionRecord:
    """Return an inspection by ID."""
    svc = get_investigator_management_service()
    insp = svc.get_inspection(inspection_id)
    if insp is None:
        raise HTTPException(status_code=404, detail=f"Inspection {inspection_id} not found")
    return insp


@router.post(
    "/inspections",
    response_model=InspectionRecord,
    summary="Create inspection",
    description="Create a new inspection record.",
    status_code=201,
)
async def create_inspection(
    req: InspectionCreateRequest,
    _perm: None = Depends(_require_perm),
) -> InspectionRecord:
    """Create a new inspection record."""
    svc = get_investigator_management_service()
    if svc.get_investigator(req.investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {req.investigator_id} not found")
    return svc.create_inspection(req)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


@router.get(
    "/training/gap-analysis/{investigator_id}",
    response_model=TrainingGapAnalysis,
    summary="Training gap analysis",
    description="Analyze training gaps for an investigator.",
)
async def get_training_gap_analysis(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> TrainingGapAnalysis:
    """Return training gap analysis."""
    svc = get_investigator_management_service()
    analysis = svc.get_training_gap_analysis(investigator_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return analysis


@router.get(
    "/training/{investigator_id}",
    response_model=list[TrainingRecord],
    summary="List training records",
    description="List all training records for an investigator.",
)
async def list_training_records(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> list[TrainingRecord]:
    """Return training records for an investigator."""
    svc = get_investigator_management_service()
    if svc.get_investigator(investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return svc.get_training_records(investigator_id)


@router.post(
    "/training",
    response_model=TrainingRecord,
    summary="Create training record",
    description="Create a new training record.",
    status_code=201,
)
async def create_training_record(
    req: TrainingCreateRequest,
    _perm: None = Depends(_require_perm),
) -> TrainingRecord:
    """Create a new training record."""
    svc = get_investigator_management_service()
    if svc.get_investigator(req.investigator_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigator {req.investigator_id} not found")
    return svc.create_training_record(req)


# ---------------------------------------------------------------------------
# Workload
# ---------------------------------------------------------------------------


@router.get(
    "/workload-report",
    response_model=WorkloadReport,
    summary="Workload report",
    description="Full workload analysis across all investigators.",
)
async def get_workload_report(
    _perm: None = Depends(_require_perm),
) -> WorkloadReport:
    """Return workload report for all investigators."""
    svc = get_investigator_management_service()
    return svc.get_workload_report()


@router.get(
    "/workload/{investigator_id}",
    response_model=InvestigatorWorkload,
    summary="Get workload",
    description="Get workload metrics for an investigator.",
)
async def get_workload(
    investigator_id: str,
    _perm: None = Depends(_require_perm),
) -> InvestigatorWorkload:
    """Return workload for an investigator."""
    svc = get_investigator_management_service()
    wl = svc.get_workload(investigator_id)
    if wl is None:
        raise HTTPException(status_code=404, detail=f"Investigator {investigator_id} not found")
    return wl


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@router.get(
    "/match",
    response_model=list[InvestigatorMatchResult],
    summary="Find available investigators",
    description="Find investigators with capacity for new trial assignments.",
)
async def find_available_investigators(
    min_performance: float = Query(70.0, ge=0.0, le=100.0, description="Minimum performance score"),
    specialty: Optional[str] = Query(None, description="Filter by specialty"),
    max_results: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    _perm: None = Depends(_require_perm),
) -> list[InvestigatorMatchResult]:
    """Find investigators available for new trial assignments."""
    svc = get_investigator_management_service()
    return svc.find_available_investigators(
        min_performance=min_performance,
        specialty=specialty,
        max_results=max_results,
    )


# ---------------------------------------------------------------------------
# Metrics and stats
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=InvestigatorMetrics,
    summary="Aggregate metrics",
    description="Return aggregate investigator performance metrics.",
)
async def get_metrics(
    _perm: None = Depends(_require_perm),
) -> InvestigatorMetrics:
    """Return aggregate metrics."""
    svc = get_investigator_management_service()
    return svc.get_metrics()


@router.get(
    "/stats",
    summary="Service health stats",
    description="Return service health statistics.",
)
async def get_stats(
    _perm: None = Depends(_require_perm),
) -> dict:
    """Return service stats."""
    svc = get_investigator_management_service()
    return svc.get_stats()
