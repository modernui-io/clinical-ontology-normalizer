"""Document Tags API endpoints - Tagging, categorization, and clinical decision support."""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.models.clinical_value import ValueType
from app.services.value_extraction import get_value_extraction_service
from app.services.nlp_clinical_ner import get_clinical_ner_service
from app.services.relation_extraction import get_relation_extraction_service, RelationType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents", "clinical-decision-support"])


# ============================================================================
# Value Extraction Endpoints
# ============================================================================


class ExtractValuesRequest(BaseModel):
    """Request body for clinical value extraction."""

    text: str = Field(..., description="Clinical note text to extract values from")
    include_vitals: bool = Field(True, description="Extract vital signs")
    include_labs: bool = Field(True, description="Extract lab results")
    include_measurements: bool = Field(True, description="Extract clinical measurements")
    include_medications: bool = Field(True, description="Extract medication doses")


class ExtractedValuePreview(BaseModel):
    """Preview of an extracted clinical value."""

    text: str = Field(..., description="The extracted text span")
    start_offset: int = Field(..., description="Character start position")
    end_offset: int = Field(..., description="Character end position")
    name: str = Field(..., description="Name/label of the measurement")
    value_type: str = Field(..., description="Type of value (vital_sign, lab_result, etc.)")
    value: float | None = Field(None, description="Primary numeric value")
    value_secondary: float | None = Field(None, description="Secondary value (e.g., diastolic BP)")
    unit: str | None = Field(None, description="Unit of measurement")
    unit_normalized: str | None = Field(None, description="Normalized standard unit")
    frequency: str | None = Field(None, description="Medication frequency (e.g., BID)")
    route: str | None = Field(None, description="Medication route (e.g., oral)")
    omop_concept_id: int | None = Field(None, description="Linked OMOP concept ID")
    confidence: float = Field(..., description="Extraction confidence 0.0-1.0")


class ExtractValuesResponse(BaseModel):
    """Response from clinical value extraction."""

    values: list[ExtractedValuePreview] = Field(..., description="Extracted clinical values")
    extraction_time_ms: float = Field(..., description="Time taken for extraction in ms")
    value_count: int = Field(..., description="Total number of values extracted")
    by_type: dict[str, int] = Field(..., description="Count of values by type")


@router.post(
    "/preview/values",
    response_model=ExtractValuesResponse,
    summary="Extract clinical values without saving",
    description="Extract vital signs, lab results, measurements, and medication doses from clinical text.",
)
async def preview_value_extraction(
    request: ExtractValuesRequest,
) -> ExtractValuesResponse:
    """Run clinical value extraction on text.

    This endpoint extracts quantitative clinical data:
    - Vital signs: BP, HR, RR, Temp, O2 sat, Weight, Height, BMI
    - Lab results: Chemistry (Na, K, Cr, BUN, glucose), CBC (WBC, Hgb, Plt), etc.
    - Measurements: EF, LVEF
    - Medication doses: Drug name, dose, unit, frequency, route

    Results are NOT saved to the database. Use for previewing extraction.

    Args:
        request: The text to extract from and extraction options.

    Returns:
        ExtractValuesResponse with extracted values and timing.
    """
    import time

    # Get extraction service
    service = get_value_extraction_service()

    # Run extraction with timing
    start_time = time.perf_counter()
    extracted = service.extract_all(
        text=request.text,
        include_vitals=request.include_vitals,
        include_labs=request.include_labs,
        include_measurements=request.include_measurements,
        include_medications=request.include_medications,
    )
    extraction_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert to preview format
    values = [
        ExtractedValuePreview(
            text=v.text,
            start_offset=v.start_offset,
            end_offset=v.end_offset,
            name=v.name,
            value_type=v.value_type.value,
            value=v.value,
            value_secondary=v.value_secondary,
            unit=v.unit,
            unit_normalized=v.unit_normalized,
            frequency=v.frequency,
            route=v.route,
            omop_concept_id=v.omop_concept_id,
            confidence=v.confidence,
        )
        for v in extracted
    ]

    # Count by type
    by_type: dict[str, int] = {}
    for v in extracted:
        type_name = v.value_type.value
        by_type[type_name] = by_type.get(type_name, 0) + 1

    return ExtractValuesResponse(
        values=values,
        extraction_time_ms=round(extraction_time_ms, 2),
        value_count=len(values),
        by_type=by_type,
    )


# ============================================================================
# Clinical NER Endpoints
# ============================================================================


class ExtractNERRequest(BaseModel):
    """Request body for clinical NER extraction."""

    text: str = Field(..., description="Clinical note text to extract entities from")
    note_type: str | None = Field(None, description="Type of clinical note for context")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold")


class ExtractedNEREntity(BaseModel):
    """Preview of an extracted clinical entity."""

    text: str = Field(..., description="The extracted text span")
    start_offset: int = Field(..., description="Character start position")
    end_offset: int = Field(..., description="Character end position")
    normalized_text: str = Field(..., description="Normalized/lemmatized form")
    domain: str | None = Field(None, description="OMOP domain (Condition, Drug, Procedure, etc.)")
    section: str | None = Field(None, description="Clinical section detected")
    assertion: str = Field(..., description="Assertion status (present/absent/possible)")
    temporality: str = Field(..., description="Temporal context (current/past/future)")
    experiencer: str = Field(..., description="Who it applies to (patient/family/other)")
    confidence: float = Field(..., description="Extraction confidence 0.0-1.0")


class ExtractNERResponse(BaseModel):
    """Response from clinical NER extraction."""

    entities: list[ExtractedNEREntity] = Field(..., description="Extracted clinical entities")
    extraction_time_ms: float = Field(..., description="Time taken for extraction in ms")
    entity_count: int = Field(..., description="Total number of entities extracted")
    by_domain: dict[str, int] = Field(..., description="Count of entities by domain")
    model_info: dict[str, bool] = Field(..., description="Information about available models")


@router.post(
    "/preview/ner",
    response_model=ExtractNERResponse,
    summary="Extract clinical entities using ML NER",
    description="Run ML-based Named Entity Recognition on clinical text using transformer models.",
)
async def preview_ner_extraction(
    request: ExtractNERRequest,
) -> ExtractNERResponse:
    """Run clinical NER extraction on text using ML models.

    This endpoint uses transformer-based NER models (Bio_ClinicalBERT variants)
    to extract clinical entities from text. It identifies:
    - Conditions/Diseases: Medical problems, symptoms
    - Drugs/Medications: Treatment drugs, chemicals
    - Procedures: Medical procedures
    - Measurements/Tests: Lab tests, diagnostic procedures
    - Anatomic sites: Body parts, organs

    Results include context detection (assertion, temporality, experiencer).
    Results are NOT saved to the database. Use for previewing extraction.

    Args:
        request: The text to extract from and configuration options.

    Returns:
        ExtractNERResponse with extracted entities and timing.
    """
    import time

    # Get NER service
    service = get_clinical_ner_service()

    # Run extraction with timing
    start_time = time.perf_counter()
    extracted = service.extract_mentions(
        text=request.text,
        document_id=uuid4(),  # Dummy ID for preview
        note_type=request.note_type,
    )
    extraction_time_ms = (time.perf_counter() - start_time) * 1000

    # Filter by confidence
    extracted = [e for e in extracted if e.confidence >= request.min_confidence]

    # Convert to preview format
    entities = [
        ExtractedNEREntity(
            text=e.text,
            start_offset=e.start_offset,
            end_offset=e.end_offset,
            normalized_text=e.lexical_variant,
            domain=e.domain_hint,
            section=e.section,
            assertion=e.assertion.value,
            temporality=e.temporality.value,
            experiencer=e.experiencer.value,
            confidence=e.confidence,
        )
        for e in extracted
    ]

    # Count by domain
    by_domain: dict[str, int] = {}
    for e in extracted:
        domain = e.domain_hint or "Unknown"
        by_domain[domain] = by_domain.get(domain, 0) + 1

    # Model availability info
    model_info = {
        "spacy_available": service._spacy_available if service._initialized else False,
        "transformer_available": service._transformer_available if service._initialized else False,
    }

    return ExtractNERResponse(
        entities=entities,
        extraction_time_ms=round(extraction_time_ms, 2),
        entity_count=len(entities),
        by_domain=by_domain,
        model_info=model_info,
    )


# ============================================================================
# Relation Extraction Endpoints
# ============================================================================


class ExtractRelationsRequest(BaseModel):
    """Request body for clinical relation extraction."""

    text: str = Field(..., description="Clinical note text to extract relations from")
    use_ner: bool = Field(True, description="Use NER to extract mentions first")
    use_patterns: bool = Field(True, description="Use pattern matching for relation extraction")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold")


class ExtractedRelationPreview(BaseModel):
    """Preview of an extracted clinical relation."""

    source_text: str = Field(..., description="Source entity text")
    source_start: int = Field(..., description="Source entity start position")
    source_end: int = Field(..., description="Source entity end position")
    source_domain: str | None = Field(None, description="Source entity domain")

    target_text: str = Field(..., description="Target entity text")
    target_start: int = Field(..., description="Target entity start position")
    target_end: int = Field(..., description="Target entity end position")
    target_domain: str | None = Field(None, description="Target entity domain")

    relation_type: str = Field(..., description="Type of relation (treats, causes, etc.)")
    confidence: float = Field(..., description="Extraction confidence 0.0-1.0")
    evidence_text: str = Field(..., description="Text span containing the relation")
    extraction_method: str = Field(..., description="How the relation was extracted")


