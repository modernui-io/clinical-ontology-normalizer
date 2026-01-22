"""Tests for Advanced NLP Post-Processing Service."""

import pytest
from uuid import uuid4

from app.schemas.base import Assertion, Domain, Experiencer, Temporality
# Import directly from module file to avoid __init__.py dependency chain
from app.services.nlp import ExtractedMention
from app.services.nlp_advanced import (
    AdvancedNLPConfig,
    AdvancedNLPService,
    AbbreviationContext,
    EnhancedMention,
    Laterality,
    MentionEnhancement,
    get_advanced_nlp_service,
    reset_advanced_nlp_service,
)

# Skip collection of conftest to avoid sentence_transformers dependency
pytest_plugins = []


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def service():
    """Create a fresh service for each test."""
    reset_advanced_nlp_service()
    return AdvancedNLPService()


@pytest.fixture
def doc_id():
    """Generate a document ID."""
    return uuid4()


def create_mention(
    text: str,
    start: int,
    end: int | None = None,
    domain: str = Domain.CONDITION.value,
    assertion: Assertion = Assertion.PRESENT,
) -> ExtractedMention:
    """Helper to create test mentions."""
    if end is None:
        end = start + len(text)
    return ExtractedMention(
        text=text,
        start_offset=start,
        end_offset=end,
        lexical_variant=text.lower(),
        domain_hint=domain,
        assertion=assertion,
        temporality=Temporality.CURRENT,
        experiencer=Experiencer.PATIENT,
        confidence=0.85,
    )


# ==============================================================================
# Abbreviation Disambiguation Tests
# ==============================================================================


