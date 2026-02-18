"""Contract tests for Phase 3: API Maturity Labeling and Lifecycle Controls."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from app.core.api_maturity import (
    DEPRECATION_SCHEDULE,
    DeprecationInfo,
    ENDPOINT_MATURITY_REGISTRY,
    EndpointMaturity,
    classify_path,
    validate_completeness,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_router_prefixes() -> set[str]:
    """Collect all unique router prefixes registered in main.py.

    Imports each router and inspects its prefix attribute.
    """
    import app.api as api_mod

    prefixes = set()
    for attr_name in dir(api_mod):
        obj = getattr(api_mod, attr_name)
        if hasattr(obj, "prefix") and isinstance(getattr(obj, "prefix", None), str):
            prefix = obj.prefix
            # Skip routers with /api/v1 prefix (health, metrics, diagnostics)
            # — these are mounted directly on app, not under api_v1_router
            if prefix.startswith("/api/v1"):
                prefix = prefix[len("/api/v1"):]
            if prefix:
                prefixes.add(prefix)
    return prefixes


# ---------------------------------------------------------------------------
# WS1: Registry completeness
# ---------------------------------------------------------------------------

class TestRegistryCompleteness:
    """Every router prefix must have a maturity classification."""

    def test_all_router_prefixes_classified(self):
        """No router prefix should return None from classify_path."""
        prefixes = _collect_router_prefixes()
        missing = validate_completeness(prefixes)
        assert missing == [], (
            f"Unclassified router prefixes: {missing}. "
            "Add them to ENDPOINT_MATURITY_REGISTRY in api_maturity.py."
        )

    def test_registry_is_not_empty(self):
        assert len(ENDPOINT_MATURITY_REGISTRY) > 0

    def test_registry_has_all_three_tiers(self):
        tiers = {v for v in ENDPOINT_MATURITY_REGISTRY.values()}
        assert EndpointMaturity.PRODUCTION in tiers
        assert EndpointMaturity.PILOT in tiers
        assert EndpointMaturity.SCAFFOLD in tiers


# ---------------------------------------------------------------------------
# classify_path correctness
# ---------------------------------------------------------------------------

class TestClassifyPath:
    """classify_path returns correct tiers for known paths."""

    @pytest.mark.parametrize("path,expected", [
        ("/api/v1/patients", EndpointMaturity.PRODUCTION),
        ("/api/v1/patients/123", EndpointMaturity.PRODUCTION),
        ("/api/v1/documents", EndpointMaturity.PRODUCTION),
        ("/api/v1/coding", EndpointMaturity.PRODUCTION),
        ("/api/v1/drug-safety", EndpointMaturity.PRODUCTION),
        ("/api/v1/audit", EndpointMaturity.PRODUCTION),
        ("/api/v1/auth", EndpointMaturity.PRODUCTION),
        ("/api/v1/export", EndpointMaturity.PRODUCTION),
    ])
    def test_production_paths(self, path: str, expected: EndpointMaturity):
        assert classify_path(path) == expected

    @pytest.mark.parametrize("path,expected", [
        ("/api/v1/graph", EndpointMaturity.PILOT),
        ("/api/v1/graph-rag", EndpointMaturity.PILOT),
        ("/api/v1/nlp", EndpointMaturity.PILOT),
        ("/api/v1/nlp/extract", EndpointMaturity.PILOT),
        ("/api/v1/fhir", EndpointMaturity.PILOT),
        ("/api/v1/trials", EndpointMaturity.PILOT),
        ("/api/v1/clinical-agent", EndpointMaturity.PILOT),
        ("/api/v1/sites", EndpointMaturity.PILOT),
        ("/api/v1/consent", EndpointMaturity.PILOT),
    ])
    def test_pilot_paths(self, path: str, expected: EndpointMaturity):
        assert classify_path(path) == expected

    @pytest.mark.parametrize("path,expected", [
        ("/api/v1/federated", EndpointMaturity.SCAFFOLD),
        ("/api/v1/tefca", EndpointMaturity.SCAFFOLD),
        ("/api/v1/synthetic", EndpointMaturity.SCAFFOLD),
        ("/api/v1/voice", EndpointMaturity.SCAFFOLD),
        ("/api/v1/llm", EndpointMaturity.SCAFFOLD),
        ("/api/v1/adverse-events", EndpointMaturity.SCAFFOLD),
        ("/api/v1/biomarker-analysis", EndpointMaturity.SCAFFOLD),
    ])
    def test_scaffold_paths(self, path: str, expected: EndpointMaturity):
        assert classify_path(path) == expected

    def test_unrecognized_path_returns_none(self):
        assert classify_path("/api/v1/nonexistent-route") is None

    def test_root_returns_none(self):
        assert classify_path("/api/v1") is None
        assert classify_path("/api/v1/") is None

    def test_longest_prefix_wins(self):
        """More specific prefix should override general prefix."""
        # /graph/reasoning is PILOT, /graph is PILOT — both should be PILOT
        assert classify_path("/api/v1/graph/reasoning") == EndpointMaturity.PILOT
        # /kg/benchmark is SCAFFOLD, /kg/health is PILOT
        assert classify_path("/api/v1/kg/benchmark") == EndpointMaturity.SCAFFOLD
        assert classify_path("/api/v1/kg/health") == EndpointMaturity.PILOT


# ---------------------------------------------------------------------------
# Deprecation schedule integrity
# ---------------------------------------------------------------------------

class TestDeprecationSchedule:
    """Deprecation schedule entries must reference valid registry prefixes."""

    def test_all_deprecated_prefixes_in_registry(self):
        for prefix in DEPRECATION_SCHEDULE:
            maturity = classify_path(f"/api/v1{prefix}")
            assert maturity is not None, (
                f"DEPRECATION_SCHEDULE prefix '{prefix}' not found in registry"
            )

    def test_deprecation_info_has_sunset_date(self):
        for prefix, info in DEPRECATION_SCHEDULE.items():
            assert info.sunset_date, f"Missing sunset_date for {prefix}"

    def test_nlp_deprecation_entry(self):
        assert "/nlp" in DEPRECATION_SCHEDULE
        info = DEPRECATION_SCHEDULE["/nlp"]
        assert info.sunset_date == "2026-06-30"
        assert info.successor == "/clinical-agent"


# ---------------------------------------------------------------------------
# Header emission (middleware integration)
# ---------------------------------------------------------------------------

class TestMaturityHeaders:
    """MaturityGateMiddleware emits correct headers."""

    @pytest.fixture
    def client(self):
        """Create a test client with middleware active.

        follow_redirects=False prevents redirect loops for routes that
        redirect (e.g. /graph -> /graph/).  The middleware still sets
        headers on the redirect response itself.
        """
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app, raise_server_exceptions=False, follow_redirects=False)

    def test_production_route_has_maturity_header(self, client):
        response = client.get("/api/v1/patients")
        assert response.headers.get("X-API-Maturity") == "production"

    def test_pilot_route_has_maturity_header(self, client):
        response = client.get("/api/v1/graph")
        assert response.headers.get("X-API-Maturity") == "pilot"

    def test_scaffold_route_has_maturity_header(self, client):
        with patch("app.core.config.settings.block_scaffold_endpoints", False):
            response = client.get("/api/v1/federated")
            assert response.headers.get("X-API-Maturity") == "scaffold"

    def test_deprecated_nlp_headers(self, client):
        response = client.get("/api/v1/nlp")
        assert response.headers.get("Deprecation") == "true"
        assert response.headers.get("Sunset") == "2026-06-30"
        assert "successor-version" in response.headers.get("Link", "")
        assert response.headers.get("X-API-Stability") == "deprecated"

    def test_scaffold_experimental_headers(self, client):
        with patch("app.core.config.settings.block_scaffold_endpoints", False):
            response = client.get("/api/v1/federated")
            assert response.headers.get("X-API-Stability") == "experimental"
            assert "299" in response.headers.get("Warning", "")
            assert "Experimental API" in response.headers.get("Warning", "")


# ---------------------------------------------------------------------------
# OpenAPI extensions
# ---------------------------------------------------------------------------

class TestOpenAPIExtensions:
    """OpenAPI schema includes maturity extensions."""

    @pytest.fixture
    def openapi_schema(self):
        from app.main import app
        # Clear cached schema so custom_openapi runs fresh
        app.openapi_schema = None
        return app.openapi()

    def test_path_operations_have_x_maturity(self, openapi_schema):
        paths = openapi_schema.get("paths", {})
        assert len(paths) > 0, "OpenAPI schema has no paths"
        tagged_count = 0
        for path, methods in paths.items():
            for method, info in methods.items():
                if isinstance(info, dict) and "x-maturity" in info:
                    tagged_count += 1
                    assert info["x-maturity"] in ("production", "pilot", "scaffold")
        assert tagged_count > 0, "No path operations have x-maturity"

    def test_tags_have_x_maturity(self, openapi_schema):
        tags = openapi_schema.get("tags", [])
        assert len(tags) > 0, "OpenAPI schema has no tags"
        for tag in tags:
            assert "x-maturity" in tag, (
                f"Tag '{tag['name']}' missing x-maturity extension"
            )
            assert tag["x-maturity"] in ("production", "pilot", "scaffold")

    def test_production_tag_maturity(self, openapi_schema):
        tags = {t["name"]: t for t in openapi_schema.get("tags", [])}
        assert tags["Patients"]["x-maturity"] == "production"
        assert tags["Documents"]["x-maturity"] == "production"

    def test_pilot_tag_maturity(self, openapi_schema):
        tags = {t["name"]: t for t in openapi_schema.get("tags", [])}
        assert tags["FHIR"]["x-maturity"] == "pilot"
        assert tags["Graph"]["x-maturity"] == "pilot"
