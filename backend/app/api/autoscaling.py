"""Auto-Scaling API endpoints (DEVOPS-3).

Provides management of auto-scaling policies, evaluation of scaling decisions,
scaling event history, and KEDA ScaledObject spec generation for the clinical
trial platform.

Endpoints:
    GET    /infrastructure/scaling/policies              - List all scaling policies
    GET    /infrastructure/scaling/policies/{policy_id}  - Get policy detail
    POST   /infrastructure/scaling/policies              - Create scaling policy
    PUT    /infrastructure/scaling/policies/{policy_id}  - Update policy
    DELETE /infrastructure/scaling/policies/{policy_id}  - Delete policy
    GET    /infrastructure/scaling/targets               - Scaling targets with current replicas
    POST   /infrastructure/scaling/evaluate              - Evaluate scaling decision
    GET    /infrastructure/scaling/history               - Scaling event history
    GET    /infrastructure/scaling/keda-spec/{target}    - Generate KEDA ScaledObject YAML
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.autoscaling import (
    KEDAScaledObjectSpec,
    PolicyStatus,
    ScalingEvaluationRequest,
    ScalingEvaluationResponse,
    ScalingHistoryResponse,
    ScalingPoliciesResponse,
    ScalingPolicy,
    ScalingPolicyCreate,
    ScalingPolicyUpdate,
    ScalingTargetName,
    ScalingTargetsResponse,
)
from app.services.autoscaling_service import get_autoscaling_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/infrastructure/scaling",
    tags=["Auto-Scaling"],
)


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


@router.get(
    "/policies",
    response_model=ScalingPoliciesResponse,
    summary="List all scaling policies",
)
async def list_policies(
    target: ScalingTargetName | None = Query(None, description="Filter by target"),
    status: PolicyStatus | None = Query(None, description="Filter by status"),
) -> ScalingPoliciesResponse:
    """List all scaling policies with optional filtering."""
    svc = get_autoscaling_service()
    return svc.list_policies(target=target, status=status)


@router.get(
    "/policies/{policy_id}",
    response_model=ScalingPolicy,
    summary="Get scaling policy detail",
)
async def get_policy(policy_id: str) -> ScalingPolicy:
    """Get a single scaling policy by ID."""
    svc = get_autoscaling_service()
    try:
        return svc.get_policy(policy_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")


@router.post(
    "/policies",
    response_model=ScalingPolicy,
    status_code=201,
    summary="Create scaling policy",
)
async def create_policy(data: ScalingPolicyCreate) -> ScalingPolicy:
    """Create a new scaling policy."""
    svc = get_autoscaling_service()
    return svc.create_policy(data)


@router.put(
    "/policies/{policy_id}",
    response_model=ScalingPolicy,
    summary="Update scaling policy",
)
async def update_policy(policy_id: str, data: ScalingPolicyUpdate) -> ScalingPolicy:
    """Update an existing scaling policy."""
    svc = get_autoscaling_service()
    try:
        return svc.update_policy(policy_id, data)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")


@router.delete(
    "/policies/{policy_id}",
    response_model=ScalingPolicy,
    summary="Delete scaling policy",
)
async def delete_policy(policy_id: str) -> ScalingPolicy:
    """Delete a scaling policy."""
    svc = get_autoscaling_service()
    try:
        return svc.delete_policy(policy_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")


# ---------------------------------------------------------------------------
# Scaling Targets
# ---------------------------------------------------------------------------


@router.get(
    "/targets",
    response_model=ScalingTargetsResponse,
    summary="Get scaling targets with current replicas",
)
async def get_targets() -> ScalingTargetsResponse:
    """Get all scaling targets with their current replica counts and status."""
    svc = get_autoscaling_service()
    return svc.get_targets()


# ---------------------------------------------------------------------------
# Scaling Evaluation
# ---------------------------------------------------------------------------


@router.post(
    "/evaluate",
    response_model=ScalingEvaluationResponse,
    summary="Evaluate scaling decision for current metrics",
)
async def evaluate_scaling(request: ScalingEvaluationRequest) -> ScalingEvaluationResponse:
    """Evaluate scaling decisions based on provided metrics.

    Pass current metric values and receive scaling decisions for each target.
    """
    svc = get_autoscaling_service()
    return svc.evaluate(
        metrics=request.metrics,
        target_filter=request.target,
    )


# ---------------------------------------------------------------------------
# Scaling History
# ---------------------------------------------------------------------------


@router.get(
    "/history",
    response_model=ScalingHistoryResponse,
    summary="Get scaling event history",
)
async def get_history(
    target: ScalingTargetName | None = Query(None, description="Filter by target"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> ScalingHistoryResponse:
    """Get scaling event history, optionally filtered by target."""
    svc = get_autoscaling_service()
    return svc.get_history(target=target, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# KEDA Spec
# ---------------------------------------------------------------------------


@router.get(
    "/keda-spec/{target}",
    response_model=KEDAScaledObjectSpec,
    summary="Generate KEDA ScaledObject YAML",
)
async def get_keda_spec(target: ScalingTargetName) -> KEDAScaledObjectSpec:
    """Generate a KEDA ScaledObject YAML specification for a target.

    This YAML can be applied to a Kubernetes cluster with KEDA installed
    to enable event-driven auto-scaling.
    """
    svc = get_autoscaling_service()
    try:
        return svc.generate_keda_spec(target)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Target '{target}' not found")
