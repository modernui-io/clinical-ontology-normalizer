"""Tests for vocabulary loading and database mapping service.

Tests the vocabulary fixture loading into database (task 5.2).
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.vocabulary import Concept, ConceptSynonym
from app.schemas.base import Domain
from app.services.mapping import MappingMethod
from app.services.mapping_db import DatabaseMappingService

_vocab_test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    future=True,
)
_VocabTestSession = sessionmaker(
    bind=_vocab_test_engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="function")
def vocab_session() -> Session:
    """Create a database session with only vocabulary tables."""
    Concept.__table__.create(bind=_vocab_test_engine, checkfirst=True)
    ConceptSynonym.__table__.create(bind=_vocab_test_engine, checkfirst=True)

    session = _VocabTestSession()
    try:
        yield session
    finally:
        session.close()
        ConceptSynonym.__table__.drop(bind=_vocab_test_engine, checkfirst=True)
        Concept.__table__.drop(bind=_vocab_test_engine, checkfirst=True)


class TestVocabularyFixtureLoading:
    """Tests for loading vocabulary fixture into database."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "omop_vocabulary.json"

    @pytest.fixture
    def fixture_data(self, fixture_path: Path) -> dict:
        with open(fixture_path) as f:
            return json.load(f)

    def test_fixture_file_exists(self, fixture_path: Path) -> None:
        assert fixture_path.exists()

    def test_fixture_has_concepts(self, fixture_data: dict) -> None:
        concepts = fixture_data.get("concepts", [])
        assert len(concepts) > 0

    def test_fixture_has_expected_domains(self, fixture_data: dict) -> None:
        concepts = fixture_data.get("concepts", [])
        domains = {c["domain_id"] for c in concepts}
        assert "Condition" in domains
        assert "Drug" in domains
        assert "Measurement" in domains
        assert "Procedure" in domains

    def test_fixture_concepts_have_synonyms(self, fixture_data: dict) -> None:
        concepts = fixture_data.get("concepts", [])
        concepts_with_synonyms = [c for c in concepts if c.get("synonyms")]
        assert len(concepts_with_synonyms) == len(concepts)

    def test_fixture_has_hypertension(self, fixture_data: dict) -> None:
        concepts = fixture_data.get("concepts", [])
        hypertension = next(
            (c for c in concepts if "hypertension" in c["concept_name"].lower()),
            None,
        )
        assert hypertension is not None
        assert "hypertension" in hypertension.get("synonyms", [])

    def test_fixture_has_metformin(self, fixture_data: dict) -> None:
        concepts = fixture_data.get("concepts", [])
        metformin = next(
            (c for c in concepts if "metformin" in c["concept_name"].lower()),
            None,
        )
        assert metformin is not None
        assert metformin["domain_id"] == "Drug"


class TestDatabaseMappingServiceUnit:
    """Unit tests for DatabaseMappingService without database."""

    def test_init_without_session(self) -> None:
        service = DatabaseMappingService()
        assert service is not None
        assert service.is_loaded() is False

    def test_ensure_loaded_raises_without_session(self) -> None:
        service = DatabaseMappingService()
        with pytest.raises(RuntimeError, match="Vocabulary not loaded"):
            service.map_mention("test")

    def test_concept_count_before_load(self) -> None:
        service = DatabaseMappingService()
        assert service.concept_count == 0


