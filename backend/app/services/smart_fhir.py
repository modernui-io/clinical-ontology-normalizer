"""SMART on FHIR client service for EHR connectivity.

Provides OAuth2 authorization code flow with PKCE support for
Epic, Cerner, and other SMART on FHIR compliant EHR systems.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.smart_config import (
    EHRVendor,
    SMARTSettings,
    WellKnownConfig,
    build_authorization_url,
    discover_smart_configuration,
    smart_settings,
)

logger = logging.getLogger(__name__)


class TokenType(str, Enum):
    """OAuth2 token types."""

    BEARER = "Bearer"


class LaunchContext(BaseModel):
    """SMART launch context from EHR."""

    patient: str | None = Field(None, description="Patient ID in context")
    encounter: str | None = Field(None, description="Encounter ID in context")
    location: str | None = Field(None, description="Location ID in context")
    fhir_user: str | None = Field(None, description="FHIR User reference")
    need_patient_banner: bool = Field(
        True, description="Whether to show patient banner"
    )
    intent: str | None = Field(None, description="Launch intent")
    smart_style_url: str | None = Field(None, description="Style URL for branding")


class TokenSet(BaseModel):
    """OAuth2 token set from authorization."""

    access_token: str
    token_type: TokenType = TokenType.BEARER
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    id_token: str | None = None

    # Computed fields
    expires_at: datetime | None = None
    obtained_at: datetime = Field(default_factory=datetime.utcnow)

    # Launch context
    patient: str | None = None
    encounter: str | None = None
    fhir_user: str | None = None
    need_patient_banner: bool = True
    smart_style_url: str | None = None

    def model_post_init(self, __context: Any) -> None:
        """Calculate expiration time after initialization."""
        if self.expires_in and not self.expires_at:
            self.expires_at = self.obtained_at + timedelta(seconds=self.expires_in)

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def should_refresh(self) -> bool:
        """Check if the token should be refreshed (within threshold)."""
        if not self.expires_at:
            return False
        threshold = timedelta(
            seconds=smart_settings.token_refresh_threshold_seconds
        )
        return datetime.now(timezone.utc) >= (self.expires_at - threshold)

    def get_launch_context(self) -> LaunchContext:
        """Get the launch context from this token set."""
        return LaunchContext(
            patient=self.patient,
            encounter=self.encounter,
            fhir_user=self.fhir_user,
            need_patient_banner=self.need_patient_banner,
            smart_style_url=self.smart_style_url,
        )


@dataclass
class OAuthState:
    """OAuth state for CSRF protection and session tracking."""

    state: str
    code_verifier: str | None = None  # For PKCE
    fhir_base_url: str = ""
    scopes: list[str] = field(default_factory=list)
    launch_token: str | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if the state has expired."""
        ttl = smart_settings.state_ttl_seconds
        return (time.time() - self.created_at) > ttl


class SMARTClientError(Exception):
    """Base exception for SMART client errors."""

    pass


class AuthorizationError(SMARTClientError):
    """Error during authorization flow."""

    pass


class TokenError(SMARTClientError):
    """Error during token exchange or refresh."""

    pass


class FHIRRequestError(SMARTClientError):
    """Error making FHIR API requests."""

    pass


# VP-Caching-1: Bounded TTL cache for SMART configurations
class SMARTConfigCache:
    """Thread-safe bounded cache with TTL for SMART configurations.

    Prevents unbounded memory growth when connecting to many FHIR servers.
    Uses LRU eviction when capacity is reached.
    """

    def __init__(
        self,
        maxsize: int = 100,
        ttl_seconds: float = 3600.0,  # 1 hour default
    ) -> None:
        """Initialize the cache.

        Args:
            maxsize: Maximum number of entries to store.
            ttl_seconds: Time-to-live for each entry in seconds.
        """
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[WellKnownConfig, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> WellKnownConfig | None:
        """Get a value from the cache if it exists and hasn't expired."""
        with self._lock:
            if key not in self._cache:
                return None

            config, timestamp = self._cache[key]
            if time.time() - timestamp > self._ttl:
                # Expired, remove it
                del self._cache[key]
                return None

            # Move to end for LRU
            self._cache.move_to_end(key)
            return config

    def set(self, key: str, value: WellKnownConfig) -> None:
        """Store a value in the cache."""
        with self._lock:
            # If key exists, update and move to end
            if key in self._cache:
                self._cache[key] = (value, time.time())
                self._cache.move_to_end(key)
                return

            # Evict oldest if at capacity
            while len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)

            self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        """Return the number of entries in the cache."""
        with self._lock:
            return len(self._cache)


