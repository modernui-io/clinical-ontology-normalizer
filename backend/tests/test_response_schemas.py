"""Tests for VP-Backend standardized API response models."""

from datetime import datetime

import pytest
from pydantic import BaseModel

from app.schemas.response import (
    APIResponse,
    ErrorDetail,
    ErrorResponse,
    PaginatedAPIResponse,
    PaginationMeta,
    ResponseMeta,
)


class TestResponseMeta:
    """Tests for ResponseMeta."""

    def test_default_timestamp(self) -> None:
        """Test that timestamp is auto-generated."""
        meta = ResponseMeta()
        assert meta.timestamp is not None
        # Verify it's a valid ISO format
        datetime.fromisoformat(meta.timestamp.replace("Z", "+00:00"))

    def test_with_request_id(self) -> None:
        """Test setting request ID."""
        meta = ResponseMeta(request_id="req-123")
        assert meta.request_id == "req-123"

    def test_with_duration(self) -> None:
        """Test setting duration."""
        meta = ResponseMeta(duration_ms=42.5)
        assert meta.duration_ms == 42.5


class TestErrorDetail:
    """Tests for ErrorDetail."""

    def test_basic_error(self) -> None:
        """Test creating a basic error."""
        error = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid email format",
        )
        assert error.code == "VALIDATION_ERROR"
        assert error.message == "Invalid email format"
        assert error.field is None

    def test_field_error(self) -> None:
        """Test error with field."""
        error = ErrorDetail(
            code="REQUIRED_FIELD",
            message="This field is required",
            field="email",
        )
        assert error.field == "email"

    def test_error_with_details(self) -> None:
        """Test error with additional details."""
        error = ErrorDetail(
            code="RATE_LIMIT",
            message="Rate limit exceeded",
            details={"retry_after": 60, "limit": 100},
        )
        assert error.details["retry_after"] == 60


class TestErrorResponse:
    """Tests for ErrorResponse."""

    def test_error_response(self) -> None:
        """Test creating an error response."""
        response = ErrorResponse(
            error=ErrorDetail(
                code="NOT_FOUND",
                message="Resource not found",
            )
        )
        assert response.success is False
        assert response.error.code == "NOT_FOUND"
        assert response.meta.timestamp is not None


class TestAPIResponse:
    """Tests for APIResponse."""

    def test_success_response(self) -> None:
        """Test creating a successful response."""
        response = APIResponse(
            success=True,
            data={"id": "123", "name": "Test"},
            message="Created successfully",
        )
        assert response.success is True
        assert response.data["id"] == "123"
        assert response.message == "Created successfully"

    def test_generic_type(self) -> None:
        """Test that generic types work."""

        class User(BaseModel):
            id: str
            name: str

        user = User(id="u1", name="Alice")
        response: APIResponse[User] = APIResponse(
            success=True,
            data=user,
        )
        assert response.data.id == "u1"
        assert response.data.name == "Alice"

    def test_ok_factory(self) -> None:
        """Test the ok() factory method."""
        response = APIResponse.ok(
            data=["item1", "item2", "item3"],
            message="Items retrieved",
            request_id="req-456",
        )
        assert response.success is True
        assert len(response.data) == 3
        assert response.message == "Items retrieved"
        assert response.meta.request_id == "req-456"

    def test_fail_factory(self) -> None:
        """Test the fail() factory method."""
        response = APIResponse.fail(
            message="Operation failed",
            request_id="req-789",
        )
        assert response.success is False
        assert response.data is None
        assert response.message == "Operation failed"

    def test_none_data(self) -> None:
        """Test response with no data."""
        response: APIResponse[None] = APIResponse(
            success=True,
            message="Deleted successfully",
        )
        assert response.success is True
        assert response.data is None


