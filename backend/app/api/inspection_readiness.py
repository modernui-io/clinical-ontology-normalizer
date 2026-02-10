"""Inspection Readiness API endpoints.

Provides comprehensive inspection readiness operations: inspection event
scheduling and tracking, readiness assessments with scoring, checklist
management, inspection finding recording, CAPA lifecycle management,
overdue tracking, and inspection readiness metrics.

Endpoints:
    GET    /inspection-readiness/inspections                              - List inspections
    GET    /inspection-readiness/inspections/{inspection_id}              - Get single inspection
    POST   /inspection-readiness/inspections                              - Schedule inspection
    PUT    /inspection-readiness/inspections/{inspection_id}              - Update inspection
    DELETE /inspection-readiness/inspections/{inspection_id}              - Delete inspection
    GET    /inspection-readiness/assessments                              - List assessments
    GET    /inspection-readiness/assessments/{assessment_id}              - Get single assessment
    POST   /inspection-readiness/assessments                              - Conduct assessment
    PUT    /inspection-readiness/assessments/{assessment_id}              - Update assessment
    DELETE /inspection-readiness/assessments/{assessment_id}              - Delete assessment
    POST   /inspection-readiness/assessments/{assessment_id}/score        - Score readiness
    GET    /inspection-readiness/checklists                               - List checklists
    GET    /inspection-readiness/checklists/{checklist_id}                - Get single checklist
    POST   /inspection-readiness/checklists                               - Create checklist item
    PUT    /inspection-readiness/checklists/{checklist_id}                - Update checklist item
    DELETE /inspection-readiness/checklists/{checklist_id}                - Delete checklist item
    GET    /inspection-readiness/findings                                 - List findings
    GET    /inspection-readiness/findings/{finding_id}                    - Get single finding
    POST   /inspection-readiness/findings                                 - Record finding
    PUT    /inspection-readiness/findings/{finding_id}                    - Update finding
    DELETE /inspection-readiness/findings/{finding_id}                    - Delete finding
    GET    /inspection-readiness/capas                                    - List CAPAs
    GET    /inspection-readiness/capas/overdue                            - Get overdue CAPAs
    GET    /inspection-readiness/capas/{capa_id}                          - Get single CAPA
    POST   /inspection-readiness/capas                                    - Create CAPA
    PUT    /inspection-readiness/capas/{capa_id}                          - Update CAPA
    DELETE /inspection-readiness/capas/{capa_id}                          - Delete CAPA
    GET    /inspection-readiness/metrics                                  - Inspection readiness metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.inspection_readiness import (
    CAPA,
    CAPACreate,
    CAPAListResponse,
    CAPAStatus,
    CAPAUpdate,
    ChecklistCategory,
    ChecklistItemStatus,
    FindingSeverity,
    InspectionEvent,
    InspectionEventCreate,
    InspectionEventListResponse,
    InspectionEventStatus,
    InspectionEventUpdate,
    InspectionFinding,
    InspectionFindingCreate,
    InspectionFindingListResponse,
    InspectionFindingUpdate,
    InspectionMetrics,
    InspectionType,
    ReadinessAssessment,
    ReadinessAssessmentCreate,
    ReadinessAssessmentListResponse,
    ReadinessAssessmentUpdate,
    ReadinessChecklist,
    ReadinessChecklistCreate,
    ReadinessChecklistListResponse,
    ReadinessChecklistUpdate,
    ReadinessStatus,
)
from app.services.inspection_readiness_service import get_inspection_readiness_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inspection-readiness",
    tags=["Inspection Readiness"],
)


# ---------------------------------------------------------------------------
# Inspection Events
# ---------------------------------------------------------------------------


@router.get(
    "/inspections",
    response_model=InspectionEventListResponse,
    summary="List inspection events",
    description="Retrieve inspection events with optional filtering by trial, site, type, and status.",
)
async def list_inspections(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    inspection_type: Optional[InspectionType] = Query(None, description="Filter by inspection type"),
    status: Optional[InspectionEventStatus] = Query(None, description="Filter by status"),
) -> InspectionEventListResponse:
    svc = get_inspection_readiness_service()
    items = svc.list_inspections(
        trial_id=trial_id, site_id=site_id, inspection_type=inspection_type, status=status,
    )
    return InspectionEventListResponse(items=items, total=len(items))


@router.get(
    "/inspections/{inspection_id}",
    response_model=InspectionEvent,
    summary="Get an inspection event",
)
async def get_inspection(inspection_id: str) -> InspectionEvent:
    svc = get_inspection_readiness_service()
    event = svc.get_inspection(inspection_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found")
    return event


@router.post(
    "/inspections",
    response_model=InspectionEvent,
    status_code=201,
    summary="Schedule a new inspection",
    description="Schedule a new inspection event for a trial site.",
)
async def schedule_inspection(payload: InspectionEventCreate) -> InspectionEvent:
    svc = get_inspection_readiness_service()
    return svc.schedule_inspection(payload)


@router.put(
    "/inspections/{inspection_id}",
    response_model=InspectionEvent,
    summary="Update an inspection event",
)
async def update_inspection(inspection_id: str, payload: InspectionEventUpdate) -> InspectionEvent:
    svc = get_inspection_readiness_service()
    updated = svc.update_inspection(inspection_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found")
    return updated


@router.delete(
    "/inspections/{inspection_id}",
    status_code=204,
    summary="Delete an inspection event",
)
async def delete_inspection(inspection_id: str) -> None:
    svc = get_inspection_readiness_service()
    deleted = svc.delete_inspection(inspection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found")


# ---------------------------------------------------------------------------
# Readiness Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=ReadinessAssessmentListResponse,
    summary="List readiness assessments",
    description="Retrieve readiness assessments with optional filtering by trial, site, and status.",
)
async def list_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[ReadinessStatus] = Query(None, description="Filter by readiness status"),
) -> ReadinessAssessmentListResponse:
    svc = get_inspection_readiness_service()
    items = svc.list_assessments(trial_id=trial_id, site_id=site_id, status=status)
    return ReadinessAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=ReadinessAssessment,
    summary="Get a readiness assessment",
)
async def get_assessment(assessment_id: str) -> ReadinessAssessment:
    svc = get_inspection_readiness_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=ReadinessAssessment,
    status_code=201,
    summary="Conduct a readiness assessment",
    description="Create a new readiness assessment for a trial site.",
)
async def conduct_assessment(payload: ReadinessAssessmentCreate) -> ReadinessAssessment:
    svc = get_inspection_readiness_service()
    return svc.conduct_assessment(payload)


@router.put(
    "/assessments/{assessment_id}",
    response_model=ReadinessAssessment,
    summary="Update a readiness assessment",
)
async def update_assessment(assessment_id: str, payload: ReadinessAssessmentUpdate) -> ReadinessAssessment:
    svc = get_inspection_readiness_service()
    updated = svc.update_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a readiness assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_inspection_readiness_service()
    deleted = svc.delete_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")


@router.post(
    "/assessments/{assessment_id}/score",
    response_model=ReadinessAssessment,
    summary="Score readiness for an assessment",
    description="Calculate readiness score based on checklist completion. "
                "Computes per-category scores and overall weighted score.",
)
async def score_readiness(assessment_id: str) -> ReadinessAssessment:
    svc = get_inspection_readiness_service()
    result = svc.score_readiness(assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------


@router.get(
    "/checklists",
    response_model=ReadinessChecklistListResponse,
    summary="List checklist items",
    description="Retrieve checklist items with optional filtering by assessment, category, and status.",
)
async def list_checklists(
    assessment_id: Optional[str] = Query(None, description="Filter by assessment ID"),
    category: Optional[ChecklistCategory] = Query(None, description="Filter by category"),
    status: Optional[ChecklistItemStatus] = Query(None, description="Filter by status"),
) -> ReadinessChecklistListResponse:
    svc = get_inspection_readiness_service()
    items = svc.list_checklists(assessment_id=assessment_id, category=category, status=status)
    return ReadinessChecklistListResponse(items=items, total=len(items))


@router.get(
    "/checklists/{checklist_id}",
    response_model=ReadinessChecklist,
    summary="Get a checklist item",
)
async def get_checklist(checklist_id: str) -> ReadinessChecklist:
    svc = get_inspection_readiness_service()
    checklist = svc.get_checklist(checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail=f"Checklist item '{checklist_id}' not found")
    return checklist


@router.post(
    "/checklists",
    response_model=ReadinessChecklist,
    status_code=201,
    summary="Create a checklist item",
    description="Create a new checklist item for a readiness assessment.",
)
async def create_checklist(payload: ReadinessChecklistCreate) -> ReadinessChecklist:
    svc = get_inspection_readiness_service()
    try:
        return svc.create_checklist(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/checklists/{checklist_id}",
    response_model=ReadinessChecklist,
    summary="Update a checklist item",
)
async def update_checklist(checklist_id: str, payload: ReadinessChecklistUpdate) -> ReadinessChecklist:
    svc = get_inspection_readiness_service()
    updated = svc.update_checklist(checklist_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Checklist item '{checklist_id}' not found")
    return updated


@router.delete(
    "/checklists/{checklist_id}",
    status_code=204,
    summary="Delete a checklist item",
)
async def delete_checklist(checklist_id: str) -> None:
    svc = get_inspection_readiness_service()
    deleted = svc.delete_checklist(checklist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Checklist item '{checklist_id}' not found")


# ---------------------------------------------------------------------------
# Inspection Findings
# ---------------------------------------------------------------------------


@router.get(
    "/findings",
    response_model=InspectionFindingListResponse,
    summary="List inspection findings",
    description="Retrieve inspection findings with optional filtering by inspection, severity, and category.",
)
async def list_findings(
    inspection_id: Optional[str] = Query(None, description="Filter by inspection ID"),
    severity: Optional[FindingSeverity] = Query(None, description="Filter by severity"),
    category: Optional[ChecklistCategory] = Query(None, description="Filter by category"),
) -> InspectionFindingListResponse:
    svc = get_inspection_readiness_service()
    items = svc.list_findings(
        inspection_id=inspection_id, severity=severity, category=category,
    )
    return InspectionFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/{finding_id}",
    response_model=InspectionFinding,
    summary="Get an inspection finding",
)
async def get_finding(finding_id: str) -> InspectionFinding:
    svc = get_inspection_readiness_service()
    finding = svc.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return finding


@router.post(
    "/findings",
    response_model=InspectionFinding,
    status_code=201,
    summary="Record an inspection finding",
    description="Record a new finding from an inspection. Auto-generates finding number.",
)
async def record_finding(payload: InspectionFindingCreate) -> InspectionFinding:
    svc = get_inspection_readiness_service()
    try:
        return svc.record_finding(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/findings/{finding_id}",
    response_model=InspectionFinding,
    summary="Update an inspection finding",
)
async def update_finding(finding_id: str, payload: InspectionFindingUpdate) -> InspectionFinding:
    svc = get_inspection_readiness_service()
    updated = svc.update_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return updated


@router.delete(
    "/findings/{finding_id}",
    status_code=204,
    summary="Delete an inspection finding",
)
async def delete_finding(finding_id: str) -> None:
    svc = get_inspection_readiness_service()
    deleted = svc.delete_finding(finding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")


# ---------------------------------------------------------------------------
# CAPAs
# ---------------------------------------------------------------------------


@router.get(
    "/capas",
    response_model=CAPAListResponse,
    summary="List CAPAs",
    description="Retrieve CAPAs with optional filtering by trial, site, status, and finding.",
)
async def list_capas(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[CAPAStatus] = Query(None, description="Filter by CAPA status"),
    finding_id: Optional[str] = Query(None, description="Filter by finding ID"),
) -> CAPAListResponse:
    svc = get_inspection_readiness_service()
    items = svc.list_capas(
        trial_id=trial_id, site_id=site_id, status=status, finding_id=finding_id,
    )
    return CAPAListResponse(items=items, total=len(items))


@router.get(
    "/capas/overdue",
    response_model=CAPAListResponse,
    summary="Get overdue CAPAs",
    description="Retrieve CAPAs that are past their due date and not closed.",
)
async def get_overdue_capas() -> CAPAListResponse:
    svc = get_inspection_readiness_service()
    items = svc.get_overdue_capas()
    return CAPAListResponse(items=items, total=len(items))


@router.get(
    "/capas/{capa_id}",
    response_model=CAPA,
    summary="Get a CAPA",
)
async def get_capa(capa_id: str) -> CAPA:
    svc = get_inspection_readiness_service()
    capa = svc.get_capa(capa_id)
    if capa is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return capa


@router.post(
    "/capas",
    response_model=CAPA,
    status_code=201,
    summary="Create a CAPA",
    description="Create a new Corrective and Preventive Action linked to a finding.",
)
async def create_capa(payload: CAPACreate) -> CAPA:
    svc = get_inspection_readiness_service()
    try:
        return svc.create_capa(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/capas/{capa_id}",
    response_model=CAPA,
    summary="Update a CAPA",
)
async def update_capa(capa_id: str, payload: CAPAUpdate) -> CAPA:
    svc = get_inspection_readiness_service()
    updated = svc.update_capa(capa_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return updated


@router.delete(
    "/capas/{capa_id}",
    status_code=204,
    summary="Delete a CAPA",
)
async def delete_capa(capa_id: str) -> None:
    svc = get_inspection_readiness_service()
    deleted = svc.delete_capa(capa_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=InspectionMetrics,
    summary="Get inspection readiness metrics",
    description="Aggregated inspection readiness metrics including inspection counts, "
                "readiness scores, checklist completion, finding severity breakdown, "
                "and CAPA status summary.",
)
async def get_metrics() -> InspectionMetrics:
    svc = get_inspection_readiness_service()
    return svc.get_metrics()
