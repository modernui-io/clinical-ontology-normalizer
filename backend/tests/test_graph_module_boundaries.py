"""Contract tests for graph module boundaries.

Phase 2 — verifies that graph service files respect module boundaries,
the registry covers all graph/kg files, and key services have expected interfaces.
"""

from __future__ import annotations

import pathlib

import pytest

from app.services.graph_module_registry import (
    ALL_GRAPH_SERVICES,
    ALLOWED_DEPENDENCIES,
    GRAPH_ANALYTICS_SERVICES,
    GRAPH_RAG_SERVICES,
    GRAPH_STORAGE_SERVICES,
    GRAPH_SUPPORT_SERVICES,
    get_module_for_service,
    validate_boundaries,
)


SERVICES_DIR = pathlib.Path(__file__).resolve().parent.parent / "app" / "services"


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    """Verify the registry accounts for every graph_*.py and kg_*.py file."""

    def test_all_graph_files_registered(self):
        """Every graph_*.py and kg_*.py in services/ must appear in the registry."""
        on_disk = {
            p.stem
            for p in SERVICES_DIR.glob("graph_*.py")
            if p.stem != "graph_module_registry"
        } | {p.stem for p in SERVICES_DIR.glob("kg_*.py")}

        missing = on_disk - ALL_GRAPH_SERVICES
        extra = ALL_GRAPH_SERVICES - on_disk

        assert not missing, f"Files on disk but NOT in registry: {sorted(missing)}"
        assert not extra, f"In registry but NOT on disk: {sorted(extra)}"

    def test_no_duplicate_across_modules(self):
        """No service should appear in more than one module."""
        seen: dict[str, str] = {}
        for module, services in [
            ("graph_storage", GRAPH_STORAGE_SERVICES),
            ("graph_analytics", GRAPH_ANALYTICS_SERVICES),
            ("graph_rag", GRAPH_RAG_SERVICES),
            ("graph_support", GRAPH_SUPPORT_SERVICES),
        ]:
            for svc in services:
                assert svc not in seen, (
                    f"{svc} appears in both {seen[svc]} and {module}"
                )
                seen[svc] = module

    def test_get_module_for_service_known(self):
        """get_module_for_service returns correct module for known services."""
        assert get_module_for_service("graph_builder") == "graph_storage"
        assert get_module_for_service("graph_analytics_service") == "graph_analytics"
        assert get_module_for_service("graph_augmented_rag") == "graph_rag"
        assert get_module_for_service("kg_cache_service") == "graph_support"

    def test_get_module_for_service_unknown(self):
        """get_module_for_service returns None for unrecognised names."""
        assert get_module_for_service("not_a_graph_service") is None


# ---------------------------------------------------------------------------
# Module boundary enforcement (AST-based)
# ---------------------------------------------------------------------------


class TestModuleBoundaries:
    """Verify import-level boundaries between graph modules."""

    def test_validate_boundaries_no_violations(self):
        """validate_boundaries() should return an empty list."""
        violations = validate_boundaries()
        assert violations == [], (
            "Graph module boundary violations detected:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_storage_does_not_import_analytics(self):
        """Storage module must NOT import from analytics or RAG."""
        import ast

        for svc_name in GRAPH_STORAGE_SERVICES:
            filepath = SERVICES_DIR / f"{svc_name}.py"
            if not filepath.exists():
                continue
            source = filepath.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "services":
                        imported = parts[2]
                        assert imported not in GRAPH_ANALYTICS_SERVICES, (
                            f"{svc_name} (storage) imports {imported} (analytics)"
                        )
                        assert imported not in GRAPH_RAG_SERVICES, (
                            f"{svc_name} (storage) imports {imported} (rag)"
                        )

    def test_analytics_does_not_import_rag(self):
        """Analytics module must NOT import from RAG."""
        import ast

        for svc_name in GRAPH_ANALYTICS_SERVICES:
            filepath = SERVICES_DIR / f"{svc_name}.py"
            if not filepath.exists():
                continue
            source = filepath.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "services":
                        imported = parts[2]
                        assert imported not in GRAPH_RAG_SERVICES, (
                            f"{svc_name} (analytics) imports {imported} (rag)"
                        )

    def test_support_does_not_import_core_modules(self):
        """Support module must NOT import from storage, analytics, or RAG."""
        import ast

        non_support = GRAPH_STORAGE_SERVICES | GRAPH_ANALYTICS_SERVICES | GRAPH_RAG_SERVICES
        for svc_name in GRAPH_SUPPORT_SERVICES:
            filepath = SERVICES_DIR / f"{svc_name}.py"
            if not filepath.exists():
                continue
            source = filepath.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "services":
                        imported = parts[2]
                        assert imported not in non_support, (
                            f"{svc_name} (support) imports {imported} — "
                            f"support must not import from storage/analytics/rag"
                        )


# ---------------------------------------------------------------------------
# Interface contracts for key services
# ---------------------------------------------------------------------------


class TestDatabaseGraphBuilderServiceContract:
    """Verify DatabaseGraphBuilderService has expected interface."""

    def test_import(self):
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        assert DatabaseGraphBuilderService is not None

    def test_has_build_graph_for_patient(self):
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        assert hasattr(DatabaseGraphBuilderService, "build_graph_for_patient")

    def test_has_create_node(self):
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        assert hasattr(DatabaseGraphBuilderService, "create_node")

    def test_has_create_edge(self):
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        assert hasattr(DatabaseGraphBuilderService, "create_edge")

    def test_has_project_fact_to_graph(self):
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        assert hasattr(DatabaseGraphBuilderService, "project_fact_to_graph")

    def test_has_get_patient_graph(self):
        from app.services.graph_builder_db import DatabaseGraphBuilderService

        assert hasattr(DatabaseGraphBuilderService, "get_patient_graph")


class TestGraphDatabaseServiceContract:
    """Verify GraphDatabaseService has expected interface methods."""

    def test_import(self):
        from app.services.graph_database_service import GraphDatabaseService

        assert GraphDatabaseService is not None

    def test_has_execute_query(self):
        from app.services.graph_database_service import GraphDatabaseService

        assert hasattr(GraphDatabaseService, "execute_query")

    def test_has_execute_write(self):
        from app.services.graph_database_service import GraphDatabaseService

        assert hasattr(GraphDatabaseService, "execute_write")

    def test_has_execute_read(self):
        from app.services.graph_database_service import GraphDatabaseService

        assert hasattr(GraphDatabaseService, "execute_read")

    def test_has_health_check(self):
        from app.services.graph_database_service import GraphDatabaseService

        assert hasattr(GraphDatabaseService, "health_check")

    def test_has_close(self):
        from app.services.graph_database_service import GraphDatabaseService

        assert hasattr(GraphDatabaseService, "close")
