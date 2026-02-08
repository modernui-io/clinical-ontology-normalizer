"""Vendor Risk Management Service (COO-3).

Manages third-party vendor risk for the clinical trial patient recruitment
platform. Tracks vendor records, compliance certifications, risk assessments,
and provides portfolio-level metrics for GRC oversight.

Usage:
    from app.services.vendor_management_service import get_vendor_management_service

    service = get_vendor_management_service()
    vendors = service.list_vendors()
    metrics = service.get_metrics()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.vendor_management import (
    AssessmentRequest,
    CertificationAlert,
    CertificationName,
    CertificationStatus,
    ComplianceCertification,
    ContractRenewal,
    DataAccessLevel,
    RiskLevel,
    VendorCategory,
    VendorCreate,
    VendorMetrics,
    VendorRecord,
    VendorRiskAssessment,
    VendorStatus,
    VendorUpdate,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_vendor_service_instance: VendorManagementService | None = None
_vendor_service_lock = Lock()

# ---------------------------------------------------------------------------
# Risk score -> Risk level thresholds
# ---------------------------------------------------------------------------

RISK_SCORE_THRESHOLDS: list[tuple[float, RiskLevel]] = [
    (76.0, RiskLevel.CRITICAL),
    (51.0, RiskLevel.HIGH),
    (26.0, RiskLevel.MEDIUM),
    (1.0, RiskLevel.LOW),
    (0.0, RiskLevel.MINIMAL),
]

# Assessment dimension weights for overall score calculation
ASSESSMENT_WEIGHTS = {
    "data_handling": 0.30,
    "security_posture": 0.30,
    "compliance": 0.25,
    "business_continuity": 0.15,
}


def _risk_level_from_score(score: float) -> RiskLevel:
    """Determine risk level from a 0-100 score."""
    for threshold, level in RISK_SCORE_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.MINIMAL


def _build_seed_vendors() -> list[VendorRecord]:
    """Build pre-populated vendor records for demo/seed data."""
    now = datetime.now(timezone.utc)
    one_year_ago = now - timedelta(days=365)
    one_year_ahead = now + timedelta(days=365)
    six_months_ahead = now + timedelta(days=180)
    three_months_ahead = now + timedelta(days=90)
    two_months_ahead = now + timedelta(days=60)
    thirty_days_ahead = now + timedelta(days=30)
    fifteen_days_ahead = now + timedelta(days=15)
    expired_30_days = now - timedelta(days=30)

    vendors: list[VendorRecord] = [
        # 1. AWS - Cloud Infrastructure
        VendorRecord(
            id="vendor-001",
            name="Amazon Web Services (AWS)",
            category=VendorCategory.CLOUD_INFRASTRUCTURE,
            description=(
                "Primary cloud infrastructure provider. Hosts all production "
                "workloads, databases, and storage for the platform."
            ),
            contact_email="enterprise-support@aws.amazon.com",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=480000.0,
            risk_level=RiskLevel.CRITICAL,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.PHI,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=90),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.ISO27001,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=90),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.FEDRAMP,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=60),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.HIPAA_BAA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=120),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=82.0,
            last_assessment_date=now - timedelta(days=90),
            next_assessment_due=three_months_ahead,
            notes="Critical dependency. BAA executed. HIPAA-eligible services configured.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 2. Metriport - Data Processing / Integration
        VendorRecord(
            id="vendor-002",
            name="Metriport",
            category=VendorCategory.INTEGRATION,
            description=(
                "Healthcare data integration platform. Provides FHIR-based "
                "patient data aggregation and interoperability services."
            ),
            contact_email="support@metriport.com",
            contract_start=one_year_ago,
            contract_end=six_months_ahead,
            annual_cost=120000.0,
            risk_level=RiskLevel.HIGH,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.PHI,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.HIPAA_BAA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=60),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.PENDING,
                    verified_date=None,
                    expiry_date=None,
                ),
            ],
            risk_score=65.0,
            last_assessment_date=now - timedelta(days=60),
            next_assessment_due=two_months_ahead,
            notes="FHIR integration partner. BAA executed. SOC 2 audit in progress.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 3. Supabase (PostgreSQL)
        VendorRecord(
            id="vendor-003",
            name="Supabase (PostgreSQL)",
            category=VendorCategory.DATA_PROCESSING,
            description=(
                "Managed PostgreSQL database service. Hosts primary "
                "relational data store for patient and clinical data."
            ),
            contact_email="support@supabase.io",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=36000.0,
            risk_level=RiskLevel.HIGH,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.PHI,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=45),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.HIPAA_BAA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=90),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=58.0,
            last_assessment_date=now - timedelta(days=45),
            next_assessment_due=three_months_ahead,
            notes="Primary database. Encryption at rest and in transit enabled.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 4. Redis Labs
        VendorRecord(
            id="vendor-004",
            name="Redis Labs",
            category=VendorCategory.CLOUD_INFRASTRUCTURE,
            description=(
                "Managed Redis service. Provides caching, job queues, "
                "and session storage."
            ),
            contact_email="support@redis.com",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=18000.0,
            risk_level=RiskLevel.MEDIUM,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.METADATA,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=120),
                    expiry_date=six_months_ahead,
                ),
            ],
            risk_score=38.0,
            last_assessment_date=now - timedelta(days=120),
            next_assessment_due=thirty_days_ahead,
            notes="Caching layer. No PHI stored. TLS enabled.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 5. Anthropic
        VendorRecord(
            id="vendor-005",
            name="Anthropic",
            category=VendorCategory.ANALYTICS,
            description=(
                "AI/ML provider for clinical NLP, guideline RAG, and "
                "clinical decision support features."
            ),
            contact_email="enterprise@anthropic.com",
            contract_start=now - timedelta(days=180),
            contract_end=six_months_ahead,
            annual_cost=96000.0,
            risk_level=RiskLevel.HIGH,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.METADATA,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=30),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=55.0,
            last_assessment_date=now - timedelta(days=30),
            next_assessment_due=three_months_ahead,
            notes="AI provider. No PHI sent to API. De-identified data only.",
            created_at=now - timedelta(days=180),
            updated_at=now,
        ),
        # 6. Clerk (Auth)
        VendorRecord(
            id="vendor-006",
            name="Clerk",
            category=VendorCategory.SECURITY,
            description=(
                "Authentication and user management platform. "
                "Handles user identity, SSO, and session management."
            ),
            contact_email="support@clerk.dev",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=24000.0,
            risk_level=RiskLevel.HIGH,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.METADATA,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=60),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.ISO27001,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=60),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=52.0,
            last_assessment_date=now - timedelta(days=60),
            next_assessment_due=two_months_ahead,
            notes="Identity provider. Handles PII (email, name). No PHI access.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 7. Vercel
        VendorRecord(
            id="vendor-007",
            name="Vercel",
            category=VendorCategory.CLOUD_INFRASTRUCTURE,
            description=(
                "Frontend hosting and edge deployment platform. "
                "Serves the Next.js web application."
            ),
            contact_email="support@vercel.com",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=12000.0,
            risk_level=RiskLevel.MEDIUM,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.NONE,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=90),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=30.0,
            last_assessment_date=now - timedelta(days=90),
            next_assessment_due=three_months_ahead,
            notes="Frontend hosting only. No backend data access.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 8. Datadog
        VendorRecord(
            id="vendor-008",
            name="Datadog",
            category=VendorCategory.CLOUD_INFRASTRUCTURE,
            description=(
                "Application performance monitoring, logging, and "
                "infrastructure observability platform."
            ),
            contact_email="support@datadoghq.com",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=42000.0,
            risk_level=RiskLevel.LOW,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.METADATA,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=45),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.ISO27001,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=45),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.HIPAA_BAA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=45),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=18.0,
            last_assessment_date=now - timedelta(days=45),
            next_assessment_due=six_months_ahead,
            notes="Monitoring only. PHI scrubbing enabled in log pipeline.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 9. External Clinical Data Provider
        VendorRecord(
            id="vendor-009",
            name="Clinical Data Solutions Inc.",
            category=VendorCategory.CLINICAL_OPERATIONS,
            description=(
                "External clinical data provider. Supplies real-world "
                "evidence data, lab results, and clinical trial benchmarks."
            ),
            contact_email="contracts@clinicaldatasolutions.com",
            contract_start=one_year_ago,
            contract_end=three_months_ahead,
            annual_cost=240000.0,
            risk_level=RiskLevel.CRITICAL,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.PHI,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.HIPAA_BAA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=30),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.HITRUST,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=30),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.EXPIRED,
                    verified_date=now - timedelta(days=400),
                    expiry_date=expired_30_days,
                ),
            ],
            risk_score=78.0,
            last_assessment_date=now - timedelta(days=30),
            next_assessment_due=fifteen_days_ahead,
            notes="Critical data supplier. SOC 2 renewal in progress. PHI access via SFTP.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 10. Legal/Compliance Consultant
        VendorRecord(
            id="vendor-010",
            name="HealthTech Legal Partners LLP",
            category=VendorCategory.COMPLIANCE,
            description=(
                "Legal and regulatory compliance consulting firm. "
                "Advises on HIPAA, FDA, and clinical trial regulations."
            ),
            contact_email="info@healthtechlegal.com",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=180000.0,
            risk_level=RiskLevel.MEDIUM,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.METADATA,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.NOT_REQUIRED,
                    verified_date=None,
                    expiry_date=None,
                ),
            ],
            risk_score=35.0,
            last_assessment_date=now - timedelta(days=180),
            next_assessment_due=two_months_ahead,
            notes="Advisory role. Access to de-identified summaries only.",
            created_at=one_year_ago,
            updated_at=now,
        ),
        # 11. EDC Integration Partner
        VendorRecord(
            id="vendor-011",
            name="TrialSync EDC",
            category=VendorCategory.INTEGRATION,
            description=(
                "Electronic Data Capture integration partner. Provides "
                "bidirectional data exchange with sponsor EDC systems."
            ),
            contact_email="integrations@trialsync.com",
            contract_start=now - timedelta(days=270),
            contract_end=six_months_ahead,
            annual_cost=84000.0,
            risk_level=RiskLevel.HIGH,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.PHI,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.HIPAA_BAA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=90),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=90),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.GDPR_DPA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=60),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=62.0,
            last_assessment_date=now - timedelta(days=90),
            next_assessment_due=three_months_ahead,
            notes="EDC bidirectional sync. CDISC CDASH/SDTM compliant.",
            created_at=now - timedelta(days=270),
            updated_at=now,
        ),
        # 12. Backup Service
        VendorRecord(
            id="vendor-012",
            name="CloudVault Backup",
            category=VendorCategory.CLOUD_INFRASTRUCTURE,
            description=(
                "Cloud backup and disaster recovery service. "
                "Provides encrypted offsite backups and point-in-time recovery."
            ),
            contact_email="support@cloudvault.io",
            contract_start=one_year_ago,
            contract_end=one_year_ahead,
            annual_cost=9600.0,
            risk_level=RiskLevel.MEDIUM,
            status=VendorStatus.ACTIVE,
            data_access_level=DataAccessLevel.PHI,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=60),
                    expiry_date=one_year_ahead,
                ),
                ComplianceCertification(
                    name=CertificationName.HIPAA_BAA,
                    status=CertificationStatus.VERIFIED,
                    verified_date=now - timedelta(days=60),
                    expiry_date=one_year_ahead,
                ),
            ],
            risk_score=40.0,
            last_assessment_date=now - timedelta(days=60),
            next_assessment_due=three_months_ahead,
            notes="AES-256 encryption. Geo-redundant storage.",
            created_at=one_year_ago,
            updated_at=now,
        ),
    ]

    return vendors


class VendorManagementService:
    """Service for vendor/third-party risk management.

    Maintains a registry of vendors, tracks compliance certifications,
    conducts risk assessments, and provides portfolio-level metrics for
    GRC (Governance, Risk, Compliance) oversight.

    COO-3: Vendor Risk Management
    """

    def __init__(self) -> None:
        """Initialize with seed vendor data."""
        self._vendors: dict[str, VendorRecord] = {}
        self._assessments: dict[str, list[VendorRiskAssessment]] = {}
        self._next_id_counter: int = 100

        # Load seed vendors
        for vendor in _build_seed_vendors():
            self._vendors[vendor.id] = vendor
            self._assessments[vendor.id] = []

        logger.info(
            "VendorManagementService initialized with %d vendors",
            len(self._vendors),
        )

    # -------------------------------------------------------------------
    # Vendor CRUD
    # -------------------------------------------------------------------

    def create_vendor(self, request: VendorCreate) -> VendorRecord:
        """Create a new vendor record.

        Args:
            request: Vendor creation request.

        Returns:
            Created vendor record.
        """
        now = datetime.now(timezone.utc)
        self._next_id_counter += 1
        vendor_id = f"vendor-{self._next_id_counter:03d}"

        vendor = VendorRecord(
            id=vendor_id,
            name=request.name,
            category=request.category,
            description=request.description,
            contact_email=request.contact_email,
            contract_start=request.contract_start,
            contract_end=request.contract_end,
            annual_cost=request.annual_cost,
            risk_level=request.risk_level,
            status=request.status,
            data_access_level=request.data_access_level,
            certifications=request.certifications,
            risk_score=0.0,
            last_assessment_date=None,
            next_assessment_due=now + timedelta(days=90),
            notes=request.notes,
            created_at=now,
            updated_at=now,
        )

        self._vendors[vendor_id] = vendor
        self._assessments[vendor_id] = []

        logger.info("Created vendor %s: %s", vendor_id, request.name)
        return vendor

    def update_vendor(
        self, vendor_id: str, request: VendorUpdate
    ) -> VendorRecord | None:
        """Update an existing vendor record.

        Args:
            vendor_id: Vendor ID to update.
            request: Update fields.

        Returns:
            Updated vendor record, or None if not found.
        """
        vendor = self._vendors.get(vendor_id)
        if vendor is None:
            return None

        now = datetime.now(timezone.utc)
        update_data = request.model_dump(exclude_none=True)

        # Build new vendor with updated fields
        vendor_dict = vendor.model_dump()
        vendor_dict.update(update_data)
        vendor_dict["updated_at"] = now

        updated = VendorRecord(**vendor_dict)
        self._vendors[vendor_id] = updated

        logger.info("Updated vendor %s", vendor_id)
        return updated

    def get_vendor(self, vendor_id: str) -> VendorRecord | None:
        """Get a vendor by ID.

        Args:
            vendor_id: Vendor ID.

        Returns:
            Vendor record or None if not found.
        """
        return self._vendors.get(vendor_id)

    def list_vendors(
        self,
        category: VendorCategory | None = None,
        risk_level: RiskLevel | None = None,
        status: VendorStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[VendorRecord], int]:
        """List vendors with optional filtering.

        Args:
            category: Filter by vendor category.
            risk_level: Filter by risk level.
            status: Filter by status.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            Tuple of (vendor list, total count).
        """
        vendors = list(self._vendors.values())

        if category is not None:
            vendors = [v for v in vendors if v.category == category]
        if risk_level is not None:
            vendors = [v for v in vendors if v.risk_level == risk_level]
        if status is not None:
            vendors = [v for v in vendors if v.status == status]

        # Sort by name
        vendors.sort(key=lambda v: v.name)

        total = len(vendors)
        vendors = vendors[offset : offset + limit]

        return vendors, total

    # -------------------------------------------------------------------
    # Risk Assessments
    # -------------------------------------------------------------------

    def conduct_assessment(
        self, vendor_id: str, request: AssessmentRequest
    ) -> VendorRiskAssessment | None:
        """Conduct a risk assessment on a vendor.

        Calculates weighted overall score and auto-updates vendor risk level.

        Args:
            vendor_id: Vendor ID to assess.
            request: Assessment scores and findings.

        Returns:
            Created assessment, or None if vendor not found.

        Raises:
            ValueError: If vendor is in TERMINATED status.
        """
        vendor = self._vendors.get(vendor_id)
        if vendor is None:
            return None

        if vendor.status == VendorStatus.TERMINATED:
            raise ValueError(
                f"Cannot assess terminated vendor {vendor_id}"
            )

        now = datetime.now(timezone.utc)

        # Calculate weighted overall score (0-100 scale)
        overall_score = (
            request.data_handling_score * 10 * ASSESSMENT_WEIGHTS["data_handling"]
            + request.security_posture_score * 10 * ASSESSMENT_WEIGHTS["security_posture"]
            + request.compliance_score * 10 * ASSESSMENT_WEIGHTS["compliance"]
            + request.business_continuity_score * 10 * ASSESSMENT_WEIGHTS["business_continuity"]
        )
        overall_score = round(min(max(overall_score, 0.0), 100.0), 2)

        risk_level = _risk_level_from_score(overall_score)

        assessment = VendorRiskAssessment(
            id=f"assess-{uuid4().hex[:12]}",
            vendor_id=vendor_id,
            assessment_date=now,
            assessed_by=request.assessed_by,
            data_handling_score=request.data_handling_score,
            security_posture_score=request.security_posture_score,
            compliance_score=request.compliance_score,
            business_continuity_score=request.business_continuity_score,
            overall_risk_score=overall_score,
            findings=request.findings,
            recommendations=request.recommendations,
            risk_level=risk_level,
        )

        # Store assessment
        if vendor_id not in self._assessments:
            self._assessments[vendor_id] = []
        self._assessments[vendor_id].append(assessment)

        # Update vendor risk level, score, and assessment dates
        vendor_dict = vendor.model_dump()
        vendor_dict["risk_level"] = risk_level
        vendor_dict["risk_score"] = overall_score
        vendor_dict["last_assessment_date"] = now
        vendor_dict["next_assessment_due"] = now + timedelta(days=90)
        vendor_dict["updated_at"] = now
        self._vendors[vendor_id] = VendorRecord(**vendor_dict)

        logger.info(
            "Assessment completed for vendor %s: score=%.1f, risk=%s",
            vendor_id,
            overall_score,
            risk_level.value,
        )

        return assessment

    def get_assessments(
        self, vendor_id: str
    ) -> list[VendorRiskAssessment] | None:
        """Get assessment history for a vendor.

        Args:
            vendor_id: Vendor ID.

        Returns:
            List of assessments, or None if vendor not found.
        """
        if vendor_id not in self._vendors:
            return None
        return list(self._assessments.get(vendor_id, []))

    def get_assessment(
        self, assessment_id: str
    ) -> VendorRiskAssessment | None:
        """Get a single assessment by ID.

        Args:
            assessment_id: Assessment ID.

        Returns:
            Assessment or None if not found.
        """
        for assessments in self._assessments.values():
            for assessment in assessments:
                if assessment.id == assessment_id:
                    return assessment
        return None

    # -------------------------------------------------------------------
    # Certification Tracking
    # -------------------------------------------------------------------

    def check_certifications(self) -> list[CertificationAlert]:
        """Check for expired or expiring certifications across all vendors.

        Returns:
            List of certification alerts for expired or expiring (within 90 days)
            certifications.
        """
        now = datetime.now(timezone.utc)
        alerts: list[CertificationAlert] = []

        for vendor in self._vendors.values():
            for cert in vendor.certifications:
                if cert.status == CertificationStatus.NOT_REQUIRED:
                    continue
                if cert.expiry_date is None:
                    continue

                days_until = (cert.expiry_date - now).days

                # Alert if expired or expiring within 90 days
                if days_until <= 90:
                    alerts.append(
                        CertificationAlert(
                            vendor_id=vendor.id,
                            vendor_name=vendor.name,
                            certification=cert,
                            days_until_expiry=days_until,
                        )
                    )

        # Sort: expired first, then by days until expiry
        alerts.sort(key=lambda a: a.days_until_expiry if a.days_until_expiry is not None else 0)
        return alerts

    # -------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------

    def get_metrics(self) -> VendorMetrics:
        """Get aggregated vendor portfolio metrics.

        Returns:
            Portfolio-level metrics including counts, spend, and risk.
        """
        now = datetime.now(timezone.utc)
        vendors = list(self._vendors.values())

        # Count by category
        by_category: dict[str, int] = {}
        for cat in VendorCategory:
            count = sum(1 for v in vendors if v.category == cat)
            if count > 0:
                by_category[cat.value] = count

        # Count by risk level
        by_risk_level: dict[str, int] = {}
        for level in RiskLevel:
            count = sum(1 for v in vendors if v.risk_level == level)
            if count > 0:
                by_risk_level[level.value] = count

        # Count by status
        by_status: dict[str, int] = {}
        for st in VendorStatus:
            count = sum(1 for v in vendors if v.status == st)
            if count > 0:
                by_status[st.value] = count

        # Total annual spend
        total_annual_spend = sum(v.annual_cost for v in vendors)

        # Assessments due in 30 days
        thirty_days_out = now + timedelta(days=30)
        assessments_due = sum(
            1
            for v in vendors
            if v.next_assessment_due is not None
            and v.next_assessment_due <= thirty_days_out
        )

        # Expired certifications
        expired_certs = 0
        for v in vendors:
            for cert in v.certifications:
                if cert.status == CertificationStatus.EXPIRED:
                    expired_certs += 1
                elif (
                    cert.expiry_date is not None
                    and cert.expiry_date < now
                    and cert.status != CertificationStatus.NOT_REQUIRED
                ):
                    expired_certs += 1

        # Average risk score
        scores = [v.risk_score for v in vendors if v.risk_score > 0]
        avg_risk = round(sum(scores) / len(scores), 2) if scores else 0.0

        return VendorMetrics(
            total_vendors=len(vendors),
            by_category=by_category,
            by_risk_level=by_risk_level,
            by_status=by_status,
            total_annual_spend=total_annual_spend,
            assessments_due_30days=assessments_due,
            expired_certifications=expired_certs,
            average_risk_score=avg_risk,
        )

    # -------------------------------------------------------------------
    # Data Access Queries
    # -------------------------------------------------------------------

    def get_vendors_by_data_access(
        self, level: DataAccessLevel
    ) -> list[VendorRecord]:
        """Find all vendors with a given data access level.

        Args:
            level: Data access level to filter by.

        Returns:
            List of vendors with the specified access level.
        """
        return [
            v for v in self._vendors.values() if v.data_access_level == level
        ]

    # -------------------------------------------------------------------
    # Vendor Lifecycle
    # -------------------------------------------------------------------

    def suspend_vendor(
        self, vendor_id: str, reason: str
    ) -> VendorRecord | None:
        """Suspend a vendor.

        Args:
            vendor_id: Vendor to suspend.
            reason: Reason for suspension.

        Returns:
            Updated vendor, or None if not found.

        Raises:
            ValueError: If vendor is already suspended or terminated.
        """
        vendor = self._vendors.get(vendor_id)
        if vendor is None:
            return None

        if vendor.status == VendorStatus.SUSPENDED:
            raise ValueError(f"Vendor {vendor_id} is already suspended")
        if vendor.status == VendorStatus.TERMINATED:
            raise ValueError(f"Cannot suspend terminated vendor {vendor_id}")

        now = datetime.now(timezone.utc)
        vendor_dict = vendor.model_dump()
        vendor_dict["status"] = VendorStatus.SUSPENDED
        vendor_dict["notes"] = f"{vendor.notes}\n[SUSPENDED {now.isoformat()}] {reason}".strip()
        vendor_dict["updated_at"] = now
        updated = VendorRecord(**vendor_dict)
        self._vendors[vendor_id] = updated

        logger.info("Vendor %s suspended: %s", vendor_id, reason)
        return updated

    def reactivate_vendor(self, vendor_id: str) -> VendorRecord | None:
        """Reactivate a suspended vendor.

        Args:
            vendor_id: Vendor to reactivate.

        Returns:
            Updated vendor, or None if not found.

        Raises:
            ValueError: If vendor is not suspended.
        """
        vendor = self._vendors.get(vendor_id)
        if vendor is None:
            return None

        if vendor.status != VendorStatus.SUSPENDED:
            raise ValueError(
                f"Vendor {vendor_id} is not suspended (status: {vendor.status.value})"
            )

        now = datetime.now(timezone.utc)
        vendor_dict = vendor.model_dump()
        vendor_dict["status"] = VendorStatus.ACTIVE
        vendor_dict["notes"] = f"{vendor.notes}\n[REACTIVATED {now.isoformat()}]".strip()
        vendor_dict["updated_at"] = now
        updated = VendorRecord(**vendor_dict)
        self._vendors[vendor_id] = updated

        logger.info("Vendor %s reactivated", vendor_id)
        return updated

    # -------------------------------------------------------------------
    # Contract Renewals
    # -------------------------------------------------------------------

    def get_contract_renewals(self, days_ahead: int = 90) -> list[ContractRenewal]:
        """Get vendors with contracts expiring within N days.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of contract renewal notifications.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)

        renewals: list[ContractRenewal] = []
        for vendor in self._vendors.values():
            if vendor.contract_end is None:
                continue
            if vendor.contract_end <= cutoff:
                days_until = (vendor.contract_end - now).days
                renewals.append(
                    ContractRenewal(
                        vendor_id=vendor.id,
                        vendor_name=vendor.name,
                        contract_end=vendor.contract_end,
                        days_until_expiry=days_until,
                        annual_cost=vendor.annual_cost,
                        risk_level=vendor.risk_level,
                    )
                )

        renewals.sort(key=lambda r: r.days_until_expiry)
        return renewals


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_vendor_management_service() -> VendorManagementService:
    """Get or create the singleton VendorManagementService."""
    global _vendor_service_instance
    if _vendor_service_instance is None:
        with _vendor_service_lock:
            if _vendor_service_instance is None:
                _vendor_service_instance = VendorManagementService()
    return _vendor_service_instance


def reset_vendor_management_service() -> None:
    """Reset the singleton (for testing)."""
    global _vendor_service_instance
    with _vendor_service_lock:
        _vendor_service_instance = None
