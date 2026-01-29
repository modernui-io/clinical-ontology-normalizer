"""Tests for Clinical Risk Calculators Service.

Tests the clinical risk calculator functionality.
"""

import pytest

from app.services.clinical_calculators import (
    ClinicalCalculatorService,
    RiskLevel,
    CalculatorResult,
    get_clinical_calculator_service,
    reset_clinical_calculator_service,
    calculate_bmi,
    calculate_chadsvasc,
    calculate_hasbled,
    calculate_meld,
    calculate_egfr_ckdepi,
    calculate_wells_dvt,
    calculate_curb65,
    calculate_framingham_10yr,
    calculate_from_definition,
    get_data_driven_calculators,
)


# ============================================================================
# Service Tests
# ============================================================================


class TestServiceInit:
    """Test service initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_clinical_calculator_service()

    def test_service_creation(self):
        """Test basic service creation."""
        service = ClinicalCalculatorService()
        assert service is not None

    def test_singleton_pattern(self):
        """Test singleton pattern works."""
        service1 = get_clinical_calculator_service()
        service2 = get_clinical_calculator_service()
        assert service1 is service2

    def test_singleton_reset(self):
        """Test singleton can be reset."""
        service1 = get_clinical_calculator_service()
        reset_clinical_calculator_service()
        service2 = get_clinical_calculator_service()
        assert service1 is not service2

    def test_get_available_calculators(self):
        """Test listing available calculators."""
        service = ClinicalCalculatorService()
        calcs = service.get_available_calculators()

        assert "bmi" in calcs
        assert "chadsvasc" in calcs
        assert "meld" in calcs
        assert "egfr" in calcs

    def test_calculate_unknown_raises(self):
        """Test that unknown calculator raises ValueError."""
        service = ClinicalCalculatorService()
        with pytest.raises(ValueError):
            service.calculate("unknown_calculator")


# ============================================================================
# BMI Tests
# ============================================================================


class TestBMI:
    """Test BMI calculator."""

    def test_normal_bmi(self):
        """Test normal BMI calculation."""
        result = calculate_bmi(weight_kg=70, height_cm=175)

        assert result.calculator_name == "Body Mass Index (BMI)"
        assert 22 < result.score < 24
        assert result.risk_level == RiskLevel.LOW
        assert "Normal" in result.interpretation

    def test_underweight_bmi(self):
        """Test underweight BMI."""
        result = calculate_bmi(weight_kg=50, height_cm=175)

        assert result.score < 18.5
        assert result.risk_level == RiskLevel.MODERATE
        assert "Underweight" in result.interpretation

    def test_overweight_bmi(self):
        """Test overweight BMI."""
        result = calculate_bmi(weight_kg=85, height_cm=175)

        assert 25 <= result.score < 30
        assert result.risk_level == RiskLevel.MODERATE
        assert "Overweight" in result.interpretation

    def test_obese_bmi(self):
        """Test obese BMI."""
        result = calculate_bmi(weight_kg=110, height_cm=175)

        assert result.score >= 30
        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]

    def test_via_service(self):
        """Test BMI calculation via service."""
        service = ClinicalCalculatorService()
        result = service.calculate("bmi", weight_kg=70, height_cm=175)
        assert result.score > 0


# ============================================================================
# CHA₂DS₂-VASc Tests
# ============================================================================


class TestCHADSVASc:
    """Test CHA₂DS₂-VASc calculator."""

    def test_zero_score(self):
        """Test zero score (low risk)."""
        result = calculate_chadsvasc(
            age=50, female=False,
            hypertension=False, diabetes=False
        )

        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_female_adds_point(self):
        """Test female sex adds 1 point."""
        male = calculate_chadsvasc(age=50, female=False)
        female = calculate_chadsvasc(age=50, female=True)

        assert female.score == male.score + 1

    def test_age_75_adds_two_points(self):
        """Test age ≥75 adds 2 points."""
        young = calculate_chadsvasc(age=50, female=False)
        old = calculate_chadsvasc(age=75, female=False)

        assert old.score == young.score + 2

    def test_prior_stroke_adds_two_points(self):
        """Test prior stroke adds 2 points."""
        no_stroke = calculate_chadsvasc(age=50, female=False)
        stroke = calculate_chadsvasc(
            age=50, female=False, stroke_tia_thromboembolism=True
        )

        assert stroke.score == no_stroke.score + 2

    def test_high_risk_patient(self):
        """Test high risk patient with multiple factors."""
        result = calculate_chadsvasc(
            age=75, female=True,
            congestive_heart_failure=True,
            hypertension=True,
            diabetes=True,
            stroke_tia_thromboembolism=True,
        )

        assert result.score >= 6
        assert result.risk_level == RiskLevel.VERY_HIGH


# ============================================================================
# HAS-BLED Tests
# ============================================================================


class TestHASBLED:
    """Test HAS-BLED calculator."""

    def test_zero_score(self):
        """Test zero score (low risk)."""
        result = calculate_hasbled()

        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_high_score(self):
        """Test high score (high risk)."""
        result = calculate_hasbled(
            hypertension=True,
            renal_disease=True,
            liver_disease=True,
            stroke_history=True,
            bleeding_history=True,
        )

        assert result.score >= 5
        assert result.risk_level == RiskLevel.HIGH


# ============================================================================
# MELD Tests
# ============================================================================


class TestMELD:
    """Test MELD calculator."""

    def test_normal_values(self):
        """Test MELD with normal values."""
        result = calculate_meld(
            creatinine=1.0,
            bilirubin=1.0,
            inr=1.0,
        )

        assert result.score < 10
        assert result.risk_level == RiskLevel.LOW

    def test_elevated_values(self):
        """Test MELD with elevated values."""
        result = calculate_meld(
            creatinine=2.5,
            bilirubin=4.0,
            inr=2.0,
        )

        assert result.score > 15
        assert result.risk_level in [RiskLevel.MODERATE, RiskLevel.HIGH]

    def test_dialysis_adjustment(self):
        """Test MELD with dialysis (creatinine capped at 4)."""
        no_dialysis = calculate_meld(creatinine=2.0, bilirubin=2.0, inr=1.5)
        dialysis = calculate_meld(
            creatinine=2.0, bilirubin=2.0, inr=1.5, on_dialysis=True
        )

        assert dialysis.score > no_dialysis.score

    def test_meld_na(self):
        """Test MELD-Na with sodium."""
        result = calculate_meld(
            creatinine=1.5,
            bilirubin=3.0,
            inr=1.5,
            sodium=128,  # Low sodium
        )

        assert "MELD-Na" in result.calculator_name
        assert "sodium" in result.components


# ============================================================================
# eGFR Tests
# ============================================================================


class TestEGFR:
    """Test eGFR calculator."""

    def test_normal_egfr(self):
        """Test normal eGFR."""
        result = calculate_egfr_ckdepi(
            creatinine=1.0, age=40, female=False
        )

        assert result.score >= 90
        assert result.risk_level == RiskLevel.LOW
        assert "G1" in result.interpretation

    def test_moderately_decreased(self):
        """Test moderately decreased eGFR."""
        result = calculate_egfr_ckdepi(
            creatinine=1.8, age=65, female=False
        )

        assert 30 < result.score < 60
        assert "G3" in result.interpretation

    def test_severely_decreased(self):
        """Test severely decreased eGFR."""
        result = calculate_egfr_ckdepi(
            creatinine=4.0, age=70, female=False
        )

        assert result.score < 30
        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]

    def test_female_adjustment(self):
        """Test female adjustment in eGFR."""
        male = calculate_egfr_ckdepi(creatinine=1.0, age=50, female=False)
        female = calculate_egfr_ckdepi(creatinine=1.0, age=50, female=True)

        # Female should have slightly higher eGFR for same creatinine
        assert female.score != male.score


# ============================================================================
# Wells DVT Tests
# ============================================================================


class TestWellsDVT:
    """Test Wells DVT calculator."""

    def test_zero_score(self):
        """Test zero score (low probability)."""
        result = calculate_wells_dvt()

        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_moderate_score(self):
        """Test moderate score."""
        result = calculate_wells_dvt(
            localized_tenderness=True,
            calf_swelling_3cm=True,
        )

        assert result.score == 2
        assert result.risk_level == RiskLevel.MODERATE

    def test_high_score(self):
        """Test high score."""
        result = calculate_wells_dvt(
            active_cancer=True,
            paralysis_immobilization=True,
            localized_tenderness=True,
            entire_leg_swollen=True,
            pitting_edema=True,
        )

        assert result.score >= 3
        assert result.risk_level == RiskLevel.HIGH

    def test_alternative_diagnosis_subtracts(self):
        """Test alternative diagnosis subtracts 2 points."""
        with_alt = calculate_wells_dvt(
            localized_tenderness=True,
            alternative_diagnosis_likely=True,
        )
        without_alt = calculate_wells_dvt(localized_tenderness=True)

        assert with_alt.score == without_alt.score - 2


# ============================================================================
# CURB-65 Tests
# ============================================================================


class TestCURB65:
    """Test CURB-65 calculator."""

    def test_zero_score(self):
        """Test zero score (outpatient)."""
        result = calculate_curb65()

        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW
        assert "outpatient" in result.interpretation.lower()

    def test_moderate_score(self):
        """Test moderate score (consider admission)."""
        result = calculate_curb65(
            confusion=True,
            bun_over_19=True,
        )

        assert result.score == 2
        assert result.risk_level == RiskLevel.MODERATE

    def test_high_score(self):
        """Test high score (ICU)."""
        result = calculate_curb65(
            confusion=True,
            bun_over_19=True,
            respiratory_rate_over_30=True,
            sbp_under_90_or_dbp_under_60=True,
            age_65_or_older=True,
        )

        assert result.score == 5
        assert result.risk_level == RiskLevel.VERY_HIGH


# ============================================================================
# Framingham Tests
# ============================================================================


class TestFramingham:
    """Test Framingham 10-year CVD risk calculator."""

    def test_low_risk_young(self):
        """Test low risk young patient."""
        result = calculate_framingham_10yr(
            age=35, female=False,
            total_cholesterol=180,
            hdl_cholesterol=55,
            systolic_bp=115,
        )

        assert result.score < 10
        assert result.risk_level in [RiskLevel.LOW, RiskLevel.LOW_MODERATE]

    def test_high_risk_multiple_factors(self):
        """Test high risk with multiple factors."""
        result = calculate_framingham_10yr(
            age=65, female=False,
            total_cholesterol=260,
            hdl_cholesterol=35,
            systolic_bp=160,
            bp_treated=True,
            smoker=True,
            diabetic=True,
        )

        assert result.score >= 20
        assert result.risk_level == RiskLevel.HIGH

    def test_female_vs_male_risk(self):
        """Test female generally lower risk than male."""
        male = calculate_framingham_10yr(
            age=55, female=False,
            total_cholesterol=220,
            hdl_cholesterol=45,
            systolic_bp=140,
        )
        female = calculate_framingham_10yr(
            age=55, female=True,
            total_cholesterol=220,
            hdl_cholesterol=45,
            systolic_bp=140,
        )

        # Female generally has lower risk
        assert female.score <= male.score


# ============================================================================
# Result Structure Tests
# ============================================================================


class TestResultStructure:
    """Test calculator result structure."""

    def test_result_has_required_fields(self):
        """Test that results have all required fields."""
        result = calculate_bmi(weight_kg=70, height_cm=175)

        assert hasattr(result, "calculator_name")
        assert hasattr(result, "score")
        assert hasattr(result, "score_unit")
        assert hasattr(result, "risk_level")
        assert hasattr(result, "interpretation")
        assert hasattr(result, "recommendations")
        assert hasattr(result, "components")
        assert hasattr(result, "references")

    def test_recommendations_not_empty(self):
        """Test that recommendations are provided."""
        result = calculate_chadsvasc(age=75, female=True, hypertension=True)
        assert len(result.recommendations) > 0

    def test_references_provided(self):
        """Test that references are provided."""
        result = calculate_curb65()
        assert len(result.references) > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for clinical calculator service."""

    def setup_method(self):
        """Create service for testing."""
        reset_clinical_calculator_service()
        self.service = ClinicalCalculatorService()

    def test_all_calculators_run(self):
        """Test that all calculators can run without error."""
        # BMI
        self.service.calculate("bmi", weight_kg=70, height_cm=175)

        # CHA₂DS₂-VASc
        self.service.calculate("chadsvasc", age=70, female=True)

        # HAS-BLED
        self.service.calculate("hasbled")

        # MELD
        self.service.calculate("meld", creatinine=1.5, bilirubin=2.0, inr=1.5)

        # eGFR
        self.service.calculate("egfr", creatinine=1.2, age=60, female=False)

        # Wells DVT
        self.service.calculate("wells_dvt")

        # CURB-65
        self.service.calculate("curb65")

        # Framingham
        self.service.calculate(
            "framingham",
            age=55, female=False,
            total_cholesterol=200, hdl_cholesterol=50, systolic_bp=130
        )

    def test_stats(self):
        """Test service statistics."""
        stats = self.service.get_stats()

        assert stats["total_calculators"] == 42
        assert "bmi" in stats["calculator_list"]


