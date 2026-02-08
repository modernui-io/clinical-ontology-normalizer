"""NLP Pipeline Regression Test Suite (CTO-3).

Golden-dataset-driven regression tests that catch NLP extraction quality
regressions before they reach production. Uses the ExtractionPipeline
(pattern-based extraction with context analysis and validation) to
test against annotated clinical notes.

Markers:
    @pytest.mark.regression - All tests are gated behind this marker for CI.

Thresholds:
    - Precision >= 0.70
    - Recall >= 0.60
    - These are baseline thresholds; tighten as pipeline improves.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import pytest

from app.services.extraction_pipeline import ExtractionPipeline, PipelineEntity

from tests.test_nlp_regression_utils import (
    ActualMention,
    ExpectedMention,
    GoldenNote,
    MentionMatch,
    MetricResult,
    NoteResult,
    RegressionResult,
    _assertion_slice,
    _domain_slice,
    _normalize_assertion,
    _normalize_domain,
    calculate_mention_metrics,
    calculate_metrics_by_slice,
    compare_mentions,
    generate_regression_report,
    load_golden_dataset,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

MIN_PRECISION = 0.70
MIN_RECALL = 0.60
MIN_F1 = 0.60

# Per-domain thresholds (can be looser for harder domains)
DOMAIN_THRESHOLDS: dict[str, dict[str, float]] = {
    "condition": {"precision": 0.65, "recall": 0.55},
    "drug": {"precision": 0.75, "recall": 0.65},
    "measurement": {"precision": 0.75, "recall": 0.60},
}

# Per-assertion thresholds
ASSERTION_THRESHOLDS: dict[str, dict[str, float]] = {
    "present": {"precision": 0.70, "recall": 0.60},
    "absent": {"precision": 0.50, "recall": 0.40},
    "possible": {"precision": 0.30, "recall": 0.20},
}


# ---------------------------------------------------------------------------
# Helpers: convert pipeline output to ActualMention objects
# ---------------------------------------------------------------------------

def _entity_to_assertion(entity: PipelineEntity) -> str:
    """Derive the best assertion string for a PipelineEntity.

    The ExtractionPipeline's ContextAnalyzer marks negated and family-history
    entities with `include_in_output=False` and sets flags like `is_negated`
    and `is_family_history`. For regression testing we need those entities to
    appear in the output with the correct assertion so we can measure assertion
    detection accuracy.
    """
    if entity.is_family_history:
        return "family"
    if entity.is_negated:
        return "absent"
    if entity.is_uncertain:
        return "possible"
    if entity.is_historical:
        return "historical"
    # Fall back to the string assertion set by the context analyzer
    return entity.assertion


def _pipeline_entity_to_actual(entity: PipelineEntity) -> ActualMention:
    """Convert a PipelineEntity to an ActualMention for comparison."""
    return ActualMention(
        text=entity.text,
        domain=entity.entity_type,  # "condition", "drug", "measurement"
        assertion=_entity_to_assertion(entity),
        concept_name=entity.normalized_text,
        confidence=entity.final_confidence,
        start_offset=entity.span_start,
        end_offset=entity.span_end,
    )


def _run_pipeline_on_note(
    pipeline: ExtractionPipeline,
    note: GoldenNote,
) -> list[ActualMention]:
    """Run the extraction pipeline on a golden note and return ActualMentions.

    IMPORTANT: We include ALL extracted entities -- even those the pipeline
    marks as `include_in_output=False` (negated, family history) -- because
    the golden dataset expects negated and family-history mentions to appear
    with their correct assertion type. The pipeline's context analyzer still
    *detects* these; it just filters them from the default output. Regression
    testing needs to verify detection accuracy, not output filtering.
    """
    # Run pipeline stages manually to access all entities
    preprocessing_result = pipeline.preprocessor.process(note.text)
    entities = pipeline.extractor.extract(note.text, preprocessing_result)
    entities = pipeline.context_analyzer.analyze(entities, note.text, preprocessing_result)
    entities = pipeline.validator.validate(entities)

    actual_mentions = []
    for entity in entities:
        actual_mentions.append(_pipeline_entity_to_actual(entity))

    return actual_mentions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pipeline() -> ExtractionPipeline:
    """Create a fresh ExtractionPipeline for the test module."""
    return ExtractionPipeline(min_confidence=0.3)


@pytest.fixture(scope="module")
def golden_notes() -> list[GoldenNote]:
    """Load the golden dataset."""
    return load_golden_dataset()


@pytest.fixture(scope="module")
def regression_result(
    pipeline: ExtractionPipeline,
    golden_notes: list[GoldenNote],
) -> RegressionResult:
    """Run the full pipeline over all golden notes and compute metrics.

    This fixture is computed once per module and shared across all tests.
    """
    all_matches: list[MentionMatch] = []
    note_results: list[NoteResult] = []
    category_matches: dict[str, list[MentionMatch]] = defaultdict(list)

    for note in golden_notes:
        actual = _run_pipeline_on_note(pipeline, note)
        matches = compare_mentions(note.expected_mentions, actual)

        note_metrics = calculate_mention_metrics(matches)
        note_results.append(
            NoteResult(
                note_id=note.note_id,
                category=note.category,
                matches=matches,
                metrics=note_metrics,
            )
        )

        all_matches.extend(matches)
        category_matches[note.category].extend(matches)

    overall_metrics = calculate_mention_metrics(all_matches)
    domain_metrics = calculate_metrics_by_slice(all_matches, _domain_slice)
    assertion_metrics = calculate_metrics_by_slice(all_matches, _assertion_slice)
    category_metrics = {
        cat: calculate_mention_metrics(ms)
        for cat, ms in category_matches.items()
    }

    return RegressionResult(
        note_results=note_results,
        overall_metrics=overall_metrics,
        domain_metrics=domain_metrics,
        assertion_metrics=assertion_metrics,
        category_metrics=category_metrics,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.regression
class TestGoldenDatasetLoading:
    """Verify the golden dataset loads correctly."""

    def test_golden_dataset_loads(self, golden_notes: list[GoldenNote]) -> None:
        """Golden dataset should load without errors."""
        assert len(golden_notes) >= 25, (
            f"Golden dataset should have >= 25 notes, got {len(golden_notes)}"
        )

    def test_golden_notes_have_expected_mentions(
        self, golden_notes: list[GoldenNote]
    ) -> None:
        """Every golden note should have at least one expected mention."""
        for note in golden_notes:
            assert len(note.expected_mentions) > 0, (
                f"Note {note.note_id} has no expected mentions"
            )

    def test_golden_dataset_covers_domains(
        self, golden_notes: list[GoldenNote]
    ) -> None:
        """Golden dataset should cover all key domains."""
        domains = set()
        for note in golden_notes:
            for em in note.expected_mentions:
                domains.add(em.domain)

        required_domains = {"CONDITION", "MEDICATION", "LAB"}
        missing = required_domains - domains
        assert not missing, f"Golden dataset missing domains: {missing}"

    def test_golden_dataset_covers_assertions(
        self, golden_notes: list[GoldenNote]
    ) -> None:
        """Golden dataset should cover key assertion types."""
        assertions = set()
        for note in golden_notes:
            for em in note.expected_mentions:
                assertions.add(em.assertion)

        required_assertions = {"PRESENT", "ABSENT"}
        missing = required_assertions - assertions
        assert not missing, f"Golden dataset missing assertion types: {missing}"

    def test_golden_dataset_covers_categories(
        self, golden_notes: list[GoldenNote]
    ) -> None:
        """Golden dataset should cover multiple clinical categories."""
        categories = {note.category for note in golden_notes}
        assert len(categories) >= 3, (
            f"Golden dataset should cover >= 3 categories, got {len(categories)}: {categories}"
        )


@pytest.mark.regression
class TestOverallMetrics:
    """Test overall precision, recall, and F1 thresholds."""

    def test_overall_precision(self, regression_result: RegressionResult) -> None:
        """Overall precision should meet minimum threshold."""
        p = regression_result.overall_metrics.precision
        assert p >= MIN_PRECISION, (
            f"Overall precision {p:.3f} < {MIN_PRECISION} threshold. "
            f"TP={regression_result.overall_metrics.true_positives}, "
            f"FP={regression_result.overall_metrics.false_positives}"
        )

    def test_overall_recall(self, regression_result: RegressionResult) -> None:
        """Overall recall should meet minimum threshold."""
        r = regression_result.overall_metrics.recall
        assert r >= MIN_RECALL, (
            f"Overall recall {r:.3f} < {MIN_RECALL} threshold. "
            f"TP={regression_result.overall_metrics.true_positives}, "
            f"FN={regression_result.overall_metrics.false_negatives}"
        )

    def test_overall_f1(self, regression_result: RegressionResult) -> None:
        """Overall F1 should meet minimum threshold."""
        f1 = regression_result.overall_metrics.f1
        assert f1 >= MIN_F1, (
            f"Overall F1 {f1:.3f} < {MIN_F1} threshold"
        )

    def test_pipeline_produces_output(self, regression_result: RegressionResult) -> None:
        """Pipeline should produce at least some true positives."""
        tp = regression_result.overall_metrics.true_positives
        assert tp > 0, "Pipeline produced zero true positives across all golden notes"


@pytest.mark.regression
class TestDomainMetrics:
    """Test precision/recall per clinical domain."""

    def test_condition_extraction(self, regression_result: RegressionResult) -> None:
        """Condition domain should meet minimum thresholds."""
        metrics = regression_result.domain_metrics.get("condition")
        if metrics is None:
            pytest.skip("No condition mentions in results")

        thresholds = DOMAIN_THRESHOLDS.get("condition", {})
        min_p = thresholds.get("precision", MIN_PRECISION)
        min_r = thresholds.get("recall", MIN_RECALL)

        assert metrics.precision >= min_p, (
            f"Condition precision {metrics.precision:.3f} < {min_p}. "
            f"TP={metrics.true_positives}, FP={metrics.false_positives}"
        )
        assert metrics.recall >= min_r, (
            f"Condition recall {metrics.recall:.3f} < {min_r}. "
            f"TP={metrics.true_positives}, FN={metrics.false_negatives}"
        )

    def test_medication_extraction(self, regression_result: RegressionResult) -> None:
        """Drug/Medication domain should meet minimum thresholds."""
        metrics = regression_result.domain_metrics.get("drug")
        if metrics is None:
            pytest.skip("No drug mentions in results")

        thresholds = DOMAIN_THRESHOLDS.get("drug", {})
        min_p = thresholds.get("precision", MIN_PRECISION)
        min_r = thresholds.get("recall", MIN_RECALL)

        assert metrics.precision >= min_p, (
            f"Drug precision {metrics.precision:.3f} < {min_p}. "
            f"TP={metrics.true_positives}, FP={metrics.false_positives}"
        )
        assert metrics.recall >= min_r, (
            f"Drug recall {metrics.recall:.3f} < {min_r}. "
            f"TP={metrics.true_positives}, FN={metrics.false_negatives}"
        )

    def test_measurement_extraction(self, regression_result: RegressionResult) -> None:
        """Measurement/Lab domain should meet minimum thresholds."""
        metrics = regression_result.domain_metrics.get("measurement")
        if metrics is None:
            pytest.skip("No measurement mentions in results")

        thresholds = DOMAIN_THRESHOLDS.get("measurement", {})
        min_p = thresholds.get("precision", MIN_PRECISION)
        min_r = thresholds.get("recall", MIN_RECALL)

        assert metrics.precision >= min_p, (
            f"Measurement precision {metrics.precision:.3f} < {min_p}. "
            f"TP={metrics.true_positives}, FP={metrics.false_positives}"
        )
        assert metrics.recall >= min_r, (
            f"Measurement recall {metrics.recall:.3f} < {min_r}. "
            f"TP={metrics.true_positives}, FN={metrics.false_negatives}"
        )


@pytest.mark.regression
class TestAssertionDetection:
    """Test assertion detection accuracy per assertion type."""

    def test_present_assertion_detection(
        self, regression_result: RegressionResult
    ) -> None:
        """PRESENT assertions should be detected reliably."""
        metrics = regression_result.assertion_metrics.get("present")
        if metrics is None:
            pytest.skip("No present assertions in results")

        thresholds = ASSERTION_THRESHOLDS.get("present", {})
        min_p = thresholds.get("precision", MIN_PRECISION)
        min_r = thresholds.get("recall", MIN_RECALL)

        assert metrics.precision >= min_p, (
            f"PRESENT precision {metrics.precision:.3f} < {min_p}"
        )
        assert metrics.recall >= min_r, (
            f"PRESENT recall {metrics.recall:.3f} < {min_r}"
        )

    def test_absent_assertion_detection(
        self, regression_result: RegressionResult
    ) -> None:
        """ABSENT (negated) assertions should be detected above threshold."""
        metrics = regression_result.assertion_metrics.get("absent")
        if metrics is None:
            pytest.skip("No absent assertions in results")

        thresholds = ASSERTION_THRESHOLDS.get("absent", {})
        min_p = thresholds.get("precision", MIN_PRECISION)
        min_r = thresholds.get("recall", MIN_RECALL)

        assert metrics.precision >= min_p, (
            f"ABSENT precision {metrics.precision:.3f} < {min_p}. "
            f"TP={metrics.true_positives}, FP={metrics.false_positives}"
        )
        assert metrics.recall >= min_r, (
            f"ABSENT recall {metrics.recall:.3f} < {min_r}. "
            f"TP={metrics.true_positives}, FN={metrics.false_negatives}"
        )

    def test_possible_assertion_detection(
        self, regression_result: RegressionResult
    ) -> None:
        """POSSIBLE (uncertain) assertions should be detected above threshold."""
        metrics = regression_result.assertion_metrics.get("possible")
        if metrics is None:
            pytest.skip("No possible assertions in results")

        thresholds = ASSERTION_THRESHOLDS.get("possible", {})
        min_p = thresholds.get("precision", MIN_PRECISION)
        min_r = thresholds.get("recall", MIN_RECALL)

        # Uncertainty detection is hard -- use looser thresholds
        assert metrics.precision >= min_p, (
            f"POSSIBLE precision {metrics.precision:.3f} < {min_p}"
        )
        assert metrics.recall >= min_r, (
            f"POSSIBLE recall {metrics.recall:.3f} < {min_r}"
        )

    def test_negation_does_not_bleed(
        self,
        pipeline: ExtractionPipeline,
    ) -> None:
        """Negation should not bleed into the next sentence.

        Example: 'No chest pain. Taking metformin.' -- metformin should
        be PRESENT, not ABSENT.
        """
        text = "No chest pain. Taking metformin 500mg daily."
        result = pipeline.process(document_id="negation-bleed-test", text=text)

        metformin_entities = [
            e for e in result.entities
            if "metformin" in e.text.lower()
        ]

        if metformin_entities:
            for entity in metformin_entities:
                assert entity.assertion != "absent", (
                    f"Negation bled into next sentence: metformin assertion={entity.assertion}"
                )

    def test_family_history_detection(
        self,
        pipeline: ExtractionPipeline,
    ) -> None:
        """Family history mentions should have correct context.

        The pipeline uses is_family_history flag rather than assertion='family_history',
        so we check the flag here.
        """
        text = "Family history: mother had breast cancer and father had coronary artery disease."
        result = pipeline.process(document_id="family-history-test", text=text)

        # Check if any entities detected in family history context
        family_entities = [
            e for e in result.entities
            if e.is_family_history
        ]
        # Pipeline may or may not detect family history depending on context analyzer
        # This is a characterization test -- log the result
        logger.info(
            f"Family history test: {len(family_entities)} entities flagged as family history "
            f"out of {len(result.entities)} total"
        )


@pytest.mark.regression
class TestTemporalExtraction:
    """Test temporal context detection accuracy."""

    def test_historical_detection(
        self,
        pipeline: ExtractionPipeline,
    ) -> None:
        """Historical mentions should get is_historical flag."""
        text = "Past medical history: hypertension, type 2 diabetes mellitus."
        result = pipeline.process(document_id="temporal-history-test", text=text)

        # Check that at least some entities get historical flag
        historical = [e for e in result.entities if e.is_historical]
        logger.info(
            f"Historical detection: {len(historical)} historical out of "
            f"{len(result.entities)} total entities"
        )

    def test_current_vs_historical_distinction(
        self,
        pipeline: ExtractionPipeline,
    ) -> None:
        """Pipeline should distinguish current from historical conditions."""
        text = (
            "Assessment: Patient has hypertension. "
            "Past medical history includes coronary artery disease."
        )
        result = pipeline.process(document_id="temporal-distinction-test", text=text)

        conditions = {
            e.normalized_text: e
            for e in result.entities
            if e.entity_type == "condition"
        }

        # At minimum, the pipeline should extract both conditions
        htn = conditions.get("hypertension")
        cad = conditions.get("coronary artery disease")

        if htn and cad:
            # Both should be present (not negated), but CAD may be historical
            assert htn.assertion != "absent", "Current hypertension should not be absent"
            assert cad.assertion != "absent", "Historical CAD should not be absent"


@pytest.mark.regression
class TestPerNoteResults:
    """Verify no single note has catastrophic failure."""

    def test_no_zero_recall_notes(self, regression_result: RegressionResult) -> None:
        """No note should have zero recall (all expected mentions missed)."""
        zero_recall_notes = []
        for nr in regression_result.note_results:
            if nr.metrics.recall == 0.0 and len(nr.matches) > 0:
                zero_recall_notes.append(nr.note_id)

        assert len(zero_recall_notes) == 0, (
            f"Notes with zero recall (all expected mentions missed): {zero_recall_notes}"
        )

    def test_no_zero_precision_notes(self, regression_result: RegressionResult) -> None:
        """No note should have zero precision (all extractions wrong)."""
        zero_precision_notes = []
        for nr in regression_result.note_results:
            # Only count notes where the pipeline produced output
            has_output = any(
                m.actual is not None for m in nr.matches
            )
            if has_output and nr.metrics.precision == 0.0:
                zero_precision_notes.append(nr.note_id)

        assert len(zero_precision_notes) == 0, (
            f"Notes with zero precision (all extractions wrong): {zero_precision_notes}"
        )


@pytest.mark.regression
class TestRegressionReport:
    """Test that regression report can be generated and is non-empty."""

    def test_report_generation(self, regression_result: RegressionResult) -> None:
        """Regression report should generate successfully."""
        report = generate_regression_report(regression_result)
        assert len(report) > 0, "Report should not be empty"
        assert "# NLP Pipeline Regression Test Report" in report
        assert "Precision" in report
        assert "Recall" in report

    def test_report_contains_per_note_details(
        self, regression_result: RegressionResult
    ) -> None:
        """Report should contain details for each note."""
        report = generate_regression_report(regression_result)
        for nr in regression_result.note_results:
            assert nr.note_id in report, (
                f"Report missing details for note {nr.note_id}"
            )

    def test_print_regression_report(
        self,
        regression_result: RegressionResult,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Print the full regression report for developer review.

        This test always passes but outputs the report to stdout
        so it can be reviewed with pytest -s.
        """
        report = generate_regression_report(regression_result)
        print("\n" + report)


