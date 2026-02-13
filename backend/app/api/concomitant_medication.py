"""Concomitant Medication Tracking API endpoints (CMT-TRK).

Provides comprehensive concomitant medication operations: medication records,
drug interaction checks, prohibited medication alerts, medication reconciliation
tasks, and concomitant medication metrics.

Endpoints:
    GET    /concomitant-medication/medication-records                         - List medication records
    GET    /concomitant-medication/medication-records/{record_id}             - Get single record
    POST   /concomitant-medication/medication-records                         - Create record
    PUT    /concomitant-medication/medication-records/{record_id}             - Update record
    DELETE /concomitant-medication/medication-records/{record_id}             - Delete record
    GET    /concomitant-medication/drug-interaction-checks                    - List interaction checks
    GET    /concomitant-medication/drug-interaction-checks/{check_id}         - Get single check
    POST   /concomitant-medication/drug-interaction-checks                    - Create check
    PUT    /concomitant-medication/drug-interaction-checks/{check_id}         - Update check
    DELETE /concomitant-medication/drug-interaction-checks/{check_id}         - Delete check
    GET    /concomitant-medication/prohibited-medication-alerts               - List alerts
    GET    /concomitant-medication/prohibited-medication-alerts/{alert_id}    - Get single alert
    POST   /concomitant-medication/prohibited-medication-alerts               - Create alert
    PUT    /concomitant-medication/prohibited-medication-alerts/{alert_id}    - Update alert
    DELETE /concomitant-medication/prohibited-medication-alerts/{alert_id}    - Delete alert
    GET    /concomitant-medication/medication-reconciliations                 - List reconciliations
    GET    /concomitant-medication/medication-reconciliations/{recon_id}      - Get single reconciliation
    POST   /concomitant-medication/medication-reconciliations                 - Create reconciliation
    PUT    /concomitant-medication/medication-reconciliations/{recon_id}      - Update reconciliation
    DELETE /concomitant-medication/medication-reconciliations/{recon_id}      - Delete reconciliation
    GET    /concomitant-medication/metrics                                    - Concomitant medication metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.concomitant_medication import (
    AlertPriority,
    AlertStatus,
    ConcomitantMedicationMetrics,
    DrugInteractionCheck,
    DrugInteractionCheckCreate,
    DrugInteractionCheckListResponse,
    DrugInteractionCheckUpdate,
    InteractionSeverity,
    MedicationRecord,
    MedicationRecordCreate,
    MedicationRecordListResponse,
    MedicationRecordUpdate,
    MedicationReconciliation,
    MedicationReconciliationCreate,
    MedicationReconciliationListResponse,
    MedicationReconciliationUpdate,
    MedicationStatus,
    ProhibitedMedicationAlert,
    ProhibitedMedicationAlertCreate,
    ProhibitedMedicationAlertListResponse,
    ProhibitedMedicationAlertUpdate,
    ReconciliationOutcome,
)
from app.services.concomitant_medication_service import get_concomitant_medication_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/concomitant-medication",
    tags=["Concomitant Medication"],
)


# ---------------------------------------------------------------------------
# Medication Records
# ---------------------------------------------------------------------------


@router.get(
    "/medication-records",
    response_model=MedicationRecordListResponse,
    summary="List medication records",
    description="Retrieve medication records with optional filtering by trial, status, and subject.",
)
async def list_medication_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    medication_status: Optional[MedicationStatus] = Query(None, description="Filter by medication status"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> MedicationRecordListResponse:
    svc = get_concomitant_medication_service()
    items = svc.list_medication_records(
        trial_id=trial_id, medication_status=medication_status, subject_id=subject_id
    )
    return MedicationRecordListResponse(items=items, total=len(items))


@router.get(
    "/medication-records/{record_id}",
    response_model=MedicationRecord,
    summary="Get a medication record",
)
async def get_medication_record(record_id: str) -> MedicationRecord:
    svc = get_concomitant_medication_service()
    record = svc.get_medication_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Medication record '{record_id}' not found")
    return record


@router.post(
    "/medication-records",
    response_model=MedicationRecord,
    status_code=201,
    summary="Create a medication record",
)
async def create_medication_record(payload: MedicationRecordCreate) -> MedicationRecord:
    svc = get_concomitant_medication_service()
    return svc.create_medication_record(payload)


@router.put(
    "/medication-records/{record_id}",
    response_model=MedicationRecord,
    summary="Update a medication record",
)
async def update_medication_record(
    record_id: str, payload: MedicationRecordUpdate
) -> MedicationRecord:
    svc = get_concomitant_medication_service()
    updated = svc.update_medication_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Medication record '{record_id}' not found")
    return updated


@router.delete(
    "/medication-records/{record_id}",
    status_code=204,
    summary="Delete a medication record",
)
async def delete_medication_record(record_id: str) -> None:
    svc = get_concomitant_medication_service()
    deleted = svc.delete_medication_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Medication record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Drug Interaction Checks
# ---------------------------------------------------------------------------


@router.get(
    "/drug-interaction-checks",
    response_model=DrugInteractionCheckListResponse,
    summary="List drug interaction checks",
    description="Retrieve drug interaction checks with optional filtering by trial, severity, and subject.",
)
async def list_drug_interaction_checks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    interaction_severity: Optional[InteractionSeverity] = Query(None, description="Filter by interaction severity"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> DrugInteractionCheckListResponse:
    svc = get_concomitant_medication_service()
    items = svc.list_drug_interaction_checks(
        trial_id=trial_id, interaction_severity=interaction_severity, subject_id=subject_id
    )
    return DrugInteractionCheckListResponse(items=items, total=len(items))


@router.get(
    "/drug-interaction-checks/{check_id}",
    response_model=DrugInteractionCheck,
    summary="Get a drug interaction check",
)
async def get_drug_interaction_check(check_id: str) -> DrugInteractionCheck:
    svc = get_concomitant_medication_service()
    record = svc.get_drug_interaction_check(check_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Drug interaction check '{check_id}' not found"
        )
    return record


@router.post(
    "/drug-interaction-checks",
    response_model=DrugInteractionCheck,
    status_code=201,
    summary="Create a drug interaction check",
)
async def create_drug_interaction_check(
    payload: DrugInteractionCheckCreate,
) -> DrugInteractionCheck:
    svc = get_concomitant_medication_service()
    return svc.create_drug_interaction_check(payload)


@router.put(
    "/drug-interaction-checks/{check_id}",
    response_model=DrugInteractionCheck,
    summary="Update a drug interaction check",
)
async def update_drug_interaction_check(
    check_id: str, payload: DrugInteractionCheckUpdate
) -> DrugInteractionCheck:
    svc = get_concomitant_medication_service()
    updated = svc.update_drug_interaction_check(check_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Drug interaction check '{check_id}' not found"
        )
    return updated


@router.delete(
    "/drug-interaction-checks/{check_id}",
    status_code=204,
    summary="Delete a drug interaction check",
)
async def delete_drug_interaction_check(check_id: str) -> None:
    svc = get_concomitant_medication_service()
    deleted = svc.delete_drug_interaction_check(check_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Drug interaction check '{check_id}' not found"
        )


# ---------------------------------------------------------------------------
# Prohibited Medication Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/prohibited-medication-alerts",
    response_model=ProhibitedMedicationAlertListResponse,
    summary="List prohibited medication alerts",
    description="Retrieve prohibited medication alerts with optional filtering by trial, priority, and status.",
)
async def list_prohibited_medication_alerts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    alert_priority: Optional[AlertPriority] = Query(None, description="Filter by alert priority"),
    alert_status: Optional[AlertStatus] = Query(None, description="Filter by alert status"),
) -> ProhibitedMedicationAlertListResponse:
    svc = get_concomitant_medication_service()
    items = svc.list_prohibited_medication_alerts(
        trial_id=trial_id, alert_priority=alert_priority, alert_status=alert_status
    )
    return ProhibitedMedicationAlertListResponse(items=items, total=len(items))


@router.get(
    "/prohibited-medication-alerts/{alert_id}",
    response_model=ProhibitedMedicationAlert,
    summary="Get a prohibited medication alert",
)
async def get_prohibited_medication_alert(alert_id: str) -> ProhibitedMedicationAlert:
    svc = get_concomitant_medication_service()
    record = svc.get_prohibited_medication_alert(alert_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Prohibited medication alert '{alert_id}' not found",
        )
    return record


@router.post(
    "/prohibited-medication-alerts",
    response_model=ProhibitedMedicationAlert,
    status_code=201,
    summary="Create a prohibited medication alert",
)
async def create_prohibited_medication_alert(
    payload: ProhibitedMedicationAlertCreate,
) -> ProhibitedMedicationAlert:
    svc = get_concomitant_medication_service()
    return svc.create_prohibited_medication_alert(payload)


@router.put(
    "/prohibited-medication-alerts/{alert_id}",
    response_model=ProhibitedMedicationAlert,
    summary="Update a prohibited medication alert",
)
async def update_prohibited_medication_alert(
    alert_id: str, payload: ProhibitedMedicationAlertUpdate
) -> ProhibitedMedicationAlert:
    svc = get_concomitant_medication_service()
    updated = svc.update_prohibited_medication_alert(alert_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Prohibited medication alert '{alert_id}' not found",
        )
    return updated


@router.delete(
    "/prohibited-medication-alerts/{alert_id}",
    status_code=204,
    summary="Delete a prohibited medication alert",
)
async def delete_prohibited_medication_alert(alert_id: str) -> None:
    svc = get_concomitant_medication_service()
    deleted = svc.delete_prohibited_medication_alert(alert_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Prohibited medication alert '{alert_id}' not found",
        )


# ---------------------------------------------------------------------------
# Medication Reconciliations
# ---------------------------------------------------------------------------


@router.get(
    "/medication-reconciliations",
    response_model=MedicationReconciliationListResponse,
    summary="List medication reconciliations",
    description="Retrieve medication reconciliations with optional filtering by trial, outcome, and subject.",
)
async def list_medication_reconciliations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    reconciliation_outcome: Optional[ReconciliationOutcome] = Query(
        None, description="Filter by reconciliation outcome"
    ),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> MedicationReconciliationListResponse:
    svc = get_concomitant_medication_service()
    items = svc.list_medication_reconciliations(
        trial_id=trial_id,
        reconciliation_outcome=reconciliation_outcome,
        subject_id=subject_id,
    )
    return MedicationReconciliationListResponse(items=items, total=len(items))


@router.get(
    "/medication-reconciliations/{reconciliation_id}",
    response_model=MedicationReconciliation,
    summary="Get a medication reconciliation",
)
async def get_medication_reconciliation(
    reconciliation_id: str,
) -> MedicationReconciliation:
    svc = get_concomitant_medication_service()
    record = svc.get_medication_reconciliation(reconciliation_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Medication reconciliation '{reconciliation_id}' not found",
        )
    return record


@router.post(
    "/medication-reconciliations",
    response_model=MedicationReconciliation,
    status_code=201,
    summary="Create a medication reconciliation",
)
async def create_medication_reconciliation(
    payload: MedicationReconciliationCreate,
) -> MedicationReconciliation:
    svc = get_concomitant_medication_service()
    return svc.create_medication_reconciliation(payload)


@router.put(
    "/medication-reconciliations/{reconciliation_id}",
    response_model=MedicationReconciliation,
    summary="Update a medication reconciliation",
)
async def update_medication_reconciliation(
    reconciliation_id: str, payload: MedicationReconciliationUpdate
) -> MedicationReconciliation:
    svc = get_concomitant_medication_service()
    updated = svc.update_medication_reconciliation(reconciliation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Medication reconciliation '{reconciliation_id}' not found",
        )
    return updated


@router.delete(
    "/medication-reconciliations/{reconciliation_id}",
    status_code=204,
    summary="Delete a medication reconciliation",
)
async def delete_medication_reconciliation(reconciliation_id: str) -> None:
    svc = get_concomitant_medication_service()
    deleted = svc.delete_medication_reconciliation(reconciliation_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Medication reconciliation '{reconciliation_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ConcomitantMedicationMetrics,
    summary="Get concomitant medication metrics",
    description="Aggregated metrics across all concomitant medication operations.",
)
async def get_metrics() -> ConcomitantMedicationMetrics:
    svc = get_concomitant_medication_service()
    return svc.get_metrics()
