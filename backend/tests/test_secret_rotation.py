"""Tests for Secret Rotation framework (DEVOPS-4).

Tests cover:
- Secret creation and storage
- Rotation: current -> previous transition, new value generation
- Grace period: both current and previous valid during window
- Grace period expiry: previous cleared after window
- Auto-rotation: identifies overdue secrets, rotates them
- Policy enforcement: correct intervals per secret type
- Compliance report: overdue detection, upcoming rotation listing
- Audit trail: rotation events recorded correctly
- Encrypted store: encrypt/decrypt round-trip, tamper detection
- Masked values in API responses (only first/last 4 chars shown)
- Validation: accepts current OR previous during grace period
- API endpoint responses
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.secret_store import (
    InMemorySecretStore,
    EncryptedFileSecretStore,
    encrypt_data,
    decrypt_data,
)
from app.services.secret_rotation_service import (
    DEFAULT_POLICIES,
    RotationPolicy,
    SecretRotationService,
    SecretType,
    _generate_secret_value,
    _mask_value,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def store() -> InMemorySecretStore:
    """Create a fresh in-memory store for each test."""
    return InMemorySecretStore()


@pytest.fixture
def service(store: InMemorySecretStore) -> SecretRotationService:
    """Create a fresh SecretRotationService backed by in-memory store."""
    return SecretRotationService(store=store)


@pytest.fixture
def now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


# ============================================================================
# Secret Creation and Storage
# ============================================================================


class TestSecretCreation:
    """Tests for creating and storing secrets."""

    def test_create_secret_with_auto_generated_value(self, service: SecretRotationService) -> None:
        """Creating a secret without a value generates a random one."""
        record = service.create_secret("test-key", SecretType.API_KEY)
        assert record["name"] == "test-key"
        assert record["secret_type"] == "API_KEY"
        assert record["current_value"] is not None
        assert len(record["current_value"]) > 0
        assert record["previous_value"] is None

    def test_create_secret_with_explicit_value(self, service: SecretRotationService) -> None:
        """Creating a secret with an explicit value stores it correctly."""
        record = service.create_secret("db-pass", SecretType.DB_CREDENTIAL, value="my-secret-123")
        assert record["current_value"] == "my-secret-123"

    def test_create_secret_sets_expiry(self, service: SecretRotationService) -> None:
        """Created secret has correct expiry based on policy."""
        record = service.create_secret("jwt", SecretType.JWT_SECRET)
        expires = datetime.fromisoformat(record["expires_at"])
        created = datetime.fromisoformat(record["created_at"])
        delta = expires - created
        assert delta.days == 90  # JWT_SECRET default policy

    def test_create_secret_records_audit(self, service: SecretRotationService) -> None:
        """Creating a secret records an audit entry."""
        service.create_secret("audit-test", SecretType.WEBHOOK_SECRET)
        audit = service.get_audit_log(secret_name="audit-test")
        assert len(audit) == 1
        assert audit[0]["action"] == "created"
        assert audit[0]["secret_name"] == "audit-test"

    def test_retrieve_secret(self, service: SecretRotationService) -> None:
        """Secret can be retrieved by name."""
        service.create_secret("retrieve-me", SecretType.API_KEY, value="hello123")
        record = service.get_secret("retrieve-me")
        assert record is not None
        assert record["current_value"] == "hello123"

    def test_retrieve_nonexistent_secret(self, service: SecretRotationService) -> None:
        """Retrieving a non-existent secret returns None."""
        assert service.get_secret("does-not-exist") is None

    def test_list_secrets_returns_masked_metadata(self, service: SecretRotationService) -> None:
        """Listing secrets returns metadata with masked values."""
        service.create_secret("secret-a", SecretType.API_KEY)
        service.create_secret("secret-b", SecretType.JWT_SECRET)
        secrets = service.list_secrets()
        assert len(secrets) == 2
        for s in secrets:
            assert "current_value" not in s
            assert "masked_value" in s

    def test_delete_secret(self, service: SecretRotationService) -> None:
        """Deleting a secret removes it from the store."""
        service.create_secret("deletable", SecretType.API_KEY)
        assert service.delete_secret("deletable") is True
        assert service.get_secret("deletable") is None

    def test_delete_nonexistent_secret(self, service: SecretRotationService) -> None:
        """Deleting a non-existent secret returns False."""
        assert service.delete_secret("nope") is False


# ============================================================================
# Rotation
# ============================================================================


class TestRotation:
    """Tests for secret rotation logic."""

    def test_rotation_moves_current_to_previous(self, service: SecretRotationService) -> None:
        """Rotation moves current value to previous."""
        record = service.create_secret("rotate-me", SecretType.API_KEY, value="old-value")
        rotated = service.rotate_secret("rotate-me")
        assert rotated is not None
        assert rotated["previous_value"] == "old-value"
        assert rotated["current_value"] != "old-value"

    def test_rotation_generates_new_value(self, service: SecretRotationService) -> None:
        """Rotation generates a new cryptographically random value."""
        service.create_secret("new-val", SecretType.JWT_SECRET, value="initial")
        rotated = service.rotate_secret("new-val")
        assert rotated is not None
        assert rotated["current_value"] != "initial"
        assert len(rotated["current_value"]) > 0

    def test_rotation_with_explicit_new_value(self, service: SecretRotationService) -> None:
        """Rotation can accept an explicit new value."""
        service.create_secret("explicit", SecretType.DB_CREDENTIAL, value="old")
        rotated = service.rotate_secret("explicit", new_value="new-explicit")
        assert rotated is not None
        assert rotated["current_value"] == "new-explicit"
        assert rotated["previous_value"] == "old"

    def test_rotation_updates_rotated_at(self, service: SecretRotationService) -> None:
        """Rotation updates the rotated_at timestamp."""
        service.create_secret("ts-test", SecretType.WEBHOOK_SECRET)
        rotated = service.rotate_secret("ts-test")
        assert rotated is not None
        assert rotated["rotated_at"] is not None

    def test_rotation_updates_expiry(self, service: SecretRotationService) -> None:
        """Rotation resets the expiry based on the rotation policy."""
        service.create_secret("expiry-test", SecretType.JWT_SECRET)
        rotated = service.rotate_secret("expiry-test")
        assert rotated is not None
        expires = datetime.fromisoformat(rotated["expires_at"])
        rotated_at = datetime.fromisoformat(rotated["rotated_at"])
        delta = expires - rotated_at
        assert delta.days == 90

    def test_rotation_of_nonexistent_secret(self, service: SecretRotationService) -> None:
        """Rotating a non-existent secret returns None."""
        assert service.rotate_secret("ghost") is None

    def test_rotation_records_audit(self, service: SecretRotationService) -> None:
        """Rotation records an audit entry."""
        service.create_secret("audit-rotate", SecretType.API_KEY)
        service.rotate_secret("audit-rotate", initiated_by="admin", reason="quarterly")
        audit = service.get_audit_log(secret_name="audit-rotate")
        actions = [e["action"] for e in audit]
        assert "rotated" in actions
        rotate_entry = next(e for e in audit if e["action"] == "rotated")
        assert rotate_entry["initiated_by"] == "admin"
        assert rotate_entry["reason"] == "quarterly"


# ============================================================================
# Grace Period
# ============================================================================


class TestGracePeriod:
    """Tests for the dual-read grace period window."""

    def test_both_values_valid_during_grace_period(self, service: SecretRotationService) -> None:
        """Both current and previous values are accepted during grace window."""
        service.create_secret("grace", SecretType.JWT_SECRET, value="old-val")
        service.rotate_secret("grace", new_value="new-val")
        assert service.validate_secret("grace", "new-val") is True
        assert service.validate_secret("grace", "old-val") is True

    def test_invalid_value_rejected(self, service: SecretRotationService) -> None:
        """A random value is rejected."""
        service.create_secret("reject", SecretType.API_KEY, value="real")
        assert service.validate_secret("reject", "fake") is False

    def test_previous_cleared_after_grace_period(self, service: SecretRotationService) -> None:
        """Previous value is cleared once the grace period expires."""
        store = InMemorySecretStore()
        svc = SecretRotationService(store=store)
        svc.create_secret("grace-expire", SecretType.JWT_SECRET, value="v1")
        svc.rotate_secret("grace-expire", new_value="v2")

        # Simulate grace period expiring by setting previous_expires_at to the past
        record = store.get("grace-expire")
        assert record is not None
        record["previous_expires_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
        store.set("grace-expire", record)

        # Now get_secret should auto-clear the previous value
        updated = svc.get_secret("grace-expire")
        assert updated is not None
        assert updated["previous_value"] is None

    def test_previous_invalid_after_grace_period(self, service: SecretRotationService) -> None:
        """Previous value is rejected after grace period expires."""
        store = InMemorySecretStore()
        svc = SecretRotationService(store=store)
        svc.create_secret("grace-invalid", SecretType.API_KEY, value="v1")
        svc.rotate_secret("grace-invalid", new_value="v2")

        # Expire the grace period
        record = store.get("grace-invalid")
        assert record is not None
        record["previous_expires_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
        store.set("grace-invalid", record)

        assert svc.validate_secret("grace-invalid", "v1") is False
        assert svc.validate_secret("grace-invalid", "v2") is True

    def test_validate_nonexistent_secret(self, service: SecretRotationService) -> None:
        """Validating against a nonexistent secret returns False."""
        assert service.validate_secret("no-such", "val") is False

    def test_grace_period_sets_previous_expires_at(self, service: SecretRotationService) -> None:
        """Rotation sets a previous_expires_at timestamp based on grace period."""
        service.create_secret("prev-exp", SecretType.JWT_SECRET, value="v1")
        rotated = service.rotate_secret("prev-exp")
        assert rotated is not None
        assert rotated["previous_expires_at"] is not None
        prev_exp = datetime.fromisoformat(rotated["previous_expires_at"])
        rotated_at = datetime.fromisoformat(rotated["rotated_at"])
        delta = prev_exp - rotated_at
        assert 59 <= delta.total_seconds() / 60 <= 61  # 60 min for JWT_SECRET

    def test_manual_clear_previous(self, service: SecretRotationService) -> None:
        """Previous value can be manually cleared before grace period expires."""
        service.create_secret("manual-clear", SecretType.API_KEY, value="v1")
        service.rotate_secret("manual-clear", new_value="v2")
        assert service.clear_previous("manual-clear") is True
        record = service.get_secret("manual-clear")
        assert record is not None
        assert record["previous_value"] is None


# ============================================================================
# Auto-Rotation
# ============================================================================


class TestAutoRotation:
    """Tests for automatic rotation scheduling."""

    def test_auto_rotation_identifies_overdue_secrets(self) -> None:
        """Auto-rotation detects and rotates overdue secrets."""
        store = InMemorySecretStore()
        svc = SecretRotationService(store=store)
        svc.create_secret("overdue", SecretType.JWT_SECRET, value="old")

        # Make the secret overdue by setting expires_at to the past
        record = store.get("overdue")
        assert record is not None
        record["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        store.set("overdue", record)

        result = svc.check_and_rotate()
        assert "overdue" in result["rotated"]
        assert result["checked"] == 1

    def test_auto_rotation_skips_current_secrets(self, service: SecretRotationService) -> None:
        """Auto-rotation does not rotate secrets that are not overdue."""
        service.create_secret("fresh", SecretType.API_KEY)
        result = service.check_and_rotate()
        assert result["rotated"] == []
        assert result["checked"] == 1

    def test_auto_rotation_multiple_secrets(self) -> None:
        """Auto-rotation handles multiple secrets correctly."""
        store = InMemorySecretStore()
        svc = SecretRotationService(store=store)
        svc.create_secret("s1", SecretType.JWT_SECRET)
        svc.create_secret("s2", SecretType.API_KEY)

        # Make s1 overdue
        record = store.get("s1")
        assert record is not None
        record["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        store.set("s1", record)

        result = svc.check_and_rotate()
        assert "s1" in result["rotated"]
        assert "s2" not in result["rotated"]
        assert result["checked"] == 2


# ============================================================================
# Policy Enforcement
# ============================================================================


class TestPolicyEnforcement:
    """Tests for rotation policy configuration and enforcement."""

    def test_default_jwt_policy(self, service: SecretRotationService) -> None:
        """JWT_SECRET has 90-day rotation, 60-min grace period."""
        policy = service.get_policy(SecretType.JWT_SECRET)
        assert policy.rotation_interval_days == 90
        assert policy.grace_period_minutes == 60

    def test_default_db_credential_policy(self, service: SecretRotationService) -> None:
        """DB_CREDENTIAL has 180-day rotation, 30-min grace period."""
        policy = service.get_policy(SecretType.DB_CREDENTIAL)
        assert policy.rotation_interval_days == 180
        assert policy.grace_period_minutes == 30

    def test_default_api_key_policy(self, service: SecretRotationService) -> None:
        """API_KEY has 365-day rotation, 120-min grace period."""
        policy = service.get_policy(SecretType.API_KEY)
        assert policy.rotation_interval_days == 365
        assert policy.grace_period_minutes == 120

    def test_default_webhook_secret_policy(self, service: SecretRotationService) -> None:
        """WEBHOOK_SECRET has 90-day rotation, 60-min grace period."""
        policy = service.get_policy(SecretType.WEBHOOK_SECRET)
        assert policy.rotation_interval_days == 90
        assert policy.grace_period_minutes == 60

    def test_default_encryption_key_policy(self, service: SecretRotationService) -> None:
        """ENCRYPTION_KEY has 365-day rotation, 1440-min (24h) grace period."""
        policy = service.get_policy(SecretType.ENCRYPTION_KEY)
        assert policy.rotation_interval_days == 365
        assert policy.grace_period_minutes == 1440

    def test_custom_policy(self, service: SecretRotationService) -> None:
        """Custom policies can be set and take effect."""
        custom = RotationPolicy(rotation_interval_days=7, grace_period_minutes=5)
        service.set_policy(SecretType.JWT_SECRET, custom)
        record = service.create_secret("custom-policy", SecretType.JWT_SECRET)
        expires = datetime.fromisoformat(record["expires_at"])
        created = datetime.fromisoformat(record["created_at"])
        delta = expires - created
        assert delta.days == 7


# ============================================================================
# Compliance Reporting
# ============================================================================


class TestComplianceReport:
    """Tests for compliance report generation."""

    def test_compliance_current_secret(self, service: SecretRotationService) -> None:
        """Freshly created secrets show as CURRENT."""
        service.create_secret("compliant", SecretType.API_KEY)
        report = service.get_compliance_report()
        assert report["compliant_count"] == 1
        assert report["overdue_count"] == 0

    def test_compliance_overdue_detection(self) -> None:
        """Overdue secrets are detected in compliance report."""
        store = InMemorySecretStore()
        svc = SecretRotationService(store=store)
        svc.create_secret("overdue-comp", SecretType.JWT_SECRET)

        record = store.get("overdue-comp")
        assert record is not None
        record["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(days=5)
        ).isoformat()
        store.set("overdue-comp", record)

        report = svc.get_compliance_report()
        assert report["overdue_count"] == 1
        secret_report = report["reports"][0]
        assert secret_report["status"] == "OVERDUE"
        assert secret_report["days_until_rotation"] < 0

    def test_compliance_due_soon(self) -> None:
        """Secrets due within 30 days show as DUE_SOON."""
        store = InMemorySecretStore()
        svc = SecretRotationService(store=store)
        svc.create_secret("due-soon", SecretType.JWT_SECRET)

        record = store.get("due-soon")
        assert record is not None
        record["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(days=15)
        ).isoformat()
        store.set("due-soon", record)

        report = svc.get_compliance_report()
        assert report["due_soon_count"] == 1
        assert report["reports"][0]["status"] == "DUE_SOON"

    def test_compliance_report_totals(self, service: SecretRotationService) -> None:
        """Compliance report has correct totals."""
        service.create_secret("s1", SecretType.API_KEY)
        service.create_secret("s2", SecretType.JWT_SECRET)
        report = service.get_compliance_report()
        assert report["total"] == 2


# ============================================================================
# Audit Trail
# ============================================================================


class TestAuditTrail:
    """Tests for audit trail recording."""

    def test_creation_audit_entry(self, service: SecretRotationService) -> None:
        """Creation is recorded in audit log."""
        service.create_secret("aud1", SecretType.API_KEY, initiated_by="alice", reason="setup")
        log = service.get_audit_log()
        assert len(log) == 1
        assert log[0]["action"] == "created"
        assert log[0]["initiated_by"] == "alice"
        assert log[0]["reason"] == "setup"

    def test_rotation_audit_entry(self, service: SecretRotationService) -> None:
        """Rotation is recorded in audit log."""
        service.create_secret("aud2", SecretType.JWT_SECRET)
        service.rotate_secret("aud2", initiated_by="bob", reason="policy")
        log = service.get_audit_log(secret_name="aud2")
        actions = [e["action"] for e in log]
        assert "created" in actions
        assert "rotated" in actions

    def test_audit_log_ordering(self, service: SecretRotationService) -> None:
        """Audit log entries are returned most-recent-first."""
        service.create_secret("order", SecretType.API_KEY)
        service.rotate_secret("order")
        log = service.get_audit_log(secret_name="order")
        assert log[0]["action"] == "rotated"
        assert log[1]["action"] == "created"

    def test_audit_log_limit(self, service: SecretRotationService) -> None:
        """Audit log respects the limit parameter."""
        for i in range(5):
            service.create_secret(f"lim-{i}", SecretType.API_KEY)
        log = service.get_audit_log(limit=3)
        assert len(log) == 3

    def test_audit_log_filter_by_name(self, service: SecretRotationService) -> None:
        """Audit log can be filtered by secret name."""
        service.create_secret("a", SecretType.API_KEY)
        service.create_secret("b", SecretType.JWT_SECRET)
        log_a = service.get_audit_log(secret_name="a")
        assert all(e["secret_name"] == "a" for e in log_a)

    def test_audit_has_uuid_id(self, service: SecretRotationService) -> None:
        """Each audit entry has a UUID id."""
        service.create_secret("uuid-test", SecretType.API_KEY)
        log = service.get_audit_log()
        assert len(log[0]["id"]) == 36  # UUID format


# ============================================================================
# Encrypted Store
# ============================================================================


class TestEncryptedStore:
    """Tests for the encrypted file secret store."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Encrypt then decrypt produces original plaintext."""
        key = b"test-master-key-for-encryption"
        plaintext = b"hello world secret data 12345"
        blob = encrypt_data(plaintext, key)
        result = decrypt_data(blob, key)
        assert result == plaintext

    def test_encrypt_produces_different_ciphertext(self) -> None:
        """Two encryptions of the same data produce different ciphertext (random IV)."""
        key = b"my-key"
        plaintext = b"same data"
        blob1 = encrypt_data(plaintext, key)
        blob2 = encrypt_data(plaintext, key)
        assert blob1 != blob2

    def test_tamper_detection(self) -> None:
        """Modifying ciphertext causes HMAC verification to fail."""
        key = b"integrity-key"
        plaintext = b"important secret"
        blob = encrypt_data(plaintext, key)
        # Tamper with a byte in the ciphertext region
        tampered = bytearray(blob)
        tampered[20] ^= 0xFF
        with pytest.raises(ValueError, match="HMAC verification failed"):
            decrypt_data(bytes(tampered), key)

    def test_encrypted_file_store_crud(self) -> None:
        """EncryptedFileSecretStore round-trips data through file."""
        with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
            path = f.name
        try:
            store = EncryptedFileSecretStore(file_path=path, master_key="test-key-123")
            store.set("s1", {"value": "hello", "count": 42})
            result = store.get("s1")
            assert result is not None
            assert result["value"] == "hello"
            assert result["count"] == 42

            keys = store.list_keys()
            assert "s1" in keys

            assert store.delete("s1") is True
            assert store.get("s1") is None
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_encrypted_file_store_persists(self) -> None:
        """Data survives across store instances (same file, same key)."""
        with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
            path = f.name
        try:
            store1 = EncryptedFileSecretStore(file_path=path, master_key="persist-key")
            store1.set("persist", {"data": "sticky"})

            # Create a new store instance pointing to the same file
            store2 = EncryptedFileSecretStore(file_path=path, master_key="persist-key")
            result = store2.get("persist")
            assert result is not None
            assert result["data"] == "sticky"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_encrypted_file_store_wrong_key_fails(self) -> None:
        """Using the wrong master key to decrypt raises an error."""
        with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
            path = f.name
        try:
            store = EncryptedFileSecretStore(file_path=path, master_key="right-key")
            store.set("secret", {"val": "data"})

            wrong_store = EncryptedFileSecretStore(file_path=path, master_key="wrong-key")
            with pytest.raises(ValueError):
                wrong_store.get("secret")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_encrypted_store_no_master_key_raises(self) -> None:
        """EncryptedFileSecretStore raises without a master key."""
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=False):
            env = os.environ.copy()
            env.pop("SECRET_MASTER_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValueError, match="Master key is required"):
                    EncryptedFileSecretStore(file_path="dummy.enc")


# ============================================================================
# Masking
# ============================================================================


class TestMasking:
    """Tests for secret value masking."""

    def test_mask_long_value(self) -> None:
        """Long values show first/last 4 chars with dots."""
        result = _mask_value("abcdefghijklmnop")
        assert result == "abcd...mnop"

    def test_mask_short_value(self) -> None:
        """Short values (<=8 chars) are fully masked."""
        result = _mask_value("short")
        assert result == "*****"

    def test_mask_exactly_8_chars(self) -> None:
        """8-char values are fully masked."""
        result = _mask_value("12345678")
        assert result == "********"

    def test_mask_9_chars(self) -> None:
        """9-char values show first/last 4."""
        result = _mask_value("123456789")
        assert result == "1234...6789"

    def test_metadata_has_masked_value(self, service: SecretRotationService) -> None:
        """get_secret_metadata returns masked value, not raw."""
        service.create_secret("mask-test", SecretType.API_KEY, value="abcdefghijklmnopqrstuvwxyz")
        meta = service.get_secret_metadata("mask-test")
        assert meta is not None
        assert meta["masked_value"] == "abcd...wxyz"
        assert "current_value" not in meta


# ============================================================================
# Helper Functions
# ============================================================================


class TestHelpers:
    """Tests for helper/utility functions."""

    def test_generate_secret_value_length(self) -> None:
        """Generated secrets are URL-safe base64 of the requested byte length."""
        val = _generate_secret_value(32)
        assert len(val) > 0
        # Should be decodable
        decoded = base64.urlsafe_b64decode(val)
        assert len(decoded) == 32

    def test_generate_secret_value_uniqueness(self) -> None:
        """Two generated secrets are different."""
        v1 = _generate_secret_value()
        v2 = _generate_secret_value()
        assert v1 != v2


# ============================================================================
# API Endpoints (using TestClient)
# ============================================================================


class TestAPIEndpoints:
    """Tests for the secret rotation API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_app(self) -> None:
        """Set up a test app with pre-seeded secrets."""
        import app.services.secret_rotation_service as svc_mod

        # Replace singleton with fresh service
        store = InMemorySecretStore()
        self.service = SecretRotationService(store=store)
        svc_mod._service = self.service

        # Seed some secrets
        self.service.create_secret("test-jwt", SecretType.JWT_SECRET)
        self.service.create_secret("test-api", SecretType.API_KEY, value="abcdefghijklmnopqrstuvwxyz")

        from app.main import app

        self.client = TestClient(app)

        yield  # type: ignore[misc]

        # Restore singleton
        svc_mod._service = None

    def test_list_secrets_endpoint(self) -> None:
        """GET /admin/secrets returns masked secret list."""
        resp = self.client.get("/api/v1/admin/secrets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["secrets"]) == 2
        for s in data["secrets"]:
            assert "masked_value" in s
            # Ensure raw values are not exposed
            assert "current_value" not in s

    def test_get_single_secret_endpoint(self) -> None:
        """GET /admin/secrets/{name} returns masked metadata."""
        resp = self.client.get("/api/v1/admin/secrets/test-api")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-api"
        assert data["masked_value"] == "abcd...wxyz"

    def test_get_nonexistent_secret_endpoint(self) -> None:
        """GET /admin/secrets/{name} returns 404 for unknown secret."""
        resp = self.client.get("/api/v1/admin/secrets/nope")
        assert resp.status_code == 404

    def test_rotate_secret_endpoint(self) -> None:
        """POST /admin/secrets/{name}/rotate triggers rotation."""
        resp = self.client.post(
            "/api/v1/admin/secrets/test-jwt/rotate",
            json={"reason": "test-rotation", "initiated_by": "tester"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_previous"] is True
        assert data["rotated_at"] is not None

    def test_rotate_nonexistent_endpoint(self) -> None:
        """POST /admin/secrets/{name}/rotate returns 404 for unknown."""
        resp = self.client.post("/api/v1/admin/secrets/ghost/rotate")
        assert resp.status_code == 404

    def test_compliance_endpoint(self) -> None:
        """GET /admin/secrets/compliance returns compliance report."""
        resp = self.client.get("/api/v1/admin/secrets/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["compliant_count"] >= 0

    def test_audit_log_endpoint(self) -> None:
        """GET /admin/secrets/audit-log returns audit entries."""
        resp = self.client.get("/api/v1/admin/secrets/audit-log")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2  # At least the two creation events

    def test_check_schedule_endpoint(self) -> None:
        """POST /admin/secrets/check-schedule runs auto-rotation."""
        resp = self.client.post("/api/v1/admin/secrets/check-schedule")
        assert resp.status_code == 200
        data = resp.json()
        assert "checked" in data
        assert "rotated" in data
        assert data["checked"] == 2
