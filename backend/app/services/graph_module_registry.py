"""
Graph module boundary registry.

Phase 2 canonicalization — defines which services belong to which graph module
and provides test-time boundary validation.

Modules:
- graph_storage: Core graph persistence (PostgreSQL, Neo4j)
- graph_analytics: Graph analysis, embeddings, scoring, visualization
- graph_rag: RAG integration, ETL
- graph_support: Cross-cutting utilities (cache, audit, tracing, metrics, config, etc.)
"""

from __future__ import annotations

import ast
import pathlib
from typing import Any

GRAPH_STORAGE_SERVICES: set[str] = {
    "graph_builder",
    "graph_builder_db",
    "graph_database_service",
}

GRAPH_ANALYTICS_SERVICES: set[str] = {
    "graph_analytics_service",
    "graph_embedding_service",
    "kg_completeness_scorer",
    "kg_visualization_service",
}

GRAPH_RAG_SERVICES: set[str] = {
    "graph_augmented_rag",
    "graph_etl_service",
}

GRAPH_SUPPORT_SERVICES: set[str] = {
    "kg_cache_service",
    "kg_tracing_service",
    "kg_webhook_service",
    "kg_data_export_service",
    "kg_grafana_dashboards",
    "kg_partitioning_service",
    "kg_audit_service",
    "kg_config_service",
    "kg_prometheus_metrics",
    "kg_api_key_service",
    "kg_load_testing_service",
    "kg_logging_service",
    "kg_schema_migration_service",
    "kg_kafka_streaming_service",
    "kg_calculator_mapper",
    "kg_merge_validator",
}

ALL_GRAPH_SERVICES: set[str] = (
    GRAPH_STORAGE_SERVICES
    | GRAPH_ANALYTICS_SERVICES
    | GRAPH_RAG_SERVICES
    | GRAPH_SUPPORT_SERVICES
)

# Allowed dependency directions: module -> set of modules it may import from
ALLOWED_DEPENDENCIES: dict[str, set[str]] = {
    "graph_storage": {"graph_support"},
    "graph_analytics": {"graph_storage", "graph_support"},
    "graph_rag": {"graph_storage", "graph_support"},
    "graph_support": set(),  # support modules should not import from other graph modules
}

_MODULE_MAP: list[tuple[str, set[str]]] = [
    ("graph_storage", GRAPH_STORAGE_SERVICES),
    ("graph_analytics", GRAPH_ANALYTICS_SERVICES),
    ("graph_rag", GRAPH_RAG_SERVICES),
    ("graph_support", GRAPH_SUPPORT_SERVICES),
]


def get_module_for_service(service_name: str) -> str | None:
    """Return the module name for a given service file."""
    for module, services in _MODULE_MAP:
        if service_name in services:
            return module
    return None


def _extract_graph_imports(source: str) -> list[str]:
    """Parse Python source and return imported graph/kg service names."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # Match 'from app.services.graph_xxx import ...' or 'from app.services.kg_xxx import ...'
            parts = node.module.split(".")
            if len(parts) >= 3 and parts[0] == "app" and parts[1] == "services":
                svc_name = parts[2]
                if svc_name.startswith("graph_") or svc_name.startswith("kg_"):
                    imported.append(svc_name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) >= 3 and parts[0] == "app" and parts[1] == "services":
                    svc_name = parts[2]
                    if svc_name.startswith("graph_") or svc_name.startswith("kg_"):
                        imported.append(svc_name)
    return imported


def validate_boundaries() -> list[str]:
    """
    Check that no module imports from a module it shouldn't.
    Returns list of violation descriptions (empty = clean).
    Uses AST-based import analysis.
    """
    services_dir = pathlib.Path(__file__).parent
    violations: list[str] = []

    for module_name, services in _MODULE_MAP:
        allowed = ALLOWED_DEPENDENCIES[module_name]
        # A module is also allowed to import from itself
        allowed_with_self = allowed | {module_name}

        for svc_name in services:
            filepath = services_dir / f"{svc_name}.py"
            if not filepath.exists():
                continue

            source = filepath.read_text()
            imported_services = _extract_graph_imports(source)

            for imp_svc in imported_services:
                imp_module = get_module_for_service(imp_svc)
                if imp_module is None:
                    # Not a registered graph service — skip
                    continue
                if imp_module not in allowed_with_self:
                    violations.append(
                        f"{svc_name} ({module_name}) imports {imp_svc} ({imp_module}) "
                        f"— not in allowed deps {allowed}"
                    )

    return violations
