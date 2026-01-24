"""Tests for mapping accuracy on synthetic note fixtures.

Validates that the mapping service correctly maps clinical terms
from the synthetic notes to OMOP concepts (task 5.6).
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.vocabulary import Concept, ConceptSynonym
from app.schemas.base import Domain
from app.services.mapping_db import DatabaseMappingService

# Create test database engine
_test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    future=True,
)
_TestSession = sessionmaker(
    bind=_test_engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="module")
def fixture_path() -> Path:
    """Get path to vocabulary fixture."""
    return Path(__file__).parent.parent / "fixtures" / "omop_vocabulary.json"


@pytest.fixture(scope="module")
def notes_path() -> Path:
    """Get path to synthetic notes fixture."""
    return Path(__file__).parent.parent / "fixtures" / "synthetic_notes.json"


@pytest.fixture(scope="module")
def mapping_session(fixture_path: Path) -> Session:
    """Create a database session with vocabulary loaded."""
    # Create tables
    Concept.__table__.create(bind=_test_engine, checkfirst=True)
    ConceptSynonym.__table__.create(bind=_test_engine, checkfirst=True)

    session = _TestSession()

    # Load vocabulary fixture
    with open(fixture_path) as f:
        data = json.load(f)

    for concept_data in data.get("concepts", []):
        concept = Concept(
            concept_id=concept_data["concept_id"],
            concept_name=concept_data["concept_name"],
            domain_id=concept_data["domain_id"],
            vocabulary_id=concept_data["vocabulary_id"],
            concept_class_id=concept_data["concept_class_id"],
            standard_concept=concept_data.get("standard_concept"),
        )
        session.add(concept)
    session.commit()

    for concept_data in data.get("concepts", []):
        for synonym in concept_data.get("synonyms", []):
            syn = ConceptSynonym(
                concept_id=concept_data["concept_id"],
                concept_synonym_name=synonym.lower(),
                language_concept_id=4180186,
            )
            session.add(syn)
    session.commit()

    yield session

    session.close()
    ConceptSynonym.__table__.drop(bind=_test_engine, checkfirst=True)
    Concept.__table__.drop(bind=_test_engine, checkfirst=True)


@pytest.fixture(scope="module")
def mapping_service(mapping_session: Session) -> DatabaseMappingService:
    """Create mapping service with loaded vocabulary."""
    service = DatabaseMappingService()
    service.load_from_db(mapping_session)
    return service


class TestConditionMapping:
    """Tests for condition concept mapping accuracy."""

    def test_map_cough(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'cough' to OMOP concept."""
        candidates = mapping_service.map_mention("cough")
        assert len(candidates) > 0
        assert candidates[0].concept_name == "Cough"
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_fever(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'fever' to OMOP concept."""
        candidates = mapping_service.map_mention("fever")
        assert len(candidates) > 0
        assert candidates[0].concept_name == "Fever"
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_pneumonia(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'pneumonia' to OMOP concept."""
        candidates = mapping_service.map_mention("pneumonia")
        assert len(candidates) > 0
        assert candidates[0].concept_name == "Pneumonia"
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_congestive_heart_failure(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'congestive heart failure' to OMOP concept."""
        candidates = mapping_service.map_mention("congestive heart failure")
        assert len(candidates) > 0
        assert "heart failure" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_chf_synonym(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'CHF' synonym to OMOP concept."""
        candidates = mapping_service.map_mention("CHF")
        assert len(candidates) > 0
        assert "heart failure" in candidates[0].concept_name.lower()

    def test_map_colon_cancer(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'colon cancer' to OMOP concept."""
        candidates = mapping_service.map_mention("colon cancer")
        assert len(candidates) > 0
        assert "colon cancer" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_type2_diabetes(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Type 2 diabetes mellitus' to OMOP concept."""
        candidates = mapping_service.map_mention("Type 2 diabetes mellitus")
        assert len(candidates) > 0
        assert "diabetes" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_hypertension(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'hypertension' to OMOP concept."""
        candidates = mapping_service.map_mention("hypertension")
        assert len(candidates) > 0
        assert "hypertension" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_chest_pain(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'chest pain' to OMOP concept."""
        candidates = mapping_service.map_mention("chest pain")
        assert len(candidates) > 0
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_dyspnea(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'dyspnea' to OMOP concept."""
        candidates = mapping_service.map_mention("dyspnea")
        assert len(candidates) > 0
        assert candidates[0].domain_id == Domain.CONDITION

    def test_map_stroke(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'stroke' to OMOP concept."""
        candidates = mapping_service.map_mention("stroke")
        assert len(candidates) > 0
        assert candidates[0].domain_id == Domain.CONDITION


class TestDrugMapping:
    """Tests for drug concept mapping accuracy."""

    def test_map_metformin(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Metformin' to OMOP concept."""
        candidates = mapping_service.map_mention("Metformin")
        assert len(candidates) > 0
        assert "metformin" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.DRUG

    def test_map_lisinopril(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Lisinopril' to OMOP concept."""
        candidates = mapping_service.map_mention("Lisinopril")
        assert len(candidates) > 0
        assert "lisinopril" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.DRUG

    def test_map_aspirin(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Aspirin' to OMOP concept."""
        candidates = mapping_service.map_mention("Aspirin")
        assert len(candidates) > 0
        assert "aspirin" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.DRUG

    def test_map_atorvastatin(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Atorvastatin' to OMOP concept."""
        candidates = mapping_service.map_mention("Atorvastatin")
        assert len(candidates) > 0
        assert "atorvastatin" in candidates[0].concept_name.lower()
        assert candidates[0].domain_id == Domain.DRUG


class TestMeasurementMapping:
    """Tests for measurement concept mapping accuracy."""

    def test_map_hemoglobin_a1c(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Hemoglobin A1c' to OMOP concept."""
        candidates = mapping_service.map_mention("Hemoglobin A1c")
        assert len(candidates) > 0
        assert candidates[0].domain_id == Domain.MEASUREMENT

    def test_map_blood_pressure(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Blood pressure' to OMOP concept."""
        candidates = mapping_service.map_mention("Blood pressure")
        assert len(candidates) > 0
        assert candidates[0].domain_id == Domain.MEASUREMENT

    def test_map_creatinine(self, mapping_service: DatabaseMappingService) -> None:
        """Test mapping 'Creatinine' to OMOP concept."""
        candidates = mapping_service.map_mention("Creatinine")
        assert len(candidates) > 0
        assert candidates[0].domain_id == Domain.MEASUREMENT


class TestDomainFiltering:
    """Tests for domain-filtered mapping accuracy."""

    def test_condition_domain_filter(self, mapping_service: DatabaseMappingService) -> None:
        """Test filtering by condition domain."""
        candidates = mapping_service.map_mention("fever", domain=Domain.CONDITION)
        for candidate in candidates:
            assert candidate.domain_id == Domain.CONDITION

    def test_drug_domain_filter(self, mapping_service: DatabaseMappingService) -> None:
        """Test filtering by drug domain."""
        candidates = mapping_service.map_mention("metformin", domain=Domain.DRUG)
        for candidate in candidates:
            assert candidate.domain_id == Domain.DRUG

    def test_measurement_domain_filter(self, mapping_service: DatabaseMappingService) -> None:
        """Test filtering by measurement domain."""
        candidates = mapping_service.map_mention("blood pressure", domain=Domain.MEASUREMENT)
        for candidate in candidates:
            assert candidate.domain_id == Domain.MEASUREMENT


class TestSyntheticNotesMapping:
    """Integration tests mapping terms from actual synthetic notes."""

    @pytest.fixture
    def synthetic_notes(self, notes_path: Path) -> list[dict]:
        """Load synthetic notes fixture."""
        with open(notes_path) as f:
            data = json.load(f)
        return data.get("notes", [])

    def test_note_001_terms_map(
        self,
        mapping_service: DatabaseMappingService,
        synthetic_notes: list[dict],
    ) -> None:
        """Test mapping terms from note_001 (cough, fever, pneumonia)."""
        note = next(n for n in synthetic_notes if n["id"] == "note_001")
        expected_mentions = note["expected_mentions"]

        for mention in expected_mentions:
            term = mention["text"]
            candidates = mapping_service.map_mention(term)
            assert len(candidates) > 0, f"No candidates found for '{term}'"

    def test_note_004_drugs_map(
        self,
        mapping_service: DatabaseMappingService,
    ) -> None:
        """Test mapping drug terms from note_004 (Metformin, Lisinopril)."""
        # Check Metformin mapping
        metformin_candidates = mapping_service.map_mention("Metformin")
        assert len(metformin_candidates) > 0
        assert metformin_candidates[0].domain_id == Domain.DRUG

        # Check Lisinopril mapping
        lisinopril_candidates = mapping_service.map_mention("Lisinopril")
        assert len(lisinopril_candidates) > 0
        assert lisinopril_candidates[0].domain_id == Domain.DRUG

    def test_note_005_measurements_map(
        self,
        mapping_service: DatabaseMappingService,
        synthetic_notes: list[dict],
    ) -> None:
        """Test mapping measurement terms from note_005."""
        # Check measurement mappings
        a1c_candidates = mapping_service.map_mention("Hemoglobin A1c")
        assert len(a1c_candidates) > 0
        assert a1c_candidates[0].domain_id == Domain.MEASUREMENT

        creatinine_candidates = mapping_service.map_mention("Creatinine")
        assert len(creatinine_candidates) > 0
        assert creatinine_candidates[0].domain_id == Domain.MEASUREMENT

    def test_mapping_coverage_for_conditions(
        self,
        mapping_service: DatabaseMappingService,
    ) -> None:
        """Test that common condition terms from notes are mapped."""
        condition_terms = [
            "cough",
            "fever",
            "pneumonia",
            "heart failure",
            "diabetes",
            "hypertension",
            "chest pain",
            "dyspnea",
            "stroke",
        ]

        mapped_count = 0
        for term in condition_terms:
            candidates = mapping_service.map_mention(term, domain=Domain.CONDITION)
            if len(candidates) > 0:
                mapped_count += 1

        # At least 80% of terms should map
        coverage = mapped_count / len(condition_terms)
        assert coverage >= 0.8, f"Condition mapping coverage {coverage:.0%} is below 80%"

    def test_mapping_coverage_for_drugs(
        self,
        mapping_service: DatabaseMappingService,
    ) -> None:
        """Test that common drug terms from notes are mapped."""
        drug_terms = [
            "Metformin",
            "Lisinopril",
            "Aspirin",
            "Atorvastatin",
        ]

        mapped_count = 0
        for term in drug_terms:
            candidates = mapping_service.map_mention(term, domain=Domain.DRUG)
            if len(candidates) > 0:
                mapped_count += 1

        # All drugs should map since they're in the vocabulary
        assert mapped_count == len(drug_terms), (
            f"Only {mapped_count}/{len(drug_terms)} drugs mapped"
        )
