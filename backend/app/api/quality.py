"""Quality Measure Tracking and Data Quality Dashboard API Endpoints.

Provides endpoints for:
1. Quality measure evaluation and care gap detection (HEDIS, CQM)
2. OHDSI-style Data Quality Dashboard (DQD) for OMOP CDM validation

Quality Measures:
- List available quality measures (HEDIS, CQM)
- Evaluate patient against measures
- Get patient care gaps
- Generate aggregate performance reports

Data Quality Dashboard:
- Overall quality scores (Completeness, Conformance, Plausibility)
- Individual check results
- Issue tracking with severity levels
- Historical quality trends
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


# ============================================================================
# Data Quality Dashboard (DQD) Enums
# ============================================================================


class DQDCategoryAPI(str, Enum):
    """Data quality check categories."""

    COMPLETENESS = "completeness"
    CONFORMANCE = "conformance"
    PLAUSIBILITY = "plausibility"


class DQDSubcategoryAPI(str, Enum):
    """Data quality check subcategories."""

    COMPLETENESS_REQUIRED = "required_fields"
    COMPLETENESS_OPTIONAL = "optional_fields"
    CONFORMANCE_VALUE = "value_conformance"
    CONFORMANCE_RELATIONAL = "relational_conformance"
    CONFORMANCE_COMPUTATIONAL = "computational_conformance"
    PLAUSIBILITY_TEMPORAL = "temporal_plausibility"
    PLAUSIBILITY_ATEMPORAL = "atemporal_plausibility"
    PLAUSIBILITY_UNIQUENESS = "uniqueness_plausibility"


class DQDSeverityAPI(str, Enum):
    """Severity levels for data quality issues."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DQDStatusAPI(str, Enum):
    """Status of a quality check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class OMOPTableAPI(str, Enum):
    """OMOP CDM tables."""

    PERSON = "person"
    VISIT_OCCURRENCE = "visit_occurrence"
    CONDITION_OCCURRENCE = "condition_occurrence"
    DRUG_EXPOSURE = "drug_exposure"
    PROCEDURE_OCCURRENCE = "procedure_occurrence"
    MEASUREMENT = "measurement"
    OBSERVATION = "observation"
    NOTE = "note"
    NOTE_NLP = "note_nlp"
    DEATH = "death"


# ============================================================================
# DQD Response Models
# ============================================================================


class DQDCheckResultResponse(BaseModel):
    """Result of a single data quality check."""

    check_id: str = Field(..., description="Unique check identifier")
    check_name: str = Field(..., description="Human-readable check name")
    category: DQDCategoryAPI = Field(..., description="Check category")
    subcategory: DQDSubcategoryAPI = Field(..., description="Check subcategory")
    table: OMOPTableAPI = Field(..., description="OMOP table being checked")
    field: str | None = Field(None, description="Field being checked")

    status: DQDStatusAPI = Field(..., description="Check status")
    severity: DQDSeverityAPI = Field(..., description="Issue severity if failed")
    score: float = Field(..., ge=0, le=100, description="Check score (0-100)")

    records_total: int = Field(0, description="Total records checked")
    records_passed: int = Field(0, description="Records that passed")
    records_failed: int = Field(0, description="Records that failed")
    percent_passed: float = Field(0, description="Percentage of records passed")

    threshold_value: float = Field(0, description="Pass threshold")
    message: str = Field("", description="Result message")
    failed_examples: list[dict] = Field(default_factory=list, description="Sample failed records")
    execution_time_ms: float = Field(0, description="Check execution time")
    executed_at: str = Field(..., description="Execution timestamp")


class DQDIssueResponse(BaseModel):
    """A data quality issue."""

    issue_id: str = Field(..., description="Unique issue identifier")
    check_id: str = Field(..., description="Check that found this issue")
    table: OMOPTableAPI = Field(..., description="Affected table")
    field: str | None = Field(None, description="Affected field")
    record_id: str | None = Field(None, description="Specific record ID if applicable")
    severity: DQDSeverityAPI = Field(..., description="Issue severity")
    category: DQDCategoryAPI = Field(..., description="Issue category")

    description: str = Field(..., description="Issue description")
    current_value: str | None = Field(None, description="Current value")
    expected_value: str | None = Field(None, description="Expected value")
    recommendation: str = Field("", description="Remediation recommendation")

    detected_at: str = Field(..., description="When issue was detected")
    resolved: bool = Field(False, description="Whether issue is resolved")


class DQDCategorySummaryResponse(BaseModel):
    """Summary for a quality category."""

    category: DQDCategoryAPI = Field(..., description="Category")
    score: float = Field(..., ge=0, le=100, description="Category score")
    checks_total: int = Field(..., description="Total checks in category")
    checks_passed: int = Field(..., description="Passed checks")
    checks_failed: int = Field(..., description="Failed checks")
    checks_warning: int = Field(..., description="Warning checks")
    critical_issues: int = Field(0, description="Critical issues count")
    high_issues: int = Field(0, description="High priority issues count")

    previous_score: float | None = Field(None, description="Previous score for trend")
    score_change: float | None = Field(None, description="Score change from previous")


class DQDTableSummaryResponse(BaseModel):
    """Summary for an OMOP table."""

    table: OMOPTableAPI = Field(..., description="Table name")
    record_count: int = Field(..., description="Total records in table")
    score: float = Field(..., ge=0, le=100, description="Table quality score")
    completeness_score: float = Field(..., description="Completeness score")
    conformance_score: float = Field(..., description="Conformance score")
    plausibility_score: float = Field(..., description="Plausibility score")
    issues_count: int = Field(0, description="Total issues for table")
    critical_issues: int = Field(0, description="Critical issues for table")


class DQDSummaryResponse(BaseModel):
    """Overall data quality summary."""

    overall_score: float = Field(..., ge=0, le=100, description="Overall quality score")
    executed_at: str = Field(..., description="Last execution timestamp")
    execution_time_ms: float = Field(..., description="Execution time")

    completeness_score: float = Field(..., description="Completeness score")
    conformance_score: float = Field(..., description="Conformance score")
    plausibility_score: float = Field(..., description="Plausibility score")

    total_checks: int = Field(..., description="Total checks executed")
    checks_passed: int = Field(..., description="Checks passed")
    checks_failed: int = Field(..., description="Checks failed")
    checks_warning: int = Field(..., description="Checks with warnings")
    checks_error: int = Field(0, description="Checks that errored")

    total_issues: int = Field(0, description="Total issues found")
    critical_issues: int = Field(0, description="Critical issues")
    high_issues: int = Field(0, description="High priority issues")
    medium_issues: int = Field(0, description="Medium priority issues")
    low_issues: int = Field(0, description="Low priority issues")

    category_summaries: list[DQDCategorySummaryResponse] = Field(
        default_factory=list,
        description="Summaries by category"
    )
    table_summaries: list[DQDTableSummaryResponse] = Field(
        default_factory=list,
        description="Summaries by table"
    )


class DQDHistoryEntryResponse(BaseModel):
    """Historical quality score entry."""

    run_id: str = Field(..., description="Run identifier")
    timestamp: str = Field(..., description="Run timestamp")
    overall_score: float = Field(..., description="Overall score")
    completeness_score: float = Field(..., description="Completeness score")
    conformance_score: float = Field(..., description="Conformance score")
    plausibility_score: float = Field(..., description="Plausibility score")
    total_checks: int = Field(..., description="Total checks")
    checks_passed: int = Field(..., description="Checks passed")
    total_issues: int = Field(..., description="Total issues")


class DQDCheckListResponse(BaseModel):
    """Response for list of check results."""

    request_id: str = Field(..., description="Request identifier")
    total_checks: int = Field(..., description="Total checks returned")
    category_filter: str | None = Field(None, description="Category filter applied")
    checks: list[DQDCheckResultResponse] = Field(..., description="Check results")


class DQDHistoryResponse(BaseModel):
    """Response for quality history."""

    request_id: str = Field(..., description="Request identifier")
    entries: list[DQDHistoryEntryResponse] = Field(..., description="History entries")
    total_entries: int = Field(..., description="Total entries returned")


class DQDRunResponse(BaseModel):
    """Response for a quality check run."""

    request_id: str = Field(..., description="Request identifier")
    run_id: str = Field(..., description="Run identifier")
    summary: DQDSummaryResponse = Field(..., description="Run summary")
    total_checks: int = Field(..., description="Total checks executed")
    total_issues: int = Field(..., description="Total issues found")
    duration_ms: float = Field(..., description="Run duration")
    started_at: str = Field(..., description="Run start time")
    completed_at: str = Field(..., description="Run completion time")


class DQDIssueListResponse(BaseModel):
    """Response for list of issues."""

    request_id: str = Field(..., description="Request identifier")
    total_issues: int = Field(..., description="Total issues")
    severity_filter: str | None = Field(None, description="Severity filter applied")
    issues: list[DQDIssueResponse] = Field(..., description="Issues list")


# ============================================================================
# DQD API Endpoints
# ============================================================================


@router.get(
    "/dqd/summary",
    response_model=DQDSummaryResponse,
    summary="Get overall data quality summary",
    description="Returns aggregate quality scores for Completeness, Conformance, and Plausibility.",
    tags=["Data Quality Dashboard"],
)
async def get_dqd_summary() -> DQDSummaryResponse:
    """Get overall data quality summary.

    Returns aggregate quality scores across all OMOP CDM tables,
    broken down by the three OHDSI DQD categories:
    - Completeness: Required fields populated
    - Conformance: Values within expected ranges
    - Plausibility: Temporal consistency and reasonable values

    Returns:
        DQDSummaryResponse with overall and category scores.
    """
    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        summary = service.get_summary()

        return DQDSummaryResponse(
            overall_score=summary.overall_score,
            executed_at=summary.executed_at,
            execution_time_ms=summary.execution_time_ms,
            completeness_score=summary.completeness_score,
            conformance_score=summary.conformance_score,
            plausibility_score=summary.plausibility_score,
            total_checks=summary.total_checks,
            checks_passed=summary.checks_passed,
            checks_failed=summary.checks_failed,
            checks_warning=summary.checks_warning,
            checks_error=summary.checks_error,
            total_issues=summary.total_issues,
            critical_issues=summary.critical_issues,
            high_issues=summary.high_issues,
            medium_issues=summary.medium_issues,
            low_issues=summary.low_issues,
            category_summaries=[
                DQDCategorySummaryResponse(
                    category=DQDCategoryAPI(cs.category.value),
                    score=cs.score,
                    checks_total=cs.checks_total,
                    checks_passed=cs.checks_passed,
                    checks_failed=cs.checks_failed,
                    checks_warning=cs.checks_warning,
                    critical_issues=cs.critical_issues,
                    high_issues=cs.high_issues,
                    previous_score=cs.previous_score,
                    score_change=cs.score_change,
                )
                for cs in summary.category_summaries
            ],
            table_summaries=[
                DQDTableSummaryResponse(
                    table=OMOPTableAPI(ts.table.value),
                    record_count=ts.record_count,
                    score=ts.score,
                    completeness_score=ts.completeness_score,
                    conformance_score=ts.conformance_score,
                    plausibility_score=ts.plausibility_score,
                    issues_count=ts.issues_count,
                    critical_issues=ts.critical_issues,
                )
                for ts in summary.table_summaries
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD summary: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/checks",
    response_model=DQDCheckListResponse,
    summary="List all data quality check results",
    description="Returns results of all executed quality checks.",
    tags=["Data Quality Dashboard"],
)
async def list_dqd_checks(
    category: DQDCategoryAPI | None = Query(None, description="Filter by category"),
) -> DQDCheckListResponse:
    """List all data quality check results.

    Args:
        category: Optional category filter (completeness, conformance, plausibility)

    Returns:
        DQDCheckListResponse with check results.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import (
            get_data_quality_service,
            DQDCategory,
        )

        service = get_data_quality_service()

        cat_filter = None
        if category:
            cat_filter = DQDCategory(category.value)

        checks = service.get_checks(category=cat_filter)

        return DQDCheckListResponse(
            request_id=request_id,
            total_checks=len(checks),
            category_filter=category.value if category else None,
            checks=[
                DQDCheckResultResponse(
                    check_id=c.check_id,
                    check_name=c.check_name,
                    category=DQDCategoryAPI(c.category.value),
                    subcategory=DQDSubcategoryAPI(c.subcategory.value),
                    table=OMOPTableAPI(c.table.value),
                    field=c.field,
                    status=DQDStatusAPI(c.status.value),
                    severity=DQDSeverityAPI(c.severity.value),
                    score=c.score,
                    records_total=c.records_total,
                    records_passed=c.records_passed,
                    records_failed=c.records_failed,
                    percent_passed=c.percent_passed,
                    threshold_value=c.threshold_value,
                    message=c.message,
                    failed_examples=c.failed_examples,
                    execution_time_ms=c.execution_time_ms,
                    executed_at=c.executed_at,
                )
                for c in checks
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to list DQD checks: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/checks/{category}",
    response_model=DQDCheckListResponse,
    summary="Get checks by category",
    description="Returns check results for a specific quality category.",
    tags=["Data Quality Dashboard"],
)
async def get_dqd_checks_by_category(
    category: DQDCategoryAPI,
) -> DQDCheckListResponse:
    """Get check results for a specific category.

    Args:
        category: Quality category (completeness, conformance, plausibility)

    Returns:
        DQDCheckListResponse with filtered check results.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import (
            get_data_quality_service,
            DQDCategory,
        )

        service = get_data_quality_service()
        cat_enum = DQDCategory(category.value)
        checks = service.get_checks_by_category(cat_enum)

        return DQDCheckListResponse(
            request_id=request_id,
            total_checks=len(checks),
            category_filter=category.value,
            checks=[
                DQDCheckResultResponse(
                    check_id=c.check_id,
                    check_name=c.check_name,
                    category=DQDCategoryAPI(c.category.value),
                    subcategory=DQDSubcategoryAPI(c.subcategory.value),
                    table=OMOPTableAPI(c.table.value),
                    field=c.field,
                    status=DQDStatusAPI(c.status.value),
                    severity=DQDSeverityAPI(c.severity.value),
                    score=c.score,
                    records_total=c.records_total,
                    records_passed=c.records_passed,
                    records_failed=c.records_failed,
                    percent_passed=c.percent_passed,
                    threshold_value=c.threshold_value,
                    message=c.message,
                    failed_examples=c.failed_examples,
                    execution_time_ms=c.execution_time_ms,
                    executed_at=c.executed_at,
                )
                for c in checks
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD checks by category: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/dqd/run",
    response_model=DQDRunResponse,
    summary="Trigger data quality check run",
    description="Executes all data quality checks and returns results.",
    tags=["Data Quality Dashboard"],
)
async def run_dqd_checks() -> DQDRunResponse:
    """Trigger a fresh data quality check run.

    Executes all configured quality checks against the OMOP CDM tables
    and returns comprehensive results.

    Returns:
        DQDRunResponse with run results and summary.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        run_result = service.run_checks()

        summary = run_result.summary
        return DQDRunResponse(
            request_id=request_id,
            run_id=run_result.run_id,
            summary=DQDSummaryResponse(
                overall_score=summary.overall_score,
                executed_at=summary.executed_at,
                execution_time_ms=summary.execution_time_ms,
                completeness_score=summary.completeness_score,
                conformance_score=summary.conformance_score,
                plausibility_score=summary.plausibility_score,
                total_checks=summary.total_checks,
                checks_passed=summary.checks_passed,
                checks_failed=summary.checks_failed,
                checks_warning=summary.checks_warning,
                checks_error=summary.checks_error,
                total_issues=summary.total_issues,
                critical_issues=summary.critical_issues,
                high_issues=summary.high_issues,
                medium_issues=summary.medium_issues,
                low_issues=summary.low_issues,
                category_summaries=[
                    DQDCategorySummaryResponse(
                        category=DQDCategoryAPI(cs.category.value),
                        score=cs.score,
                        checks_total=cs.checks_total,
                        checks_passed=cs.checks_passed,
                        checks_failed=cs.checks_failed,
                        checks_warning=cs.checks_warning,
                        critical_issues=cs.critical_issues,
                        high_issues=cs.high_issues,
                    )
                    for cs in summary.category_summaries
                ],
                table_summaries=[
                    DQDTableSummaryResponse(
                        table=OMOPTableAPI(ts.table.value),
                        record_count=ts.record_count,
                        score=ts.score,
                        completeness_score=ts.completeness_score,
                        conformance_score=ts.conformance_score,
                        plausibility_score=ts.plausibility_score,
                        issues_count=ts.issues_count,
                        critical_issues=ts.critical_issues,
                    )
                    for ts in summary.table_summaries
                ],
            ),
            total_checks=len(run_result.check_results),
            total_issues=len(run_result.issues),
            duration_ms=run_result.duration_ms,
            started_at=run_result.started_at,
            completed_at=run_result.completed_at,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to run DQD checks: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/history",
    response_model=DQDHistoryResponse,
    summary="Get historical quality scores",
    description="Returns historical quality scores for trend analysis.",
    tags=["Data Quality Dashboard"],
)
async def get_dqd_history(
    limit: int = Query(30, ge=1, le=100, description="Number of entries to return"),
) -> DQDHistoryResponse:
    """Get historical quality scores.

    Args:
        limit: Maximum number of history entries to return (default 30, max 100)

    Returns:
        DQDHistoryResponse with historical entries.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        history = service.get_history(limit=limit)

        return DQDHistoryResponse(
            request_id=request_id,
            entries=[
                DQDHistoryEntryResponse(
                    run_id=h.run_id,
                    timestamp=h.timestamp,
                    overall_score=h.overall_score,
                    completeness_score=h.completeness_score,
                    conformance_score=h.conformance_score,
                    plausibility_score=h.plausibility_score,
                    total_checks=h.total_checks,
                    checks_passed=h.checks_passed,
                    total_issues=h.total_issues,
                )
                for h in history
            ],
            total_entries=len(history),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD history: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/issues",
    response_model=DQDIssueListResponse,
    summary="Get data quality issues",
    description="Returns list of identified data quality issues.",
    tags=["Data Quality Dashboard"],
)
async def get_dqd_issues(
    severity: DQDSeverityAPI | None = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=500, description="Maximum issues to return"),
) -> DQDIssueListResponse:
    """Get data quality issues.

    Args:
        severity: Optional severity filter
        limit: Maximum number of issues to return

    Returns:
        DQDIssueListResponse with issues list.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import (
            get_data_quality_service,
            DQDSeverity,
        )

        service = get_data_quality_service()

        sev_filter = None
        if severity:
            sev_filter = DQDSeverity(severity.value)

        issues = service.get_issues(severity=sev_filter, limit=limit)

        return DQDIssueListResponse(
            request_id=request_id,
            total_issues=len(issues),
            severity_filter=severity.value if severity else None,
            issues=[
                DQDIssueResponse(
                    issue_id=i.issue_id,
                    check_id=i.check_id,
                    table=OMOPTableAPI(i.table.value),
                    field=i.field,
                    record_id=i.record_id,
                    severity=DQDSeverityAPI(i.severity.value),
                    category=DQDCategoryAPI(i.category.value),
                    description=i.description,
                    current_value=str(i.current_value) if i.current_value else None,
                    expected_value=str(i.expected_value) if i.expected_value else None,
                    recommendation=i.recommendation,
                    detected_at=i.detected_at,
                    resolved=i.resolved,
                )
                for i in issues
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD issues: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/stats",
    summary="Get DQD service statistics",
    description="Get statistics about the Data Quality Dashboard service.",
    tags=["Data Quality Dashboard"],
)
async def get_dqd_stats() -> dict:
    """Get DQD service statistics.

    Returns information about configured checks and service state.
    """
    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        return service.get_stats()

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD stats: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )
