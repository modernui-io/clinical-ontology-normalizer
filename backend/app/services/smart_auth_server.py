"""SMART on FHIR Authorization Server Service.

This service implements a full SMART on FHIR authorization server with:
- OAuth2 authorization code flow with PKCE support
- Client credentials grant for backend services
- Launch context handling for EHR integration
- SMART-compliant access token generation

The authorization server enables third-party SMART applications to:
- Register and authenticate as OAuth2 clients
- Request user authorization for FHIR resource access
- Exchange authorization codes for access tokens
- Use refresh tokens for long-lived access
- Receive patient and encounter context from EHR launches

Security features:
- PKCE (RFC 7636) for public clients
- Bcrypt hashing for client secrets
- JWT access tokens with SMART-specific claims
- Short-lived authorization codes (10 minutes)
- Scope validation and intersection
"""

import base64
import hashlib
import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.rbac import User, UserRole, Role
from app.models.smart_app import SMARTApp, SMARTAuthorizationCode

logger = logging.getLogger(__name__)

# Authorization code settings
AUTH_CODE_EXPIRE_MINUTES = 10
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30

# JWT configuration
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = "HS256"


@dataclass
class TokenResponse:
    """OAuth2 token response per SMART on FHIR spec."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_token: str | None = None
    scope: str = ""
    id_token: str | None = None

    # SMART launch context
    patient: str | None = None
    encounter: str | None = None
    fhir_user: str | None = None
    need_patient_banner: bool = True
    smart_style_url: str | None = None


@dataclass
class AppRegistration:
    """Result of SMART app registration."""

    client_id: str
    client_secret: str | None = None  # Only for confidential clients
    name: str = ""
    redirect_uris: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    grant_types: list[str] = field(default_factory=list)
    is_confidential: bool = False


@dataclass
class ClientValidation:
    """Result of client validation."""

    valid: bool
    app: SMARTApp | None = None
    error: str | None = None


@dataclass
class ScopeValidation:
    """Result of scope validation."""

    valid: bool
    granted_scopes: list[str] = field(default_factory=list)
    rejected_scopes: list[str] = field(default_factory=list)


class SMARTAuthServerError(Exception):
    """Base exception for SMART auth server errors."""

    pass


class InvalidClientError(SMARTAuthServerError):
    """Error for invalid client credentials."""

    pass


class InvalidGrantError(SMARTAuthServerError):
    """Error for invalid authorization code or grant."""

    pass


class InvalidScopeError(SMARTAuthServerError):
    """Error for invalid or unauthorized scopes."""

    pass


class SMARTAuthServer:
    """SMART on FHIR Authorization Server.

    Implements OAuth2 authorization server functionality for SMART on FHIR
    applications. Supports both public and confidential clients, PKCE
    for enhanced security, and EHR launch context.

    Usage:
        server = get_smart_auth_server()

        # Register a new app
        registration = await server.register_app(
            db,
            name="My Clinical App",
            redirect_uris=["https://myapp.com/callback"],
            scopes=["patient/*.read", "openid"],
            is_confidential=True
        )

        # Create authorization code after user consent
        code = await server.create_authorization_code(
            db,
            client_id=registration.client_id,
            user_id=user.id,
            redirect_uri="https://myapp.com/callback",
            scope="patient/*.read openid",
            patient_id="patient-123"
        )

        # Exchange code for tokens
        tokens = await server.exchange_code(
            db,
            code=code,
            client_id=registration.client_id,
            client_secret=registration.client_secret,
            redirect_uri="https://myapp.com/callback"
        )
    """

    def __init__(
        self,
        secret_key: str = JWT_SECRET_KEY,
        algorithm: str = JWT_ALGORITHM,
        access_token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days: int = REFRESH_TOKEN_EXPIRE_DAYS,
        auth_code_expire_minutes: int = AUTH_CODE_EXPIRE_MINUTES,
    ) -> None:
        """Initialize the SMART auth server.

        Args:
            secret_key: Secret key for JWT signing
            algorithm: JWT algorithm (HS256)
            access_token_expire_minutes: Access token TTL in minutes
            refresh_token_expire_days: Refresh token TTL in days
            auth_code_expire_minutes: Authorization code TTL in minutes
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.auth_code_expire_minutes = auth_code_expire_minutes

        # In-memory launch context store (for development)
        # In production, use Redis or database
        self._launch_contexts: dict[str, dict[str, str | None]] = {}

    # -------------------------------------------------------------------------
    # Password/Secret Hashing
    # -------------------------------------------------------------------------

    def _hash_secret(self, secret: str) -> str:
        """Hash a client secret using bcrypt.

        Args:
            secret: Plain text secret

        Returns:
            Bcrypt hashed secret
        """
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(secret.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def _verify_secret(self, secret: str, hashed_secret: str) -> bool:
        """Verify a client secret against its hash.

        Args:
            secret: Plain text secret to verify
            hashed_secret: Stored bcrypt hash

        Returns:
            True if secret matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                secret.encode("utf-8"),
                hashed_secret.encode("utf-8"),
            )
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # PKCE Support
    # -------------------------------------------------------------------------

    def _verify_pkce(self, code_challenge: str, code_verifier: str) -> bool:
        """Verify PKCE code challenge using S256 method.

        Args:
            code_challenge: The original code challenge from auth request
            code_verifier: The code verifier from token request

        Returns:
            True if verification passes, False otherwise
        """
        if not code_challenge or not code_verifier:
            return False

        try:
            # S256: SHA-256 hash of code_verifier, base64url encoded
            verifier_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
            computed_challenge = (
                base64.urlsafe_b64encode(verifier_hash)
                .decode("ascii")
                .rstrip("=")
            )
            return secrets.compare_digest(code_challenge, computed_challenge)
        except Exception as e:
            logger.warning(f"PKCE verification error: {e}")
            return False

    # -------------------------------------------------------------------------
    # App Registration
    # -------------------------------------------------------------------------

    async def register_app(
        self,
        db: AsyncSession,
        name: str,
        redirect_uris: list[str],
        scopes: list[str],
        grant_types: list[str] | None = None,
        is_confidential: bool = True,
        launch_url: str | None = None,
    ) -> AppRegistration:
        """Register a new SMART application.

        Creates a new OAuth2 client with generated credentials.
        For confidential clients, a client_secret is generated and hashed.

        Args:
            db: Database session
            name: Human-readable application name
            redirect_uris: List of allowed redirect URIs
            scopes: List of SMART scopes the app can request
            grant_types: Allowed OAuth2 grant types (defaults to auth_code + refresh)
            is_confidential: Whether this is a confidential client
            launch_url: Optional EHR launch URL

        Returns:
            AppRegistration with client credentials
        """
        if grant_types is None:
            grant_types = ["authorization_code", "refresh_token"]

        # Generate client credentials
        client_id = f"smart-{secrets.token_urlsafe(16)}"
        client_secret = None
        client_secret_hash = None

        if is_confidential:
            client_secret = secrets.token_urlsafe(32)
            client_secret_hash = self._hash_secret(client_secret)

        # Create the app record
        app = SMARTApp(
            client_id=client_id,
            client_secret_hash=client_secret_hash,
            app_name=name,
            redirect_uris=redirect_uris,
            scopes=scopes,
            grant_types=grant_types,
            is_confidential=is_confidential,
            launch_url=launch_url,
            is_active=True,
        )
        db.add(app)
        await db.commit()
        await db.refresh(app)

        logger.info(f"Registered SMART app: {name} (client_id={client_id})")

        return AppRegistration(
            client_id=client_id,
            client_secret=client_secret,
            name=name,
            redirect_uris=redirect_uris,
            scopes=scopes,
            grant_types=grant_types,
            is_confidential=is_confidential,
        )

    # -------------------------------------------------------------------------
    # Client Validation
    # -------------------------------------------------------------------------

    async def validate_client(
        self,
        db: AsyncSession,
        client_id: str,
        client_secret: str | None = None,
    ) -> ClientValidation:
        """Validate OAuth2 client credentials.

        For confidential clients, both client_id and client_secret are required.
        For public clients, only client_id is required.

        Args:
            db: Database session
            client_id: OAuth2 client identifier
            client_secret: Optional client secret for confidential clients

        Returns:
            ClientValidation with validation result
        """
        # Find the app
        stmt = select(SMARTApp).where(
            SMARTApp.client_id == client_id,
            SMARTApp.is_active == True,  # noqa: E712
        )
        result = await db.execute(stmt)
        app = result.scalar_one_or_none()

        if not app:
            return ClientValidation(
                valid=False,
                error="Unknown client_id or inactive application",
            )

        # Validate client secret for confidential clients
        if app.is_confidential:
            if not client_secret:
                return ClientValidation(
                    valid=False,
                    error="Client secret required for confidential clients",
                )

            if not app.client_secret_hash:
                return ClientValidation(
                    valid=False,
                    error="Application misconfigured: no secret hash",
                )

            if not self._verify_secret(client_secret, app.client_secret_hash):
                logger.warning(f"Invalid client secret for: {client_id}")
                return ClientValidation(
                    valid=False,
                    error="Invalid client secret",
                )

        return ClientValidation(valid=True, app=app)

    # -------------------------------------------------------------------------
    # Scope Validation
    # -------------------------------------------------------------------------

    def validate_scopes(
        self,
        requested_scopes: list[str],
        registered_scopes: list[str],
    ) -> ScopeValidation:
        """Validate and intersect requested scopes with registered scopes.

        Returns only the scopes that are both requested and allowed.

        Args:
            requested_scopes: Scopes requested by the client
            registered_scopes: Scopes the client is allowed to request

        Returns:
            ScopeValidation with granted and rejected scopes
        """
        requested_set = set(requested_scopes)
        registered_set = set(registered_scopes)

        granted = list(requested_set & registered_set)
        rejected = list(requested_set - registered_set)

        return ScopeValidation(
            valid=len(granted) > 0,
            granted_scopes=granted,
            rejected_scopes=rejected,
        )

    # -------------------------------------------------------------------------
    # Launch Context
    # -------------------------------------------------------------------------

    def create_launch_context(
        self,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ) -> str:
        """Create a launch context token for EHR launch flow.

        The launch token is an opaque identifier that maps to the
        patient and encounter context selected by the user in the EHR.

        Args:
            patient_id: FHIR Patient ID
            encounter_id: FHIR Encounter ID

        Returns:
            Opaque launch token
        """
        launch_token = secrets.token_urlsafe(32)

        self._launch_contexts[launch_token] = {
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.debug(
            f"Created launch context: token={launch_token[:8]}..., "
            f"patient={patient_id}, encounter={encounter_id}"
        )

        return launch_token

    def resolve_launch_context(
        self,
        launch_token: str,
    ) -> dict[str, str | None] | None:
        """Resolve a launch token to patient/encounter context.

        Args:
            launch_token: The opaque launch token

        Returns:
            Dictionary with patient_id and encounter_id, or None if not found
        """
        context = self._launch_contexts.pop(launch_token, None)

        if context:
            logger.debug(f"Resolved launch context: token={launch_token[:8]}...")
            return {
                "patient_id": context.get("patient_id"),
                "encounter_id": context.get("encounter_id"),
            }

        return None

    def cleanup_expired_contexts(self, max_age_minutes: int = 15) -> int:
        """Remove expired launch contexts.

        Args:
            max_age_minutes: Maximum age of contexts to keep

        Returns:
            Number of contexts removed
        """
        now = datetime.now(timezone.utc)
        expired = []

        for token, context in self._launch_contexts.items():
            created_str = context.get("created_at")
            if created_str:
                created = datetime.fromisoformat(created_str)
                if (now - created) > timedelta(minutes=max_age_minutes):
                    expired.append(token)

        for token in expired:
            del self._launch_contexts[token]

        return len(expired)

    # -------------------------------------------------------------------------
    # Authorization Code Flow
    # -------------------------------------------------------------------------

    async def create_authorization_code(
        self,
        db: AsyncSession,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ) -> str:
        """Create an authorization code after user consent.

        The authorization code is single-use and short-lived (10 minutes).
        It is bound to the specific client, user, redirect URI, and scope.

        Args:
            db: Database session
            client_id: OAuth2 client identifier
            user_id: User who authorized the request
            redirect_uri: Redirect URI from the authorization request
            scope: Space-separated scopes that were authorized
            code_challenge: PKCE code challenge (for public clients)
            code_challenge_method: PKCE method (should be "S256")
            patient_id: Patient context for EHR launch
            encounter_id: Encounter context for EHR launch

        Returns:
            The authorization code string

        Raises:
            InvalidClientError: If client_id is invalid
        """
        # Validate client exists
        stmt = select(SMARTApp).where(
            SMARTApp.client_id == client_id,
            SMARTApp.is_active == True,  # noqa: E712
        )
        result = await db.execute(stmt)
        app = result.scalar_one_or_none()

        if not app:
            raise InvalidClientError(f"Unknown client_id: {client_id}")

        # Validate redirect URI
        if redirect_uri not in app.redirect_uris:
            raise InvalidClientError(f"Invalid redirect_uri: {redirect_uri}")

        # Generate the authorization code
        code = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.auth_code_expire_minutes
        )

        # Create the authorization code record
        auth_code = SMARTAuthorizationCode(
            code=code,
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method or "S256",
            patient_id=patient_id,
            encounter_id=encounter_id,
            expires_at=expires_at,
            is_used=False,
        )
        db.add(auth_code)
        await db.commit()

        logger.info(
            f"Created authorization code for client={client_id}, "
            f"user={user_id[:8]}..., patient={patient_id}"
        )

        return code

    async def exchange_code(
        self,
        db: AsyncSession,
        code: str,
        client_id: str,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        code_verifier: str | None = None,
    ) -> TokenResponse:
        """Exchange an authorization code for tokens.

        Validates the code, client credentials, PKCE (if applicable),
        and issues access and refresh tokens.

        Args:
            db: Database session
            code: The authorization code to exchange
            client_id: OAuth2 client identifier
            client_secret: Client secret for confidential clients
            redirect_uri: Redirect URI (must match the original request)
            code_verifier: PKCE code verifier for public clients

        Returns:
            TokenResponse with access token and optional refresh token

        Raises:
            InvalidClientError: If client validation fails
            InvalidGrantError: If the code is invalid or expired
        """
        # Validate client
        client_validation = await self.validate_client(db, client_id, client_secret)
        if not client_validation.valid:
            raise InvalidClientError(client_validation.error or "Invalid client")

        app = client_validation.app
        if not app:
            raise InvalidClientError("Application not found")

        # Find the authorization code
        stmt = (
            select(SMARTAuthorizationCode)
            .options(selectinload(SMARTAuthorizationCode.user))
            .where(
                SMARTAuthorizationCode.code == code,
                SMARTAuthorizationCode.client_id == client_id,
            )
        )
        result = await db.execute(stmt)
        auth_code = result.scalar_one_or_none()

        if not auth_code:
            raise InvalidGrantError("Invalid authorization code")

        if auth_code.is_used:
            logger.warning(f"Attempted reuse of authorization code: {code[:8]}...")
            raise InvalidGrantError("Authorization code already used")

        if auth_code.expires_at < datetime.now(timezone.utc):
            raise InvalidGrantError("Authorization code expired")

        if redirect_uri and auth_code.redirect_uri != redirect_uri:
            raise InvalidGrantError("Redirect URI mismatch")

        # Verify PKCE for public clients or if code_challenge was provided
        if auth_code.code_challenge:
            if not code_verifier:
                raise InvalidGrantError("PKCE code_verifier required")

            if not self._verify_pkce(auth_code.code_challenge, code_verifier):
                raise InvalidGrantError("PKCE verification failed")

        # Mark code as used
        auth_code.is_used = True
        await db.commit()

        # Get user with roles for token generation
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
            )
            .where(User.id == auth_code.user_id)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise InvalidGrantError("User not found")

        # Parse scopes
        scopes = auth_code.scope.split() if auth_code.scope else []

        # Generate tokens
        access_token = self._generate_access_token(
            user=user,
            scopes=scopes,
            patient_id=auth_code.patient_id,
            encounter_id=auth_code.encounter_id,
            client_id=client_id,
        )

        refresh_token = None
        if "refresh_token" in app.grant_types:
            refresh_token = self._generate_refresh_token(
                user_id=user.id,
                client_id=client_id,
                scope=auth_code.scope,
            )

        # Build FHIR User reference
        fhir_user = None
        if "fhirUser" in scopes or "openid" in scopes:
            fhir_user = f"Practitioner/{user.id}"

        logger.info(
            f"Token exchange successful for client={client_id}, "
            f"patient={auth_code.patient_id}"
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=self.access_token_expire_minutes * 60,
            refresh_token=refresh_token,
            scope=auth_code.scope,
            patient=auth_code.patient_id,
            encounter=auth_code.encounter_id,
            fhir_user=fhir_user,
        )

    # -------------------------------------------------------------------------
    # Token Generation
    # -------------------------------------------------------------------------

    def _generate_access_token(
        self,
        user: User,
        scopes: list[str],
        patient_id: str | None = None,
        encounter_id: str | None = None,
        client_id: str | None = None,
    ) -> str:
        """Generate a SMART-compliant JWT access token.

        The token includes standard JWT claims plus SMART-specific claims
        for scope, patient context, and FHIR user reference.

        Args:
            user: The authenticated user
            scopes: Granted SMART scopes
            patient_id: Patient context (if applicable)
            encounter_id: Encounter context (if applicable)
            client_id: OAuth2 client identifier

        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.access_token_expire_minutes)

        # Get user roles
        roles = [ur.role.name for ur in user.user_roles]

        payload: dict[str, Any] = {
            # Standard JWT claims
            "iss": "clinical-ontology-normalizer",
            "sub": user.id,
            "aud": "smart-fhir-api",
            "exp": expires,
            "iat": now,
            "jti": secrets.token_urlsafe(16),

            # User claims
            "email": user.email,
            "name": user.name,
            "roles": roles,

            # SMART claims
            "scope": " ".join(scopes),
            "client_id": client_id,
        }

        # Add context claims if present
        if patient_id:
            payload["patient"] = patient_id

        if encounter_id:
            payload["encounter"] = encounter_id

        # Add fhirUser claim
        if "fhirUser" in scopes or "openid" in scopes:
            payload["fhirUser"] = f"Practitioner/{user.id}"

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def _generate_refresh_token(
        self,
        user_id: str,
        client_id: str,
        scope: str,
    ) -> str:
        """Generate a refresh token.

        Args:
            user_id: User ID
            client_id: OAuth2 client identifier
            scope: Granted scopes

        Returns:
            Encoded JWT refresh token
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "iss": "clinical-ontology-normalizer",
            "sub": user_id,
            "exp": expires,
            "iat": now,
            "jti": secrets.token_urlsafe(16),
            "type": "refresh",
            "client_id": client_id,
            "scope": scope,
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def generate_smart_access_token(
        self,
        user: User,
        scopes: list[str],
        patient_id: str | None = None,
        encounter_id: str | None = None,
        client_id: str | None = None,
    ) -> str:
        """Public method to generate a SMART access token.

        Args:
            user: The authenticated user
            scopes: Granted SMART scopes
            patient_id: Patient context
            encounter_id: Encounter context
            client_id: OAuth2 client identifier

        Returns:
            Encoded JWT access token
        """
        return self._generate_access_token(
            user=user,
            scopes=scopes,
            patient_id=patient_id,
            encounter_id=encounter_id,
            client_id=client_id,
        )

    # -------------------------------------------------------------------------
    # Client Credentials Grant
    # -------------------------------------------------------------------------

    async def client_credentials_token(
        self,
        db: AsyncSession,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
    ) -> TokenResponse:
        """Issue tokens using client credentials grant.

        This grant type is for backend services that access FHIR resources
        without user context. The client must be confidential and have
        "client_credentials" in its allowed grant types.

        Args:
            db: Database session
            client_id: OAuth2 client identifier
            client_secret: Client secret
            scope: Requested scopes (space-separated)

        Returns:
            TokenResponse with access token (no refresh token)

        Raises:
            InvalidClientError: If client validation fails
            InvalidScopeError: If requested scopes are not allowed
        """
        # Validate client credentials
        client_validation = await self.validate_client(db, client_id, client_secret)
        if not client_validation.valid:
            raise InvalidClientError(client_validation.error or "Invalid client")

        app = client_validation.app
        if not app:
            raise InvalidClientError("Application not found")

        # Check grant type is allowed
        if "client_credentials" not in app.grant_types:
            raise InvalidClientError("client_credentials grant not allowed")

        # Validate scopes
        requested_scopes = scope.split() if scope else []
        if not requested_scopes:
            requested_scopes = app.scopes  # Use all registered scopes

        scope_validation = self.validate_scopes(requested_scopes, app.scopes)
        if not scope_validation.valid:
            raise InvalidScopeError(
                f"No valid scopes granted. Rejected: {scope_validation.rejected_scopes}"
            )

        # Generate access token (no user context)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "iss": "clinical-ontology-normalizer",
            "sub": client_id,  # Client is the subject for client_credentials
            "aud": "smart-fhir-api",
            "exp": expires,
            "iat": now,
            "jti": secrets.token_urlsafe(16),
            "scope": " ".join(scope_validation.granted_scopes),
            "client_id": client_id,
            "grant_type": "client_credentials",
        }

        access_token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        logger.info(f"Client credentials token issued for: {client_id}")

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=self.access_token_expire_minutes * 60,
            scope=" ".join(scope_validation.granted_scopes),
        )

    # -------------------------------------------------------------------------
    # Token Introspection
    # -------------------------------------------------------------------------

    def decode_token(self, token: str) -> dict[str, Any] | None:
        """Decode and validate a JWT token.

        Args:
            token: JWT token to decode

        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience="smart-fhir-api",
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token: {e}")
            return None

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service stats
        """
        return {
            "pending_launch_contexts": len(self._launch_contexts),
            "access_token_expire_minutes": self.access_token_expire_minutes,
            "refresh_token_expire_days": self.refresh_token_expire_days,
            "auth_code_expire_minutes": self.auth_code_expire_minutes,
        }


# Singleton instance
_smart_auth_server: SMARTAuthServer | None = None
_smart_auth_lock = threading.Lock()


def get_smart_auth_server() -> SMARTAuthServer:
    """Get the singleton SMARTAuthServer instance.

    Returns:
        SMARTAuthServer instance
    """
    global _smart_auth_server
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _smart_auth_server is None:
        with _smart_auth_lock:
            if _smart_auth_server is None:
                _smart_auth_server = SMARTAuthServer()
    return _smart_auth_server


def reset_smart_auth_server() -> None:
    """Reset the singleton for testing."""
    global _smart_auth_server
    with _smart_auth_lock:
        _smart_auth_server = None
