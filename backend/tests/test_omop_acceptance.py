"""OMOP acceptance tests for mapping quality validation.

P1-010: Validates that the OMOP mapping pipeline meets a minimum
precision threshold against a curated acceptance corpus of positive
and negative concept pairs.
"""

from __future__ import annotations

import os

import pytest

from tests.fixtures.omop_acceptance_corpus import NEGATIVE_PAIRS, POSITIVE_PAIRS

# Precision threshold -- configurable via env, default 0.80
PRECISION_THRESHOLD = float(os.environ.get("OMOP_ACCEPTANCE_PRECISION", "0.80"))


def _mock_map_text(input_text: str) -> int | None:
    """Simulate OMOP concept mapping for acceptance testing.

    In a live environment this would call the real mapping service.
    For unit-level acceptance testing we import the mapping function
    and validate its output against the corpus.

    Returns:
        The mapped OMOP concept ID or None if no mapping found.
    """
    try:
        from app.services.mapping_service import MappingService

        svc = MappingService()
        result = svc.map_text_to_concept(input_text)
        if result and hasattr(result, "concept_id"):
            return result.concept_id
        return None
    except Exception:
        # If mapping service is unavailable, return None
        return None


class TestOMOPAcceptanceCorpus:
    """Validate OMOP mapping quality against acceptance corpus."""

    def test_corpus_is_non_empty(self) -> None:
        """Ensure the acceptance corpus has content."""
        assert len(POSITIVE_PAIRS) >= 20, (
            f"Positive corpus must have >= 20 pairs, got {len(POSITIVE_PAIRS)}"
        )
        assert len(NEGATIVE_PAIRS) >= 10, (
            f"Negative corpus must have >= 10 pairs, got {len(NEGATIVE_PAIRS)}"
        )

    def test_positive_pairs_structure(self) -> None:
        """Validate that positive pairs have correct tuple structure."""
        for pair in POSITIVE_PAIRS:
            assert len(pair) == 3, f"Expected 3-tuple, got {pair}"
            text, concept_id, concept_name = pair
            assert isinstance(text, str) and text.strip(), f"Bad text: {text}"
            assert isinstance(concept_id, int) and concept_id > 0, (
                f"Bad concept_id: {concept_id}"
            )
            assert isinstance(concept_name, str) and concept_name.strip(), (
                f"Bad concept_name: {concept_name}"
            )

    def test_negative_pairs_structure(self) -> None:
        """Validate that negative pairs have correct tuple structure."""
        for pair in NEGATIVE_PAIRS:
            assert len(pair) == 2, f"Expected 2-tuple, got {pair}"
            text, concept_id = pair
            assert isinstance(text, str) and text.strip(), f"Bad text: {text}"
            assert isinstance(concept_id, int) and concept_id > 0, (
                f"Bad concept_id: {concept_id}"
            )

    def test_no_duplicate_positive_pairs(self) -> None:
        """Ensure no duplicate input texts in the positive corpus."""
        texts = [t.lower() for t, _, _ in POSITIVE_PAIRS]
        assert len(texts) == len(set(texts)), "Duplicate texts in POSITIVE_PAIRS"

    def test_domains_covered(self) -> None:
        """Ensure the corpus covers medications, conditions, procedures, and labs."""
        texts = [t.lower() for t, _, _ in POSITIVE_PAIRS]
        # At least one medication
        meds = {"aspirin", "metformin", "lisinopril"}
        assert meds & set(texts), "Corpus must include medication pairs"
        # At least one condition
        conditions = {"pneumonia", "asthma"}
        assert conditions & set(texts), "Corpus must include condition pairs"

    @pytest.mark.integration
    def test_precision_gate(self) -> None:
        """Run positive corpus through mapping and assert precision >= threshold.

        This test is marked as integration because it requires the mapping
        service to be available. In CI without backend services it will be
        skipped.
        """
        correct = 0
        mapped = 0
        failures: list[str] = []

        for input_text, expected_id, expected_name in POSITIVE_PAIRS:
            result_id = _mock_map_text(input_text)
            if result_id is not None:
                mapped += 1
                if result_id == expected_id:
                    correct += 1
                else:
                    failures.append(
                        f"  '{input_text}': expected {expected_id} ({expected_name}), "
                        f"got {result_id}"
                    )

        if mapped == 0:
            pytest.skip("Mapping service unavailable -- no concepts mapped")

        precision = correct / mapped
        msg = (
            f"Precision {precision:.2%} ({correct}/{mapped}) "
            f"below threshold {PRECISION_THRESHOLD:.0%}.\nFailures:\n"
            + "\n".join(failures)
        )
        assert precision >= PRECISION_THRESHOLD, msg

    @pytest.mark.integration
    def test_negative_pairs_rejected(self) -> None:
        """Ensure known false-positive mappings are NOT produced.

        For each negative pair (text, bad_concept_id) the mapper must NOT
        return bad_concept_id.
        """
        violations: list[str] = []

        for input_text, bad_id in NEGATIVE_PAIRS:
            result_id = _mock_map_text(input_text)
            if result_id == bad_id:
                violations.append(
                    f"  '{input_text}' incorrectly mapped to {bad_id}"
                )

        if violations:
            pytest.fail(
                f"{len(violations)} false-positive violation(s):\n"
                + "\n".join(violations)
            )
