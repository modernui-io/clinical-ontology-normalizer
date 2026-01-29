"""ML Model Service for Predictive Analytics.

Provides comprehensive ML model management:
- Model registry (store/load models with versioning)
- Training pipeline for sklearn/XGBoost models
- Inference API with batch and single prediction
- Feature engineering utilities
- Model performance tracking (AUC, calibration)
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    auc,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class ModelType(str, Enum):
    """Supported model types."""

    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    NEURAL_NETWORK = "neural_network"


class ModelStatus(str, Enum):
    """Model lifecycle status."""

    TRAINING = "training"
    VALIDATING = "validating"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PredictionType(str, Enum):
    """Type of prediction task."""

    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    REGRESSION = "regression"
    SURVIVAL = "survival"


# ============================================================================
# Pydantic Models
# ============================================================================


class ModelMetadata(BaseModel):
    """Model metadata for registry."""

    model_id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    version: str = Field(..., description="Model version (semver)")
    model_type: ModelType = Field(..., description="Type of ML model")
    prediction_type: PredictionType = Field(..., description="Type of prediction")
    status: ModelStatus = Field(default=ModelStatus.TRAINING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")
    description: str | None = Field(None)
    tags: list[str] = Field(default_factory=list)
    feature_names: list[str] = Field(default_factory=list)
    target_name: str = Field(default="target")
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    training_data_hash: str | None = Field(None)
    training_samples: int = Field(default=0)
    training_time_seconds: float = Field(default=0.0)


class ModelPerformance(BaseModel):
    """Model performance metrics."""

    model_id: str = Field(..., description="Model identifier")
    version: str = Field(..., description="Model version")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dataset_type: str = Field(default="validation", description="train/validation/test")
    sample_count: int = Field(default=0)

    # Classification metrics
    auc_roc: float | None = Field(None, ge=0, le=1)
    auc_pr: float | None = Field(None, ge=0, le=1)
    accuracy: float | None = Field(None, ge=0, le=1)
    precision: float | None = Field(None, ge=0, le=1)
    recall: float | None = Field(None, ge=0, le=1)
    f1: float | None = Field(None, ge=0, le=1)
    specificity: float | None = Field(None, ge=0, le=1)

    # Calibration metrics
    brier_score: float | None = Field(None, ge=0, le=1)
    calibration_slope: float | None = Field(None)
    calibration_intercept: float | None = Field(None)
    expected_calibration_error: float | None = Field(None)

    # ROC curve data
    roc_curve_fpr: list[float] = Field(default_factory=list)
    roc_curve_tpr: list[float] = Field(default_factory=list)
    roc_curve_thresholds: list[float] = Field(default_factory=list)

    # PR curve data
    pr_curve_precision: list[float] = Field(default_factory=list)
    pr_curve_recall: list[float] = Field(default_factory=list)

    # Calibration curve data
    calibration_prob_true: list[float] = Field(default_factory=list)
    calibration_prob_pred: list[float] = Field(default_factory=list)

    # Confusion matrix
    confusion_matrix: list[list[int]] | None = Field(None)

    # Feature importance
    feature_importance: dict[str, float] = Field(default_factory=dict)


class FeatureSet(BaseModel):
    """Feature set for prediction."""

    patient_id: str = Field(..., description="Patient identifier")
    features: dict[str, float | int | str | None] = Field(..., description="Feature values")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PredictionResult(BaseModel):
    """Result of a single prediction."""

    patient_id: str = Field(..., description="Patient identifier")
    model_id: str = Field(..., description="Model used for prediction")
    model_version: str = Field(..., description="Model version")
    prediction: float = Field(..., description="Predicted probability or value")
    prediction_label: str | None = Field(None, description="Predicted class label")
    confidence: float = Field(..., ge=0, le=1, description="Prediction confidence")
    risk_tier: str | None = Field(None, description="Risk tier classification")
    predicted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    feature_contributions: dict[str, float] = Field(
        default_factory=dict, description="SHAP-like feature contributions"
    )
    explanation: str | None = Field(None, description="Human-readable explanation")


class BatchPredictionResult(BaseModel):
    """Result of batch predictions."""

    model_id: str
    model_version: str
    total_predictions: int
    successful: int
    failed: int
    predictions: list[PredictionResult]
    processing_time_ms: float
    predicted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrainingConfig(BaseModel):
    """Configuration for model training."""

    model_type: ModelType = Field(default=ModelType.GRADIENT_BOOSTING)
    prediction_type: PredictionType = Field(default=PredictionType.BINARY_CLASSIFICATION)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    validation_split: float = Field(default=0.2, ge=0.1, le=0.4)
    cross_validation_folds: int = Field(default=5, ge=2, le=10)
    random_state: int = Field(default=42)
    early_stopping_rounds: int | None = Field(default=10)
    class_weight: str | None = Field(default="balanced")


class TrainingResult(BaseModel):
    """Result from model training."""

    model_id: str
    version: str
    status: ModelStatus
    training_time_seconds: float
    validation_performance: ModelPerformance | None
    cross_validation_scores: list[float] = Field(default_factory=list)
    cv_mean: float | None = None
    cv_std: float | None = None
    message: str | None = None


# ============================================================================
# Feature Engineering
# ============================================================================


class FeatureEngineer:
    """Feature engineering utilities for clinical data."""

    @staticmethod
    def normalize_numeric(value: float, mean: float, std: float) -> float:
        """Z-score normalization."""
        if std == 0:
            return 0.0
        return (value - mean) / std

    @staticmethod
    def min_max_scale(value: float, min_val: float, max_val: float) -> float:
        """Min-max scaling to [0, 1]."""
        if max_val == min_val:
            return 0.5
        return (value - min_val) / (max_val - min_val)

    @staticmethod
    def encode_categorical(value: str, categories: list[str]) -> list[int]:
        """One-hot encode categorical value."""
        encoding = [0] * len(categories)
        if value in categories:
            encoding[categories.index(value)] = 1
        return encoding

    @staticmethod
    def bin_continuous(
        value: float, bins: list[float], labels: list[str] | None = None
    ) -> str | int:
        """Bin continuous variable into categories."""
        for i, threshold in enumerate(bins):
            if value <= threshold:
                return labels[i] if labels else i
        return labels[-1] if labels else len(bins)

    @staticmethod
    def calculate_age_from_dob(dob: datetime, reference_date: datetime | None = None) -> int:
        """Calculate age from date of birth."""
        if reference_date is None:
            reference_date = datetime.now(timezone.utc)
        age = reference_date.year - dob.year
        if (reference_date.month, reference_date.day) < (dob.month, dob.day):
            age -= 1
        return age

    @staticmethod
    def calculate_comorbidity_count(conditions: list[str], comorbidity_list: list[str]) -> int:
        """Count matching comorbidities."""
        return sum(1 for c in conditions if c.lower() in [x.lower() for x in comorbidity_list])

    @staticmethod
    def days_since_event(event_date: datetime, reference_date: datetime | None = None) -> int:
        """Calculate days since an event."""
        if reference_date is None:
            reference_date = datetime.now(timezone.utc)
        return (reference_date - event_date).days

    @staticmethod
    def extract_numeric_features(data: dict[str, Any], numeric_keys: list[str]) -> np.ndarray:
        """Extract numeric features from a dictionary."""
        return np.array([float(data.get(key, 0) or 0) for key in numeric_keys])


# ============================================================================
# Model Registry
# ============================================================================


class ModelRegistry:
    """In-memory model registry with versioning support."""

    def __init__(self, storage_path: Path | None = None):
        """Initialize the model registry.

        Args:
            storage_path: Optional path to persist models on disk.
        """
        self._models: dict[str, dict[str, Any]] = {}  # model_id -> version -> model
        self._metadata: dict[str, dict[str, ModelMetadata]] = {}  # model_id -> version -> metadata
        self._performance: dict[str, dict[str, list[ModelPerformance]]] = {}
        self._active_versions: dict[str, str] = {}  # model_id -> active version
        self._storage_path = storage_path

    def register_model(
        self,
        model: Any,
        metadata: ModelMetadata,
    ) -> str:
        """Register a new model in the registry.

        Args:
            model: The trained model object.
            metadata: Model metadata.

        Returns:
            The model ID.
        """
        model_id = metadata.model_id
        version = metadata.version

        if model_id not in self._models:
            self._models[model_id] = {}
            self._metadata[model_id] = {}
            self._performance[model_id] = {}

        self._models[model_id][version] = model
        self._metadata[model_id][version] = metadata
        self._performance[model_id][version] = []

        # If this is the first version or marked as active, set as active
        if metadata.status == ModelStatus.ACTIVE or model_id not in self._active_versions:
            self._active_versions[model_id] = version

        logger.info(f"Registered model {model_id} version {version}")
        return model_id

    def get_model(self, model_id: str, version: str | None = None) -> tuple[Any, ModelMetadata]:
        """Retrieve a model from the registry.

        Args:
            model_id: The model identifier.
            version: Optional specific version (defaults to active version).

        Returns:
            Tuple of (model, metadata).

        Raises:
            KeyError: If model or version not found.
        """
        if model_id not in self._models:
            raise KeyError(f"Model {model_id} not found in registry")

        if version is None:
            version = self._active_versions.get(model_id)
            if version is None:
                raise KeyError(f"No active version for model {model_id}")

        if version not in self._models[model_id]:
            raise KeyError(f"Version {version} not found for model {model_id}")

        return self._models[model_id][version], self._metadata[model_id][version]

    def list_models(self) -> list[ModelMetadata]:
        """List all models with their active versions."""
        result = []
        for model_id, versions in self._metadata.items():
            active_version = self._active_versions.get(model_id)
            if active_version and active_version in versions:
                result.append(versions[active_version])
        return result

    def list_versions(self, model_id: str) -> list[ModelMetadata]:
        """List all versions of a specific model."""
        if model_id not in self._metadata:
            return []
        return list(self._metadata[model_id].values())

    def set_active_version(self, model_id: str, version: str) -> None:
        """Set the active version for a model."""
        if model_id not in self._models or version not in self._models[model_id]:
            raise KeyError(f"Model {model_id} version {version} not found")
        self._active_versions[model_id] = version

        # Update metadata status
        for v, meta in self._metadata[model_id].items():
            if v == version:
                meta.status = ModelStatus.ACTIVE
            elif meta.status == ModelStatus.ACTIVE:
                meta.status = ModelStatus.DEPRECATED

    def add_performance(self, model_id: str, version: str, performance: ModelPerformance) -> None:
        """Add performance metrics for a model version."""
        if model_id not in self._performance:
            self._performance[model_id] = {}
        if version not in self._performance[model_id]:
            self._performance[model_id][version] = []
        self._performance[model_id][version].append(performance)

    def get_performance(self, model_id: str, version: str | None = None) -> list[ModelPerformance]:
        """Get performance metrics for a model."""
        if model_id not in self._performance:
            return []
        if version is None:
            version = self._active_versions.get(model_id)
        if version is None or version not in self._performance[model_id]:
            return []
        return self._performance[model_id][version]

    def delete_model(self, model_id: str, version: str | None = None) -> None:
        """Delete a model or specific version."""
        if model_id not in self._models:
            return

        if version:
            self._models[model_id].pop(version, None)
            self._metadata[model_id].pop(version, None)
            self._performance[model_id].pop(version, None)
            if self._active_versions.get(model_id) == version:
                # Set a new active version if possible
                remaining = list(self._models[model_id].keys())
                if remaining:
                    self._active_versions[model_id] = remaining[0]
                else:
                    del self._active_versions[model_id]
        else:
            del self._models[model_id]
            del self._metadata[model_id]
            del self._performance[model_id]
            self._active_versions.pop(model_id, None)


# ============================================================================
# ML Model Service
# ============================================================================


class MLModelService:
    """Comprehensive ML model service for predictive analytics."""

    def __init__(self):
        """Initialize the ML model service."""
        self._registry = ModelRegistry()
        self._feature_engineer = FeatureEngineer()
        self._initialized = False
        self._load_demo_models()

    def _load_demo_models(self) -> None:
        """Load demonstration models for testing."""
        # Create mock models for demonstration
        demo_models = [
            {
                "model_id": "readmission-risk-v1",
                "name": "30-Day Readmission Risk Model",
                "version": "1.2.0",
                "model_type": ModelType.GRADIENT_BOOSTING,
                "prediction_type": PredictionType.BINARY_CLASSIFICATION,
                "description": "Predicts 30-day hospital readmission risk using LACE+ features",
                "tags": ["readmission", "lace", "hospital", "production"],
                "feature_names": [
                    "length_of_stay",
                    "acuity_score",
                    "comorbidity_count",
                    "ed_visits_6mo",
                    "age",
                    "discharge_disposition",
                    "prior_admissions",
                    "medication_count",
                ],
            },
            {
                "model_id": "deterioration-risk-v1",
                "name": "Clinical Deterioration Risk (NEWS2)",
                "version": "2.0.0",
                "model_type": ModelType.XGBOOST,
                "prediction_type": PredictionType.BINARY_CLASSIFICATION,
                "description": "Predicts risk of clinical deterioration using NEWS2 enhanced features",
                "tags": ["deterioration", "news2", "early-warning", "production"],
                "feature_names": [
                    "respiratory_rate",
                    "oxygen_saturation",
                    "supplemental_oxygen",
                    "systolic_bp",
                    "heart_rate",
                    "consciousness_level",
                    "temperature",
                    "age",
                ],
            },
            {
                "model_id": "mortality-risk-v1",
                "name": "Mortality Risk Stratification",
                "version": "1.0.5",
                "model_type": ModelType.GRADIENT_BOOSTING,
                "prediction_type": PredictionType.BINARY_CLASSIFICATION,
                "description": "In-hospital mortality risk using Charlson/Elixhauser comorbidity indices",
                "tags": ["mortality", "charlson", "elixhauser", "production"],
                "feature_names": [
                    "charlson_score",
                    "elixhauser_score",
                    "age",
                    "admission_type",
                    "icu_admission",
                    "mechanical_ventilation",
                    "vasopressor_use",
                    "creatinine",
                    "bilirubin",
                ],
            },
        ]

        for config in demo_models:
            # Create a mock model (in production, this would be a real trained model)
            mock_model = self._create_mock_model(config["model_type"])

            metadata = ModelMetadata(
                model_id=config["model_id"],
                name=config["name"],
                version=config["version"],
                model_type=config["model_type"],
                prediction_type=config["prediction_type"],
                status=ModelStatus.ACTIVE,
                description=config["description"],
                tags=config["tags"],
                feature_names=config["feature_names"],
                training_samples=50000,
                training_time_seconds=120.5,
            )

            self._registry.register_model(mock_model, metadata)

            # Add mock performance metrics
            performance = self._create_mock_performance(config["model_id"], config["version"])
            self._registry.add_performance(config["model_id"], config["version"], performance)

        self._initialized = True
        logger.info(f"Loaded {len(demo_models)} demonstration models")

    def _create_mock_model(self, model_type: ModelType) -> dict[str, Any]:
        """Create a mock model for demonstration."""
        # In production, this would return an actual sklearn/XGBoost model
        return {
            "type": model_type.value,
            "coefficients": np.random.randn(10).tolist(),
            "intercept": np.random.randn(),
            "created": datetime.now(timezone.utc).isoformat(),
        }

    def _create_mock_performance(self, model_id: str, version: str) -> ModelPerformance:
        """Create mock performance metrics for demonstration."""
        # Generate realistic-looking metrics
        auc = 0.75 + np.random.random() * 0.15  # AUC between 0.75-0.90

        return ModelPerformance(
            model_id=model_id,
            version=version,
            dataset_type="validation",
            sample_count=10000,
            auc_roc=round(auc, 4),
            auc_pr=round(auc - 0.05, 4),
            accuracy=round(0.7 + np.random.random() * 0.15, 4),
            precision=round(0.65 + np.random.random() * 0.2, 4),
            recall=round(0.6 + np.random.random() * 0.25, 4),
            f1=round(0.65 + np.random.random() * 0.15, 4),
            specificity=round(0.75 + np.random.random() * 0.15, 4),
            brier_score=round(0.1 + np.random.random() * 0.1, 4),
            calibration_slope=round(0.9 + np.random.random() * 0.2, 4),
            calibration_intercept=round(-0.1 + np.random.random() * 0.2, 4),
            expected_calibration_error=round(0.02 + np.random.random() * 0.05, 4),
            roc_curve_fpr=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            roc_curve_tpr=[0.0, 0.4, 0.55, 0.65, 0.73, 0.8, 0.85, 0.9, 0.94, 0.97, 1.0],
            pr_curve_precision=[1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1],
            pr_curve_recall=[0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 1.0],
            calibration_prob_true=[0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
            calibration_prob_pred=[0.06, 0.14, 0.26, 0.34, 0.46, 0.54, 0.66, 0.74, 0.86, 0.94],
            feature_importance={
                "length_of_stay": 0.25,
                "acuity_score": 0.18,
                "comorbidity_count": 0.15,
                "ed_visits_6mo": 0.12,
                "age": 0.10,
                "prior_admissions": 0.08,
                "medication_count": 0.07,
                "discharge_disposition": 0.05,
            },
        )

    def list_models(self) -> list[ModelMetadata]:
        """List all registered models."""
        return self._registry.list_models()

    def get_model_metadata(self, model_id: str, version: str | None = None) -> ModelMetadata:
        """Get model metadata."""
        _, metadata = self._registry.get_model(model_id, version)
        return metadata

    def get_model_performance(
        self, model_id: str, version: str | None = None
    ) -> list[ModelPerformance]:
        """Get model performance metrics."""
        return self._registry.get_performance(model_id, version)

    def predict(self, model_id: str, feature_set: FeatureSet) -> PredictionResult:
        """Make a single prediction.

        Args:
            model_id: Model to use for prediction.
            feature_set: Features for the patient.

        Returns:
            PredictionResult with prediction and explanation.
        """
        model, metadata = self._registry.get_model(model_id)

        # In production, this would use the actual model for prediction
        # For demo, generate realistic predictions based on features
        prediction = self._simulate_prediction(model, metadata, feature_set)

        # Apply calibration if available
        try:
            from app.services.prediction_calibration_service import (
                get_prediction_calibration_service,
            )

            calibration_service = get_prediction_calibration_service()
            calibrated_scores = calibration_service.apply_calibration(
                model_id, metadata.version, [prediction.prediction], strict=False
            )
            if calibrated_scores:
                calibrated = float(calibrated_scores[0])
                if abs(calibrated - prediction.prediction) > 1e-6:
                    calibrated = round(calibrated, 4)
                    prediction = prediction.model_copy(
                        update={
                            "prediction": calibrated,
                            "confidence": round(abs(calibrated - 0.5) * 2, 4),
                            "risk_tier": self._risk_tier_from_probability(calibrated),
                            "prediction_label": "Positive" if calibrated >= 0.5 else "Negative",
                        }
                    )
        except Exception as exc:
            logger.debug(f"Calibration skipped for {model_id}: {exc}")

        return prediction

    def predict_batch(
        self, model_id: str, feature_sets: list[FeatureSet]
    ) -> BatchPredictionResult:
        """Make batch predictions.

        Args:
            model_id: Model to use for prediction.
            feature_sets: List of feature sets for multiple patients.

        Returns:
            BatchPredictionResult with all predictions.
        """
        start_time = time.perf_counter()
        _, metadata = self._registry.get_model(model_id)

        predictions = []
        successful = 0
        failed = 0

        for fs in feature_sets:
            try:
                pred = self.predict(model_id, fs)
                predictions.append(pred)
                successful += 1
            except Exception as e:
                logger.warning(f"Prediction failed for patient {fs.patient_id}: {e}")
                failed += 1

        processing_time = (time.perf_counter() - start_time) * 1000

        return BatchPredictionResult(
            model_id=model_id,
            model_version=metadata.version,
            total_predictions=len(feature_sets),
            successful=successful,
            failed=failed,
            predictions=predictions,
            processing_time_ms=round(processing_time, 2),
        )

    def _simulate_prediction(
        self, model: dict[str, Any], metadata: ModelMetadata, feature_set: FeatureSet
    ) -> PredictionResult:
        """Simulate a prediction for demonstration.

        In production, this would use the actual model to make predictions.
        """
        # Create a deterministic but realistic prediction based on features
        features = feature_set.features
        seed = int(hashlib.md5(feature_set.patient_id.encode()).hexdigest()[:8], 16)
        np.random.seed(seed)

        # Base prediction influenced by key features
        base_prob = 0.2

        # Adjust based on available features
        if "length_of_stay" in features:
            los = float(features.get("length_of_stay", 0) or 0)
            base_prob += min(los / 30, 0.3)  # Longer stays increase risk

        if "comorbidity_count" in features:
            comorbidities = int(features.get("comorbidity_count", 0) or 0)
            base_prob += comorbidities * 0.05

        if "age" in features:
            age = int(features.get("age", 50) or 50)
            if age > 65:
                base_prob += (age - 65) * 0.005

        if "ed_visits_6mo" in features:
            ed_visits = int(features.get("ed_visits_6mo", 0) or 0)
            base_prob += ed_visits * 0.08

        # Add some noise
        base_prob += np.random.normal(0, 0.05)

        # Clamp to valid probability range
        prediction = max(0.01, min(0.99, base_prob))

        risk_tier = self._risk_tier_from_probability(prediction)

        # Generate feature contributions (mock SHAP values)
        contributions = {}
        feature_names = metadata.feature_names
        for name in feature_names:
            if name in features:
                contributions[name] = round(np.random.uniform(-0.2, 0.2), 4)

        # Generate explanation
        top_factors = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        explanation_parts = []
        for factor, contrib in top_factors:
            direction = "increases" if contrib > 0 else "decreases"
            explanation_parts.append(f"{factor.replace('_', ' ')} {direction} risk")

        explanation = f"{risk_tier} risk. Key factors: {', '.join(explanation_parts)}."

        return PredictionResult(
            patient_id=feature_set.patient_id,
            model_id=metadata.model_id,
            model_version=metadata.version,
            prediction=round(prediction, 4),
            prediction_label="Positive" if prediction >= 0.5 else "Negative",
            confidence=round(abs(prediction - 0.5) * 2, 4),  # Distance from 0.5
            risk_tier=risk_tier,
            feature_contributions=contributions,
            explanation=explanation,
        )

    @staticmethod
    def _risk_tier_from_probability(prediction: float) -> str:
        if prediction >= 0.7:
            return "Critical"
        if prediction >= 0.5:
            return "High"
        if prediction >= 0.3:
            return "Medium"
        return "Low"

    def train_model(
        self,
        name: str,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        config: TrainingConfig,
    ) -> TrainingResult:
        """Train a new model.

        Args:
            name: Name for the model.
            X: Feature matrix.
            y: Target vector.
            feature_names: Names of features.
            config: Training configuration.

        Returns:
            TrainingResult with model info and performance.
        """
        start_time = time.perf_counter()
        model_id = f"{name.lower().replace(' ', '-')}-{str(uuid4())[:8]}"
        version = "1.0.0"

        try:
            # Create and train the model based on type
            model = self._train_model_by_type(X, y, config)

            training_time = time.perf_counter() - start_time

            # Calculate data hash for reproducibility
            data_hash = hashlib.md5(X.tobytes() + y.tobytes()).hexdigest()[:16]

            # Create metadata
            metadata = ModelMetadata(
                model_id=model_id,
                name=name,
                version=version,
                model_type=config.model_type,
                prediction_type=config.prediction_type,
                status=ModelStatus.ACTIVE,
                feature_names=feature_names,
                hyperparameters=config.hyperparameters,
                training_data_hash=data_hash,
                training_samples=len(y),
                training_time_seconds=training_time,
            )

            # Register the model
            self._registry.register_model(model, metadata)

            # Evaluate on validation set
            performance = self._evaluate_model(model, X, y, model_id, version)
            self._registry.add_performance(model_id, version, performance)

            return TrainingResult(
                model_id=model_id,
                version=version,
                status=ModelStatus.ACTIVE,
                training_time_seconds=round(training_time, 2),
                validation_performance=performance,
                message="Model trained successfully",
            )

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return TrainingResult(
                model_id=model_id,
                version=version,
                status=ModelStatus.ARCHIVED,
                training_time_seconds=time.perf_counter() - start_time,
                validation_performance=None,
                message=f"Training failed: {str(e)}",
            )

    def _train_model_by_type(
        self, X: np.ndarray, y: np.ndarray, config: TrainingConfig
    ) -> Any:
        """Train a model based on the specified type."""
        # Import here to avoid circular imports and allow optional dependencies
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.linear_model import LogisticRegression

        if config.model_type == ModelType.LOGISTIC_REGRESSION:
            model = LogisticRegression(
                random_state=config.random_state,
                class_weight=config.class_weight,
                max_iter=1000,
                **config.hyperparameters,
            )
        elif config.model_type == ModelType.RANDOM_FOREST:
            model = RandomForestClassifier(
                random_state=config.random_state,
                class_weight=config.class_weight,
                n_estimators=100,
                **config.hyperparameters,
            )
        elif config.model_type == ModelType.GRADIENT_BOOSTING:
            model = GradientBoostingClassifier(
                random_state=config.random_state,
                n_estimators=100,
                **config.hyperparameters,
            )
        else:
            # Default to Gradient Boosting
            model = GradientBoostingClassifier(
                random_state=config.random_state,
                n_estimators=100,
            )

        model.fit(X, y)
        return model

    def _evaluate_model(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        model_id: str,
        version: str,
    ) -> ModelPerformance:
        """Evaluate a trained model."""
        # Get predictions
        y_pred = model.predict(X)
        y_prob = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else y_pred

        # Calculate metrics
        fpr, tpr, thresholds = roc_curve(y, y_prob)
        precision_arr, recall_arr, _ = precision_recall_curve(y, y_prob)

        # Calibration
        prob_true, prob_pred = calibration_curve(y, y_prob, n_bins=10, strategy="uniform")

        # Feature importance
        feature_importance = {}
        if hasattr(model, "feature_importances_"):
            # Tree-based models
            for i, imp in enumerate(model.feature_importances_):
                feature_importance[f"feature_{i}"] = float(imp)
        elif hasattr(model, "coef_"):
            # Linear models
            for i, coef in enumerate(model.coef_[0]):
                feature_importance[f"feature_{i}"] = float(abs(coef))

        return ModelPerformance(
            model_id=model_id,
            version=version,
            dataset_type="validation",
            sample_count=len(y),
            auc_roc=round(roc_auc_score(y, y_prob), 4),
            auc_pr=round(auc(recall_arr, precision_arr), 4),
            accuracy=round(accuracy_score(y, y_pred), 4),
            precision=round(precision_score(y, y_pred, zero_division=0), 4),
            recall=round(recall_score(y, y_pred, zero_division=0), 4),
            f1=round(f1_score(y, y_pred, zero_division=0), 4),
            brier_score=round(brier_score_loss(y, y_prob), 4),
            roc_curve_fpr=fpr.tolist(),
            roc_curve_tpr=tpr.tolist(),
            roc_curve_thresholds=thresholds.tolist(),
            pr_curve_precision=precision_arr.tolist(),
            pr_curve_recall=recall_arr.tolist(),
            calibration_prob_true=prob_true.tolist(),
            calibration_prob_pred=prob_pred.tolist(),
            feature_importance=feature_importance,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        models = self._registry.list_models()
        return {
            "total_models": len(models),
            "active_models": len([m for m in models if m.status == ModelStatus.ACTIVE]),
            "model_types": list(set(m.model_type.value for m in models)),
            "initialized": self._initialized,
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_ml_model_service: MLModelService | None = None


def get_ml_model_service() -> MLModelService:
    """Get the singleton ML model service instance."""
    global _ml_model_service
    if _ml_model_service is None:
        _ml_model_service = MLModelService()
    return _ml_model_service
