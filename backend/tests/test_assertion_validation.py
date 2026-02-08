"""Tests for the assertion validation framework (CMO-1.2).

Validates:
- Golden dataset integrity (loading, size, coverage)
- Per-category accuracy thresholds
- Per-difficulty accuracy
- Validation report generation
- Single-mention validation
- Disagreement tracking
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.assertion_validation import (
    AssertionExpected,
    AssertionTestCase,
    AssertionValidationReport,
    CategoryMetrics,
    DifficultyMetrics,
    DisagreementRecord,
    TestCaseCategory,
    TestCaseDifficulty,
)
from app.services.assertion_validator import AssertionValidator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATASET_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "assertion_golden_dataset.json"
)


@pytest.fixture(scope="module")
def validator() -> AssertionValidator:
    return AssertionValidator()


@pytest.fixture(scope="module")
def report(validator: AssertionValidator) -> AssertionValidationReport:
    return validator.validate_assertions(DATASET_PATH)


@pytest.fixture(scope="module")
def raw_dataset() -> dict:
    with open(DATASET_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Dataset integrity tests
# ---------------------------------------------------------------------------


class TestGoldenDatasetIntegrity:
    """Verify the golden dataset loads correctly and has required coverage."""

    def test_dataset_file_exists(self) -> None:
        assert DATASET_PATH.exists(), f"Dataset not found at {DATASET_PATH}"

    def test_dataset_loads_valid_json(self, raw_dataset: dict) -> None:
        assert "test_cases" in raw_dataset
        assert isinstance(raw_dataset["test_cases"], list)

    def test_dataset_has_100_plus_entries(self, raw_dataset: dict) -> None:
        assert len(raw_dataset["test_cases"]) >= 100, (
            f"Expected >= 100 test cases, got {len(raw_dataset['test_cases'])}"
        )

    def test_all_entries_parse_as_test_cases(self, raw_dataset: dict) -> None:
        for entry in raw_dataset["test_cases"]:
            tc = AssertionTestCase(**entry)
            assert tc.text
            assert tc.mention_text
            assert tc.mention_start >= 0

    def test_mention_offsets_are_valid(self, raw_dataset: dict) -> None:
        """Verify mention_start + len(mention_text) is within text bounds."""
        for entry in raw_dataset["test_cases"]:
            tc = AssertionTestCase(**entry)
            mention_end = tc.mention_start + len(tc.mention_text)
            assert mention_end <= len(tc.text), (
                f"Test case {tc.id}: mention_end {mention_end} > text length {len(tc.text)}"
            )

    def test_mention_text_matches_span(self, raw_dataset: dict) -> None:
        """The text at [mention_start:mention_start+len(mention_text)] must
        match mention_text (case-insensitive)."""
        for entry in raw_dataset["test_cases"]:
            tc = AssertionTestCase(**entry)
            actual = tc.text[tc.mention_start : tc.mention_start + len(tc.mention_text)]
            assert actual.lower() == tc.mention_text.lower(), (
                f"Test case {tc.id}: span '{actual}' != mention_text '{tc.mention_text}'"
            )

    def test_unique_ids(self, raw_dataset: dict) -> None:
        ids = [e["id"] for e in raw_dataset["test_cases"]]
        assert len(ids) == len(set(ids)), "Duplicate test case IDs found"


# ---------------------------------------------------------------------------
# 2. Category coverage tests
# ---------------------------------------------------------------------------


class TestCategoryCoverage:
    """Ensure all required categories are represented."""

    def test_negation_category_present(self, raw_dataset: dict) -> None:
        cats = {e["category"] for e in raw_dataset["test_cases"]}
        assert "negation" in cats

    def test_family_history_category_present(self, raw_dataset: dict) -> None:
        cats = {e["category"] for e in raw_dataset["test_cases"]}
        assert "family_history" in cats

    def test_hypothetical_category_present(self, raw_dataset: dict) -> None:
        cats = {e["category"] for e in raw_dataset["test_cases"]}
        assert "hypothetical" in cats

    def test_uncertainty_category_present(self, raw_dataset: dict) -> None:
        cats = {e["category"] for e in raw_dataset["test_cases"]}
        assert "uncertainty" in cats

    def test_double_negation_category_present(self, raw_dataset: dict) -> None:
        cats = {e["category"] for e in raw_dataset["test_cases"]}
        assert "double_negation" in cats

    def test_section_context_category_present(self, raw_dataset: dict) -> None:
        cats = {e["category"] for e in raw_dataset["test_cases"]}
        assert "section_context" in cats

    def test_temporal_category_present(self, raw_dataset: dict) -> None:
        cats = {e["category"] for e in raw_dataset["test_cases"]}
        assert "temporal" in cats


# ---------------------------------------------------------------------------
# 3. Difficulty coverage tests
# ---------------------------------------------------------------------------


class TestDifficultyCoverage:
    """Ensure all difficulty levels are represented."""

    def test_easy_difficulty_present(self, raw_dataset: dict) -> None:
        diffs = {e["difficulty"] for e in raw_dataset["test_cases"]}
        assert "easy" in diffs

    def test_medium_difficulty_present(self, raw_dataset: dict) -> None:
        diffs = {e["difficulty"] for e in raw_dataset["test_cases"]}
        assert "medium" in diffs

    def test_hard_difficulty_present(self, raw_dataset: dict) -> None:
        diffs = {e["difficulty"] for e in raw_dataset["test_cases"]}
        assert "hard" in diffs


# ---------------------------------------------------------------------------
# 4. Accuracy threshold tests
# ---------------------------------------------------------------------------


class TestAccuracyThresholds:
    """Test that accuracy meets minimum clinical thresholds."""

    def test_overall_accuracy_gte_75(self, report: AssertionValidationReport) -> None:
        assert report.overall_accuracy >= 0.75, (
            f"Overall accuracy {report.overall_accuracy:.2%} < 75%"
        )

    def test_negation_accuracy_gte_90(self, report: AssertionValidationReport) -> None:
        negation = next(
            (m for m in report.category_metrics if m.category == "negation"), None
        )
        assert negation is not None, "No negation category in report"
        assert negation.accuracy >= 0.90, (
            f"Negation accuracy {negation.accuracy:.2%} < 90%"
        )

    def test_family_history_accuracy_gte_85(
        self, report: AssertionValidationReport
    ) -> None:
        fh = next(
            (m for m in report.category_metrics if m.category == "family_history"),
            None,
        )
        assert fh is not None, "No family_history category in report"
        assert fh.accuracy >= 0.85, (
            f"Family history accuracy {fh.accuracy:.2%} < 85%"
        )

    def test_hypothetical_accuracy_gte_80(
        self, report: AssertionValidationReport
    ) -> None:
        hyp = next(
            (m for m in report.category_metrics if m.category == "hypothetical"),
            None,
        )
        assert hyp is not None, "No hypothetical category in report"
        assert hyp.accuracy >= 0.80, (
            f"Hypothetical accuracy {hyp.accuracy:.2%} < 80%"
        )

    def test_uncertainty_accuracy_gte_75(
        self, report: AssertionValidationReport
    ) -> None:
        unc = next(
            (m for m in report.category_metrics if m.category == "uncertainty"),
            None,
        )
        assert unc is not None, "No uncertainty category in report"
        assert unc.accuracy >= 0.75, (
            f"Uncertainty accuracy {unc.accuracy:.2%} < 75%"
        )

    def test_easy_difficulty_accuracy_gte_85(
        self, report: AssertionValidationReport
    ) -> None:
        easy = next(
            (m for m in report.difficulty_metrics if m.difficulty == "easy"), None
        )
        assert easy is not None, "No easy difficulty in report"
        assert easy.accuracy >= 0.85, (
            f"Easy difficulty accuracy {easy.accuracy:.2%} < 85%"
        )


# ---------------------------------------------------------------------------
# 5. Report structure tests
# ---------------------------------------------------------------------------


class TestValidationReport:
    """Test that the validation report is well-formed."""

    def test_report_total_cases_matches_dataset(
        self, report: AssertionValidationReport, raw_dataset: dict
    ) -> None:
        assert report.total_cases == len(raw_dataset["test_cases"])

    def test_report_has_category_metrics(
        self, report: AssertionValidationReport
    ) -> None:
        assert len(report.category_metrics) > 0

    def test_report_has_difficulty_metrics(
        self, report: AssertionValidationReport
    ) -> None:
        assert len(report.difficulty_metrics) > 0

    def test_report_has_assertion_accuracy(
        self, report: AssertionValidationReport
    ) -> None:
        assert len(report.assertion_accuracy) > 0

    def test_report_correct_plus_disagreements_equals_total(
        self, report: AssertionValidationReport
    ) -> None:
        assert report.overall_correct + len(report.disagreements) == report.total_cases

    def test_category_totals_sum_to_total(
        self, report: AssertionValidationReport
    ) -> None:
        cat_total = sum(m.total for m in report.category_metrics)
        assert cat_total == report.total_cases

    def test_difficulty_totals_sum_to_total(
        self, report: AssertionValidationReport
    ) -> None:
        diff_total = sum(m.total for m in report.difficulty_metrics)
        assert diff_total == report.total_cases


# ---------------------------------------------------------------------------
# 6. Single-mention validation
# ---------------------------------------------------------------------------


class TestSingleValidation:
    """Test the validate_single method."""

    def test_simple_negation(self, validator: AssertionValidator) -> None:
        result = validator.validate_single(
            text="Patient denies chest pain.",
            mention_text="chest pain",
            mention_start=15,
        )
        assert result.predicted_assertion == "ABSENT"
        assert result.confidence > 0.0

    def test_present_assertion(self, validator: AssertionValidator) -> None:
        result = validator.validate_single(
            text="Diagnosed with diabetes mellitus.",
            mention_text="diabetes mellitus",
            mention_start=15,
        )
        assert result.predicted_assertion == "PRESENT"

    def test_uncertain_assertion(self, validator: AssertionValidator) -> None:
        result = validator.validate_single(
            text="Possible pneumonia on chest X-ray.",
            mention_text="pneumonia",
            mention_start=9,
        )
        assert result.predicted_assertion == "POSSIBLE"

    def test_family_history_assertion(self, validator: AssertionValidator) -> None:
        result = validator.validate_single(
            text="Mother had breast cancer at age 45.",
            mention_text="breast cancer",
            mention_start=11,
        )
        assert result.predicted_assertion == "FAMILY_HISTORY"
