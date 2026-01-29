"""C-CDA/CDA Source Connector.

This module provides a connector for extracting clinical data from
C-CDA (Consolidated Clinical Document Architecture) and HL7 CDA documents.

Supported Document Types:
    - CCD (Continuity of Care Document)
    - Discharge Summary
    - Consultation Note
    - Progress Note
    - Any valid C-CDA Release 2.1 document

Supported Sections (templateIds):
    - Patient Demographics: recordTarget
    - Problems: 2.16.840.1.113883.10.20.22.2.5.1
    - Medications: 2.16.840.1.113883.10.20.22.2.1.1
    - Allergies: 2.16.840.1.113883.10.20.22.2.6.1
    - Vital Signs: 2.16.840.1.113883.10.20.22.2.4.1
    - Results: 2.16.840.1.113883.10.20.22.2.3.1
    - Procedures: 2.16.840.1.113883.10.20.22.2.7.1
    - Encounters: 2.16.840.1.113883.10.20.22.2.22.1

Usage:
    config = CCDAConnectorConfig(
        documents_path="/path/to/ccda/files",
        file_pattern="*.xml"
    )
    connector = CCDAConnector(config)

    async for patient in connector.extract_patients():
        print(patient.source_id, patient.given_name, patient.family_name)
"""

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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
    CCDA_ENCOUNTER_CODE_MAP,
    CCDA_SECTION_TEMPLATE_IDS,
)

