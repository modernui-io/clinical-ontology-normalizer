"""Tests for Active Learning Feedback Service."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.services.active_learning_service import (
    ActiveLearningService,
    CorrectionPriority,
    CorrectionRecord,
    CorrectionType,
    ReviewStatus,
    TrainingDataset,
    UncertaintySample,
    UncertaintyType,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service():
    """Create a fresh ActiveLearningService for each test."""
    return ActiveLearningService()


@pytest.fixture
def sample_correction_data():
    """Sample data for creating corrections."""
    return {
        "correction_type": CorrectionType.ASSERTION_WRONG,
        "original_text": "chest pain",
        "original_value": "absent",
        "corrected_value": "present",
        "document_id": "doc_123",
        "patient_id": "patient_456",
        "context_before": "Patient denies ",
        "context_after": " but reports discomfort.",
        "section": "HPI",
        "note_type": "Progress Note",
        "corrected_by": "dr_smith",
    }


@pytest.fixture
def sample_prediction_probabilities():
    """Sample prediction probabilities for uncertainty testing."""
    return {
        "present": 0.45,
        "absent": 0.35,
        "possible": 0.20,
    }


# =============================================================================
# CorrectionPriority Tests
# =============================================================================


class TestCorrectionPriority:
    """Tests for CorrectionPriority calculation."""

    def test_negation_related_is_critical(self):
        """Negation-related errors should be critical priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ASSERTION_WRONG,
            is_negation_related=True,
        )
        assert priority == CorrectionPriority.CRITICAL

    def test_drug_domain_missed_entity_is_critical(self):
        """Missed drug entities should be critical priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ENTITY_MISSED,
            is_negation_related=False,
            domain="Drug",
        )
        assert priority == CorrectionPriority.CRITICAL

    def test_drug_domain_wrong_assertion_is_critical(self):
        """Wrong drug assertions should be critical priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ASSERTION_WRONG,
            is_negation_related=False,
            domain="Medication",
        )
        assert priority == CorrectionPriority.CRITICAL

    def test_drug_domain_other_errors_are_high(self):
        """Other drug-related errors should be high priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ENTITY_WRONG,
            is_negation_related=False,
            domain="Drug",
        )
        assert priority == CorrectionPriority.HIGH

    def test_missed_entity_is_high(self):
        """Missed entities should be high priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ENTITY_MISSED,
        )
        assert priority == CorrectionPriority.HIGH

    def test_false_positive_is_high(self):
        """False positive entities should be high priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ENTITY_FALSE_POSITIVE,
        )
        assert priority == CorrectionPriority.HIGH

    def test_assertion_wrong_is_high(self):
        """Wrong assertions should be high priority (without negation flag)."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ASSERTION_WRONG,
            is_negation_related=False,
        )
        assert priority == CorrectionPriority.HIGH

    def test_entity_wrong_is_medium(self):
        """Wrong entity spans should be medium priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.ENTITY_WRONG,
        )
        assert priority == CorrectionPriority.MEDIUM

    def test_temporality_wrong_is_medium(self):
        """Wrong temporality should be medium priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.TEMPORALITY_WRONG,
        )
        assert priority == CorrectionPriority.MEDIUM

    def test_section_wrong_is_low(self):
        """Wrong section detection should be low priority."""
        priority = CorrectionPriority.calculate_priority(
            CorrectionType.SECTION_WRONG,
        )
        assert priority == CorrectionPriority.LOW


# =============================================================================
# UncertaintySample Tests
# =============================================================================


