"""Service for extracting clinical values from text.

Extracts quantitative clinical data:
- Lab results: HbA1c 7.2%, Creatinine 1.8 mg/dL
- Vital signs: BP 145/92, HR 88, Temp 101.2F
- Medication doses: Metformin 1000mg BID
- Measurements: EF 35%, BMI 32

Uses regex patterns with medical unit normalization and OMOP concept linking.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Sequence
from uuid import UUID

from app.models.clinical_value import ValueType

logger = logging.getLogger(__name__)


@dataclass
class ExtractedValue:
    """A single extracted clinical value."""

    text: str
    start_offset: int
    end_offset: int
    name: str
    value_type: ValueType
    value: float | None = None
    value_secondary: float | None = None
    unit: str | None = None
    unit_normalized: str | None = None
    frequency: str | None = None
    route: str | None = None
    omop_concept_id: int | None = None
    confidence: float = 0.8
    section: str | None = None


# OMOP concept IDs for common measurements
MEASUREMENT_CONCEPTS = {
    # Vitals
    "bp": 3012888,  # Blood pressure
    "systolic": 3004249,
    "diastolic": 3012888,
    "hr": 3027018,  # Heart rate
    "pulse": 3027018,
    "rr": 3024171,  # Respiratory rate
    "temp": 3020891,  # Body temperature
    "temperature": 3020891,
    "o2": 3016502,  # Oxygen saturation
    "spo2": 3016502,
    "o2 sat": 3016502,
    "sat": 3016502,
    "weight": 3025315,
    "height": 3036277,
    "bmi": 3038553,

    # Labs - Chemistry
    "glucose": 3004501,
    "sodium": 3019550,
    "na": 3019550,
    "potassium": 3023103,
    "k": 3023103,
    "chloride": 3014576,
    "cl": 3014576,
    "co2": 3015632,
    "bicarbonate": 3015632,
    "bun": 3013682,
    "creatinine": 3016723,
    "cr": 3016723,
    "egfr": 3049187,
    "calcium": 3006906,
    "ca": 3006906,
    "magnesium": 3001420,
    "mg": 3001420,
    "phosphorus": 3011904,
    "phos": 3011904,

    # Labs - Liver
    "ast": 3013721,
    "sgot": 3013721,
    "alt": 3006923,
    "sgpt": 3006923,
    "alp": 3035995,
    "alkaline phosphatase": 3035995,
    "bilirubin": 3024128,
    "total bilirubin": 3024128,
    "direct bilirubin": 3007220,
    "albumin": 3024561,
    "total protein": 3020630,

    # Labs - CBC
    "wbc": 3010813,
    "rbc": 3020416,
    "hemoglobin": 3000963,
    "hgb": 3000963,
    "hematocrit": 3009542,
    "hct": 3009542,
    "platelets": 3024929,
    "plt": 3024929,
    "mcv": 3023599,
    "mch": 3012030,
    "mchc": 3009744,
    "rdw": 3002888,

    # Labs - Coagulation
    "pt": 3034426,
    "inr": 3022217,
    "ptt": 3013466,
    "aptt": 3013466,
    "fibrinogen": 3005785,

    # Labs - Cardiac
    "troponin": 3025232,
    "trop": 3025232,
    "bnp": 3029435,
    "nt-probnp": 3029435,
    "ck": 3019170,
    "ck-mb": 3001582,

    # Labs - Diabetes
    "hba1c": 3004410,
    "a1c": 3004410,
    "hemoglobin a1c": 3004410,

    # Labs - Thyroid
    "tsh": 3016251,
    "t4": 3026300,
    "free t4": 3026300,
    "t3": 3005949,

    # Labs - Lipids
    "cholesterol": 3027114,
    "total cholesterol": 3027114,
    "ldl": 3028437,
    "hdl": 3011884,
    "triglycerides": 3022192,
    "tg": 3022192,

    # Labs - Urinalysis
    "ph": 3015736,
    "specific gravity": 3016436,

    # Cardiac measurements
    "ef": 3027694,  # Ejection fraction
    "lvef": 3027694,
    "ejection fraction": 3027694,
}

# Unit normalization mapping
UNIT_NORMALIZATION = {
    # Mass
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "mcg": "mcg",
    "microgram": "mcg",
    "micrograms": "mcg",
    "ug": "mcg",
    "kg": "kg",
    "kilogram": "kg",

    # Volume
    "ml": "mL",
    "milliliter": "mL",
    "milliliters": "mL",
    "l": "L",
    "liter": "L",
    "liters": "L",
    "dl": "dL",
    "deciliter": "dL",

    # Concentration
    "mg/dl": "mg/dL",
    "mg/l": "mg/L",
    "mmol/l": "mmol/L",
    "meq/l": "mEq/L",
    "meq/l": "mEq/L",
    "g/dl": "g/dL",
    "ng/ml": "ng/mL",
    "pg/ml": "pg/mL",
    "iu/l": "IU/L",
    "u/l": "U/L",
    "iu/ml": "IU/mL",

    # Count
    "cells/ul": "cells/uL",
    "/ul": "/uL",
    "k/ul": "K/uL",
    "x10^3/ul": "K/uL",
    "x10^6/ul": "M/uL",
    "m/ul": "M/uL",
    "x10^9/l": "x10^9/L",
    "x10^12/l": "x10^12/L",

    # Percentage
    "%": "%",
    "percent": "%",

    # Temperature
    "f": "°F",
    "°f": "°F",
    "fahrenheit": "°F",
    "c": "°C",
    "°c": "°C",
    "celsius": "°C",

    # Pressure
    "mmhg": "mmHg",
    "mm hg": "mmHg",

    # Rate
    "bpm": "bpm",
    "/min": "/min",
    "per minute": "/min",
    "breaths/min": "/min",
}

# Frequency normalization
FREQUENCY_PATTERNS = {
    r"\bqd\b": "daily",
    r"\bdaily\b": "daily",
    r"\bonce daily\b": "daily",
    r"\bqhs\b": "at bedtime",
    r"\bhs\b": "at bedtime",
    r"\bbid\b": "twice daily",
    r"\btwice daily\b": "twice daily",
    r"\bb\.i\.d\.?\b": "twice daily",
    r"\btid\b": "three times daily",
    r"\bthree times daily\b": "three times daily",
    r"\bt\.i\.d\.?\b": "three times daily",
    r"\bqid\b": "four times daily",
    r"\bfour times daily\b": "four times daily",
    r"\bq\.i\.d\.?\b": "four times daily",
    r"\bprn\b": "as needed",
    r"\bas needed\b": "as needed",
    r"\bq(\d+)h\b": r"every \1 hours",
    r"\bevery (\d+) hours?\b": r"every \1 hours",
    r"\bweekly\b": "weekly",
    r"\bqweek\b": "weekly",
    r"\bmonthly\b": "monthly",
    r"\bqmonth\b": "monthly",
}

# Route patterns
ROUTE_PATTERNS = {
    r"\bpo\b": "oral",
    r"\boral\b": "oral",
    r"\bby mouth\b": "oral",
    r"\biv\b": "intravenous",
    r"\bintravenous\b": "intravenous",
    r"\bim\b": "intramuscular",
    r"\bintramuscular\b": "intramuscular",
    r"\bsc\b": "subcutaneous",
    r"\bsubq\b": "subcutaneous",
    r"\bsubcutaneous\b": "subcutaneous",
    r"\bsl\b": "sublingual",
    r"\bsublingual\b": "sublingual",
    r"\btopical\b": "topical",
    r"\binhaled\b": "inhaled",
    r"\binh\b": "inhaled",
    r"\bnasal\b": "nasal",
    r"\brectal\b": "rectal",
    r"\bpr\b": "rectal",
    r"\bophthalmic\b": "ophthalmic",
    r"\botic\b": "otic",
    r"\btransdermal\b": "transdermal",
    r"\bpatch\b": "transdermal",
}


@dataclass
class ValueExtractionService:
    """Service for extracting clinical values from text."""

    # Compiled regex patterns (lazy init)
    _vital_patterns: list[tuple[re.Pattern, str, str | None]] = field(
        default_factory=list, repr=False
    )
    _lab_patterns: list[tuple[re.Pattern, str, str | None]] = field(
        default_factory=list, repr=False
    )
    _med_patterns: list[tuple[re.Pattern, str]] = field(
        default_factory=list, repr=False
    )
    _measurement_patterns: list[tuple[re.Pattern, str, str | None]] = field(
        default_factory=list, repr=False
    )
    _initialized: bool = False

    def _initialize(self) -> None:
        """Initialize regex patterns."""
        if self._initialized:
            return

        # Vital sign patterns
        self._vital_patterns = [
            # Blood pressure: BP 145/92, 145/92 mmHg
            (
                re.compile(
                    r"\b(?:bp|blood pressure)\s*[:=]?\s*(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mmhg|mm hg)?",
                    re.IGNORECASE,
                ),
                "Blood Pressure",
                "mmHg",
            ),
            # Standalone BP values
            (
                re.compile(
                    r"(?<!\d)(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mmhg|mm hg)",
                    re.IGNORECASE,
                ),
                "Blood Pressure",
                "mmHg",
            ),
            # Heart rate: HR 88, pulse 88 bpm
            (
                re.compile(
                    r"\b(?:hr|heart rate|pulse)\s*[:=]?\s*(\d{2,3})\s*(?:bpm|/min)?",
                    re.IGNORECASE,
                ),
                "Heart Rate",
                "bpm",
            ),
            # Respiratory rate: RR 18, resp rate 18
            (
                re.compile(
                    r"\b(?:rr|resp(?:iratory)? rate)\s*[:=]?\s*(\d{1,2})\s*(?:/min|breaths?/min)?",
                    re.IGNORECASE,
                ),
                "Respiratory Rate",
                "/min",
            ),
            # Temperature: Temp 101.2F, 98.6°F
            (
                re.compile(
                    r"\b(?:temp(?:erature)?)\s*[:=]?\s*(\d{2,3}(?:\.\d)?)\s*(?:°?\s*[fc]|fahrenheit|celsius)?",
                    re.IGNORECASE,
                ),
                "Temperature",
                "°F",
            ),
            # O2 saturation: O2 sat 94%, SpO2 94%
            (
                re.compile(
                    r"\b(?:o2\s*sat(?:uration)?|spo2|sao2|oxygen sat(?:uration)?)\s*[:=]?\s*(\d{2,3})\s*%?",
                    re.IGNORECASE,
                ),
                "Oxygen Saturation",
                "%",
            ),
            # Weight: Weight 70 kg, Wt 154 lbs
            (
                re.compile(
                    r"\b(?:weight|wt)\s*[:=]?\s*(\d{2,3}(?:\.\d)?)\s*(kg|lbs?|pounds?|kilograms?)?",
                    re.IGNORECASE,
                ),
                "Weight",
                None,  # Unit captured in pattern
            ),
            # Height: Height 5'10", Ht 170 cm
            (
                re.compile(
                    r"\b(?:height|ht)\s*[:=]?\s*(\d{1,3}(?:\.\d)?)\s*(cm|in|inches|m|feet|ft)?",
                    re.IGNORECASE,
                ),
                "Height",
                None,
            ),
            # BMI: BMI 32
            (
                re.compile(
                    r"\b(?:bmi)\s*[:=]?\s*(\d{1,2}(?:\.\d)?)",
                    re.IGNORECASE,
                ),
                "BMI",
                "kg/m²",
            ),
        ]

        # Lab result patterns
        self._lab_patterns = [
            # Generic lab: Name value unit (e.g., Creatinine 1.8 mg/dL)
            (
                re.compile(
                    r"\b(hemoglobin|hgb|hematocrit|hct|wbc|rbc|platelets?|plt|"
                    r"sodium|na|potassium|k|chloride|cl|co2|bicarbonate|"
                    r"bun|creatinine|cr|glucose|calcium|ca|magnesium|mg|phosphorus|phos|"
                    r"ast|sgot|alt|sgpt|alp|alkaline phosphatase|bilirubin|albumin|"
                    r"total protein|pt|inr|ptt|aptt|fibrinogen|"
                    r"troponin|trop|bnp|nt-probnp|ck|ck-mb|"
                    r"tsh|t4|free t4|t3|"
                    r"cholesterol|ldl|hdl|triglycerides|tg|"
                    r"hba1c|a1c|hemoglobin a1c|egfr)"
                    r"\s*[:=]?\s*"
                    r"(\d+(?:\.\d+)?)\s*"
                    r"(mg/dl|mg/l|mmol/l|meq/l|g/dl|ng/ml|pg/ml|iu/l|u/l|"
                    r"k/ul|m/ul|x10\^?[369]/[ul]l?|cells?/ul|/ul|"
                    r"%|seconds?|sec|s)?",
                    re.IGNORECASE,
                ),
                None,  # Name captured in pattern
                None,  # Unit captured in pattern
            ),
            # HbA1c specific: A1c 7.2%
            (
                re.compile(
                    r"\b(?:hba1c|a1c|hemoglobin a1c)\s*[:=]?\s*(\d+(?:\.\d)?)\s*%?",
                    re.IGNORECASE,
                ),
                "HbA1c",
                "%",
            ),
            # eGFR: eGFR >60, eGFR 45
            (
                re.compile(
                    r"\begfr\s*[:=]?\s*[<>]?\s*(\d+(?:\.\d)?)\s*(?:ml/min)?",
                    re.IGNORECASE,
                ),
                "eGFR",
                "mL/min/1.73m²",
            ),
            # INR: INR 2.3
            (
                re.compile(
                    r"\binr\s*[:=]?\s*(\d+(?:\.\d)?)",
                    re.IGNORECASE,
                ),
                "INR",
                None,
            ),
        ]

        # Measurement patterns (cardiac, etc.)
        self._measurement_patterns = [
            # Ejection fraction: EF 35%, LVEF 40%
            (
                re.compile(
                    r"\b(?:ef|lvef|ejection fraction)\s*[:=]?\s*(\d{1,2}(?:\.\d)?)\s*%?",
                    re.IGNORECASE,
                ),
                "Ejection Fraction",
                "%",
            ),
        ]

        # Medication dose patterns
        self._med_patterns = [
            # Drug dose frequency: Metformin 1000mg BID
            (
                re.compile(
                    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+"  # Drug name
                    r"(\d+(?:\.\d+)?)\s*"  # Dose
                    r"(mg|mcg|g|ml|units?|iu)\s*"  # Unit
                    r"(?:(po|iv|im|sc|subq|sl|pr|topical|inhaled?|inh|patch)\s*)?"  # Route
                    r"(qd|daily|bid|tid|qid|q\d+h|prn|"
                    r"once daily|twice daily|three times daily|four times daily|"
                    r"every \d+ hours?|as needed|weekly|monthly|at bedtime|hs|qhs)?",  # Frequency
                    re.IGNORECASE,
                ),
                None,  # Name from pattern
            ),
            # Simpler: Drug dose (Aspirin 81mg)
            (
                re.compile(
                    r"\b([A-Z][a-z]+)\s+(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|units?|iu)",
                    re.IGNORECASE,
                ),
                None,
            ),
        ]

        self._initialized = True

    def _normalize_unit(self, unit: str | None) -> str | None:
        """Normalize a unit to standard form."""
        if not unit:
            return None
        unit_lower = unit.lower().strip()
        return UNIT_NORMALIZATION.get(unit_lower, unit)

    def _extract_frequency(self, text: str) -> str | None:
        """Extract medication frequency from text."""
        text_lower = text.lower()
        for pattern, freq in FREQUENCY_PATTERNS.items():
            match = re.search(pattern, text_lower)
            if match:
                if r"\1" in freq:
                    return re.sub(pattern, freq, match.group(0))
                return freq
        return None

    def _extract_route(self, text: str) -> str | None:
        """Extract medication route from text."""
        text_lower = text.lower()
        for pattern, route in ROUTE_PATTERNS.items():
            if re.search(pattern, text_lower):
                return route
        return None

    def _get_concept_id(self, name: str) -> int | None:
        """Get OMOP concept ID for a measurement name."""
        name_lower = name.lower().strip()
        return MEASUREMENT_CONCEPTS.get(name_lower)

    def extract_vitals(self, text: str, offset: int = 0) -> list[ExtractedValue]:
        """Extract vital signs from text."""
        self._initialize()
        results = []

        for pattern, name, default_unit in self._vital_patterns:
            for match in pattern.finditer(text):
                try:
                    # Handle BP (two values)
                    if "Blood Pressure" in name:
                        value = float(match.group(1))
                        value_secondary = float(match.group(2))
                        unit = default_unit
                    else:
                        value = float(match.group(1))
                        value_secondary = None
                        # Try to get unit from match or use default
                        unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else default_unit

                    results.append(ExtractedValue(
                        text=match.group(0),
                        start_offset=offset + match.start(),
                        end_offset=offset + match.end(),
                        name=name,
                        value_type=ValueType.VITAL_SIGN,
                        value=value,
                        value_secondary=value_secondary,
                        unit=unit,
                        unit_normalized=self._normalize_unit(unit),
                        omop_concept_id=self._get_concept_id(name),
                        confidence=0.9,
                    ))
                except (ValueError, IndexError):
                    continue

        return results

    def extract_labs(self, text: str, offset: int = 0) -> list[ExtractedValue]:
        """Extract lab results from text."""
        self._initialize()
        results = []

        for pattern, default_name, default_unit in self._lab_patterns:
            for match in pattern.finditer(text):
                try:
                    groups = match.groups()

                    # Determine name, value, unit based on pattern
                    if default_name is None:
                        # Name is first capture group
                        name = groups[0].strip()
                        value = float(groups[1])
                        unit = groups[2] if len(groups) > 2 else default_unit
                    else:
                        name = default_name
                        value = float(groups[0])
                        unit = groups[1] if len(groups) > 1 and groups[1] else default_unit

                    results.append(ExtractedValue(
                        text=match.group(0),
                        start_offset=offset + match.start(),
                        end_offset=offset + match.end(),
                        name=name,
                        value_type=ValueType.LAB_RESULT,
                        value=value,
                        unit=unit,
                        unit_normalized=self._normalize_unit(unit),
                        omop_concept_id=self._get_concept_id(name),
                        confidence=0.85,
                    ))
                except (ValueError, IndexError):
                    continue

        return results

    def extract_measurements(self, text: str, offset: int = 0) -> list[ExtractedValue]:
        """Extract clinical measurements (EF, etc.) from text."""
        self._initialize()
        results = []

        for pattern, name, default_unit in self._measurement_patterns:
            for match in pattern.finditer(text):
                try:
                    value = float(match.group(1))
                    unit = default_unit

                    results.append(ExtractedValue(
                        text=match.group(0),
                        start_offset=offset + match.start(),
                        end_offset=offset + match.end(),
                        name=name,
                        value_type=ValueType.MEASUREMENT,
                        value=value,
                        unit=unit,
                        unit_normalized=self._normalize_unit(unit),
                        omop_concept_id=self._get_concept_id(name),
                        confidence=0.9,
                    ))
                except (ValueError, IndexError):
                    continue

        return results

    def extract_medication_doses(self, text: str, offset: int = 0) -> list[ExtractedValue]:
        """Extract medication doses from text."""
        self._initialize()
        results = []

        for pattern, _ in self._med_patterns:
            for match in pattern.finditer(text):
                try:
                    groups = match.groups()
                    name = groups[0].strip()
                    dose = float(groups[1])
                    unit = groups[2] if len(groups) > 2 else None

                    # Extract route and frequency from full match
                    full_text = match.group(0)
                    route = None
                    frequency = None

                    if len(groups) > 3 and groups[3]:
                        route = self._extract_route(groups[3])
                    if len(groups) > 4 and groups[4]:
                        frequency = self._extract_frequency(groups[4])

                    # Fallback to searching full text
                    if not route:
                        route = self._extract_route(full_text)
                    if not frequency:
                        frequency = self._extract_frequency(full_text)

                    results.append(ExtractedValue(
                        text=full_text,
                        start_offset=offset + match.start(),
                        end_offset=offset + match.end(),
                        name=name,
                        value_type=ValueType.MEDICATION_DOSE,
                        value=dose,
                        unit=unit,
                        unit_normalized=self._normalize_unit(unit),
                        frequency=frequency,
                        route=route,
                        confidence=0.85,
                    ))
                except (ValueError, IndexError):
                    continue

        return results

    def extract_all(
        self,
        text: str,
        offset: int = 0,
        include_vitals: bool = True,
        include_labs: bool = True,
        include_measurements: bool = True,
        include_medications: bool = True,
    ) -> list[ExtractedValue]:
        """Extract all clinical values from text.

        Args:
            text: The clinical text to process.
            offset: Starting offset for position tracking.
            include_vitals: Extract vital signs.
            include_labs: Extract lab results.
            include_measurements: Extract clinical measurements.
            include_medications: Extract medication doses.

        Returns:
            List of ExtractedValue objects sorted by position.
        """
        results: list[ExtractedValue] = []

        if include_vitals:
            results.extend(self.extract_vitals(text, offset))

        if include_labs:
            results.extend(self.extract_labs(text, offset))

        if include_measurements:
            results.extend(self.extract_measurements(text, offset))

        if include_medications:
            results.extend(self.extract_medication_doses(text, offset))

        # Sort by position and remove duplicates (overlapping extractions)
        results.sort(key=lambda x: (x.start_offset, -x.end_offset))
        results = self._remove_overlapping(results)

        return results

    def _remove_overlapping(self, values: list[ExtractedValue]) -> list[ExtractedValue]:
        """Remove overlapping extractions, keeping the longer/more specific one."""
        if not values:
            return values

        filtered = []
        for value in values:
            # Check if this overlaps with any already accepted value
            overlaps = False
            for accepted in filtered:
                if (value.start_offset < accepted.end_offset and
                    value.end_offset > accepted.start_offset):
                    # Overlap detected - keep the longer one
                    if len(value.text) > len(accepted.text):
                        filtered.remove(accepted)
                        filtered.append(value)
                    overlaps = True
                    break

            if not overlaps:
                filtered.append(value)

        return sorted(filtered, key=lambda x: x.start_offset)


# Singleton instance
_value_extraction_service: ValueExtractionService | None = None
_value_extraction_lock = threading.Lock()


def get_value_extraction_service() -> ValueExtractionService:
    """Get the singleton value extraction service."""
    global _value_extraction_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _value_extraction_service is None:
        with _value_extraction_lock:
            if _value_extraction_service is None:
                _value_extraction_service = ValueExtractionService()
    return _value_extraction_service
