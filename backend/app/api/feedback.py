"""Active Learning Feedback API endpoints.

Provides REST endpoints for human-in-the-loop clinical NLP improvement:
- Record clinician corrections
- Review uncertain samples
- Generate training datasets
- Track improvement metrics
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.active_learning_service import (
    ActiveLearningService,
    CorrectionPriority,
    CorrectionRecord,
    CorrectionType,
    ImprovementMetrics,
    ReviewStatus,
    TrainingDataset,
    UncertaintySample,
    UncertaintyType,
    get_active_learning_service,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CorrectionRequest(BaseModel):
    """Request model for recording a correction."""

    correction_type: CorrectionType = Field(..., description="Type of correction")
    original_text: str = Field(..., description="Original extracted text")
    original_value: str | None = Field(None, description="Original prediction value")
    corrected_value: str | None = Field(None, description="Corrected value")
    document_id: str | None = Field(None, description="Source document ID")
    patient_id: str | None = Field(None, description="Patient ID")
    mention_id: str | None = Field(None, description="Mention ID")
    fact_id: str | None = Field(None, description="Clinical fact ID")
    original_start: int = Field(0, description="Original start offset")
    original_end: int = Field(0, description="Original end offset")
    original_confidence: float | None = Field(None, description="Original confidence score")
    corrected_text: str | None = Field(None, description="Corrected text span")
    corrected_start: int | None = Field(None, description="Corrected start offset")
    corrected_end: int | None = Field(None, description="Corrected end offset")
    context_before: str = Field("", description="Text before the mention")
    context_after: str = Field("", description="Text after the mention")
    section: str | None = Field(None, description="Clinical section")
    note_type: str | None = Field(None, description="Type of clinical note")
    corrected_by: str | None = Field(None, description="User ID of corrector")
    notes: str | None = Field(None, description="Additional notes")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    domain: str | None = Field(None, description="Clinical domain")

    model_config = {"json_schema_extra": {"example": {
        "correction_type": "assertion_wrong",
        "original_text": "chest pain",
        "original_value": "absent",
        "corrected_value": "present",
        "document_id": "doc_123",
        "context_before": "Patient denies ",
        "context_after": " but reports discomfort.",
        "section": "HPI",
        "corrected_by": "dr_smith",
    }}}


class CorrectionResponse(BaseModel):
    """Response model for a correction record."""

    id: str
    created_at: datetime
    correction_type: str
    priority: str
    document_id: str | None
    patient_id: str | None
    mention_id: str | None
    original_text: str
    original_value: str | None
    corrected_value: str | None
    context_before: str
    context_after: str
    section: str | None
    corrected_by: str | None
    notes: str | None
    tags: list[str]
    included_in_training: bool

    @classmethod
    def from_record(cls, record: CorrectionRecord) -> "CorrectionResponse":
        """Create response from CorrectionRecord."""
        return cls(
            id=record.id,
            created_at=record.created_at,
            correction_type=record.correction_type.value,
            priority=record.priority.value,
            document_id=record.document_id,
            patient_id=record.patient_id,
            mention_id=record.mention_id,
            original_text=record.original_text,
            original_value=record.original_value,
            corrected_value=record.corrected_value,
            context_before=record.context_before,
            context_after=record.context_after,
            section=record.section,
            corrected_by=record.corrected_by,
            notes=record.notes,
            tags=record.tags,
            included_in_training=record.included_in_training,
        )


class UncertaintySampleRequest(BaseModel):
    """Request model for flagging an uncertain sample."""

    text: str = Field(..., description="Extracted text")
    prediction_probabilities: dict[str, float] = Field(
        ..., description="Probabilities for each label"
    )
    predicted_label: str | None = Field(None, description="Predicted label")
    document_id: str | None = Field(None, description="Source document ID")
    patient_id: str | None = Field(None, description="Patient ID")
    mention_id: str | None = Field(None, description="Mention ID")
    start_offset: int = Field(0, description="Start offset")
    end_offset: int = Field(0, description="End offset")
    context_before: str = Field("", description="Text before mention")
    context_after: str = Field("", description="Text after mention")
    section: str | None = Field(None, description="Clinical section")


class UncertaintySampleResponse(BaseModel):
    """Response model for an uncertainty sample."""

    id: str
    created_at: datetime
    document_id: str | None
    patient_id: str | None
    text: str
    start_offset: int
    end_offset: int
    context_before: str
    context_after: str
    section: str | None
    predicted_label: str | None
    predicted_confidence: float
    prediction_probabilities: dict[str, float]
    entropy: float
    margin: float
    least_confident: float
    uncertainty_score: float
    review_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_result: str | None
    review_notes: str | None

    @classmethod
    def from_sample(cls, sample: UncertaintySample) -> "UncertaintySampleResponse":
        """Create response from UncertaintySample."""
        return cls(
            id=sample.id,
            created_at=sample.created_at,
            document_id=sample.document_id,
            patient_id=sample.patient_id,
            text=sample.text,
            start_offset=sample.start_offset,
            end_offset=sample.end_offset,
            context_before=sample.context_before,
            context_after=sample.context_after,
            section=sample.section,
            predicted_label=sample.predicted_label,
            predicted_confidence=sample.predicted_confidence,
            prediction_probabilities=sample.prediction_probabilities,
            entropy=sample.entropy,
            margin=sample.margin,
            least_confident=sample.least_confident,
            uncertainty_score=sample.uncertainty_score,
            review_status=sample.review_status.value,
            reviewed_by=sample.reviewed_by,
            reviewed_at=sample.reviewed_at,
            review_result=sample.review_result,
            review_notes=sample.review_notes,
        )


class ReviewRequest(BaseModel):
    """Request model for submitting a review."""

    reviewed_by: str = Field(..., description="User ID of reviewer")
    review_result: str | None = Field(None, description="Corrected label if different")
    review_notes: str | None = Field(None, description="Review notes")
    approved: bool = Field(True, description="Whether prediction was correct")


class GenerateDatasetRequest(BaseModel):
    """Request model for generating a training dataset."""

    name: str = Field(..., description="Dataset name")
    description: str = Field("", description="Dataset description")
    correction_types: list[CorrectionType] | None = Field(
        None, description="Filter by correction types"
    )
    min_priority: CorrectionPriority = Field(
        CorrectionPriority.LOW, description="Minimum priority to include"
    )
    include_reviewed_samples: bool = Field(
        True, description="Include reviewed uncertain samples"
    )
    train_split: float = Field(0.8, ge=0.0, le=1.0, description="Training split fraction")
    validation_split: float = Field(0.1, ge=0.0, le=1.0, description="Validation split")
    test_split: float = Field(0.1, ge=0.0, le=1.0, description="Test split fraction")
    output_format: str = Field("jsonl", description="Output format")


class TrainingDatasetResponse(BaseModel):
    """Response model for a training dataset."""

    id: str
    created_at: datetime
    name: str
    description: str
    task_type: str
    total_examples: int
    train_examples: int
    validation_examples: int
    test_examples: int
    correction_ids: list[str]
    sample_ids: list[str]
    output_format: str
    output_path: str | None
    status: str
    error_message: str | None

    @classmethod
    def from_dataset(cls, dataset: TrainingDataset) -> "TrainingDatasetResponse":
        """Create response from TrainingDataset."""
        return cls(
            id=dataset.id,
            created_at=dataset.created_at,
            name=dataset.name,
            description=dataset.description,
            task_type=dataset.task_type,
            total_examples=dataset.total_examples,
            train_examples=dataset.train_examples,
            validation_examples=dataset.validation_examples,
            test_examples=dataset.test_examples,
            correction_ids=dataset.correction_ids,
            sample_ids=dataset.sample_ids,
            output_format=dataset.output_format,
            output_path=dataset.output_path,
            status=dataset.status,
            error_message=dataset.error_message,
        )


class ImprovementMetricsResponse(BaseModel):
    """Response model for improvement metrics."""

    calculated_at: datetime
    total_corrections: int
    corrections_by_type: dict[str, int]
    corrections_by_priority: dict[str, int]
    corrections_by_domain: dict[str, int]
    corrections_this_week: int
    corrections_last_week: int
    correction_trend: float
    pending_reviews: int
    avg_review_time_hours: float
    review_agreement_rate: float
    training_datasets_created: int
    examples_used_for_training: int
    estimated_accuracy_improvement: float
    top_error_categories: list[dict[str, Any]]

    @classmethod
    def from_metrics(cls, metrics: ImprovementMetrics) -> "ImprovementMetricsResponse":
        """Create response from ImprovementMetrics."""
        return cls(
            calculated_at=metrics.calculated_at,
            total_corrections=metrics.total_corrections,
            corrections_by_type=metrics.corrections_by_type,
            corrections_by_priority=metrics.corrections_by_priority,
            corrections_by_domain=metrics.corrections_by_domain,
            corrections_this_week=metrics.corrections_this_week,
            corrections_last_week=metrics.corrections_last_week,
            correction_trend=metrics.correction_trend,
            pending_reviews=metrics.pending_reviews,
            avg_review_time_hours=metrics.avg_review_time_hours,
            review_agreement_rate=metrics.review_agreement_rate,
            training_datasets_created=metrics.training_datasets_created,
            examples_used_for_training=metrics.examples_used_for_training,
            estimated_accuracy_improvement=metrics.estimated_accuracy_improvement,
            top_error_categories=metrics.top_error_categories,
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/corrections",
    response_model=CorrectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a correction",
    description="Record a clinician correction for NLP improvement.",
)
def create_correction(request: CorrectionRequest) -> CorrectionResponse:
    """Record a clinician correction."""
    service = get_active_learning_service()

    correction = service.record_correction(
        correction_type=request.correction_type,
        original_text=request.original_text,
        original_value=request.original_value,
        corrected_value=request.corrected_value,
        document_id=request.document_id,
        patient_id=request.patient_id,
        mention_id=request.mention_id,
        fact_id=request.fact_id,
        original_start=request.original_start,
        original_end=request.original_end,
        original_confidence=request.original_confidence,
        corrected_text=request.corrected_text,
        corrected_start=request.corrected_start,
        corrected_end=request.corrected_end,
        context_before=request.context_before,
        context_after=request.context_after,
        section=request.section,
        note_type=request.note_type,
        corrected_by=request.corrected_by,
        notes=request.notes,
        tags=request.tags,
        domain=request.domain,
    )

    return CorrectionResponse.from_record(correction)


@router.get(
    "/corrections",
    response_model=list[CorrectionResponse],
    summary="List corrections",
    description="Get a list of recorded corrections with optional filters.",
)
def list_corrections(
    correction_type: CorrectionType | None = Query(None, description="Filter by type"),
    priority: CorrectionPriority | None = Query(None, description="Filter by priority"),
    document_id: str | None = Query(None, description="Filter by document"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
) -> list[CorrectionResponse]:
    """List recorded corrections."""
    service = get_active_learning_service()

    corrections = service.get_corrections(
        correction_type=correction_type,
        priority=priority,
        document_id=document_id,
        limit=limit,
    )

    return [CorrectionResponse.from_record(c) for c in corrections]


@router.get(
    "/corrections/{correction_id}",
    response_model=CorrectionResponse,
    summary="Get correction",
    description="Get a specific correction by ID.",
)
def get_correction(correction_id: str) -> CorrectionResponse:
    """Get a correction by ID."""
    service = get_active_learning_service()

    correction = service.get_correction(correction_id)
    if correction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Correction {correction_id} not found",
        )

    return CorrectionResponse.from_record(correction)


@router.post(
    "/uncertain-samples",
    response_model=UncertaintySampleResponse | None,
    status_code=status.HTTP_201_CREATED,
    summary="Flag uncertain sample",
    description="Flag a sample for uncertainty review if it exceeds threshold.",
)
def flag_uncertain_sample(
    request: UncertaintySampleRequest,
) -> UncertaintySampleResponse | None:
    """Flag an uncertain sample for review."""
    service = get_active_learning_service()

    sample = service.flag_uncertain_sample(
        text=request.text,
        prediction_probabilities=request.prediction_probabilities,
        predicted_label=request.predicted_label,
        document_id=request.document_id,
        patient_id=request.patient_id,
        mention_id=request.mention_id,
        start_offset=request.start_offset,
        end_offset=request.end_offset,
        context_before=request.context_before,
        context_after=request.context_after,
        section=request.section,
    )

    if sample is None:
        return None

    return UncertaintySampleResponse.from_sample(sample)


@router.get(
    "/review-queue",
    response_model=list[UncertaintySampleResponse],
    summary="Get review queue",
    description="Get samples needing expert review, prioritized by uncertainty.",
)
def get_review_queue(
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    uncertainty_type: UncertaintyType = Query(
        UncertaintyType.ENTROPY, description="Sort by uncertainty type"
    ),
    status_filter: ReviewStatus = Query(
        ReviewStatus.PENDING, alias="status", description="Filter by review status"
    ),
    section: str | None = Query(None, description="Filter by clinical section"),
) -> list[UncertaintySampleResponse]:
    """Get samples for expert review."""
    service = get_active_learning_service()

    samples = service.get_samples_for_review(
        limit=limit,
        uncertainty_type=uncertainty_type,
        status=status_filter,
        section_filter=section,
    )

    return [UncertaintySampleResponse.from_sample(s) for s in samples]


@router.get(
    "/review-queue/{sample_id}",
    response_model=UncertaintySampleResponse,
    summary="Get sample",
    description="Get a specific uncertain sample by ID.",
)
def get_sample(sample_id: str) -> UncertaintySampleResponse:
    """Get an uncertain sample by ID."""
    service = get_active_learning_service()

    sample = service.get_sample(sample_id)
    if sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found",
        )

    return UncertaintySampleResponse.from_sample(sample)


@router.post(
    "/review-queue/{sample_id}/review",
    response_model=UncertaintySampleResponse,
    summary="Submit review",
    description="Submit a review for an uncertain sample.",
)
def submit_review(sample_id: str, request: ReviewRequest) -> UncertaintySampleResponse:
    """Submit a review for a sample."""
    service = get_active_learning_service()

    sample = service.submit_review(
        sample_id=sample_id,
        reviewed_by=request.reviewed_by,
        review_result=request.review_result,
        review_notes=request.review_notes,
        approved=request.approved,
    )

    if sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found",
        )

    return UncertaintySampleResponse.from_sample(sample)


@router.post(
    "/generate-dataset",
    response_model=TrainingDatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate training dataset",
    description="Generate a training dataset from corrections and reviewed samples.",
)
def generate_dataset(request: GenerateDatasetRequest) -> TrainingDatasetResponse:
    """Generate a training dataset."""
    # Validate splits sum to 1.0
    total_split = request.train_split + request.validation_split + request.test_split
    if abs(total_split - 1.0) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Splits must sum to 1.0, got {total_split}",
        )

    service = get_active_learning_service()

    dataset = service.generate_training_dataset(
        name=request.name,
        description=request.description,
        correction_types=request.correction_types,
        min_priority=request.min_priority,
        include_reviewed_samples=request.include_reviewed_samples,
        train_split=request.train_split,
        validation_split=request.validation_split,
        test_split=request.test_split,
        output_format=request.output_format,
    )

    return TrainingDatasetResponse.from_dataset(dataset)


@router.get(
    "/datasets",
    response_model=list[TrainingDatasetResponse],
    summary="List datasets",
    description="List all generated training datasets.",
)
def list_datasets() -> list[TrainingDatasetResponse]:
    """List all training datasets."""
    service = get_active_learning_service()

    datasets = service.list_datasets()
    return [TrainingDatasetResponse.from_dataset(d) for d in datasets]


@router.get(
    "/datasets/{dataset_id}",
    response_model=TrainingDatasetResponse,
    summary="Get dataset",
    description="Get a specific training dataset by ID.",
)
def get_dataset(dataset_id: str) -> TrainingDatasetResponse:
    """Get a training dataset by ID."""
    service = get_active_learning_service()

    dataset = service.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )

    return TrainingDatasetResponse.from_dataset(dataset)


@router.get(
    "/metrics",
    response_model=ImprovementMetricsResponse,
    summary="Get improvement metrics",
    description="Get metrics tracking model improvement from feedback.",
)
def get_metrics() -> ImprovementMetricsResponse:
    """Get improvement metrics."""
    service = get_active_learning_service()

    metrics = service.get_improvement_metrics()
    return ImprovementMetricsResponse.from_metrics(metrics)