class TestUncertaintySample:
    """Tests for uncertainty metric calculations."""

    def test_calculate_entropy_uniform(self):
        """Uniform distribution should have maximum entropy (1.0)."""
        probs = {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
        entropy = UncertaintySample.calculate_entropy(probs)
        assert abs(entropy - 1.0) < 0.01

    def test_calculate_entropy_certain(self):
        """Certain prediction should have zero entropy."""
        probs = {"a": 1.0, "b": 0.0, "c": 0.0}
        entropy = UncertaintySample.calculate_entropy(probs)
        assert entropy == 0.0

    def test_calculate_entropy_skewed(self):
        """Skewed distribution should have intermediate entropy."""
        probs = {"a": 0.9, "b": 0.05, "c": 0.05}
        entropy = UncertaintySample.calculate_entropy(probs)
        assert 0 < entropy < 1.0

    def test_calculate_entropy_empty(self):
        """Empty probabilities should return 0."""
        entropy = UncertaintySample.calculate_entropy({})
        assert entropy == 0.0

    def test_calculate_margin_high_confidence(self):
        """High confidence should have high margin."""
        probs = {"a": 0.9, "b": 0.1}
        margin = UncertaintySample.calculate_margin(probs)
        assert margin == 0.8

    def test_calculate_margin_uncertain(self):
        """Close predictions should have low margin."""
        probs = {"a": 0.51, "b": 0.49}
        margin = UncertaintySample.calculate_margin(probs)
        assert abs(margin - 0.02) < 0.001

    def test_calculate_margin_single_class(self):
        """Single class should return margin of 1.0."""
        probs = {"a": 1.0}
        margin = UncertaintySample.calculate_margin(probs)
        assert margin == 1.0

    def test_calculate_least_confident_high(self):
        """High confidence should have low least_confident."""
        probs = {"a": 0.9, "b": 0.1}
        lc = UncertaintySample.calculate_least_confident(probs)
        assert lc == pytest.approx(0.1)

    def test_calculate_least_confident_uncertain(self):
        """Low confidence should have high least_confident."""
        probs = {"a": 0.4, "b": 0.35, "c": 0.25}
        lc = UncertaintySample.calculate_least_confident(probs)
        assert lc == 0.6

    def test_calculate_least_confident_empty(self):
        """Empty probabilities should return 1.0."""
        lc = UncertaintySample.calculate_least_confident({})
        assert lc == 1.0

    def test_calculate_uncertainty_score_combines_metrics(self):
        """Uncertainty score should combine all metrics."""
        probs = {"a": 0.45, "b": 0.35, "c": 0.20}
        score, entropy, margin, least_conf = UncertaintySample.calculate_uncertainty_score(probs)

        # Verify individual metrics are calculated
        assert entropy > 0
        assert margin < 1.0
        assert least_conf > 0

        # Verify combined score
        assert 0 < score < 1.0


# =============================================================================
# ActiveLearningService Correction Tests
# =============================================================================


class TestActiveLearningServiceCorrections:
    """Tests for correction recording and retrieval."""

    def test_record_correction_creates_record(self, service, sample_correction_data):
        """Recording a correction should create a CorrectionRecord."""
        correction = service.record_correction(**sample_correction_data)

        assert correction.id is not None
        assert correction.correction_type == CorrectionType.ASSERTION_WRONG
        assert correction.original_text == "chest pain"
        assert correction.corrected_value == "present"

    def test_record_correction_calculates_priority(self, service, sample_correction_data):
        """Priority should be calculated based on correction type."""
        correction = service.record_correction(**sample_correction_data)

        # Assertion errors are marked as negation-related by default
        assert correction.priority == CorrectionPriority.CRITICAL

    def test_record_correction_drug_domain_priority(self, service):
        """Drug domain should influence priority."""
        correction = service.record_correction(
            correction_type=CorrectionType.ENTITY_MISSED,
            original_text="metformin",
            domain="Drug",
        )

        assert correction.priority == CorrectionPriority.CRITICAL

    def test_get_correction_returns_record(self, service, sample_correction_data):
        """get_correction should return the stored record."""
        created = service.record_correction(**sample_correction_data)
        retrieved = service.get_correction(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.original_text == created.original_text

    def test_get_correction_not_found_returns_none(self, service):
        """get_correction should return None for unknown ID."""
        result = service.get_correction("unknown_id")
        assert result is None

    def test_get_corrections_returns_all(self, service, sample_correction_data):
        """get_corrections should return all matching records."""
        service.record_correction(**sample_correction_data)
        service.record_correction(
            correction_type=CorrectionType.ENTITY_MISSED,
            original_text="diabetes",
        )

        corrections = service.get_corrections()
        assert len(corrections) == 2

    def test_get_corrections_filter_by_type(self, service):
        """get_corrections should filter by correction type."""
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )
        service.record_correction(
            correction_type=CorrectionType.ENTITY_MISSED,
            original_text="diabetes",
        )

        corrections = service.get_corrections(
            correction_type=CorrectionType.ENTITY_MISSED
        )
        assert len(corrections) == 1
        assert corrections[0].correction_type == CorrectionType.ENTITY_MISSED

    def test_get_corrections_filter_by_priority(self, service):
        """get_corrections should filter by priority."""
        # Create critical (assertion)
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )
        # Create low priority
        service.record_correction(
            correction_type=CorrectionType.SECTION_WRONG,
            original_text="section",
        )

        corrections = service.get_corrections(priority=CorrectionPriority.LOW)
        assert len(corrections) == 1

    def test_get_corrections_limit(self, service):
        """get_corrections should respect limit."""
        for i in range(10):
            service.record_correction(
                correction_type=CorrectionType.OTHER,
                original_text=f"text_{i}",
            )

        corrections = service.get_corrections(limit=5)
        assert len(corrections) == 5


