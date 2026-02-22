"""Longitudinal Clinical Benchmark schemas — HealthBench-style evaluation.

Data structures for the MIMIC-IV longitudinal QA benchmark that evaluates
KG-RAG performance as a function of encounter history depth.

Design:
- HealthBench-style: each question has multiple binary rubric criteria
- Criteria are typed by reasoning skill (experiencer, temporal, assertion, etc.)
- Patients are stratified by longitudinal tier (A=1-2, B=5-10, C=15+ encounters)
- Conditions B0-B3 form a clean ablation ladder
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ============================================================================
# Enums
# ============================================================================


class LongitudinalTier(str, Enum):
    """Patient stratification by encounter count."""

    A = "A"  # 1-2 encounters (baseline — KG has little to add)
    B = "B"  # 5-10 encounters (mid-range — KG starts showing value)
    C = "C"  # 15+ encounters (deep longitudinal — KG's sweet spot)


class CriterionType(str, Enum):
    """Reasoning skill tag for each rubric criterion."""

    CHRONOLOGY = "chronology"          # Correct temporal ordering / dates
    CAUSAL = "causal"                  # Causal or association reasoning
    MEDICATION = "medication"          # Drug exposure, interaction, reconciliation
    EXPERIENCER = "experiencer"        # Family history vs patient (the fix we just made)
    ASSERTION = "assertion"            # Negation, uncertainty, conditional
    UNCERTAINTY = "uncertainty"        # Calibrated uncertainty handling
    SYNTHESIS = "synthesis"            # Multi-fact integration / problem list
    RISK = "risk"                      # Risk factor identification


class CriterionWeight(str, Enum):
    """Importance level for rubric criteria."""

    CRITICAL = "critical"  # Must-have — weight 2
    IMPORTANT = "important"  # Weight 1
    NICE = "nice"  # Weight 0.5


class ConditionID(str, Enum):
    """Ablation conditions for the longitudinal benchmark."""

    B0 = "B0_llm_alone"           # LLM with no patient data
    B1 = "B1_latest_note"         # LLM + latest discharge summary only
    B2 = "B2_all_notes_rag"       # LLM + naive "all notes" RAG (flattened text retrieval)
    B3 = "B3_kg_rag"              # LLM + full KG-RAG system


class QuestionDomain(str, Enum):
    """Clinical domain tags for questions."""

    MEDICATION_RECONCILIATION = "medication_reconciliation"
    PROBLEM_LIST = "problem_list"
    FAMILY_HISTORY = "family_history"
    TEMPORAL_REASONING = "temporal_reasoning"
    RISK_ASSESSMENT = "risk_assessment"


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class LongBenchCriterion:
    """A single binary rubric criterion (HealthBench-style).

    Each criterion maps to exactly one reasoning skill so we can compute
    per-skill breakdowns across the benchmark.
    """

    criterion_id: str
    text: str                           # Human-readable description
    criterion_type: CriterionType       # Which reasoning skill this tests
    weight: CriterionWeight = CriterionWeight.IMPORTANT
    # Ground truth derivation
    evidence_source: str = ""           # Which encounter(s) support this criterion

    @property
    def numeric_weight(self) -> float:
        return {
            CriterionWeight.CRITICAL: 2.0,
            CriterionWeight.IMPORTANT: 1.0,
            CriterionWeight.NICE: 0.5,
        }[self.weight]


@dataclass
class LongBenchQuestion:
    """A single clinical QA question with HealthBench-style rubric criteria."""

    question_id: str
    patient_id: str
    question_text: str
    domain: QuestionDomain
    tier: LongitudinalTier
    criteria: list[LongBenchCriterion] = field(default_factory=list)
    # For provenance
    encounter_count: int = 0             # How many encounters this patient has
    evidence_window: str = ""            # Temporal bounds of relevant evidence
    generated_by: str = "llm"            # "llm", "template", "human"
    validated_by: str | None = None      # annotator ID if human-validated
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def max_score(self) -> float:
        return sum(c.numeric_weight for c in self.criteria)


@dataclass
class CriterionResult:
    """Evaluation result for a single criterion."""

    criterion_id: str
    satisfied: bool
    confidence: float = 1.0     # Judge confidence (0-1)
    reasoning: str = ""


@dataclass
class LongBenchResult:
    """Result of evaluating one question under one condition."""

    question_id: str
    patient_id: str
    condition: ConditionID
    tier: LongitudinalTier
    domain: QuestionDomain
    predicted_answer: str
    criterion_results: list[CriterionResult] = field(default_factory=list)
    # Computed scores
    raw_score: float = 0.0         # Sum of weighted satisfied criteria
    max_score: float = 0.0         # Sum of all criterion weights
    normalized_score: float = 0.0  # raw_score / max_score
    # Metadata
    latency_ms: float = 0.0
    token_count: int = 0
    error: str | None = None

    def compute_scores(self, criteria: list[LongBenchCriterion]) -> None:
        """Compute raw/max/normalized scores from criterion results."""
        crit_map = {c.criterion_id: c for c in criteria}
        self.raw_score = 0.0
        self.max_score = 0.0
        for cr in self.criterion_results:
            crit = crit_map.get(cr.criterion_id)
            if not crit:
                continue
            self.max_score += crit.numeric_weight
            if cr.satisfied:
                self.raw_score += crit.numeric_weight
        self.normalized_score = (
            self.raw_score / self.max_score if self.max_score > 0 else 0.0
        )


@dataclass
class PatientCohortEntry:
    """A patient selected for the longitudinal benchmark."""

    patient_id: str
    tier: LongitudinalTier
    encounter_count: int
    total_note_length: int = 0       # Total chars across all notes
    note_types: list[str] = field(default_factory=list)
    earliest_date: str = ""
    latest_date: str = ""
    # Clinical richness indicators
    condition_count: int = 0
    medication_count: int = 0
    has_family_history: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LongBenchCohort:
    """The full benchmark cohort definition."""

    cohort_id: str
    patients: list[PatientCohortEntry] = field(default_factory=list)
    questions: list[LongBenchQuestion] = field(default_factory=list)
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def patients_by_tier(self) -> dict[LongitudinalTier, list[PatientCohortEntry]]:
        result: dict[LongitudinalTier, list[PatientCohortEntry]] = {
            t: [] for t in LongitudinalTier
        }
        for p in self.patients:
            result[p.tier].append(p)
        return result

    @property
    def questions_by_tier(self) -> dict[LongitudinalTier, list[LongBenchQuestion]]:
        result: dict[LongitudinalTier, list[LongBenchQuestion]] = {
            t: [] for t in LongitudinalTier
        }
        for q in self.questions:
            result[q.tier].append(q)
        return result

    @property
    def tier_summary(self) -> dict[str, dict[str, int]]:
        return {
            tier.value: {
                "patients": len(patients),
                "questions": len(self.questions_by_tier[tier]),
            }
            for tier, patients in self.patients_by_tier.items()
        }


# ============================================================================
# Aggregate analysis structures
# ============================================================================


@dataclass
class ConditionTierScore:
    """Aggregate score for one condition x tier cell."""

    condition: ConditionID
    tier: LongitudinalTier
    n_questions: int = 0
    mean_score: float = 0.0
    std_score: float = 0.0
    # Per-criterion-type breakdowns
    criterion_type_scores: dict[str, float] = field(default_factory=dict)
    criterion_type_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class LongBenchReport:
    """Full benchmark report — the output artifact."""

    cohort_id: str
    results: list[LongBenchResult] = field(default_factory=list)
    condition_tier_scores: list[ConditionTierScore] = field(default_factory=list)
    # Global metrics
    total_questions: int = 0
    total_criteria: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
