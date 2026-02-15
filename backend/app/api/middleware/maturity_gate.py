"""API Maturity Gate Middleware.

Adds an X-API-Maturity response header to every request and optionally
blocks SCAFFOLD endpoints when BLOCK_SCAFFOLD_ENDPOINTS is enabled.

Also adds X-API-Stability headers for canonical vs deprecated route
marking (P0-020).
"""

from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.api_maturity import EndpointMaturity, classify_path
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# P0-020: Canonical vs deprecated route stability classification.
# The /clinical-agent prefix is the canonical pilot route; /nlp is deprecated.
# ---------------------------------------------------------------------------
_API_PREFIX = "/api/v1"

_STABILITY_DEPRECATED_PREFIXES: tuple[str, ...] = (
    f"{_API_PREFIX}/nlp",
)

_STABILITY_PILOT_PREFIXES: tuple[str, ...] = (
    f"{_API_PREFIX}/clinical-agent",
)


class MaturityGateMiddleware(BaseHTTPMiddleware):
    """Classify every request by maturity tier and block scaffold in production."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        maturity = classify_path(path)

        # Block scaffold endpoints when configured
        if (
            maturity == EndpointMaturity.SCAFFOLD
            and settings.block_scaffold_endpoints
        ):
            logger.info("Blocked scaffold endpoint: %s", path)
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"},
            )

        response = await call_next(request)

        # Tag every response with its maturity tier
        if maturity is not None:
            response.headers["X-API-Maturity"] = maturity.value

        # P0-020: Tag deprecated NLP routes
        if any(path.startswith(p) for p in _STABILITY_DEPRECATED_PREFIXES):
            response.headers["X-API-Stability"] = "deprecated"
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2026-06-30"
            response.headers["Link"] = (
                '</api/v1/clinical-agent>; rel="successor-version"'
            )
            # Log deprecation warning in production
            if os.getenv("ENV", "development").lower() in ("production", "prod"):
                logger.warning(
                    "Deprecated NLP route called: %s %s — "
                    "migrate to /api/v1/clinical-agent (canonical pilot route)",
                    request.method,
                    path,
                )

        # P0-020: Tag canonical pilot routes
        elif any(path.startswith(p) for p in _STABILITY_PILOT_PREFIXES):
            response.headers["X-API-Stability"] = "pilot"

        return response