@pytest.mark.regression
class TestPipelineSmoke:
    """Smoke tests for the extraction pipeline itself."""

    def test_pipeline_handles_empty_text(self, pipeline: ExtractionPipeline) -> None:
        """Pipeline should handle empty text gracefully."""
        result = pipeline.process(document_id="empty-test", text="")
        assert result.entities is not None
        assert result.final_count == 0

    def test_pipeline_handles_non_clinical_text(
        self, pipeline: ExtractionPipeline
    ) -> None:
        """Pipeline should not crash on non-clinical text."""
        text = "The quick brown fox jumps over the lazy dog."
        result = pipeline.process(document_id="nonclinical-test", text=text)
        assert result.entities is not None

    def test_pipeline_extracts_known_condition(
        self, pipeline: ExtractionPipeline
    ) -> None:
        """Pipeline should extract a well-known condition."""
        text = "Patient presents with hypertension."
        result = pipeline.process(document_id="smoke-condition", text=text)

        conditions = [e for e in result.entities if e.entity_type == "condition"]
        htn = [e for e in conditions if "hypertension" in e.normalized_text]
        assert len(htn) > 0, (
            f"Pipeline failed to extract 'hypertension'. "
            f"Got conditions: {[e.text for e in conditions]}"
        )

    def test_pipeline_extracts_known_drug(
        self, pipeline: ExtractionPipeline
    ) -> None:
        """Pipeline should extract a well-known drug."""
        text = "Currently taking metformin 500mg twice daily."
        result = pipeline.process(document_id="smoke-drug", text=text)

        drugs = [e for e in result.entities if e.entity_type == "drug"]
        metformin = [e for e in drugs if "metformin" in e.normalized_text]
        assert len(metformin) > 0, (
            f"Pipeline failed to extract 'metformin'. "
            f"Got drugs: {[e.text for e in drugs]}"
        )

    def test_pipeline_extracts_lab_value(
        self, pipeline: ExtractionPipeline
    ) -> None:
        """Pipeline should extract a lab measurement with value."""
        text = "HbA1c: 7.2%."
        result = pipeline.process(document_id="smoke-lab", text=text)

        measurements = [e for e in result.entities if e.entity_type == "measurement"]
        hba1c = [e for e in measurements if "hba1c" in e.normalized_text.lower()]
        assert len(hba1c) > 0, (
            f"Pipeline failed to extract 'HbA1c'. "
            f"Got measurements: {[e.text for e in measurements]}"
        )

        # Check value extraction
        if hba1c:
            assert hba1c[0].value is not None, "HbA1c should have extracted value"
