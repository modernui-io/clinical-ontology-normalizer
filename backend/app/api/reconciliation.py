"""Medication Reconciliation API Endpoints.

Provides medication reconciliation services:
- Create and manage reconciliation sessions
- Compare two medication lists for discrepancies
- Resolve discrepancies with audit trail
- Drug safety and interaction checking
- Generate reconciliation reports

Clinical Use Cases:
- Hospital admission/discharge reconciliation
- Care transition medication review
- Therapeutic duplicate detection
- High-risk medication monitoring
"""

from __future__ import annotations

import time
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError, ValidationError

router = APIRouter(prefix="/reconciliation", tags=["Medication Reconciliation"])


# ============================================================================
# Enums (mirroring service enums for API contract)
# ============================================================================


class DiscrepancyType(str, Enum):
    """Type of medication discrepancy."""

    ADDITION = "addition"
    DISCONTINUATION = "discontinuation"
    DOSE_CHANGE = "dose_change"
    FREQUENCY_CHANGE = "frequency_change"
    ROUTE_CHANGE = "route_change"
    THERAPEUTIC_DUPLICATION = "therapeutic_duplication"
    BRAND_GENERIC_SWAP = "brand_generic_swap"
    FORMULATION_CHANGE = "formulation_change"


class DiscrepancySeverity(str, Enum):
    """Severity level of a discrepancy."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class ReconciliationStatus(str, Enum):
    """Status of the reconciliation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REQUIRES_ACTION = "requires_action"


class ResolutionAction(str, Enum):
    """Action taken to resolve a discrepancy."""

    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"
    DEFER = "defer"


class ResolutionReason(str, Enum):
    """Reason for resolution action."""

    INTENDED_CHANGE = "intended_change"
    DOSING_ADJUSTMENT = "dosing_adjustment"
    THERAPEUTIC_SUBSTITUTION = "therapeutic_substitution"
    DISCONTINUE_DUPLICATE = "discontinue_duplicate"
    ADVERSE_REACTION = "adverse_reaction"
    COST_SUBSTITUTION = "cost_substitution"
    FORMULARY_CHANGE = "formulary_change"
    PATIENT_PREFERENCE = "patient_preference"
    CLINICAL_INDICATION = "clinical_indication"
    DOCUMENTATION_ERROR = "documentation_error"
    OTHER = "other"


# ============================================================================
# Request/Response Models
# ============================================================================


class MedicationInput(BaseModel):
    """Input model for a medication entry."""

    drug_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Medication name (brand or generic)",
    )
    dose: str = Field(
        default="",
        max_length=100,
        description="Dose amount (e.g., '10 mg', '500 mg')",
    )
    frequency: str = Field(
        default="",
        max_length=100,
        description="Dosing frequency (e.g., 'twice daily', 'BID', 'q6h')",
    )
    route: str = Field(
        default="",
        max_length=50,
        description="Administration route (e.g., 'oral', 'IV', 'topical')",
    )
    start_date: date | None = Field(
        default=None,
        description="Date medication was started",
    )
    end_date: date | None = Field(
        default=None,
        description="Date medication was stopped (if applicable)",
    )
    prescriber: str = Field(
        default="",
        max_length=200,
        description="Prescribing provider",
    )
    indication: str = Field(
        default="",
        max_length=500,
        description="Reason for medication",
    )
    is_prn: bool = Field(
        default=False,
        description="Whether this is an as-needed medication",
    )
    notes: str = Field(
        default="",
        max_length=1000,
        description="Additional notes",
    )


class MedicationOutput(BaseModel):
    """Output model for a medication with normalized data."""

    drug_name: str = Field(..., description="Original medication name")
    dose: str = Field(default="", description="Dose amount")
    frequency: str = Field(default="", description="Dosing frequency")
    route: str = Field(default="", description="Administration route")
    start_date: date | None = Field(default=None, description="Start date")
    end_date: date | None = Field(default=None, description="End date")
    prescriber: str = Field(default="", description="Prescribing provider")
    indication: str = Field(default="", description="Reason for medication")
    is_prn: bool = Field(default=False, description="As-needed medication")
    notes: str = Field(default="", description="Additional notes")

    # Normalized/computed fields
    normalized_name: str = Field(default="", description="Generic drug name")
    rxcui: str = Field(default="", description="RxNorm CUI if resolved")
    therapeutic_class: str = Field(default="", description="Drug class")
    is_high_risk: bool = Field(default=False, description="High-alert medication flag")


class MedicationMatchOutput(BaseModel):
    """Output model for a matched medication pair."""

    source_medication: MedicationOutput
    target_medication: MedicationOutput
    match_confidence: float = Field(
        ..., ge=0, le=1, description="Match confidence score"
    )
    match_type: str = Field(
        ..., description="Type of match (exact, generic, brand, fuzzy)"
    )
    has_changes: bool = Field(
        default=False, description="Whether there are differences"
    )


