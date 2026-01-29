"""Clinical note section parser for section-aware NLP extraction.

Parses clinical notes to identify section boundaries and provides
section-domain affinity mapping for improved extraction accuracy.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class ClinicalSection(str, Enum):
    """Canonical clinical note section names."""

    # Subjective sections
    CHIEF_COMPLAINT = "Chief Complaint"
    HPI = "History of Present Illness"
    PAST_MEDICAL_HISTORY = "Past Medical History"
    PAST_SURGICAL_HISTORY = "Past Surgical History"
    FAMILY_HISTORY = "Family History"
    SOCIAL_HISTORY = "Social History"
    REVIEW_OF_SYSTEMS = "Review of Systems"
    ALLERGIES = "Allergies"
    MEDICATIONS = "Medications"
    HOME_MEDICATIONS = "Home Medications"

    # Objective sections
    VITAL_SIGNS = "Vital Signs"
    PHYSICAL_EXAM = "Physical Exam"
    LABS = "Labs"
    IMAGING = "Imaging"
    EKG = "EKG"
    STUDIES = "Studies"

    # Assessment sections
    ASSESSMENT = "Assessment"
    ASSESSMENT_PLAN = "Assessment and Plan"
    DIAGNOSIS = "Diagnosis"
    IMPRESSION = "Impression"

    # Plan sections
    PLAN = "Plan"
    HOSPITAL_COURSE = "Hospital Course"
    PROCEDURES = "Procedures"

    # Discharge sections
    DISCHARGE_DIAGNOSIS = "Discharge Diagnosis"
    DISCHARGE_MEDICATIONS = "Discharge Medications"
    DISCHARGE_INSTRUCTIONS = "Discharge Instructions"
    FOLLOW_UP = "Follow-up"

    # Other
    UNKNOWN = "Unknown"


@dataclass
class SectionSpan:
    """Represents a section's span in a clinical note."""

    section: ClinicalSection
    start: int
    end: int
    header_text: str  # The actual header text found


