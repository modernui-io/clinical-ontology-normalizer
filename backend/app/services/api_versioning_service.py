"""API Versioning and Deprecation Policy service (CTO-8).

Manages API version lifecycle, endpoint versioning, breaking change detection,
migration guide generation, and client usage tracking.

Usage:
    from app.services.api_versioning_service import get_api_versioning_service

    service = get_api_versioning_service()
    versions = service.list_versions()
    guide = service.generate_migration_guide("v1", "v2")
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock

from pydantic import BaseModel, Field

from app.schemas.api_versioning import (
    APIVersionListResponse,
    APIVersionRecord,
    APIVersionStatus,
    BreakingChange,
    BreakingChangeReport,
    BreakingChangeType,
    ClientUsageRecord,
    ClientUsageResponse,
    DeprecatedEndpointResponse,
    DeprecationHeaders,
    DeprecationPolicy,
    EndpointVersionInfo,
    EndpointVersionListResponse,
    MigrationGuide,
    MigrationStep,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_api_versioning_instance: APIVersioningService | None = None
_api_versioning_lock = Lock()


# ---------------------------------------------------------------------------
# Deprecation policy constants
# ---------------------------------------------------------------------------

MINIMUM_DEPRECATION_NOTICE_DAYS = 180  # 6 months
MINIMUM_SUNSET_PERIOD_DAYS = 90  # 3 months


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class APIVersioningService:
    """Manages API version lifecycle, deprecation, and client tracking.

    Thread-safe singleton service providing:
    - API version lifecycle (CURRENT -> DEPRECATED -> SUNSET -> RETIRED)
    - Per-endpoint versioning and deprecation tracking
    - Breaking change detection between versions
    - Migration guide generation
    - Client API version usage tracking
    - Deprecation policy enforcement
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._versions: dict[str, APIVersionRecord] = {}
        self._endpoints: dict[str, list[EndpointVersionInfo]] = {}  # version -> endpoints
        self._client_usage: dict[str, ClientUsageRecord] = {}  # client_id -> record
        self._policy = DeprecationPolicy(
            last_updated=datetime.now(timezone.utc),
        )
        self._initialize_default_versions()
        logger.info("APIVersioningService initialized")

    def _initialize_default_versions(self) -> None:
        """Pre-populate with v1 as the current API version."""
        now = datetime.now(timezone.utc)
        v1 = APIVersionRecord(
            version="v1",
            status=APIVersionStatus.CURRENT,
            release_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            changelog=[
                "Initial API release",
                "Clinical NLP endpoints",
                "OMOP terminology mapping",
                "Patient management CRUD",
                "Document ingestion pipeline",
                "Drug safety checking",
                "FHIR R4 resource management",
                "Knowledge graph queries",
                "Clinical trial screening",
            ],
            supported_until=datetime(2027, 1, 15, tzinfo=timezone.utc),
        )
        self._versions["v1"] = v1

        # Pre-populate sample endpoints for v1
        sample_endpoints = [
            EndpointVersionInfo(
                endpoint_path="/api/v1/patients",
                http_method="GET",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/patients",
                http_method="POST",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/patients/{patient_id}",
                http_method="GET",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/documents",
                http_method="POST",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/documents/{document_id}",
                http_method="GET",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/nlp/extract",
                http_method="POST",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/terminology/search",
                http_method="GET",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/fhir/Patient",
                http_method="GET",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/graph/query",
                http_method="POST",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/trials",
                http_method="GET",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/drug-safety/check",
                http_method="POST",
                introduced_in="v1",
            ),
            EndpointVersionInfo(
                endpoint_path="/api/v1/coding/icd10/suggest",
                http_method="POST",
                introduced_in="v1",
            ),
        ]
        self._endpoints["v1"] = sample_endpoints

    # -----------------------------------------------------------------------
    # Version Lifecycle Management
    # -----------------------------------------------------------------------

    def list_versions(self) -> APIVersionListResponse:
        """List all API versions with their lifecycle status."""
        with self._lock:
            versions = list(self._versions.values())
            current = "v1"
            for v in versions:
                if v.status == APIVersionStatus.CURRENT:
                    current = v.version
                    break
            return APIVersionListResponse(
                versions=versions,
                current_version=current,
                total=len(versions),
            )

    def get_version(self, version: str) -> APIVersionRecord | None:
        """Get a specific API version record."""
        with self._lock:
            return self._versions.get(version)

    def register_version(
        self,
        version: str,
        release_date: datetime,
        changelog: list[str] | None = None,
        supported_until: datetime | None = None,
    ) -> APIVersionRecord:
        """Register a new API version.

        Args:
            version: Version identifier (e.g., v2).
            release_date: When the version was released.
            changelog: Notable changes in this version.
            supported_until: Projected end-of-support date.

        Returns:
            The created APIVersionRecord.

        Raises:
            ValueError: If version already exists.
        """
        with self._lock:
            if version in self._versions:
                raise ValueError(f"Version {version} already exists")

            record = APIVersionRecord(
                version=version,
                status=APIVersionStatus.CURRENT,
                release_date=release_date,
                changelog=changelog or [],
                supported_until=supported_until,
            )
            self._versions[version] = record
            self._endpoints.setdefault(version, [])
            logger.info(f"Registered API version {version}")
            return record

    def deprecate_version(
        self,
        version: str,
        sunset_date: datetime | None = None,
    ) -> APIVersionRecord:
        """Mark an API version as deprecated.

        Enforces minimum 6-month notice before sunset.

        Args:
            version: Version to deprecate.
            sunset_date: Optional explicit sunset date.

        Returns:
            Updated APIVersionRecord.

        Raises:
            ValueError: If version not found or invalid transition.
        """
        with self._lock:
            record = self._versions.get(version)
            if not record:
                raise ValueError(f"Version {version} not found")

            if record.status != APIVersionStatus.CURRENT:
                raise ValueError(
                    f"Cannot deprecate version {version} with status {record.status.value}. "
                    f"Only CURRENT versions can be deprecated."
                )

            now = datetime.now(timezone.utc)
            deprecation_date = now

            # Enforce minimum deprecation notice
            if sunset_date:
                days_until_sunset = (sunset_date - deprecation_date).days
                if days_until_sunset < MINIMUM_DEPRECATION_NOTICE_DAYS:
                    raise ValueError(
                        f"Sunset date must be at least {MINIMUM_DEPRECATION_NOTICE_DAYS} days "
                        f"after deprecation. Got {days_until_sunset} days."
                    )
            else:
                sunset_date = deprecation_date + timedelta(days=MINIMUM_DEPRECATION_NOTICE_DAYS)

            record = record.model_copy(
                update={
                    "status": APIVersionStatus.DEPRECATED,
                    "deprecation_date": deprecation_date,
                    "sunset_date": sunset_date,
                }
            )
            self._versions[version] = record
            logger.info(f"Deprecated API version {version}, sunset: {sunset_date}")
            return record

    def sunset_version(self, version: str) -> APIVersionRecord:
        """Move an API version to sunset (read-only) mode.

        Args:
            version: Version to sunset.

        Returns:
            Updated APIVersionRecord.

        Raises:
            ValueError: If version not found or invalid transition.
        """
        with self._lock:
            record = self._versions.get(version)
            if not record:
                raise ValueError(f"Version {version} not found")

            if record.status != APIVersionStatus.DEPRECATED:
                raise ValueError(
                    f"Cannot sunset version {version} with status {record.status.value}. "
                    f"Only DEPRECATED versions can be sunset."
                )

            now = datetime.now(timezone.utc)
            retirement_date = now + timedelta(days=MINIMUM_SUNSET_PERIOD_DAYS)

            record = record.model_copy(
                update={
                    "status": APIVersionStatus.SUNSET,
                    "sunset_date": now,
                    "retirement_date": retirement_date,
                }
            )
            self._versions[version] = record
            logger.info(f"Sunset API version {version}, retirement: {retirement_date}")
            return record

    def retire_version(self, version: str) -> APIVersionRecord:
        """Retire an API version (remove from service).

        Args:
            version: Version to retire.

        Returns:
            Updated APIVersionRecord.

        Raises:
            ValueError: If version not found or invalid transition.
        """
        with self._lock:
            record = self._versions.get(version)
            if not record:
                raise ValueError(f"Version {version} not found")

            if record.status != APIVersionStatus.SUNSET:
                raise ValueError(
                    f"Cannot retire version {version} with status {record.status.value}. "
                    f"Only SUNSET versions can be retired."
                )

            now = datetime.now(timezone.utc)
            record = record.model_copy(
                update={
                    "status": APIVersionStatus.RETIRED,
                    "retirement_date": now,
                }
            )
            self._versions[version] = record
            logger.info(f"Retired API version {version}")
            return record

    # -----------------------------------------------------------------------
    # Endpoint Versioning
    # -----------------------------------------------------------------------

    def get_version_endpoints(self, version: str) -> EndpointVersionListResponse:
        """Get all endpoints for a specific API version.

        Args:
            version: API version to query.

        Returns:
            EndpointVersionListResponse with endpoints.

        Raises:
            ValueError: If version not found.
        """
        with self._lock:
            if version not in self._versions:
                raise ValueError(f"Version {version} not found")

            endpoints = self._endpoints.get(version, [])
            deprecated_count = sum(
                1 for ep in endpoints if ep.deprecated_in is not None
            )
            return EndpointVersionListResponse(
                version=version,
                endpoints=endpoints,
                total=len(endpoints),
                deprecated_count=deprecated_count,
            )

    def register_endpoint(
        self,
        version: str,
        endpoint_path: str,
        http_method: str,
    ) -> EndpointVersionInfo:
        """Register a new endpoint in a specific version.

        Args:
            version: API version to register in.
            endpoint_path: Endpoint path.
            http_method: HTTP method.

        Returns:
            Created EndpointVersionInfo.

        Raises:
            ValueError: If version not found or endpoint already exists.
        """
        with self._lock:
            if version not in self._versions:
                raise ValueError(f"Version {version} not found")

            # Check for duplicates
            endpoints = self._endpoints.setdefault(version, [])
            for ep in endpoints:
                if ep.endpoint_path == endpoint_path and ep.http_method == http_method.upper():
                    raise ValueError(
                        f"Endpoint {http_method.upper()} {endpoint_path} already exists in {version}"
                    )

            info = EndpointVersionInfo(
                endpoint_path=endpoint_path,
                http_method=http_method.upper(),
                introduced_in=version,
            )
            endpoints.append(info)
            return info

    def deprecate_endpoint(
        self,
        version: str,
        endpoint_path: str,
        http_method: str,
        deprecated_in: str,
        replacement_path: str | None = None,
        replacement_method: str | None = None,
        reason: str | None = None,
        sunset_date: datetime | None = None,
    ) -> EndpointVersionInfo:
        """Mark an endpoint as deprecated.

        Args:
            version: Version containing the endpoint.
            endpoint_path: Endpoint path to deprecate.
            http_method: HTTP method.
            deprecated_in: Version where deprecation occurs.
            replacement_path: Path to the replacement endpoint.
            replacement_method: HTTP method for the replacement.
            reason: Deprecation reason.
            sunset_date: When this endpoint will stop responding.

        Returns:
            Updated EndpointVersionInfo.

        Raises:
            ValueError: If endpoint not found.
        """
        with self._lock:
            endpoints = self._endpoints.get(version, [])
            for i, ep in enumerate(endpoints):
                if ep.endpoint_path == endpoint_path and ep.http_method == http_method.upper():
                    updated = EndpointVersionInfo(
                        endpoint_path=ep.endpoint_path,
                        http_method=ep.http_method,
                        introduced_in=ep.introduced_in,
                        deprecated_in=deprecated_in,
                        replacement_path=replacement_path,
                        replacement_method=replacement_method or ep.http_method,
                        deprecation_reason=reason,
                        sunset_date=sunset_date,
                    )
                    endpoints[i] = updated
                    logger.info(
                        f"Deprecated endpoint {http_method.upper()} {endpoint_path} "
                        f"in {version}, replacement: {replacement_path}"
                    )
                    return updated

            raise ValueError(
                f"Endpoint {http_method.upper()} {endpoint_path} not found in {version}"
            )

    def get_all_deprecated_endpoints(self) -> DeprecatedEndpointResponse:
        """Get all deprecated endpoints across all versions."""
        with self._lock:
            deprecated = []
            for version_endpoints in self._endpoints.values():
                for ep in version_endpoints:
                    if ep.deprecated_in is not None:
                        deprecated.append(ep)

            return DeprecatedEndpointResponse(
                endpoints=deprecated,
                total=len(deprecated),
            )

    def get_deprecation_headers(
        self,
        endpoint_path: str,
        http_method: str,
    ) -> DeprecationHeaders | None:
        """Get deprecation response headers for an endpoint (RFC 8594).

        Args:
            endpoint_path: The endpoint path.
            http_method: The HTTP method.

        Returns:
            DeprecationHeaders if endpoint is deprecated, else None.
        """
        with self._lock:
            for version_endpoints in self._endpoints.values():
                for ep in version_endpoints:
                    if (
                        ep.endpoint_path == endpoint_path
                        and ep.http_method == http_method.upper()
                        and ep.deprecated_in is not None
                    ):
                        headers = DeprecationHeaders()

                        # RFC 8594 Deprecation header
                        headers.deprecation = "true"

                        # Sunset header
                        if ep.sunset_date:
                            headers.sunset = ep.sunset_date.strftime(
                                "%a, %d %b %Y %H:%M:%S GMT"
                            )

                        # Link header to replacement
                        if ep.replacement_path:
                            headers.link = (
                                f'<{ep.replacement_path}>; rel="successor-version"'
                            )

                        return headers
            return None

    # -----------------------------------------------------------------------
    # Breaking Change Detection
    # -----------------------------------------------------------------------

    def detect_breaking_changes(
        self,
        from_version: str,
        to_version: str,
    ) -> BreakingChangeReport:
        """Detect breaking changes between two API versions.

        Compares endpoints in from_version against to_version to find:
        - Removed endpoints
        - Changed request schemas (simulated)
        - Changed response schemas (simulated)
        - Changed auth requirements (simulated)

        Args:
            from_version: Source version.
            to_version: Target version.

        Returns:
            BreakingChangeReport with detected changes.

        Raises:
            ValueError: If either version not found.
        """
        with self._lock:
            if from_version not in self._versions:
                raise ValueError(f"Version {from_version} not found")
            if to_version not in self._versions:
                raise ValueError(f"Version {to_version} not found")

            from_endpoints = self._endpoints.get(from_version, [])
            to_endpoints = self._endpoints.get(to_version, [])

            # Build lookup sets
            from_set = {
                (ep.endpoint_path, ep.http_method) for ep in from_endpoints
            }
            to_set = {
                (ep.endpoint_path, ep.http_method) for ep in to_endpoints
            }

            breaking_changes: list[BreakingChange] = []
            non_breaking: list[str] = []

            # Find removed endpoints (in from but not in to)
            removed = from_set - to_set
            for path, method in sorted(removed):
                breaking_changes.append(
                    BreakingChange(
                        change_type=BreakingChangeType.ENDPOINT_REMOVED,
                        endpoint_path=path,
                        http_method=method,
                        description=f"Endpoint {method} {path} was removed in {to_version}",
                        severity="HIGH",
                    )
                )

            # Find added endpoints (non-breaking)
            added = to_set - from_set
            for path, method in sorted(added):
                non_breaking.append(
                    f"New endpoint {method} {path} added in {to_version}"
                )

            # Check for deprecated endpoints that have replacements with
            # different paths (potential schema changes)
            for ep in from_endpoints:
                if ep.deprecated_in and ep.replacement_path:
                    # If the replacement exists in the target version, flag
                    # potential schema changes
                    replacement_key = (
                        ep.replacement_path,
                        ep.replacement_method or ep.http_method,
                    )
                    if replacement_key in to_set:
                        breaking_changes.append(
                            BreakingChange(
                                change_type=BreakingChangeType.REQUEST_SCHEMA_CHANGED,
                                endpoint_path=ep.endpoint_path,
                                http_method=ep.http_method,
                                description=(
                                    f"Endpoint {ep.http_method} {ep.endpoint_path} "
                                    f"replaced by {ep.replacement_path} in {to_version}. "
                                    f"Request/response schema may have changed."
                                ),
                                severity="MEDIUM",
                            )
                        )

            total_breaking = len(breaking_changes)
            total_non_breaking = len(non_breaking)
            is_compatible = total_breaking == 0

            if is_compatible:
                recommendation = (
                    f"Migration from {from_version} to {to_version} is fully backward "
                    f"compatible. No breaking changes detected."
                )
            elif total_breaking <= 3:
                recommendation = (
                    f"Migration from {from_version} to {to_version} has {total_breaking} "
                    f"breaking change(s). Review the changes and update client code accordingly."
                )
            else:
                recommendation = (
                    f"Migration from {from_version} to {to_version} has {total_breaking} "
                    f"breaking changes. Plan a phased migration with thorough testing."
                )

            return BreakingChangeReport(
                from_version=from_version,
                to_version=to_version,
                breaking_changes=breaking_changes,
                non_breaking_changes=non_breaking,
                is_compatible=is_compatible,
                total_breaking=total_breaking,
                total_non_breaking=total_non_breaking,
                recommendation=recommendation,
            )

    # -----------------------------------------------------------------------
    # Migration Guide Generation
    # -----------------------------------------------------------------------

    def generate_migration_guide(
        self,
        from_version: str,
        to_version: str,
    ) -> MigrationGuide:
        """Generate a migration guide between two API versions.

        Args:
            from_version: Source version to migrate from.
            to_version: Target version to migrate to.

        Returns:
            MigrationGuide with steps and instructions.

        Raises:
            ValueError: If either version not found.
        """
        # First detect breaking changes
        report = self.detect_breaking_changes(from_version, to_version)

        steps: list[MigrationStep] = []
        deprecation_warnings: list[str] = []
        step_num = 1

        # Step 1: Always start with inventory
        steps.append(
            MigrationStep(
                step_number=step_num,
                action=(
                    f"Inventory all API calls using {from_version} endpoints. "
                    f"Update base URL from /api/{from_version}/ to /api/{to_version}/."
                ),
                notes="Use API client logs to identify all endpoints in use.",
            )
        )
        step_num += 1

        # Generate steps for each breaking change
        for change in report.breaking_changes:
            if change.change_type == BreakingChangeType.ENDPOINT_REMOVED:
                # Find if there's a replacement
                replacement = self._find_replacement(
                    from_version, change.endpoint_path, change.http_method
                )
                if replacement:
                    steps.append(
                        MigrationStep(
                            step_number=step_num,
                            action=(
                                f"Replace {change.http_method} {change.endpoint_path} "
                                f"with {replacement.replacement_method or change.http_method} "
                                f"{replacement.replacement_path}"
                            ),
                            old_endpoint=change.endpoint_path,
                            new_endpoint=replacement.replacement_path,
                            notes=replacement.deprecation_reason,
                        )
                    )
                else:
                    steps.append(
                        MigrationStep(
                            step_number=step_num,
                            action=(
                                f"Remove calls to {change.http_method} {change.endpoint_path}. "
                                f"This endpoint has been removed with no direct replacement."
                            ),
                            old_endpoint=change.endpoint_path,
                            notes="Contact API support if this endpoint is critical to your workflow.",
                        )
                    )
                step_num += 1

            elif change.change_type == BreakingChangeType.REQUEST_SCHEMA_CHANGED:
                steps.append(
                    MigrationStep(
                        step_number=step_num,
                        action=(
                            f"Update request/response handling for "
                            f"{change.http_method} {change.endpoint_path}. "
                            f"{change.description}"
                        ),
                        old_endpoint=change.endpoint_path,
                        notes="Review API documentation for the updated schema.",
                    )
                )
                step_num += 1

        # Add deprecation warnings
        with self._lock:
            from_endpoints = self._endpoints.get(from_version, [])
            for ep in from_endpoints:
                if ep.deprecated_in:
                    deprecation_warnings.append(
                        f"{ep.http_method} {ep.endpoint_path} is deprecated "
                        f"since {ep.deprecated_in}"
                        + (f". Use {ep.replacement_path} instead." if ep.replacement_path else ".")
                    )

        # Final testing step
        steps.append(
            MigrationStep(
                step_number=step_num,
                action="Run integration tests against the new API version.",
                notes=(
                    "Verify all endpoints return expected responses. "
                    "Check for any schema changes in response payloads."
                ),
            )
        )

        # Determine estimated effort
        if report.total_breaking == 0:
            effort = "LOW"
            summary = (
                f"Straightforward migration from {from_version} to {to_version}. "
                f"No breaking changes detected."
            )
        elif report.total_breaking <= 5:
            effort = "MEDIUM"
            summary = (
                f"Moderate migration from {from_version} to {to_version}. "
                f"{report.total_breaking} breaking change(s) require code updates."
            )
        else:
            effort = "HIGH"
            summary = (
                f"Significant migration from {from_version} to {to_version}. "
                f"{report.total_breaking} breaking changes require careful planning."
            )

        return MigrationGuide(
            from_version=from_version,
            to_version=to_version,
            title=f"Migration Guide: {from_version} to {to_version}",
            summary=summary,
            estimated_effort=effort,
            steps=steps,
            breaking_changes_count=report.total_breaking,
            deprecation_warnings=deprecation_warnings,
            rollback_instructions=(
                f"To rollback, revert your API base URL from /api/{to_version}/ "
                f"to /api/{from_version}/ and restore any modified request/response handlers."
            ),
        )

    def _find_replacement(
        self,
        version: str,
        endpoint_path: str,
        http_method: str,
    ) -> EndpointVersionInfo | None:
        """Find the replacement for a deprecated endpoint."""
        endpoints = self._endpoints.get(version, [])
        for ep in endpoints:
            if (
                ep.endpoint_path == endpoint_path
                and ep.http_method == http_method.upper()
                and ep.replacement_path
            ):
                return ep
        return None

    # -----------------------------------------------------------------------
    # Client Usage Tracking
    # -----------------------------------------------------------------------

    def track_client_usage(
        self,
        client_id: str,
        api_version: str,
    ) -> ClientUsageRecord:
        """Track a client's API version usage.

        Args:
            client_id: Unique client identifier.
            api_version: API version the client used.

        Returns:
            Updated ClientUsageRecord.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._client_usage.get(client_id)
            if existing:
                # Update existing record
                version_record = self._versions.get(api_version)
                using_deprecated = False
                if version_record and version_record.status in (
                    APIVersionStatus.DEPRECATED,
                    APIVersionStatus.SUNSET,
                ):
                    using_deprecated = True

                updated = ClientUsageRecord(
                    client_id=client_id,
                    api_version=api_version,
                    last_seen=now,
                    request_count=existing.request_count + 1,
                    first_seen=existing.first_seen,
                    using_deprecated=using_deprecated,
                )
                self._client_usage[client_id] = updated
                return updated
            else:
                # Create new record
                version_record = self._versions.get(api_version)
                using_deprecated = False
                if version_record and version_record.status in (
                    APIVersionStatus.DEPRECATED,
                    APIVersionStatus.SUNSET,
                ):
                    using_deprecated = True

                record = ClientUsageRecord(
                    client_id=client_id,
                    api_version=api_version,
                    last_seen=now,
                    request_count=1,
                    first_seen=now,
                    using_deprecated=using_deprecated,
                )
                self._client_usage[client_id] = record
                return record

    def get_client_usage(self) -> ClientUsageResponse:
        """Get client usage statistics across all API versions."""
        with self._lock:
            clients = list(self._client_usage.values())
            on_deprecated = sum(1 for c in clients if c.using_deprecated)

            # Count clients on current version
            current_version = None
            for v in self._versions.values():
                if v.status == APIVersionStatus.CURRENT:
                    current_version = v.version
                    break

            on_current = sum(
                1 for c in clients
                if c.api_version == current_version
            ) if current_version else 0

            # Version distribution
            distribution: dict[str, int] = {}
            for c in clients:
                distribution[c.api_version] = distribution.get(c.api_version, 0) + 1

            return ClientUsageResponse(
                clients=clients,
                total_clients=len(clients),
                clients_on_deprecated=on_deprecated,
                clients_on_current=on_current,
                version_distribution=distribution,
            )

    def get_clients_on_deprecated_versions(self) -> list[ClientUsageRecord]:
        """Get clients still using deprecated API versions."""
        with self._lock:
            return [c for c in self._client_usage.values() if c.using_deprecated]

    # -----------------------------------------------------------------------
    # Deprecation Policy
    # -----------------------------------------------------------------------

    def get_deprecation_policy(self) -> DeprecationPolicy:
        """Get the current deprecation policy configuration."""
        with self._lock:
            return self._policy

    def validate_deprecation_timeline(
        self,
        deprecation_date: datetime,
        sunset_date: datetime,
        retirement_date: datetime | None = None,
    ) -> dict[str, bool | str]:
        """Validate a proposed deprecation timeline against policy.

        Args:
            deprecation_date: Proposed deprecation date.
            sunset_date: Proposed sunset date.
            retirement_date: Optional proposed retirement date.

        Returns:
            Dict with validation results.
        """
        results: dict[str, bool | str] = {"valid": True, "errors": ""}
        errors: list[str] = []

        # Check deprecation to sunset gap
        days_to_sunset = (sunset_date - deprecation_date).days
        if days_to_sunset < MINIMUM_DEPRECATION_NOTICE_DAYS:
            errors.append(
                f"Deprecation notice period ({days_to_sunset} days) is less than "
                f"required minimum ({MINIMUM_DEPRECATION_NOTICE_DAYS} days)"
            )

        # Check sunset to retirement gap
        if retirement_date:
            days_to_retirement = (retirement_date - sunset_date).days
            if days_to_retirement < MINIMUM_SUNSET_PERIOD_DAYS:
                errors.append(
                    f"Sunset period ({days_to_retirement} days) is less than "
                    f"required minimum ({MINIMUM_SUNSET_PERIOD_DAYS} days)"
                )

        if errors:
            results["valid"] = False
            results["errors"] = "; ".join(errors)

        return results

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get service statistics."""
        with self._lock:
            total_endpoints = sum(
                len(eps) for eps in self._endpoints.values()
            )
            deprecated_endpoints = sum(
                1
                for eps in self._endpoints.values()
                for ep in eps
                if ep.deprecated_in is not None
            )
            return {
                "total_versions": len(self._versions),
                "total_endpoints": total_endpoints,
                "deprecated_endpoints": deprecated_endpoints,
                "tracked_clients": len(self._client_usage),
                "policy_version": self._policy.policy_version,
            }


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_api_versioning_service() -> APIVersioningService:
    """Get or create the singleton APIVersioningService instance."""
    global _api_versioning_instance
    if _api_versioning_instance is None:
        with _api_versioning_lock:
            if _api_versioning_instance is None:
                _api_versioning_instance = APIVersioningService()
    return _api_versioning_instance


def reset_api_versioning_service() -> None:
    """Reset singleton for testing."""
    global _api_versioning_instance
    with _api_versioning_lock:
        _api_versioning_instance = None
