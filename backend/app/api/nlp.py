"""NLP Entity Extraction API Endpoints.

Provides clinical NLP entity extraction services:
- Extract clinical entities from text
- Batch extraction for multiple documents
- List available NLP models
- Normalize extracted entities to standard codes
"""

import time
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError


router = APIRouter(prefix="/nlp", tags=["NLP"])


# ============================================================================
# Enums (matching service enums for API layer)
# ============================================================================


class EntityTypeEnum(str, Enum):
    """Types of clinical entities that can be extracted."""

    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    LAB_RESULT = "lab_result"
    VITAL_SIGN = "vital_sign"
    ANATOMICAL_LOCATION = "anatomical_location"
    TEMPORAL = "temporal"
    SYMPTOM = "symptom"
    ALLERGY = "allergy"


class AssertionStatusEnum(str, Enum):
    """Assertion status for extracted entities."""

    PRESENT = "present"
    ABSENT = "absent"
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"
    HYPOTHETICAL = "hypothetical"
    FAMILY_HISTORY = "family_history"


class ClinicalSectionEnum(str, Enum):
    """Clinical document sections."""

    CHIEF_COMPLAINT = "chief_complaint"
    HPI = "hpi"
    ROS = "ros"
    PAST_MEDICAL_HISTORY = "pmh"
    PAST_SURGICAL_HISTORY = "psh"
    FAMILY_HISTORY = "fhx"
    SOCIAL_HISTORY = "shx"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    VITAL_SIGNS = "vitals"
    PHYSICAL_EXAM = "physical_exam"
    LABS = "labs"
    IMAGING = "imaging"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    UNKNOWN = "unknown"


class NormalizationVocabularyEnum(str, Enum):
    """Standard vocabularies for entity normalization."""

    SNOMED_CT = "SNOMED-CT"
    RXNORM = "RxNorm"
    LOINC = "LOINC"
    ICD10_CM = "ICD-10-CM"
    ICD10_PCS = "ICD-10-PCS"
    CPT = "CPT"
    NDC = "NDC"


# ============================================================================
# Request/Response Models
# ============================================================================


class EntitySpanResponse(BaseModel):
    """Represents a text span in the source document."""

    start: int = Field(..., description="Start character offset")
    end: int = Field(..., description="End character offset")
    text: str = Field(..., description="The matched text")


class NormalizedCodeResponse(BaseModel):
    """A normalized code from a standard vocabulary."""

    code: str = Field(..., description="The code value")
    display: str = Field(..., description="Code display text")
    system: NormalizationVocabularyEnum = Field(..., description="Vocabulary system")
    confidence: float = Field(..., ge=0, le=1, description="Match confidence")
    is_preferred: bool = Field(default=False, description="Whether this is the preferred code")


class ExtractedEntityResponse(BaseModel):
    """A clinical entity extracted from text."""

    id: str = Field(..., description="Unique entity identifier")
    entity_type: EntityTypeEnum = Field(..., description="Type of entity")
    text: str = Field(..., description="Original matched text")
    normalized_text: str = Field(..., description="Normalized/standardized text")
    span: EntitySpanResponse = Field(..., description="Text span information")
    section: ClinicalSectionEnum = Field(..., description="Clinical section where found")
    assertion: AssertionStatusEnum = Field(..., description="Assertion status")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")
    normalized_codes: list[NormalizedCodeResponse] = Field(
        default_factory=list, description="Normalized codes"
    )

    # Entity-specific fields
    value: str | None = Field(None, description="Value (for vitals/labs)")
    unit: str | None = Field(None, description="Unit (for vitals/labs)")
    reference_range: str | None = Field(None, description="Reference range (for labs)")
    laterality: str | None = Field(None, description="Laterality (left/right/bilateral)")
    dosage: str | None = Field(None, description="Dosage (for medications)")
    frequency: str | None = Field(None, description="Frequency (for medications)")
    route: str | None = Field(None, description="Route (for medications)")
    duration: str | None = Field(None, description="Duration")

    # Negation information
    negation_trigger: str | None = Field(None, description="Negation trigger word/phrase")
    negation_scope_start: int | None = Field(None, description="Negation scope start offset")
    negation_scope_end: int | None = Field(None, description="Negation scope end offset")


