"""Prediction Audit Service for tracking ML model predictions.

Provides functionality to log and query ML model predictions
for auditing, explainability, and drift detection.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class PredictionOutcome(str, Enum):
    """Outcome of a prediction after ground truth is known."""

    PENDING = "pending"
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class FeedbackType(str, Enum):
    """Type of user feedback on a prediction."""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    FLAG = "flag"
    CORRECTION = "correction"
    COMMENT = "comment"


@dataclass
class PredictionInput:
    """Input features used for a prediction."""

    feature_name: str
    feature_value: Any
    feature_importance: float = 0.0


@dataclass
class PredictionAudit:
    """Audit record for a single prediction."""

    id: str
    model_name: str
    model_version: str
    patient_id: str | None
    prediction_type: str  # mortality, readmission, etc.
    prediction_value: float | str
    prediction_confidence: float | None
    prediction_tier: str | None  # low, medium, high, critical
    inputs: list[PredictionInput]
    explanation: str | None
    created_at: datetime
    user_id: str | None
    session_id: str | None
    latency_ms: float
    outcome: PredictionOutcome = PredictionOutcome.PENDING
    outcome_updated_at: datetime | None = None
    feedback: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DriftMetrics:
    """Model drift metrics over a time period."""

    model_name: str
    period_start: datetime
    period_end: datetime
    total_predictions: int
    mean_confidence: float
    confidence_std: float
    distribution: dict[str, int]  # tier -> count
    accuracy: float | None  # If ground truth available
    false_positive_rate: float | None
    false_negative_rate: float | None


class PredictionAuditService:
    """Service for managing prediction audit records."""

    def __init__(self) -> None:
        """Initialize the prediction audit service."""
        self._audits: dict[str, PredictionAudit] = {}
        self._lock = threading.Lock()

    def log_prediction(
        self,
        model_name: str,
        model_version: str,
        prediction_type: str,
        prediction_value: float | str,
        inputs: list[dict[str, Any]],
        patient_id: str | None = None,
        prediction_confidence: float | None = None,
        prediction_tier: str | None = None,
        explanation: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        latency_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> PredictionAudit:
        """Log a new prediction for audit.

        Args:
            model_name: Name of the ML model.
            model_version: Version of the model.
            prediction_type: Type of prediction (mortality, readmission, etc.).
            prediction_value: The predicted value.
            inputs: List of input features used.
            patient_id: Optional patient identifier.
            prediction_confidence: Model confidence score.
            prediction_tier: Risk tier classification.
            explanation: Human-readable explanation.
            user_id: User who requested the prediction.
            session_id: Session identifier.
            latency_ms: Prediction latency in milliseconds.
            metadata: Additional metadata.

        Returns:
            Created PredictionAudit record.
        """
        audit_id = str(uuid4())
        now = datetime.now(UTC)

        parsed_inputs = [
            PredictionInput(
                feature_name=inp["feature_name"],
                feature_value=inp["feature_value"],
                feature_importance=inp.get("feature_importance", 0.0),
            )
            for inp in inputs
        ]

        audit = PredictionAudit(
            id=audit_id,
            model_name=model_name,
            model_version=model_version,
            patient_id=patient_id,
            prediction_type=prediction_type,
            prediction_value=prediction_value,
            prediction_confidence=prediction_confidence,
            prediction_tier=prediction_tier,
            inputs=parsed_inputs,
            explanation=explanation,
            created_at=now,
            user_id=user_id,
            session_id=session_id,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )

        with self._lock:
            self._audits[audit_id] = audit

        logger.info(f"Logged prediction audit: {audit_id} for {model_name}")
        return audit

    def get_audit(self, audit_id: str) -> PredictionAudit | None:
        """Get a specific audit record."""
        return self._audits.get(audit_id)

    def list_audits(
        self,
        model_name: str | None = None,
        patient_id: str | None = None,
        prediction_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[PredictionAudit]:
        """List audit records with filtering.

        Args:
            model_name: Filter by model name.
            patient_id: Filter by patient ID.
            prediction_type: Filter by prediction type.
            start_date: Filter by start date.
            end_date: Filter by end date.
            limit: Maximum results.

        Returns:
            List of matching audit records.
        """
        audits = list(self._audits.values())

        if model_name:
            audits = [a for a in audits if a.model_name == model_name]

        if patient_id:
            audits = [a for a in audits if a.patient_id == patient_id]

        if prediction_type:
            audits = [a for a in audits if a.prediction_type == prediction_type]

        if start_date:
            audits = [a for a in audits if a.created_at >= start_date]

        if end_date:
            audits = [a for a in audits if a.created_at <= end_date]

        # Sort by created_at descending
        audits.sort(key=lambda a: a.created_at, reverse=True)

        return audits[:limit]

    def update_outcome(
        self,
        audit_id: str,
        outcome: PredictionOutcome,
    ) -> PredictionAudit | None:
        """Update the outcome for a prediction after ground truth is known.

        Args:
            audit_id: Audit record ID.
            outcome: The actual outcome.

        Returns:
            Updated audit record or None if not found.
        """
        with self._lock:
            audit = self._audits.get(audit_id)
            if not audit:
                return None

            audit.outcome = outcome
            audit.outcome_updated_at = datetime.now(UTC)

        logger.info(f"Updated outcome for {audit_id}: {outcome.value}")
        return audit

    def add_feedback(
        self,
        audit_id: str,
        feedback_type: FeedbackType,
        value: Any = None,
        comment: str | None = None,
        user_id: str | None = None,
    ) -> PredictionAudit | None:
        """Add user feedback to a prediction.

        Args:
            audit_id: Audit record ID.
            feedback_type: Type of feedback.
            value: Feedback value (e.g., corrected prediction).
            comment: Optional comment.
            user_id: User providing feedback.

        Returns:
            Updated audit record or None if not found.
        """
        with self._lock:
            audit = self._audits.get(audit_id)
            if not audit:
                return None

            audit.feedback.append({
                "type": feedback_type.value,
                "value": value,
                "comment": comment,
                "user_id": user_id,
                "created_at": datetime.now(UTC).isoformat(),
            })

        logger.info(f"Added feedback to {audit_id}: {feedback_type.value}")
        return audit

    def get_drift_metrics(
        self,
        model_name: str,
        period_days: int = 7,
    ) -> DriftMetrics:
        """Calculate drift metrics for a model over a time period.

        Args:
            model_name: Model to analyze.
            period_days: Number of days to analyze.

        Returns:
            DriftMetrics for the period.
        """
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=period_days)

        audits = self.list_audits(
            model_name=model_name,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        if not audits:
            return DriftMetrics(
                model_name=model_name,
                period_start=start_date,
                period_end=end_date,
                total_predictions=0,
                mean_confidence=0.0,
                confidence_std=0.0,
                distribution={},
                accuracy=None,
                false_positive_rate=None,
                false_negative_rate=None,
            )

        # Calculate confidence statistics
        confidences = [a.prediction_confidence for a in audits if a.prediction_confidence is not None]
        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        confidence_std = 0.0
        if len(confidences) > 1:
            variance = sum((c - mean_confidence) ** 2 for c in confidences) / len(confidences)
            confidence_std = variance ** 0.5

        # Calculate tier distribution
        distribution: dict[str, int] = {}
        for audit in audits:
            tier = audit.prediction_tier or "unknown"
            distribution[tier] = distribution.get(tier, 0) + 1

        # Calculate accuracy if outcomes are known
        outcomes_known = [a for a in audits if a.outcome != PredictionOutcome.PENDING]
        accuracy = None
        if outcomes_known:
            correct = sum(1 for a in outcomes_known if a.outcome == PredictionOutcome.CORRECT)
            accuracy = correct / len(outcomes_known)

        return DriftMetrics(
            model_name=model_name,
            period_start=start_date,
            period_end=end_date,
            total_predictions=len(audits),
            mean_confidence=mean_confidence,
            confidence_std=confidence_std,
            distribution=distribution,
            accuracy=accuracy,
            false_positive_rate=None,  # Would need more complex logic
            false_negative_rate=None,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get overall prediction audit statistics."""
        audits = list(self._audits.values())

        by_model: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}

        for audit in audits:
            by_model[audit.model_name] = by_model.get(audit.model_name, 0) + 1
            by_type[audit.prediction_type] = by_type.get(audit.prediction_type, 0) + 1
            by_outcome[audit.outcome.value] = by_outcome.get(audit.outcome.value, 0) + 1

        return {
            "total_predictions": len(audits),
            "by_model": by_model,
            "by_type": by_type,
            "by_outcome": by_outcome,
            "with_feedback": sum(1 for a in audits if a.feedback),
        }


# Singleton instance
_prediction_audit_service: PredictionAuditService | None = None
_prediction_audit_lock = threading.Lock()


def get_prediction_audit_service() -> PredictionAuditService:
    """Get the singleton PredictionAuditService instance."""
    global _prediction_audit_service

    if _prediction_audit_service is None:
        with _prediction_audit_lock:
            if _prediction_audit_service is None:
                logger.info("Creating singleton PredictionAuditService instance")
                _prediction_audit_service = PredictionAuditService()

    return _prediction_audit_service


def reset_prediction_audit_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _prediction_audit_service
    with _prediction_audit_lock:
        _prediction_audit_service = None
