"""Device Exposure Table ETL Service.

This module provides ETL functionality for transforming source device
data into the OMOP CDM Device_Exposure table.

The service handles:
    - FHIR DeviceRequest and DeviceUseStatement mapping
    - SNOMED device concept mapping
    - UDI (Unique Device Identifier) preservation
    - Device date normalization

FHIR R4 Resource Mapping:
    DeviceRequest -> Device_Exposure (ordered devices)
        - authoredOn -> device_exposure_start_date
        - occurrenceDateTime/Period -> timing
        - codeCodeableConcept -> device_concept_id

    DeviceUseStatement -> Device_Exposure (used devices)
        - timingPeriod -> start/end dates
        - device reference -> Device resource
        - bodySite -> implicit in device concept

    Device -> device_concept_id lookup
        - deviceName -> source value
        - udiCarrier -> unique_device_id
        - type -> device_concept_id

Standard OMOP Device Type Concept IDs:
    32817 - EHR encounter record
    32821 - EHR administration record
    32840 - Claim
    44818707 - Patient Self-Report
    44818705 - Patient-reported device

Usage:
    from app.etl import DeviceETL, DeviceETLConfig
    from app.connectors import SourceDevice, DeviceStatus

    etl = DeviceETL(db_session)

    device = SourceDevice(
        source_id="DEV001",
        patient_source_id="PAT001",
        device_code="704125003",
        device_code_system="SNOMED",
        device_name="Insulin pump",
        start_datetime=datetime(2024, 1, 15),
        unique_device_id="(01)00884521094142"
    )

    device_exp = await etl.transform_and_load(device, person_id=1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    DEFAULT_DEVICE_TYPE_CONCEPT_ID,
    DEVICE_TYPE_CONCEPT_MAP,
)
from app.models.omop import DeviceExposure

logger = logging.getLogger(__name__)


# Extended device type mapping for additional categories
DEVICE_TYPE_EXTENDED_MAP = {
    **DEVICE_TYPE_CONCEPT_MAP,
    "ehr_admin": 32821,     # EHR administration record
    "self_report": 44818707, # Patient self-report
    "patient_reported": 44818705,  # Patient-reported device
}


class DeviceStatus:
    """Status values for device records."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ENTERED_IN_ERROR = "entered-in-error"
    INTENDED = "intended"
    STOPPED = "stopped"
    ON_HOLD = "on-hold"
    UNKNOWN = "unknown"


# Device Status to OMOP handling
DEVICE_STATUS_MAP = {
    DeviceStatus.ACTIVE: True,        # Include in CDM
    DeviceStatus.COMPLETED: True,      # Include
    DeviceStatus.ENTERED_IN_ERROR: False,  # Exclude
    DeviceStatus.INTENDED: True,       # Include (ordered)
    DeviceStatus.STOPPED: True,        # Include
    DeviceStatus.ON_HOLD: True,        # Include
    DeviceStatus.UNKNOWN: True,        # Include
}


@dataclass
class SourceDevice:
    """Standardized device record from source systems.

    Maps to OMOP Device_Exposure table.
    Represents FHIR DeviceRequest, DeviceUseStatement, or Device resources.
    """

    source_id: str
    source_system: str = ""
    patient_source_id: str = ""
    visit_source_id: str | None = None

    # Device identification
    device_code: str | None = None
    device_code_system: str | None = None
    device_name: str | None = None
    unique_device_id: str | None = None  # UDI
    production_id: str | None = None     # Lot number or serial

    # Status
    status: str = DeviceStatus.UNKNOWN

    # Timing
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    authored_datetime: datetime | None = None

    # Quantity
    quantity: int = 1

    # Provider/performer
    provider_id: str | None = None
    provider_name: str | None = None

    # FHIR resource type for mapping context
    fhir_resource_type: str | None = None  # DeviceRequest, DeviceUseStatement, Device

    # Body site (from DeviceUseStatement)
    body_site_code: str | None = None
    body_site_text: str | None = None

    # Additional metadata
    raw_data: dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)


@dataclass
class DeviceETLConfig:
    """Configuration for Device ETL service."""

    map_to_standard: bool = True
    preserve_source_codes: bool = True
    default_device_type: int = DEFAULT_DEVICE_TYPE_CONCEPT_ID
    include_entered_in_error: bool = False
    batch_size: int = 1000


@dataclass
class DeviceETLResult:
    """Result of Device ETL operation."""

    total_processed: int = 0
    devices_created: int = 0
    devices_updated: int = 0
    devices_skipped: int = 0
    unmapped_codes: int = 0
    errors: list[str] = field(default_factory=list)


