"""Visualization data preparation service for advanced clinical analytics.

This service provides data preparation functions for various visualization types:
- Treatment pathway Sankey diagrams
- Kaplan-Meier survival analysis
- Geospatial health mapping
- Forest plots for meta-analysis
- Volcano plots for differential analysis
- Study timeline Gantt charts
"""

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================


class CohortType(str, Enum):
    """Types of patient cohorts for analysis."""
    TREATMENT = "treatment"
    CONTROL = "control"
    INTERVENTION = "intervention"
    PLACEBO = "placebo"


@dataclass
class SankeyNode:
    """Node in a Sankey diagram."""
    id: str
    name: str
    category: str
    value: int = 0


@dataclass
class SankeyLink:
    """Link between nodes in a Sankey diagram."""
    source: str
    target: str
    value: int


@dataclass
class SankeyData:
    """Complete Sankey diagram data."""
    nodes: list[SankeyNode]
    links: list[SankeyLink]
    total_patients: int


@dataclass
class SurvivalPoint:
    """Single point on a survival curve."""
    time: float  # Time in months
    survival_probability: float
    at_risk: int
    events: int
    censored: int
    ci_lower: float | None = None
    ci_upper: float | None = None


@dataclass
class SurvivalCurve:
    """Complete survival curve for a cohort."""
    cohort_id: str
    cohort_name: str
    points: list[SurvivalPoint]
    median_survival: float | None
    events_total: int
    censored_total: int
    patients_total: int


@dataclass
class SurvivalData:
    """Kaplan-Meier survival analysis data."""
    curves: list[SurvivalCurve]
    log_rank_p_value: float | None
    hazard_ratio: float | None
    hazard_ratio_ci: tuple[float, float] | None
    time_unit: str = "months"


@dataclass
class GeospatialRegion:
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
    confidence_interval: tuple[float, float] | None = None
    trend: str | None = None  # "increasing", "decreasing", "stable"
    sub_regions: list["GeospatialRegion"] = field(default_factory=list)


@dataclass
class GeospatialData:
    """Geospatial health mapping data."""
    regions: list[GeospatialRegion]
    metric_name: str
    metric_unit: str
    min_value: float
    max_value: float
    national_average: float
    time_period: str


@dataclass
class ForestPlotStudy:
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


@dataclass
class ForestPlotData:
    """Meta-analysis forest plot data."""
    studies: list[ForestPlotStudy]
    pooled_effect: float
    pooled_ci_lower: float
    pooled_ci_upper: float
    heterogeneity_i2: float
    heterogeneity_q: float
    heterogeneity_p: float
    effect_measure: str  # "OR", "RR", "HR", "MD", "SMD"
    null_value: float = 1.0  # 1 for ratios, 0 for differences


@dataclass
class VolcanoPoint:
    """Single point in a volcano plot."""
    id: str
    name: str
    log_fold_change: float
    neg_log_p_value: float
    p_value: float
    significant: bool
    direction: str  # "up", "down", "none"
    category: str | None = None


@dataclass
class VolcanoData:
    """Differential analysis volcano plot data."""
    points: list[VolcanoPoint]
    fc_threshold: float
    p_threshold: float
    total_features: int
    significant_up: int
    significant_down: int
    comparison: str  # e.g., "Treatment vs Control"


@dataclass
class TimelineEvent:
    """Event in a study timeline."""
    id: str
    name: str
    start_date: datetime
    end_date: datetime | None
    category: str
    status: str  # "planned", "in_progress", "completed", "delayed"
    progress: float  # 0-100
    milestones: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class TimelineData:
    """Study timeline Gantt chart data."""
    events: list[TimelineEvent]
    study_name: str
    study_start: datetime
    study_end: datetime | None
    categories: list[str]


# ==============================================================================
# Visualization Data Service
# ==============================================================================


