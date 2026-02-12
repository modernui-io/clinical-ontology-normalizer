"""Drug Accountability Management API endpoints (DRUG-ACCT).

Provides comprehensive drug accountability operations: dispensation records,
drug return tracking, destruction records, accountability reconciliation,
deviation tracking, and drug accountability operational metrics.

Endpoints:
    POST   /drug-accountability/dispensation-records                        - Create dispensation record
    GET    /drug-accountability/dispensation-records                        - List dispensation records
    GET    /drug-accountability/dispensation-records/{record_id}            - Get dispensation record
    PUT    /drug-accountability/dispensation-records/{record_id}            - Update dispensation record
    DELETE /drug-accountability/dispensation-records/{record_id}            - Delete dispensation record
    POST   /drug-accountability/drug-returns                               - Create drug return
    GET    /drug-accountability/drug-returns                               - List drug returns
    GET    /drug-accountability/drug-returns/{return_id}                    - Get drug return
    PUT    /drug-accountability/drug-returns/{return_id}                    - Update drug return
    DELETE /drug-accountability/drug-returns/{return_id}                    - Delete drug return
    POST   /drug-accountability/destruction-records                        - Create destruction record
    GET    /drug-accountability/destruction-records                        - List destruction records
    GET    /drug-accountability/destruction-records/{record_id}            - Get destruction record
    PUT    /drug-accountability/destruction-records/{record_id}            - Update destruction record
    DELETE /drug-accountability/destruction-records/{record_id}            - Delete destruction record
    POST   /drug-accountability/reconciliations                            - Create reconciliation
    GET    /drug-accountability/reconciliations                            - List reconciliations
    GET    /drug-accountability/reconciliations/{recon_id}                  - Get reconciliation
    PUT    /drug-accountability/reconciliations/{recon_id}                  - Update reconciliation
    DELETE /drug-accountability/reconciliations/{recon_id}                  - Delete reconciliation
    POST   /drug-accountability/deviations                                 - Create deviation
    GET    /drug-accountability/deviations                                 - List deviations
    GET    /drug-accountability/deviations/{deviation_id}                   - Get deviation
    PUT    /drug-accountability/deviations/{deviation_id}                   - Update deviation
    DELETE /drug-accountability/deviations/{deviation_id}                   - Delete deviation
    GET    /drug-accountability/metrics                                     - Get metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.drug_accountability import (
    AccountabilityDeviation,
    AccountabilityDeviationCreate,
    AccountabilityDeviationListResponse,
    AccountabilityDeviationUpdate,
    AccountabilityReconciliation,
    AccountabilityReconciliationCreate,
    AccountabilityReconciliationListResponse,
    AccountabilityReconciliationUpdate,
    DestructionRecord,
    DestructionRecordCreate,
    DestructionRecordListResponse,
    DestructionRecordUpdate,
    DispensationRecord,
    DispensationRecordCreate,
    DispensationRecordListResponse,
    DispensationRecordUpdate,
    DrugAccountabilityMetrics,
    DrugReturn,
    DrugReturnCreate,
    DrugReturnListResponse,
    DrugReturnUpdate,
)
from app.services.drug_accountability_service import get_drug_accountability_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/drug-accountability",
    tags=["Drug Accountability"],
)


# ---------------------------------------------------------------------------
# Dispensation Records
# ---------------------------------------------------------------------------


@router.post(
    "/dispensation-records",
    response_model=DispensationRecord,
    status_code=201,
    summary="Create a dispensation record",
)
async def create_dispensation_record(payload: DispensationRecordCreate) -> DispensationRecord:
    svc = get_drug_accountability_service()
    return svc.create_dispensation_record(payload)


@router.get(
    "/dispensation-records",
    response_model=DispensationRecordListResponse,
    summary="List dispensation records",
    description="Retrieve dispensation records with optional filtering by trial ID.",
)
async def list_dispensation_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DispensationRecordListResponse:
    svc = get_drug_accountability_service()
    items = svc.list_dispensation_records(trial_id=trial_id)
    return DispensationRecordListResponse(items=items, total=len(items))


@router.get(
    "/dispensation-records/{record_id}",
    response_model=DispensationRecord,
    summary="Get a dispensation record",
)
async def get_dispensation_record(record_id: str) -> DispensationRecord:
    svc = get_drug_accountability_service()
    record = svc.get_dispensation_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Dispensation record '{record_id}' not found")
    return record


@router.put(
    "/dispensation-records/{record_id}",
    response_model=DispensationRecord,
    summary="Update a dispensation record",
)
async def update_dispensation_record(
    record_id: str, payload: DispensationRecordUpdate
) -> DispensationRecord:
    svc = get_drug_accountability_service()
    updated = svc.update_dispensation_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Dispensation record '{record_id}' not found")
    return updated


@router.delete(
    "/dispensation-records/{record_id}",
    status_code=204,
    summary="Delete a dispensation record",
)
async def delete_dispensation_record(record_id: str) -> None:
    svc = get_drug_accountability_service()
    deleted = svc.delete_dispensation_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dispensation record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Drug Returns
# ---------------------------------------------------------------------------


@router.post(
    "/drug-returns",
    response_model=DrugReturn,
    status_code=201,
    summary="Create a drug return",
)
async def create_drug_return(payload: DrugReturnCreate) -> DrugReturn:
    svc = get_drug_accountability_service()
    return svc.create_drug_return(payload)


@router.get(
    "/drug-returns",
    response_model=DrugReturnListResponse,
    summary="List drug returns",
    description="Retrieve drug returns with optional filtering by trial ID.",
)
async def list_drug_returns(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DrugReturnListResponse:
    svc = get_drug_accountability_service()
    items = svc.list_drug_returns(trial_id=trial_id)
    return DrugReturnListResponse(items=items, total=len(items))


@router.get(
    "/drug-returns/{return_id}",
    response_model=DrugReturn,
    summary="Get a drug return",
)
async def get_drug_return(return_id: str) -> DrugReturn:
    svc = get_drug_accountability_service()
    record = svc.get_drug_return(return_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Drug return '{return_id}' not found")
    return record


@router.put(
    "/drug-returns/{return_id}",
    response_model=DrugReturn,
    summary="Update a drug return",
)
async def update_drug_return(return_id: str, payload: DrugReturnUpdate) -> DrugReturn:
    svc = get_drug_accountability_service()
    updated = svc.update_drug_return(return_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Drug return '{return_id}' not found")
    return updated


@router.delete(
    "/drug-returns/{return_id}",
    status_code=204,
    summary="Delete a drug return",
)
async def delete_drug_return(return_id: str) -> None:
    svc = get_drug_accountability_service()
    deleted = svc.delete_drug_return(return_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Drug return '{return_id}' not found")


# ---------------------------------------------------------------------------
# Destruction Records
# ---------------------------------------------------------------------------


@router.post(
    "/destruction-records",
    response_model=DestructionRecord,
    status_code=201,
    summary="Create a destruction record",
)
async def create_destruction_record(payload: DestructionRecordCreate) -> DestructionRecord:
    svc = get_drug_accountability_service()
    return svc.create_destruction_record(payload)


@router.get(
    "/destruction-records",
    response_model=DestructionRecordListResponse,
    summary="List destruction records",
    description="Retrieve destruction records with optional filtering by trial ID.",
)
async def list_destruction_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DestructionRecordListResponse:
    svc = get_drug_accountability_service()
    items = svc.list_destruction_records(trial_id=trial_id)
    return DestructionRecordListResponse(items=items, total=len(items))


@router.get(
    "/destruction-records/{record_id}",
    response_model=DestructionRecord,
    summary="Get a destruction record",
)
async def get_destruction_record(record_id: str) -> DestructionRecord:
    svc = get_drug_accountability_service()
    record = svc.get_destruction_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Destruction record '{record_id}' not found")
    return record


@router.put(
    "/destruction-records/{record_id}",
    response_model=DestructionRecord,
    summary="Update a destruction record",
)
async def update_destruction_record(
    record_id: str, payload: DestructionRecordUpdate
) -> DestructionRecord:
    svc = get_drug_accountability_service()
    updated = svc.update_destruction_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Destruction record '{record_id}' not found")
    return updated


@router.delete(
    "/destruction-records/{record_id}",
    status_code=204,
    summary="Delete a destruction record",
)
async def delete_destruction_record(record_id: str) -> None:
    svc = get_drug_accountability_service()
    deleted = svc.delete_destruction_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Destruction record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Accountability Reconciliations
# ---------------------------------------------------------------------------


@router.post(
    "/reconciliations",
    response_model=AccountabilityReconciliation,
    status_code=201,
    summary="Create an accountability reconciliation",
)
async def create_reconciliation(
    payload: AccountabilityReconciliationCreate,
) -> AccountabilityReconciliation:
    svc = get_drug_accountability_service()
    return svc.create_accountability_reconciliation(payload)


@router.get(
    "/reconciliations",
    response_model=AccountabilityReconciliationListResponse,
    summary="List accountability reconciliations",
    description="Retrieve reconciliations with optional filtering by trial ID.",
)
async def list_reconciliations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> AccountabilityReconciliationListResponse:
    svc = get_drug_accountability_service()
    items = svc.list_accountability_reconciliations(trial_id=trial_id)
    return AccountabilityReconciliationListResponse(items=items, total=len(items))


@router.get(
    "/reconciliations/{recon_id}",
    response_model=AccountabilityReconciliation,
    summary="Get an accountability reconciliation",
)
async def get_reconciliation(recon_id: str) -> AccountabilityReconciliation:
    svc = get_drug_accountability_service()
    record = svc.get_accountability_reconciliation(recon_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Reconciliation '{recon_id}' not found")
    return record


@router.put(
    "/reconciliations/{recon_id}",
    response_model=AccountabilityReconciliation,
    summary="Update an accountability reconciliation",
)
async def update_reconciliation(
    recon_id: str, payload: AccountabilityReconciliationUpdate
) -> AccountabilityReconciliation:
    svc = get_drug_accountability_service()
    updated = svc.update_accountability_reconciliation(recon_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Reconciliation '{recon_id}' not found")
    return updated


@router.delete(
    "/reconciliations/{recon_id}",
    status_code=204,
    summary="Delete an accountability reconciliation",
)
async def delete_reconciliation(recon_id: str) -> None:
    svc = get_drug_accountability_service()
    deleted = svc.delete_accountability_reconciliation(recon_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Reconciliation '{recon_id}' not found")


# ---------------------------------------------------------------------------
# Accountability Deviations
# ---------------------------------------------------------------------------


@router.post(
    "/deviations",
    response_model=AccountabilityDeviation,
    status_code=201,
    summary="Create an accountability deviation",
)
async def create_deviation(payload: AccountabilityDeviationCreate) -> AccountabilityDeviation:
    svc = get_drug_accountability_service()
    return svc.create_accountability_deviation(payload)


@router.get(
    "/deviations",
    response_model=AccountabilityDeviationListResponse,
    summary="List accountability deviations",
    description="Retrieve deviations with optional filtering by trial ID.",
)
async def list_deviations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> AccountabilityDeviationListResponse:
    svc = get_drug_accountability_service()
    items = svc.list_accountability_deviations(trial_id=trial_id)
    return AccountabilityDeviationListResponse(items=items, total=len(items))


@router.get(
    "/deviations/{deviation_id}",
    response_model=AccountabilityDeviation,
    summary="Get an accountability deviation",
)
async def get_deviation(deviation_id: str) -> AccountabilityDeviation:
    svc = get_drug_accountability_service()
    record = svc.get_accountability_deviation(deviation_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Deviation '{deviation_id}' not found")
    return record


@router.put(
    "/deviations/{deviation_id}",
    response_model=AccountabilityDeviation,
    summary="Update an accountability deviation",
)
async def update_deviation(
    deviation_id: str, payload: AccountabilityDeviationUpdate
) -> AccountabilityDeviation:
    svc = get_drug_accountability_service()
    updated = svc.update_accountability_deviation(deviation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Deviation '{deviation_id}' not found")
    return updated


@router.delete(
    "/deviations/{deviation_id}",
    status_code=204,
    summary="Delete an accountability deviation",
)
async def delete_deviation(deviation_id: str) -> None:
    svc = get_drug_accountability_service()
    deleted = svc.delete_accountability_deviation(deviation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Deviation '{deviation_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DrugAccountabilityMetrics,
    summary="Get drug accountability metrics",
    description="Aggregated drug accountability operational metrics across all trials and sites.",
)
async def get_metrics() -> DrugAccountabilityMetrics:
    svc = get_drug_accountability_service()
    return svc.get_metrics()
