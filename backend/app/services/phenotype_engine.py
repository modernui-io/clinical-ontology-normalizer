"""Computable Phenotype Engine for Clinical Decision Support.

This module provides a rule-based phenotype evaluation engine that uses
the patient knowledge graph to determine if patients meet criteria for
specific clinical phenotypes (e.g., HFrEF, Type 2 Diabetes, CKD Stage 3+).

Key Features:
- Computable phenotype definitions with inclusion/exclusion criteria
- Temporal filtering (lookback periods)
- Value-based filtering for measurements
- Care gap identification
- Support for custom phenotype definitions

References:
- OHDSI Phenotype Library: https://ohdsi.github.io/PhenotypeLibrary/
- PheKB Phenotype Knowledge Base: https://phekb.org/
- eMERGE Network: https://emerge-network.org/
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType

logger = logging.getLogger(__name__)


class PhenotypeStatus(str, Enum):
    """Status of phenotype evaluation for a patient."""

    PRESENT = "present"  # Patient meets all criteria
    ABSENT = "absent"  # Patient does not meet criteria (exclusion or missing inclusion)
    POSSIBLE = "possible"  # Some criteria met, but insufficient data for certainty
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough data to evaluate


class CriterionLogic(str, Enum):
    """Logic for combining criteria."""

    AND = "and"  # All criteria must be met
    OR = "or"  # At least one criterion must be met
    NOT = "not"  # Criterion must NOT be met (exclusion)


class ValueOperator(str, Enum):
    """Operators for value-based criteria."""

    EQ = "eq"  # Equal to
    NE = "ne"  # Not equal to
    LT = "lt"  # Less than
    LE = "le"  # Less than or equal
    GT = "gt"  # Greater than
    GE = "ge"  # Greater than or equal
    BETWEEN = "between"  # Between two values (inclusive)
    IN = "in"  # In a list of values


@dataclass
class PhenotypeCriterion:
    """A single criterion for phenotype evaluation.

    Attributes:
        name: Human-readable name for this criterion
        concept_codes: OMOP concept IDs that satisfy this criterion
        node_types: Node types to search (default: all clinical types)
        value_field: Property field to check for value-based criteria
        value_operator: Comparison operator for values
        value_threshold: Threshold value(s) for comparison
        lookback_days: How far back to look for matching concepts (None = all time)
        min_occurrences: Minimum number of times concept must appear
        require_current: Only count currently active/valid edges
        assertion_filter: Filter by assertion status (present, absent, possible)
        description: Description of what this criterion represents
    """

    name: str
    concept_codes: list[int]
    node_types: list[NodeType] = field(
        default_factory=lambda: [NodeType.CONDITION, NodeType.DRUG, NodeType.MEASUREMENT]
    )
    value_field: str | None = None
    value_operator: ValueOperator | None = None
    value_threshold: float | list[float] | None = None
    lookback_days: int | None = None
    min_occurrences: int = 1
    require_current: bool = False
    assertion_filter: list[str] | None = None  # ["present", "absent", "possible"]
    description: str = ""


@dataclass
class PhenotypeDefinition:
    """Definition of a computable phenotype.

    Attributes:
        id: Unique identifier for this phenotype
        name: Human-readable name
        description: Detailed description
        inclusion_criteria: Criteria that must be met (AND logic by default)
        exclusion_criteria: Criteria that disqualify the patient
        inclusion_logic: How to combine inclusion criteria (AND or OR)
        care_gap_criteria: Criteria for identifying care gaps
        version: Version of this phenotype definition
        source: Source of the phenotype (e.g., "OHDSI", "PheKB", "custom")
    """

    id: str
    name: str
    description: str
    inclusion_criteria: list[PhenotypeCriterion]
    exclusion_criteria: list[PhenotypeCriterion] = field(default_factory=list)
    inclusion_logic: CriterionLogic = CriterionLogic.AND
    care_gap_criteria: list[PhenotypeCriterion] = field(default_factory=list)
    version: str = "1.0"
    source: str = "custom"


@dataclass
class CriterionResult:
    """Result of evaluating a single criterion.

    Attributes:
        criterion: The criterion that was evaluated
        met: Whether the criterion was met
        matched_concepts: Concepts that matched the criterion
        occurrence_count: Number of matching occurrences
        most_recent_date: Date of most recent matching event
        value: Value if this was a value-based criterion
    """

    criterion: PhenotypeCriterion
    met: bool
    matched_concepts: list[dict[str, Any]] = field(default_factory=list)
    occurrence_count: int = 0
    most_recent_date: datetime | None = None
    value: float | None = None


@dataclass
class CareGap:
    """A care gap identified during phenotype evaluation.

    Attributes:
        criterion: The care gap criterion
        description: Human-readable description of the gap
        severity: Severity level (high, medium, low)
        recommendation: Recommended action to address the gap
    """

    criterion: PhenotypeCriterion
    description: str
    severity: str = "medium"
    recommendation: str = ""


@dataclass
class PhenotypeResult:
    """Result of phenotype evaluation for a patient.

    Attributes:
        phenotype_id: ID of the evaluated phenotype
        patient_id: Patient identifier
        status: Overall phenotype status
        confidence: Confidence in the evaluation (0-1)
        inclusion_results: Results for each inclusion criterion
        exclusion_results: Results for each exclusion criterion
        care_gaps: Identified care gaps
        evaluated_at: When the evaluation was performed
        evidence_summary: Human-readable summary of evidence
    """

    phenotype_id: str
    patient_id: str
    status: PhenotypeStatus
    confidence: float
    inclusion_results: list[CriterionResult] = field(default_factory=list)
    exclusion_results: list[CriterionResult] = field(default_factory=list)
    care_gaps: list[CareGap] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_summary: str = ""

    @property
    def has_care_gaps(self) -> bool:
        """Check if there are any care gaps."""
        return len(self.care_gaps) > 0

    @property
    def is_present(self) -> bool:
        """Check if phenotype is present."""
        return self.status == PhenotypeStatus.PRESENT

    @property
    def inclusion_criteria_met(self) -> int:
        """Count of inclusion criteria met."""
        return sum(1 for r in self.inclusion_results if r.met)

    @property
    def total_inclusion_criteria(self) -> int:
        """Total number of inclusion criteria."""
        return len(self.inclusion_results)


# =============================================================================
# Built-in Phenotype Definitions
# =============================================================================
# These are common clinical phenotypes based on standard definitions.
# OMOP Concept IDs are used for interoperability.
# =============================================================================

# Heart Failure with Reduced Ejection Fraction (HFrEF)
# Based on OHDSI phenotype definitions
HFREF_PHENOTYPE = PhenotypeDefinition(
    id="hfref",
    name="Heart Failure with Reduced Ejection Fraction",
    description="HFrEF: Heart failure with LVEF <= 40%",
    inclusion_criteria=[
        PhenotypeCriterion(
            name="Heart Failure Diagnosis",
            concept_codes=[
                316139,  # Heart failure
                319835,  # Congestive heart failure
                443580,  # Heart failure with reduced ejection fraction
                4215802,  # Systolic heart failure
            ],
            node_types=[NodeType.CONDITION],
            min_occurrences=1,
            assertion_filter=["present"],
            description="Diagnosis of heart failure",
        ),
        PhenotypeCriterion(
            name="Reduced Ejection Fraction",
            concept_codes=[
                3004249,  # Left ventricular ejection fraction (LVEF)
            ],
            node_types=[NodeType.MEASUREMENT],
            value_field="value",
            value_operator=ValueOperator.LE,
            value_threshold=40.0,
            lookback_days=365,
            description="LVEF <= 40%",
        ),
    ],
    exclusion_criteria=[
        PhenotypeCriterion(
            name="Preserved Ejection Fraction",
            concept_codes=[3004249],  # LVEF
            node_types=[NodeType.MEASUREMENT],
            value_field="value",
            value_operator=ValueOperator.GE,
            value_threshold=50.0,
            lookback_days=90,
            description="Recent LVEF >= 50% would indicate HFpEF, not HFrEF",
        ),
    ],
    care_gap_criteria=[
        PhenotypeCriterion(
            name="ACE Inhibitor or ARB",
            concept_codes=[
                1308216,  # ACE inhibitors
                1335471,  # Angiotensin receptor blockers
                1310756,  # Lisinopril
                1341927,  # Losartan
            ],
            node_types=[NodeType.DRUG],
            lookback_days=180,
            min_occurrences=1,
            description="ACE-I or ARB therapy for HFrEF",
        ),
        PhenotypeCriterion(
            name="Beta Blocker",
            concept_codes=[
                1314577,  # Beta blockers
                1314002,  # Carvedilol
                1386957,  # Metoprolol
            ],
            node_types=[NodeType.DRUG],
            lookback_days=180,
            min_occurrences=1,
            description="Beta blocker therapy for HFrEF",
        ),
    ],
    source="OHDSI",
)

# Type 2 Diabetes Mellitus
T2DM_PHENOTYPE = PhenotypeDefinition(
    id="t2dm",
    name="Type 2 Diabetes Mellitus",
    description="Type 2 diabetes based on diagnosis, medications, or lab values",
    inclusion_criteria=[
        PhenotypeCriterion(
            name="T2DM Diagnosis",
            concept_codes=[
                201826,  # Type 2 diabetes mellitus
                4193704,  # Type 2 diabetes mellitus without complication
                443732,  # Diabetes mellitus type 2 with peripheral circulatory disorder
            ],
            node_types=[NodeType.CONDITION],
            min_occurrences=1,
            assertion_filter=["present"],
            description="Diagnosis of type 2 diabetes",
        ),
    ],
    inclusion_logic=CriterionLogic.OR,  # Any of these criteria
    exclusion_criteria=[
        PhenotypeCriterion(
            name="Type 1 Diabetes",
            concept_codes=[
                201254,  # Type 1 diabetes mellitus
                435216,  # Diabetes mellitus type 1
            ],
            node_types=[NodeType.CONDITION],
            assertion_filter=["present"],
            description="Type 1 diabetes excludes T2DM phenotype",
        ),
    ],
    care_gap_criteria=[
        PhenotypeCriterion(
            name="HbA1c Measurement",
            concept_codes=[
                3004410,  # Hemoglobin A1c
                3034639,  # HbA1c measurement
            ],
            node_types=[NodeType.MEASUREMENT],
            lookback_days=180,
            description="HbA1c should be measured every 3-6 months",
        ),
        PhenotypeCriterion(
            name="Metformin Therapy",
            concept_codes=[
                1503297,  # Metformin
            ],
            node_types=[NodeType.DRUG],
            lookback_days=90,
            description="First-line therapy for T2DM",
        ),
    ],
    source="PheKB",
)

# Chronic Kidney Disease Stage 3+
CKD_3PLUS_PHENOTYPE = PhenotypeDefinition(
    id="ckd_3plus",
    name="Chronic Kidney Disease Stage 3 or Higher",
    description="CKD Stage 3+ based on eGFR < 60 mL/min/1.73m2",
    inclusion_criteria=[
        PhenotypeCriterion(
            name="CKD Diagnosis",
            concept_codes=[
                443597,  # Chronic kidney disease stage 3
                443611,  # Chronic kidney disease stage 4
                443612,  # Chronic kidney disease stage 5
                46271022,  # Chronic kidney disease
            ],
            node_types=[NodeType.CONDITION],
            min_occurrences=1,
            assertion_filter=["present"],
            description="Diagnosis of CKD stage 3 or higher",
        ),
        PhenotypeCriterion(
            name="eGFR < 60",
            concept_codes=[
                3049187,  # Glomerular filtration rate
                3030354,  # eGFR
            ],
            node_types=[NodeType.MEASUREMENT],
            value_field="value",
            value_operator=ValueOperator.LT,
            value_threshold=60.0,
            min_occurrences=2,  # Two readings to confirm
            lookback_days=365,
            description="eGFR < 60 mL/min/1.73m2 on two occasions",
        ),
    ],
    inclusion_logic=CriterionLogic.OR,
    care_gap_criteria=[
        PhenotypeCriterion(
            name="ACE Inhibitor or ARB for CKD",
            concept_codes=[
                1308216,  # ACE inhibitors
                1335471,  # ARBs
            ],
            node_types=[NodeType.DRUG],
            lookback_days=180,
            description="ACE-I or ARB for kidney protection",
        ),
    ],
    source="OHDSI",
)


class PhenotypeEngine:
    """Engine for evaluating computable phenotypes.

    Uses the patient knowledge graph to determine if patients meet
    criteria for specific clinical phenotypes.

    Usage:
        engine = PhenotypeEngine(session)
        result = engine.evaluate("hfref", "patient_123")

        # Custom phenotype
        custom_pheno = PhenotypeDefinition(...)
        engine.register_phenotype(custom_pheno)
        result = engine.evaluate(custom_pheno.id, "patient_123")
    """

    def __init__(self, session: Session) -> None:
        """Initialize the phenotype engine.

        Args:
            session: SQLAlchemy database session for KG queries.
        """
        self._session = session
        self._phenotypes: dict[str, PhenotypeDefinition] = {}

        # Register built-in phenotypes
        self.register_phenotype(HFREF_PHENOTYPE)
        self.register_phenotype(T2DM_PHENOTYPE)
        self.register_phenotype(CKD_3PLUS_PHENOTYPE)

    def register_phenotype(self, phenotype: PhenotypeDefinition) -> None:
        """Register a phenotype definition.

        Args:
            phenotype: The phenotype definition to register.
        """
        self._phenotypes[phenotype.id] = phenotype
        logger.debug(f"Registered phenotype: {phenotype.id}")

    def list_phenotypes(self) -> list[dict[str, str]]:
        """List all available phenotypes.

        Returns:
            List of phenotype summaries with id, name, and description.
        """
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "version": p.version,
                "source": p.source,
            }
            for p in self._phenotypes.values()
        ]

    def get_phenotype(self, phenotype_id: str) -> PhenotypeDefinition | None:
        """Get a phenotype definition by ID.

        Args:
            phenotype_id: The phenotype ID.

        Returns:
            The phenotype definition or None if not found.
        """
        return self._phenotypes.get(phenotype_id)

    def evaluate(self, phenotype_id: str, patient_id: str) -> PhenotypeResult:
        """Evaluate a phenotype for a specific patient.

        Args:
            phenotype_id: ID of the phenotype to evaluate.
            patient_id: Patient identifier.

        Returns:
            PhenotypeResult with status, evidence, and care gaps.

        Raises:
            ValueError: If phenotype_id is not registered.
        """
        phenotype = self._phenotypes.get(phenotype_id)
        if phenotype is None:
            raise ValueError(f"Unknown phenotype: {phenotype_id}")

        # Evaluate inclusion criteria
        inclusion_results = [
            self._evaluate_criterion(criterion, patient_id)
            for criterion in phenotype.inclusion_criteria
        ]

        # Evaluate exclusion criteria
        exclusion_results = [
            self._evaluate_criterion(criterion, patient_id)
            for criterion in phenotype.exclusion_criteria
        ]

        # Determine phenotype status
        status, confidence = self._determine_status(
            inclusion_results,
            exclusion_results,
            phenotype.inclusion_logic,
        )

        # Identify care gaps (only if phenotype is present)
        care_gaps: list[CareGap] = []
        if status == PhenotypeStatus.PRESENT:
            care_gaps = self._identify_care_gaps(phenotype, patient_id)

        # Build evidence summary
        evidence_summary = self._build_evidence_summary(
            phenotype, inclusion_results, exclusion_results, status
        )

        return PhenotypeResult(
            phenotype_id=phenotype_id,
            patient_id=patient_id,
            status=status,
            confidence=confidence,
            inclusion_results=inclusion_results,
            exclusion_results=exclusion_results,
            care_gaps=care_gaps,
            evidence_summary=evidence_summary,
        )

    def evaluate_all(self, patient_id: str) -> list[PhenotypeResult]:
        """Evaluate all registered phenotypes for a patient.

        Args:
            patient_id: Patient identifier.

        Returns:
            List of PhenotypeResult for each phenotype.
        """
        return [
            self.evaluate(phenotype_id, patient_id)
            for phenotype_id in self._phenotypes.keys()
        ]

    def _evaluate_criterion(
        self,
        criterion: PhenotypeCriterion,
        patient_id: str,
    ) -> CriterionResult:
        """Evaluate a single criterion against the patient's KG.

        Args:
            criterion: The criterion to evaluate.
            patient_id: Patient identifier.

        Returns:
            CriterionResult with match details.
        """
        # Build query for nodes matching the concept codes
        stmt = (
            select(KGNode, KGEdge)
            .join(KGEdge, KGNode.id == KGEdge.target_node_id)
            .where(KGNode.patient_id == patient_id)
            .where(KGNode.omop_concept_id.in_(criterion.concept_codes))
        )

        # Filter by node types
        if criterion.node_types:
            stmt = stmt.where(KGNode.node_type.in_(criterion.node_types))

        # Filter by lookback period
        if criterion.lookback_days is not None:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=criterion.lookback_days)
            stmt = stmt.where(
                or_(
                    KGEdge.event_date >= cutoff_date,
                    KGEdge.valid_from >= cutoff_date,
                    and_(KGEdge.event_date.is_(None), KGEdge.valid_from.is_(None)),
                )
            )

        # Filter by current validity
        if criterion.require_current:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                or_(
                    KGEdge.valid_to.is_(None),
                    KGEdge.valid_to > now,
                )
            )

        # Execute query
        result = self._session.execute(stmt)
        matches = result.all()

        # Filter by assertion if specified
        if criterion.assertion_filter:
            matches = [
                (node, edge)
                for node, edge in matches
                if node.properties.get("assertion") in criterion.assertion_filter
            ]

        # Filter by value if specified
        if criterion.value_field and criterion.value_operator and criterion.value_threshold is not None:
            matches = [
                (node, edge)
                for node, edge in matches
                if self._check_value(node.properties.get(criterion.value_field), criterion)
            ]

        # Build matched concepts list
        matched_concepts = []
        most_recent_date: datetime | None = None
        latest_value: float | None = None

        for node, edge in matches:
            event_date = edge.event_date or edge.valid_from
            concept_info = {
                "concept_id": node.omop_concept_id,
                "label": node.label,
                "node_type": node.node_type.value if node.node_type else None,
                "assertion": node.properties.get("assertion"),
                "event_date": event_date.isoformat() if event_date else None,
            }

            # Add value if present
            if criterion.value_field:
                value = node.properties.get(criterion.value_field)
                concept_info["value"] = value
                if event_date and (most_recent_date is None or event_date > most_recent_date):
                    most_recent_date = event_date
                    latest_value = value

            matched_concepts.append(concept_info)

            # Track most recent date
            if event_date:
                if most_recent_date is None or event_date > most_recent_date:
                    most_recent_date = event_date

        # Determine if criterion is met
        occurrence_count = len(matches)
        met = occurrence_count >= criterion.min_occurrences

        return CriterionResult(
            criterion=criterion,
            met=met,
            matched_concepts=matched_concepts,
            occurrence_count=occurrence_count,
            most_recent_date=most_recent_date,
            value=latest_value,
        )

    def _check_value(
        self,
        value: Any,
        criterion: PhenotypeCriterion,
    ) -> bool:
        """Check if a value meets the criterion's threshold.

        Args:
            value: The value to check.
            criterion: The criterion with operator and threshold.

        Returns:
            True if value meets the criterion.
        """
        if value is None:
            return False

        try:
            value = float(value)
        except (TypeError, ValueError):
            return False

        threshold = criterion.value_threshold
        operator = criterion.value_operator

        if operator == ValueOperator.EQ:
            return value == threshold
        elif operator == ValueOperator.NE:
            return value != threshold
        elif operator == ValueOperator.LT:
            return value < threshold
        elif operator == ValueOperator.LE:
            return value <= threshold
        elif operator == ValueOperator.GT:
            return value > threshold
        elif operator == ValueOperator.GE:
            return value >= threshold
        elif operator == ValueOperator.BETWEEN:
            if isinstance(threshold, list) and len(threshold) == 2:
                return threshold[0] <= value <= threshold[1]
            return False
        elif operator == ValueOperator.IN:
            if isinstance(threshold, list):
                return value in threshold
            return False

        return False

    def _determine_status(
        self,
        inclusion_results: list[CriterionResult],
        exclusion_results: list[CriterionResult],
        inclusion_logic: CriterionLogic,
    ) -> tuple[PhenotypeStatus, float]:
        """Determine phenotype status from criterion results.

        Args:
            inclusion_results: Results of inclusion criteria evaluation.
            exclusion_results: Results of exclusion criteria evaluation.
            inclusion_logic: Logic for combining inclusion criteria.

        Returns:
            Tuple of (status, confidence).
        """
        # Check if any exclusion criteria are met
        if any(r.met for r in exclusion_results):
            return PhenotypeStatus.ABSENT, 0.95

        # Check inclusion criteria
        if not inclusion_results:
            return PhenotypeStatus.INSUFFICIENT_DATA, 0.0

        inclusion_met = [r.met for r in inclusion_results]
        total_criteria = len(inclusion_met)
        met_count = sum(inclusion_met)

        # Apply logic
        if inclusion_logic == CriterionLogic.AND:
            if all(inclusion_met):
                confidence = 0.90 + (0.10 * min(met_count / total_criteria, 1.0))
                return PhenotypeStatus.PRESENT, confidence
            elif any(inclusion_met):
                confidence = 0.50 * (met_count / total_criteria)
                return PhenotypeStatus.POSSIBLE, confidence
            else:
                return PhenotypeStatus.ABSENT, 0.80

        elif inclusion_logic == CriterionLogic.OR:
            if any(inclusion_met):
                confidence = 0.85 + (0.15 * (met_count / total_criteria))
                return PhenotypeStatus.PRESENT, confidence
            else:
                return PhenotypeStatus.ABSENT, 0.75

        return PhenotypeStatus.INSUFFICIENT_DATA, 0.0

    def _identify_care_gaps(
        self,
        phenotype: PhenotypeDefinition,
        patient_id: str,
    ) -> list[CareGap]:
        """Identify care gaps for a patient with a phenotype.

        Args:
            phenotype: The phenotype definition.
            patient_id: Patient identifier.

        Returns:
            List of identified care gaps.
        """
        care_gaps: list[CareGap] = []

        for criterion in phenotype.care_gap_criteria:
            result = self._evaluate_criterion(criterion, patient_id)

            if not result.met:
                # Create care gap
                gap = CareGap(
                    criterion=criterion,
                    description=f"Missing: {criterion.name}",
                    severity="medium",
                    recommendation=criterion.description,
                )

                # Adjust severity based on criterion type
                if criterion.node_types == [NodeType.DRUG]:
                    gap.severity = "high"
                    gap.description = f"Medication gap: {criterion.name}"
                elif criterion.node_types == [NodeType.MEASUREMENT]:
                    gap.severity = "medium"
                    gap.description = f"Missing measurement: {criterion.name}"

                care_gaps.append(gap)

        return care_gaps

    def _build_evidence_summary(
        self,
        phenotype: PhenotypeDefinition,
        inclusion_results: list[CriterionResult],
        exclusion_results: list[CriterionResult],
        status: PhenotypeStatus,
    ) -> str:
        """Build a human-readable evidence summary.

        Args:
            phenotype: The phenotype definition.
            inclusion_results: Results of inclusion criteria.
            exclusion_results: Results of exclusion criteria.
            status: The determined status.

        Returns:
            Evidence summary string.
        """
        lines = [f"Phenotype: {phenotype.name}"]
        lines.append(f"Status: {status.value}")
        lines.append("")

        # Inclusion criteria
        lines.append("Inclusion Criteria:")
        for result in inclusion_results:
            status_mark = "[+]" if result.met else "[-]"
            lines.append(f"  {status_mark} {result.criterion.name}: {result.occurrence_count} occurrence(s)")
            if result.value is not None:
                lines.append(f"      Value: {result.value}")

        # Exclusion criteria (if any met)
        if any(r.met for r in exclusion_results):
            lines.append("")
            lines.append("Exclusion Criteria Met:")
            for result in exclusion_results:
                if result.met:
                    lines.append(f"  [!] {result.criterion.name}")

        return "\n".join(lines)


# Module-level function for getting singleton instance
_phenotype_engine: PhenotypeEngine | None = None
_phenotype_lock = threading.Lock()


def get_phenotype_engine(session: Session) -> PhenotypeEngine:
    """Get or create the phenotype engine.

    Args:
        session: SQLAlchemy database session.

    Returns:
        PhenotypeEngine instance.
    """
    global _phenotype_engine
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _phenotype_engine is None:
        with _phenotype_lock:
            if _phenotype_engine is None:
                _phenotype_engine = PhenotypeEngine(session)
    return _phenotype_engine