# =============================================================================
# ActiveLearningService Uncertainty Tests
# =============================================================================


class TestActiveLearningServiceUncertainty:
    """Tests for uncertainty sample handling."""

    def test_flag_uncertain_sample_above_threshold(
        self, service, sample_prediction_probabilities
    ):
        """Uncertain samples above threshold should be flagged."""
        sample = service.flag_uncertain_sample(
            text="mild discomfort",
            prediction_probabilities=sample_prediction_probabilities,
        )

        assert sample is not None
        assert sample.text == "mild discomfort"
        assert sample.uncertainty_score > 0

    def test_flag_uncertain_sample_below_threshold(self, service):
        """Certain samples below threshold should not be flagged."""
        sample = service.flag_uncertain_sample(
            text="chest pain",
            prediction_probabilities={"present": 0.95, "absent": 0.05},
        )

        # Low uncertainty should not be flagged
        assert sample is None

    def test_flag_uncertain_sample_calculates_metrics(
        self, service, sample_prediction_probabilities
    ):
        """Flagged samples should have all uncertainty metrics."""
        sample = service.flag_uncertain_sample(
            text="discomfort",
            prediction_probabilities=sample_prediction_probabilities,
        )

        assert sample is not None
        assert sample.entropy > 0
        assert sample.margin < 1.0
        assert sample.least_confident > 0
        assert sample.uncertainty_score > 0

    def test_flag_uncertain_sample_infers_label(
        self, service, sample_prediction_probabilities
    ):
        """Predicted label should be inferred if not provided."""
        sample = service.flag_uncertain_sample(
            text="discomfort",
            prediction_probabilities=sample_prediction_probabilities,
        )

        assert sample is not None
        assert sample.predicted_label == "present"  # Highest probability

    def test_get_samples_for_review_sorts_by_entropy(self, service):
        """Samples should be sorted by entropy (highest first)."""
        # Create samples with different uncertainty levels
        service.flag_uncertain_sample(
            text="low_entropy",
            prediction_probabilities={"a": 0.7, "b": 0.3},
        )
        service.flag_uncertain_sample(
            text="high_entropy",
            prediction_probabilities={"a": 0.34, "b": 0.33, "c": 0.33},
        )

        samples = service.get_samples_for_review(
            uncertainty_type=UncertaintyType.ENTROPY
        )

        if len(samples) >= 2:
            assert samples[0].entropy >= samples[1].entropy

    def test_get_samples_for_review_filters_by_status(self, service):
        """Samples should be filtered by review status."""
        sample = service.flag_uncertain_sample(
            text="text",
            prediction_probabilities={"a": 0.5, "b": 0.5},
        )

        # Mark as reviewed
        if sample:
            service.submit_review(
                sample_id=sample.id,
                reviewed_by="reviewer",
                approved=True,
            )

        pending = service.get_samples_for_review(status=ReviewStatus.PENDING)
        approved = service.get_samples_for_review(status=ReviewStatus.APPROVED)

        # Original sample should now be approved, not pending
        assert all(s.review_status == ReviewStatus.PENDING for s in pending)
        assert all(s.review_status == ReviewStatus.APPROVED for s in approved)


# =============================================================================
# ActiveLearningService Review Tests
# =============================================================================


