"""
Data Source Service

Service for managing external data source connections.
Handles CRUD operations, connection testing, and health monitoring.
"""

import asyncio
import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.data_source import (
    AuthMethod,
    DataSource,
    DataSourceType,
    HealthStatus,
)

logger = logging.getLogger(__name__)


# Generate a stable encryption key from JWT secret
def _get_encryption_key() -> bytes:
    """Derive encryption key from app secret."""
    key_material = settings.jwt_secret_key.encode()
    # Use SHA256 to get 32 bytes, then base64 encode for Fernet
    digest = hashlib.sha256(key_material).digest()
    return base64.urlsafe_b64encode(digest)


_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Get Fernet instance for credential encryption."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_encryption_key())
    return _fernet


def encrypt_value(value: str) -> str:
    """Encrypt a sensitive value."""
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt a sensitive value."""
    return get_fernet().decrypt(encrypted.encode()).decode()


# Pydantic models for API
class DataSourceCreate(BaseModel):
    """Request model for creating a data source."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_type: DataSourceType
    auth_method: AuthMethod = AuthMethod.NONE

    # Connection details
    base_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  # Will be encrypted
    api_key: Optional[str] = None  # Will be encrypted
    username: Optional[str] = None
    password: Optional[str] = None  # Will be encrypted
    token_url: Optional[str] = None
    scopes: list[str] = Field(default_factory=list)

    # Settings
    timeout_seconds: int = 30
    verify_ssl: bool = True
    default_batch_size: int = 100
    default_retry_count: int = 3


