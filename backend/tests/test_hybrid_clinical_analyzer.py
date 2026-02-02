from __future__ import annotations

from app.services.hybrid_clinical_analyzer import HybridClinicalAnalyzer
from app.services.nlp_coverage import calculate_token_coverage
from app.services.nlp_entity import (
    AssertionStatus,
    ClinicalSection,
    EntitySpan,
    EntityType,
    ExtractionResult,
    ExtractedEntity,
)


class _StubNLPService:
    def __init__(self, entities: list[ExtractedEntity]) -> None:
        self._entities = entities

    def extract_entities(self, text: str) -> ExtractionResult:
        return ExtractionResult(
            entities=self._entities,
            model_id="stub-model",
            processing_time_ms=0.1,
            text_length=len(text),
            sections=[],
        )


def test_hybrid_analyzer_coverage_pct_matches_token_coverage() -> None:
    note_text = "Patient has asthma and diabetes."

    asthma_start = note_text.index("asthma")
    diabetes_start = note_text.index("diabetes")

    entities = [
        ExtractedEntity(
            id="e1",
            entity_type=EntityType.DIAGNOSIS,
            text="asthma",
            normalized_text="Asthma",
            span=EntitySpan(
                start=asthma_start,
                end=asthma_start + len("asthma"),
                text="asthma",
            ),
            section=ClinicalSection.ASSESSMENT,
            assertion=AssertionStatus.PRESENT,
            confidence=0.9,
        ),
        ExtractedEntity(
            id="e2",
            entity_type=EntityType.DIAGNOSIS,
            text="diabetes",
            normalized_text="Diabetes",
            span=EntitySpan(
                start=diabetes_start,
                end=diabetes_start + len("diabetes"),
                text="diabetes",
            ),
            section=ClinicalSection.ASSESSMENT,
            assertion=AssertionStatus.PRESENT,
            confidence=0.9,
        ),
    ]

    analyzer = HybridClinicalAnalyzer(use_unified_extraction=False)
    analyzer._nlp_service = _StubNLPService(entities)

    context = analyzer._extract_with_nlp_service(note_text)

    expected = calculate_token_coverage(
        note_text,
        [(entity.span.start, entity.span.end) for entity in entities],
    )

    assert context.coverage_pct == expected.coverage_pct
    assert context.entity_count == 2
