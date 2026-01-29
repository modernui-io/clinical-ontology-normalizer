"""Active Learning Feedback Service for Clinical NLP.

This module provides human-in-the-loop learning capabilities:
- Record clinician corrections for continuous improvement
- Flag uncertain samples for expert review
- Uncertainty sampling for efficient labeling
- Training dataset generation from corrections
- Improvement metrics tracking

Key Features:
- Uncertainty quantification (entropy, margin, disagreement)
- Priority-based review queues (safety-critical items first)
- Integration with LLMFineTuningService for model updates
- Correction context preservation for analysis

References:
- Settles (2009) - Active Learning Literature Survey
- Khetan et al. (2017) - Learning From Noisy Singly-labeled Data
- Monarch (2021) - Human-in-the-Loop Machine Learning
"""

import hashlib
import json
import logging
import math
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class CorrectionType(str, Enum):
    """Types of corrections that can be recorded."""

    # Entity-level corrections
    ENTITY_MISSED = "entity_missed"  # NLP missed an entity that should be extracted
    ENTITY_WRONG = "entity_wrong"  # NLP extracted wrong text span
    ENTITY_FALSE_POSITIVE = "entity_false_positive"  # NLP extracted something that isn't an entity

    # Attribute corrections
    ASSERTION_WRONG = "assertion_wrong"  # Wrong assertion (present/absent/possible)
    TEMPORALITY_WRONG = "temporality_wrong"  # Wrong temporality (current/past/future)
    EXPERIENCER_WRONG = "experiencer_wrong"  # Wrong experiencer (patient/family/other)

    # Mapping corrections
    MAPPING_WRONG = "mapping_wrong"  # Wrong OMOP concept mapping
    DOMAIN_WRONG = "domain_wrong"  # Wrong domain classification

    # Relationship corrections
    RELATION_MISSED = "relation_missed"  # Missed a relationship
    RELATION_WRONG = "relation_wrong"  # Wrong relationship type
    RELATION_FALSE_POSITIVE = "relation_false_positive"  # Incorrect relationship

    # Document-level corrections
    SECTION_WRONG = "section_wrong"  # Wrong section detection
    DOCUMENT_TYPE_WRONG = "document_type_wrong"  # Wrong document classification

    # Phenotype corrections
    PHENOTYPE_WRONG = "phenotype_wrong"  # Wrong phenotype status

    # Other
    OTHER = "other"  # Catch-all for other correction types


class CorrectionPriority(str, Enum):
    """Priority levels for corrections based on clinical impact."""

    CRITICAL = "critical"  # Safety-critical (e.g., drug allergy missed)
    HIGH = "high"  # Clinically significant errors
    MEDIUM = "medium"  # Moderate impact
    LOW = "low"  # Minor errors, cosmetic issues

    @classmethod
    def calculate_priority(
        cls,
        correction_type: CorrectionType,
        is_negation_related: bool = False,
        domain: str | None = None,
    ) -> "CorrectionPriority":
        """Calculate priority based on correction characteristics.

        Args:
            correction_type: The type of correction.
            is_negation_related: Whether the error involves negation.
            domain: The clinical domain (Drug, Condition, etc.).

        Returns:
            Calculated priority level.
        """
        # Negation errors are always high priority (can flip meaning)
        if is_negation_related:
            return cls.CRITICAL

        # Drug-related errors are critical (safety)
        if domain and domain.lower() in ("drug", "medication", "ingredient"):
            if correction_type in (
                CorrectionType.ENTITY_MISSED,
                CorrectionType.ASSERTION_WRONG,
                CorrectionType.MAPPING_WRONG,
            ):
                return cls.CRITICAL
            return cls.HIGH

        # Entity-level errors
        if correction_type in (CorrectionType.ENTITY_MISSED, CorrectionType.ENTITY_FALSE_POSITIVE):
            return cls.HIGH
        if correction_type == CorrectionType.ENTITY_WRONG:
            return cls.MEDIUM

        # Assertion/attribute errors
        if correction_type == CorrectionType.ASSERTION_WRONG:
            return cls.HIGH
        if correction_type in (CorrectionType.TEMPORALITY_WRONG, CorrectionType.EXPERIENCER_WRONG):
            return cls.MEDIUM

        # Mapping errors
        if correction_type == CorrectionType.MAPPING_WRONG:
            return cls.MEDIUM

        # Section/document errors
        if correction_type in (CorrectionType.SECTION_WRONG, CorrectionType.DOCUMENT_TYPE_WRONG):
            return cls.LOW

        return cls.MEDIUM


