"""Utility functions for NLP pipeline regression testing (CTO-3).

Provides:
- Golden dataset loading and validation
- Mention comparison with fuzzy matching
- Precision/recall/F1 metric calculation
- Regression report generation in markdown format
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExpectedMention:
    """An expected mention from the golden dataset."""

    text: str
    domain: str
    assertion: str
    concept_name: str


@dataclass
class ActualMention:
    """An actual mention extracted by the NLP pipeline."""

    text: str
    domain: str
    assertion: str
    concept_name: str | None = None
    confidence: float = 1.0
    start_offset: int = 0
    end_offset: int = 0


@dataclass
class MentionMatch:
    """A match (or mismatch) between expected and actual mentions."""

    expected: ExpectedMention | None
    actual: ActualMention | None
    match_type: str  # "exact", "partial", "domain_mismatch", "assertion_mismatch", "false_positive", "false_negative"
    text_similarity: float = 0.0  # 0.0 - 1.0


@dataclass
class MetricResult:
    """Precision, recall, and F1 for a given slice of data."""

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)


@dataclass
class GoldenNote:
    """A single annotated clinical note from the golden dataset."""

    note_id: str
    text: str
    category: str
    description: str
    expected_mentions: list[ExpectedMention]


@dataclass
class NoteResult:
    """Regression test result for a single note."""

    note_id: str
    category: str
    matches: list[MentionMatch]
    metrics: MetricResult


@dataclass
class RegressionResult:
    """Full regression test result across all notes."""

    note_results: list[NoteResult] = field(default_factory=list)
    overall_metrics: MetricResult = field(default_factory=MetricResult)
    domain_metrics: dict[str, MetricResult] = field(default_factory=dict)
    assertion_metrics: dict[str, MetricResult] = field(default_factory=dict)
    category_metrics: dict[str, MetricResult] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Golden dataset loading
# ---------------------------------------------------------------------------

def _get_golden_dataset_path() -> Path:
    """Get the path to the golden dataset JSON file."""
    # Try relative to this test file
    test_dir = Path(__file__).parent
    golden_path = test_dir / "golden_data" / "clinical_notes.json"
    if golden_path.exists():
        return golden_path

    # Try from project root
    project_root = Path(__file__).parent.parent.parent
    golden_path = project_root / "backend" / "tests" / "golden_data" / "clinical_notes.json"
    if golden_path.exists():
        return golden_path

    raise FileNotFoundError(
        f"Golden dataset not found. Looked in:\n"
        f"  - {test_dir / 'golden_data' / 'clinical_notes.json'}\n"
        f"  - {project_root / 'backend' / 'tests' / 'golden_data' / 'clinical_notes.json'}"
    )


def load_golden_dataset() -> list[GoldenNote]:
    """Load and validate the golden dataset from JSON.

    Returns:
        List of GoldenNote objects with expected mentions.

    Raises:
        FileNotFoundError: If golden dataset file is not found.
        ValueError: If the dataset fails validation.
    """
    path = _get_golden_dataset_path()

    with open(path) as f:
        data = json.load(f)

    # Validate top-level structure
    if "notes" not in data:
        raise ValueError("Golden dataset missing 'notes' key")

    notes: list[GoldenNote] = []

    for i, note_data in enumerate(data["notes"]):
        # Validate required fields
        required_fields = ["note_id", "text", "category", "expected_mentions"]
        for req in required_fields:
            if req not in note_data:
                raise ValueError(f"Note at index {i} missing required field '{req}'")

        # Parse expected mentions
        expected_mentions = []
        for j, em_data in enumerate(note_data["expected_mentions"]):
            mention_required = ["text", "domain", "assertion"]
            for req in mention_required:
                if req not in em_data:
                    raise ValueError(
                        f"Note '{note_data['note_id']}' mention at index {j} "
                        f"missing required field '{req}'"
                    )

            expected_mentions.append(
                ExpectedMention(
                    text=em_data["text"],
                    domain=em_data["domain"],
                    assertion=em_data["assertion"],
                    concept_name=em_data.get("concept_name", ""),
                )
            )

        notes.append(
            GoldenNote(
                note_id=note_data["note_id"],
                text=note_data["text"],
                category=note_data.get("category", "general"),
                description=note_data.get("description", ""),
                expected_mentions=expected_mentions,
            )
        )

    return notes


# ---------------------------------------------------------------------------
# Fuzzy text matching
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    return text.lower().strip()


def _text_overlap_ratio(text_a: str, text_b: str) -> float:
    """Calculate bidirectional overlap ratio between two texts.

    Uses both substring containment and token overlap for robustness.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    a = _normalize_text(text_a)
    b = _normalize_text(text_b)

    if a == b:
        return 1.0

    # Check substring containment (one contains the other)
    if a in b:
        return len(a) / len(b)
    if b in a:
        return len(b) / len(a)

    # Token-level overlap (Jaccard similarity)
    tokens_a = set(a.split())
    tokens_b = set(b.split())

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Mention comparison
# ---------------------------------------------------------------------------

