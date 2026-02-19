"""Pydantic schemas for ClinicalIntelligenceBench — NeurIPS 2026.

Defines the data contracts for:
- Benchmark questions (Tasks A-D)
- Benchmark results and scoring
- Ablation experiment configurations
- API request/response models
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class BenchmarkTask(str, Enum):
    """The four benchmark tasks in ClinicalIntelligenceBench."""

    TASK_A_NEGATION = "task_a_negation"
    TASK_B_TEMPORAL = "task_b_temporal"
    TASK_C_CALCULATOR = "task_c_calculator"
    TASK_D_FUSION = "task_d_fusion"


class QuestionDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AssertionType(str, Enum):
    """Assertion subtypes for Task A."""

    NEGATION = "negation"
    UNCERTAINTY = "uncertainty"
    FAMILY_HISTORY = "family_history"
    CONDITIONAL = "conditional"


class TemporalType(str, Enum):
    """Temporal subtypes for Task B."""

    CURRENT_STATE = "current_state"
    HISTORICAL = "historical"
    SEQUENCE = "sequence"
    DURATION = "duration"
    CHANGE = "change"


class CalculatorType(str, Enum):
    """Calculator subtypes for Task C."""

    HEART = "heart"
    WELLS_PE = "wells_pe"
    SOFA = "sofa"
    CKD_EPI = "ckd_epi"
    ASCVD = "ascvd"
    MELD = "meld"
    OTHER = "other"


class FusionType(str, Enum):
    """Fusion subtypes for Task D."""

    LAB_NOTE = "lab_note"
    VITAL_NOTE = "vital_note"
    TEMPORAL_FUSION = "temporal_fusion"
    CROSS_NOTE_DISCORDANCE = "cross_note_discordance"


class AblationCondition(str, Enum):
    """The 5 ablation conditions."""

    C1_LLM_ALONE = "C1_llm_alone"
    C2_VANILLA_RAG = "C2_vanilla_rag"
    C3_KG_RAG = "C3_kg_rag"
    C4_EPISTEMIC_KG_RAG = "C4_epistemic_kg_rag"
    C5_FULL_SYSTEM = "C5_full_system"


# ============================================================================
# Benchmark Question Schemas
# ============================================================================


class BenchmarkQuestion(BaseModel):
    """A single benchmark question with gold-standard answer."""

    question_id: str = Field(..., description="Unique question identifier")
    task: BenchmarkTask = Field(..., description="Which task this belongs to")
    subtype: str = Field(..., description="Question subtype within the task")
    question: str = Field(..., description="The clinical question text")
    expected_answer: str = Field(..., description="Gold-standard expected answer")
    mimic_subject_id: int | None = Field(None, description="MIMIC patient subject_id")
    mimic_hadm_id: int | None = Field(None, description="MIMIC admission ID")
    clinical_context: str = Field("", description="Relevant clinical note excerpt")
    difficulty: QuestionDifficulty = Field(QuestionDifficulty.MEDIUM)
    scoring_rubric: dict[str, float] = Field(
        default_factory=dict,
        description="Category-specific scoring weights",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    annotator_id: str | None = Field(None, description="Who created/verified this question")
    annotation_notes: str = Field("", description="Annotator notes on question quality")


class BenchmarkQuestionSet(BaseModel):
    """A complete set of benchmark questions for one task."""

    task: BenchmarkTask
    version: str = Field("1.0.0", description="Question set version")
    questions: list[BenchmarkQuestion]
    total_count: int = Field(0)
    subtype_distribution: dict[str, int] = Field(default_factory=dict)
    created_at: datetime | None = None

    def model_post_init(self, __context: Any) -> None:
        self.total_count = len(self.questions)
        dist: dict[str, int] = {}
        for q in self.questions:
            dist[q.subtype] = dist.get(q.subtype, 0) + 1
        self.subtype_distribution = dist


# ============================================================================
# Scoring Schemas
# ============================================================================


class QuestionScore(BaseModel):
    """Score for a single question."""

    question_id: str
    task: BenchmarkTask
    subtype: str
    predicted_answer: str
    expected_answer: str
    correct: bool
    factual_accuracy: float = Field(0.0, ge=0.0, le=1.0)
    assertion_correctness: float = Field(0.0, ge=0.0, le=1.0)
    temporal_correctness: float = Field(0.0, ge=0.0, le=1.0)
    clinical_safety: float = Field(0.0, ge=0.0, le=1.0)
    overall_score: float = Field(0.0, ge=0.0, le=1.0)
    latency_ms: float = 0.0
    reasoning_trace: str = ""
    error: str | None = None


class TaskResult(BaseModel):
    """Aggregate result for a single task under one condition."""

    task: BenchmarkTask
    condition: AblationCondition
    total_questions: int
    correct: int
    accuracy: float
    subtype_accuracies: dict[str, float] = Field(default_factory=dict)
    avg_latency_ms: float = 0.0
    safety_score: float = 0.0
    scores: list[QuestionScore] = Field(default_factory=list)


class ConditionResult(BaseModel):
    """Result for all tasks under one ablation condition."""

    condition: AblationCondition
    task_results: dict[str, TaskResult] = Field(default_factory=dict)
    overall_accuracy: float = 0.0
    overall_safety: float = 0.0
    avg_latency_ms: float = 0.0


class BenchmarkRunResult(BaseModel):
    """Complete result of a benchmark run across all conditions."""

    run_id: str
    run_at: datetime
    benchmark_version: str = "1.0.0"
    llm_model: str
    patient_count: int = 0
    total_questions: int = 0
    conditions: dict[str, ConditionResult] = Field(default_factory=dict)
    total_duration_s: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Metric Schemas (for assertion-weighted and temporal metrics)
# ============================================================================


class AssertionWeightedMetrics(BaseModel):
    """Task A metrics: assertion-weighted accuracy.

    False positive on negated finding penalized 2x per the paper.
    """

    total: int = 0
    correct: int = 0
    raw_accuracy: float = 0.0
    weighted_accuracy: float = Field(
        0.0, description="Accuracy with 2x penalty for false positive on negated"
    )
    negation_accuracy: float = 0.0
    uncertainty_accuracy: float = 0.0
    family_history_accuracy: float = 0.0
    conditional_accuracy: float = 0.0
    false_positive_on_negated: int = Field(
        0, description="Count of dangerous errors (affirming negated condition)"
    )


class TemporalMetrics(BaseModel):
    """Task B metrics: temporal accuracy."""

    total: int = 0
    correct: int = 0
    accuracy: float = 0.0
    current_state_accuracy: float = 0.0
    historical_accuracy: float = 0.0
    sequence_accuracy: float = 0.0
    duration_accuracy: float = 0.0
    change_accuracy: float = 0.0


class CalculatorMetrics(BaseModel):
    """Task C metrics: calculator accuracy + decision accuracy."""

    total: int = 0
    calculator_correct: int = Field(0, description="Correct calculator score")
    decision_correct: int = Field(0, description="Correct clinical decision from score")
    calculator_accuracy: float = 0.0
    decision_accuracy: float = 0.0
    per_calculator: dict[str, float] = Field(
        default_factory=dict,
        description="Accuracy per calculator type",
    )


class FusionMetrics(BaseModel):
    """Task D metrics: fusion accuracy + source attribution."""

    total: int = 0
    correct: int = 0
    accuracy: float = 0.0
    source_attribution_accuracy: float = Field(
        0.0, description="Did the model correctly identify which source (lab/note/vital)"
    )
    discordance_detection: float = Field(
        0.0, description="Did the model detect discordance between sources"
    )


# ============================================================================
# API Request/Response Schemas
# ============================================================================


class RunBenchmarkRequest(BaseModel):
    """API request to run a benchmark."""

    patient_ids: list[str] = Field(..., min_length=1)
    tasks: list[BenchmarkTask] | None = Field(
        None, description="Specific tasks to run. None = all."
    )
    conditions: list[AblationCondition] | None = Field(
        None, description="Specific conditions to run. None = all 5."
    )
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_provider: str = "anthropic"
    use_llm_judge: bool = True
    question_limit: int | None = Field(
        None, description="Limit questions per task for faster iteration"
    )


class RunBenchmarkResponse(BaseModel):
    """API response after starting a benchmark run."""

    run_id: str
    status: str = "started"
    total_questions: int = 0
    estimated_cost_usd: float | None = None


class BenchmarkStatusResponse(BaseModel):
    """API response for benchmark run status."""

    run_id: str
    status: str  # "running", "completed", "failed"
    progress: float = Field(0.0, ge=0.0, le=1.0)
    conditions_completed: int = 0
    conditions_total: int = 5
    questions_completed: int = 0
    questions_total: int = 0
    elapsed_s: float = 0.0


class BenchmarkResultResponse(BaseModel):
    """API response with full benchmark results."""

    result: BenchmarkRunResult
    markdown_table: str = ""
    latex_table: str = ""


class GenerateQuestionsRequest(BaseModel):
    """API request to generate benchmark questions from MIMIC."""

    task: BenchmarkTask
    count: int = Field(100, ge=1, le=500)
    mimic_subject_ids: list[int] | None = None
    difficulty_distribution: dict[str, float] | None = None


class GenerateQuestionsResponse(BaseModel):
    """API response after generating questions."""

    task: BenchmarkTask
    generated_count: int
    question_set: BenchmarkQuestionSet
