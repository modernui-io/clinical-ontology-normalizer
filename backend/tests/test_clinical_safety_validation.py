"""Tests for clinical safety validation: input plausibility + diagnosis ranking labels.

Covers P1-014 (calculator input plausibility validation) and
P1-015 (differential diagnosis ranking labels).
"""

import pytest

from app.services.clinical_input_validator import (
    PLAUSIBILITY_RANGES,
    PlausibilityResult,
    validate_clinical_inputs,
)
from app.services.differential_diagnosis import (
    DiagnosisCandidate,
    DifferentialDiagnosisService,
    DifferentialResult,
    reset_differential_diagnosis_service,
)


# ============================================================================
# P1-014: Calculator Input Plausibility Validation
# ============================================================================


class TestPlausibilityResultDataclass:
    """Test PlausibilityResult structure."""

    def test_default_construction(self):
        result = PlausibilityResult(valid=True)
        assert result.valid is True
        assert result.warnings == []
        assert result.blocked is False
        assert result.blocked_reason is None

    def test_blocked_construction(self):
        result = PlausibilityResult(
            valid=False,
            blocked=True,
            blocked_reason="value out of range",
        )
        assert result.valid is False
        assert result.blocked is True
        assert result.blocked_reason == "value out of range"


class TestNormalRangeInputs:
    """Normal-range inputs should pass without warnings or blocking."""

    def test_normal_heart_rate(self):
        result = validate_clinical_inputs({"heart_rate": 72})
        assert result.valid is True
        assert result.blocked is False
        assert result.warnings == []

    def test_normal_blood_pressure(self):
        result = validate_clinical_inputs({
            "systolic_bp": 120,
            "diastolic_bp": 80,
        })
        assert result.valid is True
        assert result.blocked is False
        assert result.warnings == []

    def test_normal_temperature(self):
        result = validate_clinical_inputs({"temperature": 37.0})
        assert result.valid is True
        assert result.warnings == []

    def test_normal_weight_and_height(self):
        result = validate_clinical_inputs({
            "weight_kg": 70,
            "height_cm": 170,
        })
        assert result.valid is True
        assert result.warnings == []

    def test_normal_age(self):
        result = validate_clinical_inputs({"age": 45})
        assert result.valid is True
        assert result.warnings == []

    def test_normal_creatinine(self):
        result = validate_clinical_inputs({"creatinine": 1.1})
        assert result.valid is True
        assert result.warnings == []

    def test_normal_gfr(self):
        result = validate_clinical_inputs({"gfr": 90})
        assert result.valid is True
        assert result.warnings == []

    def test_all_normal_values(self):
        """All common clinical values in normal range."""
        result = validate_clinical_inputs({
            "heart_rate": 80,
            "systolic_bp": 118,
            "diastolic_bp": 76,
            "temperature": 36.8,
            "weight_kg": 68,
            "height_cm": 165,
            "age": 55,
            "creatinine": 0.9,
            "gfr": 95,
        })
        assert result.valid is True
        assert result.blocked is False
        assert result.warnings == []


class TestFlagRangeInputs:
    """Flag-range values produce warnings but do not block."""

    def test_low_heart_rate_flag(self):
        """HR = 20 is at the flag boundary -- still valid."""
        result = validate_clinical_inputs({"heart_rate": 20})
        assert result.valid is True
        assert result.blocked is False
        # 20 is exactly at flag_min, so no warning (within range)
        assert len(result.warnings) == 0

    def test_high_heart_rate_flag(self):
        """HR = 300 is at the flag boundary."""
        result = validate_clinical_inputs({"heart_rate": 300})
        assert result.valid is True
        assert result.blocked is False

    def test_low_systolic_bp_flag(self):
        """SBP = 40 is at flag boundary."""
        result = validate_clinical_inputs({"systolic_bp": 40})
        assert result.valid is True
        assert result.blocked is False

    def test_extreme_weight_flag(self):
        """Weight = 500 kg at the flag boundary."""
        result = validate_clinical_inputs({"weight_kg": 500})
        assert result.valid is True

    def test_extreme_age_flag(self):
        """Age = 150 at the flag boundary."""
        result = validate_clinical_inputs({"age": 150})
        assert result.valid is True

    def test_extreme_creatinine_flag(self):
        """Creatinine = 30 at the flag boundary."""
        result = validate_clinical_inputs({"creatinine": 30})
        assert result.valid is True


