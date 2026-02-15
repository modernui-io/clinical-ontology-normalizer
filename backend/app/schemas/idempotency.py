"""Schemas for idempotency middleware responses.

P2-020: Provides typed response models for idempotency cache hits
and conflict errors returned by IdempotencyMiddleware.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IdempotencyReplayedResponse(BaseModel):
    """Indicates the response was replayed from the idempotency cache."""

    idempotency_key: str = Field(..., description="The idempotency key that matched")
    replayed: bool = Field(True, description="Whether this is a replayed response")
    original_status_code: int = Field(..., description="Status code of the original response")


class IdempotencyConflictResponse(BaseModel):
    """Returned when a concurrent request with the same idempotency key is in flight."""

    detail: str = Field(
        "A request with this Idempotency-Key is already being processed",
        description="Conflict detail message",
    )


class IdempotencyKeyTooLongResponse(BaseModel):
    """Returned when the Idempotency-Key header exceeds maximum length."""

    detail: str = Field(
        ...,
        description="Validation error detail",
    )
