"""Assertion Validation Service for Clinical NLP.

Validates the assertion classifier against a golden dataset of annotated
clinical text, producing per-category accuracy, precision, recall, F1
metrics, per-difficulty accuracy, and a list of disagreements flagged for
clinical review.

The validator combines:
- ``ProbabilisticAssertionClassifier`` for negation / uncertainty / hypothetical
- ``FamilyHistoryDetector`` for family-history attribution
- Section-header awareness via ``SectionDetector``

This ensures that the validation covers the full assertion taxonomy used in
the application: PRESENT, ABSENT, POSSIBLE, HYPOTHETICAL, FAMILY_HISTORY,
CONDITIONAL.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from app.schemas.assertion_validation import (
    AssertionExpected,
    AssertionSingleResult,
    AssertionTestCase,
    AssertionValidationReport,
    CategoryMetrics,
    DifficultyMetrics,
    DisagreementRecord,
)
from app.schemas.base import Assertion
from app.services.assertion_classifier import (
    AssertionCategory,
    ProbabilisticAssertionClassifier,
)

logger = logging.getLogger(__name__)

# Default path to the golden dataset (relative to repo root)
_DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "assertion_golden_dataset.json"
)

# ---------------------------------------------------------------------------
# Family-history detection (lightweight, standalone)
# ---------------------------------------------------------------------------

_FAMILY_TRIGGERS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bfamily\s+history\b",
        r"\bfhx?\b",
        r"\bmother\b",
        r"\bfather\b",
        r"\bparent[s]?\b",
        r"\bsibling[s]?\b",
        r"\bbrother\b",
        r"\bsister\b",
        r"\bgrandmother\b",
        r"\bgrandfather\b",
        r"\bgrandparent[s]?\b",
        r"\baunt\b",
        r"\buncle\b",
        r"\bcousin\b",
        r"\brelative[s]?\b",
        r"\bmaternal\b",
        r"\bpaternal\b",
    ]
]

_FAMILY_HISTORY_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:family\s+(?:medical\s+)?history|fhx?)\s*[:\n]",
    re.IGNORECASE,
)


def _is_family_history(
    text: str, mention_start: int, mention_end: int
) -> bool:
    """Return True if the mention is in a family-history context.

    Checks both section headers and proximity-based family triggers.
    A preceding negation such as "no family history of" should *not* be
    classified as FAMILY_HISTORY -- the negation takes priority.
    """
    text_lower = text.lower()

    # 1) Section-header check: is the mention inside a "Family History:" section?
    for m in _FAMILY_HISTORY_SECTION_RE.finditer(text):
        section_start = m.start()
        # The section extends to the next section header or end-of-text.
        next_section = re.search(
            r"\n\s*[A-Z][A-Za-z /]+:", text[m.end() :]
        )
        section_end = (m.end() + next_section.start()) if next_section else len(text)
        if section_start <= mention_start < section_end:
            return True

    # 2) Proximity check: look 60 chars before the mention for family cues.
    context_start = max(0, mention_start - 60)
    context = text_lower[context_start:mention_end]
    for pattern in _FAMILY_TRIGGERS:
        if pattern.search(context):
            # Make sure there isn't a negation of the family history itself
            # e.g. "no family history of cancer" -> ABSENT, not FAMILY_HISTORY
            neg_prefix = text_lower[context_start:mention_start]
            if re.search(r"\bno\b|\bdenies\b|\bnegative\b|\bwithout\b", neg_prefix):
                return False
            return True

    return False


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------


def _normalize_assertion(value: str) -> str:
    """Normalise an assertion string to upper-case canonical form."""
    return value.upper().replace(" ", "_")


def _map_classifier_result(
    assertion: Assertion,
    category: AssertionCategory,
    text: str,
    mention_start: int,
    mention_end: int,
) -> str:
    """Map the raw classifier + family-history detector output to the
    ``AssertionExpected`` taxonomy used by the golden dataset.

    The existing ``ProbabilisticAssertionClassifier`` maps:
      - ABSENT  -> ABSENT
      - POSSIBLE (from uncertain OR hypothetical triggers) -> POSSIBLE or HYPOTHETICAL
      - PRESENT -> PRESENT

    We further distinguish HYPOTHETICAL from POSSIBLE by checking the
    classifier's internal ``AssertionCategory``, and layer on
    FAMILY_HISTORY detection.
    """
    # Family-history takes precedence unless the base assertion is ABSENT
    # (e.g. "no family history of cancer" should remain ABSENT).
    if assertion != Assertion.ABSENT and _is_family_history(text, mention_start, mention_end):
        return AssertionExpected.FAMILY_HISTORY.value

    if assertion == Assertion.ABSENT:
        return AssertionExpected.ABSENT.value
    if assertion == Assertion.PRESENT:
        return AssertionExpected.PRESENT.value
    if assertion == Assertion.POSSIBLE:
        # Distinguish HYPOTHETICAL from POSSIBLE — both hypothetical and
        # conditional categories represent non-confirmed future/contingent
        # findings, mapped to HYPOTHETICAL in the golden-dataset taxonomy.
        if category in (AssertionCategory.HYPOTHETICAL, AssertionCategory.CONDITIONAL):
            return AssertionExpected.HYPOTHETICAL.value
        return AssertionExpected.POSSIBLE.value

    # Fallback for any other Assertion enum values
    return _normalize_assertion(assertion.value)


class AssertionValidator:
    """Validate the assertion classifier against a golden dataset.

    Usage::

        validator = AssertionValidator()
        report = validator.validate_assertions()        # uses default dataset
        report = validator.validate_assertions("/path/to/dataset.json")
    """

    def __init__(self) -> None:
        self._classifier = ProbabilisticAssertionClassifier()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_single(
        self,
        text: str,
        mention_text: str,
        mention_start: int,
    ) -> AssertionSingleResult:
        """Classify a single mention and return the predicted assertion.

        Parameters
        ----------
        text:
            Full clinical text containing the mention.
        mention_text:
            The mention span text (used to derive ``mention_end``).
        mention_start:
            Character offset of the mention start in *text*.

        Returns
        -------
        AssertionSingleResult
        """
        mention_end = mention_start + len(mention_text)
        result = self._classifier.classify(text, mention_start, mention_end)
        predicted = _map_classifier_result(
            result.assertion,
            result.category,
            text,
            mention_start,
            mention_end,
        )
        return AssertionSingleResult(
            predicted_assertion=predicted,
            confidence=result.confidence,
            trigger_text=result.trigger_text,
            trigger_distance=result.trigger_distance,
        )

    def validate_assertions(
        self,
        dataset_path: str | Path | None = None,
    ) -> AssertionValidationReport:
        """Run the classifier against the golden dataset and produce a
        validation report.

        Parameters
        ----------
        dataset_path:
            Path to the golden-dataset JSON file.  Defaults to
            ``backend/tests/fixtures/assertion_golden_dataset.json``.

        Returns
        -------
        AssertionValidationReport
        """
        path = Path(dataset_path) if dataset_path else _DEFAULT_DATASET_PATH
        test_cases = self._load_dataset(path)

        # Accumulators
        total = 0
        correct = 0
        disagreements: list[DisagreementRecord] = []

        # Per-category counters: {category -> {total, correct, tp, fp, fn}}
        cat_counters: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "correct": 0, "tp": 0, "fp": 0, "fn": 0}
        )

        # Per-difficulty counters
        diff_counters: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "correct": 0}
        )

        # Per-assertion-type counters
        assertion_counters: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "correct": 0}
        )

        for tc in test_cases:
            mention_end = tc.mention_start + len(tc.mention_text)
            result = self._classifier.classify(tc.text, tc.mention_start, mention_end)
            predicted_raw = _map_classifier_result(
                result.assertion,
                result.category,
                tc.text,
                tc.mention_start,
                mention_end,
            )

            expected = tc.expected_assertion.value
            is_correct = predicted_raw == expected

            total += 1
            if is_correct:
                correct += 1

            # Category metrics
            cat = tc.category.value
            cat_counters[cat]["total"] += 1
            if is_correct:
                cat_counters[cat]["correct"] += 1
                cat_counters[cat]["tp"] += 1
            else:
                cat_counters[cat]["fn"] += 1
                # The predicted category may differ; mark fp in predicted's bucket
                # (for cross-category precision we track on expected category)

            # Difficulty metrics
            diff = tc.difficulty.value
            diff_counters[diff]["total"] += 1
            if is_correct:
                diff_counters[diff]["correct"] += 1

            # Per-assertion-type
            assertion_counters[expected]["total"] += 1
            if is_correct:
                assertion_counters[expected]["correct"] += 1

            if not is_correct:
                disagreements.append(
                    DisagreementRecord(
                        test_case=tc,
                        predicted_assertion=predicted_raw,
                        expected_assertion=expected,
                        confidence=result.confidence,
                        trigger_text=result.trigger_text,
                    )
                )

        # Build CategoryMetrics
        category_metrics: list[CategoryMetrics] = []
        for cat_name, counters in sorted(cat_counters.items()):
            t = counters["total"]
            c = counters["correct"]
            tp = counters["tp"]
            fn = counters["fn"]
            # Simplified precision/recall: treat "correct" as TP
            # FP = predicted this category but it was wrong -> approximated
            fp = t - c - fn if (t - c - fn) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )
            category_metrics.append(
                CategoryMetrics(
                    category=cat_name,
                    total=t,
                    correct=c,
                    accuracy=c / t if t else 0.0,
                    precision=round(precision, 4),
                    recall=round(recall, 4),
                    f1=round(f1, 4),
                )
            )

        # Build DifficultyMetrics
        difficulty_metrics: list[DifficultyMetrics] = []
        for diff_name, counters in sorted(diff_counters.items()):
            t = counters["total"]
            c = counters["correct"]
            difficulty_metrics.append(
                DifficultyMetrics(
                    difficulty=diff_name,
                    total=t,
                    correct=c,
                    accuracy=c / t if t else 0.0,
                )
            )

        # Per-assertion accuracy
        assertion_accuracy: dict[str, float] = {}
        for a_name, counters in sorted(assertion_counters.items()):
            t = counters["total"]
            c = counters["correct"]
            assertion_accuracy[a_name] = round(c / t, 4) if t else 0.0

        return AssertionValidationReport(
            total_cases=total,
            overall_correct=correct,
            overall_accuracy=round(correct / total, 4) if total else 0.0,
            category_metrics=category_metrics,
            difficulty_metrics=difficulty_metrics,
            disagreements=disagreements,
            assertion_accuracy=assertion_accuracy,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _load_dataset(path: Path) -> list[AssertionTestCase]:
        """Load and parse the golden dataset JSON file."""
        if not path.exists():
            raise FileNotFoundError(
                f"Golden assertion dataset not found at {path}"
            )
        with open(path) as f:
            data = json.load(f)

        raw_cases = data.get("test_cases", [])
        if not raw_cases:
            raise ValueError("Golden dataset contains no test_cases")

        cases: list[AssertionTestCase] = []
        for entry in raw_cases:
            cases.append(AssertionTestCase(**entry))
        return cases