class TestBlockRangeInputs:
    """Block-range values must be rejected."""

    def test_negative_heart_rate(self):
        result = validate_clinical_inputs({"heart_rate": -5})
        assert result.valid is False
        assert result.blocked is True
        assert result.blocked_reason is not None
        assert "heart_rate" in result.blocked_reason

    def test_impossibly_high_heart_rate(self):
        result = validate_clinical_inputs({"heart_rate": 350})
        assert result.valid is False
        assert result.blocked is True

    def test_negative_systolic_bp(self):
        result = validate_clinical_inputs({"systolic_bp": 10})
        assert result.valid is False
        assert result.blocked is True

    def test_impossibly_high_systolic_bp(self):
        result = validate_clinical_inputs({"systolic_bp": 350})
        assert result.valid is False
        assert result.blocked is True

    def test_sub_freezing_temperature(self):
        result = validate_clinical_inputs({"temperature": 20.0})
        assert result.valid is False
        assert result.blocked is True

    def test_impossibly_high_temperature(self):
        result = validate_clinical_inputs({"temperature": 50.0})
        assert result.valid is False
        assert result.blocked is True

    def test_negative_weight(self):
        result = validate_clinical_inputs({"weight_kg": 0.0})
        assert result.valid is False
        assert result.blocked is True

    def test_impossibly_heavy(self):
        result = validate_clinical_inputs({"weight_kg": 600})
        assert result.valid is False
        assert result.blocked is True

    def test_negative_height(self):
        result = validate_clinical_inputs({"height_cm": 10})
        assert result.valid is False
        assert result.blocked is True

    def test_impossibly_tall(self):
        result = validate_clinical_inputs({"height_cm": 300})
        assert result.valid is False
        assert result.blocked is True

    def test_negative_age(self):
        result = validate_clinical_inputs({"age": -1})
        assert result.valid is False
        assert result.blocked is True

    def test_impossibly_old(self):
        result = validate_clinical_inputs({"age": 200})
        assert result.valid is False
        assert result.blocked is True

    def test_near_zero_creatinine(self):
        result = validate_clinical_inputs({"creatinine": 0.05})
        assert result.valid is False
        assert result.blocked is True

    def test_impossibly_high_creatinine(self):
        result = validate_clinical_inputs({"creatinine": 50})
        assert result.valid is False
        assert result.blocked is True

    def test_negative_gfr(self):
        result = validate_clinical_inputs({"gfr": -10})
        assert result.valid is False
        assert result.blocked is True

    def test_impossibly_high_gfr(self):
        result = validate_clinical_inputs({"gfr": 300})
        assert result.valid is False
        assert result.blocked is True

    def test_blocked_stops_at_first(self):
        """Only the first blocked value generates the reason."""
        result = validate_clinical_inputs({
            "heart_rate": -5,
            "age": -1,
        })
        assert result.blocked is True
        assert result.blocked_reason is not None


class TestBoundaryValues:
    """Edge cases at exact boundaries."""

    @pytest.mark.parametrize("key,value", [
        ("heart_rate", 20),
        ("heart_rate", 300),
        ("systolic_bp", 40),
        ("systolic_bp", 300),
        ("diastolic_bp", 20),
        ("diastolic_bp", 200),
        ("temperature", 25.0),
        ("temperature", 45.0),
        ("weight_kg", 0.5),
        ("weight_kg", 500),
        ("height_cm", 20),
        ("height_cm", 280),
        ("age", 0),
        ("age", 150),
        ("creatinine", 0.1),
        ("creatinine", 30),
        ("gfr", 0),
        ("gfr", 200),
    ])
    def test_exact_boundary_accepted(self, key, value):
        """Values at the exact boundary should NOT be blocked."""
        result = validate_clinical_inputs({key: value})
        assert result.valid is True
        assert result.blocked is False

    @pytest.mark.parametrize("key,below_block,above_block", [
        ("heart_rate", -1, 301),
        ("systolic_bp", 39, 301),
        ("diastolic_bp", 19, 201),
        ("temperature", 24.9, 45.1),
        ("weight_kg", 0.4, 501),
        ("height_cm", 19, 281),
        ("age", -1, 151),
        ("creatinine", 0.09, 31),
        ("gfr", -1, 201),
    ])
    def test_just_outside_boundary_blocked(self, key, below_block, above_block):
        """Values just outside the boundary should be blocked."""
        result_low = validate_clinical_inputs({key: below_block})
        assert result_low.blocked is True

        result_high = validate_clinical_inputs({key: above_block})
        assert result_high.blocked is True