class ExtractRelationsResponse(BaseModel):
    """Response from clinical relation extraction."""

    relations: list[ExtractedRelationPreview] = Field(..., description="Extracted relations")
    extraction_time_ms: float = Field(..., description="Time taken for extraction in ms")
    relation_count: int = Field(..., description="Total number of relations extracted")
    by_type: dict[str, int] = Field(..., description="Count of relations by type")
    entity_count: int = Field(0, description="Number of entities found (if NER was used)")


@router.post(
    "/preview/relations",
    response_model=ExtractRelationsResponse,
    summary="Extract clinical relations",
    description="Extract relationships between clinical entities (drug-treats-condition, etc.).",
)
async def preview_relation_extraction(
    request: ExtractRelationsRequest,
) -> ExtractRelationsResponse:
    """Run clinical relation extraction on text.

    This endpoint extracts relationships between clinical entities:
    - Treatment relations: Drug treats Condition
    - Adverse relations: Drug causes Side Effect
    - Diagnostic relations: Test diagnoses Condition
    - Procedural relations: Procedure for Condition

    Can optionally run NER first to extract entities, then find relations
    between them. Results are NOT saved to the database.

    Args:
        request: The text to extract from and configuration options.

    Returns:
        ExtractRelationsResponse with extracted relations and timing.
    """
    import time

    # Get services
    relation_service = get_relation_extraction_service()
    ner_service = get_clinical_ner_service()

    # Run extraction with timing
    start_time = time.perf_counter()

    mentions = None
    entity_count = 0

    # Optionally run NER first
    if request.use_ner:
        mentions = ner_service.extract_mentions(
            text=request.text,
            document_id=uuid4(),
            note_type=None,
        )
        entity_count = len(mentions)

    # Extract relations
    if request.use_patterns:
        relations = relation_service.extract_all(request.text, mentions)
    else:
        relations = relation_service.extract_mention_relations(request.text, mentions or [])

    extraction_time_ms = (time.perf_counter() - start_time) * 1000

    # Filter by confidence
    relations = [r for r in relations if r.confidence >= request.min_confidence]

    # Convert to preview format
    relation_previews = [
        ExtractedRelationPreview(
            source_text=r.source_text,
            source_start=r.source_start,
            source_end=r.source_end,
            source_domain=r.source_domain,
            target_text=r.target_text,
            target_start=r.target_start,
            target_end=r.target_end,
            target_domain=r.target_domain,
            relation_type=r.relation_type.value,
            confidence=r.confidence,
            evidence_text=r.evidence_text,
            extraction_method=r.extraction_method,
        )
        for r in relations
    ]

    # Count by type
    by_type: dict[str, int] = {}
    for r in relations:
        type_name = r.relation_type.value
        by_type[type_name] = by_type.get(type_name, 0) + 1

    return ExtractRelationsResponse(
        relations=relation_previews,
        extraction_time_ms=round(extraction_time_ms, 2),
        relation_count=len(relations),
        by_type=by_type,
        entity_count=entity_count,
    )


# ============================================================================
# Ensemble Extraction Endpoint
# ============================================================================


class EnsembleExtractRequest(BaseModel):
    """Request body for ensemble clinical extraction."""

    text: str = Field(..., description="Clinical note text to process")
    note_type: str | None = Field(None, description="Type of clinical note for context")
    use_rule_based: bool = Field(True, description="Enable rule-based extraction")
    use_ml_ner: bool = Field(True, description="Enable ML NER extraction")
    use_value_extraction: bool = Field(True, description="Enable value extraction")
    use_relation_extraction: bool = Field(True, description="Enable relation extraction")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold")


class EnsembleMentionPreview(BaseModel):
    """Preview of an extracted mention from ensemble."""

    text: str = Field(..., description="The extracted text span")
    start_offset: int = Field(..., description="Character start position")
    end_offset: int = Field(..., description="Character end position")
    normalized_text: str = Field(..., description="Normalized/lemmatized form")
    domain: str | None = Field(None, description="OMOP domain")
    section: str | None = Field(None, description="Clinical section detected")
    assertion: str = Field(..., description="Assertion status")
    temporality: str = Field(..., description="Temporal context")
    experiencer: str = Field(..., description="Who it applies to")
    confidence: float = Field(..., description="Extraction confidence")
    omop_concept_id: int | None = Field(None, description="Linked OMOP concept ID")


class EnsembleExtractResponse(BaseModel):
    """Response from ensemble clinical extraction."""

    mentions: list[EnsembleMentionPreview] = Field(..., description="Extracted mentions")
    relations: list[ExtractedRelationPreview] = Field(..., description="Extracted relations")
    extraction_time_ms: float = Field(..., description="Total extraction time in ms")
    mention_count: int = Field(..., description="Number of mentions extracted")
    relation_count: int = Field(..., description="Number of relations extracted")
    by_domain: dict[str, int] = Field(..., description="Mentions by domain")
    by_relation_type: dict[str, int] = Field(..., description="Relations by type")


@router.post(
    "/preview/ensemble",
    response_model=EnsembleExtractResponse,
    summary="Run full ensemble extraction pipeline",
    description="Extract mentions and relations using all available NLP methods combined.",
)
async def preview_ensemble_extraction(
    request: EnsembleExtractRequest,
) -> EnsembleExtractResponse:
    """Run full ensemble extraction pipeline on clinical text.

    This endpoint combines multiple extraction methods:
    - **Rule-based**: High-precision patterns for medications, vitals, labs
    - **ML NER**: Transformer-based entity recognition for conditions, drugs
    - **Value extraction**: Quantitative measurements with unit normalization
    - **Relation extraction**: Relationships like drug-treats-condition

    Results are merged and deduplicated, with confidence boosting when
    multiple methods agree. NOT saved to database - use for previewing.

    Args:
        request: The text to extract from and configuration options.

    Returns:
        EnsembleExtractResponse with mentions, relations, and statistics.
    """
    import time

    # Configure and get ensemble service
    from app.services.nlp_ensemble import EnsembleConfig, EnsembleNLPService

    config = EnsembleConfig(
        use_rule_based=request.use_rule_based,
        use_ml_ner=request.use_ml_ner,
        use_value_extraction=request.use_value_extraction,
        use_relation_extraction=request.use_relation_extraction,
        min_confidence=request.min_confidence,
    )

    # Create a new service instance with this config (don't pollute singleton)
    service = EnsembleNLPService(config=config)

    # Run extraction
    start_time = time.perf_counter()
    result = service.extract_all(
        text=request.text,
        document_id=uuid4(),
        note_type=request.note_type,
    )
    total_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert mentions to preview format
    mentions = [
        EnsembleMentionPreview(
            text=m.text,
            start_offset=m.start_offset,
            end_offset=m.end_offset,
            normalized_text=m.lexical_variant,
            domain=m.domain_hint,
            section=m.section,
            assertion=m.assertion.value,
            temporality=m.temporality.value,
            experiencer=m.experiencer.value,
            confidence=m.confidence,
            omop_concept_id=m.omop_concept_id,
        )
        for m in result.mentions
    ]

    # Convert relations to preview format
    relations = [
        ExtractedRelationPreview(
            source_text=r.source_text,
            source_start=r.source_start,
            source_end=r.source_end,
            source_domain=r.source_domain,
            target_text=r.target_text,
            target_start=r.target_start,
            target_end=r.target_end,
            target_domain=r.target_domain,
            relation_type=r.relation_type.value,
            confidence=r.confidence,
            evidence_text=r.evidence_text,
            extraction_method=r.extraction_method,
        )
        for r in result.relations
    ]

    return EnsembleExtractResponse(
        mentions=mentions,
        relations=relations,
        extraction_time_ms=round(total_time_ms, 2),
        mention_count=len(mentions),
        relation_count=len(relations),
        by_domain=result.stats.get("by_domain", {}),
        by_relation_type=result.stats.get("by_relation_type", {}),
    )


# ============================================================================
# Drug Interaction Checking Endpoint
# ============================================================================


class DrugInteractionCheckRequest(BaseModel):
    """Request body for drug interaction check."""

    drugs: list[str] = Field(..., description="List of drug names to check for interactions")


class DrugInteractionResult(BaseModel):
    """A single drug interaction."""

    drug1: str = Field(..., description="First drug in the interaction")
    drug2: str = Field(..., description="Second drug in the interaction")
    severity: str = Field(..., description="Severity level (contraindicated, major, moderate, minor)")
    interaction_type: str = Field(..., description="Type of interaction (pharmacokinetic, etc.)")
    description: str = Field(..., description="Description of the interaction mechanism")
    clinical_effect: str = Field(..., description="Clinical effects/risks")
    management: str = Field(..., description="Recommended management strategy")
    references: list[str] = Field(..., description="Source references")


class DrugInteractionCheckResponse(BaseModel):
    """Response from drug interaction check."""

    drugs_checked: list[str] = Field(..., description="Normalized list of drugs that were checked")
    interactions: list[DrugInteractionResult] = Field(..., description="Found interactions")
    total_interactions: int = Field(..., description="Total number of interactions found")
    by_severity: dict[str, int] = Field(..., description="Count by severity level")
    highest_severity: str | None = Field(None, description="Most severe interaction level found")
    has_contraindicated: bool = Field(..., description="Whether any contraindicated combinations exist")
    has_major: bool = Field(..., description="Whether any major interactions exist")
    check_time_ms: float = Field(..., description="Time taken for the check in ms")
    database_stats: dict = Field(..., description="Drug interaction database statistics")