# Domain normalization mapping (pipeline uses lowercase entity_type names)
_DOMAIN_NORMALIZATION: dict[str, str] = {
    # From golden dataset
    "CONDITION": "condition",
    "MEDICATION": "drug",
    "PROCEDURE": "procedure",
    "OBSERVATION": "observation",
    "LAB": "measurement",
    # From pipeline (already normalized)
    "condition": "condition",
    "drug": "drug",
    "measurement": "measurement",
    "procedure": "procedure",
    "observation": "observation",
    # OMOP domain_id values
    "Condition": "condition",
    "Drug": "drug",
    "Measurement": "measurement",
    "Procedure": "procedure",
    "Observation": "observation",
}

# Assertion normalization mapping
_ASSERTION_NORMALIZATION: dict[str, str] = {
    # From golden dataset
    "PRESENT": "present",
    "ABSENT": "absent",
    "HYPOTHETICAL": "hypothetical",
    "FAMILY_HISTORY": "family_history",
    "POSSIBLE": "possible",
    # From pipeline assertion field
    "present": "present",
    "absent": "absent",
    "possible": "possible",
    "hypothetical": "hypothetical",
    "family_history": "family_history",
    "conditional": "hypothetical",
    "historical": "present",  # historical is still present, just past
    # From clinical_context module Assertion values
    "uncertain": "possible",
    "family": "family_history",
}


def _normalize_domain(domain: str) -> str:
    """Normalize domain strings for comparison."""
    return _DOMAIN_NORMALIZATION.get(domain, domain.lower())


def _normalize_assertion(assertion: str) -> str:
    """Normalize assertion strings for comparison."""
    return _ASSERTION_NORMALIZATION.get(assertion, assertion.lower())


