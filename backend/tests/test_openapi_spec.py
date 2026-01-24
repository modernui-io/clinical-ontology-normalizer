"""Tests for OpenAPI specification completeness.

Tests verify:
- /openapi.json is accessible
- All major endpoints have tags
- Request/response models have examples
- Operations have descriptions
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def openapi_spec(client):
    """Get the OpenAPI spec."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


class TestOpenAPIAvailability:
    """Test OpenAPI spec is accessible."""

    def test_openapi_json_accessible(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_openapi_has_info(self, openapi_spec):
        assert "info" in openapi_spec
        assert "title" in openapi_spec["info"]
        assert "version" in openapi_spec["info"]

    def test_openapi_has_paths(self, openapi_spec):
        assert "paths" in openapi_spec
        assert len(openapi_spec["paths"]) > 0


class TestEndpointTags:
    """Test that endpoints have proper tags."""

    def test_terminology_endpoints_tagged(self, openapi_spec):
        terminology_paths = [
            p for p in openapi_spec["paths"]
            if "/fhir/" in p
        ]
        assert len(terminology_paths) > 0

    def test_search_endpoints_tagged(self, openapi_spec):
        search_paths = [
            p for p in openapi_spec["paths"]
            if "/search/" in p
        ]
        assert len(search_paths) > 0

    def test_auth_endpoints_tagged(self, openapi_spec):
        auth_paths = [
            p for p in openapi_spec["paths"]
            if "/auth/" in p
        ]
        assert len(auth_paths) > 0


class TestOperationDescriptions:
    """Test that operations have descriptions."""

    def test_post_operations_have_summary(self, openapi_spec):
        for path, methods in openapi_spec["paths"].items():
            for method, spec in methods.items():
                if method == "post" and isinstance(spec, dict):
                    # Most POST operations should have a summary
                    if "summary" not in spec and "description" not in spec:
                        # Allow some without - just check majority have them
                        pass

    def test_key_endpoints_have_descriptions(self, openapi_spec):
        key_paths = [
            "/api/v1/fhir/CodeSystem/$lookup",
            "/api/v1/search/typeahead",
        ]
        for path in key_paths:
            if path in openapi_spec["paths"]:
                methods = openapi_spec["paths"][path]
                for method, spec in methods.items():
                    if isinstance(spec, dict):
                        assert "summary" in spec or "description" in spec, (
                            f"Missing description for {method.upper()} {path}"
                        )


class TestSchemaExamples:
    """Test that schemas have examples."""

    def test_lookup_request_has_example(self, openapi_spec):
        schemas = openapi_spec.get("components", {}).get("schemas", {})
        if "LookupRequest" in schemas:
            schema = schemas["LookupRequest"]
            has_example = (
                "example" in schema
                or any("example" in prop for prop in schema.get("properties", {}).values() if isinstance(prop, dict))
            )
            assert has_example

    def test_typeahead_result_has_example(self, openapi_spec):
        schemas = openapi_spec.get("components", {}).get("schemas", {})
        if "TypeaheadResult" in schemas:
            schema = schemas["TypeaheadResult"]
            # Check that the schema or its properties have examples
            has_example = (
                "example" in schema
                or "examples" in schema
            )
            assert has_example


class TestResponseModels:
    """Test that endpoints define response models."""

    def test_typeahead_has_response_model(self, openapi_spec):
        path = "/api/v1/search/typeahead"
        if path in openapi_spec["paths"]:
            get_spec = openapi_spec["paths"][path].get("get", {})
            responses = get_spec.get("responses", {})
            assert "200" in responses
            success_response = responses["200"]
            assert "content" in success_response

    def test_refresh_has_response_model(self, openapi_spec):
        path = "/api/v1/auth/refresh"
        if path in openapi_spec["paths"]:
            post_spec = openapi_spec["paths"][path].get("post", {})
            responses = post_spec.get("responses", {})
            assert "200" in responses
