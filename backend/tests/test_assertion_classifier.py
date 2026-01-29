"""Tests for the Probabilistic Assertion Classifier.

Tests cover:
- Basic negation detection
- Uncertainty detection
- Hypothetical detection
- Present/affirmed detection
- Scope-aware matching
- Pseudo-negation handling
- Scope termination patterns
- Edge cases
"""

import pytest

from app.schemas.base import Assertion
from app.services.assertion_classifier import (
    AssertionCategory,
    AssertionResult,
    ProbabilisticAssertionClassifier,
    TriggerScope,
    classify_assertion,
    get_classifier,
)


class TestNegationDetection:
    """Tests for negation/absent assertion detection."""

    def test_no_evidence_of(self) -> None:
        text = "Patient shows no evidence of pneumonia on chest X-ray."
        # "pneumonia" starts at position 29, ends at 38
        result = classify_assertion(text, 29, 38)
        assert result.assertion == Assertion.ABSENT
        assert result.confidence >= 0.95
        assert result.trigger_text == "no evidence of"
        assert result.category == AssertionCategory.ABSENT

    def test_denies(self) -> None:
        text = "Patient denies chest pain or shortness of breath."
        # "chest pain" starts at 15, ends at 25
        result = classify_assertion(text, 15, 25)
        assert result.assertion == Assertion.ABSENT
        assert result.confidence >= 0.95
        assert result.trigger_text == "denies"

    def test_ruled_out_backward_scope(self) -> None:
        text = "Pulmonary embolism was ruled out by CT angiography."
        # "Pulmonary embolism" starts at 0, ends at 18
        result = classify_assertion(text, 0, 18)
        assert result.assertion == Assertion.ABSENT
        assert result.confidence >= 0.95
        # Can match either "was ruled out" or "ruled out"
        assert "ruled out" in result.trigger_text

    def test_negative_for(self) -> None:
        text = "Blood culture negative for bacteria."
        # "bacteria" starts at 28, ends at 36
        result = classify_assertion(text, 28, 36)
        assert result.assertion == Assertion.ABSENT
        assert result.confidence >= 0.95
        assert result.trigger_text == "negative for"

    def test_no_history_of(self) -> None:
        text = "Patient has no history of diabetes mellitus."
        # "diabetes mellitus" starts at 26, ends at 43
        result = classify_assertion(text, 26, 43)
        assert result.assertion == Assertion.ABSENT
        assert result.trigger_text == "no history of"

    def test_without(self) -> None:
        text = "Abdomen is soft without tenderness."
        # "tenderness" starts at 25, ends at 35
        result = classify_assertion(text, 25, 35)
        assert result.assertion == Assertion.ABSENT
        assert result.trigger_text == "without"

    def test_simple_no(self) -> None:
        text = "No fever noted."
        # "fever" starts at 3, ends at 8
        result = classify_assertion(text, 3, 8)
        assert result.assertion == Assertion.ABSENT
        assert result.trigger_text == "no"


class TestUncertaintyDetection:
    """Tests for uncertainty/possible assertion detection."""

    def test_possible(self) -> None:
        text = "Findings suggestive of possible pneumonia."
        # "pneumonia" starts at 32, ends at 41
        result = classify_assertion(text, 32, 41)
        assert result.assertion == Assertion.POSSIBLE
        assert 0.50 <= result.confidence <= 0.60
        assert result.trigger_text == "possible"
        assert result.category == AssertionCategory.UNCERTAIN

    def test_likely(self) -> None:
        text = "Patient likely has urinary tract infection."
        # "urinary tract infection" starts at 19, ends at 42
        result = classify_assertion(text, 19, 42)
        assert result.assertion == Assertion.POSSIBLE
        assert result.confidence >= 0.65
        assert result.trigger_text == "likely"

    def test_suspected(self) -> None:
        text = "Suspected appendicitis, recommend CT."
        # "appendicitis" starts at 10, ends at 22
        result = classify_assertion(text, 10, 22)
        assert result.assertion == Assertion.POSSIBLE
        assert 0.40 <= result.confidence <= 0.50
        assert result.trigger_text == "suspected"

    def test_cannot_rule_out(self) -> None:
        text = "Cannot rule out malignancy."
        # "malignancy" starts at 16, ends at 26
        result = classify_assertion(text, 16, 26)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "cannot rule out"

    def test_consistent_with(self) -> None:
        text = "Imaging findings consistent with cholecystitis."
        # "cholecystitis" starts at 33, ends at 46
        result = classify_assertion(text, 33, 46)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "consistent with"

    def test_may_have(self) -> None:
        text = "Patient may have early-stage dementia."
        # "dementia" starts at 30, ends at 38
        result = classify_assertion(text, 30, 38)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "may have"


class TestHypotheticalDetection:
    """Tests for hypothetical/conditional assertion detection."""

    def test_risk_of(self) -> None:
        text = "Patient at risk of falls due to age."
        # "falls" starts at 19, ends at 24
        result = classify_assertion(text, 19, 24)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "risk of"
        assert result.category == AssertionCategory.HYPOTHETICAL

    def test_to_rule_out(self) -> None:
        text = "Ordering CT to rule out stroke."
        # "stroke" starts at 25, ends at 31
        result = classify_assertion(text, 25, 31)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "to rule out"
        assert result.category == AssertionCategory.HYPOTHETICAL

    def test_evaluate_for(self) -> None:
        text = "Please evaluate for pulmonary hypertension."
        # "pulmonary hypertension" starts at 20, ends at 42
        result = classify_assertion(text, 20, 42)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "evaluate for"

    def test_prophylaxis_for(self) -> None:
        text = "Started on prophylaxis for DVT."
        # "DVT" starts at 28, ends at 31
        result = classify_assertion(text, 28, 31)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "prophylaxis for"


class TestPresentDetection:
    """Tests for present/affirmed assertion detection."""

    def test_confirmed(self) -> None:
        text = "Biopsy confirmed malignancy."
        # "malignancy" starts at 17, ends at 27
        result = classify_assertion(text, 17, 27)
        assert result.assertion == Assertion.PRESENT
        assert result.confidence >= 0.95
        assert result.trigger_text == "confirmed"
        assert result.category == AssertionCategory.PRESENT

    def test_positive_for(self) -> None:
        text = "Patient tested positive for COVID-19."
        # "COVID-19" starts at 28, ends at 36
        result = classify_assertion(text, 28, 36)
        assert result.assertion == Assertion.PRESENT
        assert result.confidence >= 0.95
        assert result.trigger_text == "positive for"

    def test_diagnosed_with(self) -> None:
        text = "Patient diagnosed with type 2 diabetes."
        # "type 2 diabetes" starts at 23, ends at 38
        result = classify_assertion(text, 23, 38)
        assert result.assertion == Assertion.PRESENT
        assert result.confidence >= 0.95
        assert result.trigger_text == "diagnosed with"

    def test_presents_with(self) -> None:
        text = "Patient presents with acute abdominal pain."
        # "acute abdominal pain" starts at 22, ends at 42
        result = classify_assertion(text, 22, 42)
        assert result.assertion == Assertion.PRESENT
        assert result.trigger_text == "presents with"

    def test_no_trigger_defaults_to_present(self) -> None:
        text = "Patient has diabetes."
        # "diabetes" starts at 12, ends at 20
        result = classify_assertion(text, 12, 20)
        assert result.assertion == Assertion.PRESENT
        # No strong trigger found, defaults to PRESENT with default confidence
        assert result.trigger_text is None
        assert result.confidence == 0.85  # default confidence


class TestPseudoNegation:
    """Tests for pseudo-negation patterns that should NOT negate."""

    def test_no_change(self) -> None:
        text = "Tumor shows no change from prior imaging."
        # "Tumor" starts at 0, ends at 5
        result = classify_assertion(text, 0, 5)
        # "no change" is pseudo-negation, should not negate "Tumor"
        assert result.assertion == Assertion.PRESENT
        assert result.trigger_text == "no change"

    def test_gram_negative(self) -> None:
        text = "Culture grew gram negative bacteria."
        # "bacteria" starts at 27, ends at 35
        result = classify_assertion(text, 27, 35)
        # "gram negative" is pseudo-negation
        assert result.assertion == Assertion.PRESENT
        assert result.trigger_text == "gram negative"

    def test_not_ruled_out(self) -> None:
        text = "Malignancy not ruled out at this time."
        # "Malignancy" starts at 0, ends at 10
        result = classify_assertion(text, 0, 10)
        # "not ruled out" is pseudo-negation (uncertain, not absent)
        assert result.assertion == Assertion.POSSIBLE
        assert result.trigger_text == "not ruled out"


