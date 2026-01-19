"""Quality Measure Tracking API Endpoints.

Provides endpoints for quality measure evaluation and care gap detection:
- List available quality measures (HEDIS, CQM)
- Evaluate patient against measures
- Get patient care gaps
- Generate aggregate performance reports

Supports value-based care programs and quality reporting.
"""

import time
from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError

router = APIRouter(prefix="/quality", tags=["Quality Measures"])


# ============================================================================
# Enums and Types
# ============================================================================


class MeasureCategoryAPI(str, Enum):
    """Quality measure category for API."""

    DIABETES = "diabetes"
    CARDIOVASCULAR = "cardiovascular"
    PREVENTIVE = "preventive"
    MEDICATION_ADHERENCE = "medication_adherence"
    BEHAVIORAL_HEALTH = "behavioral_health"
    RESPIRATORY = "respiratory"
    MUSCULOSKELETAL = "musculoskeletal"
    WOMENS_HEALTH = "womens_health"
    PEDIATRIC = "pediatric"
    SAFETY = "safety"


class MeasureTypeAPI(str, Enum):
    """Type of quality measure for API."""

    HEDIS = "hedis"
    CQM = "cqm"
    MIPS = "mips"
    CUSTOM = "custom"


class MeasurePriorityAPI(str, Enum):
    """Priority level for care gaps."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceStatusAPI(str, Enum):
    """Compliance status for a measure."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    EXCLUDED = "excluded"
    NOT_ELIGIBLE = "not_eligible"
    PENDING = "pending"


# ============================================================================
# Request/Response Models
# ============================================================================


class AgeRangeResponse(BaseModel):
    """Age range specification."""

    min_age: int = Field(..., description="Minimum age")
    max_age: int = Field(..., description="Maximum age")
    unit: str = Field(..., description="Age unit (years, months, days)")


class EligibilityCriteriaResponse(BaseModel):
    """Eligibility criteria for a measure."""

    age_range: AgeRangeResponse | None = Field(None, description="Required age range")
    gender: str | None = Field(None, description="Required gender (M/F)")
    diagnoses: list[str] = Field(default_factory=list, description="Required diagnosis codes")
    exclusion_diagnoses: list[str] = Field(default_factory=list, description="Exclusion diagnosis codes")


class QualityMeasureResponse(BaseModel):
    """Quality measure definition."""

    id: str = Field(..., description="Measure ID")
    name: str = Field(..., description="Measure name")
    description: str = Field(..., description="Measure description")
    category: MeasureCategoryAPI = Field(..., description="Measure category")
    measure_type: MeasureTypeAPI = Field(..., description="Measure type (HEDIS, CQM, etc.)")
    version: str = Field(..., description="Measure version/year")

    steward: str = Field(..., description="Measure steward organization")
    domain: str = Field(..., description="Clinical domain")
    nqf_number: str | None = Field(None, description="NQF number if applicable")
    cms_id: str | None = Field(None, description="CMS ID if applicable")

    benchmark_50th: float = Field(..., description="50th percentile benchmark")
    benchmark_90th: float = Field(..., description="90th percentile benchmark")
    default_priority: MeasurePriorityAPI = Field(..., description="Default gap priority")

    clinical_guidance: str = Field(..., description="Clinical guidance for the measure")


class MeasureListResponse(BaseModel):
    """Response for list of measures."""

    request_id: str = Field(..., description="Unique request identifier")
    total_measures: int = Field(..., description="Total number of measures")
    measures: list[QualityMeasureResponse] = Field(..., description="List of measures")
    by_category: dict[str, int] = Field(default_factory=dict, description="Count by category")
    by_type: dict[str, int] = Field(default_factory=dict, description="Count by type")


