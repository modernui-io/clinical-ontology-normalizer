"""Data-Driven Clinical Calculator Definitions.

This module provides comprehensive data structures for defining clinical calculators
in a declarative, data-driven manner. Based on patterns from:
- MDCalc (900+ calculators): https://www.mdcalc.com/
- EBMcalc: https://ebmcalc.com/
- MedCalc-Bench (NCBI/NLM): https://github.com/ncbi-nlp/MedCalc-Bench

Calculator Types Supported:
1. CRITERIA: Point-based scoring (CHA2DS2-VASc, HAS-BLED, Wells, CURB-65)
2. EQUATION: Mathematical formulas (BMI, eGFR, MELD, ASCVD)
3. DECISION_TREE: Algorithmic pathways (Ottawa Ankle, PERC)
4. CONVERSION: Unit conversions (temperature, weight, lab values)

Scoring Patterns:
- Boolean criteria (1 point if true)
- Multi-level criteria (0/1/2 points based on severity)
- Threshold criteria (points based on numeric ranges)
- Age-based scoring (tiered by age brackets)

The data-driven approach handles:
- Calculator metadata (name, category, specialty, references)
- Scoring criteria definitions (all patterns)
- Risk threshold interpretations
- Recommendations per risk level
- Formula parameter definitions (for equation-based)

This reduces repetitive boilerplate while keeping formulas safe and testable.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RiskLevel(str, Enum):
    """Risk stratification levels."""
    LOW = "low"
    LOW_MODERATE = "low_moderate"
    MODERATE = "moderate"
    MODERATE_HIGH = "moderate_high"
    HIGH = "high"
    VERY_HIGH = "very_high"


class CalculatorType(str, Enum):
    """Calculator computation types (based on MDCalc/MedCalc-Bench taxonomy)."""
    CRITERIA = "criteria"  # Rule-based scoring (risk, severity, diagnosis)
    EQUATION = "equation"  # Mathematical formulas (lab test, dosage, physical)
    DECISION_TREE = "decision_tree"  # Algorithmic pathways
    CONVERSION = "conversion"  # Unit conversions


class CalculatorCategory(str, Enum):
    """Calculator clinical categories (based on MDCalc specialties)."""
    CARDIOVASCULAR = "cardiovascular"
    RENAL = "renal"
    HEPATIC = "hepatic"
    CRITICAL_CARE = "critical_care"
    PULMONARY = "pulmonary"
    NEUROLOGICAL = "neurological"
    INFECTIOUS = "infectious"
    SURGICAL = "surgical"
    OBSTETRIC = "obstetric"
    METABOLIC = "metabolic"
    HEMATOLOGY = "hematology"
    ONCOLOGY = "oncology"
    EMERGENCY = "emergency"
    PEDIATRIC = "pediatric"
    GERIATRIC = "geriatric"
    GENERAL = "general"


class OutputType(str, Enum):
    """Calculator output types (based on MedCalc-Bench)."""
    INTEGER = "integer"  # Whole number score
    DECIMAL = "decimal"  # Floating point value
    PERCENTAGE = "percentage"  # Risk as percentage
    CATEGORY = "category"  # Categorical result (low/moderate/high)
    DATE = "date"  # Date calculation (e.g., due date)
    DURATION = "duration"  # Time duration (weeks, days)


@dataclass
class ScoringCriterion:
    """A single boolean scoring criterion for point-based calculators.

    Use for simple yes/no criteria that award fixed points.

    Attributes:
        name: Parameter name (e.g., "congestive_heart_failure")
        display_name: Human-readable name (e.g., "CHF")
        points: Points awarded if criterion is met
        description: Clinical description for documentation
    """
    name: str
    display_name: str
    points: int
    description: str = ""


@dataclass
class MultiLevelCriterion:
    """Multi-level scoring criterion (0/1/2 points based on severity).

    Use for criteria like HEART score history (slightly/moderately/highly suspicious)
    or troponin levels (normal/1-3x/3x+ ULN).

    Attributes:
        name: Parameter name base (e.g., "history")
        display_name: Human-readable category (e.g., "History")
        levels: List of (level_name, points, display_text) tuples
                First match wins, so order from most to least severe.
        description: Clinical description
    """
    name: str
    display_name: str
    levels: list[tuple[str, int, str]]  # [(param_suffix, points, display), ...]
    description: str = ""


@dataclass
class ThresholdCriterion:
    """Threshold-based scoring criterion for numeric values.

    Use for criteria like SIRS temperature (>38°C or <36°C awards 1 point).

    Attributes:
        name: Parameter name (e.g., "temperature")
        display_name: Human-readable name (e.g., "Temperature")
        thresholds: List of (operator, value, points, display) tuples
                   Operators: "gt", "lt", "gte", "lte", "eq", "between"
        unit: Unit of measurement (e.g., "°C", "bpm")
        description: Clinical description
    """
    name: str
    display_name: str
    thresholds: list[tuple[str, float | tuple[float, float], int, str]]
    unit: str = ""
    description: str = ""


@dataclass
class AgeScoringRule:
    """Age-based scoring rule for calculators with age thresholds.

    Attributes:
        thresholds: List of (age_threshold, points) tuples, evaluated high to low
        display_format: Format string for component display (e.g., "Age ≥{threshold}")
    """
    thresholds: list[tuple[int, int]]  # [(threshold, points), ...]
    display_format: str = "Age ≥{threshold}"


@dataclass
class FormulaParameter:
    """Parameter definition for equation-based calculators.

    Attributes:
        name: Parameter name (e.g., "creatinine")
        display_name: Human-readable name (e.g., "Serum Creatinine")
        unit: Unit of measurement (e.g., "mg/dL")
        min_value: Minimum valid value (for validation)
        max_value: Maximum valid value (for validation)
        required: Whether parameter is required
        description: Clinical description
    """
    name: str
    display_name: str
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None
    required: bool = True
    description: str = ""


@dataclass
class FormulaDefinition:
    """Definition for equation-based calculators.

    The actual formula stays as Python code for safety, but this defines
    the parameters and expected output.

    Attributes:
        parameters: List of input parameters
        formula_text: Human-readable formula description
        output_unit: Unit of the calculated result
        precision: Number of decimal places for output
    """
    parameters: list[FormulaParameter]
    formula_text: str
    output_unit: str
    precision: int = 1


@dataclass
class ThresholdInterpretation:
    """Risk interpretation based on score thresholds.

    Attributes:
        min_score: Minimum score for this interpretation (inclusive)
        max_score: Maximum score for this interpretation (exclusive, None=no limit)
        risk_level: Risk classification
        interpretation: Clinical interpretation text
        recommendations: List of clinical recommendations
    """
    min_score: int | float
    max_score: int | float | None
    risk_level: RiskLevel
    interpretation: str
    recommendations: list[str]


@dataclass
class CalculatorDefinition:
    """Complete definition for a clinical calculator.

    Supports multiple calculator types from MDCalc/MedCalc-Bench taxonomy:
    - CRITERIA: Point-based scoring with boolean, multi-level, or threshold criteria
    - EQUATION: Mathematical formulas with defined parameters
    - DECISION_TREE: Algorithmic decision pathways
    - CONVERSION: Unit conversion calculations

    Attributes:
        id: Unique calculator identifier (e.g., "chadsvasc")
        name: Full display name (e.g., "CHA₂DS₂-VASc Score")
        short_name: Abbreviated name (e.g., "CHA2DS2-VASc")
        calc_type: Type of calculator (CRITERIA, EQUATION, etc.)
        category: Clinical category (cardiovascular, renal, etc.)
        output_type: Type of output (integer, decimal, percentage, etc.)
        score_unit: Unit for the score (e.g., "points", "kg/m²", "%")
        references: List of literature references
        description: Clinical description/indication
        criteria: List of boolean scoring criteria
        multi_level_criteria: List of multi-level criteria (0/1/2 points)
        threshold_criteria: List of threshold-based criteria
        age_scoring: Age-based scoring rule (optional)
        formula: Formula definition (for equation-based)
        interpretations: List of threshold interpretations
        notes: Additional clinical notes
        specialties: List of relevant medical specialties
    """
    id: str
    name: str
    short_name: str
    calc_type: CalculatorType = CalculatorType.CRITERIA
    category: CalculatorCategory = CalculatorCategory.GENERAL
    output_type: OutputType = OutputType.INTEGER
    score_unit: str = "points"
    references: list[str] = field(default_factory=list)
    description: str = ""
    criteria: list[ScoringCriterion] = field(default_factory=list)
    multi_level_criteria: list[MultiLevelCriterion] = field(default_factory=list)
    threshold_criteria: list[ThresholdCriterion] = field(default_factory=list)
    age_scoring: AgeScoringRule | None = None
    formula: FormulaDefinition | None = None
    interpretations: list[ThresholdInterpretation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)


@dataclass
class CalculatorResult:
    """Result from a clinical calculator.

    Attributes:
        calculator_name: Name of the calculator used
        score: Calculated score value
        score_unit: Unit of measurement
        risk_level: Risk classification
        interpretation: Clinical interpretation
        recommendations: List of recommendations
        components: Score breakdown by component
        references: Literature references
        warnings: Any applicable warnings
    """
    calculator_name: str
    score: float
    score_unit: str
    risk_level: RiskLevel
    interpretation: str
    recommendations: list[str]
    components: dict[str, Any] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _evaluate_threshold(
    value: float,
    operator: str,
    threshold: float | tuple[float, float],
) -> bool:
    """Evaluate a threshold condition."""
    if operator == "gt":
        return value > threshold
    elif operator == "lt":
        return value < threshold
    elif operator == "gte":
        return value >= threshold
    elif operator == "lte":
        return value <= threshold
    elif operator == "eq":
        return value == threshold
    elif operator == "between":
        if isinstance(threshold, tuple):
            return threshold[0] <= value <= threshold[1]
    elif operator == "outside":
        if isinstance(threshold, tuple):
            return value < threshold[0] or value > threshold[1]
    return False


def calculate_point_based_score(
    definition: CalculatorDefinition,
    values: dict[str, bool | int | float],
    age: int | None = None,
) -> CalculatorResult:
    """Calculate score for a point-based calculator using its definition.

    Supports three types of criteria:
    1. Boolean criteria: Simple yes/no with fixed points
    2. Multi-level criteria: 0/1/2 points based on severity level
    3. Threshold criteria: Points based on numeric value ranges

    Args:
        definition: Calculator definition with criteria and interpretations
        values: Dict mapping criterion names to values (bool, int, or float)
        age: Patient age (for calculators with age-based scoring)

    Returns:
        CalculatorResult with score and interpretation
    """
    score = 0
    components: dict[str, int] = {}

    # 1. Sum points from boolean criteria
    for criterion in definition.criteria:
        if values.get(criterion.name, False):
            score += criterion.points
            components[criterion.display_name] = criterion.points

    # 2. Process multi-level criteria (0/1/2 based on severity)
    for mlc in definition.multi_level_criteria:
        matched = False
        for level_suffix, points, display in mlc.levels:
            param_name = f"{mlc.name}_{level_suffix}"
            if values.get(param_name, False):
                score += points
                components[display] = points
                matched = True
                break
        if not matched:
            # No level matched, record 0 points for the base criterion
            components[f"{mlc.display_name} (none)"] = 0

    # 3. Process threshold-based criteria (numeric ranges)
    for tc in definition.threshold_criteria:
        value = values.get(tc.name)
        if value is not None and isinstance(value, (int, float)):
            for operator, threshold, points, display in tc.thresholds:
                if _evaluate_threshold(float(value), operator, threshold):
                    score += points
                    components[display] = points
                    break

    # 4. Apply age-based scoring if applicable
    if age is not None and definition.age_scoring is not None:
        sorted_thresholds = sorted(definition.age_scoring.thresholds, reverse=True)
        for i, (threshold, points) in enumerate(sorted_thresholds):
            if age >= threshold:
                score += points
                # Determine display format - if there's a higher threshold, show range
                if i == 0:  # Highest threshold
                    display = f"Age ≥{threshold}"
                else:
                    higher_threshold = sorted_thresholds[i - 1][0]
                    display = f"Age {threshold}-{higher_threshold - 1}"
                components[display] = points
                break

    # Find matching interpretation
    interpretation = None
    for interp in definition.interpretations:
        if interp.min_score <= score:
            if interp.max_score is None or score < interp.max_score:
                interpretation = interp
                break

    if interpretation is None:
        # Fallback if no interpretation matches
        interpretation = ThresholdInterpretation(
            min_score=0,
            max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="Score calculated",
            recommendations=["Consult clinical guidelines"],
        )

    return CalculatorResult(
        calculator_name=definition.name,
        score=score,
        score_unit=definition.score_unit,
        risk_level=interpretation.risk_level,
        interpretation=interpretation.interpretation,
        recommendations=interpretation.recommendations,
        components=components,
        references=definition.references,
    )


# ============================================================================
# Calculator Definitions Registry
# ============================================================================

CHADSVASC_DEFINITION = CalculatorDefinition(
    id="chadsvasc",
    name="CHA₂DS₂-VASc Score",
    short_name="CHA2DS2-VASc",
    category=CalculatorCategory.CARDIOVASCULAR,
    score_unit="points",
    description="Stroke risk stratification in atrial fibrillation",
    references=["2019 AHA/ACC/HRS AF Guidelines"],
    criteria=[
        ScoringCriterion("congestive_heart_failure", "CHF", 1, "History of congestive heart failure"),
        ScoringCriterion("hypertension", "Hypertension", 1, "History of hypertension"),
        ScoringCriterion("diabetes", "Diabetes", 1, "History of diabetes mellitus"),
        ScoringCriterion("stroke_tia_thromboembolism", "Prior Stroke/TIA", 2, "Prior stroke, TIA, or thromboembolism"),
        ScoringCriterion("vascular_disease", "Vascular disease", 1, "Prior MI, PAD, or aortic plaque"),
        ScoringCriterion("female", "Female", 1, "Female sex"),
    ],
    age_scoring=AgeScoringRule(
        thresholds=[(75, 2), (65, 1)],
        display_format="Age {threshold}-{next}",  # Special handling needed
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - anticoagulation generally not recommended",
            recommendations=[
                "Anticoagulation not recommended",
                "Consider aspirin or no therapy",
                "Reassess risk factors annually",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=2,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low-moderate risk - consider anticoagulation",
            recommendations=[
                "Consider oral anticoagulation based on patient preferences",
                "If male with score 1 (no other risk factors), may consider no therapy",
                "Discuss bleeding risk vs stroke prevention",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate risk - anticoagulation recommended",
            recommendations=[
                "Oral anticoagulation recommended",
                "DOAC preferred over warfarin in most cases",
                "Assess bleeding risk (HAS-BLED score)",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=5,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk - anticoagulation strongly recommended",
            recommendations=[
                "Oral anticoagulation strongly recommended",
                "DOAC preferred unless contraindicated",
                "Consider left atrial appendage closure if anticoagulation contraindicated",
                "Strict risk factor control",
            ],
        ),
        ThresholdInterpretation(
            min_score=5, max_score=None,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="High risk - anticoagulation strongly recommended",
            recommendations=[
                "Oral anticoagulation strongly recommended",
                "DOAC preferred unless contraindicated",
                "Consider left atrial appendage closure if anticoagulation contraindicated",
                "Strict risk factor control",
            ],
        ),
    ],
)


HASBLED_DEFINITION = CalculatorDefinition(
    id="hasbled",
    name="HAS-BLED Score",
    short_name="HAS-BLED",
    category=CalculatorCategory.CARDIOVASCULAR,
    score_unit="points",
    description="Major bleeding risk on anticoagulation",
    references=["Pisters R, et al. Chest 2010"],
    criteria=[
        ScoringCriterion("hypertension", "Hypertension", 1, "Uncontrolled SBP >160 mmHg"),
        ScoringCriterion("renal_disease", "Abnormal renal function", 1, "Dialysis, transplant, Cr >2.6 mg/dL"),
        ScoringCriterion("liver_disease", "Abnormal liver function", 1, "Cirrhosis or bilirubin >2x normal + ALT/AST >3x normal"),
        ScoringCriterion("stroke_history", "Stroke history", 1, "Prior stroke"),
        ScoringCriterion("bleeding_history", "Bleeding history", 1, "Prior major bleeding or predisposition"),
        ScoringCriterion("labile_inr", "Labile INR", 1, "Unstable/high INRs or <60% time in therapeutic range"),
        ScoringCriterion("age_over_65", "Age >65", 1, "Age over 65 years"),
        ScoringCriterion("antiplatelet_nsaid", "Antiplatelet/NSAID", 1, "Concomitant aspirin or NSAIDs"),
        ScoringCriterion("alcohol_use", "Alcohol use", 1, "≥8 drinks/week"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low bleeding risk",
            recommendations=[
                "Anticoagulation generally safe",
                "Standard monitoring",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate bleeding risk",
            recommendations=[
                "Anticoagulation can be considered",
                "Address modifiable risk factors",
                "Enhanced monitoring recommended",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High bleeding risk",
            recommendations=[
                "High bleeding risk does not contraindicate anticoagulation",
                "Address all modifiable risk factors",
                "Consider DOAC over warfarin",
                "Close monitoring and follow-up",
                "Consider PPI for GI protection",
            ],
        ),
    ],
)


WELLS_DVT_DEFINITION = CalculatorDefinition(
    id="wells_dvt",
    name="Wells Score for DVT",
    short_name="Wells DVT",
    category=CalculatorCategory.CARDIOVASCULAR,
    score_unit="points",
    description="Deep vein thrombosis probability assessment",
    references=["Wells PS, et al. Lancet 1997"],
    criteria=[
        ScoringCriterion("active_cancer", "Active cancer", 1, "Treatment ongoing or within 6 months"),
        ScoringCriterion("paralysis_paresis", "Paralysis/paresis", 1, "Recently bedridden >3 days or major surgery within 12 weeks"),
        ScoringCriterion("bedridden", "Bedridden/immobilization", 1, "Recently bedridden >3 days or major surgery within 12 weeks"),
        ScoringCriterion("localized_tenderness", "Localized tenderness", 1, "Along the deep venous system"),
        ScoringCriterion("entire_leg_swollen", "Entire leg swollen", 1, "Entire leg swelling"),
        ScoringCriterion("calf_swelling", "Calf swelling >3cm", 1, "Calf swelling >3cm compared to asymptomatic leg"),
        ScoringCriterion("pitting_edema", "Pitting edema", 1, "Confined to symptomatic leg"),
        ScoringCriterion("collateral_veins", "Collateral superficial veins", 1, "Non-varicose collateral veins"),
        ScoringCriterion("previous_dvt", "Previous DVT", 1, "Previously documented DVT"),
        ScoringCriterion("alternative_diagnosis", "Alternative diagnosis", -2, "Alternative diagnosis as or more likely than DVT"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=-2, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low probability DVT (3% prevalence)",
            recommendations=[
                "D-dimer testing recommended",
                "If D-dimer negative, DVT unlikely",
                "If D-dimer positive, proceed to ultrasound",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate probability DVT (17% prevalence)",
            recommendations=[
                "Consider D-dimer testing",
                "Ultrasound recommended if D-dimer elevated",
                "High-sensitivity D-dimer assay preferred",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High probability DVT (75% prevalence)",
            recommendations=[
                "Ultrasound recommended",
                "D-dimer not recommended as standalone",
                "Consider empiric anticoagulation while awaiting imaging",
            ],
        ),
    ],
)


CURB65_DEFINITION = CalculatorDefinition(
    id="curb65",
    name="CURB-65 Score",
    short_name="CURB-65",
    category=CalculatorCategory.PULMONARY,
    score_unit="points",
    description="Community-acquired pneumonia severity assessment",
    references=["Lim WS, et al. Thorax 2003"],
    criteria=[
        ScoringCriterion("confusion", "Confusion", 1, "New mental confusion"),
        ScoringCriterion("uremia", "Uremia", 1, "BUN >19 mg/dL (>7 mmol/L)"),
        ScoringCriterion("respiratory_rate", "Respiratory rate ≥30", 1, "Respiratory rate ≥30 breaths/min"),
        ScoringCriterion("low_blood_pressure", "Low BP", 1, "SBP <90 or DBP ≤60 mmHg"),
        ScoringCriterion("age_65_or_older", "Age ≥65", 1, "Age 65 years or older"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low severity - outpatient treatment appropriate",
            recommendations=[
                "Consider outpatient treatment",
                "Oral antibiotics usually sufficient",
                "Close follow-up recommended",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=2,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate severity - consider hospitalization",
            recommendations=[
                "Short inpatient stay or supervised outpatient",
                "IV antibiotics may be beneficial",
                "Reassess within 24-48 hours",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=4,
            risk_level=RiskLevel.HIGH,
            interpretation="Severe pneumonia - hospitalization required",
            recommendations=[
                "Inpatient hospitalization recommended",
                "IV antibiotics indicated",
                "Consider ICU evaluation if score ≥3",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=None,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very severe pneumonia - ICU consideration",
            recommendations=[
                "ICU admission may be warranted",
                "Aggressive supportive care",
                "Consider broad-spectrum antibiotics",
                "Monitor for sepsis and ARDS",
            ],
        ),
    ],
)


QSOFA_DEFINITION = CalculatorDefinition(
    id="qsofa",
    name="qSOFA Score",
    short_name="qSOFA",
    category=CalculatorCategory.CRITICAL_CARE,
    score_unit="points",
    description="Quick sepsis-related organ failure assessment",
    references=["Seymour CW, et al. JAMA 2016", "Singer M, et al. JAMA 2016"],
    criteria=[
        ScoringCriterion("respiratory_rate_22", "Respiratory rate ≥22", 1, "Respiratory rate ≥22 breaths/min"),
        ScoringCriterion("altered_mentation", "Altered mentation", 1, "GCS <15 or altered mental status"),
        ScoringCriterion("systolic_bp_100", "SBP ≤100", 1, "Systolic blood pressure ≤100 mmHg"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - not at high risk for poor outcome",
            recommendations=[
                "qSOFA ≥2 not met",
                "Continue monitoring for clinical deterioration",
                "Investigate for infection if suspected",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk - increased mortality risk from sepsis",
            recommendations=[
                "Assess for evidence of organ dysfunction",
                "Calculate full SOFA score",
                "Consider ICU level care",
                "Early antibiotics if infection suspected",
                "Fluid resuscitation as appropriate",
            ],
        ),
    ],
)


# Registry of all calculator definitions
HEART_SCORE_DEFINITION = CalculatorDefinition(
    id="heart_score",
    name="HEART Score",
    short_name="HEART",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Major adverse cardiac events risk in chest pain patients",
    references=["Six AJ, et al. Neth Heart J 2008", "Backus BE, et al. Int J Cardiol 2013"],
    specialties=["Emergency Medicine", "Cardiology"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="history",
            display_name="History",
            levels=[
                ("highly_suspicious", 2, "History (highly suspicious)"),
                ("moderately_suspicious", 1, "History (moderately suspicious)"),
                ("slightly_suspicious", 0, "History (slightly suspicious)"),
            ],
            description="History suspicion level for ACS",
        ),
        MultiLevelCriterion(
            name="ekg",
            display_name="EKG",
            levels=[
                ("significant_st_depression", 2, "EKG (significant ST depression)"),
                ("nonspecific_changes", 1, "EKG (non-specific changes)"),
                ("normal", 0, "EKG (normal)"),
            ],
            description="EKG findings",
        ),
        MultiLevelCriterion(
            name="risk_factors",
            display_name="Risk Factors",
            levels=[
                ("three_or_more", 2, "Risk factors ≥3"),
                ("one_or_two", 1, "Risk factors 1-2"),
                ("none", 0, "No risk factors"),
            ],
            description="HTN, DM, smoking, obesity, family hx, hyperlipidemia",
        ),
        MultiLevelCriterion(
            name="troponin",
            display_name="Troponin",
            levels=[
                ("elevated_3x", 2, "Troponin >3x ULN"),
                ("elevated_1_3x", 1, "Troponin 1-3x ULN"),
                ("normal", 0, "Troponin normal"),
            ],
            description="Initial troponin level",
        ),
    ],
    age_scoring=AgeScoringRule(
        thresholds=[(65, 2), (45, 1)],
        display_format="Age ≥{threshold}",
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=4,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - consider early discharge",
            recommendations=[
                "Consider early discharge with outpatient follow-up",
                "Stress testing within 72 hours if discharged",
                "Return precautions for chest pain",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=7,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate risk - admission recommended",
            recommendations=[
                "Admission for observation recommended",
                "Serial troponins",
                "Consider non-invasive stress testing",
                "Cardiology consultation",
            ],
        ),
        ThresholdInterpretation(
            min_score=7, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk - early invasive management",
            recommendations=[
                "Admit to monitored bed",
                "Early invasive strategy recommended",
                "Cardiology consultation urgent",
                "Dual antiplatelet therapy if not contraindicated",
            ],
        ),
    ],
)


SIRS_DEFINITION = CalculatorDefinition(
    id="sirs",
    name="SIRS Criteria",
    short_name="SIRS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Systemic Inflammatory Response Syndrome criteria",
    references=["Bone RC, et al. Chest 1992"],
    specialties=["Critical Care", "Emergency Medicine", "Internal Medicine"],
    threshold_criteria=[
        ThresholdCriterion(
            name="temperature",
            display_name="Temperature",
            thresholds=[
                ("gt", 38.0, 1, "Temperature >38°C"),
                ("lt", 36.0, 1, "Temperature <36°C"),
            ],
            unit="°C",
            description="Body temperature abnormal (>38°C or <36°C)",
        ),
        ThresholdCriterion(
            name="heart_rate",
            display_name="Heart Rate",
            thresholds=[
                ("gt", 90, 1, "Heart rate >90 bpm"),
            ],
            unit="bpm",
            description="Heart rate >90 bpm",
        ),
        ThresholdCriterion(
            name="respiratory_rate",
            display_name="Respiratory Rate",
            thresholds=[
                ("gt", 20, 1, "Respiratory rate >20/min"),
            ],
            unit="/min",
            description="Respiratory rate >20/min or PaCO2 <32 mmHg",
        ),
        ThresholdCriterion(
            name="wbc",
            display_name="WBC",
            thresholds=[
                ("gt", 12.0, 1, "WBC >12,000"),
                ("lt", 4.0, 1, "WBC <4,000"),
            ],
            unit="×10³/µL",
            description="WBC >12,000 or <4,000 or >10% bands",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="SIRS negative",
            recommendations=[
                "SIRS criteria not met",
                "Continue monitoring vital signs",
                "Investigate other causes of symptoms",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="SIRS positive - evaluate for infection",
            recommendations=[
                "SIRS criteria met - evaluate for infection source",
                "Consider sepsis workup (cultures, lactate)",
                "Monitor for organ dysfunction (qSOFA, SOFA)",
                "Early antibiotics if infection suspected",
            ],
        ),
    ],
)


GCS_DEFINITION = CalculatorDefinition(
    id="gcs",
    name="Glasgow Coma Scale",
    short_name="GCS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Level of consciousness assessment",
    references=["Teasdale G, Jennett B. Lancet 1974"],
    specialties=["Emergency Medicine", "Neurology", "Critical Care", "Trauma"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="eye",
            display_name="Eye Opening",
            levels=[
                ("spontaneous", 4, "Eye: Spontaneous (4)"),
                ("to_voice", 3, "Eye: To voice (3)"),
                ("to_pain", 2, "Eye: To pain (2)"),
                ("none", 1, "Eye: None (1)"),
            ],
            description="Best eye opening response",
        ),
        MultiLevelCriterion(
            name="verbal",
            display_name="Verbal Response",
            levels=[
                ("oriented", 5, "Verbal: Oriented (5)"),
                ("confused", 4, "Verbal: Confused (4)"),
                ("inappropriate", 3, "Verbal: Inappropriate words (3)"),
                ("incomprehensible", 2, "Verbal: Incomprehensible sounds (2)"),
                ("none", 1, "Verbal: None (1)"),
            ],
            description="Best verbal response",
        ),
        MultiLevelCriterion(
            name="motor",
            display_name="Motor Response",
            levels=[
                ("obeys", 6, "Motor: Obeys commands (6)"),
                ("localizes", 5, "Motor: Localizes pain (5)"),
                ("withdraws", 4, "Motor: Withdraws from pain (4)"),
                ("flexion", 3, "Motor: Abnormal flexion (3)"),
                ("extension", 2, "Motor: Extension (2)"),
                ("none", 1, "Motor: None (1)"),
            ],
            description="Best motor response",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=3, max_score=9,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe brain injury - GCS 3-8",
            recommendations=[
                "Airway protection likely needed",
                "Consider intubation for GCS ≤8",
                "Urgent neuroimaging",
                "Neurosurgery consultation",
            ],
        ),
        ThresholdInterpretation(
            min_score=9, max_score=13,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate brain injury - GCS 9-12",
            recommendations=[
                "Close neurological monitoring",
                "Neuroimaging recommended",
                "Frequent reassessment",
            ],
        ),
        ThresholdInterpretation(
            min_score=13, max_score=None,
            risk_level=RiskLevel.LOW,
            interpretation="Mild brain injury - GCS 13-15",
            recommendations=[
                "Observation and monitoring",
                "Consider CT if indicated by mechanism",
                "Discharge with head injury precautions if appropriate",
            ],
        ),
    ],
)


RCRI_DEFINITION = CalculatorDefinition(
    id="rcri",
    name="Revised Cardiac Risk Index (RCRI)",
    short_name="RCRI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Perioperative cardiac risk assessment for non-cardiac surgery",
    references=["Lee TH, et al. Circulation 1999"],
    specialties=["Anesthesiology", "Cardiology", "Surgery", "Internal Medicine"],
    criteria=[
        ScoringCriterion("high_risk_surgery", "High-risk surgery", 1,
                        "Intraperitoneal, intrathoracic, or suprainguinal vascular surgery"),
        ScoringCriterion("history_of_ihd", "Ischemic heart disease", 1,
                        "MI, positive exercise test, angina, nitrate use, Q waves on EKG"),
        ScoringCriterion("history_of_chf", "CHF history", 1,
                        "CHF history, pulmonary edema, PND, bilateral rales, S3, elevated BNP"),
        ScoringCriterion("history_of_cvd", "Cerebrovascular disease", 1,
                        "Stroke or TIA history"),
        ScoringCriterion("insulin_therapy", "Insulin therapy", 1,
                        "Preoperative insulin therapy for diabetes"),
        ScoringCriterion("preop_creatinine_over_2", "Creatinine >2", 1,
                        "Preoperative serum creatinine >2 mg/dL"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="RCRI Class I-II - Low perioperative cardiac risk (0.4-0.9%)",
            recommendations=[
                "Low cardiac risk - proceed with surgery",
                "No additional cardiac testing recommended",
                "Standard perioperative monitoring",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=2,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="RCRI Class II - Low risk (0.9% major cardiac event)",
            recommendations=[
                "Low cardiac risk - proceed with surgery",
                "Consider beta-blocker if already on one",
                "Standard perioperative monitoring",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="RCRI Class III - Moderate risk (6.6% major cardiac event)",
            recommendations=[
                "Moderate cardiac risk",
                "Consider non-invasive testing if poor functional capacity",
                "Perioperative beta-blockade may be beneficial",
                "Close hemodynamic monitoring",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="RCRI Class IV - High risk (≥11% major cardiac event)",
            recommendations=[
                "High cardiac risk",
                "Non-invasive cardiac testing recommended",
                "Cardiology consultation",
                "Consider revascularization if severe CAD",
                "Optimize medical therapy preoperatively",
                "ICU monitoring postoperatively",
            ],
        ),
    ],
)


PERC_DEFINITION = CalculatorDefinition(
    id="perc",
    name="PERC Rule for Pulmonary Embolism",
    short_name="PERC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Rule out pulmonary embolism without testing in low-risk patients",
    references=["Kline JA, et al. J Thromb Haemost 2004", "Kline JA, et al. J Thromb Haemost 2008"],
    specialties=["Emergency Medicine", "Pulmonology"],
    notes=["Only apply if pre-test probability is low (<15%)",
           "If ANY criteria present, PERC cannot rule out PE"],
    criteria=[
        ScoringCriterion("age_50_or_older", "Age ≥50", 1, "Age 50 years or older"),
        ScoringCriterion("heart_rate_100_or_more", "HR ≥100", 1, "Heart rate ≥100 bpm"),
        ScoringCriterion("o2_sat_less_than_95", "SpO2 <95%", 1, "Oxygen saturation <95% on room air"),
        ScoringCriterion("unilateral_leg_swelling", "Unilateral leg swelling", 1, "Unilateral leg swelling"),
        ScoringCriterion("hemoptysis", "Hemoptysis", 1, "Hemoptysis present"),
        ScoringCriterion("recent_surgery_trauma", "Recent surgery/trauma", 1, "Surgery or trauma within 4 weeks"),
        ScoringCriterion("prior_pe_dvt", "Prior PE/DVT", 1, "Prior PE or DVT"),
        ScoringCriterion("hormone_use", "Hormone use", 1, "Exogenous estrogen (OCP, HRT)"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="PERC negative - PE effectively ruled out",
            recommendations=[
                "No further workup for PE needed",
                "PERC criteria met - <2% chance of PE",
                "Consider alternative diagnoses",
                "No D-dimer or imaging required",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="PERC positive - cannot rule out PE",
            recommendations=[
                "PERC criteria NOT met",
                "D-dimer recommended",
                "If D-dimer elevated, CT-PA indicated",
                "Consider Wells PE score for risk stratification",
            ],
        ),
    ],
)


CENTOR_DEFINITION = CalculatorDefinition(
    id="centor",
    name="Centor Score (Modified/McIsaac)",
    short_name="Centor",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.INFECTIOUS,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Likelihood of streptococcal pharyngitis",
    references=["Centor RM, et al. Med Decis Making 1981", "McIsaac WJ, et al. CMAJ 1998"],
    specialties=["Emergency Medicine", "Family Medicine", "Pediatrics", "Internal Medicine"],
    criteria=[
        ScoringCriterion("tonsillar_exudates", "Tonsillar exudates", 1, "Tonsillar swelling or exudates"),
        ScoringCriterion("tender_anterior_cervical_nodes", "Tender anterior cervical lymphadenopathy", 1,
                        "Tender or swollen anterior cervical lymph nodes"),
        ScoringCriterion("fever_history", "History of fever", 1, "Temperature >38°C (100.4°F) by history"),
        ScoringCriterion("absence_of_cough", "Absence of cough", 1, "No cough present"),
    ],
    age_scoring=AgeScoringRule(
        thresholds=[(45, -1), (15, 0), (3, 1)],  # >44: -1, 15-44: 0, 3-14: +1
        display_format="Age adjustment",
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=-1, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low likelihood of strep (~1-10%)",
            recommendations=[
                "No further testing recommended",
                "Symptomatic treatment only",
                "Antibiotics not indicated",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate likelihood of strep (~11-35%)",
            recommendations=[
                "Rapid strep test recommended",
                "Treat if positive",
                "Consider throat culture if rapid test negative",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High likelihood of strep (~25-50%)",
            recommendations=[
                "Rapid strep test or throat culture",
                "Consider empiric antibiotics if testing unavailable",
                "Penicillin V or amoxicillin first-line",
            ],
        ),
    ],
)


APGAR_DEFINITION = CalculatorDefinition(
    id="apgar",
    name="APGAR Score",
    short_name="APGAR",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.OBSTETRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Newborn assessment at 1 and 5 minutes after birth",
    references=["Apgar V. Curr Res Anesth Analg 1953"],
    specialties=["Obstetrics", "Neonatology", "Pediatrics"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="appearance",
            display_name="Appearance (skin color)",
            levels=[
                ("pink", 2, "Appearance: Pink (2)"),
                ("acrocyanosis", 1, "Appearance: Body pink, extremities blue (1)"),
                ("blue_pale", 0, "Appearance: Blue/pale all over (0)"),
            ],
            description="Skin color: pink, blue extremities, or pale/blue",
        ),
        MultiLevelCriterion(
            name="pulse",
            display_name="Pulse (heart rate)",
            levels=[
                ("above_100", 2, "Pulse: >100 bpm (2)"),
                ("below_100", 1, "Pulse: <100 bpm (1)"),
                ("absent", 0, "Pulse: Absent (0)"),
            ],
            description="Heart rate: >100, <100, or absent",
        ),
        MultiLevelCriterion(
            name="grimace",
            display_name="Grimace (reflex irritability)",
            levels=[
                ("cry_sneeze", 2, "Grimace: Cry/sneeze/cough (2)"),
                ("grimace", 1, "Grimace: Grimace only (1)"),
                ("no_response", 0, "Grimace: No response (0)"),
            ],
            description="Response to stimulation",
        ),
        MultiLevelCriterion(
            name="activity",
            display_name="Activity (muscle tone)",
            levels=[
                ("active", 2, "Activity: Active movement (2)"),
                ("some_flexion", 1, "Activity: Some flexion (1)"),
                ("limp", 0, "Activity: Limp (0)"),
            ],
            description="Muscle tone: active, some flexion, or limp",
        ),
        MultiLevelCriterion(
            name="respiration",
            display_name="Respiration",
            levels=[
                ("crying", 2, "Respiration: Good cry (2)"),
                ("weak_cry", 1, "Respiration: Weak/irregular (1)"),
                ("absent", 0, "Respiration: Absent (0)"),
            ],
            description="Respiratory effort",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=4,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severely depressed - immediate resuscitation needed",
            recommendations=[
                "Initiate neonatal resuscitation",
                "Suction, stimulate, provide warmth",
                "Consider positive pressure ventilation",
                "May need intubation and chest compressions",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=7,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderately depressed - assisted ventilation likely needed",
            recommendations=[
                "Stimulation and suction",
                "Provide supplemental oxygen",
                "Consider positive pressure ventilation",
                "Continue monitoring and reassess at 5 minutes",
            ],
        ),
        ThresholdInterpretation(
            min_score=7, max_score=None,
            risk_level=RiskLevel.LOW,
            interpretation="Normal - routine newborn care",
            recommendations=[
                "Standard newborn care",
                "Skin-to-skin contact with mother",
                "Continue monitoring",
                "Reassess at 5 minutes",
            ],
        ),
    ],
)


# ============================================================================
# WELLS PE SCORE - Pulmonary Embolism Probability
# ============================================================================
WELLS_PE_DEFINITION = CalculatorDefinition(
    id="wells_pe",
    name="Wells' Criteria for Pulmonary Embolism",
    short_name="Wells PE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.DECIMAL,
    score_unit="points",
    description="Clinical probability assessment for pulmonary embolism",
    references=["Wells PS, et al. Ann Intern Med 1998", "Wells PS, et al. Thromb Haemost 2000"],
    specialties=["Emergency Medicine", "Pulmonology", "Internal Medicine"],
    criteria=[
        ScoringCriterion("clinical_signs_dvt", "Clinical signs of DVT", 3,
                        "Leg swelling, pain with palpation of deep veins"),
        ScoringCriterion("pe_most_likely", "PE is most likely diagnosis", 3,
                        "PE is #1 diagnosis, or equally likely"),
        ScoringCriterion("heart_rate_over_100", "Heart rate >100", 1.5,
                        "Heart rate greater than 100 bpm"),
        ScoringCriterion("immobilization_surgery", "Immobilization/surgery", 1.5,
                        "Immobilization ≥3 days or surgery in past 4 weeks"),
        ScoringCriterion("previous_pe_dvt", "Previous PE/DVT", 1.5,
                        "Objectively diagnosed PE or DVT"),
        ScoringCriterion("hemoptysis", "Hemoptysis", 1, "Hemoptysis present"),
        ScoringCriterion("malignancy", "Malignancy", 1,
                        "Cancer treatment within 6 months or palliative care"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low probability of PE (<2% if PERC negative)",
            recommendations=[
                "Consider PERC rule if low clinical suspicion",
                "If PERC positive, check D-dimer",
                "If D-dimer negative, PE excluded",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=6,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate probability of PE (~20%)",
            recommendations=[
                "D-dimer testing recommended",
                "If D-dimer elevated, CT-PA indicated",
                "If D-dimer negative, PE excluded",
            ],
        ),
        ThresholdInterpretation(
            min_score=6, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High probability of PE (~50-70%)",
            recommendations=[
                "CT-PA recommended (bypass D-dimer)",
                "Consider empiric anticoagulation while awaiting imaging",
                "If CT-PA negative but high suspicion, consider V/Q scan",
            ],
        ),
    ],
)


# ============================================================================
# CHARLSON COMORBIDITY INDEX
# ============================================================================
CHARLSON_DEFINITION = CalculatorDefinition(
    id="charlson",
    name="Charlson Comorbidity Index (CCI)",
    short_name="Charlson",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts 10-year survival based on comorbidities",
    references=["Charlson ME, et al. J Chronic Dis 1987"],
    specialties=["Internal Medicine", "Geriatrics", "Oncology", "Surgery"],
    criteria=[
        # 1-point conditions
        ScoringCriterion("mi", "Myocardial infarction", 1, "History of MI"),
        ScoringCriterion("chf", "Congestive heart failure", 1, "CHF"),
        ScoringCriterion("peripheral_vascular", "Peripheral vascular disease", 1, "PVD"),
        ScoringCriterion("cerebrovascular", "Cerebrovascular disease", 1, "CVA or TIA"),
        ScoringCriterion("dementia", "Dementia", 1, "Dementia"),
        ScoringCriterion("copd", "Chronic pulmonary disease", 1, "COPD"),
        ScoringCriterion("connective_tissue", "Connective tissue disease", 1, "Rheumatoid arthritis, lupus, etc."),
        ScoringCriterion("peptic_ulcer", "Peptic ulcer disease", 1, "PUD"),
        ScoringCriterion("mild_liver", "Mild liver disease", 1, "Chronic hepatitis, cirrhosis without portal HTN"),
        ScoringCriterion("diabetes_uncomplicated", "Diabetes (uncomplicated)", 1, "DM without end-organ damage"),
        # 2-point conditions
        ScoringCriterion("hemiplegia", "Hemiplegia", 2, "Hemiplegia"),
        ScoringCriterion("moderate_severe_ckd", "Moderate/severe CKD", 2, "Creatinine >3 or on dialysis"),
        ScoringCriterion("diabetes_complicated", "Diabetes with complications", 2, "DM with retinopathy, nephropathy, neuropathy"),
        ScoringCriterion("solid_tumor", "Tumor without metastasis", 2, "Solid tumor without mets (past 5 years)"),
        ScoringCriterion("leukemia", "Leukemia", 2, "Leukemia"),
        ScoringCriterion("lymphoma", "Lymphoma", 2, "Lymphoma"),
        # 3-point conditions
        ScoringCriterion("moderate_severe_liver", "Moderate/severe liver disease", 3, "Cirrhosis with portal HTN, varices"),
        # 6-point conditions
        ScoringCriterion("metastatic_tumor", "Metastatic solid tumor", 6, "Metastatic cancer"),
        ScoringCriterion("aids", "AIDS", 6, "AIDS (not just HIV+)"),
    ],
    age_scoring=AgeScoringRule(
        thresholds=[(80, 4), (70, 3), (60, 2), (50, 1), (0, 0)],
        display_format="Age points",
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low comorbidity burden - ~98% 10-year survival",
            recommendations=[
                "Standard treatment approaches appropriate",
                "Reassess annually or with new diagnoses",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=3,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mild comorbidity burden - ~90% 10-year survival",
            recommendations=[
                "Standard treatment generally appropriate",
                "Consider comorbidity impact on treatment decisions",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=5,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate comorbidity burden - ~77% 10-year survival",
            recommendations=[
                "Consider functional status in treatment decisions",
                "Multidisciplinary care coordination recommended",
                "May need modified treatment intensity",
            ],
        ),
        ThresholdInterpretation(
            min_score=5, max_score=7,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="High comorbidity burden - ~53% 10-year survival",
            recommendations=[
                "Goals of care discussion recommended",
                "Treatment modifications likely needed",
                "Close coordination with primary care",
            ],
        ),
        ThresholdInterpretation(
            min_score=7, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Very high comorbidity burden - <45% 10-year survival",
            recommendations=[
                "Advance care planning strongly recommended",
                "Consider palliative care consultation",
                "Treatment decisions should prioritize quality of life",
            ],
        ),
    ],
)


# ============================================================================
# TIMI RISK SCORE FOR STEMI
# ============================================================================
TIMI_STEMI_DEFINITION = CalculatorDefinition(
    id="timi_stemi",
    name="TIMI Risk Score for STEMI",
    short_name="TIMI-STEMI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="30-day mortality risk in STEMI patients",
    references=["Morrow DA, et al. Circulation 2000"],
    specialties=["Cardiology", "Emergency Medicine", "Critical Care"],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[
                ("gte", 75, 3, "Age ≥75"),
                ("range", (65, 75), 2, "Age 65-74"),
            ],
            description="Age category",
        ),
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[
                ("lt", 100, 3, "SBP <100 mmHg"),
            ],
            unit="mmHg",
            description="Systolic blood pressure",
        ),
        ThresholdCriterion(
            name="heart_rate",
            display_name="Heart Rate",
            thresholds=[
                ("gt", 100, 2, "HR >100 bpm"),
            ],
            unit="bpm",
            description="Heart rate",
        ),
        ThresholdCriterion(
            name="killip_class",
            display_name="Killip Class",
            thresholds=[
                ("gte", 2, 2, "Killip class II-IV"),
            ],
            description="Heart failure severity",
        ),
        ThresholdCriterion(
            name="weight",
            display_name="Weight",
            thresholds=[
                ("lt", 67, 1, "Weight <67 kg"),
            ],
            unit="kg",
            description="Body weight",
        ),
    ],
    criteria=[
        ScoringCriterion("anterior_st_elevation", "Anterior ST elevation or LBBB", 1,
                        "Anterior STEMI or new LBBB"),
        ScoringCriterion("time_to_treatment_over_4h", "Time to treatment >4 hours", 1,
                        "Time from symptom onset to treatment >4 hours"),
        ScoringCriterion("history_diabetes_htn_angina", "DM, HTN, or angina history", 1,
                        "History of diabetes, hypertension, or angina"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - 30-day mortality ~1.6%",
            recommendations=[
                "Standard STEMI care",
                "Primary PCI within 90 minutes",
                "Guideline-directed medical therapy",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=4,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low-intermediate risk - 30-day mortality ~4%",
            recommendations=[
                "Expedited reperfusion therapy",
                "Close hemodynamic monitoring",
                "Consider ICU level care",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=6,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk - 30-day mortality ~8%",
            recommendations=[
                "Urgent reperfusion - PCI preferred",
                "ICU monitoring",
                "Aggressive medical management",
                "Watch for cardiogenic shock",
            ],
        ),
        ThresholdInterpretation(
            min_score=6, max_score=8,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk - 30-day mortality ~17%",
            recommendations=[
                "Emergent PCI",
                "ICU monitoring with hemodynamic support ready",
                "Consider mechanical circulatory support",
                "Early involvement of heart failure/shock team",
            ],
        ),
        ThresholdInterpretation(
            min_score=8, max_score=None,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very high risk - 30-day mortality >25%",
            recommendations=[
                "Emergent PCI with shock team activation",
                "Consider IABP or Impella",
                "Goals of care discussion if appropriate",
                "Maximum medical support",
            ],
        ),
    ],
)


# ============================================================================
# TIMI RISK SCORE FOR NSTEMI/UA
# ============================================================================
TIMI_NSTEMI_DEFINITION = CalculatorDefinition(
    id="timi_nstemi",
    name="TIMI Risk Score for NSTEMI/UA",
    short_name="TIMI-NSTEMI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="14-day risk of death, MI, or urgent revascularization in NSTEMI/UA",
    references=["Antman EM, et al. JAMA 2000"],
    specialties=["Cardiology", "Emergency Medicine"],
    criteria=[
        ScoringCriterion("age_65_or_older", "Age ≥65", 1, "Age 65 years or older"),
        ScoringCriterion("3_or_more_cad_risk_factors", "≥3 CAD risk factors", 1,
                        "HTN, DM, dyslipidemia, family hx, smoking"),
        ScoringCriterion("known_cad", "Known CAD (stenosis ≥50%)", 1,
                        "Prior coronary stenosis ≥50%"),
        ScoringCriterion("aspirin_use_last_7_days", "Aspirin use in past 7 days", 1,
                        "ASA use within 7 days"),
        ScoringCriterion("severe_angina", "Severe angina (≥2 episodes/24h)", 1,
                        "2 or more anginal episodes in past 24 hours"),
        ScoringCriterion("st_changes", "ST changes ≥0.5mm", 1,
                        "ST deviation ≥0.5mm on ECG"),
        ScoringCriterion("elevated_cardiac_markers", "Elevated cardiac markers", 1,
                        "Elevated troponin or CK-MB"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - 14-day event rate ~5%",
            recommendations=[
                "Stress testing before discharge",
                "Consider non-invasive evaluation",
                "Optimal medical therapy",
                "Outpatient cardiology follow-up",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=4,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk - 14-day event rate ~12%",
            recommendations=[
                "Early invasive strategy within 24-72 hours",
                "Dual antiplatelet therapy",
                "Anticoagulation",
                "Cardiology consultation",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=5,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="Intermediate-high risk - 14-day event rate ~20%",
            recommendations=[
                "Urgent invasive strategy within 24 hours",
                "GP IIb/IIIa inhibitor consideration",
                "CCU monitoring",
                "Aggressive antiplatelet + anticoagulation",
            ],
        ),
        ThresholdInterpretation(
            min_score=5, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk - 14-day event rate >25%",
            recommendations=[
                "Immediate invasive strategy",
                "CCU monitoring",
                "Aggressive medical management",
                "Consider intra-aortic balloon pump if hemodynamically unstable",
            ],
        ),
    ],
)


# ============================================================================
# MELD SCORE (Model for End-Stage Liver Disease)
# ============================================================================
MELD_DEFINITION = CalculatorDefinition(
    id="meld",
    name="MELD Score (Original)",
    short_name="MELD",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="points",
    description="Predicts 3-month mortality in end-stage liver disease; used for transplant prioritization",
    references=["Kamath PS, et al. Hepatology 2001", "Wiesner R, et al. Gastroenterology 2003"],
    specialties=["Hepatology", "Transplant", "Gastroenterology", "Critical Care"],
    notes=[
        "Formula: 3.78×ln(bilirubin) + 11.2×ln(INR) + 9.57×ln(creatinine) + 6.43",
        "Minimum values: bilirubin 1.0, creatinine 1.0, INR 1.0",
        "Maximum creatinine: 4.0 (or 4.0 if on dialysis)",
        "Score range: 6-40",
    ],
    formula=FormulaDefinition(
        formula_text="3.78×ln(bilirubin) + 11.2×ln(INR) + 9.57×ln(creatinine) + 6.43",
        output_unit="points",
        precision=0,
        parameters=[
            FormulaParameter(
                name="bilirubin",
                display_name="Total Bilirubin",
                unit="mg/dL",
                min_value=1.0,
                max_value=None,
                description="Serum total bilirubin (minimum 1.0)",
            ),
            FormulaParameter(
                name="inr",
                display_name="INR",
                unit="",
                min_value=1.0,
                max_value=None,
                description="International normalized ratio (minimum 1.0)",
            ),
            FormulaParameter(
                name="creatinine",
                display_name="Creatinine",
                unit="mg/dL",
                min_value=1.0,
                max_value=4.0,
                description="Serum creatinine (min 1.0, max 4.0; use 4.0 if on dialysis)",
            ),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=10,
            risk_level=RiskLevel.LOW,
            interpretation="MELD <10 - Low 3-month mortality (~2%)",
            recommendations=[
                "Continue monitoring every 3 months",
                "Focus on treating underlying cause",
                "Unlikely to benefit from transplant at this time",
            ],
        ),
        ThresholdInterpretation(
            min_score=10, max_score=20,
            risk_level=RiskLevel.MODERATE,
            interpretation="MELD 10-19 - Moderate 3-month mortality (~6%)",
            recommendations=[
                "Monitor every 1-3 months",
                "Transplant evaluation if progressive disease",
                "Optimize nutrition and manage complications",
            ],
        ),
        ThresholdInterpretation(
            min_score=20, max_score=30,
            risk_level=RiskLevel.HIGH,
            interpretation="MELD 20-29 - High 3-month mortality (~20%)",
            recommendations=[
                "Active transplant listing if appropriate",
                "Monitor weekly to monthly",
                "Aggressive management of hepatic decompensation",
            ],
        ),
        ThresholdInterpretation(
            min_score=30, max_score=40,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="MELD 30-39 - Very high 3-month mortality (~50%)",
            recommendations=[
                "Urgent transplant evaluation",
                "ICU level monitoring if needed",
                "Consider living donor if available",
            ],
        ),
        ThresholdInterpretation(
            min_score=40, max_score=None,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="MELD ≥40 - Highest priority; >70% 3-month mortality",
            recommendations=[
                "Highest transplant priority",
                "ICU management",
                "Goals of care discussion if transplant not possible",
            ],
        ),
    ],
)


# ============================================================================
# MELD-Na SCORE
# ============================================================================
MELD_NA_DEFINITION = CalculatorDefinition(
    id="meld_na",
    name="MELD-Na Score",
    short_name="MELD-Na",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="points",
    description="MELD score adjusted for sodium; better predictor of waitlist mortality",
    references=["Kim WR, et al. Hepatology 2008", "OPTN Policy (2016)"],
    specialties=["Hepatology", "Transplant", "Gastroenterology"],
    notes=[
        "Formula: MELD + 1.32×(137-Na) - 0.033×MELD×(137-Na)",
        "Sodium bounds: 125-137 mEq/L",
        "Used by OPTN since January 2016 for transplant allocation",
    ],
    formula=FormulaDefinition(
        formula_text="MELD + 1.32×(137-Na) - 0.033×MELD×(137-Na)",
        output_unit="points",
        precision=0,
        parameters=[
            FormulaParameter(
                name="meld",
                display_name="MELD Score",
                unit="",
                min_value=6,
                max_value=40,
                description="Original MELD score",
            ),
            FormulaParameter(
                name="sodium",
                display_name="Serum Sodium",
                unit="mEq/L",
                min_value=125,
                max_value=137,
                description="Serum sodium (bounds: 125-137)",
            ),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=15,
            risk_level=RiskLevel.LOW,
            interpretation="MELD-Na <15 - Lower transplant priority",
            recommendations=[
                "Monitor every 3 months",
                "Address underlying liver disease",
                "Nutrition optimization",
            ],
        ),
        ThresholdInterpretation(
            min_score=15, max_score=25,
            risk_level=RiskLevel.MODERATE,
            interpretation="MELD-Na 15-24 - Moderate priority",
            recommendations=[
                "Active transplant listing appropriate",
                "Monitor every 1-2 months",
                "Manage complications aggressively",
            ],
        ),
        ThresholdInterpretation(
            min_score=25, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="MELD-Na ≥25 - High priority for transplant",
            recommendations=[
                "Urgent transplant prioritization",
                "Weekly lab monitoring",
                "ICU care if decompensated",
            ],
        ),
    ],
)


# ============================================================================
# BMI CALCULATOR
# ============================================================================
BMI_DEFINITION = CalculatorDefinition(
    id="bmi",
    name="Body Mass Index (BMI)",
    short_name="BMI",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="kg/m²",
    description="Body mass index calculation and classification",
    references=["WHO Expert Consultation. Lancet 2004"],
    specialties=["Internal Medicine", "Family Medicine", "Endocrinology", "Nutrition"],
    formula=FormulaDefinition(
        formula_text="weight / height²",
        output_unit="kg/m²",
        precision=1,
        parameters=[
            FormulaParameter(
                name="weight",
                display_name="Weight",
                unit="kg",
                min_value=1,
                max_value=None,
                description="Body weight in kilograms",
            ),
            FormulaParameter(
                name="height",
                display_name="Height",
                unit="m",
                min_value=0.5,
                max_value=2.5,
                description="Height in meters",
            ),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=18.5,
            risk_level=RiskLevel.MODERATE,
            interpretation="Underweight (BMI <18.5)",
            recommendations=[
                "Evaluate for underlying conditions",
                "Nutrition assessment",
                "Consider dietitian referral",
            ],
        ),
        ThresholdInterpretation(
            min_score=18.5, max_score=25,
            risk_level=RiskLevel.LOW,
            interpretation="Normal weight (BMI 18.5-24.9)",
            recommendations=[
                "Maintain healthy lifestyle",
                "Regular exercise and balanced diet",
            ],
        ),
        ThresholdInterpretation(
            min_score=25, max_score=30,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Overweight (BMI 25-29.9)",
            recommendations=[
                "Lifestyle modifications recommended",
                "Diet and exercise counseling",
                "Screen for metabolic syndrome",
            ],
        ),
        ThresholdInterpretation(
            min_score=30, max_score=35,
            risk_level=RiskLevel.MODERATE,
            interpretation="Obesity Class I (BMI 30-34.9)",
            recommendations=[
                "Comprehensive weight management program",
                "Screen for comorbidities",
                "Consider pharmacotherapy",
            ],
        ),
        ThresholdInterpretation(
            min_score=35, max_score=40,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="Obesity Class II (BMI 35-39.9)",
            recommendations=[
                "Intensive lifestyle intervention",
                "Pharmacotherapy consideration",
                "Bariatric surgery evaluation if comorbidities",
            ],
        ),
        ThresholdInterpretation(
            min_score=40, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Obesity Class III (BMI ≥40)",
            recommendations=[
                "Bariatric surgery evaluation",
                "Aggressive comorbidity management",
                "Multidisciplinary care team",
            ],
        ),
    ],
)


# ============================================================================
# SOFA SCORE - Sequential Organ Failure Assessment
# ============================================================================
SOFA_DEFINITION = CalculatorDefinition(
    id="sofa",
    name="Sequential Organ Failure Assessment (SOFA)",
    short_name="SOFA",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Organ dysfunction assessment in critically ill patients",
    references=["Vincent JL, et al. Intensive Care Med 1996", "Singer M, et al. JAMA 2016 (Sepsis-3)"],
    specialties=["Critical Care", "Emergency Medicine", "Internal Medicine"],
    notes=[
        "Score each organ system 0-4 based on worst value in 24h",
        "Total range: 0-24",
        "Sepsis = suspected infection + SOFA ≥2 from baseline",
    ],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="respiration",
            display_name="Respiration (PaO2/FiO2)",
            levels=[
                ("gte_400", 0, "PaO2/FiO2 ≥400 (0)"),
                ("300_399", 1, "PaO2/FiO2 300-399 (1)"),
                ("200_299", 2, "PaO2/FiO2 200-299 (2)"),
                ("100_199_vent", 3, "PaO2/FiO2 100-199 + ventilation (3)"),
                ("lt_100_vent", 4, "PaO2/FiO2 <100 + ventilation (4)"),
            ],
            description="Respiratory function",
        ),
        MultiLevelCriterion(
            name="coagulation",
            display_name="Coagulation (Platelets)",
            levels=[
                ("gte_150", 0, "Platelets ≥150 (0)"),
                ("100_149", 1, "Platelets 100-149 (1)"),
                ("50_99", 2, "Platelets 50-99 (2)"),
                ("20_49", 3, "Platelets 20-49 (3)"),
                ("lt_20", 4, "Platelets <20 (4)"),
            ],
            description="Platelet count (×10³/µL)",
        ),
        MultiLevelCriterion(
            name="liver",
            display_name="Liver (Bilirubin)",
            levels=[
                ("lt_1_2", 0, "Bilirubin <1.2 (0)"),
                ("1_2_1_9", 1, "Bilirubin 1.2-1.9 (1)"),
                ("2_5_9", 2, "Bilirubin 2.0-5.9 (2)"),
                ("6_11_9", 3, "Bilirubin 6.0-11.9 (3)"),
                ("gte_12", 4, "Bilirubin ≥12 (4)"),
            ],
            description="Total bilirubin (mg/dL)",
        ),
        MultiLevelCriterion(
            name="cardiovascular",
            display_name="Cardiovascular",
            levels=[
                ("map_gte_70", 0, "MAP ≥70 (0)"),
                ("map_lt_70", 1, "MAP <70 (1)"),
                ("dopa_low", 2, "Dopamine ≤5 or dobutamine any (2)"),
                ("dopa_mid", 3, "Dopamine >5 or epi/norepi ≤0.1 (3)"),
                ("dopa_high", 4, "Dopamine >15 or epi/norepi >0.1 (4)"),
            ],
            description="Blood pressure and vasopressors",
        ),
        MultiLevelCriterion(
            name="cns",
            display_name="CNS (Glasgow Coma Scale)",
            levels=[
                ("gcs_15", 0, "GCS 15 (0)"),
                ("gcs_13_14", 1, "GCS 13-14 (1)"),
                ("gcs_10_12", 2, "GCS 10-12 (2)"),
                ("gcs_6_9", 3, "GCS 6-9 (3)"),
                ("gcs_lt_6", 4, "GCS <6 (4)"),
            ],
            description="Glasgow Coma Scale",
        ),
        MultiLevelCriterion(
            name="renal",
            display_name="Renal (Creatinine or UOP)",
            levels=[
                ("cr_lt_1_2", 0, "Creatinine <1.2 (0)"),
                ("cr_1_2_1_9", 1, "Creatinine 1.2-1.9 (1)"),
                ("cr_2_3_4", 2, "Creatinine 2.0-3.4 (2)"),
                ("cr_3_5_4_9", 3, "Creatinine 3.5-4.9 or UOP <500 (3)"),
                ("cr_gte_5", 4, "Creatinine ≥5.0 or UOP <200 (4)"),
            ],
            description="Creatinine (mg/dL) or urine output",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=6,
            risk_level=RiskLevel.LOW,
            interpretation="SOFA 0-6 - Low mortality risk (~10%)",
            recommendations=[
                "Standard ICU monitoring",
                "Treat underlying condition",
                "Reassess daily",
            ],
        ),
        ThresholdInterpretation(
            min_score=6, max_score=10,
            risk_level=RiskLevel.MODERATE,
            interpretation="SOFA 6-9 - Moderate mortality risk (~20-30%)",
            recommendations=[
                "Aggressive organ support",
                "Source control if infection",
                "Consider early goals of care discussion",
            ],
        ),
        ThresholdInterpretation(
            min_score=10, max_score=15,
            risk_level=RiskLevel.HIGH,
            interpretation="SOFA 10-14 - High mortality risk (~50%)",
            recommendations=[
                "Maximum organ support",
                "Goals of care discussion",
                "Family meeting recommended",
            ],
        ),
        ThresholdInterpretation(
            min_score=15, max_score=None,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="SOFA ≥15 - Very high mortality risk (>80%)",
            recommendations=[
                "Reassess goals of care",
                "Palliative care consultation",
                "Family meeting urgently needed",
            ],
        ),
    ],
)


# ============================================================================
# OTTAWA ANKLE RULES
# ============================================================================
OTTAWA_ANKLE_DEFINITION = CalculatorDefinition(
    id="ottawa_ankle",
    name="Ottawa Ankle Rules",
    short_name="Ottawa Ankle",
    calc_type=CalculatorType.DECISION_TREE,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.CATEGORY,
    score_unit="",
    description="Clinical decision rule to exclude ankle/midfoot fractures without X-ray",
    references=["Stiell IG, et al. JAMA 1993", "Stiell IG, et al. Ann Emerg Med 1995"],
    specialties=["Emergency Medicine", "Family Medicine", "Sports Medicine"],
    notes=[
        "Sensitivity ~98-100% for clinically significant fractures",
        "X-ray needed if ANY criteria present",
        "Not validated for age <18",
    ],
    criteria=[
        # Ankle series criteria
        ScoringCriterion("bone_tenderness_lat_malleolus", "Bone tenderness at posterior edge or tip of lateral malleolus", 1, ""),
        ScoringCriterion("bone_tenderness_med_malleolus", "Bone tenderness at posterior edge or tip of medial malleolus", 1, ""),
        ScoringCriterion("unable_bear_weight", "Unable to bear weight immediately and in ED (4 steps)", 1, ""),
        # Foot series criteria
        ScoringCriterion("bone_tenderness_navicular", "Bone tenderness at navicular", 1, ""),
        ScoringCriterion("bone_tenderness_base_5th_mt", "Bone tenderness at base of 5th metatarsal", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Ottawa negative - X-ray not required",
            recommendations=[
                "Very low probability of fracture",
                "Supportive care: RICE (rest, ice, compression, elevation)",
                "NSAIDs for pain",
                "Follow up if not improving in 5-7 days",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="Ottawa positive - X-ray indicated",
            recommendations=[
                "Obtain ankle X-ray series (if ankle criteria met)",
                "Obtain foot X-ray series (if foot criteria met)",
                "Immobilize pending results",
            ],
        ),
    ],
)


# ============================================================================
# CIWA-Ar (Alcohol Withdrawal)
# ============================================================================
CIWA_AR_DEFINITION = CalculatorDefinition(
    id="ciwa_ar",
    name="CIWA-Ar (Alcohol Withdrawal)",
    short_name="CIWA-Ar",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Clinical Institute Withdrawal Assessment for Alcohol - monitors withdrawal severity",
    references=["Sullivan JT, et al. Br J Addict 1989"],
    specialties=["Emergency Medicine", "Psychiatry", "Internal Medicine", "Addiction Medicine"],
    notes=[
        "Assess every 1-4 hours based on score",
        "Score range: 0-67",
        "Used to guide benzodiazepine dosing",
    ],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="nausea_vomiting",
            display_name="Nausea/Vomiting",
            levels=[
                ("none", 0, "None (0)"),
                ("mild", 1, "Mild nausea, no vomiting (1)"),
                ("intermittent", 4, "Intermittent nausea (4)"),
                ("constant_retching", 7, "Constant nausea, retching (7)"),
            ],
            description="Nausea and vomiting",
        ),
        MultiLevelCriterion(
            name="tremor",
            display_name="Tremor",
            levels=[
                ("none", 0, "No tremor (0)"),
                ("not_visible", 1, "Not visible, can be felt (1)"),
                ("moderate", 4, "Moderate, with arms extended (4)"),
                ("severe", 7, "Severe, even with arms at rest (7)"),
            ],
            description="Tremor severity",
        ),
        MultiLevelCriterion(
            name="paroxysmal_sweats",
            display_name="Sweating",
            levels=[
                ("none", 0, "No sweat visible (0)"),
                ("barely", 1, "Barely perceptible, palms moist (1)"),
                ("beads", 4, "Beads of sweat on forehead (4)"),
                ("drenching", 7, "Drenching sweats (7)"),
            ],
            description="Paroxysmal sweats",
        ),
        MultiLevelCriterion(
            name="anxiety",
            display_name="Anxiety",
            levels=[
                ("none", 0, "No anxiety, at ease (0)"),
                ("mildly", 1, "Mildly anxious (1)"),
                ("moderately", 4, "Moderately anxious/guarded (4)"),
                ("equivalent_panic", 7, "Equivalent to acute panic state (7)"),
            ],
            description="Anxiety level",
        ),
        MultiLevelCriterion(
            name="agitation",
            display_name="Agitation",
            levels=[
                ("none", 0, "Normal activity (0)"),
                ("somewhat", 1, "Somewhat more than normal (1)"),
                ("moderately", 4, "Moderately restless (4)"),
                ("paces_thrashing", 7, "Paces or thrashes about (7)"),
            ],
            description="Agitation",
        ),
        MultiLevelCriterion(
            name="tactile_disturbances",
            display_name="Tactile Disturbances",
            levels=[
                ("none", 0, "None (0)"),
                ("mild", 1, "Mild itching, pins/needles, burning (1)"),
                ("moderate", 2, "Moderate (2)"),
                ("moderately_severe", 3, "Moderately severe (3)"),
                ("hallucinations", 4, "Continuous hallucinations (4)"),
            ],
            description="Tactile disturbances",
        ),
        MultiLevelCriterion(
            name="auditory_disturbances",
            display_name="Auditory Disturbances",
            levels=[
                ("none", 0, "Not present (0)"),
                ("mild", 1, "Mild sensitivity (1)"),
                ("moderate", 2, "Moderate (2)"),
                ("moderately_severe", 3, "Moderately severe (3)"),
                ("hallucinations", 4, "Continuous hallucinations (4)"),
            ],
            description="Auditory disturbances",
        ),
        MultiLevelCriterion(
            name="visual_disturbances",
            display_name="Visual Disturbances",
            levels=[
                ("none", 0, "Not present (0)"),
                ("mild", 1, "Mild sensitivity (1)"),
                ("moderate", 2, "Moderate (2)"),
                ("moderately_severe", 3, "Moderately severe (3)"),
                ("hallucinations", 4, "Continuous hallucinations (4)"),
            ],
            description="Visual disturbances",
        ),
        MultiLevelCriterion(
            name="headache",
            display_name="Headache/Fullness",
            levels=[
                ("none", 0, "Not present (0)"),
                ("mild", 1, "Very mild (1)"),
                ("mild_moderate", 2, "Mild (2)"),
                ("moderate", 3, "Moderate (3)"),
                ("moderately_severe", 4, "Moderately severe (4)"),
                ("severe", 5, "Severe (5)"),
                ("very_severe", 6, "Very severe (6)"),
                ("extremely_severe", 7, "Extremely severe (7)"),
            ],
            description="Headache, fullness in head",
        ),
        MultiLevelCriterion(
            name="orientation",
            display_name="Orientation/Clouding",
            levels=[
                ("oriented", 0, "Oriented, can do serial additions (0)"),
                ("uncertain", 1, "Cannot do serial additions or uncertain about date (1)"),
                ("disoriented_date", 2, "Disoriented to date by <2 days (2)"),
                ("disoriented_date_more", 3, "Disoriented to date by >2 days (3)"),
                ("disoriented_place", 4, "Disoriented to place/person (4)"),
            ],
            description="Orientation and sensorium",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=9,
            risk_level=RiskLevel.LOW,
            interpretation="Minimal withdrawal - Supportive care",
            recommendations=[
                "Reassess every 4 hours",
                "Supportive care: hydration, nutrition, thiamine",
                "May not require pharmacologic treatment",
            ],
        ),
        ThresholdInterpretation(
            min_score=9, max_score=16,
            risk_level=RiskLevel.MODERATE,
            interpretation="Mild-moderate withdrawal",
            recommendations=[
                "Reassess every 2-4 hours",
                "Consider symptom-triggered benzodiazepines",
                "Typical dose: chlordiazepoxide 25-50mg or lorazepam 1-2mg",
            ],
        ),
        ThresholdInterpretation(
            min_score=16, max_score=25,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="Moderate-severe withdrawal",
            recommendations=[
                "Reassess every 1-2 hours",
                "Benzodiazepines indicated",
                "Higher doses needed: chlordiazepoxide 50-100mg or lorazepam 2-4mg",
                "Monitor for seizure activity",
            ],
        ),
        ThresholdInterpretation(
            min_score=25, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Severe withdrawal - High risk of complications",
            recommendations=[
                "Continuous monitoring",
                "Aggressive benzodiazepine dosing",
                "Consider ICU admission",
                "Watch for delirium tremens",
                "May need IV diazepam or phenobarbital",
            ],
        ),
    ],
)


# ============================================================================
# FRAMINGHAM RISK SCORE (Simplified 10-year CVD)
# ============================================================================
FRAMINGHAM_CVD_DEFINITION = CalculatorDefinition(
    id="framingham_cvd",
    name="Framingham 10-Year CVD Risk",
    short_name="Framingham",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.PERCENTAGE,
    score_unit="%",
    description="10-year risk of cardiovascular disease",
    references=["D'Agostino RB, et al. Circulation 2008"],
    specialties=["Cardiology", "Internal Medicine", "Family Medicine"],
    notes=[
        "Sex-specific calculations",
        "Risk factors: age, total cholesterol, HDL, SBP, smoking, diabetes",
        "Note: This is a simplified point-based approximation",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[
                ("range", (30, 34), 0, "Age 30-34"),
                ("range", (35, 39), 2, "Age 35-39"),
                ("range", (40, 44), 5, "Age 40-44"),
                ("range", (45, 49), 6, "Age 45-49"),
                ("range", (50, 54), 8, "Age 50-54"),
                ("range", (55, 59), 10, "Age 55-59"),
                ("range", (60, 64), 11, "Age 60-64"),
                ("range", (65, 69), 12, "Age 65-69"),
                ("range", (70, 74), 14, "Age 70-74"),
                ("gte", 75, 15, "Age ≥75"),
            ],
            description="Age in years",
        ),
        ThresholdCriterion(
            name="total_cholesterol",
            display_name="Total Cholesterol",
            thresholds=[
                ("lt", 160, 0, "TC <160"),
                ("range", (160, 199), 1, "TC 160-199"),
                ("range", (200, 239), 2, "TC 200-239"),
                ("range", (240, 279), 3, "TC 240-279"),
                ("gte", 280, 4, "TC ≥280"),
            ],
            unit="mg/dL",
            description="Total cholesterol",
        ),
        ThresholdCriterion(
            name="hdl",
            display_name="HDL Cholesterol",
            thresholds=[
                ("gte", 60, -2, "HDL ≥60"),
                ("range", (50, 59), -1, "HDL 50-59"),
                ("range", (45, 49), 0, "HDL 45-49"),
                ("range", (35, 44), 1, "HDL 35-44"),
                ("lt", 35, 2, "HDL <35"),
            ],
            unit="mg/dL",
            description="HDL cholesterol",
        ),
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[
                ("lt", 120, 0, "SBP <120"),
                ("range", (120, 129), 1, "SBP 120-129"),
                ("range", (130, 139), 2, "SBP 130-139"),
                ("range", (140, 159), 3, "SBP 140-159"),
                ("gte", 160, 4, "SBP ≥160"),
            ],
            unit="mmHg",
            description="Systolic blood pressure (add points if untreated)",
        ),
    ],
    criteria=[
        ScoringCriterion("current_smoker", "Current smoker", 4, "Current tobacco use"),
        ScoringCriterion("diabetes", "Diabetes", 3, "Diabetes mellitus"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=10,
            risk_level=RiskLevel.LOW,
            interpretation="Low 10-year CVD risk (<10%)",
            recommendations=[
                "Lifestyle modifications",
                "Reassess risk factors every 4-6 years",
                "Diet and exercise counseling",
            ],
        ),
        ThresholdInterpretation(
            min_score=10, max_score=20,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate 10-year CVD risk (10-20%)",
            recommendations=[
                "Aggressive lifestyle modifications",
                "Consider statin therapy based on LDL",
                "Blood pressure management",
                "Reassess annually",
            ],
        ),
        ThresholdInterpretation(
            min_score=20, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High 10-year CVD risk (≥20%)",
            recommendations=[
                "Statin therapy indicated",
                "Aggressive BP control (<130/80)",
                "Aspirin consideration if benefit > bleed risk",
                "Consider cardiology referral",
            ],
        ),
    ],
)


# ============================================================================
# CHILD-PUGH SCORE - Cirrhosis Severity
# ============================================================================
CHILD_PUGH_DEFINITION = CalculatorDefinition(
    id="child_pugh",
    name="Child-Pugh Score",
    short_name="Child-Pugh",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Assesses severity of cirrhosis and predicts survival",
    references=["Pugh RN, et al. Br J Surg 1973", "Child CG, Turcotte JG. Surgery 1964"],
    specialties=["Hepatology", "Gastroenterology", "Surgery"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="encephalopathy",
            display_name="Hepatic Encephalopathy",
            levels=[
                ("none", 1, "None (1)"),
                ("grade_1_2", 2, "Grade I-II (2)"),
                ("grade_3_4", 3, "Grade III-IV (3)"),
            ],
            description="Hepatic encephalopathy grade",
        ),
        MultiLevelCriterion(
            name="ascites",
            display_name="Ascites",
            levels=[
                ("none", 1, "Absent (1)"),
                ("slight", 2, "Mild/diuretic-responsive (2)"),
                ("moderate", 3, "Moderate-severe/refractory (3)"),
            ],
            description="Ascites severity",
        ),
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="bilirubin",
            display_name="Bilirubin",
            thresholds=[
                ("lt", 2, 1, "Bilirubin <2"),
                ("range", (2, 3), 2, "Bilirubin 2-3"),
                ("gt", 3, 3, "Bilirubin >3"),
            ],
            unit="mg/dL",
            description="Total serum bilirubin",
        ),
        ThresholdCriterion(
            name="albumin",
            display_name="Albumin",
            thresholds=[
                ("gt", 3.5, 1, "Albumin >3.5"),
                ("range", (2.8, 3.5), 2, "Albumin 2.8-3.5"),
                ("lt", 2.8, 3, "Albumin <2.8"),
            ],
            unit="g/dL",
            description="Serum albumin",
        ),
        ThresholdCriterion(
            name="inr",
            display_name="INR",
            thresholds=[
                ("lt", 1.7, 1, "INR <1.7"),
                ("range", (1.7, 2.3), 2, "INR 1.7-2.3"),
                ("gt", 2.3, 3, "INR >2.3"),
            ],
            unit="",
            description="INR",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=5, max_score=7,
            risk_level=RiskLevel.LOW,
            interpretation="Child-Pugh Class A - Well-compensated",
            recommendations=[
                "1-year survival ~100%, 2-year ~85%",
                "Low perioperative mortality (~10%)",
                "Continue monitoring",
            ],
        ),
        ThresholdInterpretation(
            min_score=7, max_score=10,
            risk_level=RiskLevel.MODERATE,
            interpretation="Child-Pugh Class B - Significant compromise",
            recommendations=[
                "1-year survival ~80%, 2-year ~60%",
                "Moderate perioperative mortality (~30%)",
                "Consider transplant evaluation",
            ],
        ),
        ThresholdInterpretation(
            min_score=10, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Child-Pugh Class C - Decompensated",
            recommendations=[
                "1-year survival ~45%, 2-year ~35%",
                "High perioperative mortality (~80%)",
                "Urgent transplant evaluation",
            ],
        ),
    ],
)


# ============================================================================
# ABCD2 SCORE - TIA Stroke Risk
# ============================================================================
ABCD2_DEFINITION = CalculatorDefinition(
    id="abcd2",
    name="ABCD² Score for TIA",
    short_name="ABCD²",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts 2-day stroke risk after TIA",
    references=["Johnston SC, et al. Lancet 2007"],
    specialties=["Neurology", "Emergency Medicine", "Internal Medicine"],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[("gte", 60, 1, "Age ≥60")],
            description="Age ≥60 years",
        ),
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Blood Pressure",
            thresholds=[("gte", 140, 1, "SBP ≥140 or DBP ≥90")],
            unit="mmHg",
            description="BP ≥140/90 at presentation",
        ),
        ThresholdCriterion(
            name="duration",
            display_name="Duration",
            thresholds=[
                ("gte", 60, 2, "≥60 minutes"),
                ("range", (10, 60), 1, "10-59 minutes"),
            ],
            unit="minutes",
            description="TIA duration",
        ),
    ],
    criteria=[
        ScoringCriterion("unilateral_weakness", "Unilateral weakness", 2, ""),
        ScoringCriterion("speech_impairment", "Speech impairment (no weakness)", 1, ""),
        ScoringCriterion("diabetes", "Diabetes", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=4,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - 2-day stroke risk ~1%",
            recommendations=["Urgent outpatient workup within 48-72h", "Start aspirin"],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=6,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate risk - 2-day stroke risk ~4%",
            recommendations=["Consider admission", "Rapid neurology consult"],
        ),
        ThresholdInterpretation(
            min_score=6, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk - 2-day stroke risk ~8%",
            recommendations=["Hospital admission", "Emergent workup"],
        ),
    ],
)


# ============================================================================
# PHQ-9 - Depression Screening
# ============================================================================
PHQ9_DEFINITION = CalculatorDefinition(
    id="phq9",
    name="Patient Health Questionnaire-9",
    short_name="PHQ-9",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Depression screening and severity",
    references=["Kroenke K, et al. J Gen Intern Med 2001"],
    specialties=["Psychiatry", "Family Medicine", "Internal Medicine"],
    notes=["Each item 0-3 over past 2 weeks", "Item 9 (suicidality) requires assessment"],
    multi_level_criteria=[
        MultiLevelCriterion(name="interest", display_name="1. Little interest",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Little interest or pleasure"),
        MultiLevelCriterion(name="depressed", display_name="2. Feeling down",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Feeling down, depressed, hopeless"),
        MultiLevelCriterion(name="sleep", display_name="3. Sleep problems",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Sleep problems"),
        MultiLevelCriterion(name="energy", display_name="4. Little energy",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Tired or little energy"),
        MultiLevelCriterion(name="appetite", display_name="5. Appetite",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Poor appetite or overeating"),
        MultiLevelCriterion(name="self_esteem", display_name="6. Self-esteem",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Feeling bad about yourself"),
        MultiLevelCriterion(name="concentration", display_name="7. Concentration",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Trouble concentrating"),
        MultiLevelCriterion(name="psychomotor", display_name="8. Psychomotor",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Moving/speaking slowly or restless"),
        MultiLevelCriterion(name="suicidality", display_name="9. Self-harm thoughts",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Thoughts of self-harm"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="Minimal depression", recommendations=["Supportive care", "Re-screen PRN"]),
        ThresholdInterpretation(min_score=5, max_score=10, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mild depression", recommendations=["Watchful waiting", "Consider therapy"]),
        ThresholdInterpretation(min_score=10, max_score=15, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate depression", recommendations=["Treatment plan needed", "Therapy/meds"]),
        ThresholdInterpretation(min_score=15, max_score=20, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="Moderately severe depression", recommendations=["Active treatment", "Safety planning"]),
        ThresholdInterpretation(min_score=20, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Severe depression", recommendations=["Immediate treatment", "Psychiatry referral"]),
    ],
)


# ============================================================================
# GAD-7 - Anxiety Screening
# ============================================================================
GAD7_DEFINITION = CalculatorDefinition(
    id="gad7",
    name="Generalized Anxiety Disorder 7-item",
    short_name="GAD-7",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Anxiety screening and severity",
    references=["Spitzer RL, et al. Arch Intern Med 2006"],
    specialties=["Psychiatry", "Family Medicine", "Internal Medicine"],
    multi_level_criteria=[
        MultiLevelCriterion(name="nervous", display_name="1. Nervous/anxious",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Feeling nervous, anxious, on edge"),
        MultiLevelCriterion(name="worry_control", display_name="2. Can't stop worrying",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Not being able to stop worrying"),
        MultiLevelCriterion(name="excessive_worry", display_name="3. Worrying too much",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Worrying too much about different things"),
        MultiLevelCriterion(name="relaxing", display_name="4. Trouble relaxing",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Trouble relaxing"),
        MultiLevelCriterion(name="restless", display_name="5. Restless",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Being so restless it's hard to sit still"),
        MultiLevelCriterion(name="irritable", display_name="6. Easily annoyed",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Becoming easily annoyed or irritable"),
        MultiLevelCriterion(name="afraid", display_name="7. Feeling afraid",
            levels=[("not_at_all", 0, "0"), ("several_days", 1, "1"), ("more_than_half", 2, "2"), ("nearly_every_day", 3, "3")],
            description="Feeling afraid as if something awful might happen"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="Minimal anxiety", recommendations=["Monitor symptoms"]),
        ThresholdInterpretation(min_score=5, max_score=10, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mild anxiety", recommendations=["Watchful waiting", "Self-management"]),
        ThresholdInterpretation(min_score=10, max_score=15, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate anxiety", recommendations=["CBT recommended", "Consider meds"]),
        ThresholdInterpretation(min_score=15, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Severe anxiety", recommendations=["Pharmacotherapy", "Psychiatry referral"]),
    ],
)


# ============================================================================
# CORRECTED CALCIUM
# ============================================================================
CORRECTED_CALCIUM_DEFINITION = CalculatorDefinition(
    id="corrected_calcium",
    name="Corrected Calcium",
    short_name="Corrected Ca",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mg/dL",
    description="Adjusts calcium for albumin levels",
    references=["Payne RB, et al. Br Med J 1973"],
    specialties=["Internal Medicine", "Nephrology", "Endocrinology"],
    formula=FormulaDefinition(
        formula_text="Ca + 0.8 × (4.0 - Albumin)",
        output_unit="mg/dL",
        precision=1,
        parameters=[
            FormulaParameter(name="calcium", display_name="Measured Ca", unit="mg/dL", min_value=4.0, max_value=16.0),
            FormulaParameter(name="albumin", display_name="Albumin", unit="g/dL", min_value=1.0, max_value=5.5),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=8.5, risk_level=RiskLevel.MODERATE,
            interpretation="Hypocalcemia", recommendations=["Evaluate cause", "Check ionized Ca"]),
        ThresholdInterpretation(min_score=8.5, max_score=10.5, risk_level=RiskLevel.LOW,
            interpretation="Normal", recommendations=["No intervention needed"]),
        ThresholdInterpretation(min_score=10.5, max_score=12.0, risk_level=RiskLevel.MODERATE,
            interpretation="Mild hypercalcemia", recommendations=["Check PTH", "Hydration"]),
        ThresholdInterpretation(min_score=12.0, max_score=14.0, risk_level=RiskLevel.HIGH,
            interpretation="Moderate hypercalcemia", recommendations=["IV saline", "Bisphosphonates"]),
        ThresholdInterpretation(min_score=14.0, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe hypercalcemia - Emergency", recommendations=["Aggressive hydration", "Calcitonin"]),
    ],
)


# ============================================================================
# CORRECTED QT (QTc)
# ============================================================================
CORRECTED_QT_DEFINITION = CalculatorDefinition(
    id="corrected_qt",
    name="Corrected QT Interval (QTc)",
    short_name="QTc",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="ms",
    description="Heart rate-corrected QT interval (Bazett)",
    references=["Bazett HC. Heart 1920"],
    specialties=["Cardiology", "Emergency Medicine", "Critical Care"],
    formula=FormulaDefinition(
        formula_text="QT / √(60/HR)",
        output_unit="ms",
        precision=0,
        parameters=[
            FormulaParameter(name="qt_interval", display_name="QT Interval", unit="ms", min_value=200, max_value=700),
            FormulaParameter(name="heart_rate", display_name="Heart Rate", unit="bpm", min_value=40, max_value=200),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=440, risk_level=RiskLevel.LOW,
            interpretation="Normal QTc", recommendations=["No intervention"]),
        ThresholdInterpretation(min_score=440, max_score=460, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Borderline prolonged", recommendations=["Review QT-prolonging meds"]),
        ThresholdInterpretation(min_score=460, max_score=500, risk_level=RiskLevel.MODERATE,
            interpretation="Prolonged QTc", recommendations=["D/C QT meds if possible", "Correct lytes"]),
        ThresholdInterpretation(min_score=500, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Markedly prolonged - Torsades risk", recommendations=["D/C QT meds", "K >4, Mg >2", "Monitoring"]),
    ],
)


# ============================================================================
# ANION GAP
# ============================================================================
ANION_GAP_DEFINITION = CalculatorDefinition(
    id="anion_gap",
    name="Anion Gap",
    short_name="AG",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.INTEGER,
    score_unit="mEq/L",
    description="Serum anion gap for acidosis classification",
    references=["Kraut JA, Madias NE. N Engl J Med 2007"],
    specialties=["Critical Care", "Nephrology", "Emergency Medicine"],
    formula=FormulaDefinition(
        formula_text="Na - (Cl + HCO3)",
        output_unit="mEq/L",
        precision=0,
        parameters=[
            FormulaParameter(name="sodium", display_name="Sodium", unit="mEq/L", min_value=100, max_value=180),
            FormulaParameter(name="chloride", display_name="Chloride", unit="mEq/L", min_value=70, max_value=130),
            FormulaParameter(name="bicarbonate", display_name="HCO3", unit="mEq/L", min_value=5, max_value=45),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=8, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low AG", recommendations=["Evaluate: hypoalbuminemia, myeloma"]),
        ThresholdInterpretation(min_score=8, max_score=12, risk_level=RiskLevel.LOW,
            interpretation="Normal AG", recommendations=["If acidosis: non-AG (diarrhea, RTA)"]),
        ThresholdInterpretation(min_score=12, max_score=20, risk_level=RiskLevel.MODERATE,
            interpretation="Elevated AG", recommendations=["Check lactate, ketones, uremia, toxins"]),
        ThresholdInterpretation(min_score=20, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High AG - Significant acidosis", recommendations=["MUDPILES workup", "Treat cause"]),
    ],
)


# Registry of all calculator definitions
CALCULATOR_DEFINITIONS: dict[str, CalculatorDefinition] = {
    "chadsvasc": CHADSVASC_DEFINITION,
    "hasbled": HASBLED_DEFINITION,
    "wells_dvt": WELLS_DVT_DEFINITION,
    "curb65": CURB65_DEFINITION,
    "qsofa": QSOFA_DEFINITION,
    "heart_score": HEART_SCORE_DEFINITION,
    "sirs": SIRS_DEFINITION,
    "gcs": GCS_DEFINITION,
    "rcri": RCRI_DEFINITION,
    "perc": PERC_DEFINITION,
    "centor": CENTOR_DEFINITION,
    "apgar": APGAR_DEFINITION,
    # Pulmonary/VTE
    "wells_pe": WELLS_PE_DEFINITION,
    # Comorbidity
    "charlson": CHARLSON_DEFINITION,
    # Cardiac
    "timi_stemi": TIMI_STEMI_DEFINITION,
    "timi_nstemi": TIMI_NSTEMI_DEFINITION,
    "framingham_cvd": FRAMINGHAM_CVD_DEFINITION,
    "corrected_qt": CORRECTED_QT_DEFINITION,
    # Hepatic
    "meld": MELD_DEFINITION,
    "meld_na": MELD_NA_DEFINITION,
    "child_pugh": CHILD_PUGH_DEFINITION,
    # Metabolic
    "bmi": BMI_DEFINITION,
    "corrected_calcium": CORRECTED_CALCIUM_DEFINITION,
    "anion_gap": ANION_GAP_DEFINITION,
    # Critical Care
    "sofa": SOFA_DEFINITION,
    # Emergency
    "ottawa_ankle": OTTAWA_ANKLE_DEFINITION,
    "ciwa_ar": CIWA_AR_DEFINITION,
    # Neurological
    "abcd2": ABCD2_DEFINITION,
    # Psychiatry
    "phq9": PHQ9_DEFINITION,
    "gad7": GAD7_DEFINITION,
}


def get_calculator_definition(calculator_id: str) -> CalculatorDefinition | None:
    """Get a calculator definition by ID."""
    return CALCULATOR_DEFINITIONS.get(calculator_id)


def list_calculator_definitions() -> list[CalculatorDefinition]:
    """List all available calculator definitions."""
    return list(CALCULATOR_DEFINITIONS.values())
