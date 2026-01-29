"""Text normalization and preprocessing for clinical NLP.

This module contains:
- Section detection patterns and logic
- Negation detection patterns and algorithms
- Confidence calculation
- Entity deduplication and merging
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .nlp_entity_core import ExtractedEntity


# ============================================================================
# Enums and Types
# ============================================================================


class EntityType(str, Enum):
    """Types of clinical entities that can be extracted."""

    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    LAB_RESULT = "lab_result"
    VITAL_SIGN = "vital_sign"
    ANATOMICAL_LOCATION = "anatomical_location"
    TEMPORAL = "temporal"
    SYMPTOM = "symptom"
    ALLERGY = "allergy"


class AssertionStatus(str, Enum):
    """Assertion status for extracted entities."""

    PRESENT = "present"
    ABSENT = "absent"
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"
    HYPOTHETICAL = "hypothetical"
    FAMILY_HISTORY = "family_history"


class ClinicalSection(str, Enum):
    """Clinical document sections."""

    CHIEF_COMPLAINT = "chief_complaint"
    HPI = "hpi"
    ROS = "ros"
    PAST_MEDICAL_HISTORY = "pmh"
    PAST_SURGICAL_HISTORY = "psh"
    FAMILY_HISTORY = "fhx"
    SOCIAL_HISTORY = "shx"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    VITAL_SIGNS = "vitals"
    PHYSICAL_EXAM = "physical_exam"
    LABS = "labs"
    IMAGING = "imaging"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    UNKNOWN = "unknown"


class NormalizationVocabulary(str, Enum):
    """Standard vocabularies for entity normalization."""

    SNOMED_CT = "SNOMED-CT"
    RXNORM = "RxNorm"
    LOINC = "LOINC"
    ICD10_CM = "ICD-10-CM"
    ICD10_PCS = "ICD-10-PCS"
    CPT = "CPT"
    NDC = "NDC"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class EntitySpan:
    """Represents a text span in the source document."""

    start: int
    end: int
    text: str


@dataclass
class NormalizedCode:
    """A normalized code from a standard vocabulary."""

    code: str
    display: str
    system: NormalizationVocabulary
    confidence: float = 0.0
    is_preferred: bool = False


@dataclass
class SectionSpan:
    """A detected clinical section in the document."""

    section: ClinicalSection
    start: int
    end: int
    header_text: str | None = None


# ============================================================================
# Section Detection Patterns
# ============================================================================


SECTION_PATTERNS: dict[ClinicalSection, list[str]] = {
    ClinicalSection.CHIEF_COMPLAINT: [
        r"(?:chief\s+complaint|cc|presenting\s+complaint)[\s:]+",
    ],
    ClinicalSection.HPI: [
        r"(?:history\s+of\s+present(?:ing)?\s+illness|hpi|present\s+illness)[\s:]+",
    ],
    ClinicalSection.ROS: [
        r"(?:review\s+of\s+systems?|ros)[\s:]+",
    ],
    ClinicalSection.PAST_MEDICAL_HISTORY: [
        r"(?:past\s+medical\s+history|pmh|medical\s+history)[\s:]+",
    ],
    ClinicalSection.PAST_SURGICAL_HISTORY: [
        r"(?:past\s+surgical\s+history|psh|surgical\s+history)[\s:]+",
    ],
    ClinicalSection.FAMILY_HISTORY: [
        r"(?:family\s+history|fh|fhx)[\s:]+",
    ],
    ClinicalSection.SOCIAL_HISTORY: [
        r"(?:social\s+history|sh|shx)[\s:]+",
    ],
    ClinicalSection.MEDICATIONS: [
        r"(?:medications?|meds|current\s+medications?|home\s+medications?)[\s:]+",
    ],
    ClinicalSection.ALLERGIES: [
        r"(?:allergies|drug\s+allergies|medication\s+allergies|nkda)[\s:]+",
    ],
    ClinicalSection.VITAL_SIGNS: [
        r"(?:vital\s+signs?|vitals)[\s:]+",
    ],
    ClinicalSection.PHYSICAL_EXAM: [
        r"(?:physical\s+exam(?:ination)?|pe|exam)[\s:]+",
    ],
    ClinicalSection.LABS: [
        r"(?:lab(?:oratory)?\s+(?:results?|data|values?)|labs)[\s:]+",
    ],
    ClinicalSection.IMAGING: [
        r"(?:imaging|radiology|x-?ray|ct|mri|ultrasound)[\s:]+",
    ],
    ClinicalSection.ASSESSMENT: [
        r"(?:assessment|impression|diagnosis|diagnoses)[\s:]+",
    ],
    ClinicalSection.PLAN: [
        r"(?:plan|recommendations?|disposition)[\s:]+",
    ],
}


# ============================================================================
# Negation Detection Patterns
# ============================================================================


NEGATION_TRIGGERS = [
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

UNCERTAINTY_TRIGGERS = [
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

FAMILY_HISTORY_TRIGGERS = [
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

# Laterality patterns
LATERALITY_PATTERNS = [
    (r"\bleft\b", "left"),
    (r"\bright\b", "right"),
    (r"\bbilateral\b", "bilateral"),
    (r"\bunilateral\b", "unilateral"),
]


# ============================================================================
# Normalizer Mixin Class
# ============================================================================


class NormalizerMixin:
    """Mixin providing text normalization and preprocessing methods."""

    # These will be populated by _compile_patterns
    _section_regexes: dict[ClinicalSection, list[re.Pattern]]
    _negation_regexes: list[re.Pattern]
    _uncertainty_regexes: list[re.Pattern]
    _family_history_regexes: list[re.Pattern]
    _initialized: bool

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        if self._initialized:
            return

        # Compile section patterns
        self._section_regexes = {}
        for section, patterns in SECTION_PATTERNS.items():
            self._section_regexes[section] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        # Compile negation patterns
        self._negation_regexes = [
            re.compile(p, re.IGNORECASE) for p in NEGATION_TRIGGERS
        ]
        self._uncertainty_regexes = [
            re.compile(p, re.IGNORECASE) for p in UNCERTAINTY_TRIGGERS
        ]
        self._family_history_regexes = [
            re.compile(p, re.IGNORECASE) for p in FAMILY_HISTORY_TRIGGERS
        ]

        self._initialized = True

    def _detect_sections(self, text: str) -> list[SectionSpan]:
        """Detect clinical sections in the document."""
        sections: list[SectionSpan] = []
        text_lower = text.lower()

        for section, patterns in self._section_regexes.items():
            for pattern in patterns:
                for match in pattern.finditer(text_lower):
                    sections.append(
                        SectionSpan(
                            section=section,
                            start=match.start(),
                            end=len(text),  # Will be adjusted
                            header_text=match.group(0).strip(),
                        )
                    )

        # Sort by start position and adjust end positions
        sections.sort(key=lambda s: s.start)
        for i, section in enumerate(sections):
            if i < len(sections) - 1:
                section.end = sections[i + 1].start

        return sections

    def _get_section_at_offset(
        self, offset: int, sections: list[SectionSpan]
    ) -> ClinicalSection:
        """Get the section at a given offset."""
        for section in reversed(sections):
            if section.start <= offset < section.end:
                return section.section
        return ClinicalSection.UNKNOWN

    def _apply_negation_detection(
        self, text: str, entities: list["ExtractedEntity"]
    ) -> list["ExtractedEntity"]:
        """Apply negation detection to entities using NegEx-style algorithm."""
        text_lower = text.lower()

        for entity in entities:
            # Get preceding context (50 chars before entity)
            context_start = max(0, entity.span.start - 50)
            preceding_context = text_lower[context_start : entity.span.start]

            # Respect section/paragraph boundaries - don't let negation cross double newlines
            # This prevents "No headache" from negating entities in subsequent sections
            if "\n\n" in preceding_context:
                # Only use context after the last section boundary
                last_boundary = preceding_context.rfind("\n\n")
                preceding_context = preceding_context[last_boundary + 2:]

            # Also truncate at single newline for list items (- item)
            if "\n-" in preceding_context or "\n\u2022" in preceding_context:
                last_newline = max(preceding_context.rfind("\n-"), preceding_context.rfind("\n\u2022"))
                if last_newline >= 0:
                    preceding_context = preceding_context[last_newline + 1:]

            # For lab results, vitals, and procedures, truncate at any newline
            # This prevents "no ischemic changes" from negating lab values/procedures on the next line
            if entity.entity_type in (EntityType.LAB_RESULT, EntityType.VITAL_SIGN, EntityType.PROCEDURE):
                if "\n" in preceding_context:
                    last_newline = preceding_context.rfind("\n")
                    preceding_context = preceding_context[last_newline + 1:]

            # Check for family history context
            for pattern in self._family_history_regexes:
                if pattern.search(preceding_context):
                    entity.assertion = AssertionStatus.FAMILY_HISTORY
                    break

            if entity.assertion == AssertionStatus.FAMILY_HISTORY:
                continue

            # Check for uncertainty triggers
            for pattern in self._uncertainty_regexes:
                match = pattern.search(preceding_context)
                if match:
                    entity.assertion = AssertionStatus.POSSIBLE
                    entity.negation_trigger = match.group(0)
                    break

            if entity.assertion == AssertionStatus.POSSIBLE:
                continue

            # Check for negation triggers
            for pattern in self._negation_regexes:
                match = pattern.search(preceding_context)
                if match:
                    entity.assertion = AssertionStatus.ABSENT
                    entity.negation_trigger = match.group(0)
                    entity.negation_scope_start = context_start + match.start()
                    entity.negation_scope_end = entity.span.end
                    break

        return entities

    def _calculate_confidence(
        self,
        matched_text: str,
        normalized_text: str,
        section: ClinicalSection,
        entity_type: EntityType,
    ) -> float:
        """Calculate confidence score for an extraction."""
        base_confidence = 0.7

        # Bonus for longer matches (more specific)
        length_bonus = min(0.1, len(matched_text) / 100)
        base_confidence += length_bonus

        # Section-specific bonuses
        section_bonuses = {
            (EntityType.DIAGNOSIS, ClinicalSection.ASSESSMENT): 0.1,
            (EntityType.DIAGNOSIS, ClinicalSection.PAST_MEDICAL_HISTORY): 0.1,
            (EntityType.MEDICATION, ClinicalSection.MEDICATIONS): 0.1,
            (EntityType.SYMPTOM, ClinicalSection.HPI): 0.1,
            (EntityType.SYMPTOM, ClinicalSection.ROS): 0.1,
            (EntityType.PROCEDURE, ClinicalSection.PAST_SURGICAL_HISTORY): 0.1,
            (EntityType.VITAL_SIGN, ClinicalSection.VITAL_SIGNS): 0.1,
            (EntityType.LAB_RESULT, ClinicalSection.LABS): 0.1,
        }

        bonus = section_bonuses.get((entity_type, section), 0)
        base_confidence += bonus

        return min(1.0, base_confidence)

    def _deduplicate_entities(
        self, entities: list["ExtractedEntity"]
    ) -> list["ExtractedEntity"]:
        """Remove duplicate entities based on span overlap.

        Prefers longer (more specific) matches over shorter ones.
        Among matches of same length, prefers diagnoses/medications/procedures
        over temporal/anatomical entities, then higher confidence.
        """
        if not entities:
            return entities

        # Entity type priority: diagnoses/meds/procedures > symptoms > labs/vitals > others
        type_priority = {
            EntityType.DIAGNOSIS: 0,
            EntityType.MEDICATION: 0,
            EntityType.PROCEDURE: 0,
            EntityType.SYMPTOM: 1,
            EntityType.LAB_RESULT: 2,
            EntityType.VITAL_SIGN: 2,
            EntityType.ALLERGY: 3,
            EntityType.ANATOMICAL_LOCATION: 4,
            EntityType.TEMPORAL: 5,
        }

        # Sort by: start position, then span length (descending, prefer longer),
        # then entity type priority, then confidence (descending)
        entities.sort(key=lambda e: (
            e.span.start,
            -(e.span.end - e.span.start),  # Longer spans first
            type_priority.get(e.entity_type, 10),  # Important types first
            -e.confidence
        ))

        deduplicated: list["ExtractedEntity"] = []
        for entity in entities:
            # Check for overlap with existing entities
            overlaps = False
            for existing in deduplicated:
                if (
                    entity.span.start < existing.span.end
                    and entity.span.end > existing.span.start
                ):
                    overlaps = True
                    break

            if not overlaps:
                deduplicated.append(entity)

        return deduplicated

    def _merge_entities(
        self,
        rule_entities: list["ExtractedEntity"],
        ml_entities: list["ExtractedEntity"],
    ) -> list["ExtractedEntity"]:
        """Merge entities from rule-based and ML extractions."""
        # Simple merge: prefer ML entities when there's overlap
        merged = list(ml_entities)

        for rule_entity in rule_entities:
            overlaps = False
            for ml_entity in ml_entities:
                if (
                    rule_entity.span.start < ml_entity.span.end
                    and rule_entity.span.end > ml_entity.span.start
                ):
                    overlaps = True
                    break

            if not overlaps:
                merged.append(rule_entity)

        return merged
