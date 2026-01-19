"""Quality Measures API Endpoints.

Provides endpoints for clinical quality measure tracking:
- List measures (HEDIS, CQM, eCQM)
- Get measure details with NQF ID, steward, rationale
- Calculate performance with numerator/denominator/exclusion logic
- Detect patient care gaps
- Track gap closure
- Generate performance trends and benchmark comparisons
"""

import logging
import time
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query, Path, Body, HTTPException
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quality", tags=["Quality Measures"])


# ============================================================================
# Enums
# ============================================================================


class MeasureCategoryEnum(str, Enum):
    """Quality measure category."""
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


class MeasureTypeEnum(str, Enum):
    """Type of quality measure."""
    HEDIS = "hedis"
    CQM = "cqm"
    MIPS = "mips"
    CUSTOM = "custom"


class MeasurePriorityEnum(str, Enum):
    """Priority level for care gaps."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceStatusEnum(str, Enum):
    """Compliance status for a measure."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    EXCLUDED = "excluded"
    NOT_ELIGIBLE = "not_eligible"
    PENDING = "pending"


class MeasureSetEnum(str, Enum):
    """Measure set for filtering."""
    ALL = "all"
    HEDIS = "hedis"
    CQM = "cqm"
    STAR = "star"
    CUSTOM = "custom"


class TimePeriodEnum(str, Enum):
    """Time period for performance reporting."""
    CURRENT_YEAR = "current_year"
    LAST_YEAR = "last_year"
    LAST_6_MONTHS = "last_6_months"
    LAST_12_MONTHS = "last_12_months"
    CUSTOM = "custom"


# ============================================================================
# Request/Response Models
# ============================================================================


class MeasureMetadata(BaseModel):
    """Measure metadata including NQF and steward information."""
    nqf_id: str | None = Field(None, description="National Quality Forum ID")
    cms_id: str | None = Field(None, description="CMS measure ID")
    steward: str = Field(..., description="Organization that maintains the measure")
    domain: str = Field(..., description="Clinical domain")
    description: str = Field(..., description="Full measure description")
    rationale: str = Field("", description="Clinical rationale for the measure")
    specifications_url: str | None = Field(None, description="Link to measure specifications")


class BenchmarkInfo(BaseModel):
    """Benchmark comparison information."""
    percentile_50th: float = Field(..., description="50th percentile benchmark")
    percentile_90th: float = Field(..., description="90th percentile benchmark")
    national_average: float | None = Field(None, description="National average if available")
    star_rating: int = Field(..., ge=1, le=5, description="1-5 star rating")
    meets_benchmark: bool = Field(..., description="Whether performance meets 50th percentile")


class PerformanceRate(BaseModel):
    """Performance rate details."""
    rate: float = Field(..., ge=0, le=1, description="Performance rate (0-1)")
    rate_display: str = Field(..., description="Display formatted rate (e.g., '72.5%')")
    numerator: int = Field(..., description="Numerator count")
    denominator: int = Field(..., description="Denominator count")
    excluded: int = Field(0, description="Excluded count")
    eligible_population: int = Field(..., description="Total eligible population")


class TrendPoint(BaseModel):
    """Single point in a performance trend."""
    period: str = Field(..., description="Period label (e.g., '2024-Q1')")
    period_start: date = Field(..., description="Period start date")
    period_end: date = Field(..., description="Period end date")
    rate: float = Field(..., description="Performance rate for period")
    numerator: int = Field(..., description="Numerator for period")
    denominator: int = Field(..., description="Denominator for period")


