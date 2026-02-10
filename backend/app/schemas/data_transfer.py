"""Pydantic schemas for Clinical Data Transfer Management (DATA-XFER).

Manages data transfers between sponsors, CROs, labs, and regulatory authorities:
transfer agreements, transfer execution tracking, data validation checks,
reconciliation, secure file transfer monitoring, and transfer metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TransferDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class TransferMethod(str, Enum):
    SFTP = "sftp"
    API = "api"
    ENCRYPTED_EMAIL = "encrypted_email"
    PHYSICAL_MEDIA = "physical_media"
    CLOUD_SHARE = "cloud_share"
    DIRECT_DATABASE = "direct_database"


class TransferFrequency(str, Enum):
    REAL_TIME = "real_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"
    MILESTONE_BASED = "milestone_based"


class TransferStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"


class ValidationResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNINGS = "warnings"
    PENDING = "pending"


class AgreementStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class DataTransferAgreement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    partner_name: str
    partner_type: str
    direction: TransferDirection
    transfer_method: TransferMethod
    frequency: TransferFrequency
    data_types: list[str] = Field(default_factory=list)
    encryption_required: bool = True
    status: AgreementStatus = AgreementStatus.DRAFT
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    responsible_person: str
    technical_contact: str
    created_at: datetime


class DataTransferExecution(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agreement_id: str
    trial_id: str
    transfer_date: datetime
    direction: TransferDirection
    status: TransferStatus = TransferStatus.SCHEDULED
    records_expected: int = Field(ge=0, default=0)
    records_transferred: int = Field(ge=0, default=0)
    records_failed: int = Field(ge=0, default=0)
    file_count: int = Field(ge=0, default=0)
    total_size_bytes: int = Field(ge=0, default=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    error_message: str | None = None
    initiated_by: str


class TransferValidation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    execution_id: str
    validation_type: str
    result: ValidationResult = ValidationResult.PENDING
    records_checked: int = Field(ge=0, default=0)
    records_passed: int = Field(ge=0, default=0)
    records_failed: int = Field(ge=0, default=0)
    issues: list[str] = Field(default_factory=list)
    validated_by: str
    validated_date: datetime


class TransferReconciliation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    execution_id: str
    source_record_count: int = Field(ge=0)
    target_record_count: int = Field(ge=0)
    matched_records: int = Field(ge=0)
    unmatched_records: int = Field(ge=0)
    reconciled: bool = False
    reconciled_by: str | None = None
    reconciled_date: datetime | None = None
    discrepancy_notes: str | None = None


class DataTransferAgreementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    partner_name: str
    partner_type: str
    direction: TransferDirection
    transfer_method: TransferMethod
    frequency: TransferFrequency
    data_types: list[str] = Field(default_factory=list)
    encryption_required: bool = True
    responsible_person: str
    technical_contact: str


class DataTransferAgreementUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AgreementStatus | None = None
    transfer_method: TransferMethod | None = None
    frequency: TransferFrequency | None = None
    data_types: list[str] | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None


class DataTransferExecutionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agreement_id: str
    trial_id: str
    direction: TransferDirection
    records_expected: int = Field(ge=0, default=0)
    file_count: int = Field(ge=0, default=0)
    initiated_by: str


class DataTransferExecutionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: TransferStatus | None = None
    records_transferred: int | None = None
    records_failed: int | None = None
    total_size_bytes: int | None = None
    error_message: str | None = None


class TransferValidationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    execution_id: str
    validation_type: str
    validated_by: str
    records_checked: int = Field(ge=0, default=0)
    records_passed: int = Field(ge=0, default=0)
    records_failed: int = Field(ge=0, default=0)
    issues: list[str] = Field(default_factory=list)
    result: ValidationResult = ValidationResult.PENDING


class TransferReconciliationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    execution_id: str
    source_record_count: int = Field(ge=0)
    target_record_count: int = Field(ge=0)
    matched_records: int = Field(ge=0)
    unmatched_records: int = Field(ge=0)
    reconciled_by: str | None = None
    discrepancy_notes: str | None = None


class TransferReconciliationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reconciled: bool | None = None
    reconciled_by: str | None = None
    discrepancy_notes: str | None = None


class DataTransferAgreementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataTransferAgreement] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataTransferExecutionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataTransferExecution] = Field(default_factory=list)
    total: int = Field(ge=0)


class TransferValidationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TransferValidation] = Field(default_factory=list)
    total: int = Field(ge=0)


class TransferReconciliationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TransferReconciliation] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataTransferMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_agreements: int = Field(ge=0)
    agreements_by_status: dict[str, int] = Field(default_factory=dict)
    agreements_by_method: dict[str, int] = Field(default_factory=dict)
    total_executions: int = Field(ge=0)
    executions_by_status: dict[str, int] = Field(default_factory=dict)
    successful_transfers: int = Field(ge=0)
    failed_transfers: int = Field(ge=0)
    total_records_transferred: int = Field(ge=0)
    total_validations: int = Field(ge=0)
    validations_passed: int = Field(ge=0)
    validations_failed: int = Field(ge=0)
    total_reconciliations: int = Field(ge=0)
    reconciled_count: int = Field(ge=0)
    avg_transfer_duration_seconds: float = Field(ge=0)
