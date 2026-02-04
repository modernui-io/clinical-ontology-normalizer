"""NLP Entity Extraction API Endpoints.

Provides clinical NLP entity extraction services:
- Extract clinical entities from text
- Batch extraction for multiple documents
- List available NLP models
- Normalize extracted entities to standard codes
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError

logger = logging.getLogger(__name__)


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
    SOCIAL_HISTORY = "social_history"


class AssertionStatusEnum(str, Enum):
    """Assertion status for extracted entities."""

    PRESENT = "present"
    ABSENT = "absent"
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"
    HYPOTHETICAL = "hypothetical"
    FAMILY_HISTORY = "family_history"
    HISTORICAL = "historical"


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
    create_facts: bool = Field(
        default=False,
        description="Create ClinicalFacts from extracted entities and build knowledge graph",
    )
    patient_id: str | None = Field(
        default=None,
        description="Patient ID for fact/KG creation (required if create_facts=True)",
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
    # Optional fact/graph creation stats (populated when create_facts=True)
    facts_created: int | None = Field(
        None, description="Number of ClinicalFacts created (if create_facts=True)"
    )
    graph_nodes_created: int | None = Field(
        None, description="Number of KG nodes created (if create_facts=True)"
    )
    graph_edges_created: int | None = Field(
        None, description="Number of KG edges created (if create_facts=True)"
    )
    patient_id: str | None = Field(
        None, description="Patient ID for created facts/graph (if create_facts=True)"
    )


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
        from uuid import uuid4
        from app.services.nlp_entity_service import (
            get_nlp_entity_service,
            EntityType,
            NormalizationVocabulary,
            ExtractionResult,
            ExtractedEntity,
            EntitySpan,
            AssertionStatus,
            ClinicalSection,
        )

        # Check if using LLM model (MedGemma via Ollama)
        if request.model_id == "llm_api":
            from app.services.nlp_claude_api import get_llm_nlp_service
            import time

            start_time = time.perf_counter()
            llm_service = get_llm_nlp_service()
            if not llm_service.is_available:
                raise InternalError(
                    message="LLM service not available. Make sure Ollama is running.",
                    error_code=ErrorCode.SERVICE_UNAVAILABLE,
                )

            # Get entity types filter
            entity_type_strs = None
            if request.entity_types:
                entity_type_strs = [et.value for et in request.entity_types]

            llm_entities, _ = llm_service.extract_entities(request.text, entity_type_strs)
            processing_time = (time.perf_counter() - start_time) * 1000

            # Map LLM entities to ExtractedEntity format
            llm_entity_type_map = {
                "diagnosis": EntityType.DIAGNOSIS,
                "medication": EntityType.MEDICATION,
                "procedure": EntityType.PROCEDURE,
                "lab_result": EntityType.LAB_RESULT,
                "vital_sign": EntityType.VITAL_SIGN,
                "symptom": EntityType.SYMPTOM,
                "allergy": EntityType.ALLERGY,
                "anatomical_location": EntityType.ANATOMICAL_LOCATION,
                "temporal": EntityType.TEMPORAL,
                "social_history": EntityType.SOCIAL_HISTORY,
            }
            llm_assertion_map = {
                "present": AssertionStatus.PRESENT,
                "absent": AssertionStatus.ABSENT,
                "possible": AssertionStatus.POSSIBLE,
                "conditional": AssertionStatus.CONDITIONAL,
                "hypothetical": AssertionStatus.HYPOTHETICAL,
                "family_history": AssertionStatus.FAMILY_HISTORY,
            }

            extracted = []
            for e in llm_entities:
                entity_type = llm_entity_type_map.get(e.entity_type, EntityType.DIAGNOSIS)
                assertion = llm_assertion_map.get(e.assertion, AssertionStatus.PRESENT)
                extracted.append(ExtractedEntity(
                    id=e.id,
                    entity_type=entity_type,
                    text=e.text,
                    normalized_text=e.normalized_text,
                    span=EntitySpan(start=e.start, end=e.end, text=e.text),
                    section=ClinicalSection.UNKNOWN,
                    assertion=assertion,
                    confidence=e.confidence,
                    value=e.value,
                    unit=e.unit,
                ))

            result = ExtractionResult(
                entities=extracted,
                model_id="llm_api",
                processing_time_ms=round(processing_time, 2),
                text_length=len(request.text),
            )
            service = get_nlp_entity_service()  # For normalization

        # Use Ensemble NLP when use_ml_models is True (combines rule-based + ClinicalBERT + ModernBERT)
        elif request.use_ml_models:
            from app.services.nlp_ensemble import get_ensemble_nlp_service
            import time

            start_time = time.perf_counter()
            ensemble_service = get_ensemble_nlp_service()
            ensemble_result = ensemble_service.extract_all(request.text, document_id=uuid4())
            processing_time = (time.perf_counter() - start_time) * 1000

            # Map ensemble mentions to ExtractedEntity format
            domain_to_entity_type = {
                "condition": EntityType.DIAGNOSIS,
                "drug": EntityType.MEDICATION,
                "procedure": EntityType.PROCEDURE,
                "measurement": EntityType.LAB_RESULT,
                "observation": EntityType.SYMPTOM,
                "anatomy": EntityType.ANATOMICAL_LOCATION,
            }

            ml_entities = []
            for m in ensemble_result.mentions:
                entity_type = domain_to_entity_type.get(m.domain_hint, EntityType.DIAGNOSIS)
                assertion = AssertionStatus.ABSENT if m.is_negated else AssertionStatus.PRESENT
                if m.is_uncertain:
                    assertion = AssertionStatus.UNCERTAIN

                ml_entities.append(ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=entity_type,
                    text=m.text,
                    normalized_text=m.lexical_variant or m.text,
                    span=EntitySpan(start=m.start_offset, end=m.end_offset, text=m.text),
                    section=ClinicalSection.UNKNOWN,
                    assertion=assertion,
                    confidence=float(m.confidence),
                ))

            result = ExtractionResult(
                entities=ml_entities,
                model_id="ensemble_nlp",  # Rule-based + ClinicalBERT + ModernBERT
                processing_time_ms=round(processing_time, 2),
                text_length=len(request.text),
            )
            service = get_nlp_entity_service()  # For normalization
        else:
            service = get_nlp_entity_service()

            # Convert API enums to service enums
            entity_types = None
            if request.entity_types:
                entity_types = [EntityType(et.value) for et in request.entity_types]

            # Extract entities using rule-based service
            result = service.extract_entities(
                text=request.text,
                entity_types=entity_types,
                model_id="rule_based",
            )

        # Generate request ID for this request
        import uuid
        request_id = f"req-{uuid.uuid4().hex[:12]}"

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
                        confidence=min(1.0, max(0.0, nc.confidence)),  # Clamp to [0, 1]
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

        # Optional: Create facts and build knowledge graph
        facts_created = None
        graph_nodes_created = None
        graph_edges_created = None
        response_patient_id = None

        if request.create_facts:
            if not request.patient_id:
                raise InternalError(
                    message="patient_id is required when create_facts=True",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            from sqlalchemy.orm import Session
            from app.core.database import get_sync_engine
            from app.services.fact_builder_db import DatabaseFactBuilderService
            from app.services.graph_builder_db import DatabaseGraphBuilderService
            from app.schemas.base import Assertion, Domain, Temporality, Experiencer

            # Map entity types to domains
            entity_type_to_domain = {
                EntityTypeEnum.DIAGNOSIS: Domain.CONDITION,
                EntityTypeEnum.MEDICATION: Domain.DRUG,
                EntityTypeEnum.PROCEDURE: Domain.PROCEDURE,
                EntityTypeEnum.LAB_RESULT: Domain.MEASUREMENT,
                EntityTypeEnum.VITAL_SIGN: Domain.MEASUREMENT,
                EntityTypeEnum.SYMPTOM: Domain.CONDITION,
                EntityTypeEnum.ALLERGY: Domain.OBSERVATION,
                EntityTypeEnum.ANATOMICAL_LOCATION: Domain.OBSERVATION,
                EntityTypeEnum.TEMPORAL: Domain.OBSERVATION,
                EntityTypeEnum.SOCIAL_HISTORY: Domain.OBSERVATION,
            }

            # Map assertion status to Assertion enum
            assertion_map = {
                AssertionStatusEnum.PRESENT: Assertion.PRESENT,
                AssertionStatusEnum.ABSENT: Assertion.ABSENT,
                AssertionStatusEnum.POSSIBLE: Assertion.POSSIBLE,
                AssertionStatusEnum.CONDITIONAL: Assertion.POSSIBLE,
                AssertionStatusEnum.HYPOTHETICAL: Assertion.POSSIBLE,
                AssertionStatusEnum.FAMILY_HISTORY: Assertion.PRESENT,
                AssertionStatusEnum.HISTORICAL: Assertion.ABSENT,  # Historical/former = not currently present
            }

            with Session(get_sync_engine()) as session:
                fact_builder = DatabaseFactBuilderService(session)
                facts_created = 0

                for entity in entities_response:
                    # Get domain from entity type
                    domain = entity_type_to_domain.get(entity.entity_type, Domain.OBSERVATION)

                    # Get assertion
                    assertion = assertion_map.get(entity.assertion, Assertion.PRESENT)

                    # Get OMOP concept ID from normalized codes if available
                    omop_concept_id = 0
                    if entity.normalized_codes:
                        # Use first normalized code as concept ID
                        try:
                            omop_concept_id = int(entity.normalized_codes[0].code)
                        except (ValueError, IndexError):
                            omop_concept_id = 0

                    # Create fact
                    try:
                        fact_builder.create_fact_from_mention(
                            mention_id=uuid4(),  # Generate a mention ID
                            patient_id=request.patient_id,
                            omop_concept_id=omop_concept_id,
                            concept_name=entity.normalized_text or entity.text,
                            domain=domain,
                            assertion=assertion,
                            temporality=Temporality.CURRENT,
                            experiencer=Experiencer.PATIENT,
                            confidence=entity.confidence,
                        )
                        facts_created += 1
                    except Exception as fact_err:
                        # Log but continue with other entities
                        import logging
                        logging.getLogger(__name__).warning(
                            f"Failed to create fact for entity '{entity.text}': {fact_err}"
                        )

                # Build knowledge graph from facts
                if facts_created > 0:
                    try:
                        graph_builder = DatabaseGraphBuilderService(session)
                        graph_result = graph_builder.build_graph_for_patient(request.patient_id)
                        graph_nodes_created = graph_result.nodes_created
                        graph_edges_created = graph_result.edges_created
                    except Exception as graph_err:
                        import logging
                        logging.getLogger(__name__).warning(
                            f"Failed to build knowledge graph: {graph_err}"
                        )
                        graph_nodes_created = 0
                        graph_edges_created = 0

                session.commit()
                response_patient_id = request.patient_id

        return ExtractResponse(
            request_id=request_id,
            text_length=result.text_length,
            entities=entities_response,
            sections=sections_response,
            entity_count=result.entity_count,
            entities_by_type=result.entities_by_type,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_id,  # Map model_id to model_used
            facts_created=facts_created,
            graph_nodes_created=graph_nodes_created,
            graph_edges_created=graph_edges_created,
            patient_id=response_patient_id,
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
# Preload Endpoint
# ============================================================================


@router.post(
    "/preload",
    summary="Preload LLM model",
    description="Warm up the LLM model to reduce first extraction latency.",
)
async def preload_model() -> dict:
    """Preload the LLM model into memory.

    This endpoint triggers Ollama to load the model into VRAM/RAM
    so subsequent extraction requests are faster.

    Returns:
        Status message with model info.
    """
    try:
        from app.services.nlp_claude_api import get_llm_nlp_service
        import httpx

        llm_service = get_llm_nlp_service()
        if not llm_service._ollama_available:
            return {
                "status": "skipped",
                "message": "Ollama not available - no preload needed",
            }

        # Send a minimal prompt to warm up the model
        with httpx.Client(timeout=300.0) as client:  # 5 min timeout for loading
            response = client.post(
                f"{llm_service.config.ollama_base_url}/api/generate",
                json={
                    "model": llm_service.config.ollama_model,
                    "prompt": "Hello",
                    "stream": False,
                    "options": {"num_predict": 1},  # Only generate 1 token
                },
            )
            response.raise_for_status()

        return {
            "status": "success",
            "message": f"Model {llm_service.config.ollama_model} loaded and ready",
            "model": llm_service.config.ollama_model,
        }
    except Exception as e:
        logger.error(f"Preload failed: {e}")
        return {
            "status": "error",
            "message": f"Failed to preload model: {str(e)}",
        }


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

        # Only include rule_based model from service (skip broken ML models)
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
            if m.model_id == "rule_based"
        ]

        # Add LLM API model option (Ollama/MedGemma)
        try:
            from app.services.nlp_claude_api import get_llm_nlp_service
            llm_service = get_llm_nlp_service()
            model_info = llm_service.get_model_info()
            models_response.append(
                NLPModelInfo(
                    model_id="llm_api",
                    name=model_info.get("name", "LLM API"),
                    description=model_info.get("description", "LLM-based clinical NER"),
                    entity_types=list(EntityTypeEnum),
                    is_available=model_info.get("is_available", False),
                    requires_gpu=False,
                    version="1.0.0",
                )
            )
        except Exception as e:
            logger.warning(f"LLM API service not available: {e}")
            models_response.append(
                NLPModelInfo(
                    model_id="llm_api",
                    name="LLM API (MedGemma/Ollama)",
                    description="LLM-based clinical NER - requires Ollama running locally",
                    entity_types=list(EntityTypeEnum),
                    is_available=False,
                    requires_gpu=False,
                    version="1.0.0",
                )
            )

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
                    confidence=min(1.0, max(0.0, nc.confidence)),  # Clamp to [0, 1]
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
                    confidence=min(1.0, max(0.0, norm_result.best_match.confidence)),  # Clamp to [0, 1]
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


# ============================================================================
# Ontology Mapper Endpoints
# ============================================================================


class OntologyMapRequest(BaseModel):
    """Request for ontology mapping."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Clinical text to process",
    )


