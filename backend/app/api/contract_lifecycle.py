"""Contract Lifecycle Management API endpoints (CLO-6).

Pharma-grade contract lifecycle management covering IP management, contract
versioning, milestone tracking, amendment workflows, and compliance obligations.

Endpoints:
    GET    /contract-lifecycle/contracts                          - List contracts
    POST   /contract-lifecycle/contracts                          - Create contract
    GET    /contract-lifecycle/contracts/metrics                   - Portfolio metrics
    GET    /contract-lifecycle/contracts/compliance                - Compliance report
    GET    /contract-lifecycle/contracts/auto-renewal              - Auto-renewal candidates
    GET    /contract-lifecycle/contracts/{id}                      - Get contract detail
    PUT    /contract-lifecycle/contracts/{id}                      - Update contract
    DELETE /contract-lifecycle/contracts/{id}                      - Delete draft contract
    POST   /contract-lifecycle/contracts/{id}/transition           - Status transition
    GET    /contract-lifecycle/contracts/{id}/milestones           - List milestones
    POST   /contract-lifecycle/contracts/{id}/milestones           - Create milestone
    PUT    /contract-lifecycle/contracts/{id}/milestones/{ms_id}   - Update milestone status
    GET    /contract-lifecycle/contracts/{id}/obligations          - List obligations
    POST   /contract-lifecycle/contracts/{id}/obligations          - Create obligation
    POST   /contract-lifecycle/contracts/{id}/obligations/{obl_id}/complete - Complete obligation
    GET    /contract-lifecycle/obligations/overdue                 - Overdue obligations
    GET    /contract-lifecycle/contracts/{id}/amendments           - List amendments
    POST   /contract-lifecycle/contracts/{id}/amendments           - Create amendment
    GET    /contract-lifecycle/ip-records                          - List IP records
    POST   /contract-lifecycle/ip-records                          - Create IP record
    GET    /contract-lifecycle/ip-records/{id}                     - Get IP record
    POST   /contract-lifecycle/ip-records/{ip_id}/link/{ctr_id}   - Link IP to contract
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.contract_lifecycle import (
    AmendmentCreateRequest,
    Contract,
    ContractAmendment,
    ContractComplianceReport,
    ContractCreateRequest,
    ContractListResponse,
    ContractMetrics,
    ContractMilestone,
    ContractObligation,
    ContractStatus,
    ContractType,
    ContractUpdateRequest,
    IPRecord,
    IPRecordCreateRequest,
    IPRecordListResponse,
    MilestoneCreateRequest,
    MilestoneStatus,
    ObligationCreateRequest,
)
from app.services.contract_lifecycle_service import get_contract_lifecycle_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contract-lifecycle", tags=["Contract Lifecycle"])


# ---------------------------------------------------------------------------
# Contract CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/contracts",
    response_model=ContractListResponse,
    summary="List contracts",
    description="List all contracts with optional filtering by type, status, or party name.",
)
async def list_contracts(
    contract_type: Optional[ContractType] = Query(
        default=None, description="Filter by contract type"
    ),
    contract_status: Optional[ContractStatus] = Query(
        default=None,
        alias="status",
        description="Filter by contract status",
    ),
    party_name: Optional[str] = Query(
        default=None, description="Filter by party name (partial match)"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> ContractListResponse:
    """List contracts with optional filters."""
    svc = get_contract_lifecycle_service()
    return svc.list_contracts(
        contract_type=contract_type,
        status=contract_status,
        party_name=party_name,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/contracts",
    response_model=Contract,
    status_code=status.HTTP_201_CREATED,
    summary="Create contract",
    description="Create a new contract in DRAFT status.",
)
async def create_contract(req: ContractCreateRequest) -> Contract:
    """Create a new contract."""
    svc = get_contract_lifecycle_service()
    return svc.create_contract(req)


@router.get(
    "/contracts/metrics",
    response_model=ContractMetrics,
    summary="Portfolio metrics",
    description="Get aggregated metrics for the contract portfolio.",
)
async def get_metrics() -> ContractMetrics:
    """Get contract portfolio metrics."""
    svc = get_contract_lifecycle_service()
    return svc.get_metrics()


@router.get(
    "/contracts/compliance",
    response_model=ContractComplianceReport,
    summary="Compliance report",
    description="Generate a compliance report identifying contract health issues.",
)
async def get_compliance_report() -> ContractComplianceReport:
    """Get compliance report."""
    svc = get_contract_lifecycle_service()
    return svc.get_compliance_report()


@router.get(
    "/contracts/auto-renewal",
    response_model=list[Contract],
    summary="Auto-renewal candidates",
    description="Get contracts approaching auto-renewal within their notice window.",
)
async def get_auto_renewal() -> list[Contract]:
    """Get auto-renewal candidates."""
    svc = get_contract_lifecycle_service()
    return svc.get_auto_renewal_contracts()


@router.get(
    "/contracts/{contract_id}",
    response_model=Contract,
    summary="Get contract",
    description="Get a single contract by ID.",
)
async def get_contract(contract_id: str) -> Contract:
    """Get a contract by ID."""
    svc = get_contract_lifecycle_service()
    contract = svc.get_contract(contract_id)
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return contract


@router.put(
    "/contracts/{contract_id}",
    response_model=Contract,
    summary="Update contract",
    description="Update contract fields. Status transitions are validated.",
)
async def update_contract(
    contract_id: str, req: ContractUpdateRequest
) -> Contract:
    """Update a contract."""
    svc = get_contract_lifecycle_service()
    try:
        contract = svc.update_contract(contract_id, req)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return contract


@router.delete(
    "/contracts/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete contract",
    description="Delete a DRAFT contract. Non-draft contracts cannot be deleted.",
)
async def delete_contract(contract_id: str) -> None:
    """Delete a draft contract."""
    svc = get_contract_lifecycle_service()
    try:
        deleted = svc.delete_contract(contract_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )


@router.post(
    "/contracts/{contract_id}/transition",
    response_model=Contract,
    summary="Transition status",
    description="Transition a contract to a new status. Validates allowed transitions.",
)
async def transition_status(
    contract_id: str,
    new_status: ContractStatus = Query(..., description="Target status"),
) -> Contract:
    """Transition contract status."""
    svc = get_contract_lifecycle_service()
    try:
        contract = svc.transition_status(contract_id, new_status)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return contract


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contract_id}/milestones",
    response_model=list[ContractMilestone],
    summary="List milestones",
    description="List all milestones for a contract.",
)
async def list_milestones(contract_id: str) -> list[ContractMilestone]:
    """List milestones for a contract."""
    svc = get_contract_lifecycle_service()
    if svc.get_contract(contract_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return svc.list_milestones(contract_id)


@router.post(
    "/contracts/{contract_id}/milestones",
    response_model=ContractMilestone,
    status_code=status.HTTP_201_CREATED,
    summary="Create milestone",
    description="Add a new milestone to a contract.",
)
async def create_milestone(
    contract_id: str, req: MilestoneCreateRequest
) -> ContractMilestone:
    """Create a milestone."""
    svc = get_contract_lifecycle_service()
    ms = svc.create_milestone(contract_id, req)
    if ms is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return ms


@router.put(
    "/contracts/{contract_id}/milestones/{milestone_id}",
    response_model=ContractMilestone,
    summary="Update milestone status",
    description="Update the status of a contract milestone.",
)
async def update_milestone(
    contract_id: str,
    milestone_id: str,
    milestone_status: MilestoneStatus = Query(
        ..., alias="status", description="New milestone status"
    ),
) -> ContractMilestone:
    """Update milestone status."""
    svc = get_contract_lifecycle_service()
    ms = svc.update_milestone_status(contract_id, milestone_id, milestone_status)
    if ms is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Milestone {milestone_id} not found in contract {contract_id}",
        )
    return ms


# ---------------------------------------------------------------------------
# Obligations
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contract_id}/obligations",
    response_model=list[ContractObligation],
    summary="List obligations",
    description="List all obligations for a contract.",
)
async def list_obligations(contract_id: str) -> list[ContractObligation]:
    """List obligations for a contract."""
    svc = get_contract_lifecycle_service()
    if svc.get_contract(contract_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return svc.list_obligations(contract_id)


@router.post(
    "/contracts/{contract_id}/obligations",
    response_model=ContractObligation,
    status_code=status.HTTP_201_CREATED,
    summary="Create obligation",
    description="Add a new obligation to a contract.",
)
async def create_obligation(
    contract_id: str, req: ObligationCreateRequest
) -> ContractObligation:
    """Create an obligation."""
    svc = get_contract_lifecycle_service()
    obl = svc.create_obligation(contract_id, req)
    if obl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return obl


@router.post(
    "/contracts/{contract_id}/obligations/{obligation_id}/complete",
    response_model=ContractObligation,
    summary="Complete obligation",
    description="Mark a contractual obligation as completed.",
)
async def complete_obligation(
    contract_id: str, obligation_id: str
) -> ContractObligation:
    """Complete an obligation."""
    svc = get_contract_lifecycle_service()
    obl = svc.complete_obligation(contract_id, obligation_id)
    if obl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation {obligation_id} not found in contract {contract_id}",
        )
    return obl


@router.get(
    "/obligations/overdue",
    response_model=list[ContractObligation],
    summary="Overdue obligations",
    description="Get all overdue obligations across all active contracts.",
)
async def get_overdue_obligations() -> list[ContractObligation]:
    """Get overdue obligations."""
    svc = get_contract_lifecycle_service()
    return svc.get_overdue_obligations()


# ---------------------------------------------------------------------------
# Amendments
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contract_id}/amendments",
    response_model=list[ContractAmendment],
    summary="List amendments",
    description="List all amendments for a contract.",
)
async def list_amendments(contract_id: str) -> list[ContractAmendment]:
    """List amendments for a contract."""
    svc = get_contract_lifecycle_service()
    if svc.get_contract(contract_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return svc.list_amendments(contract_id)


@router.post(
    "/contracts/{contract_id}/amendments",
    response_model=ContractAmendment,
    status_code=status.HTTP_201_CREATED,
    summary="Create amendment",
    description="Add a new amendment to a contract.",
)
async def create_amendment(
    contract_id: str, req: AmendmentCreateRequest
) -> ContractAmendment:
    """Create an amendment."""
    svc = get_contract_lifecycle_service()
    amd = svc.create_amendment(contract_id, req)
    if amd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    return amd


# ---------------------------------------------------------------------------
# IP Records
# ---------------------------------------------------------------------------


@router.get(
    "/ip-records",
    response_model=IPRecordListResponse,
    summary="List IP records",
    description="List all intellectual property records.",
)
async def list_ip_records() -> IPRecordListResponse:
    """List all IP records."""
    svc = get_contract_lifecycle_service()
    return svc.list_ip_records()


@router.post(
    "/ip-records",
    response_model=IPRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create IP record",
    description="Create a new intellectual property record.",
)
async def create_ip_record(req: IPRecordCreateRequest) -> IPRecord:
    """Create an IP record."""
    svc = get_contract_lifecycle_service()
    return svc.create_ip_record(req)


@router.get(
    "/ip-records/{ip_id}",
    response_model=IPRecord,
    summary="Get IP record",
    description="Get a single IP record by ID.",
)
async def get_ip_record(ip_id: str) -> IPRecord:
    """Get an IP record by ID."""
    svc = get_contract_lifecycle_service()
    ip_record = svc.get_ip_record(ip_id)
    if ip_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP record {ip_id} not found",
        )
    return ip_record


@router.post(
    "/ip-records/{ip_id}/link/{contract_id}",
    response_model=IPRecord,
    summary="Link IP to contract",
    description="Link an IP record to a contract.",
)
async def link_ip_to_contract(ip_id: str, contract_id: str) -> IPRecord:
    """Link an IP record to a contract."""
    svc = get_contract_lifecycle_service()
    # Verify contract exists
    if svc.get_contract(contract_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found",
        )
    ip_record = svc.link_ip_to_contract(ip_id, contract_id)
    if ip_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP record {ip_id} not found",
        )
    return ip_record
