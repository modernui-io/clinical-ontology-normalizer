"""Clinical Context Analysis Service.

Provides advanced NLP capabilities for clinical text:
- Negation detection (NegEx-style algorithm)
- Section detection and classification
- Temporal context (historical vs current)
- Assertion classification (positive, negative, uncertain, hypothetical)

These capabilities dramatically improve extraction precision by filtering
out false positives from negated mentions, family history, etc.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ============================================================================
# Enums
# ============================================================================


class Assertion(Enum):
    """Assertion status of a clinical finding."""
    PRESENT = "present"           # Confirmed present
    ABSENT = "absent"             # Explicitly negated
    UNCERTAIN = "uncertain"       # Possible/probable
    HYPOTHETICAL = "hypothetical" # If/would
    HISTORICAL = "historical"     # Past history
    FAMILY = "family"             # Family history
    OTHER_PERSON = "other_person" # About someone else


class ClinicalSection(Enum):
    """Standard clinical note sections."""
    CHIEF_COMPLAINT = "chief_complaint"
    HPI = "history_of_present_illness"
    PMH = "past_medical_history"
    PSH = "past_surgical_history"
    FAMILY_HISTORY = "family_history"
    SOCIAL_HISTORY = "social_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    ROS = "review_of_systems"
    PHYSICAL_EXAM = "physical_exam"
    VITALS = "vitals"
    LABS = "labs"
    IMAGING = "imaging"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    UNKNOWN = "unknown"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class NegationScope:
    """Represents a negation scope in text."""
    trigger: str
    trigger_start: int
    trigger_end: int
    scope_start: int
    scope_end: int
    negation_type: str  # "negation", "uncertainty", "hypothetical"


@dataclass
class SectionSpan:
    """A detected section in the clinical note."""
    section: ClinicalSection
    header: str
    start: int
    end: int
    content: str


@dataclass
class ContextualMention:
    """A mention with its clinical context."""
    text: str
    start: int
    end: int
    assertion: Assertion
    section: ClinicalSection
    is_negated: bool = False
    is_uncertain: bool = False
    is_historical: bool = False
    is_family_history: bool = False
    confidence_modifier: float = 1.0  # Multiplier for base confidence
    context_clues: list[str] = field(default_factory=list)


# ============================================================================
# Negation Detection (NegEx-style)
# ============================================================================


class NegationDetector:
    """
    Detects negation in clinical text using a NegEx-style algorithm.

    NegEx identifies negation triggers and their scope to determine
    if a clinical finding is negated (e.g., "no fever" → fever is ABSENT).

    Patterns are pre-compiled at class level for performance.
    """

    # Pre-negation triggers (negate terms that follow)
    PRE_NEGATION_TRIGGERS = [
        # Definite negation
        r'\bno\b',
        r'\bnot\b',
        r'\bwithout\b',
        r'\bdeny\b',
        r'\bdenies\b',
        r'\bdenied\b',
        r'\bnegative for\b',
        r'\brules out\b',
        r'\bruled out\b',
        r'\br/o\b',
        r'\bfree of\b',
        r'\babsence of\b',
        r'\babsent\b',
        r'\bno evidence of\b',
        r'\bno signs of\b',
        r'\bno symptoms of\b',
        r'\bno history of\b',
        r'\bno known\b',
        r'\bnever had\b',
        r'\bnever\b',
        r'\bfailed to reveal\b',
        r'\btest negative\b',
        r'\btested negative\b',
        r'\bnon-?diagnostic\b',
        r'\bexclude[ds]?\b',
        r'\bexcluding\b',
        r'\bunremarkable\b',
        r'\bnormal\b(?=\s+(?:limits?|range|findings?))',
        r'\bwas not\b',
        r'\bwere not\b',
        r'\bdid not have\b',
        r'\bdoes not have\b',
        r'\bhas no\b',
        r'\bhave no\b',
        r'\bno apparent\b',
        r'\bno acute\b',
        r'\bno significant\b',
        r'\bno obvious\b',
        r'\bno gross\b',
        r'\bno definite\b',
        r'\bresolve[ds]?\b',
        r'\bresolution of\b',
    ]

    # Post-negation triggers (negate terms that precede)
    POST_NEGATION_TRIGGERS = [
        r'\brunlikely\b',
        r'\bhas been ruled out\b',
        r'\bwas ruled out\b',
        r'\bwere ruled out\b',
        r'\bnot present\b',
        r'\bnot seen\b',
        r'\bnot observed\b',
        r'\bnot identified\b',
        r'\bnot detected\b',
        r'\bnot demonstrated\b',
        r'\bwas negative\b',
        r'\bwere negative\b',
    ]

    # Uncertainty triggers
    UNCERTAINTY_TRIGGERS = [
        r'\bpossible\b',
        r'\bpossibly\b',
        r'\bprobable\b',
        r'\bprobably\b',
        r'\blikely\b',
        r'\bsuspect(?:ed|s)?\b',
        r'\bsuspicious\b',
        r'\bsuggestive\b',
        r'\bquestionable\b',
        r'\buncertain\b',
        r'\bunclear\b',
        r'\bequivocal\b',
        r'\bcannot be excluded\b',
        r'\bcannot rule out\b',
        r'\bconcern(?:ed|ing)? for\b',
        r'\braise[sd]? concern\b',
        r'\bworrisome\b',
        r'\bmay (?:be|have|represent)\b',
        r'\bmight (?:be|have|represent)\b',
        r'\bcould (?:be|have|represent)\b',
        r'\b(?:differential|ddx)\b.*\bincludes?\b',
        r'\brule out\b',  # When used as "to rule out" = uncertain
        r'\b\?\b',  # Question mark often indicates uncertainty
    ]

    # Hypothetical triggers
    HYPOTHETICAL_TRIGGERS = [
        r'\bif\b',
        r'\bshould\b',
        r'\bwould\b',
        r'\bcould\b',
        r'\bwill (?:be|have)\b',
        r'\bwatch for\b',
        r'\breturn (?:precautions|if)\b',
        r'\bmonitor for\b',
        r'\bin (?:the )?event of\b',
        r'\bin case of\b',
    ]

    # Scope terminators (stop negation scope)
    SCOPE_TERMINATORS = [
        r'\bbut\b',
        r'\bhowever\b',
        r'\balthough\b',
        r'\bthough\b',
        r'\baside from\b',
        r'\bexcept\b',
        r'\bapart from\b',
        r'\bother than\b',
        r'\bnevertheless\b',
        r'\byet\b',
        r'\bstill\b',
        r'\bwhich\b',
        r'\bthat\b',
        r'\bwho\b',
        r';',
        r'\.',
        r':',
    ]

    # Maximum scope distance (characters)
    MAX_SCOPE_DISTANCE = 50

    def __init__(self):
        # Compile patterns
        self._pre_neg_pattern = re.compile(
            '|'.join(f'({p})' for p in self.PRE_NEGATION_TRIGGERS),
            re.IGNORECASE
        )
        self._post_neg_pattern = re.compile(
            '|'.join(f'({p})' for p in self.POST_NEGATION_TRIGGERS),
            re.IGNORECASE
        )
        self._uncertainty_pattern = re.compile(
            '|'.join(f'({p})' for p in self.UNCERTAINTY_TRIGGERS),
            re.IGNORECASE
        )
        self._hypothetical_pattern = re.compile(
            '|'.join(f'({p})' for p in self.HYPOTHETICAL_TRIGGERS),
            re.IGNORECASE
        )
        self._terminator_pattern = re.compile(
            '|'.join(f'({p})' for p in self.SCOPE_TERMINATORS),
            re.IGNORECASE
        )

    def find_negation_scopes(self, text: str) -> list[NegationScope]:
        """
        Find all negation scopes in text.

        Args:
            text: Clinical text to analyze

        Returns:
            List of NegationScope objects
        """
        scopes = []

        # Find pre-negation scopes
        for match in self._pre_neg_pattern.finditer(text):
            scope_end = self._find_scope_end(text, match.end())
            scopes.append(NegationScope(
                trigger=match.group(),
                trigger_start=match.start(),
                trigger_end=match.end(),
                scope_start=match.end(),
                scope_end=scope_end,
                negation_type="negation",
            ))

        # Find post-negation scopes
        for match in self._post_neg_pattern.finditer(text):
            scope_start = self._find_scope_start(text, match.start())
            scopes.append(NegationScope(
                trigger=match.group(),
                trigger_start=match.start(),
                trigger_end=match.end(),
                scope_start=scope_start,
                scope_end=match.start(),
                negation_type="negation",
            ))

        # Find uncertainty scopes
        for match in self._uncertainty_pattern.finditer(text):
            scope_end = self._find_scope_end(text, match.end())
            scopes.append(NegationScope(
                trigger=match.group(),
                trigger_start=match.start(),
                trigger_end=match.end(),
                scope_start=match.end(),
                scope_end=scope_end,
                negation_type="uncertainty",
            ))

        # Find hypothetical scopes
        for match in self._hypothetical_pattern.finditer(text):
            scope_end = self._find_scope_end(text, match.end())
            scopes.append(NegationScope(
                trigger=match.group(),
                trigger_start=match.start(),
                trigger_end=match.end(),
                scope_start=match.end(),
                scope_end=scope_end,
                negation_type="hypothetical",
            ))

        return scopes

    def _find_scope_end(self, text: str, start: int) -> int:
        """Find where negation scope ends (forward)."""
        remaining = text[start:start + self.MAX_SCOPE_DISTANCE]

        # Look for terminator
        match = self._terminator_pattern.search(remaining)
        if match:
            return start + match.start()

        return start + min(len(remaining), self.MAX_SCOPE_DISTANCE)

    def _find_scope_start(self, text: str, end: int) -> int:
        """Find where negation scope starts (backward)."""
        start = max(0, end - self.MAX_SCOPE_DISTANCE)
        preceding = text[start:end]

        # Look for terminator (searching backward)
        for match in self._terminator_pattern.finditer(preceding):
            start = start + match.end()

        return start

    def is_negated(self, text: str, mention_start: int, mention_end: int) -> tuple[bool, str | None]:
        """
        Check if a mention at given position is negated.

        Args:
            text: Full clinical text
            mention_start: Start position of mention
            mention_end: End position of mention

        Returns:
            Tuple of (is_negated, trigger_text)
        """
        scopes = self.find_negation_scopes(text)

        for scope in scopes:
            if scope.negation_type == "negation":
                # Check if mention falls within scope
                if scope.scope_start <= mention_start and mention_end <= scope.scope_end:
                    return True, scope.trigger
                # Also check for pre-negation where trigger is right before mention
                if scope.trigger_end <= mention_start <= scope.trigger_end + 5:
                    return True, scope.trigger

        return False, None

    def get_assertion(self, text: str, mention_start: int, mention_end: int) -> tuple[Assertion, str | None]:
        """
        Get the assertion status of a mention.

        Args:
            text: Full clinical text
            mention_start: Start position of mention
            mention_end: End position of mention

        Returns:
            Tuple of (Assertion, trigger_text)
        """
        scopes = self.find_negation_scopes(text)

        for scope in scopes:
            # Check if mention falls within scope
            in_scope = (scope.scope_start <= mention_start and mention_end <= scope.scope_end) or \
                      (scope.trigger_end <= mention_start <= scope.trigger_end + 5)

            if in_scope:
                if scope.negation_type == "negation":
                    return Assertion.ABSENT, scope.trigger
                elif scope.negation_type == "uncertainty":
                    return Assertion.UNCERTAIN, scope.trigger
                elif scope.negation_type == "hypothetical":
                    return Assertion.HYPOTHETICAL, scope.trigger

        return Assertion.PRESENT, None


# ============================================================================
# Section Detection
# ============================================================================


class SectionDetector:
    """Detects and classifies sections in clinical notes."""

    SECTION_PATTERNS = {
        ClinicalSection.CHIEF_COMPLAINT: [
            r'\bchief complaint[s]?\b',
            r'\bcc\b(?=\s*:)',
            r'\breason for (?:visit|consultation|admission)\b',
            r'\bpresenting complaint\b',
        ],
        ClinicalSection.HPI: [
            r'\bhistory of present(?:ing)? illness\b',
            r'\bhpi\b(?=\s*:)',
            r'\bpresent(?:ing)? illness\b',
            r'\bhistory of the present illness\b',
        ],
        ClinicalSection.PMH: [
            r'\bpast medical history\b',
            r'\bpmh\b(?=\s*:)',
            r'\bmedical history\b',
            r'\bpast history\b',
            r'\bbackground\b(?=\s*:)',
        ],
        ClinicalSection.PSH: [
            r'\bpast surgical history\b',
            r'\bsurgical history\b',
            r'\bpsh\b(?=\s*:)',
            r'\boperations?\b(?=\s*:)',
            r'\bprocedures?\b(?=\s*:)',
        ],
        ClinicalSection.FAMILY_HISTORY: [
            r'\bfamily (?:medical )?history\b',
            r'\bfhx?\b(?=\s*:)',
            r'\bfamily hx\b',
        ],
        ClinicalSection.SOCIAL_HISTORY: [
            r'\bsocial history\b',
            r'\bshx?\b(?=\s*:)',
            r'\bsocial hx\b',
            r'\bhabits?\b(?=\s*:)',
        ],
        ClinicalSection.MEDICATIONS: [
            r'\bmedications?\b',
            r'\bmeds?\b(?=\s*:)',
            r'\bcurrent medications?\b',
            r'\bhome medications?\b',
            r'\bmedication list\b',
            r'\bdrugs?\b(?=\s*:)',
        ],
        ClinicalSection.ALLERGIES: [
            r'\ballergi(?:es|c)\b',
            r'\bnkda\b',
            r'\bdrug allergi(?:es|c)\b',
            r'\badverse (?:drug )?reactions?\b',
        ],
        ClinicalSection.ROS: [
            r'\breview of systems?\b',
            r'\bros\b(?=\s*:)',
            r'\bsystems? review\b',
        ],
        ClinicalSection.PHYSICAL_EXAM: [
            r'\bphysical exam(?:ination)?\b',
            r'\bpe\b(?=\s*:)',
            r'\bexam(?:ination)?\b(?=\s*:)',
            r'\bobjective\b(?=\s*:)',
            r'\bfindings?\b(?=\s*:)',
        ],
        ClinicalSection.VITALS: [
            r'\bvital signs?\b',
            r'\bvitals?\b(?=\s*:)',
            r'\bvs\b(?=\s*:)',
        ],
        ClinicalSection.LABS: [
            r'\blab(?:oratory)?(?: results?)?\b(?=\s*:)',
            r'\blabs?\b(?=\s*:)',
            r'\btest results?\b',
            r'\bchemistry\b',
            r'\bcbc\b',
            r'\bbmp\b',
            r'\bcmp\b',
        ],
        ClinicalSection.IMAGING: [
            r'\bimaging\b',
            r'\bradiology\b',
            r'\bx-?ray\b',
            r'\bct\b(?=\s)',
            r'\bmri\b',
            r'\bultrasound\b',
            r'\becg\b',
            r'\bekg\b',
            r'\bechocardiogram\b',
        ],
        ClinicalSection.ASSESSMENT: [
            r'\bassessment\b(?=\s*:|\s*(?:and|&))',
            r'\bimpression\b',
            r'\bdiagnos(?:is|es)\b',
            r'\bddx\b',
            r'\bdifferential\b',
            r'\bconclusion\b',
        ],
        ClinicalSection.PLAN: [
            r'\bplan\b(?=\s*:)',
            r'\brecommendations?\b',
            r'\btreatment(?: plan)?\b',
            r'\bmanagement\b',
            r'\bdisposition\b',
            r'\bfollow[- ]?up\b',
        ],
    }

    def __init__(self):
        self._patterns = {}
        for section, patterns in self.SECTION_PATTERNS.items():
            combined = '|'.join(f'({p})' for p in patterns)
            self._patterns[section] = re.compile(combined, re.IGNORECASE)

    def detect_sections(self, text: str) -> list[SectionSpan]:
        """
        Detect all sections in clinical text.

        Args:
            text: Clinical note text

        Returns:
            List of SectionSpan objects sorted by position
        """
        sections = []

        for section, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                # Find section end (next section or end of text)
                sections.append(SectionSpan(
                    section=section,
                    header=match.group(),
                    start=match.start(),
                    end=-1,  # Will be set later
                    content="",
                ))

        # Sort by start position
        sections.sort(key=lambda s: s.start)

        # Set end positions and content
        for i, section in enumerate(sections):
            if i + 1 < len(sections):
                section.end = sections[i + 1].start
            else:
                section.end = len(text)
            section.content = text[section.start:section.end]

        return sections

    def get_section_at_position(self, sections: list[SectionSpan], position: int) -> ClinicalSection:
        """Get the section containing a given position."""
        for section in sections:
            if section.start <= position < section.end:
                return section.section
        return ClinicalSection.UNKNOWN


# ============================================================================
# Historical Detection
# ============================================================================


class HistoricalDetector:
    """Detects historical (past) vs current (active) mentions."""

    HISTORICAL_TRIGGERS = [
        r'\bhistory of\b',
        r'\bh/o\b',
        r'\bpast (?:medical )?history\b',
        r'\bpmh\b',
        r'\bprevious(?:ly)?\b',
        r'\bformer(?:ly)?\b',
        r'\bprior\b',
        r'\bpast\b',
        r'\bremote\b',
        r'\bchildhood\b',
        r'\byears? ago\b',
        r'\bmonths? ago\b',
        r'\b(?:in|since) (?:19|20)\d{2}\b',
        r'\bresolved\b',
        r'\bquiescent\b',
        r'\binactive\b',
        r'\bremission\b',
        r'\bs/p\b',  # status post
        r'\bstatus post\b',
        r'\bpost-?\b',
    ]

    CURRENT_TRIGGERS = [
        r'\bcurrent(?:ly)?\b',
        r'\bactive\b',
        r'\bacute(?:ly)?\b',
        r'\bongoing\b',
        r'\bpresent(?:ly|ing)?\b',
        r'\bnew(?:ly)?\b',
        r'\brecent(?:ly)?\b',
        r'\btoday\b',
        r'\bthis (?:morning|afternoon|evening)\b',
        r'\bnow\b',
        r'\bworsening\b',
        r'\bexacerbation\b',
    ]

    def __init__(self):
        self._historical_pattern = re.compile(
            '|'.join(f'({p})' for p in self.HISTORICAL_TRIGGERS),
            re.IGNORECASE
        )
        self._current_pattern = re.compile(
            '|'.join(f'({p})' for p in self.CURRENT_TRIGGERS),
            re.IGNORECASE
        )

    def is_historical(self, text: str, mention_start: int, mention_end: int) -> tuple[bool, str | None]:
        """
        Check if a mention refers to historical (past) condition.

        Args:
            text: Full clinical text
            mention_start: Start position of mention
            mention_end: End position of mention

        Returns:
            Tuple of (is_historical, trigger_text)
        """
        # Look in preceding context (up to 30 chars before)
        context_start = max(0, mention_start - 30)
        preceding = text[context_start:mention_start].lower()

        # Check for historical triggers
        for match in self._historical_pattern.finditer(preceding):
            return True, match.group()

        # Check for current triggers (these override historical)
        for match in self._current_pattern.finditer(preceding):
            return False, None

        return False, None


# ============================================================================
# Family History Detection
# ============================================================================


class FamilyHistoryDetector:
    """Detects mentions that refer to family members rather than patient."""

    FAMILY_TRIGGERS = [
        r'\bfamily history\b',
        r'\bfhx?\b',
        r'\bmother\b',
        r'\bfather\b',
        r'\bparent[s]?\b',
        r'\bsibling[s]?\b',
        r'\bbrother\b',
        r'\bsister\b',
        r'\bgrandmother\b',
        r'\bgrandfather\b',
        r'\bgrandparent[s]?\b',
        r'\baunt\b',
        r'\buncle\b',
        r'\bcousin\b',
        r'\brelative[s]?\b',
        r'\bmaternal\b',
        r'\bpaternal\b',
    ]

    def __init__(self):
        self._family_pattern = re.compile(
            '|'.join(f'({p})' for p in self.FAMILY_TRIGGERS),
            re.IGNORECASE
        )

    def is_family_history(
        self,
        text: str,
        mention_start: int,
        mention_end: int,
        sections: list[SectionSpan] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if a mention refers to family history.

        Args:
            text: Full clinical text
            mention_start: Start position of mention
            mention_end: End position of mention
            sections: Pre-detected sections (optional)

        Returns:
            Tuple of (is_family_history, trigger_text)
        """
        # Check if in Family History section
        if sections:
            for section in sections:
                if section.section == ClinicalSection.FAMILY_HISTORY:
                    if section.start <= mention_start < section.end:
                        return True, "family history section"

        # Look in surrounding context
        context_start = max(0, mention_start - 50)
        context_end = min(len(text), mention_end + 20)
        context = text[context_start:context_end].lower()

        for match in self._family_pattern.finditer(context):
            # Check if family trigger is near the mention
            trigger_pos = context_start + match.start()
            if abs(trigger_pos - mention_start) < 50:
                return True, match.group()

        return False, None


