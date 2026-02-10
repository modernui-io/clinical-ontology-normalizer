"""Language & Translation Services API endpoints.

Provides comprehensive translation management: project lifecycle, task assignment
and tracking, linguistic validation with forward-backward and cognitive debriefing
methods, certified translator management, multilingual glossary maintenance,
workflow operations (assign, submit, certify), project progress tracking,
and language metrics.

Endpoints:
    GET    /language-services/projects                              - List projects
    GET    /language-services/projects/{project_id}                 - Get single project
    POST   /language-services/projects                              - Create project
    PUT    /language-services/projects/{project_id}                 - Update project
    DELETE /language-services/projects/{project_id}                 - Delete project
    GET    /language-services/projects/{project_id}/progress        - Get project progress
    GET    /language-services/tasks                                 - List tasks
    GET    /language-services/tasks/{task_id}                       - Get single task
    POST   /language-services/tasks                                 - Create task
    PUT    /language-services/tasks/{task_id}                       - Update task
    DELETE /language-services/tasks/{task_id}                       - Delete task
    POST   /language-services/tasks/{task_id}/assign-translator     - Assign translator
    POST   /language-services/tasks/{task_id}/submit-translation    - Submit translation
    POST   /language-services/tasks/{task_id}/certify               - Certify translation
    GET    /language-services/validations                           - List validations
    GET    /language-services/validations/{validation_id}           - Get single validation
    POST   /language-services/validations                           - Create validation
    PUT    /language-services/validations/{validation_id}           - Update validation
    DELETE /language-services/validations/{validation_id}           - Delete validation
    GET    /language-services/translators                           - List translators
    GET    /language-services/translators/{translator_id}           - Get single translator
    POST   /language-services/translators                           - Create translator
    PUT    /language-services/translators/{translator_id}           - Update translator
    DELETE /language-services/translators/{translator_id}           - Delete translator
    GET    /language-services/glossary                              - List glossary entries
    GET    /language-services/glossary/{entry_id}                   - Get single glossary entry
    POST   /language-services/glossary                              - Create glossary entry
    PUT    /language-services/glossary/{entry_id}                   - Update glossary entry
    DELETE /language-services/glossary/{entry_id}                   - Delete glossary entry
    GET    /language-services/metrics                               - Language metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.language_services import (
    CertificationLevel,
    CertifiedTranslator,
    CertifiedTranslatorCreate,
    CertifiedTranslatorListResponse,
    CertifiedTranslatorUpdate,
    DocumentCategory,
    LanguageMetrics,
    LinguisticValidation,
    LinguisticValidationCreate,
    LinguisticValidationListResponse,
    LinguisticValidationUpdate,
    ProjectProgress,
    TranslationCertification,
    TranslationGlossary,
    TranslationGlossaryCreate,
    TranslationGlossaryListResponse,
    TranslationGlossaryUpdate,
    TranslationProject,
    TranslationProjectCreate,
    TranslationProjectListResponse,
    TranslationProjectUpdate,
    TranslationStatus,
    TranslationSubmission,
    TranslationTask,
    TranslationTaskCreate,
    TranslationTaskListResponse,
    TranslationTaskUpdate,
    TranslatorAssignment,
    TranslatorStatus,
    ValidationMethod,
)
from app.services.language_services_service import get_language_services_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/language-services",
    tags=["Language Services"],
)


# ---------------------------------------------------------------------------
# Translation Project Management
# ---------------------------------------------------------------------------


@router.get(
    "/projects",
    response_model=TranslationProjectListResponse,
    summary="List translation projects",
    description="Retrieve translation projects with optional filtering by trial, status, and document category.",
)
async def list_projects(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[TranslationStatus] = Query(None, description="Filter by status"),
    document_category: Optional[DocumentCategory] = Query(None, description="Filter by document category"),
) -> TranslationProjectListResponse:
    svc = get_language_services_service()
    items = svc.list_projects(trial_id=trial_id, status=status, document_category=document_category)
    return TranslationProjectListResponse(items=items, total=len(items))


@router.get(
    "/projects/{project_id}",
    response_model=TranslationProject,
    summary="Get a translation project",
)
async def get_project(project_id: str) -> TranslationProject:
    svc = get_language_services_service()
    project = svc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


@router.post(
    "/projects",
    response_model=TranslationProject,
    status_code=201,
    summary="Create a translation project",
)
async def create_project(payload: TranslationProjectCreate) -> TranslationProject:
    svc = get_language_services_service()
    return svc.create_project(payload)


@router.put(
    "/projects/{project_id}",
    response_model=TranslationProject,
    summary="Update a translation project",
)
async def update_project(
    project_id: str, payload: TranslationProjectUpdate
) -> TranslationProject:
    svc = get_language_services_service()
    updated = svc.update_project(project_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return updated


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    summary="Delete a translation project",
)
async def delete_project(project_id: str) -> None:
    svc = get_language_services_service()
    deleted = svc.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get(
    "/projects/{project_id}/progress",
    response_model=ProjectProgress,
    summary="Get project progress",
    description="Retrieve progress summary for a translation project including task completion, word counts, and validation results.",
)
async def get_project_progress(project_id: str) -> ProjectProgress:
    svc = get_language_services_service()
    progress = svc.get_project_progress(project_id)
    if progress is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return progress


# ---------------------------------------------------------------------------
# Translation Task Management
# ---------------------------------------------------------------------------


@router.get(
    "/tasks",
    response_model=TranslationTaskListResponse,
    summary="List translation tasks",
    description="Retrieve translation tasks with optional filtering by project, status, target language, and translator.",
)
async def list_tasks(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status: Optional[TranslationStatus] = Query(None, description="Filter by status"),
    target_language: Optional[str] = Query(None, description="Filter by target language"),
    translator_id: Optional[str] = Query(None, description="Filter by translator ID"),
) -> TranslationTaskListResponse:
    svc = get_language_services_service()
    items = svc.list_tasks(
        project_id=project_id, status=status,
        target_language=target_language, translator_id=translator_id,
    )
    return TranslationTaskListResponse(items=items, total=len(items))


@router.get(
    "/tasks/{task_id}",
    response_model=TranslationTask,
    summary="Get a translation task",
)
async def get_task(task_id: str) -> TranslationTask:
    svc = get_language_services_service()
    task = svc.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.post(
    "/tasks",
    response_model=TranslationTask,
    status_code=201,
    summary="Create a translation task",
)
async def create_task(payload: TranslationTaskCreate) -> TranslationTask:
    svc = get_language_services_service()
    return svc.create_task(payload)


@router.put(
    "/tasks/{task_id}",
    response_model=TranslationTask,
    summary="Update a translation task",
)
async def update_task(
    task_id: str, payload: TranslationTaskUpdate
) -> TranslationTask:
    svc = get_language_services_service()
    updated = svc.update_task(task_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return updated


@router.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a translation task",
)
async def delete_task(task_id: str) -> None:
    svc = get_language_services_service()
    deleted = svc.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")


# ---------------------------------------------------------------------------
# Workflow Operations
# ---------------------------------------------------------------------------


@router.post(
    "/tasks/{task_id}/assign-translator",
    response_model=TranslationTask,
    summary="Assign a translator to a task",
    description="Assign a certified translator and optional reviewer to a task. Moves task to in_progress status.",
)
async def assign_translator(
    task_id: str, payload: TranslatorAssignment
) -> TranslationTask:
    svc = get_language_services_service()
    try:
        result = svc.assign_translator(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return result


@router.post(
    "/tasks/{task_id}/submit-translation",
    response_model=TranslationTask,
    summary="Submit a translation",
    description="Submit a completed translation for a task. Includes translated document reference and optional back-translation.",
)
async def submit_translation(
    task_id: str, payload: TranslationSubmission
) -> TranslationTask:
    svc = get_language_services_service()
    result = svc.submit_translation(task_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return result


@router.post(
    "/tasks/{task_id}/certify",
    response_model=TranslationTask,
    summary="Certify a translation",
    description="Certify a completed translation. Moves task to certified status.",
)
async def certify_translation(
    task_id: str, payload: TranslationCertification
) -> TranslationTask:
    svc = get_language_services_service()
    result = svc.certify_translation(task_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Linguistic Validation Management
# ---------------------------------------------------------------------------


@router.get(
    "/validations",
    response_model=LinguisticValidationListResponse,
    summary="List linguistic validations",
    description="Retrieve linguistic validations with optional filtering by task and method.",
)
async def list_validations(
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    method: Optional[ValidationMethod] = Query(None, description="Filter by validation method"),
) -> LinguisticValidationListResponse:
    svc = get_language_services_service()
    items = svc.list_validations(task_id=task_id, method=method)
    return LinguisticValidationListResponse(items=items, total=len(items))


@router.get(
    "/validations/{validation_id}",
    response_model=LinguisticValidation,
    summary="Get a linguistic validation",
)
async def get_validation(validation_id: str) -> LinguisticValidation:
    svc = get_language_services_service()
    validation = svc.get_validation(validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return validation


@router.post(
    "/validations",
    response_model=LinguisticValidation,
    status_code=201,
    summary="Create a linguistic validation",
)
async def create_validation(payload: LinguisticValidationCreate) -> LinguisticValidation:
    svc = get_language_services_service()
    try:
        return svc.create_validation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/validations/{validation_id}",
    response_model=LinguisticValidation,
    summary="Update a linguistic validation",
)
async def update_validation(
    validation_id: str, payload: LinguisticValidationUpdate
) -> LinguisticValidation:
    svc = get_language_services_service()
    updated = svc.update_validation(validation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return updated


@router.delete(
    "/validations/{validation_id}",
    status_code=204,
    summary="Delete a linguistic validation",
)
async def delete_validation(validation_id: str) -> None:
    svc = get_language_services_service()
    deleted = svc.delete_validation(validation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")


# ---------------------------------------------------------------------------
# Certified Translator Management
# ---------------------------------------------------------------------------


@router.get(
    "/translators",
    response_model=CertifiedTranslatorListResponse,
    summary="List certified translators",
    description="Retrieve certified translators with optional filtering by status, language, and certification level.",
)
async def list_translators(
    status: Optional[TranslatorStatus] = Query(None, description="Filter by translator status"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    certification_level: Optional[CertificationLevel] = Query(None, description="Filter by certification level"),
) -> CertifiedTranslatorListResponse:
    svc = get_language_services_service()
    items = svc.list_translators(
        status=status, language=language,
        certification_level=certification_level,
    )
    return CertifiedTranslatorListResponse(items=items, total=len(items))


@router.get(
    "/translators/{translator_id}",
    response_model=CertifiedTranslator,
    summary="Get a certified translator",
)
async def get_translator(translator_id: str) -> CertifiedTranslator:
    svc = get_language_services_service()
    translator = svc.get_translator(translator_id)
    if translator is None:
        raise HTTPException(status_code=404, detail=f"Translator '{translator_id}' not found")
    return translator


@router.post(
    "/translators",
    response_model=CertifiedTranslator,
    status_code=201,
    summary="Register a certified translator",
)
async def create_translator(payload: CertifiedTranslatorCreate) -> CertifiedTranslator:
    svc = get_language_services_service()
    return svc.create_translator(payload)


@router.put(
    "/translators/{translator_id}",
    response_model=CertifiedTranslator,
    summary="Update a certified translator",
)
async def update_translator(
    translator_id: str, payload: CertifiedTranslatorUpdate
) -> CertifiedTranslator:
    svc = get_language_services_service()
    updated = svc.update_translator(translator_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Translator '{translator_id}' not found")
    return updated


@router.delete(
    "/translators/{translator_id}",
    status_code=204,
    summary="Delete a certified translator",
)
async def delete_translator(translator_id: str) -> None:
    svc = get_language_services_service()
    deleted = svc.delete_translator(translator_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Translator '{translator_id}' not found")


# ---------------------------------------------------------------------------
# Translation Glossary Management
# ---------------------------------------------------------------------------


@router.get(
    "/glossary",
    response_model=TranslationGlossaryListResponse,
    summary="List glossary entries",
    description="Retrieve glossary entries with optional filtering by trial, source language, and approval status.",
)
async def list_glossary(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    source_language: Optional[str] = Query(None, description="Filter by source language"),
    approved: Optional[bool] = Query(None, description="Filter by approval status"),
) -> TranslationGlossaryListResponse:
    svc = get_language_services_service()
    items = svc.list_glossary(
        trial_id=trial_id, source_language=source_language, approved=approved,
    )
    return TranslationGlossaryListResponse(items=items, total=len(items))


@router.get(
    "/glossary/{entry_id}",
    response_model=TranslationGlossary,
    summary="Get a glossary entry",
)
async def get_glossary_entry(entry_id: str) -> TranslationGlossary:
    svc = get_language_services_service()
    entry = svc.get_glossary_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Glossary entry '{entry_id}' not found")
    return entry


@router.post(
    "/glossary",
    response_model=TranslationGlossary,
    status_code=201,
    summary="Create a glossary entry",
)
async def create_glossary_entry(payload: TranslationGlossaryCreate) -> TranslationGlossary:
    svc = get_language_services_service()
    return svc.create_glossary_entry(payload)


@router.put(
    "/glossary/{entry_id}",
    response_model=TranslationGlossary,
    summary="Update a glossary entry",
)
async def update_glossary_entry(
    entry_id: str, payload: TranslationGlossaryUpdate
) -> TranslationGlossary:
    svc = get_language_services_service()
    updated = svc.update_glossary_entry(entry_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Glossary entry '{entry_id}' not found")
    return updated


@router.delete(
    "/glossary/{entry_id}",
    status_code=204,
    summary="Delete a glossary entry",
)
async def delete_glossary_entry(entry_id: str) -> None:
    svc = get_language_services_service()
    deleted = svc.delete_glossary_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Glossary entry '{entry_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=LanguageMetrics,
    summary="Get language services metrics",
    description="Aggregated Language & Translation Services metrics including project/task counts, "
                "validation scores, translator statistics, and glossary coverage.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> LanguageMetrics:
    svc = get_language_services_service()
    return svc.get_metrics(trial_id=trial_id)
