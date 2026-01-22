"""Tests for Knowledge Graph error handling middleware."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.middleware.kg_error_handler import (
    KGError,
    KGErrorHandlerMiddleware,
    KGErrors,
    KGErrorType,
    handle_kg_errors,
    validate_cui,
    validate_max_hops,
    validate_patient_id,
)


class TestKGErrorType:
    """Test KGErrorType enum."""

    def test_client_error_types(self) -> None:
        """Test client error types exist."""
        assert KGErrorType.VALIDATION_ERROR.value == "validation_error"
        assert KGErrorType.NOT_FOUND.value == "not_found"
        assert KGErrorType.INVALID_CUI.value == "invalid_cui"
        assert KGErrorType.RATE_LIMITED.value == "rate_limited"

    def test_server_error_types(self) -> None:
        """Test server error types exist."""
        assert KGErrorType.DATABASE_ERROR.value == "database_error"
        assert KGErrorType.CONNECTION_ERROR.value == "connection_error"
        assert KGErrorType.TIMEOUT_ERROR.value == "timeout_error"
        assert KGErrorType.INTERNAL_ERROR.value == "internal_error"

    def test_kg_specific_error_types(self) -> None:
        """Test KG-specific error types exist."""
        assert KGErrorType.GRAPH_TRAVERSAL_ERROR.value == "graph_traversal_error"
        assert KGErrorType.EMBEDDING_ERROR.value == "embedding_error"
        assert KGErrorType.REASONING_ERROR.value == "reasoning_error"


class TestKGError:
    """Test KGError dataclass."""

    def test_error_creation(self) -> None:
        """Test creating a KG error."""
        error = KGError(
            error_type=KGErrorType.NOT_FOUND,
            message="Concept not found",
            status_code=404,
        )
        assert error.error_type == KGErrorType.NOT_FOUND
        assert error.message == "Concept not found"
        assert error.status_code == 404

    def test_error_with_details(self) -> None:
        """Test error with details."""
        error = KGError(
            error_type=KGErrorType.INVALID_CUI,
            message="Invalid CUI format",
            status_code=400,
            details={"cui": "INVALID", "expected": "CXXXXXXX"},
        )
        assert error.details["cui"] == "INVALID"
        assert error.details["expected"] == "CXXXXXXX"

    def test_retryable_error(self) -> None:
        """Test retryable error."""
        error = KGError(
            error_type=KGErrorType.DATABASE_ERROR,
            message="Connection failed",
            status_code=503,
            retryable=True,
            retry_after_seconds=30,
        )
        assert error.retryable is True
        assert error.retry_after_seconds == 30

    def test_error_str(self) -> None:
        """Test error string representation."""
        error = KGError(
            error_type=KGErrorType.NOT_FOUND,
            message="Concept not found",
            status_code=404,
        )
        assert str(error) == "not_found: Concept not found"

    def test_error_to_dict(self) -> None:
        """Test error to dictionary conversion."""
        error = KGError(
            error_type=KGErrorType.VALIDATION_ERROR,
            message="Invalid input",
            status_code=400,
            details={"field": "cui"},
            correlation_id="test-123",
        )

        data = error.to_dict()
        assert "error" in data
        assert data["error"]["type"] == "validation_error"
        assert data["error"]["message"] == "Invalid input"
        assert data["error"]["status_code"] == 400
        assert data["error"]["correlation_id"] == "test-123"
        assert data["error"]["details"]["field"] == "cui"
        assert "timestamp" in data["error"]

    def test_retryable_error_to_dict(self) -> None:
        """Test retryable error to dictionary includes retry info."""
        error = KGError(
            error_type=KGErrorType.RATE_LIMITED,
            message="Rate limited",
            status_code=429,
            retryable=True,
            retry_after_seconds=60,
        )

        data = error.to_dict()
        assert data["error"]["retryable"] is True
        assert data["error"]["retry_after_seconds"] == 60


class TestKGErrors:
    """Test KGErrors factory methods."""

    def test_not_found(self) -> None:
        """Test not found error factory."""
        error = KGErrors.not_found("Concept", "C0004096")
        assert error.error_type == KGErrorType.NOT_FOUND
        assert error.status_code == 404
        assert "C0004096" in error.message

    def test_invalid_cui(self) -> None:
        """Test invalid CUI error factory."""
        error = KGErrors.invalid_cui("INVALID", "Must start with C")
        assert error.error_type == KGErrorType.INVALID_CUI
        assert error.status_code == 400
        assert "INVALID" in error.message

    def test_invalid_query(self) -> None:
        """Test invalid query error factory."""
        error = KGErrors.invalid_query("SELECT *", "Missing WHERE clause")
        assert error.error_type == KGErrorType.INVALID_QUERY
        assert error.status_code == 400

    def test_database_error(self) -> None:
        """Test database error factory."""
        error = KGErrors.database_error("insert", "Constraint violation")
        assert error.error_type == KGErrorType.DATABASE_ERROR
        assert error.status_code == 503
        assert error.retryable is True

    def test_connection_error(self) -> None:
        """Test connection error factory."""
        error = KGErrors.connection_error("Neo4j", "Connection refused")
        assert error.error_type == KGErrorType.CONNECTION_ERROR
        assert error.status_code == 503
        assert error.retryable is True

    def test_timeout_error(self) -> None:
        """Test timeout error factory."""
        error = KGErrors.timeout_error("graph_traversal", 30.0)
        assert error.error_type == KGErrorType.TIMEOUT_ERROR
        assert error.status_code == 504
        assert error.retryable is True

    def test_rate_limited(self) -> None:
        """Test rate limited error factory."""
        error = KGErrors.rate_limited(100, 60, 30)
        assert error.error_type == KGErrorType.RATE_LIMITED
        assert error.status_code == 429
        assert error.retry_after_seconds == 30

    def test_service_unavailable(self) -> None:
        """Test service unavailable error factory."""
        error = KGErrors.service_unavailable("EmbeddingService", "Model not loaded")
        assert error.error_type == KGErrorType.SERVICE_UNAVAILABLE
        assert error.status_code == 503

    def test_validation_error(self) -> None:
        """Test validation error factory."""
        error = KGErrors.validation_error("max_hops", "Must be positive", -1)
        assert error.error_type == KGErrorType.VALIDATION_ERROR
        assert error.status_code == 400
        assert "max_hops" in error.message

    def test_graph_traversal_error(self) -> None:
        """Test graph traversal error factory."""
        error = KGErrors.graph_traversal_error("C0004096", "C0007785", "No path found")
        assert error.error_type == KGErrorType.GRAPH_TRAVERSAL_ERROR
        assert error.status_code == 500

    def test_embedding_error(self) -> None:
        """Test embedding error factory."""
        error = KGErrors.embedding_error("Sample text", "Model unavailable")
        assert error.error_type == KGErrorType.EMBEDDING_ERROR
        assert error.status_code == 500
        assert error.retryable is True

    def test_cache_error(self) -> None:
        """Test cache error factory."""
        error = KGErrors.cache_error("get", "Redis connection failed")
        assert error.error_type == KGErrorType.CACHE_ERROR
        assert error.status_code == 500

    def test_reasoning_error(self) -> None:
        """Test reasoning error factory."""
        error = KGErrors.reasoning_error("What causes diabetes?", "Knowledge graph incomplete")
        assert error.error_type == KGErrorType.REASONING_ERROR
        assert error.status_code == 500

    def test_internal_error(self) -> None:
        """Test internal error factory."""
        error = KGErrors.internal_error("Unexpected state")
        assert error.error_type == KGErrorType.INTERNAL_ERROR
        assert error.status_code == 500


class TestValidateCui:
    """Test CUI validation."""

    def test_valid_cui(self) -> None:
        """Test valid CUI passes validation."""
        assert validate_cui("C0004096") == "C0004096"

    def test_lowercase_cui(self) -> None:
        """Test lowercase CUI is normalized."""
        assert validate_cui("c0004096") == "C0004096"

    def test_cui_with_whitespace(self) -> None:
        """Test CUI with whitespace is trimmed."""
        assert validate_cui("  C0004096  ") == "C0004096"

    def test_empty_cui(self) -> None:
        """Test empty CUI raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_cui("")
        assert exc_info.value.error_type == KGErrorType.INVALID_CUI

    def test_invalid_format(self) -> None:
        """Test invalid CUI format raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_cui("INVALID")
        assert exc_info.value.error_type == KGErrorType.INVALID_CUI

    def test_wrong_prefix(self) -> None:
        """Test CUI with wrong prefix raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_cui("D0004096")
        assert exc_info.value.error_type == KGErrorType.INVALID_CUI

    def test_wrong_length(self) -> None:
        """Test CUI with wrong length raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_cui("C00040")
        assert exc_info.value.error_type == KGErrorType.INVALID_CUI

    def test_non_numeric_digits(self) -> None:
        """Test CUI with non-numeric digits raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_cui("C000409X")
        assert exc_info.value.error_type == KGErrorType.INVALID_CUI