# ============================================================================
# Combined Clinical Context Analyzer
# ============================================================================


class ClinicalContextAnalyzer:
    """
    Comprehensive clinical context analyzer.

    Combines negation detection, section awareness, historical detection,
    and family history detection to provide rich context for each mention.
    """

    def __init__(self):
        self.negation_detector = NegationDetector()
        self.section_detector = SectionDetector()
        self.historical_detector = HistoricalDetector()
        self.family_history_detector = FamilyHistoryDetector()

    def analyze_mention(
        self,
        text: str,
        mention_text: str,
        mention_start: int,
        mention_end: int,
        sections: list[SectionSpan] | None = None,
    ) -> ContextualMention:
        """
        Analyze the clinical context of a mention.

        Args:
            text: Full clinical text
            mention_text: The mention text
            mention_start: Start position
            mention_end: End position
            sections: Pre-detected sections (optional, will detect if None)

        Returns:
            ContextualMention with full context analysis
        """
        if sections is None:
            sections = self.section_detector.detect_sections(text)

        # Get section
        section = self.section_detector.get_section_at_position(sections, mention_start)

        # Check negation
        assertion, neg_trigger = self.negation_detector.get_assertion(text, mention_start, mention_end)

        # Check if historical
        is_historical, hist_trigger = self.historical_detector.is_historical(text, mention_start, mention_end)

        # Check if family history
        is_family, family_trigger = self.family_history_detector.is_family_history(
            text, mention_start, mention_end, sections
        )

        # Determine final assertion
        if is_family:
            assertion = Assertion.FAMILY
        elif is_historical and assertion == Assertion.PRESENT:
            assertion = Assertion.HISTORICAL

        # Build context clues
        context_clues = []
        if neg_trigger:
            context_clues.append(f"negation: {neg_trigger}")
        if hist_trigger:
            context_clues.append(f"historical: {hist_trigger}")
        if family_trigger:
            context_clues.append(f"family: {family_trigger}")

        # Calculate confidence modifier
        confidence_modifier = 1.0
        if assertion == Assertion.ABSENT:
            confidence_modifier = 0.0  # Negated = don't extract
        elif assertion == Assertion.UNCERTAIN:
            confidence_modifier = 0.7
        elif assertion == Assertion.HYPOTHETICAL:
            confidence_modifier = 0.3
        elif assertion == Assertion.FAMILY:
            confidence_modifier = 0.0  # Family history = don't extract as patient condition
        elif assertion == Assertion.HISTORICAL:
            confidence_modifier = 0.8  # Historical is still relevant but lower weight

        # Sections that shouldn't contribute to active conditions
        if section == ClinicalSection.FAMILY_HISTORY:
            confidence_modifier = 0.0
        elif section == ClinicalSection.ROS:
            # ROS with negation is very common
            if assertion == Assertion.ABSENT:
                confidence_modifier = 0.0

        return ContextualMention(
            text=mention_text,
            start=mention_start,
            end=mention_end,
            assertion=assertion,
            section=section,
            is_negated=(assertion == Assertion.ABSENT),
            is_uncertain=(assertion == Assertion.UNCERTAIN),
            is_historical=(assertion == Assertion.HISTORICAL),
            is_family_history=(assertion == Assertion.FAMILY or section == ClinicalSection.FAMILY_HISTORY),
            confidence_modifier=confidence_modifier,
            context_clues=context_clues,
        )

    def analyze_text(self, text: str) -> tuple[list[SectionSpan], list[NegationScope]]:
        """
        Pre-analyze text for sections and negation scopes.

        Useful for batch processing multiple mentions from same text.

        Args:
            text: Clinical text

        Returns:
            Tuple of (sections, negation_scopes)
        """
        sections = self.section_detector.detect_sections(text)
        scopes = self.negation_detector.find_negation_scopes(text)
        return sections, scopes


# ============================================================================
# Singleton
# ============================================================================


_analyzer_instance: ClinicalContextAnalyzer | None = None
_analyzer_lock = threading.Lock()


def get_clinical_context_analyzer() -> ClinicalContextAnalyzer:
    """Get or create the singleton analyzer instance."""
    global _analyzer_instance
    # VP-ThreadSafety-1: Double-checked locking for thread safety
    if _analyzer_instance is None:
        with _analyzer_lock:
            if _analyzer_instance is None:
                _analyzer_instance = ClinicalContextAnalyzer()
    return _analyzer_instance
