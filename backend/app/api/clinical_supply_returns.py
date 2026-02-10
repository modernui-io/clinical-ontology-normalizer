"""Clinical Supply Returns Management API endpoints (SUPPLY-RET).

Provides comprehensive supply returns operations: return tracking, destruction records,
temperature excursion documentation, quarantine management, drug accountability
reconciliation, and returns metrics.

Endpoints:
    GET    /clinical-supply-returns/returns                                     - List returns
    GET    /clinical-supply-returns/returns/{return_id}                         - Get single return
    POST   /clinical-supply-returns/returns                                     - Create return
    PUT    /clinical-supply-returns/returns/{return_id}                         - Update return
    DELETE /clinical-supply-returns/returns/{return_id}                         - Delete return
    GET    /clinical-supply-returns/destructions                                - List destructions
    GET    /clinical-supply-returns/destructions/{destruction_id}               - Get single destruction
    POST   /clinical-supply-returns/destructions                                - Create destruction
    DELETE /clinical-supply-returns/destructions/{destruction_id}               - Delete destruction
    GET    /clinical-supply-returns/excursions                                  - List excursions
    GET    /clinical-supply-returns/excursions/{excursion_id}                   - Get single excursion
    POST   /clinical-supply-returns/excursions                                  - Create excursion
    PUT    /clinical-supply-returns/excursions/{excursion_id}                   - Update excursion
    DELETE /clinical-supply-returns/excursions/{excursion_id}                   - Delete excursion
    GET    /clinical-supply-returns/quarantines                                 - List quarantines
    GET    /clinical-supply-returns/quarantines/{quarantine_id}                 - Get single quarantine
    POST   /clinical-supply-returns/quarantines                                 - Create quarantine
    PUT    /clinical-supply-returns/quarantines/{quarantine_id}                 - Update quarantine
    DELETE /clinical-supply-returns/quarantines/{quarantine_id}                 - Delete quarantine
    GET    /clinical-supply-returns/accountabilities                            - List accountabilities
    GET    /clinical-supply-returns/accountabilities/{accountability_id}        - Get single accountability
    POST   /clinical-supply-returns/accountabilities                            - Create accountability
    PUT    /clinical-supply-returns/accountabilities/{accountability_id}        - Update accountability
    DELETE /clinical-supply-returns/accountabilities/{accountability_id}        - Delete accountability
    GET    /clinical-supply-returns/metrics                                     - Returns metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_supply_returns import (
    DestructionMethod,
    DestructionRecord,
    DestructionRecordCreate,
    DestructionRecordListResponse,
    DrugAccountability,
    DrugAccountabilityCreate,
    DrugAccountabilityListResponse,
    DrugAccountabilityUpdate,
    ExcursionSeverity,
    QuarantineRecord,
    QuarantineRecordCreate,
    QuarantineRecordListResponse,
    QuarantineRecordUpdate,
    ReconciliationResult,
    ReturnReason,
    ReturnStatus,
    SupplyReturn,
    SupplyReturnCreate,
    SupplyReturnListResponse,
    SupplyReturnUpdate,
    SupplyReturnsMetrics,
    TemperatureExcursion,
    TemperatureExcursionCreate,
    TemperatureExcursionListResponse,
    TemperatureExcursionUpdate,
)
from app.services.clinical_supply_returns_service import get_clinical_supply_returns_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-supply-returns",
    tags=["Clinical Supply Returns"],
)


# ---------------------------------------------------------------------------
# Supply Returns
# ---------------------------------------------------------------------------


@router.get(
    "/returns",
    response_model=SupplyReturnListResponse,
    summary="List supply returns",
    description="Retrieve supply returns with optional filtering by trial, status, and reason.",
)
async def list_returns(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ReturnStatus] = Query(None, description="Filter by return status"),
    return_reason: Optional[ReturnReason] = Query(None, description="Filter by return reason"),
) -> SupplyReturnListResponse:
    svc = get_clinical_supply_returns_service()
    items = svc.list_returns(trial_id=trial_id, status=status, return_reason=return_reason)
    return SupplyReturnListResponse(items=items, total=len(items))


@router.get(
    "/returns/{return_id}",
    response_model=SupplyReturn,
    summary="Get a supply return",
)
async def get_return(return_id: str) -> SupplyReturn:
    svc = get_clinical_supply_returns_service()
    supply_return = svc.get_return(return_id)
    if supply_return is None:
        raise HTTPException(status_code=404, detail=f"Return '{return_id}' not found")
    return supply_return


@router.post(
    "/returns",
    response_model=SupplyReturn,
    status_code=201,
    summary="Create a supply return",
)
async def create_return(payload: SupplyReturnCreate) -> SupplyReturn:
    svc = get_clinical_supply_returns_service()
    return svc.create_return(payload)


@router.put(
    "/returns/{return_id}",
    response_model=SupplyReturn,
    summary="Update a supply return",
)
async def update_return(
    return_id: str, payload: SupplyReturnUpdate
) -> SupplyReturn:
    svc = get_clinical_supply_returns_service()
    updated = svc.update_return(return_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Return '{return_id}' not found")
    return updated


@router.delete(
    "/returns/{return_id}",
    status_code=204,
    summary="Delete a supply return",
)
async def delete_return(return_id: str) -> None:
    svc = get_clinical_supply_returns_service()
    deleted = svc.delete_return(return_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Return '{return_id}' not found")


# ---------------------------------------------------------------------------
# Destruction Records
# ---------------------------------------------------------------------------


@router.get(
    "/destructions",
    response_model=DestructionRecordListResponse,
    summary="List destruction records",
    description="Retrieve destruction records with optional filtering by trial and method.",
)
async def list_destructions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    destruction_method: Optional[DestructionMethod] = Query(None, description="Filter by destruction method"),
) -> DestructionRecordListResponse:
    svc = get_clinical_supply_returns_service()
    items = svc.list_destructions(trial_id=trial_id, destruction_method=destruction_method)
    return DestructionRecordListResponse(items=items, total=len(items))


@router.get(
    "/destructions/{destruction_id}",
    response_model=DestructionRecord,
    summary="Get a destruction record",
)
async def get_destruction(destruction_id: str) -> DestructionRecord:
    svc = get_clinical_supply_returns_service()
    record = svc.get_destruction(destruction_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Destruction record '{destruction_id}' not found")
    return record


@router.post(
    "/destructions",
    response_model=DestructionRecord,
    status_code=201,
    summary="Create a destruction record",
)
async def create_destruction(payload: DestructionRecordCreate) -> DestructionRecord:
    svc = get_clinical_supply_returns_service()
    return svc.create_destruction(payload)


@router.delete(
    "/destructions/{destruction_id}",
    status_code=204,
    summary="Delete a destruction record",
)
async def delete_destruction(destruction_id: str) -> None:
    svc = get_clinical_supply_returns_service()
    deleted = svc.delete_destruction(destruction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Destruction record '{destruction_id}' not found")


# ---------------------------------------------------------------------------
# Temperature Excursions
# ---------------------------------------------------------------------------


@router.get(
    "/excursions",
    response_model=TemperatureExcursionListResponse,
    summary="List temperature excursions",
    description="Retrieve temperature excursions with optional filtering by trial and severity.",
)
async def list_excursions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    severity: Optional[ExcursionSeverity] = Query(None, description="Filter by severity"),
) -> TemperatureExcursionListResponse:
    svc = get_clinical_supply_returns_service()
    items = svc.list_excursions(trial_id=trial_id, severity=severity)
    return TemperatureExcursionListResponse(items=items, total=len(items))


@router.get(
    "/excursions/{excursion_id}",
    response_model=TemperatureExcursion,
    summary="Get a temperature excursion",
)
async def get_excursion(excursion_id: str) -> TemperatureExcursion:
    svc = get_clinical_supply_returns_service()
    excursion = svc.get_excursion(excursion_id)
    if excursion is None:
        raise HTTPException(status_code=404, detail=f"Excursion '{excursion_id}' not found")
    return excursion


@router.post(
    "/excursions",
    response_model=TemperatureExcursion,
    status_code=201,
    summary="Create a temperature excursion",
)
async def create_excursion(payload: TemperatureExcursionCreate) -> TemperatureExcursion:
    svc = get_clinical_supply_returns_service()
    return svc.create_excursion(payload)


@router.put(
    "/excursions/{excursion_id}",
    response_model=TemperatureExcursion,
    summary="Update a temperature excursion",
)
async def update_excursion(
    excursion_id: str, payload: TemperatureExcursionUpdate
) -> TemperatureExcursion:
    svc = get_clinical_supply_returns_service()
    updated = svc.update_excursion(excursion_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Excursion '{excursion_id}' not found")
    return updated


@router.delete(
    "/excursions/{excursion_id}",
    status_code=204,
    summary="Delete a temperature excursion",
)
async def delete_excursion(excursion_id: str) -> None:
    svc = get_clinical_supply_returns_service()
    deleted = svc.delete_excursion(excursion_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Excursion '{excursion_id}' not found")


# ---------------------------------------------------------------------------
# Quarantine Records
# ---------------------------------------------------------------------------


@router.get(
    "/quarantines",
    response_model=QuarantineRecordListResponse,
    summary="List quarantine records",
    description="Retrieve quarantine records with optional filtering by trial and release status.",
)
async def list_quarantines(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    released: Optional[bool] = Query(None, description="Filter by release status"),
) -> QuarantineRecordListResponse:
    svc = get_clinical_supply_returns_service()
    items = svc.list_quarantines(trial_id=trial_id, released=released)
    return QuarantineRecordListResponse(items=items, total=len(items))


@router.get(
    "/quarantines/{quarantine_id}",
    response_model=QuarantineRecord,
    summary="Get a quarantine record",
)
async def get_quarantine(quarantine_id: str) -> QuarantineRecord:
    svc = get_clinical_supply_returns_service()
    record = svc.get_quarantine(quarantine_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Quarantine '{quarantine_id}' not found")
    return record


@router.post(
    "/quarantines",
    response_model=QuarantineRecord,
    status_code=201,
    summary="Create a quarantine record",
)
async def create_quarantine(payload: QuarantineRecordCreate) -> QuarantineRecord:
    svc = get_clinical_supply_returns_service()
    return svc.create_quarantine(payload)


@router.put(
    "/quarantines/{quarantine_id}",
    response_model=QuarantineRecord,
    summary="Update a quarantine record",
)
async def update_quarantine(
    quarantine_id: str, payload: QuarantineRecordUpdate
) -> QuarantineRecord:
    svc = get_clinical_supply_returns_service()
    updated = svc.update_quarantine(quarantine_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Quarantine '{quarantine_id}' not found")
    return updated


@router.delete(
    "/quarantines/{quarantine_id}",
    status_code=204,
    summary="Delete a quarantine record",
)
async def delete_quarantine(quarantine_id: str) -> None:
    svc = get_clinical_supply_returns_service()
    deleted = svc.delete_quarantine(quarantine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Quarantine '{quarantine_id}' not found")


# ---------------------------------------------------------------------------
# Drug Accountability
# ---------------------------------------------------------------------------


@router.get(
    "/accountabilities",
    response_model=DrugAccountabilityListResponse,
    summary="List drug accountability records",
    description="Retrieve drug accountability records with optional filtering by trial and result.",
)
async def list_accountabilities(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    result: Optional[ReconciliationResult] = Query(None, description="Filter by reconciliation result"),
) -> DrugAccountabilityListResponse:
    svc = get_clinical_supply_returns_service()
    items = svc.list_accountabilities(trial_id=trial_id, result=result)
    return DrugAccountabilityListResponse(items=items, total=len(items))


@router.get(
    "/accountabilities/{accountability_id}",
    response_model=DrugAccountability,
    summary="Get a drug accountability record",
)
async def get_accountability(accountability_id: str) -> DrugAccountability:
    svc = get_clinical_supply_returns_service()
    record = svc.get_accountability(accountability_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Accountability '{accountability_id}' not found")
    return record


@router.post(
    "/accountabilities",
    response_model=DrugAccountability,
    status_code=201,
    summary="Create a drug accountability record",
)
async def create_accountability(payload: DrugAccountabilityCreate) -> DrugAccountability:
    svc = get_clinical_supply_returns_service()
    return svc.create_accountability(payload)


@router.put(
    "/accountabilities/{accountability_id}",
    response_model=DrugAccountability,
    summary="Update a drug accountability record",
)
async def update_accountability(
    accountability_id: str, payload: DrugAccountabilityUpdate
) -> DrugAccountability:
    svc = get_clinical_supply_returns_service()
    updated = svc.update_accountability(accountability_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Accountability '{accountability_id}' not found")
    return updated


@router.delete(
    "/accountabilities/{accountability_id}",
    status_code=204,
    summary="Delete a drug accountability record",
)
async def delete_accountability(accountability_id: str) -> None:
    svc = get_clinical_supply_returns_service()
    deleted = svc.delete_accountability(accountability_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Accountability '{accountability_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SupplyReturnsMetrics,
    summary="Get supply returns metrics",
    description="Aggregated supply returns metrics including returns by status/reason, "
                "destruction counts, excursion severity breakdown, quarantine status, "
                "and drug accountability reconciliation stats.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> SupplyReturnsMetrics:
    svc = get_clinical_supply_returns_service()
    return svc.get_metrics(trial_id=trial_id)
