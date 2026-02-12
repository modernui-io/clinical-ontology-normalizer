"""Endpoint Adjudication Committee API endpoints (EAC-MGMT).

Provides comprehensive endpoint adjudication committee operations: committee
member management, case review tracking, adjudication outcomes, charter
management, and blinding compliance with committee metrics.

Endpoints:
    GET    /endpoint-adjudication-committee/committee-members                       - List members
    GET    /endpoint-adjudication-committee/committee-members/{member_id}            - Get single member
    POST   /endpoint-adjudication-committee/committee-members                       - Create member
    PUT    /endpoint-adjudication-committee/committee-members/{member_id}            - Update member
    DELETE /endpoint-adjudication-committee/committee-members/{member_id}            - Delete member
    GET    /endpoint-adjudication-committee/case-reviews                             - List case reviews
    GET    /endpoint-adjudication-committee/case-reviews/{case_id}                   - Get single case
    POST   /endpoint-adjudication-committee/case-reviews                             - Create case review
    PUT    /endpoint-adjudication-committee/case-reviews/{case_id}                   - Update case review
    DELETE /endpoint-adjudication-committee/case-reviews/{case_id}                   - Delete case review
    GET    /endpoint-adjudication-committee/adjudication-results                     - List results
    GET    /endpoint-adjudication-committee/adjudication-results/{result_id}         - Get single result
    POST   /endpoint-adjudication-committee/adjudication-results                     - Create result
    PUT    /endpoint-adjudication-committee/adjudication-results/{result_id}         - Update result
    DELETE /endpoint-adjudication-committee/adjudication-results/{result_id}         - Delete result
    GET    /endpoint-adjudication-committee/charter-records                          - List charters
    GET    /endpoint-adjudication-committee/charter-records/{charter_id}             - Get single charter
    POST   /endpoint-adjudication-committee/charter-records                          - Create charter
    PUT    /endpoint-adjudication-committee/charter-records/{charter_id}             - Update charter
    DELETE /endpoint-adjudication-committee/charter-records/{charter_id}             - Delete charter
    GET    /endpoint-adjudication-committee/blinding-compliance                      - List blinding records
    GET    /endpoint-adjudication-committee/blinding-compliance/{compliance_id}      - Get single record
    POST   /endpoint-adjudication-committee/blinding-compliance                      - Create record
    PUT    /endpoint-adjudication-committee/blinding-compliance/{compliance_id}      - Update record
    DELETE /endpoint-adjudication-committee/blinding-compliance/{compliance_id}      - Delete record
    GET    /endpoint-adjudication-committee/metrics                                  - EAC metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.endpoint_adjudication_committee import (
    AdjudicationOutcome,
    AdjudicationResult,
    AdjudicationResultCreate,
    AdjudicationResultListResponse,
    AdjudicationResultUpdate,
    BlindingCompliance,
    BlindingComplianceCreate,
    BlindingComplianceListResponse,
    BlindingComplianceUpdate,
    BlindingStatus,
    CaseReview,
    CaseReviewCreate,
    CaseReviewListResponse,
    CaseReviewUpdate,
    CaseStatus,
    CharterRecord,
    CharterRecordCreate,
    CharterRecordListResponse,
    CharterRecordUpdate,
    CharterStatus,
    CommitteeMember,
    CommitteeMemberCreate,
    CommitteeMemberListResponse,
    CommitteeMemberUpdate,
    EndpointAdjudicationMetrics,
    MemberRole,
)
from app.services.endpoint_adjudication_committee_service import (
    get_endpoint_adjudication_committee_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/endpoint-adjudication-committee",
    tags=["Endpoint Adjudication Committee"],
)


# ---------------------------------------------------------------------------
# Committee Members
# ---------------------------------------------------------------------------


@router.get(
    "/committee-members",
    response_model=CommitteeMemberListResponse,
    summary="List committee members",
    description="Retrieve committee members with optional filtering by trial, role, and active status.",
)
async def list_committee_members(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    role: Optional[MemberRole] = Query(None, description="Filter by member role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> CommitteeMemberListResponse:
    svc = get_endpoint_adjudication_committee_service()
    items = svc.list_committee_members(trial_id=trial_id, role=role, is_active=is_active)
    return CommitteeMemberListResponse(items=items, total=len(items))


@router.get(
    "/committee-members/{member_id}",
    response_model=CommitteeMember,
    summary="Get a committee member",
)
async def get_committee_member(member_id: str) -> CommitteeMember:
    svc = get_endpoint_adjudication_committee_service()
    member = svc.get_committee_member(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Committee member '{member_id}' not found")
    return member


@router.post(
    "/committee-members",
    response_model=CommitteeMember,
    status_code=201,
    summary="Create a committee member",
)
async def create_committee_member(payload: CommitteeMemberCreate) -> CommitteeMember:
    svc = get_endpoint_adjudication_committee_service()
    return svc.create_committee_member(payload)


@router.put(
    "/committee-members/{member_id}",
    response_model=CommitteeMember,
    summary="Update a committee member",
)
async def update_committee_member(
    member_id: str, payload: CommitteeMemberUpdate
) -> CommitteeMember:
    svc = get_endpoint_adjudication_committee_service()
    updated = svc.update_committee_member(member_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Committee member '{member_id}' not found")
    return updated


@router.delete(
    "/committee-members/{member_id}",
    status_code=204,
    summary="Delete a committee member",
)
async def delete_committee_member(member_id: str) -> None:
    svc = get_endpoint_adjudication_committee_service()
    deleted = svc.delete_committee_member(member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Committee member '{member_id}' not found")


# ---------------------------------------------------------------------------
# Case Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/case-reviews",
    response_model=CaseReviewListResponse,
    summary="List case reviews",
    description="Retrieve case reviews with optional filtering by trial and status.",
)
async def list_case_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[CaseStatus] = Query(None, description="Filter by case status"),
) -> CaseReviewListResponse:
    svc = get_endpoint_adjudication_committee_service()
    items = svc.list_case_reviews(trial_id=trial_id, status=status)
    return CaseReviewListResponse(items=items, total=len(items))


@router.get(
    "/case-reviews/{case_id}",
    response_model=CaseReview,
    summary="Get a case review",
)
async def get_case_review(case_id: str) -> CaseReview:
    svc = get_endpoint_adjudication_committee_service()
    case = svc.get_case_review(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case review '{case_id}' not found")
    return case


@router.post(
    "/case-reviews",
    response_model=CaseReview,
    status_code=201,
    summary="Create a case review",
)
async def create_case_review(payload: CaseReviewCreate) -> CaseReview:
    svc = get_endpoint_adjudication_committee_service()
    return svc.create_case_review(payload)


@router.put(
    "/case-reviews/{case_id}",
    response_model=CaseReview,
    summary="Update a case review",
)
async def update_case_review(
    case_id: str, payload: CaseReviewUpdate
) -> CaseReview:
    svc = get_endpoint_adjudication_committee_service()
    updated = svc.update_case_review(case_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Case review '{case_id}' not found")
    return updated


@router.delete(
    "/case-reviews/{case_id}",
    status_code=204,
    summary="Delete a case review",
)
async def delete_case_review(case_id: str) -> None:
    svc = get_endpoint_adjudication_committee_service()
    deleted = svc.delete_case_review(case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Case review '{case_id}' not found")


# ---------------------------------------------------------------------------
# Adjudication Results
# ---------------------------------------------------------------------------


@router.get(
    "/adjudication-results",
    response_model=AdjudicationResultListResponse,
    summary="List adjudication results",
    description="Retrieve adjudication results with optional filtering by trial and outcome.",
)
async def list_adjudication_results(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    outcome: Optional[AdjudicationOutcome] = Query(None, description="Filter by outcome"),
) -> AdjudicationResultListResponse:
    svc = get_endpoint_adjudication_committee_service()
    items = svc.list_adjudication_results(trial_id=trial_id, outcome=outcome)
    return AdjudicationResultListResponse(items=items, total=len(items))


@router.get(
    "/adjudication-results/{result_id}",
    response_model=AdjudicationResult,
    summary="Get an adjudication result",
)
async def get_adjudication_result(result_id: str) -> AdjudicationResult:
    svc = get_endpoint_adjudication_committee_service()
    result = svc.get_adjudication_result(result_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Adjudication result '{result_id}' not found"
        )
    return result


@router.post(
    "/adjudication-results",
    response_model=AdjudicationResult,
    status_code=201,
    summary="Create an adjudication result",
)
async def create_adjudication_result(payload: AdjudicationResultCreate) -> AdjudicationResult:
    svc = get_endpoint_adjudication_committee_service()
    return svc.create_adjudication_result(payload)


@router.put(
    "/adjudication-results/{result_id}",
    response_model=AdjudicationResult,
    summary="Update an adjudication result",
)
async def update_adjudication_result(
    result_id: str, payload: AdjudicationResultUpdate
) -> AdjudicationResult:
    svc = get_endpoint_adjudication_committee_service()
    updated = svc.update_adjudication_result(result_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Adjudication result '{result_id}' not found"
        )
    return updated


@router.delete(
    "/adjudication-results/{result_id}",
    status_code=204,
    summary="Delete an adjudication result",
)
async def delete_adjudication_result(result_id: str) -> None:
    svc = get_endpoint_adjudication_committee_service()
    deleted = svc.delete_adjudication_result(result_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Adjudication result '{result_id}' not found"
        )


# ---------------------------------------------------------------------------
# Charter Records
# ---------------------------------------------------------------------------


@router.get(
    "/charter-records",
    response_model=CharterRecordListResponse,
    summary="List charter records",
    description="Retrieve charter records with optional filtering by trial and status.",
)
async def list_charter_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[CharterStatus] = Query(None, description="Filter by charter status"),
) -> CharterRecordListResponse:
    svc = get_endpoint_adjudication_committee_service()
    items = svc.list_charter_records(trial_id=trial_id, status=status)
    return CharterRecordListResponse(items=items, total=len(items))


@router.get(
    "/charter-records/{charter_id}",
    response_model=CharterRecord,
    summary="Get a charter record",
)
async def get_charter_record(charter_id: str) -> CharterRecord:
    svc = get_endpoint_adjudication_committee_service()
    charter = svc.get_charter_record(charter_id)
    if charter is None:
        raise HTTPException(
            status_code=404, detail=f"Charter record '{charter_id}' not found"
        )
    return charter


@router.post(
    "/charter-records",
    response_model=CharterRecord,
    status_code=201,
    summary="Create a charter record",
)
async def create_charter_record(payload: CharterRecordCreate) -> CharterRecord:
    svc = get_endpoint_adjudication_committee_service()
    return svc.create_charter_record(payload)


@router.put(
    "/charter-records/{charter_id}",
    response_model=CharterRecord,
    summary="Update a charter record",
)
async def update_charter_record(
    charter_id: str, payload: CharterRecordUpdate
) -> CharterRecord:
    svc = get_endpoint_adjudication_committee_service()
    updated = svc.update_charter_record(charter_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Charter record '{charter_id}' not found"
        )
    return updated


@router.delete(
    "/charter-records/{charter_id}",
    status_code=204,
    summary="Delete a charter record",
)
async def delete_charter_record(charter_id: str) -> None:
    svc = get_endpoint_adjudication_committee_service()
    deleted = svc.delete_charter_record(charter_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Charter record '{charter_id}' not found"
        )


# ---------------------------------------------------------------------------
# Blinding Compliance
# ---------------------------------------------------------------------------


@router.get(
    "/blinding-compliance",
    response_model=BlindingComplianceListResponse,
    summary="List blinding compliance records",
    description="Retrieve blinding compliance records with optional filtering by trial and status.",
)
async def list_blinding_compliance(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    blinding_status: Optional[BlindingStatus] = Query(
        None, description="Filter by blinding status"
    ),
) -> BlindingComplianceListResponse:
    svc = get_endpoint_adjudication_committee_service()
    items = svc.list_blinding_compliance(
        trial_id=trial_id, blinding_status=blinding_status
    )
    return BlindingComplianceListResponse(items=items, total=len(items))


@router.get(
    "/blinding-compliance/{compliance_id}",
    response_model=BlindingCompliance,
    summary="Get a blinding compliance record",
)
async def get_blinding_compliance(compliance_id: str) -> BlindingCompliance:
    svc = get_endpoint_adjudication_committee_service()
    compliance = svc.get_blinding_compliance(compliance_id)
    if compliance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Blinding compliance record '{compliance_id}' not found",
        )
    return compliance


@router.post(
    "/blinding-compliance",
    response_model=BlindingCompliance,
    status_code=201,
    summary="Create a blinding compliance record",
)
async def create_blinding_compliance(
    payload: BlindingComplianceCreate,
) -> BlindingCompliance:
    svc = get_endpoint_adjudication_committee_service()
    return svc.create_blinding_compliance(payload)


@router.put(
    "/blinding-compliance/{compliance_id}",
    response_model=BlindingCompliance,
    summary="Update a blinding compliance record",
)
async def update_blinding_compliance(
    compliance_id: str, payload: BlindingComplianceUpdate
) -> BlindingCompliance:
    svc = get_endpoint_adjudication_committee_service()
    updated = svc.update_blinding_compliance(compliance_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Blinding compliance record '{compliance_id}' not found",
        )
    return updated


@router.delete(
    "/blinding-compliance/{compliance_id}",
    status_code=204,
    summary="Delete a blinding compliance record",
)
async def delete_blinding_compliance(compliance_id: str) -> None:
    svc = get_endpoint_adjudication_committee_service()
    deleted = svc.delete_blinding_compliance(compliance_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Blinding compliance record '{compliance_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=EndpointAdjudicationMetrics,
    summary="Get endpoint adjudication committee metrics",
    description="Aggregated metrics across all endpoint adjudication committee operations.",
)
async def get_metrics() -> EndpointAdjudicationMetrics:
    svc = get_endpoint_adjudication_committee_service()
    return svc.get_metrics()
