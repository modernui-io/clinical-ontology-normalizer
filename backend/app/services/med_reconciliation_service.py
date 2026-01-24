"""Medication Reconciliation Service.

Compares medication lists and identifies discrepancies with severity classification.
Supports admission vs discharge and EHR vs patient-reported comparisons.
"""

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class DiscrepancyType(str, Enum):
    NEW = "new"
    DISCONTINUED = "discontinued"
    DOSE_CHANGE = "dose_change"
    DUPLICATE = "duplicate"
    FREQUENCY_CHANGE = "frequency_change"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Medication classes considered high-risk for discrepancies
HIGH_RISK_CLASSES = {
    "anticoagulant", "insulin", "opioid", "antiarrhythmic",
    "immunosuppressant", "chemotherapy",
}

# Classes considered low-risk (supplements, vitamins)
LOW_RISK_CLASSES = {
    "supplement", "vitamin", "mineral", "probiotic", "herbal",
}


@dataclass
class Medication:
    """Represents a medication entry."""

    name: str
    dose: str = ""
    frequency: str = ""
    route: str = ""
    drug_class: str = ""
    rxnorm_code: str = ""

    @property
    def normalized_name(self) -> str:
        return self.name.strip().lower()


@dataclass
class Discrepancy:
    """A detected discrepancy between medication lists."""

    type: DiscrepancyType
    severity: Severity
    medication_name: str
    details: str
    source_med: Medication | None = None
    target_med: Medication | None = None


@dataclass
class ReconciliationResult:
    """Result of a medication reconciliation."""

    id: str
    source_label: str
    target_label: str
    matched: list[tuple[Medication, Medication]]
    discrepancies: list[Discrepancy]
    source_count: int = 0
    target_count: int = 0


class MedReconciliationService:
    """Service for comparing medication lists and detecting discrepancies."""

    def __init__(self):
        self._results: dict[str, ReconciliationResult] = {}
        self._lock = Lock()

    def reconcile(
        self,
        source_meds: list[dict[str, str]],
        target_meds: list[dict[str, str]],
        source_label: str = "admission",
        target_label: str = "discharge",
    ) -> ReconciliationResult:
        """Compare two medication lists and identify discrepancies.

        Args:
            source_meds: List of medication dicts (name, dose, frequency, route, drug_class)
            target_meds: Same format as source_meds
            source_label: Label for the source list (e.g., "admission")
            target_label: Label for the target list (e.g., "discharge")

        Returns:
            ReconciliationResult with matches and discrepancies
        """
        source = [Medication(**m) for m in source_meds]
        target = [Medication(**m) for m in target_meds]

        matched = []
        discrepancies = []
        source_matched = set()
        target_matched = set()

        # Match medications by normalized name or rxnorm code
        for i, s_med in enumerate(source):
            for j, t_med in enumerate(target):
                if j in target_matched:
                    continue
                if self._is_match(s_med, t_med):
                    source_matched.add(i)
                    target_matched.add(j)
                    matched.append((s_med, t_med))

                    # Check for dose/frequency changes
                    if s_med.dose and t_med.dose and s_med.dose != t_med.dose:
                        discrepancies.append(Discrepancy(
                            type=DiscrepancyType.DOSE_CHANGE,
                            severity=self._classify_severity(s_med, DiscrepancyType.DOSE_CHANGE),
                            medication_name=s_med.name,
                            details=f"Dose changed from {s_med.dose} to {t_med.dose}",
                            source_med=s_med,
                            target_med=t_med,
                        ))
                    if s_med.frequency and t_med.frequency and s_med.frequency != t_med.frequency:
                        discrepancies.append(Discrepancy(
                            type=DiscrepancyType.FREQUENCY_CHANGE,
                            severity=self._classify_severity(s_med, DiscrepancyType.FREQUENCY_CHANGE),
                            medication_name=s_med.name,
                            details=f"Frequency changed from {s_med.frequency} to {t_med.frequency}",
                            source_med=s_med,
                            target_med=t_med,
                        ))
                    break

        # Discontinued: in source but not target
        for i, s_med in enumerate(source):
            if i not in source_matched:
                discrepancies.append(Discrepancy(
                    type=DiscrepancyType.DISCONTINUED,
                    severity=self._classify_severity(s_med, DiscrepancyType.DISCONTINUED),
                    medication_name=s_med.name,
                    details=f"{s_med.name} discontinued from {source_label} to {target_label}",
                    source_med=s_med,
                ))

        # New: in target but not source
        for j, t_med in enumerate(target):
            if j not in target_matched:
                discrepancies.append(Discrepancy(
                    type=DiscrepancyType.NEW,
                    severity=self._classify_severity(t_med, DiscrepancyType.NEW),
                    medication_name=t_med.name,
                    details=f"{t_med.name} added in {target_label}",
                    target_med=t_med,
                ))

        # Check for duplicates within target list
        seen_names = {}
        for j, t_med in enumerate(target):
            norm = t_med.normalized_name
            if norm in seen_names:
                discrepancies.append(Discrepancy(
                    type=DiscrepancyType.DUPLICATE,
                    severity=Severity.MEDIUM,
                    medication_name=t_med.name,
                    details=f"Duplicate medication: {t_med.name} appears multiple times in {target_label}",
                    target_med=t_med,
                ))
            else:
                seen_names[norm] = j

        result = ReconciliationResult(
            id=str(uuid.uuid4()),
            source_label=source_label,
            target_label=target_label,
            matched=matched,
            discrepancies=discrepancies,
            source_count=len(source),
            target_count=len(target),
        )

        with self._lock:
            self._results[result.id] = result

        return result

    def get_result(self, reconciliation_id: str) -> ReconciliationResult | None:
        """Retrieve a previous reconciliation result by ID."""
        with self._lock:
            return self._results.get(reconciliation_id)

    def _is_match(self, med1: Medication, med2: Medication) -> bool:
        """Check if two medications represent the same drug."""
        if med1.rxnorm_code and med2.rxnorm_code:
            return med1.rxnorm_code == med2.rxnorm_code
        return med1.normalized_name == med2.normalized_name

    def _classify_severity(self, med: Medication, disc_type: DiscrepancyType) -> Severity:
        """Classify severity based on drug class and discrepancy type."""
        drug_class = med.drug_class.lower()

        if drug_class in HIGH_RISK_CLASSES:
            return Severity.HIGH

        if drug_class in LOW_RISK_CLASSES:
            return Severity.LOW

        if disc_type == DiscrepancyType.DOSE_CHANGE:
            return Severity.MEDIUM

        if disc_type in (DiscrepancyType.NEW, DiscrepancyType.DISCONTINUED):
            if drug_class in HIGH_RISK_CLASSES:
                return Severity.HIGH
            return Severity.MEDIUM

        return Severity.LOW


# Singleton
_med_reconciliation_service: MedReconciliationService | None = None


def get_med_reconciliation_service() -> MedReconciliationService:
    global _med_reconciliation_service
    if _med_reconciliation_service is None:
        _med_reconciliation_service = MedReconciliationService()
    return _med_reconciliation_service


def reset_med_reconciliation_service() -> None:
    global _med_reconciliation_service
    _med_reconciliation_service = None
