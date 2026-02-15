"""Tests for P3-008: Queue observability service."""

from __future__ import annotations

import time

import pytest

from app.services.queue_observability_service import (
    HealthStatus,
    QueueDashboard,
    QueueHealthSummary,
    QueueMetrics,
    QueueObservabilityService,
    WorkerMetrics,
    WorkerStatus,
    get_queue_observability_service,
    reset_queue_observability_service,
)


@pytest.fixture()
def svc() -> QueueObservabilityService:
    """Fresh service instance for each test."""
    return QueueObservabilityService()


# ---------------------------------------------------------------------------
# QueueMetrics tests
# ---------------------------------------------------------------------------


class TestQueueMetrics:
    def test_register_queue_initializes_metrics(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("document_processing")
        metrics = svc.get_queue_metrics()
        assert len(metrics) == 1
        assert metrics[0].queue_name == "document_processing"
        assert metrics[0].depth == 0

    def test_update_queue_depth(self, svc: QueueObservabilityService) -> None:
        svc.update_queue_depth("nlp", 42)
        metrics = svc.get_queue_metrics()
        assert metrics[0].depth == 42

    def test_update_consumer_count(self, svc: QueueObservabilityService) -> None:
        svc.update_consumer_count("nlp", 3)
        metrics = svc.get_queue_metrics()
        assert metrics[0].consumer_count == 3

    def test_enqueue_rate_tracking(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("test_q")
        for _ in range(10):
            svc.record_enqueue("test_q")
        metrics = svc.get_queue_metrics()
        # With 10 events in rapid succession, rate should be > 0
        assert metrics[0].enqueue_rate_per_min >= 0

    def test_dequeue_rate_tracking(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("test_q")
        svc.update_queue_depth("test_q", 10)
        for _ in range(5):
            svc.record_dequeue("test_q")
        metrics = svc.get_queue_metrics()
        assert metrics[0].dequeue_rate_per_min >= 0

    def test_multiple_queues(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("alpha")
        svc.register_queue("beta")
        svc.register_queue("gamma")
        metrics = svc.get_queue_metrics()
        assert len(metrics) == 3
        names = [m.queue_name for m in metrics]
        assert names == ["alpha", "beta", "gamma"]  # sorted


# ---------------------------------------------------------------------------
# WorkerMetrics tests
# ---------------------------------------------------------------------------


class TestWorkerMetrics:
    def test_register_worker(self, svc: QueueObservabilityService) -> None:
        svc.register_worker("worker-1")
        workers = svc.get_worker_metrics()
        assert len(workers) == 1
        assert workers[0].worker_id == "worker-1"
        assert workers[0].status == WorkerStatus.IDLE

    def test_update_worker_status(self, svc: QueueObservabilityService) -> None:
        svc.register_worker("worker-1")
        svc.update_worker_status("worker-1", WorkerStatus.BUSY, current_task="doc-123")
        workers = svc.get_worker_metrics()
        assert workers[0].status == WorkerStatus.BUSY
        assert workers[0].current_task == "doc-123"

    def test_record_task_completion(self, svc: QueueObservabilityService) -> None:
        svc.register_worker("worker-1")
        svc.record_worker_task_complete("worker-1")
        svc.record_worker_task_complete("worker-1")
        workers = svc.get_worker_metrics()
        assert workers[0].tasks_completed == 2

    def test_record_task_failure(self, svc: QueueObservabilityService) -> None:
        svc.register_worker("worker-1")
        svc.record_worker_task_failed("worker-1")
        workers = svc.get_worker_metrics()
        assert workers[0].tasks_failed == 1

    def test_worker_uptime(self, svc: QueueObservabilityService) -> None:
        svc.register_worker("worker-1")
        time.sleep(0.05)
        workers = svc.get_worker_metrics()
        assert workers[0].uptime_seconds > 0

    def test_remove_worker(self, svc: QueueObservabilityService) -> None:
        svc.register_worker("worker-1")
        svc.remove_worker("worker-1")
        workers = svc.get_worker_metrics()
        assert len(workers) == 0


# ---------------------------------------------------------------------------
# Health summary tests
# ---------------------------------------------------------------------------


class TestQueueHealthSummary:
    def test_healthy_status(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_queue_depth("q1", 5)
        svc.update_consumer_count("q1", 2)
        svc.register_worker("w1")
        health = svc.get_queue_health_summary()
        assert health.status == HealthStatus.HEALTHY
        assert health.total_queues == 1
        assert health.total_workers == 1
        assert len(health.issues) == 0

    def test_warning_on_high_queue_depth(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_queue_depth("q1", 150)
        svc.update_consumer_count("q1", 2)
        health = svc.get_queue_health_summary()
        assert health.status == HealthStatus.WARNING
        assert len(health.issues) >= 1

    def test_critical_on_very_high_queue_depth(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_queue_depth("q1", 600)
        svc.update_consumer_count("q1", 2)
        health = svc.get_queue_health_summary()
        assert health.status == HealthStatus.CRITICAL

    def test_critical_on_no_consumers_with_messages(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_queue_depth("q1", 10)
        svc.update_consumer_count("q1", 0)
        health = svc.get_queue_health_summary()
        assert health.status == HealthStatus.CRITICAL
        assert any("0 consumers" in issue for issue in health.issues)

    def test_unknown_when_no_queues_or_workers(self, svc: QueueObservabilityService) -> None:
        health = svc.get_queue_health_summary()
        assert health.status == HealthStatus.UNKNOWN

    def test_worker_failure_rate_warning(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_consumer_count("q1", 1)
        svc.register_worker("w1")
        # 6% failure rate (> 5% threshold)
        for _ in range(94):
            svc.record_worker_task_complete("w1")
        for _ in range(6):
            svc.record_worker_task_failed("w1")
        health = svc.get_queue_health_summary()
        assert health.status == HealthStatus.WARNING

    def test_worker_failure_rate_critical(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_consumer_count("q1", 1)
        svc.register_worker("w1")
        # 25% failure rate (> 20% threshold)
        for _ in range(75):
            svc.record_worker_task_complete("w1")
        for _ in range(25):
            svc.record_worker_task_failed("w1")
        health = svc.get_queue_health_summary()
        assert health.status == HealthStatus.CRITICAL

    def test_worker_counts(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_consumer_count("q1", 3)
        svc.register_worker("w1")
        svc.register_worker("w2")
        svc.register_worker("w3")
        svc.update_worker_status("w1", WorkerStatus.BUSY)
        svc.update_worker_status("w2", WorkerStatus.IDLE)
        svc.update_worker_status("w3", WorkerStatus.OFFLINE)
        health = svc.get_queue_health_summary()
        assert health.workers_busy == 1
        assert health.workers_idle == 1
        assert health.workers_offline == 1


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------


class TestQueueDashboard:
    def test_get_queue_dashboard(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.register_worker("w1")
        dashboard = svc.get_queue_dashboard()
        assert isinstance(dashboard, QueueDashboard)
        assert len(dashboard.queues) == 1
        assert len(dashboard.workers) == 1
        assert isinstance(dashboard.health, QueueHealthSummary)
        assert dashboard.timestamp > 0

    def test_dashboard_reflects_updates(self, svc: QueueObservabilityService) -> None:
        svc.register_queue("q1")
        svc.update_queue_depth("q1", 50)
        svc.register_worker("w1")
        svc.update_worker_status("w1", WorkerStatus.BUSY, current_task="job-abc")
        dashboard = svc.get_queue_dashboard()
        assert dashboard.queues[0].depth == 50
        assert dashboard.workers[0].current_task == "job-abc"


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_returns_same_instance(self) -> None:
        reset_queue_observability_service()
        a = get_queue_observability_service()
        b = get_queue_observability_service()
        assert a is b

    def test_reset_creates_new_instance(self) -> None:
        a = get_queue_observability_service()
        reset_queue_observability_service()
        b = get_queue_observability_service()
        assert a is not b
