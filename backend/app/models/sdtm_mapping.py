"""SDTM Mapping Specification Models.

Defines the data model for SDTM (Study Data Tabulation Model) mappings
that transform source data to CDISC SDTM format.

SDTM mappings consist of:
- Domain specification (target SDTM domain like DM, AE, CM)
- Variable mappings (source column to SDTM variable)
- Transformations (data type conversions, codelist lookups)
- Validation rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class SDTMDomainClass(str, Enum):
    """SDTM domain classes per CDISC SDTMIG."""

    SPECIAL_PURPOSE = "special_purpose"  # DM, CO, SE, SV
    INTERVENTIONS = "interventions"  # CM, EC, EX, SU
    EVENTS = "events"  # AE, CE, DS, DV, HO, MH
    FINDINGS = "findings"  # DA, EG, IE, LB, MB, MI, MO, MS, OM, PC, PE, PP, QS, RE, RP, RS, SC, SS, TU, UR, VS
    TRIAL_DESIGN = "trial_design"  # TA, TE, TI, TS, TV
    RELATIONSHIP = "relationship"  # RELREC


class SDTMVariableRole(str, Enum):
    """SDTM variable roles."""

    IDENTIFIER = "Identifier"
    TOPIC = "Topic"
    TIMING = "Timing"
    QUALIFIER = "Qualifier"
    RULE = "Rule"
    RECORD_QUALIFIER = "Record Qualifier"
    VARIABLE_QUALIFIER = "Variable Qualifier"
    SYNONYM_QUALIFIER = "Synonym Qualifier"


class SDTMDataType(str, Enum):
    """SDTM data types per CDISC standards."""

    CHAR = "Char"  # Character
    NUM = "Num"  # Numeric
    DATE = "date"  # ISO 8601 date
    DATETIME = "datetime"  # ISO 8601 datetime
    DURATION = "duration"  # ISO 8601 duration
    INTEGER = "integer"  # Integer numeric


class TransformationType(str, Enum):
    """Types of transformations for source to SDTM mapping."""

    DIRECT = "direct"  # Direct copy from source
    CONSTANT = "constant"  # Fixed value
    CONCATENATE = "concatenate"  # Combine multiple source fields
    CODELIST = "codelist"  # Lookup in controlled terminology
    DATE_CONVERT = "date_convert"  # Convert date format
    SUBSTRING = "substring"  # Extract substring
    EXPRESSION = "expression"  # Custom expression
    LOOKUP = "lookup"  # External lookup table
    SEQUENCE = "sequence"  # Generate sequence number


@dataclass
class SDTMVariable:
    """Definition of an SDTM variable."""

    name: str  # Variable name (e.g., USUBJID, AETERM)
    label: str  # Variable label
    data_type: SDTMDataType = SDTMDataType.CHAR
    length: int | None = None  # For character variables
    role: SDTMVariableRole = SDTMVariableRole.QUALIFIER
    controlled_term: str | None = None  # Codelist reference
    core: str = "Perm"  # Req, Exp, Perm
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "data_type": self.data_type.value,
            "length": self.length,
            "role": self.role.value,
            "controlled_term": self.controlled_term,
            "core": self.core,
            "comment": self.comment,
        }


@dataclass
class VariableTransformation:
    """Transformation rule for a source to SDTM variable mapping."""

    transformation_type: TransformationType
    source_columns: list[str] = field(default_factory=list)  # Source column names
    constant_value: str | None = None  # For CONSTANT type
    format_pattern: str | None = None  # Date format, expression, etc.
    codelist_id: str | None = None  # For CODELIST type
    lookup_table: str | None = None  # For LOOKUP type
    parameters: dict[str, Any] = field(default_factory=dict)  # Additional params

    def to_dict(self) -> dict[str, Any]:
        return {
            "transformation_type": self.transformation_type.value,
            "source_columns": self.source_columns,
            "constant_value": self.constant_value,
            "format_pattern": self.format_pattern,
            "codelist_id": self.codelist_id,
            "lookup_table": self.lookup_table,
            "parameters": self.parameters,
        }


@dataclass
class VariableMapping:
    """Mapping from source data to an SDTM variable."""

    target_variable: str  # SDTM variable name
    transformation: VariableTransformation
    condition: str | None = None  # Optional condition for conditional mapping
    order: int = 0  # Processing order

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_variable": self.target_variable,
            "transformation": self.transformation.to_dict(),
            "condition": self.condition,
            "order": self.order,
        }


@dataclass
class SDTMDomainSpec:
    """Specification for an SDTM domain."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain: str = ""  # Two-letter domain code (DM, AE, etc.)
    domain_class: SDTMDomainClass = SDTMDomainClass.SPECIAL_PURPOSE
    label: str = ""  # Domain description
    structure: str = "One record per subject"  # Dataset structure
    key_variables: list[str] = field(default_factory=list)  # Key sequence variables
    variables: list[SDTMVariable] = field(default_factory=list)
    variable_mappings: list[VariableMapping] = field(default_factory=list)
    source_table: str | None = None  # Primary source table
    source_filter: str | None = None  # SQL-like filter for source data
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "domain_class": self.domain_class.value,
            "label": self.label,
            "structure": self.structure,
            "key_variables": self.key_variables,
            "variables": [v.to_dict() for v in self.variables],
            "variable_mappings": [m.to_dict() for m in self.variable_mappings],
            "source_table": self.source_table,
            "source_filter": self.source_filter,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SDTMDomainSpec":
        """Create SDTMDomainSpec from dictionary."""
        variables = [
            SDTMVariable(
                name=v["name"],
                label=v["label"],
                data_type=SDTMDataType(v.get("data_type", "Char")),
                length=v.get("length"),
                role=SDTMVariableRole(v.get("role", "Qualifier")),
                controlled_term=v.get("controlled_term"),
                core=v.get("core", "Perm"),
                comment=v.get("comment"),
            )
            for v in data.get("variables", [])
        ]

        mappings = []
        for m in data.get("variable_mappings", []):
            trans = m.get("transformation", {})
            transformation = VariableTransformation(
                transformation_type=TransformationType(trans.get("transformation_type", "direct")),
                source_columns=trans.get("source_columns", []),
                constant_value=trans.get("constant_value"),
                format_pattern=trans.get("format_pattern"),
                codelist_id=trans.get("codelist_id"),
                lookup_table=trans.get("lookup_table"),
                parameters=trans.get("parameters", {}),
            )
            mappings.append(
                VariableMapping(
                    target_variable=m["target_variable"],
                    transformation=transformation,
                    condition=m.get("condition"),
                    order=m.get("order", 0),
                )
            )

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            domain=data.get("domain", ""),
            domain_class=SDTMDomainClass(data.get("domain_class", "special_purpose")),
            label=data.get("label", ""),
            structure=data.get("structure", ""),
            key_variables=data.get("key_variables", []),
            variables=variables,
            variable_mappings=mappings,
            source_table=data.get("source_table"),
            source_filter=data.get("source_filter"),
            version=data.get("version", "1.0.0"),
            notes=data.get("notes"),
        )