class TestPaginationMeta:
    """Tests for PaginationMeta."""

    def test_pagination_meta(self) -> None:
        """Test creating pagination metadata."""
        meta = PaginationMeta(
            page=2,
            page_size=10,
            total_items=45,
            total_pages=5,
            has_next=True,
            has_prev=True,
        )
        assert meta.page == 2
        assert meta.page_size == 10
        assert meta.total_items == 45
        assert meta.total_pages == 5
        assert meta.has_next is True
        assert meta.has_prev is True

    def test_first_page(self) -> None:
        """Test first page pagination."""
        meta = PaginationMeta(
            page=1,
            page_size=20,
            total_items=100,
            total_pages=5,
            has_next=True,
            has_prev=False,
        )
        assert meta.has_prev is False
        assert meta.has_next is True

    def test_last_page(self) -> None:
        """Test last page pagination."""
        meta = PaginationMeta(
            page=5,
            page_size=20,
            total_items=100,
            total_pages=5,
            has_next=False,
            has_prev=True,
        )
        assert meta.has_prev is True
        assert meta.has_next is False


class TestPaginatedAPIResponse:
    """Tests for PaginatedAPIResponse."""

    def test_paginated_response(self) -> None:
        """Test creating a paginated response."""
        items = [{"id": i} for i in range(10)]

        response = PaginatedAPIResponse(
            success=True,
            data=items,
            pagination=PaginationMeta(
                page=1,
                page_size=10,
                total_items=50,
                total_pages=5,
                has_next=True,
                has_prev=False,
            ),
        )

        assert response.success is True
        assert len(response.data) == 10
        assert response.pagination.total_items == 50

    def test_create_factory(self) -> None:
        """Test the create() factory method."""
        items = ["a", "b", "c"]

        response = PaginatedAPIResponse.create(
            data=items,
            page=2,
            page_size=3,
            total_items=10,
        )

        assert response.success is True
        assert response.data == ["a", "b", "c"]
        assert response.pagination.page == 2
        assert response.pagination.page_size == 3
        assert response.pagination.total_items == 10
        assert response.pagination.total_pages == 4  # 10 / 3 = 3.33 -> 4
        assert response.pagination.has_prev is True
        assert response.pagination.has_next is True

    def test_create_edge_cases(self) -> None:
        """Test create() with edge cases."""
        # Empty list
        response = PaginatedAPIResponse.create(
            data=[],
            page=1,
            page_size=10,
            total_items=0,
        )
        assert response.pagination.total_pages == 0
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is False

        # Single page
        response = PaginatedAPIResponse.create(
            data=[1, 2, 3],
            page=1,
            page_size=10,
            total_items=3,
        )
        assert response.pagination.total_pages == 1
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is False

    def test_generic_type(self) -> None:
        """Test that generic types work with pagination."""

        class Item(BaseModel):
            id: int
            name: str

        items = [Item(id=1, name="First"), Item(id=2, name="Second")]

        response: PaginatedAPIResponse[Item] = PaginatedAPIResponse.create(
            data=items,
            page=1,
            page_size=10,
            total_items=2,
        )

        assert response.data[0].id == 1
        assert response.data[1].name == "Second"


class TestResponseSerialization:
    """Tests for response serialization."""

    def test_api_response_json(self) -> None:
        """Test that APIResponse serializes to valid JSON."""
        response = APIResponse.ok(
            data={"key": "value"},
            message="Success",
        )

        json_str = response.model_dump_json()
        assert "success" in json_str
        assert "key" in json_str

    def test_paginated_response_json(self) -> None:
        """Test that PaginatedAPIResponse serializes to valid JSON."""
        response = PaginatedAPIResponse.create(
            data=[1, 2, 3],
            page=1,
            page_size=10,
            total_items=3,
        )

        json_str = response.model_dump_json()
        assert "pagination" in json_str
        assert "total_items" in json_str

    def test_error_response_json(self) -> None:
        """Test that ErrorResponse serializes to valid JSON."""
        response = ErrorResponse(
            error=ErrorDetail(
                code="SERVER_ERROR",
                message="Internal server error",
            )
        )

        json_str = response.model_dump_json()
        assert "error" in json_str
        assert "SERVER_ERROR" in json_str
