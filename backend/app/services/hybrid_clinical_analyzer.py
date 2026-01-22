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

        # Categorize entities
        for entity in mapping.entities:
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

        # Extract relationships
        for rel in mapping.relationships:
            context.relationships.append({
                "subject": rel.subject.span.text,
                "relation": rel.relation.value,
                "object": rel.object.span.text,
                "confidence": rel.confidence,
            })

        return context, mapping

    async def analyze(
        self,
        note_text: str,
        analysis_type: AnalysisType = AnalysisType.CLINICAL_SUMMARY,
        question: str | None = None,
        include_raw_mapping: bool = False,
        llm_model: str | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> HybridAnalysisResult:
        """Perform hybrid analysis on a clinical note.

        Args:
            note_text: The clinical note text.
            analysis_type: Type of analysis to perform.
            question: Specific question (for QUESTION_ANSWER type).
            include_raw_mapping: Whether to include raw mapping in result.
            llm_model: Override LLM model.
            llm_provider: Override LLM provider.

        Returns:
            HybridAnalysisResult with grounded analysis.
        """
        total_start = time.perf_counter()

        # Step 1: Deterministic extraction
        extract_start = time.perf_counter()
        context, mapping = self.extract_structured_context(note_text)
        extraction_time = (time.perf_counter() - extract_start) * 1000

        # Step 2: Build LLM prompt with structured context
        system_prompt = SYSTEM_PROMPTS.get(analysis_type, SYSTEM_PROMPTS[AnalysisType.FREE_FORM])

        user_prompt = f"""STRUCTURED CLINICAL DATA (extracted deterministically):

{context.to_prompt_context()}

---

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
