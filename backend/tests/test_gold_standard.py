"""Tests for Gold Standard Dataset Management.

Tests cover:
- Dataset creation and listing
- Annotation management
- Evaluation accuracy calculation
- Per-class metrics (precision, recall, F1)
- Confusion matrix generation
- Inter-annotator agreement
- Fixture file loading
- API endpoints (CRUD and evaluation)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.gold_standard import GoldStandardDomain, Prediction
from app.services.gold_standard_service import (
    GoldStandardService,
    get_gold_standard_service,
    reset_gold_standard_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_gold_standard_service()
    yield
    reset_gold_standard_service()


@pytest.fixture
def service() -> GoldStandardService:
    return get_gold_standard_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Dataset Creation Tests
# ============================================================================


class TestDatasetCreation:
    """Tests for creating gold standard datasets."""

    def test_create_dataset(self, service: GoldStandardService):
        ds = service.create_dataset(
            name="nlp-test",
            domain=GoldStandardDomain.NLP_EXTRACTION,
            description="NLP extraction benchmark",
            version="1.0.0",
        )
        assert ds.name == "nlp-test"
        assert ds.domain == GoldStandardDomain.NLP_EXTRACTION
        assert ds.description == "NLP extraction benchmark"
        assert ds.version == "1.0.0"
        assert ds.annotation_count == 0
        assert ds.id is not None
        assert ds.created_at is not None

    def test_create_dataset_duplicate_returns_existing(self, service: GoldStandardService):
        ds1 = service.create_dataset("test", GoldStandardDomain.OMOP_MAPPING, version="1.0.0")
        ds2 = service.create_dataset("test", GoldStandardDomain.OMOP_MAPPING, version="1.0.0")
        assert ds1.id == ds2.id
        assert ds1.created_at == ds2.created_at

    def test_create_dataset_different_versions(self, service: GoldStandardService):
        ds1 = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION, version="1.0.0")
        ds2 = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION, version="2.0.0")
        assert ds1.id != ds2.id

    def test_list_datasets_empty(self, service: GoldStandardService):
        assert service.list_datasets() == []

    def test_list_datasets(self, service: GoldStandardService):
        service.create_dataset("ds1", GoldStandardDomain.NLP_EXTRACTION)
        service.create_dataset("ds2", GoldStandardDomain.OMOP_MAPPING)
        service.create_dataset("ds3", GoldStandardDomain.TRIAL_SCREENING)
        datasets = service.list_datasets()
        assert len(datasets) == 3

    def test_list_datasets_filtered_by_domain(self, service: GoldStandardService):
        service.create_dataset("ds1", GoldStandardDomain.NLP_EXTRACTION)
        service.create_dataset("ds2", GoldStandardDomain.OMOP_MAPPING)
        service.create_dataset("ds3", GoldStandardDomain.NLP_EXTRACTION)
        datasets = service.list_datasets(domain=GoldStandardDomain.NLP_EXTRACTION)
        assert len(datasets) == 2
        assert all(d.domain == GoldStandardDomain.NLP_EXTRACTION for d in datasets)

    def test_get_dataset_by_name(self, service: GoldStandardService):
        service.create_dataset("my-dataset", GoldStandardDomain.TRIAL_SCREENING)
        result = service.get_dataset("my-dataset")
        assert result is not None
        assert result.name == "my-dataset"

    def test_get_dataset_by_name_and_version(self, service: GoldStandardService):
        service.create_dataset("my-dataset", GoldStandardDomain.NLP_EXTRACTION, version="1.0.0")
        service.create_dataset("my-dataset", GoldStandardDomain.NLP_EXTRACTION, version="2.0.0")
        result = service.get_dataset("my-dataset", version="1.0.0")
        assert result is not None
        assert result.version == "1.0.0"

    def test_get_dataset_not_found(self, service: GoldStandardService):
        assert service.get_dataset("nonexistent") is None


# ============================================================================
# Annotation Management Tests
# ============================================================================


class TestAnnotationManagement:
    """Tests for adding and retrieving annotations."""

    def test_add_annotation(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        ann = service.add_annotation(
            dataset_id=ds.id,
            input_data={"text": "Patient has diabetes."},
            expected_output={"mentions": [{"text": "diabetes", "domain": "CONDITION"}]},
            annotator_id="annotator-1",
        )
        assert ann.id is not None
        assert ann.dataset_id == ds.id
        assert ann.input_data["text"] == "Patient has diabetes."
        assert ann.annotator_id == "annotator-1"

    def test_add_annotation_updates_count(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        service.add_annotation(ds.id, {"text": "a"}, {"label": "x"})
        service.add_annotation(ds.id, {"text": "b"}, {"label": "y"})

        # Re-fetch to get updated count
        updated_ds = service.get_dataset("test")
        assert updated_ds is not None
        assert updated_ds.annotation_count == 2

    def test_add_annotation_invalid_dataset(self, service: GoldStandardService):
        with pytest.raises(ValueError, match="not found"):
            service.add_annotation(
                dataset_id="nonexistent-id",
                input_data={"text": "a"},
                expected_output={"label": "x"},
            )

    def test_get_annotations(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        service.add_annotation(ds.id, {"text": "a"}, {"label": "x"})
        service.add_annotation(ds.id, {"text": "b"}, {"label": "y"})
        annotations = service.get_annotations(ds.id)
        assert len(annotations) == 2


# ============================================================================
# Evaluation Tests
# ============================================================================


class TestEvaluation:
    """Tests for evaluating predictions against gold standard."""

    def test_perfect_accuracy(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        a1 = service.add_annotation(ds.id, {"text": "a"}, {"label": "CONDITION"})
        a2 = service.add_annotation(ds.id, {"text": "b"}, {"label": "MEDICATION"})
        a3 = service.add_annotation(ds.id, {"text": "c"}, {"label": "CONDITION"})

        predictions = [
            Prediction(annotation_id=a1.id, predicted_output={"label": "CONDITION"}),
            Prediction(annotation_id=a2.id, predicted_output={"label": "MEDICATION"}),
            Prediction(annotation_id=a3.id, predicted_output={"label": "CONDITION"}),
        ]
        result = service.evaluate_against(ds.id, predictions)
        assert result.total == 3
        assert result.correct == 3
        assert result.incorrect == 0
        assert result.accuracy == 1.0

    def test_partial_accuracy(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        a1 = service.add_annotation(ds.id, {"text": "a"}, {"label": "CONDITION"})
        a2 = service.add_annotation(ds.id, {"text": "b"}, {"label": "MEDICATION"})

        predictions = [
            Prediction(annotation_id=a1.id, predicted_output={"label": "CONDITION"}),
            Prediction(annotation_id=a2.id, predicted_output={"label": "CONDITION"}),  # wrong
        ]
        result = service.evaluate_against(ds.id, predictions)
        assert result.total == 2
        assert result.correct == 1
        assert result.incorrect == 1
        assert result.accuracy == 0.5

    def test_per_class_metrics(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        # 3 CONDITION (2 correct, 1 wrong), 2 MEDICATION (1 correct, 1 wrong)
        a1 = service.add_annotation(ds.id, {"text": "a"}, {"label": "CONDITION"})
        a2 = service.add_annotation(ds.id, {"text": "b"}, {"label": "CONDITION"})
        a3 = service.add_annotation(ds.id, {"text": "c"}, {"label": "CONDITION"})
        a4 = service.add_annotation(ds.id, {"text": "d"}, {"label": "MEDICATION"})
        a5 = service.add_annotation(ds.id, {"text": "e"}, {"label": "MEDICATION"})

        predictions = [
            Prediction(annotation_id=a1.id, predicted_output={"label": "CONDITION"}),
            Prediction(annotation_id=a2.id, predicted_output={"label": "CONDITION"}),
            Prediction(annotation_id=a3.id, predicted_output={"label": "MEDICATION"}),  # wrong
            Prediction(annotation_id=a4.id, predicted_output={"label": "MEDICATION"}),
            Prediction(annotation_id=a5.id, predicted_output={"label": "CONDITION"}),  # wrong
        ]
        result = service.evaluate_against(ds.id, predictions)

        assert result.total == 5
        assert result.correct == 3
        assert result.incorrect == 2

        # Check per-class metrics
        condition_metric = next(
            m for m in result.per_class_metrics if m.class_name == "CONDITION"
        )
        # CONDITION: TP=2, FP=1 (a5 predicted CONDITION but was MEDICATION), FN=1 (a3 was CONDITION but predicted MEDICATION)
        assert condition_metric.support == 3
        assert condition_metric.precision == pytest.approx(2 / 3, abs=0.01)
        assert condition_metric.recall == pytest.approx(2 / 3, abs=0.01)

        medication_metric = next(
            m for m in result.per_class_metrics if m.class_name == "MEDICATION"
        )
        # MEDICATION: TP=1, FP=1 (a3 predicted MEDICATION but was CONDITION), FN=1 (a5 was MEDICATION but predicted CONDITION)
        assert medication_metric.support == 2
        assert medication_metric.precision == pytest.approx(1 / 2, abs=0.01)
        assert medication_metric.recall == pytest.approx(1 / 2, abs=0.01)

    def test_confusion_data(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        a1 = service.add_annotation(ds.id, {"text": "a"}, {"label": "A"})
        a2 = service.add_annotation(ds.id, {"text": "b"}, {"label": "A"})
        a3 = service.add_annotation(ds.id, {"text": "c"}, {"label": "B"})

        predictions = [
            Prediction(annotation_id=a1.id, predicted_output={"label": "A"}),
            Prediction(annotation_id=a2.id, predicted_output={"label": "B"}),  # misclassified
            Prediction(annotation_id=a3.id, predicted_output={"label": "B"}),
        ]
        result = service.evaluate_against(ds.id, predictions)

        assert "A" in result.confusion_data
        assert result.confusion_data["A"]["A"] == 1
        assert result.confusion_data["A"]["B"] == 1
        assert result.confusion_data["B"]["B"] == 1

    def test_evaluate_unknown_annotation_counted_incorrect(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        predictions = [
            Prediction(annotation_id="nonexistent", predicted_output={"label": "X"}),
        ]
        result = service.evaluate_against(ds.id, predictions)
        assert result.total == 1
        assert result.incorrect == 1
        assert result.accuracy == 0.0

    def test_evaluate_invalid_dataset(self, service: GoldStandardService):
        with pytest.raises(ValueError, match="not found"):
            service.evaluate_against("bad-id", [])


# ============================================================================
# Inter-Annotator Agreement Tests
# ============================================================================


class TestInterAnnotatorAgreement:
    """Tests for inter-annotator agreement metrics."""

    def test_iaa_perfect_agreement(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        # Both annotators agree on the same input
        service.add_annotation(
            ds.id, {"text": "diabetes"}, {"label": "CONDITION"}, annotator_id="ann-1"
        )
        service.add_annotation(
            ds.id, {"text": "diabetes"}, {"label": "CONDITION"}, annotator_id="ann-2"
        )

        iaa = service.get_inter_annotator_agreement(ds.id)
        assert iaa.annotator_count == 2
        assert iaa.pairwise_agreement == 1.0
        assert "ann-1" in iaa.annotators
        assert "ann-2" in iaa.annotators

    def test_iaa_no_agreement(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        service.add_annotation(
            ds.id, {"text": "pain"}, {"label": "CONDITION"}, annotator_id="ann-1"
        )
        service.add_annotation(
            ds.id, {"text": "pain"}, {"label": "SYMPTOM"}, annotator_id="ann-2"
        )

        iaa = service.get_inter_annotator_agreement(ds.id)
        assert iaa.pairwise_agreement == 0.0

    def test_iaa_requires_two_annotators(self, service: GoldStandardService):
        ds = service.create_dataset("test", GoldStandardDomain.NLP_EXTRACTION)
        service.add_annotation(ds.id, {"text": "a"}, {"label": "X"}, annotator_id="ann-1")

        with pytest.raises(ValueError, match="at least 2 annotators"):
            service.get_inter_annotator_agreement(ds.id)

    def test_iaa_invalid_dataset(self, service: GoldStandardService):
        with pytest.raises(ValueError, match="not found"):
            service.get_inter_annotator_agreement("bad-id")


# ============================================================================
# Fixture Loading Tests
# ============================================================================


class TestFixtureLoading:
    """Tests for loading pre-built fixture datasets."""

    def test_load_nlp_extraction_fixture(self, service: GoldStandardService):
        ds = service.load_fixture("nlp_extraction_gold.json")
        assert ds.name == "nlp-extraction-gold"
        assert ds.domain == GoldStandardDomain.NLP_EXTRACTION
        assert ds.annotation_count == 50

    def test_load_omop_mapping_fixture(self, service: GoldStandardService):
        ds = service.load_fixture("omop_mapping_gold.json")
        assert ds.name == "omop-mapping-gold"
        assert ds.domain == GoldStandardDomain.OMOP_MAPPING
        assert ds.annotation_count == 100

    def test_load_screening_fixture(self, service: GoldStandardService):
        ds = service.load_fixture("screening_gold.json")
        assert ds.name == "screening-gold"
        assert ds.domain == GoldStandardDomain.TRIAL_SCREENING
        assert ds.annotation_count == 30

    def test_load_fixture_not_found(self, service: GoldStandardService):
        with pytest.raises(FileNotFoundError, match="not found"):
            service.load_fixture("nonexistent.json")

    def test_loaded_fixture_has_annotations(self, service: GoldStandardService):
        ds = service.load_fixture("nlp_extraction_gold.json")
        annotations = service.get_annotations(ds.id)
        assert len(annotations) == 50
        # Verify annotation structure
        first = annotations[0]
        assert "text" in first.input_data
        assert "mentions" in first.expected_output


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for the REST API layer."""

    @pytest.mark.asyncio
    async def test_create_dataset_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/ml/gold-standard",
                json={
                    "name": "api-test",
                    "domain": "nlp_extraction",
                    "description": "API test dataset",
                    "version": "1.0.0",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "api-test"
        assert data["domain"] == "nlp_extraction"
        assert data["annotation_count"] == 0

    @pytest.mark.asyncio
    async def test_list_datasets_api(self, client):
        svc = get_gold_standard_service()
        svc.create_dataset("ds1", GoldStandardDomain.NLP_EXTRACTION)
        svc.create_dataset("ds2", GoldStandardDomain.OMOP_MAPPING)

        async with client as ac:
            response = await ac.get("/api/v1/ml/gold-standard")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_list_datasets_filtered_api(self, client):
        svc = get_gold_standard_service()
        svc.create_dataset("ds1", GoldStandardDomain.NLP_EXTRACTION)
        svc.create_dataset("ds2", GoldStandardDomain.OMOP_MAPPING)

        async with client as ac:
            response = await ac.get(
                "/api/v1/ml/gold-standard",
                params={"domain": "nlp_extraction"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_get_dataset_api(self, client):
        svc = get_gold_standard_service()
        ds = svc.create_dataset("my-ds", GoldStandardDomain.TRIAL_SCREENING)
        svc.add_annotation(ds.id, {"text": "a"}, {"label": "x"})

        async with client as ac:
            response = await ac.get("/api/v1/ml/gold-standard/my-ds")
        assert response.status_code == 200
        data = response.json()
        assert data["dataset"]["name"] == "my-ds"
        assert len(data["annotations"]) == 1

    @pytest.mark.asyncio
    async def test_get_dataset_not_found_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/ml/gold-standard/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_annotation_api(self, client):
        svc = get_gold_standard_service()
        svc.create_dataset("my-ds", GoldStandardDomain.NLP_EXTRACTION)

        async with client as ac:
            response = await ac.post(
                "/api/v1/ml/gold-standard/my-ds/annotations",
                json={
                    "input_data": {"text": "Patient has hypertension."},
                    "expected_output": {"mentions": [{"text": "hypertension", "domain": "CONDITION"}]},
                    "annotator_id": "test-annotator",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["annotator_id"] == "test-annotator"
        assert data["input_data"]["text"] == "Patient has hypertension."

    @pytest.mark.asyncio
    async def test_evaluate_api(self, client):
        svc = get_gold_standard_service()
        ds = svc.create_dataset("eval-ds", GoldStandardDomain.NLP_EXTRACTION)
        a1 = svc.add_annotation(ds.id, {"text": "a"}, {"label": "CONDITION"})
        a2 = svc.add_annotation(ds.id, {"text": "b"}, {"label": "MEDICATION"})

        async with client as ac:
            response = await ac.post(
                "/api/v1/ml/gold-standard/eval-ds/evaluate",
                json={
                    "predictions": [
                        {"annotation_id": a1.id, "predicted_output": {"label": "CONDITION"}},
                        {"annotation_id": a2.id, "predicted_output": {"label": "MEDICATION"}},
                    ]
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["correct"] == 2
        assert data["accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_not_found_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/ml/gold-standard/nonexistent/evaluate",
                json={
                    "predictions": [
                        {"annotation_id": "x", "predicted_output": {"label": "A"}},
                    ]
                },
            )
        assert response.status_code == 404