class MeasureResponse(BaseModel):
    """Complete quality measure response."""
    id: str = Field(..., description="Measure ID (e.g., 'HEDIS-CDC-HBA1C')")
    name: str = Field(..., description="Measure name")
    category: MeasureCategoryEnum = Field(..., description="Measure category")
    measure_type: MeasureTypeEnum = Field(..., description="Measure type")
    version: str = Field(..., description="Measure version/year")

    metadata: MeasureMetadata = Field(..., description="Measure metadata")
    clinical_guidance: str = Field(..., description="Clinical guidance for closing gaps")
    default_priority: MeasurePriorityEnum = Field(..., description="Default gap priority")

    # Performance (optional, included when performance data requested)
    performance: PerformanceRate | None = Field(None, description="Current performance")
    benchmark: BenchmarkInfo | None = Field(None, description="Benchmark comparison")
    trend: list[TrendPoint] | None = Field(None, description="Performance trend")

    # Gap summary
    total_gaps: int = Field(0, description="Total care gaps")
    critical_gaps: int = Field(0, description="Critical priority gaps")
    high_priority_gaps: int = Field(0, description="High priority gaps")


class MeasureListResponse(BaseModel):
    """Response for listing measures."""
    request_id: str = Field(..., description="Unique request identifier")
    total: int = Field(..., description="Total measures matching filters")
    measures: list[MeasureResponse] = Field(..., description="List of measures")
    by_category: dict[str, int] = Field(default_factory=dict, description="Count by category")
    by_type: dict[str, int] = Field(default_factory=dict, description="Count by type")


class PatientGapResponse(BaseModel):
    """Care gap for a patient."""
    id: str = Field(..., description="Gap identifier")
    patient_id: str = Field(..., description="Patient identifier")
    patient_name: str | None = Field(None, description="Patient name if available")

    measure_id: str = Field(..., description="Measure ID")
    measure_name: str = Field(..., description="Measure name")
    category: MeasureCategoryEnum = Field(..., description="Measure category")

    missing_element: str = Field(..., description="What's missing")
    missing_codes: list[str] = Field(default_factory=list, description="Codes that would satisfy")

    due_date: date = Field(..., description="When gap should be addressed")
    priority: MeasurePriorityEnum = Field(..., description="Gap priority")
    days_overdue: int = Field(0, description="Days past due")

    last_performed: date | None = Field(None, description="When last performed")
    recommendation: str = Field("", description="Clinical recommendation")
    patient_instructions: str = Field("", description="Patient-friendly instructions")

    attributed_provider_id: str | None = Field(None, description="Attributed provider ID")
    attributed_provider_name: str | None = Field(None, description="Attributed provider name")

    status: str = Field("open", description="Gap status: open, scheduled, closed, excluded")
    scheduled_date: date | None = Field(None, description="Scheduled date for gap closure")
    closed_date: date | None = Field(None, description="Date gap was closed")
    closed_by: str | None = Field(None, description="User who closed the gap")


class GapListResponse(BaseModel):
    """Response for listing patient gaps."""
    request_id: str = Field(..., description="Unique request identifier")
    total: int = Field(..., description="Total gaps matching filters")
    total_critical: int = Field(0, description="Critical gaps count")
    total_high: int = Field(0, description="High priority gaps count")
    total_medium: int = Field(0, description="Medium priority gaps count")
    total_low: int = Field(0, description="Low priority gaps count")
    gaps: list[PatientGapResponse] = Field(..., description="List of gaps")


class CloseGapRequest(BaseModel):
    """Request to mark a gap as closed."""
    closure_reason: str = Field(..., description="Reason for closure")
    closure_code: str | None = Field(None, description="Code that satisfied the gap")
    closure_date: date | None = Field(None, description="Date of closure (defaults to today)")
    notes: str = Field("", description="Additional notes")


class CloseGapResponse(BaseModel):
    """Response after closing a gap."""
    request_id: str = Field(..., description="Unique request identifier")
    gap_id: str = Field(..., description="Gap ID that was closed")
    patient_id: str = Field(..., description="Patient ID")
    measure_id: str = Field(..., description="Measure ID")
    status: str = Field("closed", description="New status")
    closed_date: date = Field(..., description="Closure date")
    closed_by: str = Field(..., description="User who closed")


