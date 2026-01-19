"""Base classes and data models for source connectors.

This module defines:
1. SourceConnector - Abstract base class for all connectors
2. Source data models - Standardized intermediate representation
3. ConnectorConfig - Configuration for connectors
4. ExtractionResult - Result container with statistics

All connectors extract data into these standardized models, which are then
transformed to OMOP CDM format by the ETL pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, AsyncIterator


# ============================================================================
# Enums
# ============================================================================


class ConnectorType(str, Enum):
    """Types of source connectors."""

    FHIR = "fhir"
    HL7V2 = "hl7v2"
    CCDA = "ccda"
    CSV = "csv"
    DATABASE = "database"


class Gender(str, Enum):
    """Standardized gender values."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class ConditionStatus(str, Enum):
    """Status of a condition."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class DrugStatus(str, Enum):
    """Status of a drug/medication."""

    ACTIVE = "active"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ON_HOLD = "on_hold"
    UNKNOWN = "unknown"


class ProcedureStatus(str, Enum):
    """Status of a procedure."""

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    NOT_DONE = "not_done"
    UNKNOWN = "unknown"


class DeviceStatus(str, Enum):
    """Status of a device record."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ENTERED_IN_ERROR = "entered-in-error"
    INTENDED = "intended"
    STOPPED = "stopped"
    ON_HOLD = "on-hold"
    UNKNOWN = "unknown"


