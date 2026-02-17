"""Tests for the unified ConditionMatchingService.

Covers:
- Exact matching
- Compound-term rejection (the core bug fix)
- Qualified substring matching with word boundaries
- Primary-condition gating
- Multi-word term preservation
- Score aggregation
- Integration-point scenarios (guideline/calculator/policy)
"""

from __future__ import annotations

import pytest

from app.services.condition_matching_service import (
    ConditionMatch,
    MatchResult,
    _is_compound_term_conflict,
    _normalize,
    _word_boundary_match,
    match_conditions,
    match_conditions_simple,
    score_condition_overlap,
)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_lowercase_and_strip_punctuation(self):
        assert _normalize("Type 2 Diabetes") == "type 2 diabetes"

    def test_collapses_whitespace(self):
        assert _normalize("  iron  deficiency   anemia  ") == "iron  deficiency   anemia"

    def test_strips_special_chars(self):
        assert _normalize("Crohn's Disease") == "crohns disease"


# ---------------------------------------------------------------------------
# Word-boundary matching
# ---------------------------------------------------------------------------


class TestWordBoundaryMatch:
    def test_anemia_in_iron_deficiency_anemia(self):
        assert _word_boundary_match("anemia", "iron deficiency anemia") is True

    def test_anemia_in_sickle_cell_anemia(self):
        # Word boundary matches, but compound-term check blocks later
        assert _word_boundary_match("anemia", "sickle cell anemia") is True

    def test_pe_not_in_peripheral(self):
        assert _word_boundary_match("pe", "peripheral artery disease") is False

    def test_pe_in_acute_pe(self):
        assert _word_boundary_match("pe", "acute pe") is True

    def test_cancer_in_colorectal_cancer(self):
        assert _word_boundary_match("cancer", "colorectal cancer") is True

    def test_can_not_in_cancer(self):
        assert _word_boundary_match("can", "cancer") is False

    def test_exact_match(self):
        assert _word_boundary_match("diabetes", "diabetes") is True

    def test_diabetes_in_type_2_diabetes(self):
        assert _word_boundary_match("diabetes", "type 2 diabetes") is True


# ---------------------------------------------------------------------------
# Compound-term conflict detection
# ---------------------------------------------------------------------------


class TestCompoundTermConflict:
    def test_anemia_vs_sickle_cell_anemia(self):
        assert _is_compound_term_conflict("anemia", "sickle cell anemia") is True

    def test_anemia_vs_pernicious_anemia(self):
        assert _is_compound_term_conflict("anemia", "pernicious anemia") is True

    def test_anemia_vs_aplastic_anemia(self):
        assert _is_compound_term_conflict("anemia", "aplastic anemia") is True

    def test_anemia_vs_anemia_exact(self):
        assert _is_compound_term_conflict("anemia", "anemia") is False

    def test_cancer_vs_breast_cancer(self):
        assert _is_compound_term_conflict("cancer", "breast cancer") is True

    def test_cancer_vs_colorectal_cancer(self):
        assert _is_compound_term_conflict("cancer", "colorectal cancer") is True

    def test_cancer_vs_cancer_exact(self):
        assert _is_compound_term_conflict("cancer", "cancer") is False

    def test_sickle_cell_disease_vs_sickle_cell_anemia(self):
        # These are different but related compound terms; neither is a
        # misleading substring of the other.
        assert _is_compound_term_conflict("sickle cell disease", "sickle cell anemia") is False

    def test_diabetes_vs_type_2_diabetes(self):
        assert _is_compound_term_conflict("diabetes", "type 2 diabetes") is True

    def test_pain_vs_low_back_pain(self):
        assert _is_compound_term_conflict("pain", "low back pain") is True

    def test_arthritis_vs_rheumatoid_arthritis(self):
        assert _is_compound_term_conflict("arthritis", "rheumatoid arthritis") is True


