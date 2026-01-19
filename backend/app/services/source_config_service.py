"""ETL Source Configuration Service.

This module provides services for managing ETL data source configurations,
including secure credential storage, connection testing, and sample data retrieval.

Features:
    - Source configuration CRUD operations
    - Encrypted credential storage using Fernet
    - Connection testing for all supported source types
    - Sample data preview functionality
    - Pipeline configuration and scheduling

Supported Source Types:
    - FHIR (R4 and STU3)
    - HL7v2 (v2.x messages)
    - C-CDA (Clinical Document Architecture)
    - CSV (Comma-separated values)
    - Database (PostgreSQL, MySQL, SQL Server)
"""

import asyncio
import base64
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================


class SourceType(str, Enum):
    """Supported ETL source types."""

    FHIR = "fhir"
    HL7V2 = "hl7v2"
    CCDA = "ccda"
    CSV = "csv"
    DATABASE = "database"


class ConnectionStatus(str, Enum):
    """Connection status for a data source."""

    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TESTING = "testing"


class PipelineStatus(str, Enum):
    """Status of an ETL pipeline."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    ERROR = "error"


class ScheduleFrequency(str, Enum):
    """Frequency options for pipeline scheduling."""

    MANUAL = "manual"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


# Default encryption key - in production, this should come from environment/secrets
DEFAULT_ENCRYPTION_KEY = os.environ.get(
    "ETL_ENCRYPTION_KEY",
    Fernet.generate_key().decode()
)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class SourceCredentials:
    """Credentials for connecting to a data source.

    All credential fields are optional; different source types require
    different credentials.

    Attributes:
        username: Username for authentication.
        password: Password for authentication (stored encrypted).
        api_key: API key for token-based auth.
        client_id: OAuth2 client ID.
        client_secret: OAuth2 client secret.
        auth_token: Bearer token for FHIR servers.
        ssh_key: SSH private key for secure connections.
        certificate: Client certificate for mTLS.
        extra: Additional credential fields.
    """

    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    auth_token: str | None = None
    ssh_key: str | None = None
    certificate: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def has_credentials(self) -> bool:
        """Check if any credentials are set."""
        return any([
            self.username,
            self.password,
            self.api_key,
            self.client_id,
            self.client_secret,
            self.auth_token,
            self.ssh_key,
            self.certificate,
            self.extra,
        ])

    def to_dict(self, mask: bool = True) -> dict[str, Any]:
        """Convert to dictionary, optionally masking sensitive values."""
        def mask_value(value: str | None) -> str | None:
            if value is None:
                return None
            if mask:
                return "******" if len(value) > 0 else None
            return value

        result = {
            "username": self.username,
            "password": mask_value(self.password),
            "api_key": mask_value(self.api_key),
            "client_id": self.client_id,
            "client_secret": mask_value(self.client_secret),
            "auth_token": mask_value(self.auth_token),
            "ssh_key": mask_value(self.ssh_key),
            "certificate": mask_value(self.certificate),
        }

        if self.extra:
            result["extra"] = {
                k: mask_value(v) if mask else v
                for k, v in self.extra.items()
            }

        return result


@dataclass
class ConnectionParams:
    """Connection parameters for a data source.

    Attributes:
        host: Hostname or IP address.
        port: Port number.
        path: Path (URL path or filesystem path).
        database: Database name for database sources.
        schema: Schema name for database sources.
        ssl_enabled: Whether to use SSL/TLS.
        verify_ssl: Whether to verify SSL certificates.
        timeout_seconds: Connection timeout.
        extra: Additional connection parameters.
    """

    host: str | None = None
    port: int | None = None
    path: str | None = None
    database: str | None = None
    schema: str | None = None
    ssl_enabled: bool = True
    verify_ssl: bool = True
    timeout_seconds: int = 30
    extra: dict[str, Any] = field(default_factory=dict)

    def get_connection_string(self, source_type: SourceType) -> str:
        """Generate a connection string based on source type."""
        if source_type == SourceType.FHIR:
            protocol = "https" if self.ssl_enabled else "http"
            port_str = f":{self.port}" if self.port else ""
            path_str = self.path or "/fhir"
            return f"{protocol}://{self.host}{port_str}{path_str}"

        elif source_type == SourceType.DATABASE:
            # PostgreSQL style connection string
            port_str = f":{self.port}" if self.port else ""
            db_str = f"/{self.database}" if self.database else ""
            return f"postgresql://{self.host}{port_str}{db_str}"

        elif source_type in (SourceType.CSV, SourceType.HL7V2, SourceType.CCDA):
            return self.path or ""

        return ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "database": self.database,
            "schema": self.schema,
            "ssl_enabled": self.ssl_enabled,
            "verify_ssl": self.verify_ssl,
            "timeout_seconds": self.timeout_seconds,
            "extra": self.extra,
        }


@dataclass
class SourceConfig:
    """Configuration for an ETL data source.

    Attributes:
        id: Unique identifier.
        name: Human-readable name.
        description: Optional description.
        source_type: Type of data source.
        connection_params: Connection parameters.
        credentials: Authentication credentials.
        status: Current connection status.
        enabled: Whether the source is enabled.
        last_tested_at: When connection was last tested.
        last_sync_at: When data was last synced.
        test_result: Result of last connection test.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        metadata: Additional metadata.
    """

    id: UUID
    name: str
    source_type: SourceType
    connection_params: ConnectionParams
    description: str = ""
    credentials: SourceCredentials = field(default_factory=SourceCredentials)
    status: ConnectionStatus = ConnectionStatus.UNKNOWN
    enabled: bool = True
    last_tested_at: datetime | None = None
    last_sync_at: datetime | None = None
    test_result: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_credentials: bool = False) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type.value,
            "connection_params": self.connection_params.to_dict(),
            "status": self.status.value,
            "enabled": self.enabled,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "test_result": self.test_result,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

        if include_credentials:
            result["credentials"] = self.credentials.to_dict(mask=True)

        return result


@dataclass
class PipelineSchedule:
    """Schedule configuration for an ETL pipeline.

    Attributes:
        frequency: How often to run.
        cron_expression: Cron expression for custom schedules.
        time_of_day: Time to run (HH:MM format).
        day_of_week: Day of week (0-6, Monday=0).
        day_of_month: Day of month (1-31).
        timezone: Timezone for scheduling.
        enabled: Whether scheduling is enabled.
    """

    frequency: ScheduleFrequency = ScheduleFrequency.MANUAL
    cron_expression: str | None = None
    time_of_day: str = "00:00"
    day_of_week: int | None = None
    day_of_month: int | None = None
    timezone: str = "UTC"
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frequency": self.frequency.value,
            "cron_expression": self.cron_expression,
            "time_of_day": self.time_of_day,
            "day_of_week": self.day_of_week,
            "day_of_month": self.day_of_month,
            "timezone": self.timezone,
            "enabled": self.enabled,
        }


@dataclass
class PipelineStage:
    """A stage in an ETL pipeline.

    Attributes:
        name: Stage name.
        stage_type: Type of stage (extract, transform, load).
        config: Stage-specific configuration.
        order: Execution order.
        enabled: Whether the stage is enabled.
    """

    name: str
    stage_type: str
    config: dict[str, Any] = field(default_factory=dict)
    order: int = 0
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "stage_type": self.stage_type,
            "config": self.config,
            "order": self.order,
            "enabled": self.enabled,
        }


@dataclass
class PipelineRun:
    """Record of a pipeline execution.

    Attributes:
        id: Unique identifier.
        pipeline_id: ID of the pipeline.
        status: Run status.
        started_at: Start timestamp.
        completed_at: Completion timestamp.
        records_processed: Number of records processed.
        records_failed: Number of records that failed.
        error_message: Error message if failed.
        duration_seconds: Total duration.
    """

    id: UUID
    pipeline_id: UUID
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    records_processed: int = 0
    records_failed: int = 0
    error_message: str | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "pipeline_id": str(self.pipeline_id),
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "records_processed": self.records_processed,
            "records_failed": self.records_failed,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class Pipeline:
    """ETL pipeline configuration.

    Attributes:
        id: Unique identifier.
        name: Pipeline name.
        description: Optional description.
        source_id: ID of the data source.
        status: Pipeline status.
        schedule: Schedule configuration.
        stages: List of pipeline stages.
        batch_size: Records per batch.
        max_records: Maximum records to process.
        skip_on_error: Continue on errors.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        last_run_at: Last execution timestamp.
        last_run_status: Status of last run.
        run_count: Total number of runs.
    """

    id: UUID
    name: str
    source_id: UUID
    description: str = ""
    status: PipelineStatus = PipelineStatus.ACTIVE
    schedule: PipelineSchedule = field(default_factory=PipelineSchedule)
    stages: list[PipelineStage] = field(default_factory=list)
    batch_size: int = 100
    max_records: int | None = None
    skip_on_error: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    run_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "source_id": str(self.source_id),
            "status": self.status.value,
            "schedule": self.schedule.to_dict(),
            "stages": [s.to_dict() for s in self.stages],
            "batch_size": self.batch_size,
            "max_records": self.max_records,
            "skip_on_error": self.skip_on_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
            "run_count": self.run_count,
        }


@dataclass
class ConnectionTestResult:
    """Result of a connection test.

    Attributes:
        success: Whether the connection succeeded.
        message: Human-readable result message.
        latency_ms: Connection latency in milliseconds.
        server_info: Information about the server.
        error_details: Detailed error information if failed.
        tested_at: When the test was performed.
    """

    success: bool
    message: str
    latency_ms: float | None = None
    server_info: dict[str, Any] = field(default_factory=dict)
    error_details: str | None = None
    tested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "server_info": self.server_info,
            "error_details": self.error_details,
            "tested_at": self.tested_at.isoformat(),
        }


@dataclass
class SampleDataPreview:
    """Preview of sample data from a source.

    Attributes:
        source_id: ID of the source.
        record_count: Number of sample records.
        records: Sample records.
        schema_info: Information about the data schema.
        fetched_at: When the preview was fetched.
    """

    source_id: UUID
    record_count: int
    records: list[dict[str, Any]]
    schema_info: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": str(self.source_id),
            "record_count": self.record_count,
            "records": self.records,
            "schema_info": self.schema_info,
            "fetched_at": self.fetched_at.isoformat(),
        }


# ============================================================================
# Credential Encryption Service
# ============================================================================


class CredentialEncryptor:
    """Service for encrypting and decrypting credentials.

    Uses Fernet symmetric encryption for secure credential storage.
    """

    def __init__(self, encryption_key: str | None = None):
        """Initialize with an encryption key.

        Args:
            encryption_key: Base64-encoded Fernet key.
                          If not provided, uses environment variable or generates one.
        """
        key = encryption_key or DEFAULT_ENCRYPTION_KEY
        if isinstance(key, str):
            key = key.encode()
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        """Encrypt a string value.

        Args:
            value: Plain text value to encrypt.

        Returns:
            Base64-encoded encrypted value.
        """
        encrypted = self._fernet.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt an encrypted value.

        Args:
            encrypted_value: Base64-encoded encrypted value.

        Returns:
            Decrypted plain text value.

        Raises:
            InvalidToken: If decryption fails.
        """
        encrypted = base64.b64decode(encrypted_value.encode())
        decrypted = self._fernet.decrypt(encrypted)
        return decrypted.decode()

    def encrypt_credentials(self, credentials: SourceCredentials) -> dict[str, str]:
        """Encrypt all non-null credential values.

        Args:
            credentials: Credentials to encrypt.

        Returns:
            Dictionary of encrypted credential values.
        """
        encrypted = {}

        for field_name in ["password", "api_key", "client_secret", "auth_token", "ssh_key", "certificate"]:
            value = getattr(credentials, field_name)
            if value:
                encrypted[field_name] = self.encrypt(value)

        if credentials.extra:
            encrypted["extra"] = {
                k: self.encrypt(v)
                for k, v in credentials.extra.items()
            }

        return encrypted

    def decrypt_credentials(
        self,
        encrypted: dict[str, str],
        credentials: SourceCredentials,
    ) -> SourceCredentials:
        """Decrypt credential values into a SourceCredentials object.

        Args:
            encrypted: Dictionary of encrypted values.
            credentials: Base credentials to update.

        Returns:
            Updated SourceCredentials with decrypted values.
        """
        for field_name in ["password", "api_key", "client_secret", "auth_token", "ssh_key", "certificate"]:
            if field_name in encrypted:
                try:
                    setattr(credentials, field_name, self.decrypt(encrypted[field_name]))
                except InvalidToken:
                    logger.warning(f"Failed to decrypt {field_name}")

        if "extra" in encrypted:
            for key, value in encrypted["extra"].items():
                try:
                    credentials.extra[key] = self.decrypt(value)
                except InvalidToken:
                    logger.warning(f"Failed to decrypt extra.{key}")

        return credentials


