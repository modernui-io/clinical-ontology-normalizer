"""Clinical Data Transfer Management API endpoints (DATA-XFER).

Provides comprehensive data transfer operations: agreement management,
transfer execution tracking, data validation checks, reconciliation,
secure file transfer monitoring, and transfer metrics.

Endpoints:
    GET    /data-transfer/agreements                              - List agreements
    GET    /data-transfer/agreements/{agreement_id}               - Get single agreement
    POST   /data-transfer/agreements                              - Create agreement
    PUT    /data-transfer/agreements/{agreement_id}               - Update agreement
    DELETE /data-transfer/agreements/{agreement_id}               - Delete agreement
    GET    /data-transfer/executions                              - List executions
    GET    /data-transfer/executions/{execution_id}               - Get single execution
    POST   /data-transfer/executions                              - Create execution
    PUT    /data-transfer/executions/{execution_id}               - Update execution
    DELETE /data-transfer/executions/{execution_id}               - Delete execution
    GET    /data-transfer/validations                             - List validations
    GET    /data-transfer/validations/{validation_id}             - Get single validation
    POST   /data-transfer/validations                             - Create validation
    DELETE /data-transfer/validations/{validation_id}             - Delete validation
    GET    /data-transfer/reconciliations                         - List reconciliations
    GET    /data-transfer/reconciliations/{reconciliation_id}     - Get single reconciliation
    POST   /data-transfer/reconciliations                         - Create reconciliation
    PUT    /data-transfer/reconciliations/{reconciliation_id}     - Update reconciliation
    DELETE /data-transfer/reconciliations/{reconciliation_id}     - Delete reconciliation
    GET    /data-transfer/metrics                                 - Transfer metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.data_transfer import (
    AgreementStatus,
    DataTransferAgreement,
    DataTransferAgreementCreate,
    DataTransferAgreementListResponse,
    DataTransferAgreementUpdate,
    DataTransferExecution,
    DataTransferExecutionCreate,
    DataTransferExecutionListResponse,
    DataTransferExecutionUpdate,
    DataTransferMetrics,
    TransferDirection,
    TransferFrequency,
    TransferMethod,
    TransferReconciliation,
    TransferReconciliationCreate,
    TransferReconciliationListResponse,
    TransferReconciliationUpdate,
    TransferStatus,
    TransferValidation,
    TransferValidationCreate,
    TransferValidationListResponse,
    ValidationResult,
)
from app.services.data_transfer_service import get_data_transfer_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data-transfer",
    tags=["Data Transfer"],
)


# ---------------------------------------------------------------------------
# Agreement Management
# ---------------------------------------------------------------------------


@router.get(
    "/agreements",
    response_model=DataTransferAgreementListResponse,
    summary="List transfer agreements",
    description="Retrieve data transfer agreements with optional filtering.",
)
async def list_agreements(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    direction: Optional[TransferDirection] = Query(None, description="Filter by direction"),
    method: Optional[TransferMethod] = Query(None, description="Filter by transfer method"),
    status: Optional[AgreementStatus] = Query(None, description="Filter by status"),
    frequency: Optional[TransferFrequency] = Query(None, description="Filter by frequency"),
) -> DataTransferAgreementListResponse:
    svc = get_data_transfer_service()
    items = svc.list_agreements(
        trial_id=trial_id, direction=direction, method=method,
        status=status, frequency=frequency,
    )
    return DataTransferAgreementListResponse(items=items, total=len(items))


@router.get(
    "/agreements/{agreement_id}",
    response_model=DataTransferAgreement,
    summary="Get a transfer agreement",
)
async def get_agreement(agreement_id: str) -> DataTransferAgreement:
    svc = get_data_transfer_service()
    agreement = svc.get_agreement(agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")
    return agreement


@router.post(
    "/agreements",
    response_model=DataTransferAgreement,
    status_code=201,
    summary="Create a transfer agreement",
)
async def create_agreement(payload: DataTransferAgreementCreate) -> DataTransferAgreement:
    svc = get_data_transfer_service()
    return svc.create_agreement(payload)


@router.put(
    "/agreements/{agreement_id}",
    response_model=DataTransferAgreement,
    summary="Update a transfer agreement",
)
async def update_agreement(
    agreement_id: str, payload: DataTransferAgreementUpdate
) -> DataTransferAgreement:
    svc = get_data_transfer_service()
    updated = svc.update_agreement(agreement_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")
    return updated


@router.delete(
    "/agreements/{agreement_id}",
    status_code=204,
    summary="Delete a transfer agreement",
)
async def delete_agreement(agreement_id: str) -> None:
    svc = get_data_transfer_service()
    deleted = svc.delete_agreement(agreement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")


# ---------------------------------------------------------------------------
# Execution Management
# ---------------------------------------------------------------------------


@router.get(
    "/executions",
    response_model=DataTransferExecutionListResponse,
    summary="List transfer executions",
    description="Retrieve transfer executions with optional filtering.",
)
async def list_executions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    agreement_id: Optional[str] = Query(None, description="Filter by agreement ID"),
    direction: Optional[TransferDirection] = Query(None, description="Filter by direction"),
    status: Optional[TransferStatus] = Query(None, description="Filter by status"),
) -> DataTransferExecutionListResponse:
    svc = get_data_transfer_service()
    items = svc.list_executions(
        trial_id=trial_id, agreement_id=agreement_id,
        direction=direction, status=status,
    )
    return DataTransferExecutionListResponse(items=items, total=len(items))


@router.get(
    "/executions/{execution_id}",
    response_model=DataTransferExecution,
    summary="Get a transfer execution",
)
async def get_execution(execution_id: str) -> DataTransferExecution:
    svc = get_data_transfer_service()
    execution = svc.get_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
    return execution


@router.post(
    "/executions",
    response_model=DataTransferExecution,
    status_code=201,
    summary="Create a transfer execution",
)
async def create_execution(payload: DataTransferExecutionCreate) -> DataTransferExecution:
    svc = get_data_transfer_service()
    try:
        return svc.create_execution(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/executions/{execution_id}",
    response_model=DataTransferExecution,
    summary="Update a transfer execution",
)
async def update_execution(
    execution_id: str, payload: DataTransferExecutionUpdate
) -> DataTransferExecution:
    svc = get_data_transfer_service()
    updated = svc.update_execution(execution_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
    return updated


@router.delete(
    "/executions/{execution_id}",
    status_code=204,
    summary="Delete a transfer execution",
)
async def delete_execution(execution_id: str) -> None:
    svc = get_data_transfer_service()
    deleted = svc.delete_execution(execution_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")


# ---------------------------------------------------------------------------
# Validation Management
# ---------------------------------------------------------------------------


@router.get(
    "/validations",
    response_model=TransferValidationListResponse,
    summary="List transfer validations",
    description="Retrieve transfer validations with optional filtering.",
)
async def list_validations(
    execution_id: Optional[str] = Query(None, description="Filter by execution ID"),
    result: Optional[ValidationResult] = Query(None, description="Filter by validation result"),
) -> TransferValidationListResponse:
    svc = get_data_transfer_service()
    items = svc.list_validations(execution_id=execution_id, result=result)
    return TransferValidationListResponse(items=items, total=len(items))


@router.get(
    "/validations/{validation_id}",
    response_model=TransferValidation,
    summary="Get a transfer validation",
)
async def get_validation(validation_id: str) -> TransferValidation:
    svc = get_data_transfer_service()
    validation = svc.get_validation(validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return validation


@router.post(
    "/validations",
    response_model=TransferValidation,
    status_code=201,
    summary="Create a transfer validation",
)
async def create_validation(payload: TransferValidationCreate) -> TransferValidation:
    svc = get_data_transfer_service()
    try:
        return svc.create_validation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/validations/{validation_id}",
    status_code=204,
    summary="Delete a transfer validation",
)
async def delete_validation(validation_id: str) -> None:
    svc = get_data_transfer_service()
    deleted = svc.delete_validation(validation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")


# ---------------------------------------------------------------------------
# Reconciliation Management
# ---------------------------------------------------------------------------


@router.get(
    "/reconciliations",
    response_model=TransferReconciliationListResponse,
    summary="List transfer reconciliations",
    description="Retrieve transfer reconciliations with optional filtering.",
)
async def list_reconciliations(
    execution_id: Optional[str] = Query(None, description="Filter by execution ID"),
    reconciled: Optional[bool] = Query(None, description="Filter by reconciled status"),
) -> TransferReconciliationListResponse:
    svc = get_data_transfer_service()
    items = svc.list_reconciliations(execution_id=execution_id, reconciled=reconciled)
    return TransferReconciliationListResponse(items=items, total=len(items))


@router.get(
    "/reconciliations/{reconciliation_id}",
    response_model=TransferReconciliation,
    summary="Get a transfer reconciliation",
)
async def get_reconciliation(reconciliation_id: str) -> TransferReconciliation:
    svc = get_data_transfer_service()
    reconciliation = svc.get_reconciliation(reconciliation_id)
    if reconciliation is None:
        raise HTTPException(status_code=404, detail=f"Reconciliation '{reconciliation_id}' not found")
    return reconciliation


@router.post(
    "/reconciliations",
    response_model=TransferReconciliation,
    status_code=201,
    summary="Create a transfer reconciliation",
)
async def create_reconciliation(payload: TransferReconciliationCreate) -> TransferReconciliation:
    svc = get_data_transfer_service()
    try:
        return svc.create_reconciliation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/reconciliations/{reconciliation_id}",
    response_model=TransferReconciliation,
    summary="Update a transfer reconciliation",
)
async def update_reconciliation(
    reconciliation_id: str, payload: TransferReconciliationUpdate
) -> TransferReconciliation:
    svc = get_data_transfer_service()
    updated = svc.update_reconciliation(reconciliation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Reconciliation '{reconciliation_id}' not found")
    return updated


@router.delete(
    "/reconciliations/{reconciliation_id}",
    status_code=204,
    summary="Delete a transfer reconciliation",
)
async def delete_reconciliation(reconciliation_id: str) -> None:
    svc = get_data_transfer_service()
    deleted = svc.delete_reconciliation(reconciliation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Reconciliation '{reconciliation_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DataTransferMetrics,
    summary="Get data transfer metrics",
    description="Aggregated data transfer metrics including agreement status breakdown, "
                "execution success/failure rates, validation results, reconciliation status, "
                "and average transfer duration.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> DataTransferMetrics:
    svc = get_data_transfer_service()
    return svc.get_metrics(trial_id=trial_id)
