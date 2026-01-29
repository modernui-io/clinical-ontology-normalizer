"""VP-Backend: Standardized API response models.

Provides consistent response structure across all API endpoints:
- APIResponse: Standard wrapper with success flag, message, data, and metadata
- ErrorResponse: Standard error format with code, message, and details
- PaginatedAPIResponse: Paginated data with consistent pagination metadata

Usage:
    from app.schemas.response import APIResponse, PaginatedAPIResponse

    @router.get("/items")
    async def list_items() -> APIResponse[list[Item]]:
        items = await get_items()
        return APIResponse(
            success=True,
            data=items,
            meta={"count": len(items)}
        )
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Metadata included in all API responses."""

    request_id: str | None = Field(default=None, description="Unique request identifier for tracing")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO8601 timestamp of the response",
    )
    duration_ms: float | None = Field(default=None, description="Request processing time in milliseconds")


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(description="Machine-readable error code (e.g., 'VALIDATION_ERROR')")
    message: str = Field(description="Human-readable error message")
    field: str | None = Field(default=None, description="Field that caused the error (for validation errors)")
    details: dict[str, Any] | None = Field(default=None, description="Additional error context")


class ErrorResponse(BaseModel):
    """Standard error response format.

    Used for all API error responses to ensure consistent error handling.
    """

    success: bool = Field(default=False, description="Always False for errors")
    error: ErrorDetail = Field(description="Error details")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper.

    Provides consistent structure for all successful API responses:
    - success: Boolean indicating if the request succeeded
    - data: The actual response payload (generic type T)
    - message: Optional human-readable message
    - meta: Request metadata (request_id, timestamp, duration)

    Example:
        >>> response = APIResponse(
        ...     success=True,
        ...     data={"id": "123", "name": "Test"},
        ...     message="Item created successfully"
        ... )
    """

    success: bool = Field(default=True, description="Whether the request succeeded")
    data: T | None = Field(default=None, description="Response payload")
    message: str | None = Field(default=None, description="Human-readable status message")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata")

    @classmethod
    def ok(cls, data: T, message: str | None = None, **meta_kwargs: Any) -> "APIResponse[T]":
        """Create a successful response.

        Args:
            data: Response payload
            message: Optional success message
            **meta_kwargs: Additional metadata fields

        Returns:
            APIResponse with success=True
        """
        return cls(
            success=True,
            data=data,
            message=message,
            meta=ResponseMeta(**meta_kwargs),
        )

    @classmethod
    def fail(cls, message: str, **meta_kwargs: Any) -> "APIResponse[None]":
        """Create a failed response (for soft failures, not HTTP errors).

        Args:
            message: Failure message
            **meta_kwargs: Additional metadata fields

        Returns:
            APIResponse with success=False
        """
        return cls(
            success=False,
            data=None,
            message=message,
            meta=ResponseMeta(**meta_kwargs),
        )


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(ge=1, le=1000, description="Number of items per page")
    total_items: int = Field(ge=0, description="Total number of items across all pages")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there are more pages after this one")
    has_prev: bool = Field(description="Whether there are pages before this one")


class PaginatedAPIResponse(BaseModel, Generic[T]):
    """Paginated API response wrapper.

    Used for list endpoints that support pagination:
    - data: List of items for the current page
    - pagination: Page number, size, total counts
    - meta: Request metadata

    Example:
        >>> response = PaginatedAPIResponse(
        ...     success=True,
        ...     data=[item1, item2, item3],
        ...     pagination=PaginationMeta(
        ...         page=1,
        ...         page_size=10,
        ...         total_items=100,
        ...         total_pages=10,
        ...         has_next=True,
        ...         has_prev=False
        ...     )
        ... )
    """

    success: bool = Field(default=True, description="Whether the request succeeded")
    data: list[T] = Field(default_factory=list, description="List of items for the current page")
    pagination: PaginationMeta = Field(description="Pagination metadata")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata")

    @classmethod
    def create(
        cls,
        data: list[T],
        page: int,
        page_size: int,
        total_items: int,
        **meta_kwargs: Any,
    ) -> "PaginatedAPIResponse[T]":
        """Create a paginated response with calculated pagination metadata.

        Args:
            data: List of items for the current page
            page: Current page number (1-indexed)
            page_size: Items per page
            total_items: Total items across all pages
            **meta_kwargs: Additional metadata fields

        Returns:
            PaginatedAPIResponse with calculated pagination
        """
        total_pages = (total_items + page_size - 1) // page_size if page_size > 0 else 0

        return cls(
            success=True,
            data=data,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1,
            ),
            meta=ResponseMeta(**meta_kwargs),
        )
