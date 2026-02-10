"""Protocol Feasibility Assessment API endpoints.

Provides comprehensive protocol feasibility operations: feasibility study lifecycle,
site evaluation and scoring, competitive landscape analysis, enrollment projection
modeling, questionnaire management, feasibility summary generation, and operational
metrics.

Endpoints:
    GET    /protocol-feasibility/studies                                    - List studies
    POST   /protocol-feasibility/studies                                    - Create study
    GET    /protocol-feasibility/studies/{id}                               - Get study
    PUT    /protocol-feasibility/studies/{id}                               - Update study
    DELETE /protocol-feasibility/studies/{id}                               - Delete study
    GET    /protocol-feasibility/studies/{id}/site-assessments              - List site assessments
    POST   /protocol-feasibility/studies/{id}/site-assessments              - Create site assessment
    GET    /protocol-feasibility/site-assessments/{id}                      - Get site assessment
    PUT    /protocol-feasibility/site-assessments/{id}                      - Update site assessment
    GET    /protocol-feasibility/studies/{id}/competitive-landscape         - List competitive entries
    POST   /protocol-feasibility/studies/{id}/competitive-landscape         - Create competitive entry
    GET    /protocol-feasibility/competitive-landscape/{id}                 - Get competitive entry
    PUT    /protocol-feasibility/competitive-landscape/{id}                 - Update competitive entry
    GET    /protocol-feasibility/studies/{id}/enrollment-projections        - List projections
    POST   /protocol-feasibility/studies/{id}/enrollment-projections        - Create projection
    GET    /protocol-feasibility/enrollment-projections/{id}                - Get projection
    GET    /protocol-feasibility/studies/{id}/summary                       - Get feasibility summary
    GET    /protocol-feasibility/studies/{id}/questionnaire                 - List questions
    POST   /protocol-feasibility/studies/{id}/questionnaire                 - Create question
    POST   /protocol-feasibility/studies/{id}/questionnaire-responses       - Submit response
    GET    /protocol-feasibility/metrics                                    - Get metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.protocol_feasibility import (
    CompetitiveLandscape,
    CompetitiveLandscapeCreate,
    CompetitiveLandscapeListResponse,
    CompetitiveLandscapeUpdate,
    CompetitiveThreatLevel,
    EnrollmentProjection,
    EnrollmentProjectionCreate,
    EnrollmentProjectionListResponse,
    FeasibilityMetrics,
    FeasibilityQuestion,
    FeasibilityQuestionCreate,
    FeasibilityQuestionListResponse,
    FeasibilityStatus,
    FeasibilityStudy,
    FeasibilityStudyCreate,
    FeasibilityStudyListResponse,
    FeasibilityStudyUpdate,
    FeasibilitySummary,
    QuestionnaireResponseCreate,
    SiteAssessment,
    SiteAssessmentCreate,
    SiteAssessmentListResponse,
    SiteAssessmentUpdate,
    SiteQuestionnaireResponse,
    SiteRating,
)
from app.services.protocol_feasibility_service import get_protocol_feasibility_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/protocol-feasibility",
    tags=["Protocol Feasibility"],
)


# ---------------------------------------------------------------------------
# Feasibility Studies
# ---------------------------------------------------------------------------


@router.get(
    "/studies",
    response_model=FeasibilityStudyListResponse,
    summary="List feasibility studies",
    description="Retrieve feasibility studies with optional filtering by status and therapeutic area.",
)
async def list_studies(
    status: Optional[FeasibilityStatus] = Query(None, description="Filter by study status"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
) -> FeasibilityStudyListResponse:
    svc = get_protocol_feasibility_service()
    items = svc.list_studies(status=status, therapeutic_area=therapeutic_area)
    return FeasibilityStudyListResponse(items=items, total=len(items))


@router.post(
    "/studies",
    response_model=FeasibilityStudy,
    status_code=201,
    summary="Create a feasibility study",
)
async def create_study(payload: FeasibilityStudyCreate) -> FeasibilityStudy:
    svc = get_protocol_feasibility_service()
    return svc.create_study(payload)


@router.get(
    "/studies/{study_id}",
    response_model=FeasibilityStudy,
    summary="Get a feasibility study",
)
async def get_study(study_id: str) -> FeasibilityStudy:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    return study


@router.put(
    "/studies/{study_id}",
    response_model=FeasibilityStudy,
    summary="Update a feasibility study",
)
async def update_study(study_id: str, payload: FeasibilityStudyUpdate) -> FeasibilityStudy:
    svc = get_protocol_feasibility_service()
    updated = svc.update_study(study_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    return updated


@router.delete(
    "/studies/{study_id}",
    status_code=204,
    summary="Delete a feasibility study",
)
async def delete_study(study_id: str) -> None:
    svc = get_protocol_feasibility_service()
    deleted = svc.delete_study(study_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")


# ---------------------------------------------------------------------------
# Site Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/studies/{study_id}/site-assessments",
    response_model=SiteAssessmentListResponse,
    summary="List site assessments for a study",
    description="Retrieve site assessments with optional filtering by country and rating.",
)
async def list_site_assessments(
    study_id: str,
    country: Optional[str] = Query(None, description="Filter by country"),
    site_rating: Optional[SiteRating] = Query(None, description="Filter by site rating"),
) -> SiteAssessmentListResponse:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    items = svc.list_site_assessments(study_id, country=country, site_rating=site_rating)
    return SiteAssessmentListResponse(items=items, total=len(items))


@router.post(
    "/studies/{study_id}/site-assessments",
    response_model=SiteAssessment,
    status_code=201,
    summary="Create a site assessment",
    description="Assess a potential investigator site. Site rating is auto-computed from sub-scores.",
)
async def create_site_assessment(
    study_id: str, payload: SiteAssessmentCreate
) -> SiteAssessment:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    return svc.create_site_assessment(study_id, payload)


@router.get(
    "/site-assessments/{assessment_id}",
    response_model=SiteAssessment,
    summary="Get a site assessment",
)
async def get_site_assessment(assessment_id: str) -> SiteAssessment:
    svc = get_protocol_feasibility_service()
    assessment = svc.get_site_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=404, detail=f"Site assessment '{assessment_id}' not found"
        )
    return assessment


@router.put(
    "/site-assessments/{assessment_id}",
    response_model=SiteAssessment,
    summary="Update a site assessment",
    description="Update assessment details. Site rating is recomputed if any sub-score changes.",
)
async def update_site_assessment(
    assessment_id: str, payload: SiteAssessmentUpdate
) -> SiteAssessment:
    svc = get_protocol_feasibility_service()
    updated = svc.update_site_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Site assessment '{assessment_id}' not found"
        )
    return updated


# ---------------------------------------------------------------------------
# Competitive Landscape
# ---------------------------------------------------------------------------


@router.get(
    "/studies/{study_id}/competitive-landscape",
    response_model=CompetitiveLandscapeListResponse,
    summary="List competitive landscape entries",
    description="Retrieve competing trials with optional filtering by threat level.",
)
async def list_competitive_landscape(
    study_id: str,
    threat_level: Optional[CompetitiveThreatLevel] = Query(
        None, description="Filter by threat level"
    ),
) -> CompetitiveLandscapeListResponse:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    items = svc.list_competitive_landscape(study_id, threat_level=threat_level)
    return CompetitiveLandscapeListResponse(items=items, total=len(items))


@router.post(
    "/studies/{study_id}/competitive-landscape",
    response_model=CompetitiveLandscape,
    status_code=201,
    summary="Add a competitive landscape entry",
)
async def create_competitive_entry(
    study_id: str, payload: CompetitiveLandscapeCreate
) -> CompetitiveLandscape:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    return svc.create_competitive_entry(study_id, payload)


@router.get(
    "/competitive-landscape/{entry_id}",
    response_model=CompetitiveLandscape,
    summary="Get a competitive landscape entry",
)
async def get_competitive_entry(entry_id: str) -> CompetitiveLandscape:
    svc = get_protocol_feasibility_service()
    entry = svc.get_competitive_entry(entry_id)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Competitive entry '{entry_id}' not found"
        )
    return entry


@router.put(
    "/competitive-landscape/{entry_id}",
    response_model=CompetitiveLandscape,
    summary="Update a competitive landscape entry",
)
async def update_competitive_entry(
    entry_id: str, payload: CompetitiveLandscapeUpdate
) -> CompetitiveLandscape:
    svc = get_protocol_feasibility_service()
    updated = svc.update_competitive_entry(entry_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Competitive entry '{entry_id}' not found"
        )
    return updated


# ---------------------------------------------------------------------------
# Enrollment Projections
# ---------------------------------------------------------------------------


@router.get(
    "/studies/{study_id}/enrollment-projections",
    response_model=EnrollmentProjectionListResponse,
    summary="List enrollment projections",
    description="Retrieve enrollment projection scenarios for a study.",
)
async def list_enrollment_projections(study_id: str) -> EnrollmentProjectionListResponse:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    items = svc.list_enrollment_projections(study_id)
    return EnrollmentProjectionListResponse(items=items, total=len(items))


@router.post(
    "/studies/{study_id}/enrollment-projections",
    response_model=EnrollmentProjection,
    status_code=201,
    summary="Create an enrollment projection",
    description="Create a projection scenario. Enrollment months, totals, risk, and confidence are auto-computed.",
)
async def create_enrollment_projection(
    study_id: str, payload: EnrollmentProjectionCreate
) -> EnrollmentProjection:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    return svc.create_enrollment_projection(study_id, payload)


@router.get(
    "/enrollment-projections/{projection_id}",
    response_model=EnrollmentProjection,
    summary="Get an enrollment projection",
)
async def get_enrollment_projection(projection_id: str) -> EnrollmentProjection:
    svc = get_protocol_feasibility_service()
    projection = svc.get_enrollment_projection(projection_id)
    if projection is None:
        raise HTTPException(
            status_code=404, detail=f"Enrollment projection '{projection_id}' not found"
        )
    return projection


# ---------------------------------------------------------------------------
# Feasibility Summary
# ---------------------------------------------------------------------------


@router.get(
    "/studies/{study_id}/summary",
    response_model=FeasibilitySummary,
    summary="Get feasibility summary",
    description="Compute an aggregated feasibility summary including site ratings, "
                "enrollment range, top risks, and recommendations.",
)
async def get_feasibility_summary(study_id: str) -> FeasibilitySummary:
    svc = get_protocol_feasibility_service()
    summary = svc.get_feasibility_summary(study_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    return summary


# ---------------------------------------------------------------------------
# Questionnaire
# ---------------------------------------------------------------------------


@router.get(
    "/studies/{study_id}/questionnaire",
    response_model=FeasibilityQuestionListResponse,
    summary="List questionnaire questions",
    description="Retrieve the feasibility questionnaire for a study.",
)
async def list_questionnaire(study_id: str) -> FeasibilityQuestionListResponse:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    items = svc.list_questions(study_id)
    return FeasibilityQuestionListResponse(items=items, total=len(items))


@router.post(
    "/studies/{study_id}/questionnaire",
    response_model=FeasibilityQuestion,
    status_code=201,
    summary="Add a questionnaire question",
)
async def create_question(
    study_id: str, payload: FeasibilityQuestionCreate
) -> FeasibilityQuestion:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    return svc.create_question(study_id, payload)


@router.post(
    "/studies/{study_id}/questionnaire-responses",
    response_model=SiteQuestionnaireResponse,
    status_code=201,
    summary="Submit a questionnaire response",
    description="Submit a site's response to a feasibility questionnaire question.",
)
async def submit_questionnaire_response(
    study_id: str, payload: QuestionnaireResponseCreate
) -> SiteQuestionnaireResponse:
    svc = get_protocol_feasibility_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Feasibility study '{study_id}' not found")
    try:
        return svc.submit_questionnaire_response(study_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=FeasibilityMetrics,
    summary="Get feasibility metrics",
    description="Aggregated protocol feasibility operational metrics.",
)
async def get_metrics() -> FeasibilityMetrics:
    svc = get_protocol_feasibility_service()
    return svc.get_metrics()
