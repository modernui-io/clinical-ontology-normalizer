"""eCTD Submission Management API endpoints (eCTD-MGMT).

Provides comprehensive eCTD submission operations: sequence planning & tracking,
document assembly & lifecycle, eCTD validation, health authority response
management, submission plans, and operational metrics.

Endpoints:
    GET    /ectd-submission/sequences                    - List sequences
    GET    /ectd-submission/sequences/{sequence_id}      - Get single sequence
    POST   /ectd-submission/sequences                    - Create sequence
    PUT    /ectd-submission/sequences/{sequence_id}      - Update sequence
    DELETE /ectd-submission/sequences/{sequence_id}      - Delete sequence
    GET    /ectd-submission/documents                    - List documents
    GET    /ectd-submission/documents/{document_id}      - Get single document
    POST   /ectd-submission/documents                    - Create document
    PUT    /ectd-submission/documents/{document_id}      - Update document
    DELETE /ectd-submission/documents/{document_id}      - Delete document
    GET    /ectd-submission/validations                  - List validations
    GET    /ectd-submission/validations/{validation_id}  - Get single validation
    POST   /ectd-submission/validations                  - Create validation
    DELETE /ectd-submission/validations/{validation_id}  - Delete validation
    GET    /ectd-submission/ha-responses                 - List HA responses
    GET    /ectd-submission/ha-responses/{response_id}   - Get single HA response
    POST   /ectd-submission/ha-responses                 - Create HA response
    PUT    /ectd-submission/ha-responses/{response_id}   - Update HA response
    DELETE /ectd-submission/ha-responses/{response_id}   - Delete HA response
    GET    /ectd-submission/plans                        - List submission plans
    GET    /ectd-submission/plans/{plan_id}              - Get single plan
    POST   /ectd-submission/plans                        - Create plan
    PUT    /ectd-submission/plans/{plan_id}              - Update plan
    DELETE /ectd-submission/plans/{plan_id}              - Delete plan
    GET    /ectd-submission/metrics                      - eCTD operational metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response

from app.schemas.ectd_submission import (
    CTDModule,
    ECTDDocument,
    ECTDDocumentCreate,
    ECTDDocumentListResponse,
    ECTDDocumentUpdate,
    ECTDMetrics,
    ECTDSequence,
    ECTDSequenceCreate,
    ECTDSequenceListResponse,
    ECTDSequenceUpdate,
    ECTDValidation,
    ECTDValidationCreate,
    ECTDValidationListResponse,
    HAResponse,
    HAResponseCreate,
    HAResponseListResponse,
    HAResponseType,
    HAResponseUpdate,
    RegulatoryRegion,
    SequenceStatus,
    SubmissionPlan,
    SubmissionPlanCreate,
    SubmissionPlanListResponse,
    SubmissionPlanUpdate,
    SubmissionType,
)
from app.services.ectd_submission_service import get_ectd_submission_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ectd-submission",
    tags=["eCTD Submission"],
)

# ============================================================================
# ECTDSequence endpoints
# ============================================================================


@router.get("/sequences", response_model=ECTDSequenceListResponse)
def list_sequences(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    region: Optional[RegulatoryRegion] = Query(None, description="Filter by regulatory region"),
    status: Optional[SequenceStatus] = Query(None, description="Filter by status"),
    submission_type: Optional[SubmissionType] = Query(None, description="Filter by submission type"),
) -> ECTDSequenceListResponse:
    """List all eCTD sequences with optional filters."""
    svc = get_ectd_submission_service()
    items = svc.list_sequences(
        trial_id=trial_id,
        region=region,
        status=status,
        submission_type=submission_type,
    )
    return ECTDSequenceListResponse(items=items, total=len(items))


@router.get("/sequences/{sequence_id}", response_model=ECTDSequence)
def get_sequence(sequence_id: str) -> ECTDSequence:
    """Get a single eCTD sequence by ID."""
    svc = get_ectd_submission_service()
    seq = svc.get_sequence(sequence_id)
    if not seq:
        raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")
    return seq


@router.post("/sequences", response_model=ECTDSequence, status_code=201)
def create_sequence(payload: ECTDSequenceCreate) -> ECTDSequence:
    """Create a new eCTD sequence."""
    svc = get_ectd_submission_service()
    return svc.create_sequence(payload)


@router.put("/sequences/{sequence_id}", response_model=ECTDSequence)
def update_sequence(sequence_id: str, payload: ECTDSequenceUpdate) -> ECTDSequence:
    """Update an existing eCTD sequence."""
    svc = get_ectd_submission_service()
    updated = svc.update_sequence(sequence_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")
    return updated


@router.delete("/sequences/{sequence_id}", status_code=204)
def delete_sequence(sequence_id: str) -> Response:
    """Delete an eCTD sequence."""
    svc = get_ectd_submission_service()
    if not svc.delete_sequence(sequence_id):
        raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")
    return Response(status_code=204)


# ============================================================================
# ECTDDocument endpoints
# ============================================================================


@router.get("/documents", response_model=ECTDDocumentListResponse)
def list_documents(
    sequence_id: Optional[str] = Query(None, description="Filter by sequence ID"),
    module: Optional[CTDModule] = Query(None, description="Filter by CTD module"),
    approved: Optional[bool] = Query(None, description="Filter by approval status"),
) -> ECTDDocumentListResponse:
    """List all eCTD documents with optional filters."""
    svc = get_ectd_submission_service()
    items = svc.list_documents(sequence_id=sequence_id, module=module, approved=approved)
    return ECTDDocumentListResponse(items=items, total=len(items))


@router.get("/documents/{document_id}", response_model=ECTDDocument)
def get_document(document_id: str) -> ECTDDocument:
    """Get a single eCTD document by ID."""
    svc = get_ectd_submission_service()
    doc = svc.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.post("/documents", response_model=ECTDDocument, status_code=201)
def create_document(payload: ECTDDocumentCreate) -> ECTDDocument:
    """Create a new eCTD document."""
    svc = get_ectd_submission_service()
    return svc.create_document(payload)


@router.put("/documents/{document_id}", response_model=ECTDDocument)
def update_document(document_id: str, payload: ECTDDocumentUpdate) -> ECTDDocument:
    """Update an existing eCTD document."""
    svc = get_ectd_submission_service()
    updated = svc.update_document(document_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return updated


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str) -> Response:
    """Delete an eCTD document."""
    svc = get_ectd_submission_service()
    if not svc.delete_document(document_id):
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return Response(status_code=204)


# ============================================================================
# ECTDValidation endpoints
# ============================================================================


@router.get("/validations", response_model=ECTDValidationListResponse)
def list_validations(
    sequence_id: Optional[str] = Query(None, description="Filter by sequence ID"),
    passed: Optional[bool] = Query(None, description="Filter by passed status"),
) -> ECTDValidationListResponse:
    """List all eCTD validations with optional filters."""
    svc = get_ectd_submission_service()
    items = svc.list_validations(sequence_id=sequence_id, passed=passed)
    return ECTDValidationListResponse(items=items, total=len(items))


@router.get("/validations/{validation_id}", response_model=ECTDValidation)
def get_validation(validation_id: str) -> ECTDValidation:
    """Get a single eCTD validation by ID."""
    svc = get_ectd_submission_service()
    val = svc.get_validation(validation_id)
    if not val:
        raise HTTPException(status_code=404, detail=f"Validation {validation_id} not found")
    return val


@router.post("/validations", response_model=ECTDValidation, status_code=201)
def create_validation(payload: ECTDValidationCreate) -> ECTDValidation:
    """Create a new eCTD validation record."""
    svc = get_ectd_submission_service()
    return svc.create_validation(payload)


@router.delete("/validations/{validation_id}", status_code=204)
def delete_validation(validation_id: str) -> Response:
    """Delete an eCTD validation record."""
    svc = get_ectd_submission_service()
    if not svc.delete_validation(validation_id):
        raise HTTPException(status_code=404, detail=f"Validation {validation_id} not found")
    return Response(status_code=204)


# ============================================================================
# HAResponse endpoints
# ============================================================================


@router.get("/ha-responses", response_model=HAResponseListResponse)
def list_ha_responses(
    sequence_id: Optional[str] = Query(None, description="Filter by sequence ID"),
    response_type: Optional[HAResponseType] = Query(None, description="Filter by response type"),
    status: Optional[str] = Query(None, description="Filter by status (open/closed)"),
) -> HAResponseListResponse:
    """List all health authority responses with optional filters."""
    svc = get_ectd_submission_service()
    items = svc.list_ha_responses(
        sequence_id=sequence_id,
        response_type=response_type,
        status=status,
    )
    return HAResponseListResponse(items=items, total=len(items))


@router.get("/ha-responses/{response_id}", response_model=HAResponse)
def get_ha_response(response_id: str) -> HAResponse:
    """Get a single health authority response by ID."""
    svc = get_ectd_submission_service()
    har = svc.get_ha_response(response_id)
    if not har:
        raise HTTPException(status_code=404, detail=f"HA response {response_id} not found")
    return har


@router.post("/ha-responses", response_model=HAResponse, status_code=201)
def create_ha_response(payload: HAResponseCreate) -> HAResponse:
    """Create a new health authority response."""
    svc = get_ectd_submission_service()
    return svc.create_ha_response(payload)


@router.put("/ha-responses/{response_id}", response_model=HAResponse)
def update_ha_response(response_id: str, payload: HAResponseUpdate) -> HAResponse:
    """Update an existing health authority response."""
    svc = get_ectd_submission_service()
    updated = svc.update_ha_response(response_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail=f"HA response {response_id} not found")
    return updated


@router.delete("/ha-responses/{response_id}", status_code=204)
def delete_ha_response(response_id: str) -> Response:
    """Delete a health authority response."""
    svc = get_ectd_submission_service()
    if not svc.delete_ha_response(response_id):
        raise HTTPException(status_code=404, detail=f"HA response {response_id} not found")
    return Response(status_code=204)


# ============================================================================
# SubmissionPlan endpoints
# ============================================================================


@router.get("/plans", response_model=SubmissionPlanListResponse)
def list_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[str] = Query(None, description="Filter by plan status"),
) -> SubmissionPlanListResponse:
    """List all submission plans with optional filters."""
    svc = get_ectd_submission_service()
    items = svc.list_plans(trial_id=trial_id, status=status)
    return SubmissionPlanListResponse(items=items, total=len(items))


@router.get("/plans/{plan_id}", response_model=SubmissionPlan)
def get_plan(plan_id: str) -> SubmissionPlan:
    """Get a single submission plan by ID."""
    svc = get_ectd_submission_service()
    plan = svc.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


@router.post("/plans", response_model=SubmissionPlan, status_code=201)
def create_plan(payload: SubmissionPlanCreate) -> SubmissionPlan:
    """Create a new submission plan."""
    svc = get_ectd_submission_service()
    return svc.create_plan(payload)


@router.put("/plans/{plan_id}", response_model=SubmissionPlan)
def update_plan(plan_id: str, payload: SubmissionPlanUpdate) -> SubmissionPlan:
    """Update an existing submission plan."""
    svc = get_ectd_submission_service()
    updated = svc.update_plan(plan_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return updated


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: str) -> Response:
    """Delete a submission plan."""
    svc = get_ectd_submission_service()
    if not svc.delete_plan(plan_id):
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return Response(status_code=204)


# ============================================================================
# Metrics
# ============================================================================


@router.get("/metrics", response_model=ECTDMetrics)
def get_metrics() -> ECTDMetrics:
    """Get eCTD submission operational metrics."""
    svc = get_ectd_submission_service()
    return svc.get_metrics()
