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


# ============================================================================
# Specialty Calculators Tests - Neurology
# ============================================================================


class TestNeurologyCalculators:
    """Test neurology specialty calculators."""

    def test_nihss_minor_stroke(self):
        """Test NIHSS for minor stroke."""
        result = calculate_from_definition(
            "nihss",
            {
                "loc_alert": True,  # 0
                "loc_questions_both_correct": True,  # 0
                "loc_commands_both_correct": True,  # 0
                "gaze_normal": True,  # 0
                "visual_normal": True,  # 0
                "facial_minor": True,  # 1
                "motor_left_arm_normal": True,  # 0
                "motor_right_arm_normal": True,  # 0
                "motor_left_leg_normal": True,  # 0
                "motor_right_leg_normal": True,  # 0
                "ataxia_absent": True,  # 0
                "sensory_normal": True,  # 0
                "language_normal": True,  # 0
                "dysarthria_normal": True,  # 0
                "extinction_normal": True,  # 0
            },
        )
        assert result.score == 1
        assert result.risk_level == RiskLevel.LOW
        assert "Minor" in result.interpretation

    def test_nihss_moderate_stroke(self):
        """Test NIHSS for moderate stroke."""
        result = calculate_from_definition(
            "nihss",
            {
                "loc_drowsy": True,  # 1
                "loc_questions_one_correct": True,  # 1
                "loc_commands_both_correct": True,  # 0
                "gaze_partial": True,  # 1
                "visual_partial": True,  # 1
                "facial_partial": True,  # 2
                "motor_left_arm_drift": True,  # 1
                "motor_right_arm_normal": True,  # 0
                "motor_left_leg_drift": True,  # 1
                "motor_right_leg_normal": True,  # 0
                "ataxia_absent": True,  # 0
                "sensory_mild": True,  # 1
                "language_mild": True,  # 1
                "dysarthria_mild": True,  # 1
                "extinction_normal": True,  # 0
            },
        )
        # Score: 1+1+0+1+1+2+1+0+1+0+0+1+1+1+0 = 11
        assert result.score == 11
        assert result.risk_level == RiskLevel.MODERATE

    def test_hunt_hess_good_grade(self):
        """Test Hunt & Hess for good grade SAH."""
        result = calculate_from_definition(
            "hunt_hess",
            {"grade_grade_1": True},
        )
        assert result.score == 1
        assert result.risk_level == RiskLevel.LOW

    def test_hunt_hess_poor_grade(self):
        """Test Hunt & Hess for poor grade SAH."""
        result = calculate_from_definition(
            "hunt_hess",
            {"grade_grade_5": True},
        )
        assert result.score == 5
        assert result.risk_level == RiskLevel.VERY_HIGH

    def test_ich_score_low_risk(self):
        """Test ICH Score for low mortality risk."""
        result = calculate_from_definition(
            "ich_score",
            {
                "gcs_13_15": True,  # 0
                "volume_lt_30": True,  # 0
                "ivh_no": True,  # 0
                "infratentorial_no": True,  # 0
                "age_lt_80": True,  # 0
            },
        )
        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_ich_score_high_risk(self):
        """Test ICH Score for high mortality risk."""
        result = calculate_from_definition(
            "ich_score",
            {
                "gcs_3_4": True,  # 2
                "volume_gte_30": True,  # 1
                "ivh_yes": True,  # 1
                "infratentorial_yes": True,  # 1
                "age_gte_80": True,  # 1
            },
        )
        assert result.score == 6
        assert result.risk_level == RiskLevel.VERY_HIGH

    def test_four_score_severe(self):
        """Test FOUR Score for severe impairment."""
        result = calculate_from_definition(
            "four_score",
            {
                "eye_e0": True,  # 0
                "motor_m0": True,  # 0
                "brainstem_b0": True,  # 0
                "respiration_r0": True,  # 0
            },
        )
        assert result.score == 0
        assert result.risk_level == RiskLevel.VERY_HIGH

    def test_mrs_good_outcome(self):
        """Test mRS for good outcome."""
        result = calculate_from_definition(
            "mrs",
            {"grade_grade_1": True},
        )
        assert result.score == 1
        assert result.risk_level == RiskLevel.LOW

    def test_canadian_ct_head_positive(self):
        """Test Canadian CT Head Rule - CT indicated."""
        result = calculate_from_definition(
            "canadian_ct_head",
            {
                "gcs_below_15_at_2hr": True,
                "vomiting_2_episodes": True,
            },
        )
        assert result.score == 2
        assert result.risk_level == RiskLevel.HIGH


# ============================================================================
# Specialty Calculators Tests - Oncology
# ============================================================================


