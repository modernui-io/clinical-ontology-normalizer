"""ModernBERT-based clinical NER service.

Provides a ModernBERT-backed variant of the clinical NER service with a
different default transformer model while reusing the existing extraction
logic, assertion detection, and OMOP domain mapping.
"""

from dataclasses import dataclass, field

from app.services.nlp_clinical_ner import ClinicalNERService, TransformerNERConfig


@dataclass
class ModernBERTNERConfig(TransformerNERConfig):
    """Configuration for ModernBERT-based clinical NER."""

    # ModernBERT clinical NER checkpoint (override with your fine-tuned model)
    model_name: str = "modernbert-clinical-ner"

    # Prefer legacy clinical NER checkpoints as fallbacks if ModernBERT is unavailable
    fallback_models: tuple[str, ...] = (
        "samrawal/bert-base-uncased_clinical-ner",
        "alvaroalon2/biobert_diseases_ner",
        "dmis-lab/biobert-base-cased-v1.1",
    )


@dataclass
class ModernBERTNERService(ClinicalNERService):
    """Clinical NER service using ModernBERT as the primary transformer model."""

    config: ModernBERTNERConfig = field(default_factory=ModernBERTNERConfig)


_modernbert_ner_service: ModernBERTNERService | None = None


def get_modernbert_ner_service(
    config: ModernBERTNERConfig | None = None,
) -> ModernBERTNERService:
    """Get the singleton ModernBERT NER service."""
    global _modernbert_ner_service
    if _modernbert_ner_service is None:
        _modernbert_ner_service = ModernBERTNERService(
            config=config or ModernBERTNERConfig()
        )
    return _modernbert_ner_service


def reset_modernbert_ner_service() -> None:
    """Reset the ModernBERT singleton service (mainly for testing)."""
    global _modernbert_ner_service
    _modernbert_ner_service = None
