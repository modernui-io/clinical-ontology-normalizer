"""Tests for CTO-7 developer experience tools.

Tests the three dev scripts:
- dev_setup_check.py: development environment validator
- service_dependency_graph.py: service dependency mapper
- endpoint_inventory.py: API endpoint inventory builder
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from dev_setup_check import (
    CheckReport,
    CheckResult,
    Severity,
    check_env_file,
    check_frontend_deps,
    check_git_hooks,
    check_port_available,
    check_python_version,
    check_system_tools,
    run_all_checks,
)
from endpoint_inventory import (
    EndpointInfo,
    compute_stats,
    extract_endpoints_from_file,
    extract_router_prefix,
    format_csv_output,
    format_json_output,
    format_markdown,
    run_endpoint_inventory,
    scan_api_directory,
)
from service_dependency_graph import (
    build_dependency_graph,
    compute_stats as dep_compute_stats,
    extract_service_imports,
    find_circular_dependencies,
    format_json as dep_format_json,
    format_mermaid,
    format_summary,
    run_dependency_analysis,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def tmp_services_dir(tmp_path: Path) -> Path:
    """Create a temporary services directory with mock service files."""
    svc_dir = tmp_path / "services"
    svc_dir.mkdir()

    (svc_dir / "__init__.py").write_text("")

    (svc_dir / "alpha_service.py").write_text(textwrap.dedent("""\
        from app.services.beta_service import BetaService
        from app.services.gamma_service import something

        class AlphaService:
            pass
    """))

    (svc_dir / "beta_service.py").write_text(textwrap.dedent("""\
        from app.services.gamma_service import GammaService

        class BetaService:
            pass
    """))

    (svc_dir / "gamma_service.py").write_text(textwrap.dedent("""\
        import logging

        class GammaService:
            pass
    """))

    (svc_dir / "delta_service.py").write_text(textwrap.dedent("""\
        from app.services.alpha_service import AlphaService
        from app.services.beta_service import BetaService
        from app.services.gamma_service import GammaService

        class DeltaService:
            pass
    """))

    return svc_dir


@pytest.fixture
def circular_services_dir(tmp_path: Path) -> Path:
    """Create services with circular dependencies."""
    svc_dir = tmp_path / "services"
    svc_dir.mkdir()

    (svc_dir / "__init__.py").write_text("")

    (svc_dir / "service_a.py").write_text(textwrap.dedent("""\
        from app.services.service_b import ServiceB
        class ServiceA:
            pass
    """))

    (svc_dir / "service_b.py").write_text(textwrap.dedent("""\
        from app.services.service_c import ServiceC
        class ServiceB:
            pass
    """))

    (svc_dir / "service_c.py").write_text(textwrap.dedent("""\
        from app.services.service_a import ServiceA
        class ServiceC:
            pass
    """))

    return svc_dir


@pytest.fixture
def tmp_api_dir(tmp_path: Path) -> Path:
    """Create a temporary API directory with mock router files."""
    api_dir = tmp_path / "api"
    api_dir.mkdir()

    (api_dir / "__init__.py").write_text("")

    (api_dir / "health.py").write_text(textwrap.dedent("""\
        from fastapi import APIRouter

        router = APIRouter(prefix="/api/v1/health", tags=["Health"])

        @router.get("", summary="Health check")
        def health_check():
            return {"status": "ok"}

        @router.get("/deep", response_model=dict, summary="Deep health check")
        def deep_health():
            return {"status": "ok", "db": True}
    """))

    (api_dir / "patients.py").write_text(textwrap.dedent("""\
        from fastapi import APIRouter, Depends

        def get_current_user():
            pass

        router = APIRouter(prefix="/patients", tags=["Patients"])

        @router.get("", summary="List patients")
        def list_patients(current_user=Depends(get_current_user)):
            return []

        @router.post("", response_model=dict, summary="Create patient")
        def create_patient(current_user=Depends(get_current_user)):
            return {}

        @router.get("/{patient_id}", summary="Get patient")
        def get_patient(patient_id: str, current_user=Depends(get_current_user)):
            return {}

        @router.delete("/{patient_id}", summary="Delete patient")
        def delete_patient(patient_id: str, current_user=Depends(get_current_user)):
            return {}
    """))

    return api_dir


@pytest.fixture
def tmp_project_root(tmp_path: Path) -> Path:
    """Create a minimal project structure for dev_setup_check tests."""
    root = tmp_path / "project"
    root.mkdir()

    # .env file
    (root / ".env").write_text("DATABASE_URL=postgresql://...\nREDIS_URL=redis://...\n")

    # backend/requirements.txt
    backend = root / "backend"
    backend.mkdir()
    (backend / "requirements.txt").write_text("pytest\nfastapi\n")

    # frontend/node_modules
    frontend = root / "frontend"
    frontend.mkdir()
    (frontend / "node_modules").mkdir()

    # .git/hooks
    git_dir = root / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    (git_dir / "pre-commit").write_text("#!/bin/sh\nexit 0\n")

    return root


# ===========================================================================
# dev_setup_check.py tests
# ===========================================================================


class TestDevSetupCheck:
    """Tests for the development environment validator."""

    def test_check_python_version_passes(self):
        """Current Python should pass the version check."""
        report = CheckReport()
        check_python_version(report)
        assert len(report.results) == 1
        result = report.results[0]
        assert result.passed is True
        assert result.severity == Severity.CRITICAL
        assert "Python" in result.message

    def test_check_report_to_dict(self):
        """CheckReport.to_dict() returns expected structure."""
        report = CheckReport()
        report.add(CheckResult(
            name="Test check",
            passed=True,
            severity=Severity.CRITICAL,
            message="All good",
        ))
        report.add(CheckResult(
            name="Failing check",
            passed=False,
            severity=Severity.CRITICAL,
            message="Not good",
            fix_hint="Fix it",
        ))

        d = report.to_dict()
        assert d["passed"] is False  # one critical failure
        assert d["summary"]["total"] == 2
        assert d["summary"]["passed"] == 1
        assert d["summary"]["critical_failures"] == 1
        assert len(d["results"]) == 2

    def test_env_file_check_with_valid_env(self, tmp_project_root: Path):
        """Env file check passes when .env has required vars."""
        report = CheckReport()
        check_env_file(report, tmp_project_root)
        # Should have: .env exists + DATABASE_URL + REDIS_URL
        assert len(report.results) >= 3
        # .env file should pass
        assert report.results[0].passed is True
        # Both env vars should pass
        assert report.results[1].passed is True
        assert report.results[2].passed is True

    def test_env_file_check_missing_env(self, tmp_path: Path):
        """Env file check fails when .env is missing."""
        report = CheckReport()
        check_env_file(report, tmp_path)
        assert report.results[0].passed is False
        assert ".env" in report.results[0].message

    def test_frontend_deps_present(self, tmp_project_root: Path):
        """Frontend deps check passes when node_modules exists."""
        report = CheckReport()
        check_frontend_deps(report, tmp_project_root)
        assert report.results[0].passed is True

    def test_frontend_deps_missing(self, tmp_path: Path):
        """Frontend deps check fails when node_modules is missing."""
        report = CheckReport()
        check_frontend_deps(report, tmp_path)
        assert report.results[0].passed is False

    def test_git_hooks_detected(self, tmp_project_root: Path):
        """Git hooks check detects installed hooks."""
        report = CheckReport()
        check_git_hooks(report, tmp_project_root)
        assert report.results[0].passed is True
        assert "1 hook" in report.results[0].message

    def test_port_available_check(self):
        """Port check on an unlikely port should report available."""
        # Port 59999 is unlikely to be in use
        result = check_port_available(59999, "Test service")
        assert result.passed is True
        assert "available" in result.message

    def test_all_critical_passed_property(self):
        """Report correctly identifies when all critical checks pass."""
        report = CheckReport()
        report.add(CheckResult(name="a", passed=True, severity=Severity.CRITICAL))
        report.add(CheckResult(name="b", passed=False, severity=Severity.WARNING))
        assert report.all_critical_passed is True

        report.add(CheckResult(name="c", passed=False, severity=Severity.CRITICAL))
        assert report.all_critical_passed is False


# ===========================================================================
# service_dependency_graph.py tests
# ===========================================================================


class TestServiceDependencyGraph:
    """Tests for the service dependency mapper."""

    def test_extract_service_imports_from_import(self):
        """Extract imports using 'from app.services.X import Y' pattern."""
        source = textwrap.dedent("""\
            from app.services.audit_service import AuditService
            from app.services.graph_builder import build_graph
            import os
        """)
        deps = extract_service_imports(source)
        assert deps == ["audit_service", "graph_builder"]

    def test_extract_service_imports_ignores_non_service(self):
        """Non-service imports are excluded."""
        source = textwrap.dedent("""\
            from app.models.user import User
            from app.core.config import settings
            import logging
        """)
        deps = extract_service_imports(source)
        assert deps == []

    def test_extract_service_imports_import_statement(self):
        """Extract imports using 'import app.services.X' pattern."""
        source = "import app.services.fact_builder\n"
        deps = extract_service_imports(source)
        assert deps == ["fact_builder"]

    def test_build_dependency_graph(self, tmp_services_dir: Path):
        """Build graph from mock service files."""
        graph = build_dependency_graph(tmp_services_dir)

        assert "alpha_service" in graph
        assert "beta_service" in graph
        assert "gamma_service" in graph
        assert "delta_service" in graph

        assert sorted(graph["alpha_service"]) == ["beta_service", "gamma_service"]
        assert graph["beta_service"] == ["gamma_service"]
        assert graph["gamma_service"] == []
        assert sorted(graph["delta_service"]) == ["alpha_service", "beta_service", "gamma_service"]

    def test_no_circular_dependencies(self, tmp_services_dir: Path):
        """No circular dependencies in a DAG."""
        graph = build_dependency_graph(tmp_services_dir)
        cycles = find_circular_dependencies(graph)
        assert cycles == []

    def test_detect_circular_dependencies(self, circular_services_dir: Path):
        """Circular dependencies are detected."""
        graph = build_dependency_graph(circular_services_dir)
        cycles = find_circular_dependencies(graph)
        assert len(cycles) >= 1
        # The cycle should contain all three services
        cycle_services = set(cycles[0][:-1])  # exclude the repeated element
        assert cycle_services == {"service_a", "service_b", "service_c"}

    def test_compute_stats(self, tmp_services_dir: Path):
        """Statistics computation returns expected shape."""
        graph = build_dependency_graph(tmp_services_dir)
        stats = dep_compute_stats(graph)
        assert stats["total_services"] == 4
        assert stats["total_edges"] > 0
        assert isinstance(stats["most_depended_on"], list)
        assert isinstance(stats["most_dependent"], list)

    def test_mermaid_output(self, tmp_services_dir: Path):
        """Mermaid output is valid."""
        graph = build_dependency_graph(tmp_services_dir)
        cycles = find_circular_dependencies(graph)
        output = format_mermaid(graph, cycles)
        assert output.startswith("graph LR")
        assert "-->" in output

    def test_json_output_parseable(self, tmp_services_dir: Path):
        """JSON output is valid JSON."""
        graph = build_dependency_graph(tmp_services_dir)
        cycles = find_circular_dependencies(graph)
        stats = dep_compute_stats(graph)
        output = dep_format_json(graph, cycles, stats)
        data = json.loads(output)
        assert "adjacency_list" in data
        assert "circular_dependencies" in data
        assert "stats" in data

    def test_summary_output(self, tmp_services_dir: Path):
        """Summary output contains expected sections."""
        graph = build_dependency_graph(tmp_services_dir)
        cycles = find_circular_dependencies(graph)
        stats = dep_compute_stats(graph)
        output = format_summary(graph, cycles, stats)
        assert "Service Dependency Graph" in output
        assert "Total services: 4" in output
        assert "No circular dependencies" in output

    def test_run_dependency_analysis_on_real_codebase(self):
        """Run analysis on the actual services directory (smoke test)."""
        real_dir = Path(__file__).resolve().parent.parent / "app" / "services"
        if not real_dir.is_dir():
            pytest.skip("Real services directory not found")
        graph, cycles, stats = run_dependency_analysis(real_dir)
        assert stats["total_services"] > 0
        assert isinstance(graph, dict)


# ===========================================================================
# endpoint_inventory.py tests
# ===========================================================================


class TestEndpointInventory:
    """Tests for the API endpoint inventory builder."""

    def test_extract_router_prefix(self):
        """Router prefix is extracted from source."""
        source = 'router = APIRouter(prefix="/api/v1/health", tags=["Health"])'
        assert extract_router_prefix(source) == "/api/v1/health"

    def test_extract_router_prefix_no_prefix(self):
        """Returns empty string when no prefix is set."""
        source = "router = APIRouter()"
        assert extract_router_prefix(source) == ""

    def test_extract_endpoints_from_file(self, tmp_api_dir: Path):
        """Endpoints are extracted from a router file."""
        endpoints = extract_endpoints_from_file(tmp_api_dir / "health.py")
        assert len(endpoints) == 2
        methods = {e.method for e in endpoints}
        assert methods == {"GET"}
        paths = {e.path for e in endpoints}
        assert "/api/v1/health" in paths
        assert "/api/v1/health/deep" in paths

    def test_auth_detection(self, tmp_api_dir: Path):
        """Auth dependency detection works."""
        endpoints = extract_endpoints_from_file(tmp_api_dir / "patients.py")
        assert len(endpoints) == 4
        # All patient endpoints use get_current_user
        for ep in endpoints:
            assert ep.auth_required is True

    def test_no_auth_endpoints(self, tmp_api_dir: Path):
        """Health endpoints have no auth."""
        endpoints = extract_endpoints_from_file(tmp_api_dir / "health.py")
        for ep in endpoints:
            assert ep.auth_required is False

    def test_scan_api_directory(self, tmp_api_dir: Path):
        """Scanning directory finds endpoints from all files."""
        endpoints = scan_api_directory(tmp_api_dir)
        assert len(endpoints) == 6  # 2 health + 4 patients

    def test_compute_stats(self, tmp_api_dir: Path):
        """Stats computation returns expected shape."""
        endpoints = scan_api_directory(tmp_api_dir)
        stats = compute_stats(endpoints)
        assert stats["total_endpoints"] == 6
        assert "GET" in stats["by_method"]
        assert isinstance(stats["auth_required"], int)

    def test_markdown_output(self, tmp_api_dir: Path):
        """Markdown output contains expected sections."""
        endpoints = scan_api_directory(tmp_api_dir)
        stats = compute_stats(endpoints)
        output = format_markdown(endpoints, stats)
        assert "# API Endpoint Inventory" in output
        assert "## Summary" in output
        assert "## Endpoints" in output
        assert "| Method |" in output

    def test_csv_output(self, tmp_api_dir: Path):
        """CSV output is parseable."""
        endpoints = scan_api_directory(tmp_api_dir)
        output = format_csv_output(endpoints)
        lines = output.strip().split("\n")
        assert len(lines) == 7  # header + 6 endpoints
        assert "method,path,function_name" in lines[0]

    def test_json_output_parseable(self, tmp_api_dir: Path):
        """JSON output is valid JSON."""
        endpoints = scan_api_directory(tmp_api_dir)
        stats = compute_stats(endpoints)
        output = format_json_output(endpoints, stats)
        data = json.loads(output)
        assert "stats" in data
        assert "endpoints" in data
        assert len(data["endpoints"]) == 6

    def test_maturity_tier_detection(self, tmp_api_dir: Path):
        """Maturity tier is set based on filename."""
        endpoints = extract_endpoints_from_file(tmp_api_dir / "health.py")
        for ep in endpoints:
            assert ep.maturity_tier == "Production"

        endpoints = extract_endpoints_from_file(tmp_api_dir / "patients.py")
        for ep in endpoints:
            assert ep.maturity_tier == "Production"

    def test_run_endpoint_inventory_on_real_codebase(self):
        """Run inventory on the actual API directory (smoke test)."""
        real_dir = Path(__file__).resolve().parent.parent / "app" / "api"
        if not real_dir.is_dir():
            pytest.skip("Real API directory not found")
        endpoints, stats = run_endpoint_inventory(real_dir)
        assert stats["total_endpoints"] > 0
        assert isinstance(endpoints, list)
