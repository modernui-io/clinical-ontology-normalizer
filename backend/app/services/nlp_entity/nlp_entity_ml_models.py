"""ML model adapters for the NLP entity service.

These adapters wrap existing mention-level NLP services (ClinicalNER/ModernBERT)
and expose them via the MLModelProtocol used by the entity extraction API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID, uuid4

from app.schemas.base import Assertion as BaseAssertion, Domain, Experiencer, Temporality
from app.services.nlp import ExtractedMention
from app.services.nlp_clinical_ner import get_clinical_ner_service
from app.services.nlp_modernbert_ner import get_modernbert_ner_service

from .nlp_entity_core import ClinicalNLPEntityService, MLModelProtocol, NLPModelInfo
from .nlp_entity_extractors import ExtractedEntity
from .nlp_entity_normalizers import (
    AssertionStatus,
    ClinicalSection,
    EntitySpan,
    EntityType,
)

logger = logging.getLogger(__name__)


DOMAIN_TO_ENTITY_TYPE: dict[str, EntityType] = {
    Domain.CONDITION.value: EntityType.DIAGNOSIS,
    Domain.DRUG.value: EntityType.MEDICATION,
    Domain.MEASUREMENT.value: EntityType.LAB_RESULT,
    Domain.PROCEDURE.value: EntityType.PROCEDURE,
    Domain.OBSERVATION.value: EntityType.SYMPTOM,
    Domain.SPEC_ANATOMIC_SITE.value: EntityType.ANATOMICAL_LOCATION,
    Domain.DEVICE.value: EntityType.PROCEDURE,
}


def _map_domain_to_entity_type(domain_hint: str | None) -> EntityType:
    if not domain_hint:
        return EntityType.DIAGNOSIS
    return DOMAIN_TO_ENTITY_TYPE.get(domain_hint, EntityType.DIAGNOSIS)


def _map_assertion(mention: ExtractedMention) -> AssertionStatus:
    if mention.experiencer == Experiencer.FAMILY:
        return AssertionStatus.FAMILY_HISTORY
    if mention.temporality == Temporality.PAST:
        return AssertionStatus.HISTORICAL
    if mention.assertion:
        try:
            return AssertionStatus(mention.assertion.value)
        except ValueError:
            pass
    return AssertionStatus.PRESENT


def _clinical_ner_available() -> bool:
    try:
        import spacy  # noqa: F401
        return True
    except Exception:
        pass
    try:
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def _modernbert_available() -> bool:
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
        return True
    except Exception:
        return False


@dataclass
class MentionModelAdapter(MLModelProtocol):
    """Adapter to expose mention-level NLP services as ML models."""

    model_id: str
    name: str
    description: str
    service_getter: Callable[[], MentionServiceProtocol]
    availability_check: Callable[[], bool] | None = None

    def extract_entities(
        self, text: str, entity_types: list[EntityType] | None = None
    ) -> list[ExtractedEntity]:
        service = self.service_getter()
        try:
            mentions = service.extract_mentions(text, document_id=uuid4())
        except Exception as exc:
            logger.warning(f"ML model '{self.model_id}' extraction failed: {exc}")
            return []

        entities: list[ExtractedEntity] = []
        for mention in mentions:
            entity_type = _map_domain_to_entity_type(mention.domain_hint)
            if entity_types is not None and entity_type not in entity_types:
                continue

            entities.append(
                ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=entity_type,
                    text=mention.text,
                    normalized_text=mention.lexical_variant or mention.text,
                    span=EntitySpan(
                        start=mention.start_offset,
                        end=mention.end_offset,
                        text=mention.text,
                    ),
                    section=ClinicalSection.UNKNOWN,
                    assertion=_map_assertion(mention),
                    confidence=float(mention.confidence),
                )
            )

        return entities

    def get_model_info(self) -> NLPModelInfo:
        if self.availability_check is not None:
            is_available = self.availability_check()
        else:
            is_available = True

        return NLPModelInfo(
            model_id=self.model_id,
            name=self.name,
            description=self.description,
            entity_types=list(EntityType),
            is_available=is_available,
            version="1.0.0",
        )


def register_default_ml_models(service: ClinicalNLPEntityService) -> None:
    """Register built-in ML models on the NLP entity service."""
    try:
        available = {m.model_id for m in service.get_available_models()}
    except Exception:
        available = set()

    if "clinical_ner" not in available:
        service.register_ml_model(
            "clinical_ner",
            MentionModelAdapter(
                model_id="clinical_ner",
                name="Clinical NER (BioClinicalBERT)",
                description="Transformer-based clinical NER with spaCy fallback",
                service_getter=get_clinical_ner_service,
                availability_check=_clinical_ner_available,
            ),
        )

    if "modernbert_ner" not in available:
        service.register_ml_model(
            "modernbert_ner",
            MentionModelAdapter(
                model_id="modernbert_ner",
                name="ModernBERT NER (8K context)",
                description="ModernBERT-based clinical NER for long notes",
                service_getter=get_modernbert_ner_service,
                availability_check=_modernbert_available,
            ),
        )
class MentionServiceProtocol(Protocol):
    """Protocol for mention-level NLP services used by adapters."""

    def extract_mentions(self, text: str, document_id: UUID) -> list[ExtractedMention]:
        """Extract mentions from text."""
        ...
