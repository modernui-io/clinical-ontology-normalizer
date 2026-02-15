"""Tests for P1-022/023/025: Worker liveness, queue backpressure, restart policy.

Covers:
- WorkerHealthCheck scenarios (alive, stuck, disconnected)
- Queue depth SLO classification
- Throttling decisions at various depths
- Backpressure rejection at max depth
- QueueSLO validation
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.core.worker_health import (
    WorkerHealthCheck,
    WorkerHealthResult,
    check_worker_health,
    get_worker_health,
    WORKER_STUCK_THRESHOLD_SECONDS,
)
from app.core.queue_backpressure import (
    QueueBackpressureError,
    QueueDepthResult,
    QueueSLO,
    QueueStatus,
    ThrottleDecision,
    check_queue_depth,
    enqueue_with_backpressure,
    should_throttle,
)


# ---------------------------------------------------------------------------
# P1-022: Worker health check tests
# ---------------------------------------------------------------------------


class TestWorkerHealthResult:
    """Test WorkerHealthResult dataclass."""

    def test_healthy_when_alive_not_stuck_connected(self) -> None:
        result = WorkerHealthResult(
            alive=True, stuck=False, queue_connected=True, last_heartbeat=1.0
        )
        assert result.healthy is True

    def test_unhealthy_when_not_alive(self) -> None:
        result = WorkerHealthResult(
            alive=False, stuck=False, queue_connected=True, last_heartbeat=1.0
        )
        assert result.healthy is False

    def test_unhealthy_when_stuck(self) -> None:
        result = WorkerHealthResult(
            alive=True, stuck=True, queue_connected=True, last_heartbeat=1.0
        )
        assert result.healthy is False

    def test_unhealthy_when_disconnected(self) -> None:
        result = WorkerHealthResult(
            alive=True, stuck=False, queue_connected=False, last_heartbeat=1.0
        )
        assert result.healthy is False

    def test_unhealthy_all_bad(self) -> None:
        result = WorkerHealthResult(
            alive=False, stuck=True, queue_connected=False, last_heartbeat=None
        )
        assert result.healthy is False


class TestWorkerHealthCheck:
    """Test WorkerHealthCheck class."""

    def test_process_alive(self) -> None:
        """Current process should always report alive."""
        hc = WorkerHealthCheck()
        assert hc.check_process_alive() is True

    def test_not_stuck_initially(self) -> None:
        """Freshly created worker should not be stuck."""
        hc = WorkerHealthCheck()
        assert hc.is_stuck() is False

    def test_stuck_after_threshold(self) -> None:
        """Worker is stuck if started_at is older than threshold."""
        hc = WorkerHealthCheck()
        # Backdate startup to exceed threshold
        hc._started_at = time.monotonic() - (WORKER_STUCK_THRESHOLD_SECONDS + 10)
        assert hc.is_stuck() is True

    def test_not_stuck_after_heartbeat(self) -> None:
        """Worker is not stuck if a recent heartbeat was recorded."""
        hc = WorkerHealthCheck()
        hc._started_at = time.monotonic() - (WORKER_STUCK_THRESHOLD_SECONDS + 10)
        hc.record_task_completed()
        assert hc.is_stuck() is False

    def test_stuck_after_heartbeat_goes_stale(self) -> None:
        """Worker is stuck if heartbeat itself is stale."""
        hc = WorkerHealthCheck()
        hc._last_task_completed = time.monotonic() - (WORKER_STUCK_THRESHOLD_SECONDS + 10)
        assert hc.is_stuck() is True

    def test_record_heartbeat_alias(self) -> None:
        """record_heartbeat should update last task completed."""
        hc = WorkerHealthCheck()
        assert hc._last_task_completed is None
        hc.record_heartbeat()
        assert hc._last_task_completed is not None

    @patch("app.core.redis.ping_redis", return_value=True)
    def test_queue_connected(self, mock_ping: MagicMock) -> None:
        hc = WorkerHealthCheck()
        assert hc.check_queue_connected() is True
        mock_ping.assert_called_once()

    @patch("app.core.redis.ping_redis", return_value=False)
    def test_queue_disconnected(self, mock_ping: MagicMock) -> None:
        hc = WorkerHealthCheck()
        assert hc.check_queue_connected() is False

    @patch("app.core.redis.ping_redis", side_effect=Exception("conn refused"))
    def test_queue_connection_error(self, mock_ping: MagicMock) -> None:
        hc = WorkerHealthCheck()
        assert hc.check_queue_connected() is False

    @patch("app.core.redis.ping_redis", return_value=True)
    def test_check_returns_healthy(self, mock_ping: MagicMock) -> None:
        hc = WorkerHealthCheck()
        result = hc.check()
        assert result.alive is True
        assert result.stuck is False
        assert result.queue_connected is True
        assert result.healthy is True
        assert result.pid is not None

    @patch("app.core.redis.ping_redis", return_value=False)
    def test_check_returns_unhealthy_on_disconnect(self, mock_ping: MagicMock) -> None:
        hc = WorkerHealthCheck()
        result = hc.check()
        assert result.healthy is False
        assert result.queue_connected is False

    @patch("app.core.redis.ping_redis", return_value=True)
    def test_check_returns_unhealthy_when_stuck(self, mock_ping: MagicMock) -> None:
        hc = WorkerHealthCheck()
        hc._started_at = time.monotonic() - (WORKER_STUCK_THRESHOLD_SECONDS + 10)
        result = hc.check()
        assert result.healthy is False
        assert result.stuck is True

    def test_get_memory_mb(self) -> None:
        hc = WorkerHealthCheck()
        mem = hc.get_memory_mb()
        # Should return some positive value on any platform with resource module
        assert mem is None or mem > 0


class TestCheckWorkerHealthFunction:
    """Test the module-level convenience function."""

    @patch("app.core.redis.ping_redis", return_value=True)
    def test_check_worker_health(self, mock_ping: MagicMock) -> None:
        result = check_worker_health()
        assert isinstance(result, WorkerHealthResult)
        assert result.alive is True


# ---------------------------------------------------------------------------
# P1-023: Queue backpressure tests
# ---------------------------------------------------------------------------


class TestQueueSLO:
    """Test QueueSLO classification."""

    def test_normal(self) -> None:
        slo = QueueSLO(warning_depth=100, critical_depth=500, max_depth=1000)
        assert slo.classify(0) == QueueStatus.NORMAL
        assert slo.classify(50) == QueueStatus.NORMAL
        assert slo.classify(99) == QueueStatus.NORMAL

    def test_warning(self) -> None:
        slo = QueueSLO(warning_depth=100, critical_depth=500, max_depth=1000)
        assert slo.classify(100) == QueueStatus.WARNING
        assert slo.classify(250) == QueueStatus.WARNING
        assert slo.classify(499) == QueueStatus.WARNING

    def test_critical(self) -> None:
        slo = QueueSLO(warning_depth=100, critical_depth=500, max_depth=1000)
        assert slo.classify(500) == QueueStatus.CRITICAL
        assert slo.classify(750) == QueueStatus.CRITICAL
        assert slo.classify(999) == QueueStatus.CRITICAL

    def test_rejected(self) -> None:
        slo = QueueSLO(warning_depth=100, critical_depth=500, max_depth=1000)
        assert slo.classify(1000) == QueueStatus.REJECTED
        assert slo.classify(5000) == QueueStatus.REJECTED

    def test_invalid_thresholds_raises(self) -> None:
        with pytest.raises(ValueError, match="Thresholds must be"):
            QueueSLO(warning_depth=500, critical_depth=100, max_depth=1000)

    def test_invalid_zero_warning_raises(self) -> None:
        with pytest.raises(ValueError):
            QueueSLO(warning_depth=0, critical_depth=100, max_depth=200)

    def test_equal_thresholds_raises(self) -> None:
        with pytest.raises(ValueError):
            QueueSLO(warning_depth=100, critical_depth=100, max_depth=200)


class TestQueueDepthResult:
    """Test QueueDepthResult properties."""

    def test_ok_when_normal(self) -> None:
        r = QueueDepthResult(queue_name="test", depth=10, status=QueueStatus.NORMAL, max_depth=1000)
        assert r.ok is True

    def test_ok_when_warning(self) -> None:
        r = QueueDepthResult(queue_name="test", depth=150, status=QueueStatus.WARNING, max_depth=1000)
        assert r.ok is True

    def test_not_ok_when_critical(self) -> None:
        r = QueueDepthResult(queue_name="test", depth=600, status=QueueStatus.CRITICAL, max_depth=1000)
        assert r.ok is False

    def test_not_ok_when_rejected(self) -> None:
        r = QueueDepthResult(queue_name="test", depth=1200, status=QueueStatus.REJECTED, max_depth=1000)
        assert r.ok is False


class TestCheckQueueDepth:
    """Test check_queue_depth function."""

    @patch("app.core.queue_backpressure._get_queue_length", return_value=50)
    def test_normal_depth(self, mock_len: MagicMock) -> None:
        result = check_queue_depth("default")
        assert result.status == QueueStatus.NORMAL
        assert result.depth == 50

    @patch("app.core.queue_backpressure._get_queue_length", return_value=200)
    def test_warning_depth(self, mock_len: MagicMock) -> None:
        result = check_queue_depth("default")
        assert result.status == QueueStatus.WARNING
        assert result.depth == 200

    @patch("app.core.queue_backpressure._get_queue_length", return_value=600)
    def test_critical_depth(self, mock_len: MagicMock) -> None:
        result = check_queue_depth("default")
        assert result.status == QueueStatus.CRITICAL

    @patch("app.core.queue_backpressure._get_queue_length", return_value=1500)
    def test_rejected_depth(self, mock_len: MagicMock) -> None:
        result = check_queue_depth("default")
        assert result.status == QueueStatus.REJECTED

    @patch("app.core.queue_backpressure._get_queue_length", return_value=30)
    def test_custom_slo(self, mock_len: MagicMock) -> None:
        slo = QueueSLO(warning_depth=10, critical_depth=20, max_depth=50)
        result = check_queue_depth("default", slo=slo)
        assert result.status == QueueStatus.CRITICAL
        assert result.max_depth == 50


class TestShouldThrottle:
    """Test should_throttle function."""

    @patch("app.core.queue_backpressure._get_queue_length", return_value=10)
    def test_no_throttle_normal(self, mock_len: MagicMock) -> None:
        decision = should_throttle("default")
        assert decision.throttle is False
        assert decision.reject is False
        assert decision.status == QueueStatus.NORMAL

    @patch("app.core.queue_backpressure._get_queue_length", return_value=200)
    def test_throttle_warning(self, mock_len: MagicMock) -> None:
        decision = should_throttle("default")
        assert decision.throttle is True
        assert decision.reject is False
        assert decision.status == QueueStatus.WARNING
        assert "warning threshold" in decision.reason

    @patch("app.core.queue_backpressure._get_queue_length", return_value=700)
    def test_throttle_critical(self, mock_len: MagicMock) -> None:
        decision = should_throttle("default")
        assert decision.throttle is True
        assert decision.reject is False
        assert decision.status == QueueStatus.CRITICAL
        assert "critical threshold" in decision.reason

    @patch("app.core.queue_backpressure._get_queue_length", return_value=1200)
    def test_throttle_and_reject(self, mock_len: MagicMock) -> None:
        decision = should_throttle("default")
        assert decision.throttle is True
        assert decision.reject is True
        assert decision.status == QueueStatus.REJECTED
        assert "rejecting" in decision.reason

    @patch("app.core.queue_backpressure._get_queue_length", return_value=5)
    def test_custom_slo_throttle(self, mock_len: MagicMock) -> None:
        slo = QueueSLO(warning_depth=3, critical_depth=8, max_depth=15)
        decision = should_throttle("default", slo=slo)
        assert decision.throttle is True
        assert decision.reject is False
        assert decision.status == QueueStatus.WARNING


class TestEnqueueWithBackpressure:
    """Test enqueue_with_backpressure gating function."""

    @patch("app.core.queue_backpressure._get_queue_length", return_value=10)
    @patch("app.core.queue.enqueue_job")
    def test_enqueue_allowed(self, mock_enqueue: MagicMock, mock_len: MagicMock) -> None:
        mock_job = MagicMock()
        mock_enqueue.return_value = mock_job

        result = enqueue_with_backpressure(lambda: None, queue_name="default")
        assert result is mock_job
        mock_enqueue.assert_called_once()

    @patch("app.core.queue_backpressure._get_queue_length", return_value=1500)
    def test_enqueue_rejected(self, mock_len: MagicMock) -> None:
        with pytest.raises(QueueBackpressureError) as exc_info:
            enqueue_with_backpressure(lambda: None, queue_name="default")
        assert exc_info.value.queue_name == "default"
        assert exc_info.value.depth == 1500
        assert "rejecting" in exc_info.value.reason


class TestQueueBackpressureError:
    """Test QueueBackpressureError exception."""

    def test_attributes(self) -> None:
        err = QueueBackpressureError("queue full", "my_queue", 1200)
        assert err.reason == "queue full"
        assert err.queue_name == "my_queue"
        assert err.depth == 1200
        assert str(err) == "queue full"
