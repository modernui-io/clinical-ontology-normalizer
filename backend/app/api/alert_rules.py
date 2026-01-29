"""Alert Rules API endpoints.

Provides endpoints for managing clinical alert rules based on risk thresholds,
lab values, and clinical conditions.
"""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.errors import (
    ValidationError,
    NotFoundError,
    ErrorCode,
    ErrorDetail,
)
from app.services.alert_rules_service import (
    get_alert_rules_service,
    AlertCategory,
    AlertSeverity,
    RuleStatus,
    RuleOperator,
)

router = APIRouter(prefix="/alert-rules", tags=["Alert Rules"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ConditionRequest(BaseModel):
    """A rule condition."""

    field: str = Field(..., description="Field to evaluate")
    operator: str = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")
    label: str = Field(default="", description="Human-readable label")

    model_config = {
        "json_schema_extra": {
            "example": {
                "field": "readmission_risk_score",
                "operator": "gte",
                "value": 0.7,
                "label": "Readmission risk >= 70%",
            }
        }
    }


class ActionRequest(BaseModel):
    """An alert action."""

    type: str = Field(..., description="Action type (notify, escalate, create_task)")
    config: dict[str, Any] = Field(default_factory=dict, description="Action configuration")

    model_config = {
        "json_schema_extra": {
            "example": {
                "type": "notify",
                "config": {"channel": "care_team", "urgent": True},
            }
        }
    }


class CreateRuleRequest(BaseModel):
    """Request to create an alert rule."""

    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    description: str = Field(default="", description="Rule description")
    category: str = Field(..., description="Alert category")
    severity: str = Field(..., description="Alert severity")
    conditions: list[ConditionRequest] = Field(..., min_length=1, description="Rule conditions")
    actions: list[ActionRequest] = Field(default_factory=list, description="Actions when triggered")
    patient_filter: dict[str, Any] | None = Field(None, description="Optional patient filter")
    cooldown_minutes: int = Field(60, ge=0, description="Cooldown between alerts")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "High Fall Risk",
                "description": "Alert when patient has high fall risk",
                "category": "risk_score",
                "severity": "high",
                "conditions": [
                    {
                        "field": "fall_risk_score",
                        "operator": "gte",
                        "value": 0.8,
                        "label": "Fall risk >= 80%",
                    }
                ],
                "actions": [
                    {"type": "notify", "config": {"channel": "nursing"}},
                ],
                "cooldown_minutes": 120,
            }
        }
    }


class UpdateRuleRequest(BaseModel):
    """Request to update an alert rule."""

    name: str | None = Field(None, description="Rule name")
    description: str | None = Field(None, description="Rule description")
    severity: str | None = Field(None, description="Alert severity")
    status: str | None = Field(None, description="Rule status")
    conditions: list[ConditionRequest] | None = Field(None, description="Rule conditions")
    actions: list[ActionRequest] | None = Field(None, description="Actions when triggered")
    cooldown_minutes: int | None = Field(None, ge=0, description="Cooldown between alerts")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class ConditionResponse(BaseModel):
    """A rule condition response."""

    field: str
    operator: str
    value: Any
    label: str


class ActionResponse(BaseModel):
    """An alert action response."""

    type: str
    config: dict[str, Any]


class RuleResponse(BaseModel):
    """Response for an alert rule."""

    id: str = Field(..., description="Rule ID")
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    category: str = Field(..., description="Alert category")
    severity: str = Field(..., description="Alert severity")
    status: str = Field(..., description="Rule status")
    conditions: list[ConditionResponse] = Field(..., description="Rule conditions")
    actions: list[ActionResponse] = Field(..., description="Actions when triggered")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    created_by: str = Field(..., description="Creator user ID")
    patient_filter: dict[str, Any] | None = Field(None, description="Patient filter")
    cooldown_minutes: int = Field(..., description="Cooldown minutes")
    metadata: dict[str, Any] = Field(..., description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "rule-123",
                "name": "High Readmission Risk",
                "description": "Alert when 30-day readmission risk exceeds threshold",
                "category": "risk_score",
                "severity": "high",
                "status": "active",
                "conditions": [
                    {
                        "field": "readmission_risk_score",
                        "operator": "gte",
                        "value": 0.7,
                        "label": "Readmission risk >= 70%",
                    }
                ],
                "actions": [{"type": "notify", "config": {"channel": "care_team"}}],
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00",
                "created_by": "user-123",
                "cooldown_minutes": 60,
                "metadata": {},
            }
        }
    }


class RuleListResponse(BaseModel):
    """Response for list of alert rules."""

    total: int = Field(..., description="Total number of rules")
    rules: list[RuleResponse] = Field(..., description="List of rules")


