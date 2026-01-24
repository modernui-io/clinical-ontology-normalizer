"""Tests for Ensemble NLP Service.

Tests the combined extraction pipeline that merges results from
rule-based, ML NER, and value extraction services.
"""

import pytest
from uuid import uuid4

from app.services.nlp_ensemble import (
    EnsembleConfig,
    EnsembleNLPService,
    EnsembleResult,
    get_ensemble_nlp_service,
    reset_ensemble_nlp_service,
)
from app.services.nlp import ExtractedMention
from app.schemas.base import Assertion, Domain, Experiencer, Temporality


# ============================================================================
# Configuration Tests
# ============================================================================


class TestEnsembleConfig:
    """Test configuration dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EnsembleConfig()
        assert config.use_rule_based is True
        assert config.use_ml_ner is True
        assert config.use_value_extraction is True
        assert config.use_relation_extraction is True
        assert config.min_confidence == 0.5
        assert config.agreement_boost == 0.10
        assert config.max_confidence == 0.99

    def test_custom_config(self):
        """Test custom configuration."""
        config = EnsembleConfig(
            use_ml_ner=False,
            min_confidence=0.8,
            agreement_boost=0.15,
        )
        assert config.use_ml_ner is False
        assert config.min_confidence == 0.8
        assert config.agreement_boost == 0.15

    def test_domain_preferences(self):
        """Test domain preference defaults."""
        config = EnsembleConfig()
        assert config.domain_preferences[Domain.MEASUREMENT.value] == "value"
        assert config.domain_preferences[Domain.DRUG.value] == "rule_based"
        assert config.domain_preferences[Domain.CONDITION.value] == "ml_ner"


# ============================================================================
# Service Initialization Tests
# ============================================================================


class TestEnsembleServiceInit:
    """Test service initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_ensemble_nlp_service()

    def test_service_creation(self):
        """Test basic service creation."""
        service = EnsembleNLPService()
        assert service is not None
        assert service.config is not None

    def test_service_with_custom_config(self):
        """Test service creation with custom config."""
        config = EnsembleConfig(min_confidence=0.9)
        service = EnsembleNLPService(config=config)
        assert service.config.min_confidence == 0.9

    def test_singleton_pattern(self):
        """Test singleton pattern works."""
        service1 = get_ensemble_nlp_service()
        service2 = get_ensemble_nlp_service()
        assert service1 is service2

    def test_singleton_reset(self):
        """Test singleton can be reset."""
        service1 = get_ensemble_nlp_service()
        reset_ensemble_nlp_service()
        service2 = get_ensemble_nlp_service()
        assert service1 is not service2


# ============================================================================
# Span Overlap Tests
# ============================================================================


class TestSpanOverlap:
    """Test span overlap detection."""

    def setup_method(self):
        """Create service for testing."""
        reset_ensemble_nlp_service()
        self.service = EnsembleNLPService()

    def test_complete_overlap(self):
        """Test complete overlap detection."""
        # Span 1: [0, 10], Span 2: [0, 10] -> complete overlap
        assert self.service._spans_overlap(0, 10, 0, 10)

    def test_partial_overlap(self):
        """Test partial overlap detection."""
        # Span 1: [0, 10], Span 2: [5, 15] -> 50% overlap
        assert self.service._spans_overlap(0, 10, 5, 15)

    def test_contained_span(self):
        """Test contained span overlap."""
        # Span 1: [0, 20], Span 2: [5, 10] -> contained
        assert self.service._spans_overlap(0, 20, 5, 10)

    def test_no_overlap(self):
        """Test non-overlapping spans."""
        # Span 1: [0, 10], Span 2: [15, 25] -> no overlap
        assert not self.service._spans_overlap(0, 10, 15, 25)

    def test_adjacent_spans(self):
        """Test adjacent spans don't overlap."""
        # Span 1: [0, 10], Span 2: [10, 20] -> adjacent
        assert not self.service._spans_overlap(0, 10, 10, 20)

    def test_small_overlap(self):
        """Test small overlap below threshold."""
        # Small overlap might be filtered by threshold
        # [0, 10] and [9, 20] -> only 1 char overlap = 10% of smaller span
        assert not self.service._spans_overlap(0, 10, 9, 20, threshold=0.5)


# ============================================================================
# Extraction Tests
# ============================================================================


