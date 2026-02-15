"""Tests for P2-012: Queue partitioning by workload class."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from app.core.queue_partitioning import (
    PartitionStats,
    QueueClass,
    QueuePartitionConfig,
    get_all_partition_configs,
    get_partition_config,
    get_partition_stats,
    get_queue_name,
    should_accept,
)


class TestQueueClass:
    """Tests for the QueueClass enum."""

    def test_all_classes_defined(self) -> None:
        assert QueueClass.INGEST.value == "ingest"
        assert QueueClass.MAPPING.value == "mapping"
        assert QueueClass.KG_BUILD.value == "kg_build"
        assert QueueClass.EXPORT.value == "export"
        assert QueueClass.GENERAL.value == "general"

    def test_queue_class_is_string(self) -> None:
        for qc in QueueClass:
            assert isinstance(qc.value, str)


class TestGetQueueName:
    """Tests for get_queue_name()."""

    def test_enum_input(self) -> None:
        assert get_queue_name(QueueClass.INGEST) == "queue:ingest"
        assert get_queue_name(QueueClass.MAPPING) == "queue:mapping"
        assert get_queue_name(QueueClass.KG_BUILD) == "queue:kg_build"
        assert get_queue_name(QueueClass.EXPORT) == "queue:export"
        assert get_queue_name(QueueClass.GENERAL) == "queue:general"

    def test_string_input(self) -> None:
        assert get_queue_name("ingest") == "queue:ingest"
        assert get_queue_name("custom") == "queue:custom"

    def test_prefix_format(self) -> None:
        for qc in QueueClass:
            name = get_queue_name(qc)
            assert name.startswith("queue:")
            assert qc.value in name


class TestQueuePartitionConfig:
    """Tests for QueuePartitionConfig dataclass."""

    def test_config_creation(self) -> None:
        config = QueuePartitionConfig(
            queue_class=QueueClass.INGEST,
            max_depth=500,
            priority=1,
        )
        assert config.queue_class == QueueClass.INGEST
        assert config.max_depth == 500
        assert config.priority == 1

    def test_queue_name_property(self) -> None:
        config = QueuePartitionConfig(
            queue_class=QueueClass.EXPORT,
            max_depth=100,
            priority=4,
        )
        assert config.queue_name == "queue:export"

    def test_frozen(self) -> None:
        config = QueuePartitionConfig(
            queue_class=QueueClass.INGEST,
            max_depth=500,
            priority=1,
        )
        with pytest.raises(AttributeError):
            config.max_depth = 999  # type: ignore[misc]


class TestGetAllPartitionConfigs:
    """Tests for get_all_partition_configs()."""

    def test_returns_all_classes(self) -> None:
        configs = get_all_partition_configs()
        for qc in QueueClass:
            assert qc in configs

    def test_default_values(self) -> None:
        configs = get_all_partition_configs()
        assert configs[QueueClass.INGEST].max_depth == 500
        assert configs[QueueClass.INGEST].priority == 1
        assert configs[QueueClass.MAPPING].max_depth == 300
        assert configs[QueueClass.EXPORT].max_depth == 100
        assert configs[QueueClass.GENERAL].max_depth == 1000

    def test_env_override(self, monkeypatch) -> None:
        overrides = {"ingest": {"max_depth": 999, "priority": 10}}
        monkeypatch.setenv("QUEUE_PARTITIONS", json.dumps(overrides))

        configs = get_all_partition_configs()
        assert configs[QueueClass.INGEST].max_depth == 999
        assert configs[QueueClass.INGEST].priority == 10
        # Other classes unchanged
        assert configs[QueueClass.MAPPING].max_depth == 300

    def test_partial_env_override(self, monkeypatch) -> None:
        overrides = {"export": {"max_depth": 50}}
        monkeypatch.setenv("QUEUE_PARTITIONS", json.dumps(overrides))

        configs = get_all_partition_configs()
        assert configs[QueueClass.EXPORT].max_depth == 50
        # Priority should remain default
        assert configs[QueueClass.EXPORT].priority == 4

    def test_invalid_json_env(self, monkeypatch) -> None:
        monkeypatch.setenv("QUEUE_PARTITIONS", "not-json")
        # Should fall back to defaults without error
        configs = get_all_partition_configs()
        assert configs[QueueClass.INGEST].max_depth == 500

    def test_non_dict_json_env(self, monkeypatch) -> None:
        monkeypatch.setenv("QUEUE_PARTITIONS", '"just a string"')
        configs = get_all_partition_configs()
        assert configs[QueueClass.INGEST].max_depth == 500


class TestGetPartitionConfig:
    """Tests for get_partition_config()."""

    def test_returns_correct_class(self) -> None:
        config = get_partition_config(QueueClass.KG_BUILD)
        assert config.queue_class == QueueClass.KG_BUILD
        assert config.max_depth == 200
        assert config.priority == 3


class TestGetPartitionStats:
    """Tests for get_partition_stats()."""

    @patch("app.core.queue_partitioning._get_queue_length", return_value=42)
    @patch("app.core.queue_partitioning._get_worker_count", return_value=3)
    def test_returns_stats_for_all_classes(self, mock_workers, mock_depth) -> None:
        stats = get_partition_stats()
        assert len(stats) == len(QueueClass)
        for qc in QueueClass:
            assert qc in stats
            s = stats[qc]
            assert isinstance(s, PartitionStats)
            assert s.queue_class == qc
            assert s.depth == 42
            assert s.worker_count == 3

    @patch("app.core.queue_partitioning._get_queue_length", return_value=250)
    @patch("app.core.queue_partitioning._get_worker_count", return_value=1)
    def test_utilization_calculation(self, mock_workers, mock_depth) -> None:
        stats = get_partition_stats()
        # Ingest: 250/500 = 50%
        assert stats[QueueClass.INGEST].utilization_pct == 50.0
        # Export: 250/100 = 250% -> capped at 100%
        assert stats[QueueClass.EXPORT].utilization_pct == 100.0

    @patch("app.core.queue_partitioning._get_queue_length", return_value=0)
    @patch("app.core.queue_partitioning._get_worker_count", return_value=0)
    def test_empty_queues(self, mock_workers, mock_depth) -> None:
        stats = get_partition_stats()
        for qc in QueueClass:
            assert stats[qc].depth == 0
            assert stats[qc].utilization_pct == 0.0

    @patch("app.core.queue_partitioning._get_queue_length", return_value=0)
    @patch("app.core.queue_partitioning._get_worker_count", return_value=0)
    def test_queue_name_format(self, mock_workers, mock_depth) -> None:
        stats = get_partition_stats()
        for qc in QueueClass:
            assert stats[qc].queue_name == f"queue:{qc.value}"


class TestShouldAccept:
    """Tests for should_accept()."""

    @patch("app.core.queue_partitioning._get_queue_length", return_value=0)
    def test_empty_queue_accepts(self, mock_depth) -> None:
        assert should_accept(QueueClass.INGEST) is True

    @patch("app.core.queue_partitioning._get_queue_length", return_value=499)
    def test_below_max_accepts(self, mock_depth) -> None:
        assert should_accept(QueueClass.INGEST) is True

    @patch("app.core.queue_partitioning._get_queue_length", return_value=500)
    def test_at_max_rejects(self, mock_depth) -> None:
        assert should_accept(QueueClass.INGEST) is False

    @patch("app.core.queue_partitioning._get_queue_length", return_value=9999)
    def test_over_max_rejects(self, mock_depth) -> None:
        assert should_accept(QueueClass.INGEST) is False