class EvaluateRequest(BaseModel):
    """Request to evaluate a rule against patient data."""

    patient_data: dict[str, Any] = Field(..., description="Patient data to evaluate")
    patient_id: str | None = Field(None, description="Patient identifier")

    model_config = {
        "json_schema_extra": {
            "example": {
                "patient_data": {
                    "readmission_risk_score": 0.75,
                    "mortality_risk_tier": "medium",
                    "potassium": 4.5,
                },
                "patient_id": "patient-123",
            }
        }
    }


class EvaluationResponse(BaseModel):
    """Response for rule evaluation."""

    rule_id: str = Field(..., description="Rule ID")
    rule_name: str = Field(..., description="Rule name")
    triggered: bool = Field(..., description="Whether alert was triggered")
    severity: str = Field(..., description="Alert severity")
    message: str = Field(..., description="Evaluation message")
    matched_conditions: list[str] = Field(..., description="Conditions that matched")
    patient_id: str | None = Field(None, description="Patient identifier")
    evaluated_at: str = Field(..., description="Evaluation timestamp")


class EvaluatePatientRequest(BaseModel):
    """Request to evaluate all rules against a patient."""

    patient_data: dict[str, Any] = Field(..., description="Patient data")
    patient_id: str | None = Field(None, description="Patient identifier")
    category: str | None = Field(None, description="Filter by category")


class EvaluatePatientResponse(BaseModel):
    """Response for patient evaluation."""

    total_rules: int = Field(..., description="Total rules evaluated")
    triggered_count: int = Field(..., description="Number of triggered alerts")
    evaluations: list[EvaluationResponse] = Field(..., description="All evaluations")


class StatsResponse(BaseModel):
    """Response for alert rules statistics."""

    total_rules: int = Field(..., description="Total number of rules")
    by_category: dict[str, int] = Field(..., description="Rules by category")
    by_severity: dict[str, int] = Field(..., description="Rules by severity")
    by_status: dict[str, int] = Field(..., description="Rules by status")
    active_rules: int = Field(..., description="Number of active rules")


class OperatorsResponse(BaseModel):
    """Response for available operators."""

    operators: list[dict[str, str]] = Field(..., description="Available operators")


class CategoriesResponse(BaseModel):
    """Response for available categories."""

    categories: list[dict[str, str]] = Field(..., description="Available categories")


class SeveritiesResponse(BaseModel):
    """Response for available severities."""

    severities: list[dict[str, str]] = Field(..., description="Available severities")


# ============================================================================
# Helper Functions
# ============================================================================


def _rule_to_response(rule) -> RuleResponse:
    """Convert AlertRule to response model."""
    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        category=rule.category.value,
        severity=rule.severity.value,
        status=rule.status.value,
        conditions=[
            ConditionResponse(
                field=c.field,
                operator=c.operator.value,
                value=c.value,
                label=c.label,
            )
            for c in rule.conditions
        ],
        actions=[
            ActionResponse(type=a.type, config=a.config)
            for a in rule.actions
        ],
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
        created_by=rule.created_by,
        patient_filter=rule.patient_filter,
        cooldown_minutes=rule.cooldown_minutes,
        metadata=rule.metadata,
    )


# ============================================================================
# Endpoints - Static routes MUST come before parameterized routes
# ============================================================================