@dataclass
class SectionParser:
    """Parser for clinical note sections.

    Identifies section boundaries in clinical notes and provides
    efficient O(1) section lookup for any character offset.

    Usage:
        parser = SectionParser()
        sections = parser.parse(note_text)
        section = parser.get_section_at(note_text, offset)
    """

    # Section header patterns mapped to canonical sections
    # Order matters - more specific patterns should come first
    # All patterns use word boundary \b and require : or newline after header
    SECTION_PATTERNS: ClassVar[list[tuple[str, ClinicalSection]]] = [
        # Chief Complaint variations
        (r"\b(?:CHIEF\s+COMPLAINT|CC|C/C|REASON\s+FOR\s+(?:VISIT|ADMISSION))\s*:", ClinicalSection.CHIEF_COMPLAINT),

        # HPI variations
        (r"\b(?:HISTORY\s+OF\s+(?:THE\s+)?PRESENT(?:ING)?\s+ILLNESS|HPI|H\.P\.I\.)\s*:", ClinicalSection.HPI),

        # Past Medical History variations
        (r"\b(?:PAST\s+MEDICAL\s+HISTORY|PMHx?|P\.M\.H\.|MEDICAL\s+HISTORY)\s*:", ClinicalSection.PAST_MEDICAL_HISTORY),

        # Past Surgical History
        (r"\b(?:PAST\s+SURGICAL\s+HISTORY|PSHx?|SURGICAL\s+HISTORY)\s*:", ClinicalSection.PAST_SURGICAL_HISTORY),

        # Family History variations
        (r"\b(?:FAMILY\s+HISTORY|FHx?|F\.H\.)\s*:", ClinicalSection.FAMILY_HISTORY),

        # Social History variations (SH requires : immediately after)
        (r"\b(?:SOCIAL\s+HISTORY|SHx|S\.H\.)\s*:", ClinicalSection.SOCIAL_HISTORY),

        # Review of Systems variations
        (r"\b(?:REVIEW\s+OF\s+SYSTEMS|ROS|R\.O\.S\.)\s*:", ClinicalSection.REVIEW_OF_SYSTEMS),

        # Allergies variations
        (r"\b(?:ALLERGIES|DRUG\s+ALLERGIES|KNOWN\s+ALLERGIES)\s*:", ClinicalSection.ALLERGIES),

        # Medications variations (before discharge meds)
        (r"\b(?:DISCHARGE\s+MEDICATIONS?|D/C\s+MEDS?)\s*:", ClinicalSection.DISCHARGE_MEDICATIONS),
        (r"\b(?:HOME\s+MEDICATIONS?|OUTPATIENT\s+MEDICATIONS?)\s*:", ClinicalSection.HOME_MEDICATIONS),
        (r"\b(?:MEDICATIONS?|CURRENT\s+MEDICATIONS?)\s*:", ClinicalSection.MEDICATIONS),

        # Vital Signs variations
        (r"\b(?:VITAL\s+SIGNS?|VITALS?)\s*:", ClinicalSection.VITAL_SIGNS),

        # Physical Exam variations (PE requires : immediately after)
        (r"\b(?:PHYSICAL\s+EXAM(?:INATION)?|P\.E\.)\s*:", ClinicalSection.PHYSICAL_EXAM),

        # Labs variations
        (r"\b(?:LAB(?:ORATORY)?\s*(?:RESULTS?|DATA|VALUES?)?|LABS)\s*:", ClinicalSection.LABS),

        # Imaging variations (require full words, not abbreviations that could match elsewhere)
        (r"\b(?:IMAGING|RADIOLOGY)\s*:", ClinicalSection.IMAGING),

        # EKG/ECG variations
        (r"\b(?:EKG|ECG|ELECTROCARDIOGRAM)\s*:", ClinicalSection.EKG),

        # Studies
        (r"\b(?:STUDIES|DIAGNOSTIC\s+STUDIES)\s*:", ClinicalSection.STUDIES),

        # Assessment/Plan combined (check before individual)
        (r"\b(?:ASSESSMENT\s*(?:AND|&|/)\s*PLAN|A\s*/\s*P)\s*:", ClinicalSection.ASSESSMENT_PLAN),

        # Assessment variations
        (r"\b(?:ASSESSMENT|IMPRESSION|CLINICAL\s+IMPRESSION)\s*:", ClinicalSection.ASSESSMENT),

        # Plan variations
        (r"\b(?:PLAN|TREATMENT\s+PLAN|MANAGEMENT)\s*:", ClinicalSection.PLAN),

        # Diagnosis variations
        (r"\b(?:DIAGNOSIS|DIAGNOSES|PROBLEM\s+LIST)\s*:", ClinicalSection.DIAGNOSIS),
        (r"\b(?:DISCHARGE\s+DIAGNOSIS|DISCHARGE\s+DX|FINAL\s+DIAGNOSIS)\s*:", ClinicalSection.DISCHARGE_DIAGNOSIS),
        (r"\b(?:ADMISSION\s+DIAGNOSIS|ADMITTING\s+DIAGNOSIS)\s*:", ClinicalSection.DIAGNOSIS),

        # Hospital Course
        (r"\b(?:HOSPITAL\s+COURSE|CLINICAL\s+COURSE)\s*:", ClinicalSection.HOSPITAL_COURSE),

        # Procedures
        (r"\b(?:PROCEDURES?|OPERATIONS?|INTERVENTIONS?)\s*:", ClinicalSection.PROCEDURES),

        # Follow-up
        (r"\b(?:FOLLOW[\s-]?UP|F/U|DISPOSITION)\s*:", ClinicalSection.FOLLOW_UP),

        # Discharge Instructions
        (r"\b(?:DISCHARGE\s+INSTRUCTIONS?|PATIENT\s+INSTRUCTIONS?)\s*:", ClinicalSection.DISCHARGE_INSTRUCTIONS),
    ]

    # Domain affinity for each section (which domains are expected)
    # Higher values = stronger affinity
    SECTION_DOMAIN_AFFINITY: ClassVar[dict[ClinicalSection, dict[str, float]]] = {
        ClinicalSection.CHIEF_COMPLAINT: {
            "Condition": 0.9,
            "Observation": 0.8,
        },
        ClinicalSection.HPI: {
            "Condition": 0.9,
            "Observation": 0.7,
            "Drug": 0.5,
        },
        ClinicalSection.PAST_MEDICAL_HISTORY: {
            "Condition": 1.0,
            "Procedure": 0.6,
        },
        ClinicalSection.PAST_SURGICAL_HISTORY: {
            "Procedure": 1.0,
            "Condition": 0.4,
        },
        ClinicalSection.FAMILY_HISTORY: {
            "Condition": 1.0,
        },
        ClinicalSection.SOCIAL_HISTORY: {
            "Observation": 0.8,
            "Condition": 0.5,
        },
        ClinicalSection.ALLERGIES: {
            "Drug": 1.0,
            "Observation": 0.6,
        },
        ClinicalSection.MEDICATIONS: {
            "Drug": 1.0,
        },
        ClinicalSection.HOME_MEDICATIONS: {
            "Drug": 1.0,
        },
        ClinicalSection.DISCHARGE_MEDICATIONS: {
            "Drug": 1.0,
        },
        ClinicalSection.VITAL_SIGNS: {
            "Measurement": 1.0,
            "Observation": 0.7,
        },
        ClinicalSection.PHYSICAL_EXAM: {
            "Observation": 1.0,
            "Condition": 0.6,
            "Measurement": 0.5,
        },
        ClinicalSection.LABS: {
            "Measurement": 1.0,
        },
        ClinicalSection.IMAGING: {
            "Procedure": 0.8,
            "Observation": 0.7,
            "Condition": 0.5,
        },
        ClinicalSection.EKG: {
            "Procedure": 0.7,
            "Observation": 0.8,
            "Condition": 0.5,
        },
        ClinicalSection.ASSESSMENT: {
            "Condition": 1.0,
            "Observation": 0.6,
        },
        ClinicalSection.ASSESSMENT_PLAN: {
            "Condition": 0.9,
            "Drug": 0.7,
            "Procedure": 0.6,
        },
        ClinicalSection.PLAN: {
            "Drug": 0.9,
            "Procedure": 0.8,
            "Condition": 0.5,
        },
        ClinicalSection.DIAGNOSIS: {
            "Condition": 1.0,
        },
        ClinicalSection.DISCHARGE_DIAGNOSIS: {
            "Condition": 1.0,
        },
        ClinicalSection.HOSPITAL_COURSE: {
            "Condition": 0.8,
            "Drug": 0.7,
            "Procedure": 0.7,
        },
        ClinicalSection.PROCEDURES: {
            "Procedure": 1.0,
        },
    }

    # Compiled patterns (lazy initialized)
    _compiled_patterns: list[tuple[re.Pattern, ClinicalSection]] = field(
        default_factory=list, repr=False
    )

    def __post_init__(self) -> None:
        """Compile regex patterns."""
        if not self._compiled_patterns:
            self._compiled_patterns = [
                (re.compile(pattern, re.IGNORECASE | re.MULTILINE), section)
                for pattern, section in self.SECTION_PATTERNS
            ]

    def parse(self, text: str) -> list[SectionSpan]:
        """Parse a clinical note to identify section boundaries.

        Args:
            text: The clinical note text.

        Returns:
            List of SectionSpan objects representing identified sections.
        """
        sections: list[SectionSpan] = []
        found_positions: set[int] = set()

        # Find all section headers
        for pattern, section in self._compiled_patterns:
            for match in pattern.finditer(text):
                start = match.start()
                # Avoid duplicate sections at same position
                if start in found_positions:
                    continue
                found_positions.add(start)

                sections.append(SectionSpan(
                    section=section,
                    start=start,
                    end=len(text),  # Will be updated below
                    header_text=match.group().strip(),
                ))

        # Sort by position
        sections.sort(key=lambda s: s.start)

        # Update end positions (each section ends where the next begins)
        for i in range(len(sections) - 1):
            sections[i].end = sections[i + 1].start

        return sections

    def get_section_at(self, text: str, offset: int) -> ClinicalSection:
        """Get the clinical section for a given character offset.

        Args:
            text: The clinical note text.
            offset: Character offset to find section for.

        Returns:
            The ClinicalSection at the given offset.
        """
        sections = self.parse(text)

        for section_span in reversed(sections):
            if section_span.start <= offset:
                return section_span.section

        return ClinicalSection.UNKNOWN

    def get_domain_affinity(
        self, section: ClinicalSection, domain: str
    ) -> float:
        """Get the affinity score for a domain in a section.

        Higher scores indicate the domain is more expected in that section.

        Args:
            section: The clinical section.
            domain: The OMOP domain (e.g., "Condition", "Drug").

        Returns:
            Affinity score between 0.0 and 1.0.
        """
        if section not in self.SECTION_DOMAIN_AFFINITY:
            return 0.5  # Neutral affinity for unknown sections

        affinities = self.SECTION_DOMAIN_AFFINITY[section]
        return affinities.get(domain, 0.3)  # Low default for unexpected domains

    def calculate_confidence_modifier(
        self, section: ClinicalSection, domain: str
    ) -> float:
        """Calculate a confidence modifier based on section-domain fit.

        Args:
            section: The clinical section where term was found.
            domain: The OMOP domain of the extracted term.

        Returns:
            Modifier between 0.8 and 1.1 to apply to base confidence.
        """
        affinity = self.get_domain_affinity(section, domain)

        # Scale affinity to confidence modifier
        # High affinity (0.8-1.0) -> slight boost (1.0-1.1)
        # Medium affinity (0.4-0.7) -> neutral (0.95-1.0)
        # Low affinity (0.0-0.3) -> slight reduction (0.8-0.9)

        if affinity >= 0.8:
            return 1.0 + (affinity - 0.8) * 0.5  # 1.0 to 1.1
        elif affinity >= 0.4:
            return 0.95 + (affinity - 0.4) * 0.125  # 0.95 to 1.0
        else:
            return 0.8 + affinity * 0.5  # 0.8 to 0.95


# Singleton instance for reuse
_section_parser: SectionParser | None = None
_parser_lock = threading.Lock()


def get_section_parser() -> SectionParser:
    """Get the singleton SectionParser instance."""
    global _section_parser
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _section_parser is None:
        with _parser_lock:
            if _section_parser is None:
                _section_parser = SectionParser()
    return _section_parser
