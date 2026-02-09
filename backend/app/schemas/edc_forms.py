"""Pydantic schemas for Electronic Data Capture (EDC) Form Management (CLINICAL-24).

Manages EDC operations: CRF template definitions with visit applicability, CRF field
configuration with SDTM mapping, CRF instance lifecycle (blank through locked/frozen),
data query management with auto-generation, edit check definitions with severity levels,
form-level data entry and validation, and EDC operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FormStatus(str, Enum):
    """Lifecycle status of a CRF instance."""

    BLANK = "blank"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SIGNED = "signed"
    LOCKED = "locked"
    FROZEN = "frozen"


class FieldType(str, Enum):
    """Type of a CRF field."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    TEXTAREA = "textarea"
    CALCULATED = "calculated"
    LAB_VALUE = "lab_value"


class QueryStatus(str, Enum):
    """Lifecycle status of a data query."""

    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class EditCheckType(str, Enum):
    """Type of edit check rule."""

    RANGE_CHECK = "range_check"
    CONSISTENCY_CHECK = "consistency_check"
    REQUIRED_FIELD = "required_field"
    CROSS_FORM_CHECK = "cross_form_check"
    DYNAMIC_EDIT = "dynamic_edit"


class EditCheckSeverity(str, Enum):
    """Severity level of an edit check violation."""

    WARNING = "warning"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class CRFField(BaseModel):
    """Definition of a single field within a CRF template."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique field identifier")
    field_name: str = Field(..., description="Internal field name (machine-readable)")
    label: str = Field(..., description="Human-readable field label")
    field_type: FieldType = Field(..., description="Field data type")
    required: bool = Field(default=False, description="Whether the field is required")
    validation_rules: dict | None = Field(
        None, description="Validation rules (e.g., min, max, regex)"
    )
    options: list[str] | None = Field(
        None, description="Options for dropdown/radio/checkbox fields"
    )
    default_value: str | None = Field(None, description="Default value for the field")
    sas_variable_name: str | None = Field(
        None, description="SAS variable name for export"
    )
    sdtm_domain: str | None = Field(
        None, description="SDTM domain mapping (e.g., DM, AE, VS)"
    )
    sdtm_variable: str | None = Field(
        None, description="SDTM variable mapping (e.g., BRTHDTC, AETERM)"
    )


class EditCheck(BaseModel):
    """Definition of an edit check rule for a CRF template."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique edit check identifier")
    template_id: str = Field(..., description="Associated CRF template ID")
    check_type: EditCheckType = Field(..., description="Type of edit check")
    description: str = Field(..., description="Human-readable description of the check")
    expression: str = Field(
        ..., description="Check expression (e.g., 'SYSBP >= 60 AND SYSBP <= 250')"
    )
    error_message: str = Field(
        ..., description="Message displayed when check fails"
    )
    severity: EditCheckSeverity = Field(
        default=EditCheckSeverity.ERROR, description="Severity level"
    )
    active: bool = Field(default=True, description="Whether this check is active")


class CRFTemplate(BaseModel):
    """Definition of a Case Report Form template."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique template identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    form_name: str = Field(..., description="Form name (e.g., Demographics, Vitals)")
    version: str = Field(..., description="Template version (e.g., 1.0, 2.1)")
    visit_applicability: list[str] = Field(
        default_factory=list,
        description="Visits where this form applies (e.g., Screening, Week 4)",
    )
    fields: list[CRFField] = Field(
        default_factory=list, description="Fields defined in this template"
    )
    edit_checks: list[EditCheck] = Field(
        default_factory=list, description="Edit checks associated with this template"
    )
    status: str = Field(
        default="active", description="Template status (active, draft, retired)"
    )


class CRFInstance(BaseModel):
    """A specific instance of a CRF filled out for a patient visit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique instance identifier")
    template_id: str = Field(..., description="Associated CRF template ID")
    patient_id: str = Field(..., description="Patient/subject identifier")
    visit_number: int = Field(..., description="Visit number")
    site_id: str = Field(..., description="Site identifier")
    status: FormStatus = Field(
        default=FormStatus.BLANK, description="Form lifecycle status"
    )
    started_date: datetime | None = Field(
        None, description="Date data entry was started"
    )
    completed_date: datetime | None = Field(
        None, description="Date the form was completed"
    )
    signed_by: str | None = Field(None, description="Name of the signer")
    signed_date: datetime | None = Field(None, description="Date the form was signed")
    locked_date: datetime | None = Field(None, description="Date the form was locked")
    data: dict[str, object] = Field(
        default_factory=dict,
        description="Form data as field_name -> value mapping",
    )


class DataQuery(BaseModel):
    """A data query raised against a CRF field value."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique query identifier")
    instance_id: str = Field(..., description="Associated CRF instance ID")
    field_name: str = Field(..., description="Field name the query refers to")
    query_text: str = Field(..., description="Query description / question")
    raised_by: str = Field(..., description="Person or system that raised the query")
    raised_date: datetime = Field(..., description="Date the query was raised")
    response: str | None = Field(None, description="Response to the query")
    responded_by: str | None = Field(None, description="Person who responded")
    responded_date: datetime | None = Field(
        None, description="Date the response was provided"
    )
    status: QueryStatus = Field(
        default=QueryStatus.OPEN, description="Query lifecycle status"
    )
    auto_generated: bool = Field(
        default=False, description="Whether this query was auto-generated by an edit check"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class CRFTemplateCreate(BaseModel):
    """Request to create a new CRF template."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    form_name: str = Field(..., description="Form name")
    version: str = Field(default="1.0", description="Template version")
    visit_applicability: list[str] = Field(
        default_factory=list, description="Applicable visits"
    )
    fields: list[CRFFieldCreate] | None = Field(
        None, description="Initial field definitions"
    )


class CRFTemplateUpdate(BaseModel):
    """Request to update a CRF template."""

    model_config = ConfigDict(from_attributes=True)

    form_name: str | None = Field(None, description="Form name")
    version: str | None = Field(None, description="Version")
    visit_applicability: list[str] | None = Field(
        None, description="Applicable visits"
    )
    status: str | None = Field(None, description="Template status")


class CRFFieldCreate(BaseModel):
    """Request to add a field to a CRF template."""

    model_config = ConfigDict(from_attributes=True)

    field_name: str = Field(..., description="Internal field name")
    label: str = Field(..., description="Display label")
    field_type: FieldType = Field(..., description="Field type")
    required: bool = Field(default=False, description="Whether required")
    validation_rules: dict | None = Field(None, description="Validation rules")
    options: list[str] | None = Field(None, description="Options for select fields")
    default_value: str | None = Field(None, description="Default value")
    sas_variable_name: str | None = Field(None, description="SAS variable name")
    sdtm_domain: str | None = Field(None, description="SDTM domain")
    sdtm_variable: str | None = Field(None, description="SDTM variable")


class CRFInstanceCreate(BaseModel):
    """Request to create a CRF instance."""

    model_config = ConfigDict(from_attributes=True)

    template_id: str = Field(..., description="Template ID")
    patient_id: str = Field(..., description="Patient ID")
    visit_number: int = Field(..., description="Visit number")
    site_id: str = Field(..., description="Site ID")


class CRFInstanceUpdate(BaseModel):
    """Request to update CRF instance data."""

    model_config = ConfigDict(from_attributes=True)

    data: dict[str, object] | None = Field(None, description="Field data to update")
    status: FormStatus | None = Field(None, description="New status")


class CRFInstanceSign(BaseModel):
    """Request to sign a CRF instance."""

    model_config = ConfigDict(from_attributes=True)

    signed_by: str = Field(..., description="Name of the signer")


class DataQueryCreate(BaseModel):
    """Request to create a data query."""

    model_config = ConfigDict(from_attributes=True)

    instance_id: str = Field(..., description="CRF instance ID")
    field_name: str = Field(..., description="Field name")
    query_text: str = Field(..., description="Query text")
    raised_by: str = Field(..., description="Person raising the query")
    auto_generated: bool = Field(default=False, description="Auto-generated flag")


class DataQueryRespond(BaseModel):
    """Request to respond to a data query."""

    model_config = ConfigDict(from_attributes=True)

    response: str = Field(..., description="Response text")
    responded_by: str = Field(..., description="Person responding")


class DataQueryClose(BaseModel):
    """Request to close a data query."""

    model_config = ConfigDict(from_attributes=True)

    closed_by: str = Field(..., description="Person closing the query")


class EditCheckCreate(BaseModel):
    """Request to create an edit check."""

    model_config = ConfigDict(from_attributes=True)

    template_id: str = Field(..., description="Template ID")
    check_type: EditCheckType = Field(..., description="Check type")
    description: str = Field(..., description="Description")
    expression: str = Field(..., description="Check expression")
    error_message: str = Field(..., description="Error message on failure")
    severity: EditCheckSeverity = Field(
        default=EditCheckSeverity.ERROR, description="Severity"
    )


class EditCheckUpdate(BaseModel):
    """Request to update an edit check."""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = Field(None, description="Description")
    expression: str | None = Field(None, description="Check expression")
    error_message: str | None = Field(None, description="Error message")
    severity: EditCheckSeverity | None = Field(None, description="Severity")
    active: bool | None = Field(None, description="Active status")


class EditCheckResult(BaseModel):
    """Result of running edit checks against a CRF instance."""

    model_config = ConfigDict(from_attributes=True)

    instance_id: str = Field(..., description="CRF instance ID")
    total_checks: int = Field(ge=0, description="Total edit checks evaluated")
    passed: int = Field(ge=0, description="Checks passed")
    failed: int = Field(ge=0, description="Checks failed")
    failures: list[EditCheckFailure] = Field(
        default_factory=list, description="Details of failed checks"
    )


class EditCheckFailure(BaseModel):
    """Detail of a single edit check failure."""

    model_config = ConfigDict(from_attributes=True)

    check_id: str = Field(..., description="Edit check ID")
    check_type: EditCheckType = Field(..., description="Check type")
    field_name: str | None = Field(None, description="Relevant field name")
    error_message: str = Field(..., description="Error message")
    severity: EditCheckSeverity = Field(..., description="Severity")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class CRFTemplateListResponse(BaseModel):
    """List of CRF templates."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CRFTemplate] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CRFInstanceListResponse(BaseModel):
    """List of CRF instances."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CRFInstance] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DataQueryListResponse(BaseModel):
    """List of data queries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DataQuery] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class EditCheckListResponse(BaseModel):
    """List of edit checks."""

    model_config = ConfigDict(from_attributes=True)

    items: list[EditCheck] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class EDCMetrics(BaseModel):
    """Aggregated Electronic Data Capture operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_forms: int = Field(ge=0, description="Total CRF instances")
    forms_by_status: dict[str, int] = Field(
        default_factory=dict, description="Form counts by lifecycle status"
    )
    total_queries: int = Field(ge=0, description="Total data queries")
    open_queries: int = Field(ge=0, description="Number of open queries")
    avg_query_resolution_days: float = Field(
        ge=0.0, description="Average days to resolve a query"
    )
    data_entry_lag_avg_days: float = Field(
        ge=0.0, description="Average days between visit and data entry start"
    )
    completion_rate: float = Field(
        ge=0.0, le=100.0, description="Percentage of forms completed or beyond"
    )
