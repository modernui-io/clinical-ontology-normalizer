"""Patient Timeline Visualization API Endpoints.

Provides endpoints for building and querying patient timelines:
- Build complete patient timeline with events
- Get timeline summary with key statistics
- Query filtered events with date ranges and types
- Analyze care gaps and overdue items

Supports clinical decision support and care coordination workflows.
"""

import time
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError

router = APIRouter(prefix="/timeline", tags=["Patient Timeline"])


# ============================================================================
# Enums and Types
# ============================================================================


class TimelineEventTypeAPI(str, Enum):
    """Types of timeline events for API."""

    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    MEDICATION_START = "medication_start"
    MEDICATION_STOP = "medication_stop"
    LAB_RESULT = "lab_result"
    VITAL_SIGN = "vital_sign"
    IMAGING = "imaging"
    HOSPITALIZATION = "hospitalization"
    SURGERY = "surgery"
    VACCINATION = "vaccination"
    ENCOUNTER = "encounter"
    REFERRAL = "referral"
    ALLERGY = "allergy"
    PROBLEM_ONSET = "problem_onset"
    PROBLEM_RESOLVED = "problem_resolved"


class EventSeverityAPI(str, Enum):
    """Severity levels for API."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GapTypeAPI(str, Enum):
    """Types of care gaps for API."""

    OVERDUE_SCREENING = "overdue_screening"
    MISSED_FOLLOWUP = "missed_followup"
    MEDICATION_GAP = "medication_gap"
    LAB_MONITORING = "lab_monitoring"
    IMMUNIZATION_DUE = "immunization_due"
    REFERRAL_PENDING = "referral_pending"
    CHRONIC_CARE_GAP = "chronic_care_gap"


class GapPriorityAPI(str, Enum):
    """Gap priority levels for API."""

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================================
# Request/Response Models
# ============================================================================


class PatientDataInput(BaseModel):
    """Patient clinical data input for timeline building."""

    demographics: dict = Field(
        ...,
        description="Demographics: {age, gender, dob}",
        json_schema_extra={"example": {"age": 55, "gender": "M", "dob": "1969-05-15"}}
    )
    diagnoses: list[dict] = Field(
        default_factory=list,
        description="Diagnoses: [{code, date, description, status}]",
        json_schema_extra={"example": [{"code": "E11.9", "date": "2024-01-15", "description": "Type 2 diabetes", "status": "active"}]}
    )
    procedures: list[dict] = Field(
        default_factory=list,
        description="Procedures: [{code, date, description}]",
        json_schema_extra={"example": [{"code": "92014", "date": "2024-03-20", "description": "Eye exam"}]}
    )
    labs: list[dict] = Field(
        default_factory=list,
        description="Labs: [{name, value, date, loinc, unit, reference_range}]",
        json_schema_extra={"example": [{"name": "HbA1c", "value": 7.2, "date": "2024-06-01", "loinc": "4548-4", "unit": "%"}]}
    )
    medications: list[dict] = Field(
        default_factory=list,
        description="Medications: [{name, rxnorm, start_date, end_date, dose}]",
        json_schema_extra={"example": [{"name": "Metformin", "rxnorm": "6809", "start_date": "2024-01-01", "dose": "500mg"}]}
    )
    vitals: list[dict] = Field(
        default_factory=list,
        description="Vitals: [{name, value, date, unit}]",
        json_schema_extra={"example": [{"name": "systolic_bp", "value": 135, "date": "2024-06-15", "unit": "mmHg"}]}
    )
    encounters: list[dict] = Field(
        default_factory=list,
        description="Encounters: [{id, date, type, provider, facility}]",
        json_schema_extra={"example": [{"id": "enc_123", "date": "2024-06-15", "type": "Office visit"}]}
    )
    immunizations: list[dict] = Field(
        default_factory=list,
        description="Immunizations: [{vaccine, date, cvx, dose}]",
        json_schema_extra={"example": [{"vaccine": "Influenza", "date": "2024-10-01", "cvx": "158"}]}
    )


class TimelineFilterInput(BaseModel):
    """Filter criteria for timeline queries."""

    date_from: date | None = Field(None, description="Start date for filtering")
    date_to: date | None = Field(None, description="End date for filtering")
    event_types: list[TimelineEventTypeAPI] | None = Field(None, description="Filter by event types")
    severities: list[EventSeverityAPI] | None = Field(None, description="Filter by severity levels")
    search_text: str | None = Field(None, description="Text search in descriptions")
    exclude_routine: bool = Field(False, description="Exclude low/info severity events")
    limit: int | None = Field(None, ge=1, le=1000, description="Maximum events to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class TimelineEventResponse(BaseModel):
    """A single timeline event."""

    id: str = Field(..., description="Unique event identifier")
    event_date: date = Field(..., description="Date of the event")
    event_type: TimelineEventTypeAPI = Field(..., description="Type of event")
    description: str = Field(..., description="Event description")
    severity: EventSeverityAPI = Field(..., description="Event severity")

    code: str | None = Field(None, description="Clinical code (ICD-10, CPT, LOINC, etc.)")
    code_system: str | None = Field(None, description="Code system identifier")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional event details")

    source_encounter: str | None = Field(None, description="Source encounter ID")
    provider: str | None = Field(None, description="Provider name")
    facility: str | None = Field(None, description="Facility name")


class TimelineSummaryResponse(BaseModel):
    """Summary of a patient timeline."""

    event_counts_by_type: dict[str, int] = Field(default_factory=dict, description="Event counts by type")
    key_events: list[TimelineEventResponse] = Field(default_factory=list, description="Key clinical events")
    active_conditions: list[dict] = Field(default_factory=list, description="Current active conditions")
    current_medications: list[dict] = Field(default_factory=list, description="Current medications")
    recent_labs: list[dict] = Field(default_factory=list, description="Recent lab results (30 days)")

    hospitalizations_past_year: int = Field(0, description="Hospitalizations in past year")
    surgeries_past_year: int = Field(0, description="Surgeries in past year")
    total_encounters: int = Field(0, description="Total unique encounters")

    earliest_event: date | None = Field(None, description="Earliest event date")
    latest_event: date | None = Field(None, description="Latest event date")


class CareGapResponse(BaseModel):
    """A care gap identified in the timeline."""

    id: str = Field(..., description="Gap identifier")
    gap_type: GapTypeAPI = Field(..., description="Type of care gap")
    description: str = Field(..., description="Gap description")
    priority: GapPriorityAPI = Field(..., description="Gap priority")

    due_date: date | None = Field(None, description="When gap should be addressed")
    days_overdue: int = Field(0, description="Days overdue")

    related_condition: str | None = Field(None, description="Related condition")
    related_codes: list[str] = Field(default_factory=list, description="Related clinical codes")
    recommendation: str = Field(..., description="Clinical recommendation")
    last_completed: date | None = Field(None, description="Last completion date")
    expected_interval_days: int | None = Field(None, description="Expected interval in days")


class TimelineRequest(BaseModel):
    """Request to build a patient timeline."""

    patient_data: PatientDataInput = Field(..., description="Patient clinical data")
    filter: TimelineFilterInput | None = Field(None, description="Optional filter criteria")


class TimelineResponse(BaseModel):
    """Complete patient timeline response."""

    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")

    events: list[TimelineEventResponse] = Field(..., description="Timeline events")
    summary: TimelineSummaryResponse = Field(..., description="Timeline summary")

    date_range_start: date | None = Field(None, description="Start of date range covered")
    date_range_end: date | None = Field(None, description="End of date range covered")

    total_events: int = Field(..., description="Total events before filtering")
    filtered_events: int = Field(..., description="Events after filtering")

    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class EventsRequest(BaseModel):
    """Request to get filtered timeline events."""

    patient_data: PatientDataInput = Field(..., description="Patient clinical data")
    filter: TimelineFilterInput = Field(..., description="Filter criteria")


class EventsResponse(BaseModel):
    """Response with filtered timeline events."""

    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")

    events: list[TimelineEventResponse] = Field(..., description="Filtered events")
    total_matching: int = Field(..., description="Total events matching filter")

    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class GapAnalysisRequest(BaseModel):
    """Request for care gap analysis."""

    patient_data: PatientDataInput = Field(..., description="Patient clinical data")
    analysis_date: date | None = Field(None, description="Date for analysis (today if not provided)")


class GapAnalysisResponse(BaseModel):
    """Response from care gap analysis."""

    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    analysis_date: date = Field(..., description="Analysis date")

    gaps: list[CareGapResponse] = Field(..., description="Identified care gaps")

    total_gaps: int = Field(..., description="Total gaps found")
    urgent_gaps: int = Field(..., description="Urgent priority gaps")
    high_priority_gaps: int = Field(..., description="High priority gaps")
    gaps_by_type: dict[str, int] = Field(default_factory=dict, description="Gaps by type")

    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class SummaryRequest(BaseModel):
    """Request for timeline summary."""

    patient_data: PatientDataInput = Field(..., description="Patient clinical data")


class SummaryResponse(BaseModel):
    """Response with timeline summary."""

    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    summary: TimelineSummaryResponse = Field(..., description="Timeline summary")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class RelativeDateRequest(BaseModel):
    """Request to parse a relative date query."""

    query: str = Field(
        ...,
        description="Relative date query (e.g., 'last 6 months', 'past year')",
        json_schema_extra={"example": "last 6 months"}
    )
    reference_date: date | None = Field(None, description="Reference date (today if not provided)")


class RelativeDateResponse(BaseModel):
    """Response with parsed date range."""

    query: str = Field(..., description="Original query")
    date_from: date = Field(..., description="Start date of range")
    date_to: date = Field(..., description="End date of range")


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/{patient_id}",
    response_model=TimelineResponse,
    summary="Build patient timeline",
    description="Build a comprehensive patient timeline from clinical data with optional filtering.",
)
async def get_patient_timeline(
    patient_id: str,
    request: TimelineRequest,
) -> TimelineResponse:
    """Build a patient timeline.

    Aggregates events from diagnoses, procedures, labs, medications,
    vitals, encounters, and immunizations into a chronological timeline.

    Args:
        patient_id: Patient identifier
        request: Patient data and optional filter criteria

    Returns:
        TimelineResponse with events and summary
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.patient_timeline import (
            get_patient_timeline_service,
            TimelineFilter,
            TimelineEventType,
            EventSeverity,
        )

        service = get_patient_timeline_service()

        # Convert input to dict format
        patient_data = {
            "demographics": request.patient_data.demographics,
            "diagnoses": request.patient_data.diagnoses,
            "procedures": request.patient_data.procedures,
            "labs": request.patient_data.labs,
            "medications": request.patient_data.medications,
            "vitals": request.patient_data.vitals,
            "encounters": request.patient_data.encounters,
            "immunizations": request.patient_data.immunizations,
        }

        # Convert filter if provided
        filter_criteria = None
        if request.filter:
            event_types = None
            if request.filter.event_types:
                event_types = [TimelineEventType(et.value) for et in request.filter.event_types]

            severities = None
            if request.filter.severities:
                severities = [EventSeverity(s.value) for s in request.filter.severities]

            filter_criteria = TimelineFilter(
                date_from=request.filter.date_from,
                date_to=request.filter.date_to,
                event_types=event_types,
                severities=severities,
                search_text=request.filter.search_text,
                exclude_routine=request.filter.exclude_routine,
                limit=request.filter.limit,
                offset=request.filter.offset,
            )

        timeline = service.build_timeline(
            patient_id=patient_id,
            patient_data=patient_data,
            filter_criteria=filter_criteria,
        )

        # Convert events to response models
        events_response = [
            TimelineEventResponse(
                id=e.id,
                event_date=e.event_date,
                event_type=TimelineEventTypeAPI(e.event_type.value),
                description=e.description,
                severity=EventSeverityAPI(e.severity.value),
                code=e.code,
                code_system=e.code_system,
                details=e.details,
                source_encounter=e.source_encounter,
                provider=e.provider,
                facility=e.facility,
            )
            for e in timeline.events
        ]

        # Convert summary
        summary_response = TimelineSummaryResponse(
            event_counts_by_type=timeline.summary.event_counts_by_type if timeline.summary else {},
            key_events=[
                TimelineEventResponse(
                    id=e.id,
                    event_date=e.event_date,
                    event_type=TimelineEventTypeAPI(e.event_type.value),
                    description=e.description,
                    severity=EventSeverityAPI(e.severity.value),
                    code=e.code,
                    code_system=e.code_system,
                    details=e.details,
                    source_encounter=e.source_encounter,
                    provider=e.provider,
                    facility=e.facility,
                )
                for e in (timeline.summary.key_events if timeline.summary else [])
            ],
            active_conditions=timeline.summary.active_conditions if timeline.summary else [],
            current_medications=timeline.summary.current_medications if timeline.summary else [],
            recent_labs=timeline.summary.recent_labs if timeline.summary else [],
            hospitalizations_past_year=timeline.summary.hospitalizations_past_year if timeline.summary else 0,
            surgeries_past_year=timeline.summary.surgeries_past_year if timeline.summary else 0,
            total_encounters=timeline.summary.total_encounters if timeline.summary else 0,
            earliest_event=timeline.summary.earliest_event if timeline.summary else None,
            latest_event=timeline.summary.latest_event if timeline.summary else None,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        return TimelineResponse(
            request_id=request_id,
            patient_id=patient_id,
            events=events_response,
            summary=summary_response,
            date_range_start=timeline.date_range_start,
            date_range_end=timeline.date_range_end,
            total_events=timeline.total_events,
            filtered_events=timeline.filtered_events,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to build timeline: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/{patient_id}/summary",
    response_model=SummaryResponse,
    summary="Get timeline summary",
    description="Get a summary of the patient timeline with key statistics and events.",
)
async def get_timeline_summary(
    patient_id: str,
    request: SummaryRequest,
) -> SummaryResponse:
    """Get timeline summary.

    Returns key statistics and events without the full event list.

    Args:
        patient_id: Patient identifier
        request: Patient clinical data

    Returns:
        SummaryResponse with timeline summary
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.patient_timeline import get_patient_timeline_service

        service = get_patient_timeline_service()

        patient_data = {
            "demographics": request.patient_data.demographics,
            "diagnoses": request.patient_data.diagnoses,
            "procedures": request.patient_data.procedures,
            "labs": request.patient_data.labs,
            "medications": request.patient_data.medications,
            "vitals": request.patient_data.vitals,
            "encounters": request.patient_data.encounters,
            "immunizations": request.patient_data.immunizations,
        }

        summary = service.get_timeline_summary(patient_id, patient_data)

        # Convert to response
        summary_response = TimelineSummaryResponse(
            event_counts_by_type=summary.event_counts_by_type,
            key_events=[
                TimelineEventResponse(
                    id=e.id,
                    event_date=e.event_date,
                    event_type=TimelineEventTypeAPI(e.event_type.value),
                    description=e.description,
                    severity=EventSeverityAPI(e.severity.value),
                    code=e.code,
                    code_system=e.code_system,
                    details=e.details,
                    source_encounter=e.source_encounter,
                    provider=e.provider,
                    facility=e.facility,
                )
                for e in summary.key_events
            ],
            active_conditions=summary.active_conditions,
            current_medications=summary.current_medications,
            recent_labs=summary.recent_labs,
            hospitalizations_past_year=summary.hospitalizations_past_year,
            surgeries_past_year=summary.surgeries_past_year,
            total_encounters=summary.total_encounters,
            earliest_event=summary.earliest_event,
            latest_event=summary.latest_event,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        return SummaryResponse(
            request_id=request_id,
            patient_id=patient_id,
            summary=summary_response,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get timeline summary: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/{patient_id}/events",
    response_model=EventsResponse,
    summary="Get filtered timeline events",
    description="Get filtered timeline events based on date range, types, and other criteria.",
)
async def get_filtered_events(
    patient_id: str,
    request: EventsRequest,
) -> EventsResponse:
    """Get filtered timeline events.

    Returns events matching the specified filter criteria.

    Args:
        patient_id: Patient identifier
        request: Patient data and filter criteria

    Returns:
        EventsResponse with filtered events
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.patient_timeline import (
            get_patient_timeline_service,
            TimelineFilter,
            TimelineEventType,
            EventSeverity,
        )

        service = get_patient_timeline_service()

        patient_data = {
            "demographics": request.patient_data.demographics,
            "diagnoses": request.patient_data.diagnoses,
            "procedures": request.patient_data.procedures,
            "labs": request.patient_data.labs,
            "medications": request.patient_data.medications,
            "vitals": request.patient_data.vitals,
            "encounters": request.patient_data.encounters,
            "immunizations": request.patient_data.immunizations,
        }

        # Convert filter
        event_types = None
        if request.filter.event_types:
            event_types = [TimelineEventType(et.value) for et in request.filter.event_types]

        severities = None
        if request.filter.severities:
            severities = [EventSeverity(s.value) for s in request.filter.severities]

        filter_criteria = TimelineFilter(
            date_from=request.filter.date_from,
            date_to=request.filter.date_to,
            event_types=event_types,
            severities=severities,
            search_text=request.filter.search_text,
            exclude_routine=request.filter.exclude_routine,
            limit=request.filter.limit,
            offset=request.filter.offset,
        )

        events = service.get_filtered_events(patient_id, patient_data, filter_criteria)

        # Convert to response
        events_response = [
            TimelineEventResponse(
                id=e.id,
                event_date=e.event_date,
                event_type=TimelineEventTypeAPI(e.event_type.value),
                description=e.description,
                severity=EventSeverityAPI(e.severity.value),
                code=e.code,
                code_system=e.code_system,
                details=e.details,
                source_encounter=e.source_encounter,
                provider=e.provider,
                facility=e.facility,
            )
            for e in events
        ]

        processing_time = (time.perf_counter() - start_time) * 1000

        return EventsResponse(
            request_id=request_id,
            patient_id=patient_id,
            events=events_response,
            total_matching=len(events_response),
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get filtered events: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/{patient_id}/gaps",
    response_model=GapAnalysisResponse,
    summary="Analyze care gaps",
    description="Analyze the patient timeline for care gaps and overdue items.",
)
async def analyze_care_gaps(
    patient_id: str,
    request: GapAnalysisRequest,
) -> GapAnalysisResponse:
    """Analyze care gaps.

    Identifies overdue screenings, missed follow-ups, medication monitoring
    gaps, and other care gaps based on patient data and clinical guidelines.

    Args:
        patient_id: Patient identifier
        request: Patient data and analysis options

    Returns:
        GapAnalysisResponse with identified care gaps
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.patient_timeline import get_patient_timeline_service

        service = get_patient_timeline_service()

        patient_data = {
            "demographics": request.patient_data.demographics,
            "diagnoses": request.patient_data.diagnoses,
            "procedures": request.patient_data.procedures,
            "labs": request.patient_data.labs,
            "medications": request.patient_data.medications,
            "vitals": request.patient_data.vitals,
            "encounters": request.patient_data.encounters,
            "immunizations": request.patient_data.immunizations,
        }

        result = service.analyze_care_gaps(
            patient_id=patient_id,
            patient_data=patient_data,
            analysis_date=request.analysis_date,
        )

        # Convert gaps to response
        gaps_response = [
            CareGapResponse(
                id=g.id,
                gap_type=GapTypeAPI(g.gap_type.value),
                description=g.description,
                priority=GapPriorityAPI(g.priority.value),
                due_date=g.due_date,
                days_overdue=g.days_overdue,
                related_condition=g.related_condition,
                related_codes=g.related_codes,
                recommendation=g.recommendation,
                last_completed=g.last_completed,
                expected_interval_days=g.expected_interval_days,
            )
            for g in result.gaps
        ]

        processing_time = (time.perf_counter() - start_time) * 1000

        return GapAnalysisResponse(
            request_id=request_id,
            patient_id=patient_id,
            analysis_date=result.analysis_date,
            gaps=gaps_response,
            total_gaps=result.total_gaps,
            urgent_gaps=result.urgent_gaps,
            high_priority_gaps=result.high_priority_gaps,
            gaps_by_type=result.gaps_by_type,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to analyze care gaps: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/parse-date-range",
    response_model=RelativeDateResponse,
    summary="Parse relative date query",
    description="Parse a natural language date query into a date range.",
)
async def parse_relative_date(
    request: RelativeDateRequest,
) -> RelativeDateResponse:
    """Parse a relative date query.

    Converts natural language date queries like "last 6 months" or
    "past year" into actual date ranges.

    Args:
        request: Date query and optional reference date

    Returns:
        RelativeDateResponse with parsed date range
    """
    try:
        from app.services.patient_timeline import get_patient_timeline_service

        service = get_patient_timeline_service()

        date_from, date_to = service.parse_relative_date(
            relative_query=request.query,
            reference_date=request.reference_date,
        )

        return RelativeDateResponse(
            query=request.query,
            date_from=date_from,
            date_to=date_to,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to parse date query: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/stats",
    summary="Get timeline service statistics",
    description="Get statistics about the timeline service capabilities.",
)
async def get_stats() -> dict:
    """Get service statistics.

    Returns information about supported event types, gap types,
    and screening definitions.
    """
    try:
        from app.services.patient_timeline import get_patient_timeline_service

        service = get_patient_timeline_service()
        return service.get_stats()

    except Exception as e:
        raise InternalError(
            message=f"Failed to get stats: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )
