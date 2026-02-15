"""Tests for P3-016: Synthetic Data Generation Toolkit.

Tests cover:
- Deterministic patient generation (same seed -> same patient)
- SYNTH- prefix on all IDs
- Patient field completeness (name, dob, mrn, conditions, medications, labs, procedures)
- Document generation for all note types
- Corpus batch generation
- Seed reproducibility across runs
- Edge cases (seed 0, large seed, single-item corpus)
"""

from __future__ import annotations

import pytest

from app.services.synthetic_data_generator import (
    SYNTH_PREFIX,
    NoteType,
    SyntheticCorpus,
    SyntheticDocument,
    SyntheticLabResult,
    SyntheticPatient,
    generate_synthetic_corpus,
    generate_synthetic_document,
    generate_synthetic_patient,
)


# ============================================================================
# Patient Generation
# ============================================================================


class TestGenerateSyntheticPatient:
    """Tests for generate_synthetic_patient."""

    def test_returns_synthetic_patient(self):
        patient = generate_synthetic_patient(seed=42)
        assert isinstance(patient, SyntheticPatient)

    def test_patient_id_has_synth_prefix(self):
        patient = generate_synthetic_patient(seed=42)
        assert patient.patient_id.startswith(SYNTH_PREFIX)

    def test_mrn_has_synth_prefix(self):
        patient = generate_synthetic_patient(seed=42)
        assert patient.mrn.startswith(SYNTH_PREFIX)

    def test_deterministic_same_seed(self):
        p1 = generate_synthetic_patient(seed=100)
        p2 = generate_synthetic_patient(seed=100)
        assert p1.patient_id == p2.patient_id
        assert p1.mrn == p2.mrn
        assert p1.first_name == p2.first_name
        assert p1.last_name == p2.last_name
        assert p1.date_of_birth == p2.date_of_birth
        assert p1.sex == p2.sex
        assert p1.conditions == p2.conditions
        assert p1.medications == p2.medications

    def test_different_seeds_produce_different_patients(self):
        p1 = generate_synthetic_patient(seed=1)
        p2 = generate_synthetic_patient(seed=2)
        # At least patient_id should differ
        assert p1.patient_id != p2.patient_id

    def test_has_conditions(self):
        patient = generate_synthetic_patient(seed=42)
        assert len(patient.conditions) >= 1

    def test_has_medications(self):
        patient = generate_synthetic_patient(seed=42)
        assert len(patient.medications) >= 1

    def test_has_lab_results(self):
        patient = generate_synthetic_patient(seed=42)
        assert len(patient.lab_results) >= 3
        for lab in patient.lab_results:
            assert isinstance(lab, SyntheticLabResult)
            assert lab.test_name
            assert lab.unit
            assert lab.reference_range

    def test_sex_is_valid(self):
        patient = generate_synthetic_patient(seed=42)
        assert patient.sex in ("M", "F")

    def test_date_of_birth_is_iso_format(self):
        patient = generate_synthetic_patient(seed=42)
        # Should parse without error
        from datetime import date
        date.fromisoformat(patient.date_of_birth)

    def test_seed_zero(self):
        patient = generate_synthetic_patient(seed=0)
        assert patient.patient_id.startswith(SYNTH_PREFIX)
        assert patient.first_name  # non-empty

    def test_large_seed(self):
        patient = generate_synthetic_patient(seed=999_999_999)
        assert patient.patient_id.startswith(SYNTH_PREFIX)


# ============================================================================
# Document Generation
# ============================================================================


class TestGenerateSyntheticDocument:
    """Tests for generate_synthetic_document."""

    def test_returns_synthetic_document(self):
        doc = generate_synthetic_document("SYNTH-PAT001", NoteType.ADMISSION, seed=42)
        assert isinstance(doc, SyntheticDocument)

    def test_document_id_has_synth_prefix(self):
        doc = generate_synthetic_document("SYNTH-PAT001", NoteType.PROGRESS, seed=42)
        assert doc.document_id.startswith(SYNTH_PREFIX)

    def test_patient_id_preserved(self):
        doc = generate_synthetic_document("SYNTH-PAT001", NoteType.DISCHARGE, seed=42)
        assert doc.patient_id == "SYNTH-PAT001"

    def test_note_type_preserved(self):
        for nt in NoteType:
            doc = generate_synthetic_document("SYNTH-PAT001", nt, seed=42)
            assert doc.note_type == nt

    def test_content_contains_synthetic_marker(self):
        doc = generate_synthetic_document("SYNTH-PAT001", NoteType.ADMISSION, seed=42)
        assert "SYNTHETIC DATA" in doc.content

    def test_deterministic_same_seed(self):
        d1 = generate_synthetic_document("SYNTH-PAT001", NoteType.LAB_REPORT, seed=77)
        d2 = generate_synthetic_document("SYNTH-PAT001", NoteType.LAB_REPORT, seed=77)
        assert d1.document_id == d2.document_id
        assert d1.content == d2.content

    def test_different_seeds_produce_different_docs(self):
        d1 = generate_synthetic_document("SYNTH-PAT001", NoteType.CONSULTATION, seed=1)
        d2 = generate_synthetic_document("SYNTH-PAT001", NoteType.CONSULTATION, seed=2)
        assert d1.document_id != d2.document_id

    def test_note_type_as_string(self):
        doc = generate_synthetic_document("SYNTH-PAT001", "admission", seed=42)
        assert doc.note_type == NoteType.ADMISSION

    @pytest.mark.parametrize("note_type", list(NoteType))
    def test_all_note_types_produce_content(self, note_type: NoteType):
        doc = generate_synthetic_document("SYNTH-PAT001", note_type, seed=42)
        assert len(doc.content) > 50
        assert doc.title


# ============================================================================
# Corpus Generation
# ============================================================================


class TestGenerateSyntheticCorpus:
    """Tests for generate_synthetic_corpus."""

    def test_returns_corpus(self):
        corpus = generate_synthetic_corpus(n_patients=2, notes_per_patient=1, seed=42)
        assert isinstance(corpus, SyntheticCorpus)

    def test_corpus_id_has_synth_prefix(self):
        corpus = generate_synthetic_corpus(n_patients=1, notes_per_patient=1, seed=42)
        assert corpus.corpus_id.startswith(SYNTH_PREFIX)

    def test_correct_patient_count(self):
        corpus = generate_synthetic_corpus(n_patients=5, notes_per_patient=1, seed=42)
        assert len(corpus.patients) == 5

    def test_correct_document_count(self):
        corpus = generate_synthetic_corpus(n_patients=3, notes_per_patient=2, seed=42)
        assert len(corpus.documents) == 6  # 3 * 2

    def test_all_patients_have_synth_ids(self):
        corpus = generate_synthetic_corpus(n_patients=3, notes_per_patient=1, seed=42)
        for p in corpus.patients:
            assert p.patient_id.startswith(SYNTH_PREFIX)
            assert p.mrn.startswith(SYNTH_PREFIX)

    def test_documents_reference_valid_patients(self):
        corpus = generate_synthetic_corpus(n_patients=3, notes_per_patient=2, seed=42)
        patient_ids = {p.patient_id for p in corpus.patients}
        for doc in corpus.documents:
            assert doc.patient_id in patient_ids

    def test_deterministic(self):
        c1 = generate_synthetic_corpus(n_patients=2, notes_per_patient=1, seed=99)
        c2 = generate_synthetic_corpus(n_patients=2, notes_per_patient=1, seed=99)
        assert c1.corpus_id == c2.corpus_id
        assert len(c1.patients) == len(c2.patients)
        for p1, p2 in zip(c1.patients, c2.patients):
            assert p1.patient_id == p2.patient_id

    def test_seed_stored(self):
        corpus = generate_synthetic_corpus(n_patients=1, notes_per_patient=1, seed=42)
        assert corpus.seed == 42

    def test_single_patient_corpus(self):
        corpus = generate_synthetic_corpus(n_patients=1, notes_per_patient=1, seed=42)
        assert len(corpus.patients) == 1
        assert len(corpus.documents) == 1

    def test_zero_notes_per_patient(self):
        corpus = generate_synthetic_corpus(n_patients=3, notes_per_patient=0, seed=42)
        assert len(corpus.patients) == 3
        assert len(corpus.documents) == 0
