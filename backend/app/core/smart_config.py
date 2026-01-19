"""SMART on FHIR application configuration.

Provides configuration for SMART on FHIR OAuth2 authorization flow,
supporting EHR launch context for Epic, Cerner, and other compliant systems.
"""

import logging
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class SMARTScope(str, Enum):
    """Standard SMART on FHIR scopes."""

    # Patient-level scopes (SMART v1)
    PATIENT_READ = "patient/*.read"
    PATIENT_WRITE = "patient/*.write"
    PATIENT_ALL = "patient/*.*"

    # Resource-specific patient scopes
    PATIENT_CONDITION_READ = "patient/Condition.read"
    PATIENT_MEDICATION_READ = "patient/MedicationRequest.read"
    PATIENT_OBSERVATION_READ = "patient/Observation.read"
    PATIENT_ALLERGY_READ = "patient/AllergyIntolerance.read"
    PATIENT_PROCEDURE_READ = "patient/Procedure.read"
    PATIENT_ENCOUNTER_READ = "patient/Encounter.read"
    PATIENT_IMMUNIZATION_READ = "patient/Immunization.read"
    PATIENT_DIAGNOSTICREPORT_READ = "patient/DiagnosticReport.read"
    PATIENT_DOCUMENTREFERENCE_READ = "patient/DocumentReference.read"

    # User-level scopes (for provider access)
    USER_READ = "user/*.read"
    USER_WRITE = "user/*.write"
    USER_ALL = "user/*.*"

    # Launch context scopes
    LAUNCH_PATIENT = "launch/patient"
    LAUNCH_ENCOUNTER = "launch/encounter"
    LAUNCH = "launch"

    # OpenID Connect scopes
    OPENID = "openid"
    FHIR_USER = "fhirUser"
    PROFILE = "profile"
    OFFLINE_ACCESS = "offline_access"


class EHRVendor(str, Enum):
    """Supported EHR vendors with SMART on FHIR."""

    EPIC = "epic"
    CERNER = "cerner"
    ALLSCRIPTS = "allscripts"
    ATHENAHEALTH = "athenahealth"
    MEDITECH = "meditech"
    GENERIC = "generic"