class TestValidatePatientId:
    """Test patient ID validation."""

    def test_valid_patient_id(self) -> None:
        """Test valid patient ID passes validation."""
        assert validate_patient_id("P12345") == "P12345"

    def test_patient_id_with_whitespace(self) -> None:
        """Test patient ID with whitespace is trimmed."""
        assert validate_patient_id("  P12345  ") == "P12345"

    def test_empty_patient_id(self) -> None:
        """Test empty patient ID raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_patient_id("")
        assert exc_info.value.error_type == KGErrorType.VALIDATION_ERROR

    def test_too_short_patient_id(self) -> None:
        """Test too short patient ID raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_patient_id("AB")
        assert exc_info.value.error_type == KGErrorType.VALIDATION_ERROR

    def test_too_long_patient_id(self) -> None:
        """Test too long patient ID raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_patient_id("A" * 51)
        assert exc_info.value.error_type == KGErrorType.VALIDATION_ERROR


class TestValidateMaxHops:
    """Test max_hops validation."""

    def test_valid_max_hops(self) -> None:
        """Test valid max_hops passes validation."""
        assert validate_max_hops(3) == 3

    def test_min_max_hops(self) -> None:
        """Test minimum max_hops passes validation."""
        assert validate_max_hops(1) == 1

    def test_max_max_hops(self) -> None:
        """Test maximum max_hops passes validation."""
        assert validate_max_hops(10) == 10

    def test_zero_max_hops(self) -> None:
        """Test zero max_hops raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_max_hops(0)
        assert exc_info.value.error_type == KGErrorType.VALIDATION_ERROR

    def test_negative_max_hops(self) -> None:
        """Test negative max_hops raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_max_hops(-1)
        assert exc_info.value.error_type == KGErrorType.VALIDATION_ERROR

    def test_too_large_max_hops(self) -> None:
        """Test too large max_hops raises error."""
        with pytest.raises(KGError) as exc_info:
            validate_max_hops(11)
        assert exc_info.value.error_type == KGErrorType.VALIDATION_ERROR

    def test_custom_range(self) -> None:
        """Test custom min/max range."""
        assert validate_max_hops(5, min_value=2, max_value=8) == 5

        with pytest.raises(KGError):
            validate_max_hops(1, min_value=2, max_value=8)

        with pytest.raises(KGError):
            validate_max_hops(9, min_value=2, max_value=8)


class TestKGErrorHandlerMiddleware:
    """Test KG error handler middleware."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test FastAPI app."""
        app = FastAPI()
        app.add_middleware(KGErrorHandlerMiddleware, include_stack_trace=False)

        @app.get("/api/v1/kg/test")
        async def kg_test_endpoint():
            return {"status": "ok"}

        @app.get("/api/v1/kg/error")
        async def kg_error_endpoint():
            raise KGErrors.not_found("Concept", "C0004096")

        @app.get("/api/v1/kg/http-error")
        async def kg_http_error_endpoint():
            raise HTTPException(status_code=404, detail="Not found")

        @app.get("/api/v1/kg/unhandled")
        async def kg_unhandled_endpoint():
            raise RuntimeError("Unexpected error")

        @app.get("/api/v1/kg/retryable")
        async def kg_retryable_endpoint():
            raise KGErrors.rate_limited(100, 60, 30)

        @app.get("/api/v1/other/test")
        async def other_test_endpoint():
            return {"status": "ok"}

        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_successful_request(self, client: TestClient) -> None:
        """Test successful request passes through."""
        response = client.get("/api/v1/kg/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "X-Correlation-ID" in response.headers

    def test_kg_error_response(self, client: TestClient) -> None:
        """Test KG error is handled."""
        response = client.get("/api/v1/kg/error")
        assert response.status_code == 404

        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "not_found"
        assert "X-Correlation-ID" in response.headers

    def test_http_error_passthrough(self, client: TestClient) -> None:
        """Test HTTPException is handled by FastAPI's default handler.

        Note: HTTPExceptions raised in route handlers are caught by FastAPI's
        built-in exception handler before the middleware's error handling.
        This is the expected Starlette/FastAPI architecture.
        """
        response = client.get("/api/v1/kg/http-error")
        assert response.status_code == 404

        # FastAPI handles HTTPException with its default format
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not found"

    def test_unhandled_error(self, client: TestClient) -> None:
        """Test unhandled error becomes internal error."""
        response = client.get("/api/v1/kg/unhandled")
        assert response.status_code == 500

        data = response.json()
        assert data["error"]["type"] == "internal_error"

    def test_retryable_error_headers(self, client: TestClient) -> None:
        """Test retryable error includes Retry-After header."""
        response = client.get("/api/v1/kg/retryable")
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "30"

    def test_non_kg_endpoint_not_affected(self, client: TestClient) -> None:
        """Test non-KG endpoints are not affected."""
        response = client.get("/api/v1/other/test")
        assert response.status_code == 200
        # Middleware should not add correlation ID to non-KG endpoints
        # (it returns early before processing)


class TestHandleKGErrorsDecorator:
    """Test handle_kg_errors decorator."""

    @pytest.mark.asyncio
    async def test_successful_function(self) -> None:
        """Test successful function passes through."""
        @handle_kg_errors
        async def successful_func() -> dict:
            return {"result": "success"}

        result = await successful_func()
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_kg_error_reraise(self) -> None:
        """Test KGError is re-raised."""
        @handle_kg_errors
        async def kg_error_func() -> dict:
            raise KGErrors.not_found("Test", "123")

        with pytest.raises(KGError) as exc_info:
            await kg_error_func()
        assert exc_info.value.error_type == KGErrorType.NOT_FOUND

    @pytest.mark.asyncio
    async def test_http_exception_reraise(self) -> None:
        """Test HTTPException is re-raised."""
        @handle_kg_errors
        async def http_error_func() -> dict:
            raise HTTPException(status_code=401, detail="Unauthorized")

        with pytest.raises(HTTPException) as exc_info:
            await http_error_func()
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_value_error_converted(self) -> None:
        """Test ValueError is converted to validation error."""
        @handle_kg_errors
        async def value_error_func() -> dict:
            raise ValueError("Invalid input")

        with pytest.raises(KGError) as exc_info:
            await value_error_func()
        assert exc_info.value.error_type == KGErrorType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_timeout_error_converted(self) -> None:
        """Test TimeoutError is converted to timeout error."""
        @handle_kg_errors
        async def timeout_func() -> dict:
            raise TimeoutError("Operation timed out")

        with pytest.raises(KGError) as exc_info:
            await timeout_func()
        assert exc_info.value.error_type == KGErrorType.TIMEOUT_ERROR

    @pytest.mark.asyncio
    async def test_connection_error_converted(self) -> None:
        """Test ConnectionError is converted."""
        @handle_kg_errors
        async def connection_error_func() -> dict:
            raise ConnectionError("Connection refused")

        with pytest.raises(KGError) as exc_info:
            await connection_error_func()
        assert exc_info.value.error_type == KGErrorType.CONNECTION_ERROR

    @pytest.mark.asyncio
    async def test_generic_exception_converted(self) -> None:
        """Test generic exception is converted to internal error."""
        @handle_kg_errors
        async def generic_error_func() -> dict:
            raise RuntimeError("Something went wrong")

        with pytest.raises(KGError) as exc_info:
            await generic_error_func()
        assert exc_info.value.error_type == KGErrorType.INTERNAL_ERROR