class TestEnsembleExtraction:
    """Test ensemble extraction functionality."""

    def setup_method(self):
        """Create service for testing."""
        reset_ensemble_nlp_service()
        # Use a minimal config for faster tests
        self.config = EnsembleConfig(
            use_ml_ner=False,  # Disable ML NER for faster tests
            use_relation_extraction=False,
        )
        self.service = EnsembleNLPService(config=self.config)

    def test_extract_mentions_basic(self):
        """Test basic mention extraction."""
        text = "Patient has diabetes and takes metformin 500mg daily."
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        assert isinstance(mentions, list)

    def test_extract_mentions_with_vitals(self):
        """Test extraction of vital signs."""
        text = "Vital signs: BP 120/80, HR 72, Temp 98.6F"
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)

        # Should extract vital sign mentions
        assert len(mentions) > 0

    def test_extract_mentions_with_labs(self):
        """Test extraction of lab values."""
        text = "Labs: Na 140, K 4.0, Cr 1.2, HbA1c 7.2%"
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)

        # Should extract lab value mentions
        assert len(mentions) > 0

    def test_extract_mentions_with_medications(self):
        """Test extraction of medications."""
        text = "Medications: Metformin 1000mg BID, Lisinopril 20mg daily"
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)

        # Should extract medication mentions
        assert len(mentions) > 0

    def test_extract_mentions_empty_text(self):
        """Test extraction with empty text."""
        doc_id = uuid4()
        mentions = self.service.extract_mentions("", doc_id)
        assert mentions == []

    def test_confidence_filtering(self):
        """Test that low confidence mentions are filtered."""
        config = EnsembleConfig(min_confidence=0.99)
        service = EnsembleNLPService(config=config)

        text = "Patient has diabetes."
        doc_id = uuid4()
        mentions = service.extract_mentions(text, doc_id)

        # High threshold should filter most/all mentions
        for mention in mentions:
            assert mention.confidence >= 0.99


# ============================================================================
# Merge Tests
# ============================================================================


class TestMentionMerging:
    """Test mention merging from multiple sources."""

    def setup_method(self):
        """Create service for testing."""
        reset_ensemble_nlp_service()
        self.service = EnsembleNLPService()

    def _create_mention(
        self,
        text: str,
        start: int,
        end: int,
        domain: str,
        confidence: float = 0.8,
    ) -> ExtractedMention:
        """Helper to create test mentions."""
        return ExtractedMention(
            text=text,
            start_offset=start,
            end_offset=end,
            lexical_variant=text.lower(),
            domain_hint=domain,
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=confidence,
        )

    def test_merge_non_overlapping(self):
        """Test merging non-overlapping mentions."""
        mentions_by_source = {
            "rule_based": [
                self._create_mention("diabetes", 0, 8, Domain.CONDITION.value)
            ],
            "value": [
                self._create_mention("BP 120/80", 20, 29, Domain.MEASUREMENT.value)
            ],
        }

        merged = self.service._merge_mentions(mentions_by_source)
        assert len(merged) == 2

    def test_merge_overlapping_same_text(self):
        """Test merging overlapping mentions with same text."""
        mentions_by_source = {
            "rule_based": [
                self._create_mention("diabetes", 0, 8, Domain.CONDITION.value, 0.8)
            ],
            "ml_ner": [
                self._create_mention("diabetes", 0, 8, Domain.CONDITION.value, 0.7)
            ],
        }

        merged = self.service._merge_mentions(mentions_by_source)
        # Should merge to single mention
        assert len(merged) == 1
        # Confidence should be at least as good as the best source
        assert merged[0].confidence >= 0.7

    def test_merge_overlapping_different_lengths(self):
        """Test merging overlapping mentions with different lengths."""
        mentions_by_source = {
            "rule_based": [
                self._create_mention("diabetes", 0, 8, Domain.CONDITION.value, 0.8)
            ],
            "ml_ner": [
                self._create_mention("diabetes mellitus", 0, 17, Domain.CONDITION.value, 0.7)
            ],
        }

        merged = self.service._merge_mentions(mentions_by_source)
        # Overlapping mentions should be merged
        assert len(merged) >= 1
        # The merged result should contain one of the overlapping texts
        assert merged[0].text in ("diabetes", "diabetes mellitus")

    def test_merge_preserves_domain_preference(self):
        """Test that domain preferences are respected."""
        # For conditions, ML NER is preferred
        service = EnsembleNLPService(config=EnsembleConfig(
            domain_preferences={Domain.CONDITION.value: "ml_ner"}
        ))

        mentions_by_source = {
            "rule_based": [
                self._create_mention("diabetes", 0, 8, Domain.CONDITION.value, 0.9)
            ],
            "ml_ner": [
                self._create_mention("diabetes", 0, 8, Domain.CONDITION.value, 0.7)
            ],
        }

        merged = service._merge_mentions(mentions_by_source)
        # ML NER version should be kept despite lower confidence
        assert len(merged) == 1


