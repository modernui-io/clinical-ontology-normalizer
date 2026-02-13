"""Post-Marketing Surveillance (PMS) API endpoints.

Provides comprehensive post-marketing surveillance operations: safety signal
tracking, periodic safety update reports (PSURs), risk management plan updates,
product quality review, and post-marketing commitment tracking with PMS metrics.

Endpoints:
    GET    /post-marketing-surveillance/safety-signals                         - List safety signals
    GET    /post-marketing-surveillance/safety-signals/{signal_id}             - Get single signal
    POST   /post-marketing-surveillance/safety-signals                         - Create signal
    PUT    /post-marketing-surveillance/safety-signals/{signal_id}             - Update signal
    DELETE /post-marketing-surveillance/safety-signals/{signal_id}             - Delete signal
    GET    /post-marketing-surveillance/psur-records                           - List PSUR records
    GET    /post-marketing-surveillance/psur-records/{psur_id}                 - Get single PSUR
    POST   /post-marketing-surveillance/psur-records                           - Create PSUR
    PUT    /post-marketing-surveillance/psur-records/{psur_id}                 - Update PSUR
    DELETE /post-marketing-surveillance/psur-records/{psur_id}                 - Delete PSUR
    GET    /post-marketing-surveillance/risk-management-plans                  - List risk plans
    GET    /post-marketing-surveillance/risk-management-plans/{plan_id}        - Get single plan
    POST   /post-marketing-surveillance/risk-management-plans                  - Create plan
    PUT    /post-marketing-surveillance/risk-management-plans/{plan_id}        - Update plan
    DELETE /post-marketing-surveillance/risk-management-plans/{plan_id}        - Delete plan
    GET    /post-marketing-surveillance/product-quality-reviews                - List reviews
    GET    /post-marketing-surveillance/product-quality-reviews/{review_id}    - Get single review
    POST   /post-marketing-surveillance/product-quality-reviews                - Create review
    PUT    /post-marketing-surveillance/product-quality-reviews/{review_id}    - Update review
    DELETE /post-marketing-surveillance/product-quality-reviews/{review_id}    - Delete review
    GET    /post-marketing-surveillance/commitments                            - List commitments
    GET    /post-marketing-surveillance/commitments/{commitment_id}            - Get single commitment
    POST   /post-marketing-surveillance/commitments                            - Create commitment
    PUT    /post-marketing-surveillance/commitments/{commitment_id}            - Update commitment
    DELETE /post-marketing-surveillance/commitments/{commitment_id}            - Delete commitment
    GET    /post-marketing-surveillance/metrics                                - PMS metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.post_marketing_surveillance import (
    CommitmentType,
    PostMarketingCommitment,
    PostMarketingCommitmentCreate,
    PostMarketingCommitmentListResponse,
    PostMarketingCommitmentUpdate,
    PostMarketingSurveillanceMetrics,
    ProductQualityReview,
    ProductQualityReviewCreate,
    ProductQualityReviewListResponse,
    ProductQualityReviewUpdate,
    PSURRecord,
    PSURRecordCreate,
    PSURRecordListResponse,
    PSURRecordUpdate,
    PSURStatus,
    RiskCategory,
    RiskManagementPlan,
    RiskManagementPlanCreate,
    RiskManagementPlanListResponse,
    RiskManagementPlanUpdate,
    SafetySignalTracker,
    SafetySignalTrackerCreate,
    SafetySignalTrackerListResponse,
    SafetySignalTrackerUpdate,
    SignalSource,
    SignalStatus,
)
from app.services.post_marketing_surveillance_service import (
    get_post_marketing_surveillance_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/post-marketing-surveillance",
    tags=["Post-Marketing Surveillance"],
)


# ---------------------------------------------------------------------------
# Safety Signals
# ---------------------------------------------------------------------------


@router.get(
    "/safety-signals",
    response_model=SafetySignalTrackerListResponse,
    summary="List safety signals",
    description="Retrieve safety signals with optional filtering by trial, source, and status.",
)
async def list_safety_signals(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    signal_source: Optional[SignalSource] = Query(None, description="Filter by signal source"),
    status: Optional[SignalStatus] = Query(None, description="Filter by signal status"),
) -> SafetySignalTrackerListResponse:
    svc = get_post_marketing_surveillance_service()
    items = svc.list_safety_signals(
        trial_id=trial_id, signal_source=signal_source, status=status
    )
    return SafetySignalTrackerListResponse(items=items, total=len(items))


@router.get(
    "/safety-signals/{signal_id}",
    response_model=SafetySignalTracker,
    summary="Get a safety signal",
)
async def get_safety_signal(signal_id: str) -> SafetySignalTracker:
    svc = get_post_marketing_surveillance_service()
    signal = svc.get_safety_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Safety signal '{signal_id}' not found")
    return signal


@router.post(
    "/safety-signals",
    response_model=SafetySignalTracker,
    status_code=201,
    summary="Create a safety signal",
)
async def create_safety_signal(payload: SafetySignalTrackerCreate) -> SafetySignalTracker:
    svc = get_post_marketing_surveillance_service()
    return svc.create_safety_signal(payload)


@router.put(
    "/safety-signals/{signal_id}",
    response_model=SafetySignalTracker,
    summary="Update a safety signal",
)
async def update_safety_signal(
    signal_id: str, payload: SafetySignalTrackerUpdate
) -> SafetySignalTracker:
    svc = get_post_marketing_surveillance_service()
    updated = svc.update_safety_signal(signal_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Safety signal '{signal_id}' not found")
    return updated


@router.delete(
    "/safety-signals/{signal_id}",
    status_code=204,
    summary="Delete a safety signal",
)
async def delete_safety_signal(signal_id: str) -> None:
    svc = get_post_marketing_surveillance_service()
    deleted = svc.delete_safety_signal(signal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Safety signal '{signal_id}' not found")


# ---------------------------------------------------------------------------
# PSUR Records
# ---------------------------------------------------------------------------


@router.get(
    "/psur-records",
    response_model=PSURRecordListResponse,
    summary="List PSUR records",
    description="Retrieve PSUR records with optional filtering by trial and status.",
)
async def list_psur_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[PSURStatus] = Query(None, description="Filter by PSUR status"),
) -> PSURRecordListResponse:
    svc = get_post_marketing_surveillance_service()
    items = svc.list_psur_records(trial_id=trial_id, status=status)
    return PSURRecordListResponse(items=items, total=len(items))


@router.get(
    "/psur-records/{psur_id}",
    response_model=PSURRecord,
    summary="Get a PSUR record",
)
async def get_psur_record(psur_id: str) -> PSURRecord:
    svc = get_post_marketing_surveillance_service()
    psur = svc.get_psur_record(psur_id)
    if psur is None:
        raise HTTPException(status_code=404, detail=f"PSUR record '{psur_id}' not found")
    return psur


@router.post(
    "/psur-records",
    response_model=PSURRecord,
    status_code=201,
    summary="Create a PSUR record",
)
async def create_psur_record(payload: PSURRecordCreate) -> PSURRecord:
    svc = get_post_marketing_surveillance_service()
    return svc.create_psur_record(payload)


@router.put(
    "/psur-records/{psur_id}",
    response_model=PSURRecord,
    summary="Update a PSUR record",
)
async def update_psur_record(
    psur_id: str, payload: PSURRecordUpdate
) -> PSURRecord:
    svc = get_post_marketing_surveillance_service()
    updated = svc.update_psur_record(psur_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"PSUR record '{psur_id}' not found")
    return updated


@router.delete(
    "/psur-records/{psur_id}",
    status_code=204,
    summary="Delete a PSUR record",
)
async def delete_psur_record(psur_id: str) -> None:
    svc = get_post_marketing_surveillance_service()
    deleted = svc.delete_psur_record(psur_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"PSUR record '{psur_id}' not found")


# ---------------------------------------------------------------------------
# Risk Management Plans
# ---------------------------------------------------------------------------


@router.get(
    "/risk-management-plans",
    response_model=RiskManagementPlanListResponse,
    summary="List risk management plans",
    description="Retrieve risk management plans with optional filtering by trial and risk category.",
)
async def list_risk_management_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    risk_category: Optional[RiskCategory] = Query(None, description="Filter by risk category"),
) -> RiskManagementPlanListResponse:
    svc = get_post_marketing_surveillance_service()
    items = svc.list_risk_management_plans(
        trial_id=trial_id, risk_category=risk_category
    )
    return RiskManagementPlanListResponse(items=items, total=len(items))


@router.get(
    "/risk-management-plans/{plan_id}",
    response_model=RiskManagementPlan,
    summary="Get a risk management plan",
)
async def get_risk_management_plan(plan_id: str) -> RiskManagementPlan:
    svc = get_post_marketing_surveillance_service()
    plan = svc.get_risk_management_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404, detail=f"Risk management plan '{plan_id}' not found"
        )
    return plan


@router.post(
    "/risk-management-plans",
    response_model=RiskManagementPlan,
    status_code=201,
    summary="Create a risk management plan",
)
async def create_risk_management_plan(
    payload: RiskManagementPlanCreate,
) -> RiskManagementPlan:
    svc = get_post_marketing_surveillance_service()
    return svc.create_risk_management_plan(payload)


@router.put(
    "/risk-management-plans/{plan_id}",
    response_model=RiskManagementPlan,
    summary="Update a risk management plan",
)
async def update_risk_management_plan(
    plan_id: str, payload: RiskManagementPlanUpdate
) -> RiskManagementPlan:
    svc = get_post_marketing_surveillance_service()
    updated = svc.update_risk_management_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Risk management plan '{plan_id}' not found"
        )
    return updated


@router.delete(
    "/risk-management-plans/{plan_id}",
    status_code=204,
    summary="Delete a risk management plan",
)
async def delete_risk_management_plan(plan_id: str) -> None:
    svc = get_post_marketing_surveillance_service()
    deleted = svc.delete_risk_management_plan(plan_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Risk management plan '{plan_id}' not found"
        )


# ---------------------------------------------------------------------------
# Product Quality Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/product-quality-reviews",
    response_model=ProductQualityReviewListResponse,
    summary="List product quality reviews",
    description="Retrieve product quality reviews with optional filtering by trial.",
)
async def list_product_quality_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ProductQualityReviewListResponse:
    svc = get_post_marketing_surveillance_service()
    items = svc.list_product_quality_reviews(trial_id=trial_id)
    return ProductQualityReviewListResponse(items=items, total=len(items))


@router.get(
    "/product-quality-reviews/{review_id}",
    response_model=ProductQualityReview,
    summary="Get a product quality review",
)
async def get_product_quality_review(review_id: str) -> ProductQualityReview:
    svc = get_post_marketing_surveillance_service()
    review = svc.get_product_quality_review(review_id)
    if review is None:
        raise HTTPException(
            status_code=404, detail=f"Product quality review '{review_id}' not found"
        )
    return review


@router.post(
    "/product-quality-reviews",
    response_model=ProductQualityReview,
    status_code=201,
    summary="Create a product quality review",
)
async def create_product_quality_review(
    payload: ProductQualityReviewCreate,
) -> ProductQualityReview:
    svc = get_post_marketing_surveillance_service()
    return svc.create_product_quality_review(payload)


@router.put(
    "/product-quality-reviews/{review_id}",
    response_model=ProductQualityReview,
    summary="Update a product quality review",
)
async def update_product_quality_review(
    review_id: str, payload: ProductQualityReviewUpdate
) -> ProductQualityReview:
    svc = get_post_marketing_surveillance_service()
    updated = svc.update_product_quality_review(review_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Product quality review '{review_id}' not found"
        )
    return updated


@router.delete(
    "/product-quality-reviews/{review_id}",
    status_code=204,
    summary="Delete a product quality review",
)
async def delete_product_quality_review(review_id: str) -> None:
    svc = get_post_marketing_surveillance_service()
    deleted = svc.delete_product_quality_review(review_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Product quality review '{review_id}' not found"
        )


# ---------------------------------------------------------------------------
# Post-Marketing Commitments
# ---------------------------------------------------------------------------


@router.get(
    "/commitments",
    response_model=PostMarketingCommitmentListResponse,
    summary="List post-marketing commitments",
    description="Retrieve post-marketing commitments with optional filtering by trial and commitment type.",
)
async def list_commitments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    commitment_type: Optional[CommitmentType] = Query(
        None, description="Filter by commitment type"
    ),
) -> PostMarketingCommitmentListResponse:
    svc = get_post_marketing_surveillance_service()
    items = svc.list_post_marketing_commitments(
        trial_id=trial_id, commitment_type=commitment_type
    )
    return PostMarketingCommitmentListResponse(items=items, total=len(items))


@router.get(
    "/commitments/{commitment_id}",
    response_model=PostMarketingCommitment,
    summary="Get a post-marketing commitment",
)
async def get_commitment(commitment_id: str) -> PostMarketingCommitment:
    svc = get_post_marketing_surveillance_service()
    commitment = svc.get_post_marketing_commitment(commitment_id)
    if commitment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Post-marketing commitment '{commitment_id}' not found",
        )
    return commitment


@router.post(
    "/commitments",
    response_model=PostMarketingCommitment,
    status_code=201,
    summary="Create a post-marketing commitment",
)
async def create_commitment(
    payload: PostMarketingCommitmentCreate,
) -> PostMarketingCommitment:
    svc = get_post_marketing_surveillance_service()
    return svc.create_post_marketing_commitment(payload)


@router.put(
    "/commitments/{commitment_id}",
    response_model=PostMarketingCommitment,
    summary="Update a post-marketing commitment",
)
async def update_commitment(
    commitment_id: str, payload: PostMarketingCommitmentUpdate
) -> PostMarketingCommitment:
    svc = get_post_marketing_surveillance_service()
    updated = svc.update_post_marketing_commitment(commitment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Post-marketing commitment '{commitment_id}' not found",
        )
    return updated


@router.delete(
    "/commitments/{commitment_id}",
    status_code=204,
    summary="Delete a post-marketing commitment",
)
async def delete_commitment(commitment_id: str) -> None:
    svc = get_post_marketing_surveillance_service()
    deleted = svc.delete_post_marketing_commitment(commitment_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Post-marketing commitment '{commitment_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PostMarketingSurveillanceMetrics,
    summary="Get post-marketing surveillance metrics",
    description="Compute aggregate PMS metrics across all entities with optional trial filter.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PostMarketingSurveillanceMetrics:
    svc = get_post_marketing_surveillance_service()
    return svc.get_metrics(trial_id=trial_id)