@router.post(
    "/clinical/drug-interactions",
    response_model=DrugInteractionCheckResponse,
    summary="Check for drug-drug interactions",
    description="Check a list of medications for known drug-drug interactions.",
)
async def check_drug_interactions(
    request: DrugInteractionCheckRequest,
) -> DrugInteractionCheckResponse:
    """Check for drug-drug interactions among a list of medications.

    This endpoint checks for known clinically significant drug-drug interactions
    based on FDA labels and clinical guidelines. It returns:

    - **Contraindicated**: Combinations that should never be used together
    - **Major**: Serious interactions requiring close monitoring or avoidance
    - **Moderate**: Interactions requiring caution and monitoring
    - **Minor**: Usually not clinically significant

    Supports both generic and brand names, as well as common abbreviations
    (e.g., ASA for aspirin, HCTZ for hydrochlorothiazide).

    Args:
        request: List of drug names to check.

    Returns:
        DrugInteractionCheckResponse with all found interactions and statistics.
    """
    import time
    from app.services.drug_interactions import get_drug_interaction_service

    start_time = time.perf_counter()

    service = get_drug_interaction_service()
    result = service.check_interactions(request.drugs)

    check_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert interactions to response format
    interactions = [
        DrugInteractionResult(
            drug1=i.drug1,
            drug2=i.drug2,
            severity=i.severity.value,
            interaction_type=i.interaction_type.value,
            description=i.description,
            clinical_effect=i.clinical_effect,
            management=i.management,
            references=i.references,
        )
        for i in result.interactions_found
    ]

    return DrugInteractionCheckResponse(
        drugs_checked=result.drugs_checked,
        interactions=interactions,
        total_interactions=result.total_interactions,
        by_severity=result.by_severity,
        highest_severity=result.highest_severity.value if result.highest_severity else None,
        has_contraindicated=result.has_contraindicated,
        has_major=result.has_major,
        check_time_ms=round(check_time_ms, 2),
        database_stats=service.get_stats(),
    )


# ============================================================================
# Lab Interpretation Endpoint
# ============================================================================


class LabValue(BaseModel):
    """A single lab value for interpretation."""

    test: str = Field(..., description="Test name, code, or alias (e.g., 'Na', 'sodium', 'K')")
    value: float = Field(..., description="Numeric value")


class LabInterpretRequest(BaseModel):
    """Request body for lab interpretation."""

    values: list[LabValue] = Field(..., description="List of lab values to interpret")
    gender: str | None = Field(None, description="Patient gender ('male' or 'female') for gender-specific ranges")


class LabInterpretResult(BaseModel):
    """Interpretation result for a single lab value."""

    test_name: str = Field(..., description="Full test name")
    value: float = Field(..., description="The input value")
    unit: str = Field(..., description="Unit of measurement")
    level: str = Field(..., description="Interpretation level (critical_low, low, normal, high, critical_high)")
    reference_range: str = Field(..., description="Normal reference range (e.g., '136-145')")
    is_critical: bool = Field(..., description="Whether the value is critically abnormal")
    clinical_significance: str = Field(..., description="Clinical significance of the value")
    possible_causes: list[str] = Field(..., description="Possible causes of abnormal value")
    recommended_actions: list[str] = Field(..., description="Recommended clinical actions")


class LabInterpretResponse(BaseModel):
    """Response from lab interpretation."""

    interpretations: list[LabInterpretResult] = Field(..., description="Interpretations for each lab value")
    unrecognized_tests: list[str] = Field(..., description="Tests that were not recognized")
    total_interpreted: int = Field(..., description="Number of tests successfully interpreted")
    abnormal_count: int = Field(..., description="Number of abnormal values")
    critical_count: int = Field(..., description="Number of critical values")
    interpret_time_ms: float = Field(..., description="Time taken for interpretation in ms")
    database_stats: dict = Field(..., description="Lab reference database statistics")


@router.post(
    "/clinical/lab-interpret",
    response_model=LabInterpretResponse,
    summary="Interpret laboratory values",
    description="Interpret lab results with reference ranges and clinical guidance.",
)
async def interpret_lab_values(
    request: LabInterpretRequest,
) -> LabInterpretResponse:
    """Interpret laboratory values against reference ranges.

    This endpoint provides clinical interpretation for lab values including:
    - Normal/abnormal/critical classification
    - Reference ranges (with gender-specific values when applicable)
    - Possible causes of abnormal values
    - Recommended clinical actions

    Supports common lab tests from:
    - Basic Metabolic Panel (Na, K, Cl, CO2, BUN, Cr, Glucose)
    - Complete Metabolic Panel (plus ALT, AST, ALP, bilirubin, albumin)
    - Complete Blood Count (WBC, Hgb, Hct, Plt, MCV)
    - Coagulation (PT, INR, PTT)
    - Cardiac markers (Troponin, BNP)
    - Lipid panel (TC, LDL, HDL, TG)
    - Thyroid (TSH, FT4, FT3)
    - And more...

    Args:
        request: Lab values to interpret and optional patient gender.

    Returns:
        LabInterpretResponse with interpretations and statistics.
    """
    import time
    from app.services.lab_reference import get_lab_reference_service

    start_time = time.perf_counter()

    service = get_lab_reference_service()

    interpretations: list[LabInterpretResult] = []
    unrecognized: list[str] = []
    abnormal_count = 0
    critical_count = 0

    for lab in request.values:
        result = service.interpret(lab.test, lab.value, request.gender)

        if result is None:
            unrecognized.append(lab.test)
            continue

        if result.level.value != "normal":
            abnormal_count += 1

        if result.is_critical:
            critical_count += 1

        interpretations.append(
            LabInterpretResult(
                test_name=result.test_name,
                value=result.value,
                unit=result.unit,
                level=result.level.value,
                reference_range=result.reference_range,
                is_critical=result.is_critical,
                clinical_significance=result.clinical_significance,
                possible_causes=result.possible_causes,
                recommended_actions=result.recommended_actions,
            )
        )

    interpret_time_ms = (time.perf_counter() - start_time) * 1000

    return LabInterpretResponse(
        interpretations=interpretations,
        unrecognized_tests=unrecognized,
        total_interpreted=len(interpretations),
        abnormal_count=abnormal_count,
        critical_count=critical_count,
        interpret_time_ms=round(interpret_time_ms, 2),
        database_stats=service.get_stats(),
    )


# ============================================================================
# Clinical Calculator Endpoint
# ============================================================================


class CalculatorRequest(BaseModel):
    """Request body for clinical calculator."""

    calculator: str = Field(
        ...,
        description="Calculator name: bmi, chadsvasc, hasbled, meld, egfr, wells_dvt, curb65, framingham",
    )
    parameters: dict = Field(
        ...,
        description="Calculator-specific parameters",
    )


class CalculatorResultResponse(BaseModel):
    """Response from clinical calculator."""

    calculator_name: str = Field(..., description="Full name of the calculator")
    score: float = Field(..., description="Calculated score")
    score_unit: str = Field(..., description="Unit of the score (points, %, kg/m2, etc.)")
    risk_level: str = Field(..., description="Risk level (low, moderate, high, very_high)")
    interpretation: str = Field(..., description="Clinical interpretation of the score")
    recommendations: list[str] = Field(..., description="Clinical recommendations based on score")
    components: dict = Field(..., description="Individual components that contribute to the score")
    references: list[str] = Field(..., description="Source references")
    calculation_time_ms: float = Field(..., description="Time taken for calculation in ms")


class CalculatorListResponse(BaseModel):
    """Response listing available calculators."""

    calculators: list[dict] = Field(..., description="Available calculators with their parameters")
    total_count: int = Field(..., description="Total number of calculators")