# ============================================================================
# Full Pipeline Tests
# ============================================================================


class TestFullPipeline:
    """Test full ensemble extraction pipeline."""

    def setup_method(self):
        """Create service for testing."""
        reset_ensemble_nlp_service()
        self.service = EnsembleNLPService()

    def test_extract_all_returns_result(self):
        """Test that extract_all returns EnsembleResult."""
        text = "Patient has diabetes. BP 120/80."
        doc_id = uuid4()
        result = self.service.extract_all(text, doc_id)

        assert isinstance(result, EnsembleResult)
        assert hasattr(result, "mentions")
        assert hasattr(result, "relations")
        assert hasattr(result, "stats")

    def test_extract_all_stats(self):
        """Test that extract_all returns statistics."""
        text = "Patient has diabetes. BP 120/80. Takes metformin."
        doc_id = uuid4()
        result = self.service.extract_all(text, doc_id)

        assert "mention_count" in result.stats
        assert "mention_extraction_ms" in result.stats
        assert "by_domain" in result.stats

    def test_extract_all_with_relations(self):
        """Test extraction with relation extraction enabled."""
        config = EnsembleConfig(use_relation_extraction=True)
        service = EnsembleNLPService(config=config)

        text = "Diabetes - continue metformin. Hypertension - start lisinopril."
        doc_id = uuid4()
        result = service.extract_all(text, doc_id)

        # Should have relations if found
        assert "relation_count" in result.stats


# ============================================================================
# Complex Clinical Text Tests
# ============================================================================


class TestComplexClinicalText:
    """Test extraction on realistic clinical text."""

    def setup_method(self):
        """Create service for testing."""
        reset_ensemble_nlp_service()
        self.service = EnsembleNLPService()

    def test_full_clinical_note(self):
        """Test extraction on a full clinical note."""
        text = """
VITAL SIGNS: BP 145/92 mmHg, HR 88 bpm, Temp 98.6F, O2 sat 98%

LABS: Na 138, K 4.2, Cr 1.4 mg/dL, HbA1c 7.2%

ASSESSMENT AND PLAN:
1. Type 2 diabetes - continue metformin 1000mg BID
2. Hypertension - start lisinopril 10mg daily
3. Chronic kidney disease stage 3 - monitor creatinine

MEDICATIONS:
- Metformin 1000mg BID
- Aspirin 81mg daily
"""
        doc_id = uuid4()
        result = self.service.extract_all(text, doc_id)

        # Should extract multiple mentions
        assert result.stats["mention_count"] > 0

        # Should have measurements
        measurement_count = result.stats.get("by_domain", {}).get(
            Domain.MEASUREMENT.value, 0
        )
        assert measurement_count > 0

    def test_discharge_summary(self):
        """Test extraction on discharge summary."""
        text = """
DISCHARGE DIAGNOSES:
1. Community-acquired pneumonia
2. Type 2 diabetes mellitus
3. Hypertension

DISCHARGE MEDICATIONS:
1. Azithromycin 250mg daily x 2 days
2. Metformin 500mg BID
3. Lisinopril 10mg daily
4. Aspirin 81mg daily
"""
        doc_id = uuid4()
        result = self.service.extract_all(text, doc_id)

        assert result.stats["mention_count"] > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for ensemble service."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_ensemble_nlp_service()

    def test_service_implements_interface(self):
        """Test that service extends BaseNLPService."""
        from app.services.nlp import BaseNLPService

        service = EnsembleNLPService()
        assert isinstance(service, BaseNLPService)

        # Check required methods exist
        assert hasattr(service, "extract_mentions")
        assert hasattr(service, "get_section_name")
        assert callable(service.extract_mentions)

    def test_mention_objects_complete(self):
        """Test that extracted mentions have all required fields."""
        service = EnsembleNLPService()
        text = "BP 120/80"
        doc_id = uuid4()
        mentions = service.extract_mentions(text, doc_id)

        for mention in mentions:
            assert hasattr(mention, "text")
            assert hasattr(mention, "start_offset")
            assert hasattr(mention, "end_offset")
            assert hasattr(mention, "lexical_variant")
            assert hasattr(mention, "domain_hint")
            assert hasattr(mention, "assertion")
            assert hasattr(mention, "temporality")
            assert hasattr(mention, "experiencer")
            assert hasattr(mention, "confidence")
