"""Tests for ModernBERT clinical NER service."""

from uuid import uuid4

from app.services.nlp_modernbert_ner import (
    ModernBERTNERConfig,
    ModernBERTNERService,
    get_modernbert_ner_service,
    reset_modernbert_ner_service,
)


class TestModernBERTNERConfig:
    """Test ModernBERT NER configuration."""

    def test_default_config(self):
        config = ModernBERTNERConfig()
        assert config.model_name == "modernbert-clinical-ner"
        assert "samrawal/bert-base-uncased_clinical-ner" in config.fallback_models


class TestModernBERTNERServiceInit:
    """Test ModernBERT NER service initialization and singleton behavior."""

    def setup_method(self):
        reset_modernbert_ner_service()

    def test_service_creation(self):
        service = ModernBERTNERService()
        assert service is not None
        assert service.config is not None

    def test_singleton_pattern(self):
        service1 = get_modernbert_ner_service()
        service2 = get_modernbert_ner_service()
        assert service1 is service2

    def test_singleton_reset(self):
        service1 = get_modernbert_ner_service()
        reset_modernbert_ner_service()
        service2 = get_modernbert_ner_service()
        assert service1 is not service2

    def test_extract_mentions_runs(self):
        service = ModernBERTNERService()
        mentions = service.extract_mentions("Patient has diabetes.", uuid4())
        assert isinstance(mentions, list)