class PatientDataInput(BaseModel):
    """Patient clinical data for evaluation."""

    demographics: dict = Field(
        ...,
        description="Demographics: {age, gender, dob}",
        json_schema_extra={"example": {"age": 55, "gender": "M", "dob": "1969-05-15"}}
    )
    diagnoses: list[dict] = Field(
        default_factory=list,
        description="Diagnoses: [{code, date}]",
        json_schema_extra={"example": [{"code": "E11.9", "date": "2024-01-15"}]}
    )
    procedures: list[dict] = Field(
        default_factory=list,
        description="Procedures: [{code, date}]",
        json_schema_extra={"example": [{"code": "92014", "date": "2024-03-20"}]}
    )
    labs: list[dict] = Field(
        default_factory=list,
        description="Labs: [{name, value, date, loinc}]",
        json_schema_extra={"example": [{"name": "HbA1c", "value": 7.2, "date": "2024-06-01", "loinc": "4548-4"}]}
    )
    medications: list[dict] = Field(
        default_factory=list,
        description="Medications: [{rxnorm, start_date, end_date, days_supply}]",
        json_schema_extra={"example": [{"rxnorm": "6809", "start_date": "2024-01-01"}]}
    )
    vitals: list[dict] = Field(
        default_factory=list,
        description="Vitals: [{name, value, date}]",
        json_schema_extra={"example": [{"name": "systolic_bp", "value": 135, "date": "2024-06-15"}]}
    )


class EvaluateRequest(BaseModel):
    """Request to evaluate a patient against measures."""

    patient_data: PatientDataInput = Field(..., description="Patient clinical data")
    measure_ids: list[str] | None = Field(
        None,
        description="Specific measures to evaluate (all if not provided)"
    )
    measurement_date: date | None = Field(
        None,
        description="Date for evaluation (today if not provided)"
    )


class PatientGapResponse(BaseModel):
    """A care gap identified for a patient."""

    measure_id: str = Field(..., description="Measure ID")
    measure_name: str = Field(..., description="Measure name")
    category: MeasureCategoryAPI = Field(..., description="Measure category")
    missing_element: str = Field(..., description="What's missing")
    missing_codes: list[str] = Field(default_factory=list, description="Codes that would satisfy")
    due_date: date = Field(..., description="When the gap should be addressed")
    priority: MeasurePriorityAPI = Field(..., description="Gap priority")
    last_performed: date | None = Field(None, description="Last time performed")
    days_overdue: int = Field(0, description="Days overdue")
    recommendation: str = Field(..., description="Clinical recommendation")
    patient_instructions: str = Field(..., description="Patient-friendly instructions")


class MeasureResultResponse(BaseModel):
    """Result of evaluating a patient against a measure."""

    measure_id: str = Field(..., description="Measure ID")
    measure_name: str = Field(..., description="Measure name")
    category: MeasureCategoryAPI = Field(..., description="Measure category")

    is_eligible: bool = Field(..., description="Whether patient is eligible")
    eligibility_reason: str = Field(..., description="Eligibility explanation")

    status: ComplianceStatusAPI = Field(..., description="Compliance status")
    in_numerator: bool = Field(..., description="Whether patient meets numerator criteria")

    evidence: list[dict] = Field(default_factory=list, description="Supporting evidence")
    gap: PatientGapResponse | None = Field(None, description="Care gap if non-compliant")

    measurement_period_start: date | None = Field(None, description="Start of measurement period")
    measurement_period_end: date | None = Field(None, description="End of measurement period")


class EvaluationSummary(BaseModel):
    """Summary of patient evaluation."""

    total_measures_evaluated: int = Field(..., description="Total measures evaluated")
    measures_compliant: int = Field(..., description="Measures meeting criteria")
    measures_non_compliant: int = Field(..., description="Measures not meeting criteria")
    measures_excluded: int = Field(..., description="Measures excluded")
    overall_compliance_rate: float = Field(..., description="Overall compliance rate (0-1)")
    care_gaps_count: int = Field(..., description="Total care gaps")
    critical_gaps_count: int = Field(..., description="Critical priority gaps")


