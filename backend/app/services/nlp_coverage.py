"""Token coverage utilities for NLP extraction audits.

Calculates how much of the note's token stream is covered by extracted entity
spans, enabling MVP coverage auditing for the NLP workbench.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.services.clinical_ontology_mapper import (
    OntologyCategory,
    TokenSpan,
    get_ontology_mapper,
)


@dataclass
class CoverageStats:
    """Coverage statistics for extracted entities over tokenized text."""

    total_tokens: int
    covered_tokens: int
    coverage_pct: float
    uncovered_tokens: list[TokenSpan] = field(default_factory=list)


@dataclass
class CoverageGapToken:
    """Token span with ontology category for coverage gap reporting."""

    start: int
    end: int
    text: str
    ontology_category: str | None = None


@dataclass
class CoverageGapReport:
    """Gap report comparing extraction coverage vs ontology entity coverage."""

    total_tokens: int
    extraction_covered_tokens: int
    ontology_entity_tokens: int
    overlap_tokens: int
    extraction_only_tokens: int
    ontology_only_tokens: int
    overlap_pct: float
    extraction_only_pct: float
    ontology_only_pct: float
    extraction_only: list[CoverageGapToken] = field(default_factory=list)
    ontology_only: list[CoverageGapToken] = field(default_factory=list)


def _merge_spans(spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping spans into a sorted list."""
    normalized = sorted((start, end) for start, end in spans if start < end)
    if not normalized:
        return []

    merged: list[tuple[int, int]] = []
    current_start, current_end = normalized[0]
    for start, end in normalized[1:]:
        if start > current_end:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    merged.append((current_start, current_end))
    return merged


def calculate_token_coverage(
    text: str,
    spans: Iterable[tuple[int, int]],
    *,
    include_uncovered_tokens: bool = False,
    max_uncovered_tokens: int = 200,
) -> CoverageStats:
    """Calculate token coverage for extracted entity spans.

    Args:
        text: Full note text.
        spans: Iterable of (start, end) character offsets for extracted entities.
        include_uncovered_tokens: Whether to return a sample of uncovered tokens.
        max_uncovered_tokens: Max uncovered tokens to return (to cap response size).

    Returns:
        CoverageStats with coverage percentage and optional uncovered tokens.
    """
    mapper = get_ontology_mapper()
    tokens = mapper.tokenize_text(text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        return CoverageStats(total_tokens=0, covered_tokens=0, coverage_pct=0.0)

    merged_spans = _merge_spans(spans)

    covered_tokens = 0
    uncovered_tokens: list[TokenSpan] = []
    span_idx = 0

    for token in tokens:
        while span_idx < len(merged_spans) and merged_spans[span_idx][1] <= token.start:
            span_idx += 1

        covered = False
        if span_idx < len(merged_spans):
            span_start, span_end = merged_spans[span_idx]
            if token.end > span_start and token.start < span_end:
                covered = True

        if covered:
            covered_tokens += 1
        elif include_uncovered_tokens and len(uncovered_tokens) < max_uncovered_tokens and token.text.strip():
            uncovered_tokens.append(token)

    coverage_pct = round((covered_tokens / total_tokens) * 100, 1)

    return CoverageStats(
        total_tokens=total_tokens,
        covered_tokens=covered_tokens,
        coverage_pct=coverage_pct,
        uncovered_tokens=uncovered_tokens,
    )


def calculate_coverage_gap(
    text: str,
    spans: Iterable[tuple[int, int]],
    *,
    max_gap_tokens: int = 200,
) -> CoverageGapReport:
    """Calculate token-level gaps between extraction spans and ontology entities.

    Args:
        text: Full note text.
        spans: Iterable of (start, end) character offsets for extracted entities.
        max_gap_tokens: Max tokens to return per gap list (to cap response size).

    Returns:
        CoverageGapReport with counts, percentages, and token samples.
    """
    mapper = get_ontology_mapper()
    ontology_result = mapper.map_note(text)
    tokens = ontology_result.tokens
    total_tokens = len(tokens)

    if total_tokens == 0:
        return CoverageGapReport(
            total_tokens=0,
            extraction_covered_tokens=0,
            ontology_entity_tokens=0,
            overlap_tokens=0,
            extraction_only_tokens=0,
            ontology_only_tokens=0,
            overlap_pct=0.0,
            extraction_only_pct=0.0,
            ontology_only_pct=0.0,
        )

    merged_spans = _merge_spans(spans)

    # Keep in sync with ClinicalOntologyMapper.map_note entity categories.
    entity_categories = {
        OntologyCategory.DIAGNOSIS,
        OntologyCategory.SYMPTOM,
        OntologyCategory.MEDICATION,
        OntologyCategory.PROCEDURE,
        OntologyCategory.LAB_TEST,
        OntologyCategory.LAB_VALUE,
        OntologyCategory.VITAL_SIGN,
        OntologyCategory.VITAL_VALUE,
        OntologyCategory.IMAGING,
        OntologyCategory.FINDING,
        OntologyCategory.ANATOMY,
    }

    extraction_covered_tokens = 0
    ontology_entity_tokens = 0
    overlap_tokens = 0
    extraction_only_tokens = 0
    ontology_only_tokens = 0
    extraction_only: list[CoverageGapToken] = []
    ontology_only: list[CoverageGapToken] = []
    span_idx = 0

    for token in tokens:
        while span_idx < len(merged_spans) and merged_spans[span_idx][1] <= token.span.start:
            span_idx += 1

        covered = False
        if span_idx < len(merged_spans):
            span_start, span_end = merged_spans[span_idx]
            if token.span.end > span_start and token.span.start < span_end:
                covered = True

        is_entity = token.category in entity_categories

        if covered:
            extraction_covered_tokens += 1
        if is_entity:
            ontology_entity_tokens += 1

        if covered and is_entity:
            overlap_tokens += 1
        elif covered and not is_entity:
            extraction_only_tokens += 1
            if len(extraction_only) < max_gap_tokens and token.span.text.strip():
                extraction_only.append(
                    CoverageGapToken(
                        start=token.span.start,
                        end=token.span.end,
                        text=token.span.text,
                        ontology_category=token.category.value,
                    )
                )
        elif (not covered) and is_entity:
            ontology_only_tokens += 1
            if len(ontology_only) < max_gap_tokens and token.span.text.strip():
                ontology_only.append(
                    CoverageGapToken(
                        start=token.span.start,
                        end=token.span.end,
                        text=token.span.text,
                        ontology_category=token.category.value,
                    )
                )

    overlap_pct = (
        round((overlap_tokens / ontology_entity_tokens) * 100, 1)
        if ontology_entity_tokens
        else 0.0
    )
    ontology_only_pct = (
        round((ontology_only_tokens / ontology_entity_tokens) * 100, 1)
        if ontology_entity_tokens
        else 0.0
    )
    extraction_only_pct = (
        round((extraction_only_tokens / extraction_covered_tokens) * 100, 1)
        if extraction_covered_tokens
        else 0.0
    )

    return CoverageGapReport(
        total_tokens=total_tokens,
        extraction_covered_tokens=extraction_covered_tokens,
        ontology_entity_tokens=ontology_entity_tokens,
        overlap_tokens=overlap_tokens,
        extraction_only_tokens=extraction_only_tokens,
        ontology_only_tokens=ontology_only_tokens,
        overlap_pct=overlap_pct,
        extraction_only_pct=extraction_only_pct,
        ontology_only_pct=ontology_only_pct,
        extraction_only=extraction_only,
        ontology_only=ontology_only,
    )