# ============================================================================
# Data-Driven Calculator Tests
# ============================================================================


class TestDataDrivenCalculators:
    """Test data-driven calculator integration."""

    def test_get_data_driven_calculators(self):
        """Test listing data-driven calculators."""
        calcs = get_data_driven_calculators()
        assert len(calcs) > 0
        assert "chadsvasc" in calcs
        assert "hasbled" in calcs
        assert "wells_dvt" in calcs
        assert "curb65" in calcs

    def test_calculate_from_definition_chadsvasc(self):
        """Test CHA2DS2-VASc via data-driven approach."""
        result = calculate_from_definition(
            "chadsvasc",
            {
                "hypertension": True,
                "diabetes": True,
                "vascular_disease": True,
            },
            age=72,
        )

        # HTN(1) + DM(1) + Vascular(1) + Age65-74(1) = 4
        assert result.score == 4
        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.MODERATE]
        assert "CHA" in result.calculator_name

    def test_calculate_from_definition_wells_dvt(self):
        """Test Wells DVT via data-driven approach."""
        result = calculate_from_definition(
            "wells_dvt",
            {
                "active_cancer": True,
                "calf_swelling": True,
                "pitting_edema": True,
            },
        )

        # Cancer(1) + Calf(1) + Edema(1) = 3
        assert result.score == 3
        assert "Wells" in result.calculator_name

    def test_calculate_from_definition_curb65(self):
        """Test CURB-65 via data-driven approach."""
        result = calculate_from_definition(
            "curb65",
            {
                "confusion": True,
                "uremia": True,
                "respiratory_rate": True,
                "low_blood_pressure": True,
                "age_65_or_older": True,
            },
        )

        assert result.score == 5
        assert result.risk_level == RiskLevel.VERY_HIGH

    def test_data_driven_unknown_raises(self):
        """Test unknown calculator raises ValueError."""
        with pytest.raises(ValueError):
            calculate_from_definition("not_a_real_calculator", {})

    def test_data_driven_equation_type_raises(self):
        """Test that EQUATION type calculators raise ValueError."""
        # BMI is an EQUATION type, should raise
        with pytest.raises(ValueError, match="equation"):
            calculate_from_definition("bmi", {"weight_kg": 70, "height_cm": 175})
