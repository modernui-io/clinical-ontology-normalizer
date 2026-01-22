"""KG API Key Authentication Service.

This module provides API key management and authentication for the Knowledge Graph API.
Supports key generation, validation, rotation, scopes, and rate limiting per key.
"""

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class APIKeyScope(str, Enum):
    """API key permission scopes."""

    # Read operations
    READ_CONCEPTS = "read:concepts"
    READ_RELATIONSHIPS = "read:relationships"
    READ_PATIENTS = "read:patients"
    READ_REASONING = "read:reasoning"
    READ_BENCHMARKS = "read:benchmarks"
    READ_HEALTH = "read:health"
    READ_METRICS = "read:metrics"

    # Write operations
    WRITE_CONCEPTS = "write:concepts"
    WRITE_RELATIONSHIPS = "write:relationships"
    WRITE_PATIENTS = "write:patients"

    # Admin operations
    ADMIN_KEYS = "admin:keys"
    ADMIN_CONFIG = "admin:config"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_SYSTEM = "admin:system"

    # Batch operations
    BATCH_READ = "batch:read"
    BATCH_WRITE = "batch:write"

    # Export operations
    EXPORT_DATA = "export:data"
    EXPORT_FHIR = "export:fhir"

    # Full access
    FULL_ACCESS = "*"


# Pre-defined scope sets
SCOPE_PRESETS = {
    "readonly": {
        APIKeyScope.READ_CONCEPTS,
        APIKeyScope.READ_RELATIONSHIPS,
        APIKeyScope.READ_PATIENTS,
        APIKeyScope.READ_REASONING,
        APIKeyScope.READ_HEALTH,
    },
    "standard": {
        APIKeyScope.READ_CONCEPTS,
        APIKeyScope.READ_RELATIONSHIPS,
        APIKeyScope.READ_PATIENTS,
        APIKeyScope.READ_REASONING,
        APIKeyScope.READ_HEALTH,
        APIKeyScope.READ_METRICS,
        APIKeyScope.BATCH_READ,
    },
    "full": {
        APIKeyScope.READ_CONCEPTS,
        APIKeyScope.READ_RELATIONSHIPS,
        APIKeyScope.READ_PATIENTS,
        APIKeyScope.READ_REASONING,
        APIKeyScope.READ_BENCHMARKS,
        APIKeyScope.READ_HEALTH,
        APIKeyScope.READ_METRICS,
        APIKeyScope.WRITE_CONCEPTS,
        APIKeyScope.WRITE_RELATIONSHIPS,
        APIKeyScope.WRITE_PATIENTS,
        APIKeyScope.BATCH_READ,
        APIKeyScope.BATCH_WRITE,
        APIKeyScope.EXPORT_DATA,
        APIKeyScope.EXPORT_FHIR,
    },
    "admin": {APIKeyScope.FULL_ACCESS},
}


class APIKeyStatus(str, Enum):
    """API key status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class APIKeyRateLimit:
    """Rate limit configuration for an API key."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_limit: int = 10

    # Tracking
    minute_count: int = 0
    hour_count: int = 0
    day_count: int = 0
    burst_count: int = 0
    last_minute_reset: float = field(default_factory=time.time)
    last_hour_reset: float = field(default_factory=time.time)
    last_day_reset: float = field(default_factory=time.time)
    last_burst_reset: float = field(default_factory=time.time)

    def check_and_increment(self) -> Tuple[bool, Optional[str], Optional[int]]:
        """Check rate limit and increment counters.

        Returns:
            Tuple of (allowed, error_message, retry_after_seconds)
        """
        now = time.time()

        # Reset counters if time windows have passed
        if now - self.last_minute_reset >= 60:
            self.minute_count = 0
            self.last_minute_reset = now

        if now - self.last_hour_reset >= 3600:
            self.hour_count = 0
            self.last_hour_reset = now

        if now - self.last_day_reset >= 86400:
            self.day_count = 0
            self.last_day_reset = now

        if now - self.last_burst_reset >= 1:
            self.burst_count = 0
            self.last_burst_reset = now

        # Check limits
        if self.burst_count >= self.burst_limit:
            retry_after = int(1 - (now - self.last_burst_reset))
            return False, "Burst rate limit exceeded", max(1, retry_after)

        if self.minute_count >= self.requests_per_minute:
            retry_after = int(60 - (now - self.last_minute_reset))
            return False, "Per-minute rate limit exceeded", max(1, retry_after)

        if self.hour_count >= self.requests_per_hour:
            retry_after = int(3600 - (now - self.last_hour_reset))
            return False, "Per-hour rate limit exceeded", max(1, retry_after)

        if self.day_count >= self.requests_per_day:
            retry_after = int(86400 - (now - self.last_day_reset))
            return False, "Per-day rate limit exceeded", max(1, retry_after)

        # Increment counters
        self.burst_count += 1
        self.minute_count += 1
        self.hour_count += 1
        self.day_count += 1

        return True, None, None

    def get_remaining(self) -> Dict[str, int]:
        """Get remaining requests for each limit window."""
        return {
            "burst": max(0, self.burst_limit - self.burst_count),
            "minute": max(0, self.requests_per_minute - self.minute_count),
            "hour": max(0, self.requests_per_hour - self.hour_count),
            "day": max(0, self.requests_per_day - self.day_count),
        }


