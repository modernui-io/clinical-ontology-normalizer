"""Patient Timeline Visualization Service for Clinical Ontology Normalizer.

Aggregates patient events across encounters to build a comprehensive
timeline view for clinical decision support and care coordination.

Key capabilities:
1. Aggregate events from multiple sources (encounters, labs, medications)
2. Chronological ordering with event deduplication
3. Gap detection (missing follow-ups, overdue screenings)
4. Event clustering and summarization
5. Filtering by date range, event type, and categories
6. Highlight significant events (hospitalizations, surgeries, new diagnoses)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
import logging
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class TimelineEventType(Enum):
    """Types of events that can appear on a patient timeline."""

    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    MEDICATION_START = "medication_start"
    MEDICATION_STOP = "medication_stop"
    LAB_RESULT = "lab_result"
    VITAL_SIGN = "vital_sign"
    IMAGING = "imaging"
    HOSPITALIZATION = "hospitalization"
    SURGERY = "surgery"
    VACCINATION = "vaccination"
    ENCOUNTER = "encounter"
    REFERRAL = "referral"
    ALLERGY = "allergy"
    PROBLEM_ONSET = "problem_onset"
    PROBLEM_RESOLVED = "problem_resolved"


class EventSeverity(Enum):
    """Severity/importance level of timeline events."""

    CRITICAL = "critical"  # Requires immediate attention (hospitalization, critical lab)
    HIGH = "high"  # Significant event (new diagnosis, surgery)
    MEDIUM = "medium"  # Notable event (procedure, abnormal lab)
    LOW = "low"  # Routine event (follow-up, normal lab)
    INFO = "info"  # Informational only


class GapType(Enum):
    """Types of care gaps identified in timeline."""

    OVERDUE_SCREENING = "overdue_screening"
    MISSED_FOLLOWUP = "missed_followup"
    MEDICATION_GAP = "medication_gap"
    LAB_MONITORING = "lab_monitoring"
    IMMUNIZATION_DUE = "immunization_due"
    REFERRAL_PENDING = "referral_pending"
    CHRONIC_CARE_GAP = "chronic_care_gap"


class GapPriority(Enum):
    """Priority level for care gaps."""

    URGENT = "urgent"  # Address immediately
    HIGH = "high"  # Address within 7 days
    MEDIUM = "medium"  # Address within 30 days
    LOW = "low"  # Address within 90 days


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class TimelineEvent:
    """A single event on the patient timeline."""

    id: str  # Unique event identifier
    event_date: date
    event_type: TimelineEventType
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    source_encounter: str | None = None  # Encounter ID if applicable
    severity: EventSeverity = EventSeverity.LOW

    # Optional metadata
    code: str | None = None  # ICD-10, CPT, LOINC, RxNorm, etc.
    code_system: str | None = None  # Code system identifier
    provider: str | None = None
    facility: str | None = None

    # For duplicate detection
    fingerprint: str | None = None

    # Timestamp for precise ordering
    event_datetime: datetime | None = None

    def __post_init__(self):
        """Generate fingerprint for deduplication."""
        if not self.fingerprint:
            fp_parts = [
                str(self.event_date),
                self.event_type.value,
                self.code or "",
                self.description[:50] if self.description else "",
            ]
            self.fingerprint = "|".join(fp_parts)


@dataclass
class TimelineFilter:
    """Filter criteria for timeline queries."""

    date_from: date | None = None
    date_to: date | None = None
    event_types: list[TimelineEventType] | None = None
    categories: list[str] | None = None  # e.g., ["cardiovascular", "diabetes"]
    severities: list[EventSeverity] | None = None
    search_text: str | None = None
    exclude_routine: bool = False  # Exclude low/info severity
    limit: int | None = None
    offset: int = 0


@dataclass
class CareGap:
    """A care gap identified in the patient timeline."""

    id: str
    gap_type: GapType
    description: str
    priority: GapPriority
    due_date: date | None = None
    days_overdue: int = 0

    # Related information
    related_condition: str | None = None
    related_codes: list[str] = field(default_factory=list)
    recommendation: str = ""
    last_completed: date | None = None

    # Expected interval
    expected_interval_days: int | None = None


@dataclass
class TimelineSummary:
    """Summary statistics for a patient timeline."""

    # Event counts by type
    event_counts_by_type: dict[str, int] = field(default_factory=dict)

    # Key clinical events
    key_events: list[TimelineEvent] = field(default_factory=list)

    # Active conditions (current diagnoses)
    active_conditions: list[dict[str, Any]] = field(default_factory=list)

    # Current medications
    current_medications: list[dict[str, Any]] = field(default_factory=list)

    # Recent labs (last 30 days)
    recent_labs: list[dict[str, Any]] = field(default_factory=list)

    # Hospitalizations in past year
    hospitalizations_past_year: int = 0

    # Surgeries in past year
    surgeries_past_year: int = 0

    # Total unique encounters
    total_encounters: int = 0

    # Date range covered
    earliest_event: date | None = None
    latest_event: date | None = None


@dataclass
class PatientTimeline:
    """Complete patient timeline with events and summary."""

    patient_id: str
    events: list[TimelineEvent] = field(default_factory=list)
    date_range_start: date | None = None
    date_range_end: date | None = None
    summary: TimelineSummary | None = None

    # Processing metadata
    total_events: int = 0
    filtered_events: int = 0
    generation_time_ms: float = 0.0


@dataclass
class GapAnalysisResult:
    """Results of care gap analysis."""

    patient_id: str
    analysis_date: date
    gaps: list[CareGap] = field(default_factory=list)

    # Summary counts
    total_gaps: int = 0
    urgent_gaps: int = 0
    high_priority_gaps: int = 0

    # By type
    gaps_by_type: dict[str, int] = field(default_factory=dict)

    # Processing
    analysis_time_ms: float = 0.0


# ============================================================================
# Screening and Follow-up Definitions
# ============================================================================

# Standard screening intervals (in days)
SCREENING_INTERVALS = {
    # Cancer screenings
    "mammogram": {"interval_days": 730, "age_min": 50, "age_max": 74, "gender": "F"},
    "colonoscopy": {"interval_days": 3650, "age_min": 45, "age_max": 75},
    "cervical_screening": {"interval_days": 1095, "age_min": 21, "age_max": 65, "gender": "F"},
    "lung_cancer_screening": {"interval_days": 365, "age_min": 50, "age_max": 80},

    # Diabetes monitoring
    "hba1c_diabetes": {"interval_days": 90, "conditions": ["E10", "E11", "E13"]},
    "eye_exam_diabetes": {"interval_days": 365, "conditions": ["E10", "E11", "E13"]},
    "foot_exam_diabetes": {"interval_days": 365, "conditions": ["E10", "E11", "E13"]},
    "nephropathy_screening": {"interval_days": 365, "conditions": ["E10", "E11", "E13"]},

    # Cardiovascular monitoring
    "lipid_panel": {"interval_days": 365, "conditions": ["I25", "E78", "E11"]},
    "inr_monitoring": {"interval_days": 30, "medications": ["warfarin"]},

    # Immunizations
    "flu_vaccine": {"interval_days": 365, "age_min": 6},
    "pneumonia_vaccine": {"interval_days": 1825, "age_min": 65},  # 5 years for PPSV23
    "shingles_vaccine": {"interval_days": None, "age_min": 50},  # One-time series
    "tdap_vaccine": {"interval_days": 3650, "age_min": 19},

    # Other monitoring
    "bone_density": {"interval_days": 730, "age_min": 65, "gender": "F"},
    "aaa_screening": {"interval_days": None, "age_min": 65, "age_max": 75, "gender": "M"},  # One-time
}

# Lab monitoring for medications
MEDICATION_LAB_MONITORING = {
    "metformin": [
        {"lab": "creatinine", "interval_days": 365, "loinc": "2160-0"},
        {"lab": "vitamin_b12", "interval_days": 365, "loinc": "2132-9"},
    ],
    "statin": [
        {"lab": "lipid_panel", "interval_days": 365, "loinc": "57698-3"},
        {"lab": "alt", "interval_days": 365, "loinc": "1742-6"},
    ],
    "ace_inhibitor": [
        {"lab": "potassium", "interval_days": 90, "loinc": "2823-3"},
        {"lab": "creatinine", "interval_days": 365, "loinc": "2160-0"},
    ],
    "lithium": [
        {"lab": "lithium_level", "interval_days": 90, "loinc": "14334-7"},
        {"lab": "tsh", "interval_days": 180, "loinc": "3016-3"},
        {"lab": "creatinine", "interval_days": 180, "loinc": "2160-0"},
    ],
    "anticoagulant": [
        {"lab": "cbc", "interval_days": 90, "loinc": "58410-2"},
    ],
    "thyroid_replacement": [
        {"lab": "tsh", "interval_days": 365, "loinc": "3016-3"},
    ],
}


# ============================================================================
# Patient Timeline Service
# ============================================================================


class PatientTimelineService:
    """Service for building and analyzing patient timelines."""

    def __init__(self):
        """Initialize the service."""
        self._screening_intervals = SCREENING_INTERVALS
        self._medication_monitoring = MEDICATION_LAB_MONITORING
        logger.info("PatientTimelineService initialized")

    def build_timeline(
        self,
        patient_id: str,
        patient_data: dict[str, Any],
        filter_criteria: TimelineFilter | None = None,
    ) -> PatientTimeline:
        """Build a patient timeline from clinical data.

        Args:
            patient_id: Patient identifier
            patient_data: Patient clinical data including:
                - demographics: {age, gender, dob}
                - diagnoses: [{code, date, description, status}]
                - procedures: [{code, date, description}]
                - labs: [{name, value, date, loinc, unit, reference_range}]
                - medications: [{name, rxnorm, start_date, end_date, status}]
                - vitals: [{name, value, date, unit}]
                - encounters: [{id, date, type, provider, facility}]
                - immunizations: [{vaccine, date, dose}]
            filter_criteria: Optional filter criteria

        Returns:
            PatientTimeline with aggregated events
        """
        import time
        start_time = time.perf_counter()

        events: list[TimelineEvent] = []

        # Extract events from each data source
        events.extend(self._extract_diagnosis_events(patient_data))
        events.extend(self._extract_procedure_events(patient_data))
        events.extend(self._extract_lab_events(patient_data))
        events.extend(self._extract_medication_events(patient_data))
        events.extend(self._extract_vital_events(patient_data))
        events.extend(self._extract_encounter_events(patient_data))
        events.extend(self._extract_immunization_events(patient_data))

        # Deduplicate events
        events = self._deduplicate_events(events)

        # Sort chronologically (most recent first)
        events.sort(key=lambda e: (e.event_date, e.event_datetime or datetime.min), reverse=True)

        total_events = len(events)

        # Apply filters
        if filter_criteria:
            events = self._apply_filters(events, filter_criteria)

        # Build summary
        summary = self._build_summary(events, patient_data)

        # Determine date range
        date_range_start = None
        date_range_end = None
        if events:
            dates = [e.event_date for e in events]
            date_range_start = min(dates)
            date_range_end = max(dates)

        generation_time = (time.perf_counter() - start_time) * 1000

        return PatientTimeline(
            patient_id=patient_id,
            events=events,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            summary=summary,
            total_events=total_events,
            filtered_events=len(events),
            generation_time_ms=round(generation_time, 2),
        )

    def get_timeline_summary(
        self,
        patient_id: str,
        patient_data: dict[str, Any],
    ) -> TimelineSummary:
        """Get a summary of the patient timeline.

        Args:
            patient_id: Patient identifier
            patient_data: Patient clinical data

        Returns:
            TimelineSummary with key statistics and events
        """
        timeline = self.build_timeline(patient_id, patient_data)
        return timeline.summary or self._build_summary(timeline.events, patient_data)

    def get_filtered_events(
        self,
        patient_id: str,
        patient_data: dict[str, Any],
        filter_criteria: TimelineFilter,
    ) -> list[TimelineEvent]:
        """Get filtered timeline events.

        Args:
            patient_id: Patient identifier
            patient_data: Patient clinical data
            filter_criteria: Filter criteria

        Returns:
            List of filtered TimelineEvents
        """
        timeline = self.build_timeline(patient_id, patient_data, filter_criteria)
        return timeline.events

    def analyze_care_gaps(
        self,
        patient_id: str,
        patient_data: dict[str, Any],
        analysis_date: date | None = None,
    ) -> GapAnalysisResult:
        """Analyze patient timeline for care gaps.

        Identifies:
        - Overdue screenings based on age/gender/conditions
        - Missing follow-ups for chronic conditions
        - Medication monitoring gaps
        - Immunization gaps

        Args:
            patient_id: Patient identifier
            patient_data: Patient clinical data
            analysis_date: Date for analysis (today if not provided)

        Returns:
            GapAnalysisResult with identified gaps
        """
        import time
        start_time = time.perf_counter()

        analysis_date = analysis_date or date.today()
        gaps: list[CareGap] = []

        demographics = patient_data.get("demographics", {})
        patient_age = demographics.get("age", 0)
        patient_gender = demographics.get("gender", "").upper()

        # Get patient diagnoses for condition-based screenings
        diagnoses = patient_data.get("diagnoses", [])
        diagnosis_codes = [d.get("code", "") for d in diagnoses]

        # Get patient medications
        medications = patient_data.get("medications", [])

        # Get patient labs
        labs = patient_data.get("labs", [])

        # Get patient procedures
        procedures = patient_data.get("procedures", [])

        # Get immunizations
        immunizations = patient_data.get("immunizations", [])

        # Check age/gender based screenings
        gaps.extend(self._check_screening_gaps(
            patient_age, patient_gender, diagnosis_codes,
            procedures, labs, immunizations, analysis_date
        ))

        # Check condition-specific monitoring
        gaps.extend(self._check_condition_monitoring_gaps(
            diagnosis_codes, labs, analysis_date
        ))

        # Check medication monitoring gaps
        gaps.extend(self._check_medication_monitoring_gaps(
            medications, labs, analysis_date
        ))

        # Check follow-up gaps (hospitalizations, surgeries)
        gaps.extend(self._check_followup_gaps(
            patient_data, analysis_date
        ))

        # Sort by priority
        priority_order = {
            GapPriority.URGENT: 0,
            GapPriority.HIGH: 1,
            GapPriority.MEDIUM: 2,
            GapPriority.LOW: 3,
        }
        gaps.sort(key=lambda g: (priority_order.get(g.priority, 4), g.days_overdue), reverse=True)

        # Count by type and priority
        gaps_by_type: dict[str, int] = {}
        urgent_count = 0
        high_count = 0
        for gap in gaps:
            gt = gap.gap_type.value
            gaps_by_type[gt] = gaps_by_type.get(gt, 0) + 1
            if gap.priority == GapPriority.URGENT:
                urgent_count += 1
            elif gap.priority == GapPriority.HIGH:
                high_count += 1

        analysis_time = (time.perf_counter() - start_time) * 1000

        return GapAnalysisResult(
            patient_id=patient_id,
            analysis_date=analysis_date,
            gaps=gaps,
            total_gaps=len(gaps),
            urgent_gaps=urgent_count,
            high_priority_gaps=high_count,
            gaps_by_type=gaps_by_type,
            analysis_time_ms=round(analysis_time, 2),
        )

    def parse_relative_date(
        self,
        relative_query: str,
        reference_date: date | None = None,
    ) -> tuple[date, date]:
        """Parse relative date queries into date range.

        Supports queries like:
        - "last 6 months"
        - "past year"
        - "last 30 days"
        - "past 2 years"
        - "this month"
        - "this year"

        Args:
            relative_query: Natural language date query
            reference_date: Reference date (today if not provided)

        Returns:
            Tuple of (start_date, end_date)
        """
        reference_date = reference_date or date.today()
        query = relative_query.lower().strip()

        # Parse number + unit patterns
        patterns = [
            (r"(?:last|past)\s+(\d+)\s+days?", "days"),
            (r"(?:last|past)\s+(\d+)\s+weeks?", "weeks"),
            (r"(?:last|past)\s+(\d+)\s+months?", "months"),
            (r"(?:last|past)\s+(\d+)\s+years?", "years"),
            (r"(?:last|past)\s+year", "year"),
            (r"(?:last|past)\s+month", "month"),
            (r"(?:last|past)\s+week", "week"),
            (r"this\s+year", "this_year"),
            (r"this\s+month", "this_month"),
            (r"this\s+week", "this_week"),
        ]

        for pattern, unit in patterns:
            match = re.match(pattern, query)
            if match:
                if unit == "days":
                    days = int(match.group(1))
                    return reference_date - timedelta(days=days), reference_date
                elif unit == "weeks":
                    weeks = int(match.group(1))
                    return reference_date - timedelta(weeks=weeks), reference_date
                elif unit == "months":
                    months = int(match.group(1))
                    return self._subtract_months(reference_date, months), reference_date
                elif unit == "years":
                    years = int(match.group(1))
                    return self._subtract_years(reference_date, years), reference_date
                elif unit == "year":
                    return self._subtract_years(reference_date, 1), reference_date
                elif unit == "month":
                    return self._subtract_months(reference_date, 1), reference_date
                elif unit == "week":
                    return reference_date - timedelta(weeks=1), reference_date
                elif unit == "this_year":
                    return date(reference_date.year, 1, 1), reference_date
                elif unit == "this_month":
                    return date(reference_date.year, reference_date.month, 1), reference_date
                elif unit == "this_week":
                    start = reference_date - timedelta(days=reference_date.weekday())
                    return start, reference_date

        # Default: last year
        return self._subtract_years(reference_date, 1), reference_date

    def _extract_diagnosis_events(self, patient_data: dict[str, Any]) -> list[TimelineEvent]:
        """Extract diagnosis events from patient data."""
        events = []
        diagnoses = patient_data.get("diagnoses", [])

        for i, dx in enumerate(diagnoses):
            event_date = self._parse_date(dx.get("date"))
            if not event_date:
                continue

            # Determine severity based on diagnosis
            severity = EventSeverity.MEDIUM
            code = dx.get("code", "")

            # Critical diagnoses
            if any(code.startswith(c) for c in ["I21", "I22", "I63", "C"]):
                severity = EventSeverity.CRITICAL
            elif any(code.startswith(c) for c in ["I25", "E10", "E11", "N18"]):
                severity = EventSeverity.HIGH

            status = dx.get("status", "active")
            event_type = TimelineEventType.DIAGNOSIS
            if status == "resolved":
                event_type = TimelineEventType.PROBLEM_RESOLVED

            events.append(TimelineEvent(
                id=f"dx_{i}_{code}",
                event_date=event_date,
                event_type=event_type,
                description=dx.get("description", f"Diagnosis: {code}"),
                details={
                    "status": status,
                    "category": dx.get("category"),
                },
                code=code,
                code_system="ICD-10-CM",
                severity=severity,
                source_encounter=dx.get("encounter_id"),
            ))

        return events

    def _extract_procedure_events(self, patient_data: dict[str, Any]) -> list[TimelineEvent]:
        """Extract procedure events from patient data."""
        events = []
        procedures = patient_data.get("procedures", [])

        # Surgical procedure codes (simplified list)
        surgical_prefixes = ["27", "28", "29", "33", "35", "36", "43", "44", "47", "49"]

        for i, proc in enumerate(procedures):
            event_date = self._parse_date(proc.get("date"))
            if not event_date:
                continue

            code = proc.get("code", "")

            # Determine if surgery
            is_surgery = any(code.startswith(p) for p in surgical_prefixes)
            event_type = TimelineEventType.SURGERY if is_surgery else TimelineEventType.PROCEDURE

            # Determine severity
            severity = EventSeverity.HIGH if is_surgery else EventSeverity.MEDIUM

            events.append(TimelineEvent(
                id=f"proc_{i}_{code}",
                event_date=event_date,
                event_type=event_type,
                description=proc.get("description", f"Procedure: {code}"),
                details={
                    "is_surgery": is_surgery,
                },
                code=code,
                code_system="CPT",
                severity=severity,
                provider=proc.get("provider"),
                facility=proc.get("facility"),
                source_encounter=proc.get("encounter_id"),
            ))

        return events

    def _extract_lab_events(self, patient_data: dict[str, Any]) -> list[TimelineEvent]:
        """Extract lab result events from patient data."""
        events = []
        labs = patient_data.get("labs", [])

        for i, lab in enumerate(labs):
            event_date = self._parse_date(lab.get("date"))
            if not event_date:
                continue

            # Determine severity based on value vs reference range
            severity = EventSeverity.LOW
            value = lab.get("value")
            ref_low = lab.get("reference_low")
            ref_high = lab.get("reference_high")
            interpretation = lab.get("interpretation", "").upper()

            if interpretation in ["CRITICAL", "PANIC"]:
                severity = EventSeverity.CRITICAL
            elif interpretation in ["HIGH", "LOW", "ABNORMAL"]:
                severity = EventSeverity.MEDIUM
            elif value is not None and ref_low is not None and ref_high is not None:
                try:
                    val = float(value)
                    low = float(ref_low)
                    high = float(ref_high)
                    if val < low * 0.5 or val > high * 2:
                        severity = EventSeverity.HIGH
                    elif val < low or val > high:
                        severity = EventSeverity.MEDIUM
                except (ValueError, TypeError):
                    pass

            events.append(TimelineEvent(
                id=f"lab_{i}_{lab.get('loinc', lab.get('name', ''))}",
                event_date=event_date,
                event_type=TimelineEventType.LAB_RESULT,
                description=f"{lab.get('name', 'Lab')}: {value} {lab.get('unit', '')}",
                details={
                    "value": value,
                    "unit": lab.get("unit"),
                    "reference_range": lab.get("reference_range"),
                    "interpretation": interpretation,
                },
                code=lab.get("loinc"),
                code_system="LOINC",
                severity=severity,
                source_encounter=lab.get("encounter_id"),
            ))

        return events

    def _extract_medication_events(self, patient_data: dict[str, Any]) -> list[TimelineEvent]:
        """Extract medication events from patient data."""
        events = []
        medications = patient_data.get("medications", [])

        for i, med in enumerate(medications):
            start_date = self._parse_date(med.get("start_date"))
            end_date = self._parse_date(med.get("end_date"))

            # Medication start event
            if start_date:
                events.append(TimelineEvent(
                    id=f"med_start_{i}_{med.get('rxnorm', med.get('name', ''))}",
                    event_date=start_date,
                    event_type=TimelineEventType.MEDICATION_START,
                    description=f"Started: {med.get('name', 'Medication')}",
                    details={
                        "dose": med.get("dose"),
                        "frequency": med.get("frequency"),
                        "route": med.get("route"),
                    },
                    code=med.get("rxnorm"),
                    code_system="RxNorm",
                    severity=EventSeverity.LOW,
                    source_encounter=med.get("encounter_id"),
                ))

            # Medication stop event
            if end_date:
                events.append(TimelineEvent(
                    id=f"med_stop_{i}_{med.get('rxnorm', med.get('name', ''))}",
                    event_date=end_date,
                    event_type=TimelineEventType.MEDICATION_STOP,
                    description=f"Stopped: {med.get('name', 'Medication')}",
                    details={
                        "reason": med.get("discontinuation_reason"),
                    },
                    code=med.get("rxnorm"),
                    code_system="RxNorm",
                    severity=EventSeverity.INFO,
                    source_encounter=med.get("encounter_id"),
                ))

        return events

    def _extract_vital_events(self, patient_data: dict[str, Any]) -> list[TimelineEvent]:
        """Extract vital sign events from patient data."""
        events = []
        vitals = patient_data.get("vitals", [])

        for i, vital in enumerate(vitals):
            event_date = self._parse_date(vital.get("date"))
            if not event_date:
                continue

            # Determine severity based on vital
            severity = EventSeverity.INFO
            name = vital.get("name", "").lower()
            value = vital.get("value")

            if value is not None:
                try:
                    val = float(value)
                    if "systolic" in name and (val > 180 or val < 90):
                        severity = EventSeverity.CRITICAL
                    elif "systolic" in name and (val > 140 or val < 100):
                        severity = EventSeverity.MEDIUM
                    elif "diastolic" in name and (val > 120 or val < 50):
                        severity = EventSeverity.CRITICAL
                    elif "diastolic" in name and val > 90:
                        severity = EventSeverity.MEDIUM
                    elif "heart_rate" in name or "pulse" in name:
                        if val > 120 or val < 50:
                            severity = EventSeverity.HIGH
                        elif val > 100 or val < 60:
                            severity = EventSeverity.MEDIUM
                    elif "oxygen" in name or "spo2" in name:
                        if val < 90:
                            severity = EventSeverity.CRITICAL
                        elif val < 94:
                            severity = EventSeverity.HIGH
                except (ValueError, TypeError):
                    pass

            events.append(TimelineEvent(
                id=f"vital_{i}_{name}",
                event_date=event_date,
                event_type=TimelineEventType.VITAL_SIGN,
                description=f"{vital.get('name', 'Vital')}: {value} {vital.get('unit', '')}",
                details={
                    "value": value,
                    "unit": vital.get("unit"),
                },
                severity=severity,
                source_encounter=vital.get("encounter_id"),
            ))

        return events

    def _extract_encounter_events(self, patient_data: dict[str, Any]) -> list[TimelineEvent]:
        """Extract encounter events from patient data."""
        events = []
        encounters = patient_data.get("encounters", [])

        for i, enc in enumerate(encounters):
            event_date = self._parse_date(enc.get("date"))
            if not event_date:
                continue

            enc_type = enc.get("type", "").lower()

            # Determine event type and severity
            if "hospital" in enc_type or "inpatient" in enc_type:
                event_type = TimelineEventType.HOSPITALIZATION
                severity = EventSeverity.CRITICAL
            elif "emergency" in enc_type or "er" in enc_type:
                event_type = TimelineEventType.ENCOUNTER
                severity = EventSeverity.HIGH
            else:
                event_type = TimelineEventType.ENCOUNTER
                severity = EventSeverity.LOW

            events.append(TimelineEvent(
                id=f"enc_{i}_{enc.get('id', '')}",
                event_date=event_date,
                event_type=event_type,
                description=f"{enc.get('type', 'Encounter')}",
                details={
                    "encounter_type": enc.get("type"),
                    "reason": enc.get("reason"),
                    "discharge_disposition": enc.get("discharge_disposition"),
                },
                severity=severity,
                provider=enc.get("provider"),
                facility=enc.get("facility"),
                source_encounter=enc.get("id"),
            ))

        return events

    def _extract_immunization_events(self, patient_data: dict[str, Any]) -> list[TimelineEvent]:
        """Extract immunization events from patient data."""
        events = []
        immunizations = patient_data.get("immunizations", [])

        for i, imm in enumerate(immunizations):
            event_date = self._parse_date(imm.get("date"))
            if not event_date:
                continue

            events.append(TimelineEvent(
                id=f"imm_{i}_{imm.get('cvx', imm.get('vaccine', ''))}",
                event_date=event_date,
                event_type=TimelineEventType.VACCINATION,
                description=f"Vaccination: {imm.get('vaccine', 'Unknown')}",
                details={
                    "dose_number": imm.get("dose"),
                    "lot_number": imm.get("lot_number"),
                    "site": imm.get("site"),
                },
                code=imm.get("cvx"),
                code_system="CVX",
                severity=EventSeverity.LOW,
                source_encounter=imm.get("encounter_id"),
            ))

        return events

    def _deduplicate_events(self, events: list[TimelineEvent]) -> list[TimelineEvent]:
        """Remove duplicate events based on fingerprint."""
        seen_fingerprints: set[str] = set()
        unique_events: list[TimelineEvent] = []

        for event in events:
            if event.fingerprint and event.fingerprint not in seen_fingerprints:
                seen_fingerprints.add(event.fingerprint)
                unique_events.append(event)
            elif not event.fingerprint:
                unique_events.append(event)

        return unique_events

    def _apply_filters(
        self,
        events: list[TimelineEvent],
        filter_criteria: TimelineFilter,
    ) -> list[TimelineEvent]:
        """Apply filter criteria to events."""
        filtered = events

        # Date range filter
        if filter_criteria.date_from:
            filtered = [e for e in filtered if e.event_date >= filter_criteria.date_from]
        if filter_criteria.date_to:
            filtered = [e for e in filtered if e.event_date <= filter_criteria.date_to]

        # Event type filter
        if filter_criteria.event_types:
            filtered = [e for e in filtered if e.event_type in filter_criteria.event_types]

        # Severity filter
        if filter_criteria.severities:
            filtered = [e for e in filtered if e.severity in filter_criteria.severities]

        # Exclude routine events
        if filter_criteria.exclude_routine:
            filtered = [e for e in filtered if e.severity not in [EventSeverity.LOW, EventSeverity.INFO]]

        # Text search
        if filter_criteria.search_text:
            search_lower = filter_criteria.search_text.lower()
            filtered = [
                e for e in filtered
                if search_lower in e.description.lower()
                or (e.code and search_lower in e.code.lower())
            ]

        # Pagination
        if filter_criteria.offset:
            filtered = filtered[filter_criteria.offset:]
        if filter_criteria.limit:
            filtered = filtered[:filter_criteria.limit]

        return filtered

    def _build_summary(
        self,
        events: list[TimelineEvent],
        patient_data: dict[str, Any],
    ) -> TimelineSummary:
        """Build timeline summary from events."""
        # Count by type
        event_counts: dict[str, int] = {}
        for event in events:
            et = event.event_type.value
            event_counts[et] = event_counts.get(et, 0) + 1

        # Key events (high/critical severity)
        key_events = [e for e in events if e.severity in [EventSeverity.CRITICAL, EventSeverity.HIGH]][:10]

        # Active conditions (from patient data)
        diagnoses = patient_data.get("diagnoses", [])
        active_conditions = [
            {
                "code": d.get("code"),
                "description": d.get("description"),
                "onset_date": d.get("date"),
            }
            for d in diagnoses
            if d.get("status", "active") == "active"
        ]

        # Current medications
        medications = patient_data.get("medications", [])
        current_meds = [
            {
                "name": m.get("name"),
                "rxnorm": m.get("rxnorm"),
                "dose": m.get("dose"),
                "start_date": m.get("start_date"),
            }
            for m in medications
            if not m.get("end_date")
        ]

        # Recent labs (last 30 days)
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)
        recent_labs = [
            {
                "name": e.details.get("name") or e.description,
                "value": e.details.get("value"),
                "date": str(e.event_date),
                "interpretation": e.details.get("interpretation"),
            }
            for e in events
            if e.event_type == TimelineEventType.LAB_RESULT and e.event_date >= thirty_days_ago
        ][:20]

        # Hospitalizations in past year
        year_ago = self._subtract_years(today, 1)
        hospitalizations_past_year = sum(
            1 for e in events
            if e.event_type == TimelineEventType.HOSPITALIZATION and e.event_date >= year_ago
        )

        # Surgeries in past year
        surgeries_past_year = sum(
            1 for e in events
            if e.event_type == TimelineEventType.SURGERY and e.event_date >= year_ago
        )

        # Unique encounters
        encounters = {e.source_encounter for e in events if e.source_encounter}

        # Date range
        earliest = min((e.event_date for e in events), default=None)
        latest = max((e.event_date for e in events), default=None)

        return TimelineSummary(
            event_counts_by_type=event_counts,
            key_events=key_events,
            active_conditions=active_conditions,
            current_medications=current_meds,
            recent_labs=recent_labs,
            hospitalizations_past_year=hospitalizations_past_year,
            surgeries_past_year=surgeries_past_year,
            total_encounters=len(encounters),
            earliest_event=earliest,
            latest_event=latest,
        )

    def _check_screening_gaps(
        self,
        patient_age: int,
        patient_gender: str,
        diagnosis_codes: list[str],
        procedures: list[dict],
        labs: list[dict],
        immunizations: list[dict],
        analysis_date: date,
    ) -> list[CareGap]:
        """Check for overdue screening gaps."""
        gaps = []

        for screening_name, criteria in self._screening_intervals.items():
            # Check age eligibility
            age_min = criteria.get("age_min", 0)
            age_max = criteria.get("age_max", 999)
            if not (age_min <= patient_age <= age_max):
                continue

            # Check gender eligibility
            required_gender = criteria.get("gender")
            if required_gender and patient_gender != required_gender:
                continue

            # Check condition requirement
            required_conditions = criteria.get("conditions", [])
            if required_conditions:
                has_condition = any(
                    any(dc.startswith(rc) for rc in required_conditions)
                    for dc in diagnosis_codes
                )
                if not has_condition:
                    continue

            # Check if screening is one-time or recurring
            interval_days = criteria.get("interval_days")
            if interval_days is None:
                # One-time screening - check if ever done
                # (simplified - would need more specific logic)
                continue

            # Find last screening date
            last_screening = self._find_last_screening_date(
                screening_name, procedures, labs, immunizations
            )

            # Calculate if overdue
            if last_screening:
                next_due = last_screening + timedelta(days=interval_days)
                if next_due <= analysis_date:
                    days_overdue = (analysis_date - next_due).days
                    priority = self._determine_gap_priority(days_overdue, interval_days)

                    gaps.append(CareGap(
                        id=f"screening_{screening_name}",
                        gap_type=GapType.OVERDUE_SCREENING,
                        description=f"Overdue: {screening_name.replace('_', ' ').title()}",
                        priority=priority,
                        due_date=next_due,
                        days_overdue=days_overdue,
                        recommendation=f"Schedule {screening_name.replace('_', ' ')}",
                        last_completed=last_screening,
                        expected_interval_days=interval_days,
                    ))
            else:
                # Never done - consider as overdue
                priority = GapPriority.HIGH
                gaps.append(CareGap(
                    id=f"screening_{screening_name}",
                    gap_type=GapType.OVERDUE_SCREENING,
                    description=f"Never completed: {screening_name.replace('_', ' ').title()}",
                    priority=priority,
                    due_date=analysis_date,
                    days_overdue=0,
                    recommendation=f"Schedule initial {screening_name.replace('_', ' ')}",
                    expected_interval_days=interval_days,
                ))

        return gaps

    def _check_condition_monitoring_gaps(
        self,
        diagnosis_codes: list[str],
        labs: list[dict],
        analysis_date: date,
    ) -> list[CareGap]:
        """Check for condition-specific monitoring gaps."""
        gaps = []

        # Diabetes monitoring
        has_diabetes = any(dc.startswith(("E10", "E11", "E13")) for dc in diagnosis_codes)
        if has_diabetes:
            # Check HbA1c
            last_hba1c = self._find_last_lab_date(labs, ["4548-4", "hba1c", "hemoglobin a1c"])
            if last_hba1c:
                next_due = last_hba1c + timedelta(days=90)
                if next_due <= analysis_date:
                    days_overdue = (analysis_date - next_due).days
                    gaps.append(CareGap(
                        id="diabetes_hba1c",
                        gap_type=GapType.LAB_MONITORING,
                        description="Overdue: HbA1c monitoring",
                        priority=GapPriority.HIGH if days_overdue > 30 else GapPriority.MEDIUM,
                        due_date=next_due,
                        days_overdue=days_overdue,
                        related_condition="Diabetes",
                        recommendation="Order HbA1c test",
                        last_completed=last_hba1c,
                        expected_interval_days=90,
                    ))

        # CKD monitoring
        has_ckd = any(dc.startswith("N18") for dc in diagnosis_codes)
        if has_ckd:
            last_creatinine = self._find_last_lab_date(labs, ["2160-0", "creatinine"])
            if last_creatinine:
                next_due = last_creatinine + timedelta(days=90)
                if next_due <= analysis_date:
                    days_overdue = (analysis_date - next_due).days
                    gaps.append(CareGap(
                        id="ckd_creatinine",
                        gap_type=GapType.LAB_MONITORING,
                        description="Overdue: Kidney function monitoring",
                        priority=GapPriority.HIGH if days_overdue > 30 else GapPriority.MEDIUM,
                        due_date=next_due,
                        days_overdue=days_overdue,
                        related_condition="CKD",
                        recommendation="Order BMP or CMP",
                        last_completed=last_creatinine,
                        expected_interval_days=90,
                    ))

        return gaps

    def _check_medication_monitoring_gaps(
        self,
        medications: list[dict],
        labs: list[dict],
        analysis_date: date,
    ) -> list[CareGap]:
        """Check for medication-specific lab monitoring gaps."""
        gaps = []

        for med in medications:
            med_name = med.get("name", "").lower()

            # Skip discontinued medications
            if med.get("end_date"):
                continue

            # Check each medication class for monitoring requirements
            for med_class, monitoring_reqs in self._medication_monitoring.items():
                if med_class.lower() in med_name:
                    for req in monitoring_reqs:
                        last_lab = self._find_last_lab_date(labs, [req["loinc"], req["lab"]])
                        interval = req["interval_days"]

                        if last_lab:
                            next_due = last_lab + timedelta(days=interval)
                            if next_due <= analysis_date:
                                days_overdue = (analysis_date - next_due).days
                                gaps.append(CareGap(
                                    id=f"med_{med_class}_{req['lab']}",
                                    gap_type=GapType.LAB_MONITORING,
                                    description=f"Overdue: {req['lab'].replace('_', ' ').title()} for {med_class}",
                                    priority=GapPriority.HIGH if days_overdue > 14 else GapPriority.MEDIUM,
                                    due_date=next_due,
                                    days_overdue=days_overdue,
                                    related_codes=[req["loinc"]],
                                    recommendation=f"Order {req['lab'].replace('_', ' ')} for {med_class} monitoring",
                                    last_completed=last_lab,
                                    expected_interval_days=interval,
                                ))

        return gaps

    def _check_followup_gaps(
        self,
        patient_data: dict[str, Any],
        analysis_date: date,
    ) -> list[CareGap]:
        """Check for post-discharge and post-procedure follow-up gaps."""
        gaps = []
        encounters = patient_data.get("encounters", [])

        for enc in encounters:
            enc_type = enc.get("type", "").lower()
            enc_date = self._parse_date(enc.get("date"))

            if not enc_date:
                continue

            # Check for hospitalization follow-up (within 7 days)
            if "hospital" in enc_type or "inpatient" in enc_type:
                followup_due = enc_date + timedelta(days=7)
                if followup_due <= analysis_date:
                    # Check if there was a follow-up encounter
                    has_followup = any(
                        self._parse_date(e.get("date")) and
                        enc_date < self._parse_date(e.get("date")) <= followup_due
                        for e in encounters
                        if e != enc
                    )

                    if not has_followup:
                        days_overdue = (analysis_date - followup_due).days
                        gaps.append(CareGap(
                            id=f"followup_hosp_{enc.get('id', '')}",
                            gap_type=GapType.MISSED_FOLLOWUP,
                            description="Missed: Post-hospitalization follow-up",
                            priority=GapPriority.URGENT if days_overdue > 7 else GapPriority.HIGH,
                            due_date=followup_due,
                            days_overdue=days_overdue,
                            recommendation="Schedule post-discharge follow-up appointment",
                            last_completed=enc_date,
                            expected_interval_days=7,
                        ))

        return gaps

    def _find_last_screening_date(
        self,
        screening_name: str,
        procedures: list[dict],
        labs: list[dict],
        immunizations: list[dict],
    ) -> date | None:
        """Find the last date a screening was performed."""
        dates = []

        # Map screening names to procedure codes
        screening_codes = {
            "mammogram": ["77067", "77066", "G0202", "G0204"],
            "colonoscopy": ["45378", "45380", "45381", "G0105", "G0121"],
            "cervical_screening": ["88141", "88142", "88143", "87624", "87625"],
            "eye_exam_diabetes": ["92002", "92004", "92012", "92014", "92227"],
            "bone_density": ["77080", "77081"],
        }

        codes = screening_codes.get(screening_name, [])
        for proc in procedures:
            if proc.get("code") in codes:
                proc_date = self._parse_date(proc.get("date"))
                if proc_date:
                    dates.append(proc_date)

        # Map screening names to lab LOINC codes
        screening_labs = {
            "hba1c_diabetes": ["4548-4"],
            "lipid_panel": ["57698-3", "2093-3"],
            "nephropathy_screening": ["14957-5", "9318-7"],
        }

        loincs = screening_labs.get(screening_name, [])
        for lab in labs:
            if lab.get("loinc") in loincs:
                lab_date = self._parse_date(lab.get("date"))
                if lab_date:
                    dates.append(lab_date)

        # Immunizations
        vaccine_map = {
            "flu_vaccine": ["flu", "influenza"],
            "pneumonia_vaccine": ["pneumo", "ppsv", "pcv"],
            "shingles_vaccine": ["shingrix", "zostavax", "zoster"],
            "tdap_vaccine": ["tdap", "tetanus", "diphtheria"],
        }

        vaccines = vaccine_map.get(screening_name, [])
        for imm in immunizations:
            vaccine_name = imm.get("vaccine", "").lower()
            if any(v in vaccine_name for v in vaccines):
                imm_date = self._parse_date(imm.get("date"))
                if imm_date:
                    dates.append(imm_date)

        return max(dates) if dates else None

    def _find_last_lab_date(
        self,
        labs: list[dict],
        identifiers: list[str],
    ) -> date | None:
        """Find the last date a lab was performed."""
        dates = []
        identifiers_lower = [i.lower() for i in identifiers]

        for lab in labs:
            loinc = lab.get("loinc", "").lower()
            name = lab.get("name", "").lower()

            if loinc in identifiers_lower or any(i in name for i in identifiers_lower):
                lab_date = self._parse_date(lab.get("date"))
                if lab_date:
                    dates.append(lab_date)

        return max(dates) if dates else None

    def _determine_gap_priority(self, days_overdue: int, interval_days: int) -> GapPriority:
        """Determine gap priority based on how overdue it is."""
        # Calculate percentage overdue
        pct_overdue = days_overdue / interval_days if interval_days > 0 else 0

        if pct_overdue > 0.5:  # More than 50% overdue
            return GapPriority.URGENT
        elif pct_overdue > 0.25:  # More than 25% overdue
            return GapPriority.HIGH
        elif pct_overdue > 0.1:  # More than 10% overdue
            return GapPriority.MEDIUM
        else:
            return GapPriority.LOW

    def _parse_date(self, date_value: Any) -> date | None:
        """Parse a date from various formats."""
        if date_value is None:
            return None
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, "%Y-%m-%d").date()
            except ValueError:
                try:
                    return datetime.fromisoformat(date_value).date()
                except ValueError:
                    return None
        return None

    def _subtract_months(self, d: date, months: int) -> date:
        """Subtract months from a date."""
        month = d.month - months
        year = d.year
        while month <= 0:
            month += 12
            year -= 1
        day = min(d.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date(year, month, day)

    def _subtract_years(self, d: date, years: int) -> date:
        """Subtract years from a date."""
        try:
            return d.replace(year=d.year - years)
        except ValueError:
            # Handle leap year edge case (Feb 29)
            return d.replace(year=d.year - years, day=28)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "screening_types_defined": len(self._screening_intervals),
            "medication_monitoring_classes": len(self._medication_monitoring),
            "event_types_supported": len(TimelineEventType),
            "gap_types_supported": len(GapType),
        }


# ============================================================================
# Singleton Pattern
# ============================================================================

_service_instance: PatientTimelineService | None = None
_service_lock = threading.Lock()


def get_patient_timeline_service() -> PatientTimelineService:
    """Get singleton instance of PatientTimelineService."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = PatientTimelineService()
    return _service_instance


def reset_patient_timeline_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
