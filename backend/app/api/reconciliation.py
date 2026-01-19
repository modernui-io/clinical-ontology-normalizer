"""Medication Reconciliation API Endpoints.

Provides medication reconciliation services:
- Compare two medication lists for discrepancies
- Analyze single medication list for issues
- Retrieve reconciliation reports

Clinical Use Cases:
- Hospital admission/discharge reconciliation
- Care transition medication review
- Therapeutic duplicate detection
- High-risk medication monitoring
"""

import time
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError

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