class ReviewStatus(str, Enum):
    """Status of a sample in the review queue."""

    PENDING = "pending"  # Waiting for review
    IN_PROGRESS = "in_progress"  # Currently being reviewed
    APPROVED = "approved"  # Reviewed and approved
    REJECTED = "rejected"  # Reviewed and rejected
    DEFERRED = "deferred"  # Deferred for later review


class UncertaintyType(str, Enum):
    """Types of uncertainty measures."""

    ENTROPY = "entropy"  # Shannon entropy of predictions
    MARGIN = "margin"  # Difference between top two predictions
    LEAST_CONFIDENT = "least_confident"  # 1 - max probability
    DISAGREEMENT = "disagreement"  # Model disagreement (ensemble)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CorrectionRecord:
    """A record of a clinician correction.

    Preserves full context for analysis and training data generation.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # What was corrected
    correction_type: CorrectionType = CorrectionType.OTHER
    priority: CorrectionPriority = CorrectionPriority.MEDIUM

    # Source context
    document_id: str | None = None
    patient_id: str | None = None
    mention_id: str | None = None
    fact_id: str | None = None

    # Original extraction
    original_text: str = ""
    original_start: int = 0
    original_end: int = 0
    original_value: str | None = None  # Original assertion, concept, etc.
    original_confidence: float | None = None

    # Correction
    corrected_value: str | None = None  # Corrected assertion, concept, etc.
    corrected_text: str | None = None  # For span corrections
    corrected_start: int | None = None
    corrected_end: int | None = None

    # Context for training
    context_before: str = ""  # Text before the mention
    context_after: str = ""  # Text after the mention
    section: str | None = None
    note_type: str | None = None

    # Metadata
    corrected_by: str | None = None  # User ID
    notes: str | None = None
    tags: list[str] = field(default_factory=list)

    # Training data status
    included_in_training: bool = False
    training_dataset_id: str | None = None

    def to_training_example(self) -> dict[str, Any]:
        """Convert to a training example format.

        Returns:
            Dictionary suitable for model training.
        """
        return {
            "id": self.id,
            "text": f"{self.context_before}{self.original_text}{self.context_after}",
            "entities": [{
                "start": len(self.context_before),
                "end": len(self.context_before) + len(self.original_text),
                "label": self.corrected_value or self.original_value,
            }] if self.correction_type in (
                CorrectionType.ENTITY_MISSED,
                CorrectionType.ENTITY_WRONG,
                CorrectionType.ASSERTION_WRONG,
            ) else [],
            "correction_type": self.correction_type.value,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "section": self.section,
            "metadata": {
                "document_id": self.document_id,
                "patient_id": self.patient_id,
                "note_type": self.note_type,
            },
        }


@dataclass
class UncertaintySample:
    """A sample flagged for uncertainty review.

    Uses uncertainty sampling metrics to prioritize expert review.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Source
    document_id: str | None = None
    patient_id: str | None = None
    mention_id: str | None = None

    # Text and context
    text: str = ""
    start_offset: int = 0
    end_offset: int = 0
    context_before: str = ""
    context_after: str = ""
    section: str | None = None

    # Predictions and uncertainty
    predicted_label: str | None = None
    predicted_confidence: float = 0.0
    prediction_probabilities: dict[str, float] = field(default_factory=dict)

    # Uncertainty metrics
    entropy: float = 0.0  # Higher = more uncertain
    margin: float = 1.0  # Lower = more uncertain (close predictions)
    least_confident: float = 0.0  # Higher = more uncertain

    # Combined uncertainty score (weighted average)
    uncertainty_score: float = 0.0

    # Review tracking
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_result: str | None = None  # The corrected label, if any
    review_notes: str | None = None

    @classmethod
    def calculate_entropy(cls, probabilities: dict[str, float]) -> float:
        """Calculate Shannon entropy from probability distribution.

        Args:
            probabilities: Dictionary of label -> probability.

        Returns:
            Entropy value (higher = more uncertain).
        """
        if not probabilities:
            return 0.0

        entropy = 0.0
        for p in probabilities.values():
            if p > 0:
                entropy -= p * math.log2(p)

        # Normalize by max entropy (uniform distribution)
        max_entropy = math.log2(len(probabilities)) if len(probabilities) > 1 else 1.0
        return entropy / max_entropy if max_entropy > 0 else 0.0

    @classmethod
    def calculate_margin(cls, probabilities: dict[str, float]) -> float:
        """Calculate margin between top two predictions.

        Args:
            probabilities: Dictionary of label -> probability.

        Returns:
            Margin value (lower = more uncertain).
        """
        if len(probabilities) < 2:
            return 1.0

        sorted_probs = sorted(probabilities.values(), reverse=True)
        return sorted_probs[0] - sorted_probs[1]

    @classmethod
    def calculate_least_confident(cls, probabilities: dict[str, float]) -> float:
        """Calculate least confidence score.

        Args:
            probabilities: Dictionary of label -> probability.

        Returns:
            Least confidence value (higher = more uncertain).
        """
        if not probabilities:
            return 1.0

        max_prob = max(probabilities.values())
        return 1.0 - max_prob

    @classmethod
    def calculate_uncertainty_score(
        cls,
        probabilities: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> tuple[float, float, float, float]:
        """Calculate combined uncertainty score.

        Args:
            probabilities: Dictionary of label -> probability.
            weights: Optional weights for each metric.

        Returns:
            Tuple of (uncertainty_score, entropy, margin, least_confident).
        """
        if weights is None:
            weights = {"entropy": 0.4, "margin": 0.3, "least_confident": 0.3}

        entropy = cls.calculate_entropy(probabilities)
        margin = cls.calculate_margin(probabilities)
        least_confident = cls.calculate_least_confident(probabilities)

        # Invert margin so higher = more uncertain
        inverted_margin = 1.0 - margin

        # Weighted combination
        uncertainty = (
            weights.get("entropy", 0.4) * entropy
            + weights.get("margin", 0.3) * inverted_margin
            + weights.get("least_confident", 0.3) * least_confident
        )

        return uncertainty, entropy, margin, least_confident


@dataclass
class TrainingDataset:
    """A generated training dataset from corrections."""

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    name: str = ""
    description: str = ""
    task_type: str = ""  # NER, classification, etc.

    # Statistics
    total_examples: int = 0
    train_examples: int = 0
    validation_examples: int = 0
    test_examples: int = 0

    # Source
    correction_ids: list[str] = field(default_factory=list)
    sample_ids: list[str] = field(default_factory=list)

    # Output
    output_format: str = "jsonl"
    output_path: str | None = None

    # Status
    status: str = "created"  # created, processing, ready, error
    error_message: str | None = None


@dataclass
class ImprovementMetrics:
    """Metrics tracking model improvement over time."""

    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Correction statistics
    total_corrections: int = 0
    corrections_by_type: dict[str, int] = field(default_factory=dict)
    corrections_by_priority: dict[str, int] = field(default_factory=dict)
    corrections_by_domain: dict[str, int] = field(default_factory=dict)

    # Trend analysis
    corrections_this_week: int = 0
    corrections_last_week: int = 0
    correction_trend: float = 0.0  # Positive = increasing, negative = decreasing

    # Review queue statistics
    pending_reviews: int = 0
    avg_review_time_hours: float = 0.0
    review_agreement_rate: float = 0.0  # Agreement between model and reviewer

    # Training impact
    training_datasets_created: int = 0
    examples_used_for_training: int = 0

    # Model improvement estimates
    estimated_accuracy_improvement: float = 0.0
    top_error_categories: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Active Learning Service
# =============================================================================


class ActiveLearningService:
    """Service for active learning and human feedback collection.

    Manages the feedback loop between clinical NLP and domain experts:
    1. Record corrections from clinicians
    2. Flag uncertain samples for review
    3. Generate training datasets from feedback
    4. Track improvement metrics

    Usage:
        service = ActiveLearningService()

        # Record a correction
        correction = service.record_correction(
            document_id="doc_123",
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="chest pain",
            original_value="absent",
            corrected_value="present",
            context_before="Patient denies ",
            context_after=" but reports discomfort.",
        )

        # Flag uncertain sample
        sample = service.flag_uncertain_sample(
            document_id="doc_123",
            text="mild discomfort",
            prediction_probabilities={"present": 0.45, "absent": 0.35, "possible": 0.20},
        )

        # Get samples for review
        samples = service.get_samples_for_review(limit=10)

        # Generate training dataset
        dataset = service.generate_training_dataset(
            name="negation_corrections_v1",
            correction_types=[CorrectionType.ASSERTION_WRONG],
        )
    """

    def __init__(self) -> None:
        """Initialize the active learning service."""
        self._corrections: dict[str, CorrectionRecord] = {}
        self._uncertain_samples: dict[str, UncertaintySample] = {}
        self._datasets: dict[str, TrainingDataset] = {}
        self._lock = threading.Lock()

        # Uncertainty thresholds
        self._uncertainty_threshold = 0.5  # Flag samples above this
        self._high_uncertainty_threshold = 0.7  # Prioritize these

        logger.info("ActiveLearningService initialized")

    def record_correction(
        self,
        correction_type: CorrectionType,
        original_text: str,
        original_value: str | None = None,
        corrected_value: str | None = None,
        document_id: str | None = None,
        patient_id: str | None = None,
        mention_id: str | None = None,
        fact_id: str | None = None,
        original_start: int = 0,
        original_end: int = 0,
        original_confidence: float | None = None,
        corrected_text: str | None = None,
        corrected_start: int | None = None,
        corrected_end: int | None = None,
        context_before: str = "",
        context_after: str = "",
        section: str | None = None,
        note_type: str | None = None,
        corrected_by: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        domain: str | None = None,
    ) -> CorrectionRecord:
        """Record a clinician correction.

        Args:
            correction_type: Type of correction being made.
            original_text: The original extracted text.
            original_value: The original prediction (assertion, concept, etc.).
            corrected_value: The correct value.
            document_id: Source document ID.
            patient_id: Patient ID (for PHI tracking).
            mention_id: ID of the mention being corrected.
            fact_id: ID of the clinical fact.
            original_start: Start offset of original extraction.
            original_end: End offset of original extraction.
            original_confidence: Confidence of original prediction.
            corrected_text: Corrected text span (if different).
            corrected_start: Corrected start offset.
            corrected_end: Corrected end offset.
            context_before: Text before the mention.
            context_after: Text after the mention.
            section: Clinical section.
            note_type: Type of clinical note.
            corrected_by: User ID of corrector.
            notes: Additional notes.
            tags: Tags for categorization.
            domain: Clinical domain (for priority calculation).

        Returns:
            The created CorrectionRecord.
        """
        # Calculate priority based on correction characteristics
        is_negation_related = correction_type == CorrectionType.ASSERTION_WRONG
        priority = CorrectionPriority.calculate_priority(
            correction_type, is_negation_related, domain
        )

        correction = CorrectionRecord(
            correction_type=correction_type,
            priority=priority,
            document_id=document_id,
            patient_id=patient_id,
            mention_id=mention_id,
            fact_id=fact_id,
            original_text=original_text,
            original_start=original_start,
            original_end=original_end,
            original_value=original_value,
            original_confidence=original_confidence,
            corrected_value=corrected_value,
            corrected_text=corrected_text,
            corrected_start=corrected_start,
            corrected_end=corrected_end,
            context_before=context_before,
            context_after=context_after,
            section=section,
            note_type=note_type,
            corrected_by=corrected_by,
            notes=notes,
            tags=tags or [],
        )

        with self._lock:
            self._corrections[correction.id] = correction

        logger.info(
            f"Recorded correction {correction.id}: {correction_type.value} "
            f"(priority: {priority.value})"
        )

        return correction

    def flag_uncertain_sample(
        self,
        text: str,
        prediction_probabilities: dict[str, float],
        predicted_label: str | None = None,
        document_id: str | None = None,
        patient_id: str | None = None,
        mention_id: str | None = None,
        start_offset: int = 0,
        end_offset: int = 0,
        context_before: str = "",
        context_after: str = "",
        section: str | None = None,
    ) -> UncertaintySample | None:
        """Flag a sample for uncertainty review.

        Only flags if uncertainty exceeds threshold.

        Args:
            text: The extracted text.
            prediction_probabilities: Probabilities for each label.
            predicted_label: The predicted label.
            document_id: Source document ID.
            patient_id: Patient ID.
            mention_id: Mention ID.
            start_offset: Start offset in document.
            end_offset: End offset in document.
            context_before: Text before the mention.
            context_after: Text after the mention.
            section: Clinical section.

        Returns:
            UncertaintySample if flagged, None if below threshold.
        """
        # Calculate uncertainty metrics
        (
            uncertainty_score,
            entropy,
            margin,
            least_confident,
        ) = UncertaintySample.calculate_uncertainty_score(prediction_probabilities)

        # Only flag if above threshold
        if uncertainty_score < self._uncertainty_threshold:
            return None

        # Get predicted label if not provided
        if predicted_label is None and prediction_probabilities:
            predicted_label = max(prediction_probabilities, key=prediction_probabilities.get)

        predicted_confidence = prediction_probabilities.get(predicted_label, 0.0) if predicted_label else 0.0

        sample = UncertaintySample(
            document_id=document_id,
            patient_id=patient_id,
            mention_id=mention_id,
            text=text,
            start_offset=start_offset,
            end_offset=end_offset,
            context_before=context_before,
            context_after=context_after,
            section=section,
            predicted_label=predicted_label,
            predicted_confidence=predicted_confidence,
            prediction_probabilities=prediction_probabilities,
            entropy=entropy,
            margin=margin,
            least_confident=least_confident,
            uncertainty_score=uncertainty_score,
        )

        with self._lock:
            self._uncertain_samples[sample.id] = sample

        logger.debug(
            f"Flagged uncertain sample {sample.id}: score={uncertainty_score:.3f}, "
            f"entropy={entropy:.3f}, margin={margin:.3f}"
        )

        return sample

    def get_samples_for_review(
        self,
        limit: int = 20,
        uncertainty_type: UncertaintyType = UncertaintyType.ENTROPY,
        status: ReviewStatus = ReviewStatus.PENDING,
        section_filter: str | None = None,
    ) -> list[UncertaintySample]:
        """Get samples needing expert review, prioritized by uncertainty.

        Args:
            limit: Maximum number of samples to return.
            uncertainty_type: Which uncertainty metric to sort by.
            status: Filter by review status.
            section_filter: Filter by clinical section.

        Returns:
            List of samples sorted by uncertainty (most uncertain first).
        """
        with self._lock:
            # Filter samples
            samples = [
                s for s in self._uncertain_samples.values()
                if s.review_status == status
                and (section_filter is None or s.section == section_filter)
            ]

        # Sort by uncertainty metric
        if uncertainty_type == UncertaintyType.ENTROPY:
            samples.sort(key=lambda s: s.entropy, reverse=True)
        elif uncertainty_type == UncertaintyType.MARGIN:
            samples.sort(key=lambda s: s.margin)  # Lower = more uncertain
        elif uncertainty_type == UncertaintyType.LEAST_CONFIDENT:
            samples.sort(key=lambda s: s.least_confident, reverse=True)
        else:
            samples.sort(key=lambda s: s.uncertainty_score, reverse=True)

        return samples[:limit]

    def submit_review(
        self,
        sample_id: str,
        reviewed_by: str,
        review_result: str | None = None,
        review_notes: str | None = None,
        approved: bool = True,
    ) -> UncertaintySample | None:
        """Submit a review for an uncertain sample.

        Args:
            sample_id: ID of the sample being reviewed.
            reviewed_by: User ID of reviewer.
            review_result: The correct label (if different from predicted).
            review_notes: Additional notes.
            approved: Whether the prediction was correct.

        Returns:
            Updated sample, or None if not found.
        """
        with self._lock:
            sample = self._uncertain_samples.get(sample_id)
            if sample is None:
                return None

            sample.review_status = ReviewStatus.APPROVED if approved else ReviewStatus.REJECTED
            sample.reviewed_by = reviewed_by
            sample.reviewed_at = datetime.now(timezone.utc)
            sample.review_result = review_result
            sample.review_notes = review_notes

        # If rejected (prediction was wrong), create a correction record
        if not approved and review_result:
            self.record_correction(
                correction_type=CorrectionType.ASSERTION_WRONG,
                original_text=sample.text,
                original_value=sample.predicted_label,
                corrected_value=review_result,
                document_id=sample.document_id,
                patient_id=sample.patient_id,
                mention_id=sample.mention_id,
                original_start=sample.start_offset,
                original_end=sample.end_offset,
                original_confidence=sample.predicted_confidence,
                context_before=sample.context_before,
                context_after=sample.context_after,
                section=sample.section,
                corrected_by=reviewed_by,
                notes=review_notes,
            )

        logger.info(f"Review submitted for sample {sample_id}: {'approved' if approved else 'rejected'}")

        return sample

    def generate_training_dataset(
        self,
        name: str,
        description: str = "",
        correction_types: list[CorrectionType] | None = None,
        min_priority: CorrectionPriority = CorrectionPriority.LOW,
        include_reviewed_samples: bool = True,
        train_split: float = 0.8,
        validation_split: float = 0.1,
        test_split: float = 0.1,
        output_format: str = "jsonl",
    ) -> TrainingDataset:
        """Generate a training dataset from corrections and reviewed samples.

        Args:
            name: Dataset name.
            description: Dataset description.
            correction_types: Filter by correction types.
            min_priority: Minimum priority to include.
            include_reviewed_samples: Include reviewed uncertain samples.
            train_split: Fraction for training set.
            validation_split: Fraction for validation set.
            test_split: Fraction for test set.
            output_format: Output format (jsonl, csv, etc.).

        Returns:
            The generated TrainingDataset.
        """
        priority_order = [
            CorrectionPriority.CRITICAL,
            CorrectionPriority.HIGH,
            CorrectionPriority.MEDIUM,
            CorrectionPriority.LOW,
        ]
        min_priority_index = priority_order.index(min_priority)
        valid_priorities = set(priority_order[: min_priority_index + 1])

        with self._lock:
            # Collect corrections
            corrections = [
                c for c in self._corrections.values()
                if (correction_types is None or c.correction_type in correction_types)
                and c.priority in valid_priorities
                and not c.included_in_training
            ]

            # Collect reviewed samples that were rejected (corrections needed)
            reviewed_samples = []
            if include_reviewed_samples:
                reviewed_samples = [
                    s for s in self._uncertain_samples.values()
                    if s.review_status == ReviewStatus.REJECTED
                    and s.review_result is not None
                ]

        # Convert to training examples
        examples = []
        correction_ids = []
        sample_ids = []

        for correction in corrections:
            examples.append(correction.to_training_example())
            correction_ids.append(correction.id)

        for sample in reviewed_samples:
            examples.append({
                "id": sample.id,
                "text": f"{sample.context_before}{sample.text}{sample.context_after}",
                "entities": [{
                    "start": len(sample.context_before),
                    "end": len(sample.context_before) + len(sample.text),
                    "label": sample.review_result,
                }],
                "correction_type": "review_correction",
                "original_value": sample.predicted_label,
                "corrected_value": sample.review_result,
                "section": sample.section,
                "metadata": {
                    "document_id": sample.document_id,
                    "patient_id": sample.patient_id,
                    "uncertainty_score": sample.uncertainty_score,
                },
            })
            sample_ids.append(sample.id)

        # Split into train/validation/test
        import random
        random.shuffle(examples)

        total = len(examples)
        train_end = int(total * train_split)
        val_end = train_end + int(total * validation_split)

        dataset = TrainingDataset(
            name=name,
            description=description,
            task_type="correction_feedback",
            total_examples=total,
            train_examples=train_end,
            validation_examples=val_end - train_end,
            test_examples=total - val_end,
            correction_ids=correction_ids,
            sample_ids=sample_ids,
            output_format=output_format,
            status="ready",
        )

        # Mark corrections as included
        with self._lock:
            for cid in correction_ids:
                if cid in self._corrections:
                    self._corrections[cid].included_in_training = True
                    self._corrections[cid].training_dataset_id = dataset.id

            self._datasets[dataset.id] = dataset

        logger.info(
            f"Generated training dataset '{name}' with {total} examples "
            f"(train: {dataset.train_examples}, val: {dataset.validation_examples}, "
            f"test: {dataset.test_examples})"
        )

        return dataset

    def get_improvement_metrics(self) -> ImprovementMetrics:
        """Calculate improvement metrics from recorded feedback.

        Returns:
            ImprovementMetrics with current statistics.
        """
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        with self._lock:
            corrections = list(self._corrections.values())
            samples = list(self._uncertain_samples.values())
            datasets = list(self._datasets.values())

        # Count corrections by type
        corrections_by_type: dict[str, int] = defaultdict(int)
        corrections_by_priority: dict[str, int] = defaultdict(int)
        corrections_by_domain: dict[str, int] = defaultdict(int)

        for c in corrections:
            corrections_by_type[c.correction_type.value] += 1
            corrections_by_priority[c.priority.value] += 1
            # Infer domain from tags or section
            domain = "unknown"
            if c.tags:
                domain = c.tags[0]
            elif c.section:
                domain = c.section
            corrections_by_domain[domain] += 1

        # Weekly trends
        corrections_this_week = sum(1 for c in corrections if c.created_at >= week_ago)
        corrections_last_week = sum(
            1 for c in corrections if two_weeks_ago <= c.created_at < week_ago
        )
        correction_trend = 0.0
        if corrections_last_week > 0:
            correction_trend = (corrections_this_week - corrections_last_week) / corrections_last_week

        # Review statistics
        pending_reviews = sum(1 for s in samples if s.review_status == ReviewStatus.PENDING)

        reviewed_samples = [s for s in samples if s.reviewed_at is not None]
        avg_review_time = 0.0
        if reviewed_samples:
            review_times = [
                (s.reviewed_at - s.created_at).total_seconds() / 3600
                for s in reviewed_samples
            ]
            avg_review_time = sum(review_times) / len(review_times)

        # Agreement rate
        approved_count = sum(1 for s in reviewed_samples if s.review_status == ReviewStatus.APPROVED)
        agreement_rate = approved_count / len(reviewed_samples) if reviewed_samples else 0.0

        # Training statistics
        examples_used = sum(1 for c in corrections if c.included_in_training)

        # Top error categories
        top_errors = sorted(corrections_by_type.items(), key=lambda x: x[1], reverse=True)[:5]
        top_error_categories = [{"type": t, "count": c} for t, c in top_errors]

        # Estimate accuracy improvement (rough heuristic)
        # More corrections + lower agreement rate = more room for improvement
        estimated_improvement = min(
            0.1 * (1.0 - agreement_rate) * (len(corrections) / 100),
            0.05,  # Cap at 5% improvement estimate
        )

        return ImprovementMetrics(
            total_corrections=len(corrections),
            corrections_by_type=dict(corrections_by_type),
            corrections_by_priority=dict(corrections_by_priority),
            corrections_by_domain=dict(corrections_by_domain),
            corrections_this_week=corrections_this_week,
            corrections_last_week=corrections_last_week,
            correction_trend=correction_trend,
            pending_reviews=pending_reviews,
            avg_review_time_hours=avg_review_time,
            review_agreement_rate=agreement_rate,
            training_datasets_created=len(datasets),
            examples_used_for_training=examples_used,
            estimated_accuracy_improvement=estimated_improvement,
            top_error_categories=top_error_categories,
        )

    def get_correction(self, correction_id: str) -> CorrectionRecord | None:
        """Get a correction by ID."""
        with self._lock:
            return self._corrections.get(correction_id)

    def get_corrections(
        self,
        correction_type: CorrectionType | None = None,
        priority: CorrectionPriority | None = None,
        document_id: str | None = None,
        limit: int = 100,
    ) -> list[CorrectionRecord]:
        """Get corrections with optional filters."""
        with self._lock:
            corrections = [
                c for c in self._corrections.values()
                if (correction_type is None or c.correction_type == correction_type)
                and (priority is None or c.priority == priority)
                and (document_id is None or c.document_id == document_id)
            ]
        corrections.sort(key=lambda c: c.created_at, reverse=True)
        return corrections[:limit]

    def get_sample(self, sample_id: str) -> UncertaintySample | None:
        """Get an uncertain sample by ID."""
        with self._lock:
            return self._uncertain_samples.get(sample_id)

    def get_dataset(self, dataset_id: str) -> TrainingDataset | None:
        """Get a training dataset by ID."""
        with self._lock:
            return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[TrainingDataset]:
        """List all training datasets."""
        with self._lock:
            return list(self._datasets.values())


# Module-level singleton
_active_learning_service: ActiveLearningService | None = None
_service_lock = threading.Lock()


def get_active_learning_service() -> ActiveLearningService:
    """Get the active learning service singleton."""
    global _active_learning_service
    if _active_learning_service is None:
        with _service_lock:
            if _active_learning_service is None:
                _active_learning_service = ActiveLearningService()
    return _active_learning_service
