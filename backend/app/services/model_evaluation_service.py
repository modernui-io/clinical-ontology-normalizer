"""Model Evaluation Service.

Provides a lightweight, in-memory framework for tracking and comparing
ML model performance over time.  Supports:
- Model registration with metadata
- Recording evaluation runs with arbitrary metrics
- Retrieving evaluation history for a model
- Comparing two versions of a model
- Selecting the best version by a given metric
- Regression detection between consecutive versions
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.model_evaluation import (
    ComparisonResult,
    EvaluationRun,
    MetricComparison,
    ModelInfo,
    ModelType,
    RegressionCheck,
)

logger = logging.getLogger(__name__)


class ModelEvaluationService:
    """In-memory model evaluation tracking service."""

    def __init__(self) -> None:
        # model_name -> {version -> ModelInfo}
        self._models: dict[str, dict[str, ModelInfo]] = {}
        # model_name -> list[EvaluationRun]  (ordered by timestamp)
        self._evaluations: dict[str, list[EvaluationRun]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Model registration
    # ------------------------------------------------------------------

    def register_model(
        self,
        name: str,
        version: str,
        model_type: ModelType,
        description: str = "",
    ) -> ModelInfo:
        """Register a model with metadata.

        If the same (name, version) already exists the existing entry is
        returned unchanged.
        """
        with self._lock:
            if name not in self._models:
                self._models[name] = {}

            if version in self._models[name]:
                logger.info(f"Model {name} v{version} already registered")
                return self._models[name][version]

            info = ModelInfo(
                name=name,
                version=version,
                model_type=model_type,
                description=description,
            )
            self._models[name][version] = info
            logger.info(f"Registered model {name} v{version} ({model_type.value})")
            return info

    def list_models(self) -> list[ModelInfo]:
        """Return all registered model entries (all versions)."""
        result: list[ModelInfo] = []
        for versions in self._models.values():
            result.extend(versions.values())
        return result

    def get_model(self, name: str, version: str | None = None) -> ModelInfo | None:
        """Return a single model entry, or None if not found."""
        versions = self._models.get(name)
        if versions is None:
            return None
        if version is not None:
            return versions.get(version)
        # Return latest registered version
        if versions:
            return list(versions.values())[-1]
        return None

    # ------------------------------------------------------------------
    # Evaluation recording
    # ------------------------------------------------------------------

    def record_evaluation(
        self,
        model_name: str,
        model_version: str,
        dataset_name: str,
        metrics: dict[str, float],
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationRun:
        """Record an evaluation run for a model version."""
        run = EvaluationRun(
            id=str(uuid4()),
            model_name=model_name,
            model_version=model_version,
            dataset_name=dataset_name,
            metrics=metrics,
            metadata=metadata or {},
        )

        with self._lock:
            if model_name not in self._evaluations:
                self._evaluations[model_name] = []
            self._evaluations[model_name].append(run)

        logger.info(
            f"Recorded evaluation {run.id} for {model_name} v{model_version} "
            f"on dataset {dataset_name}"
        )
        return run

    # ------------------------------------------------------------------
    # History & querying
    # ------------------------------------------------------------------

    def get_model_history(
        self,
        model_name: str,
        version: str | None = None,
    ) -> list[EvaluationRun]:
        """Return evaluation history for a model, optionally filtered by version."""
        runs = self._evaluations.get(model_name, [])
        if version is not None:
            runs = [r for r in runs if r.model_version == version]
        return runs

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    def compare_versions(
        self,
        model_name: str,
        version_a: str,
        version_b: str,
    ) -> ComparisonResult:
        """Compare the *latest* evaluation of two model versions.

        For each metric present in *both* evaluations, compute the diff,
        percentage change, and whether version B improved.

        Raises:
            ValueError: If no evaluations exist for either version.
        """
        runs = self._evaluations.get(model_name, [])
        runs_a = [r for r in runs if r.model_version == version_a]
        runs_b = [r for r in runs if r.model_version == version_b]

        if not runs_a:
            raise ValueError(
                f"No evaluations found for {model_name} v{version_a}"
            )
        if not runs_b:
            raise ValueError(
                f"No evaluations found for {model_name} v{version_b}"
            )

        latest_a = runs_a[-1]
        latest_b = runs_b[-1]

        comparisons: list[MetricComparison] = []
        all_metrics = set(latest_a.metrics.keys()) | set(latest_b.metrics.keys())

        for metric in sorted(all_metrics):
            if metric not in latest_a.metrics or metric not in latest_b.metrics:
                continue
            val_a = latest_a.metrics[metric]
            val_b = latest_b.metrics[metric]
            diff = val_b - val_a
            diff_pct = (diff / val_a * 100) if val_a != 0 else 0.0

            comparisons.append(
                MetricComparison(
                    metric=metric,
                    value_a=val_a,
                    value_b=val_b,
                    diff=round(diff, 6),
                    diff_pct=round(diff_pct, 4),
                    improved=val_b > val_a,
                )
            )

        return ComparisonResult(
            model_name=model_name,
            version_a=version_a,
            version_b=version_b,
            metric_comparisons=comparisons,
        )

    def get_best_model(
        self,
        model_name: str,
        metric: str,
    ) -> EvaluationRun | None:
        """Return the evaluation run with the highest value for *metric*.

        Returns None if no evaluations contain the given metric.
        """
        runs = self._evaluations.get(model_name, [])
        candidates = [r for r in runs if metric in r.metrics]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.metrics[metric])

    def check_regression(
        self,
        model_name: str,
        metric: str,
        threshold: float = 0.0,
    ) -> RegressionCheck:
        """Check whether the latest evaluation regressed on *metric*.

        A regression is detected when the latest value is worse (lower)
        than the previous evaluation value by more than *threshold*.

        Raises:
            ValueError: If fewer than two evaluations contain the metric.
        """
        runs = self._evaluations.get(model_name, [])
        candidates = [r for r in runs if metric in r.metrics]

        if len(candidates) < 2:
            raise ValueError(
                f"Need at least 2 evaluations with metric '{metric}' "
                f"for {model_name}; found {len(candidates)}"
            )

        previous = candidates[-2]
        current = candidates[-1]

        prev_val = previous.metrics[metric]
        curr_val = current.metrics[metric]
        is_regression = (prev_val - curr_val) > threshold

        return RegressionCheck(
            model_name=model_name,
            metric=metric,
            current_value=curr_val,
            previous_value=prev_val,
            threshold=threshold,
            is_regression=is_regression,
        )


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_service: ModelEvaluationService | None = None
_service_lock = threading.Lock()


def get_model_evaluation_service() -> ModelEvaluationService:
    """Return the singleton ModelEvaluationService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = ModelEvaluationService()
    return _service


def reset_model_evaluation_service() -> None:
    """Reset the singleton (useful for test isolation)."""
    global _service
    with _service_lock:
        _service = None
