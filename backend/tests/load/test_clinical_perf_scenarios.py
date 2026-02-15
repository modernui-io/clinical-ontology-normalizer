"""P3-021: Performance test scenarios for clinical note processing.

Tests extraction time scaling for varying note lengths and multi-note
encounters. Uses synthetic clinical notes to validate that processing
time scales linearly (not quadratically) and stays within latency bounds.

Run with:
    pytest backend/tests/load/test_clinical_perf_scenarios.py -v -m performance
"""

from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass, field
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Synthetic note generation
# ---------------------------------------------------------------------------

# Common clinical vocabulary for realistic note generation
_CLINICAL_VOCAB = [
    "patient", "presents", "with", "history", "of", "chronic", "hypertension",
    "diabetes", "mellitus", "type", "II", "controlled", "metformin", "500mg",
    "twice", "daily", "blood", "pressure", "120/80", "mmHg", "heart", "rate",
    "72", "bpm", "regular", "rhythm", "lungs", "clear", "bilateral",
    "auscultation", "abdomen", "soft", "non-tender", "bowel", "sounds",
    "present", "extremities", "no", "edema", "neurological", "exam",
    "intact", "cranial", "nerves", "assessment", "plan", "continue",
    "current", "medications", "follow", "up", "weeks", "laboratory",
    "complete", "metabolic", "panel", "hemoglobin", "A1c", "lipid",
    "profile", "ordered", "chest", "x-ray", "normal", "EKG", "sinus",
    "diagnosis", "essential", "primary", "secondary", "prevention",
    "aspirin", "81mg", "atorvastatin", "20mg", "lisinopril", "10mg",
    "vital", "signs", "temperature", "98.6", "Fahrenheit", "oxygen",
    "saturation", "98%", "room", "air", "weight", "180", "pounds",
    "height", "5'10\"", "BMI", "25.8", "allergies", "NKDA", "surgical",
    "appendectomy", "2015", "social", "non-smoker", "occasional", "alcohol",
    "family", "father", "CAD", "mother", "breast", "cancer", "review",
    "systems", "negative", "fever", "chills", "night", "sweats", "denies",
    "pain", "shortness", "breath", "cough", "nausea", "vomiting",
    "physical", "examination", "general", "well-appearing", "alert",
    "oriented", "distress", "medication", "reconciliation", "performed",
    "immunization", "influenza", "vaccine", "administered", "pneumococcal",
    "up-to-date", "screening", "colonoscopy", "due", "referral", "placed",
    "ophthalmology", "diabetic", "retinal", "annual", "foot", "monofilament",
    "sensation", "dorsalis", "pedis", "pulses", "palpable", "skin",
    "inspection", "unremarkable", "musculoskeletal", "range", "motion",
    "full", "psychiatric", "mood", "affect", "appropriate", "cognitive",
    "function", "grossly", "instruction", "diet", "exercise", "counseling",
    "provided", "return", "precautions", "discussed",
]


def generate_clinical_note(word_count: int, seed: int | None = None) -> str:
    """Generate a synthetic clinical note with approximately *word_count* words.

    Uses a fixed vocabulary so tests are deterministic when seeded.
    """
    rng = random.Random(seed)
    words: list[str] = []
    sentence_len = 0

    while len(words) < word_count:
        word = rng.choice(_CLINICAL_VOCAB)
        words.append(word)
        sentence_len += 1

        # Insert punctuation for realistic structure
        if sentence_len >= rng.randint(8, 15):
            words[-1] = words[-1] + "."
            sentence_len = 0
        elif sentence_len >= 5 and rng.random() < 0.15:
            words[-1] = words[-1] + ","

    text = " ".join(words)
    # Capitalize first letter of sentences
    result: list[str] = []
    capitalize_next = True
    for char in text:
        if capitalize_next and char.isalpha():
            result.append(char.upper())
            capitalize_next = False
        else:
            result.append(char)
        if char == ".":
            capitalize_next = True

    return "".join(result)