@dataclass
class SDTMMappingSpec:
    """Complete SDTM mapping specification for a study."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str = ""
    study_name: str = ""
    sdtmig_version: str = "3.3"  # SDTM Implementation Guide version
    domains: list[SDTMDomainSpec] = field(default_factory=list)
    global_variables: dict[str, str] = field(default_factory=dict)  # Study-level vars
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    status: str = "draft"  # draft, active, archived

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "study_id": self.study_id,
            "study_name": self.study_name,
            "sdtmig_version": self.sdtmig_version,
            "domains": [d.to_dict() for d in self.domains],
            "global_variables": self.global_variables,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SDTMMappingSpec":
        """Create SDTMMappingSpec from dictionary."""
        domains = [
            SDTMDomainSpec.from_dict(d)
            for d in data.get("domains", [])
        ]

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            study_id=data.get("study_id", ""),
            study_name=data.get("study_name", ""),
            sdtmig_version=data.get("sdtmig_version", "3.3"),
            domains=domains,
            global_variables=data.get("global_variables", {}),
            created_by=data.get("created_by"),
            status=data.get("status", "draft"),
        )

    def get_domain(self, domain_code: str) -> SDTMDomainSpec | None:
        """Get a domain spec by domain code."""
        for domain in self.domains:
            if domain.domain == domain_code:
                return domain
        return None

    def add_domain(self, domain: SDTMDomainSpec) -> None:
        """Add a domain to the mapping spec."""
        # Remove existing if present
        self.domains = [d for d in self.domains if d.domain != domain.domain]
        self.domains.append(domain)
        self.updated_at = datetime.now(timezone.utc)
