"""CSV/Flat File Source Connector.

Reads clinical data from CSV files and transforms to standardized format.
Supports multiple CSV files (one per resource type) or a single combined file.

Usage:
    config = CSVConnectorConfig(
        patients_file="patients.csv",
        conditions_file="diagnoses.csv",
        drugs_file="medications.csv",
    )
    connector = CSVConnector(config)

    async with connector:
        async for patient in connector.extract_patients():
            print(patient.full_name)
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncIterator

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
    VisitType,
)
from app.connectors.concept_mappings import (
    DEFAULT_CODE_SYSTEMS,
    parse_condition_status,
    parse_drug_status,
    parse_gender,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CSV Connector Configuration
# ============================================================================


@dataclass
class CSVConnectorConfig(ConnectorConfig):
    """Configuration for CSV connector.

    Specify paths to CSV files for each resource type.
    Files can be absolute paths or relative to a base directory.
    """

    connector_type: ConnectorType = ConnectorType.CSV

    # Base directory for relative paths
    base_dir: Path | str | None = None

    # File paths (relative to base_dir or absolute)
    patients_file: Path | str | None = None
    visits_file: Path | str | None = None
    conditions_file: Path | str | None = None
    drugs_file: Path | str | None = None
    procedures_file: Path | str | None = None
    measurements_file: Path | str | None = None
    observations_file: Path | str | None = None

    # CSV parsing options
    delimiter: str = ","
    encoding: str = "utf-8"
    has_header: bool = True
    skip_rows: int = 0

    # Column mappings (if column names differ from expected)
    # Maps expected field name -> actual column name in CSV
    column_mappings: dict[str, dict[str, str]] = field(default_factory=dict)

    # Date format for parsing
    date_format: str = "%Y-%m-%d"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"

    def get_file_path(self, file_attr: str) -> Path | None:
        """Get resolved file path."""
        file_path = getattr(self, file_attr, None)
        if file_path is None:
            return None

        path = Path(file_path)
        if not path.is_absolute() and self.base_dir:
            path = Path(self.base_dir) / path

        return path if path.exists() else None


# ============================================================================
# Default Column Mappings
# ============================================================================

# Expected columns for each resource type
# Actual CSVs may have different column names - use column_mappings to map

DEFAULT_PATIENT_COLUMNS = {
    "source_id": ["patient_id", "id", "mrn", "patientid"],
    "given_name": ["first_name", "given_name", "firstname", "given"],
    "family_name": ["last_name", "family_name", "lastname", "family", "surname"],
    "birth_date": ["dob", "birth_date", "birthdate", "date_of_birth"],
    "gender": ["sex", "gender"],
    "race": ["race"],
    "ethnicity": ["ethnicity"],
    "mrn": ["mrn", "medical_record_number"],
    "address_line1": ["address", "address1", "street"],
    "city": ["city"],
    "state": ["state", "province"],
    "postal_code": ["zip", "postal_code", "zipcode"],
    "phone": ["phone", "telephone"],
    "email": ["email"],
    "deceased": ["deceased", "is_deceased"],
    "death_date": ["death_date", "date_of_death"],
}

DEFAULT_CONDITION_COLUMNS = {
    "source_id": ["condition_id", "diagnosis_id", "id"],
    "patient_source_id": ["patient_id", "patientid"],
    "visit_source_id": ["visit_id", "encounter_id"],
    "code": ["icd_code", "code", "diagnosis_code", "icd10"],
    "code_system": ["code_system", "vocabulary"],
    "display_text": ["description", "display", "diagnosis_name", "condition_name"],
    "status": ["status", "clinical_status"],
    "onset_datetime": ["onset_date", "diagnosis_date", "start_date"],
    "category": ["category", "type"],
}

DEFAULT_DRUG_COLUMNS = {
    "source_id": ["medication_id", "drug_id", "id", "rx_id"],
    "patient_source_id": ["patient_id", "patientid"],
    "visit_source_id": ["visit_id", "encounter_id"],
    "code": ["ndc", "rxnorm", "code", "drug_code"],
    "code_system": ["code_system", "vocabulary"],
    "display_text": ["drug_name", "medication_name", "name", "description"],
    "status": ["status"],
    "start_datetime": ["start_date", "order_date", "prescribed_date"],
    "end_datetime": ["end_date", "stop_date"],
    "dose_value": ["dose", "dose_value", "strength"],
    "dose_unit": ["dose_unit", "unit"],
    "route": ["route", "route_of_admin"],
    "frequency": ["frequency", "sig"],
    "quantity": ["quantity", "qty"],
    "days_supply": ["days_supply", "supply_days"],
}

DEFAULT_PROCEDURE_COLUMNS = {
    "source_id": ["procedure_id", "id"],
    "patient_source_id": ["patient_id", "patientid"],
    "visit_source_id": ["visit_id", "encounter_id"],
    "code": ["cpt_code", "procedure_code", "code", "icd10pcs"],
    "code_system": ["code_system", "vocabulary"],
    "display_text": ["procedure_name", "description", "name"],
    "status": ["status"],
    "performed_datetime": ["procedure_date", "performed_date", "date"],
}

DEFAULT_MEASUREMENT_COLUMNS = {
    "source_id": ["measurement_id", "lab_id", "result_id", "id"],
    "patient_source_id": ["patient_id", "patientid"],
    "visit_source_id": ["visit_id", "encounter_id"],
    "code": ["loinc", "code", "test_code"],
    "code_system": ["code_system", "vocabulary"],
    "display_text": ["test_name", "name", "description"],
    "value_numeric": ["value", "result", "numeric_value"],
    "value_text": ["text_value", "value_text"],
    "unit": ["unit", "units"],
    "range_low": ["reference_low", "normal_low", "range_low"],
    "range_high": ["reference_high", "normal_high", "range_high"],
    "interpretation": ["interpretation", "flag", "abnormal_flag"],
    "effective_datetime": ["result_date", "collection_date", "date"],
}


# ============================================================================
# CSV Connector
# ============================================================================


class CSVConnector(SourceConnector):
    """Source connector for CSV/flat files.

    Reads clinical data from CSV files and yields standardized records.
    Supports flexible column mappings and date formats.
    """

    def __init__(self, config: CSVConnectorConfig):
        """Initialize CSV connector.

        Args:
            config: CSV connector configuration
        """
        super().__init__(config)
        self.csv_config = config
        self._source_system = config.name or "csv"

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.CSV

    @property
    def source_system(self) -> str:
        return self._source_system

    # -------------------------------------------------------------------------
    # Connection (no-op for CSV)
    # -------------------------------------------------------------------------

    async def connect(self) -> bool:
        """Verify CSV files exist."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """No-op for CSV."""
        self._connected = False

    async def test_connection(self) -> tuple[bool, str]:
        """Test that CSV files exist and are readable."""
        files_found = []
        files_missing = []

        for attr in [
            "patients_file",
            "visits_file",
            "conditions_file",
            "drugs_file",
            "procedures_file",
            "measurements_file",
            "observations_file",
        ]:
            path = self.csv_config.get_file_path(attr)
            if path:
                if path.exists():
                    files_found.append(path.name)
                else:
                    files_missing.append(getattr(self.csv_config, attr))

        if files_missing:
            return False, f"Missing files: {files_missing}"

        if not files_found:
            return False, "No CSV files configured"

        return True, f"Found {len(files_found)} CSV files"

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _find_column(
        self, headers: list[str], field_name: str, default_mappings: dict[str, list[str]]
    ) -> str | None:
        """Find the actual column name for a field.

        Args:
            headers: List of column headers from CSV
            field_name: Expected field name
            default_mappings: Default column name mappings

        Returns:
            Actual column name or None if not found
        """
        headers_lower = [h.lower().strip() for h in headers]

        # Check custom mappings first
        resource_mappings = self.csv_config.column_mappings.get(field_name, {})
        if field_name in resource_mappings:
            mapped_name = resource_mappings[field_name].lower()
            if mapped_name in headers_lower:
                return headers[headers_lower.index(mapped_name)]

        # Check default mappings
        possible_names = default_mappings.get(field_name, [field_name])
        for name in possible_names:
            if name.lower() in headers_lower:
                return headers[headers_lower.index(name.lower())]

        return None

    def _get_value(self, row: dict[str, str], column: str | None) -> str | None:
        """Get value from row, handling None columns."""
        if column is None:
            return None
        value = row.get(column, "").strip()
        return value if value else None

    def _parse_date(self, value: str | None) -> date | None:
        """Parse a date string."""
        if not value:
            return None
        try:
            return datetime.strptime(value, self.csv_config.date_format).date()
        except ValueError:
            # Try common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"]:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse a datetime string."""
        if not value:
            return None
        try:
            return datetime.strptime(value, self.csv_config.datetime_format)
        except ValueError:
            # Try common formats
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%m/%d/%Y %H:%M",
                "%Y-%m-%d",
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return None

    def _parse_float(self, value: str | None) -> float | None:
        """Parse a float value."""
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_int(self, value: str | None) -> int | None:
        """Parse an int value."""
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    def _parse_bool(self, value: str | None) -> bool:
        """Parse a boolean value."""
        if not value:
            return False
        return value.lower() in ("true", "1", "yes", "y", "t")

    def _parse_gender(self, value: str | None) -> Gender:
        """Parse gender value."""
        return parse_gender(value)

    def _parse_condition_status(self, value: str | None) -> ConditionStatus:
        """Parse condition status."""
        return parse_condition_status(value)

    def _parse_drug_status(self, value: str | None) -> DrugStatus:
        """Parse drug status."""
        return parse_drug_status(value)

    def _read_csv(self, file_path: Path) -> list[dict[str, str]]:
        """Read CSV file and return list of row dicts."""
        rows = []
        with open(file_path, "r", encoding=self.csv_config.encoding) as f:
            # Skip rows if configured
            for _ in range(self.csv_config.skip_rows):
                next(f, None)

            reader = csv.DictReader(f, delimiter=self.csv_config.delimiter)
            for row in reader:
                rows.append(row)

        return rows

    # -------------------------------------------------------------------------
    # Extraction Methods
    # -------------------------------------------------------------------------

    async def extract_patients(self) -> AsyncIterator[SourcePatient]:
        """Extract patients from CSV file."""
        file_path = self.csv_config.get_file_path("patients_file")
        if not file_path:
            return

        rows = self._read_csv(file_path)
        if not rows:
            return

        headers = list(rows[0].keys())
        col = lambda field: self._find_column(headers, field, DEFAULT_PATIENT_COLUMNS)

        for row in rows:
            try:
                patient = SourcePatient(
                    source_id=self._get_value(row, col("source_id")) or "",
                    source_system=self.source_system,
                    raw_data=dict(row),
                    given_name=self._get_value(row, col("given_name")),
                    family_name=self._get_value(row, col("family_name")),
                    birth_date=self._parse_date(self._get_value(row, col("birth_date"))),
                    gender=self._parse_gender(self._get_value(row, col("gender"))),
                    race=self._get_value(row, col("race")),
                    ethnicity=self._get_value(row, col("ethnicity")),
                    mrn=self._get_value(row, col("mrn")),
                    address_line1=self._get_value(row, col("address_line1")),
                    city=self._get_value(row, col("city")),
                    state=self._get_value(row, col("state")),
                    postal_code=self._get_value(row, col("postal_code")),
                    phone=self._get_value(row, col("phone")),
                    email=self._get_value(row, col("email")),
                    deceased=self._parse_bool(self._get_value(row, col("deceased"))),
                    death_date=self._parse_date(self._get_value(row, col("death_date"))),
                )
                if patient.source_id:
                    yield patient
            except Exception as e:
                logger.warning(f"Error parsing patient row: {e}")
                if not self.csv_config.skip_on_error:
                    raise

    async def extract_visits(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceVisit]:
        """Extract visits from CSV file."""
        file_path = self.csv_config.get_file_path("visits_file")
        if not file_path:
            return

        rows = self._read_csv(file_path)
        if not rows:
            return

        headers = list(rows[0].keys())

        visit_columns = {
            "source_id": ["visit_id", "encounter_id", "id"],
            "patient_source_id": ["patient_id", "patientid"],
            "visit_type": ["visit_type", "encounter_type", "type"],
            "start_datetime": ["admission_date", "start_date", "visit_date"],
            "end_datetime": ["discharge_date", "end_date"],
            "facility_name": ["facility", "hospital", "clinic"],
        }

        col = lambda field: self._find_column(headers, field, visit_columns)

        for row in rows:
            try:
                pid = self._get_value(row, col("patient_source_id"))
                if patient_source_id and pid != patient_source_id:
                    continue

                visit = SourceVisit(
                    source_id=self._get_value(row, col("source_id")) or "",
                    source_system=self.source_system,
                    raw_data=dict(row),
                    patient_source_id=pid or "",
                    start_datetime=self._parse_datetime(
                        self._get_value(row, col("start_datetime"))
                    ),
                    end_datetime=self._parse_datetime(
                        self._get_value(row, col("end_datetime"))
                    ),
                    facility_name=self._get_value(row, col("facility_name")),
                )
                if visit.source_id:
                    yield visit
            except Exception as e:
                logger.warning(f"Error parsing visit row: {e}")
                if not self.csv_config.skip_on_error:
                    raise

    async def extract_conditions(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceCondition]:
        """Extract conditions from CSV file."""
        file_path = self.csv_config.get_file_path("conditions_file")
        if not file_path:
            return

        rows = self._read_csv(file_path)
        if not rows:
            return

        headers = list(rows[0].keys())
        col = lambda field: self._find_column(headers, field, DEFAULT_CONDITION_COLUMNS)

        for row in rows:
            try:
                pid = self._get_value(row, col("patient_source_id"))
                if patient_source_id and pid != patient_source_id:
                    continue

                condition = SourceCondition(
                    source_id=self._get_value(row, col("source_id")) or "",
                    source_system=self.source_system,
                    raw_data=dict(row),
                    patient_source_id=pid or "",
                    visit_source_id=self._get_value(row, col("visit_source_id")),
                    code=self._get_value(row, col("code")),
                    code_system=self._get_value(row, col("code_system")) or DEFAULT_CODE_SYSTEMS["condition"],
                    display_text=self._get_value(row, col("display_text")),
                    status=self._parse_condition_status(
                        self._get_value(row, col("status"))
                    ),
                    onset_datetime=self._parse_datetime(
                        self._get_value(row, col("onset_datetime"))
                    ),
                    category=self._get_value(row, col("category")),
                )
                if condition.source_id:
                    yield condition
            except Exception as e:
                logger.warning(f"Error parsing condition row: {e}")
                if not self.csv_config.skip_on_error:
                    raise

    async def extract_drugs(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceDrug]:
        """Extract drugs/medications from CSV file."""
        file_path = self.csv_config.get_file_path("drugs_file")
        if not file_path:
            return

        rows = self._read_csv(file_path)
        if not rows:
            return

        headers = list(rows[0].keys())
        col = lambda field: self._find_column(headers, field, DEFAULT_DRUG_COLUMNS)

        for row in rows:
            try:
                pid = self._get_value(row, col("patient_source_id"))
                if patient_source_id and pid != patient_source_id:
                    continue

                drug = SourceDrug(
                    source_id=self._get_value(row, col("source_id")) or "",
                    source_system=self.source_system,
                    raw_data=dict(row),
                    patient_source_id=pid or "",
                    visit_source_id=self._get_value(row, col("visit_source_id")),
                    code=self._get_value(row, col("code")),
                    code_system=self._get_value(row, col("code_system")) or DEFAULT_CODE_SYSTEMS["drug"],
                    display_text=self._get_value(row, col("display_text")),
                    status=self._parse_drug_status(self._get_value(row, col("status"))),
                    start_datetime=self._parse_datetime(
                        self._get_value(row, col("start_datetime"))
                    ),
                    end_datetime=self._parse_datetime(
                        self._get_value(row, col("end_datetime"))
                    ),
                    dose_value=self._parse_float(self._get_value(row, col("dose_value"))),
                    dose_unit=self._get_value(row, col("dose_unit")),
                    route=self._get_value(row, col("route")),
                    frequency=self._get_value(row, col("frequency")),
                    quantity=self._parse_float(self._get_value(row, col("quantity"))),
                    days_supply=self._parse_int(self._get_value(row, col("days_supply"))),
                )
                if drug.source_id:
                    yield drug
            except Exception as e:
                logger.warning(f"Error parsing drug row: {e}")
                if not self.csv_config.skip_on_error:
                    raise

    async def extract_procedures(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceProcedure]:
        """Extract procedures from CSV file."""
        file_path = self.csv_config.get_file_path("procedures_file")
        if not file_path:
            return

        rows = self._read_csv(file_path)
        if not rows:
            return

        headers = list(rows[0].keys())
        col = lambda field: self._find_column(headers, field, DEFAULT_PROCEDURE_COLUMNS)

        for row in rows:
            try:
                pid = self._get_value(row, col("patient_source_id"))
                if patient_source_id and pid != patient_source_id:
                    continue

                procedure = SourceProcedure(
                    source_id=self._get_value(row, col("source_id")) or "",
                    source_system=self.source_system,
                    raw_data=dict(row),
                    patient_source_id=pid or "",
                    visit_source_id=self._get_value(row, col("visit_source_id")),
                    code=self._get_value(row, col("code")),
                    code_system=self._get_value(row, col("code_system")) or DEFAULT_CODE_SYSTEMS["procedure"],
                    display_text=self._get_value(row, col("display_text")),
                    performed_datetime=self._parse_datetime(
                        self._get_value(row, col("performed_datetime"))
                    ),
                )
                if procedure.source_id:
                    yield procedure
            except Exception as e:
                logger.warning(f"Error parsing procedure row: {e}")
                if not self.csv_config.skip_on_error:
                    raise

    async def extract_measurements(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceMeasurement]:
        """Extract measurements/labs from CSV file."""
        file_path = self.csv_config.get_file_path("measurements_file")
        if not file_path:
            return

        rows = self._read_csv(file_path)
        if not rows:
            return

        headers = list(rows[0].keys())
        col = lambda field: self._find_column(headers, field, DEFAULT_MEASUREMENT_COLUMNS)

        for row in rows:
            try:
                pid = self._get_value(row, col("patient_source_id"))
                if patient_source_id and pid != patient_source_id:
                    continue

                measurement = SourceMeasurement(
                    source_id=self._get_value(row, col("source_id")) or "",
                    source_system=self.source_system,
                    raw_data=dict(row),
                    patient_source_id=pid or "",
                    visit_source_id=self._get_value(row, col("visit_source_id")),
                    code=self._get_value(row, col("code")),
                    code_system=self._get_value(row, col("code_system")) or DEFAULT_CODE_SYSTEMS["measurement"],
                    display_text=self._get_value(row, col("display_text")),
                    value_numeric=self._parse_float(
                        self._get_value(row, col("value_numeric"))
                    ),
                    value_text=self._get_value(row, col("value_text")),
                    unit=self._get_value(row, col("unit")),
                    range_low=self._parse_float(self._get_value(row, col("range_low"))),
                    range_high=self._parse_float(self._get_value(row, col("range_high"))),
                    interpretation=self._get_value(row, col("interpretation")),
                    effective_datetime=self._parse_datetime(
                        self._get_value(row, col("effective_datetime"))
                    ),
                )
                if measurement.source_id:
                    yield measurement
            except Exception as e:
                logger.warning(f"Error parsing measurement row: {e}")
                if not self.csv_config.skip_on_error:
                    raise

    async def extract_observations(
        self, patient_source_id: str | None = None
    ) -> AsyncIterator[SourceObservation]:
        """Extract observations from CSV file."""
        file_path = self.csv_config.get_file_path("observations_file")
        if not file_path:
            return

        rows = self._read_csv(file_path)
        if not rows:
            return

        headers = list(rows[0].keys())

        obs_columns = {
            "source_id": ["observation_id", "id"],
            "patient_source_id": ["patient_id", "patientid"],
            "visit_source_id": ["visit_id", "encounter_id"],
            "code": ["code", "loinc", "snomed"],
            "code_system": ["code_system", "vocabulary"],
            "display_text": ["name", "description", "display"],
            "category": ["category", "type"],
            "value_numeric": ["value", "numeric_value"],
            "value_text": ["text_value", "value_text"],
            "unit": ["unit", "units"],
            "effective_datetime": ["date", "observation_date", "recorded_date"],
        }

        col = lambda field: self._find_column(headers, field, obs_columns)

        for row in rows:
            try:
                pid = self._get_value(row, col("patient_source_id"))
                if patient_source_id and pid != patient_source_id:
                    continue

                observation = SourceObservation(
                    source_id=self._get_value(row, col("source_id")) or "",
                    source_system=self.source_system,
                    raw_data=dict(row),
                    patient_source_id=pid or "",
                    visit_source_id=self._get_value(row, col("visit_source_id")),
                    code=self._get_value(row, col("code")),
                    code_system=self._get_value(row, col("code_system")),
                    display_text=self._get_value(row, col("display_text")),
                    category=self._get_value(row, col("category")),
                    value_numeric=self._parse_float(
                        self._get_value(row, col("value_numeric"))
                    ),
                    value_text=self._get_value(row, col("value_text")),
                    unit=self._get_value(row, col("unit")),
                    effective_datetime=self._parse_datetime(
                        self._get_value(row, col("effective_datetime"))
                    ),
                )
                if observation.source_id:
                    yield observation
            except Exception as e:
                logger.warning(f"Error parsing observation row: {e}")
                if not self.csv_config.skip_on_error:
                    raise
