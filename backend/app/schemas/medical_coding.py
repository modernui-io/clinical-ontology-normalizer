"""Pydantic schemas for Medical Coding Management (MED-CODE).

Manages medical coding operations: MedDRA coding of adverse events, WHO Drug
coding of concomitant medications, dictionary version management, auto-coding
rules, coding query resolution, and medical coding operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DictionaryType(str, Enum):
    MEDDRA = "meddra"
    WHO_DRUG = "who_drug"
    SNOMED = "snomed"
    ICD10 = "icd10"
    ATC = "atc"
    LOINC = "loinc"


class CodingStatus(str, Enum):
    PENDING = "pending"
    AUTO_CODED = "auto_coded"
    MANUALLY_CODED = "manually_coded"
    QUERY_OPEN = "query_open"
    QUERY_ANSWERED = "query_answered"
    VERIFIED = "verified"
    APPROVED = "approved"


class QueryStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class CodingPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MedDRALevel(str, Enum):
    SOC = "system_organ_class"
    HLGT = "high_level_group_term"
    HLT = "high_level_term"
    PT = "preferred_term"
    LLT = "lowest_level_term"


class DictionaryVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dictionary_type: DictionaryType
    version: str
    release_date: datetime
    effective_date: datetime
    expiry_date: datetime | None = None
    total_terms: int = Field(ge=0, default=0)
    active: bool = True
    migration_status: str | None = None
    notes: str | None = None
    loaded_by: str
    loaded_at: datetime


class CodingEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    source_term: str
    dictionary_type: DictionaryType
    dictionary_version: str
    coded_term: str | None = None
    coded_code: str | None = None
    meddra_pt: str | None = None
    meddra_soc: str | None = None
    meddra_llt: str | None = None
    meddra_hlt: str | None = None
    who_drug_name: str | None = None
    who_drug_atc: str | None = None
    status: CodingStatus = CodingStatus.PENDING
    priority: CodingPriority = CodingPriority.MEDIUM
    auto_code_confidence: float | None = None
    coded_by: str | None = None
    coded_date: datetime | None = None
    verified_by: str | None = None
    verified_date: datetime | None = None
    source_form: str | None = None
    source_field: str | None = None
    created_at: datetime


class AutoCodingRule(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str | None = None
    dictionary_type: DictionaryType
    source_pattern: str
    target_code: str
    target_term: str
    confidence_threshold: float = Field(ge=0, le=1, default=0.9)
    match_type: str = "exact"
    case_sensitive: bool = False
    active: bool = True
    hit_count: int = Field(ge=0, default=0)
    created_by: str
    created_at: datetime
    last_used: datetime | None = None


class CodingQuery(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    coding_entry_id: str
    trial_id: str
    subject_id: str
    query_text: str
    status: QueryStatus = QueryStatus.OPEN
    priority: CodingPriority = CodingPriority.MEDIUM
    assigned_to: str | None = None
    response_text: str | None = None
    response_by: str | None = None
    response_date: datetime | None = None
    site_id: str | None = None
    due_date: datetime | None = None
    opened_by: str
    opened_date: datetime
    closed_date: datetime | None = None


class CodingBatch(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    dictionary_type: DictionaryType
    batch_name: str
    total_entries: int = Field(ge=0, default=0)
    coded_entries: int = Field(ge=0, default=0)
    auto_coded: int = Field(ge=0, default=0)
    manually_coded: int = Field(ge=0, default=0)
    pending_entries: int = Field(ge=0, default=0)
    queries_raised: int = Field(ge=0, default=0)
    status: str = "in_progress"
    started_by: str
    started_at: datetime
    completed_at: datetime | None = None


class DictionaryVersionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dictionary_type: DictionaryType
    version: str
    release_date: datetime
    effective_date: datetime
    total_terms: int = Field(ge=0, default=0)
    loaded_by: str


class DictionaryVersionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    active: bool | None = None
    expiry_date: datetime | None = None
    migration_status: str | None = None
    notes: str | None = None


class CodingEntryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    source_term: str
    dictionary_type: DictionaryType
    dictionary_version: str
    priority: CodingPriority = CodingPriority.MEDIUM
    source_form: str | None = None
    source_field: str | None = None


class CodingEntryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    coded_term: str | None = None
    coded_code: str | None = None
    meddra_pt: str | None = None
    meddra_soc: str | None = None
    who_drug_name: str | None = None
    who_drug_atc: str | None = None
    status: CodingStatus | None = None
    coded_by: str | None = None
    verified_by: str | None = None


class AutoCodingRuleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str | None = None
    dictionary_type: DictionaryType
    source_pattern: str
    target_code: str
    target_term: str
    confidence_threshold: float = Field(ge=0, le=1, default=0.9)
    match_type: str = "exact"
    created_by: str


class AutoCodingRuleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    confidence_threshold: float | None = None
    active: bool | None = None
    target_code: str | None = None
    target_term: str | None = None


class CodingQueryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    coding_entry_id: str
    trial_id: str
    subject_id: str
    query_text: str
    priority: CodingPriority = CodingPriority.MEDIUM
    assigned_to: str | None = None
    site_id: str | None = None
    due_date: datetime | None = None
    opened_by: str


class CodingQueryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: QueryStatus | None = None
    response_text: str | None = None
    response_by: str | None = None
    assigned_to: str | None = None


class CodingBatchCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    dictionary_type: DictionaryType
    batch_name: str
    started_by: str


class CodingBatchUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    coded_entries: int | None = None
    auto_coded: int | None = None
    manually_coded: int | None = None
    pending_entries: int | None = None
    queries_raised: int | None = None
    status: str | None = None


class DictionaryVersionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DictionaryVersion] = Field(default_factory=list)
    total: int = Field(ge=0)


class CodingEntryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CodingEntry] = Field(default_factory=list)
    total: int = Field(ge=0)


class AutoCodingRuleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AutoCodingRule] = Field(default_factory=list)
    total: int = Field(ge=0)


class CodingQueryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CodingQuery] = Field(default_factory=list)
    total: int = Field(ge=0)


class CodingBatchListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CodingBatch] = Field(default_factory=list)
    total: int = Field(ge=0)


class MedicalCodingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_dictionary_versions: int = Field(ge=0)
    active_versions: int = Field(ge=0)
    total_coding_entries: int = Field(ge=0)
    entries_by_status: dict[str, int] = Field(default_factory=dict)
    entries_by_dictionary: dict[str, int] = Field(default_factory=dict)
    auto_code_rate_pct: float = Field(ge=0, le=100)
    total_auto_coding_rules: int = Field(ge=0)
    active_rules: int = Field(ge=0)
    total_queries: int = Field(ge=0)
    queries_by_status: dict[str, int] = Field(default_factory=dict)
    open_queries: int = Field(ge=0)
    avg_query_resolution_days: float = Field(ge=0)
    total_batches: int = Field(ge=0)
    completed_batches: int = Field(ge=0)
