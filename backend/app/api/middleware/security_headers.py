"""Security Headers Middleware.

VP-Security: Adds security headers to all responses per OWASP recommendations.
VP-Security-4: HSTS only sent in production to avoid dev issues with self-signed certs.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    VP-Security-4: Implements OWASP security headers best practices:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filtering (legacy browsers)
    - Strict-Transport-Security: Enforces HTTPS (production only)
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    - Cache-Control: Prevents caching of sensitive data
    - Content-Security-Policy: Restricts resource loading (production only)
    """

    def __init__(self, app, enable_hsts: bool | None = None):
        """Initialize security headers middleware.

        Args:
            app: ASGI application
            enable_hsts: Override HSTS behavior. If None, uses settings.is_production.
        """
        super().__init__(app)
        self._enable_hsts = enable_hsts if enable_hsts is not None else settings.is_production

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS filter (for legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # VP-Security-4: Enforce HTTPS only in production
        # Avoids issues with self-signed certs in development
        if self._enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features (disable unnecessary APIs)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # VP-Security-4: Content Security Policy for API responses
        # Restricts what can be loaded - mainly for API error pages that might render HTML
        if self._enable_hsts:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                "frame-ancestors 'none'; "
                "form-action 'none'"
            )

        # Prevent caching of API responses with sensitive data
        # Individual endpoints can override this if caching is safe
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response