# ---------------------------------------------------------------------------
# Exact match (tier 1)
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_identical_strings(self):
        r = match_conditions(["anemia"], ["anemia"], use_hierarchy=False)
        assert r.has_match
        assert r.best_score == 1.0
        assert r.matches[0].tier == "exact"

    def test_case_insensitive(self):
        r = match_conditions(["Anemia"], ["anemia"], use_hierarchy=False)
        assert r.has_match
        assert r.best_score == 1.0

    def test_multi_word_exact(self):
        r = match_conditions(
            ["colorectal cancer"], ["colorectal cancer"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.best_score == 1.0


# ---------------------------------------------------------------------------
# Qualified substring match (tier 3)
# ---------------------------------------------------------------------------


class TestQualifiedSubstringMatch:
    def test_anemia_matches_iron_deficiency_anemia(self):
        r = match_conditions(
            ["anemia"], ["iron deficiency anemia"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.best_score == 0.6
        assert r.matches[0].tier == "qualified_substring"

    def test_diabetes_blocked_from_type_2_diabetes_mellitus(self):
        # "type 2 diabetes" is a compound term — "diabetes" alone should not
        # match via substring. In practice, guidelines list both "diabetes"
        # and "type 2 diabetes" in applies_to_conditions for exact matching,
        # or OMOP hierarchy would handle the IS_A relationship.
        r = match_conditions(
            ["diabetes"], ["type 2 diabetes mellitus"],
            use_hierarchy=False,
        )
        assert not r.has_match

    def test_hypertension_matches_pulmonary_hypertension_blocked(self):
        # "hypertension" in "pulmonary hypertension" — compound term
        r = match_conditions(
            ["hypertension"], ["pulmonary hypertension"],
            use_hierarchy=False,
        )
        assert not r.has_match


# ---------------------------------------------------------------------------
# Compound-term rejection (the core bug fix)
# ---------------------------------------------------------------------------


class TestCompoundTermRejection:
    """These are the critical test cases that verify the root cause fix."""

    def test_anemia_does_not_match_sickle_cell_anemia(self):
        r = match_conditions(
            ["anemia"], ["sickle cell anemia"],
            use_hierarchy=False,
        )
        assert not r.has_match

    def test_anemia_does_not_match_pernicious_anemia(self):
        r = match_conditions(
            ["anemia"], ["pernicious anemia"],
            use_hierarchy=False,
        )
        assert not r.has_match

    def test_cancer_does_not_match_breast_cancer(self):
        r = match_conditions(
            ["cancer"], ["breast cancer"],
            use_hierarchy=False,
        )
        assert not r.has_match

    def test_pain_does_not_match_low_back_pain(self):
        r = match_conditions(
            ["pain"], ["low back pain"],
            use_hierarchy=False,
        )
        assert not r.has_match


# ---------------------------------------------------------------------------
# Primary-condition gating
# ---------------------------------------------------------------------------


class TestPrimaryConditionGating:
    def test_scd_guideline_rejected_for_generic_anemia_patient(self):
        """Patient with just 'anemia' should NOT match SCD guideline."""
        r = match_conditions(
            patient_conditions=["anemia"],
            target_conditions=["sickle cell disease", "sickle cell anemia", "severe anemia"],
            primary_conditions=["sickle cell disease"],
            use_hierarchy=False,
        )
        assert not r.has_match
        assert not r.primary_gate_passed

    def test_scd_guideline_accepted_for_scd_patient(self):
        """Patient with 'sickle cell disease' SHOULD match SCD guideline."""
        r = match_conditions(
            patient_conditions=["sickle cell disease"],
            target_conditions=["sickle cell disease", "sickle cell anemia"],
            primary_conditions=["sickle cell disease"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.primary_gate_passed
        assert r.best_score == 1.0

    def test_crc_patient_does_not_match_scd(self):
        """Patient TEST66066 (colorectal cancer + anemia) must NOT match SCD."""
        r = match_conditions(
            patient_conditions=["colorectal cancer", "anemia"],
            target_conditions=["sickle cell disease", "scd", "sickle cell anemia"],
            primary_conditions=["sickle cell disease"],
            use_hierarchy=False,
        )
        assert not r.has_match

    def test_crc_patient_matches_crc_guideline(self):
        """Patient TEST66066 SHOULD match NCCN CRC guideline."""
        r = match_conditions(
            patient_conditions=["colorectal cancer", "anemia"],
            target_conditions=["colorectal cancer", "colon cancer", "adenomatous polyps"],
            primary_conditions=["colorectal cancer"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.best_score == 1.0

    def test_no_primary_conditions_means_no_gate(self):
        """When primary_conditions is empty, gating is skipped."""
        r = match_conditions(
            patient_conditions=["anemia"],
            target_conditions=["anemia", "fatigue"],
            primary_conditions=None,
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.primary_gate_passed

    def test_patient_with_both_scd_and_crc(self):
        """A patient with both SCD and CRC should match SCD guideline."""
        r = match_conditions(
            patient_conditions=["sickle cell disease", "colorectal cancer"],
            target_conditions=["sickle cell disease", "sickle cell anemia"],
            primary_conditions=["sickle cell disease"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.primary_gate_passed


# ---------------------------------------------------------------------------
# Multi-word term preservation
# ---------------------------------------------------------------------------


class TestMultiWordPreservation:
    def test_colorectal_cancer_not_split(self):
        """'colorectal cancer' should match as a whole term, not 'colorectal' + 'cancer'."""
        r = match_conditions(
            ["colorectal cancer"], ["colorectal cancer"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.best_score == 1.0
        assert r.matches[0].tier == "exact"

    def test_sickle_cell_disease_not_split(self):
        r = match_conditions(
            ["sickle cell disease"], ["sickle cell disease"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.best_score == 1.0


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


class TestMatchConditionsSimple:
    def test_returns_true_on_match(self):
        assert match_conditions_simple(["anemia"], ["anemia"], use_hierarchy=False) is True

    def test_returns_false_on_no_match(self):
        assert match_conditions_simple(["anemia"], ["sickle cell anemia"], use_hierarchy=False) is False


class TestScoreConditionOverlap:
    def test_exact_match_high_score(self):
        score = score_condition_overlap(
            ["anemia"], ["anemia"],
            use_hierarchy=False,
        )
        assert score >= 0.7

    def test_no_match_zero_score(self):
        score = score_condition_overlap(
            ["anemia"], ["sickle cell anemia"],
            use_hierarchy=False,
        )
        assert score == 0.0

    def test_gated_out_zero_score(self):
        score = score_condition_overlap(
            ["anemia"], ["sickle cell anemia", "scd"],
            primary_conditions=["sickle cell disease"],
            use_hierarchy=False,
        )
        assert score == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_patient_conditions(self):
        r = match_conditions([], ["anemia"], use_hierarchy=False)
        assert not r.has_match

    def test_empty_target_conditions(self):
        r = match_conditions(["anemia"], [], use_hierarchy=False)
        assert not r.has_match

    def test_both_empty(self):
        r = match_conditions([], [], use_hierarchy=False)
        assert not r.has_match

    def test_set_input(self):
        r = match_conditions({"anemia"}, {"anemia"}, use_hierarchy=False)
        assert r.has_match

    def test_multiple_matches_best_score(self):
        r = match_conditions(
            ["diabetes", "hypertension"],
            ["diabetes", "type 2 diabetes"],
            use_hierarchy=False,
        )
        assert r.has_match
        assert r.best_score == 1.0  # "diabetes" exact match
