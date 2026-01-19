"""Clinical Note Generation API Endpoints.

Provides AI-powered clinical note generation:
- POST /notes/generate - Generate a clinical note
- GET /notes/templates - List available templates
- GET /notes/templates/{template_id} - Get specific template
- POST /notes/enhance - Enhance/complete partial note
- POST /notes/validate - Validate note completeness

PHI Note: Ensure clinical data is properly de-identified before
using these endpoints if sending to external LLM providers.
"""

from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/notes", tags=["Clinical Note Generation"])


# ============================================================================
# Enums and Types
# ============================================================================


class NoteTypeParam(str, Enum):
    """Types of clinical notes that can be generated."""

    SOAP = "soap"
    HP = "hp"
    PROGRESS = "progress"
    DISCHARGE = "discharge"
    PROCEDURE = "procedure"


class LLMProviderParam(str, Enum):
    """LLM provider selection."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class NoteStatusResponse(str, Enum):
    """Status of a generated note."""

    DRAFT = "draft"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NEEDS_REVIEW = "needs_review"


class ConfidenceLevelResponse(str, Enum):
    """Confidence level in generated content."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SectionStatusResponse(str, Enum):
    """Status of a note section."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    GENERATED = "generated"
    USER_PROVIDED = "user_provided"


# ============================================================================
# Request/Response Models - Input Data
# ============================================================================


class PatientDataInput(BaseModel):
    """Patient demographic and clinical data for note generation."""

    age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    sex: str | None = Field(None, pattern="^(M|F|Other)$", description="Patient sex (M, F, Other)")

    chief_complaint: str | None = Field(None, max_length=500, description="Chief complaint")
    history_present_illness: str | None = Field(
        None, max_length=5000, description="History of present illness narrative"
    )
    past_medical_history: list[str] = Field(
        default_factory=list, description="List of past medical conditions"
    )
    past_surgical_history: list[str] = Field(
        default_factory=list, description="List of past surgeries"
    )
    medications: list[str] = Field(default_factory=list, description="Current medications")
    allergies: list[str] = Field(default_factory=list, description="Known allergies")
    social_history: str | None = Field(None, max_length=1000, description="Social history")
    family_history: str | None = Field(None, max_length=1000, description="Family history")
    review_of_systems: dict[str, str] = Field(
        default_factory=dict, description="Review of systems by organ system"
    )
    vitals: dict[str, str | float | int] = Field(
        default_factory=dict, description="Vital signs (bp, hr, rr, temp, spo2, etc.)"
    )


class EncounterDataInput(BaseModel):
    """Encounter-specific data for note generation."""

    encounter_type: str = Field(
        ..., description="Encounter type (inpatient, outpatient, emergency, etc.)"
    )
    encounter_date: str | None = Field(None, description="Encounter date (ISO format)")
    provider_type: str | None = Field(None, description="Provider type (MD, DO, NP, PA)")
    location: str | None = Field(None, description="Location (clinic, hospital, ER)")

    physical_exam: dict[str, str] = Field(
        default_factory=dict, description="Physical exam findings by system"
    )
    lab_results: dict[str, str | float | dict] = Field(
        default_factory=dict, description="Laboratory results"
    )
    imaging_results: dict[str, str] = Field(
        default_factory=dict, description="Imaging study results"
    )

    diagnoses: list[str] = Field(default_factory=list, description="Diagnoses")
    icd10_codes: list[str] = Field(default_factory=list, description="ICD-10 codes")
    procedures_performed: list[str] = Field(
        default_factory=list, description="Procedures performed"
    )
    cpt_codes: list[str] = Field(default_factory=list, description="CPT codes")
    plan_items: list[str] = Field(default_factory=list, description="Plan items")

    # Optional context
    interval_history: str | None = Field(
        None, max_length=3000, description="Interval history for progress notes"
    )
    hospital_course: str | None = Field(
        None, max_length=5000, description="Hospital course for discharge"
    )
    follow_up: list[str] = Field(default_factory=list, description="Follow-up instructions")

    # For procedure notes
    procedure_name: str | None = Field(None, description="Procedure name")
    procedure_indication: str | None = Field(None, description="Procedure indication")
    procedure_findings: str | None = Field(None, description="Procedure findings")
    procedure_complications: str | None = Field(
        None, description="Complications (or 'None')"
    )
    estimated_blood_loss: str | None = Field(None, description="Estimated blood loss")
    specimens: list[str] = Field(default_factory=list, description="Specimens obtained")


# ============================================================================
# Request Models
# ============================================================================


class NoteGenerationRequest(BaseModel):
    """Request to generate a clinical note."""

    note_type: NoteTypeParam = Field(..., description="Type of note to generate")
    patient_data: PatientDataInput = Field(..., description="Patient clinical data")
    encounter_data: EncounterDataInput = Field(..., description="Encounter-specific data")
    template_id: str | None = Field(None, description="Template ID to use")
    custom_instructions: str | None = Field(
        None, max_length=1000, description="Custom generation instructions"
    )
    include_codes: bool = Field(True, description="Include ICD-10/CPT codes in output")
    provider: LLMProviderParam | None = Field(None, description="LLM provider to use")
    model: str | None = Field(None, description="Specific LLM model to use")


class NoteEnhanceRequest(BaseModel):
    """Request to enhance a partial clinical note."""

    content: str = Field(
        ..., min_length=10, max_length=50000, description="Partial note content to enhance"
    )
    note_type: NoteTypeParam = Field(..., description="Type of note")
    patient_data: PatientDataInput | None = Field(
        None, description="Additional patient data"
    )
    encounter_data: EncounterDataInput | None = Field(
        None, description="Additional encounter data"
    )
    provider: LLMProviderParam | None = Field(None, description="LLM provider to use")
    model: str | None = Field(None, description="Specific LLM model to use")


class NoteValidateRequest(BaseModel):
    """Request to validate a clinical note."""

    content: str = Field(
        ..., min_length=10, max_length=50000, description="Note content to validate"
    )
    note_type: NoteTypeParam = Field(..., description="Type of note")
    provider: LLMProviderParam | None = Field(None, description="LLM provider for AI validation")
    model: str | None = Field(None, description="Specific LLM model to use")


# ============================================================================
# Response Models
# ============================================================================


class NoteSectionResponse(BaseModel):
    """A section within a generated clinical note."""

    name: str = Field(..., description="Section name")
    key: str = Field(..., description="Section identifier")
    content: str = Field(..., description="Section content")
    required: bool = Field(..., description="Whether section is required")
    order: int = Field(..., description="Section order")
    status: SectionStatusResponse = Field(..., description="Section completion status")
    word_count: int = Field(..., description="Word count")
    warnings: list[str] = Field(default_factory=list, description="Section-specific warnings")


class NoteValidationResponse(BaseModel):
    """Validation result for a clinical note."""

    is_valid: bool = Field(..., description="Whether note passes validation")
    completeness_score: float = Field(..., ge=0, le=1, description="Completeness score (0-1)")
    missing_sections: list[str] = Field(
        default_factory=list, description="List of missing required sections"
    )
    incomplete_sections: list[str] = Field(
        default_factory=list, description="List of incomplete sections"
    )
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    suggestions: list[str] = Field(
        default_factory=list, description="Suggestions for improvement"
    )


class GeneratedNoteResponse(BaseModel):
    """Response containing generated clinical note."""

    request_id: str = Field(..., description="Unique request identifier")
    note_id: str = Field(..., description="Generated note identifier")
    note_type: NoteTypeParam = Field(..., description="Type of note generated")
    content: str = Field(..., description="Full formatted note content")
    sections: list[NoteSectionResponse] = Field(
        default_factory=list, description="Parsed note sections"
    )
    status: NoteStatusResponse = Field(..., description="Note completion status")
    confidence: ConfidenceLevelResponse = Field(..., description="Generation confidence")
    generated_at: str = Field(..., description="Generation timestamp (ISO format)")
    template_id: str | None = Field(None, description="Template used")
    model_used: str = Field(..., description="LLM model used")
    token_usage: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Estimated cost in USD")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    validation: NoteValidationResponse | None = Field(
        None, description="Validation result"
    )
    warnings: list[str] = Field(default_factory=list, description="Generation warnings")


class NoteEnhanceResponse(BaseModel):
    """Response from note enhancement."""

    request_id: str = Field(..., description="Unique request identifier")
    enhanced_content: str = Field(..., description="Enhanced note content")
    original_word_count: int = Field(..., description="Original content word count")
    enhanced_word_count: int = Field(..., description="Enhanced content word count")
    sections_enhanced: list[str] = Field(
        default_factory=list, description="Sections that were enhanced"
    )
    sections_added: list[str] = Field(
        default_factory=list, description="Sections that were added"
    )
    confidence: ConfidenceLevelResponse = Field(..., description="Enhancement confidence")
    token_usage: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Estimated cost in USD")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    warnings: list[str] = Field(default_factory=list, description="Enhancement warnings")


class NoteSectionTemplateResponse(BaseModel):
    """Template for a note section."""

    name: str = Field(..., description="Section name")
    key: str = Field(..., description="Section identifier")
    required: bool = Field(..., description="Whether section is required")
    order: int = Field(..., description="Section order")
    subsections: list[str] = Field(default_factory=list, description="Subsection names")


class NoteTemplateResponse(BaseModel):
    """Response containing a note template."""

    template_id: str = Field(..., description="Template identifier")
    note_type: NoteTypeParam = Field(..., description="Note type this template supports")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    sections: list[NoteSectionTemplateResponse] = Field(
        default_factory=list, description="Template sections"
    )


class NoteTemplatesListResponse(BaseModel):
    """Response listing available templates."""

    templates: list[NoteTemplateResponse] = Field(
        default_factory=list, description="Available templates"
    )
    total: int = Field(..., description="Total number of templates")


class NoteServiceStats(BaseModel):
    """Statistics for the note generation service."""

    total_notes_generated: int = Field(..., description="Total notes generated")
    total_tokens_used: int = Field(..., description="Total tokens used")
    total_cost_usd: float = Field(..., description="Total estimated cost")
    available_templates: int = Field(..., description="Number of available templates")


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/generate",
    response_model=GeneratedNoteResponse,
    summary="Generate a clinical note",
    description="Generate a clinical note (SOAP, H&P, Progress, Discharge, Procedure) using AI.",
)
async def generate_note(request: NoteGenerationRequest) -> GeneratedNoteResponse:
    """Generate a clinical note using AI.

    This endpoint uses an external LLM (OpenAI or Anthropic) to generate
    structured clinical documentation based on provided patient and
    encounter data.

    **Supported Note Types:**
    - `soap`: SOAP note (Subjective, Objective, Assessment, Plan)
    - `hp`: History and Physical
    - `progress`: Progress Note
    - `discharge`: Discharge Summary
    - `procedure`: Procedure Note

    **PHI Warning**: Ensure data is properly de-identified before using
    this endpoint if PHI protection is required.

    Args:
        request: Note generation request with patient and encounter data.

    Returns:
        GeneratedNoteResponse with the generated note content and metadata.
    """
    request_id = str(uuid4())

    try:
        from app.services.note_generator import (
            EncounterData,
            NoteGenerationRequest as ServiceRequest,
            NoteType,
            PatientData,
            get_note_generator_service,
        )
        from app.services.llm_service import LLMProvider

        service = get_note_generator_service()

        # Map note type
        note_type_map = {
            NoteTypeParam.SOAP: NoteType.SOAP,
            NoteTypeParam.HP: NoteType.HP,
            NoteTypeParam.PROGRESS: NoteType.PROGRESS,
            NoteTypeParam.DISCHARGE: NoteType.DISCHARGE,
            NoteTypeParam.PROCEDURE: NoteType.PROCEDURE,
        }
        note_type = note_type_map.get(request.note_type, NoteType.SOAP)

        # Map provider
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        # Convert patient data
        patient_data = PatientData(
            age=request.patient_data.age,
            sex=request.patient_data.sex,
            chief_complaint=request.patient_data.chief_complaint,
            history_present_illness=request.patient_data.history_present_illness,
            past_medical_history=request.patient_data.past_medical_history,
            past_surgical_history=request.patient_data.past_surgical_history,
            medications=request.patient_data.medications,
            allergies=request.patient_data.allergies,
            social_history=request.patient_data.social_history,
            family_history=request.patient_data.family_history,
            review_of_systems=request.patient_data.review_of_systems,
            vitals=request.patient_data.vitals,
        )

        # Convert encounter data
        encounter_data = EncounterData(
            encounter_type=request.encounter_data.encounter_type,
            encounter_date=request.encounter_data.encounter_date,
            provider_type=request.encounter_data.provider_type,
            location=request.encounter_data.location,
            physical_exam=request.encounter_data.physical_exam,
            lab_results=request.encounter_data.lab_results,
            imaging_results=request.encounter_data.imaging_results,
            diagnoses=request.encounter_data.diagnoses,
            icd10_codes=request.encounter_data.icd10_codes,
            procedures_performed=request.encounter_data.procedures_performed,
            cpt_codes=request.encounter_data.cpt_codes,
            plan_items=request.encounter_data.plan_items,
            interval_history=request.encounter_data.interval_history,
            hospital_course=request.encounter_data.hospital_course,
            follow_up=request.encounter_data.follow_up,
            procedure_name=request.encounter_data.procedure_name,
            procedure_indication=request.encounter_data.procedure_indication,
            procedure_findings=request.encounter_data.procedure_findings,
            procedure_complications=request.encounter_data.procedure_complications,
            estimated_blood_loss=request.encounter_data.estimated_blood_loss,
            specimens=request.encounter_data.specimens,
        )

        # Create service request
        service_request = ServiceRequest(
            note_type=note_type,
            patient_data=patient_data,
            encounter_data=encounter_data,
            template_id=request.template_id,
            custom_instructions=request.custom_instructions,
            include_codes=request.include_codes,
            provider=provider,
            model=request.model,
        )

        # Generate note
        result = await service.generate_note(service_request)

        # Convert sections
        sections = [
            NoteSectionResponse(
                name=s.name,
                key=s.key,
                content=s.content,
                required=s.required,
                order=s.order,
                status=SectionStatusResponse(s.status.value),
                word_count=s.word_count,
                warnings=s.warnings,
            )
            for s in result.sections
        ]

        # Convert validation
        validation = None
        if result.validation:
            validation = NoteValidationResponse(
                is_valid=result.validation.is_valid,
                completeness_score=result.validation.completeness_score,
                missing_sections=result.validation.missing_sections,
                incomplete_sections=result.validation.incomplete_sections,
                warnings=result.validation.warnings,
                suggestions=result.validation.suggestions,
            )

        return GeneratedNoteResponse(
            request_id=request_id,
            note_id=result.note_id,
            note_type=request.note_type,
            content=result.content,
            sections=sections,
            status=NoteStatusResponse(result.status.value),
            confidence=ConfidenceLevelResponse(result.confidence.value),
            generated_at=result.generated_at,
            template_id=result.template_id,
            model_used=result.model_used,
            token_usage=result.token_usage,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
            validation=validation,
            warnings=result.warnings,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Note generation failed: {str(e)}"
        )


@router.get(
    "/templates",
    response_model=NoteTemplatesListResponse,
    summary="List available note templates",
    description="Get all available clinical note templates.",
)
async def list_templates(
    note_type: NoteTypeParam | None = Query(
        None, description="Filter by note type"
    ),
) -> NoteTemplatesListResponse:
    """List available note templates.

    Returns all configured templates for clinical note generation,
    optionally filtered by note type.

    Args:
        note_type: Optional filter by note type.

    Returns:
        NoteTemplatesListResponse with available templates.
    """
    try:
        from app.services.note_generator import NoteType, get_note_generator_service

        service = get_note_generator_service()

        # Map note type for filter
        filter_type = None
        if note_type:
            note_type_map = {
                NoteTypeParam.SOAP: NoteType.SOAP,
                NoteTypeParam.HP: NoteType.HP,
                NoteTypeParam.PROGRESS: NoteType.PROGRESS,
                NoteTypeParam.DISCHARGE: NoteType.DISCHARGE,
                NoteTypeParam.PROCEDURE: NoteType.PROCEDURE,
            }
            filter_type = note_type_map.get(note_type)

        templates = service.get_templates(filter_type)

        # Convert to response format
        response_templates = []
        for t in templates:
            note_type_response = NoteTypeParam(t.note_type.value)
            sections = [
                NoteSectionTemplateResponse(
                    name=s.name,
                    key=s.key,
                    required=s.required,
                    order=s.order,
                    subsections=s.subsections,
                )
                for s in t.sections
            ]
            response_templates.append(
                NoteTemplateResponse(
                    template_id=t.template_id,
                    note_type=note_type_response,
                    name=t.name,
                    description=t.description,
                    sections=sections,
                )
            )

        return NoteTemplatesListResponse(
            templates=response_templates,
            total=len(response_templates),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list templates: {str(e)}"
        )


@router.get(
    "/templates/{template_id}",
    response_model=NoteTemplateResponse,
    summary="Get a specific template",
    description="Get details of a specific note template by ID.",
)
async def get_template(template_id: str) -> NoteTemplateResponse:
    """Get a specific note template.

    Args:
        template_id: Template identifier.

    Returns:
        NoteTemplateResponse with template details.
    """
    try:
        from app.services.note_generator import get_note_generator_service

        service = get_note_generator_service()
        template = service.get_template(template_id)

        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {template_id}",
            )

        note_type_response = NoteTypeParam(template.note_type.value)
        sections = [
            NoteSectionTemplateResponse(
                name=s.name,
                key=s.key,
                required=s.required,
                order=s.order,
                subsections=s.subsections,
            )
            for s in template.sections
        ]

        return NoteTemplateResponse(
            template_id=template.template_id,
            note_type=note_type_response,
            name=template.name,
            description=template.description,
            sections=sections,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get template: {str(e)}"
        )


@router.post(
    "/enhance",
    response_model=NoteEnhanceResponse,
    summary="Enhance a partial note",
    description="Enhance or complete a partial clinical note using AI.",
)
async def enhance_note(request: NoteEnhanceRequest) -> NoteEnhanceResponse:
    """Enhance a partial clinical note.

    Takes incomplete note content and uses AI to:
    - Identify missing sections
    - Complete partial sections
    - Improve documentation quality

    **PHI Warning**: Ensure data is properly de-identified before using
    this endpoint if PHI protection is required.

    Args:
        request: Enhancement request with partial content.

    Returns:
        NoteEnhanceResponse with enhanced content.
    """
    request_id = str(uuid4())

    try:
        from app.services.note_generator import (
            EncounterData,
            NoteType,
            PatientData,
            get_note_generator_service,
        )
        from app.services.llm_service import LLMProvider

        service = get_note_generator_service()

        # Map note type
        note_type_map = {
            NoteTypeParam.SOAP: NoteType.SOAP,
            NoteTypeParam.HP: NoteType.HP,
            NoteTypeParam.PROGRESS: NoteType.PROGRESS,
            NoteTypeParam.DISCHARGE: NoteType.DISCHARGE,
            NoteTypeParam.PROCEDURE: NoteType.PROCEDURE,
        }
        note_type = note_type_map.get(request.note_type, NoteType.SOAP)

        # Map provider
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        # Convert optional patient data
        patient_data = None
        if request.patient_data:
            patient_data = PatientData(
                age=request.patient_data.age,
                sex=request.patient_data.sex,
                chief_complaint=request.patient_data.chief_complaint,
                history_present_illness=request.patient_data.history_present_illness,
                past_medical_history=request.patient_data.past_medical_history,
                past_surgical_history=request.patient_data.past_surgical_history,
                medications=request.patient_data.medications,
                allergies=request.patient_data.allergies,
                social_history=request.patient_data.social_history,
                family_history=request.patient_data.family_history,
                review_of_systems=request.patient_data.review_of_systems,
                vitals=request.patient_data.vitals,
            )

        # Convert optional encounter data
        encounter_data = None
        if request.encounter_data:
            encounter_data = EncounterData(
                encounter_type=request.encounter_data.encounter_type,
                encounter_date=request.encounter_data.encounter_date,
                provider_type=request.encounter_data.provider_type,
                location=request.encounter_data.location,
                physical_exam=request.encounter_data.physical_exam,
                lab_results=request.encounter_data.lab_results,
                imaging_results=request.encounter_data.imaging_results,
                diagnoses=request.encounter_data.diagnoses,
                icd10_codes=request.encounter_data.icd10_codes,
                procedures_performed=request.encounter_data.procedures_performed,
                cpt_codes=request.encounter_data.cpt_codes,
                plan_items=request.encounter_data.plan_items,
                interval_history=request.encounter_data.interval_history,
                hospital_course=request.encounter_data.hospital_course,
                follow_up=request.encounter_data.follow_up,
                procedure_name=request.encounter_data.procedure_name,
                procedure_indication=request.encounter_data.procedure_indication,
                procedure_findings=request.encounter_data.procedure_findings,
                procedure_complications=request.encounter_data.procedure_complications,
                estimated_blood_loss=request.encounter_data.estimated_blood_loss,
                specimens=request.encounter_data.specimens,
            )

        # Enhance note
        result = await service.enhance_note(
            partial_content=request.content,
            note_type=note_type,
            patient_data=patient_data,
            encounter_data=encounter_data,
            provider=provider,
            model=request.model,
        )

        return NoteEnhanceResponse(
            request_id=request_id,
            enhanced_content=result.enhanced_content,
            original_word_count=len(result.original_content.split()),
            enhanced_word_count=len(result.enhanced_content.split()),
            sections_enhanced=result.sections_enhanced,
            sections_added=result.sections_added,
            confidence=ConfidenceLevelResponse(result.confidence.value),
            token_usage=result.token_usage,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
            warnings=result.warnings,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Note enhancement failed: {str(e)}"
        )


@router.post(
    "/validate",
    response_model=NoteValidationResponse,
    summary="Validate a clinical note",
    description="Validate a clinical note for completeness and documentation quality.",
)
async def validate_note(request: NoteValidateRequest) -> NoteValidationResponse:
    """Validate a clinical note.

    Analyzes note content to check:
    - Required section completeness
    - Documentation quality
    - Potential compliance issues

    Args:
        request: Validation request with note content.

    Returns:
        NoteValidationResponse with validation results.
    """
    try:
        from app.services.note_generator import NoteType, get_note_generator_service
        from app.services.llm_service import LLMProvider

        service = get_note_generator_service()

        # Map note type
        note_type_map = {
            NoteTypeParam.SOAP: NoteType.SOAP,
            NoteTypeParam.HP: NoteType.HP,
            NoteTypeParam.PROGRESS: NoteType.PROGRESS,
            NoteTypeParam.DISCHARGE: NoteType.DISCHARGE,
            NoteTypeParam.PROCEDURE: NoteType.PROCEDURE,
        }
        note_type = note_type_map.get(request.note_type, NoteType.SOAP)

        # Map provider
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        # Validate note
        result = await service.validate_note(
            content=request.content,
            note_type=note_type,
            provider=provider,
            model=request.model,
        )

        return NoteValidationResponse(
            is_valid=result.is_valid,
            completeness_score=result.completeness_score,
            missing_sections=result.missing_sections,
            incomplete_sections=result.incomplete_sections,
            warnings=result.warnings,
            suggestions=result.suggestions,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Note validation failed: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=NoteServiceStats,
    summary="Get note generation statistics",
    description="Get usage statistics for the note generation service.",
)
async def get_stats() -> NoteServiceStats:
    """Get note generation service statistics.

    Returns usage metrics including total notes generated,
    tokens used, and estimated costs.

    Returns:
        NoteServiceStats with service metrics.
    """
    try:
        from app.services.note_generator import get_note_generator_service

        service = get_note_generator_service()
        stats = service.get_stats()

        return NoteServiceStats(
            total_notes_generated=stats.get("total_notes_generated", 0),
            total_tokens_used=stats.get("total_tokens_used", 0),
            total_cost_usd=round(stats.get("total_cost_usd", 0), 4),
            available_templates=stats.get("available_templates", 0),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get stats: {str(e)}"
        )


@router.get(
    "/note-types",
    summary="Get supported note types",
    description="Get list of supported clinical note types with descriptions.",
)
async def get_note_types() -> dict:
    """Get list of supported note types.

    Returns descriptions and typical use cases for each
    supported clinical note type.

    Returns:
        Dictionary with note type information.
    """
    return {
        "note_types": [
            {
                "type": "soap",
                "name": "SOAP Note",
                "description": "Subjective, Objective, Assessment, Plan format for outpatient encounters",
                "typical_use": "Primary care, specialty clinic visits",
            },
            {
                "type": "hp",
                "name": "History and Physical",
                "description": "Comprehensive H&P for admissions or new patient evaluations",
                "typical_use": "Hospital admissions, new patient encounters",
            },
            {
                "type": "progress",
                "name": "Progress Note",
                "description": "Daily or interval progress documentation",
                "typical_use": "Inpatient daily rounds, follow-up visits",
            },
            {
                "type": "discharge",
                "name": "Discharge Summary",
                "description": "Comprehensive summary for hospital discharge",
                "typical_use": "Hospital discharge, transitions of care",
            },
            {
                "type": "procedure",
                "name": "Procedure Note",
                "description": "Documentation of medical procedures",
                "typical_use": "Surgical procedures, invasive tests",
            },
        ]
    }


# ============================================================================
# Patient Summary Models
# ============================================================================


class PatientFactInput(BaseModel):
    """A clinical fact about a patient."""

    fact_id: str = Field(..., description="Unique fact identifier")
    fact_type: str = Field(
        ..., description="Type of fact (problem, medication, lab, vital, allergy, encounter)"
    )
    description: str = Field(..., max_length=1000, description="Fact description")
    code: str | None = Field(None, description="Clinical code (ICD-10, RxNorm, LOINC)")
    code_system: str | None = Field(None, description="Code system name")
    value: str | None = Field(None, description="Value (for labs, vitals)")
    unit: str | None = Field(None, description="Unit of measurement")
    date: str | None = Field(None, description="Date of fact (ISO format)")
    status: str | None = Field(None, description="Status (active, resolved, etc.)")
    source_document_id: str | None = Field(None, description="Source document ID")
    confidence: float = Field(1.0, ge=0, le=1, description="Confidence score")


class PatientSummaryRequest(BaseModel):
    """Request to generate a patient summary."""

    patient_id: str = Field(..., description="Patient identifier")
    facts: list[PatientFactInput] = Field(..., description="Clinical facts about the patient")
    focus_areas: list[str] = Field(
        default_factory=list,
        description="Focus areas: problems, meds, visits, labs, etc.",
    )
    max_length: int | None = Field(None, ge=100, le=5000, description="Maximum summary length")
    include_citations: bool = Field(True, description="Include fact citations")
    provider: LLMProviderParam | None = Field(None, description="LLM provider to use")
    model: str | None = Field(None, description="Specific LLM model to use")


class FactCitationResponse(BaseModel):
    """Citation linking summary text to source facts."""

    text_span: str = Field(..., description="The text in the summary")
    fact_id: str = Field(..., description="ID of the source fact")
    fact_type: str = Field(..., description="Type of the source fact")
    source_description: str = Field(..., description="Description of the source")


class PatientSummaryResponse(BaseModel):
    """Response containing generated patient summary."""

    summary_id: str = Field(..., description="Unique summary identifier")
    patient_id: str = Field(..., description="Patient identifier")
    content: str = Field(..., description="Full summary content")
    sections: dict[str, str] = Field(default_factory=dict, description="Summary sections")
    citations: list[FactCitationResponse] = Field(
        default_factory=list, description="Fact citations"
    )
    generated_at: str = Field(..., description="Generation timestamp")
    focus_areas: list[str] = Field(default_factory=list, description="Focus areas used")
    fact_count: int = Field(..., description="Number of facts processed")
    model_used: str = Field(..., description="LLM model used")
    token_usage: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Estimated cost in USD")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    confidence: ConfidenceLevelResponse = Field(..., description="Summary confidence")


# ============================================================================
# Note History Models
# ============================================================================


class NoteHistoryEntryResponse(BaseModel):
    """Entry in the note generation history."""

    note_id: str = Field(..., description="Note identifier")
    note_type: NoteTypeParam = Field(..., description="Type of note")
    patient_id: str | None = Field(None, description="Patient identifier")
    template_id: str | None = Field(None, description="Template used")
    status: NoteStatusResponse = Field(..., description="Note status")
    generated_at: str = Field(..., description="Generation timestamp")
    model_used: str = Field(..., description="LLM model used")
    token_usage: int = Field(..., description="Tokens used")
    cost_usd: float = Field(..., description="Cost in USD")
    preview: str = Field(..., description="Content preview")


class NoteHistoryResponse(BaseModel):
    """Response containing note generation history."""

    history: list[NoteHistoryEntryResponse] = Field(
        default_factory=list, description="History entries"
    )
    total: int = Field(..., description="Total entries")


# ============================================================================
# Template Customization Models
# ============================================================================


class SectionTemplateInput(BaseModel):
    """Input for a custom note section."""

    name: str = Field(..., description="Section name")
    key: str = Field(..., description="Section key (unique identifier)")
    required: bool = Field(True, description="Whether section is required")
    order: int = Field(0, description="Section order")
    prompt_hint: str | None = Field(None, description="Prompt hint for generation")
    subsections: list[str] = Field(default_factory=list, description="Subsection names")


class TemplateCustomizationRequest(BaseModel):
    """Request to customize a note template."""

    base_template_id: str = Field(..., description="Base template to customize")
    new_template_id: str = Field(..., description="ID for the new template")
    name: str = Field(..., max_length=100, description="New template name")
    description: str | None = Field(None, max_length=500, description="Template description")
    sections_to_add: list[SectionTemplateInput] = Field(
        default_factory=list, description="Sections to add"
    )
    sections_to_remove: list[str] = Field(
        default_factory=list, description="Section keys to remove"
    )
    section_order: list[str] | None = Field(
        None, description="Ordered list of section keys"
    )
    custom_prompts: dict[str, str] = Field(
        default_factory=dict, description="Custom prompts by section key"
    )


# ============================================================================
# New Endpoints
# ============================================================================


@router.post(
    "/summarize",
    response_model=PatientSummaryResponse,
    summary="Generate a patient summary",
    description="Generate a concise patient summary from clinical facts using AI.",
)
async def summarize_patient(request: PatientSummaryRequest) -> PatientSummaryResponse:
    """Generate a patient summary from clinical facts.

    Takes a list of clinical facts (problems, medications, labs, etc.)
    and generates a concise, clinically useful summary.

    **Features:**
    - Organizes information by clinical relevance
    - Includes fact citations for traceability
    - Supports focus areas to emphasize specific data
    - HIPAA-compliant generation (no hallucinated PHI)

    **PHI Warning**: Ensure data is properly de-identified before using
    this endpoint if PHI protection is required.

    Args:
        request: Summary generation request with patient facts.

    Returns:
        PatientSummaryResponse with generated summary and citations.
    """
    try:
        from app.services.note_generator import (
            PatientFact,
            PatientSummaryRequest as ServiceRequest,
            get_patient_summary_service,
        )
        from app.services.llm_service import LLMProvider

        service = get_patient_summary_service()

        # Map provider
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        # Convert facts
        facts = [
            PatientFact(
                fact_id=f.fact_id,
                fact_type=f.fact_type,
                description=f.description,
                code=f.code,
                code_system=f.code_system,
                value=f.value,
                unit=f.unit,
                date=f.date,
                status=f.status,
                source_document_id=f.source_document_id,
                confidence=f.confidence,
            )
            for f in request.facts
        ]

        # Create service request
        service_request = ServiceRequest(
            patient_id=request.patient_id,
            facts=facts,
            focus_areas=request.focus_areas,
            max_length=request.max_length,
            include_citations=request.include_citations,
            provider=provider,
            model=request.model,
        )

        # Generate summary
        result = await service.generate_summary(service_request)

        # Convert citations
        citations = [
            FactCitationResponse(
                text_span=c.text_span,
                fact_id=c.fact_id,
                fact_type=c.fact_type,
                source_description=c.source_description,
            )
            for c in result.citations
        ]

        return PatientSummaryResponse(
            summary_id=result.summary_id,
            patient_id=result.patient_id,
            content=result.content,
            sections=result.sections,
            citations=citations,
            generated_at=result.generated_at,
            focus_areas=result.focus_areas,
            fact_count=result.fact_count,
            model_used=result.model_used,
            token_usage=result.token_usage,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
            confidence=ConfidenceLevelResponse(result.confidence.value),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Summary generation failed: {str(e)}"
        )


@router.get(
    "/history",
    response_model=NoteHistoryResponse,
    summary="Get note generation history",
    description="Get the history of generated clinical notes.",
)
async def get_history(
    limit: int = Query(50, ge=1, le=100, description="Maximum entries to return"),
    note_type: NoteTypeParam | None = Query(None, description="Filter by note type"),
    patient_id: str | None = Query(None, description="Filter by patient ID"),
) -> NoteHistoryResponse:
    """Get note generation history.

    Returns a list of recently generated notes with metadata.
    Can be filtered by note type or patient ID.

    Args:
        limit: Maximum number of entries to return.
        note_type: Optional filter by note type.
        patient_id: Optional filter by patient ID.

    Returns:
        NoteHistoryResponse with history entries.
    """
    try:
        from app.services.note_generator import (
            NoteType,
            get_note_generator_service,
            get_note_history,
        )

        service = get_note_generator_service()

        # Map note type for filter
        filter_type = None
        if note_type:
            note_type_map = {
                NoteTypeParam.SOAP: NoteType.SOAP,
                NoteTypeParam.HP: NoteType.HP,
                NoteTypeParam.PROGRESS: NoteType.PROGRESS,
                NoteTypeParam.DISCHARGE: NoteType.DISCHARGE,
                NoteTypeParam.PROCEDURE: NoteType.PROCEDURE,
            }
            filter_type = note_type_map.get(note_type)

        # Get history
        history = get_note_history(
            service,
            limit=limit,
            note_type=filter_type,
            patient_id=patient_id,
        )

        # Convert to response
        entries = [
            NoteHistoryEntryResponse(
                note_id=h.note_id,
                note_type=NoteTypeParam(h.note_type.value),
                patient_id=h.patient_id,
                template_id=h.template_id,
                status=NoteStatusResponse(h.status.value),
                generated_at=h.generated_at,
                model_used=h.model_used,
                token_usage=h.token_usage,
                cost_usd=round(h.cost_usd, 6),
                preview=h.preview,
            )
            for h in history
        ]

        return NoteHistoryResponse(
            history=entries,
            total=len(entries),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get history: {str(e)}"
        )


@router.put(
    "/templates/{template_id}",
    response_model=NoteTemplateResponse,
    summary="Customize a note template",
    description="Create a customized template based on an existing one.",
)
async def customize_template(
    template_id: str,
    request: TemplateCustomizationRequest,
) -> NoteTemplateResponse:
    """Customize a note template.

    Creates a new template based on an existing one with customizations:
    - Add or remove sections
    - Reorder sections
    - Set custom prompts for sections

    The original template is not modified.

    Args:
        template_id: ID for the new customized template.
        request: Customization details.

    Returns:
        NoteTemplateResponse with the new template.
    """
    try:
        from app.services.note_generator import (
            CustomTemplateRequest,
            NoteSectionTemplate,
            customize_template as service_customize,
            get_note_generator_service,
        )

        service = get_note_generator_service()

        # Override template_id from path
        request.new_template_id = template_id

        # Convert sections to add
        sections_to_add = [
            NoteSectionTemplate(
                name=s.name,
                key=s.key,
                required=s.required,
                order=s.order,
                prompt_template=s.prompt_hint,
                subsections=s.subsections,
            )
            for s in request.sections_to_add
        ]

        # Create service request
        service_request = CustomTemplateRequest(
            base_template_id=request.base_template_id,
            new_template_id=request.new_template_id,
            name=request.name,
            description=request.description,
            sections_to_add=sections_to_add,
            sections_to_remove=request.sections_to_remove,
            section_order=request.section_order,
            custom_prompts=request.custom_prompts,
        )

        # Create customized template
        template = service_customize(service, service_request)

        # Convert to response
        note_type_response = NoteTypeParam(template.note_type.value)
        sections = [
            NoteSectionTemplateResponse(
                name=s.name,
                key=s.key,
                required=s.required,
                order=s.order,
                subsections=s.subsections,
            )
            for s in template.sections
        ]

        return NoteTemplateResponse(
            template_id=template.template_id,
            note_type=note_type_response,
            name=template.name,
            description=template.description,
            sections=sections,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Template customization failed: {str(e)}"
        )