class SectionSpanResponse(BaseModel):
    """A detected clinical section in the document."""

    section: ClinicalSectionEnum = Field(..., description="Section type")
    start: int = Field(..., description="Start character offset")
    end: int = Field(..., description="End character offset")
    header_text: str | None = Field(None, description="Section header text")


class ExtractRequest(BaseModel):
    """Request for entity extraction."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Clinical text to process",
    )
    entity_types: list[EntityTypeEnum] | None = Field(
        default=None,
        description="Entity types to extract. If None, extracts all types.",
    )
    use_ml_models: bool = Field(
        default=False,
        description="Whether to use ML models (if available)",
    )
    model_id: str | None = Field(
        default=None,
        description="Specific ML model to use",
    )
    include_normalized_codes: bool = Field(
        default=True,
        description="Whether to include normalized codes in response",
    )


class ExtractResponse(BaseModel):
    """Response from entity extraction."""

    request_id: str = Field(..., description="Unique request identifier")
    text_length: int = Field(..., description="Length of input text")
    entities: list[ExtractedEntityResponse] = Field(
        ..., description="Extracted entities"
    )
    sections: list[SectionSpanResponse] = Field(
        ..., description="Detected clinical sections"
    )
    entity_count: int = Field(..., description="Total entities extracted")
    entities_by_type: dict[str, int] = Field(
        ..., description="Entity counts by type"
    )
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    model_used: str = Field(..., description="Model used for extraction")


class BatchExtractRequest(BaseModel):
    """Request for batch entity extraction."""

    texts: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of clinical texts to process",
    )
    entity_types: list[EntityTypeEnum] | None = Field(
        default=None,
        description="Entity types to extract",
    )
    use_ml_models: bool = Field(
        default=False,
        description="Whether to use ML models",
    )
    model_id: str | None = Field(
        default=None,
        description="Specific ML model to use",
    )


class BatchExtractItem(BaseModel):
    """Result for a single text in batch extraction."""

    index: int = Field(..., description="Index in input list")
    text_preview: str = Field(..., description="First 100 chars of text")
    entity_count: int = Field(..., description="Number of entities extracted")
    entities_by_type: dict[str, int] = Field(..., description="Counts by type")
    processing_time_ms: float = Field(..., description="Processing time")
    error: str | None = Field(None, description="Error message if failed")


class BatchExtractResponse(BaseModel):
    """Response from batch entity extraction."""

    request_id: str = Field(..., description="Unique request identifier")
    total_texts: int = Field(..., description="Total texts processed")
    successful: int = Field(..., description="Successfully processed")
    failed: int = Field(..., description="Failed to process")
    results: list[BatchExtractItem] = Field(..., description="Results for each text")
    total_time_ms: float = Field(..., description="Total processing time")


class NLPModelInfo(BaseModel):
    """Information about an available NLP model."""

    model_id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Model name")
    description: str = Field(..., description="Model description")
    entity_types: list[EntityTypeEnum] = Field(
        ..., description="Supported entity types"
    )
    is_available: bool = Field(..., description="Whether model is available")
    requires_gpu: bool = Field(default=False, description="Whether model requires GPU")
    version: str = Field(default="1.0.0", description="Model version")


class ModelsResponse(BaseModel):
    """Response listing available NLP models."""

    models: list[NLPModelInfo] = Field(..., description="Available models")
    default_model: str = Field(..., description="Default model ID")


class NormalizeRequest(BaseModel):
    """Request for entity normalization."""

    entities: list[ExtractedEntityResponse] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Entities to normalize",
    )
    vocabularies: list[NormalizationVocabularyEnum] | None = Field(
        default=None,
        description="Vocabularies to use for normalization",
    )


class NormalizationResultItem(BaseModel):
    """Result of normalizing a single entity."""

    entity_id: str = Field(..., description="Entity identifier")
    original_text: str = Field(..., description="Original entity text")
    normalized_codes: list[NormalizedCodeResponse] = Field(
        ..., description="Normalized codes"
    )
    best_match: NormalizedCodeResponse | None = Field(
        None, description="Best matching code"
    )
    processing_time_ms: float = Field(..., description="Processing time")


class NormalizeResponse(BaseModel):
    """Response from entity normalization."""

    request_id: str = Field(..., description="Unique request identifier")
    results: list[NormalizationResultItem] = Field(
        ..., description="Normalization results"
    )
    total_entities: int = Field(..., description="Total entities normalized")
    entities_with_codes: int = Field(
        ..., description="Entities that received codes"
    )
    total_time_ms: float = Field(..., description="Total processing time")


# ============================================================================
# Extract Endpoint
# ============================================================================


@router.post(
    "/extract",
    response_model=ExtractResponse,
    summary="Extract entities from clinical text",
    description="Extract clinical entities from text using NLP.",
)
async def extract_entities(request: ExtractRequest) -> ExtractResponse:
    """Extract clinical entities from text.

    This endpoint extracts various clinical entities from clinical notes:
    - Diagnoses/Problems (conditions, symptoms, diseases)
    - Medications (drug names, dosages, frequencies, routes)
    - Procedures (surgeries, treatments, interventions)
    - Lab Results (test names, values, units, reference ranges)
    - Vital Signs (BP, HR, temp, SpO2, weight, height)
    - Anatomical Locations (body parts, laterality)
    - Temporal Expressions (dates, durations, frequencies)

    Features:
    - Negation detection (e.g., "no fever", "denies chest pain")
    - Confidence scoring for each extraction
    - Section detection (HPI, ROS, Assessment, Plan, etc.)
    - Optional normalization to standard codes

    Args:
        request: Clinical text and extraction options.

    Returns:
        ExtractResponse with extracted entities and metadata.
    """
    try:
        from app.services.nlp_entity_service import (
            get_nlp_entity_service,
            EntityType,
            NormalizationVocabulary,
        )

        service = get_nlp_entity_service()

        # Convert API enums to service enums
        entity_types = None
        if request.entity_types:
            entity_types = [EntityType(et.value) for et in request.entity_types]

        # Extract entities
        result = service.extract_entities(
            text=request.text,
            entity_types=entity_types,
            use_ml_models=request.use_ml_models,
            model_id=request.model_id,
        )

        # Normalize entities if requested
        entities_response: list[ExtractedEntityResponse] = []
        for entity in result.entities:
            normalized_codes = []
            if request.include_normalized_codes:
                norm_result = service.normalize_entity(entity)
                normalized_codes = [
                    NormalizedCodeResponse(
                        code=nc.code,
                        display=nc.display,
                        system=NormalizationVocabularyEnum(nc.system.value),
                        confidence=nc.confidence,
                        is_preferred=nc.is_preferred,
                    )
                    for nc in norm_result.normalized_codes
                ]

            entities_response.append(
                ExtractedEntityResponse(
                    id=entity.id,
                    entity_type=EntityTypeEnum(entity.entity_type.value),
                    text=entity.text,
                    normalized_text=entity.normalized_text,
                    span=EntitySpanResponse(
                        start=entity.span.start,
                        end=entity.span.end,
                        text=entity.span.text,
                    ),
                    section=ClinicalSectionEnum(entity.section.value),
                    assertion=AssertionStatusEnum(entity.assertion.value),
                    confidence=entity.confidence,
                    normalized_codes=normalized_codes,
                    value=entity.value,
                    unit=entity.unit,
                    reference_range=entity.reference_range,
                    laterality=entity.laterality,
                    dosage=entity.dosage,
                    frequency=entity.frequency,
                    route=entity.route,
                    duration=entity.duration,
                    negation_trigger=entity.negation_trigger,
                    negation_scope_start=entity.negation_scope_start,
                    negation_scope_end=entity.negation_scope_end,
                )
            )

        sections_response = [
            SectionSpanResponse(
                section=ClinicalSectionEnum(s.section.value),
                start=s.start,
                end=s.end,
                header_text=s.header_text,
            )
            for s in result.sections
        ]

        return ExtractResponse(
            request_id=result.request_id,
            text_length=result.text_length,
            entities=entities_response,
            sections=sections_response,
            entity_count=result.entity_count,
            entities_by_type=result.entities_by_type,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_used,
        )

    except Exception as e:
        raise InternalError(
            message=f"Entity extraction failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )


# ============================================================================
# Batch Extract Endpoint
# ============================================================================


@router.post(
    "/extract/batch",
    response_model=BatchExtractResponse,
    summary="Batch extract entities from multiple texts",
    description="Process multiple clinical texts for entity extraction.",
)
async def batch_extract_entities(request: BatchExtractRequest) -> BatchExtractResponse:
    """Batch extract entities from multiple clinical texts.

    Efficiently processes multiple texts in a single request.
    Returns summary results for each text.

    Args:
        request: List of texts and extraction options.

    Returns:
        BatchExtractResponse with results for each text.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    results: list[BatchExtractItem] = []
    successful = 0
    failed = 0

    for i, text in enumerate(request.texts):
        try:
            single_request = ExtractRequest(
                text=text,
                entity_types=request.entity_types,
                use_ml_models=request.use_ml_models,
                model_id=request.model_id,
                include_normalized_codes=False,  # Skip normalization for batch
            )
            response = await extract_entities(single_request)

            results.append(
                BatchExtractItem(
                    index=i,
                    text_preview=text[:100] + "..." if len(text) > 100 else text,
                    entity_count=response.entity_count,
                    entities_by_type=response.entities_by_type,
                    processing_time_ms=response.processing_time_ms,
                    error=None,
                )
            )
            successful += 1

        except Exception as e:
            results.append(
                BatchExtractItem(
                    index=i,
                    text_preview=text[:100] + "..." if len(text) > 100 else text,
                    entity_count=0,
                    entities_by_type={},
                    processing_time_ms=0,
                    error=str(e),
                )
            )
            failed += 1

    total_time = (time.perf_counter() - start_time) * 1000

    return BatchExtractResponse(
        request_id=request_id,
        total_texts=len(request.texts),
        successful=successful,
        failed=failed,
        results=results,
        total_time_ms=round(total_time, 2),
    )


