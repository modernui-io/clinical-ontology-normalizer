"""Middleware components for Clinical Ontology Normalizer API."""

from app.api.middleware.audit_middleware import AuditMiddleware, AsyncAuditMiddleware
from app.api.middleware.auth_middleware import (
    CurrentUser,
    PermissionChecker,
    RoleChecker,
    get_current_active_user,
    get_current_user,
    get_current_user_optional,
    require_admin,
    require_any_permission,
    require_any_role,
    require_documents_read,
    require_documents_write,
    require_patients_read,
    require_permission,
    require_role,
)
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.request_id import RequestIdMiddleware, get_request_id

__all__ = [
    # Audit Middleware
    "AuditMiddleware",
    "AsyncAuditMiddleware",
    # Auth Middleware
    "CurrentUser",
    "PermissionChecker",
    "RoleChecker",
    "get_current_active_user",
    "get_current_user",
    "get_current_user_optional",
    "require_admin",
    "require_any_permission",
    "require_any_role",
    "require_documents_read",
    "require_documents_write",
    "require_patients_read",
    "require_permission",
    "require_role",
    # Error Handler Middleware
    "ErrorHandlerMiddleware",
    # Request ID Middleware
    "RequestIdMiddleware",
    "get_request_id",
]
