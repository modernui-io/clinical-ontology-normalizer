"""Quality Metrics Service.

Tracks and reports on NLP processing quality including:
- Extraction accuracy metrics
- Processing time statistics
- Confidence score distributions
- Error tracking and analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import threading
import statistics
from collections import defaultdict


# ============================================================================
# Enums and Data Classes
# ============================================================================


class MetricType(Enum):
    """Types of quality metrics."""

    EXTRACTION_ACCURACY = "extraction_accuracy"
    PROCESSING_TIME = "processing_time"
    CONFIDENCE_SCORE = "confidence_score"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    MAPPING_ACCURACY = "mapping_accuracy"


class EntityType(Enum):
    """Types of extracted entities."""

    CONDITION = "condition"
    DRUG = "drug"
    MEASUREMENT = "measurement"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    ALL = "all"


class TimeWindow(Enum):
    """Time windows for metric aggregation."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ALL_TIME = "all_time"


@dataclass
class ProcessingMetrics:
    """Metrics for a single document processing."""

    document_id: str
    patient_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Timing metrics (milliseconds)
    total_time_ms: float = 0.0
    nlp_time_ms: float = 0.0
    mapping_time_ms: float = 0.0
    graph_time_ms: float = 0.0

    # Extraction metrics
    mentions_extracted: int = 0
    facts_created: int = 0
    nodes_created: int = 0
    edges_created: int = 0

    # By entity type
    conditions_extracted: int = 0
    drugs_extracted: int = 0
    measurements_extracted: int = 0
    procedures_extracted: int = 0
    observations_extracted: int = 0

    # Quality metrics
    avg_confidence: float = 0.0
    low_confidence_count: int = 0  # Below 0.5
    mappings_found: int = 0
    mappings_failed: int = 0

    # Document info
    document_length: int = 0
    section_count: int = 0

    # Errors
    errors: list[str] = field(default_factory=list)


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time window."""

    time_window: TimeWindow
    start_time: str
    end_time: str
    document_count: int = 0

    # Timing aggregates
    avg_total_time_ms: float = 0.0
    p50_total_time_ms: float = 0.0
    p95_total_time_ms: float = 0.0
    p99_total_time_ms: float = 0.0
    max_total_time_ms: float = 0.0

    # Extraction aggregates
    total_mentions: int = 0
    total_facts: int = 0
    avg_mentions_per_doc: float = 0.0
    avg_facts_per_doc: float = 0.0

    # By entity type
    by_entity_type: dict[str, int] = field(default_factory=dict)

    # Quality aggregates
    avg_confidence: float = 0.0
    confidence_distribution: dict[str, int] = field(default_factory=dict)

    # Mapping metrics
    mapping_success_rate: float = 0.0
    total_mappings_attempted: int = 0
    total_mappings_succeeded: int = 0

    # Error metrics
    error_count: int = 0
    error_rate: float = 0.0
    error_types: dict[str, int] = field(default_factory=dict)

    # Throughput
    docs_per_minute: float = 0.0
    mentions_per_minute: float = 0.0


@dataclass
class AccuracyMetrics:
    """Accuracy metrics from validation."""

    entity_type: EntityType
    total_samples: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0


@dataclass
class DashboardData:
    """Complete dashboard data package."""

    generated_at: str
    time_window: TimeWindow

    # Summary cards
    total_documents_processed: int = 0
    total_extractions: int = 0
    avg_processing_time_ms: float = 0.0
    overall_confidence: float = 0.0
    error_rate: float = 0.0

    # Time series data (for charts)
    processing_times: list[dict] = field(default_factory=list)
    extraction_counts: list[dict] = field(default_factory=list)
    confidence_trend: list[dict] = field(default_factory=list)

    # Distribution data
    entity_distribution: dict[str, int] = field(default_factory=dict)
    confidence_distribution: dict[str, int] = field(default_factory=dict)

    # Top errors
    top_errors: list[dict] = field(default_factory=list)

    # Recent documents
    recent_documents: list[dict] = field(default_factory=list)

    # Accuracy metrics (if validation data available)
    accuracy_by_entity: dict[str, dict] = field(default_factory=dict)


# ============================================================================
# Quality Metrics Service
# ============================================================================


class QualityMetricsService:
    """Service for tracking and reporting quality metrics."""

    def __init__(self, max_history: int = 10000):
        """
        Initialize the metrics service.

        Args:
            max_history: Maximum number of processing records to keep in memory
        """
        self._max_history = max_history
        self._processing_history: list[ProcessingMetrics] = []
        self._validation_data: dict[EntityType, list[tuple[bool, bool]]] = defaultdict(list)
        self._error_counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record_processing(self, metrics: ProcessingMetrics) -> None:
        """
        Record processing metrics for a document.

        Args:
            metrics: Processing metrics to record
        """
        with self._lock:
            self._processing_history.append(metrics)

            # Trim history if needed
            if len(self._processing_history) > self._max_history:
                self._processing_history = self._processing_history[-self._max_history:]

            # Track errors
            for error in metrics.errors:
                error_type = error.split(":")[0] if ":" in error else error[:50]
                self._error_counts[error_type] += 1

    def record_validation(
        self,
        entity_type: EntityType,
        predicted: bool,
        actual: bool,
    ) -> None:
        """
        Record validation result for accuracy tracking.

        Args:
            entity_type: Type of entity being validated
            predicted: Whether entity was predicted
            actual: Whether entity actually exists (ground truth)
        """
        with self._lock:
            self._validation_data[entity_type].append((predicted, actual))
            self._validation_data[EntityType.ALL].append((predicted, actual))

    def get_aggregated_metrics(
        self,
        time_window: TimeWindow = TimeWindow.DAY,
    ) -> AggregatedMetrics:
        """
        Get aggregated metrics for a time window.

        Args:
            time_window: Time window to aggregate over

        Returns:
            Aggregated metrics
        """
        with self._lock:
            # Filter by time window
            now = datetime.now(timezone.utc)
            if time_window == TimeWindow.HOUR:
                cutoff = now - timedelta(hours=1)
            elif time_window == TimeWindow.DAY:
                cutoff = now - timedelta(days=1)
            elif time_window == TimeWindow.WEEK:
                cutoff = now - timedelta(weeks=1)
            elif time_window == TimeWindow.MONTH:
                cutoff = now - timedelta(days=30)
            else:
                cutoff = datetime.min

            filtered = [
                m for m in self._processing_history
                if datetime.fromisoformat(m.timestamp) >= cutoff
            ]

            if not filtered:
                return AggregatedMetrics(
                    time_window=time_window,
                    start_time=cutoff.isoformat(),
                    end_time=now.isoformat(),
                )

            # Calculate timing metrics
            times = [m.total_time_ms for m in filtered]
            times_sorted = sorted(times)

            # Calculate by entity type
            by_entity = {
                "condition": sum(m.conditions_extracted for m in filtered),
                "drug": sum(m.drugs_extracted for m in filtered),
                "measurement": sum(m.measurements_extracted for m in filtered),
                "procedure": sum(m.procedures_extracted for m in filtered),
                "observation": sum(m.observations_extracted for m in filtered),
            }

            # Calculate confidence distribution
            conf_buckets = {"0.0-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
            for m in filtered:
                if m.avg_confidence < 0.5:
                    conf_buckets["0.0-0.5"] += 1
                elif m.avg_confidence < 0.7:
                    conf_buckets["0.5-0.7"] += 1
                elif m.avg_confidence < 0.9:
                    conf_buckets["0.7-0.9"] += 1
                else:
                    conf_buckets["0.9-1.0"] += 1

            # Calculate mapping metrics
            total_mappings = sum(m.mappings_found + m.mappings_failed for m in filtered)
            successful_mappings = sum(m.mappings_found for m in filtered)

            # Calculate error metrics
            total_errors = sum(len(m.errors) for m in filtered)

            # Calculate throughput
            time_span_minutes = max(
                (now - datetime.fromisoformat(filtered[0].timestamp)).total_seconds() / 60,
                1
            )

            return AggregatedMetrics(
                time_window=time_window,
                start_time=cutoff.isoformat(),
                end_time=now.isoformat(),
                document_count=len(filtered),
                avg_total_time_ms=statistics.mean(times),
                p50_total_time_ms=times_sorted[len(times_sorted) // 2],
                p95_total_time_ms=times_sorted[int(len(times_sorted) * 0.95)] if len(times_sorted) > 20 else max(times),
                p99_total_time_ms=times_sorted[int(len(times_sorted) * 0.99)] if len(times_sorted) > 100 else max(times),
                max_total_time_ms=max(times),
                total_mentions=sum(m.mentions_extracted for m in filtered),
                total_facts=sum(m.facts_created for m in filtered),
                avg_mentions_per_doc=statistics.mean([m.mentions_extracted for m in filtered]),
                avg_facts_per_doc=statistics.mean([m.facts_created for m in filtered]),
                by_entity_type=by_entity,
                avg_confidence=statistics.mean([m.avg_confidence for m in filtered if m.avg_confidence > 0]),
                confidence_distribution=conf_buckets,
                mapping_success_rate=successful_mappings / total_mappings if total_mappings > 0 else 0,
                total_mappings_attempted=total_mappings,
                total_mappings_succeeded=successful_mappings,
                error_count=total_errors,
                error_rate=total_errors / len(filtered) if filtered else 0,
                error_types=dict(self._error_counts),
                docs_per_minute=len(filtered) / time_span_minutes,
                mentions_per_minute=sum(m.mentions_extracted for m in filtered) / time_span_minutes,
            )

    def get_accuracy_metrics(
        self,
        entity_type: EntityType = EntityType.ALL,
    ) -> AccuracyMetrics:
        """
        Calculate accuracy metrics from validation data.

        Args:
            entity_type: Type of entity to calculate metrics for

        Returns:
            Accuracy metrics
        """
        with self._lock:
            data = self._validation_data.get(entity_type, [])

            if not data:
                return AccuracyMetrics(entity_type=entity_type)

            tp = sum(1 for pred, actual in data if pred and actual)
            fp = sum(1 for pred, actual in data if pred and not actual)
            fn = sum(1 for pred, actual in data if not pred and actual)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            return AccuracyMetrics(
                entity_type=entity_type,
                total_samples=len(data),
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=round(precision, 4),
                recall=round(recall, 4),
                f1_score=round(f1, 4),
            )

    def get_dashboard_data(
        self,
        time_window: TimeWindow = TimeWindow.DAY,
    ) -> DashboardData:
        """
        Get complete dashboard data package.

        Args:
            time_window: Time window for metrics

        Returns:
            Dashboard data
        """
        aggregated = self.get_aggregated_metrics(time_window)

        with self._lock:
            # Build time series data (hourly buckets for day view)
            processing_times = []
            extraction_counts = []
            confidence_trend = []

            if time_window == TimeWindow.DAY:
                # Group by hour
                hourly_data: dict[int, list[ProcessingMetrics]] = defaultdict(list)
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(days=1)

                for m in self._processing_history:
                    ts = datetime.fromisoformat(m.timestamp)
                    if ts >= cutoff:
                        hour = ts.hour
                        hourly_data[hour].append(m)

                for hour in range(24):
                    data = hourly_data.get(hour, [])
                    if data:
                        processing_times.append({
                            "hour": hour,
                            "avg_time_ms": statistics.mean([m.total_time_ms for m in data]),
                            "count": len(data),
                        })
                        extraction_counts.append({
                            "hour": hour,
                            "mentions": sum(m.mentions_extracted for m in data),
                            "facts": sum(m.facts_created for m in data),
                        })
                        confidence_trend.append({
                            "hour": hour,
                            "avg_confidence": statistics.mean([m.avg_confidence for m in data if m.avg_confidence > 0]) if any(m.avg_confidence > 0 for m in data) else 0,
                        })

            # Get top errors
            top_errors = [
                {"error": err, "count": count}
                for err, count in sorted(self._error_counts.items(), key=lambda x: -x[1])[:10]
            ]

            # Get recent documents
            recent = sorted(
                self._processing_history[-20:],
                key=lambda m: m.timestamp,
                reverse=True
            )
            recent_docs = [
                {
                    "document_id": m.document_id,
                    "timestamp": m.timestamp,
                    "processing_time_ms": m.total_time_ms,
                    "mentions": m.mentions_extracted,
                    "confidence": m.avg_confidence,
                    "errors": len(m.errors),
                }
                for m in recent[:10]
            ]

            # Get accuracy by entity type
            accuracy_by_entity = {}
            for entity_type in EntityType:
                if entity_type != EntityType.ALL:
                    metrics = self.get_accuracy_metrics(entity_type)
                    if metrics.total_samples > 0:
                        accuracy_by_entity[entity_type.value] = {
                            "precision": metrics.precision,
                            "recall": metrics.recall,
                            "f1_score": metrics.f1_score,
                            "samples": metrics.total_samples,
                        }

            return DashboardData(
                generated_at=datetime.now(timezone.utc).isoformat(),
                time_window=time_window,
                total_documents_processed=aggregated.document_count,
                total_extractions=aggregated.total_mentions,
                avg_processing_time_ms=aggregated.avg_total_time_ms,
                overall_confidence=aggregated.avg_confidence,
                error_rate=aggregated.error_rate,
                processing_times=processing_times,
                extraction_counts=extraction_counts,
                confidence_trend=confidence_trend,
                entity_distribution=aggregated.by_entity_type,
                confidence_distribution=aggregated.confidence_distribution,
                top_errors=top_errors,
                recent_documents=recent_docs,
                accuracy_by_entity=accuracy_by_entity,
            )

    def get_processing_trend(
        self,
        metric: str = "processing_time",
        points: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get trend data for a specific metric.

        Args:
            metric: Metric to trend (processing_time, mentions, confidence)
            points: Number of data points to return

        Returns:
            List of data points with timestamp and value
        """
        with self._lock:
            recent = self._processing_history[-points:]

            trend = []
            for m in recent:
                point = {"timestamp": m.timestamp}
                if metric == "processing_time":
                    point["value"] = m.total_time_ms
                elif metric == "mentions":
                    point["value"] = m.mentions_extracted
                elif metric == "confidence":
                    point["value"] = m.avg_confidence
                elif metric == "facts":
                    point["value"] = m.facts_created
                trend.append(point)

            return trend

    def clear_history(self) -> None:
        """Clear all recorded metrics (for testing)."""
        with self._lock:
            self._processing_history.clear()
            self._validation_data.clear()
            self._error_counts.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            return {
                "records_in_memory": len(self._processing_history),
                "max_history": self._max_history,
                "validation_samples": sum(len(v) for v in self._validation_data.values()),
                "unique_error_types": len(self._error_counts),
                "total_errors_recorded": sum(self._error_counts.values()),
            }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: QualityMetricsService | None = None
_service_lock = threading.Lock()


def get_quality_metrics_service() -> QualityMetricsService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = QualityMetricsService()

    return _service_instance


def reset_quality_metrics_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
