"""Pydantic schemas for CDISC Standards Management (CDISC-STD).

Manages CDISC compliance: SDTM domain mapping, ADaM dataset definitions,
controlled terminology management, define.xml generation, conformance
validation, and CDISC operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CDISCStandard(str, Enum):
    SDTM = "sdtm"
    ADAM = "adam"
    SEND = "send"
    CDASH = "cdash"
    DEFINE_XML = "define_xml"


class DomainClass(str, Enum):
    EVENTS = "events"
    FINDINGS = "findings"
    INTERVENTIONS = "interventions"
    SPECIAL_PURPOSE = "special_purpose"
    TRIAL_DESIGN = "trial_design"
    RELATIONSHIP = "relationship"
    ASSOCIATED_PERSONS = "associated_persons"


class ConformanceLevel(str, Enum):
    REQUIRED = "required"
    EXPECTED = "expected"
    PERMISSIBLE = "permissible"
    CONDITIONAL = "conditional"


class MappingStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    MAPPED = "mapped"
    VALIDATED = "validated"
    APPROVED = "approved"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"
    INFO = "info"


class SDTMDomain(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    domain_code: str
    domain_name: str
    domain_class: DomainClass
    sdtm_version: str
    description: str
    key_variables: list[str] = Field(default_factory=list)
    total_variables: int = Field(ge=0, default=0)
    mapped_variables: int = Field(ge=0, default=0)
    status: MappingStatus = MappingStatus.NOT_STARTED
    source_datasets: list[str] = Field(default_factory=list)
    programmer: str
    reviewer: str | None = None
    created_at: datetime


class ADaMDataset(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    dataset_name: str
    dataset_label: str
    adam_version: str
    source_domains: list[str] = Field(default_factory=list)
    total_variables: int = Field(ge=0, default=0)
    derived_variables: int = Field(ge=0, default=0)
    status: MappingStatus = MappingStatus.NOT_STARTED
    analysis_purpose: str | None = None
    population_flag: str | None = None
    programmer: str
    reviewer: str | None = None
    created_at: datetime


class ControlledTerm(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str | None = None
    codelist_code: str
    codelist_name: str
    term_code: str
    term_value: str
    decoded_value: str
    ct_version: str
    standard: CDISCStandard
    extensible: bool = False
    custom: bool = False
    created_at: datetime


class DefineXML(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    standard: CDISCStandard
    version: str
    file_name: str
    status: str = "draft"
    total_datasets: int = Field(ge=0, default=0)
    total_variables: int = Field(ge=0, default=0)
    total_codelists: int = Field(ge=0, default=0)
    total_methods: int = Field(ge=0, default=0)
    total_comments: int = Field(ge=0, default=0)
    generated_date: datetime | None = None
    validated: bool = False
    validation_errors: int = Field(ge=0, default=0)
    author: str
    created_at: datetime


class ConformanceResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    standard: CDISCStandard
    validation_tool: str
    validation_date: datetime
    dataset_name: str
    rule_id: str
    severity: ValidationSeverity
    message: str
    variable: str | None = None
    record_count: int = Field(ge=0, default=0)
    status: str = "open"
    resolution: str | None = None
    resolved_by: str | None = None
    resolved_date: datetime | None = None


class SDTMDomainCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    domain_code: str
    domain_name: str
    domain_class: DomainClass
    sdtm_version: str
    description: str
    key_variables: list[str] = Field(default_factory=list)
    programmer: str


class SDTMDomainUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: MappingStatus | None = None
    total_variables: int | None = None
    mapped_variables: int | None = None
    reviewer: str | None = None
    source_datasets: list[str] | None = None


class ADaMDatasetCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    dataset_name: str
    dataset_label: str
    adam_version: str
    source_domains: list[str] = Field(default_factory=list)
    programmer: str
    analysis_purpose: str | None = None


class ADaMDatasetUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: MappingStatus | None = None
    total_variables: int | None = None
    derived_variables: int | None = None
    reviewer: str | None = None
    population_flag: str | None = None


class ControlledTermCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str | None = None
    codelist_code: str
    codelist_name: str
    term_code: str
    term_value: str
    decoded_value: str
    ct_version: str
    standard: CDISCStandard
    extensible: bool = False


class DefineXMLCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    standard: CDISCStandard
    version: str
    file_name: str
    author: str


class DefineXMLUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    total_datasets: int | None = None
    total_variables: int | None = None
    total_codelists: int | None = None
    validated: bool | None = None
    validation_errors: int | None = None


class ConformanceResultCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    standard: CDISCStandard
    validation_tool: str
    dataset_name: str
    rule_id: str
    severity: ValidationSeverity
    message: str
    variable: str | None = None
    record_count: int = Field(ge=0, default=0)


class ConformanceResultUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    resolution: str | None = None
    resolved_by: str | None = None


class SDTMDomainListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SDTMDomain] = Field(default_factory=list)
    total: int = Field(ge=0)


class ADaMDatasetListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ADaMDataset] = Field(default_factory=list)
    total: int = Field(ge=0)


class ControlledTermListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ControlledTerm] = Field(default_factory=list)
    total: int = Field(ge=0)


class DefineXMLListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DefineXML] = Field(default_factory=list)
    total: int = Field(ge=0)


class ConformanceResultListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ConformanceResult] = Field(default_factory=list)
    total: int = Field(ge=0)


class CDISCMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_sdtm_domains: int = Field(ge=0)
    domains_by_class: dict[str, int] = Field(default_factory=dict)
    domains_by_status: dict[str, int] = Field(default_factory=dict)
    sdtm_mapping_pct: float = Field(ge=0, le=100)
    total_adam_datasets: int = Field(ge=0)
    adam_by_status: dict[str, int] = Field(default_factory=dict)
    total_controlled_terms: int = Field(ge=0)
    custom_terms: int = Field(ge=0)
    total_define_xmls: int = Field(ge=0)
    validated_define_xmls: int = Field(ge=0)
    total_conformance_results: int = Field(ge=0)
    results_by_severity: dict[str, int] = Field(default_factory=dict)
    open_errors: int = Field(ge=0)
