"""Product Complaint Management API endpoints (PROD-COMPL).

Provides comprehensive product complaint operations: complaint intake,
investigation tracking, root cause analysis, CAPA linkage, and regulatory
reporting with complaint metrics.

Endpoints:
    GET    /product-complaint/complaint-intakes                          - List complaint intakes
    GET    /product-complaint/complaint-intakes/{intake_id}              - Get single intake
    POST   /product-complaint/complaint-intakes                          - Create intake
    PUT    /product-complaint/complaint-intakes/{intake_id}              - Update intake
    DELETE /product-complaint/complaint-intakes/{intake_id}              - Delete intake
    GET    /product-complaint/investigation-records                      - List investigations
    GET    /product-complaint/investigation-records/{record_id}          - Get single investigation
    POST   /product-complaint/investigation-records                      - Create investigation
    PUT    /product-complaint/investigation-records/{record_id}          - Update investigation
    DELETE /product-complaint/investigation-records/{record_id}          - Delete investigation
    GET    /product-complaint/root-cause-analyses                        - List root cause analyses
    GET    /product-complaint/root-cause-analyses/{analysis_id}          - Get single RCA
    POST   /product-complaint/root-cause-analyses                        - Create RCA
    PUT    /product-complaint/root-cause-analyses/{analysis_id}          - Update RCA
    DELETE /product-complaint/root-cause-analyses/{analysis_id}          - Delete RCA
    GET    /product-complaint/capa-linkages                              - List CAPA linkages
    GET    /product-complaint/capa-linkages/{linkage_id}                 - Get single CAPA
    POST   /product-complaint/capa-linkages                              - Create CAPA
    PUT    /product-complaint/capa-linkages/{linkage_id}                 - Update CAPA
    DELETE /product-complaint/capa-linkages/{linkage_id}                 - Delete CAPA
    GET    /product-complaint/regulatory-reports                         - List regulatory reports
    GET    /product-complaint/regulatory-reports/{report_id}             - Get single report
    POST   /product-complaint/regulatory-reports                         - Create report
    PUT    /product-complaint/regulatory-reports/{report_id}             - Update report
    DELETE /product-complaint/regulatory-reports/{report_id}             - Delete report
    GET    /product-complaint/metrics                                    - Product complaint metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.product_complaint import (
    CAPALinkage,
    CAPALinkageCreate,
    CAPALinkageListResponse,
    CAPALinkageUpdate,
    ComplaintCategory,
    ComplaintIntake,
    ComplaintIntakeCreate,
    ComplaintIntakeListResponse,
    ComplaintIntakeUpdate,
    ComplaintSeverity,
    ComplaintStatus,
    InvestigationOutcome,
    InvestigationRecord,
    InvestigationRecordCreate,
    InvestigationRecordListResponse,
    InvestigationRecordUpdate,
    ProductComplaintMetrics,
    RegulatoryReport,
    RegulatoryReportCreate,
    RegulatoryReportListResponse,
    RegulatoryReportUpdate,
    RootCauseAnalysis,
    RootCauseAnalysisCreate,
    RootCauseAnalysisListResponse,
    RootCauseAnalysisUpdate,
    RootCauseCategory,
)
from app.services.product_complaint_service import get_product_complaint_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/product-complaint",
    tags=["Product Complaint"],
)


# ---------------------------------------------------------------------------
# Complaint Intakes
# ---------------------------------------------------------------------------


@router.get(
    "/complaint-intakes",
    response_model=ComplaintIntakeListResponse,
    summary="List complaint intakes",
    description="Retrieve complaint intakes with optional filtering by trial, category, severity, and status.",
)
async def list_complaint_intakes(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    category: Optional[ComplaintCategory] = Query(None, description="Filter by complaint category"),
    severity: Optional[ComplaintSeverity] = Query(None, description="Filter by severity"),
    status: Optional[ComplaintStatus] = Query(None, description="Filter by status"),
) -> ComplaintIntakeListResponse:
    svc = get_product_complaint_service()
    items = svc.list_complaint_intakes(
        trial_id=trial_id, category=category, severity=severity, status=status
    )
    return ComplaintIntakeListResponse(items=items, total=len(items))


@router.get(
    "/complaint-intakes/{intake_id}",
    response_model=ComplaintIntake,
    summary="Get a complaint intake",
)
async def get_complaint_intake(intake_id: str) -> ComplaintIntake:
    svc = get_product_complaint_service()
    intake = svc.get_complaint_intake(intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail=f"Complaint intake '{intake_id}' not found")
    return intake


@router.post(
    "/complaint-intakes",
    response_model=ComplaintIntake,
    status_code=201,
    summary="Create a complaint intake",
)
async def create_complaint_intake(payload: ComplaintIntakeCreate) -> ComplaintIntake:
    svc = get_product_complaint_service()
    return svc.create_complaint_intake(payload)


@router.put(
    "/complaint-intakes/{intake_id}",
    response_model=ComplaintIntake,
    summary="Update a complaint intake",
)
async def update_complaint_intake(
    intake_id: str, payload: ComplaintIntakeUpdate
) -> ComplaintIntake:
    svc = get_product_complaint_service()
    updated = svc.update_complaint_intake(intake_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Complaint intake '{intake_id}' not found")
    return updated


@router.delete(
    "/complaint-intakes/{intake_id}",
    status_code=204,
    summary="Delete a complaint intake",
)
async def delete_complaint_intake(intake_id: str) -> None:
    svc = get_product_complaint_service()
    deleted = svc.delete_complaint_intake(intake_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Complaint intake '{intake_id}' not found")


# ---------------------------------------------------------------------------
# Investigation Records
# ---------------------------------------------------------------------------


@router.get(
    "/investigation-records",
    response_model=InvestigationRecordListResponse,
    summary="List investigation records",
    description="Retrieve investigation records with optional filtering by trial, complaint, and outcome.",
)
async def list_investigation_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    complaint_id: Optional[str] = Query(None, description="Filter by complaint ID"),
    outcome: Optional[InvestigationOutcome] = Query(None, description="Filter by outcome"),
) -> InvestigationRecordListResponse:
    svc = get_product_complaint_service()
    items = svc.list_investigation_records(
        trial_id=trial_id, complaint_id=complaint_id, outcome=outcome
    )
    return InvestigationRecordListResponse(items=items, total=len(items))


@router.get(
    "/investigation-records/{record_id}",
    response_model=InvestigationRecord,
    summary="Get an investigation record",
)
async def get_investigation_record(record_id: str) -> InvestigationRecord:
    svc = get_product_complaint_service()
    record = svc.get_investigation_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Investigation record '{record_id}' not found"
        )
    return record


@router.post(
    "/investigation-records",
    response_model=InvestigationRecord,
    status_code=201,
    summary="Create an investigation record",
)
async def create_investigation_record(payload: InvestigationRecordCreate) -> InvestigationRecord:
    svc = get_product_complaint_service()
    return svc.create_investigation_record(payload)


@router.put(
    "/investigation-records/{record_id}",
    response_model=InvestigationRecord,
    summary="Update an investigation record",
)
async def update_investigation_record(
    record_id: str, payload: InvestigationRecordUpdate
) -> InvestigationRecord:
    svc = get_product_complaint_service()
    updated = svc.update_investigation_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Investigation record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/investigation-records/{record_id}",
    status_code=204,
    summary="Delete an investigation record",
)
async def delete_investigation_record(record_id: str) -> None:
    svc = get_product_complaint_service()
    deleted = svc.delete_investigation_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Investigation record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Root Cause Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/root-cause-analyses",
    response_model=RootCauseAnalysisListResponse,
    summary="List root cause analyses",
    description="Retrieve root cause analyses with optional filtering by trial, complaint, and category.",
)
async def list_root_cause_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    complaint_id: Optional[str] = Query(None, description="Filter by complaint ID"),
    root_cause_category: Optional[RootCauseCategory] = Query(None, description="Filter by root cause category"),
) -> RootCauseAnalysisListResponse:
    svc = get_product_complaint_service()
    items = svc.list_root_cause_analyses(
        trial_id=trial_id, complaint_id=complaint_id, root_cause_category=root_cause_category
    )
    return RootCauseAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/root-cause-analyses/{analysis_id}",
    response_model=RootCauseAnalysis,
    summary="Get a root cause analysis",
)
async def get_root_cause_analysis(analysis_id: str) -> RootCauseAnalysis:
    svc = get_product_complaint_service()
    rca = svc.get_root_cause_analysis(analysis_id)
    if rca is None:
        raise HTTPException(
            status_code=404, detail=f"Root cause analysis '{analysis_id}' not found"
        )
    return rca


@router.post(
    "/root-cause-analyses",
    response_model=RootCauseAnalysis,
    status_code=201,
    summary="Create a root cause analysis",
)
async def create_root_cause_analysis(payload: RootCauseAnalysisCreate) -> RootCauseAnalysis:
    svc = get_product_complaint_service()
    return svc.create_root_cause_analysis(payload)


@router.put(
    "/root-cause-analyses/{analysis_id}",
    response_model=RootCauseAnalysis,
    summary="Update a root cause analysis",
)
async def update_root_cause_analysis(
    analysis_id: str, payload: RootCauseAnalysisUpdate
) -> RootCauseAnalysis:
    svc = get_product_complaint_service()
    updated = svc.update_root_cause_analysis(analysis_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Root cause analysis '{analysis_id}' not found"
        )
    return updated


@router.delete(
    "/root-cause-analyses/{analysis_id}",
    status_code=204,
    summary="Delete a root cause analysis",
)
async def delete_root_cause_analysis(analysis_id: str) -> None:
    svc = get_product_complaint_service()
    deleted = svc.delete_root_cause_analysis(analysis_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Root cause analysis '{analysis_id}' not found"
        )


# ---------------------------------------------------------------------------
# CAPA Linkages
# ---------------------------------------------------------------------------


@router.get(
    "/capa-linkages",
    response_model=CAPALinkageListResponse,
    summary="List CAPA linkages",
    description="Retrieve CAPA linkages with optional filtering by trial, complaint, and status.",
)
async def list_capa_linkages(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    complaint_id: Optional[str] = Query(None, description="Filter by complaint ID"),
    status: Optional[str] = Query(None, description="Filter by CAPA status"),
) -> CAPALinkageListResponse:
    svc = get_product_complaint_service()
    items = svc.list_capa_linkages(
        trial_id=trial_id, complaint_id=complaint_id, status=status
    )
    return CAPALinkageListResponse(items=items, total=len(items))


@router.get(
    "/capa-linkages/{linkage_id}",
    response_model=CAPALinkage,
    summary="Get a CAPA linkage",
)
async def get_capa_linkage(linkage_id: str) -> CAPALinkage:
    svc = get_product_complaint_service()
    linkage = svc.get_capa_linkage(linkage_id)
    if linkage is None:
        raise HTTPException(
            status_code=404, detail=f"CAPA linkage '{linkage_id}' not found"
        )
    return linkage


@router.post(
    "/capa-linkages",
    response_model=CAPALinkage,
    status_code=201,
    summary="Create a CAPA linkage",
)
async def create_capa_linkage(payload: CAPALinkageCreate) -> CAPALinkage:
    svc = get_product_complaint_service()
    return svc.create_capa_linkage(payload)


@router.put(
    "/capa-linkages/{linkage_id}",
    response_model=CAPALinkage,
    summary="Update a CAPA linkage",
)
async def update_capa_linkage(
    linkage_id: str, payload: CAPALinkageUpdate
) -> CAPALinkage:
    svc = get_product_complaint_service()
    updated = svc.update_capa_linkage(linkage_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"CAPA linkage '{linkage_id}' not found"
        )
    return updated


@router.delete(
    "/capa-linkages/{linkage_id}",
    status_code=204,
    summary="Delete a CAPA linkage",
)
async def delete_capa_linkage(linkage_id: str) -> None:
    svc = get_product_complaint_service()
    deleted = svc.delete_capa_linkage(linkage_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"CAPA linkage '{linkage_id}' not found"
        )


# ---------------------------------------------------------------------------
# Regulatory Reports
# ---------------------------------------------------------------------------


@router.get(
    "/regulatory-reports",
    response_model=RegulatoryReportListResponse,
    summary="List regulatory reports",
    description="Retrieve regulatory reports with optional filtering by trial, complaint, type, and authority.",
)
async def list_regulatory_reports(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    complaint_id: Optional[str] = Query(None, description="Filter by complaint ID"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    regulatory_authority: Optional[str] = Query(None, description="Filter by regulatory authority"),
) -> RegulatoryReportListResponse:
    svc = get_product_complaint_service()
    items = svc.list_regulatory_reports(
        trial_id=trial_id,
        complaint_id=complaint_id,
        report_type=report_type,
        regulatory_authority=regulatory_authority,
    )
    return RegulatoryReportListResponse(items=items, total=len(items))


@router.get(
    "/regulatory-reports/{report_id}",
    response_model=RegulatoryReport,
    summary="Get a regulatory report",
)
async def get_regulatory_report(report_id: str) -> RegulatoryReport:
    svc = get_product_complaint_service()
    report = svc.get_regulatory_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=404, detail=f"Regulatory report '{report_id}' not found"
        )
    return report


@router.post(
    "/regulatory-reports",
    response_model=RegulatoryReport,
    status_code=201,
    summary="Create a regulatory report",
)
async def create_regulatory_report(payload: RegulatoryReportCreate) -> RegulatoryReport:
    svc = get_product_complaint_service()
    return svc.create_regulatory_report(payload)


@router.put(
    "/regulatory-reports/{report_id}",
    response_model=RegulatoryReport,
    summary="Update a regulatory report",
)
async def update_regulatory_report(
    report_id: str, payload: RegulatoryReportUpdate
) -> RegulatoryReport:
    svc = get_product_complaint_service()
    updated = svc.update_regulatory_report(report_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Regulatory report '{report_id}' not found"
        )
    return updated


@router.delete(
    "/regulatory-reports/{report_id}",
    status_code=204,
    summary="Delete a regulatory report",
)
async def delete_regulatory_report(report_id: str) -> None:
    svc = get_product_complaint_service()
    deleted = svc.delete_regulatory_report(report_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Regulatory report '{report_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ProductComplaintMetrics,
    summary="Get product complaint metrics",
    description="Aggregated metrics across all product complaint operations.",
)
async def get_metrics() -> ProductComplaintMetrics:
    svc = get_product_complaint_service()
    return svc.get_metrics()
