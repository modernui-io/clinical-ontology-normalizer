"""Patient Insurance Verification (PIV-VER) API endpoints.

Manages patient insurance verification operations: eligibility checks,
pre-authorization requests, coverage determinations, reimbursement tracking,
and aggregated metrics across clinical trials.

Endpoints:
    GET    /patient-insurance-verification/eligibility-checks                    - List eligibility checks
    GET    /patient-insurance-verification/eligibility-checks/{check_id}         - Get single eligibility check
    POST   /patient-insurance-verification/eligibility-checks                    - Create eligibility check
    PUT    /patient-insurance-verification/eligibility-checks/{check_id}         - Update eligibility check
    DELETE /patient-insurance-verification/eligibility-checks/{check_id}         - Delete eligibility check
    GET    /patient-insurance-verification/pre-authorization-requests            - List pre-auth requests
    GET    /patient-insurance-verification/pre-authorization-requests/{id}       - Get single pre-auth request
    POST   /patient-insurance-verification/pre-authorization-requests            - Create pre-auth request
    PUT    /patient-insurance-verification/pre-authorization-requests/{id}       - Update pre-auth request
    DELETE /patient-insurance-verification/pre-authorization-requests/{id}       - Delete pre-auth request
    GET    /patient-insurance-verification/coverage-determinations               - List coverage determinations
    GET    /patient-insurance-verification/coverage-determinations/{id}          - Get single coverage determination
    POST   /patient-insurance-verification/coverage-determinations               - Create coverage determination
    PUT    /patient-insurance-verification/coverage-determinations/{id}          - Update coverage determination
    DELETE /patient-insurance-verification/coverage-determinations/{id}          - Delete coverage determination
    GET    /patient-insurance-verification/reimbursement-trackings               - List reimbursement trackings
    GET    /patient-insurance-verification/reimbursement-trackings/{id}          - Get single reimbursement tracking
    POST   /patient-insurance-verification/reimbursement-trackings               - Create reimbursement tracking
    PUT    /patient-insurance-verification/reimbursement-trackings/{id}          - Update reimbursement tracking
    DELETE /patient-insurance-verification/reimbursement-trackings/{id}          - Delete reimbursement tracking
    GET    /patient-insurance-verification/metrics                               - Get aggregated metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_insurance_verification import (
    CoverageDetermination,
    CoverageDeterminationCreate,
    CoverageDeterminationListResponse,
    CoverageDeterminationUpdate,
    EligibilityCheck,
    EligibilityCheckCreate,
    EligibilityCheckListResponse,
    EligibilityCheckUpdate,
    PatientInsuranceVerificationMetrics,
    PreAuthorizationRequest,
    PreAuthorizationRequestCreate,
    PreAuthorizationRequestListResponse,
    PreAuthorizationRequestUpdate,
    ReimbursementTracking,
    ReimbursementTrackingCreate,
    ReimbursementTrackingListResponse,
    ReimbursementTrackingUpdate,
)
from app.services.patient_insurance_verification_service import (
    get_patient_insurance_verification_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-insurance-verification",
    tags=["Patient Insurance Verification"],
)


# ---------------------------------------------------------------------------
# Eligibility Checks
# ---------------------------------------------------------------------------


@router.get(
    "/eligibility-checks",
    response_model=EligibilityCheckListResponse,
    summary="List eligibility checks",
    description="Retrieve eligibility checks with optional filtering by trial ID.",
)
async def list_eligibility_checks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> EligibilityCheckListResponse:
    svc = get_patient_insurance_verification_service()
    items = svc.list_eligibility_checks(trial_id=trial_id)
    return EligibilityCheckListResponse(items=items, total=len(items))


@router.get(
    "/eligibility-checks/{check_id}",
    response_model=EligibilityCheck,
    summary="Get an eligibility check",
)
async def get_eligibility_check(check_id: str) -> EligibilityCheck:
    svc = get_patient_insurance_verification_service()
    check = svc.get_eligibility_check(check_id)
    if check is None:
        raise HTTPException(status_code=404, detail=f"Eligibility check '{check_id}' not found")
    return check


@router.post(
    "/eligibility-checks",
    response_model=EligibilityCheck,
    status_code=201,
    summary="Create an eligibility check",
)
async def create_eligibility_check(payload: EligibilityCheckCreate) -> EligibilityCheck:
    svc = get_patient_insurance_verification_service()
    return svc.create_eligibility_check(payload)


@router.put(
    "/eligibility-checks/{check_id}",
    response_model=EligibilityCheck,
    summary="Update an eligibility check",
)
async def update_eligibility_check(
    check_id: str, payload: EligibilityCheckUpdate
) -> EligibilityCheck:
    svc = get_patient_insurance_verification_service()
    updated = svc.update_eligibility_check(check_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Eligibility check '{check_id}' not found")
    return updated


@router.delete(
    "/eligibility-checks/{check_id}",
    status_code=204,
    summary="Delete an eligibility check",
)
async def delete_eligibility_check(check_id: str) -> None:
    svc = get_patient_insurance_verification_service()
    deleted = svc.delete_eligibility_check(check_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Eligibility check '{check_id}' not found")


# ---------------------------------------------------------------------------
# Pre-Authorization Requests
# ---------------------------------------------------------------------------


@router.get(
    "/pre-authorization-requests",
    response_model=PreAuthorizationRequestListResponse,
    summary="List pre-authorization requests",
    description="Retrieve pre-authorization requests with optional filtering by trial ID.",
)
async def list_pre_authorization_requests(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PreAuthorizationRequestListResponse:
    svc = get_patient_insurance_verification_service()
    items = svc.list_pre_authorization_requests(trial_id=trial_id)
    return PreAuthorizationRequestListResponse(items=items, total=len(items))


@router.get(
    "/pre-authorization-requests/{request_id}",
    response_model=PreAuthorizationRequest,
    summary="Get a pre-authorization request",
)
async def get_pre_authorization_request(request_id: str) -> PreAuthorizationRequest:
    svc = get_patient_insurance_verification_service()
    request = svc.get_pre_authorization_request(request_id)
    if request is None:
        raise HTTPException(
            status_code=404, detail=f"Pre-authorization request '{request_id}' not found"
        )
    return request


@router.post(
    "/pre-authorization-requests",
    response_model=PreAuthorizationRequest,
    status_code=201,
    summary="Create a pre-authorization request",
)
async def create_pre_authorization_request(
    payload: PreAuthorizationRequestCreate,
) -> PreAuthorizationRequest:
    svc = get_patient_insurance_verification_service()
    return svc.create_pre_authorization_request(payload)


@router.put(
    "/pre-authorization-requests/{request_id}",
    response_model=PreAuthorizationRequest,
    summary="Update a pre-authorization request",
)
async def update_pre_authorization_request(
    request_id: str, payload: PreAuthorizationRequestUpdate
) -> PreAuthorizationRequest:
    svc = get_patient_insurance_verification_service()
    updated = svc.update_pre_authorization_request(request_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Pre-authorization request '{request_id}' not found"
        )
    return updated


@router.delete(
    "/pre-authorization-requests/{request_id}",
    status_code=204,
    summary="Delete a pre-authorization request",
)
async def delete_pre_authorization_request(request_id: str) -> None:
    svc = get_patient_insurance_verification_service()
    deleted = svc.delete_pre_authorization_request(request_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Pre-authorization request '{request_id}' not found"
        )


# ---------------------------------------------------------------------------
# Coverage Determinations
# ---------------------------------------------------------------------------


@router.get(
    "/coverage-determinations",
    response_model=CoverageDeterminationListResponse,
    summary="List coverage determinations",
    description="Retrieve coverage determinations with optional filtering by trial ID.",
)
async def list_coverage_determinations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CoverageDeterminationListResponse:
    svc = get_patient_insurance_verification_service()
    items = svc.list_coverage_determinations(trial_id=trial_id)
    return CoverageDeterminationListResponse(items=items, total=len(items))


@router.get(
    "/coverage-determinations/{determination_id}",
    response_model=CoverageDetermination,
    summary="Get a coverage determination",
)
async def get_coverage_determination(determination_id: str) -> CoverageDetermination:
    svc = get_patient_insurance_verification_service()
    determination = svc.get_coverage_determination(determination_id)
    if determination is None:
        raise HTTPException(
            status_code=404,
            detail=f"Coverage determination '{determination_id}' not found",
        )
    return determination


@router.post(
    "/coverage-determinations",
    response_model=CoverageDetermination,
    status_code=201,
    summary="Create a coverage determination",
)
async def create_coverage_determination(
    payload: CoverageDeterminationCreate,
) -> CoverageDetermination:
    svc = get_patient_insurance_verification_service()
    return svc.create_coverage_determination(payload)


@router.put(
    "/coverage-determinations/{determination_id}",
    response_model=CoverageDetermination,
    summary="Update a coverage determination",
)
async def update_coverage_determination(
    determination_id: str, payload: CoverageDeterminationUpdate
) -> CoverageDetermination:
    svc = get_patient_insurance_verification_service()
    updated = svc.update_coverage_determination(determination_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Coverage determination '{determination_id}' not found",
        )
    return updated


@router.delete(
    "/coverage-determinations/{determination_id}",
    status_code=204,
    summary="Delete a coverage determination",
)
async def delete_coverage_determination(determination_id: str) -> None:
    svc = get_patient_insurance_verification_service()
    deleted = svc.delete_coverage_determination(determination_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Coverage determination '{determination_id}' not found",
        )


# ---------------------------------------------------------------------------
# Reimbursement Trackings
# ---------------------------------------------------------------------------


@router.get(
    "/reimbursement-trackings",
    response_model=ReimbursementTrackingListResponse,
    summary="List reimbursement trackings",
    description="Retrieve reimbursement trackings with optional filtering by trial ID.",
)
async def list_reimbursement_trackings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ReimbursementTrackingListResponse:
    svc = get_patient_insurance_verification_service()
    items = svc.list_reimbursement_trackings(trial_id=trial_id)
    return ReimbursementTrackingListResponse(items=items, total=len(items))


@router.get(
    "/reimbursement-trackings/{tracking_id}",
    response_model=ReimbursementTracking,
    summary="Get a reimbursement tracking",
)
async def get_reimbursement_tracking(tracking_id: str) -> ReimbursementTracking:
    svc = get_patient_insurance_verification_service()
    tracking = svc.get_reimbursement_tracking(tracking_id)
    if tracking is None:
        raise HTTPException(
            status_code=404, detail=f"Reimbursement tracking '{tracking_id}' not found"
        )
    return tracking


@router.post(
    "/reimbursement-trackings",
    response_model=ReimbursementTracking,
    status_code=201,
    summary="Create a reimbursement tracking",
)
async def create_reimbursement_tracking(
    payload: ReimbursementTrackingCreate,
) -> ReimbursementTracking:
    svc = get_patient_insurance_verification_service()
    return svc.create_reimbursement_tracking(payload)


@router.put(
    "/reimbursement-trackings/{tracking_id}",
    response_model=ReimbursementTracking,
    summary="Update a reimbursement tracking",
)
async def update_reimbursement_tracking(
    tracking_id: str, payload: ReimbursementTrackingUpdate
) -> ReimbursementTracking:
    svc = get_patient_insurance_verification_service()
    updated = svc.update_reimbursement_tracking(tracking_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Reimbursement tracking '{tracking_id}' not found"
        )
    return updated


@router.delete(
    "/reimbursement-trackings/{tracking_id}",
    status_code=204,
    summary="Delete a reimbursement tracking",
)
async def delete_reimbursement_tracking(tracking_id: str) -> None:
    svc = get_patient_insurance_verification_service()
    deleted = svc.delete_reimbursement_tracking(tracking_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Reimbursement tracking '{tracking_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PatientInsuranceVerificationMetrics,
    summary="Get patient insurance verification metrics",
    description="Aggregated insurance verification metrics with optional trial ID filter.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PatientInsuranceVerificationMetrics:
    svc = get_patient_insurance_verification_service()
    return svc.get_metrics(trial_id=trial_id)
