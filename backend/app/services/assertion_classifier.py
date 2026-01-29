"""Probabilistic Assertion Classifier for Clinical NLP.

This module provides calibrated confidence scores for assertion detection
in clinical text, replacing binary classification with probability distributions.

Key features:
- Calibrated confidence scores based on clinical NLP literature
- Scope-aware trigger matching (forward/backward/bidirectional)
- Support for multiple assertion categories (absent, uncertain, hypothetical, present)
- Batch processing for efficiency
- Integration with existing ExtractedMention dataclass

References:
- NegEx: Chapman et al. (2001) - A simple algorithm for negation detection
- ConText: Harkema et al. (2009) - Extending NegEx with temporal and experiencer
- NegBERT: Khandelwal & Sawant (2020) - Transformer-based negation detection
"""

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple

from app.schemas.base import Assertion

logger = logging.getLogger(__name__)


class TriggerScope(str, Enum):
    """Direction of trigger influence on assertion."""

    FORWARD = "forward"  # Trigger affects text after it (e.g., "no evidence of")
    BACKWARD = "backward"  # Trigger affects text before it (e.g., "is ruled out")
    BIDIRECTIONAL = "bidirectional"  # Trigger affects text in both directions


class AssertionCategory(str, Enum):
    """Categories of assertion with associated confidence ranges."""

    ABSENT = "absent"  # Negated/denied (confidence 0.85-0.98)
    UNCERTAIN = "uncertain"  # Possible/suspected (confidence 0.30-0.70)
    HYPOTHETICAL = "hypothetical"  # Conditional/future (confidence 0.20-0.40)
    PRESENT = "present"  # Affirmed/confirmed (confidence 0.85-0.98)


@dataclass(frozen=True)
class AssertionTrigger:
    """A trigger pattern for assertion detection with calibrated confidence.

    Attributes:
        pattern: The trigger text pattern (lowercase)
        category: The assertion category this trigger indicates
        confidence: Calibrated confidence score (0.0-1.0)
        scope: Direction of trigger influence
        max_scope_tokens: Maximum tokens between trigger and mention
        is_pseudo: If True, this is a pseudo-negation (e.g., "no change" doesn't negate)
    """

    pattern: str
    category: AssertionCategory
    confidence: float
    scope: TriggerScope = TriggerScope.FORWARD
    max_scope_tokens: int = 6
    is_pseudo: bool = False


class AssertionResult(NamedTuple):
    """Result of assertion classification.

    Attributes:
        assertion: The Assertion enum value
        confidence: Calibrated confidence score (0.0-1.0)
        trigger_text: The trigger pattern that matched (if any)
        trigger_distance: Token distance from trigger to mention
        category: The AssertionCategory that was detected
    """

    assertion: Assertion
    confidence: float
    trigger_text: str | None
    trigger_distance: int | None
    category: AssertionCategory


# =============================================================================
# Calibrated Trigger Patterns
# =============================================================================
# Confidence scores are calibrated based on:
# - NegEx validation studies (Chapman et al., 2001)
# - ConText evaluation (Harkema et al., 2009)
# - Clinical intuition for edge cases
# =============================================================================