class DiscrepancyAlertOutput(BaseModel):
    """Output model for a discrepancy alert."""

    id: str = Field(..., description="Unique alert identifier")
    discrepancy_type: DiscrepancyType = Field(..., description="Type of discrepancy")
    severity: DiscrepancySeverity = Field(..., description="Severity level")
    description: str = Field(..., description="Human-readable description")
    clinical_significance: str = Field(
        ..., description="Clinical significance of the discrepancy"
    )
    recommended_action: str = Field(
        ..., description="Recommended clinical action"
    )
    medications_involved: list[MedicationOutput] = Field(
        default_factory=list, description="Medications involved in this discrepancy"
    )
    source_list_name: str = Field(default="", description="Source list name")
    target_list_name: str = Field(default="", description="Target list name")


class TherapeuticDuplicateOutput(BaseModel):
    """Output model for therapeutic duplication finding."""

    therapeutic_class: str = Field(..., description="Drug class with duplication")
    medications: list[MedicationOutput] = Field(
        ..., description="Medications in the same class"
    )
    severity: DiscrepancySeverity = Field(..., description="Severity level")
    clinical_rationale: str = Field(
        ..., description="Clinical significance explanation"
    )
    recommendation: str = Field(..., description="Recommended action")


class ReconciliationSummary(BaseModel):
    """Summary statistics for reconciliation."""

    total_source_medications: int = Field(
        ..., description="Total medications in source list"
    )
    total_target_medications: int = Field(
        ..., description="Total medications in target list"
    )
    total_matches: int = Field(..., description="Number of matched medications")
    total_additions: int = Field(..., description="New medications added")
    total_discontinuations: int = Field(..., description="Medications stopped")
    total_changes: int = Field(..., description="Medications with changes")
    total_alerts: int = Field(..., description="Total discrepancy alerts")
    high_risk_discrepancies: int = Field(
        ..., description="Number of high-severity discrepancies"
    )
    therapeutic_duplicates_count: int = Field(
        ..., description="Number of therapeutic duplications"
    )
    requires_pharmacist_review: bool = Field(
        ..., description="Whether pharmacist review is recommended"
    )


# ============================================================================
# Compare Endpoint Models
# ============================================================================


class CompareRequest(BaseModel):
    """Request to compare two medication lists."""

    source_medications: list[MedicationInput] = Field(
        ...,
        min_length=0,
        max_length=200,
        description="First medication list (e.g., admission medications)",
    )
    target_medications: list[MedicationInput] = Field(
        ...,
        min_length=0,
        max_length=200,
        description="Second medication list (e.g., discharge medications)",
    )
    source_list_name: str = Field(
        default="Source Medications",
        max_length=100,
        description="Display name for source list",
    )
    target_list_name: str = Field(
        default="Target Medications",
        max_length=100,
        description="Display name for target list",
    )


class CompareResponse(BaseModel):
    """Response from medication list comparison."""

    reconciliation_id: str = Field(..., description="Unique reconciliation identifier")
    source_list_name: str = Field(..., description="Source list name")
    target_list_name: str = Field(..., description="Target list name")
    reconciliation_timestamp: datetime = Field(
        ..., description="When reconciliation was performed"
    )
    status: ReconciliationStatus = Field(..., description="Reconciliation status")

    # Results
    matches: list[MedicationMatchOutput] = Field(
        default_factory=list, description="Medications that match between lists"
    )
    additions: list[MedicationOutput] = Field(
        default_factory=list, description="New medications in target list"
    )
    discontinuations: list[MedicationOutput] = Field(
        default_factory=list, description="Medications stopped from source list"
    )
    changes: list[MedicationMatchOutput] = Field(
        default_factory=list, description="Medications with changes"
    )
    alerts: list[DiscrepancyAlertOutput] = Field(
        default_factory=list, description="Discrepancy alerts"
    )
    therapeutic_duplicates: list[TherapeuticDuplicateOutput] = Field(
        default_factory=list, description="Therapeutic duplications found"
    )

    summary: ReconciliationSummary = Field(..., description="Summary statistics")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


# ============================================================================
# Analyze Endpoint Models
# ============================================================================


class AnalyzeRequest(BaseModel):
    """Request to analyze a single medication list."""

    medications: list[MedicationInput] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Medication list to analyze",
    )
    list_name: str = Field(
        default="Medication List",
        max_length=100,
        description="Display name for the list",
    )


class MedicationsByClassOutput(BaseModel):
    """Medications grouped by therapeutic class."""

    therapeutic_class: str = Field(..., description="Therapeutic class name")
    medications: list[MedicationOutput] = Field(
        ..., description="Medications in this class"
    )


class AnalyzeResponse(BaseModel):
    """Response from medication list analysis."""

    analysis_id: str = Field(..., description="Unique analysis identifier")
    list_name: str = Field(..., description="List name")
    analysis_timestamp: datetime = Field(..., description="When analysis was performed")
    total_medications: int = Field(..., description="Total medications analyzed")

    high_risk_medications: list[MedicationOutput] = Field(
        default_factory=list, description="High-alert medications identified"
    )
    therapeutic_duplicates: list[TherapeuticDuplicateOutput] = Field(
        default_factory=list, description="Therapeutic duplications found"
    )
    alerts: list[DiscrepancyAlertOutput] = Field(
        default_factory=list, description="Issues found in the list"
    )
    medications_by_class: list[MedicationsByClassOutput] = Field(
        default_factory=list, description="Medications grouped by therapeutic class"
    )

    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


