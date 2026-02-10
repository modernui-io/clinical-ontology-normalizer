"""Clinical Trial Insurance Service.

Manages insurance policies, certificates, claims, coverage requirements,
renewals, and compliance checking for clinical trial liability coverage
across multiple jurisdictions.

Usage:
    from app.services.trial_insurance_service import (
        get_trial_insurance_service,
    )

    svc = get_trial_insurance_service()
    policies = svc.list_policies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.trial_insurance import (
    CertificateStatus,
    ClaimStatus,
    CoverageComplianceResult,
    CoverageRequirement,
    CoverageRequirementCreate,
    CoverageRequirementUpdate,
    CoverageScope,
    InsuranceCertificate,
    InsuranceCertificateCreate,
    InsuranceCertificateUpdate,
    InsuranceClaim,
    InsuranceClaimCreate,
    InsuranceClaimUpdate,
    InsuranceMetrics,
    InsurancePolicy,
    InsurancePolicyCreate,
    InsurancePolicyUpdate,
    InsuranceRenewal,
    InsuranceRenewalCreate,
    InsuranceRenewalUpdate,
    PolicyStatus,
    PolicyType,
    RenewalStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class TrialInsuranceService:
    """In-memory Clinical Trial Insurance engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._policies: dict[str, InsurancePolicy] = {}
        self._certificates: dict[str, InsuranceCertificate] = {}
        self._claims: dict[str, InsuranceClaim] = {}
        self._requirements: dict[str, CoverageRequirement] = {}
        self._renewals: dict[str, InsuranceRenewal] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic insurance data for clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 4 Insurance Policies ---
        policies_data = [
            {
                "id": "POL-001",
                "trial_id": EYLEA_TRIAL,
                "policy_number": "CTL-2025-00147",
                "policy_type": PolicyType.CLINICAL_TRIAL_LIABILITY,
                "insurer": "AIG Clinical Trials Division",
                "coverage_scope": CoverageScope.GLOBAL,
                "countries_covered": ["US", "UK", "DE", "FR", "JP", "CA", "AU"],
                "coverage_amount": 50_000_000.0,
                "deductible": 100_000.0,
                "premium": 875_000.0,
                "premium_currency": "USD",
                "effective_date": now - timedelta(days=180),
                "expiry_date": now + timedelta(days=185),
                "renewal_date": now + timedelta(days=155),
                "status": PolicyStatus.ACTIVE,
                "broker": "Marsh McLennan Life Sciences",
                "special_conditions": "Includes gene therapy extension endorsement; "
                "excludes pre-existing conditions not disclosed at screening",
                "created_at": now - timedelta(days=200),
                "updated_at": now - timedelta(days=10),
            },
            {
                "id": "POL-002",
                "trial_id": DUPIXENT_TRIAL,
                "policy_number": "PL-2025-00892",
                "policy_type": PolicyType.PRODUCT_LIABILITY,
                "insurer": "Zurich Insurance Group",
                "coverage_scope": CoverageScope.REGIONAL,
                "countries_covered": ["US", "CA", "MX"],
                "coverage_amount": 25_000_000.0,
                "deductible": 50_000.0,
                "premium": 425_000.0,
                "premium_currency": "USD",
                "effective_date": now - timedelta(days=120),
                "expiry_date": now + timedelta(days=245),
                "renewal_date": now + timedelta(days=215),
                "status": PolicyStatus.ACTIVE,
                "broker": "Willis Towers Watson",
                "special_conditions": None,
                "created_at": now - timedelta(days=140),
                "updated_at": now - timedelta(days=5),
            },
            {
                "id": "POL-003",
                "trial_id": LIBTAYO_TRIAL,
                "policy_number": "NFC-2025-00231",
                "policy_type": PolicyType.NO_FAULT_COMPENSATION,
                "insurer": "Lloyd's of London Syndicate 457",
                "coverage_scope": CoverageScope.COUNTRY_SPECIFIC,
                "countries_covered": ["FR", "DE", "BE", "NL"],
                "coverage_amount": 10_000_000.0,
                "deductible": 0.0,
                "premium": 195_000.0,
                "premium_currency": "EUR",
                "effective_date": now - timedelta(days=90),
                "expiry_date": now + timedelta(days=25),
                "renewal_date": now + timedelta(days=10),
                "status": PolicyStatus.PENDING_RENEWAL,
                "broker": "Aon Life Sciences",
                "special_conditions": "No-fault compensation as required by EU Clinical Trials "
                "Regulation (EU) 536/2014; covers bodily injury to trial participants",
                "created_at": now - timedelta(days=100),
                "updated_at": now - timedelta(days=2),
            },
            {
                "id": "POL-004",
                "trial_id": EYLEA_TRIAL,
                "policy_number": "PI-2024-01205",
                "policy_type": PolicyType.PROFESSIONAL_INDEMNITY,
                "insurer": "Chubb Life Sciences",
                "coverage_scope": CoverageScope.GLOBAL,
                "countries_covered": ["US", "UK", "DE", "FR", "JP"],
                "coverage_amount": 15_000_000.0,
                "deductible": 75_000.0,
                "premium": 310_000.0,
                "premium_currency": "USD",
                "effective_date": now - timedelta(days=400),
                "expiry_date": now - timedelta(days=35),
                "renewal_date": None,
                "status": PolicyStatus.EXPIRED,
                "broker": "Marsh McLennan Life Sciences",
                "special_conditions": None,
                "created_at": now - timedelta(days=420),
                "updated_at": now - timedelta(days=35),
            },
        ]

        for p in policies_data:
            self._policies[p["id"]] = InsurancePolicy(**p)

        # --- 6 Insurance Certificates ---
        certificates_data = [
            {
                "id": "CERT-001",
                "policy_id": "POL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "certificate_number": "COI-2025-US-0147-001",
                "issued_date": now - timedelta(days=170),
                "expiry_date": now + timedelta(days=185),
                "coverage_amount": 50_000_000.0,
                "status": CertificateStatus.ACTIVE,
                "regulatory_requirement": "21 CFR 312 - IND Application Insurance Requirement",
                "country": "US",
                "filed_with_authority": True,
                "authority_name": "FDA",
                "filing_date": now - timedelta(days=165),
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "CERT-002",
                "policy_id": "POL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "certificate_number": "COI-2025-UK-0147-002",
                "issued_date": now - timedelta(days=160),
                "expiry_date": now + timedelta(days=185),
                "coverage_amount": 50_000_000.0,
                "status": CertificateStatus.ACTIVE,
                "regulatory_requirement": "UK Medicines for Human Use (Clinical Trials) Regulations 2004",
                "country": "UK",
                "filed_with_authority": True,
                "authority_name": "MHRA",
                "filing_date": now - timedelta(days=155),
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "CERT-003",
                "policy_id": "POL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "certificate_number": "COI-2025-DE-0147-003",
                "issued_date": now - timedelta(days=150),
                "expiry_date": now + timedelta(days=185),
                "coverage_amount": 50_000_000.0,
                "status": CertificateStatus.ACTIVE,
                "regulatory_requirement": "Arzneimittelgesetz (AMG) Section 40 - Insurance Requirement",
                "country": "DE",
                "filed_with_authority": True,
                "authority_name": "BfArM",
                "filing_date": now - timedelta(days=145),
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CERT-004",
                "policy_id": "POL-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "certificate_number": "COI-2025-US-0892-001",
                "issued_date": now - timedelta(days=110),
                "expiry_date": now + timedelta(days=245),
                "coverage_amount": 25_000_000.0,
                "status": CertificateStatus.ACTIVE,
                "regulatory_requirement": "21 CFR 312 - IND Application Insurance Requirement",
                "country": "US",
                "filed_with_authority": True,
                "authority_name": "FDA",
                "filing_date": now - timedelta(days=105),
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "CERT-005",
                "policy_id": "POL-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "certificate_number": "COI-2025-FR-0231-001",
                "issued_date": now - timedelta(days=85),
                "expiry_date": now + timedelta(days=25),
                "coverage_amount": 10_000_000.0,
                "status": CertificateStatus.ACTIVE,
                "regulatory_requirement": "EU CTR 536/2014 Article 76 - Damage Compensation",
                "country": "FR",
                "filed_with_authority": True,
                "authority_name": "ANSM",
                "filing_date": now - timedelta(days=80),
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "CERT-006",
                "policy_id": "POL-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "certificate_number": "COI-2025-DE-0231-002",
                "issued_date": now - timedelta(days=80),
                "expiry_date": now + timedelta(days=25),
                "coverage_amount": 10_000_000.0,
                "status": CertificateStatus.PENDING,
                "regulatory_requirement": "Arzneimittelgesetz (AMG) Section 40",
                "country": "DE",
                "filed_with_authority": False,
                "authority_name": "BfArM",
                "filing_date": None,
                "created_at": now - timedelta(days=80),
            },
        ]

        for c in certificates_data:
            self._certificates[c["id"]] = InsuranceCertificate(**c)

        # --- 3 Insurance Claims ---
        claims_data = [
            {
                "id": "CLM-001",
                "policy_id": "POL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "patient_id": "PAT-00142",
                "claim_number": "CLM-2025-0147-001",
                "claim_date": now - timedelta(days=60),
                "incident_date": now - timedelta(days=75),
                "incident_description": "Patient experienced severe allergic reaction during "
                "study drug administration requiring emergency hospitalization. "
                "Reaction occurred 15 minutes post-infusion.",
                "claim_amount": 285_000.0,
                "settled_amount": 220_000.0,
                "status": ClaimStatus.SETTLED,
                "adjuster": "Karen Whitfield, AIG Claims",
                "investigation_notes": "Investigation confirmed reaction was related to study "
                "drug. Site followed proper emergency protocols. Settlement "
                "covers medical expenses and patient compensation.",
                "resolution_date": now - timedelta(days=15),
                "created_at": now - timedelta(days=58),
                "updated_at": now - timedelta(days=15),
            },
            {
                "id": "CLM-002",
                "policy_id": "POL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "patient_id": "PAT-00287",
                "claim_number": "CLM-2025-0147-002",
                "claim_date": now - timedelta(days=20),
                "incident_date": now - timedelta(days=30),
                "incident_description": "Patient developed hepatotoxicity Grade 3 during "
                "treatment period. Hospitalized for 5 days with elevated "
                "liver enzymes. Causality assessment pending.",
                "claim_amount": 450_000.0,
                "settled_amount": None,
                "status": ClaimStatus.UNDER_INVESTIGATION,
                "adjuster": "James Morton, AIG Claims",
                "investigation_notes": "Medical records under review. Independent causality "
                "assessment commissioned from expert hepatologist.",
                "resolution_date": None,
                "created_at": now - timedelta(days=18),
                "updated_at": now - timedelta(days=3),
            },
            {
                "id": "CLM-003",
                "policy_id": "POL-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "patient_id": "PAT-00531",
                "claim_number": "CLM-2025-0892-001",
                "claim_date": now - timedelta(days=10),
                "incident_date": now - timedelta(days=18),
                "incident_description": "Patient reported persistent vision changes after "
                "intravitreal injection at study visit 4. Ophthalmology "
                "consultation ordered to assess potential retinal damage.",
                "claim_amount": 175_000.0,
                "settled_amount": None,
                "status": ClaimStatus.FILED,
                "adjuster": None,
                "investigation_notes": None,
                "resolution_date": None,
                "created_at": now - timedelta(days=9),
                "updated_at": now - timedelta(days=9),
            },
        ]

        for c in claims_data:
            self._claims[c["id"]] = InsuranceClaim(**c)

        # --- 5 Coverage Requirements ---
        requirements_data = [
            {
                "id": "REQ-001",
                "trial_id": EYLEA_TRIAL,
                "country": "US",
                "regulatory_authority": "FDA",
                "required_policy_type": PolicyType.CLINICAL_TRIAL_LIABILITY,
                "minimum_coverage_amount": 10_000_000.0,
                "per_patient_minimum": 500_000.0,
                "aggregate_minimum": 10_000_000.0,
                "proof_required": True,
                "deadline": now - timedelta(days=160),
                "met": True,
                "notes": "Certificate of insurance filed with IND application",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "REQ-002",
                "trial_id": EYLEA_TRIAL,
                "country": "DE",
                "regulatory_authority": "BfArM",
                "required_policy_type": PolicyType.CLINICAL_TRIAL_LIABILITY,
                "minimum_coverage_amount": 500_000.0,
                "per_patient_minimum": 500_000.0,
                "aggregate_minimum": 500_000.0,
                "proof_required": True,
                "deadline": now - timedelta(days=140),
                "met": True,
                "notes": "AMG Section 40 requires mandatory insurance for all trial participants in Germany",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "REQ-003",
                "trial_id": LIBTAYO_TRIAL,
                "country": "FR",
                "regulatory_authority": "ANSM",
                "required_policy_type": PolicyType.NO_FAULT_COMPENSATION,
                "minimum_coverage_amount": 8_000_000.0,
                "per_patient_minimum": 300_000.0,
                "aggregate_minimum": 8_000_000.0,
                "proof_required": True,
                "deadline": now - timedelta(days=80),
                "met": True,
                "notes": "EU CTR 536/2014 Article 76 requires no-fault compensation coverage",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "REQ-004",
                "trial_id": LIBTAYO_TRIAL,
                "country": "BE",
                "regulatory_authority": "FAMHP",
                "required_policy_type": PolicyType.NO_FAULT_COMPENSATION,
                "minimum_coverage_amount": 5_000_000.0,
                "per_patient_minimum": 250_000.0,
                "aggregate_minimum": 5_000_000.0,
                "proof_required": True,
                "deadline": now + timedelta(days=30),
                "met": False,
                "notes": "Certificate not yet filed with Belgian FAMHP; deadline approaching",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "REQ-005",
                "trial_id": DUPIXENT_TRIAL,
                "country": "US",
                "regulatory_authority": "FDA",
                "required_policy_type": PolicyType.PRODUCT_LIABILITY,
                "minimum_coverage_amount": 15_000_000.0,
                "per_patient_minimum": 1_000_000.0,
                "aggregate_minimum": 15_000_000.0,
                "proof_required": True,
                "deadline": now - timedelta(days=100),
                "met": True,
                "notes": "Product liability coverage required for IND application",
                "created_at": now - timedelta(days=140),
            },
        ]

        for r in requirements_data:
            self._requirements[r["id"]] = CoverageRequirement(**r)

        # --- 3 Insurance Renewals ---
        renewals_data = [
            {
                "id": "RNW-001",
                "policy_id": "POL-003",
                "renewal_date": now + timedelta(days=10),
                "new_premium": 215_000.0,
                "premium_change_pct": 10.26,
                "coverage_changes": "Increased aggregate limit from EUR 10M to EUR 12M; "
                "added Belgium as covered country",
                "approved_by": None,
                "approved_date": None,
                "status": RenewalStatus.PENDING,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RNW-002",
                "policy_id": "POL-001",
                "renewal_date": now + timedelta(days=155),
                "new_premium": 910_000.0,
                "premium_change_pct": 4.0,
                "coverage_changes": "No material changes; standard renewal with inflation adjustment",
                "approved_by": "Dr. Sarah Chen, VP Clinical Operations",
                "approved_date": now - timedelta(days=5),
                "status": RenewalStatus.APPROVED,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RNW-003",
                "policy_id": "POL-004",
                "renewal_date": now - timedelta(days=35),
                "new_premium": 340_000.0,
                "premium_change_pct": 9.68,
                "coverage_changes": "Added cyber liability endorsement; increased deductible to $100K",
                "approved_by": None,
                "approved_date": None,
                "status": RenewalStatus.REJECTED,
                "created_at": now - timedelta(days=60),
            },
        ]

        for r in renewals_data:
            self._renewals[r["id"]] = InsuranceRenewal(**r)

    # ------------------------------------------------------------------
    # Policy Management
    # ------------------------------------------------------------------

    def list_policies(
        self,
        *,
        trial_id: str | None = None,
        policy_type: PolicyType | None = None,
        status: PolicyStatus | None = None,
    ) -> list[InsurancePolicy]:
        """List insurance policies with optional filters."""
        with self._lock:
            result = list(self._policies.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if policy_type is not None:
            result = [p for p in result if p.policy_type == policy_type]
        if status is not None:
            result = [p for p in result if p.status == status]

        return sorted(result, key=lambda p: p.created_at, reverse=True)

    def get_policy(self, policy_id: str) -> InsurancePolicy | None:
        """Get a single policy by ID."""
        with self._lock:
            return self._policies.get(policy_id)

    def create_policy(self, payload: InsurancePolicyCreate) -> InsurancePolicy:
        """Create a new insurance policy."""
        now = datetime.now(timezone.utc)
        policy_id = f"POL-{uuid4().hex[:8].upper()}"
        policy = InsurancePolicy(
            id=policy_id,
            status=PolicyStatus.DRAFT,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._policies[policy_id] = policy
        logger.info("Created insurance policy %s: %s", policy_id, payload.policy_number)
        return policy

    def update_policy(
        self, policy_id: str, payload: InsurancePolicyUpdate
    ) -> InsurancePolicy | None:
        """Update an existing insurance policy."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._policies.get(policy_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = InsurancePolicy(**data)
            self._policies[policy_id] = updated
        return updated

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy. Returns True if deleted, False if not found."""
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Certificate Management
    # ------------------------------------------------------------------

    def list_certificates(
        self,
        *,
        policy_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: CertificateStatus | None = None,
        country: str | None = None,
    ) -> list[InsuranceCertificate]:
        """List insurance certificates with optional filters."""
        with self._lock:
            result = list(self._certificates.values())

        if policy_id is not None:
            result = [c for c in result if c.policy_id == policy_id]
        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if status is not None:
            result = [c for c in result if c.status == status]
        if country is not None:
            result = [c for c in result if c.country == country]

        return sorted(result, key=lambda c: c.issued_date, reverse=True)

    def get_certificate(self, certificate_id: str) -> InsuranceCertificate | None:
        """Get a single certificate by ID."""
        with self._lock:
            return self._certificates.get(certificate_id)

    def issue_certificate(
        self, payload: InsuranceCertificateCreate
    ) -> InsuranceCertificate:
        """Issue a new insurance certificate for a site.

        Validates that the referenced policy exists and is active.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            policy = self._policies.get(payload.policy_id)

        if policy is None:
            raise ValueError(f"Policy '{payload.policy_id}' not found")
        if policy.status not in (PolicyStatus.ACTIVE, PolicyStatus.PENDING_RENEWAL):
            raise ValueError(
                f"Policy '{payload.policy_id}' is not active (status: {policy.status.value})"
            )

        cert_id = f"CERT-{uuid4().hex[:8].upper()}"
        cert_number = f"COI-{now.year}-{payload.country}-{policy.policy_number[-4:]}-{uuid4().hex[:3].upper()}"

        cert = InsuranceCertificate(
            id=cert_id,
            policy_id=payload.policy_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            certificate_number=cert_number,
            issued_date=now,
            expiry_date=policy.expiry_date,
            coverage_amount=payload.coverage_amount,
            status=CertificateStatus.ACTIVE,
            regulatory_requirement=payload.regulatory_requirement,
            country=payload.country,
            filed_with_authority=False,
            authority_name=payload.authority_name,
            filing_date=None,
            created_at=now,
        )

        with self._lock:
            self._certificates[cert_id] = cert

        logger.info(
            "Issued certificate %s for policy %s site %s country %s",
            cert_id, payload.policy_id, payload.site_id, payload.country,
        )
        return cert

    def update_certificate(
        self, certificate_id: str, payload: InsuranceCertificateUpdate
    ) -> InsuranceCertificate | None:
        """Update an insurance certificate."""
        with self._lock:
            existing = self._certificates.get(certificate_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InsuranceCertificate(**data)
            self._certificates[certificate_id] = updated
        return updated

    def delete_certificate(self, certificate_id: str) -> bool:
        """Delete a certificate. Returns True if deleted."""
        with self._lock:
            if certificate_id in self._certificates:
                del self._certificates[certificate_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Claims Management
    # ------------------------------------------------------------------

    def list_claims(
        self,
        *,
        policy_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: ClaimStatus | None = None,
    ) -> list[InsuranceClaim]:
        """List insurance claims with optional filters."""
        with self._lock:
            result = list(self._claims.values())

        if policy_id is not None:
            result = [c for c in result if c.policy_id == policy_id]
        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.claim_date, reverse=True)

    def get_claim(self, claim_id: str) -> InsuranceClaim | None:
        """Get a single claim by ID."""
        with self._lock:
            return self._claims.get(claim_id)

    def file_claim(self, payload: InsuranceClaimCreate) -> InsuranceClaim:
        """File a new insurance claim.

        Validates that the referenced policy exists and is active.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            policy = self._policies.get(payload.policy_id)

        if policy is None:
            raise ValueError(f"Policy '{payload.policy_id}' not found")
        if policy.status not in (
            PolicyStatus.ACTIVE,
            PolicyStatus.PENDING_RENEWAL,
            PolicyStatus.RENEWED,
        ):
            raise ValueError(
                f"Policy '{payload.policy_id}' is not active (status: {policy.status.value})"
            )

        claim_id = f"CLM-{uuid4().hex[:8].upper()}"
        claim_number = f"CLM-{now.year}-{policy.policy_number[-4:]}-{uuid4().hex[:3].upper()}"

        claim = InsuranceClaim(
            id=claim_id,
            policy_id=payload.policy_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            patient_id=payload.patient_id,
            claim_number=claim_number,
            claim_date=now,
            incident_date=payload.incident_date,
            incident_description=payload.incident_description,
            claim_amount=payload.claim_amount,
            settled_amount=None,
            status=ClaimStatus.FILED,
            adjuster=None,
            investigation_notes=None,
            resolution_date=None,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._claims[claim_id] = claim

        logger.info(
            "Filed claim %s against policy %s for amount %.2f",
            claim_id, payload.policy_id, payload.claim_amount,
        )
        return claim

    def update_claim(
        self, claim_id: str, payload: InsuranceClaimUpdate
    ) -> InsuranceClaim | None:
        """Update an insurance claim."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._claims.get(claim_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolution_date when status moves to terminal state
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ClaimStatus(new_status)
                if new_status in (
                    ClaimStatus.SETTLED,
                    ClaimStatus.DENIED,
                    ClaimStatus.CLOSED,
                ) and existing.status not in (
                    ClaimStatus.SETTLED,
                    ClaimStatus.DENIED,
                    ClaimStatus.CLOSED,
                ):
                    if "resolution_date" not in updates or updates["resolution_date"] is None:
                        updates["resolution_date"] = now

            data.update(updates)
            data["updated_at"] = now
            updated = InsuranceClaim(**data)
            self._claims[claim_id] = updated
        return updated

    def delete_claim(self, claim_id: str) -> bool:
        """Delete a claim. Returns True if deleted."""
        with self._lock:
            if claim_id in self._claims:
                del self._claims[claim_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Coverage Requirements
    # ------------------------------------------------------------------

    def list_requirements(
        self,
        *,
        trial_id: str | None = None,
        country: str | None = None,
        met: bool | None = None,
    ) -> list[CoverageRequirement]:
        """List coverage requirements with optional filters."""
        with self._lock:
            result = list(self._requirements.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if country is not None:
            result = [r for r in result if r.country == country]
        if met is not None:
            result = [r for r in result if r.met == met]

        return sorted(result, key=lambda r: r.deadline)

    def get_requirement(self, requirement_id: str) -> CoverageRequirement | None:
        """Get a single coverage requirement by ID."""
        with self._lock:
            return self._requirements.get(requirement_id)

    def create_requirement(
        self, payload: CoverageRequirementCreate
    ) -> CoverageRequirement:
        """Create a new coverage requirement."""
        now = datetime.now(timezone.utc)
        req_id = f"REQ-{uuid4().hex[:8].upper()}"
        req = CoverageRequirement(
            id=req_id,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._requirements[req_id] = req
        logger.info(
            "Created coverage requirement %s for trial %s country %s",
            req_id, payload.trial_id, payload.country,
        )
        return req

    def update_requirement(
        self, requirement_id: str, payload: CoverageRequirementUpdate
    ) -> CoverageRequirement | None:
        """Update a coverage requirement."""
        with self._lock:
            existing = self._requirements.get(requirement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CoverageRequirement(**data)
            self._requirements[requirement_id] = updated
        return updated

    def delete_requirement(self, requirement_id: str) -> bool:
        """Delete a requirement. Returns True if deleted."""
        with self._lock:
            if requirement_id in self._requirements:
                del self._requirements[requirement_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Coverage Compliance
    # ------------------------------------------------------------------

    def check_coverage_compliance(
        self, trial_id: str
    ) -> CoverageComplianceResult:
        """Check coverage compliance for a trial.

        Evaluates all coverage requirements for the given trial and determines
        which are met and which are not.
        """
        with self._lock:
            requirements = [
                r for r in self._requirements.values() if r.trial_id == trial_id
            ]

        if not requirements:
            return CoverageComplianceResult(
                trial_id=trial_id,
                total_requirements=0,
                requirements_met=0,
                requirements_unmet=0,
                compliance_pct=100.0,
                fully_compliant=True,
                unmet_details=[],
            )

        met_count = sum(1 for r in requirements if r.met)
        unmet = [r for r in requirements if not r.met]
        total = len(requirements)
        pct = round((met_count / total) * 100.0, 1) if total > 0 else 100.0

        return CoverageComplianceResult(
            trial_id=trial_id,
            total_requirements=total,
            requirements_met=met_count,
            requirements_unmet=len(unmet),
            compliance_pct=pct,
            fully_compliant=len(unmet) == 0,
            unmet_details=unmet,
        )

    # ------------------------------------------------------------------
    # Renewal Management
    # ------------------------------------------------------------------

    def list_renewals(
        self,
        *,
        policy_id: str | None = None,
        status: RenewalStatus | None = None,
    ) -> list[InsuranceRenewal]:
        """List renewals with optional filters."""
        with self._lock:
            result = list(self._renewals.values())

        if policy_id is not None:
            result = [r for r in result if r.policy_id == policy_id]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.renewal_date)

    def get_renewal(self, renewal_id: str) -> InsuranceRenewal | None:
        """Get a single renewal by ID."""
        with self._lock:
            return self._renewals.get(renewal_id)

    def initiate_renewal(
        self, payload: InsuranceRenewalCreate
    ) -> InsuranceRenewal:
        """Initiate a policy renewal.

        Validates that the referenced policy exists.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            policy = self._policies.get(payload.policy_id)

        if policy is None:
            raise ValueError(f"Policy '{payload.policy_id}' not found")

        renewal_id = f"RNW-{uuid4().hex[:8].upper()}"
        renewal = InsuranceRenewal(
            id=renewal_id,
            status=RenewalStatus.PENDING,
            created_at=now,
            **payload.model_dump(),
        )

        with self._lock:
            self._renewals[renewal_id] = renewal
            # Update policy status to pending_renewal
            data = policy.model_dump()
            data["status"] = PolicyStatus.PENDING_RENEWAL
            data["updated_at"] = now
            self._policies[payload.policy_id] = InsurancePolicy(**data)

        logger.info(
            "Initiated renewal %s for policy %s", renewal_id, payload.policy_id
        )
        return renewal

    def update_renewal(
        self, renewal_id: str, payload: InsuranceRenewalUpdate
    ) -> InsuranceRenewal | None:
        """Update a renewal record."""
        with self._lock:
            existing = self._renewals.get(renewal_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InsuranceRenewal(**data)
            self._renewals[renewal_id] = updated
        return updated

    def delete_renewal(self, renewal_id: str) -> bool:
        """Delete a renewal. Returns True if deleted."""
        with self._lock:
            if renewal_id in self._renewals:
                del self._renewals[renewal_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Expiring Policies
    # ------------------------------------------------------------------

    def get_expiring_policies(
        self, days: int = 90
    ) -> list[InsurancePolicy]:
        """Get policies expiring within the specified number of days."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)

        with self._lock:
            result = [
                p for p in self._policies.values()
                if p.status in (PolicyStatus.ACTIVE, PolicyStatus.PENDING_RENEWAL)
                and p.expiry_date <= cutoff
            ]

        return sorted(result, key=lambda p: p.expiry_date)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> InsuranceMetrics:
        """Compute aggregated insurance operational metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            policies = list(self._policies.values())
            certificates = list(self._certificates.values())
            claims = list(self._claims.values())
            requirements = list(self._requirements.values())
            renewals = list(self._renewals.values())

        # Policies
        active_policies = [
            p for p in policies
            if p.status in (PolicyStatus.ACTIVE, PolicyStatus.PENDING_RENEWAL)
        ]
        policies_by_type: dict[str, int] = {}
        policies_by_status: dict[str, int] = {}
        for p in policies:
            policies_by_type[p.policy_type.value] = (
                policies_by_type.get(p.policy_type.value, 0) + 1
            )
            policies_by_status[p.status.value] = (
                policies_by_status.get(p.status.value, 0) + 1
            )

        total_coverage = sum(p.coverage_amount for p in active_policies)
        total_premium = sum(p.premium for p in active_policies)

        # Certificates
        active_certificates = sum(
            1 for c in certificates if c.status == CertificateStatus.ACTIVE
        )

        # Claims
        open_claim_statuses = (
            ClaimStatus.FILED,
            ClaimStatus.UNDER_INVESTIGATION,
            ClaimStatus.APPROVED,
        )
        open_claims = sum(1 for c in claims if c.status in open_claim_statuses)
        total_claimed = sum(c.claim_amount for c in claims)
        total_settled = sum(
            c.settled_amount for c in claims if c.settled_amount is not None
        )

        # Requirements
        requirements_met = sum(1 for r in requirements if r.met)
        total_req = len(requirements)
        compliance_pct = (
            round((requirements_met / total_req) * 100.0, 1) if total_req > 0 else 100.0
        )

        # Renewals
        pending_renewals = sum(
            1 for r in renewals if r.status == RenewalStatus.PENDING
        )

        # Expiring policies
        cutoff_30 = now + timedelta(days=30)
        cutoff_90 = now + timedelta(days=90)
        expiring_30 = sum(
            1 for p in active_policies if p.expiry_date <= cutoff_30
        )
        expiring_90 = sum(
            1 for p in active_policies if p.expiry_date <= cutoff_90
        )

        return InsuranceMetrics(
            total_policies=len(policies),
            active_policies=len(active_policies),
            policies_by_type=policies_by_type,
            policies_by_status=policies_by_status,
            total_coverage_amount=total_coverage,
            total_premium=total_premium,
            total_certificates=len(certificates),
            active_certificates=active_certificates,
            total_claims=len(claims),
            open_claims=open_claims,
            total_claimed_amount=total_claimed,
            total_settled_amount=total_settled,
            total_requirements=total_req,
            requirements_met=requirements_met,
            compliance_pct=compliance_pct,
            pending_renewals=pending_renewals,
            expiring_within_30_days=expiring_30,
            expiring_within_90_days=expiring_90,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TrialInsuranceService | None = None
_instance_lock = threading.Lock()


def get_trial_insurance_service() -> TrialInsuranceService:
    """Return the singleton TrialInsuranceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TrialInsuranceService()
    return _instance


def reset_trial_insurance_service() -> TrialInsuranceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = TrialInsuranceService()
    return _instance
