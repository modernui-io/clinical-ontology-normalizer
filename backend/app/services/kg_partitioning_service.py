"""Knowledge Graph Partitioning Service.

This module provides graph partitioning strategies for scaling
the clinical knowledge graph horizontally. Supports multiple
partitioning schemes optimized for healthcare data patterns.

Key capabilities:
- Patient-centric partitioning (by patient ID)
- Semantic type partitioning (by UMLS type)
- Temporal partitioning (by time ranges)
- Geographic partitioning (by facility/region)
- Hybrid partitioning strategies
"""
# MODULE: graph_support
# MATURITY: pilot

from __future__ import annotations

import hashlib
import logging
import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PartitionStrategy(str, Enum):
    """Partitioning strategies for the knowledge graph."""

    HASH = "hash"  # Hash-based distribution
    PATIENT_CENTRIC = "patient_centric"  # Group by patient
    SEMANTIC_TYPE = "semantic_type"  # Group by UMLS semantic type
    TEMPORAL = "temporal"  # Partition by time ranges
    GEOGRAPHIC = "geographic"  # Partition by location
    HYBRID = "hybrid"  # Combination of strategies


class PartitionState(str, Enum):
    """State of a partition."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    REBALANCING = "rebalancing"
    MIGRATING = "migrating"


@dataclass
class PartitionConfig:
    """Configuration for a partition."""

    partition_id: str
    strategy: PartitionStrategy
    shard_key: str
    node_count: int = 0
    edge_count: int = 0
    size_bytes: int = 0
    state: PartitionState = PartitionState.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ShardAssignment:
    """Assignment of an entity to a shard."""

    entity_id: str
    entity_type: str
    partition_id: str
    shard_key: str
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PartitionStats:
    """Statistics for a partition."""

    partition_id: str
    node_count: int
    edge_count: int
    size_bytes: int
    query_load: float
    write_load: float
    avg_latency_ms: float
    hot_spot_ratio: float


@dataclass
class RebalanceOperation:
    """An operation to rebalance partitions."""

    operation_id: str
    source_partition: str
    target_partition: str
    entity_count: int
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class PartitionRoutingTable:
    """Routing table for partition lookups."""

    version: int
    partitions: dict[str, PartitionConfig]
    routing_rules: list[dict[str, Any]]
    last_updated: datetime


class KGPartitioningService:
    """Service for partitioning the knowledge graph for scale.

    This service provides:
    - Multiple partitioning strategies
    - Automatic shard key generation
    - Load balancing and rebalancing
    - Cross-partition query routing
    - Partition health monitoring
    """

    def __init__(
        self,
        num_partitions: int = 16,
        strategy: PartitionStrategy = PartitionStrategy.PATIENT_CENTRIC,
    ) -> None:
        """Initialize the partitioning service."""
        self._num_partitions = num_partitions
        self._default_strategy = strategy

        # Partition state
        self._partitions: dict[str, PartitionConfig] = {}
        self._assignments: dict[str, ShardAssignment] = {}
        self._routing_table: PartitionRoutingTable | None = None

        # Statistics
        self._partition_stats: dict[str, PartitionStats] = {}
        self._rebalance_history: list[RebalanceOperation] = []

        # Initialize default partitions
        self._initialize_partitions()

    def _initialize_partitions(self) -> None:
        """Initialize default partition configuration."""
        for i in range(self._num_partitions):
            partition_id = f"partition_{i:03d}"
            self._partitions[partition_id] = PartitionConfig(
                partition_id=partition_id,
                strategy=self._default_strategy,
                shard_key=f"shard_{i:03d}",
                state=PartitionState.ACTIVE,
            )

        # Create routing table
        self._routing_table = PartitionRoutingTable(
            version=1,
            partitions=self._partitions.copy(),
            routing_rules=self._create_routing_rules(),
            last_updated=datetime.now(timezone.utc),
        )

    def _create_routing_rules(self) -> list[dict[str, Any]]:
        """Create routing rules based on strategy."""
        rules = []

        if self._default_strategy == PartitionStrategy.PATIENT_CENTRIC:
            rules.append({
                "type": "entity_type",
                "entity_types": ["Patient", "Condition", "Medication", "Observation"],
                "key_field": "patient_id",
                "algorithm": "consistent_hash",
            })
        elif self._default_strategy == PartitionStrategy.SEMANTIC_TYPE:
            # Group related semantic types together
            rules.append({
                "type": "semantic_group",
                "groups": {
                    "disorders": ["T047", "T048", "T191"],  # Diseases, Syndromes
                    "drugs": ["T121", "T122", "T200"],  # Pharmacologic
                    "procedures": ["T061", "T060", "T059"],  # Procedures
                    "anatomy": ["T023", "T024", "T025"],  # Anatomical
                },
                "algorithm": "range_partition",
            })
        elif self._default_strategy == PartitionStrategy.TEMPORAL:
            rules.append({
                "type": "temporal",
                "time_field": "valid_from",
                "bucket_size_days": 365,  # Annual partitions
                "algorithm": "range_partition",
            })

        return rules

    def get_partition_for_entity(
        self,
        entity_id: str,
        entity_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Get the partition ID for an entity.

        Args:
            entity_id: The entity identifier
            entity_type: Type of entity (Patient, Condition, etc.)
            metadata: Additional metadata for routing

        Returns:
            Partition ID for the entity
        """
        metadata = metadata or {}

        # Check if already assigned
        if entity_id in self._assignments:
            return self._assignments[entity_id].partition_id

        # Calculate partition based on strategy
        partition_id = self._calculate_partition(entity_id, entity_type, metadata)

        # Record assignment
        self._assignments[entity_id] = ShardAssignment(
            entity_id=entity_id,
            entity_type=entity_type,
            partition_id=partition_id,
            shard_key=self._generate_shard_key(entity_id, entity_type, metadata),
        )

        # Update partition stats
        if partition_id in self._partitions:
            self._partitions[partition_id].node_count += 1

        return partition_id

    def _calculate_partition(
        self,
        entity_id: str,
        entity_type: str,
        metadata: dict[str, Any],
    ) -> str:
        """Calculate partition for an entity based on strategy."""
        if self._default_strategy == PartitionStrategy.PATIENT_CENTRIC:
            return self._patient_centric_partition(entity_id, entity_type, metadata)
        elif self._default_strategy == PartitionStrategy.SEMANTIC_TYPE:
            return self._semantic_type_partition(entity_id, entity_type, metadata)
        elif self._default_strategy == PartitionStrategy.TEMPORAL:
            return self._temporal_partition(entity_id, entity_type, metadata)
        elif self._default_strategy == PartitionStrategy.HASH:
            return self._hash_partition(entity_id)
        else:
            return self._hash_partition(entity_id)

    def _patient_centric_partition(
        self,
        entity_id: str,
        entity_type: str,
        metadata: dict[str, Any],
    ) -> str:
        """Partition by patient ID to keep patient data together."""
        # Extract patient ID from metadata or entity ID
        patient_id = metadata.get("patient_id")

        if not patient_id:
            # Try to extract from entity ID
            if entity_type == "Patient":
                patient_id = entity_id
            elif "_" in entity_id:
                parts = entity_id.split("_")
                for part in parts:
                    if part.startswith("P"):
                        patient_id = part
                        break

        if patient_id:
            return self._hash_partition(patient_id)

        # Fallback to hash partition
        return self._hash_partition(entity_id)

    def _semantic_type_partition(
        self,
        entity_id: str,
        entity_type: str,
        metadata: dict[str, Any],
    ) -> str:
        """Partition by semantic type to optimize type-based queries."""
        semantic_type = metadata.get("semantic_type", "")

        # Map semantic types to partition ranges
        type_mappings = {
            "T047": 0,  # Disease or Syndrome
            "T121": 3,  # Pharmacologic Substance
            "T061": 6,  # Therapeutic Procedure
            "T034": 9,  # Laboratory Finding
            "T023": 12,  # Body Part
        }

        # Get base partition for type
        base_partition = type_mappings.get(semantic_type, 15)

        # Add some distribution within the type group
        hash_val = int(hashlib.md5(entity_id.encode()).hexdigest(), 16)
        offset = hash_val % 3  # 3 partitions per type group

        partition_idx = (base_partition + offset) % self._num_partitions
        return f"partition_{partition_idx:03d}"

    def _temporal_partition(
        self,
        entity_id: str,
        entity_type: str,
        metadata: dict[str, Any],
    ) -> str:
        """Partition by time to optimize temporal queries."""
        valid_from = metadata.get("valid_from")

        if valid_from:
            if isinstance(valid_from, str):
                valid_from = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))

            # Partition by year
            year = valid_from.year
            base_year = 2020  # Reference year
            partition_idx = (year - base_year) % self._num_partitions
            return f"partition_{partition_idx:03d}"

        # Fallback to hash
        return self._hash_partition(entity_id)

    def _hash_partition(self, key: str) -> str:
        """Hash-based partition assignment."""
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        partition_idx = hash_val % self._num_partitions
        return f"partition_{partition_idx:03d}"

    def _generate_shard_key(
        self,
        entity_id: str,
        entity_type: str,
        metadata: dict[str, Any],
    ) -> str:
        """Generate a shard key for an entity."""
        if self._default_strategy == PartitionStrategy.PATIENT_CENTRIC:
            patient_id = metadata.get("patient_id", entity_id)
            return f"patient:{patient_id}"
        elif self._default_strategy == PartitionStrategy.SEMANTIC_TYPE:
            semantic_type = metadata.get("semantic_type", "unknown")
            return f"type:{semantic_type}:{entity_id}"
        elif self._default_strategy == PartitionStrategy.TEMPORAL:
            valid_from = metadata.get("valid_from", datetime.now(timezone.utc))
            if isinstance(valid_from, datetime):
                return f"time:{valid_from.year}:{entity_id}"
            return f"time:unknown:{entity_id}"
        else:
            return f"hash:{entity_id}"

    def get_partitions_for_query(
        self,
        query_type: str,
        filters: dict[str, Any],
    ) -> list[str]:
        """Get partitions to query based on filters.

        Args:
            query_type: Type of query (patient_lookup, type_search, etc.)
            filters: Query filters

        Returns:
            List of partition IDs to query
        """
        if self._default_strategy == PartitionStrategy.PATIENT_CENTRIC:
            if "patient_id" in filters:
                # Single partition lookup
                partition = self._hash_partition(filters["patient_id"])
                return [partition]

        if self._default_strategy == PartitionStrategy.SEMANTIC_TYPE:
            if "semantic_type" in filters:
                # Query specific type partitions
                partition = self._semantic_type_partition(
                    "", "", {"semantic_type": filters["semantic_type"]}
                )
                return [partition]

        if self._default_strategy == PartitionStrategy.TEMPORAL:
            if "valid_from" in filters and "valid_to" in filters:
                # Query time range partitions
                partitions = self._get_temporal_range_partitions(
                    filters["valid_from"], filters["valid_to"]
                )
                return partitions

        # Default: query all partitions
        return list(self._partitions.keys())

    def _get_temporal_range_partitions(
        self,
        start: datetime,
        end: datetime,
    ) -> list[str]:
        """Get partitions covering a temporal range."""
        partitions = []
        base_year = 2020

        start_year = start.year if isinstance(start, datetime) else base_year
        end_year = end.year if isinstance(end, datetime) else datetime.now(timezone.utc).year

        for year in range(start_year, end_year + 1):
            partition_idx = (year - base_year) % self._num_partitions
            partition_id = f"partition_{partition_idx:03d}"
            if partition_id not in partitions:
                partitions.append(partition_id)

        return partitions

    def get_partition_stats(self, partition_id: str) -> PartitionStats | None:
        """Get statistics for a partition."""
        if partition_id not in self._partitions:
            return None

        config = self._partitions[partition_id]

        # Calculate stats (simulated for now)
        return PartitionStats(
            partition_id=partition_id,
            node_count=config.node_count,
            edge_count=config.edge_count,
            size_bytes=config.size_bytes,
            query_load=0.5,  # Simulated
            write_load=0.3,  # Simulated
            avg_latency_ms=15.0,  # Simulated
            hot_spot_ratio=0.1,  # Simulated
        )

    def get_all_partition_stats(self) -> list[PartitionStats]:
        """Get statistics for all partitions."""
        return [
            self.get_partition_stats(pid)
            for pid in self._partitions
            if self.get_partition_stats(pid) is not None
        ]

    def check_rebalance_needed(self) -> bool:
        """Check if partitions need rebalancing."""
        stats = self.get_all_partition_stats()

        if len(stats) < 2:
            return False

        node_counts = [s.node_count for s in stats if s]

        if not node_counts or max(node_counts) == 0:
            return False

        # Check for skew
        avg_count = statistics.mean(node_counts)
        max_count = max(node_counts)
        min_count = min(node_counts)

        # Rebalance if max is > 2x average or imbalance > 50%
        if avg_count > 0:
            skew = (max_count - min_count) / avg_count
            return skew > 0.5

        return False

    async def rebalance_partitions(self) -> list[RebalanceOperation]:
        """Rebalance partitions to distribute load evenly."""
        operations = []

        stats = self.get_all_partition_stats()
        if not stats:
            return operations

        node_counts = [(s.partition_id, s.node_count) for s in stats if s]
        if not node_counts:
            return operations

        avg_count = sum(c for _, c in node_counts) / len(node_counts)

        # Sort by node count
        node_counts.sort(key=lambda x: x[1], reverse=True)

        # Find overloaded and underloaded partitions
        overloaded = [(pid, count) for pid, count in node_counts if count > avg_count * 1.2]
        underloaded = [(pid, count) for pid, count in node_counts if count < avg_count * 0.8]

        # Create rebalance operations
        for source_id, source_count in overloaded:
            for target_id, target_count in underloaded:
                excess = int(source_count - avg_count)
                deficit = int(avg_count - target_count)
                move_count = min(excess, deficit)

                if move_count > 0:
                    operation = RebalanceOperation(
                        operation_id=f"rebal_{source_id}_{target_id}",
                        source_partition=source_id,
                        target_partition=target_id,
                        entity_count=move_count,
                        status="pending",
                        started_at=datetime.now(timezone.utc),
                    )
                    operations.append(operation)
                    self._rebalance_history.append(operation)

        return operations

    def get_routing_table(self) -> PartitionRoutingTable | None:
        """Get the current routing table."""
        return self._routing_table

    def get_partition_count(self) -> int:
        """Get the number of partitions."""
        return len(self._partitions)

    def get_partition_config(self, partition_id: str) -> PartitionConfig | None:
        """Get configuration for a partition."""
        return self._partitions.get(partition_id)

    def list_partitions(self) -> list[PartitionConfig]:
        """List all partition configurations."""
        return list(self._partitions.values())

    def get_entity_assignment(self, entity_id: str) -> ShardAssignment | None:
        """Get the shard assignment for an entity."""
        return self._assignments.get(entity_id)

    def get_assignment_count(self) -> int:
        """Get the total number of assignments."""
        return len(self._assignments)

    def get_strategy(self) -> PartitionStrategy:
        """Get the current partitioning strategy."""
        return self._default_strategy

    def update_partition_stats(
        self,
        partition_id: str,
        node_delta: int = 0,
        edge_delta: int = 0,
        size_delta: int = 0,
    ) -> None:
        """Update statistics for a partition."""
        if partition_id in self._partitions:
            config = self._partitions[partition_id]
            config.node_count += node_delta
            config.edge_count += edge_delta
            config.size_bytes += size_delta

    def get_rebalance_history(self) -> list[RebalanceOperation]:
        """Get history of rebalance operations."""
        return self._rebalance_history

    def export_partition_map(self) -> dict[str, Any]:
        """Export the partition map for serialization."""
        return {
            "strategy": self._default_strategy.value,
            "num_partitions": self._num_partitions,
            "partitions": {
                pid: {
                    "partition_id": cfg.partition_id,
                    "strategy": cfg.strategy.value,
                    "shard_key": cfg.shard_key,
                    "node_count": cfg.node_count,
                    "edge_count": cfg.edge_count,
                    "state": cfg.state.value,
                }
                for pid, cfg in self._partitions.items()
            },
            "routing_table_version": self._routing_table.version if self._routing_table else 0,
        }


# Singleton instances for different strategies
_services: dict[PartitionStrategy, KGPartitioningService] = {}
_services_lock = threading.Lock()


def get_kg_partitioning_service(
    strategy: PartitionStrategy = PartitionStrategy.PATIENT_CENTRIC,
    num_partitions: int = 16,
) -> KGPartitioningService:
    """Get the singleton KG Partitioning service instance."""
    global _services
    # VP-ThreadSafety: Double-checked locking for thread safety
    if strategy not in _services:
        with _services_lock:
            if strategy not in _services:
                _services[strategy] = KGPartitioningService(
                    num_partitions=num_partitions,
                    strategy=strategy,
                )
    return _services[strategy]
