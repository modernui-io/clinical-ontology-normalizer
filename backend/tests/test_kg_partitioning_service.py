"""Tests for KG Partitioning Service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.kg_partitioning_service import (
    KGPartitioningService,
    PartitionConfig,
    PartitionState,
    PartitionStats,
    PartitionStrategy,
    RebalanceOperation,
    ShardAssignment,
    get_kg_partitioning_service,
)


class TestPartitionConfig:
    """Test PartitionConfig dataclass."""

    def test_create_partition_config(self) -> None:
        """Test creating a partition configuration."""
        config = PartitionConfig(
            partition_id="partition_001",
            strategy=PartitionStrategy.PATIENT_CENTRIC,
            shard_key="shard_001",
            node_count=1000,
            edge_count=5000,
        )
        assert config.partition_id == "partition_001"
        assert config.strategy == PartitionStrategy.PATIENT_CENTRIC
        assert config.node_count == 1000

    def test_default_state(self) -> None:
        """Test default partition state is active."""
        config = PartitionConfig(
            partition_id="partition_002",
            strategy=PartitionStrategy.HASH,
            shard_key="shard_002",
        )
        assert config.state == PartitionState.ACTIVE


class TestShardAssignment:
    """Test ShardAssignment dataclass."""

    def test_create_shard_assignment(self) -> None:
        """Test creating a shard assignment."""
        assignment = ShardAssignment(
            entity_id="patient_P12345",
            entity_type="Patient",
            partition_id="partition_003",
            shard_key="patient:P12345",
        )
        assert assignment.entity_id == "patient_P12345"
        assert assignment.partition_id == "partition_003"
        assert assignment.assigned_at is not None


class TestPartitionStats:
    """Test PartitionStats dataclass."""

    def test_create_partition_stats(self) -> None:
        """Test creating partition statistics."""
        stats = PartitionStats(
            partition_id="partition_001",
            node_count=5000,
            edge_count=25000,
            size_bytes=1024 * 1024 * 100,  # 100MB
            query_load=0.6,
            write_load=0.3,
            avg_latency_ms=12.5,
            hot_spot_ratio=0.15,
        )
        assert stats.node_count == 5000
        assert stats.avg_latency_ms == 12.5


class TestRebalanceOperation:
    """Test RebalanceOperation dataclass."""

    def test_create_rebalance_operation(self) -> None:
        """Test creating a rebalance operation."""
        operation = RebalanceOperation(
            operation_id="rebal_001",
            source_partition="partition_001",
            target_partition="partition_005",
            entity_count=500,
            status="pending",
            started_at=datetime.now(timezone.utc),
        )
        assert operation.source_partition == "partition_001"
        assert operation.entity_count == 500
        assert operation.completed_at is None


class TestKGPartitioningService:
    """Test KGPartitioningService class."""

    def test_service_initialization(self) -> None:
        """Test service initializes correctly."""
        service = KGPartitioningService(num_partitions=8)
        assert service._num_partitions == 8
        assert len(service._partitions) == 8

    def test_default_strategy_patient_centric(self) -> None:
        """Test default strategy is patient-centric."""
        service = KGPartitioningService()
        assert service.get_strategy() == PartitionStrategy.PATIENT_CENTRIC

    def test_initialize_with_hash_strategy(self) -> None:
        """Test initializing with hash strategy."""
        service = KGPartitioningService(strategy=PartitionStrategy.HASH)
        assert service.get_strategy() == PartitionStrategy.HASH

    def test_get_partition_count(self) -> None:
        """Test getting partition count."""
        service = KGPartitioningService(num_partitions=16)
        assert service.get_partition_count() == 16


class TestPatientCentricPartitioning:
    """Test patient-centric partitioning strategy."""

    def test_patient_entity_partitioning(self) -> None:
        """Test patient entities are partitioned correctly."""
        service = KGPartitioningService(
            strategy=PartitionStrategy.PATIENT_CENTRIC
        )

        partition = service.get_partition_for_entity(
            entity_id="patient_P12345",
            entity_type="Patient",
            metadata={"patient_id": "P12345"},
        )

        assert partition.startswith("partition_")

    def test_same_patient_same_partition(self) -> None:
        """Test entities for same patient go to same partition."""
        service = KGPartitioningService(
            strategy=PartitionStrategy.PATIENT_CENTRIC
        )

        patient_id = "P12345"

        partition1 = service.get_partition_for_entity(
            entity_id="patient_P12345",
            entity_type="Patient",
            metadata={"patient_id": patient_id},
        )

        partition2 = service.get_partition_for_entity(
            entity_id="condition_E11.9_P12345",
            entity_type="Condition",
            metadata={"patient_id": patient_id},
        )

        partition3 = service.get_partition_for_entity(
            entity_id="medication_metformin_P12345",
            entity_type="Medication",
            metadata={"patient_id": patient_id},
        )

        assert partition1 == partition2 == partition3

    def test_different_patients_distributed(self) -> None:
        """Test different patients are distributed across partitions."""
        service = KGPartitioningService(
            num_partitions=16,
            strategy=PartitionStrategy.PATIENT_CENTRIC,
        )

        partitions = set()
        for i in range(100):
            partition = service.get_partition_for_entity(
                entity_id=f"patient_P{i:05d}",
                entity_type="Patient",
                metadata={"patient_id": f"P{i:05d}"},
            )
            partitions.add(partition)

        # Should use multiple partitions
        assert len(partitions) > 1


class TestSemanticTypePartitioning:
    """Test semantic type partitioning strategy."""

    def test_disease_entities_grouped(self) -> None:
        """Test disease entities are grouped together."""
        service = KGPartitioningService(
            strategy=PartitionStrategy.SEMANTIC_TYPE
        )

        partition1 = service.get_partition_for_entity(
            entity_id="disease_diabetes",
            entity_type="Disease",
            metadata={"semantic_type": "T047"},
        )

        partition2 = service.get_partition_for_entity(
            entity_id="disease_hypertension",
            entity_type="Disease",
            metadata={"semantic_type": "T047"},
        )

        # Both should be in the same partition group (within 3 partitions)
        idx1 = int(partition1.split("_")[1])
        idx2 = int(partition2.split("_")[1])
        assert abs(idx1 - idx2) <= 3

    def test_drugs_and_diseases_separated(self) -> None:
        """Test drugs and diseases are in different partition groups."""
        service = KGPartitioningService(
            num_partitions=16,
            strategy=PartitionStrategy.SEMANTIC_TYPE,
        )

        disease_partition = service.get_partition_for_entity(
            entity_id="disease_diabetes",
            entity_type="Disease",
            metadata={"semantic_type": "T047"},
        )

        drug_partition = service.get_partition_for_entity(
            entity_id="drug_metformin",
            entity_type="Drug",
            metadata={"semantic_type": "T121"},
        )

        # Should be in different partition groups
        assert disease_partition != drug_partition


class TestTemporalPartitioning:
    """Test temporal partitioning strategy."""

    def test_same_year_same_partition(self) -> None:
        """Test entities from same year go to same partition."""
        service = KGPartitioningService(
            strategy=PartitionStrategy.TEMPORAL
        )

        partition1 = service.get_partition_for_entity(
            entity_id="event_001",
            entity_type="Event",
            metadata={"valid_from": datetime(2024, 1, 15, tzinfo=timezone.utc)},
        )

        partition2 = service.get_partition_for_entity(
            entity_id="event_002",
            entity_type="Event",
            metadata={"valid_from": datetime(2024, 6, 20, tzinfo=timezone.utc)},
        )

        assert partition1 == partition2

    def test_different_years_different_partitions(self) -> None:
        """Test entities from different years go to different partitions."""
        service = KGPartitioningService(
            num_partitions=16,
            strategy=PartitionStrategy.TEMPORAL,
        )

        partition_2023 = service.get_partition_for_entity(
            entity_id="event_2023",
            entity_type="Event",
            metadata={"valid_from": datetime(2023, 6, 1, tzinfo=timezone.utc)},
        )

        partition_2024 = service.get_partition_for_entity(
            entity_id="event_2024",
            entity_type="Event",
            metadata={"valid_from": datetime(2024, 6, 1, tzinfo=timezone.utc)},
        )

        assert partition_2023 != partition_2024


class TestHashPartitioning:
    """Test hash-based partitioning strategy."""

    def test_deterministic_partitioning(self) -> None:
        """Test hash partitioning is deterministic."""
        service = KGPartitioningService(strategy=PartitionStrategy.HASH)

        partition1 = service.get_partition_for_entity(
            entity_id="entity_abc123",
            entity_type="Generic",
        )

        # Create new service instance
        service2 = KGPartitioningService(strategy=PartitionStrategy.HASH)

        partition2 = service2.get_partition_for_entity(
            entity_id="entity_abc123",
            entity_type="Generic",
        )

        assert partition1 == partition2

    def test_even_distribution(self) -> None:
        """Test hash distribution is relatively even."""
        service = KGPartitioningService(
            num_partitions=8,
            strategy=PartitionStrategy.HASH,
        )

        partition_counts: dict[str, int] = {}
        for i in range(1000):
            partition = service.get_partition_for_entity(
                entity_id=f"entity_{i:05d}",
                entity_type="Generic",
            )
            partition_counts[partition] = partition_counts.get(partition, 0) + 1

        # Check that all partitions are used
        assert len(partition_counts) == 8

        # Check distribution is relatively even (no partition > 2x average)
        avg = 1000 / 8
        for count in partition_counts.values():
            assert count < avg * 2


class TestQueryRouting:
    """Test query routing to partitions."""

    def test_patient_query_single_partition(self) -> None:
        """Test patient query routes to single partition."""
        service = KGPartitioningService(
            strategy=PartitionStrategy.PATIENT_CENTRIC
        )

        partitions = service.get_partitions_for_query(
            query_type="patient_lookup",
            filters={"patient_id": "P12345"},
        )

        assert len(partitions) == 1

    def test_general_query_all_partitions(self) -> None:
        """Test general query routes to all partitions."""
        service = KGPartitioningService(num_partitions=8)

        partitions = service.get_partitions_for_query(
            query_type="general_search",
            filters={},
        )

        assert len(partitions) == 8

    def test_semantic_type_query_routing(self) -> None:
        """Test semantic type query routes to type partitions."""
        service = KGPartitioningService(
            strategy=PartitionStrategy.SEMANTIC_TYPE
        )

        partitions = service.get_partitions_for_query(
            query_type="type_search",
            filters={"semantic_type": "T047"},
        )

        assert len(partitions) == 1


class TestPartitionStats:
    """Test partition statistics."""

    def test_get_partition_stats(self) -> None:
        """Test getting stats for a partition."""
        service = KGPartitioningService(num_partitions=4)

        # Add some entities
        for i in range(100):
            service.get_partition_for_entity(
                entity_id=f"entity_{i}",
                entity_type="Test",
                metadata={"patient_id": f"P{i % 10}"},
            )

        stats = service.get_partition_stats("partition_000")
        assert stats is not None
        assert stats.partition_id == "partition_000"

    def test_get_all_partition_stats(self) -> None:
        """Test getting stats for all partitions."""
        service = KGPartitioningService(num_partitions=4)

        stats = service.get_all_partition_stats()
        assert len(stats) == 4

    def test_update_partition_stats(self) -> None:
        """Test updating partition statistics."""
        service = KGPartitioningService(num_partitions=4)

        service.update_partition_stats(
            "partition_000",
            node_delta=100,
            edge_delta=500,
        )

        config = service.get_partition_config("partition_000")
        assert config is not None
        assert config.node_count == 100
        assert config.edge_count == 500


class TestRebalancing:
    """Test partition rebalancing."""

    def test_check_rebalance_not_needed(self) -> None:
        """Test rebalance check when balanced."""
        service = KGPartitioningService(num_partitions=4)

        # Even distribution
        for i, partition_id in enumerate(service._partitions):
            service._partitions[partition_id].node_count = 100

        assert service.check_rebalance_needed() is False

    def test_check_rebalance_needed(self) -> None:
        """Test rebalance check when imbalanced."""
        service = KGPartitioningService(num_partitions=4)

        # Uneven distribution
        partition_ids = list(service._partitions.keys())
        service._partitions[partition_ids[0]].node_count = 1000
        service._partitions[partition_ids[1]].node_count = 100
        service._partitions[partition_ids[2]].node_count = 100
        service._partitions[partition_ids[3]].node_count = 100

        assert service.check_rebalance_needed() is True

    @pytest.mark.asyncio
    async def test_rebalance_partitions(self) -> None:
        """Test rebalancing partitions."""
        service = KGPartitioningService(num_partitions=4)

        # Create imbalance
        partition_ids = list(service._partitions.keys())
        service._partitions[partition_ids[0]].node_count = 1000
        service._partitions[partition_ids[1]].node_count = 100
        service._partitions[partition_ids[2]].node_count = 100
        service._partitions[partition_ids[3]].node_count = 100

        operations = await service.rebalance_partitions()

        # Should generate rebalance operations
        assert len(operations) > 0
        assert operations[0].source_partition == partition_ids[0]


class TestEntityAssignment:
    """Test entity assignment tracking."""

    def test_get_entity_assignment(self) -> None:
        """Test getting entity assignment."""
        service = KGPartitioningService()

        service.get_partition_for_entity(
            entity_id="patient_P12345",
            entity_type="Patient",
            metadata={"patient_id": "P12345"},
        )

        assignment = service.get_entity_assignment("patient_P12345")
        assert assignment is not None
        assert assignment.entity_type == "Patient"
        assert assignment.shard_key.startswith("patient:")

    def test_get_assignment_count(self) -> None:
        """Test getting assignment count."""
        service = KGPartitioningService()

        for i in range(50):
            service.get_partition_for_entity(
                entity_id=f"entity_{i}",
                entity_type="Test",
            )

        assert service.get_assignment_count() == 50


class TestRoutingTable:
    """Test partition routing table."""

    def test_get_routing_table(self) -> None:
        """Test getting routing table."""
        service = KGPartitioningService(num_partitions=4)

        table = service.get_routing_table()
        assert table is not None
        assert table.version == 1
        assert len(table.partitions) == 4

    def test_routing_rules_created(self) -> None:
        """Test routing rules are created."""
        service = KGPartitioningService(
            strategy=PartitionStrategy.PATIENT_CENTRIC
        )

        table = service.get_routing_table()
        assert len(table.routing_rules) > 0


class TestPartitionExport:
    """Test partition map export."""

    def test_export_partition_map(self) -> None:
        """Test exporting partition map."""
        service = KGPartitioningService(num_partitions=4)

        exported = service.export_partition_map()

        assert "strategy" in exported
        assert exported["strategy"] == "patient_centric"
        assert "num_partitions" in exported
        assert exported["num_partitions"] == 4
        assert "partitions" in exported
        assert len(exported["partitions"]) == 4


class TestPartitionStrategies:
    """Test PartitionStrategy enum."""

    def test_all_strategies(self) -> None:
        """Test all partition strategies exist."""
        strategies = list(PartitionStrategy)
        assert PartitionStrategy.HASH in strategies
        assert PartitionStrategy.PATIENT_CENTRIC in strategies
        assert PartitionStrategy.SEMANTIC_TYPE in strategies
        assert PartitionStrategy.TEMPORAL in strategies
        assert PartitionStrategy.GEOGRAPHIC in strategies
        assert PartitionStrategy.HYBRID in strategies


class TestPartitionStates:
    """Test PartitionState enum."""

    def test_all_states(self) -> None:
        """Test all partition states exist."""
        states = list(PartitionState)
        assert PartitionState.ACTIVE in states
        assert PartitionState.INACTIVE in states
        assert PartitionState.REBALANCING in states
        assert PartitionState.MIGRATING in states


class TestSingletonPattern:
    """Test singleton service pattern."""

    def test_get_singleton_instance(self) -> None:
        """Test getting singleton service instance."""
        service1 = get_kg_partitioning_service(
            strategy=PartitionStrategy.PATIENT_CENTRIC
        )
        service2 = get_kg_partitioning_service(
            strategy=PartitionStrategy.PATIENT_CENTRIC
        )
        assert service1 is service2

    def test_different_strategies_different_instances(self) -> None:
        """Test different strategies get different instances."""
        service1 = get_kg_partitioning_service(
            strategy=PartitionStrategy.PATIENT_CENTRIC
        )
        service2 = get_kg_partitioning_service(
            strategy=PartitionStrategy.HASH
        )
        assert service1 is not service2
