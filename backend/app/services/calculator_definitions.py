"""Data-Driven Clinical Calculator Definitions.

This module provides data structures for defining clinical calculators
in a declarative, data-driven manner. The goal is to reduce code duplication
while maintaining safety and testability for medical calculations.

Two main patterns are supported:

1. Point-Based Scoring: Calculators that sum points for boolean criteria
   (CHA2DS2-VASc, HAS-BLED, Wells DVT, CURB-65, etc.)

2. Formula-Based: Calculators with mathematical formulas
   (BMI, eGFR, MELD, ASCVD, etc.) - formulas stay as Python code

The data-driven approach handles:
- Calculator metadata (name, category, references)
- Scoring criteria definitions
- Risk threshold interpretations
- Recommendations per risk level

This reduces repetitive boilerplate while keeping formulas safe.
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


class CalculatorCategory(str, Enum):
    """Calculator categories."""
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
    GENERAL = "general"


@dataclass
class ScoringCriterion:
    """A single scoring criterion for point-based calculators.

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
class AgeScoringRule:
    """Age-based scoring rule for calculators with age thresholds.

    Attributes:
        thresholds: List of (age_threshold, points) tuples, evaluated high to low
        display_format: Format string for component display (e.g., "Age ≥{threshold}")
    """
    thresholds: list[tuple[int, int]]  # [(threshold, points), ...]
    display_format: str = "Age ≥{threshold}"


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

    Attributes:
        id: Unique calculator identifier (e.g., "chadsvasc")
        name: Full display name (e.g., "CHA₂DS₂-VASc Score")
        short_name: Abbreviated name (e.g., "CHA2DS2-VASc")
        category: Calculator category
        score_unit: Unit for the score (e.g., "points", "kg/m²", "%")
        references: List of literature references
        description: Clinical description/indication
        criteria: List of scoring criteria (for point-based)
        age_scoring: Age-based scoring rule (optional)
        interpretations: List of threshold interpretations
        notes: Additional clinical notes
    """
    id: str
    name: str
    short_name: str
    category: CalculatorCategory
    score_unit: str
    references: list[str]
    description: str = ""
    criteria: list[ScoringCriterion] = field(default_factory=list)
    age_scoring: AgeScoringRule | None = None
    interpretations: list[ThresholdInterpretation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


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


def calculate_point_based_score(
    definition: CalculatorDefinition,
    values: dict[str, bool],
    age: int | None = None,
) -> CalculatorResult:
    """Calculate score for a point-based calculator using its definition.

    Args:
        definition: Calculator definition with criteria and interpretations
        values: Dict mapping criterion names to boolean values
        age: Patient age (for calculators with age-based scoring)

    Returns:
        CalculatorResult with score and interpretation
    """
    score = 0
    components: dict[str, int] = {}

    # Sum points from boolean criteria
    for criterion in definition.criteria:
        if values.get(criterion.name, False):
            score += criterion.points
            components[criterion.display_name] = criterion.points

    # Apply age-based scoring if applicable
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
CALCULATOR_DEFINITIONS: dict[str, CalculatorDefinition] = {
    "chadsvasc": CHADSVASC_DEFINITION,
    "hasbled": HASBLED_DEFINITION,
    "wells_dvt": WELLS_DVT_DEFINITION,
    "curb65": CURB65_DEFINITION,
    "qsofa": QSOFA_DEFINITION,
}


def get_calculator_definition(calculator_id: str) -> CalculatorDefinition | None:
    """Get a calculator definition by ID."""
    return CALCULATOR_DEFINITIONS.get(calculator_id)


def list_calculator_definitions() -> list[CalculatorDefinition]:
    """List all available calculator definitions."""
    return list(CALCULATOR_DEFINITIONS.values())
