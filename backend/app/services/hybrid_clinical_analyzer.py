"""Hybrid Clinical Analyzer - Combining Deterministic + LLM Analysis.

This service combines two complementary approaches:

1. DETERMINISTIC LAYER (Ontology Mapper):
   - 100% token coverage
   - Structured extraction (entities, relationships)
   - Fast (~1ms processing)
   - Reproducible output
   - No hallucination risk

2. LLM LAYER:
   - Clinical reasoning over structured data
   - Explanation and summarization
   - Handles ambiguous cases
   - Answers complex questions
   - Generates clinical insights

The hybrid approach provides:
- Grounded reasoning (LLM reasons over verified structure)
- Reduced hallucination (LLM cites extracted entities)
- Deterministic foundation with intelligent analysis
- Best of both worlds

Architecture:
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLINICAL NOTE INPUT                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│  ONTOLOGY MAPPER    │   │  RELATIONSHIP       │   │  VOCABULARY         │
│  (Token-level)      │   │  EXTRACTION         │   │  NORMALIZATION      │
│                     │   │                     │   │                     │
│  • Every word       │   │  • Entity links     │   │  • SNOMED-CT        │
│  • Categories       │   │  • Treatment        │   │  • ICD-10           │
│  • Confidence       │   │  • Negation         │   │  • RxNorm           │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STRUCTURED CONTEXT                                  │
│  • Entities: [{type, name, code, negated, confidence}, ...]                 │
│  • Relationships: [{subject, relation, object}, ...]                        │
│  • Coverage: 99.0%                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM REASONING                                     │
│                                                                             │
│  System: "You are a clinical assistant. Reason ONLY over the provided      │
│           structured data. Do not infer beyond what is extracted."          │
│                                                                             │
│  User: "Given these entities and relationships: {structured_context}        │
│         Answer: {user_question}"                                            │
│                                                                             │
│  → Grounded response with citations to extracted entities                   │
└─────────────────────────────────────────────────────────────────────────────┘
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any

from app.services.clinical_ontology_mapper import (
    ClinicalOntologyMapper,
    ClassifiedToken,
    OntologyCategory,
    OntologyMappingResult,
    Relationship,
    get_ontology_mapper,
)
from app.services.llm_service import (
    LLMService,
    LLMMessage,
    LLMResponse,
    LLMProvider,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class AnalysisType(str, Enum):
    """Types of hybrid analysis."""
    CLINICAL_SUMMARY = "clinical_summary"
    RISK_ASSESSMENT = "risk_assessment"
    MEDICATION_REVIEW = "medication_review"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    TREATMENT_PLAN = "treatment_plan"
    LAB_INTERPRETATION = "lab_interpretation"
    QUESTION_ANSWER = "question_answer"
    FREE_FORM = "free_form"


@dataclass
class StructuredContext:
    """Structured context extracted from a clinical note."""
    # Entities by type
    diagnoses: list[dict[str, Any]] = field(default_factory=list)
    medications: list[dict[str, Any]] = field(default_factory=list)
    labs: list[dict[str, Any]] = field(default_factory=list)
    vitals: list[dict[str, Any]] = field(default_factory=list)
    symptoms: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    procedures: list[dict[str, Any]] = field(default_factory=list)

    # Relationships
    relationships: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    negated_findings: list[str] = field(default_factory=list)
    uncertain_findings: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    entity_count: int = 0

    def to_prompt_context(self) -> str:
        """Convert to a prompt-friendly string for LLM."""
        sections = []

        if self.diagnoses:
            diag_list = [d["name"] + (" (negated)" if d.get("negated") else "") for d in self.diagnoses]
            sections.append(f"DIAGNOSES: {', '.join(diag_list)}")

        if self.medications:
            med_list = [m["name"] for m in self.medications]
            sections.append(f"MEDICATIONS: {', '.join(med_list)}")

        if self.labs:
            lab_list = [f"{l['name']}: {l.get('value', 'pending')}" for l in self.labs]
            sections.append(f"LABS: {', '.join(lab_list)}")

        if self.vitals:
            vital_list = [f"{v['name']}: {v.get('value', 'N/A')}" for v in self.vitals]
            sections.append(f"VITALS: {', '.join(vital_list)}")

        if self.symptoms:
            symp_list = [s["name"] + (" (negated)" if s.get("negated") else "") for s in self.symptoms]
            sections.append(f"SYMPTOMS: {', '.join(symp_list)}")

        if self.findings:
            find_list = [f["name"] for f in self.findings]
            sections.append(f"FINDINGS: {', '.join(find_list)}")

        if self.procedures:
            proc_list = [p["name"] for p in self.procedures]
            sections.append(f"PROCEDURES: {', '.join(proc_list)}")

        if self.relationships:
            rel_list = [f"{r['subject']} → {r['relation']} → {r['object']}" for r in self.relationships]
            sections.append(f"RELATIONSHIPS:\n  " + "\n  ".join(rel_list))

        if self.negated_findings:
            sections.append(f"NEGATED (not present): {', '.join(self.negated_findings)}")

        sections.append(f"\n[Extraction confidence: {self.coverage_pct}% coverage, {self.entity_count} entities]")

        return "\n".join(sections)

    # Terms that are partial medical phrases (not meaningful standalone)
    _PARTIAL_TERMS = frozenset({
        "mellitus", "coronary", "myocardial", "infarction", "syndrome",
        "artery", "arterial", "venous", "vascular", "pulmonary", "renal",
        "hepatic", "cerebral", "peripheral", "systemic", "insufficiency",
        "dysfunction", "disease", "disorder", "failure", "deficiency",
        "hemoglobin", "cardiology", "troponins", "serial",
    })

    def _dedupe_entities(self, entities: list[dict], name_key: str = "name") -> list[dict]:
        """Deduplicate entities by name (case-insensitive)."""
        seen = set()
        result = []
        for entity in entities:
            name = (entity.get("normalized") or entity.get(name_key, "")).lower()
            # Skip partial medical terms that aren't meaningful standalone
            if name in self._PARTIAL_TERMS:
                continue
            if name and name not in seen:
                seen.add(name)
                result.append(entity)
        return result

    def to_human_readable_summary(self) -> str:
        """Generate a human-readable clinical summary.

        Returns:
            A formatted string summary that's easy to read.
        """
        lines = []

        # Active Problems / Diagnoses (deduplicated)
        if self.diagnoses:
            present_dx = self._dedupe_entities(
                [d for d in self.diagnoses if not d.get("negated")]
            )
            if present_dx:
                lines.append("**Active Problems:**")
                for dx in present_dx[:10]:  # Limit to top 10
                    name = dx.get("normalized") or dx.get("name", "Unknown")
                    code = dx.get("vocabulary_code", "")
                    code_str = f" ({code})" if code else ""
                    lines.append(f"  • {name}{code_str}")
                if len(present_dx) > 10:
                    lines.append(f"  ... and {len(present_dx) - 10} more")
                lines.append("")

        # Current Medications (deduplicated)
        if self.medications:
            deduped_meds = self._dedupe_entities(self.medications)
            if deduped_meds:
                lines.append("**Current Medications:**")
                for med in deduped_meds[:10]:
                    name = med.get("normalized") or med.get("name", "Unknown")
                    dose = med.get("dose", "")
                    freq = med.get("frequency", "")
                    details = " ".join(filter(None, [dose, freq]))
                    details_str = f" - {details}" if details else ""
                    lines.append(f"  • {name}{details_str}")
                if len(deduped_meds) > 10:
                    lines.append(f"  ... and {len(deduped_meds) - 10} more")
                lines.append("")

        # Vital Signs (only show if we have values)
        if self.vitals:
            vital_strs = []
            deduped_vitals = self._dedupe_entities(self.vitals)
            for vital in deduped_vitals[:8]:
                name = vital.get("name", "")
                value = vital.get("value", "")
                if name and value:
                    vital_strs.append(f"{name}: {value}")
            if vital_strs:
                lines.append("**Vital Signs:**")
                lines.append(f"  {', '.join(vital_strs)}")
                lines.append("")

        # Lab Results (only show if we have actual results)
        if self.labs:
            deduped_labs = self._dedupe_entities(self.labs)
            lab_lines = []
            for lab in deduped_labs[:10]:
                name = lab.get("name", "Unknown")
                value = lab.get("value")
                if value:  # Only show labs with actual values
                    unit = lab.get("unit", "")
                    flag = lab.get("flag", "")
                    value_str = f"{value} {unit}".strip()
                    flag_str = f" [{flag.upper()}]" if flag else ""
                    lab_lines.append(f"  • {name}: {value_str}{flag_str}")
            if lab_lines:
                lines.append("**Laboratory Results:**")
                lines.extend(lab_lines)
                lines.append("")

        # Symptoms (present, deduplicated)
        if self.symptoms:
            present_symptoms = self._dedupe_entities(
                [s for s in self.symptoms if not s.get("negated")]
            )
            if present_symptoms:
                lines.append("**Presenting Symptoms:**")
                symptom_names = list(set(
                    s.get("normalized") or s.get("name", "")
                    for s in present_symptoms[:8]
                ))
                lines.append(f"  {', '.join(filter(None, symptom_names))}")
                lines.append("")

        # Procedures (deduplicated)
        if self.procedures:
            deduped_procs = self._dedupe_entities(self.procedures)
            if deduped_procs:
                lines.append("**Procedures/Treatments:**")
                for proc in deduped_procs[:5]:
                    name = proc.get("normalized") or proc.get("name", "Unknown")
                    lines.append(f"  • {name}")
                if len(deduped_procs) > 5:
                    lines.append(f"  ... and {len(deduped_procs) - 5} more")
                lines.append("")

        # Negated findings (what was ruled out, deduplicated)
        if self.negated_findings:
            negated_list = list(set(self.negated_findings))[:8]
            if negated_list:
                lines.append("**Ruled Out / Denied:**")
                lines.append(f"  {', '.join(negated_list)}")
                if len(set(self.negated_findings)) > 8:
                    lines.append(f"  ... and more")
                lines.append("")

        if not lines:
            return "No significant clinical findings extracted."

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "diagnoses": self.diagnoses,
            "medications": self.medications,
            "labs": self.labs,
            "vitals": self.vitals,
            "symptoms": self.symptoms,
            "findings": self.findings,
            "procedures": self.procedures,
            "relationships": self.relationships,
            "negated_findings": self.negated_findings,
            "uncertain_findings": self.uncertain_findings,
            "coverage_pct": self.coverage_pct,
            "entity_count": self.entity_count,
            "human_readable_summary": self.to_human_readable_summary(),
        }


@dataclass
class HybridAnalysisResult:
    """Result of hybrid analysis."""
    # Analysis output
    analysis: str
    analysis_type: AnalysisType

    # Structured extraction (deterministic)
    structured_context: StructuredContext
    raw_mapping: OntologyMappingResult | None = None

    # LLM metadata
    llm_model: str = ""
    llm_tokens_used: int = 0
    llm_cost_usd: float = 0.0

    # Timing
    extraction_time_ms: float = 0.0
    llm_time_ms: float = 0.0
    total_time_ms: float = 0.0

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis,
            "analysis_type": self.analysis_type.value,
            "structured_context": self.structured_context.to_dict(),
            "llm_model": self.llm_model,
            "llm_tokens_used": self.llm_tokens_used,
            "llm_cost_usd": self.llm_cost_usd,
            "extraction_time_ms": self.extraction_time_ms,
            "llm_time_ms": self.llm_time_ms,
            "total_time_ms": self.total_time_ms,
            "timestamp": self.timestamp,
        }


# =============================================================================
# SYSTEM PROMPTS FOR DIFFERENT ANALYSIS TYPES
# =============================================================================

SYSTEM_PROMPTS = {
    AnalysisType.CLINICAL_SUMMARY: """You are a clinical documentation assistant. Your task is to provide a concise clinical summary based ONLY on the structured data provided.

