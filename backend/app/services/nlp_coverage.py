"""Token coverage utilities for NLP extraction audits.

Calculates how much of the note's token stream is covered by extracted entity
spans, enabling MVP coverage auditing for the NLP workbench.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.services.clinical_ontology_mapper import TokenSpan, get_ontology_mapper


@dataclass
class CoverageStats:
    """Coverage statistics for extracted entities over tokenized text."""

    total_tokens: int
    covered_tokens: int
    coverage_pct: float
    uncovered_tokens: list[TokenSpan] = field(default_factory=list)


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