@dataclass
class APIKey:
    """API key entity."""

    key_id: str
    key_hash: str  # Store hash, not raw key
    name: str
    description: str = ""
    scopes: Set[APIKeyScope] = field(default_factory=set)
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    rate_limit: APIKeyRateLimit = field(default_factory=APIKeyRateLimit)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Usage tracking
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    def is_valid(self) -> Tuple[bool, Optional[str]]:
        """Check if the API key is valid for use."""
        if self.status == APIKeyStatus.REVOKED:
            return False, "API key has been revoked"
        if self.status == APIKeyStatus.SUSPENDED:
            return False, "API key is suspended"
        if self.status == APIKeyStatus.EXPIRED:
            return False, "API key has expired"
        if self.expires_at and datetime.utcnow() > self.expires_at:
            self.status = APIKeyStatus.EXPIRED
            return False, "API key has expired"
        return True, None

    def has_scope(self, required_scope: APIKeyScope) -> bool:
        """Check if key has the required scope."""
        if APIKeyScope.FULL_ACCESS in self.scopes:
            return True
        return required_scope in self.scopes

    def has_any_scope(self, required_scopes: Set[APIKeyScope]) -> bool:
        """Check if key has any of the required scopes."""
        if APIKeyScope.FULL_ACCESS in self.scopes:
            return True
        return bool(self.scopes & required_scopes)

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "key_id": self.key_id,
            "name": self.name,
            "description": self.description,
            "scopes": [s.value for s in self.scopes],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_by": self.created_by,
            "metadata": self.metadata,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limit": {
                "requests_per_minute": self.rate_limit.requests_per_minute,
                "requests_per_hour": self.rate_limit.requests_per_hour,
                "requests_per_day": self.rate_limit.requests_per_day,
                "remaining": self.rate_limit.get_remaining(),
            },
        }
        if include_sensitive:
            result["key_hash"] = self.key_hash
        return result


@dataclass
class AuthenticationResult:
    """Result of API key authentication."""

    authenticated: bool
    key: Optional[APIKey] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "authenticated": self.authenticated,
            "key_id": self.key.key_id if self.key else None,
            "error": self.error,
            "retry_after": self.retry_after,
        }


