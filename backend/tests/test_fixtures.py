"""Tests for synthetic clinical note fixtures."""

import json
from pathlib import Path

import pytest

FIXTURES_PATH = Path(__file__).parent.parent / "fixtures" / "synthetic_notes.json"


@pytest.fixture
def fixtures_data() -> dict:
    """Load fixtures data."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


def test_fixtures_file_exists() -> None:
    """Verify fixtures file exists."""
    assert FIXTURES_PATH.exists(), f"Fixtures file not found at {FIXTURES_PATH}"


def test_fixtures_has_10_notes(fixtures_data: dict) -> None:
    """Verify we have exactly 10 synthetic notes."""
    assert len(fixtures_data["notes"]) == 10


def test_each_note_has_required_fields(fixtures_data: dict) -> None:
    """Verify each note has required fields."""
    required_fields = {"id", "patient_id", "note_type", "text", "expected_mentions"}
    for note in fixtures_data["notes"]:
        missing = required_fields - set(note.keys())
        assert not missing, f"Note {note.get('id', 'unknown')} missing fields: {missing}"


def test_each_mention_has_required_fields(fixtures_data: dict) -> None:
    """Verify each expected mention has required fields."""
    required_fields = {"text", "assertion", "temporality", "experiencer", "expected_domain"}
    for note in fixtures_data["notes"]:
        for mention in note["expected_mentions"]:
            missing = required_fields - set(mention.keys())
            assert not missing, f"Mention in {note['id']} missing fields: {missing}"


def test_assertion_values_valid(fixtures_data: dict) -> None:
    """Verify assertion values are valid."""
    valid_assertions = {"present", "absent", "possible"}
    for note in fixtures_data["notes"]:
        for mention in note["expected_mentions"]:
            assert mention["assertion"] in valid_assertions, (
                f"Invalid assertion '{mention['assertion']}' in {note['id']}"
            )


def test_temporality_values_valid(fixtures_data: dict) -> None:
    """Verify temporality values are valid."""
    valid_temporality = {"current", "past", "future"}
    for note in fixtures_data["notes"]:
        for mention in note["expected_mentions"]:
            assert mention["temporality"] in valid_temporality, (
                f"Invalid temporality '{mention['temporality']}' in {note['id']}"
            )


def test_experiencer_values_valid(fixtures_data: dict) -> None:
    """Verify experiencer values are valid."""
    valid_experiencers = {"patient", "family", "other"}
    for note in fixtures_data["notes"]:
        for mention in note["expected_mentions"]:
            assert mention["experiencer"] in valid_experiencers, (
                f"Invalid experiencer '{mention['experiencer']}' in {note['id']}"
            )


def test_domain_values_valid(fixtures_data: dict) -> None:
    """Verify expected_domain values are valid."""
    valid_domains = {"condition", "drug", "measurement", "procedure", "observation"}
    for note in fixtures_data["notes"]:
        for mention in note["expected_mentions"]:
            assert mention["expected_domain"] in valid_domains, (
                f"Invalid domain '{mention['expected_domain']}' in {note['id']}"
            )


def test_negation_coverage(fixtures_data: dict) -> None:
    """Verify we have negation examples (assertion=absent)."""
    negated_mentions = [
        m
        for note in fixtures_data["notes"]
        for m in note["expected_mentions"]
        if m["assertion"] == "absent"
    ]
    assert len(negated_mentions) >= 5, "Need at least 5 negation examples"


def test_temporality_past_coverage(fixtures_data: dict) -> None:
    """Verify we have past temporality examples."""
    past_mentions = [
        m
        for note in fixtures_data["notes"]
        for m in note["expected_mentions"]
        if m["temporality"] == "past"
    ]
    assert len(past_mentions) >= 3, "Need at least 3 past temporality examples"


def test_family_experiencer_coverage(fixtures_data: dict) -> None:
    """Verify we have family experiencer examples."""
    family_mentions = [
        m
        for note in fixtures_data["notes"]
        for m in note["expected_mentions"]
        if m["experiencer"] == "family"
    ]
    assert len(family_mentions) >= 2, "Need at least 2 family experiencer examples"


def test_uncertainty_coverage(fixtures_data: dict) -> None:
    """Verify we have uncertainty examples (assertion=possible)."""
    uncertain_mentions = [
        m
        for note in fixtures_data["notes"]
        for m in note["expected_mentions"]
        if m["assertion"] == "possible"
    ]
    assert len(uncertain_mentions) >= 2, "Need at least 2 uncertainty examples"


def test_medication_coverage(fixtures_data: dict) -> None:
    """Verify we have medication examples."""
    drug_mentions = [
        m
        for note in fixtures_data["notes"]
        for m in note["expected_mentions"]
        if m["expected_domain"] == "drug"
    ]
    assert len(drug_mentions) >= 4, "Need at least 4 medication examples"


def test_measurement_coverage(fixtures_data: dict) -> None:
    """Verify we have measurement examples."""
    measurement_mentions = [
        m
        for note in fixtures_data["notes"]
        for m in note["expected_mentions"]
        if m["expected_domain"] == "measurement"
    ]
    assert len(measurement_mentions) >= 4, "Need at least 4 measurement examples"
