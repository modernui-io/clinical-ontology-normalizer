"""Clinical Trial Agreement Management (CTA-MGT) Service.

Manages legal agreement operations: clinical trial agreements, confidentiality
agreements, budget negotiations, site contract execution, amendment tracking,
and agreement operational metrics.

Usage:
    from app.services.clinical_trial_agreement_service import (
        get_clinical_trial_agreement_service,
    )

    svc = get_clinical_trial_agreement_service()
    agreements = svc.list_agreements()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_trial_agreement import (
    Agreement,
    AgreementAmendment,
    AgreementAmendmentCreate,
    AgreementAmendmentUpdate,
    AgreementCreate,
    AgreementStatus,
    AgreementType,
    AgreementUpdate,
    BudgetLineItem,
    BudgetLineItemCreate,
    BudgetLineItemUpdate,
    ClinicalTrialAgreementMetrics,
    ContractMilestone,
    ContractMilestoneCreate,
    ContractMilestoneUpdate,
    NegotiationIssue,
    NegotiationRecord,
    NegotiationRecordCreate,
    NegotiationRecordUpdate,
    PaymentTerms,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalTrialAgreementService:
    """In-memory Clinical Trial Agreement Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._agreements: dict[str, Agreement] = {}
        self._negotiations: dict[str, NegotiationRecord] = {}
        self._line_items: dict[str, BudgetLineItem] = {}
        self._amendments: dict[str, AgreementAmendment] = {}
        self._milestones: dict[str, ContractMilestone] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic agreement data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Agreements ---
        agreements_data = [
            # EYLEA agreements
            {"id": "CTA-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "agreement_type": AgreementType.CTA, "status": AgreementStatus.EXECUTED, "title": "EYLEA HD Phase 3 Clinical Trial Agreement - Bascom Palmer", "version": "2.0", "effective_date": now - timedelta(days=365), "expiry_date": now + timedelta(days=730), "total_budget": 1250000.00, "currency": "USD", "payment_terms": PaymentTerms.MILESTONE, "per_patient_cost": 8500.00, "overhead_rate_pct": 28.0, "sponsor_signatory": "Dr. George Yancopoulos", "site_signatory": "Dr. Elizabeth Chen", "executed_date": now - timedelta(days=360), "contract_manager": "Sarah Mitchell", "legal_reviewer": "James Thornton", "negotiation_rounds": 3, "created_at": now - timedelta(days=400)},
            {"id": "CTA-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "agreement_type": AgreementType.CTA, "status": AgreementStatus.EXECUTED, "title": "EYLEA HD Phase 3 Clinical Trial Agreement - Wills Eye", "version": "1.5", "effective_date": now - timedelta(days=350), "expiry_date": now + timedelta(days=745), "total_budget": 980000.00, "currency": "USD", "payment_terms": PaymentTerms.MILESTONE, "per_patient_cost": 8200.00, "overhead_rate_pct": 25.0, "sponsor_signatory": "Dr. George Yancopoulos", "site_signatory": "Dr. James Rodriguez", "executed_date": now - timedelta(days=345), "contract_manager": "Sarah Mitchell", "legal_reviewer": "James Thornton", "negotiation_rounds": 2, "created_at": now - timedelta(days=385)},
            {"id": "CTA-003", "trial_id": EYLEA_TRIAL, "site_id": "SITE-103", "agreement_type": AgreementType.CDA, "status": AgreementStatus.EXECUTED, "title": "EYLEA HD Confidentiality Agreement - Cole Eye Institute", "version": "1.0", "effective_date": now - timedelta(days=420), "expiry_date": now + timedelta(days=310), "total_budget": None, "currency": "USD", "payment_terms": None, "per_patient_cost": None, "overhead_rate_pct": None, "sponsor_signatory": "Dr. George Yancopoulos", "site_signatory": "Dr. Laura Kim", "executed_date": now - timedelta(days=418), "contract_manager": "Sarah Mitchell", "legal_reviewer": "James Thornton", "negotiation_rounds": 1, "created_at": now - timedelta(days=430)},
            {"id": "CTA-004", "trial_id": EYLEA_TRIAL, "site_id": "SITE-103", "agreement_type": AgreementType.BUDGET, "status": AgreementStatus.NEGOTIATION, "title": "EYLEA HD Budget Agreement - Cole Eye Institute", "version": "1.2", "effective_date": None, "expiry_date": None, "total_budget": 875000.00, "currency": "USD", "payment_terms": PaymentTerms.QUARTERLY, "per_patient_cost": 7800.00, "overhead_rate_pct": 30.0, "sponsor_signatory": None, "site_signatory": None, "executed_date": None, "contract_manager": "Sarah Mitchell", "legal_reviewer": "Amanda Fields", "negotiation_rounds": 4, "created_at": now - timedelta(days=90)},

            # Dupixent agreements
            {"id": "CTA-005", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-104", "agreement_type": AgreementType.CTA, "status": AgreementStatus.EXECUTED, "title": "Dupixent AD Phase 3 Clinical Trial Agreement - NYU Langone", "version": "3.0", "effective_date": now - timedelta(days=300), "expiry_date": now + timedelta(days=795), "total_budget": 1500000.00, "currency": "USD", "payment_terms": PaymentTerms.MILESTONE, "per_patient_cost": 6200.00, "overhead_rate_pct": 27.0, "sponsor_signatory": "Dr. Leonard Schleifer", "site_signatory": "Dr. Robert Williams", "executed_date": now - timedelta(days=295), "contract_manager": "Michael Chang", "legal_reviewer": "Patricia Hoffman", "negotiation_rounds": 2, "created_at": now - timedelta(days=340)},
            {"id": "CTA-006", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-105", "agreement_type": AgreementType.SITE_SPECIFIC, "status": AgreementStatus.EXECUTED, "title": "Dupixent Site-Specific Agreement - National Jewish Health", "version": "1.0", "effective_date": now - timedelta(days=280), "expiry_date": now + timedelta(days=815), "total_budget": 1100000.00, "currency": "USD", "payment_terms": PaymentTerms.NET_30, "per_patient_cost": 5800.00, "overhead_rate_pct": 26.0, "sponsor_signatory": "Dr. Leonard Schleifer", "site_signatory": "Dr. Angela Martinez", "executed_date": now - timedelta(days=275), "contract_manager": "Michael Chang", "legal_reviewer": "Patricia Hoffman", "negotiation_rounds": 3, "created_at": now - timedelta(days=320)},
            {"id": "CTA-007", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106", "agreement_type": AgreementType.CTA, "status": AgreementStatus.LEGAL_REVIEW, "title": "Dupixent AD Clinical Trial Agreement - Northwestern Medicine", "version": "1.0", "effective_date": None, "expiry_date": None, "total_budget": 920000.00, "currency": "USD", "payment_terms": PaymentTerms.NET_45, "per_patient_cost": 6000.00, "overhead_rate_pct": 29.0, "sponsor_signatory": None, "site_signatory": None, "executed_date": None, "contract_manager": "Michael Chang", "legal_reviewer": "Patricia Hoffman", "negotiation_rounds": 5, "created_at": now - timedelta(days=60)},
            {"id": "CTA-008", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106", "agreement_type": AgreementType.INVESTIGATOR, "status": AgreementStatus.DRAFT, "title": "Dupixent Investigator Agreement - Dr. Patricia Sullivan", "version": "0.1", "effective_date": None, "expiry_date": None, "total_budget": None, "currency": "USD", "payment_terms": None, "per_patient_cost": None, "overhead_rate_pct": None, "sponsor_signatory": None, "site_signatory": None, "executed_date": None, "contract_manager": "Michael Chang", "legal_reviewer": None, "negotiation_rounds": 0, "created_at": now - timedelta(days=15)},

            # Libtayo agreements
            {"id": "CTA-009", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "agreement_type": AgreementType.MASTER_CTA, "status": AgreementStatus.EXECUTED, "title": "Libtayo CSCC Master Clinical Trial Agreement - MSK", "version": "2.0", "effective_date": now - timedelta(days=400), "expiry_date": now + timedelta(days=695), "total_budget": 2200000.00, "currency": "USD", "payment_terms": PaymentTerms.MILESTONE, "per_patient_cost": 12500.00, "overhead_rate_pct": 30.0, "sponsor_signatory": "Dr. George Yancopoulos", "site_signatory": "Dr. Catherine Liu", "executed_date": now - timedelta(days=395), "contract_manager": "David Park", "legal_reviewer": "Rebecca Lawson", "negotiation_rounds": 4, "created_at": now - timedelta(days=450)},
            {"id": "CTA-010", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "agreement_type": AgreementType.CTA, "status": AgreementStatus.EXECUTED, "title": "Libtayo CSCC Clinical Trial Agreement - MD Anderson", "version": "1.5", "effective_date": now - timedelta(days=380), "expiry_date": now + timedelta(days=715), "total_budget": 1800000.00, "currency": "USD", "payment_terms": PaymentTerms.QUARTERLY, "per_patient_cost": 11000.00, "overhead_rate_pct": 28.0, "sponsor_signatory": "Dr. George Yancopoulos", "site_signatory": "Dr. Andrew Foster", "executed_date": now - timedelta(days=375), "contract_manager": "David Park", "legal_reviewer": "Rebecca Lawson", "negotiation_rounds": 3, "created_at": now - timedelta(days=420)},
            {"id": "CTA-011", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "agreement_type": AgreementType.AMENDMENT, "status": AgreementStatus.SITE_REVIEW, "title": "Libtayo CTA Amendment 1 - Additional Cohort Budget", "version": "1.0", "effective_date": None, "expiry_date": None, "total_budget": 450000.00, "currency": "USD", "payment_terms": PaymentTerms.MILESTONE, "per_patient_cost": 11500.00, "overhead_rate_pct": 28.0, "sponsor_signatory": None, "site_signatory": None, "executed_date": None, "contract_manager": "David Park", "legal_reviewer": "Rebecca Lawson", "negotiation_rounds": 2, "created_at": now - timedelta(days=45)},
            {"id": "CTA-012", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "agreement_type": AgreementType.CDA, "status": AgreementStatus.EXPIRED, "title": "Libtayo Pre-Study CDA - MSK (expired)", "version": "1.0", "effective_date": now - timedelta(days=600), "expiry_date": now - timedelta(days=50), "total_budget": None, "currency": "USD", "payment_terms": None, "per_patient_cost": None, "overhead_rate_pct": None, "sponsor_signatory": "Dr. George Yancopoulos", "site_signatory": "Dr. Catherine Liu", "executed_date": now - timedelta(days=598), "contract_manager": "David Park", "legal_reviewer": "Rebecca Lawson", "negotiation_rounds": 1, "created_at": now - timedelta(days=620)},
        ]

        for a in agreements_data:
            self._agreements[a["id"]] = Agreement(**a)

        # --- 15 Negotiation Records ---
        negotiations_data = [
            {"id": "NEG-001", "agreement_id": "CTA-001", "round_number": 1, "issue": NegotiationIssue.INDEMNIFICATION, "sponsor_position": "Standard sponsor indemnification clause", "site_position": "Request broader indemnification coverage", "resolution": "Expanded coverage to include protocol-mandated procedures", "resolved": True, "escalated": False, "negotiated_by": "Sarah Mitchell", "negotiation_date": now - timedelta(days=390), "notes": "Site accepted with minor language adjustments", "created_at": now - timedelta(days=390)},
            {"id": "NEG-002", "agreement_id": "CTA-001", "round_number": 2, "issue": NegotiationIssue.BUDGET_PER_PATIENT, "sponsor_position": "Per-patient cost of $7,500", "site_position": "Per-patient cost of $9,200 based on procedure complexity", "resolution": "Agreed at $8,500 with additional imaging reimbursement", "resolved": True, "escalated": False, "negotiated_by": "Sarah Mitchell", "negotiation_date": now - timedelta(days=380), "notes": "Fair market value analysis supported $8,500", "created_at": now - timedelta(days=380)},
            {"id": "NEG-003", "agreement_id": "CTA-001", "round_number": 3, "issue": NegotiationIssue.PUBLICATION_RIGHTS, "sponsor_position": "60-day review period before publication", "site_position": "30-day review period", "resolution": "45-day review period with expedited process for abstracts", "resolved": True, "escalated": False, "negotiated_by": "Sarah Mitchell", "negotiation_date": now - timedelta(days=370), "notes": None, "created_at": now - timedelta(days=370)},
            {"id": "NEG-004", "agreement_id": "CTA-002", "round_number": 1, "issue": NegotiationIssue.OVERHEAD_RATE, "sponsor_position": "Standard 25% overhead rate", "site_position": "Institutional rate of 30%", "resolution": "Accepted at 25% with separate startup fee", "resolved": True, "escalated": False, "negotiated_by": "Sarah Mitchell", "negotiation_date": now - timedelta(days=370), "notes": "Startup fee of $15,000 added to offset overhead gap", "created_at": now - timedelta(days=370)},
            {"id": "NEG-005", "agreement_id": "CTA-002", "round_number": 2, "issue": NegotiationIssue.INSURANCE, "sponsor_position": "Standard clinical trial insurance", "site_position": "Additional coverage for investigator liability", "resolution": "Extended coverage provided via sponsor insurance rider", "resolved": True, "escalated": False, "negotiated_by": "Sarah Mitchell", "negotiation_date": now - timedelta(days=360), "notes": None, "created_at": now - timedelta(days=360)},
            {"id": "NEG-006", "agreement_id": "CTA-004", "round_number": 1, "issue": NegotiationIssue.BUDGET_PER_PATIENT, "sponsor_position": "Per-patient cost of $7,000", "site_position": "Per-patient cost of $8,500", "resolution": None, "resolved": False, "escalated": False, "negotiated_by": "Sarah Mitchell", "negotiation_date": now - timedelta(days=80), "notes": "Initial positions exchanged", "created_at": now - timedelta(days=80)},
            {"id": "NEG-007", "agreement_id": "CTA-004", "round_number": 2, "issue": NegotiationIssue.OVERHEAD_RATE, "sponsor_position": "25% overhead", "site_position": "32% overhead per institutional policy", "resolution": None, "resolved": False, "escalated": True, "negotiated_by": "Sarah Mitchell", "negotiation_date": now - timedelta(days=70), "notes": "Escalated to finance leadership", "created_at": now - timedelta(days=70)},
            {"id": "NEG-008", "agreement_id": "CTA-005", "round_number": 1, "issue": NegotiationIssue.IP_OWNERSHIP, "sponsor_position": "Sponsor retains all IP from trial data", "site_position": "Joint IP for biomarker discoveries", "resolution": "Sponsor retains IP with site publication rights and acknowledgment", "resolved": True, "escalated": False, "negotiated_by": "Michael Chang", "negotiation_date": now - timedelta(days=330), "notes": None, "created_at": now - timedelta(days=330)},
            {"id": "NEG-009", "agreement_id": "CTA-005", "round_number": 2, "issue": NegotiationIssue.DATA_OWNERSHIP, "sponsor_position": "Sponsor owns all study data", "site_position": "Site retains access for academic use", "resolution": "Sponsor owns data; site gets de-identified dataset post-publication", "resolved": True, "escalated": False, "negotiated_by": "Michael Chang", "negotiation_date": now - timedelta(days=320), "notes": "Standard academic use provision applied", "created_at": now - timedelta(days=320)},
            {"id": "NEG-010", "agreement_id": "CTA-006", "round_number": 1, "issue": NegotiationIssue.REGULATORY_COMPLIANCE, "sponsor_position": "FDA 21 CFR Part 11 compliance required", "site_position": "Need timeline extension for system validation", "resolution": "6-month compliance window with sponsor technical support", "resolved": True, "escalated": False, "negotiated_by": "Michael Chang", "negotiation_date": now - timedelta(days=310), "notes": None, "created_at": now - timedelta(days=310)},
            {"id": "NEG-011", "agreement_id": "CTA-007", "round_number": 1, "issue": NegotiationIssue.INDEMNIFICATION, "sponsor_position": "Standard indemnification", "site_position": "Request state law-specific provisions", "resolution": None, "resolved": False, "escalated": False, "negotiated_by": "Michael Chang", "negotiation_date": now - timedelta(days=55), "notes": "Legal review of state-specific requirements pending", "created_at": now - timedelta(days=55)},
            {"id": "NEG-012", "agreement_id": "CTA-007", "round_number": 2, "issue": NegotiationIssue.TERMINATION_CLAUSE, "sponsor_position": "30-day termination notice", "site_position": "90-day notice with patient transition plan", "resolution": None, "resolved": False, "escalated": True, "negotiated_by": "Michael Chang", "negotiation_date": now - timedelta(days=45), "notes": "Escalated to legal committee", "created_at": now - timedelta(days=45)},
            {"id": "NEG-013", "agreement_id": "CTA-009", "round_number": 1, "issue": NegotiationIssue.BUDGET_PER_PATIENT, "sponsor_position": "Per-patient cost of $11,000", "site_position": "Per-patient cost of $14,000 for complex oncology protocol", "resolution": "Agreed at $12,500 with additional biomarker testing fee", "resolved": True, "escalated": False, "negotiated_by": "David Park", "negotiation_date": now - timedelta(days=440), "notes": "Oncology-specific fair market value supported higher rate", "created_at": now - timedelta(days=440)},
            {"id": "NEG-014", "agreement_id": "CTA-009", "round_number": 2, "issue": NegotiationIssue.PUBLICATION_RIGHTS, "sponsor_position": "90-day review period", "site_position": "45-day review period", "resolution": "60-day review with pre-submission abstract sharing", "resolved": True, "escalated": False, "negotiated_by": "David Park", "negotiation_date": now - timedelta(days=430), "notes": None, "created_at": now - timedelta(days=430)},
            {"id": "NEG-015", "agreement_id": "CTA-011", "round_number": 1, "issue": NegotiationIssue.BUDGET_PER_PATIENT, "sponsor_position": "Same per-patient rate for additional cohort", "site_position": "5% increase for expanded biomarker panel", "resolution": None, "resolved": False, "escalated": False, "negotiated_by": "David Park", "negotiation_date": now - timedelta(days=40), "notes": "Under review by sponsor finance team", "created_at": now - timedelta(days=40)},
        ]

        for n in negotiations_data:
            self._negotiations[n["id"]] = NegotiationRecord(**n)

        # --- 18 Budget Line Items ---
        line_items_data = [
            # CTA-001 budget
            {"id": "BLI-001", "agreement_id": "CTA-001", "category": "Patient Visits", "description": "Screening visit including OCT and BCVA assessment", "unit_cost": 450.00, "quantity": 150, "total_cost": 67500.00, "currency": "USD", "fair_market_value": 425.00, "justification": "Standard ophthalmology screening visit rate", "approved": True, "approved_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},
            {"id": "BLI-002", "agreement_id": "CTA-001", "category": "Patient Visits", "description": "Treatment visit with intravitreal injection", "unit_cost": 850.00, "quantity": 600, "total_cost": 510000.00, "currency": "USD", "fair_market_value": 820.00, "justification": "Includes injection procedure, monitoring, and documentation", "approved": True, "approved_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},
            {"id": "BLI-003", "agreement_id": "CTA-001", "category": "Imaging", "description": "OCT imaging per protocol schedule", "unit_cost": 250.00, "quantity": 900, "total_cost": 225000.00, "currency": "USD", "fair_market_value": 240.00, "justification": "Includes SD-OCT and analysis", "approved": True, "approved_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},
            {"id": "BLI-004", "agreement_id": "CTA-001", "category": "Site Staff", "description": "Study coordinator FTE (0.5)", "unit_cost": 45000.00, "quantity": 2, "total_cost": 90000.00, "currency": "USD", "fair_market_value": 42000.00, "justification": "Annual salary for half-time coordinator x 2 years", "approved": True, "approved_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},
            {"id": "BLI-005", "agreement_id": "CTA-001", "category": "Equipment", "description": "ETDRS chart calibration and maintenance", "unit_cost": 2500.00, "quantity": 1, "total_cost": 2500.00, "currency": "USD", "fair_market_value": 2200.00, "justification": None, "approved": True, "approved_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},

            # CTA-005 budget
            {"id": "BLI-006", "agreement_id": "CTA-005", "category": "Patient Visits", "description": "Screening visit including EASI and IGA assessment", "unit_cost": 380.00, "quantity": 240, "total_cost": 91200.00, "currency": "USD", "fair_market_value": 370.00, "justification": "Standard dermatology screening visit", "approved": True, "approved_by": "Michael Chang", "created_at": now - timedelta(days=335)},
            {"id": "BLI-007", "agreement_id": "CTA-005", "category": "Patient Visits", "description": "Treatment visit with subcutaneous injection training", "unit_cost": 320.00, "quantity": 960, "total_cost": 307200.00, "currency": "USD", "fair_market_value": 310.00, "justification": "Includes injection training and EASI scoring", "approved": True, "approved_by": "Michael Chang", "created_at": now - timedelta(days=335)},
            {"id": "BLI-008", "agreement_id": "CTA-005", "category": "Photography", "description": "Clinical photography per visit", "unit_cost": 150.00, "quantity": 960, "total_cost": 144000.00, "currency": "USD", "fair_market_value": 140.00, "justification": "Standardized clinical photos for endpoint assessment", "approved": True, "approved_by": "Michael Chang", "created_at": now - timedelta(days=335)},
            {"id": "BLI-009", "agreement_id": "CTA-005", "category": "Laboratory", "description": "Biomarker sample processing and storage", "unit_cost": 200.00, "quantity": 480, "total_cost": 96000.00, "currency": "USD", "fair_market_value": 190.00, "justification": "Serum IgE and cytokine panels", "approved": True, "approved_by": "Michael Chang", "created_at": now - timedelta(days=335)},

            # CTA-009 budget
            {"id": "BLI-010", "agreement_id": "CTA-009", "category": "Patient Visits", "description": "Screening with imaging and biopsy review", "unit_cost": 650.00, "quantity": 180, "total_cost": 117000.00, "currency": "USD", "fair_market_value": 630.00, "justification": "Complex oncology screening including CT review", "approved": True, "approved_by": "David Park", "created_at": now - timedelta(days=445)},
            {"id": "BLI-011", "agreement_id": "CTA-009", "category": "Patient Visits", "description": "Infusion visit with pre-medications", "unit_cost": 1200.00, "quantity": 720, "total_cost": 864000.00, "currency": "USD", "fair_market_value": 1150.00, "justification": "IV infusion with monitoring, includes chair time", "approved": True, "approved_by": "David Park", "created_at": now - timedelta(days=445)},
            {"id": "BLI-012", "agreement_id": "CTA-009", "category": "Imaging", "description": "CT scan per RECIST assessment schedule", "unit_cost": 800.00, "quantity": 540, "total_cost": 432000.00, "currency": "USD", "fair_market_value": 780.00, "justification": "Contrast-enhanced CT chest/abdomen/pelvis", "approved": True, "approved_by": "David Park", "created_at": now - timedelta(days=445)},
            {"id": "BLI-013", "agreement_id": "CTA-009", "category": "Biopsy", "description": "Tumor biopsy collection and processing", "unit_cost": 2500.00, "quantity": 90, "total_cost": 225000.00, "currency": "USD", "fair_market_value": 2400.00, "justification": "Core biopsy with pathology processing", "approved": True, "approved_by": "David Park", "created_at": now - timedelta(days=445)},

            # CTA-004 budget (in negotiation - some not approved)
            {"id": "BLI-014", "agreement_id": "CTA-004", "category": "Patient Visits", "description": "Screening visit", "unit_cost": 420.00, "quantity": 120, "total_cost": 50400.00, "currency": "USD", "fair_market_value": 400.00, "justification": None, "approved": False, "approved_by": None, "created_at": now - timedelta(days=85)},
            {"id": "BLI-015", "agreement_id": "CTA-004", "category": "Patient Visits", "description": "Treatment visit with injection", "unit_cost": 800.00, "quantity": 480, "total_cost": 384000.00, "currency": "USD", "fair_market_value": 780.00, "justification": None, "approved": False, "approved_by": None, "created_at": now - timedelta(days=85)},
            {"id": "BLI-016", "agreement_id": "CTA-004", "category": "Site Staff", "description": "Study coordinator FTE (0.75)", "unit_cost": 67500.00, "quantity": 2, "total_cost": 135000.00, "currency": "USD", "fair_market_value": 63000.00, "justification": "Annual salary for 0.75 FTE coordinator x 2 years", "approved": False, "approved_by": None, "created_at": now - timedelta(days=85)},

            # CTA-010 budget
            {"id": "BLI-017", "agreement_id": "CTA-010", "category": "Patient Visits", "description": "Infusion visit", "unit_cost": 1100.00, "quantity": 600, "total_cost": 660000.00, "currency": "USD", "fair_market_value": 1050.00, "justification": "Standard oncology infusion visit", "approved": True, "approved_by": "David Park", "created_at": now - timedelta(days=415)},
            {"id": "BLI-018", "agreement_id": "CTA-010", "category": "Imaging", "description": "CT scan with RECIST evaluation", "unit_cost": 780.00, "quantity": 450, "total_cost": 351000.00, "currency": "USD", "fair_market_value": 760.00, "justification": None, "approved": True, "approved_by": "David Park", "created_at": now - timedelta(days=415)},
        ]

        for li in line_items_data:
            self._line_items[li["id"]] = BudgetLineItem(**li)

        # --- 10 Agreement Amendments ---
        amendments_data = [
            {"id": "AMD-001", "agreement_id": "CTA-001", "amendment_number": 1, "title": "Protocol Amendment 2 Budget Impact", "description": "Additional OCT imaging visits added per protocol amendment 2", "change_type": "budget_increase", "budget_impact": 75000.00, "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=200), "initiated_by": "Sarah Mitchell", "approved_by": "James Thornton", "created_at": now - timedelta(days=220)},
            {"id": "AMD-002", "agreement_id": "CTA-001", "amendment_number": 2, "title": "Extended Follow-up Period", "description": "12-month extension for long-term follow-up data collection", "change_type": "scope_change", "budget_impact": 150000.00, "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=120), "initiated_by": "Sarah Mitchell", "approved_by": "James Thornton", "created_at": now - timedelta(days=140)},
            {"id": "AMD-003", "agreement_id": "CTA-002", "amendment_number": 1, "title": "Additional Site Staff Support", "description": "Add 0.25 FTE research nurse for increased enrollment", "change_type": "budget_increase", "budget_impact": 32000.00, "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=180), "initiated_by": "Sarah Mitchell", "approved_by": "James Thornton", "created_at": now - timedelta(days=200)},
            {"id": "AMD-004", "agreement_id": "CTA-005", "amendment_number": 1, "title": "Biomarker Substudy Addition", "description": "New biomarker sample collection added at weeks 4, 8, 12", "change_type": "scope_change", "budget_impact": 96000.00, "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=150), "initiated_by": "Michael Chang", "approved_by": "Patricia Hoffman", "created_at": now - timedelta(days=170)},
            {"id": "AMD-005", "agreement_id": "CTA-005", "amendment_number": 2, "title": "Per-Patient Cost Adjustment", "description": "Adjust per-patient rate for increased visit complexity", "change_type": "budget_increase", "budget_impact": 48000.00, "status": AgreementStatus.FINAL, "effective_date": None, "initiated_by": "Michael Chang", "approved_by": "Patricia Hoffman", "created_at": now - timedelta(days=60)},
            {"id": "AMD-006", "agreement_id": "CTA-006", "amendment_number": 1, "title": "Regulatory Update Compliance", "description": "Updated language for new FDA guidance on decentralized trial elements", "change_type": "regulatory", "budget_impact": None, "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=100), "initiated_by": "Michael Chang", "approved_by": "Patricia Hoffman", "created_at": now - timedelta(days=120)},
            {"id": "AMD-007", "agreement_id": "CTA-009", "amendment_number": 1, "title": "Expanded Cohort Addition", "description": "New treatment cohort with combination therapy", "change_type": "scope_change", "budget_impact": 450000.00, "status": AgreementStatus.SITE_REVIEW, "effective_date": None, "initiated_by": "David Park", "approved_by": None, "created_at": now - timedelta(days=45)},
            {"id": "AMD-008", "agreement_id": "CTA-009", "amendment_number": 2, "title": "Imaging Schedule Revision", "description": "CT scans moved from q8w to q6w per DSMB recommendation", "change_type": "budget_increase", "budget_impact": 120000.00, "status": AgreementStatus.NEGOTIATION, "effective_date": None, "initiated_by": "David Park", "approved_by": None, "created_at": now - timedelta(days=30)},
            {"id": "AMD-009", "agreement_id": "CTA-010", "amendment_number": 1, "title": "Termination Clause Update", "description": "Updated termination provisions per legal review", "change_type": "administrative", "budget_impact": None, "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=200), "initiated_by": "David Park", "approved_by": "Rebecca Lawson", "created_at": now - timedelta(days=220)},
            {"id": "AMD-010", "agreement_id": "CTA-010", "amendment_number": 2, "title": "Payment Terms Revision", "description": "Switch from quarterly to milestone-based payments", "change_type": "administrative", "budget_impact": None, "status": AgreementStatus.INTERNAL_REVIEW, "effective_date": None, "initiated_by": "David Park", "approved_by": None, "created_at": now - timedelta(days=20)},
        ]

        for am in amendments_data:
            self._amendments[am["id"]] = AgreementAmendment(**am)

        # --- 15 Contract Milestones ---
        milestones_data = [
            # CTA-001 milestones
            {"id": "CMS-001", "agreement_id": "CTA-001", "milestone_name": "Site Initiation Visit", "description": "Completion of site initiation visit and staff training", "payment_amount": 25000.00, "currency": "USD", "due_date": now - timedelta(days=340), "completed_date": now - timedelta(days=345), "status": "completed", "evidence_required": "SIV report and training log", "verified_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},
            {"id": "CMS-002", "agreement_id": "CTA-001", "milestone_name": "First Patient Enrolled", "description": "First patient screened and randomized", "payment_amount": 50000.00, "currency": "USD", "due_date": now - timedelta(days=300), "completed_date": now - timedelta(days=310), "status": "completed", "evidence_required": "Randomization confirmation", "verified_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},
            {"id": "CMS-003", "agreement_id": "CTA-001", "milestone_name": "50% Enrollment Target", "description": "50% of target enrollment achieved", "payment_amount": 150000.00, "currency": "USD", "due_date": now - timedelta(days=180), "completed_date": now - timedelta(days=190), "status": "completed", "evidence_required": "Enrollment tracker report", "verified_by": "Sarah Mitchell", "created_at": now - timedelta(days=395)},
            {"id": "CMS-004", "agreement_id": "CTA-001", "milestone_name": "100% Enrollment Target", "description": "Full enrollment target achieved", "payment_amount": 200000.00, "currency": "USD", "due_date": now - timedelta(days=60), "completed_date": None, "status": "in_progress", "evidence_required": "Final enrollment report", "verified_by": None, "created_at": now - timedelta(days=395)},
            {"id": "CMS-005", "agreement_id": "CTA-001", "milestone_name": "Last Patient Last Visit", "description": "All patients completed final study visit", "payment_amount": 100000.00, "currency": "USD", "due_date": now + timedelta(days=180), "completed_date": None, "status": "pending", "evidence_required": "LPLV confirmation", "verified_by": None, "created_at": now - timedelta(days=395)},

            # CTA-005 milestones
            {"id": "CMS-006", "agreement_id": "CTA-005", "milestone_name": "Site Initiation Visit", "description": "SIV completion for Dupixent AD trial", "payment_amount": 20000.00, "currency": "USD", "due_date": now - timedelta(days=280), "completed_date": now - timedelta(days=282), "status": "completed", "evidence_required": "SIV report", "verified_by": "Michael Chang", "created_at": now - timedelta(days=335)},
            {"id": "CMS-007", "agreement_id": "CTA-005", "milestone_name": "First Patient Enrolled", "description": "First patient randomized in AD study", "payment_amount": 40000.00, "currency": "USD", "due_date": now - timedelta(days=240), "completed_date": now - timedelta(days=245), "status": "completed", "evidence_required": "Randomization confirmation", "verified_by": "Michael Chang", "created_at": now - timedelta(days=335)},
            {"id": "CMS-008", "agreement_id": "CTA-005", "milestone_name": "50% Enrollment", "description": "Half of target enrollment reached", "payment_amount": 120000.00, "currency": "USD", "due_date": now - timedelta(days=120), "completed_date": now - timedelta(days=125), "status": "completed", "evidence_required": "Enrollment report", "verified_by": "Michael Chang", "created_at": now - timedelta(days=335)},
            {"id": "CMS-009", "agreement_id": "CTA-005", "milestone_name": "100% Enrollment", "description": "Full enrollment target achieved", "payment_amount": 180000.00, "currency": "USD", "due_date": now - timedelta(days=30), "completed_date": None, "status": "overdue", "evidence_required": "Final enrollment report", "verified_by": None, "created_at": now - timedelta(days=335)},

            # CTA-009 milestones
            {"id": "CMS-010", "agreement_id": "CTA-009", "milestone_name": "Site Initiation Visit", "description": "SIV for Libtayo CSCC trial at MSK", "payment_amount": 35000.00, "currency": "USD", "due_date": now - timedelta(days=380), "completed_date": now - timedelta(days=385), "status": "completed", "evidence_required": "SIV report and pharmacy setup", "verified_by": "David Park", "created_at": now - timedelta(days=445)},
            {"id": "CMS-011", "agreement_id": "CTA-009", "milestone_name": "First Patient Enrolled", "description": "First patient dosed in CSCC trial", "payment_amount": 75000.00, "currency": "USD", "due_date": now - timedelta(days=340), "completed_date": now - timedelta(days=350), "status": "completed", "evidence_required": "Dosing confirmation", "verified_by": "David Park", "created_at": now - timedelta(days=445)},
            {"id": "CMS-012", "agreement_id": "CTA-009", "milestone_name": "25% Enrollment", "description": "Quarter of target enrollment achieved", "payment_amount": 100000.00, "currency": "USD", "due_date": now - timedelta(days=280), "completed_date": now - timedelta(days=285), "status": "completed", "evidence_required": "Enrollment tracker", "verified_by": "David Park", "created_at": now - timedelta(days=445)},
            {"id": "CMS-013", "agreement_id": "CTA-009", "milestone_name": "50% Enrollment", "description": "Half of enrollment target reached", "payment_amount": 200000.00, "currency": "USD", "due_date": now - timedelta(days=200), "completed_date": now - timedelta(days=205), "status": "completed", "evidence_required": "Enrollment report", "verified_by": "David Park", "created_at": now - timedelta(days=445)},
            {"id": "CMS-014", "agreement_id": "CTA-009", "milestone_name": "100% Enrollment", "description": "Full enrollment achieved", "payment_amount": 250000.00, "currency": "USD", "due_date": now - timedelta(days=90), "completed_date": None, "status": "in_progress", "evidence_required": "Final enrollment report", "verified_by": None, "created_at": now - timedelta(days=445)},
            {"id": "CMS-015", "agreement_id": "CTA-009", "milestone_name": "Database Lock", "description": "Clinical database locked for analysis", "payment_amount": 150000.00, "currency": "USD", "due_date": now + timedelta(days=120), "completed_date": None, "status": "pending", "evidence_required": "Database lock confirmation", "verified_by": None, "created_at": now - timedelta(days=445)},
        ]

        for ms in milestones_data:
            self._milestones[ms["id"]] = ContractMilestone(**ms)

    # ------------------------------------------------------------------
    # Agreement CRUD
    # ------------------------------------------------------------------

    def list_agreements(
        self,
        *,
        trial_id: str | None = None,
        status: AgreementStatus | None = None,
        agreement_type: AgreementType | None = None,
    ) -> list[Agreement]:
        """List agreements with optional filters."""
        with self._lock:
            result = list(self._agreements.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if status is not None:
            result = [a for a in result if a.status == status]
        if agreement_type is not None:
            result = [a for a in result if a.agreement_type == agreement_type]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_agreement(self, agreement_id: str) -> Agreement | None:
        """Get a single agreement by ID."""
        with self._lock:
            return self._agreements.get(agreement_id)

    def create_agreement(self, payload: AgreementCreate) -> Agreement:
        """Create a new agreement."""
        now = datetime.now(timezone.utc)
        agreement_id = f"CTA-{uuid4().hex[:8].upper()}"
        agreement = Agreement(
            id=agreement_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            agreement_type=payload.agreement_type,
            status=AgreementStatus.DRAFT,
            title=payload.title,
            version="0.1",
            total_budget=payload.total_budget,
            currency=payload.currency,
            payment_terms=payload.payment_terms,
            contract_manager=payload.contract_manager,
            created_at=now,
        )
        with self._lock:
            self._agreements[agreement_id] = agreement
        logger.info("Created agreement %s: %s", agreement_id, payload.title)
        return agreement

    def update_agreement(
        self, agreement_id: str, payload: AgreementUpdate
    ) -> Agreement | None:
        """Update an existing agreement."""
        with self._lock:
            existing = self._agreements.get(agreement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Agreement(**data)
            self._agreements[agreement_id] = updated
        return updated

    def delete_agreement(self, agreement_id: str) -> bool:
        """Delete an agreement. Returns True if deleted."""
        with self._lock:
            if agreement_id in self._agreements:
                del self._agreements[agreement_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Negotiation Records
    # ------------------------------------------------------------------

    def list_negotiations(
        self,
        *,
        agreement_id: str | None = None,
        resolved: bool | None = None,
    ) -> list[NegotiationRecord]:
        """List negotiation records with optional filters."""
        with self._lock:
            result = list(self._negotiations.values())

        if agreement_id is not None:
            result = [n for n in result if n.agreement_id == agreement_id]
        if resolved is not None:
            result = [n for n in result if n.resolved == resolved]

        return sorted(result, key=lambda n: n.negotiation_date, reverse=True)

    def get_negotiation(self, negotiation_id: str) -> NegotiationRecord | None:
        """Get a single negotiation record by ID."""
        with self._lock:
            return self._negotiations.get(negotiation_id)

    def create_negotiation(self, payload: NegotiationRecordCreate) -> NegotiationRecord:
        """Create a new negotiation record."""
        now = datetime.now(timezone.utc)
        negotiation_id = f"NEG-{uuid4().hex[:8].upper()}"
        record = NegotiationRecord(
            id=negotiation_id,
            agreement_id=payload.agreement_id,
            round_number=payload.round_number,
            issue=payload.issue,
            sponsor_position=payload.sponsor_position,
            site_position=payload.site_position,
            negotiated_by=payload.negotiated_by,
            negotiation_date=now,
            created_at=now,
        )
        with self._lock:
            self._negotiations[negotiation_id] = record
        logger.info("Created negotiation %s for agreement %s", negotiation_id, payload.agreement_id)
        return record

    def update_negotiation(
        self, negotiation_id: str, payload: NegotiationRecordUpdate
    ) -> NegotiationRecord | None:
        """Update a negotiation record."""
        with self._lock:
            existing = self._negotiations.get(negotiation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = NegotiationRecord(**data)
            self._negotiations[negotiation_id] = updated
        return updated

    def delete_negotiation(self, negotiation_id: str) -> bool:
        """Delete a negotiation record."""
        with self._lock:
            if negotiation_id in self._negotiations:
                del self._negotiations[negotiation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Budget Line Items
    # ------------------------------------------------------------------

    def list_line_items(
        self,
        *,
        agreement_id: str | None = None,
        approved: bool | None = None,
    ) -> list[BudgetLineItem]:
        """List budget line items with optional filters."""
        with self._lock:
            result = list(self._line_items.values())

        if agreement_id is not None:
            result = [li for li in result if li.agreement_id == agreement_id]
        if approved is not None:
            result = [li for li in result if li.approved == approved]

        return sorted(result, key=lambda li: li.created_at, reverse=True)

    def get_line_item(self, line_item_id: str) -> BudgetLineItem | None:
        """Get a single budget line item by ID."""
        with self._lock:
            return self._line_items.get(line_item_id)

    def create_line_item(self, payload: BudgetLineItemCreate) -> BudgetLineItem:
        """Create a new budget line item."""
        now = datetime.now(timezone.utc)
        line_item_id = f"BLI-{uuid4().hex[:8].upper()}"
        item = BudgetLineItem(
            id=line_item_id,
            agreement_id=payload.agreement_id,
            category=payload.category,
            description=payload.description,
            unit_cost=payload.unit_cost,
            quantity=payload.quantity,
            total_cost=payload.total_cost,
            currency=payload.currency,
            fair_market_value=payload.fair_market_value,
            created_at=now,
        )
        with self._lock:
            self._line_items[line_item_id] = item
        logger.info("Created budget line item %s for agreement %s", line_item_id, payload.agreement_id)
        return item

    def update_line_item(
        self, line_item_id: str, payload: BudgetLineItemUpdate
    ) -> BudgetLineItem | None:
        """Update a budget line item."""
        with self._lock:
            existing = self._line_items.get(line_item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BudgetLineItem(**data)
            self._line_items[line_item_id] = updated
        return updated

    def delete_line_item(self, line_item_id: str) -> bool:
        """Delete a budget line item."""
        with self._lock:
            if line_item_id in self._line_items:
                del self._line_items[line_item_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Agreement Amendments
    # ------------------------------------------------------------------

    def list_amendments(
        self,
        *,
        agreement_id: str | None = None,
        status: AgreementStatus | None = None,
    ) -> list[AgreementAmendment]:
        """List agreement amendments with optional filters."""
        with self._lock:
            result = list(self._amendments.values())

        if agreement_id is not None:
            result = [am for am in result if am.agreement_id == agreement_id]
        if status is not None:
            result = [am for am in result if am.status == status]

        return sorted(result, key=lambda am: am.created_at, reverse=True)

    def get_amendment(self, amendment_id: str) -> AgreementAmendment | None:
        """Get a single amendment by ID."""
        with self._lock:
            return self._amendments.get(amendment_id)

    def create_amendment(self, payload: AgreementAmendmentCreate) -> AgreementAmendment:
        """Create a new agreement amendment."""
        now = datetime.now(timezone.utc)
        amendment_id = f"AMD-{uuid4().hex[:8].upper()}"
        amendment = AgreementAmendment(
            id=amendment_id,
            agreement_id=payload.agreement_id,
            amendment_number=payload.amendment_number,
            title=payload.title,
            description=payload.description,
            change_type=payload.change_type,
            budget_impact=payload.budget_impact,
            initiated_by=payload.initiated_by,
            created_at=now,
        )
        with self._lock:
            self._amendments[amendment_id] = amendment
        logger.info("Created amendment %s for agreement %s", amendment_id, payload.agreement_id)
        return amendment

    def update_amendment(
        self, amendment_id: str, payload: AgreementAmendmentUpdate
    ) -> AgreementAmendment | None:
        """Update an agreement amendment."""
        with self._lock:
            existing = self._amendments.get(amendment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AgreementAmendment(**data)
            self._amendments[amendment_id] = updated
        return updated

    def delete_amendment(self, amendment_id: str) -> bool:
        """Delete an amendment."""
        with self._lock:
            if amendment_id in self._amendments:
                del self._amendments[amendment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Contract Milestones
    # ------------------------------------------------------------------

    def list_milestones(
        self,
        *,
        agreement_id: str | None = None,
        status: str | None = None,
    ) -> list[ContractMilestone]:
        """List contract milestones with optional filters."""
        with self._lock:
            result = list(self._milestones.values())

        if agreement_id is not None:
            result = [ms for ms in result if ms.agreement_id == agreement_id]
        if status is not None:
            result = [ms for ms in result if ms.status == status]

        return sorted(result, key=lambda ms: ms.due_date)

    def get_milestone(self, milestone_id: str) -> ContractMilestone | None:
        """Get a single milestone by ID."""
        with self._lock:
            return self._milestones.get(milestone_id)

    def create_milestone(self, payload: ContractMilestoneCreate) -> ContractMilestone:
        """Create a new contract milestone."""
        now = datetime.now(timezone.utc)
        milestone_id = f"CMS-{uuid4().hex[:8].upper()}"
        milestone = ContractMilestone(
            id=milestone_id,
            agreement_id=payload.agreement_id,
            milestone_name=payload.milestone_name,
            description=payload.description,
            payment_amount=payload.payment_amount,
            currency=payload.currency,
            due_date=payload.due_date,
            evidence_required=payload.evidence_required,
            created_at=now,
        )
        with self._lock:
            self._milestones[milestone_id] = milestone
        logger.info("Created milestone %s for agreement %s", milestone_id, payload.agreement_id)
        return milestone

    def update_milestone(
        self, milestone_id: str, payload: ContractMilestoneUpdate
    ) -> ContractMilestone | None:
        """Update a contract milestone."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._milestones.get(milestone_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status changes to completed
            if updates.get("status") == "completed" and existing.completed_date is None:
                updates["completed_date"] = now

            data.update(updates)
            updated = ContractMilestone(**data)
            self._milestones[milestone_id] = updated
        return updated

    def delete_milestone(self, milestone_id: str) -> bool:
        """Delete a milestone."""
        with self._lock:
            if milestone_id in self._milestones:
                del self._milestones[milestone_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> ClinicalTrialAgreementMetrics:
        """Compute aggregated agreement management metrics."""
        with self._lock:
            agreements = list(self._agreements.values())
            negotiations = list(self._negotiations.values())
            line_items = list(self._line_items.values())
            amendments = list(self._amendments.values())
            milestones = list(self._milestones.values())

        if trial_id is not None:
            agreements = [a for a in agreements if a.trial_id == trial_id]
            agreement_ids = {a.id for a in agreements}
            negotiations = [n for n in negotiations if n.agreement_id in agreement_ids]
            line_items = [li for li in line_items if li.agreement_id in agreement_ids]
            amendments = [am for am in amendments if am.agreement_id in agreement_ids]
            milestones = [ms for ms in milestones if ms.agreement_id in agreement_ids]

        # Agreements by type
        agreements_by_type: dict[str, int] = {}
        for a in agreements:
            key = a.agreement_type.value
            agreements_by_type[key] = agreements_by_type.get(key, 0) + 1

        # Agreements by status
        agreements_by_status: dict[str, int] = {}
        for a in agreements:
            key = a.status.value
            agreements_by_status[key] = agreements_by_status.get(key, 0) + 1

        # Executed count
        executed = sum(1 for a in agreements if a.status == AgreementStatus.EXECUTED)

        # Average negotiation rounds
        rounds = [a.negotiation_rounds for a in agreements if a.negotiation_rounds > 0]
        avg_rounds = round(sum(rounds) / len(rounds), 1) if rounds else 0.0

        # Total budget committed (executed agreements only)
        total_budget = sum(
            a.total_budget for a in agreements
            if a.status == AgreementStatus.EXECUTED and a.total_budget is not None
        )

        # Negotiations
        open_negotiations = sum(1 for n in negotiations if not n.resolved)

        # Line items
        approved_items = sum(1 for li in line_items if li.approved)

        # Milestones
        completed_milestones = sum(1 for ms in milestones if ms.status == "completed")

        return ClinicalTrialAgreementMetrics(
            total_agreements=len(agreements),
            agreements_by_type=agreements_by_type,
            agreements_by_status=agreements_by_status,
            executed_agreements=executed,
            avg_negotiation_rounds=avg_rounds,
            total_budget_committed=total_budget,
            total_negotiations=len(negotiations),
            open_negotiations=open_negotiations,
            total_line_items=len(line_items),
            approved_line_items=approved_items,
            total_amendments=len(amendments),
            total_milestones=len(milestones),
            completed_milestones=completed_milestones,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalTrialAgreementService | None = None
_instance_lock = threading.Lock()


def get_clinical_trial_agreement_service() -> ClinicalTrialAgreementService:
    """Return the singleton ClinicalTrialAgreementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalTrialAgreementService()
    return _instance


def reset_clinical_trial_agreement_service() -> ClinicalTrialAgreementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalTrialAgreementService()
    return _instance
