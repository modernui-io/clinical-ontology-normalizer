"""
Clinical Intelligence Agent API Endpoints.

Provides REST API access to the Clinical Intelligence Agent for:
- Drug discovery and clinical trial data extraction
- Medical coding and billing support (Ambient Scribe)
- Clinical reasoning and Q&A
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.clinical_intelligence_agent import (
    ClinicalIntelligenceAgent,
    AgentRequest,
    AgentResponse,
    ActionType,
    UseCaseType,
    get_clinical_intelligence_agent,
)

router = APIRouter(prefix="/agent", tags=["Clinical Intelligence Agent"])


# =============================================================================
# Request/Response Models
# =============================================================================


class AgentRequestModel(BaseModel):
    """Request model for agent API."""
    action: str = Field(..., description="Action to perform (e.g., 'extract_entities', 'analyze_hcc')")
    clinical_text: str = Field(..., description="Clinical text to analyze")
    use_case: str = Field(default="general_analysis", description="Use case context")

    # Optional context
    patient_id: Optional[str] = None
    encounter_id: Optional[str] = None
    current_icd10_codes: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    lab_values: List[Dict[str, Any]] = Field(default_factory=list)

    # For reasoning/Q&A
    question: Optional[str] = None

    # For eligibility checking
    eligibility_criteria: List[Dict[str, Any]] = Field(default_factory=list)

    # Options
    include_normalized_codes: bool = True
    include_confidence_scores: bool = True
    include_evidence: bool = True
    max_results: int = 50

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "action": "extract_entities",
                    "clinical_text": "Patient has type 2 diabetes with neuropathy, on metformin 1000mg BID.",
                    "use_case": "medical_coding"
                },
                {
                    "action": "analyze_hcc",
                    "clinical_text": "62yo male with CHF (EF 35%), CKD stage 4, and COPD on home oxygen.",
                    "use_case": "medical_coding",
                    "current_icd10_codes": ["I50.9"]
                },
                {
                    "action": "answer_question",
                    "clinical_text": "Patient presents with chest pain, troponin elevated at 2.4 ng/mL...",
                    "question": "What is the most likely diagnosis?"
                }
            ]
        }
    }


class CodingAnalysisRequest(BaseModel):
    """Request for medical coding analysis."""
    clinical_text: str = Field(..., description="Clinical note to analyze")
    current_icd10_codes: List[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "clinical_text": "Patient with diabetes, neuropathy, and CKD stage 3.",
                    "current_icd10_codes": ["E11.9"]
                }
            ]
        }
    }


class ResearchAnalysisRequest(BaseModel):
    """Request for research/clinical trial analysis."""
    clinical_text: str = Field(..., description="Clinical note to analyze")
    eligibility_criteria: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of eligibility criteria to check against"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "clinical_text": "62yo male with type 2 diabetes, HbA1c 8.2%, on metformin.",
                    "eligibility_criteria": [
                        {"type": "inclusion", "domain": "condition", "value": "diabetes", "description": "Has diabetes"},
                        {"type": "exclusion", "domain": "condition", "value": "cancer", "description": "No active cancer"}
                    ]
                }
            ]
        }
    }


class QuestionRequest(BaseModel):
    """Request for clinical Q&A."""
    clinical_text: str = Field(..., description="Clinical note to analyze")
    question: str = Field(..., description="Question to answer about the note")


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/process", response_model=Dict[str, Any])
async def process_request(request: AgentRequestModel) -> Dict[str, Any]:
    """
    Process a generic agent request.

    This is the main entry point for the Clinical Intelligence Agent.
    Supports all action types and use cases.
    """
    agent = get_clinical_intelligence_agent()

    try:
        action = ActionType(request.action)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action: {request.action}. Valid actions: {[a.value for a in ActionType]}"
        )

    try:
        use_case = UseCaseType(request.use_case)
    except ValueError:
        use_case = UseCaseType.GENERAL_ANALYSIS

    agent_request = AgentRequest(
        action=action,
        clinical_text=request.clinical_text,
        use_case=use_case,
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        current_icd10_codes=request.current_icd10_codes,
        current_medications=request.current_medications,
        lab_values=request.lab_values,
        question=request.question,
        eligibility_criteria=request.eligibility_criteria,
        include_normalized_codes=request.include_normalized_codes,
        include_confidence_scores=request.include_confidence_scores,
        include_evidence=request.include_evidence,
        max_results=request.max_results,
    )

    response = agent.process(agent_request)

    return _response_to_dict(response)


@router.post("/coding/analyze", response_model=Dict[str, Any])
async def analyze_for_coding(request: CodingAnalysisRequest) -> Dict[str, Any]:
    """
    Analyze clinical text for medical coding.

    Combines HCC risk adjustment analysis with ICD-10/CPT code suggestions.
    Ideal for:
    - Revenue cycle optimization
    - Ambient Scribe documentation
    - CDI (Clinical Documentation Improvement)
    """
    agent = get_clinical_intelligence_agent()

    response = agent.analyze_for_coding(
        clinical_text=request.clinical_text,
        current_codes=request.current_icd10_codes,
    )

    return _response_to_dict(response)


@router.post("/research/analyze", response_model=Dict[str, Any])
async def analyze_for_research(request: ResearchAnalysisRequest) -> Dict[str, Any]:
    """
    Analyze clinical text for research purposes.

    Extracts patient phenotype and checks eligibility against criteria.
    Ideal for:
    - Drug discovery cohort identification
    - Clinical trial eligibility screening
    - Retrospective research
    """
    agent = get_clinical_intelligence_agent()

    response = agent.analyze_for_research(
        clinical_text=request.clinical_text,
        criteria=request.eligibility_criteria,
    )

    return _response_to_dict(response)


@router.post("/qa", response_model=Dict[str, Any])
async def answer_question(request: QuestionRequest) -> Dict[str, Any]:
    """
    Answer a clinical question about a note.

    Uses hybrid deterministic + LLM analysis for grounded reasoning.
    """
    agent = get_clinical_intelligence_agent()

    agent_request = AgentRequest(
        action=ActionType.ANSWER_QUESTION,
        clinical_text=request.clinical_text,
        question=request.question,
    )

    response = agent.process(agent_request)

    return _response_to_dict(response)


@router.post("/summarize", response_model=Dict[str, Any])
async def summarize_note(clinical_text: str) -> Dict[str, Any]:
    """
    Generate a clinical summary of the note.
    """
    agent = get_clinical_intelligence_agent()

    agent_request = AgentRequest(
        action=ActionType.SUMMARIZE,
        clinical_text=clinical_text,
    )

    response = agent.process(agent_request)

    return _response_to_dict(response)


@router.get("/capabilities", response_model=Dict[str, Any])
async def get_capabilities() -> Dict[str, Any]:
    """
    Get the capabilities of the Clinical Intelligence Agent.

    Returns available actions, use cases, and which services are loaded.
    """
    agent = get_clinical_intelligence_agent()
    return agent.get_capabilities()


@router.get("/actions", response_model=List[Dict[str, str]])
async def list_actions() -> List[Dict[str, str]]:
    """
    List all available actions with descriptions.
    """
    return [
        {"action": "extract_entities", "description": "Extract clinical entities (diagnoses, medications, etc.)"},
        {"action": "extract_measurements", "description": "Extract lab values and vital signs"},
        {"action": "extract_medications", "description": "Extract medications with doses"},
        {"action": "extract_diagnoses", "description": "Extract diagnoses and conditions"},
        {"action": "extract_procedures", "description": "Extract procedures"},
        {"action": "analyze_hcc", "description": "Analyze for HCC coding opportunities and RAF score"},
        {"action": "analyze_documentation", "description": "Analyze documentation quality"},
        {"action": "generate_codes", "description": "Generate ICD-10 and CPT code suggestions"},
        {"action": "check_eligibility", "description": "Check patient eligibility against criteria"},
        {"action": "build_timeline", "description": "Build patient timeline from text"},
        {"action": "build_phenotype", "description": "Build OMOP CDM-compatible patient phenotype"},
        {"action": "build_cohort_query", "description": "Build cohort query from criteria"},
        {"action": "clinical_reasoning", "description": "Perform clinical reasoning over extracted data"},
        {"action": "summarize", "description": "Generate clinical summary"},
        {"action": "answer_question", "description": "Answer a clinical question about the note"},
    ]


@router.get("/use-cases", response_model=List[Dict[str, str]])
async def list_use_cases() -> List[Dict[str, str]]:
    """
    List all supported use cases with descriptions.
    """
    return [
        {"use_case": "drug_discovery", "description": "Extract data for drug discovery research"},
        {"use_case": "clinical_trial", "description": "Screen patients for clinical trial eligibility"},
        {"use_case": "medical_coding", "description": "Medical coding and billing optimization"},
        {"use_case": "ambient_scribe", "description": "Real-time documentation assistance"},
        {"use_case": "quality_measure", "description": "Quality measure and compliance checking"},
        {"use_case": "general_analysis", "description": "General clinical text analysis"},
    ]


# =============================================================================
# Helper Functions
# =============================================================================


def _response_to_dict(response: AgentResponse) -> Dict[str, Any]:
    """Convert AgentResponse to dictionary for JSON serialization."""
    result = {
        "success": response.success,
        "action": response.action.value,
        "use_case": response.use_case.value,
        "processing_time_ms": round(response.processing_time_ms, 2),
    }

    # Only include non-empty fields
    if response.entities:
        result["entities"] = response.entities
    if response.measurements:
        result["measurements"] = response.measurements
    if response.diagnoses:
        result["diagnoses"] = response.diagnoses
    if response.medications:
        result["medications"] = response.medications
    if response.procedures:
        result["procedures"] = response.procedures

    if response.hcc_opportunities:
        result["hcc_analysis"] = {
            "opportunities": response.hcc_opportunities,
            "current_raf_score": response.raf_score,
            "revenue_opportunity": response.revenue_opportunity,
            "documentation_gaps": response.documentation_gaps,
        }

    if response.suggested_icd10:
        result["suggested_icd10"] = response.suggested_icd10
    if response.suggested_cpt:
        result["suggested_cpt"] = response.suggested_cpt

    if response.eligibility_result:
        result["eligibility"] = response.eligibility_result

    if response.timeline_events:
        result["timeline"] = response.timeline_events
    if response.phenotype:
        result["phenotype"] = response.phenotype
    if response.cohort_query:
        result["cohort_query"] = response.cohort_query

    if response.analysis:
        result["analysis"] = response.analysis
    if response.summary:
        result["summary"] = response.summary
    if response.answer:
        result["answer"] = response.answer

    if response.error_message:
        result["error"] = response.error_message
    if response.warnings:
        result["warnings"] = response.warnings

    return result
