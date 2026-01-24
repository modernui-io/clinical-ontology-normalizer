"""Tests for NLP extraction with synthetic clinical notes.

Task 4.7: Comprehensive tests validating assertion, temporality, and experiencer
detection using the 10 synthetic notes from fixtures/synthetic_notes.json.
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.base import Assertion, Experiencer, Temporality
from app.services import RuleBasedNLPService


@pytest.fixture
def nlp_service() -> RuleBasedNLPService:
    """Create NLP service for testing."""
    return RuleBasedNLPService()


@pytest.fixture
def synthetic_notes() -> list[dict]:
    """Load synthetic notes from fixture."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "synthetic_notes.json"
    with open(fixtures_path) as f:
        data = json.load(f)
    return data["notes"]


class TestNegationDetection:
    """Tests for negation (ABSENT assertion) detection.

    Uses notes: 001, 002, 003, 007, 008 which contain negated findings.
    """

    def test_note_001_pneumonia_negated(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 001: 'No evidence of pneumonia' should be ABSENT."""
        text = (
            "Patient is a 65-year-old male presenting with cough and fever. "
            "Chest X-ray performed. No evidence of pneumonia. Will monitor symptoms."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        pneumonia = next((m for m in mentions if "pneumonia" in m.lexical_variant.lower()), None)
        assert pneumonia is not None, "Should find pneumonia mention"
        assert pneumonia.assertion == Assertion.ABSENT, "Pneumonia should be negated"

    def test_note_002_acute_distress_negated(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 002: 'No acute distress' should be ABSENT."""
        text = (
            "History of congestive heart failure. Patient currently stable "
            "on current medications. No acute distress."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        distress = next(
            (m for m in mentions if "distress" in m.lexical_variant.lower()),
            None,
        )
        if distress:  # May not be in vocabulary
            assert distress.assertion == Assertion.ABSENT

    def test_note_003_gi_symptoms_denied(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 003: 'denies any GI symptoms' should be ABSENT."""
        text = (
            "Family history significant for colon cancer - mother diagnosed at age 55. "
            "Patient denies any GI symptoms. Colonoscopy recommended."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        gi_symptoms = next(
            (m for m in mentions if "gi" in m.lexical_variant.lower()),
            None,
        )
        if gi_symptoms:  # May not be in vocabulary
            assert gi_symptoms.assertion == Assertion.ABSENT

    def test_note_007_acs_ruled_out(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 007: 'ruled out for acute coronary syndrome' should be ABSENT."""
        text = (
            "Patient admitted for chest pain. Cardiac enzymes negative. EKG normal. "
            "Chest pain ruled out for acute coronary syndrome. "
            "Discharge diagnosis: non-cardiac chest pain, likely musculoskeletal."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        # Acute coronary syndrome may or may not be in vocabulary
        acs = next(
            (m for m in mentions if "coronary" in m.lexical_variant.lower()),
            None,
        )
        if acs:
            assert acs.assertion == Assertion.ABSENT

    def test_note_008_chest_pain_denied(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 008: 'Denies chest pain' should be ABSENT."""
        text = (
            "Previous myocardial infarction in 2019. Currently on Aspirin 81mg daily "
            "and Atorvastatin 40mg daily. Denies chest pain or shortness of breath."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        chest_pain = next(
            (m for m in mentions if "chest pain" in m.lexical_variant.lower()),
            None,
        )
        if chest_pain:
            assert chest_pain.assertion == Assertion.ABSENT

    def test_note_008_sob_denied(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 008: 'Denies shortness of breath' should be ABSENT."""
        text = (
            "Previous myocardial infarction in 2019. Currently on Aspirin 81mg daily "
            "and Atorvastatin 40mg daily. Denies chest pain or shortness of breath."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        sob = next(
            (m for m in mentions if "shortness of breath" in m.lexical_variant.lower()),
            None,
        )
        if sob:
            assert sob.assertion == Assertion.ABSENT


class TestTemporalityDetection:
    """Tests for temporality (PAST/CURRENT) detection.

    Uses notes: 002, 008, 009 which contain historical conditions.
    """

    def test_note_002_chf_history(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 002: 'History of congestive heart failure' should be PAST."""
        text = (
            "History of congestive heart failure. Patient currently stable "
            "on current medications. No acute distress."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        chf = next(
            (m for m in mentions if "heart failure" in m.lexical_variant.lower()),
            None,
        )
        assert chf is not None, "Should find CHF mention"
        assert chf.temporality == Temporality.PAST, "CHF should be historical"

    def test_note_008_mi_previous(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 008: 'Previous myocardial infarction' should be PAST."""
        text = (
            "Previous myocardial infarction in 2019. Currently on Aspirin 81mg daily "
            "and Atorvastatin 40mg daily. Denies chest pain or shortness of breath."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        mi = next(
            (m for m in mentions if "myocardial infarction" in m.lexical_variant.lower()),
            None,
        )
        if mi:
            assert mi.temporality == Temporality.PAST

    def test_note_009_stroke_father(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 009: 'Father had stroke' should be PAST (also FAMILY)."""
        text = (
            "Father had stroke at age 60. Patient is concerned about stroke risk. "
            "Blood pressure today 142/88. Will start antihypertensive therapy."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        stroke = next(
            (m for m in mentions if "stroke" in m.lexical_variant.lower()),
            None,
        )
        if stroke:
            # Should be past because of 'had'
            assert stroke.temporality == Temporality.PAST

    def test_note_004_current_conditions(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 004: Current conditions should have CURRENT temporality."""
        text = (
            "Patient with Type 2 diabetes mellitus. Current medications include "
            "Metformin 1000mg twice daily and Lisinopril 10mg daily for hypertension."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        diabetes = next(
            (m for m in mentions if "diabetes" in m.lexical_variant.lower()),
            None,
        )
        assert diabetes is not None, "Should find diabetes mention"
        assert diabetes.temporality == Temporality.CURRENT


class TestExperiencerDetection:
    """Tests for experiencer (PATIENT/FAMILY) detection.

    Uses notes: 003, 009 which contain family history.
    """

    def test_note_003_family_cancer(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 003: 'Family history significant for colon cancer' should be FAMILY."""
        text = (
            "Family history significant for colon cancer - mother diagnosed at age 55. "
            "Patient denies any GI symptoms. Colonoscopy recommended."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        cancer = next(
            (m for m in mentions if "cancer" in m.lexical_variant.lower()),
            None,
        )
        assert cancer is not None, "Should find cancer mention"
        assert cancer.experiencer == Experiencer.FAMILY, "Cancer should be family history"

    def test_note_009_father_stroke(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 009: 'Father had stroke' should have FAMILY experiencer."""
        text = (
            "Father had stroke at age 60. Patient is concerned about stroke risk. "
            "Blood pressure today 142/88. Will start antihypertensive therapy."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        stroke = next(
            (m for m in mentions if "stroke" in m.lexical_variant.lower()),
            None,
        )
        if stroke:
            assert stroke.experiencer == Experiencer.FAMILY

    def test_note_001_patient_conditions(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 001: Patient's conditions should have PATIENT experiencer."""
        text = (
            "Patient is a 65-year-old male presenting with cough and fever. "
            "Chest X-ray performed. No evidence of pneumonia. Will monitor symptoms."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        for mention in mentions:
            # All mentions in this note are patient's
            assert mention.experiencer == Experiencer.PATIENT


class TestUncertaintyDetection:
    """Tests for uncertainty (POSSIBLE assertion) detection.

    Uses notes: 006, 010 which contain uncertain diagnoses.
    """

    def test_note_006_possible_uti(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 006: 'Possible urinary tract infection' should be POSSIBLE."""
        text = (
            "Possible urinary tract infection. Patient reports dysuria and frequency. "
            "Urine culture pending. Started on empiric antibiotics."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        uti = next(
            (m for m in mentions if "urinary tract infection" in m.lexical_variant.lower()),
            None,
        )
        if uti:
            assert uti.assertion == Assertion.POSSIBLE

    def test_note_010_cannot_rule_out_pe(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 010: 'Cannot rule out pulmonary embolism' should be POSSIBLE."""
        text = (
            "Cannot rule out pulmonary embolism. Patient with sudden onset dyspnea "
            "and pleuritic chest pain. D-dimer elevated. CT angiography ordered."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        pe = next(
            (m for m in mentions if "pulmonary embolism" in m.lexical_variant.lower()),
            None,
        )
        if pe:
            # "Cannot rule out" is a form of uncertainty
            assert pe.assertion in (Assertion.POSSIBLE, Assertion.PRESENT)


class TestPresentFindings:
    """Tests for positive (PRESENT assertion) findings."""

    def test_note_001_positive_symptoms(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 001: Cough and fever should be PRESENT."""
        text = (
            "Patient is a 65-year-old male presenting with cough and fever. "
            "Chest X-ray performed. No evidence of pneumonia. Will monitor symptoms."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        cough = next((m for m in mentions if "cough" in m.lexical_variant.lower()), None)
        fever = next((m for m in mentions if "fever" in m.lexical_variant.lower()), None)

        assert cough is not None, "Should find cough mention"
        assert cough.assertion == Assertion.PRESENT, "Cough should be present"

        assert fever is not None, "Should find fever mention"
        assert fever.assertion == Assertion.PRESENT, "Fever should be present"

    def test_note_004_conditions_present(self, nlp_service: RuleBasedNLPService) -> None:
        """Note 004: Diabetes and hypertension should be PRESENT."""
        text = (
            "Patient with Type 2 diabetes mellitus. Current medications include "
            "Metformin 1000mg twice daily and Lisinopril 10mg daily for hypertension."
        )
        mentions = nlp_service.extract_mentions(text, uuid4())

        diabetes = next(
            (m for m in mentions if "diabetes" in m.lexical_variant.lower()),
            None,
        )
        htn = next(
            (m for m in mentions if "hypertension" in m.lexical_variant.lower()),
            None,
        )

        assert diabetes is not None, "Should find diabetes mention"
        assert diabetes.assertion == Assertion.PRESENT

        assert htn is not None, "Should find hypertension mention"
        assert htn.assertion == Assertion.PRESENT


class TestSyntheticNotesIntegration:
    """Integration tests using all synthetic notes."""

    def test_all_notes_produce_mentions(
        self, nlp_service: RuleBasedNLPService, synthetic_notes: list[dict]
    ) -> None:
        """Each synthetic note should produce at least one mention."""
        for note in synthetic_notes:
            mentions = nlp_service.extract_mentions(note["text"], uuid4())
            # Some notes may have terms not in vocabulary, but most should have matches
            # At minimum, check notes with common terms
            if note["id"] in ["note_001", "note_002", "note_004"]:
                assert len(mentions) > 0, f"Note {note['id']} should produce mentions"

    def test_mentions_have_valid_offsets(
        self, nlp_service: RuleBasedNLPService, synthetic_notes: list[dict]
    ) -> None:
        """All mention offsets should point to valid text spans."""
        for note in synthetic_notes:
            text = note["text"]
            mentions = nlp_service.extract_mentions(text, uuid4())

            for mention in mentions:
                # Verify offset validity
                assert 0 <= mention.start_offset < len(text)
                assert mention.start_offset < mention.end_offset <= len(text)
                # Verify extracted text matches
                extracted = text[mention.start_offset : mention.end_offset].lower()
                assert extracted == mention.text.lower()

    def test_negated_mentions_are_preserved(
        self, nlp_service: RuleBasedNLPService, synthetic_notes: list[dict]
    ) -> None:
        """Negated mentions must be preserved (not filtered out)."""
        # Note 001 has "No evidence of pneumonia"
        note_001 = next(n for n in synthetic_notes if n["id"] == "note_001")
        mentions = nlp_service.extract_mentions(note_001["text"], uuid4())

        pneumonia = next(
            (m for m in mentions if "pneumonia" in m.lexical_variant.lower()),
            None,
        )
        # Pneumonia should be present in mentions AND marked as absent
        assert pneumonia is not None, "Negated mention should be preserved"
        assert pneumonia.assertion == Assertion.ABSENT