# ============================================================================
# Models Endpoint
# ============================================================================


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="List available NLP models",
    description="Get list of available NLP models for entity extraction.",
)
async def list_models() -> ModelsResponse:
    """List available NLP models.

    Returns information about available NLP models including:
    - Model ID and name
    - Supported entity types
    - Whether the model is available
    - GPU requirements

    Returns:
        ModelsResponse with available models.
    """
    try:
        from app.services.nlp_entity_service import get_nlp_entity_service

        service = get_nlp_entity_service()
        models = service.get_available_models()

        models_response = [
            NLPModelInfo(
                model_id=m.model_id,
                name=m.name,
                description=m.description,
                entity_types=[EntityTypeEnum(et.value) for et in m.entity_types],
                is_available=m.is_available,
                requires_gpu=m.requires_gpu,
                version=m.version,
            )
            for m in models
        ]

        return ModelsResponse(
            models=models_response,
            default_model="rule_based",
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to list models: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Normalize Endpoint
# ============================================================================


@router.post(
    "/normalize",
    response_model=NormalizeResponse,
    summary="Normalize entities to standard codes",
    description="Normalize extracted entities to standard vocabulary codes.",
)
async def normalize_entities(request: NormalizeRequest) -> NormalizeResponse:
    """Normalize extracted entities to standard codes.

    Maps extracted entities to standard vocabulary codes:
    - Diagnoses -> SNOMED-CT, ICD-10-CM
    - Medications -> RxNorm, NDC
    - Procedures -> CPT, ICD-10-PCS
    - Labs/Vitals -> LOINC

    Args:
        request: Entities to normalize and vocabularies to use.

    Returns:
        NormalizeResponse with normalization results.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.nlp_entity_service import (
            get_nlp_entity_service,
            ExtractedEntity,
            EntitySpan,
            EntityType,
            ClinicalSection,
            AssertionStatus,
            NormalizationVocabulary,
        )

        service = get_nlp_entity_service()

        # Convert vocabularies
        vocabularies = None
        if request.vocabularies:
            vocabularies = [
                NormalizationVocabulary(v.value) for v in request.vocabularies
            ]

        results: list[NormalizationResultItem] = []
        entities_with_codes = 0

        for entity_data in request.entities:
            # Reconstruct entity object
            entity = ExtractedEntity(
                id=entity_data.id,
                entity_type=EntityType(entity_data.entity_type.value),
                text=entity_data.text,
                normalized_text=entity_data.normalized_text,
                span=EntitySpan(
                    start=entity_data.span.start,
                    end=entity_data.span.end,
                    text=entity_data.span.text,
                ),
                section=ClinicalSection(entity_data.section.value),
                assertion=AssertionStatus(entity_data.assertion.value),
                confidence=entity_data.confidence,
            )

            # Normalize
            norm_result = service.normalize_entity(entity, vocabularies)

            normalized_codes = [
                NormalizedCodeResponse(
                    code=nc.code,
                    display=nc.display,
                    system=NormalizationVocabularyEnum(nc.system.value),
                    confidence=nc.confidence,
                    is_preferred=nc.is_preferred,
                )
                for nc in norm_result.normalized_codes
            ]

            best_match = None
            if norm_result.best_match:
                best_match = NormalizedCodeResponse(
                    code=norm_result.best_match.code,
                    display=norm_result.best_match.display,
                    system=NormalizationVocabularyEnum(norm_result.best_match.system.value),
                    confidence=norm_result.best_match.confidence,
                    is_preferred=norm_result.best_match.is_preferred,
                )
                entities_with_codes += 1

            results.append(
                NormalizationResultItem(
                    entity_id=entity_data.id,
                    original_text=entity_data.text,
                    normalized_codes=normalized_codes,
                    best_match=best_match,
                    processing_time_ms=norm_result.processing_time_ms,
                )
            )

        total_time = (time.perf_counter() - start_time) * 1000

        return NormalizeResponse(
            request_id=request_id,
            results=results,
            total_entities=len(request.entities),
            entities_with_codes=entities_with_codes,
            total_time_ms=round(total_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Normalization failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )


# ============================================================================
# Sample Data Endpoints (for demo/testing)
# ============================================================================


@router.get(
    "/samples",
    summary="Get sample clinical notes",
    description="Get sample clinical notes for testing the NLP extraction.",
)
async def get_sample_notes() -> dict:
    """Get sample clinical notes for testing.

    Returns a collection of sample clinical notes that can be used
    to test the entity extraction endpoints.

    Returns:
        Dictionary with sample notes.
    """
    return {
        "samples": [
            {
                "id": "progress_note",
                "title": "Progress Note",
                "text": """CHIEF COMPLAINT: Follow-up for diabetes and hypertension

HISTORY OF PRESENT ILLNESS:
65-year-old male with type 2 diabetes mellitus and essential hypertension presents for routine follow-up. Patient reports good compliance with medications. Denies chest pain, shortness of breath, or palpitations. No hypoglycemic episodes. Patient reports occasional headaches in the morning.

PAST MEDICAL HISTORY:
- Type 2 diabetes mellitus (diagnosed 2018)
- Essential hypertension
- Hyperlipidemia
- History of GERD
- Osteoarthritis of bilateral knees

MEDICATIONS:
1. Metformin 1000mg twice daily
2. Lisinopril 20mg daily
3. Atorvastatin 40mg at bedtime
4. Omeprazole 20mg daily
5. Aspirin 81mg daily

ALLERGIES: No known drug allergies

FAMILY HISTORY: Father had MI at age 62. Mother with type 2 diabetes.

VITAL SIGNS:
Blood pressure: 138/86 mmHg
Heart rate: 72 bpm
Temperature: 98.4 F
Respiratory rate: 16/min
SpO2: 98% on room air
Weight: 92 kg
Height: 5'10"
BMI: 29.5

LABORATORY DATA:
HbA1c: 7.2% (improved from 8.1% three months ago)
Fasting glucose: 132 mg/dL
Creatinine: 1.1 mg/dL
eGFR: 72 mL/min
LDL: 98 mg/dL
HDL: 45 mg/dL
Triglycerides: 156 mg/dL

ASSESSMENT:
1. Type 2 diabetes mellitus - improved control, continue current regimen
2. Essential hypertension - mildly elevated today, continue monitoring
3. Hyperlipidemia - at goal on current statin therapy
4. Osteoarthritis - stable, continue conservative management

PLAN:
1. Continue Metformin 1000mg BID
2. Continue Lisinopril 20mg daily, recheck BP in 2 weeks
3. Continue Atorvastatin 40mg QHS
4. Diabetic eye exam due - referral to ophthalmology
5. Follow-up in 3 months with repeat labs""",
            },
            {
                "id": "discharge_summary",
                "title": "Discharge Summary",
                "text": """ADMISSION DATE: 01/10/2026
DISCHARGE DATE: 01/15/2026

PRINCIPAL DIAGNOSIS: Acute exacerbation of COPD

SECONDARY DIAGNOSES:
- Chronic obstructive pulmonary disease, severe
- Atrial fibrillation with rapid ventricular response
- Type 2 diabetes mellitus with diabetic nephropathy
- Chronic kidney disease, stage 3
- Hypertension

HOSPITAL COURSE:
72-year-old female with history of COPD on home oxygen presented to the ED with 3 days of worsening dyspnea, productive cough with yellow sputum, and fever. Initial vitals showed BP 142/88, HR 112 (irregular), temp 101.2 F, RR 24, SpO2 88% on 2L NC.

Labs on admission:
WBC: 14.2 K/uL (elevated)
Hemoglobin: 11.8 g/dL
Creatinine: 1.8 mg/dL (baseline 1.4)
BNP: 890 pg/mL
Procalcitonin: 0.8 ng/mL

Chest X-ray showed bilateral infiltrates consistent with pneumonia.

Patient was started on IV antibiotics (ceftriaxone and azithromycin) and nebulizer treatments. Prednisone 40mg daily was initiated. Rate control achieved with metoprolol for atrial fibrillation. Patient's respiratory status improved over 4 days.

PROCEDURES:
- No surgical procedures performed
- Bronchoscopy considered but deferred given clinical improvement

DISCHARGE MEDICATIONS:
1. Prednisone 40mg daily x 5 days (taper)
2. Azithromycin 500mg daily x 3 more days
3. Albuterol inhaler 2 puffs Q4H PRN
4. Tiotropium 18mcg inhaled daily
5. Metoprolol tartrate 25mg BID
6. Lisinopril 10mg daily
7. Metformin 500mg BID (reduced due to AKI)
8. Home oxygen 2L NC continuous

FOLLOW-UP:
- PCP appointment in 1 week
- Pulmonology follow-up in 2 weeks
- Repeat labs (BMP, CBC) in 3 days

DISCHARGE CONDITION: Improved, stable""",
            },
            {
                "id": "ros_negative",
                "title": "Review of Systems (Negative)",
                "text": """REVIEW OF SYSTEMS:
Constitutional: No fever, no chills, no weight loss, no fatigue.
HEENT: No headache, no vision changes, no hearing loss, no sore throat.
Cardiovascular: No chest pain, no palpitations, no leg swelling.
Respiratory: No shortness of breath, no cough, no wheezing.
Gastrointestinal: No nausea, no vomiting, no abdominal pain, no diarrhea, no constipation.
Genitourinary: No dysuria, no frequency, no urgency, no hematuria.
Musculoskeletal: No joint pain, no muscle weakness, no back pain.
Neurological: No dizziness, no numbness, no tingling, no seizures.
Psychiatric: No depression, no anxiety, denies suicidal ideation.
Skin: No rash, no itching.""",
            },
        ]
    }


@router.get(
    "/stats",
    summary="Get NLP service statistics",
    description="Get statistics about the NLP entity extraction service.",
)
async def get_service_stats() -> dict:
    """Get NLP service statistics.

    Returns statistics about the service including:
    - Number of registered ML models
    - Pattern counts by category
    - Available entity types

    Returns:
        Dictionary with service statistics.
    """
    try:
        from app.services.nlp_entity_service import get_nlp_entity_service

        service = get_nlp_entity_service()
        return service.get_stats()

    except Exception as e:
        raise InternalError(
            message=f"Failed to get stats: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )
