"""SAE Regulatory Reporting API endpoints (CLINICAL-SAE).

Provides comprehensive serious adverse event (SAE) regulatory reporting operations:
SAE report CRUD, lifecycle management (draft -> medical_review -> submitted ->
acknowledged -> closed), causality assessment, regulatory authority submission,
MedWatch/CIOMS form generation, reporting deadline enforcement, narrative
management, and safety metrics.

Endpoints:
    GET    /sae-reporting/                                                 - List SAE reports
    GET    /sae-reporting/metrics                                          - Get SAE metrics
    GET    /sae-reporting/overdue                                          - Get overdue reports
    GET    /sae-reporting/deadlines                                        - Check reporting deadlines
    GET    /sae-reporting/trial/{trial_id}/safety-summary                  - Get trial safety summary
    GET    /sae-reporting/causality-records/{record_id}                    - Get causality record
    GET    /sae-reporting/regulatory-submissions/{submission_id}           - Get regulatory submission
    POST   /sae-reporting/regulatory-submissions/{submission_id}/acknowledge - Record acknowledgment
    GET    /sae-reporting/{report_id}                                      - Get single SAE report
    POST   /sae-reporting/                                                 - Create SAE report
    PUT    /sae-reporting/{report_id}                                      - Update SAE report
    DELETE /sae-reporting/{report_id}                                      - Delete SAE report
    POST   /sae-reporting/{report_id}/submit-for-review                   - Submit for medical review
    POST   /sae-reporting/{report_id}/approve-review                      - Approve medical review
    POST   /sae-reporting/{report_id}/close                               - Close SAE report
    POST   /sae-reporting/{report_id}/follow-up                           - Create follow-up report
    POST   /sae-reporting/{report_id}/final                               - Create final report
    GET    /sae-reporting/{report_id}/causality-records                    - List causality records
    POST   /sae-reporting/{report_id}/causality-records                    - Create causality record
    GET    /sae-reporting/{report_id}/regulatory-submissions               - List regulatory submissions
    POST   /sae-reporting/{report_id}/regulatory-submissions               - Submit to authority
    GET    /sae-reporting/{report_id}/narrative                            - Get SAE narrative
    POST   /sae-reporting/{report_id}/narrative/follow-up                  - Add follow-up narrative
    POST   /sae-reporting/{report_id}/narrative/medical-review             - Add medical review note
    GET    /sae-reporting/{report_id}/medwatch                             - Generate MedWatch form
    GET    /sae-reporting/{report_id}/cioms                                - Generate CIOMS form
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.schemas.sae_reporting import (
    CausalityRecord,
    CausalityRecordCreate,
    CausalityRecordListResponse,
    CIOMSForm,
    MedWatchForm,
    RegulatoryAuthority,
    RegulatorySubmission,
    RegulatorySubmissionCreate,
    RegulatorySubmissionListResponse,
    SAEMetrics,
    SAENarrative,
    SAEOutcome,
    SAEReport,
    SAEReportCreate,
    SAEReportListResponse,
    SAEReportUpdate,
    SAESeriousness,
    SAEStatus,
    TrialSafetySummary,
)
from app.services.sae_reporting_service import get_sae_reporting_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sae-reporting",
    tags=["SAE Regulatory Reporting"],
)


# ---------------------------------------------------------------------------
# Request bodies for simple text payloads
# ---------------------------------------------------------------------------


class NarrativeTextPayload(BaseModel):
    """Request body for adding narrative text."""

    text: str


class AcknowledgmentPayload(BaseModel):
    """Request body for recording an acknowledgment."""

    acknowledgment_number: str
    acknowledgment_date: datetime


# ---------------------------------------------------------------------------
# SAE Report CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=SAEReportListResponse,
    summary="List SAE reports",
    description="Retrieve SAE reports with optional filtering by trial, status, seriousness, and study drug.",
)
async def list_sae_reports(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SAEStatus] = Query(None, description="Filter by status"),
    seriousness: Optional[SAESeriousness] = Query(None, description="Filter by seriousness"),
    study_drug: Optional[str] = Query(None, description="Filter by study drug"),
) -> SAEReportListResponse:
    svc = get_sae_reporting_service()
    items = svc.list_sae_reports(
        trial_id=trial_id, status=status, seriousness=seriousness, study_drug=study_drug
    )
    return SAEReportListResponse(items=items, total=len(items))


@router.get(
    "/metrics",
    response_model=SAEMetrics,
    summary="Get SAE metrics",
    description="Aggregated SAE reporting metrics across all trials.",
)
async def get_sae_metrics() -> SAEMetrics:
    svc = get_sae_reporting_service()
    return svc.get_sae_metrics()


@router.get(
    "/overdue",
    response_model=SAEReportListResponse,
    summary="Get overdue SAE reports",
    description="Returns all SAE reports past their reporting deadline that have not been submitted.",
)
async def get_overdue_reports() -> SAEReportListResponse:
    svc = get_sae_reporting_service()
    items = svc.get_overdue_reports()
    return SAEReportListResponse(items=items, total=len(items))


@router.get(
    "/deadlines",
    response_model=SAEReportListResponse,
    summary="Check reporting deadlines",
    description="Returns SAE reports approaching or past their deadline (within 48 hours) that are not yet submitted.",
)
async def check_reporting_deadlines() -> SAEReportListResponse:
    svc = get_sae_reporting_service()
    items = svc.check_reporting_deadlines()
    return SAEReportListResponse(items=items, total=len(items))


@router.get(
    "/trial/{trial_id}/safety-summary",
    response_model=TrialSafetySummary,
    summary="Get trial safety summary",
    description="Safety summary with SAE breakdown for a specific trial.",
)
async def get_trial_safety_summary(trial_id: str) -> TrialSafetySummary:
    svc = get_sae_reporting_service()
    return svc.get_trial_safety_summary(trial_id)


@router.get(
    "/causality-records/{record_id}",
    response_model=CausalityRecord,
    summary="Get a causality record",
)
async def get_causality_record(record_id: str) -> CausalityRecord:
    svc = get_sae_reporting_service()
    record = svc.get_causality_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Causality record '{record_id}' not found")
    return record


@router.get(
    "/regulatory-submissions/{submission_id}",
    response_model=RegulatorySubmission,
    summary="Get a regulatory submission",
)
async def get_regulatory_submission(submission_id: str) -> RegulatorySubmission:
    svc = get_sae_reporting_service()
    sub = svc.get_regulatory_submission(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail=f"Regulatory submission '{submission_id}' not found")
    return sub


@router.post(
    "/regulatory-submissions/{submission_id}/acknowledge",
    response_model=RegulatorySubmission,
    summary="Record acknowledgment from regulatory authority",
    description="Record the acknowledgment number and date received from a regulatory authority.",
)
async def record_acknowledgment(
    submission_id: str, payload: AcknowledgmentPayload
) -> RegulatorySubmission:
    svc = get_sae_reporting_service()
    result = svc.record_acknowledgment(
        submission_id, payload.acknowledgment_number, payload.acknowledgment_date
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Regulatory submission '{submission_id}' not found")
    return result


@router.get(
    "/{report_id}",
    response_model=SAEReport,
    summary="Get an SAE report",
)
async def get_sae_report(report_id: str) -> SAEReport:
    svc = get_sae_reporting_service()
    report = svc.get_sae_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")
    return report


@router.post(
    "/",
    response_model=SAEReport,
    status_code=201,
    summary="Create an SAE report",
    description="Create a new initial SAE report. Reporting timeline and deadline are auto-calculated from seriousness criteria.",
)
async def create_sae_report(payload: SAEReportCreate) -> SAEReport:
    svc = get_sae_reporting_service()
    return svc.create_sae_report(payload)


@router.put(
    "/{report_id}",
    response_model=SAEReport,
    summary="Update an SAE report",
)
async def update_sae_report(
    report_id: str, payload: SAEReportUpdate
) -> SAEReport:
    svc = get_sae_reporting_service()
    updated = svc.update_sae_report(report_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")
    return updated


@router.delete(
    "/{report_id}",
    status_code=204,
    summary="Delete an SAE report",
)
async def delete_sae_report(report_id: str) -> None:
    svc = get_sae_reporting_service()
    deleted = svc.delete_sae_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")


# ---------------------------------------------------------------------------
# SAE Report Lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/{report_id}/submit-for-review",
    response_model=SAEReport,
    summary="Submit SAE report for medical review",
    description="Transition SAE report from draft to medical_review status.",
)
async def submit_for_medical_review(report_id: str) -> SAEReport:
    svc = get_sae_reporting_service()
    try:
        result = svc.submit_for_medical_review(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")
    return result


@router.post(
    "/{report_id}/approve-review",
    response_model=SAEReport,
    summary="Approve medical review",
    description="Approve medical review, transitioning SAE report to submitted status.",
)
async def approve_medical_review(report_id: str) -> SAEReport:
    svc = get_sae_reporting_service()
    try:
        result = svc.approve_medical_review(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")
    return result


@router.post(
    "/{report_id}/close",
    response_model=SAEReport,
    summary="Close SAE report",
    description="Close an SAE report. Requires submitted or acknowledged status.",
)
async def close_report(report_id: str) -> SAEReport:
    svc = get_sae_reporting_service()
    try:
        result = svc.close_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Follow-up and Final Reports
# ---------------------------------------------------------------------------


@router.post(
    "/{report_id}/follow-up",
    response_model=SAEReport,
    status_code=201,
    summary="Create a follow-up SAE report",
    description="Create a follow-up report linked to a parent SAE report.",
)
async def create_follow_up_report(
    report_id: str, payload: SAEReportCreate
) -> SAEReport:
    svc = get_sae_reporting_service()
    try:
        return svc.create_follow_up_report(report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/{report_id}/final",
    response_model=SAEReport,
    status_code=201,
    summary="Create a final SAE report",
    description="Create a final report linked to a parent SAE report.",
)
async def create_final_report(
    report_id: str, payload: SAEReportCreate
) -> SAEReport:
    svc = get_sae_reporting_service()
    try:
        return svc.create_final_report(report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Causality Records
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}/causality-records",
    response_model=CausalityRecordListResponse,
    summary="List causality records for an SAE report",
)
async def list_causality_records(report_id: str) -> CausalityRecordListResponse:
    svc = get_sae_reporting_service()
    items = svc.list_causality_records(sae_report_id=report_id)
    return CausalityRecordListResponse(items=items, total=len(items))


@router.post(
    "/{report_id}/causality-records",
    response_model=CausalityRecord,
    status_code=201,
    summary="Create a causality assessment",
    description="Add a causality assessment record to an SAE report.",
)
async def create_causality_record(
    report_id: str, payload: CausalityRecordCreate
) -> CausalityRecord:
    svc = get_sae_reporting_service()
    try:
        return svc.create_causality_record(report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Regulatory Submissions
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}/regulatory-submissions",
    response_model=RegulatorySubmissionListResponse,
    summary="List regulatory submissions for an SAE report",
)
async def list_regulatory_submissions(
    report_id: str,
    authority: Optional[RegulatoryAuthority] = Query(None, description="Filter by authority"),
) -> RegulatorySubmissionListResponse:
    svc = get_sae_reporting_service()
    items = svc.list_regulatory_submissions(sae_report_id=report_id, authority=authority)
    return RegulatorySubmissionListResponse(items=items, total=len(items))


@router.post(
    "/{report_id}/regulatory-submissions",
    response_model=RegulatorySubmission,
    status_code=201,
    summary="Submit SAE to regulatory authority",
    description="Create a regulatory submission for an SAE report. Report must be in submitted or acknowledged status.",
)
async def submit_to_authority(
    report_id: str, payload: RegulatorySubmissionCreate
) -> RegulatorySubmission:
    svc = get_sae_reporting_service()
    try:
        return svc.submit_to_authority(report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Narrative Management
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}/narrative",
    response_model=SAENarrative,
    summary="Get SAE narrative",
    description="Retrieve the narrative for an SAE report.",
)
async def get_narrative(report_id: str) -> SAENarrative:
    svc = get_sae_reporting_service()
    narrative = svc.get_narrative(report_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail=f"Narrative for SAE report '{report_id}' not found")
    return narrative


@router.post(
    "/{report_id}/narrative/follow-up",
    response_model=SAENarrative,
    summary="Add follow-up narrative",
    description="Add a follow-up narrative entry to an SAE report.",
)
async def add_follow_up_narrative(
    report_id: str, payload: NarrativeTextPayload
) -> SAENarrative:
    svc = get_sae_reporting_service()
    result = svc.add_follow_up_narrative(report_id, payload.text)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Narrative for SAE report '{report_id}' not found")
    return result


@router.post(
    "/{report_id}/narrative/medical-review",
    response_model=SAENarrative,
    summary="Add medical review note",
    description="Add a medical review note to an SAE narrative.",
)
async def add_medical_review_note(
    report_id: str, payload: NarrativeTextPayload
) -> SAENarrative:
    svc = get_sae_reporting_service()
    result = svc.add_medical_review_note(report_id, payload.text)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Narrative for SAE report '{report_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Form Generation
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}/medwatch",
    response_model=MedWatchForm,
    summary="Generate MedWatch 3500A form",
    description="Auto-generate FDA MedWatch 3500A form data from an SAE report.",
)
async def generate_medwatch_form(report_id: str) -> MedWatchForm:
    svc = get_sae_reporting_service()
    form = svc.generate_medwatch_form(report_id)
    if form is None:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")
    return form


@router.get(
    "/{report_id}/cioms",
    response_model=CIOMSForm,
    summary="Generate CIOMS I form",
    description="Auto-generate CIOMS I form data for international regulatory reporting.",
)
async def generate_cioms_form(report_id: str) -> CIOMSForm:
    svc = get_sae_reporting_service()
    form = svc.generate_cioms_form(report_id)
    if form is None:
        raise HTTPException(status_code=404, detail=f"SAE report '{report_id}' not found")
    return form
