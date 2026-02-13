"""Pydantic schemas for External Data Integration (EXT-DATA).

Manages external data integration operations: data source registry,
integration pipeline tracking, data quality validation, mapping
configuration, and transfer log management with integration metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    EDC = "edc"
    LABORATORY = "laboratory"
    IMAGING = "imaging"
    WEARABLE = "wearable"
    EHR = "ehr"
    REGISTRY = "registry"


class ConnectionProtocol(str, Enum):
    REST_API = "rest_api"
    SFTP = "sftp"
    HL7_FHIR = "hl7_fhir"
    CDISC_ODM = "cdisc_odm"
    DATABASE_LINK = "database_link"
    FILE_IMPORT = "file_import"


class PipelineStatus(str, Enum):
    CONFIGURED = "configured"
    TESTING = "testing"
    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"
    RETIRED = "retired"


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    BLOCKING = "blocking"


class TransferDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"
    SYNCHRONIZATION = "synchronization"


class DataSourceRegistry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    source_name: str
    source_type: SourceType
    connection_protocol: ConnectionProtocol
    endpoint_url: str | None = None
    is_active: bool = True
    vendor_name: str | None = None
    data_format: str = "JSON"
    refresh_frequency: str = "daily"
    last_successful_sync: datetime | None = None
    total_records_synced: int = Field(ge=0, default=0)
    authentication_method: str = "api_key"
    ssl_required: bool = True
    registered_by: str
    notes: str | None = None
    created_at: datetime


class IntegrationPipeline(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    source_id: str
    pipeline_name: str
    status: PipelineStatus = PipelineStatus.CONFIGURED
    direction: TransferDirection = TransferDirection.INBOUND
    schedule_cron: str | None = None
    last_run_date: datetime | None = None
    next_run_date: datetime | None = None
    total_runs: int = Field(ge=0, default=0)
    successful_runs: int = Field(ge=0, default=0)
    failed_runs: int = Field(ge=0, default=0)
    avg_processing_seconds: float = Field(ge=0, default=0.0)
    error_threshold: int = Field(ge=0, default=5)
    auto_retry: bool = True
    managed_by: str
    notes: str | None = None
    created_at: datetime


class DataQualityValidation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    pipeline_id: str
    validation_name: str
    validation_date: datetime
    severity: ValidationSeverity = ValidationSeverity.INFO
    records_validated: int = Field(ge=0, default=0)
    records_passed: int = Field(ge=0, default=0)
    records_failed: int = Field(ge=0, default=0)
    pass_rate_pct: float = Field(ge=0, le=100, default=100.0)
    rule_description: str
    failure_details: list[str] = Field(default_factory=list)
    auto_resolved: bool = False
    resolved: bool = False
    resolved_by: str | None = None
    validated_by: str
    notes: str | None = None
    created_at: datetime


class MappingConfiguration(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    source_id: str
    mapping_name: str
    source_field: str
    target_field: str
    transformation_rule: str = "direct"
    data_type_source: str = "string"
    data_type_target: str = "string"
    is_required: bool = True
    default_value: str | None = None
    lookup_table: str | None = None
    version: str = "1.0"
    validated: bool = False
    created_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class TransferLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    pipeline_id: str
    transfer_date: datetime
    direction: TransferDirection
    records_sent: int = Field(ge=0, default=0)
    records_received: int = Field(ge=0, default=0)
    records_rejected: int = Field(ge=0, default=0)
    file_size_bytes: int = Field(ge=0, default=0)
    duration_seconds: float = Field(ge=0, default=0.0)
    status: str = "completed"
    error_message: str | None = None
    checksum: str | None = None
    acknowledged_by_target: bool = False
    initiated_by: str
    notes: str | None = None
    created_at: datetime


class DataSourceRegistryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    source_name: str
    source_type: SourceType
    connection_protocol: ConnectionProtocol
    registered_by: str
    vendor_name: str | None = None
    data_format: str = "JSON"


class DataSourceRegistryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    refresh_frequency: str | None = None
    total_records_synced: int | None = None
    last_successful_sync: datetime | None = None
    notes: str | None = None


class IntegrationPipelineCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    source_id: str
    pipeline_name: str
    managed_by: str
    direction: TransferDirection = TransferDirection.INBOUND
    schedule_cron: str | None = None


class IntegrationPipelineUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: PipelineStatus | None = None
    successful_runs: int | None = None
    failed_runs: int | None = None
    auto_retry: bool | None = None
    notes: str | None = None


class DataQualityValidationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    pipeline_id: str
    validation_name: str
    rule_description: str
    validated_by: str
    records_validated: int = Field(ge=0, default=0)
    severity: ValidationSeverity = ValidationSeverity.INFO


class DataQualityValidationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resolved: bool | None = None
    resolved_by: str | None = None
    severity: ValidationSeverity | None = None
    records_failed: int | None = None
    notes: str | None = None


class MappingConfigurationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    source_id: str
    mapping_name: str
    source_field: str
    target_field: str
    created_by: str
    transformation_rule: str = "direct"


class MappingConfigurationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    validated: bool | None = None
    transformation_rule: str | None = None
    approved_by: str | None = None
    default_value: str | None = None
    notes: str | None = None


class TransferLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    pipeline_id: str
    direction: TransferDirection
    initiated_by: str
    records_sent: int = Field(ge=0, default=0)
    records_received: int = Field(ge=0, default=0)


class TransferLogUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    records_rejected: int | None = None
    acknowledged_by_target: bool | None = None
    error_message: str | None = None
    notes: str | None = None


class DataSourceRegistryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataSourceRegistry] = Field(default_factory=list)
    total: int = Field(ge=0)


class IntegrationPipelineListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[IntegrationPipeline] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataQualityValidationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataQualityValidation] = Field(default_factory=list)
    total: int = Field(ge=0)


class MappingConfigurationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MappingConfiguration] = Field(default_factory=list)
    total: int = Field(ge=0)


class TransferLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TransferLog] = Field(default_factory=list)
    total: int = Field(ge=0)


class ExternalDataIntegrationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_data_sources: int = Field(ge=0)
    sources_by_type: dict[str, int] = Field(default_factory=dict)
    sources_by_protocol: dict[str, int] = Field(default_factory=dict)
    active_sources: int = Field(ge=0)
    total_pipelines: int = Field(ge=0)
    pipelines_by_status: dict[str, int] = Field(default_factory=dict)
    active_pipelines: int = Field(ge=0)
    total_validations: int = Field(ge=0)
    validations_by_severity: dict[str, int] = Field(default_factory=dict)
    unresolved_validations: int = Field(ge=0)
    total_mappings: int = Field(ge=0)
    validated_mappings: int = Field(ge=0)
    total_transfers: int = Field(ge=0)
    transfers_by_direction: dict[str, int] = Field(default_factory=dict)
    total_records_transferred: int = Field(ge=0)
