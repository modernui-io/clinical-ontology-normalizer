"""Protocol Knowledge Assessment API endpoints (PKA-ASM).

Provides comprehensive protocol knowledge assessment operations: assessment
questionnaires, assessment responses, competency records, remediation plans,
and assessment metrics.

Endpoints:
    GET    /protocol-knowledge-assessment/assessment-questionnaires                          - List questionnaires
    GET    /protocol-knowledge-assessment/assessment-questionnaires/{questionnaire_id}       - Get single questionnaire
    POST   /protocol-knowledge-assessment/assessment-questionnaires                          - Create questionnaire
    PUT    /protocol-knowledge-assessment/assessment-questionnaires/{questionnaire_id}       - Update questionnaire
    DELETE /protocol-knowledge-assessment/assessment-questionnaires/{questionnaire_id}       - Delete questionnaire
    GET    /protocol-knowledge-assessment/assessment-responses                               - List responses
    GET    /protocol-knowledge-assessment/assessment-responses/{response_id}                 - Get single response
    POST   /protocol-knowledge-assessment/assessment-responses                               - Create response
    PUT    /protocol-knowledge-assessment/assessment-responses/{response_id}                 - Update response
    DELETE /protocol-knowledge-assessment/assessment-responses/{response_id}                 - Delete response
    GET    /protocol-knowledge-assessment/competency-records                                 - List competency records
    GET    /protocol-knowledge-assessment/competency-records/{record_id}                     - Get single record
    POST   /protocol-knowledge-assessment/competency-records                                 - Create record
    PUT    /protocol-knowledge-assessment/competency-records/{record_id}                     - Update record
    DELETE /protocol-knowledge-assessment/competency-records/{record_id}                     - Delete record
    GET    /protocol-knowledge-assessment/remediation-plans                                  - List plans
    GET    /protocol-knowledge-assessment/remediation-plans/{plan_id}                        - Get single plan
    POST   /protocol-knowledge-assessment/remediation-plans                                  - Create plan
    PUT    /protocol-knowledge-assessment/remediation-plans/{plan_id}                        - Update plan
    DELETE /protocol-knowledge-assessment/remediation-plans/{plan_id}                        - Delete plan
    GET    /protocol-knowledge-assessment/metrics                                            - Assessment metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.protocol_knowledge_assessment import (
    AssessmentQuestionnaire,
    AssessmentQuestionnaireCreate,
    AssessmentQuestionnaireListResponse,
    AssessmentQuestionnaireUpdate,
    AssessmentResponse,
    AssessmentResponseCreate,
    AssessmentResponseListResponse,
    AssessmentResponseUpdate,
    AssessmentResult,
    CompetencyLevel,
    CompetencyRecord,
    CompetencyRecordCreate,
    CompetencyRecordListResponse,
    CompetencyRecordUpdate,
    ProtocolKnowledgeMetrics,
    QuestionnaireStatus,
    RemediationPlan,
    RemediationPlanCreate,
    RemediationPlanListResponse,
    RemediationPlanUpdate,
    RemediationStatus,
)
from app.services.protocol_knowledge_assessment_service import (
    get_protocol_knowledge_assessment_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/protocol-knowledge-assessment",
    tags=["Protocol Knowledge Assessment"],
)


# ---------------------------------------------------------------------------
# Assessment Questionnaires
# ---------------------------------------------------------------------------


@router.get(
    "/assessment-questionnaires",
    response_model=AssessmentQuestionnaireListResponse,
    summary="List assessment questionnaires",
    description="Retrieve assessment questionnaires with optional filtering by trial and status.",
)
async def list_assessment_questionnaires(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    questionnaire_status: Optional[QuestionnaireStatus] = Query(
        None, description="Filter by questionnaire status"
    ),
) -> AssessmentQuestionnaireListResponse:
    svc = get_protocol_knowledge_assessment_service()
    items = svc.list_assessment_questionnaires(
        trial_id=trial_id, questionnaire_status=questionnaire_status
    )
    return AssessmentQuestionnaireListResponse(items=items, total=len(items))


@router.get(
    "/assessment-questionnaires/{questionnaire_id}",
    response_model=AssessmentQuestionnaire,
    summary="Get an assessment questionnaire",
)
async def get_assessment_questionnaire(questionnaire_id: str) -> AssessmentQuestionnaire:
    svc = get_protocol_knowledge_assessment_service()
    record = svc.get_assessment_questionnaire(questionnaire_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment questionnaire '{questionnaire_id}' not found",
        )
    return record


@router.post(
    "/assessment-questionnaires",
    response_model=AssessmentQuestionnaire,
    status_code=201,
    summary="Create an assessment questionnaire",
)
async def create_assessment_questionnaire(
    payload: AssessmentQuestionnaireCreate,
) -> AssessmentQuestionnaire:
    svc = get_protocol_knowledge_assessment_service()
    return svc.create_assessment_questionnaire(payload)


@router.put(
    "/assessment-questionnaires/{questionnaire_id}",
    response_model=AssessmentQuestionnaire,
    summary="Update an assessment questionnaire",
)
async def update_assessment_questionnaire(
    questionnaire_id: str, payload: AssessmentQuestionnaireUpdate
) -> AssessmentQuestionnaire:
    svc = get_protocol_knowledge_assessment_service()
    updated = svc.update_assessment_questionnaire(questionnaire_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment questionnaire '{questionnaire_id}' not found",
        )
    return updated


@router.delete(
    "/assessment-questionnaires/{questionnaire_id}",
    status_code=204,
    summary="Delete an assessment questionnaire",
)
async def delete_assessment_questionnaire(questionnaire_id: str) -> None:
    svc = get_protocol_knowledge_assessment_service()
    deleted = svc.delete_assessment_questionnaire(questionnaire_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment questionnaire '{questionnaire_id}' not found",
        )


# ---------------------------------------------------------------------------
# Assessment Responses
# ---------------------------------------------------------------------------


@router.get(
    "/assessment-responses",
    response_model=AssessmentResponseListResponse,
    summary="List assessment responses",
    description="Retrieve assessment responses with optional filtering by trial, result, and questionnaire.",
)
async def list_assessment_responses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    assessment_result: Optional[AssessmentResult] = Query(
        None, description="Filter by assessment result"
    ),
    questionnaire_id: Optional[str] = Query(None, description="Filter by questionnaire ID"),
) -> AssessmentResponseListResponse:
    svc = get_protocol_knowledge_assessment_service()
    items = svc.list_assessment_responses(
        trial_id=trial_id,
        assessment_result=assessment_result,
        questionnaire_id=questionnaire_id,
    )
    return AssessmentResponseListResponse(items=items, total=len(items))


@router.get(
    "/assessment-responses/{response_id}",
    response_model=AssessmentResponse,
    summary="Get an assessment response",
)
async def get_assessment_response(response_id: str) -> AssessmentResponse:
    svc = get_protocol_knowledge_assessment_service()
    record = svc.get_assessment_response(response_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment response '{response_id}' not found",
        )
    return record


@router.post(
    "/assessment-responses",
    response_model=AssessmentResponse,
    status_code=201,
    summary="Create an assessment response",
)
async def create_assessment_response(payload: AssessmentResponseCreate) -> AssessmentResponse:
    svc = get_protocol_knowledge_assessment_service()
    return svc.create_assessment_response(payload)


@router.put(
    "/assessment-responses/{response_id}",
    response_model=AssessmentResponse,
    summary="Update an assessment response",
)
async def update_assessment_response(
    response_id: str, payload: AssessmentResponseUpdate
) -> AssessmentResponse:
    svc = get_protocol_knowledge_assessment_service()
    updated = svc.update_assessment_response(response_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment response '{response_id}' not found",
        )
    return updated


@router.delete(
    "/assessment-responses/{response_id}",
    status_code=204,
    summary="Delete an assessment response",
)
async def delete_assessment_response(response_id: str) -> None:
    svc = get_protocol_knowledge_assessment_service()
    deleted = svc.delete_assessment_response(response_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment response '{response_id}' not found",
        )


# ---------------------------------------------------------------------------
# Competency Records
# ---------------------------------------------------------------------------


@router.get(
    "/competency-records",
    response_model=CompetencyRecordListResponse,
    summary="List competency records",
    description="Retrieve competency records with optional filtering by trial, level, and site.",
)
async def list_competency_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    competency_level: Optional[CompetencyLevel] = Query(
        None, description="Filter by competency level"
    ),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> CompetencyRecordListResponse:
    svc = get_protocol_knowledge_assessment_service()
    items = svc.list_competency_records(
        trial_id=trial_id, competency_level=competency_level, site_id=site_id
    )
    return CompetencyRecordListResponse(items=items, total=len(items))


@router.get(
    "/competency-records/{record_id}",
    response_model=CompetencyRecord,
    summary="Get a competency record",
)
async def get_competency_record(record_id: str) -> CompetencyRecord:
    svc = get_protocol_knowledge_assessment_service()
    record = svc.get_competency_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Competency record '{record_id}' not found",
        )
    return record


@router.post(
    "/competency-records",
    response_model=CompetencyRecord,
    status_code=201,
    summary="Create a competency record",
)
async def create_competency_record(payload: CompetencyRecordCreate) -> CompetencyRecord:
    svc = get_protocol_knowledge_assessment_service()
    return svc.create_competency_record(payload)


@router.put(
    "/competency-records/{record_id}",
    response_model=CompetencyRecord,
    summary="Update a competency record",
)
async def update_competency_record(
    record_id: str, payload: CompetencyRecordUpdate
) -> CompetencyRecord:
    svc = get_protocol_knowledge_assessment_service()
    updated = svc.update_competency_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Competency record '{record_id}' not found",
        )
    return updated


@router.delete(
    "/competency-records/{record_id}",
    status_code=204,
    summary="Delete a competency record",
)
async def delete_competency_record(record_id: str) -> None:
    svc = get_protocol_knowledge_assessment_service()
    deleted = svc.delete_competency_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Competency record '{record_id}' not found",
        )


# ---------------------------------------------------------------------------
# Remediation Plans
# ---------------------------------------------------------------------------


@router.get(
    "/remediation-plans",
    response_model=RemediationPlanListResponse,
    summary="List remediation plans",
    description="Retrieve remediation plans with optional filtering by trial and status.",
)
async def list_remediation_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    remediation_status: Optional[RemediationStatus] = Query(
        None, description="Filter by remediation status"
    ),
) -> RemediationPlanListResponse:
    svc = get_protocol_knowledge_assessment_service()
    items = svc.list_remediation_plans(
        trial_id=trial_id, remediation_status=remediation_status
    )
    return RemediationPlanListResponse(items=items, total=len(items))


@router.get(
    "/remediation-plans/{plan_id}",
    response_model=RemediationPlan,
    summary="Get a remediation plan",
)
async def get_remediation_plan(plan_id: str) -> RemediationPlan:
    svc = get_protocol_knowledge_assessment_service()
    record = svc.get_remediation_plan(plan_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Remediation plan '{plan_id}' not found",
        )
    return record


@router.post(
    "/remediation-plans",
    response_model=RemediationPlan,
    status_code=201,
    summary="Create a remediation plan",
)
async def create_remediation_plan(payload: RemediationPlanCreate) -> RemediationPlan:
    svc = get_protocol_knowledge_assessment_service()
    return svc.create_remediation_plan(payload)


@router.put(
    "/remediation-plans/{plan_id}",
    response_model=RemediationPlan,
    summary="Update a remediation plan",
)
async def update_remediation_plan(
    plan_id: str, payload: RemediationPlanUpdate
) -> RemediationPlan:
    svc = get_protocol_knowledge_assessment_service()
    updated = svc.update_remediation_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Remediation plan '{plan_id}' not found",
        )
    return updated


@router.delete(
    "/remediation-plans/{plan_id}",
    status_code=204,
    summary="Delete a remediation plan",
)
async def delete_remediation_plan(plan_id: str) -> None:
    svc = get_protocol_knowledge_assessment_service()
    deleted = svc.delete_remediation_plan(plan_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Remediation plan '{plan_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ProtocolKnowledgeMetrics,
    summary="Get protocol knowledge assessment metrics",
    description="Aggregated metrics across all protocol knowledge assessment operations.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ProtocolKnowledgeMetrics:
    svc = get_protocol_knowledge_assessment_service()
    return svc.get_metrics(trial_id=trial_id)
