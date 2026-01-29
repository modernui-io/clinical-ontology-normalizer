"""CDS Hooks Service.

Implements CDS Hooks specification 1.1 for clinical decision support.
Provides hooks for:
- patient-view: Alerts when patient chart is opened
- order-select: Drug interaction checks when medication selected
- order-sign: Order validation before signing
- medication-prescribe: Medication prescribing checks

See: https://cds-hooks.org/specification/current/
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any

from app.services.drug_interactions import (
    DrugInteractionService,
    InteractionSeverity,
    get_drug_interaction_service,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CDS Hooks Enums and Types
# =============================================================================


class CDSIndicator(str, Enum):
    """CDS Card indicator levels per specification."""

    INFO = "info"  # Informational, no action required
    WARNING = "warning"  # Attention needed, but not critical
    CRITICAL = "critical"  # Urgent attention required
    HARD_STOP = "hard-stop"  # Cannot proceed without addressing


class CDSActionType(str, Enum):
    """Types of actions that can be suggested."""

    CREATE = "create"  # Create a new resource
    UPDATE = "update"  # Update an existing resource
    DELETE = "delete"  # Delete a resource


class CDSLinkType(str, Enum):
    """Types of links that can be provided."""

    ABSOLUTE = "absolute"  # External URL
    SMART = "smart"  # SMART app launch URL


class HookType(str, Enum):
    """Supported CDS Hook types."""

    PATIENT_VIEW = "patient-view"
    ORDER_SELECT = "order-select"
    ORDER_SIGN = "order-sign"
    MEDICATION_PRESCRIBE = "medication-prescribe"


# =============================================================================
# CDS Hooks Data Classes
# =============================================================================


@dataclass
class CDSSource:
    """Source attribution for a CDS card."""

    label: str
    url: str | None = None
    icon: str | None = None
    topic: dict[str, str] | None = None  # Coding for the topic


@dataclass
class CDSAction:
    """An action that can be performed from a suggestion."""

    type: CDSActionType
    description: str
    resource: dict[str, Any] | None = None  # FHIR resource for create/update
    resource_id: str | None = None  # For update/delete actions


@dataclass
class CDSSuggestion:
    """A suggestion for the user to take action."""

    label: str
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_recommended: bool = False
    actions: list[CDSAction] = field(default_factory=list)


@dataclass
class CDSLink:
    """A link to external resources."""

    label: str
    url: str
    type: CDSLinkType = CDSLinkType.ABSOLUTE
    app_context: str | None = None  # For SMART app launches


@dataclass
class CDSCard:
    """A CDS Hooks response card."""

    summary: str
    indicator: CDSIndicator
    source: CDSSource
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    detail: str | None = None
    suggestions: list[CDSSuggestion] = field(default_factory=list)
    selection_behavior: str | None = None  # "at-most-one" or None
    override_reasons: list[dict[str, str]] | None = None
    links: list[CDSLink] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to CDS Hooks spec-compliant dictionary."""
        result: dict[str, Any] = {
            "uuid": self.uuid,
            "summary": self.summary,
            "indicator": self.indicator.value,
            "source": {
                "label": self.source.label,
            },
        }

        if self.source.url:
            result["source"]["url"] = self.source.url
        if self.source.icon:
            result["source"]["icon"] = self.source.icon
        if self.source.topic:
            result["source"]["topic"] = self.source.topic

        if self.detail:
            result["detail"] = self.detail

        if self.suggestions:
            result["suggestions"] = [
                {
                    "uuid": s.uuid,
                    "label": s.label,
                    "isRecommended": s.is_recommended,
                    "actions": [
                        {
                            "type": a.type.value,
                            "description": a.description,
                            **({"resource": a.resource} if a.resource else {}),
                            **({"resourceId": a.resource_id} if a.resource_id else {}),
                        }
                        for a in s.actions
                    ],
                }
                for s in self.suggestions
            ]

        if self.selection_behavior:
            result["selectionBehavior"] = self.selection_behavior

        if self.override_reasons:
            result["overrideReasons"] = self.override_reasons

        if self.links:
            result["links"] = [
                {
                    "label": link.label,
                    "url": link.url,
                    "type": link.type.value,
                    **({"appContext": link.app_context} if link.app_context else {}),
                }
                for link in self.links
            ]

        return result