class EvaluateResponse(BaseModel):
    """Response from patient evaluation."""

    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    evaluation_date: datetime = Field(..., description="Evaluation timestamp")

    summary: EvaluationSummary = Field(..., description="Evaluation summary")
    measure_results: list[MeasureResultResponse] = Field(..., description="Results by measure")
    care_gaps: list[PatientGapResponse] = Field(..., description="Identified care gaps")

    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class GapsRequest(BaseModel):
    """Request to get patient care gaps."""

    patient_data: PatientDataInput = Field(..., description="Patient clinical data")
    priority_filter: MeasurePriorityAPI | None = Field(
        None,
        description="Filter by priority level"
    )


class GapsResponse(BaseModel):
    """Response for patient care gaps."""

    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    total_gaps: int = Field(..., description="Total gaps found")
    critical_gaps: int = Field(..., description="Critical priority gaps")
    high_priority_gaps: int = Field(..., description="High priority gaps")
    gaps: list[PatientGapResponse] = Field(..., description="Care gaps sorted by priority")


class MeasurePerformanceResponse(BaseModel):
    """Performance for a single measure."""

    measure_id: str = Field(..., description="Measure ID")
    measure_name: str = Field(..., description="Measure name")
    category: MeasureCategoryAPI = Field(..., description="Measure category")

    eligible_population: int = Field(..., description="Eligible population count")
    numerator_count: int = Field(..., description="Patients meeting criteria")
    denominator_count: int = Field(..., description="Denominator count")
    excluded_count: int = Field(..., description="Excluded count")

    performance_rate: float = Field(..., description="Performance rate (0-1)")
    benchmark_50th: float = Field(..., description="50th percentile benchmark")
    benchmark_90th: float = Field(..., description="90th percentile benchmark")
    meets_benchmark: bool = Field(..., description="Meets 50th percentile")
    star_rating: int = Field(..., ge=1, le=5, description="1-5 star rating")

    total_gaps: int = Field(0, description="Total care gaps")
    critical_gaps: int = Field(0, description="Critical priority gaps")


class PerformanceRequest(BaseModel):
    """Request for aggregate performance report."""

    patients_data: list[PatientDataInput] = Field(
        ...,
        description="List of patient clinical data",
        min_length=1,
    )
    period_start: date = Field(..., description="Start of measurement period")
    period_end: date = Field(..., description="End of measurement period")
    measure_ids: list[str] | None = Field(
        None,
        description="Specific measures to include (all if not provided)"
    )


