"""P2-012: Queue partitioning by workload class.

Provides named queue partitions with configurable depth limits and priority,
so different workload types (ingest, mapping, KG build, export) can be
isolated and independently monitored.

Configure via QUEUE_PARTITIONS env var (JSON):
    QUEUE_PARTITIONS='{"ingest": {"max_depth": 500, "priority": 1}}'
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class QueueClass(str, Enum):
    """Workload classes for queue partitioning."""

    INGEST = "ingest"
    MAPPING = "mapping"
    KG_BUILD = "kg_build"
    EXPORT = "export"
    GENERAL = "general"


# Default configuration per queue class
_DEFAULT_CONFIG: dict[str, dict[str, int]] = {
    QueueClass.INGEST.value: {"max_depth": 500, "priority": 1},
    QueueClass.MAPPING.value: {"max_depth": 300, "priority": 2},
    QueueClass.KG_BUILD.value: {"max_depth": 200, "priority": 3},
    QueueClass.EXPORT.value: {"max_depth": 100, "priority": 4},
    QueueClass.GENERAL.value: {"max_depth": 1000, "priority": 5},
}


@dataclass(frozen=True)
class QueuePartitionConfig:
    """Configuration for a single queue partition."""

    queue_class: QueueClass
    max_depth: int
    priority: int  # Lower number = higher priority

    @property
    def queue_name(self) -> str:
        """Return the prefixed queue name."""
        return get_queue_name(self.queue_class)


@dataclass
class PartitionStats:
    """Runtime stats for a single queue partition."""

    queue_class: QueueClass
    queue_name: str
    depth: int
    max_depth: int
    priority: int
    worker_count: int
    utilization_pct: float


def get_queue_name(workload_class: QueueClass | str) -> str:
    """Return the prefixed queue name for a workload class.

    Args:
        workload_class: A QueueClass enum value or its string representation.

    Returns:
        Queue name in the format "queue:{class}".
    """
    if isinstance(workload_class, QueueClass):
        return f"queue:{workload_class.value}"
    return f"queue:{workload_class}"


def _load_config_from_env() -> dict[str, dict[str, int]]:
    """Load partition config from QUEUE_PARTITIONS env var, merged over defaults."""
    config = dict(_DEFAULT_CONFIG)
    raw = os.environ.get("QUEUE_PARTITIONS")
    if raw:
        try:
            overrides = json.loads(raw)
            if not isinstance(overrides, dict):
                logger.warning("QUEUE_PARTITIONS must be a JSON object, ignoring")
                return config
            for key, vals in overrides.items():
                if key in config and isinstance(vals, dict):
                    config[key] = {**config[key], **vals}
                elif isinstance(vals, dict):
                    config[key] = vals
                else:
                    logger.warning("Invalid config for queue class '%s', ignoring", key)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse QUEUE_PARTITIONS: %s", e)
    return config


def get_all_partition_configs() -> dict[QueueClass, QueuePartitionConfig]:
    """Load and return all partition configs, merging env overrides.

    Returns:
        Dict mapping QueueClass to its QueuePartitionConfig.
    """
    raw_config = _load_config_from_env()
    result: dict[QueueClass, QueuePartitionConfig] = {}
    for qc in QueueClass:
        cfg = raw_config.get(qc.value, _DEFAULT_CONFIG.get(qc.value, {"max_depth": 1000, "priority": 5}))
        result[qc] = QueuePartitionConfig(
            queue_class=qc,
            max_depth=cfg.get("max_depth", 1000),
            priority=cfg.get("priority", 5),
        )
    return result


def get_partition_config(workload_class: QueueClass) -> QueuePartitionConfig:
    """Get the partition config for a specific workload class."""
    return get_all_partition_configs()[workload_class]


def _get_queue_length(queue_name: str) -> int:
    """Get current queue length from Redis/RQ. Returns 0 if unavailable."""
    try:
        from app.core.queue import get_queue
        q = get_queue(queue_name)
        return len(q)
    except Exception as e:
        logger.debug("Could not read queue length for %s: %s", queue_name, e)
        return 0


def _get_worker_count(queue_name: str) -> int:
    """Get worker count for a queue. Returns 0 if unavailable."""
    try:
        from app.core.queue import get_queue
        from rq import Worker
        q = get_queue(queue_name)
        workers = Worker.all(connection=q.connection)
        return sum(1 for w in workers if queue_name in [qn.name for qn in w.queues])
    except Exception:
        return 0


def get_partition_stats() -> dict[QueueClass, PartitionStats]:
    """Return depth and worker count per queue partition.

    Returns:
        Dict mapping QueueClass to PartitionStats with current depth,
        max_depth, priority, worker_count, and utilization percentage.
    """
    configs = get_all_partition_configs()
    stats: dict[QueueClass, PartitionStats] = {}

    for qc, config in configs.items():
        qname = config.queue_name
        depth = _get_queue_length(qname)
        worker_count = _get_worker_count(qname)
        utilization = (depth / config.max_depth * 100) if config.max_depth > 0 else 0.0

        stats[qc] = PartitionStats(
            queue_class=qc,
            queue_name=qname,
            depth=depth,
            max_depth=config.max_depth,
            priority=config.priority,
            worker_count=worker_count,
            utilization_pct=round(min(utilization, 100.0), 2),
        )

    return stats


def should_accept(workload_class: QueueClass) -> bool:
    """Check if a queue partition can accept new work.

    Returns True if current depth is below max_depth for the partition.
    """
    config = get_partition_config(workload_class)
    depth = _get_queue_length(config.queue_name)
    return depth < config.max_depth
