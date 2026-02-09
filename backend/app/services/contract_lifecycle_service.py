"""Contract Lifecycle Management Service (CLO-6).

Manages pharma-grade contract lifecycle including IP management, contract
versioning, milestone tracking, amendment workflows, and compliance obligations
for the clinical trial patient recruitment platform.

Usage:
    from app.services.contract_lifecycle_service import get_contract_lifecycle_service

    service = get_contract_lifecycle_service()
    contracts = service.list_contracts()
    metrics = service.get_metrics()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.contract_lifecycle import (
    AmendmentCreateRequest,
    Contract,
    ContractAmendment,
    ContractComplianceReport,
    ContractCreateRequest,
    ContractListResponse,
    ContractMetrics,
    ContractMilestone,
    ContractObligation,
    ContractParty,
    ContractStatus,
    ContractType,
    ContractUpdateRequest,
    IPRecord,
    IPRecordCreateRequest,
    IPRecordListResponse,
    IPType,
    MilestoneCreateRequest,
    MilestoneStatus,
    ObligationCreateRequest,
    ObligationType,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_contract_service_instance: ContractLifecycleService | None = None
_contract_service_lock = Lock()

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[ContractStatus, set[ContractStatus]] = {
    ContractStatus.DRAFT: {ContractStatus.REVIEW},
    ContractStatus.REVIEW: {ContractStatus.NEGOTIATION, ContractStatus.DRAFT},
    ContractStatus.NEGOTIATION: {
        ContractStatus.PENDING_SIGNATURE,
        ContractStatus.REVIEW,
    },
    ContractStatus.PENDING_SIGNATURE: {
        ContractStatus.ACTIVE,
        ContractStatus.NEGOTIATION,
    },
    ContractStatus.ACTIVE: {
        ContractStatus.EXPIRED,
        ContractStatus.TERMINATED,
        ContractStatus.RENEWED,
        ContractStatus.SUSPENDED,
    },
    ContractStatus.SUSPENDED: {ContractStatus.ACTIVE, ContractStatus.TERMINATED},
    ContractStatus.RENEWED: {ContractStatus.ACTIVE},
    ContractStatus.EXPIRED: set(),
    ContractStatus.TERMINATED: set(),
}


def _build_seed_data() -> (
    tuple[list[Contract], list[IPRecord]]
):
    """Build pre-populated contracts and IP records for demo/seed data."""
    now = datetime.now(timezone.utc)
    one_year_ago = now - timedelta(days=365)
    six_months_ago = now - timedelta(days=180)
    three_months_ago = now - timedelta(days=90)
    one_year_ahead = now + timedelta(days=365)
    six_months_ahead = now + timedelta(days=180)
    three_months_ahead = now + timedelta(days=90)
    two_months_ahead = now + timedelta(days=60)
    thirty_days_ahead = now + timedelta(days=30)
    sixty_days_ahead = now + timedelta(days=60)
    expired_30_days = now - timedelta(days=30)

    contracts: list[Contract] = []

    # -----------------------------------------------------------------------
    # 1. Master Service Agreement with Regeneron
    # -----------------------------------------------------------------------
    msa_milestones = [
        ContractMilestone(
            id="MS-001",
            contract_id="CTR-001",
            title="Platform Deployment Phase 1",
            description="Deploy patient recruitment platform for initial trial sites",
            due_date=three_months_ago,
            status=MilestoneStatus.COMPLETED,
            responsible_party="BrainStorm Health",
            deliverable="Production deployment for 10 sites",
            completion_date=three_months_ago + timedelta(days=5),
        ),
        ContractMilestone(
            id="MS-002",
            contract_id="CTR-001",
            title="Platform Deployment Phase 2",
            description="Expand to remaining trial sites with full screening engine",
            due_date=three_months_ahead,
            status=MilestoneStatus.IN_PROGRESS,
            responsible_party="BrainStorm Health",
            deliverable="Production deployment for 50 sites",
        ),
        ContractMilestone(
            id="MS-003",
            contract_id="CTR-001",
            title="Year-1 Performance Review",
            description="Annual performance review and SLA compliance audit",
            due_date=sixty_days_ahead,
            status=MilestoneStatus.PENDING,
            responsible_party="Both Parties",
            deliverable="Annual performance report",
        ),
    ]

    msa_obligations = [
        ContractObligation(
            id="OBL-001",
            contract_id="CTR-001",
            obligation_type=ObligationType.REPORTING,
            description="Monthly screening performance report to Regeneron",
            owner="BrainStorm Health",
            due_date=thirty_days_ahead,
            recurring=True,
            frequency_days=30,
            status=MilestoneStatus.PENDING,
        ),
        ContractObligation(
            id="OBL-002",
            contract_id="CTR-001",
            obligation_type=ObligationType.FINANCIAL,
            description="Quarterly license fee payment",
            owner="Regeneron Pharmaceuticals",
            due_date=two_months_ahead,
            recurring=True,
            frequency_days=90,
            status=MilestoneStatus.PENDING,
        ),
        ContractObligation(
            id="OBL-003",
            contract_id="CTR-001",
            obligation_type=ObligationType.REGULATORY,
            description="Annual HIPAA compliance attestation",
            owner="BrainStorm Health",
            due_date=six_months_ahead,
            recurring=True,
            frequency_days=365,
            status=MilestoneStatus.PENDING,
        ),
    ]

    contracts.append(
        Contract(
            id="CTR-001",
            title="Master Service Agreement - Regeneron Pharmaceuticals",
            contract_type=ContractType.MASTER_SERVICE,
            status=ContractStatus.ACTIVE,
            description=(
                "Master service agreement for clinical trial patient recruitment "
                "platform services. Covers EYLEA HD, DUPIXENT, and LIBTAYO trials."
            ),
            parties=[
                ContractParty(
                    name="Regeneron Pharmaceuticals, Inc.",
                    role="Sponsor",
                    contact_email="contracts@regeneron.com",
                    organization="Regeneron Pharmaceuticals",
                ),
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Service Provider",
                    contact_email="legal@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
            ],
            effective_date=one_year_ago,
            expiry_date=one_year_ahead,
            auto_renew=True,
            renewal_notice_days=90,
            total_value=2400000.0,
            currency="USD",
            milestones=msa_milestones,
            obligations=msa_obligations,
            amendments=[],
            ip_records=["IP-001", "IP-002"],
            created_at=one_year_ago - timedelta(days=30),
            updated_at=now,
            signed_date=one_year_ago,
            risk_level=RiskLevel.HIGH,
            tags=["regeneron", "msa", "patient-recruitment", "multi-trial"],
        )
    )

    # -----------------------------------------------------------------------
    # 2. BAA with Metriport
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-002",
            title="Business Associate Agreement - Metriport",
            contract_type=ContractType.BAA,
            status=ContractStatus.ACTIVE,
            description=(
                "HIPAA Business Associate Agreement governing the handling of PHI "
                "through Metriport's healthcare data integration platform."
            ),
            parties=[
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Covered Entity",
                    contact_email="legal@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
                ContractParty(
                    name="Metriport, Inc.",
                    role="Business Associate",
                    contact_email="legal@metriport.com",
                    organization="Metriport",
                ),
            ],
            effective_date=one_year_ago,
            expiry_date=one_year_ahead,
            auto_renew=True,
            renewal_notice_days=60,
            total_value=0.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-004",
                    contract_id="CTR-002",
                    title="Annual BAA Review",
                    description="Annual review of BAA terms and compliance",
                    due_date=three_months_ahead,
                    status=MilestoneStatus.PENDING,
                    responsible_party="Both Parties",
                    deliverable="BAA review summary",
                ),
                ContractMilestone(
                    id="MS-005",
                    contract_id="CTR-002",
                    title="Security Assessment",
                    description="Independent security assessment of PHI handling",
                    due_date=two_months_ahead,
                    status=MilestoneStatus.PENDING,
                    responsible_party="Metriport",
                    deliverable="Security assessment report",
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-004",
                    contract_id="CTR-002",
                    obligation_type=ObligationType.DATA_DELIVERY,
                    description="Breach notification within 72 hours",
                    owner="Metriport",
                    due_date=one_year_ahead,
                    recurring=False,
                    status=MilestoneStatus.PENDING,
                ),
                ContractObligation(
                    id="OBL-005",
                    contract_id="CTR-002",
                    obligation_type=ObligationType.CONFIDENTIALITY,
                    description="PHI encryption at rest and in transit",
                    owner="Metriport",
                    due_date=one_year_ahead,
                    recurring=False,
                    status=MilestoneStatus.COMPLETED,
                    last_completed=three_months_ago,
                ),
            ],
            created_at=one_year_ago,
            updated_at=now,
            signed_date=one_year_ago,
            risk_level=RiskLevel.CRITICAL,
            tags=["metriport", "baa", "hipaa", "phi"],
        )
    )

    # -----------------------------------------------------------------------
    # 3. Clinical Trial Agreement for EYLEA HD
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-003",
            title="Clinical Trial Agreement - EYLEA HD (aflibercept 8 mg)",
            contract_type=ContractType.CLINICAL_TRIAL,
            status=ContractStatus.ACTIVE,
            description=(
                "Clinical trial site agreement for EYLEA HD patient screening "
                "and recruitment support across Phase III/IV sites."
            ),
            parties=[
                ContractParty(
                    name="Regeneron Pharmaceuticals, Inc.",
                    role="Sponsor",
                    contact_email="trials@regeneron.com",
                    organization="Regeneron Pharmaceuticals",
                ),
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Technology Partner",
                    contact_email="trials@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
            ],
            effective_date=six_months_ago,
            expiry_date=one_year_ahead,
            auto_renew=False,
            renewal_notice_days=90,
            total_value=850000.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-006",
                    contract_id="CTR-003",
                    title="First Patient Screened",
                    description="First patient screened through the platform",
                    due_date=three_months_ago,
                    status=MilestoneStatus.COMPLETED,
                    responsible_party="BrainStorm Health",
                    deliverable="Screening confirmation report",
                    completion_date=three_months_ago + timedelta(days=10),
                ),
                ContractMilestone(
                    id="MS-007",
                    contract_id="CTR-003",
                    title="50% Enrollment Target",
                    description="Reach 50% of target enrollment across sites",
                    due_date=sixty_days_ahead,
                    status=MilestoneStatus.IN_PROGRESS,
                    responsible_party="BrainStorm Health",
                    deliverable="Enrollment status report",
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-006",
                    contract_id="CTR-003",
                    obligation_type=ObligationType.REPORTING,
                    description="Weekly screening activity report",
                    owner="BrainStorm Health",
                    due_date=now + timedelta(days=7),
                    recurring=True,
                    frequency_days=7,
                    status=MilestoneStatus.PENDING,
                ),
                ContractObligation(
                    id="OBL-007",
                    contract_id="CTR-003",
                    obligation_type=ObligationType.REGULATORY,
                    description="IRB approval maintenance for each site",
                    owner="Both Parties",
                    due_date=one_year_ahead,
                    recurring=True,
                    frequency_days=365,
                    status=MilestoneStatus.PENDING,
                ),
            ],
            created_at=six_months_ago - timedelta(days=15),
            updated_at=now,
            signed_date=six_months_ago,
            risk_level=RiskLevel.HIGH,
            tags=["eylea-hd", "clinical-trial", "regeneron", "ophthalmology"],
        )
    )

    # -----------------------------------------------------------------------
    # 4. Data Use Agreement for RWE
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-004",
            title="Data Use Agreement - Real-World Evidence Data",
            contract_type=ContractType.DATA_USE,
            status=ContractStatus.ACTIVE,
            description=(
                "Agreement governing the use of de-identified real-world evidence data "
                "for patient screening and eligibility determination."
            ),
            parties=[
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Data Recipient",
                    contact_email="data@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
                ContractParty(
                    name="Clinical Data Solutions Inc.",
                    role="Data Provider",
                    contact_email="contracts@clinicaldatasolutions.com",
                    organization="Clinical Data Solutions",
                ),
            ],
            effective_date=one_year_ago,
            expiry_date=thirty_days_ahead,
            auto_renew=False,
            renewal_notice_days=60,
            total_value=360000.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-008",
                    contract_id="CTR-004",
                    title="Initial Data Transfer",
                    description="Complete initial batch data transfer",
                    due_date=one_year_ago + timedelta(days=30),
                    status=MilestoneStatus.COMPLETED,
                    responsible_party="Clinical Data Solutions",
                    deliverable="Data transfer confirmation",
                    completion_date=one_year_ago + timedelta(days=25),
                ),
                ContractMilestone(
                    id="MS-009",
                    contract_id="CTR-004",
                    title="Data Quality Audit",
                    description="Quarterly data quality audit",
                    due_date=expired_30_days,
                    status=MilestoneStatus.OVERDUE,
                    responsible_party="Both Parties",
                    deliverable="Data quality report",
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-008",
                    contract_id="CTR-004",
                    obligation_type=ObligationType.DATA_DELIVERY,
                    description="Monthly data refresh delivery",
                    owner="Clinical Data Solutions",
                    due_date=expired_30_days,
                    recurring=True,
                    frequency_days=30,
                    status=MilestoneStatus.OVERDUE,
                    last_completed=now - timedelta(days=60),
                ),
                ContractObligation(
                    id="OBL-009",
                    contract_id="CTR-004",
                    obligation_type=ObligationType.CONFIDENTIALITY,
                    description="Data destruction upon agreement termination",
                    owner="BrainStorm Health",
                    due_date=thirty_days_ahead,
                    recurring=False,
                    status=MilestoneStatus.PENDING,
                ),
            ],
            created_at=one_year_ago - timedelta(days=20),
            updated_at=now,
            signed_date=one_year_ago,
            risk_level=RiskLevel.HIGH,
            tags=["rwe", "data-use", "clinical-data-solutions"],
        )
    )

    # -----------------------------------------------------------------------
    # 5. NDA with CRO Partner
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-005",
            title="Non-Disclosure Agreement - PharmaCRO Partners",
            contract_type=ContractType.NDA,
            status=ContractStatus.ACTIVE,
            description=(
                "Mutual NDA covering confidential information exchange "
                "with CRO partner for clinical trial coordination."
            ),
            parties=[
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Disclosing Party",
                    contact_email="legal@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
                ContractParty(
                    name="PharmaCRO Partners LLC",
                    role="Receiving Party",
                    contact_email="legal@pharmacro.com",
                    organization="PharmaCRO Partners",
                ),
            ],
            effective_date=six_months_ago,
            expiry_date=six_months_ahead,
            auto_renew=True,
            renewal_notice_days=30,
            total_value=0.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-010",
                    contract_id="CTR-005",
                    title="NDA Renewal Decision",
                    description="Decision on NDA renewal before expiry",
                    due_date=six_months_ahead - timedelta(days=30),
                    status=MilestoneStatus.PENDING,
                    responsible_party="Both Parties",
                    deliverable="Renewal decision document",
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-010",
                    contract_id="CTR-005",
                    obligation_type=ObligationType.CONFIDENTIALITY,
                    description="Return or destroy confidential materials on termination",
                    owner="Both Parties",
                    due_date=six_months_ahead,
                    recurring=False,
                    status=MilestoneStatus.PENDING,
                ),
            ],
            created_at=six_months_ago - timedelta(days=10),
            updated_at=now,
            signed_date=six_months_ago,
            risk_level=RiskLevel.LOW,
            tags=["nda", "cro", "confidentiality"],
        )
    )

    # -----------------------------------------------------------------------
    # 6. Statement of Work (EXPIRED)
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-006",
            title="Statement of Work - Platform Customization",
            contract_type=ContractType.STATEMENT_OF_WORK,
            status=ContractStatus.EXPIRED,
            description=(
                "SOW for custom platform development including protocol-specific "
                "screening criteria implementation and EDC integration."
            ),
            parties=[
                ContractParty(
                    name="Regeneron Pharmaceuticals, Inc.",
                    role="Client",
                    contact_email="it@regeneron.com",
                    organization="Regeneron Pharmaceuticals",
                ),
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Vendor",
                    contact_email="delivery@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
            ],
            effective_date=one_year_ago,
            expiry_date=expired_30_days,
            auto_renew=False,
            renewal_notice_days=30,
            total_value=450000.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-011",
                    contract_id="CTR-006",
                    title="Deliverable: EDC Integration Module",
                    description="Build and deploy EDC integration module",
                    due_date=three_months_ago,
                    status=MilestoneStatus.COMPLETED,
                    responsible_party="BrainStorm Health",
                    deliverable="EDC integration module",
                    completion_date=three_months_ago - timedelta(days=5),
                ),
                ContractMilestone(
                    id="MS-012",
                    contract_id="CTR-006",
                    title="Final Acceptance Testing",
                    description="Complete acceptance testing",
                    due_date=expired_30_days,
                    status=MilestoneStatus.COMPLETED,
                    responsible_party="Regeneron Pharmaceuticals",
                    deliverable="Acceptance test report",
                    completion_date=expired_30_days - timedelta(days=2),
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-011",
                    contract_id="CTR-006",
                    obligation_type=ObligationType.OPERATIONAL,
                    description="90-day warranty support post-delivery",
                    owner="BrainStorm Health",
                    due_date=sixty_days_ahead,
                    recurring=False,
                    status=MilestoneStatus.IN_PROGRESS,
                ),
            ],
            created_at=one_year_ago - timedelta(days=15),
            updated_at=expired_30_days,
            signed_date=one_year_ago,
            risk_level=RiskLevel.MEDIUM,
            tags=["sow", "regeneron", "customization", "edc"],
        )
    )

    # -----------------------------------------------------------------------
    # 7. Licensing Agreement (NEGOTIATION)
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-007",
            title="Technology Licensing Agreement - AI Screening Engine",
            contract_type=ContractType.LICENSING,
            status=ContractStatus.NEGOTIATION,
            description=(
                "Licensing agreement for BrainStorm Health's AI-powered patient "
                "screening engine to be used by a pharma partner."
            ),
            parties=[
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Licensor",
                    contact_email="licensing@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
                ContractParty(
                    name="Global Pharma Corp.",
                    role="Licensee",
                    contact_email="legal@globalpharma.com",
                    organization="Global Pharma Corp.",
                ),
            ],
            effective_date=None,
            expiry_date=None,
            auto_renew=False,
            renewal_notice_days=90,
            total_value=1500000.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-013",
                    contract_id="CTR-007",
                    title="Term Sheet Agreement",
                    description="Agree on commercial terms and pricing",
                    due_date=thirty_days_ahead,
                    status=MilestoneStatus.IN_PROGRESS,
                    responsible_party="Both Parties",
                    deliverable="Signed term sheet",
                ),
                ContractMilestone(
                    id="MS-014",
                    contract_id="CTR-007",
                    title="IP Audit",
                    description="Complete IP audit of screening engine",
                    due_date=two_months_ahead,
                    status=MilestoneStatus.PENDING,
                    responsible_party="BrainStorm Health",
                    deliverable="IP audit report",
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-012",
                    contract_id="CTR-007",
                    obligation_type=ObligationType.REGULATORY,
                    description="FDA 21 CFR Part 11 compliance verification",
                    owner="BrainStorm Health",
                    due_date=two_months_ahead,
                    recurring=False,
                    status=MilestoneStatus.PENDING,
                ),
            ],
            created_at=now - timedelta(days=45),
            updated_at=now,
            signed_date=None,
            risk_level=RiskLevel.HIGH,
            tags=["licensing", "ai-screening", "ip"],
        )
    )

    # -----------------------------------------------------------------------
    # 8. Amendment to MSA
    # -----------------------------------------------------------------------
    msa_amendment = ContractAmendment(
        id="AMD-001",
        contract_id="CTR-001",
        title="Amendment 1 - LIBTAYO Trial Addition",
        description="Amendment to add LIBTAYO trial to the MSA scope",
        changes_summary=(
            "Added LIBTAYO (cemiplimab) trial to covered trials. "
            "Increased total contract value by $400,000. "
            "Extended agreement through Dec 2026."
        ),
        effective_date=three_months_ago,
        approved_by="VP Legal, Regeneron",
        created_at=three_months_ago - timedelta(days=7),
    )

    contracts.append(
        Contract(
            id="CTR-008",
            title="Amendment 1 to MSA - LIBTAYO Trial Addition",
            contract_type=ContractType.AMENDMENT,
            status=ContractStatus.ACTIVE,
            description=(
                "First amendment to the Master Service Agreement (CTR-001), "
                "adding the LIBTAYO immuno-oncology trial to the scope of services."
            ),
            parties=[
                ContractParty(
                    name="Regeneron Pharmaceuticals, Inc.",
                    role="Sponsor",
                    contact_email="contracts@regeneron.com",
                    organization="Regeneron Pharmaceuticals",
                ),
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Service Provider",
                    contact_email="legal@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
            ],
            effective_date=three_months_ago,
            expiry_date=one_year_ahead,
            auto_renew=False,
            renewal_notice_days=90,
            total_value=400000.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-015",
                    contract_id="CTR-008",
                    title="LIBTAYO Screening Go-Live",
                    description="Go-live for LIBTAYO screening on the platform",
                    due_date=now + timedelta(days=14),
                    status=MilestoneStatus.IN_PROGRESS,
                    responsible_party="BrainStorm Health",
                    deliverable="Go-live confirmation",
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-013",
                    contract_id="CTR-008",
                    obligation_type=ObligationType.OPERATIONAL,
                    description="Configure LIBTAYO-specific screening criteria within 30 days",
                    owner="BrainStorm Health",
                    due_date=now + timedelta(days=14),
                    recurring=False,
                    status=MilestoneStatus.IN_PROGRESS,
                ),
            ],
            amendments=[msa_amendment],
            created_at=three_months_ago - timedelta(days=7),
            updated_at=now,
            signed_date=three_months_ago,
            risk_level=RiskLevel.MEDIUM,
            tags=["amendment", "libtayo", "regeneron", "msa"],
        )
    )

    # Also add the amendment to CTR-001
    contracts[0].amendments.append(msa_amendment)

    # -----------------------------------------------------------------------
    # 9. Additional NDA (ACTIVE, expiring soon for auto-renew testing)
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-009",
            title="Non-Disclosure Agreement - Data Analytics Partner",
            contract_type=ContractType.NDA,
            status=ContractStatus.ACTIVE,
            description=(
                "NDA with analytics partner for sharing de-identified "
                "screening metrics and platform usage data."
            ),
            parties=[
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Disclosing Party",
                    contact_email="legal@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
                ContractParty(
                    name="HealthMetrics Analytics",
                    role="Receiving Party",
                    contact_email="legal@healthmetrics.com",
                    organization="HealthMetrics Analytics",
                ),
            ],
            effective_date=one_year_ago,
            expiry_date=sixty_days_ahead,
            auto_renew=True,
            renewal_notice_days=90,
            total_value=0.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-016",
                    contract_id="CTR-009",
                    title="Renewal Review",
                    description="Review NDA terms for renewal",
                    due_date=thirty_days_ahead,
                    status=MilestoneStatus.PENDING,
                    responsible_party="Both Parties",
                    deliverable="Renewal decision",
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-014",
                    contract_id="CTR-009",
                    obligation_type=ObligationType.CONFIDENTIALITY,
                    description="Maintain data handling procedures",
                    owner="HealthMetrics Analytics",
                    due_date=sixty_days_ahead,
                    recurring=False,
                    status=MilestoneStatus.PENDING,
                ),
            ],
            created_at=one_year_ago,
            updated_at=now,
            signed_date=one_year_ago,
            risk_level=RiskLevel.LOW,
            tags=["nda", "analytics", "healthmetrics"],
        )
    )

    # -----------------------------------------------------------------------
    # 10. Clinical Trial Agreement - DUPIXENT
    # -----------------------------------------------------------------------
    contracts.append(
        Contract(
            id="CTR-010",
            title="Clinical Trial Agreement - DUPIXENT (dupilumab)",
            contract_type=ContractType.CLINICAL_TRIAL,
            status=ContractStatus.ACTIVE,
            description=(
                "Clinical trial site agreement for DUPIXENT patient screening "
                "and recruitment support for atopic dermatitis trials."
            ),
            parties=[
                ContractParty(
                    name="Regeneron Pharmaceuticals, Inc.",
                    role="Sponsor",
                    contact_email="trials@regeneron.com",
                    organization="Regeneron Pharmaceuticals",
                ),
                ContractParty(
                    name="BrainStorm Health, Inc.",
                    role="Technology Partner",
                    contact_email="trials@brainstormhealth.com",
                    organization="BrainStorm Health",
                ),
            ],
            effective_date=six_months_ago,
            expiry_date=one_year_ahead,
            auto_renew=False,
            renewal_notice_days=90,
            total_value=720000.0,
            currency="USD",
            milestones=[
                ContractMilestone(
                    id="MS-017",
                    contract_id="CTR-010",
                    title="Screening Engine Deployment",
                    description="Deploy DUPIXENT-specific screening criteria",
                    due_date=three_months_ago,
                    status=MilestoneStatus.COMPLETED,
                    responsible_party="BrainStorm Health",
                    deliverable="Deployment confirmation",
                    completion_date=three_months_ago + timedelta(days=3),
                ),
            ],
            obligations=[
                ContractObligation(
                    id="OBL-015",
                    contract_id="CTR-010",
                    obligation_type=ObligationType.REPORTING,
                    description="Bi-weekly enrollment status update",
                    owner="BrainStorm Health",
                    due_date=now + timedelta(days=14),
                    recurring=True,
                    frequency_days=14,
                    status=MilestoneStatus.PENDING,
                ),
            ],
            created_at=six_months_ago - timedelta(days=10),
            updated_at=now,
            signed_date=six_months_ago,
            risk_level=RiskLevel.MEDIUM,
            tags=["dupixent", "clinical-trial", "regeneron", "dermatology"],
        )
    )

    # -----------------------------------------------------------------------
    # IP Records
    # -----------------------------------------------------------------------
    ip_records: list[IPRecord] = [
        IPRecord(
            id="IP-001",
            title="Patient Screening Algorithm - NLP-Based Eligibility Matching",
            ip_type=IPType.PATENT,
            description=(
                "Patent covering the NLP-based patient screening algorithm that "
                "matches clinical data against trial eligibility criteria."
            ),
            filing_date=one_year_ago - timedelta(days=180),
            status="PENDING",
            registration_number=None,
            jurisdiction="US",
            owner="BrainStorm Health, Inc.",
            expiry_date=None,
            related_contracts=["CTR-001", "CTR-007"],
        ),
        IPRecord(
            id="IP-002",
            title="Clinical Data Normalization Engine",
            ip_type=IPType.TRADE_SECRET,
            description=(
                "Trade secret covering the proprietary clinical data normalization "
                "engine including OMOP mapping and FHIR transformation logic."
            ),
            filing_date=None,
            status="ACTIVE",
            registration_number=None,
            jurisdiction="US",
            owner="BrainStorm Health, Inc.",
            expiry_date=None,
            related_contracts=["CTR-001"],
        ),
        IPRecord(
            id="IP-003",
            title="BrainStorm Health Platform Logo and Brand",
            ip_type=IPType.TRADEMARK,
            description="Registered trademark for the BrainStorm Health platform brand.",
            filing_date=one_year_ago - timedelta(days=365),
            status="ACTIVE",
            registration_number="TM-2024-78543",
            jurisdiction="US",
            owner="BrainStorm Health, Inc.",
            expiry_date=now + timedelta(days=365 * 9),
            related_contracts=[],
        ),
        IPRecord(
            id="IP-004",
            title="Screening Dashboard UI/UX",
            ip_type=IPType.COPYRIGHT,
            description=(
                "Copyright for the screening dashboard UI/UX designs, "
                "wireframes, and interaction patterns."
            ),
            filing_date=one_year_ago,
            status="ACTIVE",
            registration_number="CR-2024-11234",
            jurisdiction="US",
            owner="BrainStorm Health, Inc.",
            expiry_date=now + timedelta(days=365 * 70),
            related_contracts=["CTR-001"],
        ),
        IPRecord(
            id="IP-005",
            title="Multi-Modal Eligibility Scoring Invention",
            ip_type=IPType.INVENTION_DISCLOSURE,
            description=(
                "Invention disclosure for a multi-modal approach to patient "
                "eligibility scoring combining NLP, lab values, and imaging data."
            ),
            filing_date=three_months_ago,
            status="UNDER_REVIEW",
            registration_number=None,
            jurisdiction="US",
            owner="BrainStorm Health, Inc.",
            expiry_date=None,
            related_contracts=["CTR-001", "CTR-003"],
        ),
        IPRecord(
            id="IP-006",
            title="Real-World Evidence Integration Framework",
            ip_type=IPType.TRADE_SECRET,
            description=(
                "Proprietary framework for integrating real-world evidence data "
                "into the clinical trial screening pipeline."
            ),
            filing_date=None,
            status="ACTIVE",
            registration_number=None,
            jurisdiction="US",
            owner="BrainStorm Health, Inc.",
            expiry_date=None,
            related_contracts=["CTR-004"],
        ),
    ]

    return contracts, ip_records


class ContractLifecycleService:
    """Manages the full lifecycle of contracts, milestones, obligations, amendments, and IP."""

    def __init__(self) -> None:
        contracts, ip_records = _build_seed_data()
        self._contracts: dict[str, Contract] = {c.id: c for c in contracts}
        self._ip_records: dict[str, IPRecord] = {ip.id: ip for ip in ip_records}
        self._next_contract_id = len(self._contracts) + 1
        self._next_milestone_id = 18  # Continue after MS-017
        self._next_obligation_id = 16  # Continue after OBL-015
        self._next_amendment_id = 2  # Continue after AMD-001
        self._next_ip_id = 7  # Continue after IP-006
        logger.info(
            "ContractLifecycleService initialized with %d contracts, %d IP records",
            len(self._contracts),
            len(self._ip_records),
        )

    # -------------------------------------------------------------------
    # Contract CRUD
    # -------------------------------------------------------------------

    def list_contracts(
        self,
        *,
        contract_type: ContractType | None = None,
        status: ContractStatus | None = None,
        party_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ContractListResponse:
        """List contracts with optional filters."""
        items = list(self._contracts.values())

        if contract_type is not None:
            items = [c for c in items if c.contract_type == contract_type]
        if status is not None:
            items = [c for c in items if c.status == status]
        if party_name is not None:
            party_lower = party_name.lower()
            items = [
                c
                for c in items
                if any(party_lower in p.name.lower() or party_lower in p.organization.lower() for p in c.parties)
            ]

        total = len(items)
        items = items[offset : offset + limit]

        return ContractListResponse(
            items=items, total=total, limit=limit, offset=offset
        )

    def get_contract(self, contract_id: str) -> Contract | None:
        """Get a single contract by ID."""
        return self._contracts.get(contract_id)

    def create_contract(self, req: ContractCreateRequest) -> Contract:
        """Create a new contract in DRAFT status."""
        now = datetime.now(timezone.utc)
        contract_id = f"CTR-{self._next_contract_id:03d}"
        self._next_contract_id += 1

        contract = Contract(
            id=contract_id,
            title=req.title,
            contract_type=req.contract_type,
            status=ContractStatus.DRAFT,
            description=req.description,
            parties=req.parties,
            effective_date=req.effective_date,
            expiry_date=req.expiry_date,
            auto_renew=req.auto_renew,
            renewal_notice_days=req.renewal_notice_days,
            total_value=req.total_value,
            currency=req.currency,
            risk_level=req.risk_level,
            tags=req.tags,
            created_at=now,
            updated_at=now,
        )

        self._contracts[contract.id] = contract
        logger.info("Created contract %s: %s", contract.id, contract.title)
        return contract

    def update_contract(
        self, contract_id: str, req: ContractUpdateRequest
    ) -> Contract | None:
        """Update a contract. Status transitions are validated."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        now = datetime.now(timezone.utc)

        # Validate status transition if requested
        if req.status is not None and req.status != contract.status:
            valid = VALID_TRANSITIONS.get(contract.status, set())
            if req.status not in valid:
                raise ValueError(
                    f"Invalid transition from {contract.status.value} to {req.status.value}. "
                    f"Valid transitions: {[s.value for s in valid]}"
                )

        updates = req.model_dump(exclude_none=True)
        for field, value in updates.items():
            setattr(contract, field, value)

        # Auto-set signed_date when transitioning to ACTIVE
        if req.status == ContractStatus.ACTIVE and contract.signed_date is None:
            contract.signed_date = now

        # Auto-set terminated_date
        if req.status == ContractStatus.TERMINATED:
            contract.terminated_date = now

        contract.updated_at = now
        return contract

    def delete_contract(self, contract_id: str) -> bool:
        """Delete a contract. Only DRAFT contracts can be deleted."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return False
        if contract.status != ContractStatus.DRAFT:
            raise ValueError("Only DRAFT contracts can be deleted")
        del self._contracts[contract_id]
        return True

    def transition_status(
        self, contract_id: str, new_status: ContractStatus
    ) -> Contract | None:
        """Transition a contract to a new status with validation."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        valid = VALID_TRANSITIONS.get(contract.status, set())
        if new_status not in valid:
            raise ValueError(
                f"Invalid transition from {contract.status.value} to {new_status.value}. "
                f"Valid transitions: {[s.value for s in valid]}"
            )

        now = datetime.now(timezone.utc)
        contract.status = new_status
        contract.updated_at = now

        if new_status == ContractStatus.ACTIVE and contract.signed_date is None:
            contract.signed_date = now
        if new_status == ContractStatus.TERMINATED:
            contract.terminated_date = now

        return contract

    # -------------------------------------------------------------------
    # Milestones
    # -------------------------------------------------------------------

    def create_milestone(
        self, contract_id: str, req: MilestoneCreateRequest
    ) -> ContractMilestone | None:
        """Add a milestone to a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        milestone_id = f"MS-{self._next_milestone_id:03d}"
        self._next_milestone_id += 1

        milestone = ContractMilestone(
            id=milestone_id,
            contract_id=contract_id,
            title=req.title,
            description=req.description,
            due_date=req.due_date,
            responsible_party=req.responsible_party,
            deliverable=req.deliverable,
        )

        contract.milestones.append(milestone)
        contract.updated_at = datetime.now(timezone.utc)
        return milestone

    def update_milestone_status(
        self, contract_id: str, milestone_id: str, status: MilestoneStatus
    ) -> ContractMilestone | None:
        """Update a milestone's status."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        for ms in contract.milestones:
            if ms.id == milestone_id:
                ms.status = status
                if status == MilestoneStatus.COMPLETED:
                    ms.completion_date = datetime.now(timezone.utc)
                contract.updated_at = datetime.now(timezone.utc)
                return ms

        return None

    def get_milestone(
        self, contract_id: str, milestone_id: str
    ) -> ContractMilestone | None:
        """Get a specific milestone from a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        for ms in contract.milestones:
            if ms.id == milestone_id:
                return ms
        return None

    def list_milestones(self, contract_id: str) -> list[ContractMilestone]:
        """List all milestones for a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return []
        return list(contract.milestones)

    # -------------------------------------------------------------------
    # Obligations
    # -------------------------------------------------------------------

    def create_obligation(
        self, contract_id: str, req: ObligationCreateRequest
    ) -> ContractObligation | None:
        """Add an obligation to a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        obligation_id = f"OBL-{self._next_obligation_id:03d}"
        self._next_obligation_id += 1

        obligation = ContractObligation(
            id=obligation_id,
            contract_id=contract_id,
            obligation_type=req.obligation_type,
            description=req.description,
            owner=req.owner,
            due_date=req.due_date,
            recurring=req.recurring,
            frequency_days=req.frequency_days,
        )

        contract.obligations.append(obligation)
        contract.updated_at = datetime.now(timezone.utc)
        return obligation

    def complete_obligation(
        self, contract_id: str, obligation_id: str
    ) -> ContractObligation | None:
        """Mark an obligation as completed."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        for obl in contract.obligations:
            if obl.id == obligation_id:
                now = datetime.now(timezone.utc)
                obl.status = MilestoneStatus.COMPLETED
                obl.last_completed = now
                contract.updated_at = now
                return obl

        return None

    def get_obligation(
        self, contract_id: str, obligation_id: str
    ) -> ContractObligation | None:
        """Get a specific obligation from a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        for obl in contract.obligations:
            if obl.id == obligation_id:
                return obl
        return None

    def list_obligations(self, contract_id: str) -> list[ContractObligation]:
        """List all obligations for a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return []
        return list(contract.obligations)

    def get_overdue_obligations(self) -> list[ContractObligation]:
        """Get all overdue obligations across all contracts."""
        now = datetime.now(timezone.utc)
        overdue: list[ContractObligation] = []
        for contract in self._contracts.values():
            if contract.status in (ContractStatus.TERMINATED, ContractStatus.EXPIRED):
                continue
            for obl in contract.obligations:
                if (
                    obl.status in (MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS, MilestoneStatus.OVERDUE)
                    and obl.due_date < now
                ):
                    obl.status = MilestoneStatus.OVERDUE
                    overdue.append(obl)
        return overdue

    # -------------------------------------------------------------------
    # Amendments
    # -------------------------------------------------------------------

    def create_amendment(
        self, contract_id: str, req: AmendmentCreateRequest
    ) -> ContractAmendment | None:
        """Add an amendment to a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        amendment_id = f"AMD-{self._next_amendment_id:03d}"
        self._next_amendment_id += 1
        now = datetime.now(timezone.utc)

        amendment = ContractAmendment(
            id=amendment_id,
            contract_id=contract_id,
            title=req.title,
            description=req.description,
            changes_summary=req.changes_summary,
            effective_date=req.effective_date,
            approved_by=req.approved_by,
            created_at=now,
        )

        contract.amendments.append(amendment)
        contract.updated_at = now
        return amendment

    def list_amendments(self, contract_id: str) -> list[ContractAmendment]:
        """List all amendments for a contract."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return []
        return list(contract.amendments)

    # -------------------------------------------------------------------
    # IP Records
    # -------------------------------------------------------------------

    def list_ip_records(self) -> IPRecordListResponse:
        """List all IP records."""
        items = list(self._ip_records.values())
        return IPRecordListResponse(items=items, total=len(items))

    def get_ip_record(self, ip_id: str) -> IPRecord | None:
        """Get a single IP record by ID."""
        return self._ip_records.get(ip_id)

    def create_ip_record(self, req: IPRecordCreateRequest) -> IPRecord:
        """Create a new IP record."""
        ip_id = f"IP-{self._next_ip_id:03d}"
        self._next_ip_id += 1

        ip_record = IPRecord(
            id=ip_id,
            title=req.title,
            ip_type=req.ip_type,
            description=req.description,
            filing_date=req.filing_date,
            status=req.status,
            registration_number=req.registration_number,
            jurisdiction=req.jurisdiction,
            owner=req.owner,
            expiry_date=req.expiry_date,
            related_contracts=req.related_contracts,
        )

        self._ip_records[ip_record.id] = ip_record
        logger.info("Created IP record %s: %s", ip_record.id, ip_record.title)
        return ip_record

    def link_ip_to_contract(
        self, ip_id: str, contract_id: str
    ) -> IPRecord | None:
        """Link an IP record to a contract."""
        ip_record = self._ip_records.get(ip_id)
        if ip_record is None:
            return None

        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        if contract_id not in ip_record.related_contracts:
            ip_record.related_contracts.append(contract_id)
        if ip_id not in contract.ip_records:
            contract.ip_records.append(ip_id)

        return ip_record

    # -------------------------------------------------------------------
    # Metrics & Compliance
    # -------------------------------------------------------------------

    def get_metrics(self) -> ContractMetrics:
        """Calculate portfolio-level contract metrics."""
        now = datetime.now(timezone.utc)
        ninety_days = now + timedelta(days=90)

        contracts = list(self._contracts.values())

        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        total_value = 0.0
        expiring_soon = 0
        overdue_milestones = 0
        overdue_obligations = 0

        for c in contracts:
            by_status[c.status.value] = by_status.get(c.status.value, 0) + 1
            by_type[c.contract_type.value] = by_type.get(c.contract_type.value, 0) + 1

            if c.total_value:
                total_value += c.total_value

            if (
                c.expiry_date
                and c.expiry_date <= ninety_days
                and c.status == ContractStatus.ACTIVE
            ):
                expiring_soon += 1

            for ms in c.milestones:
                if ms.status == MilestoneStatus.OVERDUE or (
                    ms.status in (MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS)
                    and ms.due_date < now
                ):
                    overdue_milestones += 1

            for obl in c.obligations:
                if obl.status == MilestoneStatus.OVERDUE or (
                    obl.status in (MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS)
                    and obl.due_date < now
                ):
                    overdue_obligations += 1

        active_ip = sum(1 for ip in self._ip_records.values() if ip.status == "ACTIVE")

        return ContractMetrics(
            total_contracts=len(contracts),
            by_status=by_status,
            by_type=by_type,
            total_value=total_value,
            expiring_soon=expiring_soon,
            overdue_milestones=overdue_milestones,
            overdue_obligations=overdue_obligations,
            active_ip_records=active_ip,
        )

    def get_compliance_report(self) -> ContractComplianceReport:
        """Generate a compliance report."""
        now = datetime.now(timezone.utc)
        ninety_days = now + timedelta(days=90)

        overdue_obligation_contracts: list[str] = []
        unsigned_past_due: list[str] = []
        approaching_expiry: list[str] = []
        auto_renewal_pending: list[str] = []

        for c in self._contracts.values():
            # Contracts with overdue obligations
            has_overdue = False
            for obl in c.obligations:
                if obl.status == MilestoneStatus.OVERDUE or (
                    obl.status in (MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS)
                    and obl.due_date < now
                ):
                    has_overdue = True
                    break
            if has_overdue:
                overdue_obligation_contracts.append(c.id)

            # Unsigned past effective date
            if (
                c.signed_date is None
                and c.effective_date is not None
                and c.effective_date < now
                and c.status not in (ContractStatus.EXPIRED, ContractStatus.TERMINATED)
            ):
                unsigned_past_due.append(c.id)

            # Approaching expiry
            if (
                c.expiry_date is not None
                and c.expiry_date <= ninety_days
                and c.status == ContractStatus.ACTIVE
            ):
                approaching_expiry.append(c.id)

            # Auto-renewal pending
            if (
                c.auto_renew
                and c.expiry_date is not None
                and c.status == ContractStatus.ACTIVE
            ):
                notice_date = c.expiry_date - timedelta(days=c.renewal_notice_days)
                if notice_date <= now:
                    auto_renewal_pending.append(c.id)

        total_issues = (
            len(overdue_obligation_contracts)
            + len(unsigned_past_due)
            + len(approaching_expiry)
            + len(auto_renewal_pending)
        )

        return ContractComplianceReport(
            contracts_with_overdue_obligations=overdue_obligation_contracts,
            unsigned_past_due=unsigned_past_due,
            approaching_expiry=approaching_expiry,
            auto_renewal_pending=auto_renewal_pending,
            total_issues=total_issues,
            generated_at=now,
        )

    def get_auto_renewal_contracts(self) -> list[Contract]:
        """Get contracts with auto_renew=True approaching expiry within renewal_notice_days."""
        now = datetime.now(timezone.utc)
        result: list[Contract] = []

        for c in self._contracts.values():
            if (
                c.auto_renew
                and c.expiry_date is not None
                and c.status == ContractStatus.ACTIVE
            ):
                notice_date = c.expiry_date - timedelta(days=c.renewal_notice_days)
                if notice_date <= now:
                    result.append(c)

        return result

    def get_stats(self) -> dict:
        """Return service stats for health checks."""
        return {
            "total_contracts": len(self._contracts),
            "total_ip_records": len(self._ip_records),
        }


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_contract_lifecycle_service() -> ContractLifecycleService:
    """Get or create the singleton ContractLifecycleService."""
    global _contract_service_instance
    if _contract_service_instance is None:
        with _contract_service_lock:
            if _contract_service_instance is None:
                _contract_service_instance = ContractLifecycleService()
    return _contract_service_instance


def reset_contract_lifecycle_service() -> ContractLifecycleService:
    """Reset the singleton (for testing). Returns the new instance."""
    global _contract_service_instance
    with _contract_service_lock:
        _contract_service_instance = ContractLifecycleService()
    return _contract_service_instance
