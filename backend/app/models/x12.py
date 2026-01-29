"""X12 EDI Data Models for Healthcare Claims.

This module provides Pydantic models for X12 EDI healthcare transactions:
- 837P (Professional Claim)
- 837I (Institutional Claim)
- 835 (Payment/Remittance Advice)

These models represent the hierarchical structure of X12 transactions
and support both parsing (X12 -> JSON) and generation (JSON -> X12).
"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================================
# Enumerations
# ============================================================================


class X12TransactionType(str, Enum):
    """X12 healthcare transaction types."""

    PROFESSIONAL_CLAIM = "837P"
    INSTITUTIONAL_CLAIM = "837I"
    PAYMENT_REMITTANCE = "835"
    ELIGIBILITY_INQUIRY = "270"
    ELIGIBILITY_RESPONSE = "271"
    CLAIM_STATUS_INQUIRY = "276"
    CLAIM_STATUS_RESPONSE = "277"


class ClaimFrequencyCode(str, Enum):
    """Claim frequency type codes."""

    ORIGINAL = "1"  # Original claim
    REPLACEMENT = "7"  # Replacement of prior claim
    VOID = "8"  # Void/cancel prior claim


class ClaimFilingIndicator(str, Enum):
    """Claim filing indicator codes."""

    COMMERCIAL = "CI"
    MEDICARE_PART_A = "MA"
    MEDICARE_PART_B = "MB"
    MEDICAID = "MC"
    CHAMPUS = "CH"
    TRICARE = "TF"
    WORKERS_COMP = "WC"
    BCBS = "BL"
    OTHER = "ZZ"


class ProviderTaxonomyCode(str, Enum):
    """Common provider taxonomy codes."""

    FAMILY_MEDICINE = "207Q00000X"
    INTERNAL_MEDICINE = "207R00000X"
    PEDIATRICS = "208000000X"
    EMERGENCY_MEDICINE = "207P00000X"
    CARDIOLOGY = "207RC0000X"
    HOSPITAL_GENERAL = "282N00000X"
    SKILLED_NURSING = "314000000X"


class PlaceOfService(str, Enum):
    """Place of service codes (CMS-1500)."""

    TELEHEALTH = "02"
    OFFICE = "11"
    HOME = "12"
    INPATIENT_HOSPITAL = "21"
    OUTPATIENT_HOSPITAL = "22"
    EMERGENCY_ROOM = "23"
    AMBULATORY_SURGICAL = "24"
    SKILLED_NURSING = "31"
    HOSPICE = "34"
    AMBULANCE_LAND = "41"
    AMBULANCE_AIR = "42"


class DiagnosisCodeQualifier(str, Enum):
    """Diagnosis code qualifier."""

    ICD10_CM = "ABK"  # ICD-10-CM Principal Diagnosis
    ICD10_ADDITIONAL = "ABF"  # ICD-10-CM Diagnosis
    ICD9_CM = "BK"  # ICD-9-CM (legacy)


class ProcedureCodeQualifier(str, Enum):
    """Procedure code qualifier."""

    CPT = "HC"  # CPT/HCPCS
    ICD10_PCS = "BBR"  # ICD-10-PCS (Institutional)
    REVENUE_CODE = "NU"  # Revenue Code


class ClaimAdjustmentReasonCode(str, Enum):
    """Common claim adjustment reason codes (CARC)."""

    DEDUCTIBLE = "1"  # Deductible Amount
    COINSURANCE = "2"  # Coinsurance Amount
    COPAY = "3"  # Copay Amount
    NOT_COVERED = "96"  # Not covered
    DUPLICATE = "18"  # Duplicate claim
    TIMELY_FILING = "29"  # Timely filing
    BUNDLED = "97"  # Bundled service


class RemittanceAdviceRemarkCode(str, Enum):
    """Common remittance advice remark codes (RARC)."""

    NO_ACTION = "N1"  # No action required
    ALERT_INFORMATIONAL = "N7"  # Alert - informational
    ADDITIONAL_INFO = "N30"  # Additional information requested
    PATIENT_RESPONSIBILITY = "N130"  # Patient responsibility


class EntityTypeQualifier(str, Enum):
    """Entity type qualifiers."""

    PERSON = "1"
    NON_PERSON = "2"


class X12EntityRole(str, Enum):
    """Role of an X12 entity in a transaction.

    Used to distinguish between different provider types in a single
    unified X12Entity model instead of separate classes.
    """

    BILLING = "billing"  # Billing provider (NM1*85)
    RENDERING = "rendering"  # Rendering/performing provider (NM1*82)
    REFERRING = "referring"  # Referring provider (NM1*DN)
    PAY_TO = "pay_to"  # Pay-to provider (NM1*87)
    FACILITY = "facility"  # Service facility (NM1*77)
    ATTENDING = "attending"  # Attending physician
    OPERATING = "operating"  # Operating physician
    SUPERVISING = "supervising"  # Supervising provider


class IdentificationCodeQualifier(str, Enum):
    """Identification code qualifiers."""

    NPI = "XX"  # National Provider Identifier
    TAX_ID = "FI"  # Federal Tax ID
    SSN = "SY"  # Social Security Number
    MEMBER_ID = "MI"  # Member Identification Number
    PAYER_ID = "PI"  # Payer Identification


# ============================================================================
# Base Models
# ============================================================================


class X12Address(BaseModel):
    """Address information (N3/N4 segments)."""

    address_line_1: str = Field(..., max_length=55, description="Street address line 1")
    address_line_2: str | None = Field(None, max_length=55, description="Street address line 2")
    city: str = Field(..., max_length=30, description="City name")
    state: str = Field(..., min_length=2, max_length=2, description="State code")
    postal_code: str = Field(..., max_length=15, description="ZIP/postal code")
    country_code: str = Field("US", max_length=3, description="Country code")


class X12ContactInfo(BaseModel):
    """Contact information (PER segment)."""

    contact_name: str | None = Field(None, max_length=60, description="Contact name")
    phone: str | None = Field(None, max_length=256, description="Phone number")
    fax: str | None = Field(None, max_length=256, description="Fax number")
    email: str | None = Field(None, max_length=256, description="Email address")


class X12Identifier(BaseModel):
    """Entity identifier."""

    qualifier: IdentificationCodeQualifier = Field(..., description="ID type qualifier")
    value: str = Field(..., max_length=80, description="Identifier value")


# ============================================================================
# Provider Models
# ============================================================================


class X12Entity(BaseModel):
    """Unified healthcare entity model for all provider types.

    This single model replaces X12Provider, X12RenderingProvider, and
    X12ReferringProvider by using a role field to distinguish entity types.
    Different roles may use different subsets of fields.

    Roles and typical field usage:
    - BILLING: Full provider info (org or person, address, tax_id, contact)
    - RENDERING: Person name, NPI, taxonomy_code
    - REFERRING: Person name, NPI
    - PAY_TO: Same as BILLING
    - FACILITY: Organization name, NPI, address
    """

    role: X12EntityRole = Field(
        X12EntityRole.BILLING,
        description="Role of this entity in the transaction"
    )
    entity_type: EntityTypeQualifier = Field(
        EntityTypeQualifier.NON_PERSON,
        description="Entity type (person or organization)"
    )
    organization_name: str | None = Field(None, max_length=60, description="Organization name")
    last_name: str | None = Field(None, max_length=60, description="Individual last name")
    first_name: str | None = Field(None, max_length=35, description="Individual first name")
    middle_name: str | None = Field(None, max_length=25, description="Individual middle name")
    suffix: str | None = Field(None, max_length=10, description="Name suffix")
    npi: str = Field(..., min_length=10, max_length=10, description="National Provider Identifier")
    tax_id: str | None = Field(None, max_length=50, description="Federal Tax ID or SSN")
    taxonomy_code: str | None = Field(None, max_length=50, description="Provider taxonomy code")
    address: X12Address | None = Field(None, description="Entity address")
    contact: X12ContactInfo | None = Field(None, description="Contact information")

    # Additional identifiers
    other_ids: list[X12Identifier] = Field(default_factory=list, description="Additional identifiers")

    @property
    def display_name(self) -> str:
        """Get display name based on entity type."""
        if self.entity_type == EntityTypeQualifier.NON_PERSON:
            return self.organization_name or "Unknown Organization"
        parts = [self.last_name or "", self.first_name or ""]
        return ", ".join(p for p in parts if p) or "Unknown"


# Type aliases for backwards compatibility
X12Provider = X12Entity
X12RenderingProvider = X12Entity
X12ReferringProvider = X12Entity


# ============================================================================
# Subscriber/Patient Models
# ============================================================================


class X12Subscriber(BaseModel):
    """Subscriber (insurance policyholder) information."""

    member_id: str = Field(..., max_length=80, description="Member/subscriber ID")
    last_name: str = Field(..., max_length=60, description="Last name")
    first_name: str = Field(..., max_length=35, description="First name")
    middle_name: str | None = Field(None, max_length=25, description="Middle name")
    suffix: str | None = Field(None, max_length=10, description="Name suffix")
    date_of_birth: date = Field(..., description="Date of birth")
    gender: str = Field(..., description="Gender code (M/F/U)")
    address: X12Address | None = Field(None, description="Subscriber address")

    # Insurance info
    group_number: str | None = Field(None, max_length=50, description="Group/policy number")
    relationship_code: str = Field("18", description="Relationship to subscriber (18=Self)")


class X12Patient(BaseModel):
    """Patient information (when different from subscriber)."""

    last_name: str = Field(..., max_length=60, description="Last name")
    first_name: str = Field(..., max_length=35, description="First name")
    middle_name: str | None = Field(None, max_length=25, description="Middle name")
    suffix: str | None = Field(None, max_length=10, description="Name suffix")
    date_of_birth: date = Field(..., description="Date of birth")
    gender: str = Field(..., description="Gender code (M/F/U)")
    address: X12Address | None = Field(None, description="Patient address")
    relationship_code: str = Field(..., description="Relationship to subscriber")


class X12Payer(BaseModel):
    """Payer (insurance company) information."""

    name: str = Field(..., max_length=60, description="Payer name")
    payer_id: str = Field(..., max_length=80, description="Payer identifier")
    address: X12Address | None = Field(None, description="Payer address")
    claim_filing_indicator: ClaimFilingIndicator = Field(
        ClaimFilingIndicator.COMMERCIAL,
        description="Claim filing indicator code"
    )


# ============================================================================
# Diagnosis and Procedure Models
# ============================================================================


class X12Diagnosis(BaseModel):
    """Diagnosis code (HI segment)."""

    code: str = Field(..., max_length=30, description="Diagnosis code")
    qualifier: DiagnosisCodeQualifier = Field(
        DiagnosisCodeQualifier.ICD10_CM,
        description="Code qualifier"
    )
    is_principal: bool = Field(False, description="Is principal diagnosis")
    description: str | None = Field(None, description="Code description")


class X12Procedure(BaseModel):
    """Procedure code information."""

    code: str = Field(..., max_length=48, description="Procedure code")
    qualifier: ProcedureCodeQualifier = Field(
        ProcedureCodeQualifier.CPT,
        description="Code qualifier"
    )
    modifiers: list[str] = Field(default_factory=list, description="Modifiers (max 4)")
    description: str | None = Field(None, description="Procedure description")
    procedure_date: date | None = Field(None, description="Procedure date")


# ============================================================================
# Service Line Models
# ============================================================================


class X12ServiceLine(BaseModel):
    """Service line for professional claims (SV1 segment)."""

    line_number: int = Field(..., ge=1, description="Service line number")
    procedure_code: str = Field(..., max_length=48, description="CPT/HCPCS code")
    modifiers: list[str] = Field(default_factory=list, description="Procedure modifiers")
    description: str | None = Field(None, max_length=80, description="Service description")

    # Charges
    charge_amount: Decimal = Field(..., ge=0, description="Billed charge amount")
    units: Decimal = Field(Decimal("1"), ge=0, description="Unit count")
    unit_basis_code: str = Field("UN", description="Unit basis code (UN=Units)")

    # Place and dates
    place_of_service: PlaceOfService = Field(
        PlaceOfService.OFFICE,
        description="Place of service code"
    )
    service_date_from: date = Field(..., description="Service start date")
    service_date_to: date | None = Field(None, description="Service end date")

    # Diagnosis pointers
    diagnosis_pointers: list[int] = Field(
        default_factory=list,
        description="Diagnosis code pointers (1-based index)"
    )

    # Rendering provider (if different from billing)
    rendering_provider: X12Entity | None = Field(
        None,
        description="Rendering provider for this line"
    )

    # Revenue code (for institutional)
    revenue_code: str | None = Field(None, max_length=4, description="Revenue code")

    # NDC for drugs
    ndc_code: str | None = Field(None, max_length=50, description="National Drug Code")
    ndc_unit_code: str | None = Field(None, description="NDC unit of measurement")
    ndc_quantity: Decimal | None = Field(None, description="NDC quantity")


class X12InstitutionalServiceLine(BaseModel):
    """Service line for institutional claims (SV2 segment)."""

    line_number: int = Field(..., ge=1, description="Service line number")
    revenue_code: str = Field(..., min_length=4, max_length=4, description="Revenue code")
    procedure_code: str | None = Field(None, max_length=48, description="HCPCS/CPT code")
    procedure_qualifier: ProcedureCodeQualifier = Field(
        ProcedureCodeQualifier.CPT,
        description="Procedure code qualifier"
    )
    modifiers: list[str] = Field(default_factory=list, description="Procedure modifiers")
    description: str | None = Field(None, max_length=80, description="Service description")

    # Charges
    charge_amount: Decimal = Field(..., ge=0, description="Billed charge amount")
    units: Decimal = Field(Decimal("1"), ge=0, description="Unit count")
    unit_basis_code: str = Field("UN", description="Unit basis code")

    # Dates
    service_date: date = Field(..., description="Service date")


# ============================================================================
# Claim Models
# ============================================================================


class X12ClaimLine(BaseModel):
    """A single claim line item."""

    line_number: int
    service: X12ServiceLine | X12InstitutionalServiceLine


class X12Claim(BaseModel):
    """Healthcare claim (837P/837I)."""

    # Claim identifiers
    claim_id: str = Field(default_factory=lambda: str(uuid4())[:20], description="Claim ID")
    patient_control_number: str = Field(..., max_length=38, description="Patient control number")

    # Claim type and status
    transaction_type: X12TransactionType = Field(
        X12TransactionType.PROFESSIONAL_CLAIM,
        description="Transaction type (837P or 837I)"
    )
    frequency_code: ClaimFrequencyCode = Field(
        ClaimFrequencyCode.ORIGINAL,
        description="Claim frequency code"
    )

    # Financial
    total_charge: Decimal = Field(..., ge=0, description="Total claim charge")

    # Dates
    statement_from_date: date = Field(..., description="Statement period from date")
    statement_to_date: date = Field(..., description="Statement period to date")

    # Admission info (institutional)
    admission_date: date | None = Field(None, description="Admission date")
    admission_hour: str | None = Field(None, description="Admission hour (00-23)")
    admission_type_code: str | None = Field(None, description="Admission type code")
    admission_source_code: str | None = Field(None, description="Admission source code")
    discharge_hour: str | None = Field(None, description="Discharge hour")
    patient_status_code: str | None = Field(None, description="Patient status code")

    # Place of service
    facility_type_code: str | None = Field(None, description="Facility type code")
    place_of_service: PlaceOfService = Field(
        PlaceOfService.OFFICE,
        description="Place of service"
    )

    # Parties (all use unified X12Entity with different roles)
    billing_provider: X12Entity = Field(..., description="Billing provider")
    pay_to_provider: X12Entity | None = Field(None, description="Pay-to provider")
    rendering_provider: X12Entity | None = Field(None, description="Rendering provider")
    referring_provider: X12Entity | None = Field(None, description="Referring provider")
    facility: X12Entity | None = Field(None, description="Service facility")

    # Insurance
    payer: X12Payer = Field(..., description="Primary payer")
    subscriber: X12Subscriber = Field(..., description="Subscriber")
    patient: X12Patient | None = Field(None, description="Patient (if not subscriber)")

    # Diagnoses (ordered - first is principal)
    diagnoses: list[X12Diagnosis] = Field(..., min_length=1, description="Diagnosis codes")

    # Service lines
    service_lines: list[X12ServiceLine] = Field(..., min_length=1, description="Service lines")

    # Other claim info
    original_reference_number: str | None = Field(
        None,
        description="Original claim reference (for replacement/void)"
    )
    prior_authorization_number: str | None = Field(
        None,
        max_length=50,
        description="Prior authorization number"
    )
    referral_number: str | None = Field(None, max_length=50, description="Referral number")

    # Notes
    claim_note: str | None = Field(None, max_length=80, description="Claim note")


# ============================================================================
# Remittance/Payment Models
# ============================================================================


class X12Adjustment(BaseModel):
    """Claim adjustment (CAS segment)."""

    group_code: str = Field(..., description="Adjustment group code (CO/PR/PI/OA/CR)")
    reason_code: str = Field(..., description="Claim adjustment reason code")
    amount: Decimal = Field(..., description="Adjustment amount")
    quantity: Decimal | None = Field(None, description="Adjustment quantity")


class X12ServicePayment(BaseModel):
    """Service line payment information (SVC segment)."""

    procedure_code: str = Field(..., description="Procedure code")
    procedure_qualifier: str = Field("HC", description="Code qualifier")
    modifiers: list[str] = Field(default_factory=list, description="Modifiers")

    charge_amount: Decimal = Field(..., description="Billed amount")
    paid_amount: Decimal = Field(..., description="Paid amount")
    allowed_amount: Decimal | None = Field(None, description="Allowed amount")

    units_billed: Decimal | None = Field(None, description="Units billed")
    units_paid: Decimal | None = Field(None, description="Units paid")

    # Adjustments
    adjustments: list[X12Adjustment] = Field(default_factory=list, description="Line adjustments")

    # Dates
    service_date: date | None = Field(None, description="Service date")

    # Remarks
    remark_codes: list[str] = Field(default_factory=list, description="Remark codes")


class X12ClaimPayment(BaseModel):
    """Claim-level payment information (CLP segment)."""

    patient_control_number: str = Field(..., description="Patient control number")
    claim_status_code: str = Field(..., description="Claim status (1=Processed, 2=Denied, etc)")

    # Amounts
    charge_amount: Decimal = Field(..., description="Total charges")
    paid_amount: Decimal = Field(..., description="Total paid")
    patient_responsibility: Decimal = Field(Decimal("0"), description="Patient responsibility")

    # Claim filing
    claim_filing_indicator: str | None = Field(None, description="Claim filing indicator")
    payer_claim_control_number: str | None = Field(None, description="Payer claim number")
    facility_type_code: str | None = Field(None, description="Facility type code")

    # Claim adjustments
    adjustments: list[X12Adjustment] = Field(default_factory=list, description="Claim adjustments")

    # Service lines
    service_payments: list[X12ServicePayment] = Field(
        default_factory=list,
        description="Service line payments"
    )

    # Provider info
    rendering_provider_npi: str | None = Field(None, description="Rendering provider NPI")

    # Patient/Subscriber
    patient_name: str | None = Field(None, description="Patient name")
    subscriber_id: str | None = Field(None, description="Subscriber ID")


class X12Payment(BaseModel):
    """Payment transaction (BPR segment)."""

    transaction_handling_code: str = Field("I", description="Payment handling (I=Remit only)")
    payment_amount: Decimal = Field(..., description="Total payment amount")
    credit_debit_flag: str = Field("C", description="Credit or debit (C=Credit)")
    payment_method: str = Field("CHK", description="Payment method (CHK/ACH/NON)")
    payment_format: str | None = Field(None, description="Payment format code")

    # Bank info (for ACH)
    sender_dfi_id_qualifier: str | None = Field(None, description="Sender bank qualifier")
    sender_dfi_id: str | None = Field(None, description="Sender bank routing")
    sender_account_qualifier: str | None = Field(None, description="Sender account type")
    sender_account_number: str | None = Field(None, description="Sender account")

    receiver_dfi_id_qualifier: str | None = Field(None, description="Receiver bank qualifier")
    receiver_dfi_id: str | None = Field(None, description="Receiver bank routing")
    receiver_account_qualifier: str | None = Field(None, description="Receiver account type")
    receiver_account_number: str | None = Field(None, description="Receiver account")

    # Check info
    check_number: str | None = Field(None, description="Check number")

    # Dates
    effective_date: date = Field(..., description="Payment effective date")


class X12Remittance(BaseModel):
    """Electronic remittance advice (835)."""

    # Transaction identifiers
    transaction_id: str = Field(
        default_factory=lambda: str(uuid4())[:20],
        description="Transaction ID"
    )

    # Payment info
    payment: X12Payment = Field(..., description="Payment transaction info")

    # Payer info
    payer_name: str = Field(..., description="Payer name")
    payer_id: str = Field(..., description="Payer ID")
    payer_address: X12Address | None = Field(None, description="Payer address")
    payer_contact: X12ContactInfo | None = Field(None, description="Payer contact")

    # Payee info
    payee_name: str = Field(..., description="Payee name")
    payee_npi: str = Field(..., description="Payee NPI")
    payee_tax_id: str | None = Field(None, description="Payee Tax ID")
    payee_address: X12Address | None = Field(None, description="Payee address")

    # Claim payments
    claims: list[X12ClaimPayment] = Field(default_factory=list, description="Claim payments")

    # Provider level adjustments
    provider_adjustments: list[X12Adjustment] = Field(
        default_factory=list,
        description="Provider-level adjustments"
    )

    # Totals
    total_claims: int = Field(0, description="Total claims in remittance")
    total_charge_amount: Decimal = Field(Decimal("0"), description="Total charges")
    total_paid_amount: Decimal = Field(Decimal("0"), description="Total paid")


# ============================================================================
# Interchange and Functional Group Models
# ============================================================================


class X12InterchangeHeader(BaseModel):
    """Interchange envelope header (ISA segment)."""

    authorization_qualifier: str = Field("00", max_length=2)
    authorization_info: str = Field("          ", max_length=10)  # 10 spaces
    security_qualifier: str = Field("00", max_length=2)
    security_info: str = Field("          ", max_length=10)  # 10 spaces
    sender_qualifier: str = Field("ZZ", max_length=2)
    sender_id: str = Field(..., max_length=15)
    receiver_qualifier: str = Field("ZZ", max_length=2)
    receiver_id: str = Field(..., max_length=15)
    interchange_date: date = Field(default_factory=date.today)
    interchange_time: str = Field(default_factory=lambda: datetime.now().strftime("%H%M"))
    repetition_separator: str = Field("^", max_length=1)
    version: str = Field("00501", max_length=5)
    control_number: str = Field(..., max_length=9)
    acknowledgment_requested: str = Field("0", max_length=1)
    usage_indicator: str = Field("P", max_length=1)  # P=Production, T=Test
    component_separator: str = Field(":", max_length=1)


class X12FunctionalGroupHeader(BaseModel):
    """Functional group header (GS segment)."""

    functional_id: str = Field(..., max_length=2)  # HC for 837
    sender_id: str = Field(..., max_length=15)
    receiver_id: str = Field(..., max_length=15)
    group_date: date = Field(default_factory=date.today)
    group_time: str = Field(default_factory=lambda: datetime.now().strftime("%H%M%S"))
    group_control_number: str = Field(..., max_length=9)
    responsible_agency: str = Field("X", max_length=2)
    version: str = Field("005010X222A1", max_length=12)  # 837P version


class X12TransactionSetHeader(BaseModel):
    """Transaction set header (ST segment)."""

    transaction_set_id: str = Field(..., max_length=3)  # 837 or 835
    transaction_set_control: str = Field(..., max_length=9)
    implementation_convention: str | None = Field(None, max_length=35)


class X12Envelope(BaseModel):
    """Complete X12 interchange envelope."""

    interchange_header: X12InterchangeHeader
    functional_groups: list["X12FunctionalGroup"] = Field(default_factory=list)


class X12FunctionalGroup(BaseModel):
    """Functional group containing transaction sets."""

    header: X12FunctionalGroupHeader
    transaction_sets: list["X12TransactionSet"] = Field(default_factory=list)


class X12TransactionSet(BaseModel):
    """A single transaction set (claim or remittance)."""

    header: X12TransactionSetHeader
    claim: X12Claim | None = None
    remittance: X12Remittance | None = None


# ============================================================================
# Validation Result Models
# ============================================================================


class X12ValidationError(BaseModel):
    """Validation error details."""

    segment: str = Field(..., description="Segment identifier")
    element: str | None = Field(None, description="Element position")
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    severity: str = Field("error", description="Severity (error/warning)")


class X12ValidationResult(BaseModel):
    """Result of X12 validation."""

    is_valid: bool = Field(..., description="Overall validation result")
    transaction_type: X12TransactionType | None = Field(None, description="Transaction type")
    errors: list[X12ValidationError] = Field(default_factory=list, description="Errors found")
    warnings: list[X12ValidationError] = Field(default_factory=list, description="Warnings")
    segment_count: int = Field(0, description="Total segments parsed")


# ============================================================================
# Parse Result Models
# ============================================================================


class X12ParseResult(BaseModel):
    """Result of parsing an X12 file."""

    success: bool = Field(..., description="Parse successful")
    transaction_type: X12TransactionType | None = Field(None, description="Transaction type")
    claims: list[X12Claim] = Field(default_factory=list, description="Parsed claims")
    remittances: list[X12Remittance] = Field(default_factory=list, description="Parsed remittances")
    errors: list[str] = Field(default_factory=list, description="Parse errors")
    raw_segments: list[str] = Field(default_factory=list, description="Raw segment data")


# ============================================================================
# Generation Result Models
# ============================================================================


class X12GenerationResult(BaseModel):
    """Result of generating X12 content."""

    success: bool = Field(..., description="Generation successful")
    x12_content: str = Field("", description="Generated X12 content")
    transaction_type: X12TransactionType = Field(..., description="Transaction type")
    segment_count: int = Field(0, description="Number of segments generated")
    errors: list[str] = Field(default_factory=list, description="Generation errors")