@router.get(
    "",
    response_model=RuleListResponse,
    summary="List alert rules",
    description="Get a list of alert rules with optional filtering.",
)
async def list_rules(
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> RuleListResponse:
    """List alert rules."""
    service = get_alert_rules_service()

    # Convert string filters to enums
    cat_enum = None
    if category:
        try:
            cat_enum = AlertCategory(category)
        except ValueError:
            raise ValidationError(
                message=f"Invalid category: {category}",
                error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
                details=[ErrorDetail(
                    field="category",
                    message=f"Must be one of: {', '.join(c.value for c in AlertCategory)}",
                    value=category,
                )],
            )

    status_enum = None
    if status:
        try:
            status_enum = RuleStatus(status)
        except ValueError:
            raise ValidationError(
                message=f"Invalid status: {status}",
                error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
                details=[ErrorDetail(
                    field="status",
                    message=f"Must be one of: {', '.join(s.value for s in RuleStatus)}",
                    value=status,
                )],
            )

    sev_enum = None
    if severity:
        try:
            sev_enum = AlertSeverity(severity)
        except ValueError:
            raise ValidationError(
                message=f"Invalid severity: {severity}",
                error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
                details=[ErrorDetail(
                    field="severity",
                    message=f"Must be one of: {', '.join(s.value for s in AlertSeverity)}",
                    value=severity,
                )],
            )

    rules = service.list_rules(
        category=cat_enum,
        status=status_enum,
        severity=sev_enum,
        limit=limit,
    )

    return RuleListResponse(
        total=len(rules),
        rules=[_rule_to_response(r) for r in rules],
    )


@router.post(
    "",
    response_model=RuleResponse,
    summary="Create alert rule",
    description="Create a new clinical alert rule.",
)
async def create_rule(request: CreateRuleRequest) -> RuleResponse:
    """Create a new alert rule."""
    service = get_alert_rules_service()

    # Validate enums
    try:
        category = AlertCategory(request.category)
    except ValueError:
        raise ValidationError(
            message=f"Invalid category: {request.category}",
            error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
            details=[ErrorDetail(
                field="category",
                message=f"Must be one of: {', '.join(c.value for c in AlertCategory)}",
                value=request.category,
            )],
        )

    try:
        severity = AlertSeverity(request.severity)
    except ValueError:
        raise ValidationError(
            message=f"Invalid severity: {request.severity}",
            error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
            details=[ErrorDetail(
                field="severity",
                message=f"Must be one of: {', '.join(s.value for s in AlertSeverity)}",
                value=request.severity,
            )],
        )

    # Validate operators in conditions
    for cond in request.conditions:
        try:
            RuleOperator(cond.operator)
        except ValueError:
            raise ValidationError(
                message=f"Invalid operator: {cond.operator}",
                error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
                details=[ErrorDetail(
                    field="conditions[].operator",
                    message=f"Must be one of: {', '.join(o.value for o in RuleOperator)}",
                    value=cond.operator,
                )],
            )

    rule = service.create_rule(
        name=request.name,
        description=request.description,
        category=category,
        severity=severity,
        conditions=[c.model_dump() for c in request.conditions],
        actions=[a.model_dump() for a in request.actions],
        created_by="anonymous",  # Would come from auth in production
        patient_filter=request.patient_filter,
        cooldown_minutes=request.cooldown_minutes,
        metadata=request.metadata,
    )

    return _rule_to_response(rule)


# --- Static routes (must be defined before /{rule_id}) ---


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get statistics",
    description="Get alert rules statistics.",
)
async def get_stats() -> StatsResponse:
    """Get alert rules statistics."""
    service = get_alert_rules_service()
    stats = service.get_stats()

    return StatsResponse(
        total_rules=stats["total_rules"],
        by_category=stats["by_category"],
        by_severity=stats["by_severity"],
        by_status=stats["by_status"],
        active_rules=stats["active_rules"],
    )


@router.get(
    "/meta/operators",
    response_model=OperatorsResponse,
    summary="List operators",
    description="Get list of available rule operators.",
)
async def list_operators() -> OperatorsResponse:
    """List available operators."""
    operators = [
        {"value": op.value, "name": op.name.replace("_", " ").title()}
        for op in RuleOperator
    ]
    return OperatorsResponse(operators=operators)


@router.get(
    "/meta/categories",
    response_model=CategoriesResponse,
    summary="List categories",
    description="Get list of available alert categories.",
)
async def list_categories() -> CategoriesResponse:
    """List available categories."""
    categories = [
        {"value": cat.value, "name": cat.name.replace("_", " ").title()}
        for cat in AlertCategory
    ]
    return CategoriesResponse(categories=categories)


@router.get(
    "/meta/severities",
    response_model=SeveritiesResponse,
    summary="List severities",
    description="Get list of available alert severities.",
)
async def list_severities() -> SeveritiesResponse:
    """List available severities."""
    severities = [
        {"value": sev.value, "name": sev.name.replace("_", " ").title()}
        for sev in AlertSeverity
    ]
    return SeveritiesResponse(severities=severities)


@router.post(
    "/evaluate-patient",
    response_model=EvaluatePatientResponse,
    summary="Evaluate all rules for patient",
    description="Evaluate all active rules against a patient's data.",
)
async def evaluate_patient(request: EvaluatePatientRequest) -> EvaluatePatientResponse:
    """Evaluate all rules against a patient."""
    service = get_alert_rules_service()

    cat_enum = None
    if request.category:
        try:
            cat_enum = AlertCategory(request.category)
        except ValueError:
            raise ValidationError(
            message=f"Invalid category: {request.category}",
            error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
            details=[ErrorDetail(
                field="category",
                message=f"Must be one of: {', '.join(c.value for c in AlertCategory)}",
                value=request.category,
            )],
        )

    evaluations = service.evaluate_patient(
        patient_data=request.patient_data,
        patient_id=request.patient_id,
        category=cat_enum,
    )

    triggered_count = sum(1 for e in evaluations if e.triggered)

    return EvaluatePatientResponse(
        total_rules=len(evaluations),
        triggered_count=triggered_count,
        evaluations=[
            EvaluationResponse(
                rule_id=e.rule_id,
                rule_name=e.rule_name,
                triggered=e.triggered,
                severity=e.severity.value,
                message=e.message,
                matched_conditions=e.matched_conditions,
                patient_id=e.patient_id,
                evaluated_at=e.evaluated_at.isoformat(),
            )
            for e in evaluations
        ],
    )


