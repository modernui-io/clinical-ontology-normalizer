"""Tests for KG Kafka Streaming Service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.kg_kafka_streaming_service import (
    ConsumerConfig,
    EventType,
    GraphUpdate,
    KGKafkaStreamingService,
    ProcessingResult,
    ProcessingStatus,
    ProducerConfig,
    StreamEvent,
    get_kg_kafka_streaming_service,
)


class TestStreamEvent:
    """Test StreamEvent dataclass."""

    def test_create_stream_event(self) -> None:
        """Test creating a stream event."""
        event = StreamEvent(
            event_id="evt_001",
            event_type=EventType.DIAGNOSIS_ADDED,
            timestamp=datetime.now(timezone.utc),
            patient_id="P12345",
            payload={"icd10_code": "E11.9", "name": "Type 2 Diabetes"},
            source_system="ehr-system",
        )
        assert event.event_id == "evt_001"
        assert event.event_type == EventType.DIAGNOSIS_ADDED
        assert event.patient_id == "P12345"

    def test_event_with_correlation_id(self) -> None:
        """Test event with correlation ID for tracing."""
        event = StreamEvent(
            event_id="evt_002",
            event_type=EventType.MEDICATION_ORDERED,
            timestamp=datetime.now(timezone.utc),
            patient_id="P12345",
            payload={"rxnorm_code": "860975", "name": "Metformin"},
            source_system="pharmacy",
            correlation_id="corr_abc123",
            partition_key="P12345",
        )
        assert event.correlation_id == "corr_abc123"
        assert event.partition_key == "P12345"


class TestProcessingResult:
    """Test ProcessingResult dataclass."""

    def test_create_successful_result(self) -> None:
        """Test creating a successful processing result."""
        result = ProcessingResult(
            event_id="evt_001",
            status=ProcessingStatus.COMPLETED,
            nodes_created=2,
            edges_created=3,
            inferences_made=1,
            processing_time_ms=15.5,
        )
        assert result.status == ProcessingStatus.COMPLETED
        assert result.nodes_created == 2
        assert result.edges_created == 3

    def test_create_failed_result(self) -> None:
        """Test creating a failed processing result."""
        result = ProcessingResult(
            event_id="evt_002",
            status=ProcessingStatus.FAILED,
            error="Connection timeout",
        )
        assert result.status == ProcessingStatus.FAILED
        assert result.error == "Connection timeout"


class TestGraphUpdate:
    """Test GraphUpdate dataclass."""

    def test_create_node_update(self) -> None:
        """Test creating a node update."""
        update = GraphUpdate(
            operation="create_node",
            entity_type="Condition",
            entity_id="cond_E11.9_P12345",
            properties={
                "code": "E11.9",
                "name": "Type 2 Diabetes",
            },
            temporal={
                "valid_from": "2024-01-01T00:00:00Z",
            },
        )
        assert update.operation == "create_node"
        assert update.entity_type == "Condition"
        assert update.temporal is not None

    def test_create_edge_update(self) -> None:
        """Test creating an edge update."""
        update = GraphUpdate(
            operation="create_edge",
            entity_type="TREATS",
            entity_id="edge_drug_cond",
            properties={
                "source": "drug_metformin",
                "target": "cond_diabetes",
            },
        )
        assert update.operation == "create_edge"
        assert "source" in update.properties


class TestConsumerConfig:
    """Test ConsumerConfig dataclass."""

    def test_create_consumer_config(self) -> None:
        """Test creating consumer configuration."""
        config = ConsumerConfig(
            bootstrap_servers=["kafka1:9092", "kafka2:9092"],
            topics=["clinical-events"],
            group_id="kg-consumer",
        )
        assert len(config.bootstrap_servers) == 2
        assert "clinical-events" in config.topics
        assert config.auto_offset_reset == "latest"


class TestProducerConfig:
    """Test ProducerConfig dataclass."""

    def test_create_producer_config(self) -> None:
        """Test creating producer configuration."""
        config = ProducerConfig(
            bootstrap_servers=["kafka1:9092"],
            acks="all",
            retries=5,
        )
        assert config.acks == "all"
        assert config.retries == 5


class TestKGKafkaStreamingService:
    """Test KGKafkaStreamingService class."""

    def test_service_initialization(self) -> None:
        """Test service initializes correctly."""
        service = KGKafkaStreamingService()
        assert service._running is False
        assert service._processed_count == 0
        assert len(service._handlers) > 0

    def test_default_handlers_registered(self) -> None:
        """Test default handlers are registered."""
        service = KGKafkaStreamingService()

        # Check key event types have handlers
        assert EventType.DIAGNOSIS_ADDED in service._handlers
        assert EventType.MEDICATION_ORDERED in service._handlers
        assert EventType.LAB_RESULTED in service._handlers

    def test_register_custom_handler(self) -> None:
        """Test registering a custom handler."""
        service = KGKafkaStreamingService()

        def custom_handler(event: StreamEvent) -> ProcessingResult:
            return ProcessingResult(
                event_id=event.event_id,
                status=ProcessingStatus.COMPLETED,
            )

        initial_count = len(service._handlers.get(EventType.PATIENT_ADMIT, []))
        service.register_handler(EventType.PATIENT_ADMIT, custom_handler)

        assert len(service._handlers[EventType.PATIENT_ADMIT]) == initial_count + 1

    def test_create_event(self) -> None:
        """Test creating an event."""
        service = KGKafkaStreamingService()

        event = service.create_event(
            event_type=EventType.DIAGNOSIS_ADDED,
            payload={"icd10_code": "I10", "name": "Hypertension"},
            patient_id="P12345",
            source_system="ehr",
        )

        assert event.event_id is not None
        assert event.event_type == EventType.DIAGNOSIS_ADDED
        assert event.patient_id == "P12345"
        assert event.partition_key == "P12345"

    @pytest.mark.asyncio
    async def test_publish_event(self) -> None:
        """Test publishing an event to the queue."""
        service = KGKafkaStreamingService()

        event = service.create_event(
            event_type=EventType.LAB_RESULTED,
            payload={"loinc_code": "4548-4", "value": 7.2},
            patient_id="P12345",
        )

        await service.publish_event(event)
        assert service._event_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_start_stop_service(self) -> None:
        """Test starting and stopping the service."""
        service = KGKafkaStreamingService()

        assert service._running is False

        await service.start()
        assert service._running is True

        await service.stop()
        assert service._running is False


class TestEventHandlers:
    """Test individual event handlers."""

    @pytest.mark.asyncio
    async def test_handle_diagnosis_added(self) -> None:
        """Test handling diagnosis added event."""
        service = KGKafkaStreamingService()

        event = StreamEvent(
            event_id="evt_001",
            event_type=EventType.DIAGNOSIS_ADDED,
            timestamp=datetime.now(timezone.utc),
            patient_id="P12345",
            payload={
                "icd10_code": "E11.9",
                "name": "Type 2 Diabetes Mellitus",
                "onset_date": "2024-01-15",
            },
            source_system="ehr",
        )

        result = await service._handle_diagnosis_added(event)

        assert result.status == ProcessingStatus.COMPLETED
        assert result.nodes_created >= 1
        assert result.edges_created >= 1

    @pytest.mark.asyncio
    async def test_handle_medication_ordered(self) -> None:
        """Test handling medication ordered event."""
        service = KGKafkaStreamingService()

        event = StreamEvent(
            event_id="evt_002",
            event_type=EventType.MEDICATION_ORDERED,
            timestamp=datetime.now(timezone.utc),
            patient_id="P12345",
            payload={
                "rxnorm_code": "860975",
                "name": "Metformin 500mg",
                "dose": "500mg",
            },
            source_system="pharmacy",
        )

        result = await service._handle_medication_ordered(event)

        assert result.status == ProcessingStatus.COMPLETED
        assert result.nodes_created >= 1
        assert result.inferences_made >= 1

    @pytest.mark.asyncio
    async def test_handle_lab_critical(self) -> None:
        """Test handling critical lab value event."""
        service = KGKafkaStreamingService()

        event = StreamEvent(
            event_id="evt_003",
            event_type=EventType.LAB_CRITICAL,
            timestamp=datetime.now(timezone.utc),
            patient_id="P12345",
            payload={
                "loinc_code": "2345-7",
                "name": "Glucose",
                "value": 450,
                "critical_high": 400,
            },
            source_system="lab",
        )

        result = await service._handle_lab_critical(event)

        assert result.status == ProcessingStatus.COMPLETED
        # Critical values should trigger more inferences
        assert result.inferences_made >= 1


class TestEventSerialization:
    """Test event serialization and deserialization."""

    def test_serialize_event(self) -> None:
        """Test serializing an event to JSON."""
        service = KGKafkaStreamingService()

        event = service.create_event(
            event_type=EventType.DIAGNOSIS_ADDED,
            payload={"icd10_code": "E11.9"},
            patient_id="P12345",
        )

        serialized = service.serialize_event(event)
        assert isinstance(serialized, str)
        assert "diagnosis.added" in serialized
        assert "P12345" in serialized

    def test_deserialize_event(self) -> None:
        """Test deserializing an event from JSON."""
        service = KGKafkaStreamingService()

        original = service.create_event(
            event_type=EventType.MEDICATION_ORDERED,
            payload={"rxnorm_code": "860975"},
            patient_id="P12345",
            correlation_id="corr_123",
        )

        serialized = service.serialize_event(original)
        deserialized = service.deserialize_event(serialized)

        assert deserialized.event_id == original.event_id
        assert deserialized.event_type == original.event_type
        assert deserialized.patient_id == original.patient_id
        assert deserialized.correlation_id == original.correlation_id

    def test_roundtrip_serialization(self) -> None:
        """Test round-trip serialization preserves data."""
        service = KGKafkaStreamingService()

        event = StreamEvent(
            event_id="test_001",
            event_type=EventType.LAB_RESULTED,
            timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            patient_id="P12345",
            payload={
                "loinc_code": "4548-4",
                "value": 7.2,
                "unit": "%",
            },
            source_system="lab-system",
            correlation_id="corr_xyz",
            partition_key="P12345",
            metadata={"lab_id": "lab_001"},
        )

        serialized = service.serialize_event(event)
        restored = service.deserialize_event(serialized)

        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        assert restored.patient_id == event.patient_id
        assert restored.payload == event.payload


class TestMetricsAndStats:
    """Test metrics and statistics."""

    def test_get_metrics_initial(self) -> None:
        """Test getting metrics on fresh service."""
        service = KGKafkaStreamingService()
        metrics = service.get_metrics()

        assert metrics["running"] is False
        assert metrics["processed_count"] == 0
        assert metrics["error_count"] == 0
        assert "registered_handlers" in metrics

    def test_get_processing_stats_empty(self) -> None:
        """Test getting stats with no processed events."""
        service = KGKafkaStreamingService()
        stats = service.get_processing_stats()

        assert "message" in stats

    def test_get_recent_results_empty(self) -> None:
        """Test getting recent results when empty."""
        service = KGKafkaStreamingService()
        results = service.get_recent_results()

        assert results == []


class TestEventTypes:
    """Test EventType enum."""

    def test_patient_events(self) -> None:
        """Test patient event types."""
        assert EventType.PATIENT_ADMIT.value == "patient.admit"
        assert EventType.PATIENT_DISCHARGE.value == "patient.discharge"
        assert EventType.PATIENT_TRANSFER.value == "patient.transfer"

    def test_clinical_events(self) -> None:
        """Test clinical event types."""
        assert EventType.DIAGNOSIS_ADDED.value == "diagnosis.added"
        assert EventType.MEDICATION_ORDERED.value == "medication.ordered"
        assert EventType.LAB_RESULTED.value == "lab.resulted"

    def test_kg_events(self) -> None:
        """Test knowledge graph event types."""
        assert EventType.CONCEPT_ADDED.value == "kg.concept.added"
        assert EventType.RELATION_ADDED.value == "kg.relation.added"
        assert EventType.INFERENCE_MADE.value == "kg.inference.made"


class TestProcessingStatus:
    """Test ProcessingStatus enum."""

    def test_all_statuses(self) -> None:
        """Test all processing statuses exist."""
        statuses = list(ProcessingStatus)
        assert ProcessingStatus.PENDING in statuses
        assert ProcessingStatus.PROCESSING in statuses
        assert ProcessingStatus.COMPLETED in statuses
        assert ProcessingStatus.FAILED in statuses
        assert ProcessingStatus.RETRYING in statuses


class TestSingletonPattern:
    """Test singleton service pattern."""

    def test_get_singleton_instance(self) -> None:
        """Test getting singleton service instance."""
        service1 = get_kg_kafka_streaming_service()
        service2 = get_kg_kafka_streaming_service()
        assert service1 is service2


class TestProcessSingleEvent:
    """Test single event processing."""

    @pytest.mark.asyncio
    async def test_process_event_with_handler(self) -> None:
        """Test processing an event that has a handler."""
        service = KGKafkaStreamingService()

        event = StreamEvent(
            event_id="evt_001",
            event_type=EventType.DIAGNOSIS_ADDED,
            timestamp=datetime.now(timezone.utc),
            patient_id="P12345",
            payload={"icd10_code": "E11.9"},
            source_system="ehr",
        )

        result = await service._process_single_event(event)

        assert result.event_id == "evt_001"
        assert result.status == ProcessingStatus.COMPLETED
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_process_event_without_handler(self) -> None:
        """Test processing an event without a handler."""
        service = KGKafkaStreamingService()

        event = StreamEvent(
            event_id="evt_002",
            event_type=EventType.PATIENT_TRANSFER,  # May not have default handler
            timestamp=datetime.now(timezone.utc),
            patient_id="P12345",
            payload={},
            source_system="adt",
        )

        result = await service._process_single_event(event)

        # Should complete even without handler
        assert result.status == ProcessingStatus.COMPLETED