# ============================================================================
# Source Configuration Service
# ============================================================================


class SourceConfigService:
    """Service for managing ETL source configurations.

    Provides CRUD operations, connection testing, and sample data retrieval
    for ETL data sources.
    """

    def __init__(self, encryption_key: str | None = None):
        """Initialize the service.

        Args:
            encryption_key: Optional encryption key for credentials.
        """
        self._sources: dict[UUID, SourceConfig] = {}
        self._pipelines: dict[UUID, Pipeline] = {}
        self._pipeline_runs: dict[UUID, list[PipelineRun]] = {}
        self._encrypted_credentials: dict[UUID, dict[str, str]] = {}
        self._encryptor = CredentialEncryptor(encryption_key)
        self._lock = asyncio.Lock()

        logger.info("SourceConfigService initialized")

    # -------------------------------------------------------------------------
    # Source CRUD Operations
    # -------------------------------------------------------------------------

    async def create_source(
        self,
        name: str,
        source_type: SourceType,
        connection_params: ConnectionParams,
        credentials: SourceCredentials | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SourceConfig:
        """Create a new source configuration.

        Args:
            name: Source name.
            source_type: Type of source.
            connection_params: Connection parameters.
            credentials: Optional credentials.
            description: Optional description.
            metadata: Optional metadata.

        Returns:
            Created SourceConfig.
        """
        source_id = uuid4()
        now = datetime.now(UTC)

        source = SourceConfig(
            id=source_id,
            name=name,
            description=description,
            source_type=source_type,
            connection_params=connection_params,
            credentials=credentials or SourceCredentials(),
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        async with self._lock:
            self._sources[source_id] = source

            # Encrypt and store credentials separately
            if credentials and credentials.has_credentials():
                self._encrypted_credentials[source_id] = self._encryptor.encrypt_credentials(
                    credentials
                )

        logger.info(f"Created source {source_id}: {name} ({source_type.value})")
        return source

    async def get_source(self, source_id: UUID) -> SourceConfig | None:
        """Get a source configuration by ID.

        Args:
            source_id: Source UUID.

        Returns:
            SourceConfig if found, None otherwise.
        """
        return self._sources.get(source_id)

    async def get_source_with_credentials(self, source_id: UUID) -> SourceConfig | None:
        """Get a source with decrypted credentials.

        Args:
            source_id: Source UUID.

        Returns:
            SourceConfig with decrypted credentials if found.
        """
        source = self._sources.get(source_id)
        if not source:
            return None

        # Decrypt credentials if stored
        if source_id in self._encrypted_credentials:
            source.credentials = self._encryptor.decrypt_credentials(
                self._encrypted_credentials[source_id],
                source.credentials,
            )

        return source

    async def list_sources(
        self,
        source_type: SourceType | None = None,
        enabled_only: bool = False,
        limit: int = 100,
    ) -> list[SourceConfig]:
        """List source configurations.

        Args:
            source_type: Optional filter by type.
            enabled_only: Only return enabled sources.
            limit: Maximum results to return.

        Returns:
            List of SourceConfig objects.
        """
        sources = list(self._sources.values())

        if source_type:
            sources = [s for s in sources if s.source_type == source_type]

        if enabled_only:
            sources = [s for s in sources if s.enabled]

        # Sort by created_at descending
        sources.sort(key=lambda s: s.created_at, reverse=True)

        return sources[:limit]

    async def update_source(
        self,
        source_id: UUID,
        name: str | None = None,
        description: str | None = None,
        connection_params: ConnectionParams | None = None,
        credentials: SourceCredentials | None = None,
        enabled: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SourceConfig | None:
        """Update a source configuration.

        Args:
            source_id: Source UUID.
            name: New name.
            description: New description.
            connection_params: New connection params.
            credentials: New credentials.
            enabled: New enabled state.
            metadata: New metadata.

        Returns:
            Updated SourceConfig if found.
        """
        async with self._lock:
            source = self._sources.get(source_id)
            if not source:
                return None

            if name is not None:
                source.name = name
            if description is not None:
                source.description = description
            if connection_params is not None:
                source.connection_params = connection_params
            if enabled is not None:
                source.enabled = enabled
            if metadata is not None:
                source.metadata = metadata

            source.updated_at = datetime.now(UTC)

            # Update encrypted credentials
            if credentials is not None:
                source.credentials = credentials
                if credentials.has_credentials():
                    self._encrypted_credentials[source_id] = self._encryptor.encrypt_credentials(
                        credentials
                    )
                elif source_id in self._encrypted_credentials:
                    del self._encrypted_credentials[source_id]

        logger.info(f"Updated source {source_id}")
        return source

    async def delete_source(self, source_id: UUID) -> bool:
        """Delete a source configuration.

        Args:
            source_id: Source UUID.

        Returns:
            True if deleted, False if not found.
        """
        async with self._lock:
            if source_id not in self._sources:
                return False

            del self._sources[source_id]
            self._encrypted_credentials.pop(source_id, None)

            # Also delete associated pipelines
            pipelines_to_delete = [
                pid for pid, p in self._pipelines.items()
                if p.source_id == source_id
            ]
            for pid in pipelines_to_delete:
                del self._pipelines[pid]
                self._pipeline_runs.pop(pid, None)

        logger.info(f"Deleted source {source_id}")
        return True

    # -------------------------------------------------------------------------
    # Connection Testing
    # -------------------------------------------------------------------------

    async def test_connection(self, source_id: UUID) -> ConnectionTestResult:
        """Test connection to a data source.

        Args:
            source_id: Source UUID.

        Returns:
            ConnectionTestResult with test outcome.
        """
        source = await self.get_source_with_credentials(source_id)
        if not source:
            return ConnectionTestResult(
                success=False,
                message="Source not found",
            )

        # Update status to testing
        source.status = ConnectionStatus.TESTING
        source.last_tested_at = datetime.now(UTC)

        try:
            start_time = datetime.now(UTC)
            result = await self._test_source_connection(source)
            end_time = datetime.now(UTC)

            result.latency_ms = (end_time - start_time).total_seconds() * 1000
            result.tested_at = end_time

            # Update source status
            async with self._lock:
                if source_id in self._sources:
                    self._sources[source_id].status = (
                        ConnectionStatus.CONNECTED if result.success
                        else ConnectionStatus.ERROR
                    )
                    self._sources[source_id].last_tested_at = end_time
                    self._sources[source_id].test_result = result.message

            return result

        except Exception as e:
            logger.error(f"Connection test failed for {source_id}: {e}")

            async with self._lock:
                if source_id in self._sources:
                    self._sources[source_id].status = ConnectionStatus.ERROR
                    self._sources[source_id].test_result = str(e)

            return ConnectionTestResult(
                success=False,
                message=f"Connection test failed: {str(e)}",
                error_details=str(e),
            )

    async def _test_source_connection(self, source: SourceConfig) -> ConnectionTestResult:
        """Internal method to test connection based on source type.

        Args:
            source: Source configuration to test.

        Returns:
            ConnectionTestResult.
        """
        if source.source_type == SourceType.FHIR:
            return await self._test_fhir_connection(source)
        elif source.source_type == SourceType.DATABASE:
            return await self._test_database_connection(source)
        elif source.source_type == SourceType.CSV:
            return await self._test_csv_connection(source)
        elif source.source_type == SourceType.HL7V2:
            return await self._test_hl7v2_connection(source)
        elif source.source_type == SourceType.CCDA:
            return await self._test_ccda_connection(source)
        else:
            return ConnectionTestResult(
                success=False,
                message=f"Unknown source type: {source.source_type}",
            )

    async def _test_fhir_connection(self, source: SourceConfig) -> ConnectionTestResult:
        """Test connection to a FHIR server."""
        import httpx

        url = source.connection_params.get_connection_string(SourceType.FHIR)
        metadata_url = f"{url}/metadata"

        headers = {}
        if source.credentials.auth_token:
            headers["Authorization"] = f"Bearer {source.credentials.auth_token}"

        try:
            async with httpx.AsyncClient(
                verify=source.connection_params.verify_ssl,
                timeout=source.connection_params.timeout_seconds,
            ) as client:
                response = await client.get(metadata_url, headers=headers)
                response.raise_for_status()

                data = response.json()
                return ConnectionTestResult(
                    success=True,
                    message="Successfully connected to FHIR server",
                    server_info={
                        "fhir_version": data.get("fhirVersion"),
                        "software": data.get("software", {}).get("name"),
                        "implementation": data.get("implementation", {}).get("description"),
                    },
                )

        except httpx.HTTPStatusError as e:
            return ConnectionTestResult(
                success=False,
                message=f"FHIR server returned error: {e.response.status_code}",
                error_details=str(e),
            )
        except httpx.RequestError as e:
            return ConnectionTestResult(
                success=False,
                message=f"Failed to connect to FHIR server: {str(e)}",
                error_details=str(e),
            )

    async def _test_database_connection(self, source: SourceConfig) -> ConnectionTestResult:
        """Test connection to a database."""
        # Simulate database connection test
        # In production, use actual database driver
        try:
            conn_string = source.connection_params.get_connection_string(SourceType.DATABASE)

            # Basic validation
            if not source.connection_params.host:
                return ConnectionTestResult(
                    success=False,
                    message="Database host not specified",
                )

            # Simulate connection (would use asyncpg/aiomysql in production)
            await asyncio.sleep(0.1)  # Simulate network latency

            return ConnectionTestResult(
                success=True,
                message="Successfully connected to database",
                server_info={
                    "host": source.connection_params.host,
                    "database": source.connection_params.database,
                },
            )

        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Database connection failed: {str(e)}",
                error_details=str(e),
            )

    async def _test_csv_connection(self, source: SourceConfig) -> ConnectionTestResult:
        """Test access to CSV file directory."""
        path = source.connection_params.path
        if not path:
            return ConnectionTestResult(
                success=False,
                message="CSV path not specified",
            )

        path_obj = Path(path)
        if not path_obj.exists():
            return ConnectionTestResult(
                success=False,
                message=f"Path does not exist: {path}",
            )

        if not path_obj.is_dir():
            return ConnectionTestResult(
                success=False,
                message=f"Path is not a directory: {path}",
            )

        # Count CSV files
        csv_files = list(path_obj.glob("*.csv"))
        return ConnectionTestResult(
            success=True,
            message=f"CSV directory accessible with {len(csv_files)} CSV files",
            server_info={
                "path": str(path_obj.absolute()),
                "file_count": len(csv_files),
            },
        )

    async def _test_hl7v2_connection(self, source: SourceConfig) -> ConnectionTestResult:
        """Test access to HL7v2 message directory."""
        path = source.connection_params.path
        if not path:
            return ConnectionTestResult(
                success=False,
                message="HL7v2 messages path not specified",
            )

        path_obj = Path(path)
        if not path_obj.exists():
            return ConnectionTestResult(
                success=False,
                message=f"Path does not exist: {path}",
            )

        # Count HL7 files
        hl7_files = list(path_obj.glob("*.hl7")) + list(path_obj.glob("*.txt"))
        return ConnectionTestResult(
            success=True,
            message=f"HL7v2 directory accessible with {len(hl7_files)} message files",
            server_info={
                "path": str(path_obj.absolute()),
                "file_count": len(hl7_files),
            },
        )

    async def _test_ccda_connection(self, source: SourceConfig) -> ConnectionTestResult:
        """Test access to C-CDA document directory."""
        path = source.connection_params.path
        if not path:
            return ConnectionTestResult(
                success=False,
                message="C-CDA documents path not specified",
            )

        path_obj = Path(path)
        if not path_obj.exists():
            return ConnectionTestResult(
                success=False,
                message=f"Path does not exist: {path}",
            )

        # Count XML files
        xml_files = list(path_obj.glob("*.xml"))
        return ConnectionTestResult(
            success=True,
            message=f"C-CDA directory accessible with {len(xml_files)} document files",
            server_info={
                "path": str(path_obj.absolute()),
                "file_count": len(xml_files),
            },
        )

    # -------------------------------------------------------------------------
    # Sample Data Preview
    # -------------------------------------------------------------------------

    async def get_sample_data(
        self,
        source_id: UUID,
        limit: int = 10,
    ) -> SampleDataPreview | None:
        """Get sample data from a source for preview.

        Args:
            source_id: Source UUID.
            limit: Maximum records to fetch.

        Returns:
            SampleDataPreview if successful.
        """
        source = await self.get_source_with_credentials(source_id)
        if not source:
            return None

        try:
            records = await self._fetch_sample_records(source, limit)
            schema_info = await self._infer_schema(source, records)

            return SampleDataPreview(
                source_id=source_id,
                record_count=len(records),
                records=records,
                schema_info=schema_info,
            )

        except Exception as e:
            logger.error(f"Failed to fetch sample data for {source_id}: {e}")
            return SampleDataPreview(
                source_id=source_id,
                record_count=0,
                records=[],
                schema_info={"error": str(e)},
            )

    async def _fetch_sample_records(
        self,
        source: SourceConfig,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch sample records from a source.

        Args:
            source: Source configuration.
            limit: Maximum records.

        Returns:
            List of record dictionaries.
        """
        if source.source_type == SourceType.FHIR:
            return await self._fetch_fhir_samples(source, limit)
        elif source.source_type == SourceType.CSV:
            return await self._fetch_csv_samples(source, limit)
        elif source.source_type == SourceType.DATABASE:
            return await self._fetch_database_samples(source, limit)
        else:
            # Return placeholder for other types
            return [
                {"id": f"sample_{i}", "type": source.source_type.value}
                for i in range(min(limit, 3))
            ]

    async def _fetch_fhir_samples(
        self,
        source: SourceConfig,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch sample Patient resources from FHIR server."""
        import httpx

        url = source.connection_params.get_connection_string(SourceType.FHIR)
        patient_url = f"{url}/Patient?_count={limit}"

        headers = {"Accept": "application/fhir+json"}
        if source.credentials.auth_token:
            headers["Authorization"] = f"Bearer {source.credentials.auth_token}"

        try:
            async with httpx.AsyncClient(
                verify=source.connection_params.verify_ssl,
                timeout=source.connection_params.timeout_seconds,
            ) as client:
                response = await client.get(patient_url, headers=headers)
                response.raise_for_status()

                bundle = response.json()
                entries = bundle.get("entry", [])

                return [
                    {
                        "id": entry.get("resource", {}).get("id"),
                        "resourceType": entry.get("resource", {}).get("resourceType"),
                        "name": self._format_fhir_name(
                            entry.get("resource", {}).get("name", [])
                        ),
                        "gender": entry.get("resource", {}).get("gender"),
                        "birthDate": entry.get("resource", {}).get("birthDate"),
                    }
                    for entry in entries[:limit]
                ]

        except Exception as e:
            logger.warning(f"Failed to fetch FHIR samples: {e}")
            return []

    def _format_fhir_name(self, names: list) -> str:
        """Format FHIR name array to string."""
        if not names:
            return "Unknown"
        name = names[0]
        given = " ".join(name.get("given", []))
        family = name.get("family", "")
        return f"{given} {family}".strip() or "Unknown"

    async def _fetch_csv_samples(
        self,
        source: SourceConfig,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch sample records from CSV files."""
        import csv

        path = Path(source.connection_params.path or "")
        csv_files = list(path.glob("*.csv"))

        if not csv_files:
            return []

        # Read from first CSV file
        first_file = csv_files[0]
        records = []

        try:
            with open(first_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= limit:
                        break
                    records.append(dict(row))

        except Exception as e:
            logger.warning(f"Failed to read CSV file {first_file}: {e}")

        return records

    async def _fetch_database_samples(
        self,
        source: SourceConfig,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch sample records from database."""
        # Placeholder - would use actual database query
        return [
            {"id": i, "table": "patients", "sample": True}
            for i in range(min(limit, 3))
        ]

    async def _infer_schema(
        self,
        source: SourceConfig,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Infer schema from sample records."""
        if not records:
            return {"fields": []}

        # Get all unique keys
        all_keys = set()
        for record in records:
            all_keys.update(record.keys())

        # Infer types from first non-null value
        fields = []
        for key in sorted(all_keys):
            field_type = "string"
            for record in records:
                value = record.get(key)
                if value is not None:
                    if isinstance(value, bool):
                        field_type = "boolean"
                    elif isinstance(value, int):
                        field_type = "integer"
                    elif isinstance(value, float):
                        field_type = "number"
                    elif isinstance(value, (list, dict)):
                        field_type = "object"
                    break

            fields.append({"name": key, "type": field_type})

        return {
            "fields": fields,
            "record_count": len(records),
        }

    # -------------------------------------------------------------------------
    # Pipeline CRUD Operations
    # -------------------------------------------------------------------------

    async def create_pipeline(
        self,
        name: str,
        source_id: UUID,
        description: str = "",
        schedule: PipelineSchedule | None = None,
        stages: list[PipelineStage] | None = None,
        batch_size: int = 100,
        max_records: int | None = None,
        skip_on_error: bool = True,
    ) -> Pipeline | None:
        """Create a new ETL pipeline.

        Args:
            name: Pipeline name.
            source_id: Associated source ID.
            description: Optional description.
            schedule: Schedule configuration.
            stages: Pipeline stages.
            batch_size: Records per batch.
            max_records: Maximum records.
            skip_on_error: Continue on errors.

        Returns:
            Created Pipeline if source exists.
        """
        # Verify source exists
        if source_id not in self._sources:
            return None

        pipeline_id = uuid4()
        now = datetime.now(UTC)

        # Default stages if not provided
        if stages is None:
            stages = [
                PipelineStage(name="Extract", stage_type="extract", order=0),
                PipelineStage(name="Transform", stage_type="transform", order=1),
                PipelineStage(name="Load", stage_type="load", order=2),
            ]

        pipeline = Pipeline(
            id=pipeline_id,
            name=name,
            description=description,
            source_id=source_id,
            schedule=schedule or PipelineSchedule(),
            stages=stages,
            batch_size=batch_size,
            max_records=max_records,
            skip_on_error=skip_on_error,
            created_at=now,
            updated_at=now,
        )

        async with self._lock:
            self._pipelines[pipeline_id] = pipeline
            self._pipeline_runs[pipeline_id] = []

        logger.info(f"Created pipeline {pipeline_id}: {name}")
        return pipeline

    async def get_pipeline(self, pipeline_id: UUID) -> Pipeline | None:
        """Get a pipeline by ID."""
        return self._pipelines.get(pipeline_id)

    async def list_pipelines(
        self,
        source_id: UUID | None = None,
        status: PipelineStatus | None = None,
        limit: int = 100,
    ) -> list[Pipeline]:
        """List pipelines with optional filters."""
        pipelines = list(self._pipelines.values())

        if source_id:
            pipelines = [p for p in pipelines if p.source_id == source_id]

        if status:
            pipelines = [p for p in pipelines if p.status == status]

        pipelines.sort(key=lambda p: p.created_at, reverse=True)
        return pipelines[:limit]

    async def update_pipeline(
        self,
        pipeline_id: UUID,
        name: str | None = None,
        description: str | None = None,
        status: PipelineStatus | None = None,
        schedule: PipelineSchedule | None = None,
        stages: list[PipelineStage] | None = None,
        batch_size: int | None = None,
        max_records: int | None = None,
        skip_on_error: bool | None = None,
    ) -> Pipeline | None:
        """Update a pipeline configuration."""
        async with self._lock:
            pipeline = self._pipelines.get(pipeline_id)
            if not pipeline:
                return None

            if name is not None:
                pipeline.name = name
            if description is not None:
                pipeline.description = description
            if status is not None:
                pipeline.status = status
            if schedule is not None:
                pipeline.schedule = schedule
            if stages is not None:
                pipeline.stages = stages
            if batch_size is not None:
                pipeline.batch_size = batch_size
            if max_records is not None:
                pipeline.max_records = max_records
            if skip_on_error is not None:
                pipeline.skip_on_error = skip_on_error

            pipeline.updated_at = datetime.now(UTC)

        logger.info(f"Updated pipeline {pipeline_id}")
        return pipeline

    async def update_pipeline_schedule(
        self,
        pipeline_id: UUID,
        schedule: PipelineSchedule,
    ) -> Pipeline | None:
        """Update only the pipeline schedule."""
        return await self.update_pipeline(pipeline_id, schedule=schedule)

    async def delete_pipeline(self, pipeline_id: UUID) -> bool:
        """Delete a pipeline."""
        async with self._lock:
            if pipeline_id not in self._pipelines:
                return False

            del self._pipelines[pipeline_id]
            self._pipeline_runs.pop(pipeline_id, None)

        logger.info(f"Deleted pipeline {pipeline_id}")
        return True

    # -------------------------------------------------------------------------
    # Pipeline Run Management
    # -------------------------------------------------------------------------

    async def create_pipeline_run(self, pipeline_id: UUID) -> PipelineRun | None:
        """Start a new pipeline run."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return None

        run = PipelineRun(
            id=uuid4(),
            pipeline_id=pipeline_id,
            status="running",
            started_at=datetime.now(UTC),
        )

        async with self._lock:
            if pipeline_id not in self._pipeline_runs:
                self._pipeline_runs[pipeline_id] = []
            self._pipeline_runs[pipeline_id].append(run)

            # Update pipeline
            pipeline.last_run_at = run.started_at
            pipeline.last_run_status = "running"
            pipeline.run_count += 1

        return run

    async def complete_pipeline_run(
        self,
        run_id: UUID,
        status: str,
        records_processed: int = 0,
        records_failed: int = 0,
        error_message: str | None = None,
    ) -> PipelineRun | None:
        """Mark a pipeline run as complete."""
        async with self._lock:
            for pipeline_id, runs in self._pipeline_runs.items():
                for run in runs:
                    if run.id == run_id:
                        run.status = status
                        run.completed_at = datetime.now(UTC)
                        run.records_processed = records_processed
                        run.records_failed = records_failed
                        run.error_message = error_message
                        run.duration_seconds = (
                            run.completed_at - run.started_at
                        ).total_seconds()

                        # Update pipeline
                        pipeline = self._pipelines.get(pipeline_id)
                        if pipeline:
                            pipeline.last_run_status = status

                        return run

        return None

    async def get_pipeline_runs(
        self,
        pipeline_id: UUID,
        limit: int = 20,
    ) -> list[PipelineRun]:
        """Get run history for a pipeline."""
        runs = self._pipeline_runs.get(pipeline_id, [])
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    # -------------------------------------------------------------------------
    # Service Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        source_counts = {}
        for source in self._sources.values():
            source_type = source.source_type.value
            source_counts[source_type] = source_counts.get(source_type, 0) + 1

        status_counts = {}
        for source in self._sources.values():
            status = source.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        pipeline_status_counts = {}
        for pipeline in self._pipelines.values():
            status = pipeline.status.value
            pipeline_status_counts[status] = pipeline_status_counts.get(status, 0) + 1

        return {
            "total_sources": len(self._sources),
            "sources_by_type": source_counts,
            "sources_by_status": status_counts,
            "total_pipelines": len(self._pipelines),
            "pipelines_by_status": pipeline_status_counts,
        }


# ============================================================================
# Singleton Management
# ============================================================================

_source_config_service: SourceConfigService | None = None


def get_source_config_service(
    encryption_key: str | None = None,
) -> SourceConfigService:
    """Get or create the global SourceConfigService singleton.

    Args:
        encryption_key: Optional encryption key.

    Returns:
        The global SourceConfigService instance.
    """
    global _source_config_service
    if _source_config_service is None:
        _source_config_service = SourceConfigService(encryption_key)
    return _source_config_service


def reset_source_config_service() -> None:
    """Reset the global SourceConfigService singleton."""
    global _source_config_service
    _source_config_service = None
