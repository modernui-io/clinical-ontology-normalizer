"""Date parser utility for extracting dates from clinical text.

Handles various date formats commonly found in clinical documentation:
- MM/DD/YYYY, YYYY-MM-DD (standard formats)
- "March 15, 2023" (month name formats)
- Relative dates: "3 days ago", "last week"
- Clinical context: "diagnosed on DATE", "since DATE"
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import NamedTuple

logger = logging.getLogger(__name__)


class ParsedDate(NamedTuple):
    """Result of date parsing."""

    date: datetime | None
    original_text: str
    date_type: str  # "absolute", "relative", "partial"
    confidence: float


# Month name mappings
MONTH_MAP = {
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

# Date patterns with named groups for parsing
DATE_PATTERNS = [
    # MM/DD/YYYY or MM-DD-YYYY
    (r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", "mdy_full"),
    # MM/DD/YY or MM-DD-YY
    (r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})(?!\d)", "mdy_short"),
    # YYYY-MM-DD (ISO format)
    (r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", "ymd"),
    # Month DD, YYYY (e.g., "March 15, 2023")
    (r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", "month_name_full"),
    # DD Month YYYY (e.g., "15 March 2023")
    (r"(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?,?\s+(\d{4})", "day_month_full"),
    # Month YYYY (partial date)
    (r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+(\d{4})", "month_year"),
]

# Relative date patterns
RELATIVE_PATTERNS = [
    # N days/weeks/months/years ago
    (r"(\d+)\s*(days?|weeks?|months?|years?)\s+ago", "relative_ago"),
    # last week/month/year
    (r"last\s+(week|month|year)", "last_period"),
    # yesterday/today
    (r"\b(yesterday|today)\b", "relative_day"),
]


def parse_date(text: str, reference_date: datetime | None = None) -> ParsedDate | None:
    """Parse a date string into a datetime object.

    Args:
        text: Text containing a date to parse.
        reference_date: Reference date for relative dates (defaults to now).

    Returns:
        ParsedDate with the parsed datetime, or None if no date found.
    """
    if not text:
        return None

    text_lower = text.lower().strip()
    ref_date = reference_date or datetime.now()

    # Try absolute date patterns first
    for pattern, pattern_type in DATE_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            try:
                parsed = _parse_absolute_date(match, pattern_type, ref_date)
                if parsed:
                    return ParsedDate(
                        date=parsed,
                        original_text=match.group(0),
                        date_type="absolute" if "partial" not in pattern_type else "partial",
                        confidence=0.95,
                    )
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse date '{match.group(0)}': {e}")
                continue

    # Try relative date patterns
    for pattern, pattern_type in RELATIVE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            try:
                parsed = _parse_relative_date(match, pattern_type, ref_date)
                if parsed:
                    return ParsedDate(
                        date=parsed,
                        original_text=match.group(0),
                        date_type="relative",
                        confidence=0.8,  # Lower confidence for relative dates
                    )
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse relative date '{match.group(0)}': {e}")
                continue

    return None


def _parse_absolute_date(match: re.Match, pattern_type: str, ref_date: datetime) -> datetime | None:
    """Parse an absolute date match."""
    groups = match.groups()

    if pattern_type == "mdy_full":
        # MM/DD/YYYY
        month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
    elif pattern_type == "mdy_short":
        # MM/DD/YY - assume 20XX for years < 50, 19XX otherwise
        month, day = int(groups[0]), int(groups[1])
        year = int(groups[2])
        year = 2000 + year if year < 50 else 1900 + year
    elif pattern_type == "ymd":
        # YYYY-MM-DD
        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
    elif pattern_type == "month_name_full":
        # Month DD, YYYY
        month = MONTH_MAP.get(groups[0].lower())
        if month is None:
            return None
        day, year = int(groups[1]), int(groups[2])
    elif pattern_type == "day_month_full":
        # DD Month YYYY
        day = int(groups[0])
        month = MONTH_MAP.get(groups[1].lower())
        if month is None:
            return None
        year = int(groups[2])
    elif pattern_type == "month_year":
        # Month YYYY (partial - use first of month)
        month = MONTH_MAP.get(groups[0].lower())
        if month is None:
            return None
        year = int(groups[1])
        day = 1
    else:
        return None

    # Validate and create datetime
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
        return None

    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_relative_date(match: re.Match, pattern_type: str, ref_date: datetime) -> datetime | None:
    """Parse a relative date match."""
    groups = match.groups()

    if pattern_type == "relative_ago":
        # N days/weeks/months/years ago
        amount = int(groups[0])
        unit = groups[1].rstrip("s")  # Remove plural

        if unit == "day":
            return ref_date - timedelta(days=amount)
        elif unit == "week":
            return ref_date - timedelta(weeks=amount)
        elif unit == "month":
            # Approximate month as 30 days
            return ref_date - timedelta(days=amount * 30)
        elif unit == "year":
            # Approximate year as 365 days
            return ref_date - timedelta(days=amount * 365)

    elif pattern_type == "last_period":
        # last week/month/year
        unit = groups[0]
        if unit == "week":
            return ref_date - timedelta(weeks=1)
        elif unit == "month":
            return ref_date - timedelta(days=30)
        elif unit == "year":
            return ref_date - timedelta(days=365)

    elif pattern_type == "relative_day":
        # yesterday/today
        word = groups[0]
        if word == "yesterday":
            return ref_date - timedelta(days=1)
        elif word == "today":
            return ref_date

    return None


def extract_event_date(text: str, reference_date: datetime | None = None) -> ParsedDate | None:
    """Extract an event date from clinical text with context.

    Looks for date patterns in context of clinical event phrases like:
    - "diagnosed on DATE"
    - "resulted on DATE"
    - "started DATE"
    - "since DATE"

    Args:
        text: Clinical text to search.
        reference_date: Reference date for relative dates.

    Returns:
        ParsedDate if found, None otherwise.
    """
    # Event context patterns with capturing group for the date portion
    event_patterns = [
        (r"(?:diagnosed|dx|discovered)(?:\s+with\s+\w+)?(?:\s+on\s+|\s+)(.+?)(?:\.|,|$|\s+and\s+|\s+with\s+)", "diagnosis_date"),
        (r"(?:resulted|reported|resulted\s+on)(?:\s+on\s+|\s+)(.+?)(?:\.|,|$|\s+showing)", "result_date"),
        (r"(?:started|began|initiated|commenced)(?:\s+on\s+|\s+)(.+?)(?:\.|,|$|\s+and\s+|\s+with\s+|\s+taking)", "start_date"),
        (r"(?:since\s+)(.+?)(?:\.|,|$|\s+and\s+|\s+with\s+)", "since_date"),
        (r"(?:on\s+)(.+?)(?:\s+(?:patient|pt|he|she|they)\s+)", "on_date"),
    ]

    for pattern, _context_type in event_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_portion = match.group(1).strip()
            # Try to parse the captured portion
            parsed = parse_date(date_portion, reference_date)
            if parsed:
                return parsed

    # Fallback: just look for any date in the text
    return parse_date(text, reference_date)