@router.get(
    "/clinical/calculators",
    response_model=CalculatorListResponse,
    summary="List available clinical calculators",
    description="Get a list of all available clinical risk calculators and their parameters.",
)
async def list_calculators() -> CalculatorListResponse:
    """List all available clinical risk calculators.

    Returns information about each calculator including:
    - Calculator name and description
    - Required and optional parameters
    - Parameter types and valid ranges

    Returns:
        CalculatorListResponse with available calculators.
    """
    from app.services.clinical_calculators import ClinicalCalculatorService

    service = ClinicalCalculatorService()

    calculators = [
        {
            "name": "bmi",
            "full_name": "Body Mass Index (BMI)",
            "description": "Calculates BMI for obesity classification",
            "required_params": {"weight_kg": "Weight in kilograms", "height_cm": "Height in centimeters"},
            "optional_params": {},
        },
        {
            "name": "chadsvasc",
            "full_name": "CHA2DS2-VASc Score",
            "description": "Stroke risk assessment for atrial fibrillation",
            "required_params": {"age": "Patient age in years", "female": "True if female sex"},
            "optional_params": {
                "congestive_heart_failure": "History of CHF",
                "hypertension": "History of hypertension",
                "diabetes": "History of diabetes",
                "stroke_tia_thromboembolism": "Prior stroke/TIA/thromboembolism",
                "vascular_disease": "History of vascular disease",
            },
        },
        {
            "name": "hasbled",
            "full_name": "HAS-BLED Score",
            "description": "Bleeding risk in atrial fibrillation patients on anticoagulation",
            "required_params": {},
            "optional_params": {
                "hypertension": "Uncontrolled hypertension (>160 mmHg)",
                "renal_disease": "Chronic dialysis/transplant/Cr>2.3",
                "liver_disease": "Chronic liver disease or bilirubin>2x/enzymes>3x",
                "stroke_history": "Prior stroke history",
                "bleeding_history": "Prior major bleed or predisposition",
                "labile_inr": "Unstable/high INRs (time in range <60%)",
                "age_over_65": "Age > 65 years",
                "antiplatelet_or_nsaid": "Concurrent antiplatelet or NSAID use",
                "alcohol": "Alcohol abuse (>8 drinks/week)",
            },
        },
        {
            "name": "meld",
            "full_name": "MELD Score (Model for End-Stage Liver Disease)",
            "description": "Severity of chronic liver disease for transplant prioritization",
            "required_params": {
                "creatinine": "Serum creatinine (mg/dL)",
                "bilirubin": "Total bilirubin (mg/dL)",
                "inr": "INR",
            },
            "optional_params": {
                "sodium": "Serum sodium (mEq/L) for MELD-Na calculation",
                "on_dialysis": "On dialysis twice in past week",
            },
        },
        {
            "name": "egfr",
            "full_name": "eGFR (CKD-EPI 2021)",
            "description": "Estimated glomerular filtration rate for kidney function",
            "required_params": {
                "creatinine": "Serum creatinine (mg/dL)",
                "age": "Patient age in years",
                "female": "True if female sex",
            },
            "optional_params": {},
        },
        {
            "name": "wells_dvt",
            "full_name": "Wells' Criteria for DVT",
            "description": "Clinical probability of deep vein thrombosis",
            "required_params": {},
            "optional_params": {
                "active_cancer": "Active cancer (within 6 months)",
                "paralysis_immobilization": "Paralysis/paresis/recent immobilization of lower extremity",
                "bedridden_3_days": "Bedridden >3 days or major surgery in past 12 weeks",
                "localized_tenderness": "Localized tenderness along deep venous system",
                "entire_leg_swollen": "Entire leg swollen",
                "calf_swelling_3cm": "Calf swelling >3cm vs asymptomatic leg",
                "pitting_edema": "Pitting edema confined to symptomatic leg",
                "collateral_superficial_veins": "Collateral superficial veins",
                "previous_dvt": "Previously documented DVT",
                "alternative_diagnosis_likely": "Alternative diagnosis as likely or more likely than DVT (-2 points)",
            },
        },
        {
            "name": "curb65",
            "full_name": "CURB-65 Score",
            "description": "Pneumonia severity assessment for disposition decisions",
            "required_params": {},
            "optional_params": {
                "confusion": "New-onset confusion",
                "bun_over_19": "BUN > 19 mg/dL (or Urea > 7 mmol/L)",
                "respiratory_rate_over_30": "Respiratory rate >= 30/min",
                "sbp_under_90_or_dbp_under_60": "SBP < 90 or DBP <= 60 mmHg",
                "age_65_or_older": "Age >= 65 years",
            },
        },
        {
            "name": "framingham",
            "full_name": "Framingham 10-Year CVD Risk",
            "description": "10-year cardiovascular disease risk prediction",
            "required_params": {
                "age": "Patient age (30-74 years)",
                "female": "True if female sex",
                "total_cholesterol": "Total cholesterol (mg/dL)",
                "hdl_cholesterol": "HDL cholesterol (mg/dL)",
                "systolic_bp": "Systolic blood pressure (mmHg)",
            },
            "optional_params": {
                "bp_treated": "On blood pressure treatment",
                "smoker": "Current smoker",
                "diabetic": "Has diabetes",
            },
        },
    ]

    return CalculatorListResponse(
        calculators=calculators,
        total_count=len(calculators),
    )


@router.post(
    "/clinical/calculate",
    response_model=CalculatorResultResponse,
    summary="Run a clinical calculator",
    description="Calculate clinical risk scores using validated calculators.",
)
async def run_calculator(
    request: CalculatorRequest,
) -> CalculatorResultResponse:
    """Run a clinical risk calculator.

    Available calculators:

    - **bmi**: Body Mass Index - obesity classification
    - **chadsvasc**: CHA2DS2-VASc - stroke risk in atrial fibrillation
    - **hasbled**: HAS-BLED - bleeding risk on anticoagulation
    - **meld**: MELD/MELD-Na - liver disease severity for transplant
    - **egfr**: CKD-EPI eGFR - estimated kidney function
    - **wells_dvt**: Wells' Criteria - DVT clinical probability
    - **curb65**: CURB-65 - pneumonia severity/disposition
    - **framingham**: Framingham - 10-year CVD risk prediction

    Each calculator returns:
    - Score with units
    - Risk level classification
    - Clinical interpretation
    - Evidence-based recommendations
    - Component breakdown
    - Source references

    Args:
        request: Calculator name and parameters.

    Returns:
        CalculatorResultResponse with calculated score and interpretation.

    Raises:
        HTTPException: 400 if calculator unknown or parameters invalid.
    """
    import time
    from app.services.clinical_calculators import get_clinical_calculator_service

    start_time = time.perf_counter()

    service = get_clinical_calculator_service()

    # Validate calculator exists
    available = service.get_available_calculators()
    if request.calculator.lower() not in available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown calculator '{request.calculator}'. Available: {', '.join(available)}",
        )

    try:
        result = service.calculate(request.calculator.lower(), **request.parameters)
    except TypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters for {request.calculator}: {e}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Calculation error for {request.calculator}: {e}",
        )

    calculation_time_ms = (time.perf_counter() - start_time) * 1000

    return CalculatorResultResponse(
        calculator_name=result.calculator_name,
        score=result.score,
        score_unit=result.score_unit,
        risk_level=result.risk_level.value,
        interpretation=result.interpretation,
        recommendations=result.recommendations,
        components=result.components,
        references=result.references,
        calculation_time_ms=round(calculation_time_ms, 2),
    )


# ============================================================================
# Differential Diagnosis Endpoint
# ============================================================================


class DifferentialDiagnosisRequest(BaseModel):
    """Request body for differential diagnosis generation."""

    findings: list[str] = Field(
        ...,
        description="List of clinical findings (symptoms, signs, abnormalities)",
    )
    age: int | None = Field(None, ge=0, le=120, description="Patient age in years")
    gender: str | None = Field(None, description="Patient gender ('male' or 'female')")
    max_diagnoses: int = Field(10, ge=1, le=20, description="Maximum diagnoses to return")


class DiagnosisCandidateResponse(BaseModel):
    """A candidate diagnosis in the differential."""

    name: str = Field(..., description="Diagnosis name")
    omop_concept_id: int | None = Field(None, description="OMOP concept ID")
    icd10_code: str | None = Field(None, description="ICD-10 code")
    domain: str = Field(..., description="Clinical domain (cardiovascular, respiratory, etc.)")
    urgency: str = Field(..., description="Urgency level (emergent, urgent, semi_urgent, routine)")
    probability_score: float = Field(..., description="Relative probability score (0-1)")
    supporting_findings: list[str] = Field(..., description="Findings supporting this diagnosis")
    opposing_findings: list[str] = Field(..., description="Findings arguing against")
    red_flags: list[str] = Field(..., description="Warning signs to watch for")
    recommended_workup: list[str] = Field(..., description="Suggested diagnostic tests")
    key_features: list[str] = Field(..., description="Classic features of this diagnosis")


class DifferentialDiagnosisResponse(BaseModel):
    """Response from differential diagnosis generation."""

    presenting_findings: list[str] = Field(..., description="Input findings")
    age: int | None = Field(None, description="Patient age if provided")
    gender: str | None = Field(None, description="Patient gender if provided")
    differential: list[DiagnosisCandidateResponse] = Field(..., description="Ranked differential diagnoses")
    red_flag_diagnoses: list[str] = Field(..., description="High-urgency diagnoses to rule out")
    cannot_miss_diagnoses: list[str] = Field(..., description="Must-not-miss diagnoses")
    suggested_history: list[str] = Field(..., description="Additional history to gather")
    suggested_exam: list[str] = Field(..., description="Physical exam maneuvers")
    generation_time_ms: float = Field(..., description="Time taken in ms")
    database_stats: dict = Field(..., description="Diagnosis database statistics")


