"""Coding Query Generator Service.

Generates structured queries for Clinical Documentation Improvement (CDI).
These queries are designed to be sent to providers for clarification
of ambiguous or incomplete clinical documentation.

Features:
- Integration with DocumentationGapDetector for gap identification
- CER (Claim-Evidence-Reasoning) citations for each query
- Priority-based query ordering (critical, high, medium, low)
- Specialty-specific query templates
- Query tracking and status management
- Estimated revenue impact calculation
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Any
import uuid

from app.services.documentation_gaps import (
    DocumentationGap,
    DocumentationGapDetector,
    DocumentationGapResult,
    GapCategory,
    GapSeverity,
    get_documentation_gap_detector,
)

logger = logging.getLogger(__name__)


class QueryStatus(Enum):
    """Status of a coding query."""

    PENDING = "pending"  # Not yet sent
    SENT = "sent"  # Sent to provider
    RESPONDED = "responded"  # Provider responded
    RESOLVED = "resolved"  # Query resolved, code assigned
    CANCELLED = "cancelled"  # Query cancelled
    EXPIRED = "expired"  # No response within timeframe


class QueryPriority(Enum):
    """Priority level for queries - affects routing and urgency."""

    STAT = "stat"  # Immediate response needed (billing blocked)
    URGENT = "urgent"  # Response needed within 24 hours
    ROUTINE = "routine"  # Response needed within 3 days
    DEFERRED = "deferred"  # Can wait for next encounter


class CodingImpact(Enum):
    """Type of coding impact from the query."""

    DRG_CHANGE = "drg_change"  # Could change DRG
    CC_MCC = "cc_mcc"  # Complication/Comorbidity impact
    HCC = "hcc"  # Hierarchical Condition Category (risk adjustment)
    QUALITY = "quality"  # Quality measure impact
    MEDICAL_NECESSITY = "medical_necessity"  # Supports medical necessity
    SPECIFICITY = "specificity"  # Improves code specificity only


@dataclass
class CERCitation:
    """Claim-Evidence-Reasoning citation for query justification."""

    claim: str  # What we're asserting (e.g., "Type specification required")
    evidence: list[str]  # Documentation excerpts supporting the claim
    reasoning: str  # Why this matters for coding
    strength: str  # HIGH, MEDIUM, LOW
    regulatory_basis: list[str] = field(default_factory=list)  # Guidelines, rules
    coding_references: list[str] = field(default_factory=list)  # ICD-10-CM, CPT refs


@dataclass
class ResponseOption:
    """A possible response option for a coding query."""

    label: str  # Display label (e.g., "Type 1 Diabetes")
    value: str  # Value to store (e.g., "type_1")
    icd10_code: str | None = None  # Resulting ICD-10 code if selected
    cpt_code: str | None = None  # Resulting CPT code if selected
    additional_queries: list[str] = field(default_factory=list)  # Follow-up queries


@dataclass
class CodingQuery:
    """A structured coding query for provider clarification."""

    # Required fields (no defaults) first
    query_id: str  # Unique identifier (e.g., "CDI-2024-001234")
    priority: QueryPriority
    status: QueryStatus
    question: str  # The question to ask
    clinical_context: str  # Relevant documentation excerpt
    response_options: list[ResponseOption]
    gap_category: GapCategory
    gap_severity: GapSeverity
    finding: str  # The ambiguous finding

    # Optional fields with defaults
    allows_free_text: bool = True

    # Impact information
    coding_impacts: list[CodingImpact] = field(default_factory=list)
    affected_icd10_codes: list[str] = field(default_factory=list)
    affected_cpt_codes: list[str] = field(default_factory=list)
    estimated_revenue_impact: float = 0.0
    quality_measures_affected: list[str] = field(default_factory=list)

    # CER Citation
    cer_citation: CERCitation | None = None

    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: datetime | None = None
    responded_at: datetime | None = None
    response_value: str | None = None
    response_notes: str | None = None

    # Metadata
    encounter_id: str | None = None
    patient_id: str | None = None
    provider_id: str | None = None
    coder_id: str | None = None


@dataclass
class QueryBatch:
    """A batch of queries for a single encounter/document."""

    batch_id: str
    encounter_id: str | None = None
    patient_id: str | None = None
    document_id: str | None = None

    queries: list[CodingQuery] = field(default_factory=list)
    total_queries: int = 0

    # Summary statistics
    by_priority: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)

    # Impact summary
    total_estimated_revenue_impact: float = 0.0
    drg_impact_possible: bool = False
    hcc_impact_possible: bool = False
    quality_measures_at_risk: list[str] = field(default_factory=list)

    # Documentation score
    documentation_score: int = 100

    # Timing
    created_at: datetime = field(default_factory=datetime.now)


# Query templates for common clinical scenarios
QUERY_TEMPLATES: dict[str, dict[str, Any]] = {
    # Diabetes queries
    "diabetes_type": {
        "question": "Please specify the type of diabetes mellitus:",
        "response_options": [
            ResponseOption(
                label="Type 1 Diabetes Mellitus",
                value="type_1",
                icd10_code="E10.9",
                additional_queries=["diabetes_complications"]
            ),
            ResponseOption(
                label="Type 2 Diabetes Mellitus",
                value="type_2",
                icd10_code="E11.9",
                additional_queries=["diabetes_complications", "diabetes_control"]
            ),
            ResponseOption(
                label="Secondary Diabetes (due to underlying condition)",
                value="secondary",
                icd10_code="E13.9",
                additional_queries=["diabetes_etiology"]
            ),
            ResponseOption(
                label="Gestational Diabetes",
                value="gestational",
                icd10_code="O24.419",
            ),
        ],
        "coding_impacts": [CodingImpact.HCC, CodingImpact.QUALITY],
        "regulatory_basis": [
            "ICD-10-CM Official Guidelines Section I.A.13",
            "HEDIS Comprehensive Diabetes Care measures"
        ],
    },
    "diabetes_complications": {
        "question": "Does the patient have any diabetes-related complications?",
        "response_options": [
            ResponseOption(label="Diabetic nephropathy/CKD", value="nephropathy", icd10_code="E11.22"),
            ResponseOption(label="Diabetic neuropathy", value="neuropathy", icd10_code="E11.40"),
            ResponseOption(label="Diabetic retinopathy", value="retinopathy", icd10_code="E11.319"),
            ResponseOption(label="Peripheral vascular disease", value="pvd", icd10_code="E11.51"),
            ResponseOption(label="No documented complications", value="none"),
        ],
        "coding_impacts": [CodingImpact.HCC, CodingImpact.CC_MCC],
        "regulatory_basis": ["ICD-10-CM Official Guidelines Section I.A.13.d"],
    },
    "diabetes_control": {
        "question": "Is the diabetes currently controlled or uncontrolled?",
        "response_options": [
            ResponseOption(label="Well controlled (A1c at goal)", value="controlled"),
            ResponseOption(label="Uncontrolled/with hyperglycemia", value="uncontrolled", icd10_code="E11.65"),
            ResponseOption(label="With hypoglycemia", value="hypoglycemia", icd10_code="E11.649"),
        ],
        "coding_impacts": [CodingImpact.QUALITY, CodingImpact.SPECIFICITY],
        "regulatory_basis": ["HEDIS HbA1c Control measures"],
    },

    # Heart failure queries
    "heart_failure_type": {
        "question": "Please specify the type of heart failure:",
        "response_options": [
            ResponseOption(
                label="Heart Failure with Reduced Ejection Fraction (HFrEF)",
                value="hfref",
                icd10_code="I50.20",
                additional_queries=["heart_failure_acuity"]
            ),
            ResponseOption(
                label="Heart Failure with Preserved Ejection Fraction (HFpEF)",
                value="hfpef",
                icd10_code="I50.30",
                additional_queries=["heart_failure_acuity"]
            ),
            ResponseOption(
                label="Combined Systolic and Diastolic",
                value="combined",
                icd10_code="I50.40",
            ),
            ResponseOption(
                label="Type unspecified - need echocardiogram",
                value="unspecified",
                icd10_code="I50.9",
            ),
        ],
        "coding_impacts": [CodingImpact.CC_MCC, CodingImpact.HCC, CodingImpact.DRG_CHANGE],
        "regulatory_basis": [
            "ICD-10-CM Official Guidelines Section I.C.9.a",
            "CMS HCC Risk Adjustment Model"
        ],
    },
    "heart_failure_acuity": {
        "question": "Is this heart failure acute, chronic, or acute-on-chronic?",
        "response_options": [
            ResponseOption(label="Acute (new onset or decompensation)", value="acute", icd10_code="I50.21"),
            ResponseOption(label="Chronic (stable)", value="chronic", icd10_code="I50.22"),
            ResponseOption(label="Acute on Chronic (exacerbation of chronic HF)", value="acute_on_chronic", icd10_code="I50.23"),
        ],
        "coding_impacts": [CodingImpact.CC_MCC, CodingImpact.DRG_CHANGE],
        "regulatory_basis": ["ICD-10-CM Section I.C.9.a.1"],
    },

    # CKD queries
    "ckd_stage": {
        "question": "What is the stage of chronic kidney disease?",
        "response_options": [
            ResponseOption(label="Stage 1 (GFR ≥90)", value="stage1", icd10_code="N18.1"),
            ResponseOption(label="Stage 2 (GFR 60-89)", value="stage2", icd10_code="N18.2"),
            ResponseOption(label="Stage 3a (GFR 45-59)", value="stage3a", icd10_code="N18.31"),
            ResponseOption(label="Stage 3b (GFR 30-44)", value="stage3b", icd10_code="N18.32"),
            ResponseOption(label="Stage 4 (GFR 15-29)", value="stage4", icd10_code="N18.4"),
            ResponseOption(label="Stage 5/ESRD (GFR <15)", value="stage5", icd10_code="N18.5"),
        ],
        "coding_impacts": [CodingImpact.HCC, CodingImpact.CC_MCC],
        "regulatory_basis": [
            "ICD-10-CM Official Guidelines Section I.C.14.a",
            "KDIGO CKD Classification Guidelines"
        ],
    },

    # Hypertension queries
    "hypertension_control": {
        "question": "Is the hypertension currently controlled or uncontrolled?",
        "response_options": [
            ResponseOption(label="Controlled (at BP goal)", value="controlled", icd10_code="I10"),
            ResponseOption(label="Uncontrolled/Inadequately controlled", value="uncontrolled", icd10_code="I10"),
            ResponseOption(label="Hypertensive urgency (severely elevated)", value="urgency", icd10_code="I16.0"),
            ResponseOption(label="Hypertensive crisis/emergency", value="crisis", icd10_code="I16.1"),
        ],
        "coding_impacts": [CodingImpact.QUALITY, CodingImpact.SPECIFICITY],
        "regulatory_basis": ["Controlling High Blood Pressure (NQF 0018)"],
    },

    # Fracture queries
    "fracture_episode": {
        "question": "What is the episode of care for this fracture?",
        "response_options": [
            ResponseOption(label="Initial encounter (active treatment)", value="initial"),
            ResponseOption(label="Subsequent encounter (routine healing)", value="subsequent"),
            ResponseOption(label="Subsequent - delayed healing", value="delayed"),
            ResponseOption(label="Subsequent - nonunion", value="nonunion"),
            ResponseOption(label="Subsequent - malunion", value="malunion"),
            ResponseOption(label="Sequela (late effect)", value="sequela"),
        ],
        "coding_impacts": [CodingImpact.SPECIFICITY],
        "regulatory_basis": ["ICD-10-CM Official Guidelines Section I.C.19.c"],
    },

    # Laterality queries
    "laterality": {
        "question": "Please specify the laterality (side) of this condition:",
        "response_options": [
            ResponseOption(label="Right", value="right"),
            ResponseOption(label="Left", value="left"),
            ResponseOption(label="Bilateral", value="bilateral"),
        ],
        "coding_impacts": [CodingImpact.SPECIFICITY],
        "regulatory_basis": ["ICD-10-CM Official Guidelines Section I.B.13"],
    },

    # Stroke queries
    "stroke_type": {
        "question": "Please specify the type of stroke/CVA:",
        "response_options": [
            ResponseOption(label="Ischemic stroke (cerebral infarction)", value="ischemic", icd10_code="I63.9"),
            ResponseOption(label="Hemorrhagic stroke - intracerebral", value="hemorrhagic_ich", icd10_code="I61.9"),
            ResponseOption(label="Hemorrhagic stroke - subarachnoid", value="hemorrhagic_sah", icd10_code="I60.9"),
            ResponseOption(label="TIA (transient ischemic attack)", value="tia", icd10_code="G45.9"),
        ],
        "coding_impacts": [CodingImpact.CC_MCC, CodingImpact.DRG_CHANGE, CodingImpact.HCC],
        "regulatory_basis": ["ICD-10-CM Official Guidelines Section I.C.9.d"],
    },

    # Infection queries
    "infection_organism": {
        "question": "Has the causative organism been identified?",
        "response_options": [
            ResponseOption(label="Culture/lab pending", value="pending"),
            ResponseOption(label="Organism identified - will specify", value="identified"),
            ResponseOption(label="Culture negative / no organism identified", value="negative"),
            ResponseOption(label="Empiric treatment - no culture obtained", value="empiric"),
        ],
        "coding_impacts": [CodingImpact.SPECIFICITY, CodingImpact.CC_MCC],
        "regulatory_basis": ["ICD-10-CM Official Guidelines Section I.B.10"],
    },

    # Procedure documentation
    "procedure_medical_necessity": {
        "question": "Please document the medical necessity for this procedure:",
        "response_options": [
            ResponseOption(label="Diagnostic - to evaluate symptoms", value="diagnostic"),
            ResponseOption(label="Therapeutic - to treat condition", value="therapeutic"),
            ResponseOption(label="Preventive - screening/surveillance", value="preventive"),
            ResponseOption(label="Emergency - urgent medical need", value="emergency"),
        ],
        "coding_impacts": [CodingImpact.MEDICAL_NECESSITY],
        "regulatory_basis": ["CMS Medical Necessity Guidelines", "LCD/NCD Requirements"],
    },
}


class CodingQueryGeneratorService:
    """Service for generating structured coding queries."""

    def __init__(self):
        """Initialize the service."""
        self._gap_detector = get_documentation_gap_detector()
        self._query_templates = QUERY_TEMPLATES
        # Common clinical terms to look for in text
        self._clinical_triggers = [
            # Conditions
            "diabetes", "dm", "diabetic", "heart failure", "chf", "hf",
            "hypertension", "htn", "ckd", "chronic kidney disease", "renal",
            "copd", "asthma", "stroke", "cva", "atrial fibrillation", "afib",
            "cancer", "malignancy", "fracture", "pneumonia", "sepsis",
            "depression", "anxiety", "obesity", "anemia",
            # Procedures/conditions needing laterality
            "knee", "hip", "shoulder", "ankle", "wrist", "cataract",
            "carpal tunnel", "rotator cuff", "dvt",
        ]
        logger.info("CodingQueryGeneratorService initialized")

    def _extract_basic_mentions(self, clinical_text: str) -> list[dict[str, Any]]:
        """Extract basic mentions from clinical text for gap analysis.

        This is a simple extraction for when no NLP-extracted mentions are provided.
        It finds clinical terms in the text and creates mention dicts.

        Args:
            clinical_text: The clinical documentation text

        Returns:
            List of mention dicts with 'text' and 'domain' keys
        """
        mentions = []
        text_lower = clinical_text.lower()

        for trigger in self._clinical_triggers:
            if trigger in text_lower:
                # Find the position and extract context
                pos = text_lower.find(trigger)
                # Extract a window around the trigger
                start = max(0, pos - 20)
                end = min(len(clinical_text), pos + len(trigger) + 20)
                context = clinical_text[start:end].strip()

                # Determine domain based on trigger
                domain = "Condition"
                if trigger in ["knee", "hip", "shoulder", "ankle", "wrist"]:
                    domain = "Procedure"

                mentions.append({
                    "text": context,
                    "domain": domain,
                    "trigger": trigger,
                    "confidence": 0.8,
                })

        return mentions

    def generate_queries(
        self,
        clinical_text: str,
        extracted_mentions: list[dict[str, Any]] | None = None,
        encounter_context: dict[str, Any] | None = None,
    ) -> QueryBatch:
        """Generate coding queries from clinical documentation.

        Args:
            clinical_text: The clinical documentation text
            extracted_mentions: Pre-extracted NLP mentions (optional)
            encounter_context: Additional context (encounter type, setting, etc.)

        Returns:
            QueryBatch containing prioritized queries
        """
        encounter_context = encounter_context or {}

        # If no extracted mentions provided, do basic text extraction
        if not extracted_mentions:
            extracted_mentions = self._extract_basic_mentions(clinical_text)

        # Step 1: Detect documentation gaps
        gap_result = self._gap_detector.analyze(
            clinical_text=clinical_text,
            extracted_mentions=extracted_mentions
        )

        # Step 2: Convert gaps to structured queries
        queries = self._convert_gaps_to_queries(
            gaps=gap_result.gaps,
            clinical_text=clinical_text,
            encounter_context=encounter_context
        )

        # Step 3: Prioritize queries
        queries = self._prioritize_queries(queries, encounter_context)

        # Step 4: Build query batch
        batch = self._build_query_batch(
            queries=queries,
            gap_result=gap_result,
            encounter_context=encounter_context
        )

        logger.info(f"Generated {len(queries)} coding queries")
        return batch

    def _convert_gaps_to_queries(
        self,
        gaps: list[DocumentationGap],
        clinical_text: str,
        encounter_context: dict[str, Any]
    ) -> list[CodingQuery]:
        """Convert documentation gaps to structured queries."""
        queries = []

        for gap in gaps:
            # Find matching template
            template_key = self._find_template_for_gap(gap)
            template = self._query_templates.get(template_key) if template_key else None

            # Build query from gap and template
            query = self._build_query_from_gap(
                gap=gap,
                template=template,
                clinical_text=clinical_text,
                encounter_context=encounter_context
            )
            queries.append(query)

        return queries

    def _find_template_for_gap(self, gap: DocumentationGap) -> str | None:
        """Find the appropriate template for a documentation gap."""
        finding_lower = gap.finding.lower()
        issue_lower = gap.issue.lower()

        # Match based on finding content
        if "diabetes" in finding_lower or "dm" in finding_lower:
            if "type" in issue_lower:
                return "diabetes_type"
            if "complication" in issue_lower:
                return "diabetes_complications"
            if "control" in issue_lower:
                return "diabetes_control"

        if "heart failure" in finding_lower or "chf" in finding_lower or "hf" in finding_lower:
            if "type" in issue_lower or "systolic" in issue_lower or "diastolic" in issue_lower:
                return "heart_failure_type"
            if "acute" in issue_lower or "chronic" in issue_lower:
                return "heart_failure_acuity"

        if "ckd" in finding_lower or "chronic kidney" in finding_lower:
            return "ckd_stage"

        if "hypertension" in finding_lower:
            return "hypertension_control"

        if "fracture" in finding_lower:
            if "episode" in issue_lower or "initial" in issue_lower:
                return "fracture_episode"

        if "stroke" in finding_lower or "cva" in finding_lower:
            return "stroke_type"

        if gap.category == GapCategory.LATERALITY:
            return "laterality"

        if gap.category == GapCategory.MEDICAL_NECESSITY:
            return "procedure_medical_necessity"

        return None

    def _build_query_from_gap(
        self,
        gap: DocumentationGap,
        template: dict[str, Any] | None,
        clinical_text: str,
        encounter_context: dict[str, Any]
    ) -> CodingQuery:
        """Build a CodingQuery from a gap and optional template."""
        query_id = f"CDI-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # Determine priority based on severity and encounter type
        priority = self._determine_priority(gap, encounter_context)

        # Build response options
        if template:
            response_options = template.get("response_options", [])
            coding_impacts = template.get("coding_impacts", [])
            regulatory_basis = template.get("regulatory_basis", [])
            question = template.get("question", gap.query_text)
        else:
            response_options = [
                ResponseOption(label=opt, value=opt.lower().replace(" ", "_"))
                for opt in gap.query_options
            ]
            coding_impacts = self._infer_coding_impacts(gap)
            regulatory_basis = []
            question = gap.query_text

        # Build CER citation
        cer_citation = self._build_cer_citation(
            gap=gap,
            regulatory_basis=regulatory_basis
        )

        # Extract relevant clinical context
        context_snippet = self._extract_context_snippet(
            clinical_text=clinical_text,
            finding=gap.finding
        )

        query = CodingQuery(
            query_id=query_id,
            priority=priority,
            status=QueryStatus.PENDING,
            question=question,
            clinical_context=context_snippet,
            response_options=response_options,
            gap_category=gap.category,
            gap_severity=gap.severity,
            finding=gap.finding,
            coding_impacts=coding_impacts,
            affected_icd10_codes=gap.icd10_implications,
            affected_cpt_codes=gap.cpt_implications,
            estimated_revenue_impact=self._estimate_single_query_impact(gap),
            quality_measures_affected=gap.quality_implications,
            cer_citation=cer_citation,
            encounter_id=encounter_context.get("encounter_id"),
            patient_id=encounter_context.get("patient_id"),
        )

        return query

    def _determine_priority(
        self,
        gap: DocumentationGap,
        encounter_context: dict[str, Any]
    ) -> QueryPriority:
        """Determine query priority based on severity and context."""
        encounter_type = encounter_context.get("encounter_type", "")

        # Critical gaps are always urgent
        if gap.severity == GapSeverity.CRITICAL:
            return QueryPriority.STAT if "inpatient" in encounter_type.lower() else QueryPriority.URGENT

        # High severity based on encounter type
        if gap.severity == GapSeverity.HIGH:
            if "inpatient" in encounter_type.lower() or "emergency" in encounter_type.lower():
                return QueryPriority.URGENT
            return QueryPriority.ROUTINE

        # Medium and low
        if gap.severity == GapSeverity.MEDIUM:
            return QueryPriority.ROUTINE

        return QueryPriority.DEFERRED

    def _infer_coding_impacts(self, gap: DocumentationGap) -> list[CodingImpact]:
        """Infer coding impacts from a gap without a template."""
        impacts = []

        finding_lower = gap.finding.lower()

        # Check for HCC impact conditions
        hcc_conditions = ["diabetes", "chf", "heart failure", "ckd", "copd", "stroke", "cancer"]
        if any(cond in finding_lower for cond in hcc_conditions):
            impacts.append(CodingImpact.HCC)

        # Check for CC/MCC conditions
        cc_conditions = ["acute", "exacerbation", "complication", "failure", "sepsis"]
        if any(cond in finding_lower for cond in cc_conditions):
            impacts.append(CodingImpact.CC_MCC)

        # Specificity is always an impact
        impacts.append(CodingImpact.SPECIFICITY)

        # Check for quality measure conditions
        quality_conditions = ["diabetes", "hypertension", "depression", "screening"]
        if any(cond in finding_lower for cond in quality_conditions):
            impacts.append(CodingImpact.QUALITY)

        return impacts

    def _build_cer_citation(
        self,
        gap: DocumentationGap,
        regulatory_basis: list[str]
    ) -> CERCitation:
        """Build a CER citation for a query."""
        # Build claim
        claim = f"Documentation clarification needed: {gap.issue}"

        # Build evidence
        evidence = [
            f"Finding: {gap.finding}",
            f"Gap category: {gap.category.value}",
            f"Severity: {gap.severity.value}",
        ]
        # Convert icd10_implications to list if needed (may be dict_values)
        icd10_list = list(gap.icd10_implications) if gap.icd10_implications else []
        if icd10_list:
            evidence.append(f"ICD-10 impact: {', '.join(icd10_list[:3])}")

        # Build reasoning
        reasoning = f"{gap.impact} Without clarification, the most accurate code cannot be assigned, potentially affecting reimbursement and quality reporting."

        return CERCitation(
            claim=claim,
            evidence=evidence,
            reasoning=reasoning,
            strength=self._severity_to_strength(gap.severity),
            regulatory_basis=regulatory_basis or ["ICD-10-CM Official Guidelines"],
            coding_references=icd10_list[:5]
        )

    def _severity_to_strength(self, severity: GapSeverity) -> str:
        """Convert gap severity to CER strength."""
        mapping = {
            GapSeverity.CRITICAL: "HIGH",
            GapSeverity.HIGH: "HIGH",
            GapSeverity.MEDIUM: "MEDIUM",
            GapSeverity.LOW: "LOW"
        }
        return mapping.get(severity, "MEDIUM")

    def _extract_context_snippet(
        self,
        clinical_text: str,
        finding: str,
        context_chars: int = 200
    ) -> str:
        """Extract a context snippet around the finding."""
        finding_lower = finding.lower()
        text_lower = clinical_text.lower()

        # Find the position of the finding
        pos = text_lower.find(finding_lower)
        if pos == -1:
            # Try partial match
            for word in finding_lower.split():
                if len(word) > 3:
                    pos = text_lower.find(word)
                    if pos != -1:
                        break

        if pos == -1:
            # Return first part of text if finding not found
            return clinical_text[:context_chars] + "..." if len(clinical_text) > context_chars else clinical_text

        # Extract context around the finding
        start = max(0, pos - context_chars // 2)
        end = min(len(clinical_text), pos + len(finding) + context_chars // 2)

        snippet = clinical_text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(clinical_text):
            snippet = snippet + "..."

        return snippet

    def _estimate_single_query_impact(self, gap: DocumentationGap) -> float:
        """Estimate revenue impact for a single query."""
        base_impacts = {
            GapSeverity.CRITICAL: 500.0,
            GapSeverity.HIGH: 150.0,
            GapSeverity.MEDIUM: 50.0,
            GapSeverity.LOW: 10.0
        }
        return base_impacts.get(gap.severity, 25.0)

    def _prioritize_queries(
        self,
        queries: list[CodingQuery],
        encounter_context: dict[str, Any]
    ) -> list[CodingQuery]:
        """Sort queries by priority and estimated impact."""
        priority_order = {
            QueryPriority.STAT: 0,
            QueryPriority.URGENT: 1,
            QueryPriority.ROUTINE: 2,
            QueryPriority.DEFERRED: 3
        }

        return sorted(
            queries,
            key=lambda q: (priority_order.get(q.priority, 99), -q.estimated_revenue_impact)
        )

    def _build_query_batch(
        self,
        queries: list[CodingQuery],
        gap_result: DocumentationGapResult,
        encounter_context: dict[str, Any]
    ) -> QueryBatch:
        """Build a QueryBatch from queries and gap analysis."""
        batch_id = f"BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        # Count by priority
        by_priority = {}
        for q in queries:
            key = q.priority.value
            by_priority[key] = by_priority.get(key, 0) + 1

        # Count by category
        by_category = {}
        for q in queries:
            key = q.gap_category.value
            by_category[key] = by_category.get(key, 0) + 1

        # Count by status
        by_status = {"pending": len(queries)}

        # Check for major impacts
        drg_impact = any(CodingImpact.DRG_CHANGE in q.coding_impacts for q in queries)
        hcc_impact = any(CodingImpact.HCC in q.coding_impacts for q in queries)

        # Collect quality measures
        quality_measures = set()
        for q in queries:
            quality_measures.update(q.quality_measures_affected)

        return QueryBatch(
            batch_id=batch_id,
            encounter_id=encounter_context.get("encounter_id"),
            patient_id=encounter_context.get("patient_id"),
            document_id=encounter_context.get("document_id"),
            queries=queries,
            total_queries=len(queries),
            by_priority=by_priority,
            by_category=by_category,
            by_status=by_status,
            total_estimated_revenue_impact=gap_result.estimated_revenue_at_risk,
            drg_impact_possible=drg_impact,
            hcc_impact_possible=hcc_impact,
            quality_measures_at_risk=list(quality_measures),
            documentation_score=gap_result.overall_documentation_score
        )

    def update_query_status(
        self,
        query: CodingQuery,
        new_status: QueryStatus,
        response_value: str | None = None,
        response_notes: str | None = None
    ) -> CodingQuery:
        """Update the status of a query."""
        query.status = new_status

        if new_status == QueryStatus.SENT:
            query.sent_at = datetime.now(timezone.utc)
        elif new_status in [QueryStatus.RESPONDED, QueryStatus.RESOLVED]:
            query.responded_at = datetime.now(timezone.utc)
            query.response_value = response_value
            query.response_notes = response_notes

        return query

    def get_query_template(self, template_key: str) -> dict[str, Any] | None:
        """Get a specific query template."""
        return self._query_templates.get(template_key)

    def list_template_keys(self) -> list[str]:
        """List available query template keys."""
        return list(self._query_templates.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "template_count": len(self._query_templates),
            "templates": list(self._query_templates.keys()),
            "gap_categories": [c.value for c in GapCategory],
            "priorities": [p.value for p in QueryPriority],
            "coding_impacts": [i.value for i in CodingImpact],
        }


# Singleton pattern
_service_instance: CodingQueryGeneratorService | None = None
_service_lock = threading.Lock()


def get_coding_query_generator_service() -> CodingQueryGeneratorService:
    """Get singleton instance of CodingQueryGeneratorService."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = CodingQueryGeneratorService()
    return _service_instance


def reset_coding_query_generator_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
