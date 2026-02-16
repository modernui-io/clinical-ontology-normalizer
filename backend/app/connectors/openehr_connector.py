"""OpenEHR Source Connector.

Extracts clinical data from OpenEHR servers using the OpenEHR REST API.
Parses COMPOSITION JSON into standardized Source* intermediate models.

Supported Archetypes:
    - EVALUATION.problem_diagnosis.v1 -> SourceCondition
    - INSTRUCTION.medication_order.v3 -> SourceDrug
    - OBSERVATION.laboratory_test_result.v1 -> SourceMeasurement
    - OBSERVATION.blood_pressure.v2 -> SourceMeasurement (systolic + diastolic)
    - OBSERVATION.body_temperature/weight/height/pulse/pulse_oximetry -> SourceMeasurement
    - ACTION.procedure.v1 -> SourceProcedure
    - EVALUATION.adverse_reaction_risk.v1 -> SourceObservation (allergy)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from app.connectors.base import (
    ConditionStatus,
    ConnectorConfig,
    ConnectorType,
    DrugStatus,
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
)

logger = logging.getLogger(__name__)


@dataclass
class OpenEHRConnectorConfig(ConnectorConfig):
    """Configuration for OpenEHR connector.

    Attributes:
        base_url: OpenEHR server base URL (e.g., https://server.com/ehrbase/rest).
        auth_token: Bearer token for authentication.
        page_size: Number of compositions per page (default: 50).
        timeout: Request timeout in seconds (default: 30).
    """

    base_url: str = ""
    auth_token: str | None = None
    page_size: int = 50
    timeout: int = 30

    def __post_init__(self) -> None:
        self.connector_type = ConnectorType.OPENEHR


class OpenEHRConnector(SourceConnector):
    """Source connector for OpenEHR servers.

    Extracts clinical data from OpenEHR servers using the standard REST API.
    Parses COMPOSITION entries and maps RM data types to Source* models.
    """

    def __init__(self, config: OpenEHRConnectorConfig):
        super().__init__(config)
        self.config: OpenEHRConnectorConfig = config
        self._client: httpx.AsyncClient | None = None

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.OPENEHR

    @property
    def source_system(self) -> str:
        return f"openehr:{self.config.base_url}"

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.config.auth_token:
            token = self.config.auth_token
            if not token.lower().startswith("bearer "):
                token = f"Bearer {token}"
            headers["Authorization"] = token
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=self._get_headers(),
                timeout=self.config.timeout,
            )
        return self._client

    async def connect(self) -> bool:
        if not self.config.base_url:
            return False
        try:
            client = await self._get_client()
            response = await client.get("/definition/template/adl1.4")
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to connect to OpenEHR server: {e}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def test_connection(self) -> tuple[bool, str]:
        try:
            connected = await self.connect()
            if connected:
                return True, "Connected to OpenEHR server"
            return False, "Could not connect to OpenEHR server"
        except Exception as e:
            return False, str(e)

    # -------------------------------------------------------------------------
    # RM Data Type Parsers
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_dv_coded_text(
        dv: dict[str, Any] | None,
    ) -> tuple[str | None, str | None, str | None]:
        """Parse DV_CODED_TEXT -> (code, system, display)."""
        if not dv:
            return None, None, None
        display = dv.get("value")
        defining_code = dv.get("defining_code", {})
        code = defining_code.get("code_string")
        terminology = defining_code.get("terminology_id", {}).get("value")
        return code, terminology, display

    @staticmethod
    def parse_dv_quantity(dv: dict[str, Any] | None) -> tuple[float | None, str | None]:
        """Parse DV_QUANTITY -> (magnitude, units)."""
        if not dv:
            return None, None
        return dv.get("magnitude"), dv.get("units")

    @staticmethod
    def parse_dv_date_time(dv: dict[str, Any] | None) -> datetime | None:
        """Parse DV_DATE_TIME -> datetime."""
        if not dv:
            return None
        value = dv.get("value")
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_dv_text(dv: dict[str, Any] | None) -> str | None:
        """Parse DV_TEXT -> string value."""
        if not dv:
            return None
        return dv.get("value")

    # -------------------------------------------------------------------------
    # Composition Parsing
    # -------------------------------------------------------------------------

    def _get_content_entries(
        self, composition: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract content entries from a COMPOSITION."""
        return composition.get("content", [])

    def _get_archetype_id(self, entry: dict[str, Any]) -> str | None:
        """Extract the archetype concept name from archetype_node_id."""
        node_id = entry.get("archetype_node_id", "")
        # e.g., openEHR-EHR-EVALUATION.problem_diagnosis.v1
        # -> EVALUATION.problem_diagnosis.v1
        parts = node_id.split("-")
        if len(parts) >= 4:
            return "-".join(parts[2:])  # e.g., EVALUATION.problem_diagnosis.v1
        return node_id

    def _get_first_event_data(
        self, entry: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Get the data items from the first event in OBSERVATION.data.events."""
        data = entry.get("data", {})
        events = data.get("events", [])
        if events:
            return events[0].get("data", {})
        return None

    def _find_element_by_name(
        self, items: list[dict[str, Any]], name: str
    ) -> dict[str, Any] | None:
        """Find an ELEMENT in items list by its name value."""
        for item in items:
            item_name = item.get("name", {}).get("value", "")
            if item_name.lower() == name.lower():
                return item
        return None

    # -------------------------------------------------------------------------
    # Extract methods (SourceConnector interface)
    # -------------------------------------------------------------------------

    async def extract_patients(self) -> AsyncIterator[SourcePatient]:
        """Extract patients from OpenEHR server.

        OpenEHR stores patients as EHR objects with demographic references.
        """
        client = await self._get_client()
        try:
            response = await client.get("/ehr")
            if response.status_code == 200:
                ehrs = response.json()
                ehr_list = ehrs if isinstance(ehrs, list) else ehrs.get("items", [])
                for ehr in ehr_list:
                    ehr_id = ehr.get("ehr_id", {}).get("value", "")
                    yield SourcePatient(
                        source_id=ehr_id,
                        source_system=self.source_system,
                        raw_data=ehr,
                    )
        except Exception as e:
            logger.error(f"Error extracting patients: {e}")

    async def extract_visits(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceVisit]:
        return
        yield  # type: ignore[misc]

    async def extract_conditions(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceCondition]:
        """Extract conditions from EVALUATION.problem_diagnosis.v1 archetypes."""
        if not patient_source_id:
            return

        client = await self._get_client()
        try:
            aql = (
                "SELECT c FROM EHR e CONTAINS COMPOSITION c "
                "CONTAINS EVALUATION e2[openEHR-EHR-EVALUATION.problem_diagnosis.v1] "
                f"WHERE e.ehr_id/value = '{patient_source_id}'"
            )
            response = await client.post("/query/aql", json={"q": aql})
            if response.status_code != 200:
                return

            result = response.json()
            for row in result.get("rows", []):
                comp = row[0] if isinstance(row, list) else row
                for entry in self._get_content_entries(comp):
                    archetype = self._get_archetype_id(entry)
                    if archetype and "problem_diagnosis" in archetype:
                        condition = self._parse_condition_entry(
                            entry, patient_source_id
                        )
                        if condition:
                            yield condition
        except Exception as e:
            logger.error(f"Error extracting conditions: {e}")

    def _parse_condition_entry(
        self, entry: dict[str, Any], patient_source_id: str
    ) -> SourceCondition | None:
        """Parse a problem_diagnosis entry into SourceCondition."""
        items = entry.get("data", {}).get("items", [])

        # Find Problem/Diagnosis name
        name_elem = self._find_element_by_name(items, "Problem/Diagnosis name")
        if not name_elem:
            return None

        code, system, display = self.parse_dv_coded_text(name_elem.get("value"))
        if not display:
            return None

        # Find onset date
        onset_elem = self._find_element_by_name(items, "Date/time of onset")
        onset = self.parse_dv_date_time(onset_elem.get("value") if onset_elem else None)

        return SourceCondition(
            source_id=entry.get("archetype_node_id", ""),
            source_system=self.source_system,
            patient_source_id=patient_source_id,
            code=code,
            code_system=system,
            display_text=display,
            status=ConditionStatus.ACTIVE,
            onset_datetime=onset,
            raw_data=entry,
        )

    async def extract_drugs(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceDrug]:
        """Extract medications from INSTRUCTION.medication_order.v3 archetypes."""
        if not patient_source_id:
            return

        client = await self._get_client()
        try:
            aql = (
                "SELECT c FROM EHR e CONTAINS COMPOSITION c "
                "CONTAINS INSTRUCTION i[openEHR-EHR-INSTRUCTION.medication_order.v3] "
                f"WHERE e.ehr_id/value = '{patient_source_id}'"
            )
            response = await client.post("/query/aql", json={"q": aql})
            if response.status_code != 200:
                return

            result = response.json()
            for row in result.get("rows", []):
                comp = row[0] if isinstance(row, list) else row
                for entry in self._get_content_entries(comp):
                    archetype = self._get_archetype_id(entry)
                    if archetype and "medication_order" in archetype:
                        drug = self._parse_medication_entry(
                            entry, patient_source_id
                        )
                        if drug:
                            yield drug
        except Exception as e:
            logger.error(f"Error extracting drugs: {e}")

    def _parse_medication_entry(
        self, entry: dict[str, Any], patient_source_id: str
    ) -> SourceDrug | None:
        """Parse a medication_order entry into SourceDrug."""
        # Activities contain the medication details
        activities = entry.get("activities", [])
        if not activities:
            return None

        description = activities[0].get("description", {})
        items = description.get("items", [])

        # Find Medication item
        med_elem = self._find_element_by_name(items, "Medication item")
        if not med_elem:
            return None

        code, system, display = self.parse_dv_coded_text(med_elem.get("value"))
        if not display:
            return None

        # Find dosage
        dose_elem = self._find_element_by_name(items, "Dose amount")
        dose_value, dose_unit = self.parse_dv_quantity(
            dose_elem.get("value") if dose_elem else None
        )

        # Find route
        route_elem = self._find_element_by_name(items, "Route")
        route_text = self.parse_dv_text(route_elem.get("value") if route_elem else None)

        return SourceDrug(
            source_id=entry.get("archetype_node_id", ""),
            source_system=self.source_system,
            patient_source_id=patient_source_id,
            code=code,
            code_system=system,
            display_text=display,
            status=DrugStatus.ACTIVE,
            dose_value=dose_value,
            dose_unit=dose_unit,
            route=route_text,
            raw_data=entry,
        )

    async def extract_procedures(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceProcedure]:
        """Extract procedures from ACTION.procedure.v1 archetypes."""
        if not patient_source_id:
            return

        client = await self._get_client()
        try:
            aql = (
                "SELECT c FROM EHR e CONTAINS COMPOSITION c "
                "CONTAINS ACTION a[openEHR-EHR-ACTION.procedure.v1] "
                f"WHERE e.ehr_id/value = '{patient_source_id}'"
            )
            response = await client.post("/query/aql", json={"q": aql})
            if response.status_code != 200:
                return

            result = response.json()
            for row in result.get("rows", []):
                comp = row[0] if isinstance(row, list) else row
                for entry in self._get_content_entries(comp):
                    archetype = self._get_archetype_id(entry)
                    if archetype and "procedure" in archetype:
                        procedure = self._parse_procedure_entry(
                            entry, patient_source_id
                        )
                        if procedure:
                            yield procedure
        except Exception as e:
            logger.error(f"Error extracting procedures: {e}")

    def _parse_procedure_entry(
        self, entry: dict[str, Any], patient_source_id: str
    ) -> SourceProcedure | None:
        """Parse a procedure entry into SourceProcedure."""
        description = entry.get("description", {})
        items = description.get("items", [])

        # Find Procedure name
        name_elem = self._find_element_by_name(items, "Procedure name")
        if not name_elem:
            return None

        code, system, display = self.parse_dv_coded_text(name_elem.get("value"))
        if not display:
            return None

        # Find date
        time_data = entry.get("time", {})
        performed = self.parse_dv_date_time(time_data)

        return SourceProcedure(
            source_id=entry.get("archetype_node_id", ""),
            source_system=self.source_system,
            patient_source_id=patient_source_id,
            code=code,
            code_system=system,
            display_text=display,
            status=ProcedureStatus.COMPLETED,
            performed_datetime=performed,
            raw_data=entry,
        )

    async def extract_measurements(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceMeasurement]:
        """Extract measurements from OBSERVATION archetypes."""
        if not patient_source_id:
            return

        client = await self._get_client()
        try:
            aql = (
                "SELECT c FROM EHR e CONTAINS COMPOSITION c "
                "CONTAINS OBSERVATION o "
                f"WHERE e.ehr_id/value = '{patient_source_id}'"
            )
            response = await client.post("/query/aql", json={"q": aql})
            if response.status_code != 200:
                return

            result = response.json()
            for row in result.get("rows", []):
                comp = row[0] if isinstance(row, list) else row
                for entry in self._get_content_entries(comp):
                    archetype = self._get_archetype_id(entry)
                    if not archetype:
                        continue
                    measurements = self._parse_observation_entry(
                        entry, archetype, patient_source_id
                    )
                    for m in measurements:
                        yield m
        except Exception as e:
            logger.error(f"Error extracting measurements: {e}")

    def _parse_observation_entry(
        self,
        entry: dict[str, Any],
        archetype: str,
        patient_source_id: str,
    ) -> list[SourceMeasurement]:
        """Parse an OBSERVATION entry into one or more SourceMeasurements."""
        event_data = self._get_first_event_data(entry)
        if not event_data:
            return []

        items = event_data.get("items", [])
        measurements: list[SourceMeasurement] = []

        if "blood_pressure" in archetype:
            # Blood pressure produces two measurements
            for name in ("Systolic", "Diastolic"):
                elem = self._find_element_by_name(items, name)
                if elem:
                    mag, unit = self.parse_dv_quantity(elem.get("value"))
                    measurements.append(
                        SourceMeasurement(
                            source_id=f"{entry.get('archetype_node_id', '')}:{name.lower()}",
                            source_system=self.source_system,
                            patient_source_id=patient_source_id,
                            code=None,
                            code_system=None,
                            display_text=f"Blood Pressure - {name}",
                            value_numeric=mag,
                            unit=unit,
                            raw_data=entry,
                        )
                    )
        elif "laboratory_test_result" in archetype:
            # Lab results may have multiple analytes
            for item in items:
                if item.get("_type") == "CLUSTER":
                    for sub_item in item.get("items", []):
                        name_text = sub_item.get("name", {}).get("value", "")
                        value_node = sub_item.get("value", {})
                        if value_node.get("_type") == "DV_QUANTITY":
                            mag, unit = self.parse_dv_quantity(value_node)
                            measurements.append(
                                SourceMeasurement(
                                    source_id=entry.get("archetype_node_id", ""),
                                    source_system=self.source_system,
                                    patient_source_id=patient_source_id,
                                    display_text=name_text or "Lab Result",
                                    value_numeric=mag,
                                    unit=unit,
                                    raw_data=entry,
                                )
                            )
                        elif value_node.get("_type") == "DV_CODED_TEXT":
                            _, _, disp = self.parse_dv_coded_text(value_node)
                            measurements.append(
                                SourceMeasurement(
                                    source_id=entry.get("archetype_node_id", ""),
                                    source_system=self.source_system,
                                    patient_source_id=patient_source_id,
                                    display_text=name_text or "Lab Result",
                                    value_text=disp,
                                    raw_data=entry,
                                )
                            )
        else:
            # Single-value observations (temperature, weight, height, pulse, SpO2)
            for item in items:
                value_node = item.get("value", {})
                if value_node.get("_type") == "DV_QUANTITY":
                    mag, unit = self.parse_dv_quantity(value_node)
                    display = item.get("name", {}).get("value", archetype)
                    measurements.append(
                        SourceMeasurement(
                            source_id=entry.get("archetype_node_id", ""),
                            source_system=self.source_system,
                            patient_source_id=patient_source_id,
                            display_text=display,
                            value_numeric=mag,
                            unit=unit,
                            raw_data=entry,
                        )
                    )
                    break  # Single primary value

        return measurements

    async def extract_observations(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceObservation]:
        """Extract allergies from EVALUATION.adverse_reaction_risk.v1 archetypes."""
        if not patient_source_id:
            return

        client = await self._get_client()
        try:
            aql = (
                "SELECT c FROM EHR e CONTAINS COMPOSITION c "
                "CONTAINS EVALUATION ev[openEHR-EHR-EVALUATION.adverse_reaction_risk.v1] "
                f"WHERE e.ehr_id/value = '{patient_source_id}'"
            )
            response = await client.post("/query/aql", json={"q": aql})
            if response.status_code != 200:
                return

            result = response.json()
            for row in result.get("rows", []):
                comp = row[0] if isinstance(row, list) else row
                for entry in self._get_content_entries(comp):
                    archetype = self._get_archetype_id(entry)
                    if archetype and "adverse_reaction_risk" in archetype:
                        obs = self._parse_allergy_entry(entry, patient_source_id)
                        if obs:
                            yield obs
        except Exception as e:
            logger.error(f"Error extracting observations: {e}")

    def _parse_allergy_entry(
        self, entry: dict[str, Any], patient_source_id: str
    ) -> SourceObservation | None:
        """Parse an adverse_reaction_risk entry into SourceObservation."""
        items = entry.get("data", {}).get("items", [])

        # Find Substance
        substance_elem = self._find_element_by_name(items, "Substance")
        if not substance_elem:
            return None

        code, system, display = self.parse_dv_coded_text(substance_elem.get("value"))
        if not display:
            return None

        # Find reaction manifestation
        reaction_text = None
        for item in items:
            if item.get("_type") == "CLUSTER" and "Reaction event" in item.get("name", {}).get("value", ""):
                for sub in item.get("items", []):
                    if "Manifestation" in sub.get("name", {}).get("value", ""):
                        _, _, reaction_text = self.parse_dv_coded_text(sub.get("value"))
                        break

        return SourceObservation(
            source_id=entry.get("archetype_node_id", ""),
            source_system=self.source_system,
            patient_source_id=patient_source_id,
            code=code,
            code_system=system,
            display_text=display,
            category="allergy",
            reaction=reaction_text,
            raw_data=entry,
        )
