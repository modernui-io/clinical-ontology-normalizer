"""Patient Stipend Management API endpoints.

Manages patient compensation for clinical trial participation including stipend
schedules, payment processing, tax reporting, travel reimbursements, and
compliance with fair market value (FMV) guidelines.

Endpoints:
    GET    /patient-stipends/schedules                                 - List stipend schedules
    GET    /patient-stipends/schedules/{schedule_id}                   - Get single schedule
    POST   /patient-stipends/schedules                                 - Create schedule
    PUT    /patient-stipends/schedules/{schedule_id}                   - Update schedule
    DELETE /patient-stipends/schedules/{schedule_id}                   - Delete schedule
    GET    /patient-stipends/stipends                                  - List patient stipends
    GET    /patient-stipends/stipends/{stipend_id}                     - Get single stipend
    POST   /patient-stipends/stipends                                  - Create stipend
    PUT    /patient-stipends/stipends/{stipend_id}                     - Update stipend
    DELETE /patient-stipends/stipends/{stipend_id}                     - Delete stipend
    POST   /patient-stipends/stipends/{stipend_id}/process-payment     - Process payment
    POST   /patient-stipends/stipends/{stipend_id}/submit-receipt      - Submit receipt
    POST   /patient-stipends/stipends/{stipend_id}/verify-receipt      - Verify receipt
    GET    /patient-stipends/travel                                    - List travel reimbursements
    GET    /patient-stipends/travel/{reimbursement_id}                 - Get single reimbursement
    POST   /patient-stipends/travel                                    - Create travel reimbursement
    PUT    /patient-stipends/travel/{reimbursement_id}                 - Update travel reimbursement
    DELETE /patient-stipends/travel/{reimbursement_id}                 - Delete travel reimbursement
    GET    /patient-stipends/tax-records                               - List tax records
    GET    /patient-stipends/tax-records/{tax_record_id}               - Get single tax record
    GET    /patient-stipends/tax-records/check-threshold               - Check tax threshold
    GET    /patient-stipends/patients/{patient_id}/summary             - Get patient summary
    GET    /patient-stipends/metrics                                   - Get stipend metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_stipend import (
    PatientPaymentSummary,
    PatientStipend,
    PatientStipendCreate,
    PatientStipendListResponse,
    PatientStipendUpdate,
    ProcessPaymentRequest,
    ReceiptSubmission,
    StipendMetrics,
    StipendSchedule,
    StipendScheduleCreate,
    StipendScheduleListResponse,
    StipendScheduleUpdate,
    StipendStatus,
    StipendType,
    TaxRecord,
    TaxRecordListResponse,
    TravelReimbursement,
    TravelReimbursementCreate,
    TravelReimbursementListResponse,
    TravelReimbursementUpdate,
)
from app.services.patient_stipend_service import get_patient_stipend_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-stipends",
    tags=["Patient Stipends"],
)


# ---------------------------------------------------------------------------
# Stipend Schedule Management
# ---------------------------------------------------------------------------


@router.get(
    "/schedules",
    response_model=StipendScheduleListResponse,
    summary="List stipend schedules",
    description="Retrieve stipend schedule templates with optional filtering by trial and type.",
)
async def list_schedules(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    stipend_type: Optional[StipendType] = Query(None, description="Filter by stipend type"),
) -> StipendScheduleListResponse:
    svc = get_patient_stipend_service()
    items = svc.list_schedules(trial_id=trial_id, stipend_type=stipend_type)
    return StipendScheduleListResponse(items=items, total=len(items))


@router.get(
    "/schedules/{schedule_id}",
    response_model=StipendSchedule,
    summary="Get a stipend schedule",
)
async def get_schedule(schedule_id: str) -> StipendSchedule:
    svc = get_patient_stipend_service()
    schedule = svc.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return schedule


@router.post(
    "/schedules",
    response_model=StipendSchedule,
    status_code=201,
    summary="Create a stipend schedule",
)
async def create_schedule(payload: StipendScheduleCreate) -> StipendSchedule:
    svc = get_patient_stipend_service()
    return svc.create_schedule(payload)


@router.put(
    "/schedules/{schedule_id}",
    response_model=StipendSchedule,
    summary="Update a stipend schedule",
)
async def update_schedule(schedule_id: str, payload: StipendScheduleUpdate) -> StipendSchedule:
    svc = get_patient_stipend_service()
    updated = svc.update_schedule(schedule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return updated


@router.delete(
    "/schedules/{schedule_id}",
    status_code=204,
    summary="Delete a stipend schedule",
)
async def delete_schedule(schedule_id: str) -> None:
    svc = get_patient_stipend_service()
    deleted = svc.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")


# ---------------------------------------------------------------------------
# Patient Stipend Management
# ---------------------------------------------------------------------------


@router.get(
    "/stipends",
    response_model=PatientStipendListResponse,
    summary="List patient stipends",
    description="Retrieve patient stipend payments with optional filtering by patient, trial, site, status, and type.",
)
async def list_stipends(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[StipendStatus] = Query(None, description="Filter by payment status"),
    stipend_type: Optional[StipendType] = Query(None, description="Filter by stipend type"),
) -> PatientStipendListResponse:
    svc = get_patient_stipend_service()
    items = svc.list_stipends(
        patient_id=patient_id,
        trial_id=trial_id,
        site_id=site_id,
        status=status,
        stipend_type=stipend_type,
    )
    return PatientStipendListResponse(items=items, total=len(items))


@router.get(
    "/stipends/{stipend_id}",
    response_model=PatientStipend,
    summary="Get a patient stipend",
)
async def get_stipend(stipend_id: str) -> PatientStipend:
    svc = get_patient_stipend_service()
    stipend = svc.get_stipend(stipend_id)
    if stipend is None:
        raise HTTPException(status_code=404, detail=f"Stipend '{stipend_id}' not found")
    return stipend


@router.post(
    "/stipends",
    response_model=PatientStipend,
    status_code=201,
    summary="Create a patient stipend",
)
async def create_stipend(payload: PatientStipendCreate) -> PatientStipend:
    svc = get_patient_stipend_service()
    return svc.create_stipend(payload)


@router.put(
    "/stipends/{stipend_id}",
    response_model=PatientStipend,
    summary="Update a patient stipend",
)
async def update_stipend(stipend_id: str, payload: PatientStipendUpdate) -> PatientStipend:
    svc = get_patient_stipend_service()
    updated = svc.update_stipend(stipend_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Stipend '{stipend_id}' not found")
    return updated


@router.delete(
    "/stipends/{stipend_id}",
    status_code=204,
    summary="Delete a patient stipend",
)
async def delete_stipend(stipend_id: str) -> None:
    svc = get_patient_stipend_service()
    deleted = svc.delete_stipend(stipend_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Stipend '{stipend_id}' not found")


# ---------------------------------------------------------------------------
# Payment Processing
# ---------------------------------------------------------------------------


@router.post(
    "/stipends/{stipend_id}/process-payment",
    response_model=PatientStipend,
    summary="Process a stipend payment",
    description="Process a payment for a scheduled or approved stipend. Transitions the stipend to paid status.",
)
async def process_payment(stipend_id: str, payload: ProcessPaymentRequest) -> PatientStipend:
    svc = get_patient_stipend_service()
    try:
        return svc.process_payment(stipend_id, payload)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail:
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)


# ---------------------------------------------------------------------------
# Receipt Management
# ---------------------------------------------------------------------------


@router.post(
    "/stipends/{stipend_id}/submit-receipt",
    response_model=PatientStipend,
    summary="Submit a receipt for a stipend",
    description="Submit a receipt document for a stipend that requires receipt verification.",
)
async def submit_receipt(stipend_id: str, payload: ReceiptSubmission) -> PatientStipend:
    svc = get_patient_stipend_service()
    try:
        return svc.submit_receipt(stipend_id, payload.receipt_path, payload.notes)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail:
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)


@router.post(
    "/stipends/{stipend_id}/verify-receipt",
    response_model=PatientStipend,
    summary="Verify a submitted receipt",
    description="Mark a submitted receipt as verified or rejected.",
)
async def verify_receipt(
    stipend_id: str,
    verified: bool = Query(True, description="Whether to mark the receipt as verified or rejected"),
) -> PatientStipend:
    svc = get_patient_stipend_service()
    try:
        return svc.verify_receipt(stipend_id, verified=verified)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail:
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)


# ---------------------------------------------------------------------------
# Travel Reimbursement Management
# ---------------------------------------------------------------------------


@router.get(
    "/travel",
    response_model=TravelReimbursementListResponse,
    summary="List travel reimbursements",
    description="Retrieve travel reimbursement claims with optional filtering by patient, trial, and status.",
)
async def list_travel_reimbursements(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[StipendStatus] = Query(None, description="Filter by status"),
) -> TravelReimbursementListResponse:
    svc = get_patient_stipend_service()
    items = svc.list_travel_reimbursements(
        patient_id=patient_id, trial_id=trial_id, status=status
    )
    return TravelReimbursementListResponse(items=items, total=len(items))


@router.get(
    "/travel/{reimbursement_id}",
    response_model=TravelReimbursement,
    summary="Get a travel reimbursement",
)
async def get_travel_reimbursement(reimbursement_id: str) -> TravelReimbursement:
    svc = get_patient_stipend_service()
    reimb = svc.get_travel_reimbursement(reimbursement_id)
    if reimb is None:
        raise HTTPException(status_code=404, detail=f"Travel reimbursement '{reimbursement_id}' not found")
    return reimb


@router.post(
    "/travel",
    response_model=TravelReimbursement,
    status_code=201,
    summary="Create a travel reimbursement",
    description="Create a new travel reimbursement claim. Total is auto-calculated from components.",
)
async def create_travel_reimbursement(payload: TravelReimbursementCreate) -> TravelReimbursement:
    svc = get_patient_stipend_service()
    return svc.create_travel_reimbursement(payload)


@router.put(
    "/travel/{reimbursement_id}",
    response_model=TravelReimbursement,
    summary="Update a travel reimbursement",
    description="Update a travel reimbursement claim. Total is recalculated automatically.",
)
async def update_travel_reimbursement(
    reimbursement_id: str, payload: TravelReimbursementUpdate
) -> TravelReimbursement:
    svc = get_patient_stipend_service()
    updated = svc.update_travel_reimbursement(reimbursement_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Travel reimbursement '{reimbursement_id}' not found")
    return updated


@router.delete(
    "/travel/{reimbursement_id}",
    status_code=204,
    summary="Delete a travel reimbursement",
)
async def delete_travel_reimbursement(reimbursement_id: str) -> None:
    svc = get_patient_stipend_service()
    deleted = svc.delete_travel_reimbursement(reimbursement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Travel reimbursement '{reimbursement_id}' not found")


# ---------------------------------------------------------------------------
# Tax Record Management
# ---------------------------------------------------------------------------


@router.get(
    "/tax-records",
    response_model=TaxRecordListResponse,
    summary="List tax records",
    description="Retrieve tax records with optional filtering by patient, trial, and tax year.",
)
async def list_tax_records(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    tax_year: Optional[int] = Query(None, description="Filter by tax year"),
) -> TaxRecordListResponse:
    svc = get_patient_stipend_service()
    items = svc.list_tax_records(
        patient_id=patient_id, trial_id=trial_id, tax_year=tax_year
    )
    return TaxRecordListResponse(items=items, total=len(items))


@router.get(
    "/tax-records/check-threshold",
    response_model=TaxRecord,
    summary="Check tax reporting threshold",
    description="Check if a patient has exceeded the IRS reporting threshold for a trial in the current year.",
)
async def check_tax_threshold(
    patient_id: str = Query(..., description="Patient ID"),
    trial_id: str = Query(..., description="Trial ID"),
) -> TaxRecord:
    svc = get_patient_stipend_service()
    record = svc.check_tax_threshold(patient_id, trial_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No tax record found for patient '{patient_id}' in trial '{trial_id}'"
        )
    return record


@router.get(
    "/tax-records/{tax_record_id}",
    response_model=TaxRecord,
    summary="Get a tax record",
)
async def get_tax_record(tax_record_id: str) -> TaxRecord:
    svc = get_patient_stipend_service()
    record = svc.get_tax_record(tax_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Tax record '{tax_record_id}' not found")
    return record


# ---------------------------------------------------------------------------
# Patient Summary
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/summary",
    response_model=PatientPaymentSummary,
    summary="Get patient payment summary",
    description="Generate a comprehensive payment summary for a patient in a specific trial.",
)
async def get_patient_summary(
    patient_id: str,
    trial_id: str = Query(..., description="Trial ID"),
) -> PatientPaymentSummary:
    svc = get_patient_stipend_service()
    summary = svc.get_patient_summary(patient_id, trial_id)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail=f"No stipend records found for patient '{patient_id}' in trial '{trial_id}'"
        )
    return summary


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=StipendMetrics,
    summary="Get stipend management metrics",
    description="Aggregated patient stipend management metrics across all trials.",
)
async def get_metrics() -> StipendMetrics:
    svc = get_patient_stipend_service()
    return svc.get_metrics()
