"""SQLAlchemy models for SMART on FHIR app registration and authorization.

This module implements the SMART on FHIR authorization framework with:
- SMARTApp: Registered SMART applications with OAuth2 client credentials
- SMARTAuthorizationCode: OAuth2 authorization codes for the authorization code flow

The implementation supports:
- Confidential and public clients
- PKCE (Proof Key for Code Exchange) for enhanced security
- EHR launch context (patient and encounter selection)
- Scoped access based on SMART on FHIR scopes
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.rbac import User


class SMARTApp(Base):
    """Registered SMART on FHIR application.

    Represents a third-party application registered to access the FHIR API
    using the SMART on FHIR authorization framework. Supports both
    confidential clients (with client_secret) and public clients (PKCE only).

    OAuth2 Grant Types:
    - authorization_code: Standard OAuth2 authorization code flow
    - client_credentials: Backend service authorization (no user context)
    - refresh_token: Token refresh capability

    SMART Scopes follow the pattern:
    - patient/*.read - Read all patient data
    - patient/Observation.read - Read patient observations
    - launch - EHR launch context
    - launch/patient - Patient launch context
    - openid, profile, fhirUser - Identity scopes
    """

    __tablename__ = "smart_apps"

    client_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="OAuth2 client identifier (unique per app)",
    )
    client_secret_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Bcrypt hashed client secret (null for public clients)",
    )
    app_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable application name",
    )
    redirect_uris: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of allowed OAuth2 redirect URIs",
    )
    scopes: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of allowed SMART on FHIR scopes",
    )
    grant_types: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["authorization_code"],
        comment="Allowed OAuth2 grant types",
    )
    launch_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="EHR launch URL for embedded launch",
    )
    is_confidential: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is a confidential client (has client_secret)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether the app is currently active and can authorize",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp of last update",
    )

    # Relationships
    authorization_codes: Mapped[list["SMARTAuthorizationCode"]] = relationship(
        back_populates="smart_app",
        cascade="all, delete-orphan",
        foreign_keys="[SMARTAuthorizationCode.client_id]",
        primaryjoin="SMARTApp.client_id == foreign(SMARTAuthorizationCode.client_id)",
    )

    def __repr__(self) -> str:
        return f"<SMARTApp(id={self.id}, client_id={self.client_id}, app_name={self.app_name}, is_active={self.is_active})>"


class SMARTAuthorizationCode(Base):
    """OAuth2 authorization code for SMART on FHIR authorization.

    Represents a short-lived authorization code issued during the
    OAuth2 authorization code flow. The code is exchanged for
    access and refresh tokens.

    Supports PKCE (RFC 7636) for enhanced security with public clients:
    - code_challenge: Base64-URL encoded SHA-256 hash of code_verifier
    - code_challenge_method: Must be "S256" for SHA-256

    EHR Launch Context:
    - patient_id: Selected patient context (for patient-facing apps)
    - encounter_id: Selected encounter context (if applicable)
    """

    __tablename__ = "smart_authorization_codes"

    code: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="The authorization code (cryptographically random)",
    )
    client_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("smart_apps.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="OAuth2 client identifier",
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who authorized the request",
    )
    redirect_uri: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Redirect URI for this authorization",
    )
    scope: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Space-separated list of granted scopes",
    )
    code_challenge: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="PKCE code challenge (base64url-encoded SHA256 of verifier)",
    )
    code_challenge_method: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="PKCE challenge method (S256)",
    )
    patient_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="EHR launch context: selected patient ID",
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="EHR launch context: selected encounter ID",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When the authorization code expires",
    )
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether the code has been exchanged for tokens",
    )

    # Relationships
    smart_app: Mapped[SMARTApp] = relationship(
        back_populates="authorization_codes",
        foreign_keys=[client_id],
        primaryjoin="SMARTAuthorizationCode.client_id == SMARTApp.client_id",
    )
    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<SMARTAuthorizationCode(id={self.id}, client_id={self.client_id}, user_id={self.user_id}, is_used={self.is_used})>"
