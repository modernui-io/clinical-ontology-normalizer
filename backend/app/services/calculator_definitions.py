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
}


def get_calculator_definition(calculator_id: str) -> CalculatorDefinition | None:
    """Get a calculator definition by ID."""
    return CALCULATOR_DEFINITIONS.get(calculator_id)


def list_calculator_definitions() -> list[CalculatorDefinition]:
    """List all available calculator definitions."""
    return list(CALCULATOR_DEFINITIONS.values())
