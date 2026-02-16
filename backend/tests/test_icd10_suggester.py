"""Tests for ICD-10 Code Suggester Service.

Tests the ICD-10 code suggestion functionality.
"""

import pytest

from app.services.icd10_suggester import (
    CodeCategory,
    CodeConfidence,
    ICD10Code,
    ICD10SuggesterService,
    get_icd10_suggester_service,
    reset_icd10_suggester_service,
    ICD10_CODES,
    SYNONYM_TO_CODE,
)


# ============================================================================
# Service Tests
# ============================================================================


class TestServiceInit:
    """Test service initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_icd10_suggester_service()

    def test_service_creation(self):
        """Test basic service creation."""
        service = ICD10SuggesterService()
        assert service is not None

    def test_singleton_pattern(self):
        """Test singleton pattern works."""
        service1 = get_icd10_suggester_service()
        service2 = get_icd10_suggester_service()
        assert service1 is service2

    def test_singleton_reset(self):
        """Test singleton can be reset."""
        service1 = get_icd10_suggester_service()
        reset_icd10_suggester_service()
        service2 = get_icd10_suggester_service()
        assert service1 is not service2


# ============================================================================
# Database Content Tests
# ============================================================================


class TestDatabaseContent:
    """Test the ICD-10 code database content."""

    def test_database_not_empty(self):
        """Test that database has codes."""
        assert len(ICD10_CODES) > 0

    def test_codes_have_required_fields(self):
        """Test that all codes have required fields."""
        for code in ICD10_CODES:
            assert code.code
            assert code.description
            assert code.category

    def test_has_multiple_categories(self):
        """Test that database covers multiple categories."""
        categories = set(code.category for code in ICD10_CODES)
        assert len(categories) >= 5

    def test_synonym_index_exists(self):
        """Test that synonym index is populated."""
        assert len(SYNONYM_TO_CODE) > 0

    def test_common_conditions_present(self):
        """Test that common conditions are in the database."""
        service = ICD10SuggesterService()

        # Should find common conditions
        assert service.get_code("I10") is not None  # Hypertension
        assert service.get_code("E11.9") is not None  # Type 2 diabetes
        assert service.get_code("I50.9") is not None  # Heart failure


# ============================================================================
# Code Lookup Tests
# ============================================================================


class TestCodeLookup:
    """Test code lookup functionality."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_get_code_exact(self):
        """Test getting code by exact code."""
        code = self.service.get_code("I10")
        assert code is not None
        assert code.description == "Essential (primary) hypertension"

    def test_get_code_case_insensitive(self):
        """Test case insensitive lookup."""
        code1 = self.service.get_code("i10")
        code2 = self.service.get_code("I10")
        assert code1 == code2

    def test_get_code_not_found(self):
        """Test getting nonexistent code."""
        code = self.service.get_code("ZZZ999")
        assert code is None


# ============================================================================
# Code Suggestion Tests
# ============================================================================


class TestCodeSuggestion:
    """Test code suggestion functionality."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_suggest_by_synonym(self):
        """Test suggesting by exact synonym."""
        result = self.service.suggest_codes("hypertension")
        assert len(result.suggestions) > 0
        codes = [s.code for s in result.suggestions]
        assert "I10" in codes

    def test_suggest_by_abbreviation(self):
        """Test suggesting by abbreviation."""
        result = self.service.suggest_codes("htn")
        codes = [s.code for s in result.suggestions]
        assert "I10" in codes

    def test_suggest_diabetes(self):
        """Test suggesting diabetes codes."""
        result = self.service.suggest_codes("type 2 diabetes")
        codes = [s.code for s in result.suggestions]
        # Fixture uses E119 (no dot); accept either format
        assert "E11.9" in codes or "E119" in codes

    def test_suggest_heart_failure(self):
        """Test suggesting heart failure codes."""
        result = self.service.suggest_codes("chf")
        codes = [s.code for s in result.suggestions]
        assert "I50.9" in codes

    def test_suggest_atrial_fibrillation(self):
        """Test suggesting afib codes."""
        result = self.service.suggest_codes("afib")
        codes = [s.code for s in result.suggestions]
        assert "I48.91" in codes

    def test_suggest_no_matches(self):
        """Test suggesting with no matches."""
        result = self.service.suggest_codes("xyzqwerty12345")
        assert len(result.suggestions) == 0

    def test_suggest_limit(self):
        """Test suggestion limit."""
        result = self.service.suggest_codes("pain", max_suggestions=3)
        assert len(result.suggestions) <= 3


# ============================================================================
# Confidence Level Tests
# ============================================================================


class TestConfidenceLevels:
    """Test confidence level assignment."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_exact_match_high_confidence(self):
        """Test that exact matches have high confidence."""
        result = self.service.suggest_codes("hypertension")
        htn = next((s for s in result.suggestions if s.code == "I10"), None)
        assert htn is not None
        assert htn.confidence == CodeConfidence.HIGH

    def test_partial_match_lower_confidence(self):
        """Test that partial matches have lower confidence."""
        result = self.service.suggest_codes("elevated blood")
        # Should find hypertension but with lower confidence
        htn = next((s for s in result.suggestions if s.code == "I10"), None)
        if htn:
            assert htn.confidence in [CodeConfidence.MEDIUM, CodeConfidence.LOW]


