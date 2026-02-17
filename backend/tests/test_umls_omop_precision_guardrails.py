"""UMLS/OMOP precision guardrail regression tests.

P2-008: Extends P1-010 acceptance tests with:
1. Hierarchy false-positive rejection (dangerous near-matches)
2. Near-miss/ambiguous mappings rejected or downgraded with reason codes
3. Per-domain precision gates (medications 0.90, conditions 0.80, etc.)

Unit tests run without external dependencies.
Integration/regression tests gracefully skip when services are unavailable.
"""

from __future__ import annotations

import os

import pytest

from app.services.omop_hierarchy_service import OMOPHierarchyService

from tests.fixtures.omop_guardrail_corpus import (
    DOMAIN_POSITIVE_PAIRS,
    DOMAIN_PRECISION_THRESHOLDS,
    GUARDRAIL_AMBIGUOUS_PAIRS,
    HIERARCHY_FALSE_POSITIVE_PAIRS,
    HIERARCHY_MUST_ACCEPT_PAIRS,
    SIMILARITY_BOUNDARY_CASES,
    VALID_AMBIGUOUS_ACTIONS,
    VALID_REASON_CODES,
)

# Avoid importing the full acceptance corpus at module level — guard
# against ImportError if the fixture layout changes.
try:
    from tests.fixtures.omop_acceptance_corpus import POSITIVE_PAIRS as ACCEPTANCE_POSITIVE
except ImportError:
    ACCEPTANCE_POSITIVE = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(*, strict: bool = True) -> OMOPHierarchyService:
    """Create a fresh service instance (no DB, no Neo4j)."""
    return OMOPHierarchyService(strict_matching_mode=strict)


def _mock_map_text(input_text: str) -> int | None:
    """Simulate OMOP concept mapping for acceptance testing.

    Returns the mapped OMOP concept ID or None if no mapping found.
    """
    try:
        from app.services.mapping_service import MappingService

        svc = MappingService()
        result = svc.map_text_to_concept(input_text)
        if result and hasattr(result, "concept_id"):
            return result.concept_id
        return None
    except Exception:
        return None


def _mock_map_text_with_quality(input_text: str) -> tuple[int | None, str | None]:
    """Map text and return (concept_id, match_quality).

    Returns (None, None) when mapping service is unavailable.
    """
    try:
        from app.services.mapping_service import MappingService

        svc = MappingService()
        result = svc.map_text_to_concept(input_text)
        if result and hasattr(result, "concept_id"):
            quality = getattr(result, "match_quality", None)
            return result.concept_id, quality
        return None, None
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# 1. TestGuardrailCorpusStructure
# ---------------------------------------------------------------------------

