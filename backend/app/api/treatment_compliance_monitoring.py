"""Treatment Compliance Monitoring (TCM-MON) API endpoints.

Provides treatment compliance monitoring operations: dosing records, compliance
assessments, medication accountability logs, treatment interruption events,
and aggregated metrics.

Endpoints:
    GET    /treatment-compliance-monitoring/dosing-records                          - List dosing records
    GET    /treatment-compliance-monitoring/dosing-records/{record_id}              - Get single dosing record
    POST   /treatment-compliance-monitoring/dosing-records                          - Create dosing record
    PUT    /treatment-compliance-monitoring/dosing-records/{record_id}              - Update dosing record
    DELETE /treatment-compliance-monitoring/dosing-records/{record_id}              - Delete dosing record
    GET    /treatment-compliance-monitoring/compliance-assessments                  - List compliance assessments
    GET    /treatment-compliance-monitoring/compliance-assessments/{assessment_id}  - Get single compliance assessment
    POST   /treatment-compliance-monitoring/compliance-assessments                  - Create compliance assessment
    PUT    /treatment-compliance-monitoring/compliance-assessments/{assessment_id}  - Update compliance assessment
    DELETE /treatment-compliance-monitoring/compliance-assessments/{assessment_id}  - Delete compliance assessment
    GET    /treatment-compliance-monitoring/accountability-logs                     - List medication accountability logs
    GET    /treatment-compliance-monitoring/accountability-logs/{log_id}            - Get single accountability log
    POST   /treatment-compliance-monitoring/accountability-logs                     - Create accountability log
    PUT    /treatment-compliance-monitoring/accountability-logs/{log_id}            - Update accountability log
    DELETE /treatment-compliance-monitoring/accountability-logs/{log_id}            - Delete accountability log
    GET    /treatment-compliance-monitoring/interruption-events                     - List treatment interruption events
    GET    /treatment-compliance-monitoring/interruption-events/{event_id}          - Get single interruption event
    POST   /treatment-compliance-monitoring/interruption-events                     - Create interruption event
    PUT    /treatment-compliance-monitoring/interruption-events/{event_id}          - Update interruption event
    DELETE /treatment-compliance-monitoring/interruption-events/{event_id}          - Delete interruption event
    GET    /treatment-compliance-monitoring/metrics                                 - Treatment compliance metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.treatment_compliance_monitoring import (
    ComplianceAssessment,
    ComplianceAssessmentCreate,
    ComplianceAssessmentListResponse,
    ComplianceAssessmentUpdate,
    DosingRecord,
    DosingRecordCreate,
    DosingRecordListResponse,
    DosingRecordUpdate,
    MedicationAccountabilityLog,
    MedicationAccountabilityLogCreate,
    MedicationAccountabilityLogListResponse,
    MedicationAccountabilityLogUpdate,
    TreatmentComplianceMetrics,
    TreatmentInterruptionEvent,
    TreatmentInterruptionEventCreate,
    TreatmentInterruptionEventListResponse,
    TreatmentInterruptionEventUpdate,
)
from app.services.treatment_compliance_monitoring_service import (
    get_treatment_compliance_monitoring_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/treatment-compliance-monitoring",
    tags=["Treatment Compliance Monitoring"],
)


# ---------------------------------------------------------------------------
# Dosing Records
# ---------------------------------------------------------------------------


@router.get(
    "/dosing-records",
    response_model=DosingRecordListResponse,
    summary="List dosing records",
    description="Retrieve dosing records with optional filtering by trial ID.",
)
async def list_dosing_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DosingRecordListResponse:
    svc = get_treatment_compliance_monitoring_service()
    items = svc.list_dosing_records(trial_id=trial_id)
    return DosingRecordListResponse(items=items, total=len(items))


@router.get(
    "/dosing-records/{record_id}",
    response_model=DosingRecord,
    summary="Get a dosing record",
)
async def get_dosing_record(record_id: str) -> DosingRecord:
    svc = get_treatment_compliance_monitoring_service()
    record = svc.get_dosing_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Dosing record '{record_id}' not found")
    return record


@router.post(
    "/dosing-records",
    response_model=DosingRecord,
    status_code=201,
    summary="Create a dosing record",
)
async def create_dosing_record(payload: DosingRecordCreate) -> DosingRecord:
    svc = get_treatment_compliance_monitoring_service()
    return svc.create_dosing_record(payload)


@router.put(
    "/dosing-records/{record_id}",
    response_model=DosingRecord,
    summary="Update a dosing record",
)
async def update_dosing_record(record_id: str, payload: DosingRecordUpdate) -> DosingRecord:
    svc = get_treatment_compliance_monitoring_service()
    updated = svc.update_dosing_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Dosing record '{record_id}' not found")
    return updated


@router.delete(
    "/dosing-records/{record_id}",
    status_code=204,
    summary="Delete a dosing record",
)
async def delete_dosing_record(record_id: str) -> None:
    svc = get_treatment_compliance_monitoring_service()
    deleted = svc.delete_dosing_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dosing record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Compliance Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/compliance-assessments",
    response_model=ComplianceAssessmentListResponse,
    summary="List compliance assessments",
    description="Retrieve compliance assessments with optional filtering by trial ID.",
)
async def list_compliance_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ComplianceAssessmentListResponse:
    svc = get_treatment_compliance_monitoring_service()
    items = svc.list_compliance_assessments(trial_id=trial_id)
    return ComplianceAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/compliance-assessments/{assessment_id}",
    response_model=ComplianceAssessment,
    summary="Get a compliance assessment",
)
async def get_compliance_assessment(assessment_id: str) -> ComplianceAssessment:
    svc = get_treatment_compliance_monitoring_service()
    assessment = svc.get_compliance_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Compliance assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/compliance-assessments",
    response_model=ComplianceAssessment,
    status_code=201,
    summary="Create a compliance assessment",
)
async def create_compliance_assessment(payload: ComplianceAssessmentCreate) -> ComplianceAssessment:
    svc = get_treatment_compliance_monitoring_service()
    return svc.create_compliance_assessment(payload)


@router.put(
    "/compliance-assessments/{assessment_id}",
    response_model=ComplianceAssessment,
    summary="Update a compliance assessment",
)
async def update_compliance_assessment(assessment_id: str, payload: ComplianceAssessmentUpdate) -> ComplianceAssessment:
    svc = get_treatment_compliance_monitoring_service()
    updated = svc.update_compliance_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Compliance assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/compliance-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a compliance assessment",
)
async def delete_compliance_assessment(assessment_id: str) -> None:
    svc = get_treatment_compliance_monitoring_service()
    deleted = svc.delete_compliance_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Compliance assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Medication Accountability Logs
# ---------------------------------------------------------------------------


@router.get(
    "/accountability-logs",
    response_model=MedicationAccountabilityLogListResponse,
    summary="List medication accountability logs",
    description="Retrieve medication accountability logs with optional filtering by trial ID.",
)
async def list_medication_accountability_logs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> MedicationAccountabilityLogListResponse:
    svc = get_treatment_compliance_monitoring_service()
    items = svc.list_medication_accountability_logs(trial_id=trial_id)
    return MedicationAccountabilityLogListResponse(items=items, total=len(items))


@router.get(
    "/accountability-logs/{log_id}",
    response_model=MedicationAccountabilityLog,
    summary="Get a medication accountability log",
)
async def get_medication_accountability_log(log_id: str) -> MedicationAccountabilityLog:
    svc = get_treatment_compliance_monitoring_service()
    log = svc.get_medication_accountability_log(log_id)
    if log is None:
        raise HTTPException(status_code=404, detail=f"Medication accountability log '{log_id}' not found")
    return log


@router.post(
    "/accountability-logs",
    response_model=MedicationAccountabilityLog,
    status_code=201,
    summary="Create a medication accountability log",
)
async def create_medication_accountability_log(payload: MedicationAccountabilityLogCreate) -> MedicationAccountabilityLog:
    svc = get_treatment_compliance_monitoring_service()
    return svc.create_medication_accountability_log(payload)


@router.put(
    "/accountability-logs/{log_id}",
    response_model=MedicationAccountabilityLog,
    summary="Update a medication accountability log",
)
async def update_medication_accountability_log(log_id: str, payload: MedicationAccountabilityLogUpdate) -> MedicationAccountabilityLog:
    svc = get_treatment_compliance_monitoring_service()
    updated = svc.update_medication_accountability_log(log_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Medication accountability log '{log_id}' not found")
    return updated


@router.delete(
    "/accountability-logs/{log_id}",
    status_code=204,
    summary="Delete a medication accountability log",
)
async def delete_medication_accountability_log(log_id: str) -> None:
    svc = get_treatment_compliance_monitoring_service()
    deleted = svc.delete_medication_accountability_log(log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Medication accountability log '{log_id}' not found")


# ---------------------------------------------------------------------------
# Treatment Interruption Events
# ---------------------------------------------------------------------------


@router.get(
    "/interruption-events",
    response_model=TreatmentInterruptionEventListResponse,
    summary="List treatment interruption events",
    description="Retrieve treatment interruption events with optional filtering by trial ID.",
)
async def list_treatment_interruption_events(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> TreatmentInterruptionEventListResponse:
    svc = get_treatment_compliance_monitoring_service()
    items = svc.list_treatment_interruption_events(trial_id=trial_id)
    return TreatmentInterruptionEventListResponse(items=items, total=len(items))


@router.get(
    "/interruption-events/{event_id}",
    response_model=TreatmentInterruptionEvent,
    summary="Get a treatment interruption event",
)
async def get_treatment_interruption_event(event_id: str) -> TreatmentInterruptionEvent:
    svc = get_treatment_compliance_monitoring_service()
    event = svc.get_treatment_interruption_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Treatment interruption event '{event_id}' not found")
    return event


@router.post(
    "/interruption-events",
    response_model=TreatmentInterruptionEvent,
    status_code=201,
    summary="Create a treatment interruption event",
)
async def create_treatment_interruption_event(payload: TreatmentInterruptionEventCreate) -> TreatmentInterruptionEvent:
    svc = get_treatment_compliance_monitoring_service()
    return svc.create_treatment_interruption_event(payload)


@router.put(
    "/interruption-events/{event_id}",
    response_model=TreatmentInterruptionEvent,
    summary="Update a treatment interruption event",
)
async def update_treatment_interruption_event(event_id: str, payload: TreatmentInterruptionEventUpdate) -> TreatmentInterruptionEvent:
    svc = get_treatment_compliance_monitoring_service()
    updated = svc.update_treatment_interruption_event(event_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Treatment interruption event '{event_id}' not found")
    return updated


@router.delete(
    "/interruption-events/{event_id}",
    status_code=204,
    summary="Delete a treatment interruption event",
)
async def delete_treatment_interruption_event(event_id: str) -> None:
    svc = get_treatment_compliance_monitoring_service()
    deleted = svc.delete_treatment_interruption_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Treatment interruption event '{event_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=TreatmentComplianceMetrics,
    summary="Get treatment compliance metrics",
    description="Aggregated treatment compliance metrics across all entities, optionally filtered by trial ID.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> TreatmentComplianceMetrics:
    svc = get_treatment_compliance_monitoring_service()
    return svc.get_metrics(trial_id=trial_id)