@router.post(
    "/clinical/differential",
    response_model=DifferentialDiagnosisResponse,
    summary="Generate differential diagnosis",
    description="Generate a ranked differential diagnosis from clinical findings.",
)
async def generate_differential_diagnosis(
    request: DifferentialDiagnosisRequest,
) -> DifferentialDiagnosisResponse:
    """Generate a ranked differential diagnosis based on clinical findings.

    This endpoint provides clinical decision support by analyzing presenting
    symptoms, signs, and findings to generate a ranked list of potential
    diagnoses. Results include:

    - **Probability ranking**: Diagnoses ranked by likelihood based on findings
    - **Urgency classification**: Emergent, urgent, semi-urgent, or routine
    - **Supporting evidence**: Which findings support each diagnosis
    - **Red flags**: Warning signs that require immediate attention
    - **Recommended workup**: Suggested diagnostic tests
    - **History/exam suggestions**: Additional data to gather

    Demographics (age, gender) adjust probability estimates based on
    disease epidemiology.

    **Important**: This is a clinical decision support tool and should not
    replace clinical judgment. All diagnoses should be confirmed through
    appropriate diagnostic workup.

    Args:
        request: Clinical findings and optional demographics.

    Returns:
        DifferentialDiagnosisResponse with ranked diagnoses and recommendations.
    """
    import time
    from app.services.differential_diagnosis import get_differential_diagnosis_service

    start_time = time.perf_counter()

    service = get_differential_diagnosis_service()

    result = service.generate_differential(
        findings=request.findings,
        age=request.age,
        gender=request.gender,
        max_diagnoses=request.max_diagnoses,
    )

    generation_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert to response format
    differential = [
        DiagnosisCandidateResponse(
            name=dx.name,
            omop_concept_id=dx.omop_concept_id,
            icd10_code=dx.icd10_code,
            domain=dx.domain.value,
            urgency=dx.urgency.value,
            probability_score=dx.probability_score,
            supporting_findings=dx.supporting_findings,
            opposing_findings=dx.opposing_findings,
            red_flags=dx.red_flags,
            recommended_workup=dx.recommended_workup,
            key_features=dx.key_features,
        )
        for dx in result.differential
    ]

    return DifferentialDiagnosisResponse(
        presenting_findings=result.presenting_findings,
        age=result.age,
        gender=result.gender,
        differential=differential,
        red_flag_diagnoses=result.red_flag_diagnoses,
        cannot_miss_diagnoses=result.cannot_miss_diagnoses,
        suggested_history=result.suggested_history,
        suggested_exam=result.suggested_exam,
        generation_time_ms=round(generation_time_ms, 2),
        database_stats=service.get_stats(),
    )


# ============================================================================
# Drug Safety Check Endpoint
# ============================================================================


class DrugSafetyCheckRequest(BaseModel):
    """Request body for drug safety check."""

    drug: str = Field(..., description="Drug name (generic or brand)")
    patient_conditions: list[str] | None = Field(None, description="Patient conditions/diagnoses")
    age: int | None = Field(None, ge=0, le=120, description="Patient age in years")
    pregnant: bool = Field(False, description="Whether patient is pregnant")
    lactating: bool = Field(False, description="Whether patient is lactating")
    egfr: float | None = Field(None, ge=0, description="eGFR for renal dosing (mL/min/1.73m2)")


class DrugContraindicationResponse(BaseModel):
    """A contraindication for a drug."""

    condition: str = Field(..., description="Contraindicated condition")
    rationale: str = Field(..., description="Reason for contraindication")


class DrugSafetyProfileResponse(BaseModel):
    """Drug safety profile summary."""

    drug_name: str = Field(..., description="Drug name")
    generic_name: str = Field(..., description="Generic name")
    drug_class: str = Field(..., description="Drug class")
    pregnancy_category: str = Field(..., description="Pregnancy category (A, B, C, D, X)")
    lactation_safety: str = Field(..., description="Lactation safety")
    black_box_warnings: list[str] = Field(..., description="Black box warnings")
    common_adverse_effects: list[str] = Field(..., description="Common side effects")
    serious_adverse_effects: list[str] = Field(..., description="Serious adverse effects")
    monitoring_parameters: list[str] = Field(..., description="Recommended monitoring")


class DrugSafetyCheckResponse(BaseModel):
    """Response from drug safety check."""

    drug_name: str = Field(..., description="Drug name checked")
    overall_safety: str = Field(..., description="Overall safety level (safe, caution, warning, contraindicated)")
    contraindicated_conditions: list[DrugContraindicationResponse] = Field(..., description="Contraindicated conditions")
    warnings: list[str] = Field(..., description="Warnings and black box alerts")
    cautions: list[str] = Field(..., description="Cautions")
    dosing_considerations: list[str] = Field(..., description="Dosing adjustments needed")
    monitoring_needed: list[str] = Field(..., description="Required monitoring")
    pregnancy_warning: str | None = Field(None, description="Pregnancy-specific warning")
    lactation_warning: str | None = Field(None, description="Lactation-specific warning")
    profile: DrugSafetyProfileResponse | None = Field(None, description="Full drug profile")
    check_time_ms: float = Field(..., description="Time taken in ms")
    database_stats: dict = Field(..., description="Safety database statistics")


@router.post(
    "/clinical/drug-safety",
    response_model=DrugSafetyCheckResponse,
    summary="Check drug safety for a patient",
    description="Check drug safety including contraindications, warnings, and dosing considerations.",
)
async def check_drug_safety(
    request: DrugSafetyCheckRequest,
) -> DrugSafetyCheckResponse:
    """Check drug safety for a specific patient context.

    This endpoint provides comprehensive drug safety checking including:

    - **Contraindications**: Conditions where the drug should not be used
    - **Black box warnings**: FDA-mandated serious warnings
    - **Pregnancy safety**: Category and specific risks
    - **Lactation safety**: Breastfeeding compatibility
    - **Dosing adjustments**: Renal, hepatic, age-based modifications
    - **Monitoring requirements**: Parameters to track during therapy
    - **Adverse effects**: Common and serious side effects

    The check considers:
    - Patient conditions/diagnoses
    - Age (pediatric/geriatric considerations)
    - Pregnancy and lactation status
    - Renal function (eGFR) for dosing

    **Important**: This is a clinical decision support tool. Always consult
    current prescribing information and exercise clinical judgment.

    Args:
        request: Drug and patient-specific parameters.

    Returns:
        DrugSafetyCheckResponse with safety assessment.
    """
    import time
    from app.services.drug_safety import get_drug_safety_service

    start_time = time.perf_counter()

    service = get_drug_safety_service()

    result = service.check_safety(
        drug=request.drug,
        patient_conditions=request.patient_conditions,
        age=request.age,
        pregnant=request.pregnant,
        lactating=request.lactating,
        egfr=request.egfr,
    )

    check_time_ms = (time.perf_counter() - start_time) * 1000

    # Build profile response if available
    profile_response = None
    if result.profile:
        profile_response = DrugSafetyProfileResponse(
            drug_name=result.profile.drug_name,
            generic_name=result.profile.generic_name,
            drug_class=result.profile.drug_class,
            pregnancy_category=result.profile.pregnancy_category.value,
            lactation_safety=result.profile.lactation_safety.value,
            black_box_warnings=result.profile.black_box_warnings,
            common_adverse_effects=result.profile.common_adverse_effects,
            serious_adverse_effects=result.profile.serious_adverse_effects,
            monitoring_parameters=result.profile.monitoring_parameters,
        )

    # Convert contraindications
    contraindications = [
        DrugContraindicationResponse(condition=c[0], rationale=c[1])
        for c in result.contraindicated_conditions
    ]

    return DrugSafetyCheckResponse(
        drug_name=result.drug_name,
        overall_safety=result.overall_safety.value,
        contraindicated_conditions=contraindications,
        warnings=result.warnings,
        cautions=result.cautions,
        dosing_considerations=result.dosing_considerations,
        monitoring_needed=result.monitoring_needed,
        pregnancy_warning=result.pregnancy_warning,
        lactation_warning=result.lactation_warning,
        profile=profile_response,
        check_time_ms=round(check_time_ms, 2),
        database_stats=service.get_stats(),
    )


# ============================================================================
# ICD-10 Code Suggestion Endpoint (with CER Framework)
# ============================================================================


class ICD10SuggestRequest(BaseModel):
    """Request body for ICD-10 code suggestion."""

    query: str = Field(
        ...,
        description="Clinical text or diagnosis to code (e.g., 'hypertension', 'type 2 diabetes')",
    )
    max_suggestions: int = Field(10, ge=1, le=20, description="Maximum codes to return")


class CERCitationResponse(BaseModel):
    """Claim-Evidence-Reasoning citation for a code suggestion."""

    claim: str = Field(..., description="The assertion about code appropriateness")
    evidence: list[str] = Field(..., description="Clinical findings supporting the claim")
    reasoning: str = Field(..., description="Explanation connecting evidence to the claim")
    strength: str = Field(..., description="Confidence strength (high, medium, low)")
    guidelines: list[str] = Field(default_factory=list, description="Relevant coding guidelines")


class ICD10SuggestionResponse(BaseModel):
    """A suggested ICD-10 code with CER citation."""

    code: str = Field(..., description="ICD-10-CM code")
    description: str = Field(..., description="Code description")
    confidence: str = Field(..., description="Confidence level (high, medium, low)")
    match_reason: str = Field(..., description="Why this code was matched")
    is_billable: bool = Field(..., description="Whether the code is billable")
    category: str = Field(..., description="ICD-10 chapter/category")
    cer_citation: CERCitationResponse = Field(..., description="CER citation for this suggestion")
    more_specific_codes: list[tuple[str, str]] = Field(
        default_factory=list, description="More specific codes available"
    )
    related_codes: list[tuple[str, str]] = Field(default_factory=list, description="Related codes")
    coding_guidance: list[str] = Field(default_factory=list, description="Coding guidance notes")


class ICD10SuggestResponse(BaseModel):
    """Response from ICD-10 code suggestion."""

    query: str = Field(..., description="Original query")
    suggestions: list[ICD10SuggestionResponse] = Field(..., description="Suggested codes with CER")
    total_matches: int = Field(..., description="Total codes matched")
    coding_tips: list[str] = Field(..., description="General coding tips")
    suggestion_time_ms: float = Field(..., description="Time taken in ms")
    database_stats: dict = Field(..., description="Code database statistics")


