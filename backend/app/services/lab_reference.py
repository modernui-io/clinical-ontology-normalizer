"""Lab Reference Ranges Service.

Provides reference ranges and interpretation for clinical laboratory values.
Based on standard clinical reference ranges from major laboratories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class LabCategory(str, Enum):
    """Categories of laboratory tests."""

    CHEMISTRY = "chemistry"  # Basic metabolic, liver, etc.
    HEMATOLOGY = "hematology"  # CBC, coagulation
    CARDIAC = "cardiac"  # Cardiac markers
    LIPID = "lipid"  # Lipid panel
    THYROID = "thyroid"  # Thyroid function
    DIABETES = "diabetes"  # Glucose, HbA1c
    RENAL = "renal"  # Kidney function
    HEPATIC = "hepatic"  # Liver function
    INFLAMMATORY = "inflammatory"  # CRP, ESR
    ELECTROLYTE = "electrolyte"  # Na, K, etc.


class InterpretationLevel(str, Enum):
    """Interpretation levels for lab values."""

    CRITICAL_LOW = "critical_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL_HIGH = "critical_high"


@dataclass
class ReferenceRange:
    """Reference range for a laboratory test."""

    test_name: str
    test_code: str  # LOINC or common abbreviation
    category: LabCategory
    unit: str
    low_normal: float
    high_normal: float
    low_critical: float | None = None
    high_critical: float | None = None
    gender_specific: bool = False
    male_low: float | None = None
    male_high: float | None = None
    female_low: float | None = None
    female_high: float | None = None
    age_specific: bool = False
    notes: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class LabInterpretation:
    """Result of interpreting a lab value."""

    test_name: str
    value: float
    unit: str
    level: InterpretationLevel
    reference_range: str  # "70-100" format
    is_critical: bool
    clinical_significance: str
    possible_causes: list[str]
    recommended_actions: list[str]


# ============================================================================
# Lab Reference Range Database
# ============================================================================

LAB_REFERENCE_RANGES: list[ReferenceRange] = [
    # ==========================================================================
    # BASIC METABOLIC PANEL (BMP)
    # ==========================================================================
    ReferenceRange(
        test_name="Sodium",
        test_code="Na",
        category=LabCategory.ELECTROLYTE,
        unit="mEq/L",
        low_normal=136,
        high_normal=145,
        low_critical=120,
        high_critical=160,
        notes="Serum sodium; reflects fluid balance",
        aliases=["na", "sodium", "serum sodium", "na+"],
    ),
    ReferenceRange(
        test_name="Potassium",
        test_code="K",
        category=LabCategory.ELECTROLYTE,
        unit="mEq/L",
        low_normal=3.5,
        high_normal=5.0,
        low_critical=2.5,
        high_critical=6.5,
        notes="Serum potassium; critical for cardiac function",
        aliases=["k", "potassium", "serum potassium", "k+"],
    ),
    ReferenceRange(
        test_name="Chloride",
        test_code="Cl",
        category=LabCategory.ELECTROLYTE,
        unit="mEq/L",
        low_normal=98,
        high_normal=106,
        notes="Serum chloride",
        aliases=["cl", "chloride", "serum chloride", "cl-"],
    ),
    ReferenceRange(
        test_name="Bicarbonate",
        test_code="CO2",
        category=LabCategory.ELECTROLYTE,
        unit="mEq/L",
        low_normal=23,
        high_normal=29,
        low_critical=12,
        high_critical=40,
        notes="Also called total CO2; reflects acid-base status",
        aliases=["co2", "bicarb", "hco3", "bicarbonate", "total co2"],
    ),
    ReferenceRange(
        test_name="Blood Urea Nitrogen",
        test_code="BUN",
        category=LabCategory.RENAL,
        unit="mg/dL",
        low_normal=7,
        high_normal=20,
        high_critical=100,
        notes="Kidney function marker; also affected by hydration",
        aliases=["bun", "urea nitrogen", "urea", "blood urea nitrogen"],
    ),
    ReferenceRange(
        test_name="Creatinine",
        test_code="Cr",
        category=LabCategory.RENAL,
        unit="mg/dL",
        low_normal=0.7,
        high_normal=1.3,
        high_critical=10.0,
        gender_specific=True,
        male_low=0.7,
        male_high=1.3,
        female_low=0.6,
        female_high=1.1,
        notes="Primary kidney function marker",
        aliases=["cr", "creat", "creatinine", "serum creatinine", "scr"],
    ),
    ReferenceRange(
        test_name="Glucose",
        test_code="Glu",
        category=LabCategory.DIABETES,
        unit="mg/dL",
        low_normal=70,
        high_normal=100,
        low_critical=40,
        high_critical=500,
        notes="Fasting glucose; random may be higher",
        aliases=["glucose", "glu", "blood sugar", "bs", "fasting glucose", "fbg"],
    ),
    ReferenceRange(
        test_name="Calcium",
        test_code="Ca",
        category=LabCategory.CHEMISTRY,
        unit="mg/dL",
        low_normal=8.5,
        high_normal=10.5,
        low_critical=6.0,
        high_critical=13.0,
        notes="Total calcium; interpret with albumin",
        aliases=["ca", "calcium", "serum calcium", "ca2+"],
    ),

    # ==========================================================================
    # COMPLETE METABOLIC PANEL (CMP) - Additional tests
    # ==========================================================================
    ReferenceRange(
        test_name="Total Protein",
        test_code="TP",
        category=LabCategory.HEPATIC,
        unit="g/dL",
        low_normal=6.0,
        high_normal=8.3,
        notes="Total serum protein",
        aliases=["tp", "total protein", "protein total"],
    ),
    ReferenceRange(
        test_name="Albumin",
        test_code="Alb",
        category=LabCategory.HEPATIC,
        unit="g/dL",
        low_normal=3.5,
        high_normal=5.0,
        notes="Main plasma protein; nutritional marker",
        aliases=["alb", "albumin", "serum albumin"],
    ),
    ReferenceRange(
        test_name="Total Bilirubin",
        test_code="TBili",
        category=LabCategory.HEPATIC,
        unit="mg/dL",
        low_normal=0.1,
        high_normal=1.2,
        high_critical=15.0,
        notes="Total bilirubin; elevated in liver disease/hemolysis",
        aliases=["tbili", "bilirubin", "total bilirubin", "bili"],
    ),
    ReferenceRange(
        test_name="Alkaline Phosphatase",
        test_code="ALP",
        category=LabCategory.HEPATIC,
        unit="U/L",
        low_normal=44,
        high_normal=147,
        notes="Liver/bone enzyme; elevated in cholestasis",
        aliases=["alp", "alk phos", "alkaline phosphatase"],
    ),
    ReferenceRange(
        test_name="AST",
        test_code="AST",
        category=LabCategory.HEPATIC,
        unit="U/L",
        low_normal=10,
        high_normal=40,
        high_critical=1000,
        notes="Aspartate aminotransferase; liver/heart/muscle",
        aliases=["ast", "sgot", "aspartate aminotransferase"],
    ),
    ReferenceRange(
        test_name="ALT",
        test_code="ALT",
        category=LabCategory.HEPATIC,
        unit="U/L",
        low_normal=7,
        high_normal=56,
        high_critical=1000,
        notes="Alanine aminotransferase; liver-specific",
        aliases=["alt", "sgpt", "alanine aminotransferase"],
    ),

    # ==========================================================================
    # COMPLETE BLOOD COUNT (CBC)
    # ==========================================================================
    ReferenceRange(
        test_name="White Blood Cell Count",
        test_code="WBC",
        category=LabCategory.HEMATOLOGY,
        unit="K/uL",
        low_normal=4.5,
        high_normal=11.0,
        low_critical=1.0,
        high_critical=30.0,
        notes="Total white blood cells",
        aliases=["wbc", "white count", "white blood cells", "leukocytes"],
    ),
    ReferenceRange(
        test_name="Hemoglobin",
        test_code="Hgb",
        category=LabCategory.HEMATOLOGY,
        unit="g/dL",
        low_normal=12.0,
        high_normal=17.5,
        low_critical=7.0,
        high_critical=20.0,
        gender_specific=True,
        male_low=13.5,
        male_high=17.5,
        female_low=12.0,
        female_high=16.0,
        notes="Oxygen-carrying capacity",
        aliases=["hgb", "hb", "hemoglobin"],
    ),
    ReferenceRange(
        test_name="Hematocrit",
        test_code="Hct",
        category=LabCategory.HEMATOLOGY,
        unit="%",
        low_normal=36,
        high_normal=50,
        low_critical=20,
        high_critical=60,
        gender_specific=True,
        male_low=38.3,
        male_high=50,
        female_low=36,
        female_high=44.4,
        notes="Red blood cell volume percentage",
        aliases=["hct", "hematocrit", "crit"],
    ),
    ReferenceRange(
        test_name="Platelet Count",
        test_code="Plt",
        category=LabCategory.HEMATOLOGY,
        unit="K/uL",
        low_normal=150,
        high_normal=400,
        low_critical=50,
        high_critical=1000,
        notes="Thrombocyte count; clotting cells",
        aliases=["plt", "platelets", "platelet count", "thrombocytes"],
    ),
    ReferenceRange(
        test_name="Mean Corpuscular Volume",
        test_code="MCV",
        category=LabCategory.HEMATOLOGY,
        unit="fL",
        low_normal=80,
        high_normal=100,
        notes="Average RBC size; classifies anemia",
        aliases=["mcv", "mean corpuscular volume"],
    ),

    # ==========================================================================
    # COAGULATION PANEL
    # ==========================================================================
    ReferenceRange(
        test_name="Prothrombin Time",
        test_code="PT",
        category=LabCategory.HEMATOLOGY,
        unit="seconds",
        low_normal=11,
        high_normal=13.5,
        high_critical=50,
        notes="Extrinsic pathway; monitors warfarin",
        aliases=["pt", "prothrombin time", "pro time"],
    ),
    ReferenceRange(
        test_name="INR",
        test_code="INR",
        category=LabCategory.HEMATOLOGY,
        unit="ratio",
        low_normal=0.8,
        high_normal=1.1,
        high_critical=5.0,
        notes="Standardized PT; therapeutic 2-3 for most indications",
        aliases=["inr", "international normalized ratio"],
    ),
    ReferenceRange(
        test_name="PTT",
        test_code="PTT",
        category=LabCategory.HEMATOLOGY,
        unit="seconds",
        low_normal=25,
        high_normal=35,
        high_critical=100,
        notes="Intrinsic pathway; monitors heparin",
        aliases=["ptt", "aptt", "partial thromboplastin time"],
    ),

    # ==========================================================================
    # CARDIAC MARKERS
    # ==========================================================================
    ReferenceRange(
        test_name="Troponin I",
        test_code="TnI",
        category=LabCategory.CARDIAC,
        unit="ng/mL",
        low_normal=0,
        high_normal=0.04,
        high_critical=0.5,
        notes="Cardiac-specific; elevated in MI",
        aliases=["troponin", "tni", "troponin i", "cardiac troponin"],
    ),
    ReferenceRange(
        test_name="BNP",
        test_code="BNP",
        category=LabCategory.CARDIAC,
        unit="pg/mL",
        low_normal=0,
        high_normal=100,
        high_critical=900,
        notes="Heart failure marker",
        aliases=["bnp", "b-type natriuretic peptide", "brain natriuretic peptide"],
    ),
    ReferenceRange(
        test_name="NT-proBNP",
        test_code="NT-proBNP",
        category=LabCategory.CARDIAC,
        unit="pg/mL",
        low_normal=0,
        high_normal=300,
        high_critical=1800,
        age_specific=True,
        notes="Heart failure marker; age-dependent cutoffs",
        aliases=["nt-probnp", "ntprobnp", "pro-bnp"],
    ),

    # ==========================================================================
    # LIPID PANEL
    # ==========================================================================
    ReferenceRange(
        test_name="Total Cholesterol",
        test_code="TC",
        category=LabCategory.LIPID,
        unit="mg/dL",
        low_normal=0,
        high_normal=200,
        notes="<200 desirable; >240 high",
        aliases=["cholesterol", "total cholesterol", "tc", "chol"],
    ),
    ReferenceRange(
        test_name="LDL Cholesterol",
        test_code="LDL",
        category=LabCategory.LIPID,
        unit="mg/dL",
        low_normal=0,
        high_normal=100,
        notes="<100 optimal; <70 for high-risk patients",
        aliases=["ldl", "ldl-c", "ldl cholesterol", "bad cholesterol"],
    ),
    ReferenceRange(
        test_name="HDL Cholesterol",
        test_code="HDL",
        category=LabCategory.LIPID,
        unit="mg/dL",
        low_normal=40,
        high_normal=200,
        gender_specific=True,
        male_low=40,
        male_high=200,
        female_low=50,
        female_high=200,
        notes=">40 men, >50 women; higher is better",
        aliases=["hdl", "hdl-c", "hdl cholesterol", "good cholesterol"],
    ),
    ReferenceRange(
        test_name="Triglycerides",
        test_code="TG",
        category=LabCategory.LIPID,
        unit="mg/dL",
        low_normal=0,
        high_normal=150,
        high_critical=500,
        notes="<150 normal; >500 pancreatitis risk",
        aliases=["tg", "triglycerides", "trigs"],
    ),

    # ==========================================================================
    # THYROID FUNCTION
    # ==========================================================================
    ReferenceRange(
        test_name="TSH",
        test_code="TSH",
        category=LabCategory.THYROID,
        unit="mIU/L",
        low_normal=0.4,
        high_normal=4.0,
        notes="Primary thyroid screening test",
        aliases=["tsh", "thyroid stimulating hormone", "thyrotropin"],
    ),
    ReferenceRange(
        test_name="Free T4",
        test_code="FT4",
        category=LabCategory.THYROID,
        unit="ng/dL",
        low_normal=0.8,
        high_normal=1.8,
        notes="Free thyroxine; active thyroid hormone",
        aliases=["ft4", "free t4", "free thyroxine", "t4 free"],
    ),
    ReferenceRange(
        test_name="Free T3",
        test_code="FT3",
        category=LabCategory.THYROID,
        unit="pg/mL",
        low_normal=2.3,
        high_normal=4.2,
        notes="Free triiodothyronine",
        aliases=["ft3", "free t3", "free triiodothyronine", "t3 free"],
    ),

    # ==========================================================================
    # DIABETES
    # ==========================================================================
    ReferenceRange(
        test_name="Hemoglobin A1c",
        test_code="HbA1c",
        category=LabCategory.DIABETES,
        unit="%",
        low_normal=4.0,
        high_normal=5.6,
        notes="<5.7 normal; 5.7-6.4 prediabetes; >=6.5 diabetes",
        aliases=["hba1c", "a1c", "hemoglobin a1c", "glycated hemoglobin", "glycohemoglobin"],
    ),

    # ==========================================================================
    # INFLAMMATORY MARKERS
    # ==========================================================================
    ReferenceRange(
        test_name="C-Reactive Protein",
        test_code="CRP",
        category=LabCategory.INFLAMMATORY,
        unit="mg/L",
        low_normal=0,
        high_normal=3.0,
        notes="Acute phase reactant; <1 low CV risk, 1-3 mod, >3 high",
        aliases=["crp", "c-reactive protein", "hs-crp", "high-sensitivity crp"],
    ),
    ReferenceRange(
        test_name="ESR",
        test_code="ESR",
        category=LabCategory.INFLAMMATORY,
        unit="mm/hr",
        low_normal=0,
        high_normal=20,
        gender_specific=True,
        male_low=0,
        male_high=15,
        female_low=0,
        female_high=20,
        notes="Non-specific inflammatory marker",
        aliases=["esr", "sed rate", "erythrocyte sedimentation rate"],
    ),

    # ==========================================================================
    # RENAL FUNCTION
    # ==========================================================================
    ReferenceRange(
        test_name="eGFR",
        test_code="eGFR",
        category=LabCategory.RENAL,
        unit="mL/min/1.73m2",
        low_normal=90,
        high_normal=120,
        low_critical=15,
        notes=">90 normal; 60-89 mild CKD; 30-59 moderate; 15-29 severe; <15 ESRD",
        aliases=["egfr", "gfr", "estimated gfr", "glomerular filtration rate"],
    ),
    ReferenceRange(
        test_name="Uric Acid",
        test_code="UA",
        category=LabCategory.RENAL,
        unit="mg/dL",
        low_normal=3.5,
        high_normal=7.2,
        gender_specific=True,
        male_low=4.0,
        male_high=8.0,
        female_low=2.5,
        female_high=7.0,
        notes="Elevated in gout, kidney disease",
        aliases=["uric acid", "ua", "serum uric acid"],
    ),

    # ==========================================================================
    # MAGNESIUM & PHOSPHORUS
    # ==========================================================================
    ReferenceRange(
        test_name="Magnesium",
        test_code="Mg",
        category=LabCategory.ELECTROLYTE,
        unit="mg/dL",
        low_normal=1.7,
        high_normal=2.2,
        low_critical=1.0,
        high_critical=4.0,
        notes="Often low with diuretics, alcohol use",
        aliases=["mg", "magnesium", "serum magnesium", "mg2+"],
    ),
    ReferenceRange(
        test_name="Phosphorus",
        test_code="Phos",
        category=LabCategory.ELECTROLYTE,
        unit="mg/dL",
        low_normal=2.5,
        high_normal=4.5,
        low_critical=1.0,
        high_critical=9.0,
        notes="Inverse relationship with calcium",
        aliases=["phos", "phosphorus", "phosphate", "serum phosphorus", "po4"],
    ),
]

# Build lookup indexes
_TEST_INDEX: dict[str, ReferenceRange] = {}
_ALIAS_INDEX: dict[str, ReferenceRange] = {}

for ref_range in LAB_REFERENCE_RANGES:
    _TEST_INDEX[ref_range.test_code.lower()] = ref_range
    for alias in ref_range.aliases:
        _ALIAS_INDEX[alias.lower()] = ref_range


# ============================================================================
# Interpretation Causes and Recommendations
# ============================================================================

INTERPRETATION_CAUSES: dict[str, dict[str, list[str]]] = {
    "na": {
        "low": ["SIADH", "Diuretics", "Heart failure", "Cirrhosis", "Adrenal insufficiency"],
        "high": ["Dehydration", "Diabetes insipidus", "Excessive salt intake", "Hyperaldosteronism"],
    },
    "k": {
        "low": ["Diuretics", "Vomiting/diarrhea", "Hypomagnesemia", "Alkalosis", "Insulin"],
        "high": ["Kidney disease", "ACE inhibitors", "Potassium supplements", "Hemolysis", "Acidosis"],
    },
    "glucose": {
        "low": ["Insulin overdose", "Skipped meal", "Alcohol", "Sepsis", "Adrenal insufficiency"],
        "high": ["Diabetes", "Stress response", "Corticosteroids", "Infection", "Pancreatitis"],
    },
    "cr": {
        "high": ["Acute kidney injury", "Chronic kidney disease", "Dehydration", "Medications", "Rhabdomyolysis"],
    },
    "bun": {
        "high": ["Dehydration", "GI bleeding", "High protein diet", "Kidney disease", "Heart failure"],
    },
    "hgb": {
        "low": ["Iron deficiency", "B12/folate deficiency", "Chronic disease", "Bleeding", "Hemolysis"],
        "high": ["Polycythemia vera", "Chronic hypoxia", "Dehydration"],
    },
    "wbc": {
        "low": ["Bone marrow suppression", "Chemotherapy", "Viral infection", "Autoimmune disease"],
        "high": ["Infection", "Inflammation", "Leukemia", "Stress response", "Corticosteroids"],
    },
    "plt": {
        "low": ["ITP", "DIC", "Bone marrow suppression", "Splenomegaly", "Medications"],
        "high": ["Reactive thrombocytosis", "Myeloproliferative disorder", "Iron deficiency"],
    },
    "troponin": {
        "high": ["Myocardial infarction", "Myocarditis", "Pulmonary embolism", "Heart failure", "Sepsis"],
    },
    "tsh": {
        "low": ["Hyperthyroidism", "Excessive thyroid replacement", "Pituitary disease", "Non-thyroidal illness"],
        "high": ["Hypothyroidism", "Inadequate thyroid replacement", "TSH-secreting tumor"],
    },
    "hba1c": {
        "high": ["Uncontrolled diabetes", "Non-adherence to medications", "Dietary indiscretion"],
    },
}


class LabReferenceService:
    """Service for interpreting laboratory values.

    Provides reference ranges and clinical interpretation for common
    laboratory tests.

    Usage:
        service = LabReferenceService()

        # Interpret a single value
        result = service.interpret("Na", 130)
        print(f"{result.test_name}: {result.level.value}")

        # Get reference range
        ref = service.get_reference("glucose")
        print(f"Normal range: {ref.low_normal}-{ref.high_normal} {ref.unit}")
    """

    def __init__(self) -> None:
        """Initialize the lab reference service."""
        self._reference_ranges = LAB_REFERENCE_RANGES
        self._test_index = _TEST_INDEX
        self._alias_index = _ALIAS_INDEX

    def normalize_test_name(self, test: str) -> str:
        """Normalize test name to lookup key.

        Args:
            test: Test name or code.

        Returns:
            Normalized lowercase test name.
        """
        return test.lower().strip()

    def get_reference(self, test: str) -> ReferenceRange | None:
        """Get reference range for a test.

        Args:
            test: Test name, code, or alias.

        Returns:
            ReferenceRange if found, None otherwise.
        """
        key = self.normalize_test_name(test)

        # Check direct code match first
        if key in self._test_index:
            return self._test_index[key]

        # Check aliases
        if key in self._alias_index:
            return self._alias_index[key]

        return None

    def interpret(
        self,
        test: str,
        value: float,
        gender: str | None = None,
    ) -> LabInterpretation | None:
        """Interpret a laboratory value.

        Args:
            test: Test name, code, or alias.
            value: Numeric value.
            gender: Optional "male" or "female" for gender-specific ranges.

        Returns:
            LabInterpretation if test found, None otherwise.
        """
        ref = self.get_reference(test)
        if ref is None:
            return None

        # Determine reference range to use
        low = ref.low_normal
        high = ref.high_normal

        if ref.gender_specific and gender:
            if gender.lower() == "male" and ref.male_low is not None:
                low = ref.male_low
                high = ref.male_high or ref.high_normal
            elif gender.lower() == "female" and ref.female_low is not None:
                low = ref.female_low
                high = ref.female_high or ref.high_normal

        # Determine interpretation level
        level = InterpretationLevel.NORMAL
        is_critical = False

        if ref.low_critical is not None and value < ref.low_critical:
            level = InterpretationLevel.CRITICAL_LOW
            is_critical = True
        elif value < low:
            level = InterpretationLevel.LOW
        elif ref.high_critical is not None and value > ref.high_critical:
            level = InterpretationLevel.CRITICAL_HIGH
            is_critical = True
        elif value > high:
            level = InterpretationLevel.HIGH

        # Build reference range string
        ref_str = f"{low}-{high}"

        # Get clinical significance
        significance = self._get_significance(ref.test_code, level, value, ref)

        # Get possible causes
        causes = self._get_causes(ref.test_code, level)

        # Get recommended actions
        actions = self._get_actions(level, is_critical)

        return LabInterpretation(
            test_name=ref.test_name,
            value=value,
            unit=ref.unit,
            level=level,
            reference_range=ref_str,
            is_critical=is_critical,
            clinical_significance=significance,
            possible_causes=causes,
            recommended_actions=actions,
        )

    def _get_significance(
        self,
        test_code: str,
        level: InterpretationLevel,
        value: float,
        ref: ReferenceRange,
    ) -> str:
        """Get clinical significance description."""
        if level == InterpretationLevel.NORMAL:
            return f"{ref.test_name} is within normal limits"

        if level == InterpretationLevel.CRITICAL_LOW:
            return f"Critically low {ref.test_name} - may require immediate intervention"

        if level == InterpretationLevel.CRITICAL_HIGH:
            return f"Critically elevated {ref.test_name} - may require immediate intervention"

        if level == InterpretationLevel.LOW:
            return f"Low {ref.test_name} - may indicate underlying condition"

        if level == InterpretationLevel.HIGH:
            return f"Elevated {ref.test_name} - may indicate underlying condition"

        return ""

    def _get_causes(self, test_code: str, level: InterpretationLevel) -> list[str]:
        """Get possible causes for abnormal value."""
        key = test_code.lower()
        if key not in INTERPRETATION_CAUSES:
            return []

        causes = INTERPRETATION_CAUSES[key]

        if level in [InterpretationLevel.LOW, InterpretationLevel.CRITICAL_LOW]:
            return causes.get("low", [])
        elif level in [InterpretationLevel.HIGH, InterpretationLevel.CRITICAL_HIGH]:
            return causes.get("high", [])

        return []

    def _get_actions(
        self,
        level: InterpretationLevel,
        is_critical: bool,
    ) -> list[str]:
        """Get recommended actions based on interpretation level."""
        if is_critical:
            return [
                "Notify physician immediately",
                "Recheck value to confirm",
                "Assess patient clinically",
                "Consider immediate intervention",
            ]

        if level in [InterpretationLevel.LOW, InterpretationLevel.HIGH]:
            return [
                "Correlate with clinical presentation",
                "Consider repeat testing",
                "Review medication list",
                "Evaluate for underlying causes",
            ]

        return []

    def interpret_panel(
        self,
        values: dict[str, float],
        gender: str | None = None,
    ) -> list[LabInterpretation]:
        """Interpret multiple lab values.

        Args:
            values: Dict of test name/code to value.
            gender: Optional gender for gender-specific ranges.

        Returns:
            List of interpretations for recognized tests.
        """
        results = []
        for test, value in values.items():
            interpretation = self.interpret(test, value, gender)
            if interpretation:
                results.append(interpretation)
        return results

    def get_all_references(
        self,
        category: LabCategory | None = None,
    ) -> list[ReferenceRange]:
        """Get all reference ranges, optionally filtered by category.

        Args:
            category: Optional category filter.

        Returns:
            List of reference ranges.
        """
        if category is None:
            return self._reference_ranges

        return [r for r in self._reference_ranges if r.category == category]

    def search(self, query: str, limit: int = 10) -> list[ReferenceRange]:
        """Search for reference ranges by name or alias.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            List of matching reference ranges.
        """
        query_lower = query.lower()
        results = []

        for ref in self._reference_ranges:
            # Check test name and code
            if query_lower in ref.test_name.lower() or query_lower in ref.test_code.lower():
                results.append(ref)
                continue

            # Check aliases
            for alias in ref.aliases:
                if query_lower in alias:
                    results.append(ref)
                    break

            if len(results) >= limit:
                break

        return results[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the reference database.

        Returns:
            Dictionary with database statistics.
        """
        by_category: dict[str, int] = {}
        gender_specific = 0
        with_critical_ranges = 0

        for ref in self._reference_ranges:
            cat = ref.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            if ref.gender_specific:
                gender_specific += 1

            if ref.low_critical is not None or ref.high_critical is not None:
                with_critical_ranges += 1

        return {
            "total_tests": len(self._reference_ranges),
            "by_category": by_category,
            "gender_specific_count": gender_specific,
            "with_critical_ranges": with_critical_ranges,
            "total_aliases": sum(len(r.aliases) for r in self._reference_ranges),
        }


# Singleton instance and lock
_lab_reference_service: LabReferenceService | None = None
_lab_reference_lock = Lock()


def get_lab_reference_service() -> LabReferenceService:
    """Get the singleton LabReferenceService instance.

    Returns:
        The singleton LabReferenceService instance.
    """
    global _lab_reference_service

    if _lab_reference_service is None:
        with _lab_reference_lock:
            if _lab_reference_service is None:
                logger.info("Creating singleton LabReferenceService instance")
                _lab_reference_service = LabReferenceService()

    return _lab_reference_service


def reset_lab_reference_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _lab_reference_service
    with _lab_reference_lock:
        _lab_reference_service = None
