"""
Canonical NLP shared resources.

Phase 2 canonicalization — single source of truth for negation triggers
and section headers used across NLP service variants.

The authoritative definitions live in nlp_entity/nlp_entity_normalizers.py.
This module re-exports them so that future code can import from a single,
stable location without pulling in the full nlp_entity package.

Usage:
    from app.services.nlp_shared import (
        CANONICAL_NEGATION_TRIGGERS,
        CANONICAL_UNCERTAINTY_TRIGGERS,
        CANONICAL_FAMILY_HISTORY_TRIGGERS,
        CANONICAL_SECTION_HEADERS,
    )
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canonical negation triggers (regex patterns, case-insensitive)
#
# Authoritative copy: app.services.nlp_entity.nlp_entity_normalizers.NEGATION_TRIGGERS
# Any additions/removals should be made there first, then mirrored here.
# ---------------------------------------------------------------------------
CANONICAL_NEGATION_TRIGGERS: list[str] = [
    r"\bno\b",
    r"\bnot\b",
    r"\bdenies\b",
    r"\bdenied\b",
    r"\bwithout\b",
    r"\babsence\s+of\b",
    r"\bnegative\s+for\b",
    r"\bruled\s+out\b",
    r"\bunlikely\b",
    r"\bno\s+evidence\s+of\b",
    r"\bnever\b",
    r"\bnone\b",
    r"\bfree\s+of\b",
    r"\brules\s+out\b",
    r"\bdeclines\b",
    r"\bdoes\s+not\s+have\b",
    r"\bnon-?\b",
    r"\blow\s+suspicion\s+for\b",
    r"\bno\s+suspicion\s+for\b",
    r"\blow\s+concern\s+for\b",
]

# ---------------------------------------------------------------------------
# Canonical uncertainty triggers (regex patterns, case-insensitive)
# ---------------------------------------------------------------------------
CANONICAL_UNCERTAINTY_TRIGGERS: list[str] = [
    r"\bcannot\s+rule\s+out\b",
    r"\bcan\'?t\s+rule\s+out\b",
    r"\bpossible\b",
    r"\bprobable\b",
    r"\bsuspected?\b",
    r"\bquestionable\b",
    r"\bmay\s+have\b",
    r"\bmight\s+have\b",
    r"\bcould\s+be\b",
    r"\bappears?\s+to\s+be\b",
    r"\blikely\b",
    r"\bconcern\s+for\b",
    r"\brule\s+out\b",
    r"\b(?:r/o|ro)\b",
]

# ---------------------------------------------------------------------------
# Canonical family-history triggers (regex patterns, case-insensitive)
# ---------------------------------------------------------------------------
CANONICAL_FAMILY_HISTORY_TRIGGERS: list[str] = [
    r"\bfamily\s+history\b",
    r"\bfamily\s+hx\b",
    r"\bfhx\b",
    r"\bmother\s+(?:has|had|with|diagnosed)\b",
    r"\bfather\s+(?:has|had|with|diagnosed)\b",
    r"\bsibling\s+(?:has|had|with|diagnosed)\b",
    r"\bbrother\s+(?:has|had|with|diagnosed)\b",
    r"\bsister\s+(?:has|had|with|diagnosed)\b",
    r"\bparent\s+(?:has|had|with|diagnosed)\b",
]

# ---------------------------------------------------------------------------
# Canonical section header patterns
#
# Maps ClinicalSection enum value -> list of regex patterns.
# Authoritative copy: app.services.nlp_entity.nlp_entity_normalizers.SECTION_PATTERNS
# ---------------------------------------------------------------------------
CANONICAL_SECTION_HEADERS: dict[str, list[str]] = {
    "chief_complaint": [
        r"(?:chief\s+complaint|cc|presenting\s+complaint)[\s:]+",
    ],
    "hpi": [
        r"(?:history\s+of\s+present(?:ing)?\s+illness|hpi|present\s+illness)[\s:]+",
    ],
    "ros": [
        r"(?:review\s+of\s+systems?|ros)[\s:]+",
    ],
    "pmh": [
        r"(?:past\s+medical\s+history|pmh|medical\s+history)[\s:]+",
    ],
    "psh": [
        r"(?:past\s+surgical\s+history|psh|surgical\s+history)[\s:]+",
    ],
    "fhx": [
        r"(?:family\s+history|fh|fhx)[\s:]+",
    ],
    "shx": [
        r"(?:social\s+history|sh|shx)[\s:]+",
    ],
    "medications": [
        r"(?:medications?|meds|current\s+medications?|home\s+medications?)[\s:]+",
    ],
    "allergies": [
        r"(?:allergies|drug\s+allergies|medication\s+allergies|nkda)[\s:]+",
    ],
    "vitals": [
        r"(?:vital\s+signs?|vitals)[\s:]+",
    ],
    "physical_exam": [
        r"(?:physical\s+exam(?:ination)?|pe|exam)[\s:]+",
    ],
    "labs": [
        r"(?:lab(?:oratory)?\s+(?:results?|data|values?)|labs)[\s:]+",
    ],
    "imaging": [
        r"(?:imaging|radiology|x-?ray|ct|mri|ultrasound)[\s:]+",
    ],
    "assessment": [
        r"(?:assessment|impression|diagnosis|diagnoses)[\s:]+",
    ],
    "plan": [
        r"(?:plan|recommendations?|disposition)[\s:]+",
    ],
}
