"""Model Registry Service for ML model versioning and lifecycle management.

Provides functionality to:
- Register and version ML models
- Track model metadata and performance metrics
- Manage model lifecycle (staging, production, archived)
- Store model artifacts and dependencies
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ModelStage(str, Enum):
    """Model lifecycle stages."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class ModelType(str, Enum):
    """Types of ML models."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    NLP = "nlp"
    CLUSTERING = "clustering"
    RECOMMENDATION = "recommendation"
    ANOMALY_DETECTION = "anomaly_detection"
    TIME_SERIES = "time_series"


@dataclass
class ModelVersion:
    """A specific version of a model."""

    version: str
    stage: ModelStage
    created_at: datetime
    created_by: str
    description: str
    metrics: dict[str, float]  # accuracy, precision, recall, f1, auc, etc.
    parameters: dict[str, Any]  # hyperparameters
    artifact_path: str | None
    signature: dict[str, Any] | None  # input/output schema
    is_current: bool = False


@dataclass
class RegisteredModel:
    """A registered ML model with versions."""

    id: str
    name: str
    model_type: ModelType
    description: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    tags: list[str]
    versions: list[ModelVersion]
    latest_version: str | None
    production_version: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelRegistryService:
    """Service for managing ML model registry."""

    def __init__(self) -> None:
        """Initialize the model registry service."""
        self._models: dict[str, RegisteredModel] = {}
        self._lock = threading.Lock()
        self._init_sample_models()

    def _init_sample_models(self) -> None:
        """Initialize sample models for demonstration."""
        now = datetime.now()

        # Mortality risk model
        mortality_model = RegisteredModel(
            id=str(uuid4()),
            name="mortality_risk_v1",
            model_type=ModelType.CLASSIFICATION,
            description="30-day mortality risk prediction model",
            created_at=now,
            updated_at=now,
            created_by="ml-team",
            tags=["risk", "mortality", "clinical"],
            versions=[
                ModelVersion(
                    version="1.0.0",
                    stage=ModelStage.PRODUCTION,
                    created_at=now,
                    created_by="ml-team",
                    description="Initial production release",
                    metrics={"auc": 0.87, "precision": 0.82, "recall": 0.79, "f1": 0.80},
                    parameters={"n_estimators": 100, "max_depth": 10, "learning_rate": 0.1},
                    artifact_path="/models/mortality_risk_v1/1.0.0",
                    signature={"input": ["age", "comorbidities", "vitals"], "output": "risk_score"},
                    is_current=True,
                ),
                ModelVersion(
                    version="0.9.0",
                    stage=ModelStage.ARCHIVED,
                    created_at=now,
                    created_by="ml-team",
                    description="Beta version",
                    metrics={"auc": 0.83, "precision": 0.78, "recall": 0.75, "f1": 0.76},
                    parameters={"n_estimators": 50, "max_depth": 8, "learning_rate": 0.05},
                    artifact_path="/models/mortality_risk_v1/0.9.0",
                    signature=None,
                ),
            ],
            latest_version="1.0.0",
            production_version="1.0.0",
        )

        # Readmission model
        readmission_model = RegisteredModel(
            id=str(uuid4()),
            name="readmission_30day",
            model_type=ModelType.CLASSIFICATION,
            description="30-day hospital readmission prediction",
            created_at=now,
            updated_at=now,
            created_by="ml-team",
            tags=["risk", "readmission", "clinical"],
            versions=[
                ModelVersion(
                    version="2.1.0",
                    stage=ModelStage.STAGING,
                    created_at=now,
                    created_by="ml-team",
                    description="Improved feature set",
                    metrics={"auc": 0.78, "precision": 0.72, "recall": 0.68, "f1": 0.70},
                    parameters={"model_type": "gradient_boosting", "n_estimators": 200},
                    artifact_path="/models/readmission_30day/2.1.0",
                    signature=None,
                    is_current=True,
                ),
            ],
            latest_version="2.1.0",
            production_version=None,
        )

        self._models[mortality_model.id] = mortality_model
        self._models[readmission_model.id] = readmission_model

    def register_model(
        self,
        name: str,
        model_type: ModelType,
        description: str,
        created_by: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegisteredModel:
        """Register a new model."""
        model_id = str(uuid4())
        now = datetime.now()

        model = RegisteredModel(
            id=model_id,
            name=name,
            model_type=model_type,
            description=description,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            tags=tags or [],
            versions=[],
            latest_version=None,
            production_version=None,
            metadata=metadata or {},
        )

        with self._lock:
            self._models[model_id] = model

        logger.info(f"Registered model: {name} ({model_id})")
        return model

    def get_model(self, model_id: str) -> RegisteredModel | None:
        """Get a model by ID."""
        return self._models.get(model_id)

    def get_model_by_name(self, name: str) -> RegisteredModel | None:
        """Get a model by name."""
        for model in self._models.values():
            if model.name == name:
                return model
        return None

    def list_models(
        self,
        model_type: ModelType | None = None,
        stage: ModelStage | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> list[RegisteredModel]:
        """List registered models with optional filtering."""
        models = list(self._models.values())

        if model_type:
            models = [m for m in models if m.model_type == model_type]

        if stage:
            models = [
                m for m in models
                if any(v.stage == stage for v in m.versions)
            ]

        if tag:
            models = [m for m in models if tag in m.tags]

        models.sort(key=lambda m: m.updated_at, reverse=True)
        return models[:limit]

    def add_version(
        self,
        model_id: str,
        version: str,
        description: str,
        created_by: str,
        metrics: dict[str, float],
        parameters: dict[str, Any],
        artifact_path: str | None = None,
        signature: dict[str, Any] | None = None,
    ) -> ModelVersion | None:
        """Add a new version to a model."""
        with self._lock:
            model = self._models.get(model_id)
            if not model:
                return None

            # Check if version already exists
            if any(v.version == version for v in model.versions):
                return None

            new_version = ModelVersion(
                version=version,
                stage=ModelStage.DEVELOPMENT,
                created_at=datetime.now(),
                created_by=created_by,
                description=description,
                metrics=metrics,
                parameters=parameters,
                artifact_path=artifact_path,
                signature=signature,
                is_current=True,
            )

            # Unmark previous current version
            for v in model.versions:
                v.is_current = False

            model.versions.append(new_version)
            model.latest_version = version
            model.updated_at = datetime.now()

            logger.info(f"Added version {version} to model {model.name}")
            return new_version

    def transition_stage(
        self,
        model_id: str,
        version: str,
        new_stage: ModelStage,
    ) -> ModelVersion | None:
        """Transition a model version to a new stage."""
        with self._lock:
            model = self._models.get(model_id)
            if not model:
                return None

            version_obj = next(
                (v for v in model.versions if v.version == version),
                None
            )
            if not version_obj:
                return None

            old_stage = version_obj.stage
            version_obj.stage = new_stage

            # Update production version tracking
            if new_stage == ModelStage.PRODUCTION:
                # Archive previous production version
                for v in model.versions:
                    if v.version != version and v.stage == ModelStage.PRODUCTION:
                        v.stage = ModelStage.ARCHIVED
                model.production_version = version
            elif old_stage == ModelStage.PRODUCTION:
                model.production_version = None

            model.updated_at = datetime.now()

            logger.info(f"Transitioned {model.name}:{version} from {old_stage} to {new_stage}")
            return version_obj

    def delete_model(self, model_id: str) -> bool:
        """Delete a model."""
        with self._lock:
            if model_id in self._models:
                del self._models[model_id]
                logger.info(f"Deleted model: {model_id}")
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        models = list(self._models.values())

        by_type: dict[str, int] = {}
        for model in models:
            by_type[model.model_type.value] = by_type.get(model.model_type.value, 0) + 1

        total_versions = sum(len(m.versions) for m in models)
        production_models = sum(1 for m in models if m.production_version)

        return {
            "total_models": len(models),
            "total_versions": total_versions,
            "production_models": production_models,
            "models_by_type": by_type,
        }


# Singleton instance
_model_registry_service: ModelRegistryService | None = None
_model_registry_lock = threading.Lock()


def get_model_registry_service() -> ModelRegistryService:
    """Get the singleton ModelRegistryService instance."""
    global _model_registry_service

    if _model_registry_service is None:
        with _model_registry_lock:
            if _model_registry_service is None:
                logger.info("Creating singleton ModelRegistryService instance")
                _model_registry_service = ModelRegistryService()

    return _model_registry_service


def reset_model_registry_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _model_registry_service
    with _model_registry_lock:
        _model_registry_service = None
