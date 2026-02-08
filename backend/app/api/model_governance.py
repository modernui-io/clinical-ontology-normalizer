"""Model Governance API endpoints (VP-DS-8).

Provides endpoints for ML model governance and lifecycle management:
- Register and manage governed models
- Submit for validation and track validation records
- Request and manage approvals with tier-based requirements
- Deploy approved models
- Record, acknowledge, and resolve monitoring alerts
- Track overdue reviews
- View governance metrics and model history
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.model_governance import (
    AlertListResponse,
    ApprovalRequestListResponse,
    ApproveModelRequest,
    GovernanceStatus,
    GovernedModel,
    GovernedModelCreate,
    GovernedModelListResponse,
    GovernedModelUpdate,
    ModelApprovalRequest,
    ModelGovernanceMetrics,
    ModelHistoryResponse,
    ModelMonitoringAlert,
    ModelRiskTier,
    ModelValidationRecord,
    RecordAlertRequest,
    SubmitValidationRequest,
    ValidationRecordListResponse,
)
from app.services.model_governance_service import get_model_governance_service

router = APIRouter(prefix="/model-governance", tags=["Model Governance"])


# ============================================================================
# Model CRUD
# ============================================================================


@router.get(
    "/models",
    response_model=GovernedModelListResponse,
    summary="List governed models",
    description="List all models under governance with optional filtering by risk tier and status.",
)
async def list_models(
    risk_tier: ModelRiskTier | None = Query(None, description="Filter by risk tier"),
    status: GovernanceStatus | None = Query(None, description="Filter by governance status"),
    limit: int = Query(100, ge=1, le=1000, description="Max models to return"),
) -> GovernedModelListResponse:
    """List governed models."""
    service = get_model_governance_service()
    models = service.list_models(risk_tier=risk_tier, status=status, limit=limit)
    return GovernedModelListResponse(total=len(models), models=models)


@router.get(
    "/models/{model_id}",
    response_model=GovernedModel,
    summary="Get model details",
    description="Get detailed information about a specific governed model.",
)
async def get_model(model_id: str) -> GovernedModel:
    """Get a specific governed model."""
    service = get_model_governance_service()
    model = service.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return model


@router.post(
    "/models",
    response_model=GovernedModel,
    summary="Register governed model",
    description="Register a new model under governance oversight.",
)
async def register_model(request: GovernedModelCreate) -> GovernedModel:
    """Register a new governed model."""
    service = get_model_governance_service()
    return service.register_model(
        name=request.name,
        version=request.version,
        model_type=request.model_type,
        risk_tier=request.risk_tier,
        owner=request.owner,
        description=request.description,
        team=request.team,
        training_data_hash=request.training_data_hash,
        performance_metrics=request.performance_metrics,
        fairness_metrics=request.fairness_metrics,
        review_frequency_days=request.review_frequency_days,
    )


@router.patch(
    "/models/{model_id}",
    response_model=GovernedModel,
    summary="Update governed model",
    description="Update mutable fields of a governed model.",
)
async def update_model(model_id: str, request: GovernedModelUpdate) -> GovernedModel:
    """Update a governed model."""
    service = get_model_governance_service()
    model = service.update_model(
        model_id,
        description=request.description,
        performance_metrics=request.performance_metrics,
        fairness_metrics=request.fairness_metrics,
        monitoring_config=request.monitoring_config,
        review_frequency_days=request.review_frequency_days,
    )
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return model


@router.delete(
    "/models/{model_id}",
    summary="Delete governed model",
    description="Delete a governed model and all associated records.",
)
async def delete_model(model_id: str) -> dict[str, str]:
    """Delete a governed model."""
    service = get_model_governance_service()
    if not service.delete_model(model_id):
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return {"status": "deleted", "model_id": model_id}


# ============================================================================
# Lifecycle transitions
# ============================================================================


@router.post(
    "/models/{model_id}/validate",
    response_model=ModelValidationRecord,
    summary="Submit for validation",
    description="Submit a model for validation (technical, clinical, or regulatory).",
)
async def submit_for_validation(
    model_id: str, request: SubmitValidationRequest
) -> ModelValidationRecord:
    """Submit a model for validation."""
    service = get_model_governance_service()
    record = service.submit_for_validation(
        model_id=model_id,
        validation_type=request.validation_type,
        validator=request.validator,
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return record


@router.post(
    "/models/{model_id}/request-approval",
    response_model=ModelApprovalRequest,
    summary="Request approval",
    description="Request approval for a model. Tier-based requirements apply.",
)
async def request_approval(
    model_id: str,
    requested_by: str = Query("", description="Person requesting approval"),
) -> ModelApprovalRequest:
    """Request approval for a model."""
    service = get_model_governance_service()
    request_obj = service.request_approval(model_id=model_id, requested_by=requested_by)
    if request_obj is None:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_id}' not found or not in a valid status for approval request",
        )
    return request_obj


@router.post(
    "/models/{model_id}/approve",
    response_model=ModelApprovalRequest,
    summary="Approve model",
    description="Record an approval for a model. Fully approved when all required roles are met.",
)
async def approve_model(
    model_id: str, request: ApproveModelRequest
) -> ModelApprovalRequest:
    """Approve a model."""
    service = get_model_governance_service()
    result = service.approve_model(
        model_id=model_id,
        approver=request.approver,
        role=request.role,
        comments=request.comments,
    )
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_id}' not found or no pending approval request",
        )
    return result


@router.post(
    "/models/{model_id}/reject",
    response_model=ModelApprovalRequest,
    summary="Reject approval",
    description="Reject a pending approval request.",
)
async def reject_approval(
    model_id: str,
    rejector: str = Query(..., description="Person rejecting"),
    reason: str = Query("", description="Reason for rejection"),
) -> ModelApprovalRequest:
    """Reject a pending approval."""
    service = get_model_governance_service()
    result = service.reject_approval(model_id=model_id, rejector=rejector, reason=reason)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_id}' not found or no pending approval request",
        )
    return result


@router.post(
    "/models/{model_id}/deploy",
    response_model=GovernedModel,
    summary="Deploy model",
    description="Deploy an approved model to production.",
)
async def deploy_model(model_id: str) -> GovernedModel:
    """Deploy an approved model."""
    service = get_model_governance_service()
    model = service.deploy_model(model_id)
    if model is None:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_id}' not found or not in APPROVED status",
        )
    return model


@router.post(
    "/models/{model_id}/deprecate",
    response_model=GovernedModel,
    summary="Deprecate model",
    description="Mark a model as deprecated.",
)
async def deprecate_model(model_id: str) -> GovernedModel:
    """Deprecate a model."""
    service = get_model_governance_service()
    model = service.deprecate_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return model


@router.post(
    "/models/{model_id}/retire",
    response_model=GovernedModel,
    summary="Retire model",
    description="Retire a model (final lifecycle stage).",
)
async def retire_model(model_id: str) -> GovernedModel:
    """Retire a model."""
    service = get_model_governance_service()
    model = service.retire_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return model


# ============================================================================
# Monitoring alerts
# ============================================================================


@router.post(
    "/models/{model_id}/alerts",
    response_model=ModelMonitoringAlert,
    summary="Record monitoring alert",
    description="Record a monitoring alert for a model.",
)
async def record_alert(
    model_id: str, request: RecordAlertRequest
) -> ModelMonitoringAlert:
    """Record a monitoring alert."""
    service = get_model_governance_service()
    alert = service.record_monitoring_alert(
        model_id=model_id,
        alert_type=request.alert_type,
        severity=request.severity,
        message=request.message,
    )
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return alert


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List all alerts",
    description="List all monitoring alerts across all models.",
)
async def list_alerts(
    model_id: str | None = Query(None, description="Filter by model ID"),
    unresolved_only: bool = Query(False, description="Only show unresolved alerts"),
) -> AlertListResponse:
    """List monitoring alerts."""
    service = get_model_governance_service()
    alerts = service.get_alerts(model_id=model_id, unresolved_only=unresolved_only)
    return AlertListResponse(total=len(alerts), alerts=alerts)


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=ModelMonitoringAlert,
    summary="Acknowledge alert",
    description="Mark a monitoring alert as acknowledged.",
)
async def acknowledge_alert(alert_id: str) -> ModelMonitoringAlert:
    """Acknowledge an alert."""
    service = get_model_governance_service()
    alert = service.acknowledge_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return alert


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=ModelMonitoringAlert,
    summary="Resolve alert",
    description="Mark a monitoring alert as resolved.",
)
async def resolve_alert(alert_id: str) -> ModelMonitoringAlert:
    """Resolve an alert."""
    service = get_model_governance_service()
    alert = service.resolve_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return alert


# ============================================================================
# Validation records and approvals
# ============================================================================


@router.get(
    "/models/{model_id}/validations",
    response_model=ValidationRecordListResponse,
    summary="List validations",
    description="List all validation records for a model.",
)
async def list_validations(model_id: str) -> ValidationRecordListResponse:
    """List validation records for a model."""
    service = get_model_governance_service()
    if service.get_model(model_id) is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    records = service.get_validations(model_id)
    return ValidationRecordListResponse(total=len(records), records=records)


@router.get(
    "/models/{model_id}/approvals",
    response_model=ApprovalRequestListResponse,
    summary="List approval requests",
    description="List all approval requests for a model.",
)
async def list_approvals(model_id: str) -> ApprovalRequestListResponse:
    """List approval requests for a model."""
    service = get_model_governance_service()
    if service.get_model(model_id) is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    requests = service.get_approval_requests(model_id)
    return ApprovalRequestListResponse(total=len(requests), requests=requests)


# ============================================================================
# Reports and metrics
# ============================================================================


@router.get(
    "/overdue-reviews",
    response_model=GovernedModelListResponse,
    summary="Get overdue reviews",
    description="List models with overdue governance reviews.",
)
async def get_overdue_reviews() -> GovernedModelListResponse:
    """Get models with overdue reviews."""
    service = get_model_governance_service()
    models = service.get_overdue_reviews()
    return GovernedModelListResponse(total=len(models), models=models)


@router.get(
    "/metrics",
    response_model=ModelGovernanceMetrics,
    summary="Get governance metrics",
    description="Get aggregated governance metrics across all models.",
)
async def get_metrics() -> ModelGovernanceMetrics:
    """Get governance metrics."""
    service = get_model_governance_service()
    return service.get_metrics()


@router.get(
    "/models/{model_id}/history",
    response_model=ModelHistoryResponse,
    summary="Get model history",
    description="Get complete history for a model including validations, alerts, and approvals.",
)
async def get_model_history(model_id: str) -> ModelHistoryResponse:
    """Get model history."""
    service = get_model_governance_service()
    history = service.get_model_history(model_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return ModelHistoryResponse(**history)