# C-CDA XML Namespaces
NAMESPACES = {
    "cda": "urn:hl7-org:v3",
    "sdtc": "urn:hl7-org:sdtc",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# Use consolidated section template IDs from concept_mappings
# Local alias for backward compatibility
SECTION_TEMPLATE_IDS = CCDA_SECTION_TEMPLATE_IDS


@dataclass
class CCDAConnectorConfig(ConnectorConfig):
    """Configuration for C-CDA document connector.

    Attributes:
        documents_path: Path to directory containing C-CDA XML files.
        documents: List of XML strings to parse (alternative to file path).
        file_pattern: Glob pattern for finding XML files (default: "*.xml").
        recursive: Whether to search subdirectories (default: False).
        encoding: File encoding (default: "utf-8").
        validate_structure: Whether to validate C-CDA structure (default: True).
        extract_free_text: Extract narrative text sections (default: True).
    """

    documents_path: Path | None = None
    documents: list[str] = field(default_factory=list)
    file_pattern: str = "*.xml"
    recursive: bool = False
    encoding: str = "utf-8"
    validate_structure: bool = True
    extract_free_text: bool = True

    def __post_init__(self) -> None:
        """Set connector type after initialization."""
        self.connector_type = ConnectorType.CCDA


class CCDADocument:
    """Parser for a single C-CDA document.

    Provides methods to extract patient demographics and clinical data
    from C-CDA XML structure using XPath queries.
    """

    def __init__(self, xml_content: str, source_file: str | None = None):
        """Initialize C-CDA document parser.

        Args:
            xml_content: Raw XML string of the C-CDA document.
            source_file: Optional source file path for error messages.
        """
        self.source_file = source_file or "unknown"
        self.root: ET.Element | None = None
        self._parse(xml_content)

    def _parse(self, xml_content: str) -> None:
        """Parse XML content into element tree.

        Args:
            xml_content: Raw XML string.

        Raises:
            ValueError: If XML is invalid or not a C-CDA document.
        """
        try:
            # Register namespaces to preserve prefixes
            for prefix, uri in NAMESPACES.items():
                ET.register_namespace(prefix, uri)

            self.root = ET.fromstring(xml_content)

            # Verify it's a ClinicalDocument
            if not self.root.tag.endswith("ClinicalDocument"):
                raise ValueError(f"Root element is not ClinicalDocument: {self.root.tag}")

        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in {self.source_file}: {e}")

    def _find(self, xpath: str, context: ET.Element | None = None) -> ET.Element | None:
        """Find first element matching XPath.

        Args:
            xpath: XPath expression with namespace prefixes.
            context: Context element (defaults to root).

        Returns:
            First matching element or None.
        """
        context = context if context is not None else self.root
        if context is None:
            return None
        return context.find(xpath, NAMESPACES)

    def _findall(self, xpath: str, context: ET.Element | None = None) -> list[ET.Element]:
        """Find all elements matching XPath.

        Args:
            xpath: XPath expression with namespace prefixes.
            context: Context element (defaults to root).

        Returns:
            List of matching elements.
        """
        context = context if context is not None else self.root
        if context is None:
            return []
        return context.findall(xpath, NAMESPACES)

    def _get_text(self, xpath: str, context: ET.Element | None = None) -> str | None:
        """Get text content from element.

        Args:
            xpath: XPath expression.
            context: Context element.

        Returns:
            Text content or None.
        """
        elem = self._find(xpath, context)
        if elem is not None:
            return elem.text
        return None

    def _get_attr(self, xpath: str, attr: str, context: ET.Element | None = None) -> str | None:
        """Get attribute value from element.

        Args:
            xpath: XPath expression.
            attr: Attribute name.
            context: Context element.

        Returns:
            Attribute value or None.
        """
        elem = self._find(xpath, context)
        if elem is not None:
            return elem.get(attr)
        return None

    def _parse_date(self, value: str | None) -> datetime | None:
        """Parse HL7 date/datetime string.

        Supports formats:
            - YYYYMMDD
            - YYYYMMDDHHMMSS
            - YYYYMMDDHHMMSS.SSS
            - With timezone offset

        Args:
            value: HL7 date string.

        Returns:
            Parsed datetime or None.
        """
        if not value:
            return None

        # Strip timezone info for simplicity
        value = re.sub(r"[+-]\d{4}$", "", value)

        formats = [
            "%Y%m%d%H%M%S.%f",
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y%m%d",
            "%Y%m",
            "%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value[:len(fmt.replace("%", ""))], fmt)
            except (ValueError, IndexError):
                continue

        return None

    def _get_code(self, xpath: str, context: ET.Element | None = None) -> dict[str, str | None]:
        """Extract code element attributes.

        Args:
            xpath: XPath to code element.
            context: Context element.

        Returns:
            Dictionary with code, codeSystem, codeSystemName, displayName.
        """
        elem = self._find(xpath, context)
        if elem is None:
            return {"code": None, "code_system": None, "code_system_name": None, "display_name": None}

        return {
            "code": elem.get("code"),
            "code_system": elem.get("codeSystem"),
            "code_system_name": elem.get("codeSystemName"),
            "display_name": elem.get("displayName"),
        }

    def _get_section_by_template_id(self, template_id: str) -> ET.Element | None:
        """Find section by template ID.

        Args:
            template_id: C-CDA section template OID.

        Returns:
            Section element or None.
        """
        for section in self._findall(".//cda:section"):
            for template in self._findall("cda:templateId", section):
                if template.get("root") == template_id:
                    return section
        return None

    def get_document_id(self) -> str:
        """Get unique document identifier.

        Returns:
            Document ID from id element or generated from file.
        """
        id_elem = self._find("cda:id")
        if id_elem is not None:
            root = id_elem.get("root", "")
            ext = id_elem.get("extension", "")
            if ext:
                return f"{root}^{ext}"
            return root
        return f"doc_{hash(self.source_file)}"

    def get_patient_id(self) -> str:
        """Get patient identifier from recordTarget.

        Returns:
            Patient ID string.
        """
        id_elem = self._find("cda:recordTarget/cda:patientRole/cda:id")
        if id_elem is not None:
            root = id_elem.get("root", "")
            ext = id_elem.get("extension", "")
            if ext:
                return f"{root}^{ext}"
            return root
        return f"patient_{self.get_document_id()}"

    def get_patient_demographics(self) -> SourcePatient:
        """Extract patient demographics from recordTarget.

        Returns:
            SourcePatient with demographics data.
        """
        patient_role = self._find("cda:recordTarget/cda:patientRole")
        patient = self._find("cda:patient", patient_role) if patient_role else None

        # Parse name
        given_names: list[str] = []
        family_name = None
        if patient:
            for given in self._findall("cda:name/cda:given", patient):
                if given.text:
                    given_names.append(given.text)
            family_elem = self._find("cda:name/cda:family", patient)
            family_name = family_elem.text if family_elem is not None else None

        # Parse gender
        gender_code = self._get_attr("cda:administrativeGenderCode", "code", patient)
        gender = Gender.UNKNOWN
        if gender_code == "M":
            gender = Gender.MALE
        elif gender_code == "F":
            gender = Gender.FEMALE
        elif gender_code == "UN":
            gender = Gender.OTHER

        # Parse birth date
        birth_time = self._get_attr("cda:birthTime", "value", patient)
        birth_date = self._parse_date(birth_time)

        # Parse race (SDTC extension)
        race_code = self._get_code("cda:raceCode", patient)

        # Parse ethnicity
        ethnicity_code = self._get_code("cda:ethnicGroupCode", patient)

        # Parse address
        addr = self._find("cda:addr", patient_role)
        address_parts = []
        city = state = postal_code = country = None
        if addr:
            for street in self._findall("cda:streetAddressLine", addr):
                if street.text:
                    address_parts.append(street.text)
            city = self._get_text("cda:city", addr)
            state = self._get_text("cda:state", addr)
            postal_code = self._get_text("cda:postalCode", addr)
            country = self._get_text("cda:country", addr)

        # Parse MRN (Medical Record Number)
        mrn = None
        for id_elem in self._findall("cda:id", patient_role):
            # Look for MRN-type identifier
            root = id_elem.get("root", "")
            if "MRN" in root.upper() or "2.16.840.1.113883.4.1" not in root:  # Not SSN
                mrn = id_elem.get("extension")
                if mrn:
                    break

        return SourcePatient(
            source_id=self.get_patient_id(),
            mrn=mrn,
            given_name=" ".join(given_names) if given_names else None,
            family_name=family_name,
            birth_date=birth_date,
            gender=gender,
            race=race_code.get("display_name"),
            ethnicity=ethnicity_code.get("display_name"),
            address_line1=address_parts[0] if address_parts else None,
            address_line2=address_parts[1] if len(address_parts) > 1 else None,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            raw_data={"source_file": self.source_file, "document_id": self.get_document_id()},
        )

    def get_encounters(self) -> list[SourceVisit]:
        """Extract encounters from Encounters section.

        Returns:
            List of SourceVisit objects.
        """
        visits: list[SourceVisit] = []
        section = self._get_section_by_template_id(SECTION_TEMPLATE_IDS["encounters"])

        if section is None:
            # Try to get encounter from encompassingEncounter
            enc = self._find("cda:componentOf/cda:encompassingEncounter")
            if enc is not None:
                visits.append(self._parse_encounter(enc, "encompassing"))
            return visits

        # Parse encounter entries
        for idx, entry in enumerate(self._findall("cda:entry/cda:encounter", section)):
            visits.append(self._parse_encounter(entry, f"enc_{idx}"))

        return visits

    def _parse_encounter(self, encounter: ET.Element, default_id: str) -> SourceVisit:
        """Parse a single encounter element.

        Args:
            encounter: Encounter XML element.
            default_id: Default ID if none found.

        Returns:
            SourceVisit object.
        """
        # Get encounter ID
        id_elem = self._find("cda:id", encounter)
        visit_id = default_id
        if id_elem is not None:
            ext = id_elem.get("extension")
            root = id_elem.get("root", "")
            visit_id = ext if ext else root

        # Parse dates
        eff_time = self._find("cda:effectiveTime", encounter)
        start_date = end_date = None
        if eff_time is not None:
            low = self._get_attr("cda:low", "value", eff_time)
            high = self._get_attr("cda:high", "value", eff_time)
            center = eff_time.get("value")
            start_date = self._parse_date(low or center)
            end_date = self._parse_date(high)

        # Parse encounter type
        code = self._get_code("cda:code", encounter)
        visit_type = VisitType.OUTPATIENT

        # Map common encounter codes to visit types
        code_value = code.get("code", "")
        visit_type = CCDA_ENCOUNTER_CODE_MAP.get(code_value, VisitType.OUTPATIENT)

        return SourceVisit(
            source_id=f"{self.get_patient_id()}_{visit_id}",
            patient_source_id=self.get_patient_id(),
            visit_type=visit_type,
            start_date=start_date,
            end_date=end_date,
            visit_source_value=code.get("display_name") or code_value,
            raw_data={
                "code": code.get("code"),
                "code_system": code.get("code_system"),
                "display_name": code.get("display_name"),
            },
        )

    def get_problems(self) -> list[SourceCondition]:
        """Extract problems/diagnoses from Problems section.

        Returns:
            List of SourceCondition objects.
        """
        conditions: list[SourceCondition] = []
        section = self._get_section_by_template_id(SECTION_TEMPLATE_IDS["problems"])

        if section is None:
            return conditions

        for idx, entry in enumerate(self._findall("cda:entry", section)):
            # Problem acts contain observations
            act = self._find("cda:act", entry)
            if act is None:
                continue

            obs = self._find("cda:entryRelationship/cda:observation", act)
            if obs is None:
                continue

            # Get problem code
            code = self._get_code("cda:value", obs)
            if not code.get("code"):
                # Try translation
                code = self._get_code("cda:value/cda:translation", obs)

            # Parse dates
            eff_time = self._find("cda:effectiveTime", obs)
            start_date = end_date = None
            if eff_time is not None:
                low = self._get_attr("cda:low", "value", eff_time)
                high = self._get_attr("cda:high", "value", eff_time)
                start_date = self._parse_date(low)
                end_date = self._parse_date(high)

            # Parse status
            status_code = self._get_attr("cda:statusCode", "code", obs)
            status = ConditionStatus.ACTIVE
            if status_code == "completed":
                status = ConditionStatus.RESOLVED
            elif status_code == "aborted":
                status = ConditionStatus.INACTIVE

            conditions.append(SourceCondition(
                source_id=f"{self.get_patient_id()}_prob_{idx}",
                patient_source_id=self.get_patient_id(),
                condition_code=code.get("code"),
                condition_code_system=code.get("code_system_name") or code.get("code_system"),
                condition_name=code.get("display_name"),
                onset_date=start_date,
                resolution_date=end_date,
                status=status,
                raw_data={
                    "code": code.get("code"),
                    "code_system": code.get("code_system"),
                    "code_system_name": code.get("code_system_name"),
                    "display_name": code.get("display_name"),
                },
            ))

        return conditions

    def get_medications(self) -> list[SourceDrug]:
        """Extract medications from Medications section.

        Returns:
            List of SourceDrug objects.
        """
        drugs: list[SourceDrug] = []
        section = self._get_section_by_template_id(SECTION_TEMPLATE_IDS["medications"])

        if section is None:
            return drugs

        for idx, entry in enumerate(self._findall("cda:entry", section)):
            subst_admin = self._find("cda:substanceAdministration", entry)
            if subst_admin is None:
                continue

            # Get drug code from manufacturedProduct
            consumable = self._find("cda:consumable/cda:manufacturedProduct", subst_admin)
            code = self._get_code("cda:manufacturedMaterial/cda:code", consumable)

            if not code.get("code"):
                # Try translation
                code = self._get_code("cda:manufacturedMaterial/cda:code/cda:translation", consumable)

            # Parse dates
            eff_time = self._find("cda:effectiveTime[@xsi:type='IVL_TS']", subst_admin)
            if eff_time is None:
                eff_time = self._find("cda:effectiveTime", subst_admin)

            start_date = end_date = None
            if eff_time is not None:
                low = self._get_attr("cda:low", "value", eff_time)
                high = self._get_attr("cda:high", "value", eff_time)
                center = eff_time.get("value")
                start_date = self._parse_date(low or center)
                end_date = self._parse_date(high)

            # Parse dose
            dose_elem = self._find("cda:doseQuantity", subst_admin)
            dose_value = dose_unit = None
            if dose_elem is not None:
                dose_value = dose_elem.get("value")
                dose_unit = dose_elem.get("unit")

            # Parse route
            route_code = self._get_code("cda:routeCode", subst_admin)

            # Parse status
            status_code = self._get_attr("cda:statusCode", "code", subst_admin)
            status = DrugStatus.ACTIVE
            if status_code == "completed":
                status = DrugStatus.COMPLETED
            elif status_code == "aborted":
                status = DrugStatus.STOPPED

            drugs.append(SourceDrug(
                source_id=f"{self.get_patient_id()}_med_{idx}",
                patient_source_id=self.get_patient_id(),
                drug_code=code.get("code"),
                drug_code_system=code.get("code_system_name") or code.get("code_system"),
                drug_name=code.get("display_name"),
                start_date=start_date,
                end_date=end_date,
                status=status,
                dose_value=dose_value,
                dose_unit=dose_unit,
                route=route_code.get("display_name") or route_code.get("code"),
                raw_data={
                    "code": code.get("code"),
                    "code_system": code.get("code_system"),
                    "display_name": code.get("display_name"),
                    "route_code": route_code.get("code"),
                },
            ))

        return drugs

    def get_vital_signs(self) -> list[SourceMeasurement]:
        """Extract vital signs from Vital Signs section.

        Returns:
            List of SourceMeasurement objects.
        """
        measurements: list[SourceMeasurement] = []
        section = self._get_section_by_template_id(SECTION_TEMPLATE_IDS["vital_signs"])

        if section is None:
            return measurements

        for org_idx, organizer in enumerate(self._findall("cda:entry/cda:organizer", section)):
            # Parse organizer time (applies to all components)
            org_time = self._get_attr("cda:effectiveTime", "value", organizer)
            measurement_date = self._parse_date(org_time)

            for comp_idx, component in enumerate(self._findall("cda:component/cda:observation", organizer)):
                code = self._get_code("cda:code", component)

                # Get value
                value_elem = self._find("cda:value", component)
                value = unit = None
                if value_elem is not None:
                    value = value_elem.get("value")
                    unit = value_elem.get("unit")

                # Use observation time if available
                obs_time = self._get_attr("cda:effectiveTime", "value", component)
                obs_date = self._parse_date(obs_time) if obs_time else measurement_date

                measurements.append(SourceMeasurement(
                    source_id=f"{self.get_patient_id()}_vital_{org_idx}_{comp_idx}",
                    patient_source_id=self.get_patient_id(),
                    measurement_code=code.get("code"),
                    measurement_code_system=code.get("code_system_name") or "LOINC",
                    measurement_name=code.get("display_name"),
                    value_numeric=float(value) if value else None,
                    unit=unit,
                    measurement_date=obs_date,
                    raw_data={
                        "code": code.get("code"),
                        "code_system": code.get("code_system"),
                        "display_name": code.get("display_name"),
                    },
                ))

        return measurements

    def get_lab_results(self) -> list[SourceMeasurement]:
        """Extract lab results from Results section.

        Returns:
            List of SourceMeasurement objects.
        """
        measurements: list[SourceMeasurement] = []
        section = self._get_section_by_template_id(SECTION_TEMPLATE_IDS["results"])

        if section is None:
            return measurements

        for org_idx, organizer in enumerate(self._findall("cda:entry/cda:organizer", section)):
            # Get panel code
            panel_code = self._get_code("cda:code", organizer)

            for comp_idx, component in enumerate(self._findall("cda:component/cda:observation", organizer)):
                code = self._get_code("cda:code", component)

                # Get value
                value_elem = self._find("cda:value", component)
                value_numeric = None
                value_text = None
                unit = None

                if value_elem is not None:
                    xsi_type = value_elem.get("{http://www.w3.org/2001/XMLSchema-instance}type", "")

                    if "PQ" in xsi_type:  # Physical Quantity
                        value_numeric = value_elem.get("value")
                        if value_numeric:
                            try:
                                value_numeric = float(value_numeric)
                            except ValueError:
                                value_text = value_numeric
                                value_numeric = None
                        unit = value_elem.get("unit")
                    elif "ST" in xsi_type or "CD" in xsi_type:  # String or Coded
                        value_text = value_elem.text or value_elem.get("displayName")

                # Get interpretation
                interp = self._get_code("cda:interpretationCode", component)

                # Get reference range
                ref_range = self._find("cda:referenceRange/cda:observationRange/cda:value", component)
                range_low = range_high = None
                if ref_range is not None:
                    range_low = self._get_attr("cda:low", "value", ref_range)
                    range_high = self._get_attr("cda:high", "value", ref_range)
                    if range_low:
                        try:
                            range_low = float(range_low)
                        except ValueError:
                            range_low = None
                    if range_high:
                        try:
                            range_high = float(range_high)
                        except ValueError:
                            range_high = None

                # Parse date
                obs_time = self._get_attr("cda:effectiveTime", "value", component)
                measurement_date = self._parse_date(obs_time)

                measurements.append(SourceMeasurement(
                    source_id=f"{self.get_patient_id()}_lab_{org_idx}_{comp_idx}",
                    patient_source_id=self.get_patient_id(),
                    measurement_code=code.get("code"),
                    measurement_code_system=code.get("code_system_name") or "LOINC",
                    measurement_name=code.get("display_name"),
                    value_numeric=value_numeric,
                    value_text=value_text,
                    unit=unit,
                    range_low=range_low,
                    range_high=range_high,
                    measurement_date=measurement_date,
                    abnormal_flag=interp.get("code"),
                    raw_data={
                        "code": code.get("code"),
                        "code_system": code.get("code_system"),
                        "panel_code": panel_code.get("code"),
                        "panel_name": panel_code.get("display_name"),
                        "interpretation": interp.get("display_name"),
                    },
                ))

        return measurements

    def get_procedures(self) -> list[SourceProcedure]:
        """Extract procedures from Procedures section.

        Returns:
            List of SourceProcedure objects.
        """
        procedures: list[SourceProcedure] = []
        section = self._get_section_by_template_id(SECTION_TEMPLATE_IDS["procedures"])

        if section is None:
            return procedures

        for idx, entry in enumerate(self._findall("cda:entry", section)):
            proc = self._find("cda:procedure", entry)
            if proc is None:
                proc = self._find("cda:act", entry)
            if proc is None:
                proc = self._find("cda:observation", entry)
            if proc is None:
                continue

            code = self._get_code("cda:code", proc)

            # Parse date
            eff_time = self._find("cda:effectiveTime", proc)
            procedure_date = None
            if eff_time is not None:
                time_val = eff_time.get("value")
                low_val = self._get_attr("cda:low", "value", eff_time)
                procedure_date = self._parse_date(time_val or low_val)

            # Parse status
            status_code = self._get_attr("cda:statusCode", "code", proc)
            status = ProcedureStatus.COMPLETED
            if status_code == "active":
                status = ProcedureStatus.IN_PROGRESS
            elif status_code == "cancelled" or status_code == "aborted":
                status = ProcedureStatus.CANCELLED

            # Get performer/provider
            performer = self._find("cda:performer/cda:assignedEntity/cda:assignedPerson/cda:name", proc)
            provider_name = None
            if performer is not None:
                given = self._get_text("cda:given", performer) or ""
                family = self._get_text("cda:family", performer) or ""
                provider_name = f"{given} {family}".strip() or None

            procedures.append(SourceProcedure(
                source_id=f"{self.get_patient_id()}_proc_{idx}",
                patient_source_id=self.get_patient_id(),
                procedure_code=code.get("code"),
                procedure_code_system=code.get("code_system_name") or code.get("code_system"),
                procedure_name=code.get("display_name"),
                procedure_date=procedure_date,
                status=status,
                provider_name=provider_name,
                raw_data={
                    "code": code.get("code"),
                    "code_system": code.get("code_system"),
                    "code_system_name": code.get("code_system_name"),
                    "display_name": code.get("display_name"),
                },
            ))

        return procedures

    def get_allergies(self) -> list[SourceObservation]:
        """Extract allergies from Allergies section.

        Returns:
            List of SourceObservation objects representing allergies.
        """
        observations: list[SourceObservation] = []
        section = self._get_section_by_template_id(SECTION_TEMPLATE_IDS["allergies"])

        if section is None:
            return observations

        for idx, entry in enumerate(self._findall("cda:entry", section)):
            act = self._find("cda:act", entry)
            if act is None:
                continue

            obs = self._find("cda:entryRelationship/cda:observation", act)
            if obs is None:
                continue

            # Get allergen
            participant = self._find("cda:participant/cda:participantRole/cda:playingEntity", obs)
            allergen_code = self._get_code("cda:code", participant)

            # Get reaction
            reaction_obs = self._find("cda:entryRelationship/cda:observation", obs)
            reaction_code = self._get_code("cda:value", reaction_obs) if reaction_obs else {}

            # Parse date
            eff_time = self._find("cda:effectiveTime", obs)
            onset_date = None
            if eff_time is not None:
                low = self._get_attr("cda:low", "value", eff_time)
                onset_date = self._parse_date(low)

            # Get severity
            severity_obs = None
            for rel in self._findall("cda:entryRelationship", obs):
                obs_inner = self._find("cda:observation", rel)
                if obs_inner is not None:
                    template = self._find("cda:templateId[@root='2.16.840.1.113883.10.20.22.4.8']", obs_inner)
                    if template is not None:
                        severity_obs = obs_inner
                        break

            severity = None
            if severity_obs is not None:
                sev_code = self._get_code("cda:value", severity_obs)
                severity = sev_code.get("display_name")

            observations.append(SourceObservation(
                source_id=f"{self.get_patient_id()}_allergy_{idx}",
                patient_source_id=self.get_patient_id(),
                observation_code=allergen_code.get("code") or "ALLERGY",
                observation_code_system=allergen_code.get("code_system_name") or "RxNorm",
                observation_name=allergen_code.get("display_name"),
                observation_type="allergy",
                observation_date=onset_date,
                value_text=reaction_code.get("display_name"),
                raw_data={
                    "allergen_code": allergen_code.get("code"),
                    "allergen_name": allergen_code.get("display_name"),
                    "reaction_code": reaction_code.get("code"),
                    "reaction_name": reaction_code.get("display_name"),
                    "severity": severity,
                },
            ))

        return observations


class CCDAConnector(SourceConnector):
    """Source connector for C-CDA/CDA documents.

    Extracts clinical data from C-CDA XML files into standardized
    source data models for OMOP CDM transformation.
    """

    def __init__(self, config: CCDAConnectorConfig):
        """Initialize C-CDA connector.

        Args:
            config: Connector configuration.
        """
        super().__init__(config)
        self.config: CCDAConnectorConfig = config
        self._documents: list[CCDADocument] = []
        self._loaded = False

    def _load_documents(self) -> None:
        """Load and parse all C-CDA documents."""
        if self._loaded:
            return

        self._documents = []

        # Load from file path
        if self.config.documents_path:
            path = Path(self.config.documents_path)
            if path.is_dir():
                pattern = "**/" + self.config.file_pattern if self.config.recursive else self.config.file_pattern
                for xml_file in path.glob(pattern):
                    try:
                        content = xml_file.read_text(encoding=self.config.encoding)
                        doc = CCDADocument(content, str(xml_file))
                        self._documents.append(doc)
                    except (OSError, ValueError) as e:
                        self._log_error(f"Failed to load {xml_file}: {e}")
            elif path.is_file():
                try:
                    content = path.read_text(encoding=self.config.encoding)
                    doc = CCDADocument(content, str(path))
                    self._documents.append(doc)
                except (OSError, ValueError) as e:
                    self._log_error(f"Failed to load {path}: {e}")

        # Load from string list
        for idx, xml_content in enumerate(self.config.documents):
            try:
                doc = CCDADocument(xml_content, f"document_{idx}")
                self._documents.append(doc)
            except ValueError as e:
                self._log_error(f"Failed to parse document {idx}: {e}")

        self._loaded = True

    def _log_error(self, message: str) -> None:
        """Log extraction error.

        Args:
            message: Error message.
        """
        # VP-Logging-1: Use proper logging instead of print
        logger.error(f"CCDAConnector: {message}")

    async def connect(self) -> bool:
        """Connect to data source.

        For C-CDA files, this validates the configuration.

        Returns:
            True if configuration is valid.
        """
        if not self.config.documents_path and not self.config.documents:
            return False
        return True

    async def disconnect(self) -> None:
        """Disconnect from data source.

        Clears loaded documents from memory.
        """
        self._documents = []
        self._loaded = False

    async def test_connection(self) -> bool:
        """Test connection to data source.

        Verifies at least one document can be loaded.

        Returns:
            True if documents can be loaded.
        """
        self._load_documents()
        return len(self._documents) > 0

    async def extract_patients(self) -> AsyncIterator[SourcePatient]:
        """Extract patients from C-CDA documents.

        Each C-CDA document contains one patient's data.

        Yields:
            SourcePatient objects.
        """
        self._load_documents()
        seen_patients: set[str] = set()

        for doc in self._documents:
            try:
                patient = doc.get_patient_demographics()
                if patient.source_id not in seen_patients:
                    seen_patients.add(patient.source_id)
                    yield patient
            except Exception as e:
                self._log_error(f"Failed to extract patient from {doc.source_file}: {e}")

    async def extract_visits(self, patient_source_id: str | None = None) -> AsyncIterator[SourceVisit]:
        """Extract visits/encounters from C-CDA documents.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceVisit objects.
        """
        self._load_documents()

        for doc in self._documents:
            if patient_source_id and doc.get_patient_id() != patient_source_id:
                continue

            try:
                for visit in doc.get_encounters():
                    yield visit
            except Exception as e:
                self._log_error(f"Failed to extract visits from {doc.source_file}: {e}")

    async def extract_conditions(self, patient_source_id: str | None = None) -> AsyncIterator[SourceCondition]:
        """Extract conditions/problems from C-CDA documents.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceCondition objects.
        """
        self._load_documents()

        for doc in self._documents:
            if patient_source_id and doc.get_patient_id() != patient_source_id:
                continue

            try:
                for condition in doc.get_problems():
                    yield condition
            except Exception as e:
                self._log_error(f"Failed to extract conditions from {doc.source_file}: {e}")

    async def extract_drugs(self, patient_source_id: str | None = None) -> AsyncIterator[SourceDrug]:
        """Extract medications from C-CDA documents.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceDrug objects.
        """
        self._load_documents()

        for doc in self._documents:
            if patient_source_id and doc.get_patient_id() != patient_source_id:
                continue

            try:
                for drug in doc.get_medications():
                    yield drug
            except Exception as e:
                self._log_error(f"Failed to extract drugs from {doc.source_file}: {e}")

    async def extract_procedures(self, patient_source_id: str | None = None) -> AsyncIterator[SourceProcedure]:
        """Extract procedures from C-CDA documents.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceProcedure objects.
        """
        self._load_documents()

        for doc in self._documents:
            if patient_source_id and doc.get_patient_id() != patient_source_id:
                continue

            try:
                for procedure in doc.get_procedures():
                    yield procedure
            except Exception as e:
                self._log_error(f"Failed to extract procedures from {doc.source_file}: {e}")

    async def extract_measurements(self, patient_source_id: str | None = None) -> AsyncIterator[SourceMeasurement]:
        """Extract measurements (vital signs + labs) from C-CDA documents.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceMeasurement objects.
        """
        self._load_documents()

        for doc in self._documents:
            if patient_source_id and doc.get_patient_id() != patient_source_id:
                continue

            try:
                # Vital signs
                for measurement in doc.get_vital_signs():
                    yield measurement

                # Lab results
                for measurement in doc.get_lab_results():
                    yield measurement
            except Exception as e:
                self._log_error(f"Failed to extract measurements from {doc.source_file}: {e}")

    async def extract_observations(self, patient_source_id: str | None = None) -> AsyncIterator[SourceObservation]:
        """Extract observations (allergies, social history) from C-CDA documents.

        Args:
            patient_source_id: Optional patient ID filter.

        Yields:
            SourceObservation objects.
        """
        self._load_documents()

        for doc in self._documents:
            if patient_source_id and doc.get_patient_id() != patient_source_id:
                continue

            try:
                for observation in doc.get_allergies():
                    yield observation
            except Exception as e:
                self._log_error(f"Failed to extract observations from {doc.source_file}: {e}")

    async def get_extraction_stats(self) -> ExtractionResult:
        """Get extraction statistics.

        Returns:
            ExtractionResult with counts from all documents.
        """
        self._load_documents()

        result = ExtractionResult()
        result.documents_processed = len(self._documents)

        for doc in self._documents:
            result.patients_extracted += 1  # One patient per document
            result.visits_extracted += len(doc.get_encounters())
            result.conditions_extracted += len(doc.get_problems())
            result.drugs_extracted += len(doc.get_medications())
            result.procedures_extracted += len(doc.get_procedures())
            result.measurements_extracted += len(doc.get_vital_signs()) + len(doc.get_lab_results())
            result.observations_extracted += len(doc.get_allergies())

        return result