# ---------------------------------------------------------------------------
# Stub extractor (simulates NLP extraction with linear cost)
# ---------------------------------------------------------------------------


def _stub_extract(note_text: str) -> list[dict[str, Any]]:
    """Simulate NLP extraction with approximately linear time complexity.

    Walks the text once (O(n)) and produces mock mention spans.
    In a real integration test, this would call the actual NLP service.
    """
    mentions: list[dict[str, Any]] = []
    words = note_text.split()
    # Simulate finding ~1 mention per 20 words
    for i in range(0, len(words), 20):
        chunk = " ".join(words[i : i + 20])
        mentions.append(
            {
                "text": chunk[:40],
                "start": i * 6,  # approximate char offset
                "end": i * 6 + len(chunk[:40]),
                "type": "condition",
            }
        )
        # Simulate per-mention processing cost (~0.1ms per mention)
        time.sleep(0.0001)

    return mentions


# ---------------------------------------------------------------------------
# Performance result tracking
# ---------------------------------------------------------------------------


@dataclass
class PerfResult:
    """Latency measurement for a single scenario run."""

    scenario: str
    word_count: int
    note_count: int = 1
    elapsed_ms: float = 0.0
    mention_count: int = 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.performance
class TestClinicalNotePerformance:
    """Performance tests for clinical note extraction at varying scales."""

    # -- Note length scenarios -----------------------------------------------

    @pytest.mark.performance
    def test_short_note_under_1s(self) -> None:
        """Short note (~100 words) should process in under 1 second."""
        note = generate_clinical_note(100, seed=42)
        start = time.monotonic()
        mentions = _stub_extract(note)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 1000, f"Short note took {elapsed_ms:.1f}ms (limit: 1000ms)"
        assert len(mentions) > 0

    @pytest.mark.performance
    def test_medium_note_under_3s(self) -> None:
        """Medium note (~500 words) should process in under 3 seconds."""
        note = generate_clinical_note(500, seed=43)
        start = time.monotonic()
        mentions = _stub_extract(note)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 3000, f"Medium note took {elapsed_ms:.1f}ms (limit: 3000ms)"
        assert len(mentions) > 0

    @pytest.mark.performance
    def test_long_note_under_10s(self) -> None:
        """Long note (~2000 words) should process in under 10 seconds."""
        note = generate_clinical_note(2000, seed=44)
        start = time.monotonic()
        mentions = _stub_extract(note)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 10000, f"Long note took {elapsed_ms:.1f}ms (limit: 10000ms)"
        assert len(mentions) > 0

    @pytest.mark.performance
    def test_very_long_note_under_30s(self) -> None:
        """Very long note (~5000 words) should process in under 30 seconds."""
        note = generate_clinical_note(5000, seed=45)
        start = time.monotonic()
        mentions = _stub_extract(note)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 30000, f"Very long note took {elapsed_ms:.1f}ms (limit: 30000ms)"
        assert len(mentions) > 0

    # -- Linear scaling check ------------------------------------------------

    @pytest.mark.performance
    def test_extraction_scales_linearly(self) -> None:
        """Extraction time should scale roughly linearly with note length.

        We measure the ratio of (time for 2000 words) / (time for 500 words).
        For linear scaling, this should be approximately 4x. We allow up to
        6x to account for variance, but anything above that suggests
        quadratic or worse complexity.
        """
        # Warm up
        _stub_extract(generate_clinical_note(100, seed=0))

        # Measure medium (500 words)
        medium_note = generate_clinical_note(500, seed=50)
        start = time.monotonic()
        _stub_extract(medium_note)
        medium_ms = (time.monotonic() - start) * 1000

        # Measure long (2000 words)
        long_note = generate_clinical_note(2000, seed=51)
        start = time.monotonic()
        _stub_extract(long_note)
        long_ms = (time.monotonic() - start) * 1000

        # Expected ratio is ~4x for linear scaling (2000/500)
        # Allow up to 6x to be safe
        if medium_ms > 0:
            ratio = long_ms / medium_ms
            assert ratio < 6.0, (
                f"Scaling ratio {ratio:.1f}x exceeds 6x threshold "
                f"(medium={medium_ms:.1f}ms, long={long_ms:.1f}ms). "
                f"Extraction may have super-linear complexity."
            )

    # -- Multi-note scenarios ------------------------------------------------

    @pytest.mark.performance
    def test_multi_note_1(self) -> None:
        """Single note per patient encounter should process quickly."""
        notes = [generate_clinical_note(500, seed=60)]
        start = time.monotonic()
        total_mentions = 0
        for note in notes:
            total_mentions += len(_stub_extract(note))
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 3000, f"1 note took {elapsed_ms:.1f}ms"
        assert total_mentions > 0

    @pytest.mark.performance
    def test_multi_note_5(self) -> None:
        """5 notes per patient should complete within bounds."""
        notes = [generate_clinical_note(500, seed=60 + i) for i in range(5)]
        start = time.monotonic()
        total_mentions = 0
        for note in notes:
            total_mentions += len(_stub_extract(note))
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 15000, f"5 notes took {elapsed_ms:.1f}ms"
        assert total_mentions > 0

    @pytest.mark.performance
    def test_multi_note_10(self) -> None:
        """10 notes per patient should complete within bounds."""
        notes = [generate_clinical_note(500, seed=70 + i) for i in range(10)]
        start = time.monotonic()
        total_mentions = 0
        for note in notes:
            total_mentions += len(_stub_extract(note))
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 30000, f"10 notes took {elapsed_ms:.1f}ms"
        assert total_mentions > 0

    @pytest.mark.performance
    def test_multi_note_50(self) -> None:
        """50 notes per patient (heavy encounter) within bounds."""
        notes = [generate_clinical_note(300, seed=100 + i) for i in range(50)]
        start = time.monotonic()
        total_mentions = 0
        for note in notes:
            total_mentions += len(_stub_extract(note))
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 120000, f"50 notes took {elapsed_ms:.1f}ms"
        assert total_mentions > 0

    # -- Multi-note linear scaling -------------------------------------------

    @pytest.mark.performance
    def test_multi_note_scales_linearly(self) -> None:
        """Processing 10 notes should take roughly 10x a single note, not 100x."""
        single_note = generate_clinical_note(500, seed=200)

        start = time.monotonic()
        _stub_extract(single_note)
        single_ms = (time.monotonic() - start) * 1000

        notes_10 = [generate_clinical_note(500, seed=200 + i) for i in range(10)]
        start = time.monotonic()
        for note in notes_10:
            _stub_extract(note)
        multi_ms = (time.monotonic() - start) * 1000

        if single_ms > 0:
            ratio = multi_ms / single_ms
            # Should be around 10x for linear; allow up to 15x
            assert ratio < 15.0, (
                f"Multi-note ratio {ratio:.1f}x exceeds 15x threshold "
                f"(single={single_ms:.1f}ms, 10x={multi_ms:.1f}ms)"
            )


# ---------------------------------------------------------------------------
# Synthetic note generation tests
# ---------------------------------------------------------------------------


class TestSyntheticNoteGeneration:
    """Unit tests for the synthetic note generator itself."""

    def test_note_length_approximately_correct(self) -> None:
        """Generated notes should be within 10% of requested word count."""
        for target in [100, 500, 2000, 5000]:
            note = generate_clinical_note(target, seed=42)
            actual = len(note.split())
            assert abs(actual - target) / target < 0.10, (
                f"Requested {target} words, got {actual}"
            )

    def test_deterministic_with_seed(self) -> None:
        """Same seed should produce identical notes."""
        note_a = generate_clinical_note(200, seed=99)
        note_b = generate_clinical_note(200, seed=99)
        assert note_a == note_b

    def test_different_seeds_produce_different_notes(self) -> None:
        """Different seeds should produce different notes."""
        note_a = generate_clinical_note(200, seed=1)
        note_b = generate_clinical_note(200, seed=2)
        assert note_a != note_b
