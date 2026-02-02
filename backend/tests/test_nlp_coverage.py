"""Tests for NLP extraction coverage utilities."""

from __future__ import annotations

from app.services.clinical_ontology_mapper import get_ontology_mapper
from app.services.nlp_coverage import calculate_token_coverage


def test_token_coverage_counts_tokens() -> None:
    text = "Aspirin 81 mg daily."
    start = text.index("Aspirin")
    end = start + len("Aspirin")

    stats = calculate_token_coverage(
        text,
        [(start, end)],
        include_uncovered_tokens=True,
    )

    tokens = get_ontology_mapper().tokenize_text(text)

    assert stats.total_tokens == len(tokens)
    assert stats.covered_tokens == 1
    assert stats.coverage_pct == round((1 / len(tokens)) * 100, 1)
    assert any(token.text == "81" for token in stats.uncovered_tokens)


def test_token_coverage_merges_overlaps() -> None:
    text = "chest pain"
    span_full = (0, len(text))
    span_partial = (0, len("chest"))

    stats = calculate_token_coverage(text, [span_full, span_partial])
    tokens = get_ontology_mapper().tokenize_text(text)

    assert stats.covered_tokens == len(tokens)
    assert stats.coverage_pct == 100.0


def test_token_coverage_empty_spans() -> None:
    text = "No findings noted."
    stats = calculate_token_coverage(text, [])
    tokens = get_ontology_mapper().tokenize_text(text)

    assert stats.total_tokens == len(tokens)
    assert stats.covered_tokens == 0
    assert stats.coverage_pct == 0.0