def compare_mentions(
    expected: list[ExpectedMention],
    actual: list[ActualMention],
    text_threshold: float = 0.5,
) -> list[MentionMatch]:
    """Compare expected mentions against actual extracted mentions.

    Uses fuzzy text matching to allow partial span overlap. Attempts
    to find the best overall matching between expected and actual mentions
    using a greedy approach (best match first).

    Args:
        expected: Expected mentions from golden dataset.
        actual: Actual mentions from NLP pipeline.
        text_threshold: Minimum text similarity for a match (0.0 - 1.0).

    Returns:
        List of MentionMatch objects describing each match or mismatch.
    """
    matches: list[MentionMatch] = []

    # Build similarity matrix
    scored_pairs: list[tuple[float, int, int, str]] = []

    for i, exp in enumerate(expected):
        for j, act in enumerate(actual):
            text_sim = _text_overlap_ratio(exp.text, act.text)

            if text_sim < text_threshold:
                continue

            norm_exp_domain = _normalize_domain(exp.domain)
            norm_act_domain = _normalize_domain(act.domain)
            norm_exp_assertion = _normalize_assertion(exp.assertion)
            norm_act_assertion = _normalize_assertion(act.assertion)

            # Determine match type
            domain_match = norm_exp_domain == norm_act_domain
            assertion_match = norm_exp_assertion == norm_act_assertion

            if text_sim >= 0.8 and domain_match and assertion_match:
                match_type = "exact"
                score = text_sim * 1.0
            elif text_sim >= text_threshold and domain_match and assertion_match:
                match_type = "partial"
                score = text_sim * 0.9
            elif text_sim >= text_threshold and domain_match:
                match_type = "assertion_mismatch"
                score = text_sim * 0.5
            elif text_sim >= text_threshold and assertion_match:
                match_type = "domain_mismatch"
                score = text_sim * 0.5
            else:
                match_type = "partial"
                score = text_sim * 0.3

            scored_pairs.append((score, i, j, match_type))

    # Greedy matching: best score first
    scored_pairs.sort(key=lambda x: x[0], reverse=True)

    matched_expected: set[int] = set()
    matched_actual: set[int] = set()

    for score, i, j, match_type in scored_pairs:
        if i in matched_expected or j in matched_actual:
            continue

        text_sim = _text_overlap_ratio(expected[i].text, actual[j].text)

        matches.append(
            MentionMatch(
                expected=expected[i],
                actual=actual[j],
                match_type=match_type,
                text_similarity=text_sim,
            )
        )
        matched_expected.add(i)
        matched_actual.add(j)

    # False negatives (expected but not found)
    for i, exp in enumerate(expected):
        if i not in matched_expected:
            matches.append(
                MentionMatch(
                    expected=exp,
                    actual=None,
                    match_type="false_negative",
                    text_similarity=0.0,
                )
            )

    # False positives (found but not expected)
    for j, act in enumerate(actual):
        if j not in matched_actual:
            matches.append(
                MentionMatch(
                    expected=None,
                    actual=act,
                    match_type="false_positive",
                    text_similarity=0.0,
                )
            )

    return matches


# ---------------------------------------------------------------------------
# Metrics calculation
# ---------------------------------------------------------------------------

def calculate_mention_metrics(matches: list[MentionMatch]) -> MetricResult:
    """Calculate precision, recall, and F1 from match results.

    True positives: exact or partial matches (text + domain + assertion all match)
    False positives: actual mentions with no matching expected mention
    False negatives: expected mentions with no matching actual mention

    Args:
        matches: List of MentionMatch from compare_mentions().

    Returns:
        MetricResult with TP, FP, FN counts and derived precision/recall/F1.
    """
    result = MetricResult()

    for match in matches:
        if match.match_type in ("exact", "partial"):
            result.true_positives += 1
        elif match.match_type == "false_positive":
            result.false_positives += 1
        elif match.match_type == "false_negative":
            result.false_negatives += 1
        elif match.match_type in ("assertion_mismatch", "domain_mismatch"):
            # Count as partial TP for overall, but note the mismatch
            # For strict metrics, we count assertion/domain mismatches as errors
            result.false_positives += 1
            result.false_negatives += 1

    return result


def calculate_metrics_by_slice(
    all_matches: list[MentionMatch],
    slice_fn: Any,
) -> dict[str, MetricResult]:
    """Calculate metrics grouped by a slicing function.

    Args:
        all_matches: All mention matches across notes.
        slice_fn: Function that takes a MentionMatch and returns a string key
                  (e.g., domain or assertion type).

    Returns:
        Dict mapping slice key to MetricResult.
    """
    grouped: dict[str, list[MentionMatch]] = defaultdict(list)

    for match in all_matches:
        key = slice_fn(match)
        if key is not None:
            grouped[key].append(match)

    return {key: calculate_mention_metrics(matches) for key, matches in grouped.items()}


def _domain_slice(match: MentionMatch) -> str | None:
    """Slice by domain."""
    if match.expected:
        return _normalize_domain(match.expected.domain)
    if match.actual:
        return _normalize_domain(match.actual.domain)
    return None


