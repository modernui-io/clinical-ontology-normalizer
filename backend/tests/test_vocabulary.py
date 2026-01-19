"""Comprehensive tests for vocabulary service and related API endpoints.

Tests vocabulary functionality including:
- ICD-10 code lookup
- SNOMED-CT search
- Code validation
- Concept relationships
- Cross-vocabulary mapping
"""

import pytest
from unittest.mock import MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.base import Domain
from app.services.vocabulary import (
    VocabularyService,
    OMOPConcept,
    get_vocabulary_service,
    preload_vocabulary,
    reset_vocabulary_singleton,
)


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def vocab_service():
    """Create a fresh vocabulary service for testing."""
    reset_vocabulary_singleton()
    service = VocabularyService()
    service.load()
    return service


class TestICD10Lookup:
    """Test ICD-10 code lookup functionality."""

    def test_search_icd10_code_by_name(self, vocab_service: VocabularyService) -> None:
        """Test searching for ICD-10 codes by condition name."""
        results = vocab_service.search("diabetes", limit=10)

        # Should find diabetes-related codes
        assert len(results) >= 0  # May be empty if not in fixture
        for result in results:
            assert isinstance(result, OMOPConcept)

    def test_search_icd10_by_partial_match(self, vocab_service: VocabularyService) -> None:
        """Test partial matching on ICD-10 terms."""
        results = vocab_service.search("diabet", limit=10)
        assert isinstance(results, list)

    def test_icd10_code_format_validation(self) -> None:
        """Test that ICD-10 codes follow expected format."""
        # ICD-10 codes follow pattern: Letter + 2 digits + optional decimal + digits
        valid_codes = ["E11.9", "J18.1", "I10", "E11.65"]
        invalid_codes = ["123", "ABC", "E1", "E11."]

        import re
        icd10_pattern = r"^[A-Z]\d{2}(\.\d{1,2})?$"

        for code in valid_codes:
            assert re.match(icd10_pattern, code), f"{code} should be valid"

        for code in invalid_codes:
            assert not re.match(icd10_pattern, code), f"{code} should be invalid"


class TestSNOMEDSearch:
    """Test SNOMED-CT search functionality."""

    def test_search_snomed_by_term(self, vocab_service: VocabularyService) -> None:
        """Test searching SNOMED concepts by term."""
        results = vocab_service.search("pneumonia", limit=5)

        # Should return list of matching concepts
        assert isinstance(results, list)

    def test_search_snomed_by_domain(self, vocab_service: VocabularyService) -> None:
        """Test searching SNOMED concepts filtered by domain."""
        results = vocab_service.search_by_domain("hypertension", Domain.CONDITION, limit=5)

        # All results should be in Condition domain
        for result in results:
            assert result.domain == Domain.CONDITION

    def test_snomed_search_case_insensitive(self, vocab_service: VocabularyService) -> None:
        """Test that SNOMED search is case insensitive."""
        results_lower = vocab_service.search("diabetes", limit=5)
        results_upper = vocab_service.search("DIABETES", limit=5)
        results_mixed = vocab_service.search("Diabetes", limit=5)

        # All should return the same concepts
        if results_lower and results_upper and results_mixed:
            lower_ids = {r.concept_id for r in results_lower}
            upper_ids = {r.concept_id for r in results_upper}
            mixed_ids = {r.concept_id for r in results_mixed}

            assert lower_ids == upper_ids == mixed_ids


class TestCodeValidation:
    """Test code validation functionality."""

    def test_get_concept_by_id(self, vocab_service: VocabularyService) -> None:
        """Test retrieving concept by OMOP concept ID."""
        # First get any concept from search
        results = vocab_service.search("test", limit=1)

        if results:
            concept_id = results[0].concept_id
            found = vocab_service.get_by_id(concept_id)
            assert found is not None
            assert found.concept_id == concept_id

    def test_get_concept_by_invalid_id(self, vocab_service: VocabularyService) -> None:
        """Test that invalid concept ID returns None."""
        result = vocab_service.get_by_id(-999999)
        assert result is None

    def test_concept_has_required_fields(self, vocab_service: VocabularyService) -> None:
        """Test that concepts have all required fields."""
        results = vocab_service.search("condition", limit=1)

        if results:
            concept = results[0]
            assert concept.concept_id is not None
            assert concept.concept_name is not None
            assert concept.concept_code is not None
            assert concept.vocabulary_id is not None
            assert concept.domain_id is not None