# --- Parameterized routes (must come after static routes) ---


@router.get(
    "/{rule_id}",
    response_model=RuleResponse,
    summary="Get alert rule",
    description="Get a specific alert rule by ID.",
)
async def get_rule(rule_id: str) -> RuleResponse:
    """Get a specific alert rule."""
    service = get_alert_rules_service()
    rule = service.get_rule(rule_id)

    if not rule:
        raise NotFoundError(
            message=f"Alert rule with ID '{rule_id}' not found",
            error_code=ErrorCode.NOT_FOUND_ALERT_RULE,
        )

    return _rule_to_response(rule)


@router.put(
    "/{rule_id}",
    response_model=RuleResponse,
    summary="Update alert rule",
    description="Update an existing alert rule.",
)
async def update_rule(rule_id: str, request: UpdateRuleRequest) -> RuleResponse:
    """Update an alert rule."""
    service = get_alert_rules_service()

    updates = {}

    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.severity is not None:
        try:
            AlertSeverity(request.severity)
            updates["severity"] = request.severity
        except ValueError:
            raise ValidationError(
            message=f"Invalid severity: {request.severity}",
            error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
            details=[ErrorDetail(
                field="severity",
                message=f"Must be one of: {', '.join(s.value for s in AlertSeverity)}",
                value=request.severity,
            )],
        )
    if request.status is not None:
        try:
            RuleStatus(request.status)
            updates["status"] = request.status
        except ValueError:
            raise ValidationError(
                message=f"Invalid status: {request.status}",
                error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
                details=[ErrorDetail(
                    field="status",
                    message=f"Must be one of: {', '.join(s.value for s in RuleStatus)}",
                    value=request.status,
                )],
            )
    if request.conditions is not None:
        # Validate operators
        for cond in request.conditions:
            try:
                RuleOperator(cond.operator)
            except ValueError:
                raise ValidationError(
                message=f"Invalid operator: {cond.operator}",
                error_code=ErrorCode.VALIDATION_INVALID_ENUM_VALUE,
                details=[ErrorDetail(
                    field="conditions[].operator",
                    message=f"Must be one of: {', '.join(o.value for o in RuleOperator)}",
                    value=cond.operator,
                )],
            )
        updates["conditions"] = [c.model_dump() for c in request.conditions]
    if request.actions is not None:
        updates["actions"] = [a.model_dump() for a in request.actions]
    if request.cooldown_minutes is not None:
        updates["cooldown_minutes"] = request.cooldown_minutes
    if request.metadata is not None:
        updates["metadata"] = request.metadata

    rule = service.update_rule(rule_id, **updates)

    if not rule:
        raise NotFoundError(
            message=f"Alert rule with ID '{rule_id}' not found",
            error_code=ErrorCode.NOT_FOUND_ALERT_RULE,
        )

    return _rule_to_response(rule)


@router.delete(
    "/{rule_id}",
    summary="Delete alert rule",
    description="Delete an alert rule.",
)
async def delete_rule(rule_id: str) -> dict[str, bool]:
    """Delete an alert rule."""
    service = get_alert_rules_service()
    deleted = service.delete_rule(rule_id)

    if not deleted:
        raise NotFoundError(
            message=f"Alert rule with ID '{rule_id}' not found",
            error_code=ErrorCode.NOT_FOUND_ALERT_RULE,
        )

    return {"deleted": True}


@router.post(
    "/{rule_id}/evaluate",
    response_model=EvaluationResponse,
    summary="Evaluate rule",
    description="Evaluate a specific rule against patient data.",
)
async def evaluate_rule(rule_id: str, request: EvaluateRequest) -> EvaluationResponse:
    """Evaluate a rule against patient data."""
    service = get_alert_rules_service()

    evaluation = service.evaluate_rule(
        rule_id=rule_id,
        patient_data=request.patient_data,
        patient_id=request.patient_id,
    )

    return EvaluationResponse(
        rule_id=evaluation.rule_id,
        rule_name=evaluation.rule_name,
        triggered=evaluation.triggered,
        severity=evaluation.severity.value,
        message=evaluation.message,
        matched_conditions=evaluation.matched_conditions,
        patient_id=evaluation.patient_id,
        evaluated_at=evaluation.evaluated_at.isoformat(),
    )
