"""UMLS/OMOP precision guardrail tests for OMOPHierarchyService fallback matching.

ROL-08 / P2-008: Regression suite verifying that the strict-mode string-fallback
path in OMOPHierarchyService correctly rejects clinically dangerous near-matches
and accepts only exact matches when Neo4j is unavailable.

All tests are pure-Python unit tests with no external dependencies.
"""

import pytest

from app.services.omop_hierarchy_service import OMOPHierarchyService

from tests.fixtures.omop_guardrail_corpus import (
    HIERARCHY_FALSE_POSITIVE_PAIRS,
    HIERARCHY_MUST_ACCEPT_PAIRS,
    SIMILARITY_BOUNDARY_CASES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(*, strict: bool = True) -> OMOPHierarchyService:
    """Create a fresh service instance (no DB, no Neo4j)."""
    return OMOPHierarchyService(strict_matching_mode=strict)


# ---------------------------------------------------------------------------
# 1. TestComputeStringSimilarity
# ---------------------------------------------------------------------------

class TestComputeStringSimilarity:
    """Validate the static Jaccard bigram similarity computation."""

    def test_identical_strings(self) -> None:
        score = OMOPHierarchyService._compute_string_similarity("metformin", "metformin")
        assert score == 1.0

    def test_empty_first_string(self) -> None:
        score = OMOPHierarchyService._compute_string_similarity("", "metformin")
        assert score == 0.0

    def test_empty_second_string(self) -> None:
        score = OMOPHierarchyService._compute_string_similarity("metformin", "")
        assert score == 0.0

    def test_both_empty(self) -> None:
        score = OMOPHierarchyService._compute_string_similarity("", "")
        assert score == 0.0

    def test_single_char_same(self) -> None:
        score = OMOPHierarchyService._compute_string_similarity("a", "a")
        assert score == 1.0

    def test_single_char_different(self) -> None:
        score = OMOPHierarchyService._compute_string_similarity("a", "b")
        assert score == 0.0

    def test_dangerous_drug_pair_below_threshold(self) -> None:
        """metformin vs metronidazole must score well below 0.85."""
        score = OMOPHierarchyService._compute_string_similarity("metformin", "metronidazole")
        assert score < 0.85, f"Dangerous pair scored {score:.3f} — must be below 0.85"


# ---------------------------------------------------------------------------
# 2. TestStringFallbackMatchStrict
# ---------------------------------------------------------------------------

class TestStringFallbackMatchStrict:
    """Strict-mode fallback: reject all false positives, accept exact matches."""

    def setup_method(self) -> None:
        self.svc = _make_service(strict=True)

    # --- False-positive rejection (each corpus pair) ---

    @pytest.mark.parametrize(
        "patient, target, reason",
        HIERARCHY_FALSE_POSITIVE_PAIRS,
        ids=[f"{p}-vs-{t}" for p, t, _ in HIERARCHY_FALSE_POSITIVE_PAIRS],
    )
    def test_rejects_false_positive(self, patient: str, target: str, reason: str) -> None:
        result = self.svc._string_fallback_match(patient, target)
        assert not result.matched, (
            f"Strict mode accepted dangerous pair: '{patient}' vs '{target}' — {reason}"
        )

    # --- Exact match acceptance ---

    @pytest.mark.parametrize(
        "patient, target, reason",
        HIERARCHY_MUST_ACCEPT_PAIRS,
        ids=[f"exact-{p}" for p, _, _ in HIERARCHY_MUST_ACCEPT_PAIRS],
    )
    def test_accepts_exact_match(self, patient: str, target: str, reason: str) -> None:
        result = self.svc._string_fallback_match(patient, target)
        assert result.matched, (
            f"Strict mode rejected exact match: '{patient}' vs '{target}' — {reason}"
        )
        assert result.match_type == "exact"
        assert result.match_quality == "exact"

    def test_exact_match_case_insensitive(self) -> None:
        result = self.svc._string_fallback_match("Pneumonia", "pneumonia")
        assert result.matched
        assert result.match_type == "exact"

    def test_strict_mode_flag_is_set(self) -> None:
        assert self.svc.strict_matching_mode is True

    def test_min_fallback_similarity_is_085(self) -> None:
        assert self.svc._min_fallback_similarity == 0.85


# ---------------------------------------------------------------------------
# 3. TestStringFallbackMatchNonStrict
# ---------------------------------------------------------------------------

class TestStringFallbackMatchNonStrict:
    """Non-strict mode: permits substring/word-overlap matches."""

    def setup_method(self) -> None:
        self.svc = _make_service(strict=False)

    def test_substring_match_accepted(self) -> None:
        """Non-strict mode accepts substring containment."""
        result = self.svc._string_fallback_match("chronic kidney disease", "kidney disease")
        assert result.matched
        assert result.match_type == "substring"

    def test_word_overlap_accepted(self) -> None:
        """Non-strict mode accepts word overlap when words > 3 chars."""
        result = self.svc._string_fallback_match("chest pain", "chest tube")
        assert result.matched
        assert result.match_type == "word_overlap"

    def test_exact_match_still_works(self) -> None:
        result = self.svc._string_fallback_match("pneumonia", "pneumonia")
        assert result.matched
        assert result.match_type == "exact"

    def test_no_overlap_rejected(self) -> None:
        """Even non-strict mode rejects completely unrelated terms."""
        result = self.svc._string_fallback_match("aspirin", "colonoscopy")
        assert not result.matched


# ---------------------------------------------------------------------------
# 4. TestPrecisionGuardrailCorpus
# ---------------------------------------------------------------------------

class TestPrecisionGuardrailCorpus:
    """Sweep all corpus sections and enforce minimum corpus sizes."""

    def setup_method(self) -> None:
        self.svc = _make_service(strict=True)

    def test_false_positive_corpus_minimum_size(self) -> None:
        assert len(HIERARCHY_FALSE_POSITIVE_PAIRS) >= 10, (
            "Guardrail corpus must contain at least 10 false-positive pairs"
        )

    def test_must_accept_corpus_minimum_size(self) -> None:
        assert len(HIERARCHY_MUST_ACCEPT_PAIRS) >= 5, (
            "Guardrail corpus must contain at least 5 must-accept pairs"
        )

    def test_all_false_positives_rejected_sweep(self) -> None:
        """Zero-tolerance sweep: every false-positive pair must be rejected."""
        failures: list[str] = []
        for patient, target, reason in HIERARCHY_FALSE_POSITIVE_PAIRS:
            result = self.svc._string_fallback_match(patient, target)
            if result.matched:
                failures.append(f"  '{patient}' vs '{target}': {reason}")
        assert not failures, (
            f"Strict mode accepted {len(failures)} dangerous pair(s):\n"
            + "\n".join(failures)
        )

    def test_similarity_boundary_cases(self) -> None:
        """Verify similarity scores fall within expected ranges."""
        failures: list[str] = []
        for str_a, str_b, min_exp, max_exp, desc in SIMILARITY_BOUNDARY_CASES:
            score = OMOPHierarchyService._compute_string_similarity(
                str_a.lower(), str_b.lower()
            )
            if not (min_exp <= score <= max_exp):
                failures.append(
                    f"  '{str_a}' vs '{str_b}': score={score:.4f}, "
                    f"expected [{min_exp:.2f}, {max_exp:.2f}] — {desc}"
                )
        assert not failures, (
            f"Similarity boundary violations:\n" + "\n".join(failures)
        )


# ---------------------------------------------------------------------------
# 5. TestCheckHierarchyMatchFallback
# ---------------------------------------------------------------------------

class TestCheckHierarchyMatchFallback:
    """Public API delegates to string fallback when Neo4j is absent."""

    def setup_method(self) -> None:
        # Service with no DB connection — _resolve_concept returns None,
        # so check_hierarchy_match always falls through to _string_fallback_match.
        self.svc = _make_service(strict=True)

    def test_exact_match_via_public_api(self) -> None:
        result = self.svc.check_hierarchy_match("pneumonia", "pneumonia")
        assert result.matched
        assert result.match_type == "exact"

    def test_false_positive_rejected_via_public_api(self) -> None:
        result = self.svc.check_hierarchy_match("metformin", "metronidazole")
        assert not result.matched

    def test_case_insensitive_via_public_api(self) -> None:
        result = self.svc.check_hierarchy_match("Aspirin", "aspirin")
        assert result.matched

    def test_unrelated_terms_rejected_via_public_api(self) -> None:
        result = self.svc.check_hierarchy_match("lisinopril", "colonoscopy")
        assert not result.matched