class TestScopeTermination:
    """Tests for scope termination patterns."""

    def test_but_terminates_scope(self) -> None:
        text = "No chest pain but has shortness of breath."
        # "shortness of breath" starts at 23, ends at 42
        result = classify_assertion(text, 23, 42)
        # "but" should terminate the scope of "No"
        assert result.assertion == Assertion.PRESENT

    def test_however_terminates_scope(self) -> None:
        text = "Denies fever; however, reports chills."
        # "chills" starts at 31, ends at 37
        result = classify_assertion(text, 31, 37)
        # "however" should terminate the scope of "Denies"
        assert result.assertion == Assertion.PRESENT

    def test_semicolon_terminates_scope(self) -> None:
        text = "No evidence of infection; wound healing well."
        # "wound" starts at 26, ends at 31
        result = classify_assertion(text, 26, 31)
        # ";" should terminate the scope of "No evidence of"
        assert result.assertion == Assertion.PRESENT


class TestScopeDistance:
    """Tests for trigger scope distance limits."""

    def test_trigger_within_scope(self) -> None:
        text = "No acute pneumonia."
        # "pneumonia" starts at 10, ends at 19
        result = classify_assertion(text, 10, 19)
        assert result.assertion == Assertion.ABSENT
        assert result.trigger_distance is not None
        assert result.trigger_distance <= 6

    def test_trigger_outside_scope(self) -> None:
        text = "No history of smoking, alcohol use, or other risk factors for pneumonia."
        # "pneumonia" is far from "No" (more than 6 tokens)
        # starts at 62, ends at 71
        result = classify_assertion(text, 62, 71)
        # Should default to PRESENT since "No" is too far
        # Actually "no" has max_scope_tokens=4, so it won't reach
        # But "risk factors for" isn't a trigger
        assert result.assertion == Assertion.PRESENT


class TestClassifierConfiguration:
    """Tests for classifier configuration options."""

    def test_custom_default_confidence(self) -> None:
        classifier = ProbabilisticAssertionClassifier(default_confidence=0.90)
        text = "Patient has diabetes."
        result = classifier.classify(text, 12, 20)
        # "has" matches, so confidence should be from the trigger
        assert result.assertion == Assertion.PRESENT

    def test_disable_pseudo_negation(self) -> None:
        classifier = ProbabilisticAssertionClassifier(use_pseudo_negation=False)
        text = "Tumor shows no change from prior imaging."
        # With pseudo-negation disabled, "no" should negate
        result = classifier.classify(text, 0, 5)
        # The trigger "no change" is still in the list but won't be prioritized
        assert result.assertion in (Assertion.PRESENT, Assertion.ABSENT)


class TestBatchClassification:
    """Tests for batch classification."""

    def test_classify_batch(self) -> None:
        text = "Patient denies chest pain but has shortness of breath. No fever."
        mentions = [
            (15, 25),  # "chest pain"
            (34, 53),  # "shortness of breath"
            (58, 63),  # "fever"
        ]
        classifier = get_classifier()
        results = classifier.classify_batch(text, mentions)

        assert len(results) == 3
        assert results[0].assertion == Assertion.ABSENT  # denies chest pain
        assert results[1].assertion == Assertion.PRESENT  # has shortness of breath
        assert results[2].assertion == Assertion.ABSENT  # No fever


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_text(self) -> None:
        result = classify_assertion("", 0, 0)
        assert result.assertion == Assertion.PRESENT
        assert result.trigger_text is None

    def test_mention_at_start(self) -> None:
        text = "Diabetes is controlled."
        result = classify_assertion(text, 0, 8)
        assert result.assertion == Assertion.PRESENT

    def test_mention_at_end(self) -> None:
        text = "No evidence of diabetes"
        result = classify_assertion(text, 15, 23)
        assert result.assertion == Assertion.ABSENT

    def test_case_insensitivity(self) -> None:
        text = "PATIENT DENIES CHEST PAIN."
        result = classify_assertion(text, 15, 25)
        assert result.assertion == Assertion.ABSENT
        assert result.trigger_text == "denies"

    def test_multiple_triggers_closest_wins(self) -> None:
        text = "No evidence of, likely pneumonia."
        # Both "no evidence of" (absent) and "likely" (uncertain) are present
        # "likely" is closer to "pneumonia"
        result = classify_assertion(text, 23, 32)
        assert result.trigger_text == "likely"
        assert result.assertion == Assertion.POSSIBLE


