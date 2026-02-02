"""Tests for NLP coverage gap report."""

from __future__ import annotations

from app.services.clinical_ontology_mapper import get_ontology_mapper
from app.services.nlp_coverage import calculate_coverage_gap


def test_coverage_gap_report_counts_and_samples() -> None:
    text = "hypertension flarf"
    flarf_start = text.index("flarf")
    flarf_end = flarf_start + len("flarf")

    report = calculate_coverage_gap(text, [(flarf_start, flarf_end)], max_gap_tokens=10)

    tokens = get_ontology_mapper().tokenize_text(text)

    assert report.total_tokens == len(tokens)
    assert report.extraction_covered_tokens == 1
    assert report.ontology_entity_tokens == 1
    assert report.overlap_tokens == 0
    assert report.extraction_only_tokens == 1
    assert report.ontology_only_tokens == 1
    assert report.extraction_only_pct == 100.0
    assert report.ontology_only_pct == 100.0
    assert report.overlap_pct == 0.0

    assert report.extraction_only
    assert report.extraction_only[0].text == "flarf"
    assert report.ontology_only
    assert report.ontology_only[0].text == "hypertension"