class TestActiveLearningServiceReview:
    """Tests for sample review submission."""

    def test_submit_review_approved(self, service, sample_prediction_probabilities):
        """Approved reviews should update status."""
        sample = service.flag_uncertain_sample(
            text="text",
            prediction_probabilities=sample_prediction_probabilities,
        )
        assert sample is not None

        reviewed = service.submit_review(
            sample_id=sample.id,
            reviewed_by="dr_jones",
            approved=True,
        )

        assert reviewed is not None
        assert reviewed.review_status == ReviewStatus.APPROVED
        assert reviewed.reviewed_by == "dr_jones"
        assert reviewed.reviewed_at is not None

    def test_submit_review_rejected_creates_correction(
        self, service, sample_prediction_probabilities
    ):
        """Rejected reviews should create a correction record."""
        sample = service.flag_uncertain_sample(
            text="chest pain",
            prediction_probabilities=sample_prediction_probabilities,
            document_id="doc_123",
        )
        assert sample is not None

        reviewed = service.submit_review(
            sample_id=sample.id,
            reviewed_by="dr_jones",
            review_result="absent",  # Correct to absent
            approved=False,
        )

        assert reviewed is not None
        assert reviewed.review_status == ReviewStatus.REJECTED

        # Check that a correction was created
        corrections = service.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].corrected_value == "absent"

    def test_submit_review_not_found(self, service):
        """Submitting review for unknown sample returns None."""
        result = service.submit_review(
            sample_id="unknown_id",
            reviewed_by="reviewer",
            approved=True,
        )
        assert result is None


# =============================================================================
# ActiveLearningService Training Dataset Tests
# =============================================================================


class TestActiveLearningServiceDataset:
    """Tests for training dataset generation."""

    def test_generate_training_dataset_from_corrections(self, service):
        """Dataset should include corrections."""
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
            original_value="absent",
            corrected_value="present",
        )
        service.record_correction(
            correction_type=CorrectionType.ENTITY_MISSED,
            original_text="diabetes",
        )

        dataset = service.generate_training_dataset(name="test_dataset")

        assert dataset.name == "test_dataset"
        assert dataset.total_examples == 2
        assert len(dataset.correction_ids) == 2

    def test_generate_training_dataset_marks_included(self, service):
        """Included corrections should be marked."""
        correction = service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )

        service.generate_training_dataset(name="test")

        # Check correction was marked
        updated = service.get_correction(correction.id)
        assert updated is not None
        assert updated.included_in_training is True

    def test_generate_training_dataset_excludes_already_included(self, service):
        """Already-included corrections should not be re-included."""
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )

        # Generate first dataset
        dataset1 = service.generate_training_dataset(name="first")
        assert dataset1.total_examples == 1

        # Generate second dataset
        dataset2 = service.generate_training_dataset(name="second")
        assert dataset2.total_examples == 0  # No new corrections

    def test_generate_training_dataset_filter_by_type(self, service):
        """Dataset should filter by correction type."""
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )
        service.record_correction(
            correction_type=CorrectionType.ENTITY_MISSED,
            original_text="diabetes",
        )

        dataset = service.generate_training_dataset(
            name="assertions_only",
            correction_types=[CorrectionType.ASSERTION_WRONG],
        )

        assert dataset.total_examples == 1

    def test_generate_training_dataset_includes_reviewed_samples(self, service):
        """Dataset should include rejected review samples."""
        sample = service.flag_uncertain_sample(
            text="pain",
            prediction_probabilities={"present": 0.5, "absent": 0.5},
        )
        assert sample is not None

        service.submit_review(
            sample_id=sample.id,
            reviewed_by="reviewer",
            review_result="absent",
            approved=False,
        )

        dataset = service.generate_training_dataset(
            name="with_reviews",
            include_reviewed_samples=True,
        )

        # Should have 1 from the rejected review (creates correction) + 1 review sample
        assert len(dataset.sample_ids) == 1

    def test_generate_training_dataset_splits(self, service):
        """Dataset should have correct splits."""
        for i in range(10):
            service.record_correction(
                correction_type=CorrectionType.OTHER,
                original_text=f"text_{i}",
            )

        dataset = service.generate_training_dataset(
            name="split_test",
            train_split=0.8,
            validation_split=0.1,
            test_split=0.1,
        )

        assert dataset.total_examples == 10
        assert dataset.train_examples == 8
        assert dataset.validation_examples == 1
        assert dataset.test_examples == 1

    def test_list_datasets(self, service):
        """list_datasets should return all datasets."""
        service.record_correction(
            correction_type=CorrectionType.OTHER,
            original_text="text",
        )

        service.generate_training_dataset(name="dataset1")

        # Add another correction for second dataset
        service.record_correction(
            correction_type=CorrectionType.OTHER,
            original_text="text2",
        )
        service.generate_training_dataset(name="dataset2")

        datasets = service.list_datasets()
        assert len(datasets) == 2

    def test_get_dataset_by_id(self, service):
        """get_dataset should return dataset by ID."""
        service.record_correction(
            correction_type=CorrectionType.OTHER,
            original_text="text",
        )

        created = service.generate_training_dataset(name="test")
        retrieved = service.get_dataset(created.id)

        assert retrieved is not None
        assert retrieved.name == "test"


