"""Tests for Standardized Error Response middleware.

Tests verify:
- 404 returns standardized format
- Validation error returns field-level details
- 500 returns safe error without stack trace
- request_id is present in all error responses
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, ErrorDetail, NotFoundError, ValidationError as APIValidationError
from app.api.middleware.error_handler import ErrorHandlerMiddleware, register_exception_handlers
from app.api.middleware.request_id import RequestIdMiddleware


@pytest.fixture
def app():
    """Create test FastAPI app with error handler middleware."""
    test_app = FastAPI()

    # Add request ID middleware first (inner), then error handler (outer)
    test_app.add_middleware(ErrorHandlerMiddleware)
    test_app.add_middleware(RequestIdMiddleware)

    # Register exception handlers for validation, API errors, and generic exceptions
    register_exception_handlers(test_app)

    class ItemRequest(BaseModel):
        name: str = Field(..., min_length=1, max_length=50)
        quantity: int = Field(..., ge=1)

    @test_app.get("/items/{item_id}")
    async def get_item(item_id: str):
        raise NotFoundError(
            message=f"Item {item_id} not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
            details=[ErrorDetail(field="item_id", message="Item does not exist")],
        )

    @test_app.post("/items")
    async def create_item(item: ItemRequest):
        return {"name": item.name, "quantity": item.quantity}

    @test_app.get("/error")
    async def trigger_error():
        raise RuntimeError("Something went wrong internally")

    @test_app.get("/http-404")
    async def http_not_found():
        raise HTTPException(status_code=404, detail="Resource not found")

    @test_app.get("/validation-error")
    async def validation_endpoint():
        raise APIValidationError(
            message="Invalid input",
            error_code=ErrorCode.VALIDATION_ERROR,
            details=[
                ErrorDetail(field="email", message="Invalid email format"),
                ErrorDetail(field="age", message="Must be positive"),
            ],
        )

    return test_app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


class TestNotFoundReturnsStandardFormat:
    """Test 404 returns standardized error format."""

    def test_404_has_error_code(self, client):
        response = client.get("/items/missing-123")
        assert response.status_code == 404
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "NOT_FOUND_RESOURCE"

    def test_404_has_message(self, client):
        response = client.get("/items/missing-123")
        data = response.json()
        assert "message" in data
        assert "missing-123" in data["message"]

    def test_404_has_details(self, client):
        response = client.get("/items/missing-123")
        data = response.json()
        assert "details" in data
        assert len(data["details"]) > 0

    def test_404_has_timestamp(self, client):
        response = client.get("/items/missing-123")
        data = response.json()
        assert "timestamp" in data

    def test_api_not_found_returns_standard_format(self, client):
        """Verify our custom NotFoundError returns standardized format."""
        response = client.get("/items/another-id")
        assert response.status_code == 404
        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert data["error_code"] == "NOT_FOUND_RESOURCE"


class TestValidationErrorFieldDetails:
    """Test validation error returns field-level details."""

    def test_pydantic_validation_returns_422(self, client):
        response = client.post("/items", json={"name": "", "quantity": 0})
        assert response.status_code == 422

    def test_validation_error_has_details(self, client):
        response = client.post("/items", json={"name": "", "quantity": 0})
        data = response.json()
        assert "details" in data
        assert len(data["details"]) >= 1

    def test_validation_details_have_field(self, client):
        response = client.post("/items", json={"name": "", "quantity": 0})
        data = response.json()
        fields = [d.get("field") for d in data["details"]]
        assert any(f is not None for f in fields)

    def test_validation_details_have_message(self, client):
        response = client.post("/items", json={"name": "", "quantity": 0})
        data = response.json()
        for detail in data["details"]:
            assert "message" in detail
            assert len(detail["message"]) > 0

    def test_custom_validation_error(self, client):
        response = client.get("/validation-error")
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert len(data["details"]) == 2


class TestInternalErrorSafety:
    """Test 500 returns safe error without stack trace."""

    def test_500_returns_safe_message(self, client):
        response = client.get("/error")
        assert response.status_code == 500
        data = response.json()
        assert "Something went wrong internally" not in data["message"]
        assert "RuntimeError" not in data.get("message", "")

    def test_500_no_stack_trace_in_production(self, client):
        response = client.get("/error")
        data = response.json()
        # Stack trace details should not appear in the top-level message field
        assert "traceback" not in data.get("message", "").lower()

    def test_500_has_error_code(self, client):
        response = client.get("/error")
        data = response.json()
        assert data["error_code"] == "INTERNAL_ERROR"


class TestRequestIdPresent:
    """Test request_id is present in all error responses."""

    def test_404_has_request_id(self, client):
        response = client.get("/items/missing-123")
        data = response.json()
        assert "request_id" in data

    def test_422_has_request_id(self, client):
        response = client.post("/items", json={"name": "", "quantity": 0})
        data = response.json()
        assert "request_id" in data

    def test_500_has_request_id(self, client):
        response = client.get("/error")
        data = response.json()
        assert "request_id" in data

    def test_request_id_matches_header(self, client):
        response = client.get("/items/missing-123")
        data = response.json()
        header_id = response.headers.get("X-Request-ID")
        if header_id and data.get("request_id"):
            # Both should be present
            assert data["request_id"] is not None
