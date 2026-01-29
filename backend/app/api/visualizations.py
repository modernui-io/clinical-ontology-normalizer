"""Visualization API endpoints for advanced clinical analytics."""

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.visualization_data_service import (
    get_visualization_data_service,
    SankeyData,
    SurvivalData,
    GeospatialData,
    ForestPlotData,
    VolcanoData,
    TimelineData,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visualizations", tags=["Visualizations"])


# ==============================================================================
# Response Models
# ==============================================================================


class SankeyNodeResponse(BaseModel):
    """Sankey diagram node."""
    id: str
    name: str
    category: str
    value: int = 0


class SankeyLinkResponse(BaseModel):
    """Sankey diagram link."""
    source: str
    target: str
    value: int


class SankeyResponse(BaseModel):
    """Treatment pathway Sankey diagram response."""
    nodes: list[SankeyNodeResponse]
    links: list[SankeyLinkResponse]
    total_patients: int
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SurvivalPointResponse(BaseModel):
    """Survival curve point."""
    time: float
    survival_probability: float
    at_risk: int
    events: int
    censored: int
    ci_lower: float | None = None
    ci_upper: float | None = None


class SurvivalCurveResponse(BaseModel):
    """Survival curve for a cohort."""
    cohort_id: str
    cohort_name: str
    points: list[SurvivalPointResponse]
    median_survival: float | None
    events_total: int
    censored_total: int
    patients_total: int


class SurvivalResponse(BaseModel):
    """Kaplan-Meier survival analysis response."""
    curves: list[SurvivalCurveResponse]
    log_rank_p_value: float | None
    hazard_ratio: float | None
    hazard_ratio_ci: list[float] | None
    time_unit: str = "months"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GeospatialRegionResponse(BaseModel):
    """Health data for a geographic region."""
    region_id: str
    region_name: str
    state_code: str | None
    latitude: float
    longitude: float
    metric_value: float
    metric_label: str
    population: int
    patient_count: int
    confidence_interval: list[float] | None = None
    trend: str | None = None


class GeospatialResponse(BaseModel):
    """Geospatial health mapping response."""
    regions: list[GeospatialRegionResponse]
    metric_name: str
    metric_unit: str
    min_value: float
    max_value: float
    national_average: float
    time_period: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ForestPlotStudyResponse(BaseModel):
    """Single study in a forest plot."""
    study_id: str
    study_name: str
    year: int
    effect_size: float
    ci_lower: float
    ci_upper: float
    weight: float
    sample_size: int
    events_treatment: int | None = None
    events_control: int | None = None
    n_treatment: int | None = None
    n_control: int | None = None


class ForestPlotResponse(BaseModel):
    """Meta-analysis forest plot response."""
    studies: list[ForestPlotStudyResponse]
    pooled_effect: float
    pooled_ci_lower: float
    pooled_ci_upper: float
    heterogeneity_i2: float
    heterogeneity_q: float
    heterogeneity_p: float
    effect_measure: str
    null_value: float = 1.0
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VolcanoPointResponse(BaseModel):
    """Volcano plot point."""
    id: str
    name: str
    log_fold_change: float
    neg_log_p_value: float
    p_value: float
    significant: bool
    direction: str
    category: str | None = None


class VolcanoResponse(BaseModel):
    """Differential analysis volcano plot response."""
    points: list[VolcanoPointResponse]
    fc_threshold: float
    p_threshold: float
    total_features: int
    significant_up: int
    significant_down: int
    comparison: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TimelineMilestone(BaseModel):
    """Timeline event milestone."""
    name: str
    date: str


class TimelineEventResponse(BaseModel):
    """Timeline event."""
    id: str
    name: str
    start_date: str
    end_date: str | None
    category: str
    status: str
    progress: float
    milestones: list[TimelineMilestone] = []
    dependencies: list[str] = []


class TimelineResponse(BaseModel):
    """Study timeline Gantt chart response."""
    events: list[TimelineEventResponse]
    study_name: str
    study_start: str
    study_end: str | None
    categories: list[str]
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==============================================================================
# Helper Functions
# ==============================================================================


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert dataclass to dictionary, handling nested objects."""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for key, value in asdict(obj).items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, tuple):
                result[key] = list(value)
            else:
                result[key] = value
        return result
    return obj


# ==============================================================================
# Endpoints
# ==============================================================================


@router.get(
    "/sankey",
    response_model=SankeyResponse,
    summary="Get treatment pathway Sankey data",
    description="Generate treatment pathway Sankey diagram data showing patient flow through treatment stages.",
)
async def get_sankey_data(
    cohort_id: str | None = Query(None, description="Filter by cohort ID"),
    time_period: str | None = Query(None, description="Time period (e.g., '2024', 'Q1-2024')"),
    pathway_type: str = Query("treatment", description="Pathway type: treatment, diagnosis, care"),
) -> SankeyResponse:
    """Get treatment pathway Sankey diagram data.

    Shows patient flow from diagnosis through treatment stages to outcomes.
    Useful for understanding treatment patterns and outcomes distribution.
    """
    service = get_visualization_data_service()
    data = service.generate_sankey_data(
        cohort_id=cohort_id,
        time_period=time_period,
        pathway_type=pathway_type,
    )

    return SankeyResponse(
        nodes=[SankeyNodeResponse(**_dataclass_to_dict(n)) for n in data.nodes],
        links=[SankeyLinkResponse(**_dataclass_to_dict(l)) for l in data.links],
        total_patients=data.total_patients,
    )


@router.get(
    "/survival",
    response_model=SurvivalResponse,
    summary="Get Kaplan-Meier survival data",
    description="Calculate Kaplan-Meier survival curves for cohort comparison.",
)
async def get_survival_data(
    cohort_ids: list[str] | None = Query(None, description="Cohort IDs to compare"),
    endpoint: str = Query("overall_survival", description="Survival endpoint type"),
    max_time: int = Query(60, ge=12, le=120, description="Maximum follow-up time in months"),
) -> SurvivalResponse:
    """Get Kaplan-Meier survival analysis data.

    Compares survival curves between cohorts with:
    - Survival probability over time
    - Confidence intervals
    - Log-rank test p-value
    - Hazard ratio with CI
    - Risk table data
    """
    service = get_visualization_data_service()
    data = service.calculate_survival_data(
        cohort_ids=cohort_ids,
        endpoint=endpoint,
        max_time=max_time,
    )

    curves = []
    for curve in data.curves:
        points = [SurvivalPointResponse(**_dataclass_to_dict(p)) for p in curve.points]
        curves.append(
            SurvivalCurveResponse(
                cohort_id=curve.cohort_id,
                cohort_name=curve.cohort_name,
                points=points,
                median_survival=curve.median_survival,
                events_total=curve.events_total,
                censored_total=curve.censored_total,
                patients_total=curve.patients_total,
            )
        )

    return SurvivalResponse(
        curves=curves,
        log_rank_p_value=data.log_rank_p_value,
        hazard_ratio=data.hazard_ratio,
        hazard_ratio_ci=list(data.hazard_ratio_ci) if data.hazard_ratio_ci else None,
        time_unit=data.time_unit,
    )


@router.get(
    "/geospatial",
    response_model=GeospatialResponse,
    summary="Get regional health data",
    description="Aggregate health metrics by geographic region for choropleth mapping.",
)
async def get_geospatial_data(
    metric: str = Query("prevalence", description="Health metric: prevalence, incidence, mortality, outcomes"),
    condition: str | None = Query(None, description="Condition filter (e.g., diabetes, hypertension)"),
    time_period: str | None = Query(None, description="Time period for data"),
    granularity: str = Query("state", description="Geographic granularity: state, county, zip"),
) -> GeospatialResponse:
    """Get geospatial health mapping data.

    Aggregates health metrics by region for choropleth visualization:
    - Regional health statistics
    - Population-adjusted metrics
    - Confidence intervals
    - Trend indicators
    """
    service = get_visualization_data_service()
    data = service.aggregate_geospatial_data(
        metric=metric,
        condition=condition,
        time_period=time_period,
        granularity=granularity,
    )

    regions = []
    for region in data.regions:
        regions.append(
            GeospatialRegionResponse(
                region_id=region.region_id,
                region_name=region.region_name,
                state_code=region.state_code,
                latitude=region.latitude,
                longitude=region.longitude,
                metric_value=region.metric_value,
                metric_label=region.metric_label,
                population=region.population,
                patient_count=region.patient_count,
                confidence_interval=list(region.confidence_interval) if region.confidence_interval else None,
                trend=region.trend,
            )
        )

    return GeospatialResponse(
        regions=regions,
        metric_name=data.metric_name,
        metric_unit=data.metric_unit,
        min_value=data.min_value,
        max_value=data.max_value,
        national_average=data.national_average,
        time_period=data.time_period,
    )


@router.get(
    "/forest",
    response_model=ForestPlotResponse,
    summary="Get forest plot data",
    description="Prepare meta-analysis forest plot data with effect sizes and pooled estimates.",
)
async def get_forest_plot_data(
    meta_analysis_id: str | None = Query(None, description="Meta-analysis ID"),
    effect_measure: str = Query("OR", description="Effect measure: OR, RR, HR, MD, SMD"),
) -> ForestPlotResponse:
    """Get meta-analysis forest plot data.

    Provides study-level and pooled effect estimates for forest plot visualization:
    - Individual study effect sizes with confidence intervals
    - Study weights
    - Pooled effect estimate
    - Heterogeneity statistics (I², Q, p-value)
    """
    service = get_visualization_data_service()
    data = service.prepare_forest_plot_data(
        meta_analysis_id=meta_analysis_id,
        effect_measure=effect_measure,
    )

    studies = [ForestPlotStudyResponse(**_dataclass_to_dict(s)) for s in data.studies]

    return ForestPlotResponse(
        studies=studies,
        pooled_effect=data.pooled_effect,
        pooled_ci_lower=data.pooled_ci_lower,
        pooled_ci_upper=data.pooled_ci_upper,
        heterogeneity_i2=data.heterogeneity_i2,
        heterogeneity_q=data.heterogeneity_q,
        heterogeneity_p=data.heterogeneity_p,
        effect_measure=data.effect_measure,
        null_value=data.null_value,
    )


@router.get(
    "/volcano",
    response_model=VolcanoResponse,
    summary="Get volcano plot data",
    description="Prepare differential analysis volcano plot data with fold changes and p-values.",
)
async def get_volcano_data(
    analysis_id: str | None = Query(None, description="Differential analysis ID"),
    fc_threshold: float = Query(1.0, ge=0.5, le=2.0, description="Log2 fold change threshold"),
    p_threshold: float = Query(0.05, ge=0.001, le=0.1, description="P-value threshold"),
) -> VolcanoResponse:
    """Get differential analysis volcano plot data.

    Provides log fold change vs significance data for volcano plot visualization:
    - Feature-level fold changes and p-values
    - Significance thresholds
    - Up/down regulation counts
    """
    service = get_visualization_data_service()
    data = service.prepare_volcano_data(
        analysis_id=analysis_id,
        fc_threshold=fc_threshold,
        p_threshold=p_threshold,
    )

    points = [VolcanoPointResponse(**_dataclass_to_dict(p)) for p in data.points]

    return VolcanoResponse(
        points=points,
        fc_threshold=data.fc_threshold,
        p_threshold=data.p_threshold,
        total_features=data.total_features,
        significant_up=data.significant_up,
        significant_down=data.significant_down,
        comparison=data.comparison,
    )


@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Get study timeline data",
    description="Generate study timeline Gantt chart data with events and milestones.",
)
async def get_timeline_data(
    study_id: str | None = Query(None, description="Clinical study ID"),
) -> TimelineResponse:
    """Get study timeline Gantt chart data.

    Provides study event timeline for Gantt chart visualization:
    - Study phases and events
    - Start/end dates
    - Progress tracking
    - Milestones
    - Dependencies between events
    """
    service = get_visualization_data_service()
    data = service.generate_timeline_data(study_id=study_id)

    events = []
    for event in data.events:
        milestones = [TimelineMilestone(**m) for m in event.milestones]
        events.append(
            TimelineEventResponse(
                id=event.id,
                name=event.name,
                start_date=event.start_date.isoformat(),
                end_date=event.end_date.isoformat() if event.end_date else None,
                category=event.category,
                status=event.status,
                progress=event.progress,
                milestones=milestones,
                dependencies=event.dependencies,
            )
        )

    return TimelineResponse(
        events=events,
        study_name=data.study_name,
        study_start=data.study_start.isoformat(),
        study_end=data.study_end.isoformat() if data.study_end else None,
        categories=data.categories,
    )


@router.get(
    "/stats",
    summary="Get visualization service statistics",
    description="Get statistics about the visualization data service.",
)
async def get_visualization_stats() -> dict[str, Any]:
    """Get visualization service statistics."""
    service = get_visualization_data_service()
    return service.get_stats()
