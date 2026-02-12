"""Clinical Trial Agreement Management (CTA-MGT) API endpoints.

Provides comprehensive agreement management operations: clinical trial agreements,
confidentiality agreements, budget negotiations, site contract execution, amendment
tracking, contract milestones, and agreement operational metrics.

Endpoints:
    GET    /clinical-trial-agreement/agreements                          - List agreements
    GET    /clinical-trial-agreement/agreements/{agreement_id}           - Get single agreement
    POST   /clinical-trial-agreement/agreements                          - Create agreement
    PUT    /clinical-trial-agreement/agreements/{agreement_id}           - Update agreement
    DELETE /clinical-trial-agreement/agreements/{agreement_id}           - Delete agreement
    GET    /clinical-trial-agreement/negotiations                        - List negotiations
    GET    /clinical-trial-agreement/negotiations/{negotiation_id}       - Get single negotiation
    POST   /clinical-trial-agreement/negotiations                        - Create negotiation
    PUT    /clinical-trial-agreement/negotiations/{negotiation_id}       - Update negotiation
    DELETE /clinical-trial-agreement/negotiations/{negotiation_id}       - Delete negotiation
    GET    /clinical-trial-agreement/line-items                          - List budget line items
    GET    /clinical-trial-agreement/line-items/{line_item_id}           - Get single line item
    POST   /clinical-trial-agreement/line-items                          - Create line item
    PUT    /clinical-trial-agreement/line-items/{line_item_id}           - Update line item
    DELETE /clinical-trial-agreement/line-items/{line_item_id}           - Delete line item
    GET    /clinical-trial-agreement/amendments                          - List amendments
    GET    /clinical-trial-agreement/amendments/{amendment_id}           - Get single amendment
    POST   /clinical-trial-agreement/amendments                          - Create amendment
    PUT    /clinical-trial-agreement/amendments/{amendment_id}           - Update amendment
    DELETE /clinical-trial-agreement/amendments/{amendment_id}           - Delete amendment
    GET    /clinical-trial-agreement/milestones                          - List milestones
    GET    /clinical-trial-agreement/milestones/{milestone_id}           - Get single milestone
    POST   /clinical-trial-agreement/milestones                          - Create milestone
    PUT    /clinical-trial-agreement/milestones/{milestone_id}           - Update milestone
    DELETE /clinical-trial-agreement/milestones/{milestone_id}           - Delete milestone
    GET    /clinical-trial-agreement/metrics                             - Agreement metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_trial_agreement import (
    Agreement,
    AgreementAmendment,
    AgreementAmendmentCreate,
    AgreementAmendmentListResponse,
    AgreementAmendmentUpdate,
    AgreementCreate,
    AgreementListResponse,
    AgreementStatus,
    AgreementType,
    AgreementUpdate,
    BudgetLineItem,
    BudgetLineItemCreate,
    BudgetLineItemListResponse,
    BudgetLineItemUpdate,
    ClinicalTrialAgreementMetrics,
    ContractMilestone,
    ContractMilestoneCreate,
    ContractMilestoneListResponse,
    ContractMilestoneUpdate,
    NegotiationRecord,
    NegotiationRecordCreate,
    NegotiationRecordListResponse,
    NegotiationRecordUpdate,
)
from app.services.clinical_trial_agreement_service import (
    get_clinical_trial_agreement_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-trial-agreement",
    tags=["Clinical Trial Agreement Management"],
)


# ---------------------------------------------------------------------------
# Agreements
# ---------------------------------------------------------------------------


@router.get(
    "/agreements",
    response_model=AgreementListResponse,
    summary="List agreements",
    description="Retrieve agreements with optional filtering by trial, status, and type.",
)
async def list_agreements(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AgreementStatus] = Query(None, description="Filter by status"),
    agreement_type: Optional[AgreementType] = Query(None, description="Filter by agreement type"),
) -> AgreementListResponse:
    svc = get_clinical_trial_agreement_service()
    items = svc.list_agreements(trial_id=trial_id, status=status, agreement_type=agreement_type)
    return AgreementListResponse(items=items, total=len(items))


@router.get(
    "/agreements/{agreement_id}",
    response_model=Agreement,
    summary="Get an agreement",
)
async def get_agreement(agreement_id: str) -> Agreement:
    svc = get_clinical_trial_agreement_service()
    agreement = svc.get_agreement(agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")
    return agreement


@router.post(
    "/agreements",
    response_model=Agreement,
    status_code=201,
    summary="Create an agreement",
)
async def create_agreement(payload: AgreementCreate) -> Agreement:
    svc = get_clinical_trial_agreement_service()
    return svc.create_agreement(payload)


@router.put(
    "/agreements/{agreement_id}",
    response_model=Agreement,
    summary="Update an agreement",
)
async def update_agreement(
    agreement_id: str, payload: AgreementUpdate
) -> Agreement:
    svc = get_clinical_trial_agreement_service()
    updated = svc.update_agreement(agreement_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")
    return updated


@router.delete(
    "/agreements/{agreement_id}",
    status_code=204,
    summary="Delete an agreement",
)
async def delete_agreement(agreement_id: str) -> None:
    svc = get_clinical_trial_agreement_service()
    deleted = svc.delete_agreement(agreement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")


# ---------------------------------------------------------------------------
# Negotiation Records
# ---------------------------------------------------------------------------


@router.get(
    "/negotiations",
    response_model=NegotiationRecordListResponse,
    summary="List negotiation records",
    description="Retrieve negotiation records with optional filtering by agreement and resolution status.",
)
async def list_negotiations(
    agreement_id: Optional[str] = Query(None, description="Filter by agreement ID"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
) -> NegotiationRecordListResponse:
    svc = get_clinical_trial_agreement_service()
    items = svc.list_negotiations(agreement_id=agreement_id, resolved=resolved)
    return NegotiationRecordListResponse(items=items, total=len(items))


@router.get(
    "/negotiations/{negotiation_id}",
    response_model=NegotiationRecord,
    summary="Get a negotiation record",
)
async def get_negotiation(negotiation_id: str) -> NegotiationRecord:
    svc = get_clinical_trial_agreement_service()
    record = svc.get_negotiation(negotiation_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Negotiation '{negotiation_id}' not found")
    return record


@router.post(
    "/negotiations",
    response_model=NegotiationRecord,
    status_code=201,
    summary="Create a negotiation record",
)
async def create_negotiation(payload: NegotiationRecordCreate) -> NegotiationRecord:
    svc = get_clinical_trial_agreement_service()
    return svc.create_negotiation(payload)


@router.put(
    "/negotiations/{negotiation_id}",
    response_model=NegotiationRecord,
    summary="Update a negotiation record",
)
async def update_negotiation(
    negotiation_id: str, payload: NegotiationRecordUpdate
) -> NegotiationRecord:
    svc = get_clinical_trial_agreement_service()
    updated = svc.update_negotiation(negotiation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Negotiation '{negotiation_id}' not found")
    return updated


@router.delete(
    "/negotiations/{negotiation_id}",
    status_code=204,
    summary="Delete a negotiation record",
)
async def delete_negotiation(negotiation_id: str) -> None:
    svc = get_clinical_trial_agreement_service()
    deleted = svc.delete_negotiation(negotiation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Negotiation '{negotiation_id}' not found")


# ---------------------------------------------------------------------------
# Budget Line Items
# ---------------------------------------------------------------------------


@router.get(
    "/line-items",
    response_model=BudgetLineItemListResponse,
    summary="List budget line items",
    description="Retrieve budget line items with optional filtering by agreement and approval status.",
)
async def list_line_items(
    agreement_id: Optional[str] = Query(None, description="Filter by agreement ID"),
    approved: Optional[bool] = Query(None, description="Filter by approval status"),
) -> BudgetLineItemListResponse:
    svc = get_clinical_trial_agreement_service()
    items = svc.list_line_items(agreement_id=agreement_id, approved=approved)
    return BudgetLineItemListResponse(items=items, total=len(items))


@router.get(
    "/line-items/{line_item_id}",
    response_model=BudgetLineItem,
    summary="Get a budget line item",
)
async def get_line_item(line_item_id: str) -> BudgetLineItem:
    svc = get_clinical_trial_agreement_service()
    item = svc.get_line_item(line_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Line item '{line_item_id}' not found")
    return item


@router.post(
    "/line-items",
    response_model=BudgetLineItem,
    status_code=201,
    summary="Create a budget line item",
)
async def create_line_item(payload: BudgetLineItemCreate) -> BudgetLineItem:
    svc = get_clinical_trial_agreement_service()
    return svc.create_line_item(payload)


@router.put(
    "/line-items/{line_item_id}",
    response_model=BudgetLineItem,
    summary="Update a budget line item",
)
async def update_line_item(
    line_item_id: str, payload: BudgetLineItemUpdate
) -> BudgetLineItem:
    svc = get_clinical_trial_agreement_service()
    updated = svc.update_line_item(line_item_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Line item '{line_item_id}' not found")
    return updated


@router.delete(
    "/line-items/{line_item_id}",
    status_code=204,
    summary="Delete a budget line item",
)
async def delete_line_item(line_item_id: str) -> None:
    svc = get_clinical_trial_agreement_service()
    deleted = svc.delete_line_item(line_item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Line item '{line_item_id}' not found")


# ---------------------------------------------------------------------------
# Agreement Amendments
# ---------------------------------------------------------------------------


@router.get(
    "/amendments",
    response_model=AgreementAmendmentListResponse,
    summary="List agreement amendments",
    description="Retrieve amendments with optional filtering by agreement and status.",
)
async def list_amendments(
    agreement_id: Optional[str] = Query(None, description="Filter by agreement ID"),
    status: Optional[AgreementStatus] = Query(None, description="Filter by status"),
) -> AgreementAmendmentListResponse:
    svc = get_clinical_trial_agreement_service()
    items = svc.list_amendments(agreement_id=agreement_id, status=status)
    return AgreementAmendmentListResponse(items=items, total=len(items))


@router.get(
    "/amendments/{amendment_id}",
    response_model=AgreementAmendment,
    summary="Get an agreement amendment",
)
async def get_amendment(amendment_id: str) -> AgreementAmendment:
    svc = get_clinical_trial_agreement_service()
    amendment = svc.get_amendment(amendment_id)
    if amendment is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return amendment


@router.post(
    "/amendments",
    response_model=AgreementAmendment,
    status_code=201,
    summary="Create an agreement amendment",
)
async def create_amendment(payload: AgreementAmendmentCreate) -> AgreementAmendment:
    svc = get_clinical_trial_agreement_service()
    return svc.create_amendment(payload)


@router.put(
    "/amendments/{amendment_id}",
    response_model=AgreementAmendment,
    summary="Update an agreement amendment",
)
async def update_amendment(
    amendment_id: str, payload: AgreementAmendmentUpdate
) -> AgreementAmendment:
    svc = get_clinical_trial_agreement_service()
    updated = svc.update_amendment(amendment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return updated


@router.delete(
    "/amendments/{amendment_id}",
    status_code=204,
    summary="Delete an agreement amendment",
)
async def delete_amendment(amendment_id: str) -> None:
    svc = get_clinical_trial_agreement_service()
    deleted = svc.delete_amendment(amendment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")


# ---------------------------------------------------------------------------
# Contract Milestones
# ---------------------------------------------------------------------------


@router.get(
    "/milestones",
    response_model=ContractMilestoneListResponse,
    summary="List contract milestones",
    description="Retrieve milestones with optional filtering by agreement and status.",
)
async def list_milestones(
    agreement_id: Optional[str] = Query(None, description="Filter by agreement ID"),
    status: Optional[str] = Query(None, description="Filter by milestone status"),
) -> ContractMilestoneListResponse:
    svc = get_clinical_trial_agreement_service()
    items = svc.list_milestones(agreement_id=agreement_id, status=status)
    return ContractMilestoneListResponse(items=items, total=len(items))


@router.get(
    "/milestones/{milestone_id}",
    response_model=ContractMilestone,
    summary="Get a contract milestone",
)
async def get_milestone(milestone_id: str) -> ContractMilestone:
    svc = get_clinical_trial_agreement_service()
    milestone = svc.get_milestone(milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail=f"Milestone '{milestone_id}' not found")
    return milestone


@router.post(
    "/milestones",
    response_model=ContractMilestone,
    status_code=201,
    summary="Create a contract milestone",
)
async def create_milestone(payload: ContractMilestoneCreate) -> ContractMilestone:
    svc = get_clinical_trial_agreement_service()
    return svc.create_milestone(payload)


@router.put(
    "/milestones/{milestone_id}",
    response_model=ContractMilestone,
    summary="Update a contract milestone",
)
async def update_milestone(
    milestone_id: str, payload: ContractMilestoneUpdate
) -> ContractMilestone:
    svc = get_clinical_trial_agreement_service()
    updated = svc.update_milestone(milestone_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Milestone '{milestone_id}' not found")
    return updated


@router.delete(
    "/milestones/{milestone_id}",
    status_code=204,
    summary="Delete a contract milestone",
)
async def delete_milestone(milestone_id: str) -> None:
    svc = get_clinical_trial_agreement_service()
    deleted = svc.delete_milestone(milestone_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Milestone '{milestone_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalTrialAgreementMetrics,
    summary="Get agreement management metrics",
    description="Aggregated metrics including agreement counts, negotiation status, "
                "budget totals, amendment tracking, and milestone completion.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> ClinicalTrialAgreementMetrics:
    svc = get_clinical_trial_agreement_service()
    return svc.get_metrics(trial_id=trial_id)