RULES:
1. Only reference entities that appear in the provided structured data
2. Do not infer diagnoses or findings that are not listed
3. Clearly distinguish between present findings and negated findings
4. Be concise and clinically relevant
5. Use standard medical terminology

Format your response as:
- Chief Concern (if identifiable)
- Key Findings (from the data)
- Active Problems
- Current Medications
- Notable Lab/Vital Values""",

    AnalysisType.RISK_ASSESSMENT: """You are a clinical risk assessment assistant. Identify potential risks based ONLY on the structured data provided.

RULES:
1. Only assess risks based on extracted entities
2. Do not speculate beyond the provided data
3. Cite specific findings that support each risk
4. Prioritize by clinical urgency
5. Note any missing data that would affect assessment

Format your response as:
- HIGH PRIORITY risks (immediate attention)
- MODERATE risks (monitoring needed)
- Potential drug interactions (if medications listed)
- Missing data that limits assessment""",

    AnalysisType.MEDICATION_REVIEW: """You are a clinical pharmacist assistant. Review the medications based on the structured data provided.

RULES:
1. Only discuss medications explicitly listed
2. Check for known drug-drug interactions
3. Consider diagnoses when assessing appropriateness
4. Note any potential concerns given the clinical context
5. Do not recommend medications not supported by the data