class PerformanceSummaryResponse(BaseModel):
    """Overall performance summary."""
    request_id: str = Field(..., description="Unique request identifier")
    period_start: date = Field(..., description="Performance period start")
    period_end: date = Field(..., description="Performance period end")

    total_measures: int = Field(..., description="Total measures tracked")
    measures_meeting_benchmark: int = Field(..., description="Measures at or above 50th percentile")
    average_performance: float = Field(..., description="Average performance rate")

    total_gaps: int = Field(..., description="Total open gaps")
    critical_gaps: int = Field(..., description="Critical gaps")
    gap_closure_rate: float = Field(0, description="Gap closure rate (past 30 days)")

    by_category: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Performance by category"
    )

    star_distribution: dict[int, int] = Field(
        default_factory=dict,
        description="Count of measures by star rating (1-5)"
    )


class TrendResponse(BaseModel):
    """Performance trend response."""
    request_id: str = Field(..., description="Unique request identifier")
    measure_id: str | None = Field(None, description="Measure ID if specific measure")
    period_type: str = Field(..., description="Period type (monthly, quarterly, yearly)")

    trend_data: list[TrendPoint] = Field(..., description="Trend data points")
    overall_direction: str = Field(..., description="Trend direction: improving, declining, stable")
    change_from_previous: float | None = Field(None, description="Change from previous period")


# ============================================================================
# Mock Data Generation
# ============================================================================


def generate_mock_patient_gaps(
    measure_filter: str | None = None,
    provider_filter: str | None = None,
    priority_filter: MeasurePriorityEnum | None = None,
    limit: int = 100,
) -> list[PatientGapResponse]:
    """Generate realistic mock patient gaps."""
    from app.services.quality_measures import get_quality_measure_service

    service = get_quality_measure_service()
    measures = service.get_all_measures()

    # Sample patient data
    patients = [
        ("P001", "John Smith", "DR001", "Dr. Sarah Johnson"),
        ("P002", "Mary Johnson", "DR001", "Dr. Sarah Johnson"),
        ("P003", "Robert Williams", "DR002", "Dr. Michael Chen"),
        ("P004", "Lisa Brown", "DR002", "Dr. Michael Chen"),
        ("P005", "David Garcia", "DR003", "Dr. Emily Rodriguez"),
        ("P006", "Sarah Miller", "DR003", "Dr. Emily Rodriguez"),
        ("P007", "Michael Davis", "DR001", "Dr. Sarah Johnson"),
        ("P008", "Jennifer Wilson", "DR002", "Dr. Michael Chen"),
        ("P009", "James Anderson", "DR004", "Dr. James Park"),
        ("P010", "Patricia Martinez", "DR004", "Dr. James Park"),
        ("P011", "William Taylor", "DR001", "Dr. Sarah Johnson"),
        ("P012", "Elizabeth Thomas", "DR002", "Dr. Michael Chen"),
        ("P013", "Christopher Jackson", "DR003", "Dr. Emily Rodriguez"),
        ("P014", "Amanda White", "DR005", "Dr. Lisa Kim"),
        ("P015", "Daniel Harris", "DR005", "Dr. Lisa Kim"),
    ]

    gaps: list[PatientGapResponse] = []
    gap_id = 1

    for measure in measures:
        if measure_filter and measure.id != measure_filter:
            continue

        # Generate 2-8 gaps per measure
        import random
        random.seed(hash(measure.id))
        num_gaps = random.randint(2, 8)

        for i in range(num_gaps):
            if len(gaps) >= limit:
                break

            patient = patients[gap_id % len(patients)]

            if provider_filter and patient[2] != provider_filter:
                continue

            # Generate priority based on measure default with some variation
            priorities = [
                measure.default_priority.value,
                measure.default_priority.value,
                "high" if measure.default_priority.value == "critical" else measure.default_priority.value,
            ]
            priority_val = random.choice(priorities)
            priority = MeasurePriorityEnum(priority_val)

            if priority_filter and priority != priority_filter:
                continue

            # Generate dates
            days_overdue = random.randint(0, 90) if random.random() > 0.3 else 0
            due_date = date.today() if days_overdue == 0 else date(2025, 1, 1)
            last_performed = None
            if random.random() > 0.5:
                last_performed = date(2024, random.randint(1, 12), random.randint(1, 28))

            gap = PatientGapResponse(
                id=f"gap-{gap_id:04d}",
                patient_id=patient[0],
                patient_name=patient[1],
                measure_id=measure.id,
                measure_name=measure.name,
                category=MeasureCategoryEnum(measure.category.value),
                missing_element=f"{measure.name} not documented",
                missing_codes=["CPT-CODE-1", "CPT-CODE-2"][:random.randint(1, 2)],
                due_date=due_date,
                priority=priority,
                days_overdue=days_overdue,
                last_performed=last_performed,
                recommendation=measure.clinical_guidance,
                patient_instructions=f"Please schedule an appointment for {measure.name.lower()}.",
                attributed_provider_id=patient[2],
                attributed_provider_name=patient[3],
                status="open",
            )
            gaps.append(gap)
            gap_id += 1

    # Sort by priority then due date
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps.sort(key=lambda g: (priority_order.get(g.priority.value, 4), g.due_date))

    return gaps[:limit]


