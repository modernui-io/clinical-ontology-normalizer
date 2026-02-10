"""Lab Certification & Accreditation Service (CLINICAL-LC).

Manages laboratory certifications, accreditation tracking, proficiency testing,
lab qualifications for clinical trials, and compliance monitoring with
corrective action tracking.

Usage:
    from app.services.lab_certification_service import (
        get_lab_certification_service,
    )

    svc = get_lab_certification_service()
    labs = svc.list_laboratories()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.lab_certification import (
    AccreditationBody,
    CertificationStatus,
    CertificationType,
    ComplianceFinding,
    ComplianceFindingCreate,
    ComplianceFindingStatus,
    ComplianceFindingUpdate,
    FindingSeverity,
    FindingType,
    LabCertification,
    LabCertificationCreate,
    LabCertificationUpdate,
    LabMetrics,
    LabQualification,
    LabQualificationCreate,
    LabQualificationUpdate,
    LabType,
    Laboratory,
    LaboratoryCreate,
    LaboratoryUpdate,
    ProficiencyResult,
    ProficiencyTest,
    ProficiencyTestCreate,
    ProficiencyTestUpdate,
    QualificationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Certifications expiring within this window are flagged
EXPIRING_SOON_DAYS = 90


class LabCertificationService:
    """In-memory Lab Certification & Accreditation engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._labs: dict[str, Laboratory] = {}
        self._certifications: dict[str, LabCertification] = {}
        self._proficiency_tests: dict[str, ProficiencyTest] = {}
        self._qualifications: dict[str, LabQualification] = {}
        self._findings: dict[str, ComplianceFinding] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic lab certification data."""
        now = datetime.now(timezone.utc)

        # --- 5 Laboratories ---
        labs_data = [
            {
                "id": "LAB-001",
                "name": "Covance Central Laboratory",
                "lab_type": LabType.CENTRAL,
                "address": "8211 SciCor Drive, Indianapolis, IN 46214",
                "country": "US",
                "contact_name": "Dr. Rebecca Chen",
                "contact_email": "rebecca.chen@covance.com",
                "phone": "+1-317-271-1200",
                "active": True,
                "capabilities": [
                    "hematology", "chemistry", "immunology", "biomarker",
                    "pharmacokinetic", "urinalysis", "coagulation",
                ],
                "specializations": ["oncology", "ophthalmology", "immunology"],
            },
            {
                "id": "LAB-002",
                "name": "Q2 Solutions Reference Lab",
                "lab_type": LabType.REFERENCE,
                "address": "2400 Research Blvd, Durham, NC 27709",
                "country": "US",
                "contact_name": "Dr. James Whitfield",
                "contact_email": "james.whitfield@q2labsolutions.com",
                "phone": "+1-919-998-7000",
                "active": True,
                "capabilities": [
                    "hematology", "chemistry", "immunology", "biomarker",
                    "coagulation",
                ],
                "specializations": ["dermatology", "autoimmune", "rare diseases"],
            },
            {
                "id": "LAB-003",
                "name": "ICON Bioanalytical Labs",
                "lab_type": LabType.BIOANALYTICAL,
                "address": "100 Front Street, Worcester, MA 01608",
                "country": "US",
                "contact_name": "Dr. Samantha Park",
                "contact_email": "samantha.park@iconplc.com",
                "phone": "+1-508-791-0700",
                "active": True,
                "capabilities": [
                    "pharmacokinetic", "biomarker", "immunology",
                ],
                "specializations": ["oncology", "CNS", "metabolic"],
            },
            {
                "id": "LAB-004",
                "name": "Eurofins Central Lab Europe",
                "lab_type": LabType.CENTRAL,
                "address": "Rue Montoyer 62, 1000 Brussels, Belgium",
                "country": "BE",
                "contact_name": "Dr. Klaus Weber",
                "contact_email": "klaus.weber@eurofins.com",
                "phone": "+32-2-766-1620",
                "active": True,
                "capabilities": [
                    "hematology", "chemistry", "immunology", "urinalysis",
                    "coagulation",
                ],
                "specializations": ["ophthalmology", "cardiovascular"],
            },
            {
                "id": "LAB-005",
                "name": "Tokyo Clinical Lab Services",
                "lab_type": LabType.LOCAL,
                "address": "3-5-1 Nihonbashi, Chuo-ku, Tokyo 103-0027",
                "country": "JP",
                "contact_name": "Dr. Yuki Tanaka",
                "contact_email": "yuki.tanaka@tclsjp.com",
                "phone": "+81-3-6202-7000",
                "active": False,
                "capabilities": ["hematology", "chemistry", "urinalysis"],
                "specializations": ["oncology"],
            },
        ]

        for lab in labs_data:
            self._labs[lab["id"]] = Laboratory(**lab)

        # --- 10 Certifications ---
        certs_data = [
            {
                "id": "CERT-001",
                "lab_id": "LAB-001",
                "certification_type": CertificationType.CLIA,
                "accreditation_body": AccreditationBody.CLIA,
                "certificate_number": "15D2082770",
                "issued_date": now - timedelta(days=365),
                "expiry_date": now + timedelta(days=365),
                "status": CertificationStatus.ACTIVE,
                "scope": "Full clinical laboratory testing including chemistry, hematology, immunology",
                "last_inspection_date": now - timedelta(days=180),
                "next_inspection_date": now + timedelta(days=185),
                "findings_count": 1,
                "corrective_actions_pending": 0,
            },
            {
                "id": "CERT-002",
                "lab_id": "LAB-001",
                "certification_type": CertificationType.CAP,
                "accreditation_body": AccreditationBody.CAP,
                "certificate_number": "CAP-9012345",
                "issued_date": now - timedelta(days=300),
                "expiry_date": now + timedelta(days=65),
                "status": CertificationStatus.ACTIVE,
                "scope": "Anatomic and clinical pathology, toxicology, immunohistochemistry",
                "last_inspection_date": now - timedelta(days=150),
                "next_inspection_date": now + timedelta(days=30),
                "findings_count": 2,
                "corrective_actions_pending": 1,
            },
            {
                "id": "CERT-003",
                "lab_id": "LAB-001",
                "certification_type": CertificationType.GCP_COMPLIANT,
                "accreditation_body": AccreditationBody.ISO,
                "certificate_number": "GCP-2024-IND-001",
                "issued_date": now - timedelta(days=200),
                "expiry_date": now + timedelta(days=530),
                "status": CertificationStatus.ACTIVE,
                "scope": "Good Clinical Practice compliance for clinical trial testing",
                "last_inspection_date": now - timedelta(days=100),
                "next_inspection_date": now + timedelta(days=265),
                "findings_count": 0,
                "corrective_actions_pending": 0,
            },
            {
                "id": "CERT-004",
                "lab_id": "LAB-002",
                "certification_type": CertificationType.CLIA,
                "accreditation_body": AccreditationBody.CLIA,
                "certificate_number": "34D2094812",
                "issued_date": now - timedelta(days=400),
                "expiry_date": now + timedelta(days=330),
                "status": CertificationStatus.ACTIVE,
                "scope": "Clinical chemistry, hematology, immunology",
                "last_inspection_date": now - timedelta(days=200),
                "next_inspection_date": now + timedelta(days=165),
                "findings_count": 0,
                "corrective_actions_pending": 0,
            },
            {
                "id": "CERT-005",
                "lab_id": "LAB-002",
                "certification_type": CertificationType.ISO_15189,
                "accreditation_body": AccreditationBody.ISO,
                "certificate_number": "ISO-15189-2024-NC-002",
                "issued_date": now - timedelta(days=500),
                "expiry_date": now + timedelta(days=230),
                "status": CertificationStatus.ACTIVE,
                "scope": "Medical laboratory quality and competence",
                "last_inspection_date": now - timedelta(days=250),
                "next_inspection_date": now + timedelta(days=115),
                "findings_count": 1,
                "corrective_actions_pending": 1,
            },
            {
                "id": "CERT-006",
                "lab_id": "LAB-003",
                "certification_type": CertificationType.GMP_COMPLIANT,
                "accreditation_body": AccreditationBody.ISO,
                "certificate_number": "GMP-BA-2024-003",
                "issued_date": now - timedelta(days=180),
                "expiry_date": now + timedelta(days=550),
                "status": CertificationStatus.ACTIVE,
                "scope": "Bioanalytical method validation and sample analysis",
                "last_inspection_date": now - timedelta(days=90),
                "next_inspection_date": now + timedelta(days=275),
                "findings_count": 0,
                "corrective_actions_pending": 0,
            },
            {
                "id": "CERT-007",
                "lab_id": "LAB-003",
                "certification_type": CertificationType.CLIA,
                "accreditation_body": AccreditationBody.CLIA,
                "certificate_number": "22D2071893",
                "issued_date": now - timedelta(days=700),
                "expiry_date": now - timedelta(days=10),
                "status": CertificationStatus.EXPIRED,
                "scope": "Clinical laboratory testing",
                "last_inspection_date": now - timedelta(days=365),
                "next_inspection_date": None,
                "findings_count": 3,
                "corrective_actions_pending": 2,
            },
            {
                "id": "CERT-008",
                "lab_id": "LAB-004",
                "certification_type": CertificationType.ISO_15189,
                "accreditation_body": AccreditationBody.DAKKS,
                "certificate_number": "DAKKS-ML-2024-EU-004",
                "issued_date": now - timedelta(days=450),
                "expiry_date": now + timedelta(days=280),
                "status": CertificationStatus.ACTIVE,
                "scope": "Medical laboratory testing under ISO 15189:2022",
                "last_inspection_date": now - timedelta(days=225),
                "next_inspection_date": now + timedelta(days=140),
                "findings_count": 1,
                "corrective_actions_pending": 0,
            },
            {
                "id": "CERT-009",
                "lab_id": "LAB-004",
                "certification_type": CertificationType.GCP_COMPLIANT,
                "accreditation_body": AccreditationBody.ISO,
                "certificate_number": "GCP-EU-2025-004",
                "issued_date": now - timedelta(days=100),
                "expiry_date": now + timedelta(days=630),
                "status": CertificationStatus.PENDING,
                "scope": "GCP compliance for EU clinical trial laboratory work",
                "last_inspection_date": None,
                "next_inspection_date": now + timedelta(days=60),
                "findings_count": 0,
                "corrective_actions_pending": 0,
            },
            {
                "id": "CERT-010",
                "lab_id": "LAB-005",
                "certification_type": CertificationType.STATE_LICENSE,
                "accreditation_body": AccreditationBody.JIS,
                "certificate_number": "JIS-TKY-2023-005",
                "issued_date": now - timedelta(days=800),
                "expiry_date": now - timedelta(days=70),
                "status": CertificationStatus.SUSPENDED,
                "scope": "Tokyo prefectural clinical laboratory license",
                "last_inspection_date": now - timedelta(days=400),
                "next_inspection_date": None,
                "findings_count": 4,
                "corrective_actions_pending": 3,
            },
        ]

        for c in certs_data:
            self._certifications[c["id"]] = LabCertification(**c)

        # --- 7 Proficiency Tests ---
        pt_data = [
            {
                "id": "PT-001",
                "lab_id": "LAB-001",
                "test_name": "CAP Surveys - Chemistry",
                "analyte": "Hemoglobin A1c",
                "sample_id": "C-24-A1C-001",
                "expected_value": 7.2,
                "reported_value": 7.1,
                "result": ProficiencyResult.SATISFACTORY,
                "tested_date": now - timedelta(days=45),
                "reported_date": now - timedelta(days=40),
                "cycle": "2025-Q4",
                "notes": None,
            },
            {
                "id": "PT-002",
                "lab_id": "LAB-001",
                "test_name": "CAP Surveys - Hematology",
                "analyte": "Complete Blood Count",
                "sample_id": "H-24-CBC-002",
                "expected_value": 14.5,
                "reported_value": 14.3,
                "result": ProficiencyResult.SATISFACTORY,
                "tested_date": now - timedelta(days=42),
                "reported_date": now - timedelta(days=38),
                "cycle": "2025-Q4",
                "notes": None,
            },
            {
                "id": "PT-003",
                "lab_id": "LAB-002",
                "test_name": "CAP Surveys - Immunology",
                "analyte": "IgE Total",
                "sample_id": "I-24-IGE-003",
                "expected_value": 250.0,
                "reported_value": 268.0,
                "result": ProficiencyResult.SATISFACTORY,
                "tested_date": now - timedelta(days=30),
                "reported_date": now - timedelta(days=25),
                "cycle": "2026-Q1",
                "notes": "Within acceptable range",
            },
            {
                "id": "PT-004",
                "lab_id": "LAB-002",
                "test_name": "CAP Surveys - Chemistry",
                "analyte": "Creatinine",
                "sample_id": "C-24-CREAT-004",
                "expected_value": 1.2,
                "reported_value": 1.8,
                "result": ProficiencyResult.UNSATISFACTORY,
                "tested_date": now - timedelta(days=28),
                "reported_date": now - timedelta(days=22),
                "cycle": "2026-Q1",
                "notes": "Reported value exceeds acceptable deviation; root cause investigation initiated",
            },
            {
                "id": "PT-005",
                "lab_id": "LAB-003",
                "test_name": "RIQAS Immunoassay",
                "analyte": "Anti-Drug Antibody",
                "sample_id": "IM-24-ADA-005",
                "expected_value": 120.0,
                "reported_value": 118.5,
                "result": ProficiencyResult.SATISFACTORY,
                "tested_date": now - timedelta(days=20),
                "reported_date": now - timedelta(days=15),
                "cycle": "2026-Q1",
                "notes": None,
            },
            {
                "id": "PT-006",
                "lab_id": "LAB-004",
                "test_name": "EQAS Chemistry Panel",
                "analyte": "ALT/SGPT",
                "sample_id": "EU-24-ALT-006",
                "expected_value": 45.0,
                "reported_value": 44.2,
                "result": ProficiencyResult.SATISFACTORY,
                "tested_date": now - timedelta(days=15),
                "reported_date": now - timedelta(days=10),
                "cycle": "2026-Q1",
                "notes": None,
            },
            {
                "id": "PT-007",
                "lab_id": "LAB-005",
                "test_name": "NEQAS Hematology",
                "analyte": "WBC Count",
                "sample_id": "JP-24-WBC-007",
                "expected_value": 6.8,
                "reported_value": 0.0,
                "result": ProficiencyResult.PENDING,
                "tested_date": now - timedelta(days=5),
                "reported_date": now - timedelta(days=3),
                "cycle": "2026-Q1",
                "notes": "Lab suspended; results pending review",
            },
        ]

        for pt in pt_data:
            self._proficiency_tests[pt["id"]] = ProficiencyTest(**pt)

        # --- 4 Lab Qualifications ---
        qual_data = [
            {
                "id": "QUAL-001",
                "lab_id": "LAB-001",
                "trial_id": EYLEA_TRIAL,
                "qualified_date": now - timedelta(days=120),
                "qualification_status": QualificationStatus.QUALIFIED,
                "assays_qualified": [
                    "VEGF ELISA", "Anti-Drug Antibody", "Complete Blood Count",
                    "Metabolic Panel", "Urinalysis",
                ],
                "training_completed": True,
                "equipment_verified": True,
                "sop_reviewed": True,
                "qualified_by": "Dr. Sarah Mitchell",
                "notes": "Full qualification for all protocol-specified assessments",
            },
            {
                "id": "QUAL-002",
                "lab_id": "LAB-002",
                "trial_id": DUPIXENT_TRIAL,
                "qualified_date": now - timedelta(days=90),
                "qualification_status": QualificationStatus.QUALIFIED,
                "assays_qualified": [
                    "Total IgE", "Eosinophil Count", "Thymus and Activation Regulated Chemokine",
                    "Complete Blood Count",
                ],
                "training_completed": True,
                "equipment_verified": True,
                "sop_reviewed": True,
                "qualified_by": "Dr. David Park",
                "notes": "Qualified for dermatology biomarker panel",
            },
            {
                "id": "QUAL-003",
                "lab_id": "LAB-003",
                "trial_id": LIBTAYO_TRIAL,
                "qualified_date": None,
                "qualification_status": QualificationStatus.CONDITIONALLY_QUALIFIED,
                "assays_qualified": [
                    "PD-L1 IHC", "Anti-Drug Antibody",
                ],
                "training_completed": True,
                "equipment_verified": True,
                "sop_reviewed": False,
                "qualified_by": None,
                "notes": "Awaiting SOP review completion; conditionally approved for PK analysis",
            },
            {
                "id": "QUAL-004",
                "lab_id": "LAB-005",
                "trial_id": EYLEA_TRIAL,
                "qualified_date": None,
                "qualification_status": QualificationStatus.DISQUALIFIED,
                "assays_qualified": [],
                "training_completed": False,
                "equipment_verified": False,
                "sop_reviewed": False,
                "qualified_by": "Dr. Sarah Mitchell",
                "notes": "Lab suspended due to certification issues; disqualified from trial",
            },
        ]

        for q in qual_data:
            self._qualifications[q["id"]] = LabQualification(**q)

        # --- 6 Compliance Findings ---
        findings_data = [
            {
                "id": "CF-001",
                "lab_id": "LAB-001",
                "certification_id": "CERT-002",
                "finding_type": FindingType.DOCUMENTATION,
                "severity": FindingSeverity.MINOR,
                "description": "Temperature monitoring logs for reagent storage refrigerator incomplete for 3 days in October 2025",
                "identified_date": now - timedelta(days=150),
                "due_date": now - timedelta(days=120),
                "resolved_date": now - timedelta(days=125),
                "corrective_action": "Implemented automated temperature monitoring with SMS alerts; retrained staff on log procedures",
                "status": ComplianceFindingStatus.VERIFIED,
            },
            {
                "id": "CF-002",
                "lab_id": "LAB-001",
                "certification_id": "CERT-002",
                "finding_type": FindingType.PROCESS,
                "severity": FindingSeverity.MAJOR,
                "description": "Calibration verification for chemistry analyzer not performed within required 6-month interval; 2-week gap identified",
                "identified_date": now - timedelta(days=60),
                "due_date": now - timedelta(days=15),
                "resolved_date": None,
                "corrective_action": "Calibration completed; preventive maintenance schedule updated in LIMS",
                "status": ComplianceFindingStatus.IN_PROGRESS,
            },
            {
                "id": "CF-003",
                "lab_id": "LAB-002",
                "certification_id": "CERT-005",
                "finding_type": FindingType.EQUIPMENT,
                "severity": FindingSeverity.MAJOR,
                "description": "Pipette calibration certificates expired for 4 volumetric pipettes used in immunoassay testing",
                "identified_date": now - timedelta(days=30),
                "due_date": now + timedelta(days=15),
                "resolved_date": None,
                "corrective_action": None,
                "status": ComplianceFindingStatus.OPEN,
            },
            {
                "id": "CF-004",
                "lab_id": "LAB-003",
                "certification_id": "CERT-007",
                "finding_type": FindingType.DATA_INTEGRITY,
                "severity": FindingSeverity.CRITICAL,
                "description": "LIMS audit trail shows manual override of quality control flags without supervisor review for 12 samples",
                "identified_date": now - timedelta(days=20),
                "due_date": now + timedelta(days=10),
                "resolved_date": None,
                "corrective_action": None,
                "status": ComplianceFindingStatus.OPEN,
            },
            {
                "id": "CF-005",
                "lab_id": "LAB-005",
                "certification_id": "CERT-010",
                "finding_type": FindingType.PERSONNEL,
                "severity": FindingSeverity.CRITICAL,
                "description": "Laboratory director qualifications do not meet regulatory requirements; no documented competency assessments for 5 analysts",
                "identified_date": now - timedelta(days=90),
                "due_date": now - timedelta(days=30),
                "resolved_date": None,
                "corrective_action": None,
                "status": ComplianceFindingStatus.OVERDUE,
            },
            {
                "id": "CF-006",
                "lab_id": "LAB-005",
                "certification_id": "CERT-010",
                "finding_type": FindingType.QUALITY_CONTROL,
                "severity": FindingSeverity.MAJOR,
                "description": "QC acceptance criteria not defined for 3 of 8 analytes on the chemistry panel; out-of-range QC results not investigated",
                "identified_date": now - timedelta(days=85),
                "due_date": now - timedelta(days=25),
                "resolved_date": None,
                "corrective_action": None,
                "status": ComplianceFindingStatus.OVERDUE,
            },
        ]

        for f in findings_data:
            self._findings[f["id"]] = ComplianceFinding(**f)

    # ------------------------------------------------------------------
    # Laboratory CRUD
    # ------------------------------------------------------------------

    def list_laboratories(
        self,
        *,
        lab_type: LabType | None = None,
        active: bool | None = None,
        country: str | None = None,
    ) -> list[Laboratory]:
        """List laboratories with optional filters."""
        with self._lock:
            result = list(self._labs.values())

        if lab_type is not None:
            result = [lab for lab in result if lab.lab_type == lab_type]
        if active is not None:
            result = [lab for lab in result if lab.active == active]
        if country is not None:
            result = [lab for lab in result if lab.country == country]

        return sorted(result, key=lambda lab: lab.name)

    def get_laboratory(self, lab_id: str) -> Laboratory | None:
        """Get a single laboratory by ID."""
        with self._lock:
            return self._labs.get(lab_id)

    def create_laboratory(self, payload: LaboratoryCreate) -> Laboratory:
        """Create a new laboratory."""
        lab_id = f"LAB-{uuid4().hex[:8].upper()}"
        lab = Laboratory(
            id=lab_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._labs[lab_id] = lab
        logger.info("Created laboratory %s: %s", lab_id, payload.name)
        return lab

    def update_laboratory(self, lab_id: str, payload: LaboratoryUpdate) -> Laboratory | None:
        """Update an existing laboratory."""
        with self._lock:
            existing = self._labs.get(lab_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Laboratory(**data)
            self._labs[lab_id] = updated
        return updated

    def delete_laboratory(self, lab_id: str) -> bool:
        """Delete a laboratory. Returns True if deleted, False if not found."""
        with self._lock:
            if lab_id in self._labs:
                del self._labs[lab_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Certification CRUD
    # ------------------------------------------------------------------

    def list_certifications(
        self,
        *,
        lab_id: str | None = None,
        certification_type: CertificationType | None = None,
        status: CertificationStatus | None = None,
    ) -> list[LabCertification]:
        """List certifications with optional filters."""
        with self._lock:
            result = list(self._certifications.values())

        if lab_id is not None:
            result = [c for c in result if c.lab_id == lab_id]
        if certification_type is not None:
            result = [c for c in result if c.certification_type == certification_type]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.expiry_date)

    def get_certification(self, cert_id: str) -> LabCertification | None:
        """Get a single certification by ID."""
        with self._lock:
            return self._certifications.get(cert_id)

    def create_certification(self, payload: LabCertificationCreate) -> LabCertification:
        """Create a new certification."""
        # Verify lab exists
        with self._lock:
            if payload.lab_id not in self._labs:
                raise ValueError(f"Laboratory '{payload.lab_id}' not found")

        cert_id = f"CERT-{uuid4().hex[:8].upper()}"
        cert = LabCertification(
            id=cert_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._certifications[cert_id] = cert
        logger.info(
            "Created certification %s for lab %s: %s",
            cert_id, payload.lab_id, payload.certification_type.value,
        )
        return cert

    def update_certification(
        self, cert_id: str, payload: LabCertificationUpdate
    ) -> LabCertification | None:
        """Update an existing certification."""
        with self._lock:
            existing = self._certifications.get(cert_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabCertification(**data)
            self._certifications[cert_id] = updated
        return updated

    def delete_certification(self, cert_id: str) -> bool:
        """Delete a certification. Returns True if deleted."""
        with self._lock:
            if cert_id in self._certifications:
                del self._certifications[cert_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Proficiency Testing
    # ------------------------------------------------------------------

    def list_proficiency_tests(
        self,
        *,
        lab_id: str | None = None,
        result: ProficiencyResult | None = None,
        cycle: str | None = None,
    ) -> list[ProficiencyTest]:
        """List proficiency tests with optional filters."""
        with self._lock:
            items = list(self._proficiency_tests.values())

        if lab_id is not None:
            items = [pt for pt in items if pt.lab_id == lab_id]
        if result is not None:
            items = [pt for pt in items if pt.result == result]
        if cycle is not None:
            items = [pt for pt in items if pt.cycle == cycle]

        return sorted(items, key=lambda pt: pt.tested_date, reverse=True)

    def get_proficiency_test(self, pt_id: str) -> ProficiencyTest | None:
        """Get a single proficiency test by ID."""
        with self._lock:
            return self._proficiency_tests.get(pt_id)

    def record_proficiency_test(self, payload: ProficiencyTestCreate) -> ProficiencyTest:
        """Record a new proficiency test result."""
        with self._lock:
            if payload.lab_id not in self._labs:
                raise ValueError(f"Laboratory '{payload.lab_id}' not found")

        pt_id = f"PT-{uuid4().hex[:8].upper()}"
        pt = ProficiencyTest(
            id=pt_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._proficiency_tests[pt_id] = pt
        logger.info(
            "Recorded proficiency test %s for lab %s: %s (%s)",
            pt_id, payload.lab_id, payload.analyte, payload.result.value,
        )
        return pt

    def update_proficiency_test(
        self, pt_id: str, payload: ProficiencyTestUpdate
    ) -> ProficiencyTest | None:
        """Update a proficiency test record."""
        with self._lock:
            existing = self._proficiency_tests.get(pt_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProficiencyTest(**data)
            self._proficiency_tests[pt_id] = updated
        return updated

    def delete_proficiency_test(self, pt_id: str) -> bool:
        """Delete a proficiency test. Returns True if deleted."""
        with self._lock:
            if pt_id in self._proficiency_tests:
                del self._proficiency_tests[pt_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Lab Qualifications
    # ------------------------------------------------------------------

    def list_qualifications(
        self,
        *,
        lab_id: str | None = None,
        trial_id: str | None = None,
        qualification_status: QualificationStatus | None = None,
    ) -> list[LabQualification]:
        """List lab qualifications with optional filters."""
        with self._lock:
            items = list(self._qualifications.values())

        if lab_id is not None:
            items = [q for q in items if q.lab_id == lab_id]
        if trial_id is not None:
            items = [q for q in items if q.trial_id == trial_id]
        if qualification_status is not None:
            items = [q for q in items if q.qualification_status == qualification_status]

        return sorted(items, key=lambda q: q.id)

    def get_qualification(self, qual_id: str) -> LabQualification | None:
        """Get a single qualification by ID."""
        with self._lock:
            return self._qualifications.get(qual_id)

    def qualify_lab_for_trial(self, payload: LabQualificationCreate) -> LabQualification:
        """Qualify a laboratory for a clinical trial.

        If all prerequisites (training, equipment, SOP) are met, the lab is
        automatically set to QUALIFIED status. Otherwise it is set to PENDING.
        """
        with self._lock:
            if payload.lab_id not in self._labs:
                raise ValueError(f"Laboratory '{payload.lab_id}' not found")

        now = datetime.now(timezone.utc)
        qual_id = f"QUAL-{uuid4().hex[:8].upper()}"

        # Determine qualification status based on prerequisites
        all_prereqs = (
            payload.training_completed
            and payload.equipment_verified
            and payload.sop_reviewed
        )

        if all_prereqs:
            status = QualificationStatus.QUALIFIED
            qualified_date = now
        else:
            status = QualificationStatus.PENDING
            qualified_date = None

        qual = LabQualification(
            id=qual_id,
            lab_id=payload.lab_id,
            trial_id=payload.trial_id,
            qualified_date=qualified_date,
            qualification_status=status,
            assays_qualified=payload.assays_qualified,
            training_completed=payload.training_completed,
            equipment_verified=payload.equipment_verified,
            sop_reviewed=payload.sop_reviewed,
            qualified_by=payload.qualified_by,
            notes=payload.notes,
        )
        with self._lock:
            self._qualifications[qual_id] = qual
        logger.info(
            "Qualification %s created for lab %s trial %s: status=%s",
            qual_id, payload.lab_id, payload.trial_id, status.value,
        )
        return qual

    def update_qualification(
        self, qual_id: str, payload: LabQualificationUpdate
    ) -> LabQualification | None:
        """Update a lab qualification.

        Automatically promotes to QUALIFIED and sets qualified_date when all
        prerequisites become met (unless explicitly set to another status).
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._qualifications.get(qual_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)

            # Auto-promote if all prerequisites now met
            training = data.get("training_completed", False)
            equipment = data.get("equipment_verified", False)
            sop = data.get("sop_reviewed", False)

            if (
                training and equipment and sop
                and "qualification_status" not in updates
                and data.get("qualification_status") in (
                    QualificationStatus.PENDING.value,
                    QualificationStatus.CONDITIONALLY_QUALIFIED.value,
                    QualificationStatus.PENDING,
                    QualificationStatus.CONDITIONALLY_QUALIFIED,
                )
            ):
                data["qualification_status"] = QualificationStatus.QUALIFIED
                if data.get("qualified_date") is None:
                    data["qualified_date"] = now

            updated = LabQualification(**data)
            self._qualifications[qual_id] = updated
        return updated

    def delete_qualification(self, qual_id: str) -> bool:
        """Delete a qualification. Returns True if deleted."""
        with self._lock:
            if qual_id in self._qualifications:
                del self._qualifications[qual_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compliance Findings
    # ------------------------------------------------------------------

    def list_compliance_findings(
        self,
        *,
        lab_id: str | None = None,
        certification_id: str | None = None,
        severity: FindingSeverity | None = None,
        status: ComplianceFindingStatus | None = None,
    ) -> list[ComplianceFinding]:
        """List compliance findings with optional filters."""
        with self._lock:
            items = list(self._findings.values())

        if lab_id is not None:
            items = [f for f in items if f.lab_id == lab_id]
        if certification_id is not None:
            items = [f for f in items if f.certification_id == certification_id]
        if severity is not None:
            items = [f for f in items if f.severity == severity]
        if status is not None:
            items = [f for f in items if f.status == status]

        return sorted(items, key=lambda f: f.identified_date, reverse=True)

    def get_compliance_finding(self, finding_id: str) -> ComplianceFinding | None:
        """Get a single compliance finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def log_compliance_finding(self, payload: ComplianceFindingCreate) -> ComplianceFinding:
        """Log a new compliance finding."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if payload.lab_id not in self._labs:
                raise ValueError(f"Laboratory '{payload.lab_id}' not found")
            if (
                payload.certification_id is not None
                and payload.certification_id not in self._certifications
            ):
                raise ValueError(
                    f"Certification '{payload.certification_id}' not found"
                )

        finding_id = f"CF-{uuid4().hex[:8].upper()}"
        finding = ComplianceFinding(
            id=finding_id,
            lab_id=payload.lab_id,
            certification_id=payload.certification_id,
            finding_type=payload.finding_type,
            severity=payload.severity,
            description=payload.description,
            identified_date=now,
            due_date=payload.due_date,
            resolved_date=None,
            corrective_action=payload.corrective_action,
            status=ComplianceFindingStatus.OPEN,
        )
        with self._lock:
            self._findings[finding_id] = finding

        # Increment finding count on associated certification
        if payload.certification_id:
            with self._lock:
                cert = self._certifications.get(payload.certification_id)
                if cert:
                    data = cert.model_dump()
                    data["findings_count"] = data.get("findings_count", 0) + 1
                    data["corrective_actions_pending"] = (
                        data.get("corrective_actions_pending", 0) + 1
                    )
                    self._certifications[payload.certification_id] = LabCertification(
                        **data
                    )

        logger.info(
            "Logged compliance finding %s for lab %s: %s (%s)",
            finding_id, payload.lab_id, payload.finding_type.value,
            payload.severity.value,
        )
        return finding

    def update_compliance_finding(
        self, finding_id: str, payload: ComplianceFindingUpdate
    ) -> ComplianceFinding | None:
        """Update a compliance finding."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolved_date when status goes to resolved
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ComplianceFindingStatus(new_status)
                if (
                    new_status == ComplianceFindingStatus.RESOLVED
                    and existing.status != ComplianceFindingStatus.RESOLVED
                ):
                    updates["resolved_date"] = now

            data.update(updates)
            updated = ComplianceFinding(**data)
            self._findings[finding_id] = updated
        return updated

    def delete_compliance_finding(self, finding_id: str) -> bool:
        """Delete a compliance finding. Returns True if deleted."""
        with self._lock:
            if finding_id in self._findings:
                del self._findings[finding_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Expiring Certifications
    # ------------------------------------------------------------------

    def get_expiring_certifications(
        self, *, days: int = EXPIRING_SOON_DAYS
    ) -> list[LabCertification]:
        """Get certifications expiring within the specified number of days.

        Only returns active or pending certifications (not already expired/revoked).
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)

        with self._lock:
            result = [
                c for c in self._certifications.values()
                if c.status in (CertificationStatus.ACTIVE, CertificationStatus.PENDING)
                and c.expiry_date <= cutoff
            ]

        return sorted(result, key=lambda c: c.expiry_date)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> LabMetrics:
        """Compute aggregated lab certification metrics."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=EXPIRING_SOON_DAYS)

        with self._lock:
            labs = list(self._labs.values())
            certs = list(self._certifications.values())
            pts = list(self._proficiency_tests.values())
            quals = list(self._qualifications.values())
            findings = list(self._findings.values())

        # Labs
        active_labs = sum(1 for lab in labs if lab.active)
        labs_by_type: dict[str, int] = {}
        for lab in labs:
            key = lab.lab_type.value
            labs_by_type[key] = labs_by_type.get(key, 0) + 1

        # Certifications
        active_certs = sum(
            1 for c in certs if c.status == CertificationStatus.ACTIVE
        )
        expired_certs = sum(
            1 for c in certs if c.status == CertificationStatus.EXPIRED
        )
        expiring_soon = sum(
            1 for c in certs
            if c.status in (CertificationStatus.ACTIVE, CertificationStatus.PENDING)
            and c.expiry_date <= cutoff
        )
        certs_by_status: dict[str, int] = {}
        for c in certs:
            key = c.status.value
            certs_by_status[key] = certs_by_status.get(key, 0) + 1

        # Proficiency tests
        graded_pts = [
            pt for pt in pts
            if pt.result in (ProficiencyResult.SATISFACTORY, ProficiencyResult.UNSATISFACTORY)
        ]
        satisfactory_count = sum(
            1 for pt in graded_pts if pt.result == ProficiencyResult.SATISFACTORY
        )
        satisfactory_rate = (
            round(satisfactory_count / len(graded_pts) * 100, 1) if graded_pts else 0.0
        )

        # Qualifications
        qualified_count = sum(
            1 for q in quals if q.qualification_status == QualificationStatus.QUALIFIED
        )

        # Findings
        open_findings = sum(
            1 for f in findings
            if f.status in (
                ComplianceFindingStatus.OPEN,
                ComplianceFindingStatus.IN_PROGRESS,
            )
        )
        overdue_findings = sum(
            1 for f in findings if f.status == ComplianceFindingStatus.OVERDUE
        )
        # Also count findings past due date that are still open
        overdue_findings += sum(
            1 for f in findings
            if f.status in (
                ComplianceFindingStatus.OPEN,
                ComplianceFindingStatus.IN_PROGRESS,
            )
            and f.due_date < now
        )
        critical_findings = sum(
            1 for f in findings
            if f.severity == FindingSeverity.CRITICAL
            and f.status not in (
                ComplianceFindingStatus.RESOLVED,
                ComplianceFindingStatus.VERIFIED,
            )
        )

        return LabMetrics(
            total_labs=len(labs),
            active_labs=active_labs,
            labs_by_type=labs_by_type,
            total_certifications=len(certs),
            active_certifications=active_certs,
            expiring_soon=expiring_soon,
            expired_certifications=expired_certs,
            certifications_by_status=certs_by_status,
            total_proficiency_tests=len(pts),
            satisfactory_rate=satisfactory_rate,
            total_qualifications=len(quals),
            qualified_count=qualified_count,
            total_compliance_findings=len(findings),
            open_findings=open_findings,
            overdue_findings=overdue_findings,
            critical_findings=critical_findings,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: LabCertificationService | None = None
_instance_lock = threading.Lock()


def get_lab_certification_service() -> LabCertificationService:
    """Return the singleton LabCertificationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LabCertificationService()
    return _instance


def reset_lab_certification_service() -> LabCertificationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = LabCertificationService()
    return _instance
