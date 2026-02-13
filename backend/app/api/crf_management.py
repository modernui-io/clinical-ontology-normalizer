"""CRF Management API endpoints (CRF-MGT).

Provides comprehensive CRF management operations: CRF version control,
field definitions, edit check rules, CRF deployment tracking, CRF annotations,
and CRF metrics.

Endpoints:
    GET    /crf-management/crf-versions                              - List CRF versions
    GET    /crf-management/crf-versions/{version_id}                 - Get single version
    POST   /crf-management/crf-versions                              - Create version
    PUT    /crf-management/crf-versions/{version_id}                 - Update version
    DELETE /crf-management/crf-versions/{version_id}                 - Delete version
    GET    /crf-management/crf-fields                                - List CRF fields
    GET    /crf-management/crf-fields/{field_id}                     - Get single field
    POST   /crf-management/crf-fields                                - Create field
    PUT    /crf-management/crf-fields/{field_id}                     - Update field
    DELETE /crf-management/crf-fields/{field_id}                     - Delete field
    GET    /crf-management/edit-check-rules                          - List edit check rules
    GET    /crf-management/edit-check-rules/{rule_id}                - Get single rule
    POST   /crf-management/edit-check-rules                          - Create rule
    PUT    /crf-management/edit-check-rules/{rule_id}                - Update rule
    DELETE /crf-management/edit-check-rules/{rule_id}                - Delete rule
    GET    /crf-management/deployments                               - List deployments
    GET    /crf-management/deployments/{deployment_id}               - Get single deployment
    POST   /crf-management/deployments                               - Create deployment
    PUT    /crf-management/deployments/{deployment_id}               - Update deployment
    DELETE /crf-management/deployments/{deployment_id}               - Delete deployment
    GET    /crf-management/annotations                               - List annotations
    GET    /crf-management/annotations/{annotation_id}               - Get single annotation
    POST   /crf-management/annotations                               - Create annotation
    PUT    /crf-management/annotations/{annotation_id}               - Update annotation
    DELETE /crf-management/annotations/{annotation_id}               - Delete annotation
    GET    /crf-management/metrics                                   - CRF metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.crf_management import (
    AnnotationType,
    CRFAnnotation,
    CRFAnnotationCreate,
    CRFAnnotationListResponse,
    CRFAnnotationUpdate,
    CRFDeployment,
    CRFDeploymentCreate,
    CRFDeploymentListResponse,
    CRFDeploymentUpdate,
    CRFField,
    CRFFieldCreate,
    CRFFieldListResponse,
    CRFFieldUpdate,
    CRFManagementMetrics,
    CRFStatus,
    CRFVersion,
    CRFVersionCreate,
    CRFVersionListResponse,
    CRFVersionUpdate,
    DeploymentStatus,
    EditCheckRule,
    EditCheckRuleCreate,
    EditCheckRuleListResponse,
    EditCheckRuleUpdate,
    EditCheckSeverity,
    FieldType,
)
from app.services.crf_management_service import get_crf_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/crf-management",
    tags=["CRF Management"],
)


# ---------------------------------------------------------------------------
# CRF Versions
# ---------------------------------------------------------------------------


@router.get(
    "/crf-versions",
    response_model=CRFVersionListResponse,
    summary="List CRF versions",
    description="Retrieve CRF versions with optional filtering by trial and status.",
)
async def list_crf_versions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    crf_status: Optional[CRFStatus] = Query(None, description="Filter by CRF status"),
) -> CRFVersionListResponse:
    svc = get_crf_management_service()
    items = svc.list_crf_versions(trial_id=trial_id, crf_status=crf_status)
    return CRFVersionListResponse(items=items, total=len(items))


@router.get(
    "/crf-versions/{version_id}",
    response_model=CRFVersion,
    summary="Get a CRF version",
)
async def get_crf_version(version_id: str) -> CRFVersion:
    svc = get_crf_management_service()
    record = svc.get_crf_version(version_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"CRF version '{version_id}' not found")
    return record


@router.post(
    "/crf-versions",
    response_model=CRFVersion,
    status_code=201,
    summary="Create a CRF version",
)
async def create_crf_version(payload: CRFVersionCreate) -> CRFVersion:
    svc = get_crf_management_service()
    return svc.create_crf_version(payload)


@router.put(
    "/crf-versions/{version_id}",
    response_model=CRFVersion,
    summary="Update a CRF version",
)
async def update_crf_version(
    version_id: str, payload: CRFVersionUpdate
) -> CRFVersion:
    svc = get_crf_management_service()
    updated = svc.update_crf_version(version_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"CRF version '{version_id}' not found")
    return updated


@router.delete(
    "/crf-versions/{version_id}",
    status_code=204,
    summary="Delete a CRF version",
)
async def delete_crf_version(version_id: str) -> None:
    svc = get_crf_management_service()
    deleted = svc.delete_crf_version(version_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"CRF version '{version_id}' not found")


# ---------------------------------------------------------------------------
# CRF Fields
# ---------------------------------------------------------------------------


@router.get(
    "/crf-fields",
    response_model=CRFFieldListResponse,
    summary="List CRF fields",
    description="Retrieve CRF fields with optional filtering by trial, version, and field type.",
)
async def list_crf_fields(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    crf_version_id: Optional[str] = Query(None, description="Filter by CRF version ID"),
    field_type: Optional[FieldType] = Query(None, description="Filter by field type"),
) -> CRFFieldListResponse:
    svc = get_crf_management_service()
    items = svc.list_crf_fields(
        trial_id=trial_id, crf_version_id=crf_version_id, field_type=field_type
    )
    return CRFFieldListResponse(items=items, total=len(items))


@router.get(
    "/crf-fields/{field_id}",
    response_model=CRFField,
    summary="Get a CRF field",
)
async def get_crf_field(field_id: str) -> CRFField:
    svc = get_crf_management_service()
    record = svc.get_crf_field(field_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"CRF field '{field_id}' not found")
    return record


@router.post(
    "/crf-fields",
    response_model=CRFField,
    status_code=201,
    summary="Create a CRF field",
)
async def create_crf_field(payload: CRFFieldCreate) -> CRFField:
    svc = get_crf_management_service()
    return svc.create_crf_field(payload)


@router.put(
    "/crf-fields/{field_id}",
    response_model=CRFField,
    summary="Update a CRF field",
)
async def update_crf_field(
    field_id: str, payload: CRFFieldUpdate
) -> CRFField:
    svc = get_crf_management_service()
    updated = svc.update_crf_field(field_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"CRF field '{field_id}' not found")
    return updated


@router.delete(
    "/crf-fields/{field_id}",
    status_code=204,
    summary="Delete a CRF field",
)
async def delete_crf_field(field_id: str) -> None:
    svc = get_crf_management_service()
    deleted = svc.delete_crf_field(field_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"CRF field '{field_id}' not found")


# ---------------------------------------------------------------------------
# Edit Check Rules
# ---------------------------------------------------------------------------


@router.get(
    "/edit-check-rules",
    response_model=EditCheckRuleListResponse,
    summary="List edit check rules",
    description="Retrieve edit check rules with optional filtering by trial, version, severity, and active status.",
)
async def list_edit_check_rules(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    crf_version_id: Optional[str] = Query(None, description="Filter by CRF version ID"),
    edit_check_severity: Optional[EditCheckSeverity] = Query(
        None, description="Filter by severity"
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> EditCheckRuleListResponse:
    svc = get_crf_management_service()
    items = svc.list_edit_check_rules(
        trial_id=trial_id,
        crf_version_id=crf_version_id,
        edit_check_severity=edit_check_severity,
        is_active=is_active,
    )
    return EditCheckRuleListResponse(items=items, total=len(items))


@router.get(
    "/edit-check-rules/{rule_id}",
    response_model=EditCheckRule,
    summary="Get an edit check rule",
)
async def get_edit_check_rule(rule_id: str) -> EditCheckRule:
    svc = get_crf_management_service()
    record = svc.get_edit_check_rule(rule_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Edit check rule '{rule_id}' not found")
    return record


@router.post(
    "/edit-check-rules",
    response_model=EditCheckRule,
    status_code=201,
    summary="Create an edit check rule",
)
async def create_edit_check_rule(payload: EditCheckRuleCreate) -> EditCheckRule:
    svc = get_crf_management_service()
    return svc.create_edit_check_rule(payload)


@router.put(
    "/edit-check-rules/{rule_id}",
    response_model=EditCheckRule,
    summary="Update an edit check rule",
)
async def update_edit_check_rule(
    rule_id: str, payload: EditCheckRuleUpdate
) -> EditCheckRule:
    svc = get_crf_management_service()
    updated = svc.update_edit_check_rule(rule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Edit check rule '{rule_id}' not found")
    return updated


@router.delete(
    "/edit-check-rules/{rule_id}",
    status_code=204,
    summary="Delete an edit check rule",
)
async def delete_edit_check_rule(rule_id: str) -> None:
    svc = get_crf_management_service()
    deleted = svc.delete_edit_check_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Edit check rule '{rule_id}' not found")


# ---------------------------------------------------------------------------
# CRF Deployments
# ---------------------------------------------------------------------------


@router.get(
    "/deployments",
    response_model=CRFDeploymentListResponse,
    summary="List CRF deployments",
    description="Retrieve CRF deployments with optional filtering by trial, status, and version.",
)
async def list_deployments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    deployment_status: Optional[DeploymentStatus] = Query(
        None, description="Filter by deployment status"
    ),
    crf_version_id: Optional[str] = Query(None, description="Filter by CRF version ID"),
) -> CRFDeploymentListResponse:
    svc = get_crf_management_service()
    items = svc.list_deployments(
        trial_id=trial_id,
        deployment_status=deployment_status,
        crf_version_id=crf_version_id,
    )
    return CRFDeploymentListResponse(items=items, total=len(items))


@router.get(
    "/deployments/{deployment_id}",
    response_model=CRFDeployment,
    summary="Get a CRF deployment",
)
async def get_deployment(deployment_id: str) -> CRFDeployment:
    svc = get_crf_management_service()
    record = svc.get_deployment(deployment_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"CRF deployment '{deployment_id}' not found"
        )
    return record


@router.post(
    "/deployments",
    response_model=CRFDeployment,
    status_code=201,
    summary="Create a CRF deployment",
)
async def create_deployment(payload: CRFDeploymentCreate) -> CRFDeployment:
    svc = get_crf_management_service()
    return svc.create_deployment(payload)


@router.put(
    "/deployments/{deployment_id}",
    response_model=CRFDeployment,
    summary="Update a CRF deployment",
)
async def update_deployment(
    deployment_id: str, payload: CRFDeploymentUpdate
) -> CRFDeployment:
    svc = get_crf_management_service()
    updated = svc.update_deployment(deployment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"CRF deployment '{deployment_id}' not found"
        )
    return updated


@router.delete(
    "/deployments/{deployment_id}",
    status_code=204,
    summary="Delete a CRF deployment",
)
async def delete_deployment(deployment_id: str) -> None:
    svc = get_crf_management_service()
    deleted = svc.delete_deployment(deployment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"CRF deployment '{deployment_id}' not found"
        )


# ---------------------------------------------------------------------------
# CRF Annotations
# ---------------------------------------------------------------------------


@router.get(
    "/annotations",
    response_model=CRFAnnotationListResponse,
    summary="List CRF annotations",
    description="Retrieve CRF annotations with optional filtering by trial, version, and type.",
)
async def list_annotations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    crf_version_id: Optional[str] = Query(None, description="Filter by CRF version ID"),
    annotation_type: Optional[AnnotationType] = Query(
        None, description="Filter by annotation type"
    ),
) -> CRFAnnotationListResponse:
    svc = get_crf_management_service()
    items = svc.list_annotations(
        trial_id=trial_id,
        crf_version_id=crf_version_id,
        annotation_type=annotation_type,
    )
    return CRFAnnotationListResponse(items=items, total=len(items))


@router.get(
    "/annotations/{annotation_id}",
    response_model=CRFAnnotation,
    summary="Get a CRF annotation",
)
async def get_annotation(annotation_id: str) -> CRFAnnotation:
    svc = get_crf_management_service()
    record = svc.get_annotation(annotation_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"CRF annotation '{annotation_id}' not found"
        )
    return record


@router.post(
    "/annotations",
    response_model=CRFAnnotation,
    status_code=201,
    summary="Create a CRF annotation",
)
async def create_annotation(payload: CRFAnnotationCreate) -> CRFAnnotation:
    svc = get_crf_management_service()
    return svc.create_annotation(payload)


@router.put(
    "/annotations/{annotation_id}",
    response_model=CRFAnnotation,
    summary="Update a CRF annotation",
)
async def update_annotation(
    annotation_id: str, payload: CRFAnnotationUpdate
) -> CRFAnnotation:
    svc = get_crf_management_service()
    updated = svc.update_annotation(annotation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"CRF annotation '{annotation_id}' not found"
        )
    return updated


@router.delete(
    "/annotations/{annotation_id}",
    status_code=204,
    summary="Delete a CRF annotation",
)
async def delete_annotation(annotation_id: str) -> None:
    svc = get_crf_management_service()
    deleted = svc.delete_annotation(annotation_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"CRF annotation '{annotation_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CRFManagementMetrics,
    summary="Get CRF management metrics",
    description="Aggregated metrics across all CRF management operations.",
)
async def get_metrics() -> CRFManagementMetrics:
    svc = get_crf_management_service()
    return svc.get_metrics()