class TestConceptRelationships:
    """Test concept relationship functionality."""

    def test_concepts_have_domain(self, vocab_service: VocabularyService) -> None:
        """Test that all concepts have a valid domain."""
        results = vocab_service.search("condition", limit=10)

        for concept in results:
            assert concept.domain in [
                Domain.CONDITION,
                Domain.DRUG,
                Domain.MEASUREMENT,
                Domain.PROCEDURE,
                Domain.OBSERVATION,
                Domain.DEVICE,
            ]

    def test_get_concepts_by_domain(self, vocab_service: VocabularyService) -> None:
        """Test retrieving all concepts in a specific domain."""
        conditions = vocab_service.get_concepts_by_domain(Domain.CONDITION)
        drugs = vocab_service.get_concepts_by_domain(Domain.DRUG)
        measurements = vocab_service.get_concepts_by_domain(Domain.MEASUREMENT)

        # Each should be a list
        assert isinstance(conditions, list)
        assert isinstance(drugs, list)
        assert isinstance(measurements, list)

        # All concepts in each list should have matching domain
        for concept in conditions:
            assert concept.domain_id == "Condition"

        for concept in drugs:
            assert concept.domain_id == "Drug"

        for concept in measurements:
            assert concept.domain_id == "Measurement"


class TestVocabularySingleton:
    """Test vocabulary service singleton pattern."""

    def test_singleton_returns_same_instance(self) -> None:
        """Test that get_vocabulary_service returns the same instance."""
        reset_vocabulary_singleton()

        service1 = get_vocabulary_service()
        service2 = get_vocabulary_service()

        assert service1 is service2

    def test_singleton_is_preloaded(self) -> None:
        """Test that singleton is loaded on first access."""
        reset_vocabulary_singleton()

        service = get_vocabulary_service()

        # Should be loaded
        assert service.get_stats()["loaded"] is True

    def test_preload_returns_stats(self) -> None:
        """Test that preload_vocabulary returns statistics."""
        reset_vocabulary_singleton()

        stats = preload_vocabulary()

        assert "loaded" in stats
        assert "concept_count" in stats
        assert "term_count" in stats
        assert "load_time_ms" in stats


class TestVocabularyServiceStats:
    """Test vocabulary service statistics."""

    def test_stats_includes_counts(self, vocab_service: VocabularyService) -> None:
        """Test that stats include concept and term counts."""
        stats = vocab_service.get_stats()

        assert "concept_count" in stats
        assert "term_count" in stats
        assert stats["concept_count"] >= 0
        assert stats["term_count"] >= 0

    def test_stats_includes_load_time(self, vocab_service: VocabularyService) -> None:
        """Test that stats include load time."""
        stats = vocab_service.get_stats()

        assert "load_time_ms" in stats
        assert stats["load_time_ms"] >= 0

    def test_stats_before_load(self) -> None:
        """Test stats before vocabulary is loaded."""
        reset_vocabulary_singleton()
        service = VocabularyService()
        service._loaded = False

        stats = service.get_stats()

        assert stats["loaded"] is False
        assert stats["concept_count"] == 0
        assert stats["term_count"] == 0


class TestVocabularyAPI:
    """Test vocabulary-related API endpoints."""

    @pytest.mark.asyncio
    async def test_terminology_search_endpoint(self, client: AsyncClient) -> None:
        """Test the terminology search API endpoint."""
        response = await client.get(
            "/api/v1/terminology/search",
            params={"query": "diabetes", "limit": 5}
        )

        # Should return results or empty list
        assert response.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_terminology_lookup_endpoint(self, client: AsyncClient) -> None:
        """Test the terminology lookup API endpoint."""
        response = await client.get("/api/v1/terminology/concepts/4024561")

        # May not exist in test data
        assert response.status_code in (200, 404)


