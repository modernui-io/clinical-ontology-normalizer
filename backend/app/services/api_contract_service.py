"""API Contract Stability Service (CTO-5).

Provides introspection of a FastAPI application to capture endpoint
contracts, compare snapshots for breaking changes, and generate
human-readable reports.

Usage:
    from app.services.api_contract_service import ApiContractService
    svc = ApiContractService(app)
    snapshot = svc.capture_contract_snapshot("v1.0")
    comparison = svc.compare_contracts(baseline, snapshot)
    report = svc.generate_contract_report(comparison)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.core.api_maturity import classify_path
from app.schemas.api_contract import (
    ChangeType,
    ContractChange,
    ContractComparison,
    ContractSnapshot,
    EndpointContract,
)

logger = logging.getLogger(__name__)

# Default directory for storing contract snapshots
DEFAULT_CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "contracts"


class ApiContractService:
    """Service for capturing and comparing API contract snapshots."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    # ------------------------------------------------------------------
    # Snapshot capture
    # ------------------------------------------------------------------

    def capture_contract_snapshot(
        self,
        version: str,
        app_version: str = "1.0.0",
    ) -> ContractSnapshot:
        """Introspect the FastAPI app and capture all route contracts.

        Args:
            version: Identifier for this snapshot (e.g. "v1.0", "pr-123").
            app_version: The application version string.

        Returns:
            A ContractSnapshot containing all endpoint contracts.
        """
        endpoints: list[EndpointContract] = []

        for route in self.app.routes:
            if not isinstance(route, APIRoute):
                continue

            # Skip internal/docs routes
            if route.path in ("/openapi.json", "/docs", "/redoc"):
                continue

            for method in sorted(route.methods or []):
                if method.upper() == "HEAD":
                    continue

                endpoint = self._extract_endpoint_contract(route, method)
                endpoints.append(endpoint)

        # Sort for deterministic output
        endpoints.sort(key=lambda ep: (ep.path, ep.method))

        snapshot = ContractSnapshot(
            version=version,
            timestamp=datetime.now(timezone.utc),
            app_version=app_version,
            endpoints=endpoints,
            endpoint_count=len(endpoints),
        )

        logger.info(
            "Captured contract snapshot %s with %d endpoints",
            version,
            len(endpoints),
        )
        return snapshot

    def _extract_endpoint_contract(
        self, route: APIRoute, method: str
    ) -> EndpointContract:
        """Extract the contract for a single route + method combination."""
        # Response schema
        response_schema = None
        if route.response_model is not None:
            try:
                response_schema = route.response_model.model_json_schema()
            except (AttributeError, TypeError):
                # response_model might not be a Pydantic model
                pass

        # Request body schema (from route.dependant.body_params)
        request_schema = None
        if hasattr(route, "dependant") and route.dependant.body_params:
            for body_param in route.dependant.body_params:
                field_info = body_param.field_info
                annotation = body_param.type_
                if annotation is not None and hasattr(annotation, "model_json_schema"):
                    try:
                        request_schema = annotation.model_json_schema()
                    except (AttributeError, TypeError):
                        pass
                    break

        # Query parameters
        query_params: list[dict[str, Any]] = []
        if hasattr(route, "dependant"):
            for param in route.dependant.query_params:
                param_info: dict[str, Any] = {
                    "name": param.alias or param.name,
                    "required": param.required,
                }
                if param.type_ is not None:
                    param_info["type"] = _type_name(param.type_)
                if param.default is not None:
                    try:
                        # Only store JSON-serializable defaults
                        json.dumps(param.default)
                        param_info["default"] = param.default
                    except (TypeError, ValueError):
                        pass
                query_params.append(param_info)

        # Path parameters
        path_params: list[dict[str, Any]] = []
        if hasattr(route, "dependant"):
            for param in route.dependant.path_params:
                param_info = {
                    "name": param.alias or param.name,
                    "required": True,
                }
                if param.type_ is not None:
                    param_info["type"] = _type_name(param.type_)
                path_params.append(param_info)

        # Auth detection: check for Depends(get_current_user) or similar
        auth_required = self._detect_auth(route)

        # Maturity tier from the classification registry
        maturity = classify_path(route.path)
        maturity_tier = maturity.value if maturity is not None else None

        # Tags
        tags = list(route.tags) if route.tags else []

        return EndpointContract(
            path=route.path,
            method=method.upper(),
            request_schema=request_schema,
            response_schema=response_schema,
            query_params=query_params,
            path_params=path_params,
            auth_required=auth_required,
            maturity_tier=maturity_tier,
            tags=tags,
        )

    def _detect_auth(self, route: APIRoute) -> bool:
        """Heuristically detect whether a route requires authentication.

        Looks for dependency functions whose names suggest authentication
        (e.g. get_current_user, require_auth, verify_token).
        """
        auth_indicators = {
            "get_current_user",
            "require_auth",
            "verify_token",
            "get_current_active_user",
            "api_key_auth",
            "require_api_key",
        }
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                call = dep.call
                name = getattr(call, "__name__", "")
                if name in auth_indicators:
                    return True
        return False

    # ------------------------------------------------------------------
    # Contract comparison
    # ------------------------------------------------------------------

    def compare_contracts(
        self,
        baseline: ContractSnapshot,
        current: ContractSnapshot,
    ) -> ContractComparison:
        """Compare two contract snapshots and detect breaking changes.

        Breaking changes:
            - Removed endpoints
            - Removed response fields
            - Changed field types
            - Added required fields to response
            - Added required request parameters

        Non-breaking changes:
            - New endpoints
            - New optional response fields
            - New optional request parameters

        Args:
            baseline: The reference/older snapshot.
            current: The new/current snapshot.

        Returns:
            A ContractComparison with all detected changes.
        """
        baseline_map = baseline.endpoints_by_key()
        current_map = current.endpoints_by_key()

        breaking: list[ContractChange] = []
        non_breaking: list[ContractChange] = []
        removed: list[str] = []
        added: list[str] = []

        # Detect removed endpoints (BREAKING)
        for key in baseline_map:
            if key not in current_map:
                removed.append(key)
                breaking.append(
                    ContractChange(
                        change_type=ChangeType.BREAKING,
                        endpoint=key,
                        field="",
                        description=f"Endpoint removed: {key}",
                    )
                )

        # Detect added endpoints (NON_BREAKING)
        for key in current_map:
            if key not in baseline_map:
                added.append(key)
                non_breaking.append(
                    ContractChange(
                        change_type=ChangeType.NON_BREAKING,
                        endpoint=key,
                        field="",
                        description=f"New endpoint added: {key}",
                    )
                )

        # Compare endpoints present in both
        for key in baseline_map:
            if key not in current_map:
                continue  # Already handled as removed

            base_ep = baseline_map[key]
            curr_ep = current_map[key]

            # Compare response schemas
            if base_ep.response_schema and curr_ep.response_schema:
                schema_changes = _compare_schemas(
                    base_ep.response_schema,
                    curr_ep.response_schema,
                    key,
                    "response",
                )
                for change in schema_changes:
                    if change.change_type == ChangeType.BREAKING:
                        breaking.append(change)
                    else:
                        non_breaking.append(change)

            elif base_ep.response_schema and not curr_ep.response_schema:
                breaking.append(
                    ContractChange(
                        change_type=ChangeType.BREAKING,
                        endpoint=key,
                        field="response_schema",
                        description="Response schema removed entirely",
                    )
                )

            # Compare request schemas
            if base_ep.request_schema and curr_ep.request_schema:
                schema_changes = _compare_schemas(
                    base_ep.request_schema,
                    curr_ep.request_schema,
                    key,
                    "request",
                )
                for change in schema_changes:
                    if change.change_type == ChangeType.BREAKING:
                        breaking.append(change)
                    else:
                        non_breaking.append(change)

            # Compare query parameters
            param_changes = _compare_params(
                base_ep.query_params, curr_ep.query_params, key, "query"
            )
            for change in param_changes:
                if change.change_type == ChangeType.BREAKING:
                    breaking.append(change)
                else:
                    non_breaking.append(change)

        return ContractComparison(
            baseline_version=baseline.version,
            current_version=current.version,
            breaking_changes=breaking,
            non_breaking_changes=non_breaking,
            removed_endpoints=removed,
            added_endpoints=added,
        )

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_contract_report(self, comparison: ContractComparison) -> str:
        """Generate a Markdown report from a contract comparison.

        Args:
            comparison: The comparison result to report on.

        Returns:
            A Markdown-formatted string.
        """
        lines: list[str] = []
        lines.append("# API Contract Comparison Report")
        lines.append("")
        lines.append(
            f"**Baseline:** {comparison.baseline_version} | "
            f"**Current:** {comparison.current_version}"
        )
        lines.append("")

        # Summary
        status = "FAIL - Breaking changes detected" if comparison.has_breaking_changes else "PASS"
        lines.append(f"## Status: {status}")
        lines.append("")
        lines.append(f"- Breaking changes: {len(comparison.breaking_changes)}")
        lines.append(f"- Non-breaking changes: {len(comparison.non_breaking_changes)}")
        lines.append(f"- Removed endpoints: {len(comparison.removed_endpoints)}")
        lines.append(f"- Added endpoints: {len(comparison.added_endpoints)}")
        lines.append("")

        # Breaking changes
        if comparison.breaking_changes:
            lines.append("## Breaking Changes")
            lines.append("")
            for change in comparison.breaking_changes:
                field_part = f" [{change.field}]" if change.field else ""
                lines.append(f"- **{change.endpoint}**{field_part}: {change.description}")
            lines.append("")

        # Non-breaking changes
        if comparison.non_breaking_changes:
            lines.append("## Non-Breaking Changes")
            lines.append("")
            for change in comparison.non_breaking_changes:
                field_part = f" [{change.field}]" if change.field else ""
                lines.append(f"- {change.endpoint}{field_part}: {change.description}")
            lines.append("")

        # Removed endpoints
        if comparison.removed_endpoints:
            lines.append("## Removed Endpoints")
            lines.append("")
            for ep in comparison.removed_endpoints:
                lines.append(f"- `{ep}`")
            lines.append("")

        # Added endpoints
        if comparison.added_endpoints:
            lines.append("## Added Endpoints")
            lines.append("")
            for ep in comparison.added_endpoints:
                lines.append(f"- `{ep}`")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_snapshot(
        self,
        snapshot: ContractSnapshot,
        directory: Path | None = None,
    ) -> Path:
        """Save a snapshot as a JSON file.

        Args:
            snapshot: The snapshot to persist.
            directory: Target directory (defaults to tests/contracts/).

        Returns:
            Path to the written file.
        """
        target_dir = directory or DEFAULT_CONTRACTS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"api_contract_{snapshot.version}.json"
        filepath = target_dir / filename

        filepath.write_text(
            snapshot.model_dump_json(indent=2),
            encoding="utf-8",
        )

        logger.info("Saved contract snapshot to %s", filepath)
        return filepath

    @staticmethod
    def load_snapshot(filepath: Path) -> ContractSnapshot:
        """Load a snapshot from a JSON file.

        Args:
            filepath: Path to the JSON file.

        Returns:
            The deserialized ContractSnapshot.
        """
        data = filepath.read_text(encoding="utf-8")
        return ContractSnapshot.model_validate_json(data)


