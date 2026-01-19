"""X12 EDI Mapper Service.

This module provides bidirectional mapping between:
- Internal claim/remittance data and X12 format
- Standard medical codes and X12-specific codes
- Different code systems (ICD-10, CPT, NDC, etc.)

Key features:
- Code translation and normalization
- Data transformation for X12 compliance
- Internal model to X12 model mapping
- X12 model to internal model mapping
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar

from app.models.x12 import (
    ClaimFilingIndicator,
    ClaimFrequencyCode,
    DiagnosisCodeQualifier,
    EntityTypeQualifier,
    PlaceOfService,
    ProcedureCodeQualifier,
    X12Address,
    X12Adjustment,
    X12Claim,
    X12ClaimPayment,
    X12ContactInfo,
    X12Diagnosis,
    X12Payer,
    X12Payment,
    X12Provider,
    X12ReferringProvider,
    X12Remittance,
    X12RenderingProvider,
    X12ServiceLine,
    X12ServicePayment,
    X12Subscriber,
    X12TransactionType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Code Translation Tables
# ============================================================================


class GenderCode(str, Enum):
    """Standard gender codes."""
    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"


class RelationshipCode(str, Enum):
    """Subscriber relationship codes."""
    SELF = "18"
    SPOUSE = "01"
    CHILD = "19"
    OTHER = "G8"


# Place of Service mapping from common names to codes
PLACE_OF_SERVICE_MAP: dict[str, PlaceOfService] = {
    "office": PlaceOfService.OFFICE,
    "clinic": PlaceOfService.OFFICE,
    "outpatient": PlaceOfService.OUTPATIENT_HOSPITAL,
    "inpatient": PlaceOfService.INPATIENT_HOSPITAL,
    "hospital": PlaceOfService.INPATIENT_HOSPITAL,
    "emergency": PlaceOfService.EMERGENCY_ROOM,
    "er": PlaceOfService.EMERGENCY_ROOM,
    "ed": PlaceOfService.EMERGENCY_ROOM,
    "home": PlaceOfService.HOME,
    "telehealth": PlaceOfService.TELEHEALTH,
    "telemedicine": PlaceOfService.TELEHEALTH,
    "video": PlaceOfService.TELEHEALTH,
    "snf": PlaceOfService.SKILLED_NURSING,
    "skilled nursing": PlaceOfService.SKILLED_NURSING,
    "asc": PlaceOfService.AMBULATORY_SURGICAL,
    "ambulatory": PlaceOfService.AMBULATORY_SURGICAL,
    "hospice": PlaceOfService.HOSPICE,
    "ambulance": PlaceOfService.AMBULANCE_LAND,
}

# Claim filing indicator mapping
PAYER_TYPE_MAP: dict[str, ClaimFilingIndicator] = {
    "medicare": ClaimFilingIndicator.MEDICARE_PART_B,
    "medicare a": ClaimFilingIndicator.MEDICARE_PART_A,
    "medicare b": ClaimFilingIndicator.MEDICARE_PART_B,
    "medicaid": ClaimFilingIndicator.MEDICAID,
    "commercial": ClaimFilingIndicator.COMMERCIAL,
    "bcbs": ClaimFilingIndicator.BCBS,
    "blue cross": ClaimFilingIndicator.BCBS,
    "tricare": ClaimFilingIndicator.TRICARE,
    "champus": ClaimFilingIndicator.CHAMPUS,
    "workers comp": ClaimFilingIndicator.WORKERS_COMP,
    "work comp": ClaimFilingIndicator.WORKERS_COMP,
}

# Revenue code descriptions
REVENUE_CODE_DESCRIPTIONS: dict[str, str] = {
    "0001": "Total Charges",
    "0100": "All-Inclusive Rate",
    "0110": "Room & Board - Private",
    "0120": "Room & Board - Semi-Private",
    "0250": "Pharmacy",
    "0260": "IV Therapy",
    "0270": "Medical/Surgical Supplies",
    "0300": "Laboratory",
    "0320": "Radiology - Diagnostic",
    "0350": "CT Scan",
    "0360": "Operating Room",
    "0370": "Anesthesia",
    "0450": "Emergency Room",
    "0510": "Clinic",
    "0636": "Drugs - Self-Administered",
    "0730": "EKG/ECG",
    "0750": "Gastro-Intestinal Services",
    "0761": "Treatment Room",
    "0942": "Other Therapeutic Services - Education/Training",
}

# Adjustment reason code descriptions
ADJUSTMENT_REASON_DESCRIPTIONS: dict[str, str] = {
    "1": "Deductible Amount",
    "2": "Coinsurance Amount",
    "3": "Co-payment Amount",
    "4": "The procedure code is inconsistent with the modifier used",
    "5": "The procedure code/bill type is inconsistent with the place of service",
    "6": "The procedure/revenue code is inconsistent with the patient's age",
    "7": "The procedure/revenue code is inconsistent with the patient's gender",
    "16": "Claim/service lacks information or has submission/billing error(s)",
    "18": "Exact duplicate claim/service",
    "22": "This care may be covered by another payer per coordination of benefits",
    "23": "The impact of prior payer(s) adjudication including payments and/or adjustments",
    "29": "The time limit for filing has expired",
    "45": "Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement",
    "50": "These are non-covered services because this is not deemed a medical necessity",
    "96": "Non-covered charge(s)",
    "97": "The benefit for this service is included in the payment/allowance for another service",
    "119": "Benefit maximum for this time period or occurrence has been reached",
    "A1": "Claim/Service denied. At least one Remark Code must be provided",
    "B1": "Non-covered visits",
    "B7": "This provider was not certified/eligible to be paid for this procedure/service",
    "PR": "Patient Responsibility",
    "CO": "Contractual Obligation",
    "OA": "Other Adjustment",
    "PI": "Payer Initiated Reduction",
}


# ============================================================================
# Internal Data Models for Mapping
# ============================================================================


@dataclass
class InternalPatient:
    """Internal patient representation."""
    patient_id: str
    first_name: str
    last_name: str
    middle_name: str | None = None
    date_of_birth: date | None = None
    gender: str = "U"
    ssn: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    email: str | None = None


@dataclass
class InternalProvider:
    """Internal provider representation."""
    npi: str
    name: str  # Organization or "Last, First"
    tax_id: str | None = None
    taxonomy_code: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    fax: str | None = None


@dataclass
class InternalPayer:
    """Internal payer/insurance representation."""
    payer_id: str
    payer_name: str
    payer_type: str = "commercial"  # medicare, medicaid, commercial, etc.
    plan_name: str | None = None
    group_number: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None


@dataclass
class InternalDiagnosis:
    """Internal diagnosis representation."""
    code: str  # ICD-10 code
    description: str | None = None
    is_principal: bool = False


@dataclass
class InternalServiceLine:
    """Internal service line representation."""
    line_number: int
    procedure_code: str  # CPT/HCPCS
    modifiers: list[str] = field(default_factory=list)
    description: str | None = None
    charge_amount: Decimal = Decimal("0")
    units: Decimal = Decimal("1")
    service_date: date | None = None
    service_date_end: date | None = None
    place_of_service: str = "office"
    diagnosis_codes: list[str] = field(default_factory=list)
    rendering_provider_npi: str | None = None
    revenue_code: str | None = None  # For institutional claims
    ndc_code: str | None = None


@dataclass
class InternalClaim:
    """Internal claim representation."""
    claim_id: str
    patient: InternalPatient
    billing_provider: InternalProvider
    payer: InternalPayer

    # Subscriber (may be same as patient)
    subscriber: InternalPatient | None = None
    subscriber_id: str | None = None
    relationship_to_subscriber: str = "self"

    # Clinical data
    diagnoses: list[InternalDiagnosis] = field(default_factory=list)
    service_lines: list[InternalServiceLine] = field(default_factory=list)

    # Dates
    service_date: date | None = None
    service_date_end: date | None = None
    admission_date: date | None = None
    discharge_date: date | None = None

    # Claim type and status
    claim_type: str = "professional"  # professional, institutional
    claim_frequency: str = "original"  # original, replacement, void

    # Additional info
    prior_auth_number: str | None = None
    referral_number: str | None = None
    referring_provider_npi: str | None = None
    referring_provider_name: str | None = None

    # Facility (for institutional)
    facility_npi: str | None = None
    facility_name: str | None = None


@dataclass
class InternalPayment:
    """Internal payment representation."""
    payment_id: str
    claim_id: str
    patient_control_number: str

    # Amounts
    charge_amount: Decimal = Decimal("0")
    allowed_amount: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    patient_responsibility: Decimal = Decimal("0")

    # Status
    claim_status: str = "processed"  # processed, denied, adjusted

    # Payer info
    payer_name: str = ""
    payer_id: str = ""
    check_number: str | None = None
    payment_date: date | None = None

    # Provider info
    payee_npi: str = ""
    payee_name: str = ""

    # Adjustments
    adjustments: list[dict[str, Any]] = field(default_factory=list)
    service_payments: list[dict[str, Any]] = field(default_factory=list)


# ============================================================================
# X12 Mapper Service
# ============================================================================

_mapper_service: "X12MapperService | None" = None
_mapper_lock = threading.Lock()


def get_x12_mapper_service() -> "X12MapperService":
    """Get the singleton X12 mapper service instance."""
    global _mapper_service
    if _mapper_service is None:
        with _mapper_lock:
            if _mapper_service is None:
                _mapper_service = X12MapperService()
    return _mapper_service


def reset_x12_mapper_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _mapper_service
    with _mapper_lock:
        _mapper_service = None


class X12MapperService:
    """Service for mapping between internal and X12 data formats."""

    def __init__(self) -> None:
        """Initialize the mapper service."""
        self._pos_map = PLACE_OF_SERVICE_MAP
        self._payer_type_map = PAYER_TYPE_MAP
        self._revenue_descriptions = REVENUE_CODE_DESCRIPTIONS
        self._adjustment_descriptions = ADJUSTMENT_REASON_DESCRIPTIONS

    # ========================================================================
    # Internal to X12 Mapping
    # ========================================================================

    def internal_to_x12_claim(
        self,
        claim: InternalClaim,
        transaction_type: X12TransactionType = X12TransactionType.PROFESSIONAL_CLAIM,
    ) -> X12Claim:
        """Convert internal claim to X12Claim.

        Args:
            claim: Internal claim data
            transaction_type: Target transaction type (837P or 837I)

        Returns:
            X12Claim ready for generation.
        """
        # Build billing provider
        billing_provider = self._map_internal_provider(claim.billing_provider)

        # Build payer
        payer = self._map_internal_payer(claim.payer)

        # Build subscriber
        subscriber_source = claim.subscriber or claim.patient
        subscriber = self._map_internal_subscriber(
            subscriber_source,
            claim.subscriber_id,
            claim.relationship_to_subscriber,
            claim.payer.group_number,
        )

        # Build patient (if different from subscriber)
        patient = None
        if claim.subscriber and claim.patient:
            if claim.patient.patient_id != claim.subscriber.patient_id:
                patient = self._map_internal_patient(claim.patient, claim.relationship_to_subscriber)

        # Build diagnoses
        diagnoses = [
            self._map_internal_diagnosis(diag)
            for diag in claim.diagnoses
        ]

        # Ensure at least one diagnosis
        if not diagnoses:
            diagnoses = [X12Diagnosis(code="Z00.00", is_principal=True)]

        # Build service lines
        service_lines = [
            self._map_internal_service_line(line, claim.diagnoses, transaction_type)
            for line in claim.service_lines
        ]

        # Ensure at least one service line
        if not service_lines:
            service_lines = [X12ServiceLine(
                line_number=1,
                procedure_code="99999",
                charge_amount=Decimal("0"),
                service_date_from=claim.service_date or date.today(),
            )]

        # Calculate total charge
        total_charge = sum(line.charge_amount for line in service_lines)

        # Determine dates
        statement_from = claim.service_date or min(
            line.service_date_from for line in service_lines
        )
        statement_to = claim.service_date_end or max(
            line.service_date_to or line.service_date_from for line in service_lines
        )

        # Map frequency code
        freq_map = {
            "original": ClaimFrequencyCode.ORIGINAL,
            "replacement": ClaimFrequencyCode.REPLACEMENT,
            "void": ClaimFrequencyCode.VOID,
        }
        frequency_code = freq_map.get(claim.claim_frequency.lower(), ClaimFrequencyCode.ORIGINAL)

        # Build referring provider if present
        referring_provider = None
        if claim.referring_provider_npi and claim.referring_provider_name:
            name_parts = claim.referring_provider_name.split(",")
            last_name = name_parts[0].strip() if name_parts else "Unknown"
            first_name = name_parts[1].strip() if len(name_parts) > 1 else "Unknown"
            referring_provider = X12ReferringProvider(
                last_name=last_name,
                first_name=first_name,
                npi=claim.referring_provider_npi,
            )

        return X12Claim(
            claim_id=claim.claim_id,
            patient_control_number=claim.claim_id,
            transaction_type=transaction_type,
            frequency_code=frequency_code,
            total_charge=total_charge,
            statement_from_date=statement_from,
            statement_to_date=statement_to,
            admission_date=claim.admission_date,
            billing_provider=billing_provider,
            payer=payer,
            subscriber=subscriber,
            patient=patient,
            diagnoses=diagnoses,
            service_lines=service_lines,
            prior_authorization_number=claim.prior_auth_number,
            referral_number=claim.referral_number,
            referring_provider=referring_provider,
        )

    def _map_internal_provider(self, provider: InternalProvider) -> X12Provider:
        """Map internal provider to X12Provider."""
        # Parse name to determine entity type
        name_parts = provider.name.split(",") if "," in provider.name else [provider.name]

        # Check if organization or person
        is_org = len(name_parts) == 1 and not any(
            term in provider.name.upper() for term in ["MD", "DO", "NP", "PA"]
        )

        address = None
        if provider.address_line_1:
            address = X12Address(
                address_line_1=provider.address_line_1,
                address_line_2=provider.address_line_2,
                city=provider.city or "Unknown",
                state=provider.state or "XX",
                postal_code=provider.zip_code or "00000",
            )

        contact = None
        if provider.phone:
            contact = X12ContactInfo(
                phone=provider.phone,
                fax=provider.fax,
            )

        if is_org:
            return X12Provider(
                entity_type=EntityTypeQualifier.NON_PERSON,
                organization_name=provider.name,
                npi=provider.npi,
                tax_id=provider.tax_id,
                taxonomy_code=provider.taxonomy_code,
                address=address,
                contact=contact,
            )
        else:
            last_name = name_parts[0].strip()
            first_name = name_parts[1].strip() if len(name_parts) > 1 else ""
            return X12Provider(
                entity_type=EntityTypeQualifier.PERSON,
                last_name=last_name,
                first_name=first_name,
                npi=provider.npi,
                tax_id=provider.tax_id,
                taxonomy_code=provider.taxonomy_code,
                address=address,
                contact=contact,
            )

    def _map_internal_payer(self, payer: InternalPayer) -> X12Payer:
        """Map internal payer to X12Payer."""
        # Determine claim filing indicator
        payer_type_lower = payer.payer_type.lower()
        claim_filing = self._payer_type_map.get(
            payer_type_lower,
            ClaimFilingIndicator.COMMERCIAL,
        )

        address = None
        if payer.address_line_1:
            address = X12Address(
                address_line_1=payer.address_line_1,
                city=payer.city or "Unknown",
                state=payer.state or "XX",
                postal_code=payer.zip_code or "00000",
            )

        return X12Payer(
            name=payer.payer_name,
            payer_id=payer.payer_id,
            address=address,
            claim_filing_indicator=claim_filing,
        )

    def _map_internal_subscriber(
        self,
        patient: InternalPatient,
        subscriber_id: str | None,
        relationship: str,
        group_number: str | None,
    ) -> X12Subscriber:
        """Map internal patient to X12Subscriber."""
        # Map relationship code
        rel_map = {
            "self": "18",
            "spouse": "01",
            "child": "19",
            "other": "G8",
        }
        relationship_code = rel_map.get(relationship.lower(), "18")

        address = None
        if patient.address_line_1:
            address = X12Address(
                address_line_1=patient.address_line_1,
                address_line_2=patient.address_line_2,
                city=patient.city or "Unknown",
                state=patient.state or "XX",
                postal_code=patient.zip_code or "00000",
            )

        return X12Subscriber(
            member_id=subscriber_id or patient.patient_id,
            last_name=patient.last_name,
            first_name=patient.first_name,
            middle_name=patient.middle_name,
            date_of_birth=patient.date_of_birth or date(1900, 1, 1),
            gender=self._normalize_gender(patient.gender),
            address=address,
            group_number=group_number,
            relationship_code=relationship_code,
        )

    def _map_internal_patient(
        self,
        patient: InternalPatient,
        relationship: str,
    ) -> X12Subscriber:
        """Map internal patient to X12Patient (when different from subscriber)."""
        from app.models.x12 import X12Patient

        rel_map = {
            "self": "18",
            "spouse": "01",
            "child": "19",
            "other": "G8",
        }
        relationship_code = rel_map.get(relationship.lower(), "G8")

        address = None
        if patient.address_line_1:
            address = X12Address(
                address_line_1=patient.address_line_1,
                address_line_2=patient.address_line_2,
                city=patient.city or "Unknown",
                state=patient.state or "XX",
                postal_code=patient.zip_code or "00000",
            )

        return X12Patient(
            last_name=patient.last_name,
            first_name=patient.first_name,
            middle_name=patient.middle_name,
            date_of_birth=patient.date_of_birth or date(1900, 1, 1),
            gender=self._normalize_gender(patient.gender),
            address=address,
            relationship_code=relationship_code,
        )

    def _map_internal_diagnosis(self, diagnosis: InternalDiagnosis) -> X12Diagnosis:
        """Map internal diagnosis to X12Diagnosis."""
        # Normalize ICD-10 code (remove dots if present)
        code = diagnosis.code.replace(".", "")

        return X12Diagnosis(
            code=code,
            qualifier=DiagnosisCodeQualifier.ICD10_CM,
            is_principal=diagnosis.is_principal,
            description=diagnosis.description,
        )

    def _map_internal_service_line(
        self,
        line: InternalServiceLine,
        diagnoses: list[InternalDiagnosis],
        transaction_type: X12TransactionType,
    ) -> X12ServiceLine:
        """Map internal service line to X12ServiceLine."""
        # Map place of service
        pos_lower = line.place_of_service.lower()
        place_of_service = self._pos_map.get(pos_lower, PlaceOfService.OFFICE)

        # Build diagnosis pointers (1-based)
        diagnosis_pointers = []
        for diag_code in line.diagnosis_codes:
            normalized_code = diag_code.replace(".", "")
            for i, diag in enumerate(diagnoses, 1):
                if diag.code.replace(".", "") == normalized_code:
                    diagnosis_pointers.append(i)
                    break

        # If no pointers, default to first diagnosis
        if not diagnosis_pointers:
            diagnosis_pointers = [1]

        # Map rendering provider if present
        rendering_provider = None
        if line.rendering_provider_npi:
            rendering_provider = X12RenderingProvider(
                last_name="Provider",
                first_name="Rendering",
                npi=line.rendering_provider_npi,
            )

        return X12ServiceLine(
            line_number=line.line_number,
            procedure_code=line.procedure_code,
            modifiers=line.modifiers[:4],  # Max 4 modifiers
            description=line.description,
            charge_amount=line.charge_amount,
            units=line.units,
            place_of_service=place_of_service,
            service_date_from=line.service_date or date.today(),
            service_date_to=line.service_date_end,
            diagnosis_pointers=diagnosis_pointers,
            rendering_provider=rendering_provider,
            revenue_code=line.revenue_code,
            ndc_code=line.ndc_code,
        )

    # ========================================================================
    # X12 to Internal Mapping
    # ========================================================================

    def x12_claim_to_internal(self, claim: X12Claim) -> InternalClaim:
        """Convert X12Claim to internal format.

        Args:
            claim: X12Claim from parsing

        Returns:
            InternalClaim representation.
        """
        # Build internal patient from subscriber
        patient = self._map_x12_subscriber_to_patient(claim.subscriber)

        # Build internal provider
        billing_provider = self._map_x12_provider_to_internal(claim.billing_provider)

        # Build internal payer
        payer = self._map_x12_payer_to_internal(claim.payer)

        # Build internal diagnoses
        diagnoses = [
            InternalDiagnosis(
                code=self._format_icd10(diag.code),
                description=diag.description,
                is_principal=diag.is_principal,
            )
            for diag in claim.diagnoses
        ]

        # Build internal service lines
        service_lines = [
            self._map_x12_service_line_to_internal(line, claim.diagnoses)
            for line in claim.service_lines
        ]

        # Determine claim type
        claim_type = (
            "institutional" if claim.transaction_type == X12TransactionType.INSTITUTIONAL_CLAIM
            else "professional"
        )

        # Map frequency
        freq_map = {
            ClaimFrequencyCode.ORIGINAL: "original",
            ClaimFrequencyCode.REPLACEMENT: "replacement",
            ClaimFrequencyCode.VOID: "void",
        }
        claim_frequency = freq_map.get(claim.frequency_code, "original")

        return InternalClaim(
            claim_id=claim.patient_control_number,
            patient=patient,
            billing_provider=billing_provider,
            payer=payer,
            subscriber_id=claim.subscriber.member_id,
            relationship_to_subscriber=self._map_relationship_code(claim.subscriber.relationship_code),
            diagnoses=diagnoses,
            service_lines=service_lines,
            service_date=claim.statement_from_date,
            service_date_end=claim.statement_to_date,
            admission_date=claim.admission_date,
            claim_type=claim_type,
            claim_frequency=claim_frequency,
            prior_auth_number=claim.prior_authorization_number,
            referral_number=claim.referral_number,
        )

    def x12_remittance_to_internal(self, remittance: X12Remittance) -> list[InternalPayment]:
        """Convert X12Remittance to internal payment records.

        Args:
            remittance: X12Remittance from parsing

        Returns:
            List of InternalPayment records (one per claim in remittance).
        """
        payments = []

        for claim_payment in remittance.claims:
            # Map adjustments
            adjustments = [
                {
                    "group_code": adj.group_code,
                    "reason_code": adj.reason_code,
                    "amount": float(adj.amount),
                    "description": self._adjustment_descriptions.get(
                        adj.reason_code,
                        f"Adjustment reason {adj.reason_code}",
                    ),
                }
                for adj in claim_payment.adjustments
            ]

            # Map service payments
            service_payments = [
                {
                    "procedure_code": svc.procedure_code,
                    "modifiers": svc.modifiers,
                    "charge_amount": float(svc.charge_amount),
                    "paid_amount": float(svc.paid_amount),
                    "allowed_amount": float(svc.allowed_amount) if svc.allowed_amount else None,
                    "adjustments": [
                        {
                            "group_code": adj.group_code,
                            "reason_code": adj.reason_code,
                            "amount": float(adj.amount),
                        }
                        for adj in svc.adjustments
                    ],
                }
                for svc in claim_payment.service_payments
            ]

            # Map claim status
            status_map = {
                "1": "processed",
                "2": "denied",
                "3": "reversal",
                "4": "denied",
                "19": "processed",
                "20": "partial",
                "21": "reversed",
                "22": "reversed",
            }
            claim_status = status_map.get(claim_payment.claim_status_code, "processed")

            payments.append(InternalPayment(
                payment_id=remittance.transaction_id,
                claim_id=claim_payment.patient_control_number,
                patient_control_number=claim_payment.patient_control_number,
                charge_amount=claim_payment.charge_amount,
                paid_amount=claim_payment.paid_amount,
                patient_responsibility=claim_payment.patient_responsibility,
                claim_status=claim_status,
                payer_name=remittance.payer_name,
                payer_id=remittance.payer_id,
                check_number=remittance.payment.check_number,
                payment_date=remittance.payment.effective_date,
                payee_npi=remittance.payee_npi,
                payee_name=remittance.payee_name,
                adjustments=adjustments,
                service_payments=service_payments,
            ))

        return payments

    def _map_x12_subscriber_to_patient(self, subscriber: X12Subscriber) -> InternalPatient:
        """Map X12Subscriber to internal patient."""
        address_line_1 = None
        city = None
        state = None
        zip_code = None

        if subscriber.address:
            address_line_1 = subscriber.address.address_line_1
            city = subscriber.address.city
            state = subscriber.address.state
            zip_code = subscriber.address.postal_code

        return InternalPatient(
            patient_id=subscriber.member_id,
            first_name=subscriber.first_name,
            last_name=subscriber.last_name,
            middle_name=subscriber.middle_name,
            date_of_birth=subscriber.date_of_birth,
            gender=subscriber.gender,
            address_line_1=address_line_1,
            city=city,
            state=state,
            zip_code=zip_code,
        )

    def _map_x12_provider_to_internal(self, provider: X12Provider) -> InternalProvider:
        """Map X12Provider to internal format."""
        # Build name
        if provider.entity_type == EntityTypeQualifier.NON_PERSON:
            name = provider.organization_name or "Unknown Organization"
        else:
            name = f"{provider.last_name or ''}, {provider.first_name or ''}".strip(", ")

        address_line_1 = None
        city = None
        state = None
        zip_code = None
        phone = None

        if provider.address:
            address_line_1 = provider.address.address_line_1
            city = provider.address.city
            state = provider.address.state
            zip_code = provider.address.postal_code

        if provider.contact:
            phone = provider.contact.phone

        return InternalProvider(
            npi=provider.npi,
            name=name,
            tax_id=provider.tax_id,
            taxonomy_code=provider.taxonomy_code,
            address_line_1=address_line_1,
            city=city,
            state=state,
            zip_code=zip_code,
            phone=phone,
        )

    def _map_x12_payer_to_internal(self, payer: X12Payer) -> InternalPayer:
        """Map X12Payer to internal format."""
        # Reverse map claim filing indicator to payer type
        payer_type = "commercial"
        for key, value in self._payer_type_map.items():
            if value == payer.claim_filing_indicator:
                payer_type = key
                break

        address_line_1 = None
        city = None
        state = None
        zip_code = None

        if payer.address:
            address_line_1 = payer.address.address_line_1
            city = payer.address.city
            state = payer.address.state
            zip_code = payer.address.postal_code

        return InternalPayer(
            payer_id=payer.payer_id,
            payer_name=payer.name,
            payer_type=payer_type,
            address_line_1=address_line_1,
            city=city,
            state=state,
            zip_code=zip_code,
        )

    def _map_x12_service_line_to_internal(
        self,
        line: X12ServiceLine,
        diagnoses: list[X12Diagnosis],
    ) -> InternalServiceLine:
        """Map X12ServiceLine to internal format."""
        # Build diagnosis codes from pointers
        diagnosis_codes = []
        for ptr in line.diagnosis_pointers:
            if 1 <= ptr <= len(diagnoses):
                diagnosis_codes.append(self._format_icd10(diagnoses[ptr - 1].code))

        # Reverse map place of service
        place_of_service = "office"
        for key, value in self._pos_map.items():
            if value == line.place_of_service:
                place_of_service = key
                break

        return InternalServiceLine(
            line_number=line.line_number,
            procedure_code=line.procedure_code,
            modifiers=line.modifiers,
            description=line.description,
            charge_amount=line.charge_amount,
            units=line.units,
            service_date=line.service_date_from,
            service_date_end=line.service_date_to,
            place_of_service=place_of_service,
            diagnosis_codes=diagnosis_codes,
            rendering_provider_npi=line.rendering_provider.npi if line.rendering_provider else None,
            revenue_code=line.revenue_code,
            ndc_code=line.ndc_code,
        )

    # ========================================================================
    # Code Translation Utilities
    # ========================================================================

    def normalize_npi(self, npi: str) -> str:
        """Normalize NPI to 10-digit format.

        Args:
            npi: NPI string (may have extra characters)

        Returns:
            Normalized 10-digit NPI or original if invalid.
        """
        # Remove non-digits
        digits = re.sub(r"\D", "", npi)

        # Validate length
        if len(digits) != 10:
            logger.warning(f"Invalid NPI length: {npi}")
            return npi

        return digits

    def format_icd10(self, code: str) -> str:
        """Format ICD-10 code with proper dot placement.

        Args:
            code: ICD-10 code (with or without dot)

        Returns:
            Properly formatted ICD-10 code (e.g., "E11.9").
        """
        return self._format_icd10(code)

    def _format_icd10(self, code: str) -> str:
        """Format ICD-10 code with dot."""
        # Remove existing dots
        code = code.replace(".", "").upper()

        # Add dot after 3rd character if > 3 chars
        if len(code) > 3:
            return f"{code[:3]}.{code[3:]}"
        return code

    def normalize_cpt(self, code: str) -> str:
        """Normalize CPT/HCPCS code.

        Args:
            code: CPT or HCPCS code

        Returns:
            Normalized code (uppercase, no spaces).
        """
        return code.upper().strip()

    def get_place_of_service_code(self, description: str) -> str:
        """Get POS code from description.

        Args:
            description: Place of service description

        Returns:
            POS code (default "11" for office).
        """
        pos = self._pos_map.get(description.lower(), PlaceOfService.OFFICE)
        return pos.value

    def get_place_of_service_description(self, code: str) -> str:
        """Get POS description from code.

        Args:
            code: Place of service code

        Returns:
            Human-readable description.
        """
        for desc, pos in self._pos_map.items():
            if pos.value == code:
                return desc.title()
        return f"Unknown ({code})"

    def get_revenue_code_description(self, code: str) -> str:
        """Get revenue code description.

        Args:
            code: Revenue code (4 digits)

        Returns:
            Human-readable description.
        """
        return self._revenue_descriptions.get(code, f"Revenue Code {code}")

    def get_adjustment_description(self, reason_code: str) -> str:
        """Get adjustment reason code description.

        Args:
            reason_code: CARC code

        Returns:
            Human-readable description.
        """
        return self._adjustment_descriptions.get(
            reason_code,
            f"Adjustment Reason {reason_code}",
        )

    def _normalize_gender(self, gender: str) -> str:
        """Normalize gender code."""
        gender_upper = gender.upper()
        if gender_upper in ("M", "MALE"):
            return "M"
        elif gender_upper in ("F", "FEMALE"):
            return "F"
        else:
            return "U"

    def _map_relationship_code(self, code: str) -> str:
        """Map X12 relationship code to internal format."""
        rel_map = {
            "18": "self",
            "01": "spouse",
            "19": "child",
            "G8": "other",
        }
        return rel_map.get(code, "self")

    # ========================================================================
    # Dict/JSON Conversions
    # ========================================================================

    def dict_to_internal_claim(self, data: dict[str, Any]) -> InternalClaim:
        """Convert dictionary to InternalClaim.

        Args:
            data: Dictionary with claim data

        Returns:
            InternalClaim instance.
        """
        # Build patient
        patient_data = data.get("patient", {})
        patient = InternalPatient(
            patient_id=patient_data.get("patient_id", "UNKNOWN"),
            first_name=patient_data.get("first_name", "Unknown"),
            last_name=patient_data.get("last_name", "Unknown"),
            middle_name=patient_data.get("middle_name"),
            date_of_birth=self._parse_date(patient_data.get("date_of_birth")),
            gender=patient_data.get("gender", "U"),
            address_line_1=patient_data.get("address_line_1"),
            address_line_2=patient_data.get("address_line_2"),
            city=patient_data.get("city"),
            state=patient_data.get("state"),
            zip_code=patient_data.get("zip_code"),
            phone=patient_data.get("phone"),
        )

        # Build billing provider
        provider_data = data.get("billing_provider", {})
        billing_provider = InternalProvider(
            npi=provider_data.get("npi", "0000000000"),
            name=provider_data.get("name", "Unknown Provider"),
            tax_id=provider_data.get("tax_id"),
            taxonomy_code=provider_data.get("taxonomy_code"),
            address_line_1=provider_data.get("address_line_1"),
            city=provider_data.get("city"),
            state=provider_data.get("state"),
            zip_code=provider_data.get("zip_code"),
            phone=provider_data.get("phone"),
        )

        # Build payer
        payer_data = data.get("payer", {})
        payer = InternalPayer(
            payer_id=payer_data.get("payer_id", "UNKNOWN"),
            payer_name=payer_data.get("payer_name", "Unknown Payer"),
            payer_type=payer_data.get("payer_type", "commercial"),
            plan_name=payer_data.get("plan_name"),
            group_number=payer_data.get("group_number"),
        )

        # Build diagnoses
        diagnoses = [
            InternalDiagnosis(
                code=diag.get("code", "Z00.00"),
                description=diag.get("description"),
                is_principal=diag.get("is_principal", i == 0),
            )
            for i, diag in enumerate(data.get("diagnoses", []))
        ]

        # Build service lines
        service_lines = [
            InternalServiceLine(
                line_number=line.get("line_number", i + 1),
                procedure_code=line.get("procedure_code", "99999"),
                modifiers=line.get("modifiers", []),
                description=line.get("description"),
                charge_amount=Decimal(str(line.get("charge_amount", 0))),
                units=Decimal(str(line.get("units", 1))),
                service_date=self._parse_date(line.get("service_date")),
                service_date_end=self._parse_date(line.get("service_date_end")),
                place_of_service=line.get("place_of_service", "office"),
                diagnosis_codes=line.get("diagnosis_codes", []),
                rendering_provider_npi=line.get("rendering_provider_npi"),
                revenue_code=line.get("revenue_code"),
                ndc_code=line.get("ndc_code"),
            )
            for i, line in enumerate(data.get("service_lines", []))
        ]

        return InternalClaim(
            claim_id=data.get("claim_id", ""),
            patient=patient,
            billing_provider=billing_provider,
            payer=payer,
            subscriber_id=data.get("subscriber_id"),
            relationship_to_subscriber=data.get("relationship_to_subscriber", "self"),
            diagnoses=diagnoses,
            service_lines=service_lines,
            service_date=self._parse_date(data.get("service_date")),
            service_date_end=self._parse_date(data.get("service_date_end")),
            admission_date=self._parse_date(data.get("admission_date")),
            discharge_date=self._parse_date(data.get("discharge_date")),
            claim_type=data.get("claim_type", "professional"),
            claim_frequency=data.get("claim_frequency", "original"),
            prior_auth_number=data.get("prior_auth_number"),
            referral_number=data.get("referral_number"),
            referring_provider_npi=data.get("referring_provider_npi"),
            referring_provider_name=data.get("referring_provider_name"),
        )

    def _parse_date(self, value: str | date | None) -> date | None:
        """Parse date from string or return date as-is."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            try:
                return datetime.strptime(value, "%m/%d/%Y").date()
            except (ValueError, TypeError):
                return None

    def get_stats(self) -> dict:
        """Get service statistics."""
        return {
            "place_of_service_mappings": len(self._pos_map),
            "payer_type_mappings": len(self._payer_type_map),
            "revenue_code_descriptions": len(self._revenue_descriptions),
            "adjustment_reason_descriptions": len(self._adjustment_descriptions),
        }