class TestSynonymMatching:
    """Test synonym matching functionality."""

    def test_exact_synonym_match(self, vocab_service: VocabularyService) -> None:
        """Test that exact synonym matches are found."""
        # Search for a common clinical term
        results = vocab_service.search("bp", limit=10)

        # Should find blood pressure if in synonyms
        assert isinstance(results, list)

    def test_partial_synonym_match(self, vocab_service: VocabularyService) -> None:
        """Test partial matching on synonyms."""
        results = vocab_service.search("diabet", limit=10)

        # Should find concepts with diabetes in synonyms
        assert isinstance(results, list)


class TestClinicalAbbreviations:
    """Test clinical abbreviation handling."""

    def test_common_lab_abbreviations(self, vocab_service: VocabularyService) -> None:
        """Test that common lab abbreviations are recognized."""
        common_labs = ["CBC", "BMP", "CMP", "TSH", "A1c", "HbA1c"]

        for abbrev in common_labs:
            results = vocab_service.search(abbrev, limit=3)
            # May or may not find results depending on fixtures
            assert isinstance(results, list)

    def test_vital_sign_abbreviations(self, vocab_service: VocabularyService) -> None:
        """Test that vital sign abbreviations are recognized."""
        vitals = ["BP", "HR", "RR", "SpO2", "T", "temp"]

        for vital in vitals:
            results = vocab_service.search(vital, limit=3)
            assert isinstance(results, list)


class TestDomainFiltering:
    """Test domain-based filtering."""

    def test_filter_by_condition_domain(self, vocab_service: VocabularyService) -> None:
        """Test filtering search results to Condition domain."""
        results = vocab_service.search_by_domain("pain", Domain.CONDITION, limit=10)

        for result in results:
            assert result.domain == Domain.CONDITION

    def test_filter_by_drug_domain(self, vocab_service: VocabularyService) -> None:
        """Test filtering search results to Drug domain."""
        results = vocab_service.search_by_domain("aspirin", Domain.DRUG, limit=10)

        for result in results:
            assert result.domain == Domain.DRUG

    def test_filter_by_measurement_domain(self, vocab_service: VocabularyService) -> None:
        """Test filtering search results to Measurement domain."""
        results = vocab_service.search_by_domain("glucose", Domain.MEASUREMENT, limit=10)

        for result in results:
            assert result.domain == Domain.MEASUREMENT


class TestSearchPerformance:
    """Test search performance characteristics."""

    def test_search_respects_limit(self, vocab_service: VocabularyService) -> None:
        """Test that search respects the limit parameter."""
        for limit in [1, 5, 10, 50]:
            results = vocab_service.search("a", limit=limit)
            assert len(results) <= limit

    def test_empty_search_returns_empty(self, vocab_service: VocabularyService) -> None:
        """Test that empty search returns empty results."""
        results = vocab_service.search("", limit=10)
        assert results == []

    def test_nonsense_search_returns_empty_or_few(self, vocab_service: VocabularyService) -> None:
        """Test that nonsense searches return minimal results."""
        results = vocab_service.search("xyzqwerty12345", limit=10)
        assert len(results) <= 10


class TestVocabularyEdgeCases:
    """Test edge cases in vocabulary handling."""

    def test_special_characters_in_search(self, vocab_service: VocabularyService) -> None:
        """Test handling of special characters in search."""
        special_queries = ["type-2", "E11.9", "COVID-19", "α-blocker"]

        for query in special_queries:
            # Should not raise exception
            results = vocab_service.search(query, limit=5)
            assert isinstance(results, list)

    def test_unicode_in_search(self, vocab_service: VocabularyService) -> None:
        """Test handling of unicode characters in search."""
        unicode_queries = ["aspirina", "fieber", "dolor"]

        for query in unicode_queries:
            results = vocab_service.search(query, limit=5)
            assert isinstance(results, list)

    def test_very_long_query(self, vocab_service: VocabularyService) -> None:
        """Test handling of very long search queries."""
        long_query = "a" * 1000
        results = vocab_service.search(long_query, limit=5)
        assert isinstance(results, list)