# ======================================================================
# Module-level helpers (not on the class so tests can call them directly)
# ======================================================================


def _type_name(t: Any) -> str:
    """Return a stable string name for a Python type annotation."""
    if t is None:
        return "None"
    name = getattr(t, "__name__", None)
    if name:
        return name
    return str(t)


def _compare_schemas(
    baseline: dict[str, Any],
    current: dict[str, Any],
    endpoint: str,
    context: str,
    path_prefix: str = "",
) -> list[ContractChange]:
    """Recursively compare two JSON Schema dicts.

    Args:
        baseline: The baseline JSON Schema.
        current: The current JSON Schema.
        endpoint: The endpoint key for change attribution.
        context: "request" or "response" for labelling.
        path_prefix: Dot-separated path within the schema.

    Returns:
        List of ContractChange objects.
    """
    changes: list[ContractChange] = []

    base_props = baseline.get("properties", {})
    curr_props = current.get("properties", {})
    base_required = set(baseline.get("required", []))
    curr_required = set(current.get("required", []))

    # Fields removed from the schema
    for field_name in base_props:
        full_path = f"{path_prefix}.{field_name}" if path_prefix else field_name
        if field_name not in curr_props:
            changes.append(
                ContractChange(
                    change_type=ChangeType.BREAKING,
                    endpoint=endpoint,
                    field=f"{context}.{full_path}",
                    description=f"Field '{full_path}' removed from {context} schema",
                )
            )
            continue

        # Type changes
        base_type = base_props[field_name].get("type")
        curr_type = curr_props[field_name].get("type")
        if base_type and curr_type and base_type != curr_type:
            changes.append(
                ContractChange(
                    change_type=ChangeType.BREAKING,
                    endpoint=endpoint,
                    field=f"{context}.{full_path}",
                    description=(
                        f"Field '{full_path}' type changed from "
                        f"'{base_type}' to '{curr_type}' in {context} schema"
                    ),
                )
            )

        # Recurse into nested objects
        if (
            base_props[field_name].get("type") == "object"
            and curr_props[field_name].get("type") == "object"
        ):
            nested = _compare_schemas(
                base_props[field_name],
                curr_props[field_name],
                endpoint,
                context,
                path_prefix=full_path,
            )
            changes.extend(nested)

    # Fields added to the schema
    for field_name in curr_props:
        full_path = f"{path_prefix}.{field_name}" if path_prefix else field_name
        if field_name not in base_props:
            if field_name in curr_required:
                # New required field -> BREAKING
                changes.append(
                    ContractChange(
                        change_type=ChangeType.BREAKING,
                        endpoint=endpoint,
                        field=f"{context}.{full_path}",
                        description=(
                            f"Required field '{full_path}' added to {context} schema"
                        ),
                    )
                )
            else:
                # New optional field -> NON_BREAKING
                changes.append(
                    ContractChange(
                        change_type=ChangeType.NON_BREAKING,
                        endpoint=endpoint,
                        field=f"{context}.{full_path}",
                        description=(
                            f"Optional field '{full_path}' added to {context} schema"
                        ),
                    )
                )

    # Existing field became required
    for field_name in curr_required - base_required:
        if field_name in base_props and field_name in curr_props:
            full_path = f"{path_prefix}.{field_name}" if path_prefix else field_name
            changes.append(
                ContractChange(
                    change_type=ChangeType.BREAKING,
                    endpoint=endpoint,
                    field=f"{context}.{full_path}",
                    description=(
                        f"Field '{full_path}' changed from optional to required "
                        f"in {context} schema"
                    ),
                )
            )

    return changes


