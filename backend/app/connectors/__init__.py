"""Source Data Connectors for ETL Pipeline.

This module provides a pluggable architecture for connecting to various
clinical data sources (FHIR, HL7, C-CDA, CSV, databases) and extracting
data into a standardized intermediate format for OMOP CDM transformation.

Architecture:
    SourceConnector (abstract base)
        ├── FHIRConnector - FHIR R4 servers (planned)
        ├── HL7v2Connector - HL7 v2.x messages ✓
        ├── CCDAConnector - C-CDA/CDA documents ✓
        ├── CSVConnector - CSV/flat files ✓
        └── DatabaseConnector - SQL databases (planned)

Usage:
    from app.connectors import CCDAConnector, CCDAConnectorConfig, SourcePatient

    config = CCDAConnectorConfig(documents_path="/path/to/ccda/files")
    connector = CCDAConnector(config)
    async for patient in connector.extract_patients():
        print(patient.source_id, patient.given_name, patient.family_name)
"""

from __future__ import annotations

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
    SourceRecord,
    SourceVisit,
    VisitType,
)
from app.connectors.ccda_connector import CCDAConnector, CCDAConnectorConfig
from app.connectors.csv_connector import CSVConnector, CSVConnectorConfig
from app.connectors.database_connector import (
    DatabaseConnector,
    DatabaseConnectorConfig,
    TableMapping,
)
from app.connectors.fhir_connector import FHIRConnector, FHIRConnectorConfig
from app.connectors.hl7v2_connector import HL7v2Connector, HL7v2ConnectorConfig

# Concept mappings for shared healthcare data mappings
from app.connectors.concept_mappings import (
    CCDA_ENCOUNTER_CODE_MAP,
    CCDA_SECTION_MAP,
    CCDA_SECTION_TEMPLATE_IDS,
    CODE_SYSTEM_MAP,
    CONDITION_STATUS_MAP,
    DEFAULT_CODE_SYSTEMS,
    DRUG_STATUS_MAP,
    FHIR_ENCOUNTER_CLASS_MAP,
    FHIR_OBSERVATION_CATEGORY_MAP,
    FHIR_RESOURCE_MAP,
    GENDER_MAP,
    HL7_CODING_METHOD_MAP,
    HL7_PATIENT_CLASS_MAP,
    HL7_SEGMENT_MAP,
    PROCEDURE_STATUS_MAP,
    VISIT_TYPE_MAP,
    normalize_code_system,
    parse_condition_status,
    parse_drug_status,
    parse_gender,
    parse_procedure_status,
    parse_visit_type,
)

__all__ = [
    # Base classes and enums
    "ConditionStatus",
    "ConnectorConfig",
    "ConnectorType",
    "DrugStatus",
    "ExtractionResult",
    "Gender",
    "ProcedureStatus",
    "SourceCondition",
    "SourceConnector",
    "SourceDrug",
    "SourceMeasurement",
    "SourceObservation",
    "SourcePatient",
    "SourceProcedure",
    "SourceRecord",
    "SourceVisit",
    "VisitType",
    # C-CDA Connector
    "CCDAConnector",
    "CCDAConnectorConfig",
    # CSV Connector
    "CSVConnector",
    "CSVConnectorConfig",
    # HL7 v2 Connector
    "HL7v2Connector",
    "HL7v2ConnectorConfig",
    # FHIR R4 Connector
    "FHIRConnector",
    "FHIRConnectorConfig",
    # Database Connector
    "DatabaseConnector",
    "DatabaseConnectorConfig",
    "TableMapping",
    # Concept Mappings
    "CCDA_ENCOUNTER_CODE_MAP",
    "CCDA_SECTION_MAP",
    "CCDA_SECTION_TEMPLATE_IDS",
    "CODE_SYSTEM_MAP",
    "CONDITION_STATUS_MAP",
    "DEFAULT_CODE_SYSTEMS",
    "DRUG_STATUS_MAP",
    "FHIR_ENCOUNTER_CLASS_MAP",
    "FHIR_OBSERVATION_CATEGORY_MAP",
    "FHIR_RESOURCE_MAP",
    "GENDER_MAP",
    "HL7_CODING_METHOD_MAP",
    "HL7_PATIENT_CLASS_MAP",
    "HL7_SEGMENT_MAP",
    "PROCEDURE_STATUS_MAP",
    "VISIT_TYPE_MAP",
    "normalize_code_system",
    "parse_condition_status",
    "parse_drug_status",
    "parse_gender",
    "parse_procedure_status",
    "parse_visit_type",
]
