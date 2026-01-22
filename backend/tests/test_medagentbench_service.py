"""Tests for MedAgentBench Integration Service."""

from __future__ import annotations

import pytest

from app.services.medagentbench_service import (
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkSuite,
    DifficultyLevel,
    MedAgentBenchService,
    get_medagentbench_service,
)


class TestBenchmarkCase:
    """Test BenchmarkCase dataclass."""

    def test_create_basic_case(self) -> None:
        """Test creating a basic benchmark case."""
        case = BenchmarkCase(
            case_id="test_001",
            category=BenchmarkCategory.QUESTION_ANSWERING,
            difficulty=DifficultyLevel.EASY,
            question="What treats diabetes?",
            context={"condition": "Diabetes"},
            expected_answer="Metformin",
        )
        assert case.case_id == "test_001"
        assert case.category == BenchmarkCategory.QUESTION_ANSWERING
        assert case.difficulty == DifficultyLevel.EASY
        assert case.expected_answer == "Metformin"

    def test_create_case_with_multiple_answers(self) -> None:
        """Test creating a case with multiple expected answers."""
        case = BenchmarkCase(
            case_id="test_002",
            category=BenchmarkCategory.DRUG_DISEASE,
            difficulty=DifficultyLevel.MEDIUM,
            question="What drugs treat hypertension?",
            context={},
            expected_answer=["ACE inhibitors", "ARBs", "Beta blockers"],
            expected_entities=["Hypertension"],
        )
        assert len(case.expected_answer) == 3
        assert "ACE inhibitors" in case.expected_answer

    def test_create_case_with_reasoning_steps(self) -> None:
        """Test creating a case with reasoning steps."""
        case = BenchmarkCase(
            case_id="test_003",
            category=BenchmarkCategory.MULTI_HOP_REASONING,
            difficulty=DifficultyLevel.HARD,
            question="Complex reasoning question",
            context={},
            expected_answer="Complex answer",
            reasoning_steps=[
                "Step 1: Identify condition",
                "Step 2: Find related drugs",
                "Step 3: Check interactions",
            ],
        )
        assert len(case.reasoning_steps) == 3


class TestBenchmarkResult:
    """Test BenchmarkResult dataclass."""

    def test_create_passing_result(self) -> None:
        """Test creating a passing result."""
        result = BenchmarkResult(
            case_id="test_001",
            category=BenchmarkCategory.QUESTION_ANSWERING,
            passed=True,
            actual_answer="Metformin",
            expected_answer="Metformin",
            score=1.0,
        )
        assert result.passed is True
        assert result.score == 1.0

    def test_create_failing_result(self) -> None:
        """Test creating a failing result."""
        result = BenchmarkResult(
            case_id="test_002",
            category=BenchmarkCategory.DIAGNOSTIC,
            passed=False,
            actual_answer="Wrong diagnosis",
            expected_answer="Correct diagnosis",
            score=0.2,
            error=None,
        )
        assert result.passed is False
        assert result.score == 0.2


class TestBenchmarkSuite:
    """Test BenchmarkSuite dataclass."""

    def test_create_suite(self) -> None:
        """Test creating a benchmark suite."""
        cases = [
            BenchmarkCase(
                case_id="c1",
                category=BenchmarkCategory.QUESTION_ANSWERING,
                difficulty=DifficultyLevel.EASY,
                question="Q1",
                context={},
                expected_answer="A1",
            ),
            BenchmarkCase(
                case_id="c2",
                category=BenchmarkCategory.DIAGNOSTIC,
                difficulty=DifficultyLevel.MEDIUM,
                question="Q2",
                context={},
                expected_answer="A2",
            ),
        ]

        suite = BenchmarkSuite(
            suite_id="test_suite",
            name="Test Suite",
            description="A test benchmark suite",
            cases=cases,
        )

        assert suite.suite_id == "test_suite"
        assert len(suite.cases) == 2
        assert suite.version == "1.0.0"


class TestMedAgentBenchService:
    """Test MedAgentBenchService class."""

    def test_service_initialization(self) -> None:
        """Test service initializes with built-in suites."""
        service = MedAgentBenchService()
        suites = service.list_suites()
        assert len(suites) >= 5  # Should have built-in suites

    def test_list_suites(self) -> None:
        """Test listing available benchmark suites."""
        service = MedAgentBenchService()
        suites = service.list_suites()

        assert any(s["suite_id"] == "qa_basic" for s in suites)
        assert any(s["suite_id"] == "multihop_reasoning" for s in suites)
        assert any(s["suite_id"] == "drug_disease" for s in suites)
        assert any(s["suite_id"] == "diagnostic" for s in suites)
        assert any(s["suite_id"] == "safety" for s in suites)

    def test_get_suite(self) -> None:
        """Test getting a specific suite."""
        service = MedAgentBenchService()
        suite = service.get_suite("qa_basic")

        assert suite is not None
        assert suite.suite_id == "qa_basic"
        assert len(suite.cases) > 0

    def test_get_nonexistent_suite(self) -> None:
        """Test getting a non-existent suite."""
        service = MedAgentBenchService()
        suite = service.get_suite("nonexistent")
        assert suite is None

    def test_register_custom_suite(self) -> None:
        """Test registering a custom suite."""
        service = MedAgentBenchService()

        custom_suite = BenchmarkSuite(
            suite_id="custom_test",
            name="Custom Test Suite",
            description="A custom suite for testing",
            cases=[
                BenchmarkCase(
                    case_id="custom_001",
                    category=BenchmarkCategory.QUESTION_ANSWERING,
                    difficulty=DifficultyLevel.EASY,
                    question="Custom question?",
                    context={},
                    expected_answer="Custom answer",
                ),
            ],
        )

        service.register_suite(custom_suite)
        retrieved = service.get_suite("custom_test")

        assert retrieved is not None
        assert retrieved.name == "Custom Test Suite"
        assert len(retrieved.cases) == 1

    def test_create_custom_case(self) -> None:
        """Test creating a custom benchmark case."""
        service = MedAgentBenchService()

        case = service.create_custom_case(
            case_id="new_case",
            category=BenchmarkCategory.SAFETY,
            difficulty=DifficultyLevel.HARD,
            question="Is there a drug interaction?",
            expected_answer="Yes - serious interaction",
            context={"medications": ["Drug A", "Drug B"]},
            expected_entities=["Drug A", "Drug B"],
            reasoning_steps=["Check CYP interaction"],
        )

        assert case.case_id == "new_case"
        assert case.category == BenchmarkCategory.SAFETY
        assert len(case.reasoning_steps) == 1


class TestEvaluators:
    """Test evaluation functions."""

    def test_evaluate_qa_exact_match(self) -> None:
        """Test QA evaluation with exact match."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="qa_test",
            category=BenchmarkCategory.QUESTION_ANSWERING,
            difficulty=DifficultyLevel.EASY,
            question="What treats diabetes?",
            context={},
            expected_answer="Metformin",
        )

        score, metrics = service._evaluate_qa(case, "Metformin")
        assert score == 1.0
        assert metrics["exact_match"] == 1.0

    def test_evaluate_qa_partial_match(self) -> None:
        """Test QA evaluation with partial match."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="qa_test",
            category=BenchmarkCategory.QUESTION_ANSWERING,
            difficulty=DifficultyLevel.EASY,
            question="What treats diabetes?",
            context={},
            expected_answer="Metformin",
        )

        score, metrics = service._evaluate_qa(case, "Metformin 500mg is used")
        assert score > 0
        assert metrics["partial_match"] == 1.0

    def test_evaluate_qa_no_match(self) -> None:
        """Test QA evaluation with no match."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="qa_test",
            category=BenchmarkCategory.QUESTION_ANSWERING,
            difficulty=DifficultyLevel.EASY,
            question="What treats diabetes?",
            context={},
            expected_answer="Metformin",
        )

        score, metrics = service._evaluate_qa(case, "Aspirin")
        assert score == 0.0
        assert metrics["exact_match"] == 0.0

    def test_evaluate_qa_multiple_answers(self) -> None:
        """Test QA evaluation with multiple expected answers."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="qa_test",
            category=BenchmarkCategory.QUESTION_ANSWERING,
            difficulty=DifficultyLevel.MEDIUM,
            question="What drugs treat hypertension?",
            context={},
            expected_answer=["ACE inhibitors", "ARBs", "Beta blockers"],
        )

        score, metrics = service._evaluate_qa(
            case, "ACE inhibitors and ARBs are commonly used"
        )
        assert score > 0
        assert metrics["partial_match"] > 0

    def test_evaluate_safety_yes_detected(self) -> None:
        """Test safety evaluation when interaction is detected."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="sf_test",
            category=BenchmarkCategory.SAFETY,
            difficulty=DifficultyLevel.MEDIUM,
            question="Drug interaction?",
            context={},
            expected_answer="Yes - bleeding risk",
        )

        score, metrics = service._evaluate_safety(
            case, "Yes, there is an interaction with increased bleeding risk"
        )
        assert score > 0.5
        assert metrics["safety_detection"] == 1.0

    def test_evaluate_safety_no_detected(self) -> None:
        """Test safety evaluation when no interaction."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="sf_test",
            category=BenchmarkCategory.SAFETY,
            difficulty=DifficultyLevel.EASY,
            question="Drug interaction?",
            context={},
            expected_answer="No - safe to combine",
        )

        score, metrics = service._evaluate_safety(
            case, "No significant interaction expected"
        )
        assert score > 0

    def test_evaluate_diagnostic(self) -> None:
        """Test diagnostic evaluation."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="dx_test",
            category=BenchmarkCategory.DIAGNOSTIC,
            difficulty=DifficultyLevel.MEDIUM,
            question="What is the diagnosis?",
            context={},
            expected_answer="Diabetes Mellitus",
            expected_entities=["Diabetes", "Blood glucose"],
        )

        score, metrics = service._evaluate_diagnostic(
            case, "The diagnosis is Diabetes Mellitus based on elevated blood glucose"
        )
        assert score > 0.5
        assert metrics["diagnosis_match"] > 0
        assert metrics["entity_coverage"] > 0

    def test_evaluate_multihop(self) -> None:
        """Test multi-hop reasoning evaluation."""
        service = MedAgentBenchService()

        case = BenchmarkCase(
            case_id="mh_test",
            category=BenchmarkCategory.MULTI_HOP_REASONING,
            difficulty=DifficultyLevel.HARD,
            question="Why avoid this combination?",
            context={},
            expected_answer="Causes interaction",
            reasoning_steps=[
                "Drug A inhibits CYP3A4",
                "Drug B is metabolized by CYP3A4",
                "Increased Drug B levels cause toxicity",
            ],
        )

        score, metrics = service._evaluate_multihop(
            case,
            "Drug A inhibits CYP3A4 which metabolizes Drug B, causing increased levels and toxicity"
        )
        assert score > 0
        assert "reasoning_coverage" in metrics


class TestRunBenchmark:
    """Test running benchmarks."""

    @pytest.mark.asyncio
    async def test_run_suite_with_mock_agent(self) -> None:
        """Test running a suite with a mock agent."""
        service = MedAgentBenchService()

        # Mock agent that always returns a fixed answer
        async def mock_agent(case: BenchmarkCase) -> dict:
            return {
                "answer": "Metformin",
                "reasoning_trace": ["Found treatment for diabetes"],
            }

        report = await service.run_suite("qa_basic", mock_agent)

        assert report.total_cases > 0
        assert report.passed_cases + report.failed_cases == report.total_cases
        assert 0 <= report.overall_accuracy <= 1

    @pytest.mark.asyncio
    async def test_run_suite_with_error_handling(self) -> None:
        """Test running suite handles agent errors."""
        service = MedAgentBenchService()

        # Mock agent that throws errors
        async def failing_agent(case: BenchmarkCase) -> dict:
            raise ValueError("Agent failed")

        report = await service.run_suite("qa_basic", failing_agent)

        # Should complete despite errors
        assert report.total_cases > 0
        # All should fail due to errors
        for result in report.results:
            assert result.error is not None


class TestBaselineComparison:
    """Test baseline comparison functionality."""

    def test_compare_to_drknows(self) -> None:
        """Test comparing to DR.KNOWS baseline."""
        service = MedAgentBenchService()

        # Create a mock report
        report = BenchmarkReport(
            suite_id="test",
            suite_name="Test",
            total_cases=100,
            passed_cases=85,
            failed_cases=15,
            overall_accuracy=0.85,
            category_scores={
                "question_answering": 0.88,
                "multi_hop_reasoning": 0.82,
            },
            difficulty_scores={"easy": 0.95, "medium": 0.85},
            avg_execution_time_ms=50.0,
            results=[],
        )

        comparison = service.compare_to_baseline(report, "DR.KNOWS")

        assert comparison["baseline_name"] == "DR.KNOWS"
        assert "delta_overall" in comparison
        assert "category_comparisons" in comparison
        assert "assessment" in comparison

    def test_compare_to_medqa(self) -> None:
        """Test comparing to MedQA baseline."""
        service = MedAgentBenchService()

        report = BenchmarkReport(
            suite_id="test",
            suite_name="Test",
            total_cases=50,
            passed_cases=40,
            failed_cases=10,
            overall_accuracy=0.80,
            category_scores={"question_answering": 0.80},
            difficulty_scores={},
            avg_execution_time_ms=30.0,
            results=[],
        )

        comparison = service.compare_to_baseline(report, "MedQA")

        assert comparison["baseline_name"] == "MedQA"
        assert comparison["delta_overall"] > 0  # 0.80 > 0.767

    def test_compare_unknown_baseline(self) -> None:
        """Test comparing to unknown baseline returns error."""
        service = MedAgentBenchService()

        report = BenchmarkReport(
            suite_id="test",
            suite_name="Test",
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            overall_accuracy=0.80,
            category_scores={},
            difficulty_scores={},
            avg_execution_time_ms=10.0,
            results=[],
        )

        comparison = service.compare_to_baseline(report, "UnknownSystem")
        assert "error" in comparison


class TestMetricsCalculation:
    """Test aggregate metrics calculation."""

    def test_calculate_metrics(self) -> None:
        """Test calculating aggregate metrics."""
        service = MedAgentBenchService()

        results = [
            BenchmarkResult(
                case_id="c1",
                category=BenchmarkCategory.QUESTION_ANSWERING,
                passed=True,
                actual_answer="A",
                expected_answer="A",
                score=1.0,
            ),
            BenchmarkResult(
                case_id="c2",
                category=BenchmarkCategory.QUESTION_ANSWERING,
                passed=True,
                actual_answer="B",
                expected_answer="B",
                score=0.8,
            ),
            BenchmarkResult(
                case_id="c3",
                category=BenchmarkCategory.DIAGNOSTIC,
                passed=False,
                actual_answer="C",
                expected_answer="D",
                score=0.3,
            ),
        ]

        metrics = service._calculate_aggregate_metrics(results)

        assert "mean_score" in metrics
        assert "median_score" in metrics
        assert "std_dev" in metrics
        assert "min_score" in metrics
        assert "max_score" in metrics

        assert metrics["min_score"] == 0.3
        assert metrics["max_score"] == 1.0

    def test_calculate_metrics_empty(self) -> None:
        """Test calculating metrics with no results."""
        service = MedAgentBenchService()
        metrics = service._calculate_aggregate_metrics([])
        assert metrics == {}


class TestSingletonPattern:
    """Test singleton service pattern."""

    def test_get_singleton_instance(self) -> None:
        """Test getting singleton service instance."""
        service1 = get_medagentbench_service()
        service2 = get_medagentbench_service()
        assert service1 is service2


class TestBuiltinSuites:
    """Test built-in benchmark suites."""

    def test_qa_suite_has_cases(self) -> None:
        """Test QA suite has benchmark cases."""
        service = MedAgentBenchService()
        suite = service.get_suite("qa_basic")
        assert suite is not None
        assert len(suite.cases) >= 4

    def test_multihop_suite_has_cases(self) -> None:
        """Test multi-hop suite has benchmark cases."""
        service = MedAgentBenchService()
        suite = service.get_suite("multihop_reasoning")
        assert suite is not None
        assert len(suite.cases) >= 3

        # Multi-hop cases should have reasoning steps
        for case in suite.cases:
            assert len(case.reasoning_steps) > 0

    def test_drug_disease_suite_has_cases(self) -> None:
        """Test drug-disease suite has benchmark cases."""
        service = MedAgentBenchService()
        suite = service.get_suite("drug_disease")
        assert suite is not None
        assert len(suite.cases) >= 3

    def test_diagnostic_suite_has_cases(self) -> None:
        """Test diagnostic suite has benchmark cases."""
        service = MedAgentBenchService()
        suite = service.get_suite("diagnostic")
        assert suite is not None
        assert len(suite.cases) >= 3

    def test_safety_suite_has_cases(self) -> None:
        """Test safety suite has benchmark cases."""
        service = MedAgentBenchService()
        suite = service.get_suite("safety")
        assert suite is not None
        assert len(suite.cases) >= 3


class TestCategoryEnums:
    """Test benchmark category enums."""

    def test_all_categories(self) -> None:
        """Test all benchmark categories exist."""
        categories = list(BenchmarkCategory)
        assert BenchmarkCategory.QUESTION_ANSWERING in categories
        assert BenchmarkCategory.MULTI_HOP_REASONING in categories
        assert BenchmarkCategory.DRUG_DISEASE in categories
        assert BenchmarkCategory.DIAGNOSTIC in categories
        assert BenchmarkCategory.TREATMENT in categories
        assert BenchmarkCategory.SAFETY in categories
        assert BenchmarkCategory.TEMPORAL in categories

    def test_all_difficulty_levels(self) -> None:
        """Test all difficulty levels exist."""
        levels = list(DifficultyLevel)
        assert DifficultyLevel.EASY in levels
        assert DifficultyLevel.MEDIUM in levels
        assert DifficultyLevel.HARD in levels
        assert DifficultyLevel.EXPERT in levels
