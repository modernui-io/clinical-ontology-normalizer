"""FHIR R4 Source Connector.

This module provides a connector for extracting clinical data from
FHIR R4 servers using the HL7 FHIR REST API.

Supported FHIR Resources:
    - Patient → SourcePatient
    - Encounter → SourceVisit
    - Condition → SourceCondition
    - MedicationRequest/MedicationStatement → SourceDrug
    - Procedure → SourceProcedure
    - Observation → SourceMeasurement/SourceObservation
    - AllergyIntolerance → SourceObservation

Features:
    - OAuth2/Bearer token authentication
    - Pagination support (_count, _getpages)
    - Search parameters for filtering
    - Batch resource retrieval
    - Reference resolution

Usage:
    config = FHIRConnectorConfig(
        base_url="https://fhir.example.com/r4",
        auth_token="Bearer xyz...",
    )
    connector = FHIRConnector(config)

    async for patient in connector.extract_patients():
        print(patient.source_id, patient.given_name, patient.family_name)
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    get_circuit_breaker_registry,
)

from app.connectors.base import (
    ConditionStatus,
    ConnectorConfig,
    ConnectorType,
    DrugStatus,
    ExtractionResult,
    Gender,
    ProcedureStatus,
    SourceCondition,
    SourceConnector,
    SourceDrug,
    SourceMeasurement,
    SourceObservation,
    SourcePatient,
    SourceProcedure,
    SourceVisit,
    VisitType,
)
from app.connectors.concept_mappings import (
    FHIR_ENCOUNTER_CLASS_MAP,
    normalize_code_system,
)

logger = logging.getLogger(__name__)


@dataclass
class FHIRConnectorConfig(ConnectorConfig):
    """Configuration for FHIR R4 connector.

    Attributes:
        base_url: FHIR server base URL (e.g., https://server.com/fhir/r4).
        auth_token: Bearer token for authentication.
        client_id: OAuth2 client ID (for token refresh).
        client_secret: OAuth2 client secret.
        page_size: Number of resources per page (default: 100).
        timeout: Request timeout in seconds (default: 30).
        verify_ssl: Whether to verify SSL certificates (default: True).
        headers: Additional HTTP headers.
    """

    base_url: str = ""
    auth_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    page_size: int = 100
    timeout: int = 30
    verify_ssl: bool = True
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set connector type after initialization."""
        self.connector_type = ConnectorType.FHIR


class FHIRConnector(SourceConnector):
    """Source connector for FHIR R4 servers.

    Extracts clinical data from FHIR servers using the standard REST API.
    Supports pagination, authentication, and various search parameters.

    VP-Reliability-1: Uses circuit breaker pattern for external API calls.
    """

    def __init__(self, config: FHIRConnectorConfig):
        """Initialize FHIR connector.

        Args:
            config: Connector configuration.
        """
        super().__init__(config)
        self.config: FHIRConnectorConfig = config
        self._client: httpx.AsyncClient | None = None
        self._circuit_breaker: CircuitBreaker | None = None

    def _get_circuit_breaker(self) -> CircuitBreaker:
        """Get or create circuit breaker for this FHIR server.

        VP-Reliability-1: Circuit breaker prevents cascading failures.
        """
        if self._circuit_breaker is None:
            # Create unique circuit breaker per FHIR server URL
            server_id = self.config.base_url.replace("://", "_").replace("/", "_")[:50]
            registry = get_circuit_breaker_registry()
            self._circuit_breaker = registry.get_or_create(
                f"fhir:{server_id}",
                CircuitBreakerConfig(
                    failure_threshold=5,  # Trip after 5 consecutive failures
                    success_threshold=3,  # Close after 3 successes
                    recovery_timeout=45.0,  # Wait 45s before retrying
                    trip_exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError),
                )
            )
        return self._circuit_breaker

    def _get_headers(self) -> dict[str, str]:
        """Build HTTP headers for requests."""
        headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
            **self.config.headers,
        }
        if self.config.auth_token:
            # Support both "Bearer xxx" and just "xxx"
            token = self.config.auth_token
            if not token.lower().startswith("bearer "):
                token = f"Bearer {token}"
            headers["Authorization"] = token
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=self._get_headers(),
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
        return self._client

    async def connect(self) -> bool:
        """Connect to FHIR server.

        VP-Reliability-1: Protected by circuit breaker.

        Returns:
            True if connection successful.
        """
        if not self.config.base_url:
            return False

        circuit_breaker = self._get_circuit_breaker()

        try:
            # Use circuit breaker to protect external call
            async def _do_connect() -> bool:
                client = await self._get_client()
                response = await client.get("/metadata")
                response.raise_for_status()
                return response.status_code == 200

            return await circuit_breaker.call_async(_do_connect)
        except CircuitBreakerOpen as e:
            logger.warning(f"FHIR connection blocked by circuit breaker: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to FHIR server: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from FHIR server."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def test_connection(self) -> bool:
        """Test connection to FHIR server."""
        return await self.connect()

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        search_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single page of resources with circuit breaker protection.

        VP-Reliability-1: Each HTTP call is protected by circuit breaker.
        """
        circuit_breaker = self._get_circuit_breaker()

        async def _do_fetch() -> dict[str, Any]:
            response = await client.get(url, params=search_params)
            response.raise_for_status()
            return response.json()

        return await circuit_breaker.call_async(_do_fetch)

    async def _fetch_resources(
        self,
        resource_type: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Fetch resources from FHIR server with pagination.

        VP-Reliability-1: Protected by circuit breaker.

        Args:
            resource_type: FHIR resource type (Patient, Condition, etc.).
            params: Search parameters.

        Yields:
            Individual FHIR resources.
        """
        client = await self._get_client()

        search_params = {"_count": str(self.config.page_size)}
        if params:
            search_params.update(params)

        url = f"/{resource_type}"

        while url:
            try:
                bundle = await self._fetch_page(
                    client,
                    url,
                    search_params if "?" not in url else None,
                )

                # Yield entries from bundle
                if bundle.get("resourceType") == "Bundle":
                    for entry in bundle.get("entry", []):
                        resource = entry.get("resource")
                        if resource:
                            yield resource

                # Get next page URL
                url = None
                for link in bundle.get("link", []):
                    if link.get("relation") == "next":
                        url = link.get("url")
                        search_params = {}  # Params are in the URL
                        break

            except CircuitBreakerOpen as e:
                # VP-Reliability-1: Circuit breaker is open, stop fetching
                logger.warning(
                    f"Circuit breaker open for {resource_type}, stopping pagination: {e}"
                )
                break
            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching {resource_type}: {e}")
                break
            except Exception as e:
                logger.error(f"Error fetching {resource_type}: {e}")
                break

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse FHIR datetime string."""
        if not value:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%Y-%m",
            "%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value[:len(fmt.replace("%", "").replace("f", "000000"))], fmt)
            except (ValueError, IndexError):
                continue

        return None

    def _extract_reference_id(self, reference: str | None) -> str | None:
        """Extract ID from FHIR reference (e.g., 'Patient/123' → '123')."""
        if not reference:
            return None
        if "/" in reference:
            return reference.split("/")[-1]
        return reference

    def _parse_gender(self, fhir_gender: str | None) -> Gender:
        """Map FHIR gender to Gender enum."""
        if not fhir_gender:
            return Gender.UNKNOWN

        mapping = {
            "male": Gender.MALE,
            "female": Gender.FEMALE,
            "other": Gender.OTHER,
            "unknown": Gender.UNKNOWN,
        }
        return mapping.get(fhir_gender.lower(), Gender.UNKNOWN)

    def _extract_coding(
        self,
        codeable_concept: dict[str, Any] | None,
    ) -> tuple[str | None, str | None, str | None]:
        """Extract code, system, and display from CodeableConcept.

        Returns:
            Tuple of (code, system, display).
        """
        if not codeable_concept:
            return None, None, None

        # Get first coding
        codings = codeable_concept.get("coding", [])
        if codings:
            coding = codings[0]
            return (
                coding.get("code"),
                coding.get("system"),
                coding.get("display") or codeable_concept.get("text"),
            )

        return None, None, codeable_concept.get("text")

    def _normalize_code_system(self, fhir_system: str | None) -> str | None:
        """Normalize FHIR code system URL to vocabulary name."""
        return normalize_code_system(fhir_system)

    async def extract_patients(self) -> AsyncIterator[SourcePatient]:
        """Extract patients from FHIR server.

        Yields:
            SourcePatient objects.
        """
        async for resource in self._fetch_resources("Patient"):
            try:
                # Parse name
                given_name = None
                family_name = None
                names = resource.get("name", [])
                if names:
                    name = names[0]
                    given_parts = name.get("given", [])
                    given_name = " ".join(given_parts) if given_parts else None
                    family_name = name.get("family")

                # Parse address
                address = resource.get("address", [{}])[0] if resource.get("address") else {}
                address_lines = address.get("line", [])

                # Parse identifiers
                mrn = None
                for identifier in resource.get("identifier", []):
                    if identifier.get("type", {}).get("coding", [{}])[0].get("code") == "MR":
                        mrn = identifier.get("value")
                        break

                yield SourcePatient(
                    source_id=resource.get("id", ""),
                    mrn=mrn,
                    given_name=given_name,
                    family_name=family_name,
                    birth_date=self._parse_datetime(resource.get("birthDate")),
                    gender=self._parse_gender(resource.get("gender")),
                    race=None,  # FHIR US Core extension would be needed
                    ethnicity=None,
                    address_line1=address_lines[0] if address_lines else None,
                    address_line2=address_lines[1] if len(address_lines) > 1 else None,
                    city=address.get("city"),
                    state=address.get("state"),
                    postal_code=address.get("postalCode"),
                    country=address.get("country"),
                    raw_data=resource,
                )
            except Exception as e:
                logger.warning(f"Error parsing Patient {resource.get('id')}: {e}")

    async def extract_visits(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceVisit]:
        """Extract encounters/visits from FHIR server.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceVisit objects.
        """
        params = {}
        if patient_source_id:
            params["patient"] = patient_source_id

        async for resource in self._fetch_resources("Encounter", params):
            try:
                # Parse period
                period = resource.get("period", {})
                start_date = self._parse_datetime(period.get("start"))
                end_date = self._parse_datetime(period.get("end"))

                # Parse class (visit type)
                encounter_class = resource.get("class", {})
                class_code = encounter_class.get("code", "")

                visit_type = FHIR_ENCOUNTER_CLASS_MAP.get(
                    class_code.upper(), VisitType.OUTPATIENT
                )

                # Get patient reference
                subject = resource.get("subject", {})
                patient_id = self._extract_reference_id(subject.get("reference"))

                yield SourceVisit(
                    source_id=resource.get("id", ""),
                    patient_source_id=patient_id or patient_source_id or "",
                    visit_type=visit_type,
                    start_date=start_date,
                    end_date=end_date,
                    visit_source_value=class_code or encounter_class.get("display"),
                    raw_data=resource,
                )
            except Exception as e:
                logger.warning(f"Error parsing Encounter {resource.get('id')}: {e}")

    async def extract_conditions(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceCondition]:
        """Extract conditions from FHIR server.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceCondition objects.
        """
        params = {}
        if patient_source_id:
            params["patient"] = patient_source_id

        async for resource in self._fetch_resources("Condition", params):
            try:
                # Parse code
                code, system, display = self._extract_coding(resource.get("code"))

                # Parse dates
                onset_date = self._parse_datetime(
                    resource.get("onsetDateTime") or
                    resource.get("onsetPeriod", {}).get("start")
                )
                abatement_date = self._parse_datetime(
                    resource.get("abatementDateTime") or
                    resource.get("abatementPeriod", {}).get("end")
                )

                # Parse clinical status
                clinical_status = resource.get("clinicalStatus", {})
                status_code = (clinical_status.get("coding", [{}])[0].get("code") or "").lower()

                status = ConditionStatus.ACTIVE
                status_map = {
                    "active": ConditionStatus.ACTIVE,
                    "inactive": ConditionStatus.INACTIVE,
                    "resolved": ConditionStatus.RESOLVED,
                    "remission": ConditionStatus.RESOLVED,
                }
                status = status_map.get(status_code, ConditionStatus.UNKNOWN)

                # Get patient reference
                subject = resource.get("subject", {})
                patient_id = self._extract_reference_id(subject.get("reference"))

                yield SourceCondition(
                    source_id=resource.get("id", ""),
                    patient_source_id=patient_id or patient_source_id or "",
                    condition_code=code,
                    condition_code_system=self._normalize_code_system(system),
                    condition_name=display,
                    onset_date=onset_date,
                    resolution_date=abatement_date,
                    status=status,
                    raw_data=resource,
                )
            except Exception as e:
                logger.warning(f"Error parsing Condition {resource.get('id')}: {e}")

    async def extract_drugs(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceDrug]:
        """Extract medications from FHIR server.

        Queries both MedicationRequest and MedicationStatement.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceDrug objects.
        """
        params = {}
        if patient_source_id:
            params["patient"] = patient_source_id

        # MedicationRequest (prescriptions)
        async for resource in self._fetch_resources("MedicationRequest", params):
            try:
                drug = self._parse_medication_resource(resource, patient_source_id)
                if drug:
                    yield drug
            except Exception as e:
                logger.warning(f"Error parsing MedicationRequest {resource.get('id')}: {e}")

        # MedicationStatement (administrations)
        async for resource in self._fetch_resources("MedicationStatement", params):
            try:
                drug = self._parse_medication_resource(resource, patient_source_id)
                if drug:
                    yield drug
            except Exception as e:
                logger.warning(f"Error parsing MedicationStatement {resource.get('id')}: {e}")

    def _parse_medication_resource(
        self,
        resource: dict[str, Any],
        patient_source_id: str | None,
    ) -> SourceDrug | None:
        """Parse MedicationRequest or MedicationStatement."""
        # Parse medication code
        med_codeable = resource.get("medicationCodeableConcept")
        if not med_codeable:
            # Could be a reference to Medication resource
            med_ref = resource.get("medicationReference", {})
            if med_ref.get("display"):
                med_codeable = {"text": med_ref.get("display")}

        code, system, display = self._extract_coding(med_codeable)

        # Parse dates
        authored_on = resource.get("authoredOn")
        effective = resource.get("effectivePeriod", {}) or resource.get("effectiveDateTime")

        start_date = None
        end_date = None

        if isinstance(effective, dict):
            start_date = self._parse_datetime(effective.get("start"))
            end_date = self._parse_datetime(effective.get("end"))
        elif effective:
            start_date = self._parse_datetime(effective)

        if not start_date and authored_on:
            start_date = self._parse_datetime(authored_on)

        # Parse status
        status_code = resource.get("status", "").lower()
        status = DrugStatus.ACTIVE
        status_map = {
            "active": DrugStatus.ACTIVE,
            "completed": DrugStatus.COMPLETED,
            "stopped": DrugStatus.STOPPED,
            "cancelled": DrugStatus.STOPPED,
            "entered-in-error": DrugStatus.STOPPED,
        }
        status = status_map.get(status_code, DrugStatus.UNKNOWN)

        # Parse dosage
        dose_value = None
        dose_unit = None
        route = None
        sig = None

        dosage_list = resource.get("dosageInstruction", []) or resource.get("dosage", [])
        if dosage_list:
            dosage = dosage_list[0]
            sig = dosage.get("text")

            dose_qty = dosage.get("doseAndRate", [{}])[0].get("doseQuantity", {})
            dose_value = str(dose_qty.get("value")) if dose_qty.get("value") else None
            dose_unit = dose_qty.get("unit")

            route_concept = dosage.get("route")
            if route_concept:
                _, _, route = self._extract_coding(route_concept)

        # Get patient reference
        subject = resource.get("subject", {})
        patient_id = self._extract_reference_id(subject.get("reference"))

        return SourceDrug(
            source_id=resource.get("id", ""),
            patient_source_id=patient_id or patient_source_id or "",
            drug_code=code,
            drug_code_system=self._normalize_code_system(system),
            drug_name=display,
            start_date=start_date,
            end_date=end_date,
            status=status,
            dose_value=dose_value,
            dose_unit=dose_unit,
            route=route,
            sig=sig,
            raw_data=resource,
        )

    async def extract_procedures(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceProcedure]:
        """Extract procedures from FHIR server.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceProcedure objects.
        """
        params = {}
        if patient_source_id:
            params["patient"] = patient_source_id

        async for resource in self._fetch_resources("Procedure", params):
            try:
                # Parse code
                code, system, display = self._extract_coding(resource.get("code"))

                # Parse date
                performed = resource.get("performedDateTime") or resource.get("performedPeriod", {})
                procedure_date = None
                end_date = None

                if isinstance(performed, dict):
                    procedure_date = self._parse_datetime(performed.get("start"))
                    end_date = self._parse_datetime(performed.get("end"))
                else:
                    procedure_date = self._parse_datetime(performed)

                # Parse status
                status_code = resource.get("status", "").lower()
                status = ProcedureStatus.COMPLETED
                status_map = {
                    "completed": ProcedureStatus.COMPLETED,
                    "in-progress": ProcedureStatus.IN_PROGRESS,
                    "not-done": ProcedureStatus.NOT_DONE,
                    "entered-in-error": ProcedureStatus.NOT_DONE,
                }
                status = status_map.get(status_code, ProcedureStatus.UNKNOWN)

                # Get patient reference
                subject = resource.get("subject", {})
                patient_id = self._extract_reference_id(subject.get("reference"))

                yield SourceProcedure(
                    source_id=resource.get("id", ""),
                    patient_source_id=patient_id or patient_source_id or "",
                    procedure_code=code,
                    procedure_code_system=self._normalize_code_system(system),
                    procedure_name=display,
                    procedure_date=procedure_date,
                    end_date=end_date,
                    status=status,
                    raw_data=resource,
                )
            except Exception as e:
                logger.warning(f"Error parsing Procedure {resource.get('id')}: {e}")

    async def extract_measurements(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceMeasurement]:
        """Extract measurements (labs, vitals) from FHIR server.

        Filters Observation resources by category.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceMeasurement objects.
        """
        params = {"category": "vital-signs,laboratory"}
        if patient_source_id:
            params["patient"] = patient_source_id

        async for resource in self._fetch_resources("Observation", params):
            try:
                # Skip non-measurement observations
                categories = resource.get("category", [])
                is_measurement = False
                for cat in categories:
                    cat_codes = [c.get("code") for c in cat.get("coding", [])]
                    if any(c in ["vital-signs", "laboratory"] for c in cat_codes):
                        is_measurement = True
                        break

                if not is_measurement:
                    continue

                # Parse code
                code, system, display = self._extract_coding(resource.get("code"))

                # Parse value
                value_numeric = None
                value_text = None
                unit = None

                value_qty = resource.get("valueQuantity", {})
                if value_qty:
                    value_numeric = value_qty.get("value")
                    unit = value_qty.get("unit")
                elif resource.get("valueString"):
                    value_text = resource.get("valueString")
                elif resource.get("valueCodeableConcept"):
                    _, _, value_text = self._extract_coding(resource.get("valueCodeableConcept"))

                # Parse date
                measurement_date = self._parse_datetime(
                    resource.get("effectiveDateTime") or
                    resource.get("effectivePeriod", {}).get("start")
                )

                # Parse reference range
                range_low = None
                range_high = None
                ref_ranges = resource.get("referenceRange", [])
                if ref_ranges:
                    ref_range = ref_ranges[0]
                    if ref_range.get("low"):
                        range_low = ref_range["low"].get("value")
                    if ref_range.get("high"):
                        range_high = ref_range["high"].get("value")

                # Parse interpretation
                abnormal_flag = None
                interpretation = resource.get("interpretation", [])
                if interpretation:
                    _, _, abnormal_flag = self._extract_coding(interpretation[0])

                # Get patient reference
                subject = resource.get("subject", {})
                patient_id = self._extract_reference_id(subject.get("reference"))

                yield SourceMeasurement(
                    source_id=resource.get("id", ""),
                    patient_source_id=patient_id or patient_source_id or "",
                    measurement_code=code,
                    measurement_code_system=self._normalize_code_system(system),
                    measurement_name=display,
                    value_numeric=value_numeric,
                    value_text=value_text,
                    unit=unit,
                    range_low=range_low,
                    range_high=range_high,
                    measurement_date=measurement_date,
                    abnormal_flag=abnormal_flag,
                    raw_data=resource,
                )
            except Exception as e:
                logger.warning(f"Error parsing Observation {resource.get('id')}: {e}")

    async def extract_observations(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceObservation]:
        """Extract observations (allergies, social history) from FHIR server.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceObservation objects.
        """
        # AllergyIntolerance
        params = {}
        if patient_source_id:
            params["patient"] = patient_source_id

        async for resource in self._fetch_resources("AllergyIntolerance", params):
            try:
                # Parse allergen code
                code, system, display = self._extract_coding(resource.get("code"))

                # Parse reaction
                reactions = resource.get("reaction", [])
                reaction_text = None
                if reactions:
                    manifestations = reactions[0].get("manifestation", [])
                    if manifestations:
                        _, _, reaction_text = self._extract_coding(manifestations[0])

                # Parse date
                onset_date = self._parse_datetime(resource.get("onsetDateTime"))

                # Get patient reference
                patient = resource.get("patient", {})
                patient_id = self._extract_reference_id(patient.get("reference"))

                yield SourceObservation(
                    source_id=resource.get("id", ""),
                    patient_source_id=patient_id or patient_source_id or "",
                    observation_code=code,
                    observation_code_system=self._normalize_code_system(system),
                    observation_name=display,
                    observation_type="allergy",
                    observation_date=onset_date,
                    value_text=reaction_text,
                    raw_data=resource,
                )
            except Exception as e:
                logger.warning(f"Error parsing AllergyIntolerance {resource.get('id')}: {e}")

        # Social history observations
        params = {"category": "social-history"}
        if patient_source_id:
            params["patient"] = patient_source_id

        async for resource in self._fetch_resources("Observation", params):
            try:
                # Parse code
                code, system, display = self._extract_coding(resource.get("code"))

                # Parse value
                value_text = None
                if resource.get("valueCodeableConcept"):
                    _, _, value_text = self._extract_coding(resource.get("valueCodeableConcept"))
                elif resource.get("valueString"):
                    value_text = resource.get("valueString")

                # Parse date
                obs_date = self._parse_datetime(resource.get("effectiveDateTime"))

                # Get patient reference
                subject = resource.get("subject", {})
                patient_id = self._extract_reference_id(subject.get("reference"))

                yield SourceObservation(
                    source_id=resource.get("id", ""),
                    patient_source_id=patient_id or patient_source_id or "",
                    observation_code=code,
                    observation_code_system=self._normalize_code_system(system),
                    observation_name=display,
                    observation_type="social_history",
                    observation_date=obs_date,
                    value_text=value_text,
                    raw_data=resource,
                )
            except Exception as e:
                logger.warning(f"Error parsing social history Observation {resource.get('id')}: {e}")

    async def get_extraction_stats(self) -> ExtractionResult:
        """Get extraction statistics.

        Returns:
            ExtractionResult with counts.
        """
        result = ExtractionResult()

        # Count resources
        async for _ in self.extract_patients():
            result.patients_extracted += 1

        async for _ in self.extract_visits():
            result.visits_extracted += 1

        async for _ in self.extract_conditions():
            result.conditions_extracted += 1

        async for _ in self.extract_drugs():
            result.drugs_extracted += 1

        async for _ in self.extract_procedures():
            result.procedures_extracted += 1

        async for _ in self.extract_measurements():
            result.measurements_extracted += 1

        async for _ in self.extract_observations():
            result.observations_extracted += 1

        return result