def _compare_params(
    baseline: list[dict[str, Any]],
    current: list[dict[str, Any]],
    endpoint: str,
    param_type: str,
) -> list[ContractChange]:
    """Compare query/path parameter lists.

    Args:
        baseline: Baseline parameter definitions.
        current: Current parameter definitions.
        endpoint: Endpoint key.
        param_type: "query" or "path" for labelling.

    Returns:
        List of ContractChange objects.
    """
    changes: list[ContractChange] = []

    base_by_name = {p["name"]: p for p in baseline}
    curr_by_name = {p["name"]: p for p in current}

    # Removed parameters (BREAKING)
    for name in base_by_name:
        if name not in curr_by_name:
            changes.append(
                ContractChange(
                    change_type=ChangeType.BREAKING,
                    endpoint=endpoint,
                    field=f"{param_type}_param.{name}",
                    description=f"{param_type.title()} parameter '{name}' removed",
                )
            )

    # Added parameters
    for name in curr_by_name:
        if name not in base_by_name:
            param = curr_by_name[name]
            if param.get("required", False):
                changes.append(
                    ContractChange(
                        change_type=ChangeType.BREAKING,
                        endpoint=endpoint,
                        field=f"{param_type}_param.{name}",
                        description=(
                            f"Required {param_type} parameter '{name}' added"
                        ),
                    )
                )
            else:
                changes.append(
                    ContractChange(
                        change_type=ChangeType.NON_BREAKING,
                        endpoint=endpoint,
                        field=f"{param_type}_param.{name}",
                        description=(
                            f"Optional {param_type} parameter '{name}' added"
                        ),
                    )
                )

    return changes