class DataSourceUpdate(BaseModel):
    """Request model for updating a data source."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    auth_method: Optional[AuthMethod] = None
    is_active: Optional[bool] = None

    # Connection details (only update if provided)
    base_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token_url: Optional[str] = None
    scopes: Optional[list[str]] = None

    # Settings
    timeout_seconds: Optional[int] = None
    verify_ssl: Optional[bool] = None
    default_batch_size: Optional[int] = None
    default_retry_count: Optional[int] = None


class DataSourceResponse(BaseModel):
    """Response model for data source."""
    id: UUID
    name: str
    description: Optional[str]
    source_type: DataSourceType
    auth_method: AuthMethod
    is_active: bool
    health_status: HealthStatus
    last_health_check_at: Optional[datetime]
    last_health_message: Optional[str]
    last_connected_at: Optional[datetime]
    total_records_imported: int
    default_batch_size: int
    default_timeout_seconds: int
    default_retry_count: int
    created_at: datetime
    updated_at: datetime

    # Connection details (secrets masked)
    base_url: Optional[str] = None
    client_id: Optional[str] = None
    has_client_secret: bool = False
    has_api_key: bool = False
    token_url: Optional[str] = None
    scopes: list[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    verify_ssl: bool = True

    class Config:
        from_attributes = True


class ConnectionTestResult(BaseModel):
    """Result of testing a data source connection."""
    success: bool
    message: str
    latency_ms: Optional[int] = None
    server_info: Optional[dict] = None
    error_details: Optional[str] = None


class DataSourceService:
    """Service for managing data sources."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        data: DataSourceCreate,
        created_by: Optional[UUID] = None,
    ) -> DataSource:
        """Create a new data source."""
        # Build connection config with encrypted secrets
        connection_config = self._build_connection_config(data)

        source = DataSource(
            name=data.name,
            description=data.description,
            source_type=data.source_type,
            auth_method=data.auth_method,
            connection_config=connection_config,
            default_batch_size=data.default_batch_size,
            default_timeout_seconds=data.timeout_seconds,
            default_retry_count=data.default_retry_count,
            created_by=created_by,
        )

        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)

        logger.info(f"Created data source: {source.id} ({source.name})")
        return source

    async def get(self, source_id: UUID) -> Optional[DataSource]:
        """Get a data source by ID."""
        result = await self.db.execute(
            select(DataSource).where(DataSource.id == source_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        source_type: Optional[DataSourceType] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DataSource]:
        """List data sources with optional filtering."""
        query = select(DataSource)

        if source_type is not None:
            query = query.where(DataSource.source_type == source_type)
        if is_active is not None:
            query = query.where(DataSource.is_active == is_active)

        query = query.order_by(DataSource.name).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        source_id: UUID,
        data: DataSourceUpdate,
    ) -> Optional[DataSource]:
        """Update a data source."""
        source = await self.get(source_id)
        if not source:
            return None

        # Update basic fields
        if data.name is not None:
            source.name = data.name
        if data.description is not None:
            source.description = data.description
        if data.auth_method is not None:
            source.auth_method = data.auth_method
        if data.is_active is not None:
            source.is_active = data.is_active

        # Update settings
        if data.default_batch_size is not None:
            source.default_batch_size = data.default_batch_size
        if data.default_retry_count is not None:
            source.default_retry_count = data.default_retry_count

        # Update connection config
        config = dict(source.connection_config) if source.connection_config else {}

        if data.base_url is not None:
            config["base_url"] = data.base_url
        if data.client_id is not None:
            config["client_id"] = data.client_id
        if data.client_secret is not None:
            config["client_secret_encrypted"] = encrypt_value(data.client_secret)
        if data.api_key is not None:
            config["api_key_encrypted"] = encrypt_value(data.api_key)
        if data.username is not None:
            config["username"] = data.username
        if data.password is not None:
            config["password_encrypted"] = encrypt_value(data.password)
        if data.token_url is not None:
            config["token_url"] = data.token_url
        if data.scopes is not None:
            config["scopes"] = data.scopes
        if data.timeout_seconds is not None:
            config["timeout_seconds"] = data.timeout_seconds
            source.default_timeout_seconds = data.timeout_seconds
        if data.verify_ssl is not None:
            config["verify_ssl"] = data.verify_ssl

        source.connection_config = config

        await self.db.commit()
        await self.db.refresh(source)

        logger.info(f"Updated data source: {source_id}")
        return source

    async def delete(self, source_id: UUID) -> bool:
        """Delete a data source."""
        source = await self.get(source_id)
        if not source:
            return False

        await self.db.delete(source)
        await self.db.commit()

        logger.info(f"Deleted data source: {source_id}")
        return True

    async def test_connection(self, source_id: UUID) -> ConnectionTestResult:
        """Test connection to a data source."""
        source = await self.get(source_id)
        if not source:
            return ConnectionTestResult(
                success=False,
                message="Data source not found",
            )

        try:
            start_time = asyncio.get_event_loop().time()

            if source.source_type == DataSourceType.FHIR_SERVER:
                result = await self._test_fhir_connection(source)
            elif source.source_type in (DataSourceType.HIE, DataSourceType.AGGREGATOR):
                result = await self._test_api_connection(source)
            else:
                result = ConnectionTestResult(
                    success=True,
                    message=f"Connection test not implemented for {source.source_type.value}",
                )

            latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            result.latency_ms = latency_ms

            # Update health status
            await self._update_health_status(
                source_id,
                HealthStatus.HEALTHY if result.success else HealthStatus.OFFLINE,
                result.message,
            )

            return result

        except Exception as e:
            logger.error(f"Connection test failed for {source_id}: {e}")
            await self._update_health_status(
                source_id,
                HealthStatus.OFFLINE,
                str(e),
            )
            return ConnectionTestResult(
                success=False,
                message="Connection test failed",
                error_details=str(e),
            )

    async def _test_fhir_connection(self, source: DataSource) -> ConnectionTestResult:
        """Test connection to a FHIR server."""
        config = source.connection_config or {}
        base_url = config.get("base_url")

        if not base_url:
            return ConnectionTestResult(
                success=False,
                message="No base URL configured",
            )

        # Build headers
        headers = {"Accept": "application/fhir+json"}
        headers = await self._add_auth_headers(source, headers)

        timeout = config.get("timeout_seconds", 30)
        verify_ssl = config.get("verify_ssl", True)

        async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
            # Test metadata endpoint
            response = await client.get(
                f"{base_url.rstrip('/')}/metadata",
                headers=headers,
            )

            if response.status_code == 200:
                try:
                    metadata = response.json()
                    server_info = {
                        "fhir_version": metadata.get("fhirVersion"),
                        "software": metadata.get("software", {}).get("name"),
                        "implementation": metadata.get("implementation", {}).get("description"),
                    }
                    return ConnectionTestResult(
                        success=True,
                        message="Connected successfully",
                        server_info=server_info,
                    )
                except Exception:
                    return ConnectionTestResult(
                        success=True,
                        message="Connected but could not parse metadata",
                    )
            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"Server returned status {response.status_code}",
                    error_details=response.text[:500] if response.text else None,
                )

    async def _test_api_connection(self, source: DataSource) -> ConnectionTestResult:
        """Test connection to a generic API (HIE, aggregator)."""
        config = source.connection_config or {}
        base_url = config.get("base_url")

        if not base_url:
            return ConnectionTestResult(
                success=False,
                message="No base URL configured",
            )

        headers = {"Accept": "application/json"}
        headers = await self._add_auth_headers(source, headers)

        timeout = config.get("timeout_seconds", 30)
        verify_ssl = config.get("verify_ssl", True)

        async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
            # Try a health check endpoint
            for endpoint in ["/health", "/api/health", "/status", "/"]:
                try:
                    response = await client.get(
                        f"{base_url.rstrip('/')}{endpoint}",
                        headers=headers,
                    )
                    if response.status_code < 400:
                        return ConnectionTestResult(
                            success=True,
                            message=f"Connected successfully via {endpoint}",
                        )
                except Exception:
                    continue

            return ConnectionTestResult(
                success=False,
                message="Could not connect to any health endpoint",
            )

    async def _add_auth_headers(
        self,
        source: DataSource,
        headers: dict,
    ) -> dict:
        """Add authentication headers based on auth method."""
        config = source.connection_config or {}

        if source.auth_method == AuthMethod.BEARER_TOKEN:
            api_key = config.get("api_key_encrypted")
            if api_key:
                headers["Authorization"] = f"Bearer {decrypt_value(api_key)}"

        elif source.auth_method == AuthMethod.API_KEY:
            api_key = config.get("api_key_encrypted")
            if api_key:
                headers["X-API-Key"] = decrypt_value(api_key)

        elif source.auth_method == AuthMethod.BASIC:
            username = config.get("username")
            password_enc = config.get("password_encrypted")
            if username and password_enc:
                import base64
                password = decrypt_value(password_enc)
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"

        elif source.auth_method == AuthMethod.OAUTH2_CLIENT_CREDENTIALS:
            # Get token from token endpoint
            token = await self._get_oauth2_token(source)
            if token:
                headers["Authorization"] = f"Bearer {token}"

        return headers

    async def _get_oauth2_token(self, source: DataSource) -> Optional[str]:
        """Get OAuth2 access token using client credentials."""
        config = source.connection_config or {}

        token_url = config.get("token_url")
        client_id = config.get("client_id")
        client_secret_enc = config.get("client_secret_encrypted")

        if not all([token_url, client_id, client_secret_enc]):
            return None

        client_secret = decrypt_value(client_secret_enc)
        scopes = config.get("scopes", [])

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": " ".join(scopes) if scopes else None,
                },
            )

            if response.status_code == 200:
                return response.json().get("access_token")

        return None

    async def _update_health_status(
        self,
        source_id: UUID,
        status: HealthStatus,
        message: str,
    ) -> None:
        """Update health status of a data source."""
        await self.db.execute(
            update(DataSource)
            .where(DataSource.id == source_id)
            .values(
                health_status=status,
                last_health_check_at=datetime.now(timezone.utc),
                last_health_message=message,
            )
        )
        await self.db.commit()

    def _build_connection_config(self, data: DataSourceCreate) -> dict:
        """Build connection config dict with encrypted secrets."""
        config = {
            "timeout_seconds": data.timeout_seconds,
            "verify_ssl": data.verify_ssl,
        }

        if data.base_url:
            config["base_url"] = data.base_url
        if data.client_id:
            config["client_id"] = data.client_id
        if data.client_secret:
            config["client_secret_encrypted"] = encrypt_value(data.client_secret)
        if data.api_key:
            config["api_key_encrypted"] = encrypt_value(data.api_key)
        if data.username:
            config["username"] = data.username
        if data.password:
            config["password_encrypted"] = encrypt_value(data.password)
        if data.token_url:
            config["token_url"] = data.token_url
        if data.scopes:
            config["scopes"] = data.scopes

        return config

    def to_response(self, source: DataSource) -> DataSourceResponse:
        """Convert DataSource model to response model."""
        config = source.connection_config or {}

        return DataSourceResponse(
            id=source.id,
            name=source.name,
            description=source.description,
            source_type=source.source_type,
            auth_method=source.auth_method,
            is_active=source.is_active,
            health_status=source.health_status,
            last_health_check_at=source.last_health_check_at,
            last_health_message=source.last_health_message,
            last_connected_at=source.last_connected_at,
            total_records_imported=source.total_records_imported,
            default_batch_size=source.default_batch_size,
            default_timeout_seconds=source.default_timeout_seconds,
            default_retry_count=source.default_retry_count,
            created_at=source.created_at,
            updated_at=source.updated_at,
            base_url=config.get("base_url"),
            client_id=config.get("client_id"),
            has_client_secret=bool(config.get("client_secret_encrypted")),
            has_api_key=bool(config.get("api_key_encrypted")),
            token_url=config.get("token_url"),
            scopes=config.get("scopes", []),
            timeout_seconds=config.get("timeout_seconds", 30),
            verify_ssl=config.get("verify_ssl", True),
        )
