"""Pydantic schemas for API Versioning and Deprecation Policy (CTO-8).

Provides models for API version lifecycle management, endpoint versioning,
breaking change detection, migration guide generation, and client usage tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class APIVersionStatus(str, Enum):
    """Lifecycle status of an API version."""

    CURRENT = "CURRENT"
    DEPRECATED = "DEPRECATED"
    SUNSET = "SUNSET"
    RETIRED = "RETIRED"


class BreakingChangeType(str, Enum):
    """Types of breaking changes between API versions."""

    ENDPOINT_REMOVED = "ENDPOINT_REMOVED"
    REQUEST_SCHEMA_CHANGED = "REQUEST_SCHEMA_CHANGED"
    RESPONSE_SCHEMA_CHANGED = "RESPONSE_SCHEMA_CHANGED"
    STATUS_CODE_CHANGED = "STATUS_CODE_CHANGED"
    AUTH_REQUIREMENT_CHANGED = "AUTH_REQUIREMENT_CHANGED"
    HTTP_METHOD_CHANGED = "HTTP_METHOD_CHANGED"
    PARAMETER_TYPE_CHANGED = "PARAMETER_TYPE_CHANGED"


class ChangeCategory(str, Enum):
    """Category of change: breaking or non-breaking."""

    BREAKING = "BREAKING"
    NON_BREAKING = "NON_BREAKING"


# ---------------------------------------------------------------------------
# API Version Record
# ---------------------------------------------------------------------------


class APIVersionRecord(BaseModel):
    """Full record of an API version with lifecycle dates."""

    version: str = Field(
        description="Version identifier (e.g., v1, v2)",
    )
    status: APIVersionStatus = Field(
        description="Current lifecycle status",
    )
    release_date: datetime = Field(
        description="Date the version was released",
    )
    deprecation_date: datetime | None = Field(
        default=None,
        description="Date the version was marked deprecated (must be >= 6 months before sunset)",
    )
    sunset_date: datetime | None = Field(
        default=None,
        description="Date the version entered sunset (read-only) mode",
    )
    retirement_date: datetime | None = Field(
        default=None,
        description="Date the version was fully retired and removed",
    )
    changelog: list[str] = Field(
        default_factory=list,
        description="List of notable changes in this version",
    )
    supported_until: datetime | None = Field(
        default=None,
        description="Projected end-of-support date",
    )

    model_config = {"from_attributes": True}


class APIVersionListResponse(BaseModel):
    """Response containing all API versions."""

    versions: list[APIVersionRecord] = Field(
        description="All registered API versions",
    )
    current_version: str = Field(
        description="The current active version",
    )
    total: int = Field(
        description="Total number of versions",
    )


# ---------------------------------------------------------------------------
# Endpoint Versioning
# ---------------------------------------------------------------------------


class EndpointVersionInfo(BaseModel):
    """Per-endpoint version and deprecation tracking."""

    endpoint_path: str = Field(
        description="API endpoint path (e.g., /api/v1/patients)",
    )
    http_method: str = Field(
        description="HTTP method (GET, POST, PUT, DELETE, PATCH)",
    )
    introduced_in: str = Field(
        description="Version this endpoint was introduced in",
    )
    deprecated_in: str | None = Field(
        default=None,
        description="Version this endpoint was deprecated in",
    )
    removed_in: str | None = Field(
        default=None,
        description="Version this endpoint was removed in",
    )
    replacement_path: str | None = Field(
        default=None,
        description="Replacement endpoint path if deprecated",
    )
    replacement_method: str | None = Field(
        default=None,
        description="HTTP method for the replacement endpoint",
    )
    deprecation_reason: str | None = Field(
        default=None,
        description="Reason for deprecation",
    )
    sunset_date: datetime | None = Field(
        default=None,
        description="Date this endpoint will stop serving requests",
    )

    model_config = {"from_attributes": True}


class EndpointVersionListResponse(BaseModel):
    """List of endpoint version info for a specific API version."""

    version: str = Field(description="The API version these endpoints belong to")
    endpoints: list[EndpointVersionInfo] = Field(
        description="Endpoints in this version",
    )
    total: int = Field(description="Total number of endpoints")
    deprecated_count: int = Field(
        default=0,
        description="Number of deprecated endpoints in this version",
    )


class DeprecatedEndpointResponse(BaseModel):
    """All deprecated endpoints across all versions."""

    endpoints: list[EndpointVersionInfo] = Field(
        description="All deprecated endpoints",
    )
    total: int = Field(description="Total number of deprecated endpoints")


# ---------------------------------------------------------------------------
# Deprecation Response Headers
# ---------------------------------------------------------------------------


class DeprecationHeaders(BaseModel):
    """HTTP headers to inject for deprecated endpoints (RFC 8594)."""

    deprecation: str | None = Field(
        default=None,
        description="Deprecation header value (RFC 8594 date format)",
    )
    sunset: str | None = Field(
        default=None,
        description="Sunset header value (HTTP date format)",
    )
    link: str | None = Field(
        default=None,
        description="Link header pointing to replacement endpoint",
    )


# ---------------------------------------------------------------------------
# Breaking Change Detection
# ---------------------------------------------------------------------------


class BreakingChange(BaseModel):
    """A single detected breaking change between two API versions."""

    change_type: BreakingChangeType = Field(
        description="Type of breaking change detected",
    )
    endpoint_path: str = Field(
        description="Affected endpoint path",
    )
    http_method: str = Field(
        default="GET",
        description="HTTP method of the affected endpoint",
    )
    description: str = Field(
        description="Human-readable description of the change",
    )
    severity: str = Field(
        default="HIGH",
        description="Severity: LOW, MEDIUM, HIGH, CRITICAL",
    )


class BreakingChangeRequest(BaseModel):
    """Request to check for breaking changes between two versions."""

    from_version: str = Field(
        description="Source version to compare from",
    )
    to_version: str = Field(
        description="Target version to compare to",
    )


class BreakingChangeReport(BaseModel):
    """Report of breaking changes between two API versions."""

    from_version: str = Field(description="Source version")
    to_version: str = Field(description="Target version")
    breaking_changes: list[BreakingChange] = Field(
        default_factory=list,
        description="List of detected breaking changes",
    )
    non_breaking_changes: list[str] = Field(
        default_factory=list,
        description="List of non-breaking changes (additions, etc.)",
    )
    is_compatible: bool = Field(
        description="Whether the versions are backward compatible",
    )
    total_breaking: int = Field(
        default=0,
        description="Total number of breaking changes",
    )
    total_non_breaking: int = Field(
        default=0,
        description="Total number of non-breaking changes",
    )
    recommendation: str = Field(
        default="",
        description="Recommendation for version transition",
    )


# ---------------------------------------------------------------------------
# Migration Guide
# ---------------------------------------------------------------------------


class MigrationStep(BaseModel):
    """A single step in a migration guide."""

    step_number: int = Field(description="Step order number")
    action: str = Field(description="Action to take")
    old_endpoint: str | None = Field(
        default=None, description="Old endpoint being replaced"
    )
    new_endpoint: str | None = Field(
        default=None, description="New replacement endpoint"
    )
    code_example: str | None = Field(
        default=None, description="Example code snippet for the migration"
    )
    notes: str | None = Field(
        default=None, description="Additional notes"
    )


class MigrationGuide(BaseModel):
    """Migration guide for transitioning between API versions."""

    from_version: str = Field(description="Source version to migrate from")
    to_version: str = Field(description="Target version to migrate to")
    title: str = Field(description="Guide title")
    summary: str = Field(description="Executive summary of the migration")
    estimated_effort: str = Field(
        default="LOW",
        description="Estimated effort: LOW, MEDIUM, HIGH",
    )
    steps: list[MigrationStep] = Field(
        default_factory=list,
        description="Ordered migration steps",
    )
    breaking_changes_count: int = Field(
        default=0,
        description="Number of breaking changes to address",
    )
    deprecation_warnings: list[str] = Field(
        default_factory=list,
        description="Deprecation warnings to consider",
    )
    rollback_instructions: str | None = Field(
        default=None,
        description="Instructions for rolling back the migration",
    )


# ---------------------------------------------------------------------------
# Client Usage Tracking
# ---------------------------------------------------------------------------


class ClientUsageRecord(BaseModel):
    """Tracks which API version a client is using."""

    client_id: str = Field(description="Unique client identifier")
    api_version: str = Field(description="API version the client is using")
    last_seen: datetime = Field(description="Last time this client was seen")
    request_count: int = Field(
        default=0,
        description="Total number of requests from this client",
    )
    first_seen: datetime = Field(description="First time this client was seen")
    using_deprecated: bool = Field(
        default=False,
        description="Whether the client is using a deprecated version",
    )


class ClientUsageResponse(BaseModel):
    """Response containing client usage statistics."""

    clients: list[ClientUsageRecord] = Field(
        description="Client usage records",
    )
    total_clients: int = Field(description="Total number of tracked clients")
    clients_on_deprecated: int = Field(
        default=0,
        description="Number of clients on deprecated versions",
    )
    clients_on_current: int = Field(
        default=0,
        description="Number of clients on the current version",
    )
    version_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of clients across versions",
    )


# ---------------------------------------------------------------------------
# Deprecation Policy
# ---------------------------------------------------------------------------


class DeprecationPolicy(BaseModel):
    """Current deprecation policy configuration."""

    minimum_deprecation_notice_days: int = Field(
        default=180,
        description="Minimum days of deprecation notice before sunset (6 months)",
    )
    minimum_sunset_period_days: int = Field(
        default=90,
        description="Minimum days of sunset period before retirement (3 months)",
    )
    breaking_change_requires_new_version: bool = Field(
        default=True,
        description="Whether breaking changes require a new major version",
    )
    non_breaking_additions_allowed: bool = Field(
        default=True,
        description="Whether non-breaking additions are allowed within current version",
    )
    sunset_mode_read_only: bool = Field(
        default=True,
        description="Whether sunset versions are read-only (no writes)",
    )
    versioning_strategy: str = Field(
        default="URI",
        description="Versioning strategy: URI (/api/v1/), Header, Query",
    )
    version_format: str = Field(
        default="v{major}",
        description="Version format pattern",
    )
    notification_channels: list[str] = Field(
        default_factory=lambda: ["response_headers", "changelog", "developer_portal"],
        description="Channels used to communicate deprecation notices",
    )
    policy_version: str = Field(
        default="1.0",
        description="Version of this deprecation policy",
    )
    last_updated: datetime | None = Field(
        default=None,
        description="When this policy was last updated",
    )