class VisualizationDataService:
    """Service for preparing visualization data for clinical analytics."""

    def __init__(self) -> None:
        """Initialize the visualization data service."""
        self._initialized = True
        logger.info("VisualizationDataService initialized")

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "service": "visualization_data",
            "status": "active",
            "supported_visualizations": [
                "sankey",
                "survival",
                "geospatial",
                "forest",
                "volcano",
                "timeline",
            ],
        }

    # ==========================================================================
    # Treatment Pathway Sankey
    # ==========================================================================

    def generate_sankey_data(
        self,
        cohort_id: str | None = None,
        time_period: str | None = None,
        pathway_type: str = "treatment",
    ) -> SankeyData:
        """Generate treatment pathway Sankey diagram data.

        Args:
            cohort_id: Optional cohort filter
            time_period: Time period filter (e.g., "2023", "Q1-2024")
            pathway_type: Type of pathway ("treatment", "diagnosis", "care")

        Returns:
            SankeyData with nodes and links for visualization
        """
        # Mock data for demonstration - in production, query from database
        nodes = [
            # Initial diagnosis
            SankeyNode("diagnosis_dm2", "Type 2 Diabetes", "diagnosis", 1500),
            SankeyNode("diagnosis_htn", "Hypertension", "diagnosis", 1200),
            SankeyNode("diagnosis_cad", "Coronary Artery Disease", "diagnosis", 800),
            # First-line treatment
            SankeyNode("tx1_metformin", "Metformin", "first_line", 1200),
            SankeyNode("tx1_lisinopril", "Lisinopril", "first_line", 900),
            SankeyNode("tx1_aspirin", "Aspirin", "first_line", 600),
            SankeyNode("tx1_statin", "Statin", "first_line", 800),
            # Second-line treatment
            SankeyNode("tx2_sulfonylurea", "Sulfonylurea", "second_line", 400),
            SankeyNode("tx2_glp1", "GLP-1 Agonist", "second_line", 350),
            SankeyNode("tx2_sglt2", "SGLT2 Inhibitor", "second_line", 450),
            SankeyNode("tx2_insulin", "Insulin", "second_line", 300),
            SankeyNode("tx2_arb", "ARB", "second_line", 250),
            # Outcomes
            SankeyNode("outcome_controlled", "Well Controlled", "outcome", 1800),
            SankeyNode("outcome_improved", "Improved", "outcome", 900),
            SankeyNode("outcome_unchanged", "Unchanged", "outcome", 500),
            SankeyNode("outcome_progressed", "Progressed", "outcome", 300),
        ]

        links = [
            # Diagnosis to first-line
            SankeyLink("diagnosis_dm2", "tx1_metformin", 1200),
            SankeyLink("diagnosis_dm2", "tx1_statin", 500),
            SankeyLink("diagnosis_htn", "tx1_lisinopril", 900),
            SankeyLink("diagnosis_htn", "tx1_statin", 400),
            SankeyLink("diagnosis_cad", "tx1_aspirin", 600),
            SankeyLink("diagnosis_cad", "tx1_statin", 700),
            # First-line to second-line (treatment escalation)
            SankeyLink("tx1_metformin", "tx2_sulfonylurea", 300),
            SankeyLink("tx1_metformin", "tx2_glp1", 350),
            SankeyLink("tx1_metformin", "tx2_sglt2", 350),
            SankeyLink("tx1_metformin", "tx2_insulin", 200),
            SankeyLink("tx1_lisinopril", "tx2_arb", 250),
            # First-line to outcomes (responders)
            SankeyLink("tx1_metformin", "outcome_controlled", 500),
            SankeyLink("tx1_lisinopril", "outcome_controlled", 400),
            SankeyLink("tx1_aspirin", "outcome_controlled", 300),
            SankeyLink("tx1_statin", "outcome_controlled", 350),
            # Second-line to outcomes
            SankeyLink("tx2_sulfonylurea", "outcome_controlled", 150),
            SankeyLink("tx2_sulfonylurea", "outcome_improved", 150),
            SankeyLink("tx2_sulfonylurea", "outcome_unchanged", 100),
            SankeyLink("tx2_glp1", "outcome_controlled", 200),
            SankeyLink("tx2_glp1", "outcome_improved", 100),
            SankeyLink("tx2_glp1", "outcome_unchanged", 50),
            SankeyLink("tx2_sglt2", "outcome_controlled", 250),
            SankeyLink("tx2_sglt2", "outcome_improved", 150),
            SankeyLink("tx2_sglt2", "outcome_unchanged", 50),
            SankeyLink("tx2_insulin", "outcome_improved", 150),
            SankeyLink("tx2_insulin", "outcome_unchanged", 100),
            SankeyLink("tx2_insulin", "outcome_progressed", 50),
            SankeyLink("tx2_arb", "outcome_controlled", 150),
            SankeyLink("tx2_arb", "outcome_improved", 100),
        ]

        total_patients = sum(n.value for n in nodes if n.category == "diagnosis")

        return SankeyData(nodes=nodes, links=links, total_patients=total_patients)

    # ==========================================================================
    # Kaplan-Meier Survival Analysis
    # ==========================================================================

    def calculate_survival_data(
        self,
        cohort_ids: list[str] | None = None,
        endpoint: str = "overall_survival",
        max_time: int = 60,
    ) -> SurvivalData:
        """Calculate Kaplan-Meier survival curves.

        Args:
            cohort_ids: List of cohort IDs to compare
            endpoint: Survival endpoint ("overall_survival", "progression_free", "event_free")
            max_time: Maximum follow-up time in months

        Returns:
            SurvivalData with curves and statistical comparisons
        """
        # Generate mock survival curves for demonstration
        curves = []

        # Treatment cohort - better survival
        treatment_points = self._generate_survival_curve(
            initial_survival=1.0,
            hazard_rate=0.015,
            max_time=max_time,
            initial_at_risk=500,
            median_survival=48,
        )
        curves.append(
            SurvivalCurve(
                cohort_id="treatment",
                cohort_name="Treatment Group",
                points=treatment_points,
                median_survival=48,
                events_total=sum(p.events for p in treatment_points),
                censored_total=sum(p.censored for p in treatment_points),
                patients_total=500,
            )
        )

        # Control cohort - worse survival
        control_points = self._generate_survival_curve(
            initial_survival=1.0,
            hazard_rate=0.025,
            max_time=max_time,
            initial_at_risk=500,
            median_survival=32,
        )
        curves.append(
            SurvivalCurve(
                cohort_id="control",
                cohort_name="Control Group",
                points=control_points,
                median_survival=32,
                events_total=sum(p.events for p in control_points),
                censored_total=sum(p.censored for p in control_points),
                patients_total=500,
            )
        )

        return SurvivalData(
            curves=curves,
            log_rank_p_value=0.0023,
            hazard_ratio=0.65,
            hazard_ratio_ci=(0.48, 0.88),
            time_unit="months",
        )

    def _generate_survival_curve(
        self,
        initial_survival: float,
        hazard_rate: float,
        max_time: int,
        initial_at_risk: int,
        median_survival: float,
    ) -> list[SurvivalPoint]:
        """Generate a mock survival curve with realistic patterns."""
        points = []
        at_risk = initial_at_risk
        survival = initial_survival

        for t in range(0, max_time + 1, 3):  # Every 3 months
            # Exponential survival with some noise
            base_survival = math.exp(-hazard_rate * t)
            noise = random.uniform(-0.02, 0.02) if t > 0 else 0
            survival = max(0, min(1, base_survival + noise))

            # Calculate events and censored
            if t > 0:
                expected_drop = at_risk * (1 - math.exp(-hazard_rate * 3))
                events = int(expected_drop * 0.7 + random.randint(-2, 2))
                events = max(0, min(events, at_risk))
                censored = int(expected_drop * 0.3 + random.randint(-1, 1))
                censored = max(0, min(censored, at_risk - events))
                at_risk = max(0, at_risk - events - censored)
            else:
                events = 0
                censored = 0

            # 95% confidence interval (simplified)
            se = 0.02 + (t / max_time) * 0.05
            ci_lower = max(0, survival - 1.96 * se)
            ci_upper = min(1, survival + 1.96 * se)

            points.append(
                SurvivalPoint(
                    time=float(t),
                    survival_probability=survival,
                    at_risk=at_risk,
                    events=events,
                    censored=censored,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                )
            )

        return points

    # ==========================================================================
    # Geospatial Health Mapping
    # ==========================================================================

    def aggregate_geospatial_data(
        self,
        metric: str = "prevalence",
        condition: str | None = None,
        time_period: str | None = None,
        granularity: str = "state",
    ) -> GeospatialData:
        """Aggregate health data by geographic region.

        Args:
            metric: Health metric ("prevalence", "incidence", "mortality", "outcomes")
            condition: Condition filter (e.g., "diabetes", "hypertension")
            time_period: Time period for data
            granularity: Geographic granularity ("state", "county", "zip")

        Returns:
            GeospatialData with regional health statistics
        """
        # Mock US state data
        states_data = [
            ("AL", "Alabama", 32.806671, -86.791130, 5.0, 4903000),
            ("AK", "Alaska", 61.370716, -152.404419, 4.2, 731000),
            ("AZ", "Arizona", 33.729759, -111.431221, 5.8, 7279000),
            ("AR", "Arkansas", 34.969704, -92.373123, 6.1, 3018000),
            ("CA", "California", 36.116203, -119.681564, 4.9, 39512000),
            ("CO", "Colorado", 39.059811, -105.311104, 4.1, 5774000),
            ("CT", "Connecticut", 41.597782, -72.755371, 4.5, 3565000),
            ("DE", "Delaware", 39.318523, -75.507141, 5.2, 974000),
            ("FL", "Florida", 27.766279, -81.686783, 5.6, 21478000),
            ("GA", "Georgia", 33.040619, -83.643074, 5.7, 10617000),
            ("HI", "Hawaii", 21.094318, -157.498337, 4.0, 1416000),
            ("ID", "Idaho", 44.240459, -114.478828, 4.8, 1839000),
            ("IL", "Illinois", 40.349457, -88.986137, 5.1, 12672000),
            ("IN", "Indiana", 39.849426, -86.258278, 5.4, 6733000),
            ("IA", "Iowa", 42.011539, -93.210526, 4.9, 3155000),
            ("KS", "Kansas", 38.526600, -96.726486, 5.0, 2913000),
            ("KY", "Kentucky", 37.668140, -84.670067, 6.3, 4468000),
            ("LA", "Louisiana", 31.169546, -91.867805, 6.5, 4649000),
            ("ME", "Maine", 44.693947, -69.381927, 4.7, 1344000),
            ("MD", "Maryland", 39.063946, -76.802101, 5.0, 6046000),
            ("MA", "Massachusetts", 42.230171, -71.530106, 4.3, 6893000),
            ("MI", "Michigan", 43.326618, -84.536095, 5.3, 9987000),
            ("MN", "Minnesota", 45.694454, -93.900192, 4.4, 5640000),
            ("MS", "Mississippi", 32.741646, -89.678696, 7.2, 2976000),
            ("MO", "Missouri", 38.456085, -92.288368, 5.5, 6137000),
            ("MT", "Montana", 46.921925, -110.454353, 4.6, 1069000),
            ("NE", "Nebraska", 41.125370, -98.268082, 4.7, 1934000),
            ("NV", "Nevada", 38.313515, -117.055374, 5.4, 3080000),
            ("NH", "New Hampshire", 43.452492, -71.563896, 4.4, 1360000),
            ("NJ", "New Jersey", 40.298904, -74.521011, 4.8, 8882000),
            ("NM", "New Mexico", 34.840515, -106.248482, 5.9, 2097000),
            ("NY", "New York", 42.165726, -74.948051, 4.9, 19454000),
            ("NC", "North Carolina", 35.630066, -79.806419, 5.6, 10489000),
            ("ND", "North Dakota", 47.528912, -99.784012, 4.5, 762000),
            ("OH", "Ohio", 40.388783, -82.764915, 5.5, 11689000),
            ("OK", "Oklahoma", 35.565342, -96.928917, 6.2, 3957000),
            ("OR", "Oregon", 44.572021, -122.070938, 4.5, 4218000),
            ("PA", "Pennsylvania", 40.590752, -77.209755, 5.2, 12802000),
            ("RI", "Rhode Island", 41.680893, -71.511780, 4.6, 1059000),
            ("SC", "South Carolina", 33.856892, -80.945007, 5.8, 5149000),
            ("SD", "South Dakota", 44.299782, -99.438828, 4.8, 885000),
            ("TN", "Tennessee", 35.747845, -86.692345, 6.0, 6829000),
            ("TX", "Texas", 31.054487, -97.563461, 5.7, 29000000),
            ("UT", "Utah", 40.150032, -111.862434, 3.9, 3206000),
            ("VT", "Vermont", 44.045876, -72.710686, 4.3, 623000),
            ("VA", "Virginia", 37.769337, -78.169968, 5.0, 8536000),
            ("WA", "Washington", 47.400902, -121.490494, 4.4, 7615000),
            ("WV", "West Virginia", 38.491226, -80.954453, 7.0, 1792000),
            ("WI", "Wisconsin", 44.268543, -89.616508, 4.8, 5822000),
            ("WY", "Wyoming", 42.755966, -107.302490, 4.5, 579000),
        ]

        regions = []
        values = []

        for state_code, state_name, lat, lon, base_rate, pop in states_data:
            # Add some variation to base rate
            rate = base_rate + random.uniform(-0.5, 0.5)
            rate = max(3.0, min(8.0, rate))
            values.append(rate)

            patient_count = int(pop * rate / 100)

            # Determine trend
            trend_val = random.choice(["increasing", "decreasing", "stable"])

            regions.append(
                GeospatialRegion(
                    region_id=state_code.lower(),
                    region_name=state_name,
                    state_code=state_code,
                    latitude=lat,
                    longitude=lon,
                    metric_value=round(rate, 1),
                    metric_label=f"{rate:.1f}%",
                    population=pop,
                    patient_count=patient_count,
                    confidence_interval=(round(rate - 0.3, 1), round(rate + 0.3, 1)),
                    trend=trend_val,
                )
            )

        return GeospatialData(
            regions=regions,
            metric_name=f"{condition or 'Diabetes'} {metric.title()}",
            metric_unit="%",
            min_value=min(values),
            max_value=max(values),
            national_average=sum(values) / len(values),
            time_period=time_period or "2024",
        )

    # ==========================================================================
    # Forest Plot (Meta-Analysis)
    # ==========================================================================

    def prepare_forest_plot_data(
        self,
        meta_analysis_id: str | None = None,
        effect_measure: str = "OR",
    ) -> ForestPlotData:
        """Prepare forest plot data for meta-analysis visualization.

        Args:
            meta_analysis_id: ID of saved meta-analysis
            effect_measure: Effect measure type ("OR", "RR", "HR", "MD", "SMD")

        Returns:
            ForestPlotData with study effects and pooled estimate
        """
        # Mock meta-analysis data
        studies = [
            ForestPlotStudy(
                study_id="1",
                study_name="Smith et al.",
                year=2019,
                effect_size=0.72,
                ci_lower=0.54,
                ci_upper=0.96,
                weight=15.2,
                sample_size=450,
                events_treatment=45,
                events_control=62,
                n_treatment=225,
                n_control=225,
            ),
            ForestPlotStudy(
                study_id="2",
                study_name="Johnson et al.",
                year=2020,
                effect_size=0.85,
                ci_lower=0.68,
                ci_upper=1.06,
                weight=18.5,
                sample_size=620,
                events_treatment=78,
                events_control=91,
                n_treatment=310,
                n_control=310,
            ),
            ForestPlotStudy(
                study_id="3",
                study_name="Williams et al.",
                year=2020,
                effect_size=0.63,
                ci_lower=0.45,
                ci_upper=0.88,
                weight=12.8,
                sample_size=380,
                events_treatment=38,
                events_control=58,
                n_treatment=190,
                n_control=190,
            ),
            ForestPlotStudy(
                study_id="4",
                study_name="Brown et al.",
                year=2021,
                effect_size=0.79,
                ci_lower=0.62,
                ci_upper=1.01,
                weight=16.4,
                sample_size=540,
                events_treatment=67,
                events_control=84,
                n_treatment=270,
                n_control=270,
            ),
            ForestPlotStudy(
                study_id="5",
                study_name="Davis et al.",
                year=2021,
                effect_size=0.68,
                ci_lower=0.48,
                ci_upper=0.96,
                weight=11.2,
                sample_size=320,
                events_treatment=32,
                events_control=46,
                n_treatment=160,
                n_control=160,
            ),
            ForestPlotStudy(
                study_id="6",
                study_name="Miller et al.",
                year=2022,
                effect_size=0.91,
                ci_lower=0.75,
                ci_upper=1.10,
                weight=19.8,
                sample_size=750,
                events_treatment=112,
                events_control=123,
                n_treatment=375,
                n_control=375,
            ),
            ForestPlotStudy(
                study_id="7",
                study_name="Garcia et al.",
                year=2023,
                effect_size=0.74,
                ci_lower=0.55,
                ci_upper=0.99,
                weight=6.1,
                sample_size=180,
                events_treatment=18,
                events_control=24,
                n_treatment=90,
                n_control=90,
            ),
        ]

        # Calculate pooled effect (simplified random-effects model)
        total_weight = sum(s.weight for s in studies)
        pooled_effect = sum(s.effect_size * s.weight for s in studies) / total_weight

        return ForestPlotData(
            studies=studies,
            pooled_effect=0.76,
            pooled_ci_lower=0.67,
            pooled_ci_upper=0.86,
            heterogeneity_i2=28.4,
            heterogeneity_q=8.38,
            heterogeneity_p=0.21,
            effect_measure=effect_measure,
            null_value=1.0,
        )

    # ==========================================================================
    # Volcano Plot (Differential Analysis)
    # ==========================================================================

    def prepare_volcano_data(
        self,
        analysis_id: str | None = None,
        fc_threshold: float = 1.0,
        p_threshold: float = 0.05,
    ) -> VolcanoData:
        """Prepare volcano plot data for differential analysis.

        Args:
            analysis_id: ID of differential analysis
            fc_threshold: Log2 fold change threshold for significance
            p_threshold: P-value threshold for significance

        Returns:
            VolcanoData with points and significance counts
        """
        # Generate mock differential expression data
        biomarkers = [
            # Significantly upregulated
            ("IL6", "Interleukin-6", 2.5, 0.0001, "cytokine"),
            ("TNF", "Tumor Necrosis Factor", 1.8, 0.0005, "cytokine"),
            ("CRP", "C-Reactive Protein", 2.1, 0.0002, "acute_phase"),
            ("HMGB1", "High Mobility Group Box 1", 1.6, 0.002, "alarmin"),
            ("MMP9", "Matrix Metalloproteinase 9", 1.4, 0.005, "enzyme"),
            ("VEGF", "Vascular Endothelial Growth Factor", 1.3, 0.01, "growth_factor"),
            # Significantly downregulated
            ("IL10", "Interleukin-10", -1.9, 0.0003, "cytokine"),
            ("ADIPOQ", "Adiponectin", -1.5, 0.001, "adipokine"),
            ("FOXP3", "Forkhead Box P3", -1.2, 0.008, "transcription_factor"),
            ("TGFB1", "Transforming Growth Factor Beta 1", -1.1, 0.02, "growth_factor"),
        ]

        points = []

        # Add significant points
        for gene, name, lfc, pval, category in biomarkers:
            direction = "up" if lfc > 0 else "down"
            points.append(
                VolcanoPoint(
                    id=gene,
                    name=name,
                    log_fold_change=lfc,
                    neg_log_p_value=-math.log10(pval),
                    p_value=pval,
                    significant=True,
                    direction=direction,
                    category=category,
                )
            )

        # Add non-significant points (noise)
        for i in range(90):
            lfc = random.gauss(0, 0.4)
            pval = 10 ** random.uniform(-1.5, 0)  # p between 0.03 and 1
            significant = abs(lfc) >= fc_threshold and pval <= p_threshold

            points.append(
                VolcanoPoint(
                    id=f"GENE{i+1}",
                    name=f"Gene {i+1}",
                    log_fold_change=round(lfc, 2),
                    neg_log_p_value=round(-math.log10(pval), 2),
                    p_value=round(pval, 4),
                    significant=significant,
                    direction="up" if lfc > fc_threshold else "down" if lfc < -fc_threshold else "none",
                    category="other",
                )
            )

        significant_up = len([p for p in points if p.significant and p.direction == "up"])
        significant_down = len([p for p in points if p.significant and p.direction == "down"])

        return VolcanoData(
            points=points,
            fc_threshold=fc_threshold,
            p_threshold=p_threshold,
            total_features=len(points),
            significant_up=significant_up,
            significant_down=significant_down,
            comparison="Treatment vs Control",
        )

    # ==========================================================================
    # Study Timeline (Gantt Chart)
    # ==========================================================================

    def generate_timeline_data(
        self,
        study_id: str | None = None,
    ) -> TimelineData:
        """Generate study timeline Gantt chart data.

        Args:
            study_id: ID of clinical study

        Returns:
            TimelineData with events and milestones
        """
        base_date = datetime(2024, 1, 15)

        events = [
            TimelineEvent(
                id="protocol",
                name="Protocol Development",
                start_date=base_date,
                end_date=base_date + timedelta(days=60),
                category="Planning",
                status="completed",
                progress=100,
                milestones=[
                    {"name": "Draft Complete", "date": (base_date + timedelta(days=30)).isoformat()},
                    {"name": "IRB Submission", "date": (base_date + timedelta(days=45)).isoformat()},
                ],
            ),
            TimelineEvent(
                id="irb_approval",
                name="IRB Review & Approval",
                start_date=base_date + timedelta(days=45),
                end_date=base_date + timedelta(days=105),
                category="Regulatory",
                status="completed",
                progress=100,
                milestones=[
                    {"name": "IRB Approval", "date": (base_date + timedelta(days=90)).isoformat()},
                ],
                dependencies=["protocol"],
            ),
            TimelineEvent(
                id="site_initiation",
                name="Site Initiation",
                start_date=base_date + timedelta(days=90),
                end_date=base_date + timedelta(days=150),
                category="Operations",
                status="completed",
                progress=100,
                milestones=[
                    {"name": "First Site Active", "date": (base_date + timedelta(days=120)).isoformat()},
                ],
                dependencies=["irb_approval"],
            ),
            TimelineEvent(
                id="enrollment",
                name="Patient Enrollment",
                start_date=base_date + timedelta(days=120),
                end_date=base_date + timedelta(days=365),
                category="Enrollment",
                status="in_progress",
                progress=65,
                milestones=[
                    {"name": "50% Enrollment", "date": (base_date + timedelta(days=240)).isoformat()},
                    {"name": "100% Enrollment", "date": (base_date + timedelta(days=365)).isoformat()},
                ],
                dependencies=["site_initiation"],
            ),
            TimelineEvent(
                id="treatment",
                name="Treatment Phase",
                start_date=base_date + timedelta(days=150),
                end_date=base_date + timedelta(days=545),
                category="Treatment",
                status="in_progress",
                progress=45,
                dependencies=["enrollment"],
            ),
            TimelineEvent(
                id="follow_up",
                name="Follow-up Period",
                start_date=base_date + timedelta(days=365),
                end_date=base_date + timedelta(days=730),
                category="Follow-up",
                status="planned",
                progress=0,
                milestones=[
                    {"name": "6-Month Follow-up", "date": (base_date + timedelta(days=545)).isoformat()},
                    {"name": "12-Month Follow-up", "date": (base_date + timedelta(days=730)).isoformat()},
                ],
                dependencies=["treatment"],
            ),
            TimelineEvent(
                id="analysis",
                name="Data Analysis",
                start_date=base_date + timedelta(days=700),
                end_date=base_date + timedelta(days=820),
                category="Analysis",
                status="planned",
                progress=0,
                milestones=[
                    {"name": "Database Lock", "date": (base_date + timedelta(days=730)).isoformat()},
                    {"name": "Primary Analysis", "date": (base_date + timedelta(days=790)).isoformat()},
                ],
                dependencies=["follow_up"],
            ),
            TimelineEvent(
                id="publication",
                name="Publication & Reporting",
                start_date=base_date + timedelta(days=790),
                end_date=base_date + timedelta(days=910),
                category="Publication",
                status="planned",
                progress=0,
                milestones=[
                    {"name": "Manuscript Submission", "date": (base_date + timedelta(days=850)).isoformat()},
                ],
                dependencies=["analysis"],
            ),
        ]

        categories = list(set(e.category for e in events))

        return TimelineData(
            events=events,
            study_name="Phase III Cardiovascular Outcomes Trial",
            study_start=base_date,
            study_end=base_date + timedelta(days=910),
            categories=sorted(categories),
        )


# ==============================================================================
# Singleton Pattern
# ==============================================================================


_visualization_service: VisualizationDataService | None = None


def get_visualization_data_service() -> VisualizationDataService:
    """Get or create the visualization data service singleton."""
    global _visualization_service
    if _visualization_service is None:
        _visualization_service = VisualizationDataService()
    return _visualization_service
