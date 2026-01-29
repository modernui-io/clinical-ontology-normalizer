"""HCC Revenue Recovery Pipeline.

Analyzes clinical documentation to identify HCC (Hierarchical Condition Category)
coding opportunities for Medicare Advantage risk adjustment.

Key capabilities:
1. Map ICD-10 codes to HCC categories with RAF values
2. Extract HCC-relevant conditions from clinical text
3. Compare documented vs coded conditions (gap analysis)
4. Calculate revenue opportunity ($$ impact)
5. Prioritize by capture likelihood and RAF value
6. Generate evidence-backed recommendations for coders

CMS HCC Model V28 (2024+) is the basis for category mappings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)


class HCCCategory(Enum):
    """Major HCC category groups."""

    CANCER = "cancer"
    DIABETES = "diabetes"
    LIVER = "liver"
    CARDIOVASCULAR = "cardiovascular"
    VASCULAR = "vascular"
    RENAL = "renal"
    RESPIRATORY = "respiratory"
    NEUROLOGICAL = "neurological"
    PSYCHIATRIC = "psychiatric"
    BLOOD = "blood"
    IMMUNE = "immune"
    METABOLIC = "metabolic"
    MUSCULOSKELETAL = "musculoskeletal"
    SKIN = "skin"


class CaptureConfidence(Enum):
    """Confidence that the HCC can be captured/coded."""

    HIGH = "high"  # Clear documentation, straightforward code
    MEDIUM = "medium"  # Documentation supports, may need clarification
    LOW = "low"  # Mentioned but needs significant documentation improvement


class GapType(Enum):
    """Type of HCC coding gap."""

    NOT_CODED = "not_coded"  # Documented but not on problem list/claims
    NEEDS_SPECIFICITY = "needs_specificity"  # Coded but at non-HCC level
    NEEDS_RECAPTURE = "needs_recapture"  # Previously coded, not this year
    SUSPECT = "suspect"  # Lab/clinical signs suggest but not explicitly documented


@dataclass
class HCCDefinition:
    """Definition of an HCC category."""

    hcc_code: str  # e.g., "HCC19"
    description: str
    category: HCCCategory
    raf_community: float  # Community RAF value
    raf_institutional: float  # Institutional RAF value
    icd10_codes: list[str]  # ICD-10 codes that map to this HCC
    clinical_indicators: list[str]  # Keywords/phrases that suggest this HCC
    lab_indicators: list[dict[str, Any]]  # Lab values that suggest this HCC
    documentation_requirements: list[str]  # What needs to be documented


@dataclass
class HCCEvidence:
    """Evidence supporting an HCC finding."""

    source_type: str  # "note", "lab", "problem_list", "claim"
    source_text: str  # The relevant text excerpt
    source_date: str | None = None
    confidence: float = 0.0  # 0-1 confidence score
    icd10_suggested: str | None = None


@dataclass
class HCCOpportunity:
    """An identified HCC revenue opportunity."""

    hcc_code: str
    hcc_description: str
    category: HCCCategory
    gap_type: GapType
    capture_confidence: CaptureConfidence

    # Financial impact
    raf_value: float
    estimated_revenue: float  # raf_value * per_member_payment

    # Evidence
    evidence: list[HCCEvidence] = field(default_factory=list)
    supporting_icd10_codes: list[str] = field(default_factory=list)
    current_coded_icd10: str | None = None  # What's currently coded (if any)

    # Action items
    recommended_icd10: str | None = None
    documentation_needed: list[str] = field(default_factory=list)
    coder_notes: str = ""

    # Metadata
    patient_id: str | None = None
    encounter_id: str | None = None


@dataclass
class HCCAnalysisResult:
    """Result of HCC revenue recovery analysis."""

    # Opportunities found
    opportunities: list[HCCOpportunity] = field(default_factory=list)
    total_opportunities: int = 0

    # Financial summary
    total_raf_opportunity: float = 0.0
    total_estimated_revenue: float = 0.0
    high_confidence_revenue: float = 0.0

    # Breakdown
    by_category: dict[str, int] = field(default_factory=dict)
    by_gap_type: dict[str, int] = field(default_factory=dict)
    by_confidence: dict[str, int] = field(default_factory=dict)

    # Current state
    current_hccs: list[str] = field(default_factory=list)
    current_raf_score: float = 0.0

    # Projected state
    projected_hccs: list[str] = field(default_factory=list)
    projected_raf_score: float = 0.0

    # Priority actions
    priority_actions: list[str] = field(default_factory=list)

    # Timing
    analysis_date: str = ""
    analysis_time_ms: float = 0.0


# ============================================================================
# HCC Model V28 Definitions (2024)
# Partial list - high-value HCCs
# ============================================================================

HCC_DEFINITIONS: list[HCCDefinition] = [
    # -------------------------------------------------------------------------
    # Diabetes HCCs (High prevalence, moderate RAF)
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC37",
        description="Diabetes with Chronic Complications",
        category=HCCCategory.DIABETES,
        raf_community=0.302,
        raf_institutional=0.188,
        icd10_codes=[
            "E11.21", "E11.22", "E11.29",  # DM2 with nephropathy
            "E11.311", "E11.319", "E11.321", "E11.329",  # DM2 with retinopathy
            "E11.40", "E11.41", "E11.42", "E11.43", "E11.44", "E11.49",  # DM2 with neuropathy
            "E11.51", "E11.52", "E11.59",  # DM2 with PVD
            "E11.610", "E11.618", "E11.620", "E11.621", "E11.622",  # DM2 with other complications
            "E11.628", "E11.630", "E11.638", "E11.641", "E11.649",
            "E11.65",  # DM2 with hyperglycemia
            "E10.21", "E10.22", "E10.29",  # DM1 with nephropathy
            "E10.311", "E10.319", "E10.321", "E10.329",  # DM1 with retinopathy
            "E10.40", "E10.41", "E10.42", "E10.43", "E10.44", "E10.49",  # DM1 with neuropathy
        ],
        clinical_indicators=[
            "diabetic nephropathy", "diabetic retinopathy", "diabetic neuropathy",
            "diabetic foot", "diabetic ulcer", "peripheral neuropathy",
            "nephropathy", "retinopathy", "neuropathy", "microalbuminuria",
            "proteinuria", "diabetic ckd", "diabetic kidney",
        ],
        lab_indicators=[
            {"name": "HbA1c", "operator": ">", "value": 9.0, "unit": "%"},
            {"name": "urine_albumin_creatinine_ratio", "operator": ">", "value": 30, "unit": "mg/g"},
            {"name": "eGFR", "operator": "<", "value": 60, "unit": "mL/min"},
        ],
        documentation_requirements=[
            "Type of diabetes (1 or 2)",
            "Specific complication (nephropathy, retinopathy, neuropathy, etc.)",
            "Causal relationship between diabetes and complication",
        ],
    ),

    # -------------------------------------------------------------------------
    # Heart Failure HCCs (High RAF value)
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC85",
        description="Heart Failure",
        category=HCCCategory.CARDIOVASCULAR,
        raf_community=0.323,
        raf_institutional=0.191,
        icd10_codes=[
            "I50.1", "I50.20", "I50.21", "I50.22", "I50.23",  # Systolic HF
            "I50.30", "I50.31", "I50.32", "I50.33",  # Diastolic HF
            "I50.40", "I50.41", "I50.42", "I50.43",  # Combined HF
            "I50.810", "I50.811", "I50.812", "I50.813", "I50.814",  # HF stage
            "I50.82", "I50.83", "I50.84", "I50.89", "I50.9",
        ],
        clinical_indicators=[
            "heart failure", "chf", "hfref", "hfpef", "congestive heart failure",
            "systolic dysfunction", "diastolic dysfunction", "ef ", "ejection fraction",
            "cardiomyopathy", "lvef", "reduced ef", "preserved ef",
        ],
        lab_indicators=[
            {"name": "BNP", "operator": ">", "value": 100, "unit": "pg/mL"},
            {"name": "NT-proBNP", "operator": ">", "value": 300, "unit": "pg/mL"},
            {"name": "ejection_fraction", "operator": "<", "value": 40, "unit": "%"},
        ],
        documentation_requirements=[
            "Type of heart failure (systolic/HFrEF, diastolic/HFpEF, combined)",
            "Acuity (acute, chronic, acute-on-chronic)",
            "Ejection fraction if known",
        ],
    ),

    # -------------------------------------------------------------------------
    # CKD HCCs (High prevalence)
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC326",
        description="Chronic Kidney Disease, Stage 5",
        category=HCCCategory.RENAL,
        raf_community=0.237,
        raf_institutional=0.170,
        icd10_codes=["N18.5", "N18.6"],
        clinical_indicators=[
            "ckd stage 5", "esrd", "end stage renal", "dialysis", "kidney failure",
            "chronic kidney disease stage 5", "gfr <15",
        ],
        lab_indicators=[
            {"name": "eGFR", "operator": "<", "value": 15, "unit": "mL/min"},
        ],
        documentation_requirements=[
            "CKD Stage 5 explicitly documented",
            "Dialysis status if applicable",
        ],
    ),
    HCCDefinition(
        hcc_code="HCC327",
        description="Chronic Kidney Disease, Stage 4",
        category=HCCCategory.RENAL,
        raf_community=0.237,
        raf_institutional=0.170,
        icd10_codes=["N18.4"],
        clinical_indicators=[
            "ckd stage 4", "ckd 4", "chronic kidney disease stage 4",
            "gfr 15-29", "severe ckd",
        ],
        lab_indicators=[
            {"name": "eGFR", "operator": "<", "value": 30, "unit": "mL/min"},
            {"name": "eGFR", "operator": ">=", "value": 15, "unit": "mL/min"},
        ],
        documentation_requirements=[
            "CKD Stage 4 explicitly documented",
            "Etiology if known (diabetic, hypertensive, etc.)",
        ],
    ),

    # -------------------------------------------------------------------------
    # COPD HCCs
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC111",
        description="Chronic Obstructive Pulmonary Disease",
        category=HCCCategory.RESPIRATORY,
        raf_community=0.335,
        raf_institutional=0.200,
        icd10_codes=[
            "J44.0", "J44.1", "J44.9",  # COPD
            "J43.0", "J43.1", "J43.2", "J43.8", "J43.9",  # Emphysema
        ],
        clinical_indicators=[
            "copd", "chronic obstructive pulmonary", "emphysema",
            "chronic bronchitis", "copd exacerbation", "gold stage",
            "fev1", "obstructive lung disease",
        ],
        lab_indicators=[
            {"name": "FEV1_FVC_ratio", "operator": "<", "value": 0.7, "unit": "ratio"},
        ],
        documentation_requirements=[
            "COPD diagnosis with specificity (with exacerbation, etc.)",
            "Severity if known (GOLD stage)",
        ],
    ),

    # -------------------------------------------------------------------------
    # Stroke/CVA HCCs
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC100",
        description="Ischemic or Unspecified Stroke",
        category=HCCCategory.NEUROLOGICAL,
        raf_community=0.268,
        raf_institutional=0.138,
        icd10_codes=[
            "I63.00", "I63.011", "I63.012", "I63.019", "I63.02",  # Cerebral infarction
            "I63.10", "I63.111", "I63.112", "I63.119", "I63.12",
            "I63.20", "I63.211", "I63.212", "I63.219", "I63.22",
            "I63.30", "I63.311", "I63.312", "I63.319", "I63.321",
            "I63.40", "I63.411", "I63.412", "I63.419", "I63.421",
            "I63.50", "I63.511", "I63.512", "I63.519", "I63.521",
            "I63.6", "I63.81", "I63.89", "I63.9",
        ],
        clinical_indicators=[
            "stroke", "cva", "cerebral infarction", "ischemic stroke",
            "cerebrovascular accident", "hemiparesis", "hemiplegia",
        ],
        lab_indicators=[],
        documentation_requirements=[
            "Type of stroke (ischemic, hemorrhagic)",
            "Location if known",
            "Residual deficits",
        ],
    ),

    # -------------------------------------------------------------------------
    # Major Depression HCCs
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC155",
        description="Major Depression, Moderate or Severe",
        category=HCCCategory.PSYCHIATRIC,
        raf_community=0.309,
        raf_institutional=0.189,
        icd10_codes=[
            "F32.1", "F32.2", "F32.3", "F32.4", "F32.5",  # Major depressive, single
            "F33.1", "F33.2", "F33.3", "F33.41", "F33.42",  # Major depressive, recurrent
        ],
        clinical_indicators=[
            "major depression", "major depressive disorder", "severe depression",
            "moderate depression", "mdd", "depression with psychotic",
            "recurrent depression", "treatment resistant depression",
        ],
        lab_indicators=[],
        documentation_requirements=[
            "Severity (mild, moderate, severe)",
            "Single episode vs recurrent",
            "With or without psychotic features",
        ],
    ),

    # -------------------------------------------------------------------------
    # Morbid Obesity HCC
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC48",
        description="Morbid Obesity",
        category=HCCCategory.METABOLIC,
        raf_community=0.250,
        raf_institutional=0.167,
        icd10_codes=["E66.01", "E66.2"],
        clinical_indicators=[
            "morbid obesity", "bmi 40", "bmi >40", "bmi over 40",
            "severe obesity", "class iii obesity", "super obesity",
        ],
        lab_indicators=[
            {"name": "BMI", "operator": ">=", "value": 40, "unit": "kg/m2"},
        ],
        documentation_requirements=[
            "BMI >= 40 or BMI >= 35 with comorbidity",
            "Morbid obesity explicitly documented (not just BMI)",
        ],
    ),

    # -------------------------------------------------------------------------
    # Vascular Disease HCC
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC108",
        description="Vascular Disease",
        category=HCCCategory.VASCULAR,
        raf_community=0.288,
        raf_institutional=0.158,
        icd10_codes=[
            "I70.201", "I70.202", "I70.203", "I70.208", "I70.209",  # Atherosclerosis
            "I70.211", "I70.212", "I70.213", "I70.218", "I70.219",
            "I70.221", "I70.222", "I70.223", "I70.228", "I70.229",
            "I70.231", "I70.232", "I70.233", "I70.234", "I70.235",
            "I70.25", "I70.261", "I70.262", "I70.263", "I70.268",
            "I73.9",  # Peripheral vascular disease
        ],
        clinical_indicators=[
            "peripheral vascular disease", "pvd", "pad", "peripheral arterial",
            "claudication", "atherosclerosis", "arterial insufficiency",
            "abi", "ankle brachial index",
        ],
        lab_indicators=[
            {"name": "ABI", "operator": "<", "value": 0.9, "unit": "ratio"},
        ],
        documentation_requirements=[
            "PVD/PAD explicitly documented",
            "Severity/stage if known",
            "Affected vessels if known",
        ],
    ),

    # -------------------------------------------------------------------------
    # Rheumatoid Arthritis HCC
    # -------------------------------------------------------------------------
    HCCDefinition(
        hcc_code="HCC40",
        description="Rheumatoid Arthritis and Inflammatory Connective Tissue Disease",
        category=HCCCategory.IMMUNE,
        raf_community=0.374,
        raf_institutional=0.257,
        icd10_codes=[
            "M05.00", "M05.011", "M05.012", "M05.019",  # RA with rheumatoid factor
            "M05.10", "M05.111", "M05.112", "M05.119",  # RA with lung involvement
            "M05.20", "M05.211", "M05.212", "M05.219",  # Rheumatoid vasculitis
            "M05.30", "M05.311", "M05.312", "M05.319",  # RA with heart involvement
            "M06.00", "M06.011", "M06.012", "M06.019",  # RA without rheumatoid factor
            "M32.0", "M32.10", "M32.11", "M32.12", "M32.13", "M32.14", "M32.15",  # SLE
        ],
        clinical_indicators=[
            "rheumatoid arthritis", "ra ", "systemic lupus", "sle",
            "seropositive ra", "seronegative ra", "lupus", "inflammatory arthritis",
        ],
        lab_indicators=[
            {"name": "RF", "operator": ">", "value": 14, "unit": "IU/mL"},
            {"name": "anti_CCP", "operator": ">", "value": 20, "unit": "U/mL"},
            {"name": "ANA", "operator": "positive", "value": 1, "unit": "titer"},
        ],
        documentation_requirements=[
            "Specific type of inflammatory arthritis",
            "Seropositive vs seronegative for RA",
            "Organ involvement if present",
        ],
    ),
]

# Build lookup indexes
HCC_BY_CODE: dict[str, HCCDefinition] = {hcc.hcc_code: hcc for hcc in HCC_DEFINITIONS}
ICD10_TO_HCC: dict[str, str] = {}
for hcc in HCC_DEFINITIONS:
    for icd10 in hcc.icd10_codes:
        ICD10_TO_HCC[icd10] = hcc.hcc_code


# ============================================================================
# HCC Revenue Recovery Service
# ============================================================================

# Average per-member-per-month payment (approximate for 2024)
# Actual varies by plan, geography, etc.
PMPM_PAYMENT = 1200.00  # $1,200/month = $14,400/year per 1.0 RAF


class HCCAnalyzerService:
    """Service for HCC revenue recovery analysis."""

    def __init__(self):
        """Initialize the service."""
        self._hcc_definitions = HCC_DEFINITIONS
        self._hcc_by_code = HCC_BY_CODE
        self._icd10_to_hcc = ICD10_TO_HCC
        self._pmpm_payment = PMPM_PAYMENT
        logger.info(f"HCCAnalyzerService initialized with {len(self._hcc_definitions)} HCC definitions")

    def analyze_patient(
        self,
        clinical_text: str,
        current_icd10_codes: list[str] | None = None,
        lab_values: list[dict[str, Any]] | None = None,
        patient_context: dict[str, Any] | None = None,
    ) -> HCCAnalysisResult:
        """Analyze a patient for HCC revenue opportunities.

        Args:
            clinical_text: Clinical documentation (notes, H&P, etc.)
            current_icd10_codes: Currently coded ICD-10 codes for this patient
            lab_values: Lab results (optional, enhances analysis)
            patient_context: Patient demographics and context

        Returns:
            HCCAnalysisResult with opportunities and financial impact
        """
        import time
        start_time = time.perf_counter()

        current_icd10_codes = current_icd10_codes or []
        lab_values = lab_values or []
        patient_context = patient_context or {}

        # Determine setting for RAF selection
        is_institutional = patient_context.get("setting") == "institutional"

        # Step 1: Identify current HCCs from coded diagnoses
        current_hccs = self._get_hccs_from_icd10_codes(current_icd10_codes)
        current_raf = self._calculate_raf(current_hccs, is_institutional)

        # Step 2: Scan documentation for HCC opportunities
        opportunities = self._find_opportunities(
            clinical_text=clinical_text,
            current_icd10_codes=current_icd10_codes,
            current_hccs=current_hccs,
            lab_values=lab_values,
            is_institutional=is_institutional,
            patient_context=patient_context,
        )

        # Step 3: Calculate projected state
        projected_hccs = list(current_hccs)
        for opp in opportunities:
            if opp.hcc_code not in projected_hccs:
                projected_hccs.append(opp.hcc_code)
        projected_raf = self._calculate_raf(projected_hccs, is_institutional)

        # Step 4: Calculate financial impact
        total_raf_opportunity = projected_raf - current_raf
        total_estimated_revenue = total_raf_opportunity * self._pmpm_payment * 12  # Annual

        high_conf_opps = [o for o in opportunities if o.capture_confidence == CaptureConfidence.HIGH]
        high_confidence_revenue = sum(o.estimated_revenue for o in high_conf_opps)

        # Step 5: Build statistics
        by_category = {}
        by_gap_type = {}
        by_confidence = {}
        for opp in opportunities:
            cat = opp.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            gap = opp.gap_type.value
            by_gap_type[gap] = by_gap_type.get(gap, 0) + 1

            conf = opp.capture_confidence.value
            by_confidence[conf] = by_confidence.get(conf, 0) + 1

        # Step 6: Generate priority actions
        priority_actions = self._generate_priority_actions(opportunities)

        analysis_time_ms = (time.perf_counter() - start_time) * 1000

        return HCCAnalysisResult(
            opportunities=opportunities,
            total_opportunities=len(opportunities),
            total_raf_opportunity=round(total_raf_opportunity, 3),
            total_estimated_revenue=round(total_estimated_revenue, 2),
            high_confidence_revenue=round(high_confidence_revenue, 2),
            by_category=by_category,
            by_gap_type=by_gap_type,
            by_confidence=by_confidence,
            current_hccs=current_hccs,
            current_raf_score=round(current_raf, 3),
            projected_hccs=projected_hccs,
            projected_raf_score=round(projected_raf, 3),
            priority_actions=priority_actions,
            analysis_date=datetime.now(timezone.utc).isoformat(),
            analysis_time_ms=round(analysis_time_ms, 2),
        )

    def _get_hccs_from_icd10_codes(self, icd10_codes: list[str]) -> list[str]:
        """Map ICD-10 codes to HCC categories."""
        hccs = set()
        for code in icd10_codes:
            # Try exact match
            if code in self._icd10_to_hcc:
                hccs.add(self._icd10_to_hcc[code])
            else:
                # Try prefix match (e.g., E11.65 matches E11)
                for icd10, hcc in self._icd10_to_hcc.items():
                    if code.startswith(icd10.split('.')[0]):
                        # Check if the specific code maps
                        pass  # Keep strict matching for now
        return list(hccs)

    def _calculate_raf(self, hcc_codes: list[str], is_institutional: bool) -> float:
        """Calculate RAF score from HCC codes.

        Note: This is a simplified calculation. Real RAF includes:
        - Demographic factors (age, sex, Medicaid status)
        - HCC interactions
        - Disease hierarchy (some HCCs supersede others)
        """
        raf = 0.0
        for hcc_code in hcc_codes:
            if hcc_code in self._hcc_by_code:
                hcc = self._hcc_by_code[hcc_code]
                if is_institutional:
                    raf += hcc.raf_institutional
                else:
                    raf += hcc.raf_community
        return raf

    def _find_opportunities(
        self,
        clinical_text: str,
        current_icd10_codes: list[str],
        current_hccs: list[str],
        lab_values: list[dict[str, Any]],
        is_institutional: bool,
        patient_context: dict[str, Any],
    ) -> list[HCCOpportunity]:
        """Find HCC coding opportunities in clinical documentation."""
        opportunities = []
        text_lower = clinical_text.lower()

        for hcc_def in self._hcc_definitions:
            # Skip if already captured
            if hcc_def.hcc_code in current_hccs:
                continue

            # Check clinical indicators in text
            evidence_list = []
            matched_indicators = []

            for indicator in hcc_def.clinical_indicators:
                if indicator in text_lower:
                    matched_indicators.append(indicator)
                    # Extract context around the indicator
                    context = self._extract_evidence_context(clinical_text, indicator)
                    evidence_list.append(HCCEvidence(
                        source_type="note",
                        source_text=context,
                        confidence=0.8,
                    ))

            # Check lab values
            lab_evidence = self._check_lab_indicators(lab_values, hcc_def.lab_indicators)
            evidence_list.extend(lab_evidence)

            # If we found evidence, create an opportunity
            if evidence_list:
                # Determine gap type
                gap_type = self._determine_gap_type(
                    hcc_def, current_icd10_codes, matched_indicators
                )

                # Determine confidence
                confidence = self._determine_confidence(
                    evidence_list, matched_indicators, hcc_def
                )

                # Calculate revenue
                raf_value = hcc_def.raf_institutional if is_institutional else hcc_def.raf_community
                estimated_revenue = raf_value * self._pmpm_payment * 12

                # Find recommended ICD-10
                recommended_icd10 = self._recommend_icd10(hcc_def, matched_indicators, text_lower)

                opportunity = HCCOpportunity(
                    hcc_code=hcc_def.hcc_code,
                    hcc_description=hcc_def.description,
                    category=hcc_def.category,
                    gap_type=gap_type,
                    capture_confidence=confidence,
                    raf_value=raf_value,
                    estimated_revenue=round(estimated_revenue, 2),
                    evidence=evidence_list,
                    supporting_icd10_codes=hcc_def.icd10_codes[:5],  # Top 5
                    recommended_icd10=recommended_icd10,
                    documentation_needed=hcc_def.documentation_requirements,
                    coder_notes=self._generate_coder_notes(hcc_def, matched_indicators, gap_type),
                    patient_id=patient_context.get("patient_id"),
                    encounter_id=patient_context.get("encounter_id"),
                )
                opportunities.append(opportunity)

        # Sort by revenue impact (descending)
        opportunities.sort(key=lambda o: o.estimated_revenue, reverse=True)

        return opportunities

    def _extract_evidence_context(self, text: str, indicator: str, window: int = 100) -> str:
        """Extract text context around an indicator."""
        text_lower = text.lower()
        pos = text_lower.find(indicator)
        if pos == -1:
            return ""

        start = max(0, pos - window)
        end = min(len(text), pos + len(indicator) + window)

        context = text[start:end].strip()
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."

        return context

    def _check_lab_indicators(
        self,
        lab_values: list[dict[str, Any]],
        lab_indicators: list[dict[str, Any]]
    ) -> list[HCCEvidence]:
        """Check if lab values support an HCC."""
        evidence = []

        for indicator in lab_indicators:
            lab_name = indicator.get("name", "").lower()
            operator = indicator.get("operator", "")
            threshold = indicator.get("value", 0)
            unit = indicator.get("unit", "")

            for lab in lab_values:
                if lab.get("name", "").lower() == lab_name:
                    value = lab.get("value", 0)
                    try:
                        value = float(value)
                        meets_criteria = False

                        if operator == ">" and value > threshold:
                            meets_criteria = True
                        elif operator == ">=" and value >= threshold:
                            meets_criteria = True
                        elif operator == "<" and value < threshold:
                            meets_criteria = True
                        elif operator == "<=" and value <= threshold:
                            meets_criteria = True
                        elif operator == "positive" and value:
                            meets_criteria = True

                        if meets_criteria:
                            evidence.append(HCCEvidence(
                                source_type="lab",
                                source_text=f"{lab_name}: {value} {unit} (threshold: {operator}{threshold})",
                                source_date=lab.get("date"),
                                confidence=0.9,
                            ))
                    except (ValueError, TypeError):
                        pass

        return evidence

    def _determine_gap_type(
        self,
        hcc_def: HCCDefinition,
        current_icd10_codes: list[str],
        matched_indicators: list[str]
    ) -> GapType:
        """Determine the type of HCC gap."""
        # Check if there's a less specific code already present
        for code in current_icd10_codes:
            # Check if current code is in same family but not HCC-specific
            for hcc_code in hcc_def.icd10_codes:
                if code.startswith(hcc_code[:3]) and code not in hcc_def.icd10_codes:
                    return GapType.NEEDS_SPECIFICITY

        # If we have lab evidence but no clinical mentions, it's a suspect
        if not matched_indicators:
            return GapType.SUSPECT

        # Otherwise it's documented but not coded
        return GapType.NOT_CODED

    def _determine_confidence(
        self,
        evidence: list[HCCEvidence],
        matched_indicators: list[str],
        hcc_def: HCCDefinition
    ) -> CaptureConfidence:
        """Determine confidence that this HCC can be captured."""
        # High confidence: multiple evidence sources or explicit documentation
        if len(evidence) >= 2 and len(matched_indicators) >= 2:
            return CaptureConfidence.HIGH

        # Check for explicit diagnosis language
        explicit_terms = ["diagnosed", "history of", "known", "established"]
        for ev in evidence:
            if any(term in ev.source_text.lower() for term in explicit_terms):
                return CaptureConfidence.HIGH

        # Medium: some evidence
        if evidence and matched_indicators:
            return CaptureConfidence.MEDIUM

        # Low: minimal evidence
        return CaptureConfidence.LOW

    def _recommend_icd10(
        self,
        hcc_def: HCCDefinition,
        matched_indicators: list[str],
        text_lower: str
    ) -> str | None:
        """Recommend the most appropriate ICD-10 code."""
        if not hcc_def.icd10_codes:
            return None

        # For now, return the first applicable code
        # A more sophisticated version would analyze the text for specificity
        return hcc_def.icd10_codes[0]

    def _generate_coder_notes(
        self,
        hcc_def: HCCDefinition,
        matched_indicators: list[str],
        gap_type: GapType
    ) -> str:
        """Generate notes for the coder."""
        notes = []

        if gap_type == GapType.NOT_CODED:
            notes.append(f"Documentation supports {hcc_def.description} but not currently coded.")
        elif gap_type == GapType.NEEDS_SPECIFICITY:
            notes.append("Current code lacks specificity for HCC capture. Review for more specific code.")
        elif gap_type == GapType.SUSPECT:
            notes.append("Lab values suggest this condition. Query provider for confirmation.")

        if matched_indicators:
            notes.append(f"Key terms found: {', '.join(matched_indicators[:3])}")

        if hcc_def.documentation_requirements:
            notes.append(f"Ensure documentation includes: {', '.join(hcc_def.documentation_requirements[:2])}")

        return " ".join(notes)

    def _generate_priority_actions(self, opportunities: list[HCCOpportunity]) -> list[str]:
        """Generate prioritized action items."""
        actions = []

        # High confidence, high value first
        high_value = [o for o in opportunities if o.capture_confidence == CaptureConfidence.HIGH]
        high_value.sort(key=lambda o: o.estimated_revenue, reverse=True)

        for opp in high_value[:3]:
            actions.append(
                f"[HIGH PRIORITY] Code {opp.hcc_code} ({opp.hcc_description}): "
                f"${opp.estimated_revenue:,.0f} annual opportunity. {opp.coder_notes}"
            )

        # Medium confidence
        medium = [o for o in opportunities if o.capture_confidence == CaptureConfidence.MEDIUM]
        for opp in medium[:2]:
            actions.append(
                f"[MEDIUM] Review {opp.hcc_code}: May need provider query. "
                f"${opp.estimated_revenue:,.0f} potential."
            )

        return actions

    def get_hcc_definition(self, hcc_code: str) -> HCCDefinition | None:
        """Get definition for a specific HCC code."""
        return self._hcc_by_code.get(hcc_code)

    def get_all_hcc_codes(self) -> list[str]:
        """Get all HCC codes in the model."""
        return list(self._hcc_by_code.keys())

    def get_icd10_to_hcc_mapping(self, icd10_code: str) -> str | None:
        """Get the HCC for an ICD-10 code."""
        return self._icd10_to_hcc.get(icd10_code)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        categories = {}
        for hcc in self._hcc_definitions:
            cat = hcc.category.value
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_hcc_definitions": len(self._hcc_definitions),
            "total_icd10_mappings": len(self._icd10_to_hcc),
            "by_category": categories,
            "pmpm_payment": self._pmpm_payment,
        }


# Singleton pattern
_service_instance: HCCAnalyzerService | None = None
_service_lock = threading.Lock()


def get_hcc_analyzer_service() -> HCCAnalyzerService:
    """Get singleton instance of HCCAnalyzerService."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = HCCAnalyzerService()
    return _service_instance


def reset_hcc_analyzer_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
