"""CDS Hooks API endpoints.

Implements CDS Hooks specification 1.1 REST endpoints:
- GET /cds-services - Discovery endpoint
- POST /cds-services/{service_id} - Hook invocation
- POST /cds-services/{service_id}/feedback - Feedback endpoint (optional)

See: https://cds-hooks.org/specification/current/
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.cds_hooks_service import (
    CDSHooksService,
    HookType,
    get_cds_hooks_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cds-services", tags=["CDS Hooks"])


# =============================================================================
# Request/Response Models
# =============================================================================


class FHIRCoding(BaseModel):
    """FHIR Coding element."""

    system: str | None = None
    code: str | None = None
    display: str | None = None


class FHIRCodeableConcept(BaseModel):
    """FHIR CodeableConcept element."""

    coding: list[FHIRCoding] = Field(default_factory=list)
    text: str | None = None


class CDSHookRequest(BaseModel):
    """CDS Hooks request payload per specification.

    See: https://cds-hooks.org/specification/current/#http-request_1
    """

    hook: str = Field(..., description="The hook being invoked (e.g., 'patient-view')")
    hookInstance: str = Field(..., description="Unique identifier for this hook invocation")
    fhirServer: str | None = Field(None, description="Base URL of the FHIR server")
    fhirAuthorization: dict[str, Any] | None = Field(
        None, description="OAuth2 authorization for FHIR server"
    )
    context: dict[str, Any] = Field(..., description="Hook-specific context data")
    prefetch: dict[str, Any] | None = Field(
        None, description="Prefetched FHIR resources"
    )


class CDSCardSource(BaseModel):
    """Source attribution for a CDS card."""

    label: str = Field(..., description="Short display name for the source")
    url: str | None = Field(None, description="Link to the source")
    icon: str | None = Field(None, description="URL to an icon for the source")


class CDSAction(BaseModel):
    """An action that can be taken from a card."""

    type: str = Field(..., description="Action type: create, update, or delete")
    description: str = Field(..., description="Human-readable description of action")
    resource: dict[str, Any] | None = Field(None, description="FHIR resource for the action")
    resourceId: str | None = Field(None, description="Resource ID for update/delete")


class CDSSuggestion(BaseModel):
    """A suggestion for the user."""

    uuid: str = Field(..., description="Unique identifier for this suggestion")
    label: str = Field(..., description="Human-readable label")
    isRecommended: bool = Field(False, description="Whether this is the recommended option")
    actions: list[CDSAction] = Field(default_factory=list)


class CDSLink(BaseModel):
    """A link to external resources."""

    label: str = Field(..., description="Human-readable label for the link")
    url: str = Field(..., description="URL to link to")
    type: str = Field("absolute", description="Link type: 'absolute' or 'smart'")
    appContext: str | None = Field(None, description="SMART app context for 'smart' links")


class CDSCard(BaseModel):
    """A CDS Hooks response card."""

    uuid: str = Field(..., description="Unique identifier for this card")
    summary: str = Field(..., description="Short summary (< 140 chars)")
    detail: str | None = Field(None, description="Detailed information (markdown)")
    indicator: str = Field(..., description="Urgency: info, warning, critical, hard-stop")
    source: CDSCardSource = Field(..., description="Source attribution")
    suggestions: list[CDSSuggestion] = Field(default_factory=list)
    selectionBehavior: str | None = Field(None, description="Selection behavior for suggestions")
    overrideReasons: list[dict[str, str]] | None = Field(
        None, description="Reasons for overriding the card"
    )
    links: list[CDSLink] = Field(default_factory=list)


class CDSHookResponse(BaseModel):
    """CDS Hooks response payload per specification."""

    cards: list[CDSCard] = Field(default_factory=list)
    systemActions: list[CDSAction] | None = Field(
        None, description="Actions to execute automatically"
    )


class CDSServiceDefinition(BaseModel):
    """Service definition for discovery endpoint."""

    hook: str = Field(..., description="Hook type this service implements")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Description of the service")
    id: str = Field(..., description="Unique service identifier")
    prefetch: dict[str, str] | None = Field(
        None, description="Prefetch template queries"
    )
    usageRequirements: str | None = Field(
        None, description="Requirements for using this service"
    )


class CDSDiscoveryResponse(BaseModel):
    """Response for the discovery endpoint."""

    services: list[CDSServiceDefinition] = Field(default_factory=list)


class CDSFeedbackRequest(BaseModel):
    """Feedback about a card that was displayed."""

    card: str = Field(..., description="UUID of the card")
    outcome: str = Field(..., description="Outcome: accepted, overridden")
    overrideReasons: list[FHIRCoding] | None = Field(
        None, description="Reasons for override"
    )
    outcomeTimestamp: str | None = Field(None, description="When the outcome occurred")


class CDSHookLogEntry(BaseModel):
    """Log entry for hook invocation."""

    hook_id: str
    hook_type: str
    timestamp: str
    patient_id: str | None
    user_id: str | None
    cards_returned: int
    duration_ms: float
    error: str | None


class CDSHookLogsResponse(BaseModel):
    """Response for hook logs endpoint."""

    logs: list[CDSHookLogEntry]
    total: int


class CDSServiceStats(BaseModel):
    """Statistics for the CDS service."""

    services_count: int
    total_invocations: int
    recent_invocations_24h: int
    invocations_by_hook: dict[str, int]


# =============================================================================
# Discovery Endpoint
# =============================================================================


@router.get(
    "",
    response_model=CDSDiscoveryResponse,
    summary="CDS Services Discovery",
    description="Returns a list of available CDS services (hooks) that this server implements.",
)
def discover_services() -> CDSDiscoveryResponse:
    """Discovery endpoint for CDS Hooks.

    Per CDS Hooks specification, clients call this endpoint to discover
    what hooks are available and their prefetch requirements.

    Returns:
        List of available CDS services.
    """
    service = get_cds_hooks_service()
    services = service.get_services()

    return CDSDiscoveryResponse(
        services=[
            CDSServiceDefinition(
                hook=svc["hook"],
                title=svc["title"],
                description=svc["description"],
                id=svc["id"],
                prefetch=svc.get("prefetch"),
                usageRequirements=svc.get("usageRequirements"),
            )
            for svc in services
        ]
    )


# =============================================================================
# Hook Invocation Endpoints
# =============================================================================


@router.post(
    "/patient-view",
    response_model=CDSHookResponse,
    summary="Patient View Hook",
    description="Invoked when a patient chart is opened. Returns relevant alerts and information.",
)
def invoke_patient_view(request: CDSHookRequest) -> CDSHookResponse:
    """Invoke the patient-view hook.

    This hook is triggered when a clinician opens a patient's chart.
    It can return cards with:
    - Active drug interactions
    - Care gaps and overdue screenings
    - Important alerts about patient conditions

    Args:
        request: CDS Hooks request with patient context.

    Returns:
        CDS Hooks response with relevant cards.
    """
    if request.hook != "patient-view":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hook type: expected 'patient-view', got '{request.hook}'",
        )

    service = get_cds_hooks_service()
    response = service.invoke_patient_view(
        context=request.context,
        prefetch=request.prefetch,
    )

    return CDSHookResponse(**response.to_dict())


@router.post(
    "/order-select",
    response_model=CDSHookResponse,
    summary="Order Select Hook",
    description="Invoked when medications/orders are selected. Checks for drug interactions.",
)
def invoke_order_select(request: CDSHookRequest) -> CDSHookResponse:
    """Invoke the order-select hook.

    This hook is triggered when a clinician selects one or more
    orders (typically medications) for a patient. It checks for:
    - Drug-drug interactions with current medications
    - Duplicate therapy
    - Contraindications

    Args:
        request: CDS Hooks request with order selection context.

    Returns:
        CDS Hooks response with interaction alerts.
    """
    if request.hook != "order-select":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hook type: expected 'order-select', got '{request.hook}'",
        )

    service = get_cds_hooks_service()
    response = service.invoke_order_select(
        context=request.context,
        prefetch=request.prefetch,
    )

    return CDSHookResponse(**response.to_dict())


@router.post(
    "/order-sign",
    response_model=CDSHookResponse,
    summary="Order Sign Hook",
    description="Invoked before orders are signed. Performs final validation.",
)
def invoke_order_sign(request: CDSHookRequest) -> CDSHookResponse:
    """Invoke the order-sign hook.

    This hook is triggered just before a clinician signs orders.
    It performs final validation including:
    - Contraindicated drug combinations (hard-stop)
    - Major drug interactions
    - Required documentation checks
    - Duplicate therapy warnings

    Args:
        request: CDS Hooks request with orders to be signed.

    Returns:
        CDS Hooks response with validation results.
    """
    if request.hook != "order-sign":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hook type: expected 'order-sign', got '{request.hook}'",
        )

    service = get_cds_hooks_service()
    response = service.invoke_order_sign(
        context=request.context,
        prefetch=request.prefetch,
    )

    return CDSHookResponse(**response.to_dict())


@router.post(
    "/medication-prescribe",
    response_model=CDSHookResponse,
    summary="Medication Prescribe Hook",
    description="Invoked during medication prescribing workflow.",
)
def invoke_medication_prescribe(request: CDSHookRequest) -> CDSHookResponse:
    """Invoke the medication-prescribe hook.

    This hook is triggered during the medication prescribing workflow.
    It provides guidance including:
    - Drug interaction alerts
    - Allergy cross-checks
    - Dosing recommendations
    - Formulary information

    Args:
        request: CDS Hooks request with prescription context.

    Returns:
        CDS Hooks response with prescribing guidance.
    """
    if request.hook != "medication-prescribe":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hook type: expected 'medication-prescribe', got '{request.hook}'",
        )

    service = get_cds_hooks_service()
    response = service.invoke_medication_prescribe(
        context=request.context,
        prefetch=request.prefetch,
    )

    return CDSHookResponse(**response.to_dict())


# =============================================================================
# Generic Hook Invocation (for any service)
# =============================================================================


@router.post(
    "/{service_id}",
    response_model=CDSHookResponse,
    summary="Invoke CDS Service",
    description="Generic endpoint to invoke any CDS service by ID.",
)
def invoke_service(service_id: str, request: CDSHookRequest) -> CDSHookResponse:
    """Invoke a CDS service by ID.

    This is the generic endpoint that routes to the appropriate hook handler
    based on the service ID.

    Args:
        service_id: The service identifier (e.g., "patient-view").
        request: CDS Hooks request payload.

    Returns:
        CDS Hooks response with cards.

    Raises:
        HTTPException: 404 if service not found, 400 if hook type mismatch.
    """
    service = get_cds_hooks_service()
    service_def = service.get_service_by_id(service_id)

    if not service_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service not found: {service_id}",
        )

    # Validate hook type matches
    if request.hook != service_def.hook.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hook type mismatch: service expects '{service_def.hook.value}', got '{request.hook}'",
        )

    # Route to appropriate handler
    if service_def.hook == HookType.PATIENT_VIEW:
        response = service.invoke_patient_view(request.context, request.prefetch)
    elif service_def.hook == HookType.ORDER_SELECT:
        response = service.invoke_order_select(request.context, request.prefetch)
    elif service_def.hook == HookType.ORDER_SIGN:
        response = service.invoke_order_sign(request.context, request.prefetch)
    elif service_def.hook == HookType.MEDICATION_PRESCRIBE:
        response = service.invoke_medication_prescribe(request.context, request.prefetch)
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Hook type not implemented: {service_def.hook.value}",
        )

    return CDSHookResponse(**response.to_dict())


# =============================================================================
# Feedback Endpoint (Optional per spec)
# =============================================================================


@router.post(
    "/{service_id}/feedback",
    status_code=status.HTTP_200_OK,
    summary="Submit Card Feedback",
    description="Submit feedback about how a card was handled.",
)
def submit_feedback(service_id: str, feedback: CDSFeedbackRequest) -> dict[str, str]:
    """Submit feedback about a CDS card.

    This optional endpoint allows EHR systems to report what happened
    after a card was displayed (accepted, overridden, etc.).

    Args:
        service_id: The service that generated the card.
        feedback: Feedback about the card outcome.

    Returns:
        Acknowledgment of feedback receipt.
    """
    service = get_cds_hooks_service()
    service_def = service.get_service_by_id(service_id)

    if not service_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service not found: {service_id}",
        )

    # Log the feedback
    logger.info(
        "CDS feedback received: service=%s, card=%s, outcome=%s",
        service_id,
        feedback.card,
        feedback.outcome,
    )

    # In production, this would be stored for analytics and improvement
    return {"status": "feedback received"}


# =============================================================================
# Administrative Endpoints
# =============================================================================


@router.get(
    "/admin/logs",
    response_model=CDSHookLogsResponse,
    summary="Get Hook Invocation Logs",
    description="Get recent CDS hook invocation logs for auditing.",
    tags=["CDS Hooks Admin"],
)
def get_hook_logs(
    limit: int = 100,
    hook_type: str | None = None,
    patient_id: str | None = None,
) -> CDSHookLogsResponse:
    """Get CDS hook invocation logs.

    Args:
        limit: Maximum number of logs to return.
        hook_type: Filter by hook type.
        patient_id: Filter by patient ID.

    Returns:
        Recent hook invocation logs.
    """
    service = get_cds_hooks_service()

    hook_type_enum = None
    if hook_type:
        try:
            hook_type_enum = HookType(hook_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid hook type: {hook_type}",
            )

    logs = service.get_hook_logs(
        limit=limit,
        hook_type=hook_type_enum,
        patient_id=patient_id,
    )

    return CDSHookLogsResponse(
        logs=[
            CDSHookLogEntry(
                hook_id=log["hook_id"],
                hook_type=log["hook_type"],
                timestamp=log["timestamp"],
                patient_id=log["patient_id"],
                user_id=log["user_id"],
                cards_returned=log["cards_returned"],
                duration_ms=log["duration_ms"],
                error=log["error"],
            )
            for log in logs
        ],
        total=len(logs),
    )


@router.get(
    "/admin/stats",
    response_model=CDSServiceStats,
    summary="Get Service Statistics",
    description="Get CDS Hooks service statistics.",
    tags=["CDS Hooks Admin"],
)
def get_service_stats() -> CDSServiceStats:
    """Get CDS Hooks service statistics.

    Returns:
        Service usage statistics.
    """
    service = get_cds_hooks_service()
    stats = service.get_stats()

    return CDSServiceStats(
        services_count=stats["services_count"],
        total_invocations=stats["total_invocations"],
        recent_invocations_24h=stats["recent_invocations_24h"],
        invocations_by_hook=stats["invocations_by_hook"],
    )


# =============================================================================
# Test Endpoint (for development/demo)
# =============================================================================


class TestHookRequest(BaseModel):
    """Simplified test request for trying hooks."""

    hook_type: str = Field(..., description="Hook type to test")
    patient_id: str = Field("test-patient-001", description="Test patient ID")
    medications: list[str] = Field(
        default_factory=list,
        description="List of medication names",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="List of condition names",
    )


@router.post(
    "/test",
    response_model=CDSHookResponse,
    summary="Test CDS Hook",
    description="Test endpoint for trying CDS hooks with simplified input.",
    tags=["CDS Hooks Admin"],
)
def test_hook(request: TestHookRequest) -> CDSHookResponse:
    """Test a CDS hook with simplified input.

    This endpoint allows testing hooks without constructing
    full FHIR resources. Useful for development and demos.

    Args:
        request: Simplified test request.

    Returns:
        CDS Hooks response.
    """
    import uuid

    service = get_cds_hooks_service()

    # Build context based on hook type
    context: dict[str, Any] = {
        "patientId": request.patient_id,
        "userId": "test-user",
    }

    # Build prefetch with mock FHIR resources
    prefetch: dict[str, Any] = {
        "patient": {
            "resourceType": "Patient",
            "id": request.patient_id,
            "name": [{"family": "Test", "given": ["Patient"]}],
        },
    }

    # Add medications to prefetch
    if request.medications:
        prefetch["medications"] = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": f"med-{i}",
                        "status": "active",
                        "medicationCodeableConcept": {
                            "coding": [
                                {
                                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                    "display": med,
                                }
                            ],
                            "text": med,
                        },
                    }
                }
                for i, med in enumerate(request.medications)
            ],
        }

    # Add conditions to prefetch
    if request.conditions:
        prefetch["conditions"] = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Condition",
                        "id": f"cond-{i}",
                        "clinicalStatus": {
                            "coding": [{"code": "active"}]
                        },
                        "code": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "display": cond,
                                }
                            ],
                            "text": cond,
                        },
                    }
                }
                for i, cond in enumerate(request.conditions)
            ],
        }

    # For order-select/order-sign, add medications to context
    if request.hook_type in ["order-select", "order-sign", "medication-prescribe"]:
        context["medications"] = request.medications
        if request.medications:
            context["draftOrders"] = {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": f"draft-{i}",
                            "status": "draft",
                            "medicationCodeableConcept": {
                                "coding": [{"display": med}],
                                "text": med,
                            },
                        }
                    }
                    for i, med in enumerate(request.medications)
                ],
            }

    # Invoke appropriate hook
    try:
        hook_type = HookType(request.hook_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hook type: {request.hook_type}. Valid types: {[h.value for h in HookType]}",
        )

    if hook_type == HookType.PATIENT_VIEW:
        response = service.invoke_patient_view(context, prefetch)
    elif hook_type == HookType.ORDER_SELECT:
        response = service.invoke_order_select(context, prefetch)
    elif hook_type == HookType.ORDER_SIGN:
        response = service.invoke_order_sign(context, prefetch)
    elif hook_type == HookType.MEDICATION_PRESCRIBE:
        response = service.invoke_medication_prescribe(context, prefetch)
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Hook type not implemented: {hook_type.value}",
        )

    return CDSHookResponse(**response.to_dict())