class TestAbbreviationDisambiguation:
    """Tests for context-aware abbreviation disambiguation."""

    def test_pe_cardiology_context(self, service):
        """PE in cardiology context should be pulmonary embolism."""
        text = "Patient presents with chest pain, shortness of breath, possible PE."
        mention = create_mention("PE", text.index("PE"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.CARDIOLOGY
        assert enhanced.enhancement.disambiguated_term == "pulmonary embolism"
        assert enhanced.enhancement.original_abbreviation == "PE"

    def test_pe_general_context(self, service):
        """PE in general context should be physical exam."""
        text = "PE exam vitals: BP 120/80, HR 72, RR 16."
        mention = create_mention("PE", text.index("PE"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.GENERAL
        assert enhanced.enhancement.disambiguated_term == "physical exam"

    def test_ms_cardiology_context(self, service):
        """MS near cardiac terms should be mitral stenosis."""
        text = "Echo shows moderate MS with valve area 1.2 cm2."
        mention = create_mention("MS", text.index("MS"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.CARDIOLOGY
        assert enhanced.enhancement.disambiguated_term == "mitral stenosis"

    def test_ms_neurology_context(self, service):
        """MS near neurology terms should be multiple sclerosis."""
        text = "Brain MRI shows demyelinating lesions consistent with MS."
        mention = create_mention("MS", text.index("MS"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.NEUROLOGY
        assert enhanced.enhancement.disambiguated_term == "multiple sclerosis"

    def test_pt_coagulation_context(self, service):
        """PT near coagulation terms should be prothrombin time."""
        text = "Labs: PT/INR elevated, need to adjust warfarin dose."
        mention = create_mention("PT", text.index("PT"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.CARDIOLOGY
        assert enhanced.enhancement.disambiguated_term == "prothrombin time"

    def test_pt_rehab_context(self, service):
        """PT near rehab terms should be physical therapy."""
        text = "Patient to continue PT for mobility and strength training."
        mention = create_mention("PT", text.index("PT"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.REHAB
        assert enhanced.enhancement.disambiguated_term == "physical therapy"

    def test_od_overdose_context(self, service):
        """OD in toxicology context should be overdose."""
        text = "Patient found unresponsive, suspected OD. Narcan administered."
        mention = create_mention("OD", text.index("OD"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.GENERAL
        assert enhanced.enhancement.disambiguated_term == "overdose"

    def test_od_pharmacy_context(self, service):
        """OD in medication context should be once daily."""
        text = "Medications: Lisinopril 10mg OD, Metformin 500mg BID."
        mention = create_mention("OD", text.index("OD"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.PHARMACY
        assert enhanced.enhancement.disambiguated_term == "once daily"

    def test_od_ophthalmology_context(self, service):
        """OD in eye context should be right eye."""
        text = "Eye exam: OD vision 20/40, OS vision 20/20."
        mention = create_mention("OD", text.index("OD"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context == AbbreviationContext.OPHTHALMOLOGY
        assert "right eye" in enhanced.enhancement.disambiguated_term

    def test_non_abbreviation_unchanged(self, service):
        """Non-abbreviations should not be modified."""
        text = "Patient has diabetes mellitus type 2."
        mention = create_mention("diabetes mellitus", text.index("diabetes mellitus"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguation_context is None
        assert enhanced.enhancement.disambiguated_term is None


# ==============================================================================
# Clause-Boundary-Aware Negation Tests
# ==============================================================================


class TestClauseBoundaryNegation:
    """Tests for clause-boundary-aware negation detection."""

    def test_simple_negation(self, service):
        """Simple negation should mark assertion as ABSENT."""
        text = "Patient denies chest pain."
        mention = create_mention("chest pain", text.index("chest pain"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.mention.assertion == Assertion.ABSENT
        assert enhanced.enhancement.negation_trigger == "denies"

    def test_negation_with_but_boundary(self, service):
        """Negation should not cross 'but' boundary."""
        text = "No fever but with cough and congestion."
        fever_mention = create_mention("fever", text.index("fever"))
        cough_mention = create_mention("cough", text.index("cough"))

        fever_enhanced = service.enhance_mention(text, fever_mention)
        cough_enhanced = service.enhance_mention(text, cough_mention)

        # Fever is within negation scope
        assert fever_enhanced.mention.assertion == Assertion.ABSENT
        assert fever_enhanced.enhancement.negation_trigger == "No"

        # Cough is after 'but' boundary, not negated
        assert cough_enhanced.mention.assertion == Assertion.PRESENT
        assert cough_enhanced.enhancement.negation_trigger is None

    def test_negation_with_however_boundary(self, service):
        """Negation should not cross 'however' boundary."""
        text = "Denies headache; however, reports neck stiffness."
        headache = create_mention("headache", text.index("headache"))
        stiffness = create_mention("neck stiffness", text.index("neck stiffness"))

        headache_enhanced = service.enhance_mention(text, headache)
        stiffness_enhanced = service.enhance_mention(text, stiffness)

        assert headache_enhanced.mention.assertion == Assertion.ABSENT
        assert stiffness_enhanced.mention.assertion == Assertion.PRESENT

    def test_negation_with_semicolon_boundary(self, service):
        """Negation should not cross semicolon boundary."""
        text = "No chest pain; positive for dyspnea."
        chest_pain = create_mention("chest pain", text.index("chest pain"))
        dyspnea = create_mention("dyspnea", text.index("dyspnea"))

        cp_enhanced = service.enhance_mention(text, chest_pain)
        dysp_enhanced = service.enhance_mention(text, dyspnea)

        assert cp_enhanced.mention.assertion == Assertion.ABSENT
        assert dysp_enhanced.mention.assertion == Assertion.PRESENT

    def test_no_evidence_of_phrase(self, service):
        """'No evidence of' should trigger negation."""
        text = "Imaging shows no evidence of metastatic disease."
        mention = create_mention("metastatic disease", text.index("metastatic disease"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.mention.assertion == Assertion.ABSENT
        # Negation trigger may be the full phrase or just the first word
        assert "no" in enhanced.enhancement.negation_trigger.lower()

    def test_ruled_out(self, service):
        """'Ruled out' should trigger negation."""
        text = "PE has been ruled out by CT angiography."
        mention = create_mention("PE", text.index("PE"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.mention.assertion == Assertion.ABSENT

    def test_positive_assertion_no_negation(self, service):
        """Text without negation should remain PRESENT."""
        text = "Patient presents with severe headache and photophobia."
        mention = create_mention("headache", text.index("headache"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.mention.assertion == Assertion.PRESENT
        assert enhanced.enhancement.negation_trigger is None


# ==============================================================================
# Compound Condition Extraction Tests
# ==============================================================================


class TestCompoundConditionExtraction:
    """Tests for compound condition extraction."""

    def test_heart_failure_with_reduced_ef(self, service):
        """Should extract HF with reduced EF."""
        text = "Patient has heart failure with reduced EF."
        mention = create_mention("heart failure", text.index("heart failure"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.linked_modifier is not None
        assert "reduced EF" in enhanced.enhancement.linked_modifier
        assert enhanced.enhancement.compound_condition_text is not None

    def test_hfref_abbreviation(self, service):
        """Should recognize HFrEF as compound."""
        text = "Diagnosis: HFrEF with EF 35%."
        mention = create_mention("HFrEF", text.index("HFrEF"))

        enhanced = service.enhance_mention(text, mention)

        # HFrEF itself contains the modifier
        assert enhanced.enhancement.compound_condition_text is not None

    def test_diabetes_with_nephropathy(self, service):
        """Should extract DM with nephropathy."""
        text = "Type 2 diabetes mellitus with nephropathy, stage 3 CKD."
        mention = create_mention("diabetes mellitus", text.index("diabetes mellitus"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.linked_modifier is not None
        assert "nephropathy" in enhanced.enhancement.linked_modifier

    def test_dm_with_retinopathy(self, service):
        """Should extract DM with retinopathy."""
        text = "DM with retinopathy, last eye exam 6 months ago."
        mention = create_mention("DM", text.index("DM"))

        enhanced = service.enhance_mention(text, mention)

        assert "retinopathy" in enhanced.enhancement.linked_modifier

    def test_copd_with_acute_exacerbation(self, service):
        """Should extract COPD with acute exacerbation."""
        text = "Admitted for COPD with acute exacerbation."
        mention = create_mention("COPD", text.index("COPD"))

        enhanced = service.enhance_mention(text, mention)

        assert "acute exacerbation" in enhanced.enhancement.linked_modifier

    def test_ckd_stage(self, service):
        """Should extract CKD stage."""
        text = "CKD stage 3 secondary to diabetic nephropathy."
        mention = create_mention("CKD", text.index("CKD"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.linked_modifier is not None
        assert "stage" in enhanced.enhancement.linked_modifier.lower()

    def test_ckd_esrd(self, service):
        """Should extract end-stage renal disease."""
        text = "Patient with ESRD on hemodialysis."
        # Using CKD mention but text says ESRD
        text2 = "CKD end-stage, on dialysis."
        mention = create_mention("CKD", text2.index("CKD"))

        enhanced = service.enhance_mention(text2, mention)

        assert enhanced.enhancement.linked_modifier is not None

    def test_hypertension_uncontrolled(self, service):
        """Should extract uncontrolled hypertension."""
        text = "Uncontrolled hypertension, BP 180/110."
        mention = create_mention("hypertension", text.index("hypertension"))

        enhanced = service.enhance_mention(text, mention)

        assert "uncontrolled" in enhanced.enhancement.linked_modifier

    def test_no_modifier_present(self, service):
        """Should return None when no modifier present."""
        text = "Patient has hypertension and diabetes."
        mention = create_mention("hypertension", text.index("hypertension"))

        enhanced = service.enhance_mention(text, mention)

        # Simple hypertension without modifiers
        assert enhanced.enhancement.linked_modifier is None


# ==============================================================================
# Laterality Extraction Tests
# ==============================================================================


class TestLateralityExtraction:
    """Tests for laterality extraction."""

    def test_left_knee_pain(self, service):
        """Should extract LEFT laterality."""
        text = "Patient presents with left knee pain."
        mention = create_mention("knee pain", text.index("knee pain"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality == Laterality.LEFT
        assert "left" in enhanced.enhancement.laterality_text.lower()

    def test_right_shoulder(self, service):
        """Should extract RIGHT laterality."""
        text = "X-ray of right shoulder shows calcific tendinitis."
        mention = create_mention("shoulder", text.index("shoulder"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality == Laterality.RIGHT

    def test_bilateral_edema(self, service):
        """Should extract BILATERAL laterality."""
        text = "Examination reveals bilateral lower extremity edema."
        mention = create_mention("lower extremity edema", text.index("lower extremity edema"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality == Laterality.BILATERAL

    def test_bl_abbreviation(self, service):
        """Should recognize b/l as bilateral."""
        text = "B/l lung fields clear to auscultation."
        mention = create_mention("lung", text.index("lung"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality == Laterality.BILATERAL

    def test_left_sided(self, service):
        """Should recognize left-sided."""
        text = "Left-sided weakness noted."
        mention = create_mention("weakness", text.index("weakness"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality == Laterality.LEFT

    def test_right_eye(self, service):
        """Should extract laterality for eye."""
        text = "Right eye showing signs of diabetic retinopathy."
        mention = create_mention("eye", text.index("eye"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality == Laterality.RIGHT

    def test_unilateral(self, service):
        """Should recognize unilateral."""
        text = "Unilateral hearing loss in the left ear."
        mention = create_mention("hearing loss", text.index("hearing loss"))

        # Note: "hearing loss" isn't in our anatomy list, but conditions with laterality should work
        # Let's use a condition that IS in our list
        text2 = "Unilateral leg weakness."
        mention2 = create_mention("leg weakness", text2.index("leg weakness"))

        enhanced = service.enhance_mention(text2, mention2)

        assert enhanced.enhancement.laterality == Laterality.UNILATERAL

    def test_non_lateralized_condition(self, service):
        """Non-anatomical conditions should not get laterality."""
        text = "Patient has diabetes mellitus."
        mention = create_mention("diabetes mellitus", text.index("diabetes mellitus"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality is None

    def test_l_abbreviation(self, service):
        """Should recognize L. as left."""
        text = "L. hip replacement 2020."
        mention = create_mention("hip", text.index("hip"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.laterality == Laterality.LEFT


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestAdvancedNLPIntegration:
    """Integration tests for the full pipeline."""

    def test_multiple_enhancements(self, service):
        """Should apply multiple enhancements to same mention."""
        text = "No left knee pain after PT."
        mention = create_mention("knee pain", text.index("knee pain"))

        enhanced = service.enhance_mention(text, mention)

        # Should have negation
        assert enhanced.mention.assertion == Assertion.ABSENT
        # Should have laterality
        assert enhanced.enhancement.laterality == Laterality.LEFT

    def test_enhance_multiple_mentions(self, service):
        """Should enhance multiple mentions correctly."""
        text = "Chest pain, shortness of breath, no PE. Left leg swelling."
        mentions = [
            create_mention("Chest pain", 0),
            create_mention("shortness of breath", text.index("shortness of breath")),
            create_mention("PE", text.index("PE")),
            create_mention("leg swelling", text.index("leg swelling")),
        ]

        enhanced_list = service.enhance_mentions(text, mentions)

        assert len(enhanced_list) == 4

        # PE should be negated and disambiguated
        pe_enhanced = enhanced_list[2]
        assert pe_enhanced.mention.assertion == Assertion.ABSENT
        assert pe_enhanced.enhancement.disambiguated_term == "pulmonary embolism"

        # Leg swelling should have laterality
        leg_enhanced = enhanced_list[3]
        assert leg_enhanced.enhancement.laterality == Laterality.LEFT

    def test_process_mentions_returns_mentions(self, service):
        """process_mentions should return ExtractedMention list."""
        text = "Patient has left knee pain."
        mentions = [create_mention("knee pain", text.index("knee pain"))]

        processed = service.process_mentions(text, mentions)

        assert len(processed) == 1
        assert isinstance(processed[0], ExtractedMention)

    def test_singleton_pattern(self):
        """Singleton should return same instance."""
        reset_advanced_nlp_service()

        service1 = get_advanced_nlp_service()
        service2 = get_advanced_nlp_service()

        assert service1 is service2

    def test_service_stats(self, service):
        """Service should return stats."""
        stats = service.get_stats()

        assert "abbreviations_tracked" in stats
        assert "negation_triggers" in stats
        assert "compound_patterns" in stats
        assert "laterality_patterns" in stats
        assert stats["abbreviations_tracked"] > 0

    def test_config_disable_features(self):
        """Should respect config to disable features."""
        config = AdvancedNLPConfig(
            enable_abbreviation_disambiguation=False,
            enable_laterality_extraction=False,
        )
        service = AdvancedNLPService(config=config)

        text = "Patient has PE with left knee pain."
        pe_mention = create_mention("PE", text.index("PE"))
        knee_mention = create_mention("knee pain", text.index("knee pain"))

        pe_enhanced = service.enhance_mention(text, pe_mention)
        knee_enhanced = service.enhance_mention(text, knee_mention)

        # Abbreviation should not be disambiguated
        assert pe_enhanced.enhancement.disambiguated_term is None

        # Laterality should not be extracted
        assert knee_enhanced.enhancement.laterality is None


# ==============================================================================
# Edge Cases
# ==============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_text(self, service):
        """Should handle empty text."""
        text = ""
        mention = create_mention("test", 0, 0)

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.mention is not None

    def test_mention_at_start(self, service):
        """Should handle mention at text start."""
        text = "PE suspected based on symptoms."
        mention = create_mention("PE", 0)

        enhanced = service.enhance_mention(text, mention)

        # Should still disambiguate
        assert enhanced.enhancement.disambiguated_term is not None

    def test_mention_at_end(self, service):
        """Should handle mention at text end."""
        text = "Diagnosed with PE"
        mention = create_mention("PE", text.index("PE"))

        enhanced = service.enhance_mention(text, mention)

        assert enhanced.enhancement.disambiguated_term is not None

    def test_case_insensitivity(self, service):
        """Should handle various cases."""
        texts = [
            "Patient has pe suspected.",
            "Patient has PE suspected.",
            "Patient has Pe suspected.",
        ]

        for text in texts:
            mention = create_mention(text[12:14], 12, 14)  # Get "pe", "PE", or "Pe"
            enhanced = service.enhance_mention(text, mention)
            assert enhanced.enhancement.disambiguated_term is not None

    def test_overlapping_patterns(self, service):
        """Should handle overlapping pattern matches."""
        text = "No fever, no cough, no shortness of breath."
        mentions = [
            create_mention("fever", text.index("fever")),
            create_mention("cough", text.index("cough")),
            create_mention("shortness of breath", text.index("shortness of breath")),
        ]

        enhanced_list = service.enhance_mentions(text, mentions)

        # All should be negated
        for em in enhanced_list:
            assert em.mention.assertion == Assertion.ABSENT

    def test_multiple_negation_triggers(self, service):
        """Should handle multiple negation triggers."""
        text = "Denies chest pain. No shortness of breath. Without fever."
        mentions = [
            create_mention("chest pain", text.index("chest pain")),
            create_mention("shortness of breath", text.index("shortness of breath")),
            create_mention("fever", text.index("fever")),
        ]

        enhanced_list = service.enhance_mentions(text, mentions)

        for em in enhanced_list:
            assert em.mention.assertion == Assertion.ABSENT
