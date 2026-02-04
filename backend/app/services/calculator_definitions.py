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

from __future__ import annotations

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


# =============================================================================
# Provenance Data Structures (MDCalc-style evidence documentation)
# =============================================================================


class EvidenceLevel(str, Enum):
    """Evidence quality levels based on GRADE methodology."""
    HIGH = "high"  # Level A - RCTs, meta-analyses
    MODERATE = "moderate"  # Level B - Downgraded RCTs, upgraded observational
    LOW = "low"  # Level C - Observational studies
    VERY_LOW = "very_low"  # Level D - Case series, expert opinion
    EXPERT_CONSENSUS = "expert_consensus"  # Expert opinion without formal studies


class ValidationOutcome(str, Enum):
    """Outcome of validation studies."""
    STRONGLY_VALIDATED = "strongly_validated"  # AUC >0.8, multiple populations
    VALIDATED = "validated"  # AUC 0.7-0.8, external validation
    PARTIALLY_VALIDATED = "partially_validated"  # Single center or limited pop
    INTERNALLY_VALIDATED = "internally_validated"  # Only derivation cohort
    NOT_VALIDATED = "not_validated"  # No external validation


@dataclass
class StructuredCitation:
    """Structured citation for literature references.

    Enables PubMed/DOI linking and proper academic attribution.

    Attributes:
        title: Full title of the paper
        authors: List of author names
        journal: Journal name
        year: Publication year
        pmid: PubMed ID for linking
        doi: Digital Object Identifier
        is_original_derivation: True if this is the original derivation paper
    """
    title: str
    authors: list[str]
    journal: str
    year: int
    volume: str | None = None
    pages: str | None = None
    pmid: str | None = None
    doi: str | None = None
    is_original_derivation: bool = False

    @property
    def pubmed_url(self) -> str | None:
        """Generate PubMed URL if PMID is available."""
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/" if self.pmid else None


@dataclass
class ValidationStudy:
    """A validation study that tested the calculator."""
    citation: StructuredCitation
    population: str
    sample_size: int | None = None
    setting: str | None = None
    performance_auc: float | None = None
    validation_outcome: ValidationOutcome = ValidationOutcome.VALIDATED
    notes: str | None = None


@dataclass
class ClinicalPearl:
    """A clinical pearl or tip for using the calculator."""
    text: str
    category: str = "tip"  # interpretation, usage, limitation, tip, warning
    source: str | None = None


@dataclass
class UsageGuidance:
    """Guidance on when to use and when NOT to use the calculator."""
    when_to_use: list[str] = field(default_factory=list)
    when_not_to_use: list[str] = field(default_factory=list)
    target_population: str | None = None
    excluded_populations: list[str] = field(default_factory=list)


@dataclass
class GuidelineReference:
    """Reference to a clinical guideline that endorses this calculator."""
    guideline_name: str
    recommendation_class: str | None = None  # I, IIa, IIb, III
    evidence_level: str | None = None  # A, B, C
    year: int | None = None
    organization: str | None = None  # AHA, ACC, ESC, etc.


@dataclass
class CalculatorProvenance:
    """Enhanced provenance data for clinical calculators (MDCalc-style).

    All fields are optional to allow incremental population for 201 calculators.
    """
    # Core provenance
    original_citation: StructuredCitation | None = None
    evidence_level: EvidenceLevel | None = None
    evidence_summary: str | None = None

    # Validation evidence
    validation_studies: list[ValidationStudy] = field(default_factory=list)
    overall_validation: ValidationOutcome | None = None

    # Clinical guidance
    clinical_pearls: list[ClinicalPearl] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    usage_guidance: UsageGuidance | None = None

    # Guideline relationships
    related_guidelines: list[GuidelineReference] = field(default_factory=list)
    related_calculator_ids: list[str] = field(default_factory=list)

    # External links
    mdcalc_url: str | None = None


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
    provenance: CalculatorProvenance | None = None


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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Refining clinical risk stratification for predicting stroke and thromboembolism in atrial fibrillation using a novel risk factor-based approach: the Euro Heart Survey on atrial fibrillation",
            authors=["Lip GY", "Nieuwlaat R", "Pisters R", "Lane DA", "Crijns HJ"],
            journal="Chest",
            year=2010,
            volume="137",
            pages="263-272",
            pmid="19762550",
            doi="10.1378/chest.09-1584",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Derived from 1,084 patients in the Euro Heart Survey on AF and extensively validated in millions of patients worldwide. Superior discrimination compared to original CHADS2.",
        overall_validation=ValidationOutcome.STRONGLY_VALIDATED,
        validation_studies=[
            ValidationStudy(
                citation=StructuredCitation(
                    title="Validation of the CHA2DS2-VASc score for stroke risk in atrial fibrillation",
                    authors=["Olesen JB", "Lip GY", "Hansen ML", "et al."],
                    journal="Stroke",
                    year=2011,
                    volume="42",
                    pages="1686-1691",
                    pmid="21636813",
                ),
                population="Danish nationwide cohort",
                sample_size=73538,
                setting="National registry",
                performance_auc=0.88,
                validation_outcome=ValidationOutcome.STRONGLY_VALIDATED,
                notes="Validated in >73,000 patients; superior to CHADS2 at identifying truly low-risk patients",
            ),
        ],
        clinical_pearls=[
            ClinicalPearl(
                text="Female sex only adds a point if another risk factor is present - a woman with no other risk factors (CHA2DS2-VASc = 1) is still low risk",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Always pair with HAS-BLED for bleeding risk assessment when considering anticoagulation",
                category="usage",
            ),
            ClinicalPearl(
                text="DOACs (apixaban, rivaroxaban, dabigatran, edoxaban) are preferred over warfarin for most patients",
                category="tip",
            ),
            ClinicalPearl(
                text="A score of 0 in males (or 1 in females with no other risk factors) identifies truly low-risk patients who may not need anticoagulation",
                category="interpretation",
            ),
        ],
        pitfalls=[
            "Not validated for valvular AF (mitral stenosis, mechanical heart valves)",
            "Does not account for LAA morphology or flow velocities",
            "Risk factors are binary - doesn't account for severity (e.g., uncontrolled vs controlled HTN)",
            "Female sex alone (without other risk factors) should not drive anticoagulation decision",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Non-valvular atrial fibrillation/flutter",
                "Deciding whether to initiate anticoagulation",
                "Annual reassessment of stroke risk",
            ],
            when_not_to_use=[
                "Mechanical heart valves (use different risk assessment)",
                "Moderate-severe mitral stenosis (valvular AF)",
                "Post-cardiac surgery transient AF",
            ],
            target_population="Adults with non-valvular atrial fibrillation",
            excluded_populations=[
                "Patients with mechanical heart valves",
                "Moderate-severe rheumatic mitral stenosis",
                "Pediatric patients",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="2019 AHA/ACC/HRS Focused Update on Atrial Fibrillation",
                recommendation_class="I",
                evidence_level="B",
                year=2019,
                organization="AHA/ACC/HRS",
            ),
            GuidelineReference(
                guideline_name="2020 ESC Guidelines for AF Management",
                recommendation_class="I",
                evidence_level="A",
                year=2020,
                organization="ESC",
            ),
        ],
        related_calculator_ids=["hasbled", "orbit"],
        mdcalc_url="https://www.mdcalc.com/calc/801/cha2ds2-vasc-score-atrial-fibrillation-stroke-risk",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="A novel user-friendly score (HAS-BLED) to assess 1-year risk of major bleeding in patients with atrial fibrillation: the Euro Heart Survey",
            authors=["Pisters R", "Lane DA", "Nieuwlaat R", "de Vos CB", "Crijns HJ", "Lip GY"],
            journal="Chest",
            year=2010,
            volume="138",
            pages="1093-1100",
            pmid="20299623",
            doi="10.1378/chest.10-0134",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Derived from 3,978 patients in the Euro Heart Survey on AF. Well-validated and endorsed by ESC and AHA/ACC guidelines for bleeding risk assessment.",
        overall_validation=ValidationOutcome.STRONGLY_VALIDATED,
        clinical_pearls=[
            ClinicalPearl(
                text="High HAS-BLED score should NOT be used to withhold anticoagulation - it identifies modifiable risk factors",
                category="warning",
            ),
            ClinicalPearl(
                text="Always pair with CHA2DS2-VASc - the net clinical benefit usually favors anticoagulation even with high bleeding risk",
                category="usage",
            ),
            ClinicalPearl(
                text="'L' (Labile INR) is only applicable for patients on warfarin, not DOACs",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Several factors are modifiable: uncontrolled BP, labile INR, concomitant antiplatelets/NSAIDs, alcohol",
                category="tip",
            ),
        ],
        pitfalls=[
            "Score ≥3 does NOT contraindicate anticoagulation",
            "Designed for VKA users - 'Labile INR' not applicable to DOACs",
            "Does not predict intracranial hemorrhage specifically",
            "May overestimate bleeding risk in DOAC-treated patients",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "AF patients being considered for anticoagulation",
                "Identifying modifiable bleeding risk factors",
                "Discussing bleeding risk with patients",
            ],
            when_not_to_use=[
                "As sole reason to withhold anticoagulation",
                "Predicting intracranial hemorrhage specifically",
            ],
            target_population="Adults with atrial fibrillation on or considered for anticoagulation",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="2019 AHA/ACC/HRS Focused Update on Atrial Fibrillation",
                recommendation_class="IIa",
                evidence_level="B",
                year=2019,
                organization="AHA/ACC/HRS",
            ),
            GuidelineReference(
                guideline_name="2020 ESC Guidelines for AF Management",
                recommendation_class="IIa",
                evidence_level="B",
                year=2020,
                organization="ESC",
            ),
        ],
        related_calculator_ids=["chadsvasc", "orbit"],
        mdcalc_url="https://www.mdcalc.com/calc/807/has-bled-score-major-bleeding-risk",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Value of assessment of pretest probability of deep-vein thrombosis in clinical management",
            authors=["Wells PS", "Anderson DR", "Bormanis J", "et al."],
            journal="Lancet",
            year=1997,
            volume="350",
            pages="1795-1798",
            pmid="9428249",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        clinical_pearls=[
            ClinicalPearl(
                text="A negative D-dimer plus low Wells score (<2) has >99% NPV for excluding DVT",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Modified Wells uses 'DVT as likely or more likely' as +2 instead of -2 for alternative diagnosis",
                category="tip",
            ),
            ClinicalPearl(
                text="Sensitivity drops in recurrent DVT - consider imaging regardless of score in these patients",
                category="limitation",
            ),
        ],
        pitfalls=[
            "May miss upper extremity DVT (designed for lower extremity)",
            "Less accurate in hospitalized patients and post-surgical patients",
            "Requires clinical gestalt for 'alternative diagnosis' item",
            "Should be combined with D-dimer for optimal performance",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Suspected lower extremity DVT in ambulatory patients",
                "Deciding whether D-dimer testing is sufficient",
            ],
            when_not_to_use=[
                "Upper extremity DVT",
                "Post-operative patients <30 days",
                "Patients already anticoagulated",
            ],
            target_population="Ambulatory patients with suspected lower extremity DVT",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="2018 CHEST Guideline on Antithrombotic Therapy for VTE",
                year=2018,
                organization="CHEST",
            ),
        ],
        related_calculator_ids=["wells_pe", "perc"],
        mdcalc_url="https://www.mdcalc.com/calc/362/wells-criteria-dvt",
    ),
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
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low severity - outpatient treatment appropriate",
            recommendations=[
                "Consider outpatient treatment",
                "Oral antibiotics usually sufficient",
                "Close follow-up recommended",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate severity - consider hospitalization",
            recommendations=[
                "Short inpatient stay or supervised outpatient",
                "IV antibiotics may be beneficial",
                "Reassess within 24-48 hours",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=4,
            risk_level=RiskLevel.HIGH,
            interpretation="Severe pneumonia - hospitalization required",
            recommendations=[
                "Inpatient hospitalization recommended",
                "IV antibiotics indicated",
                "Consider ICU evaluation",
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Defining community acquired pneumonia severity on presentation to hospital: an international derivation and validation study",
            authors=["Lim WS", "van der Eerden MM", "Laing R", "et al."],
            journal="Thorax",
            year=2003,
            volume="58",
            pages="377-382",
            pmid="12728155",
            doi="10.1136/thorax.58.5.377",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Derived from 1,068 patients, validated internationally. BTS/NICE recommended. Simpler alternative to PSI with comparable performance.",
        clinical_pearls=[
            ClinicalPearl(
                text="Score 0-1: Consider outpatient treatment; Score 2: Consider hospital admission; Score >=3: Consider ICU admission",
                category="interpretation",
            ),
            ClinicalPearl(
                text="CRB-65 (without urea) can be used in community settings where labs aren't available",
                category="tip",
            ),
            ClinicalPearl(
                text="Does not account for social factors, adherence, or comorbidities in disposition decision",
                category="limitation",
            ),
            ClinicalPearl(
                text="Age 65 cutoff is somewhat arbitrary - use clinical judgment near threshold",
                category="warning",
            ),
        ],
        pitfalls=[
            "Does not capture all severity factors (hypoxia, multilobar disease)",
            "May underestimate severity in young patients with severe disease",
            "Social circumstances and ability to take oral medications not captured",
            "Should be combined with clinical judgment, not used in isolation",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Risk stratification of CAP on presentation",
                "Guiding disposition decisions",
            ],
            when_not_to_use=[
                "Healthcare-associated pneumonia",
                "Immunocompromised patients",
                "Aspiration pneumonia",
            ],
            target_population="Adults with community-acquired pneumonia",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="BTS Guidelines for CAP",
                year=2009,
                organization="BTS",
            ),
            GuidelineReference(
                guideline_name="IDSA/ATS CAP Guidelines",
                year=2019,
                organization="IDSA/ATS",
            ),
        ],
        related_calculator_ids=["psi_port"],
        mdcalc_url="https://www.mdcalc.com/calc/324/curb-65-score-pneumonia-severity",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Assessment of Clinical Criteria for Sepsis: For the Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3)",
            authors=["Seymour CW", "Liu VX", "Iwashyna TJ", "et al."],
            journal="JAMA",
            year=2016,
            volume="315",
            pages="762-774",
            pmid="26903335",
            doi="10.1001/jama.2016.0288",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Part of Sepsis-3 definitions. Validated in >1.3 million patients. Outperforms SIRS for predicting mortality in suspected infection.",
        clinical_pearls=[
            ClinicalPearl(
                text="qSOFA >=2 identifies patients at high risk of poor outcomes who warrant increased monitoring",
                category="interpretation",
            ),
            ClinicalPearl(
                text="qSOFA is for risk stratification, NOT for diagnosing sepsis - use SOFA for organ dysfunction criteria",
                category="warning",
            ),
            ClinicalPearl(
                text="Can be calculated at bedside without laboratory values",
                category="usage",
            ),
            ClinicalPearl(
                text="Sensitivity is lower than SIRS but specificity is higher for poor outcomes",
                category="limitation",
            ),
        ],
        pitfalls=[
            "Not a diagnostic tool for sepsis - screens for risk of deterioration",
            "May miss early sepsis (lower sensitivity than SIRS)",
            "Does not replace clinical judgment for antibiotic initiation",
            "Requires altered mental status assessment which can be subjective",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Screening patients with suspected infection outside ICU",
                "Quick bedside risk stratification",
            ],
            when_not_to_use=[
                "ICU patients (use SOFA instead)",
                "Diagnosing sepsis definitively",
                "Deciding whether to initiate antibiotics",
            ],
            target_population="Adults with suspected infection outside the ICU",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="Surviving Sepsis Campaign 2021",
                year=2021,
                organization="SCCM/ESICM",
            ),
            GuidelineReference(
                guideline_name="Sepsis-3 Consensus Definitions",
                year=2016,
                organization="SCCM/ESICM",
            ),
        ],
        related_calculator_ids=["sofa", "sirs"],
        mdcalc_url="https://www.mdcalc.com/calc/2654/qsofa-quick-sofa-score-sepsis",
    ),
)


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
                ("nonspecific_repolarization", 1, "EKG (non-specific changes)"),
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
            name="initial_troponin",
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="A simple risk score in suspected acute coronary syndrome: an analysis of the HEART study",
            authors=["Six AJ", "Backus BE", "Kelder JC"],
            journal="American Journal of Emergency Medicine",
            year=2008,
            volume="26",
            pages="1036-1042",
            pmid="19091264",
            doi="10.1016/j.ajem.2007.12.015",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Validated in >10,000 patients across multiple studies including HEART Pathway trial. Low score (0-3) identifies patients safe for early discharge.",
        overall_validation=ValidationOutcome.STRONGLY_VALIDATED,
        validation_studies=[
            ValidationStudy(
                citation=StructuredCitation(
                    title="Effect of the HEART Pathway on ED Evaluation of Patients With Acute Chest Pain",
                    authors=["Mahler SA", "et al."],
                    journal="JAMA Cardiology",
                    year=2018,
                    pmid="29188296",
                ),
                population="Multi-center randomized trial",
                sample_size=8474,
                validation_outcome=ValidationOutcome.STRONGLY_VALIDATED,
            ),
        ],
        clinical_pearls=[
            ClinicalPearl(
                text="Score 0-3: Low risk, <2% MACE rate - safe for discharge with outpatient follow-up",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Score 4-6: Intermediate risk - observation, serial troponins, stress testing",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Score 7-10: High risk - early invasive strategy",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Troponin component uses multiples of the 99th percentile upper limit of normal",
                category="usage",
            ),
        ],
        pitfalls=[
            "History component is subjective and requires clinical experience",
            "Troponin thresholds vary by assay - know your lab's values",
            "Should not be used if STEMI/NSTEMI already diagnosed",
            "Age is binary (≥65) which may oversimplify risk",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "ED patients with acute chest pain",
                "Risk stratifying for disposition decision",
            ],
            when_not_to_use=[
                "Known STEMI or NSTEMI",
                "Clearly non-cardiac chest pain",
                "Trauma-related chest pain",
            ],
            target_population="Adult ED patients with undifferentiated chest pain",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="2021 AHA/ACC Chest Pain Guidelines",
                year=2021,
                organization="AHA/ACC",
            ),
            GuidelineReference(
                guideline_name="ACEP Clinical Policy for Chest Pain",
                year=2018,
                organization="ACEP",
            ),
        ],
        related_calculator_ids=["timi_risk", "grace_score"],
        mdcalc_url="https://www.mdcalc.com/calc/1752/heart-score-major-cardiac-events",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Assessment of coma and impaired consciousness. A practical scale",
            authors=["Teasdale G", "Jennett B"],
            journal="Lancet",
            year=1974,
            volume="2",
            pages="81-84",
            pmid="4136544",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="The most widely used neurological scoring system worldwide. Essential for TBI classification, intubation decisions, and prognostication. Validated across millions of patients over 50 years.",
        clinical_pearls=[
            ClinicalPearl(
                text="GCS 3-8 = severe TBI; 9-12 = moderate; 13-15 = mild",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Document best response, especially in intubated patients where verbal component is not assessable (use 'T' notation)",
                category="usage",
            ),
            ClinicalPearl(
                text="Motor score alone is the best predictor of outcome if full GCS cannot be obtained",
                category="tip",
            ),
            ClinicalPearl(
                text="Serial GCS changes are more important than single measurements",
                category="interpretation",
            ),
        ],
        pitfalls=[
            "Cannot fully assess intubated/sedated patients (use GCS-T notation)",
            "Eye opening may be impossible due to swelling",
            "Pre-verbal children need modified pediatric scale",
            "Affected by drugs, alcohol, metabolic derangements",
            "Does not capture brainstem function or lateralizing signs",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Initial assessment of consciousness",
                "TBI severity classification",
                "Serial monitoring of neurological status",
            ],
            when_not_to_use=[
                "Pre-verbal children (use pediatric GCS)",
                "Isolated posterior fossa lesions",
            ],
            target_population="Adults and verbal children with altered consciousness",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="Brain Trauma Foundation TBI Guidelines",
                year=2017,
                organization="BTF",
            ),
            GuidelineReference(
                guideline_name="ATLS Guidelines",
                year=2018,
                organization="ACS",
            ),
        ],
        related_calculator_ids=["pediatric_gcs"],
        mdcalc_url="https://www.mdcalc.com/calc/64/glasgow-coma-scale-score-gcs",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Derivation and prospective validation of a simple index for prediction of cardiac risk of major noncardiac surgery",
            authors=["Lee TH", "Marcantonio ER", "Mangione CM", "et al."],
            journal="Circulation",
            year=1999,
            volume="100",
            pages="1043-1049",
            pmid="10477528",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Gold standard for preoperative cardiac risk assessment. Derived from 4,315 patients, validated in 1,422. Endorsed by ACC/AHA guidelines for noncardiac surgery.",
        clinical_pearls=[
            ClinicalPearl(
                text="Score 0 = 0.4% risk; 1 = 0.9%; 2 = 6.6%; ≥3 = 11% risk of major cardiac events",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Use for intermediate-risk or higher surgeries; low-risk procedures (cataract, endoscopy) don't need risk stratification",
                category="usage",
            ),
            ClinicalPearl(
                text="Cardiac troponin and NT-proBNP may add prognostic value to RCRI",
                category="tip",
            ),
            ClinicalPearl(
                text="Does not capture functional capacity - combine with METs assessment",
                category="limitation",
            ),
        ],
        pitfalls=[
            "Underestimates risk in vascular surgery patients (use dedicated vascular calculators)",
            "Does not account for functional capacity (< 4 METs is high risk)",
            "'High-risk surgery' definition is subjective",
            "Insulin-treated diabetes only - oral agents alone score 0",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Preoperative risk assessment for noncardiac surgery",
                "Shared decision-making about surgical risk",
                "Identifying patients who may benefit from preoperative testing",
            ],
            when_not_to_use=[
                "Emergency surgery (no time for risk stratification)",
                "Low-risk surgeries",
                "Vascular surgery (use VSGNE)",
            ],
            target_population="Adults undergoing elective noncardiac surgery",
            excluded_populations=[
                "Emergency surgery patients",
                "Low-risk procedures",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="2014 ACC/AHA Perioperative Guidelines",
                year=2014,
                organization="ACC/AHA",
            ),
            GuidelineReference(
                guideline_name="2022 ESC Guidelines on Cardiovascular Assessment",
                year=2022,
                organization="ESC",
            ),
        ],
        related_calculator_ids=["nsqip", "ariscat"],
        mdcalc_url="https://www.mdcalc.com/calc/1739/revised-cardiac-risk-index-pre-operative-risk",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Clinical criteria to prevent unnecessary diagnostic testing in emergency department patients with suspected pulmonary embolism",
            authors=["Kline JA", "Mitchell AM", "Kabrhel C", "Richman PB", "Courtney DM"],
            journal="Journal of Thrombosis and Haemostasis",
            year=2004,
            volume="2",
            pages="1247-1255",
            pmid="15304025",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Validated to have <2% miss rate when all 8 criteria negative. ACEP Level B recommendation. Only apply to low pre-test probability patients.",
        clinical_pearls=[
            ClinicalPearl(
                text="PERC only applies to LOW pre-test probability patients (gestalt <15% or Wells <2)",
                category="warning",
            ),
            ClinicalPearl(
                text="All 8 criteria must be negative to rule out PE without D-dimer",
                category="interpretation",
            ),
            ClinicalPearl(
                text="If ANY criterion positive, proceed to D-dimer or imaging",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Designed to avoid testing in very low-risk patients, not to diagnose PE",
                category="usage",
            ),
        ],
        pitfalls=[
            "NEVER apply PERC to intermediate or high pre-test probability patients",
            "Criteria must ALL be negative - a single positive means PERC doesn't apply",
            "Does not apply to hospitalized patients",
            "Hormone use includes any estrogen (OCPs, HRT, testosterone in females)",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "First step in PE workup for low pre-test probability patients",
                "Avoiding unnecessary D-dimer testing",
            ],
            when_not_to_use=[
                "Intermediate or high pre-test probability",
                "Hospitalized patients",
                "Pregnancy",
            ],
            target_population="Low pre-test probability ED patients with possible PE",
            excluded_populations=[
                "Intermediate/high pre-test probability",
                "Inpatients",
                "Pregnant women",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="ACEP Clinical Policy: PE",
                year=2018,
                organization="ACEP",
            ),
        ],
        related_calculator_ids=["wells_pe", "pesi"],
        mdcalc_url="https://www.mdcalc.com/calc/347/perc-rule-pulmonary-embolism",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Derivation of a simple clinical model to categorize patients probability of pulmonary embolism: increasing the models utility with the SimpliRED D-dimer",
            authors=["Wells PS", "Anderson DR", "Rodger M", "et al."],
            journal="Thrombosis and Haemostasis",
            year=2000,
            volume="83",
            pages="416-420",
            pmid="10744147",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Validated in >10,000 patients. Part of ACEP clinical policy for PE workup. Combined with D-dimer can safely exclude PE in low-probability patients.",
        clinical_pearls=[
            ClinicalPearl(
                text="PE unlikely (<4 or ≤4): Negative D-dimer can rule out PE without imaging",
                category="interpretation",
            ),
            ClinicalPearl(
                text="PE likely (>4 or ≥5): Proceed directly to CTPA, don't rely on D-dimer",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Consider PERC rule first - if all 8 criteria negative and clinical probability low, no further testing needed",
                category="tip",
            ),
            ClinicalPearl(
                text="'PE most likely diagnosis' is subjective but important - requires clinical experience",
                category="warning",
            ),
        ],
        pitfalls=[
            "Does not apply to pregnancy (use dedicated algorithms)",
            "'PE most likely' criterion is highly subjective",
            "D-dimer less useful in hospitalized/elderly/post-operative patients",
            "Does not rule out subsegmental PE which may still be clinically significant",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "ED evaluation of suspected PE",
                "Deciding whether D-dimer testing is sufficient",
                "Risk stratifying before imaging",
            ],
            when_not_to_use=[
                "Pregnancy",
                "Patients already anticoagulated",
                "Known PE with suspected recurrence",
            ],
            target_population="Adult outpatients with suspected PE",
            excluded_populations=[
                "Pregnant patients",
                "Anticoagulated patients",
                "Hospitalized patients >48h",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="ACEP Clinical Policy: PE",
                year=2018,
                organization="ACEP",
            ),
            GuidelineReference(
                guideline_name="ESC PE Guidelines",
                year=2019,
                organization="ESC",
            ),
        ],
        related_calculator_ids=["wells_dvt", "perc", "pesi"],
        mdcalc_url="https://www.mdcalc.com/calc/115/wells-criteria-pulmonary-embolism",
    ),
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
        # 1-point conditions (names match calculate_charlson function parameters)
        ScoringCriterion("myocardial_infarction", "Myocardial infarction", 1, "History of MI"),
        ScoringCriterion("congestive_heart_failure", "Congestive heart failure", 1, "CHF"),
        ScoringCriterion("peripheral_vascular_disease", "Peripheral vascular disease", 1, "PVD"),
        ScoringCriterion("cerebrovascular_disease", "Cerebrovascular disease", 1, "CVA or TIA"),
        ScoringCriterion("dementia", "Dementia", 1, "Dementia"),
        ScoringCriterion("chronic_pulmonary_disease", "Chronic pulmonary disease", 1, "COPD"),
        ScoringCriterion("connective_tissue_disease", "Connective tissue disease", 1, "Rheumatoid arthritis, lupus, etc."),
        ScoringCriterion("peptic_ulcer_disease", "Peptic ulcer disease", 1, "PUD"),
        ScoringCriterion("mild_liver_disease", "Mild liver disease", 1, "Chronic hepatitis, cirrhosis without portal HTN"),
        ScoringCriterion("diabetes_uncomplicated", "Diabetes (uncomplicated)", 1, "DM without end-organ damage"),
        # 2-point conditions
        ScoringCriterion("hemiplegia", "Hemiplegia", 2, "Hemiplegia"),
        ScoringCriterion("moderate_severe_renal_disease", "Moderate/severe CKD", 2, "Creatinine >3 or on dialysis"),
        ScoringCriterion("diabetes_with_complications", "Diabetes with complications", 2, "DM with retinopathy, nephropathy, neuropathy"),
        ScoringCriterion("solid_tumor_no_metastasis", "Tumor without metastasis", 2, "Solid tumor without mets (past 5 years)"),
        ScoringCriterion("leukemia", "Leukemia", 2, "Leukemia"),
        ScoringCriterion("lymphoma", "Lymphoma", 2, "Lymphoma"),
        # 3-point conditions
        ScoringCriterion("moderate_severe_liver_disease", "Moderate/severe liver disease", 3, "Cirrhosis with portal HTN, varices"),
        # 6-point conditions
        ScoringCriterion("solid_tumor_metastatic", "Metastatic solid tumor", 6, "Metastatic cancer"),
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
        ScoringCriterion("three_or_more_cad_risk_factors", "≥3 CAD risk factors", 1,
                        "HTN, DM, dyslipidemia, family hx, smoking"),
        ScoringCriterion("known_cad_50_stenosis", "Known CAD (stenosis ≥50%)", 1,
                        "Prior coronary stenosis ≥50%"),
        ScoringCriterion("aspirin_use_past_7_days", "Aspirin use in past 7 days", 1,
                        "ASA use within 7 days"),
        ScoringCriterion("severe_angina_two_or_more_episodes_24h", "Severe angina (≥2 episodes/24h)", 1,
                        "2 or more anginal episodes in past 24 hours"),
        ScoringCriterion("st_changes_05mm_or_more", "ST changes ≥0.5mm", 1,
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="TIMI risk score for unstable angina/non-ST elevation MI: A method for prognostication and therapeutic decision making",
            authors=["Antman EM", "Cohen M", "Bernink PJ", "et al."],
            journal="JAMA",
            year=2000,
            volume="284",
            pages="835-842",
            pmid="10938172",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Derived from TIMI 11B trial (3,910 patients) and validated in ESSENCE trial. Validated in >10,000 patients. Predicts 14-day mortality, MI, and revascularization.",
        clinical_pearls=[
            ClinicalPearl(
                text="Score 0-2: Low risk (~5% events); 3-4: Intermediate (~15%); 5-7: High risk (~40%)",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Higher scores benefit more from early invasive strategy",
                category="interpretation",
            ),
            ClinicalPearl(
                text="ASA use in past 7 days indicates refractory symptoms = higher risk",
                category="tip",
            ),
            ClinicalPearl(
                text="TIMI is for UA/NSTEMI only - use different scores for STEMI",
                category="warning",
            ),
        ],
        pitfalls=[
            "Only for UA/NSTEMI, not STEMI (use TIMI risk for STEMI separately)",
            "Troponin positive is binary - doesn't account for degree of elevation",
            "CAD ≥50% stenosis requires prior catheterization data",
            "Does not account for ECG changes",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Risk stratification of UA/NSTEMI",
                "Deciding early invasive vs conservative strategy",
                "Prognosis discussions",
            ],
            when_not_to_use=[
                "STEMI (use TIMI for STEMI)",
                "Non-cardiac chest pain",
                "Already decided on conservative management",
            ],
            target_population="Adults with diagnosed UA/NSTEMI",
            excluded_populations=["STEMI patients", "Non-ACS chest pain"],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="2021 ACC/AHA Chest Pain Guidelines",
                year=2021,
                organization="ACC/AHA",
            ),
            GuidelineReference(
                guideline_name="2020 ESC NSTEMI Guidelines",
                year=2020,
                organization="ESC",
            ),
        ],
        related_calculator_ids=["heart_score", "grace_score"],
        mdcalc_url="https://www.mdcalc.com/calc/111/timi-risk-score-ua-nstemi",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="A model to predict survival in patients with end-stage liver disease",
            authors=["Kamath PS", "Wiesner RH", "Malinchoc M", "et al."],
            journal="Hepatology",
            year=2001,
            volume="33",
            pages="464-470",
            pmid="11172350",
            doi="10.1053/jhep.2001.22172",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="UNOS standard for liver transplant allocation since 2002. Validated in >100,000 patients. MELD 3.0 (2022) incorporates sex and removes race-based eGFR.",
        clinical_pearls=[
            ClinicalPearl(
                text="MELD is used by UNOS to prioritize liver transplant allocation - higher scores = higher priority",
                category="interpretation",
            ),
            ClinicalPearl(
                text="MELD-Na (with sodium) better predicts mortality in cirrhosis than original MELD",
                category="tip",
            ),
            ClinicalPearl(
                text="INR is affected by anticoagulation - use caution in patients on warfarin",
                category="warning",
            ),
            ClinicalPearl(
                text="MELD 3.0 (adopted 2022) adds sex, removes race from eGFR calculation",
                category="usage",
            ),
        ],
        pitfalls=[
            "INR affected by warfarin, liver synthetic function, and lab variability",
            "Creatinine affected by muscle mass, dialysis status",
            "Does not capture HCC or hepatopulmonary syndrome (need exception points)",
            "May underestimate severity in acute-on-chronic liver failure",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Liver transplant prioritization",
                "Estimating 90-day mortality in cirrhosis",
                "Assessing disease progression",
            ],
            when_not_to_use=[
                "Fulminant hepatic failure (separate criteria)",
                "Pediatric patients (use PELD)",
            ],
            target_population="Adults with chronic liver disease being considered for transplant",
            excluded_populations=[
                "Pediatric patients",
                "Acute liver failure without chronic disease",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="UNOS Liver Allocation Policy",
                year=2022,
                organization="UNOS/OPTN",
            ),
            GuidelineReference(
                guideline_name="AASLD Cirrhosis Guidelines",
                year=2021,
                organization="AASLD",
            ),
        ],
        related_calculator_ids=["child_pugh", "meld_na", "meld_3"],
        mdcalc_url="https://www.mdcalc.com/calc/78/meld-score-model-end-stage-liver-disease-12-older",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Indices of relative weight and obesity",
            authors=["Keys A", "Fidanza F", "Karvonen MJ", "Kimura N", "Taylor HL"],
            journal="Journal of Chronic Diseases",
            year=1972,
            volume="25",
            pages="329-343",
            pmid="4650929",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="WHO global standard for weight classification since 1995. Simple screening tool validated in millions. Correlates with body fat and mortality risk at population level.",
        clinical_pearls=[
            ClinicalPearl(
                text="BMI <18.5 = Underweight; 18.5-24.9 = Normal; 25-29.9 = Overweight; ≥30 = Obese",
                category="interpretation",
            ),
            ClinicalPearl(
                text="BMI does not distinguish muscle from fat - use waist circumference for central adiposity",
                category="limitation",
            ),
            ClinicalPearl(
                text="Asian populations have higher risk at lower BMI - use Asian-specific cutoffs (<23 overweight)",
                category="warning",
            ),
            ClinicalPearl(
                text="Always measure height and weight, don't rely on self-report",
                category="tip",
            ),
        ],
        pitfalls=[
            "Does not account for muscle mass (athletes may be 'overweight' by BMI but not overfat)",
            "Does not capture fat distribution (central obesity is higher risk)",
            "Standard cutoffs may not apply to all ethnicities (lower cutoffs for Asians)",
            "Not applicable to children (use CDC growth charts)",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Initial weight classification",
                "Screening for obesity-related health risks",
                "Population health studies",
            ],
            when_not_to_use=[
                "Athletes with high muscle mass",
                "Children <18 (use growth charts)",
                "Patients with edema/ascites",
            ],
            target_population="Adults 18+ for initial weight assessment",
            excluded_populations=[
                "Children",
                "Pregnant women",
                "Athletes (use body composition)",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="WHO Obesity Classification",
                year=2000,
                organization="WHO",
            ),
            GuidelineReference(
                guideline_name="AHA/ACC/TOS Obesity Guidelines",
                year=2013,
                organization="AHA/ACC/TOS",
            ),
        ],
        related_calculator_ids=["ideal_body_weight", "bsa"],
        mdcalc_url="https://www.mdcalc.com/calc/29/body-mass-index-bmi-body-surface-area-bsa",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="The SOFA (Sepsis-related Organ Failure Assessment) score to describe organ dysfunction/failure",
            authors=["Vincent JL", "Moreno R", "Takala J", "et al."],
            journal="Intensive Care Medicine",
            year=1996,
            volume="22",
            pages="707-710",
            pmid="8844239",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Gold standard for organ dysfunction assessment in critical care. Central to Sepsis-3 diagnostic criteria. Validated in thousands of ICU patients.",
        clinical_pearls=[
            ClinicalPearl(
                text="Sepsis = suspected infection + SOFA increase ≥2 from baseline",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Septic shock = sepsis + vasopressors + lactate >2 mmol/L despite fluids",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Daily SOFA trends predict mortality better than single measurements",
                category="usage",
            ),
            ClinicalPearl(
                text="Baseline SOFA assumed to be 0 in patients without known pre-existing organ dysfunction",
                category="tip",
            ),
        ],
        pitfalls=[
            "Requires laboratory values (not bedside calculation)",
            "GCS component may be confounded by sedation",
            "Chronic organ dysfunction may elevate baseline",
            "Different vasopressor doses difficult to compare precisely",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "ICU patients with suspected sepsis",
                "Tracking organ dysfunction over time",
                "Diagnosing sepsis per Sepsis-3 criteria",
            ],
            when_not_to_use=[
                "Screening outside ICU (use qSOFA)",
                "Chronic stable organ dysfunction",
            ],
            target_population="ICU patients, particularly those with suspected infection",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="Sepsis-3 Consensus Definitions",
                year=2016,
                organization="SCCM/ESICM",
            ),
            GuidelineReference(
                guideline_name="Surviving Sepsis Campaign 2021",
                year=2021,
                organization="SCCM/ESICM",
            ),
        ],
        related_calculator_ids=["qsofa", "sirs", "apache_ii"],
        mdcalc_url="https://www.mdcalc.com/calc/691/sequential-organ-failure-assessment-sofa-score",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Prediction of coronary heart disease using risk factor categories",
            authors=["Wilson PW", "D'Agostino RB", "Levy D", "Belanger AM", "Silbershatz H", "Kannel WB"],
            journal="Circulation",
            year=1998,
            volume="97",
            pages="1837-1847",
            pmid="9603539",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Foundation of cardiovascular risk prediction. Derived from 5,345 Framingham Heart Study participants. Basis for ASCVD risk calculator and statin guidelines.",
        clinical_pearls=[
            ClinicalPearl(
                text="Estimates 10-year risk of coronary heart disease (MI, coronary death)",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Risk ≥20% = high risk, equivalent to secondary prevention",
                category="interpretation",
            ),
            ClinicalPearl(
                text="ACC/AHA now prefer ASCVD Pooled Cohort Equation, which includes stroke risk",
                category="usage",
            ),
            ClinicalPearl(
                text="May underestimate risk in South Asian and Hispanic populations",
                category="limitation",
            ),
        ],
        pitfalls=[
            "Derived primarily from white population - may not generalize to all ethnicities",
            "ASCVD Pooled Cohort Equations now preferred by ACC/AHA guidelines",
            "Does not include family history as risk factor",
            "HDL and total cholesterol used, not LDL directly",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Primary prevention risk assessment",
                "Discussing statin therapy initiation",
                "Patient education about cardiovascular risk",
            ],
            when_not_to_use=[
                "Secondary prevention (already have ASCVD)",
                "Patients on statins",
                "Patients <40 or >79 years",
            ],
            target_population="Adults 40-79 years without known ASCVD for primary prevention",
            excluded_populations=[
                "Known ASCVD",
                "Age <40 or >79",
                "On lipid-lowering therapy",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="2018 ACC/AHA Cholesterol Guidelines",
                year=2018,
                organization="ACC/AHA",
            ),
        ],
        related_calculator_ids=["ascvd_pooled_cohort"],
        mdcalc_url="https://www.mdcalc.com/calc/38/framingham-risk-score-hard-coronary-heart-disease",
    ),
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
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="Surgery of portal hypertension",
            authors=["Pugh RN", "Murray-Lyon IM", "Dawson JL", "Pietroni MC", "Williams R"],
            journal="British Journal of Surgery",
            year=1973,
            volume="60",
            pages="646-649",
            pmid="4541913",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Modified Child classification, used for 50+ years. Standard for assessing hepatic reserve in cirrhosis. Predicts perioperative mortality and guides treatment decisions.",
        clinical_pearls=[
            ClinicalPearl(
                text="Class A (5-6): Good hepatic reserve, 100% 1-year survival; Class B (7-9): Moderate impairment, 80% 1-year; Class C (10-15): Severe, 45% 1-year",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Ascites and encephalopathy are subjective - be consistent in grading",
                category="tip",
            ),
            ClinicalPearl(
                text="Used to determine if patient can tolerate surgery or chemotherapy",
                category="usage",
            ),
            ClinicalPearl(
                text="INR can substitute for PT prolongation in modern practice",
                category="usage",
            ),
        ],
        pitfalls=[
            "Subjective assessment of ascites (controlled vs refractory) and encephalopathy grade",
            "Does not account for renal function (important prognostic factor)",
            "Ceiling effect at Class C limits discrimination",
            "MELD preferred for transplant allocation due to better predictive validity",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Assessing severity of cirrhosis",
                "Surgical risk stratification",
                "Drug dosing in hepatic impairment",
            ],
            when_not_to_use=[
                "Transplant prioritization (use MELD)",
                "Non-cirrhotic liver disease",
            ],
            target_population="Adults with cirrhosis",
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="EASL Cirrhosis Guidelines",
                year=2018,
                organization="EASL",
            ),
            GuidelineReference(
                guideline_name="AASLD Ascites Management",
                year=2021,
                organization="AASLD",
            ),
        ],
        related_calculator_ids=["meld", "meld_na"],
        mdcalc_url="https://www.mdcalc.com/calc/340/child-pugh-score-cirrhosis-mortality",
    ),
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


# ============================================================================
# eGFR CKD-EPI (2021 Race-free)
# ============================================================================
EGFR_CKDEPI_DEFINITION = CalculatorDefinition(
    id="egfr_ckdepi",
    name="eGFR CKD-EPI 2021",
    short_name="eGFR",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min/1.73m²",
    description="Estimated glomerular filtration rate (2021 race-free equation)",
    references=["Inker LA, et al. N Engl J Med 2021", "KDIGO 2012 Clinical Practice Guideline"],
    specialties=["Nephrology", "Internal Medicine", "Primary Care"],
    notes=["2021 equation removes race adjustment", "More accurate than Cockcroft-Gault for drug dosing"],
    formula=FormulaDefinition(
        formula_text="142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^-1.200 × 0.9938^age × sex_factor",
        output_unit="mL/min/1.73m²",
        precision=0,
        parameters=[
            FormulaParameter(name="creatinine", display_name="Serum Creatinine", unit="mg/dL", min_value=0.2, max_value=15.0),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1, description="1 if female, 0 if male"),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="G1: Normal or high (≥90)", recommendations=["CKD if other markers of kidney damage"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="G2: Mildly decreased (60-89)", recommendations=["CKD if other markers present"]),
        ThresholdInterpretation(min_score=45, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="G3a: Mildly-moderately decreased (45-59)", recommendations=["Nephrology referral", "BP/DM control"]),
        ThresholdInterpretation(min_score=30, max_score=45, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="G3b: Moderately-severely decreased (30-44)", recommendations=["Nephrology referral", "Avoid nephrotoxins"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="G4: Severely decreased (15-29)", recommendations=["Prepare for RRT", "Dietary modifications"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="G5: Kidney failure (<15)", recommendations=["Dialysis/transplant evaluation"]),
    ],
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="A new equation to estimate glomerular filtration rate",
            authors=["Levey AS", "Stevens LA", "Schmid CH", "et al."],
            journal="Annals of Internal Medicine",
            year=2009,
            volume="150",
            pages="604-612",
            pmid="19414839",
            doi="10.7326/0003-4819-150-9-200905050-00006",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Current KDIGO standard for GFR estimation. CKD-EPI 2021 removes race coefficient per NKF-ASN recommendations. More accurate than MDRD at higher GFR values.",
        clinical_pearls=[
            ClinicalPearl(
                text="CKD-EPI 2021 (race-free) is now recommended by NKF-ASN - do not use race coefficient",
                category="warning",
            ),
            ClinicalPearl(
                text="More accurate than MDRD at eGFR >60 mL/min/1.73m²",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Use cystatin C-based equation for patients with extremes of muscle mass",
                category="tip",
            ),
            ClinicalPearl(
                text="eGFR <60 for ≥3 months defines CKD, regardless of albuminuria",
                category="interpretation",
            ),
        ],
        pitfalls=[
            "Creatinine-based equations affected by muscle mass (sarcopenia, amputees, bodybuilders)",
            "Not valid in AKI (use urine output criteria)",
            "Drug dosing may require different equations for specific medications",
            "2021 race-free version gives different results than 2009 version",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "CKD staging",
                "Drug dosing for renally cleared medications",
                "Monitoring kidney function over time",
            ],
            when_not_to_use=[
                "AKI assessment",
                "Patients on dialysis",
                "Children <18 years (use Schwartz)",
            ],
            target_population="Adults with stable kidney function",
            excluded_populations=[
                "Children <18",
                "Dialysis patients",
                "AKI patients",
                "Pregnancy",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="KDIGO CKD Guidelines 2024",
                year=2024,
                organization="KDIGO",
            ),
            GuidelineReference(
                guideline_name="NKF-ASN Taskforce Recommendations",
                year=2021,
                organization="NKF-ASN",
            ),
        ],
        related_calculator_ids=["cockcroft_gault", "mdrd"],
        mdcalc_url="https://www.mdcalc.com/calc/3939/ckd-epi-equations-glomerular-filtration-rate-gfr",
    ),
)


# ============================================================================
# FIB-4 (Fibrosis-4 Index)
# ============================================================================
FIB4_DEFINITION = CalculatorDefinition(
    id="fib4",
    name="FIB-4 Index for Liver Fibrosis",
    short_name="FIB-4",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Non-invasive liver fibrosis assessment",
    references=["Sterling RK, et al. Hepatology 2006", "McPherson S, et al. Gut 2010"],
    specialties=["Hepatology", "Gastroenterology", "Primary Care"],
    notes=["Best validated in NAFLD and hepatitis C", "Low FIB-4 rules out advanced fibrosis"],
    formula=FormulaDefinition(
        formula_text="(Age × AST) / (Platelets × √ALT)",
        output_unit="",
        precision=2,
        parameters=[
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="ast", display_name="AST", unit="U/L", min_value=5, max_value=2000),
            FormulaParameter(name="alt", display_name="ALT", unit="U/L", min_value=5, max_value=2000),
            FormulaParameter(name="platelets", display_name="Platelets", unit="×10⁹/L", min_value=20, max_value=600),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1.3, risk_level=RiskLevel.LOW,
            interpretation="Low risk for advanced fibrosis (F3-F4)",
            recommendations=["Low probability of cirrhosis", "Routine follow-up", "No further testing needed"]),
        ThresholdInterpretation(min_score=1.3, max_score=2.67, risk_level=RiskLevel.MODERATE,
            interpretation="Indeterminate - further testing recommended",
            recommendations=["Consider FibroScan or ELF test", "Hepatology consultation if high risk"]),
        ThresholdInterpretation(min_score=2.67, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk for advanced fibrosis",
            recommendations=["High probability of F3-F4 fibrosis", "Hepatology referral", "Consider liver biopsy or FibroScan"]),
    ],
)


# ============================================================================
# NEWS2 (National Early Warning Score 2)
# ============================================================================
NEWS2_DEFINITION = CalculatorDefinition(
    id="news2",
    name="National Early Warning Score 2",
    short_name="NEWS2",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Identifies patients at risk of clinical deterioration",
    references=["Royal College of Physicians 2017"],
    specialties=["Emergency Medicine", "Critical Care", "Internal Medicine", "Nursing"],
    notes=["Scale 2 for SpO2 in COPD patients with target 88-92%", "3 in any parameter = clinical concern"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="respiratory_rate",
            display_name="Respiratory Rate",
            levels=[
                ("leq_8", 3, "≤8 (3)"), ("9_11", 1, "9-11 (1)"), ("12_20", 0, "12-20 (0)"),
                ("21_24", 2, "21-24 (2)"), ("gte_25", 3, "≥25 (3)"),
            ],
            description="Breaths per minute",
        ),
        MultiLevelCriterion(
            name="spo2_scale1",
            display_name="SpO2 (Scale 1)",
            levels=[
                ("leq_91", 3, "≤91% (3)"), ("92_93", 2, "92-93% (2)"),
                ("94_95", 1, "94-95% (1)"), ("gte_96", 0, "≥96% (0)"),
            ],
            description="Oxygen saturation (normal target)",
        ),
        MultiLevelCriterion(
            name="air_or_oxygen",
            display_name="Air or Oxygen",
            levels=[("air", 0, "Air (0)"), ("oxygen", 2, "Oxygen (2)")],
            description="Supplemental oxygen",
        ),
        MultiLevelCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            levels=[
                ("leq_90", 3, "≤90 (3)"), ("91_100", 2, "91-100 (2)"), ("101_110", 1, "101-110 (1)"),
                ("111_219", 0, "111-219 (0)"), ("gte_220", 3, "≥220 (3)"),
            ],
            description="Systolic blood pressure mmHg",
        ),
        MultiLevelCriterion(
            name="pulse",
            display_name="Pulse",
            levels=[
                ("leq_40", 3, "≤40 (3)"), ("41_50", 1, "41-50 (1)"), ("51_90", 0, "51-90 (0)"),
                ("91_110", 1, "91-110 (1)"), ("111_130", 2, "111-130 (2)"), ("gte_131", 3, "≥131 (3)"),
            ],
            description="Heart rate bpm",
        ),
        MultiLevelCriterion(
            name="consciousness",
            display_name="Consciousness",
            levels=[("alert", 0, "Alert (0)"), ("cvpu", 3, "Confused/V/P/U (3)")],
            description="ACVPU scale",
        ),
        MultiLevelCriterion(
            name="temperature",
            display_name="Temperature",
            levels=[
                ("leq_35", 3, "≤35.0°C (3)"), ("35_36", 1, "35.1-36.0°C (1)"),
                ("36_38", 0, "36.1-38.0°C (0)"), ("38_39", 1, "38.1-39.0°C (1)"), ("gte_39", 2, "≥39.1°C (2)"),
            ],
            description="Temperature °C",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk", recommendations=["Routine monitoring"]),
        ThresholdInterpretation(min_score=1, max_score=5, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low-medium clinical risk", recommendations=["Increased monitoring", "Nurse assessment"]),
        ThresholdInterpretation(min_score=5, max_score=7, risk_level=RiskLevel.MODERATE,
            interpretation="Medium clinical risk", recommendations=["Urgent physician review", "Consider ICU"]),
        ThresholdInterpretation(min_score=7, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High clinical risk - Emergency response", recommendations=["Immediate physician review", "Critical care assessment"]),
    ],
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="National Early Warning Score (NEWS) 2: Standardising the assessment of acute-illness severity in the NHS",
            authors=["Royal College of Physicians"],
            journal="Clinical Medicine",
            year=2017,
            pmid="29473828",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="UK NHS standard for detecting acute deterioration. NEWS2 validated across >800,000 patients. Updated in 2017 to improve detection of Type 2 respiratory failure.",
        clinical_pearls=[
            ClinicalPearl(
                text="NEWS2 aggregate score >=5 or any single parameter score of 3 = clinical urgency",
                category="interpretation",
            ),
            ClinicalPearl(
                text="SpO2 Scale 2 should be used for patients at risk of hypercapnic respiratory failure (COPD, obesity hypoventilation)",
                category="usage",
            ),
            ClinicalPearl(
                text="Track trends over time - a rising NEWS score is more concerning than a single high value",
                category="tip",
            ),
            ClinicalPearl(
                text="NEWS does not replace clinical judgment - it's a screening tool to trigger further assessment",
                category="warning",
            ),
        ],
        pitfalls=[
            "SpO2 Scale 1 vs Scale 2 selection is critical for COPD patients",
            "Does not account for patient baseline (e.g., chronically low BP)",
            "Temperature can mask deterioration if antipyretics given",
            "May not detect subtle neurological changes",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "All acute hospital admissions",
                "Tracking clinical deterioration",
                "Triggering escalation protocols",
            ],
            when_not_to_use=[
                "Children <16 (use PEWS)",
                "Obstetric patients (use MEOWS)",
                "End-of-life care settings",
            ],
            target_population="Adults in acute hospital settings",
            excluded_populations=[
                "Pediatric patients",
                "Obstetric patients",
                "Patients on comfort measures only",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="NHS England NEWS2 Implementation Guidance",
                year=2018,
                organization="NHS England",
            ),
            GuidelineReference(
                guideline_name="NICE CG50 Acutely ill adults",
                year=2007,
                organization="NICE",
            ),
        ],
        related_calculator_ids=["qsofa", "mews"],
        mdcalc_url="https://www.mdcalc.com/calc/1873/national-early-warning-score-news-2",
    ),
)


# ============================================================================
# A-a GRADIENT
# ============================================================================
AA_GRADIENT_DEFINITION = CalculatorDefinition(
    id="aa_gradient",
    name="Alveolar-arterial Gradient",
    short_name="A-a Gradient",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.DECIMAL,
    score_unit="mmHg",
    description="Difference between alveolar and arterial oxygen",
    references=["West JB. Respiratory Physiology"],
    specialties=["Pulmonology", "Critical Care", "Emergency Medicine"],
    notes=["Normal gradient increases with age: (Age/4) + 4", "High gradient = V/Q mismatch, shunt, diffusion defect"],
    formula=FormulaDefinition(
        formula_text="PAO2 - PaO2 = [(FiO2 × (Patm - 47)) - (PaCO2/0.8)] - PaO2",
        output_unit="mmHg",
        precision=1,
        parameters=[
            FormulaParameter(name="pao2", display_name="PaO2", unit="mmHg", min_value=20, max_value=600),
            FormulaParameter(name="paco2", display_name="PaCO2", unit="mmHg", min_value=10, max_value=120),
            FormulaParameter(name="fio2", display_name="FiO2", unit="%", min_value=21, max_value=100),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100, required=False),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.LOW,
            interpretation="Normal A-a gradient", recommendations=["If hypoxemic: hypoventilation (CNS, NM disease)"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.MODERATE,
            interpretation="Mildly elevated gradient", recommendations=["V/Q mismatch most likely", "Consider PE, pneumonia, asthma"]),
        ThresholdInterpretation(min_score=30, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Markedly elevated gradient", recommendations=["Significant V/Q mismatch or shunt", "Consider PE, ARDS, severe pneumonia"]),
    ],
)


# ============================================================================
# MEAN ARTERIAL PRESSURE (MAP)
# ============================================================================
MAP_DEFINITION = CalculatorDefinition(
    id="map",
    name="Mean Arterial Pressure",
    short_name="MAP",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="mmHg",
    description="Average arterial pressure during cardiac cycle",
    references=["Chemla D, et al. Chest 2005"],
    specialties=["Critical Care", "Emergency Medicine", "Cardiology", "Anesthesiology"],
    formula=FormulaDefinition(
        formula_text="DBP + (SBP - DBP)/3 or (SBP + 2×DBP)/3",
        output_unit="mmHg",
        precision=0,
        parameters=[
            FormulaParameter(name="systolic", display_name="Systolic BP", unit="mmHg", min_value=40, max_value=300),
            FormulaParameter(name="diastolic", display_name="Diastolic BP", unit="mmHg", min_value=20, max_value=200),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=60, risk_level=RiskLevel.HIGH,
            interpretation="Hypotension - inadequate organ perfusion", recommendations=["Consider fluid resuscitation", "Vasopressors may be needed"]),
        ThresholdInterpretation(min_score=60, max_score=65, risk_level=RiskLevel.MODERATE,
            interpretation="Low-normal (may be inadequate in sepsis)", recommendations=["Target MAP ≥65 in sepsis"]),
        ThresholdInterpretation(min_score=65, max_score=100, risk_level=RiskLevel.LOW,
            interpretation="Normal MAP", recommendations=["Adequate perfusion pressure"]),
        ThresholdInterpretation(min_score=100, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="Elevated MAP", recommendations=["Evaluate for hypertensive urgency/emergency if symptomatic"]),
    ],
)


# ============================================================================
# CALCULATED SERUM OSMOLALITY
# ============================================================================
SERUM_OSMOLALITY_DEFINITION = CalculatorDefinition(
    id="serum_osmolality",
    name="Calculated Serum Osmolality",
    short_name="Osm",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.INTEGER,
    score_unit="mOsm/kg",
    description="Estimated serum osmolality from routine labs",
    references=["Purssell RA, et al. Ann Emerg Med 2001"],
    specialties=["Nephrology", "Emergency Medicine", "Critical Care"],
    formula=FormulaDefinition(
        formula_text="(2 × Na) + (Glucose/18) + (BUN/2.8)",
        output_unit="mOsm/kg",
        precision=0,
        parameters=[
            FormulaParameter(name="sodium", display_name="Sodium", unit="mEq/L", min_value=100, max_value=180),
            FormulaParameter(name="glucose", display_name="Glucose", unit="mg/dL", min_value=20, max_value=1500),
            FormulaParameter(name="bun", display_name="BUN", unit="mg/dL", min_value=2, max_value=200),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=275, risk_level=RiskLevel.MODERATE,
            interpretation="Hypo-osmolal", recommendations=["Evaluate for hyponatremia causes"]),
        ThresholdInterpretation(min_score=275, max_score=295, risk_level=RiskLevel.LOW,
            interpretation="Normal osmolality (275-295)", recommendations=["Normal"]),
        ThresholdInterpretation(min_score=295, max_score=320, risk_level=RiskLevel.MODERATE,
            interpretation="Hyperosmolal", recommendations=["Evaluate for hypernatremia, hyperglycemia, uremia"]),
        ThresholdInterpretation(min_score=320, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Severely hyperosmolal (>320)", recommendations=["HHS? DKA? Evaluate urgently"]),
    ],
)


# ============================================================================
# CAPRINI VTE RISK SCORE
# ============================================================================
CAPRINI_DEFINITION = CalculatorDefinition(
    id="caprini",
    name="Caprini VTE Risk Score",
    short_name="Caprini",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.SURGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Perioperative VTE risk stratification",
    references=["Caprini JA, et al. Dis Mon 2005", "Gould MK, et al. Chest 2012"],
    specialties=["Surgery", "Anesthesiology", "Internal Medicine", "Hospitalist"],
    threshold_criteria=[
        ThresholdCriterion(name="age", display_name="Age",
            thresholds=[("range", (41, 60), 1, "41-60 (1)"), ("range", (61, 74), 2, "61-74 (2)"), ("gte", 75, 3, "≥75 (3)")],
            description="Age category"),
    ],
    criteria=[
        # 1-point factors
        ScoringCriterion("minor_surgery", "Minor surgery planned", 1, ""),
        ScoringCriterion("swollen_legs", "Swollen legs", 1, ""),
        ScoringCriterion("varicose_veins", "Varicose veins", 1, ""),
        ScoringCriterion("inflammatory_bowel", "IBD history", 1, ""),
        ScoringCriterion("obesity_bmi_25", "BMI >25", 1, ""),
        ScoringCriterion("mi", "Acute MI", 1, ""),
        ScoringCriterion("chf", "CHF", 1, ""),
        ScoringCriterion("sepsis", "Sepsis (<1 month)", 1, ""),
        ScoringCriterion("pneumonia", "Serious lung disease", 1, ""),
        ScoringCriterion("oral_contraceptives", "OCP/HRT", 1, ""),
        ScoringCriterion("pregnant", "Pregnant/postpartum", 1, ""),
        ScoringCriterion("unexplained_stillborn", "Unexplained stillborn", 1, ""),
        ScoringCriterion("recurrent_miscarriage", "Recurrent miscarriage", 1, ""),
        ScoringCriterion("bed_rest", "Bed rest >72 hours", 1, ""),
        # 2-point factors
        ScoringCriterion("major_surgery", "Major surgery >45 min", 2, ""),
        ScoringCriterion("laparoscopic_45", "Laparoscopic >45 min", 2, ""),
        ScoringCriterion("malignancy", "Malignancy", 2, ""),
        ScoringCriterion("confined_to_bed", "Confined to bed >72h", 2, ""),
        ScoringCriterion("immobilizing_cast", "Immobilizing cast", 2, ""),
        ScoringCriterion("central_venous_access", "Central venous access", 2, ""),
        # 3-point factors
        ScoringCriterion("prior_vte", "Prior VTE", 3, ""),
        ScoringCriterion("family_vte", "Family VTE history", 3, ""),
        ScoringCriterion("factor_v_leiden", "Factor V Leiden", 3, ""),
        ScoringCriterion("prothrombin_mutation", "Prothrombin 20210A", 3, ""),
        ScoringCriterion("lupus_anticoagulant", "Lupus anticoagulant", 3, ""),
        ScoringCriterion("anticardiolipin_ab", "Anticardiolipin antibodies", 3, ""),
        ScoringCriterion("elevated_homocysteine", "Elevated homocysteine", 3, ""),
        ScoringCriterion("heparin_induced_thrombocytopenia", "HIT", 3, ""),
        # 5-point factors
        ScoringCriterion("stroke", "Stroke (<1 month)", 5, ""),
        ScoringCriterion("elective_arthroplasty", "Hip/knee arthroplasty", 5, ""),
        ScoringCriterion("hip_pelvis_leg_fracture", "Fracture hip/pelvis/leg", 5, ""),
        ScoringCriterion("acute_spinal_cord_injury", "Acute spinal cord injury", 5, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Very low risk (<0.5%)", recommendations=["Early ambulation"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low risk (1.5%)", recommendations=["Mechanical prophylaxis (SCDs)"]),
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate risk (3%)", recommendations=["Pharmacologic +/- mechanical prophylaxis"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk (6%)", recommendations=["Pharmacologic + mechanical prophylaxis", "Extended prophylaxis for high-risk surgeries"]),
    ],
)


# ============================================================================
# BISAP SCORE (Pancreatitis)
# ============================================================================
BISAP_DEFINITION = CalculatorDefinition(
    id="bisap",
    name="BISAP Score for Pancreatitis Mortality",
    short_name="BISAP",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts mortality in acute pancreatitis within 24h",
    references=["Wu BU, et al. Gut 2008"],
    specialties=["Gastroenterology", "Surgery", "Emergency Medicine", "Critical Care"],
    criteria=[
        ScoringCriterion("bun_over_25", "BUN >25 mg/dL", 1, ""),
        ScoringCriterion("impaired_mental_status", "Impaired mental status", 1, ""),
        ScoringCriterion("sirs_present", "SIRS present", 1, "≥2 SIRS criteria"),
        ScoringCriterion("age_over_60", "Age >60", 1, ""),
        ScoringCriterion("pleural_effusion", "Pleural effusion on imaging", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low mortality (<1%)", recommendations=["Standard care", "Monitor for deterioration"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate mortality (~5%)", recommendations=["Close monitoring", "Consider ICU"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High mortality (>15%)", recommendations=["ICU admission", "Aggressive supportive care"]),
    ],
)


# ============================================================================
# COCKCROFT-GAULT CREATININE CLEARANCE
# ============================================================================
CREATININE_CLEARANCE_DEFINITION = CalculatorDefinition(
    id="creatinine_clearance",
    name="Creatinine Clearance (Cockcroft-Gault)",
    short_name="CrCl",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min",
    description="Estimated creatinine clearance for drug dosing",
    references=["Cockcroft DW, Gault MH. Nephron 1976"],
    specialties=["Nephrology", "Pharmacy", "Internal Medicine"],
    notes=["FDA prefers CrCl for drug dosing", "Uses actual or ideal body weight per drug label"],
    formula=FormulaDefinition(
        formula_text="[(140 - age) × weight] / (72 × Scr) × 0.85 if female",
        output_unit="mL/min",
        precision=0,
        parameters=[
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=120),
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=30, max_value=250),
            FormulaParameter(name="creatinine", display_name="Serum Creatinine", unit="mg/dL", min_value=0.3, max_value=15.0),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Normal renal function", recommendations=["Standard drug dosing"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mild impairment", recommendations=["Check drug-specific dosing"]),
        ThresholdInterpretation(min_score=30, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate impairment", recommendations=["Dose reduction often needed"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="Severe impairment", recommendations=["Significant dose reductions", "Avoid nephrotoxins"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="End-stage (<15 mL/min)", recommendations=["Dialysis dosing considerations"]),
    ],
)


# ============================================================================
# CORRECTED SODIUM (for Hyperglycemia)
# ============================================================================
CORRECTED_SODIUM_DEFINITION = CalculatorDefinition(
    id="corrected_sodium",
    name="Corrected Sodium for Hyperglycemia",
    short_name="Corrected Na",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mEq/L",
    description="Adjusts sodium for hyperglycemia (Katz formula)",
    references=["Katz MA. N Engl J Med 1973", "Hillier TA, et al. Am J Med 1999"],
    specialties=["Emergency Medicine", "Endocrinology", "Critical Care"],
    notes=["Formula: Na + 1.6 × (Glucose - 100) / 100", "Some use 2.4 mEq/L per 100 mg/dL glucose"],
    formula=FormulaDefinition(
        formula_text="Na + 1.6 × (Glucose - 100) / 100",
        output_unit="mEq/L",
        precision=1,
        parameters=[
            FormulaParameter(name="sodium", display_name="Measured Sodium", unit="mEq/L", min_value=100, max_value=180),
            FormulaParameter(name="glucose", display_name="Glucose", unit="mg/dL", min_value=100, max_value=2000),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=135, risk_level=RiskLevel.MODERATE,
            interpretation="Hyponatremia (corrected)", recommendations=["True hyponatremia despite hyperglycemia"]),
        ThresholdInterpretation(min_score=135, max_score=145, risk_level=RiskLevel.LOW,
            interpretation="Normal corrected sodium", recommendations=["Dilutional effect from hyperglycemia"]),
        ThresholdInterpretation(min_score=145, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="Hypernatremia (corrected)", recommendations=["Significant free water deficit"]),
    ],
)


# ============================================================================
# MAINTENANCE IV FLUIDS (Holliday-Segar)
# ============================================================================
MAINTENANCE_FLUIDS_DEFINITION = CalculatorDefinition(
    id="maintenance_fluids",
    name="Maintenance IV Fluids (Holliday-Segar)",
    short_name="Maintenance IVF",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="mL/day",
    description="Calculate maintenance fluid requirements by weight",
    references=["Holliday MA, Segar WE. Pediatrics 1957"],
    specialties=["Pediatrics", "Emergency Medicine", "Surgery"],
    notes=["4-2-1 rule: 4 mL/kg/hr for first 10 kg, 2 mL/kg/hr for next 10 kg, 1 mL/kg/hr thereafter"],
    formula=FormulaDefinition(
        formula_text="100 mL/kg for first 10 kg + 50 mL/kg for next 10 kg + 20 mL/kg thereafter",
        output_unit="mL/day",
        precision=0,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=1, max_value=150),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Calculated maintenance fluid rate",
            recommendations=["Adjust for ongoing losses", "Consider clinical status", "Hourly rate = daily/24"]),
    ],
)


# ============================================================================
# PARKLAND FORMULA (Burns)
# ============================================================================
PARKLAND_DEFINITION = CalculatorDefinition(
    id="parkland",
    name="Parkland Formula for Burns",
    short_name="Parkland",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="mL/24h",
    description="Fluid resuscitation for burn patients",
    references=["Baxter CR, Shires T. Surg Clin North Am 1968"],
    specialties=["Emergency Medicine", "Surgery", "Critical Care", "Burn Surgery"],
    notes=["4 mL × kg × %TBSA burned", "Give half in first 8 hours from burn time", "Use LR"],
    formula=FormulaDefinition(
        formula_text="4 × Weight(kg) × %TBSA",
        output_unit="mL in 24h",
        precision=0,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=1, max_value=200),
            FormulaParameter(name="tbsa", display_name="TBSA Burned", unit="%", min_value=1, max_value=100),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="24-hour fluid requirement",
            recommendations=[
                "Give 50% in first 8 hours from burn time",
                "Give remaining 50% over next 16 hours",
                "Use Lactated Ringer's",
                "Titrate to urine output 0.5-1 mL/kg/hr",
            ]),
    ],
)


# ============================================================================
# BISHOP SCORE (Cervical Ripening)
# ============================================================================
BISHOP_DEFINITION = CalculatorDefinition(
    id="bishop",
    name="Bishop Score",
    short_name="Bishop",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.OBSTETRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts likelihood of successful labor induction",
    references=["Bishop EH. Obstet Gynecol 1964"],
    specialties=["Obstetrics", "Maternal-Fetal Medicine"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="dilation",
            display_name="Cervical Dilation",
            levels=[
                ("closed", 0, "Closed (0)"), ("1_2", 1, "1-2 cm (1)"),
                ("3_4", 2, "3-4 cm (2)"), ("5_plus", 3, "≥5 cm (3)"),
            ],
            description="Cervical dilation in cm",
        ),
        MultiLevelCriterion(
            name="effacement",
            display_name="Effacement",
            levels=[
                ("0_30", 0, "0-30% (0)"), ("40_50", 1, "40-50% (1)"),
                ("60_70", 2, "60-70% (2)"), ("80_plus", 3, "≥80% (3)"),
            ],
            description="Cervical effacement %",
        ),
        MultiLevelCriterion(
            name="station",
            display_name="Fetal Station",
            levels=[
                ("minus_3", 0, "-3 (0)"), ("minus_2", 1, "-2 (1)"),
                ("minus_1_0", 2, "-1 to 0 (2)"), ("plus_1_2", 3, "+1 to +2 (3)"),
            ],
            description="Fetal station",
        ),
        MultiLevelCriterion(
            name="consistency",
            display_name="Cervical Consistency",
            levels=[
                ("firm", 0, "Firm (0)"), ("medium", 1, "Medium (1)"), ("soft", 2, "Soft (2)"),
            ],
            description="Cervical consistency",
        ),
        MultiLevelCriterion(
            name="position",
            display_name="Cervical Position",
            levels=[
                ("posterior", 0, "Posterior (0)"), ("mid", 1, "Mid (1)"), ("anterior", 2, "Anterior (2)"),
            ],
            description="Cervical position",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=6, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Unfavorable cervix - induction may be prolonged",
            recommendations=["Consider cervical ripening agent", "Higher C-section risk if induced"]),
        ThresholdInterpretation(min_score=6, max_score=9, risk_level=RiskLevel.LOW,
            interpretation="Favorable cervix - good induction candidate",
            recommendations=["Oxytocin induction likely successful", "Lower C-section risk"]),
        ThresholdInterpretation(min_score=9, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Very favorable - high success rate",
            recommendations=["Excellent induction candidate", "May progress to spontaneous labor"]),
    ],
)


# ============================================================================
# PSI/PORT SCORE (Pneumonia Severity)
# ============================================================================
PSI_PORT_DEFINITION = CalculatorDefinition(
    id="psi_port",
    name="Pneumonia Severity Index (PSI/PORT)",
    short_name="PSI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Risk stratification for community-acquired pneumonia",
    references=["Fine MJ, et al. N Engl J Med 1997"],
    specialties=["Pulmonology", "Emergency Medicine", "Internal Medicine", "Hospitalist"],
    notes=["Class I-II: outpatient; Class III: observation; Class IV-V: inpatient"],
    threshold_criteria=[
        ThresholdCriterion(name="age", display_name="Age",
            thresholds=[("gte", 0, 0, "Age in years (male=age, female=age-10)")],
            description="Age points (male=age, female=age-10)"),
        ThresholdCriterion(name="respiratory_rate", display_name="RR ≥30",
            thresholds=[("gte", 30, 20, "RR ≥30")], unit="/min"),
        ThresholdCriterion(name="systolic_bp", display_name="SBP <90",
            thresholds=[("lt", 90, 20, "SBP <90")], unit="mmHg"),
        ThresholdCriterion(name="temperature", display_name="Temp <35 or ≥40",
            thresholds=[("lt", 35, 15, "<35°C"), ("gte", 40, 15, "≥40°C")], unit="°C"),
        ThresholdCriterion(name="pulse", display_name="HR ≥125",
            thresholds=[("gte", 125, 10, "HR ≥125")], unit="bpm"),
        ThresholdCriterion(name="ph", display_name="pH <7.35",
            thresholds=[("lt", 7.35, 30, "pH <7.35")]),
        ThresholdCriterion(name="bun", display_name="BUN ≥30",
            thresholds=[("gte", 30, 20, "BUN ≥30")], unit="mg/dL"),
        ThresholdCriterion(name="sodium", display_name="Na <130",
            thresholds=[("lt", 130, 20, "Na <130")], unit="mEq/L"),
        ThresholdCriterion(name="glucose", display_name="Glucose ≥250",
            thresholds=[("gte", 250, 10, "Glucose ≥250")], unit="mg/dL"),
        ThresholdCriterion(name="hematocrit", display_name="Hct <30%",
            thresholds=[("lt", 30, 10, "Hct <30%")], unit="%"),
        ThresholdCriterion(name="pao2", display_name="PaO2 <60 or SpO2 <90",
            thresholds=[("lt", 60, 10, "PaO2 <60")], unit="mmHg"),
    ],
    criteria=[
        ScoringCriterion("nursing_home", "Nursing home resident", 10, ""),
        ScoringCriterion("neoplastic", "Neoplastic disease", 30, ""),
        ScoringCriterion("liver_disease", "Liver disease", 20, ""),
        ScoringCriterion("chf", "CHF", 10, ""),
        ScoringCriterion("cerebrovascular", "Cerebrovascular disease", 10, ""),
        ScoringCriterion("renal_disease", "Renal disease", 10, ""),
        ScoringCriterion("altered_mental_status", "Altered mental status", 20, ""),
        ScoringCriterion("pleural_effusion", "Pleural effusion", 10, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=51, risk_level=RiskLevel.LOW,
            interpretation="Class I-II: Low risk (0.1-0.6% mortality)",
            recommendations=["Outpatient treatment appropriate", "Oral antibiotics"]),
        ThresholdInterpretation(min_score=51, max_score=71, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Class II: Low risk (0.6% mortality)",
            recommendations=["Outpatient treatment", "Consider brief observation"]),
        ThresholdInterpretation(min_score=71, max_score=91, risk_level=RiskLevel.MODERATE,
            interpretation="Class III: Moderate risk (0.9-2.8% mortality)",
            recommendations=["Consider observation unit", "Short hospitalization if needed"]),
        ThresholdInterpretation(min_score=91, max_score=131, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="Class IV: Moderate-high risk (8.2% mortality)",
            recommendations=["Inpatient admission", "IV antibiotics"]),
        ThresholdInterpretation(min_score=131, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Class V: High risk (29.2% mortality)",
            recommendations=["ICU consideration", "Aggressive treatment"]),
    ],
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="A prediction rule to identify low-risk patients with community-acquired pneumonia",
            authors=["Fine MJ", "Auble TE", "Yealy DM", "et al."],
            journal="New England Journal of Medicine",
            year=1997,
            volume="336",
            pages="243-250",
            pmid="8995086",
            doi="10.1056/NEJM199701233360402",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="Derived from 14,199 patients, validated in 38,039. IDSA/ATS recommended for CAP risk stratification. Classes I-II outpatient, III observation, IV-V inpatient.",
        clinical_pearls=[
            ClinicalPearl(
                text="Class I-II: Safe for outpatient treatment; Class III: Consider brief observation; Class IV-V: Hospitalize",
                category="interpretation",
            ),
            ClinicalPearl(
                text="PSI may underestimate severity in young patients with severe disease (favors age)",
                category="limitation",
            ),
            ClinicalPearl(
                text="Mental status is key - new confusion = 20 points, big impact on disposition",
                category="tip",
            ),
            ClinicalPearl(
                text="Consider social factors (homeless, no oral intake) even with low PSI",
                category="warning",
            ),
        ],
        pitfalls=[
            "Age-weighted - may underestimate risk in young patients",
            "Does not capture social factors affecting disposition",
            "Requires laboratory and imaging data not always available in office settings",
            "Complex scoring system - CURB-65 simpler alternative",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "Risk stratification of CAP in ED",
                "Deciding outpatient vs inpatient treatment",
                "Research settings",
            ],
            when_not_to_use=[
                "Healthcare-associated pneumonia",
                "Immunocompromised patients",
                "Office settings without labs (use CURB-65)",
            ],
            target_population="Adults with community-acquired pneumonia",
            excluded_populations=[
                "Immunocompromised patients",
                "HAP/VAP",
                "Aspiration pneumonia",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="IDSA/ATS CAP Guidelines",
                year=2019,
                organization="IDSA/ATS",
            ),
            GuidelineReference(
                guideline_name="NICE Pneumonia Guidelines",
                year=2019,
                organization="NICE",
            ),
        ],
        related_calculator_ids=["curb65", "smart_cop"],
        mdcalc_url="https://www.mdcalc.com/calc/33/psi-port-score-pneumonia-severity-index-cap",
    ),
)


# ============================================================================
# RANSON'S CRITERIA (Pancreatitis - Admission)
# ============================================================================
RANSON_ADMISSION_DEFINITION = CalculatorDefinition(
    id="ranson_admission",
    name="Ranson's Criteria (Admission)",
    short_name="Ranson",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Pancreatitis severity at admission (gallstone vs non-gallstone)",
    references=["Ranson JH, et al. Surg Gynecol Obstet 1974"],
    specialties=["Gastroenterology", "Surgery", "Critical Care"],
    notes=["At admission criteria; 48-hour criteria scored separately", "≥3 = severe pancreatitis"],
    threshold_criteria=[
        ThresholdCriterion(name="age", display_name="Age",
            thresholds=[("gt", 55, 1, "Age >55 (non-gallstone)"), ("gt", 70, 1, "Age >70 (gallstone)")]),
        ThresholdCriterion(name="wbc", display_name="WBC",
            thresholds=[("gt", 16, 1, "WBC >16,000 (non-gallstone)"), ("gt", 18, 1, "WBC >18,000 (gallstone)")],
            unit="×10³/µL"),
        ThresholdCriterion(name="glucose", display_name="Glucose",
            thresholds=[("gt", 200, 1, "Glucose >200 (non-gallstone)"), ("gt", 220, 1, "Glucose >220 (gallstone)")],
            unit="mg/dL"),
        ThresholdCriterion(name="ldh", display_name="LDH",
            thresholds=[("gt", 350, 1, "LDH >350 (non-gallstone)"), ("gt", 400, 1, "LDH >400 (gallstone)")],
            unit="U/L"),
        ThresholdCriterion(name="ast", display_name="AST",
            thresholds=[("gt", 250, 1, "AST >250")], unit="U/L"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="Mild pancreatitis (<1% mortality)",
            recommendations=["Supportive care", "NPO, IV fluids, pain control"]),
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate severity (10-20% mortality)",
            recommendations=["Close monitoring", "Consider ICU"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Severe pancreatitis (>40% mortality)",
            recommendations=["ICU admission", "Aggressive resuscitation"]),
    ],
)


# ============================================================================
# ASCVD RISK (Pooled Cohort Equations)
# ============================================================================
ASCVD_DEFINITION = CalculatorDefinition(
    id="ascvd",
    name="ASCVD Risk Estimator (PCE)",
    short_name="ASCVD",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.PERCENTAGE,
    score_unit="%",
    description="10-year atherosclerotic cardiovascular disease risk",
    references=["Goff DC, et al. Circulation 2014", "2018 ACC/AHA Cholesterol Guidelines"],
    specialties=["Cardiology", "Internal Medicine", "Primary Care"],
    notes=["Pooled Cohort Equations", "Validated for ages 40-79", "Race-specific coefficients"],
    formula=FormulaDefinition(
        formula_text="Pooled Cohort Equations (sex/race-specific)",
        output_unit="%",
        precision=1,
        parameters=[
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=40, max_value=79),
            FormulaParameter(name="total_cholesterol", display_name="Total Cholesterol", unit="mg/dL", min_value=130, max_value=320),
            FormulaParameter(name="hdl", display_name="HDL", unit="mg/dL", min_value=20, max_value=100),
            FormulaParameter(name="systolic_bp", display_name="Systolic BP", unit="mmHg", min_value=90, max_value=200),
            FormulaParameter(name="bp_treated", display_name="On BP meds", unit="", min_value=0, max_value=1),
            FormulaParameter(name="diabetes", display_name="Diabetes", unit="", min_value=0, max_value=1),
            FormulaParameter(name="smoker", display_name="Current smoker", unit="", min_value=0, max_value=1),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="Low risk (<5%)",
            recommendations=["Lifestyle modifications", "Statin generally not indicated"]),
        ThresholdInterpretation(min_score=5, max_score=7.5, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Borderline risk (5-7.5%)",
            recommendations=["Risk discussion", "Consider risk enhancers", "Statin may be reasonable"]),
        ThresholdInterpretation(min_score=7.5, max_score=20, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk (7.5-20%)",
            recommendations=["Moderate-intensity statin recommended", "CAC score may help decision"]),
        ThresholdInterpretation(min_score=20, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk (≥20%)",
            recommendations=["High-intensity statin indicated", "Aggressive risk factor modification"]),
    ],
)


# ============================================================================
# APACHE II SCORE (Simplified - key components)
# ============================================================================
APACHE_II_DEFINITION = CalculatorDefinition(
    id="apache_ii",
    name="APACHE II Score",
    short_name="APACHE II",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="ICU mortality prediction (Acute Physiology and Chronic Health)",
    references=["Knaus WA, et al. Crit Care Med 1985"],
    specialties=["Critical Care", "Emergency Medicine", "Anesthesiology"],
    notes=["Score 0-71", "Uses worst values in first 24h of ICU admission", "Chronic health points added"],
    multi_level_criteria=[
        MultiLevelCriterion(name="temperature", display_name="Temperature",
            levels=[
                ("41_plus", 4, "≥41°C (+4)"), ("39_40_9", 3, "39-40.9°C (+3)"), ("38_5_38_9", 1, "38.5-38.9°C (+1)"),
                ("36_38_4", 0, "36-38.4°C (0)"), ("34_35_9", 1, "34-35.9°C (+1)"), ("32_33_9", 2, "32-33.9°C (+2)"),
                ("30_31_9", 3, "30-31.9°C (+3)"), ("lt_30", 4, "<30°C (+4)"),
            ], description="Core temperature"),
        MultiLevelCriterion(name="map", display_name="Mean Arterial Pressure",
            levels=[
                ("gte_160", 4, "≥160 (+4)"), ("130_159", 3, "130-159 (+3)"), ("110_129", 2, "110-129 (+2)"),
                ("70_109", 0, "70-109 (0)"), ("50_69", 2, "50-69 (+2)"), ("lt_50", 4, "<50 (+4)"),
            ], description="MAP mmHg"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("gte_180", 4, "≥180 (+4)"), ("140_179", 3, "140-179 (+3)"), ("110_139", 2, "110-139 (+2)"),
                ("70_109", 0, "70-109 (0)"), ("55_69", 2, "55-69 (+2)"), ("40_54", 3, "40-54 (+3)"), ("lt_40", 4, "<40 (+4)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="respiratory_rate", display_name="Respiratory Rate",
            levels=[
                ("gte_50", 4, "≥50 (+4)"), ("35_49", 3, "35-49 (+3)"), ("25_34", 1, "25-34 (+1)"),
                ("12_24", 0, "12-24 (0)"), ("10_11", 1, "10-11 (+1)"), ("6_9", 2, "6-9 (+2)"), ("lt_6", 4, "<6 (+4)"),
            ], description="RR /min"),
        MultiLevelCriterion(name="gcs", display_name="GCS (15-GCS)",
            levels=[
                ("gcs_15", 0, "GCS 15 (0)"), ("gcs_13_14", 1, "GCS 13-14 (+1-2)"), ("gcs_10_12", 3, "GCS 10-12 (+3-5)"),
                ("gcs_7_9", 6, "GCS 7-9 (+6-8)"), ("gcs_4_6", 9, "GCS 4-6 (+9-11)"), ("gcs_3", 12, "GCS 3 (+12)"),
            ], description="Glasgow Coma Scale"),
    ],
    threshold_criteria=[
        ThresholdCriterion(name="age", display_name="Age points",
            thresholds=[
                ("lt", 45, 0, "<45 (0)"), ("range", (45, 54), 2, "45-54 (+2)"), ("range", (55, 64), 3, "55-64 (+3)"),
                ("range", (65, 74), 5, "65-74 (+5)"), ("gte", 75, 6, "≥75 (+6)"),
            ]),
    ],
    criteria=[
        ScoringCriterion("chronic_liver", "Severe chronic liver disease", 5, "Cirrhosis with portal HTN or encephalopathy"),
        ScoringCriterion("chronic_cvd", "Severe chronic CVD (NYHA IV)", 5, ""),
        ScoringCriterion("chronic_respiratory", "Severe chronic respiratory", 5, "COPD on home O2 or CO2 retention"),
        ScoringCriterion("chronic_renal", "Chronic renal failure on dialysis", 5, ""),
        ScoringCriterion("immunocompromised", "Immunocompromised", 5, "Chemo, radiation, steroids, leukemia, AIDS"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=10, risk_level=RiskLevel.LOW,
            interpretation="Low mortality risk (~5-10%)", recommendations=["Standard ICU care"]),
        ThresholdInterpretation(min_score=10, max_score=20, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate mortality risk (~15-25%)", recommendations=["Close monitoring", "Reassess daily"]),
        ThresholdInterpretation(min_score=20, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="High mortality risk (~40-55%)", recommendations=["Goals of care discussion", "Aggressive support"]),
        ThresholdInterpretation(min_score=30, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very high mortality risk (>70%)", recommendations=["Palliative care consultation", "Family meeting"]),
    ],
    provenance=CalculatorProvenance(
        original_citation=StructuredCitation(
            title="APACHE II: a severity of disease classification system",
            authors=["Knaus WA", "Draper EA", "Wagner DP", "Zimmerman JE"],
            journal="Critical Care Medicine",
            year=1985,
            volume="13",
            pages="818-829",
            pmid="3928249",
            is_original_derivation=True,
        ),
        evidence_level=EvidenceLevel.HIGH,
        evidence_summary="The most widely used ICU severity score globally. Validated in millions of patients over 40 years. Predicts hospital mortality based on acute physiology, age, and chronic health.",
        clinical_pearls=[
            ClinicalPearl(
                text="Calculate using worst values in first 24 hours of ICU admission",
                category="usage",
            ),
            ClinicalPearl(
                text="Score predicts hospital mortality risk, not individual patient outcomes",
                category="interpretation",
            ),
            ClinicalPearl(
                text="Chronic health points apply only if severe organ dysfunction existed BEFORE this admission",
                category="warning",
            ),
            ClinicalPearl(
                text="Use actual PaO2 if FiO2 >=0.5; otherwise use A-a gradient",
                category="tip",
            ),
        ],
        pitfalls=[
            "Not validated for repeated measurements (designed for admission scoring)",
            "May underestimate severity in patients who deteriorate after 24 hours",
            "GCS component problematic in sedated/paralyzed patients",
            "Lead-time bias can affect interpretation",
            "Chronic health definitions are subjective",
        ],
        usage_guidance=UsageGuidance(
            when_to_use=[
                "ICU admission severity assessment",
                "Research and benchmarking",
                "Prognostic discussions with families",
            ],
            when_not_to_use=[
                "Serial monitoring (use SOFA)",
                "Burn patients (use ABSI)",
                "Trauma (use TRISS)",
                "Deciding to withhold treatment",
            ],
            target_population="Adult ICU patients within first 24 hours of admission",
            excluded_populations=[
                "Burn patients",
                "Cardiac surgery patients",
                "Pediatric patients",
            ],
        ),
        related_guidelines=[
            GuidelineReference(
                guideline_name="SCCM ICU Admission Guidelines",
                year=2016,
                organization="SCCM",
            ),
        ],
        related_calculator_ids=["sofa", "apache_iv", "saps_ii"],
        mdcalc_url="https://www.mdcalc.com/calc/1868/apache-ii-score",
    ),
)


# ============================================================================
# GENEVA SCORE (REVISED) - Pulmonary Embolism
# ============================================================================
GENEVA_REVISED_DEFINITION = CalculatorDefinition(
    id="geneva_revised",
    name="Geneva Score (Revised) for Pulmonary Embolism",
    short_name="Geneva (Revised)",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Clinical probability assessment for pulmonary embolism",
    references=[
        "Le Gal G, et al. Ann Intern Med. 2006;144(3):165-171. PMID: 16461960",
        "Klok FA, et al. Arch Intern Med. 2008;168(19):2131-2136. PMID: 18955643",
    ],
    specialties=["Emergency Medicine", "Pulmonology", "Internal Medicine"],
    notes=[
        "Alternative to Wells PE score",
        "Simplified version assigns 1 point per criterion",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[("gt", 65, 1, "Age >65 years")],
            description="Age greater than 65 years",
        ),
        ThresholdCriterion(
            name="heart_rate",
            display_name="Heart Rate",
            thresholds=[
                ("gte", 95, 5, "HR ≥95 bpm"),
                ("range", (75, 94), 3, "HR 75-94 bpm"),
            ],
            unit="bpm",
            description="Heart rate",
        ),
    ],
    criteria=[
        ScoringCriterion("previous_dvt_pe", "Previous DVT or PE", 3,
                        "Previous objectively diagnosed DVT or PE"),
        ScoringCriterion("surgery_fracture_1mo", "Surgery or fracture within 1 month", 2,
                        "Surgery under general anesthesia or lower limb fracture within 1 month"),
        ScoringCriterion("active_malignancy", "Active malignancy", 2,
                        "Solid or hematologic, active or cured <1 year"),
        ScoringCriterion("unilateral_lower_limb_pain", "Unilateral lower limb pain", 3,
                        "Spontaneous unilateral lower limb pain"),
        ScoringCriterion("hemoptysis", "Hemoptysis", 2, "Hemoptysis"),
        ScoringCriterion("pain_on_palpation_edema", "Pain on palpation and unilateral edema", 4,
                        "Pain on deep vein palpation and unilateral edema"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=4,
            risk_level=RiskLevel.LOW,
            interpretation="Low clinical probability of PE (8% prevalence)",
            recommendations=[
                "Consider D-dimer testing",
                "If D-dimer negative, PE excluded",
                "If D-dimer positive, proceed to CT-PA",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=11,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate clinical probability of PE (28% prevalence)",
            recommendations=[
                "D-dimer testing recommended",
                "If D-dimer negative, PE excluded",
                "If D-dimer positive, CT-PA indicated",
            ],
        ),
        ThresholdInterpretation(
            min_score=11, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High clinical probability of PE (74% prevalence)",
            recommendations=[
                "CT-PA recommended (D-dimer not sufficient to exclude)",
                "Consider empiric anticoagulation while awaiting imaging",
                "If CT-PA inconclusive, consider V/Q scan or pulmonary angiography",
            ],
        ),
    ],
)


# ============================================================================
# GRACE SCORE - ACS Mortality Risk
# ============================================================================
GRACE_SCORE_DEFINITION = CalculatorDefinition(
    id="grace",
    name="GRACE Score for ACS",
    short_name="GRACE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts in-hospital and 6-month mortality in acute coronary syndrome",
    references=[
        "Fox KA, et al. BMJ. 2006;333(7578):1091. PMID: 17032691",
        "Granger CB, et al. Arch Intern Med. 2003;163(19):2345-2353. PMID: 14581255",
    ],
    specialties=["Cardiology", "Emergency Medicine", "Critical Care"],
    notes=[
        "GRACE 2.0 available for improved calibration",
        "Online calculator recommended for precise risk estimation",
        "Components: age, HR, SBP, creatinine, Killip class, cardiac arrest, ST deviation, elevated cardiac markers",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[
                ("gte", 90, 100, "Age ≥90"),
                ("range", (80, 89), 91, "Age 80-89"),
                ("range", (70, 79), 75, "Age 70-79"),
                ("range", (60, 69), 58, "Age 60-69"),
                ("range", (50, 59), 41, "Age 50-59"),
                ("range", (40, 49), 25, "Age 40-49"),
                ("lt", 40, 0, "Age <40"),
            ],
            description="Age in years",
        ),
        ThresholdCriterion(
            name="heart_rate",
            display_name="Heart Rate",
            thresholds=[
                ("gte", 200, 46, "HR ≥200"),
                ("range", (150, 199), 38, "HR 150-199"),
                ("range", (120, 149), 28, "HR 120-149"),
                ("range", (100, 119), 19, "HR 100-119"),
                ("range", (80, 99), 10, "HR 80-99"),
                ("range", (60, 79), 3, "HR 60-79"),
                ("lt", 60, 0, "HR <60"),
            ],
            unit="bpm",
            description="Heart rate at presentation",
        ),
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[
                ("lt", 80, 58, "SBP <80"),
                ("range", (80, 99), 53, "SBP 80-99"),
                ("range", (100, 119), 43, "SBP 100-119"),
                ("range", (120, 139), 34, "SBP 120-139"),
                ("range", (140, 159), 24, "SBP 140-159"),
                ("range", (160, 199), 10, "SBP 160-199"),
                ("gte", 200, 0, "SBP ≥200"),
            ],
            unit="mmHg",
            description="Systolic blood pressure at presentation",
        ),
        ThresholdCriterion(
            name="creatinine",
            display_name="Creatinine",
            thresholds=[
                ("gte", 4.0, 28, "Cr ≥4.0 mg/dL"),
                ("range", (3.0, 3.99), 23, "Cr 3.0-3.99"),
                ("range", (2.0, 2.99), 17, "Cr 2.0-2.99"),
                ("range", (1.5, 1.99), 13, "Cr 1.5-1.99"),
                ("range", (1.0, 1.49), 7, "Cr 1.0-1.49"),
                ("lt", 1.0, 1, "Cr <1.0"),
            ],
            unit="mg/dL",
            description="Serum creatinine",
        ),
        ThresholdCriterion(
            name="killip_class",
            display_name="Killip Class",
            thresholds=[
                ("eq", 4, 59, "Killip IV"),
                ("eq", 3, 39, "Killip III"),
                ("eq", 2, 20, "Killip II"),
                ("eq", 1, 0, "Killip I"),
            ],
            description="Killip class for heart failure",
        ),
    ],
    criteria=[
        ScoringCriterion("cardiac_arrest", "Cardiac arrest at admission", 39, "Resuscitated cardiac arrest at admission"),
        ScoringCriterion("st_deviation", "ST-segment deviation", 28, "ST depression or transient ST elevation"),
        ScoringCriterion("elevated_cardiac_markers", "Elevated cardiac markers", 14, "Elevated troponin or CK-MB"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=109,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - In-hospital mortality <1%",
            recommendations=[
                "Non-invasive risk stratification",
                "Consider early discharge if other factors favorable",
                "Optimal medical therapy",
            ],
        ),
        ThresholdInterpretation(
            min_score=109, max_score=140,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk - In-hospital mortality 1-3%",
            recommendations=[
                "Consider early invasive strategy within 72 hours",
                "Dual antiplatelet therapy",
                "Anticoagulation",
                "Cardiology consultation",
            ],
        ),
        ThresholdInterpretation(
            min_score=140, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk - In-hospital mortality >3%",
            recommendations=[
                "Early invasive strategy within 24 hours",
                "CCU admission",
                "Aggressive antiplatelet and anticoagulation",
                "Consider GP IIb/IIIa inhibitors",
            ],
        ),
    ],
)


# ============================================================================
# PADUA PREDICTION SCORE - VTE Risk in Medical Patients
# ============================================================================
PADUA_DEFINITION = CalculatorDefinition(
    id="padua",
    name="Padua Prediction Score for VTE Risk",
    short_name="Padua",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="VTE risk assessment in hospitalized medical patients",
    references=[
        "Barbar S, et al. J Thromb Haemost. 2010;8(11):2450-2457. PMID: 20738765",
    ],
    specialties=["Internal Medicine", "Hospitalist", "Hematology"],
    notes=[
        "Validated in acutely ill medical patients",
        "Score ≥4 indicates high risk requiring thromboprophylaxis",
    ],
    criteria=[
        ScoringCriterion("active_cancer", "Active cancer", 3,
                        "Local or distant metastases, chemo/radiation within 6 months"),
        ScoringCriterion("previous_vte", "Previous VTE", 3,
                        "Excluding superficial vein thrombosis"),
        ScoringCriterion("reduced_mobility", "Reduced mobility", 3,
                        "Bed rest with bathroom privileges ≥3 days"),
        ScoringCriterion("known_thrombophilia", "Known thrombophilic condition", 3,
                        "Antithrombin, protein C/S deficiency, Factor V Leiden, prothrombin mutation, antiphospholipid syndrome"),
        ScoringCriterion("recent_trauma_surgery", "Recent trauma or surgery", 2,
                        "Within 1 month"),
        ScoringCriterion("age_70_or_older", "Age ≥70 years", 1, ""),
        ScoringCriterion("heart_respiratory_failure", "Heart and/or respiratory failure", 1, ""),
        ScoringCriterion("ami_stroke", "Acute MI or ischemic stroke", 1, ""),
        ScoringCriterion("acute_infection_rheumatologic", "Acute infection and/or rheumatologic disorder", 1, ""),
        ScoringCriterion("obesity_bmi_30", "Obesity (BMI ≥30)", 1, ""),
        ScoringCriterion("hormonal_treatment", "Ongoing hormonal treatment", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=4,
            risk_level=RiskLevel.LOW,
            interpretation="Low VTE risk (0.3% 90-day VTE rate)",
            recommendations=[
                "Pharmacologic prophylaxis generally not indicated",
                "Early ambulation encouraged",
                "Reassess if clinical status changes",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High VTE risk (11% 90-day VTE rate without prophylaxis)",
            recommendations=[
                "Pharmacologic thromboprophylaxis recommended",
                "LMWH, fondaparinux, or UFH",
                "Continue until mobility restored or discharge",
                "Consider extended prophylaxis if persistent risk factors",
            ],
        ),
    ],
)


# ============================================================================
# IMPROVE VTE RISK SCORE - Hospitalized Medical Patients
# ============================================================================
IMPROVE_VTE_DEFINITION = CalculatorDefinition(
    id="improve_vte",
    name="IMPROVE VTE Risk Score",
    short_name="IMPROVE VTE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="VTE risk assessment in hospitalized acutely ill medical patients",
    references=[
        "Spyropoulos AC, et al. J Thromb Haemost. 2011;9(11):2174-2181. PMID: 21848698",
    ],
    specialties=["Internal Medicine", "Hospitalist", "Hematology"],
    criteria=[
        ScoringCriterion("previous_vte", "Previous VTE", 3, ""),
        ScoringCriterion("known_thrombophilia", "Known thrombophilia", 2, ""),
        ScoringCriterion("lower_limb_paralysis", "Current lower limb paralysis", 2, ""),
        ScoringCriterion("active_cancer", "Active cancer", 2, ""),
        ScoringCriterion("icu_ccu_stay", "ICU/CCU stay", 1, ""),
        ScoringCriterion("bed_rest_7_days", "Complete bed rest ≥7 days", 1, ""),
        ScoringCriterion("age_60_or_older", "Age ≥60 years", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low VTE risk (~0.5%)",
            recommendations=[
                "Mechanical prophylaxis if any VTE risk factors",
                "Early mobilization",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=4,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate VTE risk (~1.5%)",
            recommendations=[
                "Consider pharmacologic prophylaxis",
                "Balance against bleeding risk (IMPROVE Bleeding Score)",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High VTE risk (~4%)",
            recommendations=[
                "Pharmacologic prophylaxis recommended",
                "Assess bleeding risk before starting",
            ],
        ),
    ],
)


# ============================================================================
# CRUSADE BLEEDING SCORE - ACS Patients
# ============================================================================
CRUSADE_DEFINITION = CalculatorDefinition(
    id="crusade",
    name="CRUSADE Bleeding Score",
    short_name="CRUSADE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="In-hospital major bleeding risk for ACS patients",
    references=[
        "Subherwal S, et al. Circulation. 2009;119(14):1873-1882. PMID: 19332461",
    ],
    specialties=["Cardiology", "Emergency Medicine"],
    notes=[
        "Developed from CRUSADE registry",
        "Useful for balancing anticoagulation intensity vs bleeding risk in NSTEMI",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="hematocrit",
            display_name="Baseline Hematocrit",
            thresholds=[
                ("lt", 31, 9, "Hct <31%"),
                ("range", (31, 33.9), 7, "Hct 31-33.9%"),
                ("range", (34, 36.9), 3, "Hct 34-36.9%"),
                ("range", (37, 39.9), 2, "Hct 37-39.9%"),
                ("gte", 40, 0, "Hct ≥40%"),
            ],
            unit="%",
            description="Baseline hematocrit",
        ),
        ThresholdCriterion(
            name="creatinine_clearance",
            display_name="Creatinine Clearance",
            thresholds=[
                ("lt", 15, 39, "CrCl <15"),
                ("range", (15, 30), 35, "CrCl 15-30"),
                ("range", (30, 60), 28, "CrCl 30-60"),
                ("range", (60, 90), 17, "CrCl 60-90"),
                ("range", (90, 120), 7, "CrCl 90-120"),
                ("gte", 120, 0, "CrCl ≥120"),
            ],
            unit="mL/min",
            description="Creatinine clearance (Cockcroft-Gault)",
        ),
        ThresholdCriterion(
            name="heart_rate",
            display_name="Heart Rate",
            thresholds=[
                ("gte", 121, 11, "HR ≥121"),
                ("range", (111, 120), 10, "HR 111-120"),
                ("range", (101, 110), 8, "HR 101-110"),
                ("range", (91, 100), 6, "HR 91-100"),
                ("range", (81, 90), 4, "HR 81-90"),
                ("range", (71, 80), 1, "HR 71-80"),
                ("lte", 70, 0, "HR ≤70"),
            ],
            unit="bpm",
            description="Heart rate at presentation",
        ),
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[
                ("lte", 90, 10, "SBP ≤90"),
                ("range", (91, 100), 8, "SBP 91-100"),
                ("range", (101, 120), 5, "SBP 101-120"),
                ("range", (121, 180), 1, "SBP 121-180"),
                ("range", (181, 200), 3, "SBP 181-200"),
                ("gt", 200, 5, "SBP >200"),
            ],
            unit="mmHg",
            description="Systolic blood pressure",
        ),
    ],
    criteria=[
        ScoringCriterion("female", "Female sex", 8, ""),
        ScoringCriterion("signs_of_chf", "Signs of CHF at presentation", 7, ""),
        ScoringCriterion("prior_vascular_disease", "Prior vascular disease", 6, "History of PAD or stroke"),
        ScoringCriterion("diabetes", "Diabetes mellitus", 6, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=21,
            risk_level=RiskLevel.LOW,
            interpretation="Very low bleeding risk (3.1%)",
            recommendations=["Standard antithrombotic therapy"],
        ),
        ThresholdInterpretation(
            min_score=21, max_score=31,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low bleeding risk (5.5%)",
            recommendations=["Standard antithrombotic therapy"],
        ),
        ThresholdInterpretation(
            min_score=31, max_score=41,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate bleeding risk (8.6%)",
            recommendations=[
                "Consider dose adjustment of antithrombotics",
                "Radial access for PCI preferred",
            ],
        ),
        ThresholdInterpretation(
            min_score=41, max_score=51,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="High bleeding risk (11.9%)",
            recommendations=[
                "Careful antithrombotic selection",
                "Consider shorter duration DAPT",
                "Radial access strongly preferred",
            ],
        ),
        ThresholdInterpretation(
            min_score=51, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Very high bleeding risk (19.5%)",
            recommendations=[
                "Minimize antithrombotic intensity where possible",
                "Avoid GP IIb/IIIa inhibitors if possible",
                "Careful procedural planning",
            ],
        ),
    ],
)


# ============================================================================
# ATRIA BLEEDING RISK SCORE
# ============================================================================
ATRIA_BLEEDING_DEFINITION = CalculatorDefinition(
    id="atria_bleeding",
    name="ATRIA Bleeding Risk Score",
    short_name="ATRIA Bleed",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Bleeding risk for patients with atrial fibrillation on anticoagulation",
    references=[
        "Fang MC, et al. J Am Coll Cardiol. 2011;58(4):395-401. PMID: 21757117",
    ],
    specialties=["Cardiology", "Internal Medicine", "Hematology"],
    criteria=[
        ScoringCriterion("anemia", "Anemia", 3, "Hgb <13 g/dL male, <12 g/dL female"),
        ScoringCriterion("severe_renal_disease", "Severe renal disease", 3, "GFR <30 or on dialysis"),
        ScoringCriterion("age_75_or_older", "Age ≥75 years", 2, ""),
        ScoringCriterion("prior_bleeding", "Prior hemorrhage", 1, "Any prior bleeding diagnosis"),
        ScoringCriterion("hypertension", "Hypertension", 1, "History of hypertension"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=4,
            risk_level=RiskLevel.LOW,
            interpretation="Low bleeding risk (0.8%/year)",
            recommendations=[
                "Anticoagulation generally safe",
                "Standard monitoring",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=5,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate bleeding risk (2.6%/year)",
            recommendations=[
                "Anticoagulation can be considered",
                "Address modifiable risk factors",
                "Consider DOAC over warfarin",
            ],
        ),
        ThresholdInterpretation(
            min_score=5, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High bleeding risk (5.8%/year)",
            recommendations=[
                "Weigh stroke vs bleeding risk carefully",
                "Address all modifiable risk factors",
                "Close monitoring if anticoagulated",
            ],
        ),
    ],
)


# ============================================================================
# HEMORR2HAGES SCORE - Bleeding Risk in AF
# ============================================================================
HEMORR2HAGES_DEFINITION = CalculatorDefinition(
    id="hemorr2hages",
    name="HEMORR2HAGES Bleeding Risk Score",
    short_name="HEMORR2HAGES",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Bleeding risk assessment for patients with AF on anticoagulation",
    references=[
        "Gage BF, et al. Am Heart J. 2006;151(3):713-719. PMID: 16504638",
    ],
    specialties=["Cardiology", "Internal Medicine", "Hematology"],
    notes=[
        "Mnemonic: Hepatic/renal, Ethanol, Malignancy, Older, Reduced platelets, Re-bleeding risk, Hypertension, Anemia, Genetic, Excessive fall risk, Stroke",
    ],
    criteria=[
        ScoringCriterion("hepatic_renal", "Hepatic or renal disease", 1, ""),
        ScoringCriterion("ethanol_abuse", "Ethanol abuse", 1, ""),
        ScoringCriterion("malignancy", "Malignancy", 1, ""),
        ScoringCriterion("older_75", "Age >75", 1, ""),
        ScoringCriterion("reduced_platelets", "Reduced platelet count or function", 1, ""),
        ScoringCriterion("rebleeding_risk", "Re-bleeding risk (prior bleed)", 2, "History of prior bleeding"),
        ScoringCriterion("hypertension_uncontrolled", "Hypertension (uncontrolled)", 1, ""),
        ScoringCriterion("anemia", "Anemia", 1, ""),
        ScoringCriterion("genetic_factors", "Genetic factors (CYP2C9)", 1, "CYP2C9 polymorphism"),
        ScoringCriterion("excessive_fall_risk", "Excessive fall risk", 1, ""),
        ScoringCriterion("stroke_history", "Stroke history", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low bleeding risk (1.9%/year)",
            recommendations=["Anticoagulation generally safe"],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=4,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate bleeding risk (3.4%/year)",
            recommendations=[
                "Balance stroke vs bleeding risk",
                "Consider DOAC over warfarin",
            ],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High bleeding risk (8.7%/year)",
            recommendations=[
                "High bleeding risk on anticoagulation",
                "Careful risk-benefit discussion",
                "Address modifiable factors",
            ],
        ),
    ],
)


# ============================================================================
# DUKE TREADMILL SCORE
# ============================================================================
DUKE_TREADMILL_DEFINITION = CalculatorDefinition(
    id="duke_treadmill",
    name="Duke Treadmill Score",
    short_name="Duke Treadmill",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Risk stratification using exercise stress test results",
    references=[
        "Mark DB, et al. N Engl J Med. 1991;325(12):849-853. PMID: 1875969",
    ],
    specialties=["Cardiology", "Internal Medicine"],
    notes=[
        "Formula: Exercise time (min) - (5 × max ST deviation mm) - (4 × angina index)",
        "Angina index: 0 = none, 1 = non-limiting, 2 = exercise-limiting",
    ],
    formula=FormulaDefinition(
        formula_text="Exercise time - (5 × ST deviation) - (4 × angina index)",
        output_unit="points",
        precision=0,
        parameters=[
            FormulaParameter(
                name="exercise_time",
                display_name="Exercise Time",
                unit="minutes",
                min_value=0,
                max_value=30,
                description="Total exercise time in minutes on Bruce protocol",
            ),
            FormulaParameter(
                name="st_deviation",
                display_name="Max ST Deviation",
                unit="mm",
                min_value=0,
                max_value=10,
                description="Maximum ST segment deviation during or after exercise",
            ),
            FormulaParameter(
                name="angina_index",
                display_name="Angina Index",
                unit="",
                min_value=0,
                max_value=2,
                description="0 = none, 1 = non-limiting angina, 2 = exercise-limiting angina",
            ),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=5, max_score=None,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk (annual mortality 0.25%)",
            recommendations=[
                "Medical management appropriate",
                "Annual cardiac mortality <1%",
                "Coronary angiography not routinely needed",
            ],
        ),
        ThresholdInterpretation(
            min_score=-10, max_score=5,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk (annual mortality 1.25%)",
            recommendations=[
                "Consider additional testing (stress imaging)",
                "Risk factor modification",
                "May need coronary angiography based on symptoms",
            ],
        ),
        ThresholdInterpretation(
            min_score=None, max_score=-10,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk (annual mortality 5.25%)",
            recommendations=[
                "Coronary angiography recommended",
                "High likelihood of severe/multivessel CAD",
                "Consider revascularization",
            ],
        ),
    ],
)


# ============================================================================
# MAGGIC HEART FAILURE RISK SCORE
# ============================================================================
MAGGIC_DEFINITION = CalculatorDefinition(
    id="maggic",
    name="MAGGIC Risk Calculator for Heart Failure",
    short_name="MAGGIC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="1-year and 3-year mortality risk in heart failure",
    references=[
        "Pocock SJ, et al. Eur Heart J. 2013;34(19):1404-1413. PMID: 23095984",
    ],
    specialties=["Cardiology", "Internal Medicine"],
    notes=[
        "Meta-Analysis Global Group in Chronic Heart Failure",
        "Validated in both HFrEF and HFpEF",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[
                ("lt", 55, 0, "Age <55"),
                ("range", (55, 59), 1, "Age 55-59"),
                ("range", (60, 64), 2, "Age 60-64"),
                ("range", (65, 69), 4, "Age 65-69"),
                ("range", (70, 74), 6, "Age 70-74"),
                ("range", (75, 79), 8, "Age 75-79"),
                ("gte", 80, 10, "Age ≥80"),
            ],
            description="Age in years",
        ),
        ThresholdCriterion(
            name="ejection_fraction",
            display_name="Ejection Fraction",
            thresholds=[
                ("lt", 20, 7, "EF <20%"),
                ("range", (20, 24), 6, "EF 20-24%"),
                ("range", (25, 29), 5, "EF 25-29%"),
                ("range", (30, 34), 3, "EF 30-34%"),
                ("range", (35, 39), 2, "EF 35-39%"),
                ("gte", 40, 0, "EF ≥40%"),
            ],
            unit="%",
            description="Left ventricular ejection fraction",
        ),
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[
                ("lt", 110, 5, "SBP <110"),
                ("range", (110, 119), 4, "SBP 110-119"),
                ("range", (120, 129), 3, "SBP 120-129"),
                ("range", (130, 139), 2, "SBP 130-139"),
                ("range", (140, 149), 1, "SBP 140-149"),
                ("gte", 150, 0, "SBP ≥150"),
            ],
            unit="mmHg",
            description="Systolic blood pressure",
        ),
        ThresholdCriterion(
            name="bmi",
            display_name="BMI",
            thresholds=[
                ("lt", 15, 6, "BMI <15"),
                ("range", (15, 19), 5, "BMI 15-19"),
                ("range", (20, 24), 3, "BMI 20-24"),
                ("range", (25, 29), 2, "BMI 25-29"),
                ("gte", 30, 0, "BMI ≥30"),
            ],
            unit="kg/m²",
            description="Body mass index",
        ),
        ThresholdCriterion(
            name="creatinine",
            display_name="Creatinine",
            thresholds=[
                ("lt", 0.9, 0, "Cr <0.9"),
                ("range", (0.9, 1.09), 1, "Cr 0.9-1.09"),
                ("range", (1.1, 1.29), 2, "Cr 1.1-1.29"),
                ("range", (1.3, 1.49), 3, "Cr 1.3-1.49"),
                ("range", (1.5, 1.69), 4, "Cr 1.5-1.69"),
                ("range", (1.7, 1.89), 5, "Cr 1.7-1.89"),
                ("gte", 1.9, 6, "Cr ≥1.9"),
            ],
            unit="mg/dL",
            description="Serum creatinine",
        ),
        ThresholdCriterion(
            name="nyha_class",
            display_name="NYHA Class",
            thresholds=[
                ("eq", 1, 0, "NYHA I"),
                ("eq", 2, 2, "NYHA II"),
                ("eq", 3, 6, "NYHA III"),
                ("eq", 4, 8, "NYHA IV"),
            ],
            description="NYHA functional class",
        ),
    ],
    criteria=[
        ScoringCriterion("male", "Male sex", 1, ""),
        ScoringCriterion("current_smoker", "Current smoker", 1, ""),
        ScoringCriterion("diabetes", "Diabetes", 3, ""),
        ScoringCriterion("copd", "COPD", 2, ""),
        ScoringCriterion("first_hf_diagnosis_18mo", "HF diagnosed ≤18 months ago", 2, ""),
        ScoringCriterion("not_on_beta_blocker", "Not on beta-blocker", 3, ""),
        ScoringCriterion("not_on_ace_arb", "Not on ACE-I or ARB", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=15,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - 1-year mortality ~5%",
            recommendations=["Optimize guideline-directed medical therapy"],
        ),
        ThresholdInterpretation(
            min_score=15, max_score=25,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk - 1-year mortality ~15%",
            recommendations=[
                "Ensure on all indicated therapies",
                "Consider device therapy evaluation",
            ],
        ),
        ThresholdInterpretation(
            min_score=25, max_score=35,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="High risk - 1-year mortality ~25%",
            recommendations=[
                "Advanced HF referral",
                "ICD/CRT evaluation if appropriate",
                "Goals of care discussion",
            ],
        ),
        ThresholdInterpretation(
            min_score=35, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Very high risk - 1-year mortality >40%",
            recommendations=[
                "Advanced therapies evaluation (LVAD, transplant)",
                "Palliative care consultation",
                "Goals of care discussion",
            ],
        ),
    ],
)


# ============================================================================
# DASH SCORE - VTE Recurrence
# ============================================================================
DASH_DEFINITION = CalculatorDefinition(
    id="dash",
    name="DASH Score for VTE Recurrence",
    short_name="DASH",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Risk of VTE recurrence after stopping anticoagulation for unprovoked VTE",
    references=[
        "Tosetto A, et al. J Thromb Haemost. 2012;10(6):1019-1025. PMID: 22489957",
    ],
    specialties=["Hematology", "Internal Medicine", "Vascular Medicine"],
    notes=[
        "For patients with first unprovoked VTE",
        "D-dimer measured 1 month after stopping anticoagulation",
    ],
    criteria=[
        ScoringCriterion("abnormal_d_dimer", "Abnormal D-dimer after stopping anticoagulation", 2, "D-dimer positive at 1 month"),
        ScoringCriterion("age_under_50", "Age ≤50", 1, ""),
        ScoringCriterion("male", "Male sex", 1, ""),
        ScoringCriterion("hormone_use_at_vte", "Hormone use at time of index VTE (women)", -2, "Oral contraceptives or HRT"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=-2, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low recurrence risk (3.1%/year)",
            recommendations=[
                "May consider stopping anticoagulation",
                "Annual recurrence risk ~3%",
                "Patient education on VTE symptoms",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=2,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate recurrence risk (6.4%/year)",
            recommendations=[
                "Individualized decision on anticoagulation duration",
                "Discuss risks and benefits with patient",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High recurrence risk (12.3%/year)",
            recommendations=[
                "Consider extended/indefinite anticoagulation",
                "Annual recurrence risk >10%",
            ],
        ),
    ],
)


# ============================================================================
# HERDOO2 RULE - VTE Recurrence in Women
# ============================================================================
HERDOO2_DEFINITION = CalculatorDefinition(
    id="herdoo2",
    name="HERDOO2 Rule for VTE Recurrence",
    short_name="HERDOO2",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies women at low risk of VTE recurrence who can safely stop anticoagulation",
    references=[
        "Rodger MA, et al. BMJ. 2017;356:j1065. PMID: 28314711",
    ],
    specialties=["Hematology", "Internal Medicine", "Vascular Medicine"],
    notes=[
        "Only validated in women with first unprovoked VTE",
        "HER: Hyperpigmentation, Edema, Redness of leg DOO: D-dimer, Obesity, Older",
    ],
    criteria=[
        ScoringCriterion("hyperpigmentation_edema_redness", "Post-thrombotic signs (HER)", 1,
                        "Hyperpigmentation, edema, or redness of either leg"),
        ScoringCriterion("d_dimer_250_or_more", "D-dimer ≥250 µg/L", 1,
                        "D-dimer on anticoagulation"),
        ScoringCriterion("bmi_30_or_more", "BMI ≥30 kg/m²", 1, "Obesity"),
        ScoringCriterion("age_65_or_older", "Age ≥65 years", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low recurrence risk - can stop anticoagulation",
            recommendations=[
                "Annual recurrence risk ~3% if all criteria absent",
                "Safe to discontinue anticoagulation",
                "Patient education on VTE symptoms",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Not low risk - continue anticoagulation",
            recommendations=[
                "Consider extended anticoagulation",
                "Discuss risks and benefits",
            ],
        ),
    ],
)


# ============================================================================
# VIENNA PREDICTION MODEL - VTE Recurrence
# ============================================================================
VIENNA_VTE_DEFINITION = CalculatorDefinition(
    id="vienna_vte",
    name="Vienna Prediction Model for VTE Recurrence",
    short_name="Vienna VTE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.DECIMAL,
    score_unit="%",
    description="Predicts VTE recurrence risk based on location, sex, and D-dimer",
    references=[
        "Eichinger S, et al. Circulation. 2010;121(14):1630-1636. PMID: 20351233",
    ],
    specialties=["Hematology", "Internal Medicine", "Vascular Medicine"],
    notes=[
        "Uses nomogram; this is a simplified point-based approximation",
        "D-dimer measured 3 weeks after stopping anticoagulation",
    ],
    criteria=[
        ScoringCriterion("male", "Male sex", 2, "Higher recurrence risk in males"),
        ScoringCriterion("proximal_dvt_pe", "Proximal DVT or PE", 1, "vs. distal DVT"),
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="d_dimer",
            display_name="D-dimer",
            thresholds=[
                ("lt", 250, 0, "D-dimer <250"),
                ("range", (250, 500), 1, "D-dimer 250-500"),
                ("range", (500, 750), 2, "D-dimer 500-750"),
                ("gte", 750, 3, "D-dimer ≥750"),
            ],
            unit="µg/L",
            description="D-dimer 3 weeks after stopping anticoagulation",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Lower recurrence risk (<5%/year)",
            recommendations=["May consider stopping anticoagulation"],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=4,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate recurrence risk (5-10%/year)",
            recommendations=["Individualized decision on anticoagulation"],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High recurrence risk (>10%/year)",
            recommendations=["Consider extended anticoagulation"],
        ),
    ],
)


# ============================================================================
# PRECISE-DAPT SCORE - Bleeding Risk with DAPT
# ============================================================================
PRECISE_DAPT_DEFINITION = CalculatorDefinition(
    id="precise_dapt",
    name="PRECISE-DAPT Score",
    short_name="PRECISE-DAPT",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Bleeding risk to guide dual antiplatelet therapy duration after PCI",
    references=[
        "Costa F, et al. Lancet. 2017;389(10073):1025-1034. PMID: 28290994",
    ],
    specialties=["Cardiology", "Interventional Cardiology"],
    notes=[
        "Predicts TIMI major/minor bleeding during DAPT",
        "Helps decide between short (3-6 mo) vs standard/prolonged (12-24 mo) DAPT",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[
                ("gte", 85, 9, "Age ≥85"),
                ("range", (75, 84), 7, "Age 75-84"),
                ("range", (65, 74), 5, "Age 65-74"),
                ("range", (55, 64), 3, "Age 55-64"),
                ("lt", 55, 0, "Age <55"),
            ],
            description="Age in years",
        ),
        ThresholdCriterion(
            name="creatinine_clearance",
            display_name="Creatinine Clearance",
            thresholds=[
                ("lt", 30, 8, "CrCl <30"),
                ("range", (30, 59), 5, "CrCl 30-59"),
                ("range", (60, 89), 2, "CrCl 60-89"),
                ("gte", 90, 0, "CrCl ≥90"),
            ],
            unit="mL/min",
            description="Creatinine clearance",
        ),
        ThresholdCriterion(
            name="hemoglobin",
            display_name="Hemoglobin",
            thresholds=[
                ("lt", 10, 5, "Hgb <10"),
                ("range", (10, 11.9), 3, "Hgb 10-11.9"),
                ("range", (12, 13.9), 1, "Hgb 12-13.9"),
                ("gte", 14, 0, "Hgb ≥14"),
            ],
            unit="g/dL",
            description="Hemoglobin",
        ),
        ThresholdCriterion(
            name="wbc",
            display_name="WBC",
            thresholds=[
                ("gte", 15, 3, "WBC ≥15"),
                ("range", (10, 14.9), 2, "WBC 10-14.9"),
                ("lt", 10, 0, "WBC <10"),
            ],
            unit="×10⁹/L",
            description="White blood cell count",
        ),
    ],
    criteria=[
        ScoringCriterion("prior_bleeding", "Prior spontaneous bleeding", 4, "Prior bleeding requiring transfusion or hospitalization"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=17,
            risk_level=RiskLevel.LOW,
            interpretation="Low bleeding risk",
            recommendations=[
                "Standard or prolonged DAPT (12+ months) likely beneficial",
                "Ischemic benefit outweighs bleeding risk",
            ],
        ),
        ThresholdInterpretation(
            min_score=17, max_score=25,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate bleeding risk",
            recommendations=[
                "Individualize DAPT duration",
                "Consider 6-12 months based on ischemic risk",
            ],
        ),
        ThresholdInterpretation(
            min_score=25, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High bleeding risk",
            recommendations=[
                "Shorter DAPT duration (3-6 months) may be preferred",
                "Bleeding risk may outweigh prolonged DAPT benefit",
            ],
        ),
    ],
)


# ============================================================================
# DAPT SCORE - Duration of Dual Antiplatelet Therapy
# ============================================================================
DAPT_SCORE_DEFINITION = CalculatorDefinition(
    id="dapt_score",
    name="DAPT Score",
    short_name="DAPT Score",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts benefit of continuing DAPT beyond 12 months after PCI",
    references=[
        "Yeh RW, et al. JAMA. 2016;315(16):1735-1749. PMID: 27022822",
    ],
    specialties=["Cardiology", "Interventional Cardiology"],
    notes=[
        "Applied at 12 months post-PCI without events",
        "Score ≥2: prolonged DAPT (30 months) beneficial",
        "Score <2: may stop DAPT at 12 months",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[
                ("lt", 65, 0, "Age <65 (0)"),
                ("range", (65, 74), -1, "Age 65-74 (-1)"),
                ("gte", 75, -2, "Age ≥75 (-2)"),
            ],
            description="Age (younger favors longer DAPT)",
        ),
        ThresholdCriterion(
            name="stent_diameter",
            display_name="Stent Diameter",
            thresholds=[
                ("lt", 3.0, 1, "Stent <3mm (+1)"),
            ],
            unit="mm",
            description="Smallest stent diameter",
        ),
    ],
    criteria=[
        ScoringCriterion("current_smoker", "Current cigarette smoker", 1, ""),
        ScoringCriterion("diabetes", "Diabetes mellitus", 1, ""),
        ScoringCriterion("mi_at_presentation", "MI at presentation", 1, "Index event was MI"),
        ScoringCriterion("prior_pci_mi", "Prior PCI or prior MI", 1, "Before index event"),
        ScoringCriterion("paclitaxel_stent", "Paclitaxel-eluting stent", 1, ""),
        ScoringCriterion("chf_ef_under_30", "CHF or LVEF <30%", 2, ""),
        ScoringCriterion("saphenous_vein_graft", "Saphenous vein graft PCI", 2, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=-2, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low score - may stop DAPT at 12 months",
            recommendations=[
                "Bleeding risk likely outweighs ischemic benefit",
                "Consider aspirin monotherapy after 12 months",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High score - prolonged DAPT beneficial",
            recommendations=[
                "Continue DAPT for 30 months total",
                "Net clinical benefit favors longer DAPT",
                "Reassess bleeding risk periodically",
            ],
        ),
    ],
)


# ============================================================================
# ORBIT BLEEDING SCORE - AF Anticoagulation
# ============================================================================
ORBIT_BLEEDING_DEFINITION = CalculatorDefinition(
    id="orbit_bleeding",
    name="ORBIT Bleeding Risk Score",
    short_name="ORBIT",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Bleeding risk for patients with AF on oral anticoagulation",
    references=[
        "O'Brien EC, et al. Am Heart J. 2015;169(6):747-753. PMID: 26027610",
    ],
    specialties=["Cardiology", "Internal Medicine", "Hematology"],
    notes=[
        "Derived from ORBIT-AF registry",
        "Validated in patients on warfarin and DOACs",
    ],
    criteria=[
        ScoringCriterion("older_74", "Age >74 years", 1, ""),
        ScoringCriterion("reduced_hgb_hct", "Reduced hemoglobin/hematocrit/anemia", 2,
                        "Hgb <13 male/<12 female, or Hct <40% male/<36% female"),
        ScoringCriterion("bleeding_history", "Bleeding history", 2,
                        "GI bleeding or intracranial bleeding"),
        ScoringCriterion("insufficient_kidney", "Insufficient kidney function", 1,
                        "GFR <60 mL/min/1.73m²"),
        ScoringCriterion("antiplatelet_use", "Treatment with antiplatelet", 2, "Aspirin, clopidogrel, etc."),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=3,
            risk_level=RiskLevel.LOW,
            interpretation="Low bleeding risk (2.4%/year)",
            recommendations=["Anticoagulation generally safe"],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=5,
            risk_level=RiskLevel.MODERATE,
            interpretation="Medium bleeding risk (4.7%/year)",
            recommendations=[
                "Balance stroke vs bleeding",
                "Address modifiable risk factors",
            ],
        ),
        ThresholdInterpretation(
            min_score=5, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High bleeding risk (8.6%/year)",
            recommendations=[
                "Careful risk-benefit discussion",
                "Consider avoiding antiplatelet if possible",
            ],
        ),
    ],
)


# ============================================================================
# CANADIAN SYNCOPE RISK SCORE
# ============================================================================
CANADIAN_SYNCOPE_DEFINITION = CalculatorDefinition(
    id="canadian_syncope",
    name="Canadian Syncope Risk Score",
    short_name="Canadian Syncope",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="30-day serious adverse event risk after ED evaluation for syncope",
    references=[
        "Thiruganasambandamoorthy V, et al. CMAJ. 2016;188(12):E289-E298. PMID: 27378464",
    ],
    specialties=["Emergency Medicine", "Cardiology", "Internal Medicine"],
    notes=[
        "Applied after ED workup (ECG, basic labs)",
        "Predicts: death, MI, arrhythmia, PE, SAH, significant hemorrhage, intervention",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[
                ("lt", 90, 2, "SBP <90"),
                ("range", (90, 110), 1, "SBP 90-110"),
            ],
            unit="mmHg",
            description="ED systolic blood pressure",
        ),
    ],
    criteria=[
        ScoringCriterion("vasovagal_predisposition", "Predisposition to vasovagal syncope", -1,
                        "Warm/crowded place, prolonged standing, fear, emotion, pain (negative points)"),
        ScoringCriterion("heart_disease_history", "Heart disease history", 1,
                        "CAD, atrial fibrillation, CHF, valvular disease"),
        ScoringCriterion("elevated_troponin", "Elevated troponin", 2, ">99th percentile"),
        ScoringCriterion("abnormal_qrs_axis", "Abnormal QRS axis", 1, "<-30° or >100°"),
        ScoringCriterion("qrs_duration_130", "QRS >130 ms", 1, ""),
        ScoringCriterion("qt_480_corrected", "Corrected QT >480 ms", 2, ""),
        ScoringCriterion("ed_diagnosis_vasovagal", "ED diagnosis of vasovagal syncope", -2,
                        "Clinical diagnosis of vasovagal mechanism (negative points)"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=-3, max_score=0,
            risk_level=RiskLevel.LOW,
            interpretation="Very low risk (0.4%)",
            recommendations=[
                "Discharge appropriate",
                "Outpatient follow-up",
            ],
        ),
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low risk (1.2%)",
            recommendations=[
                "Consider discharge with close follow-up",
                "Return precautions",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Medium risk (3.1%)",
            recommendations=[
                "Consider observation or admission",
                "Cardiac monitoring",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=5,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="High risk (7.5%)",
            recommendations=[
                "Admission recommended",
                "Cardiology consultation",
            ],
        ),
        ThresholdInterpretation(
            min_score=5, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Very high risk (14.3%)",
            recommendations=[
                "Admission required",
                "Telemetry monitoring",
                "Cardiology consultation",
            ],
        ),
    ],
)


# ============================================================================
# SAN FRANCISCO SYNCOPE RULE
# ============================================================================
SF_SYNCOPE_DEFINITION = CalculatorDefinition(
    id="sf_syncope",
    name="San Francisco Syncope Rule",
    short_name="SF Syncope",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies syncope patients safe for ED discharge",
    references=[
        "Quinn JV, et al. Ann Emerg Med. 2004;43(2):224-232. PMID: 14747812",
        "Quinn JV, et al. Ann Emerg Med. 2006;47(5):448-454. PMID: 16631984",
    ],
    specialties=["Emergency Medicine"],
    notes=[
        "CHESS mnemonic: CHF, Hct<30%, ECG abnormal, Shortness of breath, Systolic BP<90",
        "Any positive = not safe for discharge",
        "Sensitivity ~98%, specificity ~56%",
    ],
    criteria=[
        ScoringCriterion("chf_history", "History of CHF", 1, "History of congestive heart failure"),
        ScoringCriterion("hematocrit_low", "Hematocrit <30%", 1, ""),
        ScoringCriterion("ecg_abnormal", "Abnormal ECG", 1,
                        "New changes or non-sinus rhythm"),
        ScoringCriterion("shortness_of_breath", "Shortness of breath", 1, "Complaint of dyspnea"),
        ScoringCriterion("systolic_bp_low", "Systolic BP <90 mmHg at triage", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk - safe for discharge",
            recommendations=[
                "No criteria present",
                "Outpatient follow-up appropriate",
                "Return precautions given",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="Not low risk - further evaluation needed",
            recommendations=[
                "One or more criteria present",
                "Cannot exclude serious outcome",
                "Consider admission or observation",
            ],
        ),
    ],
)


# ============================================================================
# OESIL SCORE - Syncope Risk
# ============================================================================
OESIL_DEFINITION = CalculatorDefinition(
    id="oesil",
    name="OESIL Risk Score for Syncope",
    short_name="OESIL",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="One-year mortality risk after syncope",
    references=[
        "Colivicchi F, et al. Eur Heart J. 2003;24(9):811-819. PMID: 12727148",
    ],
    specialties=["Emergency Medicine", "Cardiology", "Internal Medicine"],
    criteria=[
        ScoringCriterion("age_65_or_older", "Age ≥65 years", 1, ""),
        ScoringCriterion("cardiovascular_history", "Cardiovascular disease history", 1, ""),
        ScoringCriterion("syncope_without_prodrome", "Syncope without prodrome", 1, "No warning symptoms"),
        ScoringCriterion("abnormal_ecg", "Abnormal ECG", 1,
                        "Any abnormality including rhythm, conduction, or morphology"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk (0-0.6% 1-year mortality)",
            recommendations=["Outpatient evaluation appropriate"],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=2,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Intermediate risk (2% 1-year mortality)",
            recommendations=["Observation or expedited outpatient workup"],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate-high risk (14% 1-year mortality)",
            recommendations=["Admission for evaluation"],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk (29% 1-year mortality)",
            recommendations=[
                "Admission required",
                "Comprehensive cardiac workup",
            ],
        ),
    ],
)


# ============================================================================
# EGSYS SCORE - Cardiac vs Non-Cardiac Syncope
# ============================================================================
EGSYS_DEFINITION = CalculatorDefinition(
    id="egsys",
    name="EGSYS Score for Cardiac Syncope",
    short_name="EGSYS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Distinguishes cardiac from non-cardiac syncope",
    references=[
        "Del Rosso A, et al. Heart. 2008;94(12):1620-1626. PMID: 18519550",
    ],
    specialties=["Emergency Medicine", "Cardiology"],
    notes=[
        "Score ≥3 suggests cardiac syncope",
        "Negative points for prodrome/predisposing factors",
    ],
    criteria=[
        ScoringCriterion("palpitations_before", "Palpitations before syncope", 4, ""),
        ScoringCriterion("abnormal_ecg", "Abnormal ECG and/or heart disease", 3,
                        "ECG abnormality or history of heart disease"),
        ScoringCriterion("syncope_during_effort", "Syncope during effort", 3, "During exertion"),
        ScoringCriterion("syncope_supine", "Syncope in supine position", 2, ""),
        ScoringCriterion("autonomic_prodromes", "Autonomic prodromes", -1,
                        "Nausea, vomiting, warmth (negative points)"),
        ScoringCriterion("predisposing_triggering", "Predisposing and/or precipitating factors", -1,
                        "Warm/crowded place, prolonged standing, fear, pain (negative points)"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=-2, max_score=3,
            risk_level=RiskLevel.LOW,
            interpretation="Likely non-cardiac syncope (2-4% cardiac)",
            recommendations=[
                "Consider vasovagal or other non-cardiac cause",
                "Outpatient evaluation may be appropriate",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Likely cardiac syncope (>90% cardiac)",
            recommendations=[
                "Admission for cardiac evaluation",
                "Telemetry monitoring",
                "Consider electrophysiology consultation",
            ],
        ),
    ],
)


# ============================================================================
# SGARBOSSA CRITERIA - STEMI with LBBB
# ============================================================================
SGARBOSSA_DEFINITION = CalculatorDefinition(
    id="sgarbossa",
    name="Sgarbossa Criteria for STEMI in LBBB",
    short_name="Sgarbossa",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Identifies STEMI in the presence of left bundle branch block",
    references=[
        "Sgarbossa EB, et al. N Engl J Med. 1996;334(8):481-487. PMID: 8559200",
    ],
    specialties=["Emergency Medicine", "Cardiology"],
    notes=[
        "Score ≥3 highly specific for acute MI",
        "Also applicable to ventricular paced rhythms",
    ],
    criteria=[
        ScoringCriterion("concordant_st_elevation", "Concordant ST elevation ≥1mm", 5,
                        "ST elevation in leads with positive QRS"),
        ScoringCriterion("concordant_st_depression", "Concordant ST depression ≥1mm in V1-V3", 3,
                        "ST depression in V1, V2, or V3"),
        ScoringCriterion("discordant_st_elevation", "Discordant ST elevation ≥5mm", 2,
                        "ST elevation ≥5mm in leads with negative QRS"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=3,
            risk_level=RiskLevel.LOW,
            interpretation="Low probability of acute MI with LBBB",
            recommendations=[
                "Does not rule out MI",
                "Serial ECGs and troponins",
                "Clinical judgment paramount",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High probability of acute MI with LBBB",
            recommendations=[
                "Treat as STEMI equivalent",
                "Activate cath lab for emergent PCI",
                "Specificity ~90% for MI",
            ],
        ),
    ],
)


# ============================================================================
# MODIFIED SGARBOSSA CRITERIA (Smith Criteria)
# ============================================================================
MODIFIED_SGARBOSSA_DEFINITION = CalculatorDefinition(
    id="modified_sgarbossa",
    name="Modified Sgarbossa Criteria (Smith)",
    short_name="Modified Sgarbossa",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Improved criteria for STEMI in LBBB using ST/S ratio",
    references=[
        "Smith SW, et al. Ann Emerg Med. 2012;60(6):766-776. PMID: 22939607",
    ],
    specialties=["Emergency Medicine", "Cardiology"],
    notes=[
        "Replaces 5mm discordant criterion with ST/S ratio ≤-0.25",
        "Any positive criterion = likely STEMI",
        "Better sensitivity than original Sgarbossa",
    ],
    criteria=[
        ScoringCriterion("concordant_st_elevation", "Concordant ST elevation ≥1mm", 1,
                        "ST elevation in leads with positive QRS"),
        ScoringCriterion("concordant_st_depression_v1v3", "Concordant ST depression ≥1mm in V1-V3", 1,
                        ""),
        ScoringCriterion("st_s_ratio", "Discordant ST/S ratio ≤-0.25", 1,
                        "Excessive discordant ST elevation relative to S wave depth"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Negative - STEMI unlikely",
            recommendations=[
                "Does not definitively rule out MI",
                "Continue monitoring and serial troponins",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Positive - likely STEMI",
            recommendations=[
                "Any positive criterion warrants cath lab activation",
                "Sensitivity ~91%, specificity ~90%",
            ],
        ),
    ],
)


# ============================================================================
# YEARS ALGORITHM - PE Diagnosis
# ============================================================================
YEARS_ALGORITHM_DEFINITION = CalculatorDefinition(
    id="years_algorithm",
    name="YEARS Algorithm for PE",
    short_name="YEARS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Simplified PE diagnostic algorithm using D-dimer thresholds",
    references=[
        "van der Hulle T, et al. Lancet. 2017;390(10091):289-297. PMID: 28549662",
    ],
    specialties=["Emergency Medicine", "Pulmonology"],
    notes=[
        "If 0 YEARS criteria: PE excluded if D-dimer <1000 ng/mL",
        "If ≥1 YEARS criteria: PE excluded if D-dimer <500 ng/mL",
        "Reduces CT-PA imaging by ~14%",
    ],
    criteria=[
        ScoringCriterion("clinical_dvt_signs", "Clinical signs of DVT", 1, "Leg swelling, pain on palpation"),
        ScoringCriterion("hemoptysis", "Hemoptysis", 1, ""),
        ScoringCriterion("pe_most_likely", "PE is most likely diagnosis", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Zero YEARS criteria present",
            recommendations=[
                "PE excluded if D-dimer <1000 ng/mL",
                "If D-dimer ≥1000, proceed to CT-PA",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="One or more YEARS criteria present",
            recommendations=[
                "PE excluded if D-dimer <500 ng/mL",
                "If D-dimer ≥500, proceed to CT-PA",
            ],
        ),
    ],
)


# ============================================================================
# AORTIC DISSECTION DETECTION RISK SCORE (ADD-RS)
# ============================================================================
ADD_RS_DEFINITION = CalculatorDefinition(
    id="add_rs",
    name="Aortic Dissection Detection Risk Score",
    short_name="ADD-RS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Risk stratification for acute aortic syndrome",
    references=[
        "Hiratzka LF, et al. Circulation. 2010;121(13):e266-e369. PMID: 20233780",
        "Rogers AM, et al. Circulation. 2011;123(20):2213-2218. PMID: 21555704",
    ],
    specialties=["Emergency Medicine", "Cardiology", "Cardiac Surgery"],
    notes=[
        "Score 0-1 with negative D-dimer may rule out dissection",
        "Score ≥1 warrants imaging",
        "D-dimer <500 has high negative predictive value",
    ],
    criteria=[
        # High-risk conditions (1 point if any present)
        ScoringCriterion("marfan_connective", "Marfan or connective tissue disease", 1, ""),
        ScoringCriterion("family_history_aortic", "Family history of aortic disease", 1, ""),
        ScoringCriterion("known_aortic_valve_disease", "Known aortic valve disease", 1, ""),
        ScoringCriterion("known_thoracic_aneurysm", "Known thoracic aortic aneurysm", 1, ""),
        ScoringCriterion("prior_aortic_manipulation", "Previous aortic manipulation/surgery", 1, ""),
        # High-risk pain features (1 point if any present)
        ScoringCriterion("chest_back_abdominal_pain", "Chest, back, or abdominal pain", 1,
                        "Severe, abrupt onset, tearing/ripping quality"),
        # High-risk exam features (1 point if any present)
        ScoringCriterion("pulse_deficit", "Pulse deficit", 1, ""),
        ScoringCriterion("systolic_bp_differential", "Systolic BP differential >20 mmHg", 1, ""),
        ScoringCriterion("focal_neurological_deficit", "Focal neurological deficit", 1, "Plus chest pain"),
        ScoringCriterion("new_aortic_murmur", "New aortic insufficiency murmur", 1, "Plus chest pain"),
        ScoringCriterion("hypotension_shock", "Hypotension or shock", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk",
            recommendations=[
                "Consider D-dimer testing",
                "If D-dimer <500 and ADD-RS 0: dissection very unlikely",
                "If D-dimer elevated: imaging indicated",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=2,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk",
            recommendations=[
                "Imaging recommended (CT angiography)",
                "D-dimer may be used to expedite workup",
            ],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High risk",
            recommendations=[
                "Emergent imaging (CT angiography)",
                "Surgical consultation",
                "BP and heart rate control",
            ],
        ),
    ],
)


# ============================================================================
# EDACS SCORE - ED Chest Pain Assessment
# ============================================================================
EDACS_DEFINITION = CalculatorDefinition(
    id="edacs",
    name="Emergency Department Assessment of Chest Pain Score",
    short_name="EDACS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Identifies low-risk chest pain patients for early discharge",
    references=[
        "Than M, et al. Lancet. 2014;383(9925):1305-1312. PMID: 24583085",
    ],
    specialties=["Emergency Medicine", "Cardiology"],
    notes=[
        "EDACS-ADP: low risk if EDACS <16, troponin negative at 0 and 2h, no ischemic ECG",
        "Allows safe early discharge (~4 hours)",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[
                ("gte", 50, 2, "Age 50-65 (+2)"),
                ("gte", 66, 4, "Age 66-85 (+4 additional)"),
                ("gte", 86, 6, "Age >85 (+6 additional)"),
            ],
            description="Age contribution (tiered)",
        ),
    ],
    criteria=[
        ScoringCriterion("male", "Male sex", 6, ""),
        ScoringCriterion("age_18_45", "Age 18-45 years", 2, ""),
        ScoringCriterion("age_46_50", "Age 46-50 years", 4, ""),
        ScoringCriterion("known_cad", "Known CAD", 4, "Prior MI, PCI, CABG, positive stress/angiography"),
        ScoringCriterion("two_or_more_risk_factors", "≥2 CV risk factors", 2, "DM, HTN, dyslipidemia, smoking, family hx"),
        ScoringCriterion("diaphoresis", "Diaphoresis", 3, "Observed sweating"),
        ScoringCriterion("pain_radiates_arm_shoulder", "Pain radiates to arm or shoulder", 5, ""),
        ScoringCriterion("pain_inspiration", "Pain with inspiration", -4, "Pleuritic pain (negative points)"),
        ScoringCriterion("pain_reproduced_palpation", "Pain reproduced by palpation", -6, "Reproducible chest wall pain (negative points)"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=-10, max_score=16,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk",
            recommendations=[
                "If troponin negative at 0 and 2h and ECG non-ischemic:",
                "Safe for early discharge (~4 hours)",
                "Outpatient follow-up",
            ],
        ),
        ThresholdInterpretation(
            min_score=16, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="Not low risk",
            recommendations=[
                "Standard chest pain pathway",
                "Serial troponins",
                "Consider observation or admission",
            ],
        ),
    ],
)


# ============================================================================
# VANCOUVER CHEST PAIN RULE
# ============================================================================
VANCOUVER_CPR_DEFINITION = CalculatorDefinition(
    id="vancouver_cpr",
    name="Vancouver Chest Pain Rule",
    short_name="Vancouver CPR",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies very low risk chest pain patients safe for early discharge",
    references=[
        "Christenson J, et al. CMAJ. 2014;186(7):E177-E183. PMID: 24614388",
    ],
    specialties=["Emergency Medicine"],
    notes=[
        "Very low risk if ALL criteria absent",
        "Sensitivity ~99% for 30-day ACS",
    ],
    criteria=[
        ScoringCriterion("abnormal_initial_ecg", "Abnormal initial ECG", 1,
                        "New ischemic changes"),
        ScoringCriterion("positive_troponin", "Positive troponin (0 or 2h)", 1, ""),
        ScoringCriterion("prior_acs_pci", "Prior ACS or PCI", 1, "History of MI, NSTEMI, PCI"),
        ScoringCriterion("nitroglycerin_use", "Used nitro prior to or in ED", 1, ""),
        ScoringCriterion("typical_pain", "Typical pain characteristics", 1,
                        "Pain worse with exertion, radiation to arm/jaw/shoulder, pressure-like"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Very low risk - safe for early discharge",
            recommendations=[
                "30-day ACS risk <1%",
                "Safe for discharge from ED",
                "Outpatient follow-up",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="Not very low risk - further evaluation needed",
            recommendations=[
                "Standard chest pain evaluation",
                "May need observation or admission",
            ],
        ),
    ],
)


# ============================================================================
# MARBURG HEART SCORE
# ============================================================================
MARBURG_DEFINITION = CalculatorDefinition(
    id="marburg",
    name="Marburg Heart Score",
    short_name="Marburg",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Primary care chest pain rule to identify CAD",
    references=[
        "Bosner S, et al. CMAJ. 2010;182(12):1295-1300. PMID: 20603345",
    ],
    specialties=["Family Medicine", "Internal Medicine"],
    notes=[
        "Developed for primary care settings",
        "Score ≤2 has <2.5% probability of CAD",
    ],
    criteria=[
        ScoringCriterion("female_55_male_65", "Female ≥65 or male ≥55 years", 1, ""),
        ScoringCriterion("known_vascular_disease", "Known clinical vascular disease", 1,
                        "CAD, PAD, cerebrovascular disease"),
        ScoringCriterion("pain_worse_exercise", "Pain worse with exercise", 1, ""),
        ScoringCriterion("pain_not_palpation", "Pain not reproducible by palpation", 1, ""),
        ScoringCriterion("patient_assumes_cardiac", "Patient assumes pain is of cardiac origin", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=3,
            risk_level=RiskLevel.LOW,
            interpretation="Low probability of CAD (<2.5%)",
            recommendations=[
                "ACS unlikely",
                "Consider non-cardiac causes",
                "May manage in primary care",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=None,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate-high probability of CAD",
            recommendations=[
                "Further evaluation indicated",
                "Consider ECG, troponin",
                "Refer if concerning features",
            ],
        ),
    ],
)


# ============================================================================
# INTERCHEST SCORE
# ============================================================================
INTERCHEST_DEFINITION = CalculatorDefinition(
    id="interchest",
    name="INTERCHEST Score",
    short_name="INTERCHEST",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Primary care chest pain rule from international derivation",
    references=[
        "Aerts M, et al. BMC Fam Pract. 2017;18(1):62. PMID: 28499356",
    ],
    specialties=["Family Medicine", "Internal Medicine"],
    criteria=[
        ScoringCriterion("chest_discomfort", "Chest discomfort lasting <1 hour", 1, ""),
        ScoringCriterion("female_65_male_55", "Female ≥65 or male ≥55 years", 1, ""),
        ScoringCriterion("known_cad_diabetes", "Known CAD or diabetes", 1, ""),
        ScoringCriterion("pain_worse_exertion", "Pain worse with exertion", 1, ""),
        ScoringCriterion("substernal_location", "Substernal location", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Low CAD probability (~2%)",
            recommendations=["Minimal further testing needed"],
        ),
        ThresholdInterpretation(
            min_score=2, max_score=4,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate CAD probability",
            recommendations=["Consider further evaluation"],
        ),
        ThresholdInterpretation(
            min_score=4, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Higher CAD probability",
            recommendations=["Cardiology referral or ED evaluation"],
        ),
    ],
)


# ============================================================================
# PESI SCORE - Pulmonary Embolism Severity Index
# ============================================================================
PESI_DEFINITION = CalculatorDefinition(
    id="pesi",
    name="Pulmonary Embolism Severity Index (PESI)",
    short_name="PESI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="30-day mortality risk stratification for confirmed PE",
    references=[
        "Aujesky D, et al. Am J Respir Crit Care Med. 2005;172(8):1041-1046. PMID: 16020800",
    ],
    specialties=["Pulmonology", "Emergency Medicine", "Internal Medicine"],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[("gte", 0, 0, "Age in years")],
            description="Age contributes points equal to age",
        ),
        ThresholdCriterion(
            name="pulse",
            display_name="Pulse",
            thresholds=[("gte", 110, 20, "Pulse ≥110")],
            unit="bpm",
            description="Heart rate",
        ),
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[("lt", 100, 30, "SBP <100")],
            unit="mmHg",
            description="",
        ),
        ThresholdCriterion(
            name="respiratory_rate",
            display_name="Respiratory Rate",
            thresholds=[("gte", 30, 20, "RR ≥30")],
            unit="/min",
            description="",
        ),
        ThresholdCriterion(
            name="temperature",
            display_name="Temperature",
            thresholds=[("lt", 36, 20, "Temp <36°C")],
            unit="°C",
            description="",
        ),
        ThresholdCriterion(
            name="o2_sat",
            display_name="O2 Saturation",
            thresholds=[("lt", 90, 20, "SpO2 <90%")],
            unit="%",
            description="On room air or supplemental O2",
        ),
    ],
    criteria=[
        ScoringCriterion("male", "Male sex", 10, ""),
        ScoringCriterion("cancer", "Cancer", 30, "Active or history within past year"),
        ScoringCriterion("heart_failure", "Heart failure", 10, ""),
        ScoringCriterion("chronic_lung_disease", "Chronic lung disease", 10, ""),
        ScoringCriterion("altered_mental_status", "Altered mental status", 60, "Disorientation, lethargy, stupor, coma"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=66,
            risk_level=RiskLevel.LOW,
            interpretation="Class I - Very low risk (0-1.6% mortality)",
            recommendations=["Outpatient treatment may be appropriate"],
        ),
        ThresholdInterpretation(
            min_score=66, max_score=86,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Class II - Low risk (1.7-3.5% mortality)",
            recommendations=["Outpatient treatment may be considered"],
        ),
        ThresholdInterpretation(
            min_score=86, max_score=106,
            risk_level=RiskLevel.MODERATE,
            interpretation="Class III - Intermediate risk (3.2-7.1% mortality)",
            recommendations=["Inpatient treatment"],
        ),
        ThresholdInterpretation(
            min_score=106, max_score=126,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="Class IV - High risk (4.0-11.4% mortality)",
            recommendations=["Inpatient treatment, consider ICU"],
        ),
        ThresholdInterpretation(
            min_score=126, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Class V - Very high risk (10-24.5% mortality)",
            recommendations=["ICU admission"],
        ),
    ],
)


# ============================================================================
# SIMPLIFIED PESI (sPESI)
# ============================================================================
SPESI_DEFINITION = CalculatorDefinition(
    id="spesi",
    name="Simplified Pulmonary Embolism Severity Index",
    short_name="sPESI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Simplified version of PESI for PE risk stratification",
    references=[
        "Jimenez D, et al. Arch Intern Med. 2010;170(15):1383-1389. PMID: 20696966",
    ],
    specialties=["Pulmonology", "Emergency Medicine", "Internal Medicine"],
    notes=[
        "0 points = low risk, may consider outpatient treatment",
        "≥1 point = not low risk",
    ],
    criteria=[
        ScoringCriterion("age_over_80", "Age >80 years", 1, ""),
        ScoringCriterion("cancer", "Cancer", 1, "Active malignancy"),
        ScoringCriterion("chronic_cardiopulmonary", "Chronic cardiopulmonary disease", 1, "CHF or chronic lung disease"),
        ScoringCriterion("pulse_110_or_more", "Pulse ≥110 bpm", 1, ""),
        ScoringCriterion("systolic_bp_under_100", "Systolic BP <100 mmHg", 1, ""),
        ScoringCriterion("o2_sat_under_90", "O2 saturation <90%", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk (30-day mortality 1.0%)",
            recommendations=[
                "Consider outpatient treatment",
                "Risk of adverse events ~1.5%",
            ],
        ),
        ThresholdInterpretation(
            min_score=1, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Not low risk (30-day mortality 10.9%)",
            recommendations=[
                "Inpatient treatment recommended",
                "Consider ICU if hemodynamically unstable",
            ],
        ),
    ],
)


# ============================================================================
# BOVA SCORE - PE Risk Stratification
# ============================================================================
BOVA_DEFINITION = CalculatorDefinition(
    id="bova",
    name="Bova Score for PE Complications",
    short_name="Bova",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts PE-related complications in hemodynamically stable patients",
    references=[
        "Bova C, et al. Eur Respir J. 2014;44(4):920-928. PMID: 25073993",
    ],
    specialties=["Pulmonology", "Emergency Medicine", "Critical Care"],
    notes=[
        "For normotensive PE patients only",
        "Predicts 30-day PE-related death, hemodynamic collapse, recurrence",
    ],
    threshold_criteria=[
        ThresholdCriterion(
            name="systolic_bp",
            display_name="Systolic BP",
            thresholds=[
                ("range", (90, 100), 2, "SBP 90-100 mmHg"),
            ],
            unit="mmHg",
            description="",
        ),
        ThresholdCriterion(
            name="heart_rate",
            display_name="Heart Rate",
            thresholds=[("gte", 110, 1, "HR ≥110 bpm")],
            unit="bpm",
            description="",
        ),
    ],
    criteria=[
        ScoringCriterion("elevated_troponin", "Elevated cardiac troponin", 2, ""),
        ScoringCriterion("rv_dysfunction", "RV dysfunction on imaging", 2, "Echo or CT showing RV strain/dilation"),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0, max_score=3,
            risk_level=RiskLevel.LOW,
            interpretation="Low risk (4% 30-day complications)",
            recommendations=[
                "Consider early discharge",
                "Close outpatient follow-up",
            ],
        ),
        ThresholdInterpretation(
            min_score=3, max_score=5,
            risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate-low risk (10% 30-day complications)",
            recommendations=[
                "Inpatient monitoring",
                "Serial biomarkers",
            ],
        ),
        ThresholdInterpretation(
            min_score=5, max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="Intermediate-high risk (24% 30-day complications)",
            recommendations=[
                "Close monitoring, consider ICU",
                "Early escalation if deterioration",
                "Consider thrombolysis if decompensates",
            ],
        ),
    ],
)


# ============================================================================
# TIER 1 - RENAL FUNCTION CALCULATORS
# ============================================================================

# CKD-EPI 2009 (Legacy with race coefficient - for comparison)
CKD_EPI_2009_DEFINITION = CalculatorDefinition(
    id="ckd_epi_2009",
    name="CKD-EPI Creatinine Equation (2009)",
    short_name="CKD-EPI 2009",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min/1.73m2",
    description="Legacy eGFR equation with race coefficient (use 2021 version for clinical practice)",
    references=["Levey AS, et al. Ann Intern Med. 2009;150(9):604-612. PMID: 19414839"],
    specialties=["Nephrology", "Internal Medicine", "Primary Care"],
    notes=["Includes race coefficient - now deprecated", "Use CKD-EPI 2021 for clinical practice"],
    formula=FormulaDefinition(
        formula_text="141 x min(Scr/k,1)^a x max(Scr/k,1)^-1.209 x 0.993^Age x 1.018[if female] x 1.159[if Black]",
        output_unit="mL/min/1.73m2",
        precision=0,
        parameters=[
            FormulaParameter(name="creatinine", display_name="Serum Creatinine", unit="mg/dL", min_value=0.2, max_value=15.0),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
            FormulaParameter(name="black", display_name="Black race", unit="", min_value=0, max_value=1, description="Race coefficient - deprecated"),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="G1: Normal or high (>=90)", recommendations=["CKD if other markers of kidney damage"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="G2: Mildly decreased (60-89)", recommendations=["CKD if other markers present"]),
        ThresholdInterpretation(min_score=45, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="G3a: Mildly-moderately decreased (45-59)", recommendations=["Nephrology referral", "BP/DM control"]),
        ThresholdInterpretation(min_score=30, max_score=45, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="G3b: Moderately-severely decreased (30-44)", recommendations=["Nephrology referral", "Avoid nephrotoxins"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="G4: Severely decreased (15-29)", recommendations=["Prepare for RRT", "Dietary modifications"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="G5: Kidney failure (<15)", recommendations=["Dialysis/transplant evaluation"]),
    ],
)

# MDRD GFR
MDRD_GFR_DEFINITION = CalculatorDefinition(
    id="mdrd_gfr",
    name="MDRD GFR Equation",
    short_name="MDRD",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min/1.73m2",
    description="Modification of Diet in Renal Disease equation for GFR estimation",
    references=["Levey AS, et al. Ann Intern Med. 1999;130(6):461-470. PMID: 10075613"],
    specialties=["Nephrology", "Internal Medicine"],
    notes=["Less accurate than CKD-EPI at higher GFR", "4-variable IDMS-traceable version"],
    formula=FormulaDefinition(
        formula_text="175 x Scr^-1.154 x Age^-0.203 x 0.742[if female] x 1.212[if Black]",
        output_unit="mL/min/1.73m2",
        precision=0,
        parameters=[
            FormulaParameter(name="creatinine", display_name="Serum Creatinine", unit="mg/dL", min_value=0.2, max_value=15.0),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
            FormulaParameter(name="black", display_name="Black race", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="G1: Normal or high (>=90)", recommendations=["CKD if other markers of kidney damage"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="G2: Mildly decreased (60-89)", recommendations=["CKD if other markers present"]),
        ThresholdInterpretation(min_score=45, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="G3a: Mildly-moderately decreased (45-59)", recommendations=["Nephrology referral"]),
        ThresholdInterpretation(min_score=30, max_score=45, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="G3b: Moderately-severely decreased (30-44)", recommendations=["Nephrology referral"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="G4: Severely decreased (15-29)", recommendations=["Prepare for RRT"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="G5: Kidney failure (<15)", recommendations=["Dialysis/transplant evaluation"]),
    ],
)

# Schwartz Formula (Pediatric eGFR)
SCHWARTZ_DEFINITION = CalculatorDefinition(
    id="schwartz",
    name="Schwartz Formula (Pediatric eGFR)",
    short_name="Schwartz",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min/1.73m2",
    description="Estimates GFR in children using creatinine and height",
    references=["Schwartz GJ, et al. Pediatrics. 2009;123(5):e829-835. PMID: 19395437"],
    specialties=["Pediatric Nephrology", "Pediatrics"],
    notes=["Bedside Schwartz (2009): k=0.413", "Valid for ages 1-16 years"],
    formula=FormulaDefinition(
        formula_text="0.413 x Height(cm) / Serum Creatinine",
        output_unit="mL/min/1.73m2",
        precision=0,
        parameters=[
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=50, max_value=200),
            FormulaParameter(name="creatinine", display_name="Serum Creatinine", unit="mg/dL", min_value=0.1, max_value=10.0),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Normal GFR", recommendations=["Normal kidney function for age"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mildly decreased", recommendations=["Monitor, pediatric nephrology if persistent"]),
        ThresholdInterpretation(min_score=30, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="Moderately decreased", recommendations=["Pediatric nephrology referral"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="Severely decreased", recommendations=["Pediatric nephrology management"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Kidney failure", recommendations=["Pediatric dialysis/transplant evaluation"]),
    ],
)

# CKD-EPI Cystatin C (2021)
CKD_EPI_CYSTATIN_DEFINITION = CalculatorDefinition(
    id="ckd_epi_cystatin",
    name="CKD-EPI Cystatin C Equation (2021)",
    short_name="CKD-EPI CysC",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min/1.73m2",
    description="eGFR using cystatin C alone (2021 race-free equation)",
    references=["Inker LA, et al. N Engl J Med. 2021;385(19):1737-1749. PMID: 34554658"],
    specialties=["Nephrology", "Internal Medicine"],
    notes=["Useful when creatinine unreliable (muscle wasting, amputation)", "More expensive than creatinine"],
    formula=FormulaDefinition(
        formula_text="133 x min(CysC/0.8,1)^-0.499 x max(CysC/0.8,1)^-1.328 x 0.996^Age x 0.932[if female]",
        output_unit="mL/min/1.73m2",
        precision=0,
        parameters=[
            FormulaParameter(name="cystatin_c", display_name="Cystatin C", unit="mg/L", min_value=0.3, max_value=10.0),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="G1: Normal or high (>=90)", recommendations=["Normal kidney function"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="G2: Mildly decreased (60-89)", recommendations=["Monitor if risk factors"]),
        ThresholdInterpretation(min_score=45, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="G3a: Mildly-moderately decreased (45-59)", recommendations=["Nephrology referral"]),
        ThresholdInterpretation(min_score=30, max_score=45, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="G3b: Moderately-severely decreased (30-44)", recommendations=["Nephrology referral"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="G4: Severely decreased (15-29)", recommendations=["Prepare for RRT"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="G5: Kidney failure (<15)", recommendations=["Dialysis/transplant evaluation"]),
    ],
)

# CKD-EPI Creatinine-Cystatin C Combined (2021)
CKD_EPI_COMBINED_DEFINITION = CalculatorDefinition(
    id="ckd_epi_combined",
    name="CKD-EPI Creatinine-Cystatin C Combined (2021)",
    short_name="CKD-EPI Cr-CysC",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min/1.73m2",
    description="Most accurate eGFR using both creatinine and cystatin C",
    references=["Inker LA, et al. N Engl J Med. 2021;385(19):1737-1749. PMID: 34554658"],
    specialties=["Nephrology", "Internal Medicine"],
    notes=["Most accurate equation when both markers available", "Use for confirmatory testing"],
    formula=FormulaDefinition(
        formula_text="135 x min(Scr/k,1)^a x max(Scr/k,1)^-0.544 x min(CysC/0.8,1)^-0.323 x max(CysC/0.8,1)^-0.778 x 0.9961^Age x 0.963[if female]",
        output_unit="mL/min/1.73m2",
        precision=0,
        parameters=[
            FormulaParameter(name="creatinine", display_name="Serum Creatinine", unit="mg/dL", min_value=0.2, max_value=15.0),
            FormulaParameter(name="cystatin_c", display_name="Cystatin C", unit="mg/L", min_value=0.3, max_value=10.0),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="G1: Normal or high (>=90)", recommendations=["Normal kidney function"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="G2: Mildly decreased (60-89)", recommendations=["Monitor if risk factors"]),
        ThresholdInterpretation(min_score=45, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="G3a: Mildly-moderately decreased (45-59)", recommendations=["Nephrology referral"]),
        ThresholdInterpretation(min_score=30, max_score=45, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="G3b: Moderately-severely decreased (30-44)", recommendations=["Nephrology referral"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="G4: Severely decreased (15-29)", recommendations=["Prepare for RRT"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="G5: Kidney failure (<15)", recommendations=["Dialysis/transplant evaluation"]),
    ],
)

# FENa (Fractional Excretion of Sodium)
FENA_DEFINITION = CalculatorDefinition(
    id="fena",
    name="Fractional Excretion of Sodium (FENa)",
    short_name="FENa",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="%",
    description="Differentiates prerenal from intrinsic AKI",
    references=["Espinel CH. JAMA. 1976;236(6):579-581. PMID: 947239"],
    specialties=["Nephrology", "Critical Care", "Emergency Medicine"],
    notes=["Less reliable if diuretics given", "Use FEUrea if on diuretics"],
    formula=FormulaDefinition(
        formula_text="(UNa x PCr) / (PNa x UCr) x 100",
        output_unit="%",
        precision=2,
        parameters=[
            FormulaParameter(name="urine_sodium", display_name="Urine Sodium", unit="mEq/L", min_value=1, max_value=300),
            FormulaParameter(name="plasma_sodium", display_name="Plasma Sodium", unit="mEq/L", min_value=100, max_value=180),
            FormulaParameter(name="urine_creatinine", display_name="Urine Creatinine", unit="mg/dL", min_value=5, max_value=500),
            FormulaParameter(name="plasma_creatinine", display_name="Plasma Creatinine", unit="mg/dL", min_value=0.2, max_value=20),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="FENa <1% - Prerenal azotemia",
            recommendations=["Volume repletion", "Treat underlying cause (CHF, cirrhosis, sepsis)", "Avoid nephrotoxins"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.MODERATE,
            interpretation="FENa 1-2% - Indeterminate",
            recommendations=["Clinical correlation needed", "May be early ATN or prerenal on diuretics"]),
        ThresholdInterpretation(min_score=2, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="FENa >2% - Intrinsic renal disease (ATN)",
            recommendations=["Supportive care", "Avoid nephrotoxins", "Consider nephrology consultation"]),
    ],
)

# FEUrea (Fractional Excretion of Urea)
FEUREA_DEFINITION = CalculatorDefinition(
    id="feurea",
    name="Fractional Excretion of Urea (FEUrea)",
    short_name="FEUrea",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="%",
    description="Differentiates prerenal from intrinsic AKI (valid with diuretics)",
    references=["Carvounis CP, et al. Kidney Int. 2002;62(6):2223-2229. PMID: 12427149"],
    specialties=["Nephrology", "Critical Care"],
    notes=["More reliable than FENa when patient on diuretics", "Urea not affected by loop diuretics"],
    formula=FormulaDefinition(
        formula_text="(UUrea x PCr) / (PUrea x UCr) x 100",
        output_unit="%",
        precision=1,
        parameters=[
            FormulaParameter(name="urine_urea", display_name="Urine Urea", unit="mg/dL", min_value=50, max_value=3000),
            FormulaParameter(name="plasma_urea", display_name="BUN", unit="mg/dL", min_value=5, max_value=200),
            FormulaParameter(name="urine_creatinine", display_name="Urine Creatinine", unit="mg/dL", min_value=5, max_value=500),
            FormulaParameter(name="plasma_creatinine", display_name="Plasma Creatinine", unit="mg/dL", min_value=0.2, max_value=20),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=35, risk_level=RiskLevel.LOW,
            interpretation="FEUrea <35% - Prerenal azotemia",
            recommendations=["Volume repletion", "Treat underlying cause", "More specific than FENa with diuretics"]),
        ThresholdInterpretation(min_score=35, max_score=50, risk_level=RiskLevel.MODERATE,
            interpretation="FEUrea 35-50% - Indeterminate",
            recommendations=["Clinical correlation needed"]),
        ThresholdInterpretation(min_score=50, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="FEUrea >50% - Intrinsic renal disease (ATN)",
            recommendations=["Supportive care", "Nephrology consultation"]),
    ],
)

# TTKG (Transtubular Potassium Gradient)
TTKG_DEFINITION = CalculatorDefinition(
    id="ttkg",
    name="Transtubular Potassium Gradient (TTKG)",
    short_name="TTKG",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Assesses renal potassium handling in hyper/hypokalemia",
    references=["West ML, et al. Clin Nephrol. 1986;26(5):245-249. PMID: 3802570"],
    specialties=["Nephrology", "Endocrinology"],
    notes=["Only valid if urine osm > serum osm and urine Na >25", "Assesses aldosterone activity"],
    formula=FormulaDefinition(
        formula_text="(UK / (Uosm/Posm)) / PK",
        output_unit="",
        precision=1,
        parameters=[
            FormulaParameter(name="urine_potassium", display_name="Urine K", unit="mEq/L", min_value=1, max_value=200),
            FormulaParameter(name="serum_potassium", display_name="Serum K", unit="mEq/L", min_value=1.5, max_value=9.0),
            FormulaParameter(name="urine_osmolality", display_name="Urine Osmolality", unit="mOsm/kg", min_value=50, max_value=1400),
            FormulaParameter(name="serum_osmolality", display_name="Serum Osmolality", unit="mOsm/kg", min_value=250, max_value=350),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="TTKG <3 in hyperkalemia - Appropriate renal response",
            recommendations=["Low aldosterone or tubular dysfunction", "Check aldosterone, cortisol"]),
        ThresholdInterpretation(min_score=3, max_score=7, risk_level=RiskLevel.MODERATE,
            interpretation="TTKG 3-7 - Intermediate",
            recommendations=["Correlation with clinical context needed"]),
        ThresholdInterpretation(min_score=7, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="TTKG >7 in hypokalemia - Renal K wasting",
            recommendations=["Check for mineralocorticoid excess", "Evaluate diuretic use, RTA"]),
    ],
)


# ============================================================================
# TIER 2 - HEPATIC FUNCTION CALCULATORS
# ============================================================================

# MELD 3.0 (2022)
MELD_3_DEFINITION = CalculatorDefinition(
    id="meld_3",
    name="MELD 3.0 Score (2022)",
    short_name="MELD 3.0",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="points",
    description="Latest MELD version (2022) with albumin, removes sex penalty",
    references=["Kim WR, et al. Hepatology. 2022 Aug 3. PMID: 35921485"],
    specialties=["Hepatology", "Transplant", "Gastroenterology"],
    notes=[
        "Includes albumin, removes sex-based coefficient",
        "Better waitlist mortality prediction than MELD-Na",
        "Score range: 6-40",
    ],
    formula=FormulaDefinition(
        formula_text="1.33*(female) + 4.56*ln(bilirubin) + 0.82*(137-Na) - 0.24*(137-Na)*ln(creatinine) + 9.09*ln(INR) + 11.14*ln(creatinine) + 1.85*(3.5-albumin) - 1.83*(3.5-albumin)*ln(creatinine) + 7.33",
        output_unit="points",
        precision=0,
        parameters=[
            FormulaParameter(name="bilirubin", display_name="Total Bilirubin", unit="mg/dL", min_value=1.0, max_value=None),
            FormulaParameter(name="inr", display_name="INR", unit="", min_value=1.0, max_value=None),
            FormulaParameter(name="creatinine", display_name="Creatinine", unit="mg/dL", min_value=1.0, max_value=3.0),
            FormulaParameter(name="sodium", display_name="Serum Sodium", unit="mEq/L", min_value=125, max_value=137),
            FormulaParameter(name="albumin", display_name="Albumin", unit="g/dL", min_value=1.5, max_value=3.5),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.LOW,
            interpretation="MELD 3.0 <15 - Lower transplant priority",
            recommendations=["Monitor every 3 months", "Address underlying disease"]),
        ThresholdInterpretation(min_score=15, max_score=25, risk_level=RiskLevel.MODERATE,
            interpretation="MELD 3.0 15-24 - Moderate priority",
            recommendations=["Active listing appropriate", "Monitor monthly"]),
        ThresholdInterpretation(min_score=25, max_score=35, risk_level=RiskLevel.HIGH,
            interpretation="MELD 3.0 25-34 - High priority",
            recommendations=["Urgent listing", "Weekly monitoring"]),
        ThresholdInterpretation(min_score=35, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="MELD 3.0 >=35 - Highest priority",
            recommendations=["Emergent transplant consideration", "ICU care"]),
    ],
)

# NAFLD Fibrosis Score
NAFLD_FIBROSIS_DEFINITION = CalculatorDefinition(
    id="nafld_fibrosis",
    name="NAFLD Fibrosis Score (NFS)",
    short_name="NFS",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Predicts advanced fibrosis in NAFLD patients",
    references=["Angulo P, et al. Hepatology. 2007;45(4):846-854. PMID: 17393509"],
    specialties=["Hepatology", "Gastroenterology", "Primary Care"],
    notes=["High NPV for ruling out advanced fibrosis", "Use with FIB-4 for two-step approach"],
    formula=FormulaDefinition(
        formula_text="-1.675 + 0.037*Age + 0.094*BMI + 1.13*IFG/DM + 0.99*AST/ALT - 0.013*Platelets - 0.66*Albumin",
        output_unit="",
        precision=2,
        parameters=[
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="bmi", display_name="BMI", unit="kg/m2", min_value=15, max_value=60),
            FormulaParameter(name="diabetes", display_name="Diabetes/IFG", unit="", min_value=0, max_value=1, description="1 if diabetes or impaired fasting glucose"),
            FormulaParameter(name="ast", display_name="AST", unit="U/L", min_value=5, max_value=500),
            FormulaParameter(name="alt", display_name="ALT", unit="U/L", min_value=5, max_value=500),
            FormulaParameter(name="platelets", display_name="Platelets", unit="x10^9/L", min_value=20, max_value=500),
            FormulaParameter(name="albumin", display_name="Albumin", unit="g/dL", min_value=1.5, max_value=5.5),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=-999, max_score=-1.455, risk_level=RiskLevel.LOW,
            interpretation="NFS <-1.455 - Low probability of advanced fibrosis (F0-F2)",
            recommendations=["NPV 88-93%", "Reassess in 2-3 years", "Lifestyle modifications"]),
        ThresholdInterpretation(min_score=-1.455, max_score=0.676, risk_level=RiskLevel.MODERATE,
            interpretation="NFS -1.455 to 0.676 - Indeterminate",
            recommendations=["Consider FibroScan or liver biopsy", "Hepatology referral"]),
        ThresholdInterpretation(min_score=0.676, max_score=999, risk_level=RiskLevel.HIGH,
            interpretation="NFS >0.676 - High probability of advanced fibrosis (F3-F4)",
            recommendations=["PPV 82-90%", "Hepatology referral", "Consider liver biopsy"]),
    ],
)

# APRI (AST to Platelet Ratio Index)
APRI_DEFINITION = CalculatorDefinition(
    id="apri",
    name="AST to Platelet Ratio Index (APRI)",
    short_name="APRI",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Simple fibrosis marker using AST and platelets",
    references=["Wai CT, et al. Hepatology. 2003;38(2):518-526. PMID: 12883497"],
    specialties=["Hepatology", "Gastroenterology", "Infectious Disease"],
    notes=["Best validated in hepatitis C", "WHO recommends for resource-limited settings"],
    formula=FormulaDefinition(
        formula_text="(AST / AST_ULN) / Platelets x 100",
        output_unit="",
        precision=2,
        parameters=[
            FormulaParameter(name="ast", display_name="AST", unit="U/L", min_value=5, max_value=2000),
            FormulaParameter(name="ast_uln", display_name="AST Upper Limit Normal", unit="U/L", min_value=20, max_value=60, description="Usually 40 U/L"),
            FormulaParameter(name="platelets", display_name="Platelets", unit="x10^9/L", min_value=20, max_value=500),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=0.5, risk_level=RiskLevel.LOW,
            interpretation="APRI <0.5 - Low probability of significant fibrosis",
            recommendations=["NPV ~85% for significant fibrosis", "Routine monitoring"]),
        ThresholdInterpretation(min_score=0.5, max_score=1.5, risk_level=RiskLevel.MODERATE,
            interpretation="APRI 0.5-1.5 - Indeterminate",
            recommendations=["Consider additional testing", "FibroScan or biopsy"]),
        ThresholdInterpretation(min_score=1.5, max_score=2.0, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="APRI 1.5-2.0 - Significant fibrosis likely",
            recommendations=["Hepatology referral"]),
        ThresholdInterpretation(min_score=2.0, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="APRI >2.0 - Cirrhosis likely",
            recommendations=["PPV ~65% for cirrhosis", "Hepatology referral", "Liver biopsy consideration"]),
    ],
)

# Maddrey Discriminant Function
MADDREY_DF_DEFINITION = CalculatorDefinition(
    id="maddrey_df",
    name="Maddrey Discriminant Function",
    short_name="Maddrey DF",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Predicts severity and prognosis in alcoholic hepatitis",
    references=["Maddrey WC, et al. Gastroenterology. 1978;75(2):193-199. PMID: 352788"],
    specialties=["Hepatology", "Gastroenterology", "Critical Care"],
    notes=["DF >=32 indicates severe alcoholic hepatitis", "Consider corticosteroids if DF >=32"],
    formula=FormulaDefinition(
        formula_text="4.6 x (PT - control PT) + Bilirubin",
        output_unit="",
        precision=1,
        parameters=[
            FormulaParameter(name="pt_patient", display_name="Patient PT", unit="seconds", min_value=10, max_value=100),
            FormulaParameter(name="pt_control", display_name="Control PT", unit="seconds", min_value=10, max_value=15),
            FormulaParameter(name="bilirubin", display_name="Total Bilirubin", unit="mg/dL", min_value=0.5, max_value=50),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=32, risk_level=RiskLevel.MODERATE,
            interpretation="DF <32 - Non-severe alcoholic hepatitis",
            recommendations=["28-day mortality ~10%", "Supportive care", "Alcohol cessation"]),
        ThresholdInterpretation(min_score=32, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="DF >=32 - Severe alcoholic hepatitis",
            recommendations=["28-day mortality 35-50%", "Consider prednisolone 40mg/day for 28 days", "Assess with Lille model at day 7"]),
    ],
)

# Lille Model
LILLE_DEFINITION = CalculatorDefinition(
    id="lille",
    name="Lille Model for Alcoholic Hepatitis",
    short_name="Lille",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Predicts response to steroids at day 7 of treatment",
    references=["Louvet A, et al. Hepatology. 2007;45(6):1348-1354. PMID: 17518367"],
    specialties=["Hepatology", "Gastroenterology"],
    notes=["Assess at day 7 of corticosteroid treatment", "Determines whether to continue steroids"],
    formula=FormulaDefinition(
        formula_text="exp(R)/(1+exp(R)) where R = 3.19 - 0.101*Age + 0.147*Alb(g/L) + 0.0165*(change in Bili) - 0.206*renal - 0.0065*Bili(day0) - 0.0096*PT",
        output_unit="",
        precision=2,
        parameters=[
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="albumin", display_name="Albumin (day 0)", unit="g/L", min_value=10, max_value=50),
            FormulaParameter(name="bilirubin_day0", display_name="Bilirubin (day 0)", unit="umol/L", min_value=10, max_value=800),
            FormulaParameter(name="bilirubin_day7", display_name="Bilirubin (day 7)", unit="umol/L", min_value=10, max_value=800),
            FormulaParameter(name="creatinine", display_name="Creatinine", unit="mg/dL", min_value=0.3, max_value=10),
            FormulaParameter(name="pt", display_name="Prothrombin Time", unit="seconds", min_value=10, max_value=60),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=0.45, risk_level=RiskLevel.LOW,
            interpretation="Lille <0.45 - Complete or partial responder",
            recommendations=["Continue corticosteroids for 28 days", "6-month survival ~85%"]),
        ThresholdInterpretation(min_score=0.45, max_score=0.56, risk_level=RiskLevel.MODERATE,
            interpretation="Lille 0.45-0.56 - Partial responder",
            recommendations=["Consider continuing steroids", "Close monitoring"]),
        ThresholdInterpretation(min_score=0.56, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Lille >=0.56 - Null responder",
            recommendations=["Stop corticosteroids", "6-month survival ~25%", "Consider early transplant evaluation"]),
    ],
)

# GAHS (Glasgow Alcoholic Hepatitis Score)
GAHS_DEFINITION = CalculatorDefinition(
    id="gahs",
    name="Glasgow Alcoholic Hepatitis Score",
    short_name="GAHS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts 28-day and 84-day mortality in alcoholic hepatitis",
    references=["Forrest EH, et al. Gut. 2005;54(8):1174-1179. PMID: 16009691"],
    specialties=["Hepatology", "Gastroenterology"],
    notes=["Score range: 5-12", "GAHS >=9 indicates need for treatment"],
    threshold_criteria=[
        ThresholdCriterion(
            name="age",
            display_name="Age",
            thresholds=[("lt", 50, 1, "Age <50 (1)"), ("gte", 50, 2, "Age >=50 (2)")],
            unit="years",
        ),
        ThresholdCriterion(
            name="wbc",
            display_name="WBC",
            thresholds=[("lt", 15, 1, "WBC <15 (1)"), ("gte", 15, 2, "WBC >=15 (2)")],
            unit="x10^9/L",
        ),
        ThresholdCriterion(
            name="bun",
            display_name="BUN",
            thresholds=[("lt", 14, 1, "BUN <14 (1)"), ("gte", 14, 2, "BUN >=14 (2)")],
            unit="mg/dL",
        ),
        ThresholdCriterion(
            name="pt_ratio",
            display_name="PT Ratio (INR)",
            thresholds=[("lt", 1.5, 1, "INR <1.5 (1)"), ("between", (1.5, 2.0), 2, "INR 1.5-2.0 (2)"), ("gt", 2.0, 3, "INR >2.0 (3)")],
            unit="",
        ),
        ThresholdCriterion(
            name="bilirubin",
            display_name="Bilirubin",
            thresholds=[("lt", 7.3, 1, "Bili <7.3 (1)"), ("between", (7.3, 14.6), 2, "Bili 7.3-14.6 (2)"), ("gt", 14.6, 3, "Bili >14.6 (3)")],
            unit="mg/dL",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=5, max_score=9, risk_level=RiskLevel.MODERATE,
            interpretation="GAHS <9 - Better prognosis",
            recommendations=["28-day mortality ~10%", "May not benefit from steroids"]),
        ThresholdInterpretation(min_score=9, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="GAHS >=9 - Poor prognosis",
            recommendations=["28-day mortality ~40-50%", "Consider corticosteroid therapy"]),
    ],
)


# ============================================================================
# TIER 3 - ELECTROLYTES & ACID-BASE CALCULATORS
# ============================================================================

# Delta Gap (Delta-Delta)
DELTA_GAP_DEFINITION = CalculatorDefinition(
    id="delta_gap",
    name="Delta Gap (Delta-Delta)",
    short_name="Delta Gap",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mEq/L",
    description="Identifies mixed acid-base disorders in AG metabolic acidosis",
    references=["Wrenn K. South Med J. 1990;83(10):1195-1198. PMID: 2218662"],
    specialties=["Critical Care", "Nephrology", "Emergency Medicine"],
    notes=["Delta AG / Delta HCO3 ratio", "Helps identify concurrent metabolic disorders"],
    formula=FormulaDefinition(
        formula_text="(AG - 12) - (24 - HCO3)",
        output_unit="mEq/L",
        precision=1,
        parameters=[
            FormulaParameter(name="anion_gap", display_name="Anion Gap", unit="mEq/L", min_value=3, max_value=50),
            FormulaParameter(name="bicarbonate", display_name="Bicarbonate", unit="mEq/L", min_value=5, max_value=45),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=-999, max_score=-6, risk_level=RiskLevel.MODERATE,
            interpretation="Delta Gap < -6: Concurrent non-AG metabolic acidosis",
            recommendations=["AG acidosis + normal AG acidosis", "Consider diarrhea, RTA, early uremia"]),
        ThresholdInterpretation(min_score=-6, max_score=6, risk_level=RiskLevel.LOW,
            interpretation="Delta Gap -6 to +6: Pure AG metabolic acidosis",
            recommendations=["No concurrent metabolic disorder", "Treat underlying AG acidosis"]),
        ThresholdInterpretation(min_score=6, max_score=999, risk_level=RiskLevel.MODERATE,
            interpretation="Delta Gap > +6: Concurrent metabolic alkalosis",
            recommendations=["AG acidosis + metabolic alkalosis", "Consider vomiting, diuretics, contraction"]),
    ],
)

# Osmolal Gap
OSMOLAL_GAP_DEFINITION = CalculatorDefinition(
    id="osmolal_gap",
    name="Osmolal Gap",
    short_name="Osm Gap",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mOsm/kg",
    description="Screens for unmeasured osmoles (toxic alcohols)",
    references=["Purssell RA, et al. Ann Emerg Med. 2001;38(6):653-659. PMID: 11719745"],
    specialties=["Emergency Medicine", "Critical Care", "Toxicology"],
    notes=["Normal gap <10", "Elevated in methanol, ethylene glycol, isopropanol, ethanol"],
    formula=FormulaDefinition(
        formula_text="Measured Osm - Calculated Osm",
        output_unit="mOsm/kg",
        precision=1,
        parameters=[
            FormulaParameter(name="measured_osm", display_name="Measured Osmolality", unit="mOsm/kg", min_value=200, max_value=500),
            FormulaParameter(name="calculated_osm", display_name="Calculated Osmolality", unit="mOsm/kg", min_value=200, max_value=400),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=-999, max_score=10, risk_level=RiskLevel.LOW,
            interpretation="Osm Gap <10 - Normal",
            recommendations=["Low probability of toxic alcohol ingestion"]),
        ThresholdInterpretation(min_score=10, max_score=25, risk_level=RiskLevel.MODERATE,
            interpretation="Osm Gap 10-25 - Mildly elevated",
            recommendations=["May be normal variant or mild ingestion", "Clinical correlation", "Consider ethanol contribution"]),
        ThresholdInterpretation(min_score=25, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Osm Gap >25 - Significant elevation",
            recommendations=["High suspicion for toxic alcohol", "Send methanol, ethylene glycol levels", "Consider fomepizole, HD"]),
    ],
)

# Winter's Formula
WINTERS_FORMULA_DEFINITION = CalculatorDefinition(
    id="winters_formula",
    name="Winter's Formula",
    short_name="Winter's",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mmHg",
    description="Expected pCO2 compensation in metabolic acidosis",
    references=["Albert MS, et al. Ann Intern Med. 1967;66(2):312-322. PMID: 6016545"],
    specialties=["Critical Care", "Pulmonology", "Nephrology"],
    notes=["Predicts respiratory compensation range", "Variance +/- 2 mmHg"],
    formula=FormulaDefinition(
        formula_text="Expected pCO2 = 1.5 x HCO3 + 8 (+/- 2)",
        output_unit="mmHg",
        precision=0,
        parameters=[
            FormulaParameter(name="bicarbonate", display_name="Bicarbonate", unit="mEq/L", min_value=5, max_value=30),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Expected pCO2 range for appropriate compensation",
            recommendations=[
                "If actual pCO2 < expected: concurrent respiratory alkalosis",
                "If actual pCO2 > expected: concurrent respiratory acidosis",
                "If within range (+/-2): appropriate compensation",
            ]),
    ],
)

# Bicarbonate Deficit
BICARB_DEFICIT_DEFINITION = CalculatorDefinition(
    id="bicarb_deficit",
    name="Bicarbonate Deficit",
    short_name="Bicarb Deficit",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mEq",
    description="Calculates bicarbonate replacement needed",
    references=["Kraut JA, Kurtz I. Clin J Am Soc Nephrol. 2015;10(5):920-926. PMID: 24677553"],
    specialties=["Critical Care", "Nephrology", "Emergency Medicine"],
    notes=["Vd ~0.5 for HCO3", "Give 50% initially, reassess"],
    formula=FormulaDefinition(
        formula_text="0.5 x Weight(kg) x (24 - HCO3)",
        output_unit="mEq",
        precision=0,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=30, max_value=200),
            FormulaParameter(name="bicarbonate", display_name="Current HCO3", unit="mEq/L", min_value=1, max_value=24),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Bicarbonate replacement needed",
            recommendations=[
                "Give 50% of calculated deficit",
                "Reassess ABG in 2-4 hours",
                "Target HCO3 ~12-14 initially in severe acidosis",
            ]),
    ],
)

# Free Water Deficit
FREE_WATER_DEFICIT_DEFINITION = CalculatorDefinition(
    id="free_water_deficit",
    name="Free Water Deficit",
    short_name="FWD",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="L",
    description="Calculates free water needed in hypernatremia",
    references=["Adrogue HJ, Madias NE. N Engl J Med. 2000;342(20):1493-1499. PMID: 10816188"],
    specialties=["Critical Care", "Nephrology", "Internal Medicine"],
    notes=["TBW = 0.6 x weight (males), 0.5 (females/elderly)", "Correct slowly: 10-12 mEq/24h"],
    formula=FormulaDefinition(
        formula_text="TBW x ((Na/140) - 1)",
        output_unit="L",
        precision=1,
        parameters=[
            FormulaParameter(name="sodium", display_name="Serum Sodium", unit="mEq/L", min_value=145, max_value=190),
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=30, max_value=200),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Free water deficit for replacement",
            recommendations=[
                "Correct Na no faster than 10-12 mEq/24h",
                "Use D5W or hypotonic saline",
                "Account for ongoing losses",
            ]),
    ],
)

# Sodium Correction Rate
SODIUM_CORRECTION_RATE_DEFINITION = CalculatorDefinition(
    id="sodium_correction_rate",
    name="Sodium Correction Rate",
    short_name="Na Rate",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mEq/L per hour",
    description="Monitors rate of sodium correction to avoid osmotic demyelination",
    references=["Sterns RH, et al. J Am Soc Nephrol. 2009;20(11):2289-2291. PMID: 19713306"],
    specialties=["Nephrology", "Critical Care"],
    notes=["Target 8-10 mEq/24h in chronic hyponatremia", "Risk of ODS if overcorrected"],
    formula=FormulaDefinition(
        formula_text="(Na2 - Na1) / Hours",
        output_unit="mEq/L per hour",
        precision=2,
        parameters=[
            FormulaParameter(name="sodium_initial", display_name="Initial Sodium", unit="mEq/L", min_value=100, max_value=180),
            FormulaParameter(name="sodium_current", display_name="Current Sodium", unit="mEq/L", min_value=100, max_value=180),
            FormulaParameter(name="hours", display_name="Hours Elapsed", unit="hours", min_value=1, max_value=72),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=-999, max_score=0.5, risk_level=RiskLevel.LOW,
            interpretation="Safe correction rate (<0.5 mEq/L/hr)",
            recommendations=["Continue current management"]),
        ThresholdInterpretation(min_score=0.5, max_score=1.0, risk_level=RiskLevel.MODERATE,
            interpretation="Borderline correction rate (0.5-1.0 mEq/L/hr)",
            recommendations=["Monitor closely", "May need to slow correction"]),
        ThresholdInterpretation(min_score=1.0, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Rapid correction (>1.0 mEq/L/hr)",
            recommendations=["Risk of ODS", "Consider D5W to re-lower Na", "Target 8-10 mEq/24h total"]),
    ],
)

# Albumin-Corrected Anion Gap
CORRECTED_AG_DEFINITION = CalculatorDefinition(
    id="corrected_ag",
    name="Albumin-Corrected Anion Gap",
    short_name="Corrected AG",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="mEq/L",
    description="Adjusts anion gap for hypoalbuminemia",
    references=["Figge J, et al. J Lab Clin Med. 1998;131(3):217-225. PMID: 9523846"],
    specialties=["Critical Care", "Nephrology", "Emergency Medicine"],
    notes=["AG increases ~2.5 mEq/L for each 1 g/dL decrease in albumin below 4"],
    formula=FormulaDefinition(
        formula_text="AG + 2.5 x (4.0 - Albumin)",
        output_unit="mEq/L",
        precision=1,
        parameters=[
            FormulaParameter(name="anion_gap", display_name="Anion Gap", unit="mEq/L", min_value=3, max_value=50),
            FormulaParameter(name="albumin", display_name="Albumin", unit="g/dL", min_value=1.0, max_value=5.5),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=12, risk_level=RiskLevel.LOW,
            interpretation="Normal corrected AG", recommendations=["No AG metabolic acidosis"]),
        ThresholdInterpretation(min_score=12, max_score=20, risk_level=RiskLevel.MODERATE,
            interpretation="Elevated corrected AG", recommendations=["AG metabolic acidosis present"]),
        ThresholdInterpretation(min_score=20, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High corrected AG", recommendations=["Significant AG acidosis", "MUDPILES workup"]),
    ],
)


# ============================================================================
# TIER 4 - FLUID/DOSING CALCULATORS
# ============================================================================

# Ideal Body Weight
IDEAL_BODY_WEIGHT_DEFINITION = CalculatorDefinition(
    id="ideal_body_weight",
    name="Ideal Body Weight (Devine)",
    short_name="IBW",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.DECIMAL,
    score_unit="kg",
    description="Ideal body weight for drug dosing and ventilator settings",
    references=["Devine BJ. Drug Intell Clin Pharm. 1974;8:650-655"],
    specialties=["Pharmacy", "Critical Care", "Pulmonology"],
    notes=["Males: 50 + 2.3 x (height in inches - 60)", "Females: 45.5 + 2.3 x (height in inches - 60)"],
    formula=FormulaDefinition(
        formula_text="Males: 50 + 2.3*(height[in]-60); Females: 45.5 + 2.3*(height[in]-60)",
        output_unit="kg",
        precision=1,
        parameters=[
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=120, max_value=220),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Ideal body weight calculated",
            recommendations=["Use for aminoglycoside dosing", "Use for tidal volume (6-8 mL/kg IBW)"]),
    ],
)

# Adjusted Body Weight
ADJUSTED_BODY_WEIGHT_DEFINITION = CalculatorDefinition(
    id="adjusted_body_weight",
    name="Adjusted Body Weight",
    short_name="AdjBW",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.DECIMAL,
    score_unit="kg",
    description="Adjusted weight for obese patients (drug dosing)",
    references=["Green B, Duffull SB. Br J Clin Pharmacol. 2004;57(4):367-370. PMID: 15025734"],
    specialties=["Pharmacy", "Critical Care"],
    notes=["Use when actual > 120% IBW", "AdjBW = IBW + 0.4 x (Actual - IBW)"],
    formula=FormulaDefinition(
        formula_text="IBW + 0.4 x (Actual - IBW)",
        output_unit="kg",
        precision=1,
        parameters=[
            FormulaParameter(name="actual_weight", display_name="Actual Weight", unit="kg", min_value=40, max_value=300),
            FormulaParameter(name="ideal_weight", display_name="Ideal Body Weight", unit="kg", min_value=30, max_value=150),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Adjusted body weight for dosing",
            recommendations=["Use for aminoglycosides in obese", "Use for enoxaparin in obesity"]),
    ],
)

# Body Surface Area (Du Bois)
BSA_DUBOIS_DEFINITION = CalculatorDefinition(
    id="bsa_dubois",
    name="Body Surface Area (Du Bois)",
    short_name="BSA",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.DECIMAL,
    score_unit="m2",
    description="Body surface area using Du Bois formula",
    references=["Du Bois D, Du Bois EF. Arch Intern Med. 1916;17:863-871"],
    specialties=["Oncology", "Nephrology", "Cardiology"],
    notes=["Used for chemotherapy dosing", "Most widely used BSA formula"],
    formula=FormulaDefinition(
        formula_text="0.007184 x Height^0.725 x Weight^0.425",
        output_unit="m2",
        precision=2,
        parameters=[
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=100, max_value=250),
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=20, max_value=300),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Body surface area calculated",
            recommendations=["Average adult ~1.7 m2", "Use for chemotherapy dosing"]),
    ],
)

# Body Surface Area (Mosteller)
BSA_MOSTELLER_DEFINITION = CalculatorDefinition(
    id="bsa_mosteller",
    name="Body Surface Area (Mosteller)",
    short_name="BSA Mosteller",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.DECIMAL,
    score_unit="m2",
    description="Body surface area using Mosteller formula",
    references=["Mosteller RD. N Engl J Med. 1987;317(17):1098. PMID: 3657876"],
    specialties=["Oncology", "Pediatrics"],
    notes=["Simpler calculation than Du Bois", "Widely used in pediatrics"],
    formula=FormulaDefinition(
        formula_text="sqrt((Height x Weight) / 3600)",
        output_unit="m2",
        precision=2,
        parameters=[
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=50, max_value=250),
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=2, max_value=300),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Body surface area calculated",
            recommendations=["Easier calculation", "Commonly used in pediatrics"]),
    ],
)

# Lean Body Weight
LBW_DEFINITION = CalculatorDefinition(
    id="lbw",
    name="Lean Body Weight (Boer)",
    short_name="LBW",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.DECIMAL,
    score_unit="kg",
    description="Lean body mass estimation",
    references=["Boer P. Am J Clin Nutr. 1984;39(3):451-454. PMID: 6695875"],
    specialties=["Pharmacy", "Anesthesiology"],
    notes=["Males: 0.407W + 0.267H - 19.2", "Females: 0.252W + 0.473H - 48.3"],
    formula=FormulaDefinition(
        formula_text="Males: 0.407W + 0.267H - 19.2; Females: 0.252W + 0.473H - 48.3",
        output_unit="kg",
        precision=1,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=30, max_value=300),
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=120, max_value=220),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Lean body weight calculated",
            recommendations=["Used for some anesthetic agents", "May be preferred for propofol dosing"]),
    ],
)

# IV Fluid Rate Calculator
IV_FLUID_RATE_DEFINITION = CalculatorDefinition(
    id="iv_fluid_rate",
    name="IV Fluid Rate Calculator",
    short_name="IV Rate",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.GENERAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/hr",
    description="Calculates IV infusion rate from volume and time",
    references=["Standard pharmacy calculation"],
    specialties=["Nursing", "Pharmacy", "Critical Care"],
    formula=FormulaDefinition(
        formula_text="Volume / Time",
        output_unit="mL/hr",
        precision=1,
        parameters=[
            FormulaParameter(name="volume", display_name="Volume", unit="mL", min_value=1, max_value=5000),
            FormulaParameter(name="hours", display_name="Infusion Time", unit="hours", min_value=0.5, max_value=24),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="IV infusion rate calculated",
            recommendations=["Verify with pharmacy for high-risk infusions"]),
    ],
)

# 24-Hour Urine Creatinine Clearance
CRCL_24HR_DEFINITION = CalculatorDefinition(
    id="crcl_24hr",
    name="Creatinine Clearance (24-hour Urine)",
    short_name="CrCl 24hr",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min",
    description="Measured creatinine clearance from 24-hour urine collection",
    references=["Levey AS, et al. J Am Soc Nephrol. 1999;10(2):397-403. PMID: 10215341"],
    specialties=["Nephrology", "Internal Medicine"],
    notes=["More accurate than estimated GFR in some populations", "Requires complete urine collection"],
    formula=FormulaDefinition(
        formula_text="(UCr x Uvol) / (PCr x 1440)",
        output_unit="mL/min",
        precision=0,
        parameters=[
            FormulaParameter(name="urine_creatinine", display_name="Urine Creatinine", unit="mg/dL", min_value=10, max_value=500),
            FormulaParameter(name="urine_volume", display_name="24h Urine Volume", unit="mL", min_value=400, max_value=5000),
            FormulaParameter(name="plasma_creatinine", display_name="Plasma Creatinine", unit="mg/dL", min_value=0.3, max_value=15),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=90, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Normal CrCl", recommendations=["Normal kidney function"]),
        ThresholdInterpretation(min_score=60, max_score=90, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mild impairment", recommendations=["Stage 2 CKD if persistent"]),
        ThresholdInterpretation(min_score=30, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate impairment", recommendations=["Nephrology referral"]),
        ThresholdInterpretation(min_score=15, max_score=30, risk_level=RiskLevel.HIGH,
            interpretation="Severe impairment", recommendations=["RRT planning"]),
        ThresholdInterpretation(min_score=0, max_score=15, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Kidney failure", recommendations=["Dialysis evaluation"]),
    ],
)

# Protein-Creatinine Ratio to 24h Conversion
PCR_TO_24HR_DEFINITION = CalculatorDefinition(
    id="pcr_to_24hr",
    name="Protein-Creatinine Ratio to 24h Conversion",
    short_name="PCR->24h",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="g/24hr",
    description="Estimates 24-hour proteinuria from spot protein:creatinine ratio",
    references=["Ginsberg JM, et al. N Engl J Med. 1983;309(25):1543-1546. PMID: 6656849"],
    specialties=["Nephrology", "Internal Medicine"],
    notes=["Spot PCR correlates with 24h protein", "Most accurate with first morning void"],
    formula=FormulaDefinition(
        formula_text="PCR (mg/mg) ~ g/24hr proteinuria",
        output_unit="g/24hr",
        precision=2,
        parameters=[
            FormulaParameter(name="urine_protein", display_name="Urine Protein", unit="mg/dL", min_value=1, max_value=5000),
            FormulaParameter(name="urine_creatinine", display_name="Urine Creatinine", unit="mg/dL", min_value=10, max_value=500),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=0.15, risk_level=RiskLevel.LOW,
            interpretation="Normal (<150 mg/24h)", recommendations=["No significant proteinuria"]),
        ThresholdInterpretation(min_score=0.15, max_score=0.5, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mild proteinuria (150-500 mg/24h)", recommendations=["Monitor, evaluate causes"]),
        ThresholdInterpretation(min_score=0.5, max_score=3.5, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate proteinuria (0.5-3.5 g/24h)", recommendations=["Nephrology evaluation"]),
        ThresholdInterpretation(min_score=3.5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Nephrotic range (>3.5 g/24h)", recommendations=["Nephrotic syndrome workup"]),
    ],
)

# Albumin-Creatinine Ratio
ACR_DEFINITION = CalculatorDefinition(
    id="acr",
    name="Urine Albumin-Creatinine Ratio (uACR)",
    short_name="uACR",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mg/g",
    description="Detects albuminuria for CKD staging",
    references=["KDIGO 2012 Clinical Practice Guideline for CKD. Kidney Int Suppl. 2013;3:1-150"],
    specialties=["Nephrology", "Endocrinology", "Primary Care"],
    notes=["Key marker for CKD staging", "Use with eGFR for complete assessment"],
    formula=FormulaDefinition(
        formula_text="Urine Albumin / Urine Creatinine",
        output_unit="mg/g",
        precision=1,
        parameters=[
            FormulaParameter(name="urine_albumin", display_name="Urine Albumin", unit="mg/L", min_value=1, max_value=10000),
            FormulaParameter(name="urine_creatinine", display_name="Urine Creatinine", unit="g/L", min_value=0.1, max_value=5),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=30, risk_level=RiskLevel.LOW,
            interpretation="A1: Normal to mildly increased (<30 mg/g)",
            recommendations=["Normal albuminuria", "Annual screening if diabetic"]),
        ThresholdInterpretation(min_score=30, max_score=300, risk_level=RiskLevel.MODERATE,
            interpretation="A2: Moderately increased (30-300 mg/g)",
            recommendations=["Microalbuminuria", "ACE-I or ARB therapy", "Optimize BP and glucose"]),
        ThresholdInterpretation(min_score=300, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="A3: Severely increased (>300 mg/g)",
            recommendations=["Macroalbuminuria", "Nephrology referral", "Aggressive risk factor control"]),
    ],
)


# ============================================================================
# TIER 5 - METABOLIC & ENDOCRINE CALCULATORS
# ============================================================================

# BMI Classification (WHO/Asian)
BMI_ASIAN_DEFINITION = CalculatorDefinition(
    id="bmi_asian",
    name="BMI Classification (Asian)",
    short_name="BMI Asian",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="kg/m2",
    description="BMI with Asian-specific cutoffs for obesity risk",
    references=["WHO Expert Consultation. Lancet. 2004;363(9403):157-163. PMID: 14726171"],
    specialties=["Internal Medicine", "Endocrinology", "Primary Care"],
    notes=["Asian cutoffs: Overweight >=23, Obese >=27.5", "Higher risk at lower BMI in Asian populations"],
    formula=FormulaDefinition(
        formula_text="Weight(kg) / Height(m)^2",
        output_unit="kg/m2",
        precision=1,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=20, max_value=300),
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=100, max_value=250),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=18.5, risk_level=RiskLevel.MODERATE,
            interpretation="Underweight (<18.5)", recommendations=["Nutritional assessment"]),
        ThresholdInterpretation(min_score=18.5, max_score=23, risk_level=RiskLevel.LOW,
            interpretation="Normal (18.5-22.9)", recommendations=["Healthy weight"]),
        ThresholdInterpretation(min_score=23, max_score=27.5, risk_level=RiskLevel.MODERATE,
            interpretation="Overweight (23-27.4) - At risk", recommendations=["Lifestyle modifications"]),
        ThresholdInterpretation(min_score=27.5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Obese (>=27.5)", recommendations=["Weight loss intervention"]),
    ],
)

# Harris-Benedict BMR
HARRIS_BENEDICT_DEFINITION = CalculatorDefinition(
    id="harris_benedict",
    name="Basal Metabolic Rate (Harris-Benedict)",
    short_name="BMR-HB",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="kcal/day",
    description="Estimates basal energy expenditure",
    references=["Harris JA, Benedict FG. Proc Natl Acad Sci. 1918;4(12):370-373"],
    specialties=["Nutrition", "Critical Care", "Endocrinology"],
    notes=["Males: 88.362 + 13.397W + 4.799H - 5.677A", "Females: 447.593 + 9.247W + 3.098H - 4.330A"],
    formula=FormulaDefinition(
        formula_text="Males: 88.362+13.397W+4.799H-5.677A; Females: 447.593+9.247W+3.098H-4.330A",
        output_unit="kcal/day",
        precision=0,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=30, max_value=200),
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=120, max_value=220),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Basal metabolic rate",
            recommendations=["Multiply by activity factor for total needs", "Sedentary: 1.2, Light: 1.375, Moderate: 1.55"]),
    ],
)

# Mifflin-St Jeor BMR
MIFFLIN_ST_JEOR_DEFINITION = CalculatorDefinition(
    id="mifflin_st_jeor",
    name="Basal Metabolic Rate (Mifflin-St Jeor)",
    short_name="BMR-MSJ",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="kcal/day",
    description="More accurate BMR estimate than Harris-Benedict",
    references=["Mifflin MD, et al. Am J Clin Nutr. 1990;51(2):241-247. PMID: 2305711"],
    specialties=["Nutrition", "Endocrinology"],
    notes=["Males: 10W + 6.25H - 5A + 5", "Females: 10W + 6.25H - 5A - 161", "Preferred over Harris-Benedict"],
    formula=FormulaDefinition(
        formula_text="Males: 10W+6.25H-5A+5; Females: 10W+6.25H-5A-161",
        output_unit="kcal/day",
        precision=0,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=30, max_value=200),
            FormulaParameter(name="height", display_name="Height", unit="cm", min_value=120, max_value=220),
            FormulaParameter(name="age", display_name="Age", unit="years", min_value=18, max_value=100),
            FormulaParameter(name="female", display_name="Female", unit="", min_value=0, max_value=1),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Basal metabolic rate",
            recommendations=["More accurate than Harris-Benedict", "Multiply by activity factor"]),
    ],
)

# HOMA-IR
HOMA_IR_DEFINITION = CalculatorDefinition(
    id="homa_ir",
    name="HOMA-IR (Insulin Resistance)",
    short_name="HOMA-IR",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Homeostatic Model Assessment for Insulin Resistance",
    references=["Matthews DR, et al. Diabetologia. 1985;28(7):412-419. PMID: 3899825"],
    specialties=["Endocrinology", "Internal Medicine"],
    notes=["Fasting insulin x Fasting glucose / 405", "Higher = more insulin resistant"],
    formula=FormulaDefinition(
        formula_text="(Fasting Insulin x Fasting Glucose) / 405",
        output_unit="",
        precision=2,
        parameters=[
            FormulaParameter(name="fasting_insulin", display_name="Fasting Insulin", unit="uU/mL", min_value=1, max_value=100),
            FormulaParameter(name="fasting_glucose", display_name="Fasting Glucose", unit="mg/dL", min_value=50, max_value=400),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1.0, risk_level=RiskLevel.LOW,
            interpretation="HOMA-IR <1.0 - Insulin sensitive",
            recommendations=["Normal insulin sensitivity"]),
        ThresholdInterpretation(min_score=1.0, max_score=2.5, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="HOMA-IR 1.0-2.5 - Normal range",
            recommendations=["Monitor if other risk factors"]),
        ThresholdInterpretation(min_score=2.5, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="HOMA-IR >2.5 - Insulin resistant",
            recommendations=["Lifestyle modifications", "Screen for metabolic syndrome"]),
    ],
)

# HOMA-B
HOMA_B_DEFINITION = CalculatorDefinition(
    id="homa_b",
    name="HOMA-B (Beta Cell Function)",
    short_name="HOMA-B",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="%",
    description="Homeostatic Model Assessment for Beta Cell Function",
    references=["Matthews DR, et al. Diabetologia. 1985;28(7):412-419. PMID: 3899825"],
    specialties=["Endocrinology"],
    notes=["(20 x Fasting Insulin) / (Fasting Glucose - 3.5)", "Expressed as % of normal"],
    formula=FormulaDefinition(
        formula_text="(360 x Fasting Insulin) / (Fasting Glucose - 63)",
        output_unit="%",
        precision=1,
        parameters=[
            FormulaParameter(name="fasting_insulin", display_name="Fasting Insulin", unit="uU/mL", min_value=1, max_value=100),
            FormulaParameter(name="fasting_glucose", display_name="Fasting Glucose", unit="mg/dL", min_value=70, max_value=400),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=80, risk_level=RiskLevel.MODERATE,
            interpretation="HOMA-B <80% - Decreased beta cell function",
            recommendations=["May indicate early diabetes", "Consider C-peptide testing"]),
        ThresholdInterpretation(min_score=80, max_score=120, risk_level=RiskLevel.LOW,
            interpretation="HOMA-B 80-120% - Normal beta cell function",
            recommendations=["Normal function"]),
        ThresholdInterpretation(min_score=120, max_score=None, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="HOMA-B >120% - Increased (compensatory)",
            recommendations=["May indicate insulin resistance with compensation"]),
    ],
)

# Free Thyroxine Index
FTI_DEFINITION = CalculatorDefinition(
    id="fti",
    name="Free Thyroxine Index (FTI)",
    short_name="FTI",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.METABOLIC,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Estimates free T4 when direct measurement unavailable",
    references=["Clark F, Horn DB. J Clin Endocrinol Metab. 1965;25(1):39-45"],
    specialties=["Endocrinology", "Internal Medicine"],
    notes=["FTI = T4 x T3RU / 100", "Corrects for binding protein abnormalities"],
    formula=FormulaDefinition(
        formula_text="T4 x T3RU / 100",
        output_unit="",
        precision=1,
        parameters=[
            FormulaParameter(name="t4", display_name="Total T4", unit="ug/dL", min_value=1, max_value=25),
            FormulaParameter(name="t3ru", display_name="T3 Resin Uptake", unit="%", min_value=15, max_value=50),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1.5, risk_level=RiskLevel.MODERATE,
            interpretation="FTI <1.5 - Possible hypothyroidism",
            recommendations=["Check TSH", "Consider free T4"]),
        ThresholdInterpretation(min_score=1.5, max_score=4.5, risk_level=RiskLevel.LOW,
            interpretation="FTI 1.5-4.5 - Normal",
            recommendations=["Normal thyroid function"]),
        ThresholdInterpretation(min_score=4.5, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="FTI >4.5 - Possible hyperthyroidism",
            recommendations=["Check TSH", "Consider T3"]),
    ],
)


# ============================================================================
# TIER 6 - ADDITIONAL RENAL/HEPATIC CALCULATORS
# ============================================================================

# UKELD Score
UKELD_DEFINITION = CalculatorDefinition(
    id="ukeld",
    name="UKELD Score (UK Model for End-Stage Liver Disease)",
    short_name="UKELD",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.DECIMAL,
    score_unit="points",
    description="UK liver transplant allocation scoring system",
    references=["Barber K, et al. Liver Transpl. 2011;17(2):181-186. PMID: 21280192"],
    specialties=["Hepatology", "Transplant"],
    notes=["Used in UK for transplant listing", "UKELD >=49 eligible for listing"],
    formula=FormulaDefinition(
        formula_text="5.395*ln(INR) + 1.485*ln(Cr) + 3.13*ln(Bili) - 81.565*ln(Na) + 435",
        output_unit="points",
        precision=0,
        parameters=[
            FormulaParameter(name="inr", display_name="INR", unit="", min_value=1.0, max_value=10),
            FormulaParameter(name="creatinine", display_name="Creatinine", unit="umol/L", min_value=50, max_value=500),
            FormulaParameter(name="bilirubin", display_name="Bilirubin", unit="umol/L", min_value=5, max_value=1000),
            FormulaParameter(name="sodium", display_name="Sodium", unit="mmol/L", min_value=110, max_value=150),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=49, risk_level=RiskLevel.MODERATE,
            interpretation="UKELD <49 - Below listing threshold",
            recommendations=["Not meeting UK listing criteria", "Continue monitoring"]),
        ThresholdInterpretation(min_score=49, max_score=60, risk_level=RiskLevel.HIGH,
            interpretation="UKELD 49-60 - Eligible for listing",
            recommendations=["Meets UK transplant listing criteria"]),
        ThresholdInterpretation(min_score=60, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="UKELD >60 - High priority",
            recommendations=["High priority for transplant"]),
    ],
)

# King's College Criteria (Paracetamol)
KINGS_COLLEGE_APAP_DEFINITION = CalculatorDefinition(
    id="kings_college_apap",
    name="King's College Criteria (Paracetamol)",
    short_name="King's APAP",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.INTEGER,
    score_unit="",
    description="Predicts need for liver transplant in paracetamol-induced ALF",
    references=["O'Grady JG, et al. Gastroenterology. 1989;97(2):439-445. PMID: 2490426"],
    specialties=["Hepatology", "Critical Care", "Toxicology"],
    notes=["Arterial pH <7.3 after resuscitation is sufficient", "Or all three: PT >100, Cr >3.4, Grade III-IV HE"],
    criteria=[
        ScoringCriterion("ph_below_7_3", "Arterial pH <7.3 (after resuscitation)", 10, "Single criterion sufficient"),
        ScoringCriterion("pt_over_100", "PT >100 seconds (INR >6.5)", 1, ""),
        ScoringCriterion("creatinine_over_3_4", "Creatinine >3.4 mg/dL", 1, ""),
        ScoringCriterion("grade_3_4_encephalopathy", "Grade III-IV encephalopathy", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Does not meet King's criteria",
            recommendations=["Continue supportive care", "N-acetylcysteine", "Serial monitoring"]),
        ThresholdInterpretation(min_score=3, max_score=10, risk_level=RiskLevel.HIGH,
            interpretation="Meets King's criteria (all 3 secondary)",
            recommendations=["Urgent transplant evaluation", "Transfer to transplant center"]),
        ThresholdInterpretation(min_score=10, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Meets King's criteria (pH <7.3)",
            recommendations=["Emergent transplant evaluation", "Very poor prognosis without transplant"]),
    ],
)

# King's College Criteria (Non-Paracetamol)
KINGS_COLLEGE_NON_APAP_DEFINITION = CalculatorDefinition(
    id="kings_college_non_apap",
    name="King's College Criteria (Non-Paracetamol)",
    short_name="King's Non-APAP",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.HEPATIC,
    output_type=OutputType.INTEGER,
    score_unit="",
    description="Predicts need for liver transplant in non-paracetamol ALF",
    references=["O'Grady JG, et al. Gastroenterology. 1989;97(2):439-445. PMID: 2490426"],
    specialties=["Hepatology", "Critical Care"],
    notes=["PT >100 (INR >6.5) alone is sufficient", "Or any 3 of the 5 criteria"],
    criteria=[
        ScoringCriterion("pt_over_100", "PT >100 seconds (INR >6.5)", 10, "Single criterion sufficient"),
        ScoringCriterion("age_unfavorable", "Age <10 or >40 years", 1, ""),
        ScoringCriterion("unfavorable_etiology", "Non-A/Non-B hepatitis, drug toxicity, Wilson's", 1, ""),
        ScoringCriterion("jaundice_over_7_days", "Jaundice >7 days before encephalopathy", 1, ""),
        ScoringCriterion("pt_over_50", "PT >50 seconds (INR >3.5)", 1, ""),
        ScoringCriterion("bilirubin_over_17", "Bilirubin >17.5 mg/dL", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Does not meet King's criteria",
            recommendations=["Supportive care", "Serial monitoring"]),
        ThresholdInterpretation(min_score=3, max_score=10, risk_level=RiskLevel.HIGH,
            interpretation="Meets King's criteria (3 of 5)",
            recommendations=["Urgent transplant evaluation"]),
        ThresholdInterpretation(min_score=10, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Meets King's criteria (PT >100)",
            recommendations=["Emergent transplant evaluation"]),
    ],
)

# AKI Staging (KDIGO)
KDIGO_AKI_DEFINITION = CalculatorDefinition(
    id="kdigo_aki",
    name="KDIGO AKI Staging",
    short_name="KDIGO AKI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.INTEGER,
    score_unit="Stage",
    description="KDIGO criteria for Acute Kidney Injury staging",
    references=["KDIGO Clinical Practice Guideline for AKI. Kidney Int Suppl. 2012;2:1-138"],
    specialties=["Nephrology", "Critical Care"],
    notes=["Based on creatinine rise or urine output", "Use worst criterion for staging"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="creatinine",
            display_name="Creatinine Criterion",
            levels=[
                ("stage_1", 1, "Stage 1: 1.5-1.9x baseline or >=0.3 mg/dL increase"),
                ("stage_2", 2, "Stage 2: 2.0-2.9x baseline"),
                ("stage_3", 3, "Stage 3: 3.0x baseline or >=4.0 mg/dL or RRT"),
            ],
        ),
        MultiLevelCriterion(
            name="urine_output",
            display_name="Urine Output Criterion",
            levels=[
                ("stage_1_uo", 1, "Stage 1: <0.5 mL/kg/hr for 6-12 hours"),
                ("stage_2_uo", 2, "Stage 2: <0.5 mL/kg/hr for >=12 hours"),
                ("stage_3_uo", 3, "Stage 3: <0.3 mL/kg/hr for >=24h or anuria >=12h"),
            ],
        ),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="No AKI", recommendations=["Continue monitoring"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.MODERATE,
            interpretation="AKI Stage 1", recommendations=["Optimize volume status", "Avoid nephrotoxins"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.HIGH,
            interpretation="AKI Stage 2", recommendations=["Nephrology consultation", "Close monitoring"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="AKI Stage 3", recommendations=["Urgent nephrology", "RRT evaluation"]),
    ],
)

# RIFLE Criteria
RIFLE_DEFINITION = CalculatorDefinition(
    id="rifle",
    name="RIFLE Criteria for AKI",
    short_name="RIFLE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.CATEGORY,
    score_unit="",
    description="Risk, Injury, Failure, Loss, End-stage criteria for AKI",
    references=["Bellomo R, et al. Crit Care. 2004;8(4):R204-R212. PMID: 15312219"],
    specialties=["Nephrology", "Critical Care"],
    notes=["Predecessor to AKIN and KDIGO", "R-I-F are acute, L-E are outcomes"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="gfr_criterion",
            display_name="GFR/Creatinine Criterion",
            levels=[
                ("risk", 1, "Risk: 1.5x Cr or GFR decrease >25%"),
                ("injury", 2, "Injury: 2x Cr or GFR decrease >50%"),
                ("failure", 3, "Failure: 3x Cr or GFR decrease >75% or Cr >=4 with acute rise"),
                ("loss", 4, "Loss: Persistent AKI >4 weeks"),
                ("esrd", 5, "ESRD: Persistent >3 months"),
            ],
        ),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="No AKI by RIFLE", recommendations=["Monitor"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.MODERATE,
            interpretation="RIFLE-Risk", recommendations=["Optimize hemodynamics"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.HIGH,
            interpretation="RIFLE-Injury", recommendations=["Nephrology involvement"]),
        ThresholdInterpretation(min_score=3, max_score=4, risk_level=RiskLevel.VERY_HIGH,
            interpretation="RIFLE-Failure", recommendations=["RRT consideration"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="RIFLE-Loss/ESRD", recommendations=["Chronic RRT"]),
    ],
)

# AKIN Criteria
AKIN_DEFINITION = CalculatorDefinition(
    id="akin",
    name="AKIN Criteria for AKI",
    short_name="AKIN",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.INTEGER,
    score_unit="Stage",
    description="Acute Kidney Injury Network staging criteria",
    references=["Mehta RL, et al. Crit Care. 2007;11(2):R31. PMID: 17331245"],
    specialties=["Nephrology", "Critical Care"],
    notes=["Changes in 48-hour window", "Predecessor to KDIGO"],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="creatinine",
            display_name="Creatinine Criterion",
            levels=[
                ("stage_1", 1, "Stage 1: Cr increase >=0.3 mg/dL or 1.5-2x baseline"),
                ("stage_2", 2, "Stage 2: Cr increase 2-3x baseline"),
                ("stage_3", 3, "Stage 3: Cr increase >3x or >=4.0 with acute rise or RRT"),
            ],
        ),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="No AKI", recommendations=["Continue monitoring"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.MODERATE,
            interpretation="AKIN Stage 1", recommendations=["Volume optimization"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.HIGH,
            interpretation="AKIN Stage 2", recommendations=["Nephrology consultation"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="AKIN Stage 3", recommendations=["RRT evaluation"]),
    ],
)

# Urinary Indices Panel
URINARY_INDICES_DEFINITION = CalculatorDefinition(
    id="urinary_indices",
    name="Urinary Indices Panel",
    short_name="Urine Indices",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Combined FENa and FEUrea for AKI evaluation",
    references=["Perazella MA, et al. Clin J Am Soc Nephrol. 2012;7(1):167-174. PMID: 22096038"],
    specialties=["Nephrology", "Critical Care"],
    notes=["Calculate both FENa and FEUrea", "FEUrea more reliable with diuretics"],
    formula=FormulaDefinition(
        formula_text="FENa and FEUrea calculation",
        output_unit="",
        precision=2,
        parameters=[
            FormulaParameter(name="urine_sodium", display_name="Urine Na", unit="mEq/L", min_value=1, max_value=300),
            FormulaParameter(name="plasma_sodium", display_name="Plasma Na", unit="mEq/L", min_value=100, max_value=180),
            FormulaParameter(name="urine_creatinine", display_name="Urine Cr", unit="mg/dL", min_value=5, max_value=500),
            FormulaParameter(name="plasma_creatinine", display_name="Plasma Cr", unit="mg/dL", min_value=0.2, max_value=20),
            FormulaParameter(name="urine_urea", display_name="Urine Urea", unit="mg/dL", min_value=50, max_value=3000, required=False),
            FormulaParameter(name="plasma_urea", display_name="BUN", unit="mg/dL", min_value=5, max_value=200, required=False),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Urinary indices calculated",
            recommendations=[
                "FENa <1% + FEUrea <35%: Prerenal",
                "FENa >2% + FEUrea >50%: ATN",
                "Mixed results: Clinical correlation needed",
            ]),
    ],
)


# ============================================================================
# CRITICAL CARE & EMERGENCY MEDICINE CALCULATORS - TIER 1: SEPSIS
# ============================================================================

# Sepsis-3 Criteria
SEPSIS_3_DEFINITION = CalculatorDefinition(
    id="sepsis_3",
    name="Sepsis-3 Criteria",
    short_name="Sepsis-3",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.CATEGORY,
    score_unit="",
    description="Defines sepsis as life-threatening organ dysfunction from dysregulated host response to infection",
    references=[
        "Singer M, et al. JAMA. 2016;315(8):801-810. PMID: 26903338",
        "Seymour CW, et al. JAMA. 2016;315(8):762-774. PMID: 26903335",
    ],
    specialties=["Critical Care", "Emergency Medicine", "Internal Medicine"],
    notes=[
        "Sepsis = Suspected infection + SOFA increase ≥2 from baseline",
        "Septic shock = Sepsis + vasopressors to maintain MAP ≥65 + lactate >2 despite adequate resuscitation",
        "qSOFA ≥2 is screening tool, not diagnostic criteria",
    ],
    criteria=[
        ScoringCriterion("suspected_infection", "Suspected or documented infection", 1, "Clinical suspicion or confirmed infection"),
        ScoringCriterion("sofa_increase_2", "SOFA increase ≥2 from baseline", 1, "Acute change in SOFA score ≥2 points"),
        ScoringCriterion("vasopressors_needed", "Vasopressors to maintain MAP ≥65", 1, "For septic shock criteria"),
        ScoringCriterion("lactate_over_2", "Lactate >2 mmol/L despite fluids", 1, "For septic shock criteria"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Sepsis criteria not met",
            recommendations=["Continue monitoring", "Investigate for infection if suspected"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.HIGH,
            interpretation="Sepsis - organ dysfunction due to infection",
            recommendations=["Hour-1 bundle: cultures, lactate, antibiotics, fluids", "Source control", "ICU level care"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Septic shock - sepsis with persistent hypotension",
            recommendations=["Vasopressors for MAP ≥65", "Serial lactate monitoring", "Consider stress-dose steroids"]),
    ],
)

# SAPS II - Simplified Acute Physiology Score II
SAPS_II_DEFINITION = CalculatorDefinition(
    id="saps_ii",
    name="Simplified Acute Physiology Score II (SAPS II)",
    short_name="SAPS II",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="ICU mortality prediction using worst values in first 24 hours",
    references=["Le Gall JR, et al. JAMA. 1993;270(24):2957-2963. PMID: 8254858"],
    specialties=["Critical Care", "Anesthesiology"],
    notes=["Score range 0-163", "Uses worst values in first 24h of ICU", "Excludes burns, cardiac surgery"],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[
                ("lt_40", 0, "<40 (0)"), ("40_59", 7, "40-59 (+7)"), ("60_69", 12, "60-69 (+12)"),
                ("70_74", 15, "70-74 (+15)"), ("75_79", 16, "75-79 (+16)"), ("gte_80", 18, "≥80 (+18)"),
            ], description="Age in years"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("lt_40", 11, "<40 (+11)"), ("40_69", 2, "40-69 (+2)"), ("70_119", 0, "70-119 (0)"),
                ("120_159", 4, "120-159 (+4)"), ("gte_160", 7, "≥160 (+7)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="systolic_bp", display_name="Systolic BP",
            levels=[
                ("lt_70", 13, "<70 (+13)"), ("70_99", 5, "70-99 (+5)"), ("100_199", 0, "100-199 (0)"), ("gte_200", 2, "≥200 (+2)"),
            ], description="Systolic BP mmHg"),
        MultiLevelCriterion(name="temperature", display_name="Temperature",
            levels=[("lt_39", 0, "<39°C (0)"), ("gte_39", 3, "≥39°C (+3)")], description="Temperature °C"),
        MultiLevelCriterion(name="pao2_fio2", display_name="PaO2/FiO2 (if ventilated)",
            levels=[
                ("lt_100", 11, "<100 (+11)"), ("100_199", 9, "100-199 (+9)"), ("gte_200", 6, "≥200 (+6)"),
            ], description="Only if mechanically ventilated"),
        MultiLevelCriterion(name="urine_output", display_name="Urine Output",
            levels=[
                ("lt_500", 11, "<500 mL/day (+11)"), ("500_999", 4, "500-999 mL/day (+4)"), ("gte_1000", 0, "≥1000 mL/day (0)"),
            ], description="24h urine output"),
        MultiLevelCriterion(name="bun", display_name="BUN",
            levels=[
                ("lt_28", 0, "<28 mg/dL (0)"), ("28_83", 6, "28-83 mg/dL (+6)"), ("gte_84", 10, "≥84 mg/dL (+10)"),
            ], description="Blood urea nitrogen"),
        MultiLevelCriterion(name="wbc", display_name="WBC",
            levels=[
                ("lt_1", 12, "<1.0 (+12)"), ("1_19", 0, "1.0-19.9 (0)"), ("gte_20", 3, "≥20 (+3)"),
            ], description="WBC ×10³/µL"),
        MultiLevelCriterion(name="potassium", display_name="Potassium",
            levels=[
                ("lt_3", 3, "<3.0 (+3)"), ("3_4_9", 0, "3.0-4.9 (0)"), ("gte_5", 3, "≥5.0 (+3)"),
            ], description="Serum potassium mEq/L"),
        MultiLevelCriterion(name="sodium", display_name="Sodium",
            levels=[
                ("lt_125", 5, "<125 (+5)"), ("125_144", 0, "125-144 (0)"), ("gte_145", 1, "≥145 (+1)"),
            ], description="Serum sodium mEq/L"),
        MultiLevelCriterion(name="bicarbonate", display_name="Bicarbonate",
            levels=[
                ("lt_15", 6, "<15 (+6)"), ("15_19", 3, "15-19 (+3)"), ("gte_20", 0, "≥20 (0)"),
            ], description="Serum bicarbonate mEq/L"),
        MultiLevelCriterion(name="bilirubin", display_name="Bilirubin",
            levels=[
                ("lt_4", 0, "<4 mg/dL (0)"), ("4_5_9", 4, "4.0-5.9 mg/dL (+4)"), ("gte_6", 9, "≥6 mg/dL (+9)"),
            ], description="Total bilirubin"),
        MultiLevelCriterion(name="gcs", display_name="Glasgow Coma Scale",
            levels=[
                ("lt_6", 26, "<6 (+26)"), ("6_8", 13, "6-8 (+13)"), ("9_10", 7, "9-10 (+7)"),
                ("11_13", 5, "11-13 (+5)"), ("14_15", 0, "14-15 (0)"),
            ], description="GCS score"),
    ],
    criteria=[
        ScoringCriterion("chronic_disease", "Chronic disease", 9, "Metastatic cancer (+9)"),
        ScoringCriterion("hematologic_malignancy", "Hematologic malignancy", 10, "+10 points"),
        ScoringCriterion("aids", "AIDS", 17, "+17 points"),
        ScoringCriterion("admission_scheduled", "Scheduled surgical admission", 0, "Scheduled surgical (0)"),
        ScoringCriterion("admission_medical", "Medical admission", 6, "Medical (+6)"),
        ScoringCriterion("admission_unscheduled", "Unscheduled surgical admission", 8, "Unscheduled surgical (+8)"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=30, risk_level=RiskLevel.LOW,
            interpretation="SAPS II <30 - Low mortality (~5-10%)", recommendations=["Standard ICU care"]),
        ThresholdInterpretation(min_score=30, max_score=50, risk_level=RiskLevel.MODERATE,
            interpretation="SAPS II 30-49 - Moderate mortality (~20-30%)", recommendations=["Close monitoring", "Early goals of care"]),
        ThresholdInterpretation(min_score=50, max_score=70, risk_level=RiskLevel.HIGH,
            interpretation="SAPS II 50-69 - High mortality (~50-60%)", recommendations=["Goals of care discussion", "Family meeting"]),
        ThresholdInterpretation(min_score=70, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="SAPS II ≥70 - Very high mortality (>80%)", recommendations=["Palliative care consultation"]),
    ],
)

# SAPS III - Simplified Acute Physiology Score III
SAPS_III_DEFINITION = CalculatorDefinition(
    id="saps_iii",
    name="Simplified Acute Physiology Score III (SAPS III)",
    short_name="SAPS III",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="ICU mortality prediction within 1 hour of admission",
    references=["Moreno RP, et al. Intensive Care Med. 2005;31(10):1336-1344. PMID: 16132892"],
    specialties=["Critical Care", "Anesthesiology"],
    notes=["Uses data within 1 hour of ICU admission", "Range 0-217", "Includes pre-ICU factors"],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[
                ("lt_40", 0, "<40 (0)"), ("40_59", 5, "40-59 (+5)"), ("60_69", 9, "60-69 (+9)"),
                ("70_74", 13, "70-74 (+13)"), ("75_79", 15, "75-79 (+15)"), ("gte_80", 18, "≥80 (+18)"),
            ], description="Age"),
        MultiLevelCriterion(name="comorbidities", display_name="Comorbidities",
            levels=[
                ("none", 0, "None (0)"), ("cancer_therapy", 3, "Cancer therapy (+3)"),
                ("chf_nyha_iv", 6, "CHF NYHA IV (+6)"), ("hematologic_cancer", 7, "Hematologic cancer (+7)"),
                ("cirrhosis", 8, "Cirrhosis (+8)"), ("aids", 8, "AIDS (+8)"), ("metastatic_cancer", 11, "Metastatic cancer (+11)"),
            ], description="Chronic health status"),
        MultiLevelCriterion(name="los_before_icu", display_name="Hospital LOS before ICU",
            levels=[
                ("lt_14", 0, "<14 days (0)"), ("14_27", 6, "14-27 days (+6)"), ("gte_28", 7, "≥28 days (+7)"),
            ], description="Days in hospital before ICU"),
        MultiLevelCriterion(name="admission_source", display_name="Admission source",
            levels=[
                ("or", 0, "OR (0)"), ("er", 5, "ER (+5)"), ("other_icu", 7, "Other ICU (+7)"), ("other", 8, "Other (+8)"),
            ], description="Where patient came from"),
        MultiLevelCriterion(name="gcs", display_name="GCS",
            levels=[
                ("3_4", 15, "3-4 (+15)"), ("5", 10, "5 (+10)"), ("6", 7, "6 (+7)"),
                ("7_12", 2, "7-12 (+2)"), ("gte_13", 0, "≥13 (0)"),
            ], description="Glasgow Coma Scale"),
        MultiLevelCriterion(name="bilirubin", display_name="Bilirubin",
            levels=[
                ("lt_2", 0, "<2 mg/dL (0)"), ("2_5_9", 4, "2-5.9 mg/dL (+4)"), ("gte_6", 5, "≥6 mg/dL (+5)"),
            ], description="Total bilirubin"),
        MultiLevelCriterion(name="temperature", display_name="Temperature",
            levels=[("lt_34_5", 7, "<34.5°C (+7)"), ("gte_34_5", 0, "≥34.5°C (0)")], description="Core temperature"),
        MultiLevelCriterion(name="creatinine", display_name="Creatinine",
            levels=[
                ("lt_1_2", 0, "<1.2 mg/dL (0)"), ("1_2_1_9", 2, "1.2-1.9 (+2)"),
                ("2_3_4", 7, "2.0-3.4 (+7)"), ("gte_3_5", 8, "≥3.5 (+8)"),
            ], description="Serum creatinine"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("lt_120", 0, "<120 (0)"), ("gte_120", 5, "≥120 (+5)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="leukocytes", display_name="WBC",
            levels=[
                ("lt_15", 0, "<15 (0)"), ("gte_15", 2, "≥15 (+2)"),
            ], description="WBC ×10³/µL"),
        MultiLevelCriterion(name="platelets", display_name="Platelets",
            levels=[
                ("lt_20", 13, "<20 (+13)"), ("20_49", 8, "20-49 (+8)"),
                ("50_99", 5, "50-99 (+5)"), ("gte_100", 0, "≥100 (0)"),
            ], description="Platelets ×10³/µL"),
        MultiLevelCriterion(name="ph", display_name="Arterial pH",
            levels=[
                ("lt_7_25", 3, "<7.25 (+3)"), ("gte_7_25", 0, "≥7.25 (0)"),
            ], description="Arterial blood pH"),
    ],
    criteria=[
        ScoringCriterion("vent_support", "Mechanical ventilation", 11, "On mechanical ventilation at admission"),
        ScoringCriterion("vasopressors", "Vasopressor use", 3, "Any vasopressor at admission"),
        ScoringCriterion("planned_admission", "Planned ICU admission", 0, "Scheduled/planned ICU"),
        ScoringCriterion("unplanned_admission", "Unplanned ICU admission", 3, "Emergency/unplanned ICU"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=40, risk_level=RiskLevel.LOW,
            interpretation="SAPS III <40 - Low mortality (<10%)", recommendations=["Standard ICU care"]),
        ThresholdInterpretation(min_score=40, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="SAPS III 40-59 - Moderate mortality (~20-40%)", recommendations=["Close monitoring"]),
        ThresholdInterpretation(min_score=60, max_score=80, risk_level=RiskLevel.HIGH,
            interpretation="SAPS III 60-79 - High mortality (~50-70%)", recommendations=["Goals of care discussion"]),
        ThresholdInterpretation(min_score=80, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="SAPS III ≥80 - Very high mortality (>80%)", recommendations=["Palliative consultation"]),
    ],
)

# ============================================================================
# CRITICAL CARE & EMERGENCY - TIER 2: RESPIRATORY & PULMONARY
# ============================================================================

# CRB-65 (No urea - community setting)
CRB65_DEFINITION = CalculatorDefinition(
    id="crb65",
    name="CRB-65 Score",
    short_name="CRB-65",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Community-acquired pneumonia severity without lab tests",
    references=["Bauer TT, et al. Eur Respir J. 2006;27(1):151-157. PMID: 16387949"],
    specialties=["Family Medicine", "Emergency Medicine", "Pulmonology"],
    notes=["Does not require BUN - can be used in community/outpatient settings"],
    criteria=[
        ScoringCriterion("confusion", "Confusion", 1, "New mental confusion"),
        ScoringCriterion("respiratory_rate_30", "Respiratory rate ≥30/min", 1, "RR ≥30 breaths/min"),
        ScoringCriterion("low_blood_pressure", "Low BP (SBP<90 or DBP≤60)", 1, "SBP <90 or DBP ≤60 mmHg"),
        ScoringCriterion("age_65_plus", "Age ≥65 years", 1, "Age 65 or older"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk (mortality 1.2%)", recommendations=["Consider outpatient treatment", "Home with oral antibiotics"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk (mortality 8.2%)", recommendations=["Consider hospital admission", "Close follow-up if outpatient"]),
        ThresholdInterpretation(min_score=2, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk (mortality 31%)", recommendations=["Hospital admission recommended", "Consider ICU evaluation"]),
    ],
)

# SMART-COP Score
SMART_COP_DEFINITION = CalculatorDefinition(
    id="smart_cop",
    name="SMART-COP Score",
    short_name="SMART-COP",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts need for intensive respiratory or vasopressor support (IRVS) in CAP",
    references=["Charles PGP, et al. Clin Infect Dis. 2008;47(3):375-384. PMID: 18558884"],
    specialties=["Pulmonology", "Emergency Medicine", "Critical Care"],
    notes=["Designed to predict ICU admission need", "More accurate than PSI for IRVS prediction"],
    criteria=[
        ScoringCriterion("systolic_bp_low", "Systolic BP <90 mmHg", 2, "S: Systolic BP <90"),
        ScoringCriterion("multilobar_infiltrates", "Multilobar infiltrates on CXR", 1, "M: Multilobar CXR involvement"),
        ScoringCriterion("albumin_low", "Albumin <3.5 g/dL", 1, "A: Albumin low"),
        ScoringCriterion("respiratory_rate_high", "RR ≥25 (≥30 if age <50)", 1, "R: Respiratory rate elevated"),
        ScoringCriterion("tachycardia", "Heart rate ≥125 bpm", 1, "T: Tachycardia"),
        ScoringCriterion("confusion", "Confusion (new onset)", 1, "C: Confusion"),
        ScoringCriterion("oxygen_low", "O2 low (PaO2<70, SpO2<93, or PF<333)", 2, "O: Oxygenation poor"),
        ScoringCriterion("ph_low", "Arterial pH <7.35", 2, "P: pH low"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Low risk of IRVS (0-2%)", recommendations=["Ward admission or outpatient care"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate risk of IRVS (8%)", recommendations=["Consider monitored bed", "Watch for deterioration"]),
        ThresholdInterpretation(min_score=4, max_score=6, risk_level=RiskLevel.HIGH,
            interpretation="High risk of IRVS (26%)", recommendations=["ICU or high-dependency unit", "Close monitoring"]),
        ThresholdInterpretation(min_score=6, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very high risk of IRVS (62%)", recommendations=["ICU admission", "Prepare for intubation/vasopressors"]),
    ],
)

# PaO2/FiO2 Ratio Calculator
PF_RATIO_DEFINITION = CalculatorDefinition(
    id="pf_ratio",
    name="PaO2/FiO2 Ratio",
    short_name="P/F Ratio",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.INTEGER,
    score_unit="mmHg",
    description="Oxygenation index used in ARDS classification",
    references=["ARDS Definition Task Force. JAMA. 2012;307(23):2526-2533. PMID: 22797452"],
    specialties=["Critical Care", "Pulmonology", "Emergency Medicine"],
    notes=["Normal P/F ratio ≈400-500", "Used in Berlin ARDS criteria"],
    formula=FormulaDefinition(
        formula_text="PaO2 / FiO2",
        output_unit="mmHg",
        precision=0,
        parameters=[
            FormulaParameter(name="pao2", display_name="PaO2", unit="mmHg", min_value=20, max_value=600),
            FormulaParameter(name="fio2", display_name="FiO2", unit="decimal", min_value=0.21, max_value=1.0),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=300, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Normal oxygenation (P/F ≥300)", recommendations=["Normal gas exchange"]),
        ThresholdInterpretation(min_score=200, max_score=300, risk_level=RiskLevel.MODERATE,
            interpretation="Mild ARDS (P/F 200-300)", recommendations=["Consider ARDS workup", "Lung-protective ventilation"]),
        ThresholdInterpretation(min_score=100, max_score=200, risk_level=RiskLevel.HIGH,
            interpretation="Moderate ARDS (P/F 100-200)", recommendations=["ICU management", "Consider prone positioning"]),
        ThresholdInterpretation(min_score=0, max_score=100, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe ARDS (P/F <100)", recommendations=["Prone positioning", "Consider ECMO evaluation"]),
    ],
)

# Oxygenation Index
OXYGENATION_INDEX_DEFINITION = CalculatorDefinition(
    id="oxygenation_index",
    name="Oxygenation Index (OI)",
    short_name="OI",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Accounts for mean airway pressure in oxygenation assessment",
    references=["Trachsel D, et al. Intensive Care Med. 2005;31(2):327-332. PMID: 15605232"],
    specialties=["Critical Care", "Pulmonology", "Pediatrics"],
    notes=["OI = (FiO2 × MAP × 100) / PaO2", "Includes ventilator settings unlike P/F ratio"],
    formula=FormulaDefinition(
        formula_text="(FiO2 × Mean Airway Pressure × 100) / PaO2",
        output_unit="",
        precision=1,
        parameters=[
            FormulaParameter(name="fio2", display_name="FiO2", unit="%", min_value=21, max_value=100),
            FormulaParameter(name="map_airway", display_name="Mean Airway Pressure", unit="cmH2O", min_value=5, max_value=50),
            FormulaParameter(name="pao2", display_name="PaO2", unit="mmHg", min_value=20, max_value=600),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="OI <5 - Mild lung injury", recommendations=["Standard ventilator management"]),
        ThresholdInterpretation(min_score=5, max_score=15, risk_level=RiskLevel.MODERATE,
            interpretation="OI 5-15 - Moderate lung injury", recommendations=["Lung-protective strategies", "Consider PEEP optimization"]),
        ThresholdInterpretation(min_score=15, max_score=25, risk_level=RiskLevel.HIGH,
            interpretation="OI 15-25 - Severe lung injury", recommendations=["Consider proning", "Inhaled vasodilators"]),
        ThresholdInterpretation(min_score=25, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="OI >25 - Very severe (ECMO consideration)", recommendations=["ECMO evaluation if refractory"]),
    ],
)

# ARDS Berlin Criteria
ARDS_BERLIN_DEFINITION = CalculatorDefinition(
    id="ards_berlin",
    name="ARDS Berlin Criteria",
    short_name="Berlin ARDS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.CATEGORY,
    score_unit="",
    description="Diagnostic criteria and severity classification for ARDS",
    references=["ARDS Definition Task Force. JAMA. 2012;307(23):2526-2533. PMID: 22797452"],
    specialties=["Critical Care", "Pulmonology"],
    notes=["Requires PEEP ≥5 cmH2O", "Within 1 week of clinical insult", "Not fully explained by cardiac failure/fluid overload"],
    multi_level_criteria=[
        MultiLevelCriterion(name="timing", display_name="Timing",
            levels=[
                ("within_1_week", 1, "Within 1 week of insult/worsening symptoms"),
                ("over_1_week", 0, ">1 week (does not meet criteria)"),
            ], description="Onset timing"),
        MultiLevelCriterion(name="imaging", display_name="Chest Imaging",
            levels=[
                ("bilateral_opacities", 1, "Bilateral opacities on CXR/CT"),
                ("unilateral_only", 0, "Unilateral or no opacities"),
            ], description="Radiographic findings"),
        MultiLevelCriterion(name="edema_origin", display_name="Origin of Edema",
            levels=[
                ("not_cardiac", 1, "Not fully explained by cardiac failure/overload"),
                ("cardiac_cause", 0, "Primarily cardiac/fluid overload"),
            ], description="Need echo if no risk factor"),
        MultiLevelCriterion(name="pf_ratio", display_name="P/F Ratio (PEEP ≥5)",
            levels=[
                ("severe", 3, "P/F ≤100 - Severe ARDS"),
                ("moderate", 2, "P/F 100-200 - Moderate ARDS"),
                ("mild", 1, "P/F 200-300 - Mild ARDS"),
                ("not_ards", 0, "P/F >300 - Not ARDS"),
            ], description="With PEEP or CPAP ≥5 cmH2O"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.LOW,
            interpretation="ARDS criteria not met", recommendations=["Evaluate for alternative diagnosis"]),
        ThresholdInterpretation(min_score=4, max_score=5, risk_level=RiskLevel.MODERATE,
            interpretation="Mild ARDS (P/F 200-300)", recommendations=["Lung-protective ventilation (6 mL/kg IBW)", "PEEP titration"]),
        ThresholdInterpretation(min_score=5, max_score=6, risk_level=RiskLevel.HIGH,
            interpretation="Moderate ARDS (P/F 100-200)", recommendations=["Consider prone positioning", "Conservative fluid strategy"]),
        ThresholdInterpretation(min_score=6, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe ARDS (P/F ≤100)", recommendations=["Prone positioning", "Neuromuscular blockade consideration", "ECMO evaluation"]),
    ],
)

# Murray Lung Injury Score
MURRAY_SCORE_DEFINITION = CalculatorDefinition(
    id="murray_score",
    name="Murray Lung Injury Score",
    short_name="Murray LIS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.DECIMAL,
    score_unit="points",
    description="Quantifies acute lung injury severity",
    references=["Murray JF, et al. Am Rev Respir Dis. 1988;138(3):720-723. PMID: 3202424"],
    specialties=["Critical Care", "Pulmonology"],
    notes=["Average of 4 components", "Used for ECMO referral criteria historically"],
    multi_level_criteria=[
        MultiLevelCriterion(name="cxr_consolidation", display_name="CXR Consolidation",
            levels=[
                ("none", 0, "No consolidation (0)"), ("1_quadrant", 1, "1 quadrant (1)"),
                ("2_quadrants", 2, "2 quadrants (2)"), ("3_quadrants", 3, "3 quadrants (3)"),
                ("4_quadrants", 4, "4 quadrants (4)"),
            ], description="Alveolar consolidation"),
        MultiLevelCriterion(name="pf_ratio", display_name="P/F Ratio",
            levels=[
                ("gte_300", 0, "≥300 (0)"), ("225_299", 1, "225-299 (1)"),
                ("175_224", 2, "175-224 (2)"), ("100_174", 3, "100-174 (3)"),
                ("lt_100", 4, "<100 (4)"),
            ], description="PaO2/FiO2 ratio"),
        MultiLevelCriterion(name="peep", display_name="PEEP Level",
            levels=[
                ("leq_5", 0, "≤5 cmH2O (0)"), ("6_8", 1, "6-8 cmH2O (1)"),
                ("9_11", 2, "9-11 cmH2O (2)"), ("12_14", 3, "12-14 cmH2O (3)"),
                ("gte_15", 4, "≥15 cmH2O (4)"),
            ], description="PEEP setting"),
        MultiLevelCriterion(name="compliance", display_name="Static Compliance",
            levels=[
                ("gte_80", 0, "≥80 mL/cmH2O (0)"), ("60_79", 1, "60-79 (1)"),
                ("40_59", 2, "40-59 (2)"), ("20_39", 3, "20-39 (3)"),
                ("leq_19", 4, "≤19 (4)"),
            ], description="Respiratory system compliance"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="No or mild lung injury", recommendations=["Supportive care"]),
        ThresholdInterpretation(min_score=1, max_score=2.5, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate lung injury", recommendations=["Lung-protective ventilation", "Monitor closely"]),
        ThresholdInterpretation(min_score=2.5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Severe lung injury (ARDS)", recommendations=["Consider ECMO if refractory", "Maximize conventional therapy first"]),
    ],
)

# ROX Index
ROX_INDEX_DEFINITION = CalculatorDefinition(
    id="rox_index",
    name="ROX Index",
    short_name="ROX",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.PULMONARY,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Predicts high-flow nasal cannula (HFNC) failure and need for intubation",
    references=["Roca O, et al. J Crit Care. 2016;35:200-205. PMID: 27481760"],
    specialties=["Critical Care", "Pulmonology", "Emergency Medicine"],
    notes=["ROX = (SpO2/FiO2) / RR", "Assess at 2, 6, 12 hours of HFNC"],
    formula=FormulaDefinition(
        formula_text="(SpO2 / FiO2) / Respiratory Rate",
        output_unit="",
        precision=2,
        parameters=[
            FormulaParameter(name="spo2", display_name="SpO2", unit="%", min_value=50, max_value=100),
            FormulaParameter(name="fio2", display_name="FiO2", unit="%", min_value=21, max_value=100),
            FormulaParameter(name="respiratory_rate", display_name="Respiratory Rate", unit="/min", min_value=5, max_value=60),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=4.88, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="ROX ≥4.88 - Low risk of HFNC failure", recommendations=["Continue HFNC", "Reassess periodically"]),
        ThresholdInterpretation(min_score=3.85, max_score=4.88, risk_level=RiskLevel.MODERATE,
            interpretation="ROX 3.85-4.88 - Intermediate risk", recommendations=["Close monitoring", "Reassess in 1-2 hours"]),
        ThresholdInterpretation(min_score=0, max_score=3.85, risk_level=RiskLevel.HIGH,
            interpretation="ROX <3.85 - High risk of HFNC failure", recommendations=["Consider intubation", "Prepare for escalation"]),
    ],
)

# ============================================================================
# CRITICAL CARE & EMERGENCY - TIER 3: GI BLEEDING
# ============================================================================

# Glasgow-Blatchford Score
GLASGOW_BLATCHFORD_DEFINITION = CalculatorDefinition(
    id="glasgow_blatchford",
    name="Glasgow-Blatchford Bleeding Score",
    short_name="GBS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts need for intervention in upper GI bleeding",
    references=["Blatchford O, et al. Lancet. 2000;356(9238):1318-1321. PMID: 11073021"],
    specialties=["Gastroenterology", "Emergency Medicine"],
    notes=["Score 0 = very low risk, may not need admission", "Higher score = greater need for intervention"],
    multi_level_criteria=[
        MultiLevelCriterion(name="bun", display_name="BUN (mg/dL)",
            levels=[
                ("lt_18_2", 0, "<18.2 (0)"), ("18_2_22_3", 2, "18.2-22.3 (+2)"),
                ("22_4_27_9", 3, "22.4-27.9 (+3)"), ("28_55_9", 4, "28-55.9 (+4)"),
                ("gte_56", 6, "≥56 (+6)"),
            ], description="Blood urea nitrogen"),
        MultiLevelCriterion(name="hemoglobin_male", display_name="Hemoglobin (male)",
            levels=[
                ("gte_13", 0, "≥13 g/dL (0)"), ("12_12_9", 1, "12-12.9 (+1)"),
                ("10_11_9", 3, "10-11.9 (+3)"), ("lt_10", 6, "<10 (+6)"),
            ], description="Hemoglobin for males"),
        MultiLevelCriterion(name="hemoglobin_female", display_name="Hemoglobin (female)",
            levels=[
                ("gte_12", 0, "≥12 g/dL (0)"), ("10_11_9", 1, "10-11.9 (+1)"), ("lt_10", 6, "<10 (+6)"),
            ], description="Hemoglobin for females"),
        MultiLevelCriterion(name="systolic_bp", display_name="Systolic BP",
            levels=[
                ("gte_110", 0, "≥110 (0)"), ("100_109", 1, "100-109 (+1)"),
                ("90_99", 2, "90-99 (+2)"), ("lt_90", 3, "<90 (+3)"),
            ], description="Systolic blood pressure mmHg"),
    ],
    criteria=[
        ScoringCriterion("pulse_100", "Pulse ≥100 bpm", 1, "Tachycardia"),
        ScoringCriterion("melena", "Melena present", 1, ""),
        ScoringCriterion("syncope", "Syncope", 2, ""),
        ScoringCriterion("hepatic_disease", "Hepatic disease", 2, "Known liver disease"),
        ScoringCriterion("cardiac_failure", "Cardiac failure", 2, "Known heart failure"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="GBS 0 - Very low risk", recommendations=["Consider outpatient management", "No immediate endoscopy needed"]),
        ThresholdInterpretation(min_score=1, max_score=6, risk_level=RiskLevel.MODERATE,
            interpretation="GBS 1-5 - Low-moderate risk", recommendations=["Admission recommended", "Endoscopy within 24 hours"]),
        ThresholdInterpretation(min_score=6, max_score=12, risk_level=RiskLevel.HIGH,
            interpretation="GBS 6-11 - High risk", recommendations=["ICU admission consideration", "Urgent endoscopy"]),
        ThresholdInterpretation(min_score=12, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="GBS ≥12 - Very high risk", recommendations=["ICU admission", "Emergent endoscopy", "Blood product preparation"]),
    ],
)

# Rockall Score (Pre-endoscopy)
ROCKALL_PRE_DEFINITION = CalculatorDefinition(
    id="rockall_pre",
    name="Rockall Score (Pre-Endoscopy)",
    short_name="Rockall Pre",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts mortality in upper GI bleeding before endoscopy",
    references=["Rockall TA, et al. Gut. 1996;38(3):316-321. PMID: 8675081"],
    specialties=["Gastroenterology", "Emergency Medicine"],
    notes=["Pre-endoscopy clinical score", "Full score adds endoscopic findings"],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[
                ("lt_60", 0, "<60 (0)"), ("60_79", 1, "60-79 (+1)"), ("gte_80", 2, "≥80 (+2)"),
            ], description="Age in years"),
        MultiLevelCriterion(name="shock", display_name="Shock Status",
            levels=[
                ("no_shock", 0, "No shock (HR<100, SBP≥100) (0)"),
                ("tachycardia", 1, "Tachycardia (HR≥100, SBP≥100) (+1)"),
                ("hypotension", 2, "Hypotension (SBP<100) (+2)"),
            ], description="Hemodynamic status"),
    ],
    criteria=[
        ScoringCriterion("cardiac_failure", "Cardiac failure", 2, "IHD, CHF, other major cardiac disease"),
        ScoringCriterion("renal_failure", "Renal failure", 2, ""),
        ScoringCriterion("liver_failure", "Liver failure", 2, ""),
        ScoringCriterion("metastatic_cancer", "Metastatic cancer", 2, "Disseminated malignancy"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Pre-endoscopy Rockall 0 - Low risk", recommendations=["Early endoscopy", "Consider outpatient if score 0"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Pre-endoscopy Rockall 1-2 - Moderate risk", recommendations=["Inpatient endoscopy within 24h"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Pre-endoscopy Rockall ≥3 - High risk", recommendations=["Urgent endoscopy", "ICU consideration"]),
    ],
)

# Rockall Score (Full/Post-endoscopy)
ROCKALL_FULL_DEFINITION = CalculatorDefinition(
    id="rockall_full",
    name="Rockall Score (Full/Post-Endoscopy)",
    short_name="Rockall Full",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Complete Rockall score including endoscopic findings",
    references=["Rockall TA, et al. Gut. 1996;38(3):316-321. PMID: 8675081"],
    specialties=["Gastroenterology"],
    notes=["Full score adds endoscopic diagnosis and stigmata"],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[
                ("lt_60", 0, "<60 (0)"), ("60_79", 1, "60-79 (+1)"), ("gte_80", 2, "≥80 (+2)"),
            ], description="Age in years"),
        MultiLevelCriterion(name="shock", display_name="Shock Status",
            levels=[
                ("no_shock", 0, "No shock (0)"), ("tachycardia", 1, "Tachycardia (+1)"), ("hypotension", 2, "Hypotension (+2)"),
            ], description="Hemodynamic status"),
        MultiLevelCriterion(name="diagnosis", display_name="Endoscopic Diagnosis",
            levels=[
                ("mallory_weiss", 0, "Mallory-Weiss, no lesion, no SRH (0)"),
                ("all_other", 1, "All other diagnoses (+1)"),
                ("gi_malignancy", 2, "Upper GI malignancy (+2)"),
            ], description="Endoscopic findings"),
        MultiLevelCriterion(name="stigmata", display_name="Stigmata of Recent Hemorrhage",
            levels=[
                ("none_dark", 0, "None or dark spot only (0)"),
                ("blood_clot_vessel", 2, "Blood in GI tract, active bleeding, visible vessel, clot (+2)"),
            ], description="Stigmata of recent hemorrhage"),
    ],
    criteria=[
        ScoringCriterion("cardiac_failure", "Cardiac failure", 2, ""),
        ScoringCriterion("renal_failure", "Renal failure", 2, ""),
        ScoringCriterion("liver_failure", "Liver failure", 2, ""),
        ScoringCriterion("metastatic_cancer", "Metastatic cancer", 2, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="Full Rockall 0-2 - Low mortality (<5%)", recommendations=["Standard care", "Early discharge possible"]),
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.MODERATE,
            interpretation="Full Rockall 3-4 - Moderate risk (~10-15%)", recommendations=["Inpatient monitoring", "Reassess after intervention"]),
        ThresholdInterpretation(min_score=5, max_score=8, risk_level=RiskLevel.HIGH,
            interpretation="Full Rockall 5-7 - High risk (~25-40%)", recommendations=["ICU level care", "Consider surgery if rebleeding"]),
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Full Rockall ≥8 - Very high mortality (>40%)", recommendations=["Goals of care discussion"]),
    ],
)

# AIMS65 Score
AIMS65_DEFINITION = CalculatorDefinition(
    id="aims65",
    name="AIMS65 Score",
    short_name="AIMS65",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts in-hospital mortality for upper GI bleeding",
    references=["Saltzman JR, et al. Gastrointest Endosc. 2011;74(6):1215-1224. PMID: 21907980"],
    specialties=["Gastroenterology", "Emergency Medicine"],
    notes=["Simple 5-item score", "Easy to calculate at bedside"],
    criteria=[
        ScoringCriterion("albumin_lt_3", "Albumin <3 g/dL", 1, "A: Albumin"),
        ScoringCriterion("inr_gt_1_5", "INR >1.5", 1, "I: INR"),
        ScoringCriterion("altered_mental", "Altered mental status", 1, "M: Mental status"),
        ScoringCriterion("sbp_leq_90", "Systolic BP ≤90 mmHg", 1, "S: Systolic BP"),
        ScoringCriterion("age_gte_65", "Age ≥65 years", 1, "65: Age"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="AIMS65 0 - Low mortality (0.3%)", recommendations=["Standard care"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="AIMS65 1 - Low-moderate mortality (1%)", recommendations=["Inpatient monitoring"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="AIMS65 2 - Moderate mortality (4%)", recommendations=["Close monitoring", "ICU consideration"]),
        ThresholdInterpretation(min_score=3, max_score=4, risk_level=RiskLevel.HIGH,
            interpretation="AIMS65 3 - High mortality (10%)", recommendations=["ICU admission"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="AIMS65 4-5 - Very high mortality (25%)", recommendations=["ICU admission", "Goals of care"]),
    ],
)

# Oakland Score (Lower GI Bleed)
OAKLAND_SCORE_DEFINITION = CalculatorDefinition(
    id="oakland_score",
    name="Oakland Score for Lower GI Bleeding",
    short_name="Oakland",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts safe discharge in lower GI bleeding",
    references=["Oakland K, et al. Gut. 2017;66(8):1441-1449. PMID: 27196586"],
    specialties=["Gastroenterology", "Emergency Medicine"],
    notes=["Score ≤8 predicts safe discharge", "Developed for lower GI bleed specifically"],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[
                ("lt_40", 0, "<40 (0)"), ("40_69", 1, "40-69 (+1)"), ("gte_70", 2, "≥70 (+2)"),
            ], description="Age in years"),
        MultiLevelCriterion(name="sex", display_name="Sex",
            levels=[("female", 0, "Female (0)"), ("male", 1, "Male (+1)")], description="Sex"),
        MultiLevelCriterion(name="hemoglobin", display_name="Hemoglobin",
            levels=[
                ("gte_16", 0, "≥16 g/dL (0)"), ("13_15_9", 4, "13-15.9 (+4)"),
                ("11_12_9", 8, "11-12.9 (+8)"), ("9_10_9", 13, "9-10.9 (+13)"),
                ("7_8_9", 17, "7-8.9 (+17)"), ("lt_7", 22, "<7 (+22)"),
            ], description="Hemoglobin g/dL"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("lt_70", 0, "<70 (0)"), ("70_89", 1, "70-89 (+1)"),
                ("90_109", 2, "90-109 (+2)"), ("gte_110", 3, "≥110 (+3)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="systolic_bp", display_name="Systolic BP",
            levels=[
                ("gte_160", 0, "≥160 (0)"), ("130_159", 1, "130-159 (+1)"),
                ("120_129", 2, "120-129 (+2)"), ("90_119", 3, "90-119 (+3)"),
                ("lt_90", 4, "<90 (+4)"),
            ], description="Systolic BP mmHg"),
    ],
    criteria=[
        ScoringCriterion("previous_lgib", "Previous LGIB admission", 1, "Prior hospitalization for lower GI bleed"),
        ScoringCriterion("dre_blood", "DRE: blood present", 1, "Blood on digital rectal exam"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=9, risk_level=RiskLevel.LOW,
            interpretation="Oakland ≤8 - Safe for discharge (99% safe)", recommendations=["Consider outpatient management", "Outpatient colonoscopy"]),
        ThresholdInterpretation(min_score=9, max_score=17, risk_level=RiskLevel.MODERATE,
            interpretation="Oakland 9-16 - Intermediate risk", recommendations=["Admission recommended", "Inpatient colonoscopy"]),
        ThresholdInterpretation(min_score=17, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Oakland ≥17 - High risk", recommendations=["Admission required", "Consider CT angiography if unstable"]),
    ],
)

# Forrest Classification
FORREST_DEFINITION = CalculatorDefinition(
    id="forrest",
    name="Forrest Classification of Ulcer Bleeding",
    short_name="Forrest",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.CATEGORY,
    score_unit="class",
    description="Endoscopic classification of peptic ulcer bleeding stigmata",
    references=["Forrest JA, et al. Lancet. 1974;2(7877):394-397. PMID: 4136718"],
    specialties=["Gastroenterology"],
    notes=["Forrest Ia/Ib = high rebleed risk, need endoscopic therapy", "Forrest III = low risk, no therapy needed"],
    multi_level_criteria=[
        MultiLevelCriterion(name="stigmata", display_name="Endoscopic Stigmata",
            levels=[
                ("ia_spurting", 6, "Ia: Spurting hemorrhage"),
                ("ib_oozing", 5, "Ib: Oozing hemorrhage"),
                ("iia_visible_vessel", 4, "IIa: Non-bleeding visible vessel"),
                ("iib_adherent_clot", 3, "IIb: Adherent clot"),
                ("iic_flat_spot", 2, "IIc: Flat pigmented spot"),
                ("iii_clean_base", 1, "III: Clean-based ulcer"),
            ], description="Stigmata of recent hemorrhage"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Forrest I (Active bleeding) - Rebleed 55-90%",
            recommendations=["Immediate endoscopic therapy", "Epinephrine + clips or thermal", "ICU monitoring"]),
        ThresholdInterpretation(min_score=4, max_score=5, risk_level=RiskLevel.HIGH,
            interpretation="Forrest IIa (Visible vessel) - Rebleed 43%",
            recommendations=["Endoscopic therapy recommended", "High-dose PPI"]),
        ThresholdInterpretation(min_score=3, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Forrest IIb (Adherent clot) - Rebleed 22%",
            recommendations=["Consider clot removal + therapy", "Or intensive PPI alone"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Forrest IIc (Flat spot) - Rebleed 10%",
            recommendations=["No endoscopic therapy needed", "Standard PPI"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Forrest III (Clean base) - Rebleed 5%",
            recommendations=["No endoscopic therapy", "Standard PPI", "Early discharge possible"]),
    ],
)

# ============================================================================
# CRITICAL CARE & EMERGENCY - TIER 4: PANCREATITIS
# ============================================================================

# Ranson's Criteria at 48 hours
RANSON_48H_DEFINITION = CalculatorDefinition(
    id="ranson_48h",
    name="Ranson's Criteria (48 Hours)",
    short_name="Ranson 48h",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="48-hour criteria for pancreatitis severity assessment",
    references=["Ranson JH, et al. Surg Gynecol Obstet. 1974;139(1):69-81. PMID: 4834279"],
    specialties=["Gastroenterology", "Surgery", "Critical Care"],
    notes=["Assess at 48 hours", "Combine with admission criteria for total score"],
    criteria=[
        ScoringCriterion("hematocrit_drop_10", "Hematocrit drop >10%", 1, "From admission"),
        ScoringCriterion("bun_increase_5", "BUN increase >5 mg/dL", 1, "From admission"),
        ScoringCriterion("calcium_lt_8", "Serum calcium <8 mg/dL", 1, ""),
        ScoringCriterion("pao2_lt_60", "PaO2 <60 mmHg", 1, ""),
        ScoringCriterion("base_deficit_gt_4", "Base deficit >4 mEq/L", 1, ""),
        ScoringCriterion("fluid_sequestration_gt_6l", "Fluid sequestration >6L", 1, "Estimated third-spacing"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="Ranson 48h 0-2 - Low additional risk", recommendations=["Standard supportive care"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Ranson 48h ≥3 - Additional severity", recommendations=["Aggressive resuscitation", "ICU monitoring"]),
    ],
)

# Glasgow-Imrie Criteria
GLASGOW_IMRIE_DEFINITION = CalculatorDefinition(
    id="glasgow_imrie",
    name="Glasgow-Imrie Criteria for Pancreatitis",
    short_name="Glasgow-Imrie",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Predicts severity of acute pancreatitis within 48 hours",
    references=["Blamey SL, et al. Gut. 1984;25(12):1340-1346. PMID: 6510766"],
    specialties=["Gastroenterology", "Surgery", "Critical Care"],
    notes=["Assessed at 48 hours", "≥3 criteria = severe pancreatitis"],
    criteria=[
        ScoringCriterion("age_gt_55", "Age >55 years", 1, ""),
        ScoringCriterion("wbc_gt_15", "WBC >15 ×10³/µL", 1, ""),
        ScoringCriterion("glucose_gt_180", "Glucose >180 mg/dL (no DM hx)", 1, "In absence of diabetes"),
        ScoringCriterion("bun_gt_45", "BUN >45 mg/dL", 1, "Or urea >16 mmol/L"),
        ScoringCriterion("pao2_lt_60", "PaO2 <60 mmHg", 1, ""),
        ScoringCriterion("calcium_lt_8", "Calcium <8 mg/dL", 1, ""),
        ScoringCriterion("albumin_lt_3_2", "Albumin <3.2 g/dL", 1, ""),
        ScoringCriterion("ldh_gt_600", "LDH >600 U/L", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="Glasgow <3 - Mild pancreatitis (~3% mortality)", recommendations=["Supportive care", "Oral intake when tolerated"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Glasgow ≥3 - Severe pancreatitis (~15% mortality)", recommendations=["ICU admission", "Aggressive fluid resuscitation", "NPO"]),
    ],
)

# CT Severity Index (CTSI/Balthazar)
CTSI_DEFINITION = CalculatorDefinition(
    id="ctsi",
    name="CT Severity Index (CTSI/Balthazar)",
    short_name="CTSI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="CT-based severity assessment for acute pancreatitis",
    references=["Balthazar EJ, et al. Radiology. 1990;174(2):331-336. PMID: 2296641"],
    specialties=["Gastroenterology", "Radiology", "Surgery"],
    notes=["Grade (0-4) + Necrosis score (0-6) = CTSI", "Modified CTSI adds extrapancreatic complications"],
    multi_level_criteria=[
        MultiLevelCriterion(name="ct_grade", display_name="CT Grade (Balthazar)",
            levels=[
                ("grade_a", 0, "A: Normal pancreas (0)"),
                ("grade_b", 1, "B: Focal/diffuse enlargement (+1)"),
                ("grade_c", 2, "C: Peripancreatic inflammation (+2)"),
                ("grade_d", 3, "D: Single fluid collection (+3)"),
                ("grade_e", 4, "E: ≥2 collections or gas (+4)"),
            ], description="Pancreatic CT appearance"),
        MultiLevelCriterion(name="necrosis", display_name="Pancreatic Necrosis",
            levels=[
                ("none", 0, "No necrosis (0)"),
                ("lt_30", 2, "<30% necrosis (+2)"),
                ("30_50", 4, "30-50% necrosis (+4)"),
                ("gt_50", 6, ">50% necrosis (+6)"),
            ], description="Extent of pancreatic necrosis"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="CTSI 0-3 - Mild (4% complications, 3% mortality)", recommendations=["Supportive care"]),
        ThresholdInterpretation(min_score=4, max_score=6, risk_level=RiskLevel.MODERATE,
            interpretation="CTSI 4-6 - Moderate (35% complications)", recommendations=["Close monitoring", "Consider ICU"]),
        ThresholdInterpretation(min_score=7, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="CTSI 7-10 - Severe (92% complications, 17% mortality)", recommendations=["ICU admission", "Surgical consultation"]),
    ],
)

# Harmless Acute Pancreatitis Score (HAPS)
HAPS_DEFINITION = CalculatorDefinition(
    id="haps",
    name="Harmless Acute Pancreatitis Score (HAPS)",
    short_name="HAPS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies patients with non-severe acute pancreatitis at admission",
    references=["Lankisch PG, et al. Hepatogastroenterology. 2009;56(91-92):817-820. PMID: 19621710"],
    specialties=["Gastroenterology", "Emergency Medicine"],
    notes=["All 3 criteria must be absent for HAPS-negative (low risk)", "Simple bedside assessment"],
    criteria=[
        ScoringCriterion("rebound_guarding", "Rebound tenderness or guarding", 1, "Peritoneal signs"),
        ScoringCriterion("hematocrit_gt_43", "Hematocrit >43% (M) or >39.6% (F)", 1, ""),
        ScoringCriterion("creatinine_gt_2", "Creatinine >2 mg/dL", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="HAPS negative (0 criteria) - Non-severe course expected", recommendations=["Low risk for severe pancreatitis", "Standard ward care"]),
        ThresholdInterpretation(min_score=1, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="HAPS positive (≥1 criteria) - Cannot rule out severe course", recommendations=["Use other scoring systems", "Monitor for complications"]),
    ],
)

# Marshall Score for Pancreatitis Organ Failure
MARSHALL_SCORE_DEFINITION = CalculatorDefinition(
    id="marshall_score",
    name="Marshall Score for Organ Failure",
    short_name="Marshall",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Modified SOFA for organ failure assessment in pancreatitis",
    references=["Marshall JC, et al. Crit Care Med. 1995;23(10):1638-1652. PMID: 7587228"],
    specialties=["Critical Care", "Gastroenterology", "Surgery"],
    notes=["Score ≥2 in any system = organ failure", "Persistent OF >48h = severe acute pancreatitis"],
    multi_level_criteria=[
        MultiLevelCriterion(name="respiratory", display_name="Respiratory (PaO2/FiO2)",
            levels=[
                ("gt_400", 0, ">400 (0)"), ("301_400", 1, "301-400 (1)"),
                ("201_300", 2, "201-300 (2)"), ("101_200", 3, "101-200 (3)"),
                ("leq_100", 4, "≤100 (4)"),
            ], description="P/F ratio"),
        MultiLevelCriterion(name="renal", display_name="Renal (Creatinine)",
            levels=[
                ("lt_1_4", 0, "<1.4 mg/dL (0)"), ("1_4_1_8", 1, "1.4-1.8 (1)"),
                ("1_9_3_6", 2, "1.9-3.6 (2)"), ("3_7_4_9", 3, "3.7-4.9 (3)"),
                ("gt_4_9", 4, ">4.9 (4)"),
            ], description="Serum creatinine"),
        MultiLevelCriterion(name="cardiovascular", display_name="Cardiovascular (SBP)",
            levels=[
                ("gt_90", 0, "SBP >90, no inotropes (0)"),
                ("lt_90_fluid", 1, "SBP <90, responds to fluids (1)"),
                ("lt_90_fluid_resistant", 2, "SBP <90, not fluid responsive (2)"),
                ("lt_90_ph_7_3", 3, "SBP <90, pH <7.3 (3)"),
                ("lt_90_ph_7_2", 4, "SBP <90, pH <7.2 (4)"),
            ], description="Blood pressure and acid-base"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="No organ failure", recommendations=["Supportive care"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Single organ failure", recommendations=["ICU consideration if >48h"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Multiple organ failure", recommendations=["ICU admission", "Aggressive support"]),
    ],
)

# ============================================================================
# CRITICAL CARE & EMERGENCY - TIER 5: TRAUMA & BURNS
# ============================================================================

# Revised Trauma Score (RTS)
RTS_DEFINITION = CalculatorDefinition(
    id="rts",
    name="Revised Trauma Score (RTS)",
    short_name="RTS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Physiologic trauma severity score for triage",
    references=["Champion HR, et al. J Trauma. 1989;29(5):623-629. PMID: 2657085"],
    specialties=["Emergency Medicine", "Trauma Surgery"],
    notes=["RTS = 0.9368(GCS) + 0.7326(SBP) + 0.2908(RR)", "Used in TRISS calculation"],
    multi_level_criteria=[
        MultiLevelCriterion(name="gcs", display_name="GCS Score",
            levels=[
                ("13_15", 4, "13-15 (4)"), ("9_12", 3, "9-12 (3)"),
                ("6_8", 2, "6-8 (2)"), ("4_5", 1, "4-5 (1)"), ("3", 0, "3 (0)"),
            ], description="Glasgow Coma Scale"),
        MultiLevelCriterion(name="sbp", display_name="Systolic BP",
            levels=[
                ("gt_89", 4, ">89 mmHg (4)"), ("76_89", 3, "76-89 (3)"),
                ("50_75", 2, "50-75 (2)"), ("1_49", 1, "1-49 (1)"), ("0", 0, "0 (0)"),
            ], description="Systolic blood pressure"),
        MultiLevelCriterion(name="rr", display_name="Respiratory Rate",
            levels=[
                ("10_29", 4, "10-29 (4)"), ("gt_29", 3, ">29 (3)"),
                ("6_9", 2, "6-9 (2)"), ("1_5", 1, "1-5 (1)"), ("0", 0, "0 (0)"),
            ], description="Respiratory rate"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.VERY_HIGH,
            interpretation="RTS <4 - Critical (survival ~30%)", recommendations=["Trauma center transfer", "Aggressive resuscitation"]),
        ThresholdInterpretation(min_score=4, max_score=8, risk_level=RiskLevel.HIGH,
            interpretation="RTS 4-7 - Serious", recommendations=["Trauma team activation", "Close monitoring"]),
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="RTS ≥8 - Moderate (survival >90%)", recommendations=["Standard trauma evaluation"]),
    ],
)

# Injury Severity Score (ISS)
ISS_DEFINITION = CalculatorDefinition(
    id="iss",
    name="Injury Severity Score (ISS)",
    short_name="ISS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Anatomic injury severity based on AIS scores",
    references=["Baker SP, et al. J Trauma. 1974;14(3):187-196. PMID: 4814394"],
    specialties=["Trauma Surgery", "Emergency Medicine"],
    notes=["ISS = sum of squares of 3 highest AIS scores from different body regions", "Range 1-75; ISS ≥16 = major trauma"],
    multi_level_criteria=[
        MultiLevelCriterion(name="region1_ais", display_name="Highest AIS (Region 1)",
            levels=[
                ("6", 36, "AIS 6 (fatal)"), ("5", 25, "AIS 5 (critical)"),
                ("4", 16, "AIS 4 (severe)"), ("3", 9, "AIS 3 (serious)"),
                ("2", 4, "AIS 2 (moderate)"), ("1", 1, "AIS 1 (minor)"), ("0", 0, "AIS 0 (none)"),
            ], description="Highest injury severity"),
        MultiLevelCriterion(name="region2_ais", display_name="2nd Highest AIS (Region 2)",
            levels=[
                ("5", 25, "AIS 5"), ("4", 16, "AIS 4"), ("3", 9, "AIS 3"),
                ("2", 4, "AIS 2"), ("1", 1, "AIS 1"), ("0", 0, "AIS 0"),
            ], description="Second highest injury severity"),
        MultiLevelCriterion(name="region3_ais", display_name="3rd Highest AIS (Region 3)",
            levels=[
                ("5", 25, "AIS 5"), ("4", 16, "AIS 4"), ("3", 9, "AIS 3"),
                ("2", 4, "AIS 2"), ("1", 1, "AIS 1"), ("0", 0, "AIS 0"),
            ], description="Third highest injury severity"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=1, max_score=9, risk_level=RiskLevel.LOW,
            interpretation="ISS 1-8 - Minor trauma", recommendations=["Standard evaluation"]),
        ThresholdInterpretation(min_score=9, max_score=16, risk_level=RiskLevel.MODERATE,
            interpretation="ISS 9-15 - Moderate trauma", recommendations=["Trauma team evaluation"]),
        ThresholdInterpretation(min_score=16, max_score=25, risk_level=RiskLevel.HIGH,
            interpretation="ISS 16-24 - Major trauma", recommendations=["Trauma center care", "ICU admission"]),
        ThresholdInterpretation(min_score=25, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="ISS ≥25 - Severe/critical trauma", recommendations=["Level 1 trauma center", "Maximum resuscitation"]),
    ],
)

# Pediatric GCS
PEDIATRIC_GCS_DEFINITION = CalculatorDefinition(
    id="pediatric_gcs",
    name="Pediatric Glasgow Coma Scale",
    short_name="Pediatric GCS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Modified GCS for preverbal children",
    references=["Holmes JF, et al. Ann Emerg Med. 2005;45(4):370-379. PMID: 15795716"],
    specialties=["Pediatrics", "Emergency Medicine", "Trauma Surgery"],
    notes=["For children <2 years or preverbal", "Uses cry/interaction instead of verbal orientation"],
    multi_level_criteria=[
        MultiLevelCriterion(name="eye", display_name="Eye Opening",
            levels=[
                ("spontaneous", 4, "Spontaneous (4)"), ("to_voice", 3, "To voice (3)"),
                ("to_pain", 2, "To pain (2)"), ("none", 1, "None (1)"),
            ], description="Eye opening response"),
        MultiLevelCriterion(name="verbal", display_name="Verbal/Cry",
            levels=[
                ("coos_babbles", 5, "Coos/babbles/smiles appropriately (5)"),
                ("irritable_cry", 4, "Irritable cry, consolable (4)"),
                ("cries_to_pain", 3, "Cries to pain (3)"),
                ("moans_to_pain", 2, "Moans to pain (2)"),
                ("none", 1, "None (1)"),
            ], description="Verbal response - modified for preverbal"),
        MultiLevelCriterion(name="motor", display_name="Motor Response",
            levels=[
                ("normal_spontaneous", 6, "Normal spontaneous movement (6)"),
                ("withdraws_touch", 5, "Withdraws to touch (5)"),
                ("withdraws_pain", 4, "Withdraws from pain (4)"),
                ("flexion", 3, "Abnormal flexion (3)"),
                ("extension", 2, "Extension (2)"),
                ("none", 1, "None (1)"),
            ], description="Motor response"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=3, max_score=9, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe impairment (3-8)", recommendations=["Airway protection", "Emergent neuroimaging", "Neurosurgery consult"]),
        ThresholdInterpretation(min_score=9, max_score=13, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate impairment (9-12)", recommendations=["Close monitoring", "Consider CT head"]),
        ThresholdInterpretation(min_score=13, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Mild impairment (13-15)", recommendations=["Observation", "PECARN criteria for CT decision"]),
    ],
)

# NEXUS Criteria for C-Spine Clearance
NEXUS_DEFINITION = CalculatorDefinition(
    id="nexus",
    name="NEXUS Criteria for C-Spine Clearance",
    short_name="NEXUS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.CATEGORY,
    score_unit="",
    description="Clinical decision rule to exclude cervical spine injury without imaging",
    references=["Hoffman JR, et al. N Engl J Med. 2000;343(2):94-99. PMID: 10891516"],
    specialties=["Emergency Medicine", "Trauma Surgery"],
    notes=["All 5 criteria must be absent to clear C-spine", "99.6% sensitivity for significant injury"],
    criteria=[
        ScoringCriterion("midline_tenderness", "Midline cervical tenderness", 1, "Posterior midline"),
        ScoringCriterion("focal_neuro_deficit", "Focal neurological deficit", 1, "Any focal finding"),
        ScoringCriterion("altered_alertness", "Altered level of alertness", 1, "GCS <15, intoxication, disorientation"),
        ScoringCriterion("intoxication", "Intoxication", 1, "Alcohol or drugs"),
        ScoringCriterion("distracting_injury", "Distracting painful injury", 1, "Painful injury elsewhere"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="NEXUS negative - C-spine injury very unlikely", recommendations=["C-spine can be cleared clinically", "No imaging required"]),
        ThresholdInterpretation(min_score=1, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="NEXUS positive - Imaging required", recommendations=["Maintain C-spine immobilization", "CT preferred over X-ray"]),
    ],
)

# Canadian C-Spine Rule
CANADIAN_CSPINE_DEFINITION = CalculatorDefinition(
    id="canadian_cspine",
    name="Canadian C-Spine Rule",
    short_name="CCR",
    calc_type=CalculatorType.DECISION_TREE,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.CATEGORY,
    score_unit="",
    description="Clinical decision rule for C-spine imaging in alert trauma patients",
    references=["Stiell IG, et al. JAMA. 2001;286(15):1841-1848. PMID: 11597285"],
    specialties=["Emergency Medicine", "Trauma Surgery"],
    notes=["More sensitive than NEXUS", "Requires GCS 15 and stable vitals to apply"],
    criteria=[
        ScoringCriterion("high_risk_factor", "High-risk factor present", 3, "Age≥65, dangerous mechanism, paresthesias"),
        ScoringCriterion("low_risk_allows_assessment", "Low-risk factor allows assessment", 1, "Simple MVC, sitting in ED, ambulatory, delayed neck pain, no midline tenderness"),
        ScoringCriterion("able_rotate_45", "Able to rotate neck 45° L and R", 0, "If able, can clear"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="CCR negative - Low risk", recommendations=["C-spine can be cleared if can rotate 45°"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="CCR indeterminate", recommendations=["Cannot assess ROM safely", "Maintain immobilization"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="CCR positive - High risk factor present", recommendations=["C-spine imaging required", "Maintain immobilization"]),
    ],
)

# Modified Brooke Formula for Burns
MODIFIED_BROOKE_DEFINITION = CalculatorDefinition(
    id="modified_brooke",
    name="Modified Brooke Formula for Burns",
    short_name="Modified Brooke",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="mL/24h",
    description="Burn fluid resuscitation (alternative to Parkland)",
    references=["Pruitt BA. J Trauma. 2000;49(5):969-978. PMID: 11086796"],
    specialties=["Burn Surgery", "Critical Care", "Emergency Medicine"],
    notes=["2 mL/kg/%TBSA (vs Parkland 4 mL)", "Often used in military settings", "Still give 50% in first 8h"],
    formula=FormulaDefinition(
        formula_text="2 × Weight(kg) × %TBSA",
        output_unit="mL in 24h",
        precision=0,
        parameters=[
            FormulaParameter(name="weight", display_name="Weight", unit="kg", min_value=1, max_value=200),
            FormulaParameter(name="tbsa", display_name="TBSA Burned", unit="%", min_value=1, max_value=100),
        ],
    ),
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="24-hour crystalloid requirement",
            recommendations=["Give 50% in first 8 hours from burn time", "Use LR", "Titrate to UOP 0.5-1 mL/kg/hr"]),
    ],
)

# TBSA Calculator (Rule of 9s)
TBSA_RULE_OF_9S_DEFINITION = CalculatorDefinition(
    id="tbsa_rule_of_9s",
    name="TBSA Calculator (Rule of 9s)",
    short_name="Rule of 9s",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="%",
    description="Estimates total body surface area burned using Rule of 9s",
    references=["Wallace AB. Lancet. 1951;1(6653):501-504. PMID: 14805109"],
    specialties=["Burn Surgery", "Emergency Medicine"],
    notes=["Adult percentages; Lund-Browder more accurate for children", "Palm = 1% TBSA for scattered burns"],
    criteria=[
        ScoringCriterion("head", "Head and neck", 9, "9% in adults"),
        ScoringCriterion("chest_anterior", "Anterior trunk (chest/abdomen)", 18, "18%"),
        ScoringCriterion("back", "Posterior trunk (back)", 18, "18%"),
        ScoringCriterion("arm_left", "Left upper extremity", 9, "9%"),
        ScoringCriterion("arm_right", "Right upper extremity", 9, "9%"),
        ScoringCriterion("leg_left", "Left lower extremity", 18, "18%"),
        ScoringCriterion("leg_right", "Right lower extremity", 18, "18%"),
        ScoringCriterion("perineum", "Perineum/genitalia", 1, "1%"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=10, risk_level=RiskLevel.LOW,
            interpretation="Minor burn (<10%)", recommendations=["Outpatient if partial thickness", "May not need IV fluids"]),
        ThresholdInterpretation(min_score=10, max_score=20, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate burn (10-20%)", recommendations=["IV fluid resuscitation", "Burn center referral if deep"]),
        ThresholdInterpretation(min_score=20, max_score=40, risk_level=RiskLevel.HIGH,
            interpretation="Major burn (20-40%)", recommendations=["Burn center transfer", "Parkland formula resuscitation"]),
        ThresholdInterpretation(min_score=40, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Extensive burn (>40%)", recommendations=["Burn center ICU", "Aggressive resuscitation", "High mortality risk"]),
    ],
)

# ============================================================================
# CRITICAL CARE & EMERGENCY - TIER 6: EARLY WARNING & SCREENING
# ============================================================================

# MEWS - Modified Early Warning Score
MEWS_DEFINITION = CalculatorDefinition(
    id="mews",
    name="Modified Early Warning Score (MEWS)",
    short_name="MEWS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Early identification of patients at risk of deterioration",
    references=["Subbe CP, et al. QJM. 2001;94(10):521-526. PMID: 11588210"],
    specialties=["Emergency Medicine", "Critical Care", "Nursing"],
    notes=["Simpler than NEWS", "Score ≥5 = high risk of deterioration"],
    multi_level_criteria=[
        MultiLevelCriterion(name="systolic_bp", display_name="Systolic BP",
            levels=[
                ("leq_70", 3, "≤70 (3)"), ("71_80", 2, "71-80 (2)"), ("81_100", 1, "81-100 (1)"),
                ("101_199", 0, "101-199 (0)"), ("gte_200", 2, "≥200 (2)"),
            ], description="Systolic BP mmHg"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("leq_40", 2, "≤40 (2)"), ("41_50", 1, "41-50 (1)"), ("51_100", 0, "51-100 (0)"),
                ("101_110", 1, "101-110 (1)"), ("111_129", 2, "111-129 (2)"), ("gte_130", 3, "≥130 (3)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="respiratory_rate", display_name="Respiratory Rate",
            levels=[
                ("lt_9", 2, "<9 (2)"), ("9_14", 0, "9-14 (0)"), ("15_20", 1, "15-20 (1)"),
                ("21_29", 2, "21-29 (2)"), ("gte_30", 3, "≥30 (3)"),
            ], description="Breaths per minute"),
        MultiLevelCriterion(name="temperature", display_name="Temperature",
            levels=[
                ("lt_35", 2, "<35°C (2)"), ("35_38_4", 0, "35-38.4°C (0)"), ("gte_38_5", 2, "≥38.5°C (2)"),
            ], description="Temperature °C"),
        MultiLevelCriterion(name="avpu", display_name="AVPU Level",
            levels=[
                ("alert", 0, "Alert (0)"), ("voice", 1, "Responds to voice (1)"),
                ("pain", 2, "Responds to pain (2)"), ("unresponsive", 3, "Unresponsive (3)"),
            ], description="AVPU consciousness scale"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="MEWS 0-1 - Low risk", recommendations=["Routine monitoring every 4-6 hours"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="MEWS 2-3 - Moderate risk", recommendations=["Increase monitoring to q2h", "Notify charge nurse"]),
        ThresholdInterpretation(min_score=4, max_score=5, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="MEWS 4 - Increased risk", recommendations=["Notify physician", "q1h monitoring", "Consider ICU"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="MEWS ≥5 - High risk", recommendations=["Urgent physician review", "ICU evaluation", "Continuous monitoring"]),
    ],
)

# PEWS - Pediatric Early Warning Score
PEWS_DEFINITION = CalculatorDefinition(
    id="pews",
    name="Pediatric Early Warning Score (PEWS)",
    short_name="PEWS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Early warning score for hospitalized children",
    references=["Monaghan A. Nurs Crit Care. 2005;10(5):231-238. PMID: 16161418"],
    specialties=["Pediatrics", "Emergency Medicine", "Critical Care"],
    notes=["Multiple versions exist", "Components vary by institution"],
    multi_level_criteria=[
        MultiLevelCriterion(name="behavior", display_name="Behavior",
            levels=[
                ("playing", 0, "Playing/appropriate (0)"), ("sleeping", 1, "Sleeping (1)"),
                ("irritable", 2, "Irritable (2)"), ("lethargic_confused", 3, "Lethargic/confused (3)"),
            ], description="Behavior/mental status"),
        MultiLevelCriterion(name="cardiovascular", display_name="Cardiovascular",
            levels=[
                ("pink_crt_lt_2", 0, "Pink, CRT 1-2 sec (0)"), ("pale_crt_3", 1, "Pale or CRT 3 sec (1)"),
                ("gray_crt_4", 2, "Gray or CRT 4 sec (2)"), ("gray_crt_gt_5", 3, "Gray, CRT ≥5 sec (3)"),
            ], description="Color and capillary refill"),
        MultiLevelCriterion(name="respiratory", display_name="Respiratory",
            levels=[
                ("normal", 0, "Normal, no retractions (0)"), ("mild_retraction", 1, "Mild retractions or >10L O2 (1)"),
                ("moderate_retraction", 2, "Moderate retractions, FiO2>40% (2)"), ("severe_retraction", 3, "Severe retractions, FiO2>50% (3)"),
            ], description="Work of breathing"),
    ],
    criteria=[
        ScoringCriterion("nebulizer_q15min", "Nebulizer q15min or continuous", 2, "For respiratory distress"),
        ScoringCriterion("persistent_vomiting", "Persistent vomiting post-surgery", 2, "Post-operative"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="PEWS 0-2 - Low risk", recommendations=["Routine monitoring"]),
        ThresholdInterpretation(min_score=3, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="PEWS 3-4 - Moderate risk", recommendations=["Increase monitoring", "Notify physician"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="PEWS ≥5 - High risk", recommendations=["Urgent physician evaluation", "Consider PICU"]),
    ],
)

# REMS - Rapid Emergency Medicine Score
REMS_DEFINITION = CalculatorDefinition(
    id="rems",
    name="Rapid Emergency Medicine Score (REMS)",
    short_name="REMS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Mortality prediction in nonsurgical ED patients",
    references=["Olsson T, et al. Am J Emerg Med. 2004;22(2):92-97. PMID: 15011224"],
    specialties=["Emergency Medicine"],
    notes=["Derived from APACHE II", "Score range 0-26"],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[
                ("lt_45", 0, "<45 (0)"), ("45_54", 2, "45-54 (+2)"), ("55_64", 3, "55-64 (+3)"),
                ("65_74", 5, "65-74 (+5)"), ("gte_75", 6, "≥75 (+6)"),
            ], description="Age in years"),
        MultiLevelCriterion(name="map", display_name="Mean Arterial Pressure",
            levels=[
                ("lt_50", 4, "<50 (+4)"), ("50_69", 2, "50-69 (+2)"), ("70_109", 0, "70-109 (0)"),
                ("110_129", 2, "110-129 (+2)"), ("130_159", 3, "130-159 (+3)"), ("gte_160", 4, "≥160 (+4)"),
            ], description="MAP mmHg"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("lt_40", 4, "<40 (+4)"), ("40_54", 3, "40-54 (+3)"), ("55_69", 2, "55-69 (+2)"),
                ("70_109", 0, "70-109 (0)"), ("110_139", 2, "110-139 (+2)"), ("140_179", 3, "140-179 (+3)"),
                ("gte_180", 4, "≥180 (+4)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="respiratory_rate", display_name="Respiratory Rate",
            levels=[
                ("lt_6", 4, "<6 (+4)"), ("6_9", 2, "6-9 (+2)"), ("10_11", 1, "10-11 (+1)"),
                ("12_24", 0, "12-24 (0)"), ("25_34", 1, "25-34 (+1)"), ("35_49", 3, "35-49 (+3)"), ("gte_50", 4, "≥50 (+4)"),
            ], description="Respiratory rate"),
        MultiLevelCriterion(name="spo2", display_name="SpO2",
            levels=[
                ("lt_75", 4, "<75% (+4)"), ("75_85", 3, "75-85% (+3)"), ("86_89", 1, "86-89% (+1)"),
                ("gte_90", 0, "≥90% (0)"),
            ], description="Oxygen saturation"),
        MultiLevelCriterion(name="gcs", display_name="GCS",
            levels=[
                ("3", 4, "GCS 3 (+4)"), ("4_6", 3, "GCS 4-6 (+3)"), ("7_9", 2, "GCS 7-9 (+2)"),
                ("10_12", 1, "GCS 10-12 (+1)"), ("13_15", 0, "GCS 13-15 (0)"),
            ], description="Glasgow Coma Scale"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=6, risk_level=RiskLevel.LOW,
            interpretation="REMS 0-5 - Low mortality (<5%)", recommendations=["Standard evaluation"]),
        ThresholdInterpretation(min_score=6, max_score=13, risk_level=RiskLevel.MODERATE,
            interpretation="REMS 6-12 - Moderate mortality (~15%)", recommendations=["Close monitoring", "Consider admission"]),
        ThresholdInterpretation(min_score=13, max_score=20, risk_level=RiskLevel.HIGH,
            interpretation="REMS 13-19 - High mortality (~50%)", recommendations=["ICU consideration"]),
        ThresholdInterpretation(min_score=20, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="REMS ≥20 - Very high mortality", recommendations=["ICU admission"]),
    ],
)

# CART Score - Cardiac Arrest Risk Triage
CART_DEFINITION = CalculatorDefinition(
    id="cart",
    name="CART Score (Cardiac Arrest Risk Triage)",
    short_name="CART",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts in-hospital cardiac arrest within 48 hours",
    references=["Churpek MM, et al. Resuscitation. 2012;83(11):1335-1340. PMID: 22580947"],
    specialties=["Critical Care", "Hospital Medicine", "Nursing"],
    notes=["Simple vital signs-based score", "For ward patients"],
    multi_level_criteria=[
        MultiLevelCriterion(name="respiratory_rate", display_name="Respiratory Rate",
            levels=[
                ("lt_21", 0, "<21 (0)"), ("21_23", 8, "21-23 (+8)"), ("24_25", 12, "24-25 (+12)"),
                ("26_29", 15, "26-29 (+15)"), ("gte_30", 22, "≥30 (+22)"),
            ], description="Respiratory rate"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("lt_110", 0, "<110 (0)"), ("110_139", 4, "110-139 (+4)"), ("gte_140", 13, "≥140 (+13)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="diastolic_bp", display_name="Diastolic BP",
            levels=[
                ("gte_50", 0, "≥50 (0)"), ("40_49", 4, "40-49 (+4)"),
                ("35_39", 6, "35-39 (+6)"), ("lt_35", 13, "<35 (+13)"),
            ], description="Diastolic BP mmHg"),
    ],
    criteria=[
        ScoringCriterion("age_gte_55", "Age ≥55 years", 4, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=20, risk_level=RiskLevel.LOW,
            interpretation="CART <20 - Low risk", recommendations=["Standard monitoring"]),
        ThresholdInterpretation(min_score=20, max_score=40, risk_level=RiskLevel.MODERATE,
            interpretation="CART 20-39 - Moderate risk", recommendations=["Increased monitoring", "Consider step-down"]),
        ThresholdInterpretation(min_score=40, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="CART ≥40 - High risk of cardiac arrest", recommendations=["ICU consideration", "Ensure code status documented"]),
    ],
)

# LODS - Logistic Organ Dysfunction System
LODS_DEFINITION = CalculatorDefinition(
    id="lods",
    name="Logistic Organ Dysfunction System (LODS)",
    short_name="LODS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="ICU mortality prediction based on organ dysfunction",
    references=["Le Gall JR, et al. JAMA. 1996;276(10):802-810. PMID: 8769590"],
    specialties=["Critical Care"],
    notes=["Range 0-22", "Uses worst values in first 24h"],
    multi_level_criteria=[
        MultiLevelCriterion(name="neuro", display_name="Neurological (GCS)",
            levels=[
                ("14_15", 0, "14-15 (0)"), ("9_13", 1, "9-13 (+1)"), ("6_8", 3, "6-8 (+3)"),
                ("lt_6", 5, "<6 (+5)"),
            ], description="Glasgow Coma Scale"),
        MultiLevelCriterion(name="cardiovascular", display_name="Cardiovascular",
            levels=[
                ("normal", 0, "Normal HR/BP (0)"), ("hr_gt_140", 1, "HR>140 or SBP 90-99 (+1)"),
                ("sbp_70_89", 3, "SBP 70-89 (+3)"), ("sbp_lt_70", 5, "SBP <70 (+5)"),
            ], description="Heart rate and blood pressure"),
        MultiLevelCriterion(name="renal", display_name="Renal",
            levels=[
                ("bun_lt_36", 0, "BUN <36 or Cr <1.2 (0)"), ("bun_36_59", 1, "BUN 36-59 (+1)"),
                ("bun_60_119", 3, "BUN 60-119 (+3)"), ("bun_gte_120", 5, "BUN ≥120 (+5)"),
            ], description="BUN or creatinine"),
        MultiLevelCriterion(name="pulmonary", display_name="Pulmonary",
            levels=[
                ("pf_gte_150", 0, "P/F ≥150 or no vent (0)"), ("pf_lt_150_vent", 1, "P/F <150 with vent (+1)"),
                ("pf_lt_100", 3, "P/F <100 (+3)"),
            ], description="PaO2/FiO2 ratio"),
        MultiLevelCriterion(name="hematologic", display_name="Hematologic",
            levels=[
                ("normal", 0, "WBC>2.5, Plt>50 (0)"), ("wbc_lt_2_5", 1, "WBC<2.5 or Plt<50 (+1)"),
                ("plt_lt_25", 3, "Plt <25 (+3)"),
            ], description="WBC and platelets"),
        MultiLevelCriterion(name="hepatic", display_name="Hepatic",
            levels=[
                ("bili_lt_2", 0, "Bilirubin <2 (0)"), ("bili_2_5", 1, "Bilirubin 2-5.9 (+1)"),
                ("bili_gte_6", 3, "Bilirubin ≥6 (+3)"),
            ], description="Total bilirubin"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="LODS 0-4 - Low mortality (~5%)", recommendations=["Standard ICU care"]),
        ThresholdInterpretation(min_score=5, max_score=10, risk_level=RiskLevel.MODERATE,
            interpretation="LODS 5-9 - Moderate mortality (~25%)", recommendations=["Close organ monitoring"]),
        ThresholdInterpretation(min_score=10, max_score=15, risk_level=RiskLevel.HIGH,
            interpretation="LODS 10-14 - High mortality (~60%)", recommendations=["Goals of care discussion"]),
        ThresholdInterpretation(min_score=15, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="LODS ≥15 - Very high mortality (>80%)", recommendations=["Palliative care consultation"]),
    ],
)

# MODS - Multiple Organ Dysfunction Score
MODS_DEFINITION = CalculatorDefinition(
    id="mods",
    name="Multiple Organ Dysfunction Score (MODS)",
    short_name="MODS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Quantifies severity of multiple organ dysfunction syndrome",
    references=["Marshall JC, et al. Crit Care Med. 1995;23(10):1638-1652. PMID: 7587228"],
    specialties=["Critical Care"],
    notes=["Range 0-24", "6 organ systems, 0-4 points each"],
    multi_level_criteria=[
        MultiLevelCriterion(name="respiratory", display_name="Respiratory (P/F)",
            levels=[
                ("gt_300", 0, ">300 (0)"), ("226_300", 1, "226-300 (+1)"), ("151_225", 2, "151-225 (+2)"),
                ("76_150", 3, "76-150 (+3)"), ("leq_75", 4, "≤75 (+4)"),
            ], description="PaO2/FiO2 ratio"),
        MultiLevelCriterion(name="renal", display_name="Renal (Creatinine)",
            levels=[
                ("leq_1_1", 0, "≤1.1 (0)"), ("1_2_2_3", 1, "1.2-2.3 (+1)"), ("2_4_3_9", 2, "2.4-3.9 (+2)"),
                ("4_5_9", 3, "4.0-5.9 (+3)"), ("gte_6", 4, "≥6.0 (+4)"),
            ], description="Serum creatinine mg/dL"),
        MultiLevelCriterion(name="hepatic", display_name="Hepatic (Bilirubin)",
            levels=[
                ("leq_1_2", 0, "≤1.2 (0)"), ("1_3_3_5", 1, "1.3-3.5 (+1)"), ("3_6_7", 2, "3.6-7.0 (+2)"),
                ("7_1_14", 3, "7.1-14 (+3)"), ("gt_14", 4, ">14 (+4)"),
            ], description="Total bilirubin mg/dL"),
        MultiLevelCriterion(name="cardiovascular", display_name="Cardiovascular (PAR)",
            levels=[
                ("leq_10", 0, "PAR ≤10 (0)"), ("10_1_15", 1, "PAR 10.1-15 (+1)"),
                ("15_1_20", 2, "PAR 15.1-20 (+2)"), ("20_1_30", 3, "PAR 20.1-30 (+3)"),
                ("gt_30", 4, "PAR >30 (+4)"),
            ], description="Pressure-adjusted heart rate"),
        MultiLevelCriterion(name="hematologic", display_name="Hematologic (Platelets)",
            levels=[
                ("gt_120", 0, ">120 (0)"), ("81_120", 1, "81-120 (+1)"), ("51_80", 2, "51-80 (+2)"),
                ("21_50", 3, "21-50 (+3)"), ("leq_20", 4, "≤20 (+4)"),
            ], description="Platelet count ×10³/µL"),
        MultiLevelCriterion(name="neurological", display_name="Neurological (GCS)",
            levels=[
                ("15", 0, "15 (0)"), ("13_14", 1, "13-14 (+1)"), ("10_12", 2, "10-12 (+2)"),
                ("7_9", 3, "7-9 (+3)"), ("leq_6", 4, "≤6 (+4)"),
            ], description="Glasgow Coma Scale"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="MODS 0-4 - Low mortality (~5%)", recommendations=["Supportive care"]),
        ThresholdInterpretation(min_score=5, max_score=9, risk_level=RiskLevel.MODERATE,
            interpretation="MODS 5-8 - Moderate mortality (~25%)", recommendations=["Optimize organ support"]),
        ThresholdInterpretation(min_score=9, max_score=13, risk_level=RiskLevel.HIGH,
            interpretation="MODS 9-12 - High mortality (~50%)", recommendations=["Goals of care discussion"]),
        ThresholdInterpretation(min_score=13, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="MODS ≥13 - Very high mortality (>75%)", recommendations=["Comfort care consideration"]),
    ],
)

# ============================================================================
# CRITICAL CARE & EMERGENCY - TIER 7: RESUSCITATION & ARREST
# ============================================================================

# GO-FAR Score - Good Outcome Following Attempted Resuscitation
GO_FAR_DEFINITION = CalculatorDefinition(
    id="go_far",
    name="GO-FAR Score",
    short_name="GO-FAR",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts neurologically intact survival after in-hospital CPR",
    references=["Ebell MH, et al. JAMA Intern Med. 2013;173(20):1872-1878. PMID: 24018585"],
    specialties=["Critical Care", "Hospital Medicine", "Palliative Care"],
    notes=["Lower score = better prognosis", "Score <14 suggests >10% good neurologic outcome"],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[
                ("lt_70", 0, "<70 (0)"), ("70_74", 2, "70-74 (+2)"), ("75_79", 5, "75-79 (+5)"),
                ("80_84", 6, "80-84 (+6)"), ("gte_85", 11, "≥85 (+11)"),
            ], description="Age in years"),
        MultiLevelCriterion(name="neuro_status", display_name="Neurologic Status",
            levels=[
                ("alert", 0, "Alert/oriented (0)"), ("confused", 3, "Confused (+3)"),
                ("coma", 10, "Comatose (+10)"),
            ], description="Pre-arrest neurologic status"),
    ],
    criteria=[
        ScoringCriterion("septicemia", "Septicemia", 5, ""),
        ScoringCriterion("metastatic_cancer", "Metastatic cancer", 7, ""),
        ScoringCriterion("medical_noncardiac", "Medical (non-cardiac) admission", 3, ""),
        ScoringCriterion("hepatic_insufficiency", "Hepatic insufficiency", 6, ""),
        ScoringCriterion("renal_dialysis", "Renal insufficiency/dialysis", 4, ""),
        ScoringCriterion("resp_insufficiency", "Respiratory insufficiency", 4, ""),
        ScoringCriterion("pneumonia", "Pneumonia", 1, ""),
        ScoringCriterion("hypotension_vasopressors", "Hypotension/vasopressors", 4, "Within 4h before arrest"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=14, risk_level=RiskLevel.LOW,
            interpretation="GO-FAR <14 - Moderate chance of good outcome (>10%)", recommendations=["CPR likely beneficial", "Discuss realistic expectations"]),
        ThresholdInterpretation(min_score=14, max_score=24, risk_level=RiskLevel.MODERATE,
            interpretation="GO-FAR 14-23 - Low chance of good outcome (~3-10%)", recommendations=["Discuss goals of care", "CPR may be considered"]),
        ThresholdInterpretation(min_score=24, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="GO-FAR ≥24 - Very low chance of good outcome (<3%)", recommendations=["Consider DNR/POLST", "Comfort-focused care discussion"]),
    ],
)

# OHCA Score - Out-of-Hospital Cardiac Arrest
OHCA_DEFINITION = CalculatorDefinition(
    id="ohca",
    name="OHCA Score (Out-of-Hospital Cardiac Arrest)",
    short_name="OHCA",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.EMERGENCY,
    output_type=OutputType.DECIMAL,
    score_unit="",
    description="Predicts favorable neurologic outcome after OHCA",
    references=["Adrie C, et al. Intensive Care Med. 2006;32(2):232-240. PMID: 16435104"],
    specialties=["Emergency Medicine", "Critical Care", "Cardiology"],
    notes=["For OHCA with ROSC", "Initial assessment score"],
    criteria=[
        ScoringCriterion("shockable_rhythm", "Initial shockable rhythm (VF/pVT)", -3, "Favorable factor"),
        ScoringCriterion("no_flow_lt_5", "No-flow time <5 min or witnessed", -2, "Favorable factor"),
        ScoringCriterion("low_flow_lt_10", "Low-flow time <10 min", -2, "Favorable factor"),
        ScoringCriterion("age_gt_60", "Age >60 years", 2, "Unfavorable"),
        ScoringCriterion("asystole_arrest", "Asystole as initial rhythm", 3, "Unfavorable"),
        ScoringCriterion("no_flow_gt_10", "No-flow time >10 min", 3, "Unfavorable"),
        ScoringCriterion("epinephrine_dose", "Cumulative epinephrine >3 mg", 2, "Unfavorable"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=-10, max_score=0, risk_level=RiskLevel.LOW,
            interpretation="OHCA ≤0 - Better prognosis", recommendations=["Aggressive post-arrest care", "Targeted temperature management"]),
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.MODERATE,
            interpretation="OHCA 1-4 - Intermediate prognosis", recommendations=["Standard post-arrest care", "Serial neuro assessment"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="OHCA ≥5 - Poor prognosis", recommendations=["Consider neuroprognostication at 72h", "Goals of care discussion"]),
    ],
)

# ============================================================================
# CRITICAL CARE & EMERGENCY - TIER 8: MISCELLANEOUS
# ============================================================================

# DIC Score (ISTH)
DIC_ISTH_DEFINITION = CalculatorDefinition(
    id="dic_isth",
    name="ISTH DIC Score",
    short_name="ISTH DIC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.HEMATOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Diagnosis of overt disseminated intravascular coagulation",
    references=["Taylor FB Jr, et al. Thromb Haemost. 2001;86(5):1327-1330. PMID: 11816725"],
    specialties=["Hematology", "Critical Care"],
    notes=["Score ≥5 = overt DIC", "Requires underlying disorder known to cause DIC"],
    multi_level_criteria=[
        MultiLevelCriterion(name="platelets", display_name="Platelet Count",
            levels=[
                ("gte_100", 0, "≥100 (0)"), ("50_99", 1, "50-99 (+1)"), ("lt_50", 2, "<50 (+2)"),
            ], description="Platelets ×10³/µL"),
        MultiLevelCriterion(name="fibrin_markers", display_name="D-dimer/FDP",
            levels=[
                ("normal", 0, "No increase (0)"), ("moderate", 2, "Moderate increase (+2)"),
                ("strong", 3, "Strong increase (+3)"),
            ], description="Fibrin degradation products"),
        MultiLevelCriterion(name="pt", display_name="Prothrombin Time",
            levels=[
                ("lt_3", 0, "<3 sec above ULN (0)"), ("3_6", 1, "3-6 sec above ULN (+1)"),
                ("gt_6", 2, ">6 sec above ULN (+2)"),
            ], description="PT prolongation"),
        MultiLevelCriterion(name="fibrinogen", display_name="Fibrinogen Level",
            levels=[
                ("gte_1", 0, "≥1.0 g/L (0)"), ("lt_1", 1, "<1.0 g/L (+1)"),
            ], description="Plasma fibrinogen"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="DIC score <5 - Not overt DIC", recommendations=["Repeat in 1-2 days if clinically indicated", "Treat underlying condition"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="DIC score ≥5 - Overt DIC", recommendations=["Treat underlying cause", "Supportive transfusions", "Consider anticoagulation per etiology"]),
    ],
)

# 4Ts Score for HIT
HIT_4TS_DEFINITION = CalculatorDefinition(
    id="hit_4ts",
    name="4Ts Score for Heparin-Induced Thrombocytopenia",
    short_name="4Ts",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.HEMATOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Pretest probability of heparin-induced thrombocytopenia",
    references=["Lo GK, et al. J Thromb Haemost. 2006;4(4):759-765. PMID: 16634744"],
    specialties=["Hematology", "Critical Care", "Hospital Medicine"],
    notes=["If low probability, HIT unlikely", "Intermediate/high = send anti-PF4 antibody"],
    multi_level_criteria=[
        MultiLevelCriterion(name="thrombocytopenia", display_name="Thrombocytopenia",
            levels=[
                ("gt_50_drop_and_nadir_20_100", 2, ">50% fall and nadir 20-100 (+2)"),
                ("30_50_drop_or_nadir_10_19", 1, "30-50% fall or nadir 10-19 (+1)"),
                ("lt_30_drop_or_nadir_lt_10", 0, "<30% fall or nadir <10 (0)"),
            ], description="Platelet count fall"),
        MultiLevelCriterion(name="timing", display_name="Timing of Platelet Fall",
            levels=[
                ("day_5_10", 2, "Day 5-10 or ≤1 day if recent heparin (+2)"),
                ("uncertain", 1, ">Day 10 or timing unclear (+1)"),
                ("day_lt_4", 0, "Day ≤4 without recent exposure (0)"),
            ], description="When platelets fell"),
        MultiLevelCriterion(name="thrombosis", display_name="Thrombosis or Other Sequelae",
            levels=[
                ("confirmed", 2, "Confirmed new thrombosis or skin necrosis (+2)"),
                ("progressive", 1, "Progressive or recurrent thrombosis (+1)"),
                ("none", 0, "None (0)"),
            ], description="Thrombotic complications"),
        MultiLevelCriterion(name="other_causes", display_name="Other Causes of Thrombocytopenia",
            levels=[
                ("none_evident", 2, "No other cause evident (+2)"),
                ("possible", 1, "Possible other cause (+1)"),
                ("definite", 0, "Definite other cause (0)"),
            ], description="Alternative explanations"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.LOW,
            interpretation="4Ts 0-3 - Low probability (<5%)", recommendations=["HIT unlikely", "Investigate other causes", "Can continue heparin"]),
        ThresholdInterpretation(min_score=4, max_score=6, risk_level=RiskLevel.MODERATE,
            interpretation="4Ts 4-5 - Intermediate probability (~14%)", recommendations=["Send anti-PF4/heparin antibody", "Consider stopping heparin"]),
        ThresholdInterpretation(min_score=6, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="4Ts 6-8 - High probability (~64%)", recommendations=["Stop all heparin", "Start non-heparin anticoagulant", "Send HIT antibody"]),
    ],
)

# NEWS (Original) - National Early Warning Score
NEWS_DEFINITION = CalculatorDefinition(
    id="news",
    name="National Early Warning Score (NEWS)",
    short_name="NEWS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Early warning score to detect clinical deterioration",
    references=["Royal College of Physicians. National Early Warning Score. 2012"],
    specialties=["Emergency Medicine", "Critical Care", "Internal Medicine", "Nursing"],
    notes=["Predecessor to NEWS2", "Score of 3 in any single parameter warrants concern"],
    multi_level_criteria=[
        MultiLevelCriterion(name="respiratory_rate", display_name="Respiratory Rate",
            levels=[
                ("leq_8", 3, "≤8 (3)"), ("9_11", 1, "9-11 (1)"), ("12_20", 0, "12-20 (0)"),
                ("21_24", 2, "21-24 (2)"), ("gte_25", 3, "≥25 (3)"),
            ], description="Breaths/min"),
        MultiLevelCriterion(name="spo2", display_name="SpO2",
            levels=[
                ("leq_91", 3, "≤91% (3)"), ("92_93", 2, "92-93% (2)"),
                ("94_95", 1, "94-95% (1)"), ("gte_96", 0, "≥96% (0)"),
            ], description="Oxygen saturation"),
        MultiLevelCriterion(name="supplemental_o2", display_name="Supplemental O2",
            levels=[("yes", 2, "Yes (2)"), ("no", 0, "No (0)")], description="On supplemental oxygen"),
        MultiLevelCriterion(name="temperature", display_name="Temperature",
            levels=[
                ("leq_35", 3, "≤35°C (3)"), ("35_1_36", 1, "35.1-36°C (1)"),
                ("36_1_38", 0, "36.1-38°C (0)"), ("38_1_39", 1, "38.1-39°C (1)"), ("gte_39_1", 2, "≥39.1°C (2)"),
            ], description="Temperature °C"),
        MultiLevelCriterion(name="systolic_bp", display_name="Systolic BP",
            levels=[
                ("leq_90", 3, "≤90 (3)"), ("91_100", 2, "91-100 (2)"), ("101_110", 1, "101-110 (1)"),
                ("111_219", 0, "111-219 (0)"), ("gte_220", 3, "≥220 (3)"),
            ], description="Systolic BP mmHg"),
        MultiLevelCriterion(name="heart_rate", display_name="Heart Rate",
            levels=[
                ("leq_40", 3, "≤40 (3)"), ("41_50", 1, "41-50 (1)"), ("51_90", 0, "51-90 (0)"),
                ("91_110", 1, "91-110 (1)"), ("111_130", 2, "111-130 (2)"), ("gte_131", 3, "≥131 (3)"),
            ], description="Heart rate bpm"),
        MultiLevelCriterion(name="consciousness", display_name="Consciousness",
            levels=[("alert", 0, "Alert (0)"), ("not_alert", 3, "V/P/U (3)")], description="AVPU scale"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk", recommendations=["Continue routine monitoring"]),
        ThresholdInterpretation(min_score=1, max_score=5, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low-medium risk", recommendations=["Increase monitoring frequency", "Nurse assessment"]),
        ThresholdInterpretation(min_score=5, max_score=7, risk_level=RiskLevel.MODERATE,
            interpretation="Medium risk", recommendations=["Urgent physician review", "Consider ICU consultation"]),
        ThresholdInterpretation(min_score=7, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk - Emergency response", recommendations=["Immediate physician assessment", "Critical care team"]),
    ],
)


# ============================================================================
# SPECIALTY CALCULATORS - NEUROLOGY
# ============================================================================

# NIH Stroke Scale (NIHSS)
NIHSS_DEFINITION = CalculatorDefinition(
    id="nihss",
    name="NIH Stroke Scale",
    short_name="NIHSS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Quantifies stroke severity (0-42 points)",
    references=["Brott T, et al. Stroke 1989;20:864-870", "Lyden P, et al. Stroke 1994;25:2220-2226"],
    specialties=["Neurology", "Emergency Medicine", "Critical Care"],
    multi_level_criteria=[
        MultiLevelCriterion(name="loc", display_name="1a. Level of Consciousness",
            levels=[("alert", 0, "Alert (0)"), ("drowsy", 1, "Not alert, arousable (1)"),
                    ("obtunded", 2, "Not alert, requires repeated stimulation (2)"), ("coma", 3, "Unresponsive (3)")]),
        MultiLevelCriterion(name="loc_questions", display_name="1b. LOC Questions",
            levels=[("both_correct", 0, "Both correct (0)"), ("one_correct", 1, "One correct (1)"), ("neither", 2, "Neither correct (2)")]),
        MultiLevelCriterion(name="loc_commands", display_name="1c. LOC Commands",
            levels=[("both_correct", 0, "Both correct (0)"), ("one_correct", 1, "One correct (1)"), ("neither", 2, "Neither correct (2)")]),
        MultiLevelCriterion(name="gaze", display_name="2. Best Gaze",
            levels=[("normal", 0, "Normal (0)"), ("partial", 1, "Partial gaze palsy (1)"), ("forced", 2, "Forced deviation (2)")]),
        MultiLevelCriterion(name="visual", display_name="3. Visual Fields",
            levels=[("normal", 0, "No visual loss (0)"), ("partial", 1, "Partial hemianopia (1)"),
                    ("complete", 2, "Complete hemianopia (2)"), ("bilateral", 3, "Bilateral hemianopia (3)")]),
        MultiLevelCriterion(name="facial", display_name="4. Facial Palsy",
            levels=[("normal", 0, "Normal (0)"), ("minor", 1, "Minor paralysis (1)"),
                    ("partial", 2, "Partial paralysis (2)"), ("complete", 3, "Complete paralysis (3)")]),
        MultiLevelCriterion(name="motor_left_arm", display_name="5a. Motor Arm - Left",
            levels=[("normal", 0, "No drift (0)"), ("drift", 1, "Drift (1)"), ("some_effort", 2, "Some effort against gravity (2)"),
                    ("no_effort", 3, "No effort against gravity (3)"), ("no_movement", 4, "No movement (4)")]),
        MultiLevelCriterion(name="motor_right_arm", display_name="5b. Motor Arm - Right",
            levels=[("normal", 0, "No drift (0)"), ("drift", 1, "Drift (1)"), ("some_effort", 2, "Some effort against gravity (2)"),
                    ("no_effort", 3, "No effort against gravity (3)"), ("no_movement", 4, "No movement (4)")]),
        MultiLevelCriterion(name="motor_left_leg", display_name="6a. Motor Leg - Left",
            levels=[("normal", 0, "No drift (0)"), ("drift", 1, "Drift (1)"), ("some_effort", 2, "Some effort against gravity (2)"),
                    ("no_effort", 3, "No effort against gravity (3)"), ("no_movement", 4, "No movement (4)")]),
        MultiLevelCriterion(name="motor_right_leg", display_name="6b. Motor Leg - Right",
            levels=[("normal", 0, "No drift (0)"), ("drift", 1, "Drift (1)"), ("some_effort", 2, "Some effort against gravity (2)"),
                    ("no_effort", 3, "No effort against gravity (3)"), ("no_movement", 4, "No movement (4)")]),
        MultiLevelCriterion(name="ataxia", display_name="7. Limb Ataxia",
            levels=[("absent", 0, "Absent (0)"), ("one_limb", 1, "Present in one limb (1)"), ("two_limbs", 2, "Present in two limbs (2)")]),
        MultiLevelCriterion(name="sensory", display_name="8. Sensory",
            levels=[("normal", 0, "Normal (0)"), ("mild", 1, "Mild-moderate loss (1)"), ("severe", 2, "Severe/total loss (2)")]),
        MultiLevelCriterion(name="language", display_name="9. Best Language",
            levels=[("normal", 0, "No aphasia (0)"), ("mild", 1, "Mild-moderate aphasia (1)"),
                    ("severe", 2, "Severe aphasia (2)"), ("mute", 3, "Mute/global aphasia (3)")]),
        MultiLevelCriterion(name="dysarthria", display_name="10. Dysarthria",
            levels=[("normal", 0, "Normal (0)"), ("mild", 1, "Mild-moderate (1)"), ("severe", 2, "Severe/mute (2)")]),
        MultiLevelCriterion(name="extinction", display_name="11. Extinction/Inattention",
            levels=[("normal", 0, "No abnormality (0)"), ("partial", 1, "Partial (1)"), ("profound", 2, "Profound (2)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="Minor stroke", recommendations=["Consider tPA if within window", "Stroke unit admission", "Aspirin if not tPA candidate"]),
        ThresholdInterpretation(min_score=5, max_score=15, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate stroke", recommendations=["tPA candidate if within window", "Evaluate for thrombectomy if LVO", "ICU monitoring"]),
        ThresholdInterpretation(min_score=15, max_score=25, risk_level=RiskLevel.HIGH,
            interpretation="Moderate-severe stroke", recommendations=["Urgent reperfusion therapy", "Thrombectomy evaluation", "ICU admission"]),
        ThresholdInterpretation(min_score=25, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe stroke", recommendations=["High mortality risk", "Goals of care discussion", "Aggressive supportive care"]),
    ],
)

# Hunt & Hess Scale (SAH)
HUNT_HESS_DEFINITION = CalculatorDefinition(
    id="hunt_hess",
    name="Hunt & Hess Scale",
    short_name="Hunt-Hess",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="grade",
    description="Clinical grading of subarachnoid hemorrhage severity",
    references=["Hunt WE, Hess RM. J Neurosurg 1968;28:14-20"],
    specialties=["Neurology", "Neurosurgery", "Critical Care"],
    multi_level_criteria=[
        MultiLevelCriterion(name="grade", display_name="Clinical Grade",
            levels=[
                ("grade_1", 1, "Grade 1: Asymptomatic or mild headache"),
                ("grade_2", 2, "Grade 2: Moderate-severe headache, nuchal rigidity, no deficit except CN palsy"),
                ("grade_3", 3, "Grade 3: Drowsy, confused, or mild focal deficit"),
                ("grade_4", 4, "Grade 4: Stupor, moderate-severe hemiparesis"),
                ("grade_5", 5, "Grade 5: Deep coma, decerebrate rigidity, moribund"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Good grade SAH - surgical mortality ~1-5%",
            recommendations=["Early aneurysm treatment", "ICU monitoring", "Nimodipine prophylaxis"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate grade SAH - mortality ~10-20%",
            recommendations=["ICU admission", "Consider EVD if hydrocephalus", "Vasospasm monitoring"]),
        ThresholdInterpretation(min_score=4, max_score=5, risk_level=RiskLevel.HIGH,
            interpretation="Poor grade SAH - mortality ~40%",
            recommendations=["ICU admission", "Aggressive ICP management", "EVD placement"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Critical SAH - mortality >70%",
            recommendations=["Stabilization before intervention", "Goals of care discussion", "Family meeting"]),
    ],
)

# Fisher Grade (SAH CT)
FISHER_GRADE_DEFINITION = CalculatorDefinition(
    id="fisher_grade",
    name="Fisher Grade",
    short_name="Fisher",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="grade",
    description="CT-based grading of SAH for vasospasm risk",
    references=["Fisher CM, et al. Neurosurgery 1980;6:1-9"],
    specialties=["Neurology", "Neurosurgery", "Radiology"],
    multi_level_criteria=[
        MultiLevelCriterion(name="grade", display_name="CT Findings",
            levels=[
                ("grade_1", 1, "Grade 1: No blood detected"),
                ("grade_2", 2, "Grade 2: Diffuse thin (<1mm) SAH"),
                ("grade_3", 3, "Grade 3: Localized clot or thick (>1mm) SAH"),
                ("grade_4", 4, "Grade 4: Intracerebral or intraventricular clot with diffuse/no SAH"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Low vasospasm risk (~20%)", recommendations=["Standard monitoring", "Nimodipine", "Daily TCDs"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate vasospasm risk (~30%)", recommendations=["Close TCD monitoring", "Consider CTA if symptomatic"]),
        ThresholdInterpretation(min_score=3, max_score=4, risk_level=RiskLevel.HIGH,
            interpretation="High vasospasm risk (~50%)", recommendations=["Aggressive vasospasm monitoring", "Early angio if symptomatic"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk with ICH/IVH component", recommendations=["Consider EVD", "Monitor for hydrocephalus"]),
    ],
)

# Modified Fisher Scale
MODIFIED_FISHER_DEFINITION = CalculatorDefinition(
    id="modified_fisher",
    name="Modified Fisher Scale",
    short_name="Mod Fisher",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="grade",
    description="Modified CT grading for SAH vasospasm prediction",
    references=["Frontera JA, et al. Neurosurgery 2006;59:21-27"],
    specialties=["Neurology", "Neurosurgery", "Critical Care"],
    multi_level_criteria=[
        MultiLevelCriterion(name="grade", display_name="CT Findings",
            levels=[
                ("grade_0", 0, "Grade 0: No SAH or IVH"),
                ("grade_1", 1, "Grade 1: Thin SAH, no IVH"),
                ("grade_2", 2, "Grade 2: Thin SAH with IVH"),
                ("grade_3", 3, "Grade 3: Thick SAH, no IVH"),
                ("grade_4", 4, "Grade 4: Thick SAH with IVH"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low vasospasm risk (0-15%)", recommendations=["Standard monitoring", "Nimodipine"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate vasospasm risk (20-35%)", recommendations=["TCD monitoring", "Consider angio if symptomatic"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High vasospasm risk (40%)", recommendations=["Aggressive monitoring", "Early intervention if DCI"]),
    ],
)

# WFNS Grade (SAH)
WFNS_GRADE_DEFINITION = CalculatorDefinition(
    id="wfns_grade",
    name="World Federation of Neurological Surgeons Grade",
    short_name="WFNS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="grade",
    description="SAH grading based on GCS and motor deficit",
    references=["Drake CG. J Neurosurg 1988;68:985-986"],
    specialties=["Neurology", "Neurosurgery"],
    multi_level_criteria=[
        MultiLevelCriterion(name="grade", display_name="Clinical Grade",
            levels=[
                ("grade_1", 1, "Grade I: GCS 15, no motor deficit"),
                ("grade_2", 2, "Grade II: GCS 13-14, no motor deficit"),
                ("grade_3", 3, "Grade III: GCS 13-14 with motor deficit"),
                ("grade_4", 4, "Grade IV: GCS 7-12"),
                ("grade_5", 5, "Grade V: GCS 3-6"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Good grade - mortality <10%", recommendations=["Early aneurysm treatment", "Standard monitoring"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate grade", recommendations=["ICU admission", "Consider early vs delayed treatment"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Poor grade - mortality >50%", recommendations=["Stabilization", "Goals of care discussion"]),
    ],
)

# ICH Score
ICH_SCORE_DEFINITION = CalculatorDefinition(
    id="ich_score",
    name="ICH Score",
    short_name="ICH Score",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="30-day mortality prediction for intracerebral hemorrhage",
    references=["Hemphill JC, et al. Stroke 2001;32:891-897"],
    specialties=["Neurology", "Neurosurgery", "Emergency Medicine", "Critical Care"],
    multi_level_criteria=[
        MultiLevelCriterion(name="gcs", display_name="GCS Score",
            levels=[("13_15", 0, "GCS 13-15 (0)"), ("5_12", 1, "GCS 5-12 (1)"), ("3_4", 2, "GCS 3-4 (2)")]),
        MultiLevelCriterion(name="volume", display_name="ICH Volume",
            levels=[("lt_30", 0, "< 30 mL (0)"), ("gte_30", 1, "≥ 30 mL (1)")]),
        MultiLevelCriterion(name="ivh", display_name="Intraventricular Hemorrhage",
            levels=[("no", 0, "No (0)"), ("yes", 1, "Yes (1)")]),
        MultiLevelCriterion(name="infratentorial", display_name="Infratentorial Origin",
            levels=[("no", 0, "No (0)"), ("yes", 1, "Yes (1)")]),
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[("lt_80", 0, "< 80 years (0)"), ("gte_80", 1, "≥ 80 years (1)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="30-day mortality 0-13%", recommendations=["ICU admission", "Blood pressure management", "Repeat imaging"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="30-day mortality 26-72%", recommendations=["ICU admission", "Consider surgical evaluation", "Goals of care"]),
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.HIGH,
            interpretation="30-day mortality 72-97%", recommendations=["Goals of care discussion", "Family meeting", "Comfort care consideration"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="30-day mortality ~100%", recommendations=["Comfort-focused care", "Family support"]),
    ],
)

# FUNC Score (ICH Functional Outcome)
FUNC_SCORE_DEFINITION = CalculatorDefinition(
    id="func_score",
    name="FUNC Score",
    short_name="FUNC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts functional independence at 90 days after ICH",
    references=["Rost NS, et al. Stroke 2008;39:2304-2309"],
    specialties=["Neurology", "Neurosurgery", "Critical Care"],
    multi_level_criteria=[
        MultiLevelCriterion(name="volume", display_name="ICH Volume",
            levels=[("lt_30", 4, "< 30 mL (4)"), ("30_60", 2, "30-60 mL (2)"), ("gt_60", 0, "> 60 mL (0)")]),
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[("lt_70", 2, "< 70 years (2)"), ("70_79", 1, "70-79 years (1)"), ("gte_80", 0, "≥ 80 years (0)")]),
        MultiLevelCriterion(name="location", display_name="ICH Location",
            levels=[("lobar", 2, "Lobar (2)"), ("deep", 1, "Deep (1)"), ("infratentorial", 0, "Infratentorial (0)")]),
        MultiLevelCriterion(name="gcs", display_name="GCS Score",
            levels=[("gte_9", 2, "GCS ≥ 9 (2)"), ("lt_9", 0, "GCS < 9 (0)")]),
        MultiLevelCriterion(name="cognitive", display_name="Pre-ICH Cognitive Impairment",
            levels=[("no", 1, "No (1)"), ("yes", 0, "Yes (0)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Functional independence unlikely (<20%)", recommendations=["Goals of care discussion", "Palliative care consultation"]),
        ThresholdInterpretation(min_score=4, max_score=8, risk_level=RiskLevel.HIGH,
            interpretation="Low probability of independence (20-50%)", recommendations=["Aggressive treatment if consistent with goals", "Rehab planning"]),
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="Good probability of independence (>70%)", recommendations=["Aggressive acute treatment", "Early rehab"]),
    ],
)

# Canadian CT Head Rule
CANADIAN_CT_HEAD_DEFINITION = CalculatorDefinition(
    id="canadian_ct_head",
    name="Canadian CT Head Rule",
    short_name="CCHR",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies minor head injury patients who need CT",
    references=["Stiell IG, et al. Lancet 2001;357:1391-1396"],
    specialties=["Emergency Medicine", "Neurology", "Trauma"],
    notes=["Applies to GCS 13-15, age ≥16, injury within 24h", "Does NOT apply if: anticoagulation, seizure, or obvious skull fracture"],
    criteria=[
        ScoringCriterion("gcs_below_15_at_2hr", "GCS <15 at 2 hours post-injury", 1, "High risk criterion"),
        ScoringCriterion("suspected_skull_fracture", "Suspected open/depressed skull fracture", 1, "High risk criterion"),
        ScoringCriterion("skull_base_fracture_signs", "Signs of basal skull fracture", 1, "Hemotympanum, raccoon eyes, CSF otorrhea/rhinorrhea, Battle's sign"),
        ScoringCriterion("vomiting_2_episodes", "≥2 episodes of vomiting", 1, "High risk criterion"),
        ScoringCriterion("age_65_plus", "Age ≥65 years", 1, "High risk criterion"),
        ScoringCriterion("amnesia_30min", "Amnesia before impact >30 min", 1, "Medium risk criterion"),
        ScoringCriterion("dangerous_mechanism", "Dangerous mechanism", 1, "Pedestrian struck, ejected from vehicle, fall >3 feet/5 stairs"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="No CT required", recommendations=["Observe and discharge with head injury instructions", "Return if symptoms worsen"]),
        ThresholdInterpretation(min_score=1, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="CT head indicated", recommendations=["Obtain CT head without contrast", "Neurosurgery consult if positive"]),
    ],
)

# PECARN Pediatric Head Injury
PECARN_HEAD_DEFINITION = CalculatorDefinition(
    id="pecarn_head",
    name="PECARN Pediatric Head Injury/Trauma Algorithm",
    short_name="PECARN",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies children at very low risk of clinically important TBI",
    references=["Kuppermann N, et al. Lancet 2009;374:1160-1170"],
    specialties=["Pediatric Emergency Medicine", "Emergency Medicine", "Pediatrics"],
    notes=["Different criteria for <2 years and ≥2 years", "GCS must be 14-15 to apply"],
    criteria=[
        ScoringCriterion("gcs_below_15", "GCS < 15", 2, "Altered mental status"),
        ScoringCriterion("altered_mental_status", "Other signs of altered mental status", 2, "Agitation, somnolence, repetitive questioning, slow response"),
        ScoringCriterion("palpable_skull_fracture", "Palpable skull fracture (age <2)", 2, "For children under 2 years"),
        ScoringCriterion("scalp_hematoma", "Non-frontal scalp hematoma (age <2)", 1, "Occipital, parietal, or temporal hematoma"),
        ScoringCriterion("loc_5_sec", "Loss of consciousness ≥5 sec", 1, ""),
        ScoringCriterion("severe_mechanism", "Severe mechanism of injury", 1, "MVC with ejection/death/rollover, struck by high-impact object, fall >3 feet (<2yo) or >5 feet (≥2yo)"),
        ScoringCriterion("not_acting_normally", "Not acting normally per parent", 1, "For children under 2 years"),
        ScoringCriterion("signs_basilar_skull_fx", "Signs of basilar skull fracture (age ≥2)", 2, "Hemotympanum, periorbital ecchymosis, CSF leak"),
        ScoringCriterion("severe_headache", "Severe headache (age ≥2)", 1, ""),
        ScoringCriterion("vomiting", "Vomiting", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Very low risk of ciTBI (<0.05%)", recommendations=["CT not recommended", "Observation appropriate", "Discharge with precautions"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low-intermediate risk", recommendations=["Consider observation vs CT", "CT if worsening or multiple findings"]),
        ThresholdInterpretation(min_score=2, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="Higher risk of ciTBI", recommendations=["CT head recommended", "Close observation if CT deferred"]),
    ],
)

# Ottawa SAH Rule
OTTAWA_SAH_DEFINITION = CalculatorDefinition(
    id="ottawa_sah",
    name="Ottawa SAH Rule",
    short_name="Ottawa SAH",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies patients with headache who need investigation for SAH",
    references=["Perry JJ, et al. JAMA 2013;310:1248-1255"],
    specialties=["Emergency Medicine", "Neurology"],
    notes=["Applies to alert patients ≥15 years with new severe non-traumatic headache peaking within 1 hour"],
    criteria=[
        ScoringCriterion("age_40_plus", "Age ≥40 years", 1, ""),
        ScoringCriterion("neck_pain_stiffness", "Neck pain or stiffness", 1, ""),
        ScoringCriterion("witnessed_loc", "Witnessed loss of consciousness", 1, ""),
        ScoringCriterion("onset_exertion", "Onset during exertion", 1, ""),
        ScoringCriterion("thunderclap_headache", "Thunderclap headache (instant peak)", 1, ""),
        ScoringCriterion("limited_neck_flexion", "Limited neck flexion on exam", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="SAH very unlikely - rule negative", recommendations=["SAH essentially ruled out", "Consider other diagnoses", "Return if worse"]),
        ThresholdInterpretation(min_score=1, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Cannot rule out SAH", recommendations=["CT head without contrast", "LP if CT negative", "CTA if high suspicion"]),
    ],
)

# FOUR Score (Full Outline of UnResponsiveness)
FOUR_SCORE_DEFINITION = CalculatorDefinition(
    id="four_score",
    name="FOUR Score",
    short_name="FOUR",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Coma scale that includes brainstem reflexes and respiration",
    references=["Wijdicks EF, et al. Ann Neurol 2005;58:585-593"],
    specialties=["Neurology", "Critical Care", "Emergency Medicine"],
    notes=["Range 0-16; can assess intubated patients unlike GCS verbal"],
    multi_level_criteria=[
        MultiLevelCriterion(name="eye", display_name="Eye Response",
            levels=[
                ("e4", 4, "Eyelids open, tracking or blinking to command (4)"),
                ("e3", 3, "Eyelids open but not tracking (3)"),
                ("e2", 2, "Eyelids closed, open to loud voice (2)"),
                ("e1", 1, "Eyelids closed, open to pain (1)"),
                ("e0", 0, "Eyelids remain closed with pain (0)"),
            ]),
        MultiLevelCriterion(name="motor", display_name="Motor Response",
            levels=[
                ("m4", 4, "Thumbs-up, fist, or peace sign (4)"),
                ("m3", 3, "Localizing to pain (3)"),
                ("m2", 2, "Flexion response to pain (2)"),
                ("m1", 1, "Extension response to pain (1)"),
                ("m0", 0, "No response or myoclonus status (0)"),
            ]),
        MultiLevelCriterion(name="brainstem", display_name="Brainstem Reflexes",
            levels=[
                ("b4", 4, "Pupil and corneal reflexes present (4)"),
                ("b3", 3, "One pupil wide and fixed (3)"),
                ("b2", 2, "Pupil OR corneal reflexes absent (2)"),
                ("b1", 1, "Pupil AND corneal reflexes absent (1)"),
                ("b0", 0, "Absent pupil, corneal, and cough reflexes (0)"),
            ]),
        MultiLevelCriterion(name="respiration", display_name="Respiration",
            levels=[
                ("r4", 4, "Not intubated, regular breathing (4)"),
                ("r3", 3, "Not intubated, Cheyne-Stokes breathing (3)"),
                ("r2", 2, "Not intubated, irregular breathing (2)"),
                ("r1", 1, "Breathes above ventilator rate (1)"),
                ("r0", 0, "Breathes at ventilator rate or apnea (0)"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe impairment - poor prognosis", recommendations=["Consider brain death evaluation if score 0", "Goals of care", "Neurology consultation"]),
        ThresholdInterpretation(min_score=4, max_score=8, risk_level=RiskLevel.HIGH,
            interpretation="Significant neurological impairment", recommendations=["ICU monitoring", "Serial assessments", "Prognostic studies"]),
        ThresholdInterpretation(min_score=8, max_score=12, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate impairment", recommendations=["ICU monitoring", "Identify reversible causes"]),
        ThresholdInterpretation(min_score=12, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Mild impairment or normal", recommendations=["Continue monitoring", "Identify etiology"]),
    ],
)

# Modified Rankin Scale (mRS)
MRS_DEFINITION = CalculatorDefinition(
    id="mrs",
    name="Modified Rankin Scale",
    short_name="mRS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="grade",
    description="Measures degree of disability/dependence after stroke",
    references=["van Swieten JC, et al. Stroke 1988;19:604-607", "Bonita R, Beaglehole R. Stroke 1988;19:1497-1500"],
    specialties=["Neurology", "Rehabilitation", "Stroke"],
    multi_level_criteria=[
        MultiLevelCriterion(name="grade", display_name="Functional Status",
            levels=[
                ("grade_0", 0, "0: No symptoms"),
                ("grade_1", 1, "1: No significant disability despite symptoms"),
                ("grade_2", 2, "2: Slight disability - unable to do all previous activities but independent"),
                ("grade_3", 3, "3: Moderate disability - requires some help but walks without assistance"),
                ("grade_4", 4, "4: Moderately severe disability - unable to walk/attend bodily needs without assistance"),
                ("grade_5", 5, "5: Severe disability - bedridden, incontinent, requires constant care"),
                ("grade_6", 6, "6: Dead"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Good outcome - functional independence", recommendations=["Continue secondary prevention", "Outpatient rehabilitation"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate disability", recommendations=["Inpatient or outpatient rehab", "Home health evaluation"]),
        ThresholdInterpretation(min_score=4, max_score=6, risk_level=RiskLevel.HIGH,
            interpretation="Severe disability", recommendations=["Skilled nursing or long-term care", "Goals of care discussion"]),
        ThresholdInterpretation(min_score=6, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Death", recommendations=[]),
    ],
)

# ============================================================================
# SPECIALTY CALCULATORS - ONCOLOGY
# ============================================================================

# ECOG Performance Status
ECOG_DEFINITION = CalculatorDefinition(
    id="ecog",
    name="ECOG Performance Status",
    short_name="ECOG PS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="grade",
    description="Functional status scale for cancer patients",
    references=["Oken MM, et al. Am J Clin Oncol 1982;5:649-655"],
    specialties=["Oncology", "Palliative Care", "Internal Medicine"],
    multi_level_criteria=[
        MultiLevelCriterion(name="status", display_name="Performance Status",
            levels=[
                ("ps_0", 0, "0: Fully active, no restrictions"),
                ("ps_1", 1, "1: Restricted in strenuous activity, ambulatory, light work"),
                ("ps_2", 2, "2: Ambulatory, capable of self-care, up >50% of waking hours"),
                ("ps_3", 3, "3: Limited self-care, confined to bed/chair >50% of waking hours"),
                ("ps_4", 4, "4: Completely disabled, no self-care, totally confined"),
                ("ps_5", 5, "5: Dead"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Good functional status", recommendations=["Typically eligible for most clinical trials", "Standard chemotherapy appropriate"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mildly impaired", recommendations=["May be eligible for chemotherapy", "Consider performance status in treatment planning"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Moderately impaired", recommendations=["Modified chemotherapy regimens", "Consider best supportive care"]),
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.HIGH,
            interpretation="Severely impaired", recommendations=["Best supportive care", "Palliative care consultation", "Goals of care discussion"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Dead", recommendations=[]),
    ],
)

# Karnofsky Performance Status
KARNOFSKY_DEFINITION = CalculatorDefinition(
    id="karnofsky",
    name="Karnofsky Performance Status",
    short_name="KPS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="%",
    description="Functional impairment scale (100-0%)",
    references=["Karnofsky DA, Burchenal JH. 1949"],
    specialties=["Oncology", "Palliative Care", "Radiation Oncology"],
    multi_level_criteria=[
        MultiLevelCriterion(name="status", display_name="Functional Status",
            levels=[
                ("kps_100", 100, "100: Normal, no complaints"),
                ("kps_90", 90, "90: Able to carry on normal activity; minor symptoms"),
                ("kps_80", 80, "80: Normal activity with effort; some symptoms"),
                ("kps_70", 70, "70: Cares for self; unable to carry on normal activity/work"),
                ("kps_60", 60, "60: Requires occasional assistance; cares for most needs"),
                ("kps_50", 50, "50: Requires considerable assistance and frequent medical care"),
                ("kps_40", 40, "40: Disabled; requires special care and assistance"),
                ("kps_30", 30, "30: Severely disabled; hospitalization indicated"),
                ("kps_20", 20, "20: Very sick; active supportive treatment necessary"),
                ("kps_10", 10, "10: Moribund; fatal processes progressing rapidly"),
                ("kps_0", 0, "0: Dead"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=80, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Able to carry on normal activity", recommendations=["Eligible for most treatments", "Standard therapy appropriate"]),
        ThresholdInterpretation(min_score=60, max_score=80, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Unable to work but able to live at home", recommendations=["Modified treatment regimens", "Home care support"]),
        ThresholdInterpretation(min_score=40, max_score=60, risk_level=RiskLevel.MODERATE,
            interpretation="Unable to care for self", recommendations=["Consider palliative therapy", "Supportive care focus"]),
        ThresholdInterpretation(min_score=0, max_score=40, risk_level=RiskLevel.HIGH,
            interpretation="Very disabled/dying", recommendations=["Comfort care", "Hospice consideration"]),
    ],
)

# Palliative Performance Scale (PPS)
PPS_DEFINITION = CalculatorDefinition(
    id="pps",
    name="Palliative Performance Scale",
    short_name="PPS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="%",
    description="Functional status for palliative care prognosis",
    references=["Anderson F, et al. J Palliat Care 1996;12:5-11"],
    specialties=["Palliative Care", "Oncology", "Hospice"],
    multi_level_criteria=[
        MultiLevelCriterion(name="level", display_name="PPS Level",
            levels=[
                ("pps_100", 100, "100: Full ambulation, normal activity, no evidence of disease"),
                ("pps_90", 90, "90: Full ambulation, normal activity, some evidence of disease"),
                ("pps_80", 80, "80: Full ambulation, normal activity with effort"),
                ("pps_70", 70, "70: Reduced ambulation, unable to do normal job/work"),
                ("pps_60", 60, "60: Reduced ambulation, unable to do hobbies, occasional assistance"),
                ("pps_50", 50, "50: Mainly sit/lie, considerable assistance needed"),
                ("pps_40", 40, "40: Mainly in bed, extensive assistance needed"),
                ("pps_30", 30, "30: Totally bed bound, total care"),
                ("pps_20", 20, "20: Totally bed bound, total care, minimal intake"),
                ("pps_10", 10, "10: Totally bed bound, total care, mouth care only"),
                ("pps_0", 0, "0: Death"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=70, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Good functional status - median survival months", recommendations=["Continue disease-directed therapy if indicated"]),
        ThresholdInterpretation(min_score=50, max_score=70, risk_level=RiskLevel.MODERATE,
            interpretation="Declining function - median survival weeks to months", recommendations=["Goals of care discussion", "Advance care planning"]),
        ThresholdInterpretation(min_score=30, max_score=50, risk_level=RiskLevel.HIGH,
            interpretation="Poor function - median survival days to weeks", recommendations=["Hospice referral", "Comfort-focused care"]),
        ThresholdInterpretation(min_score=0, max_score=30, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very poor function - median survival days", recommendations=["Comfort care", "Family support"]),
    ],
)

# International Prognostic Index (IPI) - NHL
IPI_DEFINITION = CalculatorDefinition(
    id="ipi",
    name="International Prognostic Index (IPI)",
    short_name="IPI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Prognosis for aggressive non-Hodgkin lymphoma",
    references=["The International NHL Prognostic Factors Project. N Engl J Med 1993;329:987-994"],
    specialties=["Oncology", "Hematology"],
    criteria=[
        ScoringCriterion("age_over_60", "Age >60 years", 1, ""),
        ScoringCriterion("stage_iii_iv", "Ann Arbor stage III-IV", 1, ""),
        ScoringCriterion("elevated_ldh", "Elevated LDH", 1, "LDH above upper limit of normal"),
        ScoringCriterion("ecog_2_plus", "ECOG PS ≥2", 1, ""),
        ScoringCriterion("extranodal_sites_gt_1", ">1 extranodal site", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk - 5-year OS ~73%", recommendations=["Standard immunochemotherapy", "R-CHOP or equivalent"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Low-intermediate risk - 5-year OS ~51%", recommendations=["Standard immunochemotherapy", "Consider clinical trials"]),
        ThresholdInterpretation(min_score=2, max_score=4, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="High-intermediate risk - 5-year OS ~43%", recommendations=["Intensive chemotherapy", "Clinical trial consideration"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk - 5-year OS ~26%", recommendations=["Aggressive therapy", "Clinical trials", "Consider stem cell transplant"]),
    ],
)

# FLIPI - Follicular Lymphoma
FLIPI_DEFINITION = CalculatorDefinition(
    id="flipi",
    name="Follicular Lymphoma International Prognostic Index",
    short_name="FLIPI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Prognosis for follicular lymphoma",
    references=["Solal-Celigny P, et al. Blood 2004;104:1258-1265"],
    specialties=["Oncology", "Hematology"],
    criteria=[
        ScoringCriterion("age_over_60", "Age >60 years", 1, ""),
        ScoringCriterion("stage_iii_iv", "Ann Arbor stage III-IV", 1, ""),
        ScoringCriterion("elevated_ldh", "Elevated LDH", 1, ""),
        ScoringCriterion("hemoglobin_lt_12", "Hemoglobin <12 g/dL", 1, ""),
        ScoringCriterion("nodal_areas_gt_4", ">4 nodal areas", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk - 10-year OS ~71%", recommendations=["Watch and wait if asymptomatic", "Treatment when indicated"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk - 10-year OS ~51%", recommendations=["Consider early treatment", "Immunochemotherapy when symptomatic"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk - 10-year OS ~36%", recommendations=["Consider early treatment", "Clinical trials", "Maintenance therapy"]),
    ],
)

# International Staging System (ISS) - Myeloma
ISS_MYELOMA_DEFINITION = CalculatorDefinition(
    id="iss_myeloma",
    name="International Staging System (Myeloma)",
    short_name="ISS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="stage",
    description="Staging and prognosis for multiple myeloma",
    references=["Greipp PR, et al. J Clin Oncol 2005;23:3412-3420"],
    specialties=["Oncology", "Hematology"],
    multi_level_criteria=[
        MultiLevelCriterion(name="stage", display_name="ISS Stage",
            levels=[
                ("stage_1", 1, "Stage I: B2M <3.5 mg/L AND albumin ≥3.5 g/dL"),
                ("stage_2", 2, "Stage II: Neither stage I nor III"),
                ("stage_3", 3, "Stage III: B2M ≥5.5 mg/L"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Stage I - Median OS 62 months", recommendations=["Standard induction therapy", "Consider transplant if eligible"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Stage II - Median OS 44 months", recommendations=["Induction therapy", "Transplant evaluation"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Stage III - Median OS 29 months", recommendations=["Aggressive therapy", "Clinical trials consideration"]),
    ],
)

# MASCC Score (Febrile Neutropenia Risk)
MASCC_DEFINITION = CalculatorDefinition(
    id="mascc",
    name="MASCC Risk Index for Febrile Neutropenia",
    short_name="MASCC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Identifies low-risk febrile neutropenia patients for outpatient management",
    references=["Klastersky J, et al. J Clin Oncol 2000;18:3038-3051"],
    specialties=["Oncology", "Infectious Disease", "Emergency Medicine"],
    notes=["Score ≥21 = low risk (<5% serious complications)", "Maximum score 26"],
    multi_level_criteria=[
        MultiLevelCriterion(name="symptoms", display_name="Burden of Illness",
            levels=[
                ("no_or_mild", 5, "No or mild symptoms (5)"),
                ("moderate", 3, "Moderate symptoms (3)"),
                ("severe", 0, "Severe symptoms (0)"),
            ]),
        MultiLevelCriterion(name="hypotension", display_name="Hypotension (SBP <90)",
            levels=[("no", 5, "No hypotension (5)"), ("yes", 0, "Hypotension present (0)")]),
        MultiLevelCriterion(name="copd", display_name="COPD",
            levels=[("no", 4, "No COPD (4)"), ("yes", 0, "Active COPD (0)")]),
        MultiLevelCriterion(name="solid_tumor", display_name="Tumor Type",
            levels=[("solid_or_no_fungal", 4, "Solid tumor or no prior fungal infection (4)"), ("heme_with_fungal", 0, "Hematologic with prior fungal (0)")]),
        MultiLevelCriterion(name="dehydration", display_name="Dehydration",
            levels=[("no", 3, "No dehydration (3)"), ("yes", 0, "Dehydration present (0)")]),
        MultiLevelCriterion(name="outpatient", display_name="Outpatient Status",
            levels=[("outpatient", 3, "Outpatient at fever onset (3)"), ("inpatient", 0, "Inpatient (0)")]),
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[("lt_60", 2, "Age <60 years (2)"), ("gte_60", 0, "Age ≥60 years (0)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=21, risk_level=RiskLevel.HIGH,
            interpretation="High risk - serious complication rate >5%", recommendations=["Inpatient admission", "IV antibiotics", "Close monitoring"]),
        ThresholdInterpretation(min_score=21, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Low risk - serious complication rate <5%", recommendations=["Outpatient management may be appropriate", "Oral antibiotics if criteria met"]),
    ],
)

# Khorana Score (VTE Risk in Cancer)
KHORANA_DEFINITION = CalculatorDefinition(
    id="khorana",
    name="Khorana Score for VTE Risk in Cancer",
    short_name="Khorana",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts VTE risk in ambulatory cancer patients starting chemotherapy",
    references=["Khorana AA, et al. Blood 2008;111:4902-4907"],
    specialties=["Oncology", "Hematology", "Internal Medicine"],
    multi_level_criteria=[
        MultiLevelCriterion(name="cancer_site", display_name="Site of Cancer",
            levels=[
                ("very_high_risk", 2, "Very high risk: stomach, pancreas (2)"),
                ("high_risk", 1, "High risk: lung, lymphoma, GYN, bladder, testicular (1)"),
                ("other", 0, "Other (0)"),
            ]),
    ],
    criteria=[
        ScoringCriterion("platelet_gte_350", "Platelet count ≥350,000/μL", 1, ""),
        ScoringCriterion("hemoglobin_lt_10", "Hemoglobin <10 g/dL or using ESAs", 1, ""),
        ScoringCriterion("leukocyte_gt_11", "Leukocyte count >11,000/μL", 1, ""),
        ScoringCriterion("bmi_gte_35", "BMI ≥35 kg/m²", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk - VTE rate ~0.8%", recommendations=["Routine VTE prophylaxis not recommended", "Educate on VTE symptoms"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Intermediate risk - VTE rate ~1.8%", recommendations=["Consider prophylaxis in select patients"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk - VTE rate ~4%", recommendations=["Consider primary prophylaxis", "LMWH or DOAC if no contraindications"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk - VTE rate ~7%", recommendations=["Strongly consider prophylaxis", "LMWH or DOAC recommended"]),
    ],
)

# Gleason Score (Prostate Cancer)
GLEASON_DEFINITION = CalculatorDefinition(
    id="gleason",
    name="Gleason Score",
    short_name="Gleason",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="grade",
    description="Histologic grading for prostate cancer prognosis",
    references=["Epstein JI, et al. Am J Surg Pathol 2005;29:1228-1242"],
    specialties=["Oncology", "Urology", "Pathology"],
    notes=["Sum of primary (most prevalent) + secondary pattern; Grade Groups now preferred"],
    multi_level_criteria=[
        MultiLevelCriterion(name="grade_group", display_name="Grade Group",
            levels=[
                ("group_1", 1, "Grade Group 1: Gleason ≤6"),
                ("group_2", 2, "Grade Group 2: Gleason 3+4=7"),
                ("group_3", 3, "Grade Group 3: Gleason 4+3=7"),
                ("group_4", 4, "Grade Group 4: Gleason 8"),
                ("group_5", 5, "Grade Group 5: Gleason 9-10"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Low grade - favorable prognosis", recommendations=["Active surveillance may be appropriate", "Consider risk stratification"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Intermediate favorable", recommendations=["Active surveillance or definitive treatment"]),
        ThresholdInterpretation(min_score=3, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate unfavorable", recommendations=["Definitive treatment recommended"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High grade - aggressive disease", recommendations=["Aggressive multimodal therapy", "Consider clinical trials"]),
    ],
)

# ============================================================================
# SPECIALTY CALCULATORS - OBSTETRICS
# ============================================================================

# Biophysical Profile (BPP)
BPP_DEFINITION = CalculatorDefinition(
    id="bpp",
    name="Biophysical Profile",
    short_name="BPP",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.OBSTETRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Fetal well-being assessment via ultrasound and NST",
    references=["Manning FA, et al. Am J Obstet Gynecol 1980;136:787-795"],
    specialties=["Obstetrics", "Maternal-Fetal Medicine"],
    notes=["Each parameter scores 0 or 2; total 0-10", "Includes: NST, fetal breathing, movement, tone, AFI"],
    multi_level_criteria=[
        MultiLevelCriterion(name="nst", display_name="Non-Stress Test",
            levels=[("reactive", 2, "Reactive NST (2)"), ("nonreactive", 0, "Non-reactive NST (0)")]),
        MultiLevelCriterion(name="breathing", display_name="Fetal Breathing",
            levels=[("present", 2, "≥1 episode of ≥30 sec in 30 min (2)"), ("absent", 0, "Absent or <30 sec (0)")]),
        MultiLevelCriterion(name="movement", display_name="Fetal Movement",
            levels=[("present", 2, "≥3 discrete body/limb movements in 30 min (2)"), ("absent", 0, "<3 movements (0)")]),
        MultiLevelCriterion(name="tone", display_name="Fetal Tone",
            levels=[("present", 2, "≥1 episode of extension/flexion (2)"), ("absent", 0, "Absent tone (0)")]),
        MultiLevelCriterion(name="afi", display_name="Amniotic Fluid",
            levels=[("normal", 2, "AFI >5 cm or single pocket >2 cm (2)"), ("low", 0, "AFI ≤5 or no pocket ≥2 cm (0)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Normal - fetal asphyxia rare", recommendations=["Routine antepartum care", "Repeat per clinical indication"]),
        ThresholdInterpretation(min_score=6, max_score=8, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Equivocal", recommendations=["If oligohydramnios, consider delivery if ≥37 weeks", "Repeat in 6-24 hours if normal AFI"]),
        ThresholdInterpretation(min_score=4, max_score=6, risk_level=RiskLevel.MODERATE,
            interpretation="Abnormal - possible fetal compromise", recommendations=["If ≥32 weeks, consider delivery", "If <32 weeks, repeat in 24 hours"]),
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.HIGH,
            interpretation="Abnormal - high risk of fetal asphyxia", recommendations=["Delivery if ≥32 weeks", "Urgent MFM consultation"]),
    ],
)

# Edinburgh Postnatal Depression Scale (EPDS)
EPDS_DEFINITION = CalculatorDefinition(
    id="epds",
    name="Edinburgh Postnatal Depression Scale",
    short_name="EPDS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.OBSTETRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Screens for perinatal depression",
    references=["Cox JL, et al. Br J Psychiatry 1987;150:782-786"],
    specialties=["Obstetrics", "Psychiatry", "Primary Care"],
    notes=["Score ≥10 suggests possible depression", "Question 10 screens for self-harm thoughts"],
    multi_level_criteria=[
        MultiLevelCriterion(name="q1_laugh", display_name="1. Able to laugh",
            levels=[("0", 0, "As much as always (0)"), ("1", 1, "Not quite so much (1)"), ("2", 2, "Definitely not so much (2)"), ("3", 3, "Not at all (3)")]),
        MultiLevelCriterion(name="q2_enjoyment", display_name="2. Looked forward with enjoyment",
            levels=[("0", 0, "As much as ever (0)"), ("1", 1, "Less than used to (1)"), ("2", 2, "Definitely less (2)"), ("3", 3, "Hardly at all (3)")]),
        MultiLevelCriterion(name="q3_blame", display_name="3. Blamed self unnecessarily",
            levels=[("0", 0, "No, never (0)"), ("1", 1, "Not very often (1)"), ("2", 2, "Yes, some of the time (2)"), ("3", 3, "Yes, most of the time (3)")]),
        MultiLevelCriterion(name="q4_anxious", display_name="4. Anxious or worried for no good reason",
            levels=[("0", 0, "No, not at all (0)"), ("1", 1, "Hardly ever (1)"), ("2", 2, "Yes, sometimes (2)"), ("3", 3, "Yes, very often (3)")]),
        MultiLevelCriterion(name="q5_scared", display_name="5. Scared or panicky for no good reason",
            levels=[("0", 0, "No, not at all (0)"), ("1", 1, "No, not much (1)"), ("2", 2, "Yes, sometimes (2)"), ("3", 3, "Yes, quite a lot (3)")]),
        MultiLevelCriterion(name="q6_overwhelmed", display_name="6. Things getting on top of me",
            levels=[("0", 0, "No, I have been coping (0)"), ("1", 1, "No, most of the time coping (1)"), ("2", 2, "Yes, sometimes not coping (2)"), ("3", 3, "Yes, most of the time not coping (3)")]),
        MultiLevelCriterion(name="q7_unhappy_sleep", display_name="7. So unhappy, difficulty sleeping",
            levels=[("0", 0, "No, not at all (0)"), ("1", 1, "Not very often (1)"), ("2", 2, "Yes, sometimes (2)"), ("3", 3, "Yes, most of the time (3)")]),
        MultiLevelCriterion(name="q8_sad", display_name="8. Felt sad or miserable",
            levels=[("0", 0, "No, not at all (0)"), ("1", 1, "Not very often (1)"), ("2", 2, "Yes, quite often (2)"), ("3", 3, "Yes, most of the time (3)")]),
        MultiLevelCriterion(name="q9_crying", display_name="9. So unhappy, have been crying",
            levels=[("0", 0, "No, never (0)"), ("1", 1, "Only occasionally (1)"), ("2", 2, "Yes, quite often (2)"), ("3", 3, "Yes, most of the time (3)")]),
        MultiLevelCriterion(name="q10_self_harm", display_name="10. Thought of harming self",
            levels=[("0", 0, "Never (0)"), ("1", 1, "Hardly ever (1)"), ("2", 2, "Sometimes (2)"), ("3", 3, "Yes, quite often (3)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=9, risk_level=RiskLevel.LOW,
            interpretation="Depression not likely", recommendations=["Routine follow-up", "Continue screening at visits"]),
        ThresholdInterpretation(min_score=9, max_score=13, risk_level=RiskLevel.MODERATE,
            interpretation="Possible depression", recommendations=["Further clinical assessment", "Consider mental health referral"]),
        ThresholdInterpretation(min_score=13, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Probable depression", recommendations=["Mental health referral", "Safety assessment", "Consider treatment"]),
    ],
)

# VBAC Success Prediction (simplified Grobman model)
VBAC_DEFINITION = CalculatorDefinition(
    id="vbac",
    name="VBAC Success Calculator (Simplified)",
    short_name="VBAC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.OBSTETRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts successful vaginal birth after cesarean",
    references=["Grobman WA, et al. Am J Obstet Gynecol 2007;196:364.e1-6"],
    specialties=["Obstetrics", "Maternal-Fetal Medicine"],
    notes=["Higher score = higher probability of success"],
    criteria=[
        ScoringCriterion("prior_vaginal", "Prior vaginal delivery", 2, "Any prior vaginal delivery"),
        ScoringCriterion("prior_vbac", "Prior VBAC", 2, "Prior successful VBAC"),
        ScoringCriterion("age_lt_35", "Age <35 years", 1, ""),
        ScoringCriterion("bmi_lt_30", "BMI <30 kg/m²", 1, ""),
        ScoringCriterion("favorable_cervix", "Favorable cervix on admission", 1, "Dilation ≥2 cm or effacement ≥50%"),
        ScoringCriterion("spontaneous_labor", "Spontaneous labor", 1, "Not induced"),
        ScoringCriterion("nonrecurring_indication", "Prior cesarean for non-recurring indication", 1, "e.g., breech, fetal distress"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="Lower VBAC success probability (~50%)", recommendations=["Discuss risks/benefits carefully", "Consider repeat cesarean"]),
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate VBAC success probability (~70%)", recommendations=["TOLAC reasonable option", "Counsel on risks"]),
        ThresholdInterpretation(min_score=5, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Higher VBAC success probability (>80%)", recommendations=["TOLAC encouraged if desired", "Standard monitoring"]),
    ],
)

# Preeclampsia Risk Assessment (simplified ACOG/NICE)
PREECLAMPSIA_RISK_DEFINITION = CalculatorDefinition(
    id="preeclampsia_risk",
    name="Preeclampsia Risk Assessment",
    short_name="Preeclampsia Risk",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.OBSTETRIC,
    output_type=OutputType.INTEGER,
    score_unit="risk factors",
    description="Identifies patients at high risk for preeclampsia",
    references=["ACOG Practice Bulletin 222, 2020", "NICE Guideline CG107"],
    specialties=["Obstetrics", "Maternal-Fetal Medicine"],
    notes=["≥1 high-risk OR ≥2 moderate-risk factors = aspirin prophylaxis recommended"],
    criteria=[
        # High-risk factors (each alone qualifies)
        ScoringCriterion("prior_preeclampsia", "Prior preeclampsia", 2, "High-risk factor"),
        ScoringCriterion("multifetal_gestation", "Multifetal gestation", 2, "High-risk factor"),
        ScoringCriterion("chronic_hypertension", "Chronic hypertension", 2, "High-risk factor"),
        ScoringCriterion("type_1_or_2_dm", "Type 1 or Type 2 diabetes", 2, "High-risk factor"),
        ScoringCriterion("renal_disease", "Renal disease", 2, "High-risk factor"),
        ScoringCriterion("autoimmune_disease", "Autoimmune disease (SLE, APS)", 2, "High-risk factor"),
        # Moderate-risk factors (need ≥2)
        ScoringCriterion("nulliparous", "Nulliparous", 1, "Moderate-risk factor"),
        ScoringCriterion("obesity", "Obesity (BMI >30)", 1, "Moderate-risk factor"),
        ScoringCriterion("family_hx_preeclampsia", "Family history of preeclampsia", 1, "Moderate-risk factor"),
        ScoringCriterion("age_35_plus", "Age ≥35 years", 1, "Moderate-risk factor"),
        ScoringCriterion("low_ses", "Low socioeconomic status", 1, "Moderate-risk factor"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Low risk for preeclampsia", recommendations=["Routine prenatal care", "Monitor BP at visits"]),
        ThresholdInterpretation(min_score=2, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk for preeclampsia", recommendations=["Low-dose aspirin 81mg daily starting 12-16 weeks", "Close BP monitoring", "Consider early delivery planning"]),
    ],
)

# ============================================================================
# SPECIALTY CALCULATORS - PEDIATRICS (Additional)
# ============================================================================

# Westley Croup Score
WESTLEY_CROUP_DEFINITION = CalculatorDefinition(
    id="westley_croup",
    name="Westley Croup Score",
    short_name="Westley",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Assesses croup severity in children",
    references=["Westley CR, et al. Am J Dis Child 1978;132:484-487"],
    specialties=["Pediatrics", "Pediatric Emergency Medicine"],
    multi_level_criteria=[
        MultiLevelCriterion(name="stridor", display_name="Stridor",
            levels=[("none", 0, "None (0)"), ("at_rest_mild", 1, "When agitated (1)"), ("at_rest_severe", 2, "At rest (2)")]),
        MultiLevelCriterion(name="retractions", display_name="Retractions",
            levels=[("none", 0, "None (0)"), ("mild", 1, "Mild (1)"), ("moderate", 2, "Moderate (2)"), ("severe", 3, "Severe (3)")]),
        MultiLevelCriterion(name="air_entry", display_name="Air Entry",
            levels=[("normal", 0, "Normal (0)"), ("decreased", 1, "Decreased (1)"), ("markedly_decreased", 2, "Markedly decreased (2)")]),
        MultiLevelCriterion(name="cyanosis", display_name="Cyanosis",
            levels=[("none", 0, "None (0)"), ("with_agitation", 4, "With agitation (4)"), ("at_rest", 5, "At rest (5)")]),
        MultiLevelCriterion(name="consciousness", display_name="Level of Consciousness",
            levels=[("normal", 0, "Normal (0)"), ("altered", 5, "Altered/disoriented (5)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=2, risk_level=RiskLevel.LOW,
            interpretation="Mild croup", recommendations=["Supportive care", "Dexamethasone single dose", "Discharge with precautions"]),
        ThresholdInterpretation(min_score=2, max_score=8, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate croup", recommendations=["Dexamethasone", "Consider nebulized epinephrine", "Observation 2-4 hours"]),
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Severe croup", recommendations=["Nebulized epinephrine", "Dexamethasone", "ICU consideration", "Prepare for airway intervention"]),
    ],
)

# Pediatric Appendicitis Score (PAS)
PEDIATRIC_APPENDICITIS_DEFINITION = CalculatorDefinition(
    id="pediatric_appendicitis",
    name="Pediatric Appendicitis Score",
    short_name="PAS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts appendicitis in children 4-18 years",
    references=["Samuel M. J Pediatr Surg 2002;37:877-881"],
    specialties=["Pediatric Surgery", "Pediatric Emergency Medicine"],
    criteria=[
        ScoringCriterion("anorexia", "Anorexia", 1, ""),
        ScoringCriterion("nausea_vomiting", "Nausea or vomiting", 1, ""),
        ScoringCriterion("migration_pain", "Migration of pain to RLQ", 1, ""),
        ScoringCriterion("fever", "Fever ≥38°C (100.4°F)", 1, ""),
        ScoringCriterion("cough_percussion_tenderness", "Cough/percussion/hopping tenderness", 2, ""),
        ScoringCriterion("rlq_tenderness", "RLQ tenderness", 2, ""),
        ScoringCriterion("leukocytosis", "Leukocytosis >10,000/μL", 1, ""),
        ScoringCriterion("neutrophilia", "Neutrophilia (>75%)", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.LOW,
            interpretation="Low probability of appendicitis", recommendations=["Observation", "Consider discharge with return precautions"]),
        ThresholdInterpretation(min_score=4, max_score=7, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate probability", recommendations=["Imaging recommended (US preferred)", "Surgical consultation if imaging positive"]),
        ThresholdInterpretation(min_score=7, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High probability of appendicitis", recommendations=["Surgical consultation", "May proceed to OR without imaging in classic presentation"]),
    ],
)

# Rochester Criteria (Febrile Infant)
ROCHESTER_CRITERIA_DEFINITION = CalculatorDefinition(
    id="rochester_criteria",
    name="Rochester Criteria for Febrile Infants",
    short_name="Rochester",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies low-risk febrile infants (≤60 days) for SBI",
    references=["Dagan R, et al. J Pediatr 1985;107:855-860"],
    specialties=["Pediatrics", "Pediatric Emergency Medicine"],
    notes=["Must meet ALL criteria to be low risk", "Applies to infants ≤60 days with fever ≥38°C"],
    criteria=[
        ScoringCriterion("appears_well", "Infant appears well", 0, "Low risk criterion met"),
        ScoringCriterion("previously_healthy", "Previously healthy (term, no prior abx, no jaundice rx)", 0, "Low risk criterion met"),
        ScoringCriterion("no_focal_infection", "No evidence of soft tissue/bone/joint/ear infection", 0, "Low risk criterion met"),
        ScoringCriterion("wbc_5_15k", "WBC 5,000-15,000/mm³", 0, "Low risk criterion met"),
        ScoringCriterion("bands_lt_1500", "Band count <1,500/mm³", 0, "Low risk criterion met"),
        ScoringCriterion("ua_normal", "Urinalysis ≤10 WBC/hpf", 0, "Low risk criterion met"),
        ScoringCriterion("stool_wbc_lt_5", "If diarrhea: stool WBC <5/hpf", 0, "Low risk criterion met"),
        # If any criterion NOT met, add 1 point
        ScoringCriterion("high_risk_criteria_present", "Any high-risk criterion present", 1, "If checked, not low risk"),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk for SBI (~1%)", recommendations=["Consider outpatient management with close follow-up", "Blood/urine cultures", "LP may be deferred"]),
        ThresholdInterpretation(min_score=1, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Not low risk - higher SBI risk", recommendations=["Full sepsis workup", "Empiric antibiotics", "Hospital admission"]),
    ],
)

# Pediatric Respiratory Assessment Measure (PRAM)
PRAM_DEFINITION = CalculatorDefinition(
    id="pram",
    name="Pediatric Respiratory Assessment Measure",
    short_name="PRAM",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Assesses asthma/bronchospasm severity in children",
    references=["Chalut DS, et al. Pediatr Pulmonol 2000;29:269-275"],
    specialties=["Pediatric Emergency Medicine", "Pediatrics"],
    multi_level_criteria=[
        MultiLevelCriterion(name="scalene_contraction", display_name="Scalene Muscle Contraction",
            levels=[("absent", 0, "Absent (0)"), ("present", 2, "Present (2)")]),
        MultiLevelCriterion(name="suprasternal_retractions", display_name="Suprasternal Retractions",
            levels=[("absent", 0, "Absent (0)"), ("present", 2, "Present (2)")]),
        MultiLevelCriterion(name="wheezing", display_name="Wheezing",
            levels=[("absent", 0, "Absent (0)"), ("expiratory_only", 1, "Expiratory only (1)"),
                    ("inspiratory_expiratory", 2, "Inspiratory and expiratory (2)"), ("audible_no_stethoscope", 3, "Audible without stethoscope (3)")]),
        MultiLevelCriterion(name="air_entry", display_name="Air Entry",
            levels=[("normal", 0, "Normal (0)"), ("decreased_bases", 1, "Decreased at bases (1)"),
                    ("widespread_decrease", 2, "Widespread decrease (2)"), ("absent_silent", 3, "Absent/minimal (3)")]),
        MultiLevelCriterion(name="spo2", display_name="O2 Saturation",
            levels=[("gte_95", 0, "≥95% (0)"), ("92_94", 1, "92-94% (1)"), ("lt_92", 2, "<92% (2)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.LOW,
            interpretation="Mild exacerbation", recommendations=["Bronchodilator", "May discharge if improves"]),
        ThresholdInterpretation(min_score=4, max_score=8, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate exacerbation", recommendations=["Serial bronchodilators", "Systemic corticosteroids", "Observation"]),
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Severe exacerbation", recommendations=["Continuous nebulization", "Systemic steroids", "ICU consideration", "IV magnesium"]),
    ],
)

# BCLC Staging (Hepatocellular Carcinoma)
BCLC_DEFINITION = CalculatorDefinition(
    id="bclc",
    name="Barcelona Clinic Liver Cancer Staging",
    short_name="BCLC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="stage",
    description="Staging and treatment allocation for HCC",
    references=["Llovet JM, et al. Lancet 1999;354:1896-1899"],
    specialties=["Oncology", "Hepatology", "Gastroenterology"],
    multi_level_criteria=[
        MultiLevelCriterion(name="stage", display_name="BCLC Stage",
            levels=[
                ("stage_0", 0, "Stage 0: Single <2cm, preserved liver function, PS 0"),
                ("stage_a", 1, "Stage A: Single or ≤3 nodules <3cm, preserved function, PS 0"),
                ("stage_b", 2, "Stage B: Multinodular, preserved function, PS 0"),
                ("stage_c", 3, "Stage C: Portal invasion/extrahepatic spread or PS 1-2"),
                ("stage_d", 4, "Stage D: End-stage, Child-Pugh C or PS 3-4"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Very early/Early stage - curative treatment", recommendations=["Resection, ablation, or transplant", "5-year survival 50-70%"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Early stage", recommendations=["Ablation if not surgical candidate", "Transplant evaluation"]),
        ThresholdInterpretation(min_score=2, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate stage", recommendations=["TACE (transarterial chemoembolization)", "Median survival 16 months"]),
        ThresholdInterpretation(min_score=3, max_score=4, risk_level=RiskLevel.HIGH,
            interpretation="Advanced stage", recommendations=["Systemic therapy (sorafenib, lenvatinib)", "Median survival 6-8 months"]),
        ThresholdInterpretation(min_score=4, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Terminal stage", recommendations=["Best supportive care", "Median survival <3 months"]),
    ],
)

# Palliative Prognostic Index (PPI)
PPI_DEFINITION = CalculatorDefinition(
    id="ppi",
    name="Palliative Prognostic Index",
    short_name="PPI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.DECIMAL,
    score_unit="points",
    description="Predicts survival in terminally ill cancer patients",
    references=["Morita T, et al. J Pain Symptom Manage 1999;18:2-8"],
    specialties=["Palliative Care", "Oncology", "Hospice"],
    multi_level_criteria=[
        MultiLevelCriterion(name="pps", display_name="Palliative Performance Scale",
            levels=[("10_20", 4, "PPS 10-20 (4)"), ("30_50", 2.5, "PPS 30-50 (2.5)"), ("gte_60", 0, "PPS ≥60 (0)")]),
        MultiLevelCriterion(name="oral_intake", display_name="Oral Intake",
            levels=[("severely_reduced", 2.5, "Severely reduced (2.5)"), ("moderately_reduced", 1, "Moderately reduced (1)"), ("normal", 0, "Normal (0)")]),
        MultiLevelCriterion(name="edema", display_name="Edema",
            levels=[("present", 1, "Present (1)"), ("absent", 0, "Absent (0)")]),
        MultiLevelCriterion(name="dyspnea_at_rest", display_name="Dyspnea at Rest",
            levels=[("present", 3.5, "Present (3.5)"), ("absent", 0, "Absent (0)")]),
        MultiLevelCriterion(name="delirium", display_name="Delirium",
            levels=[("present", 4, "Present (4)"), ("absent", 0, "Absent (0)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Survival >6 weeks likely", recommendations=["Continue disease-directed therapy if appropriate"]),
        ThresholdInterpretation(min_score=4, max_score=6, risk_level=RiskLevel.HIGH,
            interpretation="Survival 3-6 weeks", recommendations=["Hospice referral", "Advance care planning"]),
        ThresholdInterpretation(min_score=6, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Survival <3 weeks likely", recommendations=["Comfort-focused care", "Family support"]),
    ],
)

# New Orleans Criteria (Minor Head Injury)
NEW_ORLEANS_CRITERIA_DEFINITION = CalculatorDefinition(
    id="new_orleans_criteria",
    name="New Orleans Criteria",
    short_name="NOC",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="criteria",
    description="Identifies minor head injury patients needing CT (GCS 15)",
    references=["Haydel MJ, et al. N Engl J Med 2000;343:100-105"],
    specialties=["Emergency Medicine", "Neurology"],
    notes=["Applies to patients with GCS 15 and LOC after blunt head trauma"],
    criteria=[
        ScoringCriterion("headache", "Headache", 1, ""),
        ScoringCriterion("vomiting", "Vomiting", 1, "Any vomiting since injury"),
        ScoringCriterion("age_over_60", "Age >60 years", 1, ""),
        ScoringCriterion("drug_alcohol", "Drug or alcohol intoxication", 1, ""),
        ScoringCriterion("persistent_anterograde_amnesia", "Persistent anterograde amnesia", 1, "Deficits in short-term memory"),
        ScoringCriterion("visible_trauma_above_clavicle", "Visible trauma above clavicles", 1, ""),
        ScoringCriterion("seizure", "Seizure", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="CT not indicated", recommendations=["Observation", "Discharge with head injury precautions"]),
        ThresholdInterpretation(min_score=1, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="CT head recommended", recommendations=["Obtain CT head without contrast", "Neurosurgery if positive"]),
    ],
)

# DRAGON Score (Stroke Outcome after tPA)
DRAGON_SCORE_DEFINITION = CalculatorDefinition(
    id="dragon_score",
    name="DRAGON Score",
    short_name="DRAGON",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts 3-month outcome after IV tPA for ischemic stroke",
    references=["Strbian D, et al. Stroke 2012;43:2315-2317"],
    specialties=["Neurology", "Emergency Medicine"],
    notes=["D=Dense MCA sign, R=mRS, A=Age, G=Glucose, O=Onset-to-treatment, N=NIHSS"],
    criteria=[
        ScoringCriterion("dense_mca_or_early_infarct", "Hyperdense MCA sign or early CT changes", 2, "(Dense) MCA sign/early infarct"),
        ScoringCriterion("prestroke_mrs_gt_1", "Pre-stroke mRS >1", 1, "(R)ankin - baseline disability"),
        ScoringCriterion("glucose_gt_144", "Blood glucose >144 mg/dL (8 mmol/L)", 1, "(G)lucose"),
    ],
    multi_level_criteria=[
        MultiLevelCriterion(name="age", display_name="(A)ge",
            levels=[("lt_65", 0, "< 65 years (0)"), ("65_79", 1, "65-79 years (1)"), ("gte_80", 2, "≥ 80 years (2)")]),
        MultiLevelCriterion(name="onset_to_treatment", display_name="(O)nset-to-treatment time",
            levels=[("lt_90", 0, "< 90 min (0)"), ("90_180", 1, "90-180 min (1)"), ("gt_180", 2, "> 180 min (2)")]),
        MultiLevelCriterion(name="nihss", display_name="(N)IHSS on admission",
            levels=[("0_4", 0, "0-4 (0)"), ("5_9", 1, "5-9 (1)"), ("10_15", 2, "10-15 (2)"), ("gt_15", 3, ">15 (3)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="Good outcome likely (mRS 0-2: ~90%)", recommendations=["tPA appropriate", "Good prognosis"]),
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate outcome (~50% mRS 0-2)", recommendations=["tPA still beneficial", "Moderate prognosis"]),
        ThresholdInterpretation(min_score=5, max_score=8, risk_level=RiskLevel.HIGH,
            interpretation="Poor outcome likely (~20% mRS 0-2)", recommendations=["Consider tPA with realistic expectations", "Goals discussion"]),
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very poor outcome (<5% mRS 0-2)", recommendations=["Discuss risks/benefits carefully", "May consider comfort care"]),
    ],
)

# Revised IPI (R-IPI) for NHL
R_IPI_DEFINITION = CalculatorDefinition(
    id="r_ipi",
    name="Revised International Prognostic Index",
    short_name="R-IPI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="factors",
    description="Prognosis for DLBCL in rituximab era",
    references=["Sehn LH, et al. Blood 2007;109:1857-1861"],
    specialties=["Oncology", "Hematology"],
    notes=["Uses same 5 factors as IPI but different risk stratification"],
    criteria=[
        ScoringCriterion("age_over_60", "Age >60 years", 1, ""),
        ScoringCriterion("stage_iii_iv", "Ann Arbor stage III-IV", 1, ""),
        ScoringCriterion("elevated_ldh", "Elevated LDH", 1, ""),
        ScoringCriterion("ecog_2_plus", "ECOG PS ≥2", 1, ""),
        ScoringCriterion("extranodal_gt_1", ">1 extranodal site", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Very good prognosis - 4-year OS 94%", recommendations=["Standard R-CHOP", "Excellent outcomes expected"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Good prognosis - 4-year OS 79%", recommendations=["Standard R-CHOP", "Good outcomes expected"]),
        ThresholdInterpretation(min_score=2, max_score=None, risk_level=RiskLevel.MODERATE,
            interpretation="Poor prognosis - 4-year OS 55%", recommendations=["Consider intensified therapy", "Clinical trials"]),
    ],
)

# Lansky Play Performance Scale (Pediatric Oncology)
LANSKY_DEFINITION = CalculatorDefinition(
    id="lansky",
    name="Lansky Play-Performance Scale",
    short_name="Lansky",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="%",
    description="Performance status for pediatric oncology (age <16)",
    references=["Lansky SB, et al. Cancer 1987;60:1651-1656"],
    specialties=["Pediatric Oncology", "Oncology"],
    multi_level_criteria=[
        MultiLevelCriterion(name="play", display_name="Play Performance",
            levels=[
                ("100", 100, "100: Fully active, normal"),
                ("90", 90, "90: Minor restrictions in strenuous activity"),
                ("80", 80, "80: Active but tires more quickly"),
                ("70", 70, "70: Greater restriction, less time in active play"),
                ("60", 60, "60: Up and around, minimal active play, keeps busy with quieter activities"),
                ("50", 50, "50: Gets dressed but lies around much of day, no active play"),
                ("40", 40, "40: Mostly in bed, participates in quiet activities"),
                ("30", 30, "30: Bedridden, needs assistance for quiet play"),
                ("20", 20, "20: Sleeping often, play limited to passive"),
                ("10", 10, "10: No play, does not get out of bed"),
                ("0", 0, "0: Unresponsive"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=70, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Good functional status", recommendations=["Eligible for most protocols"]),
        ThresholdInterpretation(min_score=50, max_score=70, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate impairment", recommendations=["May need modified treatment"]),
        ThresholdInterpretation(min_score=0, max_score=50, risk_level=RiskLevel.HIGH,
            interpretation="Significant impairment", recommendations=["Supportive care focus", "Modified therapy"]),
    ],
)

# Yale Observation Scale (Febrile Children)
YALE_OBSERVATION_DEFINITION = CalculatorDefinition(
    id="yale_observation",
    name="Yale Observation Scale",
    short_name="YOS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Identifies febrile infants/children at risk for serious illness",
    references=["McCarthy PL, et al. Pediatrics 1982;70:802-809"],
    specialties=["Pediatrics", "Pediatric Emergency Medicine"],
    notes=["Applies to children 3-36 months with fever"],
    multi_level_criteria=[
        MultiLevelCriterion(name="cry_quality", display_name="Quality of Cry",
            levels=[("strong_normal", 1, "Strong/normal or content (1)"), ("whimpering", 3, "Whimpering or sobbing (3)"), ("weak_moaning", 5, "Weak, moaning, or high-pitched (5)")]),
        MultiLevelCriterion(name="reaction_parent", display_name="Reaction to Parent Stimulation",
            levels=[("cries_briefly", 1, "Cries briefly then stops, or content (1)"), ("cries_on_off", 3, "Cries off and on (3)"), ("continuous_cry", 5, "Continual cry or hardly responds (5)")]),
        MultiLevelCriterion(name="state_variation", display_name="State Variation",
            levels=[("stays_awake", 1, "If awake, stays awake; if asleep, wakes quickly (1)"), ("eyes_briefly_close", 3, "Eyes close briefly when awake or hard to awaken (3)"), ("falls_asleep", 5, "Falls asleep or will not rouse (5)")]),
        MultiLevelCriterion(name="color", display_name="Color",
            levels=[("pink", 1, "Pink (1)"), ("pale_extremities", 3, "Pale extremities or acrocyanosis (3)"), ("pale_cyanotic", 5, "Pale, cyanotic, mottled, or ashen (5)")]),
        MultiLevelCriterion(name="hydration", display_name="Hydration",
            levels=[("skin_normal", 1, "Skin normal, eyes normal (1)"), ("skin_moist", 3, "Skin and eyes normal, mouth slightly dry (3)"), ("skin_doughy", 5, "Skin doughy or tented, dry mucous membranes, sunken eyes (5)")]),
        MultiLevelCriterion(name="response_social", display_name="Response to Social Overtures",
            levels=[("smiles_alert", 1, "Smiles or alert (1)"), ("brief_smile", 3, "Brief smile or alert briefly (3)"), ("no_smile", 5, "No smile, face anxious, dull, or no alerting (5)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=6, max_score=10, risk_level=RiskLevel.LOW,
            interpretation="Low risk of serious bacterial illness (SBI <3%)", recommendations=["May consider outpatient management", "Close follow-up"]),
        ThresholdInterpretation(min_score=10, max_score=16, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk", recommendations=["Laboratory evaluation", "Consider admission"]),
        ThresholdInterpretation(min_score=16, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk of SBI (~30%)", recommendations=["Full sepsis workup", "Empiric antibiotics", "Admission"]),
    ],
)

# Pediatric Trauma Score
PEDIATRIC_TRAUMA_SCORE_DEFINITION = CalculatorDefinition(
    id="pediatric_trauma_score",
    name="Pediatric Trauma Score",
    short_name="PTS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.PEDIATRIC,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Triage and outcome prediction in pediatric trauma",
    references=["Tepas JJ, et al. J Trauma 1987;27:370-374"],
    specialties=["Pediatric Surgery", "Pediatric Emergency Medicine", "Trauma"],
    notes=["Score ranges from -6 to +12", "Score ≤8 suggests need for trauma center"],
    multi_level_criteria=[
        MultiLevelCriterion(name="weight", display_name="Weight",
            levels=[("gt_20kg", 2, ">20 kg (+2)"), ("10_20kg", 1, "10-20 kg (+1)"), ("lt_10kg", -1, "<10 kg (-1)")]),
        MultiLevelCriterion(name="airway", display_name="Airway",
            levels=[("normal", 2, "Normal (+2)"), ("maintainable", 1, "Maintainable (+1)"), ("unmaintainable", -1, "Unmaintainable (-1)")]),
        MultiLevelCriterion(name="systolic_bp", display_name="Systolic BP",
            levels=[("gt_90", 2, ">90 mmHg (+2)"), ("50_90", 1, "50-90 mmHg (+1)"), ("lt_50", -1, "<50 mmHg (-1)")]),
        MultiLevelCriterion(name="cns", display_name="CNS Status",
            levels=[("awake", 2, "Awake (+2)"), ("obtunded", 1, "Obtunded/LOC (+1)"), ("coma", -1, "Coma/decerebrate (-1)")]),
        MultiLevelCriterion(name="skeletal", display_name="Skeletal Injury",
            levels=[("none", 2, "None (+2)"), ("closed_fracture", 1, "Closed fracture (+1)"), ("open_multiple", -1, "Open/multiple fractures (-1)")]),
        MultiLevelCriterion(name="wounds", display_name="Cutaneous Wounds",
            levels=[("none", 2, "None (+2)"), ("minor", 1, "Minor (+1)"), ("major_penetrating", -1, "Major/penetrating (-1)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=9, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="Minor trauma - mortality <1%", recommendations=["May be managed at local facility", "Routine trauma care"]),
        ThresholdInterpretation(min_score=6, max_score=9, risk_level=RiskLevel.MODERATE,
            interpretation="Potentially significant injury", recommendations=["Pediatric trauma center preferred", "Close monitoring"]),
        ThresholdInterpretation(min_score=-6, max_score=6, risk_level=RiskLevel.HIGH,
            interpretation="Severe trauma - high mortality risk", recommendations=["Transfer to pediatric trauma center", "Aggressive resuscitation"]),
    ],
)

# THRIVE Score (Thrombectomy Outcome)
THRIVE_DEFINITION = CalculatorDefinition(
    id="thrive",
    name="THRIVE Score",
    short_name="THRIVE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts outcome after endovascular thrombectomy for stroke",
    references=["Flint AC, et al. Stroke 2010;41:2004-2008"],
    specialties=["Neurology", "Interventional Neuroradiology"],
    multi_level_criteria=[
        MultiLevelCriterion(name="nihss", display_name="NIHSS Score",
            levels=[("lt_11", 0, "NIHSS <11 (0)"), ("11_20", 2, "NIHSS 11-20 (2)"), ("gt_20", 4, "NIHSS >20 (4)")]),
        MultiLevelCriterion(name="age", display_name="Age",
            levels=[("lt_60", 0, "Age <60 (0)"), ("60_79", 1, "Age 60-79 (1)"), ("gte_80", 2, "Age ≥80 (2)")]),
    ],
    criteria=[
        ScoringCriterion("hypertension", "Chronic hypertension", 1, ""),
        ScoringCriterion("diabetes", "Diabetes mellitus", 1, ""),
        ScoringCriterion("atrial_fibrillation", "Atrial fibrillation", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=3, risk_level=RiskLevel.LOW,
            interpretation="Good outcome likely after thrombectomy", recommendations=["Thrombectomy appropriate", "Good prognosis"]),
        ThresholdInterpretation(min_score=3, max_score=6, risk_level=RiskLevel.MODERATE,
            interpretation="Moderate outcome expected", recommendations=["Thrombectomy still beneficial", "Counsel on expectations"]),
        ThresholdInterpretation(min_score=6, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Poor outcome likely despite intervention", recommendations=["Discuss with family", "Thrombectomy may still be attempted"]),
    ],
)

# CLL-IPI (Chronic Lymphocytic Leukemia)
CLL_IPI_DEFINITION = CalculatorDefinition(
    id="cll_ipi",
    name="CLL International Prognostic Index",
    short_name="CLL-IPI",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Prognosis for chronic lymphocytic leukemia",
    references=["International CLL-IPI working group. Lancet Oncol 2016;17:779-790"],
    specialties=["Oncology", "Hematology"],
    criteria=[
        ScoringCriterion("del_17p_or_tp53_mut", "TP53 deletion/mutation (del17p or TP53)", 4, "High-risk genetic feature"),
        ScoringCriterion("ighv_unmutated", "IGHV unmutated", 2, ""),
        ScoringCriterion("b2m_gt_3_5", "Beta-2 microglobulin >3.5 mg/L", 2, ""),
        ScoringCriterion("stage_binet_bc_or_rai_i_iv", "Binet B/C or Rai I-IV", 1, "Clinical stage"),
        ScoringCriterion("age_over_65", "Age >65 years", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk - 5-year OS 93%", recommendations=["Watch and wait if asymptomatic", "Treatment at progression"]),
        ThresholdInterpretation(min_score=1, max_score=4, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk - 5-year OS 79%", recommendations=["Monitor closely", "Consider treatment when indicated"]),
        ThresholdInterpretation(min_score=4, max_score=7, risk_level=RiskLevel.HIGH,
            interpretation="High risk - 5-year OS 63%", recommendations=["Earlier treatment consideration", "Clinical trials"]),
        ThresholdInterpretation(min_score=7, max_score=None, risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very high risk - 5-year OS 23%", recommendations=["Aggressive treatment", "Novel agents", "Consider allogeneic SCT"]),
    ],
)

# Nottingham Grade (Breast Cancer)
NOTTINGHAM_GRADE_DEFINITION = CalculatorDefinition(
    id="nottingham_grade",
    name="Nottingham Histologic Grade (Breast Cancer)",
    short_name="Nottingham",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Histologic grading for breast cancer prognosis",
    references=["Elston CW, Ellis IO. Histopathology 1991;19:403-410"],
    specialties=["Oncology", "Pathology", "Breast Surgery"],
    multi_level_criteria=[
        MultiLevelCriterion(name="tubule_formation", display_name="Tubule Formation",
            levels=[("gt_75", 1, ">75% tubules (1)"), ("10_75", 2, "10-75% tubules (2)"), ("lt_10", 3, "<10% tubules (3)")]),
        MultiLevelCriterion(name="nuclear_pleomorphism", display_name="Nuclear Pleomorphism",
            levels=[("mild", 1, "Mild (1)"), ("moderate", 2, "Moderate (2)"), ("marked", 3, "Marked (3)")]),
        MultiLevelCriterion(name="mitotic_count", display_name="Mitotic Count (per 10 HPF)",
            levels=[("low", 1, "0-5 mitoses (1)"), ("intermediate", 2, "6-10 mitoses (2)"), ("high", 3, ">10 mitoses (3)")]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=3, max_score=5, risk_level=RiskLevel.LOW,
            interpretation="Grade 1 - Well differentiated, favorable", recommendations=["Favorable prognosis", "May be candidate for less aggressive therapy"]),
        ThresholdInterpretation(min_score=5, max_score=8, risk_level=RiskLevel.MODERATE,
            interpretation="Grade 2 - Moderately differentiated", recommendations=["Intermediate prognosis", "Standard treatment per guidelines"]),
        ThresholdInterpretation(min_score=8, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="Grade 3 - Poorly differentiated", recommendations=["More aggressive behavior", "Consider more aggressive treatment"]),
    ],
)

# CISNE Score (Febrile Neutropenia)
CISNE_DEFINITION = CalculatorDefinition(
    id="cisne",
    name="Clinical Index of Stable Febrile Neutropenia",
    short_name="CISNE",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.ONCOLOGY,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Identifies stable febrile neutropenia patients for outpatient management",
    references=["Carmona-Bayonas A, et al. J Clin Oncol 2015;33:465-471"],
    specialties=["Oncology", "Infectious Disease"],
    notes=["Applies to apparently stable solid tumor patients with febrile neutropenia"],
    criteria=[
        ScoringCriterion("ecog_gt_2", "ECOG PS ≥2", 2, ""),
        ScoringCriterion("stress_hyperglycemia", "Stress-induced hyperglycemia", 2, ""),
        ScoringCriterion("copd", "COPD", 1, ""),
        ScoringCriterion("chronic_cv_disease", "Chronic cardiovascular disease", 1, ""),
        ScoringCriterion("mucositis_grade_gte_2", "Mucositis grade ≥2 (NCI-CTCAE)", 1, ""),
        ScoringCriterion("monocytes_lt_200", "Monocytes <200/μL", 1, ""),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.LOW,
            interpretation="Low risk (class I) - complication rate ~1%", recommendations=["Outpatient management may be appropriate", "Oral antibiotics"]),
        ThresholdInterpretation(min_score=1, max_score=3, risk_level=RiskLevel.MODERATE,
            interpretation="Intermediate risk (class II) - complication rate ~6%", recommendations=["Consider short observation", "May be outpatient if stable"]),
        ThresholdInterpretation(min_score=3, max_score=None, risk_level=RiskLevel.HIGH,
            interpretation="High risk (class III) - complication rate ~36%", recommendations=["Inpatient admission", "IV antibiotics", "Close monitoring"]),
    ],
)

# Simplified Motor Score
SIMPLIFIED_MOTOR_SCORE_DEFINITION = CalculatorDefinition(
    id="simplified_motor_score",
    name="Simplified Motor Score",
    short_name="SMS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Simplified consciousness assessment (substitute for GCS)",
    references=["Gill M, et al. Ann Emerg Med 2005;45:77-81"],
    specialties=["Emergency Medicine", "Trauma", "Neurology"],
    notes=["Range 0-2; Strong correlation with GCS but simpler"],
    multi_level_criteria=[
        MultiLevelCriterion(name="motor", display_name="Motor Response",
            levels=[
                ("obeys_commands", 2, "Obeys commands (2)"),
                ("localizes_pain", 1, "Localizes pain (1)"),
                ("withdrawal_or_less", 0, "Withdrawal or less (0)"),
            ]),
    ],
    interpretations=[
        ThresholdInterpretation(min_score=2, max_score=None, risk_level=RiskLevel.LOW,
            interpretation="SMS 2 - Minor injury likely (equivalent to GCS 14-15)", recommendations=["Standard evaluation", "May not require intubation"]),
        ThresholdInterpretation(min_score=1, max_score=2, risk_level=RiskLevel.MODERATE,
            interpretation="SMS 1 - Moderate injury (equivalent to GCS 9-13)", recommendations=["Close monitoring", "CT indicated"]),
        ThresholdInterpretation(min_score=0, max_score=1, risk_level=RiskLevel.HIGH,
            interpretation="SMS 0 - Severe injury (equivalent to GCS 3-8)", recommendations=["Consider intubation", "Emergent CT", "Neurosurgery"]),
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
    "aa_gradient": AA_GRADIENT_DEFINITION,
    # Comorbidity
    "charlson": CHARLSON_DEFINITION,
    # Cardiac/Cardiovascular
    "timi_stemi": TIMI_STEMI_DEFINITION,
    "timi_nstemi": TIMI_NSTEMI_DEFINITION,
    "framingham_cvd": FRAMINGHAM_CVD_DEFINITION,
    "corrected_qt": CORRECTED_QT_DEFINITION,
    "map": MAP_DEFINITION,
    # Tier 1 - Cardiovascular
    "geneva_revised": GENEVA_REVISED_DEFINITION,
    "grace": GRACE_SCORE_DEFINITION,
    # Tier 2 - Cardiovascular VTE/Bleeding
    "padua": PADUA_DEFINITION,
    "improve_vte": IMPROVE_VTE_DEFINITION,
    "crusade": CRUSADE_DEFINITION,
    "atria_bleeding": ATRIA_BLEEDING_DEFINITION,
    "hemorr2hages": HEMORR2HAGES_DEFINITION,
    "duke_treadmill": DUKE_TREADMILL_DEFINITION,
    "maggic": MAGGIC_DEFINITION,
    # Tier 3 - VTE Recurrence
    "dash": DASH_DEFINITION,
    "herdoo2": HERDOO2_DEFINITION,
    "vienna_vte": VIENNA_VTE_DEFINITION,
    # Tier 3 - DAPT/Bleeding
    "precise_dapt": PRECISE_DAPT_DEFINITION,
    "dapt_score": DAPT_SCORE_DEFINITION,
    "orbit_bleeding": ORBIT_BLEEDING_DEFINITION,
    # Tier 4 - Syncope
    "canadian_syncope": CANADIAN_SYNCOPE_DEFINITION,
    "sf_syncope": SF_SYNCOPE_DEFINITION,
    "oesil": OESIL_DEFINITION,
    "egsys": EGSYS_DEFINITION,
    # Tier 4 - STEMI with LBBB
    "sgarbossa": SGARBOSSA_DEFINITION,
    "modified_sgarbossa": MODIFIED_SGARBOSSA_DEFINITION,
    # Tier 4 - PE
    "years_algorithm": YEARS_ALGORITHM_DEFINITION,
    # Tier 5 - Aortic/Chest Pain
    "add_rs": ADD_RS_DEFINITION,
    "edacs": EDACS_DEFINITION,
    "vancouver_cpr": VANCOUVER_CPR_DEFINITION,
    "marburg": MARBURG_DEFINITION,
    "interchest": INTERCHEST_DEFINITION,
    # Tier 5 - PE Severity
    "pesi": PESI_DEFINITION,
    "spesi": SPESI_DEFINITION,
    "bova": BOVA_DEFINITION,
    # Hepatic
    "meld": MELD_DEFINITION,
    "meld_na": MELD_NA_DEFINITION,
    "child_pugh": CHILD_PUGH_DEFINITION,
    "fib4": FIB4_DEFINITION,
    # Renal
    "egfr_ckdepi": EGFR_CKDEPI_DEFINITION,
    "creatinine_clearance": CREATININE_CLEARANCE_DEFINITION,
    # Metabolic
    "bmi": BMI_DEFINITION,
    "corrected_calcium": CORRECTED_CALCIUM_DEFINITION,
    "anion_gap": ANION_GAP_DEFINITION,
    "serum_osmolality": SERUM_OSMOLALITY_DEFINITION,
    # Critical Care
    "sofa": SOFA_DEFINITION,
    "news2": NEWS2_DEFINITION,
    # Emergency/Surgical
    "ottawa_ankle": OTTAWA_ANKLE_DEFINITION,
    "ciwa_ar": CIWA_AR_DEFINITION,
    "caprini": CAPRINI_DEFINITION,
    "bisap": BISAP_DEFINITION,
    # Neurological
    "abcd2": ABCD2_DEFINITION,
    "nihss": NIHSS_DEFINITION,
    "hunt_hess": HUNT_HESS_DEFINITION,
    "fisher_grade": FISHER_GRADE_DEFINITION,
    "modified_fisher": MODIFIED_FISHER_DEFINITION,
    "wfns_grade": WFNS_GRADE_DEFINITION,
    "ich_score": ICH_SCORE_DEFINITION,
    "func_score": FUNC_SCORE_DEFINITION,
    "canadian_ct_head": CANADIAN_CT_HEAD_DEFINITION,
    "pecarn_head": PECARN_HEAD_DEFINITION,
    "ottawa_sah": OTTAWA_SAH_DEFINITION,
    "four_score": FOUR_SCORE_DEFINITION,
    "mrs": MRS_DEFINITION,
    # Oncology
    "ecog": ECOG_DEFINITION,
    "karnofsky": KARNOFSKY_DEFINITION,
    "pps": PPS_DEFINITION,
    "ipi": IPI_DEFINITION,
    "flipi": FLIPI_DEFINITION,
    "iss_myeloma": ISS_MYELOMA_DEFINITION,
    "mascc": MASCC_DEFINITION,
    "khorana": KHORANA_DEFINITION,
    "gleason": GLEASON_DEFINITION,
    # Obstetrics
    "bpp": BPP_DEFINITION,
    "epds": EPDS_DEFINITION,
    "vbac": VBAC_DEFINITION,
    "preeclampsia_risk": PREECLAMPSIA_RISK_DEFINITION,
    # Pediatrics
    "westley_croup": WESTLEY_CROUP_DEFINITION,
    "pediatric_appendicitis": PEDIATRIC_APPENDICITIS_DEFINITION,
    "rochester_criteria": ROCHESTER_CRITERIA_DEFINITION,
    "pram": PRAM_DEFINITION,
    "bclc": BCLC_DEFINITION,
    "ppi": PPI_DEFINITION,
    "new_orleans_criteria": NEW_ORLEANS_CRITERIA_DEFINITION,
    "dragon_score": DRAGON_SCORE_DEFINITION,
    "r_ipi": R_IPI_DEFINITION,
    "lansky": LANSKY_DEFINITION,
    "yale_observation": YALE_OBSERVATION_DEFINITION,
    "pediatric_trauma_score": PEDIATRIC_TRAUMA_SCORE_DEFINITION,
    "thrive": THRIVE_DEFINITION,
    "cll_ipi": CLL_IPI_DEFINITION,
    "nottingham_grade": NOTTINGHAM_GRADE_DEFINITION,
    "cisne": CISNE_DEFINITION,
    "simplified_motor_score": SIMPLIFIED_MOTOR_SCORE_DEFINITION,
    # Psychiatry
    "phq9": PHQ9_DEFINITION,
    "gad7": GAD7_DEFINITION,
    # Additional calculators
    "corrected_sodium": CORRECTED_SODIUM_DEFINITION,
    "maintenance_fluids": MAINTENANCE_FLUIDS_DEFINITION,
    "parkland": PARKLAND_DEFINITION,
    "bishop": BISHOP_DEFINITION,
    "psi_port": PSI_PORT_DEFINITION,
    "ranson_admission": RANSON_ADMISSION_DEFINITION,
    "ascvd": ASCVD_DEFINITION,
    "apache_ii": APACHE_II_DEFINITION,
    # ================================================================
    # Tier 1 - Renal Function Calculators
    # ================================================================
    "ckd_epi_2009": CKD_EPI_2009_DEFINITION,
    "mdrd_gfr": MDRD_GFR_DEFINITION,
    "schwartz": SCHWARTZ_DEFINITION,
    "ckd_epi_cystatin": CKD_EPI_CYSTATIN_DEFINITION,
    "ckd_epi_combined": CKD_EPI_COMBINED_DEFINITION,
    "fena": FENA_DEFINITION,
    "feurea": FEUREA_DEFINITION,
    "ttkg": TTKG_DEFINITION,
    # ================================================================
    # Tier 2 - Hepatic Function Calculators
    # ================================================================
    "meld_3": MELD_3_DEFINITION,
    "nafld_fibrosis": NAFLD_FIBROSIS_DEFINITION,
    "apri": APRI_DEFINITION,
    "maddrey_df": MADDREY_DF_DEFINITION,
    "lille": LILLE_DEFINITION,
    "gahs": GAHS_DEFINITION,
    # ================================================================
    # Tier 3 - Electrolytes & Acid-Base Calculators
    # ================================================================
    "delta_gap": DELTA_GAP_DEFINITION,
    "osmolal_gap": OSMOLAL_GAP_DEFINITION,
    "winters_formula": WINTERS_FORMULA_DEFINITION,
    "bicarb_deficit": BICARB_DEFICIT_DEFINITION,
    "free_water_deficit": FREE_WATER_DEFICIT_DEFINITION,
    "sodium_correction_rate": SODIUM_CORRECTION_RATE_DEFINITION,
    "corrected_ag": CORRECTED_AG_DEFINITION,
    # ================================================================
    # Tier 4 - Fluid/Dosing Calculators
    # ================================================================
    "ideal_body_weight": IDEAL_BODY_WEIGHT_DEFINITION,
    "adjusted_body_weight": ADJUSTED_BODY_WEIGHT_DEFINITION,
    "bsa_dubois": BSA_DUBOIS_DEFINITION,
    "bsa_mosteller": BSA_MOSTELLER_DEFINITION,
    "lbw": LBW_DEFINITION,
    "iv_fluid_rate": IV_FLUID_RATE_DEFINITION,
    "crcl_24hr": CRCL_24HR_DEFINITION,
    "pcr_to_24hr": PCR_TO_24HR_DEFINITION,
    "acr": ACR_DEFINITION,
    # ================================================================
    # Tier 5 - Metabolic & Endocrine Calculators
    # ================================================================
    "bmi_asian": BMI_ASIAN_DEFINITION,
    "harris_benedict": HARRIS_BENEDICT_DEFINITION,
    "mifflin_st_jeor": MIFFLIN_ST_JEOR_DEFINITION,
    "homa_ir": HOMA_IR_DEFINITION,
    "homa_b": HOMA_B_DEFINITION,
    "fti": FTI_DEFINITION,
    # ================================================================
    # Tier 6 - Additional Renal/Hepatic Calculators
    # ================================================================
    "ukeld": UKELD_DEFINITION,
    "kings_college_apap": KINGS_COLLEGE_APAP_DEFINITION,
    "kings_college_non_apap": KINGS_COLLEGE_NON_APAP_DEFINITION,
    "kdigo_aki": KDIGO_AKI_DEFINITION,
    "rifle": RIFLE_DEFINITION,
    "akin": AKIN_DEFINITION,
    "urinary_indices": URINARY_INDICES_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 1: Sepsis & Critical Illness
    # ================================================================
    "sepsis_3": SEPSIS_3_DEFINITION,
    "saps_ii": SAPS_II_DEFINITION,
    "saps_iii": SAPS_III_DEFINITION,
    "news": NEWS_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 2: Respiratory & Pulmonary
    # ================================================================
    "crb65": CRB65_DEFINITION,
    "smart_cop": SMART_COP_DEFINITION,
    "pf_ratio": PF_RATIO_DEFINITION,
    "oxygenation_index": OXYGENATION_INDEX_DEFINITION,
    "ards_berlin": ARDS_BERLIN_DEFINITION,
    "murray_score": MURRAY_SCORE_DEFINITION,
    "rox_index": ROX_INDEX_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 3: GI Bleeding
    # ================================================================
    "glasgow_blatchford": GLASGOW_BLATCHFORD_DEFINITION,
    "rockall_pre": ROCKALL_PRE_DEFINITION,
    "rockall_full": ROCKALL_FULL_DEFINITION,
    "aims65": AIMS65_DEFINITION,
    "oakland_score": OAKLAND_SCORE_DEFINITION,
    "forrest": FORREST_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 4: Pancreatitis
    # ================================================================
    "ranson_48h": RANSON_48H_DEFINITION,
    "glasgow_imrie": GLASGOW_IMRIE_DEFINITION,
    "ctsi": CTSI_DEFINITION,
    "haps": HAPS_DEFINITION,
    "marshall_score": MARSHALL_SCORE_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 5: Trauma & Burns
    # ================================================================
    "rts": RTS_DEFINITION,
    "iss": ISS_DEFINITION,
    "pediatric_gcs": PEDIATRIC_GCS_DEFINITION,
    "nexus": NEXUS_DEFINITION,
    "canadian_cspine": CANADIAN_CSPINE_DEFINITION,
    "modified_brooke": MODIFIED_BROOKE_DEFINITION,
    "tbsa_rule_of_9s": TBSA_RULE_OF_9S_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 6: Early Warning & Screening
    # ================================================================
    "mews": MEWS_DEFINITION,
    "pews": PEWS_DEFINITION,
    "rems": REMS_DEFINITION,
    "cart": CART_DEFINITION,
    "lods": LODS_DEFINITION,
    "mods": MODS_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 7: Resuscitation & Arrest
    # ================================================================
    "go_far": GO_FAR_DEFINITION,
    "ohca": OHCA_DEFINITION,
    # ================================================================
    # CRITICAL CARE & EMERGENCY - Tier 8: Miscellaneous
    # ================================================================
    "dic_isth": DIC_ISTH_DEFINITION,
    "hit_4ts": HIT_4TS_DEFINITION,
}


def get_calculator_definition(calculator_id: str) -> CalculatorDefinition | None:
    """Get a calculator definition by ID."""
    return CALCULATOR_DEFINITIONS.get(calculator_id)


def list_calculator_definitions() -> list[CalculatorDefinition]:
    """List all available calculator definitions."""
    return list(CALCULATOR_DEFINITIONS.values())