Format your response as:
- Current Medications Review
- Potential Interactions
- Appropriateness for Listed Conditions
- Monitoring Recommendations""",

    AnalysisType.LAB_INTERPRETATION: """You are a clinical laboratory specialist. Interpret the lab values based on the structured data provided.

RULES:
1. Only interpret labs that are explicitly listed
2. Consider the clinical context (diagnoses, medications)
3. Note critical values if present
4. Suggest correlations with symptoms/diagnoses
5. Identify gaps in lab data

Format your response as:
- Critical/Abnormal Values
- Interpretation in Clinical Context
- Correlations with Diagnoses
- Suggested Additional Testing (if warranted by findings)""",

    AnalysisType.QUESTION_ANSWER: """You are a clinical assistant answering questions about a patient's data. Answer based ONLY on the structured data provided.

RULES:
1. Only use information from the provided structured data
2. If the data doesn't contain the answer, say so clearly
3. Cite specific entities when answering
4. Be precise and avoid speculation
5. Distinguish between present and negated findings""",

    AnalysisType.FREE_FORM: """You are a clinical assistant analyzing patient data. Provide analysis based ONLY on the structured data provided.

RULES:
1. Ground all statements in the provided data
2. Cite specific entities from the extraction
3. Clearly distinguish facts from clinical reasoning
4. Do not hallucinate findings not in the data
5. Note limitations of the available information""",
}


# =============================================================================
# HYBRID CLINICAL ANALYZER SERVICE
# =============================================================================


class HybridClinicalAnalyzer:
    """Combines deterministic ontology mapping with LLM reasoning.

    This analyzer provides grounded clinical analysis by:
    1. First extracting structured data deterministically
    2. Then using LLM to reason over the structured data
    3. Ensuring LLM responses are grounded in extracted entities

    Example usage:
        >>> analyzer = HybridClinicalAnalyzer()
        >>> result = await analyzer.analyze(
        ...     note_text="Patient presents with chest pain...",
        ...     analysis_type=AnalysisType.CLINICAL_SUMMARY,
        ... )
        >>> print(result.analysis)
    """

    def __init__(
        self,
        ontology_mapper: ClinicalOntologyMapper | None = None,
        llm_service: LLMService | None = None,
    ):
        """Initialize the hybrid analyzer.

        Args:
            ontology_mapper: Ontology mapper instance (uses singleton if None).
            llm_service: LLM service instance (creates new if None).
        """
        self._mapper = ontology_mapper or get_ontology_mapper()
        self._llm = llm_service or LLMService()

    # Non-clinical terms to filter out (document metadata, common words)
    NON_CLINICAL_TERMS = frozenset({
        # Document metadata and section headers
        "synthetic", "test", "patient", "testing", "data", "note", "notes",
        "document", "example", "sample", "facility", "clinic", "hospital",
        "author", "provider", "date", "time", "mrn", "dob", "age", "sex",
        "male", "female", "m", "f", "office", "visit", "type", "internal",
        "medicine", "primary", "care", "pcp", "comprehensive", "follow",
        "longitudinal", "real", "not", "history", "present", "illness",
        "chief", "complaint", "assessment", "plan", "exam", "physical",
        "review", "systems", "social", "family", "past", "medical",
        "surgical", "allergies", "impression", "recommendation", "course",
        "subjective", "objective", "discharge", "summary", "progress",
        # Time/age words
        "old", "new", "year", "years", "month", "months", "day", "days",
        "week", "weeks", "hour", "hours", "minute", "minutes", "second",
        "today", "yesterday", "tomorrow", "ago", "since", "serial", "recent",
        # Common non-clinical words that might get misclassified
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "to", "of",
        "in", "for", "on", "with", "at", "by", "from", "as", "or", "and",
        "but", "if", "then", "so", "than", "that", "this", "these", "those",
        "it", "its", "he", "she", "they", "we", "you", "i", "me", "him",
        "her", "us", "them", "my", "your", "his", "their", "our", "no", "yes",
        "up", "down", "out", "off", "over", "under", "again", "further",
        "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such",
        "only", "own", "same", "very", "just", "also", "now",
        # Anatomical modifiers (when standalone, not clinical)
        "left", "right", "upper", "lower", "bilateral", "unilateral",
        "anterior", "posterior", "lateral", "medial", "proximal", "distal",
        # Qualifiers and descriptors
        "mild", "moderate", "severe", "acute", "chronic", "stable",
        "normal", "abnormal", "elevated", "decreased", "increased",
        "positive", "negative", "present", "absent", "pending", "unknown",
        "possible", "probable", "likely", "unlikely", "ruled", "rule", "out",
        "pressure", "severity", "rated", "scale", "score", "substernal",
        "radiating", "like", "describes", "arm",
        # Environment/context words
        "room", "air", "who", "describes", "presents", "denies", "reports",
        "states", "noted", "found", "seen", "shows", "indicates", "suggests",
        "continue", "continued", "current", "currently", "previous", "prior",
        "well", "controlled", "uncontrolled", "improved", "worsening",
        "exertion", "rest", "signs", "rhythm", "regimen", "secondary",
        "clear", "rate", "regular", "consult", "monitor", "adjust",
        "oriented", "alert", "distress", "bilaterally", "auscultation",
        # Numbers and units in text form
        "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "first", "second", "third", "daily", "twice", "weekly",
        # Procedure context words (not the procedure itself)
        "lead", "ray", "scan", "image", "imaging", "study", "result", "results",
        "test", "tests", "level", "levels", "panel", "screen", "screening",
    })

    # Minimum confidence threshold for clinical entities
    MIN_CONFIDENCE_THRESHOLD = 0.3

    # Known clinical abbreviations that are valid short entities
    VALID_SHORT_ENTITIES = frozenset({
        "dm", "dm2", "htn", "cad", "chf", "mi", "cvd", "ckd", "esrd",
        "copd", "sob", "cp", "gi", "gu", "cns", "pna", "uti", "dvt",
        "pe", "tia", "cva", "af", "afib", "vfib", "hiv", "aids", "tb",
        "ra", "oa", "sle", "ibs", "ibd", "gerd", "bph", "osa", "rls",
        "ms", "als", "pd", "ad", "ptsd", "ocd", "gad", "mdd", "bp",
        "iv", "im", "po", "prn", "bid", "tid", "qid", "qd", "qod",
        "asa", "nsaid", "ace", "arb", "bb", "ccb", "ssri", "snri",
        "ecg", "ekg", "ct", "mri", "cxr", "bmp", "cmp", "cbc", "lfts",
        "hba1c", "a1c", "inr", "ptt", "pt", "bnp", "tsh", "t3", "t4",
        "hr", "bp", "rr", "o2", "spo2", "bmi", "wbc", "rbc", "hgb", "hct",
        "na", "k", "cl", "co2", "bun", "cr", "glu", "ca", "mg", "phos",
    })

    def _is_clinical_entity(self, entity_name: str, confidence: float) -> bool:
        """Check if an entity is a meaningful clinical entity."""
        # Normalize the name for comparison
        normalized = entity_name.lower().strip()

        # Filter out non-clinical terms
        if normalized in self.NON_CLINICAL_TERMS:
            return False

        # Filter out single-character entities
        if len(normalized) <= 1:
            return False

        # Filter out pure numbers
        if normalized.replace(".", "").replace(",", "").isdigit():
            return False

        # Filter out low confidence
        if confidence < self.MIN_CONFIDENCE_THRESHOLD:
            return False

        # Allow known clinical abbreviations regardless of length
        if normalized in self.VALID_SHORT_ENTITIES:
            return True

        # Filter out very short terms (2-4 chars) unless high confidence
        if len(normalized) <= 4 and confidence < 0.7:
            return False

        # Filter out terms that are too short to be meaningful (5 chars minimum)
        # unless they have reasonable confidence
        if len(normalized) < 5 and confidence < 0.5:
            return False

        return True

    def extract_structured_context(
        self,
        note_text: str,
    ) -> tuple[StructuredContext, OntologyMappingResult]:
        """Extract structured context from a clinical note.

        This is the deterministic step - no LLM involved.

        Args:
            note_text: The clinical note text.

        Returns:
            Tuple of (StructuredContext, raw OntologyMappingResult).
        """
        mapping = self._mapper.map_note(note_text)

        context = StructuredContext(
            coverage_pct=mapping.coverage_stats.get("coverage_pct", 0),
            entity_count=len(mapping.entities),
        )

        # Track negation context
        negation_tokens = set()
        for token in mapping.tokens:
            if token.category == OntologyCategory.NEGATION:
                negation_tokens.add(token.span.start)

        def is_negated(token: ClassifiedToken) -> bool:
            """Check if token is preceded by negation."""
            # Simple heuristic: check if negation within 50 chars before
            for neg_pos in negation_tokens:
                if 0 < token.span.start - neg_pos < 50:
                    return True
            return False

        # Categorize entities (with filtering for clinical relevance)
        filtered_count = 0
        for entity in mapping.entities:
            # Skip non-clinical entities
            if not self._is_clinical_entity(entity.span.text, entity.confidence):
                filtered_count += 1
                continue
            entity_dict = {
                "name": entity.span.text,
                "normalized": entity.span.normalized,
                "category": entity.category.value,
                "vocabulary_code": entity.vocabulary_code,
                "vocabulary_system": entity.vocabulary_system,
                "confidence": entity.confidence,
                "negated": is_negated(entity),
            }

            # Add value if present
            if entity.attributes:
                entity_dict["value"] = entity.attributes.get("value")
                entity_dict["unit"] = entity.attributes.get("unit")

            if entity.category == OntologyCategory.DIAGNOSIS:
                context.diagnoses.append(entity_dict)
                if entity_dict["negated"]:
                    context.negated_findings.append(entity.span.text)
            elif entity.category == OntologyCategory.MEDICATION:
                context.medications.append(entity_dict)
            elif entity.category in (OntologyCategory.LAB_TEST, OntologyCategory.LAB_VALUE):
                context.labs.append(entity_dict)
            elif entity.category in (OntologyCategory.VITAL_SIGN, OntologyCategory.VITAL_VALUE):
                context.vitals.append(entity_dict)
            elif entity.category == OntologyCategory.SYMPTOM:
                context.symptoms.append(entity_dict)
                if entity_dict["negated"]:
                    context.negated_findings.append(entity.span.text)
            elif entity.category == OntologyCategory.FINDING:
                context.findings.append(entity_dict)
            elif entity.category == OntologyCategory.PROCEDURE:
                context.procedures.append(entity_dict)

        # Extract relationships (filter to only include clinical entities)
        for rel in mapping.relationships:
            if (self._is_clinical_entity(rel.subject.span.text, rel.confidence) and
                self._is_clinical_entity(rel.object.span.text, rel.confidence)):
                context.relationships.append({
                    "subject": rel.subject.span.text,
                    "relation": rel.relation.value,
                    "object": rel.object.span.text,
                    "confidence": rel.confidence,
                })

        # Update entity count to reflect filtered clinical entities only
        actual_entity_count = (
            len(context.diagnoses) + len(context.medications) +
            len(context.labs) + len(context.vitals) +
            len(context.symptoms) + len(context.findings) +
            len(context.procedures)
        )
        context.entity_count = actual_entity_count

        logger.debug(
            f"Extracted {actual_entity_count} clinical entities "
            f"(filtered {filtered_count} non-clinical tokens)"
        )

        return context, mapping

    async def analyze(
        self,
        note_text: str,
        analysis_type: AnalysisType = AnalysisType.CLINICAL_SUMMARY,
        question: str | None = None,
        include_raw_mapping: bool = False,
        llm_model: str | None = None,
        llm_provider: LLMProvider | None = None,
        patient_id: str | None = None,
        db_session: Any | None = None,
    ) -> HybridAnalysisResult:
        """Perform hybrid analysis on a clinical note.

        Args:
            note_text: The clinical note text.
            analysis_type: Type of analysis to perform.
            question: Specific question (for QUESTION_ANSWER type).
            include_raw_mapping: Whether to include raw mapping in result.
            llm_model: Override LLM model.
            llm_provider: Override LLM provider.
            patient_id: Optional patient ID for graph-augmented context.
            db_session: Optional database session for graph queries.

        Returns:
            HybridAnalysisResult with grounded analysis.
        """
        total_start = time.perf_counter()

        # Step 1: Deterministic extraction
        extract_start = time.perf_counter()
        context, mapping = self.extract_structured_context(note_text)
        extraction_time = (time.perf_counter() - extract_start) * 1000

        # Step 1.5: Get graph-augmented context if patient_id provided
        graph_context_str = ""
        if patient_id and db_session:
            try:
                from app.services.graph_augmented_rag import get_graph_augmented_rag_service
                graph_rag = get_graph_augmented_rag_service(db_session)
                graph_context = graph_rag.retrieve_context(
                    query=question or note_text[:500],
                    patient_id=patient_id,
                    max_hops=2,
                    max_paths=5,
                    include_temporal=True,
                    include_policies=True,
                )
                graph_context_str = graph_context.to_llm_prompt()
            except Exception as e:
                logger.warning(f"Failed to retrieve graph context: {e}")

        # Step 2: Build LLM prompt with structured context
        system_prompt = SYSTEM_PROMPTS.get(analysis_type, SYSTEM_PROMPTS[AnalysisType.FREE_FORM])

        # Add graph context to system prompt if available
        if graph_context_str:
            system_prompt += "\n\nYou also have access to knowledge graph evidence showing relationships and temporal context. Use this to provide more accurate and grounded responses."

        user_prompt = f"""STRUCTURED CLINICAL DATA (extracted deterministically):

