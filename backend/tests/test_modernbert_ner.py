"""Tests for ModernBERT clinical NER service."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.nlp_modernbert_ner import (
    ModernBERTConfig,
    ModernBERTNERService,
    EntityWithContext,
    get_modernbert_ner_service,
    reset_modernbert_ner_service,
)


class TestModernBERTConfig:
    """Test ModernBERT NER configuration."""

    def test_default_config(self):
        """Default config should have 8192 sequence length."""
        config = ModernBERTConfig()
        assert config.max_sequence_length == 8192
        assert config.model_name == "answerdotai/ModernBERT-base"
        assert config.use_flash_attention is True
        assert config.use_gpu is True

    def test_custom_config(self):
        """Custom config values should be respected."""
        config = ModernBERTConfig(
            model_name="custom-model",
            max_sequence_length=4096,
            min_confidence=0.7,
            use_flash_attention=False,
        )
        assert config.model_name == "custom-model"
        assert config.max_sequence_length == 4096
        assert config.min_confidence == 0.7
        assert config.use_flash_attention is False

    def test_fallback_models(self):
        """Fallback models should be configured."""
        config = ModernBERTConfig()
        assert len(config.fallback_models) >= 1
        assert "samrawal/bert-base-uncased_clinical-ner" in config.fallback_models


class TestModernBERTNERServiceInit:
    """Test ModernBERT NER service initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_modernbert_ner_service()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_modernbert_ner_service()

    def test_service_creation(self):
        """Service should be creatable."""
        service = ModernBERTNERService()
        assert service is not None
        assert service.config is not None

    def test_singleton_pattern(self):
        """Singleton should return same instance."""
        service1 = get_modernbert_ner_service()
        service2 = get_modernbert_ner_service()
        assert service1 is service2

    def test_singleton_reset(self):
        """Reset should create new instance."""
        service1 = get_modernbert_ner_service()
        reset_modernbert_ner_service()
        service2 = get_modernbert_ner_service()
        assert service1 is not service2

    def test_config_propagates(self):
        """Config should be accessible on service."""
        config = ModernBERTConfig(min_confidence=0.8)
        service = ModernBERTNERService(config=config)
        assert service.config.min_confidence == 0.8


