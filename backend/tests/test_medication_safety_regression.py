"""Medication Safety Regression Tests (P3-020).

A regression suite verifying that the DrugSafetyService correctly detects
known drug interactions, contraindications, dose range issues, and allergy
cross-reactivity scenarios. At least 20 regression cases are included.
"""

import pytest

from app.services.drug_safety import (
    DrugSafetyService,
    SafetyLevel,
    PregnancyCategory,
    reset_drug_safety_service,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the drug safety singleton before each test."""
    reset_drug_safety_service()


@pytest.fixture
def service() -> DrugSafetyService:
    return DrugSafetyService(use_rxnorm=False)


# ============================================================================
# 1. Known Drug Interactions
# ============================================================================


class TestKnownDrugInteractions:
    """Verify detection of well-known drug-drug interactions."""

    def test_warfarin_aspirin_interaction(self, service: DrugSafetyService):
        """Warfarin + aspirin = major bleeding risk."""
        result = service.check_interactions(["warfarin", "aspirin"])
        assert result.total_interactions >= 1
        interaction = result.interactions_found[0]
        assert interaction.severity == "major"
        assert "bleeding" in interaction.description.lower()

    def test_warfarin_ibuprofen_interaction(self, service: DrugSafetyService):
        """Warfarin + ibuprofen = major anticoagulant potentiation."""
        result = service.check_interactions(["warfarin", "ibuprofen"])
        assert result.total_interactions >= 1
        assert result.interactions_found[0].severity == "major"

    def test_methotrexate_nsaid_interaction(self, service: DrugSafetyService):
        """Methotrexate + ibuprofen = methotrexate toxicity."""
        result = service.check_interactions(["methotrexate", "ibuprofen"])
        assert result.total_interactions >= 1
        interaction = result.interactions_found[0]
        assert interaction.severity == "major"
        assert "methotrexate" in interaction.description.lower() or "toxicity" in interaction.description.lower()

    def test_fluoxetine_tramadol_serotonin_syndrome(self, service: DrugSafetyService):
        """Fluoxetine + tramadol = serotonin syndrome risk."""
        result = service.check_interactions(["fluoxetine", "tramadol"])
        assert result.total_interactions >= 1
        interaction = result.interactions_found[0]
        assert "serotonin" in interaction.description.lower() or "serotonin" in interaction.mechanism.lower()

    def test_metformin_contrast_dye_interaction(self, service: DrugSafetyService):
        """Metformin + contrast dye = lactic acidosis risk."""
        result = service.check_interactions(["metformin", "contrast dye"])
        assert result.total_interactions >= 1
        assert "lactic acidosis" in result.interactions_found[0].description.lower()

    def test_digoxin_amiodarone_interaction(self, service: DrugSafetyService):
        """Digoxin + amiodarone = digoxin toxicity via P-gp inhibition."""
        result = service.check_interactions(["digoxin", "amiodarone"])
        assert result.total_interactions >= 1
        assert result.interactions_found[0].severity == "major"

    def test_simvastatin_amiodarone_rhabdomyolysis(self, service: DrugSafetyService):
        """Simvastatin + amiodarone = rhabdomyolysis risk."""
        result = service.check_interactions(["simvastatin", "amiodarone"])
        assert result.total_interactions >= 1
        assert "rhabdomyolysis" in result.interactions_found[0].description.lower()

    def test_ciprofloxacin_theophylline_toxicity(self, service: DrugSafetyService):
        """Ciprofloxacin + theophylline = theophylline toxicity."""
        result = service.check_interactions(["ciprofloxacin", "theophylline"])
        assert result.total_interactions >= 1
        assert result.interactions_found[0].severity == "major"

    def test_omeprazole_clopidogrel_reduced_efficacy(self, service: DrugSafetyService):
        """Omeprazole + clopidogrel = reduced antiplatelet effect."""
        result = service.check_interactions(["omeprazole", "clopidogrel"])
        assert result.total_interactions >= 1
        assert "efficacy" in result.interactions_found[0].description.lower() or "reduced" in result.interactions_found[0].description.lower()

    def test_metoprolol_verapamil_cardiac_depression(self, service: DrugSafetyService):
        """Metoprolol + verapamil = excessive cardiac depression."""
        result = service.check_interactions(["metoprolol", "verapamil"])
        assert result.total_interactions >= 1
        assert result.interactions_found[0].severity == "major"

    def test_no_interaction_safe_pair(self, service: DrugSafetyService):
        """Two drugs without known interaction should return zero."""
        result = service.check_interactions(["amoxicillin", "metformin"])
        assert result.total_interactions == 0


# ============================================================================
# 2. Contraindications
# ============================================================================


class TestContraindications:
    """Verify detection of drug-condition contraindications."""

    def test_ace_inhibitor_pregnancy(self, service: DrugSafetyService):
        """ACE inhibitors (lisinopril) are category D in pregnancy -- triggers warning.

        Lisinopril is pregnancy category D (not X), so the service raises a
        WARNING level rather than CONTRAINDICATED. The pregnancy contraindication
        in the profile only fires when the patient_conditions list contains
        'pregnancy'. The pregnant=True flag uses the pregnancy_category logic.
        """
        result = service.check_safety("lisinopril", pregnant=True)
        # Category D -> WARNING level (category X would be CONTRAINDICATED)
        assert result.overall_safety == SafetyLevel.WARNING
        assert result.pregnancy_warning is not None
        assert "Category D" in result.pregnancy_warning

    def test_warfarin_pregnancy_category_x(self, service: DrugSafetyService):
        """Warfarin is pregnancy category X -- absolute contraindication."""
        result = service.check_safety("warfarin", pregnant=True)
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED
        assert result.profile is not None
        assert result.profile.pregnancy_category == PregnancyCategory.X

    def test_metformin_severe_renal_impairment(self, service: DrugSafetyService):
        """Metformin is contraindicated with eGFR < 30."""
        result = service.check_safety(
            "metformin",
            patient_conditions=["severe renal impairment (eGFR <30)"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED

    def test_ibuprofen_active_gi_bleeding(self, service: DrugSafetyService):
        """NSAIDs contraindicated with active GI bleeding."""
        result = service.check_safety(
            "ibuprofen",
            patient_conditions=["active GI bleeding"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED

    def test_ciprofloxacin_myasthenia_gravis(self, service: DrugSafetyService):
        """Fluoroquinolones contraindicated in myasthenia gravis."""
        result = service.check_safety(
            "ciprofloxacin",
            patient_conditions=["myasthenia gravis"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED

    def test_oxycodone_respiratory_depression(self, service: DrugSafetyService):
        """Opioids contraindicated with significant respiratory depression."""
        result = service.check_safety(
            "oxycodone",
            patient_conditions=["significant respiratory depression"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED

    def test_metoprolol_severe_bradycardia(self, service: DrugSafetyService):
        """Beta-blockers contraindicated with severe bradycardia."""
        result = service.check_safety(
            "metoprolol",
            patient_conditions=["severe bradycardia"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED


# ============================================================================
# 3. Dose Range Validation (adult vs pediatric considerations)
# ============================================================================


class TestDoseRangeConsiderations:
    """Verify age-based dosing considerations are surfaced."""

    def test_geriatric_warfarin_dosing(self, service: DrugSafetyService):
        """Warfarin in elderly patients should trigger geriatric dosing note."""
        result = service.check_safety("warfarin", age=78)
        assert any("geriatric" in d.lower() for d in result.dosing_considerations)

    def test_pediatric_ciprofloxacin_warning(self, service: DrugSafetyService):
        """Ciprofloxacin in children should trigger pediatric caution."""
        result = service.check_safety("ciprofloxacin", age=10)
        assert any("pediatric" in d.lower() for d in result.dosing_considerations)

    def test_geriatric_oxycodone_dosing(self, service: DrugSafetyService):
        """Opioids in elderly require reduced starting dose."""
        result = service.check_safety("oxycodone", age=80)
        assert any("geriatric" in d.lower() for d in result.dosing_considerations)

    def test_renal_dosing_metformin(self, service: DrugSafetyService):
        """Metformin with reduced eGFR should flag renal dosing."""
        result = service.check_safety("metformin", egfr=35.0)
        assert any("renal" in d.lower() for d in result.dosing_considerations)


# ============================================================================
# 4. Allergy Cross-Reactivity
# ============================================================================


class TestAllergyCrossReactivity:
    """Verify allergy and cross-reactivity detection."""

    def test_penicillin_allergy_amoxicillin(self, service: DrugSafetyService):
        """Penicillin allergy should flag amoxicillin as contraindicated."""
        result = service.check_safety(
            "amoxicillin",
            patient_conditions=["penicillin allergy"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED
        ci_conditions = [c[0].lower() for c in result.contraindicated_conditions]
        assert any("penicillin" in c for c in ci_conditions)

    def test_vancomycin_allergy(self, service: DrugSafetyService):
        """Vancomycin allergy should be flagged."""
        result = service.check_safety(
            "vancomycin",
            patient_conditions=["vancomycin allergy"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED


# ============================================================================
# 5. Additional Safety Checks
# ============================================================================


class TestAdditionalSafetyChecks:
    """Miscellaneous safety regression scenarios."""

    def test_unknown_drug_returns_caution(self, service: DrugSafetyService):
        """An unrecognized drug should return CAUTION, not crash."""
        result = service.check_safety("completelyunknowndrug123")
        assert result.overall_safety == SafetyLevel.CAUTION
        assert result.profile is None

    def test_black_box_warnings_surfaced(self, service: DrugSafetyService):
        """Oxycodone should surface black box warnings about addiction/respiratory depression."""
        result = service.check_safety("oxycodone")
        assert result.warnings  # black box warnings present
        assert any("respiratory" in w.lower() for w in result.warnings)

    def test_lactation_warning_oxycodone(self, service: DrugSafetyService):
        """Oxycodone during lactation should surface a warning."""
        result = service.check_safety("oxycodone", lactating=True)
        assert result.lactation_warning is not None
        assert "potentially_hazardous" in result.lactation_warning.lower() or "hazardous" in result.lactation_warning.lower()

    def test_brand_name_resolution_coumadin(self, service: DrugSafetyService):
        """Brand name 'Coumadin' should resolve to warfarin profile."""
        profile = service.get_profile("Coumadin")
        assert profile is not None
        assert profile.generic_name == "warfarin"

    def test_brand_name_resolution_advil(self, service: DrugSafetyService):
        """Brand name 'Advil' should resolve to ibuprofen profile."""
        profile = service.get_profile("Advil")
        assert profile is not None
        assert profile.generic_name == "ibuprofen"

    def test_monitoring_parameters_present(self, service: DrugSafetyService):
        """Warfarin safety check should include INR monitoring."""
        result = service.check_safety("warfarin")
        assert result.monitoring_needed
        assert any("inr" in m.lower() for m in result.monitoring_needed)

    def test_multiple_conditions_evaluated(self, service: DrugSafetyService):
        """Multiple patient conditions should all be evaluated."""
        result = service.check_safety(
            "ibuprofen",
            patient_conditions=["active GI bleeding", "coronary artery disease"],
        )
        assert result.overall_safety == SafetyLevel.CONTRAINDICATED
        # Should have both the contraindication and the warning
        assert len(result.contraindicated_conditions) >= 1
        assert len(result.warnings) >= 1  # black box + coronary artery disease warning

    def test_interaction_coverage_status(self, service: DrugSafetyService):
        """Coverage status should be 'covered' for known drug pairs."""
        result = service.check_interactions(["warfarin", "aspirin"])
        assert result.coverage_status == "covered"

    def test_interaction_coverage_unknown_drug(self, service: DrugSafetyService):
        """Coverage should flag unknown drugs."""
        result = service.check_interactions(["warfarin", "xyzmadeup"])
        assert result.coverage_status in ("partially_covered", "uncovered")
        assert result.drug_coverage_warning is not None