class SpecimenStatus(str, Enum):
    """Status of a specimen record."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSATISFACTORY = "unsatisfactory"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"


class VisitType(str, Enum):
    """Type of clinical visit."""

    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    EMERGENCY = "emergency"
    OBSERVATION = "observation"
    TELEHEALTH = "telehealth"
    HOME = "home"
    UNKNOWN = "unknown"


# ============================================================================
# Source Data Models (Intermediate Representation)
# ============================================================================


@dataclass
class SourceRecord:
    """Base class for all source records.

    All source records have:
    - source_id: Identifier in the source system
    - source_system: Name/identifier of the source system
    - extracted_at: When the record was extracted
    - raw_data: Original data for auditing/debugging
    """

    source_id: str
    source_system: str
    extracted_at: datetime = field(default_factory=datetime.now)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.extracted_at:
            self.extracted_at = datetime.now()


@dataclass
class SourcePatient(SourceRecord):
    """Standardized patient record.

    Maps to OMOP Person table.
    """

    # Demographics
    given_name: str | None = None
    family_name: str | None = None
    birth_date: date | None = None
    gender: Gender = Gender.UNKNOWN
    race: str | None = None
    ethnicity: str | None = None

    # Identifiers
    mrn: str | None = None
    ssn: str | None = None  # Should be handled carefully

    # Contact info
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None

    # Deceased info
    deceased: bool = False
    death_date: date | None = None

    @property
    def full_name(self) -> str:
        """Get full name."""
        parts = [self.given_name, self.family_name]
        return " ".join(p for p in parts if p) or "Unknown"

    @property
    def age(self) -> int | None:
        """Calculate current age in years."""
        if not self.birth_date:
            return None
        today = date.today()
        age = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1
        return age


@dataclass
class SourceVisit(SourceRecord):
    """Standardized visit/encounter record.

    Maps to OMOP Visit_Occurrence table.
    """

    patient_source_id: str = ""
    visit_type: VisitType = VisitType.UNKNOWN

    # Timing
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None

    # Location
    facility_name: str | None = None
    facility_id: str | None = None
    department: str | None = None

    # Provider
    attending_provider_id: str | None = None
    attending_provider_name: str | None = None

    # Admission/Discharge
    admit_source: str | None = None
    discharge_disposition: str | None = None

    @property
    def duration_hours(self) -> float | None:
        """Calculate visit duration in hours."""
        if self.start_datetime and self.end_datetime:
            delta = self.end_datetime - self.start_datetime
            return delta.total_seconds() / 3600
        return None


@dataclass
class SourceCondition(SourceRecord):
    """Standardized condition/diagnosis record.

    Maps to OMOP Condition_Occurrence table.
    """

    patient_source_id: str = ""
    visit_source_id: str | None = None

    # Condition details
    code: str | None = None
    code_system: str | None = None  # ICD10CM, SNOMED, etc.
    display_text: str | None = None
    status: ConditionStatus = ConditionStatus.UNKNOWN

    # Timing
    onset_datetime: datetime | None = None
    abatement_datetime: datetime | None = None
    recorded_datetime: datetime | None = None

    # Clinical context
    category: str | None = None  # encounter-diagnosis, problem-list, etc.
    severity: str | None = None
    body_site: str | None = None
    laterality: str | None = None  # left, right, bilateral

    # Provider who recorded
    recorder_id: str | None = None
    recorder_name: str | None = None


@dataclass
class SourceDrug(SourceRecord):
    """Standardized medication/drug record.

    Maps to OMOP Drug_Exposure table.
    """

    patient_source_id: str = ""
    visit_source_id: str | None = None

    # Drug details
    code: str | None = None
    code_system: str | None = None  # RxNorm, NDC, etc.
    display_text: str | None = None
    status: DrugStatus = DrugStatus.UNKNOWN

    # Timing
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    authored_datetime: datetime | None = None

    # Dosage
    dose_value: float | None = None
    dose_unit: str | None = None
    route: str | None = None  # oral, IV, topical, etc.
    frequency: str | None = None
    quantity: float | None = None
    days_supply: int | None = None
    refills: int | None = None

    # Prescriber
    prescriber_id: str | None = None
    prescriber_name: str | None = None

    # Additional info
    sig: str | None = None  # Instructions
    indication: str | None = None


@dataclass
class SourceProcedure(SourceRecord):
    """Standardized procedure record.

    Maps to OMOP Procedure_Occurrence table.
    """

    patient_source_id: str = ""
    visit_source_id: str | None = None

    # Procedure details
    code: str | None = None
    code_system: str | None = None  # CPT, ICD10PCS, SNOMED, etc.
    display_text: str | None = None
    status: ProcedureStatus = ProcedureStatus.UNKNOWN

    # Timing
    performed_datetime: datetime | None = None
    performed_end_datetime: datetime | None = None

    # Clinical context
    category: str | None = None
    body_site: str | None = None
    laterality: str | None = None
    outcome: str | None = None

    # Performer
    performer_id: str | None = None
    performer_name: str | None = None

    # Quantity (for repeated procedures)
    quantity: int = 1


@dataclass
class SourceMeasurement(SourceRecord):
    """Standardized measurement/lab result record.

    Maps to OMOP Measurement table.
    """

    patient_source_id: str = ""
    visit_source_id: str | None = None

    # Measurement details
    code: str | None = None
    code_system: str | None = None  # LOINC, SNOMED, etc.
    display_text: str | None = None

    # Value
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    unit_code: str | None = None  # UCUM code

    # Reference range
    range_low: float | None = None
    range_high: float | None = None
    interpretation: str | None = None  # normal, high, low, critical

    # Timing
    effective_datetime: datetime | None = None
    issued_datetime: datetime | None = None

    # Specimen
    specimen_id: str | None = None
    specimen_type: str | None = None

    # Provider
    performer_id: str | None = None
    performer_name: str | None = None


@dataclass
class SourceObservation(SourceRecord):
    """Standardized observation record (non-lab findings).

    Maps to OMOP Observation table.
    Includes: vitals, social history, allergies, etc.
    """

    patient_source_id: str = ""
    visit_source_id: str | None = None

    # Observation details
    code: str | None = None
    code_system: str | None = None
    display_text: str | None = None
    category: str | None = None  # vital-signs, social-history, etc.

    # Value
    value_numeric: float | None = None
    value_text: str | None = None
    value_boolean: bool | None = None
    value_code: str | None = None
    unit: str | None = None

    # Timing
    effective_datetime: datetime | None = None

    # Interpretation
    interpretation: str | None = None

    # For allergies
    criticality: str | None = None
    reaction: str | None = None


@dataclass
class SourceDevice(SourceRecord):
    """Standardized device record.

    Maps to OMOP Device_Exposure table.
    Represents FHIR DeviceRequest, DeviceUseStatement, or Device resources.
    """

    patient_source_id: str = ""
    visit_source_id: str | None = None

    # Device identification
    device_code: str | None = None
    device_code_system: str | None = None
    device_name: str | None = None
    unique_device_id: str | None = None  # UDI
    production_id: str | None = None  # Lot number or serial

    # Status
    status: DeviceStatus = DeviceStatus.UNKNOWN

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


@dataclass
class SourceSpecimen(SourceRecord):
    """Standardized specimen record.

    Maps to OMOP Specimen table.
    Represents FHIR Specimen resource.
    """

    patient_source_id: str = ""

    # Specimen identification
    specimen_code: str | None = None
    specimen_code_system: str | None = None
    specimen_type: str | None = None  # Display text

    # Status
    status: SpecimenStatus = SpecimenStatus.UNKNOWN

    # Collection timing
    collected_datetime: datetime | None = None
    received_datetime: datetime | None = None

    # Quantity
    quantity_value: float | None = None
    quantity_unit: str | None = None
    quantity_unit_code: str | None = None  # UCUM code

    # Anatomic site (collection body site)
    body_site_code: str | None = None
    body_site_code_system: str | None = None
    body_site_text: str | None = None

    # Disease status (condition at time of collection)
    disease_status_code: str | None = None
    disease_status_text: str | None = None

    # Container information
    container_type: str | None = None
    container_description: str | None = None

    # Processing information
    processing_method: str | None = None
    additive: str | None = None

    # Accession identifier
    accession_identifier: str | None = None

    # Parent specimen (for derived specimens)
    parent_specimen_id: str | None = None


# ============================================================================
# Connector Configuration
# ============================================================================


@dataclass
class ConnectorConfig:
    """Configuration for a source connector.

    Common configuration options for all connectors.
    Specific connectors may extend this with additional options.
    """

    # Connection
    name: str = "default"
    connector_type: ConnectorType = ConnectorType.CSV

    # Batching
    batch_size: int = 100
    max_records: int | None = None  # None = no limit

    # Filtering
    patient_ids: list[str] | None = None  # Extract specific patients only
    start_date: date | None = None
    end_date: date | None = None

    # Error handling
    skip_on_error: bool = True  # Continue if a record fails
    max_errors: int = 100  # Stop after this many errors

    # Logging
    log_progress: bool = True
    progress_interval: int = 1000  # Log every N records

    # Additional connector-specific options
    options: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Extraction Result
# ============================================================================


@dataclass
class ExtractionResult:
    """Result of a connector extraction operation.

    Contains statistics and any errors encountered.
    """

    connector_type: ConnectorType
    source_system: str
    started_at: datetime
    completed_at: datetime | None = None

    # Counts
    patients_extracted: int = 0
    visits_extracted: int = 0
    conditions_extracted: int = 0
    drugs_extracted: int = 0
    procedures_extracted: int = 0
    measurements_extracted: int = 0
    observations_extracted: int = 0
    devices_extracted: int = 0
    specimens_extracted: int = 0

    # Errors
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_records(self) -> int:
        """Total records extracted."""
        return (
            self.patients_extracted
            + self.visits_extracted
            + self.conditions_extracted
            + self.drugs_extracted
            + self.procedures_extracted
            + self.measurements_extracted
            + self.observations_extracted
            + self.devices_extracted
            + self.specimens_extracted
        )

    @property
    def duration_seconds(self) -> float | None:
        """Extraction duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success(self) -> bool:
        """Whether extraction completed without critical errors."""
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/API response."""
        return {
            "connector_type": self.connector_type.value,
            "source_system": self.source_system,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "total_records": self.total_records,
            "patients": self.patients_extracted,
            "visits": self.visits_extracted,
            "conditions": self.conditions_extracted,
            "drugs": self.drugs_extracted,
            "procedures": self.procedures_extracted,
            "measurements": self.measurements_extracted,
            "observations": self.observations_extracted,
            "devices": self.devices_extracted,
            "specimens": self.specimens_extracted,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "success": self.success,
        }


# ============================================================================
# Abstract Base Connector
# ============================================================================


class SourceConnector(ABC):
    """Abstract base class for all source connectors.

    All connectors must implement methods to extract each resource type
    as async iterators, allowing efficient streaming of large datasets.

    Example implementation:
        class MyConnector(SourceConnector):
            async def extract_patients(self) -> AsyncIterator[SourcePatient]:
                async for record in self._fetch_patients():
                    yield self._transform_patient(record)

            async def connect(self) -> bool:
                self._client = await create_client()
                return True

            async def disconnect(self) -> None:
                await self._client.close()

            async def test_connection(self) -> tuple[bool, str]:
                try:
                    await self._client.ping()
                    return True, "Connected"
                except Exception as e:
                    return False, str(e)
    """

    def __init__(self, config: ConnectorConfig | None = None):
        """Initialize the connector.

        Args:
            config: Connector configuration
        """
        self.config = config or ConnectorConfig()
        self._connected = False

    @property
    @abstractmethod
    def connector_type(self) -> ConnectorType:
        """Return the connector type."""
        pass

    @property
    @abstractmethod
    def source_system(self) -> str:
        """Return the source system identifier."""
        pass

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the source system.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the source system."""
        pass

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test the connection to the source system.

        Returns:
            Tuple of (success, message)
        """
        pass

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()

    # -------------------------------------------------------------------------
    # Data Extraction (Async Iterators)
    # -------------------------------------------------------------------------

    @abstractmethod
    async def extract_patients(self) -> AsyncIterator[SourcePatient]:
        """Extract patient records from the source.

        Yields:
            SourcePatient records
        """
        pass

    @abstractmethod
    async def extract_visits(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceVisit]:
        """Extract visit records from the source.

        Args:
            patient_source_id: Optional patient ID to filter visits

        Yields:
            SourceVisit records
        """
        pass

    @abstractmethod
    async def extract_conditions(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceCondition]:
        """Extract condition/diagnosis records from the source.

        Args:
            patient_source_id: Optional patient ID to filter conditions

        Yields:
            SourceCondition records
        """
        pass

    @abstractmethod
    async def extract_drugs(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceDrug]:
        """Extract medication records from the source.

        Args:
            patient_source_id: Optional patient ID to filter drugs

        Yields:
            SourceDrug records
        """
        pass

    @abstractmethod
    async def extract_procedures(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceProcedure]:
        """Extract procedure records from the source.

        Args:
            patient_source_id: Optional patient ID to filter procedures

        Yields:
            SourceProcedure records
        """
        pass

    @abstractmethod
    async def extract_measurements(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceMeasurement]:
        """Extract measurement/lab records from the source.

        Args:
            patient_source_id: Optional patient ID to filter measurements

        Yields:
            SourceMeasurement records
        """
        pass

    @abstractmethod
    async def extract_observations(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceObservation]:
        """Extract observation records from the source.

        Args:
            patient_source_id: Optional patient ID to filter observations

        Yields:
            SourceObservation records
        """
        pass

    async def extract_devices(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceDevice]:
        """Extract device records from the source.

        Args:
            patient_source_id: Optional patient ID to filter devices

        Yields:
            SourceDevice records

        Note:
            Default implementation yields nothing. Override in connectors
            that support device extraction.
        """
        return
        yield  # Makes this an async generator

    async def extract_specimens(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceSpecimen]:
        """Extract specimen records from the source.

        Args:
            patient_source_id: Optional patient ID to filter specimens

        Yields:
            SourceSpecimen records

        Note:
            Default implementation yields nothing. Override in connectors
            that support specimen extraction.
        """
        return
        yield  # Makes this an async generator

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def extract_all_for_patient(
        self, patient_source_id: str
    ) -> dict[str, list[SourceRecord]]:
        """Extract all records for a specific patient.

        Args:
            patient_source_id: Patient ID in source system

        Returns:
            Dictionary with lists of each record type
        """
        result: dict[str, list[SourceRecord]] = {
            "visits": [],
            "conditions": [],
            "drugs": [],
            "procedures": [],
            "measurements": [],
            "observations": [],
            "devices": [],
            "specimens": [],
        }

        async for visit in self.extract_visits(patient_source_id):
            result["visits"].append(visit)

        async for condition in self.extract_conditions(patient_source_id):
            result["conditions"].append(condition)

        async for drug in self.extract_drugs(patient_source_id):
            result["drugs"].append(drug)

        async for procedure in self.extract_procedures(patient_source_id):
            result["procedures"].append(procedure)

        async for measurement in self.extract_measurements(patient_source_id):
            result["measurements"].append(measurement)

        async for observation in self.extract_observations(patient_source_id):
            result["observations"].append(observation)

        async for device in self.extract_devices(patient_source_id):
            result["devices"].append(device)

        async for specimen in self.extract_specimens(patient_source_id):
            result["specimens"].append(specimen)

        return result

    async def run_extraction(self) -> ExtractionResult:
        """Run full extraction and return statistics.

        This method extracts all resource types and tracks statistics.
        For large datasets, consider using the individual extract_*
        methods with streaming.

        Returns:
            ExtractionResult with counts and any errors
        """
        result = ExtractionResult(
            connector_type=self.connector_type,
            source_system=self.source_system,
            started_at=datetime.now(),
        )

        try:
            await self.connect()

            # Extract patients
            async for _ in self.extract_patients():
                result.patients_extracted += 1

            # Extract visits
            async for _ in self.extract_visits():
                result.visits_extracted += 1

            # Extract conditions
            async for _ in self.extract_conditions():
                result.conditions_extracted += 1

            # Extract drugs
            async for _ in self.extract_drugs():
                result.drugs_extracted += 1

            # Extract procedures
            async for _ in self.extract_procedures():
                result.procedures_extracted += 1

            # Extract measurements
            async for _ in self.extract_measurements():
                result.measurements_extracted += 1

            # Extract observations
            async for _ in self.extract_observations():
                result.observations_extracted += 1

            # Extract devices
            async for _ in self.extract_devices():
                result.devices_extracted += 1

            # Extract specimens
            async for _ in self.extract_specimens():
                result.specimens_extracted += 1

        except Exception as e:
            result.errors.append({"error": str(e), "type": type(e).__name__})
        finally:
            await self.disconnect()
            result.completed_at = datetime.now()

        return result
