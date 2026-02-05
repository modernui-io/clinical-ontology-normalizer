"""Temporal extraction service for clinical text.

Extracts dates and temporal expressions from clinical notes and associates
them with nearby entities. Supports:

1. Absolute dates: "1/15/2024", "January 15, 2024", "2024-01-15"
2. Partial dates: "in 2020", "March 2023"
3. Relative expressions: "3 days ago", "last week", "since January"
4. Temporal keywords: "diagnosed", "started", "stopped", "since"

Phase 4 of the Ontology Relationships implementation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TemporalExpression:
    """A temporal expression extracted from text."""

    text: str  # Original text span
    start: int  # Character offset start
    end: int  # Character offset end
    date: datetime | None  # Resolved date (if possible)
    date_precision: str  # "day", "month", "year", "approximate"
    expression_type: str  # "absolute", "relative", "keyword"
    confidence: float  # Extraction confidence


@dataclass
class EntityTemporalBinding:
    """Binding between an entity and a temporal expression."""

    entity_text: str
    entity_start: int
    entity_end: int
    temporal_expression: TemporalExpression
    relationship: str  # "onset", "started", "stopped", "diagnosed", "during"
    distance: int  # Character distance between entity and temporal


# Month name mappings
MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Patterns for temporal expressions
TEMPORAL_PATTERNS = [
    # ISO format: 2024-01-15
    (
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
        "absolute",
        "day",
        lambda m, ref: _parse_ymd(m.group(1), m.group(2), m.group(3)),
    ),
    # US format: 1/15/2024 or 01/15/2024
    (
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        "absolute",
        "day",
        lambda m, ref: _parse_mdy(m.group(1), m.group(2), m.group(3)),
    ),
    # US format short year: 1/15/24
    (
        r"\b(\d{1,2})/(\d{1,2})/(\d{2})\b",
        "absolute",
        "day",
        lambda m, ref: _parse_mdy(m.group(1), m.group(2), m.group(3)),
    ),
    # Month Day, Year: January 15, 2024 or Jan 15 2024
    (
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})\b",
        "absolute",
        "day",
        lambda m, ref: _parse_month_day_year(m.group(1), m.group(2), m.group(3)),
    ),
    # Day Month Year: 15 January 2024
    (
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec),?\s*(\d{4})\b",
        "absolute",
        "day",
        lambda m, ref: _parse_day_month_year(m.group(1), m.group(2), m.group(3)),
    ),
    # Month Year: January 2024, March 2023
    (
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{4})\b",
        "absolute",
        "month",
        lambda m, ref: _parse_month_year(m.group(1), m.group(2)),
    ),
    # Year only: in 2020, since 2019
    (
        r"\b(?:in|since|during|around)\s+(\d{4})\b",
        "absolute",
        "year",
        lambda m, ref: _parse_year(m.group(1)),
    ),
    # Just year at sentence boundary or with context
    (
        r"\b(\d{4})\b(?=\s*[,.\)]|\s+(?:when|after|before|following))",
        "absolute",
        "year",
        lambda m, ref: _parse_year(m.group(1)),
    ),
    # Relative: X days/weeks/months/years ago
    (
        r"\b(\d+)\s+(day|days|week|weeks|month|months|year|years)\s+ago\b",
        "relative",
        "approximate",
        lambda m, ref: _parse_relative_ago(m.group(1), m.group(2), ref),
    ),
    # Relative: last week/month/year
    (
        r"\blast\s+(week|month|year)\b",
        "relative",
        "approximate",
        lambda m, ref: _parse_last_period(m.group(1), ref),
    ),
    # Relative: this week/month/year
    (
        r"\bthis\s+(week|month|year)\b",
        "relative",
        "approximate",
        lambda m, ref: _parse_this_period(m.group(1), ref),
    ),
]

# Temporal relationship keywords that associate dates with entities
TEMPORAL_RELATIONSHIP_PATTERNS = [
    # "diagnosed with X in/on DATE"
    (r"\bdiagnosed\s+(?:with\s+)?(.+?)\s+(?:in|on)\s+", "diagnosed", "before"),
    # "started X on DATE"
    (r"\bstarted\s+(?:on\s+)?(.+?)\s+(?:on|in)\s+", "started", "before"),
    # "began X in/on DATE"
    (r"\bbegan\s+(.+?)\s+(?:in|on)\s+", "started", "before"),
    # "X since DATE"
    (r"(.+?)\s+since\s+", "onset", "after"),
    # "stopped X on DATE"
    (r"\bstopped\s+(.+?)\s+(?:on|in)\s+", "stopped", "before"),
    # "discontinued X on DATE"
    (r"\bdiscontinued\s+(.+?)\s+(?:on|in)\s+", "stopped", "before"),
    # "X for N years/months" (duration, not date)
    (r"(.+?)\s+for\s+\d+\s+(?:year|month|week|day)s?\b", "duration", "before"),
]


def _parse_ymd(year: str, month: str, day: str) -> datetime | None:
    """Parse YYYY-MM-DD format."""
    try:
        return datetime(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return None


def _parse_mdy(month: str, day: str, year: str) -> datetime | None:
    """Parse M/D/YYYY or M/D/YY format."""
    try:
        y = int(year)
        if y < 100:
            # Two-digit year - assume 20xx for 00-29, 19xx for 30-99
            y = 2000 + y if y < 30 else 1900 + y
        return datetime(y, int(month), int(day))
    except (ValueError, TypeError):
        return None


def _parse_month_day_year(month_name: str, day: str, year: str) -> datetime | None:
    """Parse 'January 15, 2024' format."""
    try:
        month = MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None
        return datetime(int(year), month, int(day))
    except (ValueError, TypeError):
        return None


def _parse_day_month_year(day: str, month_name: str, year: str) -> datetime | None:
    """Parse '15 January 2024' format."""
    try:
        month = MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None
        return datetime(int(year), month, int(day))
    except (ValueError, TypeError):
        return None


def _parse_month_year(month_name: str, year: str) -> datetime | None:
    """Parse 'January 2024' format (returns first of month)."""
    try:
        month = MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None
        return datetime(int(year), month, 1)
    except (ValueError, TypeError):
        return None


def _parse_year(year: str) -> datetime | None:
    """Parse year only (returns January 1 of that year)."""
    try:
        y = int(year)
        # Sanity check - reasonable date range for clinical notes
        if 1900 <= y <= 2100:
            return datetime(y, 1, 1)
        return None
    except (ValueError, TypeError):
        return None


def _parse_relative_ago(amount: str, unit: str, reference: datetime) -> datetime | None:
    """Parse 'X days/weeks/months/years ago' relative to reference date."""
    try:
        n = int(amount)
        unit_lower = unit.lower().rstrip("s")  # Normalize: "days" -> "day"

        if unit_lower == "day":
            return reference - timedelta(days=n)
        elif unit_lower == "week":
            return reference - timedelta(weeks=n)
        elif unit_lower == "month":
            # Approximate month as 30 days
            return reference - timedelta(days=n * 30)
        elif unit_lower == "year":
            # Approximate year as 365 days
            return reference - timedelta(days=n * 365)
        return None
    except (ValueError, TypeError):
        return None


def _parse_last_period(period: str, reference: datetime) -> datetime | None:
    """Parse 'last week/month/year' relative to reference date."""
    period_lower = period.lower()

    if period_lower == "week":
        return reference - timedelta(weeks=1)
    elif period_lower == "month":
        return reference - timedelta(days=30)
    elif period_lower == "year":
        return reference - timedelta(days=365)
    return None


def _parse_this_period(period: str, reference: datetime) -> datetime | None:
    """Parse 'this week/month/year' - returns start of current period."""
    period_lower = period.lower()

    if period_lower == "week":
        # Start of current week (Monday)
        days_since_monday = reference.weekday()
        return reference - timedelta(days=days_since_monday)
    elif period_lower == "month":
        return datetime(reference.year, reference.month, 1)
    elif period_lower == "year":
        return datetime(reference.year, 1, 1)
    return None


class TemporalExtractor:
    """Extracts temporal expressions from clinical text."""

    def __init__(self, reference_date: datetime | None = None):
        """Initialize the temporal extractor.

        Args:
            reference_date: Reference date for relative expressions.
                           Defaults to current date if not provided.
        """
        self.reference_date = reference_date or datetime.now()
        # Compile patterns for efficiency
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), expr_type, precision, parser)
            for pattern, expr_type, precision, parser in TEMPORAL_PATTERNS
        ]

    def extract_temporal_expressions(self, text: str) -> list[TemporalExpression]:
        """Extract all temporal expressions from text.

        Args:
            text: Clinical note text

        Returns:
            List of TemporalExpression objects
        """
        expressions = []
        seen_spans = set()  # Avoid duplicate extractions

        for pattern, expr_type, precision, parser in self._compiled_patterns:
            for match in pattern.finditer(text):
                span = (match.start(), match.end())

                # Skip if we already extracted this span
                if span in seen_spans:
                    continue

                # Skip if this span overlaps with an existing extraction
                overlaps = False
                for existing_start, existing_end in seen_spans:
                    if not (match.end() <= existing_start or match.start() >= existing_end):
                        overlaps = True
                        break
                if overlaps:
                    continue

                # Parse the date
                date = parser(match, self.reference_date)

                # Calculate confidence based on precision and parse success
                confidence = 0.9 if date else 0.5
                if precision == "approximate":
                    confidence *= 0.8
                elif precision == "year":
                    confidence *= 0.85
                elif precision == "month":
                    confidence *= 0.9

                expressions.append(
                    TemporalExpression(
                        text=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        date=date,
                        date_precision=precision,
                        expression_type=expr_type,
                        confidence=confidence,
                    )
                )
                seen_spans.add(span)

        # Sort by position in text
        expressions.sort(key=lambda e: e.start)
        return expressions

    def bind_entities_to_temporals(
        self,
        text: str,
        entities: list[dict[str, Any]],
        temporal_expressions: list[TemporalExpression] | None = None,
        max_distance: int = 100,
    ) -> list[EntityTemporalBinding]:
        """Associate entities with nearby temporal expressions.

        Uses proximity and relationship keywords to bind entities to dates.

        Args:
            text: Original text
            entities: List of extracted entities with 'text', 'start', 'end' keys
            temporal_expressions: Pre-extracted temporal expressions (optional)
            max_distance: Maximum character distance to consider

        Returns:
            List of EntityTemporalBinding objects
        """
        if temporal_expressions is None:
            temporal_expressions = self.extract_temporal_expressions(text)

        if not temporal_expressions or not entities:
            return []

        bindings = []

        for entity in entities:
            entity_text = entity.get("text", "")
            entity_start = entity.get("start", 0)
            entity_end = entity.get("end", len(entity_text))

            best_binding = None
            best_distance = max_distance + 1

            for temporal in temporal_expressions:
                # Calculate distance (minimum gap between spans)
                if temporal.end <= entity_start:
                    distance = entity_start - temporal.end
                elif temporal.start >= entity_end:
                    distance = temporal.start - entity_end
                else:
                    distance = 0  # Overlapping

                if distance > max_distance:
                    continue

                # Determine relationship based on context
                relationship = self._determine_relationship(
                    text, entity_start, entity_end, temporal.start, temporal.end
                )

                if distance < best_distance:
                    best_distance = distance
                    best_binding = EntityTemporalBinding(
                        entity_text=entity_text,
                        entity_start=entity_start,
                        entity_end=entity_end,
                        temporal_expression=temporal,
                        relationship=relationship,
                        distance=distance,
                    )

            if best_binding:
                bindings.append(best_binding)

        return bindings

    def _determine_relationship(
        self,
        text: str,
        entity_start: int,
        entity_end: int,
        temporal_start: int,
        temporal_end: int,
    ) -> str:
        """Determine the relationship between entity and temporal expression."""
        # Get context window around the entity-temporal pair
        window_start = max(0, min(entity_start, temporal_start) - 30)
        window_end = min(len(text), max(entity_end, temporal_end) + 10)
        context = text[window_start:window_end].lower()

        # Check for relationship keywords
        if "diagnosed" in context:
            return "diagnosed"
        elif "started" in context or "began" in context or "initiated" in context:
            return "started"
        elif "stopped" in context or "discontinued" in context:
            return "stopped"
        elif "since" in context:
            return "onset"
        elif "for" in context and ("year" in context or "month" in context):
            return "duration"
        else:
            return "during"  # Default relationship


def extract_entity_dates(
    text: str,
    entities: list[dict[str, Any]],
    document_date: datetime | None = None,
) -> dict[str, datetime | None]:
    """Convenience function to extract dates for entities.

    Args:
        text: Clinical note text
        entities: List of entities with 'text', 'start', 'end' keys
        document_date: Document date for reference (used for relative dates)

    Returns:
        Dict mapping entity text to extracted date (or None if no date found)
    """
    extractor = TemporalExtractor(reference_date=document_date or datetime.now())

    # Extract temporal expressions
    temporals = extractor.extract_temporal_expressions(text)

    # Bind entities to temporals
    bindings = extractor.bind_entities_to_temporals(text, entities, temporals)

    # Build result dict
    result: dict[str, datetime | None] = {}
    for binding in bindings:
        # Only include if we have a resolved date
        if binding.temporal_expression.date:
            result[binding.entity_text] = binding.temporal_expression.date

    return result
