"""Tests for CISO-9 RBAC Permission Framework (Phase 1).

Covers:
- Permission and Role enum completeness
- ROLE_PERMISSIONS mapping correctness
- PermissionChecker allow/deny behaviour
- Demo-mode (auth disabled) bypass
- Permission denial audit logging
- Per-role endpoint access matrix
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException, Request

from app.core.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    PermissionChecker,
    Role,
    get_role_permissions,
    require_permissions,
    role_has_permission,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(role: Role | None = None) -> Request:
    """Build a minimal Request-like object for PermissionChecker.

    Sets ``request.state.user`` with a ``roles`` attribute so that
    ``_resolve_user_role`` can find the role.
    """
    scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
    request = Request(scope)
    if role is not None:
        request.state.user = SimpleNamespace(roles=[role.value])
    else:
        # No user on the request
        request.state  # ensure .state exists (auto-created by Starlette)
    return request


# ---------------------------------------------------------------------------
# 1. Enum completeness
# ---------------------------------------------------------------------------

class TestEnumCompleteness:
    """Verify that the Permission and Role enums contain the expected members."""

    def test_permission_enum_has_all_expected_members(self) -> None:
        expected = {
            "READ_PATIENTS",
            "WRITE_PATIENTS",
            "READ_TRIALS",
            "WRITE_TRIALS",
            "SCREEN_PATIENTS",
            "READ_DOCUMENTS",
            "WRITE_DOCUMENTS",
            "READ_AUDIT",
            "ADMIN",
            "READ_ANALYTICS",
            "MANAGE_USERS",
            "READ_CLINICAL_FACTS",
            "WRITE_CLINICAL_FACTS",
            "EXPORT_DATA",
            "READ_LINEAGE",
        }
        actual = {p.name for p in Permission}
        assert actual == expected

    def test_role_enum_has_all_expected_members(self) -> None:
        expected = {"ADMIN", "PROVIDER", "COORDINATOR", "ANALYST", "VIEWER", "SYSTEM"}
        actual = {r.name for r in Role}
        assert actual == expected

    def test_permission_count(self) -> None:
        assert len(Permission) == 15

    def test_role_count(self) -> None:
        assert len(Role) == 6


# ---------------------------------------------------------------------------
# 2. Role-permission mapping
# ---------------------------------------------------------------------------

class TestRolePermissionMapping:
    """Verify that ROLE_PERMISSIONS has the correct assignments."""

    def test_every_role_is_in_mapping(self) -> None:
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"{role} missing from ROLE_PERMISSIONS"

    def test_admin_has_all_permissions(self) -> None:
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        for perm in Permission:
            assert perm in admin_perms, f"ADMIN missing {perm}"

    def test_system_has_all_permissions(self) -> None:
        system_perms = ROLE_PERMISSIONS[Role.SYSTEM]
        for perm in Permission:
            assert perm in system_perms, f"SYSTEM missing {perm}"

    def test_viewer_has_minimal_permissions(self) -> None:
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert viewer_perms == frozenset({
            Permission.READ_PATIENTS,
            Permission.READ_TRIALS,
        })

    def test_viewer_cannot_write(self) -> None:
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        write_perms = {
            Permission.WRITE_PATIENTS,
            Permission.WRITE_TRIALS,
            Permission.WRITE_DOCUMENTS,
            Permission.WRITE_CLINICAL_FACTS,
        }
        for perm in write_perms:
            assert perm not in viewer_perms, f"VIEWER should not have {perm}"

    def test_provider_permissions(self) -> None:
        provider_perms = ROLE_PERMISSIONS[Role.PROVIDER]
        expected = {
            Permission.READ_PATIENTS,
            Permission.WRITE_PATIENTS,
            Permission.READ_TRIALS,
            Permission.WRITE_TRIALS,
            Permission.SCREEN_PATIENTS,
            Permission.READ_DOCUMENTS,
            Permission.WRITE_DOCUMENTS,
            Permission.READ_CLINICAL_FACTS,
            Permission.WRITE_CLINICAL_FACTS,
            Permission.READ_LINEAGE,
        }
        assert provider_perms == frozenset(expected)

    def test_coordinator_permissions(self) -> None:
        coord_perms = ROLE_PERMISSIONS[Role.COORDINATOR]
        expected = {
            Permission.READ_PATIENTS,
            Permission.READ_TRIALS,
            Permission.SCREEN_PATIENTS,
            Permission.READ_DOCUMENTS,
            Permission.READ_LINEAGE,
        }
        assert coord_perms == frozenset(expected)

    def test_analyst_permissions(self) -> None:
        analyst_perms = ROLE_PERMISSIONS[Role.ANALYST]
        expected = {
            Permission.READ_PATIENTS,
            Permission.READ_TRIALS,
            Permission.READ_ANALYTICS,
            Permission.READ_CLINICAL_FACTS,
            Permission.EXPORT_DATA,
            Permission.READ_LINEAGE,
        }
        assert analyst_perms == frozenset(expected)

    def test_role_has_permission_helper(self) -> None:
        assert role_has_permission(Role.ADMIN, Permission.ADMIN) is True
        assert role_has_permission(Role.VIEWER, Permission.ADMIN) is False

    def test_get_role_permissions_returns_frozenset(self) -> None:
        result = get_role_permissions(Role.VIEWER)
        assert isinstance(result, frozenset)
        assert Permission.READ_PATIENTS in result


# ---------------------------------------------------------------------------
# 3. PermissionChecker - allow / deny
# ---------------------------------------------------------------------------

class TestPermissionCheckerAllowDeny:
    """Test that PermissionChecker allows or denies based on role."""

    @pytest.mark.asyncio
    async def test_admin_allowed_for_any_permission(self) -> None:
        checker = PermissionChecker([Permission.ADMIN])
        request = _make_request(Role.ADMIN)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            # Should not raise
            await checker(request)

    @pytest.mark.asyncio
    async def test_viewer_denied_write_patients(self) -> None:
        checker = PermissionChecker([Permission.WRITE_PATIENTS])
        request = _make_request(Role.VIEWER)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await checker(request)
            assert exc_info.value.status_code == 403
            assert "write_patients" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_provider_allowed_read_patients(self) -> None:
        checker = PermissionChecker([Permission.READ_PATIENTS])
        request = _make_request(Role.PROVIDER)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)

    @pytest.mark.asyncio
    async def test_provider_allowed_screen_patients(self) -> None:
        checker = PermissionChecker([Permission.SCREEN_PATIENTS])
        request = _make_request(Role.PROVIDER)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)

    @pytest.mark.asyncio
    async def test_coordinator_allowed_screen_patients(self) -> None:
        checker = PermissionChecker([Permission.SCREEN_PATIENTS])
        request = _make_request(Role.COORDINATOR)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)

    @pytest.mark.asyncio
    async def test_analyst_denied_write_trials(self) -> None:
        checker = PermissionChecker([Permission.WRITE_TRIALS])
        request = _make_request(Role.ANALYST)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await checker(request)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_analyst_allowed_export_data(self) -> None:
        checker = PermissionChecker([Permission.EXPORT_DATA])
        request = _make_request(Role.ANALYST)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)

    @pytest.mark.asyncio
    async def test_multiple_permissions_all_required(self) -> None:
        """User must have ALL listed permissions."""
        checker = PermissionChecker([Permission.READ_PATIENTS, Permission.WRITE_PATIENTS])
        request = _make_request(Role.VIEWER)  # has READ but not WRITE
        with patch("app.core.permissions._is_auth_active", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await checker(request)
            assert exc_info.value.status_code == 403
            assert "write_patients" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 4. Demo-mode bypass
# ---------------------------------------------------------------------------

class TestDemoModeBypass:
    """When auth is not active, PermissionChecker should be a no-op."""

    @pytest.mark.asyncio
    async def test_bypass_when_auth_disabled(self) -> None:
        checker = PermissionChecker([Permission.ADMIN])
        request = _make_request(Role.VIEWER)  # would normally be denied
        with patch("app.core.permissions._is_auth_active", return_value=False):
            # Should NOT raise even though VIEWER lacks ADMIN
            await checker(request)

    @pytest.mark.asyncio
    async def test_bypass_when_no_user_on_request(self) -> None:
        """No user on request + auth disabled => allow."""
        checker = PermissionChecker([Permission.WRITE_PATIENTS])
        request = _make_request(role=None)
        with patch("app.core.permissions._is_auth_active", return_value=False):
            await checker(request)

    @pytest.mark.asyncio
    async def test_no_user_with_auth_active_allows_apikey_only(self) -> None:
        """No role info but auth is active => allow (API-key-only auth)."""
        checker = PermissionChecker([Permission.READ_PATIENTS])
        request = _make_request(role=None)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            # Should allow (no role means API-key-only, handled upstream)
            await checker(request)


# ---------------------------------------------------------------------------
# 5. Audit logging on denial
# ---------------------------------------------------------------------------

class TestDenialLogging:
    """Verify that permission denials are logged."""

    @pytest.mark.asyncio
    async def test_denial_is_logged_at_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        checker = PermissionChecker([Permission.ADMIN])
        request = _make_request(Role.VIEWER)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            with caplog.at_level(logging.WARNING, logger="app.core.permissions"):
                with pytest.raises(HTTPException):
                    await checker(request)

        # Check that a warning was logged with key info
        assert any("RBAC denial" in record.message for record in caplog.records)
        assert any("viewer" in record.message for record in caplog.records)
        assert any("admin" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# 6. require_permissions convenience
# ---------------------------------------------------------------------------

class TestRequirePermissionsConvenience:
    """Test the shorthand ``require_permissions`` factory."""

    def test_returns_permission_checker_instance(self) -> None:
        checker = require_permissions(Permission.READ_PATIENTS, Permission.READ_TRIALS)
        assert isinstance(checker, PermissionChecker)
        assert checker.required_permissions == [
            Permission.READ_PATIENTS,
            Permission.READ_TRIALS,
        ]


# ---------------------------------------------------------------------------
# 7. Per-role critical-endpoint access matrix
# ---------------------------------------------------------------------------

_ENDPOINT_PERMS: list[tuple[str, list[Permission]]] = [
    ("list_trials", [Permission.READ_TRIALS]),
    ("create_trial", [Permission.WRITE_TRIALS]),
    ("screen_patients", [Permission.SCREEN_PATIENTS]),
    ("list_patients", [Permission.READ_PATIENTS]),
    ("build_patient_graph", [Permission.WRITE_PATIENTS]),
    ("get_patient_facts", [Permission.READ_CLINICAL_FACTS]),
    ("get_fact_lineage", [Permission.READ_LINEAGE]),
    ("get_fn_report", [Permission.READ_ANALYTICS]),
    ("get_trial_dashboard", [Permission.READ_ANALYTICS]),
]


class TestEndpointAccessMatrix:
    """For each critical endpoint, verify that the right roles are
    allowed and wrong roles are denied.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint_name,required_perms",
        _ENDPOINT_PERMS,
        ids=[e[0] for e in _ENDPOINT_PERMS],
    )
    async def test_admin_always_allowed(
        self, endpoint_name: str, required_perms: list[Permission]
    ) -> None:
        checker = PermissionChecker(required_perms)
        request = _make_request(Role.ADMIN)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)

    @pytest.mark.asyncio
    async def test_viewer_denied_screening(self) -> None:
        checker = PermissionChecker([Permission.SCREEN_PATIENTS])
        request = _make_request(Role.VIEWER)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await checker(request)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_denied_analytics(self) -> None:
        checker = PermissionChecker([Permission.READ_ANALYTICS])
        request = _make_request(Role.VIEWER)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            with pytest.raises(HTTPException):
                await checker(request)

    @pytest.mark.asyncio
    async def test_coordinator_denied_write_trials(self) -> None:
        checker = PermissionChecker([Permission.WRITE_TRIALS])
        request = _make_request(Role.COORDINATOR)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            with pytest.raises(HTTPException):
                await checker(request)

    @pytest.mark.asyncio
    async def test_analyst_allowed_read_lineage(self) -> None:
        checker = PermissionChecker([Permission.READ_LINEAGE])
        request = _make_request(Role.ANALYST)
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)

    @pytest.mark.asyncio
    async def test_system_allowed_everything(self) -> None:
        """SYSTEM role should pass every permission check."""
        for perm in Permission:
            checker = PermissionChecker([perm])
            request = _make_request(Role.SYSTEM)
            with patch("app.core.permissions._is_auth_active", return_value=True):
                await checker(request)


# ---------------------------------------------------------------------------
# 8. Edge-case: dict-style user on request
# ---------------------------------------------------------------------------

class TestDictStyleUser:
    """Verify that _resolve_user_role handles dict-style user objects."""

    @pytest.mark.asyncio
    async def test_dict_user_with_role_key(self) -> None:
        checker = PermissionChecker([Permission.READ_PATIENTS])
        scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
        request = Request(scope)
        request.state.user = {"role": "provider"}
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)  # provider has READ_PATIENTS

    @pytest.mark.asyncio
    async def test_dict_user_with_roles_list(self) -> None:
        checker = PermissionChecker([Permission.READ_PATIENTS])
        scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
        request = Request(scope)
        request.state.user = {"roles": ["coordinator"]}
        with patch("app.core.permissions._is_auth_active", return_value=True):
            await checker(request)  # coordinator has READ_PATIENTS
