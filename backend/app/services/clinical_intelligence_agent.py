"""
Clinical Intelligence Agent API

Unified orchestration layer for clinical NLP and intelligence services.
Designed for use by AI agents to accomplish complex clinical data tasks.

Supported Use Cases:
1. DRUG DISCOVERY & CLINICAL TRIALS
   - Patient phenotyping from clinical notes
   - Cohort eligibility matching
   - OMOP CDM-compatible extraction

2. MEDICAL CODING & BILLING (Ambient Scribe)
   - HCC risk adjustment analysis
   - ICD-10/CPT code suggestions
   - Documentation quality assessment
   - M.E.A.T. compliance checking

Architecture:
This service orchestrates:
- NLP Entity Extraction (SNOMED, RxNorm, ICD-10, LOINC)
- Clinical Ontology Mapping
- HCC Revenue Recovery Analysis
- Value Extraction (Labs, Vitals)
- Patient Timeline Building
- Cohort Definition Building
- Hybrid LLM Analysis
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class UseCaseType(str, Enum):
    """Primary use case types for the agent."""
    DRUG_DISCOVERY = "drug_discovery"
    CLINICAL_TRIAL = "clinical_trial"
    MEDICAL_CODING = "medical_coding"
    AMBIENT_SCRIBE = "ambient_scribe"
    QUALITY_MEASURE = "quality_measure"
    GENERAL_ANALYSIS = "general_analysis"


class ActionType(str, Enum):
    """Types of actions the agent can perform."""
    # Extraction actions
    EXTRACT_ENTITIES = "extract_entities"
    EXTRACT_MEASUREMENTS = "extract_measurements"
    EXTRACT_MEDICATIONS = "extract_medications"
    EXTRACT_DIAGNOSES = "extract_diagnoses"
    EXTRACT_PROCEDURES = "extract_procedures"

    # Analysis actions
    ANALYZE_HCC = "analyze_hcc"
    ANALYZE_DOCUMENTATION = "analyze_documentation"
    GENERATE_CODES = "generate_codes"
    CHECK_ELIGIBILITY = "check_eligibility"

    # Building actions
    BUILD_TIMELINE = "build_timeline"
    BUILD_PHENOTYPE = "build_phenotype"
    BUILD_COHORT_QUERY = "build_cohort_query"

    # Reasoning actions
    CLINICAL_REASONING = "clinical_reasoning"
    SUMMARIZE = "summarize"
    ANSWER_QUESTION = "answer_question"


@dataclass
class AgentRequest:
    """Request to the Clinical Intelligence Agent."""
    action: ActionType
    clinical_text: str
    use_case: UseCaseType = UseCaseType.GENERAL_ANALYSIS

    # Optional context
    patient_id: str | None = None
    encounter_id: str | None = None
    current_icd10_codes: list[str] = field(default_factory=list)
    current_medications: list[str] = field(default_factory=list)
    lab_values: list[dict[str, Any]] = field(default_factory=list)

    # For clinical reasoning
    question: str | None = None

    # For eligibility checking
    eligibility_criteria: list[dict[str, Any]] = field(default_factory=list)

    # Options
    include_normalized_codes: bool = True
    include_confidence_scores: bool = True
    include_evidence: bool = True
    max_results: int = 50


@dataclass
class AgentResponse:
    """Response from the Clinical Intelligence Agent."""
    success: bool
    action: ActionType
    use_case: UseCaseType

    # Results (populated based on action type)
    entities: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[dict[str, Any]] = field(default_factory=list)
    diagnoses: list[dict[str, Any]] = field(default_factory=list)
    medications: list[dict[str, Any]] = field(default_factory=list)
    procedures: list[dict[str, Any]] = field(default_factory=list)

    # HCC Analysis
    hcc_opportunities: list[dict[str, Any]] = field(default_factory=list)
    raf_score: float = 0.0
    revenue_opportunity: float = 0.0

    # Coding suggestions
    suggested_icd10: list[dict[str, Any]] = field(default_factory=list)
    suggested_cpt: list[dict[str, Any]] = field(default_factory=list)
    documentation_gaps: list[str] = field(default_factory=list)

    # Eligibility
    eligibility_result: dict[str, Any | None] = None

    # Timeline/Phenotype
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    phenotype: dict[str, Any | None] = None

    # Cohort query
    cohort_query: dict[str, Any | None] = None

    # LLM reasoning output
    analysis: str | None = None
    summary: str | None = None
    answer: str | None = None

    # Metadata
    processing_time_ms: float = 0.0
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)


class ClinicalIntelligenceAgent:
    """
    Unified Clinical Intelligence Agent.

    Provides a high-level API for AI agents to interact with clinical data.
    Orchestrates multiple underlying services for comprehensive analysis.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._nlp_service = None
        self._hcc_service = None
        self._value_service = None
        self._timeline_service = None
        self._cohort_service = None
        self._hybrid_analyzer = None
        self._icd10_suggester = None
        self._cpt_suggester = None

    def _lazy_init(self) -> None:
        """Lazy initialization of services to avoid circular imports."""
        if self._initialized:
            return

        try:
            from app.services.nlp_entity_service import get_nlp_entity_service
            self._nlp_service = get_nlp_entity_service()
        except Exception as e:
            logger.warning(f"Could not initialize NLP service: {e}")

        try:
            from app.services.hcc_analyzer import get_hcc_analyzer_service
            self._hcc_service = get_hcc_analyzer_service()
        except Exception as e:
            logger.warning(f"Could not initialize HCC service: {e}")

        try:
            from app.services.value_extraction import get_value_extraction_service
            self._value_service = get_value_extraction_service()
        except Exception as e:
            logger.warning(f"Could not initialize value extraction service: {e}")

        try:
            from app.services.patient_timeline import get_patient_timeline_service
            self._timeline_service = get_patient_timeline_service()
        except Exception as e:
            logger.warning(f"Could not initialize timeline service: {e}")

        try:
            from app.services.cohort_service import get_cohort_service
            self._cohort_service = get_cohort_service()
        except Exception as e:
            logger.warning(f"Could not initialize cohort service: {e}")

        try:
            from app.services.hybrid_clinical_analyzer import get_hybrid_analyzer
            self._hybrid_analyzer = get_hybrid_analyzer()
        except Exception as e:
            logger.warning(f"Could not initialize hybrid analyzer: {e}")

        try:
            from app.services.icd10_suggester import get_icd10_suggester
            self._icd10_suggester = get_icd10_suggester()
        except Exception as e:
            logger.warning(f"Could not initialize ICD-10 suggester: {e}")

        try:
            from app.services.cpt_suggester import get_cpt_suggester
            self._cpt_suggester = get_cpt_suggester()
        except Exception as e:
            logger.warning(f"Could not initialize CPT suggester: {e}")

        self._initialized = True
        logger.info("ClinicalIntelligenceAgent initialized")

    def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process an agent request and return results.

        This is the main entry point for the agent API.
        """
        self._lazy_init()
        start_time = time.perf_counter()

        response = AgentResponse(
            success=True,
            action=request.action,
            use_case=request.use_case,
        )

        try:
            # Route to appropriate handler
            if request.action == ActionType.EXTRACT_ENTITIES:
                self._handle_extract_entities(request, response)
            elif request.action == ActionType.EXTRACT_MEASUREMENTS:
                self._handle_extract_measurements(request, response)
            elif request.action == ActionType.ANALYZE_HCC:
                self._handle_analyze_hcc(request, response)
            elif request.action == ActionType.GENERATE_CODES:
                self._handle_generate_codes(request, response)
            elif request.action == ActionType.BUILD_TIMELINE:
                self._handle_build_timeline(request, response)
            elif request.action == ActionType.BUILD_PHENOTYPE:
                self._handle_build_phenotype(request, response)
            elif request.action == ActionType.CHECK_ELIGIBILITY:
                self._handle_check_eligibility(request, response)
            elif request.action == ActionType.CLINICAL_REASONING:
                self._handle_clinical_reasoning(request, response)
            elif request.action == ActionType.SUMMARIZE:
                self._handle_summarize(request, response)
            elif request.action == ActionType.ANSWER_QUESTION:
                self._handle_answer_question(request, response)
            else:
                response.success = False
                response.error_message = f"Unknown action: {request.action}"

        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            response.success = False
            response.error_message = str(e)

        response.processing_time_ms = (time.perf_counter() - start_time) * 1000
        return response

    def _handle_extract_entities(self, request: AgentRequest, response: AgentResponse) -> None:
        """Extract clinical entities from text."""
        if not self._nlp_service:
            response.warnings.append("NLP service not available")
            return

        result = self._nlp_service.extract_entities(
            text=request.clinical_text,
            include_normalized_codes=request.include_normalized_codes,
        )

        # Convert to dict format
        for entity in result.entities[:request.max_results]:
            entity_dict = {
                "text": entity.text,
                "type": entity.entity_type,
                "start": entity.start_offset,
                "end": entity.end_offset,
                "confidence": entity.confidence,
            }

            if entity.normalized_codes:
                entity_dict["codes"] = [
                    {
                        "system": code.system,
                        "code": code.code,
                        "display": code.display,
                    }
                    for code in entity.normalized_codes
                ]

            response.entities.append(entity_dict)

            # Also categorize by type
            if entity.entity_type in ["DIAGNOSIS", "CONDITION", "PROBLEM"]:
                response.diagnoses.append(entity_dict)
            elif entity.entity_type in ["MEDICATION", "DRUG"]:
                response.medications.append(entity_dict)
            elif entity.entity_type in ["PROCEDURE"]:
                response.procedures.append(entity_dict)

    def _handle_extract_measurements(self, request: AgentRequest, response: AgentResponse) -> None:
        """Extract lab values and vital signs."""
        if not self._value_service:
            response.warnings.append("Value extraction service not available")
            return

        values = self._value_service.extract_all(
            text=request.clinical_text,
        )

        for value in values[:request.max_results]:
            value_dict = {
                "name": value.name,
                "value": value.value,
                "unit": value.unit_normalized or value.unit,
                "type": value.value_type.value if hasattr(value.value_type, 'value') else str(value.value_type),
                "text": value.text,
                "confidence": value.confidence,
            }

            if value.omop_concept_id:
                value_dict["omop_concept_id"] = value.omop_concept_id

            if value.value_secondary is not None:
                value_dict["value_secondary"] = value.value_secondary

            response.measurements.append(value_dict)

    def _handle_analyze_hcc(self, request: AgentRequest, response: AgentResponse) -> None:
        """Analyze for HCC coding opportunities."""
        if not self._hcc_service:
            response.warnings.append("HCC analyzer service not available")
            return

        result = self._hcc_service.analyze_patient(
            clinical_text=request.clinical_text,
            current_icd10_codes=request.current_icd10_codes,
            lab_values=request.lab_values,
            patient_context={
                "patient_id": request.patient_id,
                "encounter_id": request.encounter_id,
            },
        )

        response.raf_score = result.current_raf_score
        response.revenue_opportunity = result.total_estimated_revenue

        for opp in result.opportunities[:request.max_results]:
            opp_dict = {
                "hcc_code": opp.hcc_code,
                "description": opp.hcc_description,
                "category": opp.category.value,
                "gap_type": opp.gap_type.value,
                "confidence": opp.capture_confidence.value,
                "raf_value": opp.raf_value,
                "estimated_revenue": opp.estimated_revenue,
                "recommended_icd10": opp.recommended_icd10,
                "documentation_needed": opp.documentation_needed,
                "coder_notes": opp.coder_notes,
            }

            if request.include_evidence:
                opp_dict["evidence"] = [
                    {
                        "source_type": ev.source_type,
                        "source_text": ev.source_text,
                        "confidence": ev.confidence,
                    }
                    for ev in opp.evidence
                ]

            response.hcc_opportunities.append(opp_dict)

        # Also generate documentation gap suggestions
        for action in result.priority_actions:
            response.documentation_gaps.append(action)

    def _handle_generate_codes(self, request: AgentRequest, response: AgentResponse) -> None:
        """Generate ICD-10 and CPT code suggestions."""
        # Extract entities first for context
        self._handle_extract_entities(request, response)

        # Use ICD-10 suggester
        if self._icd10_suggester:
            for diagnosis in response.diagnoses[:10]:
                suggestions = self._icd10_suggester.suggest_codes(
                    diagnosis.get("text", ""),
                    max_results=3,
                )
                for suggestion in suggestions:
                    response.suggested_icd10.append({
                        "code": suggestion.code,
                        "display": suggestion.display,
                        "confidence": suggestion.confidence,
                        "source_text": diagnosis.get("text", ""),
                    })

        # Use CPT suggester for procedures
        if self._cpt_suggester:
            for procedure in response.procedures[:10]:
                suggestions = self._cpt_suggester.suggest_codes(
                    procedure.get("text", ""),
                    max_results=3,
                )
                for suggestion in suggestions:
                    response.suggested_cpt.append({
                        "code": suggestion.code,
                        "display": suggestion.display,
                        "confidence": suggestion.confidence,
                        "source_text": procedure.get("text", ""),
                    })

    def _handle_build_timeline(self, request: AgentRequest, response: AgentResponse) -> None:
        """Build a patient timeline from clinical text."""
        if not self._timeline_service:
            response.warnings.append("Timeline service not available")
            return

        # First extract entities to find temporal information
        self._handle_extract_entities(request, response)

        # Build timeline from extracted entities
        events = []
        for entity in response.entities:
            event = {
                "type": entity.get("type"),
                "description": entity.get("text"),
                "codes": entity.get("codes", []),
            }
            events.append(event)

        response.timeline_events = events

    def _handle_build_phenotype(self, request: AgentRequest, response: AgentResponse) -> None:
        """Build a patient phenotype for research/trials."""
        # Extract all relevant information
        self._handle_extract_entities(request, response)
        self._handle_extract_measurements(request, response)

        # Build phenotype structure (OMOP CDM compatible)
        response.phenotype = {
            "conditions": [
                {
                    "concept_name": d.get("text"),
                    "codes": d.get("codes", []),
                    "status": "active",
                }
                for d in response.diagnoses
            ],
            "medications": [
                {
                    "concept_name": m.get("text"),
                    "codes": m.get("codes", []),
                }
                for m in response.medications
            ],
            "measurements": [
                {
                    "concept_name": m.get("name"),
                    "value": m.get("value"),
                    "unit": m.get("unit"),
                    "omop_concept_id": m.get("omop_concept_id"),
                }
                for m in response.measurements
            ],
            "procedures": [
                {
                    "concept_name": p.get("text"),
                    "codes": p.get("codes", []),
                }
                for p in response.procedures
            ],
        }

    def _handle_check_eligibility(self, request: AgentRequest, response: AgentResponse) -> None:
        """Check patient eligibility against criteria."""
        # First build phenotype
        self._handle_build_phenotype(request, response)

        if not request.eligibility_criteria:
            response.warnings.append("No eligibility criteria provided")
            return

        # Simple eligibility matching
        inclusion_met = []
        exclusion_triggered = []
        missing = []

        for criterion in request.eligibility_criteria:
            criterion_type = criterion.get("type", "")
            criterion_domain = criterion.get("domain", "")
            criterion_value = criterion.get("value")
            matched = False

            # Check against phenotype
            if criterion_domain == "condition":
                for cond in response.phenotype.get("conditions", []):
                    if criterion_value and criterion_value.lower() in cond.get("concept_name", "").lower():
                        matched = True
                        break

            elif criterion_domain == "measurement":
                for meas in response.phenotype.get("measurements", []):
                    if criterion.get("name") and criterion["name"].lower() == meas.get("concept_name", "").lower():
                        if meas.get("value") is not None:
                            matched = True
                        break

            if criterion_type == "inclusion":
                if matched:
                    inclusion_met.append(criterion)
                else:
                    missing.append(criterion)
            elif criterion_type == "exclusion":
                if matched:
                    exclusion_triggered.append(criterion)

        # Calculate eligibility
        eligible = len(exclusion_triggered) == 0 and len(missing) == 0

        response.eligibility_result = {
            "eligible": eligible,
            "inclusion_criteria_met": len(inclusion_met),
            "exclusion_criteria_triggered": len(exclusion_triggered),
            "missing_criteria": len(missing),
            "details": {
                "met": [c.get("description", "") for c in inclusion_met],
                "excluded_by": [c.get("description", "") for c in exclusion_triggered],
                "missing": [c.get("description", "") for c in missing],
            }
        }

    def _handle_clinical_reasoning(self, request: AgentRequest, response: AgentResponse) -> None:
        """Use hybrid analyzer for clinical reasoning."""
        if not self._hybrid_analyzer:
            response.warnings.append("Hybrid analyzer not available")
            return

        from app.services.hybrid_clinical_analyzer import AnalysisType

        result = self._hybrid_analyzer.analyze(
            clinical_text=request.clinical_text,
            analysis_type=AnalysisType.FREE_FORM,
            user_question=request.question or "Provide a clinical analysis of this note.",
        )

        response.analysis = result.analysis

        # Include structured context
        if result.structured_context:
            ctx = result.structured_context
            response.diagnoses = ctx.diagnoses
            response.medications = ctx.medications
            response.measurements = ctx.labs + ctx.vitals

    def _handle_summarize(self, request: AgentRequest, response: AgentResponse) -> None:
        """Generate a clinical summary."""
        if not self._hybrid_analyzer:
            response.warnings.append("Hybrid analyzer not available")
            return

        from app.services.hybrid_clinical_analyzer import AnalysisType

        result = self._hybrid_analyzer.analyze(
            clinical_text=request.clinical_text,
            analysis_type=AnalysisType.CLINICAL_SUMMARY,
        )

        response.summary = result.analysis

    def _handle_answer_question(self, request: AgentRequest, response: AgentResponse) -> None:
        """Answer a clinical question about the note."""
        if not self._hybrid_analyzer:
            response.warnings.append("Hybrid analyzer not available")
            return

        if not request.question:
            response.success = False
            response.error_message = "No question provided"
            return

        from app.services.hybrid_clinical_analyzer import AnalysisType

        result = self._hybrid_analyzer.analyze(
            clinical_text=request.clinical_text,
            analysis_type=AnalysisType.QUESTION_ANSWER,
            user_question=request.question,
        )

        response.answer = result.analysis

    # =========================================================================
    # Convenience methods for common workflows
    # =========================================================================

    def analyze_for_coding(self, clinical_text: str, current_codes: list[str] = None) -> AgentResponse:
        """
        Convenience method for medical coding workflow.

        Combines HCC analysis with code generation for billing optimization.
        """
        request = AgentRequest(
            action=ActionType.ANALYZE_HCC,
            clinical_text=clinical_text,
            use_case=UseCaseType.MEDICAL_CODING,
            current_icd10_codes=current_codes or [],
            include_evidence=True,
        )

        response = self.process(request)

        # Also generate code suggestions
        code_request = AgentRequest(
            action=ActionType.GENERATE_CODES,
            clinical_text=clinical_text,
            use_case=UseCaseType.MEDICAL_CODING,
        )
        code_response = self.process(code_request)

        response.suggested_icd10 = code_response.suggested_icd10
        response.suggested_cpt = code_response.suggested_cpt

        return response

    def analyze_for_research(self, clinical_text: str, criteria: list[Dict] = None) -> AgentResponse:
        """
        Convenience method for drug discovery/clinical trial workflow.

        Extracts patient phenotype and checks eligibility.
        """
        # Build phenotype first
        phenotype_request = AgentRequest(
            action=ActionType.BUILD_PHENOTYPE,
            clinical_text=clinical_text,
            use_case=UseCaseType.CLINICAL_TRIAL,
        )
        response = self.process(phenotype_request)

        # Check eligibility if criteria provided
        if criteria:
            eligibility_request = AgentRequest(
                action=ActionType.CHECK_ELIGIBILITY,
                clinical_text=clinical_text,
                use_case=UseCaseType.CLINICAL_TRIAL,
                eligibility_criteria=criteria,
            )
            eligibility_response = self.process(eligibility_request)
            response.eligibility_result = eligibility_response.eligibility_result

        return response

    def get_capabilities(self) -> dict[str, Any]:
        """Return the capabilities of this agent."""
        return {
            "name": "ClinicalIntelligenceAgent",
            "version": "1.0.0",
            "use_cases": [uc.value for uc in UseCaseType],
            "actions": [a.value for a in ActionType],
            "services_available": {
                "nlp_extraction": self._nlp_service is not None,
                "hcc_analysis": self._hcc_service is not None,
                "value_extraction": self._value_service is not None,
                "timeline_building": self._timeline_service is not None,
                "cohort_building": self._cohort_service is not None,
                "clinical_reasoning": self._hybrid_analyzer is not None,
                "icd10_coding": self._icd10_suggester is not None,
                "cpt_coding": self._cpt_suggester is not None,
            },
        }


# Singleton instance
_agent_instance: ClinicalIntelligenceAgent | None = None
_agent_lock = threading.Lock()


def get_clinical_intelligence_agent() -> ClinicalIntelligenceAgent:
    """Get singleton instance of the Clinical Intelligence Agent."""
    global _agent_instance
    # VP-ThreadSafety-2: Double-checked locking for thread safety
    if _agent_instance is None:
        with _agent_lock:
            if _agent_instance is None:
                _agent_instance = ClinicalIntelligenceAgent()
    return _agent_instance
