"""Tests for global exception handlers."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.api.error_handlers import register_all_exception_handlers
from app.api.errors import (
    APIError,
    AuthenticationError,
    ConflictError,
    ErrorCode,
    ErrorDetail,
    InternalError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


# ============================================================================
# Test App Setup
# ============================================================================


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with exception handlers registered."""
    app = FastAPI()
    register_all_exception_handlers(app)

    class TestInput(BaseModel):
        name: str = Field(..., min_length=1, max_length=50)
        age: int = Field(..., ge=0, le=150)

    @app.get("/raise-not-found")
    async def raise_not_found():
        raise NotFoundError(
            message="Patient P123 not found",
            error_code=ErrorCode.NOT_FOUND_PATIENT,
        )

    @app.get("/raise-validation")
    async def raise_validation():
        raise ValidationError(
            message="Invalid input",
            error_code=ErrorCode.VALIDATION_ERROR,
            details=[
                ErrorDetail(field="code", message="Invalid ICD-10 format", value="XYZ")
            ],
        )

    @app.get("/raise-auth")
    async def raise_auth():
        raise AuthenticationError(
            message="Token expired",
            error_code=ErrorCode.AUTH_EXPIRED_TOKEN,
        )

    @app.get("/raise-conflict")
    async def raise_conflict():
        raise ConflictError(
            message="Document already exists",
            error_code=ErrorCode.CONFLICT_DOCUMENT_EXISTS,
        )

    @app.get("/raise-rate-limit")
    async def raise_rate_limit():
        raise RateLimitError(
            message="Rate limit exceeded",
            retry_after=60,
        )

    @app.get("/raise-internal")
    async def raise_internal():
        raise InternalError(
            message="Database connection failed",
            error_code=ErrorCode.INTERNAL_DATABASE_ERROR,
        )

    @app.get("/raise-unhandled")
    async def raise_unhandled():
        raise RuntimeError("Something unexpected happened")

    @app.post("/validate-body")
    async def validate_body(body: TestInput):
        return {"name": body.name, "age": body.age}

    @app.get("/raise-http-404")
    async def raise_http_404():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Resource not found")

    @app.get("/raise-http-403")
    async def raise_http_403():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")

    return app


@pytest.fixture
def client():
    """Create test client."""
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Tests
# ============================================================================


class TestErrorResponseFormat:
    """Test that all error responses follow the standardized format."""

    def test_error_response_has_required_fields(self, client):
        """All error responses must have error_code, message, timestamp, path."""
        response = client.get("/raise-not-found")
        assert response.status_code == 404
        data = response.json()

        assert "error_code" in data
        assert "message" in data
        assert "timestamp" in data
        assert "path" in data

    def test_error_response_error_code_is_string(self, client):
        """error_code should be a string matching ErrorCode enum."""
        response = client.get("/raise-not-found")
        data = response.json()
        assert data["error_code"] == "NOT_FOUND_PATIENT"

    def test_error_response_path_matches_request(self, client):
        """path should match the request URL."""
        response = client.get("/raise-not-found")
        data = response.json()
        assert data["path"] == "/raise-not-found"

    def test_error_response_timestamp_is_iso8601(self, client):
        """timestamp should be ISO 8601 format."""
        response = client.get("/raise-not-found")
        data = response.json()
        # Should parse without error
        from datetime import datetime
        assert datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))


class TestNotFoundError:
    """Test 404 error handling."""

    def test_not_found_returns_404(self, client):
        response = client.get("/raise-not-found")
        assert response.status_code == 404

    def test_not_found_message(self, client):
        response = client.get("/raise-not-found")
        assert response.json()["message"] == "Patient P123 not found"

    def test_not_found_error_code(self, client):
        response = client.get("/raise-not-found")
        assert response.json()["error_code"] == "NOT_FOUND_PATIENT"


class TestValidationError:
    """Test 400/422 validation error handling."""

    def test_validation_error_returns_400(self, client):
        response = client.get("/raise-validation")
        assert response.status_code == 400

    def test_validation_error_has_details(self, client):
        response = client.get("/raise-validation")
        data = response.json()
        assert len(data["details"]) == 1
        assert data["details"][0]["field"] == "code"
        assert data["details"][0]["message"] == "Invalid ICD-10 format"

    def test_request_body_validation_returns_422(self, client):
        """Pydantic validation errors return 422 with field details."""
        response = client.post("/validate-body", json={"name": "", "age": -1})
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert len(data["details"]) > 0

    def test_request_body_missing_field(self, client):
        """Missing required fields return field-level errors."""
        response = client.post("/validate-body", json={})
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        fields = [d.get("field") for d in data["details"]]
        assert "name" in fields
        assert "age" in fields

    def test_request_body_invalid_type(self, client):
        """Wrong types return type error details."""
        response = client.post("/validate-body", json={"name": "test", "age": "not_a_number"})
        assert response.status_code == 422


class TestAuthenticationError:
    """Test 401 error handling."""

    def test_auth_error_returns_401(self, client):
        response = client.get("/raise-auth")
        assert response.status_code == 401

    def test_auth_error_has_www_authenticate_header(self, client):
        response = client.get("/raise-auth")
        assert "WWW-Authenticate" in response.headers


class TestConflictError:
    """Test 409 error handling."""

    def test_conflict_returns_409(self, client):
        response = client.get("/raise-conflict")
        assert response.status_code == 409
        assert response.json()["error_code"] == "CONFLICT_DOCUMENT_EXISTS"


class TestRateLimitError:
    """Test 429 error handling."""

    def test_rate_limit_returns_429(self, client):
        response = client.get("/raise-rate-limit")
        assert response.status_code == 429

    def test_rate_limit_has_retry_after_header(self, client):
        response = client.get("/raise-rate-limit")
        assert response.headers.get("Retry-After") == "60"


class TestInternalError:
    """Test 500 error handling."""

    def test_internal_error_returns_500(self, client):
        response = client.get("/raise-internal")
        assert response.status_code == 500
        assert response.json()["error_code"] == "INTERNAL_DATABASE_ERROR"


class TestUnhandledError:
    """Test catch-all error handling."""

    def test_unhandled_returns_500(self, client):
        response = client.get("/raise-unhandled")
        assert response.status_code == 500

    def test_unhandled_has_generic_message(self, client):
        response = client.get("/raise-unhandled")
        data = response.json()
        assert "unexpected error" in data["message"].lower()
        assert data["error_code"] == "INTERNAL_ERROR"


class TestHTTPExceptionHandling:
    """Test that FastAPI HTTPExceptions are converted to ErrorResponse."""

    def test_http_404_converted(self, client):
        response = client.get("/raise-http-404")
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND_RESOURCE"
        assert data["message"] == "Resource not found"

    def test_http_403_converted(self, client):
        response = client.get("/raise-http-403")
        assert response.status_code == 403
        data = response.json()
        assert data["error_code"] == "FORBIDDEN_INSUFFICIENT_PERMISSIONS"


class TestNonExistentRoute:
    """Test 404 for routes that don't exist."""

    def test_unknown_route_returns_404(self, client):
        response = client.get("/this-does-not-exist")
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND_RESOURCE"