class SMARTClient:
    """SMART on FHIR client for OAuth2 authorization and FHIR access.

    Implements the SMART App Launch Framework for EHR connectivity.
    Supports both standalone launch and EHR launch flows.

    Usage:
        client = SMARTClient.get_instance()

        # Start authorization
        auth_url, state = await client.initiate_authorization(
            fhir_base_url="https://ehr.example.com/fhir",
            scopes=["patient/*.read", "openid", "fhirUser"]
        )

        # After callback with code
        tokens = await client.exchange_code(code, state)

        # Access FHIR resources
        patient = await client.get_patient(tokens.patient, tokens.access_token)
    """

    _instance: "SMARTClient | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, settings: SMARTSettings | None = None):
        """Initialize the SMART client.

        Args:
            settings: Optional custom settings (uses singleton otherwise)
        """
        self._settings = settings or smart_settings
        self._http_client: httpx.AsyncClient | None = None
        self._pending_states: dict[str, OAuthState] = {}
        self._active_tokens: dict[str, TokenSet] = {}  # Keyed by session_id
        # VP-Caching-1: Use bounded TTL cache for SMART configurations
        self._smart_configs = SMARTConfigCache(maxsize=100, ttl_seconds=3600.0)

    @classmethod
    def get_instance(cls, settings: SMARTSettings | None = None) -> "SMARTClient":
        """Get the singleton instance of SMARTClient.

        Args:
            settings: Optional custom settings for first initialization

        Returns:
            SMARTClient singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(settings)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def _generate_state(self) -> str:
        """Generate a cryptographically secure state parameter."""
        return secrets.token_urlsafe(32)

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate 32 bytes (256 bits) of random data
        code_verifier = secrets.token_urlsafe(32)

        # Create SHA-256 hash and base64url encode
        code_challenge_bytes = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = (
            base64.urlsafe_b64encode(code_challenge_bytes)
            .decode("ascii")
            .rstrip("=")
        )

        return code_verifier, code_challenge

    async def get_smart_config(
        self,
        fhir_base_url: str,
        force_refresh: bool = False,
    ) -> WellKnownConfig | None:
        """Get SMART configuration for a FHIR server.

        Args:
            fhir_base_url: Base URL of the FHIR server
            force_refresh: Force refresh of cached config

        Returns:
            WellKnownConfig if available
        """
        # VP-Caching-1: Use bounded cache methods
        if not force_refresh:
            cached = self._smart_configs.get(fhir_base_url)
            if cached is not None:
                return cached

        config = await discover_smart_configuration(
            fhir_base_url,
            self._settings.ehr_vendor,
        )

        if config:
            self._smart_configs.set(fhir_base_url, config)

        return config

    async def initiate_authorization(
        self,
        fhir_base_url: str | None = None,
        scopes: list[str] | None = None,
        launch_token: str | None = None,
    ) -> tuple[str, str]:
        """Initiate the OAuth2 authorization flow.

        Args:
            fhir_base_url: FHIR server base URL (uses settings default if None)
            scopes: Scopes to request (uses settings default if None)
            launch_token: EHR launch token (for EHR launch flow)

        Returns:
            Tuple of (authorization_url, state)

        Raises:
            AuthorizationError: If SMART configuration cannot be discovered
        """
        fhir_base_url = fhir_base_url or self._settings.fhir_base_url
        scopes = scopes or self._settings.default_scopes

        # Discover SMART configuration
        config = await self.get_smart_config(fhir_base_url)
        if not config:
            raise AuthorizationError(
                f"Could not discover SMART configuration for {fhir_base_url}"
            )

        # Generate state and PKCE
        state = self._generate_state()
        code_verifier = None
        code_challenge = None

        if self._settings.pkce_enabled:
            code_verifier, code_challenge = self._generate_pkce_pair()

        # Store state for validation
        oauth_state = OAuthState(
            state=state,
            code_verifier=code_verifier,
            fhir_base_url=fhir_base_url,
            scopes=scopes,
            launch_token=launch_token,
        )
        self._pending_states[state] = oauth_state

        # Build authorization URL
        auth_url = build_authorization_url(
            authorization_endpoint=config.authorization_endpoint,
            client_id=self._settings.client_id,
            redirect_uri=self._settings.redirect_uri,
            scope=" ".join(scopes),
            state=state,
            aud=fhir_base_url,
            launch=launch_token,
            code_challenge=code_challenge,
        )

        logger.info(
            f"Initiated SMART authorization for {fhir_base_url}, state={state[:8]}..."
        )
        return auth_url, state

    async def exchange_code(
        self,
        code: str,
        state: str,
        session_id: str | None = None,
    ) -> TokenSet:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback
            state: State parameter from callback
            session_id: Optional session ID to associate tokens with

        Returns:
            TokenSet with access token and context

        Raises:
            AuthorizationError: If state is invalid or expired
            TokenError: If token exchange fails
        """
        # Validate state
        oauth_state = self._pending_states.pop(state, None)
        if not oauth_state:
            raise AuthorizationError("Invalid or expired state parameter")

        if oauth_state.is_expired:
            raise AuthorizationError("State parameter has expired")

        # Get SMART configuration
        config = await self.get_smart_config(oauth_state.fhir_base_url)
        if not config:
            raise AuthorizationError("SMART configuration not available")

        # Prepare token request
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._settings.redirect_uri,
            "client_id": self._settings.client_id,
        }

        # Add client secret if configured (confidential apps)
        if self._settings.client_secret:
            token_data["client_secret"] = self._settings.client_secret

        # Add PKCE code verifier if used
        if oauth_state.code_verifier:
            token_data["code_verifier"] = oauth_state.code_verifier

        # Exchange code for tokens
        client = await self._get_http_client()
        try:
            response = await client.post(
                config.token_endpoint,
                data=token_data,
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error_description", response.text)
                raise TokenError(f"Token exchange failed: {error_msg}")

            token_response = response.json()

        except httpx.RequestError as e:
            raise TokenError(f"Token request failed: {e}")

        # Create token set
        tokens = TokenSet(
            access_token=token_response["access_token"],
            token_type=TokenType(token_response.get("token_type", "Bearer")),
            expires_in=token_response.get("expires_in"),
            refresh_token=token_response.get("refresh_token"),
            scope=token_response.get("scope"),
            id_token=token_response.get("id_token"),
            patient=token_response.get("patient"),
            encounter=token_response.get("encounter"),
            fhir_user=token_response.get("fhirUser"),
            need_patient_banner=token_response.get("need_patient_banner", True),
            smart_style_url=token_response.get("smart_style_url"),
        )

        # Store tokens if session_id provided
        if session_id:
            self._active_tokens[session_id] = tokens

        logger.info(
            f"Token exchange successful, patient={tokens.patient}, "
            f"encounter={tokens.encounter}"
        )
        return tokens

    async def refresh_token(
        self,
        refresh_token: str,
        fhir_base_url: str | None = None,
        session_id: str | None = None,
    ) -> TokenSet:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token
            fhir_base_url: FHIR server base URL
            session_id: Optional session ID to update stored tokens

        Returns:
            New TokenSet

        Raises:
            TokenError: If refresh fails
        """
        fhir_base_url = fhir_base_url or self._settings.fhir_base_url
        config = await self.get_smart_config(fhir_base_url)
        if not config:
            raise TokenError("SMART configuration not available")

        # Prepare refresh request
        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._settings.client_id,
        }

        if self._settings.client_secret:
            token_data["client_secret"] = self._settings.client_secret

        # Make refresh request
        client = await self._get_http_client()
        try:
            response = await client.post(
                config.token_endpoint,
                data=token_data,
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error_description", response.text)
                raise TokenError(f"Token refresh failed: {error_msg}")

            token_response = response.json()

        except httpx.RequestError as e:
            raise TokenError(f"Token refresh request failed: {e}")

        # Create new token set
        tokens = TokenSet(
            access_token=token_response["access_token"],
            token_type=TokenType(token_response.get("token_type", "Bearer")),
            expires_in=token_response.get("expires_in"),
            refresh_token=token_response.get("refresh_token", refresh_token),
            scope=token_response.get("scope"),
            id_token=token_response.get("id_token"),
            patient=token_response.get("patient"),
            encounter=token_response.get("encounter"),
        )

        # Update stored tokens if session_id provided
        if session_id:
            self._active_tokens[session_id] = tokens

        logger.info("Token refresh successful")
        return tokens

    async def revoke_token(
        self,
        token: str,
        fhir_base_url: str | None = None,
        token_type_hint: str = "access_token",
    ) -> bool:
        """Revoke an access or refresh token.

        Args:
            token: The token to revoke
            fhir_base_url: FHIR server base URL
            token_type_hint: Type of token ("access_token" or "refresh_token")

        Returns:
            True if revocation succeeded
        """
        fhir_base_url = fhir_base_url or self._settings.fhir_base_url
        config = await self.get_smart_config(fhir_base_url)

        if not config or not config.revocation_endpoint:
            logger.warning("Token revocation not supported by server")
            return False

        # Prepare revocation request
        revoke_data = {
            "token": token,
            "token_type_hint": token_type_hint,
            "client_id": self._settings.client_id,
        }

        if self._settings.client_secret:
            revoke_data["client_secret"] = self._settings.client_secret

        # Make revocation request
        client = await self._get_http_client()
        try:
            response = await client.post(
                config.revocation_endpoint,
                data=revoke_data,
            )

            # RFC 7009: 200 indicates success, even if token was already invalid
            if response.status_code == 200:
                logger.info("Token revoked successfully")
                return True

            logger.warning(f"Token revocation failed: {response.status_code}")
            return False

        except httpx.RequestError as e:
            logger.error(f"Token revocation request failed: {e}")
            return False

    def get_tokens(self, session_id: str) -> TokenSet | None:
        """Get stored tokens for a session.

        Args:
            session_id: Session identifier

        Returns:
            TokenSet if available and not expired
        """
        tokens = self._active_tokens.get(session_id)
        if tokens and not tokens.is_expired:
            return tokens
        return None

    def remove_tokens(self, session_id: str) -> None:
        """Remove stored tokens for a session.

        Args:
            session_id: Session identifier
        """
        self._active_tokens.pop(session_id, None)

    async def get_patient(
        self,
        patient_id: str,
        access_token: str,
        fhir_base_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a Patient resource using authorized access.

        Args:
            patient_id: FHIR Patient ID
            access_token: Valid access token
            fhir_base_url: FHIR server base URL

        Returns:
            Patient resource or None if not found
        """
        fhir_base_url = fhir_base_url or self._settings.fhir_base_url
        client = await self._get_http_client()

        try:
            response = await client.get(
                f"{fhir_base_url}/Patient/{patient_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/fhir+json",
                },
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise FHIRRequestError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise FHIRRequestError("Access denied to patient resource")
            elif response.status_code == 404:
                return None
            else:
                raise FHIRRequestError(
                    f"FHIR request failed: {response.status_code}"
                )

        except httpx.RequestError as e:
            raise FHIRRequestError(f"FHIR request error: {e}")

    async def get_encounter(
        self,
        encounter_id: str,
        access_token: str,
        fhir_base_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch an Encounter resource using authorized access.

        Args:
            encounter_id: FHIR Encounter ID
            access_token: Valid access token
            fhir_base_url: FHIR server base URL

        Returns:
            Encounter resource or None if not found
        """
        fhir_base_url = fhir_base_url or self._settings.fhir_base_url
        client = await self._get_http_client()

        try:
            response = await client.get(
                f"{fhir_base_url}/Encounter/{encounter_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/fhir+json",
                },
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise FHIRRequestError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise FHIRRequestError("Access denied to encounter resource")
            elif response.status_code == 404:
                return None
            else:
                raise FHIRRequestError(
                    f"FHIR request failed: {response.status_code}"
                )

        except httpx.RequestError as e:
            raise FHIRRequestError(f"FHIR request error: {e}")

    async def search_resources(
        self,
        resource_type: str,
        access_token: str,
        params: dict[str, str] | None = None,
        fhir_base_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for FHIR resources using authorized access.

        Args:
            resource_type: FHIR resource type (e.g., "Condition")
            access_token: Valid access token
            params: Search parameters
            fhir_base_url: FHIR server base URL

        Returns:
            List of matching resources
        """
        fhir_base_url = fhir_base_url or self._settings.fhir_base_url
        client = await self._get_http_client()

        try:
            response = await client.get(
                f"{fhir_base_url}/{resource_type}",
                params=params or {},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/fhir+json",
                },
            )

            if response.status_code == 200:
                bundle = response.json()
                entries = bundle.get("entry", [])
                return [entry.get("resource", {}) for entry in entries]
            elif response.status_code == 401:
                raise FHIRRequestError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise FHIRRequestError(f"Access denied to {resource_type}")
            else:
                raise FHIRRequestError(
                    f"FHIR search failed: {response.status_code}"
                )

        except httpx.RequestError as e:
            raise FHIRRequestError(f"FHIR request error: {e}")

    def cleanup_expired_states(self) -> int:
        """Remove expired OAuth states.

        Returns:
            Number of expired states removed
        """
        expired = [
            state for state, oauth_state in self._pending_states.items()
            if oauth_state.is_expired
        ]
        for state in expired:
            del self._pending_states[state]
        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary with client stats
        """
        return {
            "pending_states": len(self._pending_states),
            "active_sessions": len(self._active_tokens),
            "cached_configs": len(self._smart_configs),
            "pkce_enabled": self._settings.pkce_enabled,
            "ehr_vendor": self._settings.ehr_vendor.value,
        }


# Module-level accessor functions
def get_smart_client() -> SMARTClient:
    """Get the singleton SMART client instance.

    Returns:
        SMARTClient singleton
    """
    return SMARTClient.get_instance()


def reset_smart_client() -> None:
    """Reset the singleton SMART client instance (for testing)."""
    SMARTClient.reset_instance()


# VP-Lifecycle-2: Cleanup function for application shutdown
async def close_smart_client() -> None:
    """Close the SMART client HTTP connection on shutdown.

    Should be called during application shutdown to properly close
    the httpx.AsyncClient and free resources.
    """
    if SMARTClient._instance is not None:
        await SMARTClient._instance.close()
        logger.debug("SMARTClient HTTP client closed")
