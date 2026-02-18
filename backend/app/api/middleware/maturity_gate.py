"""API Maturity Gate Middleware.

Adds an X-API-Maturity response header to every request and optionally
blocks SCAFFOLD endpoints when BLOCK_SCAFFOLD_ENDPOINTS is enabled.

Also adds deprecation headers for routes listed in DEPRECATION_SCHEDULE
and experimental warnings for scaffold routes.
"""

from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.api_maturity import (
    DEPRECATION_SCHEDULE,
    DeprecationInfo,
    EndpointMaturity,
    classify_path,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class MaturityGateMiddleware(BaseHTTPMiddleware):
    """Classify every request by maturity tier and block scaffold in production."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        maturity = classify_path(path)

        # Block scaffold endpoints when configured
        if maturity == EndpointMaturity.SCAFFOLD and settings.block_scaffold_endpoints:
            logger.info("Blocked scaffold endpoint: %s", path)
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"},
            )

        response = await call_next(request)

        # Tag every response with its maturity tier
        if maturity is not None:
            response.headers["X-API-Maturity"] = maturity.value

        # Data-driven deprecation headers
        dep_info = self._get_deprecation_info(path)
        if dep_info:
            response.headers["X-API-Stability"] = "deprecated"
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = dep_info.sunset_date
            if dep_info.successor:
                response.headers["Link"] = (
                    f'</api/v1{dep_info.successor}>; rel="successor-version"'
                )
            if os.getenv("ENV", "development").lower() in ("production", "prod"):
                logger.warning(
                    "Deprecated route called: %s %s — %s",
                    request.method,
                    path,
                    dep_info.message or "deprecated",
                )
        # Scaffold warning headers
        elif maturity == EndpointMaturity.SCAFFOLD:
            response.headers["X-API-Stability"] = "experimental"
            response.headers["Warning"] = '299 - "Experimental API - not for production use"'

        return response

    @staticmethod
    def _get_deprecation_info(path: str) -> DeprecationInfo | None:
        api_prefix = "/api/v1"
        stripped = path[len(api_prefix):] if path.startswith(api_prefix) else path
        for prefix, info in DEPRECATION_SCHEDULE.items():
            if stripped == prefix or stripped.startswith(prefix + "/"):
                return info
        return None