class WellKnownConfig(BaseModel):
    """SMART configuration from .well-known/smart-configuration endpoint."""

    issuer: str | None = None
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None = None
    management_endpoint: str | None = None
    introspection_endpoint: str | None = None
    revocation_endpoint: str | None = None
    jwks_uri: str | None = None
    scopes_supported: list[str] = Field(default_factory=list)
    response_types_supported: list[str] = Field(default_factory=list)
    grant_types_supported: list[str] = Field(default_factory=list)
    code_challenge_methods_supported: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class SMARTSettings(BaseSettings):
    """SMART on FHIR application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="SMART_",
        extra="ignore",  # Ignore extra env vars from the .env file
    )

    # Application registration settings
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8000/smart/callback"

    # FHIR server settings
    fhir_base_url: str = "http://localhost:8090/fhir"
    ehr_vendor: EHRVendor = EHRVendor.GENERIC

    # OAuth settings
    state_ttl_seconds: int = 600  # 10 minutes
    token_refresh_threshold_seconds: int = 300  # Refresh 5 min before expiry

    # Default scopes to request
    default_scopes: list[str] = Field(
        default_factory=lambda: [
            SMARTScope.LAUNCH_PATIENT.value,
            SMARTScope.LAUNCH_ENCOUNTER.value,
            SMARTScope.PATIENT_READ.value,
            SMARTScope.OPENID.value,
            SMARTScope.FHIR_USER.value,
            SMARTScope.PROFILE.value,
            SMARTScope.OFFLINE_ACCESS.value,
        ]
    )

    # Security settings
    pkce_enabled: bool = True  # Use PKCE for enhanced security


# Vendor-specific endpoint configurations
VENDOR_ENDPOINTS: dict[EHRVendor, dict[str, str]] = {
    EHRVendor.EPIC: {
        "well_known_suffix": "/.well-known/smart-configuration",
        "authorize_path": "/oauth2/authorize",
        "token_path": "/oauth2/token",
    },
    EHRVendor.CERNER: {
        "well_known_suffix": "/.well-known/smart-configuration",
        "authorize_path": "/oauth2/authorize",
        "token_path": "/oauth2/token",
    },
    EHRVendor.GENERIC: {
        "well_known_suffix": "/.well-known/smart-configuration",
        "authorize_path": "/oauth2/authorize",
        "token_path": "/oauth2/token",
    },
}


async def discover_smart_configuration(
    fhir_base_url: str,
    vendor: EHRVendor = EHRVendor.GENERIC,
) -> WellKnownConfig | None:
    """Discover SMART configuration from the well-known endpoint.

    Args:
        fhir_base_url: Base URL of the FHIR server
        vendor: EHR vendor for vendor-specific handling

    Returns:
        WellKnownConfig if discovery succeeds, None otherwise
    """
    well_known_url = f"{fhir_base_url.rstrip('/')}/.well-known/smart-configuration"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(well_known_url)

            if response.status_code == 200:
                data = response.json()
                return WellKnownConfig(
                    issuer=data.get("issuer"),
                    authorization_endpoint=data.get("authorization_endpoint", ""),
                    token_endpoint=data.get("token_endpoint", ""),
                    registration_endpoint=data.get("registration_endpoint"),
                    management_endpoint=data.get("management_endpoint"),
                    introspection_endpoint=data.get("introspection_endpoint"),
                    revocation_endpoint=data.get("revocation_endpoint"),
                    jwks_uri=data.get("jwks_uri"),
                    scopes_supported=data.get("scopes_supported", []),
                    response_types_supported=data.get("response_types_supported", []),
                    grant_types_supported=data.get("grant_types_supported", []),
                    code_challenge_methods_supported=data.get(
                        "code_challenge_methods_supported", []
                    ),
                    capabilities=data.get("capabilities", []),
                )

            logger.warning(
                f"SMART discovery failed with status {response.status_code}: {well_known_url}"
            )
            return None

    except Exception as e:
        logger.error(f"SMART discovery error: {e}")
        return None


def build_authorization_url(
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    aud: str,
    launch: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str = "S256",
) -> str:
    """Build the OAuth2 authorization URL for SMART launch.

    Args:
        authorization_endpoint: OAuth2 authorization endpoint
        client_id: Registered SMART app client ID
        redirect_uri: Callback URL for the app
        scope: Space-separated list of scopes
        state: CSRF protection state parameter
        aud: FHIR server base URL (audience)
        launch: Launch context token (for EHR launch)
        code_challenge: PKCE code challenge
        code_challenge_method: PKCE method (S256)

    Returns:
        Complete authorization URL
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "aud": aud,
    }

    if launch:
        params["launch"] = launch

    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = code_challenge_method

    query_string = "&".join(f"{k}={httpx.QueryParams({k: v})}" for k, v in params.items())
    # Use proper URL encoding
    encoded_params = httpx.QueryParams(params)
    return f"{authorization_endpoint}?{encoded_params}"


def get_recommended_scopes(
    vendor: EHRVendor = EHRVendor.GENERIC,
    include_write: bool = False,
) -> list[str]:
    """Get recommended scopes for a given EHR vendor.

    Args:
        vendor: EHR vendor
        include_write: Whether to include write scopes

    Returns:
        List of recommended scope strings
    """
    base_scopes = [
        SMARTScope.OPENID.value,
        SMARTScope.FHIR_USER.value,
        SMARTScope.PROFILE.value,
        SMARTScope.LAUNCH_PATIENT.value,
        SMARTScope.PATIENT_READ.value,
    ]

    if include_write:
        base_scopes.append(SMARTScope.PATIENT_WRITE.value)

    # Vendor-specific adjustments
    if vendor == EHRVendor.EPIC:
        # Epic prefers granular scopes
        base_scopes = [
            SMARTScope.OPENID.value,
            SMARTScope.FHIR_USER.value,
            SMARTScope.LAUNCH_PATIENT.value,
            SMARTScope.PATIENT_CONDITION_READ.value,
            SMARTScope.PATIENT_MEDICATION_READ.value,
            SMARTScope.PATIENT_OBSERVATION_READ.value,
            SMARTScope.PATIENT_ALLERGY_READ.value,
            SMARTScope.PATIENT_PROCEDURE_READ.value,
        ]

    return base_scopes


# Singleton settings instance
smart_settings = SMARTSettings()