class OntologyEntityResponse(BaseModel):
    """An entity extracted by the ontology mapper."""

    text: str = Field(..., description="Original text span")
    normalized: str = Field(..., description="Normalized text")
    category: str = Field(..., description="Entity category (diagnosis, medication, etc.)")
    subcategory: str | None = Field(None, description="Entity subcategory")
    vocabulary_code: str | None = Field(None, description="Vocabulary code")
    vocabulary_system: str | None = Field(None, description="Vocabulary system")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")
    attributes: dict = Field(default_factory=dict, description="Additional attributes")
    negated: bool = Field(default=False, description="Whether the entity is negated")


class OntologyRelationshipResponse(BaseModel):
    """A relationship between entities."""

    subject: str = Field(..., description="Subject entity text")
    relation: str = Field(..., description="Relationship type")
    object: str = Field(..., description="Object entity text")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")


class OntologyMapResponse(BaseModel):
    """Response from ontology mapping."""

    request_id: str = Field(..., description="Unique request identifier")
    text_length: int = Field(..., description="Length of input text")
    total_tokens: int = Field(..., description="Total tokens processed")
    classified_tokens: int = Field(..., description="Tokens that were classified")
    coverage_pct: float = Field(..., description="Percentage of tokens classified")
    entity_count: int = Field(..., description="Total entities extracted")
    entities_by_category: dict[str, int] = Field(..., description="Counts by category")
    entities: list[OntologyEntityResponse] = Field(..., description="Extracted entities")
    relationships: list[OntologyRelationshipResponse] = Field(
        default_factory=list, description="Entity relationships"
    )
    negated_findings: list[str] = Field(
        default_factory=list, description="Negated findings"
    )
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