class DeviceETL:
    """ETL service for transforming SourceDevice to OMOP DeviceExposure.

    Handles FHIR DeviceRequest, DeviceUseStatement, and Device resource mapping.

    Example:
        etl = DeviceETL(session)
        device_exp = await etl.transform_and_load(source_device, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: DeviceETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Device ETL service.

        Args:
            session: SQLAlchemy async session for database operations.
            config: Optional ETL configuration.
            vocabulary_service: Optional vocabulary service for concept mapping.
        """
        self.session = session
        self.config = config or DeviceETLConfig()
        self.vocabulary_service = vocabulary_service

        self._source_cache: dict[str, int] = {}
        self._concept_cache: dict[str, int] = {}

    def _normalize_code_system(self, code_system: str | None) -> str | None:
        """Normalize code system to OMOP vocabulary ID."""
        if not code_system:
            return None
        normalized = code_system.lower().strip()
        return CODE_SYSTEM_VOCABULARY_MAP.get(normalized, code_system)

    async def _lookup_concept_id(
        self,
        code: str,
        code_system: str | None,
    ) -> tuple[int, int | None]:
        """Look up OMOP concept ID for a device code.

        Args:
            code: Device code (SNOMED, UDI, etc.)
            code_system: Code system identifier

        Returns:
            Tuple of (standard_concept_id, source_concept_id)
        """
        cache_key = f"{code_system}:{code}"

        if cache_key in self._concept_cache:
            concept_id = self._concept_cache[cache_key]
            return concept_id, concept_id

        if self.vocabulary_service and self.config.map_to_standard:
            try:
                vocab_id = self._normalize_code_system(code_system)
                if vocab_id:
                    result = self.vocabulary_service.search_concepts(
                        search_term=code,
                        vocabulary_ids=[vocab_id],
                        domain_ids=["Device"],
                        exact_match=True,
                    )
                    if result and len(result) > 0:
                        concept_id = result[0].concept_id
                        self._concept_cache[cache_key] = concept_id
                        return concept_id, concept_id
            except Exception as e:
                logger.debug(f"Concept lookup failed for device code {code}: {e}")

        # Return 0 for unmapped codes
        return 0, None

    def _normalize_dates(
        self,
        device: SourceDevice,
    ) -> tuple[date, datetime | None, date | None, datetime | None]:
        """Normalize device dates.

        Args:
            device: Source device record

        Returns:
            Tuple of (start_date, start_datetime, end_date, end_datetime)
        """
        start_date: date
        start_datetime: datetime | None = None

        # Priority: start_datetime > authored_datetime > today
        if device.start_datetime:
            if isinstance(device.start_datetime, datetime):
                start_date = device.start_datetime.date()
                start_datetime = device.start_datetime
            else:
                start_date = device.start_datetime
        elif device.authored_datetime:
            if isinstance(device.authored_datetime, datetime):
                start_date = device.authored_datetime.date()
                start_datetime = device.authored_datetime
            else:
                start_date = device.authored_datetime
        else:
            start_date = date.today()

        # End date (optional for devices)
        end_date: date | None = None
        end_datetime: datetime | None = None

        if device.end_datetime:
            if isinstance(device.end_datetime, datetime):
                end_date = device.end_datetime.date()
                end_datetime = device.end_datetime
            else:
                end_date = device.end_datetime

        return start_date, start_datetime, end_date, end_datetime

    def _get_device_type_concept_id(self, device: SourceDevice) -> int:
        """Determine the device type concept ID based on source.

        Args:
            device: Source device record

        Returns:
            OMOP device type concept ID
        """
        # Check FHIR resource type
        if device.fhir_resource_type:
            resource_type = device.fhir_resource_type.lower()
            if resource_type == "devicerequest":
                return DEVICE_TYPE_EXTENDED_MAP.get("request", self.config.default_device_type)
            elif resource_type == "deviceusestatement":
                return DEVICE_TYPE_EXTENDED_MAP.get("use_statement", self.config.default_device_type)

        return self.config.default_device_type

    def _should_include_device(self, device: SourceDevice) -> bool:
        """Check if device should be included in CDM.

        Args:
            device: Source device record

        Returns:
            True if device should be included
        """
        if not device.status:
            return True

        if device.status == DeviceStatus.ENTERED_IN_ERROR:
            return self.config.include_entered_in_error

        return DEVICE_STATUS_MAP.get(device.status, True)

    async def _find_existing_device(
        self,
        source_id: str,
    ) -> DeviceExposure | None:
        """Find existing DeviceExposure by source ID.

        Args:
            source_id: Source system device ID

        Returns:
            Existing DeviceExposure or None
        """
        if source_id in self._source_cache:
            stmt = select(DeviceExposure).where(
                DeviceExposure.device_exposure_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(DeviceExposure).where(
            DeviceExposure.device_source_value == source_id
        )
        result = await self.session.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            self._source_cache[source_id] = device.device_exposure_id

        return device

    async def transform(
        self,
        device: SourceDevice,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> dict[str, Any]:
        """Transform SourceDevice to DeviceExposure attributes.

        Args:
            device: Source device record
            person_id: OMOP person_id
            visit_occurrence_id: Optional OMOP visit_occurrence_id
            provider_id: Optional OMOP provider_id

        Returns:
            Dictionary of DeviceExposure attributes
        """
        # Map concepts
        concept_id, source_concept_id = await self._lookup_concept_id(
            device.device_code or "",
            device.device_code_system,
        )

        # Normalize dates
        start_date, start_datetime, end_date, end_datetime = self._normalize_dates(device)

        # Get device type
        device_type_concept_id = self._get_device_type_concept_id(device)

        # Build source value (code with system prefix if available)
        source_value = device.device_code
        if device.device_code_system and device.device_code:
            source_value = f"{device.device_code_system}:{device.device_code}"
        elif device.device_name:
            source_value = device.device_name

        return {
            "person_id": person_id,
            "device_concept_id": concept_id,
            "device_exposure_start_date": start_date,
            "device_exposure_start_datetime": start_datetime,
            "device_exposure_end_date": end_date,
            "device_exposure_end_datetime": end_datetime,
            "device_type_concept_id": device_type_concept_id,
            "unique_device_id": device.unique_device_id[:255] if device.unique_device_id else None,
            "production_id": device.production_id[:255] if device.production_id else None,
            "quantity": device.quantity,
            "provider_id": provider_id,
            "visit_occurrence_id": visit_occurrence_id,
            "visit_detail_id": None,
            "device_source_value": source_value[:50] if source_value else None,
            "device_source_concept_id": source_concept_id,
            "unit_concept_id": None,
            "unit_source_value": None,
            "unit_source_concept_id": None,
        }

    async def transform_and_load(
        self,
        device: SourceDevice,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> DeviceExposure | None:
        """Transform and load a single device record.

        Args:
            device: Source device record
            person_id: OMOP person_id
            visit_occurrence_id: Optional OMOP visit_occurrence_id
            provider_id: Optional OMOP provider_id

        Returns:
            Created/updated DeviceExposure or None if skipped
        """
        if not device.source_id:
            raise ValueError("Device must have a source_id")

        # Check if should include
        if not self._should_include_device(device):
            return None

        existing = await self._find_existing_device(device.source_id)

        device_data = await self.transform(
            device, person_id, visit_occurrence_id, provider_id
        )

        if existing:
            for key, value in device_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        device_exp = DeviceExposure(**device_data)
        self.session.add(device_exp)
        await self.session.flush()

        self._source_cache[device.source_id] = device_exp.device_exposure_id

        return device_exp

    async def transform_and_load_batch(
        self,
        devices: list[tuple[SourceDevice, int, int | None]],
    ) -> DeviceETLResult:
        """Transform and load a batch of devices.

        Args:
            devices: List of tuples (SourceDevice, person_id, visit_occurrence_id)

        Returns:
            DeviceETLResult with statistics
        """
        result = DeviceETLResult()

        for device, person_id, visit_id in devices:
            result.total_processed += 1

            try:
                existing = await self._find_existing_device(device.source_id) if device.source_id else None

                device_exp = await self.transform_and_load(
                    device, person_id, visit_id
                )

                if device_exp is None:
                    result.devices_skipped += 1
                elif existing:
                    result.devices_updated += 1
                else:
                    result.devices_created += 1

                if device_exp and device_exp.device_concept_id == 0:
                    result.unmapped_codes += 1

                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing device {device.source_id}: {e}")
                logger.warning(f"ETL error for device {device.source_id}: {e}")

        await self.session.commit()

        return result

    @staticmethod
    def from_fhir_device_request(resource: dict[str, Any], source_system: str = "fhir") -> SourceDevice:
        """Create SourceDevice from FHIR DeviceRequest resource.

        Args:
            resource: FHIR DeviceRequest JSON resource
            source_system: Source system identifier

        Returns:
            SourceDevice instance
        """
        device = SourceDevice(
            source_id=resource.get("id", ""),
            source_system=source_system,
            fhir_resource_type="DeviceRequest",
            raw_data=resource,
        )

        # Patient reference
        subject = resource.get("subject", {})
        if subject.get("reference"):
            device.patient_source_id = subject["reference"].replace("Patient/", "")

        # Visit/Encounter reference
        encounter = resource.get("encounter", {})
        if encounter.get("reference"):
            device.visit_source_id = encounter["reference"].replace("Encounter/", "")

        # Device code
        code_concept = resource.get("codeCodeableConcept", {})
        if code_concept.get("coding"):
            coding = code_concept["coding"][0]
            device.device_code = coding.get("code")
            device.device_code_system = coding.get("system")
            device.device_name = coding.get("display") or code_concept.get("text")

        # Status
        device.status = resource.get("status", DeviceStatus.UNKNOWN)

        # Authored date
        if resource.get("authoredOn"):
            try:
                device.authored_datetime = datetime.fromisoformat(
                    resource["authoredOn"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Occurrence timing
        occurrence = resource.get("occurrenceDateTime") or resource.get("occurrencePeriod", {})
        if isinstance(occurrence, str):
            try:
                device.start_datetime = datetime.fromisoformat(occurrence.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        elif isinstance(occurrence, dict):
            if occurrence.get("start"):
                try:
                    device.start_datetime = datetime.fromisoformat(
                        occurrence["start"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass
            if occurrence.get("end"):
                try:
                    device.end_datetime = datetime.fromisoformat(
                        occurrence["end"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

        # Requester/Provider
        requester = resource.get("requester", {})
        if requester.get("reference"):
            device.provider_id = requester["reference"].replace("Practitioner/", "")
        device.provider_name = requester.get("display")

        return device

    @staticmethod
    def from_fhir_device_use_statement(resource: dict[str, Any], source_system: str = "fhir") -> SourceDevice:
        """Create SourceDevice from FHIR DeviceUseStatement resource.

        Args:
            resource: FHIR DeviceUseStatement JSON resource
            source_system: Source system identifier

        Returns:
            SourceDevice instance
        """
        device = SourceDevice(
            source_id=resource.get("id", ""),
            source_system=source_system,
            fhir_resource_type="DeviceUseStatement",
            raw_data=resource,
        )

        # Patient reference
        subject = resource.get("subject", {})
        if subject.get("reference"):
            device.patient_source_id = subject["reference"].replace("Patient/", "")

        # Status
        device.status = resource.get("status", DeviceStatus.UNKNOWN)

        # Timing
        timing = resource.get("timingPeriod") or resource.get("timingDateTime")
        if isinstance(timing, str):
            try:
                device.start_datetime = datetime.fromisoformat(timing.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        elif isinstance(timing, dict):
            if timing.get("start"):
                try:
                    device.start_datetime = datetime.fromisoformat(
                        timing["start"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass
            if timing.get("end"):
                try:
                    device.end_datetime = datetime.fromisoformat(
                        timing["end"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

        # Device reference (would need to resolve to get code/UDI)
        device_ref = resource.get("device", {})
        if device_ref.get("reference"):
            # Store reference for later resolution
            device.raw_data["device_reference"] = device_ref["reference"]

        # Body site
        body_site = resource.get("bodySite", {})
        if body_site.get("coding"):
            coding = body_site["coding"][0]
            device.body_site_code = coding.get("code")
        device.body_site_text = body_site.get("text")

        return device

    @staticmethod
    def from_fhir_device(resource: dict[str, Any], source_system: str = "fhir") -> SourceDevice:
        """Create SourceDevice from FHIR Device resource.

        Note: FHIR Device represents the device definition, not its use.
        This is typically used to resolve device references.

        Args:
            resource: FHIR Device JSON resource
            source_system: Source system identifier

        Returns:
            SourceDevice instance
        """
        device = SourceDevice(
            source_id=resource.get("id", ""),
            source_system=source_system,
            fhir_resource_type="Device",
            raw_data=resource,
        )

        # Patient reference (owner)
        patient = resource.get("patient", {})
        if patient.get("reference"):
            device.patient_source_id = patient["reference"].replace("Patient/", "")

        # Device type
        device_type = resource.get("type", {})
        if device_type.get("coding"):
            coding = device_type["coding"][0]
            device.device_code = coding.get("code")
            device.device_code_system = coding.get("system")
            device.device_name = coding.get("display") or device_type.get("text")

        # UDI Carrier
        udi_carriers = resource.get("udiCarrier", [])
        if udi_carriers:
            udi = udi_carriers[0]
            device.unique_device_id = udi.get("deviceIdentifier") or udi.get("carrierHRF")

        # Device names
        device_names = resource.get("deviceName", [])
        if device_names and not device.device_name:
            device.device_name = device_names[0].get("name")

        # Lot number / Production ID
        device.production_id = resource.get("lotNumber") or resource.get("serialNumber")

        # Status
        device.status = resource.get("status", DeviceStatus.UNKNOWN)

        return device

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics.

        Returns:
            Dictionary with service statistics
        """
        return {
            "cached_mappings": len(self._source_cache),
            "cached_concepts": len(self._concept_cache),
        }
