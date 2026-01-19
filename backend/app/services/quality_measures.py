"""Quality Measure Tracking Service for Clinical Ontology Normalizer.

Supports HEDIS (Healthcare Effectiveness Data and Information Set) and
CQM (Clinical Quality Measures) for quality reporting and care gap detection.

Key capabilities:
1. Define and manage quality measures (HEDIS, CQM, custom)
2. Evaluate patient eligibility for measures
3. Calculate numerator/denominator compliance
4. Detect care gaps and missing interventions
5. Track measure performance over time
6. Generate quality reports for value-based care programs

Supported measure categories:
- Diabetes: HbA1c control, eye exam, nephropathy screening
- Cardiovascular: Statin therapy, blood pressure control
- Preventive: Cancer screening, immunizations
- Medication: Adherence (PDC - Proportion of Days Covered)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
import logging
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class MeasureCategory(Enum):
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


class MeasureType(Enum):
    """Type of quality measure."""

    HEDIS = "hedis"  # NCQA HEDIS measures
    CQM = "cqm"  # CMS Clinical Quality Measures
    MIPS = "mips"  # Merit-based Incentive Payment System
    CUSTOM = "custom"  # Organization-specific measures


class MeasurePriority(Enum):
    """Priority level for care gaps."""

    CRITICAL = "critical"  # Immediate attention needed
    HIGH = "high"  # Address within 30 days
    MEDIUM = "medium"  # Address within 90 days
    LOW = "low"  # Routine follow-up


class ComplianceStatus(Enum):
    """Compliance status for a measure."""

    COMPLIANT = "compliant"  # Met the measure
    NON_COMPLIANT = "non_compliant"  # Did not meet the measure
    EXCLUDED = "excluded"  # Excluded from measure
    NOT_ELIGIBLE = "not_eligible"  # Not in eligible population
    PENDING = "pending"  # Awaiting data


class AgeUnit(Enum):
    """Unit for age specification."""

    YEARS = "years"
    MONTHS = "months"
    DAYS = "days"


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class AgeRange:
    """Age range for eligibility criteria."""

    min_age: int
    max_age: int
    unit: AgeUnit = AgeUnit.YEARS


@dataclass
class EligibilityCriteria:
    """Criteria for measure eligibility."""

    age_range: AgeRange | None = None
    gender: str | None = None  # "M", "F", or None for any
    diagnoses: list[str] = field(default_factory=list)  # ICD-10 codes
    procedures: list[str] = field(default_factory=list)  # CPT/HCPCS codes
    medications: list[str] = field(default_factory=list)  # RxNorm codes
    exclusion_diagnoses: list[str] = field(default_factory=list)
    exclusion_procedures: list[str] = field(default_factory=list)
    continuous_enrollment_days: int = 0  # Required enrollment period
    anchor_date_procedure: str | None = None  # Procedure that anchors measurement


@dataclass
class NumeratorCriteria:
    """Criteria for numerator compliance."""

    required_diagnoses: list[str] = field(default_factory=list)
    required_procedures: list[str] = field(default_factory=list)
    required_labs: list[dict[str, Any]] = field(default_factory=list)
    required_medications: list[str] = field(default_factory=list)
    value_thresholds: list[dict[str, Any]] = field(default_factory=list)
    lookback_days: int = 365  # How far back to look for compliance


@dataclass
class QualityMeasure:
    """Definition of a quality measure."""

    id: str  # Measure ID (e.g., "HEDIS-CDC-HBA1C")
    name: str
    description: str
    category: MeasureCategory
    measure_type: MeasureType
    version: str  # Measure year/version

    # Measure specifications
    eligibility: EligibilityCriteria
    numerator: NumeratorCriteria

    # Metadata
    steward: str  # Organization that maintains the measure
    domain: str  # Clinical domain
    nqf_number: str | None = None  # National Quality Forum number
    cms_id: str | None = None  # CMS measure ID

    # Performance
    benchmark_50th: float = 0.0  # 50th percentile benchmark
    benchmark_90th: float = 0.0  # 90th percentile benchmark

    # Gap prioritization
    default_priority: MeasurePriority = MeasurePriority.MEDIUM

    # Additional specifications
    specifications_url: str | None = None
    clinical_guidance: str = ""


@dataclass
class PatientGap:
    """A care gap identified for a patient."""

    measure_id: str
    measure_name: str
    category: MeasureCategory
    missing_element: str  # What's missing (e.g., "HbA1c test", "Eye exam")
    missing_codes: list[str]  # Codes that would satisfy the gap
    due_date: date
    priority: MeasurePriority
    last_performed: date | None = None
    days_overdue: int = 0
    recommendation: str = ""
    patient_instructions: str = ""


@dataclass
class MeasureResult:
    """Result of evaluating a patient against a measure."""

    measure_id: str
    measure_name: str
    category: MeasureCategory

    # Eligibility
    is_eligible: bool
    eligibility_reason: str

    # Compliance
    status: ComplianceStatus
    in_numerator: bool

    # Evidence
    evidence: list[dict[str, Any]] = field(default_factory=list)

    # Gap information (if non-compliant)
    gap: PatientGap | None = None

    # Dates
    measurement_period_start: date | None = None
    measurement_period_end: date | None = None
    evaluation_date: date | None = None


@dataclass
class MeasurePerformance:
    """Aggregate performance for a measure."""

    measure_id: str
    measure_name: str
    category: MeasureCategory

    # Period
    period_start: date
    period_end: date

    # Population counts
    eligible_population: int
    numerator_count: int
    denominator_count: int
    excluded_count: int

    # Rate
    performance_rate: float  # numerator / denominator

    # Benchmarks
    benchmark_50th: float
    benchmark_90th: float
    meets_benchmark: bool  # Meets 50th percentile
    star_rating: int  # 1-5 star rating based on performance

    # Trends
    previous_rate: float | None = None
    rate_change: float | None = None

    # Gap summary
    total_gaps: int = 0
    critical_gaps: int = 0
    high_priority_gaps: int = 0


@dataclass
class PatientEvaluationResult:
    """Complete evaluation result for a patient."""

    patient_id: str
    evaluation_date: datetime

    # Measure results
    measure_results: list[MeasureResult] = field(default_factory=list)

    # Summary
    total_measures_evaluated: int = 0
    measures_compliant: int = 0
    measures_non_compliant: int = 0
    measures_excluded: int = 0

    # Care gaps
    care_gaps: list[PatientGap] = field(default_factory=list)
    critical_gaps: int = 0

    # Compliance rate
    overall_compliance_rate: float = 0.0

    # Processing
    evaluation_time_ms: float = 0.0


@dataclass
class PerformanceReport:
    """Aggregate performance report."""

    report_date: datetime
    period_start: date
    period_end: date

    # Measure performances
    measures: list[MeasurePerformance] = field(default_factory=list)

    # Summary
    total_measures: int = 0
    measures_meeting_benchmark: int = 0
    average_performance_rate: float = 0.0

    # By category
    performance_by_category: dict[str, float] = field(default_factory=dict)

    # Gaps
    total_care_gaps: int = 0
    gap_closure_rate: float = 0.0

    # Processing
    report_time_ms: float = 0.0


# ============================================================================
# HEDIS and CQM Measure Definitions
# ============================================================================

QUALITY_MEASURES: list[QualityMeasure] = [
    # =========================================================================
    # DIABETES MEASURES
    # =========================================================================
    QualityMeasure(
        id="HEDIS-CDC-HBA1C",
        name="Diabetes: HbA1c Control (<8%)",
        description="Percentage of patients 18-75 with diabetes whose HbA1c was <8% during the measurement period",
        category=MeasureCategory.DIABETES,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 75),
            diagnoses=[
                "E10", "E11", "E13",  # Type 1, Type 2, Other diabetes
                "E10.9", "E11.9",  # Unspecified
                "E11.65", "E11.69",  # With hyperglycemia
            ],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            required_labs=[
                {"name": "HbA1c", "loinc": "4548-4", "operator": "<", "value": 8.0, "unit": "%"}
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Diabetes",
        nqf_number="0059",
        benchmark_50th=0.65,
        benchmark_90th=0.78,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="Order HbA1c test if not done in past year. Target <8% for most patients, <7% for patients without hypoglycemia risk.",
    ),

    QualityMeasure(
        id="HEDIS-CDC-HBA1C-POOR",
        name="Diabetes: HbA1c Poor Control (>9%)",
        description="Percentage of patients 18-75 with diabetes whose HbA1c was >9% (lower is better)",
        category=MeasureCategory.DIABETES,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 75),
            diagnoses=["E10", "E11", "E13"],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            required_labs=[
                {"name": "HbA1c", "loinc": "4548-4", "operator": ">", "value": 9.0, "unit": "%"}
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Diabetes",
        nqf_number="0059",
        benchmark_50th=0.25,  # Lower is better for this measure
        benchmark_90th=0.15,
        default_priority=MeasurePriority.CRITICAL,
        clinical_guidance="Patients with HbA1c >9% need intensified treatment. Consider medication adjustment and diabetes education.",
    ),

    QualityMeasure(
        id="HEDIS-CDC-EYE",
        name="Diabetes: Eye Exam",
        description="Percentage of patients 18-75 with diabetes who had a retinal eye exam",
        category=MeasureCategory.DIABETES,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 75),
            diagnoses=["E10", "E11", "E13"],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            required_procedures=[
                "92002", "92004", "92012", "92014",  # Eye exam codes
                "92227", "92228",  # Retinal imaging
                "2022F", "2024F", "2026F", "3072F",  # Eye exam CPT II
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Diabetes",
        nqf_number="0055",
        benchmark_50th=0.58,
        benchmark_90th=0.72,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="Annual dilated eye exam recommended. Can use retinal imaging as alternative.",
    ),

    QualityMeasure(
        id="HEDIS-CDC-NEPHROPATHY",
        name="Diabetes: Nephropathy Screening",
        description="Percentage of patients 18-75 with diabetes who had nephropathy screening or evidence of nephropathy",
        category=MeasureCategory.DIABETES,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 75),
            diagnoses=["E10", "E11", "E13"],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            required_labs=[
                {"name": "urine_albumin", "loinc": "14957-5", "presence": True},
                {"name": "urine_protein", "loinc": "2888-6", "presence": True},
                {"name": "UACR", "loinc": "9318-7", "presence": True},
            ],
            required_diagnoses=[
                "N18.1", "N18.2", "N18.3", "N18.4", "N18.5", "N18.6",  # CKD stages
                "E11.21", "E11.22", "E11.29",  # DM with nephropathy
            ],
            required_medications=[
                "197885", "310792", "310793",  # ACE inhibitors (RxNorm)
                "283316", "314076",  # ARBs
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Diabetes",
        nqf_number="0062",
        benchmark_50th=0.88,
        benchmark_90th=0.95,
        default_priority=MeasurePriority.MEDIUM,
        clinical_guidance="Annual urine albumin test recommended. ACE-I/ARB use counts as evidence of nephropathy treatment.",
    ),

    # =========================================================================
    # CARDIOVASCULAR MEASURES
    # =========================================================================
    QualityMeasure(
        id="HEDIS-SPC",
        name="Statin Therapy for Cardiovascular Disease",
        description="Percentage of males 21-75 and females 40-75 with ASCVD who were prescribed statin therapy",
        category=MeasureCategory.CARDIOVASCULAR,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(21, 75),
            diagnoses=[
                "I21", "I22",  # MI
                "I25.1", "I25.10", "I25.110", "I25.111",  # CAD
                "I63",  # Stroke
                "I70.0", "I70.1",  # Atherosclerosis
                "Z95.1", "Z95.5",  # Coronary stent/bypass
            ],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            required_medications=[
                "36567", "83367", "200345",  # Atorvastatin
                "301542", "312961",  # Rosuvastatin
                "197904", "197905",  # Simvastatin
                "259255", "316672",  # Pravastatin
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Cardiovascular",
        nqf_number="0543",
        benchmark_50th=0.80,
        benchmark_90th=0.90,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="High-intensity statin therapy recommended for patients with established ASCVD.",
    ),

    QualityMeasure(
        id="HEDIS-CBP",
        name="Controlling High Blood Pressure",
        description="Percentage of patients 18-85 with hypertension whose BP was <140/90",
        category=MeasureCategory.CARDIOVASCULAR,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 85),
            diagnoses=[
                "I10",  # Essential hypertension
                "I11", "I12", "I13",  # Hypertensive heart/kidney disease
            ],
            exclusion_diagnoses=[
                "N18.5", "N18.6",  # ESRD
                "I12.0", "I13.11", "I13.2",  # Hypertensive CKD stage 5
            ],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            value_thresholds=[
                {"name": "systolic_bp", "operator": "<", "value": 140, "unit": "mmHg"},
                {"name": "diastolic_bp", "operator": "<", "value": 90, "unit": "mmHg"},
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Cardiovascular",
        nqf_number="0018",
        benchmark_50th=0.65,
        benchmark_90th=0.78,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="Target BP <140/90 for most patients. Consider <130/80 for high-risk patients.",
    ),

    # =========================================================================
    # PREVENTIVE CARE MEASURES
    # =========================================================================
    QualityMeasure(
        id="HEDIS-BCS",
        name="Breast Cancer Screening",
        description="Percentage of women 50-74 who had a mammogram in the past 2 years",
        category=MeasureCategory.PREVENTIVE,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(50, 74),
            gender="F",
            exclusion_diagnoses=[
                "Z90.10", "Z90.11", "Z90.12", "Z90.13",  # Bilateral mastectomy
                "C50",  # Breast cancer history
            ],
            continuous_enrollment_days=730,  # 2 years
        ),
        numerator=NumeratorCriteria(
            required_procedures=[
                "77067",  # Screening mammogram
                "77066",  # Diagnostic mammogram
                "G0202", "G0204", "G0206",  # Digital mammography
            ],
            lookback_days=730,  # 2 years
        ),
        steward="NCQA",
        domain="Cancer Screening",
        nqf_number="2372",
        benchmark_50th=0.72,
        benchmark_90th=0.82,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="Mammogram recommended every 2 years for women 50-74.",
    ),

    QualityMeasure(
        id="HEDIS-COL",
        name="Colorectal Cancer Screening",
        description="Percentage of adults 50-75 who had appropriate colorectal cancer screening",
        category=MeasureCategory.PREVENTIVE,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(50, 75),
            exclusion_diagnoses=[
                "Z90.49",  # Colectomy
                "C18", "C19", "C20",  # Colorectal cancer history
            ],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            required_procedures=[
                "45378", "45380", "45381", "45382", "45384", "45385",  # Colonoscopy
                "G0105", "G0121",  # Screening colonoscopy
                "82270", "82274",  # FOBT/FIT
                "81528",  # Cologuard
            ],
            required_labs=[
                {"name": "FIT", "loinc": "29771-3", "presence": True},
                {"name": "gFOBT", "loinc": "2335-8", "presence": True},
            ],
            lookback_days=3650,  # 10 years for colonoscopy
        ),
        steward="NCQA",
        domain="Cancer Screening",
        nqf_number="0034",
        benchmark_50th=0.68,
        benchmark_90th=0.80,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="Colonoscopy every 10 years, or FIT annually, or Cologuard every 3 years.",
    ),

    QualityMeasure(
        id="HEDIS-CIS-FLU",
        name="Childhood Immunization: Influenza",
        description="Percentage of children 6 months - 18 years who received influenza vaccine",
        category=MeasureCategory.PEDIATRIC,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(6, 216, AgeUnit.MONTHS),  # 6 months to 18 years
            continuous_enrollment_days=180,
        ),
        numerator=NumeratorCriteria(
            required_procedures=[
                "90686", "90688",  # Flu vaccine codes
                "90756", "90673", "90674",
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Immunizations",
        nqf_number="0038",
        benchmark_50th=0.50,
        benchmark_90th=0.65,
        default_priority=MeasurePriority.MEDIUM,
        clinical_guidance="Annual influenza vaccination recommended for all children 6 months and older.",
    ),

    QualityMeasure(
        id="CQM-IMM-2",
        name="Adult Immunization: Influenza",
        description="Percentage of adults 18+ who received influenza vaccine during flu season",
        category=MeasureCategory.PREVENTIVE,
        measure_type=MeasureType.CQM,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 120),
            continuous_enrollment_days=180,
        ),
        numerator=NumeratorCriteria(
            required_procedures=[
                "90686", "90688", "90756", "90673", "90674",  # Flu vaccines
            ],
            lookback_days=365,
        ),
        steward="CMS",
        domain="Immunizations",
        cms_id="CMS147v12",
        benchmark_50th=0.48,
        benchmark_90th=0.60,
        default_priority=MeasurePriority.MEDIUM,
        clinical_guidance="Annual influenza vaccination recommended for all adults.",
    ),

    QualityMeasure(
        id="CQM-IMM-PNEUMO",
        name="Pneumococcal Vaccination for Older Adults",
        description="Percentage of adults 65+ who have received pneumococcal vaccine",
        category=MeasureCategory.PREVENTIVE,
        measure_type=MeasureType.CQM,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(65, 120),
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            required_procedures=[
                "90670", "90671",  # PCV13, PCV15
                "90732",  # PPSV23
            ],
            lookback_days=3650,  # Lifetime for some vaccines
        ),
        steward="CMS",
        domain="Immunizations",
        cms_id="CMS127v12",
        nqf_number="0043",
        benchmark_50th=0.75,
        benchmark_90th=0.88,
        default_priority=MeasurePriority.MEDIUM,
        clinical_guidance="PCV15 or PCV20 followed by PPSV23 for adults 65+.",
    ),

    # =========================================================================
    # MEDICATION ADHERENCE MEASURES (PDC)
    # =========================================================================
    QualityMeasure(
        id="HEDIS-PDC-RASA",
        name="PDC: Renin-Angiotensin System Antagonists",
        description="Percentage of patients with PDC >=80% for RASA medications",
        category=MeasureCategory.MEDICATION_ADHERENCE,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 120),
            medications=[
                "197885", "310792", "310793",  # ACE inhibitors
                "283316", "314076", "349483",  # ARBs
            ],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            value_thresholds=[
                {"name": "PDC", "operator": ">=", "value": 80, "unit": "%"}
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Medication Adherence",
        nqf_number="0541",
        benchmark_50th=0.80,
        benchmark_90th=0.88,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="PDC >=80% indicates good adherence. Consider 90-day fills and medication synchronization.",
    ),

    QualityMeasure(
        id="HEDIS-PDC-STATIN",
        name="PDC: Statin Medications",
        description="Percentage of patients with PDC >=80% for statin medications",
        category=MeasureCategory.MEDICATION_ADHERENCE,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 120),
            medications=[
                "36567", "83367", "200345",  # Atorvastatin
                "301542", "312961",  # Rosuvastatin
                "197904", "197905",  # Simvastatin
            ],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            value_thresholds=[
                {"name": "PDC", "operator": ">=", "value": 80, "unit": "%"}
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Medication Adherence",
        nqf_number="0541",
        benchmark_50th=0.80,
        benchmark_90th=0.88,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="PDC >=80% indicates good adherence. Address barriers to medication adherence.",
    ),

    QualityMeasure(
        id="HEDIS-PDC-DM",
        name="PDC: Diabetes Medications",
        description="Percentage of patients with PDC >=80% for diabetes medications",
        category=MeasureCategory.MEDICATION_ADHERENCE,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 120),
            diagnoses=["E10", "E11", "E13"],
            medications=[
                "6809", "860975", "860981",  # Metformin
                "73044", "1361493",  # SGLT2 inhibitors
                "1598392", "1927883",  # GLP-1 agonists
            ],
            continuous_enrollment_days=365,
        ),
        numerator=NumeratorCriteria(
            value_thresholds=[
                {"name": "PDC", "operator": ">=", "value": 80, "unit": "%"}
            ],
            lookback_days=365,
        ),
        steward="NCQA",
        domain="Medication Adherence",
        nqf_number="0541",
        benchmark_50th=0.78,
        benchmark_90th=0.86,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="PDC >=80% indicates good adherence. Consider cost, side effects as adherence barriers.",
    ),

    # =========================================================================
    # BEHAVIORAL HEALTH MEASURES
    # =========================================================================
    QualityMeasure(
        id="HEDIS-AMM-ACUTE",
        name="Antidepressant Medication Management - Acute Phase",
        description="Percentage of patients with depression who remained on antidepressant for 84 days",
        category=MeasureCategory.BEHAVIORAL_HEALTH,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 120),
            diagnoses=[
                "F32", "F33",  # Major depressive disorder
            ],
            medications=[
                "321988", "312036",  # SSRIs
                "72625", "763028",  # SNRIs
            ],
            continuous_enrollment_days=180,
        ),
        numerator=NumeratorCriteria(
            value_thresholds=[
                {"name": "days_on_medication", "operator": ">=", "value": 84, "unit": "days"}
            ],
            lookback_days=114,  # 84 days from index + 30 days
        ),
        steward="NCQA",
        domain="Behavioral Health",
        nqf_number="0105",
        benchmark_50th=0.58,
        benchmark_90th=0.72,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="Patients should continue antidepressants for at least 84 days during acute phase.",
    ),

    QualityMeasure(
        id="HEDIS-AMM-CONT",
        name="Antidepressant Medication Management - Continuation Phase",
        description="Percentage of patients with depression who remained on antidepressant for 180 days",
        category=MeasureCategory.BEHAVIORAL_HEALTH,
        measure_type=MeasureType.HEDIS,
        version="2024",
        eligibility=EligibilityCriteria(
            age_range=AgeRange(18, 120),
            diagnoses=["F32", "F33"],
            medications=["321988", "312036", "72625", "763028"],
            continuous_enrollment_days=270,
        ),
        numerator=NumeratorCriteria(
            value_thresholds=[
                {"name": "days_on_medication", "operator": ">=", "value": 180, "unit": "days"}
            ],
            lookback_days=210,
        ),
        steward="NCQA",
        domain="Behavioral Health",
        nqf_number="0105",
        benchmark_50th=0.42,
        benchmark_90th=0.58,
        default_priority=MeasurePriority.HIGH,
        clinical_guidance="Continuation phase (180+ days) reduces relapse risk. Monitor for side effects.",
    ),
]

# Build lookup indexes
MEASURES_BY_ID: dict[str, QualityMeasure] = {m.id: m for m in QUALITY_MEASURES}
MEASURES_BY_CATEGORY: dict[MeasureCategory, list[QualityMeasure]] = {}
for measure in QUALITY_MEASURES:
    if measure.category not in MEASURES_BY_CATEGORY:
        MEASURES_BY_CATEGORY[measure.category] = []
    MEASURES_BY_CATEGORY[measure.category].append(measure)


# ============================================================================
# Quality Measure Service
# ============================================================================


class QualityMeasureService:
    """Service for quality measure tracking and gap detection."""

    def __init__(self):
        """Initialize the service."""
        self._measures = QUALITY_MEASURES
        self._measures_by_id = MEASURES_BY_ID
        self._measures_by_category = MEASURES_BY_CATEGORY
        logger.info(f"QualityMeasureService initialized with {len(self._measures)} measures")

    def get_all_measures(self) -> list[QualityMeasure]:
        """Get all available quality measures."""
        return self._measures

    def get_measure(self, measure_id: str) -> QualityMeasure | None:
        """Get a specific measure by ID."""
        return self._measures_by_id.get(measure_id)

    def get_measures_by_category(self, category: MeasureCategory) -> list[QualityMeasure]:
        """Get measures for a specific category."""
        return self._measures_by_category.get(category, [])

    def get_measures_by_type(self, measure_type: MeasureType) -> list[QualityMeasure]:
        """Get measures by type (HEDIS, CQM, etc.)."""
        return [m for m in self._measures if m.measure_type == measure_type]

    def evaluate_patient(
        self,
        patient_id: str,
        patient_data: dict[str, Any],
        measure_ids: list[str] | None = None,
        measurement_date: date | None = None,
    ) -> PatientEvaluationResult:
        """Evaluate a patient against quality measures.

        Args:
            patient_id: Patient identifier
            patient_data: Patient clinical data including:
                - demographics: {age, gender, dob}
                - diagnoses: [{code, date}]
                - procedures: [{code, date}]
                - labs: [{name, value, date, loinc}]
                - medications: [{rxnorm, start_date, end_date, days_supply}]
                - vitals: [{name, value, date}]
            measure_ids: Specific measures to evaluate (all if None)
            measurement_date: Date for evaluation (today if None)

        Returns:
            PatientEvaluationResult with compliance status and gaps
        """
        import time
        start_time = time.perf_counter()

        measurement_date = measurement_date or date.today()
        measures_to_evaluate = self._measures
        if measure_ids:
            measures_to_evaluate = [m for m in self._measures if m.id in measure_ids]

        measure_results: list[MeasureResult] = []
        care_gaps: list[PatientGap] = []
        compliant_count = 0
        non_compliant_count = 0
        excluded_count = 0

        for measure in measures_to_evaluate:
            result = self._evaluate_single_measure(
                measure=measure,
                patient_data=patient_data,
                measurement_date=measurement_date,
            )
            measure_results.append(result)

            if result.status == ComplianceStatus.COMPLIANT:
                compliant_count += 1
            elif result.status == ComplianceStatus.NON_COMPLIANT:
                non_compliant_count += 1
                if result.gap:
                    care_gaps.append(result.gap)
            elif result.status == ComplianceStatus.EXCLUDED:
                excluded_count += 1

        # Calculate compliance rate
        eligible_count = compliant_count + non_compliant_count
        compliance_rate = (compliant_count / eligible_count) if eligible_count > 0 else 0.0

        # Count critical gaps
        critical_gaps = sum(1 for g in care_gaps if g.priority == MeasurePriority.CRITICAL)

        evaluation_time = (time.perf_counter() - start_time) * 1000

        return PatientEvaluationResult(
            patient_id=patient_id,
            evaluation_date=datetime.now(),
            measure_results=measure_results,
            total_measures_evaluated=len(measure_results),
            measures_compliant=compliant_count,
            measures_non_compliant=non_compliant_count,
            measures_excluded=excluded_count,
            care_gaps=care_gaps,
            critical_gaps=critical_gaps,
            overall_compliance_rate=round(compliance_rate, 3),
            evaluation_time_ms=round(evaluation_time, 2),
        )

    def _evaluate_single_measure(
        self,
        measure: QualityMeasure,
        patient_data: dict[str, Any],
        measurement_date: date,
    ) -> MeasureResult:
        """Evaluate a single measure for a patient."""
        # Check eligibility
        is_eligible, eligibility_reason = self._check_eligibility(
            measure.eligibility, patient_data, measurement_date
        )

        if not is_eligible:
            return MeasureResult(
                measure_id=measure.id,
                measure_name=measure.name,
                category=measure.category,
                is_eligible=False,
                eligibility_reason=eligibility_reason,
                status=ComplianceStatus.NOT_ELIGIBLE,
                in_numerator=False,
                measurement_period_start=measurement_date - timedelta(days=365),
                measurement_period_end=measurement_date,
                evaluation_date=measurement_date,
            )

        # Check for exclusions
        is_excluded, exclusion_reason = self._check_exclusions(
            measure.eligibility, patient_data
        )

        if is_excluded:
            return MeasureResult(
                measure_id=measure.id,
                measure_name=measure.name,
                category=measure.category,
                is_eligible=True,
                eligibility_reason="Eligible but excluded",
                status=ComplianceStatus.EXCLUDED,
                in_numerator=False,
                measurement_period_start=measurement_date - timedelta(days=365),
                measurement_period_end=measurement_date,
                evaluation_date=measurement_date,
            )

        # Check numerator compliance
        in_numerator, evidence, missing = self._check_numerator(
            measure.numerator, patient_data, measurement_date
        )

        status = ComplianceStatus.COMPLIANT if in_numerator else ComplianceStatus.NON_COMPLIANT

        # Build care gap if non-compliant
        gap = None
        if not in_numerator and missing:
            gap = PatientGap(
                measure_id=measure.id,
                measure_name=measure.name,
                category=measure.category,
                missing_element=missing.get("element", "Unknown"),
                missing_codes=missing.get("codes", []),
                due_date=missing.get("due_date", measurement_date),
                priority=measure.default_priority,
                last_performed=missing.get("last_performed"),
                days_overdue=missing.get("days_overdue", 0),
                recommendation=measure.clinical_guidance,
                patient_instructions=self._generate_patient_instructions(measure, missing),
            )

        return MeasureResult(
            measure_id=measure.id,
            measure_name=measure.name,
            category=measure.category,
            is_eligible=True,
            eligibility_reason="Met all eligibility criteria",
            status=status,
            in_numerator=in_numerator,
            evidence=evidence,
            gap=gap,
            measurement_period_start=measurement_date - timedelta(days=measure.numerator.lookback_days),
            measurement_period_end=measurement_date,
            evaluation_date=measurement_date,
        )

    def _check_eligibility(
        self,
        criteria: EligibilityCriteria,
        patient_data: dict[str, Any],
        measurement_date: date,
    ) -> tuple[bool, str]:
        """Check if patient meets eligibility criteria."""
        demographics = patient_data.get("demographics", {})

        # Check age
        if criteria.age_range:
            patient_age = demographics.get("age", 0)
            dob = demographics.get("dob")
            if dob:
                if isinstance(dob, str):
                    dob = datetime.strptime(dob, "%Y-%m-%d").date()
                patient_age = (measurement_date - dob).days // 365

            if criteria.age_range.unit == AgeUnit.MONTHS:
                patient_age_months = patient_age * 12
                if not (criteria.age_range.min_age <= patient_age_months <= criteria.age_range.max_age):
                    return False, f"Age {patient_age_months} months outside range {criteria.age_range.min_age}-{criteria.age_range.max_age} months"
            else:
                if not (criteria.age_range.min_age <= patient_age <= criteria.age_range.max_age):
                    return False, f"Age {patient_age} outside range {criteria.age_range.min_age}-{criteria.age_range.max_age}"

        # Check gender
        if criteria.gender:
            patient_gender = demographics.get("gender", "").upper()
            if patient_gender and patient_gender != criteria.gender:
                return False, f"Gender {patient_gender} does not match required {criteria.gender}"

        # Check required diagnoses
        if criteria.diagnoses:
            patient_diagnoses = [d.get("code", "") for d in patient_data.get("diagnoses", [])]
            has_required_dx = any(
                any(pd.startswith(req) for req in criteria.diagnoses)
                for pd in patient_diagnoses
            )
            if not has_required_dx:
                return False, "Missing required diagnosis"

        # Check required procedures (for anchor-based measures)
        if criteria.anchor_date_procedure:
            patient_procedures = [p.get("code", "") for p in patient_data.get("procedures", [])]
            if criteria.anchor_date_procedure not in patient_procedures:
                return False, f"Missing anchor procedure {criteria.anchor_date_procedure}"

        return True, "Meets eligibility criteria"

    def _check_exclusions(
        self,
        criteria: EligibilityCriteria,
        patient_data: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if patient should be excluded."""
        # Check exclusion diagnoses
        if criteria.exclusion_diagnoses:
            patient_diagnoses = [d.get("code", "") for d in patient_data.get("diagnoses", [])]
            for excl in criteria.exclusion_diagnoses:
                if any(pd.startswith(excl) for pd in patient_diagnoses):
                    return True, f"Excluded due to diagnosis {excl}"

        # Check exclusion procedures
        if criteria.exclusion_procedures:
            patient_procedures = [p.get("code", "") for p in patient_data.get("procedures", [])]
            for excl in criteria.exclusion_procedures:
                if excl in patient_procedures:
                    return True, f"Excluded due to procedure {excl}"

        return False, ""

    def _check_numerator(
        self,
        criteria: NumeratorCriteria,
        patient_data: dict[str, Any],
        measurement_date: date,
    ) -> tuple[bool, list[dict[str, Any]], dict[str, Any] | None]:
        """Check if patient meets numerator criteria."""
        evidence: list[dict[str, Any]] = []
        lookback_start = measurement_date - timedelta(days=criteria.lookback_days)

        # Check required labs
        if criteria.required_labs:
            patient_labs = patient_data.get("labs", [])
            for req_lab in criteria.required_labs:
                lab_found = False
                for lab in patient_labs:
                    lab_date = lab.get("date")
                    if lab_date:
                        if isinstance(lab_date, str):
                            lab_date = datetime.strptime(lab_date, "%Y-%m-%d").date()
                        if lab_date < lookback_start:
                            continue

                    # Check LOINC match
                    if req_lab.get("loinc") and lab.get("loinc") == req_lab["loinc"]:
                        # Check value threshold if specified
                        if "operator" in req_lab and "value" in req_lab:
                            lab_value = lab.get("value")
                            if lab_value is not None:
                                try:
                                    lab_value = float(lab_value)
                                    threshold = float(req_lab["value"])
                                    op = req_lab["operator"]

                                    meets_threshold = False
                                    if op == "<" and lab_value < threshold:
                                        meets_threshold = True
                                    elif op == "<=" and lab_value <= threshold:
                                        meets_threshold = True
                                    elif op == ">" and lab_value > threshold:
                                        meets_threshold = True
                                    elif op == ">=" and lab_value >= threshold:
                                        meets_threshold = True
                                    elif op == "=" and lab_value == threshold:
                                        meets_threshold = True

                                    if meets_threshold:
                                        lab_found = True
                                        evidence.append({
                                            "type": "lab",
                                            "name": req_lab.get("name"),
                                            "value": lab_value,
                                            "threshold": f"{op}{threshold}",
                                            "date": str(lab_date) if lab_date else None,
                                        })
                                except (ValueError, TypeError):
                                    pass
                        elif req_lab.get("presence"):
                            lab_found = True
                            evidence.append({
                                "type": "lab",
                                "name": req_lab.get("name"),
                                "presence": True,
                                "date": str(lab_date) if lab_date else None,
                            })

                if not lab_found and not (criteria.required_diagnoses or criteria.required_medications):
                    # Lab is required but not found
                    return False, evidence, {
                        "element": f"{req_lab.get('name', 'Lab test')} test",
                        "codes": [req_lab.get("loinc", "")],
                        "due_date": measurement_date,
                    }

        # Check required procedures
        if criteria.required_procedures:
            patient_procedures = patient_data.get("procedures", [])
            proc_found = False
            for proc in patient_procedures:
                proc_date = proc.get("date")
                if proc_date:
                    if isinstance(proc_date, str):
                        proc_date = datetime.strptime(proc_date, "%Y-%m-%d").date()
                    if proc_date < lookback_start:
                        continue

                if proc.get("code") in criteria.required_procedures:
                    proc_found = True
                    evidence.append({
                        "type": "procedure",
                        "code": proc.get("code"),
                        "date": str(proc_date) if proc_date else None,
                    })
                    break

            if not proc_found and not (criteria.required_labs or criteria.required_diagnoses):
                return False, evidence, {
                    "element": "Required procedure",
                    "codes": criteria.required_procedures[:5],
                    "due_date": measurement_date,
                }

        # Check required diagnoses (for conditions like nephropathy)
        if criteria.required_diagnoses:
            patient_diagnoses = [d.get("code", "") for d in patient_data.get("diagnoses", [])]
            dx_found = any(
                any(pd.startswith(req) for req in criteria.required_diagnoses)
                for pd in patient_diagnoses
            )
            if dx_found:
                evidence.append({
                    "type": "diagnosis",
                    "note": "Has qualifying diagnosis",
                })

        # Check required medications
        if criteria.required_medications:
            patient_meds = patient_data.get("medications", [])
            med_found = False
            for med in patient_meds:
                if med.get("rxnorm") in criteria.required_medications:
                    # Check if medication is active within lookback period
                    end_date = med.get("end_date")
                    if end_date:
                        if isinstance(end_date, str):
                            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                        if end_date >= lookback_start:
                            med_found = True
                            evidence.append({
                                "type": "medication",
                                "rxnorm": med.get("rxnorm"),
                                "active": True,
                            })
                            break
                    else:
                        med_found = True
                        evidence.append({
                            "type": "medication",
                            "rxnorm": med.get("rxnorm"),
                            "active": True,
                        })
                        break

            if med_found:
                pass  # Medication satisfies numerator
            elif not evidence:
                return False, evidence, {
                    "element": "Required medication",
                    "codes": criteria.required_medications[:5],
                    "due_date": measurement_date,
                }

        # Check value thresholds (e.g., BP, PDC)
        if criteria.value_thresholds:
            vitals = patient_data.get("vitals", [])
            for threshold in criteria.value_thresholds:
                value_name = threshold.get("name", "")

                # Find most recent value
                matching_vitals = [
                    v for v in vitals
                    if v.get("name", "").lower() == value_name.lower()
                ]

                if matching_vitals:
                    # Sort by date descending
                    matching_vitals.sort(
                        key=lambda v: v.get("date", "1900-01-01"),
                        reverse=True
                    )
                    most_recent = matching_vitals[0]
                    value = most_recent.get("value")

                    if value is not None:
                        try:
                            value = float(value)
                            target = float(threshold["value"])
                            op = threshold["operator"]

                            meets = False
                            if op == "<" and value < target:
                                meets = True
                            elif op == "<=" and value <= target:
                                meets = True
                            elif op == ">" and value > target:
                                meets = True
                            elif op == ">=" and value >= target:
                                meets = True

                            if meets:
                                evidence.append({
                                    "type": "vital",
                                    "name": value_name,
                                    "value": value,
                                    "threshold": f"{op}{target}",
                                })
                            else:
                                return False, evidence, {
                                    "element": f"{value_name} control",
                                    "codes": [],
                                    "due_date": measurement_date,
                                }
                        except (ValueError, TypeError):
                            pass

        # If we have evidence, patient is compliant
        if evidence:
            return True, evidence, None

        # Default to non-compliant if no evidence found
        return False, evidence, {
            "element": "Required evidence",
            "codes": [],
            "due_date": measurement_date,
        }

    def _generate_patient_instructions(
        self,
        measure: QualityMeasure,
        missing: dict[str, Any],
    ) -> str:
        """Generate patient-friendly instructions for closing a care gap."""
        element = missing.get("element", "health service")

        instructions = {
            "HbA1c test": "Please schedule a blood test to check your HbA1c (diabetes control). This is typically done every 3-6 months for diabetes management.",
            "Eye exam": "Please schedule a dilated eye exam with an ophthalmologist or optometrist to check for diabetes-related eye problems.",
            "Required procedure": "Please schedule an appointment with your provider to discuss the recommended procedure.",
            "Required medication": "Please talk to your provider about starting or continuing the recommended medication.",
            "systolic_bp control": "Work with your provider to keep your blood pressure under control. This may include medication adjustments, diet changes, and exercise.",
            "PDC": "Make sure to take your medications as prescribed and refill them on time. Consider using a pill organizer or setting reminders.",
        }

        return instructions.get(element, f"Please contact your healthcare provider about {element}.")

    def get_patient_gaps(
        self,
        patient_id: str,
        patient_data: dict[str, Any],
        priority_filter: MeasurePriority | None = None,
    ) -> list[PatientGap]:
        """Get care gaps for a patient.

        Args:
            patient_id: Patient identifier
            patient_data: Patient clinical data
            priority_filter: Filter by priority level

        Returns:
            List of care gaps sorted by priority
        """
        result = self.evaluate_patient(patient_id, patient_data)
        gaps = result.care_gaps

        if priority_filter:
            gaps = [g for g in gaps if g.priority == priority_filter]

        # Sort by priority (critical first)
        priority_order = {
            MeasurePriority.CRITICAL: 0,
            MeasurePriority.HIGH: 1,
            MeasurePriority.MEDIUM: 2,
            MeasurePriority.LOW: 3,
        }
        gaps.sort(key=lambda g: priority_order.get(g.priority, 4))

        return gaps

    def calculate_performance(
        self,
        measure_id: str,
        patients_data: list[dict[str, Any]],
        period_start: date,
        period_end: date,
    ) -> MeasurePerformance:
        """Calculate aggregate performance for a measure.

        Args:
            measure_id: Measure ID
            patients_data: List of patient data dictionaries
            period_start: Start of measurement period
            period_end: End of measurement period

        Returns:
            MeasurePerformance with aggregate statistics
        """
        measure = self._measures_by_id.get(measure_id)
        if not measure:
            raise ValueError(f"Unknown measure: {measure_id}")

        eligible_count = 0
        numerator_count = 0
        excluded_count = 0
        gap_count = 0
        critical_gap_count = 0
        high_gap_count = 0

        for patient_data in patients_data:
            patient_id = patient_data.get("patient_id", "unknown")
            result = self.evaluate_patient(
                patient_id=patient_id,
                patient_data=patient_data,
                measure_ids=[measure_id],
                measurement_date=period_end,
            )

            for mr in result.measure_results:
                if mr.status == ComplianceStatus.EXCLUDED:
                    excluded_count += 1
                elif mr.is_eligible:
                    eligible_count += 1
                    if mr.in_numerator:
                        numerator_count += 1
                    elif mr.gap:
                        gap_count += 1
                        if mr.gap.priority == MeasurePriority.CRITICAL:
                            critical_gap_count += 1
                        elif mr.gap.priority == MeasurePriority.HIGH:
                            high_gap_count += 1

        denominator = eligible_count
        performance_rate = (numerator_count / denominator) if denominator > 0 else 0.0

        # Calculate star rating (1-5)
        star_rating = 1
        if performance_rate >= measure.benchmark_90th:
            star_rating = 5
        elif performance_rate >= (measure.benchmark_50th + measure.benchmark_90th) / 2:
            star_rating = 4
        elif performance_rate >= measure.benchmark_50th:
            star_rating = 3
        elif performance_rate >= measure.benchmark_50th * 0.8:
            star_rating = 2

        return MeasurePerformance(
            measure_id=measure.id,
            measure_name=measure.name,
            category=measure.category,
            period_start=period_start,
            period_end=period_end,
            eligible_population=eligible_count,
            numerator_count=numerator_count,
            denominator_count=denominator,
            excluded_count=excluded_count,
            performance_rate=round(performance_rate, 3),
            benchmark_50th=measure.benchmark_50th,
            benchmark_90th=measure.benchmark_90th,
            meets_benchmark=performance_rate >= measure.benchmark_50th,
            star_rating=star_rating,
            total_gaps=gap_count,
            critical_gaps=critical_gap_count,
            high_priority_gaps=high_gap_count,
        )

    def generate_performance_report(
        self,
        patients_data: list[dict[str, Any]],
        period_start: date,
        period_end: date,
        measure_ids: list[str] | None = None,
    ) -> PerformanceReport:
        """Generate aggregate performance report.

        Args:
            patients_data: List of patient data dictionaries
            period_start: Start of measurement period
            period_end: End of measurement period
            measure_ids: Specific measures to include (all if None)

        Returns:
            PerformanceReport with aggregate statistics
        """
        import time
        start_time = time.perf_counter()

        measures_to_evaluate = self._measures
        if measure_ids:
            measures_to_evaluate = [m for m in self._measures if m.id in measure_ids]

        measure_performances: list[MeasurePerformance] = []
        performance_by_category: dict[str, list[float]] = {}
        total_gaps = 0
        measures_meeting_benchmark = 0

        for measure in measures_to_evaluate:
            perf = self.calculate_performance(
                measure_id=measure.id,
                patients_data=patients_data,
                period_start=period_start,
                period_end=period_end,
            )
            measure_performances.append(perf)

            if perf.meets_benchmark:
                measures_meeting_benchmark += 1

            total_gaps += perf.total_gaps

            cat = measure.category.value
            if cat not in performance_by_category:
                performance_by_category[cat] = []
            performance_by_category[cat].append(perf.performance_rate)

        # Calculate category averages
        category_averages = {
            cat: round(sum(rates) / len(rates), 3) if rates else 0.0
            for cat, rates in performance_by_category.items()
        }

        # Calculate overall average
        all_rates = [p.performance_rate for p in measure_performances]
        average_rate = sum(all_rates) / len(all_rates) if all_rates else 0.0

        report_time = (time.perf_counter() - start_time) * 1000

        return PerformanceReport(
            report_date=datetime.now(),
            period_start=period_start,
            period_end=period_end,
            measures=measure_performances,
            total_measures=len(measure_performances),
            measures_meeting_benchmark=measures_meeting_benchmark,
            average_performance_rate=round(average_rate, 3),
            performance_by_category=category_averages,
            total_care_gaps=total_gaps,
            gap_closure_rate=0.0,  # Would need historical data
            report_time_ms=round(report_time, 2),
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        by_category = {}
        by_type = {}
        for m in self._measures:
            cat = m.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            mt = m.measure_type.value
            by_type[mt] = by_type.get(mt, 0) + 1

        return {
            "total_measures": len(self._measures),
            "by_category": by_category,
            "by_type": by_type,
        }


# ============================================================================
# Singleton Pattern
# ============================================================================

_service_instance: QualityMeasureService | None = None
_service_lock = threading.Lock()


def get_quality_measure_service() -> QualityMeasureService:
    """Get singleton instance of QualityMeasureService."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = QualityMeasureService()
    return _service_instance


def reset_quality_measure_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