{context.to_prompt_context()}

"""
        # Add graph-augmented context if available
        if graph_context_str:
            user_prompt += f"""
KNOWLEDGE GRAPH CONTEXT (from patient's clinical history):

{graph_context_str}
"""

        user_prompt += """---

"""
        if analysis_type == AnalysisType.QUESTION_ANSWER and question:
            user_prompt += f"QUESTION: {question}\n\nPlease answer based only on the structured data above."
        elif analysis_type == AnalysisType.CLINICAL_SUMMARY:
            user_prompt += "Please provide a clinical summary based on the structured data above."
        elif analysis_type == AnalysisType.RISK_ASSESSMENT:
            user_prompt += "Please assess clinical risks based on the structured data above."
        elif analysis_type == AnalysisType.MEDICATION_REVIEW:
            user_prompt += "Please review the medications based on the structured data above."
        elif analysis_type == AnalysisType.LAB_INTERPRETATION:
            user_prompt += "Please interpret the lab values based on the structured data above."
        else:
            user_prompt += "Please analyze the clinical data above and provide insights."

        # Step 3: Call LLM
        llm_start = time.perf_counter()
        try:
            llm_response = await self._llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=llm_model,
                provider=llm_provider,
                temperature=0.3,  # Lower temperature for clinical accuracy
            )
            analysis_text = llm_response.content
            llm_model_used = llm_response.model
            tokens_used = llm_response.token_usage.total_tokens
            cost = llm_response.cost_estimate.total_cost
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            analysis_text = f"[LLM analysis unavailable: {e}]\n\nStructured extraction:\n{context.to_prompt_context()}"
            llm_model_used = "none"
            tokens_used = 0
            cost = 0.0

        llm_time = (time.perf_counter() - llm_start) * 1000
        total_time = (time.perf_counter() - total_start) * 1000

        return HybridAnalysisResult(
            analysis=analysis_text,
            analysis_type=analysis_type,
            structured_context=context,
            raw_mapping=mapping if include_raw_mapping else None,
            llm_model=llm_model_used,
            llm_tokens_used=tokens_used,
            llm_cost_usd=cost,
            extraction_time_ms=round(extraction_time, 2),
            llm_time_ms=round(llm_time, 2),
            total_time_ms=round(total_time, 2),
        )

    async def answer_question(
        self,
        note_text: str,
        question: str,
        **kwargs: Any,
    ) -> HybridAnalysisResult:
        """Answer a specific question about a clinical note.

        Convenience method for question-answering.

        Args:
            note_text: The clinical note text.
            question: The question to answer.
            **kwargs: Additional arguments passed to analyze().

        Returns:
            HybridAnalysisResult with the answer.
        """
        return await self.analyze(
            note_text=note_text,
            analysis_type=AnalysisType.QUESTION_ANSWER,
            question=question,
            **kwargs,
        )

    async def get_summary(
        self,
        note_text: str,
        **kwargs: Any,
    ) -> HybridAnalysisResult:
        """Get a clinical summary of a note.

        Convenience method for summaries.

        Args:
            note_text: The clinical note text.
            **kwargs: Additional arguments passed to analyze().

        Returns:
            HybridAnalysisResult with the summary.
        """
        return await self.analyze(
            note_text=note_text,
            analysis_type=AnalysisType.CLINICAL_SUMMARY,
            **kwargs,
        )

    async def assess_risks(
        self,
        note_text: str,
        **kwargs: Any,
    ) -> HybridAnalysisResult:
        """Assess clinical risks from a note.

        Args:
            note_text: The clinical note text.
            **kwargs: Additional arguments passed to analyze().

        Returns:
            HybridAnalysisResult with risk assessment.
        """
        return await self.analyze(
            note_text=note_text,
            analysis_type=AnalysisType.RISK_ASSESSMENT,
            **kwargs,
        )

    def extract_only(self, note_text: str) -> StructuredContext:
        """Extract structured data without LLM analysis.

        For cases where you only need the deterministic extraction.

        Args:
            note_text: The clinical note text.

        Returns:
            StructuredContext with extracted entities.
        """
        context, _ = self.extract_structured_context(note_text)
        return context


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

_analyzer_instance: HybridClinicalAnalyzer | None = None


def get_hybrid_analyzer() -> HybridClinicalAnalyzer:
    """Get or create the singleton HybridClinicalAnalyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = HybridClinicalAnalyzer()
    return _analyzer_instance
