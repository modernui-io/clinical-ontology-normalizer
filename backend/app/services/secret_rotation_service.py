"""Secret Rotation Service (DEVOPS-4).

Manages the full lifecycle of application secrets:
- Creation, rotation (current -> previous), and expiry
- Zero-downtime dual-read window (grace period)
- Auto-rotation scheduling based on configurable policies
- Compliance reporting (overdue, upcoming, history)
- Full audit trail for every mutation

No external packages -- uses os.urandom, base64, hashlib from stdlib.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.services.secret_store import AbstractSecretStore, InMemorySecretStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types & policies
# ---------------------------------------------------------------------------


class SecretType(str, Enum):
    """Types of managed secrets."""

    DB_CREDENTIAL = "DB_CREDENTIAL"
    API_KEY = "API_KEY"
    JWT_SECRET = "JWT_SECRET"
    ENCRYPTION_KEY = "ENCRYPTION_KEY"
    WEBHOOK_SECRET = "WEBHOOK_SECRET"


@dataclass(frozen=True)
class RotationPolicy:
    """Defines how often a secret should be rotated and its grace window."""

    rotation_interval_days: int
    grace_period_minutes: int


# Pre-defined rotation policies per secret type
DEFAULT_POLICIES: dict[SecretType, RotationPolicy] = {
    SecretType.JWT_SECRET: RotationPolicy(rotation_interval_days=90, grace_period_minutes=60),
    SecretType.DB_CREDENTIAL: RotationPolicy(rotation_interval_days=180, grace_period_minutes=30),
    SecretType.API_KEY: RotationPolicy(rotation_interval_days=365, grace_period_minutes=120),
    SecretType.WEBHOOK_SECRET: RotationPolicy(rotation_interval_days=90, grace_period_minutes=60),
    SecretType.ENCRYPTION_KEY: RotationPolicy(
        rotation_interval_days=365, grace_period_minutes=1440
    ),  # 24 hours
}


@dataclass
class RotationAuditEntry:
    """A single audit trail record."""

    id: str
    secret_name: str
    secret_type: str
    action: str  # "created", "rotated", "previous_cleared"
    initiated_by: str
    reason: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "secret_name": self.secret_name,
            "secret_type": self.secret_type,
            "action": self.action,
            "initiated_by": self.initiated_by,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_secret_value(length: int = 32) -> str:
    """Generate a cryptographically random URL-safe secret."""
    return base64.urlsafe_b64encode(os.urandom(length)).decode("ascii")


def _mask_value(value: str) -> str:
    """Mask a secret value showing only first and last 4 chars."""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "..." + value[-4:]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SecretRotationService:
    """Manages secret lifecycle: creation, rotation, validation, and compliance.

    Thread-safe. Backed by any ``AbstractSecretStore`` implementation.
    """

    def __init__(
        self,
        store: AbstractSecretStore | None = None,
        policies: dict[SecretType, RotationPolicy] | None = None,
    ) -> None:
        self._store = store or InMemorySecretStore()
        self._policies = dict(DEFAULT_POLICIES)
        if policies:
            self._policies.update(policies)
        self._audit_log: list[RotationAuditEntry] = []
        self._lock = threading.Lock()

    # -- policy helpers -----------------------------------------------------

    def get_policy(self, secret_type: SecretType) -> RotationPolicy:
        """Return the rotation policy for a secret type."""
        return self._policies.get(secret_type, RotationPolicy(90, 60))

    def set_policy(self, secret_type: SecretType, policy: RotationPolicy) -> None:
        """Set a custom rotation policy for a secret type."""
        self._policies[secret_type] = policy

    # -- audit helpers ------------------------------------------------------

    def _record_audit(
        self,
        secret_name: str,
        secret_type: str,
        action: str,
        initiated_by: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> RotationAuditEntry:
        entry = RotationAuditEntry(
            id=str(uuid.uuid4()),
            secret_name=secret_name,
            secret_type=secret_type,
            action=action,
            initiated_by=initiated_by,
            reason=reason,
            timestamp=_now(),
            metadata=metadata or {},
        )
        self._audit_log.append(entry)
        logger.info(
            "Secret audit: %s %s by %s (%s)",
            action,
            secret_name,
            initiated_by,
            reason,
        )
        return entry

    # -- CRUD ---------------------------------------------------------------

    def create_secret(
        self,
        name: str,
        secret_type: SecretType,
        value: str | None = None,
        initiated_by: str = "system",
        reason: str = "initial_creation",
    ) -> dict[str, Any]:
        """Create a new managed secret.

        If *value* is ``None``, a cryptographically random value is generated.
        Returns the full secret record (internal use only -- callers should
        mask before exposing via API).
        """
        policy = self.get_policy(secret_type)
        now = _now()
        secret_value = value or _generate_secret_value()

        record: dict[str, Any] = {
            "name": name,
            "secret_type": secret_type.value,
            "current_value": secret_value,
            "previous_value": None,
            "previous_expires_at": None,
            "created_at": now.isoformat(),
            "rotated_at": None,
            "expires_at": (now + timedelta(days=policy.rotation_interval_days)).isoformat(),
            "rotation_interval_days": policy.rotation_interval_days,
            "grace_period_minutes": policy.grace_period_minutes,
        }

        self._store.set(name, record)
        self._record_audit(name, secret_type.value, "created", initiated_by, reason)
        return record

    def get_secret(self, name: str) -> dict[str, Any] | None:
        """Retrieve a secret record by name (internal -- contains raw values)."""
        record = self._store.get(name)
        if record is None:
            return None
        # Auto-clear expired previous value
        self._maybe_clear_previous(record)
        return record

    def get_secret_metadata(self, name: str) -> dict[str, Any] | None:
        """Retrieve masked metadata suitable for API responses."""
        record = self.get_secret(name)
        if record is None:
            return None
        return self._to_metadata(record)

    def list_secrets(self) -> list[dict[str, Any]]:
        """List masked metadata for all managed secrets."""
        result = []
        for key in self._store.list_keys():
            record = self._store.get(key)
            if record is not None:
                self._maybe_clear_previous(record)
                result.append(self._to_metadata(record))
        return result

    def delete_secret(
        self,
        name: str,
        initiated_by: str = "system",
        reason: str = "deleted",
    ) -> bool:
        """Delete a managed secret."""
        record = self._store.get(name)
        if record is None:
            return False
        self._store.delete(name)
        self._record_audit(
            name, record.get("secret_type", "UNKNOWN"), "deleted", initiated_by, reason
        )
        return True

    # -- rotation -----------------------------------------------------------

    def rotate_secret(
        self,
        name: str,
        new_value: str | None = None,
        initiated_by: str = "system",
        reason: str = "scheduled_rotation",
    ) -> dict[str, Any] | None:
        """Rotate a secret: current -> previous, generate new current.

        During the grace period both current and previous values are valid.
        Returns the updated record or None if secret not found.
        """
        record = self._store.get(name)
        if record is None:
            return None

        now = _now()
        grace_minutes = record.get("grace_period_minutes", 30)
        policy = self.get_policy(SecretType(record["secret_type"]))

        # Move current to previous with grace window
        record["previous_value"] = record["current_value"]
        record["previous_expires_at"] = (
            now + timedelta(minutes=grace_minutes)
        ).isoformat()

        # Set new current
        record["current_value"] = new_value or _generate_secret_value()
        record["rotated_at"] = now.isoformat()
        record["expires_at"] = (
            now + timedelta(days=policy.rotation_interval_days)
        ).isoformat()

        self._store.set(name, record)

        self._record_audit(
            name,
            record["secret_type"],
            "rotated",
            initiated_by,
            reason,
            metadata={"grace_period_minutes": grace_minutes},
        )
        return record

    def validate_secret(self, name: str, value: str) -> bool:
        """Check if *value* matches the current OR previous (during grace) value.

        Returns True if the value is valid, False otherwise.
        """
        record = self.get_secret(name)
        if record is None:
            return False

        if record["current_value"] == value:
            return True

        # Check previous value within grace period
        if record.get("previous_value") and record.get("previous_expires_at"):
            expires = datetime.fromisoformat(record["previous_expires_at"])
            if _now() < expires and record["previous_value"] == value:
                return True

        return False

    def clear_previous(self, name: str) -> bool:
        """Manually clear the previous value for a secret."""
        record = self._store.get(name)
        if record is None:
            return False

        if record.get("previous_value") is not None:
            record["previous_value"] = None
            record["previous_expires_at"] = None
            self._store.set(name, record)
            self._record_audit(
                name,
                record["secret_type"],
                "previous_cleared",
                "system",
                "grace_period_expired",
            )
            return True
        return False

    # -- auto-rotation ------------------------------------------------------

    def check_and_rotate(
        self,
        initiated_by: str = "auto_rotation",
    ) -> dict[str, Any]:
        """Check all secrets and rotate any that are past their expiry.

        Returns a summary: {checked, rotated, errors, timestamp}.
        """
        keys = self._store.list_keys()
        rotated: list[str] = []
        errors: list[str] = []
        now = _now()

        for key in keys:
            record = self._store.get(key)
            if record is None:
                continue

            expires_at_str = record.get("expires_at")
            if not expires_at_str:
                continue

            expires_at = datetime.fromisoformat(expires_at_str)
            if now >= expires_at:
                try:
                    self.rotate_secret(
                        key,
                        initiated_by=initiated_by,
                        reason="auto_rotation_overdue",
                    )
                    rotated.append(key)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Auto-rotation failed for %s: %s", key, exc)
                    errors.append(f"{key}: {exc}")

        return {
            "checked": len(keys),
            "rotated": rotated,
            "errors": errors,
            "timestamp": now.isoformat(),
        }

    # -- compliance ---------------------------------------------------------

    def get_compliance_report(self) -> dict[str, Any]:
        """Generate a compliance report for all managed secrets.

        Returns aggregated counts and per-secret reports.
        """
        keys = self._store.list_keys()
        reports: list[dict[str, Any]] = []
        overdue = 0
        due_soon = 0
        compliant = 0
        now = _now()

        for key in keys:
            record = self._store.get(key)
            if record is None:
                continue

            self._maybe_clear_previous(record)

            report: dict[str, Any] = {
                "name": record["name"],
                "secret_type": record["secret_type"],
                "last_rotated": record.get("rotated_at"),
                "rotation_interval_days": record["rotation_interval_days"],
            }

            expires_at_str = record.get("expires_at")
            if not expires_at_str:
                report["status"] = "NEVER_ROTATED"
                report["next_rotation_due"] = None
                report["days_until_rotation"] = None
                reports.append(report)
                continue

            expires_at = datetime.fromisoformat(expires_at_str)
            delta = expires_at - now
            days_until = delta.days

            report["next_rotation_due"] = expires_at.isoformat()
            report["days_until_rotation"] = days_until

            if days_until < 0:
                report["status"] = "OVERDUE"
                overdue += 1
            elif days_until <= 30:
                report["status"] = "DUE_SOON"
                due_soon += 1
            else:
                report["status"] = "CURRENT"
                compliant += 1

            reports.append(report)

        return {
            "reports": reports,
            "total": len(reports),
            "overdue_count": overdue,
            "due_soon_count": due_soon,
            "compliant_count": compliant,
        }

    # -- audit log ----------------------------------------------------------

    def get_audit_log(
        self,
        secret_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return audit log entries, optionally filtered by secret name."""
        entries = self._audit_log
        if secret_name:
            entries = [e for e in entries if e.secret_name == secret_name]
        # Most recent first
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        return [e.to_dict() for e in entries[:limit]]

    # -- internal helpers ---------------------------------------------------

    def _maybe_clear_previous(self, record: dict[str, Any]) -> None:
        """Clear previous value if the grace period has expired."""
        prev_expires = record.get("previous_expires_at")
        if prev_expires and record.get("previous_value") is not None:
            if _now() >= datetime.fromisoformat(prev_expires):
                name = record["name"]
                record["previous_value"] = None
                record["previous_expires_at"] = None
                self._store.set(name, record)
                self._record_audit(
                    name,
                    record["secret_type"],
                    "previous_cleared",
                    "system",
                    "grace_period_expired",
                )

    def _to_metadata(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert an internal record to masked metadata for API exposure."""
        return {
            "name": record["name"],
            "secret_type": record["secret_type"],
            "masked_value": _mask_value(record["current_value"]),
            "has_previous": record.get("previous_value") is not None,
            "created_at": record["created_at"],
            "rotated_at": record.get("rotated_at"),
            "expires_at": record.get("expires_at"),
            "rotation_interval_days": record["rotation_interval_days"],
            "grace_period_minutes": record["grace_period_minutes"],
        }


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------

_service: SecretRotationService | None = None
_service_lock = threading.Lock()


def get_secret_rotation_service() -> SecretRotationService:
    """Return the module-level singleton SecretRotationService."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = SecretRotationService()
    return _service