def _assertion_slice(match: MentionMatch) -> str | None:
    """Slice by assertion."""
    if match.expected:
        return _normalize_assertion(match.expected.assertion)
    if match.actual:
        return _normalize_assertion(match.actual.assertion)
    return None


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_regression_report(result: RegressionResult) -> str:
    """Generate a markdown regression report.

    Args:
        result: Full regression result from test run.

    Returns:
        Markdown-formatted report string.
    """
    lines: list[str] = []

    lines.append("# NLP Pipeline Regression Test Report")
    lines.append("")

    # Overall metrics
    m = result.overall_metrics
    lines.append("## Overall Metrics")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Precision | {m.precision:.3f} |")
    lines.append(f"| Recall | {m.recall:.3f} |")
    lines.append(f"| F1 Score | {m.f1:.3f} |")
    lines.append(f"| True Positives | {m.true_positives} |")
    lines.append(f"| False Positives | {m.false_positives} |")
    lines.append(f"| False Negatives | {m.false_negatives} |")
    lines.append("")

    # Domain breakdown
    if result.domain_metrics:
        lines.append("## Metrics by Domain")
        lines.append("")
        lines.append("| Domain | Precision | Recall | F1 | TP | FP | FN |")
        lines.append("|--------|-----------|--------|----|----|----|----|")
        for domain, dm in sorted(result.domain_metrics.items()):
            lines.append(
                f"| {domain} | {dm.precision:.3f} | {dm.recall:.3f} | "
                f"{dm.f1:.3f} | {dm.true_positives} | {dm.false_positives} | "
                f"{dm.false_negatives} |"
            )
        lines.append("")

    # Assertion breakdown
    if result.assertion_metrics:
        lines.append("## Metrics by Assertion Type")
        lines.append("")
        lines.append("| Assertion | Precision | Recall | F1 | TP | FP | FN |")
        lines.append("|-----------|-----------|--------|----|----|----|----|")
        for assertion, am in sorted(result.assertion_metrics.items()):
            lines.append(
                f"| {assertion} | {am.precision:.3f} | {am.recall:.3f} | "
                f"{am.f1:.3f} | {am.true_positives} | {am.false_positives} | "
                f"{am.false_negatives} |"
            )
        lines.append("")

    # Category breakdown
    if result.category_metrics:
        lines.append("## Metrics by Clinical Category")
        lines.append("")
        lines.append("| Category | Precision | Recall | F1 | TP | FP | FN |")
        lines.append("|----------|-----------|--------|----|----|----|----|")
        for cat, cm in sorted(result.category_metrics.items()):
            lines.append(
                f"| {cat} | {cm.precision:.3f} | {cm.recall:.3f} | "
                f"{cm.f1:.3f} | {cm.true_positives} | {cm.false_positives} | "
                f"{cm.false_negatives} |"
            )
        lines.append("")

    # Per-note detail
    lines.append("## Per-Note Details")
    lines.append("")

    for nr in result.note_results:
        lines.append(f"### {nr.note_id} ({nr.category})")
        lines.append("")
        lines.append(
            f"P={nr.metrics.precision:.2f} R={nr.metrics.recall:.2f} "
            f"F1={nr.metrics.f1:.2f} "
            f"(TP={nr.metrics.true_positives}, FP={nr.metrics.false_positives}, "
            f"FN={nr.metrics.false_negatives})"
        )
        lines.append("")

        # Show mismatches
        mismatches = [m for m in nr.matches if m.match_type not in ("exact", "partial")]
        if mismatches:
            lines.append("**Mismatches:**")
            lines.append("")
            for mm in mismatches:
                if mm.match_type == "false_negative":
                    lines.append(
                        f"- MISSED: `{mm.expected.text}` "
                        f"(domain={mm.expected.domain}, assertion={mm.expected.assertion})"
                    )
                elif mm.match_type == "false_positive":
                    lines.append(
                        f"- EXTRA: `{mm.actual.text}` "
                        f"(domain={mm.actual.domain}, assertion={mm.actual.assertion})"
                    )
                elif mm.match_type == "assertion_mismatch":
                    lines.append(
                        f"- ASSERTION MISMATCH: `{mm.expected.text}` "
                        f"expected={mm.expected.assertion}, "
                        f"got={mm.actual.assertion}"
                    )
                elif mm.match_type == "domain_mismatch":
                    lines.append(
                        f"- DOMAIN MISMATCH: `{mm.expected.text}` "
                        f"expected={mm.expected.domain}, "
                        f"got={mm.actual.domain}"
                    )
            lines.append("")

    return "\n".join(lines)