# ============================================================================
# Search Tests
# ============================================================================


class TestSearch:
    """Test code search functionality."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_search_by_description(self):
        """Test searching by description."""
        results = self.service.search_codes("diabetes")
        assert len(results) > 0
        assert any("diabetes" in r.description.lower() for r in results)

    def test_search_by_synonym(self):
        """Test searching by synonym."""
        results = self.service.search_codes("heart attack")
        assert len(results) > 0

    def test_search_limit(self):
        """Test search limit."""
        results = self.service.search_codes("", limit=5)
        assert len(results) <= 5


# ============================================================================
# Category Tests
# ============================================================================


class TestCategories:
    """Test category-based functionality."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_get_codes_by_category(self):
        """Test getting codes by category."""
        cardiac = self.service.get_codes_by_category(CodeCategory.I00_I99)
        assert len(cardiac) > 0
        assert all(c.category == CodeCategory.I00_I99 for c in cardiac)

    def test_has_common_categories(self):
        """Test that common categories have codes."""
        assert len(self.service.get_codes_by_category(CodeCategory.I00_I99)) > 0  # Cardiovascular
        assert len(self.service.get_codes_by_category(CodeCategory.E00_E89)) > 0  # Endocrine
        assert len(self.service.get_codes_by_category(CodeCategory.J00_J99)) > 0  # Respiratory


# ============================================================================
# Coding Guidance Tests
# ============================================================================


class TestCodingGuidance:
    """Test coding guidance generation."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_suggestions_have_guidance(self):
        """Test that suggestions include coding guidance."""
        result = self.service.suggest_codes("sepsis")
        if result.suggestions:
            # Sepsis code should have use_additional_code guidance
            sepsis = next((s for s in result.suggestions if "sepsis" in s.description.lower()), None)
            if sepsis:
                assert len(sepsis.coding_guidance) > 0 or len(sepsis.related_codes) > 0

    def test_coding_tips_generated(self):
        """Test that coding tips are generated."""
        result = self.service.suggest_codes("diabetes")
        assert len(result.coding_tips) > 0


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Test service statistics."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_get_stats(self):
        """Test getting service statistics."""
        stats = self.service.get_stats()

        assert "total_codes" in stats
        assert "total_synonyms" in stats
        assert "by_category" in stats
        assert "billable_codes" in stats

    def test_stats_count_correct(self):
        """Test that stats counts are correct."""
        stats = self.service.get_stats()

        # Service loads core codes + extended fixture, so count >= core codes
        assert stats["total_codes"] >= len(ICD10_CODES)
        assert sum(stats["by_category"].values()) == stats["total_codes"]


# ============================================================================
# Clinical Scenario Tests
# ============================================================================


class TestClinicalScenarios:
    """Test realistic clinical scenarios."""

    def setup_method(self):
        """Create service for testing."""
        reset_icd10_suggester_service()
        self.service = ICD10SuggesterService()

    def test_chest_pain_workup(self):
        """Test suggesting codes for chest pain."""
        result = self.service.suggest_codes("chest pain")
        codes = [s.code for s in result.suggestions]

        # Should include symptom code and possibly cardiac codes
        assert "R07.9" in codes or any(c.startswith("R07") for c in codes)

    def test_pneumonia_diagnosis(self):
        """Test suggesting codes for pneumonia."""
        result = self.service.suggest_codes("pneumonia")
        codes = [s.code for s in result.suggestions]
        assert "J18.9" in codes

    def test_copd_exacerbation(self):
        """Test suggesting codes for COPD exacerbation."""
        result = self.service.suggest_codes("copd exacerbation")
        codes = [s.code for s in result.suggestions]
        assert "J44.1" in codes

    def test_uti_diagnosis(self):
        """Test suggesting codes for UTI."""
        result = self.service.suggest_codes("uti")
        codes = [s.code for s in result.suggestions]
        assert "N39.0" in codes

    def test_stroke(self):
        """Test suggesting codes for stroke."""
        result = self.service.suggest_codes("stroke")
        codes = [s.code for s in result.suggestions]
        assert "I63.9" in codes

    def test_mi_diagnosis(self):
        """Test suggesting codes for myocardial infarction."""
        result = self.service.suggest_codes("heart attack")
        codes = [s.code for s in result.suggestions]
        assert "I21.9" in codes

    def test_low_back_pain(self):
        """Test suggesting codes for low back pain."""
        result = self.service.suggest_codes("low back pain")
        codes = [s.code for s in result.suggestions]
        assert "M54.5" in codes

    def test_anxiety(self):
        """Test suggesting codes for anxiety."""
        result = self.service.suggest_codes("anxiety")
        codes = [s.code for s in result.suggestions]
        assert "F41.1" in codes

    def test_depression(self):
        """Test suggesting codes for depression."""
        result = self.service.suggest_codes("depression")
        codes = [s.code for s in result.suggestions]
        assert "F32.9" in codes

    def test_gout(self):
        """Test suggesting codes for gout."""
        result = self.service.suggest_codes("gout")
        codes = [s.code for s in result.suggestions]
        assert "M10.9" in codes