@router.post(
    "/ontology/map",
    response_model=OntologyMapResponse,
    summary="Map clinical text using ontology mapper",
    description="Fast deterministic extraction using clinical ontologies.",
)
async def ontology_map(request: OntologyMapRequest) -> OntologyMapResponse:
    """Map clinical text using the deterministic ontology mapper.

    This endpoint uses a rule-based approach with clinical ontologies for
    fast, deterministic entity extraction. Features:
    - 100% token coverage tracking
    - ~1ms processing time for most notes
    - No LLM required - fully deterministic
    - Negation detection
    - Relationship extraction

    Args:
        request: Clinical text to process.

    Returns:
        OntologyMapResponse with extracted entities and coverage stats.
    """
    try:
        from app.services.clinical_ontology_mapper import get_ontology_mapper

        mapper = get_ontology_mapper()
        result = mapper.map_note(request.text)

        # Convert to response format
        entities = []
        entities_by_category: dict[str, int] = {}

        for entity in result.entities:
            cat = entity.category.value
            entities_by_category[cat] = entities_by_category.get(cat, 0) + 1

            entities.append(OntologyEntityResponse(
                text=entity.span.text,
                normalized=entity.span.normalized,
                category=cat,
                subcategory=entity.subcategory,
                vocabulary_code=entity.vocabulary_code,
                vocabulary_system=entity.vocabulary_system,
                confidence=entity.confidence,
                attributes=entity.attributes,
                negated=entity.attributes.get("negated", False),
            ))

        relationships = [
            OntologyRelationshipResponse(
                subject=rel.subject.span.text,
                relation=rel.relation.value,
                object=rel.object.span.text,
                confidence=rel.confidence,
            )
            for rel in result.relationships
        ]

        # Get negated findings
        negated_findings = [
            e.span.text for e in result.entities
            if e.attributes.get("negated", False)
        ]

        stats = result.coverage_stats

        return OntologyMapResponse(
            request_id=str(uuid4()),
            text_length=len(request.text),
            total_tokens=stats["total_tokens"],
            classified_tokens=stats["classified_tokens"],
            coverage_pct=stats["coverage_pct"],
            entity_count=len(entities),
            entities_by_category=entities_by_category,
            entities=entities,
            relationships=relationships,
            negated_findings=negated_findings,
            processing_time_ms=round(result.processing_time_ms, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Ontology mapping failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )


# ============================================================================
# Hybrid Clinical Analyzer Endpoints
# ============================================================================


class AnalysisTypeEnum(str, Enum):
    """Types of clinical analysis available."""

    CLINICAL_SUMMARY = "clinical_summary"
    RISK_ASSESSMENT = "risk_assessment"
    MEDICATION_REVIEW = "medication_review"
    LAB_INTERPRETATION = "lab_interpretation"
    QUESTION_ANSWER = "question_answer"


class HybridAnalyzeRequest(BaseModel):
    """Request for hybrid clinical analysis."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Clinical text to analyze",
    )
    analysis_type: AnalysisTypeEnum = Field(
        default=AnalysisTypeEnum.CLINICAL_SUMMARY,
        description="Type of analysis to perform",
    )
    question: str | None = Field(
        None,
        description="Question to answer (for QUESTION_ANSWER type)",
    )
    use_llm: bool = Field(
        default=True,
        description="Whether to use LLM for reasoning (if False, returns extraction only)",
    )


class StructuredContextResponse(BaseModel):
    """The structured context extracted from clinical text."""

    diagnoses: list[dict] = Field(default_factory=list)
    medications: list[dict] = Field(default_factory=list)
    labs: list[dict] = Field(default_factory=list)
    vitals: list[dict] = Field(default_factory=list)
    symptoms: list[dict] = Field(default_factory=list)
    findings: list[dict] = Field(default_factory=list)
    procedures: list[dict] = Field(default_factory=list)
    negated_findings: list[str] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    entity_count: int = Field(..., description="Total entities")
    coverage_pct: float = Field(..., description="Token coverage percentage")
    human_readable_summary: str = Field(
        default="", description="Human-readable clinical summary"
    )


class HybridAnalyzeResponse(BaseModel):
    """Response from hybrid clinical analysis."""

    request_id: str = Field(..., description="Unique request identifier")
    analysis_type: str = Field(..., description="Type of analysis performed")
    analysis: str | None = Field(None, description="LLM-generated analysis (if use_llm=True)")
    structured_context: StructuredContextResponse = Field(
        ..., description="Deterministic extraction results"
    )
    extraction_time_ms: float = Field(..., description="Time for deterministic extraction")
    llm_time_ms: float | None = Field(None, description="Time for LLM analysis (if used)")
    total_time_ms: float = Field(..., description="Total processing time")
    llm_model: str | None = Field(None, description="LLM model used (if any)")
    llm_available: bool = Field(..., description="Whether LLM was available")


@router.post(
    "/analyze",
    response_model=HybridAnalyzeResponse,
    summary="Hybrid clinical analysis",
    description="Combines deterministic extraction with optional LLM reasoning.",
)
async def hybrid_analyze(request: HybridAnalyzeRequest) -> HybridAnalyzeResponse:
    """Perform hybrid clinical analysis.

    This endpoint combines:
    1. Fast deterministic extraction using clinical ontologies (~1ms)
    2. Optional LLM-powered reasoning grounded in the extracted data

    The LLM can ONLY cite entities from the deterministic extraction,
    reducing hallucination risk.

    Analysis types:
    - CLINICAL_SUMMARY: Overview of patient's clinical status
    - RISK_ASSESSMENT: Identify potential risks and concerns
    - MEDICATION_REVIEW: Analyze medications and interactions
    - LAB_INTERPRETATION: Interpret laboratory results
    - QUESTION_ANSWER: Answer specific questions about the note

    Args:
        request: Clinical text and analysis options.

    Returns:
        HybridAnalyzeResponse with structured data and optional LLM analysis.
    """
    import time as time_module
    start_time = time_module.perf_counter()

    try:
        from app.services.hybrid_clinical_analyzer import (
            HybridClinicalAnalyzer,
            AnalysisType,
        )

        analyzer = HybridClinicalAnalyzer()

        # Always do deterministic extraction first
        extraction_start = time_module.perf_counter()
        context, _ = analyzer.extract_structured_context(request.text)
        extraction_time = (time_module.perf_counter() - extraction_start) * 1000

        # Build structured context response
        structured_context = StructuredContextResponse(
            diagnoses=context.diagnoses,
            medications=context.medications,
            labs=context.labs,
            vitals=context.vitals,
            symptoms=context.symptoms,
            findings=context.findings,
            procedures=context.procedures,
            negated_findings=context.negated_findings,
            relationships=context.relationships,
            entity_count=context.entity_count,
            coverage_pct=context.coverage_pct,
            human_readable_summary=context.to_human_readable_summary(),
        )

        analysis = None
        llm_time = None
        llm_model = None
        llm_available = False

        # Try LLM analysis if requested
        if request.use_llm:
            try:
                analysis_type = AnalysisType(request.analysis_type.value)

                if request.analysis_type == AnalysisTypeEnum.QUESTION_ANSWER:
                    if not request.question:
                        raise ValueError("Question is required for QUESTION_ANSWER analysis type")
                    result = await analyzer.answer_question(request.text, request.question)
                else:
                    result = await analyzer.analyze(
                        note_text=request.text,
                        analysis_type=analysis_type,
                    )

                analysis = result.analysis
                llm_time = result.llm_time_ms
                llm_model = result.llm_model
                llm_available = True

            except Exception as llm_error:
                # LLM not available - continue with extraction only
                llm_available = False
                analysis = f"LLM analysis unavailable: {str(llm_error)}. Structured extraction completed successfully."

        total_time = (time_module.perf_counter() - start_time) * 1000

        return HybridAnalyzeResponse(
            request_id=str(uuid4()),
            analysis_type=request.analysis_type.value,
            analysis=analysis,
            structured_context=structured_context,
            extraction_time_ms=round(extraction_time, 2),
            llm_time_ms=round(llm_time, 2) if llm_time else None,
            total_time_ms=round(total_time, 2),
            llm_model=llm_model,
            llm_available=llm_available,
        )

    except Exception as e:
        raise InternalError(
            message=f"Hybrid analysis failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )


# ============================================================================
# Stats Endpoint
# ============================================================================


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


# ============================================================================
# Knowledge Graph Building Endpoint
# ============================================================================


class BuildGraphRequest(BaseModel):
    """Request to build a knowledge graph from clinical text."""

    clinical_text: str = Field(..., description="The clinical note text to process")
    patient_id: str = Field(..., description="Patient identifier")
    note_id: str | None = Field(None, description="Optional note identifier")
    encounter_id: str | None = Field(None, description="Optional encounter identifier")


class GraphNodeResponse(BaseModel):
    """A node in the knowledge graph."""

    id: str = Field(..., description="Node unique identifier")
    node_type: str = Field(..., description="Node type (condition, drug, etc.)")
    label: str = Field(..., description="Node display label")
    omop_concept_id: int | None = Field(None, description="OMOP concept ID if mapped")
    properties: dict = Field(default_factory=dict, description="Node properties")


class GraphEdgeResponse(BaseModel):
    """An edge in the knowledge graph."""

    id: str = Field(..., description="Edge unique identifier")
    source_node_id: str = Field(..., description="Source node ID")
    target_node_id: str = Field(..., description="Target node ID")
    edge_type: str = Field(..., description="Relationship type")
    properties: dict = Field(default_factory=dict, description="Edge properties")


class BuildGraphResponse(BaseModel):
    """Response from building a knowledge graph."""

    request_id: str = Field(..., description="Request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    note_id: str = Field(..., description="Note identifier")
    nodes: list[GraphNodeResponse] = Field(..., description="Graph nodes")
    edges: list[GraphEdgeResponse] = Field(..., description="Graph edges")
    node_count: int = Field(..., description="Total node count")
    edge_count: int = Field(..., description="Total edge count")
    entities_mapped: int = Field(..., description="Entities mapped to graph")
    processing_time_ms: float = Field(..., description="Processing time in ms")
    coverage_stats: dict = Field(default_factory=dict, description="Coverage statistics")


@router.post(
    "/build-graph",
    response_model=BuildGraphResponse,
    summary="Build knowledge graph from clinical text",
    description="Process clinical text through NLP extraction and build a knowledge graph.",
)
async def build_knowledge_graph(request: BuildGraphRequest) -> BuildGraphResponse:
    """Build a knowledge graph from clinical text.

    This endpoint:
    1. Extracts entities from the clinical text using NLP
    2. Maps entities to standard vocabularies (SNOMED, ICD-10, RxNorm)
    3. Creates graph nodes for each entity
    4. Creates edges connecting patient to entities and entities to each other
    5. Persists the graph to the database

    The resulting graph can be visualized at /patients/{patient_id}/graph

    Args:
        request: Clinical text, patient ID, and optional identifiers.

    Returns:
        BuildGraphResponse with the created graph.
    """
    try:
        from sqlalchemy.orm import Session
        from app.core.database import get_sync_engine
        from app.services.ontology_graph_integration import OntologyGraphIntegration
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        request_id = str(uuid4())

        with Session(get_sync_engine()) as session:
            # Use the ontology graph integration service
            integration = OntologyGraphIntegration(session)

            # Ingest the note and build the graph
            result = integration.ingest_note(
                note_text=request.clinical_text,
                patient_id=request.patient_id,
                note_id=request.note_id,
                encounter_id=request.encounter_id,
            )

            # Commit the changes
            session.commit()

            # Get the complete graph for the patient
            graph_service = DatabaseGraphBuilderService(session)
            patient_graph = graph_service.get_patient_graph(request.patient_id)

            # Convert to response format
            nodes_response = [
                GraphNodeResponse(
                    id=str(node.id),
                    node_type=node.node_type.value if hasattr(node.node_type, 'value') else str(node.node_type),
                    label=node.label,
                    omop_concept_id=node.omop_concept_id,
                    properties=node.properties or {},
                )
                for node in patient_graph.nodes
            ]

            edges_response = [
                GraphEdgeResponse(
                    id=str(edge.id),
                    source_node_id=str(edge.source_node_id),
                    target_node_id=str(edge.target_node_id),
                    edge_type=edge.edge_type.value if hasattr(edge.edge_type, 'value') else str(edge.edge_type),
                    properties=edge.properties or {},
                )
                for edge in patient_graph.edges
            ]

            return BuildGraphResponse(
                request_id=request_id,
                patient_id=request.patient_id,
                note_id=result.note_id,
                nodes=nodes_response,
                edges=edges_response,
                node_count=patient_graph.node_count,
                edge_count=patient_graph.edge_count,
                entities_mapped=result.entities_mapped,
                processing_time_ms=result.processing_time_ms,
                coverage_stats=result.coverage_stats,
            )

    except Exception as e:
        raise InternalError(
            message=f"Failed to build knowledge graph: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )


@router.post(
    "/batch-build-graph",
    summary="Build knowledge graph from multiple notes",
    description="Process multiple clinical notes and build a combined knowledge graph for a patient.",
)
async def batch_build_knowledge_graph(
    patient_id: str = Query(..., description="Patient identifier"),
    notes: list[str] = Body(..., description="List of clinical note texts"),
) -> dict:
    """Build a knowledge graph from multiple clinical notes.

    This endpoint processes multiple notes for a single patient and builds
    a combined knowledge graph. Useful for processing longitudinal patient data.

    Args:
        patient_id: The patient identifier.
        notes: List of clinical note texts.

    Returns:
        Dictionary with graph statistics and summary.
    """
    try:
        from sqlalchemy.orm import Session
        from app.core.database import get_sync_engine
        from app.services.ontology_graph_integration import OntologyGraphIntegration
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        request_id = str(uuid4())
        total_nodes = 0
        total_edges = 0
        total_entities = 0
        note_results = []

        with Session(get_sync_engine()) as session:
            integration = OntologyGraphIntegration(session)

            for i, note_text in enumerate(notes):
                result = integration.ingest_note(
                    note_text=note_text,
                    patient_id=patient_id,
                    note_id=f"note_{i+1}",
                )

                note_results.append({
                    "note_index": i,
                    "note_id": result.note_id,
                    "nodes_created": result.nodes_created,
                    "edges_created": result.edges_created,
                    "entities_mapped": result.entities_mapped,
                })

                total_nodes += result.nodes_created
                total_edges += result.edges_created
                total_entities += result.entities_mapped

            # Commit all changes
            session.commit()

            # Get final graph stats
            graph_service = DatabaseGraphBuilderService(session)
            patient_graph = graph_service.get_patient_graph(patient_id)

            return {
                "request_id": request_id,
                "patient_id": patient_id,
                "notes_processed": len(notes),
                "total_nodes": patient_graph.node_count,
                "total_edges": patient_graph.edge_count,
                "total_entities_mapped": total_entities,
                "note_results": note_results,
                "graph_url": f"/patients/{patient_id}/graph",
            }

    except Exception as e:
        raise InternalError(
            message=f"Failed to build batch knowledge graph: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )
