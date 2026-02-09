"""Pydantic schemas for Central Laboratory Management (CLINICAL-8).

Manages lab test definitions, kit tracking, sample lifecycle, result
reporting with reference range evaluation, critical value alerting,
turnaround time monitoring, and sample shipment logistics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SampleType(str, Enum):
    """Biological specimen type collected from a patient."""

    BLOOD_SERUM = "blood_serum"
    BLOOD_PLASMA = "blood_plasma"
    BLOOD_WHOLE = "blood_whole"
    URINE = "urine"
    CSF = "csf"
    TISSUE = "tissue"
    SALIVA = "saliva"
    STOOL = "stool"


class SampleStatus(str, Enum):
    """Lifecycle status of a collected sample."""

    COLLECTED = "collected"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    PROCESSING = "processing"
    RESULTED = "resulted"
    REJECTED = "rejected"
    REDRAWN = "redrawn"


class LabTestCategory(str, Enum):
    """Functional category of a laboratory test."""

    HEMATOLOGY = "hematology"
    CHEMISTRY = "chemistry"
    IMMUNOLOGY = "immunology"
    BIOMARKER = "biomarker"
    PHARMACOKINETIC = "pharmacokinetic"
    URINALYSIS = "urinalysis"
    COAGULATION = "coagulation"


class ResultStatus(str, Enum):
    """Status of a laboratory result."""

    PENDING = "pending"
    PRELIMINARY = "preliminary"
    FINAL = "final"
    AMENDED = "amended"
    CANCELLED = "cancelled"


class KitStatus(str, Enum):
    """Availability status of a lab kit."""

    AVAILABLE = "available"
    ASSIGNED = "assigned"
    USED = "used"
    EXPIRED = "expired"
    DAMAGED = "damaged"


class ResultFlag(str, Enum):
    """Clinical significance flag for a lab result."""

    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"
    PANIC = "panic"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class LabTest(BaseModel):
    """Definition of a laboratory test with reference ranges."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique lab test identifier")
    name: str = Field(..., description="Human-readable test name")
    category: LabTestCategory = Field(..., description="Test category")
    loinc_code: Optional[str] = Field(None, description="LOINC code for the test")
    specimen_type: SampleType = Field(..., description="Required specimen type")
    reference_range_low: Optional[float] = Field(
        None, description="Lower bound of normal reference range"
    )
    reference_range_high: Optional[float] = Field(
        None, description="Upper bound of normal reference range"
    )
    unit: str = Field(..., description="Unit of measurement")
    critical_low: Optional[float] = Field(
        None, description="Critical low threshold (panic value)"
    )
    critical_high: Optional[float] = Field(
        None, description="Critical high threshold (panic value)"
    )
    turnaround_hours: int = Field(
        24, ge=1, description="Expected turnaround time in hours"
    )


class LabKit(BaseModel):
    """A laboratory collection kit assigned to a trial site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique kit identifier")
    kit_number: str = Field(..., description="Kit number / barcode")
    test_ids: list[str] = Field(
        default_factory=list, description="Test IDs this kit supports"
    )
    site_id: Optional[str] = Field(None, description="Assigned site ID")
    status: KitStatus = Field(KitStatus.AVAILABLE, description="Current kit status")
    assigned_date: Optional[datetime] = Field(
        None, description="Date kit was assigned to site"
    )
    expiry_date: Optional[datetime] = Field(
        None, description="Kit expiration date"
    )
    lot_number: str = Field("", description="Manufacturing lot number")


class Sample(BaseModel):
    """A biological sample collected from a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique sample identifier")
    patient_id: str = Field(..., description="Patient who provided the sample")
    site_id: str = Field(..., description="Collection site ID")
    sample_type: SampleType = Field(..., description="Type of specimen")
    collection_date: str = Field(..., description="Date of collection (YYYY-MM-DD)")
    collection_time: Optional[str] = Field(
        None, description="Time of collection (HH:MM)"
    )
    collector_initials: Optional[str] = Field(
        None, description="Initials of the person who collected the sample"
    )
    kit_id: Optional[str] = Field(None, description="Kit used for collection")
    barcode: str = Field(..., description="Sample barcode / tracking ID")
    status: SampleStatus = Field(
        SampleStatus.COLLECTED, description="Current sample status"
    )
    received_date: Optional[str] = Field(
        None, description="Date sample was received at central lab"
    )
    rejection_reason: Optional[str] = Field(
        None, description="Reason for sample rejection"
    )


class LabResult(BaseModel):
    """A laboratory test result for a sample."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique result identifier")
    sample_id: str = Field(..., description="Associated sample ID")
    test_id: str = Field(..., description="Lab test ID")
    value: Optional[float] = Field(None, description="Numeric result value")
    unit: str = Field("", description="Unit of measurement")
    reference_range: Optional[str] = Field(
        None, description="Reference range display string"
    )
    flag: ResultFlag = Field(
        ResultFlag.NORMAL, description="Clinical significance flag"
    )
    resulted_date: Optional[str] = Field(
        None, description="Date the result was finalized"
    )
    reviewed_by: Optional[str] = Field(
        None, description="Reviewer / pathologist who reviewed the result"
    )
    status: ResultStatus = Field(
        ResultStatus.PENDING, description="Result status"
    )


class CriticalValueAlert(BaseModel):
    """Alert triggered by a critical / panic lab value."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique alert identifier")
    result_id: str = Field(..., description="Lab result that triggered the alert")
    patient_id: str = Field(..., description="Patient identifier")
    site_id: str = Field(..., description="Site identifier")
    test_name: str = Field(..., description="Test name for display")
    value: float = Field(..., description="Result value that triggered the alert")
    critical_threshold: str = Field(
        ..., description="Description of the critical threshold breached"
    )
    notification_sent: bool = Field(
        False, description="Whether notification was sent to investigator"
    )
    acknowledged_by: Optional[str] = Field(
        None, description="Person who acknowledged the alert"
    )
    acknowledged_date: Optional[str] = Field(
        None, description="Date the alert was acknowledged"
    )


class SampleShipment(BaseModel):
    """A shipment of samples from a site to the central laboratory."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique shipment identifier")
    site_id: str = Field(..., description="Originating site ID")
    tracking_number: str = Field(..., description="Carrier tracking number")
    samples: list[str] = Field(
        default_factory=list, description="List of sample IDs in shipment"
    )
    shipped_date: str = Field(..., description="Date shipped (YYYY-MM-DD)")
    received_date: Optional[str] = Field(
        None, description="Date received at central lab"
    )
    condition_on_receipt: Optional[str] = Field(
        None, description="Condition of shipment on receipt"
    )
    temperature_acceptable: Optional[bool] = Field(
        None, description="Whether temperature was within acceptable range"
    )


# ---------------------------------------------------------------------------
# Metrics / analytics
# ---------------------------------------------------------------------------


class LabMetrics(BaseModel):
    """Aggregated metrics for the central laboratory dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_samples: int = Field(0, description="Total samples registered")
    samples_by_status: dict[str, int] = Field(
        default_factory=dict, description="Sample count by status"
    )
    avg_turnaround_hours: float = Field(
        0.0, description="Average turnaround time in hours"
    )
    critical_values_30d: int = Field(
        0, description="Critical value alerts in last 30 days"
    )
    rejection_rate: float = Field(
        0.0, description="Sample rejection rate (0-1)"
    )
    pending_results: int = Field(
        0, description="Results still pending"
    )
    kits_expiring_30d: int = Field(
        0, description="Kits expiring within 30 days"
    )


class TurnaroundTimeAnalysis(BaseModel):
    """Turnaround time analysis by test category."""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(..., description="Test category")
    avg_hours: float = Field(0.0, description="Average TAT in hours")
    median_hours: float = Field(0.0, description="Median TAT in hours")
    p95_hours: float = Field(0.0, description="95th percentile TAT in hours")
    total_resulted: int = Field(0, description="Total results in category")
    within_target: int = Field(0, description="Results within target TAT")
    target_hours: int = Field(24, description="Target TAT for this category")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class LabTestCreate(BaseModel):
    """Request body to create a lab test definition."""

    name: str = Field(..., description="Test name")
    category: LabTestCategory = Field(..., description="Test category")
    loinc_code: Optional[str] = Field(None, description="LOINC code")
    specimen_type: SampleType = Field(..., description="Required specimen type")
    reference_range_low: Optional[float] = Field(None, description="Reference range low")
    reference_range_high: Optional[float] = Field(None, description="Reference range high")
    unit: str = Field(..., description="Unit of measurement")
    critical_low: Optional[float] = Field(None, description="Critical low threshold")
    critical_high: Optional[float] = Field(None, description="Critical high threshold")
    turnaround_hours: int = Field(24, ge=1, description="Target turnaround hours")


class LabTestUpdate(BaseModel):
    """Request body to update a lab test definition."""

    name: Optional[str] = None
    category: Optional[LabTestCategory] = None
    loinc_code: Optional[str] = None
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None
    unit: Optional[str] = None
    critical_low: Optional[float] = None
    critical_high: Optional[float] = None
    turnaround_hours: Optional[int] = Field(None, ge=1)


class KitAssignRequest(BaseModel):
    """Request body to assign kits to a site."""

    kit_ids: list[str] = Field(..., min_length=1, description="Kit IDs to assign")
    site_id: str = Field(..., description="Target site ID")


class SampleRegisterRequest(BaseModel):
    """Request body to register a new sample collection."""

    patient_id: str = Field(..., description="Patient ID")
    site_id: str = Field(..., description="Collection site ID")
    sample_type: SampleType = Field(..., description="Specimen type")
    collection_date: str = Field(..., description="Collection date (YYYY-MM-DD)")
    collection_time: Optional[str] = Field(None, description="Collection time (HH:MM)")
    collector_initials: Optional[str] = Field(None, description="Collector initials")
    kit_id: Optional[str] = Field(None, description="Kit used")


class SampleReceiveRequest(BaseModel):
    """Request body to mark a sample as received."""

    received_date: str = Field(..., description="Date received (YYYY-MM-DD)")
    condition: Optional[str] = Field(None, description="Condition on receipt")
    temperature_acceptable: bool = Field(True, description="Temperature within range")


class SampleRejectRequest(BaseModel):
    """Request body to reject a sample."""

    reason: str = Field(..., description="Rejection reason")


class ResultSubmitRequest(BaseModel):
    """A single result submission."""

    sample_id: str = Field(..., description="Sample ID")
    test_id: str = Field(..., description="Lab test ID")
    value: Optional[float] = Field(None, description="Numeric value")
    unit: str = Field("", description="Unit")
    resulted_date: Optional[str] = Field(None, description="Result date")
    reviewed_by: Optional[str] = Field(None, description="Reviewer")
    status: ResultStatus = Field(ResultStatus.FINAL, description="Result status")


class ResultBatchSubmitRequest(BaseModel):
    """Batch result submission."""

    results: list[ResultSubmitRequest] = Field(
        ..., min_length=1, description="List of results to submit"
    )


class ShipmentCreateRequest(BaseModel):
    """Request body to create a sample shipment."""

    site_id: str = Field(..., description="Originating site")
    tracking_number: str = Field(..., description="Carrier tracking number")
    sample_ids: list[str] = Field(
        ..., min_length=1, description="Sample IDs to include"
    )
    shipped_date: str = Field(..., description="Ship date (YYYY-MM-DD)")


class AlertAcknowledgeRequest(BaseModel):
    """Request body to acknowledge a critical value alert."""

    acknowledged_by: str = Field(..., description="Person acknowledging")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class LabTestListResponse(BaseModel):
    """Paginated response for lab tests."""

    items: list[LabTest]
    total: int
    limit: int
    offset: int


class LabKitListResponse(BaseModel):
    """Paginated response for lab kits."""

    items: list[LabKit]
    total: int
    limit: int
    offset: int


class SampleListResponse(BaseModel):
    """Paginated response for samples."""

    items: list[Sample]
    total: int
    limit: int
    offset: int


class LabResultListResponse(BaseModel):
    """Paginated response for lab results."""

    items: list[LabResult]
    total: int
    limit: int
    offset: int


class CriticalValueAlertListResponse(BaseModel):
    """Response for critical value alerts."""

    items: list[CriticalValueAlert]
    total: int


class ShipmentListResponse(BaseModel):
    """Paginated response for shipments."""

    items: list[SampleShipment]
    total: int
    limit: int
    offset: int


class SampleWithResults(BaseModel):
    """A sample with its associated lab results."""

    sample: Sample
    results: list[LabResult]