def generate_mock_trends(measure_id: str | None = None, periods: int = 12) -> list[TrendPoint]:
    """Generate mock performance trends."""
    import random

    trend_data = []
    base_rate = random.uniform(0.55, 0.75)

    for i in range(periods):
        month = 12 - periods + i + 1
        year = 2024 if month <= 12 else 2025
        if month > 12:
            month = month - 12

        # Add some random variation with slight upward trend
        rate = min(0.95, max(0.30, base_rate + random.uniform(-0.03, 0.05) + (i * 0.005)))

        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1)
        else:
            period_end = date(year, month + 1, 1)

        denominator = random.randint(800, 1200)
        numerator = int(denominator * rate)

        trend_data.append(TrendPoint(
            period=f"{year}-{month:02d}",
            period_start=period_start,
            period_end=period_end,
            rate=round(rate, 3),
            numerator=numerator,
            denominator=denominator,
        ))

    return trend_data


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "/measures",
    response_model=MeasureListResponse,
    summary="List all quality measures",
    description="Get all available quality measures with optional filtering by category, type, or set.",
)
async def list_measures(
    category: MeasureCategoryEnum | None = Query(None, description="Filter by category"),
    measure_type: MeasureTypeEnum | None = Query(None, description="Filter by type"),
    measure_set: MeasureSetEnum = Query(MeasureSetEnum.ALL, description="Filter by measure set"),
    include_performance: bool = Query(False, description="Include performance data"),
    time_period: TimePeriodEnum = Query(TimePeriodEnum.CURRENT_YEAR, description="Time period for performance"),
) -> MeasureListResponse:
    """List all available quality measures.

    Returns HEDIS, CQM, and custom measures with metadata including
    NQF ID, steward, description, and clinical rationale.
    """
    request_id = str(uuid4())

    try:
        from app.services.quality_measures import (
            get_quality_measure_service,
            MeasureCategory,
            MeasureType,
        )

        service = get_quality_measure_service()
        all_measures = service.get_all_measures()

        # Apply filters
        filtered = all_measures
        if category:
            cat_enum = MeasureCategory(category.value)
            filtered = [m for m in filtered if m.category == cat_enum]

        if measure_type:
            type_enum = MeasureType(measure_type.value)
            filtered = [m for m in filtered if m.measure_type == type_enum]

        if measure_set != MeasureSetEnum.ALL:
            if measure_set == MeasureSetEnum.HEDIS:
                filtered = [m for m in filtered if m.measure_type == MeasureType.HEDIS]
            elif measure_set == MeasureSetEnum.CQM:
                filtered = [m for m in filtered if m.measure_type == MeasureType.CQM]

        # Build responses
        measures_response = []
        for m in filtered:
            # Generate mock performance if requested
            performance = None
            benchmark = None
            trend = None

            if include_performance:
                import random
                random.seed(hash(m.id))
                rate = random.uniform(0.45, 0.90)
                denominator = random.randint(500, 3000)
                numerator = int(denominator * rate)
                excluded = random.randint(10, 100)

                performance = PerformanceRate(
                    rate=round(rate, 3),
                    rate_display=f"{rate*100:.1f}%",
                    numerator=numerator,
                    denominator=denominator,
                    excluded=excluded,
                    eligible_population=denominator + excluded,
                )

                star = 3
                if rate >= m.benchmark_90th:
                    star = 5
                elif rate >= (m.benchmark_50th + m.benchmark_90th) / 2:
                    star = 4
                elif rate >= m.benchmark_50th:
                    star = 3
                elif rate >= m.benchmark_50th * 0.8:
                    star = 2
                else:
                    star = 1

                benchmark = BenchmarkInfo(
                    percentile_50th=m.benchmark_50th,
                    percentile_90th=m.benchmark_90th,
                    national_average=round((m.benchmark_50th + m.benchmark_90th) / 2, 3),
                    star_rating=star,
                    meets_benchmark=rate >= m.benchmark_50th,
                )

                trend = generate_mock_trends(m.id, 12)

            # Count mock gaps
            import random
            random.seed(hash(m.id) + 1)
            total_gaps = random.randint(50, 500)
            critical_pct = 0.15 if m.default_priority.value == "critical" else 0.08
            high_pct = 0.30 if m.default_priority.value in ["critical", "high"] else 0.20

            measures_response.append(MeasureResponse(
                id=m.id,
                name=m.name,
                category=MeasureCategoryEnum(m.category.value),
                measure_type=MeasureTypeEnum(m.measure_type.value),
                version=m.version,
                metadata=MeasureMetadata(
                    nqf_id=m.nqf_number,
                    cms_id=m.cms_id,
                    steward=m.steward,
                    domain=m.domain,
                    description=m.description,
                    rationale=m.clinical_guidance,
                    specifications_url=m.specifications_url,
                ),
                clinical_guidance=m.clinical_guidance,
                default_priority=MeasurePriorityEnum(m.default_priority.value),
                performance=performance,
                benchmark=benchmark,
                trend=trend,
                total_gaps=total_gaps,
                critical_gaps=int(total_gaps * critical_pct),
                high_priority_gaps=int(total_gaps * high_pct),
            ))

        # Calculate counts
        by_category: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for m in measures_response:
            cat = m.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            mt = m.measure_type.value
            by_type[mt] = by_type.get(mt, 0) + 1

        return MeasureListResponse(
            request_id=request_id,
            total=len(measures_response),
            measures=measures_response,
            by_category=by_category,
            by_type=by_type,
        )

    except Exception as e:
        logger.exception(f"Failed to list measures: {e}")
        raise InternalError(
            message=f"Failed to list measures: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/measures/{measure_id}",
    response_model=MeasureResponse,
    summary="Get measure details",
    description="Get detailed information about a specific quality measure.",
)
async def get_measure(
    measure_id: str = Path(..., description="Measure ID"),
    include_performance: bool = Query(True, description="Include performance data"),
) -> MeasureResponse:
    """Get detailed information about a specific quality measure.

    Returns complete measure metadata including NQF ID, steward,
    description, rationale, and current performance if requested.
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

        # Generate mock performance if requested
        performance = None
        benchmark = None
        trend = None

        if include_performance:
            import random
            random.seed(hash(measure.id))
            rate = random.uniform(0.45, 0.90)
            denominator = random.randint(500, 3000)
            numerator = int(denominator * rate)
            excluded = random.randint(10, 100)

            performance = PerformanceRate(
                rate=round(rate, 3),
                rate_display=f"{rate*100:.1f}%",
                numerator=numerator,
                denominator=denominator,
                excluded=excluded,
                eligible_population=denominator + excluded,
            )

            star = 3
            if rate >= measure.benchmark_90th:
                star = 5
            elif rate >= (measure.benchmark_50th + measure.benchmark_90th) / 2:
                star = 4
            elif rate >= measure.benchmark_50th:
                star = 3
            elif rate >= measure.benchmark_50th * 0.8:
                star = 2
            else:
                star = 1

            benchmark = BenchmarkInfo(
                percentile_50th=measure.benchmark_50th,
                percentile_90th=measure.benchmark_90th,
                national_average=round((measure.benchmark_50th + measure.benchmark_90th) / 2, 3),
                star_rating=star,
                meets_benchmark=rate >= measure.benchmark_50th,
            )

            trend = generate_mock_trends(measure.id, 12)

        # Count mock gaps
        import random
        random.seed(hash(measure.id) + 1)
        total_gaps = random.randint(50, 500)
        critical_pct = 0.15 if measure.default_priority.value == "critical" else 0.08
        high_pct = 0.30 if measure.default_priority.value in ["critical", "high"] else 0.20

        return MeasureResponse(
            id=measure.id,
            name=measure.name,
            category=MeasureCategoryEnum(measure.category.value),
            measure_type=MeasureTypeEnum(measure.measure_type.value),
            version=measure.version,
            metadata=MeasureMetadata(
                nqf_id=measure.nqf_number,
                cms_id=measure.cms_id,
                steward=measure.steward,
                domain=measure.domain,
                description=measure.description,
                rationale=measure.clinical_guidance,
                specifications_url=measure.specifications_url,
            ),
            clinical_guidance=measure.clinical_guidance,
            default_priority=MeasurePriorityEnum(measure.default_priority.value),
            performance=performance,
            benchmark=benchmark,
            trend=trend,
            total_gaps=total_gaps,
            critical_gaps=int(total_gaps * critical_pct),
            high_priority_gaps=int(total_gaps * high_pct),
        )

    except NotFoundError:
        raise
    except Exception as e:
        logger.exception(f"Failed to get measure: {e}")
        raise InternalError(
            message=f"Failed to get measure: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/performance",
    response_model=PerformanceSummaryResponse,
    summary="Get overall performance summary",
    description="Get aggregate performance summary across all quality measures.",
)
async def get_performance_summary(
    time_period: TimePeriodEnum = Query(TimePeriodEnum.CURRENT_YEAR, description="Time period"),
    period_start: date | None = Query(None, description="Custom period start"),
    period_end: date | None = Query(None, description="Custom period end"),
) -> PerformanceSummaryResponse:
    """Get overall performance summary across all quality measures.

    Returns aggregate statistics including average performance,
    benchmark achievement, and gap counts.
    """
    request_id = str(uuid4())

    try:
        from app.services.quality_measures import get_quality_measure_service

        service = get_quality_measure_service()
        all_measures = service.get_all_measures()

        # Determine period
        if time_period == TimePeriodEnum.CUSTOM and period_start and period_end:
            p_start = period_start
            p_end = period_end
        else:
            p_end = date.today()
            if time_period == TimePeriodEnum.LAST_6_MONTHS:
                p_start = date(p_end.year, p_end.month - 6 if p_end.month > 6 else p_end.month + 6, 1)
                if p_end.month <= 6:
                    p_start = date(p_end.year - 1, p_end.month + 6, 1)
            elif time_period == TimePeriodEnum.LAST_12_MONTHS:
                p_start = date(p_end.year - 1, p_end.month, 1)
            else:
                p_start = date(p_end.year, 1, 1)

        # Calculate mock performance
        import random
        total_rates = []
        star_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        by_category: dict[str, dict[str, Any]] = {}
        total_gaps = 0
        critical_gaps = 0
        measures_meeting = 0

        for m in all_measures:
            random.seed(hash(m.id))
            rate = random.uniform(0.45, 0.90)
            total_rates.append(rate)

            if rate >= m.benchmark_50th:
                measures_meeting += 1

            # Star rating
            if rate >= m.benchmark_90th:
                star = 5
            elif rate >= (m.benchmark_50th + m.benchmark_90th) / 2:
                star = 4
            elif rate >= m.benchmark_50th:
                star = 3
            elif rate >= m.benchmark_50th * 0.8:
                star = 2
            else:
                star = 1
            star_distribution[star] += 1

            # Category aggregation
            cat = m.category.value
            if cat not in by_category:
                by_category[cat] = {
                    "measure_count": 0,
                    "average_rate": 0,
                    "rates": [],
                    "total_gaps": 0,
                    "critical_gaps": 0,
                }
            by_category[cat]["measure_count"] += 1
            by_category[cat]["rates"].append(rate)

            # Gaps
            random.seed(hash(m.id) + 1)
            gaps = random.randint(50, 500)
            total_gaps += gaps
            crit = int(gaps * 0.10)
            critical_gaps += crit
            by_category[cat]["total_gaps"] += gaps
            by_category[cat]["critical_gaps"] += crit

        # Finalize category averages
        for cat in by_category:
            rates = by_category[cat].pop("rates")
            by_category[cat]["average_rate"] = round(sum(rates) / len(rates), 3) if rates else 0

        avg_perf = sum(total_rates) / len(total_rates) if total_rates else 0

        return PerformanceSummaryResponse(
            request_id=request_id,
            period_start=p_start,
            period_end=p_end,
            total_measures=len(all_measures),
            measures_meeting_benchmark=measures_meeting,
            average_performance=round(avg_perf, 3),
            total_gaps=total_gaps,
            critical_gaps=critical_gaps,
            gap_closure_rate=0.12,  # Mock: 12% closure rate
            by_category=by_category,
            star_distribution=star_distribution,
        )

    except Exception as e:
        logger.exception(f"Failed to get performance summary: {e}")
        raise InternalError(
            message=f"Failed to get performance summary: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/gaps",
    response_model=GapListResponse,
    summary="Get patient gaps list",
    description="Get list of patient care gaps with filtering options.",
)
async def list_gaps(
    measure: str | None = Query(None, description="Filter by measure ID"),
    provider: str | None = Query(None, description="Filter by provider ID"),
    priority: MeasurePriorityEnum | None = Query(None, description="Filter by priority"),
    category: MeasureCategoryEnum | None = Query(None, description="Filter by category"),
    status: str = Query("open", description="Filter by status: open, scheduled, closed"),
    limit: int = Query(100, ge=1, le=500, description="Maximum gaps to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> GapListResponse:
    """Get list of patient care gaps.

    Returns patients with open care gaps, sorted by priority and due date.
    Supports filtering by measure, provider, priority, and category.
    """
    request_id = str(uuid4())

    try:
        gaps = generate_mock_patient_gaps(
            measure_filter=measure,
            provider_filter=provider,
            priority_filter=priority,
            limit=limit + offset,
        )

        # Filter by category if specified
        if category:
            gaps = [g for g in gaps if g.category == category]

        # Apply pagination
        paginated = gaps[offset:offset + limit]

        # Count by priority
        total_critical = sum(1 for g in gaps if g.priority == MeasurePriorityEnum.CRITICAL)
        total_high = sum(1 for g in gaps if g.priority == MeasurePriorityEnum.HIGH)
        total_medium = sum(1 for g in gaps if g.priority == MeasurePriorityEnum.MEDIUM)
        total_low = sum(1 for g in gaps if g.priority == MeasurePriorityEnum.LOW)

        return GapListResponse(
            request_id=request_id,
            total=len(gaps),
            total_critical=total_critical,
            total_high=total_high,
            total_medium=total_medium,
            total_low=total_low,
            gaps=paginated,
        )

    except Exception as e:
        logger.exception(f"Failed to list gaps: {e}")
        raise InternalError(
            message=f"Failed to list gaps: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/gaps/{patient_id}",
    response_model=GapListResponse,
    summary="Get patient's care gaps",
    description="Get all care gaps for a specific patient.",
)
async def get_patient_gaps(
    patient_id: str = Path(..., description="Patient ID"),
    priority: MeasurePriorityEnum | None = Query(None, description="Filter by priority"),
) -> GapListResponse:
    """Get care gaps for a specific patient.

    Returns all open care gaps for the patient, sorted by priority.
    """
    request_id = str(uuid4())

    try:
        all_gaps = generate_mock_patient_gaps(limit=500)

        # Filter by patient
        patient_gaps = [g for g in all_gaps if g.patient_id == patient_id]

        # Filter by priority if specified
        if priority:
            patient_gaps = [g for g in patient_gaps if g.priority == priority]

        # Count by priority
        total_critical = sum(1 for g in patient_gaps if g.priority == MeasurePriorityEnum.CRITICAL)
        total_high = sum(1 for g in patient_gaps if g.priority == MeasurePriorityEnum.HIGH)
        total_medium = sum(1 for g in patient_gaps if g.priority == MeasurePriorityEnum.MEDIUM)
        total_low = sum(1 for g in patient_gaps if g.priority == MeasurePriorityEnum.LOW)

        return GapListResponse(
            request_id=request_id,
            total=len(patient_gaps),
            total_critical=total_critical,
            total_high=total_high,
            total_medium=total_medium,
            total_low=total_low,
            gaps=patient_gaps,
        )

    except Exception as e:
        logger.exception(f"Failed to get patient gaps: {e}")
        raise InternalError(
            message=f"Failed to get patient gaps: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/gaps/{gap_id}/close",
    response_model=CloseGapResponse,
    summary="Mark gap as closed",
    description="Mark a care gap as closed with closure reason and date.",
)
async def close_gap(
    gap_id: str = Path(..., description="Gap ID to close"),
    request: CloseGapRequest = Body(...),
) -> CloseGapResponse:
    """Mark a care gap as closed.

    Records the closure reason, code, and date. This is typically
    called after a patient completes the required service.
    """
    request_id = str(uuid4())

    try:
        # In production, this would update the database
        # For now, return mock response
        closure_date = request.closure_date or date.today()

        return CloseGapResponse(
            request_id=request_id,
            gap_id=gap_id,
            patient_id="P001",  # Would be looked up from gap_id
            measure_id="HEDIS-CDC-HBA1C",  # Would be looked up
            status="closed",
            closed_date=closure_date,
            closed_by="current_user",  # Would come from auth
        )

    except Exception as e:
        logger.exception(f"Failed to close gap: {e}")
        raise InternalError(
            message=f"Failed to close gap: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/trends",
    response_model=TrendResponse,
    summary="Get performance trends",
    description="Get performance trends over time for overall or specific measure.",
)
async def get_trends(
    measure_id: str | None = Query(None, description="Specific measure ID (overall if not provided)"),
    period_type: str = Query("monthly", description="Period type: monthly, quarterly, yearly"),
    periods: int = Query(12, ge=3, le=36, description="Number of periods to include"),
) -> TrendResponse:
    """Get performance trends over time.

    Returns trend data showing performance changes over the specified
    time periods. Can be overall or for a specific measure.
    """
    request_id = str(uuid4())

    try:
        trend_data = generate_mock_trends(measure_id, periods)

        # Determine overall direction
        if len(trend_data) >= 2:
            first_half = trend_data[:len(trend_data)//2]
            second_half = trend_data[len(trend_data)//2:]
            first_avg = sum(t.rate for t in first_half) / len(first_half)
            second_avg = sum(t.rate for t in second_half) / len(second_half)

            if second_avg > first_avg + 0.02:
                direction = "improving"
            elif second_avg < first_avg - 0.02:
                direction = "declining"
            else:
                direction = "stable"

            change = round(trend_data[-1].rate - trend_data[-2].rate, 3) if len(trend_data) >= 2 else None
        else:
            direction = "stable"
            change = None

        return TrendResponse(
            request_id=request_id,
            measure_id=measure_id,
            period_type=period_type,
            trend_data=trend_data,
            overall_direction=direction,
            change_from_previous=change,
        )

    except Exception as e:
        logger.exception(f"Failed to get trends: {e}")
        raise InternalError(
            message=f"Failed to get trends: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )
