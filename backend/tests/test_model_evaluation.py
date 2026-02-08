"""Tests for Model Evaluation Framework.

Tests cover:
- Model registration
- Evaluation recording
- History retrieval
- Version comparison
- Best model selection
- Regression detection
- API endpoints
- Realistic NLP model metrics
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.model_evaluation import ModelType
from app.services.model_evaluation_service import (
    ModelEvaluationService,
    get_model_evaluation_service,
    reset_model_evaluation_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_model_evaluation_service()
    yield
    reset_model_evaluation_service()


@pytest.fixture
def service() -> ModelEvaluationService:
    return get_model_evaluation_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Model Registration Tests
# ============================================================================


class TestModelRegistration:
    """Tests for model registration."""

    def test_register_model(self, service: ModelEvaluationService):
        info = service.register_model(
            name="ner-extractor",
            version="1.0.0",
            model_type=ModelType.NLP_EXTRACTION,
            description="Named entity recognition for clinical text",
        )
        assert info.name == "ner-extractor"
        assert info.version == "1.0.0"
        assert info.model_type == ModelType.NLP_EXTRACTION
        assert info.description == "Named entity recognition for clinical text"
        assert info.registered_at is not None

    def test_register_duplicate_returns_existing(self, service: ModelEvaluationService):
        info1 = service.register_model(
            name="ner-extractor",
            version="1.0.0",
            model_type=ModelType.NLP_EXTRACTION,
        )
        info2 = service.register_model(
            name="ner-extractor",
            version="1.0.0",
            model_type=ModelType.NLP_EXTRACTION,
        )
        assert info1.registered_at == info2.registered_at

    def test_register_multiple_versions(self, service: ModelEvaluationService):
        service.register_model("mapper", "1.0.0", ModelType.OMOP_MAPPING)
        service.register_model("mapper", "2.0.0", ModelType.OMOP_MAPPING)
        models = service.list_models()
        mapper_versions = [m for m in models if m.name == "mapper"]
        assert len(mapper_versions) == 2

    def test_list_models_empty(self, service: ModelEvaluationService):
        assert service.list_models() == []

    def test_get_model_by_name(self, service: ModelEvaluationService):
        service.register_model("classifier", "1.0.0", ModelType.ASSERTION_CLASSIFIER)
        result = service.get_model("classifier")
        assert result is not None
        assert result.name == "classifier"

    def test_get_model_not_found(self, service: ModelEvaluationService):
        assert service.get_model("nonexistent") is None


# ============================================================================
# Evaluation Recording Tests
# ============================================================================


class TestEvaluationRecording:
    """Tests for recording evaluation runs."""

    def test_record_evaluation(self, service: ModelEvaluationService):
        run = service.record_evaluation(
            model_name="ner-extractor",
            model_version="1.0.0",
            dataset_name="clinical-notes-test",
            metrics={"precision": 0.85, "recall": 0.78, "f1": 0.81},
        )
        assert run.id is not None
        assert run.model_name == "ner-extractor"
        assert run.model_version == "1.0.0"
        assert run.dataset_name == "clinical-notes-test"
        assert run.metrics["precision"] == 0.85
        assert run.metrics["recall"] == 0.78
        assert run.metrics["f1"] == 0.81
        assert run.timestamp is not None

    def test_record_evaluation_with_metadata(self, service: ModelEvaluationService):
        run = service.record_evaluation(
            model_name="ner-extractor",
            model_version="1.0.0",
            dataset_name="test-set",
            metrics={"f1": 0.90},
            metadata={"gpu": "A100", "batch_size": 32},
        )
        assert run.metadata["gpu"] == "A100"
        assert run.metadata["batch_size"] == 32


# ============================================================================
# History Retrieval Tests
# ============================================================================


class TestHistoryRetrieval:
    """Tests for evaluation history retrieval."""

    def test_get_history(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds1", {"f1": 0.80})
        service.record_evaluation("m1", "1.0", "ds2", {"f1": 0.82})
        service.record_evaluation("m1", "2.0", "ds1", {"f1": 0.85})

        history = service.get_model_history("m1")
        assert len(history) == 3

    def test_get_history_filtered_by_version(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds1", {"f1": 0.80})
        service.record_evaluation("m1", "2.0", "ds1", {"f1": 0.85})

        history = service.get_model_history("m1", version="1.0")
        assert len(history) == 1
        assert history[0].model_version == "1.0"

    def test_get_history_empty(self, service: ModelEvaluationService):
        assert service.get_model_history("unknown") == []


# ============================================================================
# Version Comparison Tests
# ============================================================================


class TestVersionComparison:
    """Tests for comparing model versions."""

    def test_compare_versions(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds", {"precision": 0.80, "recall": 0.70})
        service.record_evaluation("m1", "2.0", "ds", {"precision": 0.85, "recall": 0.75})

        result = service.compare_versions("m1", "1.0", "2.0")
        assert result.model_name == "m1"
        assert result.version_a == "1.0"
        assert result.version_b == "2.0"
        assert len(result.metric_comparisons) == 2

        precision_cmp = next(c for c in result.metric_comparisons if c.metric == "precision")
        assert precision_cmp.value_a == 0.80
        assert precision_cmp.value_b == 0.85
        assert precision_cmp.improved is True

    def test_compare_versions_no_evaluations(self, service: ModelEvaluationService):
        with pytest.raises(ValueError, match="No evaluations found"):
            service.compare_versions("m1", "1.0", "2.0")

    def test_compare_versions_partial_metrics(self, service: ModelEvaluationService):
        """Only metrics present in both versions are compared."""
        service.record_evaluation("m1", "1.0", "ds", {"f1": 0.80, "auc": 0.90})
        service.record_evaluation("m1", "2.0", "ds", {"f1": 0.85, "precision": 0.88})

        result = service.compare_versions("m1", "1.0", "2.0")
        metric_names = [c.metric for c in result.metric_comparisons]
        assert "f1" in metric_names
        assert "auc" not in metric_names
        assert "precision" not in metric_names


# ============================================================================
# Best Model Selection Tests
# ============================================================================


class TestBestModelSelection:
    """Tests for selecting the best model version."""

    def test_get_best_model(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds", {"f1": 0.80})
        service.record_evaluation("m1", "2.0", "ds", {"f1": 0.85})
        service.record_evaluation("m1", "3.0", "ds", {"f1": 0.82})

        best = service.get_best_model("m1", "f1")
        assert best is not None
        assert best.model_version == "2.0"
        assert best.metrics["f1"] == 0.85

    def test_get_best_model_no_metric(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds", {"precision": 0.80})
        assert service.get_best_model("m1", "f1") is None

    def test_get_best_model_no_evaluations(self, service: ModelEvaluationService):
        assert service.get_best_model("unknown", "f1") is None


# ============================================================================
# Regression Detection Tests
# ============================================================================


class TestRegressionDetection:
    """Tests for regression detection."""

    def test_regression_detected(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds", {"f1": 0.85})
        service.record_evaluation("m1", "2.0", "ds", {"f1": 0.78})

        check = service.check_regression("m1", "f1", threshold=0.0)
        assert check.is_regression is True
        assert check.current_value == 0.78
        assert check.previous_value == 0.85

    def test_no_regression_improved(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds", {"f1": 0.80})
        service.record_evaluation("m1", "2.0", "ds", {"f1": 0.85})

        check = service.check_regression("m1", "f1", threshold=0.0)
        assert check.is_regression is False

    def test_regression_within_threshold(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds", {"f1": 0.85})
        service.record_evaluation("m1", "2.0", "ds", {"f1": 0.83})

        # Drop of 0.02 is within threshold of 0.05
        check = service.check_regression("m1", "f1", threshold=0.05)
        assert check.is_regression is False
        assert check.threshold == 0.05

    def test_regression_insufficient_evaluations(self, service: ModelEvaluationService):
        service.record_evaluation("m1", "1.0", "ds", {"f1": 0.85})
        with pytest.raises(ValueError, match="Need at least 2 evaluations"):
            service.check_regression("m1", "f1")


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for the REST API layer."""

    @pytest.mark.asyncio
    async def test_register_model_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/ml/models",
                json={
                    "name": "ner-extractor",
                    "version": "1.0.0",
                    "model_type": "nlp_extraction",
                    "description": "NER model",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "ner-extractor"
        assert data["version"] == "1.0.0"
        assert data["model_type"] == "nlp_extraction"

    @pytest.mark.asyncio
    async def test_list_models_api(self, client):
        svc = get_model_evaluation_service()
        svc.register_model("m1", "1.0", ModelType.NLP_EXTRACTION)

        async with client as ac:
            response = await ac.get("/api/v1/ml/models")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_record_evaluation_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/ml/evaluations",
                json={
                    "model_name": "m1",
                    "model_version": "1.0",
                    "dataset_name": "test-set",
                    "metrics": {"f1": 0.88, "precision": 0.90},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["f1"] == 0.88

    @pytest.mark.asyncio
    async def test_get_history_api(self, client):
        svc = get_model_evaluation_service()
        svc.record_evaluation("m1", "1.0", "ds", {"f1": 0.80})

        async with client as ac:
            response = await ac.get("/api/v1/ml/models/m1/history")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_compare_versions_api(self, client):
        svc = get_model_evaluation_service()
        svc.record_evaluation("m1", "1.0", "ds", {"f1": 0.80})
        svc.record_evaluation("m1", "2.0", "ds", {"f1": 0.85})

        async with client as ac:
            response = await ac.get(
                "/api/v1/ml/models/m1/compare",
                params={"version_a": "1.0", "version_b": "2.0"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["version_a"] == "1.0"
        assert data["version_b"] == "2.0"
        assert len(data["metric_comparisons"]) == 1

    @pytest.mark.asyncio
    async def test_regression_check_api(self, client):
        svc = get_model_evaluation_service()
        svc.record_evaluation("m1", "1.0", "ds", {"f1": 0.85})
        svc.record_evaluation("m1", "2.0", "ds", {"f1": 0.78})

        async with client as ac:
            response = await ac.get(
                "/api/v1/ml/models/m1/regression-check",
                params={"metric": "f1"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["is_regression"] is True

    @pytest.mark.asyncio
    async def test_best_model_api(self, client):
        svc = get_model_evaluation_service()
        svc.record_evaluation("m1", "1.0", "ds", {"f1": 0.80})
        svc.record_evaluation("m1", "2.0", "ds", {"f1": 0.90})

        async with client as ac:
            response = await ac.get(
                "/api/v1/ml/models/m1/best",
                params={"metric": "f1"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["model_version"] == "2.0"

    @pytest.mark.asyncio
    async def test_best_model_not_found(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/ml/models/nonexistent/best",
                params={"metric": "f1"},
            )
        assert response.status_code == 404


# ============================================================================
# Realistic NLP Model Metrics Tests
# ============================================================================


class TestRealisticNLPMetrics:
    """Tests with realistic NLP model evaluation scenarios."""

    def test_nlp_extraction_evaluation(self, service: ModelEvaluationService):
        """Test recording and comparing NLP extraction model evaluations."""
        service.register_model(
            name="clinical-ner",
            version="1.0.0",
            model_type=ModelType.NLP_EXTRACTION,
            description="Clinical NER using BioBERT",
        )
        service.register_model(
            name="clinical-ner",
            version="2.0.0",
            model_type=ModelType.NLP_EXTRACTION,
            description="Clinical NER using PubMedBERT",
        )

        # v1 evaluation
        service.record_evaluation(
            model_name="clinical-ner",
            model_version="1.0.0",
            dataset_name="i2b2-2010",
            metrics={
                "precision": 0.843,
                "recall": 0.791,
                "f1": 0.816,
                "accuracy": 0.924,
                "entity_f1_problem": 0.801,
                "entity_f1_treatment": 0.830,
                "entity_f1_test": 0.795,
            },
            metadata={"epochs": 10, "learning_rate": 2e-5},
        )

        # v2 evaluation (improved)
        service.record_evaluation(
            model_name="clinical-ner",
            model_version="2.0.0",
            dataset_name="i2b2-2010",
            metrics={
                "precision": 0.871,
                "recall": 0.829,
                "f1": 0.849,
                "accuracy": 0.941,
                "entity_f1_problem": 0.838,
                "entity_f1_treatment": 0.862,
                "entity_f1_test": 0.831,
            },
            metadata={"epochs": 15, "learning_rate": 1e-5},
        )

        # Compare
        comparison = service.compare_versions("clinical-ner", "1.0.0", "2.0.0")
        f1_cmp = next(c for c in comparison.metric_comparisons if c.metric == "f1")
        assert f1_cmp.improved is True
        assert f1_cmp.value_b > f1_cmp.value_a

        # Best
        best = service.get_best_model("clinical-ner", "f1")
        assert best is not None
        assert best.model_version == "2.0.0"

        # No regression
        check = service.check_regression("clinical-ner", "f1")
        assert check.is_regression is False

    def test_trial_matching_evaluation(self, service: ModelEvaluationService):
        """Test trial matching model evaluation workflow."""
        service.register_model(
            name="trial-matcher",
            version="1.0.0",
            model_type=ModelType.TRIAL_MATCHING,
            description="Eligibility criteria matching",
        )

        service.record_evaluation(
            model_name="trial-matcher",
            model_version="1.0.0",
            dataset_name="regeneron-criteria",
            metrics={
                "precision": 0.92,
                "recall": 0.87,
                "f1": 0.894,
                "accuracy": 0.95,
            },
        )

        history = service.get_model_history("trial-matcher")
        assert len(history) == 1
        assert history[0].metrics["precision"] == 0.92
