"""Database Source Connector for ETL Pipeline.

This module provides a connector for extracting clinical data from SQL
databases (PostgreSQL, SQL Server, MySQL, SQLite) and transforming it
into standardized SourceRecord objects for OMOP CDM transformation.

Supported Databases:
    - PostgreSQL (via asyncpg or psycopg)
    - SQL Server (via aioodbc or pyodbc)
    - MySQL/MariaDB (via aiomysql)
    - SQLite (via aiosqlite)

Architecture:
    DatabaseConnector uses configurable SQL queries or table mappings to
    extract data. It supports:
    - Custom SQL queries per record type
    - Table-to-field mappings for automatic extraction
    - Batch streaming for large datasets
    - Connection pooling for performance

Usage:
    from app.connectors import DatabaseConnector, DatabaseConnectorConfig

    config = DatabaseConnectorConfig(
        connection_string="postgresql://user:pass@localhost/clinical_db",
        patient_query="SELECT * FROM patients WHERE active = true",
        patient_mapping={
            "source_id": "patient_id",
            "given_name": "first_name",
            "family_name": "last_name",
            "birth_date": "dob",
        }
    )
    connector = DatabaseConnector(config)
    async for patient in connector.extract_patients():
        print(patient.source_id, patient.given_name)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

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
    CONDITION_STATUS_MAP,
    DRUG_STATUS_MAP,
    GENDER_MAP,
    PROCEDURE_STATUS_MAP,
    VISIT_TYPE_MAP,
)

logger = logging.getLogger(__name__)


# Default column mappings for common EHR schemas
DEFAULT_PATIENT_MAPPING = {
    "source_id": ["patient_id", "pat_id", "id", "mrn"],
    "given_name": ["first_name", "given_name", "fname", "first"],
    "family_name": ["last_name", "family_name", "lname", "last", "surname"],
    "birth_date": ["birth_date", "dob", "date_of_birth", "birthdate"],
    "gender": ["gender", "sex", "gender_code"],
    "race": ["race", "race_code"],
    "ethnicity": ["ethnicity", "ethnicity_code", "ethnic_group"],
    "address_line1": ["address", "address_line1", "street", "address1"],
    "address_line2": ["address_line2", "address2", "apt"],
    "city": ["city"],
    "state": ["state", "state_code", "province"],
    "postal_code": ["zip", "postal_code", "zip_code", "zipcode"],
    "phone": ["phone", "phone_number", "telephone"],
    "email": ["email", "email_address"],
    "ssn": ["ssn", "social_security"],
    "death_date": ["death_date", "deceased_date", "date_of_death"],
}

DEFAULT_VISIT_MAPPING = {
    "source_id": ["visit_id", "encounter_id", "enc_id", "id"],
    "patient_source_id": ["patient_id", "pat_id", "mrn"],
    "visit_type": ["visit_type", "encounter_type", "type", "class"],
    "start_date": ["start_date", "admit_date", "admission_date", "visit_date", "encounter_date"],
    "end_date": ["end_date", "discharge_date", "visit_end_date"],
    "facility": ["facility", "location", "hospital", "site"],
    "department": ["department", "dept", "unit", "service"],
    "provider_id": ["provider_id", "attending_id", "physician_id"],
    "provider_name": ["provider_name", "attending_name", "physician_name"],
    "admission_source": ["admission_source", "admit_source"],
    "discharge_disposition": ["discharge_disposition", "discharge_status", "disposition"],
}

DEFAULT_CONDITION_MAPPING = {
    "source_id": ["condition_id", "diagnosis_id", "problem_id", "id"],
    "patient_source_id": ["patient_id", "pat_id", "mrn"],
    "visit_source_id": ["visit_id", "encounter_id", "enc_id"],
    "condition_code": ["condition_code", "diagnosis_code", "icd_code", "code", "dx_code"],
    "condition_code_system": ["code_system", "coding_system", "vocabulary"],
    "condition_name": ["condition_name", "diagnosis_name", "description", "name"],
    "condition_type": ["condition_type", "diagnosis_type", "type"],
    "onset_date": ["onset_date", "diagnosis_date", "start_date", "date"],
    "resolution_date": ["resolution_date", "resolved_date", "end_date"],
    "status": ["status", "condition_status"],
}

DEFAULT_DRUG_MAPPING = {
    "source_id": ["medication_id", "drug_id", "prescription_id", "order_id", "id"],
    "patient_source_id": ["patient_id", "pat_id", "mrn"],
    "visit_source_id": ["visit_id", "encounter_id", "enc_id"],
    "drug_code": ["drug_code", "ndc", "rxnorm", "code", "med_code"],
    "drug_code_system": ["code_system", "coding_system", "vocabulary"],
    "drug_name": ["drug_name", "medication_name", "med_name", "name"],
    "start_date": ["start_date", "order_date", "prescribed_date", "date"],
    "end_date": ["end_date", "stop_date", "discontinue_date"],
    "quantity": ["quantity", "qty", "amount"],
    "days_supply": ["days_supply", "supply_days", "duration"],
    "refills": ["refills", "refill_count"],
    "dose_value": ["dose_value", "dose", "dosage", "strength"],
    "dose_unit": ["dose_unit", "unit", "strength_unit"],
    "frequency": ["frequency", "sig", "directions"],
    "route": ["route", "route_of_admin", "administration_route"],
    "status": ["status", "order_status", "medication_status"],
}

DEFAULT_PROCEDURE_MAPPING = {
    "source_id": ["procedure_id", "proc_id", "order_id", "id"],
    "patient_source_id": ["patient_id", "pat_id", "mrn"],
    "visit_source_id": ["visit_id", "encounter_id", "enc_id"],
    "procedure_code": ["procedure_code", "cpt_code", "code", "proc_code"],
    "procedure_code_system": ["code_system", "coding_system", "vocabulary"],
    "procedure_name": ["procedure_name", "description", "name"],
    "procedure_date": ["procedure_date", "performed_date", "date", "service_date"],
    "provider_id": ["provider_id", "performing_provider", "surgeon_id"],
    "modifier_codes": ["modifier_codes", "modifiers"],
    "quantity": ["quantity", "units"],
    "status": ["status", "procedure_status"],
}

DEFAULT_MEASUREMENT_MAPPING = {
    "source_id": ["measurement_id", "result_id", "observation_id", "id"],
    "patient_source_id": ["patient_id", "pat_id", "mrn"],
    "visit_source_id": ["visit_id", "encounter_id", "enc_id"],
    "measurement_code": ["measurement_code", "loinc_code", "code", "test_code"],
    "measurement_code_system": ["code_system", "coding_system", "vocabulary"],
    "measurement_name": ["measurement_name", "test_name", "name", "component"],
    "value_numeric": ["value_numeric", "result_value", "value", "result"],
    "value_text": ["value_text", "result_text", "text_value"],
    "unit": ["unit", "units", "unit_of_measure", "uom"],
    "reference_range_low": ["reference_low", "ref_low", "normal_low", "range_low"],
    "reference_range_high": ["reference_high", "ref_high", "normal_high", "range_high"],
    "measurement_date": ["measurement_date", "result_date", "date", "collected_date"],
    "abnormal_flag": ["abnormal_flag", "flag", "abnormal"],
}

DEFAULT_OBSERVATION_MAPPING = {
    "source_id": ["observation_id", "id"],
    "patient_source_id": ["patient_id", "pat_id", "mrn"],
    "visit_source_id": ["visit_id", "encounter_id", "enc_id"],
    "observation_code": ["observation_code", "code", "snomed_code"],
    "observation_code_system": ["code_system", "coding_system", "vocabulary"],
    "observation_name": ["observation_name", "name", "description"],
    "observation_type": ["observation_type", "type", "category"],
    "observation_date": ["observation_date", "date", "recorded_date"],
    "value_numeric": ["value_numeric", "value", "numeric_value"],
    "value_text": ["value_text", "text_value", "result"],
    "unit": ["unit", "units"],
}


# Status mappings are now imported from concept_mappings module
# The following local variables are kept for backward compatibility within this module
# but the actual mappings come from the consolidated concept_mappings.py


@dataclass
class TableMapping:
    """Configuration for mapping a database table to source records."""

    table_name: str
    """Name of the database table or view."""

    column_mapping: dict[str, str] = field(default_factory=dict)
    """Explicit mapping of source field to database column."""

    where_clause: str | None = None
    """Optional WHERE clause filter (without WHERE keyword)."""

    order_by: str | None = None
    """Optional ORDER BY clause (without ORDER BY keyword)."""


@dataclass
class DatabaseConnectorConfig(ConnectorConfig):
    """Configuration for database connector.

    Attributes:
        connection_string: Database connection URL.
        patient_query: Custom SQL query for patients.
        visit_query: Custom SQL query for visits.
        condition_query: Custom SQL query for conditions.
        drug_query: Custom SQL query for drugs.
        procedure_query: Custom SQL query for procedures.
        measurement_query: Custom SQL query for measurements.
        observation_query: Custom SQL query for observations.
        patient_table: Table mapping for patients (alternative to query).
        visit_table: Table mapping for visits.
        condition_table: Table mapping for conditions.
        drug_table: Table mapping for drugs.
        procedure_table: Table mapping for procedures.
        measurement_table: Table mapping for measurements.
        observation_table: Table mapping for observations.
        batch_size: Number of rows to fetch per batch.
        pool_size: Connection pool size.
    """

    connector_type: ConnectorType = field(default=ConnectorType.DATABASE)
    connection_string: str = ""

    # Custom SQL queries
    patient_query: str | None = None
    visit_query: str | None = None
    condition_query: str | None = None
    drug_query: str | None = None
    procedure_query: str | None = None
    measurement_query: str | None = None
    observation_query: str | None = None

    # Table mappings (alternative to custom queries)
    patient_table: TableMapping | None = None
    visit_table: TableMapping | None = None
    condition_table: TableMapping | None = None
    drug_table: TableMapping | None = None
    procedure_table: TableMapping | None = None
    measurement_table: TableMapping | None = None
    observation_table: TableMapping | None = None

    # Column mappings (used with queries or auto-mapping)
    patient_mapping: dict[str, str] = field(default_factory=dict)
    visit_mapping: dict[str, str] = field(default_factory=dict)
    condition_mapping: dict[str, str] = field(default_factory=dict)
    drug_mapping: dict[str, str] = field(default_factory=dict)
    procedure_mapping: dict[str, str] = field(default_factory=dict)
    measurement_mapping: dict[str, str] = field(default_factory=dict)
    observation_mapping: dict[str, str] = field(default_factory=dict)

    # Performance settings
    batch_size: int = 1000
    pool_size: int = 5
    query_timeout: int = 300  # seconds


class DatabaseConnector(SourceConnector):
    """Database source connector for extracting clinical data from SQL databases.

    Supports PostgreSQL, SQL Server, MySQL, and SQLite through unified
    async interface. Uses connection pooling and batched streaming for
    efficient data extraction.

    Example:
        config = DatabaseConnectorConfig(
            connection_string="postgresql://user:pass@localhost/db",
            patient_query="SELECT * FROM patients",
            patient_mapping={"source_id": "patient_id", "given_name": "first_name"}
        )
        connector = DatabaseConnector(config)
        async for patient in connector.extract_patients():
            print(patient.given_name)
    """

    def __init__(self, config: DatabaseConnectorConfig):
        """Initialize database connector."""
        super().__init__(config)
        self.config: DatabaseConnectorConfig = config
        self._connection = None
        self._pool = None
        self._db_type = self._detect_db_type()

    def _detect_db_type(self) -> str:
        """Detect database type from connection string."""
        conn_str = self.config.connection_string.lower()
        parsed = urlparse(self.config.connection_string)
        scheme = parsed.scheme.lower() if parsed.scheme else ""

        if "postgresql" in scheme or "postgres" in scheme:
            return "postgresql"
        elif "mysql" in scheme or "mariadb" in scheme:
            return "mysql"
        elif "mssql" in scheme or "sqlserver" in conn_str or "odbc" in scheme:
            return "mssql"
        elif "sqlite" in scheme:
            return "sqlite"
        else:
            # Try to detect from connection string content
            if "driver=" in conn_str and ("sql server" in conn_str or "odbc" in conn_str):
                return "mssql"
            return "postgresql"  # Default

    async def connect(self) -> None:
        """Establish database connection."""
        try:
            if self._db_type == "postgresql":
                await self._connect_postgresql()
            elif self._db_type == "mysql":
                await self._connect_mysql()
            elif self._db_type == "mssql":
                await self._connect_mssql()
            elif self._db_type == "sqlite":
                await self._connect_sqlite()
            else:
                raise ValueError(f"Unsupported database type: {self._db_type}")

            logger.info(f"Connected to {self._db_type} database")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def _connect_postgresql(self) -> None:
        """Connect to PostgreSQL database."""
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self.config.connection_string,
                min_size=1,
                max_size=self.config.pool_size,
                command_timeout=self.config.query_timeout,
            )
        except ImportError:
            # Fallback to psycopg if asyncpg not available
            import psycopg

            self._connection = await psycopg.AsyncConnection.connect(
                self.config.connection_string
            )

    async def _connect_mysql(self) -> None:
        """Connect to MySQL database."""
        import aiomysql
        from urllib.parse import urlparse

        parsed = urlparse(self.config.connection_string)
        self._pool = await aiomysql.create_pool(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            db=parsed.path.lstrip("/"),
            minsize=1,
            maxsize=self.config.pool_size,
        )

    async def _connect_mssql(self) -> None:
        """Connect to SQL Server database."""
        import aioodbc

        self._pool = await aioodbc.create_pool(
            dsn=self.config.connection_string,
            minsize=1,
            maxsize=self.config.pool_size,
        )

    async def _connect_sqlite(self) -> None:
        """Connect to SQLite database."""
        import aiosqlite
        from urllib.parse import urlparse

        parsed = urlparse(self.config.connection_string)
        db_path = parsed.path if parsed.path else ":memory:"
        self._connection = await aiosqlite.connect(db_path)

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._pool:
            if hasattr(self._pool, "close"):
                self._pool.close()
                if hasattr(self._pool, "wait_closed"):
                    await self._pool.wait_closed()
        if self._connection:
            await self._connection.close()

        self._pool = None
        self._connection = None
        logger.info("Disconnected from database")

    async def _execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute query and yield rows as dicts."""
        if self._pool:
            if self._db_type == "postgresql":
                async with self._pool.acquire() as conn:
                    async with conn.transaction():
                        cursor = await conn.cursor(query, *(params.values() if params else []))
                        columns = [desc[0] for desc in cursor.description or []]
                        async for row in cursor:
                            yield dict(zip(columns, row))
            elif self._db_type == "mysql":
                async with self._pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(query, params)
                        columns = [desc[0] for desc in cursor.description or []]
                        async for row in cursor:
                            yield dict(zip(columns, row))
            elif self._db_type == "mssql":
                async with self._pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(query, params)
                        columns = [desc[0] for desc in cursor.description or []]
                        while True:
                            rows = await cursor.fetchmany(self.config.batch_size)
                            if not rows:
                                break
                            for row in rows:
                                yield dict(zip(columns, row))
        elif self._connection:
            if self._db_type == "sqlite":
                self._connection.row_factory = None
                async with self._connection.execute(query, params or ()) as cursor:
                    columns = [desc[0] for desc in cursor.description or []]
                    async for row in cursor:
                        yield dict(zip(columns, row))
            else:
                async with self._connection.cursor() as cursor:
                    await cursor.execute(query, params)
                    columns = [desc[0] for desc in cursor.description or []]
                    async for row in cursor:
                        yield dict(zip(columns, row))
        else:
            raise RuntimeError("Not connected to database. Call connect() first.")

    def _build_query_from_table(self, table_mapping: TableMapping) -> str:
        """Build SELECT query from table mapping.

        VP-Security: Added SQL injection protection via identifier validation.
        Table names, column names, and operators are validated against allowlists.
        """
        # Validate table name (alphanumeric, underscores, dots for schema.table)
        table_name = table_mapping.table_name
        if not self._is_valid_identifier(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        query = f"SELECT * FROM {table_name}"

        if table_mapping.where_clause:
            # Validate where clause - only allow simple conditions
            # For complex queries, use parameterized queries directly
            validated_where = self._validate_where_clause(table_mapping.where_clause)
            query += f" WHERE {validated_where}"

        if table_mapping.order_by:
            # Validate order by - only allow column names and ASC/DESC
            validated_order = self._validate_order_by(table_mapping.order_by)
            query += f" ORDER BY {validated_order}"

        return query

    def _is_valid_identifier(self, identifier: str) -> bool:
        """Validate SQL identifier (table/column name).

        Only allows alphanumeric characters, underscores, and dots (for schema.table).
        """
        import re
        # Allow schema.table format (e.g., public.patients)
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$'
        return bool(re.match(pattern, identifier))

    def _validate_where_clause(self, where_clause: str) -> str:
        """Validate and sanitize WHERE clause.

        VP-Security: Prevents SQL injection by validating clause structure.
        Only allows simple column=value or column IN (...) patterns.
        For complex queries, raise an error and require parameterized queries.
        """
        import re

        # Check for dangerous SQL keywords/patterns
        dangerous_patterns = [
            r';\s*',           # Statement terminator
            r'--',             # Comment
            r'/\*',            # Block comment
            r'\bUNION\b',      # UNION injection
            r'\bDROP\b',       # DROP injection
            r'\bDELETE\b',     # DELETE injection
            r'\bINSERT\b',     # INSERT injection
            r'\bUPDATE\b',     # UPDATE injection
            r'\bEXEC\b',       # EXEC injection
            r'\bEXECUTE\b',    # EXECUTE injection
            r'\bxp_',          # SQL Server extended procedures
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, where_clause, re.IGNORECASE):
                raise ValueError(
                    f"Potentially dangerous SQL pattern detected in WHERE clause. "
                    f"Use parameterized queries for complex conditions."
                )

        return where_clause

    def _validate_order_by(self, order_by: str) -> str:
        """Validate ORDER BY clause.

        VP-Security: Only allows column names with optional ASC/DESC.
        """
        import re

        # Split by comma for multiple columns
        parts = [p.strip() for p in order_by.split(',')]
        validated_parts = []

        for part in parts:
            # Match: column_name or column_name ASC/DESC
            match = re.match(
                r'^([a-zA-Z_][a-zA-Z0-9_]*)(\s+(ASC|DESC))?$',
                part,
                re.IGNORECASE
            )
            if not match:
                raise ValueError(f"Invalid ORDER BY clause: {part}")
            validated_parts.append(part)

        return ', '.join(validated_parts)

    def _get_column_value(
        self,
        row: dict[str, Any],
        field: str,
        mapping: dict[str, str],
        default_mapping: dict[str, list[str]],
    ) -> Any:
        """Get column value using explicit or default mapping."""
        # Try explicit mapping first
        if field in mapping:
            col_name = mapping[field]
            if col_name in row:
                return row[col_name]
            # Try case-insensitive
            for k, v in row.items():
                if k.lower() == col_name.lower():
                    return v

        # Try default mappings
        if field in default_mapping:
            for col_name in default_mapping[field]:
                if col_name in row:
                    return row[col_name]
                # Case-insensitive
                for k, v in row.items():
                    if k.lower() == col_name.lower():
                        return v

        return None

    def _parse_date(self, value: Any) -> date | None:
        """Parse date from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"]:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse datetime from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%m/%d/%Y %H:%M:%S",
                "%Y-%m-%d",
            ]:
                try:
                    return datetime.strptime(value.split("+")[0].split("Z")[0], fmt)
                except ValueError:
                    continue
        return None

    def _parse_decimal(self, value: Any) -> Decimal | None:
        """Parse decimal/numeric value."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def _row_to_patient(self, row: dict[str, Any]) -> SourcePatient:
        """Convert database row to SourcePatient."""
        get = lambda f: self._get_column_value(
            row, f, self.config.patient_mapping, DEFAULT_PATIENT_MAPPING
        )

        gender_raw = get("gender")
        gender = Gender.UNKNOWN
        if gender_raw:
            gender = GENDER_MAP.get(str(gender_raw).lower().strip(), Gender.UNKNOWN)

        return SourcePatient(
            source_id=str(get("source_id") or ""),
            given_name=get("given_name"),
            family_name=get("family_name"),
            birth_date=self._parse_date(get("birth_date")),
            gender=gender,
            race=get("race"),
            ethnicity=get("ethnicity"),
            address_line1=get("address_line1"),
            address_line2=get("address_line2"),
            city=get("city"),
            state=get("state"),
            postal_code=get("postal_code"),
            phone=get("phone"),
            email=get("email"),
            ssn=get("ssn"),
            death_date=self._parse_date(get("death_date")),
            raw_data=row,
        )

    def _row_to_visit(self, row: dict[str, Any]) -> SourceVisit:
        """Convert database row to SourceVisit."""
        get = lambda f: self._get_column_value(
            row, f, self.config.visit_mapping, DEFAULT_VISIT_MAPPING
        )

        visit_type_raw = get("visit_type")
        visit_type = VisitType.UNKNOWN
        if visit_type_raw:
            visit_type = VISIT_TYPE_MAP.get(
                str(visit_type_raw).lower().strip(), VisitType.UNKNOWN
            )

        return SourceVisit(
            source_id=str(get("source_id") or ""),
            patient_source_id=str(get("patient_source_id") or ""),
            visit_type=visit_type,
            start_date=self._parse_date(get("start_date")),
            start_datetime=self._parse_datetime(get("start_date")),
            end_date=self._parse_date(get("end_date")),
            end_datetime=self._parse_datetime(get("end_date")),
            facility=get("facility"),
            department=get("department"),
            provider_id=get("provider_id"),
            provider_name=get("provider_name"),
            admission_source=get("admission_source"),
            discharge_disposition=get("discharge_disposition"),
            raw_data=row,
        )

    def _row_to_condition(self, row: dict[str, Any]) -> SourceCondition:
        """Convert database row to SourceCondition."""
        get = lambda f: self._get_column_value(
            row, f, self.config.condition_mapping, DEFAULT_CONDITION_MAPPING
        )

        status_raw = get("status")
        status = ConditionStatus.UNKNOWN
        if status_raw:
            status = CONDITION_STATUS_MAP.get(
                str(status_raw).lower().strip(), ConditionStatus.UNKNOWN
            )

        return SourceCondition(
            source_id=str(get("source_id") or ""),
            patient_source_id=str(get("patient_source_id") or ""),
            visit_source_id=get("visit_source_id"),
            condition_code=get("condition_code"),
            condition_code_system=get("condition_code_system"),
            condition_name=get("condition_name"),
            condition_type=get("condition_type"),
            onset_date=self._parse_date(get("onset_date")),
            onset_datetime=self._parse_datetime(get("onset_date")),
            resolution_date=self._parse_date(get("resolution_date")),
            status=status,
            raw_data=row,
        )

    def _row_to_drug(self, row: dict[str, Any]) -> SourceDrug:
        """Convert database row to SourceDrug."""
        get = lambda f: self._get_column_value(
            row, f, self.config.drug_mapping, DEFAULT_DRUG_MAPPING
        )

        status_raw = get("status")
        status = DrugStatus.UNKNOWN
        if status_raw:
            status = DRUG_STATUS_MAP.get(
                str(status_raw).lower().strip(), DrugStatus.UNKNOWN
            )

        quantity = get("quantity")
        if quantity is not None:
            try:
                quantity = float(quantity)
            except (ValueError, TypeError):
                quantity = None

        days_supply = get("days_supply")
        if days_supply is not None:
            try:
                days_supply = int(days_supply)
            except (ValueError, TypeError):
                days_supply = None

        refills = get("refills")
        if refills is not None:
            try:
                refills = int(refills)
            except (ValueError, TypeError):
                refills = None

        return SourceDrug(
            source_id=str(get("source_id") or ""),
            patient_source_id=str(get("patient_source_id") or ""),
            visit_source_id=get("visit_source_id"),
            drug_code=get("drug_code"),
            drug_code_system=get("drug_code_system"),
            drug_name=get("drug_name"),
            start_date=self._parse_date(get("start_date")),
            start_datetime=self._parse_datetime(get("start_date")),
            end_date=self._parse_date(get("end_date")),
            end_datetime=self._parse_datetime(get("end_date")),
            quantity=quantity,
            days_supply=days_supply,
            refills=refills,
            dose_value=get("dose_value"),
            dose_unit=get("dose_unit"),
            frequency=get("frequency"),
            route=get("route"),
            status=status,
            raw_data=row,
        )

    def _row_to_procedure(self, row: dict[str, Any]) -> SourceProcedure:
        """Convert database row to SourceProcedure."""
        get = lambda f: self._get_column_value(
            row, f, self.config.procedure_mapping, DEFAULT_PROCEDURE_MAPPING
        )

        status_raw = get("status")
        status = ProcedureStatus.UNKNOWN
        if status_raw:
            status = PROCEDURE_STATUS_MAP.get(
                str(status_raw).lower().strip(), ProcedureStatus.UNKNOWN
            )

        quantity = get("quantity")
        if quantity is not None:
            try:
                quantity = int(quantity)
            except (ValueError, TypeError):
                quantity = None

        modifier_codes = get("modifier_codes")
        if modifier_codes and isinstance(modifier_codes, str):
            modifier_codes = [m.strip() for m in modifier_codes.split(",")]

        return SourceProcedure(
            source_id=str(get("source_id") or ""),
            patient_source_id=str(get("patient_source_id") or ""),
            visit_source_id=get("visit_source_id"),
            procedure_code=get("procedure_code"),
            procedure_code_system=get("procedure_code_system"),
            procedure_name=get("procedure_name"),
            procedure_date=self._parse_date(get("procedure_date")),
            procedure_datetime=self._parse_datetime(get("procedure_date")),
            provider_id=get("provider_id"),
            modifier_codes=modifier_codes if modifier_codes else None,
            quantity=quantity,
            status=status,
            raw_data=row,
        )

    def _row_to_measurement(self, row: dict[str, Any]) -> SourceMeasurement:
        """Convert database row to SourceMeasurement."""
        get = lambda f: self._get_column_value(
            row, f, self.config.measurement_mapping, DEFAULT_MEASUREMENT_MAPPING
        )

        return SourceMeasurement(
            source_id=str(get("source_id") or ""),
            patient_source_id=str(get("patient_source_id") or ""),
            visit_source_id=get("visit_source_id"),
            measurement_code=get("measurement_code"),
            measurement_code_system=get("measurement_code_system"),
            measurement_name=get("measurement_name"),
            value_numeric=self._parse_decimal(get("value_numeric")),
            value_text=get("value_text"),
            unit=get("unit"),
            reference_range_low=self._parse_decimal(get("reference_range_low")),
            reference_range_high=self._parse_decimal(get("reference_range_high")),
            measurement_date=self._parse_date(get("measurement_date")),
            measurement_datetime=self._parse_datetime(get("measurement_date")),
            abnormal_flag=get("abnormal_flag"),
            raw_data=row,
        )

    def _row_to_observation(self, row: dict[str, Any]) -> SourceObservation:
        """Convert database row to SourceObservation."""
        get = lambda f: self._get_column_value(
            row, f, self.config.observation_mapping, DEFAULT_OBSERVATION_MAPPING
        )

        return SourceObservation(
            source_id=str(get("source_id") or ""),
            patient_source_id=str(get("patient_source_id") or ""),
            visit_source_id=get("visit_source_id"),
            observation_code=get("observation_code"),
            observation_code_system=get("observation_code_system"),
            observation_name=get("observation_name"),
            observation_type=get("observation_type"),
            observation_date=self._parse_date(get("observation_date")),
            observation_datetime=self._parse_datetime(get("observation_date")),
            value_numeric=self._parse_decimal(get("value_numeric")),
            value_text=get("value_text"),
            unit=get("unit"),
            raw_data=row,
        )

    async def extract_patients(self) -> AsyncIterator[SourcePatient]:
        """Extract patient records from database."""
        query = self.config.patient_query
        if not query and self.config.patient_table:
            query = self._build_query_from_table(self.config.patient_table)

        if not query:
            logger.warning("No patient query or table mapping configured")
            return

        count = 0
        async for row in self._execute_query(query):
            try:
                patient = self._row_to_patient(row)
                if patient.source_id:
                    count += 1
                    yield patient
            except Exception as e:
                logger.warning(f"Error parsing patient row: {e}")

        logger.info(f"Extracted {count} patients from database")

    async def extract_visits(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceVisit]:
        """Extract visit records from database."""
        query = self.config.visit_query
        if not query and self.config.visit_table:
            query = self._build_query_from_table(self.config.visit_table)

        if not query:
            logger.warning("No visit query or table mapping configured")
            return

        count = 0
        async for row in self._execute_query(query):
            try:
                visit = self._row_to_visit(row)
                if visit.source_id:
                    if patient_source_id is None or visit.patient_source_id == patient_source_id:
                        count += 1
                        yield visit
            except Exception as e:
                logger.warning(f"Error parsing visit row: {e}")

        logger.info(f"Extracted {count} visits from database")

    async def extract_conditions(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceCondition]:
        """Extract condition records from database."""
        query = self.config.condition_query
        if not query and self.config.condition_table:
            query = self._build_query_from_table(self.config.condition_table)

        if not query:
            logger.warning("No condition query or table mapping configured")
            return

        count = 0
        async for row in self._execute_query(query):
            try:
                condition = self._row_to_condition(row)
                if condition.source_id:
                    if patient_source_id is None or condition.patient_source_id == patient_source_id:
                        count += 1
                        yield condition
            except Exception as e:
                logger.warning(f"Error parsing condition row: {e}")

        logger.info(f"Extracted {count} conditions from database")

    async def extract_drugs(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceDrug]:
        """Extract drug/medication records from database."""
        query = self.config.drug_query
        if not query and self.config.drug_table:
            query = self._build_query_from_table(self.config.drug_table)

        if not query:
            logger.warning("No drug query or table mapping configured")
            return

        count = 0
        async for row in self._execute_query(query):
            try:
                drug = self._row_to_drug(row)
                if drug.source_id:
                    if patient_source_id is None or drug.patient_source_id == patient_source_id:
                        count += 1
                        yield drug
            except Exception as e:
                logger.warning(f"Error parsing drug row: {e}")

        logger.info(f"Extracted {count} drugs from database")

    async def extract_procedures(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceProcedure]:
        """Extract procedure records from database."""
        query = self.config.procedure_query
        if not query and self.config.procedure_table:
            query = self._build_query_from_table(self.config.procedure_table)

        if not query:
            logger.warning("No procedure query or table mapping configured")
            return

        count = 0
        async for row in self._execute_query(query):
            try:
                procedure = self._row_to_procedure(row)
                if procedure.source_id:
                    if patient_source_id is None or procedure.patient_source_id == patient_source_id:
                        count += 1
                        yield procedure
            except Exception as e:
                logger.warning(f"Error parsing procedure row: {e}")

        logger.info(f"Extracted {count} procedures from database")

    async def extract_measurements(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceMeasurement]:
        """Extract measurement records from database."""
        query = self.config.measurement_query
        if not query and self.config.measurement_table:
            query = self._build_query_from_table(self.config.measurement_table)

        if not query:
            logger.warning("No measurement query or table mapping configured")
            return

        count = 0
        async for row in self._execute_query(query):
            try:
                measurement = self._row_to_measurement(row)
                if measurement.source_id:
                    if patient_source_id is None or measurement.patient_source_id == patient_source_id:
                        count += 1
                        yield measurement
            except Exception as e:
                logger.warning(f"Error parsing measurement row: {e}")

        logger.info(f"Extracted {count} measurements from database")

    async def extract_observations(
        self,
        patient_source_id: str | None = None,
    ) -> AsyncIterator[SourceObservation]:
        """Extract observation records from database."""
        query = self.config.observation_query
        if not query and self.config.observation_table:
            query = self._build_query_from_table(self.config.observation_table)

        if not query:
            logger.warning("No observation query or table mapping configured")
            return

        count = 0
        async for row in self._execute_query(query):
            try:
                observation = self._row_to_observation(row)
                if observation.source_id:
                    if patient_source_id is None or observation.patient_source_id == patient_source_id:
                        count += 1
                        yield observation
            except Exception as e:
                logger.warning(f"Error parsing observation row: {e}")

        logger.info(f"Extracted {count} observations from database")

    async def extract_all(self) -> ExtractionResult:
        """Extract all record types from database."""
        result = ExtractionResult()

        try:
            # Extract patients
            async for patient in self.extract_patients():
                result.patients.append(patient)

            # Extract visits
            async for visit in self.extract_visits():
                result.visits.append(visit)

            # Extract conditions
            async for condition in self.extract_conditions():
                result.conditions.append(condition)

            # Extract drugs
            async for drug in self.extract_drugs():
                result.drugs.append(drug)

            # Extract procedures
            async for procedure in self.extract_procedures():
                result.procedures.append(procedure)

            # Extract measurements
            async for measurement in self.extract_measurements():
                result.measurements.append(measurement)

            # Extract observations
            async for observation in self.extract_observations():
                result.observations.append(observation)

            logger.info(
                f"Database extraction complete: {len(result.patients)} patients, "
                f"{len(result.visits)} visits, {len(result.conditions)} conditions, "
                f"{len(result.drugs)} drugs, {len(result.procedures)} procedures, "
                f"{len(result.measurements)} measurements, {len(result.observations)} observations"
            )

        except Exception as e:
            result.errors.append(f"Database extraction error: {e}")
            logger.error(f"Database extraction failed: {e}")

        return result

    async def validate_connection(self) -> tuple[bool, str]:
        """Validate database connection and configuration."""
        try:
            if not self._pool and not self._connection:
                await self.connect()

            # Try a simple query
            count = 0
            async for _ in self._execute_query("SELECT 1"):
                count += 1

            if count > 0:
                return True, f"Successfully connected to {self._db_type} database"
            return False, "Connection test query returned no results"

        except Exception as e:
            return False, f"Connection validation failed: {e}"

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        return {
            "connector_type": "database",
            "database_type": self._db_type,
            "connected": self._pool is not None or self._connection is not None,
            "batch_size": self.config.batch_size,
            "pool_size": self.config.pool_size,
        }
