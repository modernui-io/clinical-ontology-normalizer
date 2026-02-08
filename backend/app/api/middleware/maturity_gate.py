"""API Maturity Gate Middleware.

Adds an X-API-Maturity response header to every request and optionally
blocks SCAFFOLD endpoints when BLOCK_SCAFFOLD_ENDPOINTS is enabled.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.api_maturity import EndpointMaturity, classify_path
from app.core.config import settings

logger = logging.getLogger(__name__)


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

        return response
