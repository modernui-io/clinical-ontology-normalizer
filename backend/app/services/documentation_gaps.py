"""
Documentation Gap Detection Service.

Analyzes clinical documentation to identify:
1. Ambiguous terms that need clarification
2. Missing required information for coding
3. Incomplete documentation for quality measures
4. Specificity opportunities for more accurate coding

Generates structured queries for providers/coders.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GapSeverity(Enum):
    """Severity of documentation gap."""
    CRITICAL = "critical"  # Blocks coding/billing
    HIGH = "high"  # Significantly impacts accuracy
    MEDIUM = "medium"  # Affects specificity
    LOW = "low"  # Nice to have


class GapCategory(Enum):
    """Category of documentation gap."""
    SPECIFICITY = "specificity"  # Need more specific diagnosis
    LATERALITY = "laterality"  # Left/right/bilateral not specified
    ACUITY = "acuity"  # Acute/chronic not specified
    CAUSATION = "causation"  # Underlying cause not documented
    TEMPORALITY = "temporality"  # When did it start/occur
    SEVERITY = "severity"  # Mild/moderate/severe not specified
    EPISODE = "episode"  # Initial/subsequent encounter
    COMPLICATIONS = "complications"  # Complications not documented
    CONTROL_STATUS = "control_status"  # Controlled/uncontrolled
    STAGE = "stage"  # Disease stage not specified
    TYPE = "type"  # Type 1 vs Type 2, etc.
    LOCATION = "location"  # Anatomical location
    PROCEDURE_DETAILS = "procedure_details"  # Missing procedure specifics
    MEDICAL_NECESSITY = "medical_necessity"  # Why was service needed


@dataclass
class DocumentationGap:
    """A single documentation gap."""
    category: GapCategory
    severity: GapSeverity
    finding: str  # The ambiguous/incomplete finding
    issue: str  # Description of the gap
    query_text: str  # Suggested query for provider
    query_options: list[str]  # Possible answers
    impact: str  # Impact on coding/billing/quality
    icd10_implications: list[str]  # How this affects ICD-10 coding
    cpt_implications: list[str]  # How this affects CPT coding
    quality_implications: list[str]  # How this affects quality measures


@dataclass
class DocumentationGapResult:
    """Result of documentation gap analysis."""
    gaps: list[DocumentationGap] = field(default_factory=list)
    total_gaps: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    coding_queries: list[dict[str, Any]] = field(default_factory=list)
    estimated_revenue_at_risk: float = 0.0
    quality_measures_affected: list[str] = field(default_factory=list)
    overall_documentation_score: int = 100  # 0-100


# Gap detection rules for common conditions
SPECIFICITY_RULES: dict[str, dict[str, Any]] = {
    # Diabetes
    "diabetes": {
        "category": GapCategory.TYPE,
        "severity": GapSeverity.HIGH,
        "issue": "Diabetes type not specified",
        "query": "Is this Type 1 or Type 2 diabetes mellitus?",
        "options": ["Type 1 (E10.x)", "Type 2 (E11.x)", "Other specified (E13.x)", "Unspecified - need more info"],
        "impact": "Incorrect diabetes type affects E/M coding, quality measures (HEDIS), and risk adjustment",
        "icd10_codes": {
            "Type 1": "E10.9",
            "Type 2": "E11.9",
            "unspecified": "E11.9"  # Default to Type 2 per guidelines
        }
    },
    "dm": {
        "category": GapCategory.TYPE,
        "severity": GapSeverity.HIGH,
        "issue": "Diabetes type not specified",
        "query": "Is this Type 1 or Type 2 diabetes mellitus?",
        "options": ["Type 1 (E10.x)", "Type 2 (E11.x)", "Other specified (E13.x)"],
        "impact": "Incorrect diabetes type affects coding and quality measures"
    },

    # Diabetes complications
    "diabetic neuropathy": {
        "category": GapCategory.TYPE,
        "severity": GapSeverity.HIGH,
        "issue": "Diabetes type and neuropathy type not fully specified",
        "query": "What type of diabetic neuropathy? Type 1 or Type 2 DM?",
        "options": [
            "Type 2 with diabetic polyneuropathy (E11.42)",
            "Type 2 with diabetic mononeuropathy (E11.41)",
            "Type 1 with diabetic polyneuropathy (E10.42)",
            "Type 1 with diabetic mononeuropathy (E10.41)"
        ],
        "impact": "Specific neuropathy type required for accurate HCC coding"
    },

    # Hypertension
    "hypertension": {
        "category": GapCategory.CONTROL_STATUS,
        "severity": GapSeverity.MEDIUM,
        "issue": "Hypertension control status not documented",
        "query": "Is hypertension controlled or uncontrolled? Any target organ damage?",
        "options": [
            "Essential hypertension, controlled (I10)",
            "Hypertensive heart disease (I11.x)",
            "Hypertensive chronic kidney disease (I12.x)",
            "Hypertensive heart and CKD (I13.x)"
        ],
        "impact": "Affects quality measure reporting and risk adjustment"
    },
    "htn": {
        "category": GapCategory.CONTROL_STATUS,
        "severity": GapSeverity.MEDIUM,
        "issue": "Hypertension control status not documented",
        "query": "Is hypertension controlled or uncontrolled?",
        "options": ["Controlled", "Uncontrolled"],
        "impact": "Affects quality measure reporting"
    },

    # Heart Failure
    "heart failure": {
        "category": GapCategory.SPECIFICITY,
        "severity": GapSeverity.HIGH,
        "issue": "Heart failure type and acuity not specified",
        "query": "What type of heart failure? Acute or chronic? Systolic/diastolic?",
        "options": [
            "Systolic (HFrEF) - acute (I50.21)",
            "Systolic (HFrEF) - chronic (I50.22)",
            "Diastolic (HFpEF) - acute (I50.31)",
            "Diastolic (HFpEF) - chronic (I50.32)",
            "Combined systolic and diastolic (I50.4x)"
        ],
        "impact": "HF type significantly affects HCC risk scoring and quality measures"
    },
    "chf": {
        "category": GapCategory.SPECIFICITY,
        "severity": GapSeverity.HIGH,
        "issue": "Heart failure type not specified",
        "query": "Is this systolic (HFrEF) or diastolic (HFpEF) heart failure?",
        "options": ["Systolic/HFrEF", "Diastolic/HFpEF", "Combined", "Unspecified"],
        "impact": "HF type affects HCC risk scoring"
    },

    # CKD
    "chronic kidney disease": {
        "category": GapCategory.STAGE,
        "severity": GapSeverity.HIGH,
        "issue": "CKD stage not documented",
        "query": "What is the CKD stage (based on eGFR)?",
        "options": [
            "Stage 1 - eGFR ≥90 (N18.1)",
            "Stage 2 - eGFR 60-89 (N18.2)",
            "Stage 3a - eGFR 45-59 (N18.31)",
            "Stage 3b - eGFR 30-44 (N18.32)",
            "Stage 4 - eGFR 15-29 (N18.4)",
            "Stage 5 - eGFR <15 (N18.5)",
            "ESRD on dialysis (N18.6)"
        ],
        "impact": "CKD stage is critical for risk adjustment and medication dosing"
    },
    "ckd": {
        "category": GapCategory.STAGE,
        "severity": GapSeverity.HIGH,
        "issue": "CKD stage not documented",
        "query": "What is the CKD stage?",
        "options": ["Stage 1", "Stage 2", "Stage 3a", "Stage 3b", "Stage 4", "Stage 5", "ESRD"],
        "impact": "CKD stage affects risk adjustment and medication dosing"
    },

    # COPD
    "copd": {
        "category": GapCategory.ACUITY,
        "severity": GapSeverity.HIGH,
        "issue": "COPD acuity and exacerbation status not specified",
        "query": "Is this COPD with acute exacerbation or stable chronic COPD?",
        "options": [
            "COPD with acute exacerbation (J44.1)",
            "COPD with acute lower respiratory infection (J44.0)",
            "COPD, unspecified/stable (J44.9)"
        ],
        "impact": "Exacerbation status affects acute vs chronic coding and risk adjustment"
    },

    # Asthma
    "asthma": {
        "category": GapCategory.SEVERITY,
        "severity": GapSeverity.MEDIUM,
        "issue": "Asthma severity and exacerbation status not specified",
        "query": "What is the asthma severity? Is there an acute exacerbation?",
        "options": [
            "Mild intermittent (J45.20/J45.21)",
            "Mild persistent (J45.30/J45.31)",
            "Moderate persistent (J45.40/J45.41)",
            "Severe persistent (J45.50/J45.51)"
        ],
        "impact": "Severity classification affects quality measures and treatment guidelines"
    },

    # Chest Pain
    "chest pain": {
        "category": GapCategory.SPECIFICITY,
        "severity": GapSeverity.MEDIUM,
        "issue": "Chest pain etiology and characteristics not fully documented",
        "query": "What is the nature of the chest pain?",
        "options": [
            "Chest pain, unspecified (R07.9)",
            "Precordial pain (R07.2)",
            "Pleurodynia/pleuritic (R07.81)",
            "Musculoskeletal chest pain (R07.89)",
            "Angina pectoris (I20.x) - if cardiac"
        ],
        "impact": "Specific chest pain type affects workup coding and medical necessity"
    },

    # Anemia
    "anemia": {
        "category": GapCategory.CAUSATION,
        "severity": GapSeverity.HIGH,
        "issue": "Anemia type/cause not specified",
        "query": "What is the cause/type of anemia?",
        "options": [
            "Iron deficiency anemia (D50.x)",
            "Anemia of chronic disease (D63.x)",
            "Anemia in CKD (D63.1)",
            "Anemia in neoplastic disease (D63.0)",
            "B12 deficiency anemia (D51.x)",
            "Folate deficiency anemia (D52.x)",
            "Unspecified anemia (D64.9)"
        ],
        "impact": "Anemia type affects treatment coding and risk adjustment"
    },

    # Fractures
    "fracture": {
        "category": GapCategory.EPISODE,
        "severity": GapSeverity.CRITICAL,
        "issue": "Fracture episode of care not specified",
        "query": "Is this initial encounter, subsequent encounter, or sequela?",
        "options": [
            "Initial encounter (A)",
            "Subsequent encounter with routine healing (D)",
            "Subsequent encounter with delayed healing (G)",
            "Subsequent encounter with nonunion (K)",
            "Subsequent encounter with malunion (P)",
            "Sequela (S)"
        ],
        "impact": "Episode extension is REQUIRED for valid fracture coding - blocks billing if missing"
    },

    # Wounds
    "laceration": {
        "category": GapCategory.LOCATION,
        "severity": GapSeverity.HIGH,
        "issue": "Laceration location and laterality needed",
        "query": "What is the exact anatomical location and laterality?",
        "options": ["Right", "Left", "Bilateral", "Specify exact location"],
        "impact": "Location and laterality required for specific ICD-10 coding"
    },

    # Pain
    "pain": {
        "category": GapCategory.LOCATION,
        "severity": GapSeverity.MEDIUM,
        "issue": "Pain location not fully specified",
        "query": "What is the specific location of pain?",
        "options": ["Document specific anatomical location", "Specify if radiating", "Note if acute or chronic"],
        "impact": "Specific pain codes require anatomical location"
    },

    # Pneumonia
    "pneumonia": {
        "category": GapCategory.CAUSATION,
        "severity": GapSeverity.HIGH,
        "issue": "Pneumonia organism/type not specified",
        "query": "What is the causative organism or type of pneumonia?",
        "options": [
            "Bacterial pneumonia, organism unspecified (J15.9)",
            "Streptococcal pneumonia (J13)",
            "Staphylococcal pneumonia (J15.2)",
            "Viral pneumonia (J12.x)",
            "Aspiration pneumonia (J69.0)",
            "Healthcare-associated pneumonia (J15.9 + POA indicator)"
        ],
        "impact": "Organism-specific coding affects quality measures and antibiotic stewardship"
    },

    # UTI
    "urinary tract infection": {
        "category": GapCategory.LOCATION,
        "severity": GapSeverity.MEDIUM,
        "issue": "UTI location not specified (upper vs lower tract)",
        "query": "Is this a lower UTI (cystitis) or upper UTI (pyelonephritis)?",
        "options": [
            "Acute cystitis (N30.0x)",
            "Acute pyelonephritis (N10)",
            "UTI, site not specified (N39.0)"
        ],
        "impact": "Upper vs lower UTI affects treatment coding and severity"
    },
    "uti": {
        "category": GapCategory.LOCATION,
        "severity": GapSeverity.MEDIUM,
        "issue": "UTI location not specified",
        "query": "Is this cystitis or pyelonephritis?",
        "options": ["Cystitis (lower)", "Pyelonephritis (upper)", "Unspecified"],
        "impact": "Location affects treatment and coding"
    },

    # Stroke/CVA
    "stroke": {
        "category": GapCategory.TYPE,
        "severity": GapSeverity.CRITICAL,
        "issue": "Stroke type (ischemic vs hemorrhagic) not specified",
        "query": "Is this an ischemic stroke, hemorrhagic stroke, or TIA?",
        "options": [
            "Ischemic stroke (I63.x)",
            "Intracerebral hemorrhage (I61.x)",
            "Subarachnoid hemorrhage (I60.x)",
            "TIA (G45.x)",
            "History of stroke (Z86.73)"
        ],
        "impact": "Stroke type is critical for treatment, coding, and quality measures"
    },
    "cva": {
        "category": GapCategory.TYPE,
        "severity": GapSeverity.CRITICAL,
        "issue": "CVA type not specified",
        "query": "Is this ischemic or hemorrhagic?",
        "options": ["Ischemic", "Hemorrhagic (ICH)", "Hemorrhagic (SAH)", "TIA"],
        "impact": "Type is critical for treatment and coding"
    },

    # Cancer
    "cancer": {
        "category": GapCategory.STAGE,
        "severity": GapSeverity.HIGH,
        "issue": "Cancer type, site, and staging not fully documented",
        "query": "What is the primary site, histology, and stage?",
        "options": ["Document primary site", "Document histology/morphology", "Document stage (TNM or other)"],
        "impact": "Staging affects treatment coding, risk adjustment, and quality measures"
    },
    "malignancy": {
        "category": GapCategory.STAGE,
        "severity": GapSeverity.HIGH,
        "issue": "Malignancy details not fully documented",
        "query": "What is the primary site and current status?",
        "options": ["Active treatment", "Remission", "History of", "Metastatic"],
        "impact": "Status affects risk adjustment significantly"
    },

    # Obesity
    "obesity": {
        "category": GapCategory.SEVERITY,
        "severity": GapSeverity.MEDIUM,
        "issue": "Obesity class/BMI not documented",
        "query": "What is the BMI? Document obesity class if BMI ≥30",
        "options": [
            "Overweight (E66.3) - BMI 25-29.9",
            "Obesity class I (E66.01) - BMI 30-34.9",
            "Obesity class II (E66.01) - BMI 35-39.9",
            "Obesity class III/morbid (E66.01) - BMI ≥40"
        ],
        "impact": "BMI documentation required for obesity coding and risk adjustment"
    },

    # Depression
    "depression": {
        "category": GapCategory.SEVERITY,
        "severity": GapSeverity.MEDIUM,
        "issue": "Depression type and severity not specified",
        "query": "What type of depression? Current severity?",
        "options": [
            "Major depressive disorder, single episode (F32.x)",
            "Major depressive disorder, recurrent (F33.x)",
            "Persistent depressive disorder (F34.1)",
            "Severity: mild, moderate, severe, with/without psychotic features"
        ],
        "impact": "Depression type and severity affect quality measures and treatment coding"
    },

    # Atrial Fibrillation
    "atrial fibrillation": {
        "category": GapCategory.TYPE,
        "severity": GapSeverity.MEDIUM,
        "issue": "A-fib type not specified (paroxysmal, persistent, permanent)",
        "query": "What type of atrial fibrillation?",
        "options": [
            "Paroxysmal atrial fibrillation (I48.0)",
            "Persistent atrial fibrillation (I48.1)",
            "Chronic/permanent atrial fibrillation (I48.2)",
            "Unspecified (I48.91)"
        ],
        "impact": "A-fib type affects anticoagulation decisions and quality measures"
    },
    "afib": {
        "category": GapCategory.TYPE,
        "severity": GapSeverity.MEDIUM,
        "issue": "A-fib type not specified",
        "query": "Paroxysmal, persistent, or permanent?",
        "options": ["Paroxysmal", "Persistent", "Permanent", "Unspecified"],
        "impact": "Type affects treatment decisions"
    },
}

# Laterality rules - conditions that require left/right specification
LATERALITY_CONDITIONS: set[str] = {
    "knee pain", "hip pain", "shoulder pain", "ankle pain", "wrist pain",
    "knee replacement", "hip replacement", "cataract", "glaucoma",
    "carpal tunnel", "rotator cuff", "meniscus tear", "acl tear",
    "breast cancer", "lung cancer", "renal mass", "ovarian cyst",
    "pneumothorax", "pleural effusion", "dvt", "deep vein thrombosis"
}


class DocumentationGapDetector:
    """
    Detects documentation gaps in clinical text.

    Identifies ambiguous terms, missing specificity, and generates
    structured queries for providers/coders to clarify.
    """

    def __init__(self) -> None:
        self.specificity_rules = SPECIFICITY_RULES
        self.laterality_conditions = LATERALITY_CONDITIONS

    def analyze(
        self,
        extracted_mentions: list[dict[str, Any]],
        clinical_text: str | None = None,
        check_laterality: bool = True,
        check_episode: bool = True,
        check_medical_necessity: bool = True,
    ) -> DocumentationGapResult:
        """
        Analyze extracted mentions for documentation gaps.

        Args:
            extracted_mentions: List of NLP-extracted clinical mentions
            clinical_text: Original clinical text (optional, for context)
            check_laterality: Check for missing laterality
            check_episode: Check for missing episode of care
            check_medical_necessity: Check for medical necessity gaps

        Returns:
            DocumentationGapResult with identified gaps and queries
        """
        gaps: list[DocumentationGap] = []
        text_lower = (clinical_text or "").lower()

        for mention in extracted_mentions:
            mention_text = mention.get("text", "").lower()
            domain = mention.get("domain", "")

            # Check specificity rules
            for trigger, rule in self.specificity_rules.items():
                if trigger in mention_text:
                    # Check if already specific enough
                    if not self._is_already_specific(mention_text, trigger, text_lower):
                        gap = DocumentationGap(
                            category=rule["category"],
                            severity=rule["severity"],
                            finding=mention.get("text", trigger),
                            issue=rule["issue"],
                            query_text=rule["query"],
                            query_options=rule["options"],
                            impact=rule["impact"],
                            icd10_implications=rule.get("icd10_codes", {}).values() if isinstance(rule.get("icd10_codes"), dict) else [],
                            cpt_implications=[],
                            quality_implications=[]
                        )
                        gaps.append(gap)
                        break

            # Check laterality for applicable conditions
            if check_laterality:
                for condition in self.laterality_conditions:
                    if condition in mention_text:
                        if not self._has_laterality(mention_text, text_lower):
                            gap = DocumentationGap(
                                category=GapCategory.LATERALITY,
                                severity=GapSeverity.HIGH,
                                finding=mention.get("text", condition),
                                issue=f"Laterality not specified for {condition}",
                                query_text=f"Is this {condition} on the left, right, or bilateral?",
                                query_options=["Left", "Right", "Bilateral"],
                                impact="Laterality is REQUIRED for valid ICD-10 coding of this condition",
                                icd10_implications=["Code cannot be assigned without laterality"],
                                cpt_implications=["Procedure codes require laterality modifier"],
                                quality_implications=[]
                            )
                            gaps.append(gap)
                            break

        # Build result
        result = DocumentationGapResult(
            gaps=gaps,
            total_gaps=len(gaps),
            by_severity=self._count_by_severity(gaps),
            by_category=self._count_by_category(gaps),
            coding_queries=self._build_coding_queries(gaps),
            estimated_revenue_at_risk=self._estimate_revenue_impact(gaps),
            quality_measures_affected=self._get_affected_quality_measures(gaps),
            overall_documentation_score=self._calculate_doc_score(gaps)
        )

        return result

    def _is_already_specific(self, mention: str, trigger: str, full_text: str) -> bool:
        """Check if the mention is already specific enough."""
        # Check for type specifications
        if trigger in ["diabetes", "dm"]:
            if any(x in mention or x in full_text for x in ["type 1", "type 2", "t1dm", "t2dm", "type i", "type ii"]):
                return True

        if trigger == "hypertension":
            if any(x in full_text for x in ["controlled", "uncontrolled", "benign", "malignant"]):
                return True

        if trigger in ["heart failure", "chf"]:
            if any(x in full_text for x in ["systolic", "diastolic", "hfref", "hfpef", "preserved", "reduced"]):
                return True

        if trigger in ["ckd", "chronic kidney disease"]:
            if any(x in full_text for x in ["stage 1", "stage 2", "stage 3", "stage 4", "stage 5", "esrd", "g1", "g2", "g3", "g4", "g5"]):
                return True

        return False

    def _has_laterality(self, mention: str, full_text: str) -> bool:
        """Check if laterality is documented."""
        laterality_terms = ["left", "right", "bilateral", "unilateral", "l ", "r ", " l.", " r."]
        return any(term in mention or term in full_text for term in laterality_terms)

    def _count_by_severity(self, gaps: list[DocumentationGap]) -> dict[str, int]:
        """Count gaps by severity."""
        counts: dict[str, int] = {}
        for gap in gaps:
            key = gap.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_category(self, gaps: list[DocumentationGap]) -> dict[str, int]:
        """Count gaps by category."""
        counts: dict[str, int] = {}
        for gap in gaps:
            key = gap.category.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _build_coding_queries(self, gaps: list[DocumentationGap]) -> list[dict[str, Any]]:
        """Build structured coding queries from gaps."""
        queries = []
        for i, gap in enumerate(gaps, 1):
            queries.append({
                "query_id": f"CDI-{i:03d}",
                "priority": gap.severity.value,
                "category": gap.category.value,
                "finding": gap.finding,
                "question": gap.query_text,
                "response_options": gap.query_options,
                "impact_statement": gap.impact,
                "status": "pending"
            })
        return queries

    def _estimate_revenue_impact(self, gaps: list[DocumentationGap]) -> float:
        """Estimate potential revenue at risk from documentation gaps."""
        # Rough estimates based on severity
        impact = 0.0
        for gap in gaps:
            if gap.severity == GapSeverity.CRITICAL:
                impact += 500.0  # Critical gaps can block billing entirely
            elif gap.severity == GapSeverity.HIGH:
                impact += 150.0  # High severity affects HCC/risk adjustment
            elif gap.severity == GapSeverity.MEDIUM:
                impact += 50.0
            else:
                impact += 10.0
        return impact

    def _get_affected_quality_measures(self, gaps: list[DocumentationGap]) -> list[str]:
        """Identify quality measures affected by documentation gaps."""
        measures = set()
        for gap in gaps:
            if "diabetes" in gap.finding.lower():
                measures.add("HEDIS Diabetes Care")
                measures.add("HbA1c Control")
            if "hypertension" in gap.finding.lower():
                measures.add("Controlling High Blood Pressure")
            if "heart failure" in gap.finding.lower():
                measures.add("Heart Failure ACE/ARB Therapy")
            if "depression" in gap.finding.lower():
                measures.add("PHQ-9 Depression Screening")
            if "cancer" in gap.finding.lower() or "malignancy" in gap.finding.lower():
                measures.add("Cancer Screening Measures")
        return list(measures)

    def _calculate_doc_score(self, gaps: list[DocumentationGap]) -> int:
        """Calculate overall documentation quality score."""
        if not gaps:
            return 100

        # Deduct points based on severity
        deductions = 0
        for gap in gaps:
            if gap.severity == GapSeverity.CRITICAL:
                deductions += 25
            elif gap.severity == GapSeverity.HIGH:
                deductions += 15
            elif gap.severity == GapSeverity.MEDIUM:
                deductions += 8
            else:
                deductions += 3

        return max(0, 100 - deductions)


# Singleton instance
_detector: DocumentationGapDetector | None = None


def get_documentation_gap_detector() -> DocumentationGapDetector:
    """Get or create documentation gap detector singleton."""
    global _detector
    if _detector is None:
        _detector = DocumentationGapDetector()
    return _detector
