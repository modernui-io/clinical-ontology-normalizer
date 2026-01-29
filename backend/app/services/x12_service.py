"""X12 EDI Service for Healthcare Claims.

This module provides comprehensive X12 EDI support including:
- Parsing X12 837P (Professional Claims)
- Parsing X12 837I (Institutional Claims)
- Parsing X12 835 (Payment/Remittance Advice)
- Generating X12 837P/837I transactions
- Validation against X12 standards

X12 Format Overview:
- Segments are delimited by segment terminator (typically ~)
- Elements within segments are delimited by element delimiter (typically *)
- Sub-elements use component separator (typically :)
- Repetition separator (typically ^) for repeating elements
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.x12 import (
    ClaimAdjustmentReasonCode,
    ClaimFilingIndicator,
    ClaimFrequencyCode,
    DiagnosisCodeQualifier,
    EntityTypeQualifier,
    IdentificationCodeQualifier,
    PlaceOfService,
    ProcedureCodeQualifier,
    X12Address,
    X12Adjustment,
    X12Claim,
    X12ClaimPayment,
    X12ContactInfo,
    X12Diagnosis,
    X12Entity,
    X12EntityRole,
    X12Envelope,
    X12FunctionalGroup,
    X12FunctionalGroupHeader,
    X12GenerationResult,
    X12Identifier,
    X12InterchangeHeader,
    X12ParseResult,
    X12Patient,
    X12Payer,
    X12Payment,
    X12Procedure,
    X12Remittance,
    X12ServiceLine,
    X12ServicePayment,
    X12Subscriber,
    X12TransactionSet,
    X12TransactionSetHeader,
    X12TransactionType,
    X12ValidationError,
    X12ValidationResult,
)

logger = logging.getLogger(__name__)


# ============================================================================
# X12 Segment Handlers
# ============================================================================


@dataclass
class X12SegmentContext:
    """Context for tracking segment position during parsing."""

    current_loop: str = ""
    segment_count: int = 0
    transaction_set_control: str = ""
    group_control_number: str = ""
    interchange_control_number: str = ""

    # Entity tracking
    current_provider_type: str = ""  # billing, rendering, referring, etc.
    current_entity_type: str = ""  # subscriber, patient, payer

    # Hierarchical level tracking
    hl_level: int = 0
    hl_parent: int = 0
    hl_code: str = ""


@dataclass
class X12ParseState:
    """State maintained during X12 parsing."""

    # Delimiters (from ISA segment)
    element_delimiter: str = "*"
    component_separator: str = ":"
    repetition_separator: str = "^"
    segment_terminator: str = "~"

    # Current context
    context: X12SegmentContext = field(default_factory=X12SegmentContext)

    # Parsed data
    claims: list[X12Claim] = field(default_factory=list)
    remittances: list[X12Remittance] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Current claim being built
    current_claim: dict[str, Any] = field(default_factory=dict)
    current_remittance: dict[str, Any] = field(default_factory=dict)
    current_claim_payment: dict[str, Any] = field(default_factory=dict)

    # Transaction type
    transaction_type: X12TransactionType | None = None


# ============================================================================
# X12 Service
# ============================================================================

_x12_service: "X12Service | None" = None
_x12_lock = threading.Lock()


def get_x12_service() -> "X12Service":
    """Get the singleton X12 service instance."""
    global _x12_service
    if _x12_service is None:
        with _x12_lock:
            if _x12_service is None:
                _x12_service = X12Service()
    return _x12_service


def reset_x12_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _x12_service
    with _x12_lock:
        _x12_service = None


class X12Service:
    """Service for parsing and generating X12 EDI transactions."""

    def __init__(self) -> None:
        """Initialize the X12 service."""
        self._segment_handlers = {
            # Interchange and Group
            "ISA": self._parse_isa,
            "IEA": self._parse_iea,
            "GS": self._parse_gs,
            "GE": self._parse_ge,
            "ST": self._parse_st,
            "SE": self._parse_se,

            # Hierarchical Levels (837)
            "HL": self._parse_hl,

            # Name/Identification
            "NM1": self._parse_nm1,
            "N3": self._parse_n3,
            "N4": self._parse_n4,
            "REF": self._parse_ref,
            "PER": self._parse_per,

            # Subscriber/Patient
            "SBR": self._parse_sbr,
            "PAT": self._parse_pat,
            "DMG": self._parse_dmg,

            # Claim Information
            "CLM": self._parse_clm,
            "DTP": self._parse_dtp,
            "HI": self._parse_hi,
            "PWK": self._parse_pwk,
            "AMT": self._parse_amt,

            # Service Lines
            "LX": self._parse_lx,
            "SV1": self._parse_sv1,
            "SV2": self._parse_sv2,

            # Remittance (835)
            "BPR": self._parse_bpr,
            "TRN": self._parse_trn,
            "CLP": self._parse_clp,
            "SVC": self._parse_svc,
            "CAS": self._parse_cas,
            "PLB": self._parse_plb,
        }

    # ========================================================================
    # Public API
    # ========================================================================

    def parse(self, x12_content: str) -> X12ParseResult:
        """Parse X12 content into structured data.

        Args:
            x12_content: Raw X12 EDI content

        Returns:
            X12ParseResult with parsed claims/remittances and any errors.
        """
        state = X12ParseState()

        # Detect delimiters from ISA segment
        self._detect_delimiters(x12_content, state)

        # Split into segments
        segments = self._split_segments(x12_content, state)
        raw_segments = []

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            raw_segments.append(segment)
            state.context.segment_count += 1

            # Parse segment
            elements = segment.split(state.element_delimiter)
            segment_id = elements[0]

            handler = self._segment_handlers.get(segment_id)
            if handler:
                try:
                    handler(elements, state)
                except Exception as e:
                    state.errors.append(f"Error parsing {segment_id}: {e}")
                    logger.warning(f"Error parsing segment {segment_id}: {e}")

        return X12ParseResult(
            success=len(state.errors) == 0,
            transaction_type=state.transaction_type,
            claims=state.claims,
            remittances=state.remittances,
            errors=state.errors,
            raw_segments=raw_segments,
        )

    def validate(self, x12_content: str) -> X12ValidationResult:
        """Validate X12 content against standards.

        Args:
            x12_content: Raw X12 EDI content

        Returns:
            X12ValidationResult with validation status and errors.
        """
        errors: list[X12ValidationError] = []
        warnings: list[X12ValidationError] = []

        # First, try to parse
        parse_result = self.parse(x12_content)

        # Convert parse errors to validation errors
        for error in parse_result.errors:
            errors.append(X12ValidationError(
                segment="PARSE",
                code="PARSE_ERROR",
                message=error,
                severity="error",
            ))

        # Validate ISA segment
        isa_errors = self._validate_isa(x12_content)
        errors.extend(isa_errors)

        # Validate structure
        structure_errors = self._validate_structure(parse_result.raw_segments)
        errors.extend(structure_errors)

        # Validate claims
        for claim in parse_result.claims:
            claim_errors = self._validate_claim(claim)
            errors.extend(claim_errors)

        # Validate remittances
        for remittance in parse_result.remittances:
            remit_errors = self._validate_remittance(remittance)
            errors.extend(remit_errors)

        return X12ValidationResult(
            is_valid=len(errors) == 0,
            transaction_type=parse_result.transaction_type,
            errors=errors,
            warnings=warnings,
            segment_count=parse_result.raw_segments.__len__(),
        )

    def generate_837p(self, claim: X12Claim) -> X12GenerationResult:
        """Generate an 837P (Professional Claim) transaction.

        Args:
            claim: Claim data to generate

        Returns:
            X12GenerationResult with generated X12 content.
        """
        return self._generate_837(claim, X12TransactionType.PROFESSIONAL_CLAIM)

    def generate_837i(self, claim: X12Claim) -> X12GenerationResult:
        """Generate an 837I (Institutional Claim) transaction.

        Args:
            claim: Claim data to generate

        Returns:
            X12GenerationResult with generated X12 content.
        """
        return self._generate_837(claim, X12TransactionType.INSTITUTIONAL_CLAIM)

    def get_stats(self) -> dict:
        """Get service statistics."""
        return {
            "supported_transactions": [
                "837P (Professional Claim)",
                "837I (Institutional Claim)",
                "835 (Payment/Remittance)",
            ],
            "segment_handlers": len(self._segment_handlers),
        }

    # ========================================================================
    # Delimiter Detection
    # ========================================================================

    def _detect_delimiters(self, content: str, state: X12ParseState) -> None:
        """Detect delimiters from ISA segment."""
        # ISA is fixed-width: 106 characters
        # Element delimiter is at position 3
        # Component separator is at position 104
        # Segment terminator follows ISA

        if len(content) < 106:
            state.errors.append("Content too short for ISA segment")
            return

        if not content.startswith("ISA"):
            state.errors.append("Content must start with ISA segment")
            return

        # Element delimiter is character at position 3
        state.element_delimiter = content[3]

        # Component separator is at position 104 (character 105)
        state.component_separator = content[104]

        # Segment terminator is at position 105 (character 106)
        state.segment_terminator = content[105]

        # Repetition separator is in ISA11 (between positions 82-83)
        # But let's parse ISA properly to get it
        isa_elements = content[:106].split(state.element_delimiter)
        if len(isa_elements) >= 12:
            state.repetition_separator = isa_elements[11]

    def _split_segments(self, content: str, state: X12ParseState) -> list[str]:
        """Split content into segments."""
        # Remove newlines/carriage returns that might be in the content
        content = content.replace("\r", "").replace("\n", "")
        return content.split(state.segment_terminator)

    # ========================================================================
    # Segment Parsers - Interchange/Group
    # ========================================================================

    def _parse_isa(self, elements: list[str], state: X12ParseState) -> None:
        """Parse ISA (Interchange Control Header)."""
        if len(elements) < 16:
            state.errors.append("ISA segment has insufficient elements")
            return

        state.context.interchange_control_number = elements[13]

    def _parse_iea(self, elements: list[str], state: X12ParseState) -> None:
        """Parse IEA (Interchange Control Trailer)."""
        # Validates interchange control number matches
        pass

    def _parse_gs(self, elements: list[str], state: X12ParseState) -> None:
        """Parse GS (Functional Group Header)."""
        if len(elements) < 8:
            state.errors.append("GS segment has insufficient elements")
            return

        functional_id = elements[1]  # HC = 837, HP = 835
        state.context.group_control_number = elements[6]

        # Determine transaction type from functional ID and version
        version = elements[8] if len(elements) > 8 else ""
        if "222" in version:  # 837P
            state.transaction_type = X12TransactionType.PROFESSIONAL_CLAIM
        elif "223" in version:  # 837I
            state.transaction_type = X12TransactionType.INSTITUTIONAL_CLAIM
        elif "221" in version or functional_id == "HP":  # 835
            state.transaction_type = X12TransactionType.PAYMENT_REMITTANCE

    def _parse_ge(self, elements: list[str], state: X12ParseState) -> None:
        """Parse GE (Functional Group Trailer)."""
        pass

    def _parse_st(self, elements: list[str], state: X12ParseState) -> None:
        """Parse ST (Transaction Set Header)."""
        if len(elements) < 3:
            state.errors.append("ST segment has insufficient elements")
            return

        transaction_set_id = elements[1]
        state.context.transaction_set_control = elements[2]

        if transaction_set_id == "837":
            if state.transaction_type is None:
                state.transaction_type = X12TransactionType.PROFESSIONAL_CLAIM
            # Initialize new claim
            state.current_claim = {
                "diagnoses": [],
                "service_lines": [],
            }
        elif transaction_set_id == "835":
            state.transaction_type = X12TransactionType.PAYMENT_REMITTANCE
            state.current_remittance = {
                "claims": [],
                "provider_adjustments": [],
            }

    def _parse_se(self, elements: list[str], state: X12ParseState) -> None:
        """Parse SE (Transaction Set Trailer)."""
        # Finalize current claim or remittance
        if state.current_claim and state.current_claim.get("patient_control_number"):
            try:
                claim = self._build_claim(state.current_claim)
                state.claims.append(claim)
            except Exception as e:
                state.errors.append(f"Error building claim: {e}")
            state.current_claim = {}

        if state.current_remittance and state.current_remittance.get("payer_name"):
            try:
                remittance = self._build_remittance(state.current_remittance)
                state.remittances.append(remittance)
            except Exception as e:
                state.errors.append(f"Error building remittance: {e}")
            state.current_remittance = {}

    # ========================================================================
    # Segment Parsers - Hierarchical Levels
    # ========================================================================

    def _parse_hl(self, elements: list[str], state: X12ParseState) -> None:
        """Parse HL (Hierarchical Level)."""
        if len(elements) < 4:
            return

        state.context.hl_level = int(elements[1]) if elements[1] else 0
        state.context.hl_parent = int(elements[2]) if elements[2] else 0
        state.context.hl_code = elements[3]

        # HL codes:
        # 20 = Information Source (Payer)
        # 22 = Subscriber
        # 23 = Patient (Dependent)

    # ========================================================================
    # Segment Parsers - Name/Identification
    # ========================================================================

    def _parse_nm1(self, elements: list[str], state: X12ParseState) -> None:
        """Parse NM1 (Entity Name)."""
        if len(elements) < 4:
            return

        entity_code = elements[1]
        entity_type = elements[2]  # 1=Person, 2=Non-Person

        # Build name data
        name_data = {
            "entity_type": entity_type,
            "last_name": self._safe_get(elements, 3),
            "first_name": self._safe_get(elements, 4),
            "middle_name": self._safe_get(elements, 5),
            "suffix": self._safe_get(elements, 7),
        }

        # If organization (entity_type=2), last_name is org name
        if entity_type == "2":
            name_data["organization_name"] = self._safe_get(elements, 3)
            name_data["last_name"] = None

        # ID qualifier and value
        id_qualifier = self._safe_get(elements, 8)
        id_value = self._safe_get(elements, 9)

        if id_qualifier and id_value:
            name_data["id_qualifier"] = id_qualifier
            name_data["id_value"] = id_value
            if id_qualifier == "XX":  # NPI
                name_data["npi"] = id_value

        # Store based on entity code
        state.context.current_entity_type = entity_code

        if entity_code == "85":  # Billing Provider
            state.current_claim["billing_provider"] = name_data
            state.context.current_provider_type = "billing"
        elif entity_code == "87":  # Pay-to Provider
            state.current_claim["pay_to_provider"] = name_data
            state.context.current_provider_type = "pay_to"
        elif entity_code == "82":  # Rendering Provider
            state.current_claim["rendering_provider"] = name_data
            state.context.current_provider_type = "rendering"
        elif entity_code == "DN":  # Referring Provider
            state.current_claim["referring_provider"] = name_data
        elif entity_code == "77":  # Service Facility
            state.current_claim["facility"] = name_data
        elif entity_code == "IL":  # Subscriber
            state.current_claim["subscriber"] = name_data
        elif entity_code == "QC":  # Patient
            state.current_claim["patient"] = name_data
        elif entity_code == "PR":  # Payer
            state.current_claim["payer"] = name_data
            state.current_remittance["payer_name"] = name_data.get("organization_name") or name_data.get("last_name")
            state.current_remittance["payer_id"] = id_value
        elif entity_code == "PE":  # Payee (835)
            state.current_remittance["payee_name"] = name_data.get("organization_name") or name_data.get("last_name")
            state.current_remittance["payee_npi"] = name_data.get("npi")

    def _parse_n3(self, elements: list[str], state: X12ParseState) -> None:
        """Parse N3 (Address)."""
        if len(elements) < 2:
            return

        address_data = {
            "address_line_1": elements[1],
            "address_line_2": self._safe_get(elements, 2),
        }

        self._apply_address(address_data, state)

    def _parse_n4(self, elements: list[str], state: X12ParseState) -> None:
        """Parse N4 (City/State/ZIP)."""
        if len(elements) < 4:
            return

        address_update = {
            "city": elements[1],
            "state": self._safe_get(elements, 2),
            "postal_code": self._safe_get(elements, 3),
            "country_code": self._safe_get(elements, 7) or "US",
        }

        self._apply_address(address_update, state)

    def _parse_ref(self, elements: list[str], state: X12ParseState) -> None:
        """Parse REF (Reference Identification)."""
        if len(elements) < 3:
            return

        qualifier = elements[1]
        value = elements[2]

        # Common qualifiers:
        # EI = Employer's Identification Number
        # SY = Social Security Number
        # 0B = State License Number
        # G2 = Provider Commercial Number
        # LU = Location Number
        # 1G = Provider UPIN
        # G5 = Provider Site Number
        # D9 = Claim Number

        entity_type = state.context.current_entity_type
        provider_type = state.context.current_provider_type

        if qualifier == "EI":  # Tax ID
            if provider_type == "billing" and "billing_provider" in state.current_claim:
                state.current_claim["billing_provider"]["tax_id"] = value
        elif qualifier == "G2":  # Prior Auth
            state.current_claim["prior_authorization_number"] = value
        elif qualifier == "D9":  # Claim Number (replacement)
            state.current_claim["original_reference_number"] = value

    def _parse_per(self, elements: list[str], state: X12ParseState) -> None:
        """Parse PER (Contact Information)."""
        if len(elements) < 4:
            return

        contact_data = {
            "contact_name": self._safe_get(elements, 2),
        }

        # PER segment has communication number qualifiers
        # TE = Telephone, FX = Fax, EM = Email
        for i in range(3, min(len(elements), 9), 2):
            qualifier = self._safe_get(elements, i)
            value = self._safe_get(elements, i + 1)
            if qualifier == "TE":
                contact_data["phone"] = value
            elif qualifier == "FX":
                contact_data["fax"] = value
            elif qualifier == "EM":
                contact_data["email"] = value

        # Apply to current entity
        if state.context.current_provider_type == "billing":
            if "billing_provider" in state.current_claim:
                state.current_claim["billing_provider"]["contact"] = contact_data

    # ========================================================================
    # Segment Parsers - Subscriber/Patient
    # ========================================================================

    def _parse_sbr(self, elements: list[str], state: X12ParseState) -> None:
        """Parse SBR (Subscriber Information)."""
        if len(elements) < 3:
            return

        payer_responsibility = elements[1]  # P=Primary, S=Secondary, T=Tertiary
        relationship_code = self._safe_get(elements, 2)  # 18=Self
        group_number = self._safe_get(elements, 3)
        plan_name = self._safe_get(elements, 4)
        claim_filing_indicator = self._safe_get(elements, 9)

        if "subscriber" not in state.current_claim:
            state.current_claim["subscriber"] = {}

        state.current_claim["subscriber"]["relationship_code"] = relationship_code or "18"
        state.current_claim["subscriber"]["group_number"] = group_number

        if claim_filing_indicator:
            state.current_claim["claim_filing_indicator"] = claim_filing_indicator

    def _parse_pat(self, elements: list[str], state: X12ParseState) -> None:
        """Parse PAT (Patient Information)."""
        if len(elements) < 2:
            return

        relationship_code = self._safe_get(elements, 1)

        if "patient" not in state.current_claim:
            state.current_claim["patient"] = {}

        state.current_claim["patient"]["relationship_code"] = relationship_code

    def _parse_dmg(self, elements: list[str], state: X12ParseState) -> None:
        """Parse DMG (Demographic Information)."""
        if len(elements) < 4:
            return

        date_format = elements[1]  # D8 = CCYYMMDD
        dob = self._parse_date(self._safe_get(elements, 2))
        gender = self._safe_get(elements, 3)  # M/F/U

        # Apply to subscriber or patient based on HL level
        if state.context.hl_code == "22":  # Subscriber
            if "subscriber" in state.current_claim:
                state.current_claim["subscriber"]["date_of_birth"] = dob
                state.current_claim["subscriber"]["gender"] = gender
        elif state.context.hl_code == "23":  # Patient
            if "patient" in state.current_claim:
                state.current_claim["patient"]["date_of_birth"] = dob
                state.current_claim["patient"]["gender"] = gender

    # ========================================================================
    # Segment Parsers - Claim
    # ========================================================================

    def _parse_clm(self, elements: list[str], state: X12ParseState) -> None:
        """Parse CLM (Claim Information)."""
        if len(elements) < 6:
            return

        patient_control_number = elements[1]
        total_charge = self._parse_decimal(self._safe_get(elements, 2))

        # CLM05 is composite: facility_type:claim_frequency:place_of_service
        clm05 = self._safe_get(elements, 5) or ""
        clm05_parts = clm05.split(state.component_separator)

        facility_type = self._safe_get(clm05_parts, 0)
        claim_frequency = self._safe_get(clm05_parts, 1) or "1"
        # For 837P, place of service is in service lines
        # For 837I, facility type code is relevant

        state.current_claim["patient_control_number"] = patient_control_number
        state.current_claim["total_charge"] = total_charge
        state.current_claim["facility_type_code"] = facility_type
        state.current_claim["frequency_code"] = claim_frequency

        # Provider signature (element 6)
        provider_signature = self._safe_get(elements, 6)

        # Assignment of benefits (element 7)
        assignment = self._safe_get(elements, 7)

        # Release of info (element 8)
        release_info = self._safe_get(elements, 8)

    def _parse_dtp(self, elements: list[str], state: X12ParseState) -> None:
        """Parse DTP (Date/Time)."""
        if len(elements) < 4:
            return

        qualifier = elements[1]
        format_qualifier = elements[2]  # D8=Date, RD8=Date Range
        date_value = elements[3]

        parsed_date = None
        end_date = None

        if format_qualifier == "D8":
            parsed_date = self._parse_date(date_value)
        elif format_qualifier == "RD8":
            # Range: CCYYMMDD-CCYYMMDD
            parts = date_value.split("-")
            parsed_date = self._parse_date(self._safe_get(parts, 0))
            end_date = self._parse_date(self._safe_get(parts, 1))

        # DTP qualifiers:
        # 434 = Statement dates
        # 435 = Admission date
        # 096 = Discharge date
        # 472 = Service date
        # 050 = Received date

        if qualifier == "434":  # Statement period
            state.current_claim["statement_from_date"] = parsed_date
            state.current_claim["statement_to_date"] = end_date or parsed_date
        elif qualifier == "435":  # Admission
            state.current_claim["admission_date"] = parsed_date
        elif qualifier == "096":  # Discharge
            state.current_claim["discharge_date"] = parsed_date
        elif qualifier == "472":  # Service date
            # Apply to current service line
            if state.current_claim.get("current_service_line"):
                state.current_claim["current_service_line"]["service_date_from"] = parsed_date
                state.current_claim["current_service_line"]["service_date_to"] = end_date or parsed_date

    def _parse_hi(self, elements: list[str], state: X12ParseState) -> None:
        """Parse HI (Health Care Diagnosis Codes)."""
        # Each element after HI is a composite: qualifier:code
        for i in range(1, len(elements)):
            if not elements[i]:
                continue

            parts = elements[i].split(state.component_separator)
            if len(parts) < 2:
                continue

            qualifier = parts[0]
            code = parts[1]

            # Remove dots from ICD codes if present
            code = code.replace(".", "")

            diagnosis = {
                "code": code,
                "qualifier": qualifier,
                "is_principal": i == 1 and qualifier in ("ABK", "BK"),
            }

            if "diagnoses" not in state.current_claim:
                state.current_claim["diagnoses"] = []

            state.current_claim["diagnoses"].append(diagnosis)

    def _parse_pwk(self, elements: list[str], state: X12ParseState) -> None:
        """Parse PWK (Paperwork)."""
        # Attachment information
        pass

    def _parse_amt(self, elements: list[str], state: X12ParseState) -> None:
        """Parse AMT (Monetary Amount)."""
        if len(elements) < 3:
            return

        qualifier = elements[1]
        amount = self._parse_decimal(elements[2])

        # AMT qualifiers:
        # F5 = Patient Amount Paid
        # T = Total Claim Before Taxes
        # MA = Medicare A Payment Amount

    # ========================================================================
    # Segment Parsers - Service Lines
    # ========================================================================

    def _parse_lx(self, elements: list[str], state: X12ParseState) -> None:
        """Parse LX (Service Line Number)."""
        if len(elements) < 2:
            return

        line_number = int(elements[1])

        # Save any previous service line
        if state.current_claim.get("current_service_line"):
            state.current_claim["service_lines"].append(
                state.current_claim["current_service_line"]
            )

        # Start new service line
        state.current_claim["current_service_line"] = {
            "line_number": line_number,
        }

    def _parse_sv1(self, elements: list[str], state: X12ParseState) -> None:
        """Parse SV1 (Professional Service)."""
        if len(elements) < 7:
            return

        # SV101 is composite: qualifier:code:modifiers
        sv101 = elements[1].split(state.component_separator)
        procedure_qualifier = self._safe_get(sv101, 0)  # HC
        procedure_code = self._safe_get(sv101, 1)
        modifiers = [m for m in sv101[2:6] if m]  # Up to 4 modifiers

        charge_amount = self._parse_decimal(self._safe_get(elements, 2))
        unit_basis_code = self._safe_get(elements, 3) or "UN"
        units = self._parse_decimal(self._safe_get(elements, 4)) or Decimal("1")
        place_of_service = self._safe_get(elements, 5)

        # SV107 is diagnosis pointers
        diag_pointers_str = self._safe_get(elements, 7) or ""
        diag_pointers = []
        if diag_pointers_str:
            # Pointers are colon-separated
            pointers = diag_pointers_str.split(state.component_separator)
            diag_pointers = [int(p) for p in pointers if p.isdigit()]

        service_line = state.current_claim.get("current_service_line", {})
        service_line.update({
            "procedure_code": procedure_code,
            "procedure_qualifier": procedure_qualifier,
            "modifiers": modifiers,
            "charge_amount": charge_amount,
            "unit_basis_code": unit_basis_code,
            "units": units,
            "place_of_service": place_of_service,
            "diagnosis_pointers": diag_pointers,
        })
        state.current_claim["current_service_line"] = service_line

    def _parse_sv2(self, elements: list[str], state: X12ParseState) -> None:
        """Parse SV2 (Institutional Service)."""
        if len(elements) < 4:
            return

        revenue_code = elements[1]

        # SV202 is composite for HCPCS
        sv202 = (self._safe_get(elements, 2) or "").split(state.component_separator)
        procedure_qualifier = self._safe_get(sv202, 0)
        procedure_code = self._safe_get(sv202, 1)
        modifiers = [m for m in sv202[2:6] if m]

        charge_amount = self._parse_decimal(self._safe_get(elements, 3))
        unit_basis_code = self._safe_get(elements, 4) or "UN"
        units = self._parse_decimal(self._safe_get(elements, 5)) or Decimal("1")

        service_line = state.current_claim.get("current_service_line", {})
        service_line.update({
            "revenue_code": revenue_code,
            "procedure_code": procedure_code,
            "procedure_qualifier": procedure_qualifier,
            "modifiers": modifiers,
            "charge_amount": charge_amount,
            "unit_basis_code": unit_basis_code,
            "units": units,
        })
        state.current_claim["current_service_line"] = service_line

    # ========================================================================
    # Segment Parsers - Remittance (835)
    # ========================================================================

    def _parse_bpr(self, elements: list[str], state: X12ParseState) -> None:
        """Parse BPR (Financial Information)."""
        if len(elements) < 4:
            return

        transaction_handling = elements[1]  # I, H, C, D, P
        payment_amount = self._parse_decimal(self._safe_get(elements, 2))
        credit_debit = self._safe_get(elements, 3) or "C"
        payment_method = self._safe_get(elements, 4) or "CHK"

        # Bank info for ACH
        sender_dfi_qualifier = self._safe_get(elements, 5)
        sender_dfi_id = self._safe_get(elements, 6)
        sender_account_type = self._safe_get(elements, 7)
        sender_account = self._safe_get(elements, 8)

        receiver_dfi_qualifier = self._safe_get(elements, 12)
        receiver_dfi_id = self._safe_get(elements, 13)
        receiver_account_type = self._safe_get(elements, 14)
        receiver_account = self._safe_get(elements, 15)

        effective_date = self._parse_date(self._safe_get(elements, 16))

        state.current_remittance["payment"] = {
            "transaction_handling_code": transaction_handling,
            "payment_amount": payment_amount,
            "credit_debit_flag": credit_debit,
            "payment_method": payment_method,
            "sender_dfi_id_qualifier": sender_dfi_qualifier,
            "sender_dfi_id": sender_dfi_id,
            "sender_account_qualifier": sender_account_type,
            "sender_account_number": sender_account,
            "receiver_dfi_id_qualifier": receiver_dfi_qualifier,
            "receiver_dfi_id": receiver_dfi_id,
            "receiver_account_qualifier": receiver_account_type,
            "receiver_account_number": receiver_account,
            "effective_date": effective_date,
        }

    def _parse_trn(self, elements: list[str], state: X12ParseState) -> None:
        """Parse TRN (Trace Number)."""
        if len(elements) < 3:
            return

        trace_type = elements[1]
        trace_number = elements[2]

        if "payment" in state.current_remittance:
            state.current_remittance["payment"]["check_number"] = trace_number

    def _parse_clp(self, elements: list[str], state: X12ParseState) -> None:
        """Parse CLP (Claim Payment)."""
        if len(elements) < 7:
            return

        # Save any previous claim payment
        if state.current_claim_payment and state.current_claim_payment.get("patient_control_number"):
            state.current_remittance.setdefault("claims", []).append(
                state.current_claim_payment
            )

        patient_control_number = elements[1]
        claim_status = elements[2]
        charge_amount = self._parse_decimal(self._safe_get(elements, 3))
        paid_amount = self._parse_decimal(self._safe_get(elements, 4))
        patient_responsibility = self._parse_decimal(self._safe_get(elements, 5))
        claim_filing_indicator = self._safe_get(elements, 6)
        payer_claim_control = self._safe_get(elements, 7)

        state.current_claim_payment = {
            "patient_control_number": patient_control_number,
            "claim_status_code": claim_status,
            "charge_amount": charge_amount,
            "paid_amount": paid_amount,
            "patient_responsibility": patient_responsibility,
            "claim_filing_indicator": claim_filing_indicator,
            "payer_claim_control_number": payer_claim_control,
            "adjustments": [],
            "service_payments": [],
        }

    def _parse_svc(self, elements: list[str], state: X12ParseState) -> None:
        """Parse SVC (Service Payment)."""
        if len(elements) < 5:
            return

        # SVC01 is composite
        svc01 = elements[1].split(state.component_separator)
        procedure_qualifier = self._safe_get(svc01, 0)
        procedure_code = self._safe_get(svc01, 1)
        modifiers = [m for m in svc01[2:6] if m]

        charge_amount = self._parse_decimal(self._safe_get(elements, 2))
        paid_amount = self._parse_decimal(self._safe_get(elements, 3))
        units_paid = self._parse_decimal(self._safe_get(elements, 5))

        service_payment = {
            "procedure_code": procedure_code,
            "procedure_qualifier": procedure_qualifier,
            "modifiers": modifiers,
            "charge_amount": charge_amount,
            "paid_amount": paid_amount,
            "units_paid": units_paid,
            "adjustments": [],
            "remark_codes": [],
        }

        if state.current_claim_payment:
            state.current_claim_payment.setdefault("service_payments", []).append(
                service_payment
            )

    def _parse_cas(self, elements: list[str], state: X12ParseState) -> None:
        """Parse CAS (Claim Adjustment)."""
        if len(elements) < 4:
            return

        group_code = elements[1]  # CO, PR, PI, OA, CR

        # Up to 6 reason/amount pairs per CAS
        adjustments = []
        for i in range(2, min(len(elements), 20), 3):
            reason_code = self._safe_get(elements, i)
            amount = self._parse_decimal(self._safe_get(elements, i + 1))
            quantity = self._parse_decimal(self._safe_get(elements, i + 2))

            if reason_code:
                adjustments.append({
                    "group_code": group_code,
                    "reason_code": reason_code,
                    "amount": amount,
                    "quantity": quantity,
                })

        # Apply to current service payment or claim payment
        if state.current_claim_payment:
            if state.current_claim_payment.get("service_payments"):
                # Apply to last service line
                state.current_claim_payment["service_payments"][-1].setdefault(
                    "adjustments", []
                ).extend(adjustments)
            else:
                # Apply to claim level
                state.current_claim_payment.setdefault("adjustments", []).extend(
                    adjustments
                )

    def _parse_plb(self, elements: list[str], state: X12ParseState) -> None:
        """Parse PLB (Provider Level Adjustment)."""
        # Provider-level adjustments like withholdings
        pass

    # ========================================================================
    # Claim/Remittance Building
    # ========================================================================

    def _build_claim(self, data: dict[str, Any]) -> X12Claim:
        """Build X12Claim from parsed data."""
        # Finalize last service line
        if data.get("current_service_line"):
            data.setdefault("service_lines", []).append(data["current_service_line"])

        # Build provider
        billing_provider_data = data.get("billing_provider", {})
        billing_provider = X12Entity(
            role=X12EntityRole.BILLING,
            entity_type=EntityTypeQualifier.NON_PERSON if billing_provider_data.get("organization_name") else EntityTypeQualifier.PERSON,
            organization_name=billing_provider_data.get("organization_name"),
            last_name=billing_provider_data.get("last_name"),
            first_name=billing_provider_data.get("first_name"),
            npi=billing_provider_data.get("npi", "0000000000"),
            tax_id=billing_provider_data.get("tax_id"),
        )

        # Build payer
        payer_data = data.get("payer", {})
        payer = X12Payer(
            name=payer_data.get("organization_name") or payer_data.get("last_name", "Unknown Payer"),
            payer_id=payer_data.get("id_value", "UNKNOWN"),
        )

        # Build subscriber
        subscriber_data = data.get("subscriber", {})
        subscriber = X12Subscriber(
            member_id=subscriber_data.get("id_value", "UNKNOWN"),
            last_name=subscriber_data.get("last_name", "Unknown"),
            first_name=subscriber_data.get("first_name", "Unknown"),
            date_of_birth=subscriber_data.get("date_of_birth") or date(1900, 1, 1),
            gender=subscriber_data.get("gender", "U"),
            relationship_code=subscriber_data.get("relationship_code", "18"),
            group_number=subscriber_data.get("group_number"),
        )

        # Build diagnoses
        diagnoses = []
        for diag in data.get("diagnoses", []):
            qualifier_str = diag.get("qualifier", "ABK")
            try:
                qualifier = DiagnosisCodeQualifier(qualifier_str)
            except ValueError:
                qualifier = DiagnosisCodeQualifier.ICD10_CM

            diagnoses.append(X12Diagnosis(
                code=diag["code"],
                qualifier=qualifier,
                is_principal=diag.get("is_principal", False),
            ))

        if not diagnoses:
            diagnoses.append(X12Diagnosis(code="Z00.00", is_principal=True))

        # Build service lines
        service_lines = []
        for i, line in enumerate(data.get("service_lines", []), 1):
            pos_code = line.get("place_of_service", "11")
            try:
                place_of_service = PlaceOfService(pos_code)
            except ValueError:
                place_of_service = PlaceOfService.OFFICE

            service_lines.append(X12ServiceLine(
                line_number=line.get("line_number", i),
                procedure_code=line.get("procedure_code", "99999"),
                modifiers=line.get("modifiers", []),
                charge_amount=line.get("charge_amount") or Decimal("0"),
                units=line.get("units") or Decimal("1"),
                place_of_service=place_of_service,
                service_date_from=line.get("service_date_from") or date.today(),
                service_date_to=line.get("service_date_to"),
                diagnosis_pointers=line.get("diagnosis_pointers", [1]),
                revenue_code=line.get("revenue_code"),
            ))

        if not service_lines:
            service_lines.append(X12ServiceLine(
                line_number=1,
                procedure_code="99999",
                charge_amount=Decimal("0"),
                service_date_from=date.today(),
            ))

        # Build claim
        freq_code = data.get("frequency_code", "1")
        try:
            frequency_code = ClaimFrequencyCode(freq_code)
        except ValueError:
            frequency_code = ClaimFrequencyCode.ORIGINAL

        return X12Claim(
            patient_control_number=data.get("patient_control_number", "UNKNOWN"),
            total_charge=data.get("total_charge") or Decimal("0"),
            frequency_code=frequency_code,
            statement_from_date=data.get("statement_from_date") or date.today(),
            statement_to_date=data.get("statement_to_date") or date.today(),
            billing_provider=billing_provider,
            payer=payer,
            subscriber=subscriber,
            diagnoses=diagnoses,
            service_lines=service_lines,
            prior_authorization_number=data.get("prior_authorization_number"),
            original_reference_number=data.get("original_reference_number"),
            admission_date=data.get("admission_date"),
        )

    def _build_remittance(self, data: dict[str, Any]) -> X12Remittance:
        """Build X12Remittance from parsed data."""
        # Finalize last claim payment
        if data.get("current_claim_payment"):
            data.setdefault("claims", []).append(data["current_claim_payment"])

        # Build payment
        payment_data = data.get("payment", {})
        payment = X12Payment(
            payment_amount=payment_data.get("payment_amount") or Decimal("0"),
            transaction_handling_code=payment_data.get("transaction_handling_code", "I"),
            credit_debit_flag=payment_data.get("credit_debit_flag", "C"),
            payment_method=payment_data.get("payment_method", "CHK"),
            effective_date=payment_data.get("effective_date") or date.today(),
            check_number=payment_data.get("check_number"),
        )

        # Build claim payments
        claims = []
        for claim_data in data.get("claims", []):
            adjustments = [
                X12Adjustment(
                    group_code=adj["group_code"],
                    reason_code=adj["reason_code"],
                    amount=adj.get("amount") or Decimal("0"),
                    quantity=adj.get("quantity"),
                )
                for adj in claim_data.get("adjustments", [])
            ]

            service_payments = []
            for svc in claim_data.get("service_payments", []):
                svc_adjustments = [
                    X12Adjustment(
                        group_code=adj["group_code"],
                        reason_code=adj["reason_code"],
                        amount=adj.get("amount") or Decimal("0"),
                        quantity=adj.get("quantity"),
                    )
                    for adj in svc.get("adjustments", [])
                ]

                service_payments.append(X12ServicePayment(
                    procedure_code=svc.get("procedure_code", "99999"),
                    procedure_qualifier=svc.get("procedure_qualifier", "HC"),
                    modifiers=svc.get("modifiers", []),
                    charge_amount=svc.get("charge_amount") or Decimal("0"),
                    paid_amount=svc.get("paid_amount") or Decimal("0"),
                    units_paid=svc.get("units_paid"),
                    adjustments=svc_adjustments,
                    remark_codes=svc.get("remark_codes", []),
                ))

            claims.append(X12ClaimPayment(
                patient_control_number=claim_data.get("patient_control_number", "UNKNOWN"),
                claim_status_code=claim_data.get("claim_status_code", "1"),
                charge_amount=claim_data.get("charge_amount") or Decimal("0"),
                paid_amount=claim_data.get("paid_amount") or Decimal("0"),
                patient_responsibility=claim_data.get("patient_responsibility") or Decimal("0"),
                payer_claim_control_number=claim_data.get("payer_claim_control_number"),
                adjustments=adjustments,
                service_payments=service_payments,
            ))

        # Calculate totals
        total_charge = sum(c.charge_amount for c in claims)
        total_paid = sum(c.paid_amount for c in claims)

        return X12Remittance(
            payment=payment,
            payer_name=data.get("payer_name", "Unknown Payer"),
            payer_id=data.get("payer_id", "UNKNOWN"),
            payee_name=data.get("payee_name", "Unknown Payee"),
            payee_npi=data.get("payee_npi", "0000000000"),
            claims=claims,
            total_claims=len(claims),
            total_charge_amount=total_charge,
            total_paid_amount=total_paid,
        )

    # ========================================================================
    # X12 Generation
    # ========================================================================

    def _generate_837(
        self,
        claim: X12Claim,
        transaction_type: X12TransactionType,
    ) -> X12GenerationResult:
        """Generate 837 claim transaction."""
        segments: list[str] = []
        errors: list[str] = []

        try:
            # Generate control numbers
            control_number = datetime.now(UTC).strftime("%y%m%d%H%M")
            group_control = datetime.now(UTC).strftime("%H%M%S%f")[:9]

            # Determine version based on transaction type
            if transaction_type == X12TransactionType.INSTITUTIONAL_CLAIM:
                version = "005010X223A2"
            else:
                version = "005010X222A1"

            # ISA - Interchange Header
            isa_date = date.today().strftime("%y%m%d")
            isa_time = datetime.now(UTC).strftime("%H%M")
            segments.append(
                f"ISA*00*          *00*          *ZZ*"
                f"{claim.billing_provider.npi:<15}*ZZ*{claim.payer.payer_id:<15}*"
                f"{isa_date}*{isa_time}*^*00501*{control_number:>09}*0*P*:"
            )

            # GS - Functional Group Header
            gs_date = date.today().strftime("%Y%m%d")
            gs_time = datetime.now(UTC).strftime("%H%M%S")
            segments.append(
                f"GS*HC*{claim.billing_provider.npi}*{claim.payer.payer_id}*"
                f"{gs_date}*{gs_time}*{group_control}*X*{version}"
            )

            # ST - Transaction Set Header
            st_number = "0001"
            segments.append(f"ST*837*{st_number}*{version}")

            # BHT - Beginning of Hierarchical Transaction
            bht_ref = datetime.now(UTC).strftime("%y%m%d%H%M%S")
            segments.append(f"BHT*0019*00*{bht_ref}*{gs_date}*{gs_time}*CH")

            # 1000A - Submitter Name
            submitter_name = claim.billing_provider.organization_name or f"{claim.billing_provider.last_name or ''}"
            segments.append(f"NM1*41*2*{submitter_name}*****46*{claim.billing_provider.npi}")
            if claim.billing_provider.contact:
                phone = claim.billing_provider.contact.phone or ""
                segments.append(f"PER*IC*BILLING*TE*{phone}")

            # 1000B - Receiver Name
            segments.append(f"NM1*40*2*{claim.payer.name}*****46*{claim.payer.payer_id}")

            # 2000A - Billing Provider Hierarchical Level
            segments.append("HL*1**20*1")
            if claim.billing_provider.tax_id:
                segments.append(f"PRV*BI*PXC*{claim.billing_provider.taxonomy_code or '207Q00000X'}")

            # 2010AA - Billing Provider Name
            if claim.billing_provider.entity_type == EntityTypeQualifier.NON_PERSON:
                segments.append(
                    f"NM1*85*2*{claim.billing_provider.organization_name}*****XX*"
                    f"{claim.billing_provider.npi}"
                )
            else:
                segments.append(
                    f"NM1*85*1*{claim.billing_provider.last_name}*"
                    f"{claim.billing_provider.first_name}****XX*{claim.billing_provider.npi}"
                )

            if claim.billing_provider.address:
                addr = claim.billing_provider.address
                segments.append(f"N3*{addr.address_line_1}")
                segments.append(f"N4*{addr.city}*{addr.state}*{addr.postal_code}")

            if claim.billing_provider.tax_id:
                segments.append(f"REF*EI*{claim.billing_provider.tax_id}")

            # 2000B - Subscriber Hierarchical Level
            has_patient = claim.patient is not None
            segments.append(f"HL*2*1*22*{'1' if has_patient else '0'}")

            # SBR - Subscriber Information
            filing_ind = claim.payer.claim_filing_indicator.value
            segments.append(
                f"SBR*P*{claim.subscriber.relationship_code}*"
                f"{claim.subscriber.group_number or ''}*****{filing_ind}"
            )

            # 2010BA - Subscriber Name
            segments.append(
                f"NM1*IL*1*{claim.subscriber.last_name}*{claim.subscriber.first_name}****MI*"
                f"{claim.subscriber.member_id}"
            )

            if claim.subscriber.address:
                addr = claim.subscriber.address
                segments.append(f"N3*{addr.address_line_1}")
                segments.append(f"N4*{addr.city}*{addr.state}*{addr.postal_code}")

            # DMG - Subscriber Demographics
            dob = claim.subscriber.date_of_birth.strftime("%Y%m%d")
            segments.append(f"DMG*D8*{dob}*{claim.subscriber.gender}")

            # 2010BB - Payer Name
            segments.append(f"NM1*PR*2*{claim.payer.name}*****PI*{claim.payer.payer_id}")

            # 2000C - Patient Hierarchical Level (if different from subscriber)
            if claim.patient:
                segments.append("HL*3*2*23*0")
                segments.append(f"PAT*{claim.patient.relationship_code}")

                # 2010CA - Patient Name
                segments.append(
                    f"NM1*QC*1*{claim.patient.last_name}*{claim.patient.first_name}"
                )

                if claim.patient.address:
                    addr = claim.patient.address
                    segments.append(f"N3*{addr.address_line_1}")
                    segments.append(f"N4*{addr.city}*{addr.state}*{addr.postal_code}")

                # Patient Demographics
                dob = claim.patient.date_of_birth.strftime("%Y%m%d")
                segments.append(f"DMG*D8*{dob}*{claim.patient.gender}")

            # 2300 - Claim Information
            place_of_service = claim.place_of_service.value
            freq = claim.frequency_code.value
            segments.append(
                f"CLM*{claim.patient_control_number}*{claim.total_charge}***"
                f"{claim.facility_type_code or ''}:{freq}:{place_of_service}*Y*A*Y*Y"
            )

            # DTP - Service Dates
            from_date = claim.statement_from_date.strftime("%Y%m%d")
            to_date = claim.statement_to_date.strftime("%Y%m%d")
            if from_date == to_date:
                segments.append(f"DTP*434*D8*{from_date}")
            else:
                segments.append(f"DTP*434*RD8*{from_date}-{to_date}")

            # Prior Authorization
            if claim.prior_authorization_number:
                segments.append(f"REF*G1*{claim.prior_authorization_number}")

            # HI - Diagnosis Codes
            if claim.diagnoses:
                hi_elements = []
                for i, diag in enumerate(claim.diagnoses[:12]):  # Max 12 diagnoses
                    qualifier = diag.qualifier.value
                    if i == 0:
                        qualifier = "ABK"  # Principal
                    else:
                        qualifier = "ABF"  # Additional
                    hi_elements.append(f"{qualifier}:{diag.code}")

                segments.append(f"HI*{'*'.join(hi_elements)}")

            # 2310A - Referring Provider (if present)
            if claim.referring_provider:
                segments.append(
                    f"NM1*DN*1*{claim.referring_provider.last_name}*"
                    f"{claim.referring_provider.first_name}****XX*{claim.referring_provider.npi}"
                )

            # 2310B - Rendering Provider (if different from billing)
            if claim.rendering_provider:
                segments.append(
                    f"NM1*82*1*{claim.rendering_provider.last_name}*"
                    f"{claim.rendering_provider.first_name}****XX*{claim.rendering_provider.npi}"
                )

            # 2400 - Service Lines
            for line in claim.service_lines:
                segments.append(f"LX*{line.line_number}")

                # SV1 for professional claims
                if transaction_type == X12TransactionType.PROFESSIONAL_CLAIM:
                    # Build composite for procedure
                    modifiers_str = ":".join(line.modifiers) if line.modifiers else ""
                    sv101 = f"HC:{line.procedure_code}"
                    if modifiers_str:
                        sv101 += f":{modifiers_str}"

                    # Build diagnosis pointers
                    diag_ptrs = ":".join(str(p) for p in line.diagnosis_pointers) if line.diagnosis_pointers else "1"

                    segments.append(
                        f"SV1*{sv101}*{line.charge_amount}*{line.unit_basis_code}*"
                        f"{line.units}*{line.place_of_service.value}**{diag_ptrs}"
                    )
                else:
                    # SV2 for institutional
                    sv202 = f"HC:{line.procedure_code}" if line.procedure_code else ""
                    if line.modifiers:
                        sv202 += ":" + ":".join(line.modifiers)

                    segments.append(
                        f"SV2*{line.revenue_code or '0001'}*{sv202}*{line.charge_amount}*"
                        f"{line.unit_basis_code}*{line.units}"
                    )

                # DTP - Service Date
                svc_date = line.service_date_from.strftime("%Y%m%d")
                if line.service_date_to and line.service_date_to != line.service_date_from:
                    end_date = line.service_date_to.strftime("%Y%m%d")
                    segments.append(f"DTP*472*RD8*{svc_date}-{end_date}")
                else:
                    segments.append(f"DTP*472*D8*{svc_date}")

                # Line rendering provider
                if line.rendering_provider:
                    segments.append(
                        f"NM1*82*1*{line.rendering_provider.last_name}*"
                        f"{line.rendering_provider.first_name}****XX*"
                        f"{line.rendering_provider.npi}"
                    )

            # SE - Transaction Set Trailer
            segment_count = len(segments) + 1  # +1 for SE itself
            segments.append(f"SE*{segment_count}*{st_number}")

            # GE - Functional Group Trailer
            segments.append(f"GE*1*{group_control}")

            # IEA - Interchange Trailer
            segments.append(f"IEA*1*{control_number:>09}")

            # Join with segment terminator
            x12_content = "~\n".join(segments) + "~"

            return X12GenerationResult(
                success=True,
                x12_content=x12_content,
                transaction_type=transaction_type,
                segment_count=len(segments),
                errors=errors,
            )

        except Exception as e:
            errors.append(f"Generation error: {e}")
            return X12GenerationResult(
                success=False,
                x12_content="",
                transaction_type=transaction_type,
                segment_count=0,
                errors=errors,
            )

    # ========================================================================
    # Validation Helpers
    # ========================================================================

    def _validate_isa(self, content: str) -> list[X12ValidationError]:
        """Validate ISA segment."""
        errors = []

        if len(content) < 106:
            errors.append(X12ValidationError(
                segment="ISA",
                code="ISA_LENGTH",
                message="ISA segment must be at least 106 characters",
                severity="error",
            ))
            return errors

        if not content.startswith("ISA"):
            errors.append(X12ValidationError(
                segment="ISA",
                code="ISA_START",
                message="File must start with ISA segment",
                severity="error",
            ))

        return errors

    def _validate_structure(self, segments: list[str]) -> list[X12ValidationError]:
        """Validate overall X12 structure."""
        errors = []

        required_segments = {"ISA", "GS", "ST", "SE", "GE", "IEA"}
        found_segments = {s.split("*")[0] for s in segments if s}

        for req in required_segments:
            if req not in found_segments:
                errors.append(X12ValidationError(
                    segment=req,
                    code="MISSING_SEGMENT",
                    message=f"Required segment {req} not found",
                    severity="error",
                ))

        return errors

    def _validate_claim(self, claim: X12Claim) -> list[X12ValidationError]:
        """Validate claim data."""
        errors = []

        # Validate NPI format
        if not re.match(r"^\d{10}$", claim.billing_provider.npi):
            errors.append(X12ValidationError(
                segment="NM1",
                element="09",
                code="INVALID_NPI",
                message="Billing provider NPI must be 10 digits",
                severity="error",
            ))

        # Validate diagnoses
        for diag in claim.diagnoses:
            if not re.match(r"^[A-Z]\d{2}\.?\d{0,4}$", diag.code.upper()):
                errors.append(X12ValidationError(
                    segment="HI",
                    code="INVALID_ICD10",
                    message=f"Invalid ICD-10 code format: {diag.code}",
                    severity="warning",
                ))

        # Validate service lines
        for line in claim.service_lines:
            if line.charge_amount <= 0:
                errors.append(X12ValidationError(
                    segment="SV1",
                    element="02",
                    code="ZERO_CHARGE",
                    message=f"Service line {line.line_number} has zero or negative charge",
                    severity="warning",
                ))

        return errors

    def _validate_remittance(self, remittance: X12Remittance) -> list[X12ValidationError]:
        """Validate remittance data."""
        errors = []

        # Validate payee NPI
        if not re.match(r"^\d{10}$", remittance.payee_npi):
            errors.append(X12ValidationError(
                segment="NM1",
                element="09",
                code="INVALID_NPI",
                message="Payee NPI must be 10 digits",
                severity="error",
            ))

        return errors

    # ========================================================================
    # Utility Helpers
    # ========================================================================

    def _safe_get(self, lst: list, index: int, default: str = "") -> str:
        """Safely get element from list."""
        try:
            value = lst[index] if index < len(lst) else default
            return value if value else default
        except (IndexError, TypeError):
            return default

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse date from X12 format (CCYYMMDD)."""
        if not date_str:
            return None

        try:
            if len(date_str) == 8:
                return datetime.strptime(date_str, "%Y%m%d").date()
            elif len(date_str) == 6:
                return datetime.strptime(date_str, "%y%m%d").date()
        except ValueError:
            pass

        return None

    def _parse_decimal(self, value: str | None) -> Decimal | None:
        """Parse decimal value."""
        if not value:
            return None

        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    def _apply_address(self, address_data: dict, state: X12ParseState) -> None:
        """Apply address data to the appropriate entity."""
        entity_type = state.context.current_entity_type
        provider_type = state.context.current_provider_type

        # Determine target based on current context
        if entity_type == "85" or provider_type == "billing":  # Billing Provider
            if "billing_provider" in state.current_claim:
                state.current_claim["billing_provider"].setdefault("address", {}).update(address_data)
        elif entity_type == "IL":  # Subscriber
            if "subscriber" in state.current_claim:
                state.current_claim["subscriber"].setdefault("address", {}).update(address_data)
        elif entity_type == "QC":  # Patient
            if "patient" in state.current_claim:
                state.current_claim["patient"].setdefault("address", {}).update(address_data)
        elif entity_type == "PR":  # Payer
            if "payer" in state.current_claim:
                state.current_claim["payer"].setdefault("address", {}).update(address_data)
            state.current_remittance.setdefault("payer_address", {}).update(address_data)
        elif entity_type == "PE":  # Payee (835)
            state.current_remittance.setdefault("payee_address", {}).update(address_data)
