"""Risk Thresholds Service for managing ML model thresholds.

Provides functionality to configure and manage risk thresholds
for various predictive models (mortality, readmission, etc.).
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class RiskModel(str, Enum):
    """Available risk prediction models."""

    MORTALITY = "mortality"
    READMISSION_30DAY = "readmission_30day"
    READMISSION_90DAY = "readmission_90day"
    FALL_RISK = "fall_risk"
    SEPSIS = "sepsis"
    DETERIORATION = "deterioration"
    LOS_EXTENDED = "los_extended"  # Length of stay


class RiskTier(str, Enum):
    """Risk tiers for patient classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ThresholdConfig:
    """Configuration for a single threshold tier."""

    tier: RiskTier
    min_score: float
    max_score: float
    color: str
    label: str
    alert_enabled: bool = True


@dataclass
class ModelThresholds:
    """Complete threshold configuration for a risk model."""

    model: RiskModel
    thresholds: list[ThresholdConfig]
    description: str
    version: str
    updated_at: datetime
    updated_by: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_tier(self, score: float) -> RiskTier:
        """Get the risk tier for a given score."""
        for threshold in self.thresholds:
            if threshold.min_score <= score <= threshold.max_score:
                return threshold.tier
        # Default to highest tier if score exceeds all thresholds
        return RiskTier.CRITICAL if score > 0.5 else RiskTier.LOW


# Default thresholds for each model
DEFAULT_THRESHOLDS: dict[RiskModel, ModelThresholds] = {
    RiskModel.MORTALITY: ModelThresholds(
        model=RiskModel.MORTALITY,
        thresholds=[
            ThresholdConfig(RiskTier.LOW, 0.0, 0.2, "#4CAF50", "Low Risk"),
            ThresholdConfig(RiskTier.MEDIUM, 0.2, 0.5, "#FFC107", "Moderate Risk"),
            ThresholdConfig(RiskTier.HIGH, 0.5, 0.8, "#FF9800", "High Risk"),
            ThresholdConfig(RiskTier.CRITICAL, 0.8, 1.0, "#F44336", "Critical Risk"),
        ],
        description="30-day in-hospital mortality risk thresholds",
        version="1.0.0",
        updated_at=datetime.now(timezone.utc),
        updated_by="system",
    ),
    RiskModel.READMISSION_30DAY: ModelThresholds(
        model=RiskModel.READMISSION_30DAY,
        thresholds=[
            ThresholdConfig(RiskTier.LOW, 0.0, 0.15, "#4CAF50", "Low Risk"),
            ThresholdConfig(RiskTier.MEDIUM, 0.15, 0.4, "#FFC107", "Moderate Risk"),
            ThresholdConfig(RiskTier.HIGH, 0.4, 0.7, "#FF9800", "High Risk"),
            ThresholdConfig(RiskTier.CRITICAL, 0.7, 1.0, "#F44336", "Critical Risk"),
        ],
        description="30-day hospital readmission risk thresholds",
        version="1.0.0",
        updated_at=datetime.now(timezone.utc),
        updated_by="system",
    ),
    RiskModel.READMISSION_90DAY: ModelThresholds(
        model=RiskModel.READMISSION_90DAY,
        thresholds=[
            ThresholdConfig(RiskTier.LOW, 0.0, 0.2, "#4CAF50", "Low Risk"),
            ThresholdConfig(RiskTier.MEDIUM, 0.2, 0.45, "#FFC107", "Moderate Risk"),
            ThresholdConfig(RiskTier.HIGH, 0.45, 0.75, "#FF9800", "High Risk"),
            ThresholdConfig(RiskTier.CRITICAL, 0.75, 1.0, "#F44336", "Critical Risk"),
        ],
        description="90-day hospital readmission risk thresholds",
        version="1.0.0",
        updated_at=datetime.now(timezone.utc),
        updated_by="system",
    ),
    RiskModel.FALL_RISK: ModelThresholds(
        model=RiskModel.FALL_RISK,
        thresholds=[
            ThresholdConfig(RiskTier.LOW, 0.0, 0.25, "#4CAF50", "Low Risk"),
            ThresholdConfig(RiskTier.MEDIUM, 0.25, 0.5, "#FFC107", "Moderate Risk"),
            ThresholdConfig(RiskTier.HIGH, 0.5, 0.75, "#FF9800", "High Risk"),
            ThresholdConfig(RiskTier.CRITICAL, 0.75, 1.0, "#F44336", "Critical Risk"),
        ],
        description="Patient fall risk thresholds",
        version="1.0.0",
        updated_at=datetime.now(timezone.utc),
        updated_by="system",
    ),
    RiskModel.SEPSIS: ModelThresholds(
        model=RiskModel.SEPSIS,
        thresholds=[
            ThresholdConfig(RiskTier.LOW, 0.0, 0.1, "#4CAF50", "Low Risk"),
            ThresholdConfig(RiskTier.MEDIUM, 0.1, 0.3, "#FFC107", "Moderate Risk"),
            ThresholdConfig(RiskTier.HIGH, 0.3, 0.6, "#FF9800", "High Risk"),
            ThresholdConfig(RiskTier.CRITICAL, 0.6, 1.0, "#F44336", "Critical Risk", alert_enabled=True),
        ],
        description="Sepsis risk thresholds (qSOFA-based)",
        version="1.0.0",
        updated_at=datetime.now(timezone.utc),
        updated_by="system",
    ),
    RiskModel.DETERIORATION: ModelThresholds(
        model=RiskModel.DETERIORATION,
        thresholds=[
            ThresholdConfig(RiskTier.LOW, 0.0, 0.15, "#4CAF50", "Stable"),
            ThresholdConfig(RiskTier.MEDIUM, 0.15, 0.35, "#FFC107", "Watch"),
            ThresholdConfig(RiskTier.HIGH, 0.35, 0.6, "#FF9800", "Concern"),
            ThresholdConfig(RiskTier.CRITICAL, 0.6, 1.0, "#F44336", "Urgent"),
        ],
        description="Patient deterioration risk (NEWS2-based)",
        version="1.0.0",
        updated_at=datetime.now(timezone.utc),
        updated_by="system",
    ),
    RiskModel.LOS_EXTENDED: ModelThresholds(
        model=RiskModel.LOS_EXTENDED,
        thresholds=[
            ThresholdConfig(RiskTier.LOW, 0.0, 0.25, "#4CAF50", "Short Stay Expected"),
            ThresholdConfig(RiskTier.MEDIUM, 0.25, 0.5, "#FFC107", "Average Stay"),
            ThresholdConfig(RiskTier.HIGH, 0.5, 0.75, "#FF9800", "Extended Stay Likely"),
            ThresholdConfig(RiskTier.CRITICAL, 0.75, 1.0, "#F44336", "Very Extended Stay"),
        ],
        description="Extended length of stay risk thresholds",
        version="1.0.0",
        updated_at=datetime.now(timezone.utc),
        updated_by="system",
    ),
}