@router.post(
    "/clinical/icd10-suggest",
    response_model=ICD10SuggestResponse,
    summary="Suggest ICD-10 codes with CER citations",
    description="Suggest ICD-10-CM codes for a diagnosis with Claim-Evidence-Reasoning citations.",
)
async def suggest_icd10_codes(
    request: ICD10SuggestRequest,
) -> ICD10SuggestResponse:
    """Suggest ICD-10-CM codes for clinical diagnoses with CER citations.

    This endpoint provides ICD-10-CM code suggestions with Claim-Evidence-Reasoning
    (CER) citations to help clinicians understand WHY each code is suggested:

    - **Claim**: What code is being suggested and why
    - **Evidence**: Clinical findings supporting this code selection
    - **Reasoning**: Clinical logic connecting evidence to the code
    - **Guidelines**: Relevant ICD-10 coding guidelines

    Features:
    - Text-to-code mapping with natural language understanding
    - Synonym and alias matching (HTN->hypertension, DM->diabetes)
    - Code hierarchy navigation for specificity
    - Coding guidance for complex scenarios

    **Important**: Code suggestions should be verified by qualified medical coders.

    Args:
        request: Diagnosis text and configuration options.

    Returns:
        ICD10SuggestResponse with CER-cited code suggestions.
    """
    import time
    from app.services.icd10_suggester import get_icd10_suggester_service

    start_time = time.perf_counter()

    service = get_icd10_suggester_service()

    result = service.suggest_codes(
        query=request.query,
        max_suggestions=request.max_suggestions,
    )

    suggestion_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert to response format with CER citations
    suggestions = []
    for s in result.suggestions:
        cer_response = CERCitationResponse(
            claim=s.cer_citation.claim if s.cer_citation else f"{s.code} may be appropriate",
            evidence=s.cer_citation.evidence if s.cer_citation else [s.match_reason],
            reasoning=s.cer_citation.reasoning if s.cer_citation else "Based on term matching",
            strength=s.cer_citation.strength.value if s.cer_citation else s.confidence.value,
            guidelines=s.cer_citation.icd10_guidelines if s.cer_citation else [],
        )
        suggestions.append(
            ICD10SuggestionResponse(
                code=s.code,
                description=s.description,
                confidence=s.confidence.value,
                match_reason=s.match_reason,
                is_billable=s.is_billable,
                category=s.category,
                cer_citation=cer_response,
                more_specific_codes=s.more_specific_codes,
                related_codes=s.related_codes,
                coding_guidance=s.coding_guidance,
            )
        )

    return ICD10SuggestResponse(
        query=result.query,
        suggestions=suggestions,
        total_matches=result.total_matches,
        coding_tips=result.coding_tips,
        suggestion_time_ms=round(suggestion_time_ms, 2),
        database_stats=service.get_stats(),
    )


# ============================================================================
# CPT Code Suggestion Endpoint (with CER Framework)
# ============================================================================


class CPTSuggestRequest(BaseModel):
    """Request body for CPT code suggestion."""

    query: str = Field(
        ...,
        description="Procedure/service description (e.g., 'office visit', 'ecg')",
    )
    clinical_context: dict[str, str] | None = Field(
        None,
        description="Optional context: time_spent, mdm_complexity, new_patient, setting, diagnoses",
    )
    max_suggestions: int = Field(10, ge=1, le=20, description="Maximum codes to return")


class CPTCERCitationResponse(BaseModel):
    """Claim-Evidence-Reasoning citation for a CPT code suggestion."""

    claim: str = Field(..., description="The assertion about code appropriateness")
    evidence: list[str] = Field(..., description="Clinical documentation supporting the claim")
    reasoning: str = Field(..., description="Explanation connecting evidence to the claim")
    strength: str = Field(..., description="Confidence strength (high, medium, low)")


class DocumentationChecklistItem(BaseModel):
    """Documentation requirement checklist item."""

    element: str = Field(..., description="Required documentation element")
    present: bool | None = Field(None, description="Whether documented (null=unknown)")
    notes: str = Field("", description="Notes about this element")


class CPTSuggestionResponse(BaseModel):
    """A suggested CPT code with CER citation."""

    code: str = Field(..., description="CPT code")
    description: str = Field(..., description="Code description")
    category: str = Field(..., description="CPT category")
    confidence: str = Field(..., description="Confidence level")
    cer_citation: CPTCERCitationResponse = Field(..., description="CER citation")
    work_rvu: float = Field(..., description="Work RVU value")
    typical_time_minutes: int = Field(..., description="Typical time in minutes")
    suggested_modifiers: list[tuple[str, str]] = Field(
        default_factory=list, description="Suggested modifiers (code, description)"
    )
    documentation_checklist: list[DocumentationChecklistItem] = Field(
        default_factory=list, description="Documentation requirements"
    )
    supporting_diagnoses: list[tuple[str, str]] = Field(
        default_factory=list, description="Supporting ICD-10 codes"
    )
    alternative_codes: list[tuple[str, str]] = Field(
        default_factory=list, description="Alternative codes to consider"
    )
    coding_notes: list[str] = Field(default_factory=list, description="Coding notes")


class CPTSuggestResponse(BaseModel):
    """Response from CPT code suggestion."""

    query: str = Field(..., description="Original query")
    clinical_context: dict[str, str] = Field(..., description="Clinical context used")
    suggestions: list[CPTSuggestionResponse] = Field(..., description="Suggested codes with CER")
    total_matches: int = Field(..., description="Total codes matched")
    documentation_gaps: list[str] = Field(..., description="Missing documentation")
    coding_tips: list[str] = Field(..., description="Coding tips")
    suggestion_time_ms: float = Field(..., description="Time taken in ms")
    database_stats: dict = Field(..., description="Code database statistics")


@router.post(
    "/clinical/cpt-suggest",
    response_model=CPTSuggestResponse,
    summary="Suggest CPT codes with CER citations",
    description="Suggest CPT-4 codes for procedures with Claim-Evidence-Reasoning citations.",
)
async def suggest_cpt_codes(
    request: CPTSuggestRequest,
) -> CPTSuggestResponse:
    """Suggest CPT-4 codes for medical procedures with CER citations.

    This endpoint provides CPT code suggestions with Claim-Evidence-Reasoning
    (CER) citations to help clinicians understand WHY each code is suggested:

    - **Claim**: What code is being suggested for this service
    - **Evidence**: Documentation elements supporting this code
    - **Reasoning**: How the evidence supports the code selection

    Clinical context improves suggestion accuracy:
    - **time_spent**: Total encounter time in minutes
    - **mdm_complexity**: Medical decision making (straightforward, low, moderate, high)
    - **new_patient**: Whether patient is new (true/false)
    - **setting**: Service setting (office, hospital, emergency)
    - **diagnoses**: Relevant diagnosis codes

    **Important**: CPT codes are owned by the AMA. Code suggestions should be
    verified by qualified medical coders.

    Args:
        request: Procedure description and clinical context.

    Returns:
        CPTSuggestResponse with CER-cited code suggestions.
    """
    import time
    from app.services.cpt_suggester import get_cpt_suggester_service

    start_time = time.perf_counter()

    service = get_cpt_suggester_service()

    result = service.suggest_codes(
        query=request.query,
        clinical_context=request.clinical_context,
        max_suggestions=request.max_suggestions,
    )

    suggestion_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert to response format with CER citations
    suggestions = []
    for s in result.suggestions:
        cer_response = CPTCERCitationResponse(
            claim=s.cer_citation.claim,
            evidence=s.cer_citation.evidence,
            reasoning=s.cer_citation.reasoning,
            strength=s.cer_citation.strength.value,
        )
        doc_checklist = [
            DocumentationChecklistItem(
                element=d.element,
                present=d.present,
                notes=d.notes,
            )
            for d in s.documentation_checklist
        ]
        suggestions.append(
            CPTSuggestionResponse(
                code=s.code,
                description=s.description,
                category=s.category,
                confidence=s.confidence.value,
                cer_citation=cer_response,
                work_rvu=s.work_rvu,
                typical_time_minutes=s.typical_time_minutes,
                suggested_modifiers=s.suggested_modifiers,
                documentation_checklist=doc_checklist,
                supporting_diagnoses=s.supporting_diagnoses,
                alternative_codes=s.alternative_codes,
                coding_notes=s.coding_notes,
            )
        )

    return CPTSuggestResponse(
        query=result.query,
        clinical_context=result.clinical_context,
        suggestions=suggestions,
        total_matches=result.total_matches,
        documentation_gaps=result.documentation_gaps,
        coding_tips=result.coding_tips,
        suggestion_time_ms=round(suggestion_time_ms, 2),
        database_stats=service.get_stats(),
    )


# ============================================================================
# Billing Optimization Endpoint
# ============================================================================


class BillingOptimizationRequest(BaseModel):
    """Request for billing optimization analysis."""

    cpt_codes: list[str] = Field(..., description="CPT codes billed")
    icd10_codes: list[str] = Field(..., description="ICD-10 diagnosis codes")
    modifiers: list[tuple[str, str]] | None = Field(
        None, description="Modifiers as (code, modifier) pairs"
    )
    setting: str | None = Field(None, description="Clinical setting (office, hospital, ed)")
    patient_type: str | None = Field(None, description="new or established")
    time_spent: int | None = Field(None, description="Time spent in minutes")
    mdm_complexity: str | None = Field(
        None, description="MDM complexity (straightforward, low, moderate, high)"
    )
    diagnoses: list[str] | None = Field(None, description="Clinical findings/diagnoses")


