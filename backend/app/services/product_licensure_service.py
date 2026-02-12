"""Product Licensure & Market Authorization Service.

Manages regulatory application lifecycles (IND/NDA/BLA/MAA), country-by-country
approval status, product label management, post-approval changes, and market
access timelines for pharmaceutical products.

Usage:
    from app.services.product_licensure_service import (
        get_product_licensure_service,
    )

    svc = get_product_licensure_service()
    apps = svc.list_applications()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.product_licensure import (
    ApplicationApproval,
    ApplicationStatus,
    ApplicationSubmit,
    ApplicationType,
    ChangeType,
    CountryAuthorization,
    CountryAuthorizationCreate,
    CountryAuthorizationUpdate,
    LabelStatus,
    LicensureMetrics,
    MarketAccessTimeline,
    MarketAccessTimelineCreate,
    MarketAccessTimelineUpdate,
    MarketStatus,
    MilestoneStatus,
    PostApprovalChange,
    PostApprovalChangeCreate,
    PostApprovalChangeUpdate,
    ProductCountryStatus,
    ProductCountryStatusListResponse,
    ProductLabel,
    ProductLabelCreate,
    ProductLabelUpdate,
    RegulatoryApplication,
    RegulatoryApplicationCreate,
    RegulatoryApplicationUpdate,
    SubmissionType,
)

logger = logging.getLogger(__name__)


class ProductLicensureService:
    """In-memory Product Licensure & Market Authorization engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._applications: dict[str, RegulatoryApplication] = {}
        self._country_authorizations: dict[str, CountryAuthorization] = {}
        self._labels: dict[str, ProductLabel] = {}
        self._post_approval_changes: dict[str, PostApprovalChange] = {}
        self._timelines: dict[str, MarketAccessTimeline] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901 - seed method is intentionally large
        """Pre-populate realistic Regeneron product licensure data."""
        now = datetime.now(timezone.utc)

        # --- 4 Regulatory Applications ---
        apps_data = [
            {
                "id": "APP-001",
                "product_name": "Dupixent (dupilumab)",
                "application_type": ApplicationType.BLA,
                "application_number": "BLA-761055",
                "regulatory_authority": "FDA",
                "country": "US",
                "submission_date": now - timedelta(days=730),
                "acceptance_date": now - timedelta(days=710),
                "review_type": "priority",
                "pdufa_date": now - timedelta(days=365),
                "status": ApplicationStatus.APPROVED,
                "assigned_reviewer": "Dr. Sarah Chen",
                "division": "Division of Pulmonary, Allergy, and Rheumatology Products",
                "therapeutic_area": "Dermatology / Immunology",
                "indication": "Moderate-to-severe atopic dermatitis in adults",
                "sponsor_contact": "Dr. George Yancopoulos",
                "submission_type": SubmissionType.ORIGINAL,
                "created_at": now - timedelta(days=740),
                "updated_at": now - timedelta(days=30),
            },
            {
                "id": "APP-002",
                "product_name": "Eylea (aflibercept)",
                "application_type": ApplicationType.NDA,
                "application_number": "NDA-125387",
                "regulatory_authority": "FDA",
                "country": "US",
                "submission_date": now - timedelta(days=200),
                "acceptance_date": now - timedelta(days=180),
                "review_type": "standard",
                "pdufa_date": now + timedelta(days=120),
                "status": ApplicationStatus.UNDER_REVIEW,
                "assigned_reviewer": "Dr. Michael Torres",
                "division": "Division of Transplant and Ophthalmology Products",
                "therapeutic_area": "Ophthalmology",
                "indication": "Neovascular (wet) age-related macular degeneration",
                "sponsor_contact": "Dr. Robert Shapiro",
                "submission_type": SubmissionType.SUPPLEMENT,
                "created_at": now - timedelta(days=210),
                "updated_at": now - timedelta(days=10),
            },
            {
                "id": "APP-003",
                "product_name": "Libtayo (cemiplimab)",
                "application_type": ApplicationType.IND,
                "application_number": "IND-145892",
                "regulatory_authority": "FDA",
                "country": "US",
                "submission_date": now - timedelta(days=90),
                "acceptance_date": now - timedelta(days=60),
                "review_type": "breakthrough",
                "pdufa_date": None,
                "status": ApplicationStatus.SUBMITTED,
                "assigned_reviewer": None,
                "division": "Division of Oncology Products",
                "therapeutic_area": "Oncology",
                "indication": "Advanced non-small cell lung cancer with PD-L1 expression",
                "sponsor_contact": "Dr. Israel Lowy",
                "submission_type": SubmissionType.ORIGINAL,
                "created_at": now - timedelta(days=100),
                "updated_at": now - timedelta(days=60),
            },
            {
                "id": "APP-004",
                "product_name": "Dupixent (dupilumab)",
                "application_type": ApplicationType.MAA,
                "application_number": "EMEA/H/C/004390",
                "regulatory_authority": "EMA",
                "country": "EU",
                "submission_date": now - timedelta(days=600),
                "acceptance_date": now - timedelta(days=580),
                "review_type": "accelerated",
                "pdufa_date": None,
                "status": ApplicationStatus.APPROVED,
                "assigned_reviewer": "Dr. Anna Lindqvist",
                "division": "Committee for Medicinal Products for Human Use (CHMP)",
                "therapeutic_area": "Dermatology / Immunology",
                "indication": "Moderate-to-severe atopic dermatitis in adults and adolescents",
                "sponsor_contact": "Dr. George Yancopoulos",
                "submission_type": SubmissionType.ORIGINAL,
                "created_at": now - timedelta(days=620),
                "updated_at": now - timedelta(days=60),
            },
            {
                "id": "APP-005",
                "product_name": "Kevzara (sarilumab)",
                "application_type": ApplicationType.NDA,
                "application_number": "NDA-761037",
                "regulatory_authority": "FDA",
                "country": "US",
                "submission_date": now - timedelta(days=50),
                "acceptance_date": None,
                "review_type": "standard",
                "pdufa_date": None,
                "status": ApplicationStatus.PRE_SUBMISSION,
                "assigned_reviewer": None,
                "division": "Division of Rheumatology Products",
                "therapeutic_area": "Rheumatology",
                "indication": "Rheumatoid arthritis inadequately responding to DMARDs",
                "sponsor_contact": "Dr. Allen Rowe",
                "submission_type": SubmissionType.SUPPLEMENT,
                "created_at": now - timedelta(days=55),
                "updated_at": now - timedelta(days=50),
            },
        ]

        for a in apps_data:
            self._applications[a["id"]] = RegulatoryApplication(**a)

        # --- 8+ Country Authorizations ---
        ca_data = [
            {
                "id": "CA-001",
                "application_id": "APP-001",
                "country": "US",
                "authority_name": "FDA",
                "local_application_number": "BLA-761055",
                "filing_date": now - timedelta(days=730),
                "approval_date": now - timedelta(days=365),
                "market_status": MarketStatus.LAUNCHED,
                "conditions": None,
                "label_approved": True,
                "launch_date": now - timedelta(days=350),
                "patent_expiry": now + timedelta(days=2555),
                "created_at": now - timedelta(days=730),
            },
            {
                "id": "CA-002",
                "application_id": "APP-004",
                "country": "DE",
                "authority_name": "BfArM (Federal Institute for Drugs and Medical Devices)",
                "local_application_number": "EU/1/17/1229/001",
                "filing_date": now - timedelta(days=600),
                "approval_date": now - timedelta(days=300),
                "market_status": MarketStatus.LAUNCHED,
                "conditions": None,
                "label_approved": True,
                "launch_date": now - timedelta(days=270),
                "patent_expiry": now + timedelta(days=2190),
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "CA-003",
                "application_id": "APP-004",
                "country": "FR",
                "authority_name": "ANSM (Agence nationale de securite du medicament)",
                "local_application_number": "EU/1/17/1229/002",
                "filing_date": now - timedelta(days=600),
                "approval_date": now - timedelta(days=280),
                "market_status": MarketStatus.LAUNCHED,
                "conditions": None,
                "label_approved": True,
                "launch_date": now - timedelta(days=240),
                "patent_expiry": now + timedelta(days=2190),
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "CA-004",
                "application_id": "APP-004",
                "country": "GB",
                "authority_name": "MHRA (Medicines and Healthcare products Regulatory Agency)",
                "local_application_number": "PL 00000/0001",
                "filing_date": now - timedelta(days=500),
                "approval_date": now - timedelta(days=200),
                "market_status": MarketStatus.APPROVED,
                "conditions": "Post-authorization safety study required within 12 months",
                "label_approved": True,
                "launch_date": None,
                "patent_expiry": now + timedelta(days=2190),
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "CA-005",
                "application_id": "APP-004",
                "country": "JP",
                "authority_name": "PMDA (Pharmaceuticals and Medical Devices Agency)",
                "local_application_number": None,
                "filing_date": now - timedelta(days=400),
                "approval_date": None,
                "market_status": MarketStatus.UNDER_REVIEW,
                "conditions": None,
                "label_approved": False,
                "launch_date": None,
                "patent_expiry": now + timedelta(days=2555),
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "CA-006",
                "application_id": "APP-002",
                "country": "US",
                "authority_name": "FDA",
                "local_application_number": "NDA-125387-S001",
                "filing_date": now - timedelta(days=200),
                "approval_date": None,
                "market_status": MarketStatus.UNDER_REVIEW,
                "conditions": None,
                "label_approved": False,
                "launch_date": None,
                "patent_expiry": now + timedelta(days=1825),
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "CA-007",
                "application_id": "APP-001",
                "country": "CA",
                "authority_name": "Health Canada",
                "local_application_number": "HC-DIN-02468123",
                "filing_date": now - timedelta(days=650),
                "approval_date": now - timedelta(days=320),
                "market_status": MarketStatus.LAUNCHED,
                "conditions": None,
                "label_approved": True,
                "launch_date": now - timedelta(days=300),
                "patent_expiry": now + timedelta(days=2555),
                "created_at": now - timedelta(days=650),
            },
            {
                "id": "CA-008",
                "application_id": "APP-004",
                "country": "AU",
                "authority_name": "TGA (Therapeutic Goods Administration)",
                "local_application_number": None,
                "filing_date": now - timedelta(days=180),
                "approval_date": None,
                "market_status": MarketStatus.FILED,
                "conditions": None,
                "label_approved": False,
                "launch_date": None,
                "patent_expiry": now + timedelta(days=2190),
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "CA-009",
                "application_id": "APP-004",
                "country": "BR",
                "authority_name": "ANVISA",
                "local_application_number": None,
                "filing_date": None,
                "approval_date": None,
                "market_status": MarketStatus.NOT_FILED,
                "conditions": None,
                "label_approved": False,
                "launch_date": None,
                "patent_expiry": now + timedelta(days=2190),
                "created_at": now - timedelta(days=100),
            },
        ]

        for c in ca_data:
            self._country_authorizations[c["id"]] = CountryAuthorization(**c)

        # --- 3+ Product Labels ---
        labels_data = [
            {
                "id": "LBL-001",
                "application_id": "APP-001",
                "product_name": "Dupixent (dupilumab)",
                "version": "3.0",
                "country": "US",
                "language": "en",
                "status": LabelStatus.EFFECTIVE,
                "effective_date": now - timedelta(days=120),
                "sections_changed": ["Indications and Usage", "Dosage and Administration", "Warnings and Precautions"],
                "safety_updates": ["Updated hypersensitivity reaction warnings", "New drug interaction data"],
                "boxed_warning": None,
                "contraindications": ["Known hypersensitivity to dupilumab or any excipients"],
                "approved_by": "Dr. Sarah Chen",
                "approved_date": now - timedelta(days=130),
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "LBL-002",
                "application_id": "APP-001",
                "product_name": "Dupixent (dupilumab)",
                "version": "2.0",
                "country": "US",
                "language": "en",
                "status": LabelStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=400),
                "sections_changed": ["Indications and Usage", "Clinical Studies"],
                "safety_updates": [],
                "boxed_warning": None,
                "contraindications": ["Known hypersensitivity to dupilumab or any excipients"],
                "approved_by": "Dr. Sarah Chen",
                "approved_date": now - timedelta(days=410),
                "created_at": now - timedelta(days=420),
            },
            {
                "id": "LBL-003",
                "application_id": "APP-004",
                "product_name": "Dupixent (dupilumab)",
                "version": "2.1",
                "country": "DE",
                "language": "de",
                "status": LabelStatus.EFFECTIVE,
                "effective_date": now - timedelta(days=100),
                "sections_changed": ["Section 4.1 Therapeutic Indications", "Section 4.8 Undesirable Effects"],
                "safety_updates": ["Updated adverse event frequencies based on post-marketing data"],
                "boxed_warning": None,
                "contraindications": ["Hypersensitivity to the active substance or excipients"],
                "approved_by": "Dr. Anna Lindqvist",
                "approved_date": now - timedelta(days=110),
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "LBL-004",
                "application_id": "APP-002",
                "product_name": "Eylea (aflibercept)",
                "version": "1.0",
                "country": "US",
                "language": "en",
                "status": LabelStatus.DRAFT,
                "effective_date": None,
                "sections_changed": [],
                "safety_updates": [],
                "boxed_warning": None,
                "contraindications": [
                    "Ocular or periocular infections",
                    "Active intraocular inflammation",
                    "Known hypersensitivity to aflibercept",
                ],
                "approved_by": None,
                "approved_date": None,
                "created_at": now - timedelta(days=60),
            },
        ]

        for l in labels_data:
            self._labels[l["id"]] = ProductLabel(**l)

        # --- 2+ Post-Approval Changes ---
        pac_data = [
            {
                "id": "PAC-001",
                "application_id": "APP-001",
                "change_type": ChangeType.LABELING,
                "description": "Update Warnings and Precautions section to include new post-marketing hypersensitivity data from 3-year safety study",
                "submission_date": now - timedelta(days=180),
                "approval_date": now - timedelta(days=130),
                "status": ApplicationStatus.APPROVED,
                "impact_assessment": "Low impact on prescribing behavior; enhanced safety information for healthcare providers",
                "affected_countries": ["US", "CA"],
                "regulatory_reference": "CBE-30 Supplement",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "PAC-002",
                "application_id": "APP-001",
                "change_type": ChangeType.MANUFACTURING,
                "description": "Addition of new manufacturing facility in Limerick, Ireland for active substance production",
                "submission_date": now - timedelta(days=90),
                "approval_date": None,
                "status": ApplicationStatus.UNDER_REVIEW,
                "impact_assessment": "No change to product quality; facility validated per cGMP requirements",
                "affected_countries": ["US", "EU", "GB", "CA", "JP"],
                "regulatory_reference": "Prior Approval Supplement (PAS)",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "PAC-003",
                "application_id": "APP-004",
                "change_type": ChangeType.INDICATION,
                "description": "Extension of indication to include pediatric patients aged 6-11 with severe atopic dermatitis",
                "submission_date": now - timedelta(days=150),
                "approval_date": None,
                "status": ApplicationStatus.UNDER_REVIEW,
                "impact_assessment": "Significant positive impact; addresses unmet need in pediatric population",
                "affected_countries": ["DE", "FR", "GB"],
                "regulatory_reference": "Type II Variation C.I.6(a)",
                "created_at": now - timedelta(days=160),
            },
        ]

        for p in pac_data:
            self._post_approval_changes[p["id"]] = PostApprovalChange(**p)

        # --- 6+ Timeline Milestones ---
        tl_data = [
            {
                "id": "TL-001",
                "application_id": "APP-002",
                "country": "US",
                "milestone_name": "Pre-NDA Meeting with FDA",
                "planned_date": now - timedelta(days=250),
                "actual_date": now - timedelta(days=248),
                "status": MilestoneStatus.COMPLETED,
                "dependencies": [],
                "notes": "Successful Type A pre-submission meeting. FDA agreed on review strategy.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "TL-002",
                "application_id": "APP-002",
                "country": "US",
                "milestone_name": "NDA Submission",
                "planned_date": now - timedelta(days=210),
                "actual_date": now - timedelta(days=200),
                "status": MilestoneStatus.COMPLETED,
                "dependencies": ["TL-001"],
                "notes": "Complete submission package accepted by FDA.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "TL-003",
                "application_id": "APP-002",
                "country": "US",
                "milestone_name": "FDA Filing Acceptance",
                "planned_date": now - timedelta(days=170),
                "actual_date": now - timedelta(days=180),
                "status": MilestoneStatus.COMPLETED,
                "dependencies": ["TL-002"],
                "notes": "74-day filing review completed. Application accepted for substantive review.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "TL-004",
                "application_id": "APP-002",
                "country": "US",
                "milestone_name": "Mid-Cycle Review Meeting",
                "planned_date": now - timedelta(days=30),
                "actual_date": now - timedelta(days=28),
                "status": MilestoneStatus.COMPLETED,
                "dependencies": ["TL-003"],
                "notes": "No major issues identified. On track for PDUFA date.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "TL-005",
                "application_id": "APP-002",
                "country": "US",
                "milestone_name": "Advisory Committee Meeting",
                "planned_date": now + timedelta(days=60),
                "actual_date": None,
                "status": MilestoneStatus.IN_PROGRESS,
                "dependencies": ["TL-004"],
                "notes": "Advisory committee date confirmed. Briefing documents in preparation.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "TL-006",
                "application_id": "APP-002",
                "country": "US",
                "milestone_name": "PDUFA Target Action Date",
                "planned_date": now + timedelta(days=120),
                "actual_date": None,
                "status": MilestoneStatus.NOT_STARTED,
                "dependencies": ["TL-005"],
                "notes": "PDUFA date set. Preparing for potential launch.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "TL-007",
                "application_id": "APP-004",
                "country": "JP",
                "milestone_name": "PMDA Pre-Application Consultation",
                "planned_date": now - timedelta(days=420),
                "actual_date": now - timedelta(days=418),
                "status": MilestoneStatus.COMPLETED,
                "dependencies": [],
                "notes": "Consultation meeting with PMDA completed. Agreed on Japan-specific bridging study.",
                "created_at": now - timedelta(days=450),
            },
            {
                "id": "TL-008",
                "application_id": "APP-004",
                "country": "JP",
                "milestone_name": "JNDA Submission",
                "planned_date": now - timedelta(days=380),
                "actual_date": now - timedelta(days=400),
                "status": MilestoneStatus.COMPLETED,
                "dependencies": ["TL-007"],
                "notes": "JNDA submitted to PMDA with bridging study data.",
                "created_at": now - timedelta(days=430),
            },
            {
                "id": "TL-009",
                "application_id": "APP-004",
                "country": "JP",
                "milestone_name": "PMDA Review Decision",
                "planned_date": now + timedelta(days=30),
                "actual_date": None,
                "status": MilestoneStatus.DELAYED,
                "dependencies": ["TL-008"],
                "notes": "Additional queries from PMDA regarding pediatric data. Timeline extended by 60 days.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "TL-010",
                "application_id": "APP-002",
                "country": "US",
                "milestone_name": "Commercial Launch Readiness",
                "planned_date": now + timedelta(days=150),
                "actual_date": None,
                "status": MilestoneStatus.AT_RISK,
                "dependencies": ["TL-006"],
                "notes": "Supply chain readiness dependent on PDUFA outcome. Contingency plans active.",
                "created_at": now - timedelta(days=180),
            },
        ]

        for t in tl_data:
            self._timelines[t["id"]] = MarketAccessTimeline(**t)

    # ------------------------------------------------------------------
    # Regulatory Applications
    # ------------------------------------------------------------------

    def list_applications(
        self,
        *,
        application_type: ApplicationType | None = None,
        status: ApplicationStatus | None = None,
        product_name: str | None = None,
        country: str | None = None,
    ) -> list[RegulatoryApplication]:
        """List regulatory applications with optional filters."""
        with self._lock:
            result = list(self._applications.values())

        if application_type is not None:
            result = [a for a in result if a.application_type == application_type]
        if status is not None:
            result = [a for a in result if a.status == status]
        if product_name is not None:
            result = [a for a in result if product_name.lower() in a.product_name.lower()]
        if country is not None:
            result = [a for a in result if a.country == country]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_application(self, app_id: str) -> RegulatoryApplication | None:
        """Get a single application by ID."""
        with self._lock:
            return self._applications.get(app_id)

    def create_application(self, payload: RegulatoryApplicationCreate) -> RegulatoryApplication:
        """Create a new regulatory application."""
        now = datetime.now(timezone.utc)
        app_id = f"APP-{uuid4().hex[:8].upper()}"
        application = RegulatoryApplication(
            id=app_id,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._applications[app_id] = application
        logger.info("Created regulatory application %s: %s", app_id, payload.product_name)
        return application

    def update_application(
        self, app_id: str, payload: RegulatoryApplicationUpdate
    ) -> RegulatoryApplication | None:
        """Update an existing regulatory application."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._applications.get(app_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = RegulatoryApplication(**data)
            self._applications[app_id] = updated
        return updated

    def delete_application(self, app_id: str) -> bool:
        """Delete an application. Returns True if deleted."""
        with self._lock:
            if app_id in self._applications:
                del self._applications[app_id]
                return True
            return False

    def submit_application(
        self, app_id: str, payload: ApplicationSubmit
    ) -> RegulatoryApplication | None:
        """Formally submit a regulatory application."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._applications.get(app_id)
            if existing is None:
                return None

            if existing.status not in (
                ApplicationStatus.PRE_SUBMISSION,
                ApplicationStatus.COMPLETE_RESPONSE,
            ):
                raise ValueError(
                    f"Application '{app_id}' cannot be submitted from status '{existing.status.value}'"
                )

            data = existing.model_dump()
            data["submission_date"] = payload.submission_date
            data["status"] = ApplicationStatus.SUBMITTED
            data["updated_at"] = now
            updated = RegulatoryApplication(**data)
            self._applications[app_id] = updated
        logger.info("Submitted application %s", app_id)
        return updated

    def record_approval(
        self, app_id: str, payload: ApplicationApproval
    ) -> RegulatoryApplication | None:
        """Record approval of a regulatory application."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._applications.get(app_id)
            if existing is None:
                return None

            if existing.status not in (
                ApplicationStatus.SUBMITTED,
                ApplicationStatus.UNDER_REVIEW,
            ):
                raise ValueError(
                    f"Application '{app_id}' cannot be approved from status '{existing.status.value}'"
                )

            data = existing.model_dump()
            data["status"] = ApplicationStatus.APPROVED
            data["updated_at"] = now
            if payload.assigned_reviewer:
                data["assigned_reviewer"] = payload.assigned_reviewer
            updated = RegulatoryApplication(**data)
            self._applications[app_id] = updated
        logger.info("Approved application %s", app_id)
        return updated

    # ------------------------------------------------------------------
    # Country Authorizations
    # ------------------------------------------------------------------

    def list_country_authorizations(
        self,
        *,
        application_id: str | None = None,
        country: str | None = None,
        market_status: MarketStatus | None = None,
    ) -> list[CountryAuthorization]:
        """List country authorizations with optional filters."""
        with self._lock:
            result = list(self._country_authorizations.values())

        if application_id is not None:
            result = [c for c in result if c.application_id == application_id]
        if country is not None:
            result = [c for c in result if c.country == country]
        if market_status is not None:
            result = [c for c in result if c.market_status == market_status]

        return sorted(result, key=lambda c: c.id)

    def get_country_authorization(self, ca_id: str) -> CountryAuthorization | None:
        """Get a single country authorization by ID."""
        with self._lock:
            return self._country_authorizations.get(ca_id)

    def create_country_authorization(
        self, payload: CountryAuthorizationCreate
    ) -> CountryAuthorization:
        """Create a new country authorization."""
        now = datetime.now(timezone.utc)
        ca_id = f"CA-{uuid4().hex[:8].upper()}"

        # Verify parent application exists
        with self._lock:
            if payload.application_id not in self._applications:
                raise ValueError(f"Application '{payload.application_id}' not found")

        ca = CountryAuthorization(
            id=ca_id,
            application_id=payload.application_id,
            country=payload.country,
            authority_name=payload.authority_name,
            local_application_number=payload.local_application_number,
            filing_date=None,
            approval_date=None,
            market_status=MarketStatus.NOT_FILED,
            conditions=None,
            label_approved=False,
            launch_date=None,
            patent_expiry=payload.patent_expiry,
            created_at=now,
        )
        with self._lock:
            self._country_authorizations[ca_id] = ca
        logger.info(
            "Created country authorization %s for %s in %s",
            ca_id, payload.application_id, payload.country,
        )
        return ca

    def update_country_authorization(
        self, ca_id: str, payload: CountryAuthorizationUpdate
    ) -> CountryAuthorization | None:
        """Update a country authorization."""
        with self._lock:
            existing = self._country_authorizations.get(ca_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CountryAuthorization(**data)
            self._country_authorizations[ca_id] = updated
        return updated

    def delete_country_authorization(self, ca_id: str) -> bool:
        """Delete a country authorization. Returns True if deleted."""
        with self._lock:
            if ca_id in self._country_authorizations:
                del self._country_authorizations[ca_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Product Labels
    # ------------------------------------------------------------------

    def list_labels(
        self,
        *,
        application_id: str | None = None,
        country: str | None = None,
        status: LabelStatus | None = None,
    ) -> list[ProductLabel]:
        """List product labels with optional filters."""
        with self._lock:
            result = list(self._labels.values())

        if application_id is not None:
            result = [l for l in result if l.application_id == application_id]
        if country is not None:
            result = [l for l in result if l.country == country]
        if status is not None:
            result = [l for l in result if l.status == status]

        return sorted(result, key=lambda l: l.id)

    def get_label(self, label_id: str) -> ProductLabel | None:
        """Get a single product label by ID."""
        with self._lock:
            return self._labels.get(label_id)

    def create_label(self, payload: ProductLabelCreate) -> ProductLabel:
        """Create a new product label."""
        now = datetime.now(timezone.utc)
        label_id = f"LBL-{uuid4().hex[:8].upper()}"

        with self._lock:
            if payload.application_id not in self._applications:
                raise ValueError(f"Application '{payload.application_id}' not found")

        label = ProductLabel(
            id=label_id,
            application_id=payload.application_id,
            product_name=payload.product_name,
            version=payload.version,
            country=payload.country,
            language=payload.language,
            status=LabelStatus.DRAFT,
            effective_date=None,
            sections_changed=payload.sections_changed,
            safety_updates=payload.safety_updates,
            boxed_warning=payload.boxed_warning,
            contraindications=payload.contraindications,
            approved_by=None,
            approved_date=None,
            created_at=now,
        )
        with self._lock:
            self._labels[label_id] = label
        logger.info("Created product label %s v%s for %s", label_id, payload.version, payload.country)
        return label

    def update_label(self, label_id: str, payload: ProductLabelUpdate) -> ProductLabel | None:
        """Update a product label."""
        with self._lock:
            existing = self._labels.get(label_id)
            if existing is None:
                return None

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set approved_date when status changes to approved
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = LabelStatus(new_status)
                if new_status == LabelStatus.APPROVED and existing.status != LabelStatus.APPROVED:
                    if "approved_date" not in updates:
                        updates["approved_date"] = datetime.now(timezone.utc)

            data.update(updates)
            updated = ProductLabel(**data)
            self._labels[label_id] = updated
        return updated

    def delete_label(self, label_id: str) -> bool:
        """Delete a product label. Returns True if deleted."""
        with self._lock:
            if label_id in self._labels:
                del self._labels[label_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Post-Approval Changes
    # ------------------------------------------------------------------

    def list_post_approval_changes(
        self,
        *,
        application_id: str | None = None,
        change_type: ChangeType | None = None,
        status: ApplicationStatus | None = None,
    ) -> list[PostApprovalChange]:
        """List post-approval changes with optional filters."""
        with self._lock:
            result = list(self._post_approval_changes.values())

        if application_id is not None:
            result = [p for p in result if p.application_id == application_id]
        if change_type is not None:
            result = [p for p in result if p.change_type == change_type]
        if status is not None:
            result = [p for p in result if p.status == status]

        return sorted(result, key=lambda p: p.created_at, reverse=True)

    def get_post_approval_change(self, pac_id: str) -> PostApprovalChange | None:
        """Get a single post-approval change by ID."""
        with self._lock:
            return self._post_approval_changes.get(pac_id)

    def file_post_approval_change(
        self, payload: PostApprovalChangeCreate
    ) -> PostApprovalChange:
        """File a new post-approval change."""
        now = datetime.now(timezone.utc)
        pac_id = f"PAC-{uuid4().hex[:8].upper()}"

        with self._lock:
            if payload.application_id not in self._applications:
                raise ValueError(f"Application '{payload.application_id}' not found")

        pac = PostApprovalChange(
            id=pac_id,
            application_id=payload.application_id,
            change_type=payload.change_type,
            description=payload.description,
            submission_date=None,
            approval_date=None,
            status=ApplicationStatus.PRE_SUBMISSION,
            impact_assessment=payload.impact_assessment,
            affected_countries=payload.affected_countries,
            regulatory_reference=payload.regulatory_reference,
            created_at=now,
        )
        with self._lock:
            self._post_approval_changes[pac_id] = pac
        logger.info("Filed post-approval change %s for %s", pac_id, payload.application_id)
        return pac

    def update_post_approval_change(
        self, pac_id: str, payload: PostApprovalChangeUpdate
    ) -> PostApprovalChange | None:
        """Update a post-approval change."""
        with self._lock:
            existing = self._post_approval_changes.get(pac_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PostApprovalChange(**data)
            self._post_approval_changes[pac_id] = updated
        return updated

    def delete_post_approval_change(self, pac_id: str) -> bool:
        """Delete a post-approval change. Returns True if deleted."""
        with self._lock:
            if pac_id in self._post_approval_changes:
                del self._post_approval_changes[pac_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Market Access Timelines
    # ------------------------------------------------------------------

    def list_timelines(
        self,
        *,
        application_id: str | None = None,
        country: str | None = None,
        status: MilestoneStatus | None = None,
    ) -> list[MarketAccessTimeline]:
        """List timeline milestones with optional filters."""
        with self._lock:
            result = list(self._timelines.values())

        if application_id is not None:
            result = [t for t in result if t.application_id == application_id]
        if country is not None:
            result = [t for t in result if t.country == country]
        if status is not None:
            result = [t for t in result if t.status == status]

        return sorted(result, key=lambda t: t.planned_date)

    def get_timeline(self, tl_id: str) -> MarketAccessTimeline | None:
        """Get a single timeline milestone by ID."""
        with self._lock:
            return self._timelines.get(tl_id)

    def create_timeline(self, payload: MarketAccessTimelineCreate) -> MarketAccessTimeline:
        """Create a new timeline milestone."""
        now = datetime.now(timezone.utc)
        tl_id = f"TL-{uuid4().hex[:8].upper()}"

        with self._lock:
            if payload.application_id not in self._applications:
                raise ValueError(f"Application '{payload.application_id}' not found")

        milestone = MarketAccessTimeline(
            id=tl_id,
            application_id=payload.application_id,
            country=payload.country,
            milestone_name=payload.milestone_name,
            planned_date=payload.planned_date,
            actual_date=None,
            status=MilestoneStatus.NOT_STARTED,
            dependencies=payload.dependencies,
            notes=payload.notes,
            created_at=now,
        )
        with self._lock:
            self._timelines[tl_id] = milestone
        logger.info("Created timeline milestone %s: %s", tl_id, payload.milestone_name)
        return milestone

    def update_timeline(
        self, tl_id: str, payload: MarketAccessTimelineUpdate
    ) -> MarketAccessTimeline | None:
        """Update a timeline milestone."""
        with self._lock:
            existing = self._timelines.get(tl_id)
            if existing is None:
                return None

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set actual_date when status goes to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = MilestoneStatus(new_status)
                if (
                    new_status == MilestoneStatus.COMPLETED
                    and existing.status != MilestoneStatus.COMPLETED
                ):
                    if "actual_date" not in updates:
                        updates["actual_date"] = datetime.now(timezone.utc)

            data.update(updates)
            updated = MarketAccessTimeline(**data)
            self._timelines[tl_id] = updated
        return updated

    def delete_timeline(self, tl_id: str) -> bool:
        """Delete a timeline milestone. Returns True if deleted."""
        with self._lock:
            if tl_id in self._timelines:
                del self._timelines[tl_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Product Status by Country (aggregate)
    # ------------------------------------------------------------------

    def get_product_status_by_country(
        self, app_id: str
    ) -> ProductCountryStatusListResponse | None:
        """Get aggregated product status across all countries for an application."""
        with self._lock:
            application = self._applications.get(app_id)
            if application is None:
                return None

            cas = [
                c for c in self._country_authorizations.values()
                if c.application_id == app_id
            ]
            pacs = [
                p for p in self._post_approval_changes.values()
                if p.application_id == app_id
            ]
            timelines = [
                t for t in self._timelines.values()
                if t.application_id == app_id
            ]

        now = datetime.now(timezone.utc)
        countries: list[ProductCountryStatus] = []

        for ca in cas:
            # Count pending changes affecting this country
            pending = sum(
                1 for p in pacs
                if ca.country in p.affected_countries
                and p.status in (
                    ApplicationStatus.PRE_SUBMISSION,
                    ApplicationStatus.SUBMITTED,
                    ApplicationStatus.UNDER_REVIEW,
                )
            )

            # Find next upcoming milestone for this country
            upcoming = [
                t for t in timelines
                if t.country == ca.country
                and t.actual_date is None
                and t.planned_date > now
            ]
            upcoming.sort(key=lambda t: t.planned_date)

            next_ms_name = upcoming[0].milestone_name if upcoming else None
            next_ms_date = upcoming[0].planned_date if upcoming else None

            countries.append(ProductCountryStatus(
                country=ca.country,
                authority_name=ca.authority_name,
                application_status=application.status,
                market_status=ca.market_status,
                label_approved=ca.label_approved,
                approval_date=ca.approval_date,
                launch_date=ca.launch_date,
                pending_changes=pending,
                next_milestone=next_ms_name,
                next_milestone_date=next_ms_date,
            ))

        return ProductCountryStatusListResponse(
            product_name=application.product_name,
            application_id=app_id,
            countries=countries,
            total=len(countries),
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> LicensureMetrics:
        """Compute aggregated licensure metrics."""
        with self._lock:
            apps = list(self._applications.values())
            cas = list(self._country_authorizations.values())
            labels = list(self._labels.values())
            pacs = list(self._post_approval_changes.values())
            timelines = list(self._timelines.values())

        # Applications by type
        apps_by_type: dict[str, int] = {}
        for a in apps:
            key = a.application_type.value
            apps_by_type[key] = apps_by_type.get(key, 0) + 1

        # Applications by status
        apps_by_status: dict[str, int] = {}
        for a in apps:
            key = a.status.value
            apps_by_status[key] = apps_by_status.get(key, 0) + 1

        # Country authorizations
        countries_approved = sum(
            1 for c in cas if c.market_status in (MarketStatus.APPROVED, MarketStatus.LAUNCHED)
        )
        countries_launched = sum(
            1 for c in cas if c.market_status == MarketStatus.LAUNCHED
        )

        # Labels
        labels_effective = sum(1 for l in labels if l.status == LabelStatus.EFFECTIVE)

        # Post-approval changes
        pending_changes = sum(
            1 for p in pacs
            if p.status in (
                ApplicationStatus.PRE_SUBMISSION,
                ApplicationStatus.SUBMITTED,
                ApplicationStatus.UNDER_REVIEW,
            )
        )

        # Milestones
        milestones_completed = sum(
            1 for t in timelines if t.status == MilestoneStatus.COMPLETED
        )
        milestones_delayed = sum(
            1 for t in timelines if t.status == MilestoneStatus.DELAYED
        )
        milestones_at_risk = sum(
            1 for t in timelines if t.status == MilestoneStatus.AT_RISK
        )

        # Average approval time
        approval_times: list[float] = []
        for a in apps:
            if (
                a.status == ApplicationStatus.APPROVED
                and a.submission_date is not None
            ):
                # Use the earliest country authorization approval date or estimate
                app_cas = [c for c in cas if c.application_id == a.id and c.approval_date]
                if app_cas:
                    earliest = min(c.approval_date for c in app_cas)  # type: ignore[arg-type]
                    delta = (earliest - a.submission_date).days
                    if delta > 0:
                        approval_times.append(float(delta))

        avg_approval_time = (
            round(sum(approval_times) / len(approval_times), 1)
            if approval_times
            else None
        )

        return LicensureMetrics(
            total_applications=len(apps),
            applications_by_type=apps_by_type,
            applications_by_status=apps_by_status,
            total_country_authorizations=len(cas),
            countries_approved=countries_approved,
            countries_launched=countries_launched,
            total_labels=len(labels),
            labels_effective=labels_effective,
            total_post_approval_changes=len(pacs),
            pending_changes=pending_changes,
            total_milestones=len(timelines),
            milestones_completed=milestones_completed,
            milestones_delayed=milestones_delayed,
            milestones_at_risk=milestones_at_risk,
            avg_approval_time_days=avg_approval_time,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProductLicensureService | None = None
_instance_lock = threading.Lock()


def get_product_licensure_service() -> ProductLicensureService:
    """Return the singleton ProductLicensureService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProductLicensureService()
    return _instance


def reset_product_licensure_service() -> ProductLicensureService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ProductLicensureService()
    return _instance