class TestGuardrailCorpusStructure:
    """Validate corpus counts, tuple shapes, valid actions, reason codes,
    and no overlap with the acceptance corpus."""

    def test_ambiguous_pairs_minimum_count(self) -> None:
        assert len(GUARDRAIL_AMBIGUOUS_PAIRS) >= 15, (
            f"Ambiguous pairs must have >= 15 entries, got {len(GUARDRAIL_AMBIGUOUS_PAIRS)}"
        )

    def test_ambiguous_pairs_tuple_shape(self) -> None:
        for pair in GUARDRAIL_AMBIGUOUS_PAIRS:
            assert len(pair) == 4, f"Expected 4-tuple, got {pair}"
            text, concept_id, action, reason = pair
            assert isinstance(text, str) and text.strip(), f"Bad text: {text}"
            assert isinstance(concept_id, int) and concept_id > 0, (
                f"Bad concept_id: {concept_id}"
            )
            assert isinstance(action, str), f"Bad action: {action}"
            assert isinstance(reason, str), f"Bad reason: {reason}"

    def test_ambiguous_pairs_valid_actions(self) -> None:
        for text, _, action, _ in GUARDRAIL_AMBIGUOUS_PAIRS:
            assert action in VALID_AMBIGUOUS_ACTIONS, (
                f"Invalid action '{action}' for '{text}'. "
                f"Valid: {VALID_AMBIGUOUS_ACTIONS}"
            )

    def test_ambiguous_pairs_valid_reason_codes(self) -> None:
        for text, _, _, reason in GUARDRAIL_AMBIGUOUS_PAIRS:
            assert reason in VALID_REASON_CODES, (
                f"Invalid reason code '{reason}' for '{text}'. "
                f"Valid: {VALID_REASON_CODES}"
            )

    def test_domain_pairs_all_domains_present(self) -> None:
        expected_domains = {"medication", "condition", "procedure", "measurement"}
        assert set(DOMAIN_POSITIVE_PAIRS.keys()) == expected_domains, (
            f"Expected domains {expected_domains}, got {set(DOMAIN_POSITIVE_PAIRS.keys())}"
        )

    def test_domain_pairs_total_count(self) -> None:
        total = sum(len(v) for v in DOMAIN_POSITIVE_PAIRS.values())
        assert total >= 30, (
            f"Domain positive pairs must have >= 30 total entries, got {total}"
        )

    def test_domain_pairs_tuple_shape(self) -> None:
        for domain, pairs in DOMAIN_POSITIVE_PAIRS.items():
            for pair in pairs:
                assert len(pair) == 3, (
                    f"Expected 3-tuple in domain '{domain}', got {pair}"
                )
                text, concept_id, name = pair
                assert isinstance(text, str) and text.strip()
                assert isinstance(concept_id, int) and concept_id > 0
                assert isinstance(name, str) and name.strip()

    def test_domain_thresholds_all_domains(self) -> None:
        expected_domains = {"medication", "condition", "procedure", "measurement"}
        assert set(DOMAIN_PRECISION_THRESHOLDS.keys()) == expected_domains

    def test_domain_thresholds_values(self) -> None:
        for domain, threshold in DOMAIN_PRECISION_THRESHOLDS.items():
            assert 0.0 < threshold <= 1.0, (
                f"Threshold for '{domain}' must be in (0, 1], got {threshold}"
            )

    def test_no_overlap_with_acceptance_corpus(self) -> None:
        """Guardrail ambiguous input texts should not duplicate acceptance positive texts."""
        if not ACCEPTANCE_POSITIVE:
            pytest.skip("Acceptance corpus not importable")
        acceptance_texts = {t.lower() for t, _, _ in ACCEPTANCE_POSITIVE}
        ambiguous_texts = {t.lower() for t, _, _, _ in GUARDRAIL_AMBIGUOUS_PAIRS}
        overlap = acceptance_texts & ambiguous_texts
        # Some overlap is acceptable (e.g., same input text tested
        # against different concept IDs), but flag it.
        # The hard requirement is that the *pair* (text, concept_id) differs.
        if overlap:
            for text in overlap:
                acc_ids = {c for t, c, _ in ACCEPTANCE_POSITIVE if t.lower() == text}
                guard_ids = {c for t, c, _, _ in GUARDRAIL_AMBIGUOUS_PAIRS if t.lower() == text}
                assert acc_ids != guard_ids, (
                    f"'{text}' has identical concept_id sets in both corpora: {acc_ids}"
                )

    def test_false_positive_corpus_minimum(self) -> None:
        assert len(HIERARCHY_FALSE_POSITIVE_PAIRS) >= 10

    def test_must_accept_corpus_minimum(self) -> None:
        assert len(HIERARCHY_MUST_ACCEPT_PAIRS) >= 5

    def test_similarity_boundary_corpus_minimum(self) -> None:
        assert len(SIMILARITY_BOUNDARY_CASES) >= 5


# ---------------------------------------------------------------------------
# 2. TestHierarchyFalsePositiveRejection
# ---------------------------------------------------------------------------

class TestHierarchyFalsePositiveRejection:
    """Iterate HIERARCHY_FALSE_POSITIVE_PAIRS through strict-mode
    _string_fallback_match and assert matched=False."""

    def setup_method(self) -> None:
        self.svc = _make_service(strict=True)

    @pytest.mark.parametrize(
        "patient, target, reason",
        HIERARCHY_FALSE_POSITIVE_PAIRS,
        ids=[f"{p}-vs-{t}" for p, t, _ in HIERARCHY_FALSE_POSITIVE_PAIRS],
    )
    def test_strict_rejects_false_positive(
        self, patient: str, target: str, reason: str,
    ) -> None:
        result = self.svc._string_fallback_match(patient, target)
        assert not result.matched, (
            f"Strict mode accepted dangerous pair: "
            f"'{patient}' vs '{target}' — {reason}"
        )


# ---------------------------------------------------------------------------
# 3. TestSimilarityBoundary
# ---------------------------------------------------------------------------

class TestSimilarityBoundary:
    """Iterate SIMILARITY_BOUNDARY_CASES, compute similarity, assert
    scores within expected range."""

    @pytest.mark.parametrize(
        "str_a, str_b, min_exp, max_exp, desc",
        SIMILARITY_BOUNDARY_CASES,
        ids=[desc for _, _, _, _, desc in SIMILARITY_BOUNDARY_CASES],
    )
    def test_similarity_in_range(
        self, str_a: str, str_b: str, min_exp: float, max_exp: float, desc: str,
    ) -> None:
        score = OMOPHierarchyService._compute_string_similarity(
            str_a.lower(), str_b.lower(),
        )
        assert min_exp <= score <= max_exp, (
            f"'{str_a}' vs '{str_b}': score={score:.4f}, "
            f"expected [{min_exp:.2f}, {max_exp:.2f}] — {desc}"
        )


# ---------------------------------------------------------------------------
# 4. TestAmbiguousMappingHandling
# ---------------------------------------------------------------------------