class TestModernBERTNERServiceExtraction:
    """Test ModernBERT entity extraction."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_modernbert_ner_service()

    def test_extract_mentions_interface(self):
        """extract_mentions should return list."""
        service = ModernBERTNERService()
        mentions = service.extract_mentions(
            "Patient has diabetes mellitus type 2.",
            uuid4(),
        )
        # May be empty if model not available
        assert isinstance(mentions, list)

    def test_extract_entities_interface(self):
        """extract_entities should return list of dicts."""
        service = ModernBERTNERService()
        entities = service.extract_entities(
            "Patient has hypertension and diabetes."
        )
        assert isinstance(entities, list)

    def test_extract_with_context_interface(self):
        """extract_with_context should return EntityWithContext objects."""
        service = ModernBERTNERService()
        entities = service.extract_with_context(
            "History of chest pain. Patient denies shortness of breath."
        )
        assert isinstance(entities, list)
        for ent in entities:
            assert isinstance(ent, EntityWithContext)
            assert hasattr(ent, "context_before")
            assert hasattr(ent, "context_after")

    def test_get_stats(self):
        """get_stats should return service info."""
        service = ModernBERTNERService()
        stats = service.get_stats()
        assert "model_available" in stats
        assert "device" in stats
        assert "flash_attention" in stats
        assert "max_sequence_length" in stats


class TestModernBERTAssertionDetection:
    """Test assertion detection in ModernBERT service."""

    def test_detect_negation(self):
        """Negation should be detected from context."""
        service = ModernBERTNERService()
        # Force initialization to access private methods
        service._initialized = True

        from app.schemas.base import Assertion
        result = service._detect_assertion(
            "Patient denies chest pain.",
            15,  # "chest pain" start
            25,  # "chest pain" end
        )
        assert result == Assertion.ABSENT

    def test_detect_uncertainty(self):
        """Uncertainty should be detected from context."""
        service = ModernBERTNERService()
        service._initialized = True

        from app.schemas.base import Assertion
        result = service._detect_assertion(
            "Possible pneumonia on imaging.",
            9,  # "pneumonia" start
            18,  # "pneumonia" end
        )
        assert result == Assertion.POSSIBLE

    def test_detect_present(self):
        """Present assertion should be default."""
        service = ModernBERTNERService()
        service._initialized = True

        from app.schemas.base import Assertion
        result = service._detect_assertion(
            "Patient has diabetes.",
            12,  # "diabetes" start
            20,  # "diabetes" end
        )
        assert result == Assertion.PRESENT


class TestModernBERTTemporalityDetection:
    """Test temporality detection."""

    def test_detect_past(self):
        """Past temporality should be detected."""
        service = ModernBERTNERService()
        service._initialized = True

        from app.schemas.base import Temporality
        result = service._detect_temporality(
            "History of myocardial infarction.",
            11,  # "myocardial infarction" start
            32,  # end
        )
        assert result == Temporality.PAST

    def test_detect_current(self):
        """Current temporality should be default."""
        service = ModernBERTNERService()
        service._initialized = True

        from app.schemas.base import Temporality
        result = service._detect_temporality(
            "Patient has hypertension.",
            12,  # start
            24,  # end
        )
        assert result == Temporality.CURRENT


class TestModernBERTExperiencerDetection:
    """Test experiencer detection."""

    def test_detect_family(self):
        """Family experiencer should be detected."""
        service = ModernBERTNERService()
        service._initialized = True

        from app.schemas.base import Experiencer
        result = service._detect_experiencer(
            "Family history of colon cancer.",
            18,  # start
            30,  # end
        )
        assert result == Experiencer.FAMILY

    def test_detect_patient(self):
        """Patient experiencer should be default."""
        service = ModernBERTNERService()
        service._initialized = True

        from app.schemas.base import Experiencer
        result = service._detect_experiencer(
            "Patient has diabetes.",
            12,  # start
            20,  # end
        )
        assert result == Experiencer.PATIENT


class TestModernBERTChunking:
    """Test chunking for very long documents."""

    def test_deduplicate_entities(self):
        """Duplicate entities should be removed."""
        service = ModernBERTNERService()

        entities = [
            {"word": "diabetes", "start": 10, "end": 18, "score": 0.9},
            {"word": "diabetes", "start": 10, "end": 18, "score": 0.85},  # duplicate
            {"word": "hypertension", "start": 30, "end": 42, "score": 0.88},
        ]

        deduplicated = service._deduplicate_entities(entities)
        assert len(deduplicated) == 2

    def test_get_sentence(self):
        """Sentence extraction should work."""
        service = ModernBERTNERService()
        service._initialized = True

        text = "Patient is a 65 year old male. He has diabetes. Blood pressure is elevated."
        sentence = service._get_sentence(text, 38)  # Position of "diabetes"

        assert sentence is not None
        assert "diabetes" in sentence


class TestEntityWithContext:
    """Test EntityWithContext dataclass."""

    def test_entity_with_context_fields(self):
        """EntityWithContext should have all required fields."""
        entity = EntityWithContext(
            text="diabetes",
            start=10,
            end=18,
            entity_type="DISEASE",
            confidence=0.92,
            context_before="Patient has ",
            context_after=" mellitus type 2.",
            full_sentence="Patient has diabetes mellitus type 2.",
        )

        assert entity.text == "diabetes"
        assert entity.start == 10
        assert entity.end == 18
        assert entity.entity_type == "DISEASE"
        assert entity.confidence == 0.92
        assert entity.context_before == "Patient has "
        assert entity.context_after == " mellitus type 2."
        assert entity.full_sentence is not None
