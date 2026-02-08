"""Pydantic schemas for API contract stability (CTO-5).

Defines the data models for capturing, comparing, and reporting on
API contract snapshots. Used to detect breaking changes before deployment.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    """Severity classification for a contract change."""

    BREAKING = "BREAKING"
    NON_BREAKING = "NON_BREAKING"
    INFO = "INFO"


class EndpointContract(BaseModel):
    """Contract definition for a single API endpoint.

    Captures all externally-visible properties of an endpoint that
    consumers depend on: path, method, schemas, parameters, and auth.
    """

    path: str = Field(..., description="URL path (e.g. /api/v1/patients)")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    request_schema: dict[str, Any] | None = Field(
        None, description="JSON Schema of the request body"
    )
    response_schema: dict[str, Any] | None = Field(
        None, description="JSON Schema of the primary response model"
    )
    query_params: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Query parameter definitions",
    )
    path_params: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Path parameter definitions",
    )
    auth_required: bool = Field(
        False, description="Whether the endpoint requires authentication"
    )
    maturity_tier: str | None = Field(
        None,
        description="Maturity tier from X-API-Maturity (production/pilot/scaffold)",
    )
    tags: list[str] = Field(
        default_factory=list, description="OpenAPI tags for the endpoint"
    )

    def contract_key(self) -> str:
        """Return a unique key for this endpoint (method + path)."""
        return f"{self.method.upper()} {self.path}"


class ContractSnapshot(BaseModel):
    """Point-in-time snapshot of all API endpoint contracts.

    Serialized to JSON for version control and CI comparison.
    """

    version: str = Field(..., description="Snapshot version identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the snapshot was captured",
    )
    app_version: str = Field(
        "1.0.0", description="Application version at capture time"
    )
    endpoints: list[EndpointContract] = Field(
        default_factory=list, description="All captured endpoint contracts"
    )
    endpoint_count: int = Field(
        0, description="Total number of endpoints captured"
    )

    def model_post_init(self, __context: Any) -> None:
        """Set endpoint_count after initialization."""
        if self.endpoints and self.endpoint_count == 0:
            object.__setattr__(self, "endpoint_count", len(self.endpoints))

    def endpoints_by_key(self) -> dict[str, EndpointContract]:
        """Return endpoints indexed by their contract key."""
        return {ep.contract_key(): ep for ep in self.endpoints}


class ContractChange(BaseModel):
    """A single detected change between two contract snapshots."""

    change_type: ChangeType = Field(
        ..., description="Severity of the change"
    )
    endpoint: str = Field(
        ..., description="Affected endpoint (METHOD /path)"
    )
    field: str = Field(
        "", description="Specific field or path within the schema"
    )
    description: str = Field(
        ..., description="Human-readable description of the change"
    )


class ContractComparison(BaseModel):
    """Result of comparing two contract snapshots."""

    baseline_version: str = Field(
        ..., description="Version of the baseline snapshot"
    )
    current_version: str = Field(
        ..., description="Version of the current snapshot"
    )
    breaking_changes: list[ContractChange] = Field(
        default_factory=list, description="Changes that break backward compatibility"
    )
    non_breaking_changes: list[ContractChange] = Field(
        default_factory=list, description="Safe, non-breaking changes"
    )
    removed_endpoints: list[str] = Field(
        default_factory=list,
        description="Endpoints present in baseline but absent in current",
    )
    added_endpoints: list[str] = Field(
        default_factory=list,
        description="Endpoints present in current but absent in baseline",
    )

    @property
    def has_breaking_changes(self) -> bool:
        """Return True if any breaking changes were detected."""
        return len(self.breaking_changes) > 0

    @property
    def total_changes(self) -> int:
        """Return the total number of changes detected."""
        return len(self.breaking_changes) + len(self.non_breaking_changes)
