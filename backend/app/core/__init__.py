"""Core application configuration and utilities."""

from app.core.audit import AuditAction, AuditEvent, log_audit, log_data_access, log_export
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.privacy import PrivacyGuard, detect_potential_phi, validate_no_real_phi
from app.core.security import (
    PUBLIC_ROUTES,
    RequireAuth,
    RequireTenant,
    TenantContext,
    get_api_keys,
    is_auth_enabled,
    is_public_route,
    optional_verify_api_key,
    verify_api_key,
)

__all__ = [
    # Config
    "settings",
    # Database
    "Base",
    "get_db",
    # Security
    "RequireAuth",
    "RequireTenant",
    "TenantContext",
    "verify_api_key",
    "get_api_keys",
    "is_auth_enabled",
    "is_public_route",
    "optional_verify_api_key",
    "PUBLIC_ROUTES",
    # Audit
    "AuditAction",
    "AuditEvent",
    "log_audit",
    "log_data_access",
    "log_export",
    # Privacy
    "PrivacyGuard",
    "detect_potential_phi",
    "validate_no_real_phi",
]
