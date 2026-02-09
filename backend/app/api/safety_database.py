"""Safety Database & CIOMS Reporting API endpoints (CLINICAL-23).

Provides comprehensive safety database operations: individual case safety
report (ICSR) management, regulatory submission tracking with expedited
timelines (7-day/15-day), CIOMS I/II and MedWatch form generation,
aggregate safety reports (DSUR, PSUR, PBRER, ASR), SUSAR identification,
MedDRA-coded event classification, and safety database operational metrics.

Endpoints:
    GET    /safety-database/cases                                    - List safety cases
    GET    /safety-database/cases/{case_id}                          - Get single case
    POST   /safety-database/cases                                    - Create safety case
    PUT    /safety-database/cases/{case_id}                          - Update safety case
    DELETE /safety-database/cases/{case_id}                          - Delete safety case
    GET    /safety-database/cases/{case_id}/submissions              - List case submissions
    POST   /safety-database/cases/{case_id}/submissions              - Create submission for case
    GET    /safety-database/cases/{case_id}/cioms-form               - Generate CIOMS form
    GET    /safety-database/cases/{case_id}/reporting-deadline       - Get reporting deadline
    GET    /safety-database/submissions                              - List all submissions
    GET    /safety-database/submissions/{submission_id}              - Get single submission
    PUT    /safety-database/submissions/{submission_id}              - Update submission
    GET    /safety-database/submissions/overdue                      - Overdue submissions
    GET    /safety-database/cioms-forms                              - List CIOMS forms
    GET    /safety-database/susars                                   - List SUSARs
    GET    /safety-database/aggregate-reports                        - List aggregate reports
    GET    /safety-database/aggregate-reports/{report_id}            - Get single aggregate report
    POST   /safety-database/aggregate-reports                        - Create aggregate report
    PUT    /safety-database/aggregate-reports/{report_id}            - Update aggregate report
    DELETE /safety-database/aggregate-reports/{report_id}            - Delete aggregate report
    GET    /safety-database/metrics                                  - Safety database metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.safety_database import (
    AggregateReport,
    AggregateReportCreate,
    AggregateReportListResponse,
    AggregateReportStatus,
    AggregateReportType,
    AggregateReportUpdate,
    CaseType,
    CIOMSForm,
    CIOMSFormListResponse,
    CIOMSFormType,
    EventOutcome,
    Expectedness,
    Relatedness,
    RegulatoryAuthority,
    RegulatorySubmission,
    RegulatorySubmissionCreate,
    RegulatorySubmissionListResponse,
    RegulatorySubmissionUpdate,
    ReportingStatus,
    SafetyCase,
    SafetyCaseCreate,
    SafetyCaseListResponse,
    SafetyCaseUpdate,
    SafetyDatabaseMetrics,
    Seriousness,
    SubmissionStatus,
)
from app.services.safety_database_service import get_safety_db_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/safety-database",
    tags=["Safety Database"],
)


# ---------------------------------------------------------------------------
# Safety Cases
# ---------------------------------------------------------------------------


@router.get(
    "/cases",
    response_model=SafetyCaseListResponse,
    summary="List safety cases",
    description="Retrieve safety cases with optional filtering by trial, site, type, status, seriousness, expectedness, relatedness, and outcome.",
)
async def list_cases(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    case_type: Optional[CaseType] = Query(None, description="Filter by case type"),
    reporting_status: Optional[ReportingStatus] = Query(None, description="Filter by reporting status"),
    seriousness: Optional[Seriousness] = Query(None, description="Filter by seriousness criterion"),
    expectedness: Optional[Expectedness] = Query(None, description="Filter by expectedness"),
    relatedness: Optional[Relatedness] = Query(None, description="Filter by relatedness"),
    outcome: Optional[EventOutcome] = Query(None, description="Filter by outcome"),
) -> SafetyCaseListResponse:
    svc = get_safety_db_service()
    items = svc.list_cases(
        trial_id=trial_id,
        site_id=site_id,
        case_type=case_type,
        reporting_status=reporting_status,
        seriousness=seriousness,
        expectedness=expectedness,
        relatedness=relatedness,
        outcome=outcome,
    )
    return SafetyCaseListResponse(items=items, total=len(items))


@router.get(
    "/cases/{case_id}",
    response_model=SafetyCase,
    summary="Get a safety case",
)
async def get_case(case_id: str) -> SafetyCase:
    svc = get_safety_db_service()
    case = svc.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Safety case '{case_id}' not found")
    return case


@router.post(
    "/cases",
    response_model=SafetyCase,
    status_code=201,
    summary="Create a safety case",
    description="Create a new Individual Case Safety Report (ICSR).",
)
async def create_case(payload: SafetyCaseCreate) -> SafetyCase:
    svc = get_safety_db_service()
    return svc.create_case(payload)


@router.put(
    "/cases/{case_id}",
    response_model=SafetyCase,
    summary="Update a safety case",
)
async def update_case(case_id: str, payload: SafetyCaseUpdate) -> SafetyCase:
    svc = get_safety_db_service()
    updated = svc.update_case(case_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Safety case '{case_id}' not found")
    return updated


@router.delete(
    "/cases/{case_id}",
    status_code=204,
    summary="Delete a safety case",
)
async def delete_case(case_id: str) -> None:
    svc = get_safety_db_service()
    deleted = svc.delete_case(case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Safety case '{case_id}' not found")


# ---------------------------------------------------------------------------
# Case-Level Submissions
# ---------------------------------------------------------------------------


@router.get(
    "/cases/{case_id}/submissions",
    response_model=RegulatorySubmissionListResponse,
    summary="List submissions for a case",
    description="Retrieve all regulatory submissions associated with a specific safety case.",
)
async def list_case_submissions(case_id: str) -> RegulatorySubmissionListResponse:
    svc = get_safety_db_service()
    case = svc.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Safety case '{case_id}' not found")
    items = svc.list_submissions(case_id=case_id)
    return RegulatorySubmissionListResponse(items=items, total=len(items))


@router.post(
    "/cases/{case_id}/submissions",
    response_model=RegulatorySubmission,
    status_code=201,
    summary="Create a regulatory submission for a case",
    description="Create a new regulatory submission targeting a specific authority.",
)
async def create_submission(case_id: str, payload: RegulatorySubmissionCreate) -> RegulatorySubmission:
    svc = get_safety_db_service()
    try:
        return svc.create_submission(case_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/cases/{case_id}/cioms-form",
    response_model=CIOMSForm,
    summary="Generate CIOMS form for a case",
    description="Generate a CIOMS I, CIOMS II, MedWatch 3500A, or E2B R3 form from case data.",
)
async def generate_cioms_form(
    case_id: str,
    form_type: CIOMSFormType = Query(CIOMSFormType.CIOMS_I, description="Form type to generate"),
) -> CIOMSForm:
    svc = get_safety_db_service()
    form = svc.generate_cioms_form(case_id, form_type)
    if form is None:
        raise HTTPException(status_code=404, detail=f"Safety case '{case_id}' not found")
    return form


@router.get(
    "/cases/{case_id}/reporting-deadline",
    summary="Get reporting deadline for a case",
    description="Calculate the expedited reporting deadline based on seriousness, expectedness, and ICH E2A rules.",
)
async def get_reporting_deadline(case_id: str) -> dict:
    svc = get_safety_db_service()
    case = svc.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Safety case '{case_id}' not found")
    days = svc.calculate_reporting_deadline(case)
    deadline = None
    if days > 0:
        from datetime import timedelta
        deadline = (case.initial_receipt_date + timedelta(days=days)).isoformat()
    return {
        "case_id": case_id,
        "case_number": case.case_number,
        "expedited_days": days,
        "deadline": deadline,
        "is_susar": (
            bool(case.seriousness_criteria)
            and case.expectedness == Expectedness.UNEXPECTED
            and case.relatedness in (Relatedness.RELATED, Relatedness.POSSIBLY_RELATED)
        ),
    }


# ---------------------------------------------------------------------------
# Regulatory Submissions (top-level)
# ---------------------------------------------------------------------------


@router.get(
    "/submissions",
    response_model=RegulatorySubmissionListResponse,
    summary="List all regulatory submissions",
    description="Retrieve all regulatory submissions with optional filtering by case, authority, and status.",
)
async def list_submissions(
    case_id: Optional[str] = Query(None, description="Filter by case ID"),
    authority: Optional[RegulatoryAuthority] = Query(None, description="Filter by authority"),
    status: Optional[SubmissionStatus] = Query(None, description="Filter by status"),
) -> RegulatorySubmissionListResponse:
    svc = get_safety_db_service()
    items = svc.list_submissions(case_id=case_id, authority=authority, status=status)
    return RegulatorySubmissionListResponse(items=items, total=len(items))


@router.get(
    "/submissions/overdue",
    response_model=RegulatorySubmissionListResponse,
    summary="Get overdue submissions",
    description="Retrieve submissions that are past their regulatory deadline and not yet submitted.",
)
async def get_overdue_submissions() -> RegulatorySubmissionListResponse:
    svc = get_safety_db_service()
    items = svc.get_overdue_submissions()
    return RegulatorySubmissionListResponse(items=items, total=len(items))


@router.get(
    "/submissions/{submission_id}",
    response_model=RegulatorySubmission,
    summary="Get a regulatory submission",
)
async def get_submission(submission_id: str) -> RegulatorySubmission:
    svc = get_safety_db_service()
    sub = svc.get_submission(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail=f"Submission '{submission_id}' not found")
    return sub


@router.put(
    "/submissions/{submission_id}",
    response_model=RegulatorySubmission,
    summary="Update a regulatory submission",
    description="Update submission status, dates, and acknowledgment information.",
)
async def update_submission(submission_id: str, payload: RegulatorySubmissionUpdate) -> RegulatorySubmission:
    svc = get_safety_db_service()
    updated = svc.update_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Submission '{submission_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# CIOMS Forms
# ---------------------------------------------------------------------------


@router.get(
    "/cioms-forms",
    response_model=CIOMSFormListResponse,
    summary="List CIOMS forms",
    description="List generated CIOMS forms, optionally filtered by case.",
)
async def list_cioms_forms(
    case_id: Optional[str] = Query(None, description="Filter by case ID"),
) -> CIOMSFormListResponse:
    svc = get_safety_db_service()
    items = svc.list_cioms_forms(case_id=case_id)
    return CIOMSFormListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# SUSARs
# ---------------------------------------------------------------------------


@router.get(
    "/susars",
    response_model=SafetyCaseListResponse,
    summary="List SUSARs",
    description="Retrieve all Suspected Unexpected Serious Adverse Reactions (serious + unexpected + at least possibly related).",
)
async def list_susars() -> SafetyCaseListResponse:
    svc = get_safety_db_service()
    items = svc.get_susars()
    return SafetyCaseListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Aggregate Reports
# ---------------------------------------------------------------------------


@router.get(
    "/aggregate-reports",
    response_model=AggregateReportListResponse,
    summary="List aggregate safety reports",
    description="Retrieve aggregate safety reports (DSUR, PSUR, PBRER, ASR) with optional filtering.",
)
async def list_aggregate_reports(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    report_type: Optional[AggregateReportType] = Query(None, description="Filter by report type"),
    status: Optional[AggregateReportStatus] = Query(None, description="Filter by status"),
) -> AggregateReportListResponse:
    svc = get_safety_db_service()
    items = svc.list_aggregate_reports(trial_id=trial_id, report_type=report_type, status=status)
    return AggregateReportListResponse(items=items, total=len(items))


@router.get(
    "/aggregate-reports/{report_id}",
    response_model=AggregateReport,
    summary="Get an aggregate safety report",
)
async def get_aggregate_report(report_id: str) -> AggregateReport:
    svc = get_safety_db_service()
    report = svc.get_aggregate_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Aggregate report '{report_id}' not found")
    return report


@router.post(
    "/aggregate-reports",
    response_model=AggregateReport,
    status_code=201,
    summary="Create an aggregate safety report",
)
async def create_aggregate_report(payload: AggregateReportCreate) -> AggregateReport:
    svc = get_safety_db_service()
    return svc.create_aggregate_report(payload)


@router.put(
    "/aggregate-reports/{report_id}",
    response_model=AggregateReport,
    summary="Update an aggregate safety report",
)
async def update_aggregate_report(report_id: str, payload: AggregateReportUpdate) -> AggregateReport:
    svc = get_safety_db_service()
    updated = svc.update_aggregate_report(report_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Aggregate report '{report_id}' not found")
    return updated


@router.delete(
    "/aggregate-reports/{report_id}",
    status_code=204,
    summary="Delete an aggregate safety report",
)
async def delete_aggregate_report(report_id: str) -> None:
    svc = get_safety_db_service()
    deleted = svc.delete_aggregate_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Aggregate report '{report_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SafetyDatabaseMetrics,
    summary="Get safety database metrics",
    description="Aggregated safety database metrics including case counts, submission timelines, and SUSAR statistics.",
)
async def get_metrics() -> SafetyDatabaseMetrics:
    svc = get_safety_db_service()
    return svc.get_metrics()