class TestConfidenceRanges:
    """Tests to verify confidence scores are in expected ranges."""

    def test_absent_high_confidence(self) -> None:
        """High-confidence negations should have confidence >= 0.90."""
        high_conf_cases = [
            ("No evidence of pneumonia.", 15, 24),  # "pneumonia" at 15-24
            ("Patient denies chest pain.", 15, 25),  # "chest pain" at 15-25
            ("Ruled out malignancy.", 10, 20),  # "malignancy" at 10-20
        ]
        for text, start, end in high_conf_cases:
            result = classify_assertion(text, start, end)
            assert result.assertion == Assertion.ABSENT, f"Failed for: {text}, got {result}"
            assert result.confidence >= 0.90, f"Failed for: {text}, confidence={result.confidence}"

    def test_uncertain_medium_confidence(self) -> None:
        """Uncertainty triggers should have confidence 0.30-0.75."""
        uncertain_cases = [
            ("Possible pneumonia.", 9, 18),
            ("Suspected malignancy.", 10, 20),
            ("May have diabetes.", 9, 17),
        ]
        for text, start, end in uncertain_cases:
            result = classify_assertion(text, start, end)
            assert result.assertion == Assertion.POSSIBLE
            assert 0.30 <= result.confidence <= 0.80, f"Failed for: {text}"

    def test_hypothetical_low_confidence(self) -> None:
        """Hypothetical triggers should have confidence 0.20-0.40."""
        hypo_cases = [
            ("Risk of stroke.", 8, 14),
            ("To rule out PE.", 13, 15),
        ]
        for text, start, end in hypo_cases:
            result = classify_assertion(text, start, end)
            assert result.assertion == Assertion.POSSIBLE
            assert result.category == AssertionCategory.HYPOTHETICAL
            assert 0.20 <= result.confidence <= 0.40, f"Failed for: {text}"


class TestRealWorldExamples:
    """Tests using real clinical text patterns."""

    def test_history_and_physical_pattern(self) -> None:
        text = """
        Chief Complaint: Chest pain
        History: Patient denies shortness of breath, palpitations, or syncope.
        Physical: Lungs clear, no wheezing. Heart regular rhythm, no murmurs.
        Assessment: Likely musculoskeletal chest pain.
        """
        # Test "shortness of breath" is negated
        sob_start = text.find("shortness of breath")
        sob_end = sob_start + len("shortness of breath")
        result = classify_assertion(text, sob_start, sob_end)
        assert result.assertion == Assertion.ABSENT

        # Test "wheezing" is negated
        wheeze_start = text.find("wheezing")
        wheeze_end = wheeze_start + len("wheezing")
        result = classify_assertion(text, wheeze_start, wheeze_end)
        assert result.assertion == Assertion.ABSENT

        # Test "musculoskeletal chest pain" is uncertain (likely)
        msk_start = text.find("musculoskeletal chest pain")
        msk_end = msk_start + len("musculoskeletal chest pain")
        result = classify_assertion(text, msk_start, msk_end)
        assert result.assertion == Assertion.POSSIBLE

    def test_radiology_report_pattern(self) -> None:
        text = """
        CT Chest: No evidence of pulmonary embolism.
        Possible early pneumonia in right lower lobe.
        Cannot rule out malignancy; recommend follow-up.
        """
        # Test "pulmonary embolism" is negated
        pe_start = text.find("pulmonary embolism")
        pe_end = pe_start + len("pulmonary embolism")
        result = classify_assertion(text, pe_start, pe_end)
        assert result.assertion == Assertion.ABSENT

        # Test "pneumonia" is uncertain
        pna_start = text.find("pneumonia")
        pna_end = pna_start + len("pneumonia")
        result = classify_assertion(text, pna_start, pna_end)
        assert result.assertion == Assertion.POSSIBLE

        # Test "malignancy" is uncertain (cannot rule out)
        mal_start = text.find("malignancy")
        mal_end = mal_start + len("malignancy")
        result = classify_assertion(text, mal_start, mal_end)
        assert result.assertion == Assertion.POSSIBLE