# =============================================================================
# ActiveLearningService Metrics Tests
# =============================================================================


class TestActiveLearningServiceMetrics:
    """Tests for improvement metrics."""

    def test_get_improvement_metrics_counts_corrections(self, service):
        """Metrics should count total corrections."""
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )
        service.record_correction(
            correction_type=CorrectionType.ENTITY_MISSED,
            original_text="diabetes",
        )

        metrics = service.get_improvement_metrics()

        assert metrics.total_corrections == 2

    def test_get_improvement_metrics_by_type(self, service):
        """Metrics should count corrections by type."""
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="fever",
        )
        service.record_correction(
            correction_type=CorrectionType.ENTITY_MISSED,
            original_text="diabetes",
        )

        metrics = service.get_improvement_metrics()

        assert metrics.corrections_by_type["assertion_wrong"] == 2
        assert metrics.corrections_by_type["entity_missed"] == 1

    def test_get_improvement_metrics_by_priority(self, service):
        """Metrics should count corrections by priority."""
        service.record_correction(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="pain",
        )  # Critical
        service.record_correction(
            correction_type=CorrectionType.SECTION_WRONG,
            original_text="section",
        )  # Low

        metrics = service.get_improvement_metrics()

        assert metrics.corrections_by_priority.get("critical", 0) == 1
        assert metrics.corrections_by_priority.get("low", 0) == 1

    def test_get_improvement_metrics_pending_reviews(self, service):
        """Metrics should count pending reviews."""
        service.flag_uncertain_sample(
            text="pain1",
            prediction_probabilities={"a": 0.5, "b": 0.5},
        )
        service.flag_uncertain_sample(
            text="pain2",
            prediction_probabilities={"a": 0.5, "b": 0.5},
        )

        metrics = service.get_improvement_metrics()

        assert metrics.pending_reviews == 2

    def test_get_improvement_metrics_agreement_rate(self, service):
        """Metrics should calculate agreement rate."""
        # Create and approve one sample
        sample1 = service.flag_uncertain_sample(
            text="text1",
            prediction_probabilities={"a": 0.5, "b": 0.5},
        )
        if sample1:
            service.submit_review(sample1.id, "reviewer", approved=True)

        # Create and reject one sample
        sample2 = service.flag_uncertain_sample(
            text="text2",
            prediction_probabilities={"a": 0.5, "b": 0.5},
        )
        if sample2:
            service.submit_review(sample2.id, "reviewer", approved=False)

        metrics = service.get_improvement_metrics()

        # 1 approved, 1 rejected = 50% agreement
        assert metrics.review_agreement_rate == 0.5

    def test_get_improvement_metrics_training_stats(self, service):
        """Metrics should track training statistics."""
        service.record_correction(
            correction_type=CorrectionType.OTHER,
            original_text="text",
        )
        service.generate_training_dataset(name="test")

        metrics = service.get_improvement_metrics()

        assert metrics.training_datasets_created == 1
        assert metrics.examples_used_for_training == 1


# =============================================================================
# CorrectionRecord Tests
# =============================================================================


class TestCorrectionRecord:
    """Tests for CorrectionRecord conversion."""

    def test_to_training_example_basic(self):
        """to_training_example should create proper structure."""
        record = CorrectionRecord(
            correction_type=CorrectionType.ASSERTION_WRONG,
            original_text="chest pain",
            original_value="absent",
            corrected_value="present",
            context_before="Patient denies ",
            context_after=" but reports discomfort.",
            section="HPI",
            document_id="doc_123",
            patient_id="patient_456",
        )

        example = record.to_training_example()

        assert example["id"] == record.id
        assert "Patient denies chest pain but reports discomfort." in example["text"]
        assert len(example["entities"]) == 1
        assert example["entities"][0]["label"] == "present"
        assert example["correction_type"] == "assertion_wrong"
        assert example["metadata"]["document_id"] == "doc_123"

    def test_to_training_example_entity_positions(self):
        """Entity positions should be correct relative to context."""
        record = CorrectionRecord(
            correction_type=CorrectionType.ENTITY_WRONG,
            original_text="pain",
            corrected_value="present",
            context_before="Has ",  # 4 chars
            context_after=" today.",
        )

        example = record.to_training_example()

        assert example["entities"][0]["start"] == 4  # len("Has ")
        assert example["entities"][0]["end"] == 8  # len("Has ") + len("pain")