class TestAmbiguousMappingHandling:
    """For reject pairs: assert concept_id NOT returned as top match.
    For downgrade pairs: assert match_quality != 'exact'."""

    @pytest.mark.integration
    def test_reject_pairs_not_returned(self) -> None:
        reject_pairs = [
            (text, cid, reason)
            for text, cid, action, reason in GUARDRAIL_AMBIGUOUS_PAIRS
            if action == "reject"
        ]
        assert reject_pairs, "No reject pairs in corpus"

        mapped_any = False
        violations: list[str] = []

        for text, bad_cid, reason in reject_pairs:
            result_id = _mock_map_text(text)
            if result_id is not None:
                mapped_any = True
                if result_id == bad_cid:
                    violations.append(
                        f"  '{text}' incorrectly mapped to {bad_cid} ({reason})"
                    )

        if not mapped_any:
            pytest.skip("Mapping service unavailable — no concepts mapped")

        assert not violations, (
            f"{len(violations)} false-positive violation(s):\n"
            + "\n".join(violations)
        )

    @pytest.mark.integration
    def test_downgrade_pairs_not_exact(self) -> None:
        downgrade_pairs = [
            (text, cid, reason)
            for text, cid, action, reason in GUARDRAIL_AMBIGUOUS_PAIRS
            if action == "downgrade"
        ]
        if not downgrade_pairs:
            pytest.skip("No downgrade pairs in corpus")

        mapped_any = False
        violations: list[str] = []

        for text, expected_cid, reason in downgrade_pairs:
            result_id, quality = _mock_map_text_with_quality(text)
            if result_id is not None:
                mapped_any = True
                if result_id == expected_cid and quality == "exact":
                    violations.append(
                        f"  '{text}' mapped to {expected_cid} with quality='exact' "
                        f"— should be downgraded ({reason})"
                    )

        if not mapped_any:
            pytest.skip("Mapping service unavailable — no concepts mapped")

        assert not violations, (
            f"{len(violations)} downgrade violation(s):\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 5. TestDomainPrecisionGates
# ---------------------------------------------------------------------------

class TestDomainPrecisionGates:
    """Per-domain positive pairs through mapper; precision >= domain threshold."""

    @pytest.mark.integration
    @pytest.mark.parametrize("domain", list(DOMAIN_POSITIVE_PAIRS.keys()))
    def test_domain_precision(self, domain: str) -> None:
        pairs = DOMAIN_POSITIVE_PAIRS[domain]
        threshold = DOMAIN_PRECISION_THRESHOLDS[domain]

        correct = 0
        mapped = 0
        failures: list[str] = []

        for input_text, expected_id, expected_name in pairs:
            result_id = _mock_map_text(input_text)
            if result_id is not None:
                mapped += 1
                if result_id == expected_id:
                    correct += 1
                else:
                    failures.append(
                        f"  '{input_text}': expected {expected_id} "
                        f"({expected_name}), got {result_id}"
                    )

        if mapped == 0:
            pytest.skip(
                f"Mapping service unavailable for domain '{domain}' "
                f"— no concepts mapped"
            )

        precision = correct / mapped
        msg = (
            f"Domain '{domain}' precision {precision:.2%} ({correct}/{mapped}) "
            f"below threshold {threshold:.0%}.\nFailures:\n"
            + "\n".join(failures)
        )
        assert precision >= threshold, msg


# ---------------------------------------------------------------------------
# 6. TestPrecisionDriftDetection
# ---------------------------------------------------------------------------

class TestPrecisionDriftDetection:
    """Aggregate precision no-regression and false-positive count no-regression."""

    # Baseline expectations — update these when corpus or mapper changes.
    _MIN_AGGREGATE_PRECISION = float(
        os.environ.get("OMOP_GUARDRAIL_MIN_PRECISION", "0.75")
    )
    _MAX_FALSE_POSITIVES = int(
        os.environ.get("OMOP_GUARDRAIL_MAX_FP", "0")
    )

    @pytest.mark.regression
    def test_aggregate_precision_no_regression(self) -> None:
        """Overall precision across all domain pairs must not regress."""
        all_pairs = [
            (text, cid, name)
            for pairs in DOMAIN_POSITIVE_PAIRS.values()
            for text, cid, name in pairs
        ]

        correct = 0
        mapped = 0

        for input_text, expected_id, _ in all_pairs:
            result_id = _mock_map_text(input_text)
            if result_id is not None:
                mapped += 1
                if result_id == expected_id:
                    correct += 1

        if mapped == 0:
            pytest.skip("Mapping service unavailable — no concepts mapped")

        precision = correct / mapped
        assert precision >= self._MIN_AGGREGATE_PRECISION, (
            f"Aggregate precision {precision:.2%} ({correct}/{mapped}) "
            f"below baseline {self._MIN_AGGREGATE_PRECISION:.0%}"
        )

    @pytest.mark.regression
    def test_false_positive_count_no_regression(self) -> None:
        """Zero-tolerance: no false-positive pair may be accepted."""
        svc = _make_service(strict=True)
        fp_count = 0
        violations: list[str] = []

        for patient, target, reason in HIERARCHY_FALSE_POSITIVE_PAIRS:
            result = svc._string_fallback_match(patient, target)
            if result.matched:
                fp_count += 1
                violations.append(f"  '{patient}' vs '{target}': {reason}")

        assert fp_count <= self._MAX_FALSE_POSITIVES, (
            f"False-positive count {fp_count} exceeds max "
            f"{self._MAX_FALSE_POSITIVES}:\n" + "\n".join(violations)
        )