class KGAPIKeyService:
    """Service for managing API keys.

    Features:
    - Key generation with secure random tokens
    - Key validation and authentication
    - Scope-based authorization
    - Rate limiting per key
    - Key rotation
    - Usage tracking
    """

    # Key prefix for identification
    KEY_PREFIX = "kg_"
    KEY_LENGTH = 32  # bytes

    def __init__(self):
        """Initialize the API key service."""
        self._keys: Dict[str, APIKey] = {}  # key_id -> APIKey
        self._key_hash_index: Dict[str, str] = {}  # key_hash -> key_id
        self._lock = threading.RLock()

        # Listeners for key events
        self._listeners: List[Callable[[str, str, APIKey], None]] = []

        # Statistics
        self._stats = {
            "total_authentications": 0,
            "successful_authentications": 0,
            "failed_authentications": 0,
            "keys_created": 0,
            "keys_revoked": 0,
        }

    def generate_key(
        self,
        name: str,
        description: str = "",
        scopes: Optional[Set[APIKeyScope]] = None,
        preset: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        rate_limit: Optional[APIKeyRateLimit] = None,
        created_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, APIKey]:
        """Generate a new API key.

        Args:
            name: Human-readable name for the key
            description: Optional description
            scopes: Set of permission scopes
            preset: Use a preset scope set ("readonly", "standard", "full", "admin")
            expires_in_days: Days until key expires (None for no expiry)
            rate_limit: Custom rate limit configuration
            created_by: User who created the key
            metadata: Additional metadata

        Returns:
            Tuple of (raw_key, APIKey object)
            Note: The raw key is only returned once at creation
        """
        # Generate secure random key
        raw_key_bytes = secrets.token_bytes(self.KEY_LENGTH)
        raw_key = self.KEY_PREFIX + raw_key_bytes.hex()

        # Generate key ID (shorter, for display)
        key_id = f"key_{secrets.token_hex(8)}"

        # Hash the key for storage
        key_hash = self._hash_key(raw_key)

        # Determine scopes
        if preset and preset in SCOPE_PRESETS:
            key_scopes = SCOPE_PRESETS[preset].copy()
        elif scopes:
            key_scopes = scopes.copy()
        else:
            key_scopes = SCOPE_PRESETS["readonly"].copy()

        # Calculate expiry
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create API key object
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            description=description,
            scopes=key_scopes,
            status=APIKeyStatus.ACTIVE,
            rate_limit=rate_limit or APIKeyRateLimit(),
            expires_at=expires_at,
            created_by=created_by,
            metadata=metadata or {},
        )

        with self._lock:
            self._keys[key_id] = api_key
            self._key_hash_index[key_hash] = key_id
            self._stats["keys_created"] += 1

        self._notify_listeners("created", key_id, api_key)

        return raw_key, api_key

    def authenticate(self, raw_key: str) -> AuthenticationResult:
        """Authenticate an API key.

        Args:
            raw_key: The raw API key string

        Returns:
            AuthenticationResult with authentication status
        """
        self._stats["total_authentications"] += 1

        # Validate key format
        if not raw_key or not raw_key.startswith(self.KEY_PREFIX):
            self._stats["failed_authentications"] += 1
            return AuthenticationResult(
                authenticated=False,
                error="Invalid API key format",
            )

        # Hash the key and look up
        key_hash = self._hash_key(raw_key)

        with self._lock:
            key_id = self._key_hash_index.get(key_hash)
            if not key_id:
                self._stats["failed_authentications"] += 1
                return AuthenticationResult(
                    authenticated=False,
                    error="Invalid API key",
                )

            api_key = self._keys.get(key_id)
            if not api_key:
                self._stats["failed_authentications"] += 1
                return AuthenticationResult(
                    authenticated=False,
                    error="API key not found",
                )

            # Check key validity
            is_valid, error = api_key.is_valid()
            if not is_valid:
                self._stats["failed_authentications"] += 1
                api_key.failed_requests += 1
                return AuthenticationResult(
                    authenticated=False,
                    error=error,
                )

            # Check rate limit
            allowed, rate_error, retry_after = api_key.rate_limit.check_and_increment()
            if not allowed:
                self._stats["failed_authentications"] += 1
                api_key.failed_requests += 1
                return AuthenticationResult(
                    authenticated=False,
                    error=rate_error,
                    retry_after=retry_after,
                )

            # Update usage
            api_key.last_used_at = datetime.utcnow()
            api_key.total_requests += 1
            api_key.successful_requests += 1
            self._stats["successful_authentications"] += 1

            return AuthenticationResult(
                authenticated=True,
                key=api_key,
            )

    def authorize(
        self,
        raw_key: str,
        required_scope: APIKeyScope,
    ) -> AuthenticationResult:
        """Authenticate and authorize an API key for a specific scope.

        Args:
            raw_key: The raw API key string
            required_scope: The required permission scope

        Returns:
            AuthenticationResult with authorization status
        """
        # First authenticate
        auth_result = self.authenticate(raw_key)
        if not auth_result.authenticated:
            return auth_result

        # Then check scope
        if not auth_result.key.has_scope(required_scope):
            auth_result.key.failed_requests += 1
            return AuthenticationResult(
                authenticated=False,
                error=f"Missing required scope: {required_scope.value}",
            )

        return auth_result

    def get_key(self, key_id: str) -> Optional[APIKey]:
        """Get an API key by ID."""
        with self._lock:
            return self._keys.get(key_id)

    def list_keys(
        self,
        status: Optional[APIKeyStatus] = None,
        created_by: Optional[str] = None,
        include_expired: bool = False,
    ) -> List[APIKey]:
        """List API keys with optional filters."""
        with self._lock:
            keys = list(self._keys.values())

        if status:
            keys = [k for k in keys if k.status == status]

        if created_by:
            keys = [k for k in keys if k.created_by == created_by]

        if not include_expired:
            now = datetime.utcnow()
            keys = [k for k in keys if not k.expires_at or k.expires_at > now]

        return keys

    def revoke_key(self, key_id: str, reason: Optional[str] = None) -> bool:
        """Revoke an API key.

        Args:
            key_id: The key ID to revoke
            reason: Optional reason for revocation

        Returns:
            True if key was revoked, False if not found
        """
        with self._lock:
            api_key = self._keys.get(key_id)
            if not api_key:
                return False

            api_key.status = APIKeyStatus.REVOKED
            if reason:
                api_key.metadata["revocation_reason"] = reason
            api_key.metadata["revoked_at"] = datetime.utcnow().isoformat()
            self._stats["keys_revoked"] += 1

        self._notify_listeners("revoked", key_id, api_key)
        return True

    def suspend_key(self, key_id: str, reason: Optional[str] = None) -> bool:
        """Suspend an API key temporarily.

        Args:
            key_id: The key ID to suspend
            reason: Optional reason for suspension

        Returns:
            True if key was suspended, False if not found
        """
        with self._lock:
            api_key = self._keys.get(key_id)
            if not api_key:
                return False

            api_key.status = APIKeyStatus.SUSPENDED
            if reason:
                api_key.metadata["suspension_reason"] = reason
            api_key.metadata["suspended_at"] = datetime.utcnow().isoformat()

        self._notify_listeners("suspended", key_id, api_key)
        return True

    def reactivate_key(self, key_id: str) -> bool:
        """Reactivate a suspended API key.

        Args:
            key_id: The key ID to reactivate

        Returns:
            True if key was reactivated, False if not found or not suspended
        """
        with self._lock:
            api_key = self._keys.get(key_id)
            if not api_key:
                return False

            if api_key.status != APIKeyStatus.SUSPENDED:
                return False

            api_key.status = APIKeyStatus.ACTIVE
            api_key.metadata["reactivated_at"] = datetime.utcnow().isoformat()

        self._notify_listeners("reactivated", key_id, api_key)
        return True

    def rotate_key(
        self,
        key_id: str,
        grace_period_hours: int = 24,
    ) -> Tuple[Optional[str], Optional[APIKey]]:
        """Rotate an API key.

        Creates a new key with the same settings and schedules the old key
        for expiration after the grace period.

        Args:
            key_id: The key ID to rotate
            grace_period_hours: Hours before old key expires

        Returns:
            Tuple of (new_raw_key, new_APIKey) or (None, None) if not found
        """
        with self._lock:
            old_key = self._keys.get(key_id)
            if not old_key:
                return None, None

            # Create new key with same settings
            new_raw_key, new_key = self.generate_key(
                name=f"{old_key.name} (rotated)",
                description=old_key.description,
                scopes=old_key.scopes.copy(),
                rate_limit=APIKeyRateLimit(
                    requests_per_minute=old_key.rate_limit.requests_per_minute,
                    requests_per_hour=old_key.rate_limit.requests_per_hour,
                    requests_per_day=old_key.rate_limit.requests_per_day,
                    burst_limit=old_key.rate_limit.burst_limit,
                ),
                created_by=old_key.created_by,
                metadata={
                    **old_key.metadata,
                    "rotated_from": key_id,
                    "rotated_at": datetime.utcnow().isoformat(),
                },
            )

            # Schedule old key expiration
            old_key.expires_at = datetime.utcnow() + timedelta(hours=grace_period_hours)
            old_key.metadata["rotated_to"] = new_key.key_id
            old_key.metadata["rotation_grace_period_ends"] = old_key.expires_at.isoformat()

        self._notify_listeners("rotated", key_id, old_key)
        return new_raw_key, new_key

    def update_scopes(
        self,
        key_id: str,
        scopes: Set[APIKeyScope],
    ) -> bool:
        """Update the scopes for an API key.

        Args:
            key_id: The key ID to update
            scopes: New set of scopes

        Returns:
            True if updated, False if not found
        """
        with self._lock:
            api_key = self._keys.get(key_id)
            if not api_key:
                return False

            old_scopes = api_key.scopes.copy()
            api_key.scopes = scopes
            api_key.metadata["scopes_updated_at"] = datetime.utcnow().isoformat()
            api_key.metadata["previous_scopes"] = [s.value for s in old_scopes]

        self._notify_listeners("scopes_updated", key_id, api_key)
        return True

    def update_rate_limit(
        self,
        key_id: str,
        rate_limit: APIKeyRateLimit,
    ) -> bool:
        """Update the rate limit for an API key.

        Args:
            key_id: The key ID to update
            rate_limit: New rate limit configuration

        Returns:
            True if updated, False if not found
        """
        with self._lock:
            api_key = self._keys.get(key_id)
            if not api_key:
                return False

            api_key.rate_limit = rate_limit
            api_key.metadata["rate_limit_updated_at"] = datetime.utcnow().isoformat()

        self._notify_listeners("rate_limit_updated", key_id, api_key)
        return True

    def get_usage_stats(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get usage statistics for an API key."""
        with self._lock:
            api_key = self._keys.get(key_id)
            if not api_key:
                return None

            return {
                "key_id": key_id,
                "total_requests": api_key.total_requests,
                "successful_requests": api_key.successful_requests,
                "failed_requests": api_key.failed_requests,
                "success_rate": (
                    api_key.successful_requests / api_key.total_requests
                    if api_key.total_requests > 0
                    else 0
                ),
                "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                "rate_limit_remaining": api_key.rate_limit.get_remaining(),
            }

    def get_service_stats(self) -> Dict[str, Any]:
        """Get overall service statistics."""
        with self._lock:
            active_keys = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.ACTIVE)
            suspended_keys = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.SUSPENDED)
            revoked_keys = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.REVOKED)
            expired_keys = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.EXPIRED)

            return {
                **self._stats,
                "total_keys": len(self._keys),
                "active_keys": active_keys,
                "suspended_keys": suspended_keys,
                "revoked_keys": revoked_keys,
                "expired_keys": expired_keys,
                "authentication_success_rate": (
                    self._stats["successful_authentications"] / self._stats["total_authentications"]
                    if self._stats["total_authentications"] > 0
                    else 0
                ),
            }

    def add_listener(self, listener: Callable[[str, str, APIKey], None]) -> None:
        """Add a listener for key events.

        Args:
            listener: Callback function(event_type, key_id, api_key)
        """
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, str, APIKey], None]) -> None:
        """Remove a key event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event_type: str, key_id: str, api_key: APIKey) -> None:
        """Notify all listeners of a key event."""
        for listener in self._listeners:
            try:
                listener(event_type, key_id, api_key)
            except Exception:
                pass  # Don't let listener errors affect key operations

    def _hash_key(self, raw_key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def delete_key(self, key_id: str) -> bool:
        """Permanently delete an API key.

        Args:
            key_id: The key ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            api_key = self._keys.get(key_id)
            if not api_key:
                return False

            # Remove from indexes
            del self._keys[key_id]
            if api_key.key_hash in self._key_hash_index:
                del self._key_hash_index[api_key.key_hash]

        self._notify_listeners("deleted", key_id, api_key)
        return True

    def cleanup_expired(self) -> int:
        """Remove expired keys from storage.

        Returns:
            Number of keys removed
        """
        now = datetime.utcnow()
        to_remove = []

        with self._lock:
            for key_id, api_key in self._keys.items():
                if api_key.expires_at and api_key.expires_at < now:
                    to_remove.append(key_id)

            for key_id in to_remove:
                api_key = self._keys[key_id]
                del self._keys[key_id]
                if api_key.key_hash in self._key_hash_index:
                    del self._key_hash_index[api_key.key_hash]

        return len(to_remove)


# Singleton instance
_api_key_service: Optional[KGAPIKeyService] = None
_service_lock = threading.Lock()


def get_api_key_service() -> KGAPIKeyService:
    """Get the singleton API key service instance."""
    global _api_key_service
    if _api_key_service is None:
        with _service_lock:
            if _api_key_service is None:
                _api_key_service = KGAPIKeyService()
    return _api_key_service


def reset_api_key_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _api_key_service
    with _service_lock:
        _api_key_service = None
