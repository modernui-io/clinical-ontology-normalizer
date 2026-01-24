"""Tests for vocabulary seed script and fixture."""

import json
from pathlib import Path

import pytest


class TestVocabularyFixture:
    """Test the OMOP vocabulary fixture file."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        """Path to the vocabulary fixture file."""
        return Path(__file__).parent.parent / "fixtures" / "omop_vocabulary.json"

    @pytest.fixture
    def vocabulary_data(self, fixture_path: Path) -> dict:
        """Load vocabulary fixture data."""
        with open(fixture_path) as f:
            return json.load(f)

    def test_fixture_exists(self, fixture_path: Path) -> None:
        """Test that vocabulary fixture file exists."""
        assert fixture_path.exists(), f"Vocabulary fixture not found: {fixture_path}"

    def test_fixture_is_valid_json(self, fixture_path: Path) -> None:
        """Test that fixture is valid JSON."""
        with open(fixture_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_fixture_has_metadata(self, vocabulary_data: dict) -> None:
        """Test that fixture has metadata section."""
        assert "metadata" in vocabulary_data
        metadata = vocabulary_data["metadata"]
        assert "version" in metadata
        assert "description" in metadata

    def test_fixture_has_concepts(self, vocabulary_data: dict) -> None:
        """Test that fixture has concepts array."""
        assert "concepts" in vocabulary_data
        assert isinstance(vocabulary_data["concepts"], list)
        assert len(vocabulary_data["concepts"]) > 0

    def test_concepts_have_required_fields(self, vocabulary_data: dict) -> None:
        """Test that each concept has required fields."""
        required_fields = [
            "concept_id",
            "concept_name",
            "domain_id",
            "vocabulary_id",
            "concept_class_id",
        ]
        for concept in vocabulary_data["concepts"]:
            for field in required_fields:
                assert field in concept, (
                    f"Missing field '{field}' in concept: {concept.get('concept_name', 'unknown')}"
                )

    def test_concepts_have_unique_ids(self, vocabulary_data: dict) -> None:
        """Test that concept_ids are unique."""
        concept_ids = [c["concept_id"] for c in vocabulary_data["concepts"]]
        assert len(concept_ids) == len(set(concept_ids)), "Duplicate concept_ids found"

    def test_concepts_cover_multiple_domains(self, vocabulary_data: dict) -> None:
        """Test that fixture covers multiple clinical domains."""
        domains = {c["domain_id"] for c in vocabulary_data["concepts"]}
        expected_domains = {"Condition", "Drug", "Measurement", "Procedure"}
        assert expected_domains.issubset(domains), (
            f"Missing domains. Expected: {expected_domains}, Found: {domains}"
        )

    def test_concepts_cover_multiple_vocabularies(self, vocabulary_data: dict) -> None:
        """Test that fixture covers multiple vocabularies."""
        vocabularies = {c["vocabulary_id"] for c in vocabulary_data["concepts"]}
        expected_vocabs = {"SNOMED", "RxNorm", "LOINC"}
        assert expected_vocabs.issubset(vocabularies), (
            f"Missing vocabularies. Expected: {expected_vocabs}, Found: {vocabularies}"
        )

    def test_concepts_have_synonyms(self, vocabulary_data: dict) -> None:
        """Test that concepts have synonyms for fuzzy matching."""
        concepts_with_synonyms = [c for c in vocabulary_data["concepts"] if c.get("synonyms")]
        assert len(concepts_with_synonyms) > 0, "No concepts have synonyms"

        # Check that most concepts have at least one synonym
        total_concepts = len(vocabulary_data["concepts"])
        assert len(concepts_with_synonyms) > total_concepts * 0.5, (
            "Less than 50% of concepts have synonyms"
        )


class TestSyntheticNoteCoverage:
    """Test that vocabulary covers concepts in synthetic notes."""

    @pytest.fixture
    def vocabulary_data(self) -> dict:
        """Load vocabulary fixture data."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "omop_vocabulary.json"
        with open(fixture_path) as f:
            return json.load(f)

    @pytest.fixture
    def synthetic_notes(self) -> dict:
        """Load synthetic notes fixture data."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "synthetic_notes.json"
        with open(fixture_path) as f:
            return json.load(f)

    def test_vocabulary_covers_conditions(self, vocabulary_data: dict) -> None:
        """Test that vocabulary includes key conditions from synthetic notes."""
        concept_names = {c["concept_name"].lower() for c in vocabulary_data["concepts"]}

        # Add synonyms to searchable names
        for concept in vocabulary_data["concepts"]:
            for synonym in concept.get("synonyms", []):
                concept_names.add(synonym.lower())

        # Key conditions from synthetic notes
        expected_conditions = [
            "pneumonia",
            "cough",
            "fever",
            "congestive heart failure",
            "colon cancer",
            "type 2 diabetes mellitus",
            "hypertension",
            "urinary tract infection",
            "chest pain",
            "myocardial infarction",
            "stroke",
            "pulmonary embolism",
        ]

        for condition in expected_conditions:
            found = any(condition.lower() in name for name in concept_names)
            assert found, f"Expected condition '{condition}' not found in vocabulary"

    def test_vocabulary_covers_drugs(self, vocabulary_data: dict) -> None:
        """Test that vocabulary includes key drugs from synthetic notes."""
        drug_names = {
            c["concept_name"].lower()
            for c in vocabulary_data["concepts"]
            if c["domain_id"] == "Drug"
        }

        # Add synonyms
        for concept in vocabulary_data["concepts"]:
            if concept["domain_id"] == "Drug":
                for synonym in concept.get("synonyms", []):
                    drug_names.add(synonym.lower())

        expected_drugs = ["metformin", "lisinopril", "aspirin", "atorvastatin"]

        for drug in expected_drugs:
            found = any(drug.lower() in name for name in drug_names)
            assert found, f"Expected drug '{drug}' not found in vocabulary"

    def test_vocabulary_covers_measurements(self, vocabulary_data: dict) -> None:
        """Test that vocabulary includes key measurements from synthetic notes."""
        measurement_names = {
            c["concept_name"].lower()
            for c in vocabulary_data["concepts"]
            if c["domain_id"] == "Measurement"
        }

        # Add synonyms
        for concept in vocabulary_data["concepts"]:
            if concept["domain_id"] == "Measurement":
                for synonym in concept.get("synonyms", []):
                    measurement_names.add(synonym.lower())

        expected_measurements = [
            "hemoglobin a1c",
            "fasting glucose",
            "creatinine",
            "blood pressure",
            "d-dimer",
        ]

        for measurement in expected_measurements:
            found = any(measurement.lower() in name for name in measurement_names)
            assert found, f"Expected measurement '{measurement}' not found in vocabulary"


class TestSeedScriptModule:
    """Test that seed script module is importable and well-formed."""

    def test_seed_vocabulary_module_importable(self) -> None:
        """Test that seed_vocabulary module can be imported."""
        from app.scripts import seed_vocabulary

        assert seed_vocabulary is not None

    def test_seed_vocabulary_has_main_function(self) -> None:
        """Test that seed_vocabulary has main async function."""
        import asyncio

        from app.scripts.seed_vocabulary import seed_vocabulary

        assert asyncio.iscoroutinefunction(seed_vocabulary)

    def test_seed_vocabulary_has_load_fixture_function(self) -> None:
        """Test that seed_vocabulary has fixture loading function."""
        import asyncio

        from app.scripts.seed_vocabulary import load_vocabulary_fixture

        assert asyncio.iscoroutinefunction(load_vocabulary_fixture)

    def test_vocabulary_file_path_is_correct(self) -> None:
        """Test that the vocabulary file path in seed script is correct."""
        from app.scripts.seed_vocabulary import VOCABULARY_FILE

        assert VOCABULARY_FILE.exists(), f"Vocabulary file not found: {VOCABULARY_FILE}"
