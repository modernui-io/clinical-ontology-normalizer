"""Medication Reconciliation Service.

This module provides comprehensive medication reconciliation capabilities for
comparing medication lists across care transitions, detecting discrepancies,
identifying potential duplicates, and generating reconciliation reports.

Key Features:
- Compare admission vs discharge medications
- Compare home meds vs inpatient meds
- Detect therapeutic duplicates (e.g., two statins)
- Identify high-risk discrepancies (anticoagulants, insulin, opioids)
- Support for generic/brand name matching using RxNormService

Clinical Use Cases:
- Hospital admission medication reconciliation
- Discharge medication reconciliation
- Care transition safety checks
- Duplicate therapy detection
- High-risk medication monitoring
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from threading import Lock
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.rxnorm_service import RxNormService

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================


class DiscrepancyType(str, Enum):
    """Type of medication discrepancy."""

    ADDITION = "addition"  # New medication added
    DISCONTINUATION = "discontinuation"  # Medication stopped
    DOSE_CHANGE = "dose_change"  # Dose was changed
    FREQUENCY_CHANGE = "frequency_change"  # Frequency was changed
    ROUTE_CHANGE = "route_change"  # Route was changed
    THERAPEUTIC_DUPLICATION = "therapeutic_duplication"  # Same drug class
    BRAND_GENERIC_SWAP = "brand_generic_swap"  # Brand to generic or vice versa
    FORMULATION_CHANGE = "formulation_change"  # Different formulation


class DiscrepancySeverity(str, Enum):
    """Severity level of a discrepancy."""

    HIGH = "high"  # Requires immediate attention
    MODERATE = "moderate"  # Should be reviewed
    LOW = "low"  # Informational


class MedicationRoute(str, Enum):
    """Common medication administration routes."""

    ORAL = "oral"
    INTRAVENOUS = "intravenous"
    INTRAMUSCULAR = "intramuscular"
    SUBCUTANEOUS = "subcutaneous"
    TOPICAL = "topical"
    INHALATION = "inhalation"
    RECTAL = "rectal"
    OPHTHALMIC = "ophthalmic"
    OTIC = "otic"
    NASAL = "nasal"
    TRANSDERMAL = "transdermal"
    SUBLINGUAL = "sublingual"
    BUCCAL = "buccal"
    OTHER = "other"


class ReconciliationStatus(str, Enum):
    """Status of the reconciliation."""

    PENDING = "pending"  # Not yet reviewed
    IN_PROGRESS = "in_progress"  # Under review
    COMPLETED = "completed"  # Review complete
    REQUIRES_ACTION = "requires_action"  # Discrepancies need resolution


# High-risk medication categories that require special attention
HIGH_RISK_CATEGORIES = {
    "anticoagulant": ["warfarin", "heparin", "enoxaparin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban"],
    "insulin": ["insulin", "insulin lispro", "insulin aspart", "insulin glargine", "insulin detemir", "insulin degludec"],
    "opioid": ["morphine", "oxycodone", "hydrocodone", "fentanyl", "tramadol", "methadone", "hydromorphone", "codeine"],
    "immunosuppressant": ["tacrolimus", "cyclosporine", "mycophenolate", "azathioprine", "sirolimus"],
    "antiarrhythmic": ["amiodarone", "flecainide", "propafenone", "sotalol", "dofetilide"],
    "chemotherapy": ["methotrexate", "cyclophosphamide", "fluorouracil", "doxorubicin", "vincristine"],
    "hypoglycemic": ["glipizide", "glyburide", "glimepiride", "repaglinide", "nateglinide"],
    "sedative": ["midazolam", "lorazepam", "diazepam", "alprazolam", "clonazepam"],
    "digoxin": ["digoxin"],
    "lithium": ["lithium"],
}

# Therapeutic drug classes for duplicate detection
THERAPEUTIC_CLASSES = {
    "statin": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin", "fluvastatin", "pitavastatin"],
    "ace_inhibitor": ["lisinopril", "enalapril", "ramipril", "benazepril", "captopril", "quinapril", "fosinopril"],
    "arb": ["losartan", "valsartan", "irbesartan", "olmesartan", "candesartan", "telmisartan", "azilsartan"],
    "beta_blocker": ["metoprolol", "atenolol", "carvedilol", "bisoprolol", "propranolol", "nebivolol", "labetalol"],
    "calcium_channel_blocker": ["amlodipine", "diltiazem", "verapamil", "nifedipine", "felodipine"],
    "thiazide_diuretic": ["hydrochlorothiazide", "chlorthalidone", "indapamide", "metolazone"],
    "loop_diuretic": ["furosemide", "bumetanide", "torsemide", "ethacrynic acid"],
    "ppi": ["omeprazole", "pantoprazole", "esomeprazole", "lansoprazole", "rabeprazole", "dexlansoprazole"],
    "h2_blocker": ["famotidine", "ranitidine", "cimetidine", "nizatidine"],
    "ssri": ["sertraline", "fluoxetine", "paroxetine", "citalopram", "escitalopram", "fluvoxamine"],
    "snri": ["venlafaxine", "duloxetine", "desvenlafaxine", "levomilnacipran"],
    "benzodiazepine": ["alprazolam", "lorazepam", "diazepam", "clonazepam", "temazepam", "oxazepam"],
    "anticoagulant": ["warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban"],
    "antiplatelet": ["aspirin", "clopidogrel", "ticagrelor", "prasugrel"],
    "nsaid": ["ibuprofen", "naproxen", "meloxicam", "celecoxib", "diclofenac", "indomethacin", "ketorolac"],
    "opioid": ["morphine", "oxycodone", "hydrocodone", "fentanyl", "tramadol", "hydromorphone", "codeine"],
    "thyroid_hormone": ["levothyroxine", "liothyronine"],
    "bisphosphonate": ["alendronate", "risedronate", "ibandronate", "zoledronic acid"],
    "sulfonylurea": ["glipizide", "glyburide", "glimepiride"],
    "dpp4_inhibitor": ["sitagliptin", "saxagliptin", "linagliptin", "alogliptin"],
    "sglt2_inhibitor": ["empagliflozin", "canagliflozin", "dapagliflozin", "ertugliflozin"],
    "glp1_agonist": ["liraglutide", "semaglutide", "dulaglutide", "exenatide"],
    "inhaled_corticosteroid": ["fluticasone", "budesonide", "beclomethasone", "mometasone", "ciclesonide"],
    "laba": ["salmeterol", "formoterol", "vilanterol", "olodaterol"],
    "lama": ["tiotropium", "umeclidinium", "glycopyrrolate", "aclidinium"],
}


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class MedicationEntry:
    """A medication entry in a medication list.

    Represents a single medication with its dosing information.
    This is the core unit for reconciliation comparisons.
    """

    drug_name: str  # Medication name (can be brand or generic)
    dose: str = ""  # Dose amount (e.g., "10 mg", "500 mg")
    frequency: str = ""  # Dosing frequency (e.g., "twice daily", "BID")
    route: str = ""  # Administration route (e.g., "oral", "IV")
    start_date: date | None = None  # When medication was started
    end_date: date | None = None  # When medication was stopped (if applicable)
    prescriber: str = ""  # Prescribing provider
    indication: str = ""  # Reason for medication
    is_prn: bool = False  # As needed medication
    notes: str = ""  # Additional notes

    # Computed/resolved fields (populated by service)
    normalized_name: str = ""  # Generic name (resolved via RxNorm)
    rxcui: str = ""  # RxNorm CUI if available
    therapeutic_class: str = ""  # Drug class
    is_high_risk: bool = False  # High-alert medication flag

    def __post_init__(self) -> None:
        """Normalize fields after initialization."""
        self.drug_name = self.drug_name.strip()
        self.dose = self.dose.strip()
        self.frequency = self.frequency.strip().upper() if self.frequency else ""
        self.route = self.route.strip().lower() if self.route else ""


@dataclass
class MedicationMatch:
    """A matched medication between two lists."""

    source_medication: MedicationEntry
    target_medication: MedicationEntry
    match_confidence: float = 1.0  # How confident is the match (0-1)
    match_type: str = "exact"  # exact, generic, brand, fuzzy
    has_changes: bool = False  # Whether there are any differences


@dataclass
class DiscrepancyAlert:
    """Alert for a medication discrepancy.

    Represents a specific discrepancy found during reconciliation
    that requires clinical attention.
    """

    id: str  # Unique identifier
    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity
    description: str
    clinical_significance: str
    recommended_action: str
    medications_involved: list[MedicationEntry] = field(default_factory=list)
    source_list_name: str = ""  # e.g., "home medications"
    target_list_name: str = ""  # e.g., "discharge medications"


@dataclass
class TherapeuticDuplicate:
    """Represents a therapeutic duplication finding."""

    therapeutic_class: str
    medications: list[MedicationEntry]
    severity: DiscrepancySeverity
    clinical_rationale: str
    recommendation: str


@dataclass
class ReconciliationResult:
    """Complete result of medication reconciliation.

    Contains all matches, additions, discontinuations, changes,
    and alerts found during reconciliation.
    """

    id: str  # Unique reconciliation ID
    source_list_name: str  # Name of first list (e.g., "admission medications")
    target_list_name: str  # Name of second list (e.g., "discharge medications")
    reconciliation_timestamp: datetime
    status: ReconciliationStatus

    # Matched medications (same medication in both lists)
    matches: list[MedicationMatch] = field(default_factory=list)

    # New medications (in target but not source)
    additions: list[MedicationEntry] = field(default_factory=list)

    # Stopped medications (in source but not target)
    discontinuations: list[MedicationEntry] = field(default_factory=list)

    # Medications with changes (dose, frequency, route changes)
    changes: list[MedicationMatch] = field(default_factory=list)

    # All discrepancy alerts
    alerts: list[DiscrepancyAlert] = field(default_factory=list)

    # Therapeutic duplicates found
    therapeutic_duplicates: list[TherapeuticDuplicate] = field(default_factory=list)

    # Summary statistics
    total_source_medications: int = 0
    total_target_medications: int = 0
    high_risk_discrepancies: int = 0
    requires_pharmacist_review: bool = False

    # Additional metadata
    notes: str = ""
    reviewed_by: str = ""
    reviewed_at: datetime | None = None


@dataclass
class MedicationListAnalysis:
    """Analysis result for a single medication list."""

    id: str
    list_name: str
    analysis_timestamp: datetime
    total_medications: int
    high_risk_medications: list[MedicationEntry]
    therapeutic_duplicates: list[TherapeuticDuplicate]
    potential_interactions: list[str]  # References to drug interaction findings
    alerts: list[DiscrepancyAlert]
    medications_by_class: dict[str, list[MedicationEntry]]


# ============================================================================
# Medication Reconciliation Service
# ============================================================================


class MedicationReconciliationService:
    """Service for medication reconciliation.

    Provides comprehensive medication reconciliation capabilities for comparing
    medication lists across care transitions, detecting discrepancies,
    identifying potential duplicates, and generating reconciliation reports.

    Usage:
        service = get_medication_reconciliation_service()

        # Compare admission vs discharge
        result = service.compare_medication_lists(
            source_list=admission_meds,
            target_list=discharge_meds,
            source_name="Admission Medications",
            target_name="Discharge Medications",
        )

        # Check for issues
        if result.high_risk_discrepancies > 0:
            print("High-risk discrepancies found!")
            for alert in result.alerts:
                if alert.severity == DiscrepancySeverity.HIGH:
                    print(f"  - {alert.description}")

        # Analyze single list for duplicates
        analysis = service.analyze_medication_list(
            medications=current_meds,
            list_name="Current Medications",
        )
    """

    def __init__(self, use_rxnorm: bool = True) -> None:
        """Initialize the medication reconciliation service.

        Args:
            use_rxnorm: Whether to use RxNormService for drug name normalization.
        """
        self._rxnorm_service: "RxNormService | None" = None
        self._use_rxnorm = use_rxnorm
        self._reconciliation_store: dict[str, ReconciliationResult] = {}

        if use_rxnorm:
            self._init_rxnorm()

        logger.info("Medication reconciliation service initialized")

    def _init_rxnorm(self) -> None:
        """Initialize RxNorm service integration."""
        try:
            from app.services.rxnorm_service import get_rxnorm_service
            self._rxnorm_service = get_rxnorm_service()
            logger.info("RxNorm service integration enabled for medication reconciliation")
        except Exception as e:
            logger.warning(f"Failed to initialize RxNorm service: {e}")
            self._rxnorm_service = None

    def _normalize_medication(self, med: MedicationEntry) -> MedicationEntry:
        """Normalize medication entry using RxNorm.

        Resolves brand names to generic, extracts therapeutic class,
        and identifies high-risk medications.
        """
        # Get generic name
        if self._rxnorm_service:
            try:
                generic = self._rxnorm_service.normalize_to_generic(med.drug_name)
                if generic:
                    med.normalized_name = generic.lower()
                else:
                    med.normalized_name = med.drug_name.lower()

                # Get therapeutic class
                classes = self._rxnorm_service.get_therapeutic_class(med.drug_name)
                if classes:
                    med.therapeutic_class = classes[0]

                # Get RxCUI
                result = self._rxnorm_service.lookup_drug(med.drug_name)
                if result.found and result.drug_info:
                    med.rxcui = result.drug_info.rxcui

            except Exception as e:
                logger.debug(f"RxNorm lookup failed for {med.drug_name}: {e}")
                med.normalized_name = med.drug_name.lower()
        else:
            med.normalized_name = med.drug_name.lower()

        # Check if high-risk
        med.is_high_risk = self._is_high_risk_medication(med.normalized_name)

        # Try to assign therapeutic class if not set
        if not med.therapeutic_class:
            med.therapeutic_class = self._get_therapeutic_class(med.normalized_name)

        return med

    def _is_high_risk_medication(self, drug_name: str) -> bool:
        """Check if a medication is high-risk."""
        drug_lower = drug_name.lower()
        for category, drugs in HIGH_RISK_CATEGORIES.items():
            for drug in drugs:
                if drug in drug_lower or drug_lower in drug:
                    return True
        return False

    def _get_therapeutic_class(self, drug_name: str) -> str:
        """Get therapeutic class for a medication."""
        drug_lower = drug_name.lower()
        for class_name, drugs in THERAPEUTIC_CLASSES.items():
            for drug in drugs:
                if drug in drug_lower or drug_lower in drug:
                    return class_name
        return ""

    def _get_high_risk_category(self, drug_name: str) -> str:
        """Get the high-risk category for a medication."""
        drug_lower = drug_name.lower()
        for category, drugs in HIGH_RISK_CATEGORIES.items():
            for drug in drugs:
                if drug in drug_lower or drug_lower in drug:
                    return category
        return ""

    def _medications_match(
        self,
        med1: MedicationEntry,
        med2: MedicationEntry,
    ) -> tuple[bool, str, float]:
        """Check if two medications are the same drug.

        Returns:
            Tuple of (match, match_type, confidence)
        """
        name1 = med1.normalized_name or med1.drug_name.lower()
        name2 = med2.normalized_name or med2.drug_name.lower()

        # Exact match
        if name1 == name2:
            return True, "exact", 1.0

        # Check if both are the same when normalized via RxNorm
        if med1.rxcui and med2.rxcui and med1.rxcui == med2.rxcui:
            return True, "rxcui", 1.0

        # Brand/generic match
        if self._rxnorm_service:
            try:
                # Check if one is brand of the other
                gen1 = self._rxnorm_service.normalize_to_generic(med1.drug_name)
                gen2 = self._rxnorm_service.normalize_to_generic(med2.drug_name)

                if gen1 and gen2 and gen1.lower() == gen2.lower():
                    return True, "generic", 0.95

            except Exception:
                pass

        # Partial match (contains)
        if name1 in name2 or name2 in name1:
            return True, "partial", 0.8

        return False, "none", 0.0

    def _detect_changes(
        self,
        source: MedicationEntry,
        target: MedicationEntry,
    ) -> list[DiscrepancyType]:
        """Detect changes between two matched medications."""
        changes = []

        # Dose change
        if source.dose and target.dose and source.dose.lower() != target.dose.lower():
            changes.append(DiscrepancyType.DOSE_CHANGE)

        # Frequency change
        if source.frequency and target.frequency:
            if source.frequency.upper() != target.frequency.upper():
                changes.append(DiscrepancyType.FREQUENCY_CHANGE)

        # Route change
        if source.route and target.route:
            if source.route.lower() != target.route.lower():
                changes.append(DiscrepancyType.ROUTE_CHANGE)

        # Brand/generic swap
        if source.drug_name.lower() != target.drug_name.lower():
            if source.normalized_name == target.normalized_name:
                changes.append(DiscrepancyType.BRAND_GENERIC_SWAP)

        return changes

    def _create_alert(
        self,
        discrepancy_type: DiscrepancyType,
        medications: list[MedicationEntry],
        source_name: str,
        target_name: str,
        **kwargs: Any,
    ) -> DiscrepancyAlert:
        """Create a discrepancy alert."""
        # Determine severity
        is_high_risk = any(med.is_high_risk for med in medications)

        severity = DiscrepancySeverity.LOW
        if is_high_risk:
            severity = DiscrepancySeverity.HIGH
        elif discrepancy_type in [DiscrepancyType.DISCONTINUATION, DiscrepancyType.ADDITION]:
            severity = DiscrepancySeverity.MODERATE
        elif discrepancy_type in [DiscrepancyType.DOSE_CHANGE, DiscrepancyType.THERAPEUTIC_DUPLICATION]:
            severity = DiscrepancySeverity.MODERATE

        # Generate description and recommendations
        med_names = ", ".join(med.drug_name for med in medications)
        description = ""
        clinical_significance = ""
        recommended_action = ""

        if discrepancy_type == DiscrepancyType.ADDITION:
            description = f"New medication added: {med_names}"
            clinical_significance = "New medication may require patient education and monitoring."
            recommended_action = "Verify indication and ensure no contraindications."

        elif discrepancy_type == DiscrepancyType.DISCONTINUATION:
            description = f"Medication discontinued: {med_names}"
            clinical_significance = "Discontinued medication may need tapering or substitution."
            recommended_action = "Confirm intentional discontinuation and document reason."

        elif discrepancy_type == DiscrepancyType.DOSE_CHANGE:
            description = f"Dose changed for: {med_names}"
            clinical_significance = "Dose changes may affect efficacy or safety."
            recommended_action = "Verify dose change is appropriate and document rationale."

        elif discrepancy_type == DiscrepancyType.FREQUENCY_CHANGE:
            description = f"Frequency changed for: {med_names}"
            clinical_significance = "Frequency changes may affect drug levels and efficacy."
            recommended_action = "Verify frequency change and update patient instructions."

        elif discrepancy_type == DiscrepancyType.ROUTE_CHANGE:
            description = f"Route changed for: {med_names}"
            clinical_significance = "Route changes may affect bioavailability and onset."
            recommended_action = "Ensure appropriate formulation for new route."

        elif discrepancy_type == DiscrepancyType.THERAPEUTIC_DUPLICATION:
            description = f"Therapeutic duplication detected: {med_names}"
            clinical_significance = "Multiple drugs in same class may increase adverse effects."
            recommended_action = "Review for intentional combination therapy vs duplication."

        elif discrepancy_type == DiscrepancyType.BRAND_GENERIC_SWAP:
            description = f"Brand/generic substitution: {med_names}"
            clinical_significance = "Generally equivalent; narrow therapeutic index drugs need monitoring."
            recommended_action = "Verify patient tolerance of substitution."

        # Enhance for high-risk medications
        if is_high_risk:
            high_risk_cats = set()
            for med in medications:
                cat = self._get_high_risk_category(med.normalized_name or med.drug_name)
                if cat:
                    high_risk_cats.add(cat)

            if high_risk_cats:
                clinical_significance += f" HIGH-ALERT medication category: {', '.join(high_risk_cats)}."
                recommended_action += " Requires pharmacist verification."

        return DiscrepancyAlert(
            id=str(uuid.uuid4()),
            discrepancy_type=discrepancy_type,
            severity=severity,
            description=description,
            clinical_significance=clinical_significance,
            recommended_action=recommended_action,
            medications_involved=medications,
            source_list_name=source_name,
            target_list_name=target_name,
        )

    def compare_medication_lists(
        self,
        source_list: list[MedicationEntry],
        target_list: list[MedicationEntry],
        source_name: str = "Source Medications",
        target_name: str = "Target Medications",
    ) -> ReconciliationResult:
        """Compare two medication lists and identify discrepancies.

        This is the primary reconciliation method. It compares a source list
        (e.g., home medications) against a target list (e.g., discharge medications)
        and identifies all discrepancies.

        Args:
            source_list: First medication list (e.g., admission meds)
            target_list: Second medication list (e.g., discharge meds)
            source_name: Display name for source list
            target_name: Display name for target list

        Returns:
            ReconciliationResult with all findings.
        """
        reconciliation_id = str(uuid.uuid4())

        # Normalize all medications
        normalized_source = [self._normalize_medication(med) for med in source_list]
        normalized_target = [self._normalize_medication(med) for med in target_list]

        # Track which medications have been matched
        source_matched = [False] * len(normalized_source)
        target_matched = [False] * len(normalized_target)

        matches: list[MedicationMatch] = []
        changes: list[MedicationMatch] = []
        alerts: list[DiscrepancyAlert] = []

        # Find matches
        for i, source_med in enumerate(normalized_source):
            for j, target_med in enumerate(normalized_target):
                if target_matched[j]:
                    continue

                is_match, match_type, confidence = self._medications_match(source_med, target_med)

                if is_match:
                    source_matched[i] = True
                    target_matched[j] = True

                    # Check for changes
                    change_types = self._detect_changes(source_med, target_med)
                    has_changes = len(change_types) > 0

                    match = MedicationMatch(
                        source_medication=source_med,
                        target_medication=target_med,
                        match_confidence=confidence,
                        match_type=match_type,
                        has_changes=has_changes,
                    )

                    if has_changes:
                        changes.append(match)
                        # Create alerts for each change type
                        for change_type in change_types:
                            alerts.append(self._create_alert(
                                change_type,
                                [source_med, target_med],
                                source_name,
                                target_name,
                            ))
                    else:
                        matches.append(match)

                    break

        # Find discontinuations (in source but not target)
        discontinuations: list[MedicationEntry] = []
        for i, source_med in enumerate(normalized_source):
            if not source_matched[i]:
                discontinuations.append(source_med)
                alerts.append(self._create_alert(
                    DiscrepancyType.DISCONTINUATION,
                    [source_med],
                    source_name,
                    target_name,
                ))

        # Find additions (in target but not source)
        additions: list[MedicationEntry] = []
        for j, target_med in enumerate(normalized_target):
            if not target_matched[j]:
                additions.append(target_med)
                alerts.append(self._create_alert(
                    DiscrepancyType.ADDITION,
                    [target_med],
                    source_name,
                    target_name,
                ))

        # Check for therapeutic duplicates in target list
        therapeutic_duplicates = self._find_therapeutic_duplicates(normalized_target)
        for dup in therapeutic_duplicates:
            alerts.append(self._create_alert(
                DiscrepancyType.THERAPEUTIC_DUPLICATION,
                dup.medications,
                source_name,
                target_name,
            ))

        # Calculate summary stats
        high_risk_count = sum(1 for alert in alerts if alert.severity == DiscrepancySeverity.HIGH)
        requires_review = high_risk_count > 0 or len(therapeutic_duplicates) > 0

        # Determine status
        status = ReconciliationStatus.COMPLETED
        if high_risk_count > 0:
            status = ReconciliationStatus.REQUIRES_ACTION
        elif len(alerts) > 0:
            status = ReconciliationStatus.PENDING

        result = ReconciliationResult(
            id=reconciliation_id,
            source_list_name=source_name,
            target_list_name=target_name,
            reconciliation_timestamp=datetime.utcnow(),
            status=status,
            matches=matches,
            additions=additions,
            discontinuations=discontinuations,
            changes=changes,
            alerts=alerts,
            therapeutic_duplicates=therapeutic_duplicates,
            total_source_medications=len(source_list),
            total_target_medications=len(target_list),
            high_risk_discrepancies=high_risk_count,
            requires_pharmacist_review=requires_review,
        )

        # Store for later retrieval
        self._reconciliation_store[reconciliation_id] = result

        logger.info(
            f"Reconciliation {reconciliation_id}: {len(source_list)} source, "
            f"{len(target_list)} target, {len(alerts)} alerts, {high_risk_count} high-risk"
        )

        return result

    def _find_therapeutic_duplicates(
        self,
        medications: list[MedicationEntry],
    ) -> list[TherapeuticDuplicate]:
        """Find therapeutic duplicates in a medication list."""
        duplicates: list[TherapeuticDuplicate] = []

        # Group by therapeutic class
        by_class: dict[str, list[MedicationEntry]] = {}
        for med in medications:
            if med.therapeutic_class:
                if med.therapeutic_class not in by_class:
                    by_class[med.therapeutic_class] = []
                by_class[med.therapeutic_class].append(med)

        # Find classes with multiple medications
        for class_name, meds in by_class.items():
            if len(meds) > 1:
                # Determine severity based on class
                severity = DiscrepancySeverity.MODERATE
                rationale = f"Multiple {class_name} medications may increase side effects."
                recommendation = "Review for intentional combination vs unintentional duplication."

                # Some combinations are more concerning
                if class_name in ["anticoagulant", "opioid", "benzodiazepine", "nsaid"]:
                    severity = DiscrepancySeverity.HIGH
                    rationale = f"Multiple {class_name} medications significantly increase risk of adverse events."
                    recommendation = "Pharmacist review required. Consider discontinuing one agent."

                duplicates.append(TherapeuticDuplicate(
                    therapeutic_class=class_name,
                    medications=meds,
                    severity=severity,
                    clinical_rationale=rationale,
                    recommendation=recommendation,
                ))

        return duplicates

    def analyze_medication_list(
        self,
        medications: list[MedicationEntry],
        list_name: str = "Medication List",
    ) -> MedicationListAnalysis:
        """Analyze a single medication list for issues.

        Identifies high-risk medications, therapeutic duplicates,
        and potential issues within a single list.

        Args:
            medications: List of medications to analyze
            list_name: Display name for the list

        Returns:
            MedicationListAnalysis with findings.
        """
        analysis_id = str(uuid.uuid4())

        # Normalize all medications
        normalized = [self._normalize_medication(med) for med in medications]

        # Find high-risk medications
        high_risk = [med for med in normalized if med.is_high_risk]

        # Find therapeutic duplicates
        duplicates = self._find_therapeutic_duplicates(normalized)

        # Group by therapeutic class
        by_class: dict[str, list[MedicationEntry]] = {}
        for med in normalized:
            class_name = med.therapeutic_class or "unclassified"
            if class_name not in by_class:
                by_class[class_name] = []
            by_class[class_name].append(med)

        # Create alerts
        alerts: list[DiscrepancyAlert] = []

        for dup in duplicates:
            alerts.append(DiscrepancyAlert(
                id=str(uuid.uuid4()),
                discrepancy_type=DiscrepancyType.THERAPEUTIC_DUPLICATION,
                severity=dup.severity,
                description=f"Therapeutic duplication: {', '.join(m.drug_name for m in dup.medications)}",
                clinical_significance=dup.clinical_rationale,
                recommended_action=dup.recommendation,
                medications_involved=dup.medications,
                source_list_name=list_name,
                target_list_name=list_name,
            ))

        return MedicationListAnalysis(
            id=analysis_id,
            list_name=list_name,
            analysis_timestamp=datetime.utcnow(),
            total_medications=len(medications),
            high_risk_medications=high_risk,
            therapeutic_duplicates=duplicates,
            potential_interactions=[],  # Would integrate with drug interaction service
            alerts=alerts,
            medications_by_class=by_class,
        )

    def get_reconciliation_report(self, reconciliation_id: str) -> ReconciliationResult | None:
        """Retrieve a stored reconciliation report.

        Args:
            reconciliation_id: ID of the reconciliation to retrieve

        Returns:
            ReconciliationResult or None if not found.
        """
        return self._reconciliation_store.get(reconciliation_id)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service statistics.
        """
        return {
            "total_reconciliations_stored": len(self._reconciliation_store),
            "rxnorm_enabled": self._rxnorm_service is not None,
            "high_risk_categories": len(HIGH_RISK_CATEGORIES),
            "therapeutic_classes": len(THERAPEUTIC_CLASSES),
        }


# ============================================================================
# Singleton Pattern
# ============================================================================

_medication_reconciliation_service: MedicationReconciliationService | None = None
_medication_reconciliation_lock = Lock()


def get_medication_reconciliation_service() -> MedicationReconciliationService:
    """Get the singleton MedicationReconciliationService instance.

    Returns:
        The singleton MedicationReconciliationService instance.
    """
    global _medication_reconciliation_service

    if _medication_reconciliation_service is None:
        with _medication_reconciliation_lock:
            if _medication_reconciliation_service is None:
                logger.info("Creating singleton MedicationReconciliationService instance")
                _medication_reconciliation_service = MedicationReconciliationService()

    return _medication_reconciliation_service


def reset_medication_reconciliation_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _medication_reconciliation_service
    with _medication_reconciliation_lock:
        _medication_reconciliation_service = None
