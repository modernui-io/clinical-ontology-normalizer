"""X12 EDI API Endpoints.

This module provides REST API endpoints for X12 EDI operations:
- Parse X12 files to JSON
- Generate 837P (Professional Claims)
- Generate 837I (Institutional Claims)
- Validate X12 files
- Map internal data to X12 format

These endpoints enable integration with clearinghouses, payers,
and practice management systems.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.models.x12 import (
    ClaimFilingIndicator,
    ClaimFrequencyCode,
    PlaceOfService,
    X12Claim,
    X12ClaimPayment,
    X12Diagnosis,
    X12Entity,
    X12EntityRole,
    X12GenerationResult,
    X12ParseResult,
    X12Payer,
    X12Payment,
    X12Remittance,
    X12ServiceLine,
    X12Subscriber,
    X12TransactionType,
    X12ValidationResult,
)
from app.services.x12_service import get_x12_service
from app.services.x12_mapper import get_x12_mapper_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/x12", tags=["x12"])


# ============================================================================
# Request/Response Models
# ============================================================================


class X12ParseRequest(BaseModel):
    """Request to parse X12 content."""

    content: str = Field(..., description="Raw X12 EDI content")


class X12ParseResponse(BaseModel):
    """Response from X12 parsing."""

    success: bool = Field(..., description="Whether parsing succeeded")
    transaction_type: str | None = Field(None, description="Detected transaction type")
    claim_count: int = Field(0, description="Number of claims parsed")
    remittance_count: int = Field(0, description="Number of remittances parsed")
    errors: list[str] = Field(default_factory=list, description="Parse errors")
    claims: list[dict[str, Any]] = Field(default_factory=list, description="Parsed claims")
    remittances: list[dict[str, Any]] = Field(default_factory=list, description="Parsed remittances")


class X12ValidateRequest(BaseModel):
    """Request to validate X12 content."""

    content: str = Field(..., description="Raw X12 EDI content")


class X12ValidateResponse(BaseModel):
    """Response from X12 validation."""

    is_valid: bool = Field(..., description="Whether content is valid")
    transaction_type: str | None = Field(None, description="Detected transaction type")
    segment_count: int = Field(0, description="Number of segments")
    error_count: int = Field(0, description="Number of errors")
    warning_count: int = Field(0, description="Number of warnings")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="Validation errors")
    warnings: list[dict[str, Any]] = Field(default_factory=list, description="Validation warnings")


class ProviderInput(BaseModel):
    """Provider information input."""

    npi: str = Field(..., min_length=10, max_length=10, description="National Provider Identifier")
    name: str = Field(..., description="Provider or organization name")
    tax_id: str | None = Field(None, description="Federal Tax ID")
    taxonomy_code: str | None = Field(None, description="Provider taxonomy code")
    address_line_1: str | None = Field(None, description="Street address")
    address_line_2: str | None = Field(None, description="Address line 2")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, min_length=2, max_length=2, description="State code")
    zip_code: str | None = Field(None, description="ZIP code")
    phone: str | None = Field(None, description="Phone number")


class PayerInput(BaseModel):
    """Payer information input."""

    payer_id: str = Field(..., description="Payer identifier")
    payer_name: str = Field(..., description="Payer name")
    payer_type: str = Field("commercial", description="Payer type (medicare, medicaid, commercial)")
    group_number: str | None = Field(None, description="Group/policy number")


class PatientInput(BaseModel):
    """Patient information input."""

    patient_id: str = Field(..., description="Patient identifier")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    middle_name: str | None = Field(None, description="Middle name")
    date_of_birth: date = Field(..., description="Date of birth")
    gender: str = Field("U", description="Gender (M/F/U)")
    address_line_1: str | None = Field(None, description="Street address")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State code")
    zip_code: str | None = Field(None, description="ZIP code")


class DiagnosisInput(BaseModel):
    """Diagnosis code input."""

    code: str = Field(..., description="ICD-10 diagnosis code")
    description: str | None = Field(None, description="Diagnosis description")
    is_principal: bool = Field(False, description="Is principal diagnosis")


class ServiceLineInput(BaseModel):
    """Service line input."""

    line_number: int = Field(..., ge=1, description="Service line number")
    procedure_code: str = Field(..., description="CPT/HCPCS code")
    modifiers: list[str] = Field(default_factory=list, description="Procedure modifiers")
    description: str | None = Field(None, description="Service description")
    charge_amount: float = Field(..., ge=0, description="Charge amount")
    units: float = Field(1, ge=0, description="Number of units")
    place_of_service: str = Field("office", description="Place of service")
    service_date: date = Field(..., description="Service date")
    service_date_end: date | None = Field(None, description="Service end date")
    diagnosis_codes: list[str] = Field(default_factory=list, description="Linked diagnosis codes")
    rendering_provider_npi: str | None = Field(None, description="Rendering provider NPI")
    revenue_code: str | None = Field(None, description="Revenue code (institutional)")


class ClaimInput(BaseModel):
    """Healthcare claim input for X12 generation."""

    claim_id: str = Field(..., description="Unique claim identifier")
    patient: PatientInput = Field(..., description="Patient information")
    billing_provider: ProviderInput = Field(..., description="Billing provider")
    payer: PayerInput = Field(..., description="Insurance payer")

    # Subscriber info
    subscriber_id: str | None = Field(None, description="Subscriber/member ID")
    relationship_to_subscriber: str = Field("self", description="Patient's relationship to subscriber")

    # Clinical data
    diagnoses: list[DiagnosisInput] = Field(..., min_length=1, description="Diagnosis codes")
    service_lines: list[ServiceLineInput] = Field(..., min_length=1, description="Service lines")

    # Dates
    service_date: date | None = Field(None, description="Statement from date")
    service_date_end: date | None = Field(None, description="Statement to date")
    admission_date: date | None = Field(None, description="Admission date (institutional)")

    # Claim type
    claim_type: str = Field("professional", description="Claim type (professional/institutional)")
    claim_frequency: str = Field("original", description="Claim frequency (original/replacement/void)")

    # Additional info
    prior_auth_number: str | None = Field(None, description="Prior authorization number")
    referral_number: str | None = Field(None, description="Referral number")
    referring_provider_npi: str | None = Field(None, description="Referring provider NPI")
    referring_provider_name: str | None = Field(None, description="Referring provider name")


class X12GenerateResponse(BaseModel):
    """Response from X12 generation."""

    success: bool = Field(..., description="Whether generation succeeded")
    transaction_type: str = Field(..., description="Transaction type generated")
    segment_count: int = Field(0, description="Number of segments")
    x12_content: str = Field("", description="Generated X12 content")
    errors: list[str] = Field(default_factory=list, description="Generation errors")


class CodeLookupResponse(BaseModel):
    """Response for code lookup."""

    code: str = Field(..., description="Code looked up")
    description: str = Field(..., description="Code description")
    code_type: str = Field(..., description="Type of code")


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/parse", response_model=X12ParseResponse)
async def parse_x12(request: X12ParseRequest) -> X12ParseResponse:
    """Parse X12 EDI content to JSON.

    This endpoint parses raw X12 content (837P, 837I, or 835) and returns
    structured JSON data representing the claims or remittances.

    Args:
        request: Request containing raw X12 content

    Returns:
        Parsed claims and/or remittances in JSON format.
    """
    logger.info("Parsing X12 content")

    service = get_x12_service()
    result = service.parse(request.content)

    # Convert claims to dicts
    claims_dict = []
    for claim in result.claims:
        claims_dict.append(_claim_to_dict(claim))

    # Convert remittances to dicts
    remittances_dict = []
    for remit in result.remittances:
        remittances_dict.append(_remittance_to_dict(remit))

    return X12ParseResponse(
        success=result.success,
        transaction_type=result.transaction_type.value if result.transaction_type else None,
        claim_count=len(result.claims),
        remittance_count=len(result.remittances),
        errors=result.errors,
        claims=claims_dict,
        remittances=remittances_dict,
    )


@router.post("/parse/file", response_model=X12ParseResponse)
async def parse_x12_file(file: UploadFile = File(...)) -> X12ParseResponse:
    """Parse X12 file upload to JSON.

    This endpoint accepts an X12 file upload and parses it to JSON.

    Args:
        file: Uploaded X12 file

    Returns:
        Parsed claims and/or remittances in JSON format.
    """
    logger.info(f"Parsing X12 file: {file.filename}")

    content = await file.read()
    content_str = content.decode("utf-8")

    service = get_x12_service()
    result = service.parse(content_str)

    claims_dict = [_claim_to_dict(claim) for claim in result.claims]
    remittances_dict = [_remittance_to_dict(remit) for remit in result.remittances]

    return X12ParseResponse(
        success=result.success,
        transaction_type=result.transaction_type.value if result.transaction_type else None,
        claim_count=len(result.claims),
        remittance_count=len(result.remittances),
        errors=result.errors,
        claims=claims_dict,
        remittances=remittances_dict,
    )


@router.post("/validate", response_model=X12ValidateResponse)
async def validate_x12(request: X12ValidateRequest) -> X12ValidateResponse:
    """Validate X12 EDI content against standards.

    This endpoint validates X12 content for:
    - Structural integrity (ISA/IEA, GS/GE, ST/SE)
    - Required segments
    - Data element formats (NPI, dates, codes)
    - Business rules

    Args:
        request: Request containing X12 content to validate

    Returns:
        Validation result with errors and warnings.
    """
    logger.info("Validating X12 content")

    service = get_x12_service()
    result = service.validate(request.content)

    errors = [
        {
            "segment": e.segment,
            "element": e.element,
            "code": e.code,
            "message": e.message,
            "severity": e.severity,
        }
        for e in result.errors
    ]

    warnings = [
        {
            "segment": w.segment,
            "element": w.element,
            "code": w.code,
            "message": w.message,
            "severity": w.severity,
        }
        for w in result.warnings
    ]

    return X12ValidateResponse(
        is_valid=result.is_valid,
        transaction_type=result.transaction_type.value if result.transaction_type else None,
        segment_count=result.segment_count,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors,
        warnings=warnings,
    )


@router.post("/generate/837p", response_model=X12GenerateResponse)
async def generate_837p(request: ClaimInput) -> X12GenerateResponse:
    """Generate 837P (Professional Claim) X12 transaction.

    This endpoint generates an 837P transaction from structured claim data.
    The 837P is used for professional services (CMS-1500 equivalent).

    Args:
        request: Claim data for generation

    Returns:
        Generated X12 content.
    """
    logger.info(f"Generating 837P for claim: {request.claim_id}")

    mapper = get_x12_mapper_service()
    x12_service = get_x12_service()

    # Convert input to internal format
    claim_dict = request.model_dump()
    internal_claim = mapper.dict_to_internal_claim(claim_dict)

    # Convert to X12 format
    x12_claim = mapper.internal_to_x12_claim(
        internal_claim,
        X12TransactionType.PROFESSIONAL_CLAIM,
    )

    # Generate X12 content
    result = x12_service.generate_837p(x12_claim)

    return X12GenerateResponse(
        success=result.success,
        transaction_type=result.transaction_type.value,
        segment_count=result.segment_count,
        x12_content=result.x12_content,
        errors=result.errors,
    )


@router.post("/generate/837i", response_model=X12GenerateResponse)
async def generate_837i(request: ClaimInput) -> X12GenerateResponse:
    """Generate 837I (Institutional Claim) X12 transaction.

    This endpoint generates an 837I transaction from structured claim data.
    The 837I is used for institutional services (UB-04 equivalent).

    Args:
        request: Claim data for generation

    Returns:
        Generated X12 content.
    """
    logger.info(f"Generating 837I for claim: {request.claim_id}")

    mapper = get_x12_mapper_service()
    x12_service = get_x12_service()

    # Convert input to internal format
    claim_dict = request.model_dump()
    internal_claim = mapper.dict_to_internal_claim(claim_dict)

    # Convert to X12 format
    x12_claim = mapper.internal_to_x12_claim(
        internal_claim,
        X12TransactionType.INSTITUTIONAL_CLAIM,
    )

    # Generate X12 content
    result = x12_service.generate_837i(x12_claim)

    return X12GenerateResponse(
        success=result.success,
        transaction_type=result.transaction_type.value,
        segment_count=result.segment_count,
        x12_content=result.x12_content,
        errors=result.errors,
    )


@router.get("/codes/pos/{code}", response_model=CodeLookupResponse)
async def lookup_place_of_service(code: str) -> CodeLookupResponse:
    """Look up place of service code.

    Args:
        code: Place of service code (e.g., "11" for Office)

    Returns:
        Code description.
    """
    mapper = get_x12_mapper_service()
    description = mapper.get_place_of_service_description(code)

    return CodeLookupResponse(
        code=code,
        description=description,
        code_type="Place of Service",
    )


@router.get("/codes/revenue/{code}", response_model=CodeLookupResponse)
async def lookup_revenue_code(code: str) -> CodeLookupResponse:
    """Look up revenue code.

    Args:
        code: Revenue code (e.g., "0450" for Emergency Room)

    Returns:
        Code description.
    """
    mapper = get_x12_mapper_service()
    description = mapper.get_revenue_code_description(code)

    return CodeLookupResponse(
        code=code,
        description=description,
        code_type="Revenue Code",
    )


@router.get("/codes/adjustment/{code}", response_model=CodeLookupResponse)
async def lookup_adjustment_code(code: str) -> CodeLookupResponse:
    """Look up claim adjustment reason code (CARC).

    Args:
        code: Adjustment reason code (e.g., "1" for Deductible)

    Returns:
        Code description.
    """
    mapper = get_x12_mapper_service()
    description = mapper.get_adjustment_description(code)

    return CodeLookupResponse(
        code=code,
        description=description,
        code_type="Claim Adjustment Reason Code",
    )


@router.post("/convert/icd10")
async def format_icd10(code: str) -> dict[str, str]:
    """Format ICD-10 code with proper dot placement.

    Args:
        code: ICD-10 code (with or without dot)

    Returns:
        Formatted code.
    """
    mapper = get_x12_mapper_service()
    formatted = mapper.format_icd10(code)

    return {
        "original": code,
        "formatted": formatted,
    }


@router.post("/convert/npi")
async def normalize_npi(npi: str) -> dict[str, str]:
    """Normalize NPI to standard format.

    Args:
        npi: NPI string

    Returns:
        Normalized NPI.
    """
    mapper = get_x12_mapper_service()
    normalized = mapper.normalize_npi(npi)

    return {
        "original": npi,
        "normalized": normalized,
        "valid": len(normalized) == 10 and normalized.isdigit(),
    }


@router.get("/stats")
async def get_x12_stats() -> dict[str, Any]:
    """Get X12 service statistics.

    Returns:
        Service statistics including supported transactions and mappings.
    """
    x12_service = get_x12_service()
    mapper = get_x12_mapper_service()

    return {
        "x12_service": x12_service.get_stats(),
        "mapper_service": mapper.get_stats(),
    }


# ============================================================================
# Helper Functions
# ============================================================================


def _claim_to_dict(claim: X12Claim) -> dict[str, Any]:
    """Convert X12Claim to dictionary."""
    return {
        "claim_id": claim.claim_id,
        "patient_control_number": claim.patient_control_number,
        "transaction_type": claim.transaction_type.value,
        "frequency_code": claim.frequency_code.value,
        "total_charge": str(claim.total_charge),
        "statement_from_date": claim.statement_from_date.isoformat(),
        "statement_to_date": claim.statement_to_date.isoformat(),
        "admission_date": claim.admission_date.isoformat() if claim.admission_date else None,
        "billing_provider": {
            "npi": claim.billing_provider.npi,
            "name": claim.billing_provider.organization_name or f"{claim.billing_provider.last_name}, {claim.billing_provider.first_name}",
            "tax_id": claim.billing_provider.tax_id,
        },
        "payer": {
            "name": claim.payer.name,
            "payer_id": claim.payer.payer_id,
            "claim_filing_indicator": claim.payer.claim_filing_indicator.value,
        },
        "subscriber": {
            "member_id": claim.subscriber.member_id,
            "name": f"{claim.subscriber.last_name}, {claim.subscriber.first_name}",
            "date_of_birth": claim.subscriber.date_of_birth.isoformat(),
            "gender": claim.subscriber.gender,
            "relationship_code": claim.subscriber.relationship_code,
        },
        "diagnoses": [
            {
                "code": diag.code,
                "qualifier": diag.qualifier.value,
                "is_principal": diag.is_principal,
            }
            for diag in claim.diagnoses
        ],
        "service_lines": [
            {
                "line_number": line.line_number,
                "procedure_code": line.procedure_code,
                "modifiers": line.modifiers,
                "charge_amount": str(line.charge_amount),
                "units": str(line.units),
                "place_of_service": line.place_of_service.value,
                "service_date_from": line.service_date_from.isoformat(),
                "service_date_to": line.service_date_to.isoformat() if line.service_date_to else None,
                "diagnosis_pointers": line.diagnosis_pointers,
                "revenue_code": line.revenue_code,
            }
            for line in claim.service_lines
        ],
        "prior_authorization_number": claim.prior_authorization_number,
        "referral_number": claim.referral_number,
    }


def _remittance_to_dict(remittance: X12Remittance) -> dict[str, Any]:
    """Convert X12Remittance to dictionary."""
    return {
        "transaction_id": remittance.transaction_id,
        "payer": {
            "name": remittance.payer_name,
            "payer_id": remittance.payer_id,
        },
        "payee": {
            "name": remittance.payee_name,
            "npi": remittance.payee_npi,
        },
        "payment": {
            "amount": str(remittance.payment.payment_amount),
            "method": remittance.payment.payment_method,
            "check_number": remittance.payment.check_number,
            "effective_date": remittance.payment.effective_date.isoformat(),
        },
        "totals": {
            "total_claims": remittance.total_claims,
            "total_charge_amount": str(remittance.total_charge_amount),
            "total_paid_amount": str(remittance.total_paid_amount),
        },
        "claims": [
            {
                "patient_control_number": cp.patient_control_number,
                "claim_status_code": cp.claim_status_code,
                "charge_amount": str(cp.charge_amount),
                "paid_amount": str(cp.paid_amount),
                "patient_responsibility": str(cp.patient_responsibility),
                "adjustments": [
                    {
                        "group_code": adj.group_code,
                        "reason_code": adj.reason_code,
                        "amount": str(adj.amount),
                    }
                    for adj in cp.adjustments
                ],
                "service_payments": [
                    {
                        "procedure_code": svc.procedure_code,
                        "charge_amount": str(svc.charge_amount),
                        "paid_amount": str(svc.paid_amount),
                        "adjustments": [
                            {
                                "group_code": adj.group_code,
                                "reason_code": adj.reason_code,
                                "amount": str(adj.amount),
                            }
                            for adj in svc.adjustments
                        ],
                    }
                    for svc in cp.service_payments
                ],
            }
            for cp in remittance.claims
        ],
    }