class RiskThresholdsService:
    """Service for managing risk model thresholds."""

    def __init__(self) -> None:
        """Initialize the risk thresholds service."""
        self._thresholds: dict[RiskModel, ModelThresholds] = {}
        self._lock = threading.Lock()
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize default thresholds for all models."""
        for model, defaults in DEFAULT_THRESHOLDS.items():
            self._thresholds[model] = ModelThresholds(
                model=defaults.model,
                thresholds=defaults.thresholds.copy(),
                description=defaults.description,
                version=defaults.version,
                updated_at=defaults.updated_at,
                updated_by=defaults.updated_by,
                metadata=defaults.metadata.copy(),
            )

    def get_thresholds(self, model: RiskModel) -> ModelThresholds | None:
        """Get thresholds for a specific model."""
        return self._thresholds.get(model)

    def list_models(self) -> list[RiskModel]:
        """List all available risk models."""
        return list(self._thresholds.keys())

    def list_all_thresholds(self) -> list[ModelThresholds]:
        """List thresholds for all models."""
        return list(self._thresholds.values())

    def update_thresholds(
        self,
        model: RiskModel,
        thresholds: list[dict[str, Any]],
        updated_by: str,
        description: str | None = None,
    ) -> ModelThresholds:
        """Update thresholds for a model.

        Args:
            model: Risk model to update.
            thresholds: New threshold configurations.
            updated_by: User making the update.
            description: Optional new description.

        Returns:
            Updated ModelThresholds.

        Raises:
            ValueError: If thresholds are invalid.
        """
        # Validate thresholds
        self._validate_thresholds(thresholds)

        with self._lock:
            existing = self._thresholds.get(model)
            if not existing:
                raise ValueError(f"Unknown model: {model}")

            new_thresholds = [
                ThresholdConfig(
                    tier=RiskTier(t["tier"]),
                    min_score=t["min_score"],
                    max_score=t["max_score"],
                    color=t.get("color", "#000000"),
                    label=t.get("label", t["tier"]),
                    alert_enabled=t.get("alert_enabled", True),
                )
                for t in thresholds
            ]

            # Increment version
            old_version = existing.version
            parts = old_version.split(".")
            new_version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

            updated = ModelThresholds(
                model=model,
                thresholds=new_thresholds,
                description=description or existing.description,
                version=new_version,
                updated_at=datetime.now(timezone.utc),
                updated_by=updated_by,
                metadata=existing.metadata,
            )

            self._thresholds[model] = updated
            logger.info(f"Updated thresholds for {model.value}: v{old_version} -> v{new_version}")
            return updated

    def _validate_thresholds(self, thresholds: list[dict[str, Any]]) -> None:
        """Validate threshold configuration.

        Ensures:
        - All tiers are covered
        - No gaps or overlaps in score ranges
        - Scores are between 0 and 1
        """
        if not thresholds:
            raise ValueError("At least one threshold is required")

        # Sort by min_score
        sorted_thresholds = sorted(thresholds, key=lambda t: t["min_score"])

        for i, t in enumerate(sorted_thresholds):
            # Validate individual threshold
            if t["min_score"] < 0 or t["max_score"] > 1:
                raise ValueError("Scores must be between 0 and 1")
            if t["min_score"] >= t["max_score"]:
                raise ValueError("min_score must be less than max_score")

            # Validate tier
            try:
                RiskTier(t["tier"])
            except ValueError:
                raise ValueError(f"Invalid tier: {t['tier']}")

            # Check for gaps/overlaps with next threshold
            if i < len(sorted_thresholds) - 1:
                next_t = sorted_thresholds[i + 1]
                if t["max_score"] != next_t["min_score"]:
                    raise ValueError(
                        f"Gap or overlap between thresholds: {t['max_score']} != {next_t['min_score']}"
                    )

        # Ensure coverage from 0 to 1
        if sorted_thresholds[0]["min_score"] != 0:
            raise ValueError("Thresholds must start at 0")
        if sorted_thresholds[-1]["max_score"] != 1:
            raise ValueError("Thresholds must end at 1")

    def get_defaults(self, model: RiskModel) -> ModelThresholds | None:
        """Get default thresholds for a model."""
        return DEFAULT_THRESHOLDS.get(model)

    def reset_to_defaults(self, model: RiskModel, reset_by: str) -> ModelThresholds | None:
        """Reset a model's thresholds to defaults."""
        defaults = DEFAULT_THRESHOLDS.get(model)
        if not defaults:
            return None

        with self._lock:
            reset_thresholds = ModelThresholds(
                model=defaults.model,
                thresholds=defaults.thresholds.copy(),
                description=defaults.description,
                version="1.0.0",
                updated_at=datetime.now(timezone.utc),
                updated_by=reset_by,
                metadata={"reset": True, "reset_at": datetime.now(timezone.utc).isoformat()},
            )
            self._thresholds[model] = reset_thresholds
            logger.info(f"Reset thresholds for {model.value} to defaults")
            return reset_thresholds

    def classify_score(self, model: RiskModel, score: float) -> dict[str, Any]:
        """Classify a risk score using the model's thresholds.

        Args:
            model: Risk model to use.
            score: Score to classify (0-1).

        Returns:
            Classification result with tier, label, and color.
        """
        thresholds = self._thresholds.get(model)
        if not thresholds:
            raise ValueError(f"Unknown model: {model}")

        for t in thresholds.thresholds:
            if t.min_score <= score <= t.max_score:
                return {
                    "score": score,
                    "tier": t.tier.value,
                    "label": t.label,
                    "color": t.color,
                    "alert_enabled": t.alert_enabled,
                }

        # Default fallback
        return {
            "score": score,
            "tier": RiskTier.CRITICAL.value if score > 0.5 else RiskTier.LOW.value,
            "label": "Unknown",
            "color": "#9E9E9E",
            "alert_enabled": False,
        }


# Singleton instance
_risk_thresholds_service: RiskThresholdsService | None = None
_risk_thresholds_lock = threading.Lock()


def get_risk_thresholds_service() -> RiskThresholdsService:
    """Get the singleton RiskThresholdsService instance."""
    global _risk_thresholds_service

    if _risk_thresholds_service is None:
        with _risk_thresholds_lock:
            if _risk_thresholds_service is None:
                logger.info("Creating singleton RiskThresholdsService instance")
                _risk_thresholds_service = RiskThresholdsService()

    return _risk_thresholds_service


def reset_risk_thresholds_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _risk_thresholds_service
    with _risk_thresholds_lock:
        _risk_thresholds_service = None