class TestOncologyCalculators:
    """Test oncology specialty calculators."""

    def test_ecog_fully_active(self):
        """Test ECOG PS 0."""
        result = calculate_from_definition(
            "ecog",
            {"status_ps_0": True},
        )
        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_ecog_bedridden(self):
        """Test ECOG PS 4."""
        result = calculate_from_definition(
            "ecog",
            {"status_ps_4": True},
        )
        assert result.score == 4
        assert result.risk_level == RiskLevel.HIGH

    def test_karnofsky_normal(self):
        """Test Karnofsky 100%."""
        result = calculate_from_definition(
            "karnofsky",
            {"status_kps_100": True},
        )
        assert result.score == 100
        assert result.risk_level == RiskLevel.LOW

    def test_ipi_low_risk(self):
        """Test IPI low risk."""
        result = calculate_from_definition(
            "ipi",
            {
                "age_over_60": False,
                "stage_iii_iv": False,
                "elevated_ldh": False,
                "ecog_2_plus": False,
                "extranodal_sites_gt_1": False,
            },
        )
        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_ipi_high_risk(self):
        """Test IPI high risk."""
        result = calculate_from_definition(
            "ipi",
            {
                "age_over_60": True,
                "stage_iii_iv": True,
                "elevated_ldh": True,
                "ecog_2_plus": True,
                "extranodal_sites_gt_1": True,
            },
        )
        assert result.score == 5
        assert result.risk_level == RiskLevel.HIGH

    def test_mascc_low_risk(self):
        """Test MASCC low risk febrile neutropenia."""
        result = calculate_from_definition(
            "mascc",
            {
                "symptoms_no_or_mild": True,  # 5
                "hypotension_no": True,  # 5
                "copd_no": True,  # 4
                "solid_tumor_solid_or_no_fungal": True,  # 4
                "dehydration_no": True,  # 3
                "outpatient_outpatient": True,  # 3
                "age_lt_60": True,  # 2
            },
        )
        # 5+5+4+4+3+3+2 = 26
        assert result.score == 26
        assert result.risk_level == RiskLevel.LOW

    def test_khorana_high_risk(self):
        """Test Khorana VTE high risk."""
        result = calculate_from_definition(
            "khorana",
            {
                "cancer_site_very_high_risk": True,  # 2
                "platelet_gte_350": True,  # 1
                "hemoglobin_lt_10": True,  # 1
                "leukocyte_gt_11": True,  # 1
                "bmi_gte_35": True,  # 1
            },
        )
        assert result.score == 6
        assert result.risk_level == RiskLevel.HIGH


# ============================================================================
# Specialty Calculators Tests - Obstetrics
# ============================================================================


class TestObstetricCalculators:
    """Test obstetric specialty calculators."""

    def test_bpp_normal(self):
        """Test normal BPP score."""
        result = calculate_from_definition(
            "bpp",
            {
                "nst_reactive": True,  # 2
                "breathing_present": True,  # 2
                "movement_present": True,  # 2
                "tone_present": True,  # 2
                "afi_normal": True,  # 2
            },
        )
        assert result.score == 10
        assert result.risk_level == RiskLevel.LOW

    def test_bpp_abnormal(self):
        """Test abnormal BPP score."""
        result = calculate_from_definition(
            "bpp",
            {
                "nst_nonreactive": True,  # 0
                "breathing_absent": True,  # 0
                "movement_absent": True,  # 0
                "tone_absent": True,  # 0
                "afi_low": True,  # 0
            },
        )
        assert result.score == 0
        assert result.risk_level == RiskLevel.HIGH

    def test_epds_low_score(self):
        """Test EPDS with low depression risk."""
        result = calculate_from_definition(
            "epds",
            {
                "q1_laugh_0": True,
                "q2_enjoyment_0": True,
                "q3_blame_0": True,
                "q4_anxious_0": True,
                "q5_scared_0": True,
                "q6_overwhelmed_0": True,
                "q7_unhappy_sleep_0": True,
                "q8_sad_0": True,
                "q9_crying_0": True,
                "q10_self_harm_0": True,
            },
        )
        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_preeclampsia_high_risk(self):
        """Test preeclampsia risk with high-risk factors."""
        result = calculate_from_definition(
            "preeclampsia_risk",
            {
                "prior_preeclampsia": True,  # 2
                "chronic_hypertension": True,  # 2
            },
        )
        assert result.score == 4
        assert result.risk_level == RiskLevel.HIGH


# ============================================================================
# Specialty Calculators Tests - Pediatrics
# ============================================================================


class TestPediatricCalculators:
    """Test pediatric specialty calculators."""

    def test_pecarn_low_risk(self):
        """Test PECARN low risk for head CT."""
        result = calculate_from_definition(
            "pecarn_head",
            {
                "gcs_below_15": False,
                "altered_mental_status": False,
                "palpable_skull_fracture": False,
                "scalp_hematoma": False,
                "loc_5_sec": False,
                "severe_mechanism": False,
                "not_acting_normally": False,
                "signs_basilar_skull_fx": False,
                "severe_headache": False,
                "vomiting": False,
            },
        )
        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_westley_croup_severe(self):
        """Test Westley Croup Score for severe croup."""
        result = calculate_from_definition(
            "westley_croup",
            {
                "stridor_at_rest_severe": True,  # 2
                "retractions_severe": True,  # 3
                "air_entry_markedly_decreased": True,  # 2
                "cyanosis_at_rest": True,  # 5
                "consciousness_normal": True,  # 0
            },
        )
        assert result.score == 12
        assert result.risk_level == RiskLevel.HIGH

    def test_pediatric_appendicitis_high(self):
        """Test PAS for high probability appendicitis."""
        result = calculate_from_definition(
            "pediatric_appendicitis",
            {
                "anorexia": True,  # 1
                "nausea_vomiting": True,  # 1
                "migration_pain": True,  # 1
                "fever": True,  # 1
                "cough_percussion_tenderness": True,  # 2
                "rlq_tenderness": True,  # 2
                "leukocytosis": True,  # 1
                "neutrophilia": True,  # 1
            },
        )
        assert result.score == 10
        assert result.risk_level == RiskLevel.HIGH

    def test_yale_observation_low_risk(self):
        """Test Yale Observation Scale for low risk."""
        result = calculate_from_definition(
            "yale_observation",
            {
                "cry_quality_strong_normal": True,  # 1
                "reaction_parent_cries_briefly": True,  # 1
                "state_variation_stays_awake": True,  # 1
                "color_pink": True,  # 1
                "hydration_skin_normal": True,  # 1
                "response_social_smiles_alert": True,  # 1
            },
        )
        assert result.score == 6
        assert result.risk_level == RiskLevel.LOW
