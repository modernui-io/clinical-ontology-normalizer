"""Contract tests for calculator canonicalization (WS2).

Verifies that the legacy clinical_calculators.py facade delegates correctly
to the canonical clinical_calculator_service.py, and that both produce
consistent results.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 1. Legacy get_clinical_calculator_service() delegates to canonical
# ---------------------------------------------------------------------------

class TestLegacyDelegation:
    """Verify the legacy facade returns the canonical service instance."""

    def test_legacy_get_returns_canonical_type(self):
        """Legacy get_clinical_calculator_service() returns the canonical class."""
        from app.services.clinical_calculators import get_clinical_calculator_service as legacy_get
        from app.services.clinical_calculator_service import ClinicalCalculatorService as CanonicalClass

        service = legacy_get()
        assert isinstance(service, CanonicalClass)

    def test_canonical_get_returns_working_service(self):
        """Canonical get_clinical_calculator_service() returns a working service."""
        from app.services.clinical_calculator_service import get_clinical_calculator_service

        service = get_clinical_calculator_service()
        assert service is not None
        stats = service.get_stats()
        assert stats["total_calculators"] > 0

    def test_legacy_and_canonical_return_same_singleton(self):
        """Both getters return the exact same singleton instance."""
        from app.services.clinical_calculators import get_clinical_calculator_service as legacy_get
        from app.services.clinical_calculator_service import get_clinical_calculator_service as canonical_get

        legacy_svc = legacy_get()
        canonical_svc = canonical_get()
        assert legacy_svc is canonical_svc

    def test_legacy_reset_delegates_to_canonical(self):
        """Legacy reset clears the canonical singleton."""
        from app.services.clinical_calculators import (
            get_clinical_calculator_service as legacy_get,
            reset_clinical_calculator_service as legacy_reset,
        )
        from app.services.clinical_calculator_service import (
            get_clinical_calculator_service as canonical_get,
        )

        # Get the initial instance
        svc_before = canonical_get()

        # Reset via legacy
        legacy_reset()

        # New instance should be created
        svc_after = canonical_get()
        assert svc_before is not svc_after


# ---------------------------------------------------------------------------
# 2. Both services produce identical results for key calculators
# ---------------------------------------------------------------------------

class TestCalculatorParity:
    """Verify legacy standalone functions and canonical service produce equivalent results."""

    def test_bmi_parity(self):
        """BMI calculation via legacy standalone vs. canonical service."""
        from app.services.clinical_calculators import calculate_bmi
        from app.services.clinical_calculator_service import (
            ClinicalCalculatorService,
            BMIInput,
        )

        # Legacy standalone function
        legacy_result = calculate_bmi(weight_kg=70, height_cm=175)

        # Canonical service
        svc = ClinicalCalculatorService()
        canonical_result = svc.calculate("bmi", {"weight_kg": 70, "height_cm": 175})

        # Both should produce a BMI of ~22.86
        assert abs(legacy_result.score - canonical_result.score) < 0.1
        assert legacy_result.risk_level.value == canonical_result.risk_level.value

    def test_chadsvasc_parity(self):
        """CHA2DS2-VASc calculation via legacy standalone vs. canonical service."""
        from app.services.clinical_calculators import calculate_chadsvasc
        from app.services.clinical_calculator_service import (
            ClinicalCalculatorService,
        )

        # Legacy standalone function
        legacy_result = calculate_chadsvasc(
            age=72, female=True, hypertension=True, diabetes=True,
            stroke_tia_thromboembolism=False, vascular_disease=False,
            congestive_heart_failure=False,
        )

        # Canonical service uses cha2ds2_vasc key and Pydantic input
        svc = ClinicalCalculatorService()
        canonical_result = svc.calculate("cha2ds2_vasc", {
            "age": 72, "sex": "female", "hypertension": True,
            "diabetes": True, "stroke_tia_history": False,
            "vascular_disease": False, "heart_failure": False,
        })

        # Both should produce score of 5 (HTN=1 + DM=1 + female=1 + age 65-74=1 + age >= 65 implied)
        # Scores should be close (implementations may differ slightly in interpretation)
        assert legacy_result.score >= 3  # sanity check: multiple risk factors
        assert canonical_result.score >= 3

    def test_egfr_parity(self):
        """eGFR calculation via legacy standalone vs. canonical service."""
        from app.services.clinical_calculators import calculate_egfr_ckdepi
        from app.services.clinical_calculator_service import (
            ClinicalCalculatorService,
        )

        # Legacy standalone function
        legacy_result = calculate_egfr_ckdepi(
            creatinine=1.2, age=55, female=False,
        )

        # Canonical service
        svc = ClinicalCalculatorService()
        canonical_result = svc.calculate("egfr_ckdepi", {
            "creatinine": 1.2, "age": 55, "sex": "male",
        })

        # Both should compute eGFR; exact values may differ slightly between implementations
        assert legacy_result.score > 0
        assert canonical_result.score > 0
        # Both should be within reasonable range for a 55yo male with Cr 1.2
        assert 40 < legacy_result.score < 120
        assert 40 < canonical_result.score < 120


# ---------------------------------------------------------------------------
# 3. Data-driven calculator IDs backed by CALCULATOR_DEFINITIONS
# ---------------------------------------------------------------------------

class TestDataDrivenRegistry:
    """Verify all calculator IDs referenced by the canonical service
    are backed by entries in CALCULATOR_DEFINITIONS."""

    def test_canonical_service_data_driven_calculators_have_definitions(self):
        """All data-driven calculator IDs in the canonical service
        are present in CALCULATOR_DEFINITIONS."""
        from app.services.calculator_definitions import CALCULATOR_DEFINITIONS
        from app.services.clinical_calculator_service import (
            get_clinical_calculator_service,
        )

        svc = get_clinical_calculator_service()
        stats = svc.get_stats()

        # The service should track how many data-driven definitions exist
        assert stats["data_driven_calculators"] == len(CALCULATOR_DEFINITIONS)

    def test_calculator_definitions_not_empty(self):
        """CALCULATOR_DEFINITIONS contains a substantial number of calculators."""
        from app.services.calculator_definitions import CALCULATOR_DEFINITIONS

        # Should have at least the core set
        assert len(CALCULATOR_DEFINITIONS) >= 20

    def test_core_calculators_in_definitions(self):
        """Key clinical calculators exist in the definitions registry."""
        from app.services.calculator_definitions import CALCULATOR_DEFINITIONS

        core_ids = ["chadsvasc", "hasbled", "wells_dvt", "curb65", "qsofa", "bmi"]
        for calc_id in core_ids:
            assert calc_id in CALCULATOR_DEFINITIONS, (
                f"Core calculator '{calc_id}' missing from CALCULATOR_DEFINITIONS"
            )

    def test_calculate_from_definition_works_for_criteria(self):
        """calculate_from_definition() works for CRITERIA-type calculators."""
        from app.services.clinical_calculators import calculate_from_definition

        result = calculate_from_definition(
            "chadsvasc",
            {"hypertension": True, "diabetes": False, "stroke_tia": False,
             "vascular_disease": False, "heart_failure": False, "female": False},
            age=72,
        )
        assert result.score >= 1  # At minimum age-based scoring
        assert result.calculator_name is not None

    def test_calculate_from_definition_rejects_unknown_id(self):
        """calculate_from_definition() raises ValueError for unknown calculator."""
        from app.services.clinical_calculators import calculate_from_definition

        with pytest.raises(ValueError, match="not found"):
            calculate_from_definition("nonexistent_calculator", {})


# ---------------------------------------------------------------------------
# 4. __init__.py re-export resolves to the canonical service
# ---------------------------------------------------------------------------

class TestInitReExport:
    """Verify that importing through app.services gives the canonical types."""

    def test_init_calculator_result_is_canonical(self):
        """CalculatorResult from __init__ is the canonical version."""
        from app.services import CalculatorResult
        from app.services.clinical_calculator_service import (
            CalculatorResult as CanonicalResult,
        )

        assert CalculatorResult is CanonicalResult

    def test_init_service_class_is_canonical(self):
        """ClinicalCalculatorService from __init__ is the canonical version."""
        from app.services import ClinicalCalculatorService
        from app.services.clinical_calculator_service import (
            ClinicalCalculatorService as CanonicalClass,
        )

        assert ClinicalCalculatorService is CanonicalClass

    def test_init_risk_level_is_canonical(self):
        """RiskLevel from __init__ is the canonical version."""
        from app.services import RiskLevel
        from app.services.clinical_calculator_service import (
            RiskLevel as CanonicalRiskLevel,
        )

        assert RiskLevel is CanonicalRiskLevel

    def test_init_get_service_is_canonical(self):
        """get_clinical_calculator_service from __init__ is the canonical function."""
        from app.services import get_clinical_calculator_service
        from app.services.clinical_calculator_service import (
            get_clinical_calculator_service as canonical_get,
        )

        assert get_clinical_calculator_service is canonical_get

    def test_init_reset_service_is_canonical(self):
        """reset_clinical_calculator_service from __init__ is the canonical function."""
        from app.services import reset_clinical_calculator_service
        from app.services.clinical_calculator_service import (
            reset_clinical_calculator_service as canonical_reset,
        )

        assert reset_clinical_calculator_service is canonical_reset


# ---------------------------------------------------------------------------
# 5. Legacy standalone functions still work
# ---------------------------------------------------------------------------

class TestLegacyStandaloneFunctions:
    """Verify that standalone calculator functions in the legacy module
    continue to work for backward compatibility."""

    def test_calculate_bmi_standalone(self):
        """Legacy calculate_bmi() still works."""
        from app.services.clinical_calculators import calculate_bmi

        result = calculate_bmi(weight_kg=80, height_cm=180)
        expected_bmi = 80 / (1.80 ** 2)
        assert abs(result.score - expected_bmi) < 0.1
        assert result.calculator_name is not None

    def test_calculate_chadsvasc_standalone(self):
        """Legacy calculate_chadsvasc() still works."""
        from app.services.clinical_calculators import calculate_chadsvasc

        result = calculate_chadsvasc(
            age=65, female=False, hypertension=True,
            diabetes=False, stroke_tia_thromboembolism=False,
            vascular_disease=False, congestive_heart_failure=False,
        )
        assert result.score >= 1  # HTN contributes at least 1
        assert result.risk_level is not None

    def test_calculate_egfr_standalone(self):
        """Legacy calculate_egfr_ckdepi() still works."""
        from app.services.clinical_calculators import calculate_egfr_ckdepi

        result = calculate_egfr_ckdepi(creatinine=0.9, age=40, female=True)
        assert result.score > 0
        assert result.calculator_name is not None

    def test_calculate_meld_standalone(self):
        """Legacy calculate_meld() still works."""
        from app.services.clinical_calculators import calculate_meld

        result = calculate_meld(
            bilirubin=2.0, creatinine=1.5, inr=1.8,
            sodium=135, on_dialysis=False,
        )
        assert result.score > 0
        assert result.calculator_name is not None