class BillingCERResponse(BaseModel):
    """CER citation for billing finding."""

    claim: str = Field(..., description="The billing assertion")
    evidence: list[str] = Field(..., description="Supporting evidence")
    reasoning: str = Field(..., description="Clinical reasoning")
    strength: str = Field(..., description="Confidence level")
    regulatory_basis: list[str] = Field(default_factory=list, description="Regulatory references")


class BillingFindingResponse(BaseModel):
    """Single billing optimization finding."""

    category: str = Field(..., description="Finding category")
    title: str = Field(..., description="Finding title")
    description: str = Field(..., description="Detailed description")
    severity: str = Field(..., description="Severity level")
    current_code: str | None = Field(None, description="Current code if applicable")
    recommended_code: str | None = Field(None, description="Recommended code if applicable")
    revenue_impact: float | None = Field(None, description="Estimated revenue impact")
    action_required: str = Field(..., description="Required action")
    cer_citation: BillingCERResponse = Field(..., description="CER citation")


class BillingOptimizationResponse(BaseModel):
    """Response for billing optimization analysis."""

    findings: list[BillingFindingResponse] = Field(..., description="Optimization findings")
    total_findings: int = Field(..., description="Total number of findings")
    by_category: dict[str, int] = Field(..., description="Findings by category")
    by_severity: dict[str, int] = Field(..., description="Findings by severity")
    estimated_current_rvu: float = Field(..., description="Current RVU estimate")
    estimated_optimized_rvu: float = Field(..., description="Optimized RVU estimate")
    potential_revenue_increase: float = Field(..., description="Potential revenue increase")
    compliance_score: int = Field(..., description="Compliance score 0-100")
    priority_actions: list[str] = Field(..., description="Priority actions to take")
    overall_assessment: str = Field(..., description="Overall assessment summary")
    analysis_time_ms: float = Field(..., description="Analysis time in milliseconds")


@router.post(
    "/clinical/billing-optimize",
    response_model=BillingOptimizationResponse,
    tags=["clinical-decision-support"],
    summary="Analyze billing optimization opportunities",
)
async def analyze_billing_optimization(
    request: BillingOptimizationRequest,
) -> BillingOptimizationResponse:
    """
    Analyze an encounter for billing optimization opportunities.

    Checks for:
    - E/M upcoding opportunities based on time or MDM
    - Missed billable services
    - CCI bundling compliance issues
    - Medical necessity gaps
    - Missing modifiers
    - Documentation gaps

    All findings include CER (Claim-Evidence-Reasoning) citations.
    """
    import time
    from app.services.billing_optimizer import (
        BillingOptimizationService,
        EncounterCodes,
        EncounterContext,
    )

    start_time = time.time()

    service = BillingOptimizationService()

    codes = EncounterCodes(
        cpt_codes=request.cpt_codes,
        icd10_codes=request.icd10_codes,
        modifiers=request.modifiers or [],
    )

    context = EncounterContext(
        setting=request.setting,
        patient_type=request.patient_type,
        time_spent=request.time_spent,
        mdm_complexity=request.mdm_complexity,
        diagnoses=request.diagnoses or [],
    )

    result = service.analyze_encounter(codes, context)

    analysis_time_ms = (time.time() - start_time) * 1000

    findings = []
    for f in result.findings:
        cer_response = BillingCERResponse(
            claim=f.cer_citation.claim,
            evidence=f.cer_citation.evidence,
            reasoning=f.cer_citation.reasoning,
            strength=f.cer_citation.strength.value,
            regulatory_basis=f.cer_citation.regulatory_basis,
        )
        findings.append(
            BillingFindingResponse(
                category=f.category.value,
                title=f.title,
                description=f.description,
                severity=f.severity.value,
                current_code=f.current_code,
                recommended_code=f.recommended_code,
                revenue_impact=f.revenue_impact,
                action_required="; ".join(f.action_items) if f.action_items else "Review and verify coding",
                cer_citation=cer_response,
            )
        )

    return BillingOptimizationResponse(
        findings=findings,
        total_findings=result.total_findings,
        by_category=result.by_category,
        by_severity=result.by_severity,
        estimated_current_rvu=result.estimated_current_rvu,
        estimated_optimized_rvu=result.estimated_optimized_rvu,
        potential_revenue_increase=result.potential_revenue_increase,
        compliance_score=result.compliance_score,
        priority_actions=result.priority_actions,
        overall_assessment=result.overall_assessment,
        analysis_time_ms=round(analysis_time_ms, 2),
    )


# ============================================================================
# Coding Query Generator Endpoints
# ============================================================================


class CodingQueryRequest(BaseModel):
    """Request body for coding query generation."""

    clinical_text: str = Field(
        ...,
        description="Clinical documentation text to analyze",
        min_length=10,
    )
    extracted_mentions: list[dict] | None = Field(
        None,
        description="Pre-extracted NLP mentions (optional)",
    )
    encounter_id: str | None = Field(None, description="Encounter identifier")
    patient_id: str | None = Field(None, description="Patient identifier")
    encounter_type: str | None = Field(
        None,
        description="Type of encounter (inpatient, outpatient, emergency)",
    )


class QueryResponseOptionResponse(BaseModel):
    """A response option for a query."""

    label: str
    value: str
    icd10_code: str | None = None
    cpt_code: str | None = None


class QueryCERResponse(BaseModel):
    """CER citation for a query."""

    claim: str
    evidence: list[str]
    reasoning: str
    strength: str
    regulatory_basis: list[str] = []
    coding_references: list[str] = []


class CodingQueryResponse(BaseModel):
    """A single coding query."""

    query_id: str
    priority: str
    status: str
    question: str
    clinical_context: str
    response_options: list[QueryResponseOptionResponse]
    allows_free_text: bool = True
    gap_category: str
    gap_severity: str
    finding: str
    coding_impacts: list[str] = []
    affected_icd10_codes: list[str] = []
    affected_cpt_codes: list[str] = []
    estimated_revenue_impact: float = 0.0
    quality_measures_affected: list[str] = []
    cer_citation: QueryCERResponse | None = None


class CodingQueryBatchResponse(BaseModel):
    """Response for coding query generation."""

    batch_id: str
    encounter_id: str | None = None
    patient_id: str | None = None
    queries: list[CodingQueryResponse]
    total_queries: int
    by_priority: dict[str, int]
    by_category: dict[str, int]
    total_estimated_revenue_impact: float
    drg_impact_possible: bool
    hcc_impact_possible: bool
    quality_measures_at_risk: list[str]
    documentation_score: int
    generation_time_ms: float


@router.post(
    "/clinical/coding-queries",
    response_model=CodingQueryBatchResponse,
    tags=["clinical-decision-support"],
    summary="Generate coding queries for documentation clarification",
)
async def generate_coding_queries(
    request: CodingQueryRequest,
) -> CodingQueryBatchResponse:
    """
    Generate structured coding queries for Clinical Documentation Improvement (CDI).

    Analyzes clinical documentation to identify:
    - Ambiguous diagnoses needing clarification (diabetes type, HF type)
    - Missing specificity (laterality, acuity, stage)
    - Documentation gaps affecting coding accuracy
    - Quality measure opportunities

    Returns prioritized queries with:
    - CER citations explaining why clarification is needed
    - Response options with associated ICD-10/CPT codes
    - Revenue impact estimates
    - Quality measure implications

    Queries are designed to be sent to providers for documentation improvement.
    """
    import time
    from app.services.coding_query_generator import get_coding_query_generator_service

    start_time = time.time()

    service = get_coding_query_generator_service()

    # Build encounter context
    encounter_context = {
        "encounter_id": request.encounter_id,
        "patient_id": request.patient_id,
        "encounter_type": request.encounter_type or "",
    }

    # Generate queries
    batch = service.generate_queries(
        clinical_text=request.clinical_text,
        extracted_mentions=request.extracted_mentions,
        encounter_context=encounter_context,
    )

    generation_time_ms = (time.time() - start_time) * 1000

    # Convert to response format
    queries = []
    for q in batch.queries:
        # Convert response options
        response_options = []
        for opt in q.response_options:
            response_options.append(
                QueryResponseOptionResponse(
                    label=opt.label,
                    value=opt.value,
                    icd10_code=opt.icd10_code,
                    cpt_code=opt.cpt_code,
                )
            )

        # Convert CER citation
        cer = None
        if q.cer_citation:
            cer = QueryCERResponse(
                claim=q.cer_citation.claim,
                evidence=q.cer_citation.evidence,
                reasoning=q.cer_citation.reasoning,
                strength=q.cer_citation.strength,
                regulatory_basis=q.cer_citation.regulatory_basis,
                coding_references=q.cer_citation.coding_references,
            )

        queries.append(
            CodingQueryResponse(
                query_id=q.query_id,
                priority=q.priority.value,
                status=q.status.value,
                question=q.question,
                clinical_context=q.clinical_context,
                response_options=response_options,
                allows_free_text=q.allows_free_text,
                gap_category=q.gap_category.value,
                gap_severity=q.gap_severity.value,
                finding=q.finding,
                coding_impacts=[i.value for i in q.coding_impacts],
                affected_icd10_codes=q.affected_icd10_codes,
                affected_cpt_codes=q.affected_cpt_codes,
                estimated_revenue_impact=q.estimated_revenue_impact,
                quality_measures_affected=q.quality_measures_affected,
                cer_citation=cer,
            )
        )

    return CodingQueryBatchResponse(
        batch_id=batch.batch_id,
        encounter_id=batch.encounter_id,
        patient_id=batch.patient_id,
        queries=queries,
        total_queries=batch.total_queries,
        by_priority=batch.by_priority,
        by_category=batch.by_category,
        total_estimated_revenue_impact=batch.total_estimated_revenue_impact,
        drg_impact_possible=batch.drg_impact_possible,
        hcc_impact_possible=batch.hcc_impact_possible,
        quality_measures_at_risk=batch.quality_measures_at_risk,
        documentation_score=batch.documentation_score,
        generation_time_ms=round(generation_time_ms, 2),
    )


