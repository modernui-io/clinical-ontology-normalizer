"""Interactive Response Technology (IRT/IWRS) API endpoints (CLINICAL-19).

Provides comprehensive IRT operations: transaction processing, drug supply
tracking and accountability, visit scheduling with window compliance, drug
assignment and resupply workflows, dose modification, unblinding, stratification
management, patient compliance tracking, and IRT operational metrics.

Endpoints:
    GET    /irt/transactions                                 - List IRT transactions
    GET    /irt/transactions/{transaction_id}                - Get single transaction
    POST   /irt/transactions                                 - Create transaction
    GET    /irt/drug-assignments                             - List drug assignments
    GET    /irt/drug-assignments/{assignment_id}             - Get single assignment
    POST   /irt/drug-assignments                             - Create drug assignment
    PUT    /irt/drug-assignments/{assignment_id}             - Update drug assignment
    GET    /irt/drug-kits                                    - List drug kits
    GET    /irt/drug-kits/{kit_number}                       - Get single drug kit
    GET    /irt/sites/{site_id}/drug-accountability          - Drug accountability summary
    GET    /irt/sites/resupply-needed                        - Sites needing resupply
    POST   /irt/drug-resupply                                - Request drug resupply
    GET    /irt/visit-schedules                              - List visit schedules
    GET    /irt/visit-schedules/{schedule_id}                - Get single visit schedule
    POST   /irt/visit-schedules                              - Create visit schedule
    POST   /irt/visit-schedules/{schedule_id}/confirm        - Confirm a visit
    POST   /irt/dose-modification                            - Request dose modification
    POST   /irt/unblinding                                   - Request unblinding
    GET    /irt/stratification                               - List stratification entries
    GET    /irt/stratification/{patient_id}                  - Get patient stratification
    POST   /irt/stratification                               - Create stratification entry
    GET    /irt/configurations                               - List IRT configurations
    GET    /irt/configurations/{trial_id}                    - Get trial configuration
    PUT    /irt/configurations/{trial_id}                    - Update trial configuration
    GET    /irt/patients/{patient_id}/compliance             - Patient compliance summary
    GET    /irt/metrics                                      - IRT dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.irt_system import (
    DoseModificationRequest,
    DrugAccountabilitySummary,
    DrugAssignment,
    DrugAssignmentCreate,
    DrugAssignmentListResponse,
    DrugAssignmentUpdate,
    DrugKit,
    DrugKitListResponse,
    DrugResupplyRequest,
    DrugSupplyStatus,
    IRTConfiguration,
    IRTConfigurationListResponse,
    IRTConfigurationUpdate,
    IRTMetrics,
    IRTTransaction,
    IRTTransactionCreate,
    IRTTransactionListResponse,
    IRTTransactionType,
    StratificationEntry,
    StratificationEntryCreate,
    StratificationEntryListResponse,
    VisitConfirmation,
    VisitSchedule,
    VisitScheduleCreate,
    VisitScheduleListResponse,
    VisitWindow,
    UnblindingRequest,
)
from app.services.irt_service import get_irt_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/irt",
    tags=["Interactive Response Technology"],
)


# ---------------------------------------------------------------------------
# IRT Transactions
# ---------------------------------------------------------------------------


@router.get(
    "/transactions",
    response_model=IRTTransactionListResponse,
    summary="List IRT transactions",
    description="Retrieve IRT transactions with optional filtering by trial, site, patient, and type.",
)
async def list_transactions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    transaction_type: Optional[IRTTransactionType] = Query(None, description="Filter by type"),
) -> IRTTransactionListResponse:
    svc = get_irt_service()
    items = svc.list_transactions(
        trial_id=trial_id, site_id=site_id,
        patient_id=patient_id, transaction_type=transaction_type,
    )
    return IRTTransactionListResponse(items=items, total=len(items))


@router.get(
    "/transactions/{transaction_id}",
    response_model=IRTTransaction,
    summary="Get an IRT transaction",
)
async def get_transaction(transaction_id: str) -> IRTTransaction:
    svc = get_irt_service()
    tx = svc.get_transaction(transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")
    return tx


@router.post(
    "/transactions",
    response_model=IRTTransaction,
    status_code=201,
    summary="Create an IRT transaction",
    description="Record a new IRT transaction. The system generates a confirmation number and response.",
)
async def create_transaction(payload: IRTTransactionCreate) -> IRTTransaction:
    svc = get_irt_service()
    return svc.create_transaction(payload)


# ---------------------------------------------------------------------------
# Drug Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/drug-assignments",
    response_model=DrugAssignmentListResponse,
    summary="List drug assignments",
    description="Retrieve drug assignments with optional filtering by patient and treatment arm.",
)
async def list_drug_assignments(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    treatment_arm: Optional[str] = Query(None, description="Filter by treatment arm"),
) -> DrugAssignmentListResponse:
    svc = get_irt_service()
    items = svc.list_drug_assignments(patient_id=patient_id, treatment_arm=treatment_arm)
    return DrugAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/drug-assignments/{assignment_id}",
    response_model=DrugAssignment,
    summary="Get a drug assignment",
)
async def get_drug_assignment(assignment_id: str) -> DrugAssignment:
    svc = get_irt_service()
    da = svc.get_drug_assignment(assignment_id)
    if da is None:
        raise HTTPException(status_code=404, detail=f"Drug assignment '{assignment_id}' not found")
    return da


@router.post(
    "/drug-assignments",
    response_model=DrugAssignment,
    status_code=201,
    summary="Create a drug assignment",
    description="Assign a drug kit to a patient. Creates an associated IRT transaction.",
)
async def create_drug_assignment(payload: DrugAssignmentCreate) -> DrugAssignment:
    svc = get_irt_service()
    return svc.create_drug_assignment(payload)


@router.put(
    "/drug-assignments/{assignment_id}",
    response_model=DrugAssignment,
    summary="Update a drug assignment",
    description="Update drug assignment details such as return date and compliance percentage.",
)
async def update_drug_assignment(
    assignment_id: str, payload: DrugAssignmentUpdate
) -> DrugAssignment:
    svc = get_irt_service()
    updated = svc.update_drug_assignment(assignment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Drug assignment '{assignment_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Drug Kits & Accountability
# ---------------------------------------------------------------------------


@router.get(
    "/drug-kits",
    response_model=DrugKitListResponse,
    summary="List drug kits",
    description="Retrieve drug supply kits with optional filtering by site, trial, and status.",
)
async def list_drug_kits(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[DrugSupplyStatus] = Query(None, description="Filter by status"),
) -> DrugKitListResponse:
    svc = get_irt_service()
    items = svc.list_drug_kits(site_id=site_id, trial_id=trial_id, status=status)
    return DrugKitListResponse(items=items, total=len(items))


@router.get(
    "/drug-kits/{kit_number}",
    response_model=DrugKit,
    summary="Get a drug kit",
)
async def get_drug_kit(kit_number: str) -> DrugKit:
    svc = get_irt_service()
    kit = svc.get_drug_kit(kit_number)
    if kit is None:
        raise HTTPException(status_code=404, detail=f"Drug kit '{kit_number}' not found")
    return kit


@router.get(
    "/sites/{site_id}/drug-accountability",
    response_model=DrugAccountabilitySummary,
    summary="Get drug accountability for a site",
    description="Retrieve drug accountability summary including available, dispensed, returned, and destroyed kits.",
)
async def get_drug_accountability(site_id: str) -> DrugAccountabilitySummary:
    svc = get_irt_service()
    summary = svc.get_drug_accountability(site_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"No drug kits found for site '{site_id}'")
    return summary


@router.get(
    "/sites/resupply-needed",
    response_model=list[DrugAccountabilitySummary],
    summary="Get sites needing drug resupply",
    description="Retrieve sites where drug supply is below the configured buffer threshold.",
)
async def get_sites_needing_resupply() -> list[DrugAccountabilitySummary]:
    svc = get_irt_service()
    return svc.get_sites_needing_resupply()


@router.post(
    "/drug-resupply",
    response_model=IRTTransaction,
    status_code=201,
    summary="Request drug resupply",
    description="Request a drug resupply for a site. Creates new drug kits and an IRT transaction.",
)
async def request_drug_resupply(payload: DrugResupplyRequest) -> IRTTransaction:
    svc = get_irt_service()
    return svc.request_drug_resupply(payload)


# ---------------------------------------------------------------------------
# Visit Schedules
# ---------------------------------------------------------------------------


@router.get(
    "/visit-schedules",
    response_model=VisitScheduleListResponse,
    summary="List visit schedules",
    description="Retrieve visit schedules with optional filtering by patient, trial, and window status.",
)
async def list_visit_schedules(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    window_status: Optional[VisitWindow] = Query(None, description="Filter by window status"),
) -> VisitScheduleListResponse:
    svc = get_irt_service()
    items = svc.list_visit_schedules(
        patient_id=patient_id, trial_id=trial_id, window_status=window_status,
    )
    return VisitScheduleListResponse(items=items, total=len(items))


@router.get(
    "/visit-schedules/{schedule_id}",
    response_model=VisitSchedule,
    summary="Get a visit schedule",
)
async def get_visit_schedule(schedule_id: str) -> VisitSchedule:
    svc = get_irt_service()
    vs = svc.get_visit_schedule(schedule_id)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Visit schedule '{schedule_id}' not found")
    return vs


@router.post(
    "/visit-schedules",
    response_model=VisitSchedule,
    status_code=201,
    summary="Create a visit schedule",
    description="Create a new visit schedule entry with window boundaries.",
)
async def create_visit_schedule(payload: VisitScheduleCreate) -> VisitSchedule:
    svc = get_irt_service()
    return svc.create_visit_schedule(payload)


@router.post(
    "/visit-schedules/{schedule_id}/confirm",
    response_model=VisitSchedule,
    summary="Confirm a visit",
    description="Confirm that a visit occurred and calculate window compliance (early, on_time, late).",
)
async def confirm_visit(schedule_id: str, payload: VisitConfirmation) -> VisitSchedule:
    svc = get_irt_service()
    try:
        result = svc.confirm_visit(schedule_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Visit schedule '{schedule_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Dose Modification & Unblinding
# ---------------------------------------------------------------------------


@router.post(
    "/dose-modification",
    response_model=IRTTransaction,
    status_code=201,
    summary="Request dose modification",
    description="Process a dose modification request. Records the change and issues new dispensing instructions.",
)
async def request_dose_modification(payload: DoseModificationRequest) -> IRTTransaction:
    svc = get_irt_service()
    return svc.request_dose_modification(payload)


@router.post(
    "/unblinding",
    response_model=IRTTransaction,
    status_code=201,
    summary="Request emergency unblinding",
    description="Process an emergency unblinding request. Reveals treatment assignment and initiates safety review.",
)
async def request_unblinding(payload: UnblindingRequest) -> IRTTransaction:
    svc = get_irt_service()
    return svc.request_unblinding(payload)


# ---------------------------------------------------------------------------
# Stratification
# ---------------------------------------------------------------------------


@router.get(
    "/stratification",
    response_model=StratificationEntryListResponse,
    summary="List stratification entries",
    description="Retrieve patient stratification entries with optional filtering by stratum ID.",
)
async def list_stratification_entries(
    stratum_id: Optional[str] = Query(None, description="Filter by stratum ID"),
) -> StratificationEntryListResponse:
    svc = get_irt_service()
    items = svc.list_stratification_entries(stratum_id=stratum_id)
    return StratificationEntryListResponse(items=items, total=len(items))


@router.get(
    "/stratification/{patient_id}",
    response_model=StratificationEntry,
    summary="Get patient stratification",
)
async def get_stratification_entry(patient_id: str) -> StratificationEntry:
    svc = get_irt_service()
    entry = svc.get_stratification_entry(patient_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Stratification entry for '{patient_id}' not found")
    return entry


@router.post(
    "/stratification",
    response_model=StratificationEntry,
    status_code=201,
    summary="Create stratification entry",
    description="Create a stratification entry for a patient with factor values.",
)
async def create_stratification_entry(payload: StratificationEntryCreate) -> StratificationEntry:
    svc = get_irt_service()
    return svc.create_stratification_entry(payload)


# ---------------------------------------------------------------------------
# IRT Configurations
# ---------------------------------------------------------------------------


@router.get(
    "/configurations",
    response_model=IRTConfigurationListResponse,
    summary="List IRT configurations",
    description="Retrieve IRT system configurations for all trials.",
)
async def list_configurations() -> IRTConfigurationListResponse:
    svc = get_irt_service()
    items = svc.list_configurations()
    return IRTConfigurationListResponse(items=items, total=len(items))


@router.get(
    "/configurations/{trial_id}",
    response_model=IRTConfiguration,
    summary="Get trial IRT configuration",
)
async def get_configuration(trial_id: str) -> IRTConfiguration:
    svc = get_irt_service()
    cfg = svc.get_configuration(trial_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Configuration for trial '{trial_id}' not found")
    return cfg


@router.put(
    "/configurations/{trial_id}",
    response_model=IRTConfiguration,
    summary="Update trial IRT configuration",
    description="Update IRT configuration parameters for a trial.",
)
async def update_configuration(
    trial_id: str, payload: IRTConfigurationUpdate
) -> IRTConfiguration:
    svc = get_irt_service()
    updated = svc.update_configuration(trial_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Configuration for trial '{trial_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Patient Compliance
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/compliance",
    response_model=dict,
    summary="Get patient compliance summary",
    description="Retrieve drug and visit compliance summary for a specific patient.",
)
async def get_patient_compliance(patient_id: str) -> dict:
    svc = get_irt_service()
    return svc.get_patient_compliance(patient_id)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=IRTMetrics,
    summary="Get IRT dashboard metrics",
    description="Aggregated IRT operational metrics across all trials and sites.",
)
async def get_metrics() -> IRTMetrics:
    svc = get_irt_service()
    return svc.get_metrics()