# ============================================================================
# Report Endpoint Models
# ============================================================================


class ReconciliationReportResponse(BaseModel):
    """Response for retrieving a reconciliation report."""

    reconciliation_id: str = Field(..., description="Unique reconciliation identifier")
    source_list_name: str = Field(..., description="Source list name")
    target_list_name: str = Field(..., description="Target list name")
    reconciliation_timestamp: datetime = Field(
        ..., description="When reconciliation was performed"
    )
    status: ReconciliationStatus = Field(..., description="Reconciliation status")

    summary: ReconciliationSummary = Field(..., description="Summary statistics")
    alerts: list[DiscrepancyAlertOutput] = Field(
        default_factory=list, description="Discrepancy alerts"
    )
    therapeutic_duplicates: list[TherapeuticDuplicateOutput] = Field(
        default_factory=list, description="Therapeutic duplications"
    )

    # Additional metadata
    notes: str = Field(default="", description="Additional notes")
    reviewed_by: str = Field(default="", description="Reviewer name if reviewed")
    reviewed_at: datetime | None = Field(
        default=None, description="Review timestamp if reviewed"
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _convert_to_medication_entry(med_input: MedicationInput) -> Any:
    """Convert API input to service MedicationEntry."""
    from app.services.medication_reconciliation import MedicationEntry

    return MedicationEntry(
        drug_name=med_input.drug_name,
        dose=med_input.dose,
        frequency=med_input.frequency,
        route=med_input.route,
        start_date=med_input.start_date,
        end_date=med_input.end_date,
        prescriber=med_input.prescriber,
        indication=med_input.indication,
        is_prn=med_input.is_prn,
        notes=med_input.notes,
    )


def _convert_to_medication_output(med_entry: Any) -> MedicationOutput:
    """Convert service MedicationEntry to API output."""
    return MedicationOutput(
        drug_name=med_entry.drug_name,
        dose=med_entry.dose,
        frequency=med_entry.frequency,
        route=med_entry.route,
        start_date=med_entry.start_date,
        end_date=med_entry.end_date,
        prescriber=med_entry.prescriber,
        indication=med_entry.indication,
        is_prn=med_entry.is_prn,
        notes=med_entry.notes,
        normalized_name=med_entry.normalized_name,
        rxcui=med_entry.rxcui,
        therapeutic_class=med_entry.therapeutic_class,
        is_high_risk=med_entry.is_high_risk,
    )


def _convert_match(match: Any) -> MedicationMatchOutput:
    """Convert service MedicationMatch to API output."""
    return MedicationMatchOutput(
        source_medication=_convert_to_medication_output(match.source_medication),
        target_medication=_convert_to_medication_output(match.target_medication),
        match_confidence=match.match_confidence,
        match_type=match.match_type,
        has_changes=match.has_changes,
    )


def _convert_alert(alert: Any) -> DiscrepancyAlertOutput:
    """Convert service DiscrepancyAlert to API output."""
    return DiscrepancyAlertOutput(
        id=alert.id,
        discrepancy_type=DiscrepancyType(alert.discrepancy_type.value),
        severity=DiscrepancySeverity(alert.severity.value),
        description=alert.description,
        clinical_significance=alert.clinical_significance,
        recommended_action=alert.recommended_action,
        medications_involved=[
            _convert_to_medication_output(m) for m in alert.medications_involved
        ],
        source_list_name=alert.source_list_name,
        target_list_name=alert.target_list_name,
    )


def _convert_duplicate(dup: Any) -> TherapeuticDuplicateOutput:
    """Convert service TherapeuticDuplicate to API output."""
    return TherapeuticDuplicateOutput(
        therapeutic_class=dup.therapeutic_class,
        medications=[_convert_to_medication_output(m) for m in dup.medications],
        severity=DiscrepancySeverity(dup.severity.value),
        clinical_rationale=dup.clinical_rationale,
        recommendation=dup.recommendation,
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/compare",
    response_model=CompareResponse,
    summary="Compare two medication lists",
    description="Compare source and target medication lists to identify discrepancies.",
    responses={
        200: {"description": "Reconciliation completed successfully"},
        500: {"description": "Internal server error"},
    },
)
async def compare_medication_lists(request: CompareRequest) -> CompareResponse:
    """Compare two medication lists for reconciliation.

    This endpoint compares a source medication list (e.g., home medications,
    admission medications) against a target list (e.g., discharge medications,
    inpatient medications) and identifies:

    - **Matches**: Medications present in both lists
    - **Additions**: New medications in the target list
    - **Discontinuations**: Medications stopped from the source list
    - **Changes**: Dose, frequency, or route changes
    - **Therapeutic duplicates**: Multiple drugs in the same class
    - **High-risk discrepancies**: Issues with high-alert medications

    Args:
        request: Source and target medication lists to compare.

    Returns:
        CompareResponse with all reconciliation findings.
    """
    start_time = time.perf_counter()

    try:
        from app.services.medication_reconciliation import get_medication_reconciliation_service

        service = get_medication_reconciliation_service()

        # Convert inputs to service models
        source_entries = [_convert_to_medication_entry(m) for m in request.source_medications]
        target_entries = [_convert_to_medication_entry(m) for m in request.target_medications]

        # Perform reconciliation
        result = service.compare_medication_lists(
            source_list=source_entries,
            target_list=target_entries,
            source_name=request.source_list_name,
            target_name=request.target_list_name,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Build summary
        summary = ReconciliationSummary(
            total_source_medications=result.total_source_medications,
            total_target_medications=result.total_target_medications,
            total_matches=len(result.matches),
            total_additions=len(result.additions),
            total_discontinuations=len(result.discontinuations),
            total_changes=len(result.changes),
            total_alerts=len(result.alerts),
            high_risk_discrepancies=result.high_risk_discrepancies,
            therapeutic_duplicates_count=len(result.therapeutic_duplicates),
            requires_pharmacist_review=result.requires_pharmacist_review,
        )

        return CompareResponse(
            reconciliation_id=result.id,
            source_list_name=result.source_list_name,
            target_list_name=result.target_list_name,
            reconciliation_timestamp=result.reconciliation_timestamp,
            status=ReconciliationStatus(result.status.value),
            matches=[_convert_match(m) for m in result.matches],
            additions=[_convert_to_medication_output(m) for m in result.additions],
            discontinuations=[_convert_to_medication_output(m) for m in result.discontinuations],
            changes=[_convert_match(m) for m in result.changes],
            alerts=[_convert_alert(a) for a in result.alerts],
            therapeutic_duplicates=[_convert_duplicate(d) for d in result.therapeutic_duplicates],
            summary=summary,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Medication reconciliation failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze a medication list for issues",
    description="Analyze a single medication list for therapeutic duplicates and other issues.",
    responses={
        200: {"description": "Analysis completed successfully"},
        500: {"description": "Internal server error"},
    },
)
async def analyze_medication_list(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a single medication list for potential issues.

    This endpoint analyzes a medication list to identify:

    - **High-risk medications**: High-alert medications requiring special attention
    - **Therapeutic duplicates**: Multiple drugs in the same therapeutic class
    - **Medications by class**: Organization by therapeutic category

    Use this for reviewing a patient's current medication list without comparing
    to another list.

    Args:
        request: Medication list to analyze.

    Returns:
        AnalyzeResponse with analysis findings.
    """
    start_time = time.perf_counter()

    try:
        from app.services.medication_reconciliation import get_medication_reconciliation_service

        service = get_medication_reconciliation_service()

        # Convert inputs to service models
        entries = [_convert_to_medication_entry(m) for m in request.medications]

        # Perform analysis
        result = service.analyze_medication_list(
            medications=entries,
            list_name=request.list_name,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Convert medications by class to output format
        meds_by_class = [
            MedicationsByClassOutput(
                therapeutic_class=class_name,
                medications=[_convert_to_medication_output(m) for m in meds],
            )
            for class_name, meds in result.medications_by_class.items()
        ]

        return AnalyzeResponse(
            analysis_id=result.id,
            list_name=result.list_name,
            analysis_timestamp=result.analysis_timestamp,
            total_medications=result.total_medications,
            high_risk_medications=[
                _convert_to_medication_output(m) for m in result.high_risk_medications
            ],
            therapeutic_duplicates=[
                _convert_duplicate(d) for d in result.therapeutic_duplicates
            ],
            alerts=[_convert_alert(a) for a in result.alerts],
            medications_by_class=meds_by_class,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Medication analysis failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/report/{reconciliation_id}",
    response_model=ReconciliationReportResponse,
    summary="Get reconciliation report",
    description="Retrieve a previously generated reconciliation report.",
    responses={
        200: {"description": "Report retrieved successfully"},
        404: {"description": "Reconciliation not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_reconciliation_report(reconciliation_id: str) -> ReconciliationReportResponse:
    """Retrieve a stored reconciliation report.

    Retrieves a previously generated reconciliation report by its ID.
    Reports are stored in memory and available for retrieval during the
    service's lifetime.

    Args:
        reconciliation_id: Unique identifier of the reconciliation.

    Returns:
        ReconciliationReportResponse with the report details.

    Raises:
        404: If the reconciliation report is not found.
    """
    try:
        from app.services.medication_reconciliation import get_medication_reconciliation_service

        service = get_medication_reconciliation_service()

        result = service.get_reconciliation_report(reconciliation_id)

        if result is None:
            raise NotFoundError(
                message=f"Reconciliation report not found: {reconciliation_id}",
                error_code=ErrorCode.NOT_FOUND,
            )

        # Build summary
        summary = ReconciliationSummary(
            total_source_medications=result.total_source_medications,
            total_target_medications=result.total_target_medications,
            total_matches=len(result.matches),
            total_additions=len(result.additions),
            total_discontinuations=len(result.discontinuations),
            total_changes=len(result.changes),
            total_alerts=len(result.alerts),
            high_risk_discrepancies=result.high_risk_discrepancies,
            therapeutic_duplicates_count=len(result.therapeutic_duplicates),
            requires_pharmacist_review=result.requires_pharmacist_review,
        )

        return ReconciliationReportResponse(
            reconciliation_id=result.id,
            source_list_name=result.source_list_name,
            target_list_name=result.target_list_name,
            reconciliation_timestamp=result.reconciliation_timestamp,
            status=ReconciliationStatus(result.status.value),
            summary=summary,
            alerts=[_convert_alert(a) for a in result.alerts],
            therapeutic_duplicates=[_convert_duplicate(d) for d in result.therapeutic_duplicates],
            notes=result.notes,
            reviewed_by=result.reviewed_by,
            reviewed_at=result.reviewed_at,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to retrieve reconciliation report: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/stats",
    summary="Get service statistics",
    description="Get statistics about the medication reconciliation service.",
    responses={
        200: {"description": "Statistics retrieved successfully"},
    },
)
async def get_reconciliation_stats() -> dict[str, Any]:
    """Get statistics about the medication reconciliation service.

    Returns information about the service including:
    - Number of stored reconciliations
    - Whether RxNorm integration is enabled
    - Number of therapeutic classes tracked
    - Number of high-risk categories monitored

    Returns:
        Dictionary with service statistics.
    """
    from app.services.medication_reconciliation import get_medication_reconciliation_service

    service = get_medication_reconciliation_service()
    return service.get_stats()


# ============================================================================
# Session-based Reconciliation Models
# ============================================================================


class DrugInteractionWarningOutput(BaseModel):
    """Output model for drug interaction warning."""

    drug1: str = Field(..., description="First drug in interaction")
    drug2: str = Field(..., description="Second drug in interaction")
    severity: str = Field(..., description="Interaction severity")
    description: str = Field(..., description="Description of interaction")
    clinical_effect: str = Field(..., description="Clinical effect")
    management: str = Field(..., description="Management recommendation")


class DrugSafetyWarningOutput(BaseModel):
    """Output model for drug safety warning."""

    drug_name: str = Field(..., description="Drug name")
    warning_type: str = Field(..., description="Type of warning (black_box, allergy, high_risk)")
    severity: str = Field(..., description="Severity level")
    description: str = Field(..., description="Warning description")
    recommended_action: str = Field(..., description="Recommended action")


class DiscrepancyResolutionOutput(BaseModel):
    """Output model for discrepancy resolution."""

    id: str = Field(..., description="Discrepancy ID")
    action: ResolutionAction = Field(..., description="Action taken")
    reason: ResolutionReason = Field(..., description="Reason for action")
    reason_text: str = Field(default="", description="Free-text reason")
    resolved_by: str = Field(default="", description="User who resolved")
    resolved_at: datetime | None = Field(default=None, description="When resolved")
    notes: str = Field(default="", description="Additional notes")


class CreateSessionRequest(BaseModel):
    """Request to create a new reconciliation session."""

    source_medications: list[MedicationInput] = Field(
        ...,
        min_length=0,
        max_length=200,
        description="Source medication list (e.g., home medications)",
    )
    target_medications: list[MedicationInput] = Field(
        ...,
        min_length=0,
        max_length=200,
        description="Target medication list (e.g., discharge medications)",
    )
    source_list_name: str = Field(
        default="Home Medications",
        max_length=100,
        description="Display name for source list",
    )
    target_list_name: str = Field(
        default="Discharge Medications",
        max_length=100,
        description="Display name for target list",
    )
    patient_id: str = Field(
        default="",
        max_length=100,
        description="Patient identifier",
    )
    encounter_id: str = Field(
        default="",
        max_length=100,
        description="Encounter identifier",
    )
    created_by: str = Field(
        default="",
        max_length=200,
        description="User creating the session",
    )
    patient_allergies: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="List of patient allergies for cross-reference",
    )


class SessionSummary(BaseModel):
    """Summary of a reconciliation session."""

    id: str = Field(..., description="Session identifier")
    patient_id: str = Field(default="", description="Patient identifier")
    encounter_id: str = Field(default="", description="Encounter identifier")
    status: ReconciliationStatus = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str = Field(default="", description="User who created")
    source_list_name: str = Field(..., description="Source list name")
    target_list_name: str = Field(..., description="Target list name")
    source_count: int = Field(..., description="Source medication count")
    target_count: int = Field(..., description="Target medication count")
    total_discrepancies: int = Field(..., description="Total discrepancies")
    unresolved_count: int = Field(..., description="Unresolved discrepancies")
    high_risk_unresolved: int = Field(..., description="High-risk unresolved")
    interaction_count: int = Field(..., description="Drug interaction warnings")
    safety_warning_count: int = Field(..., description="Safety warnings")


class SessionResponse(BaseModel):
    """Full response for a reconciliation session."""

    id: str = Field(..., description="Session identifier")
    patient_id: str = Field(default="", description="Patient identifier")
    encounter_id: str = Field(default="", description="Encounter identifier")
    status: ReconciliationStatus = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str = Field(default="", description="User who created")
    assigned_to: str = Field(default="", description="User assigned to")
    source_list_name: str = Field(..., description="Source list name")
    target_list_name: str = Field(..., description="Target list name")

    # Medications
    source_medications: list[MedicationOutput] = Field(
        default_factory=list, description="Source medications"
    )
    target_medications: list[MedicationOutput] = Field(
        default_factory=list, description="Target medications"
    )
    reconciled_medications: list[MedicationOutput] = Field(
        default_factory=list, description="Final reconciled list"
    )

    # Reconciliation result
    matches: list[MedicationMatchOutput] = Field(
        default_factory=list, description="Matched medications"
    )
    additions: list[MedicationOutput] = Field(
        default_factory=list, description="Added medications"
    )
    discontinuations: list[MedicationOutput] = Field(
        default_factory=list, description="Discontinued medications"
    )
    changes: list[MedicationMatchOutput] = Field(
        default_factory=list, description="Changed medications"
    )
    alerts: list[DiscrepancyAlertOutput] = Field(
        default_factory=list, description="Discrepancy alerts"
    )
    therapeutic_duplicates: list[TherapeuticDuplicateOutput] = Field(
        default_factory=list, description="Therapeutic duplications"
    )

    # Resolutions
    resolutions: list[DiscrepancyResolutionOutput] = Field(
        default_factory=list, description="Discrepancy resolutions"
    )

    # Safety
    interaction_warnings: list[DrugInteractionWarningOutput] = Field(
        default_factory=list, description="Drug interaction warnings"
    )
    safety_warnings: list[DrugSafetyWarningOutput] = Field(
        default_factory=list, description="Drug safety warnings"
    )
    patient_allergies: list[str] = Field(
        default_factory=list, description="Patient allergies"
    )

    # Summary
    summary: ReconciliationSummary = Field(..., description="Summary statistics")

    # Completion
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    completed_by: str = Field(default="", description="User who completed")
    completion_notes: str = Field(default="", description="Completion notes")


class ResolveDiscrepancyRequest(BaseModel):
    """Request to resolve a discrepancy."""

    discrepancy_id: str = Field(
        ...,
        min_length=1,
        description="ID of the discrepancy to resolve",
    )
    action: ResolutionAction = Field(
        ...,
        description="Action to take (accept, reject, modify, defer)",
    )
    reason: ResolutionReason = Field(
        ...,
        description="Reason for the action",
    )
    reason_text: str = Field(
        default="",
        max_length=500,
        description="Optional free-text reason",
    )
    resolved_by: str = Field(
        default="",
        max_length=200,
        description="User resolving the discrepancy",
    )
    notes: str = Field(
        default="",
        max_length=1000,
        description="Additional notes",
    )


class CompleteSessionRequest(BaseModel):
    """Request to complete a reconciliation session."""

    completed_by: str = Field(
        default="",
        max_length=200,
        description="User completing the session",
    )
    notes: str = Field(
        default="",
        max_length=2000,
        description="Completion notes",
    )
    force: bool = Field(
        default=False,
        description="Force completion even with unresolved discrepancies",
    )


# ============================================================================
# Session Helper Functions
# ============================================================================


def _convert_session_to_response(session: Any) -> SessionResponse:
    """Convert service ReconciliationSession to API response."""
    result = session.reconciliation_result

    # Convert medications
    source_meds = [_convert_to_medication_output(m) for m in session.source_medications]
    target_meds = [_convert_to_medication_output(m) for m in session.target_medications]
    reconciled_meds = [_convert_to_medication_output(m) for m in session.reconciled_medications]

    # Convert result components
    matches = [_convert_match(m) for m in result.matches] if result else []
    additions = [_convert_to_medication_output(m) for m in result.additions] if result else []
    discontinuations = [_convert_to_medication_output(m) for m in result.discontinuations] if result else []
    changes = [_convert_match(m) for m in result.changes] if result else []
    alerts = [_convert_alert(a) for a in result.alerts] if result else []
    therapeutic_duplicates = [_convert_duplicate(d) for d in result.therapeutic_duplicates] if result else []

    # Convert resolutions
    resolutions = [
        DiscrepancyResolutionOutput(
            id=r.id,
            action=ResolutionAction(r.action.value),
            reason=ResolutionReason(r.reason.value),
            reason_text=r.reason_text,
            resolved_by=r.resolved_by,
            resolved_at=r.resolved_at,
            notes=r.notes,
        )
        for r in session.resolutions.values()
    ]

    # Convert safety warnings
    interaction_warnings = [
        DrugInteractionWarningOutput(
            drug1=w.drug1,
            drug2=w.drug2,
            severity=w.severity,
            description=w.description,
            clinical_effect=w.clinical_effect,
            management=w.management,
        )
        for w in session.interaction_warnings
    ]

    safety_warnings = [
        DrugSafetyWarningOutput(
            drug_name=w.drug_name,
            warning_type=w.warning_type,
            severity=w.severity,
            description=w.description,
            recommended_action=w.recommended_action,
        )
        for w in session.safety_warnings
    ]

    # Build summary
    summary = ReconciliationSummary(
        total_source_medications=len(session.source_medications),
        total_target_medications=len(session.target_medications),
        total_matches=len(matches),
        total_additions=len(additions),
        total_discontinuations=len(discontinuations),
        total_changes=len(changes),
        total_alerts=len(alerts),
        high_risk_discrepancies=result.high_risk_discrepancies if result else 0,
        therapeutic_duplicates_count=len(therapeutic_duplicates),
        requires_pharmacist_review=result.requires_pharmacist_review if result else False,
    )

    return SessionResponse(
        id=session.id,
        patient_id=session.patient_id,
        encounter_id=session.encounter_id,
        status=ReconciliationStatus(session.status.value),
        created_at=session.created_at,
        updated_at=session.updated_at,
        created_by=session.created_by,
        assigned_to=session.assigned_to,
        source_list_name=session.source_list_name,
        target_list_name=session.target_list_name,
        source_medications=source_meds,
        target_medications=target_meds,
        reconciled_medications=reconciled_meds,
        matches=matches,
        additions=additions,
        discontinuations=discontinuations,
        changes=changes,
        alerts=alerts,
        therapeutic_duplicates=therapeutic_duplicates,
        resolutions=resolutions,
        interaction_warnings=interaction_warnings,
        safety_warnings=safety_warnings,
        patient_allergies=session.patient_allergies,
        summary=summary,
        completed_at=session.completed_at,
        completed_by=session.completed_by,
        completion_notes=session.completion_notes,
    )


def _convert_session_to_summary(session: Any) -> SessionSummary:
    """Convert service ReconciliationSession to summary."""
    result = session.reconciliation_result

    return SessionSummary(
        id=session.id,
        patient_id=session.patient_id,
        encounter_id=session.encounter_id,
        status=ReconciliationStatus(session.status.value),
        created_at=session.created_at,
        updated_at=session.updated_at,
        created_by=session.created_by,
        source_list_name=session.source_list_name,
        target_list_name=session.target_list_name,
        source_count=len(session.source_medications),
        target_count=len(session.target_medications),
        total_discrepancies=len(result.alerts) if result else 0,
        unresolved_count=session.get_unresolved_count(),
        high_risk_unresolved=session.get_high_risk_unresolved(),
        interaction_count=len(session.interaction_warnings),
        safety_warning_count=len(session.safety_warnings),
    )


# ============================================================================
# Session Endpoints
# ============================================================================


@router.post(
    "/sessions",
    response_model=SessionResponse,
    summary="Create reconciliation session",
    description="Create a new medication reconciliation session.",
    responses={
        200: {"description": "Session created successfully"},
        500: {"description": "Internal server error"},
    },
)
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    """Create a new medication reconciliation session.

    Creates a session with two medication lists and automatically:
    - Compares the lists for discrepancies
    - Checks for drug interactions
    - Checks drug safety and allergies
    - Identifies high-risk medications

    The session can then be used to resolve discrepancies and generate
    a final reconciled medication list.

    Args:
        request: Session creation request with medications.

    Returns:
        SessionResponse with full session details.
    """
    start_time = time.perf_counter()

    try:
        from app.services.medication_reconciliation import (
            get_medication_reconciliation_service,
            MedicationEntry,
        )

        service = get_medication_reconciliation_service()

        # Convert inputs
        source_entries = [
            MedicationEntry(
                drug_name=m.drug_name,
                dose=m.dose,
                frequency=m.frequency,
                route=m.route,
                start_date=m.start_date,
                end_date=m.end_date,
                prescriber=m.prescriber,
                indication=m.indication,
                is_prn=m.is_prn,
                notes=m.notes,
            )
            for m in request.source_medications
        ]

        target_entries = [
            MedicationEntry(
                drug_name=m.drug_name,
                dose=m.dose,
                frequency=m.frequency,
                route=m.route,
                start_date=m.start_date,
                end_date=m.end_date,
                prescriber=m.prescriber,
                indication=m.indication,
                is_prn=m.is_prn,
                notes=m.notes,
            )
            for m in request.target_medications
        ]

        # Create session
        session = service.create_session(
            source_medications=source_entries,
            target_medications=target_entries,
            source_name=request.source_list_name,
            target_name=request.target_list_name,
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            created_by=request.created_by,
            patient_allergies=request.patient_allergies,
        )

        return _convert_session_to_response(session)

    except Exception as e:
        raise InternalError(
            message=f"Failed to create reconciliation session: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/sessions",
    response_model=list[SessionSummary],
    summary="List reconciliation sessions",
    description="List reconciliation sessions with optional filters.",
    responses={
        200: {"description": "Sessions retrieved successfully"},
    },
)
async def list_sessions(
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    status: ReconciliationStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum sessions to return"),
) -> list[SessionSummary]:
    """List reconciliation sessions with optional filters.

    Args:
        patient_id: Filter by patient ID
        status: Filter by session status
        limit: Maximum sessions to return

    Returns:
        List of session summaries.
    """
    from app.services.medication_reconciliation import (
        get_medication_reconciliation_service,
        ReconciliationStatus as ServiceStatus,
    )

    service = get_medication_reconciliation_service()

    service_status = None
    if status:
        service_status = ServiceStatus(status.value)

    sessions = service.list_sessions(
        patient_id=patient_id,
        status=service_status,
        limit=limit,
    )

    return [_convert_session_to_summary(s) for s in sessions]


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get reconciliation session",
    description="Get full details of a reconciliation session.",
    responses={
        200: {"description": "Session retrieved successfully"},
        404: {"description": "Session not found"},
    },
)
async def get_session(session_id: str) -> SessionResponse:
    """Get full details of a reconciliation session.

    Args:
        session_id: Session identifier

    Returns:
        SessionResponse with full session details.
    """
    from app.services.medication_reconciliation import get_medication_reconciliation_service

    service = get_medication_reconciliation_service()
    session = service.get_session(session_id)

    if not session:
        raise NotFoundError(
            message=f"Session not found: {session_id}",
            error_code=ErrorCode.NOT_FOUND,
        )

    return _convert_session_to_response(session)


@router.post(
    "/sessions/{session_id}/resolve",
    response_model=SessionResponse,
    summary="Resolve discrepancy",
    description="Resolve a discrepancy in a reconciliation session.",
    responses={
        200: {"description": "Discrepancy resolved successfully"},
        404: {"description": "Session not found"},
        400: {"description": "Invalid request"},
    },
)
async def resolve_discrepancy(
    session_id: str,
    request: ResolveDiscrepancyRequest,
) -> SessionResponse:
    """Resolve a discrepancy in a reconciliation session.

    Records the resolution action and reason for audit purposes.
    Updates the session status based on remaining unresolved discrepancies.

    Args:
        session_id: Session identifier
        request: Resolution details

    Returns:
        Updated SessionResponse.
    """
    from app.services.medication_reconciliation import (
        get_medication_reconciliation_service,
        ResolutionAction as ServiceAction,
        ResolutionReason as ServiceReason,
    )

    service = get_medication_reconciliation_service()

    session = service.resolve_discrepancy(
        session_id=session_id,
        discrepancy_id=request.discrepancy_id,
        action=ServiceAction(request.action.value),
        reason=ServiceReason(request.reason.value),
        reason_text=request.reason_text,
        resolved_by=request.resolved_by,
        notes=request.notes,
    )

    if not session:
        raise NotFoundError(
            message=f"Session not found: {session_id}",
            error_code=ErrorCode.NOT_FOUND,
        )

    return _convert_session_to_response(session)


@router.post(
    "/sessions/{session_id}/complete",
    response_model=SessionResponse,
    summary="Complete reconciliation session",
    description="Complete a reconciliation session and generate final list.",
    responses={
        200: {"description": "Session completed successfully"},
        404: {"description": "Session not found"},
        400: {"description": "Cannot complete - unresolved discrepancies"},
    },
)
async def complete_session(
    session_id: str,
    request: CompleteSessionRequest,
) -> SessionResponse:
    """Complete a reconciliation session.

    Generates the final reconciled medication list based on all resolutions.
    Re-checks drug interactions and safety for the final list.

    Args:
        session_id: Session identifier
        request: Completion details

    Returns:
        Completed SessionResponse.
    """
    from app.services.medication_reconciliation import get_medication_reconciliation_service

    service = get_medication_reconciliation_service()

    session = service.complete_session(
        session_id=session_id,
        completed_by=request.completed_by,
        notes=request.notes,
        force=request.force,
    )

    if not session:
        # Check if session exists
        existing = service.get_session(session_id)
        if not existing:
            raise NotFoundError(
                message=f"Session not found: {session_id}",
                error_code=ErrorCode.NOT_FOUND,
            )
        else:
            raise ValidationError(
                message=f"Cannot complete session: {existing.get_unresolved_count()} unresolved discrepancies",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

    return _convert_session_to_response(session)


@router.get(
    "/sessions/{session_id}/report",
    summary="Generate reconciliation report",
    description="Generate a detailed reconciliation report for a session.",
    responses={
        200: {"description": "Report generated successfully"},
        404: {"description": "Session not found"},
    },
)
async def get_session_report(session_id: str) -> dict[str, Any]:
    """Generate a detailed reconciliation report.

    Produces a comprehensive report suitable for documentation
    and compliance purposes.

    Args:
        session_id: Session identifier

    Returns:
        Dictionary with full report data.
    """
    from app.services.medication_reconciliation import get_medication_reconciliation_service

    service = get_medication_reconciliation_service()
    report = service.generate_report(session_id)

    if not report:
        raise NotFoundError(
            message=f"Session not found: {session_id}",
            error_code=ErrorCode.NOT_FOUND,
        )

    return report