ABSENT_TRIGGERS: list[AssertionTrigger] = [
    # High confidence negations (0.95-0.98)
    AssertionTrigger("no evidence of", AssertionCategory.ABSENT, 0.98, TriggerScope.FORWARD),
    AssertionTrigger("denies", AssertionCategory.ABSENT, 0.97, TriggerScope.FORWARD),
    AssertionTrigger("denied", AssertionCategory.ABSENT, 0.97, TriggerScope.FORWARD),
    AssertionTrigger("no signs of", AssertionCategory.ABSENT, 0.97, TriggerScope.FORWARD),
    AssertionTrigger("ruled out", AssertionCategory.ABSENT, 0.96, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("is ruled out", AssertionCategory.ABSENT, 0.96, TriggerScope.BACKWARD),
    AssertionTrigger("was ruled out", AssertionCategory.ABSENT, 0.96, TriggerScope.BACKWARD),
    AssertionTrigger("rules out", AssertionCategory.ABSENT, 0.95, TriggerScope.FORWARD),
    AssertionTrigger("negative for", AssertionCategory.ABSENT, 0.96, TriggerScope.FORWARD),
    AssertionTrigger("without evidence of", AssertionCategory.ABSENT, 0.96, TriggerScope.FORWARD),
    AssertionTrigger("free of", AssertionCategory.ABSENT, 0.95, TriggerScope.FORWARD),
    # Medium-high confidence negations (0.90-0.94)
    AssertionTrigger("no", AssertionCategory.ABSENT, 0.92, TriggerScope.FORWARD, max_scope_tokens=4),
    AssertionTrigger("not", AssertionCategory.ABSENT, 0.90, TriggerScope.FORWARD, max_scope_tokens=4),
    AssertionTrigger("without", AssertionCategory.ABSENT, 0.91, TriggerScope.FORWARD),
    AssertionTrigger("absence of", AssertionCategory.ABSENT, 0.94, TriggerScope.FORWARD),
    AssertionTrigger("absent", AssertionCategory.ABSENT, 0.93, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("never had", AssertionCategory.ABSENT, 0.94, TriggerScope.FORWARD),
    AssertionTrigger("never developed", AssertionCategory.ABSENT, 0.94, TriggerScope.FORWARD),
    AssertionTrigger("no history of", AssertionCategory.ABSENT, 0.93, TriggerScope.FORWARD),
    AssertionTrigger("no known", AssertionCategory.ABSENT, 0.92, TriggerScope.FORWARD),
    AssertionTrigger("no significant", AssertionCategory.ABSENT, 0.91, TriggerScope.FORWARD),
    AssertionTrigger("unremarkable", AssertionCategory.ABSENT, 0.90, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("non-contributory", AssertionCategory.ABSENT, 0.90, TriggerScope.BIDIRECTIONAL),
    # Lower confidence negations (0.85-0.89)
    AssertionTrigger("doesn't have", AssertionCategory.ABSENT, 0.89, TriggerScope.FORWARD),
    AssertionTrigger("does not have", AssertionCategory.ABSENT, 0.89, TriggerScope.FORWARD),
    AssertionTrigger("didn't have", AssertionCategory.ABSENT, 0.88, TriggerScope.FORWARD),
    AssertionTrigger("did not have", AssertionCategory.ABSENT, 0.88, TriggerScope.FORWARD),
    AssertionTrigger("no longer has", AssertionCategory.ABSENT, 0.87, TriggerScope.FORWARD),
    AssertionTrigger("resolved", AssertionCategory.ABSENT, 0.86, TriggerScope.BACKWARD),
    AssertionTrigger("has resolved", AssertionCategory.ABSENT, 0.87, TriggerScope.BACKWARD),
    AssertionTrigger("cleared", AssertionCategory.ABSENT, 0.85, TriggerScope.BACKWARD),
]

UNCERTAIN_TRIGGERS: list[AssertionTrigger] = [
    # High uncertainty (0.50-0.70) - "possible" category
    AssertionTrigger("possible", AssertionCategory.UNCERTAIN, 0.55, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("possibly", AssertionCategory.UNCERTAIN, 0.55, TriggerScope.FORWARD),
    AssertionTrigger("probable", AssertionCategory.UNCERTAIN, 0.65, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("probably", AssertionCategory.UNCERTAIN, 0.65, TriggerScope.FORWARD),
    AssertionTrigger("likely", AssertionCategory.UNCERTAIN, 0.70, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("most likely", AssertionCategory.UNCERTAIN, 0.75, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("appears to be", AssertionCategory.UNCERTAIN, 0.60, TriggerScope.FORWARD),
    AssertionTrigger("appears to have", AssertionCategory.UNCERTAIN, 0.60, TriggerScope.FORWARD),
    AssertionTrigger("suggestive of", AssertionCategory.UNCERTAIN, 0.60, TriggerScope.FORWARD),
    AssertionTrigger("consistent with", AssertionCategory.UNCERTAIN, 0.65, TriggerScope.FORWARD),
    AssertionTrigger("compatible with", AssertionCategory.UNCERTAIN, 0.60, TriggerScope.FORWARD),
    # Medium uncertainty (0.40-0.49) - "suspected" category
    AssertionTrigger("suspected", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("suspect", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.FORWARD),
    AssertionTrigger("suspicion of", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.FORWARD),
    AssertionTrigger("questionable", AssertionCategory.UNCERTAIN, 0.40, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("question of", AssertionCategory.UNCERTAIN, 0.40, TriggerScope.FORWARD),
    AssertionTrigger("concerning for", AssertionCategory.UNCERTAIN, 0.50, TriggerScope.FORWARD),
    AssertionTrigger("concern for", AssertionCategory.UNCERTAIN, 0.50, TriggerScope.FORWARD),
    AssertionTrigger("cannot rule out", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.FORWARD),
    AssertionTrigger("cannot exclude", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.FORWARD),
    AssertionTrigger("may have", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.FORWARD),
    AssertionTrigger("may be", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.FORWARD),
    AssertionTrigger("might have", AssertionCategory.UNCERTAIN, 0.40, TriggerScope.FORWARD),
    AssertionTrigger("might be", AssertionCategory.UNCERTAIN, 0.40, TriggerScope.FORWARD),
    AssertionTrigger("could be", AssertionCategory.UNCERTAIN, 0.40, TriggerScope.FORWARD),
    AssertionTrigger("could have", AssertionCategory.UNCERTAIN, 0.40, TriggerScope.FORWARD),
    # Low uncertainty (0.30-0.39) - "equivocal" category
    AssertionTrigger("equivocal", AssertionCategory.UNCERTAIN, 0.35, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("uncertain", AssertionCategory.UNCERTAIN, 0.35, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("unclear", AssertionCategory.UNCERTAIN, 0.35, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("differential includes", AssertionCategory.UNCERTAIN, 0.35, TriggerScope.FORWARD),
    AssertionTrigger("differential diagnosis", AssertionCategory.UNCERTAIN, 0.35, TriggerScope.FORWARD),
]

HYPOTHETICAL_TRIGGERS: list[AssertionTrigger] = [
    # Conditional assertions (0.20-0.40)
    AssertionTrigger("if", AssertionCategory.HYPOTHETICAL, 0.25, TriggerScope.FORWARD, max_scope_tokens=8),
    AssertionTrigger("should", AssertionCategory.HYPOTHETICAL, 0.30, TriggerScope.FORWARD),
    AssertionTrigger("would", AssertionCategory.HYPOTHETICAL, 0.25, TriggerScope.FORWARD),
    AssertionTrigger("in case of", AssertionCategory.HYPOTHETICAL, 0.20, TriggerScope.FORWARD),
    AssertionTrigger("risk of", AssertionCategory.HYPOTHETICAL, 0.35, TriggerScope.FORWARD),
    AssertionTrigger("risk for", AssertionCategory.HYPOTHETICAL, 0.35, TriggerScope.FORWARD),
    AssertionTrigger("at risk for", AssertionCategory.HYPOTHETICAL, 0.35, TriggerScope.FORWARD),
    AssertionTrigger("screening for", AssertionCategory.HYPOTHETICAL, 0.30, TriggerScope.FORWARD),
    AssertionTrigger("evaluate for", AssertionCategory.HYPOTHETICAL, 0.30, TriggerScope.FORWARD),
    AssertionTrigger("to rule out", AssertionCategory.HYPOTHETICAL, 0.25, TriggerScope.FORWARD),
    AssertionTrigger("to exclude", AssertionCategory.HYPOTHETICAL, 0.25, TriggerScope.FORWARD),
    AssertionTrigger("prophylaxis for", AssertionCategory.HYPOTHETICAL, 0.30, TriggerScope.FORWARD),
    AssertionTrigger("prophylactic", AssertionCategory.HYPOTHETICAL, 0.30, TriggerScope.FORWARD),
    AssertionTrigger("prevent", AssertionCategory.HYPOTHETICAL, 0.30, TriggerScope.FORWARD),
    AssertionTrigger("prevention of", AssertionCategory.HYPOTHETICAL, 0.30, TriggerScope.FORWARD),
]

PRESENT_TRIGGERS: list[AssertionTrigger] = [
    # High confidence affirmations (0.95-0.98)
    AssertionTrigger("confirmed", AssertionCategory.PRESENT, 0.98, TriggerScope.BIDIRECTIONAL),
    AssertionTrigger("positive for", AssertionCategory.PRESENT, 0.97, TriggerScope.FORWARD),
    AssertionTrigger("diagnosed with", AssertionCategory.PRESENT, 0.97, TriggerScope.FORWARD),
    AssertionTrigger("known", AssertionCategory.PRESENT, 0.95, TriggerScope.FORWARD),
    AssertionTrigger("known to have", AssertionCategory.PRESENT, 0.96, TriggerScope.FORWARD),
    AssertionTrigger("presents with", AssertionCategory.PRESENT, 0.96, TriggerScope.FORWARD),
    AssertionTrigger("presenting with", AssertionCategory.PRESENT, 0.96, TriggerScope.FORWARD),
    AssertionTrigger("demonstrates", AssertionCategory.PRESENT, 0.95, TriggerScope.FORWARD),
    AssertionTrigger("evidence of", AssertionCategory.PRESENT, 0.94, TriggerScope.FORWARD),
    AssertionTrigger("consistent findings of", AssertionCategory.PRESENT, 0.95, TriggerScope.FORWARD),
    # Medium-high confidence affirmations (0.85-0.94)
    # Note: "has"/"have" removed - too common and interfere with uncertainty/negation triggers
    AssertionTrigger("shows", AssertionCategory.PRESENT, 0.90, TriggerScope.FORWARD),
    AssertionTrigger("reveals", AssertionCategory.PRESENT, 0.91, TriggerScope.FORWARD),
    AssertionTrigger("exhibited", AssertionCategory.PRESENT, 0.90, TriggerScope.FORWARD),
    AssertionTrigger("experiencing", AssertionCategory.PRESENT, 0.89, TriggerScope.FORWARD),
    AssertionTrigger("complains of", AssertionCategory.PRESENT, 0.88, TriggerScope.FORWARD),
    AssertionTrigger("reports", AssertionCategory.PRESENT, 0.87, TriggerScope.FORWARD),
    AssertionTrigger("noted", AssertionCategory.PRESENT, 0.86, TriggerScope.FORWARD),  # Changed to FORWARD only
    AssertionTrigger("observed", AssertionCategory.PRESENT, 0.86, TriggerScope.FORWARD),  # Changed to FORWARD only
    AssertionTrigger("found to have", AssertionCategory.PRESENT, 0.92, TriggerScope.FORWARD),
]

# Pseudo-negation patterns - these look like negations but shouldn't negate
# Many of these need BACKWARD scope to affect entities mentioned before the pattern
PSEUDO_NEGATION_TRIGGERS: list[AssertionTrigger] = [
    AssertionTrigger("no change", AssertionCategory.PRESENT, 0.85, TriggerScope.BACKWARD, is_pseudo=True, max_scope_tokens=10),
    AssertionTrigger("no increase", AssertionCategory.PRESENT, 0.85, TriggerScope.BACKWARD, is_pseudo=True, max_scope_tokens=10),
    AssertionTrigger("no decrease", AssertionCategory.PRESENT, 0.85, TriggerScope.BACKWARD, is_pseudo=True, max_scope_tokens=10),
    AssertionTrigger("no worsening", AssertionCategory.PRESENT, 0.85, TriggerScope.BACKWARD, is_pseudo=True, max_scope_tokens=10),
    AssertionTrigger("no improvement", AssertionCategory.PRESENT, 0.85, TriggerScope.BACKWARD, is_pseudo=True, max_scope_tokens=10),
    AssertionTrigger("not only", AssertionCategory.PRESENT, 0.85, TriggerScope.FORWARD, is_pseudo=True),
    AssertionTrigger("not cause", AssertionCategory.PRESENT, 0.85, TriggerScope.FORWARD, is_pseudo=True),
    AssertionTrigger("gram negative", AssertionCategory.PRESENT, 0.95, TriggerScope.BIDIRECTIONAL, is_pseudo=True),
    AssertionTrigger("not ruled out", AssertionCategory.UNCERTAIN, 0.45, TriggerScope.BACKWARD, is_pseudo=True, max_scope_tokens=10),
]

# Termination patterns - these terminate the scope of a trigger
SCOPE_TERMINATION_PATTERNS: set[str] = {
    "but",
    "however",
    "although",
    "except",
    "apart from",
    "aside from",
    "secondary to",
    "due to",
    "because of",
    "which",
    "that",
    ";",
    ":",
    ".",
}


@dataclass
class ProbabilisticAssertionClassifier:
    """Classifier for assertion detection with calibrated confidence scores.

    This classifier uses pattern matching with scope-aware triggers to detect
    assertions in clinical text. Confidence scores are calibrated based on
    clinical NLP literature.

    Attributes:
        default_confidence: Default confidence for present assertions (default: 0.85)
        max_scope_tokens: Maximum tokens between trigger and mention (default: 6)
        use_pseudo_negation: Whether to check for pseudo-negation patterns (default: True)
    """

    default_confidence: float = 0.85
    max_scope_tokens: int = 6
    use_pseudo_negation: bool = True

    # All triggers combined and sorted by pattern length (longest first for matching)
    _all_triggers: list[AssertionTrigger] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Initialize trigger patterns sorted by length."""
        all_triggers = (
            PSEUDO_NEGATION_TRIGGERS
            + ABSENT_TRIGGERS
            + UNCERTAIN_TRIGGERS
            + HYPOTHETICAL_TRIGGERS
            + PRESENT_TRIGGERS
        )
        # Sort by pattern length descending for longest-match-first
        self._all_triggers = sorted(all_triggers, key=lambda t: len(t.pattern), reverse=True)

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace tokenization with punctuation handling."""
        # Split on whitespace and keep punctuation attached
        tokens = text.lower().split()
        return tokens

    def _count_tokens_between(self, text: str, trigger_pos: int, mention_start: int, mention_end: int) -> int:
        """Count tokens between trigger and mention."""
        if trigger_pos < mention_start:
            # Trigger is before mention
            between_text = text[trigger_pos:mention_start]
        else:
            # Trigger is after mention
            between_text = text[mention_end:trigger_pos]
        return len(self._tokenize(between_text))

    def _find_trigger_in_scope(
        self,
        text: str,
        mention_start: int,
        mention_end: int,
        trigger: AssertionTrigger,
    ) -> tuple[int, int] | None:
        """Find a trigger pattern that is in scope of the mention.

        Returns:
            Tuple of (trigger_position, token_distance) if found, None otherwise.
        """
        text_lower = text.lower()
        trigger_pattern = trigger.pattern

        # Find all occurrences of the trigger
        pos = 0
        best_match = None
        best_distance = float("inf")

        while True:
            pos = text_lower.find(trigger_pattern, pos)
            if pos == -1:
                break

            trigger_end = pos + len(trigger_pattern)

            # Check scope direction
            in_scope = False
            if trigger.scope == TriggerScope.FORWARD:
                # Trigger must be before mention
                in_scope = trigger_end <= mention_start
            elif trigger.scope == TriggerScope.BACKWARD:
                # Trigger must be after mention
                in_scope = pos >= mention_end
            else:  # BIDIRECTIONAL
                in_scope = trigger_end <= mention_start or pos >= mention_end

            if in_scope:
                # Check token distance
                distance = self._count_tokens_between(text, pos if pos >= mention_end else trigger_end, mention_start, mention_end)

                # Check for scope termination patterns
                if trigger_end <= mention_start:
                    between_text = text_lower[trigger_end:mention_start]
                else:
                    between_text = text_lower[mention_end:pos]

                # Check if any termination pattern breaks the scope
                scope_terminated = any(term in between_text for term in SCOPE_TERMINATION_PATTERNS)

                if not scope_terminated and distance <= trigger.max_scope_tokens:
                    if distance < best_distance:
                        best_distance = distance
                        best_match = (pos, distance)

            pos += 1

        return best_match

    def classify(
        self,
        text: str,
        mention_start: int,
        mention_end: int,
    ) -> AssertionResult:
        """Classify the assertion status of a mention in clinical text.

        Args:
            text: The full clinical text containing the mention
            mention_start: Start character offset of the mention
            mention_end: End character offset of the mention

        Returns:
            AssertionResult with assertion type, confidence, and trigger info
        """
        text_lower = text.lower()

        # First check for pseudo-negation patterns (they override regular negation)
        if self.use_pseudo_negation:
            for trigger in PSEUDO_NEGATION_TRIGGERS:
                match = self._find_trigger_in_scope(text, mention_start, mention_end, trigger)
                if match is not None:
                    _, distance = match
                    assertion = Assertion.PRESENT if trigger.category == AssertionCategory.PRESENT else Assertion.POSSIBLE
                    return AssertionResult(
                        assertion=assertion,
                        confidence=trigger.confidence,
                        trigger_text=trigger.pattern,
                        trigger_distance=distance,
                        category=trigger.category,
                    )

        # Check all other triggers, tracking the best match by distance
        # Priority order for ties: ABSENT > UNCERTAIN > HYPOTHETICAL > PRESENT
        # This ensures negation takes precedence over affirmation at same distance
        CATEGORY_PRIORITY = {
            AssertionCategory.ABSENT: 0,
            AssertionCategory.UNCERTAIN: 1,
            AssertionCategory.HYPOTHETICAL: 2,
            AssertionCategory.PRESENT: 3,
        }

        best_result: AssertionResult | None = None
        best_distance = float("inf")
        best_priority = float("inf")

        for trigger in self._all_triggers:
            if trigger.is_pseudo:
                continue  # Already handled above

            match = self._find_trigger_in_scope(text, mention_start, mention_end, trigger)
            if match is not None:
                _, distance = match
                priority = CATEGORY_PRIORITY.get(trigger.category, 4)

                # Prefer closer triggers, then higher priority categories (lower number)
                if distance < best_distance or (distance == best_distance and priority < best_priority):
                    best_distance = distance
                    best_priority = priority

                    # Map category to Assertion enum
                    if trigger.category == AssertionCategory.ABSENT:
                        assertion = Assertion.ABSENT
                    elif trigger.category in (AssertionCategory.UNCERTAIN, AssertionCategory.HYPOTHETICAL):
                        assertion = Assertion.POSSIBLE
                    else:
                        assertion = Assertion.PRESENT

                    best_result = AssertionResult(
                        assertion=assertion,
                        confidence=trigger.confidence,
                        trigger_text=trigger.pattern,
                        trigger_distance=distance,
                        category=trigger.category,
                    )

        # If no trigger found, default to PRESENT with default confidence
        if best_result is None:
            return AssertionResult(
                assertion=Assertion.PRESENT,
                confidence=self.default_confidence,
                trigger_text=None,
                trigger_distance=None,
                category=AssertionCategory.PRESENT,
            )

        return best_result

    def classify_batch(
        self,
        text: str,
        mentions: list[tuple[int, int]],
    ) -> list[AssertionResult]:
        """Classify assertions for multiple mentions in the same text.

        Args:
            text: The full clinical text
            mentions: List of (start, end) character offsets for each mention

        Returns:
            List of AssertionResult for each mention
        """
        return [self.classify(text, start, end) for start, end in mentions]


# Module-level singleton for convenience
_default_classifier: ProbabilisticAssertionClassifier | None = None
_classifier_lock = threading.Lock()


def get_classifier() -> ProbabilisticAssertionClassifier:
    """Get the default assertion classifier singleton."""
    global _default_classifier
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _default_classifier is None:
        with _classifier_lock:
            if _default_classifier is None:
                _default_classifier = ProbabilisticAssertionClassifier()
    return _default_classifier


def classify_assertion(
    text: str,
    mention_start: int,
    mention_end: int,
) -> AssertionResult:
    """Convenience function to classify a single mention.

    Args:
        text: The full clinical text containing the mention
        mention_start: Start character offset of the mention
        mention_end: End character offset of the mention

    Returns:
        AssertionResult with assertion type, confidence, and trigger info
    """
    return get_classifier().classify(text, mention_start, mention_end)