class PerformanceResponse(BaseModel):
    """Aggregate performance report response."""

    request_id: str = Field(..., description="Unique request identifier")
    report_date: datetime = Field(..., description="Report generation timestamp")
    period_start: date = Field(..., description="Measurement period start")
    period_end: date = Field(..., description="Measurement period end")

    total_measures: int = Field(..., description="Total measures evaluated")
    measures_meeting_benchmark: int = Field(..., description="Measures meeting 50th percentile")
    average_performance_rate: float = Field(..., description="Average performance rate")

    measures: list[MeasurePerformanceResponse] = Field(..., description="Performance by measure")
    performance_by_category: dict[str, float] = Field(
        default_factory=dict,
        description="Average performance by category"
    )

    total_care_gaps: int = Field(..., description="Total care gaps across all measures")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "/measures",
    response_model=MeasureListResponse,
    summary="List available quality measures",
    description="Get all available quality measures with filtering options.",
)
async def list_measures(
    category: MeasureCategoryAPI | None = Query(None, description="Filter by category"),
    measure_type: MeasureTypeAPI | None = Query(None, description="Filter by type (HEDIS, CQM)"),
) -> MeasureListResponse:
    """List all available quality measures.

    Returns HEDIS and CQM measures with their specifications,
    optionally filtered by category or type.

    Args:
        category: Filter by measure category (diabetes, cardiovascular, etc.)
        measure_type: Filter by measure type (hedis, cqm, etc.)

    Returns:
        MeasureListResponse with available measures and statistics.
    """
    request_id = str(uuid4())

    try:
        from app.services.quality_measures import (
            get_quality_measure_service,
            MeasureCategory,
            MeasureType,
        )

        service = get_quality_measure_service()
        measures = service.get_all_measures()

        # Apply filters
        if category:
            cat_enum = MeasureCategory(category.value)
            measures = [m for m in measures if m.category == cat_enum]

        if measure_type:
            type_enum = MeasureType(measure_type.value)
            measures = [m for m in measures if m.measure_type == type_enum]

        # Build response
        measure_responses = [
            QualityMeasureResponse(
                id=m.id,
                name=m.name,
                description=m.description,
                category=MeasureCategoryAPI(m.category.value),
                measure_type=MeasureTypeAPI(m.measure_type.value),
                version=m.version,
                steward=m.steward,
                domain=m.domain,
                nqf_number=m.nqf_number,
                cms_id=m.cms_id,
                benchmark_50th=m.benchmark_50th,
                benchmark_90th=m.benchmark_90th,
                default_priority=MeasurePriorityAPI(m.default_priority.value),
                clinical_guidance=m.clinical_guidance,
            )
            for m in measures
        ]

        # Calculate statistics
        by_category: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for m in measures:
            cat = m.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            mt = m.measure_type.value
            by_type[mt] = by_type.get(mt, 0) + 1

        return MeasureListResponse(
            request_id=request_id,
            total_measures=len(measure_responses),
            measures=measure_responses,
            by_category=by_category,
            by_type=by_type,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to list measures: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/measures/{measure_id}",
    response_model=QualityMeasureResponse,
    summary="Get a specific quality measure",
    description="Get details for a specific quality measure by ID.",
)
async def get_measure(measure_id: str) -> QualityMeasureResponse:
    """Get a specific quality measure by ID.

    Args:
        measure_id: The measure ID (e.g., "HEDIS-CDC-HBA1C")

    Returns:
        QualityMeasureResponse with measure details.
    """
    try:
        from app.services.quality_measures import get_quality_measure_service

        service = get_quality_measure_service()
        measure = service.get_measure(measure_id)

        if not measure:
            raise NotFoundError(
                message=f"Measure not found: {measure_id}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
            )

        return QualityMeasureResponse(
            id=measure.id,
            name=measure.name,
            description=measure.description,
            category=MeasureCategoryAPI(measure.category.value),
            measure_type=MeasureTypeAPI(measure.measure_type.value),
            version=measure.version,
            steward=measure.steward,
            domain=measure.domain,
            nqf_number=measure.nqf_number,
            cms_id=measure.cms_id,
            benchmark_50th=measure.benchmark_50th,
            benchmark_90th=measure.benchmark_90th,
            default_priority=MeasurePriorityAPI(measure.default_priority.value),
            clinical_guidance=measure.clinical_guidance,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to get measure: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/evaluate/{patient_id}",
    response_model=EvaluateResponse,
    summary="Evaluate patient against quality measures",
    description="Evaluate a patient's compliance with quality measures and identify care gaps.",
)
async def evaluate_patient(
    patient_id: str,
    request: EvaluateRequest,
) -> EvaluateResponse:
    """Evaluate a patient against quality measures.

    Analyzes patient clinical data against HEDIS and CQM measures to determine:
    - Eligibility for each measure
    - Compliance status (met, not met, excluded)
    - Care gaps requiring intervention

    Args:
        patient_id: Patient identifier
        request: Patient clinical data and evaluation options

    Returns:
        EvaluateResponse with compliance status and care gaps.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.quality_measures import get_quality_measure_service

        service = get_quality_measure_service()

        # Convert input to dict format expected by service
        patient_data = {
            "patient_id": patient_id,
            "demographics": request.patient_data.demographics,
            "diagnoses": request.patient_data.diagnoses,
            "procedures": request.patient_data.procedures,
            "labs": request.patient_data.labs,
            "medications": request.patient_data.medications,
            "vitals": request.patient_data.vitals,
        }

        result = service.evaluate_patient(
            patient_id=patient_id,
            patient_data=patient_data,
            measure_ids=request.measure_ids,
            measurement_date=request.measurement_date,
        )

        # Convert results to response models
        measure_results_response = []
        for mr in result.measure_results:
            gap_response = None
            if mr.gap:
                gap_response = PatientGapResponse(
                    measure_id=mr.gap.measure_id,
                    measure_name=mr.gap.measure_name,
                    category=MeasureCategoryAPI(mr.gap.category.value),
                    missing_element=mr.gap.missing_element,
                    missing_codes=mr.gap.missing_codes,
                    due_date=mr.gap.due_date,
                    priority=MeasurePriorityAPI(mr.gap.priority.value),
                    last_performed=mr.gap.last_performed,
                    days_overdue=mr.gap.days_overdue,
                    recommendation=mr.gap.recommendation,
                    patient_instructions=mr.gap.patient_instructions,
                )

            measure_results_response.append(
                MeasureResultResponse(
                    measure_id=mr.measure_id,
                    measure_name=mr.measure_name,
                    category=MeasureCategoryAPI(mr.category.value),
                    is_eligible=mr.is_eligible,
                    eligibility_reason=mr.eligibility_reason,
                    status=ComplianceStatusAPI(mr.status.value),
                    in_numerator=mr.in_numerator,
                    evidence=mr.evidence,
                    gap=gap_response,
                    measurement_period_start=mr.measurement_period_start,
                    measurement_period_end=mr.measurement_period_end,
                )
            )

        # Convert care gaps
        care_gaps_response = [
            PatientGapResponse(
                measure_id=g.measure_id,
                measure_name=g.measure_name,
                category=MeasureCategoryAPI(g.category.value),
                missing_element=g.missing_element,
                missing_codes=g.missing_codes,
                due_date=g.due_date,
                priority=MeasurePriorityAPI(g.priority.value),
                last_performed=g.last_performed,
                days_overdue=g.days_overdue,
                recommendation=g.recommendation,
                patient_instructions=g.patient_instructions,
            )
            for g in result.care_gaps
        ]

        processing_time = (time.perf_counter() - start_time) * 1000

        return EvaluateResponse(
            request_id=request_id,
            patient_id=patient_id,
            evaluation_date=result.evaluation_date,
            summary=EvaluationSummary(
                total_measures_evaluated=result.total_measures_evaluated,
                measures_compliant=result.measures_compliant,
                measures_non_compliant=result.measures_non_compliant,
                measures_excluded=result.measures_excluded,
                overall_compliance_rate=result.overall_compliance_rate,
                care_gaps_count=len(result.care_gaps),
                critical_gaps_count=result.critical_gaps,
            ),
            measure_results=measure_results_response,
            care_gaps=care_gaps_response,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to evaluate patient: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/gaps/{patient_id}",
    response_model=GapsResponse,
    summary="Get patient care gaps",
    description="Get care gaps for a patient, sorted by priority.",
)
async def get_patient_gaps(
    patient_id: str,
    request: GapsRequest,
) -> GapsResponse:
    """Get care gaps for a patient.

    Returns care gaps sorted by priority (critical first),
    optionally filtered by priority level.

    Args:
        patient_id: Patient identifier
        request: Patient data and filter options

    Returns:
        GapsResponse with prioritized care gaps.
    """
    request_id = str(uuid4())

    try:
        from app.services.quality_measures import (
            get_quality_measure_service,
            MeasurePriority,
        )

        service = get_quality_measure_service()

        # Convert input to dict format
        patient_data = {
            "patient_id": patient_id,
            "demographics": request.patient_data.demographics,
            "diagnoses": request.patient_data.diagnoses,
            "procedures": request.patient_data.procedures,
            "labs": request.patient_data.labs,
            "medications": request.patient_data.medications,
            "vitals": request.patient_data.vitals,
        }

        priority_filter = None
        if request.priority_filter:
            priority_filter = MeasurePriority(request.priority_filter.value)

        gaps = service.get_patient_gaps(
            patient_id=patient_id,
            patient_data=patient_data,
            priority_filter=priority_filter,
        )

        # Convert to response models
        gaps_response = [
            PatientGapResponse(
                measure_id=g.measure_id,
                measure_name=g.measure_name,
                category=MeasureCategoryAPI(g.category.value),
                missing_element=g.missing_element,
                missing_codes=g.missing_codes,
                due_date=g.due_date,
                priority=MeasurePriorityAPI(g.priority.value),
                last_performed=g.last_performed,
                days_overdue=g.days_overdue,
                recommendation=g.recommendation,
                patient_instructions=g.patient_instructions,
            )
            for g in gaps
        ]

        # Count by priority
        critical_count = sum(1 for g in gaps_response if g.priority == MeasurePriorityAPI.CRITICAL)
        high_count = sum(1 for g in gaps_response if g.priority == MeasurePriorityAPI.HIGH)

        return GapsResponse(
            request_id=request_id,
            patient_id=patient_id,
            total_gaps=len(gaps_response),
            critical_gaps=critical_count,
            high_priority_gaps=high_count,
            gaps=gaps_response,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get patient gaps: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/performance",
    response_model=PerformanceResponse,
    summary="Get aggregate performance report",
    description="Generate aggregate quality measure performance report across a population.",
)
async def get_performance_report(request: PerformanceRequest) -> PerformanceResponse:
    """Generate aggregate performance report.

    Calculates quality measure performance across a patient population
    including compliance rates, star ratings, and care gap summaries.

    Args:
        request: Patient population data and reporting period

    Returns:
        PerformanceResponse with aggregate statistics.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.quality_measures import get_quality_measure_service

        service = get_quality_measure_service()

        # Convert patients data
        patients_data = [
            {
                "patient_id": f"patient_{i}",
                "demographics": p.demographics,
                "diagnoses": p.diagnoses,
                "procedures": p.procedures,
                "labs": p.labs,
                "medications": p.medications,
                "vitals": p.vitals,
            }
            for i, p in enumerate(request.patients_data)
        ]

        report = service.generate_performance_report(
            patients_data=patients_data,
            period_start=request.period_start,
            period_end=request.period_end,
            measure_ids=request.measure_ids,
        )

        # Convert measure performances
        measures_response = [
            MeasurePerformanceResponse(
                measure_id=m.measure_id,
                measure_name=m.measure_name,
                category=MeasureCategoryAPI(m.category.value),
                eligible_population=m.eligible_population,
                numerator_count=m.numerator_count,
                denominator_count=m.denominator_count,
                excluded_count=m.excluded_count,
                performance_rate=m.performance_rate,
                benchmark_50th=m.benchmark_50th,
                benchmark_90th=m.benchmark_90th,
                meets_benchmark=m.meets_benchmark,
                star_rating=m.star_rating,
                total_gaps=m.total_gaps,
                critical_gaps=m.critical_gaps,
            )
            for m in report.measures
        ]

        processing_time = (time.perf_counter() - start_time) * 1000

        return PerformanceResponse(
            request_id=request_id,
            report_date=report.report_date,
            period_start=report.period_start,
            period_end=report.period_end,
            total_measures=report.total_measures,
            measures_meeting_benchmark=report.measures_meeting_benchmark,
            average_performance_rate=report.average_performance_rate,
            measures=measures_response,
            performance_by_category=report.performance_by_category,
            total_care_gaps=report.total_care_gaps,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to generate performance report: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/stats",
    summary="Get quality measure service statistics",
    description="Get statistics about available quality measures.",
)
async def get_stats() -> dict:
    """Get service statistics.

    Returns counts of available measures by category and type.
    """
    try:
        from app.services.quality_measures import get_quality_measure_service

        service = get_quality_measure_service()
        return service.get_stats()

    except Exception as e:
        raise InternalError(
            message=f"Failed to get stats: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )
