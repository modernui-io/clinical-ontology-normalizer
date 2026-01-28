"""
Data Source Models

Models for managing external data source connections (FHIR servers, HIEs, aggregators).
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class DataSourceType(str, PyEnum):
    """Types of data sources that can be configured."""
    FHIR_SERVER = "fhir_server"
    HIE = "hie"
    AGGREGATOR = "aggregator"
    FILE_UPLOAD = "file_upload"
    HL7_FEED = "hl7_feed"
    DATABASE = "database"
    CCDA = "ccda"


class HealthStatus(str, PyEnum):
    """Health status of a data source connection."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class AuthMethod(str, PyEnum):
    """Authentication methods for data sources."""
    NONE = "none"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    OAUTH2_AUTHORIZATION_CODE = "oauth2_authorization_code"
    API_KEY = "api_key"
    SMART_BACKEND = "smart_backend"


class DataSource(Base):
    """
    Configured external data source for importing clinical data.

    Stores connection details, credentials (encrypted), and health status
    for FHIR servers, HIEs, aggregator services, etc.
    """
    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(Enum(DataSourceType), nullable=False)

    # Connection configuration (stored as JSON, credentials encrypted)
    connection_config = Column(JSON, nullable=False, default=dict)
    # Example structure:
    # {
    #   "base_url": "https://fhir.example.com",
    #   "auth_method": "oauth2_client_credentials",
    #   "client_id": "...",
    #   "client_secret_encrypted": "...",  # Fernet encrypted
    #   "token_url": "https://auth.example.com/token",
    #   "scopes": ["patient/*.read", "system/*.read"],
    #   "timeout_seconds": 30,
    #   "verify_ssl": true
    # }

    # Authentication method (for UI rendering and validation)
    auth_method = Column(Enum(AuthMethod), nullable=False, default=AuthMethod.NONE)

    # Status tracking
    is_active = Column(Boolean, default=True, nullable=False)
    health_status = Column(Enum(HealthStatus), default=HealthStatus.UNKNOWN, nullable=False)
    last_health_check_at = Column(DateTime(timezone=True), nullable=True)
    last_health_message = Column(Text, nullable=True)

    # Connection statistics
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    total_records_imported = Column(Integer, default=0, nullable=False)

    # Default settings for pipelines using this source
    default_batch_size = Column(Integer, default=100, nullable=False)
    default_timeout_seconds = Column(Integer, default=300, nullable=False)
    default_retry_count = Column(Integer, default=3, nullable=False)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)  # User ID

    # Relationships
    pipelines = relationship("Pipeline", back_populates="data_source", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_data_sources_source_type", "source_type"),
        Index("ix_data_sources_is_active", "is_active"),
        Index("ix_data_sources_health_status", "health_status"),
    )

    def __repr__(self):
        return f"<DataSource(id={self.id}, name='{self.name}', type={self.source_type.value})>"


class PipelineStatus(str, PyEnum):
    """Status of a pipeline."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class ScheduleType(str, PyEnum):
    """Types of pipeline schedules."""
    MANUAL = "manual"
    INTERVAL = "interval"
    CRON = "cron"


class Pipeline(Base):
    """
    Data ingestion pipeline configuration.

    Defines how data flows from a source through transformation stages
    into the clinical ontology database.
    """
    __tablename__ = "pipelines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Link to data source
    source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)

    # Status
    status = Column(Enum(PipelineStatus), default=PipelineStatus.ACTIVE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Schedule configuration
    schedule_type = Column(Enum(ScheduleType), default=ScheduleType.MANUAL, nullable=False)
    schedule_cron = Column(String(100), nullable=True)  # Cron expression: "0 2 * * *" = 2 AM daily
    schedule_interval_minutes = Column(Integer, nullable=True)  # For interval schedules

    # Transformation configuration
    transformation_config = Column(JSON, nullable=False, default=dict)
    # Example structure:
    # {
    #   "patient_matching": {
    #     "strategy": "deterministic",  # or "probabilistic"
    #     "match_fields": ["mrn", "ssn_last4", "dob", "name"]
    #   },
    #   "code_mapping": {
    #     "prefer_standard": true,
    #     "fallback_to_source": true
    #   },
    #   "nlp_enrichment": {
    #     "enabled": true,
    #     "process_notes": true,
    #     "extract_values": true
    #   },
    #   "quality_thresholds": {
    #     "min_completeness": 0.8,
    #     "max_error_rate": 0.1
    #   },
    #   "filters": {
    #     "resource_types": ["Patient", "Condition", "MedicationRequest"],
    #     "date_range": {"start": "2024-01-01", "end": null}
    #   }
    # }

    # Run tracking
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_status = Column(String(50), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    total_runs = Column(Integer, default=0, nullable=False)
    successful_runs = Column(Integer, default=0, nullable=False)
    failed_runs = Column(Integer, default=0, nullable=False)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    data_source = relationship("DataSource", back_populates="pipelines")
    runs = relationship("PipelineRun", back_populates="pipeline", cascade="all, delete-orphan", order_by="desc(PipelineRun.started_at)")

    __table_args__ = (
        Index("ix_pipelines_source_id", "source_id"),
        Index("ix_pipelines_status", "status"),
        Index("ix_pipelines_is_active", "is_active"),
        Index("ix_pipelines_next_run_at", "next_run_at"),
    )

    def __repr__(self):
        return f"<Pipeline(id={self.id}, name='{self.name}', status={self.status.value})>"


class PipelineRunStatus(str, PyEnum):
    """Status of a pipeline run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, PyEnum):
    """Stages in the pipeline execution."""
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    INGESTING = "ingesting"
    VALIDATING = "validating"
    TRANSFORMING = "transforming"
    ENRICHING = "enriching"
    LOADING = "loading"
    FINALIZING = "finalizing"


class PipelineRun(Base):
    """
    Record of a single pipeline execution.

    Tracks progress, statistics, and errors for each run.
    """
    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)

    # Status tracking
    status = Column(Enum(PipelineRunStatus), default=PipelineRunStatus.PENDING, nullable=False)
    current_stage = Column(Enum(PipelineStage), default=PipelineStage.INITIALIZING, nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Statistics
    records_total = Column(Integer, default=0, nullable=False)
    records_processed = Column(Integer, default=0, nullable=False)
    records_succeeded = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)
    records_skipped = Column(Integer, default=0, nullable=False)

    # Detailed statistics by stage
    stage_statistics = Column(JSON, nullable=False, default=dict)
    # Example:
    # {
    #   "ingest": {"records": 1000, "duration_ms": 5000},
    #   "validate": {"records": 1000, "valid": 980, "invalid": 20, "duration_ms": 2000},
    #   "transform": {"records": 980, "mapped": 950, "unmapped": 30, "duration_ms": 8000},
    #   "enrich": {"documents": 200, "mentions": 1500, "facts": 800, "duration_ms": 15000},
    #   "load": {"inserted": 950, "updated": 0, "duration_ms": 3000}
    # }

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)  # Stack trace, failed records, etc.
    warnings = Column(JSON, nullable=False, default=list)  # Non-fatal issues

    # Trigger info
    triggered_by = Column(String(50), default="manual", nullable=False)  # "manual", "schedule", "api"
    triggered_by_user = Column(UUID(as_uuid=True), nullable=True)

    # Created entities (for potential rollback)
    created_entity_ids = Column(JSON, nullable=False, default=dict)
    # Example:
    # {
    #   "persons": ["uuid1", "uuid2"],
    #   "conditions": ["uuid3", "uuid4"],
    #   "clinical_facts": ["uuid5", "uuid6"]
    # }

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="runs")

    __table_args__ = (
        Index("ix_pipeline_runs_pipeline_id", "pipeline_id"),
        Index("ix_pipeline_runs_status", "status"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )

    def __repr__(self):
        return f"<PipelineRun(id={self.id}, pipeline_id={self.pipeline_id}, status={self.status.value})>"

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate run duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self) -> Optional[float]:
        """Calculate success rate as percentage."""
        if self.records_processed > 0:
            return (self.records_succeeded / self.records_processed) * 100
        return None