# ============================================================================
# HCC Revenue Recovery Endpoints
# ============================================================================


class HCCAnalyzeRequest(BaseModel):
    """Request body for HCC revenue recovery analysis."""

    clinical_text: str = Field(
        ...,
        description="Clinical documentation text to analyze",
        min_length=10,
    )
    current_icd10_codes: list[str] = Field(
        default_factory=list,
        description="Currently coded ICD-10 diagnoses for this patient",
    )
    lab_values: list[dict] = Field(
        default_factory=list,
        description="Lab results (name, value, unit, date)",
    )
    patient_id: str | None = Field(None, description="Patient identifier")
    encounter_id: str | None = Field(None, description="Encounter identifier")
    setting: str = Field("community", description="community or institutional")


class HCCEvidenceResponse(BaseModel):
    """Evidence supporting an HCC finding."""

    source_type: str
    source_text: str
    source_date: str | None = None
    confidence: float


class HCCOpportunityResponse(BaseModel):
    """An HCC revenue opportunity."""

    hcc_code: str
    hcc_description: str
    category: str
    gap_type: str
    capture_confidence: str
    raf_value: float
    estimated_revenue: float
    evidence: list[HCCEvidenceResponse]
    supporting_icd10_codes: list[str]
    current_coded_icd10: str | None = None
    recommended_icd10: str | None = None
    documentation_needed: list[str]
    coder_notes: str


class HCCAnalysisResponse(BaseModel):
    """Response for HCC revenue recovery analysis."""

    # Opportunities
    opportunities: list[HCCOpportunityResponse]
    total_opportunities: int

    # Financial summary
    total_raf_opportunity: float
    total_estimated_revenue: float
    high_confidence_revenue: float

    # Breakdown
    by_category: dict[str, int]
    by_gap_type: dict[str, int]
    by_confidence: dict[str, int]

    # Current vs projected state
    current_hccs: list[str]
    current_raf_score: float
    projected_hccs: list[str]
    projected_raf_score: float

    # Actions
    priority_actions: list[str]

    # Metadata
    analysis_date: str
    analysis_time_ms: float


@router.post(
    "/clinical/hcc-analyze",
    response_model=HCCAnalysisResponse,
    tags=["clinical-decision-support"],
    summary="Analyze for HCC revenue recovery opportunities",
)
async def analyze_hcc_opportunities(
    request: HCCAnalyzeRequest,
) -> HCCAnalysisResponse:
    """
    Analyze clinical documentation for HCC (Hierarchical Condition Category)
    revenue recovery opportunities for Medicare Advantage risk adjustment.

    This endpoint:
    - Maps current ICD-10 codes to HCC categories
    - Scans documentation for undocumented/underspecified conditions
    - Identifies HCC gaps (documented but not coded, needs specificity, suspect)
    - Calculates RAF (Risk Adjustment Factor) impact
    - Estimates annual revenue opportunity
    - Generates prioritized action items for coders

    HCC Model V28 (2024) is used for RAF calculations.

    **Use cases:**
    - Pre-visit chart review for Annual Wellness Visits
    - Retrospective coding review
    - Risk adjustment optimization
    - Revenue cycle improvement
    """
    from app.services.hcc_analyzer import get_hcc_analyzer_service

    service = get_hcc_analyzer_service()

    patient_context = {
        "patient_id": request.patient_id,
        "encounter_id": request.encounter_id,
        "setting": request.setting,
    }

    result = service.analyze_patient(
        clinical_text=request.clinical_text,
        current_icd10_codes=request.current_icd10_codes,
        lab_values=request.lab_values,
        patient_context=patient_context,
    )

    # Convert opportunities to response format
    opportunities = []
    for opp in result.opportunities:
        evidence = [
            HCCEvidenceResponse(
                source_type=e.source_type,
                source_text=e.source_text,
                source_date=e.source_date,
                confidence=e.confidence,
            )
            for e in opp.evidence
        ]
        opportunities.append(
            HCCOpportunityResponse(
                hcc_code=opp.hcc_code,
                hcc_description=opp.hcc_description,
                category=opp.category.value,
                gap_type=opp.gap_type.value,
                capture_confidence=opp.capture_confidence.value,
                raf_value=opp.raf_value,
                estimated_revenue=opp.estimated_revenue,
                evidence=evidence,
                supporting_icd10_codes=opp.supporting_icd10_codes,
                current_coded_icd10=opp.current_coded_icd10,
                recommended_icd10=opp.recommended_icd10,
                documentation_needed=opp.documentation_needed,
                coder_notes=opp.coder_notes,
            )
        )

    return HCCAnalysisResponse(
        opportunities=opportunities,
        total_opportunities=result.total_opportunities,
        total_raf_opportunity=result.total_raf_opportunity,
        total_estimated_revenue=result.total_estimated_revenue,
        high_confidence_revenue=result.high_confidence_revenue,
        by_category=result.by_category,
        by_gap_type=result.by_gap_type,
        by_confidence=result.by_confidence,
        current_hccs=result.current_hccs,
        current_raf_score=result.current_raf_score,
        projected_hccs=result.projected_hccs,
        projected_raf_score=result.projected_raf_score,
        priority_actions=result.priority_actions,
        analysis_date=result.analysis_date,
        analysis_time_ms=result.analysis_time_ms,
    )


# ============================================================================
# Clinical Summarization Endpoints
# ============================================================================


class PatientFactRequest(BaseModel):
    """A clinical fact for summarization."""

    fact_type: str = Field(..., description="Type: condition, drug, measurement, procedure, observation")
    label: str = Field(..., description="Fact label/name")
    value: str | None = Field(None, description="Value if applicable")
    unit: str | None = Field(None, description="Unit if applicable")
    assertion: str = Field("present", description="present, absent, possible")
    temporality: str = Field("current", description="current, historical, future")
    icd10_code: str | None = Field(None, description="ICD-10 code")
    omop_concept_id: int | None = Field(None, description="OMOP concept ID")
    confidence: float = Field(1.0, description="Confidence score 0-1")


class SummarizeRequest(BaseModel):
    """Request for clinical summarization."""

    patient_id: str = Field(..., description="Patient identifier")
    facts: list[PatientFactRequest] = Field(..., description="Clinical facts to summarize")
    summary_type: str = Field("standard", description="brief, standard, detailed, discharge, handoff")


class SectionSummaryResponse(BaseModel):
    """A section summary."""

    title: str
    content: str
    bullet_points: list[str] = []
    key_findings: list[str] = []


class ClinicalSummaryResponse(BaseModel):
    """Clinical summary response."""

    patient_id: str
    summary_type: str
    one_liner: str
    sections: list[SectionSummaryResponse]
    problem_count: int
    medication_count: int
    critical_findings: list[str]
    confidence_score: float
    generated_at: str


@router.post(
    "/clinical/summarize",
    response_model=ClinicalSummaryResponse,
    tags=["clinical-decision-support"],
    summary="Generate clinical summary",
)
async def generate_clinical_summary(
    request: SummarizeRequest,
) -> ClinicalSummaryResponse:
    """Generate a clinical summary from patient facts."""
    from app.services.clinical_summarizer import (
        ClinicalSummarizerService,
        PatientFact,
        SummaryType,
    )

    service = ClinicalSummarizerService()

    facts = [
        PatientFact(
            fact_type=f.fact_type,
            label=f.label,
            value=f.value,
            unit=f.unit,
            assertion=f.assertion,
            temporality=f.temporality,
            icd10_code=f.icd10_code,
            omop_concept_id=f.omop_concept_id,
            confidence=f.confidence,
        )
        for f in request.facts
    ]

    summary_type_map = {
        "brief": SummaryType.BRIEF,
        "standard": SummaryType.STANDARD,
        "detailed": SummaryType.DETAILED,
        "discharge": SummaryType.DISCHARGE,
        "handoff": SummaryType.HANDOFF,
    }

    result = service.summarize(
        request.patient_id,
        facts,
        summary_type_map.get(request.summary_type, SummaryType.STANDARD),
    )

    return ClinicalSummaryResponse(
        patient_id=result.patient_id,
        summary_type=result.summary_type.value,
        one_liner=result.one_liner,
        sections=[
            SectionSummaryResponse(
                title=s.title,
                content=s.content,
                bullet_points=s.bullet_points,
                key_findings=s.key_findings,
            )
            for s in result.sections
        ],
        problem_count=result.active_problem_count,
        medication_count=len(result.medications),
        critical_findings=result.critical_findings,
        confidence_score=result.confidence_score,
        generated_at=result.generated_at,
    )
