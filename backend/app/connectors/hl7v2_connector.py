"""HL7 v2.x Source Connector.

Parses HL7 v2.x messages (ADT, ORU, ORM, etc.) and extracts clinical data
into standardized format. Supports reading from files or message strings.

HL7 v2 Message Structure:
    MSH - Message Header
    PID - Patient Identification
    PV1 - Patient Visit
    DG1 - Diagnosis
    OBR - Observation Request
    OBX - Observation Result
    RXA - Pharmacy/Treatment Administration
    PR1 - Procedures

Usage:
    config = HL7v2ConnectorConfig(
        messages_dir="/path/to/hl7/messages",
        message_type="ORU"  # Optional filter
    )
    connector = HL7v2Connector(config)

    async with connector:
        async for patient in connector.extract_patients():
            print(patient.full_name)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from app.connectors.base import (
    ConditionStatus,
    ConnectorConfig,
    ConnectorType,
    DrugStatus,
    Gender,
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
    DEFAULT_CODE_SYSTEMS,
    HL7_CODING_METHOD_MAP,
    HL7_PATIENT_CLASS_MAP,
    parse_gender,
)

logger = logging.getLogger(__name__)


# ============================================================================
# HL7 v2 Connector Configuration
# ============================================================================


@dataclass
class HL7v2ConnectorConfig(ConnectorConfig):
    """Configuration for HL7 v2.x connector."""

    connector_type: ConnectorType = ConnectorType.HL7V2

    # Source options (use one)
    messages_dir: Path | str | None = None  # Directory with .hl7 files
    messages_file: Path | str | None = None  # Single file with messages
    messages: list[str] | None = None  # List of message strings

    # HL7 parsing options
    field_separator: str = "|"
    component_separator: str = "^"
    subcomponent_separator: str = "&"
    repetition_separator: str = "~"
    escape_character: str = "\\"
    segment_separator: str = "\r"

    # Filtering
    message_types: list[str] | None = None  # ADT, ORU, ORM, etc.
    include_extensions: list[str] = field(
        default_factory=lambda: [".hl7", ".txt", ".HL7"]
    )


# ============================================================================
# HL7 v2 Parser
# ============================================================================


class HL7v2Message:
    """Parsed HL7 v2.x message."""

    def __init__(
        self,
        raw: str,
        field_sep: str = "|",
        component_sep: str = "^",
        segment_sep: str = "\r",
    ):
        self.raw = raw
        self.field_sep = field_sep
        self.component_sep = component_sep
        self.segment_sep = segment_sep
        self.segments: dict[str, list[list[str]]] = {}
        self._parse()

    def _parse(self) -> None:
        """Parse the message into segments."""
        # Normalize line endings
        text = self.raw.replace("\r\n", "\r").replace("\n", "\r")
        lines = text.split(self.segment_sep)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Split into fields
            fields = line.split(self.field_sep)
            if not fields:
                continue

            segment_id = fields[0]
            if segment_id not in self.segments:
                self.segments[segment_id] = []

            # For MSH, the field separator itself is field 1
            if segment_id == "MSH":
                fields = [segment_id, self.field_sep] + fields[1:]

            self.segments[segment_id].append(fields)

    def get_segment(self, segment_id: str, index: int = 0) -> list[str] | None:
        """Get a specific segment by ID and occurrence index."""
        segments = self.segments.get(segment_id, [])
        if index < len(segments):
            return segments[index]
        return None

    def get_all_segments(self, segment_id: str) -> list[list[str]]:
        """Get all occurrences of a segment."""
        return self.segments.get(segment_id, [])

    def get_field(
        self,
        segment_id: str,
        field_num: int,
        segment_index: int = 0,
        component: int = 0,
    ) -> str | None:
        """Get a specific field value.

        Args:
            segment_id: Segment identifier (e.g., "PID", "OBX")
            field_num: Field number (1-based)
            segment_index: Which occurrence of the segment (0-based)
            component: Component within field (0-based, 0=full field)

        Returns:
            Field value or None
        """
        segment = self.get_segment(segment_id, segment_index)
        if not segment or field_num >= len(segment):
            return None

        value = segment[field_num]
        if not value:
            return None

        if component > 0:
            components = value.split(self.component_sep)
            if component <= len(components):
                return components[component - 1] or None
            return None

        return value

    def get_components(
        self, segment_id: str, field_num: int, segment_index: int = 0
    ) -> list[str]:
        """Get all components of a field."""
        value = self.get_field(segment_id, field_num, segment_index)
        if not value:
            return []
        return value.split(self.component_sep)

    @property
    def message_type(self) -> str | None:
        """Get message type (e.g., ADT^A01)."""
        return self.get_field("MSH", 9)

    @property
    def message_control_id(self) -> str | None:
        """Get message control ID."""
        return self.get_field("MSH", 10)

    @property
    def sending_application(self) -> str | None:
        """Get sending application."""
        return self.get_field("MSH", 3)

    @property
    def sending_facility(self) -> str | None:
        """Get sending facility."""
        return self.get_field("MSH", 4)


# ============================================================================
# HL7 v2 Connector
# ============================================================================


class HL7v2Connector(SourceConnector):
    """Source connector for HL7 v2.x messages.

    Parses HL7 v2 messages and extracts clinical data.
    Supports ADT (demographics), ORU (labs), and other message types.
    """

    def __init__(self, config: HL7v2ConnectorConfig):
        """Initialize HL7 v2 connector.

        Args:
            config: HL7 v2 connector configuration
        """
        super().__init__(config)
        self.hl7_config = config
        self._messages: list[HL7v2Message] = []
        self._source_system = config.name or "hl7v2"

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.HL7V2

    @property
    def source_system(self) -> str:
        return self._source_system

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    async def connect(self) -> bool:
        """Load and parse HL7 messages."""
        self._messages = []

        try:
            # Load from message strings
            if self.hl7_config.messages:
                for msg_str in self.hl7_config.messages:
                    msg = HL7v2Message(
                        msg_str,
                        self.hl7_config.field_separator,
                        self.hl7_config.component_separator,
                        self.hl7_config.segment_separator,
                    )
                    if self._should_include_message(msg):
                        self._messages.append(msg)

            # Load from single file
            elif self.hl7_config.messages_file:
                path = Path(self.hl7_config.messages_file)
                if path.exists():
                    self._load_messages_from_file(path)

            # Load from directory
            elif self.hl7_config.messages_dir:
                dir_path = Path(self.hl7_config.messages_dir)
                if dir_path.exists():
                    for ext in self.hl7_config.include_extensions:
                        for file_path in dir_path.glob(f"*{ext}"):
                            self._load_messages_from_file(file_path)

            self._connected = True
            logger.info(f"Loaded {len(self._messages)} HL7 v2 messages")
            return True

        except Exception as e:
            logger.error(f"Failed to load HL7 messages: {e}")
            return False

    def _load_messages_from_file(self, file_path: Path) -> None:
        """Load messages from a file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            # Split into individual messages (MSH starts each message)
            message_texts = re.split(r"(?=MSH\|)", content)

            for msg_text in message_texts:
                msg_text = msg_text.strip()
                if not msg_text.startswith("MSH"):
                    continue

                msg = HL7v2Message(
                    msg_text,
                    self.hl7_config.field_separator,
                    self.hl7_config.component_separator,
                    self.hl7_config.segment_separator,
                )
                if self._should_include_message(msg):
                    self._messages.append(msg)

        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")

    def _should_include_message(self, msg: HL7v2Message) -> bool:
        """Check if message should be included based on filters."""
        if not self.hl7_config.message_types:
            return True

        msg_type = msg.message_type
        if not msg_type:
            return False

        # Check if message type matches any filter (e.g., ADT, ORU)
        for filter_type in self.hl7_config.message_types:
            if msg_type.startswith(filter_type):
                return True

        return False

    async def disconnect(self) -> None:
        """Clear loaded messages."""
        self._messages = []
        self._connected = False

    async def test_connection(self) -> tuple[bool, str]:
        """Test that messages can be loaded."""
        if self._messages:
            return True, f"Loaded {len(self._messages)} messages"

        # Try to load
        success = await self.connect()
        if success:
            count = len(self._messages)
            await self.disconnect()
            return True, f"Can load {count} messages"

        return False, "No messages found or failed to parse"

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _parse_hl7_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse HL7 datetime format (YYYYMMDDHHMMSS)."""
        if not dt_str:
            return None

        # Remove timezone if present
        dt_str = dt_str.split("+")[0].split("-")[0]

        formats = [
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y%m%d",
            "%Y%m%d%H%M%S.%f",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(dt_str[:len(fmt.replace("%", ""))], fmt)
            except ValueError:
                continue

        return None

    def _parse_gender(self, gender_code: str | None) -> Gender:
        """Parse HL7 gender code."""
        return parse_gender(gender_code)

    def _parse_visit_type(self, patient_class: str | None) -> VisitType:
        """Parse HL7 patient class to visit type."""
        if not patient_class:
            return VisitType.UNKNOWN
        return HL7_PATIENT_CLASS_MAP.get(patient_class.upper(), VisitType.UNKNOWN)

    def _get_patient_id(self, msg: HL7v2Message) -> str | None:
        """Extract patient ID from PID segment."""
        # PID-3 is patient identifier list
        pid_3 = msg.get_field("PID", 3)
        if pid_3:
            # First component is usually the ID
            components = pid_3.split(self.hl7_config.component_separator)
            return components[0] if components else None
        return None

    def _get_visit_id(self, msg: HL7v2Message) -> str | None:
        """Extract visit ID from PV1 segment."""
        # PV1-19 is visit number
        return msg.get_field("PV1", 19)

    # -------------------------------------------------------------------------
    # Extraction Methods
    # -------------------------------------------------------------------------

    async def extract_patients(self) -> AsyncIterator[SourcePatient]:
        """Extract patients from PID segments."""
        seen_patients: set[str] = set()

        for msg in self._messages:
            pid_segment = msg.get_segment("PID")
            if not pid_segment:
                continue

            patient_id = self._get_patient_id(msg)
            if not patient_id or patient_id in seen_patients:
                continue
            seen_patients.add(patient_id)

            # PID-5: Patient Name (Family^Given^Middle)
            name_components = msg.get_components("PID", 5)
            family_name = name_components[0] if len(name_components) > 0 else None
            given_name = name_components[1] if len(name_components) > 1 else None

            # PID-7: Date of Birth
            dob = self._parse_hl7_datetime(msg.get_field("PID", 7))

            # PID-8: Sex
            gender = self._parse_gender(msg.get_field("PID", 8))

            # PID-10: Race
            race = msg.get_field("PID", 10, component=1)

            # PID-11: Address
            address_components = msg.get_components("PID", 11)

            # PID-13: Phone
            phone = msg.get_field("PID", 13, component=1)

            # PID-29: Death date/time
            death_dt = self._parse_hl7_datetime(msg.get_field("PID", 29))

            # PID-30: Death indicator
            deceased = msg.get_field("PID", 30, 0, 0) in ("Y", "1", "true")

            patient = SourcePatient(
                source_id=patient_id,
                source_system=self.source_system,
                raw_data={"PID": pid_segment},
                given_name=given_name,
                family_name=family_name,
                birth_date=dob.date() if dob else None,
                gender=gender,
                race=race,
                mrn=patient_id,
                address_line1=address_components[0] if len(address_components) > 0 else None,
                city=address_components[2] if len(address_components) > 2 else None,
                state=address_components[3] if len(address_components) > 3 else None,
                postal_code=address_components[4] if len(address_components) > 4 else None,
                phone=phone,
                deceased=deceased or death_dt is not None,
                death_date=death_dt.date() if death_dt else None,
            )

            yield patient

    async def extract_visits(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceVisit]:
        """Extract visits from PV1 segments."""
        seen_visits: set[str] = set()

        for msg in self._messages:
            pv1_segment = msg.get_segment("PV1")
            if not pv1_segment:
                continue

            patient_id = self._get_patient_id(msg)
            if patient_source_id and patient_id != patient_source_id:
                continue

            visit_id = self._get_visit_id(msg) or msg.message_control_id
            if not visit_id or visit_id in seen_visits:
                continue
            seen_visits.add(visit_id)

            # PV1-2: Patient Class (I=inpatient, O=outpatient, E=emergency)
            visit_type = self._parse_visit_type(msg.get_field("PV1", 2))

            # PV1-3: Assigned Patient Location
            location = msg.get_field("PV1", 3)

            # PV1-7: Attending Doctor
            attending = msg.get_components("PV1", 7)
            attending_id = attending[0] if len(attending) > 0 else None
            attending_name = f"{attending[2]} {attending[1]}" if len(attending) > 2 else None

            # PV1-44: Admit Date/Time
            admit_dt = self._parse_hl7_datetime(msg.get_field("PV1", 44))

            # PV1-45: Discharge Date/Time
            discharge_dt = self._parse_hl7_datetime(msg.get_field("PV1", 45))

            visit = SourceVisit(
                source_id=visit_id,
                source_system=self.source_system,
                raw_data={"PV1": pv1_segment},
                patient_source_id=patient_id or "",
                visit_type=visit_type,
                start_datetime=admit_dt,
                end_datetime=discharge_dt,
                facility_name=msg.sending_facility,
                department=location,
                attending_provider_id=attending_id,
                attending_provider_name=attending_name,
            )

            yield visit

    async def extract_conditions(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceCondition]:
        """Extract conditions from DG1 segments."""
        for msg in self._messages:
            patient_id = self._get_patient_id(msg)
            if patient_source_id and patient_id != patient_source_id:
                continue

            visit_id = self._get_visit_id(msg)

            for i, dg1_segment in enumerate(msg.get_all_segments("DG1")):
                # DG1-2: Diagnosis Coding Method (I9, I10)
                coding_method = msg.get_field("DG1", 2, i)

                # DG1-3: Diagnosis Code
                code_components = msg.get_components("DG1", 3)
                code = code_components[0] if len(code_components) > 0 else None
                display = code_components[1] if len(code_components) > 1 else None
                code_system = code_components[2] if len(code_components) > 2 else None

                if not code_system:
                    code_system = HL7_CODING_METHOD_MAP.get(
                        coding_method, DEFAULT_CODE_SYSTEMS["condition"]
                    )

                # DG1-5: Diagnosis Date/Time
                diag_dt = self._parse_hl7_datetime(msg.get_field("DG1", 5, i))

                # DG1-6: Diagnosis Type (A=admitting, F=final, W=working)
                diag_type = msg.get_field("DG1", 6, i)

                condition_id = f"{msg.message_control_id}-DG1-{i}"

                condition = SourceCondition(
                    source_id=condition_id,
                    source_system=self.source_system,
                    raw_data={"DG1": dg1_segment},
                    patient_source_id=patient_id or "",
                    visit_source_id=visit_id,
                    code=code,
                    code_system=code_system,
                    display_text=display,
                    status=ConditionStatus.ACTIVE,
                    onset_datetime=diag_dt,
                    category=diag_type,
                )

                if condition.code:
                    yield condition

    async def extract_drugs(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceDrug]:
        """Extract medications from RXA segments."""
        for msg in self._messages:
            patient_id = self._get_patient_id(msg)
            if patient_source_id and patient_id != patient_source_id:
                continue

            visit_id = self._get_visit_id(msg)

            for i, rxa_segment in enumerate(msg.get_all_segments("RXA")):
                # RXA-3: Date/Time Start of Administration
                start_dt = self._parse_hl7_datetime(msg.get_field("RXA", 3, i))

                # RXA-4: Date/Time End of Administration
                end_dt = self._parse_hl7_datetime(msg.get_field("RXA", 4, i))

                # RXA-5: Administered Code
                code_components = msg.get_components("RXA", 5)
                code = code_components[0] if len(code_components) > 0 else None
                display = code_components[1] if len(code_components) > 1 else None
                code_system = code_components[2] if len(code_components) > 2 else None

                # RXA-6: Administered Amount
                amount = msg.get_field("RXA", 6, i)

                # RXA-7: Administered Units
                units = msg.get_field("RXA", 7, i, component=1)

                # RXA-9: Administration Notes
                notes = msg.get_field("RXA", 9, i)

                drug_id = f"{msg.message_control_id}-RXA-{i}"

                drug = SourceDrug(
                    source_id=drug_id,
                    source_system=self.source_system,
                    raw_data={"RXA": rxa_segment},
                    patient_source_id=patient_id or "",
                    visit_source_id=visit_id,
                    code=code,
                    code_system=code_system or DEFAULT_CODE_SYSTEMS["drug"],
                    display_text=display,
                    status=DrugStatus.ACTIVE,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    dose_value=float(amount) if amount else None,
                    dose_unit=units,
                    sig=notes,
                )

                if drug.display_text or drug.code:
                    yield drug

    async def extract_procedures(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceProcedure]:
        """Extract procedures from PR1 segments."""
        for msg in self._messages:
            patient_id = self._get_patient_id(msg)
            if patient_source_id and patient_id != patient_source_id:
                continue

            visit_id = self._get_visit_id(msg)

            for i, pr1_segment in enumerate(msg.get_all_segments("PR1")):
                # PR1-3: Procedure Code
                code_components = msg.get_components("PR1", 3)
                code = code_components[0] if len(code_components) > 0 else None
                display = code_components[1] if len(code_components) > 1 else None
                code_system = code_components[2] if len(code_components) > 2 else None

                # PR1-5: Procedure Date/Time
                proc_dt = self._parse_hl7_datetime(msg.get_field("PR1", 5, i))

                # PR1-11: Surgeon
                surgeon = msg.get_components("PR1", 11)
                surgeon_id = surgeon[0] if len(surgeon) > 0 else None
                surgeon_name = f"{surgeon[2]} {surgeon[1]}" if len(surgeon) > 2 else None

                proc_id = f"{msg.message_control_id}-PR1-{i}"

                procedure = SourceProcedure(
                    source_id=proc_id,
                    source_system=self.source_system,
                    raw_data={"PR1": pr1_segment},
                    patient_source_id=patient_id or "",
                    visit_source_id=visit_id,
                    code=code,
                    code_system=code_system or DEFAULT_CODE_SYSTEMS["procedure"],
                    display_text=display,
                    performed_datetime=proc_dt,
                    performer_id=surgeon_id,
                    performer_name=surgeon_name,
                )

                if procedure.code or procedure.display_text:
                    yield procedure

    async def extract_measurements(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceMeasurement]:
        """Extract measurements from OBX segments (labs, vitals)."""
        for msg in self._messages:
            patient_id = self._get_patient_id(msg)
            if patient_source_id and patient_id != patient_source_id:
                continue

            visit_id = self._get_visit_id(msg)

            # Get OBR for context
            obr_dt = self._parse_hl7_datetime(msg.get_field("OBR", 7))

            for i, obx_segment in enumerate(msg.get_all_segments("OBX")):
                # OBX-2: Value Type (NM=numeric, ST=string, etc.)
                value_type = msg.get_field("OBX", 2, i)

                # OBX-3: Observation Identifier
                code_components = msg.get_components("OBX", 3)
                code = code_components[0] if len(code_components) > 0 else None
                display = code_components[1] if len(code_components) > 1 else None
                code_system = code_components[2] if len(code_components) > 2 else None

                # OBX-5: Observation Value
                value = msg.get_field("OBX", 5, i)
                value_numeric = None
                value_text = None

                if value_type == "NM" and value:
                    try:
                        value_numeric = float(value)
                    except ValueError:
                        value_text = value
                else:
                    value_text = value

                # OBX-6: Units
                units_components = msg.get_components("OBX", 6)
                unit = units_components[0] if len(units_components) > 0 else None

                # OBX-7: Reference Range
                ref_range = msg.get_field("OBX", 7, i)
                range_low = None
                range_high = None
                if ref_range and "-" in ref_range:
                    parts = ref_range.split("-")
                    try:
                        range_low = float(parts[0])
                        range_high = float(parts[1])
                    except ValueError:
                        pass

                # OBX-8: Abnormal Flags
                interpretation = msg.get_field("OBX", 8, i)

                # OBX-14: Date/Time of Observation
                obs_dt = self._parse_hl7_datetime(msg.get_field("OBX", 14, i)) or obr_dt

                measurement_id = f"{msg.message_control_id}-OBX-{i}"

                measurement = SourceMeasurement(
                    source_id=measurement_id,
                    source_system=self.source_system,
                    raw_data={"OBX": obx_segment},
                    patient_source_id=patient_id or "",
                    visit_source_id=visit_id,
                    code=code,
                    code_system=code_system or DEFAULT_CODE_SYSTEMS["measurement"],
                    display_text=display,
                    value_numeric=value_numeric,
                    value_text=value_text,
                    unit=unit,
                    range_low=range_low,
                    range_high=range_high,
                    interpretation=interpretation,
                    effective_datetime=obs_dt,
                )

                if measurement.code or measurement.display_text:
                    yield measurement

    async def extract_observations(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceObservation]:
        """Extract observations (non-lab OBX, allergies from AL1)."""
        for msg in self._messages:
            patient_id = self._get_patient_id(msg)
            if patient_source_id and patient_id != patient_source_id:
                continue

            visit_id = self._get_visit_id(msg)

            # Extract allergies from AL1 segments
            for i, al1_segment in enumerate(msg.get_all_segments("AL1")):
                # AL1-3: Allergen Code/Mnemonic/Description
                allergen_components = msg.get_components("AL1", 3)
                code = allergen_components[0] if len(allergen_components) > 0 else None
                display = allergen_components[1] if len(allergen_components) > 1 else None

                # AL1-4: Allergy Severity Code
                severity = msg.get_field("AL1", 4, i)

                # AL1-5: Allergy Reaction Code
                reaction = msg.get_field("AL1", 5, i)

                obs_id = f"{msg.message_control_id}-AL1-{i}"

                observation = SourceObservation(
                    source_id=obs_id,
                    source_system=self.source_system,
                    raw_data={"AL1": al1_segment},
                    patient_source_id=patient_id or "",
                    visit_source_id=visit_id,
                    code=code,
                    display_text=f"Allergy: {display}" if display else None,
                    category="allergy",
                    criticality=severity,
                    reaction=reaction,
                )

                if observation.display_text:
                    yield observation