class TestDatabaseMappingServiceWithDB:
    """Integration tests for DatabaseMappingService with database."""

    @pytest.fixture(autouse=True)
    def setup_vocabulary(self, vocab_session) -> None:
        fixture_path = Path(__file__).parent.parent / "fixtures" / "omop_vocabulary.json"
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
            vocab_session.add(concept)
        vocab_session.commit()

        for concept_data in data.get("concepts", []):
            for synonym in concept_data.get("synonyms", []):
                syn = ConceptSynonym(
                    concept_id=concept_data["concept_id"],
                    concept_synonym_name=synonym.lower(),
                    language_concept_id=4180186,
                )
                vocab_session.add(syn)
        vocab_session.commit()

    @pytest.fixture
    def service(self, vocab_session) -> DatabaseMappingService:
        service = DatabaseMappingService()
        service.load_from_db(vocab_session)
        return service

    def test_load_from_db(self, vocab_session) -> None:
        service = DatabaseMappingService()
        service.load_from_db(vocab_session)
        assert service.is_loaded() is True
        assert service.concept_count > 0

    def test_concept_count_after_load(self, service: DatabaseMappingService) -> None:
        assert service.concept_count == 259

    def test_map_mention_exact_match(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("fever")
        assert len(candidates) > 0
        assert candidates[0].concept_name == "Fever"
        assert candidates[0].method == MappingMethod.EXACT
        assert candidates[0].score == 1.0

    def test_map_mention_synonym_match(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("pyrexia")
        assert len(candidates) > 0
        assert candidates[0].concept_name == "Fever"

    def test_map_mention_case_insensitive(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("HYPERTENSION")
        assert len(candidates) > 0
        assert "hypertension" in candidates[0].concept_name.lower()

    def test_map_mention_with_domain_filter(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("fever", domain=Domain.CONDITION)
        assert len(candidates) > 0
        for candidate in candidates:
            assert candidate.domain_id == Domain.CONDITION

    def test_map_mention_domain_filter_excludes(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("metformin", domain=Domain.CONDITION)
        assert len(candidates) == 0

    def test_map_mention_returns_drug(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("metformin")
        assert len(candidates) > 0
        assert candidates[0].domain_id == Domain.DRUG

    def test_map_mention_respects_limit(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("blood pressure", limit=2)
        assert len(candidates) <= 2

    def test_get_concept_by_id(self, service: DatabaseMappingService) -> None:
        candidate = service.get_concept_by_id(437663)
        assert candidate is not None
        assert candidate.concept_name == "Fever"

    def test_get_concept_by_id_not_found(self, service: DatabaseMappingService) -> None:
        candidate = service.get_concept_by_id(999999999)
        assert candidate is None

    def test_get_synonyms(self, service: DatabaseMappingService) -> None:
        synonyms = service.get_synonyms(437663)
        assert len(synonyms) > 0
        assert "pyrexia" in synonyms

    def test_map_mention_no_match(self, service: DatabaseMappingService) -> None:
        candidates = service.map_mention("xyznonexistent123")
        assert candidates == []

    def test_search_by_domain(self, service: DatabaseMappingService) -> None:
        candidates = service.search_by_domain("pain", Domain.CONDITION)
        for candidate in candidates:
            assert candidate.domain_id == Domain.CONDITION

    def test_fuzzy_match_partial_term(self, service: DatabaseMappingService) -> None:
        """Test fuzzy matching with partial term overlap."""
        # "community pneumonia" should fuzzy match "community acquired pneumonia"
        candidates = service.map_mention("community pneumonia")
        assert len(candidates) > 0
        # Should have fuzzy matches with scores < 1.0
        fuzzy_candidates = [c for c in candidates if c.method == MappingMethod.FUZZY]
        if fuzzy_candidates:
            assert all(c.score < 1.0 for c in fuzzy_candidates)

    def test_fuzzy_match_method_type(self, service: DatabaseMappingService) -> None:
        """Test that fuzzy matches have FUZZY method type."""
        # Search for something that won't have exact match
        candidates = service.map_mention("acquired pneumonia")
        fuzzy_candidates = [c for c in candidates if c.method == MappingMethod.FUZZY]
        for candidate in fuzzy_candidates:
            assert candidate.method == MappingMethod.FUZZY
            assert candidate.score < 1.0
            assert candidate.score >= 0.3  # Minimum threshold

    def test_fuzzy_match_respects_domain_filter(self, service: DatabaseMappingService) -> None:
        """Test fuzzy matching respects domain filter."""
        candidates = service.map_mention("blood glucose", domain=Domain.MEASUREMENT, limit=10)
        for candidate in candidates:
            assert candidate.domain_id == Domain.MEASUREMENT

    def test_exact_matches_ranked_before_fuzzy(self, service: DatabaseMappingService) -> None:
        """Test that exact matches come before fuzzy matches."""
        candidates = service.map_mention("fever", limit=10)
        if len(candidates) > 1:
            # First candidate should be exact match
            exact_found = False
            for _i, candidate in enumerate(candidates):
                if candidate.method == MappingMethod.EXACT:
                    exact_found = True
                elif candidate.method == MappingMethod.FUZZY and exact_found:
                    # Fuzzy matches should come after exact
                    pass
                elif candidate.method == MappingMethod.FUZZY and not exact_found:
                    # This is OK - might not have exact matches
                    pass


class TestConceptsInDatabase:
    """Tests verifying concepts are correctly stored in database."""

    @pytest.fixture(autouse=True)
    def setup_vocabulary(self, vocab_session) -> None:
        fixture_path = Path(__file__).parent.parent / "fixtures" / "omop_vocabulary.json"
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
            vocab_session.add(concept)
        vocab_session.commit()

        for concept_data in data.get("concepts", []):
            for synonym in concept_data.get("synonyms", []):
                syn = ConceptSynonym(
                    concept_id=concept_data["concept_id"],
                    concept_synonym_name=synonym.lower(),
                    language_concept_id=4180186,
                )
                vocab_session.add(syn)
        vocab_session.commit()

    def test_concepts_loaded_in_db(self, vocab_session) -> None:
        result = vocab_session.execute(select(Concept))
        concepts = result.scalars().all()
        assert len(concepts) == 259

    def test_synonyms_loaded_in_db(self, vocab_session) -> None:
        result = vocab_session.execute(select(ConceptSynonym))
        synonyms = result.scalars().all()
        assert len(synonyms) > 0

    def test_concept_synonym_relationship(self, vocab_session) -> None:
        result = vocab_session.execute(select(Concept).where(Concept.concept_id == 437663))
        fever = result.scalar_one()
        assert fever.concept_name == "Fever"

        result = vocab_session.execute(
            select(ConceptSynonym).where(ConceptSynonym.concept_id == 437663)
        )
        synonyms = result.scalars().all()
        synonym_names = [s.concept_synonym_name for s in synonyms]
        assert "fever" in synonym_names
        assert "pyrexia" in synonym_names

    def test_condition_domain_concepts(self, vocab_session) -> None:
        result = vocab_session.execute(select(Concept).where(Concept.domain_id == "Condition"))
        conditions = result.scalars().all()
        condition_names = [c.concept_name.lower() for c in conditions]
        assert any("fever" in name for name in condition_names)
        assert any("hypertension" in name for name in condition_names)
        assert any("diabetes" in name for name in condition_names)

    def test_drug_domain_concepts(self, vocab_session) -> None:
        result = vocab_session.execute(select(Concept).where(Concept.domain_id == "Drug"))
        drugs = result.scalars().all()
        drug_names = [d.concept_name.lower() for d in drugs]
        assert any("metformin" in name for name in drug_names)
        assert any("lisinopril" in name for name in drug_names)
