"""Training & Competency Management API endpoints (CLINICAL-13).

Provides comprehensive training operations: course definitions & management,
training assignment CRUD with completion tracking, competency assessments,
training matrix by role, auto-assignment based on role/matrix, certification
expiry tracking, re-certification reminders, compliance reporting by role
and site, overdue detection, competency gap analysis, and training metrics.

Endpoints:
    GET    /training/courses                                    - List courses
    GET    /training/courses/{course_id}                        - Get single course
    POST   /training/courses                                    - Create course
    PUT    /training/courses/{course_id}                        - Update course
    DELETE /training/courses/{course_id}                        - Delete course
    GET    /training/assignments                                - List assignments
    GET    /training/assignments/{assignment_id}                - Get single assignment
    POST   /training/assignments                                - Create assignment
    PUT    /training/assignments/{assignment_id}                - Update assignment
    DELETE /training/assignments/{assignment_id}                - Delete assignment
    POST   /training/assignments/{assignment_id}/complete       - Complete assignment
    GET    /training/assignments/overdue                        - Overdue assignments
    GET    /training/assessments                                - List competency assessments
    GET    /training/assessments/{assessment_id}                - Get single assessment
    POST   /training/assessments                                - Create assessment
    PUT    /training/assessments/{assessment_id}                - Update assessment
    DELETE /training/assessments/{assessment_id}                - Delete assessment
    GET    /training/matrix                                     - Get full training matrix
    GET    /training/matrix/{role}                              - Get matrix for role
    POST   /training/auto-assign                                - Auto-assign by role
    GET    /training/certifications/expiring                    - Expiring certifications
    GET    /training/certifications/reminders                   - Re-certification reminders
    GET    /training/compliance/by-role                         - Compliance by role
    GET    /training/compliance/by-site                         - Compliance by site
    GET    /training/competency-gap/{user_id}                   - Competency gap analysis
    GET    /training/metrics                                    - Training dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.training_management import (
    AutoAssignRequest,
    AutoAssignResponse,
    CertificationExpiryListResponse,
    CompetencyAssessment,
    CompetencyAssessmentCreate,
    CompetencyAssessmentListResponse,
    CompetencyAssessmentUpdate,
    CompetencyGapAnalysis,
    CompetencyLevel,
    CompletionStatus,
    RecertificationReminderListResponse,
    TrainingAssignment,
    TrainingAssignmentComplete,
    TrainingAssignmentCreate,
    TrainingAssignmentListResponse,
    TrainingAssignmentUpdate,
    TrainingCourse,
    TrainingCourseCreate,
    TrainingCourseListResponse,
    TrainingCourseUpdate,
    TrainingMatrix,
    TrainingMatrixListResponse,
    TrainingMetrics,
    TrainingType,
)
from app.services.training_management_service import get_training_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/training",
    tags=["Training & Competency"],
)


# ---------------------------------------------------------------------------
# Course Management
# ---------------------------------------------------------------------------


@router.get(
    "/courses",
    response_model=TrainingCourseListResponse,
    summary="List training courses",
    description="Retrieve training courses with optional filtering by type and role.",
)
async def list_courses(
    training_type: Optional[TrainingType] = Query(None, description="Filter by training type"),
    role: Optional[str] = Query(None, description="Filter by required role"),
) -> TrainingCourseListResponse:
    svc = get_training_service()
    items = svc.list_courses(training_type=training_type, role=role)
    return TrainingCourseListResponse(items=items, total=len(items))


@router.get(
    "/courses/{course_id}",
    response_model=TrainingCourse,
    summary="Get a training course",
)
async def get_course(course_id: str) -> TrainingCourse:
    svc = get_training_service()
    course = svc.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found")
    return course


@router.post(
    "/courses",
    response_model=TrainingCourse,
    status_code=201,
    summary="Create a training course",
)
async def create_course(payload: TrainingCourseCreate) -> TrainingCourse:
    svc = get_training_service()
    return svc.create_course(payload)


@router.put(
    "/courses/{course_id}",
    response_model=TrainingCourse,
    summary="Update a training course",
)
async def update_course(course_id: str, payload: TrainingCourseUpdate) -> TrainingCourse:
    svc = get_training_service()
    updated = svc.update_course(course_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found")
    return updated


@router.delete(
    "/courses/{course_id}",
    status_code=204,
    summary="Delete a training course",
)
async def delete_course(course_id: str) -> None:
    svc = get_training_service()
    deleted = svc.delete_course(course_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found")


# ---------------------------------------------------------------------------
# Training Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/assignments",
    response_model=TrainingAssignmentListResponse,
    summary="List training assignments",
    description="Retrieve training assignments with optional filtering by user, course, site, status, and role.",
)
async def list_assignments(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[CompletionStatus] = Query(None, description="Filter by status"),
    role: Optional[str] = Query(None, description="Filter by role"),
) -> TrainingAssignmentListResponse:
    svc = get_training_service()
    items = svc.list_assignments(
        user_id=user_id, course_id=course_id, site_id=site_id,
        status=status, role=role,
    )
    return TrainingAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/assignments/overdue",
    response_model=TrainingAssignmentListResponse,
    summary="Get overdue assignments",
    description="Retrieve training assignments that are past their due date and not yet completed.",
)
async def get_overdue_assignments() -> TrainingAssignmentListResponse:
    svc = get_training_service()
    items = svc.get_overdue_assignments()
    return TrainingAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/assignments/{assignment_id}",
    response_model=TrainingAssignment,
    summary="Get a training assignment",
)
async def get_assignment(assignment_id: str) -> TrainingAssignment:
    svc = get_training_service()
    assignment = svc.get_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found")
    return assignment


@router.post(
    "/assignments",
    response_model=TrainingAssignment,
    status_code=201,
    summary="Create a training assignment",
)
async def create_assignment(payload: TrainingAssignmentCreate) -> TrainingAssignment:
    svc = get_training_service()
    try:
        return svc.create_assignment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/assignments/{assignment_id}",
    response_model=TrainingAssignment,
    summary="Update a training assignment",
)
async def update_assignment(
    assignment_id: str, payload: TrainingAssignmentUpdate
) -> TrainingAssignment:
    svc = get_training_service()
    updated = svc.update_assignment(assignment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found")
    return updated


@router.delete(
    "/assignments/{assignment_id}",
    status_code=204,
    summary="Delete a training assignment",
)
async def delete_assignment(assignment_id: str) -> None:
    svc = get_training_service()
    deleted = svc.delete_assignment(assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found")


@router.post(
    "/assignments/{assignment_id}/complete",
    response_model=TrainingAssignment,
    summary="Complete a training assignment",
    description="Mark a training assignment as completed with a score. "
                "If the score meets the passing threshold, a certificate is issued.",
)
async def complete_assignment(
    assignment_id: str, payload: TrainingAssignmentComplete
) -> TrainingAssignment:
    svc = get_training_service()
    try:
        result = svc.complete_assignment(assignment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Competency Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=CompetencyAssessmentListResponse,
    summary="List competency assessments",
    description="Retrieve competency assessments with optional filtering by user, skill area, and level.",
)
async def list_assessments(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    skill_area: Optional[str] = Query(None, description="Filter by skill area (partial match)"),
    level: Optional[CompetencyLevel] = Query(None, description="Filter by competency level"),
) -> CompetencyAssessmentListResponse:
    svc = get_training_service()
    items = svc.list_assessments(user_id=user_id, skill_area=skill_area, level=level)
    return CompetencyAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=CompetencyAssessment,
    summary="Get a competency assessment",
)
async def get_assessment(assessment_id: str) -> CompetencyAssessment:
    svc = get_training_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=CompetencyAssessment,
    status_code=201,
    summary="Create a competency assessment",
)
async def create_assessment(payload: CompetencyAssessmentCreate) -> CompetencyAssessment:
    svc = get_training_service()
    return svc.create_assessment(payload)


@router.put(
    "/assessments/{assessment_id}",
    response_model=CompetencyAssessment,
    summary="Update a competency assessment",
)
async def update_assessment(
    assessment_id: str, payload: CompetencyAssessmentUpdate
) -> CompetencyAssessment:
    svc = get_training_service()
    updated = svc.update_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a competency assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_training_service()
    deleted = svc.delete_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Training Matrix
# ---------------------------------------------------------------------------


@router.get(
    "/matrix",
    response_model=TrainingMatrixListResponse,
    summary="Get full training matrix",
    description="Retrieve the training matrix showing required and optional courses for each role.",
)
async def get_training_matrix() -> TrainingMatrixListResponse:
    svc = get_training_service()
    items = svc.list_training_matrix()
    return TrainingMatrixListResponse(items=items, total=len(items))


@router.get(
    "/matrix/{role}",
    response_model=TrainingMatrix,
    summary="Get training matrix for a role",
)
async def get_role_training_matrix(role: str) -> TrainingMatrix:
    svc = get_training_service()
    matrix = svc.get_training_matrix(role)
    if matrix is None:
        raise HTTPException(status_code=404, detail=f"Training matrix for role '{role}' not found")
    return matrix


# ---------------------------------------------------------------------------
# Auto-Assignment
# ---------------------------------------------------------------------------


@router.post(
    "/auto-assign",
    response_model=AutoAssignResponse,
    summary="Auto-assign training by role",
    description="Automatically assign required training courses to a user based on their role "
                "and the training matrix. Skips courses already assigned.",
)
async def auto_assign_training(payload: AutoAssignRequest) -> AutoAssignResponse:
    svc = get_training_service()
    try:
        return svc.auto_assign(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Certification Expiry
# ---------------------------------------------------------------------------


@router.get(
    "/certifications/expiring",
    response_model=CertificationExpiryListResponse,
    summary="Get expiring certifications",
    description="Retrieve certifications that are expiring within the specified number of days.",
)
async def get_expiring_certifications(
    days: int = Query(default=30, ge=1, le=365, description="Days until expiry threshold"),
) -> CertificationExpiryListResponse:
    svc = get_training_service()
    items = svc.get_expiring_certifications(days=days)
    return CertificationExpiryListResponse(items=items, total=len(items))


@router.get(
    "/certifications/reminders",
    response_model=RecertificationReminderListResponse,
    summary="Get re-certification reminders",
    description="Retrieve re-certification reminders for training expiring within 90 days, "
                "prioritized as urgent (<=7d), warning (<=30d), or info (<=90d).",
)
async def get_recertification_reminders() -> RecertificationReminderListResponse:
    svc = get_training_service()
    items = svc.get_recertification_reminders()
    return RecertificationReminderListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Compliance Reporting
# ---------------------------------------------------------------------------


@router.get(
    "/compliance/by-role",
    response_model=dict[str, float],
    summary="Get compliance rates by role",
    description="Calculate training compliance rates for each role.",
)
async def get_compliance_by_role() -> dict[str, float]:
    svc = get_training_service()
    return svc.calculate_compliance_by_role()


@router.get(
    "/compliance/by-site",
    response_model=dict[str, float],
    summary="Get compliance rates by site",
    description="Calculate training compliance rates for each site.",
)
async def get_compliance_by_site() -> dict[str, float]:
    svc = get_training_service()
    return svc.calculate_compliance_by_site()


# ---------------------------------------------------------------------------
# Competency Gap Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/competency-gap/{user_id}",
    response_model=CompetencyGapAnalysis,
    summary="Get competency gap analysis",
    description="Perform competency gap analysis for a user, identifying training gaps "
                "and providing recommendations based on role requirements.",
)
async def get_competency_gap(user_id: str) -> CompetencyGapAnalysis:
    svc = get_training_service()
    result = svc.get_competency_gap_analysis(user_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=TrainingMetrics,
    summary="Get training dashboard metrics",
    description="Aggregated training & competency metrics including completion rates, "
                "overdue counts, average scores, and compliance by role/site.",
)
async def get_metrics() -> TrainingMetrics:
    svc = get_training_service()
    return svc.get_metrics()