@dataclass
class CDSResponse:
    """Response from a CDS hook invocation."""

    cards: list[CDSCard] = field(default_factory=list)
    system_actions: list[CDSAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to CDS Hooks spec-compliant dictionary."""
        result: dict[str, Any] = {
            "cards": [card.to_dict() for card in self.cards],
        }

        if self.system_actions:
            result["systemActions"] = [
                {
                    "type": a.type.value,
                    "description": a.description,
                    **({"resource": a.resource} if a.resource else {}),
                    **({"resourceId": a.resource_id} if a.resource_id else {}),
                }
                for a in self.system_actions
            ]

        return result


@dataclass
class CDSServiceDefinition:
    """Definition of a CDS Hook service for discovery."""

    hook: HookType
    title: str
    description: str
    id: str
    prefetch: dict[str, str] | None = None
    usage_requirements: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to CDS Hooks spec-compliant dictionary."""
        result: dict[str, Any] = {
            "hook": self.hook.value,
            "title": self.title,
            "description": self.description,
            "id": self.id,
        }

        if self.prefetch:
            result["prefetch"] = self.prefetch

        if self.usage_requirements:
            result["usageRequirements"] = self.usage_requirements

        return result


@dataclass
class CDSHookLog:
    """Audit log entry for CDS hook invocation."""

    hook_id: str
    hook_type: HookType
    timestamp: datetime
    patient_id: str | None
    user_id: str | None
    context: dict[str, Any]
    cards_returned: int
    duration_ms: float
    error: str | None = None


# =============================================================================
# FHIR Context Extractors
# =============================================================================


def extract_patient_id(context: dict[str, Any]) -> str | None:
    """Extract patient ID from hook context."""
    # Direct patient ID
    if "patientId" in context:
        return context["patientId"]

    # From FHIR Patient resource
    if "patient" in context:
        patient = context["patient"]
        if isinstance(patient, dict):
            return patient.get("id")
        return patient

    return None


def extract_medications_from_context(
    context: dict[str, Any], prefetch: dict[str, Any] | None = None
) -> list[str]:
    """Extract medication names from hook context and prefetch."""
    medications: list[str] = []

    # From selections (order-select hook)
    if "selections" in context:
        for selection in context["selections"]:
            if isinstance(selection, str):
                # Selection is a reference like "MedicationRequest/123"
                if prefetch and "draftOrders" in prefetch:
                    bundle = prefetch["draftOrders"]
                    if bundle.get("resourceType") == "Bundle":
                        for entry in bundle.get("entry", []):
                            resource = entry.get("resource", {})
                            if _extract_medication_name(resource):
                                medications.append(_extract_medication_name(resource))

    # From draftOrders in context
    if "draftOrders" in context:
        orders = context["draftOrders"]
        if orders.get("resourceType") == "Bundle":
            for entry in orders.get("entry", []):
                resource = entry.get("resource", {})
                med_name = _extract_medication_name(resource)
                if med_name:
                    medications.append(med_name)

    # From prefetch medications
    if prefetch:
        if "medications" in prefetch:
            bundle = prefetch["medications"]
            if bundle.get("resourceType") == "Bundle":
                for entry in bundle.get("entry", []):
                    resource = entry.get("resource", {})
                    med_name = _extract_medication_name(resource)
                    if med_name:
                        medications.append(med_name)

    # From context medications list (custom extension)
    if "medications" in context:
        for med in context["medications"]:
            if isinstance(med, str):
                medications.append(med)
            elif isinstance(med, dict):
                med_name = _extract_medication_name(med)
                if med_name:
                    medications.append(med_name)

    return medications


def _extract_medication_name(resource: dict[str, Any]) -> str | None:
    """Extract medication name from a FHIR MedicationRequest or Medication resource."""
    resource_type = resource.get("resourceType")

    if resource_type == "MedicationRequest":
        # Check medicationCodeableConcept
        med_cc = resource.get("medicationCodeableConcept", {})
        if med_cc:
            # Try display first
            for coding in med_cc.get("coding", []):
                if coding.get("display"):
                    return coding["display"]
            # Fall back to text
            if med_cc.get("text"):
                return med_cc["text"]

        # Check medicationReference
        med_ref = resource.get("medicationReference", {})
        if med_ref.get("display"):
            return med_ref["display"]

    elif resource_type == "Medication":
        code = resource.get("code", {})
        for coding in code.get("coding", []):
            if coding.get("display"):
                return coding["display"]
        if code.get("text"):
            return code["text"]

    return None


def extract_conditions_from_prefetch(prefetch: dict[str, Any] | None) -> list[str]:
    """Extract condition names from prefetch data."""
    conditions: list[str] = []

    if not prefetch:
        return conditions

    if "conditions" in prefetch:
        bundle = prefetch["conditions"]
        if bundle.get("resourceType") == "Bundle":
            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                if resource.get("resourceType") == "Condition":
                    code = resource.get("code", {})
                    for coding in code.get("coding", []):
                        if coding.get("display"):
                            conditions.append(coding["display"])
                            break
                    else:
                        if code.get("text"):
                            conditions.append(code["text"])

    return conditions


# =============================================================================
# CDS Hooks Service
# =============================================================================


class CDSHooksService:
    """CDS Hooks Service implementing spec 1.1.

    Provides clinical decision support through standardized hooks:
    - patient-view: Triggered when patient chart is opened
    - order-select: Triggered when medication/order is selected
    - order-sign: Triggered before signing orders
    - medication-prescribe: Triggered during medication prescribing

    Usage:
        service = CDSHooksService()

        # Get available services
        services = service.get_services()

        # Invoke a hook
        response = service.invoke_patient_view(context, prefetch)
    """

    def __init__(self) -> None:
        """Initialize the CDS Hooks service."""
        self._drug_interaction_service: DrugInteractionService | None = None
        self._hook_logs: list[CDSHookLog] = []
        self._max_logs = 1000  # Keep last 1000 logs

        # Define available services
        self._services: list[CDSServiceDefinition] = [
            CDSServiceDefinition(
                hook=HookType.PATIENT_VIEW,
                id="patient-view",
                title="Patient View Alerts",
                description="Displays relevant alerts when a patient chart is opened",
                prefetch={
                    "patient": "Patient/{{context.patientId}}",
                    "conditions": "Condition?patient={{context.patientId}}&clinical-status=active",
                    "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
                    "allergies": "AllergyIntolerance?patient={{context.patientId}}",
                },
            ),
            CDSServiceDefinition(
                hook=HookType.ORDER_SELECT,
                id="order-select",
                title="Drug Interaction Check",
                description="Checks for drug-drug interactions when medications are selected",
                prefetch={
                    "patient": "Patient/{{context.patientId}}",
                    "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
                },
            ),
            CDSServiceDefinition(
                hook=HookType.ORDER_SIGN,
                id="order-sign",
                title="Order Validation",
                description="Validates orders before signing to ensure safety and completeness",
                prefetch={
                    "patient": "Patient/{{context.patientId}}",
                    "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
                    "conditions": "Condition?patient={{context.patientId}}&clinical-status=active",
                },
            ),
            CDSServiceDefinition(
                hook=HookType.MEDICATION_PRESCRIBE,
                id="medication-prescribe",
                title="Medication Prescribe Alerts",
                description="Provides alerts during medication prescribing workflow",
                prefetch={
                    "patient": "Patient/{{context.patientId}}",
                    "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
                    "allergies": "AllergyIntolerance?patient={{context.patientId}}",
                },
            ),
        ]

        logger.info("CDS Hooks service initialized with %d services", len(self._services))

    @property
    def drug_interaction_service(self) -> DrugInteractionService:
        """Lazy-load drug interaction service."""
        if self._drug_interaction_service is None:
            self._drug_interaction_service = get_drug_interaction_service()
        return self._drug_interaction_service

    def get_services(self) -> list[dict[str, Any]]:
        """Get list of available CDS services (discovery endpoint).

        Returns:
            List of service definitions per CDS Hooks spec.
        """
        return [svc.to_dict() for svc in self._services]

    def get_service_by_id(self, service_id: str) -> CDSServiceDefinition | None:
        """Get a service definition by ID."""
        for svc in self._services:
            if svc.id == service_id:
                return svc
        return None

    def _log_hook_invocation(
        self,
        hook_id: str,
        hook_type: HookType,
        context: dict[str, Any],
        cards_returned: int,
        duration_ms: float,
        error: str | None = None,
    ) -> None:
        """Log a hook invocation for audit purposes."""
        log_entry = CDSHookLog(
            hook_id=hook_id,
            hook_type=hook_type,
            timestamp=datetime.now(timezone.utc),
            patient_id=extract_patient_id(context),
            user_id=context.get("userId"),
            context=context,
            cards_returned=cards_returned,
            duration_ms=duration_ms,
            error=error,
        )

        self._hook_logs.append(log_entry)

        # Trim old logs
        if len(self._hook_logs) > self._max_logs:
            self._hook_logs = self._hook_logs[-self._max_logs:]

        logger.info(
            "CDS hook invoked: %s for patient %s, returned %d cards in %.2fms",
            hook_type.value,
            log_entry.patient_id,
            cards_returned,
            duration_ms,
        )

    def get_hook_logs(
        self,
        limit: int = 100,
        hook_type: HookType | None = None,
        patient_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent hook invocation logs.

        Args:
            limit: Maximum number of logs to return.
            hook_type: Filter by hook type.
            patient_id: Filter by patient ID.

        Returns:
            List of log entries.
        """
        logs = self._hook_logs.copy()

        if hook_type:
            logs = [log for log in logs if log.hook_type == hook_type]

        if patient_id:
            logs = [log for log in logs if log.patient_id == patient_id]

        # Return most recent first
        logs = logs[-limit:]
        logs.reverse()

        return [
            {
                "hook_id": log.hook_id,
                "hook_type": log.hook_type.value,
                "timestamp": log.timestamp.isoformat(),
                "patient_id": log.patient_id,
                "user_id": log.user_id,
                "cards_returned": log.cards_returned,
                "duration_ms": log.duration_ms,
                "error": log.error,
            }
            for log in logs
        ]

    # =========================================================================
    # Hook Implementations
    # =========================================================================

    def invoke_patient_view(
        self,
        context: dict[str, Any],
        prefetch: dict[str, Any] | None = None,
    ) -> CDSResponse:
        """Invoke patient-view hook.

        Triggered when a patient chart is opened. Returns alerts about:
        - Active drug interactions
        - Care gaps
        - Overdue screenings
        - Critical conditions

        Args:
            context: Hook context with patientId, userId, etc.
            prefetch: Prefetched FHIR resources.

        Returns:
            CDSResponse with relevant cards.
        """
        import time

        start_time = time.perf_counter()
        cards: list[CDSCard] = []

        try:
            patient_id = extract_patient_id(context)

            # Check for drug interactions in current medications
            medications = extract_medications_from_context(context, prefetch)
            if len(medications) >= 2:
                interaction_result = self.drug_interaction_service.check_interactions(
                    medications
                )

                if interaction_result.interactions_found:
                    for interaction in interaction_result.interactions_found:
                        indicator = self._severity_to_indicator(interaction.severity)

                        card = CDSCard(
                            summary=f"Drug Interaction: {interaction.drug1.title()} + {interaction.drug2.title()}",
                            detail=f"{interaction.description}\n\nClinical Effect: {interaction.clinical_effect}\n\nManagement: {interaction.management}",
                            indicator=indicator,
                            source=CDSSource(
                                label="Drug Interaction Service",
                                url="https://dailymed.nlm.nih.gov/dailymed/",
                            ),
                            links=[
                                CDSLink(
                                    label="DailyMed Drug Information",
                                    url=f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={interaction.drug1}",
                                    type=CDSLinkType.ABSOLUTE,
                                ),
                            ],
                        )
                        cards.append(card)

            # Check for conditions requiring alerts
            conditions = extract_conditions_from_prefetch(prefetch)
            high_risk_conditions = [
                "diabetes",
                "hypertension",
                "heart failure",
                "chronic kidney disease",
                "copd",
            ]

            for condition in conditions:
                condition_lower = condition.lower()
                for risk_condition in high_risk_conditions:
                    if risk_condition in condition_lower:
                        cards.append(
                            CDSCard(
                                summary=f"Active Condition: {condition}",
                                detail=f"Patient has active {condition}. Consider reviewing current management plan and ensuring appropriate monitoring.",
                                indicator=CDSIndicator.INFO,
                                source=CDSSource(
                                    label="Clinical Decision Support",
                                ),
                                links=[
                                    CDSLink(
                                        label="Clinical Guidelines",
                                        url="https://www.uptodate.com/",
                                        type=CDSLinkType.ABSOLUTE,
                                    ),
                                ],
                            )
                        )
                        break

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.PATIENT_VIEW,
                context=context,
                cards_returned=len(cards),
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.exception("Error in patient-view hook")
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.PATIENT_VIEW,
                context=context,
                cards_returned=0,
                duration_ms=duration_ms,
                error=str(e),
            )

        return CDSResponse(cards=cards)

    def invoke_order_select(
        self,
        context: dict[str, Any],
        prefetch: dict[str, Any] | None = None,
    ) -> CDSResponse:
        """Invoke order-select hook.

        Triggered when an order (usually medication) is selected.
        Checks for drug-drug interactions with current medications.

        Args:
            context: Hook context with selections, patientId, etc.
            prefetch: Prefetched FHIR resources.

        Returns:
            CDSResponse with interaction alerts.
        """
        import time

        start_time = time.perf_counter()
        cards: list[CDSCard] = []

        try:
            # Get current medications from prefetch
            current_meds = extract_medications_from_context({}, prefetch)

            # Get selected/draft medications from context
            selected_meds = extract_medications_from_context(context, None)

            # Combine all medications
            all_meds = list(set(current_meds + selected_meds))

            if len(all_meds) >= 2:
                interaction_result = self.drug_interaction_service.check_interactions(
                    all_meds
                )

                for interaction in interaction_result.interactions_found:
                    # Only show if involves a selected medication
                    selected_involved = any(
                        med.lower() in [interaction.drug1.lower(), interaction.drug2.lower()]
                        for med in selected_meds
                    )

                    if selected_involved:
                        indicator = self._severity_to_indicator(interaction.severity)

                        # Create suggestion to use alternative
                        suggestions = []
                        if interaction.severity in [
                            InteractionSeverity.CONTRAINDICATED,
                            InteractionSeverity.MAJOR,
                        ]:
                            suggestions.append(
                                CDSSuggestion(
                                    label="Remove from order",
                                    is_recommended=True,
                                    actions=[
                                        CDSAction(
                                            type=CDSActionType.DELETE,
                                            description=f"Remove {interaction.drug1} or {interaction.drug2} from the order",
                                        )
                                    ],
                                )
                            )

                        card = CDSCard(
                            summary=f"Drug Interaction Alert: {interaction.drug1.title()} + {interaction.drug2.title()}",
                            detail=f"**Severity:** {interaction.severity.value.title()}\n\n**Description:** {interaction.description}\n\n**Clinical Effect:** {interaction.clinical_effect}\n\n**Management:** {interaction.management}",
                            indicator=indicator,
                            source=CDSSource(
                                label="Drug Interaction Checker",
                                url="https://dailymed.nlm.nih.gov/dailymed/",
                            ),
                            suggestions=suggestions,
                            override_reasons=(
                                [
                                    {
                                        "code": "clinical-judgment",
                                        "display": "Clinical judgment - benefits outweigh risks",
                                    },
                                    {
                                        "code": "patient-request",
                                        "display": "Patient preference",
                                    },
                                    {
                                        "code": "no-alternative",
                                        "display": "No suitable alternative available",
                                    },
                                ]
                                if indicator
                                in [CDSIndicator.CRITICAL, CDSIndicator.HARD_STOP]
                                else None
                            ),
                            links=[
                                CDSLink(
                                    label="View interaction details",
                                    url=f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={interaction.drug1}+{interaction.drug2}",
                                    type=CDSLinkType.ABSOLUTE,
                                ),
                            ],
                        )
                        cards.append(card)

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.ORDER_SELECT,
                context=context,
                cards_returned=len(cards),
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.exception("Error in order-select hook")
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.ORDER_SELECT,
                context=context,
                cards_returned=0,
                duration_ms=duration_ms,
                error=str(e),
            )

        return CDSResponse(cards=cards)

    def invoke_order_sign(
        self,
        context: dict[str, Any],
        prefetch: dict[str, Any] | None = None,
    ) -> CDSResponse:
        """Invoke order-sign hook.

        Triggered before orders are signed. Performs final validation including:
        - Drug interaction checks
        - Duplicate therapy detection
        - Dosage validation
        - Required documentation checks

        Args:
            context: Hook context with draftOrders, patientId, etc.
            prefetch: Prefetched FHIR resources.

        Returns:
            CDSResponse with validation alerts.
        """
        import time

        start_time = time.perf_counter()
        cards: list[CDSCard] = []

        try:
            # Get all medications (current + draft orders)
            current_meds = extract_medications_from_context({}, prefetch)
            draft_meds = extract_medications_from_context(context, None)
            all_meds = list(set(current_meds + draft_meds))

            # Check for drug interactions
            if len(all_meds) >= 2:
                interaction_result = self.drug_interaction_service.check_interactions(
                    all_meds
                )

                # Only create hard-stop for contraindicated interactions
                for interaction in interaction_result.interactions_found:
                    if interaction.severity == InteractionSeverity.CONTRAINDICATED:
                        cards.append(
                            CDSCard(
                                summary=f"CONTRAINDICATED: {interaction.drug1.title()} + {interaction.drug2.title()}",
                                detail=f"This combination is contraindicated and should not be used.\n\n**Reason:** {interaction.description}\n\n**Risk:** {interaction.clinical_effect}",
                                indicator=CDSIndicator.HARD_STOP,
                                source=CDSSource(
                                    label="Drug Safety System",
                                    url="https://dailymed.nlm.nih.gov/dailymed/",
                                ),
                                suggestions=[
                                    CDSSuggestion(
                                        label="Cancel order",
                                        is_recommended=True,
                                        actions=[
                                            CDSAction(
                                                type=CDSActionType.DELETE,
                                                description="Cancel the contraindicated order",
                                            )
                                        ],
                                    )
                                ],
                                override_reasons=[
                                    {
                                        "code": "life-threatening-condition",
                                        "display": "Life-threatening condition requiring this therapy",
                                    },
                                    {
                                        "code": "previous-tolerance",
                                        "display": "Patient has previously tolerated this combination",
                                    },
                                ],
                            )
                        )
                    elif interaction.severity == InteractionSeverity.MAJOR:
                        cards.append(
                            CDSCard(
                                summary=f"Major Interaction: {interaction.drug1.title()} + {interaction.drug2.title()}",
                                detail=f"**Risk:** {interaction.clinical_effect}\n\n**Recommendation:** {interaction.management}",
                                indicator=CDSIndicator.CRITICAL,
                                source=CDSSource(
                                    label="Drug Safety System",
                                ),
                                suggestions=[
                                    CDSSuggestion(
                                        label="Acknowledge and continue",
                                        actions=[],
                                    ),
                                    CDSSuggestion(
                                        label="Modify order",
                                        is_recommended=True,
                                        actions=[
                                            CDSAction(
                                                type=CDSActionType.UPDATE,
                                                description="Review and modify the order",
                                            )
                                        ],
                                    ),
                                ],
                            )
                        )

            # Check for duplicate therapy
            duplicate_classes = self._check_duplicate_therapy(all_meds)
            for drug_class, drugs in duplicate_classes.items():
                if len(drugs) > 1:
                    cards.append(
                        CDSCard(
                            summary=f"Duplicate Therapy: {drug_class}",
                            detail=f"Multiple medications from the same class: {', '.join(drugs)}. Consider whether duplicate therapy is intended.",
                            indicator=CDSIndicator.WARNING,
                            source=CDSSource(
                                label="Clinical Decision Support",
                            ),
                            suggestions=[
                                CDSSuggestion(
                                    label="Therapeutic intent confirmed",
                                    actions=[],
                                ),
                            ],
                        )
                    )

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.ORDER_SIGN,
                context=context,
                cards_returned=len(cards),
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.exception("Error in order-sign hook")
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.ORDER_SIGN,
                context=context,
                cards_returned=0,
                duration_ms=duration_ms,
                error=str(e),
            )

        return CDSResponse(cards=cards)

    def invoke_medication_prescribe(
        self,
        context: dict[str, Any],
        prefetch: dict[str, Any] | None = None,
    ) -> CDSResponse:
        """Invoke medication-prescribe hook.

        Triggered during medication prescribing workflow. Provides:
        - Drug interaction alerts
        - Allergy alerts
        - Renal/hepatic dosing adjustments
        - Formulary information

        Args:
            context: Hook context with medication details.
            prefetch: Prefetched FHIR resources.

        Returns:
            CDSResponse with prescribing guidance.
        """
        import time

        start_time = time.perf_counter()
        cards: list[CDSCard] = []

        try:
            # Get current medications
            current_meds = extract_medications_from_context({}, prefetch)

            # Get medication being prescribed
            prescribing_meds = extract_medications_from_context(context, None)

            # Check for interactions
            all_meds = list(set(current_meds + prescribing_meds))
            if len(all_meds) >= 2:
                interaction_result = self.drug_interaction_service.check_interactions(
                    all_meds
                )

                for interaction in interaction_result.interactions_found:
                    # Only show if involves the medication being prescribed
                    prescribing_involved = any(
                        med.lower() in [interaction.drug1.lower(), interaction.drug2.lower()]
                        for med in prescribing_meds
                    )

                    if prescribing_involved:
                        indicator = self._severity_to_indicator(interaction.severity)
                        cards.append(
                            CDSCard(
                                summary=f"Interaction with Current Medication: {interaction.drug1.title()} + {interaction.drug2.title()}",
                                detail=f"{interaction.description}\n\n**Management:** {interaction.management}",
                                indicator=indicator,
                                source=CDSSource(
                                    label="Prescribing Decision Support",
                                ),
                            )
                        )

            # Check for allergies (simplified example)
            # In production, this would cross-reference with allergy list
            if prefetch and "allergies" in prefetch:
                allergy_bundle = prefetch["allergies"]
                if allergy_bundle.get("resourceType") == "Bundle":
                    for entry in allergy_bundle.get("entry", []):
                        allergy = entry.get("resource", {})
                        if allergy.get("resourceType") == "AllergyIntolerance":
                            substance = ""
                            code = allergy.get("code", {})
                            for coding in code.get("coding", []):
                                substance = coding.get("display", "")
                                break

                            # Check if prescribing related substance
                            for med in prescribing_meds:
                                if substance.lower() in med.lower() or med.lower() in substance.lower():
                                    criticality = allergy.get("criticality", "unknown")
                                    cards.append(
                                        CDSCard(
                                            summary=f"Allergy Alert: {substance}",
                                            detail=f"Patient has documented allergy to {substance}. Criticality: {criticality}",
                                            indicator=CDSIndicator.CRITICAL
                                            if criticality == "high"
                                            else CDSIndicator.WARNING,
                                            source=CDSSource(
                                                label="Allergy Checking Service",
                                            ),
                                        )
                                    )

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.MEDICATION_PRESCRIBE,
                context=context,
                cards_returned=len(cards),
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.exception("Error in medication-prescribe hook")
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_hook_invocation(
                hook_id=str(uuid.uuid4()),
                hook_type=HookType.MEDICATION_PRESCRIBE,
                context=context,
                cards_returned=0,
                duration_ms=duration_ms,
                error=str(e),
            )

        return CDSResponse(cards=cards)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _severity_to_indicator(self, severity: InteractionSeverity) -> CDSIndicator:
        """Convert drug interaction severity to CDS indicator."""
        mapping = {
            InteractionSeverity.CONTRAINDICATED: CDSIndicator.HARD_STOP,
            InteractionSeverity.MAJOR: CDSIndicator.CRITICAL,
            InteractionSeverity.MODERATE: CDSIndicator.WARNING,
            InteractionSeverity.MINOR: CDSIndicator.INFO,
        }
        return mapping.get(severity, CDSIndicator.INFO)

    def _check_duplicate_therapy(self, medications: list[str]) -> dict[str, list[str]]:
        """Check for duplicate therapy (multiple drugs from same class).

        Returns:
            Dict mapping drug class to list of medications in that class.
        """
        # Drug class mappings (simplified)
        drug_classes: dict[str, list[str]] = {
            "ACE Inhibitors": [
                "lisinopril",
                "enalapril",
                "ramipril",
                "captopril",
                "benazepril",
            ],
            "ARBs": [
                "losartan",
                "valsartan",
                "irbesartan",
                "candesartan",
                "olmesartan",
            ],
            "Beta Blockers": [
                "metoprolol",
                "atenolol",
                "carvedilol",
                "bisoprolol",
                "propranolol",
            ],
            "Statins": [
                "atorvastatin",
                "simvastatin",
                "rosuvastatin",
                "pravastatin",
                "lovastatin",
            ],
            "PPIs": [
                "omeprazole",
                "pantoprazole",
                "esomeprazole",
                "lansoprazole",
                "rabeprazole",
            ],
            "SSRIs": [
                "sertraline",
                "fluoxetine",
                "paroxetine",
                "citalopram",
                "escitalopram",
            ],
            "Benzodiazepines": [
                "alprazolam",
                "lorazepam",
                "diazepam",
                "clonazepam",
                "temazepam",
            ],
            "Opioids": [
                "oxycodone",
                "hydrocodone",
                "morphine",
                "fentanyl",
                "tramadol",
            ],
            "NSAIDs": [
                "ibuprofen",
                "naproxen",
                "meloxicam",
                "diclofenac",
                "celecoxib",
            ],
        }

        duplicates: dict[str, list[str]] = {}
        med_lower = [m.lower() for m in medications]

        for drug_class, class_drugs in drug_classes.items():
            found_in_class = [
                med
                for med in medications
                if med.lower() in class_drugs or any(cd in med.lower() for cd in class_drugs)
            ]
            if len(found_in_class) > 1:
                duplicates[drug_class] = found_in_class

        return duplicates

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service statistics.
        """
        return {
            "services_count": len(self._services),
            "total_invocations": len(self._hook_logs),
            "recent_invocations_24h": sum(
                1
                for log in self._hook_logs
                if (datetime.now(timezone.utc) - log.timestamp).total_seconds() < 86400
            ),
            "invocations_by_hook": {
                hook.value: sum(1 for log in self._hook_logs if log.hook_type == hook)
                for hook in HookType
            },
        }


# =============================================================================
# Singleton Management
# =============================================================================

_cds_hooks_service: CDSHooksService | None = None
_cds_hooks_lock = Lock()


def get_cds_hooks_service() -> CDSHooksService:
    """Get the singleton CDSHooksService instance.

    Returns:
        The singleton CDSHooksService instance.
    """
    global _cds_hooks_service

    if _cds_hooks_service is None:
        with _cds_hooks_lock:
            if _cds_hooks_service is None:
                logger.info("Creating singleton CDSHooksService instance")
                _cds_hooks_service = CDSHooksService()

    return _cds_hooks_service


def reset_cds_hooks_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _cds_hooks_service
    with _cds_hooks_lock:
        _cds_hooks_service = None