class TestAliases:
    """Input aliases resolve to the correct canonical key."""

    def test_hr_alias(self):
        result = validate_clinical_inputs({"hr": 72})
        assert result.valid is True

    def test_pulse_alias(self):
        result = validate_clinical_inputs({"pulse": 72})
        assert result.valid is True

    def test_sbp_alias(self):
        result = validate_clinical_inputs({"sbp": 120})
        assert result.valid is True

    def test_temp_alias(self):
        result = validate_clinical_inputs({"temp": 37.0})
        assert result.valid is True

    def test_cr_alias(self):
        result = validate_clinical_inputs({"cr": 1.0})
        assert result.valid is True

    def test_egfr_alias(self):
        result = validate_clinical_inputs({"egfr": 90})
        assert result.valid is True

    def test_blocked_via_alias(self):
        result = validate_clinical_inputs({"hr": -5})
        assert result.blocked is True


class TestUnknownInputsIgnored:
    """Inputs not in the plausibility table are silently skipped."""

    def test_unknown_key_passes(self):
        result = validate_clinical_inputs({"potassium": 5.0})
        assert result.valid is True
        assert result.warnings == []

    def test_mix_known_unknown(self):
        result = validate_clinical_inputs({
            "heart_rate": 72,
            "some_custom_value": 999,
        })
        assert result.valid is True


class TestEmptyInput:
    """Empty input dict should return a clean valid result."""

    def test_empty_dict(self):
        result = validate_clinical_inputs({})
        assert result.valid is True
        assert result.warnings == []
        assert result.blocked is False


# ============================================================================
# P1-015: Diagnosis Ranking Labels
# ============================================================================


class TestDiagnosisRankingLabels:
    """Differential diagnosis outputs use ranking language, not probability."""

    def setup_method(self):
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_candidate_has_ranking_score(self):
        """DiagnosisCandidate uses ranking_score, not probability_score."""
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea"],
        )
        assert len(result.differential) > 0
        dx = result.differential[0]
        assert hasattr(dx, "ranking_score")
        assert not hasattr(dx, "probability_score")

    def test_candidate_calibration_status(self):
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea"],
        )
        dx = result.differential[0]
        assert dx.calibration_status == "uncalibrated_ranking"

    def test_candidate_calibration_disclaimer(self):
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea"],
        )
        dx = result.differential[0]
        assert "ranking" in dx.calibration_disclaimer.lower()
        assert "not calibrated" in dx.calibration_disclaimer.lower() or \
               "not calibrated probabilities" in dx.calibration_disclaimer.lower()

    def test_result_calibration_status(self):
        """DifferentialResult itself carries calibration metadata."""
        result = self.service.generate_differential(
            findings=["chest pain"],
        )
        assert result.calibration_status == "uncalibrated_ranking"

    def test_result_calibration_disclaimer(self):
        result = self.service.generate_differential(
            findings=["chest pain"],
        )
        assert "ranking" in result.calibration_disclaimer.lower()

    def test_cer_claim_uses_ranking_language(self):
        """CER citation claim should say 'ranking score' not 'probability'."""
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea", "diaphoresis"],
        )
        for dx in result.differential:
            if dx.cer_citation:
                assert "ranking score" in dx.cer_citation.claim
                assert "estimated probability" not in dx.cer_citation.claim

    def test_ranking_score_range(self):
        """Ranking scores should be in [0, 1]."""
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea", "nausea"],
        )
        for dx in result.differential:
            assert 0.0 <= dx.ranking_score <= 1.0

    def test_all_candidates_have_calibration_fields(self):
        """Every candidate must carry calibration metadata."""
        result = self.service.generate_differential(
            findings=["headache", "fever", "neck stiffness"],
        )
        for dx in result.differential:
            assert dx.calibration_status == "uncalibrated_ranking"
            assert len(dx.calibration_disclaimer) > 0
